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

## Five ways to waste a paid run, all of them already paid for once

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

**Do not run a CPU-heavy simulation next to an elicitation, even on a remote transport.**
The thermal governor in the next paragraph guards `--transport ollama`, and it is easy to read
that as "the CLI and SDK transports are thermally free". They are not free *of the machine*: the
`claude -p` transport spawns one process per call at four workers, and on 2026-08-19 an axiom
battery running on that transport was killed at comparison 158 of 720 by a workstation shutdown
while a null-simulation sweep held the CPU at full load beside it. **The elicitation was not the
load; it was the thing that died.** The digest cache made the restart lossless — 158 comparisons
replayed for nothing — so the cost was wall clock again, which is the same lesson the `timeout`
guard taught one entry up. Run the arithmetic before the calls or after them, never during.

**GPU runs need the thermal governor.** `--transport ollama` is the only arm that touches the
card, and this workstation hard-shuts-down under sustained inference. `Elicitor._throttle`
sleeps `--rest-ratio × elapsed` after each call and then holds above 72 °C until the card drops
below 66 °C — the constants `cdg_battery.py` paid for when a thermal shutdown killed a run at
call 431. The temperature governor is the actual protection; the rest ratio is a coarse
pre-emptive measure, so raise it if the card still climbs. The CLI and SDK transports run on
remote compute and need none of this.

## Latent-taste probe — §87, and the one place the other interpreter is mandatory

Track P is the only measurement in this directory that reads a model's **internals**, so it is the
only one that needs torch and the GPU. The two-interpreter rule above decides it: `latent_probe.py`
runs under **MirrorBench's** venv, never `uv run python`, and it never imports `litharness` — the
fixtures come from committed JSONL and `corpora/toll-scenes.json` rather than from `toll.db`, which
is what makes that possible.

```bash
export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
```

**The fixture table, with no model and no scoring.** Cheap, and the first thing to run after
touching `ablate.py` — a transform edit changes which pairs are byte-identical and therefore which
scenes drop.

```bash
"$MB" research/quality-measurement/latent_probe.py --fixtures-only
```

**The GPU pass.** 190 texts, 380 forward passes, ~164 seconds wall clock, ~9 GB VRAM, peak 55 °C.
It writes `results/latent-taste-activations.npz` (~8.8 MB), which is **gitignored** — the rule and
its reason are in `.gitignore` beside the entry. The dump carries a digest manifest and `--score`
refuses a dump whose manifest does not match the fixtures on disk, so an edited transform produces
a loud error rather than vectors read off prose that no longer exists.

```bash
"$MB" research/quality-measurement/latent_probe.py --extract
```

**Scoring alone** needs no GPU and re-runs in about 30 seconds. It carries the previous file's
`extraction` block forward, so re-scoring does not delete the record of which weights produced the
vectors.

```bash
"$MB" research/quality-measurement/latent_probe.py
```

**Read the verdict, not the table.** The floor families are scored first and a floor that clears
its null voids everything above it — `rewhitespace_sham` does exactly that, which §78.1 and §81 had
already established it would. §87 records the defect in the pre-registration rather than dropping
the floor after the fact, so the file's own `reading` says VOID while the entry explains why the
conclusion is unchanged. And `p0_best_single_DIAGNOSTIC` is a diagnostic: it is not in any bar.

**Why it is fast enough to enumerate an exact null.** The leave-one-scene-out sign test collapses
to a `G x G` Gram matrix, so `2**G` re-runs are `2**G` matrix-vector products rather than `2**G`
refits over 2,560 dimensions. The literal implementation is kept beside the closed form and
`tests/test_latent_probe.py` asserts they agree; the first draft ran the literal one and had not
finished a single family in the time the whole run now takes.

**The conversion strata and the cross-family screen** were added after the first run, so a dump
made before them fails the manifest check loudly rather than scoring a subset. `--extract` covers
282 texts once §79's corpus is present; without it the run is 190 and `conversion_arm` reports
NOT RUN with the rebuild command. The screen is its own module and needs ollama rather than torch:

```bash
uv run python research/quality-measurement/latent_crossfamily.py --models qwen3:14b gemma3:12b --personas 4
```

It reports positional bias only. Win rates are withheld for any candidate whose **bias** falls
outside the 0.40-0.60 band. Do not remove the withholding to "just see" the number; that is the
reading §83, §85 and §79.1 each had to void.

~~which on this material is every current local model tried — `gemma3:4b` picks the first slot 32
times out of 32.~~ **Both halves of that sentence are wrong and both were corrected by
measurement.** §87.3 records the first: `gemma3:4b` *decided* only 11 of its 32 comparisons and
picked the first slot on all eleven, which is a judge that mostly abstains rather than one that
answers 32 slots. §89 records the second: `qwen3:14b` reads 0.5625 and `gemma3:12b` 0.4531, both
inside the band, so "every local model is outside the band" stopped being true the day two larger
ones were pulled.

**Read the `readings` block, not the `status`, and the reason is §89.** Seating four personas buys
four times the comparisons and not four times the evidence: `qwen3:14b` returned **one distinct
answer vector across all four personas**, byte-identical, so its 64 comparisons are 16 independent
decisions. The independent unit is the `(pair, orientation)` cell and personas are replicates on
it, so an 8-pair fixture yields 16 cells and **no judge that ignores personas can reach the
30-decision floor on this material at all**. Both readings print; neither candidate is eligible
under the corrected one.

**Track S and V's judge-free arms** need neither GPU nor quota, so they run under either
interpreter and belong with the panel runs above.

```bash
uv run python research/quality-measurement/latent_support.py
```

**The GPU governor is not optional even here.** This run is two orders of magnitude shorter than
the one that took the machine down, and it imports `cdg_battery.throttle` anyway — same 72/66
hysteresis, same three-failed-reads tolerance, `--rest-ratio` defaulting to the measured-safe 3.0.
The run never reached the pause threshold; that is the outcome the governor is for, not evidence it
was unnecessary. This box hard-shut-down again on 2026-08-19 during this directive's session.

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

## Promises and payoffs, and the budgeted reader — §94

Four modules landed together and three of them have a free leg that must run first. The rule
they share is the one this file already records twice: **run the arithmetic before the calls or
after them, never during**. Everything below with `--transport ollama` touches the 4090 and
carries the duty-cycle and temperature governor; everything with `--selftest` or `--dry-run` is
CPU-only, and starting one of those beside a live elicitation is the combination that took this
workstation down on 2026-08-19.

### W1 — what kinds of debt the summariser actually reports

The derivation behind `domain/promises.PROMISE_KINDS`. Two arms per scene: the **constrained**
arm sends the shipped schema, whose `kind` is an enum and can therefore only prune; the **open**
arm drops the enum and is the only arm a nomination can come from. 10 scenes x 3 samples x 2
arms = 60 calls, about 25 minutes on a 14B local model.

```bash
uv run python research/quality-measurement/promise_kinds.py --selftest
```

```bash
uv run python research/quality-measurement/promise_kinds.py --yes --model qwen3:14b
```

```bash
uv run python research/quality-measurement/promise_kinds.py --yes --model gemma3:12b --cache promise-kinds-gemma-raw.jsonl --out promise-kinds-gemma.json
```

