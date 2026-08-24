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
(1) the persona-grain two-way clustered bound (`bound.py`'s twin, 10 readers,
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
whole programme: **$180** on the haiku panel — dominated by the C-arm's ~4,000 two-turn
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
rejected designs are §8's record. The persona-grain two-way clustered number (`bound.py`,
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
the pair-bootstrap primary interval, the descriptive `research/preference-power/bound.py`
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
