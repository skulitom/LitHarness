# The progression-cadence census: how often the market moves a number, how early, and how evenly

**Status: MEASUREMENT, 2026-08-29. No bar is declared here, nothing is admitted to any
registry, no directive was authored, and nothing this census measured reaches a prompt.** The
distribution is the deliverable. Any admission is the operator's.

Every number is reproducible from
[`results/progression-cadence.json`](results/progression-cadence.json), which carries ids and
numbers only, under registration digest **`5d42f2065efb7e09`**.
`progression_cadence.py --selftest` fails if the frozen block moves.

**Events per 1,000 words is a density of located furniture and phrasing, not of pleasure.** A
chapter with more of them is not better. Whether any of them lands is not asked, not schema'd,
and not derivable from anything here.

## The headline, stated first because it is not the expected one

**The median LitRPG chapter carries zero located progression events. 51% of them carry none at
all. Among chapters that carry two or more, the gap between events has a coefficient of
variation of 0.96 — essentially Poisson.**

The operator's word for what they want is *constant and regular*. The market they read is
neither: progression arrives in bursts a median of 89 words apart, separated by long dry
stretches, and half of all chapters are dry end to end.

**So the cadence work downstream of this census is a deliberate departure from the market, and
is not dressed up as imitation.** What the census supplies is not a target to copy. It is the
place the market actually sits, so that a departure from it is a choice with a number beside it
instead of an adjective.

The one place the census *does* support the operator directly is the opening:

**Only 22.5% of market LitRPG chapters place a progression event inside their first 500 words,
and the median chapter's first one lands at word 585.** The complaint — *"I don't want to read
to the end of chapter 1 to see interesting progress"* — is one the market earns three times out
of four.

## 1. The validity arm, before any distribution is read

A code-only counter's characteristic failure is locating *typography* rather than events, and
nothing in the instrument itself can tell the difference. The scan was widened past the LitRPG
tag for a sibling track's frequency base, and that widening supplied the control this census
could not otherwise have had: **chapters the market did not tag `LitRPG` are a population these
counters must score well below.**

| | LitRPG | not LitRPG | separation |
|---|--:|--:|--:|
| chapters | 13,364 | 51,567 | |
| distinct fictions | 584 | 3,096 | |
| mean events / 1k | 1.224 | 0.188 | **6.50x** |
| share with ≥1 event | 49.0% | 12.8% | **3.84x** |

**Coverage is the number to believe.** It is a share, so no outlier chapter can move it. The
counters are locating something genre-specific rather than ordinary narration.

**The median ratio is deliberately not reported as the statistic.** The control's median density
is 0.0, so a ratio over it is undefined and would read as a triumph.

### 1.1 A correction the validity arm made to this instrument before it made any to the market

The first run put `system_block` at **83% of the not-LitRPG control's located events**, which is
not credible for a population that mostly has no system. The cause was mechanical: the frame
pattern was matching `***` and `---` **scene dividers**, which every fiction on the platform
uses. A run of rule characters with no furniture line in it is now a divider and not an event,
and a line inside a drawn box is classified on its contents so a boxed sheet is not lost to its
own box.

**This is recorded rather than quietly fixed, because a fix made after seeing a number has the
shape of fitting a rubric to its own answers.** It is not that one, and the argument does not
depend on the number: a scene divider is not a progression event whatever any count says, the
rule was stated before the re-run rather than tuned against it, and its declared direction was
to *lower* both populations rather than to flatter either. Measured after: both populations fell
and the separation rose from roughly 3.8x to 6.50x, which is the direction a real fix moves a
control. The digest rotated `b2901ac0ea90ff56` → `5d42f2065efb7e09`, and nothing had been
published under the first.

## 2. The distribution

`corpus_io`-pinned snapshot `0e4df3f2`, both cached shards, min 300 words, **no genre filter and
no per-story sampling** — 67,436 chapters materialised once and measured. The 26 descriptor-half
fiction ids from `voice-descriptors.json` are carried as a `quarantined` column and **subtracted
from every ours-vs-market population** (2,505 rows); they are reported separately and never
pooled.

### Density, events per 1,000 words

| population | n | mean | p50 | p75 | p90 | p95 | max |
|---|--:|--:|--:|--:|--:|--:|--:|
| LitRPG | 13,364 | 1.224 | **0.00** | 1.26 | 3.60 | 5.53 | 67.9 |
| not LitRPG | 51,567 | 0.188 | 0.00 | 0.00 | 0.40 | 0.95 | 30.7 |
| `human_pre_llm` | 5,561 | 1.398 | **0.32** | 1.43 | 3.74 | 5.77 | — |
| `undeclared_2025` | 5,803 | 1.084 | 0.00 | 1.09 | 3.36 | 5.50 | — |
| `declared_ai_2025` | 941 | — | 0.00 | — | — | — | — |
| descriptor half (quarantined) | 2,505 | — | 0.28 | — | — | — | — |

In absolute events the median LitRPG chapter has **0**, p75 is 3, p90 is 7, and the maximum is
62. The median chapter is 2,053 words.

**The cohort ordering is era and is not read as an AI tell**, for the reason the comic-beat
census gives at length: that is exactly the confound that killed `tricolon_rate`. No claim about
authorship is made here and none is available.

### Coverage: the stoic-wing question, and the answer is the opposite of levity's

