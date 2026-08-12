# Stage 0 decisions

**Status:** Slices 1-3 built and green — 119 tests (+3 opt-in live), ruff clean, mypy
strict clean. Slice 1 is the model-free manuscript spine; slice 2 the Conductor skeleton
(tick, instance lease, job selection, digest, outbox dispatch, crash recovery); slice 3 the
four provider adapters with their conformance suite and the billing guard.

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
one. Carried in `metadata` pending promotion to a real 1.x field.

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

`domain/jobs.py`. Contracts' `JobRecord` has no lease concept at all, confirming §20.3's
list. A lease is a holder plus a wall-clock expiry; claiming is a single `BEGIN IMMEDIATE`
transaction so two overlapping cron ticks cannot both win.

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

## What these slices do not include

Deliberately deferred, in the order they should land:

1. **Directive ingestion** (§4.3) — the plan scopes the Stage 0 Conductor to "tick, lease,
   job selection, digest stub", and a directive inbox without the Narrative Planner to
   interpret it would be a queue nothing can read.
2. **A real work-selection policy.** `fifo_selector` is a placeholder behind a
   `WorkSelector` protocol. §4.1 wants selection to be a policy over the book's state —
   unblocked beats, findings by severity, derived artifacts to recompute — which needs a
   plan graph and a findings store that do not exist yet. FIFO is honest about being a
   placeholder; a cleverer arbitrary ordering would not be.
3. **Retry backoff.** Retries are immediate on the next tick, bounded only by the attempt
   budget. A `next_attempt_at` column would add backoff and is not invented until something
   needs a specific delay.
4. **Wiring the registry into the Conductor.** The adapters exist and conform; no job
   handler consumes them yet, because the first real handler is a Stage 1 concern (a scene
   draft needs a plan and a context packet). The seam is `Conductor.handlers`.
5. **Contracts 1.x minors** (§20.3) — and these slices are what make them safe to write:
   `lease_holder`/`lease_expires_at` on `JobRecord`, `block_kind`/`block_payload` and a
   lock enum on `ManuscriptNode`, and the Conductor `EventType` additions are now shapes
   proven by a consumer rather than guesses.

## Two fixes this work forced upstream

Both in `litharness-contracts`, commit `2d1e759`, found by being its first strict-typed
consumer:

* **No `py.typed` marker** — mypy skipped the package entirely, so every consumer's
  annotations against contract types were unchecked.
* **No `__all__`** — under `--no-implicit-reexport` the package re-exported *nothing*, so
  `lc.Finding` and `lc.ManuscriptRevision` failed to resolve at exactly the boundary the
  package exists to define. 90 names now exported.

All consuming suites stayed green: contracts 113, ContinuityEvaluation 42,
LongRangeContext 14, BookWorldState 100, LitHarness 76.
