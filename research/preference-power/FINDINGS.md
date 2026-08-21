# What §61's bar costs, and the one place it stops being honest

The preference engine shipped with an empty verdict store. The README of the time called it the
instrument that could measure quality, "built and waiting on funded judgment", and treated that
emptiness as the honest measure of the gap. (Both that sentence and the channel behind it are
gone: the scope axiom of 2026-08-19 retired solicited judgment permanently — ledger §95. The
measurement below stands as a fact about the estimator, which is what it always was.) Nobody had said **how much** judgment, what it would cost, or
whether the estimator holds its stated level at the panel sizes anyone would actually buy.

This is that measurement. Five sweeps plus a seed-stability experiment — 272,000 simulated panels
at 2,000 bootstrap resamples each — with every bound produced by the shipped estimator rather than
a normal approximation to it.

Three results, in descending order of what they should change:

1. **A defect, not a sizing result.** §61 pre-registration (5) divides `alpha` by the candidate-book
   count. At a family size of 10 or more, that drives the bound from the 50th resampled rate down
   to the 3rd of 2,000 — deep enough into the tail that the *bootstrap seed decides certification*.
   A measured example: one verdict set clears 0.5 under 82% of seeds at C=10 and 35% at C=20. §7.
2. **The bar is honest where it matters and breaks where it is cheapest.** The bound over-rejects
   — measured at 8.40% against a nominal 2.5%, a factor of 3.4 — exactly when one cluster
   dimension is both small and heterogeneous. That is the shape of a pilot panel.
   `DESCRIPTIVE_CLUSTER_FLOOR = 5` does not protect against it. §5.
3. **A marginally-better system cannot be demonstrated at any budget tested.** At a true win rate
   of 0.55 with realistic heterogeneity, 3,000 verdicts buys 49% power — a coin flip. The bar is
   affordable only if the system is substantially better, not slightly. §6.

**What this is not.** It is not evidence about LitHarness prose. It contains no verdicts, no
readers and no money spent. It is a study of an estimator's behaviour under a declared model, and
every number below is conditional on that model being the right one — see §8 for where it is
weakest and what would refute it.

---

## 1. The instrument is the shipped estimator, proven rather than assumed

`win_rate_lower_bound` walks every observation inside each of its 2,000 resamples. A Monte Carlo
sweep needs the bound a few million times, so [`bound.py`](bound.py) computes it by walking
**cells** — one entry per (reader, pair) — instead. The resampled rate is a ratio of two bilinear
forms (`nr' S np` over `nr' C np`), so aggregating a cell before weighting it is algebra.

The part that would normally sink an equality claim is floating point: re-ordering a sum usually
perturbs it. It does not here. Scores are exactly {0.0, 0.5, 1.0}, multiplicities are small
integers, every product is a dyadic rational far inside 2^53, and such sums are exact in binary64
regardless of order. The content-derived seed is reconstructed too, via the same `payload_digest`,
so the twin is not merely same-distribution — it is the same function.

`verify_equivalence` asserts that over the shapes most likely to break it: the 2×2 cluster floor,
all-win and all-loss boundaries, heavy ties under both policies (where `DROP` changes the seed as
well as the sample), ragged incomplete designs, and duplicated cells from position swaps.

```
equivalence: 60/60 shapes agree bit for bit with win_rate_lower_bound
```

Every number in this document is therefore a fact about shipped code.

## 2. The null, and the wrong conclusion it invites

The failure worth fearing is a bar easier than it claims. Run under the least favourable
conditions for finding it — true win rate exactly 0.5, independent Bernoulli, no reader or pair
effect at all:

| R | P | verdicts | type-I (nominal 2.5%) | median bound |
|---|---|---|---|---|
| 5 | 20 | 100 | 0.150% | 0.3452 |
| 8 | 40 | 320 | 0.050% | 0.4113 |
| 12 | 60 | 720 | 0.150% | 0.4390 |
| 20 | 100 | 1600 | 0.050% | 0.4588 |

