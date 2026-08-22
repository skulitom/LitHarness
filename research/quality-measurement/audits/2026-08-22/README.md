# Maintainability audits, 2026-08-22 — digest

*(A dated record, like the results files: what was checked, by what, and what it found. It decides nothing; every item here is the operator's call.)*

Five read-only audits of this tree were run by the stealth model ox-alpha (Cline CLI) from
briefs written by Claude; one (mypy) aborted and was re-run by Claude as a script. Every
headline below was spot-checked by Claude against the tree before being written here. Counts
are each audit's own tally on this snapshot, not properties of the project. Full reports sit beside this file: `docs_audit.md`, `duplicate_helper_census.md`,
`results_orphan_census.md`, `ruff_rules_census.md`, `mypy_research_census.md`, `dead_code_census.md`.

## 1. Documents vs tree (README, CONTRIBUTING, RUNBOOK)

Four discrepancies, all confirmed:
- README:444 — `calibrate … --precision 0.86` no longer exists; the CLI takes `--correct`
  and requires `--selection-family` and `--clusters`. **Fixed on branch `claude/ox-docs_fixes-7f3a21`.**
- README:702–703 — `pair-export` / `pair-import` were deleted in 65a8ddf. **Fixed, same branch.**
- RUNBOOK:173–174 — a `--score` flag `latent_probe.py` never had (scoring is the bare default). *Left for the session editing RUNBOOK.md.*
- RUNBOOK:238 — `latent_support.py` does not import `cdg_battery.throttle` (stdlib + `latent_fixtures` only; one `--out` flag). *Left, same reason.*
CONTRIBUTING.md: no discrepancies in ~30 references checked.

## 2. Duplicate helpers across research modules

- Byte-identical pairs: `auc` (build_craft_profile ↔ evaluate — both docstrings say "deliberately not shared, change it there too"), `digest` (elicit ↔ comic_beats, restated for the MirrorBench interpreter), `gpu_temperature` (cdg_battery ↔ elicit, the copy is unmarked).
- Equivalent-but-rewritten: `spearman` ×3, `z_distance` ×2, `centroid` ×2, `digest` (cdg_battery ↔ force_harness).
- Same name, genuinely different behaviour (traps): `paragraphs`, `jaccard` (empty-set convention), the ICC family (`icc_one` NaN / `icc1` dict / `icc` 0.0 and None), `attainability`, `attainable_p` and `required_k` (one-sided in comic_beats, two-sided in elicitation_study), `features`, `separation`.
- Twelve docstring sites state the "reproduce rather than import" stance; the census reports it and does not argue with it. No consolidation proposed.

## 3. `results/` provenance (124 tracked files)

- 60 have a live writer and a reader or citation.
- 4 hard orphans (no writer anywhere): `cdg.pre-sham-fix.json`, `operator-read-key.json` (SEALED by operator decision, force-program.md:49), `force-f3-survey.json`, `comic-beats-report.json` — each anchored in the ledger; not deletion candidates without a ledger entry.
- 27 operator-named one-offs (writer exists, name came from a hand-typed `--out`/`--cache`).
- 32 written but never read or cited (raw caches, thermal CSVs, single-module summaries).
- 1 document-cited file absent from the tree: `force-f1-pilot.json` (RUNBOOK:540).

## 4. Ruff: what else would pay

Current selection (`E,F,I,UP,B,SIM,RUF`) is clean. Cheap to enable: `RET`, `PIE`, `ERA`,
`PTH`, `C4` — 23 findings tree-wide, 4 safe-autofixable (Claude re-ran the count).
`PERF`: 27, no safe fixes. Noisy and colliding with deliberate conventions: `T20` (scripts and
the CLI print by design), `TRY003` (rich exception messages, no per-message classes), `N818`
(domain-named exceptions), `PLC0415` (lazy imports documented in pyproject), `PLR2004`/`PLR09xx`
(test literals, long research modules), `FBT`, `ARG`. The twelve `PLR0124` hits are the NaN idiom.

## 5. mypy --strict over research/ (run by Claude)

58 modules, 128 errors total; 23 modules already at zero, 56 at ten or fewer; only
`persona_battery` (22) and `axiom_battery` (24) above ten. Dominant codes `no-any-return`,
`attr-defined`, `no-untyped-def` — mechanical. With the new test files as the safety net, moving
research/ under the strict gate is a bounded, oracle-checked job (≈1–2 modules per task), not a slog.

## 6. Dead code in research/

739 top-level definitions scanned; 3 with no reference anywhere (`compression_progress.Fiction`,
`elicit.samples_to_rows`, `surprisal_field.surprisal_series`) and 1 referenced only from the
decision ledger (`elicit.probe_discrimination`, plan/stage-0-decisions.md:3799). Confirmed by `git grep -w`.
The directory is lean; no sweep is warranted.
