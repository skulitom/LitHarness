# Paired reconstruction: pilot result (2026-11-09)

Protocol and bars: [PROTOCOL.md](PROTOCOL.md), committed before any rewrite was scored. Chat model:
`claude:claude-opus-5-5:medium` (the project agent, Codex, was at its usage limit). Local model: `gemma3:12b` in raw
mode. No corpus text appears here.

## Result

No arm passes any bar, and the no-training route as tested here is closed by the declared rule: none of B, C, D is
closer to the genre than plain instruction.

| Arm | Best-view AUC | Interval | d' | Pairs | Length vs real |
| --- | --- | --- | --- | --- | --- |
| A: chat model, outline and one-line instruction | 1.000 | 1.000 to 1.000 | 4.38 | 59 | 1.14 |
| B: A plus three real openings | 0.999 | 0.997 to 1.000 | 4.58 | 59 | 1.10 |
| C: local model continuing a plain document | 1.000 | 0.998 to 1.000 | 3.72 | 59 | 0.68 |
| D: C repaired by the chat model | 0.995 | 0.983 to 1.000 | 3.20 | 59 | 0.72 |

Bars: cannot be told from the genre at or below 0.663; within the genre's own variation at or below 0.677; closer
than instruction when the interval lies wholly below A's (1.000 to 1.000). Every arm's interval reaches 1.000.
Every rewrite scored as more "rewritten" than its own real twin in every arm (pair wins 1.0).

By d', C and D sit a little nearer the genre than A and B, but still more than three standard deviations away.

## Guards

- Copying from the examples (8-word runs): 0 in every arm.
- Copying from the unseen twin (8-word runs): at most 5.7% (A), 6.1% (B), 8.2% (C), 7.9% (D), from names, stats
  and System text carried by the outline.
- Outline names covered: 82% (A), 81% (B), 83% (C), 87% (D).
- One target has no outline (two draws copied 16% of the opening against the 12% limit), so every arm has 59 of 60
  pairs. One C draft needed a second run after stopping short.

## After the fact (not declared in the protocol)

`python diagnose.py`. With real and rewritten cut to the same length, the AUCs are unchanged (1.000, 0.999, 0.998,
0.995), so C's short drafts are not what separates them.

Style counts that differ most, real against rewritten (means over the 59 pairs):

| Count | Real | A | B | C |
| --- | --- | --- | --- | --- |
| Median sentence, words | 11.4 | 7.3 | 6.2 | 8.9 |
| Sentences of four words or fewer | 20% | 31% | 37% | n/a |
| Median paragraph, words | 35 | 20 | 16 | n/a |
| Paragraphs of 60 words or more | 23% | 9% | 6% | 3% |
| Commas per 1,000 words | 58.6 | n/a | n/a | 82.0 |

("n/a": not among that arm's ten largest gaps.)

- The chat model writes shorter sentences and far shorter paragraphs than the genre does. Showing it three real
  openings (B) made this stronger, not weaker.
- The local model fails differently: more commas, a wider vocabulary, longer words, almost no long paragraphs.
  The repair (D) changes little.
- Style counts alone separate A at 0.964, so most of the gap is visible in shape before any wording is considered.
  Common-word rates alone separate A at 1.000.

## Limits

- One chat model at one effort, one local model that is chat-tuned and not a true base model, 59 pairs.
- A classifier at 1.000 cannot rank how far off an arm is; d' does that only roughly.
- Nothing here measures whether a reader would enjoy an opening.

## What it does and does not close

Closed: prompting a chat model with an outline, with or without real openings in context, and a chat-tuned local
model continuing real openings. Not closed: a true base model (none is installed), and any writer that is steered by
this score instead of only measured by it. The second stage (invented outlines) is not run, since no arm passed.
