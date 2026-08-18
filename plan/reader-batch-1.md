# Reader batch 1: one set of paid verdicts, two jobs

**Status: designed, costed, and NOT funded.** Funding starts §59's one-month kill switch and is an
operator act. Nothing in this document authorises spending; it exists so that when the money is
committed, the batch that gets bought is the one that answers two questions instead of one.

The two jobs:

1. **Pilot the headline protocol.** The §1a.4/§1a.5 claim is a blinded, position-swapped pairwise
   win rate against matched published human prose, lower bound of a 95% CI above 0.5. This batch is
   the first real exercise of [preference-runbook.md](preference-runbook.md) and all five §61
   pre-registrations.
2. **Anchor the machine panel.** Every axis where the machine panel has a recorded verdict gets the
   same pairs put to humans, so the batch yields a **panel-vs-human agreement matrix per axis**
   rather than a single win rate. This is what the taste-gap programme has been unable to buy: §78
   withdrew the one axis the panel appeared decided on, and §77.1 withdrew the one external-label
   result, so the panel's relationship to human taste is currently *unmeasured* rather than known.

## 1. The composition, and the one adjacency that would ruin it

| class | pairs | both sides | what it buys |
| --- | --- | --- | --- |
| A. headline | 110 | ours vs matched human | the §1a.4 win rate, and simultaneously the human reading of the panel's `ours_vs_mol` 0.9844 |
| B. defect-manufacture | 75 | ours vs ours | per-axis panel-vs-human agreement on the three reader-named defects |
| C. attention checks | 16 | ours vs grossly-spoiled ours | reader validity, analysis-side exclusion |
| D. sham | 8 | ours vs layout-only ours | the human tie rate on a null; the panel declines these 79% of the time |

**Classes B and C must never be the same instrument, and this is the design's single most important
constraint.** Both look like "does the reader notice damage". The runbook says a reader who prefers
planted defects is excluded. If the planted defects were the *reader-named* defects — the interiority
strip, the flattened stats — then excluding readers who fail to detect them would **manufacture
agreement with the human reader on precisely the axis the batch exists to measure.** The batch would
report that humans detect interiority loss because every reader who did not was thrown out.

So:

- **Class C uses gross, uncontroversial damage** where any attentive reader of any taste agrees:
  `sentence_deletion` at full dose and `connective_scramble` at full dose. Failing these is evidence
  about the reader.
- **Class B uses the subtle reader-named defects** where the correct answer is unknown and is the
  measurement: `interiority_strip` vs `interiority_deplete_matched`, `stat_flatten` vs original,
  `em_dash_strip` vs original. Failing these is evidence about the defect, never about the reader.
- No reader is ever excluded on a class-B judgment. Stated in the analysis plan before the first
  payment, because it is the kind of rule that gets quietly relaxed when the numbers are thin.

## 2. Class B is built on the arms whose panel verdicts are recorded

One row per axis, each carrying the machine number the human verdict will be read against. The
panel's column is filled in from the committed artifacts, **not** from memory:

| axis | pairs | panel verdict | where |
| --- | --- | --- | --- |
| em dash (comma-strip vs original) | 25 | 0.3641, **VOID on positional bias 0.6032**, interval [0.2273, 0.5139] | §78.3, `results/reader-repair-fixed.json` |
| interiority (strip vs word-matched control) | 25 | see `results/reader-defects.json` | §81 |
| stats (flatten vs original) | 25 | see `results/reader-defects.json` | §81 |

**The em-dash row is the one to read first and the reason is §78.** The panel's original 0.0417 was a
paragraph-flattening artifact; the corrected arm is void on its own precondition and its interval
contains 0.5. So on the one defect a human actually named and the instrument was supposed to have an
opinion about, **the machine column is empty.** A human column would therefore not be "agreement" —
it would be the first measurement of that axis by anything. That is worth buying on its own.

Class B pairs are drawn from the same ten drafted scenes of `The Toll Road` the panel judged, using
the same transforms at the same dose, so the human and machine columns are the same comparison and
not two comparisons about the same topic.

## 3. Class A, and the frame is the claim

§61 pre-registration (4): the comparator sampling frame is declared before the first reader is paid,
because beating the median and beating the best are different claims.

**Declared frame for this batch:** *pre-LLM (pre-2023) RoyalRoad LitRPG chapters, one chapter per
story, 10,000+ total views, 1,500–6,000 words, excerpted to ~1,000 words paragraph-aligned.* That is
deliberately the same frame [taste_benchmark.py](../research/quality-measurement/taste_benchmark.py)
builds, for two reasons: the covariates are already recorded per pair in
`results/taste-benchmark-corpus.json`, and it is a **mid-list** frame, so the claim it can support is
"beats mid-list tier-matched human LitRPG" and nothing grander. 107 stories clear that frame in the
two cached shards.

