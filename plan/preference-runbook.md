# Preference-engine runbook: the first month

The pairwise preference engine (stage-0 §69) is the project's evidence source: blinded,
position-swapped pairwise judgments from paid genre readers, content-addressed in the
store. This runbook is the operating procedure for its first month, whose acceptance
criterion §61 fixed in advance: **the pipeline funds a calibration row promotable under
§59's bound within one month of operation, or that failure lands in the ledger like
every other dead instrument.** Nothing here is code; every step is an operator act.

## 0. Pre-register before paying anyone

Declare the external-comparison protocol first — `litharness protocol` — and treat the
declaration as unchangeable (redeclaration collides by construction):

- **Comparator frame** — written sentence naming the sampling frame of the human prose
  ("mid-list tier-matched RoyalRoad LitRPG, 2021–22 cohort, 300+ followers", or
  whatever is actually claimed). §1a.5: beating the median and beating the best are
  different claims, and **the frame is the claim**. The win-rate headline means nothing
  beyond this sentence.
- **Tie policy** (`half_win` or `drop`) and **grain** (scene; chapter is a recorded
  TODO — production books hold no chapter nodes).

## 1. Build the comparator corpus

`litharness corpus-add` per excerpt, with source/genre/era/words recorded — these are
the matching covariates craft-corpus's standing demand requires. Match premise and
length to the system scenes being judged. Prefer matched-obscurity where the frame
allows: the recognition screen (below) excludes recognized judgments, but every
exclusion is paid-for judgment thrown away, and the genre's most-read serials will be
recognized often (§58's familiarity lesson wears a human face here).

## 2. Draw and export

`litharness pair-draw` over accepted scenes × corpus (system-vs-system sibling draws
are minted by tournaments automatically). The draw is deterministic and
position-swapped by construction — both orientations of every pair are sibling rows,
so positional consistency is measurable per reader (RevisionBench measured 43–65%
positional artifacts in model judges; humans get checked, not trusted).
`litharness pair-export` produces the JSONL packet for readers.

## 3. Readers

- Paid, external, genre-familiar (screen: names two LitRPG titles they finished).
- Stable pseudonymous reader ids — the id is a clustering dimension in the CI;
  recycling ids across people corrupts the interval.
- Every judgment answers the **recognition question** ("do you recognize either
  passage?") — recorded, and recognized judgments are excluded from the win rate, never
  silently dropped from the record.
- Attention checks: seed a small share of pairs with an obvious-defect variant; a
  reader who prefers planted defects is excluded (their rows stay; exclusion is
  analysis-side and recorded).
- **Panel discipline (§61):** readers who select tournament winners (Add 3) are
  disjoint from readers who render the headline verdict — selection optimizes toward
  its panel's taste, and a verdict from the same panel is in-sample.

## 4. Import and read the evidence

`litharness pair-import`, then `litharness win-rate --protocol <id>`: decisive / tie /
excluded-by-recognition counts, observed rate, and the reader×pair clustered lower
bound (refused below two clusters on either dimension — one observation wearing an
interval, §59). Sizing honesty from §61: at a true rate of 0.60, roughly 100–150
decisive judgments clear the bound; at 0.55, 400–500; clustering inflates both. If
more than one book could be reported, divide alpha by the candidate count before
calling anything superhuman (§6.4 applies to the headline claim).

## 5. What the month must produce

A `litharness calibrate` row of evidence class PREFERENCE (or JUDGMENT via the audit
queue's smoke check) that `litharness calibrations` reports as sound under §59's
bound — counts stored, family declared, clusters ≥ 2, digest current. If the month
ends without one, write the entry: what throughput the money actually bought, and what
that refutes.
