# Pre-registration — v3: the same arm again with the permutation luck redrawn

**Registered 2026-09-04, before any cell of this arm is bought and while v2's result is on
disk.** This is a **replication and not a new design**: v2's registration governs everything —
the target in slot A, the book as the unit, twenty books, three replicates, the same reader on
the same model over the same transport, the same preconditions, the same alpha, the same
decision table. `PREREG-v2.md` is the design document and is not restated here. One thing
changes, deliberately and only:

> **The three shuffle seeds are redrawn.** v2 used seed indices 0, 1, 2 for each book; v3 starts
> at 3. Nothing else moves — not the books, not the competitors, not the sham, not the reader,
> not the prices, not the analysis.

### Amendment a, made before any cell was bought: the seeds follow a rule, not a list

The plan at seeds (3, 4, 5) **faulted before spending**, and the fault check is why this is an
amendment rather than a silent loss. A shuffle reorders paragraphs and `bcr.chunks` closes a
chunk once it passes the word target, so a permutation can leave a book one chunk short of the
floor a feed member needs. Measured across seeds 0 to 9 over all twenty books, **exactly one
pair does**: `fitness-08` at seed 4, which chunks to 10 against a floor of 11.

Picking a different triple *because* it happens to clear would be choosing the nuisance
parameter to fit — the thing this arm exists to rule out. So the seeds are a **rule** instead:

> For each book, the three lowest seed indices at or above the arm's start whose shuffled copy
> clears the feed's chunk floor.

It reads only chunk counts, never a reader's behaviour; it is deterministic; and it is declared
here before the arm runs. **v2's (0, 1, 2) satisfies it at start 0**, so the rule describes what
v2 already did rather than changing it. At start 3 it gives (3, 4, 5) for nineteen books and
**(3, 5, 6) for `fitness-08`** — the one deviation, named here and flagged in the result file,
which records the seeds every book actually used.

## Why this arm and why now

v2 returned **MOVES_WITH_ORDER**: intact − shuffled = +0.1640 [+0.0881, +0.2390], sham −
shuffled = +0.2411 [+0.1512, +0.3366], every precondition passed, 16 of 20 books moving in the
predicted direction. It is the first signal in this house to survive its controls.

**And v2's own diagnostic says why it might not survive a redraw.** The three shuffles of one
book produced target shares differing by **0.1804 on average** — about the size of the +0.1640
effect itself. The design averages three permutations per book to make the estimate about
*disorder* rather than about a permutation, and three is a small number against a spread that
size. So the live question is not whether the reader responded, but whether it responded to
disorder or to the particular disorder v2 happened to draw.

**One arm that survives its controls is a result; the same arm twice with the nuisance parameter
redrawn is a finding.** That is what this buys and it is the cheapest strong thing available.

## The prediction, fixed before the arm runs

Registered as a prediction and not as a hope, so the arm can fail:

- **`intact − shuffled` excludes zero on the low side, with a point estimate near +0.164.**
  "Near" is made explicit rather than left to taste: a point estimate in **[+0.08, +0.25]** is
  the same effect; outside it, the two arms disagree about magnitude even if both exclude zero,
  and the findings say so rather than averaging them.
- `sham − shuffled` also excludes zero on the low side.
- Every v2 precondition passes again: `fp5` above 0.05, slot-A share largest and at or above
  0.40, twenty books complete, every version at or above the 0.75 scorable floor.

## What each outcome means, fixed before spend

| v3's `intact − shuffled` | reading |
| --- | --- |
| excludes zero, point in [+0.08, +0.25] | **REPLICATED.** The effect survived a fresh draw of the permutation luck, and the claim stops being about the shuffles v2 drew. Still one reader, one model, one manipulation, twenty books — and still not qualification |
| excludes zero, point outside [+0.08, +0.25] | **REPLICATED, MAGNITUDE UNSTABLE.** The direction holds and the size does not; both intervals are reported side by side and neither is averaged into the other |
| contains zero | **NOT REPLICATED, and this closes the direction for this design.** v2 would then be one draw of a permutation that happened to move the reader, which is the reading its own seed spread warns about. No third arm is run to break the tie: two arms disagreeing at this n is the answer, and a best-of-three would be the rejection sampling `BRIEF.md` §6 item 6 prices |
| excludes zero on the **high** side (shuffled read *more*) | reported as what it is, and it kills the mechanism rather than reversing it |

A precondition failing reads UNREADABLE exactly as in v2, with its measured value printed beside
its floor.

**Nothing is pooled.** v2 and v3 are two arms, reported side by side; there is no combined
interval, because combining them after seeing the first would make the pair one arm with a
larger n and no registration.

## Cost, ceiling and the stop condition

Identical to v2: 20 books x 3 versions x 3 replicates = **180 sessions**, three workers, the
**2,200-call ceiling** read between sessions, a stopped run keeping every session and stamped
partial. v2 measured 1,452 calls, $49.78 and 2h04, so this is priced the same. Its own cache at
`raw-v3.jsonl` and its own result at `results-arm-v3.json`, because one file is never two
experiments.

## What may not follow from it

A replication is not a qualification. Even REPLICATED leaves the mechanism where
`plan/reader-architecture-proposal.md` puts it: a candidate with one demonstrated faculty —
order-sensitivity under a cost — measured on the most violent order damage available, and the
distance from that to *this chapter is worse* is the distance every dead proxy in `BRIEF.md`
fell into. No reader is retuned (§89, §97.1), no book is selected or revised on any of it
(§105), and no editorial intervention is licensed by any outcome above.
