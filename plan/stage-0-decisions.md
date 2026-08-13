# Stage 0 decisions

**Status:** Stage 0 slices 1-6 and Stage 1 slice 7 built and green — **292 tests (+3 opt-in live), ruff clean, mypy
strict clean.** Slice 1 is the model-free manuscript spine; slice 2 the Conductor skeleton
(tick, instance lease, job selection, digest, outbox dispatch, crash recovery); slice 3 the
four provider adapters with their conformance suite and the billing guard; slice 4 **the
first path on which generated text reaches accepted canon** — job payloads, the draft shape
gate, and a provider-backed handler wired into the tick; slice 5 **the acceptance decision
record and the direction inbox**.

PLAN.md §20.4 warns that Stage 0 carries "roughly half a dozen load-bearing design
decisions [that] are genuinely open and an agent will silently invent answers to all of
them". This is the record of those answers. Each one is implemented, tested, and stated
with the reason, so a later change is a decision rather than a discovery.

## 1. Text normalization for hashing — LF + NFC, canonicalized on ingest

`domain/text.py`. Line endings normalize to LF, Unicode to NFC, and the canonical form is
what gets stored, so a stored hash is always verifiable against the stored text.

The evidence is local: earlier the same day, `litharness-contracts` was one commit away
from having every evidence-span `content_sha256` invalidated by a Windows checkout,
because `core.autocrlf=true` rewrites LF to CRLF on the way out of git. A hash over
un-normalized text is a latent platform bug, not a style question. Hashing before storing
would have been the other half of the same mistake.

**Offsets are character offsets into the canonical string; hashes are over its UTF-8
encoding.** This matches how contracts' existing consumers resolve evidence
(`text[start:end]` on a `str`, then `.encode("utf-8")`), so a span produced here resolves
there with no coordinate conversion. Byte offsets were the other defensible choice; they
are not interchangeable, and mixing them silently mis-slices any non-ASCII text.

## 2. Position keys — gap-10, fixed width, rebalance only when no midpoint exists

`domain/position.py`. Contracts pins `position_key` as a string and both fixtures use
zero-padded gap-10 (`"010".."060"`), so the format is a compatibility requirement.

The decision is that **width is a property of the sibling set**, because keys are compared
as strings and `"100" < "20"`. Inserting a key that needs more digits therefore widens the
whole set. Insertion takes the integer midpoint; with gap 10 there are nine free slots, so
the common case never rebalances. A rebalance returns the full old→new mapping rather than
mutating in place, because position keys appear in revisions and a silent renumbering
would be invisible corruption of ordering.

## 3. Node-version fan-out — per-node content addressing, not Merkle

`domain/revision.py`. This is the decision with the widest consequences and it went
against the obvious choice.

Under a Merkle scheme, editing one scene changes its chapter's version id, its part's, and
the book's — so **every evidence span citing any ancestor goes stale on every edit**. Under
per-node addressing, editing scene 3 changes scene 3's id and nothing else. That is what
makes §12's "unchanged text is structurally ineligible for revision" mechanically true
rather than aspirational, and it is what lets a finding raised against scene 1 survive an
unrelated edit to scene 5.

A revision id still covers the whole node set, so the *snapshot* is content-addressed even
though nodes are addressed independently. Tested:
`test_editing_one_node_leaves_every_other_node_version_untouched`.

## 4. Branch fork — shared-immutable, not copy-on-write

`domain/revision.py`, and free in storage because `node_versions.version_id` is a content
address with `INSERT OR IGNORE`. A fork is a new revision row on a new `branch_id` pointing
at the same node versions.

Copy-on-write would double storage, but the real objection is correctness: it would produce
two distinct version ids for identical text, making a span citing one branch silently
unresolvable on the other. Tested: `test_fork_stores_no_new_node_versions`.

**Known ceiling:** lineage is single-parent because contracts pins `parent_revision_id` as
a single value, so this model cannot express a merge. §4.7's branch-merge story needs a
contract change first; `parents` is deliberately not a list rather than half-supported.

