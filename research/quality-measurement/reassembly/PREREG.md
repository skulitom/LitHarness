# Pre-registration — the reassembly instrument

**Registered 2026-09-02, before any cell is bought**, on the operator's direction of the same
day: *"Register the reassembly instrument and run it on both chapters."* It answers the
readers' order control (`../readers-order-control/FINDINGS.md`): both `readers` lanes read
content wherever it sits and not where the story is, and the carry-on lane is saturated. This
instrument's measurable depends on order by construction. CONJECTURE → REGISTERED here;
OBSERVED when the cells are on disk; nothing below becomes SUPPORTED by this file.

## The question

Can a model reader put a chapter's paragraphs back in the order they were written, and does
that recoverability differ between this house's chapters and the openings the operator placed
on the shelf? Recoverability is a property of the chapter's causal and temporal chaining: a
chapter whose paragraphs each follow from the last can be reassembled from its content; a
list of facts cannot. It is not engagement and is not claimed to be.

## The stimuli

Chapter one of the two third-person draws of pilot 24 — draw1 with the tells pass off
(`book-library/the-ratchet-counts-down/chapters/Chapter1.txt`) and draw2 with it on
(`book-library/the-ratchet-counts-down--0993282c/chapters/Chapter1.txt`) — and, as the
reference distribution, the four openings on the shelf (`book-library/<name>/Chapter1.txt`).
Each stimulus is its first thirty paragraphs, machine lines included as paragraphs, shuffled
with a fixed seed and labelled; three seeds per stimulus.

## The task and the measurables, all code

One plain reader (no persona: a persona is about what a reader wants, and this task wants
nothing), shown the labelled paragraphs in shuffled order and asked for the reading order as a
closed JSON list of labels, every label once. Scored by code:

- Kendall's tau between the returned order and the true order (1 is the true order, 0 is
  chance, negative is reversed);
- the fraction of true adjacent pairs the answer keeps adjacent (a local measure that survives
  one misplaced block);
- an answer that omits or repeats a label is scored as returned after dropping the repeats
  and appending the omissions in their shuffled order, and flagged.

## The reading, fixed before spend

The shelf's four give the reference range of tau per stimulus (mean of three seeds). Ours are
read against it as descriptions:

| ours against the shelf's range | reading |
| --- | --- |
| inside the range | our chapters' order is as recoverable as the market's at this grain |
| below the range | our chapters chain less than the market's: paragraphs that could be swapped without the reader noticing, which is the *list* shape the reads have named |
| above the range | our chapters signpost their order more than the market's; not better, and noted |

And the instrument's own check: if the four anchors do not reassemble well above chance
(mean tau under 0.5), the task is not readable at this grain and the instrument is not one,
whatever ours score.

## Cost and cap

Six stimuli, three seeds, eighteen calls; cap $5; one CLI arm at a time.

## What may not follow

No reader is retuned on this. A recoverability number is a description of a chapter; it is
not a bar, and a difference between two of ours (draw1 against draw2) is two draws, never a
treatment effect.
