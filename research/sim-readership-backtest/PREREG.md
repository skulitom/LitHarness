# Pre-registration — can a simulated readership post-dict the real Royal Road market?

**Status: REGISTRATION, 2026-08-24** — every slot filled from free sizing runs before any
paid call; the registering commit is this file's own history. Nothing measured before this
commit may be reported; nothing below may be edited after the first paid call, and an edit
forced by an error must name the number it had seen (the pitch-reader K1a precedent).

The question: does a simulated readership, reading blind, predict which of two real Royal Road
books the real readership stayed with — better than chance, on held-out pairs, with certified
controls? A pass makes the sim a **candidate** reward model and the launch its out-of-sample
test. A fail means the sim cannot be a reward model in its current form, learned at API cost
instead of months of publishing. Either answer is the deliverable; the job is a valid number,
not a favourable one.

## 1. Unit, corpus, and the outcome variable

**Unit of analysis: the matched pair of real RR fictions**, work-disjoint and author-disjoint
across the whole pair set (§79's rule: one fiction and one author appear at most once).

**Corpus: the twelve local shards of `OmniAICreator/RoyalRoad-1.61M`** (train-00001 through
train-00006 and train-00028 through train-00033, of 47), read-only, one crawl date, no live
fetches in the confirmatory path. Every excerpt actually shown to a persona is cached content-addressed
(sha256 over the blinded bytes) and every reported number carries the hashes it was computed
from. No scraping: the dump already holds blurbs (`description`), completion `status`,
`ratings` counts, and the engagement columns.

**Outcome: `conversion = followers / total_views`** — the platform's own acquisition-to-
retention ratio, already the house's one named derived engagement field (`corpus_io`), computed
from dump-frozen metadata so it cannot drift under us. Exposure guards rather than an exposure
model: a fitted exposure regression would be a researcher degree of freedom, so age, chapter
count and status enter as **matching variables** and a raw-exposure floor
(`total_views >= 300`; the survey's working floor, which 11,878 books clear together with the
rest of the eligibility stack) enters as an exclusion. **Star ratings are not
the outcome and are not a matching variable**: they are the most socially confounded signal on
the platform — and the dump enforces the rule for us (all five score columns are 100% null).

**A pair diverges only on outcome**: members agree on era cohort (`corpus_io.era_cohort`),
lead tag family, chapter-count band (short <8 / mid 8-24 / long >=25, counts recovered as
`round(total_views / average_views)`), completion status, blurb present (>=30 words), and
chapters 1-3 identifiable — and differ by **>= 3x in conversion**. Declared-AI books
(`declared_ai_2025`) are excluded from every arm: §104 verified the tag is mandatory policy,
so their outcome carries the tag's own audience effect.

Measured by the sizing survey (free, read-only, the F3-survey precedent) over the twelve
local shards: 22,397 fictions / 412,056 chapters; blurb-eligible 20,489 (91.5%); chapters 1-3
identifiable 15,281 (68.2%), of which 14,716 carry >= 1,500 words; the full eligibility stack
leaves **11,878 matchable books across 154 cells**, naive pair capacity 5,902, and a
**divergent-pair capacity of roughly 989** at the >= 3x conversion gap. The largest cells sit
in `human_pre_llm` and `undeclared_2025` across LitRPG / Progression / other at every band.
`status` is unrecorded (None) for 17,476 books, so status matches as recorded, None to None.
The confirmatory set is drawn from the `undeclared_2025` cells at and after the panel model's
cutoff, then recognition-screened; if what survives falls under §8's power target, the
registered verdict is INSUFFICIENT_N.

## 2. Arms

- **C-arm (primary): continuation.** Blinded chapters 1-3, each side capped at 6,000 words with
  truncation only at a paragraph boundary and the truncation recorded. The question the
  programme is named for — which book the readership *stayed* with — is this arm.
- **P-arm (secondary, own alpha, exploratory for qualification): premise.** Blinded blurb plus
  the first ~500 words of chapter 1 (to the paragraph boundary past word 500). Answers the
  acquisition stage of the funnel; reported beside the C-arm, never pooled with it.

Chapter identity: a chapter counts as 1-3 when its parsed `chapter_title` ordinal says so, or
when the dump provably holds the whole fiction (cached count >= recovered count) and release
order identifies them.

## 3. The recognition screen — a first-class VOID class

The model has read Royal Road; a "prediction" that is recognition of a known book is invalid
while looking valid, and this is the likeliest way the whole result dies.

- **Every candidate book is probed before any main-arm call**, with the same blinded excerpt
  the main arm would show: (a) name the title; (b) name the author; (c) continue the excerpt's
  final sentence for ~50 words. Scoring is code: (a)/(b) hit on normalised containment of the
  true title/author (stopword-stripped, case-folded); (c) hit when any 8-gram of the
  continuation matches the true next text verbatim. **Any hit on any probe on the panel model
  excludes the book** into a labelled `recognised` stratum (there is no spot model in
  this programme — the sentence below is why).
- The confirmatory set is recognition-clean AND, where the platform's dates allow,
  **cutoff-clean**: first release on or after **2025-08-01** — the panel model
  (`claude-haiku-4-5`) carries a documented training-data cutoff of July 2025 (platform model
  overview, fetched 2026-08-24). The rest is exploratory. **No frontier spot model touches an
  excerpt anywhere in this programme**: every current frontier model's cutoff (May 2026 for
  `claude-opus-5`) postdates the entire 2025 dump, so a spot model would empty the
  cutoff-clean set by existing. The panel model's memory is the only model memory in the loop,
  and it is the one the probe screens.
