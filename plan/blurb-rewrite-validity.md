# Blurb-rewrite validity — the reader writes, the code diffs, nobody judges

**Status: REGISTRATION, 2026-08-26.** Written before any call. This is handoff task 1
(`plan/handoff-reader-perception.md`): make the reader *produce* rather than *judge*. The
hypothesis: a model's generative fluency is reliable where its critical judgment is blind — it
will rarely write "a patch of notes" even though it cannot reliably flag one — so a silent
repair in a rewrite locates an off phrase, and an echo does not.
`research/quality-measurement/blurb_rewrite.py` carries the frozen bytes and every registered
definition.

## 0. Why this can live where verdicts died

Six probes asked a model whether phrasing was idiomatic and came back blind or inverted
(boundary 5). This instrument asks no such question. The reader is given a listing and one of
that listing's sentences and asked to **write that sentence as it would be written**. Nothing
is rated, ranked, ordered or compared; there is no schema, because the reply is a sentence, not
a record; the reply is consumed by deterministic scorers and reaches nothing else. That is the
produce frame, not the judge frame, and the diff is computed in code so no model ever reports
on itself (§143's lesson applied at span level).

## 1. The frozen ask

System (byte-frozen):

> You write listings for serial fiction on this market. Reply with a single sentence and nothing
> else.

Prompt template (byte-frozen), per sentence k of a listing:

> {title}
>
> {listing}
> ---
> Sentence {k} of this listing:
> {sentence}
>
> Write that sentence as it would be written in a listing in this market.

The reader is **never told anything is wrong**, never told to fix, improve or polish. The words
fix/improve/polish/wrong/judge/quality appear nowhere in either byte string. Requests carry
`max_output_tokens=256`, no schema, profile `reader.rewrite.v0`, call class `generation` — the
measurement-request conventions of `listing_arena.py`. **K = 4 draws per sentence** (§124's
one-draw lesson, inherited from anticipation).

Inputs: `--pool derived/<file>.json` rows read exactly as `blurb_gradient` reads them (HIGH then
LOW; its `matched_pairs` is imported, never duplicated); `--texts` accepts whatever
`listing_arena.load_texts` accepts (imported).

## 2. The measurables, all scored by code

- **`sentences(text)`** — split on `.!?` followed by whitespace. Deliberately naive: abbreviation
  false-splits ("Mr. Wu") stay false-splits, and an ellipsis touching the next word splits.
  Blurbs are 40-146 words; simplicity beats cleverness, and the limitation is registered rather
  than patched.
- **`normalise(reply)`** — collapse whitespace, strip surrounding quotes, drop a leading
  "Sentence k:" echo if the model parroted the prompt's framing.
- **`span_diff(original, rewrite)`** — lowercase word tokens, `difflib.SequenceMatcher`;
  `change_rate = 1 − (matched original tokens / original tokens)`; changed spans are the
  original-side token offsets of replace/delete opcodes.
- **Stable repairs** — original-side token positions covered by a changed span in ≥ 3 of the 4
  draws, merged across overlapping spans into one located diagnostic. Below threshold is
  paraphrase jitter, not a finding.
- Per listing: the mean of the sentences' mean change rates, plus the stable-repair list.

## 3. The four kills, readings fixed before any call

Directions plus reported distributions, **no bars** — §61's attainability discipline; a null on
every kill is a result.

- **KF — fixed point.** Draw 1's rewrite of each sentence is fed back through the same ask —
  its own listing context updated with the rewrite, and the REWRITE presented as sentence k —
  and round 2 is scored against **the rewrite it was asked to write**, by the same scorer.
  Direction: round-2 change_rate (rewrite → rewrite-of-rewrite) materially below round-1
  (original → rewrite) on the same texts; reported as paired per-sentence distributions and
  the share of sentences where round 2 sits below round 1. If round 2 does not fall, the diff
  is paraphrase noise rather than repair and the instrument is dead. *(Amended before any
  call: the first draft scored round 2 against the original sentence, which cannot fall even
  when the instrument works — asking about the original again and diffing against the
  original reproduces round 1 by construction. The fixed point being tested is the rewrite's.)*
- **Transport failures are excluded, never scored.** A failed call is a fact about the day
  (`transport_failures`, the standing rule): a draw that returned nothing is dropped from
  every rate — an empty reply diffed against the original would score as maximal repair —
  and each sentence row records its `failed_draws`. A run's verdict is unreadable until its
  failure count has been read.
- **KG — the gradient.** On blurb_gradient's length-matched pairs: LOW listings must show
  HIGHER change_rate than their HIGH partners. Statistic: the share of pairs with
  change_rate(LOW) > change_rate(HIGH), with a seeded pair-bootstrap interval over the same
  pairs. Reported as share + interval; ambiguity is reported as ambiguity, never rounded to
  the nearest story.
- **KL — length.** Pearson's r between sentence change_rate and sentence token length,
  reported whatever its size; a strong dependence is named in the results, because a gradient
  that is really word count has been seen here before (§141's reason for matching by length).
- **KP — draw reliability.** Mean pairwise Jaccard agreement of the K draws' changed-span sets,
  within sentence, reported against the between-sentence contrast in the gate-0 shape:
  reliability without the between contrast is the trap a constant scorer passes perfectly.

## 4. The §141 gradient is validation the instrument must pass first

The one separation anyone has achieved on these blurbs is the readership separating a
12,448-follower serial from a 0-follower one at H = 0.935, length matched. The handoff's rule
is adopted whole: **nothing this instrument says about our own listings is believed before KG
separates.** Until LOW sits clearly above HIGH with the interval excluding coin-flip, every
number this instrument produces about ours is unreadable — reported as machinery output, never
as a reading.

## 5. The final leg: ours against the market, anchors included

Run only after KG separates. The acceptance test, in the operator's words (2026-08-26): *"we
need agent LLM readers to score our generated text near 0 and RR titles much better."* On this
instrument that orientation is **inverted by design**: the score is repair needed, so higher
change_rate means worse writing. Our listings (`--texts`, the anchor set of
`plan/anchor-set.md` included) are run against market listings, and the pass is **ours showing
markedly HIGHER repair than the market's** — our listings near the bottom of the distribution
and the market's top clearly above. That direction is the one every model-judgment probe to
date has inverted (handoff boundary 3), which is why it is written here before any call:
**ours-above-market means the instrument is withdrawn, not that our listings are good.**

## 6. Prose, and what is deliberately out of scope

- **Results carry no third-party prose.** Pool-sourced rows store digests, token offsets and
  counts only — enforced in code (`allow_prose=False` is the default and pool rows never pass
  it); full text rows go to `derived/`, which `.gitignore` covers. Span TEXT may be stored only
  for our own listings (`--texts`).
- **Nothing here feeds a prompt** (§97.1). The scorers' output is a report beside a listing at
  most; no drafting, revision or planning path reads it.
- **No verdict vocabulary anywhere a model can reach.** The frozen ask contains none; the
  replies are prose consumed by code; nothing rates anything.
- **The instrument's verdict on our own listings is unreadable until KG separates** (§4).

## 7. Amendment: execution-side reader selection (cross-family leg, 2026-08-26)

Nothing above moves. The frozen ask, the request conventions, K, the scorers, the four kills
and every reading are unchanged; what is new is an execution-side parameter, `--reader`:
`registry` (the default — the run described above, byte for byte) or `ollama:<model>` (e.g.
`ollama:qwen3:14b`), carried by `research/quality-measurement/reader_transport.py`. The
motivation, in one line: a claude-written listing read by a model with no stake in claude's
habits attacks self-familiarity directly (`plan/reader-architecture-program.md`,
cross-family row).

The discipline does not move either. A cross-family leg validates on §141's follower gradient
before its reading of our listings is believed — and its numbers are **never pooled with
another reader's**: enforced by construction rather than care, since every run writes one
file, that file carries a single `reader` block (`{"transport", "model"}`) written once at
the top, and a non-default reader suffixes the default `--out` filename (e.g.
`blurb-rewrite-qwen3-14b.json`, with the derived/-side text dump following the same stem) so
a cross-family run cannot overwrite a registry run. The local transport keeps elicit.py's
replay-cache discipline — requests keyed on the text digest of system+prompt+model plus the
draw index, JSONL beside the results file — so the K draws per sentence stay K draws of one
distribution under any reader.
