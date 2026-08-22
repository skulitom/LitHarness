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

**After upgrading `claude`, re-run the CLAUDE.md guard before any paid arm** (stage-0 §109):

```bash
LITHARNESS_LIVE_PROVIDERS=1 uv run pytest tests/test_providers.py -k claude_md_from_the_working_directory -q
```

It spends one haiku call. Every `claude -p` call site here — `providers/cli.py`, `elicit.py`'s
and `force_remote.py`'s `CLI_HARDENING` — carries `--setting-sources user` and a
`claudeMdExcludes` setting so the repository's `CLAUDE.md` never enters a writer's or a judge's
context; one of the two rests on observed rather than documented behaviour, which is why the
outcome is what the test checks. `--bare` is not the answer: it skips keychain reads and logs a
subscription out.

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

864 calls, about two hours under the governor at the measured ~5 calls/min. The cache is per
fetch, so an interrupted run resumes for free — which is the checkpoint-per-unit rule this box
needs.

**Size the arm from `sizing_from_observed`, never from `--attainability`, once a run exists.**
The simulated table draws each session's share as twelve independent coins; a reader that
commits to a pattern for a whole session breaks that assumption completely. Measured on phi4:
session shares of exactly 0.0, 0.5 or 1.0, per-session sd **0.4025** against the simulator's
0.1443, so every control failed as `imprecise` with two of them sitting on a point estimate of
exactly 0.5. `seating.sizing_from_observed` prices the fix from the run's own shares — 64
sessions per arm rather than 24 — and it is a price, not a verdict.

**Read `failure_kind` before reacting to a FAIL.** `imprecise` means the interval still contains
the centre and is merely too wide, which is a batch size to buy; `off_centre` means the reader
has moved, which is a finding about the reader.

## The force programme — §95

Five modules, one shared harness, two pinned local families, **zero solicited judgment of any
kind**. `plan/force-program.md` is the pre-registration and is authoritative for every constant;
this section is the commands. Everything except the FM dry-run needs the GPU and therefore the
**MirrorBench** interpreter — `uv run python` has no torch and no pyarrow.

```bash
export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
```

**Arm the watchdog before any GPU arm, and leave it running.** It is a separate process on
purpose: `force_gpu.Governor` throttles *between* calls and cannot act while the job is inside
one, and a batched 512-token generation is forty seconds of uninterruptible work.

```bash
uv run python research/quality-measurement/thermal_watch.py --interval 10 --log research/quality-measurement/results/thermal-<run>.csv
```

**The thermal story on this box, because it cost two killed runs and one shutdown to learn.**
The default rest ratio is **3.0** — a 25% duty cycle — and it is 3.0 because lowering it to 0.25
to fit the GPU-hour cap is what took the machine down on 2026-08-20. The core-temperature hold
never fired in that run or the two before it: every sample sat between 47 and 65 °C against a
72 °C threshold. Do not read that as "the core is fine, push harder"; read it as "the protection
was not running".

`temperature.gpu.tlimit` looks like the sensor the core governor was missing and **is not usable
on its own**. Measured: the margin fell 13 °C in ten seconds while the core fell 5 °C and the
draw fell 200 W, which nothing thermal does. Both the governor and the watchdog now require a low
margin to **persist** across consecutive samples before it stops anything; the core reading and
the card's own throttle flag are still trusted on one sample. The shutdowns themselves remain
undiagnosed — `nvidia-smi -pl 260` from an Administrator shell is the untried intervention.

**Run these three first, in this order, and read them before spending a GPU-hour.** They cost
nothing and each one has already caught something.

```bash
uv run python research/quality-measurement/force_harness.py
```

The arithmetic, on constructed inputs. It reproduces §89.2's published attainability table
(85/144, 81/137, 43/68, 44/69) or it is wrong, and it derives `MIN_REFUTING_N = 110` rather than
declaring it — the smallest n whose interval bar still demands 0.6000 or less, which is the floor
below which a stratum returns `DEGRADED_STRATUM` instead of a FAIL nobody could have avoided.

```bash
uv run python research/quality-measurement/corpus_leak_audit.py --derived-only
```

The §1.6 extension. The history walk catches a committed excerpt *after* the fact, which in a
public repository is the thing that cannot be undone; this runs on the **working tree** and
answers the question that still has an answer — is `research/quality-measurement/derived/`
ignored, and is nothing under it tracked? Every continuation, retelling and cloze window this
programme produces lands there.

