# Pricing the anchor: the unanchored-judge validity programme

**Status: pre-registered, T0 built and RUN, the other three priced and blocked.** This
document answers the directive "bound judge divergence and exploitation tightly enough to earn
scoped selection licences using zero solicited human labour". It is written under §82's rule
rather than against it, and its first job is to separate the half of the anchoring question a
machine-only stack can settle from the half it cannot reach at any price.

**The programme's headline, stated before any tier runs, because the build produced it.** Three
of the four tiers are not runnable today and none of the three is blocked by money:

- **T1** is blocked by provider access this machine does not have. One frontier lineage is
  reachable; the local tier is measured below the instrument's capability floor.
- **T2 is blocked by its own premise.** "Newly published" and "readable retention label" are
  mutually exclusive on the measured distribution: the label needs accumulated views and a new
  serial has none. Median total views for a 2025 LitRPG serial at a median age of 98 days is
  **1,245**, median followers **5**, and only **22.3%** ever clear the 10,000-view floor that
  exists because below it `followers / total_views` means nothing. Two further blockers are
  independent of that one and either would be enough on its own.
- **T3** is blocked on T1, because "held out" means "another lineage" and there is one lineage
  here.

**What was runnable was T0, and it has run: $26.09, 720 comparisons, and the incumbent panel is
DISQUALIFIED under both readings** — on positional bias at **0.8151 over 568 decided comparisons**,
on dose monotonicity, and on paraphrase stability. §86.6 has the numbers, and the correction the
battery itself needed first. The registered expectation that the incumbent would fail is met; the
axiom it was predicted to fail on is not among the three that decided it.

---

## 1. The claim under test, split into the two claims it contains

The directive pre-registers a falsifier: *if T2 and T3 pass at their bars, the claim "selection
requires solicited human evidence" is refuted at those scopes.* That sentence carries two
claims with different truth conditions, and the programme is worth nothing if they stay welded
together.

**(a) The empirical claim** — *no machine-only evidence can bound how far a machine judge
diverges from reader response* — is falsifiable, T2 is its falsifier, and it is the half worth
buying. Nothing in the ledger asserts it and §82 does not assert it either.

**(b) The instrumental claim** — *§72's judge path requires solicited human evidence* — is true
**by definition** in `src/litharness/domain/calibration.py`, which constitutes `PREFERENCE` as
*"a human's blinded, position-swapped choice between two texts"*. No experiment refutes a
definition. A T2 pass would not open the judge path; it would make amending the instrument
worth debating, which is a different act with a different procedure.

So the falsifier is **accepted for (a) and refused for (b)**, and the refusal is not
conservatism dressed as rigour: §82 refused the licence *on evidence class*, and an entry
claiming a machine measurement had overturned it would be claiming a definition had been
measured away.

### 1.1 The definition is enforced by a docstring, and the code has a laundering path

Checked in the source while writing this document, because the whole ceiling rests on it:

- `plan_search` records a licensed judge's verdicts through **the same pair machinery humans
  use**, with `reader_id` set to the licensing calibration id and `recognized=False` — the
  comment says so in as many words, and §72 records the design intent.
- `domain/preference.analysable_judgments` — the function that decides which rows a preference
  holdout may be denominated in — filters on `verdict is not None`, `not recognized`, and
  `verdict is not NOT_SURE`. **It never inspects `reader_id`.** `pair_verdicts_digest_for` does
  not either.
- There is no source column, no `CHECK` constraint, and no runtime predicate anywhere that
  asserts a preference verdict came from a person. The human-only property of `PREFERENCE` is
  prose in an enum docstring.

**So once one human-anchored calibration licenses one judged tournament, the judge's own
verdicts join the pool that the next PREFERENCE calibration is measured on, and nothing counts
them separately.** §72's expiry rule bites first — the judge's writes move the digest and stale
its own licence — but staleness forces *re-calibration*, and re-calibration is exactly where the
contamination enters, because the re-measured holdout now contains machine answers under a class
whose definition says human.

