# Calibrating the simulated readership: matching what a population did, never asking anyone what they think

**Status: PRE-REGISTRATION, 2026-08-21. Nothing here is built.** No code, no schema, no table, no
number. Written before any book of this project's carries a retention curve, which is the only
thing that makes it a pre-registration rather than a report — and, unusually, before the decision
that would license it has been taken at all. The stage-0 entry is §106.

Stage-0 §97 owns the programme this belongs to: **the readership is the reward model, the real
population through the library is the settlement layer**, and §97.7's G5 is the flow from the
second to the first — *"publication settlement: sim forecasts against real telemetry, the only
scoreboard that compounds."* G5 reads that comparison. This document is about the **return leg**:
whether, and under what constraints, the settlement layer's own numbers may be used to *correct*
the reward model rather than only to grade it. That question has no home, which is why this file
exists; `plan/anchor-set.md` is the precedent for what a §97 companion doc is.

**Regime.** Unsolicited aggregates only, and one clause stricter than the method allows.
Retention curves, follow counts and rating histograms are **marginals a platform published about
readers nobody in this project ever contacted**. The individual-level variant of this method needs
per-person response rows and is closed twice over — see §0.1. Nothing here asks any human
anything, at any point, in the fit or out of it.

---

## 0. Track 0 — the gate this document poses and does not close

First, because a scope that arrives after the numbers is not a scope, and because on this
particular question the scope *is* the deliverable: what follows is a registration, not a plan.

### 0.1 The individual-level variant dies twice, and the second death is the one that matters

SYN-DIGITS (arXiv 2604.07513, Columbia, April 2026) stacks a matrix of real human responses on a
matrix of simulated ones and treats the sim-to-real gap as a synthetic-control / matrix-completion
problem. Its headline is **individual-level**: predict a *named person's* response to a new item
from that person's responses to past items plus the sim's. Reported gain, up to **+50%
correlation** over uncalibrated simulation.

That variant is closed here twice, independently:

- **By the scope axiom** (§95): *no solicited human judgment, ever — not hired, not operator, not
  one blinded pair*. Per-person response rows are exactly solicited judgment with a name attached.
- **By the platform.** RoyalRoad exposes aggregates and never per-reader response rows. There is
  no column to read.

**The second closure is the load-bearing one and it is worth saying why.** An axiom can be argued
with; a later session with a good reason and a tight deadline can propose an amendment to it, and
this repository's ledger contains several. A missing column cannot be argued with. Recording both
means the refusal survives a change of mind about the first.

**The distributional variant survives, and it survives cleanly.** §7 of the paper needs only
**marginal distributions per item**: reweight the *n* simulated personas — plus *K* degenerate
members, each of which always returns one fixed response so the ensemble has full support — on the
probability simplex, by mirror descent, until the ensemble's response distribution matches the
observed marginals on past items; then read the new item's distribution off the reweighted
ensemble. Reported: **50–90% reductions in distributional divergence**, with TV and KL the most
robust training objectives, and an error that decomposes into an irreducible reweighting gap plus a
term of order `sqrt(K/n)` which degrades as the new item leaves the span of the past ones.

Marginals are what a platform publishes. Nothing is solicited to obtain them.

### 0.2 Whether settlement data may reweight the reward model is an unmade decision — and §97 points two ways

The README's constraint is about the **operator**: he *"trains, calibrates and selects nothing."*
That sentence is silent about the population, so it does not settle this.

§97 is not silent, and that is the problem: two of its clauses point in different directions, and
no entry has reconciled them.

- **§97.5 appears to license the flow and fix its cadence.** *"The sim is frozen per production
  cycle. The writer optimises against a frozen sim; sims update only between cycles, from new
  unsolicited data, and never from the writer's outputs within the cycle they are judging."* A
  reweighting is a between-cycle sim update from new unsolicited data. On this reading the answer
  is yes, at that cadence, and the only open question is engineering.
- **§97.2 forbids exactly this shape, for a different source.** *"The permission is to **read** the
  comparison; the prohibition is on **feeding it back**."* That was decided for operator traces,
  with the stated reason that a programme tuning the sim to a trace *"would have quietly made one
  person the reward model"*. The reason does not transfer — a population is not one person, which
  is the whole architecture — but the **shape** does: G5 is a comparison, and reweighting is
  feeding it back.

**So the question is narrower than "may population data reach the sim", and stating it narrowly is
this section's only job.** It is: *does correcting the reward model against the settlement layer's
marginals count as §97.5's permitted between-cycle update from unsolicited data, or as §97.2's
prohibited feeding-back of the settlement comparison?* This document **poses that and does not
answer it.** A session that answered it here would be settling a §97 amendment from a companion
doc, which is not how anything in this repository has been decided.