```bash
"$MB" research/quality-measurement/determinism_probe.py --tokens 64
```

**This decides a control's tolerance, so it runs before any force and never after one fails.**
Measured on this box, both families: forward-pass replay and batched sampled continuations are
**bit-exact**, so `placebo_identical` keeps its arithmetic-check role at tolerance `0.0`. If it
ever reads NOISY the placebo is downgraded to an equivalence test against the measured scale and
the weakening is a recorded property of the box.

### F1 — register half-life, the flagship

Pilot first. It buys throughput, the censoring rate and the tie rate, and its **agreement is not
a result** — at n=16 the interval bar demands 13 of 16.

```bash
"$MB" research/quality-measurement/register_halflife.py --families gemma-3-4b --pairs 8 --tokens 384 --sham 8 --placebo 8 --rest-ratio 3.0 --out research/quality-measurement/results/force-f1-pilot.json
```

Then the full corpus, both families. ~670 batched generations per family; the placebo costs
**nothing** because its two sides are byte-identical and the cache is keyed on the text digest.

```bash
"$MB" research/quality-measurement/register_halflife.py --tokens 384 --rest-ratio 3.0
```

**Read `pilot_corrections` in the result file before reading any number.** The first pilot found
the declared anchor censored 97.9% of trajectories — own-generated LitRPG is its own register,
not a neutral centre — and the declared median-over-K tied almost every pair. Both were corrected
on **label-blind** criteria (censoring rate, tie rate) that §2.5 named in advance, and the
pilot's own agreement was discarded.

### F1 on the remote transport — §95.10

F1 is the one arm that can leave this box, because sampling is all it needs. F2 and F3 cannot
follow it: both are built on teacher-forced token logprobs and **the Messages API exposes none**.

Smoke first, always. It goes through the real plumbing — transport, ledger, cache key, the
downgraded placebo — and the first one died on a `KeyError` after thirteen seeds, for about twenty
cents, on a bug that would otherwise have surfaced hours into a fifty-two-dollar arm.

```bash
uv run python research/quality-measurement/register_halflife.py --families haiku-4-5 --pairs 1 --k 2 --sham 1 --placebo 1 --ceiling-usd 3.0 --out research/quality-measurement/results/force-f1-haiku-smoke.json
```

Then the full arm. **Do not run a second `claude -p` job beside it** — §89.5 records 390 transport
failures from exactly that. Workers *inside* the job are fine; three is what turns a 21-hour
serial run into seven hours, and the K replicates of a seed stay sequential so Claude Code's
26k-token prefix is written once and read seven times.

```bash
uv run python research/quality-measurement/register_halflife.py --families haiku-4-5 --sham 60 --placebo 24 --ceiling-usd 55
```

**Read the `ledger` block before the verdict.** It carries spend, calls, cache reads and writes,
and thinking tokens. `force_remote.Ledger` stops the run *at* the ceiling rather than reporting an
overrun afterwards; everything bought is cached, so a stopped run resumes for free.

**Read `placebo_identical.kind` too.** On this transport it is `equivalence`, not `exact` — there
is no seed parameter, so byte-identical sides cannot produce byte-identical outputs and the
placebo is read the way a sham is. §1.7 pre-registered that branch; it is still weaker, and a
result file that does not say so reads exactly like one that had the strong control.

### F2 — retention under distance

The cheap arm: twelve teacher-forced passes per pair per family, nothing sampled. ~2.6 s a pass.

```bash
"$MB" research/quality-measurement/retention_distance.py --rest-ratio 3.0
```

**A SPLIT_FAMILY here may be architectural**, and the size of that worry changed on 2026-08-20.
`gemma-3-4b` attends 1,024 tokens on five layers in six. The retired `qwen2.5-3b` was fully global
on all 36 layers, so at D=8k the two families routed long-range information through very different
amounts of the network and an architectural split was a live alternative to a lineage one. Its
replacement `qwen3.5-4b` is **hybrid too** — 8 full-attention layers of 32 — so the two pinned
families are now closer in shape, and a SPLIT_FAMILY is correspondingly more likely to be about
lineage than about routing. Pre-registered in `force_gpu.ATTENTION_SHAPE` before the first pass,
and printed in every F2 and F3 result.