This is inert today: `litharness calibrations` prints nothing, so there is no row to launder
into. It stops being inert on the day §80's batch lands. **The fix is small and it is cheapest
now**: give the machine-written rows a reader id with a reserved prefix at the one write site,
and exclude that prefix in `analysable_judgments` with a test that fails if a machine row ever
counts toward a preference holdout. This programme does not make that change — it is production
promotion semantics and not the directive's scope — but it records the mechanism, and no licence
in this document may be read as safe until it is closed.

### 1.2 The amendment, pre-registered before any number exists

§84 froze panel v2 before funding the batch so nobody could shop for a judge once the human
column existed. The same discipline applies to shopping for an evidence class once a forecast
column exists. If T2 ever passes at its bar, what gets proposed is exactly this and nothing
wider:

- a new `EvidenceClass` member — working name `FORECAST` — meaning *a machine judge's
  pre-registered prediction of reader behaviour, graded against the realised outcome*;
- at `Grain.STORY`, because that is the grain of the label;
- **absent from `veto_for`**, so it refuses nothing with zero code, exactly how `PREFERENCE`
  landed in §61 Add 3;
- **not accepted by `plan_search`'s judge path**, which continues to require `PREFERENCE`;
- with explicit entries in the per-class digest map and the per-class answered-count map,
  because a class absent from those dicts reads as "no staleness check requested" rather than
  as stale, and with a `why_not_promotable` clause, because an unhandled member falls through
  to the judgment arithmetic rather than being refused.

That amendment records evidence. It does not open a gate. Opening §72 to a non-`PREFERENCE`
class is a larger decision this programme explicitly does **not** propose, and if a future entry
proposes it, this paragraph is the record that it was not pre-registered here.

**The licensing ceiling, in the code's own terms.** All four tiers passing earns: bounded
selection between candidates a named separability measurement says the judge can tell apart,
inside agreement regions, capped below the measured pressure budget, expiring on use. That
licence lives in this programme's ledger, not in `promoted_gate`. It never earns the headline
claim and never earns absolute refusal of one text — `JUDGMENT` is documented as a human's
answer about one of our units, and a machine cannot become one.

---

## 2. T0 — the axiom battery. Built, selftested, run, $26.09

`research/quality-measurement/axiom_battery.py`. Machine-only, runs first, disqualifier
semantics: a candidate failing any axiom is out before it costs anything else.

    A0  indifference       two byte-identical texts. The panel must decline to choose.
    A1  format invariance  the same text under both paragraph-separator conventions —
                           §78.1's silent downgrade, elicited instead of inferred.
    A2  dose monotonicity  a nested damage ladder; preference for the damaged side must not
                           rise with dose, and must sit below 0.5 at the top rung.
    A3  transitivity       the same ladder as a tournament. Cycles are incoherence.
    A4  paraphrase         the same pairs under a rephrasing of the question, against the
        stability          floor of agreement with its own resamples.
    A5  within-item        ICC over the battery's pairs, gated on the aggregate reliability
        consistency        the arms actually report.
    A6  position           per-arm chose-A in 0.40–0.60. Free, never pooled, never inherited.

**Why this tier has teeth rather than being hygiene.** The week's two kills were both axiom
failures. §79.1 killed the default panel at chose-A 0.64 on 368 comparisons — a position axiom,
not a taste question. §70's absolute instrument died on a positivity floor — a range axiom.
Neither needed a human, a label, or a benchmark.

**Three arms have never been elicited in this project, and A0 is the embarrassing one.**
`Elicitor.variant_win_rate` states in its own docstring that "the original compared against
itself is 0.5 by construction and never elicited". That assumption has been load-bearing since
§70 and has never been checked. A4 has never been run in any form — every pairwise run to date
used `n_samples = 1`, so within-item repeat consistency has no measurement at all. A5 is the
first ICC on the *live* instrument; §70's 0.489 was measured on the dead absolute one and was
artifactual besides (five of six passages produced zero would-stop, and three of four
per-persona ICCs were degenerate).

