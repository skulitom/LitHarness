# Adversarial review of the force programme, 2026-08-20

Six independent lenses over the code, the statistics and section 95's claims; every finding
then handed to a separate agent instructed to refute it by default. 89 agents, 70 claims
surviving refutation, ~54 distinct defects. This file is the verbatim synthesis; the ledger
cites it rather than restating it.

---

All code paths below are under `C:/DEV/LitHarness/research/quality-measurement/`; ledger paths under `C:/DEV/LitHarness/plan/`. 70 surviving claims collapse to ~54 distinct defects. Ordered: ledger-invalidating first, then code defects that will corrupt the next run.

---

# A. Defects that make a number already written into §95 wrong or unsupported

### A1. The residual adjustment decides ties with a covariate that explains nothing
`register_halflife.py:546` → `force_harness.py:613`. `residualise` subtracts `a + b*cov` from both sides, so every exact tie becomes a decision of sign `-b*(x_hi - x_lo)` — zero input from the crossover statistic. R² = 3.4e-05, slope -0.0065 against sd 1.18. All 17 raw-tied `aligned` pairs (11 with both sides at the floor 0.0) were converted; `crossed_tight` likewise (4 ties). Both rails die: `ties: 0` in every residual stratum means `MIN_DECIDED_SHARE` can never fire on the reading the bar is declared on, and a raw `INERT_GENERATOR` becomes a residual `FAIL`.
**Fix:** carry the raw tie set forward — mark a pair undecided if `raw_hi == raw_lo`, whatever the residual says.
**Ledger:** invalidates §95.11's `aligned 140 / 76 / 0.5429 / [0.4566, 0.6272] / FAIL` and its argument "n=140 is above the refuting floor, so the stratum was entitled to refute and did." On raw-decided pairs only it is 70/123 = 0.5691 and the state is a refusal, not a refutation.

### A2. The ceiling truncated the corpus in stratum order
`force_remote.py:197` + `register_halflife.py:328` (`CeilingReached → return []`) over `force_harness.load_pairs`'s `aligned`-then-`crossed` ordering. Reconstructed from the cache: `aligned` lost **0** pairs to the ceiling (its 4 drops are empty-generation rows); `crossed` lost **72 of 137**, a clean corpus-order suffix starting at `crossed66`. The survivors also skew loose (retained 41% of `crossed_tight` vs 54% of `crossed_loose`).
**Fix:** interleave strata when building `wanted`, or hard-fail the arm when the ceiling trips instead of silently returning `[]`.
**Ledger:** §95.11's `why` and prose attribute the loss to power ("a stratum too small to refute"). It is attrition that is non-random with respect to stratum, position, and view-gap. The 0.4000, 0.3929 and 0.4054 are all computed on that biased suffix.

### A3. The anchor M is 65% high-side material
`register_halflife.py:501-509` builds M from `produced`, which includes placebo (high text twice) and sham (high + rewhitespaced high) sides. Measured on the exact replayed run: high-derived 25,063 / 38,612 = 64.9% vs 33.8% low; 227 high sides bought vs 210 low. `PILOT_CORRECTIONS["anchor"]["why_not_circular"]` — "it cannot create a systematic high/low difference" — is false in fact.
**Fix:** build the centroid from live pairs plus the neutral pool only.
**Ledger:** shifts the anchor 0.0824 z-units and moves every published F1 figure in the label-favouring direction: `aligned` raw 70/123 → 71/124, residual 0.5429 → 0.5500, `crossed` raw 24/58 → 25/59, residual 26/65 → 28/65. No verdict flips; the printed numbers are wrong.

### A4. The one F1 artifact publishes a single-family FAIL
`results/force-f1-haiku.json:79` has `force_verdict: "FAIL"` with `per_family` holding one key, and `combined.aligned = FAIL` with no `why`. Replaying its own `per_family` through the current `combine_families` returns `NOT_SCREENABLE` on all four strata. `python force_report.py` prints `F1 FAIL FAIL DEGRADED_STRATUM haiku-4-5` today. Same shape in `force-f1-smoke.json` (rows at decided=3 that today return `DEGRADED_STRATUM`) and `force-f2-smoke.json` (a per-family `DEGRADED_STRATUM` folded into a combined `FAIL`).
**Fix:** re-run the pure report assembly over the stored `per_family` (no new compute) and regenerate all four artifacts.
**Ledger:** §95.11's "`combine_families` reports `NOT_SCREENABLE` on the two-family minimum" and §95.2's "A run with fewer than two families now reads `NOT_SCREENABLE` whatever its strata did" are true of the module and false of the file of record and of the printed table.

