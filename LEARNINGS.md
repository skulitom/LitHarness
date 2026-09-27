# What the incumbent taught (2026-08-12 to 2026-09-27)

What not to buy again. [M] measured, [I] inferred; numbers describe, none is a bar. `§N` is an entry of
`plan/stage-0-decisions.md`; bare paths are at the tag `legacy/incumbent-2026-09-27`; `opening/` is
`experiments/2026-09-27-opening/`; `evidence/` is `experiments/2026-09-27-rebuild-plan/evidence/`. Read N
follows `plan/reader-read-N.md`; ledger entries mis-number some (recurrence map §1.1).

## 1. Lessons the design rests on

1. [M] Slowness was the call graph, not Python: of 16 chapter-stage calls (129,661 tokens), 8 were "OK" probes
   (27% of wall time), one outline planned 24 scenes to draft 4, and Python took ~11 s (evidence/pipeline.md).
2. [M] Lite's 2 calls (15,904 tokens) beat that chapter in both blinded orders, but on one pair, a same-family
   judge, a one-orientation damage control and a prompt-primed identical-text null (`opening/REPORT.md`).
3. [M] Our words become story, and the model adds money unasked: 4 of 5 failed read-21 draws had a located
   cause in our text (§263-§265, §267), read 20's rent line came from READER_LIFE (§262), yet draws 1, 2 and 4
   held money words no request contained (§266); Lite's hero was on probation (`opening/lite/plan.md:7`).
4. [M] Clauses are signed and lists are recited. Number tokens per 1k words in a listing: permission 47.2,
   none 29.4, prohibition 7.0, market 7.2 (§138). A six-pressure list became every arc: "water" 66/16/8
   mentions, "fight" 0 (§263). A checklist in the listing task gave a list-shaped listing (§261, read 20).
5. [M] Machinery fixed every family the reads stopped naming (14 refusals, $7.33, no false positive); in ten
   chapters no register clause moved a sentence metric; the operator ordered them out (§187, agent-impact).
6. [M] Fact packets become minutiae: facts were 65% of the scene-1 prompt (evidence/pipeline.md), and 23 of
   37 page-image facts shared a content-word bigram with the drafted page (§182).
7. [M] The sheet machinery (6,331 lines in nine modules; ~38 ledger sections, evidence/pipeline.md) mostly
   fixed its own defects; printed gains never reached the sheet reader (§234, §236). "Ranks are the numbers"
   stands (§113). A status that "came up randomly" was noise: the MC opens it and weighs options (read 10).
8. [M] The operator wants progress "as soon as possible" and "constant and regular" (after read 7;
   `plan/house-genre-constraint.md:71-84`). The market prints far less (section 6): a chosen departure.
9. [M] Hook fields (chapter-1 first use, threat and its reach, prize in pre-System words, System's look)
   reached the page per the coordinator's pilot-25 read (§198), not the operator's; read 20 failed the hook.
10. [M] Long books fail between chapters: the only currency was spent twice and a culled man came back (§242:
    arc 1, 24 scenes, 2h20m, $38). The operator on volume 1: "it looks to be a disaster" (memory, 09-07).
11. [M] Neither LLM gates nor simulated readers predict the operator: the coordinator's gate passed what reads
    9-13 and 20 failed, and at read 17 its hand read had praised 3 of the 9 items named (read 17 §1).
12. [M] Judges have measured failure modes: position, surface preference, saturation (sections 2 and 3).
13. [M] The regular AI tells ran 3-10x the shelf rate (§199). A located, counter-verified rewrite cut chained
    "and" from 6.0 to 1.0 per 1k in one scene (`plan/serial-pilot-25.md:230`) but can worsen what the counter
    cannot see ("like a bar of soap goes", §199.5). The reviser added glosses (agent-impact); dropped (§196).
14. [M] Transport isolation carries weight: from inside a repo, `claude -p` returned an untracked filename in
    1-2 of 5 calls and the path in about 2 of 5 (§258); CLAUDE.md leaked without the flags and `--bare`
    answered "Not logged in" (§109); the hardening drifted across 23 files (evidence/operations.md).
15. [M] Bloat regrows without an enforced limit: 530f40e's 34% cut of src regrew in 5.2 days. Deleting what
    advances no story (530f40e) removed 35,780 net lines; reference-counted pruning removed 1,037 (§214's five
    cuts). In 47 days src grew from 6k to 66k lines, tests to 96k, research code to 101k (evidence/bloat.md).
16. [M] Tests tied to prose and research slowed verification: the slowest (45-59 s) resolved symbols named in
    prose; ledger citations froze 410 test names; 119 test files (32,296 lines) loaded research code; a push
    took 10-14 minutes of CI; 9 of the last 20 runs were cancelled (evidence/operations.md).
17. [M] A side prototype dies: the 09-08 clean start was retired within a day, its transport ported into the
    incumbent (c69e5ad, +2,439 lines; 917ce1a), which grew through 177 commits in 18 days (evidence/lite.md).
    [I] So the rebuild replaces the incumbent instead of sitting beside it.
18. [M] Lite's REPORT advised keeping the incumbent until multi-chapter continuity is shown
    (`opening/REPORT.md:7-10`); the operator's wipe overrode it. The tag and archived draw 6 keep a baseline.

## 2. Dead instruments (BRIEF.md §2's 22 dead proxies are the 20 static ones, CDG and anticipation)

| Instrument | Why it died | Source |
|---|---|---|
| 20 static proxies | tricolon 0.629 vs pre-2023, undeclared 2025 at 0.606: it reads the year | BRIEF §2-3 |
| CDG, log-prob gain | detect AUC 0.5188; a rename sham moved it 2.0x the strongest degrader | §58 addendum |
| Pick-a-side verdicts | the verdict tracks the slot, not the text (section 3) | §89 |
| Persona panels, `readers` | saturated, and preferred surface to story order | §70, §195.5, §199.1 |
| Anticipation probe | arms spanned 0.0080 vs a 0.05 floor; placebo 0.0125 > destaking 0.0090 | §227 |
| Coordinator's prose gate | passed what reads 9-13 and 20 then failed | recurrence map §3.1; read 20 |
| Order recovery | did not split chapters the operator could not follow from sentence-level ones | §225 |

## 3. Judge bias and saturation

- Position: `gemma-3-4b-it` answered "A" on 106 of 106 passes (0.9998 positional against 0.000214 text), and
  Haiku's keep-reading pick was chose-A 0.6408 on 142, VOID (§89). RevisionBench: 43-65% positional (BRIEF.md
  §2). A panel took the first-shown copy 17 of 20 against its own source (§195.5).