**A4 is the highest-value arm and the reason is already measured.** Across the pairwise record
the persona is nearly inert — persona-to-passage sum-of-squares ratios of 0.0028, 0.0071 and
0.0342 — while changing the *question* by one word moved the sham from 0.7833 to 0.6833 and the
positional bias from 0.5874 to 0.6111. The question is the load-bearing knob, and no run has
ever asked whether a verdict survives rewording it. A4's within-wording floor is also exactly
the floor T1 needs, because two lineages agreeing no better than one lineage agrees with its own
rephrasing are one judge in costumes.

**The incumbent is predicted to fail, and the prediction is registered so it cannot be reported
later as a surprise.** §78 measured this panel preferring blank lines at a win rate of **0.0417
on Haiku and 0.0000 on Opus, at textbook-clean positional bias 0.5000** — the instrument is not
format-invariant, so A1 is predicted to fail. Roughly half of the ~25 per-arm bias estimates the
repo owns sit outside the band, so A6 is at risk on any near-twin arm. A tier whose likely first
result is "the default panel is not a coherent preference relation" is worth $25 precisely
because that sentence has no measurement behind it today.

**What A1 buys given that prediction** is the magnitude at the *mild* dose — the separator
downgrade riding silently on seven registered ablations, three of them inside `DEGRADERS`. That
effect is currently known only as the 0.2778 gap between §81's matched arm (0.3889) and its
formatting-confounded twin (0.1111), and the twin is void on bias at 0.6111. A direct,
bias-clean estimate converts a bound into a number. If the mild dose ties, the confound is
smaller than the ledger currently has to assume, which is a result worth having.

**What is deliberately not re-bought.** `rewhitespace` is not an arm: it is void on bias twice
(0.9375 on Haiku from 16 decided, 1.0000 on Opus from 25), and §78 records that it is a *weaker*
edit than the arms it was meant to bound in the dimension that turned out to matter. §81 already
declined to buy it and recorded the $2.80 saved. The external label is not here either — a
battery grading agreement with an outcome would be §79's benchmark, and this tier exists to be
cheaper than one.

**The ladder is nested by construction, and the reason is a measured failure.** On the CDG
battery, run at five doses, **no degrader was dose-monotone in the declared direction, and the
cleanest dose-response curve in the table belonged to the rename sham** — the transformation
that damages nothing. `ablate.paragraph_shuffle` re-samples which paragraphs move at every
strength, so "more damaged" is an assumption about the transform. `_nested_ladder` rotates a
prefix of one fixed permutation, so every position displaced at a low dose is displaced at every
higher one, and the certificate in the result file records displaced count, word-multiset
identity and layout identity per rung. A scene that cannot carry a strictly increasing ladder is
dropped before it costs a call.

**The battery is jointly non-trivial and the selftest proves it rather than asserting it.** Ten
synthetic oracles run through the whole arithmetic offline. The perfect judge clears every
axiom; every pathology dies somewhere; and A0, A1, A2, A3 and A4 each have an oracle they are
the *sole* cause of death for — including `unseparable_forced`, a judge that answers correctly
wherever a difference exists and manufactures a choice where none does, which is §83's measured
near-twin failure written as a unit test. A5 and A6 have no sole-cause oracle, and the selftest
output says so and says why rather than implying they were proven necessary.

**Two defects in this document's own pre-registration were caught by that selftest before any
call was made**, and both are recorded rather than quietly repaired:

- The monotonicity rule first read "non-increasing **and strictly lower at the top than at the
  bottom**". A *perfect* judge saturates — it prefers the base at every dose, all three win
  rates are 0.0, and the strict clause fails on the judge the arm exists to certify. The rule is
  now "non-increasing **and top rung below 0.5**", which excludes the tie-everything strategy
  without punishing saturation.