### A5. `crossed_tight` / `crossed_loose` publish refutations no rail permits
`register_halflife.py:738` sets `binding = label in ("aligned","crossed")`, so the halves bypass both `MIN_REFUTING_N` (`force_harness.py:401`) and any drop guard. They are an exact partition of `crossed`'s scored pairs (28+37=65, 11+15=26), so the identical data is refused a refutation when read whole and emits two when read as halves. Their own attainability rows say `insufficient_n_available: true`, required rates 0.7143 and 0.6757, intervals containing 0.50.
**Fix:** pass `binding=True` (or a `refutable=False` flag that forbids FAIL) for the view-gap halves.
**Ledger:** invalidates the `crossed tight 0.3929 FAIL` and `crossed loose 0.4054 FAIL` rows and the sentence "Both `crossed` halves point the same way, below 0.50."

### A6. The primary statistic is at its floor for 68% of continuations
`register_halflife.py:240-245`. 3,278 of 4,805 scored continuations cross at window index 0; 126 of 578 sides average exactly 0.0; median side crossover 0.5 on a 0-8 scale. Cause: M sits nearer than the seed anchor on 72.9% of *all* windows, so `crossover` returns 0 by default and censoring is low mechanically, not because a decay resolved.
**Fix:** none cheap — the statistic needs a seed anchor that is actually closer than the global centroid at window 0, or the reading is duration-of-nothing.
**Ledger:** §95.11's "The censoring rate is the one clean instrument number… so the statistic is measuring what it was designed to measure" does not follow. 0.0301 excludes the ceiling failure mode only; the floor mode is the one present.

### A7. The sham cannot reach the text it is supposed to perturb, and could not have caught §78
`register_halflife.py:191-194` joins each window with `" "`, so no window contains a newline; `ablate.rewhitespace` at strength 1.0 changes **zero newlines** (`rng.random() <= 1.0` makes the separator branch a no-op) and only intra-line spacing. Measured on 100 real sham pairs: 100/100 produce byte-identical feature rows. Separately `paragraph_len_mean` is exactly 100.0 in all 62,646 windows, so F1's space is 22 features, not the 23 implied by `excluded_features: ["words"]`. And `sham_verdict` has no power floor: at 45 decided, any agreement in [0.3556, 0.6444] passes — a wider band than `aligned`'s own required 0.5903.
**Fix:** drop the `<= strength` guard so the separator actually collapses, and give `sham_verdict` a minimum-decided floor.
**Ledger:** invalidates §95.11's "The sham is clean, and it is the first thing this programme has certified… F1 does not read layout" and "this is the control that would have caught it." The 0.4889 / [0.337, 0.6423] numbers are real; the certification they carry is not.

### A8. The sham ran at 60 while the file declares 100
`register_halflife.py:136-138` justifies `SHAM_PAIRS = 100` with "At n=100 the interval can refuse a sham effect of 0.60 or larger." `PRE_REGISTRATION["sham_subsample"]` is the frozen constant, `--sham` is an override, and RUNBOOK's documented invocation is `--sham 60`. Power against a true 0.60 is 0.2249 at the n that ran and 0.4621 at the n declared — the justification never held at any n.
**Fix:** emit the effective count, not the constant, and delete or re-derive the power sentence.
**Ledger:** `sham_subsample: 100` in `force-f1-haiku.json` is a wrong published parameter; the power claim behind §95.11's certification is void.

### A9. `transport_failures: 0` beside 8 cached transport failures
`register_halflife.py:336-339` caches unconditionally, including `{"continuations": [], "tally": {"failed": 8}}`; `Ledger.transport_failures` is per-process, so the final leg counted 0. Seed `7122c2cdbbaa9d2d` = `aligned40`/low, lost to 8 consecutive failures, replayed silently and dropped. Three more seeds lost to `too_short: 8`; 27 short-dropped replicates total, plus two pairs with unequal K across sides. Nothing reads `tally` back.
**Fix:** don't cache a row with `returned == 0`; sum `tally` across replayed rows into the published ledger block.
**Ledger:** `force-f1-haiku.json`'s `transport_failures: 0` is false, and §95.10's "dropped and counted" is unsatisfied — the 27 appear in no file.