## 5. Lock taxonomy — four kinds behind the contract's boolean

`domain/nodes.py`. `locked: bool` cannot distinguish "the director vetoed this sentence"
from "this chapter is published and a retcon needs an erratum policy" (§16). So:
`NONE`, `CONTENT` (text frozen), `STRUCTURE` (children and order frozen), `PUBLISHED`
(both, and a change requires a publication-policy decision).

It projects onto the contract as `locked = kind is not NONE`, so a consumer that only
understands the boolean still sees every lock and never mistakes a locked node for a free
one. **Promoted to a real field in contracts 1.1.0** (`lock_kind`), along with
`block_kind`, `block_payload` and the tombstone pair; it rode in `metadata` until then so
the wire shape would be proven by a consumer before being frozen upstream. `from_contract`
still reads the `metadata` form, because revisions are immutable and content addressed and
1.0-era nodes stay readable forever by design.

## 6. Blob/DB write ordering — one transaction now, blob-first later

`adapters/sqlite_store.py`. There is no separate blob store yet: node content is a TEXT
column, so a revision, its node versions, its events and its outbox rows all commit in one
transaction. There is no window in which accepted prose exists without the event recording
it.

The rule for when content does move to blobs is recorded now, because it is the crash bug
most likely to be gotten backwards: **write the blob, fsync, then commit the row that
references it.** An orphaned blob is garbage a sweep reclaims; a row referencing a missing
blob is unrecoverable corruption. The asymmetry is the whole argument.

## 7. Outbox — send-then-mark, at-least-once, dedupe on a derived key

`domain/events.py`. Rows are inserted in the state-change transaction, delivered, and only
then marked sent. Mark-then-send would be at-most-once — silent loss — which is the worse
failure for a system whose audit story rests on the event log.

`idempotency_key` is derived from the event's own content, not random, so a replayed
event collapses at insert. The subtle case is covered by
`test_redelivery_after_dispatch_does_not_requeue_the_outbox`: a duplicate arriving *after*
delivery must not resurrect a dispatched row, which is why the outbox insert is gated on
the event insert actually having created a row.

## 8. Leases — net-new, injected clock, re-checked at every write

`domain/jobs.py`. Contracts' `JobRecord` had no lease concept at all when this was
written, confirming §20.3's list; **contracts 1.1.0 has since added
`lease_holder`/`lease_expires_at`, and `to_contract` is lossless as a result.** A lease is
a holder plus a wall-clock expiry; claiming is a single `BEGIN IMMEDIATE` transaction so
two overlapping cron ticks cannot both win.

Two decisions worth stating. **Time is injected, not read from the clock**, because a
scheduler whose correctness depends on the clock has to be testable without waiting. And
**every state-advancing write re-checks the lease** (`assert_held_by`) rather than trusting
the claim from earlier in the tick — a paused process can wake believing it still holds an
expired lease. Repeated failure poisons rather than requeuing, which is §4.2's "the failure
mode is a parked unit, never a spin loop".

## 9. The tick contract — leadership first, one bounded unit, idempotent by id

`application/conductor.py`. Four decisions in the loop itself.

**A tick that is not the leader does nothing at all** — not even reconcile or dispatch,
because both mutate shared state. The instance lease is claimed first and everything else
is inside that guard. The instance lease is deliberately a separate table from the job
lease: the job lease answers "who is working this unit", the instance lease answers "who is
the Conductor right now", and conflating them would let two instances each pick a different
job and both believe they were alone.

**Tick ids are derived from `(scope, holder, instant)` and recorded with `INSERT OR
IGNORE`.** A replayed tick — a cron invocation retried after a crash at an awkward moment —
therefore cannot double-count the digest or re-run work. Verified over 200 instants replayed
in full.

**Exactly one bounded unit per tick**, then return. This is what makes a failing unit unable
to starve the queue, and it is checked directly: a poisoning job and a good job in the same
queue both reach a terminal state, with the good one confirmed to have run.

