# What the §185 reviser does to text: the pairs it was measured from do not exist, the comma chains are cut to a third, the subordination it was asked for did not arrive, and it costs more than the writer

**Operator diagnostics for the attribution report commissioned at read 13**
(`plan/serial-pilot-18.md` §6). Not research, not a claim, not a bar.

## §0. The boundary, stated before the numbers

- **One book, one writer, one chapter.** Everything below is `sandoval` writing *The Station
  Keeps Score* from one settled listing, twice: draw 2 (`serial18b.db`, book `2e14015e`, no
  reviser) and draw 3 (`serial18c.db`, book `435c41f9`, reviser on). Two scenes each.
- **No treatment claim, and the two draws are not an experiment.** Between them landed §184's
  beat gate, §186's moved-line render, a `replan` to plan epoch 1, and a fresh Architect seed
  with its own world. The writer's `policy_config_digest` differs across the two stores
  (`627399d1…` on draw 3, `9eb96d9a…` on draw 2) and carries **more than** the reviser key. A
  difference in any column below is a description of two pages, never an effect of one stage.
- **No bar is declared and no quantity here judges prose.** Every counter is a plain count.
  BRIEF.md governs; nothing here is promoted, registered, or offered as evidence.
- **`--no-revise` is the control that would settle this** (§185.8) and it has never been drawn.
  Until it is, the reviser's effect on a page is not separable from the draw it rode in on.

## 1. The first finding: there are no draft/revision pairs, anywhere, by construction

**The brief for this column assumed the stores hold the pairs. They do not, and cannot.** Three
reads, each on its own:

1. `application/handlers.py::revise_draft` runs on the provider's string and returns **one**
   string. `commit_revision` stores that one. The draft the writer returned is a local variable
   that is rebound (`result = replace(result, text=revised)`) and never persisted.
2. The reviser's own decision row (`revision.containment.v0`) carries provider, model, profile,
   invocations, tokens, cost, and the containment verdict — **and no text**. Verified on all
   five rows in `serial18c.db`. `ManuscriptCandidateCreated` carries vetoes and finding ids,
   also no text. `ManuscriptRevisionAccepted` carries `chars`, `em_dashes_removed` and
   `revised_by`, also no text.
