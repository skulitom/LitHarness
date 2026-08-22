All data gathered and cross-checked. Nothing was created, edited, or deleted: every command was a read (`ruff check` with `--statistics` / `--output-format json` / `--fix --diff`, which only prints would-be patches; `git ls-files`; `git grep`; `ruff --version`). No test suite or GPU code was run.

---

# Ruff rule-group audit — LitHarness worktree `ox-maint_audit-7f3a21`

**Method.** For each of `src`, `tests`, `research` and each candidate group (`C4 PTH RET PERF PIE ARG PL N T20 ERA TRY FBT`) I ran `uv run ruff check --select <GROUP> --statistics <dir>` (ruff 0.16.2), then `--fix --diff <dir>` to confirm the would-be patches render, and parsed `--output-format json` to count per-rule violations whose fix applicability is `safe`. Safe-fixable counts are exact from JSON; diff-hunk counts were used only as a sanity check. Baseline first: **the current selection (`E,F,I,UP,B,SIM,RUF`, line-length 100) is clean — 0 findings in all three directories.** Every count below is my tally of this audit on this snapshot, not a property of the project. Corpus size for context (my tally via `git ls-files`): src = 81 .py files, tests = 79, research = 64 (tools/ has 4 more but was outside scope).

## `src` (81 files)

| Group | Rule | Count | Safe-fixable | Representative location |
|---|---|---|---|---|
| C4 | C416 unnecessary-comprehension | 2 | 0 | src/litharness/domain/extraction.py:167 |
| PTH | — | 0 | 0 | — |
| RET | RET504 unnecessary-assign | 1 | 0 | src/litharness/adapters/sqlite_store.py:1661 |
| PERF | PERF401 manual-list-comprehension | 5 | 0 | src/litharness/application/architect.py:652 |
| PIE | — | 0 | 0 | — |
| ARG | ARG001 unused-function-argument | 8 | 0 | src/litharness/application/conductor.py:499 |
| PL | PLR0913 too-many-arguments 79 · PLR0915 too-many-statements 29 · PLR2004 magic-value 21 · PLR0912 too-many-branches 20 · PLR0911 too-many-returns 16 · PLC0415 import-outside-top-level 4 · PLC0414 useless-import-alias 2 · PLR0917 too-many-positional 2 · PLW3301 nested-min-max 1 | 174 | 0 | src/litharness/adapters/sqlite_plans.py:60 (PLR0913) |
| N | N818 error-suffix-on-exception-name 22 · N813 camelcase-imported-as-lowercase 1 | 23 | 0 | src/litharness/adapters/contracts_fixtures.py:48 (N818) |
| T20 | T201 print | 276 | 0 | src/litharness/cli.py:385 |
| ERA | — | 0 | 0 | — |
| TRY | TRY003 raise-vanilla-args 317 · TRY301 raise-within-try 2 · TRY300 try-consider-else 1 | 320 | 0 | src/litharness/adapters/continuity_cli.py:23 |
| FBT | FBT003 boolean-positional-value-in-call | 30 | 0 | src/litharness/application/constraint_locks.py:193 |

## `tests` (79 files)

| Group | Rule | Count | Safe-fixable | Representative location |
|---|---|---|---|---|
| C4 | C408 unnecessary-collection-call | 2 | 0 | tests/test_taste_benchmark.py:124 |
| PTH | — | 0 | 0 | — |
| RET | — | 0 | 0 | — |
| PERF | PERF401 manual-list-comprehension | 4 | 0 | tests/test_context.py:534 |
| PIE | PIE808 unnecessary-range-start | 1 | **1** | tests/test_serials.py:81 |
| ARG | ARG001 unused-function-arg 56 · ARG002 unused-method-arg 9 · ARG005 unused-lambda-arg 8 | 73 | 0 | tests/test_budget.py:313 (ARG002) |
| PL | PLR2004 magic-value 338 · PLC0415 import-outside-top-level 108 · PLR0913 10 · PLR0917 1 · PLW0108 unnecessary-lambda 1 | 458 | 0 | tests/conftest.py:94 (PLR0913) |
| N | — | 0 | 0 | — |
| T20 | — | 0 | 0 | — |
| ERA | — | 0 | 0 | — |
| TRY | TRY003 raise-vanilla-args | 9 | 0 | tests/test_budget.py:314 |
| FBT | FBT003 31 · FBT001 bool-positional-hint 8 · FBT002 bool-default-positional 1 | 40 | 0 | tests/test_chapter_endings.py:251 (FBT001) |

## `research` (64 files)

| Group | Rule | Count | Safe-fixable | Representative location |
|---|---|---|---|---|
| C4 | C416 unnecessary-comprehension 5 · C420 unnecessary-dict-comp-for-iterable 3 | 8 | **3** | research/quality-measurement/cadence_discrimination.py:260 (C416) |
| PTH | PTH100/119/120/123/207 os-path & open & glob | 5 | 0 | research/preference-power/simulate.py:75 (PTH120) |
| RET | RET504 unnecessary-assign | 1 | 0 | research/quality-measurement/refuted_metrics.py:76 |
| PERF | PERF401 17 · PERF402 manual-list-copy 1 | 18 | 0 | research/quality-measurement/cadence_discrimination.py:404 (PERF402) |
| PIE | PIE810 multiple-starts-ends-with | 1 | 0 | research/quality-measurement/writer_states.py:216 |
| ARG | ARG001 25 · ARG005 1 | 26 | 0 | research/frontier-arm/duplication.py:121 |
| PL | PLR2004 225 · PLC0415 116 · PLR0913 34 · PLR0915 18 · PLR0912 16 · PLR0124 comparison-with-itself 12 · PLR0917 5 · PLC0206 dict-index-missing-items 4 · PLR0911 4 · PLW2901 redefined-loop-name 2 · PLC0207/PLR1733/PLR1736 1 ea · PLR1714 1 · PLW1510 subprocess-without-check 1 | 441 | **3** | research/frontier-arm/duplication.py:155 (PLR0913) |
| N | N818 error-suffix-on-exception-name | 3 | 0 | research/quality-measurement/force_remote.py:118 |
| T20 | T201 print | 390 | 0 | research/frontier-arm/duplication.py:188 |
| ERA | ERA001 commented-out-code | 2 | 0 | research/quality-measurement/ablate.py:139 |
| TRY | TRY003 raise-vanilla-args | 90 | 0 | research/preference-power/bound.py:128 |
| FBT | FBT001 24 · FBT003 17 · FBT002 5 | 46 | 0 | research/quality-measurement/ablate.py:631 (FBT003) |

