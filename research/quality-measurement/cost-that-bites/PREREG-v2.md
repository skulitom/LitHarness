# Amended pre-registration — a cost that bites, v2: the unit is the book, and the shelf is the ceiling

**Registered 2026-09-04, before any cell of this design is bought.** `PREREG.md` and
`FINDINGS.md` beside it are the v1 registration and its reading and are **not edited**: v1 ran,
came back UNREADABLE, and its record stands whole. This file is the successor design, and every
number it is built from was measured by v1 and recorded in stage-0 §222.

**What licenses an amendment at all.** v1's decision was UNREADABLE, so no effect was read and
none is carried forward. What v1 *did* establish is two properties of the seated reader, and
both are inputs a design is allowed to use: the reader's read share by slot, and the variance of
a paired difference. Neither is the contrast under test.

## The defect being fixed, in one paragraph

v1 seated the target in each of the four slots by rotation and pooled the four. The reader
reads slot A 0.622 of the time and slots B, C and D at 0.190, 0.105 and 0.082, so where the
target sat outside A the reader frequently never read it in *either* version and the paired
difference was structurally zero — 21 of 59 triples returned exactly zero, and the per-rotation
means ran +0.286 at A against +0.020, −0.017 and +0.058 elsewhere. Three quarters of the
sessions could not register the manipulation. **The correction is the unit, not the count**: a
larger v1 would buy the same three-quarters of nothing.

**The selection is licensed by capacity and not by the effect, and the distinction is the whole
argument.** Slot A is chosen because the reader *reads* there — a property of the reader
measured from every session's slot-share vector, independent of any version contrast. That the
effect also happened to be largest at A is recorded in §222 and is **not** the reason; a design
chosen because a subgroup gave the wanted answer would be the dredge this repository refuses.
The claim v2 can make is correspondingly narrower and is stated in the reading below: it is
about a book in the position this reader attends to, and it says nothing about the others.

## What changes, and what does not

| | v1 | v2 |
| --- | --- | --- |
| target's slot | all four by rotation | **A only** |
| unit | (feed, rotation), pooled | **the book (feed)** |
| replicates per version | 1 | **3** |
| shuffle | one seed per book | **three seeds per book, one per replicate** |
| sessions | 240 | **180** |
| ceiling | $80 | **a call ceiling and a stop condition** (below) |

Unchanged and byte-frozen: `fcr.v0` itself — `feed_core`'s registration and digest, the
24-minute budget, reads at three and skims at one, forced spending, the four-book feed, the
mid-stream entry, the deterministic skim extract, `feed_session`'s loop and `feed_controls`'
arithmetic. The substrate is the same twenty own-drafted fitness books, the sham is the same
`ablate.rewhitespace` at strength 1.0, the reader is the same `claude-haiku-4-5` over
`claude -p` with the §109 flags, and the alpha is the same 0.10.

**Three shuffle seeds rather than one, because v1's claim was conditional on a permutation.**
A book shuffled once is one draw from the space of permutations, and v1's between-book spread
therefore confounds *this book is robust to disorder* with *this book's one shuffle happened to
be mild*. Three seeds averaged within the book make the estimate about disorder rather than
about a permutation, and cost nothing extra because the replicates were being bought anyway.

## Sizing, from the variance v1 measured rather than from a simulated reader

v1's attainability table simulated allocators with no positional lean and overstated the
design's power; §94.7's recourse is to re-size from the observed reader once one exists, and one
now does. Over v1's fourteen complete slot-A triples:

| contrast | mean | sd | what it is |
| --- | --- | --- | --- |
| intact − sham | +0.089 | **0.345** | the same book undamaged twice: the **noise floor** |
| intact − shuffled | +0.286 | 0.414 | the paired difference |

So the between-book component is `sqrt(0.414² − 0.345²) = 0.230`, and **69% of the variance in a
paired difference is within-cell noise that replicates remove.** That is the opposite of the
first guess a binomial argument gives, and it is why replicates are the lever: the reader
commits to an allocation for a whole session rather than flipping eight independent coins,
which is `feed_controls`' own model of it and §94.7's finding restated.

Power at the registered alpha, book effects `N(true, 0.230²)` plus cell noise
`N(0, 0.345²/k)`, 400 trials, the same cluster bootstrap the reading uses:

| replicates | sessions | true = 0 | true = +0.125 | true = +0.1875 | true = +0.25 |
| --- | --- | --- | --- | --- | --- |
| 1 | 60 | 0.080 | 0.422 | 0.677 | 0.828 |
| 2 | 120 | 0.055 | 0.537 | 0.815 | 0.958 |
| **3** | **180** | **0.065** | **0.590** | **0.877** | **0.968** |
| 4 | 240 | 0.062 | 0.613 | 0.900 | 0.983 |
| 6 | 360 | 0.072 | 0.680 | 0.920 | 0.998 |

