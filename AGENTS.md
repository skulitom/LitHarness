# Working in LitHarness

This is the short, tool-neutral guide for people and coding agents changing the repository. It
describes how to work here, not how a production model should write a book.

## First minute

1. Run `git status --short` and inspect the diff for every file you may edit. The checkout may
   contain another session's work; preserve it and stage only your own files.
2. Read [CONTRIBUTING.md](CONTRIBUTING.md). Use [README.md](README.md) for the current operator
   surface and [plan/reader-architecture-program.md](plan/reader-architecture-program.md) only
   when the task concerns reader perception or quality measurement.
3. Do not read the large decision ledger or the complete master plan as onboarding. Search them
   narrowly with `rg -n "term" PLAN.md plan/stage-0-decisions.md`, then read the surrounding
   entry. Historical paths and component names are evidence, not implementation targets.
4. Do not create, move, or recommend git worktrees unless the operator explicitly asks. Work
   safely in the checkout you were given.

## Current code map

- `src/litharness/domain/` owns rules and immutable value objects. It imports only domain code.
- `src/litharness/application/` coordinates through protocols in `application/ports.py`; it
  imports neither providers nor concrete adapters.
- `src/litharness/adapters/` owns persistence and external artifact translation.
- `src/litharness/providers/` owns model transport. Tests structurally disable billing
  providers through `LITHARNESS_ENV=test`.
- `src/litharness/cli.py` is the composition root and operator interface.
- `research/quality-measurement/` is an isolated research surface, never a production import.
- Context assembly and long-serial endurance are first-party LitHarness responsibilities.
- `litharness-contracts` is a pinned git dependency; one LitHarness checkout is sufficient.

`tests/test_architecture.py` enforces dependency direction and documentation references. If a
change needs a new import direction, treat that as an architecture change rather than routing
around the test.

## Feedback loops

Use the repository checker so every agent runs the same commands:

```bash
uv run python tools/check.py smoke
uv run python tools/check.py changed
uv run python tools/check.py quick
uv run python tools/check.py full
uv run python tools/check.py handoff
```

- `smoke` is the roughly four-second architecture/domain/state/context/serial loop.
- `changed` adds tests that correspond to modified paths and escalates to `quick` or `full`
  whenever a narrower selection cannot preserve the required checks.
- `quick` excludes deterministic simulations, endurance checks, and repository-wide scans.
- `full` runs every test without coverage.
- `handoff` runs lint, types, diff and lock checks, the full suite with coverage, wheel build,
  and the corpus-history leak audit. Run it before committing or handing off a completed change.

Direct pytest commands remain appropriate while debugging one failure. Use `-n 0` when ordering
or captured output matters. Live provider tests require explicit `LITHARNESS_LIVE_PROVIDERS=1`;
ordinary checks must never set it.

## Persistence and generated artifacts

- Never edit an applied SQL migration. Add the next numbered migration; startup verifies
  checksums.
- State mutations and their events belong in the same SQLite transaction.
- Accepted manuscript and plan revisions require recorded policy decisions.
- Identities are content-derived; retries and replays must converge rather than duplicate work.
- `runs/`, `book-library*/`, `exports/`, `dist/`, coverage files, caches, databases, and corpus
  working material are generated or local state. Keep experiments under their ignored roots.
- The repository is LF-normalised. Use UTF-8, preserve final newlines, and run `git diff --check`.

## Evidence and scope boundaries

Before proposing a quality or craft metric, read
[research/quality-measurement/BRIEF.md](research/quality-measurement/BRIEF.md) and
[research/quality-measurement/EPISTEMIC_GOVERNANCE.md](research/quality-measurement/EPISTEMIC_GOVERNANCE.md).
Before running a research arm, read its RUNBOOK.

- **Agent prose is not evidence.** Plans, summaries, apparent consensus, and repeated agreement
  may cite an artifact but cannot promote a research claim.
- Quality measurement is LLM-only. The operator's reading may harvest defects but is not a label;
  do not propose human readers, panels, or solicited judgments as the missing signal.
- No corpus text or digest crosses into generation. Commit derived numbers and identifiers,
  never third-party prose.
- No quality bar is declared without attainable range, correct direction, an independent unit,
  and a non-empty subgroup.
- Raw simulated-reader answers never reach drafting or planning. Only a qualified mechanism may
  license a scoped editorial intervention.
- No model ranks or selects candidates unless the evidence log contains the required containment
  and validity controls for that role.
- Author locks constrain feasible interventions; they are not competing quality votes.
- Keep changes narrow. Add a focused regression test, preserve unrelated work, and do not turn a
  local implementation fact into a new research claim or roadmap promise.

## Documents and decisions

`plan/stage-0-decisions.md` preserves decision history. Amend a mistaken entry visibly rather
than silently rewriting the past, and verify any cited test name still exists. Handoff files are
scoped briefs, not a backlog; read one only when the current task names it, and delete completed
briefs after their durable conclusions have a canonical home.
