# The bounded variation session

A durable, mediated, multi-attempt loop placed **in front of** the existing commit path, applied
first and only to candidate-local repair. It is not a prose hill-climber, it does not replace the
Conductor, and it introduces no literary-quality ordering.

Design decision entry: [stage-0 §105](stage-0-decisions.md). Code: `domain/variation.py`
(vocabulary and arithmetic), `application/variation.py` (the two handlers),
`adapters/sqlite_variation.py` (persistence), `migrations/030_variation_sessions.sql`.
Comparison harness: `tools/variation_repair_comparison.py`; its output is
[variation-comparison.json](variation-comparison.json).

## 1. What was missing, and what was already here

NVIDIA's AVO work reports that an evolutionary search improves sharply when the variation step is
an agent that can inspect the lineage of prior candidates, consult a knowledge base, propose an
edit, evaluate it, read the failure, and revise — repeatedly — before anything is committed. This
repository already had the other half: immutable revisions, pure pre-commit gates, recorded policy
decisions, a linear head, and a park/escalate ladder whose failure mode is a parked unit rather
than a spin loop. What was missing was exactly the durable multi-attempt session.

The fixed repair path spends **one** provider call per unit of work. If the resulting patch is
refused, `decide` returns RETRY, the Conductor fails the job, `requeue_failed` revives it, and the
handler runs again — against the same prompt, with no knowledge that anything was refused or why.
Three of those and the unit poisons. The model is never told what happened.

## 2. The dis-analogy that shapes every constraint

**AVO's scoring function is ground truth. Ours does not exist.** A kernel is correct or it is not;
a measured throughput is a number. Nothing in this repository is entitled to order prose by
quality — `research/quality-measurement/BRIEF.md` is the ledger of twenty proxies that claimed to
and died to a control, and stage-0 §98/§102 record that F3 certifies a structural mechanism and
predicts nothing about readers. A variation loop that selected among *valid* candidates by any
score would be a Goodhart machine wearing an audit trail.

So this session optimises nothing. Acceptance is **lexicographic** and only the first tier is in
play:

1. **Mechanical feasibility** — locks, shape, span staleness, preservation and cited scope, exactly
   as `apply_patch`, `gates_for_patch` and `decide` already define them, plus the day's budget.
2. **Non-regression on protected objective dimensions** — the full gate vector is stored per
   attempt so nothing can be traded away silently.
3. **Pareto improvement on an authorised objective** — none is authorised.
4. **No literary-quality ordering.** The session commits the **first** mechanically valid candidate
   and stops.

`tests/test_variation_session.py::test_the_variation_loop_imports_no_selection_machinery` makes
tier 4 structural: neither variation module may import the tournament's `select_winner` or the
pairwise preference engine.

## 3. The shape

**Four tables** (`variation_sessions`, `variation_patches`, `variation_attempts`,
`knowledge_items`). The session row carries its target, six independently enforceable ceilings,
the live counters beside them, what it has consulted, and how it ended. Attempt rows carry the
patch *by reference*, the exact gate vector the patch received, per-veto diagnostics, a recorded-
never-enforced strategy label, provenance and cost. Knowledge items are deterministic claims about
repeated mechanical failure with the attempt ids that support them.

**Six mediated actions and nothing else**: `inspect_lineage`, `consult_knowledge`,
`propose_candidate`, `evaluate_candidate`, `commit`, `stop`. The agent is the model speaking
through the provider registry with structured output. No shell, no filesystem, no store access, no
tools. A response naming anything else is counted as unusable and bounded, never accommodated.

**`commit` does not commit.** It requests acceptance from the existing policy path, and the
precondition — an attempt already evaluated with every blocking gate passing — is enforced by the
harness. A refused request is recorded and the session continues within its ceilings.

**One action per Conductor tick, one job per action.** Job ids are content-derived and insertion is
`INSERT OR IGNORE`, so the step ordinal is in the payload and therefore in the id; each step mints
the next step's job inside the same transaction that records its own outcome. The whole of a
session's state is rows, so a restart resumes with what an uninterrupted run would have had, and a
reclaimed lease meets a recorded ACCEPT and returns without re-spending the call.

**Every ceiling separate, every refusal named.** Steps, provider calls, evaluations, tokens, wall
clock, dollars. A tripped ceiling closes the session and parks the step job with a BUDGET gate, so
the attempt is refunded and the exception queue names which ceiling stopped it.

**Stalls close; they never redirect.** The same patch proposed twice, three consecutive refusals
with the same gate-and-veto signature, or three unusable responses in total. Choosing a
different strategy in response is a supervisor's judgment; no supervisor is built (§105.6).

