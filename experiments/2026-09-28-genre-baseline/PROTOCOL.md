# Genre baseline: protocol (2026-09-28)

**Question.** How close are our chapters, content-wise, to LitRPG titles in the genre? The operator asked;
this is the bench PLAN section 4 reserves. It describes and never decides: no bar, no redraw, nothing it prints
reaches a model. The operator's read stays the only gate.

**Design.** Chosen by a three-design panel and two judges (scratch record; the choice, not a claim of quality):
a deterministic census now (`bench.py`, zero calls), a model beat inventory only on the operator's go, and no
pairwise ours-against-genre judging (E6 was validated on one passage's manipulations, never on two stories).

## Corpus (`extract.py`, run with the MirrorBench interpreter)

- Source: the cached RoyalRoad-1.61M shards (Hugging Face snapshot `0e4df3f2`, 12 of 47 shards: fiction ids
  39,972-53,605 and 99,280-115,393, first released 2021-22 and 2024-25). No famous title is cached. RoyalRoad
  is never scraped.
- TOP: tag LitRPG or Progression, 1,000+ followers, one fiction per author, not declared AI, no "stub" title, not
  one of the 26 ids quarantined by the incumbent's stage-0 150.1. Chapters 1-12 by title ordinals, else a clean
  release order (rejected: first number above 1, a gap, a later book). Chapters 1-3 need 300+ words and 10+
  paragraphs. Author notes and Patreon/Discord lines stripped first (407 lines). The primary reference is the
  182 LitRPG-tagged titles (90 from 2021-22, 91 from 2024-25, 1 other); 65 Progression-only titles are held.
- OFF-GENRE: 41 titles with 1,000+ followers and no LitRPG, Progression or GameLit tag, chapters 1-3, seeded.
- Text lives only in `$LITHARNESS_HOME/corpora/genre/<fiction_id>/chNN.txt` (288 titles, 2,942 chapters, 50 MB).
  `manifest.json` here holds ids, titles, strata, chapter ids, word counts and sha256, never text.

## Measures (`bench.py`, `genre_census.v1`)

The same `normalize()` and counters run on both halves in one process; our chapter N is placed only against
genre chapter N (p10/p50/p90, percentile, robust z, era gap, off-genre AUC, our sibling-draft band).

- Content families: furniture (System lines, displays, share, widest window), progression (gains, including a
  growing field), dialogue, cast, interior, violence, trade (trade words plus the runtime's money and admin
  lexicons), other (numbers, exclamations, time skips). Surface: length, paragraphing, sentences.
- Headline: content families outside p10-p90, against the leave-one-out count of the genre's own chapters.
- Chosen departures, printed and never counted: furniture (code-owned status lines), progression (early and
  regular progress), length (1,500-word posts).
- Loose, printed and never counted: see the audit below. Cast is unaudited. No tells placement: the incumbent's
  shelf ceilings do not reproduce under the port.

## Gates run before any number was shown

- **Precision audit** (`audit.py`; 20 located hits a half, seeded, judged per family by one reviewer each):
  furniture 20/20 ours, 20/20 genre; numbers 18/20, 16/20; violence 7/20, 17/20 (our "struck" fires on doors and
  hatches); progression 0/1, 10/20; trade 4/4, 13/20; interior 11/16, 15/20; skips none, 15/20. Under 0.8 on a
  half is loose.
- **Port check** (`port.json`) on the incumbent's own population (13,364 LitRPG chapters, 584 fictions,
  quarantine removed): gains per 1k median/p75/p90 0.00/1.32/3.66 against 155.1's 0.00/1.26/3.60; chapters
  without a gain 50.7% against 51.0%; a gain in the first 500 words 12.0% against 22.5% (the v1 first-gain rule
  does not count a bare display); any display in each story's three earliest chapters 36.8% against 202's 31%
  (an added `[TAG] text` shape and 1,525 against 1,386 chapters).
- **Format symmetry**: our curly quotes, italics and dash dividers measure the same as plain ASCII (a test).

## Beat pilot (free: session subagents, no Codex quota)

Six opening beats (prior life shown, first System sign, first threat, first gain, the hero's edge, first ally)
tagged by two independent readers each over the first 4,831 words (our chapters 1-3) of ours and 10 seeded
genre titles (42783, 51624, 40971, 44915, 45370 from 2021-22; 103454, 101789, 100617, 110645, 105092 from
2024-25). Paragraph numbers only; word offsets come from code. Agreement: both absent, or both present within
3 paragraphs. Windows and tags stay under `corpora/genre/pilot/`.

## Rerun

`python bench.py baseline SLUG` after every `next` batch; the genre side is cached per bench and manifest hash.
Reports: `$LITHARNESS_HOME/serials/SLUG/baseline/<utc>.md` and `.json`, with a last-run column.
