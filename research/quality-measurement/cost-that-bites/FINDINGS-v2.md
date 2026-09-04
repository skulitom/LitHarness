# Findings — a cost that bites, v2: the reader pays less for a book whose order is gone

House form: the claim, the number beside it, and the caveat travelling with the claim.
`PREREG-v2.md` owns the design, its preconditions and the decision table fixed before spend;
`PREREG.md` and `FINDINGS.md` beside them are v1's and are untouched. Status: **OBSERVED**,
2026-09-04. The registered decision is **MOVES_WITH_ORDER**. Raw records in `raw-v2.jsonl`, the
result in `results-arm-v2.json`, registration digest `499efb7c9faea9d3`. Nothing here promotes a
claim past OBSERVED, and nothing here qualifies a mechanism to steer a book.

## The one sentence

**A reader whose continuing costs it something spends less of that cost on a book whose
paragraph order has been destroyed, and spends no less on the same book with only its whitespace
re-flowed.** That is the first time an instrument in this house has moved with a story-level
manipulation rather than with surface — §195.5's panel and §199.1's `readers` lanes both failed
exactly this test — and it is one arm, one reader, one manipulation and twenty books.

**Status, exactly: OBSERVED, and SUPPORTED for the registered claim on this one arm** at twenty
books under alpha 0.1. Not QUALIFIED, and nothing here licenses an editorial intervention or
lets any reader steer any book.

## Three ways this could be less than it looks, before anything else

Put first rather than last, because each is a live route by which the result above is smaller
than it reads.

**1. The sham's point estimate is negative.** The re-flowed copy drew *more* reads than the
intact one (−0.0771), which is not what an inert placebo does. Its interval contains zero, and
in v1's slot-A cells the same contrast ran the other way (+0.089), so across two arms it reads
as scatter about zero rather than a layout effect. **But this is where a layout confound would
first show**, and a later arm finding the sham consistently above intact would put this result
in question rather than extend it.

**2. The effect sits below the target the design declared.** 0.1640 against a declared 0.1875,
and above the 0.125 the registration says this design cannot reach. So it is inside the band
this design can see and not comfortably inside it; the interval excludes zero and that is the
whole of what is claimed.

**3. The shuffle-seed spread is about the size of the effect.** Averaged over books, the three
shuffles of one book differ by 0.1804 in target share (max 0.3813) against an effect of 0.1640.
That vindicates three seeds — a single-seed design would have been measuring one permutation's
luck, which is exactly what v1 did — and it means the number is about *disorder* only because it
was averaged over three draws. **A replication with the seeds redrawn is therefore the arm that
decides whether this survives**, and it is registered in `PREREG-v3-replication.md`.

## The run

180 of 180 sessions, **every one scorable in every version**, zero transport failures, no
ceiling stop, 1,452 calls against the registered 2,200, $49.78 equivalent, 2h04 at three
workers.

## The preconditions, with their numbers and not only their verdicts

| precondition | measured | floor | verdict |
| --- | --- | --- | --- |
| `fp5` non-degeneracy | 0.219 (switch rate 0.461, no named pattern) | 0.05 | **PASS** |
| capacity: slot-A read share | **0.5508** (A 0.5508, B 0.2072, C 0.1430, D 0.0990) | 0.40 and largest | **PASS** |
| books with a complete scorable set | **20** | 10 | **PASS** |
| scorable share per version | 1.000 / 1.000 / 1.000 | 0.75 | **PASS** |

The lean that made v1 unreadable is still there and is **weaker than v1 measured it**: 0.5508
against 0.622. It is a property of the reader on the day, not a constant, which is why the
registration made it a precondition checked in the same pass rather than an assumption carried
forward — and why the number is printed here whether it passed or not.

## The reading, by the table fixed before spend

Book as the unit, twenty clusters, the registered alpha:

| paired difference | point | 90% interval | |
| --- | --- | --- | --- |
| **intact − shuffled** | **+0.1640** | **[+0.0881, +0.2390]** | above zero |
| **sham − shuffled** | **+0.2411** | **[+0.1512, +0.3366]** | above zero |
| intact − sham | −0.0771 | [−0.1658, +0.0146] | contains zero |

Both registered conditions hold, so the decision is **MOVES_WITH_ORDER**, *for a book in the
position this reader attends to* — the narrowing v2 bought deliberately and the only claim the
design supports.

**It is not one or two books carrying it.** Sixteen of twenty move in the predicted direction,
four reverse, median +0.2054. **And the secondary measurable agrees without being asked to**:
the mean abandonment step — the last full read of the target — is 5.167 intact, 5.783 sham,
**4.317 shuffled**. The stop point moved, which is the thing the handoff's first experiment was
registered to find out.

## What this does not show, and the distance is the point

The manipulation is a **whole-book paragraph shuffle**: the most violent order damage available,
applied to every paragraph including the entry section the reader meets first. That a costed
reader notices total disorder is a floor, not a ceiling. It says nothing about whether the same
reader would notice a chapter that is merely *worse*, and BRIEF.md's whole ledger is the record
of instruments that separated a sledgehammer and nothing finer.

Nor is it a quality claim about any of the twenty books: the arm measures how a reader allocates
minutes, and every book here is one of this system's own. And it is one reader on one model —
`claude-haiku-4-5` over `claude -p` — so a different model is a different reader with its own
result file, never pooled with this one.

## What is owed

A **milder manipulation**, because the gap between "notices a shuffled book" and "notices a
worse chapter" is where every dead proxy in `BRIEF.md` lives, and this design can now be pointed
at one with its preconditions already characterised. The candidate the ledger already owns is
§104's D1P families, which need a seated reader before a dose means anything — and this arm is
the closest thing to a seating this instrument has had.

And a **proposal, not a qualification**: the handoff's fifth item is now in scope because a
signal survived its controls, and `plan/reader-architecture-proposal.md` states the mechanism,
what it has shown, what it has not, and asks for the next control rather than for authority over
a book.
