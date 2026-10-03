# Working in LitHarness

LitHarness writes LitRPG serial chapters from a short brief. The runtime is `litharness/`: stdlib
Python, agent CLIs spawned only by `litharness/transport.py`, data in plain files under `$LITHARNESS_HOME`.
[README.md](README.md) has the verbs. [LEARNINGS.md](LEARNINGS.md) says why the design is this small;
[DECISIONS.md](DECISIONS.md) records the standing choices. The incumbent lives only at the tag
`legacy/incumbent-2026-09-27` and the branch `legacy/main`; never bring its files back to main.

One agent, Codex or Claude Code, writes for the whole project, and `python -m litharness agent NAME`
switches it. Nothing may assume which: a call takes its `agent`, and a new CLI is one row of
`transport.AGENTS` plus a canary pass.

## The loop

1. The operator reads a chapter. Their read is the only quality gate: no model judges or selects.
2. Each item they name is located, either in our text (a template, the brief, a forwarded file) or
   in the model's. Record it in `reads/NN.md`: their words, the located cause, what it became.
3. The fix is the cheapest class that works: delete prompt text, then a bible or plan field, then a
   check that can redraw, then a mechanical transform. A clause comes last, only as a prohibition of
   the specific thing, and only with a failing fixture. A register or sentence-craft clause never.
4. Redraw (`redraw --from N`) and hand the chapter back.

The coordinator hand-reads every chapter against `reads/CHECKLIST.md`, line by line, never delegated,
and records residuals only, never a pass. The checklist, reports, reads and fixtures never reach a
model.

## Admission rule (all five apply)

1. The trigger is a named failure on a real chapter from this system: an item from the operator's
   read or a between-chapter contradiction. It is committed first as a failing fixture.
2. The fix is the cheapest class that works (above).
3. The commit message states the net lines, and the budgets still pass.
4. A change that adds a call or changes what the writer sees is judged by the operator's read of the
   redrawn chapter. A bench report may be attached as description; it never decides.
5. Deletion: code that is not on the chapter path and not exercised by a fixture is deleted.
   Citations never keep code alive.

## Budgets (enforced by `tests/test_guards.py`)

- `litharness/*.py` at most 1,425 physical lines in total (the plan's 1,300, raised in bb87c71, edc478e);
  any `.py` at most 350; tests at most the runtime's lines; no section sign in any `.py`. Raising a cap
  is its own one-line commit naming the case. The `address`, `cast` and `digits` reports were already
  cut for space; the next cut is a new decision, not a rule.
- Imports are stdlib or `litharness`; only `transport.py` imports `subprocess`.
- Docs are capped by line count: README 80, AGENTS 80, CLAUDE 40, LEARNINGS 150, DECISIONS 80,
  `reads/CHECKLIST.md` 40, each `reads/NN.md` 60. Rewrite a stale doc; never append to it.
- Spend: at most 3 draws per stage per input set, 2 transport retries, requests over 32,000
  characters refused, at most 10 chapters per `next`.

## Tests

`python -m unittest -q`, serial, stdlib only, target 3 s (15 s fails). No test spawns a model CLI,
pins prompt bytes or reads what a `.md` file says. Every check has one positive and one negative
fixture; `tests/fixtures.json` holds only located sentences from reads and chapters (at most 60,
each at most 40 words). A single observed false positive moves a word from `money` to `admin`, or,
when the word mostly hits true, excuses only the misfiring sense (a ball court, a town's name).

## Experiments

A comparison is frozen under `experiments/<date>-<name>/`: protocol, receipts, report. Nothing
imports from `experiments/`; its code is deleted when the experiment concludes. Third-party prose
never enters the tree, and measurement text never reaches generation.

## Git

One writer at a time. Work on a topic branch that lives under a day, land it with `--ff-only` on
main, push, and remove the worktree. `legacy/*` refs are permanent. Never `--force`, never
`git clean`, never delete another session's branch or worktree.
