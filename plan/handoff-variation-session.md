# Handoff: a bounded VariationSession for deterministic candidate repair

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose goal is
superhuman literary quality with no human in the production loop. Your task is one component:
a durable, mediated **agentic variation loop** — called a `VariationSession` — applied first
and only to **candidate-local repair**. It is not a prose hill-climber, it does not replace
the Conductor, and it must not introduce any literary-quality ordering.

File names and § numbers below were verified on 2026-08-21. If the repo has drifted, the repo
wins; re-anchor rather than following this document into a stale reference.

## Why this exists (context you need, then stop reading context)

NVIDIA's AVO work (arXiv 2603.24517; ARC-AGI-3 blog post, Aug 2026) demonstrated that an
evolutionary search loop improves sharply when the variation step is an autonomous agent that
can inspect the lineage of prior candidates and scores, consult a knowledge base, propose an
edit, evaluate it, diagnose the failure, and revise — repeatedly — before anything is
committed. LitHarness already has the other half of that system: immutable revisions, pure
pre-commit gates, recorded policy decisions, and a linear head. What is missing is exactly the
durable multi-attempt session in front of the existing commit path.

The central dis-analogy, which shapes every constraint below: AVO's scoring function is
ground truth (kernel correctness, measured TFLOPS). Ours is not. No instrument in this repo
currently holds the authority to order prose by quality (see README "Nothing in it yet
measures whether a book is any good", and stage-0 §98/§102: F3 certifies a structural
mechanism, not taste). A variation loop that optimizes a proxy score is a Goodhart machine.
So this session optimizes nothing: it repairs to **mechanical feasibility** and commits the
first candidate that passes.

## Read before writing anything

1. `CONTRIBUTING.md` — all of it, especially "Dependency direction", "Persistence and audit
   rules", "Before proposing a quality or craft metric", and "Scope discipline".
2. `PLAN.md` and `plan/stage-0-decisions.md` — skim the § index; read §4.1 (tick contract),
   §4.2 (park/escalate, "the failure mode is a parked unit, never a spin loop"), §95 (scope
   axiom: no solicited judgment, ever), and the most recent entries (§98–§102) for the
   current state of the quality programme and the house style of decision entries.
3. `src/litharness/application/conductor.py` — the tick contract in code. One bounded unit
   per tick; handlers return events and never write to the store; ticks are idempotent.
4. `src/litharness/application/repair.py` and `tests/test_repair_workflow.py` — the existing
   Stage-2 evaluate → repair → propagate chain you are extending. Note `MAX_AUTO_REPAIRS`,
   the `_REPAIR_SCHEMA` structured-output precedent, priorities, and the budget/calibration
   veto imports.
5. `src/litharness/domain/policy.py` (`GateKind`, `GateOutcome`, `PolicyDecision`, `decide`,
   `gates_for_patch`), `domain/patch.py`, `domain/candidates.py`, `domain/revision.py`,
   `domain/budget.py`, `domain/failures.py`.
6. `src/litharness/adapters/sqlite_store.py` and `migrations/` — storage idioms, digest
   conventions, and the next migration number (030 at time of writing).
7. `src/litharness/providers/` — the provider registry, the pinned frontier provider, and
   the deterministic fake used by the test suite.

## Deliverable 1 — durable typed state

Add, via the next numbered migration plus domain types plus store ports (respecting the
dependency direction rules):

- **`variation_sessions`** — id, objective kind (an enum with exactly one member for now:
  `candidate_repair`), target references (finding id, candidate id, revision id as
  applicable), status, per-session limits (internal variation steps, provider calls,
  evaluations, tokens, wall-clock time, cost — each its own column, each independently
  enforceable), live counters against those limits, terminal outcome, and open/close
  instants. Follow the store's existing id-derivation and digest idioms.
- **`variation_attempts`** — session id and ordinal, parent candidate and revision ids, the
  proposed edit or patch (by reference, following the store's existing artifact-reference
  conventions — do not inline large text), the exact evaluation vector and gate diagnostics
  it received, a strategy classification (free enum-ish string, recorded not enforced —
  e.g. `structural` vs `local_patch` — so the "structural early, micro late" hypothesis can
  later be measured rather than assumed), provider, model, tokens, cost, evaluations
  consumed, wall time, outcome (`committed`, `rejected_gate`, `rejected_budget`,
  `abandoned`, `superseded`), and the reason for abandonment when abandoned.