- The ICC arm first computed between-pair variance inside the ladder only. A perfect judge
  answers every ladder pair identically, so between-pair variance is zero and the statistic
  killed what it was built to certify. It now runs over the whole battery's pair set and is
  gated on Spearman–Brown aggregate reliability rather than the single-comparison figure — a bar
  on ICC(1) would disqualify an instrument that is noisy per call and perfectly usable at panel
  width, which is a bar about the wrong quantity.

**Cost and result.** 6 scenes, 54 pairs, **720 comparisons, $26.09** — 562 fresh calls and 158
replayed after a workstation shutdown killed the first attempt at comparison 158 and the digest
cache made the restart free. `--selftest` passes; `--dry-run` reads DISQUALIFIED as pre-registered.

**The run disqualifies the incumbent under both readings, and the battery needed a correction
before its verdict could be read at all.** `--operating-characteristic` — added mid-run, from
simulation, with no elicited verdict inspected — measures what the battery does to a judge that is
right on average and noisy per call, which the deterministic selftest cannot. As registered it
disqualifies a *good* judge 82–100% of the time, because three axioms read a positional band off
the decided comparisons and a judge that correctly declines to choose leaves almost none: at §85's
measured tie rate an identity arm yields ~10 decided comparisons, and at that count an unbiased
judge violates the band by sampling alone 35% of the time. A 30-decided floor drops that to
0.31–0.65, which is still too high, and the residual driver is A3's unclustered cycle null.

**So a bare DISQUALIFIED from this battery is not yet evidence about a judge.** What licenses the
reading is effect size: A6 at **0.8151 chose-A over 568 decided comparisons** is roughly 15 standard
errors from indifference and now the largest positional-bias figure in the project, past §79.1's
0.356 over 368. A2 inverts rather than merely flattening — the preference for the undamaged text is
strongest at the *smallest* dose and decays as damage grows, which is §5a's global-structure
blindness on a ladder. A4 puts ~14 points of a verdict on the question's wording. Full numbers in
§86.6.

**What a T0 pass licenses: nothing.** It says a candidate is coherent enough to be worth paying
to test against a label.

---

## 3. T1 — cross-lineage convergence. Not runnable on this machine

The design is sound and the blocker is procurement, so it is priced rather than designed around.

**What is reachable here.** One frontier lineage: Anthropic, via `ANTHROPIC_BASE_URL` and the
`claude` CLI. No OpenAI, Google, Mistral or DeepSeek key exists in this environment. Ollama holds
small open-weight models, and §70 already measured what that tier is worth as a judge:
`gemma3:4b` is void on bias twice — chose-A **0.8021 over 389 decided** on the preference
question (z = +11.9) and 0.8095 on intensity. The RUNBOOK records that this bounds *the
capability floor of the instrument*, not the questions. A 4B judge is not a lineage; it is a coin
with a vocabulary.

**So T1's price is provider access: small money, non-trivial setup.** An account and key per
lineage, an adapter per transport, and roughly **$12–40 per lineage per JudgeBench-equivalent
run** (§79.1's 368 comparisons cost $11.71 on the cheap Anthropic tier; other labs' frontier
tiers cost more per token, not less). The larger cost is that every lineage must clear T0 before
its agreement counts for anything, and on this material T0 is not a formality.

**Three corrections T1 needs before it is bought, all from this repo's own rules.**

- **The within-lineage floor must be a protocol resample, not a temperature resample.** If the
  floor is "the same judge asked twice", a near-deterministic judge scores ~1.0 and nothing
  clears it, while an unreliable judge scores low and everything does. Either way the control
  cannot fail in the intended direction, which is the first thing to check. A4's paraphrase
  agreement is the right floor.
- **Convergence must be computed only on bias-clean arms.** Four lineages sharing a positional
  artifact would converge beautifully and mean nothing, and §79.1's 0.356 makes that concrete
  rather than hypothetical.