### A10. "531 of 630 seeds" and "$55-58 across all three legs"
531 is `rows_on_disk`. The file holds 505 distinct digests, of which 26 rows are a K=2 smoke leg (13 texts, unreachable at K=8), 4 cache empty lists, and 499 are complete K=8 sets. True coverage is 505/630 = 80.2% attempted, 499/630 = 79.2% usable; the shortfall is 125, not 99. Pricing the earlier legs at the measured $0.0914/seed gives ~$48.5, not $55-58 (the larger figure prices 630 seeds, not 531).
**Fix:** report distinct wanted-keys hit at the run's own K, not `len(self._rows)`.
**Ledger:** both figures in §95.11's opening sentence are wrong.

### A11. §95.11 compares a lower bound against a required rate, at the wrong n
"the lower bound is 0.4566 against a required 0.5903". `required_rate` is `k/n`, an agreement; the bound's threshold is 0.50. And 0.5903 is the n=144 row while the verdict was computed at n=140, whose own row prints 0.5929. Stated gap 0.1337; real gaps 0.0434 (bound vs 0.50) or 0.0500 (agreement vs rate).
**Fix:** prose only — "agreement 0.5429 against a required 0.5929; lower bound 0.4566 against 0.50."
**Ledger:** the sentence that converts F1's headline into "a FAIL and not a near-miss" overstates the miss by ~3x.

### A12. §95.7's "about 55% of the cost" is unreachable, and the two-family decision rests on it
Per-pass cost is `C + D` with fixed `C` = passage + probe. Solving the entry's own "8k rung = 64% of the bill" gives C ≈ 1425 tokens, at which the amended ladder is **72.7%**, not 55%. 55% is not reachable at any `C >= 0`; the infimum is 61.9% at C=0, where the 8k rung would be 76%. Measured C ≈ 1690 (SEED_CAP 1400 + 220-word probe) gives 74%. 55% happens to be `4608/8192`, the top rungs alone.
**Fix:** recompute the ratio with the fixed context term and restate the budget.
**Ledger:** at the honest ratio two families cost 10.4-12.5 h against §95.6's ~10 h of computation — the amendment does not resolve the dilemma it is recorded as resolving.

### A13. §95.7 is titled "F2 ran" and there is no F2 result
`results/force-f2.json` does not exist; `force_report.py` prints `F2 NOT_RUN`. §95.6's table records the disposition as "ladder amended, then run". The only artifact is `force-f2-smoke.json`: 6 pairs, `distances: [512, 2048, 8192]` (the pre-amendment ladder) and `governor: {rest_ratio: 0.25, pause_above_c: 72, resume_below_c: 66}` (the duty cycle the same entry disowns). Its sham has `decided: 1`.
**Fix:** change the disposition to IN FLIGHT / NOT RUN and mark the smoke's ladder and governor.
**Ledger:** "F2 ran", the table row, "Both controls held on the smoke run", and "the whitespace sham reading nothing" are all unsupported.

### A14. §95.9's "F3 cannot deliver a meaningful FAIL" is false about the code
`verdict()` only reaches `INSUFFICIENT_N` when `point_bar_cleared` (`force_harness.py:426-436`). Below 0.52 it returns FAIL regardless of the interval ceiling, and `binding` is never passed by F3, so `DEGRADED_STRATUM` never fires either. `verdict('aligned', 40, 118, 118)` → FAIL at 0.3390 with CP upper 0.4319. Already precedented: `crossed_tight`/`crossed_loose` in `force-f1-haiku.json` FAIL at required rates 0.7143/0.6757.
**Fix:** prose, or make the excusal two-sided.
**Ledger:** the sentence is repeated verbatim in `plan/force-program.md:555` and `results/force-f3-survey.json:104`.

### A15. §95.3's "every placebo has read exactly 0.000000" is a tautology on three of four transports
`control_verdict(label, effect, *, tolerance, kind)` takes no n and every caller feeds a `max` over an accumulator initialised to 0.0 (`register_halflife.py:695-699`, `retention_distance.py:371-378`, `transmission_chains.py:354-370`). Worse, the two sides never produce two computations: F1-local dedups by digest so both sides share one list *object*; F2's `unit_key` collapses (24/24 placebo pairs share one key at every distance); FX's `run_chain` key has no side field so the low side replays the high side's chain. Demonstrated: with a maximally non-deterministic generator, all three still read 0.0 / PASS.
**Fix:** give the placebo low side an independent key/seed on every transport (the `cache_salt` fix already written for F1-remote), and refuse `control_verdict` at zero contributing pairs.
**Ledger:** invalidates §95.3's use of the zeros as evidence the arithmetic was checked, and §95.11's "On the local transport that is precisely the intended arithmetic check."

