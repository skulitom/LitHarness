# Pitch draws: report (2026-10-03)

A description, never a verdict: every number below counts bibles that cleared the hard checks (`money`, `leak`,
`pitch-shape`), which says nothing about whether a bible is good. The rows, traces, call folders and the per-round
analyses are in `$LITHARNESS_HOME/evals/pitch-draws/` (`REPORT.md`, `narrative.md`, `metrics.md`, `vN/`).

## Runs

All 11 briefs at 8 draws each, 88 draws a variant, at medium effort. Intervals are 95% from 2,000 resamples of
the briefs, for the difference between two variants brief by brief. No brief was held out, so the differences are
directional, and the 11 briefs count as about 7 (the four genre-asks share 53-81% of their words).

| variant | prompt | agent | passes | money clean | shape ok |
|---|---|---|---|---|---|
| baseline | main at c23a05a | codex gpt-6.1-sol | 19/88 | 24% | 98% |
| v1 | main at c23a05a | claude opus-5-5 | 23/88 | 30% | 84% |
| v3 | round 1 | codex gpt-6.1-sol | 31/88 | 36% | 97% |
| v4 | rounds 1 and 2 | codex gpt-6.1-sol | 40/88 | 47% | 98% |
| v5 | rounds 1 and 2 | claude opus-5-5 | 21/88 | 45% | 68% |

`v2` is 5 draws by gpt-6-astra, stopped when the operator moved Codex to gpt-6.1-sol (codex-cli 0.160.0).

- **Agents on main's prompt:** Claude minus Codex, +5 points [-9, +16]. The two cannot be told apart.
- **Codex, rounds 1 and 2:** +24 points [+11, +34] against baseline; round 2 alone +10 [-2, +22]. On the five short
  premises, 15 of 40 draws pass against 1.
- **Claude, rounds 1 and 2:** -2 points [-12, +9]. Money-clean rose 16 [+5, +28] and shape-ok fell 16 [-30, -2]
  (bibles over 900 words, the Listing's limits, and People sections the check miscounts).

## What the rounds changed, and why

An Opus analyzer read one variant's transcripts each round (never Claude's) and proposed one change; the operator
approved each diff before it was drawn.

1. **Prize and System.** Asked what the next rank gets him, 69% of baseline bibles answered with a civil standing
   (a key, a registered room, a licence), and the System spoke like the office that grants it. Prize now asks for
   the ability the next rank adds; System for how it looks and what it says. Grants in the Prize fell to 10% of
   draws and an office voice for the System from 89% to 18%.
2. **Threat and People.** The office then moved into the opposition: a Threat that polices his exception, an
   official among his People. Threat now asks for what kills people; People for up to three allies. A policing
   Threat fell from 46 draws to 16 and an office in People from 59 to 17. The bible no longer seats an antagonist
   with a voice in People; the operator accepted that.
3. **Not drawn.** People "allies" to "friends": a ceiling of +8 points against a band of about +/-12, and a story
   cost. What fails now is a long tail: his old life and wants told in pay and rent (Person, under the readership
   direction), the Limits line read as a debt, office words with no field behind them, and grader false positives.

Guardrails held on Codex from baseline to round 2: shape-ok 98% and 98%, leak-clean 98% and 100%, admin words 1.7
and 1.1 a bible, 760 and 764 words, 5,735 and 5,768 tokens, 93 and 100 seconds a draw.

## Grader findings

- `items()` counted each "Want:" and "Talk:" sub-bullet under a named person as another person: 6 of v1's draws
  and 10 of v5's failed "People names more than 3" with three people.
- Word-sense false positives: `council` in a town's name, "court" as a basketball court, "contract" as a verb.
- `leak` refuses a title that echoes the brief's own "sheet" or "ladder", and "Standing", which no prompt holds.

## Spend

445 pitch draws (Codex about 5.7k tokens and 95 s a draw, Claude 4.2k and 42 s), one canary and two model
probes, 0 failed attempts, 4 calls cut off by two stops; three analyzer runs.
