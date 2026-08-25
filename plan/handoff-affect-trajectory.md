# Handoff: the affect-trajectory census — where a chapter reaches for tension, relief, excitement and the rest, how often it turns, and whether a locator can see the waves at all

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose goal is
superhuman popcorn-genre books (LitRPG, progression fantasy, isekai) with no human in the
production loop. Your task is one bounded measurement: a **located census of the emotional
register a chapter reaches for, paragraph by paragraph, and the shape of the sequence that
makes** — tension building and releasing, excitement, triumph, loss — in this project's chapters
against the RoyalRoad LitRPG population. It is built in the mould of the comic-beat census
(`research/quality-measurement/comic_beats.py`, 2026-08-22) and inherits its four hard lessons.
It admits nothing, directs nothing, and scores nothing. It produces distributions and stops.

File names and § numbers below were verified on 2026-08-22 against `main`. If the repo has
drifted, the repo wins; re-anchor rather than following this document into a stale reference.
Parallel sessions run on this repository — `git status` before you commit, commit only your own
files, and leave other sessions' untracked files alone.

## Why this exists (context you need, then stop reading context)

The operator asked whether the project has any analysis of *"emotional texture … how emotions
change in waves throughout the text"*, and clarified the object: not comedy, but **tension,
relief, excitement** and their kin. Checked 2026-08-22: **it does not, and nothing in the repo
comes close.** Nothing under `src/`, `research/quality-measurement/` or `tests/` computes
sentiment, valence/arousal, mood, or any per-position affect series. The single mention is a
candidate line in a document that is itself retired: `plan/machine-taste-program.md` §3, *A3
dimension coverage — the affect column, the valence/arousal trajectory model from the
emotion-dataset thread — admitted only if it survives its own refutation gauntlet (acclaimed-prose
control, lexicon-redundancy check, conversion separation)*. That document was closed by the scope
axiom (stage-0 §95) and the "emotion-dataset thread" never entered the repository. Two of its
three gauntlet items still stand and are built into this design; the third is dead on its own
evidence (`results/conversion.json`: *SEPARATION IS PROSE-BLIND* — the label carries story size,
so there is no conversion arm here and you must not add one).

Two words will mislead you in the ledger, so fix them now. **"Valence"** in stage-0 §90–§97 means
*reader preference* — would I keep reading — and is the channel the Reader role owns and every
verdict protocol died in. It does not mean the emotional valence of a passage. **"Flat"** in
`domain/axes.py` is `stat_flatten`, the numbers in a status block; it is not flat affect. Nothing
here may reuse either word in either sense without saying which.

**What the market side already says about the shape.** `research/market/publisher-taste-profile.md`
"Emotional contract": what the genre's blurbs promise is effort→reward **fairness** — the grind
pays — apocalypse-as-opportunity, competence, clean revenge, found family, humor as coping; what
is *absent* is grief that isn't fuel, tragedy, ambiguity-as-centre. Its §4d lists
*emotional-contract delivery* as a candidate dimension with **no instrument**. So the wave the
genre sells is a set-up → payoff cycle at chapter grain, with a cliffhanger cadence at the chapter
boundary. Nobody has measured whether the genre's prose actually moves that way, or whether ours
does. That is the census: not *is the book moving*, which is a verdict, but *where does the text
reach for which register, how often does it turn, and does a pressure it sets up get released*.

**Why a trajectory and not a level.** A density of "emotional words" is the fourteenth proxy of
the shape `research/quality-measurement/BRIEF.md` §3 diagnoses — static, absolute, correlational
— and a lexicon is exactly that. The thing the operator named is the *sequence*: modulation, not
amount. So the unit this instrument reasons about is the ordered series of labels down a chapter,
and every statistic it reports is a property of that series (coverage, turn rate, run length,
set-up→release pairing, position profile), computed deterministically from the labels after the
model has placed them. The model locates; arithmetic does the rest.

