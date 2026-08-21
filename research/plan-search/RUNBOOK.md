# Plan-search acceptance experiment (§61 Add 3): the K=3 runbook

> **RETIRED 2026-08-19 — this document describes a channel that is permanently closed.**
> The **scope axiom** ([stage-0 §95](../../plan/stage-0-decisions.md)) is *no solicited human judgment,
> ever — not hired, not operator, not one blinded pair*, and §95.1 retires the `PREFERENCE`
> class for machines at every grain. Nothing below may be executed. It is kept because the
> reasoning is the record of what was tried and why it was refused, and because several of its
> pre-registrations — clustered intervals, a declared tie policy, exclusion on recognition, a
> comparator frame fixed in advance — carried over intact to the behavioural instruments that
> replaced it (`force-program.md`, ledger §95–§102).

Operator procedure, not code. The code ships the mechanism — `plan_search` tournaments,
`span_select` selection, the dormant judge path — and this runbook is the experiment that
decides whether the mechanism earns its keep. Nothing below runs automatically; every step
spends live quota or a reader's paid time, and each is an operator decision.

## The claim under test

Plan-level search — K alternative beat-plans per span, each drafted, the drafts judged
pairwise, one committed — produces a book readers prefer over the same pipeline without
search, at equal generator and equal budget per accepted scene.

## The §61 acceptance criterion, verbatim

From `plan/stage-0-decisions.md` §61, the bar every quality claim in this project now
reduces to:

> "superhuman" means the lower bound of a 95% confidence interval on blinded,
> position-swapped pairwise win rate against matched published-human prose exceeds 0.5,
> judged by paid genre readers.

And the exit this experiment feeds, from PLAN.md Stage 4, verbatim:

> **Exit:** a promotable calibration row exists under §59's bound and a selection
> mechanism consumes preference evidence (§61 Add 3); Book One produced under them.

This experiment is the *internal* form of that bar: search arm vs no-search arm, our prose
against our prose, so no human comparator is present and no superiority claim is made. What
it can establish is whether search moves pairwise preference at all — the precondition for
spending the superiority frame's paid readers on a searched book.

## The arms

Two books from one premise, one generator, one prompt profile, one budget policy:

- **Search arm:** `litharness tick` driven with `--plan-search` (or
  `LITHARNESS_PLAN_SEARCH=1`). Every unlocked span drafts by tournament at the default
  K=3 (`PlanSearchPolicy`); winners are selected by the human path unless a judge
  calibration exists (none does today).
- **Control arm:** the identical invocation without the flag. This is exactly the
  behaviour that shipped before Add 3 existed, which is what makes it a control nobody
  has to reconstruct.

Run the arms on separate databases. The arms must not share a book id: pair identity is
content-derived, and a shared store would let cross-arm pairs be drawn by accident before
the protocol below declares them.

## The protocol declaration

Declare the comparison frame BEFORE the first judgment is collected (§61 pre-registration
2 and 4: the tie policy before the first judgment, the frame before the first reader is
paid — the frame *is* the claim). For this experiment the frame is internal:

- Use `litharness protocol` to declare a scene-grain frame stating: both passages were
  written by this system from the same premise, one under plan-level search and one
  without; judged for preference between pipelines, not against any human comparator.
- Tie policy: `drop` — a tie between the arms selects neither.
- Draw the cross-arm pairs with `litharness pair-draw --protocol <id>` after importing
  each arm's scenes; judge blind via `litharness pairs` / `pair-judge`, or export for
  paid readers via `pair-export` / `pair-import`.

Do not reuse `internal-v0` (the built-in tournament frame): tournament sibling pairs and
cross-arm experiment pairs are different questions, and pooling them under one protocol id
would let tournament verdicts count toward the experiment's n.

## Size and analysis

- **n ≥ 50 blinded pairwise judgments**, both orientations of every drawn pair, before
  any number is read. §61's sizing arithmetic applies unchanged: at a true rate of 0.60,
  roughly 100-150 decisive judgments clear a 0.5 bound; a thin margin is expensive to
  certify, and pretending otherwise is how the bar gets quietly weakened.
- Analysis is `win_rate_lower_bound` — the two-way cluster bootstrap over readers x
  pairs, ties dropped per the declared policy — never the point estimate alone (§59: 14
  of 17 reads as 0.82 and bounds at 0.566).
- Recognition flags are recorded and excluded per §61 pre-registration 3, even though
  recognition of our own prose should be rare; the exclusion count is itself a finding.
- If more than one searched book could have been reported, divide the level by the
  candidate count (§61 pre-registration 5).

## What a result licenses

- A bound above 0.5 for the search arm licenses spending the *external* frame's paid
  readers on a searched book, and is the evidence base from which a
  `judge.span_select.v0` PREFERENCE calibration could later be measured on the K-sibling
  winner-prediction task itself (BRIEF §6.6: passive flag precision cannot license the
  judge — selection shifts the deployment distribution, so the calibration must be on the
  selection task).
- A bound at or below 0.5 lands in the decision ledger like every other dead instrument,
  and the tournament machinery stays what it is today: dormant behind its flag.
