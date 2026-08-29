# The number-context census: what our exact quantities are attached to, and what the market's are

**Status: MEASUREMENT, 2026-08-29. No bar is declared here, nothing is admitted to any
registry, no directive was authored, and nothing this census measured reaches a prompt.** The
distributions are the deliverable. Any admission is the operator's.

Every number is reproducible from
[`results/number-context.json`](results/number-context.json), which carries ids and numbers
only, under registration digest **`8e10ac598828d404`**.
`number_context.py selftest` fails if the frozen block moves.

**A density of mundane-anchored numbers is a density of located SURFACES, not of harm.** A
chapter with more of them is not worse. The operator said one bothered them; that is a defect
harvest and not data (§95, §97.1), and this instrument converts it into a count and no further.

This is the MUNDANE side of the operator's sentence.
[`progression_cadence.py`](progression_cadence.py) is the neighbour and holds the SYSTEM side of
the same page — it asks how often a progression event happens, this asks where a number lands
when one is written.

## The headline, in one paragraph

**Our shelf writes 2.2 times as many numbers as the market's LitRPG and none of them are system
quantities.** Across 8 books, 20 chapters and 39,947 words there is exactly one
`system_magnitude` on the whole shelf and a hand-check says it is a false positive — a parking
structure's *three levels*. Meanwhile 55.5% of the market's LitRPG chapters carry at least one.
Of every anchored number our books write, **0.3%** is a system magnitude; in the market's
LitRPG it is **20.0%**. Our own mundane-precision density is **5.93 per 1,000 words against the
genre's 1.24** — and the excess is not spread evenly: object counting runs at 2.2x the genre,
which is exactly our general numeric excess, while **calendar and duration runs at 6.2x**. The
operator pointed at *"describing days events"* and the calendar is the one family that is
disproportionate.

**The registered direction held and both of its named escape routes are closed.** The market's
LitRPG is not itself mundane-heavy (1.24/1k, a quarter of its chapters carry none), and our
mundane density is not ordinary for published fiction (5.29x the non-genre control, with **zero**
of our chapters carrying none against 32% of theirs). So this is not only an absence of the
system half. It is an absence of the system half *and* an excess of the mundane one.

## 1. The validity arm, before any distribution is read

A code-only counter's characteristic failure is locating *numerals* rather than context, and
nothing inside the instrument can tell the difference. The intermediate covers every genre, so
chapters the market did not tag `LitRPG` are a population the system counter must score well
above — and the mundane counter must **not**.

| pooled per 1,000 words | LitRPG | not LitRPG | separation |
|---|--:|--:|--:|
| `system_magnitude` | **2.632** | **0.246** | **10.7x** |
| share of chapters carrying one | **0.555** | **0.158** | **3.52x** |
| `mundane_core` | 1.236 | 1.121 | **1.10x** |

**Both rows are the arm.** A counter that separated the genre on the mundane family too would be
reading chapter length or numeral density rather than context. It separates 10.7x on system and
1.10x on mundane, which is the discriminant shape the census needs and it was computed in the
same pass (`BRIEF.md` §5).

**Coverage is the statistic to believe.** A single large stat table contributes as many system
mentions as it holds numbers, so the density is heavy-tailed; a share of chapters cannot be moved
by one outlier.

**And it is not an era artifact** — the control `BRIEF.md` §2's `tricolon_rate` row exists to
force. LitRPG `system_magnitude` pooled per 1,000: human pre-LLM **2.877**, undeclared 2025
**2.265**, declared-AI 2025 **2.160**; coverage 0.588 / 0.520 / 0.514. The genre's habit is
slightly *stronger* before the LLMs than after, so no version of "the market changed" explains
our distance from it.

## 2. The system column: ours is empty, and it is below general fiction

| | ours | market LitRPG | market not-LitRPG |
|---|--:|--:|--:|
| chapters | 20 | 13,364 | 51,567 |
| independent units | 8 books | 584 fictions | 3,096 fictions |
| `system_magnitude` per 1k, pooled | **0.025** | 2.632 | 0.246 |
| share of chapters with one | **0.05** | 0.555 | 0.158 |
| `system_ordinal` per 1k, pooled | 0.225 | 0.104 | 0.068 |
| `magnitude_share_of_anchored`, mean | **0.0029** | **0.2002** | 0.0323 |

Read the last row first: it is bounded in [0, 1] and immune to how many numbers anyone writes.
**Ours is 69 times below the genre's and 11 times below the non-genre control's.**

The `0.05` coverage is one chapter out of twenty and the hand-check disqualifies it, so the
honest reading of our system column is **zero across 39,947 words**. Six of our eight books carry
no system-anchored number of any kind.

**The one column where we are ABOVE the market is `system_ordinal`** — 0.225/1k against 0.104 and
0.068. Every system-anchored number on our shelf is an ordinal on a ladder word: *fourth grade*,
*eighth-grade price*, `THIRD TIER`, `SECOND TIER`. This is read 8 §4.2 arriving as a count. The
progression beats fired and landed on ordinal titles because an ordinal title is the only ladder
the pipeline can declare, and **the split between `system_magnitude` and `system_ordinal` exists
because our own shelf forced it** — a single `system` column would have reported us as having
nine system numbers and hidden that not one of them is a quantity.

## 3. The mundane column, and where the excess actually sits

