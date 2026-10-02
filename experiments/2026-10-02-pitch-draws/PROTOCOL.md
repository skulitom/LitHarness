# Pitch draws: protocol (2026-10-02)

**Question.** How often does one pitch draw pass its hard checks, which check fails when it does not, and does
that change with the agent or with an edit to what the pitch call sees? The operator asked for an eval of the
pitch stage. It describes and never decides: a passing bible has cleared `money`, `leak` and `pitch-shape` and
nothing more, nothing it prints reaches a model, and the operator's glance at the bible stays the gate.

**Why the pitch.** The 15 stored calls of serial `slot`, re-graded by today's checks: pitch 1 of 5 draws passed
(`money` on "tenant" in 3 draws and "council" in 1, the Listing shape in 2), plan 3 of 3, draft 7 of 7. Only the
pitch has room to move; a draft pass rate would sit at its ceiling.

## Cases (`cases.json`, shown in full in `inputs.md`)

- 11 briefs from past runs, byte-faithful, 14 to 135 words: 5 premises, 2 prior lives, 4 genre asks. None carries
  a word of the pitch money list; the runner refuses one that does, before anything is spent.
- 6 are left out, each with its reason in the file: 4 name a woman as the lead and 1 a pair with a trade premise,
  which the pitch template ("His name", Age 20-29) and the project's direction do not serve; 1 is a near-duplicate
  of a brief that is in (they share 0.85 of their words).
- What makes a case hard: a prior life (a job, a flat, a degree) or a premise near trade or housing invites
  household-money words. Slot drew "tenant" and "council" with no such word in its request.
- There is no expected output: nothing is compared with a reference text.

## One row

One row is one fresh pitch draw of one brief: `serial.new` with the draw cap set to 1, in the variant's own data
home, by the agent named. A brief is drawn `--reps` times in fresh serials, so its draws are independent and none
is adopted for production. This draws one input set more than 3 times on purpose: the cap exists to stop silent
rejection sampling, and here every draw is counted.

The grade is the app's own `checks.hard("pitch", ...)`, as the draw's manifest recorded it:

- `pass`, the headline: no hard failure.
- `money_clean`, `shape_ok`, `leak_clean`: no failure of that family. The pitch prompt states the shape limits
  and, by the prompt policy, names no money word: `shape_ok` is whether an agent kept to what it was told, and
  `money_clean` is how often it brings a household-money word unasked.
- Beside the grade and never in it: tokens, seconds, words, hits on the money list, hits on the admin list. A
  bible can clear `money` by moving to words only the inert admin list holds; that column shows it.

Not a row: an attempt that left no checked answer (a transport fault after 2 retries, a timeout, a refusal, a
reply served by another model). It goes to `errors.jsonl` with its class, and a resume draws it again. Four in a
row stop the run.

## Numbers

- A brief's rate is its share of passing draws; a variant's rate is the mean of its briefs' rates. The brief is
  the independent unit, so intervals are 95% from 2,000 seeded resamples of the briefs, printed from 5 briefs up.
- Two variants are compared brief by brief, by the difference of each brief's two rates, which removes the spread
  between briefs. Planning estimate for 11 briefs at 4 draws each: a difference under about 20 points is within
  noise (worst case sqrt(2 x 0.25 / 44) = 0.11, doubled for 95%). The measured interval replaces this once rows
  exist.
- No bar is declared. The numbers describe.

## What it cannot say

Whether a passing bible is good; anything about plans, drafts or chapters; anything about briefs unlike these 11.
Codex reports neither the model that served a call nor why it stopped, so its rows carry the model that was asked
for, and a clipped Codex answer would count as a shape failure (pitch answers run about 1,400 tokens, far from any
cap). Claude Code's rows are checked against the serving model and a clean stop. Two briefs (`depot-23`,
`owen-arcade`) use "sheet" and "ladder", which `leak` refuses in a title: a `leak` failure there may echo the brief.

## Run

```powershell
python draws.py approve                                # yours to run: records the harness hash; no call
python draws.py run --variant baseline --agent codex   # 44 draws at the default 4 a brief
python draws.py run --variant v1 --agent claude        # 44 draws
python draws.py report                                 # summary.md, recomputed from the rows
```

A variant holds one agent at one harness hash (this runner, `cases.json` and `litharness/*.py`); an edit to any of
them needs a new approval and a new variant. Data: `$LITHARNESS_HOME/evals/pitch-draws/<variant>/` holds the
rows, the traces, the errors and, under `home/`, every draw's serial with its whole call folder. The skill's
`build-report-lite.mjs` turns the same folder into `report.html`.