- Report beats verdict: asked to name the single most salient difference (E6), the same Haiku cleared 40/40,
  30/32 and 18/36 against nulls of 0.21/0.36/0.26 and called the placebo identical (§89).
- Surface over story: a shuffled opening of ours beat The Primal Hunter 20/20, the ordered copy's rate
  (§195.5); our listings beat the market's best 15 of 16 and the operator's favourites 24 of 24 (§140, §143);
  five judges from four vendors preferred a told-not-shown repair at 0.92-1.00 (memory, latent taste).
- Saturation: keep-reading on 195 of 196 (§70); 6 of 8 sibling drafts scored 4 of 4, p = 1.000 (§134); readers
  carried on 4 of 4 on shuffled copies (§199.1). [I] A reader that can answer for free saturates.
- The draft is the unit of variance: five drafts of one prompt read 3, 4, 1, 4, 4 of 4 (§133, §134). A
  one-call located count: reliability 0.54, ceiling 0.73, 4 draws for 0.8 (comic-beats-results.md:18,261).
- Retry is rejection sampling: at a 0.5 pass rate, 3 draws pass 7 in 8 (BRIEF.md §6), so show "draw k of n".
- Lite's judge `gpt-6-astra` has no position-bias measurement beyond one swapped pair (evidence/lite.md). A
  bench runs both orders on every pair, damage included, a sibling null, k >= 4 drafts and >= 3 briefs.

## 4. The costed reader: the one mechanism that replicated

A reader that pays from an attention budget to keep reading gave a book a smaller share of its reads when its
paragraphs were shuffled than when intact or whitespace-reflowed (20 of our drafted books, four slots a
session, `claude-haiku-4-5` via `claude -p`, 180 sessions per arm). Intact minus shuffled: +0.1640 [+0.0881,
+0.2390], then +0.1890 [+0.0747, +0.2955] with the permutation redrawn (90% intervals); 180/180 scorable;
$49.78 and $50.35, 2h04 each (§230; `cost-that-bites/FINDINGS-v3.md:24-32`). [I] Its reader had to give
something up (BRIEF.md §3). Limits: a whole-book shuffle is the loudest damage; the slot-A lean ate three
quarters of v1 (§222); the 20-book shelf caps its power and it needs ~3,900 words a book; it meets arguably 1
of 10 qualification fields (BRIEF.md §3). Both §230 arms ran before §258's fix; a 65% shuffle bought after it
gave +0.194 [+0.134, +0.252] on a reader drifted by +0.153 (§259). Research, not a loop.

## 5. Defect catalogue (20 operator reads, 2026-08-18 to 2026-09-23)