### F3 — compression progress

Survey first; it walks twelve parquet shards for metadata only and needs no GPU. **Do not run it
while a GPU arm is running** — CPU load beside GPU load is what took this box down once already.

```bash
"$MB" research/quality-measurement/compression_progress.py --survey-only
```

```bash
"$MB" research/quality-measurement/compression_progress.py --rest-ratio 3.0
```

The run reads `--max-fictions` (default 200) **before** pairing, so the command above builds 64
pairs — 41 aligned and 23 crossed. The survey prints that shape and the uncapped one side by
side; the difference is the cap and not a discrepancy. At every shape this substrate yields, the
interval bar demands 0.6017 or more, so **F3 can PASS and cannot FAIL** and a miss reads
`INSUFFICIENT_N` (§95.15).

Both §1.3 controls ride this arm and cost forward passes: `--controls` (default 20) sets how many
fictions carry them. The placebo re-scores a chapter list through a replicate cache key — an
actual second set of forward passes over byte-identical input, not a dictionary lookup — and the
sham scores a re-whitespaced copy of the same fiction. Unlike F1's, **this sham can fail**: F3's
statistic is token-level NLL and re-whitespacing changes tokenisation, so a PASS here is evidence
rather than a restatement of a feature space's blindness.

### FX — transmission chains, pilot only

```bash
"$MB" research/quality-measurement/transmission_chains.py --rest-ratio 3.0
```

At n=8 the interval bar demands 8 of 8, so **the pilot cannot clear a bar and is not asked to**.
Read `kill_conditions_fired`, not an agreement.

### Reading the programme's state — one command

Four tracks across two transports, several refusal states and a gated market: opening six files
in the right order is not a reporting method. This collects them and prints the table, and it
**computes nothing** — every verdict was decided by the module that produced it under bars
declared before that module ran, and a reporter that recomputed one would be a second
implementation of the bars.

```bash
uv run python research/quality-measurement/force_report.py
```

When a combining rule changes after a run was scored, the committed artifacts hold a stale
headline. Recompute each one's `combined` and `force_verdict` from its stored `per_family` — the
per-family stratum readings are never touched, and a `WITHDRAWN` artifact is skipped because its
headline is a retraction rather than a combining step:

```bash
uv run python research/quality-measurement/force_report.py --reassemble
```

Dry run by default; add `--apply` to rewrite. Each rewritten file records the before-and-after
under `reassembled`, so the change is legible in the artifact and not only in the console.

`NOT_RUN`, `SURVEY_ONLY`, `NOT_SCREENABLE`, `DEGRADED_STRATUM`, `INSUFFICIENT_N`,
`INERT_GENERATOR`, `SPLIT_FAMILY` and `VOID` print as themselves. A table that collapsed them
into pass/fail would be the exact failure §1.5's states exist to prevent.

### FM — the market, gated

No GPU, no quota, no bets. The gate is a force clearing §1.2's bars, and until it opens this
ships the mechanism and the null through it.

```bash
uv run python research/quality-measurement/force_market.py --dry-run
```

The dry-run's load-bearing line is the last one: a prose-blind followers rule scores
**−0.2877** mean log score in `aligned` and **−1.3863** in `crossed`, ending on bankrolls of
448.3 and 8.2. That is §79's two-stratum design working — and the reason a market run on one
stratum would promote a popularity proxy and call it taste.

## Royal Road platform priors — D1P, §104

`plan/royalroad-platform-priors.md` is the pre-registration and is authoritative for every
constant; this section is the commands. **Nothing here has been run**: the module was built and
its free legs exercised, and no variant has been generated.

**Read the ordering before anything else.** D1P families are *hypotheses*, not certified damage,
so a family that moves nothing on an unseated reader is indistinguishable from a reader that
perceives nothing. **D1 on certified damage runs first and seats the reader; D1P runs second.**
The module's `PRE_REGISTRATION["runs_only_on"]` carries the rule into every artifact.

The two free legs, in this order. The selftest is the argument that the dose algebra holds, and
it also **recomputes the attainability row the confirmatory bar is stated at** — it fails if
0.15 stops being reachable at the six-family adjusted level, which is the check that decided the
bar was 0.15 and not 0.10.

```bash
uv run python research/quality-measurement/platform_priors.py --selftest
```

```bash
uv run python research/quality-measurement/platform_priors.py
```

