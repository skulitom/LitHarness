# The draw battery — what the code-only instruments say about every accepted chapter 1

**Operator diagnostics, commissioned in [`serial-pilot-18.md`](../serial-pilot-18.md) §6
(read 13: *"debug and measure impact of all of our internal agents"*).** §95's sanctioned
channel. **No bar is declared, no axis is admitted, no research claim is promoted, and no new
metric is minted** — `BRIEF.md` governs, and every counter below is imported from where it
already lives. The two quantities with no instrument in the repo are marked **REIMPLEMENTED**
and **NOT-AN-INSTRUMENT** and say so in every row they touch.

**No model read anything.** Regex and arithmetic over text, end to end. No corpus was opened, so
RS1 is untouched.

**There is no conclusions section, deliberately.** This document reports what moved and what did
not; the coordinator synthesises.

Runner: [`scripts/draw_battery.py`](scripts/draw_battery.py), re-runnable, writes
[`scripts/battery.json`](scripts/battery.json).

    uv run python plan/agent-impact/scripts/draw_battery.py --context \
        --out plan/agent-impact/scripts/battery.json

---

## 0. The standing boundary, before any column is read

Every column below is **one draw of one book**. Between any two of them the writer, the seed, the
world, the system, the ladder and the cast all moved, and several rule changes landed at once.
The two same-listing families in §4 are the nearest thing here to a controlled column and they
are still not one — [`serial-pilot-15b.md`](../serial-pilot-15b.md) §0 states the boundary for
the sharpest of them, and it governs this whole document:

> "It is still two draws. The seed is a fresh draw of a different world (a different system, a
> different ladder, a different cast), and nothing here holds anything constant except the words
> on the listing."

So: **descriptions of chapters, never effects of components.** Where a number sits beside
another it is a description of two books (§0 of `serial-pilot-7.md`, and the standing boundary).

---

## 1. Component liveness — which entries were on `main` when each draw's chapter drafted

Every cell is taken from the pilot record's own statement, cited. Nothing here is inferred from
commit dates. `—` is *not on `main` at draft time*; **`live`** is the record saying so.

| draw | book | writer | §154/§155 | §157 | §158/§159 | §160–§163 | §165–§167 | §168 | §169–§171 | §172 | §173–§177 | §178–§183 | §184 | §185/§186 |
| --- | --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| **p14** | *Unlicensed Weather* | larkin | **live** | — | — | — | — | — | — | — | — | — | — | — |
| **p15-d1** | *What the Kettle Remembers* 1 | penhale | **live** | **live** | **live** | **live** | — | — | — | — | — | — | — | — |
| **p15-d2** | *…Kettle…* 2 | penhale | **live** | **live** | **live** | **live** | **live** | — | — | — | — | — | — | — |
| **p15-d3** | *…Kettle…* 3 | penhale | **live** | **live** | **live** | **live** | **live** | **live** | — | — | — | — | — | — |
| **p15-d4** | *…Kettle…* 4 | penhale | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | — | — | — | — |
| **p16** | *Reading The Ladder Wrong* | ferreira | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | — | — | — |
| **p18-d2** | *The Station Keeps Score* 2 | sandoval | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | — | — |
| **p18-d3** | *…Station…* 3 | sandoval | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** | **live** |
| *p12* | *Patch Notes for the Apocalypse* | — | — | — | — | — | — | — | — | — | — | — | — | — |
| *p13* | *The Rainwright's Apprentice…* | larkin | — | — | — | — | — | — | — | — | — | — | — | — |

**The citation for each first-live cell:**

- **§154/§155 at p14** — pilot 14 header: *"the first drawn after the genre floor and its
  scheduled progression beats (stage-0 §155) and the three re-signed opening clauses (§154)"*.
- **§157 at p15-d1** — pilot 15 §1: *"`--scenes 6`, deliberately, because §157's fix makes six
  work and this run is its first live test."* §157 is the fix filed **from** pilot 14 §3, so it
  is `—` at p14 by that record's own account (pilot 14 §10 files it as owed).
- **§158/§159 at p15-d1** — pilot 14 §10 records both as *"Paid, same day"*, i.e. after that
  draw; pilot 15 §3 walks §158's declare→accept path live.
- **§160–§163 at p15-d1** — pilot 15 header: *"the first book produced under the complete
  first-principles redesign (stage-0 §§160–163, merged at `1931dfe`)"*.
- **§165–§167 at p15-d2** — pilot 15b header: *"Three entries landed against that draw — §165 …
  §166 … §167 … This draw is the first live test of all three"*.
