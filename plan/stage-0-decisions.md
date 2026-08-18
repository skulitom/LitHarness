# Stage 0 decisions

**Status:** Stages 0-2 met against their §17 exit clauses — **787 passing tests (+8 opt-in live, 2026-08-17 — PLAN.md's header and §7 carry the same number; the suite referees any disagreement), ruff clean, mypy
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
dressed as success, and the whole audit story rests on that log. That default is still the
default; what changed is that there is now something else to choose — see §30, and note how
long "until a real sink exists" lasted without anyone deciding it should.

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

1. ~~**Directive ingestion**~~ — **capture half built in slice 5b; model interpretation
   subsequently closed for bounded one-directive proposals in §29.** The original reasoning
   ("a directive inbox without the Narrative Planner to interpret it would be a queue nothing
   can read") turned out to argue for half the work, not none of it. At that slice, directives
   were captured, drained at the top of each tick, and left in `RECEIVED` rather than silently
   dropped or guessed. `Directive.interpret` became the seam §28's verbatim lane and §29's
   model-backed lane both use.
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
   `test_the_decision_record_carries_the_provenance_section_2_requires`.
   *(Renamed when contracts 1.1.0 shipped `PolicyDecisionRecord` and the assertion moved off
   the free-form event payload onto the artifact that owns it. This citation kept the old
   name for four slices — the reason `test_every_test_cited_as_evidence_exists` now exists.)*
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

~~**Fixture discovery is a chain, and no link is an absolute path.** The golden books live
under `fixtures/golden/` at the contracts repository root, outside the importable package,
so `importlib.resources` cannot reach them. `LITHARNESS_CONTRACTS_ROOT` first (the variable
LongRangeContext already uses — a second name for one setting is how two checkouts end up
configured differently), then the installed package's own location, then a sibling checkout.
Each candidate is tested for the *manuscript*, not the directory.~~ — **The chain is retired;
see §60.** Its premise stopped being true when contracts 0.2.0 moved the books inside the
package, and the two heuristic links are deleted rather than left unused. The environment
variable survives with a narrower job. What still stands unchanged is the clause it ended
with: PLAN.md §20.2 records a
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

## 24. A refusal reached before the work costs time, never the unit

`application/conductor.py` (`_settle`), `domain/policy.py` (`refused_before_work`).

Decision 12's sibling, and a lesson this project has now paid for twice. `ProviderUnavailable`
is raised before any work is attempted, and charging it against the attempt budget meant a
fifteen-minute outage permanently poisoned every unit it touched; that was found and fixed.
**The budget ceiling is the same refusal at a different layer and survived the fix by three
commits**, because the lesson had been recorded as a patch to one branch rather than as a
rule.

Two things were wrong, and only the second is interesting. `handlers` emits `Outcome.PARK`
when a ceiling refuses a call, and `_settle` mapped PARK straight to POISONED — terminal,
not revivable, idempotency key burned — under a comment asserting that "`decide` returns
this only on attempt exhaustion". That premise was true when it was written and the budget
gate falsified it, so **the defect was a comment that had become false while still being
relied on**. A daily ceiling resets at midnight; the unit it killed did not, and could not
even be resubmitted.

The fix is to stop inferring a job-layer state from a decision-layer word. POISONED is a
fact about the attempt budget, so `_settle` reads it off the attempt budget:
`attempts >= max_attempts` poisons, anything else parks revivably. `decide` returns PARK
only at exhaustion, so every pre-existing path settles exactly as before. And a decision
whose only failing blocking gate is a budget gate gives back the attempt that
`transition_to(RUNNING)` charged — `PolicyDecision.refused_before_work`, deliberately keyed
on `GateKind.BUDGET` rather than on "any gate that ran early", so a future pre-flight gate
must opt in by name instead of inheriting the exemption silently.

**The test asserted the defect.** `test_an_exhausted_budget_refuses_before_the_provider_is_called`
ended `assert store.load_job("draft-1").status is JobStatus.POISONED`. A suite that encodes
a bug is worse than no suite, because it converts the bug into a requirement and makes the
fix look like a regression.

## 25. Attribution is minted by the operation, and checkable across all of them

`adapters/sqlite_store.py` (`revert`, `unattributed_revisions`), `cli verify`.

§19's Integrity clause is one sentence — every mutation is attributable to a recorded policy
decision *and reversible* — and the reversibility feature shipped violating the attribution
half of its own clause. `revert` took `events` defaulting to `()`, wrote no
`PolicyDecision`, and `cmd_revert` supplied neither, so a revert committed a revision, moved
`branch_heads`, and left `decision_for_revision` answering `None`. §17 Stage 1 lists "zero
silent mutation" as an exit criterion; this was the one, and the four tests covering revert
asserted its content and its lineage and never its attribution.

**Minted by the operation rather than asked of the caller.** Nothing about a revert's
decision is a policy judgment — outcome, base, result and reason are all determined by the
arguments — so leaving it to the caller only created something to forget. `revert` gained
`project_id` (an event needs a project) and writes both the decision and the
`ManuscriptRevisionAccepted` event itself, decision first, matching the draft handler and
the importer: a crash between them leaves a decision pointing at a revision that does not
exist, which is detectable and harmless, where the other order leaves a revision no decision
explains, which is the thing being prevented.

**And checked, not just fixed.** `unattributed_revisions()` asks the question directly —
which revisions does no decision explain — and `litharness verify` reports them and exits
non-zero. This is the half worth more than the fix: a structural constraint on `revert`
guards `revert`, while the query guards every path that commits a revision, including ones
not written yet. `commit_revision` stays usable unattributed because test setup legitimately
needs it; the guarantee lives where it can be *observed* rather than where it can be
enforced against one caller.

## 26. A craft refusal parks; and what the promotion bar was not checking

Two defects in one area, both found by reading the promotion path as an *operator* rather
than as a type. Neither was reachable while no calibration existed, which is exactly why
both survived: the bar had held perfectly for the uninteresting reason that nothing had ever
come through the door.

**The gate could not refuse a scene — it could only interrupt a human.** `promoted_gate`
built a blocking `GateKind.CRAFT` outcome with `vetoes=()`, and `decide` maps a failed
blocking gate carrying no veto to `ESCALATE` with the reason "a blocking gate failed without
naming a veto". None of `Veto`'s members was craft-shaped, so it could not be classified
`RETRYABLE` or `REGENERABLE` either. The consequence is not subtle: a gate firing on 5% of
scenes is one director interruption per twenty accepted, in a system whose entire product
claim is that it runs without one. The first calibration anyone recorded would have
converted §10.4's promotion into an escalation storm.

**`CRAFT_BELOW_BAR` is `PARKABLE`, and the alternatives were the argument.** `RETRYABLE`
was the tempting classification and is the dangerous one: another attempt against the same
context packet produces different text measured by the same metric, so the accepted
candidate is by construction the one that beat it. At `max_attempts` that is best-of-three
optimisation against a craft proxy — a weaker form of the coupling
[plan/craft-corpus.md](craft-corpus.md) §4.2 calls non-negotiable to prevent, but the same
shape, and it would have arrived as a *side effect of a retry class* rather than as a
decision anyone took. Escalation keeps the Goodhart channel shut and breaks the autonomy
claim instead. Parking keeps both: the refusal stands, the book continues because findings
are node-scoped, and the unit is revivable so a dismissal is the way past it — the same
shape §24 already gave a standing finding. A craft park also files **no** exception, which
is the half of the choice that lives in the Conductor rather than in the ladder: §4.2
reserves escalation for what policy could not resolve, and filing one anyway would have put
every refusal in the queue a human is asked to clear — the interruption `PARKABLE` was
chosen over `ESCALATE` to avoid, arriving one layer below the choice.

**The best argument for parking is the one that turned out not to hold yet.** This entry
first claimed that every parked unit is both a refused scene *and* an unjudged sample, so
§10.5's audit queue would accumulate from the gate's own operation. It does not. `handlers`
records craft metrics and draws the audit sample inside the acceptance branch, after
`commit_revision`; a refused candidate commits no revision, so it produces neither and its
text is discarded. Recorded as a gap rather than closed in passing, because `AuditSample` is
keyed `sha256(revision_id, logical_id)` and a refused candidate has no revision id — giving
one to text that was never accepted changes what `verdicts_digest` content-addresses, which
is the thing every promotion is measured against.

**And the premise about attempt exhaustion broke for the third time.** `Conductor._settle`
derives POISONED from `attempts >= max_attempts` alone. It once asserted "`decide` returns
PARK only on attempt exhaustion"; the budget gate falsified that and the fix narrowed the
premise to "PARK at the ceiling means exhaustion", which held only while every parkable
refusal happened to arrive at the ceiling. `PARKABLE` ends that — a craft gate refuses at
any attempt number, deliberately, since the check sits ahead of the budget. A refusal
landing on attempt 3 was therefore indistinguishable from a spent budget and poisoned the
unit: unrevivable, absent from `jobs --status parked`, its derived job id burnt, and its
exception reading "attempt budget spent" about a budget that was not what stopped it. That
made this entry's own revivability claim false in exactly the case a director would hit
after two bad drafts. `PolicyDecision.parked_by_veto` now says which it was, because the
count has been wrong about this twice and a comment asserting the count is enough has been
wrong about it three times. The tests that pin it drive real ticks to the ceiling and fail
against the pre-fix expression.

**The precision floor was measuring the wrong denominator.** `MIN_PRECISION = 0.80` on
`MIN_HOLDOUT = 50` reads as a strong bar and is not one, because precision is computed over
the *flagged* set and `holdout_size` does not bound it. A metric that flags one scene in
fifty and happens to be right scores precision 1.00 on a holdout of 50 and clears both
floors having demonstrated nothing. `recall` would have exposed it and is `None`-able, so it
could not be what catches this. `flagged` is now recorded (migration 015) and floored at
`MIN_FLAGGED = 17` — the smallest flagged set whose two-sided 95% Clopper-Pearson lower
bound on a *perfect* score clears 0.80 (0.025**(1/17) = 0.805, against 0.794 at 16). The
floor is derived rather than placed, unlike the two constants above it: it is what
`MIN_PRECISION` already implied, made a precondition instead of an assumption. An
unrecorded count is refused rather than assumed, because `None` is indistinguishable from
one flag, and 015 left the column nullable rather than backfilling for the same reason.

**Wiring the path on is not turning a gate on, and the early return is what makes that
true.** `_promoted_craft_gates` reads `store.calibrations()` and returns `()` when the table
is empty — one indexed query, no branch that can construct a gate. `NotPromotable` is
swallowed per metric rather than raised, so expired or stale evidence falls back to the
annotation `craft_gates` already produced; raising would turn "the evidence about prose
quality went stale" into "this scene cannot be drafted at all", which is §10.5 re-opening
calibration by stopping the book.

**A defect the tests could not have found, and the end-to-end run did.** `calibration_id_for`
derived identity from metric, threshold and verdict digest alone, on the reading that a
re-measurement moves the digest. It does not have to — re-measuring the same metric at the
same threshold over the same holdout is precisely what a *correction* is. The two rows
collided, `record_calibration` is `INSERT OR IGNORE`, and the correction was dropped while
the superseded row kept gating; worse, `calibrate` printed the promotability of the record
it had *built*, so the operator was told BLOCKING-ELIGIBLE about a gate that did not exist.
The measured numbers are now part of the id, and the command re-reads and reports the row
that is on record. The general lesson is the one §25 reached from the other side: a content
address must cover everything that makes two things different, and a write path must report
what the store holds rather than what the caller offered.

**One gate per metric, and a fallback that is never silent.** The ladder first appended the
promoted gate *beside* the annotation `craft_gates` had already built, so a refused scene's
decision carried the same `rule_or_critic_id` twice — `passed=True, blocking=False` and
`passed=False, blocking=True` — and `decision_id_for` hashed both. An audit asking what the
craft ladder said about one measurement got two contradictory answers. `_craft_ladder` now
builds the annotations first and *replaces* the entry for any metric that earned a blocking
gate. When a calibration exists but cannot promote, the annotation stays and the reason is
written into its `detail`: expired or stale evidence degrading to advisory is exactly §10.5's
re-opened calibration and must not fail the job, but a gate that quietly stops blocking is
the failure `promoted_gate`'s own docstring refuses by name, and until this the decision
record could not distinguish "the calibration went stale" from "no calibration exists".

**The property to know before the first promotion.** `verdicts_digest` is computed over
*every* answered audit sample, so a single new `litharness judge` verdict changes the digest
and re-opens **every** recorded calibration at once — each one becomes `stale_evidence` and
each promoted gate falls back to annotation on the next draft. That is correct under §10.5
and it is not obvious from any one function: the sampler, the digest and the promotion bar
each behave reasonably alone. It means a promotion is not a state the system settles into
but one it re-earns whenever the evidence base moves, and it is why the fallback had to
become legible before anyone records a calibration rather than after.

## 27. §12 step 5: extraction mints nothing

The last unbuilt item in §17 Stage 1's own text, and the one that made Stage 1's only
in-process detector inert. `state.contradiction.v0` names the corruption it exists to catch —
"§12 step 5's extraction writing a record that contradicts one already accepted" — and that
write did not happen: `record_state_records` had one caller, `cli import`;
`EventType.STATE_CANDIDATES_EXTRACTED` had no producer; **nothing in `src/` constructed a
`StateRecord` at all.** So the detector's zero findings on both fixtures read as a clean
negative control and were also the sound of a check with nothing to check. Stage 2's premise —
"repairs triggered by findings, verified by re-detection" — had no in-process trigger.

**The order key is read back out of the book, not computed, and that is the whole design.**
`domain/state.py` forbids deriving one and gives the reason: `order_key` is opaque, its author
chose it, and nothing anywhere maps a manuscript scene to one. `attested_position` therefore
asks the book — a canon record whose evidence cites this scene is the book's own statement
about where the scene sits in story time — and abstains when the answer is absent or
ambiguous. Measured on the two fixtures: litrpg `scene-1..6 → s1..s6`; mystery `scene-1→s1`,
`scene-2→` ambiguous (records at both s1 and s2), `scene-3→s3`, `scene-4→s4`, **`scene-5→s1`**
— the analepsis honoured rather than overridden — `scene-6→` unattested.
*Alternative:* `f"s{ordinal}"`, which is one line and reproduces litrpg 19/19. It mis-slices
the mystery, whose genre guarantees it, and the failure is invisible: a false MAJOR on a
conforming book, or a missed contradiction. A scheme that is right on your test book and
silently wrong on the next is worse than abstention. `None` means *do not extract*, never
"extract unplaced" — the detector groups on `order_key or ""`, so unplaced records share one
bucket, which is the coarsest collision scheme wearing the costume of caution.

**A deterministic extractor may write canon; a model's may not.** The chain is decision →
prose → record: a policy decision accepted the prose and this is a mechanical restatement of
it, asserting nothing the decision did not. That is why `ACCEPTED_CANON` here does not violate
§11's rule that no proposal becomes canon merely because a model returned it — no model
returned it. *Alternative:* write `PROPOSED` for safety. Measured, it is pure ceremony:
`detect_contradictions` takes only canon and `context.assemble` skips non-canon, so the
records would be invisible to both and Stage 2 would still have nothing to trigger on. The
model leg is deliberately unbuilt and its precondition is a promotion decision nobody has
taken, not effort.

**Extraction runs before the gate, not after acceptance.** The facts a candidate asserts are
judged against established canon while refusing is still free: the node stays empty, no
revision commits, no record is written, and the finding drives the ladder. Extracting after
acceptance would commit the prose *and* the contradicting record and then report the problem.
Verified end to end: a candidate whose system voice contradicts canon at s1 fails on attempt
one, and the *next* tick meets the finding already standing and parks pre-flight for no
attempt and no tokens — §19.1's two-place split, exercised by a defect the system produced
itself rather than one an operator ingested.

**`commit_revision` grew a parameter rather than the handler growing a second write.** §15's
carve-out is used, not widened, and §12 step 8's "atomically" is delivered literally: the
revision, its acceptance event, `StateCandidatesExtracted` and the rows are one transaction.
*Alternative:* a separate `record_state_records` call — before the commit it writes canon for
prose nobody has, unrecallable under `INSERT OR IGNORE`; after it, `handlers` returns early
when a prior ACCEPT decision exists, so a replay writes nothing and reports success. Records
inherit the revision's crash semantics exactly: **they cannot exist for a revision that does
not.**

**`record_id` is content-derived and value-sensitive.** *Alternative:* key on
`(subject, predicate, order_key)`, which looks like the tidier identity and makes the detector
permanently unreachable — `INSERT OR IGNORE` means a contradicting record collides with the
one it contradicts, inserts zero rows, leaves the old value standing, and reports success.

**Extraction suppresses a record identical to canon at the same position**, so a redraft that
establishes nothing new writes nothing. Measured: a clean six-scene litrpg run writes zero
rows. *Alternative:* write anyway, and every redraft costs a permanent duplicate in every
later context packet against §7's token budget.

**Revert retracts the records the discarded prose produced** (migration 016), forward-only and
in the head-move transaction. *Alternative:* leave them. Then revert-then-redraft contradicts
an orphan, and **no operator action clears it**: the detector runs in-process on every attempt
and mints its finding `OPEN` each time, while `dismiss` satisfies only the pre-flight standing
gate. That converts §19.1's free revivable park into a paid unclearable one, through a door
§19.1 did not know existed. *Also rejected:* detecting orphans by head lineage — `reverting_to`
parents on the current head, so the discarded revisions stay ancestors and the check returns
empty exactly when the failure has occurred. The discarded segment is therefore computed
*before* the head moves.

**What it deliberately does not do.** No model call, no provider change, no `state_candidates`
table, no CLI verb to accept or reject a candidate, no prose-semantic extraction, and no
change to `render_prompt` asking generators to emit system voice. The consequence, stated so a
green Stage 1 is not read as more than it is: **until that prompt change lands, extraction
yields records only for prose that already carries system voice.** It must land as its own
change — it moves every litrpg content hash and revision id, and riding along here would make
it impossible to tell which half moved the fixtures.

## 28. Explicit direction needs no model interpretation, and outranks queued prose

The immutable plan-proposal seam made a useful distinction available that "directives are
captured, not read" had hidden. Arc, tone, chapter, and premise notes require a Narrative
Planner to decide what plan edits they imply. A director-labelled `constraint` or `veto`
already is the decision. Paraphrasing it with a model adds a failure mode; leaving it unread
lets the system draft against direction it could have obeyed exactly.

The deterministic lane puts one locked `PlanKind.CONSTRAINT` through the existing content-
addressed `PlanProposal` transaction. Constraint text stays exact. Because `PlanItem` has no
veto kind, a veto keeps its original words under the mechanical label "The director vetoes"
rather than silently becoming a positive instruction. The rendered text is also the recorded
directive reading; the original body is never rewritten. Replay after a crash sees the
directive already `APPLIED` and succeeds without a second plan revision.

**Scope is resolved, never guessed.** `--book` and `--branch` can pin it at submission. An
unscoped explicit directive is actionable only when exactly one stored branch matches. The
resolved destination lives on the job payload rather than mutating the submitted directive;
the audit record therefore continues to distinguish "the director scoped this" from "the
selector had one unambiguous destination". With multiple matching branches it remains
`RECEIVED` and visible.

**Ordering is the value of the lane.** Ingest still runs first. Selection materialises the
verbatim unit at priority `1000 + directive.precedence` before claiming existing work, so a
constraint received before the tick cannot sit behind an already-queued scene and affect
only the scene after it. Interpretive directive kinds now enter the lower-priority bounded
model lane recorded in §29. Controls stay in `RECEIVED`; they are not converted into global
story constraints merely because doing so would make the unread count smaller.

## 29. Model interpretation is a proposal, never a plan write

Premise, arc, tone, and chapter notes need interpretation, so the deterministic transform in
§28 cannot honestly consume them. The first Narrative Planner producer is intentionally one
directive and one frozen plan at a time. It requests strict structured output with a maximum
of 12 edits and then reconstructs domain `PlanEdit` objects itself. Locked items, the
single-premise invariant, `canonical_in_prose`, duplicate edits, no-ops, and explicit
`target_logical_ids` are enforced after the call; the provider cannot waive them.

**Acceptance is one transaction.** The accepted policy decision, its event, the directive
reading, the new content-addressed plan revision, and `PlanChanged` land together. The head is
rechecked under the write lock because the model call is a long gap; a concurrent change
records a stale-base refusal instead of overwriting newer direction. Provider usage is
recorded on invalid output too, so a malformed proposal is not free in budget accounting.
Budget refusal remains pre-flight, revivable, and costs neither an attempt nor a call.

**Plan changes invalidate prose prompts.** Scene jobs freeze rendered context at enqueue
time. Accepting a new plan therefore advances the branch's plan epoch and cancels queued
scene jobs for that branch in the same transaction. The selector mints the replacement from
the new plan. Without this, “direction outranks queued prose” would change the plan while the
already-rendered old prompt drafted anyway.

**What this does not claim.** There is no whole-book plan generation, foreshadow/payoff
ledger, progression schedule, beat-template replacement, or structural/mechanical/craft
critic for plan quality. Those remain §9 and §20.6 work; this slice establishes the safe
provider-to-proposal lane they can reuse.

## 30. The outbox drains somewhere, and the default still drains nowhere

The transactional outbox was built in slice 2 and was correct and unreachable for nine
slices. Send-then-mark, content-derived idempotency keys, capped exponential backoff, a
FAILED terminal state, and a spin fix measured over 2,016 ticks — all of it draining into
`_null_dispatcher`, which returns False for every entry, and which no caller ever replaced
because no caller ever passed `dispatch=` at all. Every `EvaluationCompleted`,
`FindingStatusChanged`, `PlanChanged` and acceptance the system had written sat pending
forever, and the `dispatched=` count `tick` prints was **structurally** zero rather than
usually zero.

**This is the `reset_health` shape for the fourth time**, and the file already records three:
a documented promise with no non-test caller (`ProviderRegistry.reset_health`,
`bump_plan_epoch`/`replan`, and — still open — `rollback_proposal`). It is the most reliable
defect this project produces, and the reason it survives review is that every part of it
tests green: the outbox's own suite passes because it asserts the *machinery*, and §9's
"default refuses delivery" test asserts the default is honest, which it is. Nothing asserted
that anything was ever a non-default.

**JSON Lines to an operator-named file, because it is the smallest thing that is genuinely a
sink.** Append-only, so it is shaped like the log it carries; no network, no credentials and
no dependency added to a repo whose only runtime dependency is its own contracts package;
and `tail -f` is a working consumer on both supported platforms. Anything richer — webhook,
mail, a queue — is another adapter behind the same `Dispatcher` protocol and does not touch
the loop.

Four properties are what separate a sink from the appearance of one:

- **One line is exactly one `EventEnvelope`** (§13's shared contract, not a shape invented at
  the boundary), so a consumer reads it with `lc.parse_artifact`. Delivery bookkeeping is
  deliberately absent: attempt counts are this system's business, and mixing them in would
  make the line something no schema describes.
- **Flushed and fsynced before delivery is claimed.** Send-then-mark is at-least-once only if
  the send is durable before the mark. The store commits with `synchronous=FULL`; a buffered
  line still in the OS cache at power loss would be marked sent and gone — the silent loss
  the null dispatcher was written to avoid, arriving through the sink instead of the default.
- **A failed write refuses; it does not raise.** `_drain_outbox` runs *before* work selection,
  so an exception there would abort the tick before a scene was drafted: a mistyped
  `--notify-file` would stop the book. Refusing leaves the entry pending, backs it off, and
  lets the tick work. The refusal is counted and its reason surfaced on stderr by `tick`, but
  it does **not** change the exit code — the tick did its work, and paging a supervisor every
  five minutes for a condition the backoff is already handling inverts §4.1's "a quiet system
  is a healthy one".
- **The default is unchanged.** No `--notify-file` means `null_dispatcher` and a visibly
  undelivered outbox. Defaulting to some file would be worse than the old silence: events
  marked sent into a path nobody agreed to read.

`_null_dispatcher` was renamed `null_dispatcher` in the same change, which is the smaller
half of the same point. With two dispatchers the choice belongs to the composition root, and
a composition root that cannot name the default it is choosing expresses "no sink" by
omitting an argument — which is exactly how this stayed the only dispatcher for nine slices
without anyone deciding that it should.

## 31. A plan is reversible from the operator surface, or it is not reversible

§19's Integrity clause says every mutation is "attributable to a recorded policy decision and
reversible". That held for prose — `revert` restores an earlier manuscript revision as a
forward child — and did not hold for the plans that produce the prose.
`domain/plan_refinement.rollback_proposal` was implemented, tested, and documented with the
rule it enforces ("rollback goes forward"), and nothing in `src/` called it. The `reset_health`
shape again, and this one sat behind a clause the project reports itself as *met* on.

`litharness plans` and `litharness revert-plan` close it, and the read verb is not optional
decoration: an operator cannot restore a revision they cannot see, and a lineage printed as
bare content hashes would not tell them which one to pick. So each revision prints with the
summary of the proposal that produced it, the directive it came from, and whether it was
itself a rollback. A revision with no proposal is the plan the book was imported with, which
is stated rather than left as a blank line — it is also the only case where there is nothing
behind the head to restore, and `revert-plan` says so instead of raising about a baseline the
operator never chose.

**One query per branch, not one per revision.** `plan_proposals(book_id, branch_id)` reads the
whole branch on the index migration 017 already created; the obvious
`plan_proposal_for_revision` would have been a scan per revision over an unindexed column, and
the lineage of a long-lived book is as long as its direction. Conflicted proposals come back
too: a proposal that never applied is direction the system decided not to act on, and it
carries the stale-base error explaining why.

**Two things the command reports because it would otherwise be discovered later.** A rollback
is the *one* proposal permitted to move a locked item — that permission is what lets it undo a
director's constraint — so the count of locked items it moved is printed rather than silent.
And a constraint minted from a directive can be rolled back out from under it: the directive
stays `APPLIED`, still citing a plan item that no longer exists. That is recoverable, since
the direction is on record and can be resubmitted, but only if the operator is told at the
moment it happens rather than finding out when the book drafts without a constraint they
believed was in force. It exits non-zero when that happens.

**It touches no prose, and that is the division of labour.** Accepting the restored plan
advances the branch's plan epoch and cancels queued scene jobs in the same transaction
(§29's rule, unchanged), so the next tick plans still-draftable beats against the restored
plan. Scenes already accepted under the old plan stay accepted; `revert` is the verb for
those. Nothing here overrules a gate, exactly as `replan` does not.

## 32. Propagation reasons about evidence, not about position

`domain/propagation.py`. §17 Stage 2's second exit item had a complete measuring instrument
and no subject: `domain/impact.py` scores a blast-radius prediction against the gold suites
and ships three baselines for it to beat, and nothing in `src/` produced a prediction. The
engine is four rules, and each reads a different kind of evidence because the obvious signal
is refuted — `predict_downstream_scenes` ("everything after the edit") scores precision 0.333
against `predict_everything`'s 0.481, buying *worse* precision while giving up most of the
recall, and `tests/test_impact.py` refuted it before any of this was built.

- **`entity_renamed` reaches wherever the name is spelled**, forwards and backwards, on a word
  boundary, minus the aliases the change set preserves. A name is not carried forward; it is
  written, and every place it is written is wrong the moment it changes. Word boundaries are
  the whole of the rule's precision — without them "Vane" reaches "Vanessa" and a short name
  reaches the book.
- **`fact_changed` reaches forward only**, to nodes carrying both the subject and the
  predicate, and to records asserting that predicate of that subject from the change's story
  position on. The anchor is the predicate, not the value: a downstream balance is wrong
  without repeating the number that changed.
- **`event_moved` reaches the window strictly between the two edited nodes**, plus the records
  at the origin sharing the moved event's subject — knowledge acquired at the event travels
  with it. Written as a window rather than "everything after the origin" because a move can
  run backwards and the window is the same either way.
- **`surface_only` reaches nothing**, and is not a veto over the rest of the set: it says
  *this* change carries no meaning, and treating it as set-wide would let one reformatted
  sentence hide a rename beside it.

**Node space and record space are never mixed, and this is the decision most likely to be
undone by someone who has not read §27.** Manuscript order is `position_key`; story order is
`StoryPosition.order_key`; **nothing anywhere defines a mapping between them**. The mystery
fixture is the proof — `attested_position` abstains on two of its six scenes and reports a
third at `s1` — so node rules compare `position_key` against the edited nodes, record rules
compare `order_key` against other records, and the single place they must meet goes through
`attested_position`, widening the record filter where the book has not said and writing the
widening onto the target's reason.

**Two treatments of text, deliberately.** Prose is searched on word boundaries; a record's
value is split on non-alphanumerics first, because its keys are identifiers and `_` is a word
character to `` — a boundary search for "gold" does not match `cost_gold`, which is exactly
how `rec-ev-buy-lantern` states the lantern's price. A unit test caught that before the gold
suite did.

**Everything else abstains and says so.** `event_added`, `event_removed`, `plan_changed`,
`pov_changed`, `rule_changed` and `unknown` have no rule; they return in `unhandled`, leave
`complete` false, and make `litharness propagate` exit non-zero. An engine that guesses at a
change it cannot read rewrites conforming prose, and an empty result that does not distinguish
*analysed and clear* from *skipped* is the same silence `ingest` was corrected for.

**The score is 1.000/1.000 and that is not the claim.** Thirteen hits, zero misses, zero false
touches over four cases and 37 in-sample expectations, with the rules written after reading
them. It beats both baselines, which is what the exit item asks; it does not generalise, which
is what the third exit item says out loud and what `impact.CAVEAT` prints under every result.
`tests/test_propagation.py` is the other half — each rule against a book built for it, plus
the cases the gold has none of: an alias containing the old name, a fact appearing only before
the change, a move running backwards, a move with no window, and a change kind no rule reads.

## 33. The producer this repo can honestly build is the diff extraction already computes

§32 built the rules and left the producer outside: the engine was reachable only by an
operator handing it a `ChangeSet` file. That left a defect in the autonomous path that no gate
could see. `make_evaluation_handler` evaluates exactly the one `logical_id` on its job, and the
only evaluation a repair schedules is the verification of the node it repaired — so correcting
the lantern's price in scene 2 left scenes 3 to 6 carrying the old balance, with every gate
green and the finding marked fixed. Detect-then-repair without propagation is
detect-then-repair-then-lie, and Stage 2's first exit item passes either way.

**The producer was already sitting in the handler.** An accepted repair runs `extract_state`
over its result and commits the records while retracting the node's old ones. The difference
between those two sets *is* the semantic change, read rather than inferred, so
`changes_between` mints nothing and is §27's rule applied one layer up.

Three decisions inside it, each of which is wrong in an obvious way first:

- **Matched on `(subject, predicate, order_key)`.** A running balance differs at every position
  by design. Matching on `(subject, predicate)` alone would compare `rook/gold` at s3 against
  s2 and report the book working as a contradiction — then propagate from it, on every repair.
- **A mapping value is diffed to the changed field.** The record is one `status_snapshot`, and
  no book contains that word, so a change reported under it reaches records and never a scene.
  `gold` is both the changed field and the token the prose carries. Diffing to the field is
  what makes the produced change the same shape as the hand-authored gold suite.
- **A newly stated fact is not a change.** It invalidates no earlier prose, and a candidate
  contradicting standing canon is refused by the integrity gate before it can commit, so
  treating "new" as "changed" would propagate from every first draft of every scene.

**Bounded twice, because §4.2's failure mode is a parked unit and never a spin loop.** A
propagated evaluation costs a `repair_depth` level, so repair→propagate→repair→propagate
terminates at `MAX_AUTO_REPAIRS` hops; at the last depth it queues nothing rather than minting
jobs the evaluation handler would refuse for an out-of-range depth. And the fan-out per
acceptance is capped, because one repair must not be able to queue a re-check of every scene in
a novel. The `ImpactAnalyzed` event records the **reached** set beside the **enqueued** set,
because they differ exactly when a cap bit and a silent truncation reads as full coverage.

**The control is the test that keeps this affordable.** Most repairs change no fact at all, and
an engine firing on every acceptance would multiply the cost of every repair by the length of
the book. A repair that rewords a sentence queues its own verification and nothing else, and
writes no analysis event.

**What it still does not read.** `fact_changed` only. Renames and moved events have no in-repo
producer, and neither is derivable from an extraction diff — they are reached through
`litharness propagate` over a `ChangeSet`, which is §13's boundary. The extractor's own ceiling
is the producer's: a fact it cannot read is a change nothing can report.

## 34. Ask for the line the parser accepts, and only where the book already speaks it

§12 step 5 reads the `[STATUS]` line and nothing ever asked a generator to write one. So every
record in the system came from an imported snapshot, `state.contradiction.v0` could only fire
on prose somebody else wrote, and — since §33 — the propagation producer had no fact of the
system's own to compare. `render_prompt` now carries the instruction.

**The gain is the gate, not the extraction, and conflating the two would overclaim.** A
generated litrpg scene carried no game state, so the integrity gate had nothing to read and
passed it *vacuously*: a scene stating forty gold where canon says forty-five was accepted,
because it never said so on the page. Measured through the loop — a generator writing the
contradicting line parks the beat with `state.contradiction.v0`, and one carrying the
established numbers forward is accepted. What did **not** change: a redraft agreeing with canon
still extracts nothing (`_already_canon`), and a book with no imported snapshot still extracts
nothing at all, because `attested_position` has no evidence to place the scene by. Book Zero
will write system voice that nothing can yet position.

**The instruction is the extractor's own template**, `STATUS_TEMPLATE`, with a round-trip test
that fills it in and parses it back — first with `STATUS_PATTERN`, then through `extract_state`
itself. The failure this rules out is silent in the worst way: a prompt asking for a form the
parser does not accept produces prose a human reads as correct and an extractor reads as
nothing, and a scene whose state nobody could read is indistinguishable from a scene that
established none. No gate catches that, so a test holds the two statements together instead of
care.

**It is off unless the book already speaks system voice**, read from canon by
`speaks_system_voice` rather than declared by a genre flag — the reason `attested_position`
reads the order key rather than deriving it. A flag is a second source of truth for something
the records already answer, and the two eventually disagree. Canon only: a *proposed* status
record must not change how every later scene is written. The mystery fixture holds no status
snapshot, so its prompts are unchanged and its prose stays free of stat blocks — a LitRPG
status block in a locked-room mystery is not a smaller error than a missing one.

**And the values, not just the shape.** A model asked for a status line with no numbers in view
invents them, and an invented balance is a contradiction the gate then refuses and the repair
loop then pays for. The established facts are already in the packet above the instruction; the
instruction says to carry them forward unless the scene changes them.

## 35. Propagation routes re-checks; it does not decide anything is wrong

§33 said the loop closes, and the sentence needs the limit stated beside it or it reads as
"the ledger now repairs itself". Walked end to end — repair, propagate, then *run* the four
propagated evaluations — all four complete and report nothing. Correct, and not a fix:
`state.contradiction.v0` checks disagreement **at one position**, and scene 3 stating fifteen
gold agrees perfectly with the record that says fifteen gold. What is wrong is the arithmetic
*across* positions, and §8.4 gives that vocabulary to ContinuityEvaluation, whose pack is
optional.

So: **propagation routes re-checks to whatever detectors are configured, and whether anything
is found is a fact about detector coverage rather than about the book.** With the CE pack
configured the ledger rules see all four scenes; without it the re-checks are real work that
finds nothing. The work is not wasted — it is the difference between four scenes nobody looked
at and four scenes the configured detectors have now cleared — but it is not a repair.

**The engine deliberately does not fill the gap by minting a finding of its own.** It knows
scene 3 was *reached*. It does not know scene 3 is *wrong*: that it says fifteen *because of*
the number that changed is an inference, and the detector that could settle it belongs to a
sibling. Asserting staleness would be guessing in the register §27 refuses, and a blocking
finding nothing can clear would be §19.1's "a gate is not finished when it refuses correctly"
arriving one more time.

## 36. Severity finally reaches the queue

§4.1 asks for "findings to repair (severity-ordered)" by name. Severity reached the *findings*
store — indexed, sorted in `litharness findings` — and stopped there: `repair_job_for` minted
every repair at one constant priority, so a critical complaint waited behind a minor one that
happened to be enqueued first. `priority = REPAIR_PRIORITY + severity.rank` closes it.

Severity rides **on top of** the band rather than replacing it, so a repair still outranks
every evaluation and the ladder's two stages cannot interleave. And it is derived from the
finding rather than stored on the job payload, so a severity corrected after the job was minted
does not leave two answers on record.

This is the last of `jobs.priority`'s unused halves — the column PLAN.md §20.4 recorded as
inert, which had four bands using it by the time that text was corrected, and now has the
ordering the plan asked for by name.

## 37. The template may state its own chronology; the extractor still derives nothing

§27 forbids deriving a story position from a scene, and measured the refutation: an
ordinal-derived key reproduces the litrpg fixture 19/19 and mis-slices the mystery, whose
scene 5 is an analepsis attested at `s1`. That stands. What §35 got wrong was the conclusion
drawn from it — that a book this system authored is therefore unplaceable until the Narrative
Planner exists, making Book Zero's extraction a design item rather than an engineering one.

**The refutation is about *deriving* an order for an arbitrary book. It is not about a template
*stating* that the story it lays out runs forwards.** `SIX_BEAT` is setup, inciting, rising,
turn, crisis, resolution — a chronological progression with no flashback beat in it, so a book
planned from it cannot contain one, because there is no beat to hold it. That is a fact about
the sheet, known by the sheet, and `BeatTemplate.chronological` is where it now lives.

The flag defaults to **False**. A future template that forgets it loses extraction coverage on
the books it plans; one that wrongly claimed True would mint a story order nothing downstream
could detect as wrong, because the system would be checking its own invention. Forgetting must
cost coverage, never correctness.

Three guards keep the opening narrow:

- **The book always wins.** `attested_position` is read first; a stated position only fills
  silence. It can never override or reorder an author's answer.
- **A book with somebody else's vocabulary is refused outright.** One canon record carrying an
  order key this extractor did not write is enough. The mystery's scene 2 abstains while records
  at `s1` and `s2` exist, and filling that gap would insert a record into the middle of a
  numbering another author owns — worse than abstaining, and exactly what §27 refuses.
- **Provenance is on the record.** Every placed-by-plan record carries a `note` saying so,
  because "the book said where this sits" and "the sheet we planned said so" are different
  claims, and an audit that could not separate them would be worth less than one that said
  nothing.

**The defect this shipped with, and how it was found.** The vocabulary guard first counted any
canon record with an order key — including the ones this extractor had just written. Scene 1
was placed; its record then made the book look like it had a vocabulary; every later scene
abstained. A six-scene Book Zero extracted exactly one fact and looked, at every layer, like a
book whose other five scenes established nothing. Unit tests could not see it, because they
place one scene. **Running the whole book did.** `REGISTRY_VERSION` already existed to
distinguish this extractor's records from authored ones — the module docstring records that it
is deliberately not the fixtures' `fixture.v1` — so the fix was to ask the question the marker
was made for.

**The seed is the remaining input, and it is authored rather than guessed.** A book with no
status record at all is never asked for system voice (§34), so it writes none and there is
nothing to place. One starting character sheet — the initial condition a LitRPG book has anyway,
carrying no story position because it is true before the book begins — closes the circle.
Measured end to end: a book with no imported snapshot drafts six scenes and reads back all six
balances, `s1` through `s6`, with seven revisions rebuilding cleanly.

## 38. The instruction is the book's own line, because a placeholder is a thing a model copies

§34 shipped the system-voice instruction as `STATUS_TEMPLATE` — the extractor's own form,
`{subject}` and all — on the argument that the prompt and the parser must be the same
statement. The argument was right and the implementation was not, and the difference was only
findable by asking a model.

Measured against three local Ollama models, drafting scene 1 of a seeded Book Zero: two
substituted the character's name, and **one wrote `[STATUS] {subject} — Level 3 | ...` out
verbatim.** That line matches `STATUS_PATTERN` perfectly — a brace-wrapped word is a
perfectly good subject — so nothing rejected it; and `{subject}` is not a name canon knows, so
extraction yielded nothing. A scene that looks right, parses right, and establishes nothing:
precisely the silence §34 was written to prevent, produced by §34's own instruction.

`system_voice_example` replaces it with the book's own current status line, built from canon so
it mints nothing — the subject is the id the records hold, the numbers are already established.
Re-measured: three of three.

**Which line, though, is not a detail.** A model shown a line will use its numbers, so the
wrong line is worse than none. An imported book holds a snapshot at every position at once, and
picking the newest would show scene six's balance while asking for scene one — an invented
state the integrity gate then refuses, a refusal caused by the instruction rather than by the
prose. So the example is the snapshot *at* the position being drafted (`at=beat.story_order_key`),
falling back to the latest one before it, which for a book still being written is the state the
next scene continues from and for a book with nothing placed yet is the starting sheet.

**The transferable part is what could and could not have caught this.** Nothing in the suite
could: every other test runs on `FakeProvider`, which ignores the prompt entirely, so the
instruction's *content* is unobservable to all 662 of them. The round-trip test §34 added is
real and passed the whole time — it proves the parser accepts the template, not that a model
writes one. The check that matters is a live one, and it now exists as an opt-in test against
local Ollama, which costs no quota. **A prompt is not tested by a suite that never sends it.**

## 39. The layer that gates every draft had no way to look at it

Twenty-eight operator verbs, and none answered *what does this book hold as true*. Objective
story state gates every draft — the integrity gate refuses a candidate that contradicts it,
the context packet hands it to the generator as established facts, and §33's propagation
producer reads its changes out of it — and the only way to see any of it was to open the
SQLite file. `litharness state` is that view.

**Story order, because a ledger read out of order is not a ledger.** It is also what makes
this worth having rather than a convenience: §35 records that `state.contradiction.v0` compares
values at a *single* story position and cannot see a balance that stops adding up across them,
so an unconfigured installation routes propagated re-checks to detectors that find nothing.
This is where a human finds it instead — one column, six rows, and the arithmetic either works
or does not. §4.3 calls that directing rather than operating, and directing needs somewhere to
look.

**Provenance on every line**, because imported canon and extracted canon are different claims:
`given` is the author's word, `read` is this system's reading of prose it generated. The note
§37 puts on a plan-placed position prints with the record it is about, so a record resting on
the template's word says so where it is read rather than in a table nobody opens. Measured on
a Book Zero run: six `read` rows with their positions marked as the plan's, and one `given`
starting sheet.

**Unplaced records are counted rather than hidden.** A starting sheet is true before the book
begins and correctly carries no position — but the contradiction detector groups on position,
so an unplaced record is canon nothing is checking. An operator should know how much of that
they have.

The fixture's own notes come along for free, which is a small vindication of `state.describe`
being the one renderer: `f-gold-ledger`'s "the ledger-correct value is 20" prints beside the
record it is about, so §8.3's planted defects are visible to the reader they were planted for.

## 40. The prose is load-bearing, so something had better check it

This repo's comments carry the reasons, the refuted alternatives and their measurements, and
readers act on them — §27 stopped a wrong story-position scheme twice, once by being read and
once by being re-read. Nothing type-checked a word of it, and the record says what that costs:
`jobs.priority` was documented as inert in four places for two stages after it stopped being,
and a claim that the list of uncalled promises was empty survived exactly one commit.

Two checks now run in `tests/test_architecture.py`, chosen because they are the two failures
that actually happened rather than the ones easiest to write:

- **every backtick-quoted symbol in `src/` prose resolves** somewhere in the repo. Contract
  names are skipped — they belong to `litharness_contracts` and its own suite — and plain
  lowercase words are skipped, being emphasis far more often than symbols. `PROSE_ALLOWED`
  exists for a name deliberately absent, and it is empty: this project names refuted
  alternatives constantly, but does so in `plan/`, not in module docstrings.
- **every test cited as evidence exists.** §17 proves Stage 0's exit clauses by naming four
  tests; a citation that no longer resolves is a claim with its evidence quietly removed, and
  it reads exactly like a claim with evidence. Scoped to `src/` and this file — `PLAN.md` and
  the other companions also discuss siblings' suites, which this repo cannot resolve and
  should not pretend to.

**What the audit found is worth recording as much as the fixes**, because the result was
better than the criticism that prompted it. Across `src/`, every symbol named in prose exists
— **zero** stale identifiers. The whole repo yielded two stale claims:

1. `domain/beats.py` opened with "§9's Narrative Planning is a separate pillar that does not
   exist", which stopped being true when `application/narrative_planner.py` shipped §9.3's
   bounded producer. Corrected in place, with the part that *is* still absent named.
2. this file cited a test whose name was
   test_the_accepted_event_carries_the_provenance_a_policy_record_will_need, renamed to
   `test_the_decision_record_carries_the_provenance_section_2_requires` when contracts 1.1.0
   moved the assertion onto `PolicyDecisionRecord`. Four slices stale, and the reason the
   second check exists.

   *(Written without backticks on purpose, and the check is what forced the distinction: a
   dead name is a historical string, not a symbol this repo has. Quoting it as one made the
   guard fail on the very paragraph describing it — which is the right answer, and a small
   demonstration that the rule has teeth.)*

A third came from the same session that wrote the search term for it. `speaks_system_voice`
lost its production caller when the planner switched to `system_voice_example`, which was a
fresh instance of §19.1's defect family, created hours after documenting it. Closed by making
`system_voice_example` guard on the predicate — which reads better anyway, since "no example"
and "does not speak system voice" are the same answer and the code now says so.

**And a limit on the check worth stating.** A sweep for public symbols whose only callers are
tests returns sixteen, and most are correct: `assert_no_billing_reachable` is a guard tests
assert with, `no_op_handler` is the endurance workload, the `fixture_*` helpers exist to be
read by tests. The two that are genuinely unused — `initial_keys` and `key_between`, position
insertion for a system that never inserts a node — are *fine*, and forcing them a caller would
be the wrong lesson entirely. The defect family is narrower than "uncalled": it is **a thing
the project points at when asked whether something is done, that nothing in production
touches.** A count cannot tell those apart, so the sweep stays a tool rather than a test.

## 41. A backstop that cannot clear the gate it feeds is not a backstop

`build_default_registry` ordered generation as claude, codex, ollama, **fake**. The fake's
answer is ~80 characters and `DraftPolicy.min_chars` is 200, so the fake could never produce
an acceptable draft — a fact the function's own comment stated, two lines above the order that
made it the last resort for prose.

**Measured, not reasoned about.** Drafting a book on a local model while the Ollama daemon
stopped mid-session: six beats, each generating canned text three times, failing the shape
gate three times, spending their attempt budgets and poisoning. Five exceptions filed, six
content-derived job ids burned unrevivably, and `verify` reporting one clean revision. For an
outage.

**It is §19.1's rule for the fourth time and it hid better than the other three.** A provider
outage and a budget ceiling at least look like refusals; this one looked like *work*. A
healthy provider answered every call, so nothing in the loop could tell that the writer was a
stub — and the unit paid for the discovery three times. **A refusal reached before the work
must cost time, never the unit**, and a stub standing in for a writer is a refusal wearing the
costume of an answer.

The fake leaves `DEFAULT_ORDER` and stays in `DEFAULT_CHEAP_ORDER`, where extraction and
mechanical calls are schema-shaped and determinism is the point. With nothing to absorb it,
the outage surfaces as `ProviderUnavailable` — which the Conductor has always handled
correctly: the attempt is given back and the unit requeues, so the outage costs time.
`LITHARNESS_FAKE_PAD_CHARS` puts the fake back in the generation order, because setting the
pad is already the statement "I am deliberately running this loop on the fake".

**Why no test caught it.** Every test that exercises generation builds its own registry and
passes the fake deliberately, which is correct and says nothing about the default. The one
path that used the default was the CLI, and no CLI test asserts that a *scene* got drafted.
The gap was not in the suite's thoroughness but in what it never used.

## 42. Two levers for who writes the book, because they answer different questions

An operator who wanted to run a book on local models had exactly one lever:
`LITHARNESS_ENV=test`, which filters billing providers — the flag whose entire purpose is §5
rule 2, proving that *test* runs cannot reach a paid provider. Configuring production with a
test guard is how a guard stops meaning anything.

- **`--prefer NAME`** moves a provider to the front. It stays a *preference*: an unhealthy
  choice still falls back, and §5 rule 4 makes the fallback an event rather than a silent
  switch. An unknown name **raises**, because `order` ignores names it does not know by
  design — so a typo would leave the default order in place and the operator would find out
  from the bill. This is the one place a provider name arrives from a human.
- **`--no-billing`** refuses billing providers outright. Not a preference and not expressible
  as one: preferring a free provider still bills the moment that provider blips, which is
  precisely what happened in §41. It is deliberately independent of `LITHARNESS_ENV=test`,
  because a guarantee that could be switched off by configuration would not be a guarantee.

**Measured on a 3B local model**, which is the answer to whether Book Zero needs a paid
provider at fixture scale: a seeded book with no imported snapshot drafts six of six scenes in
42 seconds, free, with seven revisions rebuilding cleanly. Regenerating a *fixture* book is
stricter — its full snapshot is imported, so the integrity gate holds the prose to it, and the
same model was refused at scene 1 for writing `gold 15` where canon says 45. The gate working,
and a measurement of the model.

**And one quality finding worth keeping**, because it is the shape Stage 3's taxonomy is made
of: across all six drafted scenes the ledger never moved — `s1` through `s6` all reported gold
45. The model obeyed "carry these values forward unless this scene changes them" so literally
that the book has no economy. Nothing in the system objects, because nothing yet checks that a
story *progresses*.

## 43. An arc that reproduces the sheet, and a book that need not already exist

Stage 3 asks for 50-80k words from a premise. Two walls stood in front of the first tick, and
neither was about prose.

**`beats_for` refuses any book that is not exactly the template's length**, correctly — a
template that does not fit mislabels every beat after the gap. But `SIX_BEAT` was the only
template, so *every* book longer than six scenes reported itself blocked. `arc_template(n)`
builds a sheet of the right length from the same six functions.

Two properties make that safe rather than convenient:

- **It reproduces `SIX_BEAT` function-for-function at six.** A generalisation that drifted
  there would be a different template quietly relabelling every beat of both golden fixtures,
  and `beat_job_id` derives from the template *id* rather than its content, so nothing
  downstream would notice. `template_for` still hands six-scene books the original sheet, so
  their job ids do not remint for a change that changes nothing they ask for.
- **Singular beats stay singular.** A story has one inciting incident at any length. The
  obvious implementation — distribute the six functions proportionally — gives a sixty-scene
  book twelve inciting incidents and twelve crises, which is not a longer story but a broken
  one. Only *rising* repeats; the rest are pinned to their positions in the arc.

**And a book had to already exist to be worked on.** Every revision came from `import`, which
takes a manuscript file, so "produce a book from a premise" had no entry point — the wall Book
Zero met before its first tick. `new_book` creates N empty scenes and `litharness new` commits
them with the premise, an attributed decision, and optionally a seed snapshot. Empty rather
than absent is deliberate and is what draftable means here: `gate_draft` fills an empty node
and refuses to overwrite content.

It also gives two long-standing test-only symbols their first production callers —
`build_revision` and `initial_keys` — which the §40 audit had listed and correctly declined to
force. They were not unused because they were wrong; they were unused because nothing yet made
a book.

## 44. The first Book Zero run, and the three things it found

A 24-scene book created from a premise, seeded with a starting sheet, drafted by `llama3.2:3b`
through `--prefer ollama --no-billing`. Thirty ticks, 151 seconds, **no cost**, fifteen scenes
accepted, sixteen revisions rebuilding cleanly, nothing parked. §17 says Book Zero's output is
a failure taxonomy rather than a book; this is the first three entries.

**1. The scenes are an order of magnitude too short.** 2,413 words over fifteen scenes — a mean
of 160 words each, against a shape gate whose floor is 200 *characters*. At this rate 24 scenes
is under 4,000 words, and §17's 50-80k would need several hundred scenes rather than a longer
book. The gate cannot see it: `min_chars` is a floor against stubs and truncation, and §1a.1
warns precisely against letting a mechanical number stand in for whether the scene lands.
Nothing in this system yet has an opinion about how long a scene should be.

**2. The ledger never moves.** Fifteen scenes, and every one reports `gold=50, hp=20, level=1`
— the seed values, carried forward unchanged from beginning to end. The instruction says to
carry values forward "unless this scene changes them", and the model never decides that
anything changes them. So the book has no economy, no progression and no stakes, and **no gate
objects**, because every scene agrees with canon at its own position and the contradiction
detector asks only that. Seen twice now, on six scenes and on twenty-four, so it is a property
rather than a fluke. §17 Stage 3 names "progression schedule" as Narrative Planner v0 work;
this is the measurement of what its absence costs.

**3. A story-order bug that only appears past nine scenes.** The ledger read back `s1`, `s10`,
`s11` … `s2`. Order keys are compared as strings and `s10 < s2`, so a book of ten or more
scenes had its story order silently reversed for every consumer that compares them:
`records_before` slicing the context packet, `changes_between` matching a fact's position, and
propagation's filter asking which records come after a change. Zero-padded to the book's own
width now — `s1` to `s6` unchanged at six scenes, which is what both fixtures author.

**The third is the one worth dwelling on.** It was introduced in the same change that made
long books possible, it passed every test in the suite, and the only reason it surfaced is
that a 24-scene book was actually run and its state actually looked at. `litharness state`
existed for two commits at that point; the defect is exactly what it was built to make
visible, and it took one glance at a printed column.

## 45. Asking for a length half-works, and the half is the finding

> **RETRACTED, and the retraction is §51.** Every number in this section is two draws from
> **byte-identical prompts**. `render_prompt` accepted `target_words` and never read it: the
> commit that added it is two lines — the signature and the call site — and the body that
> builds `system` and `prompt` was untouched. The instruction was never sent, on either
> model, in either arm. The re-measurement with it actually wired is in §51; the conclusion
> reverses for the model this section calls incapable of following it. What stands unchanged
> is the paragraph on why a target is not a gate, which was reasoning rather than
> measurement.

§44's first taxonomy entry was that scenes are an order of magnitude too short — 160 words
each against a book that wants 50-80k. Nothing had ever told a generator how long a scene is,
so the obvious fix was to say so. Measured on two local models, drafting the same beat with
and without the instruction:

    llama3.2:3b   none -> 235 words | 900 -> 232 words   (ignored entirely)      [RETRACTED]
    phi4:14b      none -> 289 words | 900 -> 426 words   (+47%)                  [RETRACTED]

**Worth keeping, and it does not close the gap.** It is free, it moves the model that can
follow it, and it makes the ask explicit rather than implicit. It also does nothing at all for
a 3B model, and neither model reached the target. So **scale is a property of the generator**,
and an operator choosing a scene count should divide by what their model actually writes rather
than by what it was asked for: `--scenes 40 --target-words 900` is 36,000 words of intent and
about 17,000 of phi4 or 9,000 of llama3.2.

**It is a target and never a gate**, which is §1a.1 applied in the direction that is easy to
get wrong. A length floor raised to 900 words would pass a scene that rambles for 900 and
refuse a taut one, measuring nothing about whether the scene lands — and it would refuse
prose for obeying an instruction the model could not follow. `gate_draft` still checks only
stubs and runaways, and the live test asserts the target never provokes a refusal, because a
target that fights the gate is worse than no target.

**It lives in `DraftPolicy` so the decision record cites it.** An input that shapes every
piece of prose in the book and appears in no policy record is precisely the invisible input
`policy_config_digest` exists to catch — and `--target-words` is the only part of that policy
the CLI exposes, because an operator who could lower `min_chars` to make a run go green would
have turned the one deterministic check on drafts into a formality.

## 46. A progression schedule is a record that is not canon — and §44 over-generalised

§44's second taxonomy entry read: the ledger never moves, "seen at six scenes and at
twenty-four, so it is a property rather than a fluke". **Both runs were llama3.2.** Measured
against a second model, three samples per condition:

    llama3.2:3b   no schedule 0/3 moved | with schedule 0/3 moved   gold 50, 50, 50
    phi4:14b      no schedule 3/3 moved | with schedule 3/3 moved   gold 0, 0, 0

So the frozen ledger is **a property of that model**, not of this system. Two runs of one
model is one observation, and calling it a property because it happened twice is the same
error §19.1 keeps recording in a new costume: a number this project reported about itself,
generalised past its evidence.

**And phi4's failure is the opposite one, which is more useful than a clean result.** It moves
the ledger every time — straight from 50 gold to 0 in scene one, past the schedule's own s8
milestone of 5. Not stasis but collapse: a book whose entire economy resolves in its first
scene. So the two ends of the model range fail progression in opposite directions, and neither
is what a schedule asks for.

**The schedule instruction shows no measurable effect on either.** llama3.2 ignores it; phi4
was already moving, so nothing can be attributed to it. Kept anyway, and the reasons are worth
separating from the measurement: it is free, it is what §17 Stage 3 names, and n=3 on two small
local models is weak evidence of absence — the models that would write a real Book Zero are not
these. What it is **not** is demonstrated to work, and nothing here should say otherwise.

**The representation is the deliverable, and it is independent of any of that.** A milestone is
a claim about what the state *should become* at a future story position, and `PROPOSED` says
exactly that — so a schedule needs no new storage, no contract field and no prose to parse.
`is_canon` excludes it, so the context packet does not hand it to a scene as an established
fact and `detect_contradictions` does not weigh it against what the prose says: it informs
generation and contaminates nothing.

That matters because §19's Genre clause is "progression follows the planned schedule within
tolerance", and **a schedule that cannot be expressed cannot be checked**. It can be expressed
now, it arrives through `import --state` and `new --state` with no new verb, and `litharness
state` already shows it — milestones marked `proposed` at their positions, beside the canon the
book has actually reached. Where the plan says the book should be and where it is, in one
column, which is the §4.3 answer while §8.4's progression rules live in a sibling.

## 47. The two numbers an operator picks are coupled, and nothing said so

§17 Stage 1 recorded that the context packet drops the oldest prose rather than the least
relevant, and that "on six-scene fixtures the budget never binds, so this limit is currently
invisible; it will not be at Book Zero length." Measured on the real 24-scene run: it did not
bind — 3,309 tokens of 4,500 usable at scene 15, growing about 220 a scene, on track for
scene 24.

Then §45 added `--target-words`, and the two interact. Measured directly:

    words/scene   budget binds at   prior scenes the packet holds
            160         scene 24                              22
            400         scene 10                               8
            900          scene 5                               3
           1500          scene 4                               2

**900 is the shipped default target.** So asking for scenes of a publishable length moves the
binding point from scene 24 to scene 5, and a 40-scene book would draft its ending knowing
three scenes of its own history. Neither number is wrong; they were simply chosen
independently, one of them by me one commit earlier, and nothing connected them.

Two things follow, and neither is a fix for the packing itself — §12 gives relevance scoring
to LongRangeContext and this project has no business inventing it.

- **`--context-budget` exists.** `make_plan_selector` has always taken `token_budget`; the CLI
  never passed it, so the one number that has to move with scene length was the one an
  operator could not set.
- **A book written blind says so.** `context_omitted` has always been on the job payload,
  where nothing reads it, so a book could reach mid-draft with every scene written against
  three scenes of history while `status` reported a clean system. The planner now bumps a
  `context_omitted` digest counter at the moment it drops something, which `status` already
  prints — §4.3's daily digest, doing the job it exists for.

**The counter fires on the condition, not on the book.** It stays at zero for every six-scene
fixture, which is exactly why this limit went unnoticed for so long: nothing this project
routinely runs is long enough to hit it.

## 48. gzip, and the version of it that survives its own control

Suggested: use perplexity, or gzip, to say something about the text. Perplexity is available —
Ollama does return logprobs — but gzip needs no model, no dependency, no provider call and no
cost, and it is deterministic, which matters for a number logged on every accepted scene and
cited in a policy digest.

**The obvious form does not survive its control.** Whole-book compression ratio — compress each
scene alone, compress them together, divide — looked decisive:

    human: mystery fixture     6 scenes   joint/parts 0.757
    human: litrpg fixture      6 scenes   joint/parts 0.625
    machine: llama 24-scene   15 scenes   joint/parts 0.418

Until the fourth row: a machine-written **six**-scene book scores **0.704**, inside the human
range. Same generator, same prompt, different scene count. The ratio falls mechanically as
scenes are added, because gzip's dictionary amortises — so it measures *n*, not authorship.
That is `tricolon_rate` detecting the year, one section earlier in this file, and the only
reason it did not ship is that the control was run first.

**The pairwise form has no n in it.** Normalised compression distance between two scenes,
`(C(xy) - min(C(x),C(y))) / max(C(x),C(y))`, measured across four books with system-voice
blocks stripped:

    human: mystery           min 0.724   median 0.808
    human: litrpg            min 0.766   median 0.783
    machine: llama 6-scene   min 0.696   median 0.818
    machine: llama 24-scene  min 0.089   median 0.711   <- scenes 12 and 13

**The median separates nothing** — 0.71 to 0.82 across all four, human and machine alike — so
a book's average compression distance is noise and reporting it would be inventing a signal.
**The minimum is a duplicate detector**, an order of magnitude below every other pair in every
book. Both halves of that are the finding.

**Stripping the status blocks is not tidying.** The litrpg fixture's own plan says "a status
block appears in every scene; repetition of the block format is intentional and must not be
flagged as an echo", and leaving them in drops that fixture's closest pair from 0.766 to 0.591
— the metric's first act would be to complain about the plan being followed.

**What it caught.** Scene 13 of the Book Zero run was scene 12 with "breath hitched" changed to
"chest tightened" and a digit incremented, and scenes 10 and 14 are close behind at 0.21 and
0.25. Fifteen accepted scenes, zero exceptions, `verify` clean. The shape gate saw the right
length; the integrity gate saw no contradiction, because the ledger was frozen and there was
nothing to contradict; nothing else looks at prose at all. **That book is §1a's stated
nightmare with every mechanical check green**, and it took a stdlib compressor to see it.

**Advisory, and the module docstring now argues for it rather than assuming it.** §10.6 warns
that "inventing a fifth one on a hunch is how its findings get quietly overwritten", and that
warning is correct. Two things answer it: this was measured before it was built, with the
control that killed the first version; and it claims two scenes are the same *text*, which is
checkable without human judgment, where the four refuted proxies claimed something about
quality, which is not. §10.4 still applies in both places — nothing here can gate without
calibration evidence, and this has none.

## 49. Paragraph-grain gzip: three nulls, one coverage trap, and one metric worth keeping

Suggested: break the book into paragraphs, compress them individually, build trees. Four
formulations were measured against a real corpus — 163 pre-2023 RoyalRoad LitRPG books, 165
undeclared 2025, 31 declared `AI-Assisted Content`, reconstructed into books by `fiction_id`
— each with a fixed-window control and a fixed-seed shuffle control, each then handed to an
adversarial pass told to find the confound. **Zero of four survive as authorship signals.**
The nulls are the main product and are recorded first for that reason.

| formulation | statistic | declared-vs-undeclared AUC | outcome |
| --- | --- | --- | --- |
| paragraph echo | min cross-unit paragraph NCD | 0.325 | coverage artifact, see below |
| NCD tree | UPGMA dendrogram over paragraphs, cohesion and shape | 0.412 | clean null |
| predecessor lag | argmin NCD over earlier paragraphs, lag histogram | 0.375 | null, and inverts |
| novelty decay | exponent of the cumulative compression curve | 0.589 | a trigram counter |

**The tree is Cilibrasi and Vitányi (2005) run inside a book instead of across a document
set, and it works — it just gives the same answer for everyone.** Paragraphs really do
cluster by scene, at ≈0.25 above the chance baseline, and the cohesion measure is sound: it
collapses to −0.058..+0.051 under shuffle at every K and every seed, so the baseline is
right. Pre-LLM humans, 2025 humans and declared-AI books score 0.22–0.34 alike, and the
declared/undeclared AUC swings 0.228–0.545 across four sampling seeds — **the seed-to-seed
swing exceeds the distance from chance**. Method note worth keeping for anyone who tries
again: **50.6% of NCD cells in a paragraph-scale matrix are exact ties** (max 89.5%), because
NCD is a ratio of small integer gzip sizes, so half the distance matrix is arbitrary and the
early merges mean nothing. Compression trees at this scale need larger units.

**Predecessor lag fails worse than a null: it awards the looping book the best score in the
corpus.** The known `bookzero-24` duplicate chain is fully present in the matrix and the
argmin lands on every pair — but the lags are 1 and 2, because the duplicated scenes are
*consecutive*. The book scores median lag 1.0, the lowest, and frac≤3 = 1.00, the highest.
Planted period-8 loops light the histogram up in 13 of 14 book-variant pairs; planted
*adjacent* duplication — Book Zero's actual failure shape — moves the statistic the wrong way,
+0.038. Lag 1 is irreducibly ambiguous between "the scene continues" and "the scene is being
rewritten", and no windowing fixes that.

**Novelty decay scored AUC 1.000 machine-versus-human and is a repeated-trigram counter.**
Permuting the chunks left it at 1.000; permuting the *words* inside the window took it to
0.521, chance. `Counter(trigrams)` reproduces it outright at 1.000 / 0.558. Duplicating 24
twelve-word spans in a human window moves the exponent 0.140 → 0.260, while *moving* the same
spans leaves it at 0.147 — it responds to repetition, never to order. And 71 of 72 books
"decay" less than i.i.d. word salad resampled from their own vocabulary, so a memoryless
source beats nearly every real book at "the book stops adding information".

**The coverage trap is the new methodological finding and it generalises past gzip.** Every
size control in the first pass equalised the *number of pair comparisons* while leaving the
*fraction of the book examined* at 100% for a 15-paragraph machine book and 2–3% for an
1,800-paragraph human one. A minimum-over-pairs statistic is a lottery: more tickets, lower
minimum. Demonstrable inside a single book with the text held fixed — `llama3.2-6` scores
0.473 at 8.5% coverage, 0.408 at the "strictest" pair-matched control, and **0.078 at 100%**.
Forcing the large human books to true exhaustion reverses the result: three RoyalRoad books
score 0.052–0.062 with 7–13× more near-verbatim pairs than either machine book, and ten of
thirty score at or below the worse machine book. **There is no size-neutral version** — a
fixed budget favours the small book, exhaustion favours the large one, and both are
artifacts. §19.1's rule about a refusal reached before the work, again, in a new costume.

**A claim in this file's own §48 was wrong and is corrected here.** That entry reported human
minima of 0.72–0.77 and concluded the machine's 0.089 was an order of magnitude outside the
human range. At *scene* grain that holds. At paragraph grain, sampled exhaustively, it does
not: human books reach 0.044. Published serials repeat verbatim spans up to **93 words**
(undeclared 2025) and **70 words** (pre-2023) — longer than this project's own worst machine
book at 59. Human authors write recaps, epigraphs and quoted prophecies and repeat them
exactly.

**Shipped: `craft.repeated_span.v0`**, the longest run of words a scene repeats verbatim from
another accepted scene, system blocks stripped. Its entire justification is one measured
catch. `llama3.2-6` emitted a 28-word paragraph **byte-identical** in scenes 5 and 6, and the
whole-scene NCD of that pair is **0.695** — more than twice `scene_echo`'s alarm, so the
shipped metric calls it clean and always would have. Run forward over that book the way the
loop runs, `scene_echo` reports 0.69–0.82 on every scene and finds nothing, while
`repeated_span` reports 8, 11, 13, 10, 28. NCD is a ratio over the whole scene, so a fixed
duplicated span is diluted by everything around it, and the longer the scenes the better it
hides.

**It is a span and not a compression number on evidence, not taste.** The trigram result above
established that the compression statistic's discriminative content *is* repeated n-grams, so
the gzip form would be an opaque drawing of a count. A span reports its own evidence: "these
28 words appear in scene 5 and again in scene 6" is checkable by eye in the `detail` field,
and there is nothing left to interpret. Every proxy §10.6 refuted failed by having a number
that needed interpreting and getting interpreted as quality.

**What it is not, recorded because it will be misread otherwise.** It is not an AI tell — the
cohort numbers above say a published human serial out-repeats our worst generated book. It
reports the minimum-style extreme and never a rate: flagged-over-total is a pure denominator
artifact that buys AUC 1.000 for free, since `bookzero-24` has 105 cross-unit pairs and one
RoyalRoad book has 1,855,701, so the same three duplicates read as 2.9% against 0.0002%. It
carries no threshold; 0.25 was a plausible operating point in the study and fires on 4 of 10
human books. Advisory, `blocking=False`, no calibration, §10.4 unchanged in both places.

**The open question is operational rather than statistical.** Over the next runs, how many
flags are regeneration defects and how many are deliberate recaps? On this project's own
drafts so far, one of five flagged scene-pairs is information `scene_echo` did not already
have. If that ratio holds over twenty books the metric is redundant and should be deleted
rather than calibrated.

## 50. The calibration path was unmatched, unreachable, and counting gzip's header

A research note was added — `research/quality-measurement/hierarchical-compression-information-texture.md`,
a preregistration-ready methods proposal for hierarchical compression analysis, honest that it
reports no experimental results. Two of its statistics were measured against this corpus and
both were refuted. **What it was actually worth was three defects it exposed in shipped code.**

**Its central framing does not apply here, and saying so is most of the assessment.** The paper
is a *detector* paper: provenance discrimination, localisation of machine spans in mixed
documents, subgroup false-positive rates, the ethics of accusation. This system does not have
that problem — it knows its text is machine-written. The paper's own §2.3 separates provenance
from texture from quality and states they are different prediction targets; §1a.5 and
RevisionJudge are this project's version of the third, and they remain where the evidence is
missing. The one section that matches our problem, §10.13's editorial-intervention study, is the
one with no method attached.

**Order asymmetry (§5.2) is an LZ77 match-distance readout.** NCD symmetrises by construction;
the proposal keeps `A_C(x,y) = (C0(x||y) - C0(y||x)) / max(C0(x)+C0(y), eps)`. The effect is
real and significant in every cohort (t = -3.4 to -4.8) and it is not about narrative. Reversing
paragraph order *inside* each unit while leaving every unit in its book position **inverts the
sign** (t = +6.72); a synthetic test that moves a shared chunk relative to the concatenation
seam, holding content, sizes and mutual information fixed, swings it by twice the entire corpus
effect; and the magnitude varies 7-fold with the deflate window. Declared-vs-undeclared AUC
0.510. On `bookzero-24`, the looping book, the forward fraction is exactly 0.50 — it scores
*more* forward-signed than the median human book, the nearest-predecessor-lag failure repeated.

**A control that cannot fail is not a control, and the one specified here could not.** The plan
was "reverse the book and check the sign flips". `A_C` is algebraically antisymmetric, so whole-
book reversal maps every consecutive pair to its own transpose: measured max
|mean(reversed) + mean(original)| over 34 books is **0.000e+00, to the last bit**. It passes on
pure noise. The substitute that actually killed it permutes content *inside* the units while
leaving the units in place. Add the question to the standing list: *can this control fail?*

**Haar scale energy (§6.3) is a null with a real by-product.** The `e_d` vector is flat across
cohorts (declared-vs-undeclared AUC 0.56), so scale organisation of sentence length separates
nothing where its variance already separated nothing. The by-product is worth keeping: published
prose has genuine long-range sentence-length rhythm, scale slope H ~ 0.60-0.65 against a
simulated white-noise null of 0.471, and shuffling a book's own sentence lengths drops it to
0.478 — onto the null to three decimals. It does not ship, because across 158 disjoint windows
the within-book sd of H equals the between-book sd (0.078 each, ICC(1) = 0.270): it is 73%
measurement-window noise. **Two method rules earned here.** Simulate the null at your own *n* —
the log-log slope estimator is biased low, 0.436 at n=32 against 0.482 at n=1024, so comparing
to a theoretical 0.5 manufactures 0.03 of effect from nothing. And check within-book reliability
before believing any per-book statistic; this project had never run an ICC.

### What was fixed

**`percentile_of` was wrong by up to 0.31, and §7.1 is what found it.** The rule is that
calibration must be matched on "at least length, depth, genre, register, and dialogue
proportion". `craft-profile.json` pooled every chapter over 300 words with no upper bound. The
corpus median chapter is **2,074 words**; `DraftPolicy.target_words` is **900**. Measured over
4,000 chapters:

    metric                      rho vs length   pooled   length-matched   error
    opening_shape_repetition        -0.391       0.503       0.193        -0.310
    sentence_length_variation       +0.110       0.500       0.650        +0.150
    dialogue_ratio                  +0.155       0.500       0.617        +0.117
    tricolon_rate                   -0.050       0.500       0.472        -0.028

`opening_shape_repetition` falls monotonically from 0.0536 to 0.0204 across the length bands,
mechanically, because more sentences means more distinct openings. So a scene at the pooled
50th percentile was at the 19th among chapters its own size. The profile now carries `bands`
and `percentile_of` requires `words` — not defaulted, because an unmatched percentile is wrong
rather than approximate, and a required argument is how "we did not match on length" stops
being expressible. This holds regardless of whether the metrics discriminate anything: the
function's job is the comparison, not the discrimination.

**It abstains outside support rather than extrapolating.** No band covering the length, a band
never built, or a band under `MIN_BAND_CHAPTERS` all return None. A profile built before banding
has no `bands` key and abstains for the same reason — an unstratified corpus cannot support a
matched claim, so there is no pooled ladder to fall back to.

**And it had no production caller.** The function this module's own docstring offers as what
survived the refutation was, in the drafting path, never computed. `craft_gates` now takes the
scene's length and attaches the percentile to each gate's `detail`; `_craft_ladder` threads it;
the scene-draft handler passes `len(result.text.split())`. Same defect family as the null
dispatcher, `rollback_proposal`, `plan_history` and `impact.py`'s scorer.

**Which immediately reported something worth knowing.** A 212-word scene now receives no
percentile, because `MIN_WORDS` is 300 and no band covers it. The Book Zero run wrote scenes of
138 to 205 words, so **every scene it produced sits outside the support of the corpus this
system calibrates against**. Before banding the pooled ladder answered anyway. The abstention is
the feature: it turned a silent wrong answer into a visible gap.

**`scene_echo` was counting gzip's container, and it is a length confound not a rounding
detail.** §5.1's `C_0(x) = C(x) - h_C`; measured, `h_C` is 20 bytes. On two unrelated 22-word
scenes the payload is 105 bytes, so the container is 19% of it and the distance reads 0.6095
uncorrected against 0.7529 corrected. On published prose the bias runs +0.048 at 100 words,
+0.020 at 300, +0.008 at 900 and +0.004 at 2,000 — it shrinks as scenes grow, so **without the
correction a short scene scores as more similar than a long one for no textual reason**, and
this project's own run wrote 147-word scenes. The metric id moves to `craft.scene_echo.v1`
because the arithmetic changed: `promoted_gate` looks a calibration up by `metric_id`, and
evidence recorded against v0 values applied to v1 arithmetic is the silent inversion the
`direction` field already cost this project once.

**Still refuted, still advisory.** None of this makes any of the four metrics discriminate
anything; the rebuilt profile's separation numbers are unchanged to the fourth decimal. What
changed is that the one claim the evidence does support — where a scene sits among published
chapters of its own size — is now correct, reachable, and honest about when it cannot be made.

## 51. Four unblocks, and the instruction that was never sent

Four items were taken together because each was another's precondition: a generator that can
actually write, the sampler, a summariser in the evicted-context slot, and a route by which
corpus-calibrated evidence becomes admissible to the gate. What follows is what the work
found, in the order the findings arrived rather than the order they were planned.

### 51.1 `render_prompt` accepted `target_words` and never read it

`git show 8f7075c -- src/litharness/application/planner.py` is **exactly two lines**: the
parameter on the signature and the argument at the call site. The body that constructs
`system` and `prompt` never mentioned it. Asserted rather than argued — the harness that found
it computes `render_prompt(target=900) == render_prompt(target=0)` and gets `True`.

So §45's table is two draws from byte-identical requests, and its live test parametrised
`(0, DraftPolicy().target_words)` through the same ignoring function, which is why its
assertion could not fail on any model. **This is the `reset_health` shape for the sixth time
and the first with a *measurement* hanging off it**: not a promise whose only caller is a
test, but a promise whose only caller is a test *that reported numbers into the plan*.

The instruction is wired now. Re-measured, three draws per arm, seeds held common across arms,
same beat and same packet:

    llama3.2:3b   none -> 279 | bare ask -> 329 | with a reason -> 384     (+38%)
    phi4:14b      none -> 324 | bare ask -> 458 | with a reason -> 611     (+89%)

Two things reverse. The 3B model the record called incapable of following the instruction
follows it, because it had never been given it. And `phi4` reaches **68% of the target**
against the 19% the six stored runs averaged — so §17 Stage 3's arithmetic moves from 291
scenes for 50,000 words to about 82.

**The second sentence is doing most of the work, and that is the transferable part.** A bare
"write approximately 900 words" moves `phi4` 324 -> 458; naming what the length is *for* —
room for the scene to play out in real time rather than be told in summary — moves it
324 -> 611. A model given only a number pads, and padding is §1a.3 item 6's "summarising
instead of dramatising" arriving through the door opened to avoid it.

Two smaller defects fell out of the same path. `--target-words` reached the *selector* and not
the *handler*, so a run asking for 400 was gated and recorded against `DraftPolicy()`'s 900:
`policy_config_digest` cited a target nobody asked for. And **no shipped command could select
a model** — every adapter was constructed argument-free, so `OllamaProvider.model` was
`qwen3:4b` for every invocation of every subcommand, while §44 attributes the first Book Zero
run to `llama3.2:3b` and §45 names two more. `--prefer ollama` selects the adapter and has
never selected a model, so those attributions cannot have come from the CLI.

### 51.2 The determinism this project believed it had, it does not have

`plan/provider-adapters.md` §4.3 and the Ollama adapter both called `temperature: 0` with a
fixed `seed` "the closest thing to determinism a model offers". Measured, both halves fail:

- **The seed was inert.** At `temperature: 0` there is nothing to sample, so the seed selects
  nothing. Three seeds (7, 101, 202) against one unchanged request returned byte-identical
  text on both models tested. `seed=7` had never bought anything.
- **And `temperature: 0` does not deliver it either.** The same request sent twice is not
  byte-identical: `llama3.2` returned 245 words then 279, a 12% swing, with every later draw
  of that same request landing on 279. The **first** draw against a given prompt comes from a
  different state than the rest.

That last one is the mechanism behind the phantom +47%: a one-draw-per-arm comparison measures
the warm-up as much as it measures the arm. **The rule to carry: draw more than once, and
discard the first.** It belongs beside §50's "ask whether a control *can* fail" and §49's
coverage trap — all three are the same failure, a number whose value is set by the measurement
apparatus rather than by the thing measured.

**What the sampler cost operationally** was the retry ladder. The prompt is frozen onto the job
payload at plan time and re-read verbatim on every attempt, and `Job.fail` changes only status,
attempts and error — so under greedy decoding a refused draft was regenerated from
byte-identical inputs, met the identical refusal, and poisoned the unit. Three model calls to
receive one answer three times.

Fixed by making the sampler per-request (`CompletionRequest.sampler`, each field `None`
meaning "the adapter's default", so every existing call site is unchanged), resolving it from
the `profile` name a request already carried, and deriving the seed from the job's own
`input_digest` **and its attempt number**. That gives the property a pinned constant was
reaching for and getting backwards: the same job replays to the same prose, two different
scenes draw differently, and attempt *n* is a genuinely new draft. Schema-shaped work stays
greedy and carries no seed at all, because recording one would be provenance that explains
nothing.

The sampler is now inside `policy_config_digest`. It was not, and the profile *name* being on
the record is not the same thing: changing `generation.PROSE`'s temperature would have left
every stored digest identical while every scene written after it came from a different
generator.

### 51.3 The evicted-context slot, and why it was safe to ignore until now

§47 measured the 6,000-token budget binding at scene 24 at 160-word scenes and at scene 5 at
the 900-word target, and recorded that the eviction counter "stays at zero for every six-scene
fixture, which is exactly why this limit went unnoticed". That is the sequencing: **the slot
was unreachable because the scenes were too short**, so 51.1 is what makes 51.3 a real
condition rather than a hypothetical.

`domain/context.py` gains a `SUMMARIES` section above `PRIOR_PROSE`, on the packing order's
own existing logic — a summary is a compressed form of prose, so under pressure the compressed
form survives and the raw text goes. Three things about it are decisions rather than mechanics:

**A reserve, or the section is unfillable.** Prose packs greedily nearest-first, so by the time
the oldest scene is known to be evicted, the budget that would carry its summary is already
inside the newest scenes' full text. `SUMMARY_SHARE` holds back at most a quarter, and only as
much as the summaries actually on hand — so a book with none packs exactly as it did before.

**An evicted scene with a summary is no longer an omission.** Recording it in
`rejected_candidates` would make the packet's own accounting say the generator was told nothing
about a scene it was told the substance of.

**Keyed on the scene's content hash, not on the revision.** Every acceptance mints a new
revision id for the whole book, so a revision-keyed summary would re-summarise every scene each
time one landed — forty calls to draft the forty-first. Content-keyed, an untouched scene is
summarised once and a repaired one earns exactly one more; and `packet_for` takes only the
summary whose hash matches the node's current text, so prose repaired since it was summarised
contributes nothing rather than contributing a description of text the book no longer holds.

**The `OPEN` field is the one with a ground truth, and that is why a summariser is worth more
here than elsewhere.** Most summarisation cannot be graded: whether a compression kept the
important parts is the judgment nobody can automate. This project records `open_threads` as
state, so what a summary claims the book still owes is checkable against what the book records
it owes. Advisory, never a gate. The first version of that check counted a single shared word
over four letters, and matched "the sealed letter must be read aloud at the will reading"
against a summary whose only overlap was *aloud* — one shared word between two sentences about
the same book is vocabulary, not coverage, and a number inflated that way is §2's lesson at a
smaller scale. It now requires a majority of the thread's distinctive words.

**The trap it opens, named because it is not yet measured.** This is the one section that hands
the generator prose in a register the book must not use, directly above "now write the scene".
The block says so in words; whether saying so works is a question for the craft instrumentation
on post-eviction scenes, and it is not evidence yet.

### 51.4 Corpus evidence: a class, not a column

`promoted_gate` checked seven things and **not one was about provenance**, and migration 014
had no source column. So corpus evidence was never *refused* here — it was unlabelled, which is
worse, because the refusal looked like it was working. A percentile over 13,000 strangers'
chapters fills `holdout_size`, `precision`, `threshold` and `verdicts_digest` without any single
field being false, and the row as a whole still claims a metric predicts what a reader said
about prose this system wrote.

**The decision: `evidence_class` is the dispatcher, and a gate may make only the claim its
referent supports.** `JUDGMENT` — humans answering about our own scenes — keeps today's seven
checks unchanged and is the only class that may say a scene is not good enough. `POPULATION` —
membership in a named published cohort at matched length — may refuse, on a **different veto**
(`CRAFT_OUT_OF_DISTRIBUTION`) and in a detail that says "outside the published range at this
length" and never "below bar". `BEHAVIOUR` — aggregate reader behaviour over other authors'
whole stories — may rank and refuses nothing. `UNCLASSIFIED` is what a legacy row reads as, and
is refused by name rather than by a NULL check.

`Grain` is a second required field, checked ahead of every class-specific test, and it has one
consequence sharp enough to state plainly: **`followers / total_views` can never promote a
craft gate.** Not at any *n*, not at any AUC. It is a story-level label and a craft gate refuses
a scene. `plan/craft-corpus.md` §4.1 already conceded the ecological-fallacy risk in prose and
§20 action 10 proposed proceeding anyway; this makes the concession a clause that runs. The
route is not closed — a story-grain gate may cite it — and nothing here gates a story.

**A population threshold is read, never typed.** It must equal a stored ladder stop
(`craft.quantile_stop`), so nobody can park it where nothing crosses it; and a stop no chapter
in the reference cohort crosses is refused outright, because an inert gate is worse than an
empty table — it retires the emptiness the brief calls the honest measure of the gap. Verified
against the committed profile: `tricolon_rate` and `dialogue_ratio` have `p01 = 0.0` in *every*
band and are non-negative by construction, so a `p01`/`BELOW` calibration would have cleared
every other condition trivially and never fired.

**The control is a column, not a habit.** A population calibration carries its control cohort's
exceedance at the same threshold in the same band, and `MAX_CONTROL_RATIO` refuses a threshold
the control crosses more than twice as often. **The first thing this refuses is this project's
most promising metric, on data already in git**: at the 700-1100 band — the one bracketing
`DraftPolicy.target_words` — the pre-LLM p99 tricolon line is 4.3478, and *undeclared 2025
human* chapters put p95 at 5.0633 in the same band. More than 5% of prose nobody suspects
crosses a line the reference cohort crosses 1% of the time, a ratio above five times against a
cap of two. §2's 0.629-against-0.606 lesson, relocated from a paragraph into
`why_not_promotable`, where it fires without anyone having to have read it.

`MIN_TAIL_SUPPORT` is derived rather than placed: stops index at `round(p * (n - 1))`, so the
reference cohort's bands give 3, 5, 21, 37 and 6 observations at p99. Five refuses the 300-700
band outright and clears the target band by one — a floor that fails on real data.

`MAX_CONTROL_RATIO = 2.0` is **placed, not derived**, and it is the one number here with
nothing behind it. It guards the whole route's epistemic claim and it is the lever a maintainer
will reach for the first time a population gate refuses something they wanted. Recorded as an
open decision rather than as a measurement.

### 51.5 Two holes that were already open, found on the way

**A corpus calibration could promote by omission.** `cli.py` read
`digest = args.verdicts_digest or current`, so omitting the flag stamped the store's own
answered-audit digest onto numbers measured elsewhere — which then matched the digest
`_craft_ladder` recomputes at every draft, so the staleness clause compared a value against
itself and could never fire. The flag is deleted rather than defaulted: its only legitimate use
was the corpus case, and "elsewhere" is now a class rather than an omission.

**And the sharper one, which was never about digests at all.** Nothing anywhere compared
`holdout_size` against the number of answered audit samples the store actually holds. A digest
cannot: the digest of two verdicts matches the digest of two verdicts, whatever number is
written beside it. So `--holdout 50 --flagged 17 --precision 0.86` against a store holding
**two** verdicts cleared every floor and printed BLOCKING-ELIGIBLE. Several tests in this
repository were passing because of it, and making them honest meant seeding the judgments they
claimed — which is the tell that the bar had been measuring its own fixtures.

The cheapest way to game the whole design is to type `--evidence-class judgment` beside corpus
numbers. No schema makes assertion impossible. What the design buys is that the lie is now
**deliberate rather than an omission**, that it is inside the calibration id so the corrected
re-record does not collide under `INSERT OR IGNORE`, and that it is contradicted by the store —
because large *n* is exactly what makes a corpus measurement attractive to mislabel, and a
judgment row claiming more holdout than the store contains is refused with both numbers named.

## 52. Book Zero, run on a generator that can write: the taxonomy

Thirty scenes, **26,266 words**, drafted end to end with no inline human action, on `phi4:14b`
via Ollama at no cost. Every number below is read out of the store the run wrote.

    scenes planned / drafted     30 / 30
    total words                  26,266
    mean words per scene         875.5   (97% of the 900-word target)
    range                        586 - 1,312
    decisions                    31, all ACCEPT
    gate failures                0
    findings                     0
    exceptions                   0
    tokens per accepted scene    10,108
    cost                         $0.00 (local)

**The scale problem is solved and it was never a model problem.** 875.5 words against the 19%
the six prior runs averaged, because the instruction now reaches the prompt (§51.1). §17
Stage 3's arithmetic goes from 291 scenes for 50,000 words to **57**. At this rate a 50k draft
is about two hours of wall-clock on one local GPU.

**§15's cost model is now measured rather than hypothesised.** It estimated "roughly 10-20k
model tokens per accepted scene"; the run delivers **10,108**, at the bottom of the band, with
extraction, evaluation and the new summary call all included. The estimate stands.

### The dominant failure: whole-scene duplication, unrefused

**Five of thirty scenes (16.7%) are near-copies of an earlier scene**, and the system accepted
every one of them.

    s8  copies s6    0.703          s17 copies s6   0.782
    s11 copies s6    0.823          s17 copies s11  0.814
    s11 copies s8    0.766          s18 copies s12  0.661
    s22 copies s21   0.708

The longest verbatim run is **872 words**. For scale: §49 measured this project's own worst
previous machine book at 59 words and published human serials at up to 93. This is an order of
magnitude past anything in the ledger, and it is not a subtle statistical signal — s11 and s6
are the same scene with different sentences at the edges.

**Nothing in the ladder could refuse it, and that is by design rather than by oversight.**
`repeated_span` measured it correctly and reported 872 in the annotation's `detail`; §10.4
forbids an uncalibrated craft gate from blocking, and it has no calibration. The integrity
detector reads state records at one position, so a scene that duplicates another contradicts
nothing it can see. **Zero findings across thirty scenes** is the accurate summary: the
deterministic ladder is working exactly as specified and the specification has a hole this
book drove through five times.

### The mechanism is the plan, not the sampler

`arc_template(30)` produces **25 `rising` beats out of 30**, and `render_prompt` puts the
beat's title and its function word into the prompt and nothing else from the plan. So scenes
3 through 27 receive, from the planning side, the instruction *"Scene N — dramatic function:
rising"* and differ only in the integer. Twenty-five scenes are asked the same question.

The generator's answer is visible in the summaries the run itself produced: scene 10's says
Kestrel retrieves an artifact from the museum; scene 11's says Thorne *assigns* her the museum
artifact. The book re-issues its own errand because nothing told it not to.

**This reframes the repetition entry.** It would be easy to read 872 duplicated words as a
decoding problem and reach for the sampler — the change §51.2 just made. The evidence does not
support that: the copies cluster on scenes with identical plan input, and the sampler was
already varying per scene and per attempt. **The failure is upstream of generation.** Narrative
Planning v0 — beat sheets with distinct dramatic function, a foreshadow-payoff ledger, a
progression schedule — is what this run says to build, and §17 Stage 5's "in the order Book
Zero's taxonomy demands" now has an order.

*(An observation with its confound named, because it will otherwise be read as a finding: the
copies fall at s8-s18, where the packet carried 7-8 scenes of full prose, and the five scenes
after summary coverage passed four scenes show a maximum similarity of 0.094. That is n=5,
with position confounded against packet composition and nothing varied deliberately. The cheap
experiment is to re-run this book at two `--context-budget` settings and see whether the copy
rate tracks full-prose density. It has not been run, and until it has, the summariser must not
be credited with the improvement.)*

### Progression: the ledger moves once and then stops

Thirty-one extracted `status_snapshot` records, **two distinct ledger states**. Gold goes
12 → 2 in scene 1 and never moves again; level never leaves 1; HP never leaves 18. §46
established that the frozen ledger §44 recorded was a property of `llama3.2` rather than of the
system, and that `phi4` moved it every time — over a six-scene book. Over thirty scenes it
moves once. **So §46's correction was right and its generalisation was too strong**: a capable
model will spend the ledger when a scene gives it a reason, and twenty-five scenes labelled
`rising` give it none. Same root cause as the duplication, showing up in the game layer.

`progression_target` exists and the book had no schedule to hand it, which is the gap §20.6
already names: the progression schedule references a level curve that arrives with the
game-mechanics pack.

### What worked, recorded so the next run does not re-litigate it

- **The eviction slot filled.** 30 of 30 scenes carry a summary; by the last scenes the packet
  held 8 in full and 7 in summary. The path §47 measured as unreachable at 172-word scenes is
  live at 875, exactly as §51.3 predicted.
- **The summaries are usable and the `OPEN` field tracks the state layer.** Coverage of the
  book's one recorded open thread is 1/1 on every sampled summary — measured through
  `check_open_threads`, which is the only field in this system's summaries with a ground truth.
- **Autonomy held.** 400 ticks, 92 jobs, zero exceptions, zero parked units, zero human
  interventions. The three-lane loop — draft, evaluate, summarise — ran to completion and then
  reported `no_work` rather than spinning.

### The taxonomy, ordered by what it says to build next

1. **Undifferentiated beats.** 83% of the plan says `rising`; the plan-side prompt is a title
   and one word. Produces both the duplication and the frozen ledger. → Narrative Planning v0.
2. **No gate refuses a scene that is a copy of another.** Measured at 872 words with the
   metric already reporting it. `repeated_span` makes a mechanical, checkable claim rather
   than a quality claim, so it is the one proxy in this project that could be promoted without
   human verdicts — but note that `build_craft_profile.py` calls `measure(text)` with
   `others=()`, which pins it at 0.0 for every corpus chapter, so no population ladder for it
   exists yet (§51.4). Building one needs the harness to group chapters by `fiction_id`.
3. **Progression has no schedule.** One ledger movement in thirty scenes. → blocked on the
   game-mechanics pack's level curve, per §20.6.
4. **Cost is not the constraint.** 10,108 tokens per scene, $0 locally, ~2 hours for 50k
   words. §15's projection that gate failure rates rather than raw generation would bind is
   correct — and this run had a gate failure rate of zero, which is the problem rather than
   the reassurance.

## 53. A scene that is a copy is an integrity defect, not a craft opinion

§52's dominant finding was five of thirty scenes reproducing an earlier one — the longest
sharing **872 consecutive words** — with all 31 decisions ACCEPT and zero findings. This is
the gate for it, and the interesting part is where it had to live.

### The reclassification is the whole decision

`craft.repeated_span.v0` measured every one of those five, exactly, and reported the number in
the annotation's `detail`. It could refuse none of them, because §10.4 forbids an uncalibrated
craft gate from blocking and no calibration exists. **The measurement was never the gap; the
filing was.**

`craft.py`'s own defence of the metric already contains the argument for moving it:

> "this asserts that two scenes are largely the same text, which is checkable without asking
> anyone… 'this scene is a copy of that one' is a fact rather than an opinion, and §10.6's
> finding is about opinions."

§10.4's bar governs claims about *quality*, and it is the right bar for those — a threshold on
`tricolon_rate` is a guess wearing a measurement's authority until human verdicts say
otherwise. But "these 872 words appear in scene 6 and again in scene 11" is arithmetic over
two strings. It needs no calibration for the same reason `shape.draft.v0`'s 200-character
floor needs none, and for the same reason `state.contradiction.v0` blocks today: a
deterministic finding blocks on `blocks and deterministic`, and that clause was already there.

So the check is a **detector**, appended to `integrity.IN_PROCESS` — which the tuple's own
comment has described as the extension point since it had one member. The craft metric is
untouched and keeps reporting the number on every scene, including the ones that pass.

### `DetectorInput` grew the first field that is not state

Every check until now asked whether the candidate contradicted what the book *records*. A
scene that reproduces another contradicts nothing — the defect is only visible by comparing
prose to prose, and no detector had ever been shown another scene's text. `prior_prose`
carries `(logical_id, text)` for the accepted scenes, empty by default so a caller with no
book to compare against is unchanged.

Both call sites exclude the node under judgment, and the exclusion is load-bearing rather than
tidy at the second one: the draft handler compares a candidate against the base revision it is
not yet part of, but `InProcessEvaluator` judges a revision the scene is already *in*, so a
missing exclusion would report a 900-word self-overlap on every scene in the book.
`checked_rule_ids` gained the new rule in the same change, because a run that names one rule
while applying two is a digest claiming a narrower check than it made.

### The threshold is placed in an empty region of two distributions

`DUPLICATE_SPAN_WORDS = 120`, and it is defensible without a calibration only because of where
it sits rather than because somebody liked the number.

*Above what published human prose does.* §49's measurement over 24 published RoyalRoad serials:
longest verbatim cross-chapter span **93 words** (undeclared 2025), 91 (declared-AI), 70
(pre-2023). Human authors write recaps, epigraphs and quoted prophecies and repeat them
exactly, and that mechanism is what produces long *legitimate* spans — so the line sits above
the largest anyone has observed, with headroom, rather than at it.

*Inside a gap in this system's own output.* Across Book Zero's 30 scenes, the longest span each
scene shares with any earlier one is bimodal with nothing in between:

    24 scenes      0 - 47 words
    5 scenes       353, 431, 700, 737, 872 words
    nothing at all between 48 and 352

Every threshold in that range separates the same five scenes, so the choice is not delicate —
which is the property to look for when a number has to be placed rather than fitted. The golden
fixtures, human-authored, reach 17 (mystery) and 0 (litrpg).

*And two independent methods agree.* Whole-scene `difflib` similarity above 0.5 selects scenes
8, 11, 17, 18, 22. The span threshold selects scenes 8, 11, 17, 18, 22. Two measures sharing
nothing but the input picked the identical set.

Replayed over the thirty accepted scenes, the gate as it now stands refuses exactly those five
and names its evidence in each refusal:

    s8   700 words of this scene appear verbatim in scene-6,  starting at word 383
    s11  872 words                            in scene-8,     starting at word 426
    s17  737 words                            in scene-8,     starting at word 479
    s18  431 words                            in scene-12,    starting at word 177
    s22  353 words                            in scene-21,    starting at word 167

### What the loop actually does with it, which is not what I first wrote here

The first draft of this section said the refusal is a retry, and that the retry only became
correct once the sampler started varying per attempt. **Walking it proved the first half
wrong**, and the correction is worth keeping because the reasoning was plausible and the
behaviour is not what it predicts.

`vetoes_for` does map every blocking finding onto `CONTINUITY_BREACH`, which §4.2 classifies
`RETRYABLE`, so attempt 1's refusal is charged against the unit and issues a retry. But the
finding it produced is recorded, and it then **stands** against the beat — so attempt 2 meets
the *pre-flight* standing gate and parks, free, without calling the provider at all. Measured
through the Conductor: `JOB_FAILED` then `JOB_PARKED`, one generation total.

That is deliberate and pre-dates this gate. Slice 9 measured the alternative at 12 calls and
8,599 tokens against 3 and 1,912, and
`test_a_scene_contradicting_established_canon_is_refused_and_writes_nothing` pins the identical
sequence for the contradiction detector. So a duplicate costs **one** generation and then waits
for a human, revivably. The operator's route past it is the one that already existed and that
a legitimate recap will need: `dismiss`, then `revive`.

**I tried to "fix" this and was wrong to.** Reasoning that a finding about a *refused*
candidate describes prose the book does not contain, I made the standing gate ignore findings
on empty nodes, then made recording conditional on acceptance. Seven tests failed, and they
were right: an *ingested* planted defect also sits against an empty node, and the fixtures
depend on it parking. The finding is node-scoped — "attempts at this beat keep producing this
defect" — not a claim that the manuscript contains the refused text. Recorded here because the
argument for changing it is easy to reconstruct and the tests that refute it are three files
away.

The sampler still matters to this gate, just not where I put it: a *shape* refusal does retry,
and the seed derived from the attempt is what makes that second attempt different prose rather
than the same bytes.

### What it can get wrong, left reachable on purpose

A legitimate recap is the false positive, and §49 names recaps as the mechanism behind long
human spans. Nothing here tries to define "recap" — the operator's remedy already exists and is
the one slice 9 built after walking the journey: dismiss the finding, revive the unit.
Suppressing recaps by rule would need a definition this project does not have, and would be a
guess wearing the threshold's authority — the thing the threshold above is careful not to be.

### Two things this run of the journey surfaced that are not this gate's

**The live run produced no duplicates at all**, which is why the in-loop behaviour above had to
be driven deterministically rather than observed. Fourteen scenes on the same premise and the
same model, maximum pairwise similarity **0.131**, no refusals, no findings — against five
copies in thirty scenes on the first run. The books differ in length and in every derived seed,
nothing was varied deliberately, and n is 1 against 1. **The gate is not the cause and must not
be credited**: it refused nothing, because there was nothing to refuse. Whether duplication is
a property of the run or of length past ~14 scenes is unmeasured, and the honest reading is
that one run of each is not a comparison.

**`decisions_for_job` is ordered by attempt, and `revive` resets the attempt counter**, so a
post-revive acceptance is written at a *lower* attempt than the park that preceded it and
`[-1]` is not the chronological last. Assert on the book, as
`test_dismissing_the_finding_then_reviving_lets_the_beat_through` already does. Two things
downstream of this are worth checking separately and were left alone here: the tick reported
`JOB_PARKED` for the tick that accepted the scene and committed it, and the job row settled
`parked` after its work succeeded. The prose landed correctly in both cases, so this is
reporting rather than corruption — but "the operator surface says a unit needs attention when
its work is done" is the shape §19.1 spends its list on, and it is a real item rather than a
note.

## 54. Narrative Planning v0: one statement per scene, and what it moved

§52's first taxonomy entry was that `arc_template(30)` yields **25 `rising` beats of 30** —
ordinals 3-17 and 19-28, the turn at 18 — while the beat's title and that one function word
were the entire plan-side instruction. Twenty-five scenes were asked an identical question.

**A statement of what happens, not a richer function word.** Giving the rising span a longer
vocabulary — "complication", "setback", "reversal" — differentiates the *label* and leaves the
content mandate as empty as before; two scenes labelled "complication" still have no reason to
differ. What stops scene 11 re-running scene 10's errand is scene 11 having its own errand.

**One model call for the whole book.** A per-scene call would ask a model to invent scene 11
without having seen what scene 10 is for, which is the condition that produces the duplication
in the first place. Asked once, with the premise and every beat's function in view, the model
has to make the scenes differ from *each other*.

It writes `PlanKind.SCENE_PLAN` items scoped to each scene, through the existing
`PlanProposal` path — so the outline is versioned, attributable to a recorded decision, and
rolled back by `revert-plan` like any other plan movement. `plans.py`'s own docstring recorded
that vocabulary as unused since 1.0: "not one is a `scene_plan`; not one carries a `scope`."

**Enqueued when the sheet cannot tell its scenes apart, and never waited on.** The trigger is
a repeated function in the template, so a six-scene book — both golden fixtures — is untouched:
at six every function is distinct and there is nothing to disambiguate. The condition is the
defect, not the book. And a scene drafted without a statement simply omits the line, which is
exactly the prompt that shipped before this existed, so an outline that fails leaves a degraded
book rather than a stalled one.

### What it moved, and what it did not

Same premise, same model, same budget, 30 scenes:

    run 1  no outline          near-copies 5/30   max similarity 0.823   longest span 872
    run 3  outlined            near-copies 0/30   max similarity 0.103   longest span  55

The longest verbatim span a scene shares with any earlier one falls from **872 words to 55** —
below the 93-word maximum §49 measured across 24 published human serials. **The duplicate gate
refused nothing in run 3**, so the gate cannot be the explanation: it never intervened.

**And the confound, which is not small.** Run 2 (no outline, 14 scenes) also produced zero
copies, max similarity 0.131. So the no-outline condition has produced 5 copies once and 0
once, and n is one per arm. **Suggestive, not established** — the cheap experiment is five
runs per arm at 30 scenes.

> **Run, and §54.1 has it.** The effect is real at conventional significance and smaller and
> noisier than this section makes it sound. Two things above are now wrong: the metric, and
> the word "0".

### 54.1 Five books per arm, and the metric had to change first

**Counting copies in the finished book measures the wrong thing once the gate is live.**
`integrity.duplicate_scene.v0` refuses a duplicate rather than accepting it, so the control
arm's copies never reach the text — the beat parks. Measured across all ten books,
`copies_accepted` is **0 in every one of them**, control and outlined alike: the comparison
this section reports would have called the arms identical while one of them parked eleven
beats and the other none. And `max_span` over accepted prose is **censored at the 120-word
threshold by construction** — the control arm's 117 and 98 are the gate's ceiling showing
through rather than the model's behaviour, which is §49's coverage trap in a new costume.
The uncensored quantity is the gate's own finding count.

    duplicate findings per 30-scene book
      control   11, 8, 1, 2, 6     mean 5.6     scenes drafted 19-29
      outlined   0, 0, 0, 1, 1     mean 0.4     scenes drafted 29-30

Exact two-sided permutation test on the difference of means, five per arm: **p = 0.0238**,
against a floor of 2/252 = 0.0079 for this design. One test rather than two — `parked_beats`
is the same number as `duplicate_findings`, since a finding is what parks the beat.

**The arms overlap, and that is the correction this experiment was for.** Control run 3
produced one finding; outlined runs 4 and 5 produced one each. So the honest claim is that
outlining **substantially reduces** whole-scene duplication, not that it eliminates it, and
§54's "0/30" was one draw of a variable that ranges 0 to 1 in this arm.

**The control arm's variance is the finding underneath the finding.** It runs 1 to 11. A
single un-outlined book producing one duplicate is entirely ordinary — which is exactly what
the 14-scene run did, and why two books misled in both directions at once: the 30-scene
control looked like the rule when it was near the top of its range, and the 14-scene control
looked like a refutation when it was near the bottom. **A condition this noisy cannot be
characterised by one run**, and this project had characterised it by one twice.

**The ledger did not move: 2 distinct states in both runs.** So §52's third entry stands
untouched, which is the expected result and worth stating — the outline says what *happens*
and nothing schedules what the *numbers* do. That remains blocked on the level curve the
game-mechanics pack owns (§20.6), exactly where §52 put it.

Mean scene length fell 875.5 → 786.9 words, still 87% of target. Not investigated; a statement
that tells a scene what to do plausibly makes it shorter than one improvising to fill space,
and one run against one run cannot separate that from noise.

### Six defects an adversarial review found before this shipped

Four independent reviewers, then a refutation pass on every claim. Twenty-one candidates, eight
survived. The five that mattered:

**A partially-outlined book could never be outlined.** Reported by four lenses independently
and reproduced end to end. The selector's trigger was "*any* beat missing a statement"; the
handler's skip guard was "*all* beats have one"; and every edit was a `CREATE`. A book that
gains a scene — `new` or `import` on the same book and branch moves the head — keeps the
statements it had, so the selector fired, the guard did not, and `apply_plan_proposal` raised
`plan item 'scene-1-plan' already exists` **after the whole-book call had been paid for**.
Three generations per plan epoch, a poisoned job, an empty exception queue, and the scene that
motivated the outline drafted with no statement forever. Fixed by emitting `UPDATE` where the
item exists and `CREATE` where it does not — and by making the selector and the handler ask
the same question with the same function, which they were not: one matched on scope-then-id
and the other on id alone.

**Refusals hard-coded `RETRY` instead of consulting `decide`.** The only handler in
`application` that minted a failing outcome without the ladder. At the ceiling a hard-coded
RETRY requeues a job the queue then poisons, and the POISONED path files no exception — so an
outline that could never conform went quiet and every scene drafted with no statement. It now
carries `SHAPE_NOT_CONFORMING` and goes through `decide`, which parks it revivably with the
reason attached.

**The no-op path recorded no decision**, leaving the Conductor to settle the attempt against
whatever decision the job last produced — after a refusal, that refusal. A job with nothing
left to do settled as though it had failed.

**No `policy_config_digest`.** The same defect §51.2 had just fixed one layer over: the schema
and the target length shape every statement and appear in no record, so changing them would
have left every stored digest identical while every outline after them came from a different
question.

**The tests were the worst of it, and two of the three failures are ones this project has a
name for.** The consumer side — the selector branch and the prompt line — had **no test at
all**, and this file's own docstring claimed `test_planner.py` covered it. It did not. Branch
coverage showed the selector's new lines never executed. That is §51.1's defect — a claim
about a test that does not test it — committed in the same session that recorded §51.1.

And every happy-path fixture built its outline from `"Kestrel does thing 1."` through
`"Kestrel does thing 30."` — statements the distinctness check passes and a reader would call
one scene written thirty times. **The suite defined a correct outline as exactly the failure
the module exists to prevent.** §19.1's rule is that a suite encoding the defect converts a
bug into a requirement; here it would have made the fixture the specification. The fixture is
now fourteen statements that are actually different scenes.

Also corrected: a test named for the premise refusal reached the *no plan at all* branch and
would have passed with the premise check deleted.

### The distinctness check is exact-string identity, and that is a known floor

It folds case and whitespace and compares for equality. Two statements differing by one word
pass. The cheapest way to satisfy it is therefore near-duplicates, which is a weaker bar than
the module's own rules ask the model for — and the honest reading is that the check catches
the degenerate case and not the interesting one. It is left there rather than tightened
because the near-duplicate threshold would be a placed number with no measurement behind it,
and §53's threshold is placed only because two distributions had an empty gap to put it in.
Whether outlines in practice fail this way is a question for the next runs.

### A store asymmetry found on the way, recorded and not fixed

`record_plan_items` **accepts** a plan with no premise; `plan_revision` then **refuses to
reconstruct it**, raising `PlanProposalError` on read. So a write succeeds and creates a book
that nothing can plan, draft or report on. It is pre-existing and outside this slice; the
outline handler's own premise check is unreachable behind it and stays as a boundary guard.

### 54.2 Ten books cost the machine, and pacing is an autonomy property

The first attempt at §54.1 ended when the host powered off under sustained load — ten books
back to back is hours of continuous local inference, and §17 Stage 3 asks for 24/7 unattended
operation. **A run that cooks its own host is an autonomy failure of the same class as the
provider outage §19.1 records**, and it is not one any gate in this system can see.

Where the pacing belongs is the runner, not the product, and that is an architectural answer
rather than a convenience: `tick` deliberately does one bounded unit per invocation and the
cadence belongs to whatever drives the loop — cron in a real deployment, a shell loop here.
Adding a thermal governor to the Conductor would put a wall-clock concern inside the one
component whose tests inject time.

`scratchpad/thermal.sh` rests a fixed fraction of every unit's runtime whatever the
temperature, and rests longer as the core climbs. **The fixed fraction is the part that
matters, and the reasoning is worth keeping**: a GPU that overheats throttles itself rather
than switching the machine off, so a whole-host shutdown points at power delivery or case heat
soak, and the lever is average draw over minutes rather than the instantaneous core reading.
Measured over the 938 paced units that produced §54.1: peak **75°C**, median 67°C, zero
interventions by the temperature branch — the duty cycle alone held it, and the run completed.
Cost is about 40% wall-clock.

One setting in it is a **correctness** control rather than a thermal one. Ollama unloads an
idle model after five minutes, and §51.2 measured that the first draw against a prompt differs
from every later one. A rest long enough to unload the model would therefore inject that
warm-up artifact into the measurement once per rest, on a schedule set by how hot the room is.
`OLLAMA_KEEP_ALIVE=30m` keeps it resident; a loaded idle model costs VRAM and about 30W, so
the fix is thermally free and the experiment stays comparable across pauses.

## 55. The progression schedule had a reader, a consumer and no writer

§52's third taxonomy entry was the ledger: 31 extracted status records across thirty scenes
holding **two** distinct states. Gold moved once in scene 1 and nothing moved again, in either
arm of §54.1 — the outline says what *happens* and nothing said what the *numbers* do.

**The blocker this carried was stale, and checking it is the whole lesson.** §20.6 recorded
that a progression schedule is blocked because it "references a level curve that only exists
once the game-mechanics pack defines the sheet, and the litrpg fixture contains no XP figure,
no level curve and no milestones". Every word of that is about the **fixture**. Stage 3 books
are not imported from it — they come from `litharness new` with an authored seed sheet, and
Book Zero's was written by hand for that run. A schedule is authorable by exactly the same
route, and generatable by the route §54 had just built.

What was actually missing was one link, and it is the shape §19.1 says to search for:

    domain/extraction.py::progression_target   reads a schedule           exists since §46
    application/planner.py                     passes it to the prompt    wired
    application/planner.py::render_prompt      puts it in the system      wired
    nothing anywhere                           writes a milestone         MISSING

**A complete measuring instrument with nothing to measure** — `domain/impact.py`'s defect
exactly, the one §19.1 records as having made a Stage 2 exit criterion read as satisfied by a
scorer that could only ever report on an engine which did not exist. `progression_target` has
been able to answer since §46 and has answered `None` every time it was asked.

**Asked for in the outline call, not a second one.** §15 measures the per-invocation harness
tax as larger than the payload and says asks fold into one invocation; the model is already
holding the premise and the whole beat sheet, which is what a schedule has to be consistent
with. One call, one verdict: a schedule that fails validation refuses the outline too, rather
than landing beside a good one.

**Three refusals, and the first is the one that is about the defect.**

*A schedule may not schedule stasis.* If every milestone restates the starting sheet it
reproduces §52 exactly while looking like a fix, so it is refused — and so is any pair of
consecutive milestones that are identical, which tells the scenes between them to change
nothing. This is `_statements`' distinctness rule applied to the numbers.

*A schedule may not invent a statistic.* A model free to add an `xp` the book has never held
would have `render_status_line` asking every scene for a field the extractor cannot read back
— inventing a game system rather than scheduling the one the book has. `progression_target`
refuses to interpolate a curve for the same reason: the shape of one is the author's choice.

*A milestone is placed where the sheet says the scene sits*, never at an invented position.
`story_order_key` is `None` exactly when the template is not entitled to answer, and then the
book gets no schedule rather than a guessed one.

**`PROPOSED`, which is why this needed no new storage.** `is_canon` excludes it, so the
context packet never hands a milestone to a scene as established fact and
`detect_contradictions` never weighs one against what the prose says. It informs generation
and contaminates nothing — the property §46 designed and had no producer to exercise.

**A book that does not speak system voice gets no schedule**, decided by the same question
`render_prompt` already asks before requesting a status line, so a locked-room mystery is not
handed a level curve.

**One defect the tests caught, and it would have reached the page.** Coercing milestone values
to `float` put `Gold 4.0` into the rendered status line — and that line is what the generator
is asked to write and what the extractor reads back, so every scene would have been writing a
decimal into a ledger whose canon holds integers. The number's own type is kept.

Measured on the live model, one call, `phi4`: four milestones at s03, s11, s18 and s27, gold
rising 12 → 20 → 25 → 30 → 40 while HP falls 18 → 10 and MP 4 → 0. A debt story that earns and
is worn down, which is progression in the direction the premise asks for.

**What this does not establish, and the distinction matters.** The mechanism writes a schedule
and the loop reads it. Whether the *extracted* ledger then moves is a different question —
that depends on a generator following an instruction, which is the thing §51.1 found this
project had assumed twice without sending. **Level stays at 1 across all four milestones**
against a premise that names a level cap, so even the schedule this run produced is not the
schedule the book wants. The measurement is a drafted book with more than two distinct
extracted states, and §55.1 has it: three, which is movement rather than progression.

### 55.1 The schedule moved the ledger twice and then it stopped

Measured, one 30-scene book on `phi4` with a schedule at s03, s11, s18 and s27:

    canon status records   29        distinct ledger states   3   (was 2)
    gold   12 -> 20 at s03  -> 22 at s07  -> unchanged for the next 23 scenes
    hp, mp, level          never moved at all

So the answer to §55's open question is **movement, not progression**, and the mechanism is
not what failed. The milestones were written, `progression_target` read them, and
`render_prompt` put the next one in front of every scene. The generator took the first
milestone's gold, took two more the scene after it, and then ignored the schedule for
three-quarters of the book — the s11, s18 and s27 milestones asking for 25, 30 and 40 gold
produced nothing at all.

**The instruction defaults to stasis, and it says so in its own docstring.** §46 wrote the
progression clause and recorded the problem beside it: *"The instruction above defaults to
stasis, and a model with no reason to change anything keeps everything."* The clause it added
is hedged three times over — *carry these values forward unchanged unless this scene changes
them*, then *move it toward that where the events warrant it*, then *do not move it for no
reason on the page*. Every hedge is defensible on its own and their sum is an instruction to
leave the numbers alone unless the scene forces the issue, which is what the model did.

**This is §51.1's shape a second time, and that is the transferable part.** There the plan
carried a target the prompt never rendered; here the prompt renders it and the surrounding
words tell the model it may decline. In both cases the machinery was complete, the record
said the feature existed, and the thing that decided the outcome was one sentence of prompt
wording that nobody had measured. §51.1 also measured the fix: a bare instruction moved `phi4`
324 -> 458 words and an instruction that said what the length was *for* moved it 324 -> 611.
The schedule clause has had no equivalent pass.

**So the next experiment is named and cheap**, and it is the same shape as §51.1's: hold the
schedule fixed, vary the progression clause, three draws per arm, and count distinct extracted
states. Candidate arms are the current hedged wording, one that states the milestone as a
commitment the scene must land, and one that names what the movement is *for* the way the
length instruction does. Until that is run, the honest reading of this section is that a
progression schedule is **necessary and demonstrably not sufficient**, and taxonomy entry 3
stays open with its cause relocated from "there is no schedule" to "the scene is told it may
ignore one".

Two beats parked to the duplicate gate, so the book drafted 28 of 30 — unremarkable at this
point and noted so the scene count is not read as a new failure.

## 56. Forty-nine draws, and not one number that was not already on the page

§55.1 named the next experiment and named it precisely: hold the schedule fixed, vary the
progression clause, three draws per arm, count distinct extracted states. It has been run, and the
result does not support the section that asked for it. **The clause was never the variable.**

**Run as one scene rather than as five books, and the design is the reason the answer is
readable.** §55.1's own metric is distinct states across a thirty-scene book, which is a GPU-hour
per draw and cannot separate the wording from the thirty other things that vary across a book. The
instruction's effect is a per-scene question, so a real ten-scene prefix was drafted once on
`phi4:latest` (280 seconds) and scene 11 was then drawn ten times per arm from a byte-identical
checkpoint — same packet, same status example, same milestone, same scene plan, same sampler, same
seed sequence. `A_current` is asserted byte-identical to `render_prompt` at run time, so the
control arm is the shipped system rather than a paraphrase of it, and `Z_none` is asserted
identical to `progression=None`. The checkpoint:

    current    [STATUS] rook — Level 1 | HP 15/18 | MP 6/4 | Gold 25
    milestone  [STATUS] rook — Level 1 | HP  5/18 | MP 2/4 | Gold 30   (at s17, six scenes ahead)

Five arms: the no-clause control, the shipped wording, the hedges removed, the milestone as a
commitment this scene helps land, and one naming what the movement is *for* — §51.1's shape, the
one that beat a bare instruction on length. Measured, `phi4:latest`, ten draws each:

    arm             n   parsed   gold moved   hp moved   = milestone
    Z_none         10       10            0          0             0
    A_current      10       10            1          0             0
    B_bare         10        9            1          0             0
    C_commitment   10       10            2          1             1
    D_purpose      10       10            0          0             0

**The statistic that matters is not in that table, and it is the whole finding.** Every value any
draw wrote, in every field, was a number already printed in its prompt. Gold ∈ {25, 30}, hp ∈ {15,
5}, mp ∈ {6, 4, 2} — the current line, the milestone line, or a ceiling read off the denominator.
**Across forty-nine parsed draws not one intermediate state was computed.** The two occasions the
ledger moved at all were a copy of the milestone's gold figure and, once, a copy of the entire
milestone line. The model is not declining an instruction; it is reproducing whichever status line
is nearest to hand, which is §52's whole-scene duplication arriving in the ledger.

So a clause ablation on this generator was never going to answer anything, and **that is the
transferable part**: the experiment §55.1 specified would have returned "no effect" for five arms,
and the reading would have been that wording does not matter. It does. It could not be seen here.

### 56.1 The same prompts on a frontier generator, and what it costs

§15's "tens of dollars" is scoped to a 100k-word draft at API-key pricing and was read as a
blocker on the arm itself. It is not one. `ClaudeCodeProvider` passes no credential and inherits
the local `claude` install's auth, so on a subscription the recorded `total_cost_usd` is an
equivalent price for quota already paid. More to the point, `DEFAULT_ORDER` is `("claude_code",
"codex", "ollama")` and `generation` is deliberately absent from `CHEAP_CALL_CLASSES` — **the
frontier arm is what an unflagged `litharness tick` already does**, and every run in this log
needed `--prefer ollama` to get off it. The taxonomy was gathered on 3B–14B models by choice,
which §17 Stage 3 permits as instrumentation and §1a.5 forbids on the page.

Same checkpoint, same prompts, only the provider swapped — the contrast that separates harness
debt from generator debt. Eight draws per arm, one lost to a 529:

    generator      arm             n   gold moved   hp moved   computed values   words
    phi4:latest    A_current      10            1          0                 0     653
    phi4:latest    C_commitment   10            2          1                 0     687
    claude_code    A_current       7            1          6                 6     985
    claude_code    C_commitment    8            8          7                 9     988

    hp written, claude_code A_current      12, 10, 12, 11, 12, 11, 15
    hp written, claude_code C_commitment   10, 15, 10, 12, 10, 10, 12, 12

Current is 15 and the milestone is 5; none of those figures is printed anywhere in the prompt.
Fisher exact on draws carrying a computed value, 15/15 against 0/49: p < 1e-9. On hp moved within
the shipped arm, 6/7 against 0/10: **p = 0.00057**. Both arms also normalised the impossible `MP
6/4` to `4/4`, and both land ~985 words against the 900-word target where `phi4` reaches 653.

**And with a generator that can act on it, the clause is large.** Gold moved in 8 of 8 under
`C_commitment` against 1 of 7 under the shipped wording — **p = 0.0014**. §55.1's instinct that the
hedges suppress movement is correct; it was simply unmeasurable on the generator §55.1 proposed to
measure it with.

**The hedge was guarding something real, so this is not a wording recommendation yet.**
`C_commitment` landed on the milestone's exact gold figure of 30 in six of eight draws, which is
precisely the jump `do not jump to it` exists to prevent. Two draws moved gold *down* — 15 and 20,
the debt being paid, which is the story the premise asks for — and hp stayed gradual in both arms.
The trade is between a ledger that does not move and one that arrives early, and it can now be
decided on evidence at the cost of a few draws. It could not be before.

### 56.2 The arm found a defect before it found anything else

The run's own summary table reported `extract 0` for all sixteen frontier draws. That was not a
null result. `subprocess_runner` decoded the CLI pipe with the host locale, so every em dash in
generated prose arrived as three characters and `STATUS_PATTERN`, which matches U+2014 exactly,
matched nothing. A frontier Book Zero would have reported a permanently frozen ledger for a reason
having nothing to do with the generator. Fixed in `0e17acc`, with a test that exercises the real
subprocess rather than an injected `Runner`; the numbers above are read from the repaired files.

Two more, measured on real `claude -p` round trips and left open:

- **The health probe is a billed invocation no ceiling can see.** `Conductor.tick` calls
  `reset_health()` every tick and each cron tick is a fresh process, so the verdict never survives
  and a generating tick pays a probe. Measured: **$0.3386** cold (33,792 cache-write, 0 cache-read)
  and $0.1013 on a warm generation call. It passes neither `budget_check` nor any recorded
  decision, so `--max-cost-usd-per-day` cannot bound it.
- **The recorded model can be the wrong one.** A call requesting `claude-opus-5` returned
  `modelUsage` keyed `['claude-haiku-4-5-20251001', 'claude-opus-5']`, and `CompletionResult.model`
  reported `claude-haiku-4-5`, because `resolved` takes the first entry of the dict. Opus wrote the
  prose and Haiku is the CLI's own overhead; a provenance record naming the wrong model is what
  §19's attribution chain exists to prevent.

### 56.3 The label the craft programme pivoted to does not separate prose

`plan/craft-corpus.md` §4.1 calls calibrating proxies against `conversion = followers /
total_views` "viable now", §4.3 scores a model critic against the same label, and §4.4 selects a
reference corpus from its deciles. The label itself had never been checked, and checking it is
CPU-only on the two cached shards. Run before any critic — 354 LitRPG stories, top against bottom
conversion decile, 35 a side, with a 400-draw permuted-label null in the same pass:

    metric                       prose   conv AUC   null p05–p95   outside   era AUC
    dialogue_ratio                 yes      0.389   0.390–0.614        yes     0.508
    opening_shape_repetition       yes      0.367   0.394–0.614        yes     0.417
    sentence_length_cv             yes      0.483   0.397–0.618         no     0.555
    tricolon_rate                  yes      0.552   0.385–0.616         no     0.644
    word_count                     yes      0.575   0.390–0.618         no     0.486
    chapters_seen                   no      0.308   0.385–0.636        yes     0.689
    followers   (label component)   no      0.814   0.385–0.621        yes     0.510

**The top conversion decile is recoverable from follower count at AUC 0.814.** §3's "ρ = 0.438
against raw followers, so it is not popularity restated" holds across the middle of the
distribution and does not survive a decile split — which is exactly where §4.4 proposes to select
the corpus. Stratifying is the only rescue and it fails: pooled decile AUC within follower bands
runs 0.36–0.59 with per-band values swinging 0.41 / 0.76 / 0.55, and within length bands the same.
And `tricolon_rate` separates the year (0.644) better than the reader (0.552, inside its null) —
the lesson in a fourth costume, now against the engagement label rather than the declaration one.

This refutes the label at story-decile grain with these five instruments. It does not prove a
critic would fail, since a critic reads what counters cannot. What it establishes is that **the
control for any §4.3 critic is measured and it is `followers` at 0.814, not chance at 0.500** — and
that the number has to be pre-registered rather than discovered afterwards.

### 56.4 The packet stops representing the book at about forty scenes

§47 measured the context budget as binding at scene 5, and migration 019's summaries softened it.
Re-run over the pure `assemble` with one accepted status record per drafted scene — §52's own
density, 31 records over 30 scenes — the picture is worse and the mechanism is different. `FACTS`
is packed ahead of summaries and prose, so the ledger crowds out the story and the horizon
*shrinks* as the book grows:

    scenes   full prose   summaries   facts   dark      at --context-budget 24000
        20            3          16      19      0                         0 dark
        30            3          19      29      7                         0 dark
        57            2          22      56     32                         0 dark
        82            2          12      81     67                         0 dark
       120            1          10     119    108                              —

"Dark" is a prior scene in no form at all — not full text, not summary. **Stage 3's stated target
is 50–80k words, which at §52's measured 875-word scene is 57 to 82 scenes**, and at the shipped
default those books carry 32 to 67 dark scenes. At 82 the packet is 81 status records and 14 pieces
of story. §52's "nothing in the run suggests the remaining scenes are a different problem" is
therefore wrong: the remaining scenes are precisely where the packet stops representing the book,
and a 30-scene run could not have found it.

The mitigation available today is a flag, not a packer. Whether the horizon is a *quality* boundary
is a separate question and §52's unrun two-budget ablation is what answers it; nothing here
licenses building a relevance scorer, and LongRangeContext is a different concern from a budget the
ledger exhausts.

### 56.5 What the run demonstrated about the rules pack, without being asked to

The prefix drafted for §56 put `MP 6/4` — mana above its own ceiling — into accepted canon at s05
and s10, across twelve ACCEPT decisions and **zero findings**. The outline had already scheduled
it: `milestone-s10` carries `mp 6, mp_max 4`, so the system planned an impossible state and then
`system_voice_example` rendered it into every later prompt as "the state as it stands", with "carry
these values forward unchanged". Some draws copied it and some silently repaired it; neither is a
recorded decision, and it contaminated the ablation's own mp column, which is why §56 reports only
gold and hp.

`detect_contradictions` cannot catch this by construction — it groups on `(subject, predicate,
order_key)` and fires only when two canon records disagree at one position, so one internally
impossible record is invisible to it. `_milestones` refuses stasis and refuses an invented
statistic and never asks whether a milestone is possible. **`stats.ceiling.v0` is built and green**
in `C:\DEV\ContinuityEvaluation` with its five siblings; it reaches the loop only through
`--continuity-evaluator-command`, which defaults to unset — so §52, §54.1, §55.1 and this run all
drafted without the genre's best deterministic quality claim switched on.

### 56.6 What this says to build, and what it says not to

1. **Stop gathering taxonomy on 14B models.** Every duplication and ledger figure in §52, §54.1 and
   §55.1 is a measurement of `phi4`. The sharper cost is not that the figures are wrong but that
   **prompt experiments on that generator return false negatives** — the clause ablation reads as
   no effect on `phi4` and as p = 0.0014 on the frontier arm, from the same prompts at the same
   checkpoint.
2. **Re-run §54.1's duplication comparison on the frontier arm before building more planner.**
   Narrative Planning v0's justification is near-copies 5/30 → 0/30 at p = 0.0238, measured on the
   generator now shown to copy numbers verbatim. If duplication is largely a `phi4` artifact,
   Stage 5's ordering is aimed at the wrong entry.
3. **Wire the rules pack on, and refuse an impossible milestone.** Deterministic arithmetic, so it
   blocks without a calibration exactly as `integrity.duplicate_scene.v0` does under §53's
   precedent.
4. **Do not build the §4.3 critic yet**, and do not select §4.4's corpus from conversion deciles.
5. Two tightenings on the promotion path, both small and both independent of everything above:
   `tail_support` is computed direction-blind, so a BELOW gate at p01 reports ≈0.99n where its
   failing tail holds ≈0.01n and `MIN_TAIL_SUPPORT` is bypassed by two orders of magnitude; and the
   only inertness guard is `reference_exceedance <= 0.0`, with no upper bound, so a threshold
   refusing 99% of the reference cohort is promotable and its control clause is vacuous at exactly
   the exceedance where it matters.

**What §56 does not establish.** One checkpoint, one premise, one book, and the frontier arms are
n=7 and n=8 against a generator whose sampler this harness cannot hold — `claude -p` exposes no
temperature or seed, so the frontier draws are not paired with the local ones and their spread is
not this experiment's to control. The mp column is contaminated by §56.5. What survives all of that
is the between-arm comparison of rates, which is what the question needed.

## 57. Twenty-four scenes, no outline, and the longest repeat is seventeen words

§52's dominant failure was whole-scene duplication — five of thirty scenes near-copies, longest
verbatim run **872 words** against a published-human maximum of 93 — and §54 answered it with
Narrative Planning v0, measured at §54.1 as duplicate findings per book running **11, 8, 1, 2, 6
without an outline against 0, 0, 0, 1, 1 with one**, mean 5.6 against 0.4, permutation
p = 0.0238. That comparison is the whole justification for the outline call, and §52's taxonomy
put Narrative Planning first on the strength of it.

Every one of those ten books was drafted on `phi4:latest`. §56 then measured that same generator
reproducing whichever status line was nearest to hand in 49 of 49 draws, never once computing a
number. Copying prose and copying numbers are plausibly one behaviour, so the arm worth running
is §54.1's **control** — the no-outline condition — on a generator that does not copy.

**Measured: two 12-scene books, `--no-outline`, `claude_code` in front, everything else shipped
defaults.**

    book   scenes   words    duplicate findings   longest cross-scene verbatim span
       1       12   12,464                    0                            17 words
       2       12   12,085                    0                            12 words

    for comparison
       §52, phi4, 30 scenes, no outline                    872 words, 5 near-copies
       §54, phi4, 30 scenes, with outline                   55 words
       published human LitRPG, 24 serials (§49)             93 words (maximum observed)
       golden fixtures, human-authored                      17 (mystery), 0 (litrpg)

**The count metric proves nothing here, and the reason is a design error worth recording.**
Twelve scenes was chosen to halve the quota, on the argument that the outline places four to
eight milestones regardless of book length — which is sound for the *ledger* question §56 asked
and wrong for this one. Duplication is a property of pairs: a 30-scene book offers 435 and a
12-scene book 66, a factor of 6.6. §54.1's control mean of 5.6 findings over 435 pairs is
0.0129 per pair, so two 12-scene books at an unchanged rate would be expected to produce
**1.70** findings, and observing zero has Poisson p = **0.183**. Not a result. Had the arm been
run at 30 scenes it would have cost about 2.5x and answered the question it was built for.

**The span metric does carry, and it is the one §52 led with.** `longest_repeated_span` is a
maximum over pairs rather than a count, so it does not lose power the same way — §52's 872 words
came from a single pair, and 66 pairs is ample opportunity for one long repeat to appear if the
generator produces them at all. It produced none: **17 and 12 words, below the 93-word maximum
observed across 24 published human serials and at the level of the hand-authored mystery
fixture.** The duplicate gate refused nothing, so the gate is not the explanation, and no outline
was written, so Narrative Planning is not either.

**What this licenses saying.** Whole-scene duplication at the magnitude §52 recorded is a
property of `phi4:14b` and does not reproduce on a frontier generator drafting the same premise
in the same condition. It does **not** say the outline is worthless — §54.1's effect on `phi4` is
real and measured, and an outline plausibly does other work (a scene that knows what it is for is
not only a scene that avoids repeating). What it says is that **the taxonomy entry the outline was
built to close is not present in the generator §1a.5 requires**, so Stage 5's ordering — which
§52 set from that entry — is aimed at a defect the real drafting arm does not exhibit, and
Narrative Planning's value has to be re-argued on some other measured ground before more planner
machinery is built on it.

**Cost, and one thing it confirmed.** 24 scenes, 24,549 words, ~$0.215 equivalent per scene,
about $5.20 for the pair — close to the §56.1 extrapolation, which makes that estimate measured.
The loop was driven in one process rather than one per tick, which pays §56.2's unmetered health
probe once instead of ~26 times; that is also what a daemon does. And the run wrote four
`policy_decisions` attributing Opus-drafted scenes to `claude-haiku-4-5` before the provenance
fix landed mid-run, which is §56.2's second defect arriving as data rather than as an argument.

**What would settle the count metric**: the same arm at 30 scenes, matching §54.1 exactly, at
about 2.5x this cost. Until then the honest reading is that the span evidence is strong and the
count evidence is absent, and the two should not be quoted as if they were one result.

## 58. Every edit that made the text less familiar raised the score

BRIEF.md §3 diagnosed all twenty refuted proxies as static, absolute and correlational, and
`research/quality-measurement/surprisal.py` was the one instrument built to share none of those
properties: Context Dependency Gain, the mean log-probability gain a block of prose gets from
its own chapter's prefix over a length-matched prefix from a different chapter, under a frozen
base model (`gemma-3-4b-pt`). BRIEF.md recorded it as *built and not yet evidenced*. It has now
been run — the full `ablate.py` battery over 30 Mother of Learning chapters, 962 scored
variants, paired within-chapter by construction — and it is **dead, killed by the sham its own
docstring pre-registered as the kill condition.**

**The headline is that there is no headline.** Detect AUC **0.5153** against its own originals;
paired rate 0.5139 with a Wilson 95% interval **(0.4774, 0.5502)** over 720 damage pairs.
`evaluate.verdict()` reads "does not separate damaged prose from its own original" before any
control needs consulting. Word count separates the same variant pool at **0.5733**, so §1a.1's
shallow incumbent also wins outright.

**The control story is the finding.** Per-ablation AUC versus originals, oriented so above 0.5
means the variant scored below its original (the direction damage was declared to move):

    ablation              kind        AUC      |AUC-0.5|   mean delta at dose 1.0
    rename_entities       SHAM        0.1725     0.3275         +0.1008
    sentence_deletion     degrader    0.5961     0.0961         +0.0014  (non-monotone)
    dialogue_flatten      degrader    0.4189     0.0811         +0.0263  (wrong direction)
    respell               SHAM        0.4228     0.0772         +0.0131
    paragraph_shuffle     degrader    0.5583     0.0583         -0.0053
    transplant            degrader    0.5090     0.0090         +0.0189
    sentence_shuffle      degrader    0.5058     0.0058         +0.0054
    connective_scramble   degrader    0.5033     0.0033         +0.0010

The rename sham moved CDG **3.4× further than the strongest degrader and 5.6× further than
paragraph shuffle**, upward, dose-monotone (+0.040, +0.062, +0.087, +0.101) — the cleanest
dose-response curve in the entire battery belongs to the transformation that damages nothing.
And the two other risers complete the mechanism: `respell` (spelling variants, straightened
quotes) and `dialogue_flatten` (quotation marks deleted) are the other two edits that perturb
the *surface* the model may have memorised, and every one of them raised the score while actual
damage sat at chance. `surprisal.py`'s docstring argued memorisation "is handled by the same
subtraction" because recall raises both terms. Measured: it is not. Recall of the published
original inflates the foreign-prefix term and compresses the gap; any edit that breaks verbatim
familiarity releases it. **CDG over published fiction is substantially a memorisation-release
detector**, and the sham built to catch exactly that caught exactly that.

**Two subsidiary readings, recorded because they would bite the next design too.**

- *The margin statistic can be gamed by an inverted sham response.* `Result.margin` is
  detect − sham = 0.5153 − 0.2811 = **+0.2342**, which reads as a healthy margin — but only
  because the sham moved *opposite* to the declared damage direction, which inflates the
  subtraction instead of shrinking it. The pre-committed reading was |AUC − 0.5| per ablation,
  and by that reading the sham response dwarfs everything. `evaluate.verdict()` happened to
  catch this metric at the first rung anyway (detect within 0.05 of chance), but a metric with
  detect 0.58 and an inverted sham at 0.28 would sail through the margin check while being
  three-quarters sham. If the harness is ever revisited, the margin should be
  |detect − 0.5| − |sham − 0.5|.
- *Transplant — the declared upper anchor — was invisible at 0.5090*, and the donor choice is
  why it cannot be read as exoneration. Donors came from the same book thirty-plus chapters
  ahead (the stricter choice for the foreign-*prefix* control, and `evaluate.selftest`'s
  precedent), so at full dose the scored text is still memorised Mother of Learning in the
  memorised voice with the memorised cast. For a score dominated by familiarity, that graft is
  undetectable by construction. A cross-book donor would presumably move CDG — for the same
  familiarity reason, not a craft one — which is a second route to the same verdict, not a
  rescue.

**What this licenses.** The "nothing model-based has been tried" opening in BRIEF.md §3 is now
closed: it was tried, properly controlled, and died to the control — entry 21, and the first
casualty of the model-based family. The transferable result is a measured confound, not just a
dead metric: **a base model's familiarity with a published text swings a surprisal-difference
score several times harder than real structural damage does.** Any future model-based measure
validated on published fiction — including the §4.3-style critic the craft corpus still
gestures at — either runs on text the scoring model provably has not memorised (this project's
own generated prose qualifies; the calibration corpus does not) or measures and subtracts its
familiarity term explicitly. That constraint was bought for 66 GPU-minutes at zero dollars and
it applies to every design in that family.

**Operational footnote, because the run itself refuted an assumption.** The battery's first
attempt took the machine down with a thermal hard-shutdown at call 431 of 962 — sustained
~300W bursts on a box whose cooling turns out to sit at a 70-72°C equilibrium even at a
halved duty cycle. The run finished because every score was flushed to
`results/cdg-raw.jsonl` as it was computed and both the ablations and the scorer are
deterministic, so a restart replays finished calls from disk instead of the GPU: 431 scored
before the shutdown, 41 under a first governor whose 60°C resume floor a heat-soaked case
could not reach quickly (and whose hold a single failed `nvidia-smi` read could silently
cancel — measured doing so at 69°C), 490 under the tuned one (72°C pause, 66°C resume, three
strikes on the sensor), zero redone, zero NaN. `cdg_battery.py` carries the constants and the
reasoning; the raw log carries a `gpu_temp` per scored call, so the thermal story of the run
is itself data. Total wall for the final leg: 66 minutes.

**Addendum, same day: the sham was contaminated, and the verdict survived its own control
being fixed.** A review pass found that `rename_entities` selected "the most frequent
capitalised tokens" with a frequency floor and no stopword check, so its top-12 "entities"
on chapter 1 were Zorian, **The**, **You**, Mother, Cyoria, Fortov, **She**, Kirielle, Ilsa,
**What**, **There**, **His** — at every dose the memorisation control was also rewriting
articles and pronouns into names, which is grammatical damage, the one thing a sham must not
inflict. Fixed with two text-derived checks (a token that also occurs lowercase is sentence
capitalisation; a token never seen mid-sentence is a sentence-starter), the 120 rename
records were purged from the raw log, and the battery re-ran: 120 GPU calls, 842 replayed —
by a **text digest** now stored per record, because the `(unit, ablation, dose)` triple
would have replayed the buggy variants' numbers as if the code had not changed — 15.3
minutes, `results/cdg.pre-sham-fix.json` preserving the superseded summary.

What the fix changed: the rename effect **shrank by ~40% and survived**. Pooled AUC versus
originals 0.1725 → **0.3036**; mean delta at full dose +0.101 → +0.038; dose curve +0.031 /
+0.036 / +0.041 / +0.038 — saturating where the contaminated curve kept climbing, which
fits the mechanism (breaking the protagonist's name breaks most of the verbatim-recall
surface; clobbering ever more function words kept adding novelty). A sham that renames only
genuine names still moves CDG **2.0× further than the strongest real degrader** (|AUC−0.5|
0.196 against `sentence_deletion`'s 0.096), so the reading above — memorisation-release —
stands, now measured with a control that damages nothing.

What the harness revision changed (this section's own subsidiary reading, implemented the
same day): `evaluate.Result.margin` is now `(detect − 0.5) − |sham − 0.5|`, and the AUCs are
within-chapter means with a chapter-resampled bootstrap CI in place of the Wilson interval
that treated 720 clustered pairs as independent. Under the corrected statistics the summary
reads: detect **0.5188** (was 0.5153 pooled), margin **−0.3713** (the formulation this
section warned about had reported **+0.2342** for the same shape of data), length incumbent
0.5229 (within-chapter; still ≥ detect), paired CI **(0.4514, 0.5708)** (Wilson had claimed
(0.4774, 0.5502)). Verdict unchanged at the first rung: **DEAD — damage does not move the
score in the declared direction.** Entry 21 stands; every number in the two paragraphs above
this addendum that disagrees with `results/cdg.json` is superseded by it.

## 59. The gate's floor was on the estimate, and the row it admitted bounds at 0.566

Two research notes landed on 2026-08-17 (`research/proof-carrying-prose`,
`research/certified-bounded-revision`) and every number in both was reproduced against this
artifact before anything was taken from them: all nine Clopper-Pearson values, the cascade
recurrence and its closed form, the worked e-value, all six anytime power figures by
independent dynamic program, and the null crossing probability 0.00440766. That check is what
separated the one live defect from the four descriptive theorems.

**The defect.** `Calibration.why_not_promotable` enforced `MIN_PRECISION` as a *point
estimate*, so 14 correct flags of 17 on a holdout of 50 returned `None` — promotable — at an
exact two-sided 95% lower bound of **0.566**. The metric could be barely better than a coin
and produce that table. `MIN_FLAGGED = 17` was derived as the smallest *perfect* flagged set
whose bound clears 0.80, and its own comment said it did not make 0.80 a confidence bound in
general; it was right, and the gap it named was reachable in one line.

**What was not in that comment, and is the reason the fix is a schema change rather than one
`if`.** The bound was not reconstructible from a stored row at all: the schema held a float
`precision` and `flagged`, never the integer numerator, and 0.8235 cannot say whether it was
14 of 17 or 140 of 170. Nor was the pair checked — `precision=0.83` with `flagged=17` asserts
14.11 correct flags and was accepted, so a malformed record could present itself as exact
evidence.

**The change.** `precision` is deleted as a stored column and derived from counts, which makes
the incoherent case unrepresentable rather than merely refused. `correct`,
`selection_family_size` and `clusters` are added (migration 020), all nullable and all refused
when absent, on 015's reasoning about `flagged`. `exact_lower_bound` is a bisection on a
binomial tail summed in log space — no `scipy`, and pinned to the nine published reference
values so a bug in it cannot move the bar while every other test agrees with it.
`MIN_FLAGGED` is **deleted**: the bound implies it at one candidate and goes on implying it as
precision falls, which the constant never did. `MIN_PRECISION` survives as the floor the bound
is compared against, and one check now does the work of the two it replaces, because the limit
never exceeds the estimate.

**Two additions the note argued for that this project had already half-earned.**
`selection_family_size` is the union bound over candidates: a digest over the verdicts is
identical whether one threshold was fixed in advance or a hundred were scanned, so the count
has to be declared. It costs real sample — a perfect score needs 17 flags at one candidate and
**27** at ten. (27 rather than §5.6's 24 because `PROMOTION_ALPHA` is declared two-sided;
three flags is what the convention costs, which is why it is a module constant and not a
column a maintainer could set per row after a near miss.) And `clusters` is BRIEF §2 Pass 5's
ICC lesson arriving where it was missing: `evaluate.py` already resamples by chapter, the
promotion path had no cluster concept, and adding an exact interval without one would have
produced a *narrower* number resting on the same unexamined assumption — strictly worse than
the estimate it replaced, because it carries authority it has not earned. Only the incoherent
case is refused (fewer than two clusters is one observation wearing an interval); a
concentration cap needs per-cluster counts nobody has measured.

**Cost of doing it now: nothing.** `litharness calibrations` still prints nothing and the
`calibrations` table is empty, which is the argument 018 used for making `evidence_class`
required. The first real measurement is the last time that will be true.

**What was deliberately not taken.** The four deterministic theorems (localized
noninterference, stale-write rejection, atomic acceptance, the 55-job cascade bound) are
*descriptive* — they document behaviour the suite already holds — so they are a safety case to
cite, not a change list. `proof-carrying-prose`'s reader trial is not near-term at 793
reader-level outcomes for one endpoint of six. And its anytime-valid machinery solves a
problem this project does not have: all 21 dead proxies died to **confounds**, not to sampling
noise, and an e-process would give a valid answer to the wrong question faster. Also dropped
from the note's own recommendation set: a stored false-positive count (it is `flagged −
correct`), a stored lower bound (derived, and a second copy is a disagreement surface), per-row
alpha and sidedness columns (knobs, not evidence), a minimum-coverage floor (a placed constant
guarding usefulness rather than correctness), and the selection/split/generator/critic digests
(unenforceable today; `verdicts_digest` and `expires_at` already carry currency).

Also landed: BRIEF §6, the six questions that decide whether a real measurement may become a
decision — §5 governs whether a number is real, and those are separate failures.

## 60. The fixtures ship in the wheel, and the discovery chain is deleted

`adapters/contracts_fixtures.py`, `pyproject.toml`, `.github/workflows/ci.yml`. §19's last
entry recorded a three-link chain for finding the golden books —
`LITHARNESS_CONTRACTS_ROOT`, then the installed package's own location, then a sibling
checkout — and defended it as the honest answer to a real constraint: the books lived at
`fixtures/golden/` in the contracts repository root, outside the importable package, so no
wheel carried them and `importlib.resources` could not reach them. That entry is superseded
here. **The constraint was not a fact about packaging; it was a fact about where six JSON
files happened to sit, and it was one `git mv` deep.**

**What the chain was actually costing.** Each link existed because the one before it could
fail, so the failure modes compounded rather than narrowed: link two only worked because the
dependency was an *editable path install* (it walked three directories up from
`lc.__file__`), and link three guessed at a sibling directory beside this repository. Both
were load-bearing and neither was checkable — a clone of this repository on its own could
not run its own suite, and the suite was the only thing that would have said so. CI paid for
the same premise with a second checkout of contracts at a hand-written SHA, under a comment
calling it "the one dependency `uv.lock` cannot pin". That comment was true of a path
dependency and false of the dependency it was describing after this change.

**The move, in three parts.** Contracts 0.2.0 puts the books at
`src/litharness_contracts/fixtures/golden/` and exposes
`litharness_contracts.fixtures.golden_path` as the one canonical lookup, so they travel with
the wheel. `[tool.uv.sources]` here switches from `path = "../litharness-contracts"` to a git
rev, which `uv.lock` records — the pin moves out of a YAML comment and into the lockfile,
where `uv sync --locked` enforces it. CI drops the second checkout, the named subdirectory
and every `working-directory:` line. The `fixtures/source/` prose and annotations stay
outside the package: they are authoring input, the wheel has no reason to carry them, and
the drift test that rebuilds golden from source runs in the repository that owns both.

**`LITHARNESS_CONTRACTS_ROOT` survives, and the reasoning is not the old reasoning.** It is
no longer a link in a chain that has to succeed; it is an override in front of one that
always does. Its job is work-in-progress fixtures — edit a book in a contracts checkout and
read it here without reinstalling — and it still names a checkout *root*, so the path
beneath it moved with the files. It is still checked against the artifact rather than the
directory, which now buys something specific: a root that does not hold the file falls
through to the installed package instead of failing three layers down.

**Why this is a decision and not a chore.** The old arrangement made "can a stranger clone
this and run the tests" unanswerable, and the project had no way to notice, because every
machine that ran the suite already had the sibling. The check that pins it is not a unit
test — it is cloning this repository into a directory with no sibling checkout anywhere and
running `uv sync --locked --extra dev && uv run pytest` there. That is also the only thing
that catches the *next* instance of this defect class, since anything else read through a
checkout-root path fails in the same run.

**One thing deliberately not fixed here.** The contracts repository's root `schemas/`
directory is still outside the package, and ContinuityEvaluation still reaches it by path —
PLAN.md §20.2's `samefile("C:/DEV/litharness-contracts/schemas")`. It is the same defect
class and a separately-tracked one; moving it is a change to a sibling's consumption, not to
this repository's, and bundling them would have hidden which of the two this suite proves.

## 61. "Better than human" became measurable, so it became the goal

The goal is now **superhuman literary quality**, and this entry is what keeps that sentence
from being marketing: "superhuman" means the lower bound of a 95% confidence interval on
blinded, position-swapped pairwise win rate against matched published-human prose exceeds
0.5, judged by paid genre readers. Throughput, uptime and publication cadence stop being
goals. PLAN.md §1a.5 carries the bar; this entry carries why it is the only bar left and
what the refoundation does to the rest of the plan.

**The record forces the instrument, which is the strongest argument for the pivot.** Four
evidence channels have been tried and measured:

    channel                          measured result                                 where
    unpaid solicited judgment        2 verdicts against 104 exported pairs           §1a.4 amendment, README
    revealed preference (labels)     conversion does not separate prose;             §56.3; craft-corpus §4.4 (refused)
                                     deciles select story size and era
    raw model judges                 43–65% positional artifacts; order-consistent   BRIEF §2 Pass 4
                                     survivors prefer human originals ~80%
    model-based scoring (CDG)        dead to its own pre-registered memorisation     §58; BRIEF §2 Pass 6
                                     sham; word count beat it
    persona-reader elicitation       absolute verdict DEAD; pairwise separates on   §70 addenda 3-4;
    (added by §70, not in the        edited-ness (sham 0.78) and its pre-registered plan/persona-
    original four)                   de-stake arm ran backwards                     reader-validity.md

**The fifth row is a later addition and is not evidence yet.** §70 added it under a standing
condition — the table gains a row when a gate reports, and gate 0 reported. It is listed here so
the channel cannot be quietly re-proposed as untried, and it is marked OPEN rather than given a
result because one inconclusive gate is not a measurement of the channel. It is also the only row
whose instrument asks a *reader* question rather than an expert or a distributional one, which is
the reason the four refutations above do not bound it.

Paid pairwise judgment from external genre readers is the one channel with no refutation
against it, because it is the one channel this project never funded. "Bought rather than
volunteered" is the variable the 2-of-104 measurement never tested, and the first month of
operation is its kill-switch: if paid throughput cannot fund a promotable calibration row
(§59's bound, not the deleted `MIN_FLAGGED` constant), that result lands here like every
other dead instrument.

**Five pre-registrations, each bought by an existing measurement, none negotiable.**
(1) The interval is clustered over both readers and items — §59 added `clusters` for
exactly the reason a binomial interval over fifty scenes of one book is one observation
wearing an interval; the same readers judging many pairs is the same failure from the other
side. (2) The tie policy is declared before the first judgment. (3) A judgment where the
reader recognises either passage is excluded — §58 measured a scorer's familiarity with
published text swinging a score several times harder than real damage, and there is no
reason to believe human judges are exempt; the matched-human corpus includes some of the
genre's most-read serials, so recognition is not an edge case, it is the expected case.
(4) The comparator sampling frame is declared before the first reader is paid: beating
median tier-matched RoyalRoad serials and beating the genre's best are different claims,
and the frame *is* the claim. (5) If more than one book could have been reported, the
confidence level is divided by the candidate count — §6.4's selection family applied to
the headline claim itself. Sizing, so the money is honest: at a true win rate of 0.60,
roughly 100–150 decisive judgments clear the bound; at 0.55, 400–500; clustering inflates
both. A thin margin is expensive to certify, and pretending otherwise is how the bar gets
quietly weakened.

**Autonomy is unchanged, and the reconciliation is one sentence.** The production loop
requires no human input: human judgment enters asynchronously as calibration evidence,
gates *promotions* (§17 gate 3, §26's parking discipline), never ticks, and with zero
verdicts in the store the system drafts entire books with every structural annotation held
advisory. The goal does not restore an inline human gate; it prices the evidence that was
always the missing instrument (§1a.4).

**What this entry changes in PLAN.md, all in place with superseded text visible:** the
Role line loses "24/7"; a v2.3 header block records the refoundation; §1a.4 gains the
second amendment (revealed labels dead, paid solicited funded); §1a.5's bars are replaced
by the superiority bar (parity bar struck — with the note that craft-corpus §4.2's
discriminator loses its "bar already written" status, since distinguishable-and-preferred
now passes); §3's "better than human is not a measurable target" is superseded by its own
operationalisation, and cadence/uptime/throughput join the non-goals.

**The programme this licenses, landing as separate entries.** Seven cuts (unattended-
operation hardening; provider plurality; the four refuted craft metrics on the accept
path; sub-frontier support paths; the serial-publication pillar; the duplication-premised
roadmap ordering; the solo audit queue as primary evidence) and three additions (the
pairwise preference engine; promise/payoff and scene-delta instrumentation; plan-level
search licensed by calibration). Each cut cites its licensing measurement in its own
entry; nothing is deleted from `research/`; the calibration promotion rules are
load-bearing and do not weaken. Two corrections to the directive as drafted, accepted
before anything lands: **the §53 duplicate gate stays** — §53 classified whole-scene
duplication as integrity, not craft; the gate refused nothing on the frontier arm, so
removing it saves nothing measurable, while a pinned provider still changes model
versions underneath a book and a never-firing deterministic gate is cheap insurance
(§24: a refusal costs time, never the unit). What dies is Stage 5's ordering and the
outline-as-duplication-fix justification, per §57. And **Add 2's acceptance is a wiring
pilot, not a test**: twenty-four frontier-arm scenes can show effect direction for
overdue-promise and zero-delta flags, and cannot show prediction at any confidence worth
recording — §57 already wrote down what happens when a run is sized for the wrong
question, and that entry does not need a sequel.

## 62. The serial-publication pillar measures out at two enum values, and both stay

Cut 5 of §61's programme, and the measurement that licenses it was taken in this pass
rather than inherited: PLAN §16 — a *pillar*, with a stage of the roadmap named after it —
has a total code footprint of **two inert vocabulary values**. `LockKind.PUBLISHED` is
enforced by `Node.with_content`/`tombstone` and round-trips through contracts 1.1, and
nothing in src/ ever sets it; `ExceptionKind.PUBLICATION_DECISION` mirrors the contracts
enum and has zero producers. There is no chapter-release unit, no hook placement (the only
"hook" in src/ is the word "webhook" in a docstring), no recap generation, no per-chapter
export, no publication policy object, no posting scheduler, and no publication table
anywhere in migrations 001–020. The pillar was prose.

**What was already true, ratified rather than built.** `litharness export` renders one
revision as Markdown or print-CSS HTML with derived front matter — exactly §16's "(export
only)" manual mode, in real use (exports/ holds two rendered books). Publication is that
export, run when the book clears §1a.5's bar. Shipping on schedule is the opposite
gradient from quality (§61), and the retention bar that serialization was to feed was
struck with it.

**The cadence-economics half (§15).** The throughput framing — scenes-per-tick, a draft
in two weeks, "the binding constraint will be gate failure rates" — is retired as a goal
and had **zero code representation**: no scenes-per-day counter, no cadence target,
nothing to delete. §15's other half is measured record and stays load-bearing: the
per-invocation harness tax (measured 2026-08-12, re-measured §56.1), the budget ceilings,
`spend_on` — that is §4.2 gate 4 and §18, untouched.

**Kept, and worth naming so nothing sweeps them up later.** Both enum values (contract
vocabulary; deleting them breaks wire round-trips for a claim nobody is making);
`resolve_branch`, which lives in export.py but is imported by seven non-export CLI
commands; and the recap *measurements* — published-serial recap spans of 70–93 words are
the calibration datum behind `DUPLICATE_SPAN_WORDS`, which is quality machinery, not
publication machinery.

**PLAN edits, all in place with the superseded text visible:** §2's serial bullet, §15's
retirement note, §16 retitled retired-with-record, Stage 6 struck with its survivors
rehomed (backup drills and budget reviews to §19's playbook; calibration cadence to the
preference engine's operation). Stage 7's "provider failover" mention falls to Cut 2's
entry, not this one.

## 63. The cron armor comes off, and the loop keeps what a crash still needs

Cut 1 of §61's programme. §57 already drove a whole book from one process and noted the
loop "is also what a daemon does"; §10's own text concedes its endurance criterion was
"evidenced, not met" and measured state growth, never uptime. Every mechanism whose only
customer was the cron deployment is now gone — **net −1,103 lines** — and migration 021
drops the three tables that stored it.

**Removed, each with the cron premise that justified it.** The instance lease (leader
election among overlapping invocations; one process has nobody to lose the claim to).
Durable pause via the `control` table (an in-memory flag "is a comment" under cron;
Ctrl+C is the pause in a session — and the table's one key was never joined by the
others its comment reserved room for). The entire outbox *delivery* path — dispatcher,
JSONL sink with its fsync discipline, backoff constants, `--notify-file` — which carried
events to a consumer who was not looking at a terminal; the operator now is the
terminal, and the event log was always the durable half. Status-as-external-monitor:
the cadence-derived stalled check (hardcoded 4×300s), lease reporting, and the
exit-code-for-monitoring-scripts contract; `litharness status` survives demoted to an
operator glance (jobs, exceptions, digest, spend) that always exits 0. `last_tick`
lost its only caller with it and went too, per §51.1's promise-with-no-caller rule.
The week-scale endurance simulations shrink to 50-tick pins of the same properties.

**Kept, because a foreground session still crashes.** The events table (provenance —
the `INSERT OR IGNORE` on content-derived keys is the dedupe, and it survived the
outbox mint's removal untouched). Idempotent ticks (`tick_records`, §9) — replay
convergence is what makes kill-and-restart safe, and it is pinned by tests. The **job**
lease and its reclaim/requeue path — "who is working this unit" is a question a
suspended laptop session needs answered exactly as a crashed cron tick did; the
RUNNING→QUEUED edge exists only for that reclaim. Transient/parked attempt give-back
(§24 — an outage costs time, never the unit). The digest (the planner writes
`context_omitted` and `beats_enqueued` into it). `backup_to`. `reset_health` per tick,
which matters *more* in a resident process (§16's bug), and which Cut 2 re-prices.

**Two mechanics worth recording.** The architecture suite pins every test name this
ledger cites to an existing test — so the 50-tick bounded-growth pin keeps the week
test's name, with a docstring recording the demotion; the name is load-bearing for the
citation checker even though the magnitude changed, which is exactly the §-drift the
plan header warns about, recorded here so the name is never read as the old claim. And
`record_tick` keeps its `dispatched` column (the §9 KEEP list is inviolable); the
conductor passes 0, and the column is historical vocabulary now.

**The restart drill, stated as the operating model.** One process runs `litharness
tick` in a loop (or a shell loop does); killing it mid-job loses nothing — the expired
job lease is reclaimed, the replayed tick converges on its recorded decision, and
accepted work was committed atomically with its events. That is the §57 run's shape,
now the only shape.

## 64. One provider writes the book, and falling back is reclassified as a defect

Cut 2 of §61's programme. §1a.5 requires a frontier generator; §56.1 measured that the
frontier arm was already the unflagged default (`DEFAULT_ORDER` put `claude_code`
first, and every decision-log run needed `--prefer ollama` to *avoid* it); and the
plurality machinery's real production behaviour was a hazard dressed as resilience —
a mid-book fallback silently hands prose to a weaker model, which under the quality
goal is a defect, not a save. The registry is now **one pinned provider**
(`claude_code`, plus `FakeProvider` behind the explicit `LITHARNESS_FAKE_PAD_CHARS`
opt-in): `resolve` returns it healthy or raises `ProviderUnavailable`, the unit parks
or requeues on §24's terms, and the book is never degraded. Codex (the fallback tier)
and the Ollama adapter are deleted; `--prefer`/`--no-billing`/`--model` and their env
vars go with them. Skips dropped 8 → 2 because the sub-frontier live arms died with
their adapters.

**Three semantic changes worth their own record.**

- **The billing guard filters nothing now; it refuses.** `LITHARNESS_ENV=test` used to
  silently drop billed providers from the candidate list — a filter is a silent
  substitution, the exact shape this cut exists to kill. A billed provider reached in
  test mode now raises `BillingGuardViolation` *before* the health probe (the probe is
  itself a billed call), and the Stage-0 exit clause "test provably cannot reach a paid
  provider" holds by refusal instead of by filtering. A mis-wired test surfaces as a
  FAILED job naming the guard — a wiring defect is loud, not quietly rerouted.
- **The health cache goes asymmetric, closing §56.2's open cost.** Positive verdicts
  now live for the process lifetime; `reset_health` clears only negatives. A resident
  session pays the unmetered ~$0.34 probe once instead of per tick, and one failed
  probe still cannot kill the provider for the process lifetime (§16's original bug).
  Full metering of the probe remains open; its cost is now bounded per session.
- **Cheap-call routing is deleted, and summaries move up a class.** Of the three
  `CHEAP_CALL_CLASSES` only `mechanical` ever had a wired producer (scene summaries).
  Those now route to the frontier provider and pay the measured harness tax — under
  the quality goal that is an *upgrade*, not a cost bug: summaries feed the context
  packet the next scene is drafted from, and a weak summary degrades frontier prose
  from upstream. `call_class` survives on requests as provenance; the routing is what
  died.

**Kept, deliberately.** The sampler machinery (`draft_sampler`, `_SEED_MODULUS`,
profiles) — inert on the pinned provider, which drops sampler and token caps entirely
(measured; the per-attempt retry ladder was always Ollama-only), but load-bearing for
replay-to-same-prose digests and FakeProvider determinism; removing it would churn
recorded policy digests to delete dead weight. `PROVIDER_FELL_BACK` stays as
historical vocabulary with its emission site removed — nothing can fall back, so
nothing may claim to. Provenance columns (`provider`, `model`, `fell_back_from`)
stay; historical rows naming `ollama`/`codex` project at `DEFAULT_TAX_TOKENS` now,
which errs high — the safe direction.

**Fallout accepted and recorded.** `research/progression-clause/ablate.py` imports
the deleted adapter and no longer runs — its research is concluded (§52/§56) and its
results are committed; the script is a record, not a tool.
`research/frontier-arm/duplication.py` calls the old registry signature and is fixed
by the roadmap entry that re-scopes it (Cut 6), since its new role needs the new CLI
shape anyway. `plan/provider-adapters.md` carries a superseded banner and stays as
the measured record (the harness-tax tables are still the cost model's basis).

## 65. The gate stays; the roadmap built on its defect does not

Cut 6 of §61's programme, landed as §61 amended it rather than as the directive drafted
it. The directive said remove the duplicate gate from the default ladder; §61 recorded
the refusal and this entry executes it: **the §53 gate stays.** §53 classified a copied
scene as an integrity defect, not a craft opinion — deterministic string arithmetic
needing no calibration — and the asymmetry has only sharpened since: the gate refused
nothing across both frontier books (§57), so removing it saves nothing measurable,
while §64 pinned the generator and made model-version drift the one silent way the
defect returns. A never-firing deterministic gate in front of a single point of drift
is insurance priced at zero (§24: a refusal costs time, never the unit). Nothing about
the gate, its 120-word threshold, or its two call sites changes.

**What dies is the ordering that §52's taxonomy dictated.** PLAN Stage 5's "in the
order Book Zero's taxonomy demands" is struck: that taxonomy was measured on
`phi4:14b`, its first entry does not reproduce on the generator §1a.5 requires, and
the outline's justification-by-duplication died in §57. The ordering source is now the
frontier arm's own defect taxonomy — which does not exist yet and is collected by the
pairwise engine and the structural instrumentation (§61 Adds 1–2): **the defects that
predict pairwise losses order Stage 5.** Until that data exists, no slice is scheduled
on taxonomy grounds; §56.4's context-packet arithmetic stands as the one
frontier-measured candidate.

**Narrative Planning is kept and demoted to unproven.** §57's own caveat holds — an
outline plausibly does other work than suppressing duplication — so the machinery
(outline handler, beat templates, `--no-outline` for hand-outlined books, the
directive lane) stays wired. Its *value* on the pinned generator is unmeasured, and
§57's demand is now the standing rule: no further planner machinery is built on it
until pairwise evidence re-argues it. §61 Add 3 is exactly that re-arguing — beat-plan
alternatives selected by pairwise judgment — so the outline's next justification will
be bought with verdicts or not at all. The §52-taxonomy argument threaded through
outline/beats/planner docstrings is left in place: each cites this ledger, the
scoping lives here (§57, this entry), and rewriting history out of docstrings is the
correction-in-place rule violated in the other direction.

**The span instrument gets a standing role and a trigger.**
`research/frontier-arm/duplication.py` is re-scoped from experiment to regression
harness: its question is answered, its instrument survives as the *below-threshold*
measurement the in-ladder gate cannot provide (the gate sees nothing under 120 words;
drift from 17 toward 93 is invisible to it). **Trigger: the pinned provider's model
identity changes** — model identity, not calendar time, because §64 made the
generator the only independent variable left. Its hand-mirrored CLI namespace had
already rotted against §63/§64 (four deleted flags) and is fixed to the shipped
shape, which is itself the argument for the script driving `cli._conductor` rather
than reconstructing the loop: what it measures is the shipped configuration.

## 66. The four refuted metrics leave the page, and the control that killed them keeps its referee

Cut 3 of §61's programme. BRIEF §2 Pass 2 is the license and has been for months: all
four instrumented metrics failed era-controlled AUC against ~13,000 published chapters
(0.445 / 0.455 / 0.461 / 0.528), and `tricolon_rate`'s 0.629 against pre-2023 prose —
the closest thing this project ever had to a working AI-tell detector — was exposed as
**year detection** by the 0.606 control beside it. They kept being computed per
accepted scene anyway, six annotation gates on every decision, because nothing had
spent the afternoon to stop them. Stopped: `measure()` now computes the two survivors
(`scene_echo.v1`, `repeated_span.v0` — repetition claims, §53-adjacent, deliberately
never refuted), and each accepted scene's decision carries two CRAFT annotations
instead of six. Decision digests change shape going forward; recorded history stands.

**Archived, not deleted, and the arithmetic is pinned.** The four functions, their
helpers, and the original `METRICS` tuple moved to
`research/quality-measurement/refuted_metrics.py`; the moved profile build tool
imports them from there; and the archive was verified to reproduce the shipped
arithmetic to four decimals before anything landed. `conversion_separation.py` — which
asks the four a *different*, still-open question — re-points at the archive and stays
runnable in the MirrorBench venv.

**What deliberately stays, because it is the referee, not the defendant.** The entire
population-calibration route (percentiles, bands, `MIN_BAND_CHAPTERS`, the committed
`plan/craft-profile.json`) is untouched. The profile's only contents are the four
refuted metrics, which makes it look like cargo — it is the opposite: it is the
committed evidence artifact behind the live test proving the tricolon threshold is
**refused by its own control**, and population calibrations key on metric-id strings,
so the proof outlives the functions. The next metrics to enter the craft table are
§61 Add 2's structural ones, and when they seek population anchors this is the
machinery that will refuse them the same way. The directive's standing rule takes
effect exactly as written: the craft table records only metrics with a live
calibration candidate.

## 67. The audit queue is a smoke check, and its draw is the engine's inheritance

Cut 7 of §61's programme, and mostly a ratification: the README already called the solo
audit queue "a confirmation sample, not the plan for measuring quality", and §1a.4's
amendment already carried the measurement that demoted it — **two verdicts against 104
exported pairs** is the throughput of judgment-by-sitting-down, and no rate parameter
fixes a design whose bottleneck is a human deciding to sit. What this entry adds is the
part worth keeping precise: the queue's *draw* is not demoted. Content-derived,
replay-convergent, non-re-rollable, auditable-after-the-fact — that sampling discipline
is exactly what §61 Add 1's pair draw must copy, so the demoted instrument's remaining
job is to keep the seam alive and measured.

**Three hygiene defects fixed while demoting, each a small lie left standing.**
`domain/audit.py` claimed an `--audit-rate` flag existed; none was ever built — no
parser defines it and production runs pinned at `DEFAULT_RATE`, which the comment now
says plainly. The module docstring called the queue "the highest-leverage part of the
craft programme"; superseded in place, record kept. And the on-acceptance draw — the
one production wiring of the whole feature — had **no end-to-end test at a nonzero
rate**: every prior pin exercised `draw` and the store directly, so the handler seam
(draw after commit, addressed by the committed revision, idempotent under replay) ran
only in production. It now has its own pin, which also demonstrates the replay
convergence the pairwise engine will inherit.

**PLAN §10.3's inversion is itself superseded, closing the loop §61 opened.** That
section declared revealed judgment the primary source on the strength of the same
2-of-104 measurement; the revealed labels then died on their own controls (§56.3,
craft-corpus §4.4). Both demotions were correct; neither instrument is primary. §10.3
and §10.5 now point at the pairwise engine, and the historical paragraphs stand as the
record of how the project walked here: unpaid solicited died on throughput, revealed
died on label validity, and what remains is the channel that was never funded — which
is §61's whole argument. Also swept: `--no-outline`'s help no longer frames the flag
as §54's control arm (that measurement concluded, §57/§65); it is the hand-outlining
flag now.

## 68. Cut 4 was already true, and this entry is the audit that proves it

Cut 4 of §61's programme — remove the sub-frontier support paths and fixtures — landed
with **zero tracked edits**, because §64's registry rewrite had absorbed every item:
the live extraction check already re-pointed at the frontier provider (the one thing
FakeProvider structurally cannot verify, kept alive because it caught the `{subject}`
placeholder defect); the capable-vs-small length contrast already deleted with its
concluded question; stub names already neutral; budget tests already keyed to `fake`;
the Sampler merge coverage already re-hosted model-free. Rather than assume, the pass
verified each item against the tree and swept for residue.

**The residue audit, which is the entry's real content.** A case-insensitive sweep of
src+tests for every retired model name found **twenty hits, nineteen of them
docstring/comment provenance** — measurement records for kept code (the Sampler
determinism numbers, the target-words phrasing rationale, `_SEED_MODULUS`'s 32-bit
seed origin, the codex health-probe lesson now shaping the kept health contract, the
duplicate-paragraph run behind `repeated_span`) — each pointing at its canonical home
in this ledger, per the house rule that history is corrected in place, never scrubbed.
The **one executable mention** is deliberate and pinned: `test_budget` asserts the
retired provider names now project at `DEFAULT_TAX_TOKENS` — historical decision rows
name `ollama`/`codex`, and the safe-direction shift (they project *high* now) is
exactly the property worth a test. Replacing those strings would unpin it.

**What this entry is for.** §52 and §56 answered the sub-frontier arms' questions
(872-word verbatim runs; 49-of-49 ledger copies); their research is concluded, results
committed, scripts frozen as records. The maintenance burden the directive named is
measured at zero remaining paths. A cut that finds itself already landed still gets
its entry, because the alternative is a programme item that quietly never happened —
and the audit that distinguishes "done" from "assumed done" is cheap exactly once.

## 69. The preference engine lands, and the first thing it judged was itself

§61 Add 1 — the evidence source, and the first subsystem aimed directly at the goal.
Blinded, position-swapped pairwise judgment at scene grain: system vs matched
published-human excerpts and system vs system, content-addressed end to end in the
§10.5 draw's discipline — no RNG anywhere; pair identity from the unordered pair,
orientation a content-derived bit, both presentations minted as sibling rows so
positional consistency is *measurable*, not assumed away. Protocols are pre-registered
records (comparator frame, tie policy, grain) that refuse redeclaration by
construction, because **the frame is the claim** (§61); the win-rate bound is a
two-way cluster bootstrap over readers × pairs (§58's addendum extended a dimension),
seeded from the judgment-set digest, refused below two clusters of either kind.
`EvidenceClass.PREFERENCE` joins the promotion machinery with `veto_for` deliberately
refusing it a veto: preference evidence licenses *selection between candidates*
(§61 Add 3), never absolute refusal of one text, and the total-raise enforces that
with zero code. Eight CLI verbs; migration 022; the production loop is untouched at
zero verdicts — judgment gates promotions, never ticks. Operated per
plan/preference-runbook.md; acceptance stands as §61 wrote it: a §59-promotable row
within one month of funded operation, or this entry gets the sequel every dead
instrument got.

**Building it found two latent defects in the machinery that was already trusted.**
`cmd_calibrations` passed the answered-audit digest to every evidence class, so
POPULATION rows listed as falsely stale against a digest they never claimed — the
per-class dispatch that §58's fix installed in the ladder and `cmd_calibrate` had
never reached the listing verb. And `_craft_ladder` passed the audit-queue count as
`answered` for every class — the exact wrong-population defect BRIEF §6 question 1
warns about, one table over. Both fixed with per-class dicts beside the digests.

**Then the engine was adversarially reviewed before it was trusted, which is the
point of having promotion rules at all.** An independent pass re-derived the
orientation mapping, the system-side attribution, and the bootstrap from first
principles — different resampler, different RNG, 100k replicates — and reproduced
every pinned value, so the tests do not share a bug with the module. What it found
was at the seams, and all of it landed before this entry: **recognition was
bypassable by omission** at the paid-reader import (absent field defaulted to "not
recognized" — the §58 exclusion structurally skippable exactly where the headline
evidence enters; import now refuses any entry without an explicit boolean, and the
judge verb demands yes/no); **positional balance was unmeasured** (addresses sort
`exc:` before `rev:`, so orientation is confounded with side for every mixed pair;
win-rate now reports per-orientation counts and rates, refuses the bound when all
decisive judgments share one presented order, and warns past 2:1); the bootstrap
quantile rank was **anti-conservative by one position** (fixed to the ceil
convention; two DROP-policy pins moved, 0.35 → 1/3 and 0.25 → 0.2, recorded in the
test as the correction landing); and the NUL-join pair-id ambiguity, reachable only
by abandoning constructor discipline, is now unrepresentable rather than unreached.

**Recorded honestly rather than fixed, with the measurement that says why.** The
percentile cluster bootstrap under-covers at small cluster counts — 2×2 all-wins
prints a "97.5% lower bound" of 1.0, which no calibrated interval can — so the CLI
prints a descriptive-bound caveat below five clusters per dimension and the docstring
carries the measurement; the promotion floors are the real gate, and an estimator
upgrade (basic/BCa) is future work that must not move the bar silently. Chapter grain
is a refusal with a reason, not a feature: production books hold no chapter nodes and
inventing an assembly scheme mid-build is exactly what the spec forbade; the enum and
schema carry the grain so no future migration is needed. And the analysable-judgment
count for PREFERENCE holdouts excludes abstentions and recognized rows while
deliberately pooling protocols — the digest pools too, and over-invalidation is the
safe direction.

## 70. The reader question was never asked, so it is untested rather than dead

The instrument: a system-prompted model held in a reader persona, asked what reading a
passage was *like* rather than how to improve it, answering in the audit queue's own
`--keep-reading` / `--would-stop` / `--not-sure` vocabulary. This entry is the licensing
argument and the four corrections the record forces; the protocol is
[plan/persona-reader-validity.md](persona-reader-validity.md). **Nothing is promoted here and
no gate changes.** What lands is a pre-registered validity program with kill conditions, in
the shape §61 used for every other channel.

**Why this is not just another candidate proxy, stated against the ledger rather than
asserted.** Every refutation on the books bounds a different instrument than this one.
BRIEF.md §2's twenty-one dead proxies are deterministic and correlational (§3's diagnosis:
static, absolute, correlational). Pass 4's model judges were asked to *improve* prose and
made it worse — an expert-frame revision result, which is why the architecture is
`detect → scoped repair → verify`. Pass 6's CDG read a log-probability distribution, not a
report. Pass 3 died on archive capture date; Pass 2 detected the year. **No pass in the
record asked a model, in character as a reader, what the passage did to it.** BRIEF §3's
status note is careful about which doors it closed, and it closed the surprisal door and the
RoyalRoad within-story door — not this one. So the honest classification is *untested*, and
in this project untested means a validity study with pre-registered kill conditions, never a
feature build.

**The reframe that makes it tractable, and it settles three design arguments at once.** A
persona reader is a **predictor, not a witness**. Whether its report is faithful to any
internal state is out of scope by construction; the only target is report–population
agreement against human reader responses on held-out material. So the datum is a
*distribution* and aggregation is distribution-matching, never averaging; "is this persona
realistic" is unaskable and "is this persona calibrated" replaces it; and every known failure
mode of persona prompting converts into a pre-registerable control rather than a worry —
caricature, collapse-to-one-judge, positivity floor, knowledge leak, demand characteristics,
and reason confabulation each get a row in the protocol's kill table.

**One consistency argument in its favour, because it is a port rather than an invention.**
This project already made exactly this choice on the human side: the audit vocabulary is
keep-reading/would-stop deliberately, "§1a.5's bar rather than a rubric". Pointing the same
question at a model puts instrument and ground truth in one vocabulary by construction, which
is what makes gate 2's agreement computable without a mapping layer. Borrowing the words
borrows none of the standing — §67 demoted that queue to a smoke check.

**Four corrections to the directive as drafted, accepted before anything lands.**

**(1) The memorisation fork, which changes the shape rather than a detail.** BRIEF §2 Pass 6's
transferable rule is that a model-based measure validated on published fiction either runs on
text the model provably has not memorised or measures its familiarity term explicitly — the
rename sham moved CDG **2.0× further than the strongest real degrader**, upward and
dose-monotone, while real damage sat at chance. A persona validated on published serials sits
in that trap. So gates 0–1 run on this system's own generated prose (`research/frontier-arm/`),
which BRIEF §3 names as the one remaining untried direction *and* prices in the same
sentence — no published-reader label reaches it, which is exactly why sensitivity cannot be
the last gate. Gates 2–3 run on published material with a persona-facing **recognition probe**
recorded as a covariate: §61's pre-registration (3) and the preference runbook's recognition
question, pointed at the model.

**(2) A gate 0 the record demands and the directive omitted.** Pass 5 earned "check
within-unit reliability before believing any per-unit statistic" and tree-Haar died to it at
`ICC(1) = 0.270`, within-book sd equal to between-book sd. The directive's own `n ≥ 5`
samples per persona per boundary makes ICC computable here for the first time, so it becomes
the first gate: a panel whose within-boundary variance matches its between-boundary variance
is noise wearing a verdict, and that is the cheapest available kill.

**(3) `UntrustedVerdict` is unnecessary, and the mechanism already in the tree is better.**
`EvidenceClass` is a total dispatcher and `veto_for` raises `NotPromotable` for any class it
does not map, so a new member absent from `veto_for` **licenses no refusal with zero code** —
precisely how `PREFERENCE` landed (§69). A parallel wrapper type would duplicate a guarantee
the enum already provides by construction. It lands when gate 3 passes and not before: a row
that cannot yet be earned is not a row. **And the ceiling the directive did not state:**
`JUDGMENT` is *a human's answer about one of our units* and the only class that may say a
scene is not good enough, so a persona panel can never be a `JUDGMENT` row however well it
calibrates. Validated, it earns selection between candidates and advisory annotation, never
absolute refusal — the same ceiling §61 Add 3 put on preference.

**(4) Distance is a threat to this design specifically, and the closed design left the
number.** feasibility.md §4.3 measured an interventional effect on a model-based readout
decaying to nothing with distance: real − placebo `+0.2615` at gap 0 (12/12, p = 0.0005),
`+0.0608` at 256 tokens (11/12, p = 0.0063), `+0.0102` at 512 tokens (8/12, **p = 0.388**). A
persona reporting at a scene boundary is routinely further from a manipulation than 512
tokens, so manipulation position is a declared covariate and the decay curve is reported. It
also hands the program a control it would not otherwise have had: sensitivity that decays on
*the same curve* as a log-probability readout is a surface-locality measure in a costume,
while a flinch that survives 512+ tokens is something the closed design could not reach.

**What is reused rather than built, which is most of the sensitivity arm.**
`research/quality-measurement/ablate.py` already implements `rename_entities` and `respell` as
pre-registered shams with within-chapter paired AUC and a chapter-resampled bootstrap CI, and
`evaluate.verdict()` already carries the whole pass/fail ladder — `detect < 0.55`, then
`margin = (detect − 0.5) − |sham − 0.5| < 0.05` read per sham and never as `detect − sham`
(the subtraction reported `+0.2342` on the battery whose sham effect was the largest in the
table), then §1a.1's word-count incumbent, then the paired interval. **So the panel inherits
the rung that actually finished CDG**: word count separated that variant pool at 0.5229
against CDG's 0.5188, and a persona panel that cannot out-separate a word count is an
expensive word count. Gate 1 is a new elicitation front-end on a burned-in battery — no new
pass/fail arithmetic — which makes the placebo arm close to free, and it is not optional,
because the ledger already contains an instrument that died to renames.

**What this entry changes elsewhere: nothing.** PLAN.md's bar is untouched — §1a.5 still
carries the superiority bar and this program is not evidence against or for it. No metric
id, no enum member, no migration, no CLI verb. §61's four-channel table gains a fifth row
only when a gate reports: *persona-reader elicitation — program pre-registered, unmeasured*.

**What it licenses, and the sequencing is the argument for doing it now.** Gates 0 and 1 are
model-only and fundable today; they compete for no money with the preference engine whose
first funded month is already §61's kill-switch. The two gates most likely to kill the
program are the two that need no budget, and a clause that fails there costs nothing but the
entry recording it — which, on this project's record, is the normal outcome and the reason
the gates are ordered this way.

**Addendum: the instrument is built, and two of its parts were wrong on first inspection.**
`research/quality-measurement/personas.py` (four taste-anchored readers, held-out anchors as the
fidelity and drift probe), `elicit.py` (two-stage elicitation, stage 2 constrained by
`output_config.format`, digest-keyed replay cache, refusals recorded as refusals) and
`persona_battery.py` (gate 0's ICC, gate 1 through `evaluate.verdict()`, the pre-registered kill
conditions with the collapse threshold's null simulated at the run's own n). `corpus_io.
generated_scenes` reads drafted scenes straight out of a book database through
`application/export.collect`, which is what makes the un-memorised arm of correction (1) runnable
rather than aspirational. No metric id, no enum member, no migration, no CLI verb; `anthropic`
enters as an optional `persona` extra that nothing in `src/` imports. Suite green at 784.

**§5's manipulation set is now partly discharged, by a construction whose control is the claim.**
`ablate.destake` deletes the sentences that assert what failure costs; `ablate.deplete_matched`
deletes the *same word count* — verified exact — from sentences that assert none. The difference
between the two arms is the effect of removing stakes with length, position and quantity of
deletion held fixed, and it is the only number in that summary that speaks to the reader
hypothesis: if they move the panel equally, the lexicon selected nothing and de-stake is deletion
wearing a name. `rewhitespace` completes the placebo pair. All three are kept out of `ablate.ALL`
and reached through a new `ablations=` parameter, so §58's recorded battery still schedules exactly
the variants it scored. **Filler-inject and confusion-inject stay unbuilt** — a confusion
injection has to know what a passage's referents are, and the only thing that knows is a
generator, which `dialogue_flatten`'s docstring already refused to admit to this ground truth.

**The two defects are worth the space because both are the ledger's own recurring shape.** The
stake lexicon's first version scored *"the shrill whistle of the incoming train broke him out of
his concentration"* as the most stake-bearing sentence in a Mother of Learning chapter — `broke`
matching figuratively — and three of its next four hits were selected by `finally` and `last`
alone. A membership test had quietly selected a grammatical category nobody meant, which is
`rename_entities`'s stopword bug one function over. Fixed by pruning the polysemous cost words and
demoting finality to an amplifier that cannot open a score. And the summary's `passage_source`
was a chained conditional ending in `else "published"`, so `--book-db` fell through it and a run on
this system's own prose recorded itself as having scored the memorised corpus — the warning was
keyed separately and stayed right, so nothing failed and the record simply described a different
experiment. Both were found by printing what the code selected rather than by reading it.

**Addendum 2: gate 0 has been run, and it is not passed — the corpus could not support it.** 246
calls of `claude-haiku-4-5` through `claude -p` (the local install's own authentication, so
subscription quota rather than an API key; $3.81 equivalent, 22 minutes), 4 personas x 5 samples
over the six golden fixture scenes, un-memorised and 103–166 words each. Pooled `ICC(1)` came back
**0.489**, comfortably above the 0.270 that killed tree-Haar — and the number is an artifact.
**Five of the six passages produced zero would-stop across every persona and every sample; all
nine stops came from scene 6.** So the between-group variance the ICC is made of is one passage
differing from five identical ones, which is a step function wearing a reliability estimate. The
per-persona breakdown says the same thing louder: `voice` never once said would-stop in thirty
samples (zero variance everywhere, ICC undefined), `newcomer` scored exactly 1.0 on zero
within-passage variance, `stakes` sat at 0.103, and only `grinder` at 0.485 looks like a reader
with signal. The would-stop base rate over the whole run is **0.078**.

**Two things did work, and one of them is a method rule paying out.** The caricature condition
passes cleanly — passage sum-of-squares 0.713 against persona 0.094, a ratio of 0.13, so the
response tracks the text about seven times harder than it tracks the costume, which is the single
most encouraging number the program has produced. And the collapse condition returned an observed
mean inter-persona rank correlation of **1.0** — which, read against the pre-registered 0.9
threshold alone, says "one judge in costumes, kill the panel". Its simulated null at this run's
own dimensions also reaches **1.0** at the 95th percentile: with six passages and a 0.078 base
rate, independent personas produce identical all-zero rankings by chance constantly, so the
statistic has no power here and the observed value carries no information. Pass 5's "simulate the
null at your own n" is the only reason that was visible rather than acted on, and this entry is
what that rule bought.

**Scene 6 is the mystery's confession-and-arrest — its ending — which makes the one signal in the
run the most suspicious thing in it.** A reader handed the final scene of a story out of context
has an obvious reason to say "would stop" that has nothing to do with craft. The next run does not
need more samples; it needs passages long enough and mid-book enough for stopping to mean
something, which is what `corpus_io.generated_scenes` and `--book-db` exist to supply.

**And the fidelity probe was broken by construction, which the run exposed on its first four
calls.** Held-out anchors were withheld from the system prompt entirely, so the probe asked each
persona about books the prompt had never said it read — and three of four answered, correctly and
fatally, "I haven't actually read these books." A model's whole reading history *is* its prompt,
so holding out the title holds out the premise, and the probe was measuring willingness to
confabulate rather than stability of taste. Fixed by naming held-out titles with their verdicts
withheld. Retested live, the mechanism still cannot separate three different failures: `grinder`
refuses the frame outright, `voice` answered *correctly and in register* — "Cradle: not-sure, the
voice flattens out", matching its held-out anchor — but in prose rather than JSON and scored zero,
and only `stakes` and `newcomer` produced parseable verdicts to actually disagree with. **A gate
that drops personas cannot be allowed to conflate "wouldn't answer", "answered in the wrong
format" and "answered differently".** That is the transport's missing structured-output guarantee
reaching a decision it should never touch, and it is the next thing to fix.


**Addendum 3: the panel is a constant function, and the response variable is why.** Gate 0 re-run
on the substrate the fixtures could not provide — ten drafted scenes of "The Toll Road", ~1,000
words each, generated on the pinned provider and un-memorised by construction. 412 calls, 39
minutes, $12.86 equivalent. The result needs no interval: **195 of 196 scored verdicts were
`keep-reading`, one was `not-sure`, and not one was `would-stop`.** The six frontier spot checks
returned `keep-reading` as well, so this is not the cheap tier being agreeable. Of the closed
reason-code set, only the four positive codes were ever drawn — `stakes-real` 136, `voice-landed`
37, `curious` 18, `pulled-forward` 5 — and none of the seven stop codes was used once.

**Every kill condition came back undefined rather than passed, which is the honest reading.**
`ms_between` and `ms_within` are both exactly 0.0, so `ICC(1)` is `nan` pooled and `nan` for all
four personas; the caricature ratio is `inf` over two zero terms; every inter-persona pair is
undefined. A statistic cannot decompose variance that does not exist. The one condition that
*fires* is the positivity floor: §8 pre-registered "would-stop base rate ≈ 0 ⇒ dead as a stop
predictor", and 0.000 over 196 draws across ten passages and two model tiers is that condition
without ambiguity. **Gate 1 is unrunnable against this response variable** — a constant scalar
gives `detect_auc` 0.5 by construction, and no manipulation, however severe, can move it.

**What died is the absolute judgment, not the reader question — and this project already learned
that distinction once.** §61's channel table records raw model judges dying to 43–65% positional
artifacts, and the answer that programme reached for was not a better rating scale: it was
blinded, position-swapped **pairwise** comparison, which is what §69 built and what
`plan/preference-runbook.md` operates. §1a.5 words this project's own bar in revealed terms for
the same reason. The persona panel was handed the audit queue's three-way vocabulary — designed
for whole-unit judgment with an accumulated book behind it — and asked to apply it to a single
mid-book scene in isolation. A reader four scenes into a book does not abandon it because one
scene was ordinary. The question is real; the frame gave it no room to vary, and 196 draws is
enough to say so.

**The redirection the ledger's own history implies is to ask the panel to compare rather than to
rate**, and it is cheaper than what it replaces: present the original and a manipulated variant
blinded and position-swapped, ask which one the persona would rather keep reading, and the answer
varies by construction. It inherits §69's machinery — per-reader positional consistency, the
declared tie policy, the clustered bound — costs one call per comparison instead of a twenty-cell
panel per variant, and needs no two-stage protocol, since a forced choice cannot plant a category
the way an unprimed-then-forced sequence was built to avoid. It also lands exactly where §70's
integration note already put the ceiling: a persona panel can never be a `JUDGMENT` row and can at
most earn selection-between-candidates standing, so **the measurement should have been pairwise
from the start, because pairwise standing is the only standing it could ever earn.**

**Cost of learning this: about $16.70 across both gate-0 runs**, and the cheap death is the point —
the instrument was killed by its own pre-registered condition before any human money was spent,
which is what the gate ordering in §61 and the protocol's §4 exist to produce. Two implementation
findings ride along, both recorded because they would bite the pairwise design too. The `claude -p`
transport silently drops `max_tokens` — it has no such flag — so mean output ran to 1,928 tokens
per call on long passages against a stage-1 cap of 350, which is a third of the spend and a signal
that the persona was writing in essay register rather than reader register. And persona adherence
does not track model size: `gemma3:4b` answers in first-person reader register where `phi4`,
nearly three times its size, returns "This passage conveys a gritty, almost oppressive atmosphere"
— the critic frame §1a.2 refuted. `elicit.probe_adherence` makes that a four-call precondition.


**Addendum 4: the pairwise instrument clears the ladder and fails the claim it was built to test.**
Three runs over the same ten drafted scenes at full dose, one comparison per persona per
orientation, ties on `half_win`:

    question     model            ties   detect    sham   margin   chose-A   verdict
    preference   claude-haiku-4-5  0.18   0.9056  0.7833   0.1223    0.5874   SURVIVES this rung
    intensity    gemma3:4b         0.98   0.5340  0.4750   0.0090    0.8095   DEAD
    preference   gemma3:4b         0.57   0.4667  0.4250  -0.1083    0.8021   DEAD

**The two local rows say nothing about the questions, because the panel failed the condition
that is read first.** `gemma3:4b` chose position A on 80.2% of decided preference comparisons
(z = +11.9) and 81.0% of intensity ones. §8's pairwise table puts that condition above all
others for exactly this reason: a panel answering a *side* has reported on layout, and no
preference it states means anything. So the capability floor for this task sits above 4B, the
free local path is not available at that size, and **the intensity question remains untested on a
competent panel** — the one cell of the 2×2 still missing. What the local rows do establish is
that `probe_adherence` was necessary and not sufficient: the same model writes first-person
reader prose beautifully and then answers a closed-enum comparison by position.
`elicit.probe_discrimination` is the precondition that would have caught it in eight calls
against `transplant` at full dose, and a resolution floor is now read before a panel is trusted.

**The one interpretable run separates strongly and for the wrong reason.** Preference on Haiku
reaches detect 0.9056 against sham 0.7833, so the margin rule passes at 0.1223 — but a sham
response of 0.78 means the panel is separating *edited-ness* nearly as hard as damage, which is
the `change-detector` shape `evaluate.selftest` keeps an oracle for. Its own positional bias is
0.5874 (z = +4.73), so a real share of the answer is still layout. And `transplant` — a
length-matched graft from a different story, the strongest degrader available — comes back at
−0.0125 with a hit rate of 0.3, while `sentence_deletion` reaches −0.5. A panel that misses a
foreign story and reliably notices missing sentences is not reading for content.

**The pre-registered primary comparison fails, with the sign reversed.** §5 named one arm in
advance as carrying the reader claim: de-stake against its matched-deletion control, same word
count removed, differing only in which sentences went. Measured: `destake` −0.3503,
`deplete_matched` −0.4375, difference **+0.0872**. Under `direction = -1` the more negative arm is
the more damaging one, so **removing arbitrary neutral sentences hurt more than removing the
sentences that assert what failure costs.** The stake lexicon selected material whose removal
mattered *less* than a random sample of the same size. That is the reader-specific hypothesis
unsupported, by the comparison declared before the data precisely so this could not be argued
afterwards. `dose_rho` is `nan` on every arm because the screen ran a single dose, so §5's
monotonicity claim is untested rather than failed.

**A parser had been selecting the evidence, and it inverted a verdict.** `_strip_fence` was
applied when a record was written rather than when it was read, and `claude -p` answers with the
JSON object followed by a stray fence and prose commentary. 370 of 512 pair records were dropped
as unparseable — not refused, not malformed, merely suffixed. The loss was selective: the
surviving subset showed chose-A 0.680 against 0.551 for the recovered records, and on that subset
the run read detect 0.7125, sham 0.6833, margin 0.029, **DEAD on rung 2**. On the full 904 it
reads SURVIVES. Both numbers came from the same calls; only the parser differed. Parsing now runs
through the extractor at every read site, because stripping at write time cannot repair a cache
already written, and the record kept the raw text throughout — which is the only reason this was
recoverable at zero cost.

**Standing after three runs: the absolute form is dead, the pairwise form is not yet a reader.**
It discriminates, which the absolute form never did; it discriminates largely on edited-ness; and
the arm that would have made it reader-specific ran backwards. Nothing here licenses a row, and
§70's ceiling is unchanged.

## 71. The book now owes things on the record, and a scene that changes nothing says so

§61 Add 2 — the first instrumentation aimed at PLAN §1a.3's items 1 and 3, the ones
BRIEF §1 says nothing had ever touched. Two shapes, both advisory, both riding the
existing machinery rather than growing new call sites: the per-scene summary call —
already made, already provenance-stamped — now also answers three questions (the
scene's value shift: *what changed for whom*; promises opened; promises paid), and a
`promises` table turns the answers into a ledger with a due position per thread.
The overdue check is deterministic arithmetic over those rows
(`promise.overdue.v0`, category PROMISE_PAYOFF — the contract already had the word;
both golden fixtures already ship an example), appended to `IN_PROCESS` at MINOR +
heuristic, belt and braces so neither severity nor basis can ever block or park: §61
said advisory until calibrated, and the promotion rules are how that changes, not a
severity edit. A summary whose delta comes back empty mints `craft.scene_delta.v0`
at INFO — "no extractable value shift; dramatic_function unverified" — which is
`scene_change_profile`'s refutation honoured in design: ledger delta is not dramatic
delta (the confession scene carried zero records), so the delta question goes to the
model leg and its answer stays a hypothesis about human judgment until Add 1's data
says otherwise.

**The design is §46 arriving where it was always going.** A payoff-due position is a
record that informs and contaminates nothing; generation *sees* the debt — open
promises pack into the context packet's THREADS section as "owes: … (due by sNN)" —
and §55.1's measured lesson governed the prompt wording: the delta question is asked
unhedged, because the hedged progression clause was the documented stasis default.
Three map traps dictated the separate table and are recorded in migration 023's
header: `open_threads`' exact-equality contract, the contradiction detector's
(subject, predicate, order_key) grouping, and `has_story_vocabulary`'s registry
filter. `promise_id` derives from (book, subject) and is deliberately
value-insensitive — reopening the same debt converges — with the docstring
contrasting `record_id_for`'s opposite, equally deliberate, discipline.

**Recorded limits, none hidden.** Two branches of one book collide on `promise_id`
(single-branch reality today; the entry the branching feature writes must revisit).
A payoff summarised before its opener's summary is a silent no-op pay — write-once
by design, visible in pilot output. The evaluation lane's `checked_rule_ids`
deliberately excludes the overdue rule: that lane assembles no promise input, and
claiming a check that never ran is the §53 defect in reverse. And the acceptance
run stays a **wiring pilot** (`research/structural-instrumentation/pilot.py`,
written and not executed — it spends live quota, and its `--reset` must run on a
copy): twenty-four frontier scenes can show effect direction for overdue-promise
and zero-delta flags against Add 1's coming pairwise data, and cannot show
prediction at any confidence worth recording. §57 already wrote that entry once.

## 72. Selection pressure arrives at the plan level, and its license expires on use

§61 Add 3 — the loop that could exceed the baseline, re-founding Narrative Planning on
measured ground as §57 demanded. Under `--plan-search`: **one** structured call asks
for K structurally distinct beat-plan statements for a span (instructed distinctness
gated deterministically — sampler variation is not a diversity mechanism on a provider
that drops samplers, §64); each alternative is drafted and run through the *pure*
gates off one frozen base; survivors persist as `span_candidates` (migration 024) and
their sibling pairs — all C(K,2), both orientations, the internal protocol — enter the
preference engine. Losers **never** reach `commit_revision`: §21 is preserved by
construction (`gate_draft` returns un-persisted revisions) and pinned by a
history-untouched test, then *extended* — a book with candidates awaiting selection is
its own draft in flight, and drafting pauses on that book (not the queue) so a
cross-span commit cannot systematically invalidate paid tournaments. The whole
tournament is budget-projected at K+1 calls before the first one; the winner commits
through the full ladder and ONE `accept_plan_proposal` (one epoch bump; the
queued-work cancel filter now names all three plan-derived job kinds — the map's
hardcoded-filter trap, closed and tested).

**Two selection paths, one license.** The human path parks the span until every
sibling pair is answered in **both orientations** — the stricter reading, because a
one-sided answer is RevisionBench's positional artifact unmeasured — then selects by
canonical win count with a content-derived tie-break (a tournament the readers cannot
separate resolves by a *repeatable* arbitrary choice, stated in the code rather than
hidden). The judge path ships **dormant**: it opens only when a current
PREFERENCE-class calibration exists for `judge.span_select.v0` — calibration on the
selection task itself, per §6.6's rejection-sampling argument, never passive flag
precision — and judge verdicts are recorded through the same pair machinery with the
calibration id as reader provenance. And the license behaves exactly as the machinery
promised: **judge verdicts move the answered-verdict digest and stale the calibration
that licensed them** — one calibration buys roughly one judged tournament before
re-measurement. That is not a defect; that is §6.6 arriving as an operational fact,
and it prices what "current evidence" costs when evidence is consumed by selection.

**A comparator-frame near-miss, caught in the build.** Candidates ride the corpus
table (Add 1's candidates-as-corpus sibling mechanism), and the external pair draw
originally saw *all* excerpts — which would have put this system's own prose on the
published-human side of the superiority frame. Tournament-sourced excerpts are now
excluded from external draws by source prefix, with a test. A headline claim that
quietly compared the system to itself would have been the most expensive kind of
wrong.

**The repair generalization is one predicate.** `repair_job_for` licenses a scoped
repair from a span-carrying finding that is (blocking AND deterministic) — unchanged —
OR cites a **current** calibration whose evidence class holds a veto (JUDGMENT,
POPULATION). PREFERENCE is refused by the same `veto_for` raise that keeps it off
blocking gates: preference evidence selects between candidates; it never licenses
touching prose. Freeform revision stays structurally impossible (§1a.2); the patch is
still span-scoped and licensed by a named finding.

**Recorded judgments, not silences.** Refused candidates land as non-blocking failing
gates on the tournament's settlement decision rather than as rows or standing findings
— a loser's defect made standing would park the *winner's* commit. Director-locked
scene plans draft the ordinary way (a tournament must not overwrite the director's
word, and skipping would stall the book). A sole survivor selects immediately with
deterministic attribution. Two parks are operator-recoverable rather than
self-healing (`replan`/`revive`), and `_settle`'s attempt-ceiling poisoning of a
parked tournament is noted as a degraded record with the readiness scan as the reason
it stays harmless. Acceptance stands as §61 wrote it, runbook at
`research/plan-search/RUNBOOK.md`: a K=3 search book beats a no-search book in
blinded pairwise at n≥50, or this ledger records that it didn't.