- **A stronger tier is not the known fix for bias.** Opus-5 was measured on the same three
  repair arms as Haiku and read em_dash_strip 0.5000, em_dash_inject 0.7000 and rewhitespace
  1.0000, pooled **0.661 over 177 decided**. Any T1 candidate ladder that assumes tier buys
  positional resolution is assuming something the ledger has already measured against.

**And the assumption T1 rests on should be stated where it can be attacked:** that training
lineages are independent. Labs train on overlapping web corpora and on preference data with
shared provenance, and verbosity and sycophancy are documented cross-lab artifacts. Convergence
therefore upgrades confidence and cannot certify — and the ambiguous reading, shared truth
versus shared pathology, is the **expected** one and is pre-registered as such, so that a
universal preference is not read as vindication when it arrives.

---

## 4. T2 — prospective behavioural prediction. Three independent blockers, and the first is the premise

This is the directive's crown jewel, and it is the tier this document spent the most effort on
because it is the one whose failure mode is a wasted quarter rather than a wasted $12.

**What is right about it.** Future text cannot be memorised, which closes §70's fork completely
and answers the objection that killed CDG. Grading is mechanical. The evidence is human and costs
no solicited labour. Nothing else in the programme has those three properties at once.

### 4.1 The premise is self-contradicting on the label floor

`taste_benchmark.MIN_VIEWS = 10_000` exists because below it `followers / total_views` is noise:
§77.1's condemned pool sat at 174–1,667 views, where one follower moves the label by 0.006.
Measured on the population T2 would actually enrol — 2025-cohort LitRPG serials in the cached
shards:

    median total views at a median age of 98 days      1,245
    10th percentile                                       74
    median followers                                       5
    10th percentile                                        0
    share ever clearing the 10,000-view floor           22.3%

A serial is newly published exactly when its counters are near zero, and a retention ratio needs
a denominator. **The two halves of "prospective retention on newly published serials" cannot both
be satisfied at 30 days.** Restricting to serials that do clear the floor does not rescue it: that
restriction conditions on an outcome correlated with the label, which is a collider, not a filter.

The honest repair is not a better metric, it is calendar: lock the forecast at publication and
grade when the denominator is readable, which the measured distribution puts at months rather
than 30 days. The memorisation-safety property survives that; the schedule does not.

### 4.2 §79's arithmetic bites, and §79's repair is structurally unavailable

`conversion = followers / total_views` cannot be covariate-matched, because
`followers_hi/followers_lo = (conv_hi/conv_lo) × (views_hi/views_lo)`: match the denominator and
the numerator orders the pair. **That identity is a property of ratios, not of those two
counters**, so any prospective retention defined as a ratio of two public counters — `ΔF/ΔV` over
the window — inherits it unchanged, and differencing buys nothing.

Defining retention as growth against a t0 baseline (`F(t+30)/F(t0)`) escapes the identity,
because `F(t+30)` is post-treatment and unavailable to the judge at selection. But that escape
costs the antidote:

> **§79's repair is label-conditional selection, and a prospective design forbids it by
> definition.** The `crossed` stratum — the one that makes `min(aligned, crossed)` a bar rather
> than a number — is built by testing each popularity covariate against the *already known*
> label. At t0 the label does not exist, so the stratum cannot be constructed. **T2 inherits
> §79's confound without §79's instrument.**

What remains is incremental validity against a prose-blind forecaster computed in the same pass,
which is a legitimate design and changes the pre-registration's shape: the bar becomes a
*formula* — beat the prose-blind forecaster by margin m — rather than a number, because the
prose-blind rules cannot be scored until the outcomes land. That is acceptable if declared in
advance, and it must be declared in advance.