**The default dispatcher refuses delivery.** With no sink configured, events stay pending
rather than being marked sent. A default that silently marked them delivered would be loss
dressed as success, and the whole audit story rests on that log.

**Reconciliation is two recoveries, and the second was missing.** `reclaim_expired` rescues
a unit whose holder crashed mid-job (RUNNING with a dead lease is invisible to
`claim_next`). `requeue_failed` advances a unit that failed cleanly. The loop originally had
only the first, which left every FAILED job inert forever — no retry, no poison, no
escalation, looking like a parked unit but actually a lost one. The non-starvation test
caught it. Adding it also exposed a missing edge in the job state machine: `RUNNING →
QUEUED` had been omitted as "not a happy-path move", which is exactly why a crashed job
could never be recovered.

## 10. Endurance — measured in ticks, not in wall-clock time

Stage 0's exit says the Conductor "ticks idempotently for a week unattended". A week of
waiting is not a test, so `test_a_week_of_no_op_ticks_changes_nothing` runs the **2,016
ticks a week produces at the plan's 5-minute cadence** with injected time, and asserts what
would actually break: every outcome is `no_work`, the tick count matches exactly, the
digest accumulated once per tick across all seven days, and `revisions`, `node_versions`,
`events`, `outbox` and `jobs` are all still empty — state growth bounded to the tick log
itself. Runs in ~9 seconds.

**This is not a claim about process uptime.** It measures unbounded state growth and
non-idempotent accumulation, which are the failure modes a week would surface. It does not
measure a long-lived process surviving a week of real scheduling, OS sleep, clock changes or
database file growth. Stage 0's exit criterion is therefore *evidenced*, not met, and the
distinction should survive into any status report.

## 11. Provider adapters — capability is per-adapter, and `bills` is identity

`providers/`. Four adapters behind one `CompletionRequest`/`CompletionResult` contract:
`fake` (deterministic, free), `ollama` (local, native JSON Schema), `claude_code` (default),
`codex` (fallback).

**`bills` is a property of the adapter, not a config flag.** Whether a call consumes paid
quota decides whether a test run may touch it, so it belongs to the adapter's identity — a
new provider cannot be added without answering the question. The registry filters billing
providers out of resolution entirely in test mode rather than deprioritising them, which is
what makes the guard hold even when `order` is misconfigured. `tests/conftest.py` sets
`LITHARNESS_ENV=test` at import so the guard is structural for the whole suite, and one test
asserts it — a guard nobody checks is a guard that stops applying the day the conftest
changes.

**Structured output is a per-adapter capability.** Ollama enforces a schema natively via
`format`; `codex exec` via `--output-schema`; `claude -p` has no equivalent and returns
fenced markdown, so that adapter strips fences, parses, and reports failure as `parsed is
None`. A malformed answer is a shape-gate result earning a bounded retry (§4.2 ladder step
1), never an exception that kills the unit of work.

**Both CLI adapters take an injected runner, and that is what makes them testable.** Their
parsing is verified against **real captured envelopes** from the installed tools rather than
invented shapes — including the `claude -p` fence, its cache-read/cache-write split, codex's
four-event JSONL with usage on `turn.completed`, and codex's `reasoning_output_tokens`. Live
round trips exist but are opt-in behind `LITHARNESS_LIVE_PROVIDERS=1`, because a suite that
silently invokes a paid CLI on every run is a suite nobody can afford to run often.

**Health probes are round trips, not version checks** — the rule codex earned by spending a
whole CLI generation installed, authenticated, on PATH, and failing every call. Verdicts are
cached per tick, and a probe that raises counts as unhealthy rather than crashing the caller.

**A fallback is returned, not swallowed.** `resolve` reports which providers were skipped so
the caller can record the switch as an event; §5 rule 4 forbids a silent change of
provenance.

## 12. A job carries its input — and the blocker nobody had written down