### A16. §95.6's governor numbers match nothing
Four different pause/resume pairs are stated (§95.6: 62/55; `force-program.md:274`: 65/58; `force_gpu.py:173` docstring: 65/58; `force_gpu.py:20`: 72/66) against the executed `PAUSE_ABOVE_C = 58 / RESUME_BELOW_C = 52`. Soak: both docs say "90 s every 40 calls"; `SOAK_EVERY = 25`. And `Governor.report()` unconditionally stamps `binding_sensor: "temperature.gpu.tlimit (hotspot margin), not core"` into every result — the diagnosis §95.6 explicitly withdraws — including on the Haiku run where `calls: 0` and no sensor was read.
**Fix:** emit thresholds from the constants and delete the `binding_sensor` string.
**Ledger:** "The protections that survive all three readings" names two numbers, both wrong.

### A17. §95.9's fitness-books paragraph
`results/fitness-books.json` now holds eight `DRAFTED` / `meets_shelf_shape: true` books (3,775-3,993 words each, verified in the stores), not "one book reached a real `ran_job` tick". Measured cost is $0.2054-$0.2170 a scene, not ~$0.30 — the $0.30 is toll.db's real rate carried across a 40%-shorter scene. 20 books = ~$25, not $36.
**Fix:** re-read the artifact before quoting it; also recompute the stale index-0 row (`words: 0` against 7,773 actual).
**Ledger:** the spend figure is 43% high and §94.3's blocker "the transplant check needs a second own-generated book as donor, and neither exists" is now false.

### A18. §95.8's prose-blind demonstration is an identity
`popularity()` returns `0.75 if hi > lo else 0.25`, and the strata are *defined* so `hi > lo` always in `aligned` (144/144) and never in `crossed` (137/137). The table is a closed form of two integers: I rebuilt `prose_blind_by_stratum` byte-identically from `(74, 72)` alone. The dry run's `popularity_split_by_stratum` check compares `ln(0.75) > ln(0.25)` and cannot fail — and is a member of `all_checks_pass`.
**Fix:** drop the check or replace it with something falsifiable.
**Ledger:** "the dry run is what makes that a demonstration rather than an argument" is wrong, and "bankrupt in the other" is false — 8.25 against `BANKRUPT_AT = 1.0`, solvent, listed in `survivors`, and promoted at weight 0.0544.

### A19. F3's 27.2 GPU-hours is produced by nothing
No module writes `results/force-f3-survey.json`; `--survey-only` writes `derived/f3-survey.json` with counts only. `pairs`, `stratum_sizes` and `passes_per_family` (6,112) reproduce exactly from the survey; `gpu_hours_per_family_at_25pct_duty: 27.2` has no producer, no timing artifact, and no F3 checkpoint exists. It implies 3,806 tok/s against the ~2,000 tok/s the F2 smoke's own `gpu_seconds` gives; applying the measured throughput to F3's real 93.2M tokens gives ~55.5 h.
**Fix:** derive the price from measured `gpu_seconds` like F1 and F2, or label it an estimate.
**Ledger:** §95.6's "Every one of those prices is measured rather than estimated" is false for F3, and the number under-provisions by ~2x.

### A20. The `cache_salt` edit orphaned the whole paid F1 cache
`register_halflife.py:315-321` appends `cache_salt` (default `""`) as an 8th part; `unit_key` joins with `"|"`, so the empty salt still changes the digest. 0 of 531 rows match the current key; 518 match the pre-salt key. A live probe returns hits 0 / miss 531.
**Fix:** `parts = [... ] + ([cache_salt] if cache_salt else [])`.
**Ledger:** §95.11's "The fix… is in the module and unrun, because the budget that would pay for it is spent" understates it — the next remote run re-buys all 630 seeds (~$55) against a $22 ceiling, so it would trip `CeilingReached` partway and publish a truncated corpus. `force_remote.py:198`'s "The cache is intact; a resumed run replays everything already bought" is false for the one arm that ran.

---

# B. Code defects that will corrupt the *next* number (nothing published yet)

**B1 — CRITICAL. The control gate is inert.** `arm_status` is computed (`register_halflife.py:764`, `retention_distance.py:403`) and written to `report["status"]`, which nothing reads. `combine_families` reads only `report[stratum]`, and `verdict()` can never return VOID, so the VOID branch at `force_harness.py:551` is dead code. Demonstrated: two families whose sham reads 0.90 → VOID → arm VOID, and the file still publishes `force_verdict: "PASS"` with "machine valence exists on this material". *Fix:* in `run()`, gate `force_verdict` on `all(per_family[f]["status"] == "READ")` before consulting `combined`.