3. `providers/cli.py` passes `--no-session-persistence` on every `claude -p` call, so no
   provider-side transcript survives either. Checked empirically: zero session JSONLs under
   `C:\Users\artem\.claude\projects\C--DEV-LitHarness\` in the 15:50–17:00 run window.

**So the diff summary the brief asked for cannot be computed for any scene, ever, and no
per-pair "most-changed sentence" exists to quote.** The substitutions used below are named where
they are used.

**The only surviving quantitative fact about a draft is a bound.** Containment held at ratio ∈
[0.85, 1.20], so from the revision's own stored word count the writer's draft lay in:

| scene | revision words (store) | draft words, bounded |
|---|--:|---|
| scene-1 | 1,036 | 863 – 1,219 |
| scene-2 | 931 | 776 – 1,095 |

Approximate: the store's word count is the shape gate's, on canonicalized text, while the ratio
containment applied is `str.split()` on the raw pre-strip strings. Nothing else about either
draft survives — not a sentence, not a length, not a hash.

**This is an attribution hole and it is the report's own subject.** The stage that now writes
every sentence the book ships is the one stage whose input is not recorded. §185.8 named four
things the stage invalidates and this is a fifth: **a clause's effect at the drafting call is no
longer merely hard to read off an accepted scene — the draft that would settle it is destroyed.**

Only `serial18c.db` holds reviser rows: a byte scan of all 26 stores in
`runs/pilots/databases/` for `revision.containment.v0` returns 14 occurrences, all in that file.

## 2. Containment: five calls, zero discards

Read from `policy_decisions` in `serial18c.db`.

| | count |
|---|--:|
| reviser calls made | **5** |
| containment held, revision adopted | **5** (100%) |
| containment breached, draft stood | **0** (0%) |
| adopted, then the gate ladder refused the text anyway | **3** |

No `EMPTY`, `MACHINE_LINE_CHANGED`, `INTRODUCED`, `LENGTH_MOVED` or `UNCHANGED` breach has ever
been recorded in production. **The discard rate is 0/5.** Both accepted scenes carry
`revised_by: claude-opus-5`, so **100% of the prose on draw 3's page is the reviser's string**;
draw 2's two acceptances carry `revised_by: null`.

**The three wasted calls are structural, not bad luck.** The reviser runs *in front of* the gate
ladder, so a refused attempt has already paid for a rewrite. All three refusals on job
`beat-775aee13…` were `progression_unmoved`, and §185.3 records that containment forces the
machine lines byte-identical **so that gate's verdict cannot change**. Those three revisions were
therefore incapable of altering the outcome they were paid for, by the design's own argument.

## 3. Spend: the reviser costs more than the writer

Every row from `serial18c.db`'s `policy_decisions`; `profile` separates the two callers exactly
as §185.7 intended, with no join needed.

| job | attempt | writer (`default`) | reviser (`reviser.scene.v0`) | ladder outcome |
|---|--:|---|---|---|
| `beat-775aee13…` | 1 | $0.3781 / 56,709 tok | $0.3055 / 54,271 tok | retry `progression_unmoved` |
| `beat-775aee13…` | 2 | $0.3426 / 55,291 | $0.5050 / 62,310 | retry `progression_unmoved` |
| `beat-775aee13…` | 3 | $0.4017 / 57,653 | $0.3051 / 54,251 | park (poisoned) |
| `beat-2fa7437d…` scene-1 | 1 | $0.3708 / 56,426 | $0.5174 / 62,840 | **accept** |
| `beat-fda00f49…` scene-2 | 1 | $0.4032 / 58,888 | $0.4348 / 60,684 | **accept** |
| **total** | | **$1.8964 / 284,967** | **$2.0678 / 294,356** | |

- **The reviser is 109.0% of the writer's cost and 103.3% of its tokens.** Its per-call input is
  the scene *plus* the packet the scene was written from, which is why a rewrite is not cheaper
  than a draft.
- **Per shipped scene: $1.034** (all five calls ÷ two accepted scenes), or **$0.476** counting
  only the two calls whose text reached the page.
- **$1.1156 — 54.0% of all reviser spend on this chapter — bought text the ladder then
  refused.** With the ordering as it is, a chapter's reviser bill scales with *attempts*, not
  with scenes.
- Reconciliation with `status`: architect seed $4.1403 + writer $1.8964 + reviser $2.0678 =
  **$8.1045**, which is §5's "$8.10 on the store". Draw 2's drafting was $0.7967 for two scenes
  and had no second call at all.

## 4. The page: plain counts, draw 2 (writer) beside draw 3 (reviser)

Measured by `plan/agent-impact/scripts/reviser_impact.py`
(`script_sha256` ~~`919fc07c55a79b0dc18a7f8c76b41bf12ea4e7ecf887921e4dba5c645f2c06da`~~
**`d244748120504167b229007de70deb6c77bbf2bcaf2def0eb7abff1aa4f2c4a7`** — corrected
2026-08-30: the script was brought under the repository's ruff gate the way
`research/quality-measurement/` already is (two `# noqa` annotations, `strict=` on two
equal-by-construction `zip`s, `itertools.pairwise` for the adjacent-openings pair walk, and
two word-list literals re-wrapped, splitting to the same lists). No counter definition
changed; the numbers in this file are the struck version's output) over
`litharness export` text. Unit text digests: draw 2 `3374e5ac73cfbe25` / `1496777913d7ac66`;
draw 3 `9fb25ab7d4506a39` / `eecc812468f71848`.

The shelf column quotes **§180.1**, which owns those numbers; they are pointed at here for the
comparison and are not restated as a second home.

| | draw 2 s1 | draw 2 s2 | **draw 2 pooled** | draw 3 s1 | draw 3 s2 | **draw 3 pooled** | §180.1 shelf |
|---|--:|--:|--:|--:|--:|--:|--:|
| prose words | 919 | 959 | **1,878** | 1,023 | 918 | **1,941** | — |
| paragraphs | 31 | 32 | **63** | 43 | 42 | **85** | — |
| words / paragraph | 29.6 | 30.0 | **29.8** | 23.8 | 21.9 | **22.8** | — |
| sentences | 72 | 69 | **141** | 87 | 91 | **178** | 3,810 |
| mean sentence words | 12.76 | 13.90 | **13.32** | 11.76 | 10.09 | **10.91** | — |
| median sentence words | 8.0 | 9 | — | 9 | 7 | — | 6 |
| p90 sentence words | 32.4 | 34.0 | — | 25.0 | 23.0 | — | 29 |
| longest sentence | 62 | 61 | **62** | 55 | 37 | **55** | 86 |
| share > 30 words | 11.1% | 14.5% | **12.8%** | 4.6% | 4.4% | **4.5%** | 9.2% |
| share 0 joins | 52.8% | 46.4% | **49.6%** | 47.1% | 56.0% | **51.7%** | 53% |
| **share ≥ 4 joins** | 11.1% | 14.5% | **12.8%** | 4.6% | 3.3% | **3.9%** | 12.4% |
| **share ≥ 6 joins** | 4.2% | 4.3% | **4.3%** | 1.1% | 0.0% | **0.6%** | 4.4% |
| most joins in one sentence | 9 | 9 | **9** | 6 | 4 | **6** | — |
| **subordinators / 100 words** | 1.088 | 0.938 | **1.012** | 0.978 | 1.198 | **1.082** | — |
| adjacent same opening / 100 sent | 11.11 | 11.59 | **11.35** | 6.90 | 2.20 | **4.49** | — |
| distinct sentence openings | 35 | 31 | — | 44 | 46 | — | — |
| **verbless narratorial fragments** | 3 | 2 | **5** | 0 | 0 | **0** | — |
| **em dashes, pre-strip** | 2 | 0 | **2** | 0 | 0 | **0** | 1.79 / 1k words |
| §156 tier A (A1+A2) | 0 | 0 | **0** | 1 | 0 | **1** | — |
| §156 tier B | 0 | 1 | **1** | 0 | 2 | **2** | — |