**Why a model locator is allowed, and what a word list is for.** A model cannot be asked for a
*verdict* (stage-0 §89.4: position outweighs text 4,676 to 1) and can be asked to **locate** (E6,
§89; §97.4: *the "why" is located, not narrated; each property enters with its counter or locator
committed first*). The comic census is the one built, run and priced instrument of that shape and
it is your pattern. A valence/arousal **lexicon** series is computed beside the model's in the
same pass — not as the instrument but as the **incumbent** it has to beat: if a word list
reproduces the model's series and sees the same damage, the model is a word list with a price
tag and the word list ships instead. Either outcome is a result.

**Four lessons from the comic census you inherit rather than rediscover**
(`research/quality-measurement/comic-beats-results.md`, memory `comic-beat-census`):

1. **A one-draw model locator over a whole chapter is worth about 0.54.** Byte-identical re-ask
   moved the count by a median of five beats; anchors overlapped 18%; reliability 0.537, so no
   correlate of a single-draw number can exceed 0.73, and **four draws per unit are needed for
   0.8**. This design budgets the draws up front instead of discovering the noise afterwards.
2. **Granularity was the largest unmodelled source of variance** — "a run of banter can be
   marked once or three times" — so this instrument labels a **fixed grid the text defines**
   (paragraphs) rather than asking for free anchors. The model decides the kind; the text
   decides the positions.
3. **The layout sham was clean** (median 0.0, 90% CI [−1, +1]); the noise was undirected
   sampling variance, not an artefact. Keep the sham; expect it to pass; read it against the
   repeat spread, never alone.
4. **The pre-registration named no primary strip reading and no multiplicity policy**, and the
   results doc had to record that as a declared defect. Name both here before the first call.

Three further findings you must not re-derive: description does not move register,
demonstration does (§83: 0 of 4; §85/§85.1: exemplar arm moved 8/8 scenes); every verdict
protocol died to a control, not a bug (BRIEF §2); and a noisy instrument passes a null
automatically (§101.1), so every bar below is an equivalence bound or a refusal state, never a
pass by silence.

## Read before writing anything

1. `CONTRIBUTING.md` — all of it, especially "Before proposing a quality or craft metric" (read
   BRIEF.md §2 first; **which source you pick is a validity decision**: own-generated text is the
   only un-memorised substrate; RoyalRoad carries a familiarity term) and "Scope discipline".
2. `plan/handoff-comic-beat-census.md`, then `research/quality-measurement/comic_beats.py` and
   `comic-beats-results.md` in full — **the exact pattern you are reproducing**: frozen system
   block + question + schema + closed kinds under a content digest with a `--selftest` that
   fails on divergence and on any quality vocabulary; `PRE_REGISTRATION` as a constant copied
   verbatim into every result file; `--dump` on the MirrorBench side writing a gitignored
   JSONL under `derived/`; arms `census|repeat|sham|strip` plus `report`; ids-and-numbers-only
   results; one-sided exact sign tests with the attainable floor printed; `INSUFFICIENT_N` and
   `VOID` as outcomes. Its §6 "Known residuals" and §9 draft registration paragraph are the
   bar for honesty your results doc must clear.
3. `research/quality-measurement/opening-counters-results.md` and `plan/reader-read-2.md` — the
   census doctrine: headline first and not the flattering one; acceptance artifact; admission
   is an operator act over a measured distribution, never the instrument's own.
4. `src/litharness/domain/axes.py` module docstring and `plan/reader-judge-loop.md` §2.1 — the
   two doors an axis enters by, so you know why nothing you build may touch `AXES`, `COUNTERS`,
   a prompt, or a directive. Note `interior_per_1k`'s `_INTERIOR` verb list: it is the nearest
   existing counter to "emotion" and it is a rate, not a series — your lexicon control should
   not be that list, but you should report agreement with it once, since a reader will ask.
5. `plan/stage-0-decisions.md`: §74 (the defect-harvest shape), §83/§85/§85.1 (description vs
   demonstration; tier as the first debiasing lever), §87 and §89 (the attainability rulebook —
   range, direction, unit, non-emptiness — and the seven declared quantities that could not do
   what they said), §94.6 (fixed-pattern readers pass every declared control), §96.2 (*a part
   may locate; it may not prefer*), §97.4 (what a sim is allowed to be; *no sim narrates its
   psychology as signal*; no verdict slot anywhere), §101.1 and §101.4 (equivalence bounds; σ
   before the bar), §104.4 (chapter-hook shapes are a gated mining property — you are **not**
   classifying hook shapes), §108.5 (the endings census: a locator and counters with an era
   control that passes, and four attainability checks that could not be answered at n=2).
