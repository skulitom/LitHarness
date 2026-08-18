# Runbook — reader-panel and summariser measurements

Every number §70 and §73 record came out of a command, and until this file existed none of
those commands were written down anywhere but a shell history. The invocations below are
reconstructed from the parameters each result file records about itself (`panel_model`,
`transport`, `n_samples`, `pair_question`, `passage_source`, …), not copied from a transcript,
so treat them as *reproductions* of the recorded runs rather than transcripts of them. Where a
run's own metadata is the authority, the file is named beside it.

## The corpus, and a reproducibility hole that was open until 2026-08-18

Every reader measurement in §70 ran on a 10-scene LitRPG book this system drafted — `toll.db`,
~1,000 words per scene, `gen:scene-1` … `gen:scene-10` at `--min-words 500`. It is the only
un-memorised source available (BRIEF §4), which is the whole reason the persona work could run
honestly at all.

**It was living in a session scratchpad under `%TEMP%`.** A temp sweep would have deleted the
substrate of every recorded persona number, and nothing in the repo would have noticed. A copy
now sits at `research/quality-measurement/corpora/toll.db`.

That copy is **untracked** — `.gitignore` line 11 ignores `*.db`, and forcing an 800 KB binary
past an explicit ignore rule is a call for whoever owns the repo, not a thing to do quietly. So
the hole is smaller than it was and it is not closed: the corpus survives a temp sweep and does
not survive a fresh clone. Regenerating an equivalent book costs roughly $0.30 per drafted
scene in equivalent quota (BRIEF §4), but it would not be *this* book, and none of the recorded
numbers would be comparable across the substitution.

```bash
export TOLL=research/quality-measurement/corpora/toll.db
```

## Reader panel — the runs behind §70

All four pairwise cells score the same 113 variants over 10 passages at `--doses 1.0`.

**Gate 0, absolute verdict, real book.** 412 calls, 39 minutes, 4 refused samples. This is the
run that fired the positivity floor: 195 of 196 `keep-reading`, `ms_between` and `ms_within`
both exactly 0.0. Recorded in `results/persona-gate0-tollroad.json`.

```bash
uv run python research/quality-measurement/persona_battery.py --book-db $TOLL --min-words 500 --n-passages 10 --n-samples 5 --gate0 --transport cli --model claude-haiku-4-5 --cache persona-raw.jsonl --out persona-gate0-tollroad.json
```

**Gate 0, fixtures.** 246 calls, 22 minutes. ICC 0.489, and artifactual — 5 of 6 passages had
zero would-stop and every stop landed on the story's final scene. `results/persona-gate0-fixtures.json`.

```bash
uv run python research/quality-measurement/persona_battery.py --fixtures --n-samples 5 --gate0 --transport cli --model claude-haiku-4-5 --cache persona-raw.jsonl --out persona-gate0-fixtures.json
```

**Pairwise preference, Haiku.** The cell that clears the ladder: detect 0.9056, sham 0.7833,
margin 0.1223, positional bias 0.5874 (z = +4.73). Its `api_calls: 0 / replayed_calls: 904` is
not a free run — it is the re-parse after `_strip_fence` moved to read time, replaying the
cached text of a run already paid for. `results/persona-pairwise-tollroad.json`.

```bash
uv run python research/quality-measurement/persona_battery.py --book-db $TOLL --min-words 500 --n-passages 10 --doses 1.0 --pairwise --pair-question preference --n-samples 1 --transport cli --model claude-haiku-4-5 --no-spot --tie-policy half_win --cache persona-raw.jsonl --out persona-pairwise-tollroad.json
```

**Pairwise intensity, Haiku.** The 2×2's fourth cell.

```bash
uv run python research/quality-measurement/persona_battery.py --book-db $TOLL --min-words 500 --n-passages 10 --doses 1.0 --pairwise --pair-question intensity --n-samples 1 --transport cli --model claude-haiku-4-5 --no-spot --tie-policy half_win --cache persona-intensity-haiku-raw.jsonl --out persona-intensity-haiku.json
```

**Pairwise on gemma3:4b, both questions.** 94.1 and 36.5 minutes. **Both say nothing about the
questions**: the model failed the positional-bias precondition on each (chose-A 0.802 and
0.810), so the capability floor for this instrument is above 4B and these two runs bound that
floor rather than the persona claim. `results/persona-pref-gemma-tollroad.json` and
`results/persona-intensity-tollroad.json` — note the second file's name says `intensity` and
not `gemma`, which is the naming trap in this directory: read `panel_model` from the file, never
the filename.

```bash
uv run python research/quality-measurement/persona_battery.py --book-db $TOLL --min-words 500 --n-passages 10 --doses 1.0 --pairwise --pair-question preference --n-samples 1 --transport ollama --model gemma3:4b --no-spot --tie-policy half_win --rest-ratio 1.0 --cache persona-pref-gemma-raw.jsonl --out persona-pref-gemma-tollroad.json
```

## Summariser reliability — §73

Gates the two proposals that read across scenes. 50 calls at the defaults, well under the
module's 600-call guard. Run the null first: it needs no transport, and the point of it is that
the arithmetic has executed before the first paid call.

```bash
uv run python research/quality-measurement/summary_reliability.py --selftest
```

