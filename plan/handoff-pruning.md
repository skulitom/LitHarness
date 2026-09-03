# Handoff: pruning the codebase without losing what it knows

**Scope:** a brief for one worktree session. Read `CLAUDE.md` first, then `CONTRIBUTING.md`
in full; this file is a scoped brief and not a backlog. When the repo and this brief
disagree, the repo wins. The brief is deleted once its results have a canonical home (a
stage-0 entry per landed cut, the suite for the tests, `git log` for the diffs).

## The goal, in one sentence

Remove what the project no longer runs, reads, or cites, in small measured commits, so that
every module, script, research arm and planning file left on `main` is one somebody can
name a reader for — without deleting a fact the ledger relies on.

## Why now

The repository has grown by accretion under a house rule that prefers new files to
restructuring (`CLAUDE.md`, "New files where you can"), and by a research programme that
registers many arms and refutes most of them (`research/quality-measurement/BRIEF.md`). Both
are correct, and both leave behind code with no caller, scripts with no runbook line,
handoffs whose results already have a home, and research directories whose question is
closed. The number the project reports about itself is the one to distrust first (`PLAN.md`
header), so this brief asks for an inventory before a single deletion.

## What may not be cut, and why

- **Nothing in `plan/stage-0-decisions.md`.** Append-only; corrections in place only.
- **A test name the ledger cites.** `tests/test_architecture.py` enforces that every test
  name cited in the ledger exists. Grep the ledger before renaming or deleting a test, and
  keep a cited name alive on its replacement with a docstring recording the change.
- **The two `claude -p` hardening flags** on every call site (`--setting-sources user`
  and `claudeMdExcludes`; stage-0 §109). If a cut touches a call site, the live test
  `tests/test_providers.py` under `LITHARNESS_LIVE_PROVIDERS=1` is how it is re-proven.
- **Books on disk.** Every phase of the system-generality plan replayed the four stored
  books and read 8/8 lines identical (stage-0 §203 to §212). A pruning cut that changes
  what a stored book renders or extracts is a behaviour change wearing a cleanup's clothes.
  `tools/` has no replay script committed; the one the generality track used is in
  stage-0 §203's description (read canon, re-run `extract_state` over stored scene texts,
  compare snapshots). Write it into `tools/replay_books.py` as the first deliverable and run
  it before and after every cut.
- **Research directories whose arm is `REGISTERED` and not yet run.** The refutation ledger
  (`BRIEF.md` §2) and `EPISTEMIC_GOVERNANCE.md` say which arms are closed; a registered arm
  with a pre-registration and no result is a promise, not bloat.
- **`runs/`, `book-library/`, any gitignored data**, and other sessions' untracked files.

## The inventory first (deliverable 1, no deletions)

Write `plan/pruning-inventory.md` with, for each candidate, the evidence it is dead and the
test or ledger entry that would notice if it were not:

1. **Unreferenced code.** Every public name under `src/litharness/` with no caller outside
   its own module and no test (a script over the import graph and `grep`; do not trust
   `vulture` alone). Known candidates to check, not conclusions: `application/variation.py`
   (stage-0 §105 measured `VariationSession` null and shipped it off), the reviser path
   (`--revise` is opt-in since §196; it is not dead, but its always-on plumbing may be), the
   three `stats.*` and `ledger.gold.v0` detector ids listed in `application/evaluation.py`
   that are "built and green in a sibling checkout" and never run here, and the `characters`
   and `salience` readers' use of change roles now that `gamesystem.changes_of` reads them
   too (one reader per fact; stage-0 §212).
2. **Scripts with no runbook line.** Everything under `tools/` and every `*.py` under
   `research/quality-measurement/` not named in `RUNBOOK.md`, `BRIEF.md` or a `FINDINGS.md`.
3. **Handoffs whose work landed.** Every `plan/handoff-*.md` against the ledger: if the
   ledger entry it points at exists and records what shipped, the handoff is deletable
   (`CLAUDE.md`: completed briefs are deleted once their results have a canonical home).
4. **Worktrees and branches.** `.claude/worktrees/*` and every branch: which are already on
   `main` by content (`git log main..<branch>` may show commits that are content-identical;
   check by diff, not by count), which hold work nobody merged. Report; do not delete a
   worktree another session may be sitting in — list them for the operator.
5. **Duplicate test helpers.** `_accepted`, `_canon`, `rec`, `_system` are re-implemented
   across `tests/test_choice_points.py`, `tests/test_world_slots.py`,
   `tests/test_gamesystem.py`, `tests/test_progression_prompt.py` and others. One
   `tests/helpers.py` with the ledger-cited test names untouched.
6. **Documentation that restates counts.** `README.md`, `PLAN.md` and the plan notes may
   carry a test total, a refutation count or a status line that a canonical home already
   owns (`CLAUDE.md`, "Counts are never restated, only pointed to"). List them.

## Then the cuts (deliverable 2, one commit per cut)

Order by risk, lowest first: documentation counts, handoffs already landed, duplicate test
helpers, scripts with no runbook line, unreferenced code. For each cut:

- `git status` and `git diff` on every shared document immediately before editing it; other
  sessions edit this repo at once.
- Run `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`, and the
  replay script, before the commit; never `ruff format` a computed file list without
  guarding `[ -n "$changed" ]` (an empty list formats the tree; recorded in stage-0 §205).
- One stage-0 entry per cut that removes behaviour or a research surface, in the house form:
  what was measured (the inventory line), what shipped (the cut), what was refused, anti-scope.
  Claim the entry number with the command in `CLAUDE.md` across `main` and every worktree,
  and re-run it at commit time. A cut that removes nothing a reader could notice (a helper
  consolidation, a stale count) needs no ledger entry; say so in the commit message.
- Commit only your own files. Push after every commit (`origin`, never `--force`).

## What this brief refuses

- Rewriting for style. A long docstring that records why a decision went the way it did is
  the project's memory and is not bloat; the maintainability brief owns structure.
- Deleting a research directory because its arm was refuted. A refuted arm's records are
  the refutation; archive under `research/quality-measurement/closed/` with a pointer from
  `BRIEF.md` only if the directory's own `FINDINGS.md` already records the refutation.
- Any change to what a prompt says, what a gate refuses, or what a line prints.

## Parallel-session etiquette (binding for every worktree this week)

- One paid arm and one sustained CPU or GPU job on the box at a time across **all**
  sessions. Check the process list before launching anything that runs longer than a test
  module; if a `litharness`, `ab_redraw`, `claude -p` arm or a corpus pass is running, wait.
  The box hard-shut-down twice under combined load (`CLAUDE.md`, "Running things on this
  box").
- Do not run the full suite or `mypy` while another session's paid arm is active; module
  runs are fine.
- Stage-0 numbers: the committed entry owns the number; an uncommitted collision renumbers.

## Done looks like

The inventory file, the replay script, a run of cuts each with its green checks, the
inventory's rows marked landed or refused with the reason, and this brief deleted in the
last commit with its results pointed at from the ledger.