**Recognition is expected, not exceptional** (§61 pre-registration 3). This frame helps: mid-list
pre-LLM RoyalRoad is obscure, so recognition exclusions should be rarer than they would be against
*Mother of Learning*. MoL is therefore **excluded from class A** — it is the panel's most confident
arm (0.9844) but it is famous, and paying readers to render judgments that get excluded for
recognition is the most expensive way to learn nothing. The panel-vs-human comparison on the MoL arm
is deferred, and §77.1 already records why that arm cannot carry a claim.

## 4. Sizing, and what it can and cannot detect

§61's sizing, unchanged: at a true win rate of 0.60, roughly 100–150 decisive judgments clear the
bound; at 0.55, 400–500; clustering over readers and items inflates both.

    class A   110 pairs x 2 orientations                    = 220 raw judgments
    class B    75 pairs x 2 orientations                    = 150 raw judgments
    class C    16 pairs x 2 orientations                    =  32 raw judgments
    class D     8 pairs x 2 orientations                    =  16 raw judgments
                                                              ---
                                                              418 raw judgments

Expected attrition on class A: ties at the rate the machine panel shows on shams (high) and
recognition exclusions at an unknown rate — **assume 20% and record the actual, since this batch's
real job is to measure that rate for every batch after it.** 220 raw judgments minus 20% leaves
~176, which is comfortably inside the 100–150 band for a true rate of 0.60 and nowhere near the
400–500 needed for 0.55.

**So the honest statement of what this batch can do: it can certify a win rate at or above 0.60 and
it cannot certify 0.55.** If the true rate is a thin margin, this batch produces a lower bound below
0.5 and the correct conclusion is "not shown", not "nearly shown". §61's sizing paragraph exists
because pretending otherwise is how the bar gets quietly weakened, and this sentence is here so the
outcome cannot be renegotiated after the interval is computed.

**Readers:** 10, each taking ~42 judgments. Clustering needs ≥2 clusters on both dimensions (§59);
10 readers × 209 items gives room for the clustered lower bound to be computed at all, which a
single-reader batch would not. Stable pseudonymous ids, never recycled.

**Panel discipline (§61):** no reader in this batch may later serve on a tournament-selection panel
whose winners are reported against a verdict from this batch, and vice versa. This batch renders a
**verdict**, so its readers are verdict readers and are recorded as such.

**Cost:** 418 judgments, each a read of two ~1,000-word passages plus three questions
(preference, recognition, confidence). Per-judgment price and platform are operator inputs; at any
plausible rate this is a four-figure commitment, and it starts the §59 clock on the day it is paid.

## 5. The deliverable: an agreement matrix, not a number

    axis                    panel        human (LB, UB)   agree?   licenses
    headline win rate       0.9844       ?                 -        the §1a.4 claim, at frame above
    em dash                 VOID         ?                 -        first measurement of the axis
    interiority             §81          ?                 -        optimisable axis, or mapped hole
    stats                   §81          ?                 -        optimisable axis, or mapped hole
    sham (layout only)      0.4375*      ?                 -        whether humans also decline

    * void on bias; recorded for shape, not as a number (§74 Addendum 1, §78)

**Pre-registered readings, per axis, before any reader is paid:**

- **Panel and humans both detect a defect** → that axis is licensed for optimisation, and it is the
  first axis in this project ever licensed by external agreement rather than by our own vocabulary.
- **Humans detect and the panel does not** → confirmed mapped hole. The §72 judge is prohibited from
  selecting on that axis, and the prohibition now has a measurement behind it rather than an
  argument.
- **Panel detects and humans do not** → the panel is reading something humans do not care about. The
  axis is not a quality axis and anything already optimised toward it is suspect.
- **Neither detects** → the defect is real (a named human found it in one read) and no instrument
  reaches it. This is the outcome that most changes the programme, because it means the gap is not
  in the panel's calibration but in the whole pairwise-preference frame.
- **Humans prefer our prose at a lower bound above 0.5 on the declared frame** → the headline claim
  advances, for mid-list tier-matched LitRPG, and for nothing wider.
- **Humans do not reproduce the panel's 0.98-scale preference for our prose** → the panel's headline
  is machine taste, and the size of the disagreement is the first number the taste-gap programme
  has actually had.

## 6. What must be true before this is funded

- [ ] §81 lands, so the interiority and stats rows have machine numbers to be read against.
- [ ] The em-dash axis either closes at higher n or is funded knowing its machine column is empty.
- [ ] `litharness protocol` declares the frame in §3 verbatim, and the tie policy, before draw.
- [ ] Class B and class C transform lists are fixed in the protocol declaration, so the
      no-exclusion-on-class-B rule cannot be revisited once the numbers are in.
- [ ] The operator accepts that the §59 month starts on payment.
