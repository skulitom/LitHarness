# Proposal: the costed allocation reader, what it has shown, and what qualifying it would require

**Status: PROPOSAL, 2026-09-04. Nothing here is qualified and nothing here may steer a book.**
This is the fifth item of `plan/handoff-reader-sims.md`, which licenses a proposal only if one of
its four experiments produced a signal that survived its controls. One did — stage-0 §230, two
registered arms — and this document exists to say what that does and does not buy. Its evidence
is `research/quality-measurement/cost-that-bites/` (`PREREG-v2.md`, `PREREG-v3-replication.md`,
`FINDINGS-v2.md`, `FINDINGS-v3.md`); its authority is none.

Written to be read against §129's tier order and §61(5)'s no-ranking rule, and to be judged by
the same standard as any competing mechanism — which is why §1 states the mechanism abstractly
before naming the one that exists.

---

## 1. The mechanism, stated so a different implementation could be judged the same way

**A costed allocation reader** is any mechanism with these four properties:

1. **Continuing costs something the reader can run out of.** A finite budget, priced actions,
   and a competitor for every unit spent.
2. **Spending is forced.** There is no free abstention, so politeness cannot be performed as
   diligence — the failure §70 measured at 195 `keep-reading` of 196.
3. **The datum is an allocation, not a verdict.** What is recorded is where the budget went;
   no model rates, ranks or prefers anything, and code reads the record (§89's verdict channel
   stays shut, §61(5) and §105.1 are not engaged).
4. **Its sensitivity is demonstrated by manipulation, not asserted.** The mechanism must be
   shown to allocate differently under a manipulation of story structure, and *not* to
   allocate differently under a matched surface manipulation, with both measured in the same
   pass.

`fcr.v0` pointed at a whole-book paragraph shuffle (§122, §230) is one implementation. Any other
— a different budget, a different feed size, a different damage family — is admissible on the
same terms, and property 4 is the one that does the work: three instruments in this house
satisfied 3 and died anyway (§70's persona gate-0, §199.1's `readers` lanes, §227's anticipation
probe), all of them by saturation. **What distinguishes this family is 1 and 2, and that is the
transferable claim: a reader that can answer for free will answer the same way every time.**

## 2. What the two arms actually established

**Narrowly:** a reader whose continuing costs it something reads a book **less** when that book's
paragraph order is destroyed, and more than it does when only the whitespace is re-flowed —
replicated with the permutation redrawn, `intact − shuffled` +0.1640 [+0.0881, +0.2390] and
+0.1890 [+0.0747, +0.2955], every precondition passing in both arms.

**And that is one faculty, on the loudest possible stimulus.** A whole-book shuffle is the most
violent order damage available; a mechanism that notices it has cleared a floor. The distance
from there to *this chapter is worse than that one* is the distance every proxy in `BRIEF.md`
fell into, and nothing in these arms crosses it.

## 3. The structural problem this proposal cannot hide: the datum needs a manipulation

**The measurable is a contrast between a text and a damaged copy of itself, and a book in
production has no damaged copy.** That is not a gap in the evidence; it is a property of the
instrument, and it means "qualify this and let it steer" is not yet a well-posed request. Any
honest path to an editorial intervention has to name a datum a real chapter can produce.