`domain/jobs.py`, `migrations/003_job_input.sql`. PLAN.md §20.4 said the three remaining
Stage 0 items "all need subsystems that do not exist yet". For wiring the registry into a
handler that was simply false, and the diagnosis hid the real obstacle: **`Job` carried
`input_digest` — a hash — and no input.** A handler satisfying the `JobHandler` protocol
received a job it could not reconstruct a prompt from, so the four working adapters had no
possible consumer for reasons that had nothing to do with planners or context packets.

The digest keeps its dedupe role and `payload` sits beside it rather than replacing it,
because they answer different questions: the digest says "this is the same work", the
payload says "this is the work". `input_digest_for` delegates to `events.payload_digest`
so the package has one canonical-JSON-digest definition; two would drift, and the failure
would be silent — a job enqueued through one path would stop deduplicating against the
same job enqueued through the other.

An empty payload stores NULL rather than `"{}"`, so the no-op workload the endurance test
runs does not pay for a column it never uses, and "no input" stays distinguishable from
"empty input".

## 13. Claim ordering — priority now, policy later

`adapters/sqlite_store.py`. `fifo_selector`'s docstring blamed the missing plan graph and
findings store for the placeholder policy. True, but incomplete in a way worth recording:
`claim_next` hardcoded `ORDER BY rowid`, so **no ordering other than FIFO was expressible
at any layer** regardless of which subsystems existed. The selector seam was real; the
storage underneath it was not.

`priority INTEGER NOT NULL DEFAULT 0` plus `ORDER BY priority DESC, rowid` fixes that, and
at the default it is byte-identical to the FIFO it replaces — `fifo_selector` keeps its
exact meaning and no existing test changed. **A severity policy is deliberately not built
here.** With no findings store the column would have exactly one value, and a selector
over a constant is theatre that would later have to be unpicked.

`rowid` is absent from the index key because SQLite refuses to index it by name — and does
not need to, since every b-tree index carries the rowid as payload and breaks ties on it
ascending. That is the exact tiebreak the ORDER BY wants, and
`test_priority_ties_break_on_insertion_not_on_id` pins it rather than trusting it.

## 14. Drafting is not revising, and the type system says so

`domain/draft.py`. The decision with the widest consequences in this slice, and it is an
architectural boundary rather than a validation detail.

`apply_patch` gates a *change* to existing text. `gate_draft` gates a node's *first* prose.
They are separate functions because the interesting rule is the one that separates them:
**`DraftPolicy.allow_overwrite` defaults to False, so a draft may only fill emptiness.**
Rewriting must route through `apply_patch`, where `Veto.UNLICENSED_DELETION` requires a
located complaint.

This is §1a.2 and §12 made mechanical. Once a handler can generate and commit, the obvious
next move is "have it improve the scene it just wrote" — the open-ended revision loop the
plan forbids, with RevisionBench's ~80% preference for human originals as the measured
evidence against it. The default is what makes that move impossible by accident rather
than merely discouraged in prose, and
`test_a_draft_will_not_overwrite_existing_prose` fails if it is flipped. Do not relax it
as a convenience.

Vetoes are shared with `patch.py` in one `Veto` enum rather than split per gate, so a
policy decision record cites the same name whichever gate produced it. Two additions:
`EMPTY_DRAFT` and `SHAPE_NOT_CONFORMING`, the latter fed directly by
`CompletionResult.conforms` — a schema miss is a §4.2 ladder-step-1 result earning a
bounded retry, never an exception that kills the unit.

## 15. The handler commits the revision; the Conductor commits the job

`application/handlers.py`. `JobHandler` returns events and must not write to the store —
except that a draft handler must, because `commit_revision` is the only call that puts a
revision and its event in one transaction. Both are true, and the resolution is a
deliberate asymmetry: **the revision and its `ManuscriptRevisionAccepted` event are atomic
with each other; the job's status row is not atomic with either.**

`Conductor._run` commits handler events and the job row separately, so a crash between
them replays the job. That gap is not closed by pretending — it is closed by making the
work converge: revisions are content-addressed and inserted with `INSERT OR IGNORE`, and
event idempotency keys are content-derived, so a replay produces the same revision id and
the same event key and collapses.
`test_replaying_the_job_converges_instead_of_duplicating` runs the handler twice and
asserts one accepted revision and one event.

