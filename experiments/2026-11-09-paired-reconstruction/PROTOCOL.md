# Paired reconstruction (2026-11-09)

Written before any rewrite was scored. The baselines below were measured first, with no model calls, so the bars
could be checked for attainability before they were declared.

## Question

Which way of writing, if any, produces LitRPG openings that cannot be told from the genre's own, without training
a model and without anyone reading?

## Design

1. **Titles.** From the LitRPG titles of the genre corpus with a chapter 1 of at least 1,300 words (seed
   20261109): 60 targets (30 from 2021-22, 30 from 2024-25), 20 examples, 81 background. The unit is the opening:
   whole paragraphs of chapter 1 up to 1,200 words.
2. **Outline.** A chat model reduces each target and example opening to 15 to 30 numbered lines of content in
   flat words, plus narration person and tense. An outline is redrawn when more than 12% of its 5-word runs come
   from the opening. (First set at 3%, which the smoke batch showed is unattainable: names, stats and System
   text put 3 to 10% of runs in common. Raised before any rewrite was scored.)
3. **Writers.** Each sees the target's outline and never the target's opening.
   - **A** chat model, outline and a one-line instruction.
   - **B** chat model, the same plus three real openings (each after its outline) from the examples.
   - **C** a local model with no chat template, continuing a plain document of the same three outline-and-opening
     entries. In this pilot it is `gemma3:12b` in raw mode: chat-tuned weights, not a true base model.
   - **D** C's draft, repaired by the chat model against the outline and otherwise left alone.
4. **Score.** For each arm, a ridge classifier learns real against rewritten and is tested on titles it did not
   see (5 folds by title, 5 repeats). Three views: style counts, common-word rates, hashed character 3- and
   4-grams, plus all three together. The headline is the AUC of the best view; 0.5 means it cannot tell.
   Typography a reader cannot see is normalised on both sides first.
5. **Guards.** Longest-run copying from the examples and from the unseen twin (8-word runs), share of the
   outline's names that appear, and length against the real opening.

## Baselines (measured, no calls)

| Comparison | Best-view AUC |
| --- | --- |
| Real against real, 40 random halves of the 81 background titles | median 0.547, 95th percentile 0.663 |
| Real 2021-22 against real 2024-25 | 0.677, interval 0.559 to 0.795 |

Taking the best of four views lifts chance above 0.5; the null is computed the same way, so the bars include it.

## Bars, declared now

- **Cannot be told from the genre:** arm AUC at or below 0.663.
- **Within the genre's own variation:** arm AUC at or below 0.677, the era split.
- **Closer than instruction:** the arm's AUC interval lies wholly below arm A's.
- When AUCs are above 0.95 and cannot rank arms, the standardised gap between real and rewritten scores (d')
  ranks them instead.
- **Close the no-training route:** none of B, C, D is closer than instruction by this pilot. Because C uses
  chat-tuned weights, a C or D failure closes only the raw-mode proxy, not a true base model.

## What this cannot show

Passing means an opening is not recognisably outside the genre on these views. It does not show a reader would
enjoy it, and a classifier of this size can miss differences a reader would feel.

## Steering stage (arm E), declared after the pilot and before any E draft was scored

The pilot only measured writers. Arm E is steered by measurement.

- **Start.** Arm A's draft for the title.
- **Measure.** Three sweeps. In each, the scorer's ridge classifier learns the real openings of the 81 background
  titles (never targets or examples) against every draft so far of the *other* titles (5 folds), on style counts
  and on common-word rates. Person and tense counts are left out, since the outline fixes them.
- **Rewrite.** The chat model gets the outline, its latest draft, and what that classifier holds against the
  draft: up to 8 style counts as plain measurements with the published middle-half range, and up to 12 common
  words each that it over- and under-uses. After the third sweep one more cross-fitted classifier picks each
  title's least rewritten-looking draft of the four.
- **What steering never sees.** Any target's real opening, the title's own drafts when its classifier is
  trained, and the character n-gram view.
- **A first signal was dropped before any call.** Plain distance from the background's averages (mean absolute
  z-score) does not separate: arm A's drafts already sit nearer the average (median 0.72) than real titles do
  (0.75), because each real title is far from the average in its own way.
- **Test.** The same scoring as every arm: a fresh classifier trained on real against E's drafts, titles held
  out, all four views, same bars. Because the classifier is retrained on E's own drafts, matching the steered
  counts without reading like the genre does not pass. The character view, never steered, is reported on its own.
- **Bars.** Unchanged. In addition, E is *moving toward the genre* when its d' is below every pilot arm's (3.20)
  and its character-view AUC is below A's (1.000); otherwise steering by these counts is closed.

## Second stage, only if an arm passes

The passing writer invents outlines; invented outlines are scored against real ones the same way.