## 4. The comparison

`tools/variation_repair_comparison.py`, run 2026-08-21 on the deterministic ladder provider.
Fifteen cases: three books (the six-scene book `tests/conftest.py` builds, and the `mystery` and
`litrpg` golden fixtures from `litharness-contracts`) crossed with five ladders, where the ladder
is the ordered sequence of replacement strings **both arms draw from**. `rung1`..`rung4` name the
position of the first replacement that clears the gates; `never` has none.

Both arms run the same generator, the same `BudgetPolicy`, and the same planted located finding.
What differs is the harness and nothing else.

| case | fixed: commit / calls / gates | session: commit / calls / gates | session outcome |
|---|---|---|---|
| `*:rung1` | yes / 1 / 1 pass of 1 | yes / 3 / 2 of 2 | committed |
| `*:rung2` | yes / 2 / 1 of 2 | yes / 5 / 2 of 3 | committed |
| `*:rung3` | yes / 3 / 1 of 3 | yes / 7 / 2 of 4 | committed |
| `*:rung4` | **no** / 3 / 0 of 3 | **no** / 6 / 0 of 3 | stalled_repeated_gate |
| `*:never` | **no** / 3 / 0 of 3 | **no** / 6 / 0 of 3 | stalled_repeated_gate |

Identical on all three books. Totals over the fifteen cases:

| metric | fixed | session |
|---|---|---|
| feasible commits | **9 / 15** | **9 / 15** |
| gate runs | 36 | 45 |
| gate-pass rate | 0.250 | 0.400 |
| provider calls | 36 | 81 |
| tokens | 16,866 | 43,260 |
| calls per feasible commit | **4.00** | **9.00** |
| tokens per feasible commit | 1,874 | 4,807 |
| actions per feasible commit | 4.00 | 9.00 |
| repeated-failure rate | 0.556 | 0.556 |

### 4.1 The result, stated as it came out

**The agentic path bought nothing on these cases and cost 2.25x the provider calls and 2.31x the
tokens per feasible commit.** Same books, same generator, same budget, same nine commits. That is
the finding, and it is the one the design's own reasoning predicts rather than an accident:

**The stall detector stops the session on the same attempt the fixed path's budget stops it, and
the reason is structural to this benchmark.** Every mechanical veto a replacement *string* can
provoke against a small cited span is the length one, so every failure here carries one signature —
and `REPEATED_FAILURE_LIMIT` is 3 for the same reason `Job.max_attempts` is 3. The session cannot
reach a rung the fixed path could not. `test_the_stall_detector_stops_the_session_where_the_fixed_path_poisons`
pins that, so a change to either constant fails a test and gets argued.

**The gate-pass rate is higher for the session and the difference is an artefact, not a win.** A
committing session runs the gates twice on the winning candidate — once for `evaluate_candidate`
and once for the commit request — so its numerator gains a pass the fixed path never had the
opportunity to record. Read `calls per feasible commit` instead; it is the metric with the same
denominator on both sides.

**Where the extra calls go.** Three per committed attempt cycle against the fixed path's one:
propose, evaluate, commit. That is the price of separating the actions so each is one bounded unit
per tick, and on a case the fixed path already solves it is pure overhead.

### 4.2 What this comparison cannot say

It compares **harnesses, not models**. The deterministic fake has no capability to measure, so the
ladder is a mechanical stand-in and the scripted agent uses only the *fact* of a refusal to choose
its next action — never an oracle, and never the content of the diagnostics. The mechanism the
session exists for — a model that reads why its patch was refused and writes a different one — is
exactly the thing this benchmark holds constant. **So this is evidence about cost and control
flow, and no evidence at all about whether feedback helps.**

Two things would be needed to ask the real question, and neither is done here: a case family whose
mechanical failures carry *different* signatures (so the stall predicate stops bounding the
comparison), and a real provider run under the repo's replay conventions. Held-out books and
length transfer are a later study and are not claimed.

### 4.3 What follows from it

On the evidence in hand the fixed path remains the default, and `--variation-repair` is off. That
is not a provisional hedge: PLAN.md §20.7's standing verdict — *"the 0.22 that looked like a repair
problem was a detection problem"* — is unmoved by this table, and a mechanism that costs 2.25x for
the same nine commits is not an argument to move it.

What the session has bought that the fixed path cannot is **the record**: every attempt, its full
gate vector, its cost and its refusal, durably and by reference. That record is the input any
future measurement of feedback-driven repair would need, and it did not exist before.