- **Measured before any paid call** (the deterministic pair build over the twelve shards,
  committed as `pairs-v0.json`: 2,014 pairs at the registered floor, 963 in
  `undeclared_2025`): the cutoff-clean pair set is **empty** — no pair has both members
  first released on or after 2025-08-01, because the crawl predates that horizon. The
  confirmatory set is therefore the recognition-clean `undeclared_2025` pairs, and the
  probe carries the entire memorisation defense; the corpus's own obscurity (median one
  follower) is contextual mitigation, stated rather than weighed. The number seen when
  this clause was added: zero, from that pair build, before any call.
- The `recognised` stratum may be run and reported separately; it certifies nothing.
- If the screens leave the confirmatory set below the power target, the registered verdict is
  **INSUFFICIENT_N**, reported as such — not a smaller floor.

## 4. Blinding — code, tested, hashed

The blinding function strips identity and popularity, never craft: the fiction's title and the
author's name wherever they appear in the text (exact and normalised forms), chapter-title
lines, URLs, "Royal Road"/platform self-references, author's-note and patreon/discord blocks,
review or rating text. It does **not** rename characters (renaming is a §120 sham arm, not
blinding), does not reflow paragraphs (the paragraphing confound must stay measurable, not be
laundered), and does not touch the prose otherwise. Its output is what gets cached and hashed;
its tests pin every stripped class with a constructed positive and a near-miss negative.

## 5. Framing — describe-then-behave, behavioural vocabulary only

The one surviving frame (§89's E6; §120's inheritance): the persona first names concrete
differences between the two excerpts (stage 1, free text, never scored, operator-side
diagnostic only — §97.1), then emits one schema-constrained behavioural action:

    {"continue": "A" | "B" | "neither"}    # neither = would abandon both

plus at most one reason code from a closed list. No quality vocabulary anywhere in the schema.
"Neither" is an undecided observation: dropped from accuracy, counted, and its rate reported
per persona and per arm. Every pair runs in both orders for every persona.

## 6. Population, not panel

A new module owns **ten personas parameterised on explicit taste axes**: genre priors over the
matched tag families, slow-start tolerance, progression-payoff appetite, prose-register
preference, and trope-familiarity appetite. Frozen at registration; the module's persona table
is content-hashed and the hash printed in every result file. `personas.PANEL` and
`personas.GENRE_PANEL` stay untouched so §70's and §120's numbers remain reproducible.