An unresolved risk sits under it: baseline popularity at t0 is very likely a prose-blind
predictor of subsequent growth through platform exposure feedback, which would reintroduce a
selection-time confound the crossed-stratum trick can no longer neutralise. The cached snapshot
cannot test this, because it holds one observation per fiction.

### 4.3 The positional precondition, which no candidate currently meets

T2's fixture is a matched pair of ~1,000-word openings by two different authors. The ledger's
bias measurements on that class of material:

    arm                                          material                       bias    decided
    mol_vs_rr (§77)                              two authors, unmatched         0.4375       64
    rr_high_vs_low (§77.1)                       two authors, conversion pairs  0.3810       64  VOID
    taste benchmark (§79.1) aligned              two authors, matched pairs     0.3800      200  VOID
    taste benchmark (§79.1) crossed              two authors, matched pairs     0.3274      168  VOID
    taste benchmark pooled                                                      0.356       368  VOID

**The two arms whose construction is closest to T2's — matched, same-platform, covariate-
controlled, conversion-labelled pairs — are the two that voided, and the larger of them misses
the band by 0.14 on 368 decided comparisons, roughly 5.8 standard errors from indifference.** A
T2 run with that bias is void before its accuracy is looked at.

The generalisation is the ledger's own and it cuts both ways: **bias is a property of the pair,
not of the panel.** The sharpest demonstration is that the same 72 cells moved from 0.4857 to
0.6032 when only the compared *text* changed. So `mol_vs_rr`'s clean 0.4375 cannot be inherited
into T2's pairs either. The rule that follows is not "T2 will void" but "**T2's bias must be
measured on T2's own pairs before its accuracy may be read, and the only two measurements on the
nearest material both voided.**"

**The cheap consequence, and it is the most actionable line in this document.** §79's benchmark
already *is* the screen for that precondition, it already exists, and it costs about **$12 per
candidate**. The ordering is therefore forced:

    T0 axioms ($25, built)  ->  §79 bias screen per candidate ($12)  ->  only a candidate that
    holds 0.40-0.60 on between-author pairs may have a T2 pre-registration issued for it

### 4.4 The rest of the price, measured

- **No live data path exists.** The RoyalRoad source is a frozen HF snapshot pinned by revision;
  its newest chapter is dated 2025-06-14, which is 430 days stale. BookCrawler is a
  Wayback-*only* client — it accepts a royalroad.com URL solely to rewrite it into an archive
  replay URL and never fetches the site. The DOM parser is reusable; the client, a daily
  discovery poller and a longitudinal store are not, and are days of work.
- **Terms of service are unread and unpriced.** A grep over BookCrawler for terms / robots /
  legal returns zero hits; the only compliance reasoning on disk concerns the Internet Archive,
  a different party. **Every byte this project has taken from RoyalRoad came through Wayback.**
  Fetching the site directly on a daily schedule is a new outward-facing act and is an operator
  decision, not an implementation detail.
- **Calendar is 11–13 weeks minimum** and cannot be bought down: ~3 weeks of enrolment (measured:
  241 new LitRPG fictions in a real 3-week window, 182 of them enrollable at ≥3 chapters in 30
  days, 88 disjoint pairs after matching on first-30-day word volume), then 30 days to the first
  reading and 30 more to the second, plus the scraper.
- **"Pre-registered before publication" is unachievable** for third-party serials: the earliest
  observable moment is chapter 1 going live, which is already t0. The attainable version is a
  bounded-latency lock after appearance, declared in advance.
- **Censoring is severe and informative.** Only 43.0% of shard-3 LitRPG fictions published
  anything in days 30–60; 53% of the enrollable cohort did. Abandonment is plausibly caused by
  the same latent quantity retention is meant to measure, so dropping abandoned serials is not
  missing-at-random and the censoring rule has to be pre-registered as an outcome, not a filter.
