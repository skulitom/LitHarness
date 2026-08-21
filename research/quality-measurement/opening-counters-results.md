# `opening_proper_nouns`: the anchor, the distribution, and what it does not show

**Status: MEASUREMENT, 2026-08-21. No bar is declared here, nothing is admitted to the axis
registry, and no directive was authored.** Per `plan/reader-read-2.md`, a counter enters the
registry by an operator act over a measured distribution. This is the distribution. The
admission, if there is one, is the operator's.

Nothing in this work feeds a prompt, a directive, or any generation path. The counter is
registered in `axes.COUNTERS` and deliberately absent from `axes.AXES`, so `counts()` — which
the off-target check and the feedback loop read — cannot see it. `test_the_counter_is_not_an_axis`
pins that.

## The headline, stated first because it is not the flattering one

**Reappraisal chapter 1 scores 8, which is the 68.5th percentile of published LitRPG chapter
openings.** Nearly a third of RoyalRoad's LitRPG chapters open with *more* named things than the
chapter a reader complained about. The counter is deterministic, it recovers the names the human
pointed at, and on this evidence **it does not discriminate the defect that was named.**

That is a real finding rather than a failure to get one. Either the reader's objection is not
about the count — density and timing are the obvious alternatives, and "nine names before
anything happens" is a different claim from "nine names" — or the population is not the right
comparison because published LitRPG openings are not what this project is trying to match.
Both readings are live. Neither is settled by anything measured here.

## 1. The acceptance anchor

The read hand-counted the proper nouns on Reappraisal's first page and listed nine. Run against
the published chapter, the counter returns **eight**. Seven are shared.

| the read named | the counter | note |
|---|---|---|
| Weigh Street | ✅ | |
| Marta | ✅ | |
| Vance | ✅ | |
| the Kelling ledger | ✅ `Kelling` | the counter names the proper part, not the phrase |
| Hesk Turrow | ✅ | one name, not two |
| Bellow and Sons | ✅ | one name, not three |
| the Vessil workshop | ✅ `Vessil` | |
| **the Corvessa assay house** | ❌ **not in the text** | `Corvessa` first occurs at word **1212**. The prose says "the assay house". The human read the premise into the page. |
| **the crown-and-hook mark** | ❌ missed | present at word 261 and **lowercase** in the prose. No capitalisation rule can see it. |
| — | ➕ `Silas` | the counter finds him; the read did not list him |

**Recovery: 7 of the 8 findable items.** One of the two disagreements is the counter's limit and
one is the human's error, and it matters which is which:

- **`crown-and-hook` is the counter's floor.** A name the prose never capitalises is invisible to
  a rule built on capitalisation, and no amount of tuning changes that without a tagger.
- **`Corvessa` is the read's floor**, and the more interesting one. The name is in the premise,
  in the scene plan and in the book's title-adjacent furniture, so a reader who has seen those
  remembers meeting it. The counter reads only the page. **A hand-count is not ground truth**;
  it is one more instrument with its own failure mode, and this is the first time in this
  project that a human read has been checked against a deterministic one and found wrong about
  a specific item.

`Silas` is neither party's error, just a judgement difference: he is a proper noun introduced on
the page, and he is also the viewpoint character the premise already named. Counted here because
the counter reads the page and the page introduces him.

## 2. What was not built, and why

**The second nomination — three-noun stacks per 1k words — is blocked.** It needs a POS tagger to
tell a noun stack from an adjective run, and neither venv has one:

| venv | spacy | nltk | stanza | flair |
|---|---|---|---|---|
| `C:/DEV/LitHarness/.venv` | absent | absent | absent | absent |
| `C:/DEV/MirrorBench/.venv` | absent | absent | absent | — |

The brief forbids adding a heavyweight dependency for it, so it is recorded as blocked and
skipped. A regex approximation was considered and rejected: "assay house door" and "cold iron
gate" are the same shape to a pattern that cannot tell a noun from an adjective, so the counter
would measure something other than the thing named and report it under the name of the thing
named.

## 3. Distributions

