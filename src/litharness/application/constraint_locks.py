"""The lock a person's direction was meant to carry, restored on a plan already written.

`plans.constraints_of` selects on `locked`, so an **unlocked** constraint reaches no context
packet at all: it sits in the plan, `litharness plans` counts it, and not one word of it is ever
shown to a writer. Commit `acf0e05` fixed the mechanism — a constraint minted from a
human-authored directive now locks by construction (`narrative_planner`, the branch beside the
machine-author downgrade) — and a fix to a minting rule does nothing for a plan that was already
minted. On `serial.db`'s Serial Pilot 1 head that is five constraints, one of which is the only
sentence about endings anybody ever wrote into this system, and eight accepted scenes drafted
without them.

This is the repair, and it is deliberately the narrowest one that can be written.

**It changes exactly one boolean and never a word of text.** The item is carried forward whole
and `locked` is set; a lane that could also edit `text` would be a paraphrase wearing a repair's
name, which is the risk `directive_planner` exists to avoid on the other side of the same seam.

**Human authority or nothing.** The lock is a *person's* standing — a locked constraint lands in
the packet's CONSTRAINTS section at priority 2 and is effectively never dropped
(`plan/director-role.md` §1) — so every candidate is traced back to the directive that produced
it and refused unless a person wrote that directive. A constraint whose producing directive
cannot be recovered is refused for the same reason: unattributable is not human, and the safe
answer to "who said this" is to leave it alone and say so.

**Nothing is minted, nothing is deleted, and it proposes nothing twice.** A second run over a
plan with no unlocked directed constraints produces no proposal at all, which is what makes it
safe to leave in an operator's hands and what a lane that ran on every tick could not offer.

**Why it carries no `DirectiveReading`, which is not an oversight.** A reading is how a proposal
says "this directive now means this", and `commit_plan_application` acts on it by calling
`Directive.interpret`, which transitions `RECEIVED -> INTERPRETED`. The directives this repair
traces are already `APPLIED`, and `TRANSITIONS[APPLIED]` is `{SUPERSEDED}` — so a reading here
would not record provenance, it would raise `IllegalTransition` and the repair would be
impossible to run at all. The directive already carries its reading; what was lost was a lock,
not an interpretation. The lineage is written into the proposal's rationale and into the
decision's digest, where `litharness plans` and the decision log can both read it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

import litharness_contracts as lc

from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.ports import ConstraintLockStore
from litharness.domain.directives import Directive
from litharness.domain.directors import is_machine_author
from litharness.domain.events import payload_digest
from litharness.domain.plan_refinement import (
    PlanApplication,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalStatus,
    PlanRevision,
    StoredPlanProposal,
    apply_plan_proposal,
)
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decision_id_for,
)

PROFILE = "plan.constraint_lock.v0"

#: Why a candidate was refused. Recorded per item rather than summed, because "four locked"
#: and "four locked, one refused because a machine wrote it" are different outcomes and an
#: operator who sees only the first has been told the smaller of the two facts.
NO_LINEAGE = "no applied proposal attributes this item to a directive"
MACHINE_AUTHORED = "the directive that produced it was written by a Director, not by a person"


@dataclass(frozen=True, slots=True)
class LockCandidate:
    """One unlocked constraint, and whether a person's authority stands behind it."""

    logical_id: str
    directive_id: str | None
    author: str | None
    lockable: bool
    #: Empty when `lockable`; one of the constants above otherwise.
    refused: str = ""


@dataclass(frozen=True, slots=True)
class LockOutcome:
    """What the repair found and what it did. `application` is None when it did nothing."""

    candidates: tuple[LockCandidate, ...]
    application: PlanApplication | None

    @property
    def locked(self) -> tuple[str, ...]:
        return tuple(item.logical_id for item in self.candidates if item.lockable)

    @property
    def refused(self) -> tuple[LockCandidate, ...]:
        return tuple(item for item in self.candidates if not item.lockable)