**B2 — CRITICAL. F3 runs neither control and hard-codes `READ`.** `compression_progress.py:417`; the module imports no `placebo_pairs`/`sham_pairs`/`arm_status`. Demonstrated with a statistic that reads *only* newline counts: F3 emits `aligned PASS / crossed PASS / status READ / force_verdict PASS` and fires the headline sentence; the same force VOIDs in F1/F2/FX. *Fix:* wire the two controls and call `arm_status`. (Also: `arm_status({})` itself returns READ — add a required-name check.)

**B3 — CRITICAL. F2 scores the token *after* the matched site.** `retention_distance.py:224`: `count_tokens(family, prefix + " ")` counts the trailing space as its own token. Offset is +1 on **6,744 of 6,744** sites on both pinned tokenizers. Frequency matching holds at the matched word (mean |Δlog10| 0.175, max 0.497) and collapses at the scored position (mean 1.143, max 4.468; 35% land on words above the `MAX_COUNT=400` reject ceiling). *Fix:* `offset = force_gpu.count_tokens(family, prefix)`. This likely also explains B5.

**B4 — HIGH. `force_verdict` falls back to the aligned stratum's own status.** `register_halflife.py:810`, `retention_distance.py:445`, `compression_progress.py:467`. When aligned PASSes and crossed FAILs — the exact signature `crossed` exists to catch — `passes` is False and the fallback publishes `"PASS"` beside "does not clear both binding strata". `force_report.py:71` copies it into the table. F3's variant also passes through VOID. *Fix:* `force_verdict = "PASS" if passes else next(refusal states, else "FAIL")` — never re-read `combined["aligned"]`.

**B5 — HIGH. F2's uplift does not decay, so the slope is scatter.** Reconstructed from `derived/f2-gemma-3-4b.jsonl` (216 complete pairs): mean uplift 2.4339 / 2.4268 / 2.4383 across a 9x span; total modelled decay +0.18% of level with sd 18x its mean; 46% of sides negative; `corr(Δ1, Δ2) = -0.33` where a shared decay term forces positive. A generator with zero distance dependence emits an identical `agreement 0.5069, CP [0.4224, 0.5912], FAIL`. `INERT_GENERATOR` is unreachable because `pair_agreement` ties only on exact float equality and slopes never tie. Also: with 3 equally spaced x the OLS slope is algebraically the endpoint difference — the D=1,536 rung contributes nothing and costs a third of the bill. *Fix:* fix B3 first, then add a magnitude floor (refuse when |slope| is inside the null band).

**B6 — HIGH. `MIN_DECIDED_SHARE` is computed over survivors.** `force_harness.py:413` uses `pair_agreement`'s post-drop `total`; `n_before_drops` is written into two output keys and enters no arithmetic anywhere. `verdict('crossed', 12, 40, 40, n_before_drops=137)` returns FAIL at 0.30 — literally the counterfactual the comment above the line says cannot happen. The selftest asserts only that the key is present. *Fix:* `if decided == 0 or decided / (n_before_drops or n_total) < MIN_DECIDED_SHARE`.

**B7 — HIGH. `sham_verdict` has no power floor.** `force_harness.py:475-483` guards only `decided == 0`. For n ≤ 5 the rejection region is *empty* — `sham_verdict('rewhitespace_sham', 4, 4, 4)` (whitespace side wins every pair) returns PASS. `transmission_chains.py:492` ships `--sham` default 4, so FX's declared kill "the sham moves anything" is unreachable at its own default. *Fix:* add a `MIN_SCREENING_N` and return `NOT_SCREENABLE` below it.

**B8 — HIGH. FM ranks confidence, not skill.** `force_market.py:139-157`: `settle` takes no outcome; the truth is hard-coded to 1, so mean log score is the log geometric mean of stated probability. A perfectly calibrated force at 0.52 scores -0.6923; `lambda _: 0.95` scores -0.0513; the minimum accuracy needed to beat it is 0.9920. The committed dry run gives the text-blind `oracle` bankroll 10836.81 and **0.8804 of the promoted ensemble**. The stated overconfidence diagnostic can never fire (any forecaster with all mass ≥ 0.51 has mean log score > log 0.5). *Fix:* score against a real varying outcome, or replace the market with paired accuracy.

