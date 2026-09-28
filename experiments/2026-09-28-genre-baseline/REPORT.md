# Genre baseline: first report, serial `slot` chapters 1-3 (2026-09-28)

Frozen run: `genre_census.v1`, bench `d27ea9e57603`, manifest `b75ddeb5dfb0`, commit `a4217a81d440`
(`$LITHARNESS_HOME/serials/slot/baseline/20260928T005546Z.md`). A description of one serial, one draft line:
not a verdict on quality and not a claim about the system. The operator has not yet read these chapters.

## 1. Census (code only; our chapter N against 182 LitRPG titles' chapter N)

| | ch1 | ch2 | ch3 | genre p10 / p50 / p90 (ch1) |
|---|---|---|---|---|
| content families outside the 10-90% band (of 6) | 0 | 1 (dialogue turns) | 1 (dialogue turns) | 0 / 1 / 2 |
| System lines per 1k (chosen) | 19.7 (100th pct) | 6.3 (92nd) | 7.1 (93rd) | 0.0 / 0.0 / 4.9 |
| gains per 1k (chosen, loose) | 1.2 | 0.0 | 0.6 | 0.0 / 0.0 / 1.5 |
| speech turns per 1k | 15.5 (72nd) | 44.4 (99th) | 38.0 (97th) | 0.8 / 9.2 / 24.2 |
| words per paragraph (surface) | 8 (1st pct) | 8 (1st) | 7 (3rd) | 16 / 27 / 51 |
| median sentence, words (surface) | 6 (3rd pct) | 5 (1st) | 6 (4th) | 7 / 10 / 14 |
| chapter words (chosen) | 1,678 (22nd) | 1,600 (20th) | 1,553 (17th) | 1,265 / 2,350 / 4,296 |

The same code puts the incumbent's forty chapter 1s at a median of 1 content family out, and Lite's at 2.

**Book window, the first 4,831 words** (our chapters 1-3; a genre title's first 1-2 chapters): our first System
line at word 48 against a genre median of 1,502 (81 of 182 titles show none by word 4,831); our first gain at
word 444 against 2,105 (83 show none); gains in the window 4 against a median of 1 (80th percentile).

## 2. Opening beats pilot (10 seeded genre titles, two taggers each, agreement 58/66 = 0.88)

| beat | ours, word | genre median, word | genre titles with it in the window | earlier than ours |
|---|---|---|---|---|
| prior life shown | 6 (taggers: thin, in passing) | 145 | 7 agreed, 2 without | 1 |
| first System sign | 39 | 1,834 | 9 agreed | 0 |
| first threat | 585 | 1,870 | 8 agreed, 1 without | 1 |
| first gain | 366 | 2,995 | 7 agreed, 3 without | 0 |
| hero's edge | 1,005 | 2,448 | 6 agreed, 1 without, 3 split | 2 |
| first ally | 109 | 3,385 | 5 agreed, 3 without | 0 |

## 3. What it says, plainly

- **Content-wise, our chapters deliver the genre's opening beats in the genre's order, compressed**: everything
  the median genre title spreads over its first 2,000-3,500 words happens in our first 1,000. The previous
  life is shown in passing, not as a scene. This is the one content-level difference both instruments agree on.
- **On the families code can count reliably, we sit inside the genre's range.** Cast, dialogue share, numbers
  and exclamations are typical. Speech comes in many more, shorter turns in chapters 2-3.
- **The large gaps are surface and chosen**: paragraphs a third of the genre's length and sentences shorter
  than 97% of genre chapters (surface, not chosen); System furniture at the top of the genre's range and gains
  earlier than almost any title (the operator's recorded choices: early, regular progress and printed status).
- **What it cannot say**: whether any of this reads well; humour, stakes, scope and hook grip; anything about
  titles outside the cached 2021-22 and 2024-25 releases. The beat pilot is ten titles.

## 4. Next, only on the operator's go

The model beat inventory (PLAN section 4 bench, Design 3): a genre-derived codebook, one text per call, k=2 on
the genre and k=4 on ours, about 275 Codex calls (about 3M tokens) once, then about 12 calls per three chapters.
It sends genre chapters to Codex.