def produced_by(proposals: Sequence[StoredPlanProposal]) -> dict[str, str]:
    """Which directive the words currently in each plan item came from.

    Recovered from the applied proposal lineage rather than from
    `directives.produced_constraint_ids`, and the difference is measured rather than assumed:
    on `serial.db` that column is `[]` for every interpretive directive, because
    `narrative_planner` fills it from the constraints it minted *locked* — so the one field that
    would have named this lineage was emptied by the same defect this repair exists to undo.

    **The last edit wins, not the first.** A constraint created by one directive and rewritten
    by a later one holds the later one's words, so the later one is the authority a lock would
    be spending. Walking oldest to newest and overwriting is that rule in three lines.

    **A proposal that does not read exactly one directive clears what it touched.** A rollback
    restores text whose author is whichever proposal originally wrote it, a multi-directive
    proposal cannot say which of them a given item came from, and this lane's own proposals read
    none. In all three cases the honest answer is that the item's authority is no longer
    recoverable, and an item with no recoverable authority is refused a lock rather than given
    one on a guess.

    **"Later" is the revision chain, not the clock.** `plan_proposals` comes back ordered by
    `(created_at, proposal_id)`, and two proposals accepted inside one ISO second therefore sort
    on a content hash — which is to say arbitrarily, and "the last edit wins" would silently
    become "whichever hash sorted higher wins". The applied chain is linear by construction,
    because a proposal commits only while its base is still the head, so `base_plan_revision_id
    -> resulting_plan_revision_id` reconstructs the true order with no timestamp in it.
    """
    applied = [
        stored for stored in proposals if stored.status is PlanProposalStatus.APPLIED
    ]
    by_base = {stored.proposal.base_plan_revision_id: stored for stored in applied}
    produced = {
        stored.resulting_plan_revision_id
        for stored in applied
        if stored.resulting_plan_revision_id
    }
    roots = [
        stored
        for stored in applied
        if stored.proposal.base_plan_revision_id not in produced
    ]
    attributed: dict[str, str] = {}
    # One root on a linear chain. More than one means the store holds two disjoint lineages
    # for this branch, which nothing can currently produce; falling back to the given order
    # is better than dropping the ones the walk cannot reach.
    walked: list[StoredPlanProposal] = []
    if len(roots) == 1:
        cursor: StoredPlanProposal | None = roots[0]
        while cursor is not None:
            walked.append(cursor)
            cursor = by_base.get(cursor.resulting_plan_revision_id or "")
    if len(walked) != len(applied):
        walked = applied
    for stored in walked:
        readings = stored.proposal.readings
        directive_id = readings[0].directive_id if len(readings) == 1 else None
        for edit in stored.proposal.edits:
            if edit.action is PlanEditAction.DELETE or directive_id is None:
                attributed.pop(edit.logical_id, None)
            else:
                attributed[edit.logical_id] = directive_id
    return attributed


def lock_candidates(
    revision: PlanRevision,
    *,
    produced: Mapping[str, str],
    directives: Mapping[str, Directive],
) -> tuple[LockCandidate, ...]:
    """Every unlocked CONSTRAINT in this plan, with the verdict on each.

    **Constraints and nothing else**, which is the same line `narrative_planner` draws: its
    symmetric rule forces `locked` only where `kind is CONSTRAINT`, so locking a promise or a
    scene plan here would not be restoring what the fixed minting rule produces — it would be a
    second, wider rule invented by the repair. An unlocked promise stays unlocked; a scene plan
    stays unlocked, and `plan_search` depends on that (alternatives touch only unlocked
    SCENE_PLAN items).
    """
    out: list[LockCandidate] = []
    for item in revision.items:
        if item.kind is not lc.PlanKind.CONSTRAINT or item.locked:
            continue
        directive_id = produced.get(item.logical_id)
        directive = directives.get(directive_id or "")
        if directive_id is None or directive is None:
            out.append(
                LockCandidate(item.logical_id, directive_id, None, False, NO_LINEAGE)
            )
        elif is_machine_author(directive.author):
            out.append(
                LockCandidate(
                    item.logical_id, directive_id, directive.author, False, MACHINE_AUTHORED
                )
            )
        else:
            out.append(
                LockCandidate(item.logical_id, directive_id, directive.author, True)
            )
    return tuple(out)