The second prints the plan and spends nothing: 10 scenes x 7 arms = 70 generations, about
$16.21 at §85's measured rate, and the registration digest. Then, on an operator signature:

```bash
uv run python research/quality-measurement/platform_priors.py --generate --yes --certify
```

`--ceiling-usd` defaults to 25 and stops the run **at** the ceiling rather than reporting an
overrun afterwards. The cache is per generation and digest-keyed, so an interrupted run resumes
for free — the checkpoint-per-unit rule this box needs. Run it alone: §89.5 records 390 transport
failures from two `claude -p` jobs beside each other, and this one is deliberately sequential.

**Read `by_family` before anything else in the result file, and read it as a statement about the
manipulation.** A certified family is one whose variants are what they say they are — the rungs
are distinct and nested, the signature counter moved further than the placebo's drift, the
protected spans survived, and the insert lane lost no original paragraph. It says nothing about
whether the platform claim holds.

`--certify` alone re-scores the existing cache and costs nothing, which is the command to run
after touching a matcher or a ladder: the pre-registration digest changes with it, and a result
file whose digest differs from the module's came from a different instrument.

**The battery is not wired to `bcr`'s CLI and the module says so.** `bcr.battery_shelves`
iterates the frozen `D1_FAMILIES` tuple, so `register()` installing into `ablate.BY_KEY` is not
enough on its own. `platform_priors.shelves(variants, scenes)` returns `bcr.Shelf` objects at
book grain with `arm="D1P"` and a `skipped` list carrying every drop with its reason; wiring them
into `bcr.play` is one additive line, left to the session that runs the battery because `bcr.py`
is shared with parallel sessions.

**The interpreter is `uv run python`, not MirrorBench, and that is the two-interpreter rule
working rather than an exception to it.** MirrorBench is for the arms that read a model's
internals and need torch — the latent probe, the force programme. This module calls `claude -p`
through `writer_states.Generator` and computes regex counters, exactly like
`repair_generation.py`, so it wants the repo's own environment. The D1P *sessions* that consume
its variants are a different matter: they run on the local reader under the duty-cycle governor
and belong with `bcr.py`'s commands above.


## The comic-beat census — located levity, and what it costs to be sure of it

`comic-beats-results.md` carries every number and is authoritative; this section is the commands
and the cost as measured. **No bar is declared anywhere in this programme, nothing it produces
reaches a prompt, a directive or the axis registry, and nothing under `src/` moved.**

**The selftest gates everything and it is free.** Schema shape, the closed kind set, anchor
findability on synthetic text, the sign-test arithmetic, the strip arm's readings, the revision
certificates, and last the byte-freeze: `registration_digest()` must still equal `FROZEN_DIGEST`
(`d3200ddad172e4854b70`). A result file whose digest differs came from a different instrument and
every arm refuses to read one.

```bash
uv run python research/quality-measurement/comic_beats.py --selftest
```

**The draw crosses interpreters as a gitignored file.** The parquet shards are MirrorBench's and
the transport is the repo's, so `--dump` runs there and writes
`derived/comic-beats-royalroad.jsonl` — ids, cohort, covariates and text, local-only, under the
root `corpus_leak_audit.py` already guards. One chapter per story, chosen by digest, so re-running
reproduces the same 249 chapters from the same pinned snapshot.

```bash
C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/comic_beats.py --dump
```

**Price before you run.** `--price N` runs N calls spread across the chapter-length range, writes
a price file rather than a census, and projects the rest of the substrate from a least-squares fit
of measured price against chapter length. The calls land in the census arm's own cache, so the
census replays them for nothing. Eight calls projected the RoyalRoad census at $25.71; it came in
at $23.60.

```bash
uv run python research/quality-measurement/comic_beats.py --substrate royalroad --arm census --price 8 --yes
```

**The arms are read in order and each refuses to run out of it.** `repeat`, `sham` and `strip`
read the census's result file for their subsets — the strip subset is the census's own top decile
and the noise floor has to cover it. `--dry-run` needs no `--yes`, writes to its own `-dry` files,
and cannot touch a paid arm's results.

```bash
uv run python research/quality-measurement/comic_beats.py --substrate local --arm census --yes --workers 3
```

