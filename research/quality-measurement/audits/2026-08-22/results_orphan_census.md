All evidence is gathered. Here is the audit report.

---

# Provenance census: `research/quality-measurement/results/`

**Method.** `CONTRIBUTING.md` read first. Inventory from `git ls-files research/quality-measurement/results` — **124 tracked files**. For every basename I ran `git grep -l -F <basename>` over the whole tree excluding `results/` itself, then chased pattern-based producers (`RESULTS / …`, f-string stems, `result_path`-style helpers, argparse `--out/--cache/--log` defaults) in `research/quality-measurement/*.py`, and checked document citations in `research/quality-measurement/*.md`, `plan/*.md`, `README.md`, `CONTRIBUTING.md`. I also grepped *inside* two results-dir prose files (`force-review-findings.md`, `comic-beats-results.md`) because they cite sibling artifacts. All counts below are **my tally of this audit**, not a property of the project. Nothing was created, edited, deleted, or executed beyond reads/greps.

A recurring pattern matters for reading the lists: several modules write operator-supplied names through `--out`/`--cache` flags, so a filename appearing in no `.py` does not always mean the producing module is gone. Where that distinction holds, I say so.

## List 1 — no writer anywhere in the current code

**Hard orphans (no module names them, no pattern produces them; superseded snapshot or retired/deleted arm):**

| File | Evidence |
|---|---|
| `cdg.pre-sham-fix.json` | Cited `plan/stage-0-decisions.md:2959` ("preserving the superseded summary"). Current `cdg_battery.py` writes only `results/cdg-raw.jsonl` (`cdg_battery.py:199-201`) and `cdg.json`; no code contains this filename. |
| `operator-read-key.json` | SEALED, retired unread: `plan/force-program.md:49` and `:705`, `plan/stage-0-decisions.md:5175`, `:7369`, `plan/reader-batch-1.md:223`. Zero `.py` matches anywhere. |
| `force-f3-survey.json` | Explicitly orphaned by code change: `results/force-review-findings.md:107` — "No module writes `results/force-f3-survey.json`; `--survey-only` writes `derived/f3-survey.json`." Still cited at `plan/force-program.md:567`, `plan/stage-0-decisions.md`, `force-review-findings.md:84`. |
| `comic-beats-report.json` | `comic_beats.py` names outputs only via `f"comic-beats-{substrate}-{arm}…json"` (`result_path`, `comic_beats.py:1146`); substrate `report` (`comic_beats.py:2429`) would yield `comic-beats-report-<arm>.json`, never this name. No literal match anywhere. |

**Operator-named one-offs — the writing module exists and accepts `--out`/`--cache`, but no code path, default, or documented command produces these exact names** (reproducible only by re-running with the same hand-chosen flag value):

