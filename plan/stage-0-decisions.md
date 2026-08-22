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
(389 decided, z = +11.9) and 81.0% of intensity ones — but that second rate rests on **21
decided comparisons**, because the ties column above is not a rounding artifact: the model
answered `neither` to 98% of the intensity pairs. Its intensity row is therefore refused twice
over, once for bias and once for having almost no data under the bias, and the more useful
reading of that cell is that a 4B model asked which passage *hit harder* declines to answer at
all. §8's pairwise table puts the bias condition above all
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

**And the pattern across arms says what the panel is actually reading: local coherence.** Length
was the first suspect and it does not carry the result — Spearman between absolute word-count
change and damage detected is +0.321 over nine arms, which at that n is nothing. The informative
comparison is between arms that change no length at all:

    arm                   length      detected
    sentence_deletion     -52.9%      -0.5000
    connective_scramble     0.0%      -0.4714
    sentence_shuffle        0.0%      -0.3750
    paragraph_shuffle       0.0%      -0.3554
    dialogue_flatten        0.0%      -0.2045
    transplant              0.0%      -0.0125

Four transformations that touch not one word of length, spread from -0.47 to -0.01. What
separates them is **whether the damage is local**. Connective inversion wrecks argument structure
a clause at a time; the shuffles make the text locally incoherent; deletion leaves holes.
`transplant` grafts a length-matched run from a *different story* — and the graft itself reads
perfectly well, it simply does not belong. The panel is near-blind to it.

**That single contrast explains the de-stake failure too.** De-stake removes whole sentences
selected for meaning and leaves the remainder locally smooth; `deplete_matched` removes the same
word count at random, which is far likelier to strand a pronoun or sever a clause from its
referent. Matched deletion hurt more because it broke more *local* coherence, not because it
removed more that mattered. The primary comparison ran backwards for a reason, and the reason is
that the instrument is not reading at the scale the hypothesis is about.

**This is feasibility.md §4.3's distance decay arriving through a different door.** That study
measured an interventional effect on a model-based readout falling to nothing by 512 tokens; a
panel that catches a scrambled connective and misses a foreign story is the same locality, stated
in reader vocabulary instead of log-probabilities. It also yields a falsifiable prediction for the
next run, recorded before it: a manipulation that damages global structure while preserving local
coherence — swapping whole scenes between books, reordering a chapter's scenes — should come back
near-null like `transplant`, and one that damages local coherence while preserving meaning should
come back strong. If that fails, this reading is wrong and the transplant null needs another
explanation.

**Standing after three runs: the absolute form is dead, the pairwise form is not yet a reader.**
It discriminates, which the absolute form never did; it discriminates largely on edited-ness; and
the arm that would have made it reader-specific ran backwards. Nothing here licenses a row, and
§70's ceiling is unchanged.

**Addendum 5: the 2x2 closes, and the question matters more than the costume.** The missing
cell ran on 2026-08-18 — intensity on `claude-haiku-4-5`, 904 calls, 184.7 minutes, 13 refused.

    question     model            detect    sham   margin   chose-A   destake vs deplete_matched
    preference   claude-haiku-4-5  0.9056  0.7833   0.1223    0.5874   -0.3503 vs -0.4375  BACKWARDS
    intensity    claude-haiku-4-5  0.8514  0.6833   0.1681    0.6111   -0.3750 vs -0.3589  as predicted
    preference   gemma3:4b         0.4667  0.4250  -0.1083    0.8021   void on bias
    intensity    gemma3:4b         0.5340  0.4750   0.0090    0.8095   void on bias, 21 decided

**Intensity is the better question and it was not the one the protocol led with.** It detects
less (0.8514 against 0.9056) and that is the *point*: its sham is 0.6833 rather than 0.7833, so
less of what it separates is edited-ness, and the margin is wider at 0.1681. Most of all, the
pre-registered stakes arm — which ran backwards on preference and cost that run its central
claim — runs in the predicted direction here. `destake` -0.3750 against `deplete_matched`
-0.3589 is the right sign, though the gap is +0.0161 at n=10 and is not on its own a result.

**`transplant` replicates the §5a blindness independently**: -0.05 with a hit rate of 0.4,
against -0.0125 on preference. Two questions, two runs, the same near-null on a length-matched
graft from a foreign story. The scope limit is not an artifact of one question.

Positional bias is 0.6111, marginally outside the 0.40-0.60 band §74 later pre-registered, so
this cell is read as suggestive rather than clean under that rule.

**And the costume does nothing, which is measured rather than assumed.** Running
`variance_split` over every cached pairwise comparison — the caricature check that had never
been run on the pairwise records — gives a persona-to-passage sum-of-squares ratio of **0.0028**
on preference, **0.0071** on intensity and **0.0342** on §74's repair arms. Win rates across the
four personas spread by 0.036 to 0.081. Mean pairwise persona agreement is 0.786 on intensity,
against a chance-at-marginal value of about 0.745 when every persona answers "original" ~85% of
the time — so they agree because they say the same thing, not because they share a reading.

One word of question change moved the sham by 0.10 and fixed the sign of the primary arm; four
personas move the answer by less than a tenth of that. **The question is the load-bearing knob
and the persona is not**, which retires "write better personas" as the obvious next move. What
it does not retire is the persona *mechanism*: this cannot distinguish personas that are too
alike from a model that drops the costume under a forced binary choice, and the cheap test that
separates them is one run with two deliberately opposed readers.

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

## 73. Before asking whether summaries flow, ask whether the summariser holds still

**Pre-registered. Written before the first call, and that is the point.** §69's
selection-family rule is that a family is one comparison when it was named before the
data; this entry names four conditions and the instrument that will answer them, and
it is committed ahead of the run so the numbers cannot choose the thresholds.

The direction is a good one and it arrived from outside: *summarise each scene, then
measure how well one summary flows into the next*, and then *summarise the summaries
and measure the drift*. Long-range structure is the thing this project has no working
instrument for — §58's `transplant` arm is the one the persona panel is blind to, and
the panel's own local-coherence reading says why — so a measure that reads across
scenes rather than inside them is aimed at the right gap. But both proposals are
measurements **through** the §71 summary call, and neither is interpretable before
that call's own re-sample variance is known.

**The precedent is exact and it is a death.** `tree-Haar scale energy` died at
ICC(1) = 0.270 with within-book sd equal to between-book sd: its replicates of one
book disagreed as much as different books did, so every hierarchy built on it was
arithmetic over noise. A summariser is the same shape — a compression re-sampled per
unit — and a flow measure over unstable summaries reproduces that death one level up,
after paying for a full sweep to find out. So the summariser is measured first, and
the cost is two orders of magnitude below the sweep it gates.

**Reliability alone is a trap; separation is the test.** A summariser that answers
"two characters, one promise opened" for every scene in the book is perfectly reliable
and carries nothing. Every statistic in `research/quality-measurement/summary_reliability.py`
is therefore reported against a between-scene contrast — within-scene agreement counts
only in the amount by which it exceeds agreement between summaries of *different*
scenes — which is the sham discipline moved one instrument over: a detection rate is
read against its placebo, never alone. The Jaccard convention makes the trap explicit
rather than hiding it. Two summaries that both report no promises paid have agreed, so
empty-against-empty scores 1.0; the degenerate case that opens — a field empty
everywhere, scoring 1.0 for every pair — is caught by the contrast, which is also 1.0,
so the separation is zero and the field reads as carrying nothing.

**The conditions, with their numbers, before the data.**

| Condition | Threshold | What failing it kills |
| --- | --- | --- |
| identity | `characters` within − between Jaccard ≥ 0.30 | The summary does not identify its own scene. No flow or drift measure over it is interpretable, and the proposal stops here. |
| ledger | ICC(1) on `n_promises_opened` ≥ 0.50 | The promise ledger's inputs are re-sample noise; migration 023 is recording the sampler rather than the book. |
| delta | ICC(1) on `delta_present` ≥ 0.50 | §61 Add 1's delta correlation work has no stable left-hand side. |
| positivity | no numeric field constant across the whole grid | The gate-0 shape: 195 of 196 `keep-reading`, both mean squares exactly 0.0, every variance statistic undefined. A field that never varies is a finding, not a number. |
| level 2 *(gated)* | own-window retention − foreign-window retention ≥ 0.20 | The summary-of-summaries is not carrying what it summarises, and "drift" is measuring the sampler. |

The positivity row is stamped from experience rather than caution: it is the exact
condition that ended gate 0 of `plan/persona-reader-validity.md`, and it took a manual
read of the raw records to see that the undefined statistic *was* the finding. Here
the degenerate case is detected before the ICC is computed and reported as
`status: constant` beside it.

**What is measured is the prompt, not the job — and the gap is named here rather than
discovered later.** `render_summary_prompt` is a pure function and `SUMMARY_SCHEMA` is
a constant, so both run without the store, the queue, or a provider profile. The
production path runs the `mechanical` profile through the configured provider; this
runs a flag-selected model through `elicit`'s transport with `--effort` unset. Where
the two agree, this bounds the shipped call; where they do not, it measures the
prompt's own stability, which is the part every downstream proposal inherits whatever
provider runs it.

**Level 2 is a proposal, not a component, and it is gated.** `context.py` evicts
summaries under budget, so summaries-of-summaries do not exist in this system — their
absence is what the eviction costs, and that is the honest statement of what the
`--level 2` arm would buy. Its window rendering is a first draft whose wording is a
free parameter the measurement cannot separate from the summariser's behaviour, so it
is kept plain and said so in the code. And it is read only if level 1 clears identity:
a drift number over summaries that do not identify their own scenes is a measurement
of the sampler with a narrative attached.

**The null already runs, which gate 0's arithmetic never did.** The dry-run arm
answers from a hash of the request digest and ignores the scene entirely, so it is a
draw from the null — and it lands where a null should: separation −0.0347, delta
ICC 0.0909, and own-window retention 0.200 against foreign-window retention 0.200 for
a gap of exactly zero. The synthetic answer also opens exactly one promise every time,
which fires the positivity guard on `n_promises_opened` and demonstrates the guard on
data whose behaviour is known. A pipeline whose statistics have never executed is a
pipeline whose first real run is also its first integration test; this one has run.

## 74. A human read the book, and the instrument cannot see anything he found

> **Partly retracted by §78, on the same day.** `ablate.em_dash_strip` collapsed every blank line
> in the passage it edited, so the `em_dash_strip` arm compared a paragraphed text against an
> unparagraphed one and its win rate is an artifact. **Every `em_dash_strip` number in this entry
> and in Addendum 1 is withdrawn, and with them the `OPPOSES` verdict and the reading that a
> reader model in the loop would select *for* the em dash.** The human read itself, all four
> measured defects, `_PROTECTED`, `em_dash_inject`, `rewhitespace` and the structural finding that
> reader-named defects sit in *both* copies of an ablation pair are unaffected. §78 carries the
> proof, the fix and the pre-registration for the corrected run; the struck passages below stay
> visible because the decision log is append-only.

The first human read of a fully generated book happened on 2026-08-18, on `The Toll Road` —
ten drafted scenes, 10,049 words, the same corpus every reader measurement in §70 ran on.
Three defects were named. All three measured true, one was worse than stated, and measuring
them turned up a fourth that nobody had looked for.

| named | measured |
| --- | --- |
| stats are monotone; a standard `HP ?` is meaningless | all ten `[STATUS]` lines read `Level 2 \| HP x/22 \| MP ?/? \| Gold ?`. Level never moves. MP and Gold are literally `?` — 20 unresolved values. Nine of twelve slots carry no information. |
| first-person experience is rare; it reads as examining a human rather than being one | 82 body-part nouns against 18 interiority verbs, a **4.56:1** ratio. 26 uses of "hand". |
| AI tells remain, especially em dashes | **61 em dashes**, 5.9 per 1k words, 6.1 per scene. Other tells are near-absent: zero "not X but Y", zero sentence-initial "But". The em dash carries the signature almost alone. |
| *(not named — found while checking)* | HP gains **+4 in scene 5 and +2 in scene 8** with no healing language anywhere in either scene. The one stat that moves is also wrong, and `state.contradiction.v0` ships to catch that class. |

**The sharper version of the stats complaint is the one worth keeping.** The book prices its
tolls in *days off a man's remaining life* — 7, 9, 5 and 6 days charged across ten scenes. That
is the stat with unusual purchase on this world, it already exists in the prose, and the
`[STATUS]` block tracks generic HP/MP/Gold beside it and never once shows the debt or the days
left. The interesting number was invented by the premise and ignored by the system voice.

**The finding that reframes the programme: not one of these is visible to the instrument, and
the reason is structural rather than a matter of tuning.** Every arm in `ablate.ALL`
manufactures damage by spoiling something good, and `evaluate` validates a panel on telling the
spoiled copy from the original. All three named defects are present in **both** copies. They are
not a degradation of the baseline; they *are* the baseline. A panel that cleared §70's detection
rung at 0.906 has therefore never been asked to find a defect a human actually found, and one
read produced more diagnostic information than three paid runs did.

**`ablate.READER_DEFECT_SET` closes the manufacturing gap** — `em_dash_inject`,
`interiority_strip` (with `deplete_matched` as its matched-deletion control, exactly as
`destake` has), and `stat_flatten`, which is expected to read as a near-null here *for a reason
that is itself the finding*: the book's stats are already flat, so there is nothing left to
flatten. The set is kept out of `ALL` and out of `PERSONA_SET` for the reason
`PERSONA_DEGRADERS` gives — widening a set that recorded batteries pooled over would make a
re-run incomparable with the published summary.

**The repair direction is deliberately not an `Ablation`.** `em_dash_strip` is a plain function
kept out of every registry. The `Ablation` contract says `sign` is -1 or 0 with no +1, on
§1a.2's measured finding that models asked to improve prose make it worse, and that prohibition
is right: this function makes no claim about quality. It applies one mechanical substitution in
the direction a named human said they wanted, and whether the panel agrees is the question
rather than the assumption. Keeping it out of the registries is load-bearing rather than tidy —
`evaluate` multiplies every per-arm delta by the metric's expected `direction`, so an arm whose
expected direction is opposite would report `hit_rate` and `dose_rho` backwards while looking
like any other row.

**A confound was caught before the run and is recorded because it nearly wasn't.** The first
strip turned `**TOLL PAID — 9 days**` into `**TOLL PAID, 9 days**` and `[STATUS] wren — Level 2`
into `[STATUS] wren, Level 2`. A panel preferring the original would then have been telling us
it liked em dashes *or* that it liked unmangled stat blocks, with no way to separate them.
`ablate._PROTECTED` excludes bolded system-voice headers and `[STATUS]` lines from both em-dash
arms. After the fix: **35 prose em dashes replaced, 24 structural ones untouched**, mean word
change -0.30%, one possible comma splice across 10,000 words.

**Pre-registered, and two-sided on purpose.** `research/quality-measurement/reader_repair.py`
runs three arms over the same ten scenes at one comparison per persona per orientation — the
strip, the inject, and `rewhitespace` as the sham floor. The precondition is read first as
always: positional bias outside 0.40–0.60 voids the run, which is what both `gemma3:4b` runs
earned. Then the sham floor: if `rewhitespace` moves as far from indifference as the strip does,
the preference is edited-ness and not the mark — a live risk, because §70's pairwise sham sits
at 0.783 and both arms here are small edits to the same prose.

| branch | condition | what it would mean |
| --- | --- | --- |
| AGREES | strip ≥ 0.60 and inject ≤ 0.40 | the panel shares the human's taste, and a reader model inside the writing loop would push against the tell |
| OPPOSES | strip ≤ 0.40 or inject ≥ 0.60 | the panel has the machine's taste, and a reader in the loop selects **for** the tell |
| BLIND | both arms inside 0.40–0.60, sham cleared | the panel cannot see a defect a human found in one read |

**OPPOSES is the branch §5a predicts, and it is written down here before the run so that it
cannot be reported afterwards as a surprise.** The panel is measured sharp on local coherence
and near-blind to global belonging; an em dash is the maximally locally-smooth punctuation,
welding any two clauses without requiring the sentence to earn the join. If that reading is
right, the panel should prefer the em-dashed text. ~~That is also the direct answer to the
question this entry exists under — *should the writer simulate a reader while writing?* — which
is: yes, but not this reader, because this one would optimise the defect.~~ **Struck by §78: the
arm that appeared to confirm this prediction was measuring paragraph loss, so the prediction is
untested rather than confirmed.** The local-scale reading of §5a still predicts OPPOSES and §78.2
pre-registers the branch that would license it; what is withdrawn is the claim that it happened.

**Addendum 1: the tier check rules out a capability floor, and its gradient argues against the
reading it was meant to confirm.** The same three arms ran on `claude-opus-5`, 232 comparisons,
zero refusals.

    model             em_dash_strip   bias    em_dash_inject   bias    rewhitespace   ties
    claude-haiku-4-5    [WITHDRAWN]  0.4857           0.3527  0.8571         0.4375   79%
    claude-opus-5       [WITHDRAWN]  0.5000           0.2000  0.7000         0.4813   69%

The withdrawn column read 0.0417 and 0.0000. It is struck rather than deleted because the decision
log is append-only and because the number is still evidence — of how large an effect a layout
confound produces in this instrument, which is the most useful thing left in it: a 96–100%
preference, on the strongest tier available, at textbook-clean positional bias, produced entirely
by removing blank lines. `results/reader-repair.json` and `results/reader-repair-opus.json` are
left exactly as they were so the superseded numbers stay pointable; the corrected run writes to
`results/reader-repair-fixed.json`.

~~**Opus preferred the em-dashed original in 72 of 72 comparisons, at a positional bias of exactly
0.5000.** So this is not a weak-model artifact: the strongest tier available is *more* certain
than the cheap one and its bias is textbook-clean. Buying a better panel model does not move it.~~
**Struck by §78: both tiers ran the reformatting transform, so the Opus column measures the same
artifact on a better model. The 0.5000 bias and the zero refusals stand as facts about the run.**

~~**But the direction of that gradient is evidence against "the panel has the machine's taste".**
If replacing an em dash with a comma genuinely damages the sentence, a stronger reader should
detect the damage *more* reliably — Opus 0.000 below Haiku 0.042 is the expected shape for real
damage and the wrong shape for a shared aesthetic quirk.~~ **Struck by §78, and it is the most
instructive sentence in this entry: the inference was sound and the damage was real — it was the
paragraph loss. A stronger reader detecting a wall of text more reliably than a weaker one is
precisely the observed gradient, so the argument pointed straight at the confound and was read as
pointing away from it.** The `possible_comma_splices: 1` this protocol reported is a crude regex
and not a syntax check, so it is not evidence against that either. The decisive control is one
arm: strip em dashes to periods rather than commas. If the panel accepts a period-strip while
rejecting the comma-strip, its objection is syntax and the repair was the defect; if it rejects
both, the objection is the mark. **§78.2 makes that control conditional on the corrected arm
still showing a preference to explain.**

`rewhitespace` drew "neither" on 69% of Opus comparisons against 79% on Haiku. Both tiers decline
to choose between texts differing only in layout, which is the correct answer and the first clean
behaviour the sham machinery has produced.

`em_dash_inject` is void on both tiers (0.857 and 0.700). The same transform run in opposite
directions produces pairs the panel answers positionally in one direction and cleanly in the
other, which is a further reason positional bias cannot be inherited across experiments.

## 75. Twenty-one proxies asked whether the text was good; this one asks whether it is ours

Every refuted proxy in BRIEF §2 was trying to answer *is this text good?*, and every label
available for that question is contaminated — engagement tracks cover art and launch timing,
comment counts track archive capture date, declared-AI tracks the year. §74's human read forces
a different question, because the three defects it named are not degradations of good prose but
properties of our baseline. The question that fits them is *is this text ours?*, and it has the
one uncontaminated label this project will ever own: **we know with certainty which scenes our
pipeline wrote.** Pass 2 failed because it tried to detect *other people's* AI text through an
unreliable declaration. Nothing here depends on anyone declaring anything.

`research/quality-measurement/authorship_tells.py` fits a logistic discriminator on 24 surface
counts — no model calls, no corpus statistics, nothing that can leak across the split.

**The null is the finding, not the AUC.** Ten drafted scenes cannot train anything, so the run
scores our side leave-one-out and then executes *the identical procedure* with ten randomly
drawn human chapters standing in for ours, forty times, to learn what this method reports at
this n when there is nothing to find. Controlled run — human side length-matched to our scenes
at 700–1,400 words, system-voice lines stripped from **both** sides, the `words` feature dropped
because the first pass gave it a weight of −0.96:

| cohort | human n | our AUC | null median | null p95 | null max | p |
| --- | --- | --- | --- | --- | --- | --- |
| RoyalRoad 2021-22 (pre-LLM) | 876 | **1.0000** | 0.4956 | 0.7289 | 0.7786 | 0.0 |
| RoyalRoad 2025 | 1,618 | **1.0000** | 0.4143 | 0.6053 | 0.6637 | 0.0 |

Ten human chapters do not separate from other human chapters. Ours separate perfectly, in both
eras, with formatting and length removed as explanations.

**Six tells hold their sign across a four-year gap that contains the LLM transition**, so none of
them is the year. Weights are standardised contributions to the joint model; a positive weight is
a feature we produce *more* of.

| feature | pre-LLM | 2025 | reading |
| --- | --- | --- | --- |
| `adverb_ly_per_1k` | −1.891 | −1.546 | humans use far more -ly adverbs. We are scrubbed, not styled. |
| `word_len_mean` | −1.360 | −2.711 | our words are shorter |
| `sentence_len_cv` | **+1.064** | **+1.632** | the only one where we are higher — we over-vary sentence length |
| `question_per_1k` | −0.913 | −1.629 | humans ask far more questions |
| `first_person_per_1k` | −0.902 | −1.279 | §74's second defect, independently recovered |
| `participle_open_per_1k` | −0.619 | −0.854 | humans open with `-ing` more than we do, which inverts the folklore |

In the pre-LLM run specifically, `body_per_1k` reads +0.843 and `interior_per_1k` −0.681 — the
human's "examining a human rather than being one" arriving as a *pair* of features rather than as
an impression.

**Five of the six are shortfalls.** Only sentence-length variation is an excess. The signature of
this pipeline is not that it adds machine mannerisms; it is that it under-produces the ordinary
texture of human prose — adverbs, questions, first person, long words, participial openers — and
compensates with rhythm.

**`sentence_length_cv` is the entry that vindicates the reframe.** Pass 2 measured it at rank AUC
0.461 for declared-AI detection and buried it as dead. It is dead — as a general detector of
anyone's machine prose. It is simultaneously one of the strongest features separating *our*
output from human LitRPG. Both readings are true because the questions differ, and the second
question is the one with a clean label.

**Em dashes are real and not the biggest thing.** §74 measured our rate at 5.50 per 1k against a
pre-LLM human median of **0.00** (p90 1.91), which puts us at roughly the 95.5th percentile — the
human read was right. But once length is matched and system voice stripped, `em_per_1k` falls out
of the top ten, because other features carry more. The mark is a tell; it is not the tell.

**A methodological finding, and it costs the 2025 shard its standing as a negative class.** Human
em dashes per 1k moved from median 0.00 / p90 1.91 in 2021-22 to median 1.11 / p90 11.86 in 2025.
Interiority did not move at all across the same gap (3.69 → 3.61). The 2025 corpus has drifted
toward the machine on exactly the axis where drift would be expected, which is either LLM
contamination of RoyalRoad or a real style shift — and either way **the pre-LLM shard is the only
clean reference for tell work.** Recorded here so a future run does not measure against 2025 and
conclude it is fine.

**What this does not license.** The ten scenes are one book, one premise, one narrator. A
signature separating *The Toll Road* from human LitRPG may be that book's rather than this
pipeline's, and nothing here separates the two. A second generated book with a different premise
is the control, it is the obvious next measurement, and until it runs this reads as *this book is
distinguishable* rather than *our pipeline is*.

## 76. The ledger does not track what the story charges, and neither does anyone else's

§74's first defect in the only form that survives the two proxies which already died on it.
`progression_cost` was satisfied by a token gold decrement beside each level-up — the cheapest
repair that satisfies it *is* the disease — and `silent_ledger` fires on the fixture's best
prose. Both measured annotation **density**. The human's complaint is not about density: `The
Toll Road` prices its tolls in days off a man's remaining life (7, 9, 5 and 6 days charged
across ten scenes) and the `[STATUS]` block tracks HP / MP / Gold beside it and never shows the
debt. So `state_coverage.py` measures **correspondence** — the units the prose charges people in
against the units the record keeps. Padding the ledger cannot raise it.

**It refuted itself on its own control, twice, and the first refutation was false.** Run one
reported human median coverage 0.0 with `share_at_zero` **1.0** — every human chapter, no
exceptions — which is too clean to be a fact about the genre. It was a fact about the extractor:
`_STATUS_LINE` matched only a bracketed `[STATUS]` tag, which is what this system emits and what
**0.0% of 1,200 human RoyalRoad chapters** contain. Published LitRPG writes sheets as `Name: Dix`
/ `Level: 0` line runs and `[ Strength : 0.1 ( Tier 0 ) ]` bracket runs. The control could not
have passed. Reading both shapes took detection from 0% to 18%.

**Run two was mis-specified in a second way** — human coverage per *chapter* against ours per
*book*, when most single chapters carry no sheet at all. Grouped by story, both sides book-level:

    cohort                  stories with costs   median   mean    p90   share at zero
    RoyalRoad 2021-22 pre-LLM        95 of 151      0.0   0.168   0.50           0.590
    RoyalRoad 2025                  111 of 178      0.0   0.188   0.571          0.604

**The verdict is DOES NOT SEPARATE US, which is not the same as REFUTED and the first reading
conflated them.** The axis has real variance — 41% of human books track something they charge,
and the top decile reaches 0.5 — so it is not a constant and could discriminate. It simply does
not discriminate *us*: our 0.0 sits with the ~59% majority. So this formalisation fails to
capture the complaint that prompted it. Whatever makes flat stats feel flat, "the record omits
the charged unit" is not it, because most published LitRPG omits it too and is read anyway.

**The other half stands and is not a proxy for anything.** `unexplained_gains` flags a tracked
value rising with nothing in the prose licensing the rise, and it found both defects in this
book deterministically: HP **+4 between scenes 4 and 5** and **+2 between scenes 7 and 8**, no
healing language in either scene. Straight continuity, no quality claim, and the class
`state.contradiction.v0` ships to catch and did not.

## 77. The panel can rank human prose, and the arm that showed it is not the arm that was designed

Every comparison this project had run put our prose against our own prose, so the panel had
never judged our work against anyone else's. `taste_calibration.py` fixes that with five arms
over ~1,000-word excerpts, `claude-haiku-4-5`, 320 comparisons.

    arm                          n   win rate   chose-A   reading
    ours vs Mother of Learning  64     0.9844    0.5156   confounded — see below
    ours vs RoyalRoad median    64     1.0000    0.5000   confounded — see below
    MoL vs RoyalRoad median     64     0.9062    0.4375   clean
    RR high vs low conversion   63     0.7857    0.3810   VOID on bias (§77.1); covariates unmatched
    MoL vs MoL (floor)          64     0.4062    0.3750   void on bias

**The calibration arms are the result.** Both are excerpt-against-excerpt, the same treatment on
both sides, and the panel ranks a fan-acclaimed serial above a median RoyalRoad chapter at 0.906
and high-conversion above low-conversion at 0.786 across eight distinct stories per side. ~~The
second is the one that matters: `conversion = followers / total_views` is a label nobody told
the panel about, both sides are equally obscure, and era and platform are held fixed. **This is
the first positive result the persona instrument has produced** — it is not tasteless, and a
panel that can order human prose on an external label is a panel worth repairing.~~

**Struck by §77.1.** The second arm is **void on this protocol's own positional-bias precondition**
at `chose_A_rate` 0.3810, and "both sides are equally obscure" is false by two orders of magnitude:
the compared pairs differ **255x** in median views and 6.4x in median followers, with the
high-conversion side being the *less*-read story in 7 of 8 pairs. Era and platform *are* held fixed
— that clause survives, verified chapter by chapter. What does not survive is the conclusion: the
only readable calibration arm is `mol_vs_rr`, which recognition alone predicts, so **the panel has
not been shown to order human prose on an external label.** §77.1 carries the covariate table and
what the benchmark has to do instead.

**The headline arms are confounded and the confound is one this protocol introduced.** The
docstring written *before* the run claimed a win for us would be the reading "the confounds
cannot manufacture", and that was wrong twice over. Our units are complete scenes; the human
side is an arbitrary window cut 20% into a chapter, so ours has a beginning and an ending theirs
does not. And this book is premised on a man paying tolls in days of his life, so it is
stakes-dense by construction. The panel's own reason codes say exactly that: `stakes-real`
carries **38 of 63** wins against MoL and **43 of 64** against RoyalRoad. Pre-registering the
wrong claim is worse than not pre-registering, because it lends a number authority it has not
earned, and this entry exists partly to say so.

**A deeper problem the confound points at.** The reason vocabulary — `stakes-real`,
`voice-landed`, `pulled-forward` — is one *we* wrote, and the generator optimises the same
things (§71's promise ledger, the delta annotation, the `stakes` persona). A reader built to
read for stakes preferring a writer built to write for stakes is not taste; it is two
specifications we authored agreeing with each other. That is not fixed by better personas
either. It is fixed by criteria sourced from outside this project, and `rr_high_vs_low` is the
first evidence that such criteria are usable here at all.

**Three controls run against it**, all reading against the same cached arms at no extra cost:
`ours_win_vs_mol_win` cuts both sides to ~700-word windows so neither has a beginning or an
ending; `ours_vs_mol_stakes` selects the MoL window by stake-vocabulary density instead of
position; `ours_win_vs_mol_stakes` applies both. The second is covariate **matching** rather than
a quality selection — it uses this project's own stake lexicon, which identifies stake vocabulary
and not stakes — and its only claim is that the comparison is no longer decided by which side
happened to be about something costly.

### 77.1 The three controls land, and the arm they were not aimed at is the one that fails

The controls §77 describes as "run against it" had their numbers on disk and not in this log. All
three clear the per-arm positional-bias precondition, which the headline arms also clear and which
`rr_high_vs_low` and `mol_vs_mol` do not.

    arm                        n   win rate   chose-A   bias band
    ours vs MoL               64     0.9844    0.5156   clean
    ours_win vs mol_win       64     0.9688    0.5312   clean
    ours vs mol_stakes        64     0.9844    0.5156   clean
    ours_win vs mol_stakes    64     0.9062    0.5938   clean

512 comparisons, one refusal, `claude-haiku-4-5`, $16.12 equivalent. **Neither confound §77
identified explains the result.** Windowing our side so that it also starts and ends mid-flow costs
1.6 points; selecting the human window by stake-vocabulary density costs nothing; applying both
costs 7.8 points and still leaves 0.906. So "our units were complete scenes and theirs were
arbitrary cuttings" and "our book is stakes-dense by construction" are both bounded and neither is
the answer. What §77 says about the *reason vocabulary* is untouched by this and remains the live
objection: a reader built to read for stakes preferring a writer built to write for stakes is two
specifications we authored agreeing with each other, and no amount of windowing addresses it.

**The correction is to the arm §77 called the result.** Reading the artifact rather than the entry:

- **`rr_high_vs_low` is void on its own pre-registered precondition.** Its `chose_A_rate` is
  **0.3810**, outside the declared 0.40–0.60 band, and `taste_calibration._read` duly lists it in
  `voided_arms`. §77's table says "marginally outside the bias band" and then the prose calls it
  "the one that matters" and "the first positive result the persona instrument has produced".
  ~~Both readings are withdrawn~~ — **the arm is void, so the only readable calibration arm is
  `mol_vs_rr`, which is the fame-confounded one.** The claim that the panel "ranks human prose by
  quality" currently rests on a fan-acclaimed serial beating a median chapter, which recognition
  alone predicts. The instrument has not been shown to track an external label.
- **"Both sides are equally obscure" is false, by two orders of magnitude.** For the eight pairs
  actually compared:

        covariate      low-conversion median   high-conversion median   imbalance
        conversion                   0.00069                  0.02654      38.3x
        total_views                  213,623                    837.5    1/255x
        followers                      138.5                     21.5     1/6.4x
        favorites                         46                        5     1/9.2x
        words                        2,370.5                  2,362.5       1.0x

  Length is matched and everything about audience size is not. Because `conversion =
  followers / total_views` and followers are comparably small on both sides, the high-conversion
  side is **the side almost nobody read**: in **7 of 8 pairs** the "high quality" chapter belongs
  to the less-viewed story, with view counts of 174, 219, 280 and 331 against 3.19M, 883k, 365k
  and 352k. A ratio with a denominator that small is dominated by its own noise, and the arm is
  closer to a low-traffic-versus-high-traffic contrast than to a quality contrast.
- **`era` and `platform` *are* held fixed, and that part of §77 stands.** Every one of the sixteen
  chapters in the eight compared pairs carries `cohort == human_pre_llm`. The single
  `undeclared_2025` chapter in the pool — the 0.44751 outlier, 665 followers on 1,486 views — sits
  at index 9 of `rr_high` and falls outside the eight pairs. That is luck rather than design: the
  dump filters on `era_cohort(...) is not None`, which admits all three cohorts, so a `--pairs`
  above 9 would have pulled AI-era text into a comparison the entry describes as pre-LLM.
- **§56.6 item 4 already refused this selection, and §77 does not cite it.** "Do not select §4.4's
  corpus from conversion deciles" was landed on 2026-08-17 because the deciles are recoverable from
  prose-blind `followers` at **AUC 0.814** and from `chapters_seen` at 0.308
  ([craft-corpus.md](craft-corpus.md) §4.1). `rr_high_vs_low` selects top-ten against bottom-ten
  conversion, which is that refusal's shape. The refusal was written about a craft-exemplar corpus
  and this is judge calibration, so it is not the identical use — but the bite is the same and
  sharper here: if a judge is *selected* by agreement with a label recoverable prose-blind from
  story size, the selection prefers whichever judge best proxies story size. `conversion.json`'s
  own verdict already words the requirement — a critic scored against conversion "takes the
  prose-blind baseline as a covariate from line one".
- **The committed corpus does not regenerate from the committed defaults.** `human-excerpts.json`
  records `rr_stories_scored: 229`; `taste_calibration.dump`'s `--limit` default of 4000 yields
  **167**. Reproducing 229 needs `--limit` ≥ 6000. The payload should record the limit it was built
  with, since the file is gitignored and regenerating it is the only way to check anything about it.

**What this does to the programme.** The taste-gap work was to be anchored by scaling this label
from 8 pairs toward hundreds and selecting judge configurations by agreement with it. The label is
not usable in the form the 8 pairs used it, so scaling first would scale the confound. The
benchmark has to pair **within** view and follower bands rather than across global conversion
deciles, impose a views floor so the ratio is not noise — 175 of the 490 distinct LitRPG stories in
the two cached shards clear 10,000 views while keeping a 9.1x p10–p90 conversion spread — and
report every judge candidate against a prose-blind size baseline in the same table. That is a
different experiment from the one §77 piloted, and it is the one worth building.

## 78. The em-dash finding measured a reformatting bug, and the guards could not have seen it

§74's headline number is an artifact. `ablate.em_dash_strip` ended with

```python
return re.sub(r"\s+", " ", "".join(out)).replace(" ,", ",").strip()
```

and `\s` matches newlines, so the tidy-up applied to the whole passage rather than to the spacing
around a replaced dash. Over the ten drafted scenes of `The Toll Road` the transform took the
newline count from **858 to 90** and the blank-line count from **420 to 45** — and the survivors
are all scene 7, which contains no em dash and returns early. **Nine of the ten
"em-dash-stripped" variants were the entire scene run together as a single block.**

**This is not an inference about what the code would do; it is what the panel was sent.** All
**72** `em_dash_strip` comparisons in `results/reader-repair-raw.jsonl` were checked by rebuilding
each request digest from the flattened variant and looking the key up in the committed cache:
72/72 matched. `elicit.Elicitor._call` keys on `digest({'params': params, 'transport': ...})`, so
the key is a function of the exact bytes sent, and a match is proof of content rather than
evidence about it. The panel's 0.0417 was a preference for a paragraphed text over an
unparagraphed one, elicited at one comparison per persona per orientation, and it was never a
verdict about the mark.

**What that retracts.** §74's `em_dash_strip` rate, its `OPPOSES` verdict, and the reading built
on it — "the panel prefers the tell; a reader in the loop selects **for** it" — are withdrawn.
Addendum 1 goes with them: the Opus tier check ran the same transform, so its 0.0000 across 72 of
72 comparisons is the same artifact measured on a better model, and the gradient argument that
entry made — *"Opus 0.000 below Haiku 0.042 is the expected shape for real damage and the wrong
shape for a shared aesthetic quirk"* — was reasoning correctly about damage that was real and
misidentified. The damage was the paragraph loss. A stronger reader noticing a wall of text more
reliably than a weaker one is exactly the gradient that was observed, and it pointed at the
confound rather than away from it.

**What survives, and it is most of the entry.** The three defects the human named, and every
measurement of them — the twelve `[STATUS]` slots with nine carrying no information, the 4.56:1
body-part-to-interiority ratio, 61 em dashes at 5.9 per 1k words, the uncommented HP gains in
scenes 5 and 8 — are untouched. So is the finding that reframes the programme: all three sit in
**both** copies of every ablation pair, so a battery that validates a panel on telling a spoiled
copy from an original cannot see them however well it scores. So is `_PROTECTED` and the confound
it fixed, 35 prose dashes against 24 structural ones. So is `em_dash_inject` (0.3527 Haiku, 0.2000
Opus), which does not route through the broken tail — and it was already void on positional bias
at 0.857 and 0.700. So is `rewhitespace`, which preserves structure exactly and drew "neither" on
79% of Haiku and 69% of Opus comparisons. And so is the conclusion that positional bias is a
property of the pair rather than of the panel.

**The reason no guard caught it is the transferable part.** Every guard in place was a length
guard. `em_dash_report` counts em dashes, words and possible comma splices; `Ablation.preserves_length`
is a word-count property; and `str.split()` treats `"\n\n"` and `" "` identically. So the report
beside the result read `word_delta_pct: -0.30%`, `em_dashes_before: 59`, `em_dashes_after: 24`,
`possible_comma_splices: 1` — **every one of those numbers was correct** and not one of them could
move when the paragraphing went. A layout change is invisible to a length invariant. `rewhitespace`
existed to bound exactly this and could not, because it perturbs layout *without* destroying it:
the sham was a weaker edit than the arm it was bounding, in the one dimension that mattered.

**The fix and its check.** Both whitespace patterns in `em_dash_strip` are now horizontal-only
(`_HSPACE = r"[^\S\n]"`), which also stops the match crossing a line boundary — a dash at a line
start previously consumed the newline before it and replaced it with `", "`. After the fix the
transform is the one that was always intended: newlines 858 → 858, blank lines 420 → 420, **35
prose em dashes replaced, 1 possible comma splice** — the published transform figures, now with
the layout left alone. `tests/test_ablate_structure.py` carries the invariant that was missing:
`test_em_dash_strip_preserves_paragraph_structure` asserts this arm's layout exactly,
`test_no_transform_collapses_a_passage_to_one_block` bans the class across every registered arm,
and `test_em_dash_strip_leaves_protected_system_voice_alone` keeps §74's confound fix asserted.
The suite gets research code for the first time, deliberately and narrowly, on a synthetic fixture
rather than `corpora/toll.db` — the database is gitignored and a guard that runs only where the
corpus happens to sit is not a guard.

### 78.1 A second defect in the same audit: seven arms lose the blank line

Auditing every transform for the same class turned up a milder version of it in the shared
sentence machinery. `paragraphs()` adapts to whichever separator convention the source uses —
its docstring exists because a fixed blank-line split once turned every paragraph-level ablation
into a no-op on *Mother of Learning* — but `_join` does not adapt: it is `"\n".join(blocks)`. The
round trip is therefore lossy for a blank-line-separated source, and every arm routing through
`_rebuild` returns single-newline-separated text. Measured over the same ten scenes, newlines go
858 → 438 and blank lines 420 → 0.

    arm                 blank lines        class
    sentence_deletion   420 -> 0           separator downgraded
    sentence_shuffle    420 -> 0           separator downgraded
    paragraph_shuffle   420 -> 0           separator downgraded
    filler_inject       420 -> 0           separator downgraded
    destake             420 -> 0           separator downgraded
    deplete_matched     420 -> 0           separator downgraded
    interiority_strip   420 -> 33          separator downgraded
    em_dash_strip       420 -> 45          TOTAL flattening (fixed above)
    the other eight     420 -> 420         structure preserved

This is a real confound and a smaller one: the variant still has line breaks, so it is not a wall
of text, but it is formatted differently from the original it is compared against, and
`rewhitespace` does not bound it for the same reason it failed above. Three of these arms sit in
`DEGRADERS`, which is what §70's detection rung and the CDG battery pool over, so part of the
`detect 0.906 / sham 0.783` margin is a formatting difference rather than damage.

**It is pinned rather than fixed, and that is an operator call rather than a judgement about
which is correct.** Changing `_join` changes the variant text of seven arms; the replay caches key
on the request digest, so nothing would silently replay stale numbers — every affected comparison
would simply re-elicit, at the cost of re-running the persona battery and the CDG battery.
`test_rebuild_arms_downgrade_the_paragraph_separator` records the exact set so it cannot change
in either direction without a test failing: an arm leaving it means someone fixed `_join` and the
numbers pooled over that arm need re-reading, and an arm joining it means a new transform
inherited the defect.

**One arm's paired control is also misdescribed, and this is a correction to §74 rather than a new
defect.** §74 introduced `interiority_strip` "with `deplete_matched` as its matched-deletion
control, exactly as `destake` has". `deplete_matched` takes its budget from `_stake_plan`, so it
is matched to `destake` and to nothing else: over the ten scenes it removes **7.44%** of the words
where `interiority_strip` removes **4.44%**. A control that deletes 1.7x the text is the length
confound it exists to remove. `test_deplete_matched_does_not_match_the_interiority_budget` asserts
the mismatch so the claim cannot be re-inherited from a docstring, and the interiority arm needs a
control built against `_interiority_plan`'s own budget before it is read.

### 78.2 Pre-registration for the corrected em-dash run

Written and committed **before** the corrected arm is elicited, so the ordering is a fact in the
git record rather than an assertion in this paragraph. The run re-elicits `em_dash_strip` against
the same ten scenes with the fixed transform and replays `em_dash_inject` and `rewhitespace` from
the existing cache unchanged; output goes to `results/reader-repair-fixed.json` so that
`results/reader-repair.json` stays exactly as §74 cites it.

The precondition is read first and it is now pre-registered rather than post-hoc: per-arm
positional bias within 0.40–0.60, the rule §74 adopted mid-flight and recorded as needing a run
where it was declared in advance. This is that run. `rewhitespace`'s sham floor is reported and
**is not treated as usable** — it was void on bias at 0.9375 from 16 decided comparisons, and
§78's finding is that it is the weaker edit in the dimension that matters anyway.

| branch | condition | what it licenses |
| --- | --- | --- |
| AGREES | strip ≥ 0.60 | the panel prefers the comma-stripped text, sharing the human's taste. §74's OPPOSES is retracted and em-dash density becomes an axis a reader model could be optimised on in the direction a named human asked for. |
| BLIND | 0.40 < strip < 0.60 | the panel cannot see the tell. OPPOSES retracted; the em dash joins the mapped holes — a defect one human found in one read and the instrument cannot detect. This is the outcome the artifact explanation predicts, and it is written down here as the prediction. |
| OPPOSES | strip ≤ 0.40 | the panel prefers the em dashes on structure-preserving evidence. Only then do the three surviving readings of §74's number — machine taste for the mark, edited-ness detection, or the comma genuinely degrading the sentence — need separating, and only then is the discriminating control commit 56ca535 named worth running. |

**The discriminating control is therefore conditional, and that is a change of plan recorded as
one.** Commit 56ca535 named "an equal number of punctuation edits that touch no em dash" as the
control the third explanation needs, and §74's addendum named a period-strip as the decisive one.
Both were designed to separate readings of a number that has now been withdrawn. Running them
first would be spending on the discrimination of an artifact. If the corrected arm returns BLIND
or AGREES there is no preference left to explain and the controls are moot; if it returns OPPOSES
they are the next experiment, and the pair of them is what the separation needs — a matched-count
punctuation edit touching no dash bounds edited-ness, and a period-strip run over the *same* dash
positions as a comma-strip separates the mark from its replacement, with the token delta held
equal because both substitutions remove the spaced dash's own token.

### 78.3 The corrected arm is void, and the em-dash question is open rather than answered

Run against the pre-registration in §78.2, 72 new elicitations with 160 replayed from the existing
cache, 5 refusals, $2.65 of new spend. `results/reader-repair-fixed.json`.

    arm              buggy    corrected   per-arm bias (was)   interval
    em_dash_strip   0.0417       0.3641   0.6032 (0.4857)      [0.2273, 0.5139]
    em_dash_inject  0.3527       0.3527   0.8571 (unchanged)   replayed, structurally sound
    rewhitespace    0.4375       0.4375   0.9375 (unchanged)   replayed, structurally sound

**Roughly 70% of the effect was the reformatting.** The arm's distance from indifference falls from
0.4583 to 0.1359. What is left leans the same way — the panel still picked the em-dashed original in
about 64% of comparisons rather than 96% — and **none of it is readable**, for two independent
reasons that both have to be reported because either alone would be enough:

1. **The arm is VOID on the precondition §78.2 pre-registered.** Its positional bias is **0.6032**,
   outside the declared 0.40–0.60 band. It misses by 0.0032, which is precisely the kind of margin
   that invites a second look at the rule, and the rule was fixed in advance for that reason. §74's
   per-arm precondition was itself adopted mid-run and recorded as post-hoc; §78.2 declared it
   before this run so that this sentence could not be an argument. It is not one.
2. **The interval spans indifference.** `[0.2273, 0.5139]` over 9 passages and 4 personas contains
   0.5, so even a bias-clean arm at this n could not have licensed a branch. The 72-comparison
   design was sized for an effect of the magnitude the artifact was producing.

**So the pre-registered branch that fires is none of them, and the discriminating control does not
run.** §78.2 made commit 56ca535's control — a matched-count punctuation edit touching no em dash,
plus a period-strip over the same dash positions — conditional on OPPOSES, on the reasoning that
separating three readings of a preference is only worth paying for once a preference is established.
VOID is not OPPOSES. Running the control now would be spending on the discrimination of a number
that has no interval. It stays built-but-unrun by design, and §78.2 is the record that this was
decided before the number arrived rather than after.

**The bias moved 0.12 when only the variant text changed, which settles a §74 side claim.** Same
panel, same model, same personas, same originals, same 72 cells: the only difference between 0.4857
and 0.6032 is that the compared text is no longer flattened. §74 concluded that positional bias is a
property of the pair rather than of the panel, on the weaker evidence of three arms differing from
each other. This is the same claim measured within one arm, and it is the strongest form of it the
project has: **a bias figure cannot be inherited across a change to the texts, let alone across
experiments.**

**What the em dash now is: an open question with a named cost to close.** The human named the tell,
the count is real (61 dashes, 5.9 per 1k words, §74), and no instrument here has an opinion about it
that survives its own preconditions. Closing it needs draws per cell above one — `compare_pair`'s
`n` multiplies the two orientations rather than replacing them — which tightens the bias estimate
and the interval together. At three draws per cell that is 216 new elicitations, about $8. **This is
a power increase adopted because a precondition failed, and its direction is worth stating: the
surviving point estimate is unfavourable to the panel, so tightening it cannot buy the panel a
pass.** That is the same test §74 applied to its own post-hoc rule change, and it is the reason this
remedy is legitimate where re-reading the band would not be.

## 79. The engagement label cannot be matched, so its confound's sign becomes the instrument

§77.1 left the external-label programme without a usable label: the one arm carrying a measured
reader outcome was void on positional bias and its two sides differed 255x in views. The obvious
repair is to match the covariates and scale up. **The obvious repair is impossible, and the reason is
arithmetic.**

`conversion = followers / total_views` is a ratio of the two prose-blind quantities anyone would want
to hold fixed, so

    followers_hi / followers_lo = (conv_hi / conv_lo) x (views_hi / views_lo)

Match the denominator and the numerator becomes a perfect predictor. Measured, not argued: the first
build of `taste_benchmark.py` matched views to within a factor of two and produced followers
imbalanced 7.6x with the high-conversion side larger in **21 of 21 pairs**. Match followers instead
and views takes the role, which is §77.1's configuration. **For any pair with a real label gap, at
least one prose-blind popularity covariate orders the pair, and no choice of tolerances removes
both.** This is the mechanism behind §56.3's measured `followers` AUC of 0.814 — that number is
partly arithmetic, as `conversion.json`'s own verdict says — and it is why §56.6 item 4 refused
selecting a corpus from conversion deciles.

**So the design stops trying to remove the confound and starts using its sign.** Pairs are selected
into two strata, disjoint at story level, length-matched in both:

    stratum   pairs   conversion   views      followers   favorites   high-side larger
    aligned      25        3.26x    1.04x         3.93x       4.00x   followers 25/25, views 12/25
    crossed      21        4.66x    0.062x        0.167x      0.158x  followers 0/21, views 0/21

In `aligned` every popularity rule points **at** the label. In `crossed` every one points **away**
from it: the higher-converting story is the one with 16x fewer views and 5.9x fewer followers. A
judge reading prose should agree with the label in both. A judge proxying popularity must agree in
one and disagree in the other, and **their mean is 0.5 — indistinguishable from a coin.** So the
benchmark never averages the strata; the statistic is `min(agreement_aligned, agreement_crossed)`,
and that is a bar rather than a number.

**The bar is 0.52, and it was 0.5714 until two leaks were closed.** Both are worth recording because
both are the kind of residual that would have quietly become the result:

- **The view residual had a direction.** Matching views inside `aligned` to within a factor of two
  left 15 of 23 pairs with the high-conversion side *less* viewed, because higher conversion
  correlates with fewer views. "Pick the less-viewed side" then scored 0.652 in `aligned` and 1.000
  in `crossed` — a minimum of 0.652, so a prose-blind rule cleared 0.50 in **both** strata and the
  design's central property was already gone. Filling the two view-signs evenly inside `aligned`
  (12/25 now) drives that rule to 0.52 and 1.000.
- **One rule reads a quantity no judge can see.** `pick_longer_chapter` scored a minimum of 0.5714,
  but `_excerpt` cuts both sides to about 1,000 words, so source chapter length is invisible in what
  is actually compared. It is reported and **excluded from the bar** as `NOT_A_ROUTE`; the covariate
  that matters is excerpt length, which is matched at 1036/1023 words in `aligned` and 1025/1024 in
  `crossed`, and `pick_longer_excerpt` sits at a minimum of 0.476.

    rule                     aligned   crossed   min
    pick_more_followers        1.000     0.000   0.000
    pick_fewer_followers       0.000     1.000   0.000
    pick_more_views            0.480     0.000   0.000
    pick_fewer_views           0.520     1.000   0.520   <- the bar
    pick_more_favorites        0.960     0.000   0.000
    pick_longer_excerpt        0.640     0.476   0.476
    pick_longer_chapter        0.600     0.571   0.571   not a route: erased by excerpting

**A judge passes only by exceeding 0.52 as a minimum across strata with both interval lower bounds
above 0.50 and positional bias in band, all pre-registered in `PRE_REGISTRATION` before the first
elicitation.** What a candidate may vary is model, transport, pair question, and which existing
personas are seated. It may not introduce a persona or a rubric: §77's 2x2 measured one plain word
outperforming four authored personas, and a criterion we wrote cannot be evidence about a judge we
are selecting.

**The corpus ceiling is 46 pairs, not the hundreds the programme asked for, and that is a fact about
the disk rather than the design.** 107 pre-LLM LitRPG stories clear a 10,000-view floor at
1,500–6,000 words across the two cached shards, one chapter per story because `conversion` is a
fiction-level constant — verified: the `(followers, total_views)` tuple does not vary across a
fiction's chapters. That caps disjoint pairs at 53, and the strata take 46 of them. The dataset has
47 shards and two are cached, so reaching hundreds is a download, not a redesign. The floor is not
the binding constraint either: dropping it to 1,000 views triples the story count and reinstates the
noise the floor exists to remove, since §77.1's high-conversion pool sat at 174–1,667 views where one
follower moves the label by 0.006.

**Also fixed here: era is filtered rather than trusted.** `royalroad_chapters` yields every cohort
`era_cohort` can label, so §77's pools admitted 2025 and declared-AI chapters and the eight pairs it
happened to compare were pre-LLM by luck (§77.1). The builder takes `human_pre_llm` only.

The corpus text is gitignored under the rule bbc6560 established; the committed record is
`results/taste-benchmark-corpus.json`, which carries every pair's covariates and no third-party
prose, so the balance table above is auditable without redistributing anything.

**No judge has been run against it yet.** The benchmark is the deliverable and the first candidate
costs 368 comparisons at panel width — the elicitation channel was occupied by §81's run. What the
build already establishes is independent of any candidate: the label is unmatched-able, the strata
make that usable, and the bar is 0.52.

### 79.1 The first candidate is void, and the shape of its failure is the one the strata were built to show

The default panel — `claude-haiku-4-5`, four personas, `preference`, `half_win` — against all 46
pairs. 368 comparisons, **zero refusals**, $11.71.

    stratum   pairs   agreement   interval          positional bias   decided
    aligned      25      0.6100   [0.460, 0.745]             0.3800       200
    crossed      21      0.4107   [0.256, 0.560]             0.3274       168
    minimum               0.4107                                          368 pooled bias 0.356

**VOID on the pre-registered precondition, and it fails the bar independently.** Both strata sit far
outside the 0.40–0.60 positional band, so nothing here licenses a reading. And even setting the
precondition aside the candidate does not clear the bar: the minimum agreement is **0.4107** against
a best prose-blind minimum of **0.52**, and neither interval lower bound reaches 0.50. Two
independent failures, reported together because either alone decides it — the same shape §78.3 had
to report, and the reason both preconditions exist.

**This bias failure is not the marginal kind.** §78.3's arm missed the band by 0.0032 on 72
comparisons. This misses it by 0.14 on **368 decided comparisons**, roughly 5.8 standard errors from
indifference. The panel picked the second slot in 64% of these comparisons. So on ~1,000-word
human-against-human excerpt pairs the instrument has a large, well-estimated slot preference — a
third measurement of §74's conclusion that positional bias is a property of the pair rather than of
the panel, and the most strongly estimated one. Any future use of this instrument on this kind of
material has to measure bias on its own pairs; inheriting a figure from a different experiment
remains unsupported.

**The pattern, offered as a direction and not a result.** Agreement runs **0.61 in `aligned` and
0.41 in `crossed`** — higher where every popularity covariate points at the label, lower where they
all point away, a spread of 0.20. That is the signature the strata were constructed to expose: a
judge reading prose scores above 0.5 in both, a pure popularity proxy scores near 1.0 and near 0.0,
and this sits between them and tilted toward popularity. **It cannot be reported as a finding.** The
arm is void, both intervals contain 0.5, and 46 pairs is thin. What can be said is narrower and
still worth writing down: **the first candidate produced no evidence that the panel orders matched
human prose on a reader-behaviour label, and what structure it did produce leans the wrong way.**

**The benchmark itself behaved as designed, which is the other thing this run tested.** The
prose-blind table came out exactly as constructed — `pick_more_followers` at 1.000/0.000,
`pick_fewer_followers` at 0.000/1.000, `pick_more_favorites` at 0.960/0.000 — so every popularity
rule is perfect in one stratum and worthless in the other, and the binding minimum is
`pick_fewer_views` at 0.52. That is the property the whole design rests on and it held on real
elicitation rather than only in the selection code. Had the strata been pooled, this candidate would
have averaged to **0.51** and read as an unremarkable near-chance result instead of a 0.20 spread
with a direction; `PRE_REGISTRATION["never_average"]` exists for exactly that reason and this run is
its first vindication.

**What this does and does not say about the programme.** It is one candidate, and the benchmark's
purpose is to rank candidates — a single failure does not condemn the instrument class. The obvious
next candidates are the ones §77's 2x2 already pointed at (a single plain question outperformed four
authored personas) and a stronger tier; both are configuration changes the harness already takes as
flags, at about $12 each. What it does say is that the cheap assumption — that the existing panel
would track an external label once the corpus was clean — is not supported, and §82's conclusion
stands unchanged and now for a second reason: this candidate could not be proposed for the §72
licence even if BEHAVIOUR were the right evidence class, which it is not.

### 79.2 The band holds at the stronger tier, and the first readable candidate fails toward popularity

The two candidates §79.1 named, run 2026-08-19: the question change alone, then the tier change on
the better question. 368 comparisons each, zero refusals, $11.67 and $26.58.
`results/taste-benchmark-intensity.json` and `results/taste-benchmark-sonnet-intensity.json`.

    candidate                     aligned   crossed   min      bias al/cr      outcome
    haiku, preference (79.1)       0.6100    0.4107   0.4107   0.380 / 0.327   VOID
    haiku, intensity               0.5550    0.4405   0.4405   0.335 / 0.298   VOID
    sonnet, intensity              0.6500    0.4048   0.4048   0.540 / 0.429   FAILS

**The question is not the bias lever.** §77's 2x2 measured intensity beating preference on sham
floor and margin, and none of that transferred here: the Haiku slot preference *worsened* slightly
(0.335/0.298 against 0.380/0.327), still five-plus standard errors outside the band. Whatever one
word of question buys on ablation pairs, it buys nothing on ~1,000-word matched human pairs.

**The tier is.** Sonnet at the same question holds both strata inside the band — 0.540 aligned,
0.429 crossed — so the positional collapse that voided §79.1, this run's first cell, and §83/§85's
near-twin arms is **capability-limited, not intrinsic to the pair class**. That is the most useful
instrument fact this benchmark has produced: bias-clean single judges exist one tier up, and every
"the panel cannot see X" result earned at Haiku now carries an implicit "at Haiku" that a ~$25 rerun
can test. The §85 near-twin voids are the first candidates for that rerun.

**And the first readable candidate fails the bar, with the signature §79.1 could only gesture at.**
Minimum agreement 0.4048 against the prose-blind floor of 0.52. The shape is no longer a direction
offered without standing: 0.650 with a lower bound of 0.51 where every popularity covariate points
at the label, 0.4048 with an interval spanning 0.5 where they all point away, a spread of 0.245 on
clean bias. A judge reading prose holds above 0.5 in both strata by construction. Two readings
survive and the benchmark cannot separate them: the judge proxies popularity's prose correlates, or
the conversion label is wrong exactly where it disagrees with popularity. Separating them is a
human question — §80's batch puts crossed-stratum pairs to paid readers, and that row of the batch
just became its most load-bearing.

**Programme position after three candidates.** No candidate has produced evidence of ordering
matched human prose by the reader-behaviour label; §82 stands for a third reason. What changed is
narrower and real: the bias precondition is now passable, so the protocol track (ensembles,
notice-then-judge) runs on a tier where its results are readable rather than void by default. Next
candidates in cost order: the §85 near-twin rerun at Sonnet (~$8, tests whether the near-twin law
is also tier-limited), then protocol variants at Sonnet against this bar (~$25 each).

## 80. The first paid batch is designed to answer two questions, and is not funded

[reader-batch-1.md](reader-batch-1.md) drafts the batch so one set of paid verdicts pilots the
headline protocol *and* anchors the machine panel. **It is not funded. Payment starts §59's
one-month clock and is an operator act.**

418 raw judgments over 209 pairs in four classes: 110 headline pairs (ours against matched human), 75
defect-manufacture pairs (ours against ours, on the three reader-named axes), 16 attention checks and
8 layout shams. Ten readers at ~42 judgments each, which is what makes the §59 clustered lower bound
computable on both dimensions at all.

**The design's load-bearing constraint is that classes B and C must never be the same instrument.**
Both look like "does the reader notice damage", and the runbook excludes readers who prefer planted
defects. If the planted defects were the reader-named ones, then excluding readers who miss the
interiority strip would **manufacture agreement with the human reader on exactly the axis the batch
exists to measure** — the batch would report that humans detect interiority loss because everyone who
did not was discarded. So attention checks use gross damage (`sentence_deletion`,
`connective_scramble` at full dose) where any attentive reader agrees, class B uses the subtle
reader-named defects where the answer is unknown, and **no reader is ever excluded on a class-B
judgment.** That rule is written before payment because it is the kind that gets relaxed when the
numbers come in thin.

**The declared frame is mid-list, deliberately.** Pre-LLM RoyalRoad LitRPG, one chapter per story,
10,000+ views, excerpted to ~1,000 words — the same frame §79 builds, so the covariates are already
recorded per pair. §61's fourth pre-registration says the frame *is* the claim, so what this batch
can support is "beats mid-list tier-matched human LitRPG" and nothing wider. *Mother of Learning* is
**excluded from the headline class** despite being the panel's most confident arm at 0.9844: it is
famous, recognition exclusions are paid-for judgments thrown away, and §77.1 already records why that
arm cannot carry a claim.

**What the batch can and cannot detect, stated before it is bought.** At §61's sizing, ~176 decisive
class-A judgments after an assumed 20% recognition-and-tie attrition sits inside the 100–150 band for
a true rate of 0.60 and nowhere near the 400–500 for 0.55. **This batch can certify 0.60 and cannot
certify 0.55.** A thin true margin yields a lower bound below 0.5, and the correct conclusion is then
"not shown" rather than "nearly shown".

**The em-dash row is why the batch is worth buying even so.** After §78 and §78.3 the machine column
on that axis is *empty* — the original number was an artifact and the corrected arm is void with an
interval containing 0.5. A human column there would not be an agreement measurement; it would be the
first measurement of that axis by anything.

## 81. The panel can see the interiority go and cannot see the stats flatten

`interiority_strip` and `stat_flatten` have existed since §74 and had never run. 224 comparisons,
`claude-haiku-4-5`, zero refusals, $8.34. `results/reader-defects.json`.

    arm                        pairs   win rate   bias     interval          ladder
    interiority_vs_matched         9     0.3889   0.5278   [0.1667, 0.6667]  DETECTS
    stat_flatten_vs_original      10     0.5437   0.5696   [0.4062, 0.6937]  BLIND
    interiority_vs_original        9     0.1111   0.6111   [0.0000, 0.2361]  VOID on bias

**The primary arm is the first clean single-variable comparison this instrument has produced, and
its two sides are matched to one word.** `interiority_strip` removes the sentences reporting an
inner state; `interiority_deplete_matched` removes the same word count from sentences reporting
none. Measured on the run: 9,602 words against 9,603, a 0.01% gap, and `layout_matched: true` —
both route through `_rebuild`, so both carry §78.1's separator downgrade and neither side has a
formatting advantage. The only difference left is *which* sentences went.

**The panel prefers the text that kept its interiority, and the honest reading is "suggestive"
rather than "established".** The ladder returns DETECTS because the pre-registered rule is a point
estimate at 0.40 and the arm reads 0.3889 — it clears by 0.011. **The interval is [0.1667, 0.6667]
and contains 0.5.** Both facts are reported because the second is the one that governs what may be
built on this: at 9 passages and 4 personas this arm cannot exclude indifference, and a result that
clears its threshold by a hundredth while spanning the null is not a licence for anything.

**That is a defect in the pre-registration I wrote, and it is recorded rather than repaired after
the fact.** §78.2's branches were also point-estimate rules and that was defensible there because
the effect under test was enormous; carrying the same shape into an arm designed to detect a subtle
defect was the wrong choice, and the right rule — threshold *and* an interval excluding 0.5 — has to
be declared before the next run rather than applied to this one. Under that rule this arm is
undecided. Under the rule actually pre-registered it is DETECTS. The two readings are both written
down so that neither can be quietly selected later.

**`stat_flatten` is a mapped hole.** The panel is indifferent to having the last live values in the
stat block blanked, at 0.5437 with an interval spanning 0.5 — and the point estimate sits on the
*wrong* side of indifference, meaning the panel very slightly preferred the flattened text. §74
predicted a near-null "because the book's stats are already flat, so there is nothing left to
flatten", and that prediction was wrong about the transform: the arm blanks 30 values across the ten
scenes, three per scene, exactly the `Level`, `HP` and `MP` slots §74 counted as the only informative
ones left. So the defect was manufactured and the panel did not see it. **BLIND here means "no
preference detectable at this n", not "proven blind"** — the interval is wide — but the direction of
the estimate makes "the panel quietly likes flat stat blocks" the live alternative to "the panel
cannot tell", and neither licenses selection on this axis.

**The confounded arm is void and its number is still the most useful thing in the table.** §78.2
predicted that comparing `interiority_strip` against the *original* would read stronger than the
matched comparison, because the original differs from it by formatting as well as by interiority.
Measured: **0.1111 against 0.3889**, with the confounded arm's interval `[0.0000, 0.2361]` not even
overlapping the clean arm's point estimate. It is void on positional bias at 0.6111 so it cannot
license a reading of its own, and the gap is not a clean estimate of the confound either — but the
direction is exactly the predicted one, and it is the second measurement in two entries of the same
thing: **an unmatched formatting difference produces a large, confident, meaningless preference.**
§78 found that at 0.0417 and this finds it at 0.1111.

**What this does and does not license.**

- **Interiority is the only axis in this repository with any evidence that the panel tracks a
  reader-named defect on a comparison whose confounds are matched.** It is not yet an axis anything
  may be optimised on: the interval spans indifference, and §72's licence requires more than a point
  estimate clearing a threshold.
- **Stats join the mapped holes.** A human named the defect; the instrument does not see it. Nothing
  may select on stat quality.
- Both rows now have machine numbers, which is the precondition
  [reader-batch-1.md](reader-batch-1.md) §6 names before the paid batch can be funded — and the
  batch is the way to find out whether *humans* separate on either axis, which is the comparison
  that would make interiority an optimisable axis rather than a suggestive one.

**One code gap, recorded.** `verdict`'s `confound_note` only fires when the matched and confounded
interiority arms read `{DETECTS, BLIND}`; here the confounded arm was VOID, so the note stayed null
and the comparison above was written by hand. The condition should key on the *presence* of both
arms rather than on a particular pair of outcomes.

**No sham arm ran, and not paying for it is the point.** §78 measured why `rewhitespace` cannot be
this design's floor, its number is already recorded twice and already called unusable, and the
primary arm needs no floor because its two sides carry identical formatting by construction. That is
80 comparisons and about $2.80 not spent on reproducing a figure the ledger already refuses to use.

## 82. The §72 licence is not earned, and no machine measurement can earn it

The taste-gap programme's terminal item was: *only after the em-dash control, the defect-manufacture
arms and the external-label benchmark, and if and only if a judge configuration passes
human-external agreement on the defect axes, run the PREFERENCE calibration on
`judge.span_select.v0` and propose activating plan-level search.* All three precursors have now run
(§78.3, §81, §79). **The licence is refused, and the reason is structural rather than a matter of
the numbers falling short.**

**Two definitions already in the code decide it.**

`domain/calibration.py` defines PREFERENCE as *"a **human's** blinded, position-swapped choice
between two texts"*. Not a judge's, not a panel's. The class §72's judge path requires is
constituted by human answers, so **no quantity of machine elicitation can produce a
PREFERENCE-class row** — the panel could agree with every external label in existence and still not
be the kind of evidence the gate names.

And the same enum classifies the label this programme spent its effort on: BEHAVIOUR is *"reader
behaviour aggregated over other authors' whole stories, e.g. `followers / total_views` …
**recordable, rankable, and it refuses nothing**, because its grain is STORY and nothing in this
system gates a story."* That is precisely `conversion`. So §79's benchmark, however clean, produces
BEHAVIOUR-class evidence at STORY grain. It can **rank judge candidates**, which is what a
benchmark is for. It cannot **license** one.

`application/plan_search.py` states the position plainly and correctly: *"No such row exists today;
the human path is the production path, and the gate being the license is the entire point."* That is
still true and this entry does not change it.

**So the ordering the programme was written under was wrong in a useful way.** Items 1–3 were all
machine measurements, and the gate they were supposed to open is one that only item 4 — the paid
reader batch — can supply evidence for. The dependency is not *benchmark → licence*; it is:

    §79 benchmark (BEHAVIOUR, rankable)  ->  selects WHICH judge configuration is worth paying to
                                             validate
    §80 paid batch (PREFERENCE, human)   ->  supplies the evidence class the gate actually names,
                                             on the selection task itself per §6.6
    §72 judge path                       ->  opens, and its calibration goes stale on use

**The state of the defect axes, for the record, since the gate is refused on class rather than on
these.** Even taking the machine numbers at face value, no axis supports a licence:

    axis          machine state                                   human state
    em dash       VOID on bias, interval [0.2273, 0.5139] (§78.3)  none
    interiority   0.3889; DETECTS registered / UNDECIDED strict,
                  interval [0.1667, 0.6667] contains 0.5 (§81)     none
    stats         BLIND at 0.5437, estimate on the wrong side
                  of indifference (§81)                            none

**The human column is empty for every axis, so "human-external agreement" is not a bar this project
currently fails — it is a bar nothing has been measured against.** One axis (interiority) has
suggestive machine evidence on a properly matched comparison, which is one more than existed before
§81 and none at all under the stricter rule.

**Actions taken, and not taken.** The PREFERENCE calibration on `judge.span_select.v0` is **not**
run and no activation of plan-level search or bounded revision is proposed. Wiring the current panel
into generation stays refused, now on firmer ground than §74's: that entry refused it on a number
§78 withdrew, and the refusal survives its own evidence being withdrawn because the remaining
grounds are independent — the panel is measured near-blind to global belonging (`transplant`
−0.0125), it cannot see one of the two defects a human named (§81's stats row), and the axis it may
be able to see cannot exclude indifference at this n.

**What would change this, in order.** Close the em-dash axis at higher n (§78.3's named remedy, ~216
elicitations); run §79's benchmark across judge candidates and pick the one that clears 0.52 as a
minimum across strata; then fund §80's batch, whose class-B pairs put the same defect axes to humans
and whose class-A pairs pilot the headline. Only the third step produces PREFERENCE evidence, and
only on the selection task does it license §72.

**A note on what this programme actually bought.** It set out to close the panel–human taste gap and
instead established that the gap was unmeasured in both directions: the one axis the panel appeared
decided on was an artifact (§78), the one external-label result was void and covariate-imbalanced
(§77.1), and the label underneath it cannot be covariate-matched at all (§79). What exists now that
did not before is an instrument with a real bar, two defect axes with machine readings, and a
costed batch design. The gap itself is still unmeasured, and it is now clear that measuring it costs
money rather than compute.

## 83. Four states of mind, one voice: the register is invariant to simulated phenomenology

The directive asked whether simulating unconventional writer states — alcohol, hallucinogens —
moves the output. `research/quality-measurement/writer_states.py` is the instrument; its module
docstring carries the design and `PRE_REGISTRATION` the branches, committed before the first
call. 32 retells on the book's own drafter, 192 panel comparisons, zero refusals anywhere,
$6.10 + $8.68 equivalent. `results/writer-states.json`.

**The design in one paragraph.** Every scene of `toll.db` was retold four times by the model
that drafted it, differing only in a system-prompt state block: clear-headed (`sober`, the
anchor), most of a bottle of wine (`drunk`), a moderate psilocybin dose two hours in (`trip`),
and a cup of tea (`tea`) — a placebo state, semantically inert, whose pair against sober bounds
instruction-noise plus draw-noise the way `rewhitespace` bounds edited-ness. States are
phenomenology, never style instructions — what the evening is like, not what the sentences
should do — because "write looser" would measure prompt-following, which §70 already measures.
One craft rule bans the caricature (no typos, no slurring), so the panel could not be handed
orthographic damage and call it a state. Every comparison is retell-vs-retell so the retell
operation cancels; system-voice preservation is verified rather than trusted.

**The controls all held, which is what makes the null a measurement.** 55 of 55 protected
system-voice spans byte-identical in every arm; arm word counts 1,015–1,042 against the sober
1,035; the drafter never declined a state. Nothing §74-shaped is under this result.

**The panel voided itself on all three arms, and the voiding is the third measurement of the
same law.** Chose-A rates: drunk 0.828, trip 0.762, tea 0.734 — every arm outside the
pre-registered 0.40–0.60, so no preference here is read. §78's tail observed that positional
bias is a property of the pair rather than the panel, discriminable pairs running clean and
indiscriminable ones running biased. Two same-model fair copies of the same scene are the most
similar pairs this panel has ever been shown, and they produced its most positional answering.
The consequence for the writing loop is worth the run on its own: **in-loop selection between
same-model rewrites would be mostly layout**, whatever the win rates appear to say.

**The mechanics are not voided, and they say the states never reached the prose.** Against the
sober retell, per 1k words, with tea as the drift floor:

    arm      em dash   interiority   stakes    sent. mean   words
    tea       +0.39      +0.28        +0.04      -0.17      -20.4
    drunk     -0.43      +0.24        -0.09      +0.09       -0.4
    trip      +1.25      +0.22        +0.24      +0.06       +7.0

The one pre-registered mechanical prediction — trip raises `interiority_per_1k`, psilocybin
phenomenology being inner-experience content — is **refuted**: the placebo moved the proxy more
(+0.28) than the trip did (+0.22). The trip em-dash bump, the largest delta on the table and in
the direction of the machine tell, dissolves per-scene: mean +1.25 against a per-scene sd of
2.53, carried by two scenes of eight, sign test 5/8. Drunk's em-dash cut is 4/8 at sd 3.13.
Sentence rhythm and TTR did not move at the second decimal in any arm. Reading the openings
confirms what the numbers say: the four retells of a scene are near-twins.

**What this prices and what it does not.** At this dose — state as system-prompt phenomenology,
under fair-copy craft rules that pin events, order, POV, length and typography — simulated
intoxication does not move the prose in any direction any instrument here can see. The INERT
branch, reached through the mechanics while the panel branch reads VOID. It does *not* price
three doses above it, named now so a later run doesn't rediscover them: state under **free
drafting** (a fresh scene from a brief, where attention has room to wander and event selection
itself can carry the state); an **explicit licence to deviate** (the caricature ban and the
retell clamp may suppress exactly the variance a state would carry — a declared trade, made so
the first run could not be won by typos); and state expressed through **revision** rather than
generation. The clamp was chosen to make a positive result clean; the cost is that the null is
narrow.

**The residue is a corpus.** 32 fair copies, four per scene, near-twins by measurement — the
hardest discrimination material this project owns. A future panel that can separate them is a
different instrument from the one that just answered a side, and `writer-states-gen-raw.jsonl`
is the fixture that test was missing.

## 84. The taste gap becomes the priority, and the plan for closing it is a programme

Operator directive, 2026-08-18: researching a machine panel that can stand in for human
judgment is the project's priority. [machine-taste-program.md](machine-taste-program.md) is the
plan — written under §82's constraint rather than against it, since "as good as human judgment"
is only earnable as **scoped licences anchored by one paid human batch**, never as a blanket a
machine-only result could confer.

The programme in one breath: **JudgeBench** (five fixture families this repo already owns,
including §83's near-twins read for *calibrated indifference* rather than forced choice — the
single largest design change) grades a ladder of candidate judges; the winner is frozen as
panel v2 in a ledger entry *before* [reader-batch-1.md](reader-batch-1.md) is funded, so the
batch's per-axis agreement matrix is read against a judge nobody could shop for after the
numbers arrived; the matrix assigns per-axis licences (selection between discriminable
candidates, then in-loop feedback under monthly probes) with §72's expiry rules attached. The
certified repair pairs now generating join the batch's class B in the repair direction, which
is the interventional test `personas.py`'s reason codes have owed since §70. Kill condition at
programme level: no candidate clears §79's 0.52 external-label bar with clean bias — then
machine taste is unavailable at this frontier, and the fallback (humans judge, machines
certify) is written in the plan rather than discovered in disappointment.

## 85. The repair direction lands: the panel's first clean interval, and a voice that moves when shown

`repair_generation.py`, pre-registered in-module: three minimal revisions of each of 8 scenes
(em-dash removal by rewrite, interiority addition, typo-fix placebo) plus an exemplar-voiced
retell, 32 generations and 192 panel comparisons, zero generation refusals, $7.41 + $7.26.
`results/repair-generation.json`.

**The placebo came back byte-identical, which is the floor at its best and a band at its
worst.** All eight typo-fix revisions returned the scene unchanged — the revision operation at
an inert instruction drifts nothing, so every pair was skipped as a manufactured tie (the NaN
bias row is zero elicited pairs, not a failure). But a zero-drift placebo makes the
pre-registered containment band zero-width, and the em-dash arm's compliance reads 3/8 because
interiority deltas of |0.002–0.016| per 1k — one word's worth — formally exceed a band of 0.0.
§81's lesson repeats in a new costume: the rule as registered is reported (3/8), the defect in
the rule is recorded here, and nothing is retro-passed. The *on-axis* fact is unambiguous:
**8 of 8 scenes had every prose em dash removed at word-similarity ≥ 0.978 and growth ≤ 3.4%**,
with every protected span byte-intact. The certified pairs §80's class B needs exist.

**`repair_interiority` is the first arm in this project's history to clear its bias
precondition and exclude indifference, and it does so in the repair direction: 0.9509, bias
0.4918, interval [0.8710, 1.0000].** Read against §81's damage direction (0.3889, interval
spanning 0.5), the two now agree in sign: the panel dislikes interiority removed and strongly
prefers it added. Length is the named confound — the treatment grows scenes ~10-13% — and the
existing evidence against "prefers more words" is `filler_inject`'s standing as a detected
DEGRADER: matched-scale padding is *dispreferred* by this same panel. What no machine can
answer is the sharper worry: the added sentences are *reported* inner state, and a panel
preferring told feelings is machine taste for exactly the defect craft warns about. The
operator read (below) is the arbiter, and the question rides on it.

**`repair_emdash` voids on the near-twin law, as pre-registered.** Bias 0.6949 at similarity
0.98 — §83's prediction confirmed on fresh pairs, and the panel's directional lean (0.2734,
toward the dashed original) is therefore not read. The em-dash axis stays a human question,
which is what §80 already budgeted for.

**The exemplar arm answers §83's open question: the register moves when the voice is
demonstrated rather than described.** 8/8 scenes land nearer the exemplar-source centroid than
the sober retell does; 6/8 move further from their original in z-scored feature space. The
described-state channel is closed (§83) and the demonstrated-voice channel is open — the first
working register lever this project has measured. Its panel arm voids at bias 0.7656 and its
interval [0.4844, 0.8125] spans 0.5, so whether the moved voice is *better* is unmeasured; it
joins the operator read.

**An operator read is issued with this entry**: six blinded pairs (two per axis), orientation
derived from the pair digest, key at `results/operator-read-key.json` and deliberately not
printed in the session. The operator has seen the defect names all day, so this read is
directional evidence, not a naive measurement — recorded here so nobody later mistakes it for
one. What it uniquely answers: whether the panel's 0.95 on interiority is a preference for
prose or for bolted-on feeling, and whether the exemplar arm's measured movement reads as a
voice or as noise.

### 85.1 One tier up, the repair is unanimous, the voice arm turns readable, and the dash stays dark

§79.2's cheapest named follow-up, run 2026-08-19: §85's panel re-elicited at `claude-sonnet-5`,
same pairs, same question, generations replayed 32/32 from cache. 192 comparisons, zero
refusals, $13.62. `results/repair-generation-sonnet.json`.

    arm                  haiku (§85)          sonnet               bias h → s        sonnet interval
    repair_interiority   0.9509 (clean)       1.0000 (clean)       0.492 → 0.500     [1.000, 1.000]
    exemplar             0.6406 (VOID .766)   0.6484 (clean .490)  0.766 → 0.490     [0.500, 0.797]
    repair_emdash        0.2734 (VOID .695)   0.4844 (VOID .609)   0.695 → 0.609     [0.359, 0.594]

**The interiority repair saturates: 64 of 64 comparisons, both orientations, bias exactly 0.5.**
Two tiers now agree with clean preconditions — 0.95 at Haiku, 1.00 at Sonnet — that the panel
prefers the scene with its inner life restored. This is the strongest machine result the project
has, and its one open reading is unchanged and un-machinable: the added sentences *report* inner
state, and a panel drawn to told feelings would look exactly like this. The operator read holds
the axis's casting vote.

**The exemplar arm crosses from void to readable, and reads preferred.** Sonnet's bias lands at
0.4898 where Haiku's was 0.766, and the rate holds at 0.6484 — the pre-registered PREFERRED
branch at the point threshold, with an interval whose lower bound sits exactly on 0.5. Under
§81's stricter rule (threshold and interval excluding the null) it is suggestive rather than
established at n=8. Read with the mechanics (8/8 scenes nearer the exemplar centroid), the
demonstrated-voice lever now has direction, magnitude, and a panel that does not object —
what it lacks is n.

**The em-dash axis stays dark, by 0.0087.** Sonnet's bias on the nearest-twin pairs is 0.6087
against a band edge of 0.60 — §78.3 refused a 0.0032 miss and this one is not closer. What can
be said without reading the arm: the point estimate moved from Haiku's 0.2734 to 0.4844, so the
lean toward the dashed original did not survive the tier, and the axis looks BLIND-shaped rather
than OPPOSES-shaped. It remains the batch's question, exactly as §80 budgeted.

**The law gets its cleanest measurement yet, within one run at one tier.** Bias against pair
similarity: interiority (+10% added text) 0.500, exemplar (full retell) 0.490, em-dash (0.98
word-similarity) 0.609. Same panel, same day, same question — discriminability alone moves the
bias, and the near-twin collapse is now measured as *mostly* tier-limited: Sonnet cleans two of
three pair classes that voided Haiku wholesale, and shrinks the third from 0.695 to the band's
doorstep. Panel-v2 selection under the programme should treat tier as the first debiasing lever
and protocol as the second.

## 86. The anchor is priced, and three of the four unanchored tiers are blocked by something other than money

Operator directive, 2026-08-19: price the anchor — find out whether a validation stack using
zero solicited human labour can bound judge divergence and exploitation tightly enough to earn
scoped selection licences, so that the anchoring question stops being an assumption on either
side. [judge-validity-program.md](judge-validity-program.md) is the pre-registration, one tier
is built and selftested, none has been run, and **the pricing exercise returned a price for
every tier before a single call was bought**, which is the outcome the directive asked for even
though it is not the one it hoped for.

    tier   what it is                       money          calendar     blocked by
    T0     axiom battery                    $25            2.5 h        nothing; built
    T1     cross-lineage convergence        $12-40/lineage days         provider access
    T2     prospective retention forecast   ~$15/run       11-13 weeks  its own premise
    T3     exploitation / Goodhart budget   ~$40-80        days         T1

**The falsifier the directive pre-registered is accepted for one of the two claims inside it and
refused for the other.** *"If T2 and T3 pass, selection requires solicited human evidence is
refuted at those scopes"* welds together an empirical claim — no machine-only evidence can bound
judge–reader divergence — which is falsifiable and worth buying, and an instrumental claim —
§72's judge path requires human evidence — which is true **by definition** in
`domain/calibration.py`, where `PREFERENCE` is constituted as *"a human's blinded,
position-swapped choice between two texts"*. No experiment refutes a definition. §82 refused the
licence on evidence class, and an entry claiming a machine measurement had overturned that would
be claiming a definition had been measured away. The amendment that *would* be proposed if T2
performed is written down now rather than after the numbers — a `FORECAST` class at `STORY`
grain, absent from `veto_for` so it refuses nothing with zero code, and **not** accepted by
`plan_search`'s judge path — so that the class cannot be shopped for later, which is §84's
freeze rule pointed at the instrument instead of at the judge.

### 86.1 The class boundary the whole ceiling rests on is enforced by a docstring

Checked in source while writing that section, because everything above depends on it:

- `plan_search` records a licensed judge's verdicts through **the same pair machinery humans
  use**, `reader_id` set to the licensing calibration id, `recognized=False`. The comment says
  so and §72 records the intent.
- `preference.analysable_judgments` — the function deciding which rows a PREFERENCE holdout may
  be denominated in — filters on `verdict is not None`, `not recognized`, and `verdict is not
  NOT_SURE`. **It never inspects `reader_id`.** Neither does `pair_verdicts_digest_for`.
- There is no source column, no `CHECK` constraint and no runtime predicate anywhere asserting
  that a preference verdict came from a person. The human-only property is prose in an enum
  docstring.

**So once one human-anchored calibration licenses one judged tournament, the judge's own
verdicts join the pool the next PREFERENCE calibration is measured on, and nothing counts them
separately.** §72's expiry bites first — the judge's writes move the digest and stale its own
licence — but staleness forces re-calibration, and re-calibration is where the contamination
enters, because the re-measured holdout now contains machine answers under a class whose
definition says human. **§86.7 corrects this entry twice more in the same direction**: the
selection door checks no measured number at all, and the grain guard cited below is wired to a
different door. This is inert today, because the calibrations table is empty and there is
no row to launder into. **It stops being inert the day §80's batch lands**, which is the argument
for closing it while it is free: a reserved reader-id prefix at the one write site, excluded in
`analysable_judgments`, with a test that fails if a machine row ever counts toward a preference
holdout. Not done here — that is production promotion semantics and outside a research
directive's scope — and recorded so that no licence in the programme reads as safe until it is.
**It was closed the same day and not by this branch**: a parallel session took this subsection as its
brief and landed the denominator half as §86.6 below, which is the shape this entry asked for.

### 86.2 T0 is built, its null is verified, and it predicts the incumbent's disqualification

`research/quality-measurement/axiom_battery.py`. Six axioms as disqualifiers — indifference,
format invariance, dose monotonicity, transitivity, paraphrase stability, within-item
consistency — plus per-arm positional bias computed free on all of them. 6 scenes, 54 pairs,
**720 comparisons, ~$25, ~2.5 hours** of wall clock at the CLI transport's measured 4.9 calls
per minute. `--dry-run` — the null through the real plumbing — reads **DISQUALIFIED** on six
axioms with transitivity unreadable, and the module exits non-zero if a null ever clears.

**Three of its arms have never been elicited in this project.** `Elicitor.variant_win_rate` says
in its own docstring that "the original compared against itself is 0.5 by construction and never
elicited"; that assumption has been load-bearing since §70 and A0 is the first check of it.
Within-item repeat consistency has no measurement at all, because every pairwise run to date used
`n_samples = 1`. And question-wording stability has never been asked, which is the gap that
matters most: across the pairwise record the persona is nearly inert — persona-to-passage
sum-of-squares ratios of 0.0028, 0.0071 and 0.0342 — while one word of question change moved the
sham from 0.7833 to 0.6833 and the bias from 0.5874 to 0.6111. **The question is the load-bearing
knob and nothing has ever tested whether a verdict survives rewording it.**

**The incumbent is predicted to fail A1, and the prediction is registered so it cannot be
reported later as a surprise.** §78 measured this panel preferring blank lines at 0.0417 on Haiku
and 0.0000 on Opus at textbook-clean bias 0.5000, so the instrument is not format-invariant. What
the arm buys given that is the magnitude at the *mild* dose — the separator downgrade riding
silently on seven registered ablations — currently known only as the 0.2778 gap between §81's
matched arm and its confounded twin, and that twin is void on bias at 0.6111.

**Two defects in the pre-registration were caught by the selftest before any call was made**, and
neither is repaired after the fact because neither had a number yet. The monotonicity rule first
demanded a strictly falling win rate end to end, which a *perfect* judge cannot produce — it
saturates at 0.0 on every rung — so the rule now reads "non-increasing and top rung below 0.5",
which still excludes the tie-everything strategy. The ICC arm first computed between-pair
variance inside the ladder alone, where a perfect judge answers every pair identically and the
statistic kills what it exists to certify; it now runs over the whole battery's pairs and gates
on Spearman–Brown aggregate reliability, because a bar on the single-comparison figure would
disqualify an instrument that is noisy per call and fine at panel width.

**The battery is jointly non-trivial and the selftest executes that claim rather than asserting
it.** Ten synthetic oracles run through the whole arithmetic offline: the perfect judge clears
every axiom, every pathology dies somewhere, and A0–A4 each have an oracle they are the *sole*
cause of death for — including `unseparable_forced`, a judge that answers correctly wherever a
difference exists and manufactures a choice where none does, which is §83's near-twin failure
written as a unit test. A5 and A6 have no sole-cause oracle and the output says so and says why,
rather than leaving them looking proven.

**The ladder is nested by construction and the reason is measured.** On the CDG battery at five
doses **no degrader was dose-monotone in the declared direction, and the cleanest dose-response
curve belonged to the rename sham** — the transformation that damages nothing. So the ladder here
rotates a prefix of one fixed permutation, every position displaced at a low dose stays displaced
at every higher one, and the certificate records displaced count, word-multiset identity and
layout identity per rung. `rewhitespace` is deliberately not an arm: void twice on bias (0.9375
Haiku from 16 decided, 1.0000 Opus from 25) and already refused as a floor.

### 86.3 T2's premise is self-contradicting, and that is only its first blocker

`taste_benchmark.MIN_VIEWS = 10_000` exists because below it `followers / total_views` is noise.
Measured on the population a prospective design would actually enrol — 2025-cohort LitRPG serials
in the cached shards — **median total views 1,245 at a median age of 98 days, median followers 5,
p10 of 74 views and 0 followers, and only 22.3% ever clearing the floor.** A serial is newly
published exactly when its counters are near zero, and a retention ratio needs a denominator.
Restricting to serials that do clear the floor conditions on an outcome correlated with the
label, which is a collider rather than a filter. **"Prospective retention on newly published
serials" cannot have both halves at 30 days**; the repair is not a better metric but a longer
calendar, and the memorisation-safety property survives that while the schedule does not.

**§79's arithmetic carries over and §79's repair does not.** The identity
`followers_hi/followers_lo = (conv_hi/conv_lo) × (views_hi/views_lo)` is a property of *ratios*,
not of those two counters, so any retention defined as `ΔF/ΔV` inherits it and differencing buys
nothing. Defining retention against a t0 baseline escapes the identity — `F(t+30)` is
post-treatment and invisible to the judge — but **the `crossed` stratum is built by testing the
popularity covariates against the already-known label, and at t0 the label does not exist.** So
the sign-as-instrument repair is structurally unavailable prospectively: T2 inherits §79's
confound without §79's antidote. What is left is incremental validity against a prose-blind
forecaster computed in the same pass, which turns the bar from a number into a formula at
pre-registration time and is acceptable only if declared that way in advance.

**The positional precondition is the third blocker and it has the largest measurement behind
it.** T2's fixture is a matched pair of ~1,000-word openings by two different authors, and on
that class the record reads: `mol_vs_rr` 0.4375 (64 decided, in band, unmatched material),
`rr_high_vs_low` 0.3810 (64, VOID), and §79.1's benchmark 0.3800 aligned / 0.3274 crossed /
**0.356 pooled over 368 decided, missing the band by 0.14 at roughly 5.8 standard errors**. The
two arms whose construction is closest to T2's are the two that voided. The generalisation is the
ledger's own — bias is a property of the pair, demonstrated most sharply by the same 72 cells
moving from 0.4857 to 0.6032 when only the compared text changed — so `mol_vs_rr`'s clean figure
cannot be inherited into T2's pairs either, and the rule is not "T2 will void" but **"T2's bias
must be measured on T2's own pairs, and the only two measurements on the nearest material both
voided."** The screen for that already exists and costs $12: §79's benchmark, read for positional
band first and agreement second.

**And the rest of the price, measured rather than estimated.** No live data path exists — the
RoyalRoad source is a frozen snapshot whose newest chapter is 430 days old, and BookCrawler is a
Wayback-only client that rewrites royalroad.com URLs into archive replays and never fetches the
site. Terms of service are unread: a grep of that repository for terms, robots or legal returns
zero hits, and the only compliance reasoning on disk concerns the Internet Archive, a different
party. **Every byte this project has ever taken from RoyalRoad came through Wayback**, so a daily
direct crawl is a new outward-facing act and an operator decision. Calendar is 11–13 weeks
minimum: ~3 weeks of enrolment (241 new LitRPG fictions in a real 3-week window, 182 enrollable at
≥3 chapters in 30 days, 88 disjoint pairs after matching on first-30-day word volume), then two
30-day readings. Only 43.0% of shard-3 LitRPG fictions published anything in days 30–60, and
abandonment is plausibly caused by the same latent quantity retention measures, so the censoring
is informative and has to be pre-registered as an outcome rather than a filter. And 17.7% of 2025
LitRPG serials declare AI-assisted content against 0.3% in 2021, while `era_cohort` labels every
post-2022 fiction outside the `human_pre_llm` pool `taste_benchmark` admits — so a prospective
corpus is not comparable with §79's without a declared change of frame.

**Even a clean pass licenses nothing on its own.** Retention over other authors' whole stories is
`BEHAVIOUR` at `Grain.STORY`; `veto_for` refuses it **by class, before grain is consulted**, and
`Grain.covers` independently bars story-grain evidence from licensing a unit-grain decision.
**Both of those guard the refusal door rather than the selection one — see §86.7, which measures
which door is actually wired.**
§82's ruling on §79's benchmark applies verbatim — it can rank judge candidates, it cannot license
one — and the transfer from "orders other authors' openings" to "may choose between two drafts of
our span" runs from the easiest discrimination in the corpus to the hardest, since candidate spans
are near-twins and §83 measured near-twins void.

### 86.4 T1 and T3, and the one thing T3 can already say

**T1 needs provider access this machine does not have.** One frontier lineage is reachable; the
local tier is measured below the instrument's capability floor, `gemma3:4b` being void on bias
twice at chose-A 0.8021 over 389 decided (z = +11.9) and 0.8095 on intensity. Three corrections
ride with the design: the within-lineage floor must be a *protocol* resample rather than a
temperature one, or the control cannot fail in the intended direction at either extreme;
convergence may be computed only on bias-clean arms, since four lineages sharing a positional
artifact would converge beautifully and mean nothing; and **a stronger tier is not the known fix
for bias** — Opus-5 read the same three repair arms at 0.5000, 0.7000 and 1.0000, pooled 0.661
over 177 decided.

**T3 is blocked on T1 by definition, since "held out" means "another lineage".** Within one
lineage it would bound *protocol* exploitation and say nothing about the taste exploitation that
matters. Two things survive that anyway. The axiom battery is the one fully independent
off-target measure, because it is not a judge: prose optimised toward A while drifting into ties,
length or layout is caught by A0–A2 whatever any judge thinks. And **one implication is checkable
the day the number lands, for nothing**: `plan_search` runs K=3, so a measured budget of
"divergence begins at N=2" puts the search this project already ships over budget on arrival, and
the comparison has to be made in the same units.

### 86.5 What the stack cannot bound, and the correction to the directive's own framing

The directive says whatever these tiers cannot bound is *the measured residual that human batches
exist to cover*. **T0–T3 bound divergence from axioms, from other judges and from a behavioural
label; none of them bounds divergence from reader preference, because that quantity is
constituted by reader preference and no unsolicited source of it exists.** The residual can be
named — absolute quality, told-versus-shown interiority (exactly what §85's 0.9509 leaves open),
the near-twin region where every measurement voids, and global structure, where the panel sits at
`transplant` −0.0125 and the CDG scorer is independently near-null at AUC 0.5090 — and it cannot
be sized without the thing it is the residual of. So the programme prices the anchor in the sense
of naming what must be bought and in what order; it does not price it in the sense of measuring
what is missing, and that limit is pre-registered here so no later result can be read as having
achieved the stronger thing.

**What this reclassifies the programme as.** Not a substitute for the anchor — **insurance on
it.** §84 froze panel v2 before funding so nobody could shop for a judge after the human numbers
arrived; the risk that rule manages is paying four figures to anchor a judge that turns out void
on its own preconditions, which is precisely what §79.1's candidate was. T0 at $25 and the §79
screen at $12 make that outcome cheap to discover, and the batch stays the only source of the
residual. The sequence that follows differs from the directive's by one edge: **the batch is
funded in parallel with the machine tiers rather than after them**, because T2 alone spends more
calendar than the batch's whole turnaround and must not be allowed to delay the one instrument
that reaches what the tiers cannot.

**Actions taken.** The programme document and this entry; `axiom_battery.py` with its
pre-registration, its ten-oracle selftest and its verified null; one paraphrase question added to
`personas.PAIR_QUESTIONS` under four declared invariants, additive so no cached record changes.
**Not taken**: no paid elicitation, no production change to the preference plumbing, no T2
pre-registration issued, and no scraper written against a site whose terms nobody in this project
has read.

### 86.6 The laundering path §86.1 named is closed at the denominator and left open at the digest

(§86 and its subsections land on `claude/judge-validity-pricing-9ea30a`; this addendum is
numbered to sit under §86.1, whose defect it closes. Until that branch merges the ledger
reads §85.1 → §86.6, with §86 itself absent.)

**What changed.** `domain/preference.py` now reserves a reader-id prefix for rows a machine
wrote — `MACHINE_READER_PREFIX = "judge:"`, with `machine_reader_id` to mint one and
`is_machine_reader` to test one, all three named beside `UNASSIGNED_READER` so a future write
site cannot acquire the mint without the test. The single machine write site — the §72 judge
in `plan_search`, which is still the only one — stamps `machine_reader_id(calibration_id)`
instead of the bare calibration id, and `analysable_judgments` excludes the prefix. That
function is the one chokepoint every consumer of the preference holdout count already went
through (`handlers._craft_ladder`, both CLI surfaces), so the exclusion needed no second site.

**The decision §86.1 left open: machine rows still move `pair_verdicts_digest_for`, and that
is deliberate.** §72 states the price of the judge path — "judge verdicts move the
answered-verdict digest and stale the calibration that licensed them", one calibration buying
roughly one judged tournament — and refunding it would turn one licence into unlimited judged
tournaments. The laundering defect was never about the staleness *address*; it was about the
holdout *denominator*, and the two are now separately correct. §86.1's sharper reading — that
staleness forces re-calibration and re-calibration is where the contamination entered — is
what this closes: the judge still burns its own licence, and the re-measurement it forces is
now denominated in human rows only. The rows themselves are kept on record and in the digest,
the same shape recognition already has (§61 pre-registration 3): a row analysis must skip is
still a fact about the verdict set.

**Pinned in both directions**, because either half silently reverting restores a live defect:
`test_a_machine_written_row_can_never_denominate_a_preference_holdout` (20 machine verdicts
must not inflate a 50-row human holdout, and the calibration arithmetic that consumes the
count refuses on size rather than promoting quietly),
`test_machine_rows_still_stale_the_licence_that_bought_them` (the digest moves, the count does
not), and the end-to-end pin inside
`test_a_licensed_judge_selects_through_the_same_pair_machinery` — after a real licensed
tournament, `analysable_judgments` is empty and `judge_license` has gone stale. Verified by
mutation: dropping the filter fails all three; adding the same filter to the digest fails two.

**Deliberately left alone.**

- **No source column, `CHECK` constraint or store-level refusal.** The prefix is a mint-time
  convention honoured at one write site, which is weaker than a schema and is the whole of
  what "minimal" bought here. The dangerous direction — a *future* machine write site that
  forgets the prefix — is not catchable by any constraint on a free-text column anyway; it is
  held by there being one write site, by the mint and test being named together, and by the
  tests above. A real fix is a `source` column on the pair table with a migration, and it is
  worth doing the day a second machine writer exists.
- **No guard refusing a human `--reader judge:…` at the CLI or import path.** That mistake
  under-counts a real reader's row, which is the safe direction, and adding the guard means
  touching two operator surfaces to prevent an error nobody has made.
- **The win-rate path is untouched, because it was never exposed.** Judge rows are internal
  (`rev` vs `rev`) under `INTERNAL_PROTOCOL`, and `system_side` returns None for a pair with no
  human member, so `cmd_win_rate` already counted them as system-vs-system and kept them out of
  every observation and every bound. The hole was the holdout denominator alone.
- **No backfill.** §86.1's premise holds: the calibrations table is empty on every branch, so
  no licensed tournament has ever run outside a test and no bare-calibration-id machine row
  exists to rewrite.
### 86.7 T0 runs: the incumbent is disqualified on three axioms, and the battery that disqualified it needed a correction first

720 comparisons, 562 fresh and 158 replayed, `claude-haiku-4-5`, **$26.09**,
`results/axiom-battery.json`. The run was killed at comparison 158 by a workstation shutdown and
resumed losslessly off the digest cache — a fifth entry now sits in the RUNBOOK's list of ways to
waste a paid run, because the load that killed it was a CPU-bound null simulation running *beside*
the elicitation on a transport whose compute is remote. The elicitation was what died, not what
caused it.

**Verdict, both readings, neither selected:**

    reading          overall        failed                                    unreadable
    as registered    DISQUALIFIED   A0, A1, A2, A4, A6                        A3
    corrected        DISQUALIFIED   A2, A4, A6                                A3

#### The correction, declared mid-run from simulation with no elicited verdict read

`--operating-characteristic` asks the question the selftest cannot: not whether a *deterministic*
perfect oracle clears the battery — it does — but what the battery does to a judge that is right
on average and noisy per call. **As registered, this battery disqualifies a genuinely good
stochastic judge 82-100% of the time.** The mechanism is arithmetic and it is embarrassing: A0, A1
and A6 read a positional band off the *decided* comparisons, and a judge that correctly declines
to choose leaves almost none. At the tie rate §85 measured on layout-only shams, an identity arm
yields about ten decided comparisons across six scenes, and at that count an **unbiased** judge
violates 0.40-0.60 by sampling alone 35% of the time. **The band was failing the judge for having
behaved correctly** — §85's zero-width containment band in a new costume, and the second defect in
this programme's own pre-registration to be caught by simulation rather than by data.

The repair is one constant: a band is read only on arms carrying at least 30 decided comparisons,
which is where the standard error of a rate falls under the band's half-width. It changes no
request text, so every comparison already bought replayed unchanged and the correction cost nothing
in quota. Both readings are computed and printed for every run from here.

**It is not a full repair and the number says so.** Corrected, the battery still disqualifies a
good judge on 0.31 of runs at the repo's measured heterogeneity and 0.65 at strong heterogeneity,
the residual driver being A3, whose cycle null treats scenes as independent. **So a bare
DISQUALIFIED from this instrument is not yet evidence about a judge.** What licenses the reading
below is that the three surviving failures carry effect sizes the false-fail rate cannot produce.

#### A6 is the finding, and it is the largest positional bias this project has measured

    arm             chose-A   decided   in band
    ladder            0.8151      568   no
    paraphrase        0.7872       47   no
    format            0.7273       22   no  (below the 30-decided floor; not read)
    identity          1.0000        6   no  (below the floor; not read)

**0.8151 on 568 decided comparisons is roughly 15 standard errors from indifference** — against
§79.1's 0.356 on 368, which the ledger already called "the most strongly estimated" bias failure on
record. That record now belongs here, and on this system's *own* prose against manipulated copies
of itself, which is the material this instrument was built for and is used on. §70 measured 0.5874
on the same corpus with the full ablation set at a single dose; the difference is that this ladder
carries *small* doses, and a two-paragraph rotation is a near-twin pair. §83's law arrives on the
one material anybody hoped was exempt.

#### A2 fails in the informative direction: the panel sees local dislocation and not global reordering

Zero of six scenes ordered against a null 95th percentile of 3. The per-scene win rates for the
damaged side, at doses 0.25 / 0.50 / 1.0:

    gen:scene-1  0.1304  0.3333  0.3636      gen:scene-4  0.2174  0.5417  0.5000
    gen:scene-2  0.1304  0.4167  0.5417      gen:scene-5  0.2083  0.3043  0.3478
    gen:scene-3  0.4583  0.3478  0.5000      gen:scene-6  0.1250  0.2917  0.2917

**The preference for the undamaged text is strongest at the smallest dose and decays toward
indifference as damage grows** — inverted, not merely flat, in five of six scenes. Two paragraphs
out of place is caught hard; every paragraph out of place is barely caught at all. That is §5a's
`transplant` blindness (−0.0125) reproduced on a dose ladder: a fully rotated scene is a *global*
structural change, and this instrument is measured near-blind to those while catching local jars.
It is also the first dose-ladder measurement the pairwise instrument has ever had — every prior
pairwise run in this repository used a single dose, so `dose_rho` was NaN on all nine arms of the
2x2 and monotonicity was untested rather than failed. It is now tested and it failed.

#### A4: the first measurement of question-wording stability, and it fails

Agreement across a semantically identical rephrasing is **0.7234**, against a floor of **0.8646**
for agreement across resamples of the *same* wording — a drop of 0.141 past a 0.10 margin, on 47
and 48 cells. **Roughly fourteen points of a verdict is the wording.** Read against the persona
being nearly inert on this instrument (persona-to-passage sum-of-squares ratios of 0.0028, 0.0071
and 0.0342), this is the direct confirmation that the question is the load-bearing knob and the
costume is not. The four declared invariants held — tie option, keep-reading act, reason-code
request, plain register — so this is wording sensitivity, not a changed task.

#### A0 and A1: the assumption is approximately true, and whitespace alone moves the tie rate

**A0 is the first elicitation of a pair `variant_win_rate` has called 0.5 by construction since
§70, and the assumption survives: the panel answers `neither` on 0.875 of 48 comparisons between
byte-identical texts.** Six comparisons were decided and all six picked the same slot, which is
p ≈ 0.03 two-sided and is **flagged rather than read** — six is a fifth of the floor this entry
just registered, and reading it would be the exact move the floor exists to forbid.

**A1 is void on bias and still returns the number it was built for, because that number is a tie
rate rather than a preference.** The separator downgrade changes not one character of any word, and
it takes the decided share from **12.5% to 45.8%** (Fisher two-sided p = 0.0006). Whitespace alone
makes this panel **3.7x more willing to state a preference at all.** The direction of the
preference matches §78 — 0.818 toward the blank-line original against §78's 0.958 on the harder
flatten — but that half is unreadable at chose-A 0.7273 and is recorded for shape only. **The
registered prediction was that A1 would fail; under the corrected rule it formally PASSES, because
its band went unreadable, while the mechanism it predicted is confirmed on the one statistic that
needs no bias precondition.** Both halves are written down so neither can be selected later.

#### A5 passes, and vindicates gating the aggregate rather than the call

ICC(1) is **0.284, interval [0.169, 0.384]** — a single comparison is mostly noise — while
Spearman-Brown at the battery's measured width of 7 replicates puts the aggregate lower bound at
**0.5867**, clearing the 0.50 floor. A bar set on ICC(1) at the conventional 0.50 would have
disqualified an instrument that is adequately reliable at the width its arms are actually read at,
which is why that bar was moved to the aggregate before any number existed.

#### Three corrections to §86, from the adversarial pass, all pointing the same way

- **`judge_license` reads no measured number.** Its three clauses are `evidence_class is
  PREFERENCE`, currency, and digest equality. It never calls `why_not_promotable`, so precision,
  holdout size, flagged count and §59's lower bound are not consulted at the selection door.
- **`cmd_calibrate` records without enforcing promotability**, and says so: *"This command records;
  it does not promote... printed here as information rather than enforced here as a precondition."*
  So the row that opens the selection door need never have cleared a floor.
- **`decision_grain` is passed at exactly one call site** — `handlers.py:263`, `Grain.UNIT`, inside
  `_craft_ladder`. Selection never consults grain, so the `Grain.covers` guard §86.3 cites protects
  the *refusal* door and not the *selection* one.

**Net: the ceiling on selection rests on one clause, and §86.1 recorded that clause's human-only
meaning as enforced by a docstring.** §86 named three independent guards; there is one, and it was
the unenforced one. **It is no longer**: §86.6 above, written in a parallel session from §86.1 and
merged with this entry, closes the denominator half — machine rows carry a reserved reader-id
prefix and `analysable_judgments` excludes it — and deliberately leaves the digest half open, so the
judge still burns its own licence. The two remaining corrections in this subsection are untouched by
that fix: `judge_license` still reads no measured number, and selection still has no grain.

#### What this does to the programme

**The incumbent panel is out at T0, so §79's $12 screen is moot for it** — the ordering registered
in [judge-validity-program.md](judge-validity-program.md) §7 did its job on the first candidate, at
$26 instead of at four figures. Panel v2 selection begins from candidates that have cleared this
battery, and the two the ledger already points at — a single plain question, and a stronger tier —
are now both suspect for the same reason: §85's Opus arms read positional bias 0.5000 / 0.7000 /
1.0000, pooled 0.661, so tier does not buy positional resolution, and A4 says the question moves
0.14 of the verdict, which makes "change the question" a candidate axis rather than a fix.

**And the battery is a candidate for its own treatment.** Its corrected false-disqualification rate
of 0.31-0.65 against a good judge is too high for a tier whose whole purpose is to be a cheap,
trustworthy kill. The named repairs, in order: cluster A3's null over scenes rather than treating
tournaments as independent; raise the identity and format arms past the 30-decided floor so their
bands become readable rather than merely unfailable; and report the battery's operating
characteristic beside every verdict, which this run now does.

### 86.8 The merge corrects §86.4: T1's blocker was mis-stated, and its first datum already exists

Written at the merge of `claude/judge-validity-pricing-9ea30a` into main, because two entries that
landed in parallel bear directly on §86.4 and one of them refutes it.

**§86.4 committed the error it quoted three subsections earlier.** It ruled the local tier out as a
judge by citing `gemma3:4b` at chose-A 0.8021 over 389 decided and 0.8095 on intensity — figures
from §70's material, ~1,000-word `toll.db` passages against their own ablations. §87.3 names that
for what it is: **the inheritance §79.1 forbids**, whose closing rule is that any future use of
this instrument on a kind of material has to measure bias on its own pairs. §86.3 quotes that rule
approvingly, against T2, in this same entry. The rule was applied to somebody else's tier and not
to my own citation, and that is the whole of the mistake.

**Measured properly, the conclusion survives and the evidence changes.** `latent_crossfamily.py`
screened four local candidates on §85's certified repair pairs — local inference, no quota, 32
comparisons each:

    candidate      status                decided   chose-A   preference
    gemma3:4b      INELIGIBLE_ON_BIAS      11/32     1.000    withheld
    qwen3:4b       INELIGIBLE_ON_BIAS      32/32     0.750    withheld
    phi4:latest    ELIGIBLE                32/32     0.531    0.9688
    gpt-oss:20b    NOT_SCREENABLE           0/32         —    weights fail to load

`gemma3:4b` reads 1.000 rather than 0.802, on eleven decisions out of thirty-two — a judge that
mostly abstains and is perfectly positional when it does not. Disqualified either way, and now
disqualified on our own pairs.

**So §86.4's headline — "T1 is blocked by provider access this machine does not have" — is wrong
as written, and the correct sentence is narrower.** The screen is runnable locally, it was run, and
it cost nothing. What blocks T1 is two things §86.4 collapsed into one: **operator acceptability**
of the eligible local candidates (the operator has closed `phi4` and `gpt-oss` as too old, which is
a reserved call and not a measurement), and **frontier API access** for the ≥4 lineages the tier
asks for at a tier that clears the precondition. The second is a purchase; the first is a decision;
neither is the flat unavailability §86.4 asserted.

**And T1's first datum exists, from another session's run rather than from this programme.**
`phi4:latest` cleared the band at 0.531 and then preferred §85's interiority repair at **0.9688**,
beside Haiku's 0.9509 and Sonnet's 1.0000. A 2024-era 14B model outside the generator's family,
judging prose written by `claude-opus-5`, likes the told-not-shown repair about as much as the
generator's own family does — which is the direction that argues *against* self-preference driving
the arm. Heavily qualified (32 comparisons, two personas, an excluded candidate, and the +11.8%
length confound present for every judge alike), and still the only cross-family reading in the
file. **§86.4's pre-registered readings apply to it unchanged: a universal preference is the
ambiguous outcome, upgrading confidence and certifying nothing**, since shared training pathology
and shared truth predict the same number.

**One sharpening for the §79 screen this programme leans on.** §87.2 re-derives what the 0.52 bar
actually costs: exceeding 0.52 takes 14 of 25 and 11 of 21 pairs, while the pre-registered binding
half — a Clopper-Pearson lower bound clear of 0.50 — takes **18 of 25 and 16 of 21**, roughly three
pairs in four. The $12-per-candidate screen in [judge-validity-program.md](judge-validity-program.md)
§4.3 should therefore be read for the band first and the *interval* second, never the point
estimate, and a candidate that clears 0.52 on the nose has not cleared the bar.

**What does not change.** §86.7's disqualification of the incumbent stands on its own pairs and is
untouched by any of this. §86.1's defect is closed at the denominator by §86.6. And §86.5's
correction — that none of these tiers bounds divergence from reader *preference*, because no
unsolicited source of it exists — is if anything strengthened by §87.2, where the one family
carrying a reader-produced label fails the bar on the interval every channel was pre-registered to
be judged on.


## 87. The instrument does perceive more than it reports, and a digit counter shows it better than a probe

Track P of the latent-taste directive (2026-08-19). `latent_probe.py` and `latent_fixtures.py`
carry the design; `PRE_REGISTRATION` was committed in `8fa24e7` **before the first forward pass**,
which is what makes §82's "no bar moves after numbers arrive" checkable here rather than asserted.
282 texts, 564 forward passes on `google/gemma-3-4b-it` pinned at
`093f9f388b31de276ce2de164bdc2081324b9767`, 34 layers, read at depths 9/17/25, 252 seconds, GPU at
59 °C when the run ended and held twice at 72 °C on the way by `cdg_battery`'s governor. No quota. `results/latent-taste-probe.json`.

**The hypothesis was that near-twin discrimination exists in a model's internals and fails to reach
the verbal verdict — a report failure rather than a perception failure. The report failure is real
and the probe is not what shows it.** On every fixture family this project owns, internals add
nothing a surface counter does not already have.

    family                     G   P0   P0+  best1   text_mean      judge_last
    placebo_identical  FLOOR    8    0     0      0   0 (1.000)      0 (1.000)
    states_tea_vs_sober FLOOR    8    4     4      6   5 (0.680)      5 (0.703)
    rewhitespace_sham  FLOOR   10    9     9      5  10 (0.002)     10 (0.008)
    stat_flatten               10    0    10     10  10 (0.002)     10 (0.002)
    interiority_strip_matched   9    9     9      9   9 (0.004)      5 (0.840)
    repair_interiority          8    8     8      8   8 (0.008)      8 (0.031)
    repair_emdash               8    8     8      7   8 (0.016)      8 (0.031)
    exemplar_vs_sober           8    7     7      8   8 (0.008)      7 (0.117)
    states_drunk_vs_sober        8    2     2      7   7 (0.180)      7 (0.195)
    states_trip_vs_sober         8    3     3      7   7 (0.188)      4 (0.867)
    filler_inject              10   10    10     10  10 (0.002)     10 (0.002)

`k` of `G` scenes ordered correctly under leave-one-scene-out; p is exact, from enumerating all
`2**G` within-pair label flips. `best1` is the strongest *single* surface feature.

**The design is a paired sign count and not an AUC, and that is what made it measurable at eight
scenes.** Sixteen texts in 2,560 dimensions separate under any fitted classifier. A unit-normalised
mean of paired difference vectors has no hyperparameter, so the held-out sign test means what it
appears to mean — and it collapses to a `G x G` Gram matrix (`gram`, `signs_from_gram`), which is
the only reason the exhaustive null is affordable at all: 1,024 re-runs become 1,024 matrix-vector
products. `test_closed_form_matches_the_literal_leave_one_scene_out_refit` asserts the algebra
against a literal per-fold refit. **A probe also cannot have positional bias** — it scores one text
at a time — so the exact mechanism that voided §83's and §85's twin arms is structurally absent.

**Two floors held and one did not, and the one that did not was refused as a floor two entries
ago.** `placebo_identical` — §85's typo-fix placebo, byte-identical on both sides — returns `k=0`
on all four channels, so the pipeline does not separate a string from itself. §83's inert-state
placebo does not separate either (5 of 8, p 0.68), so nothing here is the probe reading a sampling
draw. `rewhitespace` clears everything, exactly as §78.1 measured and §81 said in terms: *"§78
measured why `rewhitespace` cannot be this design's floor … already called unusable"*. I registered
it as a floor with that sentence on the page. **The run reports VOID as registered.** The corrected
floor set is the other two, and under it the verdict is UNREPLICATED rather than positive — so the
defect changed the wording of the conclusion and not the conclusion.

**The one apparent internal win dissolves under its own diagnostic.** `exemplar_vs_sober` is the
only family where the probe cleared and beat the registered baseline: 8 of 8 against P0's 7 of 8.
But `dialogue_ratio` alone orders that family 8 of 8, and so does `word_len_mean`. P0's shortfall
was **dilution across twenty-four z-scored deltas**, not absent surface information. That column is
recorded as `p0_best_single_DIAGNOSTIC` and is deliberately *not* substituted into the bar: doing
so would be tightening a rule against numbers already seen, which is what §81 refused to do. The
corrected rule for any successor run is declared here instead — **the surface baseline is the
maximum of the aggregate direction and the best single feature**, and it must be beaten in that
form.

**The stat-flatten row is the entry's finding, and it is in the surface column.** §81 recorded the
panel BLIND at 0.5437 with the estimate on the wrong side of indifference. Here the plain P0 space
is blind too — **0 of 10** — for a reason that is ours: `strip_system` deletes the `[STATUS]` line,
which is the only line the transform edits. The steelman baseline that exists to catch exactly that
scores **10 of 10**, and so does a *single* count of digits inside the status block. So the defect a
human named and the panel cannot see is ordered perfectly by one deterministic counter. **Nothing
in this stack fails to perceive stat-flatten; the verdict channel fails to carry it.** Had P0 not
been steelmanned before the run, this entry would have reported the probe seeing what surface
cannot, and it would have been an artifact of a feature list we wrote.

**Where the near-twins actually sit.** §83's state arms are the hard case and they stay hard: the
probe reads 7 of 8 on both and clears neither null (p 0.180, 0.188), while P0 reads 2 of 8 and 3 of
8 — *below* chance, actively anti-ordered. These are the only families where surface and internals
are both undecided, and they are the ones superhuman selection would live in. For them the
directive's second quadrant row stands: **perception-limited at 4B**, recorded and closed.

**One divergence worth naming for whoever runs the successor.** On `interiority_strip_matched` the
mean-pooled text readout scores 9 of 9 and the judge-position readout 5 of 9. The difference is
present in a representation of the prose and gone by the position a verdict is generated from. That
is the shape the report-deficit hypothesis predicts; it is reported as a diagnostic and not as a
result, because the family is closed to P by the surface rule and one family is not a finding.

**A second pre-registration defect, recorded rather than repaired.** The smallest attainable
p-value is `2 / 2**G`, not `1 / 2**G` as declared. The statistic is invariant under a global sign
flip — relabelling every pair swaps the fitted direction with it — so the observed assignment
always has a twin in the enumeration. The declared family-wise alpha of 0.00625 is therefore
**unattainable at eight scenes**, and no eight-scene family could have cleared it however clean the
separation. `test_the_statistic_is_invariant_under_a_global_sign_flip` and
`test_a_perfectly_separating_family_cannot_beat_the_null_floor` pin the corrected figure. That is
the third bar in this project's history declared in a form the design could not reach (§81's point
estimate, §85's zero-width band, this), and the pattern is now explicit enough to check for: **a
declared bar should be tested against the best attainable value of its own statistic before it is
committed.**

**Which kill condition fired, precisely.** Not the one the directive wrote. Several probes cleared
their nulls, so "no probe on any fixture family clears its null" is false. Track P closes on
**redundancy** instead: on no family does an internal readout beat the best surface baseline, so
there is no family where internals buy anything. That is a more useful negative than the one
anticipated — it says the ceiling on this fixture set is not adapter-shaped *or* pretraining-shaped
but **fixture-shaped**, and the successor experiment is a harder fixture, not a bigger model.

**The quadrant, read with `surface` in the probe column, since internals added nothing.**

    separates / panel void       stat_flatten (§81 BLIND), repair_emdash (§85 bias .695),
                                 exemplar_vs_sober (§85 bias .766), interiority_strip_matched
                                 (§81 interval spans 0.5)         -> report-channel deficit
    separates / panel separates  repair_interiority (§85 0.9509, §85.1 1.0000)  -> agree
    fails / panel void           states_drunk, states_trip        -> perception-limited at 4B

**What is proposed, and to whom.** The directive's B6 was "probe–panel divergence pairs". The run
says the cheaper family is better: **counter-decidable / panel-void pairs** — fixtures a
deterministic counter orders at `k = G` and the panel cannot read. It needs no GPU, no open
weights, and no model pin; it reproduces from committed fixtures in one command; and it tests the
verdict channel directly, which is what B6 was for. **It is proposed and not admitted. Only the
operator moves what panel v2 is selected on** (§84), and the hardware-ladder question is moot
rather than answered: 12B would have to beat a digit counter, not a 4B model.

**The proposal is an artifact rather than a paragraph**, emitted by `propose_b6` into
`results/latent-taste-probe.json` under `b6_proposal`, so admitting it is a decision rather than a
re-derivation. Three members, and the membership rule is stricter than the sentence above:

    member                     counter (named a priori)  decidable   panel
    stat_flatten               system_digit_count            10/10   BLIND 0.5437 (§81)
    interiority_strip_matched  interior_per_1k                 9/9   spans null 0.3889 (§81)
    repair_emdash              em_per_1k                       7/8   VOID .695 / .609 (§85, §85.1)

**The counter has to be nameable before any result is read** — `A_PRIORI_COUNTER` maps each family
to the quantity its transform is *defined* in terms of — because the diagnostic column is a maximum
over twenty-seven features and cannot be read as one counter's score. The first draft of this rule
used that maximum and admitted §83's state arms at 7 of 8; with twenty-seven features swept, 7 of 8
somewhere is unremarkable, and those are exactly the arms this entry records as undecided by
surface *and* internals. They are rejected now, with the reason recorded beside them. `repair_emdash`
carries one **structural tie** — `gen:scene-7`'s original had no prose em dashes to remove — which
is listed as a scene id rather than counted as a miss, since an unscoreable pair is not a failure.

**What this does not license.** Nothing. A sign count is discrimination, and the panel was asked
for preference — the two are not the same question, and the honest comparison is narrower than it
looks: what the panel fails at on these pairs is *registering a difference at all*, answering the
slot instead (§83, §85), and that is the failure a counter is being compared against. Whether any
of these differences matters to a reader is untouched here and stays with §80's batch. §82 governs
verbatim; no licence moves.

### 87.1 Two arms that were designed to need a judge and turned out not to

Both run at zero quota from committed fixtures. `latent_support.py`,
`results/latent-taste-support.json`.

**Track S — the treatment the panel preferred is told-not-shown, measured at the stimulus.** D2
asks whether §85's 0.9509 is taste for the model's own register rather than for prose. The judged
form of that question needs a cross-family judge, which the directive reserves to the operator. The
unjudged half was never asked: *what did the treatment actually add?* `authorship_tells` already
separates reported inner state (`_INTERIOR`: thought, felt, knew) from demonstrated bodily state
(`_BODY`: jaw, hands, breath), which is the distinction the craft worry turns on.

    repair_interiority (n=8)   told  +1.608 per 1k, up in 7 of 8 scenes
                               shown -0.627 per 1k, up in 1 of 8 scenes
                               words +11.8%  (§85 measured 10-13%)
    exemplar        (n=8)      told  +0.346, up in 4 of 8;  shown -0.825, up in 4 of 8

**The treatment added telling and removed showing.** So whatever the panel preferred at 0.9509,
the thing it preferred was told-not-shown — established without a second judge and without
asserting anything about the first.

**Read against §85.1, which landed the same day from a parallel session, this acquires a
direction.** That entry re-elicited the identical pairs one tier up: `repair_interiority` goes
0.9509 at Haiku to **1.0000 at Sonnet**, 64 of 64, bias exactly 0.500. Capability and family match
predict opposite signs here — a *stronger* judge should be less taken in by a craft defect, and a
judge closer to the generator's own register should be more so. **Preference for the told-not-shown
treatment saturates as tier rises.** ~~That is the sharpest evidence D2 has~~ — **corrected below**
— and it is still not proof: "told feeling is worse" is craft doctrine, not a measured reader fact,
and a human may prefer the same text. What it does is remove a question from the cross-family
judge's list — the stimulus is characterised now, so the operator read and §80's class B arbitrate
preference alone. The two readings enter the ledger together, as the directive asked.

> **Correction, same day, from §87.3.** The tier gradient is **not** diagnostic of family match, so
> it is not evidence for D2 at all. §87.3 screened the local judges and found one that cleared the
> positional-bias precondition: `phi4:latest`, a 2024-era 14B outside the generator's family, which
> then preferred the same repair at **0.9688** — beside Haiku's 0.9509 and Sonnet's 1.0000. A
> cross-family judge showing the same preference is what the family-match explanation predicts
> against. Both readings stand as measured; what changes is which way they point, and the honest
> statement is now that **the one direct cross-family reading available argues against D2** at
> n=32, on a model the operator has closed as a candidate. The rest of this section is unaffected:
> the *stimulus* is told-not-shown whatever any judge thinks of it.

**Track V — the selection ceiling, measured with no selector at all.** "Selection cannot exceed the
support of the generator's distribution" has been asserted here and never measured. It needs no
judge: for any axis, `E[best of N]` under an **oracle** selector is an order statistic of the
generator's own draws, and no panel, probe or human can beat an oracle. §83 left the pool — four
retells of each scene from one prompt, measured there as near-twins — so the curve is exact by
enumeration over subsets.

    axis                  E[best of 1..4] minus sober          gain    one certified revision
    interiority (up)      +0.167 +0.524 +0.661 +0.711         +0.544   +1.608  (34%)
    prose em dash (down)  +0.296 -0.724 -1.305 -1.625         -1.921   -3.534  (54%)

**An oracle selector over four draws of this generator reaches a third of one certified revision on
interiority and half of one on em dashes.** The increments decelerate hard — +0.357, +0.137, +0.050
— but the pool is four deep, so the directive's plateau-by-N=4 condition **cannot be confirmed
beyond N=4** and is not claimed to be. What is claimed is the bound: on the two axes a human reader
named, revision reaches further than selection can, and the gap is not close. The axes are surface
proxies rather than measures of quality, and an oracle over a proxy is not an oracle over prose —
this bounds **reach**, not value.

**What waits, and for whom.** Track S's cross-family judge stays reserved to the operator (model
choice, cost, protocol fidelity), and ~~the only free local candidate is already disqualified on
protocol rather than on cost: RUNBOOK records `gemma3:4b` failing the positional-bias precondition
on this material at chose-A 0.802/0.810~~ — **struck; see §87.3.** Two errors in one sentence.
Those figures come from §70's `toll.db` runs, not from this material, so citing them here was the
inheritance §79.1 forbids by name; and there is not one free local candidate but four, of which
§87.3 finds one eligible. The conclusion — no acceptable local candidate, so the track waits — is
unchanged, and §87.3 reaches it by measuring rather than by citing. The tier ladder was **not** run here because
§85.1 and §79.2 were running it in parallel; coordinating rather than duplicating was the
directive's instruction and it saved the arm. Track V's N=8..32 curve needs fresh generations and
is not started.

### 87.2 The external-label family reverses the entry above, and fails the bar anyway

§87 was scored without the fixture the directive names as Track P's valence anchor: §79's
conversion-labelled pairs, the only material in this project carrying a label a *reader produced*
rather than one we manufactured. They are added here with their bars declared first (`e31540e`,
before the forward pass) and run on the same 282-text extraction. 46 pairs, story-disjoint, ~1,000
words a side, length-matched by §79's builder. No quota. `results/latent-taste-probe.json`,
`conversion_arm`.

**On this family, and only on this family, internals beat surface counting.**

    channel           aligned (25)   crossed (21)   minimum   aligned CI      crossed CI
    P0                15  0.600      13  0.619       0.600    [0.387, 0.789]  [0.384, 0.819]
    P0+               14  0.560      12  0.571       0.560    [0.349, 0.756]  [0.340, 0.782]
    text_mean  (L17)  20  0.800      14  0.667       0.667    [0.593, 0.932]  [0.430, 0.854]
    judge_last (L25)  15  0.600      12  0.571       0.571    [0.387, 0.789]  [0.340, 0.782]

**The probe rows are one readout depth, chosen across both strata at once, and every depth is
reported.** Picking the best layer in `aligned` and a different one in `crossed` would report a
minimum no single readout ever achieved, which is double-dipping on exactly the axis the strata
exist to police; `_select_layer` therefore maximises `min(aligned, crossed)` and `all_layers` keeps
the rest:

    text_mean   L9 0.640/0.667   L17 0.800/0.667   L25 0.800/0.571
    judge_last  L9 0.680/0.333   L17 0.640/0.333   L25 0.600/0.571

That is still a selection over three depths **which the surface baselines do not get**, so the
probe-versus-P0 comparison on this family favours the probe by construction. It cannot manufacture
a pass — the binding half of the bar is an interval, and selecting on a point estimate does not
narrow one — but every ranking below inherits the asymmetry and is written knowing it.

`k / G` here **is** agreement with the external label, in the same units as §79's 0.52 bar. The
mean-pooled readout's minimum across strata is 0.667 against P0's 0.600 and P0+'s 0.560 — the
reversal of §87's headline, on the one family where the difference was not manufactured by us.
That is not a contradiction of the entry above: everywhere else, the thing to be detected is a
thing we made, and a counter that knows what we made is unbeatable. Here nobody knows what makes
the label move.

**It fails, on the condition pre-registered as the binding one.** The bar has two halves and
`PRE_REGISTRATION_B4` declared before the run that the interval is the half that would decide it:
exceeding 0.52 takes 14 of 25 and 11 of 21, while a Clopper-Pearson lower bound clear of 0.50
takes **18 of 25 and 16 of 21** — roughly three pairs in four. `text_mean` clears the first half in
both strata and misses the second in `crossed`, whose lower bound is 0.430. **Every channel fails,
and the reading is FAILS rather than nearly passes**, which is the sentence the attainability note
was written in advance to make unavailable.

**The shape is the interesting part, and it is the shape §79 built the strata to expose.** A judge
reading prose agrees with the label in both strata; a judge proxying popularity agrees in one and
disagrees in the other. §79.1's panel candidate read **0.6100 aligned and 0.4107 crossed** — the
popularity signature, crossed below a coin — and voided at 0.356 pooled positional bias.
`text_mean` reads **0.800 and 0.667: both above 0.5**, with a 0.133 spread against the panel's
0.20. So on the benchmark this project built to *rank* judges, a free local 4B linear readout
ranks above the panel candidate §79.1 measured — with the asymmetry named above attached, since
the readout's figure is the best of three depths and the panel's is a single shot — and it does so
with the precondition that voided that candidate structurally unavailable to it — a readout scores one text at a time and has no
slot to prefer. Recorded as a ranking, which is all §82 permits BEHAVIOUR-class evidence at STORY
grain to be, and it is the machine-side input the directive licenses P to hand A2(iii).

**Three reasons not to believe it yet, in the order they would bite.** The corpus ceiling is 46
pairs and §79 already named the remedy — *"reaching hundreds is a download, not a redesign"*, two
of the dataset's 47 shards being cached. The `crossed` stratum is 21 pairs and carries the whole
minimum. And the residual confound is not popularity but *tier*: `crossed`'s high-conversion side
has 16x fewer views, so a readout could be reading amateur-versus-established register rather than
anything about quality. Agreement above 0.5 in **both** strata argues against a pure popularity
proxy, which is exactly what the design was for, and it does not rule the tier confound out.

**What it does not license.** Nothing, and the ceiling was declared before the numbers: §82
classifies conversion as BEHAVIOUR at STORY grain, `domain/calibration.py` defines PREFERENCE as a
*human's* blinded choice, and a pass here would still have been a judge-selection signal rather
than a statement that either side is better prose. It did not pass.

### 87.3 The cross-family screen: the kill condition is discharged by measurement, and D2 loses its best evidence

§87.1 ruled Track S's local option out by citing RUNBOOK's `gemma3:4b` bias of 0.802/0.810. **That
citation was the inheritance §79.1 forbids** — those figures come from §70's material, ~1,000-word
`toll.db` passages against their own ablations, not from §85's certified repair pairs. §79.1's
closing rule is explicit: *"any future use of this instrument on this kind of material has to
measure bias on its own pairs; inheriting a figure from a different experiment remains
unsupported."* `latent_crossfamily.py` measures it. Local inference, no quota, 32 comparisons per
candidate on §85's interiority pairs. `results/latent-crossfamily-screen.json`.

    candidate      status               decided   chose-A   per-persona     preference
    gemma3:4b      INELIGIBLE_ON_BIAS     11/32     1.000   1.000 / 1.000   withheld
    qwen3:4b       INELIGIBLE_ON_BIAS     32/32     0.750   0.938 / 0.563   withheld
    phi4:latest    ELIGIBLE               32/32     0.531   0.500 / 0.563   0.9688
    gpt-oss:20b    NOT_SCREENABLE          0/32         —   weights fail to load here

`chose-A` is computed over *decided* comparisons only (`elicit.positional_bias` counts A and B and
drops `neither`), which is why the `decided` column has to be read with it.

**The conclusion §87.1 reached survives; its evidence does not.** Measured on the right pairs
`gemma3:4b` reads **1.000** rather than 0.802 — but the honest sentence is narrower than the
number: it *decided* only 11 of its 32 comparisons, answering `neither` to the other 21, and every
one of those 11 landed on the first slot. So it is a judge that mostly abstains and is perfectly
positional when it does not, on eleven decisions. That is comfortably outside the band and it
disqualifies the candidate; it is not the "32 of 32 total collapse" an earlier draft of this
paragraph claimed, and the difference matters because eleven decisions is thin. The
disqualification is real and it is now *ours*, on our own material, rather than borrowed from an
experiment that asked something else.

**Three outcomes, not two, and the third is a fact about this machine.** `gpt-oss:20b` returned 32
of 32 transport errors — the weights fail to load with a tensor size overflow — so no judgment was
ever obtained. Folding that into "ineligible" would have reported a model as answering a slot when
it never answered at all, and would have let a broken install masquerade as evidence about judges.
`NOT_SCREENABLE` is its own state.

**The eligible candidate is excluded by the operator, which is the reserved half of the question.**
Operator, 2026-08-19: *"let's ignore gpt oss it's too old anyway, like phi4"*. Acceptability —
cost, terms, currency of the model — is directive §6's reserved call and not something a screen
decides. So **no acceptable local candidate is eligible, and the directive's kill condition is
discharged by measurement rather than asserted**: Track S waits on a judge the operator selects,
and no degraded protocol is substituted to force a number.

**But `phi4`'s number was legitimately obtained, and it is the first cross-family reading this
project has.** It cleared the precondition at 0.531 and then preferred the interiority repair at
**0.9688** — beside Haiku's 0.9509 (§85) and Sonnet's 1.0000 (§85.1). A 2024-era 14B model outside
the generator's family, judging prose written by `claude-opus-5`, likes the told-not-shown repair
about as much as the generator's own family does. **If family match were driving the preference, a
cross-family judge should have been markedly cooler. It was not.** The reading is heavily
qualified — 32 comparisons, two personas, a model the operator has closed as a candidate, and the
+11.8% length confound present for every judge alike — and it is still the only direct evidence on
D2 in the file, and it points away from self-preference.

### 87.4 What was not run, and the one assumption that dissolved on inspection

The directive names three things this session did not produce. Each is recorded with its reason
and its price, so the next session inherits a decision rather than a silence.

**P2 — the J-lens readout is not run, and its blocking assumption turns out not to exist.** The
directive made the `pt → it` lens transfer a named assumption requiring *"its own recorded verdict
before any P2 number is read."* The verdict is that **the assumption is unnecessary**:
`neuronpedia/jacobian-lens` (revision `a4114d7752d11eb546e6cf372213d7e75526d3a1`, MIT, ungated)
ships **both** lenses for this model —

    base (pt)      gemma-3-4b/jlens/Salesforce-wikitext/gemma-3-4b-pt_jacobian_lens.pt
                   sha256 70311caa74c3933bea8154850e88464936e07c8641ee14f9304968ec1681108a
    instruct (it)  gemma-3-4b-it/jlens/Salesforce-wikitext/gemma-3-4b-it_jacobian_lens.pt
                   sha256 dcb23c8627b2ef94225f45550d792d7608bd96f6cf89aa8d1701bd6a4681277c

so a run against `gemma-3-4b-it` reads through the `-it` lens and transfers nothing. **A different
assumption replaces it, and it is the one to record a verdict on before any P2 number:** the two
fits are not equally good. Early stopping fired at 616 prompts for the base lens at a final
identity distance of **0.684** and at 546 prompts for the instruct lens at **0.960** — the instruct
fit converged to something much closer to the identity map, and whether that is a property of the
`-it` model or a weaker fit is unsettled upstream. Also pinned for whoever runs it: `jlens` at
`581d398613e5602a5af361e1c34d3a92ea82ba8e`, which requires `transformers >= 5.5`, positions 0–15
are unfitted so `-2` is the last fitted position, and `JacobianLens.save` defaults to fp16 and
overflows without range checks, so every loaded lens needs a `torch.isfinite` gate.

**P2 is nonetheless the right thing to skip.** The directive scopes it as *"only to interpret what
P1 found"*, and P1 found nothing to interpret: no internal readout beat a surface counter on any
manufactured family. Running an interpretability layer over a null would be interpreting our own
arithmetic.

**Track V's two generation arms are designed and unfunded.** Both need fresh `claude-opus-5`
generations, and §85 measured that channel at 32 generations for $7.41 — about $0.23 each.

    arm                      shape                                    generations   ~cost
    voice-binding dose       exemplar dose 0,1,2,4,8 passages x 8              40   $9.30
                             scenes; measure z-space movement and
                             centroid distance against an n-gram
                             borrowing control, so deep-feature
                             movement is separable from mimicry
    persistence              revise each moved scene once through              8    $1.90
                             the certified path; does the voice hold
                             or drift back? a lever that resets on
                             first use is a demo
    best-of-N to N=32        32 draws x 8 scenes, to extend §87.1's           256  $59.30
                             oracle curve past its four-deep pool

The first two are the ones worth buying: §85 measured the demonstrated-voice channel *open* and
§87.1 measured selection reaching only a third to a half of one certified revision, so how deep
the voice lever binds and whether it survives a revision are the two open questions about the only
working register lever this project has. The third is the expensive one and the least informative
per dollar — the oracle curve already bounds every selector, and extending it to 32 refines a
ceiling rather than moving it.

**Track V's plateau condition remains unsettled and is not claimed either way.** The directive's
V2 kill condition is a plateau by N=4 under every selector; the pool is four draws deep, so the
curve stops exactly where the condition starts. §87.1 reports the shape within N≤4 and the ratio
to the certified revision, and nothing about N=8..32.

## 88. B6 is admitted, and the control that rides along disagrees with its own counter

Operator, 2026-08-19, on §87's `b6_proposal`: *"B6: ADMIT. All three members, a priori counters
as proposed in `results/latent-taste-probe.json`. Record the admission as its own ledger entry
before any E-track arm uses them."* §87 proposed the family and refused to admit it — *"Only the
operator moves what panel v2 is selected on"* (§84) — so this entry is the reserved act, taken.
`b6_benchmark.py`, `tests/test_b6_benchmark.py`. Local, deterministic, no quota.

**The admission is an artifact for the same reason the proposal was.** `propose_b6` emitted a
candidate so that admitting it would be a decision rather than a re-derivation; a membership
re-read out of a results file on each use is a membership nobody decided. So the decision, its
quote, and the three members live in a module, and `verify_against_proposal` checks that what is
admitted here is still what was proposed there — membership, counter, and decidable count — and
fails loudly rather than drifting.

    member                     counter (named a priori)  decidable   panel
    stat_flatten               system_digit_count            10/10   BLIND 0.5437 (§81)
    interiority_strip_matched  interior_per_1k                 9/9   SPANS_NULL 0.3889 (§81)
    repair_emdash              em_per_1k                       7/8   VOID 0.2734 (§85, §85.1)

`repair_emdash`'s eighth pair is `gen:scene-7`, whose original had no prose em dashes to remove.
It stays a scene id rather than a miss: an instrument asked to order a tie and declining is not
wrong.

**What admission changes is one thing, and the entry says so because silence here would be read
as more.** It changes which fixtures an experiment may select an instrument on. It does not move
a licence, it does not upgrade BEHAVIOUR-class evidence, and it does not make a counter a judge —
§82 governs verbatim and `domain/calibration.py` still defines PREFERENCE as a human's blinded
choice. What B6 measures is whether an instrument's channel carries a difference **provably
present in the material**; whether that difference matters to a reader is untouched and stays
with §80's batch.

**The positive control turns out not to agree with its own counter, and the disagreement is the
length confound arriving from underneath.** `repair_interiority` rides along as the thing every
protocol should preserve — 0.9509 at Haiku (§85), 1.0000 at Sonnet (§85.1), 0.9688 at `phi4`
(§87.3), three judge families. Scoring it the way B6 members are scored gives **7 of 8**, not 8:
on `gen:scene-5` `interior_per_1k` moves the *wrong way*, 3.165 down to 2.876. Nothing is broken.
§85's repair adds interiority and adds words with it — §87.1 measured +11.8% — and a per-1k
density can fall while the absolute count rises. The consequence is a rule rather than a
footnote: **the positive control is scored as a preference and never as a counter alignment**,
because scoring it against its counter would import the confound into the one arm that exists to
be clean. Recorded rather than repaired, per §81's refusal to tighten a rule against numbers
already seen; `test_the_positive_control_counter_disagrees_on_exactly_one_scene` pins it so the
exception cannot later be mistaken for a fixture bug.

**The two mandatory controls are not symmetric, and the asymmetry is §87's own correction kept
in force.** `placebo_identical` is the floor: both sides are the same string, `k = 0` on all four
of §87's channels, and an instrument that separates it separates anything. `rewhitespace_sham` is
**not** a floor — §78.1 measured why it cannot be one and §81 said so in terms while §87
registered it as one anyway — it is the void control: it differs only in formatting, and an
instrument that recovers discrimination there is reading layout. That reading is VOID, not
weakened.

**A precondition landed before this entry rather than beside it.** `f506ee7` extends the corpus
leak audit ahead of Track C's first shard. `long_strings` walked `payload[:400]` of any list and
said nothing about the rest; every product this repository has written peaked at 108, so the cap
never bit, and Track C's expansion is the first thing designed to carry hundreds of prose-bearing
rows in one list. Verified in a throwaway repository rather than by reading the code, which is
the standard `f2a2aba` and `6b073cb` set: on a history whose only excerpt sits at index 450 of a
500-row list, the committed audit prints **CLEAN and exits 0**. It now refuses and names the
unwalked range. That is `f2a2aba`'s lesson in a second costume — there a suffix no scanner
admitted, here a slice no walk reached — and the same verdict, a check that cannot fail on the
material it was pointed at.

## 89. The verdict channel cannot carry it and the report channel can, on the same model and the same pairs

The verdict-locus directive (2026-08-19). The question was scientific rather than infrastructural —
*where, between representation and verdict, does discrimination die, and is any elicitation protocol
lossless?* — and B6's admission (§88) gave it ground truth for the first time. **Both halves are
answered.**

**Where it dies.** On `gemma-3-4b-it` the greedy verdict is `A` on **106 of 106** pairwise passes,
and one step earlier the answer distribution at the verdict token decomposes into |positional|
**0.9998** against |text| **0.000214**. The signal is not lost at sampling; it is two
ten-thousandths of the distribution before anything samples. So the loss is upstream of the verdict,
and a better way of *preferring* cannot be the fix.

**Whether any protocol is lossless.** One is, and it is the one that does not ask for a preference
at all. On Haiku, same pairs, same session: asked which passage it would rather keep reading, the
panel answers the slot at chose-A **0.6408** on 142 decided comparisons and is VOID. Asked to
**name the single most salient difference**, it clears all three B6 families — 40/40 on
`stat_flatten`, 30/32 on `repair_emdash`, 18/36 on `interiority_strip_matched` against measured
nulls of 0.21/0.36/0.26 — while reporting *"the passages are identical"* on the placebo and
*"double spaces after periods"* on the sham.

**So the instrument is not blind. It is being asked the one kind of question its verdict channel
cannot carry.** That is a design instruction rather than a budget, and it is narrower than it
sounds: E6 reports a *difference*, never a preference, so it can staff a discrimination layer and
JudgeBench A2's verdict layer is still empty. §82 is untouched.

**The second result is the rulebook.** Seven declared quantities could not do what their own
declaration implied, and five were caught before a single call was bought:

    #  the declared quantity                          what it could not do                caught
    1  the 2/2**G floor, with §87's reason            transfer: §87's invariance is a       before
                                                      property of a *fitted* direction
    2  E4's per-pair sign as a persona vote           decide: two personas tie whenever     before
                                                      they disagree, ~half the pairs
    3  E6 on the shared two-sided sign test           discriminate: it credits silence      before
                                                      exactly as much as naming
    4  the leak audit's list walk                     see: it stopped at 400 silently       before
    5  a view-matched sub-stratum in `crossed`        populate: zero pairs qualify at       before
                                                      the only principled threshold
    6  the 30-decided floor, counted in comparisons   bind: four personas gave one judge    after
                                                      four times, 64 -> 16 cells
    7  the screen's withholding gate                  match its own pre-registration:       after
                                                      it withheld more than the rule said

None is exotic and all seven are the shape §81's point estimate, §85's zero-width band and §87's
sign-flip floor already had. The difference is that the checking is now a rail rather than a habit,
and four of the five caught early were caught by a dry run and a covariate distribution rather than
by anyone being clever.

**What each track produced is below. Nothing here moves a licence; §82 governs verbatim.**

### 89.1 Track S: two eligible judges, and then one judge four times

Operator directive: screen-then-decide, eligibility measured rather than assumed (§79.1, §87.3),
`qwen3:14b` and `gemma3:12b`, first to clear the precondition at the 30-decided floor takes the
track. `latent_crossfamily.py`, four personas x 8 scenes x 2 orientations, local inference, no
quota. `results/latent-crossfamily-screen-v2.json`.

    candidate    comparisons  decided  chose-A  cells  vectors  as registered  corrected
    qwen3:14b            64       64   0.5625     16      1/4   ELIGIBLE       INSUFFICIENT_DECIDED
    gemma3:12b           64       64   0.4531     16      3/4   ELIGIBLE       INSUFFICIENT_DECIDED

**As registered both clear, and the correction is the entry.** `qwen3:14b` returned **one distinct
answer vector across all four personas, byte-identical**. The persona system prompt is inert for
it, so the panel is one judge replicated and the 64 comparisons are 16 independent decisions; the
standard error on its bias estimate is 0.125 rather than 0.063. `gemma3:12b` returned three vectors
of four, which is better and not different in kind.

That is §87.3's lesson in a second costume. There the inflated number came from **abstention** —
1.000 resting on eleven decisions — and here it comes from **replication**, which is harder to see
because nothing is missing from the table. The independent unit is now the `(pair, orientation)`
cell and personas are replicates on it, **unconditionally**: applying the rule only to degenerate
panels would have been a rule chosen after seeing which candidate it rescued, which is what §81
refused to do, and `elicitation_study`'s own pre-registration — written the same morning — already
says that personas within a pair are repeated measures rather than independent draws.

**The consequence is recorded rather than lowered.** An 8-pair fixture holds 16 cells, so **no
judge that ignores personas can reach a 30-decision floor on this material however many personas
are seated.** Track S still waits on a judge the operator selects, and the kill condition stays
discharged by measurement rather than asserted.

**One code gate was stricter than the rule it implemented, and the rule won.** `withholding_rule`
withholds a win rate for a candidate whose *bias* falls outside the band; the code withheld unless
the candidate was ELIGIBLE, which also hides a candidate that cleared the band and merely lacks
depth. Those are different failures with different remedies, and suppressing a figure legitimately
obtained under the declared condition would be moving a rule after seeing what it hid. So, with
their precision attached: **0.9375 and 0.9219**, on 16 cells each.

**Beside §85's 0.9509, §85.1's 1.0000 and §87.3's 0.9688, that is five judges across four vendors
preferring the same told-not-shown repair.** D2 — the hypothesis that panel preference tracks
generator-judge family match — now has four independent non-Anthropic families arguing against it.
Whether the preference is *correct* is untouched: that is craft doctrine's claim, it is what §80's
class B and the operator read arbitrate, and the operator read is PENDING, so every told-versus-
shown reading in this entry is provisional.

### 89.2 Track C: the corpus reaches 281 pairs and the tier control has no members

`FROZEN_READOUT` was committed first (`0651a48`), before the corpus was rebuilt and before any new
pair or label was read: `text_mean`, layer 17, unit-normalised mean paired-difference direction.
§87.2 chose that depth by maximising `min(aligned, crossed)` over three and disclosed that it gave
the probe three shots where a surface counter gets one. Carrying the same selection into a larger
corpus would re-select against labels the first selection had already been fitted to, so 17 stops
being a choice and becomes a **prediction**. Every depth is still extracted and reported — a freeze
nobody can falsify is not one — and P0/P0+ run beside it unchanged, so the comparison is one shot
each for the first time.

**The corpus.** Twelve shards instead of two at the pinned snapshot: 616 stories clearing §79's
floor against 107, and **281 pairs against 46** — 144 aligned, 137 crossed. All 562 slots
story-disjoint.

**The view-matched sub-stratum cannot be a threshold, because every threshold worth naming is
empty.** §87.2 named the residual confound as tier: `crossed`'s high-conversion side carries 16x
fewer views, so a readout could be reading amateur-versus-established register. The obvious control
is to match views at the factor-of-two tolerance `aligned` already uses — and **zero of the 21
crossed pairs qualify at n=46, and zero of the 137 do at n=281.** The tightest sits at 2.1x and the
median at 12.2x.

    |log10 view ratio| <= 0.30  (2.0x):   0/137
                        <= 0.50  (3.2x):  13/137
                        <= 0.70  (5.0x):  30/137
                        <= 1.00 (10.0x):  59/137

So the split is a **rule and not a number**: the tighter-matched half of `crossed` against the
looser half. It always populates, its size is n/2 so attainability is computable before any label
is read, and the contrast between halves is the measurement — a readout reading establishment
register scores in the loose half and not the tight one. Both halves print whatever they show.

**Bars, declared before extraction and verified attainable.**

    stratum               n   k for 0.52   k for CP lower > 0.50   binding
    aligned             144           75                      85   interval
    crossed             137           72                      81   interval
    crossed, tight half  68           36                      43   interval
    crossed, loose half  69           36                      44   interval

The interval remains the binding half at the new n, which is `PRE_REGISTRATION_B4`'s logic
surviving a 6x change of scale. The required rate falls from **0.762 at n=21 to 0.591 at n=137** —
so §87.2's 0.667 on `crossed` would now pass. That is what makes the expansion a test rather than a
larger version of a failure, and it is also why the readout had to be frozen before it ran.

**Author disjointness, measured rather than assumed.** §79 enforces disjointness at story level,
which is a different and weaker property than author level, and at 616 stories the gap stops being
ignorable. `author` and `average_views` now travel with every unit and neither is selected on:
**zero pairs share an author across their two sides**, and 43 authors recur across different pairs
— 51 of 562 slots. That is a clustering caveat on the interval rather than a bias, and it is now a
number instead of a hope. `chapters` = `total_views / average_views` recovers each fiction's true
published length, since `pages` is 100% null in these shards; the median is 39.

**The leak audit's scope extension landed before the first shard** (`f506ee7`), as the directive
required, and it turned out to be closing a live hole rather than a formality. `long_strings`
walked `payload[:400]` of any list and said nothing about the rest; every product this repository
had written peaked at 108, so the cap never bit, and Track C's expansion is the first thing designed
to carry hundreds of prose-bearing rows in one list. Verified in a throwaway repository rather than
by reading the code, which is the standard `f2a2aba` and `6b073cb` set: **on a history whose only
excerpt sits at index 450 of a 500-row list, the committed audit prints CLEAN and exits 0.** It now
refuses and names the unwalked range. Same lesson as `f2a2aba` in a second costume — there a suffix
no scanner admitted, here a slice no walk reached.

**The frozen readout does not survive the corpus it was frozen for, and that is the point of
freezing it.** `text_mean` at layer 17, committed before the rebuild:

    stratum    n    k   agreement   Clopper-Pearson      §87.2 at n=46
    aligned  144   91      0.6319   [0.5476, 0.7107]     0.800
    crossed  137   72      0.5255   [0.4385, 0.6114]     0.667
    minimum across strata 0.5255                          0.667

**FAILS on the interval, which was pre-registered as the binding half.** So does the as-registered
reading that still selects a depth across strata — it picks layer 9 and reports minima of 0.5547
(`text_mean`) and 0.5839 (`judge_last`), and both miss the interval too. Both readings print and
neither passes.

**§87.2's headline reverses.** That entry's finding was that on the one family carrying an
externally produced label, internals beat surface counting — 0.667 against P0's 0.600 and P0+'s
0.560. At six times the corpus with the readout frozen, the order inverts: **P0 0.5693 and P0+
0.5764 against `text_mean`'s 0.5547.** The surface baselines now win the minimum-across-strata
statistic. §87.2 disclosed that its comparison favoured the probe by construction, because the
probe got three depths and each counter got one; removing that asymmetry removes the result.

**And the residual §87.2 named third is the one that bites.** Its three reasons not to believe the
number were corpus size, the 21-pair `crossed` stratum, and *tier* — the worry that a readout could
be reading amateur-versus-established register rather than anything about quality. The median split
measures it:

    sub-stratum       n    agreement   Clopper-Pearson      P0      P0+
    crossed, tight   68       0.5147   [0.3903, 0.6378]   0.6029  0.6029
    crossed, loose   69       0.5797   [0.4548, 0.6976]   0.5362  0.5507

**The readout scores in the loose half and not the tight one**, which is the signature of a tier
reading rather than a prose reading — and where views are matched, the plain surface baseline beats
it by nearly nine points. Neither interval excludes 0.50 and neither half is a result on its own;
the contrast is, and it points the way §87.2 feared.

### 89.3 Panel v2: layer 1 votes on nothing, and that is the design

`composite_panel.py`. §86.6 disqualified the incumbent on three axioms and §87 explained why in a
way that changes the architecture rather than the tuning: **every instrument that answers a slot
fails and every instrument that measures without being asked succeeds.**

    layer 1  counters   deterministic. Can VETO a comparison; can never pick a side.
    layer 2  readout    FROZEN_READOUT, BEHAVIOUR-class. Recorded; decides nothing.
    layer 3  verdicts   the Track E survivor, if one survives. The only source of preference.

**Layer 1 vetoes rather than votes, and the reason is §82 rather than caution.** A counter measures
that two texts differ on a named axis; it does not measure which is better, and supplying that
valence would assert craft doctrine — "told feeling is worse", "em dashes are a tell" — as a
premise, when §87.1 and §87.3 record it as the hypothesis under test. So a counter here is licensed
to say *"there is nothing here to prefer"* and nothing else. That is a statement about the material
rather than about taste.

What it buys is structural: **the composite cannot express a preference between a string and itself,
or between two texts differing only in whitespace.** Those are the two failures §83, §85 and §78.1
each had to void an arm over, and they are now unreachable rather than merely unlikely.

The aggregation was declared before the battery ran: layer 3 alone decides, layer 1 decides only
that there is nothing to decide, layer 2 is recorded, and **disagreement between layers 2 and 3
produces a diagnostic and no change of verdict** — resolving it in the readout's favour would let
BEHAVIOUR-class evidence decide a preference, and resolving it in the verdict's favour would discard
the only signal that §87's report deficit is present inside the instrument.

**A composite with no layer 3 is still a composite, and the battery says exactly what it is.**
Run through T0 with no verdict layer — free, because nothing is called — against the incumbent's
own run on the same 54 pairs:

    axiom                        incumbent (as-reg / corrected)        composite, no layer 3
    A0_indifference              FAIL / PASS   tie 0.875, bias 1.000   PASS   tie 1.000, 0 decided
    A1_format_invariance         FAIL / PASS   tie 0.542, bias 0.727   PASS   tie 1.000, 0 decided
    A2_dose_monotonicity         FAIL / FAIL                           FAIL
    A3_transitivity              -                                     UNREADABLE
    A5_within_item_consistency   PASS                                  FAIL   (ICC undefined)
    A6_position                  FAIL / FAIL                           UNREADABLE

**The two axioms the veto layer was built for are the two the incumbent measurably failed**, and
the composite passes them deterministically rather than luckily: A0 and A1 put two texts of
identical content in front of the instrument, and layer 1 refuses them before any judge is asked.
The incumbent's as-registered failures there are bias 1.000 on six decided comparisons and 0.727 on
twenty-two.

**Everything that needs a decision is failed or unreadable, and the battery is right to say so.**
A2's own reading is the sentence to quote — *"all-ties is not monotonicity"* — and A3 and A6 come
back UNREADABLE rather than passed, so the battery already refuses to credit an instrument for
having no opinion. That refusal is worth noting because it is what stops this run being a fake
improvement: a composite that ties everything is not a better judge, it is a judge with the verdict
layer removed. A5 is the honest regression — its ICC is undefined on a constant answer, where the
incumbent passed.

So the composite is **not a v2 candidate on this evidence** and is not offered as one. What the run
establishes is that the assembled object satisfies the battery's contract, that layer 1 does the
job it was designed for on the axioms that measure it, and that everything else waits on Track E.
§84's freeze remains an operator act and nothing here asks for it.

### 89.4 Track E: the verdict channel cannot carry it, and the report channel can

`elicitation_study.py` carries E1, E2, E4, E5 and E6 with `PRE_REGISTRATION` committed before the
first elicitation (`b9fd89a`); `verdict_locus.py` carries E3 and the locus ladder (`a70975a`).
**E3 is the arm that answered the question, and it is the free one.**

**The ladder, on `gemma-3-4b-it` at the pinned revision. 53 pairs, 106 forward passes, no quota.**
Stations 1 and 2 are the probe's single-text readouts; 3 and 4 are this module's pairwise pass.

    family                        st1 text_mean  st2 judge_last  st3 logits  st4 sampled
    stat_flatten                       10/10          10/10          6/10        0/0
    interiority_strip_matched           9/9            5/9           6/9         0/0
    repair_emdash                       8/8            8/8           5/7         0/0
    placebo_identical  FLOOR            0/8            0/8           0/0         0/0
    rewhitespace_sham  VOID           10/10          10/10           4/8         0/0

**Station 4 is a total collapse and it is not close.** The greedy verdict is `A` on **106 of 106**
passes — every pair, both orientations, every family, the byte-identical placebo included. The
argmax was a valid answer token every time, so this is not a formatting failure: the model answers,
and the answer carries no information about which passages it was shown. Every family reads 0/0
decided, because a constant slot answer cancels between orientations by construction.

**Station 3 says why, one step earlier.** Splitting the answer distribution into the component
invariant under swapping the passages and the component that flips with them:

    pooled     |positional| 0.9998      |text| 0.000214      ratio 4676x

The text-dependent residual is real — `placebo_identical` cancels to **exactly** 0.000000, which is
the arithmetic check that the rest is a difference and not floating-point noise — and it is about
two ten-thousandths of the answer distribution. Read as a sign test it is 6/10, 6/9 and 5/7 on B6's
three families: the right direction on all three and significant on none.

**So the loss is not at sampling, and that is the finding.** The directive framed the two
possibilities precisely — alive at station 3 and dead at station 4 means the loss is in sampling
and a protocol can recover it; already dead at station 3 means it is upstream of the verdict and no
protocol can. It is already dead at station 3: 0.02% of the distribution at the position the
verdict's first token comes from. **A better way of asking cannot be the fix for this model**, and
the composite's architecture — put the deterministic counters in front rather than behind — is the
correct response rather than the fallback one.

Bounded exactly as §87 bounds it. This is a 4B open model and not the Haiku panel, so it is a lower
bound on decodability rather than a statement about what Haiku perceives. What it does explain is
§83's and §85's positional voids: the panel answering the slot is not a quirk of those arms, it is
the dominant term. And `rewhitespace_sham` is worth its own line — 10/10 at stations 1 and 2 and
4/8 at station 3 — so the channel is not selectively losing prose, it is losing everything,
formatting included.

**Three faults surfaced in the dry run, before anything was bought.** E6 cannot use the sign test
the other five share: a two-sided test credits consistent *silence* exactly as much as consistent
naming, because `k` is the larger of the two counts by construction, so a matcher that fires on no
pair reads `k = G` and prints CLEARS. It now uses a one-sided Fisher exact against a null measured
in the same run. E4's sign was a persona vote, which with two personas ties whenever they disagree
— about half the pairs under a null, dropping G below the floor for arithmetic reasons of our own;
it is now the paired difference of means, and G went 3/3/2 to 10/9/8. And `_synthetic_text` knew
none of the new stages, so the dry run marked every E4/E5/E6 answer refused and exercised none of
their scorers — a check that could not fail on the paths it existed to check.

**The directive's floor is kept and its stated reason is not.** `2/2**G` was inherited from §87
with §87's justification, invariance under a global sign flip. That invariance is a property of
§87's *fitted* direction, and B6's counters are named a priori with nothing fitted, so no twin
exists and the one-sided floor would be `1/2**G`. The floor holds for a stronger reason: **the
alternative is non-directional** — B6 certifies that a difference exists and never which side is
better — and taking the one-sided test would have been taking the more permissive statistic after
seeing which way §81's rates pointed. Declared before the run: k = 9 of 10, 8 of 9, 7 of 7, and
`repair_emdash` at G=7 clears only on a perfect seven with no margin at all.

**The API arms landed after all, and one protocol survives.** 212 comparisons for E1/E2 and 212
responses for E6, on Haiku, at four workers: **172 calls, 252 replayed, and zero transport
failures**, $9.98. The 252 replays came from a cache seeded with three prior runs' records —
`repair-panel-raw` 192, `persona-raw` 1,566, `cdg-raw` 962 — and covered about sixty per cent of
the schedule for nothing, which is what rail 6 is for. Which records they were is identifiable
where it matters: the two repair families reproduce §85's bias figures *exactly*, 0.6949 and
0.4918, because they **are** §85's records rather than fresh measurements of them.

    protocol  precondition                                     verdict
    E1        OUT_OF_BAND  chose-A 0.6408 on 142 decided       VOID
    E2        OUT_OF_BAND  (same records, ties dropped)        VOID
    E6        SYMMETRIC                                        SURVIVES, 3 of 3 families

**E1 and E2 are void on their own precondition, on this material, with the depth to say so.**
142 decided comparisons is well past §86.7's floor, and the chose-A rate is 0.6408. The incumbent
answers the slot. Its tie rate is 0.3206, which is why `repair_emdash` fell to G=6 — the tie
arithmetic §89 predicted for E4 turns out to bite E1 instead, and the family that "clears" at 6/6
inside a VOID protocol is not read.

**The VOID is not an artifact of pooling, which is the first objection to make to it.** The
precondition here is protocol-level — one chose-A rate over every family — and that is stricter
than §78.2's per-arm rule, so a single bad family could in principle void a protocol whose B6
families were clean. They are not clean. Read per family, each of the three is out of band on its
own and each clears the 30-decided floor:

    family                     decided   chose-A   in band
    stat_flatten                    42     0.619      no      (new here)
    interiority_strip_matched       36     0.6111     no      (new here)
    repair_emdash                   59     0.6949     no      (replayed from §85)
    repair_interiority              61     0.4918     yes     (replayed from §85)

The last two are §85's own records replayed by digest rather than fresh measurements, and they
reproduce §85's figures exactly because they *are* §85's figures — which is a cache check rather
than a replication and is labelled as such (§79.1). The first two are new. The one family that
sits inside the band is the one §85 already found clean, and it is not a B6 member.

**E6 clears all three families, and the confusion matrix is what makes it credible.**

    axis matcher \ family      interiority  placebo  em dash  repair_int  sham  stat_flatten
    interiority_strip_matched       18/36     0/32     5/32      32/32     0/40     0/40
    repair_emdash                   12/36     6/32    30/32      23/32    15/40     3/40
    stat_flatten                    10/36     2/32     8/32       9/32     2/40    40/40

    axis                        own     null    confabulation   Fisher p
    stat_flatten              1.0000   0.2071      0.0625        <1e-6
    interiority_strip_matched 0.5000   0.2569      0.0000        0.00512
    repair_emdash             0.9375   0.3581      0.1875        <1e-6

**The sharpest pair of numbers in the session is on one row.** §81 measured the panel on
`stat_flatten` at **0.5437 — BLIND, with the estimate on the wrong side of indifference**. E6 asks
the same model family about the same pairs and gets the axis named **40 times out of 40**, in
sentences like the one quoted below. The transform is not subtle — digits become question marks —
and that is what makes the contrast diagnostic rather than merely favourable: a difference this
easy to *describe* was invisible to the same instrument asked to *prefer*. Nothing about the
model's access to the text changed between those two numbers. Only the question did.

The diagonal dominates and the off-diagonal is *structured rather than noisy*: the interiority
matcher fires 32 of 32 on `repair_interiority` — a genuine interiority edit — and 0 of 40 on
`stat_flatten`. Because `repair_interiority` sits inside the null pool, that 32/32 **inflates the
interiority null to 0.2569 and makes its test conservative**; the pass is understated rather than
flattered.

**The responses are the check the matcher cannot be.** On `stat_flatten`: *"Passage A shows Wren's
status with concrete values (Level 2, HP 19/22) while Passage B shows all status values as unknown
(?)"*. On the em-dash arm: *"Passage A uses em dashes to set off appositional phrases... while
Passage B replaces those em dashes with periods"*. On the **placebo**: *"The passages are
identical; there is no discernible difference between them."* On the **sham**: *"Passage A uses
single spaces after periods; Passage B uses double spaces after periods."* The model names
formatting as formatting and declines to invent prose differences where there are none — which is
the behaviour §83 and §85 could never get out of the same model through a preference question.

**Interiority's 0.50 is a fixture ceiling and not a perception limit.** `interiority_strip_matched`
is *matched*: one side loses interiority and the other loses a comparable quantity of something
else, so the pair genuinely has two salient differences and E6 asks for the single most salient
one. The misses are responses naming the other real difference — *"Passage B ends with a full game
status interface… while Passage A ends with only a fragment"* — which is a correct answer to the
question asked. §87's lesson that the fixtures are the ceiling recurs here in the one place it can
be seen directly.

**What E6 surviving does and does not buy, stated narrowly.** It is a **report** protocol: it asks
what differs, never which is better. So it can staff a *discrimination* layer and it cannot staff
a preference layer, and JudgeBench A2's verdict layer — the thing that would let a composite
express a preference — is **still empty**. §82 is untouched: PREFERENCE remains a human's blinded
choice and no arrangement of these results changes that.

**Read against E3, the two halves make one finding.** Same model, same pairs, same session: asked
to prefer, Haiku answers the slot at 0.6408 and is void; asked to name the difference, it clears
three of three. And a 4B model's internals show the mechanism the API cannot expose — at the
verdict token the answer distribution is 4,676x position over text. **The instrument is not blind.
It is being asked the one kind of question its verdict channel cannot carry.** That is the
directive's question answered, and the answer is a design instruction rather than a budget: put
the difference-detection in a channel that reports, and route preference to a human.

### 89.5 What was not run, and what it would cost

- **Track V's two funded arms** (voice-binding dose $9.30, persistence $1.90; operator: FUND) are
  built, pre-registered and **launched once Track E's arms finished**, not before: they need
  `claude-opus-5` generations through the same transport, and two CLI jobs sharing this box is what
  produced the 390 failures. 48 generations, ~$11.20. Their numbers are not in this entry and land
  in their own; `voice_binding.py` carries the pre-registration and `results/voice-binding.json`
  the result.
- **E4 and E5** were dropped from the running schedule so E1/E2 and E6 — the incumbent and the
  purest report test — would land first, and they are the two the result now makes most worth
  buying. E5 asks E1's question with a description already in the context, which is precisely the
  seam E6 just showed is open; E4 removes the slot entirely, which is the other half. Deferred
  rather than cancelled, ~$11 the pair at the measured rate.
- **The axiom battery on the composite with a real layer 3** is now runnable and was not run.
  E6 survived, but it is a report protocol and the battery asks for preferences, so wiring it in as
  layer 3 would require deciding what a named difference implies about which side is better —
  which is exactly the valence §89.3 refuses to invent. The honest next step is a battery run with
  E6 feeding layer 1's veto rather than layer 3's verdict, and that is a design change rather than
  a run.
- **No licence moved, no bar was re-declared after numbers arrived, and the §85 operator read was
  not opened.**

## 90. The loop closes on two roles split by valence, and the split is measured rather than chosen

The reader→writer directive (2026-08-19). Until this entry, nothing a reader said about prose
reached the thing that writes the next prose, by any path — `audit_samples` at 0 rows,
`calibrations` at 0 rows, and the one machine channel touching drafting (`plan_search`'s licensed
judge) rendering *verdicts*, which is the frame this project has now measured dead three times.
The design is `plan/reader-judge-loop.md`; this entry carries what it decided and the three
things the build found that the design did not predict.

**The split is not human-versus-machine. It is valence-versus-location, and the record forces
it.** A **READER** owns valence — would I keep reading, which of these two would I rather
continue — and nothing else may. A **JUDGE** owns location and axis and never valence. The
licence in each direction is a measurement, not a preference:

    frame                                   result                                    where
    verdict, T0 axiom battery               DISQUALIFIED; A6 chose-A 0.8151 / 568     §86.6
    verdict, E1/E2                          VOID on precondition; 0.6408 / 142        §89.4
    verdict, persona absolute               keep-reading on 195 of 196                §70
    report, E6 "name the difference"        clears 3 of 3 B6 families                 §89.4

**Neither source is a signal alone, and that is the load-bearing rule.** A reader establishes,
over few and expensive verdicts, the **direction** of an axis; a judge applies, cheaply and per
span, the **discrimination** on it. Direction without discrimination cannot be applied to a
draft; discrimination without direction cannot say which way to move. In code this is a
constructor precondition rather than a convention — `FeedbackItem` cannot exist without an
`AxisDirection`, and a judged difference on an undirected axis is discarded and *kept* (below).

**The counter decides which side; the judge only decides which axis and where.** This is what
makes seating a T0-disqualified model family as Judge defensible rather than hopeful: every arm
T0 fired on is a property of the *verdict channel* — A6 is chose-A over **decided comparisons**,
and a protocol asking for no choice produces none. The sharpest evidence is §89's own: §81
measured this panel on `stat_flatten` at **0.5437, BLIND, on the wrong side of indifference**;
E6 asked the same family about the same pairs and got the axis named **40 of 40**. Nothing about
its access to the text changed. Only the question did. So the judge is admitted, confined to E6's
frame, with `E6_QUESTION` and `AXIS_MATCHERS` copied **byte-for-byte** under a test, and with a
placebo and a whitespace sham riding every batch. §82 is untouched and JudgeBench A2's verdict
layer is still empty.

**Three axes, and the shortlist is an intersection rather than a choice**: §74's human read named
flat stats, no interiority and em dashes, and those are the same three families E6 clears on.
`plan/reader-judge-loop.md` §2.1 makes that birth story the **only** admission path — a named
defect from a human read, or a nomination from the discard corpus — which also gives every future
human read a defined product: a read is a *defect harvest*.

### 90.1 The prerequisite was closed by a parallel session, and separating the roles reopened two holes

§86.1's laundering path — `analysable_judgments` never inspecting `reader_id` while `plan_search`
wrote a licensed judge's verdicts through the same pair table — was closed as §86.6 before this
work began (`MACHINE_READER_PREFIX`, excluded from the denominator, kept in the staleness digest,
guarded by `test_a_machine_written_row_can_never_denominate_a_preference_holdout`). Verified in
source rather than assumed.

**Separating the roles makes the residuals worse rather than better**, because the entire point
of the split is to run judges at volume and volume is what turns an open path into a laundered
pool. Two closed here:

1. **The prefix was opt-in at one write site and unowned everywhere else.** `pair-judge` and
   `pair-import` accepted any reader id including a reserved-prefix one, so a *human* row wearing
   it would vanish from every PREFERENCE denominator silently. Both human paths now refuse it,
   and the prefix means exactly one thing.
2. **The Judge writes no `PREFERENCE`-shaped row at all.** `located_differences` is its own table
   with its own columns — no verdict, no pair sample, no laundering surface **by construction
   rather than by filter**. That is the structural version of the same fix, and it is the half
   that scales.

What cannot be closed: an importer claiming a human name for machine output. `--source` is now
required and recorded on every row's event, which is the honest half — a dump cannot arrive
anonymously even though it can arrive mislabelled.

### 90.2 The firewall binds §61's own runbook, and that is the correct blast radius

I1 requires readers *and* comparison passages split before the first verdict is routed. Built as
a write-once `PoolRegistration` with content-derived draws, `audit.bucket_for`'s discipline
inherited whole. **The consequence is larger than the new loop**: `pair-draw`, `pair-judge`,
`pair-import` and `directions` all refuse until the split exists, external pairs draw only over
measurement-pool scenes and sibling pairs only over steering-pool spans, and every
operator-surface test in `tests/test_preference.py` now starts by declaring it. One operator
command lands in front of the existing preference runbook.

That is the right blast radius and the smaller version would have been wrong: a passage split
protecting only the steering side would leave §61's own side open, which is the wrong half to
leave open. **What the two halves buy is not equal and the design says so**: the *reader* split is
the lock (a reader is in one pool for life, so the two questions are answered by disjoint people);
the *passage* split is weaker, because if the loop works at all every scene of a steered book is
shaped and no passage-level split undoes that. What it buys is narrower and still worth having —
a passage's own verdicts never feed back into the prose it is later compared as.

**The residual is stated rather than discovered later**: nothing stops one person holding two
reader ids in different pools. `litharness pools` prints that sentence under every listing.

### 90.3 The bar was wrong in the direction of false failure, and checking it is what found that

I7 asks for range, direction, unit and non-emptiness before a threshold is committed, and notes
that T0's own registered bar disqualified a *good* judge 82–100% of the time. Running the same
check on this design's bar found two defects before any verdict existed:

- **The reader-cluster floor was 3 and is now `DESCRIPTIVE_CLUSTER_FLOOR` = 5.**
  `win_rate_lower_bound`'s own docstring records that below roughly five clusters per dimension
  the percentile bootstrap is descriptive rather than calibrated. Reading a direction off a
  descriptive number is reading an interval that has not earned its level.
- **A zero-width-band refusal was written and then deleted, and the deletion is the finding.**
  The rule read "both one-sided bounds summing to 1.0 is degenerate, refuse". At the *two*-reader
  floor that is §85's zero-width defect; at *these* floors it is **unanimity** — thirty cells over
  five readers and eight pairs all pointing one way, the strongest evidence the channel can
  produce — and the rule would have refused it. The cluster floors already exclude the
  four-observation case it was aimed at.

**And the floor turned out not to be a sample size, which is the number an operator actually
needs.** Measured at the declared shape:

    smallest clearing k    22 of 30 cells

    true rate   power at 30 cells   cells for 80% power
      0.55            0.031                 220
      0.60            0.094                  90
      0.65            0.225                  60
      0.70            0.432                  50
      0.80            0.871                  30

At a true 0.60 the floor fires under a tenth of the time, so a null from thirty judgments would
say nothing about the axis. `litharness directions --attainability` prints the last column and
says that in words. It lands where §61's independent sizing landed — 90 cells at 0.60 against
§61's "roughly 100–150 decisive judgments" — which is a cross-check nobody arranged.

**The unit is the `(reader, pair)` cell, not the comparison.** §89 item 6 recorded a 30-decided
floor that could not bind because four personas were one judge four times; the same failure is
available from the other side, since both orientations of one pair answered by one reader are
**one** decision. A reader who flips with position has said nothing and collapses to a tie, which
is the only reading under which a position-swapped design measures anything.

### 90.4 The discard bucket is retained verbatim, and it is the one change that would have lost data by waiting

Arrived as an operator addendum mid-build. The E6 channel is scored by a frozen matcher over three
axes, and steps that find no match, no direction, or no counter separation each *discard* a
sentence. Counting them throws away the most interesting thing the channel produces: **an
unmatched sentence is a field report about a salient difference the axis registry cannot yet
name** — the same object §74's human read produced, from a channel that runs at volume instead of
once.

Every one is now stored verbatim with its provenance (pair addresses, batch, orientation, judge
id, separating counters, whether the batch's controls held), under five reason codes that are
different facts about different things — `unmatched` is discovery, `undirected` is the
composition rule biting and a queue of what reader evidence would unlock, `unseparated` is the
judge claiming a difference the material does not carry and is therefore a *judge*-quality
signal. A sentence from a VOID batch is retained and marked, because a confabulating judge's own
words are the evidence.

**The rail, in the table's own comment as well as the domain's**: this corpus may **nominate** a
candidate axis and may never **validate** one. A matcher drafted from these sentences and scored
against them is a rubric fitted to its own answers, which is exactly what freezing the matchers
prevents. A nominated axis takes the full path — counter, E6-family validation on *fresh pairs
the corpus never touched*, reader direction — before it emits anything.

### 90.5 What was run, and what it refuses to say

`research/quality-measurement/feedback_ablation.py`, pre-registered before any arm was generated,
four arms (`off`, `reader_only`, `judge_only`, `both`) because two would not say which half did
the work. Its selftest passes on ten constructed claims. Its `--wiring` run drives all four arms
through the real loop on the padded fake provider with a synthetic direction:

    arm            scenes carrying feedback    target counter
    off                       0                 baseline
    reader_only               6                 unchanged
    judge_only                0                 unchanged, BY CONSTRUCTION
    both                      6                 unchanged
    overall:  INERT_GENERATOR      reader side:  UNDECIDABLE (0/30 cells, 0/5 readers, 0/8 pairs)

It establishes that the feedback text reaches the frozen payload of every drafted scene in the
arms that should have it and none of the arms that should not. **It refuses to read the flat
counters as a null**: `INERT_GENERATOR` is its own verdict, because a generator that answers
every prompt identically has said nothing about the loop and a bare NULL would be quotable as
"feedback does not work". §57's lesson, wired in rather than remembered. And `judge_only` carried
nothing because the pilot runs no tournament — the report says so in its own field rather than
letting the control-under-another-name read as a measured null.

**No licence moved. No axis has a direction. No reader has been paid.** With no direction the
judge half refuses before it spends anything and the whole loop resolves to an empty feedback
set, which is recorded explicitly rather than omitted — `scene_feedback` carries an empty item
list and the empty set's real digest, because "this scene had no feedback" and "nobody recorded
whether this scene had feedback" are different facts. The emptiness of `axis_directions` is now
the measure of the gap, the way the emptiness of `calibrations` already was.

**Two register entries, designed and named and not built**: a **paraphrase sham** (same content,
different surface) to catch a judge or counter firing on surface features carrying no
reader-visible difference — a register entry rather than a task because certifying "same content"
honestly is the hard part, and a sham whose own premise is unverified is a control that cannot
fail; and the **promise/payoff ledger** as a candidate counter family, which is the right shape
(deterministic, span-locating, judge-free) and is strictly a hypothesis axis under §2.1's
admission path.

**The CLI verb `judge` is renamed `read`**, because it records a *reader* verdict and was
backwards under this split. The old name still works and warns; the cost of the rename was small
now and grows with every row.

## 91. A third role, safe for the opposite reason to the other two: it measures nothing

The Director directive (2026-08-19), landing beside §90. The operator asked for a Director role
with a personality, experimentable across several, taking human feedback but working with none by
default. The design is `plan/director-role.md`; this entry carries the licence argument, the third
costume of the laundering path, and the two defects the build found in its own rails.

**The objection to answer first, because this project has spent months earning it.** A machine
cannot be trusted to have opinions about prose — T0's panel DISQUALIFIED, §89's E1/E2 VOID, the
persona reader constant at 195 of 196. A third role that opines sounds like a fourth attempt.

**It is not, and the distinction is structural rather than rhetorical: every dead frame was
evaluative and downstream.** Each was handed prose that existed and asked how good it is. A
Director is *generative and upstream* — it says what the book should be, before any of it exists.
That is not a measurement, so it cannot be an invalid one.

    role      acts     on            answers                     licensed by
    DIRECTOR  before   nothing yet   what should this book be    nothing; it measures nothing
    JUDGE     after    two drafts    what differs, and where     E6, 3 of 3 families
    READER    after    two drafts    which would I keep reading  the only surviving valence channel

So the Director needs no validity licence. What it needs is **containment**, because a role that
measures nothing is exactly the role through which unmeasured taste walks in wearing something
else's authority.

### 91.1 The laundering path, third costume, closed while still free

`judge-validity-program` §1.1 found it in the pair table; §90 found two more when the Judge was
split out. Checked in source before the design was written, not assumed:

- `directive_planner` writes an explicit constraint or veto into a plan item with `locked=True`,
  verbatim and by design, because those words are the director's.
- **`narrative_planner` lets the model set `locked` on every edit it proposes** — the schema
  carries the boolean and the parser accepts what comes back.
- `plans.constraints_of` selects locked constraints and `context.assemble` puts them in the
  packet's CONSTRAINTS section, priority 2, above threads, facts and prose, effectively never
  dropped.
- **`Directive` had no author.** Not a column, not a field, not a check.

So the moment a machine writes a directive, its words enter every subsequent context packet as a
locked constraint carrying the director's authority, with nothing on the record saying a machine
wrote them. §86.1's shape exactly — a property enforced by who happens to hold the pen — and inert
only because the table had no machine rows.

**Closed at three points.** `Directive.author` is stored and is part of `directive_id_for`'s
material, so the same words from a person and from a Director are two directives and a machine row
cannot be silently reattributed; existing ids are unchanged, because a migration that moved them
would break every `produced_constraint_ids` reference pointing at one. The **verbatim** lane
refuses machine authorship outright. The **interpretive** lane forces `locked=False` on every edit
derived from a machine-authored directive, downgrading rather than refusing — the direction is
legitimate and only its authority is not — which also empties that proposal's produced-constraint
list, so there is nothing left to cite.

The licence rule falls out in one line: **a Director's kinds are exactly `INTERPRETIVE_KINDS`.**
Constraint and veto are the verbatim pair and a veto is a *refusal*, which is authority; `CONTROL`
is pause/resume/kill, which is operator state. A Director says what the book is about; it may not
refuse anything and it may not stop the machine.

### 91.2 A brief may name what the book is about and not what good prose is — and reusing the Judge's matchers to enforce that failed

The sharper rail, because the Reader/Judge loop would otherwise have a back door straight through
it. §90's §2.1 makes axis admission a four-step path — human read, counter, E6 validation, reader
direction — and a Director brief goes **straight into the drafting context**. A brief saying "cut
the em dashes" would inject a prose axis with none of the four. Not hypothetical: `em_dash`'s own
pre-registered hypothesis is still VOID with the estimate leaning *toward* the mark (§78.3), so
that director would be asserting as premise the thing the loop exists to test.

**The first guard reused `AXIS_MATCHERS` and had to be withdrawn, which is the finding.** Reuse
looked obviously right — those matchers define what naming an axis means, and a second vocabulary
would drift. Run once, it rejected this design's own first example brief, on the sentence *"every
level gained should have cost something"*: `stat_flatten`'s matcher contains `level`, `tier`,
`stat`, `value` and `count`, which are ordinary LitRPG **story** words.

The lesson generalises. `elicitation_study` says in as many words that those matchers are
*"deliberately generous about vocabulary and strict about topic"*, because E6 asks whether an axis
reached the output at all. **They are tuned for recall on a description task, and a refusal gate
inverts the error economics** — in E6 a generous list costs a false positive that reads as a miss;
as a gate it costs a refusal of legitimate direction. Same list, opposite cost. The brief guard
now has its own narrow, precision-tuned vocabulary and states the trade: it catches "avoid em
dashes", it does not catch a paraphrase, and no regex would.

**And the strongest containment needed no vocabulary at all: the Director is never shown the
prose.** It gets the premise, the scene statements, the ledger's open promises and the scene
*summaries* — what happened, never how it reads. `DirectorStore` has no `ManuscriptWriter` and the
handler never reads `node.content`. A role that cannot see the text cannot render a verdict on it,
which turns "may not evaluate prose" from an instruction into a property of what it was handed.

### 91.3 A personality has to be earned, and the control that checks it could not fail

The prior against "give it a personality" is this repo's own: §89.1's `qwen3:14b` returned **one
distinct answer vector across four personas, byte-identical**; §83 found the register invariant to
simulated phenomenology; §77 measured persona-to-passage sum-of-squares ratios of 0.0028, 0.0071
and 0.0342 while one word of question change moved a rate ten points. So "experiment with
different directors" is a claim to check before it is made, or it is §89.1 in a third costume.

`director_distinctness.py` draws from each director on the same book state and requires the
between-director distance to clear the within-director spread. **Its first version had four
readings and the fifth exists because running it produced one.** On the fake provider every pair
came back `DISTINCT` at `within = 0.0000` — every draw byte-identical to its siblings, because a
deterministic generator handed the same request returns the same answer. With no wobble to clear,
*"between exceeds within"* is satisfied by a single differing character: **the rail passed and
could not have failed** (§50: a control which cannot fail is not a control).

`DISTINCT_NO_FLOOR` now carries that case. It keeps what the weaker reading does establish — the
briefs are *not inert*, which is what §89.1's failure was about — and refuses it the word that
implies a margin. The run: three built-in briefs, all pairs `DISTINCT_NO_FLOOR`, `between 0.8462`
against `within 0.0000`, `COMPARABLE`, floor warning attached. It establishes that the briefs
reach the request and change it; it establishes nothing about a real model's personality, and the
results file says so in its own field.

### 91.4 What experimenting with directors costs, computed rather than waved at

**N directors divide §61's alpha by N.** Pre-registration (5) is explicit: *"If more than one book
could have been reported, the confidence level is divided by the candidate count."* Picking the
best of N directors and then measuring that book against matched published prose is precisely
reporting one of N candidates. At three directors the superiority claim is made at **α = 0.0167**,
and §61's own sizing records what a thinner margin costs — 100–150 decisive judgments at a true
0.60, 400–500 at 0.55, clustering inflating both.

The harness prints this beside every verdict rather than leaving it to be discovered after the
money is spent. The comparison itself rides the internal frame in the steering pool, so it does
not contaminate §61 directly; what it costs is the headline's confidence level, which is the one
currency this project is shortest of.

### 91.5 Bounded, subordinate, off by default

One directive per block of `DIRECTIVE_EVERY = 6` accepted scenes, keyed into the job id so a
replayed tick converges. The obvious alternative — one per plan epoch — is a spin loop wearing a
bound: a directive becomes a plan application and a plan application bumps the epoch, so the bound
resets itself. Tying the cadence to accepted scenes cannot do that, because nothing a Director
says drafts a scene. A second bound sits beside it: a Director with a directive still awaiting
interpretation stays quiet, so the inbox cannot fill with machine direction while a person's sits
behind it. `DIRECT_PRIORITY = 400` is beneath both human lanes (1000+, 500+) and above the
drafting it shapes.

`--director <name>` mirrors `--plan-search`, for the reason that flag gives in its own help text:
a director is an arm and no director is its control. An unregistered name is **refused loudly**
rather than defaulted to no director, because a typo that silently produced the control arm would
be the worst possible failure for an experiment whose whole question is whether the arms differ.
Admitting a personality is an operator act (§84's rule), and the three built-in briefs are
examples written to exercise the distinctness control — nothing claims any of them is good.

**No director has been compared to another on prose, and none will be until a reader exists.**

## 92. The library is a copy button, and the two shapes it writes have opposite requirements

*(§93 revises this entry's folder name and its cadence: the folder is `book-library/`, resolved
beside the database, and publishing is on by default rather than behind `--library`. Everything
below about the two shapes, the withholding rule and the §62 boundary stands.)*

An operator ask (2026-08-19): a folder inside the harness that the work is periodically
published to, so progress can be checked by looking rather than by remembering a command — and,
added mid-build, output that pastes cleanly into Royal Road. `application/library.py`,
`litharness library`, and ~~`--library DIR` which republishes after every tick~~ *(§93: on by
default)*.

**Most of this already existed and had no cadence and no place.** §62 ratified `export` as the
manual publication mode and its own docstring anticipated the use in as many words: *"two exports
a day apart should differ in a way you can read at a glance, which is what 'see progress over
time' means mechanically."* What was missing was that nobody ran it, `exports/` was a scratch
directory of hand-run renders, and there was no index. So this entry is mostly a cadence, and the
one genuinely new thing is the second shape.

**The two shapes have opposite requirements, which is why they are two files and not one.** The
*reading copy* is `export`'s document unchanged — whole book, derived front matter, progress
table, undrafted scenes as visible placeholders, and the gaps are the most useful thing on the
page. The *pastable copy* must contain none of that: a progress table pasted into a chapter body
publishes the scaffolding, and a placeholder publishes the words `[not yet drafted]` to readers.
So the pastable file carries no front matter, no revision id, and **no title heading** — a serial
platform takes the chapter title in its own field, so a heading in the body is published twice.

**A chapter holding an undrafted scene is withheld whole and counted.** Not emitted with a hole,
and not silently reduced to its drafted scenes either: a chapter that dropped its gap and kept
the rest would publish a jump-cut, which is worse than publishing nothing because nothing is
visible and a jump-cut is not. The withheld count is on the index, because a pastable set that
silently skipped its gaps would read as a finished serial — the one way this folder could
mislead about the thing it exists to report.

**One scene is one chapter by default, and that is the chapter-grain refusal inherited rather
than a new opinion.** Production books hold no chapter nodes and no assembly scheme is decided;
`pair-draw` already refuses chapter grain on exactly that ground rather than improvising one.
`--chapter-scenes N` exists because a real serial wants grouping, and it makes the assembly
scheme an operator act.

**The HTML is a fragment and the claim about it is bounded.** Only `<p>`, `<blockquote>` and
`<hr>`, no classes, ids or styles — the conservative subset every rich-text editor preserves —
and a fragment rather than a document, so a browser renders it for select-all-and-copy while an
HTML source view gets no `<head>` to strip. **What this repository cannot do is verify how any
particular platform's editor treats a paste**, so a `.txt` sits beside every fragment: plain text
with blank lines between paragraphs pastes as paragraphs everywhere. A fallback is the honest
response to an unverifiable claim; asserting the HTML works would not have been.

System-voice lines become `<blockquote>`, and that is labelled as a rendering choice rather than
a fact about the prose: a stat block set as an ordinary paragraph reads as a sentence, and the
genre sets it apart.

**What this is not, stated because the name would otherwise claim it.** §62 cut the
serial-publication pillar after measuring it at two inert enum values, and enumerated seven
things it lacked: chapter-release unit, hook placement, recap generation, **per-chapter export**,
publication policy object, posting scheduler, publication table. This adds exactly one of the
seven and none of the other six. §62 also settled what publishing *is* here — "publication is
that export, run when the book clears §1a.5's bar" — and no book has cleared it. So the verb is
`library` and not `publish`: a verb called `publish` would make a claim the tool is in no
position to make. The index says the same thing where somebody about to paste will read it.

**Each shelf carries a `NOTES.md`, written once and never overwritten, and it is the part with
the most leverage.** A human read is not only a progress check. §90's admission path makes "a
human read named a defect" the first of exactly two doors an axis can enter the registry by, and
all three axes the system currently measures came from one read of one book that named flat
stats, no interiority and em dashes. A read with somewhere to put what it noticed is a defect
harvest; a read without one is a memory. The template says what makes a note useful — a defect
that can be pointed at is one a counter can be built for, "chapter four dragged" is a feeling and
"nothing changed across chapter four" is an axis — and carries the caveat that this read is **not
blinded**, so a note from here is evidence of the same class as the first human read rather than
of the class a paid blinded reader produces.

**One contamination note, narrow and worth having.** Reading your own book and dropping a
directive is the intended workflow (§4.3: direct, don't operate). What it makes the operator is a
*steering* reader — so their reader id belongs in the steering pool and never in the measurement
pool, or the prose they shaped and the prose they later judge would be the same prose, which is
what §90's firewall exists to prevent. `litharness pools --who <id>` answers it, and the library
index says so.

**Generated and gitignored**, like `exports/` and `dist/`: the tree is rewritten from the store on
every publish, and a generated tree in the index would leave the working copy permanently dirty
for every parallel session sharing this repository. `NOTES.md` is the exception an operator may
want to keep, and `git add -f` is how.

## 93. The library publishes itself, and the cadence question was already answered by §63

Three operator asks in one message (2026-08-19), following §92: name the folder `book-library`
and let it supersede `exports/`; make publishing *enforced* rather than remembered; and do it at
least every few hours, "maybe you can have a cron setup".

**The folder.** `book-library/`, and the interesting part is not the name but where it resolves:
**beside the database it is derived from**, not under the working directory. That is what makes
the second ask safe. A library rooted at the current directory could not be on by default —
every test that runs a tick would write one into whatever directory pytest was invoked from —
whereas one rooted beside the store follows the store: `bz3.db` in the repository publishes
`book-library/` there, and a test against a database in a temporary directory publishes into
that temporary directory and takes its output away when the directory goes. Verified: the suite
runs green and `git status` is unchanged after it.

**The cadence, and the thing that made it cheap.** Publishing is now on by default after every
tick, with `--no-library` as the opt-out, because a reading copy you have to remember to ask for
is one nobody has. What makes that affordable is a skip: **a book whose head has not moved is not
rewritten.** Revisions are content-addressed, so "the head is the revision this shelf was built
from" is an exact statement rather than a heuristic about timestamps — a `.state.json` records it
per book and the publisher compares. Measured on a six-scene run: the two ticks that drafted a
scene republished, and the evaluation and summary ticks between them wrote nothing.

**The index gained a column, and the reason is that one timestamp would have lied.** It now
carries *Last checked* beside *Changed* per book. Collapsing them is the obvious simplification
and it is the wrong one: a single restamped time says "published just now" about a book nothing
has touched for a week, which is precisely the reassurance somebody checking on progress must not
be given. Two facts, two columns, and the one that answers "is anything happening" is the one
that does not move on its own.

### 93.1 Cron was cut, and the ask is already satisfied by what replaced it

The third request named cron, and §63 is the answer that already exists. **Cut 1 of §61's
programme removed the cron deployment entirely** — leader election, durable pause, the outbox
delivery path, status-as-external-monitor, net −1,103 lines and three tables — and stated the
replacement in one sentence: *"One process runs `litharness tick` in a loop (or a shell loop
does); killing it mid-job loses nothing."*

**Read against that, "publish every few hours" is already beaten by what the loop does.** With
publishing on every tick, the folder is exactly as fresh as the book *at all times*. A wall-clock
schedule cannot improve on that; it can only make it staler, and when the loop is off there is
nothing new to publish anyway. So the answer to the ask is `tools/run-loop.ps1` — §63's operating
model written down so it is the same loop every time — rather than a scheduler.

**A schedule is still shipped, and the distinction that makes it safe is worth recording.**
`tools/schedule-library.ps1` registers a task that runs `library` and **never `tick`**. §63
removed the instance lease that made overlapping invocations safe — *"leader election among
overlapping invocations; one process has nobody to lose the claim to"* — so a scheduled `tick`
firing beside a running loop is exactly the case that lease used to cover and which no longer
exists. `library` is read-only against the store: no lease, no job claim, no mutation. It is safe
to fire whenever, including alongside a running loop, and that is the only reason a scheduled
version of it exists at all.

The script does nothing without `-Install`, and its bare output says why the operator probably
does not want it. Registering a standing task on somebody's machine is persistent configuration
and stays their act rather than an agent's; the artifact is checked in, reviewable, and one
command away.

**What none of this re-opens.** No chapter-release unit, no posting scheduler, no publication
policy object, no publication table — the six things §62 measured the serial-publication pillar
to lack and which §92 added none of. A cadence for *rendering files locally* is not a publication
cadence, and §62's condition on the second one is untouched: publication is the export, run when
the book clears §1a.5's bar, and no book has cleared it.

## 94. The ledger learns what kind of debt it holds, and a budgeted reader is priced before it is believed

The promises-and-payoffs directive (2026-08-19), executing
[plan/llm-reader-engagement.md](llm-reader-engagement.md). Two halves that only look unrelated:
the unbuilt half of PLAN.md §9.1's foreshadow-payoff ledger, and a reader instrument whose
whole reason to exist is that the cheapest way to game a continuation metric is to open loops
and never pay them. The design is [plan/promise-payoff-development.md](promise-payoff-development.md);
this entry carries the scope, the pre-registered bars, and — because it was found before a
single call was bought — the substrate finding that decides how much of the second half can
currently be said at all.

**§92 and §93 were taken by parallel sessions while this was being written**, which is the
house rule working: this is §94 and nothing above it was renumbered.

### 94.1 What is added, and what deliberately is not

The ledger that landed as §61 Add 2 records *that* a book owes something and *whether* it was
paid. It does not record **what kind** of debt it is, nobody schedules **when** payment is
due beyond a model's one-shot `due_hint`, "a cadence a reader can feel" is an **unmeasured
claim** in PLAN.md §1a.3's own words, and payment is asserted by the **same call** that
reports it. Four gaps, and they are deliberately not four features: two are code (W1, W2) and
two are studies whose null is a publishable result (W3, W4).

**The LitRPG progression schedule stays out, and the reason is a verified absence rather than a
scheduling preference.** Checked in source: there is no forward Game-System Engine interface in
this repository — no `GameSystem`, no `WorldRule`, no `BookWorldState` under `src/` — because
§8.4 put the rule and predicate vocabulary in the game-mechanics pack inside
ContinuityEvaluation and §8.1's forward interface "has no consumer until Stage 0/1 exists".
What this repository has is a schedule *validator* (`outline._milestones`, `impossible_fields`)
and a schedule *reader* (`extraction.progression_target`), not a simulator. So W2 schedules
payoffs — which need no engine, because a window names scenes and scenes are `beats_for`'s own
minting — and says nothing about levels or currency.

### 94.2 The bars, declared before the first row and checked against I7 first

Every bar below was run through the range/direction/unit/non-emptiness check *and* an
attainability simulation before it was committed, because seven prior declarations named a
quantity that could not do what it said and the check is what caught them:

- **W3 cadence discrimination** clears the **measured null for the same matcher on the same
  pairs** — the placebo pair and the whitespace sham, both riding every batch — never a nominal
  0.5. Both shams must hold or the batch is VOID and reports no rate.
- **W4 payoff landing** clears the agreement its own **mismatched control** achieves, not
  chance. A control that shares every nuisance property is the only comparison that means
  anything, and "agrees with the owner more often than a coin" would be cleared by an
  instrument that says *yes* to everything.
- **Part A's seating controls are equivalence tests, not point checks.** The placebo shelf and
  the two shams pass when the interval on allocation share lies **inside** a declared band, so
  insufficient evidence fails rather than passes — the direction a control has to fail in.
- The unit everywhere is the **cell**, never the comparison: §89 item 6's correction, where a
  30-decided floor could not bind because four personas were one judge four times.

### 94.3 The substrate finding, and it is the load-bearing result of this entry

The Budgeted Continuation Reader needs a shelf of two texts, each long enough that the budget
cannot exhaust it — at the registered shape, 3,600 words. Counted before anything was bought:

    corpora/toll.db                  10 scenes, 10,049 words   ONE own-generated book
    exports/book-snapshots.db         2 books,  ~950 words each — imported, not generated
    contracts golden fixtures         2 books,  ~800 words each — authored fixtures

**There is exactly one own-generated text in this repository long enough to be a shelf member.**
That is not a uniform shortage and pretending it were would be the more comfortable error. The
placebo, the positional-symmetry check, both shams, the dose-response battery, budget
invariance and cross-family agreement all compare a text against a **transform of itself** and
run today on the corpus in hand. The **variance floor needs twenty own-generated texts** and the
**transplant check needs a second own-generated book as donor**, and neither exists.

**So the two that cannot run are recorded as NOT RUN with a price, never omitted**, and the
sharper of the two decides the seating: the design calls transplant-blindness a **kill**, so a
model that has not been asked cannot be seated no matter how the other five legs read. A
battery reporting four of six passes with two absences unmarked would read as a seated model,
which is exactly the shape §89's no-silent-caps rail exists to refuse. Until roughly $81 of
frontier drafting buys the fitness books, every BCR number in this repository is a statement
about the instrument's own controls and about no book.

**The order this forces is the order the design already asked for**, which is the cross-check:
seat, then battery, then freeze and register, then arms. Nothing in the optimization half
starts before the kills have had their chance, and with two legs unrunnable the kills have not
had it.

### 94.4 What shipped, and the two features cost no model call between them

**W1 — the ledger learns its kinds** (migration 028). A `kind` on every promise, reported by
the summary invocation that already reports the promise, and **derived rather than declared**:
the set started as a five-way guess and `tone` is gone because two disjoint local families
reported it **zero times across 120 promises**. `mystery` (53% / 45%) and `plot` (39% / 41%)
dominate both distributions; `character` and `progression` are each kept by one family and cut
by the other, and the rule's own "per model, never pooled" clause settles that by keeping both,
because two models disagreeing at low rates is not evidence for either.

**W2 — the planner schedules payment** (migration 029). Open promises go into the outline call
that already holds the beat sheet and come back with payoff windows, validated the way
milestones are and stored as PROPOSED-grade columns on the promise row, rendered into the packet
by `describe_owed` as part of the debt line. Six validation rules, and only one of them is about
the reader: **a schedule may not close every window inside the final act.** That is
`_milestones`' anti-stasis rule in the promise dimension — and it abstains below two windows and
below three acts rather than firing on a book too short to have the structure it describes,
which is the I7 check seven prior declarations failed.

**Neither adds an invocation**, which is §15 applied twice, and neither can refuse anything:
windows mint no finding and `promise.overdue.v0` remains the entire evaluator side. A "missed
its window" sibling was considered and deliberately not built — a model-scheduled window missed
by a model-reported payoff is two model claims disagreeing, and neither is entitled to raise a
finding about the other.

### 94.5 Three studies, three refusals, and each one is cheaper than the thing it stopped

Nothing below is a headline. All three ran on local families over this system's own prose, and
all three stopped before the expensive half — which is the whole point of running them in this
order.

**W3 — cadence is not nameable, on the one family whose controls held.** The frozen matcher
names cadence on 3 of 30 cells against a measured null of 0 of 20 (Fisher p = 0.207) on
`qwen3:14b`; `gemma3:12b` is **VOID** because its byte-identical placebo drew *"an exact
duplicate of the first, differing only in the inclusion of a final status report at the end"* —
a confabulated difference on identical text. So no cadence detector is built and no candidate
axis is nominated.

**The interesting half is a diagnostic, and the second family is what stopped it becoming a
claim.** 22 of 30 of qwen's cadence responses assert that one passage "includes additional
details" the other "omits" — about passages certified to carry identical word multisets,
character counts and paragraph counts. That family detects the manipulation reliably and names
it as *deletion* rather than as *placement*, and the frozen matcher earns its keep by refusing
to read that as a hit. gemma's rate is 3 of 30, so displacement-read-as-deletion is a property
of one model rather than of E6 at 2,000 words — a single-family run would have supported the
wider sentence and it would have been wrong. One register entry falls out: the byte-identical
placebo **cannot** catch a displacement artifact, and a word-identical reordering control is
what would.

**W4 — the scorer does not transfer, which is a shorter sentence than the study expected.** Two
substrate absences were known before the first call: no owner-read set, and **no paid promise
anywhere to build a `paid` or `mismatched` arm from**. What ran was the false-positive half,
which came back 0 of 32 on unpaid pairs and 0 of 8 on the placebo — and that reads as clean
behaviour and is not. A constructed positive, added after the first run and labelled DIAGNOSTIC,
puts the ledger's *own sentence* in the paying passage; it fires on **6 of 32**. So the scoring
ceiling is 19%, a zero elsewhere is what a near-dead matcher produces, and the module withholds
every rate rather than printing one — `latent_crossfamily`'s rule, for its reason.

The cause is that `check_open_threads` was built to ask whether a summary of the *same prose*
mentions a recorded thread, and here it is asked whether a one-sentence **paraphrase** names the
same debt: *"The identity and origin of the crate's contents and sender are settled"* against a
ledger saying *"The crate's contents, its unfamiliar wax mark, and who sent it must be
revealed"* is a correct answer sharing almost no distinctive word. Reusing the shipped matcher
was the defensible choice and it was wrong; nothing was wired, and `promise.landing.v0` does not
exist.

### 94.6 The instrument's first six sessions killed two of four candidate readers, and the control that did it was not in the design

The Budgeted Continuation Reader ran its pilot on four local families — three shelves, both
orientations, twelve forced fetches — and the first thing it produced was not a measurement of
prose:

    qwen3:14b     ABABABABABAB in all six sessions      taking turns
    gemma3:12b    AAAAAAAAAAAA in all six sessions      never leaves slot A
    phi4:latest   all-in per session, slot varies       the one live candidate
    gpt-oss:20b   no answer at all                      broken install, NOT SCREENABLE

**Both fixed-pattern readers would have passed every declared control.** A strict alternator
spends exactly half its budget on each side of every shelf, so the placebo, both shams and the
positional check read perfectly clean while nothing measures anything — the 195/196 constant
function wearing a budget, which is precisely the failure V1 is declared to catch and which V1
cannot catch here for want of twenty own-generated texts. So **P5** was added: the standard
deviation of the *slot* share across a run must exceed a floor. It needs no substrate the corpus
lacks, it fires at six sessions, and it is not a bar tuned to an answer — the pre-registration
already names this kill; P5 is that kill in the form this corpus can reach.

**P5's first formulation was wrong and the next pilot caught it**, which is the second time in
this entry that running a check is what found its defect. It read the *target* share, and the
orientation swap moves the target between slots — so `gemma3:12b`'s answer-A-every-time reader
scores maximal target-share variance and the check would have reported the most rigidly
positional family available as the most discriminating one.

**One more declared number was wrong in the direction of false failure.** `--attainability`,
run before any seating, measured the equivalence control at the declared band: at 16 sessions an
**unbiased** reader clears it only 76.5% of the time. That is I7's catalogued failure — T0's own
registered bar disqualified a good judge 82 to 100% of the time — so the floor moved to 24,
where an unbiased reader clears 91% and a 0.60 allocator is refused 93.5% of the time.

**No model is seated and none can be on this corpus**, which is §94.3's finding arriving through
the statistics rather than through the shelf builder. What the six-session screen bought is the
right to spend a seating budget on one family instead of four.

### 94.7 The seating ran, every control failed, and the number that was wrong was ours

72 sessions on `phi4:latest`, 864 forced fetches, **every one answered** — and all four
equivalence controls FAIL:

    control            verdict  failure kind   point   interval
    p1_placebo          FAIL     imprecise     0.500   [0.354, 0.625]
    p3_whitespace       FAIL     imprecise     0.396   [0.271, 0.521]
    p4_rename           FAIL     imprecise     0.500   [0.354, 0.625]
    p2_positional       FAIL     imprecise     0.615   [0.396, 0.833]
    p5_non_degenerate   PASS

**Two of them sit on a point estimate of exactly 0.5 and fail anyway.** That is a bar wrong in
the direction of false failure — I7's catalogued defect, on our own bar, for the third time in
this entry after `CONTROL_MIN_SESSIONS` and P5's first formulation. A verdict of FAIL alone
reads as a statement about the reader, so the two kinds are now named apart: an interval that
still *contains* the centre while being wider than the band is `imprecise`, and only an
interval that has moved off the band is `off_centre`.

**The cause is that `--attainability` simulated a reader nobody is.** It draws each session's
share as twelve independent coins, per-session sd about 0.144. phi4's sessions produced shares
of exactly **0.0, 0.5 or 1.0 and nothing else** — the reader picks one of four fixed patterns
(all-A, all-B, ABAB…, BABA…) and holds it for a whole session, so the fetches within a session
are perfectly correlated, the effective sample size is the **session** count rather than the
fetch count, and the observed per-session sd is **0.4025**. The interval is 2.8x wider than the
table assumed and the declared band could not have been met at any batch this programme had
budgeted.

**So sizing moved from an assumed distribution to an observed one.**
`empirical_sessions_needed` resamples the run's own session shares, centred on 0.5 so it prices
*precision* rather than certifying a bias away: at this reader's variance the band needs **64
sessions per control arm**, not 24 — 2,304 fetches per arm, roughly seven hours of governed GPU
time across the three shelves. It is reported beside a failing seating as a **price and not a
verdict**, and deliberately as a sibling of the controls rather than one of them, so a
diagnostic cannot enter the seating decision through `all(... == "PASS")`.

**This is also why the D1 battery was not started.** Its arms would have been sized off the
same broken assumption, bought thousands of calls, and produced the same uninterpretable FAIL.
The design's order — seat, then battery — is what kept that from happening, and the seating is
the step that has now returned its answer: not a reading about prose, a correction to the
instrument's own arithmetic.

**What the run does not say.** Nothing here is evidence that phi4 is unbiased; the intervals are
too wide to speak about the centre at all, which is what `imprecise` means. And nothing here
faults the instrument's shape: the forced budget worked, every session answered, no transport
failed, and P5 held. What failed was a declared number, caught by the first run declared
against it.

## 95. The programme stops asking, and everything it measured before a force had a number was its own instrument

The force directive (2026-08-19), the first issued under the **scope axiom**: *no solicited human
judgment, ever* — not hired, not operator, not one blinded pair. Its instruction was to stop
asking the model questions and start measuring what the text does to it. The design is
[plan/force-program.md](force-program.md); this entry carries the scope amendment, the bars, and
the corrections that arrived before any force had a number.

**There is no exact count in this sentence, and that is the finding.** Every attempt to write one
was out of date within the hour: the tally went ten, twelve, fourteen, and was still climbing when
this paragraph was rewritten to stop claiming a number it kept having to revise. What can be said
precisely is the *shape* of them. Two are in the harness's own arithmetic; three in the inference
layer; two in F1's declared statistic; four in the transport; two in this programme's own
selection code; one is a confound the corpus has carried since §79; and two are in the thermal
governor this repository believed it already had — including one where the *diagnosis* was wrong
and had to be withdrawn after it killed two healthy runs.

**That ratio is the entry.** A programme that spent its first day finding defect after defect in
its own instrument and none in the world is not a programme that failed to start; it is §89's
rulebook working at the only time it is cheap. Most of them returned a number rather than raising,
which is the class this repository keeps building rails for. Three are worth naming for their
shape rather than their content: one was caught by a thirteen-seed smoke run for about twenty
cents instead of by the fifty-two-dollar arm behind it; one was a problem `elicit.py` had already
solved on line 931, so the fix was in the repository, in the sibling module, and simply not
copied; and one — the `aligned`-first pairing that left F3's second stratum with a single pair —
would have produced a clean-looking result that meant nothing at all.

**Nothing above this entry was renumbered.** §92 and §93 were taken by parallel sessions while
§94 was being written; §95 was free when this began and the check was run again before it was
written.

### 95.1 Track 0: PREFERENCE is retired by choice, and FORECAST is promoted exactly as §86 wrote it

**This subsection is a decision, not a measurement, which is why it is first.** A scope that
arrives after the numbers is not a scope.

§82 refused §72's judge-path licence **on evidence class**: `domain/calibration.py` constitutes
`PREFERENCE` as *"a human's blinded, position-swapped choice between two texts"*, so — §82's
words — **no quantity of machine elicitation can produce a PREFERENCE-class row**. That left the
class *unearned* and not *unearnable*: the door stayed open and §80's paid batch was the key
beside it. Under the scope axiom the key is destroyed. There will be no paid batch, no operator
read and no blinded pair, so no PREFERENCE-class row will ever exist here.

So the class is **retired rather than refuted**. Nothing measured it away and nothing could —
§86's own falsifier paragraph says *"No experiment refutes a definition."* What changed is what
this project will do, and that belongs in the ledger, where a future session reading only the
code cannot drift back into it. Three consequences, stated so silence cannot re-litigate them:
`plan_search`'s judge path is shut permanently rather than currently; **Track B
([reader-batch-1.md](reader-batch-1.md)) is buried with its budget**, and its money is not
reallocated to a smaller version of itself because a smaller paid reader batch is still a paid
reader batch; and the §85 operator read is retired **UNREAD** — `results/operator-read-key.json`
is **SEALED** on disk (operator §7.2), so the commitment lives in this ledger rather than in a
deletion. Every told-versus-shown reading in §85, §87 and §89 that was marked provisional pending
that read is now **permanently provisional**, which is the honest status rather than a defect.

**`FORECAST` at `STORY` grain is promoted from pre-declared to active, and the promotion is
checkable against the text that pre-declared it.** §86 wrote the amendment down before the
numbers precisely so this could not be a new invention: *a `FORECAST` class at `STORY` grain,
absent from `veto_for` so it refuses nothing with zero code, and **not** accepted by
`plan_search`'s judge path — so that the class cannot be shopped for later.* It is promoted at
that grain, absent from `veto_for`, not accepted by the judge path, and it therefore licenses
nothing. It is a class an instrument may be *classified into*, never a door.

The promotion is not licensed by T2 performing; T2 never ran and §86.3 recorded its premise as
self-contradicting. **The branch condition changed.** The class was written as the amendment that
would be proposed if a machine-only instrument were the one on the table, and under the scope
axiom a machine-only instrument is the only thing that ever will be. A class that can never be
reached is a dead letter rather than a safeguard, and §84's freeze rule is satisfied by the
promotion matching the frozen text, not by the text never being used.

§82 is untouched. `veto_for` gains no member, `plan_search` gains no accepted class, `AXIS_MATCHERS`
and `E6_QUESTION` are not reopened, JudgeBench A2's verdict layer is still empty, and the verdict
channel stays dead **as measured** — §89.4's 4,676x positional-to-text ratio. No arm here routes
through it.

### 95.2 The harness, and the floor that had to be computed rather than chosen

`force_harness.py` holds the standard, so no track can re-decide it. It reproduces §89.2's
published attainability table or it is wrong — 85 of 144, 81 of 137, 43 of 68, 44 of 69, the
interval binding at every n — and its selftest asserts exactly that before any GPU is touched.

**Two rules were declared numerically before the first force ran, and both are computed rather
than picked.**

`INSUFFICIENT_N` is available only to a stratum whose *interval* bar demands more than **0.6000**.
At this programme's n that admits `crossed-tight` (0.6324), `crossed-loose` (0.6377), F3 (0.7500)
and FX's pilot (1.0000), and admits **neither** `aligned` (0.5903) **nor** `crossed` (0.5912) —
the two strata that decide whether a force passes. On those two, FAIL is FAIL.

`DEGRADED_STRATUM` is new and it exists because of a rail that did not previously reach far
enough. `pair_agreement` skips a pair it has no score for, so a stratum that lost half its pairs
to a drop would have reported a clean decided share over the survivors. Drops are now counted
against the stratum's original size, and a **binding** stratum whose decided count falls below
**MIN_REFUTING_N = 110** returns `DEGRADED_STRATUM` rather than a FAIL nobody could have avoided.
110 is derived in the selftest — the smallest n that is both attainable and demands 0.6000 or
less — and the first derivation of it was wrong in the instructive direction: omitting the
`attainable` guard returned **5**, an n at which no k clears the interval at all and the stratum
is worse than excusable rather than better. That is the seventh entry in §89's rulebook and it
was caught by a check rather than by a reader.

`combine_families` needed two corrections, and both are in the direction of claiming more than
the evidence allows. It folded `DEGRADED_STRATUM` into `FAIL` — precisely the
folding-a-refusal-into-a-verdict §1.5 forbids, in the function whose whole job is to combine
refusals — and, worse, **it did not enforce the two-family minimum it exists for**. With a single
family in the dict, `all(status == "PASS")` is trivially true, so a single-lineage arm that
cleared both strata would have reported `PASS`: the exact claim §94.5 says cannot be made, from
the exact function written to prevent it. Found while reasoning about what F1 would report on
Haiku alone, before the arm returned. A run with fewer than two families now reads
`NOT_SCREENABLE` whatever its strata did.

### 95.3 What this box actually is, measured before anything was assumed

Four measurements, all of them cheap, all of them made before a force ran, and every one changed
something.

**Replay is bit-exact, so the placebo keeps its arithmetic-check role.** `placebo_identical` is
not a null in this programme — §89.4 made it an arithmetic check — and its exactness is bought by
construction: every stochastic step seeds its RNG from the **digest of the text it acts on**, so
byte-identical sides produce byte-identical outputs. Whether the hardware honours that is a
question about bf16 reduction order and not about intentions, so `determinism_probe.py` ran
first. On both pinned families, forward-pass replay and batched sampled continuations are
**bit-exact**: placebo tolerance `0.0`. Had it read NOISY the placebo would have been downgraded
to an equivalence test against the measured scale, with the weakening recorded as a property of
the box — the branch was written before the probe, which is the point of writing it before.

**What a zero placebo is and is not evidence of, corrected after review.** An earlier draft said
"every placebo in every arm below has read exactly `0.000000`" as though that were the arithmetic
being checked. On a deterministic transport with text-digest seeding, byte-identical sides
*cannot* produce anything else — the zero is a property of the construction, not a measurement of
it. It still catches a real class of failure (a pipeline that separates a string from itself), and
it certifies nothing about the force. Where the construction supplies the zero by deduplication
instead, it does not even do that: see §95.11's vacuous remote placebo.

**Batching is 8.7x, and it is the difference between F1 existing and not.** Eight 512-token
continuations from a 1,310-token prompt: **44s** as one batch against **384s** looped. The
replicates are batched and the batch composition is a pure function of the text — always exactly
K continuations of one prompt — so the determinism the placebo needs survives.

**Full-sequence logits do not fit, and the check was made before the out-of-memory.** Gemma-3's
vocabulary is **262,208** tokens, so materialising logits for F2's 9.7k-token condition is about
8 GB in float32 on a card already holding the model, and F3's ladder is longer again.
`surprisal.py` gets away with it because its sequences are 1,152 tokens. `logits_to_keep` fixes
it, both pinned architectures accept it, and the fixed path was verified **bit-identical** to the
full-logits reference before it was used.

**The two families are not the same instrument on the long-context arms, and that is
pre-registered rather than discovered later.** Read from the configs: `gemma-3-4b` interleaves
five sliding-attention layers (window **1,024**) to every one full-attention layer and has
131,072 positions; `Qwen2.5-3B` is fully global with **32,768**. So at F2's D=8k and at every
rung of F3's ladder, gemma routes long-range information through one layer in six while Qwen
routes it through all of them. **A `SPLIT_FAMILY` on those arms may be architectural rather than
about prose**, and that reading is recorded in `force_gpu.ATTENTION_SHAPE` and printed in every
result — before the first pass, so it cannot be reached for afterwards.

Qwen's 32,768 is also what set F3's shape. Ten chapters at j=9 runs the true-context prefix past
the ceiling, and the obvious repair — truncating the prefix from the left — is the worst option
available: a truncated top rung beside an untruncated bottom one puts a **level artifact back
into the slope**, and subtracting that artifact is the only reason F3 is a slope rather than the
CDG §58 killed. So the ladder is shortened for every fiction and every family alike, and a
fiction whose top rung still does not fit is **dropped and counted**.

### 95.4 The corpus carried an unmatched length confound, and §79 could not have seen it

Measured on the real 281 pairs while wiring F1's seeds: `taste_benchmark` matches pairs on the
**source chapter's** word count at `MAX_LOG_WORD_GAP = 0.10`, and the 1,000-word **excerpt** it
actually hands a judge was never matched at all.

    |log10 excerpt word ratio|     max 0.4549  (one side 2.85x the other)
                                   23 of 281 pairs above 0.04

Nothing in §79, §87.2 or §89.2 is wrong because of it — those arms read whole excerpts and a
readout over rates is not obviously length-driven — but a *generative* force is. A fixed prompt
ceiling truncates the longer side and not the shorter one, and a force that read seed length
would have scored on the asymmetry with nothing about prose in it. So both sides of every pair
are now cut to the **same** token count, `min(high, low, 1400)`, and the pre-cut ratio travels
with the result as a printed covariate rather than an invisible one. The lesson is §89.2's
author-disjointness lesson in a second costume: a property the selection matched at one grain is
not matched at the grain the experiment actually reads.

### 95.5 F1's pilot corrected F1 twice, on criteria it had declared in advance

The design gave the pilot one job — buy the throughput, the censoring rate and the tie rate, with
its own agreement explicitly **not a result** — and the pilot spent it on finding that the
declared statistic was degenerate as specified.

**The anchor was wrong.** F1 measures when a continuation stops being nearer its seed's register
than the *model's median centroid*, and the design defined that centroid from continuations of
the own-generated neutral pool, reasoning that a centroid computed from the corpus would make
each side its own baseline. Measured: **censoring rate 0.979** — almost no trajectory ever
crossed, because own-generated LitRPG with `[STATUS]` blocks is not a neutral centre, it is its
own register, and every RoyalRoad continuation sits far from it at every window. Recomputed on
the identical cached generations with the anchor as the centroid of **every** continuation window
in the run: **0.250**. The corrected anchor is one global constant shared by both sides of every
pair, so it cannot manufacture a high/low difference; it is a nuisance anchor, not a fitted one.

**The reduction was wrong.** The crossover index is a small integer, so a median over eight
replicates takes few distinct values and pairs tie constantly — which the harness would correctly
have reported as `INERT_GENERATOR`, a true statement about a statistic nobody should have
declared. The mean over K takes eighths and clears the declared 0.90 decided-share floor.

Both criteria — censoring rate and tie rate — are **label-blind**: neither looks at `conversion`,
and the pilot's agreement was discarded. This is §94.6 twice in one run, where P5's first
formulation read the wrong share and the next pilot caught it. The corrections are recorded in
the module as `PILOT_CORRECTIONS` and printed in every F1 result file, so no future reader has to
take this paragraph's word for it.

### 95.6 The box went down, the governor had never fired, and the first diagnosis was wrong too

Mid-run on 2026-08-20, during F1's pilot, this machine hard-shut-down for the third recorded time.
The run was at `--rest-ratio 0.25` — an **80% duty cycle** — lowered from `cdg_battery`'s 3.0 on
the reasoning RUNBOOK states: the temperature governor is the actual protection, and the rest
ratio is only a coarse pre-emptive measure.

**The governor's hold had never fired, in this session or in the two shutdowns before it.** Every
core-temperature sample logged sat between 47 and 65 °C against a 72 °C pause threshold. So the
protection this repository believed it had was not running, and the rest ratio was doing all of
the work — which is the one clear conclusion this subsection is entitled to.

**The second conclusion was reached, written down, and then refuted by more of the same
measurement, which is why it is recorded here rather than quietly dropped.** `nvidia-smi` exposes
`temperature.gpu.tlimit`, degrees of margin remaining, and a first trace made it look like the
sensor the core governor had been missing:

    t =  60 s   core 56 C   margin 20 C   power  278 W
    t =  70 s   core 54 C   margin 12 C   power  164 W      core FELL, margin fell 8 C

Read alone, that says `tlimit` tracks something hotter than the core — a hotspot — and explains
three shutdowns whose core traces looked comfortable. A watchdog was built to kill on it, the
governor was rewired to hold on it, and **both promptly killed healthy runs**. A longer trace says
why:

    t = 201 s   core 58 C   margin 19 C   power  296 W
    t = 211 s   core 53 C   margin  6 C   power   93 W

The margin fell 13 °C while the core fell 5 °C **and the draw fell by 200 W**. Nothing thermal
moves that way. The same shape appeared at t = 50 s and recovered to 21 °C on the very next
sample. So these are **transient dips in a sensor whose semantics this entry does not know**, and
gating on a single one is a false positive that ends a run that was never in danger.

**What the box is entitled to claim, after two wrong readings of it, is narrower than either
draft:** core temperature and power draw are interpretable and were never near a limit;
`tlimit` is not interpretable from here; and the shutdowns remain **undiagnosed**. A whole-system
power-off with a cool core is at least as consistent with supply transients on a 382.5 W card as
with any die temperature, and this session owns no measurement of the supply. `nvidia-smi -pl 260`
returns *Insufficient Permissions* from a normal shell, so the one intervention that would settle
it is an operator action and remains **unapplied**.

The protections that survive all three readings are the ones that do not depend on knowing which
sensor is right: rest ratio back to **3.0** (25% duty); a core pause that was retuned twice more
before it worked and ended at **64 / 56 °C** (§95.12 records why 58 / 52 was unworkable — an
earlier draft of this paragraph claimed 62 / 55, which was never what the code held); a **soak
break** of 90 s every **25** calls, because per-call rest cools the die and does nothing about
heat soaked into a closed case over hours; an **independent watchdog** sampling every 10 s,
because an in-process governor cannot act *during* a call and a batched 512-token generation is
forty seconds of uninterruptible work; and — the correction the two false kills bought — **any
trip on `tlimit` must persist across consecutive samples before it stops anything**, while the
core and the card's own throttle flag are still trusted on one reading.

**The forty-GPU-hour cap turned out to be a duty-cycle cap, and that is what scoped this
programme — no result did.** At a 25% duty cycle forty hours of wall clock is roughly ten hours of
computation. The consequences are arithmetic and are recorded as prices rather than as omissions:

    track   at the declared shape          measured price       disposition
    F1      630 seeds x K=8, two families  ~18.6 h per family   left the machine entirely;
                                           ~37 h both           ran on Haiku instead (§95.10)
    F2      281 pairs, 12 passes each,     ~8.4 h per family    ladder amended, then run
            D to 8k, two families                               (§95.7)
    F3      191 pairs, 4-rung ladder,      6,112 passes and     NOT RUN, priced by survey
            8 chapters                     ~27.2 h per family   rather than by estimate
    FX      8 pairs, 6 hops, 4 chains      ~4 h GPU, or ~$8     NOT RUN; two priced routes
                                           on the remote route

**Every one of those prices is measured rather than estimated**, which is the one improvement
this session can claim over §94.3's accounting: that entry priced its two unrunnable legs from a
shelf count, and this one priced them from a stopwatch and a survey. F1's is the interesting
case — the price was what sent it off the machine altogether, and §95.10 records where it went
and what that cost in things other than hours.

### 95.7 The ladder F2 had to give up, and a saving that was overstated

**The distance ladder was amended before F2 ran at any n, on a criterion that never touches the
label.** Forward-pass cost is roughly linear in context length, and the 8,192-token rung looked
like the bulk of F2's bill; at the hardened duty cycle the declared ladder priced the arm at ~8.4
GPU-hours per family and appeared to put the **two-family minimum out of reach**. A single-family
force claims nothing by construction (§94.5's rule), so the choice looked like one between a
shorter ladder on two families and a longer one on a family whose reading would be inadmissible.
The ladder went from (512, 2048, 8192) to **(512, 1536, 4608)** — a factor of three per rung, log
spacing still exact.

**The saving was overstated and is corrected here: about 26%, not 45%.** Total context across the
three rungs falls from 15,852 tokens to 11,756, a ratio of 0.742, because every pass also carries
a ~1,400-token passage and a ~300-token probe that the amendment does not touch — the original
figure divided only the distractor lengths. So **the two-family argument rested on a number wrong
in the direction that favoured the decision**, and a 26% saving would not have bought two families
on its own. What actually decided F2's shape was a parallel session taking the card (§95.12).

**What that gives up is stated rather than buried: the longest distance is now 4,608 tokens, so a
force that would only separate beyond 4.6k is one this run cannot see.** That is a narrower claim
than the design asked for, and it is the claim the run is entitled to.

**This subsection was written under the title "F2 ran" before F2 had produced anything**, and the
two controls it reported as holding were the *smoke run's*, on three pairs, presented in a
paragraph about the full arm. The seed cap and the zero-drop claim were also the smoke's. F2's
real numbers are in §95.12 and §95.14; what belongs here is the amendment and nothing else.

**One defect in F2's controls is recorded rather than repaired mid-run.** The control subsamples
were taken as `live[:n]`, and `load_pairs` returns `aligned` and then `crossed` — so F2's sham and
placebo are drawn **entirely from `aligned`**. A sham that only ever sees one stratum certifies
that a force ignores formatting on half the corpus and says nothing about the half §79 built to
be adversarial. `force_harness.stratified_subsample` fixes it with an even stride and no draw, and
F1 uses it; F2's run was already hours in when it was found, and restarting to re-shuffle a
control would have cost more than the control is worth on a force whose primary strata are
unaffected. **F2's sham therefore covers `aligned` only, and that is a caveat on F2's sham rather
than on F2's reading.**

### 95.8 The market's dry run, and the line in it that turned out to be an identity

FM is gated — a force must clear §1.2's bars before a bet is funded — so what ran is the
mechanism against forecasters whose behaviour was known in advance, at zero GPU and zero quota.
A coin stays flat, an oracle grows, an anti-oracle goes bankrupt and stops betting, an abstainer
never bets, and the log score is clipped at 0.02 so one confident error cannot decide a market.

**The fifth competitor is worth printing and is NOT a demonstration**, which an earlier draft of
this subsection got wrong. A prose-blind rule that bets on whichever side has more followers
scores, on the held-out half:

    stratum    bets   mean log score   bankroll
    aligned      74         -0.2877     448.27
    crossed      72         -1.3863       8.25

The draft called that "§79's two-stratum design working exactly as designed… a demonstration
rather than an argument." It is neither: it is an **identity**. §79 *constructs* `aligned` so the
high-conversion side carries more followers in 144 of 144 pairs and `crossed` so it carries fewer,
so a follower rule is right by definition in one stratum and wrong by definition in the other.
The market recovered the corpus's own construction and nothing else, and a number that could not
have come out otherwise is not evidence.

What the run does establish is narrower and still worth having: the **mechanism** behaves as
declared — a coin stays flat, an oracle grows, an anti-oracle goes bankrupt and stops betting, an
abstainer never bets, and the log score is clipped so one confident error cannot decide a market.
The sentence that survives is about the arithmetic, not about taste: **a market run on one
stratum would promote a popularity proxy**, which follows from §79's construction rather than
from this run.

The survivor of a funded market would be a `FORECAST`-class **candidate** and nothing more, and
§6.2's battery — a forecast analog of §86.7's axioms, plus §86's T3 exploitation budget
instrumented from the first optimization step — stands between it and any seat.

### 95.9 What was not run, and what it would cost

- **F1 at full n**, ~18.6 GPU-hours per family and ~37 h for the two, measured rather than
  estimated. Its pilot corrected its anchor and its reduction (§95.5), so the instrument is ready
  and the substrate is affordability. A power cap applied from an Administrator shell would
  change this arithmetic more than any code change available here.
- **F3**, and the survey **was** walked, which turned a guess into three numbers and found a
  defect in this programme's own pairing code. The cached shards hold **585 fictions** with eight
  or more chapters at the pre-LLM cohort and the 10,000-view floor — far more than the directive's
  40-fiction cap assumed. Pairing them yielded **196 aligned and 1 crossed**, and the second
  stratum being empty is not a fact about RoyalRoad: both strata drew from one pool under a
  shared work/author disjointness set and `aligned` was built **first**, so it consumed 392 of
  the 585 fictions before `crossed` — which needs the high-conversion side to carry *fewer* views
  and *fewer* followers — could look. Building the scarcer stratum first gives **118 aligned and
  73 crossed**. Had this run as written, a force could have cleared `aligned` by proxying
  popularity with nothing to contradict it, which is the exact failure §79's second stratum
  exists to prevent, and the survey is the only reason it was visible before a GPU-hour was
  spent.

  Two consequences, both recorded rather than resolved. **F3 cannot deliver a meaningful FAIL at
  this substrate**: `aligned` demands 0.6017 and `crossed` 0.6301, both above the 0.6000 ceiling
  §1.2 declared for `INSUFFICIENT_N`, so the arm can pass or abstain and not refute. And the full
  191-pair shape prices at **27.2 GPU-hours per family** — 6,112 forward passes each, at the duty
  cycle §95.6 fixed after the shutdown — so it is `NOT_RUN` for the same reason F1 was, with the
  numbers now measured rather than assumed. `results/force-f3-survey.json` carries all of it. Its
  **own-generated arm stays `NOT_RUN`** regardless until §7.1's fitness books exist — §94.3
  counted exactly one own-generated text long enough to carry a slope.
- **FX's pilot**, ~4 GPU-hours, module built and selftested. At n=8 the interval demands 8 of 8,
  so it was never going to clear a bar; it is a kill screen, and it has not been run.
- **The fitness books, funded at §7.1 and DELIVERED.** Twenty own-generated books, **20 of 20
  clearing the 3,600-word shelf shape**, 3,918 to 4,059 words each, for **$26.69 of the $81
  authorised** — a third of the estimate, because §94.3 priced from a per-scene figure that
  included a book's planning overhead twice. This closes the substrate absence §94.3 called the
  load-bearing result of its entry: *"until roughly $81 of frontier drafting buys the fitness
  books, every BCR number in this repository is a statement about the instrument's own controls
  and about no book."* The BCR's variance floor wanted twenty own-generated texts and had one;
  it now has twenty. Its transplant check wanted a second book as donor; it now has nineteen.
  Neither is run here — this entry bought the substrate, and the seating is the next session's.

  Four driver defects were found on the way, and all four were the driver's rather than the
  pipeline's: an arc needs at least six scenes (`domain/beats.py` refuses five); `--no-library` is
  a top-level flag rather than one of `tick`'s, so three argparse errors had been counted as
  ticks; the stop condition tested for outcome strings the conductor never emits, so a finished
  book would have spun its whole tick budget; and a per-book cost cap cannot bound a shelf, so
  spend is now read from each book's own `policy_decisions` rows against a cumulative ceiling.
  The fifth is the one worth keeping: **the first slot reported `0 words` after 36 ticks and
  $2.79**, which reads exactly like a drafter that produced nothing. It was not. Two earlier
  failed attempts had each left a book behind, and `export` refuses once a store holds more than
  one — so the count failed while the prose sat there. That slot holds **two** complete books,
  4,047 and 4,028 words. A plausible zero standing in for a fact it was not measuring, one more
  time.
- **E4/E5**, admitted by operator §7.6 as FM baselines and **not bought**, because the gate they
  compete inside has not opened. Building them early would be the elicitation §8 prohibits, built
  early.
- **No licence moved. No bar was re-declared after numbers arrived. The §85 operator read was not
  opened**, and under §95.1 it never will be.

### 95.10 F1 leaves the machine, and the transport charges three things that are not money

**Operator amendment, 2026-08-20, mid-session.** §95.6 priced F1 at ~37 GPU-hours for two
families and recorded it `NOT_RUN`. The operator asked the obvious question — *why not Haiku?* —
and the answer splits the programme cleanly along a line nobody had drawn:

**F1 needs only sampling. F2 and F3 need token logprobs, and the Messages API exposes none.**
There is no `logprobs` parameter on `/v1/messages` in any form, so the two arms built on
teacher-forced scoring cannot leave this box at any price. F1 can, and FX could.

**The transport was priced by running it rather than by estimating it.** `claude -p` prepends
Claude Code's own system prompt — **26,357 tokens** — to every call, which dwarfs a 900-word
seed. It caches, and F1's shape is unusually kind to that, because the K replicates of one seed
are the same prompt byte for byte:

    new seed, cold prefix     $0.0210      (5,677 written, 20,807 read)
    same seed, warm prefix    $0.0089      (0 written, 26,357 read)
    one seed at K=8           $0.0833
    full arm, 630 seeds      ~$52

That is a fact about the *transport*, not about Haiku: a direct SDK call carrying only the system
prompt and the seed prices the same arm near $5, and near $2.50 through the Batch API. This box
has no `anthropic` package, no `ANTHROPIC_API_KEY` and no `ant`, so the cheap path was not
available and the operator raised §7.5's cap from $15 to **~$55** to buy the expensive one. The
figures are equivalent subscription quota rather than billed dollars, which is `providers/cli.py`'s
position and §85's convention. `force_remote.Ledger` **stops the run at the ceiling** instead of
discovering an overrun afterwards, and the run's own economics — spend, calls, cache reads and
writes, thinking tokens — print in the result file.

**The transport charges three things that are not money, and all three are declared here rather
than found in a result.**

1. **Determinism is gone.** No seed parameter and no guarantee, so `text_seed` cannot buy
   byte-identical replay and `placebo_identical` **cannot** be §89.4's exact arithmetic check. It
   is read the way a sham is read: identical sides must produce an agreement whose interval
   contains 0.50. That is §1.7's pre-registered branch, so the design survives — and it is
   strictly weaker, because an equivalence test is also passed by an instrument too noisy to show
   anything, which the exact check could never be.
2. **Instruct, not base.** §95's local families are pretrained checkpoints on purpose:
   `surprisal.py` argues that instruction tuning reshapes the very distribution F1 measures. Haiku
   is heavily post-trained and cannot be prompted into raw continuation, so the seed enters under
   a frozen continuation instruction. **The axiom holds** — nothing is asked about quality, no
   slot is offered, and valence still comes from measuring generated text rather than from
   anything the model says about it — but the instrument is a *prompted* continuation field and a
   reading from it is not interchangeable with one from family A or B.
3. **Unpinned.** `claude-haiku-4-5` is an alias. Every local family carries a 40-character commit
   sha; this one cannot, so a re-run later may not be measuring the same weights. `UNPINNED`
   prints in the provenance block of every result that uses it.

**And one correctness fix the transport forced, which the local path never needed.** Locally
`max_new_tokens` makes every trajectory the same length by construction; here the model stops when
it stops, and the first three probe calls returned 300, 815 and 1,040 output tokens. F1's
statistic is a **window index**, so a side whose continuations run longer has more windows to
cross in and a different censoring rate — a length confound sitting directly on the outcome. Every
continuation is now cut to 280 words, one shorter than 180 words is dropped and counted, and both
constants are in the cache key so a normalised row can never be replayed beside an un-normalised
one.

**A second transport defect was biased rather than random, which is why it gets its own
paragraph.** `subprocess.run(..., text=True)` decodes with the Windows console codepage, and
Claude's prose is full of characters cp1252 cannot represent — a single curly apostrophe raises
`UnicodeDecodeError` inside subprocess's reader thread. `UnicodeDecodeError` is a `ValueError`,
so the transport's own retry path caught it and counted the call as a transport failure. The loss
that produces is **not random**: it falls on exactly those seeds whose continuations happen to
contain a smart quote, which on this corpus is most of the literary ones. Measured after the fix,
no cached row had actually lost a replicate — the retries had absorbed every instance — so the
bias stayed potential rather than realised, and the honest reading is that the run was lucky and
not that the bug was harmless. `elicit.py:931` already passed `encoding="utf-8",
errors="replace"`; the sibling module had solved it and this one did not copy it.

**The most expensive defect in this entry was not in any force. It was `pkill`.**

`pkill -f register_halflife` matches nothing on this box, and it exits 0 while matching nothing.
So two "relaunches" of F1 — one to raise the worker count, one to apply the utf-8 fix — did not
replace the running arm, they **added** to it. Three copies of F1 ran against one cache for
sixteen minutes before the third crash report made the pattern visible, and the damage is
measurable from the cache itself rather than estimated:

    248 completed seed-runs        140 distinct seeds
    108 duplicate computations     35 seeds bought once, 102 twice, 3 three times
    1 corrupt line                 three appenders, and `Checkpoint`'s lock is per-process

That is roughly **$9 of paid work bought twice**, inside a total of about $20.70 spent before the
duplicates were stopped — and it was found by a *cost* audit rather than a correctness one,
because every individual number the run produced was fine. A cache with 108 duplicate keys and
one interleaved line is not a wrong measurement; it is the same measurement paid for repeatedly.

Three repairs, and only the first is about this bug:

1. **`force_remote.SingleRun`**, a PID lock file, so *relaunch* means replace. A stale lock whose
   holder is gone is taken over rather than honoured — a crashed run must not block the next one
   — and a live holder is named in the refusal. Verified by launching a second arm and reading
   the refusal.
2. **The spend ceiling now degrades instead of discarding.** It used to abandon the run and
   return `NOT_RUN`, throwing away a corpus that had already been paid for. A closed ledger now
   yields no continuations for that seed, the pair is dropped and *counted*, and the arm reports
   over what it could afford — with the shortfall visible as `dropped_before_scoring`, and a
   binding stratum that falls under `MIN_REFUTING_N` reading `DEGRADED_STRATUM` rather than a
   `FAIL` it did not earn.
3. **The generation order was wrong, and working out why is the third repair.** Seeds were
   generated pool first, then the live pairs, then the controls — which looked protective, since
   a ceiling that binds would take the sham and leave the strata the bar rests on intact. Priced
   against the actual remaining budget, that ordering guaranteed the sham would receive **no
   seeds at all**; and under the rule added the same hour, an arm whose sham is unscreenable
   reports `NOT_SCREENABLE` whatever its strata say. The protective-looking order therefore
   guaranteed a null. **The controls are now generated first**, so a shortfall trims *n* — which
   `DEGRADED_STRATUM` already handles — and leaves a certified reading over whatever the budget
   reached. The placebo costs nothing either way: its sides are the high sides, so it dedups to
   nothing.

   The rule it depends on is worth stating on its own, because it is a change to §1.3. A control
   that could not be read is **not** a detail a clean stratum can outvote: a force that has not
   been shown to ignore formatting has not been shown to be reading prose.
   `force_harness.arm_status` is the single place that decides it, and a *moved* control still
   outranks an *unscreened* one — disqualification beats "we could not tell".

The arm was relaunched with a ceiling of **$34** — the ~$55 the operator authorised, less the
$20.70 the race consumed — so the duplication is paid for out of F1's own budget rather than out
of a number nobody agreed to.

**And the smoke run earned its keep on the first attempt.** Thirteen seeds in, it died on a
`KeyError: 'log10_token_ratio'`: the two transports cap seeds in different units — tokens locally
because a tokenizer is there, words remotely because none is — and the summary block read the
local key unconditionally. Nothing about that is subtle, and nothing about it would have surfaced
before the arm had run for hours. It cost about twenty cents to find. That is the whole argument
for a smoke run that goes through the real plumbing rather than a dry run that mocks it.

**What a Haiku-only F1 is entitled to say is nothing on its own.** One lineage does not meet the
two-family minimum, so it reads `NOT_SCREENABLE` until a second family runs — §94.6's shape, where
a cheap screen bought the right to spend a seating budget on one family instead of four.
### 95.11 F1 returned, and what it returned is a reading about the instrument again

The arm completed on Haiku at its spend ceiling: **531 distinct seeds of 630**, and on the final
leg **1,975 calls for `$22.12`** at `$0.0112` a call — that leg metered by `force_remote.Ledger`.
The two earlier legs were **not metered**: their ledgers died with their processes, so the
often-repeated "about $55-58 across all three legs" is one measured number plus two reconstructed
from a per-seed rate and a duplicate count. The honest form is **$22.12 measured, ~$33-36
reconstructed, ~$55-58 total**, and only the first of those three is a fact. Two numbers in it are worth having
and one is a defect.

**RETRACTED: the sham certified nothing, and the sentence that stood here was the worst error in
this entry.** It read: *"The sham is clean, and it is the first thing this programme has
certified… F1 does not read layout… this is the control that would have caught §78."* The numbers
were real — 0.4889 on 45 decided of 60, interval [0.337, 0.6423] — and they measured **sampling
noise on identical inputs**.

`windows()` joins words with a single space, so no window ever contains a newline; and
`ablate.rewhitespace` changes newlines and intra-line spacing and **nothing else**. Measured on
100 real sham pairs after the review named it: **100 of 100 produce byte-identical feature rows.**
The perturbation never reached anything F1's feature space can see. A control that cannot move
the statistic is not a control that passed — it is the placebo defect of §95.11 a second time, in
the arm's other control, found by an adversarial review rather than by me, and celebrated in this
entry as the programme's first certification before anyone checked whether it could fail.

Two consequences fall out of the same fact and are recorded rather than tidied: F1's space is
**22 features, not 23** — `paragraph_len_mean` is a constant 100.0 in all 62,646 windows, because
every window is exactly 100 words — and **a whitespace sham cannot be F1's formatting control at
all**. F1's `rewhitespace_sham` now reports `NOT_SCREENABLE` with the measurement attached, so
both of F1's controls are unscreenable and the arm certifies nothing whatsoever.

**Every stratum was re-scored from the same 531 cached seeds under the corrected arithmetic, at
no cost, and F1 publishes no refutation at all.** The generation is what was paid for; every
correction the review forced is in the *scoring*, so the same seeds re-read give corrected
numbers for free. `results/force-f1-haiku-corrected.json` is the file of record.

    stratum          published (wrong)                    corrected
    aligned          FAIL  0.5429  140 dec,  0 ties       INERT_GENERATOR  124 dec, 16 ties
    crossed          DEGRADED_STRATUM  65 dec,  0 ties    DEGRADED_STRATUM  61 dec,  4 ties
    crossed tight    FAIL  0.3929   28 dec,  0 ties       DEGRADED_STRATUM  25 dec,  3 ties
    crossed loose    FAIL  0.4054   37 dec,  0 ties       DEGRADED_STRATUM  36 dec,  1 tie

**Three FAILs became refusals and none of them survived contact with its own rails.** `aligned`'s
was manufactured by the tie-breaking; the two halves' were emitted only because they had been
exempted from the refuting floor. The censoring rate barely moved (0.0301 → 0.0298) and the
anchor shifted 0.036 z-units once the control sides were removed from it, so the corrections
were about *what the numbers were allowed to mean*, not about the measurement.

**So the honest F1 sentence is that it refuses, and refuses in every stratum.** Not "the
generation field does not bend" — F1 has not been in a position to say anything about the
generation field. One lineage, an instruct head where §1.4 pins base checkpoints, a prompted
continuation rather than a raw one, an unpinned revision, **both** controls vacuous, a statistic
sitting at its floor for 68% of continuations, and a `crossed` stratum truncated in corpus order
by a spend ceiling. `combine_families` reads `NOT_SCREENABLE` on the two-family minimum before
any of that is reached, which is the correct verdict and was reached for the right reason only
after the review.

**RETRACTED: that `aligned` row is manufactured by the adjustment, and the FAIL is not one.**
(The retracted sentence also compared a Clopper-Pearson **lower bound**, 0.4566, against a
**required agreement rate**, 0.5903, as though they were the same quantity and at an n they were
not both computed at. The interval bar is cleared when the lower bound exceeds 0.50; the required
rate is what an agreement must reach for that to happen at a given n. Conflating them makes a
miss look like a near-miss of a specific size.)

The residual reading shows 140 of 140 pairs *decided* where the raw reading decided 123 — because
`residualise` subtracts `a + b*x` from each side, so two sides with the **same** crossover come
out differing by `-b*(x_hi - x_lo)`: a decision whose sign is set entirely by the covariate, with
zero contribution from the statistic the bar is about. The covariate explains essentially nothing
(R² = 3.4e-05). All 17 of `aligned`'s raw ties were converted this way, eleven of them from pairs
where **both sides sat at the statistic's floor**.

So the rail that exists to catch exactly this could never fire on the reading the bar is declared
on: `MIN_DECIDED_SHARE` sees `ties: 0` in every residual stratum by construction. The raw reading
is `INERT_GENERATOR` — 123 decided of 140, below the 0.90 floor — and **a raw refusal was turned
into a residual refutation by an adjustment that added no information.** On raw-decided pairs
only, `aligned` is 70 of 123 = 0.5691, and its honest state is a refusal.

`crossed`'s loss is also mis-described above. It was not power: the ceiling truncated the corpus
in **stratum order**, so `aligned` lost nothing and `crossed` lost a clean corpus-order suffix of
72 of 137 pairs — non-random with respect to stratum, position and view gap, with the survivors
skewed toward the loose half. `DEGRADED_STRATUM` is the right state for the wrong reason.

And the two `crossed` halves were never entitled to the FAILs printed for them: `binding` is set
only for `aligned` and `crossed`, so the halves bypass `MIN_REFUTING_N` entirely. The same pairs
are refused a refutation when read whole and emit two when read as halves.

**The censoring rate is the one clean instrument number.** 0.0301 against the 0.979 the declared
anchor produced and the 0.250 the correction produced locally (§95.5): on Haiku the corrected
anchor censors almost nothing, so the statistic is measuring what it was designed to measure.
The raw, unadjusted reading is `INERT_GENERATOR` — 123 decided of 140, below the 0.90 floor —
which is the tie rate §95.5's mean-over-K correction was aimed at, still biting on the raw
statistic and not on the residual one the bar is declared on.

**And the placebo was vacuous, which is the defect.** It reads `NOT_SCREENABLE`: 0 decided of 24
pairs, every one a tie. The cause is not the budget. `placebo_identical` builds both sides from
the same text, and the deduplication added to stop the remote transport buying identical seeds
twice handed both sides **one** generation set — numerically identical by construction. On the
local transport that is precisely the intended arithmetic check, because seeding on the text
digest makes byte-identical sides byte-identical anyway. On the remote transport it is the
opposite of the intended test: §1.7 downgraded the placebo to an *equivalence* check against
sampling noise, and that requires the two sides to be sampled **independently**. A cost
optimisation silently removed the only thing the remote placebo measures.

So `arm_status` reads the arm `NOT_SCREENABLE`, and that is the correct verdict rather than a
technicality: one control passed, one measured nothing, and a force with a vacuous placebo has
not had its arithmetic checked. The fix — the placebo's low side generated under its own cache
key whenever the transport is non-deterministic — is in the module and unrun, because the budget
that would pay for it is spent.

**What F1 is therefore entitled to say, and it is less than it looks.** Not "the generation field
does not bend": one lineage, an instruct head where §1.4 pins base checkpoints, a prompted
continuation rather than a raw one, an unpinned revision, a vacuous placebo, and `crossed`
underpowered. `combine_families` reports `NOT_SCREENABLE` on the two-family minimum before any of
that is reached. What it *is* entitled to say is narrow and real: **on this model, this
transport and 140 aligned pairs, the residual crossover index does not separate the sides at the
declared bar, and it is not reading formatting.** §9's negative sentence — that the taste is not
recoverable from these models by measurement — remains unearned and unclaimed.

### 95.12 F2 did not finish, and the reason was neither thermal nor F2's

F2 stopped at **1,364 of 1,686 scored units on `gemma-3-4b`**, with the second family not begun.
Its cache is intact and it resumes for free. The interesting part is the diagnosis, which this
entry got wrong once before getting it right.

**The wrong diagnosis.** The arm fell to eight scored units in twenty minutes, and the governor
was the obvious suspect: after the shutdown its pause/resume had been tightened to 58/52 °C, and
the card's *between-calls* floor under load is 53-58, so the hold could almost never release and
exited on its timeout instead. That is a real defect — it is §94's resume-threshold lesson for the
third time, *a resume must sit just under the between-calls floor, not far below it* — and it was
fixed to 64/56 with both thresholds promoted from constants to recorded flags. **It was not what
stalled F2.**

**The right one is in the memory column, and nothing about it is subtle once looked at.**

    t = 12,462 s   mem 11,628 MiB   util   0%     F2 alone, resting between governed bursts
    t = 12,865 s   mem 23,961 MiB   util 100%
    t = 13,676 s   mem 24,035 MiB   util 100%     pinned, at 115 W

Memory near the card's 24 GB ceiling with utilisation pinned at 100% and power *low* is thrashing,
not computation. A **parallel session had started its own GPU job on the same card** — the house
rule that parallel sessions share this repository, arriving through the hardware instead of
through the ledger. F2 was not throttling; it was queueing.

**The banked units were scored anyway, and that is the part worth copying.** Scoring an F2 unit
needs a *tokenizer* — matched filler lengths, distractor flushes, probe offsets — and no weights
at all; only the forward passes need the card, and those were already on disk. A tokenizer-only
load path and a `--from-cache-only` mode turned 1,364 abandoned units into a reported result
without evicting anybody. On this box that should be the default reflex for any interrupted GPU
arm: the expensive half is bought and cached, and refusing to read it because the run did not
reach the end is discarding paid work for tidiness.

    control / stratum        n    decided   wins   agreement   Clopper-Pearson    status
    placebo_identical        24         -      -      0.0000   exact              PASS
    rewhitespace_sham         1         0      -           -   -                  NOT_SCREENABLE
    aligned                 144       144     73      0.5069   [0.4224, 0.5912]   FAIL
    crossed                 137        76     43      0.5658   -                  DEGRADED_STRATUM

**The placebo is the cleanest control this programme has produced.** Byte-identical sides, effect
exactly `0.000000` — §89.4's arithmetic check doing precisely its job, on a deterministic local
transport where the text-digest seeding can deliver it. Set beside F1's vacuous remote placebo
(§95.11) it is the whole argument for §1.7's branch: the same control is an exact check on one
transport and an equivalence test on the other, and only one of those two can actually fail.

**And the sham was never reached, which is the reordering fix arriving one run too late.** F2's
process was launched before controls were moved ahead of the corpus, so it generated the sham
last and stopped before it — one pair, nothing decided. `arm_status` therefore reads the arm
`NOT_SCREENABLE`, correctly: nothing certifies that F2 is reading prose rather than layout. The
identical defect was fixed for F1 hours earlier and F1's sham came back **PASS**. Same class,
same night, one caught in time and one not — which is a fair summary of the whole entry.

`aligned` at **0.5069** with an interval spanning half is chance, and it fails the point bar
before the interval is consulted. `crossed`'s survivors sit at 0.5658 and are not entitled to say
so at n=76.

**So the card was yielded rather than raced.** At 23.4 GB of 24.5 GB in use, continuing would have
risked an out-of-memory for the other session's job as much as for this one, and every GPU arm
here checkpoints per unit — which makes stopping cost time and nothing else. F2 is `NOT_RUN` past
gemma with 1,364 units banked.

**And the watchdog had to be disarmed, which is the part worth carrying forward.**
`thermal_watch.py` terminates *"python processes holding GPU memory"*. That set is defined by a
**resource**, not by an identity — so the moment this programme's own run ended, the set became
**the other session's job**, and the next thermal trip would have SIGTERMed hours of somebody
else's compute to protect a card that was in no danger from it. It now requires an `--only`
pattern and can kill nothing but the run it was armed for. A safety mechanism that selects its
victims by resource rather than by name is a hazard on a shared machine, and this one was armed
and pointed at a stranger for roughly twenty minutes.

### 95.13 An adversarial review read this entry back, and most of what it found was in here

Eighty-nine agents across six lenses — the statistics, F1's statistic, F2's and F3's, the
transport, the controls, and **the claims in this entry** — each finding then handed to a separate
agent instructed to refute it by default. Seventy claims survived refutation, about fifty-four
distinct defects. The synthesis is committed verbatim at
`results/force-review-findings.md`; this subsection records only what it changes.

**The review was run because the session's own pattern demanded it.** Every defect found by hand
that night had returned a plausible number rather than raising, and by 05:00 the entry was full
of numbers nobody had tried to break. What came back is that the entry's two proudest sentences
were both wrong, and that the reviewer found them and the author did not.

**Retracted, and both retractions are in §95.11 above rather than hidden here.** The sham
certified nothing — 100 of 100 sham pairs produce byte-identical feature rows, because F1's
windows join words with a space and `rewhitespace` only touches newlines. And `aligned`'s FAIL was
manufactured by the residual adjustment, which converts every raw tie into a decision whose sign
comes from a covariate explaining R² = 3.4e-05 of the variance, turning a raw `INERT_GENERATOR`
into a published refutation.

**Four code defects fixed the same hour, each of which would have produced a number rather than
an error on the next run:**

- the model-median anchor was built from **every** continuation including both controls, and both
  controls are made from the *high* side — so M was 64.9% high-derived against 33.8% low, shifted
  0.0824 z-units toward the label. The claim in `PILOT_CORRECTIONS` that the anchor "cannot create
  a systematic high/low difference" was false, and is now corrected in place rather than deleted.
- the `crossed` view-gap halves were exempted from the refuting floor, so they emitted FAILs at
  n=28 and n=37 — the same pairs that are refused a refutation when read whole.
- raw ties no longer survive as decisions (above), so `MIN_DECIDED_SHARE` can fire on the reading
  the bar is declared on.
- **the placebo fix orphaned the paid cache.** Adding a `cache_salt` parameter changed every key,
  including for seeds that had no salt — so a resumed F1 would have re-bought all 531 seeds,
  roughly $50, to produce identical numbers. The salt now participates only when set. A cache key
  must change when the *measurement* changes, not when the *signature* does.

**What the review did not settle, and is therefore still open.** Its finding that the primary
statistic sits at its floor — 3,278 of 4,805 continuations crossing at window index 0, because the
global centroid is nearer than the seed anchor on 72.9% of windows — is not a bug with a one-line
fix. If it holds, F1's censoring rate of 0.0301 is low *mechanically* rather than because a decay
resolved, and §95.11's "the statistic is measuring what it was designed to measure" does not
follow. That is the next thing to settle and it is unsettled.

### 95.14 F2's numbers are withdrawn, because it scored the wrong token every time

F2's partial reading in §95.12 — `aligned` 0.5069 on 144 pairs, the placebo at exactly zero — is
**withdrawn in full**. The arm scored the token *after* the site it had matched.

`_site_logprobs` located each probe site by re-tokenising the window's prefix **plus a trailing
space**, and a trailing space tokenises as a token of its own. Verified on both pinned tokenizers:
a site whose intended word is `' the'` reads the logprob of `' river'`. The offset is +1 on
**6,744 of 6,744 sites**.

**That is not a small error, because it destroys the one thing F2's extractor exists for.**
`matched_sites` trims the two sides of a pair to a frequency-matched subset precisely so that the
force cannot measure *rarity* instead of retention. The matching was performed on the intended
word and the measurement taken from its successor — a word with no matching at all. The review
measured the damage: mean |Δlog10 frequency| between the two sides rises from **0.175 at the
matched word to 1.143 at the scored position**, and 35% of scored words fall above the
`MAX_COUNT` ceiling the extractor uses to reject a candidate outright.

**It cannot be repaired from the cache.** F2 stores the aggregated uplift per (passage, window,
sites, distance), not the per-token logprobs, so there is nothing on disk to re-read at the
corrected offset — unlike F1, whose corrections were all in scoring and re-ran for free (§95.11).
Fixing F2 means buying its forward passes again: 1,866 units at the measured rate, roughly four
and a half GPU-hours per family. The fix is in the module and the cache key now carries an
`offset-v2` marker so a corrected row can never be replayed beside an uncorrected one; the run
was stopped rather than allowed to finish producing numbers already known to be void.

**So no force in this programme has produced a valid reading.** F1 refuses in every stratum with
both controls vacuous (§95.11); F2 is void at the site level; F3 has a surveyed substrate and no
forward pass; FX has not run; FM is gated and its one apparent demonstration turned out to be an
identity (§95.8). The programme's §9 negative sentence — *the taste is not recoverable from these
models by measurement* — remains not merely unearned but **unapproached**, and the entry that
would have claimed a step toward it instead documents an instrument that was not yet able to
take one.

### 95.15 The second sweep through the review, and the four defects that were each other's cover

§95.13 worked the adversarial review's A-list and the first third of its B-list. This entry
closes the rest of what could be closed without a forward pass, and the thing worth recording is
not the count. It is that **four of the fixes are the same defect wearing different clothes: a
guard that ran, produced a value, and had no path to a verdict.**

- `arm_status({})` returned `READ`. The loop over an empty dict finds no VOID and no unscreened
  name, so *absence certified itself*. F3 is the demonstration: it imported no control, wrote
  `report["status"] = "READ"` as a literal, and a statistic reading **only newline counts**
  published `aligned PASS / crossed PASS / READ` and fired the headline sentence — while the
  identical statistic VOIDs in F1, F2 and FX, which run their controls. F3 now builds both
  controls at its own grain (chapter lists, not strings), and `REQUIRED_CONTROLS` makes a missing
  control a `NOT_SCREENABLE` rather than a silence.
- `MIN_REFUTING_N = 110` was the minimum of a **non-monotone predicate**. `required_rate` is
  sawtoothed: n in {111, 113, 116, 118} each demand 0.6017 to 0.6036, above the declared 0.6000
  ceiling, yet each clears the floor the guard compared against. F3's `aligned` stratum is
  exactly 118 — the arm with the least power was the one the threshold waved through. The
  requirement is now read at the n in hand.
- The two power guards ran **before** the bars, so a small stratum with decisive agreement was
  published as a corpus-power complaint: 95 of 100 gives a Clopper-Pearson lower bound of 0.887
  and read `DEGRADED_STRATUM`, with prose explaining that it could not refute. Their argument is
  about what a *FAIL* at this n would mean and is silent about a PASS; they now run after.
- `SPLIT_FAMILY` outranked `DEGRADED_STRATUM` and `INERT_GENERATOR`, so a family that said
  nothing was published as a family that **disagreed** — inventing a lineage finding out of an
  absence, on the first real two-family run.

**FM ranked confidence and never skill, and the correction was already written down.** `settle`
took no outcome: `ForcePair` always carries the high-conversion text in `high`, nothing swapped
the sides, so the mean log score was the log geometric mean of the stated probability. A
perfectly calibrated force at 0.52 scored -0.6923; a constant 0.95 scored -0.0513; the accuracy a
real force needed to out-earn a text-blind constant was **0.9920**. The committed dry run gave
the text-blind entry a bankroll of 10836.81 and **0.8804 of the promoted ensemble**. The module's
own pre-registration had said the question was *"P(the high-conversion side is side A)"* all
along — the code simply never asked it. Sides are now swapped on a deterministic, label-blind
coin from `pair_id`; the constant 0.95 falls to a bankroll of 2.12, below the coin's 100, and the
dry run carries `confidence_alone_loses` as a check it would have failed on the day it shipped.

Two things fell out of that fix rather than being sought:

- The **promoted ensemble admitted anything solvent**, and a flat stake leaves a sub-coin
  forecaster standing at the end of 146 bets. It promoted `coin` at 0.0628 and the constant at
  0.0357 — a FORECAST-class candidate part-built from a coin and from something that loses to
  one. Promotion now requires beating the coin, and the dry run's ensemble is the oracle alone.
- The per-stratum block selected its competitor by `constructed_competitors()[-1]`, so adding a
  competitor silently changed which forecaster was reported under the popularity rule's name. By
  name now: the rule scores **-0.2877 in `aligned` and -1.3863 in `crossed`** — right on every
  aligned pair and wrong on every crossed one, which is §79's two-stratum design demonstrating
  itself through a mechanism that had been reporting a constant.

**F1's pre-registered alternative was firing on noise, and the pre-registration was not the thing
that had drifted.** `inverted_u` read `quad < 0 and the peak is interior` with no standard error
anywhere in the function. The fit it declared READ on was quadratic **-0.017463 +/- 0.013543**
(t = -1.29, R^2 = 0.003), and on 2,000 synthetic samples with y independent of x the rule fires
**42% of the time**. `plan/force-program.md` said *significant*; the module had quietly weakened
it to *signed*. With the standard error computed and a |t| >= 1.96 bar, the measured
false-positive rate is **2.55%** — about half of alpha, which is what a negative-coefficient
restriction of a two-sided test should give. The fit also ran on `scores`, which carries the
control sides: 168 of 578 rows were controls and 105 were exact duplicates, and `n: 578` was
printed as a sample size. It fits live sides only.

**F3's substrate cannot refute, at any shape it can produce, and that is now declared rather than
discovered.** Measured from the cached survey before any forward pass:

    585 fictions (uncapped)   191 pairs   118 / 73   required 0.6017 / 0.6301
    200 fictions (declared)    64 pairs    41 / 23   required 0.6829 / 0.7391
     40 fictions (directive)   12 pairs    11 /  1   required 0.9091 / 1.0000

Every one of those rates is above the 0.6000 ceiling, so **F3 is one-directional: it can PASS and
it cannot FAIL**, and a miss returns INSUFFICIENT_N. Raising `EXTENSION_FICTIONS` to chase a
refutable n would be moving a declared bar after seeing that the declared one is unattainable,
which is exactly what §89's rulebook exists to forbid. Related, and a correction to what this
ledger has been quoting: the **191/118/73 shape was never the shape a run reads.** `--survey-only`
reported the unsliced corpus while `run()` sliced at `--max-fictions` before pairing, so the
documented full-run command builds 64 pairs, not 191. Both shapes now print, from both paths.

Three more F3 defects, all of which put a systematic artifact into the slope the arm exists to
read: the ceiling abort was **per-family and mislabelled** (Qwen loses 56 pairs to its 32,768
positions where gemma loses none — 29% of `aligned` and 34% of `crossed` would have existed for
one family only, every one filed as *"a side had missing chapters"*, while `combine_families`
compared two different corpora and called the difference lineage); the foreign donor was **one
chapter tiled** to fill each rung, growing from a mean 2.27 repetitions at j=1 to 12.86 at j=7,
differing between the two sides of 171 of 191 pairs and growing faster on the high-conversion
side in ~60% of them; and `directive_cap_40_fictions` **head-sliced a crossed-first list**, so
the directive's cap was twenty crossed pairs and zero aligned.

**One finding turned out to be cheaper than its fix, and one cache turned out to be worth less
than its size.** F2's cache key omitted the distractor and the filler — the two texts read from
`corpora/toll-scenes.json` that every uplift depends on — so editing the pool replayed stale rows
under `computed_units: 0`. Before adding the digests, the 1,751 banked rows were checked rather
than assumed: **every key matches the pre-`offset-v2` key space and none matches the post-fix
one**, so they are §95.14's withdrawn measurement and not the four GPU-hours they look like. The
file's mtime is *later* than the fix, which is why this needed checking. It is retired under a
name that says so.

**Where the programme stands is unchanged, and that is the point of saying it again.** These are
eleven more instrument defects found before any force has a number — twelve in §95.13, eleven
here — and not one of them moved a result, because there are no results. What has changed is that
the arithmetic which will read the first real run now refuses in the places it used to certify.
Still outstanding and needing a forward pass rather than an edit: **B5** (F2's uplift does not
decay, so the slope may be scatter — unanswerable until the corrected run exists), **B12** (local
F1's 4x continuation-length band, which makes §95.9's "the instrument is ready" false for the
local transport), and the four LOW findings that describe declarations rather than defects.

## 96. The project simulates a writing process, and the version of that sentence which is already dead stays dead

**A frame, not a finding.** Nothing here was measured, nothing here licenses anything, and no
document above it is rewritten. It exists because the parts this project keeps building — a
Director that says what a book is, a Writer with a dossier, a reader that locates rather than
scores, revision operators, a promise ledger that tracks debt — have been arriving one at a time
without a sentence saying what they are collectively. This is that sentence, and its second half
matters more than its first.

**The frame: the project simulates the writing *process*, rendered functionally.** A writer's
working mind as a set of operations that can be performed and measured — drafting, read-back that
**locates** what is on the page and what is missing (the E6 frame), revision operators, direction,
promise debt, backstory. Every one of those is a workflow step. Every one either changes prose or
does not, and the difference is visible in the prose.

**The rule of the frame, which is the whole of its content: simulate the workflow, never the
feelings.** The phenomenological version of this idea — a machine given an inner life and asked
to report from it — is not unexplored here. It has been adjudicated, four separate times, and it
lost every time:

| what was tried | what it returned |
|---|---|
| described inner states, asked to move register (§83) | **0 of 4** — the register was invariant to simulated phenomenology |
| personas as judges (§86.2, §89.1) | inert; `qwen3:14b` returned **one distinct answer vector across four personas, byte-identical** |
| demographic backstory (`research/quality-measurement/personas.py`) | **stereotype performance** — a model writing what it thinks that person sounds like, which is a different behaviour wearing the same words |
| self-preference, the verdict channel (§89.4) | dead; position outweighed text **4,676 to 1** |

So the frame is not a licence to build organs. It is a statement about which half of the
metaphor is load-bearing. A writing *process* is a sequence of things done to a manuscript, and
this project can measure whether each of them does anything. A writing *mind* is a claim about
interior states, and every instrument this project has pointed at one came back with a refusal.
**The goal is unchanged and is not a metaphor at all: superhuman books, no human in the loop.**

### 96.1 The standing experiment class this frame creates

**Mind-component ablations.** Any organ — a Director's brief, a Writer's dossier, inner speech,
the promise ledger — toggled across matched books and reported as a **component** effect. That is
a real experimental class rather than a description, and it comes with an arithmetic obligation
that is easy to forget precisely because each component looks like one small switch.

**§61's α division applies to the full component grid, not to each toggle separately.** §61
pre-registration (5): if more than one book could have been reported, the confidence level is
divided by the candidate count. `director-role.md` §4 applies it to N directors and
`writer-roster.md` R4 makes it multiplicative for N×M director-writer pairs. A component grid
multiplies again — four binary organs is sixteen configurations before a single director or writer
is chosen — and §61's own sizing says what a thinner margin costs: at a true win rate of 0.60,
roughly 100–150 decisive judgments; at 0.55, 400–500; clustering inflating both.

**No best-of-grid book is ever reported as the book.** The way out is not to pretend the division
does not apply. It is to fix the configuration *before* the book is measured and report that book.

### 96.2 Anti-scope, which is the operative part

- **No organ is built because minds have organs.** A part earns its place by clearing its own
  gate ladder — wiring, decorativeness, causal ablation — or it does not exist. The frame is a
  way of naming what has already been built; it is not a shopping list.
- **A part that fails its ladder is buried the way the personas were**, in this ledger, with the
  number that killed it. §58 has two entries because CDG earned the first one; the roster will
  earn its own entry either way, and a decorative roster reported as a decorative roster is a
  result.
- **No self-judgment anywhere.** The frame licenses no new judges. An organ that scores, ranks,
  prefers or reads its own reception is the dead verdict channel with a new name, and R3's rule
  from `writer-roster.md` generalises to every component: **a part may locate; it may not
  prefer.**

### 96.3 What is declared and not yet designed

**Inner speech** — a private think-aloud workspace a writer emits before and during a scene,
consumed only by its own continuation, built on the E6 frame (name what is on the page, what is
missing, and where; never how good, never a score, nothing any selector may read). Transient:
never persisted into the context packet, never canon.

Two arms are **pre-registered now, before the component is designed**, because the prediction is
the interesting part and registering it afterwards would be worthless:

- **(a) deliberation-as-description** — the writer says what it intends;
- **(b) deliberation-that-produces** — trial fragments, discarded alternatives, the writer
  demonstrating to itself.

**Operator prediction, registered 2026-08-20: (a) is inert, (b) binds.** This is §83's
description-versus-demonstration line applied inward, and it is the same line that has already
come up twice this week from the other side — §83 found register invariant to *described* inner
states, and the Writer roster found that a dossier written with em dashes *demonstrates* the mark
on every draft where a dossier instructing about it merely says so. If (a) binds, §83 is in
question and that is worth more than a confirmation.

Two constraints that bind before the first line of it is written. Its gate ladder is the usual
one — G0 wiring on the fake provider, a decorativeness check that scrambles inner speech across
scenes (**if prose does not degrade, the channel is ornament**), and a causal ablation at book
grain that rides the next fitness batch rather than bespoke drafting. And **the leak-audit scope
is extended before the first dump, not after**: an inner-speech transcript may quote packet or
library material, which makes the dumps potentially excerpt-bearing, so they are local-only and
gitignored under the same rule as `research/quality-measurement/derived/`.

## 97. The readership becomes the reward model, and the one bit a person still gets is the one that trains nothing

**Registered 2026-08-20, before any code in this programme was written and before any anchor text
was downloaded.** The architecture is named plainly here so that no later session has to
reconstruct it from the parts: **RLHF for literature with unsolicited behaviour as the feedback.**
A simulated readership is the reward model — FORECAST-class, cheap, per-draft. The real
population, reached through the library, is the settlement layer. The operator is a one-bit
acceptance gate that a general system has to earn. The goal is unchanged and is not a metaphor:
**superhuman books, no human in the production loop.**

It reuses rather than rebuilds: the BCR body (§94), the market as corrected in §95.15, the force
harness, the E6 located channel (§89.4), the twenty fitness books, the library (§92–93).

### 97.1 Three amendments, recorded before any code

**PREFERENCE is reserved, not retired, and the distinction is exactly one line wide.** §95.1
retired `PREFERENCE` because §82 refused the licence on evidence class and the scope axiom
destroyed the only key. **That retirement stands for machines at every grain, forever.** The
amendment is narrower than it looks: preference at **BOOK grain, at acceptance time, is reserved
to the operator** — one bit, accept or reject, no diagnostic riders. A rejection carries no
explanation into the system. Diagnosis comes from population signals or it does not come.

> **The apparent contradiction, resolved here rather than left for a later session to trip on.**
> The scope axiom is *no solicited human judgment, ever — not hired, not operator, not one
> blinded pair*, and an acceptance gate is a person being asked something. The axiom is about
> **measurement**, and the gate is not a measurement: it never trains, calibrates, weights or
> selects any instrument, it produces no number, and it enters no fit. It is the same shape as
> §96's argument for the Director — a role that measures nothing cannot be an invalid
> measurement — and it carries the same obligation in exchange: **containment**, which is what
> the cadence cap in §7.3 is for. A gate consulted constantly is a training signal wearing a
> gate's name.

**The generalization objective is codified.** No instrument in this repository is ever trained,
calibrated, or selected on operator traces, operator A/B responses, or operator diagnostics.
Operator design input enters by exactly one door: as a **registered prior** — the em-dash template
(§78.3, §80) — falsifiable, VOID until evidence, and never protected spec. §78's own em-dash
hypothesis is still VOID with the estimate leaning *toward* the mark, which is what a registered
prior looks like when it is honoured.

**Anchor admissibility.** Operator-named works are admissible calibration corpora **iff** they are
population-consensus summits, which is checkable — the named set's popularity is a public number
and not a taste claim — and they live on the **measurement side only** (RS1 below).

### 97.2 The gate's information policy, pre-registered before the first consultation

Operator amendment, 2026-08-20, arriving with the directive rather than after a disappointing
gate. The one-bit gate stays one bit **in band**; what changes is that the bit stops being the
only thing recorded about the event.

**(a) The acceptance read leaves a behavioural trace, in the BCR's vocabulary and no other.**
Where the read was abandoned, whether it was returned to, whether it survived a reread. Recorded
at every consultation and **used for exactly one thing: comparison against the frozen sim's
forecast.** Never a training input, never a selection input, never a weight.

> The line here is thin enough to be worth drawing explicitly, because §97.1 forbids calibrating
> any instrument on operator traces and this records operator traces. The permission is to
> **read** the comparison; the prohibition is on **feeding it back**. A trace that shows the sim
> forecast a finish where the operator abandoned at scene four is a fact about the sim's error,
> and a programme that then tuned the sim to that trace would have quietly made one person the
> reward model — which is the failure this whole architecture is built to avoid.

**(b) The divergence trigger, declared with its threshold now.** If **three consecutive
candidates** clear every machine gate and every sim threshold and still fail the grab, the
**operator-harvest leg opens**. Three consecutive is a statement about the sim, not about the
books: a reward model that passes what the population's proxy rejects three times running has
been shown to be modelling something other than the target.

What the harvest leg admits is fenced on three sides. Operator-located defects enter as
**candidate axes only** — never as instructions, never as spec. Each is subject to **the fidelity
gate before any sim or writer may act on it**, and that gate is against *real readers on held-out
material*, not against the operator. **Verbatim operator prose stays quarantined in the ledger
entry**; what crosses into the system is the located axis. So the operator may point at where a
book failed; the population still decides whether the thing pointed at matters. That is the same
shape as `reader-judge-loop.md` §2.1's four-step admission path, entered from a new door.

**(c) Described taste never crosses at the gate itself.** A rejection remains explanation-free
in band, exactly as §97.1 says. The channel widens only through (a) and (b), both of which are
out of band, both of which are gated, and neither of which is a training signal.

### 97.3 RS1, the rail with a near-miss already behind it

Anchor and contrast text may enter measurement, mining, and validation. **It may never enter a
drafting, revision, or planning prompt — whole or in part, paraphrased or verbatim.** Same
boundary class as `writer-roster.md`'s R1, and it fails the same way: a vocabulary guard is not
comprehension.

So RS1 is enforced by **provenance rather than by pattern**: corpus digests are never referenced
by any generation-side module, and that is checkable in CI rather than asserted in a docstring.
The reason it gets a mechanism instead of a rule is that this project has already walked toward
the edge of it once — the 294k near-miss was this exact text heading for the public repo — and
`writer-roster.md` found the same boundary from the other side days later, when the R1 guard
refused four dossiers for *containing* em dashes rather than for instructing about them. **Prose
that is present demonstrates**, whatever it was put there to do, which is §83's line and now the
most frequently rediscovered sentence in this repository.

### 97.4 What a sim is allowed to be

- **Valence is behavioural or it is nothing.** A sim's output vocabulary is the BCR's: *continue,
  abandon, return*, under a declared budget. **No verdict slot exists anywhere in a sim** — §89.4
  stands, and it stands at 4,676-to-1.
- **No sim narrates its psychology as signal.** This repository has measured a model confabulating
  a difference between byte-identical texts (§94.5), so a sim's account of itself is data about
  the sim and never about the text.
- **The "why" is located, not narrated.** Candidate taste-properties are mined as **E6-located
  contrasts** between summit and matched mid-tier text — named, positioned differences, the one
  channel that survived §87–§89. Each property enters a property ledger with its counter or
  locator committed **first**.
- **The fidelity gate, FORECAST-class per §86 exactly.** A property is promoted into a sim only if
  injecting or removing it through §85's certified operators moves the sim's behaviour **in the
  same direction it moves real readers**, on held-out, story- and author-disjoint material. A sim
  responsive to properties the population ignores is a mirror, not a reader, and the gate is the
  entire difference between the two.
- Candidate sims face §94.6's battery. **Two of four reader candidates are already dead**; new
  ones earn seats the same way, controls first, refusal states intact.

### 97.5 Selection, containment, and why the market's corrections are load-bearing

Sim configurations bet on real behavioural outcomes — the 281-pair conversion labels now, library
telemetry when it exists — under proper scoring with skill-weighted promotion, splits **story-
disjoint and author-disjoint**, settlement instant on scraped labels, nothing solicited ever.

**§95.15's market fixes are not history here, they are the mechanism.** That entry is one day old:
`settle` took no outcome, so the market ranked stated confidence and a text-blind constant took
0.8804 of the promoted ensemble; promotion admitted anything solvent, including a coin at 0.0628.
Both are repaired, the coin and the constant are seated as baselines, and `confidence_alone_loses`
runs as a check. A programme that selects reward models through that market would have selected
for confidence.

Containment of the loop itself:

- **The sim is frozen per production cycle.** The writer optimises against a frozen sim; sims
  update only *between* cycles, from new unsolicited data, and never from the writer's outputs
  within the cycle they are judging.
- **T3 becomes the central instrument** (§86). The exploitation budget is instrumented from the
  first optimisation step, and a cycle that exhausts it **halts the writer, not the budget**.
- **The writer never sees sim internals.** Feedback crosses only through the existing
  reader → writer schema — `AxisDirection`, located, actionable, preference-free. R3 holds on both
  sides: a reader may locate and may not prefer; a writer may draft and may not judge.
- FORECAST licences are §86's unchanged: STORY grain, absent from `veto_for`, never accepted by
  `plan_search`'s judge path. Any expansion is its own entry with its own containment argument.
- **Publication is the debugger.** Reality is the one thing the writer cannot exploit.

### 97.6 The registered hypothesis, and the three ways it dies

**Operator's prior, registered before the first property is mined:** *the taste function of the
named summit's readership is extractable from pretrained models at accessible scale, because
those readers are in the training data.*

Declared kills, all three now rather than after a disappointing number:

1. every mined property fails the fidelity gate **in both directions**;
2. all sim candidates fail §94.6's battery;
3. the market's skill-weighted survivor is **the coin**.

Any one closes the programme with the negative as the finding, and **the negative is publishable**:
it would be the first evidence that population taste is not recoverable from these models by
behavioural simulation. That is a real result and the programme is sized to be able to return it.

### 97.7 Gates, in order, nothing skipped

| gate | what it establishes | cost |
|---|---|---|
| **G0** | wiring on the fake provider: properties reach a sim, sims reach the market | zero |
| **G1** | sim distinctness — a sim must differ from seed-resampling of itself (§89.1's class); IDENTICAL or INDISTINCT buries the config | cheap |
| **G2** | fidelity on far pairs, summit against mid-tier: §97.4's gate at its easiest setting | moderate |
| **G3** | near-pair honesty — on §83-class twins a sim must **refuse** rather than confabulate; a sim that always has an answer is measuring its own noise | moderate |
| **G4** | first frozen-sim production cycle on fitness-book substrate, T3 instrumented; **the operator gate stays untouched until every machine gate has cleared** | GPU |
| **G5** | publication settlement: sim forecasts against real telemetry, the only scoreboard that compounds | slow |

### 97.8 Anti-scope

No operator-trace training, ever. No anchor text on the generation side, ever (RS1). No
narrated-psychology signal. No verdict slots, no new judges, no exposure of sim internals to the
writer. No licence movement by implication — §82's and §86's classes stand, and every expansion is
its own entry. **No consultation of the operator gate before G4 clears.**

### 97.9 §7 is unfilled, and three of its four items cannot be filled by a session

Recorded as outstanding rather than defaulted, because each blank gates something specific:

- **Anchor set names** — `Mother of Learning` plus two to four more, each carrying its
  population-consensus citation. Blocks `plan/anchor-set.md`, the contrast corpus, and every
  mining step. **A session cannot invent these**: the whole admissibility argument in §97.1 is
  that the set is *operator-named and population-checkable*, and a set chosen here would be a
  machine's taste claim wearing an operator's authority.
- **The grab criterion** — the acceptance event defined behaviourally, **in the operator's own
  wording, recorded verbatim and unchanged thereafter**. Blocks G4's exit. Paraphrasing it would
  defeat the point of recording it verbatim.
**Filled at issuance, 2026-08-20, and pre-registered here before anything they gate exists:**

- **Gate cadence cap: at most one consultation per candidate, and at most one per week.** The
  loosest of the three options offered, and the record should say what that costs and buys. It
  buys the fastest possible divergence signal: §97.2's trigger needs three consecutive failures,
  which at this cadence can fire in three weeks rather than six. It costs containment margin —
  the cap is doing less of the work §97.1's argument leans on, and the weekly ceiling is now the
  binding half rather than the per-candidate one. One read a week is still nothing like a
  training cadence, which is the property that has to hold; but the margin is thinner and a later
  session should not quietly assume otherwise.
- **Spend caps: the declared defaults.** GPU-hours **40**, with a check-in at **24**; API
  **$25**. Recorded with the fact that makes the GPU figure smaller than it looks: the force
  programme's F3 is running on the same single card, so the two tracks share one budget of wall
  clock whatever their separate hour counts say.
- **Contrast-corpus download: ALLOW**, local-only and audited. The matched mid-tier corpus may be
  fetched, and it is fenced by the same three rules as the anchor set: never committed,
  gitignored, leak-audited **before the first byte lands** rather than after, and RS1-fenced to
  the measurement side by provenance. Without it G2's far-pair fidelity gate has no contrast and
  the programme's easiest gate could not be run at all.

**Still outstanding, and neither can be filled by a session:**

- **Anchor set names** (§7.1) — `Mother of Learning` plus two to four more, each carrying its
  population-consensus citation. Blocks `plan/anchor-set.md`, the contrast corpus's selection
  rule (which is *matched to* the summit set and cannot be written before it exists), and every
  mining step.
- **The grab criterion** (§7.2) — the acceptance event defined behaviourally, in the operator's
  own wording, recorded verbatim and unchanged thereafter. Blocks G4's exit.

Until the anchor names and the grab criterion arrive, the programme can build RS1's provenance
rail and its CI check, the property-ledger structure, and G0's wiring — none of which needs to
know which works were named.

### 97.10 The anchor set is wider than §7.1 declared, and the corpus cannot supply it

**The cap moves from 3–5 to the operator's full named set** (2026-08-20). The argument is the
operator's and it is correct on its own terms: a taste function mined from ten summits generalises
further than one mined from three, and §7.1's cap was a declared number rather than a derived one.
Recorded as an amendment rather than argued with.

**What blocks the anchor set is availability, and it was never the count.** Measured against the
cached RoyalRoad shards before any download was proposed. **The first pass of this table was wrong
and is corrected here rather than quietly amended**: it counted one row per *chapter* and called
the result distinct titles, so every percentile it published was chapter-weighted and over-weighted
long fictions. Per **fiction**: 22,397 of them, p50 = 2 followers, p90 = 57, p99 = 2,035,
p99.9 = 8,136, maximum 18,718.

| named work | in corpus | followers | reading |
|---|---|---|---|
| Paranoid Mage | yes | **17,850** | **second of 22,397**, behind only *The Path of Ascension* at 18,718 |
| Mark of the Crijik | yes | **3,586** | **above p99** (2,035). The first pass called this "~p97" on the chapter-weighted figures and understated it. Its 10,554 views remain incoherent against 3,586 followers where Paranoid Mage runs 536 views per follower, so the *row* is still suspect even though the rank is not |
| Mother of Learning | **no** | — | only *"Mother of Learning: The AU Chapters"*, a fan work at 2,256. MoL proper lives in `BookCrawler/data`, outside the shards |
| Chrysalis | **no** | — | nearest is *"The Chrysalis Shogunate"*, 4 followers, a different work |
| Defiance of the Fall, The Primal Hunter, All the Skills, Bog Standard Isekai, Portal to Nova Roma, Blessed Time, The Mage of Shimmer Mountain | **no** | — | absent under loose substring match, not only exact |

**Retracted: the reverse-survivorship mechanism.** The first version of this entry claimed the
missing works were absent *because* commercial success pulls a serial off RoyalRoad, and called
the 18,718 ceiling a platform-retention ceiling rather than a popularity one. That claim does not
survive its own evidence. The corpus's top ten contains **"The Calamitous Bob (stubbed)"** at
15,913 — *stubbed* being RoyalRoad's own word for a work whose chapters were removed for Amazon —
so stubbed works are plainly **not** excluded from this corpus. The plainer explanation is the
right one: **22,397 fictions is a sample of a much larger catalogue**, absence from a sample is a
fact about the sample, and no mechanism needs inventing to explain it.

What survives the retraction is the only part that was load-bearing: **the corpus cannot supply
most of the named anchors, so they have to be acquired.** The two consequences below stand on
that, not on the mechanism.

1. **The mid-tier contrast is still drawn from this sample**, so whatever "mid-tier" means it
   means it relative to 22,397 fictions with a median of two followers — a distribution whose
   mass is inactive work. The contrast rule's real difficulty is that the population label has
   almost no dynamic range below p90.
2. **Harry Potter cannot enter under the matched-contrast rule at all.** Not RoyalRoad, no
   story-grain follower or view metric, different era and medium. §1 requires a contrast of the
   same genre and era band, length-matched, population-labelled *by the same metric*, and none of
   that is constructible against a RoyalRoad mid-tier. Its population-consensus status is beyond
   argument; its usability under this design is nil unless it is given its own band with its own
   contrast corpus, which is a second programme.

**A wider anchor set also multiplies the contrast corpus.** A summit spanning progression
fantasy, LitRPG, isekai and children's fantasy cannot share one matched mid-tier set; matching is
per-anchor, so the contrast download scales with the anchor count rather than being fixed. That is
a cost of the wider set and not an objection to it, recorded before it is paid rather than after.

**What is still needed from the operator:** §7.4's ALLOW covered the *contrast* corpus.
**Acquiring the anchor text itself is a separate decision and is not assumed.** The narrower step
— fetching public popularity metadata only, so each named work carries the §0.3 citation while no
prose moves — is the cheaper half and would settle admissibility without touching RS1's boundary.

## 98. F3 ran, and it found the mechanism it was built to find and no trace of the thing it was built to predict

**The first force in this programme to produce a valid reading**, and the reading splits cleanly
in two. The statistic works. The statistic does not track readers.

Configuration as amended and committed before the run (§95.15, commit `506f6dd`): ladder (1,2,3)
over four chapters under an 8,192-token cap, 47 pairs — 34 `aligned`, 13 `crossed` — drawn from
140 feasible fictions of 585 surveyed, both pinned families, 1,367 cached units. Nothing was
excluded by the ceiling at scoring time: the feasibility filter and the scorer agreed exactly,
which is what the retained `fit_filter` cross-check was for.

### 98.1 The controls, which is the part that had to come first

| family | placebo | sham |
|---|---|---|
| gemma-3-4b | **PASS**, effect exactly `0.0` over 20 pairs | **PASS**, 14 of 19, CP `[0.488, 0.9085]` |
| qwen2.5-3b | **PASS**, effect exactly `0.0` over 20 pairs | **PASS**, 10 of 20, CP `[0.272, 0.728]` |

Both arms read `READ`. This is the first arm in the programme whose controls certify anything —
F1's were vacuous (§95.11) and F2's were void at the site level (§95.14).

**The placebo is a real zero here, unlike F1's.** Its two passes are independent sets of forward
passes over byte-identical input under a replicate cache key, not a dictionary lookup returning
the row it just wrote; the `replicate` flag exists precisely so that the zero is measured. On a
deterministic local stack it came back exactly `0.0` on 40 of 40 comparisons.

**Gemma's sham is a weak pass and is flagged rather than banked.** 14 of 19 is an agreement of
0.7368, and its Clopper-Pearson lower bound is **0.488** — it contains 0.50 by twelve
thousandths. It passed the rule as written, and it would not take many more sham pairs pointing
the same way to VOID the arm. Qwen's sham at 10 of 20 is the clean result gemma's is not. Anyone
extending F3 should buy sham pairs before buying live ones.

### 98.2 The mechanism is real, on both families, decisively

The shuffled arm was the refutable half: same chapters, same provenance, destroyed order. If
destroying order changed nothing, then "a book teaches the model to read it" would be a claim
about vocabulary rather than about structure.

    ordered slope > shuffled slope, paired within side, 94 sides per family

    gemma-3-4b   88 of 94   mean difference +0.05240   sign test p < 0.0001
    qwen2.5-3b   89 of 94   mean difference +0.05196   sign test p < 0.0001

    ordered slope positive   gemma 94 of 94      qwen 93 of 94

So: a fiction's own earlier chapters make its later chapter more predictable than
length-matched foreign prose does; the advantage **grows** as more of the book is supplied; and
it grows **more when the chapters are in their real order** than when they are reversed. Two
independent lineages agree on every part of that.

**This is a positive result about the instrument and it is worth stating plainly, because this
ledger has recorded very few.** §58 killed CDG, whose shape F3 borrowed, and the pre-registration
said in as many words that if F3 failed, §58 would gain a second entry. It did not fail. The
level artifact that killed CDG is absent from a slope, exactly as designed.

### 98.3 And it does not predict a single thing about readers

| stratum | required | gemma | qwen |
|---|---|---|---|
| `aligned` (n=34) | 0.7059 | 0.5588 — 19 of 34, CP `[0.3789, 0.7281]` | 0.5294 — 18 of 34, CP `[0.3513, 0.7022]` |
| `crossed` (n=13) | 0.8462 | 0.6154 — 8 of 13, CP `[0.3158, 0.8614]` | 0.6154 — 8 of 13, CP `[0.3158, 0.8614]` |

**Headline: `INSUFFICIENT_N`**, both strata, both families, combined the same way. Every point
estimate sits above 0.50 and every one of them sits far below its bar, and the intervals are wide
enough to contain both.

**What this is not.** It is not a refutation, and §95.15 declared before the run that it could not
be one: at n = 34 and 13 the interval bar demands 0.7059 and 0.8462, so a true effect of 0.60
would return `INSUFFICIENT_N` exactly as an effect of 0.50 would. **A miss here is a statement
about power.** The declaration that F3 is one-directional was made on 2026-08-20 before any
forward pass, and it is now doing the work it was declared for rather than being invented to
soften a disappointment.

**Where the power went is the interesting part.** The same run answered one question at
p < 0.0001 and could not answer the other at all, and the difference is not sample size in the
naive sense — it is *pairing*. The mechanism test is **within side**: the same fiction, ordered
against shuffled, 94 paired comparisons whose between-book variance cancels. The label test is
**across books**: fiction A against fiction B, where every difference between two different
novels enters the comparison as noise and only the conversion label is signal. 47 such pairs is
very little against that variance, and the corpus cannot supply more at this ladder.

### 98.4 What the programme may now say

**A force exists that reads structure, and no force yet reads taste.** Those are different
sentences and this entry is careful to keep them apart.

- §9's negative sentence is **not** earned. It requires every force to fail with controls clean
  across two families; F3's controls are clean and F3 did not fail, it abstained.
- FM's gate stays **closed**. §95's market opens on a force clearing §1.2's bars on the held-out
  split, and `INSUFFICIENT_N` is not clearing.
- The one-directional declaration is now a **cost that has been paid rather than a hypothetical**.
  F3 cannot be run to a refutation on this substrate, and a version that could would need a
  corpus with more short-chaptered fictions than this one holds — 140 feasible of 585 surveyed.
- The mechanism result stands on its own and is reusable. A slope that is positive on 187 of 188
  sides across two lineages, and order-sensitive on 177 of 188, is a property of prose that can be
  measured cheaply and does not need the conversion label to be meaningful. What it is *for* is
  now an open question rather than an answered one.

**The honest one-line summary: the instrument works and the hypothesis it was pointed at did not
survive contact with the corpus's sample size.** Nobody should read that as evidence that
structure does not matter to readers. It is evidence that 47 cross-book pairs cannot see it.

## 99. F4, the surprisal field — and the formatting control goes vacuous the moment the directive's own default is applied

**Registered 2026-08-20, before any F4 code was written.** F4 inherits the force harness whole:
shared bars, controls first, refusal states, both readings, digest-keyed caches, two base lineages
minimum. It is a **base-head instrument by construction** — surprisal is precisely the quantity
RLHF warps — local-only, free tier.

**The non-claim, first, because it disqualifies arms rather than caveating them.** Quality is
**not monotone in surprisal at any level.** Maximal surprise is noise; minimal is cliché; the
published perplexity-as-quality record is weak for exactly this reason. Every F4 statistic is a
**shape** statistic, and any arm whose reading reduces to *"higher (or lower) mean surprisal is
better"* is mis-specified and **VOID by this paragraph** rather than by a later measurement.

**F4 is the only instrument in this shop with an external scientific validation target.**
Human reading times are approximately linear in surprisal (Levy 2008; Smith & Levy 2013) and the
N400 tracks it. Published reading-time corpora are unsolicited, public and axiom-clean, so F4 may
calibrate against them. When run, that calibration is **its own sub-entry and is evidence about
the instrument, never about any book.**

### 99.1 The control the directive specified cannot fail, and the default is what does it

§2 of the addendum says, correctly, that surprisal is tokenization-sensitive and that this is
**the first F-instrument whose formatting control can genuinely move**. It then offers two
choices and defaults to (i): compute every F4 statistic on **canonicalized text**, with the
canonicalization function committed, *"sham must then read ~0, any movement is VOID-the-arm"*.

**Both halves of that are right and together they make the sham vacuous.** Under (i) the sham
compares `canonical(x)` against `canonical(rewhitespace(x))`. `rewhitespace` perturbs exactly
what a whitespace canonicalizer normalizes — runs of spaces, sentence spacing, the paragraph
separator — so if the canonicalizer is total over whitespace the two strings are **byte-identical
before a model sees either of them**. The effect is then exactly zero for any model, including a
broken one, on any text. That is a control that cannot fail, which §50 says is not a control, and
it is the same shape as `writer-roster.md`'s permuted-dossier sham found earlier the same day.

The resolution keeps the directive's default and stops mislabelling what it buys:

- **`rewhitespace_sham` is retained and reclassified as a canonicalization-coverage check.** It
  asserts that the canonicalizer actually absorbs the transform. That is worth running and worth
  failing on — a non-zero reading means the canonicalizer is not total and choice (i) is not in
  force — but it is a **unit test of our own function**, not evidence that the model ignores
  layout. It is reported under `canonicalization_coverage`, never as the §78.1 formatting control.
- **A second sham is added that survives canonicalization: `paragraph_break_sham`.** A
  canonicalizer may normalize the paragraph *separator*; it must not move where paragraphs
  *break*, or it would be rewriting the text rather than normalizing it. So relocating a
  paragraph boundary leaves every word, every canonical whitespace convention and the whole
  vocabulary untouched while genuinely changing the token stream. It can move surprisal, and so it
  can fail. **This is F4's §78.1 control**, and the arm is VOID if its interval excludes 0.50.

Stated at design time and not after numbers, which is what §2 asked for.

### 99.2 The statistics, each with its confound named before the run

**F4a — earned surprise, the flagship.** The craft law made computable: *surprising forward,
inevitable backward*.

    forward_spike        surprisal of the event's tokens given prior context
    retro_compression    NLL(setup text | context + event)
                           minus NLL(setup text | context + length-matched neutral continuation)
    earned               forward_spike x retro_compression

Cheap surprise is a spike whose backward term is ~0: it startles and explains nothing. This is
F3's machinery pointed in reverse, and F3 has just been shown to work in the forward direction —
§98's ordered-versus-shuffled result at p < 0.0001 on both lineages is the evidence that
conditioning on a book's own text changes its predictability in a measurable, order-sensitive
way. F4a asks whether that conditioning runs *backward* from a payoff to its setup.

It gives §94's promise ledger its physics: a paid promise should be a spike that retro-compresses;
an unpaid one explains nothing. **F4a is wired to the promise ledger as a covariate source only —
no verdict, no licence**, and §94's machinery keeps its own rules.

**F4b — trajectory shape.** Variance, burstiness, autocorrelation and spectral summaries of the
surprisal series at sentence, scene and chapter grain. **Named confound, declared now: the
dialogue/exposition mix moves every one of these.** Dialogue is short-lined, high-variance and
low-surprisal per token; exposition is the reverse. The mix is recorded as a covariate on every
F4b row before any reading is taken.

**F4c — abandonment, the reader-sim bridge.** Pre-registered as a **two-sided hazard**:
abandonment follows sustained low-variance low-surprise (boredom) *or* sustained unstructured
high-surprise (confusion). Two-sided is the whole point — a one-sided version would be the
monotone claim §99's opening paragraph voids. Validation against story-grain retention labels.
F4c is the BCR body's native food: a base-headed sim reads continuation from probabilities and
never answers a question.

### 99.3 Controls, substrate, and the gate that blocks everything above the pilot

- **`placebo_identical` must read exactly zero on every F4 statistic.** Arithmetic check, and F3
  has just demonstrated it can be a measured zero rather than a cache artifact (§98.1).
- **The memorization probe is a hard gate.** Verbatim-continuation threshold pre-registered
  before use; any pretraining-era text that fails it is quarantined from all NLL readings.
  **Mother of Learning and every RoyalRoad text are presumed contaminated until probed.** Nothing
  above the pilot runs until the probe has landed.
- Two base lineages minimum for any claim (§94.5), pinned revisions, paired same-head contrasts
  only. Where both heads of a lineage run, the base–instruct delta is a first-class reading.

Substrate order follows contamination status, not convenience: **the twenty fitness books first**
— contamination-proof by construction, and every F4 statistic debuts there including F4a against
their promise-ledger records — then the own-generated pool as it grows, and only then RoyalRoad
and the anchors, per text, after each clears the probe.

### 99.4 Decisions, taken on the directive's stated defaults

- **GPU-hours for the F4 pilot: 8**, inside the standing 40-hour cap. Recorded beside the fact
  that F3 has just finished, so the card is free for the first time today.
- **Reading-time calibration (G4): RUN.** It is free and it is the only external anchor any
  instrument in this repository has ever had.
- **Canonicalization: choice (i), canonical text** — confirmed as the directive specifies, with
  §99.1's reclassification of what the whitespace sham then measures.

### 99.5 Anti-scope

No quality claim monotone in surprisal level. No F4 reading on unprobed pretraining-era text. No
instruct-head F4 numbers except as the paired delta beside the same lineage's base head. No
promise-ledger verdicts — F4a feeds covariates and nothing else. No new licences: F4 competes
under FORECAST/BEHAVIOUR like every other force, and the operator gate stays untouched.

## 100. The Qwen lineage moves to 3.5, and the architectural case for it did not survive the card

**Operator directive 2026-08-21: switch to the latest models.** Acted on, with one correction
recorded against my own reasoning rather than buried in it.

**Two of my "not found" reports were wrong, both the same way.** Told that qwen3.5 and gemma4 were
available, I checked `ollama list` — which shows what has been *pulled* — and HF under *Gemma 3's*
naming convention (`-pt`), then reported absence as fact. Both exist. Gemma 4 is current in
ollama's registry with tags `e2b/e4b/12b/26b/31b` and no `latest`, which is why `ollama show
gemma4` failed. Qwen3.5 ships a small series at 0.8B/2B/4B/9B **with base checkpoints**. Absence
from a local cache is not absence from the world, and the authoritative check was the registry and
the HF config, not the machine.

### 100.1 What was predicted, and what the card said

The configs argued strongly for the swap. Qwen2.5-3B runs **full attention on all 36 layers** and
was therefore — not gemma — the family binding every teacher-forced context budget in this
programme. Qwen3.5-4B is **hybrid like gemma-3**: 8 full-attention layers of 32, the same 16 query
heads, and a position ceiling of 262,144 against 32,768. That predicted real head-room on exactly
the axis that has bound F3 and F4 all week.

Measured, single pass, prefix plus target:

| tokens | Qwen2.5-3B (retired) | Qwen3.5-4B (pinned) |
|---|---|---|
| 7,801 | 14.7 GiB, 2.2 s | **17.1 GiB, 3.2 s** |
| 11,701 | 25.4 GiB, 43.5 s | **28.1 GiB, 62.4 s** |
| 15,601 | 40.2 GiB, 285.5 s | **43.1 GiB, 183.6 s** |
| OOM at | 19,501 | 23,401 |

**It is worse at every length this card can reach, by about 2.5 GiB.** The prediction confused two
quantities. Peak memory is resident weights plus *one* layer's attention matrix — layers are freed
as inference walks them — and both families have 16 query heads, so that matrix is identical in
size. A 4B model simply carries ~2.5 GiB more weight than a 3B one. Fewer full-attention layers
reduces **time** at long context, not peak memory, and at the lengths available here it is not
visibly faster either.

**`SINGLE_PASS_CEILING` therefore stays at 8,192**, re-verified on the new pin at 17.1 GiB and
3.2 s, with less margin than before rather than more.

### 100.2 What the swap actually buys, stated without the argument that failed

A current model, and a second lineage **architecturally closer to gemma-3**. That second point is
worth more than it looks: `RUNBOOK` warned that a SPLIT_FAMILY on F2 might be *architectural*
rather than about lineage, because gemma-3 was hybrid and Qwen2.5 was fully global. Both pinned
families are now hybrid, so a future SPLIT_FAMILY is likelier to mean what the rule intends.

Not chosen, and worth recording: **`Qwen/Qwen3-4B-Base` is also newer than 2.5 and would have been
far worse** — 32 query heads and full attention on every layer, double the matrix at equal length.
"Later version", "better instrument" and "cheaper instrument" are three different claims.

**Gemma 4 is not pinned, and the blocker is ours rather than Google's.** transformers 5.15.0 in the
MirrorBench venv raises `'head_dim' is a per-layer attribute and may vary across layers` on every
Gemma 4 config, so the installed stack predates the architecture. Upgrading is worth doing as its
own change with its own verification — that venv is shared with other work and F3's completed
result sits on the current stack — not folded into a family swap.

### 100.3 What this costs the record

`qwen2.5-3b` moves to `RETIRED_FAMILIES` rather than being deleted. **§98's F3 result was computed
on it and is not thereby stale**: it is correctly labelled with the family it used, and re-running
F3 against the new pin produces a *different* reading rather than a corrected one. The old cache
(`derived/f3-qwen2.5-3b.jsonl`) is keyed on model id and revision, so it cannot collide with the
new one and no orphaning is required.

## 101. The product becomes a serial, and the gate that would certify it cannot fail as written

**Operator directive, 2026-08-21.** The unit of production is a **serial**: open-ended chapter
count, produced at cadence (§63), published chapter-wise through the library. The twenty six-scene
books are demoted from product to **measurement substrate**. Planning gains a grain — serial
premise → **arc** → chapter → scene — with existing Director kinds applying at arc grain and no
new lever. The operator gate is unchanged and a serial reaches it only after clearing its highest
attempted rung.

**"Endless" is not a testable claim and the directive says so itself.** The testable form is **no
degradation trend over measured length, claimed only at lengths actually reached**, with every
capacity claim carrying its N. That distinction is the entry's spine.

### 101.1 The gate as specified makes the pass the null hypothesis

§5: *"A rung PASSES only if no metric worsens past its bar."* Accepting a null is not a finding —
**a noisy instrument passes automatically**, and the noisier the metric the more certainly it
passes. This is the shape §50 keeps naming, arriving one level higher than usual: not a control
inside a track but the ladder that certifies the whole product.

The arithmetic, computed before any bar was proposed. For an OLS slope over *n* equally spaced
chapter indices with residual standard deviation σ, `SE(slope) = σ / sqrt(n·(n²−1)/12)`:

| rung N | tightest slope bound | **total drift bound across the rung** |
|---|---|---|
| 8 | 0.302 σ/chapter | **± 2.42 σ** |
| 16 | 0.106 σ/chapter | ± 1.70 σ |
| 32 | 0.038 σ/chapter | ± 1.20 σ |
| 64 | 0.013 σ/chapter | **± 0.85 σ** |
| 128 | 0.005 σ/chapter | ± 0.60 σ |

**At rung 8 the tightest bound obtainable is ±2.42 standard deviations of the metric itself.** A
"no degradation" pass there is compatible with voice drifting two and a half SDs across the
serial. The rung cannot fail, so it certifies nothing.

**Proposed fix, and it is §87's attainability rule applied to a trend.** Every degradation bar is
stated as an **equivalence bound**, never as a null acceptance: a rung passes when the slope's
confidence interval **excludes** degradation worse than δ. Insufficient data then returns
`INSUFFICIENT_N` rather than PASS — exactly as F3's strata do, and exactly as §98 has just
demonstrated is a real outcome rather than a hypothetical. Four metrics all required to clear is
conservative in the pass direction, so no multiplicity correction is owed.

**Consequence the operator should see before paying for a batch: rungs 8 and 16 cannot support a
no-degradation claim at any useful δ.** They are wiring and feasibility rungs. **The first rung
entitled to make a capacity claim is 32**, and 64 is where the bound gets genuinely tight.

### 101.2 A chapter of four to five scenes does not fit the measurement twice

Operator, 2026-08-21: a chapter is currently **4–5 scenes**. Against the fitness shelf's measured
658 words per scene, and the **8,192-token single-pass ceiling** re-verified on the new Qwen pin
in §100:

| scenes/chapter | words | tokens | context left under the cap after the target chapter |
|---|---|---|---|
| 4 | 2,633 | ~3,555 | 4,381 tokens = **1.23 chapters** |
| 5 | 3,291 | ~4,443 | 3,492 tokens = **0.79 chapters** |

**At five scenes per chapter, one prior chapter plus the target does not fit in a single
teacher-forced pass.** This is §3's *"no context window holds a serial"* arriving much sharper
than intended: on this card no context window holds **two chapters** for scoring. Three
consequences, none of which the directive's design contradicts, but all of which it assumes away:

1. **The §5 degradation metrics are safe**, because they are within-chapter statistics compared
   *across* chapter index. A surprisal series over one chapter fits comfortably. Trend-over-index
   is the right shape and it is the shape that survives this ceiling.
2. **Canon integrity at distance (§3) cannot be done by context.** "Sampled facts from chapter k
   re-verified at chapter k+Δ" has no pass that holds both chapters. It must be a **retrieval**
   check — query the canon store, score a short probe against the retrieved fact — which is what
   §3's own query-against-durable-canon design implies but does not say.
3. **F4a at serial scale must be excerpt-based, not chapter-based.** Its retro-compression term
   conditions setup text on the payoff event; if setup and payoff sit in different chapters they
   cannot share a pass. F4a operates on located setup/payoff *excerpts* drawn from the promise
   ledger, not on whole chapters.

**Recommendation, and it is a real trade rather than a preference: choose four scenes per chapter,
not five.** Four leaves 1.23 chapters of context under the ceiling and five leaves 0.79. Anything
wanting one chapter of prior context plus a target is measurable at four and impossible at five,
on this hardware, today. If the product wants five, that is a legitimate choice and the cost is
that a whole class of cross-chapter measurement stops being available.

### 101.3 Substrate and spend, priced from the only own-generated cost data that exists

The fitness shelf: 19 books, 6 scenes each, median 3,950 words, **$0.2097 per scene**, $23.90
total.

| shape | scenes | words | cost |
|---|---|---|---|
| **3 × 32 × 4** (the §9 default, four scenes) | 384 | ~253k | **$80.51** |
| 3 × 32 × 5 (the §9 default, five scenes) | 480 | ~316k | $100.64 |
| 2 × 32 × 4 | 256 | ~169k | $53.67 |
| 5 × 16 × 4 | 320 | ~211k | $67.09 |
| 3 × 64 × 4 | 768 | ~506k | $161.02 |

**The §9 default of 3 × 32 fits the $120 budget at either scene count.** One wrinkle worth naming:
the declared check-in at **$80 fires at 100% of the batch at four scenes and at 80% at five**, so
as set it is a near-completion checkpoint rather than a mid-course one. If the check-in is meant
to be a place to stop and look, **$50 would fire near the end of the first serial** and be worth
something.

Note what 3 × 32 × 4 actually buys: **~253,000 words**, against the entire fitness shelf's ~79,000.
This is an order-of-magnitude change in what this project produces, and the substrate is
contamination-proof by construction for the same reason the shelf is.

### 101.4 What is proposed and what still needs a signature

Proposed by the agent per §9, pending operator signature before rung 1 runs:

- **Bars are equivalence bounds, not null acceptances** (§101.1). This is the load-bearing one.
- **Rungs 8 and 16 are declared feasibility rungs** that make no capacity claim; the first
  claim-bearing rung is 32.
- **Four scenes per chapter** if cross-chapter measurement is wanted (§101.2).
- **Check-in at $50** rather than $80, so it lands mid-course (§101.3).
- δ per metric is **not** proposed here, and deliberately: δ is in units of each metric's own σ,
  and three of the four metrics (voice drift, quality-by-index, canon-integrity rate) have never
  been measured on serial-shaped text. Proposing δ before G1 has produced a σ would be inventing
  a bar and then discovering whether it was reachable, which is the failure §87's rulebook exists
  to prevent. **G1 at rung 8 produces the σ; δ is signed after it and before rung 32 binds.**

Still operator's: the substrate split, the drafting budget, and G3's cadence per §63.

### 101.5 Anti-scope, carried forward

No "endless" claim at any finite N. No new judges, no licence movement, no per-scene casting, no
new Director kinds. One writer per serial is the default for voice continuity and R4's arithmetic;
per-arc casting is a registered open question and is not built. §61/R4's α division now counts
**serials** as the reported unit. Canon-store contents follow the existing leak rules wherever any
third-party-derived text is involved.

## 102. F3 replicates on a third checkpoint, and the control that nearly moved in §98 has now nearly moved twice

The re-run §100 called for, on the new pinned pair (`gemma-3-4b` + `qwen3.5-4b`), 683 fresh
Qwen units. **The pair shape held exactly** — 47 pairs, 34 `aligned`, 13 `crossed`, identical to
§98 despite a different tokenizer, so this is a like-for-like replication rather than the same
design on a different corpus. That was a live risk and it did not materialise.

### 102.1 The mechanism replicates, and now stands on three checkpoints

| checkpoint | ordered > shuffled | mean difference | sign test | slope positive |
|---|---|---|---|---|
| gemma-3-4b | 88 / 94 | +0.0524 | p = 8.8e-20 | 94 / 94 |
| qwen2.5-3b *(retired, §98)* | 89 / 94 | +0.0520 | p < 1e-18 | 93 / 94 |
| **qwen3.5-4b** | **87 / 94** | **+0.0549** | **p = 1.1e-18** | **93 / 94** |

Three independent checkpoints across two lineages, one of them a model that did not exist when
the hypothesis was registered. A fiction's own earlier chapters make its later chapter more
predictable, the advantage grows with more of the book, and it grows **more in the real chapter
order than reversed**. This is now the most replicated positive finding in the repository.

### 102.2 The sham looks real, and the per-family rule says PASS

§98.1 flagged gemma's sham as a weak pass rather than banking it: 14 of 19, agreement 0.7368,
Clopper-Pearson lower bound **0.488**, containing 0.50 by twelve thousandths. On the new pair
**both families landed on 14 of 19**, to four decimal places, in the same direction.

That coincidence was checked before it was reported, because a byte-identical control block
across two families is what an aliasing bug looks like. It is not one: **0 of 19 sham slope rows
are identical across the families**, and they disagree about *which* pairs — only 10 of the 14
wins overlap, and 8 pairs are won by one family and lost by the other. The computation is
per-family and correct; the summary agreement is chance.

**Which makes the reading worse rather than better.** Two independent lineages, disagreeing at
the level of individual pairs, both arriving at 74% agreement *in the same direction* — the
untouched side beating the re-whitespaced one. Pooled that is 28 of 38, CP **[0.5690, 0.8660]**,
which **excludes 0.50**.

**Pooling is not the rule and this is not a verdict.** §94.5's never-pool rule exists so that one
family's artifact cannot masquerade as a finding, and the per-family readings both PASS. But the
rule guards against the opposite situation to this one: here the two families *agree*, and the
accumulating evidence points at a control that is moving. The honest statement is that
**F3's formatting control has now nearly failed twice, and the second time on two lineages at
once.**

**Why this is probably real, and it is the problem §99 was written to avoid.** F3 computes its
slope on raw text. F4's pre-registration opens by observing that surprisal is
tokenization-sensitive and therefore mandates canonicalization before any statistic is taken.
**F3 has the defect F4 was designed around.** `rewhitespace` changes paragraph separators, which
changes the token stream of the *true-context* condition, and the measured direction is exactly
what that predicts: destroying the whitespace convention reduces how much a book's own context
appears to help.

**What survives it, and this is the load-bearing distinction.** The ordered-versus-shuffled
comparison is **whitespace-matched by construction** — both arms are the same chapters joined by
the same separator, differing only in order — so §102.1's result is untouched by whitespace
sensitivity. **The label reading is not protected the same way**, and it is the reading that was
already `INSUFFICIENT_N`.

### 102.3 The label reading, unchanged in verdict and newly split in direction

| stratum | required | gemma-3-4b | qwen3.5-4b |
|---|---|---|---|
| `aligned` (n=34) | 0.7059 | 0.5588 (19/34) | **0.4706 (16/34)** |
| `crossed` (n=13) | 0.8462 | 0.6154 (8/13) | 0.6923 (9/13) |

**Headline `INSUFFICIENT_N`**, both strata, both families, exactly as §95.15 declared before any
forward pass. Worth noting without over-reading: qwen3.5 puts `aligned` **below** 0.50 where
gemma puts it above, so the two families now disagree in *direction* on the binding stratum. At
these n both are refusals and the disagreement changes no verdict, but it is not evidence of a
weak effect — it is evidence of no detectable effect.

### 102.4 What to do about it

- **Buy sham pairs before live ones**, as §98.1 already said and this run makes urgent. The
  control is at 19 decided pairs per family against a `MIN_SCREENING_N` of 12. Doubling it would
  settle whether F3 is VOID, and it is cheap.
- **Canonicalize F3's text**, adopting F4's committed canonicalizer, and re-run. If the sham
  reads nothing afterwards, the sensitivity was tokenization and the arm is repaired; if it still
  moves, F3 reads layout and §78.1 voids it. Either outcome is worth the GPU time and neither is
  available without the change.
- **§102.1 stands regardless of both.** It is whitespace-matched by construction, replicated on
  three checkpoints, and does not depend on the label the rest of the arm failed to predict.

## 103. The prompt was frozen so it could be read, and for three stages nothing read it

The write side of provenance has been complete since Stage 1 and it is unusually complete: the
rendered prompt and system string are frozen onto the job payload at enqueue (invariant I5, so
a retry re-reads the same bytes and varies only the sampler seed), every attempt gets a
`policy_decisions` row with its gate ladder and its spend — refusals recorded as fully as
acceptances — revisions are immutable and content-addressed, losing tournament drafts stay in
`span_candidates` because deleting refused work is how a selection stops being auditable, and
`migrations/021_foreground_loop.sql` states outright that the events table *is* the provenance
record.

**None of it had a reader.** `read_log`, `decision_for_revision` and `lineage` had no caller in
`src/` at all — only the suite — the frozen prompt was printed by no command, and the per-scene
statement that steers a draft was unreadable from the CLI. This is the third time this file has
recorded the same shape: §31 for plans, §39 for state, and now for prompts, decisions and
events. The pattern is not "the feature was missing"; in all three cases the data was there,
correct, and written with care. What was missing was the sentence "and here is how you look at
it", and the tell is identical every time — the only way to see any of it was to open the
SQLite file.

### 103.1 One dossier, because the question spans seven tables

`litharness why --scene N` joins the accepted revision to its policy decision, the frozen job
payload, the plan statement, the scene's feedback provenance, its craft measurements, its
findings, and the tournament candidates that lost to it. Every one of those lives in a
different table, and the operator's actual question — *why did this scene come out like this*
— is not answerable from any one of them.

**The verb is `why` and not a noun, which breaks this CLI's habit deliberately.** Nearly every
other verb names an object (`plans`, `findings`, `state`, `discards`) or an action (`verify`,
`replan`, `contrast`). The noun candidates here — `dossier`, `provenance` — name the *artifact*
this prints, and the artifact is not what anyone is looking for. `blame` is the sibling verb
and it is a question in a verb's clothing too, borrowed from the same place. The one word an
operator or an agent types when a scene reads wrong is the one on the command.

**The prompt prints last and whole.** It is the thing the verb exists to show and also the
longest thing in the report, so a summary that came after it would be a summary nobody
reaches. Nothing in the dossier is recomputed from the prose: every line is a column somebody
wrote at the time. A dossier that re-rendered the prompt from live tables would be answering a
question about today, which is the failure I5 exists to prevent on the generation side and is
no less a failure on the reading side.

**The accepting revision is found by walking the lineage for the *change*, not for the first
appearance.** Oldest-first, remembering the revision at every change of the node's content
hash, so a scene a repair rewrote reports the repair. The decision an operator wants is the one
that produced the text they are reading.

### 103.2 Absence is a value, and it took two tries to render it

`unattributed_revisions` exists because §19's integrity clause was asserted rather than
checked. The same discipline is what a forensic read needs, one scene at a time: a dossier
printing a blank where the decision belongs reads exactly like a scene that had no decision to
print. So every gap is named — in the text and in an `absent` list in the JSON — and three of
them (`prose`, `decision`, `prompt`) mean the verb could not answer its own question and it
exits 1. The other two do not: a book run with `--no-outline` has no plan statement and a scene
older than the reader loop has no provenance row, and neither is a fault.

**Two absences that are not the same absence, which the first renderer got wrong.** Walking the
skill against a seeded store — the acceptance step, not an afterthought — turned up an
undrafted scene reporting `no policy decision explains this revision` about a revision that
does not exist. The `absent` list was already right; the *renderer* was sending a reader to
hunt a §19 attribution failure that was not there. A scene nobody has written and a scene
somebody wrote without attribution are different findings that happen to share an exit code.
`test_an_undrafted_scene_is_not_reported_as_an_attribution_gap` pins the distinction.

**The one the write side went to trouble over survives the trip.** A scene drafted with no
feedback records an explicit `[]` whose digest is a real digest of the empty list; a scene
drafted before the loop existed has no row at all. `payload_fields` documents that a nullable
column cannot tell those apart, and neither can a reader that prints both as a blank line — so
the dossier and `blame --json` both keep `null` for "nobody recorded" and `[]` for "recorded,
and it was empty" (`test_an_empty_feedback_set_is_not_the_same_as_no_feedback_row`,
`test_blame_json_keeps_an_empty_set_apart_from_no_row`).

### 103.3 The log reads in write order, with a cursor

`litharness events` is the log as it was written, which is the one view crossing jobs,
decisions, plans and findings without a join — because the store commits each event in the
same transaction as the change it describes. It is bounded by `--limit` and prints the sequence
to resume from, because an agent reconstructing a long run reads it in passes and a reader that
made the caller count lines would be a reader nobody uses twice. `--since` takes that cursor or
an ISO-8601 instant; the stamps are Z-normalised, so a date prefix is a valid one.

Text mode truncates a long payload to one line and says so. That is a pointer, and `--json`
carries the record.

### 103.4 The fence is the point, and it is now a test

`plan/serial-pilot-1.md` §6 keeps diagnostics on the operator's side of the loop and §97.1 says
a rejection carries no explanation back into the system. Everything here is a diagnostic, so
none of it may become a channel into generation — and the cheapest guarantee of that is that
reading changes nothing at all. `test_no_forensic_verb_writes_a_row` snapshots every table's
row count, runs all eight read verbs, and asserts the counts are identical. The skill file says
the same thing in the imperative, because the reader most likely to be tempted to act on a
dossier is an agent.

`--json` landed on `blame`, `feedback`, `plans` and `findings` besides, following the
`status --json` precedent: the object is what an agent chains on and the text is what a human
reads, and both are rendered from one structure in each verb so they cannot drift apart.

### 103.5 A skill, because the reader is a machine that has never seen this repo

`.claude/skills/debug-book/SKILL.md` teaches the workflow symptom-first — *scene reads flat*,
*book drifted from the directive*, *scene ignores canon*, *scene was never written* — with the
exact command for each and what every field means. It was walked end to end against a seeded
store rather than written from the source, which is what caught the renderer defect above and
two documentation errors: `directives` defaults to the *unread* inbox and shows nothing on a
book that has already acted on its direction (`--status applied` is the one you want), and the
missing-provenance line means "no row was written", of which "predates the loop" is only the
commonest cause.

### 103.6 Two write-side gaps this pass deliberately did not close

Both are real and both stayed out of scope, because a read surface is worth having before the
record it reads is perfect and widening a write path is not a read-only change:

- **The context packet's contents are not persisted.** The payload records the counts, the
  section sizes, the token budget and the omission list — which is enough to say *what was left
  out* and not enough to say *what went in*. `context_omitted` is the honest half of a packet
  whose other half is reconstructible only by re-running the assembler against tables that have
  since moved.
- **The raw provider envelope is discarded at the storage boundary.** `Usage` and the resolved
  model survive on the decision; the response as the provider returned it does not. A question
  about a refusal's exact wording, or about a field the adapter did not map, has no stored
  answer today.

The dossier says so where it applies rather than papering over it, and a question the store
genuinely cannot answer is reported as unanswerable — which is the whole idiom this entry is
about.

## 104. The go-to-market has opinions, so they become manipulations — and the platform's own AI rule turns out to be a tag rather than a door

**Registered 2026-08-21, before any variant was generated and before any battery ran.** The
operator reviewed advice from a Royal Road author in the platform's top ~1% (~2,000 followers)
on what sells there and had it distilled into seven claims. The design is
[plan/royalroad-platform-priors.md](royalroad-platform-priors.md); this entry carries the scope,
the bars, and the one fact in the set that is not a hypothesis.

**Nothing above this entry was renumbered.** §102 was the last section when this began and the
check was run again across every branch and worktree on this machine; §103 was then taken by a
parallel session while this was being written, and this entry moved rather than the one that
landed first.

**The framing, and it is the whole entry.** A claim from a successful author about a platform is
evidence about a readership, and this project has exactly one instrument that can put a question
to a readership: a budgeted reader's allocation. So each load-bearing claim becomes a
manipulation with a dose, and the answer is whatever the reader does. **A null is a result and
is recorded as one; nothing here is compiled into a drafting directive.** Two of the seven are
already this project's defaults — Serial Pilot 1's tone note declares close third person and
past tense, and its C4 prices every gain on the page — so for those the informative outcome is
the one that *refutes* the default we already have.

### 104.1 D1P: a second battery tier, and the kill condition points the other way

`bcr.D1_FAMILIES` is certified damage, which is exactly why §A3 can say a dose-response
inversion there kills **the instrument**. Nothing in this programme is certified damage: "lyrical
prose is a liability on this platform" is a claim whose sign is the hypothesis. So the tier is
separate and the kill inverts.

| tier | material | an inversion kills | order |
|---|---|---|---|
| D1 | certified damage | the **instrument** | first; it is what seats the reader |
| **D1P** | platform priors | the **family** | second, on a model D1 has already passed |

**A D1P family may be read only on a model already seated (§A2) and already through D1.** Run
the other way round, a family that moves nothing is indistinguishable from a reader that
perceives nothing. The ordering is written into the module's pre-registration so a later session
cannot reverse it by accident.

Six families, built this session in `research/quality-measurement/platform_priors.py` with
`tests/test_platform_priors.py` holding the structural invariants: `purple_prose_dose`,
`suffering_load`, `info_dump_dose`, `character_flood`, `pov_fragment`, `tense_shift`. Two lanes —
a paragraph-aligned rewrite whose *changed set is discovered rather than requested*, so a dose is
a set of the model's own edits; and a pure-insertion lane where the original survives
byte-for-byte at every dose. **Dose grows from the front**, because every claim in the set is
about the opening. **The grain a shelf reads is the book, not the scene**: a shelf member needs
13 chunks and one own-generated scene is 912 words, so generation is per scene and the dose is
applied across the assembled book. `platform_placebo` — the same contract with an inert
instruction — is the floor no family certifies without clearing.

**Three outcomes are named per family before the first session** (`confirms`, `refutes`, `null`)
and the reading is two-sided for all six. `purple_prose_dose` is why: the platform claim and the
general craft prior point in opposite directions, so a one-sided registration would have made one
of the two answers unreportable.

**Two costs are declared with the families rather than found afterwards.** `suffering_load` at
high dose can contradict what a later paragraph assumes, so a confirm there honestly reads as
"setbacks *or* the incoherence they introduce", and separating them needs a coherence-matched
control this session did not build. And `tense_shift`'s ladder measures two things: dose 1.0 is a
present-tense book, which is the claim, while every rung below it is part-present and part-past —
*tense instability*, which nobody claimed anything about. The confirmatory reading is the top
rung; the ladder is a shape reading under its own name.

### 104.2 The bar is 0.15 because 0.10 was computed to be outside the budget

Declared-bars rule, executed. Quantity: allocation share against the manipulated side, `[0, 1]`,
direction named per family, unit a share of 12 fetches — except the only model ever seated
commits for a whole session, so the binding unit is the session. Non-emptiness: the one
own-generated book is 33 chunks against a floor of 13, and a rehearsal built **24 shelves with
none skipped**.

Sizing from the observed reader, never from the simulator (`phi4`'s 72 seating sessions, shares
of exactly 0.0/0.5/1.0, per-session sd **0.4039**), through `bcr.cluster_interval`:

| δ | α = 0.05 | α = 0.025 | α = 0.00833 (six-family adjusted) |
|---|---|---|---|
| 0.15 | 24 | 24 | **48** |
| 0.10 | 64 | 96 | 128 |
| 0.05 | 320 | 448 | 448 |

At δ = 0.10 the six-family set is 768 sessions ≈ **31 GPU-hours** against §97.9's cap of 40
*shared with F3*. Declaring 0.10 would have named a quantity the budget cannot reach, which is
the failure seven prior declarations made. The declared shape is 6 sessions per intermediate rung
and 48 at the top rung — 66 per family, ≈ 16 hours for six — behind a 36-session screen that
costs 1.4 hours and can catch a broken variant set first. At six sessions per intermediate rung
the isotonic fit sees only a gross inversion, and **no subtle non-monotonicity is claimed**.

Each family reports at α = 0.05 with the adjusted 0.00833 printed beside it; any sentence about
the *set* uses the adjusted level and there is no pooled headline.

**Model spend, bounded before it is spent:** 70 generations (10 scenes × 6 families + placebo) on
`claude-opus-5` at §85's measured $0.2316 each ≈ **$16.21**, hard ceiling **$25** enforced per
call, digest-keyed replay cache so an interruption resumes free. The D1P sessions themselves are
local and cost GPU wall clock rather than quota.

### 104.3 The launch package and the opening-weighted arm, designed and not run

**BSC — Browse-Shelf Choice.** K entries for the *same* book, each showing title, tags and blurb;
the reader opens one and continues under a budget; the record is which entry was opened first. No
verbal verdict anywhere, and the choice costs budget, so §89.4's dead channel is not involved.
**Its honest limit is stated in the design**: with K entries pointing at one book everything
after the first open is the same text, so the endpoint is the first-open share and nothing else —
a continuation curve here would be the book reported under K labels. §A2's controls transfer at
packaging grain and a licence does not: a candidate must pass them on *this* stimulus. Selection
is best-of-K under §61 Add 3 / §72's expires-on-use.

**Follower and view columns are never ground truth here, and the reason is sharper than the
existing refutation.** BRIEF §3 records that the engagement label tracks **cover art and launch
timing**. Scoring packaging against a label whose known confound is packaging plus timing, with
no story-grain matching, is circular and refuted at once. It may sit beside a result as a
covariate; it may never grade one. The cover itself has no instrument in this repository and
enters as a declared **brief**, never a measured product.

**The opening-weighted arm.** Shelf members truncated to their first 3,000 words — two chapters
at the ~1,500-word Royal Road format — with the budget at 9 and the free opening chunk unchanged.
An **alpha-divided secondary** beside the whole-book AUC primary, at α = 0.025. All four
properties checked before registering: range `[0, 1]`; direction higher for the target; unit a
share of 9 fetches, resolution 0.1111; non-empty on every substrate this project has (10,049
words in hand, 3,950 median on the fitness shelf, 3,000 reached at chapter two of the publication
format). **The division's price is recorded**: 96 sessions rather than 64 at δ = 0.10, a 50%
surcharge. A fixed-sequence test would keep full α and be more powerful; the division is the
conservative choice the operator asked for, and it was considered rather than overlooked.

### 104.4 Trope-convention mining lands in §97.4, because the document it was addressed to is retired

The instruction named `plan/machine-taste-program.md`. That document is **RETIRED** — §95.1
retires the `PREFERENCE` class for machines at every grain and its own header says nothing in it
may be executed — so an additive scope note there would have extended a closed channel. The live
owner is **§97.4**'s property ledger: properties mined as E6-located contrasts between summit and
matched mid-tier, each entering with its counter or locator committed **first**, each facing the
fidelity gate before any sim or writer may act on it. The note is additive to that scope.

Four convention properties, mining and measurement side only: **status-block idiom** (fields,
placement, blocks per 1k words), **chapter-hook shapes** (what a chapter's last paragraph does,
as a small closed set of located contrasts), **progression cadence** (interval between visible
gains, which interlocks with W2's payoff windows and W3's discrimination — if a reader cannot
name a cadence difference then a cadence convention is a property of the corpus and not of a
reader), and **win-adjacency in openings** (distance in words between a named setback and the
nearest named gain inside the first N words — RR4 as a measurable convention rather than an
instruction).

**RS1 with the specific risk this note adds.** The object that crosses to the generation side is
the located axis restated in our own words, never the prose, enforced by provenance rather than
pattern. The new risk is that a convention property restated too closely *is* a paraphrase:
"status blocks appear about twice per thousand words" is a property, and a rendered example of
one is text. Serial Pilot 1's directives are the existing safe form. **Nothing is mined yet**:
the anchor set is three verified summits of eleven and anchor-text acquisition is an operator
decision that has not been taken.

### 104.5 The platform's AI rule, retrieved from the live site, and it is a tag rather than a door

Retrieved **2026-08-21** through a real browser, because the plain fetcher gets HTTP 403 here —
the same wall `plan/anchor-set.md` records. Every URL is checkable by opening it and the quotes
in the plan doc are from the rendered pages.

**AI-generated fiction is permitted and must be tagged.** The Content Guidelines
(`knowledgebase/114`, section "A.I. Content") define **AI-Assisted** and **AI-Generated** tags
and give four rules for the latter: quality must be retained and low-effort generation avoided;
no AI-generated text in reviews, comments or forum posts; the content must not violate laws or
site rules, with use "at your own risk"; and **"You must tag your story as 'AI-Generated'."** The
linked authority is an OFFICIAL POLICY blog post of 21/06/2023 (`blog/57`), which chose to allow
rather than ban on the reasoning that detection is unreliable and unenforceable rules are not
worth writing; the blog index carries no later AI-policy post.

**No discovery surface excludes AI-tagged work in the written rules.** `knowledgebase/78`
describes every list including Rising Stars and contains **no AI clause at all**; the only stated
eligibility rule of any kind is that recommendation lists need a fiction Ongoing or Completed.
The submission page (`knowledgebase/84`) puts both AI tags under **Content Warnings** beside the
mature-content ones, and the named rejection checks — plagiarism, synopsis links, fanfiction
tagging, sexual, political/religious and disturbing content, with ~10% of submissions rejected —
**do not include AI**. Advanced search lists both under Content Warnings, so readers can filter
on them. The Terms of Service (last updated 2025-03-03) carry **no AI-content clause at all**.

**Four GTM-level facts for the operator, and the launch is not blocked.**

1. **The AI-Generated tag is mandatory and is a content warning** — a fixed field in any
   packaging study, never a variable, and never omitted.
2. **No written rule excludes tagged work from Rising Stars or any list.** What the rules cannot
   settle is the *reader* discount the tag carries, which the platform's own "readers will
   decide" language invites. **That is a population effect with no measurement here and it is not
   estimated.**
3. **The enforceable clause is the quality one** — "low-effort text generation" is the named
   prohibition, with a discretionary human reviewer behind it at submission. It points at exactly
   the goal §61 already set.
4. **Two operational rails:** the ToS prohibits bots and automated access without permission, so
   a posting path is a human or an authorised integration and never a scraper; and the General
   Rules prohibit manipulating scores and rankings, which forecloses every seed-the-metrics
   tactic outright.

**Two adjacent clauses matter for the cover brief:** cover art "must relate directly to the
story", and on the good-taste exception the rules allow for borderline art, **"No such exceptions
are granted for AI-generated artwork."**

None of this changes the value of the repository work. Whether the prose earns allocation and
where a labelled book gets discounted are separate questions, and the second is the operator's.

### 104.6 Anti-scope

No claim here is a rule. No drafting, revision or planning prompt gains anything from this
programme — RS1 and §97.4's crossing rule govern, and the mined object is a restated axis. No
verdict slot, no preference leg, no new judge. No human feedback of any kind, including the
platform's follower and view columns, which are a refuted label and stay one. No D1 family is
touched and no D1P family is ever pooled with one. Serial Pilot 1 is untouched. And no D1P result
may be worded as a statement about a follow decision: this instrument measures allocation between
texts under scarcity, and the follow button is a population behaviour whose only proxy is the
label §104.3 excludes.

## 105. A repair gets many attempts instead of one, and the loop that grants them is forbidden to rank anything

**Built 2026-08-21, from `plan/handoff-variation-session.md`.** A **variation session** is a
durable, mediated, multi-attempt loop placed in front of the existing commit path, applied first
and only to candidate-local repair. Design and measurements: `plan/variation-session.md`. Code:
`domain/variation.py`, `application/variation.py`, `adapters/sqlite_variation.py`, migration 030.

**What it is for.** NVIDIA's AVO work reports that an evolutionary search improves sharply when
the variation step is an agent that inspects prior candidates, proposes an edit, evaluates it,
reads the failure and revises before anything is committed. This repository already had the other
half — immutable revisions, pure pre-commit gates, recorded decisions, a linear head, §4.2's
park-never-spin ladder — and had no multi-attempt session at all. The fixed path spends one call,
records the refusal, and lets the Conductor re-run the identical prompt; the model is never told
what happened, three times, and then the unit poisons.

**And the one thing that was not imported with it.** AVO's objective is ground truth. Ours does
not exist: nothing here is entitled to order prose by quality, and
`research/quality-measurement/BRIEF.md` is twenty refutations of the belief that something is. So
the session **optimises nothing**. It repairs to mechanical feasibility and commits the first
candidate that clears it. That is the entry's spine, and every other decision below follows from it.

### 105.1 The lexicographic bar, and the tier that is structural rather than promised

Four tiers, of which one is in play. **Mechanical feasibility** — `apply_patch`, `gates_for_patch`,
`decide`, and the day's budget, unchanged. **Non-regression on protected dimensions** — the full
gate vector is stored per attempt, passing gates included, so nothing is traded away silently.
**Pareto improvement on an authorised objective** — none is authorised. **No literary-quality
ordering** — the first mechanically valid candidate commits and the session closes.

The fourth tier is enforced rather than declared:
`test_the_variation_loop_imports_no_selection_machinery` refuses either variation module an import
of the tournament's `select_winner` or of the pairwise preference engine. There is no score column
in migration 030 and nowhere to put one. Cheaper to forbid the import than to review every future
edit for the call it would enable.

### 105.2 One action per tick, one job per action, and why the ordinal is in the job id

§4.1 fixes one bounded unit per tick, so a session that takes many actions must span many ticks.
Job ids are content-derived and `insert_job` is INSERT-OR-IGNORE; a SUCCEEDED row is terminal with
its idempotency key burned, and no code path rewrites a job's payload. **A session that minted one
job per step without a discriminator would enqueue its first step and then silently enqueue nothing
ever again.** So the step ordinal rides in the payload and therefore in the derived id — the trick
`span_select_job_id` already uses to distinguish itself from the tournament job that produced it —
and each step mints the next step's job inside the transaction that records its own outcome,
exactly as `plan_search` mints `span_select`.

**Restart safety is then a property rather than a feature.** The whole of a session's state is
rows; the prompt is re-rendered from them every step.
`test_a_session_resumes_across_a_restart_because_its_state_is_rows` drives a session with one
Conductor and finishes it with another. A reclaimed lease meets the recorded ACCEPT guard and
returns without re-spending the call.

**A session opened by a repair job takes its first action in the same tick.** A tick spent only on
bookkeeping would cost every session one more tick than the fixed path for reasons unrelated to the
loop, and §105.5's comparison would have measured that instead.

### 105.3 What a step records, and the recorded refusal this design departs from

Four tables. `variation_sessions` holds the target, six ceilings, the live counters, the
consultation links and the ending. `variation_patches` is content-addressed and holds the proposed
patch once — this is what "by reference" means here, because **there is no blob store and no path
column anywhere in this repository** — and the digest is also what the repeat-patch predicate keys
on. `variation_attempts` holds the gate vector whole, per-veto diagnostics read off
`PatchOutcome.vetoes` rather than off the flattened gate detail, and a `strategy` label that is
recorded and never enforced so that "structural early, micro late" can later be measured rather
than assumed. `knowledge_items` holds deterministic claims about repeated mechanical failure with
the attempt ids that support them.

**The departure, named because it reverses something already written down.** `spend_on` derives the
day's spend by summing decisions rather than keeping a counter, on the stated grounds that a counter
and the decisions it summarises can disagree after a crash. The session's counters are stored
anyway. The objection is exact and it is about *separate writes*: these counters advance in the
same transaction as the attempt row, the settling decision and the follow-up job, so no crash can
land one without the others — and three of them count things that mint no attempt row at all (a
lineage inspection, a knowledge consultation, an unusable response), so they could not be derived
even if the objection applied.

**Every provider call still reaches `policy_decisions`, because nothing else is visible to the
budget gate.** A loop making a dozen calls per finding whose calls never reached that table would
spend them while the day's governor reported the day untouched.
`test_the_session_spend_reaches_the_budget_governor` pins it.

**Every attempt is recorded, including the failures — and that is a departure from §72 too.** §72
records that a tournament's losers reach no rows and land as non-blocking gates on the settlement
decision, because a loser's defect made standing would park the winner's commit. The reasoning
holds and is not disturbed: an attempt row is not a finding, mints none, and is reachable by nothing
that gates prose. What it is is the record AVO's own paper discards — a committed lineage of 40
published beside 500+ explored directions that were not — and the difference between those two
numbers is the only part of a run that can ever answer why.

### 105.4 Which outcomes park, and why a refused action does not veto its own tick

A **tripped ceiling** builds a PARK decision directly with a failing blocking BUDGET gate, so
`refused_before_work` refunds the attempt and the Conductor parks the step rather than poisoning
it; the exception queue names which ceiling stopped it
(`test_a_tripped_ceiling_parks_the_session_and_names_which_one`). A **stall** and an agent **stop**
park with a passing summary gate and PARK set directly, copying the parked tournament exactly. A
**lapsed licence** settles ACCEPT and closes the session: the finding was dismissed, the work is
moot, and the fixed path already treats that as quietly completing.

**A refused action carries a non-blocking gate, and the word is load-bearing.** An unusable
response, or a commit requested for a candidate that has not passed the gates, is recorded and does
not veto the unit — because the unit of work is *one mediated action* and it executed exactly as
the surface says it should. Making it blocking would send `decide` down the retry ladder, fail the
step job and spend the Conductor's attempt budget on a bound the session's own ceilings already
hold; three of those poison the step and orphan the session, which is the one failure here with no
recovery short of an operator `revive`.

**And `revive` is the recovery that does exist.** A step job poisoned by an outage leaves the
session open with nothing queued; reviving it re-queues the very step the session stopped at,
because the step id is derived from the session and its ordinal. `open_variation_sessions` is how
the pair is seen together.

**Two gate-set facts, stated because the handoff's wording implies more than the repo has.**
Pre-commit the ladder is `shape.patch.v0` and nothing else — continuity and state are checked
*post*-commit by the `evaluate_revision` job, and a session commit schedules the same verification
and the same propagation from the same function the fixed path uses, at the same depths. And
`gate_standing` is deliberately not applied: a repair session exists *because* a finding stands, so
the standing-findings pre-flight would refuse every session on arrival.

**No new `EventType` member.** `Event.to_contract` resolves against the pinned contracts rev and
fails at insert time inside a handler. A session reuses ManuscriptCandidateCreated,
ManuscriptRevisionAccepted, PolicyDecisionRecorded, BudgetExhausted and ImpactAnalyzed. Session open
and close have no event of their own; their record is the row. Every session event payload carries
`session_id` and the attempt ordinal, because event identity digests type, revision and payload
alone and two attempts of one session against one revision would otherwise collapse onto a single
row.

### 105.5 The comparison, and it is a null result

Fifteen cases — three books crossed with five ladders — both arms drawing from the *same* ordered
generator under the same budget, differing in harness and nothing else. Full table in
`plan/variation-session.md` §4; numbers in `plan/variation-comparison.json`.

| metric | fixed | session |
|---|---|---|
| feasible commits | **9 / 15** | **9 / 15** |
| calls per feasible commit | **4.00** | **9.00** |
| tokens per feasible commit | 1,874 | 4,807 |
| actions per feasible commit | 4.00 | 9.00 |
| gate-pass rate | 0.250 | 0.400 |
| repeated-failure rate | 0.556 | 0.556 |

**The agentic path bought nothing on these cases and cost 2.25x the calls.** Three reads of that,
all of which belong beside it:

**The stall predicate stops the session where the fixed path's attempt budget stops it, and that is
structural to this benchmark.** The only mechanical veto a replacement *string* can provoke against
a small cited span is the length one, so every failure carries one signature — and
`REPEATED_FAILURE_LIMIT` is 3 for the same reason `Job.max_attempts` is 3. The session can reach no
rung the fixed path could not.
`test_the_stall_detector_stops_the_session_where_the_fixed_path_poisons` pins it, so moving either
constant fails a test and gets argued.

**The higher gate-pass rate is an artefact and must not be read as a win.** A committing session
gates the winning candidate twice — the evaluate action and the commit request — so its numerator
gains a pass the fixed path had no opportunity to record. Calls per feasible commit is the metric
with the same denominator on both sides.

**And the benchmark holds constant exactly the mechanism the session exists for.** The
deterministic fake has no capability to measure; the scripted agent uses only the *fact* of a
refusal, never its content. So this is evidence about cost and control flow and **no evidence at
all about whether feedback helps**. Asking that needs a case family whose failures carry different
signatures, and a real-provider run under the replay conventions. Neither is done. Held-out books
and length transfer are a later study and are not claimed.

**Two standing statements this touches.** PLAN.md §20.7's verdict that detector coverage outranks
further work on the repair loop is **unmoved** — a mechanism costing 2.25x for the same nine
commits is not an argument against it, and the honest reading is that this table reinforces it. And
§15's per-unit cost model, "retries/repairs amortized ×1.5–2.5 → roughly 10–20k model tokens", now
describes the **fixed path only**; a bounded session has its own call ceiling and its own
multiplier, and the numbers above are the ones to price it from.

Consequently `--variation-repair` ships **off**. The fixed path stays the default, the two are
alternative handlers for one job kind so the licence predicate and the minted work are identical on
both arms, and the arm is selectable when there is a reason to select it.

### 105.6 What a supervisor would need, and why there is not one

The stall detector **stops**; it does not redirect. Choosing a different strategy in response to a
wall is a judgment, and a variation supervisor that made it would be a new generative surface
needing containment rather than a validity licence — the shape the Director role already has to
argue. It is not built.

What it would read is now on record and nothing else would be: the attempt and evaluation
trajectory — ordinal, patch digest, strategy label, gate vector, veto signature, cost, outcome —
plus the knowledge items derived from it. That is why `strategy` is stored and unenforced, and why
the gate vector is stored whole rather than summarised. It may never touch prose, canon, locks,
gates or budgets, and it would sit above the loop rather than inside it.

### 105.7 Anti-scope, carried forward

No general prose hill-climbing, and no selection among mechanically valid candidates by any quality
proxy, score, ranking or preference signal — enforced by an import ban, not by intent. No new
quality or craft metric. Context-packing search is the next objective target and is not started
here; it waits on the gold suite growing binding-budget, long-book, evaluate and repair cases.
Reward-guided prose selection stays behind a simulated-readership force clearing its own controls
plus held-out validation, and is nowhere near this. The Director and every narrative-role module are
untouched; the variation supervisor is a distinct future component and not a Director variant. §95's
scope axiom is unchanged: nothing built here solicits judgment from anyone and no human data enters
any loop. `variation_step` is deliberately **not** in `PLAN_DERIVED_JOB_KINDS` — a repair session is
licensed by a finding, not by a plan alternative, and `repair_finding` is not there either. No claim
is made from the comparison beyond the mechanism it measured.

## 106. A method exists for correcting the simulated readership against what the population did, and the decision that would license it has not been taken

**Registered 2026-08-21, before any book of this project's has a retention curve and before the
question below has an answer.** A second research extraction landed: SYN-DIGITS (arXiv 2604.07513,
Columbia, April 2026), a post-hoc calibration framework for LLM persona simulations. It stacks a
real response matrix on a simulated one and treats the sim-to-real gap as a synthetic-control /
matrix-completion problem. The design registration is
[plan/sim-readership-calibration.md](sim-readership-calibration.md); this entry carries what is
being registered, what is prohibited, what is gated, and what triggers revisiting.

**Nothing is built and nothing is proposed to be built.** No code, no schema, no table, no number.
This is a registration and a set of constraints on work that may never be authorised.

### 106.1 The routing decision, taken first because it was the hard part

The material belongs to §97's programme — the readership is the reward model, the population
through the library is the settlement layer, and G5 is *"sim forecasts against real telemetry."*
This is G5's **return leg**, and it had no home. Four candidate homes were read in full and each
refused it for a different reason, which is what makes the vacancy real rather than a filing
preference:

- `plan/machine-taste-program.md` is **RETIRED** at its own line 3 — *"Nothing below may be
  executed"* — and §104.4 has already refused an additive scope note there on the grounds that it
  *"would have extended a closed channel."*
- `plan/judge-validity-program.md` is judge-side, and §97.4's *"no verdict slot exists anywhere in
  a sim"* makes a sim-calibration section there a re-welding of the roles §87–§89 separated.
- `plan/force-program.md` excludes the object constitutively: a force is obtained *without asking
  any model a question*, and a persona sim is nothing but asking a model a question.
- `plan/persona-reader-validity.md` says the objective in the right words — *"the datum is always a
  distribution, so aggregation is distribution-matching and never averaging"* — but it predates the
  scope axiom by a day. The string §95 appears in it zero times, its §6 still specifies a paid human
  panel and its §10 still calls that *"the first line item that pays humans."* Seating a 2026-08-21
  registration whose entire argument is that it solicits nothing two sections above a budget for
  solicited labels would put the contradiction inside the home.

**And the ordering rule is the filing rule**, which is the argument that actually decided it.
Calibration sits above instrument validity; instrument defect-hunting stays upstream. Filing the
layer that must stay downstream one heading below the gates that must stay upstream is how an order
of operations gets lost. So a new companion doc under §97 — the shape `plan/anchor-set.md` already
is — and it is not a second home for one question but the first home for the question above it.

### 106.2 The mechanism, and the half that is closed twice over

**Individual-level calibration is the paper's headline and is unavailable to this project.** It
predicts a *named person's* response to a new item from that person's responses to past items plus
the sim's, for up to **+50% correlation** over uncalibrated simulation. It needs solicited
per-person response rows, so §95 closes it — *not hired, not operator, not one blinded pair*. And
RoyalRoad exposes aggregates and never per-reader rows, so there is no column to read. **The second
closure is the one worth recording**: an axiom can be argued with by a later session and a missing
column cannot.

**Distributional calibration survives.** It needs only marginal distributions per item: reweight
the *n* simulated personas plus *K* degenerate always-one-answer members — which is how the
ensemble is guaranteed full support — on the probability simplex by mirror descent, until the
ensemble's distribution matches the observed marginals on past items, then read the new item's
distribution off the reweighted ensemble. Reported: **50–90% reductions in distributional
divergence**, TV and KL the most robust objectives, error decomposing into an irreducible
reweighting gap plus a term of order `sqrt(K/n)` that degrades as the new item leaves the span of
the past ones. Retention curves, follow counts and rating histograms are marginals, and they are
unsolicited by construction.

**The number that reframes the method, and it is a control rather than a headline.** Handing the
simulation 249 ground-truth ratings in context bought **+16%**; calibration bought **+50%**. The
sim's error is a systematic displacement of its output distribution and not a shortfall of
evidence, so **prompt enrichment is the weaker lever** — which contradicts the instinct this
project reaches for first whenever a reader model underperforms.

**One coincidence worth not mistaking for a design.** The distributional variant is defined for
structured or categorical responses; free-form text is open. §97.4 independently fixed the sim
vocabulary as *continue, abandon, return* and abolished the verdict slot. The admissible half of the
method happens to require exactly the response type this project had already restricted itself to,
for unrelated reasons.

### 106.3 The gate, posed and deliberately not closed — and the two §97 clauses that disagree

Whether the settlement layer may correct the reward model is **an unmade decision**. The README
constrains the *operator*, who *"trains, calibrates and selects nothing"*; that sentence says
nothing about the population. §97 is not silent, and the trouble is that it points both ways:

- **§97.5 reads as licensing it and fixing its cadence** — *"sims update only between cycles, from
  new unsolicited data, and never from the writer's outputs within the cycle they are judging."* A
  reweighting against platform marginals is a between-cycle update from new unsolicited data.
- **§97.2 forbids the same shape for a different source** — *"The permission is to **read** the
  comparison; the prohibition is on **feeding it back**."* Its stated reason, that tuning the sim to
  an operator trace *"would have quietly made one person the reward model"*, does not transfer to a
  population. The reason does not, but the shape does: G5 is a comparison and reweighting is
  feeding it back.

**The narrow question, which is the contribution of this entry:** *does correcting the reward model
against settlement marginals count as §97.5's permitted between-cycle update, or as §97.2's
prohibited feeding-back of the settlement comparison?* Nobody has reconciled the two clauses; this
entry poses the question and does not answer it, because answering a §97 ambiguity from a companion
doc is not how anything here has been decided.

**Trigger for deciding it, declared now so it is not decided by drift: books of this project's are
live on RoyalRoad with real aggregate data accumulating against them.** Before that the input set is
empty, which is why the deferral costs nothing and adds no line to §97's cost table — and it is also
why the question cannot be answered well today: nobody yet knows which marginals a serial of ours
will actually expose, and a rule written against imagined columns is a rule written against nothing.

### 106.4 Calibration sits above instrument validity, and this repository has already measured why

**Reweighting a channel with a known defect calibrates noise.** Three measurements, all in hand:

- T0's verdict channel carried a positional bias of **0.8151** over 568 decided comparisons. Fit its
  marginals to a population and it will match them while still answering a *side* — a defect that
  has acquired agreement with the data.
- §94.6 is sharper. `qwen3:14b` returned `ABABABABABAB` in all six sessions, `gemma3:12b` returned
  `AAAAAAAAAAAA`, and **"both fixed-pattern readers would have passed every declared control."**
  Constant behaviour survives placebos, shams and positional checks. It also fits marginals
  beautifully.
- §95.15's class — *a guard that ran, produced a value, and had no path to a verdict* — is what a
  calibration layer becomes if it is added before the instrument beneath it can fail.

So instrument defect-hunting **stays upstream**: §94.6's preconditions, `llm-reader-engagement.md`
§A3's battery and §97.7's G1–G3 clear before any weight is fitted. A calibrated broken instrument is
strictly worse than an uncalibrated one, because it has gained agreement with the data and lost the
disagreement that would have exposed it.

**And the Goodhart caution, which is separate from all of that.** The paper's guarantee is
*predictive*, not optimisation-robust. A reward model calibrated to aggregates and then optimised
against is a proxy of a proxy, and §61's α discipline applies unchanged — as does §97.5's
containment, T3 instrumentation and the frozen-per-cycle rule. Calibration buys accuracy against
observed marginals; it buys no protection at all from pressure applied afterward.

### 106.5 The constraints that bind now, because four of the five cannot be retrofitted

Recorded here because they are cheap today and expensive or impossible after the fact, and they hold
whether or not §106.3's gate ever opens:

1. **Per-reader × per-item responses persist in matrix-completable form.** A readership storing only
   pooled statistics would have to re-run every simulation to obtain a response matrix, which on
   §94.6's substrate is GPU time nobody budgeted.
2. **The sim and the settlement layer must be made to answer the same item — and today they do
   not.** The BCR's datum is an allocation share *between two texts* under a forced budget; a
   platform marginal is retention on *chapter k* of one text. Different item spaces, and a matrix
   cannot be completed against columns that mean something else. This is the constraint the other
   four assume, it is the one that can silently fail, and a fit obtained without declaring the
   mapping first would be an artefact of the join.
3. **The degenerate members are fenced, and this is the constraint the source material does not
   see.** *K* always-one-answer members are how the method guarantees support — and in this
   repository that object has a history: it is exactly the fixed-pattern reader §94.6 killed two of
   four candidates over, and the text-blind constant that took **0.8804** of a promoted ensemble in
   §97.5 before the market was repaired. So their total fitted weight prints beside every headline
   and is never folded into it; a fit in which they carry the majority of the mass is a **refusal
   state and not a result**; and they are support machinery, never counted as personas and never
   merged into the panel-size arithmetic.
4. **Ensemble concentration is standing health reporting**, not a diagnostic somebody runs when a
   result looks wrong — predicted-variance over true-variance, two-sided, with a declared refusal
   state for the case the denominator is zero, which this project has already measured (195 of 196,
   *"every variance statistic undefined rather than failed"*).
5. **A correction that cannot refuse is not accepted.** Every learned correction ships with an
   in-span diagnostic and a raw fallback. This is §97.7's G3 one layer up — *"a sim that always has
   an answer is measuring its own noise"* — and the paper's own evidence is that the refusal is
   where the value was: adaptive transfer **doubled** the gain, 19–21% to 50%.

### 106.6 What is declared, what is refused, and the bar that is deliberately absent

One bar is stated now, because it is a statement about a diagnostic's own behaviour rather than
about an effect size: **the fallback rate must be strictly between 0 and 1** on the set the
correction is applied to — a dimensionless share, two-sided, both endpoints reachable and both
already reached in this repository's history. At 0 the diagnostic never refuses, which G3 calls a
failure; at 1 the layer is inert. It is reported decomposed, because
`persona-reader-validity.md` §1 measured that *"wouldn't answer", "answered in the wrong format"*
and *"answered differently"* are three failures and the middle one is a property of the transport.

**No divergence-reduction bar is stated, and the omission is the point.** The 50–90% figure is
theirs on their task; no σ exists for any response distribution of this project's. Worse, a
percentage-reduction bar **gets easier the weaker the raw arm is** — which is exactly what §106.7's
equalizer says happens — so it is clearable by degrading the baseline. If a bar is ever stated it
goes on the calibrated *absolute* divergence with the raw printed beside it, against the baselines
§97.5 already seats: the coin, and the text-blind constant. **This is §101.4's pattern unchanged:
the σ comes first and the bar is signed after it**, because inventing a bar and then discovering
whether it was reachable is the failure §87's rulebook exists to prevent.

Three traps in the marginals themselves are recorded before anyone reaches for them: at the measured
population (median 1,245 views at 98 days, median 5 followers, 22.3% ever clearing the 10,000-view
floor) a launching serial's marginal has almost no mass, and restricting to serials that clear the
floor is a collider rather than a filter; a follow-derived marginal is orderable by size rather than
by prose, since the deciles are recoverable from follower count alone at **AUC 0.814** (§56.3); and
retention is informatively censored, with only **43.0%** of shard-3 LitRPG fictions publishing
anything in days 30–60, so a statistic computed on survivors measures survival.

### 106.7 The equalizer, recorded as a decision input and not as a claim

Calibration compressed the paper's model spread from baselines of **.048–.205** to **.204–.243**,
and **reordered** them: the best raw model was not the best calibrated one, and their fine-tuned
simulation went from worst raw (.048) to best calibrated (.243). If that transfers, **cheap personas
plus a correction layer may dominate expensive personas run raw**, which is a real input to the
force programme's model-choice economics and contests `llm-reader-engagement.md`'s working premise
that the frontier ordering is the reference.

Recorded as an input, not a claim. The numbers are theirs on their task, and this project has twice
measured that a model ranking does not transfer — §94.6 killed two of four candidates on a control
absent from the design, and §97.5's market ranked stated confidence until it was repaired. **No seat
is reopened on it**, and a calibrator that reorders models must not become a reason to reopen model
selection after the marginals have been read.

### 106.8 Anti-scope

No code, no migration, no table, no fitted anything — no mirror descent, no reweighting, no
calibration implementation. `research/quality-measurement/`, the pools, preference and judge stores,
and provider code are untouched by this entry and by its companion doc. No new quality or craft
metric. **No individual-level calibration, ever**, on either of §106.2's two closures. No RoyalRoad
scraping, collection, polling or account activity of any kind — no live data path exists, terms of
service are unread and unpriced, and fetching the site directly is an operator decision rather than
an implementation detail. Nothing here solicits judgment from anyone (§95) and no human data enters
any loop. **§106.3's gate is not closed by this entry and may not be treated as closed by anything
citing it.** No licence moves: FORECAST stays at STORY grain, absent from `veto_for`, and a
calibrated sim earns exactly what an uncalibrated one earned until an entry says otherwise. §97.8's
anti-scope stands whole and is extended by none of this.

---

## 107. The serial gets a world that exists behind it, and the detector that was supposed to check it was reading the annotation

**Built 2026-08-21, from [`plan/world-architect.md`](world-architect.md), which was written before
any code in this design and before any world was generated.** A fourth role, **the Architect**,
upstream of the Director: it says what the world *is*, never what the book is about, never drafts,
never judges. Code: `domain/worlds.py`, `application/architect.py`, `litharness forge`, plus the
projection and the `hidden` packet section in `domain/context.py`, the cardinality detector in
`domain/integrity.py`, and the second extractor family in `domain/extraction.py`. Ontology:
[`plan/state-model-abilities.md`](state-model-abilities.md) and
[`research/progression-generalization.md`](../research/progression-generalization.md), built *to*
rather than replaced.

**Nothing above this entry was renumbered.** §106 was the last section when this began and the
check was run again across every branch, every remote ref and every working tree on this machine
before this was written; no §107 existed in any of them.

**What licenses it is a count, not an ambition.** Measured against `serial.db`, the live nine-scene
serial, on 2026-08-21:

| | count |
|---|--:|
| canon state records, the whole world model of the book | **23** |
| — typed by the operator into `plan/serial-pilot-seed.json` | 15 |
| — written by the loop itself (`status_snapshot`, `litharness.systemvoice.v0`) | 8 |
| records carrying an edge (`object_ref`), every one of them operator-typed | 7 |
| promises open / paid | **40 / 0** |

The Advent, the tiers, the Tide, Marta, Vance, the assay house, the crown-and-hook mark: every one
of them is in the prose of a book whose canon has never heard of it. **That is the entry's spine.**
The eight records the loop wrote are eight readings of one line form, and `src/` contained no code
that constructed an edge at all.

### 107.1 The detector was not backwards on edges; it was blind to them, and it keyed on the annotation

`plan/state-model-abilities.md` §2 records `detect_contradictions` ignoring `object_ref` and gives
three cases. Re-run against this repository — the probe is now
`tests/test_worlds.py::test_the_edge_cases_the_design_note_measured` — **one of its rows is wrong**,
and the correction is written into that document in place rather than folded away:

| what the book says | how it is spelled | findings, before |
|---|---|--:|
| `card_of_ashes held_by → silas` and `→ marta` | edge, no value | **0** |
| the same, each edge annotated differently | edge, different values | **1, MAJOR, blocking** |
| `ash trait → keen_scent` and `→ night_sight` | edge, no value | **0** |
| `ash trait = keen_scent` and `= night_sight` | value, no edge | **1, MAJOR, blocking** |
| `card_of_ashes held_by = silas` and `= marta` | value, no edge | **1, MAJOR, blocking** |
| `silas status_snapshot {loop 1, day 1}` / `{…day 2}` at `s1` | value | 1, MAJOR, blocking |

The design note gives row 3 as **1, MAJOR, blocking**; it is **0**. It did not record which
spelling it measured and the two are not the same case. The generalisation gets stronger rather
than weaker: what decided whether an impossibility was reported was **whether the prose happened to
annotate the two edges differently**, and a perfectly ordinary two-valued relation was refused
whenever it did.

**The fix is a pair and would be wrong as either half.** `object_ref` enters the grouping key, so
two edges are two facts and never contradict each other there; and `state.cardinality.v0` reads a
world's own declared shape — `research/progression-generalization.md` §8.2's five-record encoding,
unchanged — so exclusivity becomes a thing a world *says*. The key alone would make one object in
two hands permanently invisible. **Undeclared means unchecked**, and the price of that safe
direction is stated rather than hidden: a world that declares no shape is checked for nothing.
Maxima only; under open-world reading a missing value is unknown rather than false, so a minimum is
unsafe until a scope is closed and none can be. Both golden fixtures hold **zero** records with
`object_ref` set, so their silence is untouched by construction —
`test_both_golden_fixtures_stay_silent_under_the_new_key` asserts the data rather than assuming it.

### 107.2 Record patterns, not schema classes — and no migration

Everything the Architect writes is `(subject, predicate, value, object_ref, story_position,
authority, pov_visibility)`: the shape the contract already has, which `record_json` already carries
whole. No new `StateRecordKind`, no migration, no contracts bump. The vocabulary is the research's,
spelled as it spells it — `evaluation.subject`, `claim.content`, `disclosed_to`, `precedes`,
`group_key` — and the three predicates this repository adds (`entity_role`, `consequence`,
`manifests_as`) each exist because a counter has to find the thing.

**Absence is free and it is enforced rather than intended.** Nothing requires a world to declare a
system, a criterion, a rank, a number or a creature. `Coverage.share` returns **1.0** for a world
that declared nothing, because "declared nothing" and "declared everything and showed none of it"
must not be the same number.

### 107.3 The projection, which is the item most likely to have been skipped

`state.describe` renders `subject predicate value (object_ref)`. That is right for a flat fact and
is machine notation for a reified one, and this project's quality runs entirely through what the
generator is handed — so adopting the ontology without a projection would have made canon checkable
and the prompt worse. `worlds.project` returns one English sentence per record it recognises, folds
a reified node's satellites into the node's single sentence, and returns **nothing at all** for a
record it does not know, so `state.describe` remains the fallback and a book that declares no world
packs byte-identically. A node with any restricted satellite is never folded: collapsing a fact
about who knows what into a sentence written for everybody would leak it.

### 107.4 The iceberg is a claim with a disclosure, and it is not `pov_visibility`

A new packet section, `hidden`, between `facts` and `summaries`: *true, and the reader has not been
told — write as if it is true and never put it on the page*. A claim with recorded content and no
`disclosed_to` at or before the current position is hidden; a reveal moves it, and a reveal changes
disclosure rather than past truth.

**`pov_visibility` could not have carried this and the test says why rather than the document.** It
is packet *access control*: a secret written into it reaches no packet at all when no POV is named,
so the one thing the writer most needs to honour would be the one thing it is never told
(`test_pov_visibility_is_not_how_a_secret_is_carried`). §0.1 row 2 forbade the overload; this is
what the alternative had to be.

**A modelling error the test suite found rather than the design.** The first version of this
vocabulary had a character's false belief and a mystery's answer sharing one predicate, and
`validate` caught it by demanding a scheduled reveal for a belief that must never have one. Two
consequences, both kept: `claim.false` marks a claim the world denies, so a character's error is
never carried under a heading that says *true*; and only a claim that **asks** something owes a
disclosure position, so a secret somebody keeps is not turned into a reveal the book must schedule.

### 107.5 The forge: K worlds in one call, gated, and then stopped

`litharness forge "<brief>" --k 3 --shape direct|domain_first --out <dir>` makes one structured
call, refuses a collapse deterministically, writes every candidate with its counters, records a
decision carrying the candidate count, and **stops**. `forge --out <dir> --pick <n>` is a separate
invocation that makes no provider call, records its own decision with `VerdictSource.HUMAN`, and
writes the seed, directives and promises `new --state … --promises …` consumes unchanged.

**No model orders the candidates**, enforced by import ban rather than by intent —
`test_the_architect_ranks_nothing_and_cannot_learn_to` refuses the module an import of
`select_winner`, the pairwise engine, the judge panel or `plan_search`, and refuses the strings
`select_winner`, `win_rate`, `PairVerdict` and `Calibration` anywhere in it. §105.1's device applied
to the role that would be most tempting to give a taste. §61(5) then divides the confidence level by
the candidate count, which is why the count is on both decision rows.

**The collapse gate is stricter than the one it is modelled on, and says so.**
`plan_search._alternatives` compares whole statements for exact equality after casefolding, which
cannot catch a re-worded collapse — a limitation its own docstring claims to prevent and does not.
Here the axes are *declared*: two worlds naming the same real domain, or the same geometry, are
refused before a scene is paid for. It is still not semantic, and a model writing "coopering" beside
"barrel-making" defeats it.

**Per-candidate gates, all four arithmetic or membership over the structured answer.** A declared
rule must reach **three distinct domains of life** (`CONSEQUENCE_FLOOR`, and it is the operator's
figure taken as given rather than measured — recorded as chosen so nobody later quotes it as
measured; what makes it safe is that it gates one of K rather than a serial). Every declared feature
must say how it shows on the page. Every mystery must record an answer and a scene. And nothing in
the answer may compare itself to something outside it — a **structural** RS1 guard that names no
work, because a deny-list of titles inside a generation-side module would put named works into the
generation path, which is the boundary §97.3 draws and the one this project has walked to the edge
of once. A vocabulary guard is not comprehension; the prompt carries the rule as well.

### 107.6 Measurement, pre-registered before the pilot

| # | quantity | range | direction | unit |
|---|---|---|---|---|
| M1a | within-forge spread over K | [0, 1] | reported, **no bar** | normalised compression distance |
| M1b | between-shape distinctness, `directors.distinctness` | reading | between > within | the same distance |
| M2 | genre-lexicon overlap of a world's key nouns | [0, 1] | reported, **no bar** | share of key nouns |
| M3 | consequence domains per declared rule | [0, 8] | ≥ 3 to pass the gate | distinct domains |
| M4 | manifestation coverage over declared features | [0, 1] | 1.0 to pass the gate | share of features |
| M5 | integrity findings per accepted scene | [0, ∞) | reported | findings |
| M6 | disclosure-schedule adherence | [0, 1] | reported | reveals inside their window |

**M1 is two readings and only one of them is a distinctness.** K worlds from one call share a
source, so there is no within-source floor to clear and the number can only say how far apart this
call's answers landed. The reading that *is* a distinctness is between the two prompt shapes, with
the shape playing the role the director plays in §89's control. `DISTINCT_NO_FLOOR` is a real
outcome here and must not be reported as `DISTINCT`: the pinned provider is greedy, and a control
which cannot fail is not a control (§50).

**M2 has no bar, and the reason is a case this repository already owns.** `opening_proper_nouns`
was nominated for a named reader defect and then placed the complained-about chapter at the
**68.5th percentile** of published LitRPG openings — it did not discriminate the defect it was
built for. So the K candidates' overlap distribution is reported first and no ceiling is declared.
The lexicon is built by `research/quality-measurement/world_lexicon.py` from the `description` and
`tags` columns of the twelve cached RoyalRoad shards: **22,397 fictions**, blurb vocabulary
**79,379** words, lexicon **17,541** at a document floor of 5, tag vocabulary **82**. The floor's
effect is reported beside the headline (1 → 79,379; 2 → 33,086; 5 → 17,541; 10 → 11,455; 25 →
6,510; 100 → 2,421) because a floor is a way of quietly deciding the answer. **The measured
distribution is in §107.9, and the counter's own bug is reported beside it.** **No code in this
repository had ever read the `description` column**; `corpus_io.royalroad_chapters` requests twelve
columns and that is not one of them. It enters a counter and never a prompt.

**M5 and M6 are fidelity, not quality.** Nothing here claims a forged world produces a better book.
Reader effect reaches this programme only through §97's readership sim and the operator's `NOTES.md`
harvest; anything else is a hypothesis and is labelled one.

### 107.7 The world grows, and the promotion rule is deliberately the narrow one

A second extractor family. The book declares its own graph line the way it already declares its
sheet — a label plus a phrase → predicate map, so the printed line is the book's own words and the
parse is exact — and **a book that declares none extracts no graph facts at all**. That is
`research/progression-generalization.md` §14.3 honoured rather than dodged: a rigid *hidden*
extraction format is useful and a rigid in-story status line is not the general abstraction, so the
in-story form is a per-world declaration instead of a constant.

Identity minting and factual promotion are separate. The page may **name** a new subject; the claim
arrives `PROPOSED`, reaches no packet and takes no part in the contradiction detector. Repetition
promotes nothing, explicitly — §6 item 1 rejects it as evidence. An edge is promoted when a
**later** scene names one of its endpoints under a **different** predicate: the book came back to
the thing and did something else with it. Promotion mints a new canon record at the later position
rather than editing one, because `record_state_records` is `INSERT OR IGNORE` and there is no
update path — and because the new row is the truer statement. It cannot tell causal reuse from
coincidental co-occurrence and does not claim to; what it buys is that a fact the page invented and
never touched again stays out of canon.

### 107.8 The ledger finally has something to pay with

**40 promises opened and 0 paid** on the live serial; 32 and 0 before it. Every one was opened by
the summary handler out of a scene that had just been written, and nothing anywhere held the answer.
A forged reveal arrives with its answer already in canon and its scene attached, and
`new --promises` opens it before scene one — keys taken from `beats_for` rather than from a format
string, abstaining entirely when the template is not chronological. It also makes `open_promises`
non-empty at the book's *first* outline, which is the guard that made `_payoff_windows` unreachable
on pass one. Whether the loop then *pays* any of them is the pilot's question and is not claimed
here.

**One limit, stated rather than discovered later.** `promises.model` is empty on a seeded row and
the ledger has no column that distinguishes an authored debt from a model-asserted one, so
`promise.overdue.v0` keeps reading every row as model-sourced — which is why it is MINOR and
`heuristic` and may not block. A seeded row rides an instrument that documents itself as
model-sourced, and that mismatch is real.

### 107.9 What ran, what it measured, and the eleven defects running it found

The suite goes **1,247 → 1,338** collected (the upper figure after merging main, which brought its own tests), all passing, with `ruff check .` and `mypy --strict`
clean.

**Three live forges on the pinned provider, `claude-opus-5`, one structured call each.**

| run | shape | scene count in the prompt | tokens | cost | clear of every gate | within-forge spread |
|---|---|---|--:|--:|:-:|--:|
| 1 | `direct` | absent | 91,561 | $1.37 | 2 of 3 | 0.9189 |
| 2 | `domain_first` | absent | 96,447 | $1.48 | 3 of 3 | 0.9053 |
| 3 | `direct` | 8 | 98,332 | $1.53 | 3 of 3 | 0.9302 |

**$4.38 for nine worlds.** Every one of the nine conformed to the schema on the first call; the
collapse gate refused none, because all nine declared pairwise-distinct real domains and
geometries within their run. What came back is the shape the design asked for and had no way to
guarantee: field epidemiology as contagion-of-capability, celestial navigation where a position is
a guess that grows, clonal grafting where a talent is a cutting taken from someone still bearing,
saturation diving against salvage law, musical temperament where the comma has to be *put*
somewhere, transplant immunology, and prior-appropriation water law where the river answers a date.

**Per world, run 3 — the one Serial Pilot 2 runs on:** 327 / 345 / 324 records, 76 / 79 / 72
edges, 7 / 7 / 6 rules every one of them reaching **≥ 3 distinct domains of life**, manifestation
coverage **1.00** on all three, 28 / 31 / 27 claims with recorded answers, six mysteries each and
one or two of them landing inside the eight scenes (4 and 7; 5; 3 and 8).

**Nothing in `src/` had ever constructed an edge.** A single forge now writes 72 to 79 of them —
and that count predates the `relationships` field, added afterwards so a cast's ties (who owes
whom, who employs whom, who blames whom) land as edges rather than as prose. The pilot's world
was forged before it and therefore does not carry them.

**M1a, within-forge spread:** 0.9189, 0.9053, 0.9302. Reported, no bar.

**M1b, between-shape:** `DISTINCT`, within **0.9121**, between **0.9205**, draws 3, comparable.
**Read it as a null.** The margin is 0.0084 against a within-shape floor of 0.91, and both numbers
sit where normalised compression distance saturates over 300-record JSON — the instrument may
simply lack the resolution to see a prompt-shape effect at this granularity. That is the
repository's standing prior about instructed variation arriving on schedule rather than a
surprise, and neither shape is kept over the other. `direct` is used for the pilot on a
**usability** ground and it is not a quality claim: `domain_first` returns a paragraph of real
constraints in the `domain` field, which is what it was asked for and which makes the operator's
K-world report unreadable.

**M2, genre-lexicon overlap** — measured on **run 1's** three worlds, against 22,397 RoyalRoad
fictions (12 cached shards, blurb vocabulary 79,379 words, lexicon 17,541 at a document floor of
5, tag vocabulary 82):

| | Everyone You Have Touched | The Bare Wrist | Nothing Comes True From Seed | median |
|---|--:|--:|--:|--:|
| as registered | 0.597 | 0.725 | 0.662 | 0.662 |
| after the counter bug | 0.658 | 0.756 | 0.654 | 0.658 |

Both rows are on the record because fixing a counter after seeing its answer is the failure
`platform_priors.py` freezes its matchers to avoid. **No bar, as registered.** What the coined
side actually holds after the fix reads like invention — *beodh, faske, dunnel, marnhal, ashwell,
dorrow* — and before it held `not`, `from`, `one` and `read`.

**The packet, which is the number a longer serial will be planned against.** The pilot's
329-record world assembles into a scene-one packet at **6,731 tokens of a 16,000-token budget
with zero omissions**, and **13,031** at scene eight with all seven prior 900-word scenes present.
The world is a flat ~46% of what the packet can hold and does not grow with the book; prose does.
At the **6,000 default it does not fit**: 139 of 231 facts, **no prior prose at all**, 99
omissions — and all 18 hidden claims surviving, because the iceberg packs above the facts.
`--context-budget 16000` is a precondition for a forged serial rather than a tuning knob.

**And the live packets say the world is not what fills the budget.** Across Serial Pilot 2's eight
drafting prompts the world holds flat at 229–231 facts while the **threads section grows from 6 to
41** — one row per promise the summariser opens — and the prompt runs 9,052 → 14,443 tokens with
prose stopping at three prior scenes from scene four onward. **`context_omitted` is 0 for the whole
book on both runs**: what would not fit as prose arrived as summary. So §101.2's question has a
number and it is not the expected one — the packet runs out somewhere around **scene ten**, and the
thing filling it is a ledger nobody prunes. `plan/world-architect.md` §5.1 carries that as the
retrieval design note, and it now recommends a ledger policy before a world retriever.

**Serial Pilot 2 ran twice, eight scenes each, and the first run's defect is why there are two.**
*First In Time* — a valley where the river answers a date, a right dies after five years without a
recorded use, and the only ladder available to the protagonist is built out of other people's
vacancies. 327 records seeded as canon on the pick (329 after defect 10's fix), 6 promises opened
before scene one with their answers already in the store, 12 directives — 6 forged and 6 standing
craft constraints carried from pilot 1, two with a recorded edit because their wording named
Reappraisal's own nouns.

| | run A | run B |
|---|---|---|
| ticks / jobs | 72 / 46, all succeeded | 53 / 46, all succeeded |
| decisions | 21, **every one ACCEPT** | 21, **every one ACCEPT** |
| invocations / tokens / cost | 12 / 743,603 / **$5.67** | 12 / 753,551 / **$5.89** |
| scenes, words | 8 of 8, 7,579 | 8 of 8, 7,812 |
| parked, poisoned, unattributed | 0, 0, 0 | 0, 0, 0 |
| `context_omitted`, whole book | **0** | **0** |
| findings | 5, all `promise.overdue.v0` MINOR | 5, all `promise.overdue.v0` MINOR |
| promises | 41 opened, **0 paid** | 47 opened, **0 paid** |
| the gate | fails on a pilot-1-shaped read-back check | **exits 0** |

**Four of the five pre-registered questions answered.** The world reaches the writer — scene one's
frozen prompt carries 229 facts, 20 hidden claims, 6 owed threads and 14 locked constraints at
9,052 tokens, with both criteria and their ladders in the system message. The integrity gate stays
quiet on a forged world: **zero `state.contradiction.v1`, zero `state.cardinality.v0` against three
declared shapes**, and the only five findings on either book are defect 9's clamped arc debts.
And the disclosure schedule holds *mechanically*, which the payloads show scene by scene: run B's
hidden count is 20, 20, 20, **19**, 19, 19, **18**, 18 — dropping exactly at scenes 4 and 7, the
two the world scheduled, and at no other. Run A's is 18 → 15 and was already two short at scene
one.

**The fifth is a null and it is the most useful thing in the pilot. 41 opened and 0 paid; then 47
opened and 0 paid.** Six debts existed before scene one with their answers already in canon, and
two were disclosed to the writer at the scenes they were scheduled for. The summariser still paid
none and opened 41 more of its own. **So the missing answer was never the binding constraint:**
`promises_paid` comes out of a per-scene summary call that is not told which debts are due, and
seeding the ledger does not reach it. §61's rule is that a pre-registered null is a result; this
one names the next question exactly. Package, pre-registration and both run records:
[`plan/serial-pilot-2.md`](serial-pilot-2.md).

### 107.9.1 Eleven defects, every one found by running the thing rather than by reading it

Listed because the ratio is the interesting part: **six were found by the live provider, the
pilot or a measurement, four by the test suite, one by the merge**, and none by review.

| # | found by | what it was |
|---|---|---|
| 1 | the suite | A cast member's false belief and a mystery's answer shared one predicate, so `validate` demanded a scheduled reveal for a belief that must never have one. Fixed by `claim.false` and by owing a disclosure only to a claim that **asks**. |
| 2 | the suite | Forged records stay `PROPOSED`, and `assemble` filters proposals out — so a seeded world would have reached no packet at all and the role would have been **inert and quiet about it**. `forge --pick` is now the one exit to canon. |
| 3 | the suite | Every scheduled answer sat in the *facts* rather than the hidden section, because the live drafting path passes no story-time cutoff and `at=None` read as "already disclosed". Fixed by `disclosure_at`, a coordinate for the reveal schedule that is deliberately **not** the record-slicing cutoff. |
| 4 | measurement | The hidden section packed *after* the facts, so at the 6,000 default a forged world put 183 facts in the packet and left **every recorded answer entirely out of it** — each omission dutifully recorded and none of them the one that mattered. The iceberg now packs above the facts and renders below them: at the same budget the same world keeps all 18 hidden claims and drops 92 facts instead. |
| 5 | the provider | The RS1 guard's bare `\bfranchise\b` refused **2 of 3** `domain_first` worlds on ordinary legal English — a port whose franchise is the vote, a ward surrendering its franchise. `directors._CRAFT_INSTRUCTION`'s recorded failure in a third costume; narrowed to require a capitalised title. |
| 6 | the provider | `key_nouns` counted sentence-initial words as coined names. Both figures reported above. |
| 7 | the provider | The forge was never told how long the book is, so one world scheduled all four answers at scenes **17, 25, 33 and 41** — right for an open-ended serial and useless for the two chapters being written, which would have opened four debts and paid none. **The 40-opened-0-paid defect reproduced by the machinery built to fix it.** The count is in the prompt and a gate checks it. |
| 8 | the provider | Asked for a printed line form, one world returned `graph_line.label` = "one dry season in the Kettle Basin" and eight "phrases" that were clauses of a story. Well-formed JSON, accepted by every type check, and **a parser that could never match anything a scene would print** — `MalformedSheet`'s silent failure one family over. Shape bounds now refuse it, and because a graph line has no default behind it, a bad declaration degrades to absence and `cmd_new` says so rather than raising into the draft path. |

| 9 | the pilot | An arc reveal scheduled at scene 41 was **clamped to the last beat** of an eight-scene opening, so `promise.overdue.v0` would have annotated four debts as late in a book that was never going to reach them. `Promise.due_key` is `str | None` and `overdue_promises` skips a row with none, so the honest encoding already existed: the debt is on the ledger and reaches the packet as owed, and nothing calls it late. |

| 10 | the pilot | **The reveal schedule was in a different key vocabulary from the book's own, so the iceberg leaked in exactly the wrong direction.** `beats_for` mints `s1…s8` for an eight-scene book — width **one** — while the Architect minted `s04`, `s41`, `s92`. Order keys compare lexicographically, so `"s1" > "s04"`. Measured on the run: **both answers the opening existed to keep were handed to the writer as established fact from scene one**, and by scene eight five of six were, an arc answer six chapters out drifting into the facts at scene five. Nothing raised; the strings compared fine. Fixed by minting positions in the book's own width and by minting **none at all** for a scene the book does not have — the ordinal lives under `worlds.REVEAL_SCENE`, so a serial's later answers are recorded and permanently hidden here rather than clamped. |

| 11 | the merge | **Neither side of this one was wrong alone.** A parallel session landed `OWN_POSITION_VERSIONS` — registry versions whose order keys this system's own planning placed, and which therefore are not evidence that a book has an author's story vocabulary — after measuring that one undeclared dated record flips `has_story_vocabulary` and makes §12 step 5 **extract nothing from any scene**. This branch added two more producers of dated records: the second extractor family, and an Architect's reveal positions. Both are minted in `beats_for`'s own width from the book's own scene count, so both belong in the set; left out, every forged world would have looked like somebody else's numbering and silently lost all extraction. Fixed on the merge, with `test_a_forged_world_does_not_look_like_an_authors_vocabulary` pinning it. |

**Defect 8 is unfixed in Serial Pilot 2 and that is deliberate.** The pilot runs on the world that
produced it, so its graph line is unusable and **the second extractor family is inert for this
run**: the world grows through nothing. Re-forging for a clean pilot would have cost another $1.53
and buried the finding. What the pilot tests — whether a forged world reaches the writer and is
honoured — does not depend on the graph line.

**Defect 9 is likewise unfixed in the run**, which was seeded before it was found: pilot 2's four
arc debts carry a due key of `s8` rather than none, so `promise.overdue.v0` will annotate them at
the last scene. MINOR and `heuristic`, so it cannot block or park; recorded here so the run
record's overdue count is read as this rather than as the book failing to pay.

### 107.9.2 What has not been run

**Whether the prose is any good.** No reader has seen a word of either book, the §97 sim has not
run on them, and the operator's acceptance read has not been spent. M5 and M6 are fidelity numbers
and neither is entitled to an opinion about quality.

**Why the ledger pays nothing.** S5's null names the mechanism to look at — the summary call is
not told which debts are due — and nothing here has changed it or measured whether telling it
would help.

> **Answered by §110, 2026-08-22, and the mechanism was one step earlier than this named it.** The
> summary call was not told the debts *exist*: `store.promises(...)` appeared nowhere in its
> prompt path, so paying required a one-scene, no-memory call to reproduce a `sha256` input coined
> scenes earlier — measured at one in forty-one, and in the wrong channel. Shown the open rows on
> the same forged world, run C settled **8 of 40**, with 8 of 8 returned names matching an open
> row exactly. `plan/serial-pilot-2.md` §6.3.

**The between-Architect comparison.** The distinctness control is built for K candidates from one
brief. Two briefs producing two worlds rather than one world in hats is unmeasured, and N
architects divide §61's alpha by N exactly as N directors do.

**Anything about quality.** No reader has seen a word of this, the §97 sim has not run on it, and
no counter here is entitled to an opinion. Nine worlds that clear four deterministic gates is nine
worlds that clear four deterministic gates.

**The cross-forge collapse question.** The collapse gate is *within*-forge. Run 2 produced a
land-survey-and-geodesy world and run 3 produced another; nothing compares a forge against the
ones before it, and the operator reading K worlds is the only control that currently catches it.

### 107.10 Anti-scope

No new judges and no new quality metric. No human raters, panels, or solicited judgment of any kind
— §95's scope axiom is unchanged and nothing built here asks anyone anything. No selection among
worlds by any model, score, ranking or preference signal, enforced by an import ban. No stat-sheet
default, no hardcoded genre vocabulary, no combat assumption, and no requirement that a world have
a system at all. No schema class where a record pattern will do; no new `StateRecordKind`, no
migration, no contracts bump. No claim about book quality from a counter. The Director, Writer and
Reader/Judge roles are untouched and no Director kind was added. Retrieval when a serial outgrows
the packet is a design note and is not started. There is **no amendment surface**: a world is forged
once, before scene one, and whether the growth path or the operator authors a mid-serial change is
an open decision rather than a built feature. The between-Architect comparison is not run — N
architects divide §61's alpha by N exactly as N directors do, and nothing has measured that two
briefs produce two worlds rather than one world in hats. And the first quality question in this
project with an answer outside the text is now live and unanswered: a world that literalises a real
domain can be **wrong** about it, and nothing checks that.

## 108. The only sentence anybody wrote about endings reached no prompt, and the writer was never told which chapter it was in

**Built 2026-08-22, from [`plan/handoff-chapter-endings.md`](handoff-chapter-endings.md).** Three
bounded pieces, none of which teaches this system how to end anything. Code:
`application/constraint_locks.py` and `litharness lock-constraints`; `serials.Position` /
`serials.chapter_positions` and a `chapter` parameter on `planner.render_prompt`;
`research/quality-measurement/chapter_endings.py`. Measurements and the before/after packet:
[`research/quality-measurement/chapter-endings-census.md`](../research/quality-measurement/chapter-endings-census.md).

**Nothing above this entry was renumbered.** §107 was the last section when this began; the check
was re-run across `main` and all ten `.claude/worktrees/*/plan/stage-0-decisions.md` at commit
time, matching `^#{2,3} [0-9]+` so a sub-section could not hide a claimed parent (the §86.6
collision's lesson). No §108 existed anywhere.

**What licenses it is a count.** Measured against `serial.db` — the live eight-scene serial, plan
head `953d066fd9ee`, all eight `scene_draft` jobs `succeeded` — and against every own-generated
book on this machine, on 2026-08-22:

| | count |
|---|--:|
| constraints the operator's tone note produced | **5** |
| of those, `locked=True` | **0** |
| stored drafting prompts containing any of their text | **0 of 8** |
| stored prompts containing the string `scenes end` | **0 of 8** |
| interpretive directives whose `produced_constraint_ids` names what it produced | **0 of 4** |
| callers of `domain/serials.py` in `src/` | **0** |
| own-generated units whose final prose paragraph ends on a question | **0 of 146** |
| published RoyalRoad LitRPG chapters that do (n = 3,000) | **6.50%** |
| published chapters of this project's one assembled book ending on a `[STATUS]` line | **2 of 2** |

The operator asked whether the system incorporates any cliffhanger technique. The measured answer
was no in three layers, and the middle layer is the one worth the entry: the direction existed, in
the operator's own words, in the plan, on the record — and `plans.constraints_of` selects on
`locked`, so it was shown to nobody. **A boolean, and it silenced the whole tone note.**

### 108.1 The five constraints were in the plan and in no prompt, and the field that would have said so was empty

`acf0e05` fixed the *minting* rule — a constraint from a human-authored directive now locks by
construction — and a minting rule cannot reach a plan that was already minted. So the pilot's head
still carried five unlocked constraints: close third person, dry and exact, concrete specifics,
dramatize rather than summarize, and **"scenes end on movement or on a cost paid … they never end
on a tidy emotional summary"**, which is the only sentence about endings anywhere in this system
outside a planning document.

**The defect is second-order as well as first.** `narrative_planner` fills
`directives.produced_constraint_ids` from the constraints it minted **locked**, so a run that
locked none recorded none: all four interpretive directives on this store cite `[]`. The one field
designed to say which directive produced which plan item was emptied by the same boolean. The
lineage survives only in `plan_proposals`, and `constraint_locks.produced_by` reconstructs it from
there — walking `base_plan_revision_id -> resulting_plan_revision_id` rather than the rows' order,
because `plan_proposals` sorts on `(created_at, proposal_id)` and proposals accepted inside one ISO
second therefore sort on a content hash. That was found by
`test_a_rollback_clears_the_lineage_because_it_reads_no_directive` failing, not by reading the
code.

### 108.2 The repair locks a boolean, refuses three things, and its one weakness is named rather than buried

`litharness lock-constraints [--dry-run]` is deterministic, free, replayable, idempotent, and it
does not call a model. It was chosen over re-issuing the tone note as a verbatim `constraint`
because that spends a paid call **and** because `narrative_planner.render_request` shows the model
`current_plan_items`: it may as easily `CREATE` five near-duplicates beside the five as `UPDATE`
them, and a plan carrying two readings of one instruction has no way to say which governs. This
route creates nothing, so it cannot produce that.

It refuses more than it accepts, on purpose. **A machine-authored directive's constraint** — the
lock is a person's standing and a Director has none to spend (`plan/director-role.md` §1). **A
constraint whose producing directive cannot be recovered** — unattributable is not human. **Every
kind that is not `CONSTRAINT`** — `narrative_planner`'s symmetric rule forces the lock only there,
so widening it here would not restore what the fixed rule produces, it would be a wider rule
invented by the repair; the pilot's two promises and eight scene plans stay unlocked, which is also
what `plan_search` needs.

**It carries no `DirectiveReading`, and that is load-bearing.** `commit_plan_application` acts on a
reading by calling `Directive.interpret`, which is `RECEIVED -> INTERPRETED`; the directives this
traces are already `APPLIED` and `TRANSITIONS[APPLIED]` is `{SUPERSEDED}`. A reading would not
record provenance — it would raise and make the lane unrunnable. The lineage goes in the proposal's
rationale and the decision digest instead.

**The weakness, stated because the safe-looking version of this rule repairs nothing.** `author` is
`None` on all eight of the pilot's directives — the column postdates them — and
`directors.is_machine_author` reads `None` as "unrecorded", never as "machine". On this store that
is certainly right, since no Director existed when they were written. On a future store it is a
permission a row predating the column inherits by default. The narrower rule — lock only where
`author` names a recorded person — would refuse all five and leave the tone note silent, so the
wider rule ships with the trade named here and in the census note.

### 108.3 What the rule arriving actually costs, which is not nothing

Rendered from the store with no provider call, against a copy: plan head `953d066fd9ee` ->
`d5820540fa41`, locked items 5 -> 10, unlocked constraints 5 -> 0, plan epoch 8 -> 9.

| | `scene-1` | `scene-8` |
|---|--:|--:|
| CONSTRAINTS in the packet | 4 -> 9 | 4 -> 9 |
| SUMMARIES in the packet | — | **5 -> 4** |
| items omitted for budget | 0 -> 0 | **1 -> 2** |
| packet tokens | 1,887 -> 2,145 | 4,458 -> **4,448** |

**At the far end of the book the packet is already at its ceiling, so the direction arrives by
displacing a scene summary** — and the token count falls, because what was dropped is larger than
what pushed it out. That is the packer working as specified (constraints are priority 2) and it is
a real trade rather than a free win. It is also the first concrete case of §12's known defect
biting a *deliberate* change: the packer drops the oldest prose rather than the least relevant.

**Nothing already written moved.** All 38 stored jobs compare identical on
`(job_id, input_digest)` before and after; `plan_progress` reports 8 of 8 drafted, so the epoch
advance re-mints nothing and cancels nothing. The claim made is "the rule is now in the packet",
and only that. No accepted scene was redrafted.

### 108.4 The writer is told where the scene sits, and told nothing about what to do there

`domain/serials.py` had **zero** callers in `src/` — chapter grain existed only at publish time, as
`--chapter-scenes`. It now has one: `chapter_positions` is called by the work selector, and the
fragment `Chapter {c}, scene {k} of {n}.` goes into the beat line, after the ordinal and before the
dramatic function.

**No verb and no adjective, and that is asserted rather than trusted.**
`test_the_chapter_cue_carries_no_verb_and_no_adjective` slices the cue out of a rendered prompt and
checks it against the vocabulary a hook instruction would need. Telling a writer that a scene is
the last of its chapter is position, the same class as "scene 3 of 8"; telling it what to do about
that is taste, and a default here would be this system's taste in every prompt it ever renders
(§95's scope axiom, §97.1).

**The control is a byte comparison, and it matters beyond tidiness.** At `--chapter-scenes 1` —
the default, which asserts nothing — `chapter_positions` returns an empty mapping and the prompt is
byte-for-byte what it was. `input_digest_for` covers the prompt and **that digest is the sampler
seed**, so a cue leaking into the default path would silently change the decoding of every newly
minted job in the system. Pinned by
`test_the_prompt_is_byte_identical_when_a_chapter_is_one_scene` and
`test_the_default_selector_queues_the_prompt_it_always_queued`.

Three more properties are pinned rather than assumed. The arithmetic is `chapters_of`'s, not a
`divmod` beside it — `test_a_scenes_position_agrees_with_the_chapters_it_is_grouped_into` checks
them against each other at every serial length from 0 to 29, and every pre-existing name in
`tests/test_serials.py` is still alive. A trailing partial chapter reports its **real** complement,
so scene 9 of a nine-scene serial reads `Chapter 3, scene 1 of 1` rather than `of 4`. And a book
planned before the parameter existed converges instead of re-minting
(`test_a_tick_over_a_book_planned_before_the_cue_remints_nothing`), because `beat_job_id` excludes
the prompt by design.

**The shape is per run, not per book.** A `serial.db` ticked without `--chapter-scenes 4` still
drafts with no cue. Persisting a shape per book needs a migration, a plan item or a column; it is
named as the next step and deliberately not built.

### 108.5 The census: a locator, four counters, and a zero

`research/quality-measurement/chapter_endings.py`. `final_paragraph` reuses
`domain/axes.strip_system` rather than a second regex, dropping system lines *within* a block so a
paragraph carrying a status line in its middle stays one paragraph. Four counters, none of which
needs a model: final-paragraph word count, whether it is dialogue, whether it ends on a question,
and whether the literal last line is a system line. **§104.4's chapter-hook-shape property is not
touched**: classifying "a question opened / a reversal / a price paid" is a located-contrast
judgment that belongs to E6 mining when the anchor set lands, a regex for it is the
shallow-because-easy metric §1a.1 refuses, and a model asked for it is a new verbal protocol with
no validity evidence.

| | this project | RoyalRoad LitRPG |
|---|--:|--:|
| units | 146 (2 chapters + 144 scenes, 23 books) | 3,000 chapters, 102 stories |
| final paragraph, median words | 18 | 17 |
| **ends on a question** | **0.00%** | **6.50%** |
| final paragraph is dialogue | 34–38% | 33.7% |
| last line is a system line | 13.0% (100% at chapter grain) | 0.17% |

**The era control is the point, and it passes.** BRIEF.md §2's headline is `tricolon_rate`
separating declared-AI prose from pre-2023 at 0.629 while its *undeclared* 2025 control separated
at 0.606 — the metric detected the year. This one does not: 6.91% human pre-2023, 6.20% undeclared
2025, 5.38% declared-AI 2025, a spread of 1.53 points against a 6.50-point gap to this project's
zero. Within story, 58 of 102 books have at least one chapter ending on a question, so the
population rate is not carried by outliers. The **penultimate** paragraph, measured by the same
rule in the same pass as a control, ends on a question *more* often than the final one on
RoyalRoad (7.37% against 6.50%) — the opposite of what author-note contamination would produce, so
the 6.50% is not an artefact of notes.

**And the census got its own draw wrong first.** `royalroad_chapters` streams shard 3 then shard 30
under one global `limit`, so `limit=3000` returned **no pre-2023 chapters at all** — two 2025
cohorts and silently no control era, which looks identical to a corpus holding no old chapters. The
budget is now split per shard, and the failure is recorded in the function's own docstring because
it is invisible from the outside.

**No bar is declared, and the census says what one would have to survive.** At chapter grain this
project has produced **two** units, on which a rate takes the values 0, 50 or 100 and no bar
between them is expressible; nothing measured says a question is better; the counter would be read
off the same chapters the writer was directed to change, which is the Goodhart the §94 per-kind
tripwire exists for; and any subgroup of two is empty. Four attainability checks, none of them
answerable, so nothing is declared (§81, §85, §87, §89's lesson applied before the fact rather than
after).

### 108.6 Corrections in place

**`plan/serial-pilot-1.md` §4.5** said the five prose defects the operator named after the first
read were not disobedience because "the tone note reached the plan, became locked constraints and
sat in every packet". The first clause is true and the other two are not: the constraints were
minted unlocked and reached no packet at all. The conclusion is unchanged and its ground is
stronger — the tone note could not have been disobeyed, because no scene was ever shown it. Struck
through and corrected in place, pointing here.

**`plan/handoff-chapter-endings.md`'s two coordination notes were stale by the time the work
started, and the repo won.** §107 is merged on `main`, so §106 is not the last entry and this is
§108 for a different reason than the one given; and worktree
`.claude/worktrees/litharness-architect-stage-5ee368` is clean, its `planner.py` edits merged as
`4e545bc`, so there was no parallel change to merge beside. Its substantive note stands and is
carried forward below.

### 108.7 Anti-scope

No cliffhanger recipe, no hook instruction, no "end on a question", no "raise the stakes", no
default about endings in any prompt, template, system message or beat function. `SIX_BEAT` is
unchanged and no beat function was added. **No verdict channel**: no model was asked whether an
ending is good, whether it is a hook, or which of two it prefers; E6 stays byte-frozen and no new
verbal frame was written. No axis admitted, no counter registered — `chapter_endings.py` is
research-side and `axes.AXES` and `axes.COUNTERS` are untouched. No pre-registration, no bar, no
BCR change, no persona, judge, reader or panel change, no pool registration. No anchor set moved
and §104.4 stays gated. RS1 holds: nothing under `src/litharness/` references a corpus, a digest or
a RoyalRoad text, and no corpus prose crosses to the generation side as an example ending or a
paraphrase. The `[STATUS]` line at the end of a published chapter was **counted and not moved** —
that is an operator decision. No accepted scene was redrafted; `serial.db` was read read-only and
every repair was demonstrated on a copy. **Serial Pilot 2 was not edited**, and the note it needs
is recorded rather than acted on: `plan/serial-pilot-2-directives.json` holds six directives and
not one of them contains an ending clause, and if the operator wants one there the safe form is a
verbatim-lane `constraint`, which locks by construction and passes through no model. No human
reader, label or feedback entered anything here (§95).

## 109. The generation provider read the working directory's CLAUDE.md into every call, and the documented way to stop it logs you out

**Built 2026-08-22.** Code: `providers/cli.py` — two flags on every `claude -p` call,
`--setting-sources user` and `--settings` with `CLAUDE_MD_EXCLUDES`; tests in
`tests/test_providers.py` — `test_claude_argv_carries_every_mandatory_flag` pins both and pins
`--bare` *out*, `test_the_claude_md_exclusion_is_well_formed_and_names_the_files_it_must` parses
the JSON, and the opt-in `test_live_claude_does_not_read_a_claude_md_from_the_working_directory`
checks the outcome against the installed CLI. And a root `CLAUDE.md`, the first this repository
has had, written for sessions and proven not to reach the writer.

**Nothing above this entry was renumbered.** §108 was the last section on `main` and the highest
in any worktree when this began; the check was re-run (`^#{2,3} [0-9]+` across `main` and every
`.claude/worktrees/*/plan/stage-0-decisions.md`) before this was written.

**What licenses it is a measurement, and it was taken before the file existed.** The operator
asked why the repository had no `CLAUDE.md`. `git log --all` showed none had ever been added or
removed, so there was no recorded reason — and one real one: `tools/run-loop.ps1` runs the loop
from the repository root (`Push-Location $repo`), the adapter passes no `cwd`, and the headless
documentation says a `-p` call loads the same context an interactive session would, with
`--append-system-prompt` — the adapter's only system-prompt mechanism — appended *after*
CLAUDE.md. So a root `CLAUDE.md` would have ridden into every drafting, summary, outline and
forge call, and the frozen prompt (§103) would no longer have been the whole of what the model
saw. That the repository had been safe was an accident of the file not existing. Eight probes on
`claude-haiku-4-5`, `claude` 2.1.236, one-word answers, about $0.22 in total:

| working directory | flag | answer | cache-read | cache-write |
|---|---|---|--:|--:|
| scratch dir holding `MARKER-LEAKED` in `CLAUDE.md` | none | **LEAKED** | 0 (cold) | 26,832 |
| the same | `--bare` | *Not logged in* | — | — |
| the same | `--system-prompt` instead of `--append-system-prompt` | **LEAKED** | 0 (cold) | 24,769 |
| the same | `--setting-sources user` | NONE | 21,352 | 5,326 |
| the same | `--setting-sources ""` | NONE | 21,352 | 5,188 |
| the same | `--settings '{"claudeMdExcludes":[…]}'` | NONE | 21,352 | 5,329 |
| repository root (no `CLAUDE.md` yet) | none | NONE | 21,352 | 7,113 |
| the same | `--bare` | *Not logged in* | — | — |

Then the live test, with the adapter's own argv carrying **both** flags, against a marker file in a
temporary directory: NONE. The cold-cache zeros in the first rows are the first call of a prefix,
not an effect of the marker, and are not read as one.

### 109.1 What was refused, and why each refusal is on the record

**`--bare`**, the documented full suppression — it also skips keychain reads, which is where the
subscription login this adapter runs on lives (`ClaudeCodeProvider`'s docstring: no credential of
its own). Not a fix that can be had here; it would be the fix under API-key auth. **`--system-
prompt`** — documented to ignore CLAUDE.md and measured *not* to on this version; recorded so no
later session trusts the sentence. **Relocating `cwd`** off the repository — would have worked
and been invisible and machine-dependent; a flag in `_argv` is pinned by a test and a cwd is not.

**Two mechanisms rather than one, because each covers the other's gap.** `claudeMdExcludes` is
the control the documentation names for CLAUDE.md, and it was verified only against a
working-directory file; `--setting-sources user` is docs-silent on CLAUDE.md but measured to work,
and it also drops project and local `settings.json` — hooks, permissions, env — which this adapter
never wanted and which the repository does not currently carry (`.claude/` holds a skill, the
worktrees and a lock; no settings file), so nothing any call has received to date changes.
The live test checks the outcome, not the mechanism, which is the only honest pin when one of the
two rests on observed rather than documented behaviour.

### 109.2 The overhead half of provider-adapters.md's experiment, now run

That document's open item asked whether "settings that suppress CLAUDE.md/skill/plugin
discovery" could cut the ~5k non-cacheable per-call overhead. The halves come apart: CLAUDE.md
suppression costs nothing and saves nothing (the overhead is identical with and without it), and
the skill/plugin tax is reachable only through `--bare`. Measured on 2.1.236: **21,352
cache-read + 5.2–7.1k written per call**, against the ~19k + ~5k recorded when the adapter was
built. Struck in place in `plan/provider-adapters.md` with these numbers; the module docstring's
~24k carries the ~27k beside it.

### 109.3 The file itself

`CLAUDE.md` is the session-conduct layer that had no home: the parallel-session rules, the
ledger-number procedure with its command, the citation checker, counts-point-to-homes,
corrections-in-place, the standing axioms as one-liners with pointers, the box rules (`claude -p`
fails under box load; kill by PID; two interpreters). It points at `CONTRIBUTING.md`, `README.md`,
`BRIEF.md`, `RUNBOOK.md` and the handoffs rather than restating them, and it carries **no counts,
no status and no test totals** — the PLAN.md header's own lesson, that the number the project
reports about itself is the number to distrust first. Five `plan/handoff-*.md` files had each
re-stated the same coordination rules, which is the defect the file closes.

### 109.4 Anti-scope

No prompt, packet, template or beat function changed; no call any book has received to date
contained a CLAUDE.md, so no stored prompt is re-read differently. No overhead reduction is
claimed — the number went up, and is recorded going up. No quality claim of any kind. No human
judgment entered anything (§95). The `debug-book` skill, the handoffs and the planning documents
are untouched; `CLAUDE.md` is additive and the only change to what a session is told is that it
is now told once, in one place.

### 109.5 Found after the entry was written: four instruments shell out to `claude -p` themselves

**The provider was not the only caller, and `--system-prompt` is not a shield.** The operator
asked whether the file would cause issues, and the grep that should have been run before §109.4
was run after it: `research/quality-measurement/elicit.py` (`CLI_HARDENING`, imported by
`comic_beats.py` and `writer_states.py`) and `force_remote.py` (its own copy of the tuple) build
their own `claude -p` argv, run from the repository root, and use `--system-prompt` — which the
table above already showed does **not** keep CLAUDE.md out. So with the file at the root and the
flags only on the provider, every E6 elicitation, force-programme continuation, comic-beat census
and writer-state call would have carried `CLAUDE.md` in the judge's context, and the replay cache
— keyed on (system, messages, model, transport) — would not have noticed. A contamination of the
*measurement* side rather than the generation side, and invisible from the cache.

**Closed the same day, with the same two flags on both tuples**, copied rather than imported
(research code must not depend on `src/`, and `comic_beats` runs under an interpreter that cannot
import the package). Measured through the edited `elicit.CLI_HARDENING` — `--system-prompt` plus
the two flags, marker file in the working directory — the answer is NONE (cache-read 21,092,
write 3,525). `comic_beats --selftest` passes on the same registration digest, because
`registration_digest()` never covered `CLI_HARDENING`; the four test files that import the
modules pass. **No paid research call ran between the file's creation and this fix** — the
process list was read at every step — so no cached answer carries it.

**The rule this leaves, written into `CLAUDE.md` and the RUNBOOK:** every `claude -p` call site in
this repository carries the two flags, the live test is the guard, and it is re-run after any
`claude` upgrade — the suppression rests on one documented setting and one measured flag, and
a CLI release could move either. The worktrees were also probed: a marker appended to the root
`CLAUDE.md` did **not** reach a call made from `.claude/worktrees/<name>/` (answer NONE), while a
plain child directory and a child that is its own git root both leaked a parent's file — so the
worktree boundary is respected by this version and that, too, is observed rather than
documented. Commit the flags and the file **together**, so no checkout ever has one without the
other.

## 110. The one call that can settle a debt was the one call never shown the ledger

**Built 2026-08-22, from [`plan/handoff-promise-ledger.md`](handoff-promise-ledger.md).** Code:
`application/summarize.py` — `render_summary_prompt` gains `open_promises`, the handler loads the
open rows and records which returned names matched — and `tools/rematerialise_forge_bundle.py`.
Measurements and the design note:
[`research/quality-measurement/promise-ledger-settlement.md`](../research/quality-measurement/promise-ledger-settlement.md).
The run is [`plan/serial-pilot-2.md`](serial-pilot-2.md) §4.1 (pre-registration) and §6.3.

**Nothing above this entry was renumbered, and it is §110 rather than §109 because the check at
commit time caught a collision the check at start time could not have.** §108 was the last section
when this began and the handoff said "§109 or later"; while this branch was measuring, `3fbfaf8`
landed §109 on `main` — the provider reading the working directory's `CLAUDE.md` into every call —
and seven `ox-*-7f3a21` worktrees carrying it appeared beside this one. The check was re-run across
`main`, every local branch, and all twenty-four `.claude/worktrees/*/plan/stage-0-decisions.md`,
matching `^#{2,3} [0-9]+` so a sub-section could not hide a claimed parent. That is the §86.6
lesson working: the number is claimed at commit, not at start.

**That §109 does not reach this run.** The provider defect it fixes reads a `CLAUDE.md` out of the
working directory, and this worktree has none — it branched from `83de11c`, which predates the file
— so run C's twelve invocations carried no such text, exactly as runs A and B did not. `main` was
merged in afterwards, so the fix is in the branch and was not in the run.

**What licenses it is a count, and it was taken before a line was written.** Measured against
`serial.db` — the live eight-scene serial, all eight `scene_draft` jobs `succeeded` — on
2026-08-22:

| | count |
|---|--:|
| rows in `promises` | 40 |
| of those `paid` | **0** |
| `promises_opened` items across the eight summaries | 41 |
| summaries returning a non-empty `promises_paid` | 1 of 8 |
| `promises_paid` strings returned in total | 2 |
| of those, naming a row that existed at that moment | **0** |
| of those, naming a row that ever existed | **0** |
| subjects the summariser re-coined exactly, unprompted | **1 of 41** |
| `store.promises(...)` calls anywhere in the summary prompt path | **0** |
| calls that DO see the ledger (writer's packet, outline) | 2 |

And after, on the same forged world with one block added to one prompt: **40 opened, 8 paid**.
Eight of the eight names the model returned matched an open row on the list it was shown; before,
two of two matched nothing that had ever existed.

### 110.1 It was never a model failing, and the arithmetic says so

`promises_paid` is a list of strings. Each goes through `normalise_subject` (NFC, casefold,
whitespace to underscore) into `promise_id_for(book_id, subject)` = `sha256(book_id + subject)`,
and `pay_promise` runs `UPDATE … WHERE status='open'`. **Paying a subject the ledger never opened
is a no-op by design** — a payoff with no recorded promise is not a debt the ledger can attest was
owed — so a payment lands only when a one-scene, no-memory call reproduces a subject string coined
scenes earlier.

The measured rate at which that happens unprompted is **one in forty-one**, and the one time it
happened it landed in `promises_opened`, where `INSERT OR IGNORE` collapses it and nothing
changes. The two strings the model did return as paid — *"The tarnished blank at Kessel's stall"*
and *"Turrow's ring appraisal"* — are fluent prose names for debts the book plausibly owed, and
neither was ever a key.

**Four books, and the seeding experiment had already ruled out the other hypothesis.** 32/0, then
40/0, then Serial Pilot 2's 41/0 and 47/0 on a world whose six debts were seeded *with their
answers already in canon* and two of them disclosed to the writer at their scheduled scenes.
§107.9.2 and `plan/serial-pilot-2.md` §6.2 both named the next question as "the summary call is not
told which debts are due". Measured against the code it is sharper and it is structural: **the
call was not told the debts exist.** The writer's packet has carried the open rows since §61 Add 2
and the outline call has seen their subjects since W2. The one call that can mark a debt paid was
the one call not shown them.

### 110.2 The repair is one block in one prompt, and its control is byte-identical

`render_summary_prompt` takes `open_promises`; the handler loads
`store.promises(book_id, branch_id, open_only=True)` and passes the rows through in the store's
order — due-soonest first, NULL due last — **uncapped**. Each row renders as its `subject`
verbatim followed by `describe_owed(promise)`, the ledger's own line, in a block that states its
register and is kept **separate from the THREAD block**: open threads are canon-backed state
records and promises are model-reported or forge-seeded debts, and one list under one heading
would launder the second into the register of the first. `PROMISES_PAID` now asks for names copied
exactly from that list, and is conditional so a prompt never names a list it does not carry.

**With an empty ledger the prompt is byte-for-byte the old prompt**, both halves. That is the
control, and it keeps every golden fixture, every research caller of `render_summary_prompt` and
every scene before the first promise opens asking exactly the question they asked before.

**Cost**, measured on `serial.db`'s 40 real rows against a real 900-word scene: ~32 tokens per row
net of a 44-token header, 1,611 → 2,995 at 41 rows. No cap, because the rows are one line each,
the largest ledger measured is 47, and a cap would drop exactly the debts a long book most needs
settled while reporting nothing. The named risk was at the other end — a model shown 32 names
returning an answer too long for the 512-token budget, costing the scene its summary. **It did not
happen: 0 of 46 jobs ran a second attempt.**

**The summary row now records what matched.** `promises_json` gains `paid_matched` /
`paid_unmatched` beside `paid`, exact set membership against the subjects rendered into that
call's prompt, so "did showing the ledger change anything" is answerable from the store rather
than re-derived from prose. **Deliberately not looser**: a ledger that pays on near-matches is
worse than one that pays nothing, because W4 grades payoff landing against the ledger's own
wording.

### 110.3 S5′ settles, and the answer is not one of the three outcomes that were named

Pre-registered as `plan/serial-pilot-2.md` §4.1 before the run and before any paid call, and
recorded as §6.3. Same world, same directives, same commands, same budgets; the bundle was
re-materialised rather than re-forged.

**65 ticks, 46 jobs all succeeded, 21 decisions all ACCEPT, 12 invocations, 743,800 tokens,
$5.60.** Eight of eight scenes, 7,743 words, 9 revisions rebuilding cleanly, 0 parked, 0 poisoned,
0 unattributed, `context_omitted = 0`, 5 findings all `promise.overdue.v0` MINOR — run A's and run
B's number exactly. **The gate exits 0.**

**The control holds.** The hidden-count trace reproduces byte for byte: `20, 20, 20, 19, 19, 19,
18, 18`, the same drops at scenes 4 and 7. S3's machinery was untouched and did not move.

**40 rows, 32 open, 8 paid.** Payments at scenes 4 (one), 7 (two) and 8 (five). Packet threads run
6 → 32 against run B's 6 → 41.

**The three named outcomes did not partition the space, and that is a defect in the
pre-registration rather than something to reinterpret afterwards.** They were written as if
"seeded" were one population; the six split into two — two debts the world scheduled *inside* this
book, four arc debts at scenes 26/41/63/92 that it did not. Outcome (i) named the two in-book ones
and **neither was paid**. Outcome (ii) said 0 of 6 seeded and **1 was**. Outcome (iii) said
model-opened paid and seeded not, and a seeded one was paid.

**What the run does answer is the question S5′ asked**: *does anything settle with the ledger
shown?* **Yes — 8 of 40, from 0 of 41 and 0 of 47 on the same world.** Not being shown the ledger
was the block.

**What it opens is sharper than the null it replaces.** The two seeded debts whose answers the
book *actually disclosed to the writer at their scheduled scenes* — `m_holts_date` at s4,
`m_orrin_last_call` at s7 — are the two that stayed open. The one seeded debt the ledger marks
paid is `m_the_wrong_table`, an arc debt scheduled for scene 63 whose answer stayed hidden for the
whole run. **The summariser marked paid a debt this book was never told the answer to**, and the
ledger cannot check itself — which is the self-grading defect `payoff_landing.py` opens on, and
the next question rather than this one's.

### 110.4 W4 built its scene keys two characters wide and its ledger's are one

Found while reporting what the new ledger could give
`research/quality-measurement/payoff_landing.py`, and it is §108's shape again — an instrument
reporting an empty world because of a small mistake nobody had cause to look at. `read_scenes`
padded to `max(len(str(len(units))), 2)`; `beats_for` pads to `len(str(len(scenes)))` with no
minimum. On an eight-scene book the ledger holds `s1…s8` and the instrument built `s01…s08`, so
every membership test failed and the census reported **four arms of zero** — which reads as "the
ledger supplied no substrate" and was a key-width bug. `toll.db` is ten scenes, where both rules
agree on 2, which is why nothing had noticed.

Fixed to `beats_for`'s rule exactly; nothing changes for any book of ten scenes or more. On
`serial.db` the arms go 0/0/0/0 → `unpaid` 35, `placebo` 10, `constructed_positive` 40, with
`paid` and `mismatched` still 0 because that ledger records no payment. On `serial2c.db`:
**`paid` 8, `mismatched` 8, `unpaid` 27, `placebo` 8**, and `census.unrunnable` is `[]` for the
first time — the middle arm the module calls "the whole study" has substrate.

**The module's verdict is untouched and is not about the ledger.** `SCORER_UNUSABLE` stands on its
own pre-existing grounds — `check_open_threads` was built to ask whether a summary of the same
prose mentions a recorded thread, and W4 asks it whether a one-sentence paraphrase names the same
debt — so **W4 needs a different scorer before it can be run at all**, whether or not anything
settles. The verdict stays NOT VALIDATED; the owner-read set is out of scope here, and the model
legs touch the 4090 and carry the duty-cycle and temperature governor, so running them is an
operator call.

### 110.5 The bundle was re-materialised and the operator's pick was not re-made

`pilot2/` is gitignored and was gone from this machine, and `serial-pilot-2-setup.ps1` refuses
without `seed.json` / `directives.json` / `promises.json`. Re-forging costs $1.53, yields a
different world and needs a person to choose again, so `tools/rematerialise_forge_bundle.py`
rebuilds the bundle from the committed source instead. It touches no database, records no decision
and calls no model: the pick was taken on 2026-08-22 and is already a policy decision with
`VerdictSource.HUMAN`, and a second `HUMAN`-sourced row minted by a script would be a machine
wearing a person's authority — the thing `forge`'s two-command split exists to prevent. It refuses
a package with no `picked`, a directory that already holds a bundle, and a scene count the
committed directives were not written for.

Everything in a bundle is derivable: the three uuids are `uuid5` over
`litharness://forge/{architect_id}/{index}/{part}`, so they reproduce exactly, and the committed
`directives.json` / `promises.json` are byte-equal to `architect.directives_for` /
`architect.promises_for` over the world — which the tool asserts rather than assumes. **329
records, `worlds.validate` clean**, the same count run B ran on. The one field the package cannot
recover is `meta.created_at`; it is minted, printed, and named in the run record, and no record
depends on it.

Two pre-existing conditions were carried and not fixed, as the handoff required: the world's graph
line is unusable, so the second extractor family is inert on this world (0 records read off the
book's own prose, 329 of 329 seeded — defect 8), and the four arc debts carry no due key (defect
9's fix, already in code).

### 110.6 What was refused

**No bar was declared.** S5′ is a question with named outcomes. n is six seeded debts plus
whatever the summariser opens, §108.5's "any subgroup of two is empty" applies to every split of
it, and a pre-registered null is a result (§61) — as is a pre-registration whose outcomes miss,
which is recorded rather than rewritten.

**Advisory stayed advisory.** `promises_paid` is still a model claim; `promise.overdue.v0` is
unchanged, still MINOR and `heuristic`; no finding severity moved; nothing built on the ledger
blocks, parks, ranks or selects anything.

**No fuzzy matcher, and the refusal is the point.** Exact match on purpose: a ledger that pays on
loose or majority-word matches is worse than one that pays nothing, because the report-channel
question grades against the ledger's own wording. Nothing in `src/` matches a subject any way but
exactly — and it did not need to, because 8 of 8 returned names were exact.

**No instruction about what to pay or when**, asserted rather than trusted: a test slices the
block header and the added ask out of a rendered prompt and checks both against the vocabulary an
instruction would need. **The writer's packet and the drafting prompt were not touched at all** —
exactly one file under `src/` changed, and run C's scene-1 packet reproduces run B's 229 facts /
20 hidden / 6 threads / 0 omitted.

**No migration for an authored-versus-model column.** `model = ''` is still the sentinel doing a
column's job (§107.8's stated limit). It is *named* as what a persisted ledger policy would need
and it is not built.

**No verdict channel.** No model was asked whether a payoff is good, whether a scene pays a debt
well, or which of two payoffs it prefers. E6 stays byte-frozen and no new verbal frame was
written.

**No policy, no retriever, no pruning.** §5 of the measurement note is one page of design and no
code: what "still worth carrying at scene N" would have to decide, what it must not do (drop a
debt for being old — §12's defect, which §108.3 recorded biting a deliberate change), and where a
writer-side "due now" cue would sit if the operator ever wanted one. **Whether settlement alone
relieves the packet is now measured and the answer is no**: run C settled eight and still carried
32 threads at scene 8 against run B's 41, and 34 of its 40 rows were opened by the summariser
itself. The policy is still needed; what changed is that it would now have a `paid` population to
be calibrated against instead of a column of zeros.

### 110.7 Corrections in place

**`plan/handoff-promise-ledger.md`'s `CONTRIBUTING.md` citation is stale and the repo won.** The
handoff cites `CONTRIBUTING.md` for "`claude -p` fails silently under load"; no such sentence is
in that file or anywhere else in the repository. The substance was honoured anyway — a
`litharness forge` arm was running on this box when the run was due, and the run waited for it to
exit before starting — and the rule is worth writing down somewhere it can be cited from.

**A gap in the record this change makes newly load-bearing, recorded rather than fixed.** The
*drafting* prompt is frozen into the job payload at enqueue (invariant I5); the **summary** prompt
is not — it is rendered at handle time and the payload carries only ids. So "which debts was the
summariser shown at scene 5" is reconstructable from the ledger and the summary rows, and is not
stored. That was harmless while the prompt depended only on the scene's own text. It now depends
on mutable ledger state, and freezing it is a payload change with its own compatibility question,
so it is named here rather than taken.

### 110.8 Anti-scope

No change to the drafting prompt, the packet, or `planner.render_prompt`. No "pay now" / "due now"
instruction anywhere; no model chooses which debt to pay; no ranking of debts or kinds —
`PROMISE_KINDS` carries no valence and none was added. No retriever, no pruning policy, no
migration. No re-forge, no different world, no edit to the committed world, directives, promises or
craft JSON, and no redraft of any accepted scene; `serial.db` was read read-only throughout and
every measurement on it was a query rather than a write. No `lock-constraints` on `serial.db`, no
`[STATUS]` line change, no ending clause in pilot 2's directives — all still operator decisions.
**No acceptance read was spent**: the gate exits 0 and the read is the operator's, not this
session's. No claim about prose quality and no comparison of prose between runs. No reader, judge,
persona, BCR, axis or pool change, and no pre-registration beyond S5′. No human reader, label or
solicited judgment entered anything here (§95). RS1 holds: nothing under `src/litharness/`
references a corpus, a digest or a RoyalRoad text.

---

## 111. The world reached the writer and reached neither planner, and the plan named none of what the page names

**Built 2026-08-22.** Code: `domain/world_brief.py` (new), an optional `world` on
`application/outline.py::render_outline_request` and
`application/narrative_planner.py::render_request` threaded from canon at both call sites,
`NarrativePlanningStore` widened with `StateRepository`. Measurement:
`research/quality-measurement/world_uptake.py` and `world_plan_arms.py` (new), the note at
`research/quality-measurement/world-uptake.md`, results under `results/world-uptake-run{A,B,p4}.json`
and `results/world-plan-arms{,-fake}.json`. Tests: `tests/test_world_brief.py` and
`tests/test_world_uptake.py`.

**Nothing above this entry was renumbered.** The check (`^#{2,3} [0-9]+` across `main` and every
`.claude/worktrees/*/plan/stage-0-decisions.md`) was run when this work began — §108 was then the
highest — and run again at commit time, by which point `main` had reached §110 and this moved to
its number. §86.6 and §108 both record why the check is run twice.

### 111.1 The blindness, measured before it was repaired

§107 built a world and measured that it reaches the *writer*: a flat 229-231 established facts per
drafting prompt out of 329 records, `context_omitted` 0 for the whole book, the hidden section
dropping 20 → 19 → 18 at exactly the two scenes the world scheduled. Nothing measured what the
**plan** was written against, and the plan is the sentence the writer is told to execute.

Both authors of that sentence were world-blind, and it is now a passing test rather than a claim.
`test_neither_scene_plan_author_is_told_the_world_the_writer_is_handed`, on `main` at `83de11c`:
of 7 rules, 21 consequences, 28 claims and 42 manifestations, **zero values reach either planner
payload**, and the coined nouns that do are the premise's own. `render_outline_request` was handed
the premise, the beat sheet, the starting sheet and the open promises; `render_request` was handed
the plan and a directive body. The outline handler read `store.state_records` and kept only the
`status_snapshot`; the narrative-plan handler read no state at all, and `NarrativePlanningStore`
did not compose `StateRepository`, so it structurally could not have.

**It knew the schedule and not the answers.** `promises_for` seeds one promise per reveal with the
mystery's *question* as the description and its ordinal as the due date, and open promises reach
the outline call as owed. So the defect was never ignorance of the mysteries; it was ignorance of
the world.

### 111.2 The counter, its two legs, and the control that kills one of them

`world_uptake.py` counts, per declared feature — 135 for the pilot world — whether a member of its
name set appears in a text as a whole word. Two legs, **both registered before the first count**
rather than one and then a repair: `wide` is `key_nouns`' rule per subject, and `coined` is `wide`
minus every token the RoyalRoad shelf owns at ≥ 5 of **608 distinct LitRPG fictions**. The
reference corpus is deliberately not the sham corpus; a narrowing defined by the control it has to
survive is a control that cannot fire.

**The sham kills the wide leg outright.** Twenty-one books that never saw this world name a median
**29.5%** of it — because *First In Time* coined `call`, `date`, `year`, `time`, `first`, `gate`,
`table`, `river`, `flat` and a column headed `NEVER`. On the coined leg **19 of 21 control books
name nothing at all**, median 0.0000, max 0.1020, and the two collisions are the given names
*Teodor* and *Orrin*, which the same model family reused in unrelated books. Floor sensitivity at
1 / 5 / 25 / 100 fictions: 0.3214 / 0.1837 / 0.2075 / 0.2778 pooled — the declared floor is not the
flattering one.

### 111.3 A correction inside the frozen block, and the digest that moved once

The pre-registration declared the sham quantity twice in two units: `SHAM_CEILING`'s prose named a
per-book share, `declared_quantities` named the pooled union across twenty-one books, and the first
implementation compared the union to the ceiling. **The union is not scale-free** — it rises with
the number of control books and reaches 1.0 for any non-zero per-book rate given enough of them, so
a ceiling on it is a ceiling on the size of the corpus. That is the range-and-unit failure this
project has recorded seven times, arriving in a registration written *by* the rule.

Fixed by reporting median, maximum and pooled with a verdict each; `SHAM_CEILING` unchanged at
0.05; the correction stored as `PRE_REGISTRATION["corrections"]` inside the block it addresses; the
digest moved `69ffc6a2b0917f1bec68` → `cd79c3f56e21a1354e27`; **no figure computed under the old
digest is withdrawn**.

### 111.4 The census: eight names, four cast members, and no rule at all

Run B, coined leg, world-beyond-premise — the reading that means "the 329 records reached the
page", because the planner and the writer both read the premise:

| | run B | run A |
|---|--:|--:|
| nameable features | 28 | 28 |
| ever named in the prose | 12 (0.4286) | 9 (0.3214) |
| **ever named in any of the eight plan statements** | **0** | **0** |
| writer-improvised, of the prose-named | **12 of 12** | 9 of 9 |

Run B's eight statements are 861 words and carry exactly two of the world's coined nouns — `wren`
and `headgate` — and the premise carried both. Every world name that reached the page was placed
by a writer executing a sentence written against none of it.

**The census's real resolution is eight tokens, not twenty-eight features**, and that is the
finding about the instrument. What a 329-record world put on the page beyond its premise, in
vocabulary the genre does not own, is **four of its six cast members**: Serrell (s1), Teodor (s2),
Marius Tebb (s3), Ferris Kane (s6). Orrin Veck never. `i_watermasters_office` never — its only
coined token is the plural `watermasters` and the prose says *the watermaster's*, which the
registered no-stemming rule cannot match. The two rules with coined names, `r_forfeiture` and
`r_subsidence`, and all six of their consequences: never, across 7,812 words. The other five rules
have no coined token at all and the counter cannot see them.

Of the 229 fact lines the writer read at scene one, 132 carry no name the counter can follow, and
**28.9% of the 97 that do are never echoed**. Hidden claims are reported in their own row and never
pooled: five of the nine with a coined name reach the page, and every one of those five is a
`*_secret` whose only token is a cast surname — a character appearing in a scene, not a secret
being told.

### 111.5 The brief, and the leak rail on the input side

`domain/world_brief.py` hands both planner calls what the packet already knows how to say —
`worlds.project` first and `state.describe` as the fallback, the same two calls
`context._state_item` makes in the same order, under the same filters minus the story-time cutoff
and with no POV. For the pilot world that is **229 facts, the same 229 the writer's prompt
carries**, grouped rules-first, plus both criterion ladders and all six mysteries.

**The rail is on the input, where it can be proved rather than hoped for.**
`hidden_record_ids(records, at=None)` is the maximal hidden set — with no coordinate every
scheduled claim reads as *not yet told* — and every one of those records is dropped from the facts.
An answer re-enters in exactly one place, the entry for the scene the world scheduled it at, and an
answer this book has no scene for never re-enters. Of the **20 claims hidden at scene one**, the
only two whose content appears anywhere in the payload are the two the frozen prompts show the
hidden count dropping at. Twenty of the 28 claims are hidden and only six are declared mysteries: a
brief built from `questions()` alone would have leaked fourteen cast and place secrets.

Absence stays free and it is bytes: the field is *spread* into the payload rather than assigned,
because `json.dumps` writes `null` for a value that is not there and both existing optional keys
are always-present nulls — copying the module's own style would have changed every payload in the
repository.

Four rules reach the planner and none asks for a name; a test enforces that on the prompt, because
a prompt that asked for names would make 111.2's counter its own target in the one place nobody
would look afterwards.

**One provenance gap, named and not closed.** Neither `_policy_digest` hashes the prompt, so a
world-aware outline decision and a blind one record the same `policy_config_digest` — and the
outline digest's docstring says it exists so a change to it reads as a change. Bumping it changes
the digest of every existing decision in every store, which is a repository-wide decision and not
this entry's to take.

### 111.6 P1-P4, and the stop that was raised by the leg this harness added

Six live outline calls, three forged worlds, two arms. `transport=live`, `failures=0`, 8 of 8
statements parsed in every cell; the fake-provider rehearsal parses zero and records
`statements_parsed` so a vacuous zero can never be read as a null.

**P1 — yes, and the blind side is a floor.** World-beyond-premise, coined leg, share of nameable
features named in the eight statements: *First In Time* 0/28 → **17/28**, *Borrowed Hands* 0/30 →
**3/30**, *The Traverse* 0/21 → **14/21**. Three of three worlds, and the blind arm is exactly zero
in all three — the same zero the stored run-B plan gives, reproduced live on two worlds no book has
been written on. Not the §89.1 class of instructed variation arriving inert.

**P2 — the registered instrument fired zero times.** `check_open_threads`, which the direction
names, across 3 worlds × 8 statements × 6 claims: **0**. Its depunctuated twin: **0**. Its silence
has to be read against its own arithmetic, which is reported per claim: the majority rule needs 9
to 16 of an answer's 18-32 distinctive tokens inside one ~25-word statement and can only fire on
near-verbatim restatement. That is the "0 paid is structural" shape, which is why a third leg
exists — a control-calibrated overlap check whose floor is the **blind** arm's own maximum on the
same world.

The third leg fired nine times and its verdict is `STOP` as registered. **Five of the nine land on
answers the planner was never shown**, because `brief_for` hands an answer over only at its window
and an arc claim's answer is never handed over at all — so the check is reading the world's
vocabulary rather than its secrets, which is a confound P1's own positive result guarantees. The
nine flagged statements share two or three ordinary words apiece with their answers and not one
states an answer; all nine are quoted in the result file, and the closest call is named as the
closest rather than lumped in. The rail's own named check passes; the leg that fires is this
harness's addition and its failure mode is measured rather than argued.

**P3 — the registered instrument is the wrong one and says so.** By the claim's name set: 1 of 5
windows wide, 0 of 5 coined, and the *blind* arm scores 3 of 5 on ordinary-word collisions. A claim
id is `m_holts_date`; the statement that lands its reveal says *her father's signature selling the
Holt date to Kane*, whose tokens are a plural the no-stemming rule cannot match and a word the
premise carries. Reported beside it, on the answer's own words: mean overlap at the window scene
0.0556 → 0.1432, 0.0417 → 0.2917, 0.0000 → 0.1861. Three of three worlds, four of five windows,
and the one exception is a paraphrase the overlap statistic under-reads.

**P4 — more world in the plan put more world on the page, and the improvisation share went from
everything to nothing.** One eight-scene draft of *First In Time* on a fresh store, same forge
bundle, same `--target-words 900 --context-budget 16000 --chapter-scenes 4`; gate exit 0; 7,496
words against run B's 7,812, 46 jobs against 46, 12 invocations against 12, **$6.01 against
$5.89**, 0 parked, 0 poisoned, 0 unattributed, `context_omitted` 0. Two recorded deviations:
`--library book-library-p4`, because `library.slugify` names a shelf from the title alone; and the
daily cost ceiling raised 10 → 25, a guard against a mid-run PARK that changes nothing the model
sees.

Coined leg, world-beyond-premise, 28 nameable features: **ever named in the prose 12 → 17**,
**ever named in a plan statement 0 → 20**, **plan-first of the prose-named 0 of 12 → 17 of 17**,
**writer-improvised 12 of 12 → 0 of 17**. The gain is entirely in the two kinds run B never named
at all, which are the two the world rule asks a statement to put to work: **rules 0 of 2 → 1 of 2**
and **consequences 0 of 6 → 3 of 6**; entities and claims are unchanged. Feature by feature the
whole difference is three names: `forfeiture` — one rule, three consequences, one manifestation —
goes from never across 7,812 words to scene 4, planned at scene 4; `orrin`/`veck` from never to
scene 6, planned at scene 6; and `teodor` the other way, planned at scene 2 and **not on the page**,
which is what keeps "the plan named it" and "the page names it" from being one sentence. The
registered null — plans name more and prose does not move, which would have pointed at §5.1's
per-scene selection — **did not occur**.

**The leak rail on the plan the book was actually drafted against**, and this is the finding rather
than the number. `check_open_threads` and its depunctuated twin: **0 hits**. The control leg: 32
hits, **24 of them (75%) on answers the planner was never shown**, at 2.5× the statement length P1
measured. Of the eight that are not that, two are worth reading: the scene-3 statement ends *"He has
been friendly to her for three years. She does not ask why, and he does not tell her"* against an
answer whose last clause is *"Kane has been friendly to her for three years because he is waiting to
see whether she works out…"*; and the scene-6 statement has Wren *"write down what she has been
asked"*, which is the mechanism of the scene-7 answer. **Neither statement contains its answer** — a
reader of scene 3 does not learn the date was sold, a reader of scene 6 does not learn the nephew
has been speaking it — but both stage the answer's supporting clauses one scene early, one of them
nearly verbatim while explicitly withholding the reason.

**That is a tension between two rails and neither was written knowing it.** The handoff's boundary 3
says no statement before a window may contain that claim's answer. The world rule this build hands
the planner says the window scene is where the answer lands, *planned as an event and not as an
explanation*. An event needs its causes arranged before it, and the causes of a reveal are exactly
what a recorded answer is made of, so a planner obeying the second will always put some of the
answer's words on an earlier page and a word-overlap check will always call it a leak. Which rail
gives is an operator decision; if it goes the other way the fix is in what the brief hands over —
question and window only, no answer — and P4 should be discarded with it. Both statements are quoted
in full in the note.

**What P4 may not be read as.** Not quality, not reader effect, not "the iceberg is felt". One book
against one book, no variance estimate, no second draw, and a plan whose statements are 2.5 times
longer than run B's — a difference that is itself a plausible cause of some of the movement and is
not separable here. And the two fact-level rows move in opposite directions: more of the packet's
229 facts are named beyond the premise (0.443 → 0.516) and slightly more are never named at all
(0.289 → 0.309).

### 111.7 Corrections in place

1. The handoff's Task 0 assertion — "the payload's coined-noun set is exactly the premise's" —
   holds for the outline arm and needed a computed template control on the narrative-plan arm,
   because `r_lag` manifests as a column headed `NEVER` and the request template's eighth rule
   begins "Never update or delete a locked item". The test carries the correction.
2. 111.3's registration correction, with both digests and no figure withdrawn.
3. `pilot2/direct2/forge.json` has no top-level `world`, `worlds`, `candidate_reports` or `picked`;
   its three worlds are `candidates[i]["world"]`, and `plan/serial-pilot-2-world.json`'s `picked` is
   **one-based** while the Candidate index is zero-based.
4. The committed `candidate_reports` are stale by design and the repo already says so: live
   `records_for` at `scenes=8` gives 329/346/326 records against 327/345/324 reported, and
   `reveals_scheduled` 2/1/2 against 6/6/6, because `REVEAL_SCENE` landed after the forge ran.
5. Neither this worktree nor the architect worktree held a `CLAUDE.md` while any of this ran, so
   §109's contamination touches no figure here — every call in this entry was made at `83de11c`,
   before §109's root `CLAUDE.md` existed to be read, and the merge that brings it in is *after*
   the run rather than before it, so the provider's argv did not change between P4's two phases.
6. `book-library/` was ignored and `book-library-p4/` was not. `--library` takes any root and has
   to be used whenever two runs share a title, so the run that exists because of the title
   collision left a generated library untracked, one `git add -A` from being committed. The glob
   is `book-library*/` now.

### 111.8 Anti-scope

Whether a brief moves the world (directed forges against an empty-brief control, the cross-forge
collapse rate, the between-Architect comparison) is the next direction and none of it is built
here. S5 is a parallel worktree's and §110 is its entry. World growth needs a re-forge for defect
8. Retrieval and per-scene selection for the writer stay `plan/world-architect.md` §5.1's design
note. Domain truth — whether a world can be wrong about the domain it literalised — is sketched in
the results note as a sign-flip control and deliberately not built: it needs a stated
domain-expert source for ground truth and this repository has none. No axis admitted, no counter
promoted, no directive authored, no bar declared, and no claim anywhere that a book with its world
on the page is a better book.

---

## 112. The world says whose book it is, and the exception it grants one person survives the gate

**Built 2026-08-22, from [`plan/handoff-protagonist.md`](handoff-protagonist.md).** Code:
`application/architect.py` (schema, one rule, records, gate complaints, three `report()` counters),
`domain/worlds.py` (`protagonist` as a second entity role; `edge`, `price`, `exception_to`,
`excepts`; `CardinalityShape.except_subjects`; `in_scope`; `cast_brief`; `protagonist_brief`),
`application/outline.py` (`cast` and `protagonist` inputs, two rules), `application/planner.py`
(`pov_character_id` threaded to the one production `packet_for`, `Point of view: <id>.` in the beat
line), `domain/axes.py` (a behaviour-preserving extraction, `proper_noun_introductions`), and
`research/quality-measurement/named_persons.py`. Measurements:
[`research/quality-measurement/protagonist-results.md`](../research/quality-measurement/protagonist-results.md)
and [`named-persons-results.md`](../research/quality-measurement/named-persons-results.md). The
pre-registration is [`plan/serial-pilot-4.md`](serial-pilot-4.md) §4 and **the run it registers has
not been made**.

**It is §112 and not §111, and the gap is deliberate.** The check in `CLAUDE.md` was re-run at
commit across `main` and all thirty `.claude/worktrees/*/plan/stage-0-decisions.md`, matching
`^#{2,3} [0-9]+` so a sub-section could not hide a claimed parent.
`claude/handoff-worldbuilding-plan-ae1861` has §111 **committed** on its branch and not yet merged
to `main`; the committed entry owns the number, so this one moves after it and §111 stays free for
that merge. That branch also adds a keyword argument to `render_outline_request` — see §112.7.

**What licenses it is a count, and it was taken before a line was written.** The operator read the
first two chapters of *What Takes* — Serial Pilot 3, the first book drafted on a world forged from
a directed brief — and named four defects ([`plan/reader-read-3.md`](reader-read-3.md)). Measured
against the machinery on `f947247`:

| | count |
|---|--:|
| occurrences of *protagonist*, *main character* or *hero* in `application/architect.py` | **0** |
| `StateRecord`s reaching `render_outline_request` | **0** |
| references to `domain/worlds` in `application/outline.py` | **0** |
| canon records loaded at the outline call site, and dropped | 328 of 328 |
| `packet_for` call sites in the repository | 27 |
| of those, passing `pov_character_id` | **0** |
| `PlanKind.PREMISE` constructions in `src/` | 1, `locked=True` |
| occurrences of "Kell" — the book's protagonist — in the forged world, its seed, its directives, its promises and its 328 canon records | **0** |
| forged cast members reaching the prose, of five | **1** |
| named persons the read counted across the two chapters | 17 |

**What shipped.** A world may now declare a `protagonist`: a cast id, the one declared rule or
cardinality shape that does not hold for them **by id**, the `edge` that gives them, what they
want, and the `price`. Required of the forge and refused there field-by-field on *emptiness* (the
2026-08-22 forge returned a world whose premise was the empty string under a schema that asked for
a string, conformed, and failed the shape check — $1.48); tolerated as absent by `records_for`, so
`plan/serial-pilot-2-world.json` regenerates to the same 329 records, gates clean, and emits not
one record of the new vocabulary. The declaration reaches the outline as `cast` + `protagonist`
(the request grows 1,785 → 4,856 characters on *What Takes*' own canon) and the writer as a
labelled facts block and one beat-line fragment.

**What was refused.** No verdict channel: no model is asked whether a hook is good, which premise
hooks more, or which of K worlds to pick. No bar. And no instruction anywhere about how to *handle*
a protagonist — the three added strings (the forge rule, the two outline rules, the beat-line
fragment) are each checked by a test for the vocabulary such an instruction would need.

### 112.1 The exception is the other object, and that is why scope could stay a role

`in_scope`'s docstring gives the reason a shape's scope is an `entity_role` and never a subject id:
a shape is a rule about a *kind* of thing, and one that named a carrier would be a fact about that
carrier wearing a rule's clothes. That argument is correct and is untouched. An exception is the
opposite object — a declared fact about **one** subject, which is what the word means — so it is
declared as one, as an `excepts` edge from the shape, and `in_scope` consults it before it looks at
roles.

Traced on `f947247`, a subject id put where a role belongs is **silently ignored**, which is worse
than refused: the schema enum excludes it, but that enum is prompt text — the CLI transport
serialises the schema into the prompt and `providers/base.parse_schema_payload` is shallow by
design and never descends into `worlds[].cardinality[].scope` — so the value survives parsing,
`records_for` emits it, `cardinality_shapes` builds a well-formed shape from it, and `in_scope`
matches it against a role table a subject id can never appear in. The shape then governs nobody and
looks exactly like a shape that governs everybody.

Three assertions are pinned together and **the third is the one that matters**: a shape that
excepts nobody fires on the planted violation exactly as before; the same violation on the excepted
subject yields zero findings; the same violation on a *different* subject of the same kind still
fires. A change that made the detector blind to the shape would pass the second and fail the third.
`tests/test_worlds.py::test_the_excepted_subject_is_the_one_the_maximum_does_not_bind` and
`tests/test_integrity.py::test_the_declared_exception_reaches_the_live_detector_and_binds_nobody_else`.

**One derivation, and it is a definition rather than an inference.** When a protagonist's
`exception` names a declared cardinality shape, `records_for` also emits `<shape> excepts
<protagonist>`. "X is the exception to S" and "S does not govern X" are one fact from two ends of
one edge and only the second is what the detector reads; a world that declared the first and forgot
the second would hand the writer an exception the gate still refuses, which is decoration.

### 112.2 Every packet this system had ever built was built for no one

`packet_for` has taken a `pov_character_id` since it was written and no production caller passed
one. The seam is not neutral while unused: `state.visible_to` is a whitelist in which an absent POV
**fails** a restriction, so any record carrying a `pov_visibility` would have been dropped from
every packet in the book and logged `not visible to POV (none named)`. Measured, that has cost
nothing so far — 0 of 328 records on a forged world carry one, because the iceberg is a claim with
a disclosure and not packet access control (§107.4).

So the observable effect of threading it is exactly the labelled heading, and that is what was
measured rather than assumed. Scene 1 of *What Takes* at `--context-budget 16000`, with and
without: items 305 → 305, established facts 224 → 224, hidden 23 → 23, tokens 7,493 → 7,493,
omitted 0 → 0, and a two-line diff — `Established facts:` becomes `Established facts known to
clerk_amble:`. The prompt diff is one line, and it sits before `Dramatic function:` and never after
`plans.scene_plan_line`, which stays last so `plan_search`'s K candidates keep differing in exactly
one place.

### 112.3 The counter nominated by the read does not reproduce the read

`research/quality-measurement/named_persons.py` counts distinct proper names a **chapter**
introduces, with first-appearance offsets — C6's budget is a scene-opening budget and it resets
four times before a reader reaches the end of one chapter. Run over 2,000 cached RoyalRoad chapters
per cohort and our own four:

| | median names per chapter | median per 1k words |
|---|--:|--:|
| RoyalRoad, all genres (n=2,000) | 17 | 10.15 |
| RoyalRoad, LitRPG tag (n=2,000) | **24** | **10.90** |
| *What Takes* ch. 1 / ch. 2 | **8** / **18** | 2.10 / 4.60 |
| *Reappraisal* ch. 1 / ch. 2 | 30 / 29 | 7.23 / 6.82 |

The two chapters the operator named as having too many names sit at the **11.8th** and **37.6th**
percentiles of the LitRPG cohort; the book this read did not complain about sits at the 63.5th and
61.6th. **A budget set from this distribution would license more names than the complained-about
book has.** This is the second time a counter nominated by a human read has failed to order the
case that nominated it — `opening_proper_nouns` placed the complained-about chapter at the 68.5th
percentile of published openings (§87 / `opening-counters-results.md`). Reported as a result (§61):
no bar is declared, and `plan/serial-pilot-4-craft.json` carries the chapter-grain constraint with
its number **unset** and outside the array any script reads, so it cannot be issued by accident.

What the null cannot rule out is stated with it: the read judged chapters whose named people were,
four of five, not the world's — arriving without declared ties, wants or roles — and "eight names"
and "eight names each of whom the reader has a reason to hold" are different experiences this
counter cannot separate. Nor can it separate a person from a place: it returns `February` and
`Marker` beside `Orne Marrow`, so every figure is a **name** count and the operator's person-only
hand count is reported beside it, never in place of it.

### 112.4 The craft file proposes two constraints and issues neither

`plan/serial-pilot-4-craft.json` carries C3, C4, C5, C6 and C8 verbatim from pilot 2, C7 with one
recorded edit — the lent-verb clause, from the read's fourth defect (*"Two rings of bark stood on
her wrist"*), which C7's own enumerated failures did not cover — and **two proposals in a
`proposed` array outside `directives`**: C9 (a chapter-grain introduction budget, `N` unset) and
C10 (the first sentence of the book and of each chapter belongs to the protagonist). Outside,
because `tools/serial-pilot-2-setup.ps1` issues every entry of `directives` verbatim and
`serial_pilot_check.py` counts them: an entry with a literal `N` in it would have been issued as a
directive reading "at most N people". Moving an entry into `directives` is the operator's act and
is what issues it. C10 is direction, it is the operator's, and **no form of it is in code**.

### 112.5 Pre-registered and not run

[`plan/serial-pilot-4.md`](serial-pilot-4.md) §4 registers P1–P5 with outcomes named in advance,
written before any paid call, and the run is **NOT RUN**: no forge, no pick, no book, no `pilot4/`,
no `serial4.db`. §4's P1 carries the handoff's stop condition as a named outcome — if the new rule
collapses the forge (`spread` well below pilot 3's measured **0.8959** on the same brief), the
change is unsafe and that is written up instead of the book being run. The pick rule is recorded
before the candidates exist: the first candidate clear of every gate whose real domain was not
forged in pilots 2 or 3.

### 112.6 Corrections in place

Three, all to [`plan/reader-read-3.md`](reader-read-3.md), which was written from the same texts:

1. *"the counter also flags `I'll` / `I'd` / `I've` as names — **four** false positives"* →
   there are **five**, across four scenes; scene 8 carries two. The real-name row
   (2, 3, 1, 2, 3, 1, 2, 2) is unaffected and C6 was honoured in every scene.
2. *"**None** of the forged cast reaches the page"* and *"'Amble' … appear only as a place-name and
   a surname the outline reused"* → the name-level intersection is **1 of 5**: `Amble` occurs six
   times, three as a vocative to a clerk. Whether that clerk *is* `clerk_amble` is a judgment with
   no instrument here. The direction of the finding is unchanged: four of five never reached the
   page and all seventeen named persons were written by a call that had never seen the cast.
3. *"his trade is first stated at word **804**"* → not wrong, and the apparent conflict with an
   independent re-derivation's 802 is a convention. A plain `str.split` puts `clerk` at 802 and
   `Assize` at 805; `domain/axes`' tokeniser puts `Assize` at **804**. The document's number is the
   tokeniser's. Every offset in the new counter is a tokeniser offset and says so.

`domain/axes.opening_proper_noun_names` was **not** changed. It is now
`proper_noun_introductions` with the offsets dropped, and
`tests/test_opening_counters.py::test_the_named_offsets_are_the_opening_names_with_positions` pins
that the names it returns are the ones it returned before — this counter's figures are quoted in
§87 and in `opening-counters-results.md`, and a silently drifted counter would redefine what those
numbers were about.

### 112.7 Two neighbours, and what the second merge owes

`plan/handoff-promise-ledger.md` landed at `f947247` (§110) and touched `summarize.py` only; this
branch builds on it and does not touch it.

`claude/handoff-worldbuilding-plan-ae1861` is **not on `main`** and adds its own keyword to
`render_outline_request` — a `world` brief whose contents include the cast, plus
`domain/world_brief.py` and a `StateRepository` on `NarrativePlanningStore`. Its §111 is committed
on that branch. The two changes are additive and independently correct, and both use the same
absent-rather-than-null idiom so each keeps its own byte-identical control. **Whoever merges second
owes one collapse**: a request that carries the same people twice is a request spending its budget
saying one thing. Neither branch should silently drop the other's — the protagonist is not in the
world brief, and the world brief's rules and claims are not here.

### 112.8 Found, not fixed

**Any cardinality shape with `group_key: "object"` can never fire.** `group_of(record, "object")`
returns the `object_ref`, and `detect_cardinality_violations` then counts *distinct object_refs
inside that bucket* — identically 1. So an object-keyed maximum is vacuous however it is declared,
and `c_one_owner_per_trait`, one of pilot 3's four shapes, is dead. Verified structurally and
empirically (2, 3 and more edges into one object all yield 0 findings). It is reported rather than
fixed because a fix changes detector semantics for every world already forged and could newly
refuse scenes in books already accepted — that is its own piece of work with its own control.

A relationship still reaches both the packet and the new cast brief in `state.describe`'s flat
form (`clerk_amble employed_by and is the only person who can find anything in it (the_assize)`).
It reads badly and it reads *identically* badly in both, which is why it was not improved here: the
sentence belongs in `worlds.project`, and changing it would change the packet of every book with a
forged world.

### 112.9 Anti-scope

No paid call of any kind was made. No forge, no pick, no draft, no re-pick, no redraft of any
accepted scene. `serial3.db`, `pilot3/`, `serial.db` and every `plan/serial-pilot-2-*` file were
read read-only and never written; the two measurements needing a mutable database ran on copies in
a scratch directory. No hook beat function, no change to `SIX_BEAT` or the arc template, no
instruction to any model about how to write, open, end or pace a protagonist's scene. No judge,
reader, persona, BCR, axis admission, pool change or pre-registration beyond P1–P5; `AXES` and
`COUNTERS` are untouched and `named_persons.py` is registered nowhere. No model ranks, scores or
selects anything; `domain/discrimination.py` is byte-frozen. No human reader, label or solicited
judgment entered anything here (§95) — the operator's read is a defect harvest and not data, and
no acceptance read was spent. No bar declared. The outline inventing answers to forged mysteries,
the `lock-constraints` on `serial.db`, the chapter-ending clause and the `[STATUS]` line all remain
where they were. RS1 holds: nothing under `src/litharness/` references a corpus, a digest or a
RoyalRoad text, and no anchor or corpus prose crossed into any prompt, example or rule.

---

## 113. The genre's one unbreakable rule became a declared fact the system forges, schedules, tells, prints and counts

**Built 2026-08-22, from [`plan/handoff-numbers-go-up.md`](handoff-numbers-go-up.md).** Code:
`domain/worlds.py` (`STANDS_AT_PREDICATE`, `ladder_of`, `rung_index`, `criterion_of_rung`,
`standing_of`, three validator complaints, one projection sentence), `application/architect.py`
(one optional `standing` on the protagonist, one new rule, three rule amendments, one placed
record, five gate complaints, five `report()` counters), `domain/world_brief.py` (`Ladder`,
`ladder_for`, `LADDER_RULES`), `application/outline.py` (an optional `standing_milestones` in
`OUTLINE_SCHEMA`, `_standing_milestones`, `standing_milestone_records`),
`domain/extraction.py` (`standing_target`, `standing_example`, one canon-writable shape in
`extract_graph_facts`), `application/planner.py` (two `render_prompt` inputs, threaded from the
production call). Measurement: `research/quality-measurement/standing.py` and `system_lines.py`,
with `numbers-go-up-results.md` and two committed result files. Pre-registration:
`plan/serial-pilot-5.md` §4 and `plan/serial-pilot-5-craft.json`. **The paid run has not
happened**, so §5 and §6 of that pilot are empty and nothing here is a claim about prose.

### 113.1 What was measured first, on four forged worlds and two live books

The operator's frame is the genre's four working rules, and rule 1 is *the numbers go up, and the
power is personal to the main character*. Audited before anything was built
([`research/quality-measurement/numbers-go-up-results.md`](../research/quality-measurement/numbers-go-up-results.md) §1):

- **Two of four worlds declared an ordinal chain of at least three ranks; not one cast member of
  any of the four stood anywhere on any chain.** `ranks_at` is emitted for *creatures* only — 2,
  3, 2 and 3 abundance notes. A ladder with nobody on it is a costume with nobody in it.
- **The one ordinal chain pilot 3 produced runs the wrong way.** *Senior Water* lists
  `first_water` — the most senior right — first, so its `precedes` chain reads
  `first_water → morning_right → tail_right → wash_right` and a reader counting *up* it counts a
  person getting weaker. Nothing in the rule text said which end came first.
- **3 of 3 worlds on the brief `"progression fantasy"` inverted a piece of rule 1**, in their own
  words: "portable personal power", "that a gain can be created", "monotonic growth". The
  inversion rule had no floor and deleted the genre's one non-negotiable default three times out
  of three.
- **The numeric apparatus is off on the forged book.** `serial3.db` holds no `status_snapshot`,
  so `speaks_system_voice` is False, `system_voice_example` is `None`, no milestone was ever
  scheduled, and `progression_target` answers `None` at every position of both live books (0 of 8
  and 0 of 1).
- **The chain *declare → ask → print → read* was broken at *ask*.** `grep -c graph_line
  application/planner.py` → 0. All four worlds *declared* a `graph_line`; none of the twenty
  declared phrases meant "stands at"; *What Takes* declared `ASSIZE` and **printed zero lines
  across 7,704 words in 8 scenes**.

**Two of the handoff's own premises did not survive the measurement**, and both are corrected in
the results note rather than quietly fixed: `scene_summaries.delta_json` is **non-null on all 16
scenes** (`DELTA_FIELDS` landed 2026-08-17, before both pilots) rather than null, and *What
Takes* **did** declare a graph line rather than none. The second makes the defect narrower and
the fix smaller than the handoff supposed.

### 113.2 What shipped, and the one shape it is

**A rank ladder *is* the number, and the number is derived.** The operator's direction — "bronze
to gold rank advance is the same as the number going up; say bronze is 1 and gold is 3" — makes
the quantity a rung's 1-based place in a declared chain, computed by `rung_index` when asked and
never stored: an integer beside the chain is a second answer to "which rung is third".

The standing is **one flat edge**, `subject stands_at → rung` with the criterion in the value slot
exactly as `precedes` carries it. Flat because the page can only print a flat edge and the forge's
copy of the same fact must be readable by the same function; the reified `EVALUATION_*` triple is
left for the case §8.3 built it for. No new ontology type, no new comparator, no new `GROUP_KEYS`
member.

- **Forge.** One optional `standing` on the protagonist, required in the forge request (refused by
  `worlds_from` as a missing premise is) and tolerated as absent by `records_for`, so every world
  forged before today regenerates byte-for-byte. One new rule (an `ordinal` criterion with a chain
  of at least three, **lowest first**, each rung with a `visible_form` and a `cost_to_reach`; the
  standing below the top). Three amendments: the inversion rule may remove any default **except**
  that one; a world with a ladder declares a `graph_line` carrying a `stands_at` phrase; the
  no-levels rule gains one clause saying the rungs are this world's numbers. Five membership
  complaints in `gate_candidate`; five counters in `report()` including `inversion_text` verbatim,
  so the run record can be read beside §113.1's four worlds without a classifier.
- **Schedule.** The ladder rides *inside* §111's world brief. `_standing_milestones` mirrors
  `_milestones` and adds the check it does not make — direction: `rung_index` non-decreasing from
  the opening and at least one milestone strictly above it. Refuses the whole outline on failure,
  for §55's reason. `standing_milestone_records` writes `PROPOSED` `stands_at` edges, ids derived
  from position so a replay converges.
- **Writer.** `standing_target` is `progression_target`'s twin and carries both rungs with their
  numbers; `standing_example` fills the book's own graph line with the live rung.
  `render_prompt` renders them in the numeric block's **own wording** and one filled example.
- **Read-back.** `extract_graph_facts` writes one shape as `ACCEPTED_CANON` at the position: a
  `stands_at` edge whose subject canon already uses and whose object is a declared rung of a
  declared chain. Nothing is minted, no model returned it, a recorded decision accepted the prose,
  and this is a mechanical restatement — the module docstring's own argument for the `[STATUS]`
  line. A page-minted rung stays `PROPOSED` and is promoted only by later causal reuse.

**One defect the wiring exposed and fixed.** `extract_graph_facts`' `seen` dedupe counted the
outline's own `PROPOSED` rung schedule, so the one scene that printed a scheduled rise would have
read nothing. The plan and the page are different claims; only the page makes the rise true.

### 113.3 The counters, and no bar over any of them

`research/quality-measurement/standing.py` on the two live books — **0 rungs, 0 standings, 0
rises, 0.0 graph lines per 1k words on both**, and `other_subjects` empty, which is P4's prior for
everyone rather than only for a protagonist neither book declares.

`research/quality-measurement/system_lines.py`, reusing `domain/axes._SYSTEM_LINE`,
`strip_system` and `system_digit_count` rather than a second regex. **Every leg ran; nothing is
NOT RUN.**

| | n | % with ≥1 system line | lines / 1k (median) | units with ≥2 | % of those whose digits differ |
|---|--:|--:|--:|--:|--:|
| published chapters | 4 | 50.0 | 0.4855 | 2 | 100.0 |
| own drafted scenes (24 databases) | 152 | 11.84 | 0.0 | 1 | 0.0 |
| RoyalRoad LitRPG (shards 3 + 30) | 14,156 | 2.32 | 0.0 | 144 | 43.75 |

The two *What Takes* chapters carry **zero** system lines across 7,722 words; the two
*Reappraisal* chapters carry 4 and 5. Within story at five chapters minimum: 394 stories, mean of
story means 2.59%, 65 of them with at least one such chapter. The era split is printed unasked
because `tricolon_rate` died to exactly that control — `declared_ai_2025` 8.29%,
`undeclared_2025` 2.66%, `human_pre_llm` 1.16% — and **nothing is concluded from it**; the
seven-fold gap is the shape `tricolon_rate` had before its own control landed.

**No bar is declared over any of these and none may be read in.** How often a standing should move
is the operator's to set over this distribution. `_SYSTEM_LINE` reads a bracketed all-caps tag and
nothing else — the 21-book fitness corpus renders its system voice unbracketed and contributes
zero — so **every percentage above is a floor, not an estimate**; and `digits differ` compares
consecutive system lines and cannot tell a rise from a fall. The schedule validator enforces
*shape* (declared rungs, non-decreasing, at least one rise), which is the class of check
`_milestones` already makes, and not a rate. §81, §85, §87 and §89 are each a bar declared over a
quantity that could not do what it said.

### 113.4 What was refused

**No taste in code.** No adjective and no verb about how a rise should read enters any prompt,
template, beat function or system message. The standing block reuses the numeric block's own
sentence — *the book's plan has this reaching that later on; move it toward that where the events
warrant it* — because a standing and a status snapshot are the same class of fact and a second
register would be this system deciding one of them matters more.
`test_the_standing_block_carries_no_verb_and_no_adjective` and
`test_the_ladder_rules_ask_for_a_schedule_and_never_for_a_feeling` check the text against nineteen
words such an instruction would need, and
`test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome` was widened from one rule
to all three that now mention the protagonist. The craft rule that *would* ask for the rung's
visible form on the page is drafted as **C11** in `plan/serial-pilot-5-craft.json` `proposed`,
**not issued** — it is the operator's, like C5.

**No verdict channel.** No model is asked whether a ladder is good, which rung is right, which of
K worlds to pick, or whether a rise lands. The forge stops and a person chooses; the pick rule for
pilot 5 is written down before the candidates exist and is arithmetic (first gate-clear candidate
whose declared domain was not forged in pilots 2–4). E6 is untouched; `domain/discrimination.py`
is byte-frozen.

**No monotone ontology.** `research/progression-generalization.md`'s refusal of "monotone power as
the definition of progression" stands and nothing here touches it. Comparators, partial orders and
revocable rank are exactly as they were. What was added is a **genre contract the directed brief
declares**: on this brief, the protagonist's standing on one declared ordinal ladder rises within
the arc being written, checked per comparator as `plan/state-model-abilities.md` §4 says an
`ordinal` is checked. A world that wants a fall writes it in later by directive.

**No cardinality gate.** "One standing per ladder at a position" is not declarable with today's
`GROUP_KEYS`, and a subject legitimately on two ladders holds two `stands_at` edges at one
position. No group key was added; the case is counted in `standing.py` and the open decision is
named in `plan/world-architect.md` §8.

**Backwards compatibility is asserted, not hoped.** A world that declares no standing makes
byte-identical records and reports `ladders: 0`
(`test_the_pilot_package_regenerates_the_world_it_was_run_on` stays green); a book whose canon
declares no chain renders today's outline request and today's drafting prompt byte-for-byte
(`test_a_book_with_no_ladder_is_asked_nothing_about_one`,
`test_a_book_with_no_ladder_renders_the_prompt_it_rendered_before`); both golden fixtures extract
exactly what they extracted before
(`test_the_golden_fixtures_extract_exactly_what_they_extracted_before`).

**Anti-scope.** No instruction about how to write, feel, pace or celebrate a rise; no "level-up"
beat function; no change to `SIX_BEAT`, the arc template or any chapter-ending default. No HP / MP
/ Gold / XP sheet for a forged world and no change to `DEFAULT_SHEET`. No judge, reader, persona,
BCR, axis admission, pool change or pre-registration beyond P1–P5. No human reader, label or
solicited judgment entered anything here (§95) — no acceptance read was spent and no operator read
is treated as data. RS1 holds: nothing under `src/litharness/` references a corpus, a digest or a
RoyalRoad text, and no anchor or corpus prose crossed into any prompt, example or rule; the one
real-world fact in a rule text is cited in a code comment pointing at this file, never named in
the prompt. `serial.db`, `serial3.db` and `pilot3/` were read and not written — every measurement
ran against a copy or read-only, and no accepted scene was redrafted and nothing re-picked. No
claim anywhere that a book whose number goes up is a better book.
