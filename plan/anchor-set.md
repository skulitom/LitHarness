# The anchor set: operator-named works, and the citation each one has to carry

**Status 2026-08-20: incomplete and deliberately so.** This is the metadata half of §7.1 —
option (1) of the two the operator was offered, and the one that settles *admissibility* without
moving a single byte of prose. No anchor text has been acquired. Acquisition is option (2) and is
a separate operator decision that has not been taken.

Stage-0 §97 owns the programme; §0.3 owns the rule this file exists to satisfy:

> Operator-named works are admissible calibration corpora **iff** they are population-consensus
> summits (the named set's popularity is checkable), and they live on the measurement side only.

**Why the citation is not a formality.** The rule is `iff`, and the whole generalization objective
(§97.1) rests on it. A named set admitted without checking would make the calibration target the
operator's taste rather than the population's, which is precisely what §97.1 forbids. "Titles I
really enjoyed" and "population-consensus summits" are different claims that happen to overlap;
this file is where the overlap is established one work at a time.

---

## 1. The bar, declared before the table is complete

**A summit is a work in the top 0.1% of its platform's fictions by follower count.**

Stated as a *distributional* property rather than an absolute number, deliberately: an absolute
threshold chosen after seeing the named works' figures would be a bar fitted to the answer, which
is the failure §89's rulebook exists to prevent. The percentile definition refers only to the
platform.

**Disclosure, because the ordering is not clean and pretending otherwise would be worse.** Four
of the figures below were already measured before this bar was written — two from the local corpus
and two from a web search that returned them unbidden. A reader should weigh the bar accordingly.
What protects it is that it is a percentile of a distribution nobody here controls, and that the
operator may replace it: **the bar is the operator's to set, and this is a proposal.**

For calibration, the local RoyalRoad sample (22,397 fictions) has p99 = 2,035 followers and
p99.9 = 8,136, maximum 18,718. RoyalRoad's full catalogue is several times that sample, so the
platform-wide 0.1% sits above the sample's own p99.9.

---

## 2. The named set

| # | work | followers | favorites | ratings | source | status |
|---|---|---|---|---|---|---|
| 1 | **The Primal Hunter** | **33,714** | 20,458 | 12,686 | [RR 36049](https://www.royalroad.com/fiction/36049/the-primal-hunter) | **VERIFIED SUMMIT** |
| 2 | **Defiance of the Fall** | **18,793** | 11,521 | 7,382 | [RR 24709](https://www.royalroad.com/fiction/24709/defiance-of-the-fall) | **VERIFIED SUMMIT** |
| 3 | **Paranoid Mage** | **17,850** | — | 5,899 | local corpus (as of scrape); 9,579,197 views | **VERIFIED SUMMIT** — second of 22,397 in the local sample |
| 4 | Mark of the Crijik | 3,586 | — | 1,097 | local corpus (as of scrape) | **ABOVE p99, BELOW BAR.** Also: 10,554 views against 3,586 followers is incoherent where Paranoid Mage runs 536 views per follower, so the row itself is suspect. Needs a live figure before any verdict |
| 5 | Chrysalis | pending | | | [RR 22518](https://www.royalroad.com/fiction/22518/chrysalis) | id located, stats not yet retrieved |
| 6 | All The Skills | pending | | | [RR 55687](https://www.royalroad.com/fiction/55687/all-the-skills-a-deckbuilding-litrpg) | id located, stats not yet retrieved |
| 7 | Mother of Learning | pending | | | RoyalRoad | the programme's fixed first anchor; **text already local** in `BookCrawler/data/mother-of-learning-20220313`, so it is the one work needing no acquisition |
| 8 | Portal to Nova Roma | pending | | | RoyalRoad | not yet located |
| 9 | Bog Standard Isekai | pending | | | RoyalRoad | not yet located |
| 10 | Blessed Time | pending | | | RoyalRoad | not yet located |
| 11 | The Mage of Shimmer Mountain | pending | | | RoyalRoad | not yet located |
| 12 | ~~Harry Potter~~ | n/a | | | not RoyalRoad | **EXCLUDED — see §3** |
| 13 | **The Legend of Randidly Ghosthound** | **14,275** | — | — | RR search card, read through the browser 2026-09-01 (725 chapters, 11,439,713 views) | **VERIFIED SUMMIT** — above the local sample's p99.9; operator-named 2026-09-01, chapter 1 and blurb on the shelf |
| 14 | The Gam3 | 5,404 | — | — | RR search card, read through the browser 2026-09-01 (STUB: 81 chapters remain, 3,772,714 views) | **ABOVE p99, BELOW BAR** on the stubbed figure; operator-named 2026-09-01, chapter 1 and blurb on the shelf. Admitted to the opening-parity manifest as an operator-named anchor with this status recorded beside it |

**Retrieval note.** RoyalRoad returns HTTP 403 to the fetcher, so figures come from search-result
summaries, which surface the stats panel only sometimes. Every row above is checkable by opening
the linked page; "pending" means *not yet retrieved*, never *not checkable*, and the rule §0.3
states is checkability.

---

## 3. Harry Potter is excluded, and not on its merits

Its population-consensus status is beyond argument and is not the issue. §1 of the directive
requires the mid-tier contrast corpus to be **same genre and era band, length-matched, and
population-labelled by the same story-grain metric**. Against a RoyalRoad mid-tier, none of the
three is constructible: different medium, different era, and no follower/view metric that means
the same thing. A summit that cannot be contrasted cannot enter a contrast-based mining step.

Admitting it anyway would put a traditionally-published children's fantasy of the 1990s into a
summit set otherwise made of 2020s web serials, and every "summit property" mined from that
contrast would be confounded with medium and era. It would need its own band with its own matched
contrast, which is a second programme.

---

## 4. What a wider set costs, recorded before it is paid

**Matching is per-anchor.** A summit spanning progression fantasy, LitRPG, dungeon-core, isekai
and time-loop cannot share one matched mid-tier corpus — §1's rule matches genre and era band to
*the anchor*. So the contrast download scales with the anchor count rather than being fixed, and
an eleven-work summit implies eleven matched contrasts.

That is a cost of generalising, not an objection to it. The operator's argument for the wider set
is on the record and stands: a taste function mined from ten summits generalises further than one
mined from three.

---

## 5. RS1, restated here because this is the file somebody will copy from

Anchor and contrast text may enter **measurement, mining, and validation**. It may never enter a
**drafting, revision, or planning prompt** — whole or in part, paraphrased or verbatim. Enforced
by provenance rather than by pattern: corpus digests are never referenced by any generation-side
module, checkable in CI.

Nothing in this file is text. It is titles, ids, counts and links, which is the whole point of
doing the metadata half first.