- **§168 at p15-d3** — pilot 15b, iteration 3: *"§168's passage-unit clause riding every scene
  call for the first time."*
- **§169–§171 at p15-d4** — pilot 15b, iteration 4: *"draw 4 under §168–§171 together"*.
- **§172 at p15-d4** — pilot 15b §7's closing note lands the slug fix; pilot 18 §5 observes it
  live (*"§172's suffixed slug doing its job"*). Infrastructure, not a prose rule.
- **§173–§177 at p16** — pilot 16 header: read 10 *"commissioned … §173–§177"*; §2 calls the
  listing *"the first listing drawn under §174's prior-life prohibition"*; §4 records
  *"§175's bound, held"*.
- **§178–§183 at p18-d2** — pilot 18 §3: *"first draw under §183's floor"*, and
  *"§178's machinery_names came back empty"*.
- **§184 at p18-d3** — pilot 18 §3 routes §184 **from** p18-d2's failure, so it is `—` there;
  §5 records p18-d3's scene 1 *"REFUSED three times by §184's gate (`progression_unmoved`)"*.
- **§185/§186 at p18-d3** — pilot 18 §5: *"before §186 existed"*, then reissued
  *"with §186's moved-line render"*; the run's cost includes *"every reviser call"* (§185).

**One entry the pilot records do not place: §164.** No pilot record names it, so it is given no
column rather than guessed at. **p12 and p13 are context columns** — pre-redesign, drawn before
any entry in this table, included because they were two more file reads.

---

## 2. The battery — draw × instrument

**Rates are per 1,000 *prose* words.** `prose words` drops the `[STATUS]` furniture lines and the
`* * *` scene separator, using `draft._SYSTEM_LINE` — the pipeline's own definition of a system
line, the same boundary `strip_em_dash` uses to protect them.

**What that separation is worth, measured rather than assumed.** It is large for two counters and
negligible for a third. **Em dashes:** the `[STATUS]` line's own subject separator is U+2014, so
p15-d4, p18-d2 and p18-d3 each scored 2 on the raw file with **no em dash anywhere in their
prose**. **Proper nouns:** capitalised sheet labels are read as names, and p15-d4 falls from 31
distinct to 25 once the furniture is dropped, p16 from 21 to 18. **Sentence length:** a status
line carries no terminal punctuation and folds into its neighbour, but on this shelf that moves
the sentence count by at most one (p15-d1 140 → 139, p15-d3 141 → 140) and changes **no**
chapter's longest sentence — p15-d2's 98-word maximum is a real prose sentence, which is the
check that corrected an earlier draft of this note.