- **The prospective cohort is disjoint from the existing benchmark pool.** 17.7% of 2025 LitRPG
  serials declare AI-assisted content against 0.3% in 2021, undeclared use is unmeasurable, and
  `era_cohort` labels every post-2022 fiction as `declared_ai_2025` / `undeclared_2025` while
  `taste_benchmark` admits only `human_pre_llm`. A T2 corpus is not comparable with §79's without
  a declared change to the frame.

### 4.5 What a passing T2 would and would not buy

It would refute claim (a), which is the one thing in this programme that could. It would remain
`BEHAVIOUR`-class evidence at `Grain.STORY`, which `veto_for` refuses **by class, before grain is
even consulted**, and which `Grain.covers` independently bars from licensing a `UNIT`-grain
decision. **Both of those guard the *refusal* door. The *selection* door is `judge_license`, which
never consults grain and never reads a measured number — it tests a class name, an expiry date and
a digest, and `cmd_calibrate` records a row without enforcing promotability. So the ceiling on
selection rests on one clause, `evidence_class is PREFERENCE`, whose human-only meaning §1.1
records as unenforced. That is a materially thinner guard than three independent ones, and it is
recorded here rather than left as the impression the previous sentence gives.** §82's ruling on §79's benchmark applies verbatim: it can rank judge candidates; it
cannot license one. And the transfer from "orders other authors' openings the way retention
orders their stories" to "may pick between two drafts of our span" runs from the easiest
discrimination in the corpus to the hardest, since candidate spans are near-twins of one another
and §83 measured near-twins void.

**So T2's honest maximum is a second ranking instrument alongside §79's, bought at roughly three
months of calendar, a new scraper, and an unexamined terms-of-service question.** Certification
transfer rides along as the directive specifies: judge OOD flags on own-text against the
validation distribution are reported with every use of any licence it earns.

---

## 5. T3 — the Goodhart budget. Blocked on T1, and honest about what a within-lineage held-out set bounds

Optimise against judge A — best-of-N at rising N, plus iterated rewrite climbing A's score — and
watch the off-target measures. The N at which on-target rises while off-target falls is A's
pressure budget; the licence caps below it, scopes to agreement regions, and expires on use per
§72.

**The design is right and its held-out set is the problem.** With one reachable lineage, "held
out" degrades to a different Anthropic tier, a different protocol, the axiom battery, and
deterministic craft-profile features. Those are independent of A's *protocol* and not independent
of A's *lineage* — so a within-lineage T3 bounds **protocol exploitation** and says nothing about
taste exploitation shared across the lineage, which is the failure mode that matters, because the
thing being optimised is the lineage's taste.

**Two things make it worth running anyway, and both are cheap.**

- **The axiom battery is the one fully independent off-target measure**, because it is not a
  judge. A text optimised to please judge A while drifting into ties, length or format is caught
  by A0/A1/A2 whatever any judge thinks.
- **One implication is checkable the day the number lands and costs nothing.** `plan_search`
  runs K=3 candidates. If the measured budget is "divergence begins at N=2", the search this
  project already ships is over budget on arrival. The comparison must be made in the same units
  — best-of-N against a tournament of K — and stated in the entry that reports it.

**A confound this arm must separate in the same pass**, because the ledger's own history predicts
it: off-target scores can fall because the optimiser drifted length or layout rather than because
it exploited taste. §78 measured a 96–100% preference produced by layout alone. So every
best-of-N rung carries the deterministic certificate the repair arms already use — word-count
ratio, layout identity, protected spans — and a rung that drifts them is reported as drift, not
as exploitation.

---

## 6. What the stack cannot bound, and why the residual is not a number

The directive's framing is that whatever these tiers cannot bound is *the measured residual that
human batches exist to cover*. The correction is small and it matters:

**T0–T3 bound divergence from axioms, from other judges, and from a behavioural label. None of
them bounds divergence from reader preference, because that quantity is constituted by reader
preference and no unsolicited source of it exists.** The residual can be *named* — absolute
quality; told-versus-shown interiority, which is exactly what §85's 0.9509 leaves open; the
near-twin region where every measurement voids; global structure, where the panel is near-blind at
`transplant` −0.0125 and the CDG scorer independently near-null at AUC 0.5090 — but it cannot be
*sized* without the thing it is the residual of.

