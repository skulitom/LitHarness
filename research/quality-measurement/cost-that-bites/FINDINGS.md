# Findings — a cost that bites

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG.md` owns the design, the decision table and the attainability arithmetic; this file
owns the reading. Status: **OBSERVED**, 2026-09-03. The registered decision is **UNREADABLE**,
and no effect is read from this arm. Raw answers in `raw.jsonl` (1,468 records), the screen in
`results-screen.json`, the arm in `results-arm.json`; both carry registration digest
`2659023acf6197e3`, so screen and arm are the same instrument. Nothing here promotes a claim
past OBSERVED.

## What ran

| | screen | arm |
| --- | --- | --- |
| feeds x versions x rotations | 2 x 3 x 4 = 24 sessions | 20 x 3 x 4 = 240 sessions |
| sessions scorable | 24 of 24 | 179 of 240 |
| transport failures | 0 | **60, every one `cli_error`** |
| calls bought / replayed | 194 / 0 | 594 / 934 |
| equivalent spend | $7.57 | $48.87 (cumulative cache $56.44 against the $80 ceiling) |
| `fp5` | PASS, 0.206 | PASS, 0.189 (floor 0.05) |

**The arm ran twice and the box is why.** It started at 15:48 at three workers; the machine
froze and restarted at about 16:30 with the run's process gone. The Elicitor's cache was
lossless — 934 records, 114 complete sessions, no torn line — so the run resumed at 16:57 at
two workers, replayed every answered call for free, and finished at 18:05. The resume bought
594 calls in 69 minutes. The two-worker choice was a caution after the freeze and is recorded
because it is a difference between the two passes; the freeze itself is undiagnosed and no
other sustained job was running beside the arm.

## Why the answer is UNREADABLE, and it turns on one session

The registered precondition: *a version with fewer than 75% of its sessions scorable is
UNREADABLE, and nothing is substituted, retried or filled.*

| version | scorable | share |
| --- | --- | --- |
| intact | 60 of 80 | 0.750 |
| sham | 60 of 80 | 0.750 |
| **shuffled** | **59 of 80** | **0.738** |

**Which kind of failure they were cannot be recovered, and it is not that nobody looked.**
`elicit._call_cli` reported every non-zero exit as the one string `cli_error` and discarded the
call's stdout and stderr at the moment it failed, so `failure_reasons` was a bucket by
construction; a usage limit and a crashed binary are the same row here, and they argue in
opposite directions about how many workers an arm may use. Stage-0 §224 records that, fixes it
forward, and leaves these sixty unclassified, because the information no longer exists and a
reading invented for them now would be worth less than the gap.

**The failures are one contiguous transport stop, not a reader refusing.** Every session from
181 to 240 failed — feeds 15 through 19 entire, the books `fitness-15` … `fitness-19`, lost
wholesale — plus exactly one earlier casualty at session 125 (feed 10, the shuffled copy at
rotation 0, killed at step 6 of 8). Fifteen feeds survive complete, and that single extra
casualty is the whole of the difference between 0.750 and 0.738.

So the arm is unreadable by one session out of 240. That is the floor doing exactly what it
was written to do, and the temptation it creates is the reason to say plainly what was **not**
done: **the intervals were computed and looked at before this file was written, and the one
missing cell was not bought.** Buying a single session to lift a precondition after seeing
which way the numbers pointed is the failure this project refuses hardest, and the transport
recovery the runbook licenses (a re-run replays what answered and re-issues what did not) is
not licensed *by the direction of a result*. `results-arm.json` carries the intervals; they
are not a reading, for two independent reasons — the precondition failed, and the capacity
diagnostic below shows what the pooled statistic is actually made of.

## What the arm did measure, and it is about the instrument

**The reader is not a fixed pattern.** `fp5` passes at 0.189 against a floor of 0.05, with a
mean read-switch rate of 0.436 and no named pattern; it read the full eight times in almost
every session and skimmed 0.03 of its actions. Haiku is a live seat candidate for `fcr.v0` at
this shape, which is what the screen was for and what the arm confirms at eight times the size.

**And the reader has a positional lean that eats three quarters of the design.** Mean read
share by slot, over every scorable session:

| slot | A | B | C | D |
| --- | --- | --- | --- | --- |
| mean read share | **0.622** | 0.190 | 0.105 | 0.082 |

The rotation was registered as the position control and it does its job — the target sits in
the same slot across the three versions of one session, so a paired difference cannot be a
slot difference. What the rotation cannot do is create capacity where the reader is not
looking. Per rotation, over the 59 complete triples:

| rotation (target slot) | triples | intact − shuffled | sham − shuffled | mean intact target share | intact target never read |
| --- | --- | --- | --- | --- | --- |
| r0 (slot A) | 14 | +0.286 | +0.196 | 0.688 | 1 of 14 |
| r1 (slot B) | 15 | +0.020 | +0.033 | 0.204 | 4 of 15 |
| r2 (slot C) | 15 | −0.017 | +0.014 | 0.061 | 9 of 15 |
| r3 (slot D) | 15 | +0.058 | +0.058 | 0.100 | 8 of 15 |

**Three of the four rotations cannot carry the measurement.** Where the target is in slot C or
D the reader frequently never reads it at all in *either* version, so the paired difference is
structurally zero and the session contributes noise and no signal; 21 of the 59 triples have a
difference of exactly zero. Whatever the pooled interval says, it is one rotation's
observation wearing four rotations' n.

**So the attainability table overstated the power of this design, and the reason is §94.7's
lesson recurring.** `attainability.json` simulated a content-driven Dirichlet allocator and a
mixture of fixed patterns — neither of which has a positional lean — and concluded that 80
paired sessions in 20 clusters find a one-read-in-eight shift every time. The seated reader
allocates 62% of its reads to one slot, so the effective unit is the (feed, rotation-A) cell
and the design has at most 20 of those on this substrate, not 80. The BCR sized its controls
from a reader nobody is and the corrected number was 2.7x the declared one; this table sized
its power from a reader nobody is in a different way, and the correction is a change of unit
rather than of count.

## What was refused

No effect is read from an unreadable arm, and no interval in `results-arm.json` is quoted as a
reading anywhere in this file. No bar over any quantity: none of the four attainability checks
has been run on an effect size here, and the one power argument the registration did make is
corrected above rather than relied on. No session was bought to lift the precondition. No
reader was retuned (§89, §97.1). No skim-derived number is read — `fp6` was not run and the
skim rate is a diagnostic. And no claim is made about any of the twenty books: the arm
measures a reader's allocation, and it did not measure it well enough to say anything about
prose.

## What is owed

1. **Re-size from the observed reader, not from a simulation of one** (§94.7's recourse). The
   per-rotation table above is the input: the unit is the (feed, rotation) cell, its variance
   differs by an order of magnitude across slots, and a design that pools them is averaging a
   measurement with three non-measurements.
2. **A shape that gives the manipulation somewhere to land.** Seating the target only in the
   slot the reader reads would destroy the position control and is not the answer; what is
   open is whether the feed's size, the entry depth or the budget can be re-shaped so that a
   competitor's share carries the signal the target's cannot. That is a registration, not a
   patch.
3. **The transport condition**, named here because it bounds every arm on this box: 60 of 594
   calls returned `cli_error` in one contiguous block at the end of the run, on a night when
   Opus `-p` calls were hanging past the 120-second provider probe while Haiku answered in
   five seconds. Read `transport_failures` before any verdict, and treat a block of failures
   at one end of a run as a stopped transport rather than as scattered noise.

## What it cannot show

One reader, one model, one substrate of twenty own-drafted books, one shuffle seed per book,
and a plan the transport cut short by a quarter. The question the arm was registered to
answer — does a costed reader's stop point move when the order goes — is **not answered here
in either direction**, and the direction closes for no one. The handoff's first experiment
therefore stands open with its instrument better characterised than before and its power
argument corrected.
