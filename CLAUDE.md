# Working in LitHarness

This file is for sessions — agents and people editing this repository. It is **not** read by
the book-production provider or by the research transports: `providers/cli.py` and the two
`CLI_HARDENING` tuples (`research/quality-measurement/elicit.py`, `force_remote.py`) pass
`--setting-sources user` and a `claudeMdExcludes` setting on every `claude -p` call, and an
opt-in live test (`tests/test_providers.py`, `LITHARNESS_LIVE_PROVIDERS=1`) proves a marker
CLAUDE.md in the working directory does not reach the model (stage-0 §109). Re-run that test
after any `claude` upgrade. If you add a new `claude -p` call site, carry the same two flags —
`--system-prompt` does not keep this file out, and `--bare` logs a subscription out. Nothing
written here reaches a book or a judge.

What the project *is* lives elsewhere; this file only says how to work in it. Keep it free of
counts, status lines, and test totals — the number the project reports about itself is the one
to distrust first (PLAN.md header, the same lesson recorded three times).

## Read first, in this order

1. `CONTRIBUTING.md` — setup, dependency direction, persistence rules. Short; read all of it.
2. `README.md` — what is built and how it is operated. `PLAN.md` §1a and §17 for the goal and
   the roadmap; `plan/stage-0-decisions.md` for every load-bearing decision and why it went
   the way it did, including the ones since reversed. The ledger is long; read the entries you
   are about to build on, not the whole thing.
3. Before proposing **any** quality or craft metric: `research/quality-measurement/BRIEF.md`
   (the refutation ledger) and `CONTRIBUTING.md` "Before proposing a quality or craft metric".
   Before running any research arm: `research/quality-measurement/RUNBOOK.md`.
4. Read a `plan/handoff-*.md` only when the current task names it. A handoff file is a scoped
   brief, not a backlog; completed briefs are deleted once their results and decisions have a
   canonical home. When the repo and a handoff disagree, the repo wins — re-anchor.
5. To ask why a book or scene came out as it did, use the `debug-book` skill
   (`.claude/skills/debug-book/`) before reading source or opening a database. Its one rule:
   nothing a dossier tells you may become a prompt, directive, finding or plan item.

## Standing axioms (one line each; the pointer is the authority)

- **Scope axiom** (stage-0 §95): no solicited human judgment, ever — not hired, not the
  operator, not one blinded pair. LLM-only measurement. The operator's own reads are defect
  harvests, not data. Do not propose human readers, labels, or panels.
- **RS1**: no corpus text or digest crosses to the generation side. Nothing under
  `src/litharness/` references a corpus; `tests/test_corpus_leak_audit.py` checks.
- **Declare no bar** without the four attainability checks — range at the real n, direction,
  independent unit, non-empty subgroup (§81, §85, §87, §89 each named a quantity that could
  not do what it said). Distributions before bars. A pre-registered null is a result (§61).
- **No model ranks or selects** among candidates unless the log's containment for it exists
  (§61(5), §105.1, §107.5). Roles that generate need containment; roles that judge need validity.
- **Three tiers, in this order** (§129): `house.CLARITY` is the floor; **reader direction
  outranks every other craft instruction** and is meant to reach the prompt always; every
  role-specific rule essay (including `house.READER`) ranks below both and is provisional.
  Tier 2 is currently empty, so tier 3 is still all the steering there is — subtract from it
  when the replacement carries something, not before.
- **Simulated-reader direction may reach a prompt. Nothing else may.** Opened 2026-08-24 on
  operator direction (§128) — the writer, and in time the Architect, take direction from
  simulated readers. The live path is `application/readers.py` plus
  `application/planner.py::direction_for`: a reader steers or measures, never both, and the
  request builders enforce the split. Still closed, and closed for their own reasons: the
  operator's own diagnostics (§97.1; the `debug-book` rule), and real-reader behaviour in any
  role inside the loop (§126).
