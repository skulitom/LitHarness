# Pre-registration — a cost that bites: does the costed reader's stop point move when the order goes?

**Registered 2026-09-03, before any cell is bought**, as the first experiment of
`plan/handoff-reader-sims.md`. `research/quality-measurement/cost_that_bites.py` carries the
frozen constants (its `registration_digest()` is printed on every result), the manipulations,
the plan, the runner and the reading; this file is the registration in prose. It is an
instrument-validity measurement under `EPISTEMIC_GOVERNANCE.md`: CONJECTURE → REGISTERED here;
OBSERVED when the cells are on disk; nothing below becomes SUPPORTED by this file, and a null is
a result.

## The question

The readers' order control (`../readers-order-control/FINDINGS.md`, stage-0 §199.1) found both
`readers` lanes carrying on four of four whether the chapter was in order or not, and the
opening-parity panel taking a paragraph-shuffled copy of ours at the ordered copy's rate
(§195.5). In both, continuing cost the reader nothing it could run out of. `fcr.v0` (§122) is
the one reader in this house whose continuing costs something: twenty-four minutes across four
books entered mid-stream, a full read at three minutes and a skim at one, spending forced,
abandonment revealed as the step after which a book gets no further full read. The handoff's
first experiment: point that cost at the manipulation the ledger already owns — the shuffle —
and ask whether the stop point moves. If it does not move under the strongest form of the
shuffle, that is the null and the direction closes for this reader.

## The instrument, unchanged

`fcr.v0` byte for byte: `feed_core`'s registration (its digest is stamped beside this
registration's), `feed_session`'s sequential replayable loop, `feed_substrate`'s loaders and
`feed_controls`' arithmetic. The substrate is the twenty own-drafted fitness books
(`corpora/fitness/fitness-*.db`, §95.9, §122), every one holding eleven or twelve chunks under
the shared chunker against the registered floor of eleven. The seating is
`feed_battery.seating_plan`'s: feed *i* seats book *i* as the target against books *i+1..i+3*
wrapping the pool.

**What is new is the plan.** Each feed's target is shown to the same reader at the same
rotation in three versions, the three competitors identical and intact in all three:

- `intact` — the book as drafted;
- `shuffled` — every paragraph of the whole book in a seeded random order
  (`cost_that_bites.book_shuffle`; a real shuffle seeded from the text, never
  `ablate.paragraph_shuffle`, which at strength 1.0 is one cut in an otherwise ordered book).
  Word-preserving. The reader meets the disorder in the opening — the recap and the entry
  section are random paragraphs from across the book — and in every section it pays for;
- `sham` — `ablate.rewhitespace` at strength 1.0, the standing placebo: not one character of
  any word moves, the layout does. The placebo that has killed instruments before (§78, §81),
  so a reader that moves as far for it as for the shuffle is reading edited-ness.

