# Handoff: making the codebase easier to hold in one head

**Scope:** a brief for one worktree session. Read `CLAUDE.md` first, then `CONTRIBUTING.md`
in full (the dependency direction and the persistence rules there are the constraints this
brief works inside). This is a scoped brief and not a backlog; when the repo and this brief
disagree, the repo wins. It is deleted once its results have a canonical home.

## The goal, in one sentence

A newcomer session should be able to find where a fact lives, change it in one place, and
know which test will notice, without reading a two-thousand-line module end to end — and
every change here must leave every prompt, gate, line and stored book byte-identical.

## What is true today, to be measured before anything moves

Write `plan/maintainability-survey.md` first, with numbers from scripts and not from memory:

1. **Module size and shape.** Lines, public names, and the share of lines that are docstring
   or comment, for every file under `src/litharness/`. The largest are known to be
   `cli.py`, `domain/extraction.py`, `domain/gamesystem.py`, `domain/worlds.py` and
   `application/planner.py`; the survey says by how much and what each one holds (the
   generality track put the sheet model, the line readers, the move vocabulary and the ask
   composition all into `extraction.py`).
2. **The import graph**, as it is and against `CONTRIBUTING.md`'s stated direction
   (`domain` never imports `application`; `extraction` may import `gamesystem`, never the
   reverse; `genre` imports `extraction`). `tests/test_architecture.py` enforces part of
   this; the survey lists what it does not.
3. **Test suite time and structure.** Per-module durations of `uv run pytest` (use
   `--durations`), the slowest twenty tests, which tests hit the filesystem or a store, and
   which of the roughly two hundred test names the ledger cites (grep `tests/test_` in
   `plan/stage-0-decisions.md`). The full suite takes on the order of ten minutes on this
   box, which is what makes "one sustained job at a time" bite during research arms.
4. **Where the load-bearing numbers live.** The prompt budgets (`tests/test_prompt_budget.py`
   pins every row with a reason), the seed bounds, the scale bounds, the reviser band, and
   every constant with a docstring that says why: list them with their home, so the second
   deliverable can decide what a map should point at.
5. **Docstring knowledge that is not findable.** The modules record decisions in long
   docstrings that cite ledger entries. Sample fifty `§` citations in code and check each
   entry exists and still says what the docstring says it says; list the stale ones. The
   ledger is append-only and corrected in place, so stale means the code's citation needs a
   pointer to the correcting entry, not a rewrite of the ledger.

## Then the changes, lowest risk first (deliverable 2)

Each change is one commit, run through `uv run pytest`, `uv run ruff check .`, `uv run
mypy`, `git diff --check`, and a books-on-disk replay (see the pruning brief's first
deliverable, `tools/replay_books.py`; if that brief has not landed it yet, write it here
first and coordinate through the commit history). Nothing here changes a string a model is
sent, a gate's verdict, or a line's rendering; the prompt-budget tests and the golden
fixtures are the proof, and a change that moves either is out of scope for this brief.

1. **A map, not a rewrite.** `docs/system-model.md`: one page that says where the sheet,
   the system, the moves, the changes, the displays and the floor live, which function is
   the one reader of each fact (the house rule "one source, no second answer" is stated
   dozens of times in docstrings and nowhere as a map), and which test pins each. Point at
   ledger entries; restate no counts.
2. **Split by seam with re-exports.** Where the survey shows one module holding two
   subjects, split it along the seam with the old module re-exporting every public name, so
   no import elsewhere changes in the same commit. Candidates the generality track left
   behind, to be confirmed by the survey and not assumed: `extraction.py` holds the sheet
   model and its readers (a `sheet` module), the status and graph line readers, the beat
   vocabulary (`movables`, `moved_values`, the examples), and the state extraction proper.
   `gamesystem.py` holds the definition, the arithmetic, the records round trip and the
   growth readers. Keep `tests/test_architecture.py` green and extend it to the new seams.
3. **Test helpers in one place.** The pruning brief lists the duplicated helpers; if it has
   not consolidated them, do it here (`tests/helpers.py`), keeping every ledger-cited test
   name alive.
4. **Type coverage.** `mypy` covers `src/` only; measure what `tools/` and the research
   scripts would cost to bring under it, and bring under it what costs a morning or less.
5. **Suite speed.** Mark the slow tests, add a `-m "not slow"` lane that a research arm
   can run beside, and record the two durations in the survey. Do not delete or weaken a
   test to make it fast.
6. **Stale citations.** For each stale `§` citation the survey found, add the pointer to
   the correcting entry in the docstring (one line); never edit the ledger to match the code.

## What this brief refuses

- Renaming public functions or predicates. Vocabulary predicates reach stored books and
  Architect prompts; a rename is a behaviour change.
- Shortening docstrings that record why. The project's decisions live in three places (the
  ledger, the docstrings, the tests) on purpose; the map points, it does not replace.
- Introducing a framework, a plugin system, or a config layer. The house rule is new files
  over restructuring and one function over a mode flag; a split with re-exports is the
  largest structural move this brief allows.
- Any change to `plan/stage-0-decisions.md` beyond a correction in place.

## Parallel-session etiquette (binding for every worktree this week)

- One paid arm and one sustained CPU or GPU job on the box at a time across **all**
  sessions; check the process list before the full suite or a survey script over the
  corpus, and wait if an arm is running (`CLAUDE.md`, "Running things on this box").
- `git status` and `git diff` on shared documents before editing; commit only your own
  files; push after every commit; never `--force`.
- Stage-0 numbers are claimed with the command in `CLAUDE.md` across `main` and every
  worktree and re-checked at commit time. A split with re-exports needs a short ledger
  entry (what moved, what stayed byte-identical, the replay result); a map needs none.

## Done looks like

The survey with its numbers, the map, the splits with their green checks and replay
results, the slow lane with both durations recorded, the stale-citation pointers, and this
brief deleted in the last commit with its results pointed at from the ledger.