**B9 — HIGH. `MIN_REFUTING_N = 110` is the minimum of a non-monotone predicate.** `required_rate(n)` is not monotone; n ∈ {111, 113, 116, 118} demand 0.6036 / 0.6018 / 0.6034 / 0.6017, all above the 0.6000 ceiling, yet clear the floor. F3's `aligned` stratum is exactly 118. *Fix:* gate on `attainability(decided)["insufficient_n_available"]` directly, not on a threshold.

**B10 — HIGH. F3 calls `verdict()` with neither `binding=True` nor `n_before_drops`.** `compression_progress.py:408`/`:414` — the one caller with the largest drop list. Demonstrated at the surveyed shape with 40 aligned drops: shipped code prints `pairs 78, decided 78, agreement 0.3333, FAIL`; the F1/F2 call shape prints `DEGRADED_STRATUM, dropped_before_scoring 40, n_before_drops 118`. Note `crossed` is 73 at maximum, permanently below the floor — a literal copy makes F3 unable to PASS, so this needs a decision, not a paste.

**B11 — HIGH. F3's pass rule drops empty strata out of the conjunction.** `compression_progress.py:456` `for label in sizes if sizes[label]`. Reachable two ways on real data with no exotic flags: `--max-fictions 31` gives `{aligned: 6, crossed: 0}` → PASS from aligned alone; `--max-pairs 73` gives `{aligned: 0, crossed: 73}` → PASS from crossed alone. *Fix:* iterate the fixed `("aligned","crossed")` tuple like F1/F2.

**B12 — HIGH. Local F1 continuations have a 4x length band, and the censored score *is* the window count.** `force_gpu.py:489` `min_new_tokens = max_new_tokens // 4`; `register_halflife.py:245` `return len(to_seed), True`. Measured on `derived/f1-gemma-3-4b.jsonl`: 32-338 words, 1-10 windows, r(words, crossover)=0.976 on censored rows, and 10 of 11 censored replicates score *below* the max observed crossing — the declared "ranks above every observed value" is inverted by length alone. Applying the remote 280/180 normalisation flips 1 of 5 comparable pairs. *Fix:* cut local continuations to a fixed word count and drop the short ones, exactly as `force_remote` does. **Ledger note:** this makes §95.9's "the instrument is ready and the substrate is affordability" false for local F1, and the local pilot censoring figures (0.979 → 0.250) uninterpretable.

**B13 — HIGH. `inverted_u` declares a pre-registered alternative READ on noise.** `register_halflife.py:563-578`: `inside = bool(quad < 0 and min(xs) < peak < max(xs))` — no SE, no interval. Measured: quadratic -0.017463 ± 0.013543 (t=-1.29), R² = 0.003. On 2,000 synthetic samples with y independent of x it fires **42% of the time**. The fit runs on `scores`, which includes controls: 168 of 578 rows are control sides, 105 are exact duplicates of other rows, and `n: 578` is published as a sample size. `plan/force-program.md:407` says "significant"; the module silently weakened it to "signed". *Fix:* compute the SE and restore the significance test; fit on live sides only.

**B14 — MEDIUM. F2's cache key omits the distractor and the filler.** `retention_distance.py:243` keys on passage/window/sites/distance/probe-words but not on the two texts read from `corpora/toll-scenes.json`. Demonstrated: editing the pool changes the true uplifts, the rerun replays the stale rows with `computed_units: 0`, and the slope prints 0.1413 instead of 0.0402. *Fix:* add `digest(distractor)` and `digest(filler_source)` (F3 already keys on `digest(foreign_context)`).

**B15 — MEDIUM. F3's context abort is per-family and is logged as a chapter problem.** `compression_progress.py:313` returns None inside `learnability_slope`; the only reachable drop message is `"a side had missing chapters"`. On the real 191 pairs with all 3,056 chapter texts present, Qwen loses 56 pairs to its 32,768 ceiling and gemma loses 0 — 29% of aligned and 34% of crossed exist for one family only, all mislabelled, and `prefix_truncated` is provably always False. *Fix:* drop the fiction for *both* families when either ceiling bites, and record the real cause.

**B16 — MEDIUM. F3's foreign context is one chapter repeated, and the repetition count grows with j.** `compression_progress.py:307` + `repeat_to_tokens`. Mean reps 2.27 at j=1 → 12.86 at j=7, growing on 380/382 sides; 171/191 pairs get different counts on their two sides; the growth is larger on the high-conversion side in 58%/61% of pairs. Measured on GPU, the pure artifact is 2-5% of the slope. *Fix:* draw the donor from enough of the donor fiction to fill the rung without repeating.

