# Findings — the reassembly instrument

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG.md` owns the design and the reading fixed before spend; this file owns the reading.
Status: **OBSERVED**, 2026-09-02, six stimuli, three seeds each, eighteen cells, no cell
repaired (every answer returned every label once). Raw answers in `raw.jsonl` (labels only),
the summary in `results.json`. Nothing here promotes a claim past OBSERVED.

## The cells

| stimulus | mean tau | min tau | mean adjacent pairs kept |
| --- | --- | --- | --- |
| shelf, *The Primal Hunter* | 0.997 | 0.991 | 0.97 |
| shelf, *Randidly Ghosthound* | 0.995 | 0.991 | 0.93 |
| shelf, *Defiance of the Fall* | 0.884 | 0.821 | 0.43 |
| shelf, *The Gam3* | 0.854 | 0.775 | 0.84 |
| ours, draw1 (the pass off) | 0.954 | 0.945 | 0.69 |
| ours, draw2 (the pass on) | 0.928 | 0.807 | 0.91 |

## The reading, by the table fixed before spend

**The instrument reads.** The four anchors reassemble far above chance (mean tau 0.85 to
1.00 against the registered floor of 0.5), so a model reader can recover a chapter's order at
this grain from its content, and the task cannot be passed without reading where each
paragraph belongs. This is the first instrument in this house whose measurable depends on
order by construction and whose control passed.

**Ours are inside the shelf's range.** Draw1 at 0.954 and draw2 at 0.928 sit between
*Defiance* (0.884) and *Randidly* (0.995). By the table: our chapters' order is as recoverable
as the market's at this grain. Neither the *list* reading (below the range) nor the
*signposted* reading (above it) applies.

**What the shelf's spread says about the measure.** *Defiance*'s adjacency is the lowest
(0.14 on one seed): its system boxes are one-line paragraphs the reader places well as blocks
and poorly as neighbours. *The Gam3*'s two low seeds swap one block of three paragraphs
(P17 to P19) forward. Tau is robust to both; adjacency is not, which is why both are
reported and neither is a bar.

## What it cannot show

Six stimuli, one reader, three seeds: a description of six chapters. It does not separate
draw1 from draw2 (two draws, never a treatment effect), and it does not separate ours from
the market, which is itself the finding: whatever the operator's reads name in our chapters,
it is not that the paragraphs could be swapped without a reader noticing. Recoverability is
coherence and not engagement, and is not claimed as engagement.

## What is owed

Since the tells are shapes inside sentences and the order is sound, the reader that reads
meaning is still the missing instrument, and the costed continuation (§122) with a cost that
bites is still the missing lane. Reassembly stays as a diagnostic beside the tells counter: a
chapter below the shelf's range would be a *list* the reads have named, found by code.