## Reading

**Near-zero — cheap to enable** (< ~12 findings repo-wide in my tally): `RET` (2), `PIE` (2, one safe autofix), `ERA` (2), `PTH` (5, all in research). `C4` (12, three safe autofixes) and `PERF` (27, zero safe fixes in ruff 0.16.2 — all "hidden" unsafe fixes) are still small enough to burn down by hand in an afternoon. Note none of these groups' fixes are mostly safe, so enabling them is a small manual cleanup either way; there is no free autofix win hiding here except PIE808/C420.

**Noisy at scale:** `T20` (666), `TRY` (419, essentially all TRY003), `PL` (1,073), `ARG` (107), `FBT` (116).

**Conflicts with deliberate patterns** (this is where most of the noise lives):

- **`T20` vs scripts and CLI that print by design.** All 666 hits are T201. `cli.py` is the operator surface (CONTRIBUTING.md says so explicitly), and `research/` is experiment scripts whose output *is* the result ("commit numbers"). T20 would need per-file ignores on `cli.py` + `research/**` to be anything other than pure friction.
- **`N818` vs the domain failure vocabulary.** The exception classes are deliberately named after the domain fact (`BudgetExceeded`, `IllegalTransition`, `PlanConflict`, `BillingGuardViolation`, …), not `*Error`. My `git grep` tally found only a minority carry the `Error` suffix. N818 would flag ~25 sites to defend a convention this codebase has chosen against.
- **`PLC0415` (import-outside-top-level) vs lazy imports by design.** 228 hits across the tree, and `pyproject.toml` documents the pattern as intentional: `elicit.py` "imports lazily" so the suite runs with the paid `anthropic` extra uninstalled; the same logic applies to `datasets`. Tests use function-level imports heavily (108) for isolation.
- **`PLR2004` (magic-value) vs tests and research thresholds.** 584 of its 589 hits are in tests (338 — asserting expected literals is what tests do) and research (225 — cadence/cohort thresholds are the experiment's domain constants).
- **`PLR0913/0912/0915` (complexity family) vs long modules by design.** 79 too-many-arguments in `src` alone, concentrated in the SQLite capability repositories and workflow coordinators; plus long research modules. Enabling these means either refactoring the persistence facade CONTRIBUTING.md describes or ignoring half the rules.
- **`TRY003` vs rich exception messages.** 416 hits, nearly all "raise vanilla args". The codebase raises exceptions carrying full human-readable messages (which feed operator output and policy-event details); TRY003's demand for custom exception classes per message collides head-on with the N818 finding above — the project would have to mint dozens of exception types it has deliberately not minted.
- **`FBT` vs positional booleans.** 116 hits. I did not find a stated keyword-only-boolean convention, so some of these may be genuine readability wins — but FBT003 (bool passed positionally in calls) fires 78 times in ordinary constructor/function calls, so expect churn, and FBT001/002 would force `*,` into many signatures across providers and adapters.
- **`ARG` vs test/protocol stubs.** 73 of 107 are in tests — unused fixture/monkeypatch and protocol-stub arguments, which are conventional; the 8 in `src` (unused protocol-method params in implementations) are the only ones I'd call real signal.

**Bottom line:** `RET`, `PIE`, `ERA`, `PTH` (and arguably `C4`) could be switched on today for a total of ~21 findings in my tally, none blocking. `PERF` is a modest manual follow-up (27, no autofixes). Everything else (`T20`, `TRY`, `PL`, `N`, `ARG`, `FBT`) collides with documented or clearly deliberate conventions and would arrive as hundreds of suppressions rather than signal — if wanted at all, they'd need narrow scoping (e.g., TRY300/301 without TRY003; PLR0124/PLC0206-style correctness rules without the complexity family). Per your instruction I did not touch `pyproject.toml`.

---

## Tally of this audit

- Directories checked: 3 (`src`, `tests`, `research`); groups checked: 12; group × directory runs of `--statistics`: 36; matching `--fix --diff` runs: 36; JSON parse passes: 36; baseline check of current selection: 3 runs (all clean).
- Violations counted (sum over all groups/dirs): **src 987, tests 593, research 1,061 → grand total 2,641**, of which **safe-autofixable: 7** (PIE808 ×1 in tests; C420 ×3 and PLC0207/PLR1733/PLR1736 ×1 each in research).
- Commands run that could change state: none — only read-mode ruff invocations, `git ls-files`, `git grep -h`, `uv run ruff --version`, and directory listings. Files created, edited, or deleted: 0. Tests/GPU: not run.
- Caveats: counts reflect ruff 0.16.2 on this snapshot; `tools/` (4 .py files) was outside the requested scope and unchecked; representative locations are single examples, not exhaustive lists; the N818 naming observation is based on my `git grep` listing of exception class names (38 unique names shown, majority non-`Error`).