| | share with ≥1 | share with none |
|---|--:|--:|
| LitRPG | 49.0% | **51.0%** |
| not LitRPG | 12.8% | 87.2% |

The comic-beat census found levity near-universal — only 3 of 236 chapters returned zero — and
concluded the genre has no stoic wing. **Located progression is the opposite shape.** Half the
genre's chapters carry none, which is the single most consequential line here for anyone
deciding what a per-scene schedule should look like.

### Earliness

| | LitRPG | not LitRPG |
|---|--:|--:|
| an event inside the first 500 words | **22.5%** | 5.5% |
| an event inside the first 1,000 words | 33.2% | 8.3% |
| first event, median word offset | 585 | 641 |
| first event as a fraction of the chapter, p25 / p50 / p75 | 0.10 / 0.29 / 0.56 | — |

### Regularity

Among LitRPG chapters carrying two or more events (n=4,496):

| | p25 | p50 | p75 |
|---|--:|--:|--:|
| median gap between consecutive events, words | 31 | **89** | 276 |
| coefficient of variation of the gaps | — | **0.96** | — |

**A CV near 1 is the signature of a memoryless process.** Events cluster inside a scene-sized
span and then do not recur for a long stretch. Nothing in this market is pacing them.

### The length residual, and there isn't one

Spearman(density, chapter words) = **0.003** on LitRPG, 0.096 on the control. Unlike the
comic-beat census — where longer chapters yielded fewer located beats per 1,000 words at
ρ=−0.18, and a pooled percentile therefore understated our own long chapters — this instrument
shows no length dependence worth controlling for on the genre population.

## 3. What the instrument is, mechanically

Deterministic counters over normalised text; **no model call, no transport, no cost, and no
sampling variance.** Reliability is 1.0 by construction: the same chapter always returns the
same count. That is the exact inverse of the comic locator's error profile (reliability 0.537,
precision verified by a findability check) and the trade must be read in both directions —
see §4.

Two unit rules do the work of not double-counting:

- **A furniture run is one event**, however many lines it holds, surviving at most one blank
  line. A status sheet is one notification, not twenty. A run with no furniture line in it is a
  scene divider and no event.
- **Outside runs, at most one event per sentence**, family assigned by priority. Sentence rather
  than line, because a prose-mode chapter writes long paragraphs and a per-line rule would
  under-count it against a furniture-mode chapter — the typography bias this instrument most
  needs to avoid.

Four families, priority-ordered: `system_block` (interface lines the character reads),
`level_up`, `capability_gain`, `stat_delta`. Author notes, navigation and front matter are
rejected by an explicit exclusion list.

| family share | LitRPG | not LitRPG |
|---|--:|--:|
| `system_block` | 58.6% | 64.7% |
| `stat_delta` | 16.9% | 5.8% |
| `level_up` | 14.1% | 12.5% |
| `capability_gain` | 10.5% | 17.0% |

## 4. Known residuals, unfixed and named

- **PRECISION IS UNMEASURED, and this is the top residual.** Nothing here checks that a located
  span is a progression event. The comic-beat census could make that check because a model
  returned an anchor and the anchor was matched against the page; a regex has no anchor to
  verify against anything. The cheapest fix is a model-audited subsample of located spans, it
  is a paid registered arm, and it was not run.
- **RECALL IS UNMEASURED, and the headline depends on it.** *"51% of LitRPG chapters carry no
  located event"* is a joint claim about the market and about this instrument's recall:
  progression carried purely by implication, with no furniture and no phrase from the lexicons,
  scores zero and is indistinguishable here from a chapter where nothing happened. **That
  caveat travels with the figure wherever it is quoted.**
- **The counters are a prior, not a trained classifier.** They were written from the genre's
  conventions rather than fitted to a sample — but they were never held out from one either.
- **Reliability 1.0 is not a virtue, it is a different failure mode.** A deterministic
  instrument repeats its own mistakes perfectly. The comic locator's noise at least made its
  unreliability visible; nothing here will ever disagree with itself, whatever it is wrong
  about.
- **The `system_block` family is 59% of located LitRPG events**, so the headline is carried
  disproportionately by one family — the one most exposed to the typography hazard, and the one
  the divider correction had to be made in.
- **Chapter text is whatever the shard holds**, including front matter the exclusion list
  misses.
- **One chapter per story was not enforced.** Every chapter of every story is measured, so
  prolific fictions weigh more than short ones in the pooled rows. Distinct-fiction counts are
  reported beside every n so the reader can see the ratio (13,364 chapters over 584 LitRPG
  fictions). The comic-beat census drew one chapter per story and this one deliberately did
  not, because the sibling track reading the same intermediate needed the full base.

## 5. What was deliberately not built

- **No bar, and no target cadence.** Declaring one needs the four attainability checks (§81,
  §85, §87, §89) and none was run. Distributions before bars.
- **No landing measurement.** Whether a progression event lands is valence, and valence is
  behavioural or it is nothing (§97.4).
- **No ours-vs-market placement.** Our own chapters are not scored here. The instrument's
  precision is unmeasured on the market population it was written for, and placing our prose in
  a distribution whose units are unvalidated would give a percentile the weight of a finding.
- **Nothing reaches a prompt.** No axis, no `COUNTERS` entry, no directive kind, no persona
  reason code, no writer dossier. The schedule this census informs is a plan item composed in
  code (`domain/genre.py`), and the census's numbers live in that module's commentary as the
  reason for a placement — never as text sent to a model.
