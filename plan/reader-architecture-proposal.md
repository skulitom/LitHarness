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

Cost at the arms' measured rate: three sessions a chapter, about $0.85 and six minutes.

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

**Asked:** that the next arm be the milder manipulation of §3 — order-dependence measured on real
chapters, against the null the two arms already provide — registered before spend like everything
else, and that this document be read as the statement of what qualification would require rather
than as a claim on any part of it.

**Not asked:** qualification, an editorial intervention, a bar, a place in any gate, or any
change to `src/litharness/`. `fcr.v0` remains unseated for any book-level claim, the control
plane stays inert, and the mechanism has one demonstrated faculty measured on the loudest
stimulus available to it.