| instrument | p12 | p13 | p14 | p15-d1 | p15-d2 | p15-d3 | p15-d4 | p16 | p18-d2 | p18-d3 |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| **words** (file) | 1928 | 1997 | 2016 | 2029 | 1969 | 1984 | 1906 | 2020 | 1971 | 1970 |
| **words** (prose) | 1925 | 1994 | 2013 | 1992 | 1932 | 1947 | 1861 | 1965 | 1878 | 1939 |
| *sentence stats* | | | | | | | | | | |
| sentences | 121 | 150 | 151 | 139 | 130 | 140 | 141 | 155 | 141 | **178** |
| mean words/sentence | 15.86 | 13.31 | 13.36 | 14.35 | 14.83 | 13.89 | 13.23 | 12.62 | 13.32 | **10.90** |
| median words/sentence | 8 | 7.5 | 8 | 8 | 9 | 7 | 7 | 6 | 8 | 8 |
| share over 30 words | 19.8% | 13.3% | 12.6% | 15.1% | 12.3% | 18.6% | 11.3% | 12.3% | 12.8% | **4.5%** |
| longest sentence | 74 | 53 | 60 | 58 | **98** | 50 | 58 | 64 | 62 | 55 |
| *chains (REIMPLEMENTED)* | | | | | | | | | | |
| joins/sentence, mean | 1.55 | 1.43 | 1.50 | 1.87 | 1.58 | 1.53 | 1.70 | 1.36 | 1.27 | **0.88** |
| share with 4+ joins | 19.0% | 20.7% | 16.6% | 23.7% | 15.4% | 17.9% | 20.6% | 13.6% | 12.8% | **3.9%** |
| count with 6+ joins | 11 | 6 | 6 | 12 | 10 | 8 | 15 | 8 | 6 | **1** |
| *em dashes* | | | | | | | | | | |
| in prose | 9 | 11 | 4 | 1 | 5 | 3 | **0** | **14** | **0** | **0** |
| on `[STATUS]` lines | 0 | 0 | 0 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| prose per 1k | 4.68 | 5.52 | 1.99 | 0.50 | 2.59 | 1.54 | 0.00 | 7.12 | 0.00 | 0.00 |
| *register census (gloss)* | | | | | | | | | | |
| tier A1 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |
| tier A2 | 3 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 |
| **tier A** total | **4** | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 1 |
| tier B | 1 | 0 | 0 | 0 | 0 | 3 | 1 | 1 | 1 | 2 |
| *number context* | | | | | | | | | | |
| mentions per 1k | 23.90 | 22.07 | 22.36 | 12.55 | 9.83 | 14.38 | 9.14 | 15.78 | 17.57 | 11.35 |
| `mundane_core` per 1k | 1.04 | 6.02 | 5.46 | 3.51 | 1.55 | 4.11 | **0.00** | 2.55 | 1.07 | 0.52 |
| `calendar_duration` | 2 | 5 | 8 | 6 | 2 | 7 | **0** | 5 | **0** | **0** |
| `system_any` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| *page contract* | | | | | | | | | | |
| `[STATUS]` lines | 0 | 0 | **0** | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| subject | — | — | — | `mira` | `Mira Kell` | `tam_cawl` | `Mira Kell` | `Theo` | `the board` | `Ines` |
| subject is a raw id | — | — | — | **yes** | no | **yes** | no | no | n/a¹ | no |
| a number moves across the prints | — | — | — | **no** | yes | yes² | yes | **no** | **no** | **no**³ |
| *schema leak (§178)* | | | | | | | | | | |
| machinery words as prose names | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **1** (`ladder`) | 0 | 0 |
| *proper nouns (NOT CAST)* | | | | | | | | | | |
| distinct | 10 | 15 | 13 | 17 | 17 | 16 | 25 | 18 | **5** | 11 |
| distinct per 1k | 5.19 | 7.52 | 6.46 | 8.53 | 8.80 | 8.22 | 13.43 | 9.16 | **2.66** | 5.67 |

¹ `the board` carries no capital, so the raw-id heuristic flags it, but it is a lowercase
**display name for the station's own board** — not a machine id. It is worth its own line for a
different reason: it is the only draw whose printed sheet belongs to **no person at all**.

² p15-d3's move is `tam_cawl:Work in hand 0/1→1/1` — the apprentice, not the protagonist. Pilot
15b, iteration 3, defect 2 names this: *"The protagonist's sheet never renders, and no
protagonist number moves."*

³ p18-d3's two prints are byte-identical (`Rating 3 | Graded 9 | Written 1/12 | Warmth 6/6`), so
this counter reads **no**. Pilot 18 §5 records why, and it is not the §184 failure: the rung-up
*"prints on the page"* at the **first** sheet, and *"the SECOND sheet print teaches the grading
rule by not moving"*. The move landed before the first print, where a two-print counter cannot
see it. **This counter cannot distinguish that case from p18-d2's**, which is the §184 failure
proper (*"the sheet prints `cold seal 2` at both moves"*), and it is reported here as the same
`no` for both. A counter that could tell them apart would need the entering state, which is
`§184`'s own object and not this document's.

---

## 3. Instruments that could not run, or ran and detected nothing

Flagged rather than forced, per the ask.

### 3.1 `progression_cadence` runs on one chapter and locates **zero events in all ten** — its furniture detector does not recognise our page contract

`progression_cadence.locate` / `.measure` accept a single chapter string (the CLI does not — it
takes `materialise | census | selftest` over the RoyalRoad shards only, so the module functions
were called directly with the five metadata scalars filled in as dummies). It runs without
error. It returns `events=0`, `per_1k=0.0` and `first_event_words=None` on **every draw
including both context columns**, so `median_gap` and `gap_cv` are `None` throughout — those two
need ≥2 and ≥3 events, and the instrument declines rather than returning a zero.

**The mechanism, established from the code and confirmed against a live line.** On
`[STATUS] Ines — Rating 3 | Graded 9 | Written 1/12 | Warmth 6/6`, `_is_furniture` returns
`False`. The three shapes it accepts are a whole-line bracketed span (`_RE_BRACKETED`:
`^\**\[[^\]]{1,200}\]\**[.!?]?$`), an angled span, or a **colon**-separated stat line
(`_RE_STATLINE`). Our house format is none of the three — the bracket closes after `STATUS` and
text follows, and the columns carry no colon.

**So the zero is a property of the instrument's calibration, not of the chapters.** Every
post-§160 draw has two furniture lines on the page; the market-derived detector sees none. The
`furniture_detected_by_market_instruments` field records `0` against `actually_present: 2` on
every such row so the zero can never be read as an absence.

