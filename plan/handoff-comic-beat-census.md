# Handoff: the comic-beat census — is humor attempted at genre density, measured by location and never by verdict

You are working in `C:\DEV\LitHarness`, an autonomous fiction-production system whose goal is
superhuman popcorn-genre books (LitRPG, progression fantasy, isekai) with no human in the
production loop. Your task is one bounded measurement: a **located census of attempted humor**
in this project's chapters against the RoyalRoad LitRPG population, built in the mould of the
names counter (`research/quality-measurement/opening_counters.py`, 2026-08-21). It admits
nothing, directs nothing, and scores nothing. It produces a distribution and stops.

File names and § numbers below were verified on 2026-08-21. If the repo has drifted, the repo
wins; re-anchor rather than following this document into a stale reference.

## Why this exists (context you need, then stop reading context)

The operator asked whether the project measures its ability for comedy. Checked 2026-08-21:
**it does not, and almost nothing names it.** Zero hits for humor/comedy/funny/joke/banter under
`src/`, in any test, or anywhere in git history (`git log -S`). The word appears three times in
the project: the pilot's tone note — *"Voice: dry, exact, quietly funny"*
(`plan/serial-pilot-1.md` §4.2) — which `acf0e05` found had never reached a single scene; RoyalRoad
prior **RR5** — *"Comedy is fine when native; trope imitation by an author who has not absorbed
the genre is sensed and punished"* — recorded in `plan/royalroad-platform-priors.md` §1 as
**unmanipulable at this instrument's grain**; and `research/market/publisher-taste-profile.md`,
which says the genre's voice is *"either humor-bearing snark (HWFWM register) or stoic-rational
(DotF register)"* and lists "voice presence" as a dimension with **no dedicated instrument**.

So the market research flagged humor as one of the two voices the genre runs on, and nothing
downstream ever picked it up. The operator's position: humor matters to the reader; the project's
register target is popcorn reading, never dense prose. Read humor here as **levity in the voice**
— snark, deadpan, the System as a character with an agenda — not comedy as structure. RR5's
warning is the standing risk of any later fix: bolted-on jokes are the most detectable form of
trope imitation, and quippy is also the default machine voice on the platform.

**Why a census before anything else.** This week's lesson, twice: a directive that reaches prose
should carry a measured number (C8's sentence-length figure was measured against 800 RoyalRoad
chapters, not chosen), and a counter can be perfectly deterministic and still not discriminate
the thing a reader minded (`opening-counters-results.md`: Reappraisal ch. 1 at the 68.5th
percentile). Before anyone proposes a "comedy role", the prior question is: *do our chapters
attempt humor at 0 where the genre runs at N, or not?* Nobody knows. That is the census.

**Why the census is a model report and not a counter, and why that is allowed.** There is no
deterministic counter for a joke; a regex for humor would be the fourteenth proxy of the shape
`research/quality-measurement/BRIEF.md` §3 diagnoses (static, absolute, correlational). What the
repository has measured is that models cannot be asked for a *verdict* (stage-0 §89.4: position
outweighs text 4,676 to 1; §70: 195 of 196 "keep-reading") but can be asked to **locate**: E6 —
*name the single most salient difference* — clears all three registered defect families (40/40,
30/32, 18/36 against measured nulls of 0.21/0.36/0.26, §89). §97.4 licenses exactly this shape:
*"the 'why' is located, not narrated … each property enters a property ledger with its counter
or locator committed first."* A comic beat is a property with a **locator**. The census asks
*where and what*, never *whether it is funny*.

Three findings you must not re-derive: description does not move register, demonstration does
(§83: 0 of 4; §85/§85.1: exemplar arm 8/8 scenes moved, readable at Sonnet); every verdict
protocol died to a control, not a bug (BRIEF §2); and a noisy instrument passes a null
automatically (§101.1), so every bar below is an equivalence bound or a refusal state, never a
pass by silence.

## Read before writing anything

1. `CONTRIBUTING.md` — all of it, especially "Before proposing a quality or craft metric" (read
   BRIEF.md §2 first; **which source you pick is a validity decision**: `generated_scenes` /
   the published chapters are the only un-memorised text; RoyalRoad carries a familiarity term)
   and "Scope discipline".
2. `plan/reader-read-2.md` and `research/quality-measurement/opening-counters-results.md` +
   `opening_counters.py` — **the exact pattern you are reproducing**: measurement only, two
   venvs, headline stated first and not the flattering one, acceptance anchor, distributions,
   what the instrument is mechanically, known residuals, a draft registration paragraph that
   claims no § number and admits nothing.
3. `src/litharness/domain/axes.py` module docstring and `plan/reader-judge-loop.md` §2.1 — how
   an axis enters the registry (two doors; admission is an operator act) — so you know why
   nothing you build may touch `AXES`, `COUNTERS`, a prompt, or a directive.
