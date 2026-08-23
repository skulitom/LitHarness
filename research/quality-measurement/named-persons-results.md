# Named-person introductions at chapter grain: the distribution, and the null under it

**Status: DESCRIPTIVE, 2026-08-22. No bar is declared here and none is implied.** The counter is
`named_persons.py`; it is not registered in `domain/axes.COUNTERS`, is not an axis, carries no
pole, and nothing in any generation path reads it. A chapter-grain introduction budget, if the
operator ever wants one, takes its number from the table below and the setting of it is the
operator's act (stage-0 §81, §85, §87 and §89 each record a bar declared over a quantity that
could not do what it said).

Nominated by the 2026-08-22 read ([`plan/reader-read-3.md`](../../plan/reader-read-3.md) note 2):
*"Too many names and characters mentioned too fast into the story."* C6 — *"in the first three
hundred words of a scene, name at most three things a reader is expected to remember"* — was in
every drafting prompt of *What Takes* and was honoured in every scene (the eight openings score
2, 3, 1, 2, 3, 1, 2, 2 real names). A chapter is four scenes, so the budget resets four times
before a reader reaches the end of one sitting, and nothing bounds the chapter.

## 1. What is counted, and what is not

**Distinct proper names a chapter introduces**, with the word offset of each first appearance.
Not persons: `domain/axes`' locator finds capitalised tokens the book also writes mid-sentence,
and it cannot separate a person from a place, an institution or a month — on chapter 2 of *What
Takes* it returns `February` and `Marker` beside `Orne Marrow`. Separating those is a judgment
and there is no instrument for it here. The operator's own person-only hand count of that book's
chapter 1 — nine named people and three unnamed roles — is reported beside the counter's number
and never in place of it. Nothing here classifies a name as major or minor.

Two artefacts of the locator are **carried rather than fixed**, because fixing a counter after
seeing its answer is the failure `platform_priors.py` freezes its matchers to avoid:

1. **Contractions.** `I'll`, `I'd`, `I've` satisfy every clause of `_is_candidate` and the book
   writes them mid-sentence, so the locator proves them. Measured on *What Takes*: **five** across
   the eight scene openings, affecting four scenes — `reader-read-3.md` says four, which is the
   number of affected scenes rather than the number of tokens. Every figure below is `net` (raw
   minus contractions); `raw` is in the JSON beside it.
2. **A forename met before its surname counts twice.** The fold in `opening_proper_noun_names`
   collapses a bare token into a fuller name only when the fuller name has one candidate
   component, so `Doss` at word 198 and `Doss Orley` at word 924 are two introductions.

## 2. The distributions

| substrate | n | median | mean | sd | p25 | p75 | p90 |
|---|--:|--:|--:|--:|--:|--:|--:|
| RoyalRoad, all genres | 2,000 | **17** | 21.59 | 16.18 | 11 | 27 | 42 |
| RoyalRoad, LitRPG tag | 2,000 | **24** | 29.58 | 22.53 | 14 | 39 | 60 |
| our own chapters | 4 | 23.5 | 21.25 | 8.98 | 18 | 29 | 30 |

Per 1,000 words, the same populations: RoyalRoad all-genres median **10.15**, LitRPG median
**10.90**, our four chapters **2.10 – 7.23** (median 5.71).

Substrate coverage, stated rather than assumed:

| source | ran? |
|---|---|
| own books, `book-library/*/chapters/*.txt` | **RAN** — 4 chapters across 2 shelves (`reappraisal`, `what-takes`) |
| own books via `corpus_io.generated_scenes` on `serial3.db` | **RAN** — reproduces *What Takes* at 8 and 18, off the store rather than the shelf (word counts differ by the nine standalone `*` scene-break tokens per chapter) |
| cached RoyalRoad shards, `corpus_io.royalroad_chapters` | **RAN** — shards 3 and 30 at the pinned snapshot, under `C:/DEV/MirrorBench/.venv` |

## 3. Where the four own chapters sit