**B17 — MEDIUM. F3's `--max-fictions` default builds a shape nobody declared.** `run()` slices at `args.max_fictions` (default 200) before pairing; `--survey-only` doesn't slice. RUNBOOK's documented full-run command passes no override, so it builds 64 pairs (41/23, required 0.6829/0.7391), not the 191 (118/73, 0.6017/0.6301) the ledger and the artifact quote.

**B18 — MEDIUM. `directive_cap_40_fictions` is 20 crossed pairs and zero aligned.** `compression_progress.py:412` head-slices `pairs[:20]` from a crossed-first list. `force_harness.stratified_subsample` exists for exactly this and is used by every other track.

**B19 — MEDIUM. Governor: `(gpu_sensors().get("tlimit_margin_c") or 99) <= pause_margin_c`.** `force_gpu.py:236`. Margin 0.0 — the card at its own limit — becomes 99, and so does a transient `nvidia-smi` failure. Ran it: confirmation read 3.0 → holds=1; 0.0 → holds=0; `{}` → holds=0. Every other site in the file and in `thermal_watch.py` uses `is not None`. *Fix:* `is not None`.

**B20 — MEDIUM. Governor accumulators discard every hold-loop reading.** `force_gpu.py:209-218` folds one sample per call, taken before the rest sleep; the loop's three `gpu_sensors()` calls fold none. Demonstrated: true min margin 7 published as 13, true peak core 62 published as 54, `throttle_events: 0` while 8 of 12 reads were throttling. *Fix:* fold inside the loop.

**B21 — MEDIUM. `DEGRADED_STRATUM` is tested before `INERT_GENERATOR`.** `force_harness.py:401` before `:413`. Below 110, every tie-driven inert reading on a binding stratum is published as a corpus-power complaint that explicitly acquits the force — live in `force-f1-haiku.json`'s `crossed__raw_DIAGNOSTIC` (58/65 = 0.892, below the 0.90 floor, published as DEGRADED). The same ordering also suppresses a genuine PASS and can manufacture a false `SPLIT_FAMILY`.

**B22 — MEDIUM. `verdict()` never reads `row["attainable"]`.** `force_harness.py:384`. n=5 is a hole in the ladder: perfect agreement returns `INSUFFICIENT_N` at n=2-4, `PASS` at n≥6, and **FAIL at n=5**, because the point-bar fallback reports `required_rate` 0.6000 and the escape hatch is strictly-greater. Reachable via `--pairs 10` on any track. *Fix:* `if not row["attainable"]: return INSUFFICIENT_N`.

**B23 — MEDIUM. Every committed force artifact predates one or more fixes.** 15 of 16 `combined` rows across the four files mismatch what the current module returns. Regenerate all of them from stored `per_family`. (Same action as A4.)

**B24 — LOW. `SPLIT_FAMILY` outranks `DEGRADED_STRATUM` and `INERT_GENERATOR`.** `force_harness.py:558` before `:572`, so `{PASS, DEGRADED_STRATUM}` publishes "one family reads the force and another does not" about a family that said nothing. Fires on the first real two-family run — `force-f1-haiku.json` already holds a genuine DEGRADED `crossed`.

**B25 — LOW. `sham_pairs` emits byte-identical pairs where `rewhitespace` is a no-op.** 3 of 281 high sides; index 0 (`aligned0`) is one of them and `stratified_subsample` draws index 0 at every size, so every sham subsample on every track contains a non-control. FX spends 1 of its 4 control pairs on it. Visible in both smokes. *Fix:* assert `low != high` in `sham_pairs` and skip.

**B26 — LOW. F3 at `len(pairs) == 1` makes the fiction its own donor** (`(0+1) % 1 == 0`), pinning the j=1 rung to exactly 0.0 on the high side only. Reachable via `--max-pairs 1` and via `--max-fictions` ∈ {11,12,13}.

**B27 — LOW. F2's "exactly matched token length" filler is short for 47/281 pairs on Qwen (max 90 tokens) and 32/281 on gemma.** `truncate_to_tokens` never pads; the source scene is 1,310/1,364 tokens against a 1,400 cap. Symmetric within a pair, so it moves levels not rankings — but the pre-registration says "exactly", and `repeat_to_tokens` two lines earlier would make it true.

