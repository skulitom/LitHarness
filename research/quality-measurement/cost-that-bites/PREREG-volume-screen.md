# Pre-registration — the volume screen: can a drafted book of ours carry a session at all?

**Registered 2026-09-04, before any cell is bought.** This is a **screen and not an arm**. It
buys three things and is registered to buy nothing else: whether a multi-chapter book of this
house's own drafting can be a feed member in all three versions, whether the reader behaves
sanely on it, and what a session costs on it. **It may not be read for an effect, and §6 says
what would have to exist before anything could be.**

It is the same guard that stopped v2 being written on the night it was bought (§222's screen
before its arm) and that caught `fitness-08`'s shuffle chunking below the floor before v3 spent
(the replication's amendment a). Both failure modes it checks have already happened once.

## Why a screen and not an arm, decided before the box was free

The obvious use of a newly drafted multi-chapter book is to run the §230 design on it. That is
refused here for two reasons, the first mechanical:

1. **One book yields no interval.** The registered analysis clusters on the book, and
   `bcr.cluster_interval` returns `None` below two clusters — verified by running it, not
   assumed. At n=1 there is a point estimate and nothing else. Clustering on the three shuffle
   replicates instead is refused by that function's own docstring: it would be "manufacturing a
   cluster dimension out of repeated draws".
2. **The forty book-level contrasts are not this book's reference class.** They are a *fitness
   book* target against *fitness competitors* — same corpus, same length, same 2026-08-22
   pipeline. A shelf book in the target slot changes length, pipeline, writer and concept at
   once against unchanged competitors, so a percentile position would confound *this book's
   order matters less* with *this is a different kind of book*. The null is wide in any case:
   mean +0.1765, **sd 0.2596**, range −0.542 to +0.667, 30 of 40 above zero. A single book
   landing anywhere in that spread says nothing.

**A volume arm needs books, not calls**: ten at v2's own floor, twenty for the power that
produced §230's intervals, and its null built fresh from those books rather than borrowed from
the fitness shelf. Drafting them is a substrate decision and the operator's.

## The stimulus and the plan

The target is one book of this house's own drafting with **three chapters** (draw 6, the first
this pipeline has taken past chapter one under the general system), read as one text in reading
order. Competitors are the first three fitness books, held constant, exactly as `plan_v2` seats
them. The three versions are §230's unchanged: `intact`, `shuffled` (a whole-book paragraph
shuffle at the seed rule's first usable index), and `sham` (`ablate.rewhitespace` at 1.0).

**Three sessions**: one per version, at the target rotation slot A, one replicate. Roughly
$0.85 and six minutes at v2's measured rate. `--workers 1`; one CLI arm at a time under
`runs/box.lock`.

## What is checked, all of it before any reading

1. **The fault check, which is the point.** Every version's target must hold at least
   `feed_core.MIN_CHUNKS_FEED` (11) chunks. **The shuffled copy is the one at risk**: a shuffle
   moves where `bcr.chunks` closes, and `fitness-08`'s seed-4 permutation chunked to 10 against
   the floor. A fault here is a **result of this screen**, not an error — it says the volume
   fork needs more than three chapters, and it is reported with the measured chunk count per
   version.
2. **The reader answers.** Every session scorable — no unanswered step, no `invalid_action`,
   no `slot_exhausted`. `slot_exhausted` in particular would mean the budget can exhaust this
   member and the fault check's guarantee did not hold in practice.
3. **The price**, in calls and equivalent dollars per session, which is what sizes a future arm.
4. **The reader's slot shares**, reported for comparison with §230's capacity precondition
   (0.5508 and 0.5740) — as a description of one session set and never as a precondition passed.

## The reading, fixed before spend

| outcome | reading |
| --- | --- |
| all three versions clear the floor and all three sessions are scorable | **CARRIES.** A three-chapter book of ours can be a feed member. The volume fork is open and needs books, not a new instrument |
| any version's target falls below the floor | **TOO SHORT.** Three chapters is not enough for this instrument; the count needed is reported, and the chapter-scale fork (proposal road A) gains weight against road B |
| a session is unscorable, or any exits `slot_exhausted` | **DOES NOT CARRY**, with the exit note named. A member the budget can exhaust records the corpus rather than the reader (§122) |

**No effect is read under any outcome.** The three target read shares are recorded in the result
file because they are what the sessions produce, and this registration states in advance that
**they are not compared to each other, not compared to the forty, and not reported as a
difference** — at one book there is no interval and no reference class, and §2 above is why.

## What may not follow from it

A screen licenses a seating attempt and nothing else (§104.1's ordering, §94.6's precedent). No
reader is retuned (§89, §97.1). No book is selected, revised or ranked on anything here (§105).
And CARRIES does not make a volume arm registrable — it makes it *possible*, which is a
different word, and the arm still wants ten books and a null built from them.