6. `research/quality-measurement/elicit.py` — `Elicitor(cache_path, model=PANEL_MODEL,
   transport="cli", …)` and `ask_raw(system, turns, schema=…, max_tokens=…, tag=…, sample=…)`,
   the persona-free seam; `PANEL_MODEL = "claude-haiku-4-5"`; `CLI_HARDENING` (the two flags
   every `claude -p` call must carry, stage-0 §109); the digest-keyed append-only cache.
7. `research/quality-measurement/corpus_io.py` — `royalroad_chapters` (MirrorBench venv only;
   note its per-shard budget fix recorded in §108.5), `era_cohort`, `generated_scenes`,
   `by_story`; `ablate.py` — `paragraphs`, `rewhitespace` (works block-by-block, so paragraph
   breaks survive it — assert this in your selftest), `destake`/`deplete_matched` (a stakes
   deletion with a length-matched control, the nearest existing affect-adjacent damage, not
   reused here but read it); `repair_generation.py` — the certified minimal revision pattern and
   its mandatory placebo arm; `domain/axes.strip_system` and `_SYSTEM_LINE` for system-voice
   paragraphs.
8. `research/quality-measurement/RUNBOOK.md` "Five ways to waste a paid run" and its comic-beat
   section (the cost as measured, the transport failure modes); `corpus_leak_audit.py`.

## The question, stated exactly

> Where does a chapter reach for tension, relief, excitement and the rest; how often does that
> register turn; does a pressure the text sets up get released within the chapter — in the
> genre's published chapters and in ours — and can a located instrument see any of it at a
> reliability that makes the answer worth having?

Three sub-questions, answered in this order and reported separately:

- **Q1 (baseline shape).** The distribution of the trajectory statistics (defined below) across
  RoyalRoad LitRPG chapters, by `era_cohort` (`human_pre_llm`, `undeclared_2025`,
  `declared_ai_2025`), plus the genre's **position profile** — register share by chapter decile —
  which is the population's average wave.
- **Q2 (placement).** Where our published chapters sit — `book-library/reappraisal/chapters/
  Chapter1-2.txt` and `book-library/what-takes/chapters/Chapter1-2.txt` — measured at **K = 4
  draws per chapter** so each placement carries its own interval; `generated_scenes` units as
  secondary colour at scene grain, never pooled with chapters.
- **Q3 (validity).** Test-retest agreement at the paragraph grain and at the statistic grain;
  the layout sham; a certified *flatten* revision with its placebo; the lexicon-redundancy
  reading; the misalignment (confabulation) rate on every arm.

