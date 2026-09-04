# Findings — the anticipation probe's paid run: REFUTED by its own kill conditions

House form: the claim, the number beside it, and the caveat travelling with the claim.
`plan/anticipation-probe-validity.md` and `PREREG.md` beside this file own the design, the four
kills and the amendments; this file owns the reading. Status: **OBSERVED**, 2026-09-04, and
**REFUTED** for the registered claim — the probe fired two of its own four kill conditions on a
clean, complete run. Raw answers in `results/anticipation-rerun-raw.jsonl`, the result in
`results/anticipation-rerun.json`. Nothing here promotes a claim past OBSERVED.

## The one sentence

**The probe returns the same answer whatever is done to the passage.** Deleting the sentences
that establish what failure costs moves its measurables no further than re-flowing the
whitespace does — and on specificity it moves them the *wrong way*.

## The run, which is the one thing that went right

800 calls, **200 of 200 cells scorable**, 795 of 800 draws parsed, zero transport failures, no
ceiling stop, $30.65. This is the instrument's first complete measurement: the run of six hours
earlier bought 800 equally clean calls and scored nothing, because the transport truncated every
array answer to its first element (stage-0 §226). The fix is what makes this file a reading of
the probe rather than of the transport.

## What the probe did, by arm

| arm | specificity | distinctness | engagement | bipolar rate |
| --- | --- | --- | --- | --- |
| original | 0.4255 | 0.9204 | 0.7632 | 0.844 |
| **destake** | **0.4312** | 0.9234 | 0.7542 | 0.881 |
| deplete_matched | 0.4299 | 0.9172 | 0.7688 | 0.819 |
| rename_entities | 0.4247 | 0.9140 | 0.7708 | 0.881 |
| rewhitespace | 0.4232 | 0.9184 | 0.7757 | 0.804 |

**K1 — constancy — KILL.** The arms' mean specificity spans **0.0080** against a registered
floor of 0.05. The registration said what that means before the run: *the probe is a constant
function and every statistic below it is undefined.*

**K2 — the per-sham floor — KILL.** Destake's distance from the original is 0.0090 on engagement
and 0.0057 on specificity; the largest single sham's is 0.0125 and 0.0023. Neither clears by the
registered 0.05 margin, and on engagement **the whitespace re-flow moved the probe further than
deleting the stakes did**.

**K3 — the matched control — PASS, and it is worth nothing.** Destake exceeds `deplete_matched`
on both measurables, 0.0090 against 0.0056 and 0.0057 against 0.0044. Inside a total arm span of
0.008 that is noise ordering itself, and K1 has already made it undefined. Recorded as passed
and read as meaningless — a pass on a constant function is not evidence.

**K4 — draw reliability — REPORTED.** Between-passage sd of specificity 0.0507, which is six
times the entire between-*arm* span. The probe distinguishes passages far better than it
distinguishes what was done to them.

**The sign is wrong as well as the size**, and that is the sharpest single number here: the
destaked passages scored **higher** specificity (0.4312) than the originals (0.4255). The
registered hypothesis was that flat text yields vaguer, less grounded futures. It yields
marginally more grounded ones.

## No persona rescues it

The registration's hope was that a persona reading *for* risk would be sensitive to stakes where
one reading for prose texture would not. Engagement by persona, original against destake:

| persona | original | destake | span across all five arms |
| --- | --- | --- | --- |
| climber | 0.733 | **0.767** | 0.069 |
| mechanism | 0.783 | 0.758 | 0.033 |
| regular | 0.769 | 0.733 | 0.036 |
| stranger | 0.767 | 0.758 | 0.033 |

None separates, and `climber` — the persona written to read for what a climb costs — reports
*more* engagement on the passages whose costs were deleted.

## Why it failed, and the shape is one this house has seen twice before

**The probe is saturated.** Engagement sits at 0.75–0.78 and bipolarity at 0.80–0.88 on every
arm, including the most damaged. Asked for three concrete futures and a stance on each, the
reader always produces three concrete futures and almost always reports both hope and dread. The
measurable has no room to move because the answer is always the same shape.

That is the third instrument in this house to die this way: §70's persona gate-0 returned
`keep-reading` on 195 of 196 draws, §199.1's `readers` lane carried on four of four on every
chapter and every shuffled copy of it, and now this. **A report-channel question that a
cooperative reader can always answer well is a question with no variance in it**, whatever the
answer is about — and all three instruments were designed to avoid the verdict channel §89
closed, which they did, and inherited saturation instead.

## What this does not say

Nothing about whether anticipation is a real property of reading, and nothing about §128's
direction that a writer might take direction from what a reader hopes for. It says that **this
probe, with these measurables, on this substrate, cannot tell a passage with stakes from one
without them**. The substrate is ten own-drafted scenes; the manipulation is `ablate.destake`,
which is certified only in the sense that it deletes sentences a lexicon scored as stake-bearing;
and a probe that fails to see the strongest available manipulation is not thereby shown to be
blind to subtler ones — it is shown to be blind to this one, which is the one it was registered
against.

## What is owed

Nothing further from this instrument as registered. `anticipation.v0` is REFUTED against its own
kills, and the honest next step is not a sixth arm or a reworded probe — §144's redirection says
the unit of search is the mechanism, and a seventh phrasing of the same question is not one. The
saturation observation above is the transferable part, and it belongs in `BRIEF.md` beside the
other two instruments that died of it.