The accepted event returns an empty sequence from the handler because `commit_revision`
already persisted it; returning it as well would be harmless (the key collapses) but would
misreport the tick's event count.

**A refused candidate still emits an event.** Silence would make a refusal unauditable and
hide a provider that had started returning stubs. Both events carry the provider, model,
profile, fallback chain and usage — §5 rule 4 forbids a silent provenance switch, and a
gate failure from a degraded fallback is a different diagnosis from one from the primary.
Neither is a policy decision record; that schema does not exist yet (§20.3), so the gate
results ride in the payload, which is the consumer-first evidence for what that record
must eventually hold.

## 16. `reset_health` gets the caller its own docstring promised

`application/conductor.py`. `ProviderRegistry.reset_health` documented "called at the start
of a tick" and had no non-test caller, so a provider marked dead by one failed probe stayed
dead for the life of the process and could never recover. Harmless while nothing owned a
registry; a live bug the moment slice 4 gave one a consumer.

The Conductor takes an optional `registry` typed as a structural `HealthResettable`
protocol rather than importing `ProviderRegistry`, so the loop keeps its one-way dependency
on `providers` at the handler layer. The reset happens **after** the leadership guard — a
non-leader must not touch shared state — and **before** reconcile, so every probe in a tick
sees one consistent verdict per provider.

## What these slices do not include

Deliberately deferred, in the order they should land:

1. ~~**Directive ingestion**~~ — **capture half built in slice 5b; interpretation still
   deferred.** The original reasoning ("a directive inbox without the Narrative Planner to
   interpret it would be a queue nothing can read") turned out to argue for half the work,
   not none of it. Capture needs nothing that is missing and losing direction the director
   gives *today* because the reader ships later is the worse failure. So directives are
   captured, drained at the top of each tick, and left in `RECEIVED` — visible as a growing
   unread count and as `interpreted: false` in the event log, rather than as silence or an
   invented reading. `Directive.interpret` is the seam §9 will attach to.
2. **A real work-selection policy.** `fifo_selector` is still a placeholder behind a
   `WorkSelector` protocol, but the *storage* under it no longer is — see decision 13. What
   remains genuinely blocked is the policy: §4.1 wants selection over the book's state
   (unblocked beats, findings by severity), which needs a plan graph and a findings store
   that do not exist. FIFO is honest about being a placeholder; a cleverer arbitrary
   ordering would not be.
3. **Retry backoff.** Retries are immediate on the next tick, bounded only by the attempt
   budget. A `next_attempt_at` column would add backoff and is not invented until something
   needs a specific delay.
4. ~~**Wiring the registry into the Conductor.**~~ **Done in slice 4** — decisions 12 and
   15. The stated reason for deferring ("the first real handler is a Stage 1 concern: a
   scene draft needs a plan and a context packet") was true of a *planned* scene draft and
   false of wiring; the actual obstacle was a missing payload column. `make_scene_draft_handler`
   is a closure satisfying `JobHandler` with zero Conductor changes. What is still a Stage 1
   concern is where the prompt comes from: today the caller supplies it in the job payload,
   because there is no planner to derive it from a beat and no context packet to ground it.
5. **Contracts 1.x minors** (§20.3) — and these slices are what make them safe to write:
   `lease_holder`/`lease_expires_at`/**`payload`**/**`priority`** on `JobRecord`,
   `block_kind`/`block_payload` and a lock enum on `ManuscriptNode`, and the Conductor
   `EventType` additions are now shapes proven by a consumer rather than guesses. Slice 4
   adds a sixth: the **policy decision record**, whose required fields are currently the
   provenance dict in `handlers.py` and are asserted by
   `test_the_accepted_event_carries_the_provenance_a_policy_record_will_need`.
6. **A craft gate of any kind.** Nothing here measures whether the prose is good — §1a.1's
   distinction, stated plainly so a green suite is not misread. `gate_draft` checks that a
   draft exists, is the right shape, and did not overwrite anything. A scene that passes
   every gate in this repo can still be dead on the page.

## Two fixes this work forced upstream

Both in `litharness-contracts`, commit `2d1e759`, found by being its first strict-typed
consumer:

* **No `py.typed` marker** — mypy skipped the package entirely, so every consumer's
  annotations against contract types were unchecked.
* **No `__all__`** — under `--no-implicit-reexport` the package re-exported *nothing*, so
  `lc.Finding` and `lc.ManuscriptRevision` failed to resolve at exactly the boundary the
  package exists to define. 90 names now exported.

All consuming suites stayed green: contracts 126, ContinuityEvaluation 42,
LongRangeContext 17, BookWorldState 100, LitHarness **240** (was misreported as 76 here
and in PLAN.md §20.4 through slice 3; corrected in the v2.2 pass).

## 17. Acceptance is a recorded decision, and refusals are recorded as fully as acceptances

`domain/policy.py`, `migrations/004_policy_decisions.sql`. §19 makes "every mutation is
attributable to a recorded policy decision" part of operator-grade, and slice 4 met that
only in spirit — the gate results lived in a free-form event payload, so "why was this
accepted" meant parsing prose out of a map. `store.decision_for_revision` now makes the
claim checkable.

Three decisions, each pinned by a test.

**A veto a retry cannot fix must not consume the retry budget.** Vetoes are partitioned:
`RETRYABLE` earns another bounded attempt, `REGENERABLE` earns a fresh candidate against a
re-read base, and everything else escalates. The *ordering* inside `decide` is the
substance — an unclassified veto escalates before the attempt budget is consulted, so a
locked node reports as locked on the first attempt rather than as "attempts exhausted" on
the fourth with the real cause buried. Escalation is deliberately the default for a veto
nobody has triaged: it should reach a human, not silently earn three more model calls.

**A blocking gate may not source its verdict from the model that wrote the text.**
Enforced in `PolicyDecision.__post_init__` rather than documented, because MirrorBench's
result is that self-report is not a correctness signal and a rule nobody checks is a rule
that stops applying. Self-reported verdicts remain *recordable* when they do not gate —
recorded so they can be refused, not banned from the record. Likewise an uncalibrated
craft gate may not block (§10.4), so "until then it annotates" cannot quietly become
permanent.

**Passing gates are recorded too.** A decision listing only failures cannot distinguish a
candidate that cleared the full ladder from one that was never checked, and that is the
first question an audit asks.

## 18. The direction inbox captures without interpreting, and says so

`domain/directives.py`, `migrations/005_directives.sql`, and ingest as step 1 of the tick.

**Ingest runs before selection**, which is §4.1's order and not an arbitrary one: a
directive that arrived since the last tick must be able to influence what this tick picks
up, and if selection ran first it would sit unread for a full cycle behind the work it was
meant to redirect. It sits inside the leadership guard with everything else, because it
mutates shared state.

**Only capture is built.** The earlier note here argued that an inbox without the Narrative
Planner "would be a queue nothing can read" and concluded: build neither half. That was
half right. Capture needs nothing missing, and losing direction the director gives today
because the reader ships later is the worse failure. So a directive is drained, recorded,
and left in `RECEIVED`. The absence is *visible* rather than hidden — a growing unread
count, and `interpreted: false` / `awaiting: narrative_planner` in the event log — which is
the difference between work queued and work dropped. `Directive.interpret` is the single
transition out, so §9 inherits a seam rather than a schema negotiation.

**The director's words are immutable and stored apart from what the system decided they
meant.** `body` is never rewritten; `interpretation` records the reading. Collapsing them
would make a misinterpretation invisible afterwards, and "the system quietly understood
'less combat' as 'no combat'" is exactly what this separation exists to catch.

**Precedence is explicit, not arrival order.** A veto issued Monday must outrank a tone
note issued Tuesday, and a queue resolving conflicts by recency would silently reverse
that. `VETO` defaults highest; the drain query orders by precedence and breaks ties on
arrival.

## 19. Importing is not deserializing, and the id assertion stays

`domain/revision.py` (`import_manuscript`), `adapters/contracts_fixtures.py`, `cli import`.

The system was a **closed loop with no entry point**, and nothing in this document or
PLAN.md had noticed. Fifteen subcommands and not one created a revision; `enqueue` requires
`--revision`; the only way to obtain a revision id was to commit a revision; and the only
caller of `commit_revision` outside the store was the draft handler, which needs a job,
which needs the id. Every operator verb in §4.3 — `revert`, `verify`, `enqueue` — acted on
a book that no command could bring into existence. It went unnoticed because the suite
builds its book in `conftest.make_revision()`, so every test had an entry the product did
not.

**`from_contract` cannot load the golden fixtures and must keep refusing them.** Contracts
mints `revision_id` as a UUID5; this package computes a sha256 over content; the classmethod
asserts the rebuilt id equals the serialized one. Every contracts-authored manuscript
therefore fails it, and the obvious fix — an `expected_revision_id` parameter, or dropping
the assertion — would delete the round-trip corruption check for the artifacts it exists to
protect, which are the ones *this* system wrote. So there are two operations, not one
loosened operation: `from_contract` restores our own artifact and asserts; `import_manuscript`
adopts a foreign one, rebuilds the id, and carries the source id as provenance. The check
that does the real work is untouched — `Node.from_contract` verifies every node's
`content_sha256` against its text, and that is what catches a manuscript read with the wrong
codec. `test_from_contract_still_refuses_the_fixtures` exists because the wrong fix and the
right one are indistinguishable from the outside once the fixtures load.

**Scene prose is cleared on import, and that is the operation rather than a convenience.**
`gate_draft` refuses any node that already carries content — decision 14, and §12's rule
that a rewrite needs a located complaint. A fixture imported with its prose intact is
therefore a book with six scenes and nothing to draft: it looks like progress and can take
no work. Clearing is what §17 Stage 1's "regenerate from premise" means mechanically.
`--keep-content` exists for inspection and prints that no scene is draftable, because a flag
whose consequence is invisible is a trap. Only `SCENE` nodes are cleared, because a scene is
the unit a `scene_draft` job fills; titles, ordering and parentage are the frame generation
happens *inside*, not output to reproduce. A content-locked scene is left alone and
**reported**: `replace` bypasses `with_content`'s lock check, so the lock is honoured
explicitly here, and the operator is told which scenes it cost them.

**Only a root revision can be imported.** A source carrying a `parent_revision_id` names an
ancestor that is not in this store, and `lineage` walks parents until it reaches one — so a
silently re-parented import produces a book that fails `verify` the first time anyone asks
for its history. Refused with the reason.

**The import is attributed and carries no gates.** §19 makes every mutation attributable to
a recorded policy decision, and an import is a mutation, so it writes one — keyed on the
*resulting* revision, so re-importing identical content collapses onto one decision while a
`--keep-content` import of the same book still gets its own. Its `gates` tuple is empty on
purpose: the two checks that run raise *before* a decision exists, so recording them as
passed would be a gate that cannot fail, which is the objection §8.3 raises against
recall-only fixture grading. An import is attributed, not gated.

**Fixture discovery is a chain, and no link is an absolute path.** The golden books live
under `fixtures/golden/` at the contracts repository root, outside the importable package,
so `importlib.resources` cannot reach them. `LITHARNESS_CONTRACTS_ROOT` first (the variable
LongRangeContext already uses — a second name for one setting is how two checkouts end up
configured differently), then the installed package's own location, then a sibling checkout.
Each candidate is tested for the *manuscript*, not the directory. PLAN.md §20.2 records a
machine-bound `samefile("C:/DEV/litharness-contracts/schemas")` as a defect worth fixing in
a sibling repository; hard-coding one here would have been the same bug.

## 20. Beats are derived, not stored

`domain/beats.py`, `migrations/011_plan.sql`. Stage 1 asks for a *template planner (fixed
beat sheet)*, and the imported manuscript already **is** the ordered, addressable set of
work units: `Revision.in_reading_order()` walks `children_of`, which sorts by
`(parse_key(position_key), logical_id)` and drops tombstones.

So there is no `beats` table, no `scene_plan` row per node, and no `status`/`done`/`ordinal`
column. The reason is sharper than "avoid duplication". `TARGET_HAS_NO_CONTENT` and
`CONTENT_LOCKED` are in neither `RETRYABLE` nor `REGENERABLE`, so `decide` escalates them
before consulting the attempt budget and `_settle` parks the unit **and files an
exception**. A stored "is this beat done" flag that drifted from the manuscript would
therefore not merely waste a tick — it would fill the queue §4.3 reserves for the director
with work nobody asked a human about. `draft_block` is extracted from `gate_draft` so the
selector's precondition is *literally* the gate's: one function, two callers, drift
impossible rather than merely unlikely.

What does get a table is the half `import` was throwing away: the premise, promises and
locked constraints in `plans.json`. The premise is the one thing a prompt cannot be
rendered without. `authority`, `locked` and `links` ride inside `item_json` rather than
becoming columns, because nothing in this slice reads them — §20.3's rule that a shape gets
proven by a consumer first.

**A scene-count mismatch refuses rather than interpolating.** Six template functions
against five or seven scenes has no defensible mapping, and choosing one silently would
mislabel the dramatic function of every beat after the gap.

## 21. One draft in flight per book, and why that is what keeps history linear

`application/planner.py`. The selector drains the queue before consulting the plan, and
refuses to plan a book that already has a queued or running beat.

This is the invariant that stops the branch forking. A job payload freezes its base
revision, and every acceptance writes `branch_heads` unconditionally — so six beats planned
against one import revision produce six *sibling* revisions, each holding one drafted scene
and five empty ones, each overwriting the head. The result is a book with one scene of
prose, six accepted policy decisions, six acceptance events, and no error anywhere. Every
per-scene assertion passes. `test_the_head_lineage_is_linear_and_carries_every_scene` is the
only thing that catches it, which is why it asserts a lineage length rather than a scene
count.

Drain-first *usually* achieves the invariant on its own, since a queued job is claimed
before planning happens — but not when that job is leased by another holder, and an
incidental guarantee is one that breaks quietly. `store.any_unfinished` makes it explicit.

**A blocked beat is skipped, not waited on** (§4.1: "a blocked or parked item never stalls
the queue"). There is no predecessor rule: if beat 3 is content-locked, beats 4-6 still
draft and the book finishes with a visible hole. Sequential ordering would be easier to
reason about and would let one bad scene stop a book.

## 22. Job ids carry a plan epoch

`beat_job_id`. Derived from `(book, branch, logical_id, template_id, epoch)` — so a replayed
tick converges instead of re-enqueueing, matching how revisions, decisions and events are
already keyed.

Two exclusions and one inclusion, all deliberate. The **prompt** is excluded: editing the
template must not mint a second job for work already accepted. The **base revision** is
excluded: it moves on every acceptance, so including it would mint a fresh job after every
scene. The **epoch** is included because `jobs.idempotency_key` is UNIQUE, so a poisoned
beat's id is spent permanently — without a version, "try scene 3 again after I unlocked it"
would be inexpressible and the operator's only recourse would be a new database.

## 23. A book that cannot be planned reports why, rather than looking finished

`plan_progress`. A book with no premise and a book that is complete both produce
`TickOutcome.NO_WORK`, and telling them apart is the whole difference between a green board
and a true one. `BookProgress.blocked_reason` carries the sentence; `complete` is false
whenever it is set.

The premise is required rather than defaulted for the same reason: a planner that
substituted a placeholder would draft a book against a premise nobody wrote, and the
failure mode — six scenes of plausible prose about nothing — is one no gate in this system
can detect.
