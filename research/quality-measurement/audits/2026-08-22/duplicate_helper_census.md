# Duplicate-helper census — `research/quality-measurement/*.py`

**Method.** Read-only audit of the worktree at ``. I ran only file reads, `Select-String`/regex searches, and one `Get-ChildItem` count; no state was changed and no tests or GPU code were run. I enumerated every top-level `def` in all 58 `.py` files in the directory, grouped by function name across modules, then read the bodies of each duplicated helper to classify them. All line numbers below refer to this worktree.

---

## 1. The stated stance on duplication ("reproduce rather than import")

The directory states its position repeatedly, in docstrings and comments. Where found (my tally of mentions: 12 sites):

- **`build_craft_profile.py:123`** (`auc`): "**Duplicated in `evaluate.py` beside this file and deliberately not shared.** … each must stay runnable standalone; a shared helper module would be a third place to look. The duplication is safe only while they agree… **If you change tie handling here, change it there**, or two experiments stop being comparable and nothing will say so."
- **`evaluate.py:53-60`** (`auc`): "Copied in behaviour from `build_craft_profile.py`… Reimplemented rather than imported so this file runs under either interpreter, and checked in `selftest()` against the O(n²) pairwise definition…" — same "change it there" warning.
- **`comic_beats.py:458-464`** (`digest`): "Restated from `elicit.digest` rather than imported, because `--dump` runs under the MirrorBench interpreter, which does not have this repository installed and cannot import `elicit`… byte-identical on purpose."
- **`elicit.py:139-143`** (`CLI_HARDENING`): "The hardening `providers/cli.py` earned, copied rather than imported — research code must not depend on `src/`, and each flag there carries the reason it is not optional."
- **`platform_priors.py:717-723`** (`book_text`): "Restated rather than imported so this module does not pull a battery in to concatenate a list — and asserted against `bcr.load_text` in the selftest…"
- **`world_lexicon.py:52-55`** (`SNAPSHOT_REVISION`): "restated rather than imported: this file runs under a venv where `litharness` is importable but `corpus_io`'s own module path is not guaranteed, and `corpus_io`'s docstring makes the same argument for duplicating `era_cohort` — 'any disagreement is a finding; a silent shared import would hide one'."
- **`elicitation_study.py:64-68`** (`BIAS_BAND`): "`latent_crossfamily.BIAS_BAND` uses the same numbers and this restates them rather than importing, because that module screens *candidates* and this one screens *protocols* — a shared constant would imply the two thresholds move together."
- **`corpus_io.py:278`** (`era_cohort`): "Reproduced from `build_craft_profile.py::cohort_of` rather than imported, because…"
- **`comic_beats.py:920`** (loader): "Replicated here rather than imported because `_call_cli` builds and spends in one step…"
- **`verdict_locus.py:112`**: "Inherited deliberately — the two modules must not disagree about what…"
- **`bcr.py:22`** (module docstring) and **`axiom_battery.py:46`** declare other things deliberately *not* shared/not re-bought (different sense of "deliberate", recorded for completeness).

I report this stance as found; per instructions I make nothing of it either way.

---

## 2. Helpers defined in more than one module (the census)

### 2a. Text segmentation