Then `--arm repeat`, `--arm sham`, `--arm strip`, and the same four on `--substrate royalroad`.
`--substrate report` merges them and spends nothing, so it is safe to re-run after any analysis
change. In a linked worktree pass `--library` and `--toll`: `book-library/` and `exports/` are
gitignored build products that live in the primary checkout, and a loader that silently found
nothing would report a census of zero chapters as a measurement.

**Cost as measured: $68.99 equivalent for 551 dispatched calls over about eight hours** at three
workers, one arm at a time. RoyalRoad $56.50 (census $23.60, repeat $6.16, sham $6.04, strip
locator $5.30, strip revisions $15.40); own prose $12.49. The locator fits
`$0.0732 + $0.01525 per 1k words`, which is about eleven cents for a RoyalRoad chapter; a strip and
placebo pair on the writer tier is $1.28 for a 4,151-word chapter.

**Deliberation depth is the transport's and it is the dominant cost.** `claude -p` runs with
thinking on, so most of each answer's output tokens are thinking tokens — which is why a locator
call on a 2,264-word chapter costs eleven cents rather than one. It is constant across every arm,
so no comparison is confounded by it, and no number is comparable to a run made with a different
local install.

**Four chapters of 249 cannot be sent at all, and four more timed out.** A rendered `claude -p`
command line reaching 32,767 characters is refused by Windows with WinError 206;
`CLI_COMMAND_BUDGET` measures the rendered length with `subprocess.list2cmdline` and excludes those
chapters **before** the call, counted and printed, rather than sending them and reading a transport
error indistinguishable from a broken install. The 300-second `CLI_TIMEOUT_SECONDS` is the other
censor and it is **beat-count correlated** — a chapter with more located beats generates more
thinking — so it bites the top of the distribution. Reappraisal chapter 2 timed out twice at three
workers and returned at one; **drop to `--workers 1` for a unit that keeps timing out** rather than
retrying at the same concurrency.

**Recover transport failures, but never by re-running a census.** A transport failure is
deliberately not cached, so re-running an arm replays everything that answered and re-issues only
what did not. That is safe for `repeat`, `sham` and `strip`. It is **not** safe for `census`:
recovering a chapter changes `scoreable`, which changes the top decile, which changes
`strip_subset`, and would strand a strip arm already paid for. Four lost census chapters were
reported as lost for exactly that reason.

**One arm at a time, three workers.** §89.5 recorded 390 transport failures from two `claude -p`
jobs beside each other; this programme ran at three workers beside a `litharness forge` job and
took 11 transport failures in 551 calls, which is what that costs. A dedicated cache per arm —
`Elicitor`'s write lock is per process — and a PID lock beside the results so a second launch
refuses. Never wrap a run in `timeout`. Stdout is buffered, so the cache JSONL is the progress bar.

## Chapter endings — the locator and the census, §108

**Free, deterministic, no model and no `claude -p`.** Three passes, two interpreters, and only the
middle one needs the other venv. Under two minutes end to end.

```bash
uv run python research/quality-measurement/chapter_endings.py --substrate local
```

```bash
C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/chapter_endings.py --substrate royalroad
```

```bash
uv run python research/quality-measurement/chapter_endings.py --substrate report
```

Each of the first two writes its JSON beside the script; `--substrate report` merges them and
writes nothing, so it is safe to re-run after any analysis change. `--substrate report` with no
`chapter-endings-royalroad.json` present reports that half as **NOT RUN** with the reason rather
than merging a hole. `selftest()` runs the locator's own cases on every invocation, which is where
its behaviour is pinned: `tests/` may not import from `research/`.

**Draw per shard, not per corpus.** `corpus_io.royalroad_chapters` streams shard 3 then shard 30
under one global `limit`, so any limit below shard 3's LitRPG population returns **no pre-2023
chapters at all** — two 2025 cohorts, and silently no control era, which looks exactly like a
corpus holding no old chapters. `run_royalroad` splits the budget across shards for that reason.
The first run of this census got it wrong and reported two cohorts; the numbers in
`chapter-endings-census.md` are the corrected draw.

**The locator's blind spot, priced.** `axes.strip_system` sees bracketed all-caps tags and bold
spans. The 21-book fitness corpus has neither — its system voice is *unbracketed* ALL-CAPS — so
`pct_last_line_is_system` under-counts there. A one-off uppercase probe bounds it at 1 unit in 144
on this corpus. The probe is not committed: a threshold on capitalisation is half a classifier.