**B28 — LOW. `token_logprobs` left-truncates the prefix silently**, dropping the BOS it just added, while F3's guard counts a different string with `add_special_tokens=False`. Unreachable on the current ladder (gemma's budget is ~128k), but it contradicts F3's declared no-truncation policy and `prefix_truncated` is always False by construction.

**B29 — LOW. The declared censoring convention is not implemented.** `crossover` returns `len(to_seed)` (5-8, not a constant) and `side_statistics` takes an arithmetic `fmean` over the mixture; 14 of 144 censored outcomes rank at or below observed ones. Implementing the declaration faithfully moves aligned 76/140 → 75/140 — inert as run, but the encoding of "above everything" is an undeclared free parameter (censored → 12 would give a PASS).

**B30 — LOW. `determinism_probe`'s exported pre-registration states a false premise** — "the programme generates replicates one at a time" — against `num_return_sequences=k`; the probe ran k=2/64 tokens for arms at K=8/512, and FX's `sample_batch` (the only genuinely varying-composition batch) is not probed at all. *Fix:* correct the string and add a `sample_batch` check.

---

# Numbers currently in ledger section 95 that this review believes are unsafe

**§95.11 (F1)**
- `aligned … 140 / 76 / 0.5429 / [0.4566, 0.6272] / FAIL` — 17 of the 140 decisions are covariate-only (A1); the anchor moves it to 0.5500 (A3). Raw-decided reading is 70/123 = 0.5691 and is a refusal.
- "n=140 is above the refuting floor, so the stratum was entitled to refute and did" — the n is manufactured.
- `crossed … 65 / 26 / 0.4000` and its DEGRADED attribution — survivors are a budget-ordered suffix, not a power sample (A2).
- `crossed tight 0.3929 [0.2150, 0.5942] FAIL` and `crossed loose 0.4054 [0.2475, 0.5790] FAIL`, and "Both `crossed` halves point the same way" (A5 + A2).
- Sham `0.4889 [0.337, 0.6423]` **as a certification** — "F1 does not read layout" and "this is the control that would have caught [§78]" (A7, A8). The counts themselves are real.
- Censoring rate `0.0301` **as instrument validation** (A6). The rate itself is real.
- "531 of 630 seeds" and "about $55-58 across all three legs" (A10).
- "the lower bound is 0.4566 against a required 0.5903" (A11).
- "`combine_families` reports `NOT_SCREENABLE` on the two-family minimum" (A4 — true of the module, false of the artifact and of `force_report`).
- "The fix … is in the module and unrun, because the budget … is spent" (A20 — the outstanding cost is the whole arm).

**§95.7 (F2)**
- "about 55% of the cost" and the two-family budget conclusion that rests on it (A12).
- "F2 ran" / the §95.6 table row "ladder amended, then run" (A13).
- "`placebo_identical` at exactly 0.000000" and "the whitespace sham reading nothing" (A13, A15).

**§95.6**
- "core pause tightened to 62 / 55 °C" and "a soak break of 90 s every 40 calls" (A16 — code is 58/52 and 25).
- "Every one of those prices is measured rather than estimated" as applied to F3's `~27.2 h per family` (A19; the 6,112 passes are sound).

**§95.9**
- "`aligned` demands 0.6017 and `crossed` 0.6301 … the arm can pass or abstain and not refute" (A14). The two rates are correct; the entitlement claim is not.
- "27.2 GPU-hours per family" (A19).
- "one book reached a real `ran_job` tick" and "the measured ~$0.30 a drafted scene" (A17).
- "the instrument is ready and the substrate is affordability" for local F1 (B12).

**§95.8**
- The whole prose-blind table (`-0.2877 / 448.27`, `-1.3863 / 8.25`) as a *demonstration*, and "bankrupt in the other" (A18). The numbers are correct and content-free.

**§95.3**
- "every placebo in every arm below has read exactly 0.000000" as evidence the arithmetic was checked (A15).
- "batched sampled continuations are bit-exact" as scoping "the two operations every force uses" (B30 — probed at k=2/64; `sample_batch` unprobed).

**Numbers in §95 this review found no reason to doubt:** the raw tie counts (123 of 140, 17 ties), the sham's 45-of-60 counts, F3's survey shape (585 fictions, 118 aligned / 73 crossed, 6,112 passes, required 0.6017/0.6301), the attainability table in §95.2 (85/144, 81/137, 43/68, 44/69), the batching measurement (44 s vs 384 s), the vocabulary and attention-shape facts, the F1 transport prices ($0.0210 / $0.0089 / $0.0833 / ~$52), and F2's stall diagnosis in §95.12.