**`paragraphs`**
- `ablate.py:62`; `chapter_endings.py:88`
- **Genuinely different.** `ablate.py` splits on `\n\s*\n` with a single-newline fallback ("adapting to which convention the source uses"); `chapter_endings.py` splits on `_BLANK_LINE`, pipes each block through `strip_system(block)` and drops empty results: `return [prose for block in _BLANK_LINE.split(chapter_text) if (prose := _normalised(block))]`. Its docstring: "System lines are dropped **within** a block rather than by splitting on them." Different inputs (raw text vs chapter with system voice), different outputs.
- Both independently carry the same single-newline-fallback lesson (MoL's Wayback export), documented in both places.

**`sentences` / `words`** — *not* duplicated at top level. Only `refuted_metrics.py:74` (`sentences`) and `refuted_metrics.py:79` (`words`) define them. Near-name relatives exist with different jobs: `ablate.py:434 _sentences` (token+piece split for destaking) and `ablate.py:113 words_of` (count). No cross-module duplication found.

### 2b. Set/similarity statistics

**`jaccard`**
- `comic_beats.py:737`; `summary_reliability.py:155`
- **Genuinely different on the degenerate case.** `comic_beats.py`: `if not a and not b: return None` … `return round(len(a & b) / len(a | b), 4)`. `summary_reliability.py`: `if not left and not right: return 1.0` … `return len(left & right) / len(union) if union else 1.0`. The latter justifies itself at length ("two empty sets scored as full agreement… safe only because every use is a within-versus-between difference"). Also differs in rounding and input types.

### 2c. Digests / identity

**`digest`** — four definitions:
- `cdg_battery.py:154` — `sha256(text)[:16]`, plain text input.
- `force_harness.py:195` — `sha256(text.encode("utf-8"))[:16]`, plain text input; docstring: "The key every cache and every seed derives from."
- `elicit.py:199` — `json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` → `sha256(...)[:20]`.
- `comic_beats.py:458` — body **byte-identical to `elicit.py:199`**, deliberately restated (stance quoted above).
- Classification: cdg/force_harness pair **equivalent-but-differently-written** (`"utf-8"` explicit vs implicit default); elicit/comic_beats pair **identical bodies**; text-hash vs payload-hash variants are **genuinely different** functions sharing a name.
- Import fan-out: `elicit.digest` imported by `writer_states.py:70`, `summary_reliability.py:57`, `platform_priors.py:76`; `force_harness.digest` imported by `determinism_probe.py:48`, `force_remote.py:60`.

**`registration_digest`** — three definitions:
- `bcr.py:268`, `comic_beats.py:470`, `platform_priors.py:466`
- **Equivalent pattern, genuinely different material**: each hashes its own module's frozen pre-registration (`bcr` hashes `PRE_REGISTRATION` alone via `sha256(...)[:16]`; the other two call their local `digest` over dicts that also include kinds/families/tasks). All three docstrings state the same contract ("A result file whose digest differs from the module's came from a different instrument").

**`strip_system`** — one research definition + a shipped twin:
- Research: `authorship_tells.py:75` (`_SYSTEM.sub(" ", text)`).
- Shipped: `src/litharness/domain/axes.py` defines the same function whose docstring says "`authorship_tells.strip_system`, verbatim." — i.e. here the *package* copied the research helper.
- Imported from `authorship_tells` by `voice_binding.py:44`, `platform_priors.py:75`, `repair_generation.py:66`, `latent_fixtures.py:68`; `chapter_endings.py:44` and `opening_counters.py:34` instead import it from `domain.axes`.

### 2d. Rank statistics

**`auc`**
- `build_craft_profile.py:116`; `evaluate.py:52`
- **Identical bodies** (compared line-by-line through the rank loop and return). Deliberate duplication documented in *both* docstrings (quoted in §1). Imported from `evaluate` by `cdg_battery.py:87` and `conversion_separation.py:58`.

**`spearman`**
- `baseline.py:48`; `evaluate.py:80`; `comic_beats.py:1824`
- baseline vs evaluate: **near-identical core** (same nested `ranks` with average ranks for ties, same Pearson-on-ranks formula); differ only in signature — baseline returns `(rho, n)`, evaluate returns `float` and takes `Sequence`. comic_beats: **equivalent-but-differently-written** — uses module-level `_ranks`, returns `None` instead of NaN, rounds to 4, guards `len(xs) != len(ys)`.
- `evaluate.spearman` imported by `persona_battery.py:99`.

**ICC family** (three distinct names, one statistic):
- `axiom_battery.py:434 icc_one` — ICC(1); returns **NaN** on degenerate variance; mean-replicate-count approximation.
- `persona_battery.py:110 icc1` — ICC(1); same math, but returns a **dict** (`icc1`, `groups`, `k_mean`, `ms_between`, `ms_within`, rounded), NaN convention inside.
- `bcr.py:749 icc` — ICC(1); returns **None** when fewer than two usable groups, and **0.0** (not NaN) when total variance is zero — a deliberate edge-case divergence from the other two.
- Classification: equivalent math, **genuinely different conventions** at the edges (None vs NaN vs 0.0; scalar vs report dict).
- Fan-out: `summary_reliability.py:58` imports `icc1` from `persona_battery` — the only cross-module reuse in this family.

**`spearman_brown`** — `axiom_battery.py:459` only. Not duplicated.

### 2e. Distance / feature-space helpers

**`z_distance`**
- `register_halflife.py:229`; `repair_generation.py:212`
- **Equivalent-but-differently-written.** register_halflife iterates its own `ACTIVE` feature list and returns unrounded; repair_generation iterates `scale.items()` and returns `round(..., 4)`. register_halflife's docstring even says "`repair_generation`'s.", acknowledging the twin.

**`centroid`**
- `register_halflife.py:217`; `voice_binding.py:176`
- **Equivalent modulo the feature constant**: `{name: fmean(...) for name in ACTIVE}` vs `... for name in FEATURE_NAMES`. Identical shape otherwise.

### 2f. Power / attainability naming cluster

**`attainability`**
- `bcr.py:919`; `force_harness.py:391`
- **Genuinely different despite the shared name.** bcr simulates sessions/shelves to test whether declared control bands are reachable ("Can the declared bands do what they say…? Simulated, no calls."); force_harness computes required headroom for a stratum of size n (`required_k_point`/`required_k_interval`). Same word, different quantities.

**`attainable_p`** and **`required_k`**
- `comic_beats.py:657` & `elicitation_study.py:95` (`attainable_p`); `comic_beats.py:662` & `elicitation_study.py:100` (`required_k`)
- **Genuinely different tails**: comic_beats is one-sided (`return 1.0 / (2 ** n)`), elicitation_study is two-sided (`return exact_two_sided(groups, groups)` = `2/2^groups`), and the two `required_k` scans cover different k ranges accordingly. The near-name pair is a real trap the names do not advertise.

### 2g. Excerpting (`head` / `tail` / `window` / `excerpt`)

*Not duplicated* — checked explicitly:
- `payoff_landing.py:173 head`, `:177 tail` — trivial word-slices, single definitions.
- `taste_calibration.py:92 excerpt`, `:130 window` (window delegates to excerpt with `start_fraction=0.3`) — single definitions.
- `taste_benchmark.py:89 _excerpt` — a thin wrapper that imports `taste_calibration.excerpt` at call time (docstring: "`taste_calibration.excerpt`'s logic"), because the MirrorBench interpreter can't take the top-level import. This is delegation, not duplication.

### 2h. Other shared names I compared

- **`features`** — `authorship_tells.py:79` (surface prose counts over raw text) vs `summary_reliability.py:171` (scalars/sets over a summary dict). **Same name, genuinely different domains.** `authorship_tells.features` is the heavily reused one (imported by `latent_fixtures`, `register_halflife`, `transmission_chains`, `voice_binding`, `platform_priors`, `repair_generation`).
- **`separation`** — `conversion_separation.py:160` (AUC between decile top/bottom rows) vs `summary_reliability.py:196` (within-vs-between jaccard means, deterministic, no seed). **Genuinely different.**
- **`gpu_temperature`** — `cdg_battery.py:114` and `elicit.py:182`: **identical bodies** (same nvidia-smi subprocess, same exception set). No comment marks the copy in `elicit`, though `elicit.py:170-175` credits `cdg_battery` with earning the thermal constants ("`cdg_battery.py` earned these numbers the expensive way"). `verdict_locus.py:59` imports it from `cdg_battery`.
- **`describe`** — three definitions, three behaviours: `chapter_endings.py:147` (per-unit descriptors incl. penultimate-paragraph control), `opening_counters.py:53` (quantiles/moments of a population), `comic_beats.py:745` (**not a restatement — a wrapper** importing `opening_counters.describe` at call time "so the quantile convention… is literally the same convention"; the import is deferred because opening_counters reaches `litharness.domain.axes`).
- **`percentile_of`** — `comic_beats.py:758` is likewise a call-time delegation to `opening_counters.percentile_of` ("Same source, same reason."), not a copy; `opening_counters.py:79` holds the definition.
- **`attainable_p`/`required_k`** covered above; **`load_units`** (`comic_beats.py:966`, `summary_reliability.py:398`) and **`load_scenes`** (`axiom_battery.py:1105`, `promise_kinds.py:82`) are same-name substrate plumbing with different signatures/sources — related purpose, differently written, no shared-import stance statements attached.
- **`dump`** (`comic_beats.py:772`, `taste_calibration.py:178`) — different dumps of the same two-interpreter bridge pattern ("the interpreter that can read 497MB of parquet is not the interpreter that can drive the transport").
- **`summarise_once`** (`promise_kinds.py:198`, `summary_reliability.py:315`) — same idea (one summariser call per unit/sample), different parameter surfaces (arm/system vs level/effort).
- **`wiring_run`** (`director_distinctness.py:161`, `feedback_ablation.py:366`) — same name for two different wiring-pilot drivers; docstrings distinguish them.
- **`provenance`** (`force_harness.py:960`, `force_remote.py:341`) — result-file provenance blocks; force_harness's is generic (`{"pre_registration": ..., **extra}`), force_remote's hardcodes model lineage fields.
- **`free`** (`force_gpu.py:406`, `surprisal.py:108`) — GPU memory release; near-identical intent (`gc.collect(); torch.cuda.empty_cache()`), differ in what they clear (`_LOADED.clear()` vs `_load.cache_clear()`).

### 2i. Scaffolding names (counted, not itemised)

These recur as entry-point/lifecycle plumbing and were tallied but not individually diffed beyond spot checks; they are convention, not measurement logic: `main` (49 modules), `run` (19), `selftest` (29), plus `report`, `score`, `render`, `certify`, `build_pairs`, `ask`, `verdict`, `run_local`/`run_royalroad`/`run_report` (chapter_endings/opening_counters twins), `run_family`, `_cli`, `_load`, `_progress`, `_reading`, `_rows` (chapter_endings/latent_fixtures/voice_binding — three unrelated row-builders), `_packet`/`_beat` (writer_distinctness/writer_g0 pairs), `check`, `build`, `_excerpt`.

---

## 3. Helpers imported from one module by several others (single definition, multi-importer)

- `authorship_tells.features` ← latent_fixtures, register_halflife, transmission_chains, voice_binding, platform_priors, repair_generation (6 importers)
- `authorship_tells.strip_system` ← latent_fixtures, voice_binding, platform_priors, repair_generation (4; plus the verbatim shipped twin in `domain/axes.py`)
- `authorship_tells.FEATURE_NAMES` ← latent_fixtures, register_halflife, voice_binding (3)
- `elicit.digest` ← writer_states, summary_reliability, platform_priors (3)
- `elicit.Elicitor` / `positional_bias` ← many (bcr, cadence_discrimination, axiom_battery, latent_crossfamily, elicitation_study, reader_defects, reader_repair, repair_generation, writer_states, promise_kinds)
- `force_harness.digest` ← determinism_probe, force_remote (2)
- `evaluate.auc` / `evaluate.spearman` ← cdg_battery & conversion_separation / persona_battery
- `persona_battery.icc1` and `pairwise_interval` ← summary_reliability and the reader_* trio respectively
- `ablate.*` is the largest exporter overall: `variants`, `ALL`, `rewhitespace`, `em_dash_inject/strip/report`, `_EM`, `_PROTECTED`, `_is_protected`, `_protected_spans`, `stake_score`, `filler_inject`, `interiority_*`, `stat_flatten` — imported by cdg_battery, evaluate, latent_fixtures, reader_defects, reader_repair, force_harness, writer_states, repair_generation, axiom_battery.

---

## Tally (this audit's counts, not project properties)

- Modules examined: **58** `.py` files (plus `src/litharness/domain/axes.py` for the `strip_system` trail).
- Top-level function names appearing in more than one module: **45** distinct names.
  - Of those, **20** names itemised in detail in §2 (paragraphs, jaccard, digest ×4 defs, registration_digest ×3, strip_system, auc, spearman ×3, ICC family ×3, z_distance, centroid, attainability, attainable_p, required_k, gpu_temperature, features, separation, describe, percentile_of, load_units/load_scenes, dump, summarise_once, wiring_run, provenance, free).
  - **25** scaffolding/plumbing names counted without per-body diffs (§2i).
- Duplicates classified: identical bodies **3 pairs** (auc×2, elicit/comic_beats digest, cdg/elicit gpu_temperature); equivalent-but-differently-written **5** (baseline/evaluate spearman, comic_beats spearman, z_distance, centroid, cdg/force_harness digest); genuinely different behaviour **10** (paragraphs, jaccard, the three ICC edge-case conventions, attainability, attainable_p, required_k, features, separation, provenance); delegation-wrappers-not-copies **3** (taste_benchmark._excerpt, comic_beats.describe, comic_beats.percentile_of).
- Explicit "reproduce/copied rather than import" stance statements found: **12** sites.
- Names from the brief checked and found **not** duplicated: `sentences`, `words`, `head`, `tail`, `window`, `excerpt`.

No consolidation recommendation is made; the operator decides. Nothing was created, edited, or deleted during this audit.