Q2 is worthless without Q1 and both are worthless without Q3. Report all three even if Q3 kills
the instrument — a mapped hole is a result (§74's logic), and "the genre's wave cannot be seen by
a model at this grain" is a finding the next proposal needs.

## What the instrument is

**A fixed grid, labelled.** The unit is the **paragraph**, split by the same rule everywhere
(`ablate.paragraphs`, blank-line separated; confirm it and the library's `Chapter*.txt`
agree). One whole chapter per call. The model returns, for **every** paragraph in order, two
things: `kind`, one of a closed set, and `echo`, the paragraph's first four words copied exactly.
The echo is the deterministic alignment check this design has that free anchors did not: a label
whose echo does not match its paragraph is a **misalignment**, excluded from every series and
reported as a rate on every arm. Labels beyond the paragraph count, or short of it, are counted
and reported; the series is never silently padded. Nothing is chunked: a chapter outside the
word window is excluded and the exclusion counted (no silent caps — `log` what was dropped).

**The kinds** — a closed set, because an open set cannot be falsified (`personas.py`'s
reason-code argument). Draft set, refine before freezing, **never extend after the first paid
call**, and keep it at or under ten including `none`. Every definition describes the **register
the text reaches for**, never its effect on anyone:

| kind | one-line definition (register, not effect) |
|---|---|
| `tension` | a threat, deadline, risk or unknown being pressed, the outcome still open |
| `unease` | something off, wrong or foreboding, before any threat is named |
| `anticipation` | a reward, reveal, arrival or confrontation being promised as near |
| `momentum` | action or events arriving faster than they can be weighed |
| `relief` | a pressure set up earlier being let go, or a threat passing |
| `triumph` | a win, gain, level, skill or recognition landing on the page |
| `loss` | a cost paid, a defeat, a death, a thing given up |
| `ease` | rest, care or lightness between characters or in the narration; the pressure is off |
| `wonder` | a thing of the world shown for its own strangeness or scale |
| `none` | the paragraph reaches for none of these — logistics, transition, plain exposition |

**The asking carries no quality or effect vocabulary, and the selftest enforces it as a property
rather than an intention** (comic census §5): search the rendered system block, question, schema
and definitions for `effective`, `works`, `gripping`, `moving`, `boring`, `flat`, `good`,
`better`, `quality`, `successful`, `lands`, `reader`, `feel`, `feels`, `emotion`, `emotional`,
and fail on any hit. "Emotion" is in this list on purpose: the model is asked what register the
text *reaches for*, and the word invites it to report what it imagines a reader undergoing,
which §97.4 forbids as signal.

**There is no intensity slot, and there must not be one.** A 1–5 intensity is a rating, and a
model's ratings are the narrated-judgment channel this repository has measured drifting
(§94.5: a difference confabulated between byte-identical texts). Amplitude in this design is
**emergent and deterministic**: how many words in a window carry a non-`none` label, how long a
run holds, how soon a release follows a set-up. If that proves too coarse, the honest next step is
a second closed label (e.g. `pressed` / `passing`) with its own validation — not a number the
model makes up.

**The trajectory and its statistics**, computed in-module from the label sequence with the
paragraph word counts, frozen under the same digest as the prompt, and identical for the model
series and the lexicon series:

- **coverage** — share of words under a non-`none` label; and per-kind coverage.
- **turn rate** — kind changes per 1,000 words, `none`↔`none` excluded, computed on the raw
  paragraph sequence and on a word-windowed series (window 200 words, declared before the run
  and not tuned).
- **run length** — median words per run of one kind.
- **set-up → release pairing** — a `relief` or `triumph` run is *paired* if a `tension`,
  `unease` or `anticipation` run ended within W words before it (W declared before the run, e.g.
  400, then frozen); `pairing_rate` = paired releases / releases; `unreleased_setup_share` =
  set-up runs not followed by a release within W before the chapter ends. **Its null is computed
  in the same pass**: permute the paragraph labels within the chapter (multiset preserved, 1,000
  shuffles) and report observed minus null. This is the wave reading, and it is a property of the
  sequence a shuffled chapter does not have.
- **position profile** — kind share by chapter decile of word position; averaged per cohort it
  is the genre's mean wave, and our chapters are plotted against it.
- **end state** — the kind carried by the last 150 words. Reported, by cohort, no bar; naming a
  hook *shape* from it is §104.4's gated property and is out of scope.
- **label entropy** per chapter.
- system-voice paragraphs (`_SYSTEM_LINE`) are flagged deterministically and every statistic is
  reported with and without them; a `[STATUS]` block can itself be a `triumph` paragraph and the
  model is shown it, so the flag is a covariate, not an exclusion.

**The lexicon series.** On the same grid, a per-paragraph valence and arousal from a published
word list if one is on this machine under research corpora (prefer the strongest available; a
weak list biases the redundancy check toward "not redundant", which is the flattering direction)
and otherwise a small in-module list — record which, and its provenance. Its statistics are the
same functions. It costs nothing, has zero test-retest noise, and is the thing the model has to
be shown to beat.

## Controls, pre-registered in-module before the first call

Write `PRE_REGISTRATION` as a constant block and copy it verbatim into every result file. Arms:

- **`census`** — RoyalRoad, one chapter per story, one draw. Q1 is read from this arm alone.
- **`own`** — the four published chapters at **K = 4** independent draws (distinct sample index,
  byte-identical request), `generated_scenes` units at K = 2. Q2 is read here, with a per-unit
  interval from the draws.
- **`repeat`** — RoyalRoad, a digest-chosen subset (size declared; the comic census used 40 and
  lost some to the transport), K = 2. Reports **Cohen's κ per paragraph pair** and the ICC of
  every trajectory statistic across draws; the variance decomposition (noise sd, population sd,
  reliability, draws-to-0.8) exactly as comic census §4 printed it. This is the noise floor every
  other arm is read against.
- **`sham`** — `ablate.rewhitespace` at full strength. Selftest asserts the paragraph count and
  every echo survive it. The statistics must not move beyond the `repeat` spread; if they do, the
  model is reading layout and the entry says so (§78).
- **`flatten`** — the validity arm, damage direction: a certified minimal revision in
  `repair_generation.py`'s pattern that rewrites every reach for the registers above into plain
  statement of the same events — order, POV, typography, protected system spans and length
  preserved, certified by word-similarity, growth bound and byte-survival — with
  **`flatten_placebo`** (the same revision contract, an inert task) beside it, mandatory. Run it
  on text that *has* coverage — the top decile of the `census` arm's coverage plus every own
  chapter — one dose only. Both the model series and the lexicon series are computed on original
  and flattened text.
- **`lexicon`** — free, same pass: within-chapter Spearman between the model's windowed coverage
  series and the lexicon arousal series; agreement on every trajectory statistic; and whether
  the lexicon sees the `flatten` drop as well as the model does.
- **Era table** — every statistic by cohort, always. The control that killed `tricolon_rate`
  (BRIEF §2) and the one §108.5 passed: if `human_pre_llm` and `declared_ai_2025` separate on a
  statistic more than `undeclared_2025` does from either, the statistic is reading the year.

**The primary reading and the multiplicity policy, named now** (the comic census's declared
defect, fixed here): the primary validity reading is the **coverage** drop on `flatten` versus
`flatten_placebo`, paired by unit, one-sided exact sign test; the secondary is the **turn rate**
drop; Holm across the two; everything else in Q3 is descriptive and says so. Both are read
against the `repeat` spread, and a drop the misalignment rate could manufacture is `VOID` by
rule, not by explanation afterwards.

**Bars.** Declare none for admission — admission is an operator act over the measured
distribution. For the instrument's own validity, state each quantity with direction, unit,
range and an attainability check at the n actually available **before** the first call (§87/§89;
§101.4: σ first, bar signed after). Report `INSUFFICIENT_N`, `VOID`, `DOES_NOT_SEE`, and
`REDUNDANT_WITH_LEXICON` as outcomes rather than passes or failures. Never inherit a figure from
another entry as a bar (§79.1). A sketch, for you to size rather than copy: the `flatten` drop
must exceed the `repeat` spread on a majority of paired units; the `sham` delta must sit inside
it; per-paragraph κ and per-statistic ICC are printed on every arm and an ICC that would need
more than four draws for 0.8 is stated as the cost of any per-chapter claim; the lexicon
redundancy band (a median within-chapter correlation above which, *with* the lexicon seeing the
flatten drop, the model is declared redundant) is chosen and frozen before the run.

**Familiarity is a named confound, not a footnote.** RoyalRoad may be memorised (BRIEF §2
Pass 6); own-generated text is the clean arm; the `flatten` differential on the same unit
partially cancels it; the two substrates are never pooled.

## Substrate, venvs, transport, cost

- **Reuse the comic census's draw.** The ids in `results/comic-beats-royalroad-census.json` are
  a deterministic one-chapter-per-story draw by cohort inside the [800, 6000]-word window; use
  **the same chapters**, so the two censuses share a population and any later cross-reading
  costs nothing. If `derived/` no longer holds the dump, regenerate it under the MirrorBench
  venv with the same rule and assert the id set matches before spending anything.
- **Two interpreters, split by what the run reads.** RoyalRoad parquet only under
  `C:/DEV/MirrorBench/.venv`; `--dump` writes a gitignored JSONL under
  `research/quality-measurement/derived/`; every arm runs under `uv run python` reading it.
  Committed results carry **ids and numbers only** — per-paragraph labels for RoyalRoad are
  stored by paragraph index and a hash of the echo, never the text; own chapters may store
  echoes verbatim. Every revision the `flatten` arm generates lives under `derived/`. Run
  `corpus_leak_audit.py` before committing anything.
- **Own units.** Published chapters from `book-library/*/chapters/Chapter*.txt` (the unit a
  reader receives); `generated_scenes` across the book databases as the secondary, scene-grain
  arm (§108.5's census found 146 such units across 23 books; count yours and print it).
- **Model and tier.** `PANEL_MODEL` (Haiku 4.5) for every locator arm; if `flatten` voids on
  the `repeat` spread on own prose, replicate the `flatten` arm at Sonnet before concluding
  anything (§85.1: tier is the first debiasing lever, protocol the second). Revisions on the
  tier `repair_generation` used.
- **Cost.** Price from the first ten cached calls (`--dry-run`, then ten live) and **report the
  projected cost before the main arm runs**. Do not derive it from the comic census's $68.99 —
  the answer here is a label per paragraph, which is a longer output than a list of beats, and
  `claude -p` spends most of each answer on thinking — but do use that figure as the order of
  magnitude a refusal-worthy projection would exceed by several times. Own K = 4 on four
  chapters is sixteen calls and is not where the money goes.
- **Operational rules, each already paid for once:** one CLI arm at a time on this box; no
  pytest, mypy or GPU job beside it; a dedicated `--cache` per arm, never shared; hold a PID
  lock (`force_remote.SingleRun` is the reference) so a second launch refuses; never wrap a run
  in `timeout`; `pkill -f` matches nothing here — kill by PID from PowerShell and verify zero;
  stdout is buffered, the cache JSONL is the progress bar; read `transport_failures` before any
  number; arithmetic before the calls or after them, never during; every `claude -p` call site
  carries the CLAUDE.md-suppression flags (`CLI_HARDENING`, §109) and never `--bare`.

## Deliverables

1. `research/quality-measurement/affect_trajectory.py` — the instrument. Frozen system block,
   question, schema and kinds under a content digest; the trajectory statistics as pure
   functions over `(labels, word_counts)` frozen under the same digest; `PRE_REGISTRATION`;
   `--selftest` (schema shape, kinds closed, forbidden vocabulary absent, echo alignment on a
   synthetic chapter with a known label sequence, `rewhitespace` leaves paragraph count and
   echoes intact, the permutation null returns ~0 on a shuffled chapter, byte-freeze check);
   `--dry-run`; `--dump` (MirrorBench side); `--arm census|own|repeat|sham|flatten|report`;
   `--substrate royalroad|local`; results as `results/affect-trajectory-*.json` beside a raw
   JSONL cache; module docstring in the house style (what it measures, what it cannot say,
   which venv runs what, the commands).
2. `research/quality-measurement/affect-trajectory-results.md` — in `comic-beats-results.md`'s
   shape and order: **the headline first, and the unflattering one if that is what it is**; the
   acceptance artifact — the labelled series for Reappraisal ch. 1 and What Takes ch. 1 printed
   in full (paragraph index, echo, the four draws' labels, the lexicon value) so anyone can
   check each label against the page — a transparency artifact, **not** a solicited read: do
   not ask the operator to rate, label or confirm anything; Q1 distributions by cohort (n,
   mean, sd, p5–p95) for every statistic and the mean position profile per cohort; Q2
   placements with intervals; Q3 with every control's number and every refusal state; what the
   instrument is mechanically; known residuals, unfixed and named; a **draft registration
   paragraph that claims no § number, declares no bar and admits nothing**.
3. A short `RUNBOOK.md` section: the commands, the cost as measured, the failure modes met.
   No new count anywhere — counts point to canonical homes, never restated.
4. A memory-free summary back to the operator: the three sub-answers, projected versus actual
   spend, whether the model beat the word list, and one sentence on whether a second step is
   warranted *on this evidence*.

## What is explicitly out of scope — and why each line is there

- **Nothing under `src/`.** No axis, no `COUNTERS` entry, no directive kind, no Director brief
  vocabulary, no persona reason code, no writer dossier, no roster change.
- **Nothing reaches a prompt, a directive, or any generation path.** Not a "tension note", not a
  pacing constraint, not a chapter-ending rule. A directive about affect, if one is ever
  authored, carries this census's number the way C8 carries the sentence-length number — and is
  authored by the operator, not by you.
- **No arc archetypes.** Fitting the series to a menu of shapes (rags-to-riches, man-in-a-hole,
  the six Reagan/Vonnegut curves, or any clustering into "types") is selection among candidates
  with no containment (§61(5), §105.1) and would be read as a bar the moment it printed. The
  statistics above describe a shape; nothing names one.
- **No intensity, arousal or "how strongly" rating from the model.** Stated above; repeated here
  because it is the first thing a builder will want to add.
- **No emotional *effect* measurement, no reader-sim emotional self-report.** Whether a passage
  *moves* anyone is valence; valence is behavioural or it is nothing (§97.4); a sim's account of
  what it felt is data about the sim. Name this in the results doc as the next question and do
  not build it.
- **No conversion arm.** `results/conversion.json`: the revealed-preference label is prose-blind.
  Do not correlate any statistic with it.
- **No chapter-hook-shape classification** from the end state (§104.4's gated property;
  `chapter_endings.py`'s docstring records the refusal and why).
- **No book-level arc on own prose.** Two published books of two chapters each is not a series
  across chapters; RoyalRoad `by_story` could carry one and it is secondary colour at most —
  report it only if it costs no extra calls.
- **No inject arm, no dose ladder, no second model family at census grain, no RoyalRoad
  fetching or scraping** (the shards are local; the site returns 403 and its terms are unread).
- **No ledger entry claimed.** The highest stage-0 number in use across `main` and every
  worktree was §111 on 2026-08-22, and parallel sessions collide on numbers; the draft
  registration paragraph lives in the results doc and the operator moves it. If you cite a test
  name in any document, it must exist
  (`tests/test_architecture.py::test_every_test_cited_as_evidence_exists`).
- **No quality or craft claim.** Coverage, turn rate and pairing are properties of *reaches*.
  A chapter that turns more often is not better, a chapter that is 80% `none` is not worse,
  and the doc says so in its first section. The publisher's stated contract is a prior about
  what the market selects for, not a direction anyone here has earned.

## House rules that bite here

Parallel sessions run on this repo: `git status` and `git diff` any shared doc immediately
before editing it, and re-read before each edit. Corrections are made in place with
strikethrough and a pointer, never silently. Commit numbers, never prose. The decision log is
append-only and you are not appending to it. Two interpreters, split by what the run reads. Use
`corpus_io.py`; do not write another loader. ruff rejects literal curly quotes in Python strings
(write `\u2018`-style escapes). The repo is LF; `core.autocrlf=true` is global on this machine,
so scripted edits write LF explicitly and `git diff --check` runs before commit. Before handing
off: `uv run pytest`, `uv run ruff check .`, `uv run mypy`, `git diff --check` — and none of
them while a paid arm is running.

## Invariant check, before you report done

- Every number in `affect-trajectory-results.md` is reproducible from a committed results JSON
  that carries ids and numbers only; `corpus_leak_audit.py` passes over the working tree.
- `PRE_REGISTRATION` in the module is byte-identical to the block in every results file; the
  frozen prompt's and the frozen statistics' digest is asserted by `--selftest`; the forbidden
  vocabulary is absent from the rendered asking.
- The `repeat`, `sham`, `flatten` and `lexicon` arms each report a number or a declared refusal
  state; none reports a pass by silence; the primary reading and the Holm policy are the ones
  named before the run.
- Every per-chapter placement in Q2 carries the interval its K draws give it, and no per-chapter
  claim is made from a single draw anywhere in the doc.
- Nothing under `src/` changed; no prompt, directive, axis, counter, persona, dossier or brief
  changed; no § number is claimed; no bar is declared for admission; no arc type is named.
- The headline sentence of the results doc would survive being read by someone hoping for the
  opposite result — including the outcome "a word list does this as well, for free".
