# Pre-registration — the readers' order control

**Registered 2026-09-02, before any cell is bought.** The operator's direction of read 19
(`plan/reader-read-19.md` §1): *"We really need to fix the recognition of order of sentences
and meaning for our readers."* This is the control that says whether the `readers` lanes read
story or surface, in §195.5's shape and with its decision table fixed here first. It is an
instrument-validity measurement under `EPISTEMIC_GOVERNANCE.md`: CONJECTURE → REGISTERED here;
OBSERVED when the cells are on disk; nothing below becomes SUPPORTED by this file.

## The question

Pilot 24's `readers` run (`plan/serial-pilot-24.md` §4) carried on four of four on both
chapters against named rivals, and its expectations named the book's own rules and numbers.
§195.5 found the opening-parity panel taking a paragraph-shuffled copy of ours over an anchor
at the ordered copy's rate. The question: do the two `readers` lanes answer differently when
the same chapter is shown with its order destroyed?

## The stimuli

One chapter, the third-person *The Ratchet Counts Down* (pilot 24, `book-library/the-ratchet-counts-down/chapters/Chapter1.txt`),
scene 2 as the readers read it, in three copies:

- `ordered`: the scene as drafted;
- `paragraphs`: its paragraphs shuffled with a fixed seed, machine lines kept in place;
- `sentences`: the sentences inside each paragraph shuffled with a fixed seed, paragraph order
  kept.

Each copy is cut at `text.stop_point` (the same fraction), so every reader sees about the same
number of words and the same future is withheld. The rival is the same named book for every
cell (`rivals.draw` on a fixed key).

**Amendment a, 2026-09-02, before any cell was bought.** The dry run measured the cut: the
`ordered` and `sentences` copies stop at 648 words and the `paragraphs` copy at 593, because
the stop point snaps to a paragraph boundary and shuffling the paragraphs moves the boundary
nearest the fraction. The passages are therefore not equal in length across all three copies;
the word count per copy is reported beside every number, and any reading that leans on the
`paragraphs` copy alone is weaker than one that leans on `sentences`, which is cut identically
to `ordered`. The rival every cell names is *The Exorcist Doctor*.

## The lanes and the measurables, all code

- **Measurement lane** (`readers.render_choice_request`, four readers): the choice
  (carry on / put down / later / the rival). Measurable: the count carrying on, per copy.
- **Steering lane** (`readers.render_anticipation_request`, four readers): `expect_next`.
  Measurables, code only: (a) content-word overlap between the expectation and the withheld
  continuation (Jaccard over lowercased words of four letters or more, stopwords removed);
  (b) the expectation's specificity as the anticipation probe scores it (§124): counts of
  numbers, capitalised names and concrete nouns per hundred words.

## The decision table, fixed before spend

| measurement lane, `sentences` copy against `ordered` | reading |
| --- | --- |
| carries on at the ordered copy's count (difference under 2 readers of 4) | the lane's carry-on does not depend on the story being in order: surface, as §195.5 found for the panel |
| carries on by at least 2 fewer readers | the lane reads order at this length; a first cell, n of one chapter, never a bar |

| steering lane | reading |
| --- | --- |
| overlap with the continuation is no lower on the shuffled copies than on `ordered` | the expectations come from the content and not from where the story is: surface |
| overlap is lower on both shuffled copies, the `sentences` copy lowest | the expectations follow the story; the probe's frame (§124) is the story-sensitive instrument to build out |

Any other pattern is reported as what it is. One chapter is one chapter: this registers a
control and its directions, not a result about the readership.

## Cost and cap

Three copies, eight readers, twenty-four calls; one repeat on the `sentences` copy for the
measurement lane if its count sits exactly at the boundary (four more). Cap $5. One CLI arm at
a time; not while a draw is running.

## What may not follow from it

No reader is retuned on this result (§89's verdict channel, §97.1). A lane that reads surface
stays a reading beside the chapter and steers nothing; a lane that reads order is not thereby
qualified to steer — that is the control plane's evidence (`domain/editorial.py`), of which
this is one control and not the battery.