- `bcr-pilot-gemma3-12b.{json,jsonl}`, `bcr-pilot-gpt-oss-20b.{json,jsonl}`, `bcr-pilot-phi4-latest.{json,jsonl}` (6) — `bcr.py:1592` auto-names `bcr-{seat\|battery}-{model}.json`; `RUNBOOK.md:430` documents only the unsuffixed `--cache bcr-pilot.jsonl --out bcr-pilot.json`. Model-suffixed pilot names match nothing.
- `cadence-discrimination-gemma.json`, `cadence-gemma-raw.jsonl` — defaults at `cadence_discrimination.py:475-476` are unsuffixed; gemma names match nothing.
- `elicitation-study-haiku.json`, `elicitation-study-haiku-raw.jsonl` — defaults at `elicitation_study.py:1195,1198` unsuffixed; haiku names match nothing.
- `latent-taste-probe-v2.json` — `latent_probe.py:1056` default is `latent-taste-probe.json`; `-v2` matches nothing (contrast: `latent-crossfamily-screen-v2.json` *is* cited, `plan/stage-0-decisions.md:6227`).
- `latent-crossfamily-screen-v2.json` — cited (`stage-0-decisions.md:6227`) but `latent_crossfamily.py:334` default is unsuffixed; `-v2` in no code.
- `taste-benchmark-corpus-n46.json` — `taste_benchmark.py:569` default meta is `taste-benchmark-corpus.json`; `-n46` matches nothing.
- `taste-benchmark-intensity.json`, `taste-benchmark-sonnet-intensity.json` — cited `plan/stage-0-decisions.md:4818`; neither name in any code.
- `authorship-tells-controlled.json` — `authorship_tells.py:318` single `--out` default `authorship-tells.json`; no "controlled" variant in code; name matches nothing.
- `force-f3-audit.json`, `force-f3-qwen35.json`, `force-f3-slopes.json` — `compression_progress.py:930` default out is `force-f3.json`; the three variants match nothing.
- `force-f1-haiku-corrected.json` — named only in `plan/stage-0-decisions.md:7887` ("is the file of record"); no producer; plausibly emitted by `force_report.reassemble(..., apply=True)` to an explicit path or a manual copy.
- `force-f1-smoke.json`, `force-f2-smoke.json` — no producer names them (`RUNBOOK.md:566` documents only `force-f1-haiku-smoke.json`), though both are analyzed as existing artifacts at `results/force-review-findings.md:32` and `:77`.
- `repair-generation-sonnet.json` — cited `plan/stage-0-decisions.md:5186`; `repair_generation.py:552` default is `repair-generation.json`; sonnet name in no code.
- `reader-repair-opus-raw.jsonl` — grep empty everywhere outside the tree; `reader_repair.py:278` default cache is `reader-repair-raw.jsonl`.
- `repair-panel-sonnet-raw.jsonl` — grep empty; `repair_generation.py:551` default is `repair-panel-raw.jsonl`.
- `persona-intensity-raw.jsonl` — grep empty; `persona_battery.py:611-612` default cache is `persona-raw.jsonl`, and `RUNBOOK.md:63`'s intensity command uses `persona-intensity-haiku-raw.jsonl`.

Special case, not an orphan: **`force-review-findings.md`** is an authored review document (cited at `plan/stage-0-decisions.md:8047`), not module output — no module should write it.

## List 2 — referenced by a document or code, but absent from the tree

By documents:
- **`force-f1-pilot.json`** — `research/quality-measurement/RUNBOOK.md:540` (`--out research/quality-measurement/results/force-f1-pilot.json`); not tracked.

By code (note: `force_report.py:32` documents that a missing file is the `NOT_RUN` *state*, so these absences are partly by design):
- `force-f2.json` — `force_report.py:36`; confirmed absent in prose at `results/force-review-findings.md:77`.
- `force-fx.json` — `force_report.py:38`.
- `force-f1-survey.json`, `force-fx-survey.json` — survey-file lookups exercised at `tests/test_force_report.py:54` and `:67`.
- `persona-discrimination.jsonl` — `elicit.py:1359`.
- `thermal-watch.csv` — `thermal_watch.py:188` default log.
- `latent-taste-activations.npz` — `latent_probe.py:1055`; deliberately gitignored per `RUNBOOK.md:172`.
- `derived/comic-beats-royalroad.jsonl` and royalroad per-arm raw caches — `comic_beats.py:769`, `:1158`; untracked by design (third-party prose), as is `derived/f3-survey.json` (`force-review-findings.md:107`).

I found **no case of a document citing a tracked-results filename that is missing from the tree** other than `force-f1-pilot.json`.

## List 3 — writer exists, but nothing reads or cites the file

Each is touched only by its own module (write + self-replay/self-load); greps for the basename across all docs and all other modules came back empty:

- `axiom-battery-raw.jsonl` — writer `axiom_battery.py:1165` (the summary `axiom-battery.json` *is* cited, `stage-0-decisions.md:5507`)
- `authorship-tells.json` — `authorship_tells.py:318`
- `baseline.json` — `baseline.py:154`; only consumer mention is prose in `conversion_separation.py:7`, no programmatic reader
- `cadence-discrimination.json`, `cadence-raw.jsonl` — `cadence_discrimination.py:476`, `:475`
- `comic-beats-royalroad-price.json` — written via `run_price` → `result_path` (`comic_beats.py:1717`, `:1146`); the aggregate readers iterate only census/repeat/sham/strip (`comic_beats.py:1929`, `:2118-2150`) and no document names it
- `composite-battery.json` — `composite_panel.py:326`
- `director-distinctness.json` — `director_distinctness.py:292`
- `feedback-ablation.json` — `feedback_ablation.py:575`
- `force-determinism.json` — `determinism_probe.py:131`
- `force-f4-g0.json` — `surprisal_field.py:352`
- `payoff-landing.json`, `payoff-landing-raw.jsonl` — `payoff_landing.py:589`, `:588`
- `persona-adherence.jsonl` — `elicit.py:1413`
- `promise-kinds.json`, `promise-kinds-raw.jsonl` — `promise_kinds.py:451`, `:450` (the `promise-kinds-gemma.*` variants *are* RUNBOOK-documented)
- `reader-defects-raw.jsonl` — `reader_defects.py:337` (summary `reader-defects.json` cited at `plan/reader-batch-1.md:57-58`, `stage-0-decisions.md:4898`)
- `state-coverage.json` — `state_coverage.py:270`
- `taste-benchmark-raw.jsonl`, `taste-calibration.json`, `taste-calibration-raw.jsonl` — `taste_benchmark.py:589`, `taste_calibration.py:395`, `:394`
- `thermal-check.csv`, `thermal-f1pilot.csv`, `thermal-f2.csv`, `thermal-f2b.csv`, `thermal-f2e.csv`, `thermal-f2f.csv` — writer is `thermal_watch.py --log` (`thermal_watch.py:188`; generic template `RUNBOOK.md:485`); nothing reads them. (`thermal-f2c.csv` and `thermal-f2d.csv` are exempted by name in `corpus_leak_audit.py:229`, so they are *not* in this list.)
- `verdict-locus.json`, `verdict-locus-raw.json` — `verdict_locus.py:344`, `:343`
- `voice-binding-raw.jsonl` — `voice_binding.py:391` (summary `voice-binding.json` cited at `stage-0-decisions.md:6586`)
- `writer-g0.json` — `writer_g0.py:187`
- `writer-states-raw.jsonl` — `writer_states.py:605` (siblings `writer-states.json` and `writer-states-gen-raw.jsonl` are cited/read elsewhere)

For contrast, the remaining 60 files all have a live writer (code literal, f-string pattern such as `latent_crossfamily.py:189` for the six `crossfamily-*-raw.jsonl` and `comic_beats.py:1146/:1159` for the eight comic-beats arm files, or a documented operator command such as `RUNBOOK.md:41,48,57,63,430,450,566`) **and** at least one reader or citation (e.g. `platform_priors.py:1186` reads `bcr-seat-phi4.json`; `latent_fixtures.py:74-75` reads `writer-states-gen-raw.jsonl` and `repair-gen-raw.jsonl`; `compression_progress.py:930` ↔ `force_report.py:37`; `plan/reader-batch-1.md`, `plan/craft-corpus.md:162`, `plan/force-program.md:49,115,567`, `results/force-review-findings.md:32,77,97,107`, `results/comic-beats-results.md` summarizing the comic-beats arms).

## Tally (this audit's count)

- Tracked files under `results/`: **124**
- With a live code writer + at least one external reader/citation: **60**
- List 1 (no writer found): **32** — 4 hard orphans + 27 operator-named one-offs + `force-review-findings.md` counted separately as an authored document (so 28 flagged filenames plus 1 authored doc)
- List 2 (referenced, absent from tree): **9** — 1 by document (`force-f1-pilot.json`), 8 by code/untracked-by-design paths
- List 3 (writer exists, nothing reads or cites): **32**

Per the brief, no deletions recommended — the four hard orphans in particular (`cdg.pre-sham-fix.json`, `operator-read-key.json`, `force-f3-survey.json`, `comic-beats-report.json`) are each explicitly anchored in the decision ledger, and `operator-read-key.json` is sealed-unread by operator decision (`plan/force-program.md:49`). The decision on anything here is the operator's.