### 3.2 `number_context`'s system families fire **once in ten chapters**, for the same reason

`number_context.measure(text)` takes a bare string and runs cleanly. But it copied
`is_furniture_line` from `progression_cadence` deliberately (`line_shapes_copied_deliberately`),
so it inherits §3.1's blind spot: `furniture_lines` is `0` on every draw, and `system_any` is
`0` everywhere except p12's single hit.

**And before the prose/system separation this actively contaminated the mundane half.** Run over
the raw file, the sheet's own values fall through to the ordinary prose families —
`family_of` classifies the line above as `[('3','object_count'), ('9','object_count'),
('1','unanchored'), ('12','object_count'), ('6','unanchored'), ('6','unanchored')]`. p18-d2's
nine-column sheet printed twice was inflating `object_count` from 12 to 28. **The system/mundane
split in §2 is therefore measured on prose only, and the system half of this instrument should
be read as unavailable on our shelf rather than as zero.**

### 3.3 `register_census`'s friction half cannot run per chapter; the gloss half can

`gloss_counts(text)` is str-only and is what §2 reports. **`friction` and `bigram_friction`
cannot run here**: both require a corpus frequency table (`friction(text, table, *, total=…)`)
and there is no per-chapter form. The census driver (`register_census_run.py`) takes no chapter
path at all — its inputs are hardcoded to the parquet intermediate and the whole shelf, and it
needs the MirrorBench interpreter. Not run: this is a diagnostics pass, and one sustained job at
a time on this box.

### 3.4 §180's own chain counter does not exist — §2's row is a REIMPLEMENTATION

§180.1 records that its census ran with *"a crude script that is not kept"*, and
`tests/test_sentence_structure.py` confirms no number of it lives in the repo. What shipped was a
prompt clause only. §2's `joins` rows transcribe §180.1's stated definition — *"sentences split
on terminal punctuation, and per sentence a count of coordinated joins (commas plus
free-standing *and*)"* — with §180.3's fourth-action bound, splitting via `voice.sentences` so
only the per-sentence join count is new. **The absolute levels are therefore not comparable with
§180.1's published distribution**; only the columns of this table are comparable with each other.

### 3.5 There is no named-character counter — the proper-noun row is a superset

§175 shipped a prompt bound and `domain/staging.py` says in its own docstring that no count of
drafted prose was built (*"No count of anything in drafted prose, no census, no gate"*). The
reused `register_census.proper_nouns` is a strict superset: it also catches places, institutions
and system nouns, and its majority-capitalised rule still admits sentence-initial artefacts
(`you`, `if`, `because`, `neither` all appear in the returned sets). **It is reported as proper
nouns and never as cast size.** The pilot records' own hand counts are the cast numbers and are
a different source: p16 *"Exactly three named people on the page"* (§4), p18-d2 *"cast bound
(3 named per scene)"* (§3), p15-d4 *"five named present characters plus four named offstage"*
(read 10).

### 3.6 Two counters have no instrument at all

§179 (negative-space tell) and §181 (plain diction) both shipped as prompt clauses with **no
detector, by design** — `tests/test_plain_diction.py` states it outright, and §181 is keyed on
provenance rather than rarity precisely because §156.3 measured our rare-word rate as inside the
genre's range. Nothing in §2 covers either family. Pilot 18 §3's hand count
(*"~8 not-X constructions"*) is a read, not an instrument.

---

## 4. The two same-listing families — the nearest-to-controlled columns

**The boundary first, and it is not a formality.** Both families hold the *listing* constant and
nothing else. Each draw re-seeds a fresh world with a different system, ladder and cast, and in
the kettle family several rule changes land per iteration.
[`serial-pilot-15b.md`](../serial-pilot-15b.md) §0 is the governing text — *"nothing here holds
anything constant except the words on the listing"* — and calls its own temptation *"the
sharpest any pilot has offered"*. **These are descriptions of four books and two books
respectively, never effects.**

### 4.1 *What the Kettle Remembers* — draws 1 → 2 → 3 → 4 (penhale, one listing)