Read alone this says the estimator under-rejects by 17–50× and its intervals run 1.6–1.7× wider
than an iid binomial interval. **That reading is wrong, and it is wrong because of the one
assumption in it that is certainly false for a paid panel: that readers are interchangeable.**

## 3. Calibration is a function of reader heterogeneity

Model: `logit P(win | r, p) = mu + u_r + v_p + w_rp`, with `mu` **solved** for the target marginal
rather than set to `logit(target)` — adding logit-normal noise pulls the marginal toward 0.5, and
at target 0.70 with heavy heterogeneity the naive value delivers a true marginal of 0.631.

48 points, R=12, P=60, k=30, 2,000 replicates each:

| σ_reader | type-I (nominal 2.5%) | α\* | width vs iid |
|---|---|---|---|
| 0.0 | 0.05 – 0.80% | 0.11 – 0.24 | 1.65 – 2.32 |
| 0.4 | 0.65 – 1.25% | 0.085 – 0.13 | 2.16 – 2.52 |
| 0.8 | 1.35 – 2.60% | 0.050 – 0.073 | 2.82 – 3.12 |

`α*` is the alpha that *would have to be requested* for the bound to hold at a true 2.5%. At
σ_reader = 0.8 it is 0.050 against a requested 0.05 — exact calibration.

Because a rare event cannot be measured by counting it (2,000 replicates of a 0.1% event is two
events), each replicate reads its bound at a ladder of alphas off the same sorted resamples. The
match at σ_reader = 0.8 holds across the **whole curve**, not just the tail — much harder to get
by accident:

```
requested α:   0.05   0.10   0.20   0.35   0.50   0.70   0.90
nominal:      0.025  0.050  0.100  0.175  0.250  0.350  0.450
σ_R = 0.8:    0.025  0.055  0.093  0.164  0.236  0.331  0.435
σ_R = 0.0:    0.002  0.004  0.011  0.061  0.132  0.266  0.432
```

So the estimator is neither broken nor gratuitously wide. It is **calibrated precisely in the
regime the project will occupy** — a panel of paid humans who genuinely disagree. Its width is
mostly earned. What it is, is sensitive to a quantity nobody has measured.

## 4. The interaction term is protective — a correction to this study's own hypothesis

This study was built expecting the reader×pair interaction to be the danger: the estimator
resamples two margins, an interaction is visible in neither, and position-swapped orientations of
one pair by one reader genuinely share it.

That was backwards. Holding σ_reader = 0.8, σ_pair = 0:

| σ_inter | 0.0 | 0.4 | 0.8 | 1.2 |
|---|---|---|---|---|
| type-I | 2.500% | 2.450% | 2.050% | 1.600% |

Interaction variance makes the bound **more** conservative, monotonically. An independent probe
(design panel, P3) reproduced the same sign under a probit model and a different parameterisation.
The mechanism: the interaction feeds the cell-level term, which the product weighting over-counts,
while the cluster terms carry the deflation.

**Consequence for anyone designing a successor study: setting σ_inter = 0 overstates the danger.**
The conservative modelling choice is the opposite of the intuitive one.

## 5. Where it breaks: the starved dimension

Two sweeps that appear to contradict each other, and the rule that reconciles them.

**Starve the readers** (P = 60 fixed, σ_pair = σ_inter = 0.4, 24 points):

| R \ σ_reader | 0.0 | 0.4 | 0.8 | 1.2 |
|---|---|---|---|---|
| 4 | 0.15% | 2.05% | **5.50%** | **7.70%** |
| 6 | 0.05% | 1.20% | **3.80%** | **4.60%** |
| 8 | 0.15% | 1.45% | **3.70%** | **4.80%** |
| 12 | 0.20% | 0.85% | 2.60% | 3.00% |
| 20 | 0.25% | 0.75% | 1.75% | 2.25% |
| 30 | 0.20% | 0.55% | 1.80% | 1.80% |

