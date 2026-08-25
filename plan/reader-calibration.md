# Reader calibration: can this readership tell our listing from a published one?

**Registered 2026-08-26, before any call.** Nothing here has been run. The point of writing it
first is that every quantity, every reading and every kill condition below is fixed while the
answer is still unknown — which is the one property that separates this from the twenty entries
in `research/quality-measurement/BRIEF.md`.

## 0. Where this came from, and what it is not

The operator, 2026-08-26: *"We have a lot of overviews generated, each one of them worse than
any 4 star or more reviewed title, maybe we can tune the readers so they can spot quality by
pitting ours (bad) and real good reviews."*

**What is new here is a label.** §87–§89 killed preference elicitation three times and the
reason was always the same: there was no ground truth, so a reader preferring a side told us
about the reader. A published serial rated above four stars by hundreds of people carries an
external, behavioural, non-model answer — what a market did, not what anybody thinks. That is
the first labelled pair this project has ever had.

**It is a screen and not a score.** A readership that cannot pick the published book out of a
pair the operator reads as lopsided has no resolution, and every number it has produced is
empty — including the 4/4s in `plan/serial-pilot-7.md`. A readership that can has demonstrated
resolution on *this* contrast and nothing more. Neither outcome is a quality claim about any
book, and neither licenses a bar.

**It is not §1a.5's superiority bar** and must never be reported as one. That bar is a blinded,
position-swapped win rate against **matched** published prose, powered, with a comparator frame
(PLAN.md §1a.5, demoted to long-term by §126). This is the same shape run at n=8 against
unmatched competitors to find out whether the instrument works at all. If it passes, §1a.5 is
still unattempted.

## 1. The pairing

Built and in the tree as of 2026-08-26: `readers.render_pick_request`, `domain/rivals.py`,
`litharness listing --rivals <file>`.

- **Ours**: one listing the loop produced, with its title, exactly as a reader would meet it.
- **Theirs**: one row that cleared `rivals.admit` — rated **above 4.0**, in one of this
  readership's **genres**, and either more than 20 ratings or a score carrying two decimal
  places (the operator's proxy: *"an imprecise number like 4.36 implies a lot of views"*).
- **Blinded**: neither is labelled. The two appear as ONE and THE OTHER.
- **Position-swapped**: `rivals.ours_first` derives the order from content, so it varies across
  readers, replays identically, and is **recorded**. §89 clocked a verdict channel running
  4,676x position over text; `Pairing.ours_first_share` is reported beside every result.
- **Rotated**: `rivals.draw` gives each reader a different competitor, so one screen samples the
  market rather than one book.
- **`neither` is available**, so the floor is not manufactured at 50%.

## 2. What is measured, and the readings, fixed now

Let **W** = share of answered pairs choosing ours, over the 4 measurement readers × N listings.

| | reading |
| --- | --- |
| **K1 — no resolution** | W is within 0.10 of the `neither`-adjusted chance rate. The readership cannot separate our listings from published ones, and every continuation and start number this project holds is uninterpretable. **This is the expected outcome** and it is a result. |
| **K2 — resolution** | W is at least 0.15 below chance, i.e. the readership picks the published book. The instrument discriminates on this contrast. |
| **K3 — inverted** | W is at least 0.15 **above** chance: the readership prefers ours over published, rated books. The instrument is measuring something, and it is not what we would want it to. Louder than K1. |
| **K4 — position** | `ours_first_share` is outside 0.40–0.60, **or** W computed on ours-first pairs differs from W on theirs-first pairs by more than 0.15. The result is void whatever it said, because the pairing measured order. |

K4 is checked **first**. A void arm is not re-read.

**K4 is pooled across listings and is unattainable per listing, which was caught before the
run rather than after.** With 4 measurement readers a single listing's `ours_first_share` can
only be 0, 0.25, 0.5, 0.75 or 1 — three of those five values fail a 0.40–0.60 band by
construction, so applied per listing the check would void most arms for having four readers
rather than for measuring order. Observed immediately on a model-free smoke run: 0.75 on one
listing, which means nothing. At N = 8 the pooled denominator is 32 pairs and the band is
reachable.

This is the fourth instance of the failure `plan/stage-0-decisions.md` §81, §85, §87 and §89
each record — a declared quantity that could not do what it said — and the only reason it is
recorded here as a design note instead of there as an entry is that the arithmetic was done
before the calls were bought.

## 3. The two ways this becomes circular, and the rules against them

**Tuning to the answer.** *"Tune the readers so they can spot quality"* is the request, and
tuning reader wording until they produce the expected answer is fitting a rubric to its own
answers — the failure `platform_priors` names in its own module docstring. §77 measured persona
changes moving nothing while **one word of question change moved a rate ten points**, so the
question is the powerful knob and the easy one to overfit.

The rule: **the roster and the question are frozen for the first run.** If it lands on K1, any
change to either is declared in this file before the re-run, and the re-run reports **how many
variants were tried**. A variant count that goes unreported turns a screen into a search.

**Familiarity.** BRIEF §2 Pass 6 measured a scoring model's familiarity with published text
swinging a score further than real damage did. A K2 pass is therefore ambiguous between *the
readers can tell good from bad* and *the readers recognise a book they were trained on*, and
the ambiguity is not resolvable by looking at W.

The rule: **K2 licenses nothing until the familiarity leg runs.** The leg is the same pairing
against text the model provably has not memorised — `corpus_io.generated_scenes` is named in
CONTRIBUTING as the only un-memorised source this project has — or an explicit recognition
probe. Until then a K2 is reported as *"separates published from ours"* and never as
*"detects quality"*.

## 4. What it costs

4 measurement readers × N listings, one call each, plus the rival pool assembled by hand.
At N = 8 that is 32 calls, roughly $6 at the rates in `plan/serial-pilot-7.md`. The listings
must be ones that already exist — generating fresh ones to be judged would confound the
instrument's question with the writer's draw.

**The rival pool is an operator act and there is no automated path to one.** RS1 forbids the
package from referencing a corpus, so nothing in `src/` can go and fetch rated listings;
`--rivals` takes a JSON file a person assembled, and `rivals.admit_all` refuses the file if any
row does not clear the bar.

## 5. What may be concluded, in every case

Nothing about whether any book is good. Nothing about the writers, which §137 leaves without a
key. Nothing about a bar: no quantity here has been through §61's four attainability checks —
range at the real n, direction, independent unit, non-empty subgroup — and until it has, W is a
distribution and not a threshold.

What a pass buys is narrow and worth having: **permission to read the continuation and start
numbers as meaning something.** They currently mean nothing that has been established, and the
honest status of every 4/4 in `plan/serial-pilot-7.md` is that it was produced by an instrument
whose resolution is unmeasured.