Window: the first **300 words** — the operator's own figure, kept rather than tuned.

### RoyalRoad chapter openings (the baseline)

`corpus_io.royalroad_chapters`, `min_words=300`, read under the MirrorBench venv.

| population | n | mean | sd | p5 | p10 | p25 | **p50** | p75 | p90 | p95 | max |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| all genres | 2000 | 6.90 | 4.09 | 2 | 3 | 4 | **6** | 9 | 12 | 14 | 42 |
| LitRPG-tagged | 2000 | 7.51 | 5.12 | 2 | 3 | 4 | **6** | 10 | 14 | 17 | 42 |

The two populations share a median and differ in the upper tail: LitRPG's p95 is 17 against 14.
A genre that opens on a status screen and a party roster has more names to spend, which is the
direction one would guess and is worth recording as measured rather than guessed.

### Own-generated books

| text | count | percentile (all) | percentile (LitRPG) |
|---|--:|--:|--:|
| **Reappraisal ch. 1** (the chapter the read judged) | **8** | 73.0 | **68.5** |
| Reappraisal ch. 2 | 5 | 40.6 | 39.5 |
| The Toll Road, per-scene median | 6 | 53.8 | — |

The Toll Road's ten scene openings: `6, 5, 3, 7, 5, 9, 6, 3, 8, 8` (mean 6.0, sd 1.95). These are
*scene* openings and a scene is internal structure, so they are secondary colour only — the unit
a reader receives is the chapter, and the comparison that carries weight is the chapter row.

## 4. What the counter is, mechanically

Deterministic, pure standard library, no model call, total over any input. Four rules earned
their place by fixing a measured false positive on the anchor text:

1. **All-caps tokens are excluded.** The first page carries a chalked fee schedule — `WEIGHT &
   PURITY, ONE MARK` — and a capitalisation-only rule read seven proper nouns off a price list.
2. **A sentence-initial capital counts only if the book writes it mid-sentence somewhere.**
   English capitalises every sentence's first word, so `Inside` and `Marta` are identical at
   position zero. An earlier version also accepted one whose *next* token was capitalised, on
   the theory that "Weigh Street" announces itself — it does, and so does "Ask Vance", and
   chapter 2 duly reported a person by that name.
3. **Punctuation blocks a merge.** `"Signet," Turrow said` is two things; without the boundary
   the counter reported a person called Signet Turrow.
4. **Markdown emphasis and interrupted dialogue end sentences.** A scene break written `* * *`
   and a question broken off and closed both left the next word looking mid-sentence, which
   promoted `The`, `He` and `Ask` to proper nouns.

Known residuals, unfixed and named: `Skill` and `Tuesday` are counted in chapter 2. A game term
and a weekday are proper nouns by capitalisation and arguably by grammar; whether a reader
"remembers" them the way they remember Marta is exactly the question a counter cannot answer.

## 5. Draft registration paragraph

*For the operator to move into the stage-0 ledger, edit, or discard. It claims no § number,
declares no bar, and admits nothing.*

> **`opening_proper_nouns`, nominated and not admitted.** The 2026-08-21 read named "too many
> names right at the start" as one of five prose defects. A deterministic counter for it now
> exists in `domain/axes.py` — distinct proper nouns introduced in the first 300 words — and is
> registered in `COUNTERS` while deliberately absent from `AXES`, so it carries no pole and
> reaches no packet. Against the read's own hand-count it recovers 7 of the 8 findable items,
> missing a lowercase compound and correcting the read on one item that is not in the text.
> Measured over 2,000 RoyalRoad chapter openings the population is median 6 (LitRPG p75 10, p90
> 14, p95 17); **Reappraisal chapter 1 scores 8, the 68.5th percentile**, so the chapter a reader
> objected to is unremarkable by this measure and a bar set at its value would flag roughly a
> third of published LitRPG. Admission is therefore not recommended on this evidence alone: what
> the counter measures is real, deterministic and apparently not the thing the reader minded.
> The obvious next question — whether the complaint is about *when* names arrive rather than how
> many — is not answered here and would need a different counter and a second read to license.