Type-I falls as readers are added. **Starve the pairs instead** and it reverses. An independent
probe (design panel P2, probit link, different code) found R from 5 to 30 at P = 8 with the
heterogeneity in the *pair* dimension driving type-I *up*, 2.15% → 4.90%. Re-run here with 30
readers fixed, full crossing, σ_reader = 0.2 and σ_inter = 0.4:

| P | 4 | 6 | 8 | 12 | 20 | 40 |
|---|---|---|---|---|---|---|
| σ_pair = 0.4 | 2.10% | 1.75% | 0.80% | 0.85% | 1.00% | 0.95% |
| σ_pair = 1.2 | **8.40%** | **5.30%** | **3.90%** | **2.95%** | 2.55% | 2.10% |

Both cannot be a rule about readers. The reconciliation: **the bound is governed by whichever
cluster dimension is small and heterogeneous, and adding observations to the other dimension
strips away the binomial noise that was accidentally widening the interval and masking the
shortfall.** Adding readers does not help or hurt as such; it sharpens whichever dimension is
already starved.

**The two dimensions are symmetric, and the numbers say so.** Starving readers gave 7.70% at
R = 4 with 60 pairs; starving pairs gives 8.40% at P = 4 with 30 readers. The estimator weights
its two margins identically by construction, and the failure obeys that symmetry. The design
panel's independent probit implementation put the same corner at 8.25% — three implementations,
two link functions, one number.

This is the operationally dangerous result, because it points the wrong way from instinct. A real
panel scales the dimension it can buy — readers — while the pair pool is capped by how many scenes
a book has. That is a walk *into* the failure, not out of it.

**`DESCRIPTIVE_CLUSTER_FLOOR = 5` does not cover this.** The constant flags panels below five
clusters as "descriptive rather than calibrated". At R = 6 and R = 8 — both above the floor — the
bound over-rejects at 3.7–4.8%, roughly double its nominal level. The floor is correctly aimed and
set too low, and it flags rather than refuses.

## 6. What the bar costs

48 points; verdicts interpolated on a log scale at 80% power. "not reached" means 3,000 verdicts
did not get there.

| true win rate | no heterogeneity | moderate (σR .4 / σP .8 / σI .4) | high (.8 / 1.2 / .8) |
|---|---|---|---|
| 0.55 | ~1,900 | **not reached** (49% at 3,000) | **not reached** (31% at 3,000) |
| 0.60 | ~475 | ~1,150 | ~2,400 |
| 0.65 | <320 | ~365 | ~715 |
| 0.70 | <320 | <320 | <320 |

Rows marked `<320` were already above 80% at the smallest panel tested, so they are upper bounds
rather than minima.

**Heterogeneity dominates effect size as a cost driver.** Moving from no heterogeneity to moderate
costs more verdicts at p = 0.60 (475 → 1,150) than moving the system from 0.60 to 0.65 saves.

**Money, with the assumption stated because it is the weakest link here.** A blinded pairwise
comparison of two scene-length passages is 8–15 minutes of careful reading; at paid-platform rates
plus fees and screening, $3–6 per usable verdict is defensible. This is an assumption, not a
measurement, and it is the number a real quote should replace first:

| | p = 0.60 | p = 0.65 | p = 0.70 |
|---|---|---|---|
| $3.00/verdict | $3,450 | $1,095 | $960 |
| $4.50/verdict | $5,180 | $1,640 | $1,440 |
| $6.00/verdict | $6,905 | $2,190 | $1,920 |

At p = 0.55 the study is not fundable at any price in this range — which is itself the decision-relevant fact.

## 7. The family correction is a seed lottery

§61 pre-registration (5) divides `alpha` by the candidate-book count, "because a level is honest
only at the family it was earned against". The principle is right. The implementation interacts
badly with a fixed 2,000 resamples.

The bound reads the `ceil((alpha/2) * B) - 1`-th sorted resampled rate. Dividing alpha divides the
rank:

| family size C | 1 | 2 | 3 | 5 | 10 | 20 |
|---|---|---|---|---|---|---|
| effective alpha | 0.0500 | 0.0250 | 0.0167 | 0.0100 | 0.0050 | 0.0025 |
| rank read (of 2,000) | 50th | 25th | 17th | 10th | 5th | **3rd** |

At C = 20 the certification rests on the 3rd smallest of 2,000 bootstrap draws, where Monte Carlo
noise dominates the data. Holding one dataset **completely fixed** and varying only the bootstrap
seed, over 60 seeds:

| C | 1 | 3 | 5 | 10 | 20 |
|---|---|---|---|---|---|
| spread of bound | 0.0040 | 0.0120 | 0.0130 | 0.0165 | **0.0255** |
| SD of bound | 0.0010 | 0.0019 | 0.0022 | 0.0038 | **0.0048** |

And on clustered data sitting near the decision boundary — the marginal claim the project would
actually be adjudicating — the same verdict set both certifies and fails to certify:

```
dataset with observed win rate 0.6200, 2000 verdicts, only the seed varying:
  C=1   certifies under 100% of seeds
  C=10  certifies under  82% of seeds
  C=20  certifies under  35% of seeds
```

**The sharp version.** The seed is a `payload_digest` of the verdict set, chosen so "nobody can
re-roll the bootstrap hoping for a kinder quantile". That defence holds completely — you cannot
re-roll it. But it does not make the number stable; it makes it an arbitrary draw you are stuck
with. **Determinism was doing the work of reliability, and it cannot.**

**The fix is mechanical.** `BOOTSTRAP_RESAMPLES` must scale with the family size so the rank read
stays deep enough to be data-determined — keeping the 50th-rank read at C = 20 needs B = 40,000.
The cost is linear and one-off. The alternative is an interpolated or smoothed tail quantile.

**This is fixable now and only now.** The verdict store is empty. Changing the estimator after
judgments exist is exactly the post-hoc move the pre-registration discipline exists to forbid, so
the window was open until the first paid reader answered, and it closed unopened: the scope axiom (§95) retired that channel on 2026-08-19 and no reader was ever engaged.

## 8. What this licenses, and what it does not

**It does not license** any claim about LitHarness prose, any change to the §61 bar itself, or
confidence that the model here is the right one.

**The weakest link is the generative model, and it is mine rather than a measured one.** The
crossed logit with three variance components is standard, but a design panel run against this
study proposed a materially richer one — probit link with closed-form marginals as a bug-catcher,
explicit position-bias susceptibility per reader, a book-level layer above pairs, recognition
correlated with passage quality, memory contamination across position-swapped orientations, and
reader-specific tie bands. Those are recorded as the pre-registered next step, not as findings.
Two of its probes already corrected this study (§4, §5).

**Pre-registered, before any successor runs:**

- σ_reader is the quantity that decides both validity and cost, and it is cheap to estimate
  relative to the full study. **A pilot panel should be sized to estimate σ_reader, not to clear
  the bar** — and by §5 a small pilot is exactly the shape that over-rejects, so a pilot must be
  read as a variance estimate and must not be allowed to certify anything.
- If a successor study finds type-I at or below 2.5% across a grid that includes R ≤ 8 with
  σ_reader ≥ 0.8, this study's §5 is refuted and the floor needs no change.
- If a real quote puts a usable verdict above $10, the p = 0.60 row stops being fundable and the
  bar becomes a claim that only a substantially superhuman system can attempt.

---

**Reproduce:**

```bash
uv run python research/preference-power/bound.py
uv run python research/preference-power/simulate.py --mode calibration --out cal.json
uv run python research/preference-power/simulate.py --mode power --out pow.json
uv run python research/preference-power/simulate.py --mode readers --out rdr.json
uv run python research/preference-power/simulate.py --mode pairs --out prs.json
```