- **`knowledge_items`** — durable records derived from attempts (e.g. "patches that touch X
  keep failing gate Y for reason Z"), each carrying the supporting attempt ids as evidence
  links. Consulting one is recorded.

Every attempt is recorded, including failures. AVO's paper reports a committed lineage of 40
and discards the record of 500+ explored directions; this design improves on that
deliberately. The session's state is typed, inspectable rows — never hidden conversation
history. If the session needs the model to see history, it re-renders it from these rows.

## Deliverable 2 — a mediated action surface, nothing else

The variation agent is the model speaking through the existing `TextGenerator` / provider
registry with structured output (the `_REPAIR_SCHEMA` pattern in `repair.py` is the
precedent). It chooses among exactly these actions, each a typed request the harness
executes and records:

- `inspect_lineage` — read prior attempts/candidates for the target, rendered from the
  durable rows.
- `consult_knowledge` — read matching `knowledge_items`; the consultation is recorded.
- `propose_candidate` — submit a bounded patch (through `PatchPolicy` / `apply_patch`).
- `evaluate_candidate` — run the deterministic gates; receive the exact evaluation vector
  and gate diagnostics, which are also written to the attempt row.
- `commit` — *request* acceptance from the existing policy path (`gates_for_patch` →
  `PolicyDecision` → `decide`). The existing commit path remains the sole authority; the
  session holds no direct write access to canonical state.
- `stop` — close the session with a typed outcome and reason.

No shell, no filesystem, no unrestricted Claude Code tools, no new provider integration, no
direct canonical writes. If an action the model requests is not on this list, that is a
malformed response to handle, not a capability to add.

## Deliverable 3 — Conductor integration

One agent action per Conductor tick. Each variation step is a job executed by a handler that
obeys the existing contract: it returns events, writes nothing itself, and the Conductor
commits events with the job-status change in one transaction. Session state persists between
ticks in the tables from Deliverable 1, so a restart resumes cleanly and a replayed tick is
refused at the store, not reasoned about.

Enforce every limit separately, with a typed refusal outcome naming which limit tripped.
Include deterministic stall detection that closes the session rather than spinning: at
minimum, an identical-patch cycle (same patch digest proposed twice) and N consecutive
attempts failing the same gate for the same reason (pick N deliberately and record why).
A tripped limit or stall parks/closes; it never loops. The strategy-proposing
`VariationSupervisor` from the design discussion is **out of scope** — the stall detector
only stops; it does not redirect. Record in your decision entry what a future supervisor
would need from the data you are laying down (it reads only the attempt/evaluation
trajectory; it can never touch prose, canon, locks, gates, or budgets).

## Deliverable 4 — first use: candidate-local repair

Wire the session into the existing repair chain as an alternative handler for repairing a
finding: draft → run deterministic gates → feed the exact failure diagnostics back →
propose a bounded patch → re-gate → repeat within limits.

Acceptance is **lexicographic**, and only the first tier is in play in this deliverable:

1. **Mechanical feasibility** — locks, shape, continuity, state, and budget gates, exactly
   as the existing policy path defines them.
2. **Non-regression on protected objective dimensions** — the full evaluation vector is
   recorded per attempt and per configuration; nothing here may be traded away silently.
3. **Pareto improvement on an explicitly authorized objective** — none is authorized in
   this deliverable.
4. **No literary-quality ordering.** No instrument has earned that authority. The session
   commits the **first mechanically valid candidate** and stops. It never chooses among
   valid candidates by any score, ranking, or preference signal.

An aggregate (e.g. a geomean) may appear in *reports* for readability, but it is never an
acceptance criterion and must never be presented in a way that hides a regression in a
single protected configuration — reports show the full vector alongside any aggregate.

## Deliverable 5 — comparison and report

Compare the new session-based repair against the existing fixed repair path
(`repair.py`'s current regeneration behaviour, `MAX_AUTO_REPAIRS`) under the same model and
the same total budget, on the golden repair cases (the `litharness-contracts` fixture books
and the cases exercised by `tests/test_repair_workflow.py`). Use the deterministic fake
provider for suite-level determinism; if you make any real-provider runs, follow the repo's
replay/digest conventions so they are reproducible.

Report, per path: gate-pass rate, cost per feasible commit, actions per feasible commit,
and repeated-failure rate (same gate, same reason, consecutive). State results as they come
out, including a null or negative result — "the agentic path bought nothing on these cases"
is a valid and publishable outcome of this work. Name no bar you have not checked is
attainable (range, direction, unit, non-emptiness — the declared-bars rule in the decision
log). Held-out-book and length transfer is a later study; do not claim it.

## Hard boundaries (violating any of these is failing the task)

- No general prose hill-climbing; no selection among mechanically valid candidates by any
  quality proxy.
- No new quality or craft metric (CONTRIBUTING.md has a section on exactly this).
- Context-packing search is the *next* objective target after the gold suite grows
  binding-budget, long-book, evaluate, and repair cases — do not start it here.
- Reward-guided prose selection is gated behind a simulated-readership force clearing its
  own controls plus held-out validation — nowhere near this deliverable.
- The Director and all narrative-role code stay untouched. The `VariationSupervisor` is a
  distinct future component, not a Director variant.
- Scope axiom (§95): nothing you build may solicit judgment from anyone, and no human data
  enters any loop. Measurement is LLM-only.
- The variation agent never gets tool access beyond the six mediated actions.

## Working agreements

- `uv run pytest` green before and after; new behaviour gets tests beside the existing ones
  (`tests/`), using the fake provider and injected time like the rest of the suite.
- Migrations are append-only and numbered; follow the persistence and audit rules in
  CONTRIBUTING.md (immutability, event-with-artifact atomicity, digests).
- Record the design as the next § entry in `plan/stage-0-decisions.md`, in the house style:
  what was decided, why, what was rejected, and an explicit anti-scope subsection carrying
  forward the boundaries above (see §101.5 for the pattern). Update PLAN.md only where it
  already points at repair behaviour.
- Commit messages in this repo are full sentences describing what changed and what it
  means; match that.
- Parallel sessions work in this repo. Keep the diff scoped to this feature; if you find
  unrelated defects, record them, don't fix them here.

## Definition of done

1. Migration + domain types + ports for `variation_sessions`, `variation_attempts`,
   `knowledge_items`, with every attempt (including failures) recorded and evidence-linked.
2. The six mediated actions implemented behind the provider registry with structured
   output; commit requests flow through the existing policy path only.
3. Conductor-integrated: one action per tick, independent limit enforcement with typed
   refusals, deterministic stall closure, restart-safe.
4. Candidate-local repair works end to end on the golden cases: first mechanically valid
   candidate commits; full vector recorded per attempt.
5. The comparison report from Deliverable 5 exists with all four metrics for both paths,
   stated faithfully.
6. Decision entry appended; tests green; no hard boundary crossed.
