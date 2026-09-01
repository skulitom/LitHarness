# The loop is promoted from read-driven to instrument-driven, and the operator's read moves to milestones

**Status: OPERATOR DIRECTION, 2026-09-01.** Verbatim:

> *"I was hoping we would have a method of continuously improving the reader - writer -
> architect loop using the RR data. We shouldn't train anything big, just adjust the
> cognitve architechture so that we can optimize on the RR data and then eventually on our
> own generated synthetic data."*

and, on the assessment that this is a promotion of the existing cycle rather than a pivot:
*"ok let's work on making this happen."*

## What this is

The defect-harvest cycle (read → diagnose → structural fix → redraw → gate) already turns;
today it turns only when an operator read fails something. This direction makes it turn on
instruments: every draw gets a code-only scorecard against market references, architecture
variants are compared on settled listings, and the operator reads at MILESTONES (premise,
and the operator-facing final) rather than every iteration. The operator's read remains the
promotion gate; instruments and the exploratory panel steer iterations between reads.

## The three builds, in dependency order

1. **The per-draw scorecard** (keystone). One command running the existing code-only
   battery — progression-cadence v2, number-context v2, sentence statistics, the register
   census's gloss half, cast counts, sheet-contract and beat-satisfaction checks — over one
   book's chapters, printed beside the market reference for each instrument that has one.
   Descriptive rows only: no bar, no aggregate score, no pass/fail (§61's four attainability
   checks stand between any row and a bar). Lives on the research side; `src/litharness/`
   never imports it (CONTRIBUTING's dependency direction; RS1 untouched — derived numbers
   cross, text never does).
2. **The A/B redraw harness.** The settled-listing redraw recipe (pilots 15/18's hand-run
   shape) as a scripted convention: same listing byte-for-byte, fresh store per arm,
   variant A vs B named by the §-entries that differ, scorecards for both, spend and
   §54-style control notes in one result folder. §105's measured null is the standing
   caution written into the harness: variants come from diagnosed defects, never from
   undirected variation.
3. **The exploratory panel column.** The backtest's session machinery pointed at OUR
   drafts: the frozen ten-persona panel reads a draw's chapter pair-wise against the prior
   draw of the same listing, and the preference lands on the scorecard as a column marked
   EXPLORATORY — pilot-grade evidence (0.789 descriptive on RR, controls unsettled), never
   a gate, never alone a reason to ship or kill, and never reaching a prompt (the standing
   axiom on raw reader answers is untouched). Paid per use, small (~P-arm-sized stimuli).

## The anchors, so the loop cannot eat itself

Optimization against our own outputs alone is how a system Goodharts into a corner. The
anchors stay external: the RR-derived distributions (refreshed only through the versioned
instrument channel, v2's pattern), the operator's milestone reads (the §148 harvest
channel, unchanged), and — long-term — real reader behaviour at launch, which the
follower-signal direction already sketches as §126's objective made a running stat.
Synthetic-data optimization inherits these anchors or does not run.

## Governance, restated where it binds

RS1 holds: instruments read corpora; generation reads derived numbers and structure only.
§61(5)/§84 hold: no model ranks candidate books for promotion; the scorecard describes, the
A/B harness lays two descriptions side by side, and a person (or a later qualified
mechanism) decides. §97.1 holds: read quotes stay out of prompts. The §138/§154 clause
discipline governs anything a track is tempted to write into a prompt — the fixes this loop
produces are structural or they are not made. Counts point to canonical homes.

## Anti-scope

No training, no fine-tuning, no persona editing under this note (a reader redesign is its
own registered act). No bar is declared here. The backtest's confirmatory stage stays
paused per its FINDINGS entry and is not revived by this direction.

## Amendment, same day: the adversarial layer (operator direction)

> *"We need to have compentent adverserial testers so that we don't overoptimise on
> something unrelated. i mean adverserial agents, who have to opimize for rejection"*

A variant does not win an A/B by scoring better; it wins by scoring better AND surviving an
adversarial battery built to make the win fail. Two halves:

1. **Mechanical adversaries in the harness** — the backtest's control philosophy
   generalized: the damage arm (a paragraph-shuffled copy of the winning draw — a
   preference or scorecard gain that survives shuffling is surface, not story), the sham
   arm (two windows of the same draw — position/format bias), and axis-specific degeneracy
   checks (a cadence win by furniture spam, a diegesis win by [STATUS] stuffing, a
   sentence-metric win by staccato monotony — each named axis ships with the check for its
   own degenerate maximum).
2. **Rejection-optimized critic agents** — a small versioned roster whose ONLY success
   metric is verified kills: given the winning variant and its scorecard, produce the
   strongest case for rejection. The governance that keeps this honest cuts both ways:
   a critic's prose is never evidence (the standing rule) — every claim must cash out as a
   mechanical demonstration, a line citation the coordinator's gate can check, or an item
   on the operator's recorded defect-family taxonomy — and a verified kill BLOCKS the
   variant while an unverified opinion evaporates. Critics judge nothing and gate nothing
   by preference; they hunt falsifiable defects and are scored on confirmed finds, so
   competence pressure points at rejection, exactly as directed. Their prompts draw on the
   defect-family taxonomy (the read-recurrence map's family names), never on operator
   quotes (§97.1), and their output never reaches a generation prompt (containment).

The binding rule, added to the selection section: **provisional win → adversarial battery →
survived-or-rejected**, with the battery's results in the same experiment folder. The
operator's milestone read remains above all of it.