**The trigger for deciding it, declared now so it is not decided by drift:** *books of this
project's are live on RoyalRoad and real aggregate data is accumulating against them.* Before that
the question cannot be answered usefully, because it cannot be answered concretely — nobody knows
which marginals the platform will actually expose for a serial of ours at what cadence, and a rule
written against imagined columns is a rule written against nothing.

### 0.3 Cold start: the input is empty, so today's answer costs nothing either way

There is nothing to calibrate against until published chapters have accumulated real aggregates.
This is **post-launch only**, and the observation is not a caveat but the reason §0.2's deferral is
free: an unanswered question whose input set is empty forecloses no work. It also means this
document adds **no line item** to §97's cost table. When it stops being free it will be because the
trigger fired, and that is exactly when the decision is owed.

---

## 1. The mechanism, and why the admissible half is the half that fits

### 1.1 The gap is structural, not informational — the number that reframes the whole method

The single most useful result for this project is not the headline. It is the control beside it:
handing the simulation **249 ground-truth ratings in context** bought **+16%**; calibration bought
**+50%**. Prompt enrichment does not fix simulation bias.

That is a familiar shape here. It says the sim's error is a *systematic displacement* of its
response distribution rather than a shortfall of evidence — so the repair is a correction applied
to the output, not more context on the input. Every instinct this project has about making a
reader-model better by telling it more is, on this evidence, the weaker lever.

### 1.2 The response type the method requires is the one §97.4 already fixed

The distributional variant is defined for **structured or categorical responses**; free-form text
is open in the paper. §97.4 fixed the sim vocabulary independently and for unrelated reasons:
*continue, abandon, return*, under a declared budget, and **"no verdict slot exists anywhere in a
sim"**.

Those two facts meet exactly. The admissible half of this method needs a categorical response
space, and this project already refused itself everything else. **A behavioural read-on / drop
response is precisely the datum the method can calibrate**, and the verdict slot that would have
been out of scope is a slot §89.4 already abolished at 4,676-to-1. Recorded because it is a
coincidence worth not mistaking for a design: nothing was chosen here to fit the method.

### 1.3 What it is not

It is not a fidelity gate and cannot replace one. §97.4's gate is **directional** — a property is
promoted only if injecting or removing it *"moves the sim's behaviour in the same direction it
moves real readers."* Distributional matching says the ensemble's output distribution lands where
the population's did; it says nothing about whether the sim moves the right way when the text
changes. A sim can match every marginal and respond to nothing. **The two are complements and the
gate is the one that can fail for the right reason**, so calibration is never a substitute for it
and a calibrated sim still owes §97.7's G2 and G3.

---

## 2. Order of operations — calibration sits above instrument validity, and the ordering is the filing rule

**Reweighting a channel with a known defect calibrates noise.** This is not a worry; it is the
repository's most repeatedly measured lesson pointed one layer up.

- T0's verdict channel carried a positional bias of **0.8151** over 568 decided comparisons. A
  channel answering a *side* can be reweighted until its marginals match a population perfectly
  and it will still be answering the side. It would then be a defect that agrees with the data.
- §94.6 is the sharper case and §4(b) below turns on it: `qwen3:14b` returned `ABABABABABAB` in all
  six sessions and `gemma3:12b` returned `AAAAAAAAAAAA`, and **"both fixed-pattern readers would
  have passed every declared control"**. Constant behaviour survives placebos, shams and positional
  checks. It would also fit marginals beautifully.
- §95.15's class — *"a guard that ran, produced a value, and had no path to a verdict"* — is what a
  calibration layer becomes if it is added before the instrument beneath it can fail.

So the order is fixed here and is not negotiable by convenience: **instrument defect-hunting stays
upstream.** §94.6's P1–P5 preconditions, `plan/llm-reader-engagement.md` §A3's D1–D4 battery, and
§97.7's G1–G3 all run, and clear, *before* any weight is fitted. A calibrated broken instrument is
strictly worse than an uncalibrated broken one, because it has acquired agreement with the data as
a property and lost the disagreement that would have exposed it.

This is also why this material is a **separate document** rather than a section inside
`plan/persona-reader-validity.md`. That file owns the gates that must stay upstream; filing the
layer that must stay downstream one heading below them is how an order of operations gets lost. A
second home for one question is a defect in this repository — this is the first home for the
question above it.

---

## 3. The bars, declared here and attainability-checked before anything runs