So the programme prices the anchor in the sense of naming what must be bought and in what order.
It does not price it in the sense of measuring what is missing, and an entry claiming otherwise
would be unfalsifiable. **That correction is pre-registered here so that no later result can be
read as having achieved the stronger thing.**

---

## 7. The price, totalled, against the batch it defers

    tier   status              money         calendar      engineering        blocker
    T0     RUN; incumbent out  $26.09        ~4 h          done               none
    T1     designed            $12-40/lineage days          adapter per lab    provider access
    T2     designed            ~$15/run      11-13 weeks   scraper + store    premise, label
                                                                              floor, ToS
    T3     designed            ~$40-80       days          optimiser harness  T1
    ---
    reader batch 1 (§80)       four-figure   ~2 weeks      designed           operator funding

**In money the machine stack is one to two orders of magnitude cheaper than the batch; in time it
is far more expensive.** T2 alone spends more calendar than the batch's whole turnaround, and the
batch starts a one-month §59 clock that T2's quarter would blow through on its own.

**Which settles what the programme is for, and it is not what the directive hoped.** These tiers
are not a substitute for the anchor; they are **insurance on it**. §84 already froze panel v2
before funding so nobody could shop for a judge after the human numbers arrived, and the risk that
rule manages is funding a four-figure batch to anchor a judge that turns out void on its own
preconditions — which is exactly what §79.1's candidate was. T0 at $25 and the §79 screen at $12
make that outcome cheap to discover. A batch spent on a disqualified judge is four figures and a
burnt month.

**The recommended sequence, which differs from the directive's by one edge:**

1. ~~**Now, $25** — run T0 on the default panel.~~ **Done, $26.09: the incumbent is out on three axioms (§86.6), so the $12 screen below is moot for it.** Later candidates enter at T0, not at the screen.
2. **Per candidate, $12** — the §79 screen, read for **positional band first and agreement
   second**. This is panel-v2 selection and the T2 precondition in one purchase.
3. **Fund the batch in parallel, not after.** T2 does not gate it and must not delay it: the batch
   is the only source of the residual §6 says these tiers cannot reach.
4. **T2 only if a candidate holds the band**, and only after the calendar, the scraper and the
   terms-of-service question are accepted as costs by the operator. Its 11–13 weeks then run
   concurrently with everything else, which is the only way they are affordable.
5. **T1 and T3 when provider access exists**, and not before — a within-lineage T3 would report a
   budget that does not bound the exploitation anyone is worried about.

---

## 8. Kill conditions, declared before any tier runs

- **T0** — any axiom fails → that candidate is out of the programme entirely, recorded as failed
  even if narrowly. §81's lesson: the rule as registered is what gets reported.
- **§79 screen** — no candidate holds 0.40–0.60 on between-author pairs after the candidates §77's
  2×2 points at → **T2 is unreachable at this frontier**, and the ledger records that the
  prospective channel closed on positional resolution rather than on prediction.
- **T1** — lineages agree with each other no better than one lineage agrees with its own
  rephrasing → one judge in costumes; cross-lineage convergence is abandoned as an instrument
  rather than reported at a lower bar.
- **T2** — at chance against the prose-blind forecaster after N pre-registered pairs → the trace
  channel is closed and solicited readers are the only Tier 2 left. Also killed, without
  elicitation, if the enrolled cohort cannot produce pairs whose t+60 denominators clear the noise
  floor.
- **T3** — divergence at N=2 → no budget exists, selection is unlicensed regardless of every other
  tier, and `plan_search`'s K=3 is over budget by inspection.
- **Programme** — §82's rule stands verbatim. No machine-only result upgrades any licence, and no
  bar in this document moves after a number arrives.