4. `plan/stage-0-decisions.md`: §74 (first human read, the defect-harvest shape), §83 and
   §85/§85.1 (description vs demonstration; tier as the first debiasing lever), §87 (the
   attainability rulebook: range, direction, unit, non-emptiness of every declared quantity),
   §89 (E6, and the seven declared quantities that could not do what they said), §94.6
   (fixed-pattern readers pass every declared control), §96 (the frame: *a part may locate; it
   may not prefer*), §97.4 (what a sim is allowed to be; no verdict slot anywhere), §104 (RR5).
   Skim §105–§106 for the house style of decision entries.
5. `research/quality-measurement/elicitation_study.py` — `E6_QUESTION`, `E6_SCHEMA`,
   `AXIS_MATCHERS` (frozen, "generous about vocabulary, strict about topic"), and the `e6_null`
   pre-registration: *the null is measured in the same run*, one-sided Fisher on its own family
   against the others, placebo rate reported separately as the confabulation rate.
6. `research/quality-measurement/elicit.py` — `Elicitor` (`cache_path`, `model`, `transport`,
   `ask_raw(system, turns, schema=…, max_tokens=…, tag=…)` is the persona-free seam you want),
   `PANEL_MODEL = "claude-haiku-4-5"`, the `cli` transport and its hardening, digest-keyed
   append-only JSONL cache.
7. `research/quality-measurement/corpus_io.py` — `royalroad_chapters(genre_tag="LitRPG",
   min_words=…, limit=…)` (MirrorBench venv only), `era_cohort`, `generated_scenes`; and
   `research/quality-measurement/repair_generation.py` — the **certified minimal revision**
   pattern (word-similarity, growth bound, protected-span byte survival) you will reuse for the
   strip arm.
8. `research/quality-measurement/RUNBOOK.md` "Five ways to waste a paid run, all of them already
   paid for once", and `corpus_leak_audit.py` (what counts as a leak; the whole history is in
   scope).
9. `research/quality-measurement/ablate.py` `rewhitespace` — the layout sham — and the §78
   lesson it exists for (a layout difference voided an entire arm).

## The question, stated exactly

> Do this project's published chapters attempt humor at the density the genre's readers select
> for — and can a located instrument see the difference at all?

Three sub-questions, answered in this order and reported separately:

- **Q1 (baseline).** The distribution of located comic beats per 1,000 words across RoyalRoad
  LitRPG chapters, by cohort (`era_cohort`: `human_pre_llm`, `undeclared_2025`,
  `declared_ai_2025`).
- **Q2 (placement).** Where Reappraisal chapters 1–2 (`book-library/reappraisal/chapters/
  Chapter*.txt`, the published form — the chapter is the unit, not the scene) and The Toll Road
  (`exports/the-toll-road.md`, per-scene, secondary colour only) sit in that distribution.
- **Q3 (validity).** Whether the locator sees a manufactured removal of beats, what its
  test-retest spread is, and whether it moves on layout alone.