| Family | Reads that named it | Home in the rebuild |
|---|---|---|
| F1 figures that fail a literal read | 2, 3, 6, 7, 8, 10, 13, 16, 18, 19 | CHECKLIST |
| E2 trade words, idiom, unexplained terms | 6, 7, 11, 12, 13, 16, 17, 18, 19, 20 | CHECKLIST |
| B hook or premise fails | 2, 3, 5, 7, 10, 15, 18, 20 | bible fields, `pitch-shape`; CHECKLIST |
| G1 narrated inference, manner gloss | 6, 7, 11, 12, 13, 14, 17, 19 | `tells` and rewrite; CHECKLIST |
| D sentence mechanics, and-chains, dashes | 1, 5, 6, 11, 12, 17 | normalizers, `tells` |
| A/H1 system furniture, no weighing options | 1, 4, 6, 8, 10, 18 | sheet, `rise`, `fields`, Options |
| C1 minutiae, iceberg | 4, 7, 9, 10, 11 | a bible of <=900 words, no packets |
| C2 stagnant, progress felt late | 2, 4, 7, 10 | Rise in every plan, `rise` |
| J standalone sense, device legibility | 6, 10, 17, 18 | CHECKLIST |
| E3 money, debt, institutions | 7, 8, 20; the 08-23 refusal (§116) | `money`, `admin`, prompt lint |
| C4 too many names | 2, 3, 10 | `cast` report, People caps |
| B6 not LitRPG | 7, 8, 10 | status lines, `rise` |
| G2 absence and paradox tells | 11, 15, 19 | `tells` and rewrite |

Also named: no interiority (1), a grey palette (5, 8), a schema word in a title (11, now `leak`), nobody
exclaims (18). Silence is not absence. Sources: recurrence map §3 (reads 1-13), `plan/serial-pilot-18.md`
and `plan/reader-read-15.md` to `-20.md` (14-20), evidence/reader.md. Money lived longest: 18 of 30 forged
worlds named a register, debt, court, deed or clerk in the premise, all 30 used the family (median 7.21 per
1k), from our forge rules (§116); a later institutional lean survived their deletion: the model's (§156.1).

## 6. Market reference numbers (descriptions, never bars)

- §155, 13,364 LitRPG chapters (584 fictions, median 2,053 words): progression events per 1k median 0.00 (p75
  1.26, p90 3.60); 51.0% have none (a joint claim about market and counter recall); 22.5% have one in the
  first 500 words; gap CV 0.96, about Poisson.
- §202, 1,386 early-sampled chapters (462 stories): any display in 31-39%, a window in 20-25%, a median 2
  fields per window (largest 19), 6.5% of fields at zero or blank, 3 choice screens in all; floors, as prose
  systems are invisible to it. §201: two of three shelf openings print no window in chapter 1.
- §138: ten market listings carry 7.2 number tokens per 1k words; 0 of 10 name a floor or rank position.
- §199, tells per 1k, four placed openings vs six of ours: absence 1.0-2.6 vs 4.4-12.3, paradox 0 vs 0-1.6,
  "the way" 0-0.6 vs 1.5-3.1, echo 0-1.0 vs 1.1-4.0, chained "and" 0-0.5 vs 5.1-7.2. The shelf never passes
  35 words a sentence (§199.4); our narrated-inference rate is 4.7x the genre's (§156.2).
- Levity runs a median 5.50 beats per 1k; Reappraisal's chapters 1-2 sat at its 61st percentile (comic-beats-
  results.md). A pasted RoyalRoad chapter measured 1,502 words in 21 paragraphs; the reference corpus's median
  chapter is 2,074 (memory royalroad-chapter-length-target); the shelf blurbs' longest sentence is 27 words
  (read 17's fix; memory opening-parity-track).

## 7. Where the evidence lives (`git show legacy/incumbent-2026-09-27:<path>`; never import it)

- `plan/stage-0-decisions.md`: 267 entries, 27,439 lines, 2.0 MB; search `^## NNN`, never read it whole.
- `RESEARCH.md` (results by question; §4.9 method rules); `research/quality-measurement/BRIEF.md` (the proxy
  ledger; §5 rules; §6 six questions before a number may refuse anything).
- `plan/agent-impact/read-recurrence-map.md` and `REPORT.md`: families A-M, what fixed each, gate misses.
- Reads: read 1 is §74; `plan/reader-read-2.md` to `-8.md`, `-15.md` to `-20.md`; reads 9-14 in
  `plan/serial-pilot-15b.md`, `-16.md`, `-18.md`. `tools/chapter_one_items.json` seeds `reads/CHECKLIST.md`.
- `src/litharness/domain/tells.py` (362 lines), `application/tells_pass.py` (320), `providers/cli.py`,
  `providers/codex_cli.py`, `tests/test_providers.py`: tells, rewrite, transport isolation.
- `research/opening-parity/FINDINGS.md`; `research/quality-measurement/cost-that-bites/`, `system-displays/`,
  `comic-beats-results.md`, `progression-cadence-results.md`.
- Lite's code: tag `legacy/lite-2026-09-27`. Rebuild plan: `experiments/2026-09-27-rebuild-plan/`. Books, runs
  and corpora: `C:\DEV\LitHarness-archive`, listed in `MANIFEST.tsv`.