**The normal approximation flatters the design and the amount is measured**: at 20 books, k=1
and a true +0.125 it reports 0.427 where resampling v1's own observed differences reports
0.375, so read every cell above as roughly 0.05 optimistic. The false-positive column sits at
0.055–0.080 against a nominal 0.05, so the reading is calibrated.

**k = 3 is the knee and the table says why.** Past it the noise term is already below the
between-book term and more replicates buy almost nothing: 0.590 → 0.613 → 0.680 at a one-read
shift for 60 and 180 more sessions. What would buy power is more *books* — 30 books at k=3
reaches 0.723 and 40 books 0.825 at the same shift — and this project has twenty. **The shelf,
not the call budget, is what bounds this design**, which is the finding this amendment exists to
record; drafting more fitness books is a generation spend and the operator's call, not a
worktree session's.

### What this design is therefore powered to find, declared before spend

- **A shift of 0.1875 — one and a half reads of eight — at power ≈ 0.88 (read ≈ 0.83 after the
  approximation's correction).** That is the declared target.
- **A shift of 0.125 — one read of eight — it cannot reliably find**, at ≈ 0.59 (≈ 0.54
  corrected). A null at that size is **not** evidence of absence and the reading below says so.
- The four attainability checks on the target quantity: range, a paired difference in [−1, 1] in
  eighths; direction, positive means the reader paid less for the shuffled book; unit, the book,
  of which there are twenty and none is empty; non-emptiness, every book built all three
  versions fault-free under v1.

## The reading, fixed before spend

Preconditions, in order, each refusing rather than degrading:

1. **`transport_failures` and the exit notes.** A session with any unanswered step is reported
   and never scored. A version with fewer than 75% of its sessions scorable is UNREADABLE, and
   nothing is substituted, retried or filled. **v1's amendment to this rule, learned the hard
   way: a contiguous block of failures at one end of a run is a stopped transport**, and the
   run is reported as under-run with the block named rather than read as a thin sample.
2. **`fp5`** over every scorable session, as v1.
3. **The capacity assumption, checked in the same pass.** The reader's mean read share on slot A
   must be the largest of the four and at least 0.40. This design rests on the reader attending
   to the position the target occupies; if the lean has gone, the design's premise has gone with
   it and the arm is UNREADABLE whatever the intervals say.
4. At least ten books with a complete scorable triple.

Then one decision, over `target_read_share`, paired within book, clustered on the book:

| the intervals | reading |
| --- | --- |
| `intact − shuffled` above zero **and** `sham − shuffled` above zero | **MOVES_WITH_ORDER**, for a book in the position this reader attends to |
| `intact − shuffled` above zero, `sham − shuffled` not | **MOVES_WITH_EDITEDNESS** |
| `intact − shuffled` contains zero | **NULL at the declared target**: the reader's allocation does not move by one and a half reads of eight when the order goes. Not a null at one read of eight, which this design cannot reach |
| `intact − shuffled` below zero | **INVERTED**, reported as what it is |

Reported beside the decision and deciding nothing: the abandonment step and the first-read
share paired the same way, the per-slot table (which is also precondition 3's input), the skim
rate, and the between-seed spread of the three shuffles within each book — the last is new, and
it says whether *disorder* or *a permutation* is what the number is about.

## Cost, ceiling and the stop condition

No dollar ceiling: the operator's direction of 2026-09-04 is that this is subscription quota
and the window is to be used. A registration still needs a stopping rule, so:

- **Call ceiling: 2,200 bought calls.** 180 sessions ran at 8.1 calls a session in v1, so the
  plan is about 1,460 and the ceiling covers a skim-heavy run with margin.
- **Stop condition:** the ceiling is read between sessions; a run that reaches it finishes no
  further session, keeps every session bought, stamps `stopped_at_ceiling`, and its reading is
  marked partial and never reported as a covered shelf.
- **The ledger still reports `equivalent_usd`** beside the call count, so the quota burn stays
  on the record even though it is not the limit. At v1's measured $0.32 a session the plan is
  about $58 equivalent.
- Two or three workers, never more: the box froze on 2026-09-03 under one arm at three workers
  beside five other sessions. One arm at a time under `runs/box.lock`.

## What may not follow from it

No reader is retuned (§89, §97.1). No bar over any quantity. No claim about any of the twenty
books: the arm measures an allocation. No generalisation past slot A — v2 buys a narrower claim
than v1 attempted and the narrowing is the point. And **v1 is not superseded**: its UNREADABLE
stands as the reading of the design that ran, this file is a different design, and no number
crosses between them except the two reader properties named at the top.
