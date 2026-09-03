# Handoff: experiments with simulated readers, under the axioms

**Scope:** a brief for one worktree session that will spend model budget. Read
`CLAUDE.md` first, then in this order: `research/quality-measurement/BRIEF.md` (the
refutation ledger: what has already been tried and died), `EPISTEMIC_GOVERNANCE.md` (what
may become evidence and the `CONJECTURE → REGISTERED → OBSERVED → SUPPORTED / REFUTED →
QUALIFIED` meanings), `RUNBOOK.md` (how an arm is run on this box), and stage-0 §126, §140,
§141, §144 and §195.5 (the product objective, the position-bias finding, the panel
voidings, the reader-architecture redirection). This brief is deleted once its results have
a canonical home.

## The goal, in one sentence

Find a simulated-reader mechanism whose verdicts survive the controls that have voided
every panel so far, so that the project's objective — fiction a defined simulated audience
continues and recommends (§126) — has an instrument that can say a chapter moved.

## The axioms that bound every experiment here (verbatim in spirit; the pointer is the authority)

- **No solicited human judgment, ever** (stage-0 §95): no hired readers, no labels, no
  panels of people, not the operator as data. The operator's reads are defect harvests.
- **LLM-only measurement**, and a role that judges needs a validity licence; a role that
  generates needs containment (§61(5), §105.1, §107.5). Nothing built here may rank or
  select among candidates on the generation side.
- **Declare no bar** without the four attainability checks (range at the real n, direction,
  independent unit, non-empty subgroup); distributions before bars; a pre-registered null
  is a result (§61, §81, §85, §87, §89).
- **Raw reader answers never reach scene drafting or story planning.** The live path is
  `application/editorial.py`; the loop is wired and inert until a mechanism is qualified.
- **RS1**: measurement corpora stay on the measurement side; the operator's shelf
  exemplars (§196) are out of measurement for any book that saw them (PREREG §5f).
- **Agent prose is not evidence.** A finding is a content-addressed record under
  `research/quality-measurement/`, registered before the spend.

## What is already built and where it stands (do not rebuild)

- **`fcr.v0`**, the feed-continuation instrument (§122): costed continuation with feed and
  skim; unseated; the fitness shelf is eleven to twelve chunks.
- **`anticipation.v0`** (§124): mid-chapter futures, code-only scorers, a paid run pending.
- **The sim-readership backtest** (§123): 2,014 pairs, conditional primary, cutoff-clean
  set empty; the calibration pilot was registered and never run. Distributional
  reweighting against unsolicited aggregates is the admissible half of the SYN-DIGITS
  reading (§106); individual-level calibration is closed twice.
- **The panel and its controls** (§140, §141, §195.5): a haiku panel preferred our surface
  over *The Primal Hunter* 20/20 in both orders and preferred shuffled-ours the same, so
  every ours-versus-summit share was surface; the verdict channel is position over text by
  a factor recorded in §87–§89. Any new panel runs its shuffle and position-swap controls
  before any pair it cares about.
- **The readers' order control** (`research/quality-measurement/readers-order-control/`):
  both lanes read content, not order; carry-on saturated. Owed from it: an order-recovery
  instrument and a cost that bites.
- **The reassembly instrument** (`research/quality-measurement/reassembly/`).
- **The tells counter** (§199 to §199.8): a located, family-by-family count on narration;
  ours ran three to ten times the shelf on every family before the pass and reached the
  shelf's rate on three of five families after it. It is a defect instrument, not a reader.

## The experiments, in the order the ledger's history recommends (deliverable = one registered arm at a time)

Each experiment is a `PREREG.md` before spend (the question, the pairs, the controls, the
ceilings in dollars and calls, the abstention rules, what null looks like), one arm at a
time on this box, `transport_failures` read before any verdict, and a `FINDINGS.md` in the
house form afterwards whatever the result. A null is a result and is written up.

1. **A cost that bites.** The order control found readers who read content rather than
   order and never stop. Register an instrument where continuing costs the simulated reader
   something it can run out of (the fitness shelf of `fcr.v0` is the substrate; the cost is
   the new part), and measure whether the stop point moves with a manipulation the ledger
   already owns (the D1P families of §104, or the shuffle). If it does not move under any
   manipulation, that is the null and the direction closes.
2. **Order recovery.** Given a chapter's chunks shuffled, can a simulated reader put them
   back, and does the recovery rate separate chapters the operator's reads called broken
   from ones they did not (his reads are harvests; the separation is a description, not a
   label). This is the owed instrument from the order control; it asks about structure
   without asking for a preference, which is the shape (E6, "name the difference") that
   survived where preference (E1, E2) was void (§87–§89).
3. **The calibration pilot of the backtest** (§123), as registered, with the distributional
   half only. It was gated on an operator go; this brief is that go for a bounded pilot
   under the registered ceilings, and the result is reported whatever it is.
4. **The anticipation probe's paid run** (§124), under its registration, with the
   destake-versus-matched control.
5. **Only after 1–4 have results:** a reader-architecture proposal, if any of them
   produced a signal that survived its controls. The §144 redirection says the search is for
   a reader architecture and not a metric; a proposal here names the mechanism, its
   controls, and the editorial intervention it would feed through
   `application/editorial.py`, and asks for qualification before it touches a book.

## What this brief refuses

- Any human reader in any role, including the operator as a rater.
- A panel pair without its shuffle and position-swap controls, and any share read from a
  panel whose controls were not run first.
- A reader answer reaching a writer. The editorial control plane is the only path and it
  stays inert until a mechanism is qualified.
- Hill-climbing prose on a reader score (§105's import ban stands).
- A bar declared from one run.

## Spend and box rules (binding)

- Ceilings live in each `PREREG.md`; nothing runs without one. The `claude -p` transport
  fails silently under box load: one CLI arm at a time across **all** sessions, no full
  suite or `mypy` beside an arm, every GPU arm beside the `thermal_watch.py` sidecar, and
  one sustained CPU job at a time (the box has hard-shut-down twice; `CLAUDE.md`, "Running
  things on this box"). Check the process list before launching. Replay caches key on the
  text digest; point `--cache` at prior raw JSONLs to replay identical requests for free.
- Every `claude -p` call site carries the two hardening flags (§109); never `--bare`.
- `git status` and `git diff` on shared documents before editing; commit only your own
  files; push after every commit; never `--force`; stage-0 numbers claimed with the command
  in `CLAUDE.md` across `main` and every worktree.

## Done looks like

Four registered arms with findings (nulls included), the refutation ledger in `BRIEF.md`
updated by pointer, any surviving signal written as a qualification proposal and not as a
score, and this brief deleted in the last commit with its results pointed at from the
ledger.