| | d1 | d2 | d3 | d4 | what was added |
| --- | --: | --: | --: | --: | --- |
| entries newly live | §160–§163 | §165–§167 | §168 | §169–§172 | |
| prose words | 1992 | 1932 | 1947 | 1861 | |
| mean words/sentence | 14.35 | 14.83 | 13.89 | 13.23 | |
| share over 30 words | 15.1% | 12.3% | 18.6% | 11.3% | |
| joins/sentence | 1.87 | 1.58 | 1.53 | 1.70 | |
| share 4+ joins | 23.7% | 15.4% | 17.9% | 20.6% | |
| em dashes in prose | 1 | 5 | 3 | 0 | no rule against them until §180 |
| gloss tier A | 0 | 1 | 1 | 1 | |
| gloss tier B | 0 | 0 | 3 | 1 | |
| `mundane_core`/1k | 3.51 | 1.55 | 4.11 | 0.00 | |
| `calendar_duration` | 6 | 2 | 7 | 0 | |
| `[STATUS]` subject | `mira` | `Mira Kell` | `tam_cawl` | `Mira Kell` | §169 lands at d4 |
| number moves | no | yes | yes (apprentice) | yes | §170 lands at d4 |

**Sentence structure does not move monotonically across this family** — the share over 30 words
goes 15.1 → 12.3 → **18.6** → 11.3, and the 4+ join share goes 23.7 → 15.4 → **17.9 → 20.6**,
rising over the last two draws. The page-contract rows do move as the entries land: d3's raw id
`tam_cawl` is §169's own instance, and d4 prints a display name at the protagonist's own move.

### 4.2 *The Station Keeps Score* — draws 2 → 3 (sandoval, one listing)

| | d2 | d3 | what was added |
| --- | --: | --: | --- |
| entries newly live | §178–§183 | §184, §185, §186 | the reviser and the beat gate |
| prose words | 1878 | 1939 | |
| sentences | 141 | **178** | |
| mean words/sentence | 13.32 | **10.90** | |
| share over 30 words | 12.8% | **4.5%** | |
| joins/sentence | 1.27 | **0.88** | |
| share 4+ joins | 12.8% | **3.9%** | |
| count with 6+ joins | 6 | **1** | |
| em dashes in prose | 0 | 0 | already 0 under §180.4 |
| gloss tier A / B | 0 / 1 | 1 / 2 | |
| `mundane_core`/1k | 1.07 | 0.52 | |
| `[STATUS]` subject | `the board` | `Ines` | |
| number moves across prints | no | no (see §2 note 3) | |

**This is the largest single-step movement anywhere in the battery**, and it is on the sentence
axis alone: more sentences over slightly more prose, each markedly shorter and less chained. The
gloss counts move the other way (tier A 0 → 1, tier B 1 → 2), and the page-contract rows are
unchanged by these counters. §0's boundary applies undiminished — the seed, world, system and
cast are all fresh between these two columns, and three entries landed together.

---

## 5. Where every number comes from

| number | source |
| --- | --- |
| words | `len(text.split())`, the pipeline's own idiom (`application/export.py:57`) |
| prose words, em-dash split | `draft._SYSTEM_LINE` and the `* * *` separator, dropped |
| sentences, mean, median, over-30 | `voice.sentences` + `voice._WORD` |
| joins, 4+/6+ shares | REIMPLEMENTED from §180.1's stated definition (§3.4) |
| em dashes | `voice.exhibition_census` |
| gloss tiers A1/A2/B | `register_census.gloss_counts` |
| mentions, families, `mundane_core`, `system_any` | `number_context.measure` |
| progression events | `progression_cadence.measure` (returns 0 on all ten — §3.1) |
| `[STATUS]` lines, subjects, moves | `application.statusline.parse_status_line` |
| machinery words as names | `domain.schema_words.named_in` |
| proper nouns | `register_census.proper_nouns` (NOT cast size — §3.5) |
| component liveness | the pilot records, cited line by line in §1 |
| chapter word counts in the records | pilot 14 §6, 15 §9, 15b §9 and iterations 3–4, 16 §1, 18 §3 and §5 |

**The file word counts differ from some pilot records by up to 3.** The records report the
store's per-scene sums; the file carries the published `* * *` separator, which is three
whitespace tokens. Every rate in §2 uses the prose denominator, which excludes it on all ten
rows, so the comparison across columns is unaffected.

---

## 6. Anti-scope

No bar is declared, and the four attainability checks were not run because nothing here is a
bar. No threshold is proposed over any quantity. Nothing admits an axis or promotes a research
claim under `EPISTEMIC_GOVERNANCE.md`; agent prose is not evidence. **No stage-0 number is
claimed** — nothing shipped because of this document. No model ranked, selected or judged
anything, and no corpus was read, so RS1 is untouched. Nothing in this file is read by any
generation surface, and nothing under `src/litharness/` imports the runner. Nothing the operator
said about any of these books became prompt text (§97.1).