### What the reviser measurably changes

1. **It breaks the chain.** Sentences carrying four or more coordinated joins fall from 12.8% to
   3.9%, and six or more from 4.3% to 0.6%. The writer's page sits **on** §180.1's ten-book
   shelf (12.4% and 4.4%); the reviser's page sits well below its tail. Longest chain 9 → 6.
2. **It shortens.** Mean sentence 13.32 → 10.91 words, p90 34/32 → 25/23, share past thirty
   words 12.8% → 4.5%. The scene stays the same length (1,878 → 1,941 words), so this is the
   same material cut into 178 sentences instead of 141.
3. **It splits paragraphs.** 63 → 85 paragraphs, 29.8 → 22.8 words each.
4. **It varies openings.** Adjacent sentences beginning with the same word: 11.35 → 4.49 per 100
   sentences; distinct openings 35/31 → 44/46. This is the reviser's third craft clause, and it
   is the one where its second scene is furthest from the writer's page (2.20 vs 11.59).
5. **It removes verbless fragments outright.** Five narratorial ones on the writer's page
   (mechanically flagged, hand-read: dialogue fragments excluded), zero on the reviser's. §5's
   "zero verbless fragments" is confirmed at source.
6. **It does not reach for the em dash.** `em_dashes_removed` on the acceptance events: the
   writer reached for it twice in 1,878 words, the reviser zero times in 1,941. §185.8's item 2
   — the counter has changed subject — is now measured rather than predicted.

### What it leaves alone, and what it makes worse

7. **Subordination does not move: 1.012 → 1.082 per 100 words.** This is the sharpest result in
   the table. The reviser's first craft clause asks for the relation between two happenings to
   be *said*, and §5 read the result as "subordinate connectives throughout" — but the rate of
   the seven connectives is flat. What changed is which ones: the writer leans on
   `while` (6) and `since` (4); the reviser on `when` (7) and `before` (6). **On this chapter
   the reviser answered the chained sentence by cutting it in two, not by subordinating it.**
   (Counted as bare tokens; `when`/`before`/`after`/`since`/`until` are prepositions as often as
   subordinators, so this is a density of the word, not of the construction.)
8. **The §156 gloss counter goes up, not down.** `register_census.gloss_counts`
   (`registration_digest 2029fc350b1e6684`, unedited, imported by path): 1 hit on the writer's
   1,878 words (0.53 / 1k), 3 on the reviser's 1,941 (1.55 / 1k) — and two of the reviser's three
   are the same sentence matched twice, so by **glossed sentences** it is 1 against 2, or 0.53
   against 1.03 per 1k. The tier-A hit is **read 13's own first item**, quoted in §5. The counter
   that exists for that defect family fires more often on reviser prose than on writer prose from
   the same listing. n = 4 units; a description, and at these counts a difference of one
   sentence.
9. **Long sentences survive where they are one thing described.** The reviser's longest surviving
   sentence is 55 words with six joins — §180.3's concession ("length spent on one thing
   happening is not that") holding on the page.
10. **Nothing structural changes and nothing can.** Containment forbids it, and the store shows
    it: identical machine lines, no introduced names or numbers, and §184's verdict provably
    unchanged.

The §156 **friction** half (unigram and bigram rarity) is not run: it needs the market frequency
table, which is the corpus side, and the gloss half needs nothing. The gloss tiers are the only
part of that module that runs on arbitrary text.

## 5. Illustrations, verbatim

**The brief asked for the three most-changed and three least-changed sentences per pair. No pair
exists (§1), so no such sentence can be identified.** Substituted, and the substitution is the
diagnostic: the sentences each page's *own* worst case produces on the counter the reviser's
first craft clause is aimed at, plus every hit of the §156 gloss counter.

### The writer's three heaviest chains (draw 2, no reviser) — the shape the stage exists for

> "The metal did what the corridor plate had not: it went thin under her attention, thin the way
> ice is thin where the current runs beneath it, and she knew, not guessed, knew, the way you
> know your own arm is asleep, how far the thin place ran, and that it had less time left than
> her watch was going to have." *(9 joins, 62 words — scene 1)*