**The one this proposal names, and it is the reason the proposal is worth writing:
order-dependence as a per-chapter property.** Manufacture the damaged copy from the chapter
itself and ask how much the reader's allocation moves. A chapter whose shuffled copy loses no
reads is a chapter whose order carries nothing — which is exactly the *list* shape the operator's
reads have named repeatedly (§225's three below-range chapters, read 2's "not much seems to be
happening", read 11's "describing the world to the readers"). It requires no comparison between
candidates, so §61(5) and §105.1 are untouched; it produces a located claim about one chapter;
and it has a null distribution already measured — forty book-level contrasts across the two arms.

**Correction, made 2026-09-04 before any cell was registered: this cannot be run on `fcr.v0`,
because the instrument cannot read a chapter.** A feed member needs 11 chunks so that the
24-minute budget cannot exhaust it (§122's measured floor, `MIN_CHUNKS_FEED`). Measured over
every drafted book on the shelf:

| | chunks | against a floor of 11 |
| --- | --- | --- |
| a chapter of ours, alone | **5 to 6** (median 6) | **cannot be a feed member** |
| the 28 recent single-chapter draws | 5 to 6 | none can carry a session |
| our books that *can* carry one | 24, 18, 12, 25, 24 | **five**, all drafted 2026-08-21 to 08-25 |

So the per-chapter intervention is **not measurable by this mechanism**, and the five books that
do fit are below v2's own ten-book floor and predate the concept stage, the tells pass and the
third-person position — they are the wrong books as well as too few. Reducing the budget or the
entry depth would make it fit and is refused: those constants are `fcr.v0`'s registration
(§120.5), and moving them would void the very null — the forty book-level contrasts — this arm
was going to be read against.

**What that costs this proposal is worth stating plainly: the gap to a production chapter is
wider than §3 first claimed.** It is not only that a book has no damaged copy of itself; it is
that this instrument needs about 3,900 words of member and a chapter is 2,000.

**But the constraint is length, not chapter-ness, and that leaves a fork rather than a single
road.** A first version of this correction conceded a new instrument by default; that was too
quick. Eleven chunks is a quantity of text, and two or three *consecutive* chapters of one book
clear it comfortably — which is the instrument being fed the size it was built for rather than
being weakened to accept a smaller one. The five shelf books that carry a session are exactly
the multi-chapter ones, and they are old only because the recent pilots stop at chapter one.

| road | what it needs | what it costs | what it keeps |
| --- | --- | --- | --- |
| **A. a chapter-scale costed reader** | a new instrument: its own registration, its own budget arithmetic sized to ~2,000-word members, its own attainability table computed from an observed reader (§94.7, and §222's repeat of it), its own null | design and a fresh seating; nothing transfers from v2/v3 except §1's four properties | the ability to ask about a chapter as the reader meets it, which is the unit the operator reads |
| **B. this instrument reading two or three chapters** | **no new registration and no weakening** — the pipeline drafting more than one chapter of the same book. Ten books at v2's own floor, against the five that exist and none of them recent | roughly a chapter of generation per book; pilot 24's chapters measured $4.51 and $6.21, so about $50 for ten | the forty book-level contrasts as its null, and direct comparability with §230 |

**B is the cheaper road and it is not this session's to take**: drafting is a generation spend and
a substrate decision, and §222's shelf question was already refused on the ground that a corpus
drafted overnight to feed one instrument is a substrate change nobody registered. It is stated
here so the operator picks between the two rather than inheriting the more expensive one because
a worktree session conceded it.

**The third time a substrate has bounded a design in this track**, after the twenty-book fitness
shelf (§222) and the nineteen operator reads (§225). Cost at the arms' measured rate, had it
been runnable: three sessions a chapter, about $0.85 and six minutes.

**What it would feed, per §129's tier order.** Not a score a writer sees — never that. A
qualified mechanism's output becomes a `ReaderObservation`, a controller reduces a complete panel
to one `EditorialDecision`, and only `satisfy` or `subvert` may dispatch a scoped machine
directive through the existing plan-revision path (`application/editorial.py`). The intervention
this mechanism could support is the narrowest kind: *the reader's allocation did not distinguish
this chapter from a shuffled copy of it* — a claim about structure, at chapter grain, that the
controller may act on or defer. `house.CLARITY` remains the floor above it; the rule-essays
remain below both. And §126 is untouched: no real reader's behaviour enters this or any loop.

## 4. What qualification would require, field by field

`domain/editorial.QualificationEvidence` is the contract and it refuses any missing or failed
field. Mapped honestly against what exists today:

| field | today | what would be needed |
| --- | --- | --- |
| `holdout_books` (≥ 2) | **0.** Both arms used all twenty fitness books | a registered split, the mechanism's threshold fixed on the training half and read once on the held-out half |
| `heldout_transformations` | **false.** One damage family, one implementation | a second implementation of order damage the mechanism has never seen — §104's D1P families are the candidates the ledger already owns |
| `edit_fingerprint_passed` | **partial.** The whitespace sham rides every arm and its contrast scatters about zero (+0.089, −0.077, +0.032) | the sham to stay inert on the held-out implementation too |
| `memorisation_controls_passed` | **arguably true by construction** — the substrate is this system's own un-memorised prose (BRIEF §2 Pass 6's rule) | stated as a control rather than inherited from the substrate choice |
| `full_volume_passed` | **false.** The instrument reads ~4,000-word books | a run at volume length, where the budget arithmetic that §122 sized does not obviously hold |
| `cross_volume_passed` | **false** | as above, across a volume boundary |
| `growing_serial_passed` | **false** | the same chapter measured as the serial grows behind it |
| `transfer_passed` | **false.** One model, one transport | a second reader family; `reader_transport.py` is the seam and cross-family numbers are never pooled |
| `operator_acceptance_passed` | **false.** Not attempted | the fixed acceptance test, whose inverted result withdraws the instrument rather than flattering it |
| `registered_bar_digest` | **absent, and deliberately** | a bar, which requires §61's four attainability checks on a quantity that has never had them — distributions before bars |

**One of ten.** That is the honest position, and the list is the work rather than a formality:
the two arms are evidence *for* the mechanism's first faculty and satisfy no field of the
contract except arguably one.

## 5. What would un-qualify it

A mechanism that cannot be demoted was never qualified, only adopted. Registered here so a later
arm can withdraw the licence without an argument about whether it should:

- **The primary fails to replicate on any subsequent registered arm at the same design** —
  `intact − shuffled` containing zero. The design's own registration already refuses a
  tie-breaking third arm, so two disagreeing arms is the answer.
- **The placebo stops being inert**: the `intact − sham` contrast excluding zero in either
  direction on a registered arm. A placebo that moves is a confound, and the current reading of
  it rests on three measurements that agree on no direction.
- **The capacity precondition fails**: the reader's share on the slot the target occupies
  dropping below the registered floor or ceasing to be the largest. It has already drifted once,
  0.622 → 0.5508 → 0.5740, so this is a live condition and not a formality.
- **`fp5` fails**: the reader becoming a fixed pattern wearing a budget.
- **The milder manipulation returns null** — this one **bounds** rather than withdraws: it would
  establish that the mechanism detects only gross disorder, which is a smaller claim than the
  one qualification would rest on, and the licence would have to be re-scoped rather than kept.

Any of the first four fires `reader-mechanism withdraw`, which closes future panels and already
queued controller work before it can spend.

## 6. What is asked, and what is not

**Asked:** nothing that spends, and that is a change from this document's first version. The arm
it proposed — order-dependence on real chapters — was measured unrunnable on this instrument
before it was registered (§3's correction). What is asked instead is a **decision between §3's
two roads**, which is the operator's because one of them is a substrate change: build a
chapter-scale instrument, or draft a second chapter for ten books and read them with the
instrument that already has a null. Road B is the cheaper by a wide margin and is stated as such
rather than conceded away.

Read this document as the statement of what qualification would require rather than as a claim on
any part of it.

**Not asked:** qualification, an editorial intervention, a bar, a place in any gate, or any
change to `src/litharness/`. `fcr.v0` remains unseated for any book-level claim, the control
plane stays inert, and the mechanism has one demonstrated faculty measured on the loudest
stimulus available to it.