**The split precedes everything** (the reader-judge-loop's I1 discipline): each persona is
assigned by content hash of its id with the registered salt `sim-backtest-v0-2026-08-24` to
the **reward split** (6 personas — eligible to become the reward model later) or the **holdout split**
(4 personas — never reward, kept for future Goodhart detection). Both are evaluated; only the
reward split's number decides qualification.

**The aggregate prediction** for a pair is the unweighted mean, over reward-split personas and
both orders, of decided votes for each side; the predicted side is the majority and a pair
with a tied or empty vote is undecided (counted, reported). The §120 health signature —
convergence on gross damage, scatter on shams and noise — is reported descriptively; a
population that agrees on everything is a diff-spotter, and that observation travels with any
pass.

## 7. Controls, each with its registered pass condition

- **C1 — sham pairs** (n = 12): two different excerpt windows of the *same* book presented
  as a pair. Not byte-identical (a sham that cannot move is no control — §120.2), same
  outcome by construction. Floor: the largest per-sham |continue-share − 0.5|, read per sham
  and never pooled. The primary effect must clear the largest sham deviation by **+0.05** in
  absolute distance (the K2 form). A sham deviation exceeding the primary effect voids the arm.
- **C2 — the damage arm**: standing certified transforms (`paragraph_shuffle`,
  `sentence_deletion`, `stat_flatten`, `interiority_strip` with its matched control) applied to
  one member of matched-outcome pairs. `jargonise` is not reused (withdrawn by the operator,
  §120.3) and no transform outside `ablate`'s standing set is invented here. Pass: the
  population detects damage with a lower bound above 0.5 at the registered alpha. A population
  that cannot see gross damage cannot be trusted on subtle divergence, and the qualification
  fails on this alone.
- **C3 — the label-shuffle null**: the full analysis path run on outcome-shuffled pairs.
  Expected: chance. A shuffled lower bound clearing 0.5 means the analysis leaks the label and
  **everything** is VOID.
- **C4 — the surface-confound arm**: pairs matched on outcome, divergent on formatting
  (paragraph-length quartile, stat-box/table density). Its deviation measures how much of any
  signal is the paragraphing confound wearing a new coat; if it reaches the primary effect,
  the primary is formatting and qualification fails. Its sign is expected to be shared with
  the primary, so it is **reported beside it, never subtracted** (§121's lesson).
- **Positional VOID**: the panel-level first-position rate over decided comparisons. If the
  positional deviation exceeds the largest true-pair effect, the arm is VOID (the 0.6725
  precedent capped §120's sensitivity; the same rule, unchanged).

## 8. Power and staging

Sizing was measured three times, and the first two attempts are findings rather than waste:
(1) the persona-grain two-way clustered bound (documented in
`research/preference-power/FINDINGS.md` §1; 10 readers,
sigma_reader = 0.8 — the heterogeneity the population carries *by design*) has **zero power
at every candidate size**, so no per-persona claim is registered anywhere in this document;
(2) an unconditional null that redraws personas each simulated world converts persona-draw
variance into false clears (type-I 0.21-0.34, rising with n) — which is why the primary is
registered **conditional on the frozen reward split**, the only claim the frozen-population
design makes anyway. The conditional arithmetic, exact binomial at the pair-bootstrap's
rejection rule (z = 1.96 on the normal-approximate lower bound):

    n_decided | power@0.60 | type-I@0.50 | power@0.65
          120 |      0.612 |      0.0274 |      0.923
          160 |      0.715 |      0.0239 |      0.970
          200 |      0.826 |      0.0280 |      0.992
          240 |      0.868 |      0.0226 |      0.997

**Target: 200 decided confirmatory pairs** (>= 0.80 power to distinguish 0.60 from chance).
The surveyed divergent-pair capacity (~989) covers the target with room for the screens'
attrition; if the recognition and cutoff screens leave fewer than 200 decided pairs, the
registered verdict is INSUFFICIENT_N.

Staging, each stage with its own PID lock (the `force_remote.SingleRun` pattern) and cost
ledger, replay caches keyed by request digest:

- **(a) dry run** on the fake transport — plumbing only, spends nothing, never waits on a paid
  arm.
- **(b) pilot** at ~10% of target n with all controls live — proceeds to (c) only if no VOID
  fired and the cost ledger matches the estimate within 2x.
- **(c) full run** — one confirmatory look. Everything after it is exploratory and labelled.

Panel model `claude-haiku-4-5`, no spot model (§3's cutoff reasoning — a 2026-cutoff frontier
model reading excerpts would void cutoff-cleanness by construction). Cost ceiling for the
whole programme: ~~**$180**~~ **$900 (raised 2026-08-31 by the operator after the pilot
measured the registered basis 6.2x low; his words and the numbers seen are recorded at
`backtest.COST_CEILING_USD`; quota-denominated)** on the haiku panel — dominated by the C-arm's ~4,000 two-turn
sessions over up-to-6,000-word excerpt pairs; the P-arm, the probes and the control arms are
small beside it. The ceiling is a refusal, not a note, and stage (b)'s ledger check (pilot
cost x 10 within 2x of estimate) is what keeps it one.

## 9. Primary metric and the decision rule

**Primary: pairwise accuracy of the reward split's aggregate prediction on the confirmatory
(recognition-clean, cutoff-clean where possible) C-arm pair set — a claim conditional on the
frozen reward split**, with a pair-resampled percentile bootstrap interval (2,000 resamples,
seed content-derived from the outcome vector), alpha = 0.05, one candidate (no alpha division
— nothing here selects among candidates). Conditional on the frozen personas the pair
bootstrap is calibrated (§8's measured type-I, 0.022-0.028 at every candidate n); the two
rejected designs are §8's record. The persona-grain two-way clustered number (the retired bound,
cells = (persona, pair), both orders one cell, HALF_WIN) is reported as a **descriptive
secondary only** — §8's simulation showed it cannot power at this population's registered
heterogeneity, and a number that cannot fire may not carry the qualification.

**The sim qualifies as a candidate reward model iff** the interval's lower bound clears 0.5
AND no VOID condition fired AND the damage arm passed AND the sham floor held. Anything else
is a documented failure to qualify — a finding, not a shortfall to argue around.

Secondary, exploratory, labelled: P-arm vs C-arm accuracy (funnel location), per-persona
accuracy and abandon-both rates, reason-code distributions, the holdout split's number, the
`recognised` stratum.

## 10. The analysis code path

`research/sim-readership-backtest/`: `corpus.py` (pairing + matching + content-addressed
cache), `blinding.py`, `recognition.py`, `population.py` (frozen personas + split),
`arms.py` (session construction, describe-then-behave, both orders), `analysis.py` (accuracy,
the pair-bootstrap primary interval, the descriptive clustered-bound
secondary, VOID evaluation, label-shuffle, health signature), `backtest.py` (staged driver). Transport is `elicit.Elicitor` with its
digest-keyed cache; every number in FINDINGS.md reproduces from the cached JSONLs via
RUNBOOK.md with no live call.

## 11. What a pass does and does not license

A pass makes the reward split a **candidate** reward model: it licenses the launch as its
out-of-sample test and nothing else. No gate, no selection among candidate books, no prompt
ever built from its outputs (§97's containment and §61(5) stand); the holdout split never
becomes a reward model and exists to detect Goodhart drift after any deployment. The scope
axiom stays closed: no human judgment is solicited anywhere in this programme, and the
operator's role is the one-bit gate on shipping its artifacts.

## Post-hoc amendment (2026-08-31)

**Sections 1-11 above are the registration and are not edited by this section.** Nothing above
this line has been touched; this is an appended change to the analysis rule, proposed *after*
the re-pilot's control-arm numbers were seen. That is the definition of post-hoc and it is
labelled post-hoc everywhere it appears: here, in the code (`analysis.SHAM_MIN_DECIDED`,
`backtest.STAGE_SALT`, `backtest.AMENDMENT_SECTION`), and in every result file the amended
code writes (`amendment`, `verdict_amended`).

**Every choice below is justified by a mechanical property of the statistic or of the
transport, and never by which verdict it produces.** That sentence is a constraint on the
drafting, not a compliment to it; §A.4 is where it is checked against the one dataset that
could tempt it, and the check reports that the amendment does not rescue the pilot.

**The operator's directive, verbatim:** "draft the amendment, run the full after reset".

One consequence of this section's existence, stated so nobody has to discover it: appending it
changes PREREG.md's bytes, so `result-pilot.json`'s `prereg_sha256`
(`cd52010fd3081f7e2834da7c57bce99828ba03dd1772702c23fcf657b51930db`) is the digest of the
registration as it stood at the pilot, and any later run's digest will differ from it. The
difference is exactly this section, and `amendment.section_sha256` in the result file addresses
it on its own.

### A.1 What the pilot measured (K1a form: every number seen is named)

All figures from `result-pilot.json`, stage (b) second run, 2026-08-31, under registration
digests `population_digest d024470d5266ea63` and `pairs_digest a3a877f35183c602`.

- **Run health.** 40 books probed, **0 recognised, 0 unprobed**; 0 transport failures; 0
  degenerate stimuli; 0 skipped pairs. Votes returned against planned: C 400/400, P 400/400,
  sham 236/240, damage 289/300, surface 119/120. Ledger $175.047 against a $123.00 estimate
  (within the 2x rule) under the $900 ceiling; no ceiling abort.
- **Primary (C-arm, reward split, descriptive at pilot n).** 20 pairs aggregated, **19
  decided**, 1 undecided; **15 correct, accuracy 0.7894736842105263**; the arm's
  `largest_true_effect` (|accuracy − 0.5|) **0.2894736842105263**; pair-bootstrap lower bound
  **0.5789473684210527**. `verdict` read `insufficient_n` (19 < 200), which is the registered
  precedence, not a pass.
- **Positional.** 381 decided votes, rate 0.4645669291338583, deviation **0.0354** — far under
  the void line; within-order rates 0.6270270270270271 (order 0, n=185) and 0.3112244897959184
  (order 1, n=196), i.e. the counterbalancing worked as designed.
- **Shuffle (C3).** 4 clears in 200 draws, clear-share **0.02**, under the 0.075 limit.
- **Damage (C2).** 15 outcomes, 11 intact preferred, bootstrap lower bound
  **0.4666666666666667** — at or under 0.5, so the damage arm did not pass at pilot size.
- **Sham (C1).** 12 shams, 236 votes returned, **102 decided** (a 57% "neither" rate, which
  same-book window pairs invite). Per-sham decided n and deviation, sorted by n:

  | n_decided | 2 | 5 | 5 | 6 | 7 | 8 | 9 | 9 | 12 | 12 | 13 | 14 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | deviation | **0.5** | 0.3 | 0.3 | 0.1667 | 0.0714 | 0.0 | **0.3889** | 0.0556 | 0.0 | 0.1667 | 0.2692 | 0.2143 |

  The floor is the max, never pooled (§7's K2 form): **0.5**, set by `sham-103284` on **two**
  decided votes (continue-share 1.0). 0.5 ≥ 0.2894736842105263, so `void_sham` fired in the
  pilot gate. The next-largest deviation is 0.3888888888888888 (`sham-103788`, n=9).

Two design corners, not two verdicts, follow from those numbers, and §A.2 and §A.3 amend one
each.

### A.2 Mechanical argument 1 — a statistic with two attainable values is not a deviation

The per-sham statistic is d = |k/n − 1/2| over n decided votes, so its attainable set is
{ j/(2n) : j ≡ n (mod 2), 0 ≤ j ≤ n }: **lattice spacing 1/n, maximum 0.5 at unanimity**.

- At **n = 2** the attainable set is exactly **{0, 0.5}** and nothing between. Such a cell
  reports whether the panel split, not by how much: it measures resolution, not deviation, and
  the floor it sets is the statistic's ceiling by construction. That is what set the pilot's
  0.5 floor.
- Bare non-degeneracy — some value strictly inside (0, 0.5) must exist — needs only **n ≥ 3**
  ({1/6, 1/2}). Too weak to be the rule: it still admits cells whose only alternatives are
  "0.167 or unanimous".
- Under the sham's **own null** — two windows of one book, so the true continue-share is 0.5 —
  the maximum is reached by chance with probability 2·2⁻ⁿ = 2^(1−n). Requiring that at or under
  the programme's registered ALPHA of 0.05:

      2^(1−n) ≤ 0.05  ⟺  n − 1 ≥ log₂20 = 4.3219  ⟺  n ≥ 5.3219  ⟺  n ≥ 6
      n = 2: 0.5      n = 3: 0.25     n = 4: 0.125
      n = 5: 0.0625 (> 0.05, refused)  n = 6: 0.03125 (≤ 0.05, admitted)

  **The amended minimum is n_decided ≥ 6** (`analysis.SHAM_MIN_DECIDED`), and this is the
  criterion that fixes it.
- The strictest available criterion was computed and **refused for a mechanical reason, before
  looking at what it would do to the verdict**: requiring the lattice spacing to be no coarser
  than §7's registered +0.05 margin means 1/n ≤ 0.05, i.e. n ≥ 20 — the entire per-sham vote
  budget (10 personas × 2 orders) with not one "neither" answer. The pilot measured 2-14 decided
  of 20, so that rule empties the control at every attainable size, and a control that cannot
  fire is the §120.2 defect the sham arm exists to prevent.

What the guard is: a refusal to let a cell that cannot express an intermediate value set a
maximum. What it is **not**: a repair of the max-not-pooled estimator. Under the null,
E|d| = 0.1562 at n = 6 and 0.1128 at n = 12, and the floor is a maximum over twelve such
draws; that noise is a property of the registered estimator and this amendment does not touch
it. §A.4(2) prices the consequence.

Implementation: `analysis.sham_floor(votes_by_sham, *, min_decided=0)`. **The default is the
registered rule** — no minimum, the pilot's floor recomputes bit for bit from its own votes —
and the amended floor exists only when a caller passes `SHAM_MIN_DECIDED` and says so. A sham
below the minimum keeps its measured deviation in the record with `counts_toward_floor: False`;
nothing is deleted. If the minimum leaves **no** qualifying sham, the amended verdict is
`void_sham_unmeasured`, not a pass: a floor of 0.0 must not mean "nobody was allowed to speak".

**Observed while drafting, and deliberately not amended:** §7 registers both a +0.05 clearance
requirement and a void condition, but `analysis.verdicts` implements only the void half
(`sham floor ≥ largest_true_effect`). The gap is recorded here as an observation about the
implementation; closing it would be a second amendment nobody ordered, and it would tighten the
rule after seeing the data as surely as loosening it would. The +0.05 is cited above only as
evidence of the granularity the registration itself declared.

### A.3 Mechanical argument 2 — controls must be sampled at the stage they certify

`elicit._call` keys its replay cache as `f"{digest(params)}:{sample}"`, and
`arms._sample_index` folds (pair_id, persona_id, order) into that `sample`. Control cells carry
stage-independent ids (`sham-<fiction>`, `damage-<fiction>`, `surface-<fa>-<fb>`) built from the
first clean books of the stage's pair list, and the control arms are fixed-size
(`SHAM_BOOKS = 12`, `DAMAGE_BOOKS = 15`, `SURFACE_PAIRS = 15`). Stage (c) would therefore
present byte-identical requests under identical keys and **replay the pilot's control answers**:
the sham floor of 0.5 and the damage lower bound of 0.4666666666666667 would be predetermined
before the full run began. **A control whose outcome is decided in advance certifies nothing** —
it is a constant wearing a control's name.

The amendment adds a stage salt to the sample index for the control arms only:

    arms._sample_index(spec, stage_salt)   # payload + "\x00stage:<salt>" when salt is non-empty
    backtest.STAGE_SALT = {"dry": "", "pilot": "", "full": "full"}
    backtest.CONTROL_ARMS = ("sham", "damage", "surface")
    backtest.control_stage_salt(stage, arm) -> the salt this arm carries at this stage

Properties, each of them the reason for a line above:

- **The salt changes the cache key and nothing else.** Same stimulus, same system prompt, same
  schema, same parse; only the key differs, so the cell is re-asked instead of replayed. It
  reaches no other part of the pipeline.
- **The empty salt appends nothing** — not a delimiter, not a marker — so every unsalted index
  is the same integer it was before the amendment. Stage (b) keeps the empty salt so the
  pilot's committed numbers keep replaying free, which is the RUNBOOK's standing guarantee.
- **The primary C and P arms are not salted.** Their pilot pairs are registered members of the
  confirmatory pool, drawn from the same `undeclared_2025` list in the same order, so replaying
  them is the registered design rather than a shortcut. See the disclosure in §A.4(4).
- **The recognition probes are not salted, and the reason is what a probe is.** The probe is an
  exclusion filter on a book, not a control whose value is compared against the primary effect;
  it decides membership before any arm runs and nothing in §9 reads it as a quantity. Re-drawing
  it would re-open, at cost, an exclusion that a call which did land has already made, and would
  add draw variance to the screen carrying the whole memorisation defense. The ~180 pairs new at
  stage (c) bring new fiction ids and are probed with fresh calls regardless, because their
  request bytes differ; only the 40 pilot books replay their classification. A book classified
  `clean` by an answered probe stays classified by that answer.

### A.4 Honesty checks, all written before the full run

1. **The guard does not clear the pilot's sham void, and is not what would clear anything.**
   Applying `min_decided = 6` to the pilot's own per-sham table removes three cells (n = 2 at
   deviation 0.5, and both n = 5 cells at 0.3), leaving **9 of 12 shams qualifying** and an
   amended floor of **0.3888888888888888** (`sham-103788`, n = 9). That still exceeds the pilot
   primary effect of 0.2894736842105263, so **`void_sham` fires under the amended rule as well
   as the registered one on pilot data**. What makes the control a real measurement at stage (c)
   is §A.3's fresh draws, not this guard.
2. **The stage-(c) sham floor may void the arm anyway, and that possibility is priced here
   rather than after the fact.** Under the sham null, with the guard in force and twelve
   qualifying shams, the probability that the floor alone reaches the pilot's effect size
   (0.2894736842105263) is **0.9483 if every sham has n = 6**, **0.3763 at n = 12**, and
   **0.1330 at n = 20**. The pilot averaged 8.5 decided votes per sham (102 over 12). A
   `void_sham` at stage (c) is therefore a likely outcome of a max-over-twelve statistic at
   this decidedness, is not evidence against the primary, and will be reported as what it is.
3. **The amendment is structurally permissive on the sham corner, and that is stated rather
   than argued away.** Removing cells from a maximum can only lower the floor:
   `floor_amended ≤ floor_registered`, always, on any dataset. A reader should discount the
   amended sham verdict accordingly. Three things counterweigh it, none of which cancels it:
   `void_sham_unmeasured` fires if the guard empties the control; the stage salt makes the (c)
   floor a fresh draw that can land higher than the pilot's; and both verdicts are reported.
   Whether the salt makes any verdict likelier is unknown and unknowable before the draw —
   that is the point of a salt.
4. **Disclosure, stated rather than silent:** *The confirmatory aggregate at stage (c) includes
   the 20 pilot pairs' replayed votes as its first 10%: those cells are unsalted, so they are
   read from the pilot's cache rather than re-asked, and they entered the pool under the
   registered design and the same rules as every other pair.*
5. **Nothing here is evidence of anything.** This section is a registration change, not a
   result. The re-pilot's 15-of-19 remains descriptive at pilot n, `insufficient_n` remains the
   verdict on record for stage (b), and no claim moves state on the strength of this text
   (EPISTEMIC_GOVERNANCE: agent prose is not evidence).

### A.5 The dual-verdict rule

`backtest.run_paid` computes both rules over one set of votes, differing in exactly one input —
the sham record — and writes both:

- **`verdict_registered`** — §9's rule exactly as registered, `analysis.sham_floor` at its
  registered default of no minimum.
- **`verdict_amended`** — the same rule with the sham floor from `min_decided =
  SHAM_MIN_DECIDED`, plus the `void_sham_unmeasured` outcome that only the amended path can
  reach.
- **`amendment`** — date, the operator's words verbatim, the amended parameters, the salted
  arms, the disclosure sentence, and `section_sha256` over this section's bytes. The amendment
  commit's own hash cannot appear inside the commit that adds it, so the pointer is that
  commit's subject line, recorded as `AMENDMENT_COMMIT_SUBJECT`.

There is deliberately **no key named `verdict`** in an amended result file: a reader who wants
one has to say which rule they mean. Neither verdict replaces the other in the record, in
FINDINGS.md, or in any summary.

How to read a disagreement, fixed now so it cannot be chosen later: **qualification under the
registered rule is the registered claim.** A pass that exists only under the amended rule is a
post-hoc observation, is reported as "did not qualify under the registered rule; would have
under the amended one", and would need its own pre-registered re-test before it could mean
anything. A void under both is a void.

### A.6 What licenses stage (c) at all — named, not assumed

§8 stages the programme so that (b) "proceeds to (c) only if no VOID fired". At the re-pilot
`void_sham` fired, and §A.4(1) says it fires under the amended rule too. **Stage (c) therefore
does not run because the pilot's gate cleared.** It runs on the operator's directive quoted at
the head of this section, and it runs on the one argument that can change the corner: the
pilot's sham floor was set by a cell that could not express an intermediate value (§A.2) and
its control answers were frozen in a cache that stage (c) would have replayed (§A.3), so the
pilot's control arms are not a measurement stage (c) can inherit. What stage (c) inherits is
the plumbing; its control verdicts will be computed from its own fresh draws.

The cost of that, stated: the registered staging discipline is one step weaker than it reads
above, and this is the sentence that says so instead of leaving it to be reconstructed. Two
things it does not license. Stage (c)'s own sham floor, drawn fresh, is not pre-cleared by
anything here — if it voids the arm, the arm is VOID and the programme reports a void. And no
third rule is available: the two in §A.5 are the two, fixed before the run.

### A.7 What this amendment does not change (anti-scope)

The primary metric, the pair bootstrap and its seed policy, ALPHA, the 200-decided-pair target
and its INSUFFICIENT_N verdict, §7's +0.05 clearance text, the positional and shuffle void
lines, the damage pass condition, the frozen personas and the reward/holdout split, the pair
set, the blinding, the probe rule and its `unprobed` class, the cost ceiling, and the control
arms' sizes (`SHAM_BOOKS`, `DAMAGE_BOOKS`, `SURFACE_PAIRS`) all stand as registered. The
re-pilot entry in FINDINGS.md floated a third option — larger control arms — and it is
**refused here**: neither corner requires it, it would re-price the stage the pilot's ledger
was meant to size, and enlarging an arm after seeing its number is the kind of change this
section exists to make impossible to do quietly.