```bash
uv run python research/quality-measurement/summary_reliability.py --fixtures --scenes 6 --samples 5 --level 2 --window 3 --dry-run
```

```bash
uv run python research/quality-measurement/summary_reliability.py --book-db $TOLL --min-words 500 --scenes 10 --samples 5 --transport cli --model claude-haiku-4-5
```

Add `--level 2 --window 3` for the summaries-of-summaries arm (+15 calls). Its numbers are
diagnostics unless level 1 clears identity — the module records which, in `level2.gated_by`.

## Writer states — §83

32 retells (`claude-opus-5`, the book's own drafter) + 192 panel comparisons
(`claude-haiku-4-5`), ~75 minutes, zero refusals, $6.10 + $8.68 equivalent. The generation
cache drops transport failures on load and replays everything else, so an interrupted run
resumes for free; the run that produced `results/writer-states.json` absorbed a startup-lock
herd (three concurrent first `claude -p` calls all exiting non-zero) through the retry the
module now carries.

```bash
uv run python research/quality-measurement/writer_states.py --yes
```

`--generate-only` produces and measures the retells without spending panel calls;
`--dry-run --yes` runs the arithmetic on a null. Panel verdict: all three arms VOID on
per-arm positional bias (chose-A 0.73–0.83) — near-twin pairs sit below this panel's
positional resolution, the §78-tail law at its extreme. The finding lives in the mechanics;
read §83, not the win rates.

## Four ways to waste a paid run, all of them already paid for once

**Do not share a cache file between concurrent runs.** `Elicitor`'s write lock is per-process.
`--cache` exists because two runs sharing one JSONL interleave and corrupt each other's records.

**Do not wrap a run in `timeout`.** Two runs were killed at 58 minutes by a `timeout 3500`
guard set against an estimate of ~2 hours. The digest cache made the restart lossless, so the
cost was wall-clock rather than quota — but the guard contradicted the estimate it was meant to
protect, and it was the only reason those runs died.

**The cache is keyed by the exact request text**, so editing a persona or a prompt misses the
cache for exactly the affected records and replays everything else. That is the intended
behaviour and it means an interrupted run resumes for free — but it also means an edit made
mid-run silently splits the run across two prompt versions. Finish, then edit.

**GPU runs need the thermal governor.** `--transport ollama` is the only arm that touches the
card, and this workstation hard-shuts-down under sustained inference. `Elicitor._throttle`
sleeps `--rest-ratio × elapsed` after each call and then holds above 72 °C until the card drops
below 66 °C — the constants `cdg_battery.py` paid for when a thermal shutdown killed a run at
call 431. The temperature governor is the actual protection; the rest ratio is a coarse
pre-emptive measure, so raise it if the card still climbs. The CLI and SDK transports run on
remote compute and need none of this.

## Verifying before you push

CI runs three commands, and the third and second were both skipped for a stretch here while a
stale ruff cache reported the first as green:

```bash
uv run ruff check --no-cache . && uv run mypy && uv run pytest --cov=litharness
```

`--no-cache` is load-bearing. A cached ruff pass reported green on `research/progression-clause/ablate.py`
while it imported a provider deleted in `c99dd47`, and main stayed red for 10 runs.

## Repair generation — §85

32 generations (`claude-opus-5`) + 192 panel comparisons (`claude-haiku-4-5`), ~55 minutes,
$7.41 + $7.26 equivalent. Requires §83's cached sober retells (`--states-cache`) for the
exemplar anchor.

```bash
uv run python research/quality-measurement/repair_generation.py --yes
```

Headline: `repair_interiority` at 0.9509, bias 0.4918, interval [0.871, 1.0] — the first
bias-clean interval-excluding arm in the project, in the repair direction. `repair_emdash`
mechanically perfect (8/8 scenes to zero prose dashes at sim ≥ 0.978) and VOID at the panel
per the near-twin law. Read §85 before quoting any number.

## Axiom battery — §86

Tier 0 of [the unanchored-judge programme](../../plan/judge-validity-program.md): the axioms a
candidate judge satisfies before it costs anything else. Six disqualifiers plus per-arm
positional bias, on this system's own prose. **Run the two free commands first** — the selftest
is the argument that the battery is non-trivial, and the dry run is the argument that its
arithmetic works, and both execute before a call is bought.

```bash
uv run python research/quality-measurement/axiom_battery.py --selftest
```

```bash
uv run python research/quality-measurement/axiom_battery.py --dry-run
```

The dry run must read **DISQUALIFIED** — it answers uniformly from a request hash, so it is the
coin oracle in the real plumbing, and the module exits non-zero if a null ever clears.

```bash
uv run python research/quality-measurement/axiom_battery.py --yes
```

6 scenes, 54 pairs, **720 comparisons, ~$25, ~2.5 hours** at the CLI transport's measured 4.9
calls/min. `--yes` is required; without it the plan is printed and nothing is spent. Reads
`corpora/toll-scenes.json` — the *committed* export, not the gitignored `toll.db`, so this module
survives a fresh clone where the §70 runs above do not. `--book-db` overrides it.

The pre-registration lives in the module and the run copies it into the result file. Read §86
before quoting any number, and note the registered prediction: **the default panel is expected to
fail A1**, because §78 already measured it preferring blank lines at 0.0417 with clean bias.
