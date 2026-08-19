# Reader batch 1: one set of paid verdicts, ~~two jobs~~ **three jobs**

**Status: designed, costed, and NOT funded.** Funding starts §59's one-month kill switch and is an
operator act. Nothing in this document authorises spending; it exists so that when the money is
committed, the batch that gets bought is the one that answers ~~two questions~~ **three questions**
instead of one. **The third job and the re-costing are in [§7](#7-addendum-the-third-job-and-what-it-changes-above),
appended 2026-08-19 under stage-0 §89; everything above it is the original design and is left
standing so the change is visible rather than merged away.**

~~The two jobs:~~ **Two jobs as originally designed; a third was added in [§7](#7-addendum-the-third-job-and-what-it-changes-above) and job 2 was widened there from the panel to the composite. The original wording stands below.**

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

## 7. Addendum: the third job, and what it changes above

*Appended 2026-08-19 under stage-0 §89. Everything in §1–§6 is the original design and stands; this
section adds one job, one class-B axis, one new class, and a re-costing. Where it supersedes a
number above, it says so and the old number stays visible.*

**Why a third job exists at all.** §87 set out to show that a model's internals perceive more than
its verdicts report, and the finding was sharper and more awkward than that: on every fixture family
this project owns, **a deterministic counter beats the internals**, and the panel is blind to a
defect one line of arithmetic orders perfectly. Track P closed on redundancy rather than on failure.
The lesson §87 named is the one this addendum acts on — *"the ceiling on this fixture set is not
adapter-shaped or pretraining-shaped but fixture-shaped, and the successor experiment is a harder
fixture, not a bigger model."* A harder fixture cannot be manufactured by us, because every fixture
we manufacture comes with a counter we could have named. **Only a human can certify that a pair
differs in a way no counter reaches.** That is job three, and this batch is the only instrument that
can buy it.

The three jobs, restated:

1. **Pilot the headline protocol.** Unchanged from above.
2. ~~**Anchor the machine panel.**~~ **Anchor the composite instrument, per axis and per layer.**
   The object being anchored changed under §89's Track A2′: what will ship is not a panel but a
   three-layer composite — deterministic counters, then a frozen readout, then a verdict layer —
   and an agreement matrix against "the panel" would now anchor a component rather than the
   instrument. Every axis therefore gets **three machine columns**, so a disagreement is
   attributable to a layer instead of to the whole.
3. **Certify the fixture frontier.** Pairs that humans discriminate and no counter can. Class E
   below.

### 7.1 Class B gains a fourth axis: told-versus-shown

§85's interiority repair is the one arm three separate judge families agree on — 0.9509 at Haiku,
1.0000 at Sonnet, 0.9688 at `phi4` outside the generator's family (§85, §85.1, §87.3). §87.1 then
measured **what the treatment actually put there**: told inner state up 1.608 per 1k words and
demonstrated bodily state *down* 0.627, rising in seven of eight scenes against one of eight. The
machines like it, and the thing they like is told-not-shown.

**Craft doctrine says told feeling is worse. That is a hypothesis, not a finding, and this is the
row that tests it.** §87.1 first read the Haiku-to-Sonnet gradient as evidence that the preference
was family match; §87.3 struck that reading, because a cross-family judge preferred the same repair
just as hard. So the machine column is now three-way consistent and craft doctrine is the only thing
standing against it — and craft doctrine has never been measured on a reader in this project.

| axis | pairs | machine column | where |
| --- | --- | --- | --- |
| told-vs-shown (interiority repair vs original) | 25 | 0.9509 / 1.0000 / 0.9688, bias 0.500 at Sonnet | §85, §85.1, §87.3 |

Pre-registered readings, before any reader is paid:

- **Humans prefer the repair** → told-not-shown is not a defect at this dose on this material, three
  judge families are right, and a piece of craft doctrine this project has been treating as a
  constraint is retired *with a measurement behind the retirement*.
- **Humans prefer the original** → the machine panel's single most confident arm is machine taste,
  measured against the axis §87.1 identified, and the size of the gap is the first calibration
  number the taste-gap programme has.
- **Humans tie** → the treatment is invisible to readers and the panel's 0.95–1.00 is reading
  something below the threshold of the thing the batch exists to serve.

**Read against the §85 operator read when it lands, and marked provisional until then.** The
operator's six-pair read is PENDING as of 2026-08-19 (`results/operator-read-key.json`, which no
agent opens). Every told-versus-shown conclusion in this project is therefore currently provisional,
this row included, and the addendum says so rather than letting the qualifier lapse.

### 7.2 Class E: the fixture frontier, which only humans can certify

**What it is.** Pairs where **no a-priori counter is nameable** and no readout has separated them —
the material §87 recorded as *"the only families where surface and internals are both undecided, and
they are the ones superhuman selection would live in."*

| pairs | both sides | recorded machine status |
| --- | --- | --- |
| 8 | drunk-state narration vs sober | probe 7/8, p 0.180; P0 2/8 (**below chance**); panel VOID, bias 0.828 (§83, §87) |
| 8 | tripping-state narration vs sober | probe 7/8, p 0.188; P0 3/8; panel VOID, bias 0.762 (§83, §87) |
| 8 | exemplar-conditioned vs sober | no nameable counter; panel VOID at Haiku, 0.6484 at Sonnet (§85, §85.1) |

These are §83's four states in one voice: the same scene written by a narrator in a different
simulated phenomenology, which §83 found the register invariant to. They are the only pairs this
project holds that **every instrument it owns has failed on**, and they failed for the right reason
— the difference was not defined in terms of a quantity, so nobody could have named a counter for it
in advance. B6's membership rule (§88) rejects them by name for exactly that property, which is what
makes them the frontier rather than a leftover.

**Pre-registered readings:**

- **Humans discriminate them above chance** → the fixture frontier is certified. The next fixture
  generation is built on the property these pairs have, a benchmark exists that a digit counter
  cannot win, and §87's "harder fixture, not a bigger model" acquires a target. This is the outcome
  that most changes what gets built next.
- **Humans do not discriminate them** → §83's finding is confirmed on a reader rather than on an
  instrument: simulated phenomenology does not reach the page, the arms are closed, and no
  successor experiment should be funded on them. Also worth buying: it converts "perception-limited
  at 4B" into "not there to perceive".
- **Humans discriminate and cannot say why** → the most useful outcome for the composite, because it
  says the property is real and unnamed, and it is the only condition under which a *learned* layer
  earns its place over a counter.

**Class E is never an exclusion instrument.** Same rule as class B, and for the same reason with
more force: the correct answer is not merely unknown here, it is the measurement. A reader who
cannot separate a drunk narrator from a sober one may be reading correctly.

### 7.3 The re-costing, which supersedes §4's table

    class A   110 pairs x 2 orientations                    = 220 raw judgments
    class B   100 pairs x 2 orientations                    = 200 raw judgments   (was 75 / 150)
    class C    16 pairs x 2 orientations                    =  32 raw judgments
    class D     8 pairs x 2 orientations                    =  16 raw judgments
    class E    24 pairs x 2 orientations                    =  48 raw judgments   (new)
                                                              ---
                                                              516 raw judgments   (was 418)

**+98 judgments, +23%, and the headline claim's power is unchanged** — class A is untouched at 110
pairs, so §4's honest statement stands verbatim: this batch can certify a win rate at or above 0.60
and cannot certify 0.55. The added judgments buy per-axis anchoring and the frontier, neither of
which competes with the headline for statistical power because neither draws on class A's pairs.

**Readers:** 10 readers × ~52 judgments, up from ~42. That is the number to watch. §59's clustering
requirement is unaffected, but a 52-judgment session is long enough that fatigue becomes a real
threat to the last class read, so **class order is randomised per reader and recorded**, and class E
— the one whose null result is as informative as its positive one — must not be systematically last.

**Class E adds no new transform.** Its pairs already exist as committed fixtures from §83 and §85,
which is why the third job costs 48 judgments rather than a generation budget.

### 7.4 What must be true before this is funded, extending §6

- [ ] Panel v2 is **frozen** (§84), and the freeze is a ledger entry the operator has signed. §89's
      Track A2′ produces the candidate; the freeze is not automatic on it.
- [ ] §84 §6.2's pipeline-ready condition holds, unchanged.
- [ ] The composite's three machine columns are filled from committed artifacts before the protocol
      is declared, so §2's rule — *filled in from the committed artifacts, not from memory* — covers
      all three layers.
- [ ] Class E's pairs are fixed by digest in the protocol declaration. They are the one class whose
      membership could be quietly improved after a disappointing result, and that would convert the
      frontier from a measurement into a search.
- [ ] The §85 operator read is either recorded or its absence is declared in the protocol, so §7.1's
      row is not read as settled when it is provisional.
