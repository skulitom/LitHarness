# Findings — the readers' order control

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG.md` owns the design, the decision table and amendment a; this file owns the reading.
Status: **OBSERVED**, 2026-09-02, one chapter, twenty-four cells, no repeat needed (no count
sat at a boundary). Raw answers in `raw.jsonl`, the summary in `results.json`. Nothing here
promotes a claim past OBSERVED.

## The cells

*The Ratchet Counts Down*, pilot 24 draw1 (third person), scene 2, cut at the stop point;
rival *The Exorcist Doctor* in every cell. Passage lengths: `ordered` 648 words, `sentences`
648, `paragraphs` 593 (amendment a).

| copy | carried on (of 4) | mean overlap with the withheld continuation | mean specificity |
| --- | --- | --- | --- |
| ordered | 4 | 0.040 | 0.46 |
| paragraphs | 4 | 0.040 | 3.83 |
| sentences | 4 | 0.047 | 0.00 |

## The reading, by the table fixed before spend

**Measurement lane: surface.** The `sentences` copy carried on at the ordered copy's count,
four of four, a difference of zero readers against the table's two. So did the `paragraphs`
copy, and one of its readers said so in its own words: *"The scrambled timeline is annoying but
the thing underneath is clean."* The lane's carry-on does not depend on the story being in
order. It is also saturated: four of four on every chapter this loop has read (pilot 24's four
arms) and on every copy here, which means it cannot separate anything from anything at this
length whatever the story does.

**Steering lane: surface.** Overlap with the withheld continuation is no lower on either
shuffled copy than on `ordered` (0.040, 0.040, 0.047). The expectations from the
`sentences` copy are nearly the ordered copy's word for word — *swept downstream toward
whatever's pushing and dragging in the water, loses the notebook or nearly does* — so a
sentence-shuffled passage is reassembled by these readers into the same scene, which is a fact
about a model reading and not about the chapter. The `paragraphs` copy's readers "predicted"
June's messages and the street full of words: the shuffle had moved the chapter's ending into
the visible passage, and the expectations named what they had already been shown. That is the
cleanest demonstration in the set that the expectation follows content wherever it sits and not
where the story is.

## What it cannot show

One chapter, one shuffle seed, four readers a lane: this registers the direction of a control
and reads one cell of it; it is not a result about the readership beyond this chapter. It does
say what §195.5 said of the panel, on the other instrument, and it says one more thing: a lane
whose carry-on is four of four on everything has no room to read anything.

## What is owed

An instrument whose measurable depends on order by construction, and a cost that bites.
Reassembly is the candidate for the first: hand a reader the paragraphs shuffled and score
its ordering against the true one by code (a rank correlation), which is a property of the
chapter's causal chaining that a shuffle cannot fake and a model cannot pass on content
alone. For the second, the costed continuation of §122 (`feed_core`, `feed_battery`) has the
budget the `readers` lane lacks: a reader that has to give something up to carry on. Both are
registrations, not prompts; neither retunes a reader on this file (§89, §97.1).