| chapter | words | raw | net | per 1k | percentile, all | percentile, LitRPG |
|---|--:|--:|--:|--:|--:|--:|
| `reappraisal/Chapter1` | 4,151 | 32 | 30 | 7.23 | 80.2 | 63.5 |
| `reappraisal/Chapter2` | 4,252 | 31 | 29 | 6.82 | 78.5 | 61.6 |
| `what-takes/Chapter1` | 3,805 | 9 | **8** | 2.10 | 16.1 | **11.8** |
| `what-takes/Chapter2` | 3,917 | 21 | **18** | 4.60 | 54.6 | **37.6** |

## 4. The null, reported as a result

**The counter does not reproduce the complaint.** The two chapters the operator read and named as
having too many names introduce **fewer** distinct names than the genre: 8 and 18 against a
LitRPG cohort median of 24, at the 11.8th and 37.6th percentiles, and 2.10 and 4.60 per thousand
words against a cohort median of 10.90. *Reappraisal*, which this read did not complain about,
sits higher on both chapters (63.5th and 61.6th).

A chapter budget set from this distribution would license **more** names than the complained-about
book already has. So the counter is a description of a population and not an explanation of the
defect, and this is the second time a counter nominated by a human read has failed to order the
case that nominated it — `opening_proper_nouns` placed the complained-about chapter at the 68.5th
percentile of published openings ([`opening-counters-results.md`](opening-counters-results.md)).

What the measurement cannot rule out, stated so the null is not read as more than it is: the read
judged two chapters of a book whose named people were, with one exception, **invented by the
outline** — four of the world's five forged cast members score 0 in both chapters, and only
`clerk_amble` reaches the page by name. So the reader met people who arrived without declared
ties, wants or roles. "Eight names" and "eight names each of whom the reader has a reason to
hold" are different experiences and this counter cannot tell them apart.

The offsets it does record say *when*, and when is the half of the complaint ("too fast") that a
count over a whole chapter throws away. *What Takes* chapter 1 introduces at 0, 17, 804, 1234,
2936, 3123, 3201, 3565 (net of the contraction at 236) — two names in the first eighteen words
and then nothing for four hundred; chapter 2 introduces eight of its eighteen inside the first
thousand words. Two chapters with 8 and 18 names are not two chapters that feel the same.

**A note on `reader-read-3.md`'s word 804, because two re-derivations disagreed with it and both
were right.** That document gives word 804 as where the protagonist's trade is first stated
(*"Signed, clerk of the Assize"*). Measured three ways on the same sentence: a plain `str.split`
puts `clerk` at **802** and `Assize` at **805**; `domain/axes`' tokeniser — which drops a token
that is nothing but edge punctuation once it is stripped — puts `Assize` at **804**. So the
document's number is the tokeniser's index of `Assize`, the independent re-derivation's 802 is a
plain split's index of `clerk`, and neither is wrong. A reader comparing two offsets has to know
which convention each was taken under; `named_persons.py` reports the tokeniser offset and its
docstring says so, and `test_an_offset_indexes_the_tokeniser_and_not_a_naive_split` pins the
distinction so it cannot quietly be forgotten.

## 5. Anti-scope

No axis admitted, no bar declared, no directive issued, no pole assigned, nothing registered in
`domain/axes.COUNTERS`. The one code change in the package is a behaviour-preserving extraction —
`axes.proper_noun_introductions` returns what `opening_proper_noun_names` returned plus the
offsets, and `test_the_named_offsets_are_the_opening_names_with_positions` pins that the names are
unchanged, because this counter's numbers are quoted in stage-0 §87. `plan/serial-pilot-4-craft.json`
carries the proposed chapter-grain constraint **outside** its `directives` array with `N` unset,
so no script can issue it and the operator's act is what fills the number in.

Raw output: [`results/named-persons-local.json`](results/named-persons-local.json),
[`results/named-persons-royalroad.json`](results/named-persons-royalroad.json).