Per the declared-bars rule (§87, and §89's rulebook): a bar states its **range, direction, unit and
non-emptiness**, and argues attainability, or it is a defect rather than a plan.

### 3.1 Declared now, because they can be declared without a number

**B1 — the refusal diagnostic must be able to refuse and able not to.** The paper's adaptive
transfer applies the learned correction only when a fit diagnostic says the target is in the span
of the past items, and falls back to the raw prediction otherwise; that alone **doubled** their
gain, from 19–21% to 50%. As a bar here:

    quantity   fallback rate over the calibration set: the share of target items the
               diagnostic declares out of span
    unit       a share in [0, 1], dimensionless
    direction  both ends are failures, for different reasons
    bar        strictly between 0 and 1, on the set the correction is actually applied to
    empty?     no — both endpoints are reachable and both have been reached in this
               repository's own history, which is why the bar is stated this way

At **0** the diagnostic never refuses, which §97.7's G3 already calls a failure in the instrument
below it: *"a sim that always has an answer is measuring its own noise."* At **1** the correction
never applies and the layer is inert. This is the one bar that can be honestly written before any
data exists, because it is a statement about the diagnostic's own behaviour and not about an effect
size.

**B2 — the fallback rate is decomposed or it is not reported.**
`plan/persona-reader-validity.md` §1 measured that *"wouldn't answer", "answered in the wrong
format"* and *"answered differently"* are three failures, and that the middle one *"is a property of
the transport rather than of the reader."* An undecomposed refusal rate is a JSON-parser statistic
wearing a validity name, and B1 stated on it could be cleared or failed by the deserialiser.

**B3 — the ensemble's variance retention is reported with its own refusal state.** Simulated
ensembles over-concentrate; the paper tracks predicted-variance / true-variance ≈ 1 as a health
check, and it belongs here. Two traps have to be handled at declaration time, not after:

    quantity   ratio of predicted between-reader variance to true between-reader variance
    unit       a ratio of variances, never reported in a column with TV or KL
    direction  two-sided: over-concentration and over-dispersion are both failures
    range      floored at 0, unbounded above, so a band written symmetrically around 1
               is symmetric in no space that matters — declare it in log space, or
               declare two bounds
    empty?     **the denominator has been measured at zero in this repository.** The
               persona panel returned keep-reading on 195 of 196 draws with every variance
               statistic undefined rather than failed. A ratio with a zero denominator has
               no value, so this check returns a declared refusal state and never a pass.

### 3.2 Deliberately not declared, and declaring it would be the defect

**No divergence-reduction bar is stated here**, and the omission is the point. Three reasons, each
sufficient:

1. **The 50–90% figure is theirs, on their task.** No σ exists for any response distribution of
   this project's, because no such distribution has been measured against a population.
2. **A percentage-reduction bar gets easier the worse the raw arm is.** It is measured against the
   uncalibrated sim, so a weaker baseline clears it more readily — which is exactly what §5's
   equalizer result says happens. If a bar is ever stated it goes on the **calibrated absolute
   divergence**, with the raw printed beside it, against the baselines §97.5 already seats: the
   coin, and the text-blind constant that took 0.8804 of the promoted ensemble before it was
   repaired.
3. **This is the §101.4 pattern applied unchanged.** δ was not proposed there before G1 produced a
   σ, on the stated grounds that inventing a bar and then discovering whether it was reachable is
   the failure the rulebook exists to prevent. **The σ comes first; the bar is signed after it and
   before anything binds.**

### 3.3 Two traps the marginals themselves carry, recorded before anyone reaches for them

**The bar's domain may be empty before its threshold is.** On the population measured in
`plan/judge-validity-program.md` §4.1 — median total views **1,245** at a median age of 98 days,
median followers **5**, 10th percentile **0**, and only **22.3%** ever clearing the 10,000-view
floor — a launching serial's follow or rating marginal has almost no mass to match. And restricting
to serials that clear the floor *"conditions on an outcome correlated with the label, which is a
collider, not a filter."*

**A follow-derived marginal is orderable by size rather than by prose.** §56.3 measured that
`followers / total_views` deciles are recoverable from follower count alone at **AUC 0.814**, and
§4.2 of the same document records that the ratio identity makes covariate matching structurally
unavailable. Any marginal built on those counters states `plan/craft-corpus.md` §4.1's covariate
control **before** the bar, not after it.

**Retention marginals are informatively censored.** Only **43.0%** of shard-3 LitRPG fictions
published anything in days 30–60. A retention statistic computed on the survivors measures
survival, and the censoring rule is pre-registered as an outcome rather than applied as a filter.

---

## 4. Binding constraints on any future sim-readership implementation

These bind whether or not §0.2's gate ever opens, because four of the five are cheap now and
impossible to retrofit later. This is the operative part of the document.

**(a) Per-reader × per-item responses persist in matrix-completable form.** The stacked formulation
needs a response matrix. A readership that stored only pooled statistics would have to **re-run
every simulation** to obtain one, and on the substrate §94.6 describes that is GPU time nobody
budgeted. So each session persists the individual cell — (reader model × persona) against item —
and not only the aggregate computed from it. Cheap now; a re-run later.

**(a′) The sim and the settlement layer must be made to answer the same item, and today they do
not.** This is the constraint the others assume and is stated separately because it is the one that
can silently fail. The BCR's datum is an **allocation share between two texts** under a forced
budget; a platform's marginal is **retention on chapter k** of one text. Those are different item
spaces, and a matrix cannot be completed against a matrix whose columns mean something else. Any
implementation declares the mapping — or declares an item type both sides can answer — **before**
it fits anything. Without this there is nothing to stack, and the appearance of a fit would be an
artefact of the join.

**(b) Support is guaranteed by degenerate members, and the degenerate members are fenced.** Full
support is what makes the reweighting well-posed, and *K* always-one-answer members are how the
method gets it. **In this repository that object has a history.** §94.6: a strict alternator and a
never-leaves-slot-A reader *"would have passed every declared control"*, and two of four reader
candidates died to a check that was not in the design. §97.5: a text-blind constant took **0.8804**
of a promoted ensemble before the market was repaired, and constants are now *seated as baselines*.
So the constraint is not "include dummy twins" — it is:

- their total fitted weight is **printed beside every headline**, never folded into it;
- a fit in which they carry the majority of the mass is a **refusal state**, not a result, on
  §95.15's rule that a guard producing a value with no path to a verdict is the defect;
- they are admitted as **support machinery**, never counted as personas, and never merged into the
  panel-size arithmetic `plan/persona-reader-validity.md` §1 caps at four.

**(c) Ensemble concentration is part of the readership's standing health reporting**, per B3 — not
a diagnostic somebody runs when a result looks wrong. A sim that has quietly collapsed onto one
behaviour is the 195/196 failure returning through a different door, and the only defence that has
ever worked here is reporting the statistic every time rather than when suspicious.

**(d) A correction that cannot refuse is not accepted.** Every learned correction ships with its
in-span diagnostic and its raw fallback, and B1 binds. This is §97.7's G3 applied one layer up: the
rule that a sim must refuse rather than confabulate on near pairs is the same rule a corrector owes
on out-of-span targets, and the paper's own evidence is that the refusal is where most of the value
was.

**(e) The correction's own footprint prints beside the headline.** Whatever the calibrated number
is, the uncalibrated one prints next to it, with the fitted weight vector and the fallback rate.
The precedent is this repository's only other post-hoc correction, `plan/force-program.md` §2.3's
label-blind nuisance regression: *"Both the raw agreement and the residual agreement print."* And
the general rule is §89.2's, restated in force-program §1.2 — **both readings print wherever a
choice exists**. A post-hoc adjustment whose size is invisible is one nobody can audit.

---

## 5. The equalizer, recorded as a decision input and not as a claim

Calibration compressed the paper's model spread: baselines ranging **.048–.205** landed at
**.204–.243** calibrated. It also **reordered** them — the best raw model was not the best
calibrated one, and their fine-tuned simulation went from **worst raw (.048) to best calibrated
(.243)**.

If that transfers, the economics of model choice change shape: **cheap personas plus a correction
layer may dominate expensive personas run raw.** That is a real input to the force programme's
model-choice reasoning and to §97.4's seat-earning battery, and it contests
`plan/llm-reader-engagement.md`'s working premise that the frontier ordering is the reference.

**It is recorded as an input and not as a claim, and the distinction is enforced by two things this
document cannot supply.** The numbers are theirs, on their task, and this project has already
measured that a model ranking does not transfer — §94.6 killed two of four candidates on a control
absent from the design, and §97.5's market ranked stated confidence until it was repaired. So the
implication earns a line in the decision inputs and **no seat is re-opened on it**: the
freeze-before-anchor discipline holds, and a calibrator that reorders models must not become a
reason to reopen model selection *after* the marginals have been read.

---

## 6. Anti-scope

No code, no migration, no table, no calibration implementation — no mirror descent, no reweighting,
nothing fitted. Nothing in `research/quality-measurement/`, the pools, preference or judge stores,
or provider code is touched by this document. No new quality or craft metric. **No individual-level
calibration, ever**, on either of §0.1's two closures. No RoyalRoad scraping, collection, polling or
account activity of any kind — §4.4 of `plan/judge-validity-program.md` records that no live data
path exists, that terms of service are unread and unpriced, and that fetching the site directly is
an operator decision rather than an implementation detail. Nothing here solicits judgment from
anyone (§95), and no human data enters any loop. **§0.2's gate is not closed by this document and
may not be treated as closed by anything that cites it.** No licence moves: FORECAST stays at STORY
grain, absent from `veto_for`, and a calibrated sim earns exactly what an uncalibrated one earned
until an entry says otherwise. And no bar in §3 moves after a number arrives.
