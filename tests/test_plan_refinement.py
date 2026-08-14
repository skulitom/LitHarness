"""Immutable, conflict-checked Narrative Planner proposal application."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus
from litharness.domain.events import EventType
from litharness.domain.plan_refinement import (
    DirectiveReading,
    PlanConflict,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalError,
    PlanProposalStatus,
    apply_plan_proposal,
    rollback_proposal,
)
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

STAMP = "2026-08-14T12:00:00Z"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "plan-refinement.db")


def item(
    logical_id: str,
    kind: lc.PlanKind,
    text: str,
    *,
    locked: bool = False,
) -> lc.PlanItem:
    return lc.PlanItem(
        logical_id=logical_id,
        kind=kind,
        text=text,
        authority=lc.PlanAuthority.INTENDED,
        locked=locked,
    )


def root(store: SqliteStore):
    source_items = [
        item("premise", lc.PlanKind.PREMISE, "A thief must repay an impossible debt.", locked=True),
        item("scene-1-plan", lc.PlanKind.SCENE_PLAN, "Rook takes the first job."),
    ]
    store.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        source_items,
        created_at=STAMP,
        source_revision_id="imported-plan-v1",
    )
    revision = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert revision is not None
    return revision


def update_proposal(
    base_id: str, text: str, *, summary: str = "Clarify the opening"
) -> PlanProposal:
    return PlanProposal(
        base_plan_revision_id=base_id,
        summary=summary,
        rationale="The first beat needs a concrete choice.",
        expected_outcome="The opening has a testable dramatic function.",
        edits=(
            PlanEdit(
                PlanEditAction.UPDATE,
                "scene-1-plan",
                item("scene-1-plan", lc.PlanKind.SCENE_PLAN, text),
                "make the choice explicit",
            ),
        ),
        provider="fake",
        model="scripted",
        profile="planner.v0",
    )


def test_import_bootstraps_a_content_addressed_immutable_root(store: SqliteStore) -> None:
    source = item("premise", lc.PlanKind.PREMISE, "Original", locked=True)
    store.record_plan_items(BOOK_ID, BRANCH_ID, [source], created_at=STAMP)
    revision = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert revision is not None

    source.text = "Mutated by caller"
    assert revision.item("premise").text == "Original"
    assert store.load_plan_revision(revision.plan_revision_id) == revision
    assert revision.plan_revision_id == store.plan_history(BOOK_ID, BRANCH_ID)[0].plan_revision_id


def test_accepting_a_proposal_moves_the_head_and_records_why(store: SqliteStore) -> None:
    before = root(store)
    proposal = update_proposal(before.plan_revision_id, "Rook accepts a job that costs his name.")

    application = accept_plan_proposal(
        store,
        proposal,
        project_id=PROJECT_ID,
        created_at=STAMP,
        actor="planner-test",
    )

    head = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert head is not None and head.plan_revision_id == application.after.plan_revision_id
    assert head.parent_plan_revision_id == before.plan_revision_id
    assert store.plan_items(BOOK_ID, BRANCH_ID)[1].text.endswith("his name.")
    stored = store.load_plan_proposal(proposal.proposal_id)
    assert stored.status is PlanProposalStatus.APPLIED
    assert stored.proposal.rationale == proposal.rationale
    assert stored.proposal.expected_outcome == proposal.expected_outcome
    assert stored.proposal.provider == "fake"
    decision = store.decision_for_revision(head.plan_revision_id)
    assert decision is not None and decision.outcome.value == "accept"
    [changed] = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.PLAN_CHANGED
    ]
    assert changed.correlation_id == proposal.proposal_id
    assert changed.payload["rationale"] == proposal.rationale
    assert EventType.POLICY_DECISION_RECORDED in {
        entry.event.event_type for entry in store.read_log()
    }


def test_directive_reading_and_locked_constraint_commit_together(store: SqliteStore) -> None:
    before = root(store)
    directive = Directive(
        directive_id="dir-less-combat",
        kind=DirectiveKind.CONSTRAINT,
        body="Less combat; let negotiation carry the midpoint.",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
    )
    store.submit_directive(directive, received_at=STAMP)
    constraint = item(
        "constraint-less-combat",
        lc.PlanKind.CONSTRAINT,
        "The midpoint resolves through negotiation, not combat.",
        locked=True,
    )
    proposal = PlanProposal(
        base_plan_revision_id=before.plan_revision_id,
        summary="Interpret the midpoint direction",
        rationale="Preserve the director's instruction as an enforceable plan item.",
        expected_outcome="Drafting sees an explicit locked constraint.",
        edits=(PlanEdit(PlanEditAction.CREATE, constraint.logical_id, constraint),),
        readings=(
            DirectiveReading(
                directive.directive_id,
                "Prefer negotiation over combat at the midpoint.",
                (constraint.logical_id,),
            ),
        ),
    )

    accept_plan_proposal(store, proposal, project_id=PROJECT_ID, created_at=STAMP)

    interpreted = store.load_directive(directive.directive_id)
    assert interpreted.body == directive.body
    assert interpreted.status is DirectiveStatus.APPLIED
    assert interpreted.produced_constraint_ids == (constraint.logical_id,)
    assert store.plan_revision(BOOK_ID, BRANCH_ID).item(constraint.logical_id).locked  # type: ignore[union-attr]


def test_a_missing_directive_rolls_back_the_plan_change(store: SqliteStore) -> None:
    before = root(store)
    constraint = item("constraint-x", lc.PlanKind.CONSTRAINT, "Keep the door shut.", locked=True)
    proposal = PlanProposal(
        base_plan_revision_id=before.plan_revision_id,
        summary="Interpret missing direction",
        rationale="Exercise the transaction boundary.",
        expected_outcome="Nothing commits when the directive is absent.",
        edits=(PlanEdit(PlanEditAction.CREATE, constraint.logical_id, constraint),),
        readings=(DirectiveReading("dir-missing", "Keep it shut.", (constraint.logical_id,)),),
    )

    with pytest.raises(KeyError, match="dir-missing"):
        accept_plan_proposal(store, proposal, project_id=PROJECT_ID, created_at=STAMP)

    head = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert head is not None and head.plan_revision_id == before.plan_revision_id
    with pytest.raises(KeyError):
        store.load_plan_proposal(proposal.proposal_id)


def test_a_stale_proposal_is_recorded_as_conflicted_without_overwrite(store: SqliteStore) -> None:
    before = root(store)
    winner = update_proposal(
        before.plan_revision_id, "Rook takes the dangerous job.", summary="Winner"
    )
    stale = update_proposal(before.plan_revision_id, "Rook refuses every job.", summary="Stale")
    accepted = accept_plan_proposal(
        store, winner, project_id=PROJECT_ID, created_at=STAMP
    )

    with pytest.raises(PlanConflict, match="plan head"):
        accept_plan_proposal(store, stale, project_id=PROJECT_ID, created_at=STAMP)

    head = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert head is not None and head.plan_revision_id == accepted.after.plan_revision_id
    assert store.load_plan_proposal(stale.proposal_id).status is PlanProposalStatus.CONFLICTED


def test_proposal_validation_is_atomic_and_respects_locks(store: SqliteStore) -> None:
    before = root(store)
    mixed = PlanProposal(
        base_plan_revision_id=before.plan_revision_id,
        summary="One valid and one invalid edit",
        rationale="Exercise pre-commit validation.",
        expected_outcome="No partial plan is constructed.",
        edits=(
            PlanEdit(
                PlanEditAction.UPDATE,
                "scene-1-plan",
                item("scene-1-plan", lc.PlanKind.SCENE_PLAN, "Changed"),
            ),
            PlanEdit(PlanEditAction.DELETE, "does-not-exist"),
        ),
    )
    with pytest.raises(PlanProposalError, match="does not exist"):
        apply_plan_proposal(before, mixed)
    assert before.item("scene-1-plan").text == "Rook takes the first job."

    locked = PlanProposal(
        base_plan_revision_id=before.plan_revision_id,
        summary="Rewrite the premise",
        rationale="This must be refused.",
        expected_outcome="The lock wins.",
        edits=(
            PlanEdit(
                PlanEditAction.UPDATE,
                "premise",
                item("premise", lc.PlanKind.PREMISE, "A different book", locked=True),
            ),
        ),
    )
    with pytest.raises(PlanProposalError, match="locked"):
        apply_plan_proposal(before, locked)


def test_rollback_is_a_forward_revision_that_preserves_history(store: SqliteStore) -> None:
    original = root(store)
    changed_proposal = update_proposal(original.plan_revision_id, "Rook burns the contract.")
    changed = accept_plan_proposal(
        store, changed_proposal, project_id=PROJECT_ID, created_at=STAMP
    )
    rollback = rollback_proposal(
        changed.after,
        original,
        rollback_of=changed_proposal.proposal_id,
    )

    restored = accept_plan_proposal(
        store, rollback, project_id=PROJECT_ID, created_at="2026-08-14T12:01:00Z"
    )

    assert restored.after.plan_revision_id not in {
        original.plan_revision_id,
        changed.after.plan_revision_id,
    }
    assert [item.text for item in restored.after.items] == [item.text for item in original.items]
    history = store.plan_history(BOOK_ID, BRANCH_ID)
    assert [revision.plan_revision_id for revision in history] == [
        restored.after.plan_revision_id,
        changed.after.plan_revision_id,
        original.plan_revision_id,
    ]


def test_the_proposal_that_produced_a_revision_is_findable_from_the_branch(
    store: SqliteStore,
) -> None:
    """Lineage reads backwards from the head, so the question an operator asks is *what
    changed here* about a revision id — not *what did this do* about a proposal id they have
    never seen. Answering it needs the whole branch's proposals in one query rather than one
    per revision, since a long-lived book's lineage is as long as its direction.

    The root answering nothing is the case that matters: a plan revision no proposal
    produced is the plan the book was imported with, and there is nothing behind it.
    """
    original = root(store)
    proposal = update_proposal(original.plan_revision_id, "Rook burns the contract.")
    changed = accept_plan_proposal(store, proposal, project_id=PROJECT_ID, created_at=STAMP)

    by_result = {
        stored.resulting_plan_revision_id: stored
        for stored in store.plan_proposals(BOOK_ID, BRANCH_ID)
    }

    assert by_result[changed.after.plan_revision_id].proposal.proposal_id == proposal.proposal_id
    assert by_result[changed.after.plan_revision_id].status is PlanProposalStatus.APPLIED
    assert original.plan_revision_id not in by_result


def test_a_conflicted_proposal_is_listed_rather_than_hidden(store: SqliteStore) -> None:
    """A proposal that never applied is direction the system decided not to act on. Leaving
    it out of the only read path would make it unreadable outside SQLite — and it carries
    the stale-base error explaining why the direction did not land."""
    original = root(store)
    accept_plan_proposal(
        store,
        update_proposal(original.plan_revision_id, "Rook burns the contract."),
        project_id=PROJECT_ID,
        created_at=STAMP,
    )
    stale = update_proposal(
        original.plan_revision_id,
        "Rook keeps the contract.",
        summary="Written against a stale base",
    )
    with pytest.raises(PlanConflict):
        accept_plan_proposal(store, stale, project_id=PROJECT_ID, created_at=STAMP)

    [conflicted] = [
        stored
        for stored in store.plan_proposals(BOOK_ID, BRANCH_ID)
        if stored.status is PlanProposalStatus.CONFLICTED
    ]
    assert conflicted.proposal.proposal_id == stale.proposal_id
    assert conflicted.resulting_plan_revision_id is None
    assert conflicted.error and "plan head is" in conflicted.error