def proposal_for_locks(
    revision: PlanRevision, candidates: Sequence[LockCandidate]
) -> PlanProposal | None:
    """One UPDATE per lockable candidate, or None when there is nothing to do.

    `dataclasses.replace` rather than a fresh `lc.PlanItem` with the fields spelled out: a
    constructor listing today's seven fields would silently drop the eighth the day the
    contract grows one, and this lane's whole promise is that it changes `locked` and nothing
    else.
    """
    lockable = [candidate for candidate in candidates if candidate.lockable]
    if not lockable:
        return None
    edits = tuple(
        PlanEdit(
            PlanEditAction.UPDATE,
            candidate.logical_id,
            replace(revision.item(candidate.logical_id), locked=True),
            f"restores the lock a human directive's constraint mints with "
            f"(directive {candidate.directive_id})",
        )
        for candidate in lockable
    )
    lineage = ", ".join(
        f"{candidate.logical_id} <- {candidate.directive_id}" for candidate in lockable
    )
    return PlanProposal(
        base_plan_revision_id=revision.plan_revision_id,
        summary=f"Lock {len(edits)} human-directed constraint(s) that reach no context packet",
        rationale=(
            "`plans.constraints_of` selects on `locked`, so these were in the plan and in no "
            "prompt. A constraint a person directed carries that person's authority by "
            "construction, which is what `narrative_planner` now mints and what this restores "
            f"on a plan minted before it. Lineage: {lineage}."
        ),
        expected_outcome=(
            "Subsequent context packets carry these constraints; no text changes and no item "
            "is created or deleted."
        ),
        edits=edits,
        profile=PROFILE,
    )


def lock_directed_constraints(
    store: ConstraintLockStore,
    *,
    book_id: str,
    branch_id: str,
    project_id: str,
    created_at: str,
    actor: str = "litharness",
) -> LockOutcome:
    """Find, judge and (if any survive) lock. Idempotent: a second run proposes nothing."""
    head = store.plan_revision(book_id, branch_id)
    if head is None:
        raise KeyError(f"branch {branch_id} of book {book_id} has no plan")
    produced = produced_by(store.plan_proposals(book_id, branch_id))
    directives: dict[str, Directive] = {}
    for directive_id in set(produced.values()):
        try:
            directives[directive_id] = store.load_directive(directive_id)
        except KeyError:
            # A proposal citing a directive the inbox no longer holds. Treated as no lineage
            # rather than as an error: the repair's job is to lock what it can attribute, and
            # a missing row is exactly the case where it cannot.
            continue
    candidates = lock_candidates(head, produced=produced, directives=directives)
    proposal = proposal_for_locks(head, candidates)
    if proposal is None:
        return LockOutcome(candidates, None)
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.constraint_lock.v0",
        passed=True,
    )
    decision = PolicyDecision(
        decision_id=decision_id_for(f"constraint-lock:{proposal.proposal_id}", 0, (gate,)),
        outcome=Outcome.ACCEPT,
        gates=(gate,),
        base_revision_id=head.plan_revision_id,
        # The result is computed by `accept_plan_proposal` re-reading the head, so it is
        # recomputed here from the same frozen base rather than guessed; a decision whose
        # resulting id disagrees is refused by that function on purpose.
        resulting_revision_id=apply_plan_proposal(head, proposal).after.plan_revision_id,
        profile=PROFILE,
        policy_config_digest=payload_digest(
            {
                "lane": PROFILE,
                "locked": [candidate.logical_id for candidate in candidates if candidate.lockable],
                "directives": sorted(
                    {
                        candidate.directive_id
                        for candidate in candidates
                        if candidate.lockable and candidate.directive_id
                    }
                ),
            }
        ),
        reason="human-directed constraints reach no packet while unlocked",
    )
    application = accept_plan_proposal(
        store,
        proposal,
        project_id=project_id,
        created_at=created_at,
        actor=actor,
        decision=decision,
    )
    return LockOutcome(candidates, application)


__all__ = [
    "MACHINE_AUTHORED",
    "NO_LINEAGE",
    "PROFILE",
    "LockCandidate",
    "LockOutcome",
    "lock_candidates",
    "lock_directed_constraints",
    "produced_by",
    "proposal_for_locks",
]