> "He held the transmit key down long enough for the holding of it to be an argument, and then he
> pulled his earpiece and held it out to Ines, and she put it in and heard the yard's call come
> back into her own ear, patient, unbroken, going out over everything she had just tried to put
> on top of it." *(9 joins, 61 words — scene 2)*

> "The splice she had done on the ring frame's aft loom, the one she was proud of, was there and
> graded, one line under the soup, in the same column, worth about as much." *(6 joins, 34 words
> — scene 1)*

### The reviser's three heaviest chains (draw 3) — what the stage left standing

> "It did not move the way a plate moves when you drive heat into it, shoving and buckling and
> going where it wants; it came together slowly and from both edges at once, the way a cut closes
> over a week, except that it took about as long as it takes to lose an argument." *(6 joins, 55
> words — scene 1)*

> "Her bare palm went onto the panel beside it, which stayed cold and printed no writing, and
> after a while she noticed she was waiting for the warmth the way you wait for a kettle."
> *(4 joins, 35 words — scene 2)*

> "He was at the wall with his hand flat on it, no panel under his palm, just plate, and his head
> was tipped over like a man listening at a door for whether the room is occupied." *(4 joins, 37
> words — scene 2)*

The pairing to notice: the reviser's worst case is a long sentence with a **semicolon and a
subordinating "except that"**; the writer's worst case is a comma queue. The two heaviest
reviser sentences that are *not* built that way are both "the way you \<verb\>" comparisons —
which is the next block.

### Every §156 gloss hit, both pages

Draw 3, scene 1 (tier A1, narration offset 336) — **read 13's first item**:

> "She said it the way she said most things, as though somebody had asked her twice."

Draw 3, scene 2 (tier B, narration offsets 273 and 318) — **both hits are one sentence**, so the
counter's two are one place on the page:

> "He held the bar across his chest with both arms, the way you hold a thing you have been given
> so you have something to hold."

Draw 2, scene 2 (tier B, narration offset 4142):

> "The keeper said it without any weight on it, the way you say a distance."

**Read by sentences rather than by hits, the gap narrows and does not close: two glossed
sentences on the reviser's page (1.03 / 1k words) against one on the writer's (0.53 / 1k).**
Both readings are reported because tier B fires per matched shape, not per sentence.

### The verbless narratorial fragments the reviser's page does not contain

All five are on the writer's page; the reviser's page has none.

> "Not the way she wrote it." · "Air going." · "Slower than the tear." *(draw 2, scene 1)*

> "Eleven, beside Marta's name." · "Not slowly." *(draw 2, scene 2)*

## 6. What this cannot say, and what would settle it

- **It cannot say the reviser improved or harmed the chapter.** No mechanism in this repository
  may order two texts by quality; that is BRIEF.md's whole subject. Every row in §4 is a count.
- **It cannot attribute any row to the stage.** Two draws, four scenes, one writer, and at least
  four other things changed between them. §7 and §8 are the two rows an operator would most want
  to be effects, and they are exactly as confounded as §1 to §6.
- **The one thing it can attribute is authorship.** Every sentence draw 3 ships was produced by
  the reviser call, so read 13's three items are on reviser prose by construction — which is a
  fact about who wrote the page, not evidence that the stage caused them.
- **What would settle it, cheaply:** one `--no-revise` scene drawn beside a revised one from the
  same beat and the same epoch — §185.8's own recommendation, held back and never drawn.
- **What would settle it permanently:** persisting the draft. The drafting call's own prompt is
  frozen at enqueue and readable forever (§103); the reviser's input is built inside the handler,
  sent, and dropped — so the one text that would answer "what did this stage change" is the one
  text nothing keeps. No amount of later measurement recovers a scene already written. That is a
  build decision and this report does not make one.

## Reproducing

```bash
uv run python plan/agent-impact/scripts/reviser_impact.py \
  --store draw2-no-reviser=<abs path>/runs/pilots/databases/serial18b.db \
  --store draw3-reviser=<abs path>/runs/pilots/databases/serial18c.db \
  --json <somewhere>/reviser-impact.json
```

The script shells out to the `debug-book` verbs (`export`, `events`) for everything they can
answer. It opens a **copy** of the store read-only for one thing they cannot: `why --scene N`
scopes `attempts` to the accepting job, so the three reviser calls on the job that was poisoned
before `replan` reissued its beat — 54% of this chapter's reviser spend — are reachable through
no verb. The script's docstring records that, and the copy is deleted after the read.

Counter definitions live in the script. Two are re-derivations rather than reuses and say so:
§180.1's join count (that entry records its own script "is not kept"), and the verbless-fragment
flag, which over-flags without a parser and whose numbers in §4 are the hand-read ones.