Q2 is worthless without Q1 and both are worthless without Q3. Report all three even if Q3 kills
the instrument — a mapped hole is a result (§74's logic).

## What a "comic beat" is, for the instrument

An **attempt at levity the text makes**, located by quoting an anchor of at most twelve words and
classed into one of a **closed** set of kinds (closed because an open set cannot be falsified —
`personas.py`'s reason-code argument). Draft set, refine before freezing, never extend after the
first paid call:

| kind | one-line definition |
|---|---|
| `quip` | a character's or narrator's aside whose point is to be dry or sharp |
| `deadpan` | understatement or flat delivery of something outsized |
| `absurd` | an incongruous juxtaposition played for effect |
| `undercut` | a build-up deflated in the next clause or line |
| `callback` | a return to an earlier bit |
| `system_voice` | the System / status voice itself being arch, petty, or funny |
| `banter` | a dialogue exchange whose energy is the back-and-forth rather than its content |

**The instrument asks for location only.** The system block and question carry no quality
vocabulary: not "good jokes", not "funny", not "successful" — *attempts at levity, where, which
kind*. A beat is **counted only if its anchor is findable in the text** (normalised substring
match); an unfindable anchor is a confabulation, reported as a rate and excluded from the count.
That deterministic check is the one advantage this locator has over E6's matchers — use it.

One whole chapter per call. Chunking changes counts, so a chapter longer than the window is
**excluded and the exclusion counted** (no silent caps — `log` what was dropped). The system
block, question, schema and kinds are **byte-frozen at the first paid call** with a selftest that
fails on divergence (`llm-reader-engagement.md` §A1's rule: T0's A4 put ~14 points of a verdict
on wording; a reworded prompt is a different instrument with no evidence).

## Controls, pre-registered in-module before the first call

Write `PRE_REGISTRATION` as a constant block and copy it verbatim into every result file
(`axiom_battery.py`'s discipline). Arms:

- **`census`** — the chapter as published. Q1 and Q2 are read from this arm alone.
- **`repeat`** (test-retest) — the same chapter asked again at the same temperature, distinct
  seed. Reports the per-chapter spread of counts and the anchor-overlap between the two lists.
  This is the noise floor every other arm is read against.
- **`sham`** — `ablate.rewhitespace` at full strength. Changes no character of any word. The
  count must not move beyond the `repeat` spread; if it does, the locator is responding to
  layout and the entry says so (§78).
- **`strip`** — the validity arm, damage direction. A certified minimal revision in
  `repair_generation.py`'s pattern: the chapter rewritten to remove every attempt at levity
  while preserving events, order, POV, typography and length (growth bound), certified by
  word-similarity, growth, and byte-survival of protected spans. The census on original versus
  stripped must drop, paired by chapter, sign test with the count beside it. Run it on text that
  **has** beats — the top decile of the `census` arm — plus any own chapter with ≥ 3 beats. One
  dose only; n is small and a dose ladder would be decoration.
- **No inject arm.** A model adding jokes is the thing a later programme would study, not a
  control for this one.

**Bars.** Declare none for admission — admission is an operator act over the measured
distribution, exactly as for `opening_proper_nouns`. For the instrument's own validity, state
each quantity with its direction, unit, range and an attainability check at the n actually
available **before** the first call (§87/§89's rulebook; §101.4: the σ comes first and the bar
is signed after it). Report `INSUFFICIENT_N` and `VOID` as outcomes rather than passes. Never
inherit a figure from another entry as a bar (§79.1). A sketch, for you to size rather than
copy: the `strip` drop must exceed the `repeat` spread on a majority of paired chapters; the
`sham` delta must sit inside it; the confabulation rate is printed on every arm and a rate that
would swamp the `strip` effect is a refusal state.

**Familiarity is a named confound, not a footnote.** The locator is model-based and RoyalRoad
text may be memorised (BRIEF §2 Pass 6). So: own-generated chapters are the clean Q2 arm;
RoyalRoad is the baseline arm with the confound named; the `strip` differential on the same
chapter partially cancels it; and the two are never pooled.

## Substrate, venvs, transport, cost

- **RoyalRoad text can only be read under the MirrorBench venv; the Elicitor runs under `uv`.**
  Bridge them the way `taste_calibration --dump` did: dump the sampled chapters (ids, cohort,
  covariates, text) to a **local-only, gitignored** JSONL under
  `research/quality-measurement/derived/` (already ignored; see `.gitignore`), then run the
  census under `uv run python` reading that file. The committed results carry **ids and numbers
  only** — chapter id, cohort, word count, counts by kind, anchor-findability, covariates — and
  for RoyalRoad chapters anchors are stored as offsets or hashes, **never as quoted strings**;
  for own-generated chapters anchors may be stored verbatim (we own the prose). Run
  `corpus_leak_audit.py` before committing anything.
- Sample size: the names counter used 2,000 openings because the counter was free. Here each
  chapter is a paid call; 300 LitRPG chapters stratified by cohort is enough for quantiles —
  declare the number, do not creep it.
- Model: `PANEL_MODEL` (Haiku 4.5) for the census; if `strip` voids on `repeat` spread, replicate
  the `strip` arm at Sonnet before concluding anything (§85.1: tier is the first debiasing lever;
  protocol the second). Price from the first ten cached calls (`--dry-run`, then ten live) and
  **report the projected cost before the main arm runs** — derive nothing from §85's per-
  comparison figures, since a whole-chapter input is several times a §85 pair.
- Operational rules, each already paid for once: one CLI arm at a time on this box; no pytest or
  GPU job beside it; a dedicated `--cache` per arm, never shared between concurrent runs; hold a
  PID lock (`force_remote.SingleRun` is the reference) so a second launch refuses; never wrap a
  run in `timeout`; `pkill -f` does not work here — kill by PID from PowerShell and verify the
  count is zero; stdout is buffered, so the cache JSONL is the progress bar; read
  `transport_failures` before reading any number. Covariates and arithmetic run before the calls
  or after them, never during.

## Deliverables

1. `research/quality-measurement/comic_beats.py` — the instrument. Frozen system block, question,
   schema and kinds; `PRE_REGISTRATION`; `--selftest` (schema shape, kinds closed, anchor-
   findability on a synthetic text, byte-freeze check); `--dry-run`; `--dump` (MirrorBench side);
   `--arm census|repeat|sham|strip`; `--substrate royalroad|local|report`; results as
   `results/comic-beats-*.json` beside a raw JSONL cache. Module docstring in the house style:
   what it measures, what it cannot say, which venv runs what, the commands.
2. `research/quality-measurement/comic-beats-results.md` — in `opening-counters-results.md`'s
   shape, and in this order: **the headline first, and the unflattering one if that is what it
   is**; the acceptance artifact — the located list for Reappraisal ch. 1–2 printed in full so
   anyone can check each anchor against the text (a transparency artifact, **not** a solicited
   read: do not ask the operator to rate, label or confirm anything); Q1 distributions by cohort
   (n, mean, sd, p5–p95, max) and Q2 percentiles; Q3 with every control's number; what the
   instrument is mechanically; known residuals, unfixed and named; and a **draft registration
   paragraph that claims no § number, declares no bar and admits nothing**.
3. A short `RUNBOOK.md` section with the commands and the cost as measured. No new count
   anywhere — counts point to canonical homes, never restated.
4. A memory-free summary back to the operator: the three sub-answers, the projected versus
   actual spend, and one sentence on whether a second step is warranted *on this evidence*.

## What is explicitly out of scope — and why each line is there

- **Nothing under `src/`.** No axis, no counter in `domain/axes.py`, no `COUNTERS` entry, no
  directive kind, no Director brief vocabulary, no persona reason code ("laughed" is a verdict
  slot; §97.4 forbids one anywhere in a sim), no writer dossier, no roster change.
- **Nothing reaches a prompt, a directive, or any generation path.** Not a tone note, not C9.
  A directive about humor, if one is ever authored, carries this census's number the way C8
  carries the sentence-length number — and is authored by the operator, not by you.
- **No landing measurement.** Whether a beat *lands* is valence; valence is behavioural or it is
  nothing (§97.4), the BCR is unseated (§94.6/§94.7), and W4 (`payoff_landing.py`) — the nearest
  shape, since a joke is a micro promise/payoff — is NOT VALIDATED for want of substrate. Name
  this in the results doc as the next question and do not build it.
- **No "bounce" or punch-up role.** The operator's idea — a role that proposes comic situations
  and phrases — is plausible precisely because it is *demonstration* (§85's open lever) rather
  than *description* (§83's closed one), and it would split by lane: situations are story and
  Director-shaped (`CHAPTER_NOTE`/`ARC_NOTE`, never shown prose); phrasing is writer-side (§96.3's
  inner-speech arm (b) or a certified punch-up *revision* operator, since §87.1 found revision
  beats selection), with authorship-tells features as a rail so a punch-up that adds machine
  tells is caught; it proposes and never picks (*a part may locate; it may not prefer*, §96.2);
  it is one more arm, α/N, no-bounce as control. **Design it only if this census shows a gap
  and clears Q3, and only in a separate session with its own pre-registration.** Do not start it
  here.
- **No inject arm, no dose ladder, no second model family at census grain, no RoyalRoad fetching
  or scraping** (the shards are local; the site returns 403 and its terms are unread).
- **No ledger entry claimed.** The next free number was §107 on 2026-08-21 and parallel sessions
  collide on numbers; the draft registration paragraph lives in the results doc and the operator
  moves it. If you must cite a test name in any document, it must exist
  (`tests/test_architecture.py::test_every_test_cited_as_evidence_exists`).
- **No quality or craft claim.** Beats per 1k words is a density of *attempts*. A chapter with
  more attempts is not better, and the doc says so in its first section.

## House rules that bite here

Parallel sessions run on this repo: `git status` and `git diff` any shared doc immediately before
editing it, and re-read before each edit. Corrections are made in place with strikethrough and a
pointer, never silently. Commit numbers, never prose. The decision log is append-only and you are
not appending to it. Two interpreters, split by what the run reads (parquet and torch →
MirrorBench; everything else → `uv run python`). Use `corpus_io.py`; do not write another loader.
ruff rejects literal curly quotes in Python strings (write `\u2018`-style escapes).

## Invariant check, before you report done

- Every number in `comic-beats-results.md` is reproducible from a committed results JSON that
  carries ids and numbers only; `corpus_leak_audit.py` passes over the working tree.
- `PRE_REGISTRATION` in the module is byte-identical to the block in every results file, and
  the frozen prompt's digest is asserted by `--selftest`.
- The `repeat`, `sham` and `strip` arms each report a number or a declared refusal state; none
  reports a pass by silence.
- Nothing under `src/` changed; no prompt, directive, axis, counter, persona, dossier or brief
  changed; no § number is claimed; no bar is declared for admission.
- The headline sentence of the results doc would survive being read by someone hoping for the
  opposite result.