| pooled per 1,000 words | ours | market LitRPG | ours ÷ genre |
|---|--:|--:|--:|
| all numeric mentions | 28.012 | 12.831 | **2.2x** |
| `object_count` | 9.187 | 4.113 | 2.2x |
| `mundane_core` | 5.933 | 1.236 | **4.8x** |
| `calendar_duration` | 4.431 | 0.718 | **6.2x** |
| share of chapters with no mundane number | **0.000** | 0.254 | — |

**2.2x is the baseline, not the finding.** We write more numbers of every kind, and object
counting tracks that baseline exactly. The calendar does not: 6.2x against a 2.2x general excess
is the one family whose density cannot be explained by "this shelf likes numbers."

Against the non-genre control the picture is the same and slightly larger: `mundane_core` 5.933
against 1.121, **5.3x**, and `calendar_duration` 4.431 against 0.724, **6.1x**. Our calendar habit
is not a genre convention we are over-applying. It is not a convention of published fiction at
all.

**At book grain the gap survives.** Collapsing each serial to one number (`BRIEF.md` §6(5) — fifty
chapters of one serial share an author and a tic): our median book sits at 4.78 `mundane_core` per
1,000, the median LitRPG fiction at 1.19, the median non-genre fiction at 1.04. Our side is n=8
independent units and that is small; no bar is declared over any of it.

## 4. The presentation layer, measured across 13,364 market chapters

| pooled per 1,000 words | ours | market LitRPG | market not-LitRPG |
|---|--:|--:|--:|
| spelled numbers | **27.086** | 8.158 | 7.522 |
| digits | **0.926** | 4.672 | 1.269 |
| share of chapters with no digit at all | **0.750** | 0.320 | 0.561 |

Read 4 counted **0 digits in 7,865 words** of *A Good Take* and this census reproduces that
figure exactly, then generalises it: three-quarters of our chapters contain no numeral anywhere.
The genre writes 3.7 times the digits of non-genre fiction; we write **fewer digits than
non-genre fiction does**. The genre's numbers are numerals on a surface. Ours are words in a
sentence.

## 5. What was subtracted, refused, and got fixed after the market half opened

**Quarantine, visibly.** The 26 descriptor-half fiction ids of §150.1 are 2,505 rows, subtracted
from every ours-versus-market number: 67,436 seen, 64,931 compared. They are reported on their own
line and never pooled — and they are not a neutral sample, at `system_magnitude` 3.128/1k and
0.687 coverage, both above the LitRPG half they were drawn from.

**One refusal the operator will notice.** *"An hour of rain"* is on read 8 §4.1's own list and this
instrument cannot see it: `a` and `an` are not numerals, and admitting them would sweep in every
indefinite noun phrase in the language. Declared rather than patched, with the two rejected
attempts recorded (`PRE_REGISTRATION["refused"]`) — §150.4's deleted `fragment_rate` is the
precedent for naming a counter that would not be what its name said.

**An ordinal date cannot be told from an ordinal enumeration here.** *"The fifteenth in the spring
almanac"* is a date and *"the twenty-second jar"* is an enumeration, and the distinguishing
evidence needs a parser. Both land in `ordinal_enumeration`, which is why that family is never
pooled into `mundane_core`. Two attempts are recorded as rejected: treating a bare high ordinal
as a date (fitted to one instance) and treating a nearby season word as a date context (drew *the
spring almanac*, which is a book).

**Three precision fixes were made after the market half opened, and the disclosure is part of the
record.** The frozen pre-market registration is committed at `96b622f` under digest
`134ae6f2a80bd274`, and the pre-narrowing full-corpus numbers are kept at
[`results/number-context.pre-narrowing.json`](results/number-context.pre-narrowing.json) so the
drift is auditable rather than remembered. A 2,000-row smoke aggregate **had been seen** before
they were written, so each is named with the direction it moves this census's own headline:

1. a determiner after a head ends the noun phrase — *"one more thing-your abilities"* was a stat.
   **Favours** the headline;
2. `one` leaves the copula-age pattern — *"he is one of the people in this town"* was an age.
   Lowers the mundane column on **both** halves;
3. structural headings in the shards' other languages are skipped and an `english_share` control
   is reported — *Capitulo 6* and *Cena 1* were object counts. **Cuts against** the headline.

`register_census` is the precedent — its narrowings 3 and 4 also came from the market half — and
`BRIEF.md` §5 requires it: a detector exact on the half that motivated it and loose on the half it
is compared against manufactures the comparison out of its own error rate.

**The English control, which is the one that could have taken the headline away.** A non-English
chapter scores near zero on every English lexicon here, which would depress the market's mundane
density and inflate our gap. Measured: 0.8% of the LitRPG half and 0.86% of the other sit below
the floor, and removing them moves `ours ÷ market` from **4.800 to 4.756** and from **5.295 to
5.261**. About 1% of the effect was language.

## 6. What this census does not say

It does not say a mundane-anchored number is a defect, that our calendar density caused any
reader anything, or that matching the market's ratio would improve a book. It measures where
numbers land. Precision is hand-checked and the hand-check is exhaustive on exactly one chapter —
read 8 §4.1's own list for *Unlicensed Weather* chapter 1, reproduced including its zero system
numbers. Recall against an exhaustive market count is unmeasured. One measured false positive with
no mechanical fix (`three levels of it below the lobby`) is carried in
`MEASURED_FALSE_POSITIVES` rather than quietly borne, and it is the single hit in our own system
column.
