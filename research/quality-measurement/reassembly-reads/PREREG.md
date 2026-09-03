# Pre-registration — order recovery across the chapters the operator read

**Registered 2026-09-03, before any cell is bought**, as the second experiment of
`plan/handoff-reader-sims.md`. It is the owed instrument from the readers' order control
(`../readers-order-control/FINDINGS.md`) pointed at the question the handoff asks of it: given
a chapter's paragraphs shuffled, a model reader puts them back (`../reassembly/`, stage-0
§199.2), and does that recoverability differ between the chapters the operator's reads called
broken at chapter level and the chapters where his items stayed inside sentences. His reads are
defect harvests and not data (§95); the separation below is a **description** of two sets of
chapters and never a label, a bar or a validation. CONJECTURE → REGISTERED here; OBSERVED when
the cells are on disk; nothing below becomes SUPPORTED by this file.

## The instrument, unchanged

`../reassembly/run.py` byte for byte: one plain reader through the production registry (the
pinned model, no persona), the first thirty paragraphs of a chapter shuffled under three fixed
seeds (11, 23, 37), the reading order asked for as a closed JSON list of labels, Kendall's tau
and the adjacent-pairs share scored by code, an answer that omits or repeats a label repaired
and flagged. `run.py` beside this file imports that module by path and records its SHA-256, so
a cell here and a cell there are the same measurement; the six cells already bought (the four
placed openings and pilot 24's two draws) are reused from `../reassembly/results.json` by
pointer and are not bought again. Its own check already holds: the anchors reassemble at mean
tau 0.85 to 1.00 against the registered floor of 0.5, so the task is readable at this grain.

## The stimuli and the two classes, fixed here

Every chapter one on the shelf that an operator read covered, located by grepping the read's
own quotations against the shelf's chapter files (the file the quote sits in is the file that
was read), plus the one read chapter that is off the shelf (pilot 15's draw 2, archived under
`runs/pilots/pilot15/shelf-draw-2/`). A chapter is **class S** if the read named at least one
item about the chapter rather than a sentence — whether it can be followed, whether anything
happens or progresses, whether the reader is present in it, whether paragraphs hold their
topic — and **class T** if every item the operator named was a sentence-level defect (a tell, an
idiom, a word, a figure, a manner gloss, a punctuation habit) or no chapter item was named at
all. The quote that places each chapter is the operator's; the analysis of which class it
falls in is ours and is made here, before any number exists.

| shelf folder | read | class | the operator's words that place it |
| --- | --- | --- | --- |
| `reappraisal` | 2 | S | *"Not much seems to be happening, just looking and observing things."* |
| `what-takes` | 3 | S | *"Its too confusing who the main character is."* |
| `a-good-take` | 4 | S | *"descriptions in the book are of minutia and irrelevant details"*; *"no lists of abilities progression is missing"* |
| `patch-notes-for-the-apocalypse` | 6 | S | *"i am being narrated events instead of feeling present in the events"* |
| `the-rainwright-s-apprentice-has-no-licence` | 7 | S | *"i can't continue reading, it's not gripping"* |
| `unlicensed-weather` | 8 | S | *"i'm not feeling like i'm reading litrpg at all"*; numbers *"come up in cotext they shouldn't come up"* |
| pilot 15 draw 2 (archived, `runs/pilots/pilot15/shelf-draw-2/`) | 9 | S | *"too superfocused on details, rather than story"* |
| `what-the-kettle-remembers` (draw 4) | 10 | S | *"Impossible to understand what is happening in the chapter if you haven't read the overview."*; *"stagnant and not progressing"* |
| `reading-the-ladder-wrong` | 11 | S | *"we are describing the world to the readers, instead of focusing on the actual story"* |
| `the-station-keeps-score` (draw 2) | 12 | S | *"the paragraph jumps topics mid-stream"*; *"This happend and then this happend"* |
| `failed-delivery-notice--c7497693` | 17 | S | *"i'm confused by the goal"*; *"who is saying this, i'm confused"* |
| `signed-for-by-nobody` | 18 | S | *"this failed to produce a vivid image in my mind"*; *"what does card through the door mean??"* |
| `the-station-keeps-score--435c41f9` (draw 3) | 13 | T | *"It reads a bit better"*; a manner gloss, a pedantic phrase, one garden-path clause |
| `the-station-keeps-score--fa09c89c` (draw 4) | 14 | T | one manner gloss (*"the way he had said everything since the pump"*) |
| `the-game-nobody-plays-anymore` | 15 | T | *"ai tell"* twice; *"It's very clear they are ai generated"* |
| `nineteen-floors-down` | 15 | T | read beside pilot 19; no chapter item quoted |
| `the-line-nobody-else-has--0ffc8699` | 16 | T | *"overall greatly improved"*; four idiom items |
| `the-ratchet-counts-down` (draw 1, already measured) | 19 | T | five sentence tells and one unmet term |
| `ground-held` | 19 | T | pilot 24's first-person arm; the person decision only, no item |

Twelve chapters in S and seven in T; both non-empty before spend. Chapters drafted between
2026-08-21 and 2026-09-02 under different pipelines, persons and writers sit in both classes,
and nothing here is a treatment effect between any two of them.

## The measurables and the reading, fixed before spend

Per chapter: mean tau over three seeds, the minimum, and the mean adjacent-pairs share, exactly
as `../reassembly/results.json` reports them. Then, as descriptions:

1. the two classes' per-chapter mean taus listed side by side with each class's mean, minimum
   and maximum, and the anchors' range (0.85 to 1.00) beside both;
2. the difference of class means (T minus S), with a percentile bootstrap over chapters
   (chapters as the unit, 2,000 resamples, seed fixed from the values) at the registered
   alpha of 0.10 — printed as an interval and read once, by the table below;
3. every chapter whose mean tau falls below the anchors' range, named: that is the *list*
   shape the reads have named, found by code, whatever its class.

| the interval on T minus S | reading |
| --- | --- |
| strictly above zero | recoverability runs with the operator's chapter-level items in this set: the chapters he could not follow chain less; a description of nineteen chapters, never a validation of the instrument as a reader of his judgment |
| contains zero | recoverability does not separate the classes at this n: whatever his chapter-level items name, it is not that the paragraphs could be swapped without a reader noticing — the reading the six prior cells already gave for two chapters |
| strictly below zero | reported as what it is; the chapters with sentence-level items only chain less |

No bar over tau. One reader, three seeds, nineteen chapters: a description, and the four
attainability checks are run on the description rather than on a bar — the difference lives
in [-2, 2], its direction is named, its unit is the chapter, and both classes are non-empty.

## Cost and cap

Eighteen new stimuli, three seeds, fifty-four calls on the registry's pinned model, one call
per seed with the chapter's first thirty paragraphs as input and at most 800 output tokens;
cap **$30** subscription-equivalent, read from each result's own usage and stopped between
calls, with every cell bought kept and a stopped run stamped partial. One CLI arm at a time
on this box; not while a draw or another arm is running; `transport_failures` (a refused or
malformed answer, counted by the script) read before any number.

## What may not follow from it

No reader is retuned on this (§89, §97.1). No chapter is revised, redrafted or selected on its
tau (§105). Recoverability is coherence and is not engagement; a chapter that reassembles
perfectly can be one nobody would read on, and the reads say most of these are. And a
difference between the classes, in either direction, says nothing about which pipeline change
produced it: the chapters differ in everything at once.