- **Counts are never restated, only pointed to.** BRIEF.md §2 owns the refutation count; the
  suite owns the test count; stage-0 owns decisions. Do not copy a number into a second home.

## Parallel sessions are real

Several sessions edit this repo at once, on `main` and in `.claude/worktrees/*`.

- `git status` and `git diff` on any shared document immediately before you edit it, and
  re-read a file before editing — mid-edit states have been observed on disk.
- Commit only your own files. Leave other sessions' untracked files (`runs/`, handoffs you did
  not write) alone.
- Before claiming a stage-0 number, find the highest in use across `main` **and every
  worktree**, including sub-section headings (a `§86.6` addendum once landed before its parent
  and hid the number); re-run this at commit time:

  ```bash
  for f in plan/stage-0-decisions.md .claude/worktrees/*/plan/stage-0-decisions.md; do grep -oE '^#{2,3} [0-9]+' "$f" | grep -oE '[0-9]+$' | sort -n | tail -1; done | sort -n | tail -1
  ```

  The committed entry owns the number; an uncommitted collision renumbers and moves after.
- A branch that shows commits ahead of `main` may already be on `main` by content; check
  before merging or rebuilding its work.

## The decision log and the documents

- `plan/stage-0-decisions.md` is **append-only**. Corrections are made **in place**:
  strikethrough, bold correction, pointer to the entry that corrects it. Superseded numbers
  stay visible.
- House form for an entry: title as a sentence about what was found; measured first; what
  shipped; what was refused and why; no bar declared unless the checks above were done;
  corrections in place; anti-scope.
- Every test name cited in the ledger must exist in the suite; `tests/test_architecture.py`
  enforces it. Grep the ledger before renaming or deleting a test, and keep a cited name alive
  on its replacement with a docstring recording the change.
- New files where you can; do not restructure shared planning documents.

## Running things on this box

- Before handing off: `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check`.
  Tests force `LITHARNESS_ENV=test`; the registry then refuses every billing provider. Live
  round trips are opt-in (`LITHARNESS_LIVE_PROVIDERS=1`) and spend quota.
- **`claude -p` fails under box load, not under its own concurrency, and the failure is
  silent-ish**: a failing call still returns and the run completes with unanswered cells. Do
  not run the full suite, mypy, or a GPU job while a paid arm, a pilot loop, or an Architect
  run is active; check the process list first. One CLI arm at a time; read `transport_failures`
  before reading any verdict.
- **The box hard-shut-down again on 2026-08-24, with the GPU governor holding**: an ollama
  arm was running under the 72/66 governor while two sustained CPU jobs (a parquet survey
  and a bootstrap simulation) ran beside it. The governor watches core temperature only;
  combined CPU+GPU load is what kills this machine. **One sustained job at a time — CPU
  jobs count.** Run every GPU arm beside the `thermal_watch.py` sidecar (it samples
  independently of the job and kills before the card's own limit), and check the process
  list before launching any background compute, paid or free.
- `pkill -f` matches nothing here and exits 0. Kill by PID from PowerShell and verify the count
  is zero; long paid arms hold a PID lock (`force_remote.SingleRun` is the reference).
- Two interpreters, split by what the run reads: anything touching the RoyalRoad parquet shards
  or torch/GPU runs under the MirrorBench venv (`C:/DEV/MirrorBench/.venv`); anything reading
  `research/quality-measurement/corpora/toll.db` or the package runs under `uv run python`. The 4090 box thermal-shuts-down
  under sustained load — use the duty-cycle governor the research modules already carry.
- Replay caches key on the text digest of (system, messages, model, transport); point `--cache`
  at prior raw JSONLs to replay identical requests for free. A background job's stdout is
  buffered — the cache file is the progress bar.
- Line endings: the repo is LF (`.gitattributes`); `core.autocrlf=true` is global on this
  machine, so scripted edits should write LF explicitly and `git diff --check` before commit.
