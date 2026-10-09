# Chapter draws: protocol (2026-10-09)

**Question.** How often do chapter 1's plan and draft pass their hard checks on their first draw, which check fails
when they do not, and does an edit to the PLAN or DRAFT prompt change that? The operator asked for a climb on the
chapter stages after the pitch climb on Haiku plateaued (2026-10-09). It describes and never decides: a passing chapter
has cleared the hard checks and nothing more, nothing it prints reaches a model, and the operator's read stays the gate.

**Why now.** The operator's reading chapter (`serials/slot-h`, Haiku 5.5 at high effort) needed a plan redraw (three
plans tracked the bible's sleep cost as "sleep debt", which the money check refuses) and a draft redraw (the planned
rise printed too late).

## Inputs

- 44 fixed bibles: the first 4 passing bibles of each of the 11 pitch-draws briefs in pitch-draws `v32` (the climb's
  best pitch prompt), copied once by `prepare` to `$LITHARNESS_HOME/evals/chapter-draws/bibles/` with their sources and
  hashes in `bibles.json`. Fixed inputs let a PLAN or DRAFT edit be compared on the same bibles.
- The brief of each bible's case, and the sheet `serial.new` would build from its Start lines.

## One row

One chapter-1 attempt from one fixed bible in a fresh serial of the variant's own data home: `serial.chapter` with the
draw cap set to 1, so plan, draft and (when the tells counter asks) the rewrite run once each. Graded by the app's own
checks as the manifest recorded them: `plan_pass` (the plan's first draw), `draft_pass` (the draft's first draw, only
when the plan passed), `chapter_pass` (both; the headline). A transport fault after its retries leaves no row and is
logged in `errors.jsonl`. Also recorded: the failing check families, rewrites applied, chapter words, calls, tokens,
seconds.

## Comparisons

A variant's rate is the mean of its briefs' rates; two variants are compared brief by brief with a 95% interval from
2,000 resamples of the 11 briefs (the 11 count as about 7). Keep rule for a climb round: the headline up with its
interval above 0 and no guardrail (words, rewrites, calls) worse outside noise; a winner picked from siblings is
confirmed with more draws. The runner's hash over itself, the bibles and the runtime is approved before a variant
draws (`approve`).

## Scope (operator, 2026-10-09)

Will change: the PLAN and DRAFT prompts (replacing within the 701-word prompt cap) and chapter-check parsing where it
fails a right answer (failing test first). Off limits: the money list ("sleep debt" stays refused), the briefs,
SYSTEM, v32's pitch prompt, and main without the operator's read.