Twenty feeds x three versions x four rotations = **240 sessions**, one replicate, the
registered prices only. The rotation is the position control: the target sits in the same slot
across the three versions of one session, so a paired difference cannot be a slot difference.
On six feeds the shuffled copy re-chunks to eleven sections where the intact holds twelve
(`--dry-run` lists every feed's counts); both clear the floor, and the budget cannot exhaust
either.

**The reader:** `claude-haiku-4-5`, the house's panel tier, through the `claude -p` transport
with the two hardening flags (§109); one session's turns are rendered as one prompt by
`elicit._flatten_turns`, which the module records as the one place the transport differs from
the SDK form. A different model is a different reader with its own result file, labelled and
never pooled.

## The measurables, all code

Per session (`feed_core.FeedSession`): the target's share of full reads (the primary, eight
reads at most, resolution one eighth, neutral at one quarter for a session of skims only), the
abandonment step (the index of the target's last full read, −1 for never), whether the first
full read went to the target, the skim rate, the per-slot read shares. Per (feed, rotation)
whose three versions are all scorable: the paired differences `intact − shuffled`,
`intact − sham` and `sham − shuffled`, each a percentile bootstrap clustered over feeds
(`bcr.cluster_interval`, seeded from the values, 2,000 resamples) at the registered alpha 0.10.

## The reading, fixed before spend

Preconditions, read first and in this order:

1. `transport_failures` and the exit notes: a session with any unanswered step is reported
   and never scored (`fcr.v0`'s rule). A version with fewer than 75% of its sessions scorable
   is UNREADABLE, and nothing is substituted, retried or filled.
2. `fp5` over every scorable session: the mean across-session standard deviation of each
   slot's read share must exceed 0.05, or the reader is a fixed pattern wearing a budget and
   nothing below is read (§94.6's lesson, encoded in `feed_controls`).
3. At least two feeds with a complete scorable triple, or there is no interval.

Then one decision, assembled in `cost_that_bites.decide` and nowhere else:

| the intervals on `target_read_share` | reading |
| --- | --- |
| `intact − shuffled` strictly above zero **and** `sham − shuffled` strictly above zero | **MOVES_WITH_ORDER**: the costed reader pays less for the book whose order is gone, and pays more for it than for the same book with only its layout changed; a first cell of a cost that bites, n of twenty feeds, never a bar |
| `intact − shuffled` above zero, `sham − shuffled` not | **MOVES_WITH_EDITEDNESS**: the reader moves for surface damage as much as for order; the cost bites but the reader reads surface, §195.5's finding on a third instrument |
| `intact − shuffled` contains zero | **NULL**: the stop point does not move under the strongest order manipulation this house owns, at this n; the direction closes for this reader |
| `intact − shuffled` strictly below zero | **INVERTED**: reported as what it is, never read as a preference for disorder |

The abandonment step and the first-read intervals are reported beside the primary as
descriptions and decide nothing. The per-slot shares are reported as the positional reading and
decide nothing here (the rotation already pairs position away). The skim rate is a diagnostic;
`fp6` (the skim-price control) is not run and no skim-derived number is read.

**The four checks on the reading, done before spend.** Range: a paired difference lives in
[−1, 1] in steps of one eighth. Direction: positive means the reader paid less for the
shuffled book. Unit: the feed (twenty clusters; the four rotations of one feed share its
texts). Non-empty: every feed builds all three versions fault-free at `--dry-run`.

**Attainability, simulated at the real n before anything is bought**
(`cost_that_bites.py --attainability --trials 200`, seed 20260903; the table is committed as
`attainability.json`). Two reader worlds: every session content-driven (one Dirichlet
allocation per session, eight reads on it, the manipulated session keeping the same allocation
with the target's weight scaled down), and `feed_controls`' mixture with six fixed patterns in
eight sessions, which pass `fp5` as a population and cannot move. At the arm's 80 paired
sessions in 20 clusters:

| reader world | target's weight scaled by | mean paired difference | interval above zero |
| --- | --- | --- | --- |
| content-driven | 1.0 (the null) | −0.003 | 0.040 |
| content-driven | 0.75 | +0.060 | 0.875 |
| content-driven | 0.5 | +0.126 | 1.000 |
| content-driven | 0.0 | +0.250 | 1.000 |
| mixture | 1.0 (the null) | +0.001 | 0.080 |
| mixture | 0.5 | +0.030 | 0.870 |
| mixture | 0.25 | +0.047 | 0.995 |
| mixture | 0.0 | +0.065 | 1.000 |

So at the arm's n the registered reading fires on the null 4 to 8 times in a hundred, and finds
a shift of one read in eight (a content-driven reader halving the target's weight) every time;
in a population where six sessions in eight cannot move at all, a reader that never reads the
shuffled book again is still found every time. The screen's eight paired sessions find nothing
reliably and fire on the content-driven null 16 times in a hundred, which is why the screen
reads `fp5`, the scorable share and the price, and never the effect.

## The two runs, in order

1. **The screen** (`--screen --yes`): feeds 00 and 01, 24 sessions, ceiling **$10**. It buys
   three things: `fp5` on a real reader (the §94.6 pre-seat screen; a fixed pattern ends the
   candidate here), the scorable share under this transport (the schema is an instruction on
   `claude -p`, not a guarantee), and the price of a session, which sizes the arm. The screen's
   sessions replay free into the arm — same requests, same keys.
2. **The arm** (`--arm --yes`): all 240 sessions, ceiling **$80**. If the screen's price times
   240 exceeds the ceiling, the arm is amended *before* it runs — fewer feeds, named, with the
   price seen (the K1a precedent) — or it runs to the ceiling and stops between sessions with
   `stopped_at_ceiling` stamped and the reading marked partial. A partial arm is reported as
   partial and never as a covered pool (§89's rail).

Both refuse without `--yes`, refuse a ceiling above the registered one, run three sessions
beside each other and one CLI arm at a time on this box, and read `transport_failures` before
any verdict. Raw records: `raw.jsonl` beside this file (answers and tags, never a passage);
results: `results-screen.json`, `results-arm.json`.

## What may not follow from it

No reader is retuned on this result (§89, §97.1). A reader that moves with order is not thereby
qualified to steer: that is the control plane's evidence (`domain/editorial.py`), of which this
is one control and not the battery. No bar over any effect size — the intervals are directional
readings and one arm is one arm. The D1P families (§104) are not run here: they need a seated
reader and sixteen dollars of generation before any dose exists, and the shuffle is the owned
manipulation the handoff names first. Nothing here feeds a prompt, ranks a book or selects
anything; the reader allocates minutes and code reads the allocation.