**Read the `readings` block, not `frozen_set`.** The registered rule takes the intersection of
the two arms, and running it is what showed the rule is wrong: the open arm has a free
vocabulary, so a registered kind can be absent from it because the model chose a synonym. The
defect is recorded in the pre-registration rather than dropped after the fact (§87's precedent),
and the corrected reading prints beside it as a proposal an operator freezes, not as a result.

### W3 — can a reader name a cadence difference?

E6's byte-frozen question, imported from `domain/discrimination.py`, over three payoff cadences
of the same span. **The premise is checked before any call**: `certify` refuses to run if the
three variants do not carry identical words, so a manipulation that stopped being about
placement fails loudly instead of reporting a rate.

```bash
uv run python research/quality-measurement/cadence_discrimination.py --selftest
```

```bash
uv run python research/quality-measurement/cadence_discrimination.py --yes --model qwen3:14b
```

Both controls ride every batch and either one firing makes the batch VOID. A NAMES_CADENCE
verdict makes cadence a **nominated** axis and nothing more — `domain/axes.py`'s admission path
still wants a counter, a validation on fresh pairs, and a reader direction.

### W4 — did the payoff land?

```bash
uv run python research/quality-measurement/payoff_landing.py --selftest
```

```bash
uv run python research/quality-measurement/payoff_landing.py --yes --book-db $TOLL
```

**Two arms have no substrate and the module says so on every run.** The only promise ledger in
this repository holds 32 promises, all open, none paid, so the `paid` and `mismatched` arms
cannot be built. What runs is the false-positive half — does the instrument name a matching debt
when the ledger says nothing was settled — which is cheap and can kill the instrument before its
expensive half is bought. The verdict stays NOT VALIDATED until both a ledger with payments and
an owner-read set exist; `--emit-owner-sheet` writes the blind sheet for the second.

### Part A — the Budgeted Continuation Reader

**Three free legs, in this order.** The second is the argument that the declared bands can be
met at all, and it is the one that has caught seven prior declarations in this project.

```bash
uv run python research/quality-measurement/bcr.py --selftest
```

```bash
uv run python research/quality-measurement/bcr.py --attainability
```

```bash
uv run python research/quality-measurement/bcr.py --dry-run --seat
```

Then seating, which is `BUDGET` sequential calls per session — 3 shelves x 3 replicates x 2
orientations x 12 fetches = 216 calls:

```bash
uv run python research/quality-measurement/bcr.py --seat --model qwen3:14b --yes
```

And the battery, which is far larger: five families x four doses x replicates x two
orientations, at twelve calls each. Size it with `--families` and `--doses` before running it
whole, and expect hours rather than minutes under the governor.

```bash
uv run python research/quality-measurement/bcr.py --battery --model qwen3:14b --families paragraph_shuffle --yes
```

**No model can be seated on this corpus and the module refuses to say otherwise.** V1's variance
floor needs twenty own-generated texts of 3,600+ words and D2's transplant check needs a second
own-generated book as donor; this repository holds one book of 10,049 words. Both print NOT RUN
with their price, and `seated` is false while either is unrun — transplant-blindness is a
declared kill, and an unasked kill is not a passed one.

### The BCR model screen, and why it costs six sessions instead of seventy-two

**Run the pilot before the seating, on every candidate family.** Six sessions — three shelves,
both orientations, one replicate — is 72 calls and about five minutes per family, and on
2026-08-19 it disqualified two of four before a seating budget was spent:

```bash
uv run python research/quality-measurement/bcr.py --seat --model qwen3:14b --replicates 1 --yes --cache bcr-pilot.jsonl --out bcr-pilot.json
```

    qwen3:14b     ABABABABABAB every session   P5 FAIL   taking turns
    gemma3:12b    AAAAAAAAAAAA every session   P5 FAIL   never leaves slot A
    phi4:latest   all-in per session           P5 PASS   the one live candidate
    gpt-oss:20b   no answer at all             NOT RUN   broken install, not a result

**Read P5 first and everything else second.** A fixed-pattern allocator passes the placebo,
both shams and the positional check *perfectly* — a strict alternator spends exactly half its
budget on each side of every shelf — so the other four controls say nothing until P5 has held.
`gpt-oss:20b`'s zero is a local install returning `tensor "blk.0.ffn_down_exps.weight" size
overflow`, and §87.3's rule applies: NOT SCREENABLE is its own state, never folded into
"ineligible".

Then the seating, on the survivors only. 12 replicates is 24 sessions per control arm, which is
the count `--attainability` supports — at 16 an unbiased reader fails its own control almost a
quarter of the time:

```bash
uv run python research/quality-measurement/bcr.py --seat --model phi4:latest --replicates 12 --yes --cache bcr-seat-phi4.jsonl --out bcr-seat-phi4.json
```

864 calls, roughly an hour under the governor. The cache is per fetch, so an interrupted run
resumes for free — which is the checkpoint-per-unit rule this box needs.
