"""Restoring the lock a human directive's constraint mints with, on a plan minted before it.

The first test in this file is the reproduction: a constraint a person directed, sitting in the
plan unlocked, reaching no context packet. That is the state `serial.db`'s Serial Pilot 1 head
was in for eight drafted scenes, and it is what the rest of the file repairs.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import constraint_locks
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus
from litharness.domain.directors import machine_author
from litharness.domain.plan_refinement import (
    DirectiveReading,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalStatus,
    rollback_proposal,
)
from litharness.domain.plans import constraints_of
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

STAMP = "2026-08-22T12:00:00Z"

#: The clause the pilot's tone note carried and no scene was ever shown. Kept verbatim because
#: the point of the whole exercise is that these exact words reached nothing.
ENDINGS = (
    "Scenes end on movement or on a cost paid: someone leaves, acts, loses something, or "
    "commits to a price. They never end on a tidy emotional summary."
)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "constraint-locks.db")


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
    store.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            item(
                "premise",
                lc.PlanKind.PREMISE,
                "An appraiser dies and wakes on the same morning.",
                locked=True,
            )
        ],
        created_at=STAMP,
        source_revision_id="imported-plan-v1",
    )
    revision = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert revision is not None
    return revision


def submit(store: SqliteStore, directive_id: str, *, author: str | None = None) -> Directive:
    """A tone note in the inbox, the way `litharness directive` puts one there."""
    directive = Directive(
        directive_id=directive_id,
        kind=DirectiveKind.TONE_NOTE,
        body="Scenes end on movement or cost, never on a tidy emotional summary.",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        author=author,
    )
    assert store.submit_directive(directive, received_at=STAMP)
    store.mark_directive_ingested(directive_id, ingested_at=STAMP)
    return directive


def interpret(
    store: SqliteStore,
    directive: Directive,
    *,
    logical_id: str = "constraint-scene-endings",
    text: str = ENDINGS,
    locked: bool = False,
    action: PlanEditAction = PlanEditAction.CREATE,
):
    """What `narrative_planner` did on both pilot runs: an unlocked constraint from a tone note.

    The reading cites no produced constraint, which is not this fixture being lazy — it is what
    the planner records, because it fills `produced_constraint_ids` from the constraints it
    minted *locked* and there were none.
    """
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    proposal = PlanProposal(
        base_plan_revision_id=base.plan_revision_id,
        summary="Encode the tone note as a book-wide prose constraint",
        rationale="A standing instruction about how the book is written.",
        expected_outcome="Every scene is drafted against it.",
        edits=(
            PlanEdit(
                action,
                logical_id,
                item(logical_id, lc.PlanKind.CONSTRAINT, text, locked=locked),
                "tone",
            ),
        ),
        readings=(
            DirectiveReading(
                directive.directive_id,
                "Standing instruction for how the whole book is written.",
                (logical_id,) if locked else (),
            ),
        ),
        profile="planner.directive.v0",
    )
    return accept_plan_proposal(
        store, proposal, project_id=PROJECT_ID, created_at=STAMP, actor="planner-test"
    )


def repair(store: SqliteStore) -> constraint_locks.LockOutcome:
    return constraint_locks.lock_directed_constraints(
        store,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        project_id=PROJECT_ID,
        created_at=STAMP,
        actor="lock-test",
    )


# -- the reproduction ---------------------------------------------------------------------


def test_a_constraint_a_person_directed_sits_unlocked_and_reaches_no_packet(
    store: SqliteStore,
) -> None:
    """The defect, in the shape the live store holds it.

    `plans.constraints_of` is the only door into the packet's CONSTRAINTS section and it selects
    on `locked`, so the item is present in the plan, visible to `litharness plans`, and absent
    from the one place it was written to reach.
    """
    root(store)
    interpret(store, submit(store, "dir-tone"))

    items = store.plan_items(BOOK_ID, BRANCH_ID)
    stored = next(entry for entry in items if entry.logical_id == "constraint-scene-endings")
    assert stored.text == ENDINGS
    assert stored.locked is False
    assert constraints_of(items) == ()


# -- the repair ---------------------------------------------------------------------------


def test_the_lock_repair_puts_a_human_directed_constraint_back_in_the_packet(
    store: SqliteStore,
) -> None:
    root(store)
    interpret(store, submit(store, "dir-tone"))

    outcome = repair(store)

    assert outcome.locked == ("constraint-scene-endings",)
    assert outcome.refused == ()
    assert outcome.application is not None
    reachable = constraints_of(store.plan_items(BOOK_ID, BRANCH_ID))
    assert [entry.logical_id for entry in reachable] == ["constraint-scene-endings"]
    assert reachable[0].text == ENDINGS


def test_the_lock_repair_changes_the_boolean_and_not_one_word_of_the_text(
    store: SqliteStore,
) -> None:
    root(store)
    before = interpret(store, submit(store, "dir-tone")).after.item("constraint-scene-endings")

    outcome = repair(store)

    assert outcome.application is not None
    after = outcome.application.after.item("constraint-scene-endings")
    assert after.text == before.text
    assert after.kind is before.kind and after.authority is before.authority
    assert after.scope == before.scope and after.links == before.links
    assert (before.locked, after.locked) == (False, True)


def test_a_second_run_of_the_lock_repair_proposes_nothing(store: SqliteStore) -> None:
    root(store)
    interpret(store, submit(store, "dir-tone"))
    first = repair(store)
    assert first.application is not None
    head_after_first = store.plan_revision(BOOK_ID, BRANCH_ID)

    second = repair(store)

    assert second.application is None
    assert second.candidates == ()
    assert store.plan_revision(BOOK_ID, BRANCH_ID) == head_after_first


def test_the_lock_repair_records_a_decision_and_a_proposal_an_operator_can_read(
    store: SqliteStore,
) -> None:
    root(store)
    interpret(store, submit(store, "dir-tone"))

    outcome = repair(store)

    assert outcome.application is not None
    head = outcome.application.after.plan_revision_id
    decision = store.decision_for_revision(head)
    assert decision is not None
    assert decision.profile == constraint_locks.PROFILE
    stored = store.load_plan_proposal(outcome.application.proposal.proposal_id)
    assert stored.status is PlanProposalStatus.APPLIED
    # The lineage the proposal cannot carry as a reading is carried as prose instead.
    assert "dir-tone" in stored.proposal.rationale


def test_the_repair_leaves_the_directive_applied_rather_than_transitioning_it(
    store: SqliteStore,
) -> None:
    """A `DirectiveReading` here would raise rather than record.

    `commit_plan_application` acts on a reading by calling `Directive.interpret`, which is
    `RECEIVED -> INTERPRETED`; the directives this repair traces are already APPLIED and
    `TRANSITIONS[APPLIED]` is `{SUPERSEDED}`. Carrying no reading is what makes the lane
    runnable at all, so the directive comes out of it exactly as it went in.
    """
    root(store)
    directive = submit(store, "dir-tone")
    interpret(store, directive)

    outcome = repair(store)

    assert outcome.application is not None
    assert outcome.application.proposal.readings == ()
    after = store.load_directive("dir-tone")
    assert after.status is DirectiveStatus.APPLIED
    assert after.produced_constraint_ids == ()


# -- the refusals -------------------------------------------------------------------------


def test_a_machine_authored_directives_constraint_is_refused_the_lock(
    store: SqliteStore,
) -> None:
    """The lock is a person's authority and a Director has none to spend."""
    root(store)
    interpret(store, submit(store, "dir-machine", author=machine_author("dir-alma")))

    outcome = repair(store)

    assert outcome.locked == ()
    assert outcome.application is None
    assert [entry.refused for entry in outcome.refused] == [constraint_locks.MACHINE_AUTHORED]
    assert constraints_of(store.plan_items(BOOK_ID, BRANCH_ID)) == ()


def test_a_constraint_no_proposal_attributes_to_a_directive_is_refused_the_lock(
    store: SqliteStore,
) -> None:
    """Unattributable is not human. An item whose authority cannot be recovered keeps its own."""
    base = root(store)
    orphan = PlanProposal(
        base_plan_revision_id=base.plan_revision_id,
        summary="A constraint with no directive behind it",
        rationale="Programmatic, not directed.",
        expected_outcome="Nothing claims authority for this.",
        edits=(
            PlanEdit(
                PlanEditAction.CREATE,
                "constraint-orphan",
                item("constraint-orphan", lc.PlanKind.CONSTRAINT, "No one asked for this."),
                "orphan",
            ),
        ),
    )
    accept_plan_proposal(
        store, orphan, project_id=PROJECT_ID, created_at=STAMP, actor="test"
    )

    outcome = repair(store)

    assert outcome.locked == ()
    assert [entry.refused for entry in outcome.refused] == [constraint_locks.NO_LINEAGE]


def test_the_lock_repair_leaves_promises_and_scene_plans_alone(store: SqliteStore) -> None:
    """`narrative_planner`'s symmetric rule forces the lock only on CONSTRAINT, and so does this.

    Widening it here would not restore what the fixed minting rule produces; it would be a
    second, wider rule invented by the repair — and an unlocked SCENE_PLAN is what `plan_search`
    is allowed to write alternatives over.
    """
    base = root(store)
    directive = submit(store, "dir-tone")
    proposal = PlanProposal(
        base_plan_revision_id=base.plan_revision_id,
        summary="A tone note that produced three kinds of item",
        rationale="One constraint, one promise, one scene plan.",
        expected_outcome="Only the constraint is a constraint.",
        edits=(
            PlanEdit(
                PlanEditAction.CREATE,
                "constraint-scene-endings",
                item("constraint-scene-endings", lc.PlanKind.CONSTRAINT, ENDINGS),
                "tone",
            ),
            PlanEdit(
                PlanEditAction.CREATE,
                "promise-the-loop",
                item("promise-the-loop", lc.PlanKind.PROMISE, "The loop is a holding."),
                "tone",
            ),
            PlanEdit(
                PlanEditAction.CREATE,
                "scene-1-plan",
                item("scene-1-plan", lc.PlanKind.SCENE_PLAN, "Silas catches a forgery."),
                "tone",
            ),
        ),
        readings=(DirectiveReading(directive.directive_id, "Standing instruction.", ()),),
    )
    accept_plan_proposal(
        store, proposal, project_id=PROJECT_ID, created_at=STAMP, actor="test"
    )

    outcome = repair(store)

    assert outcome.locked == ("constraint-scene-endings",)
    after = {entry.logical_id: entry.locked for entry in store.plan_items(BOOK_ID, BRANCH_ID)}
    assert after["promise-the-loop"] is False
    assert after["scene-1-plan"] is False


# -- the lineage --------------------------------------------------------------------------


def test_the_lineage_follows_the_last_edit_rather_than_the_first(store: SqliteStore) -> None:
    """The words in the plan are the last directive's, so the last directive is the authority.

    A constraint a person created and a Director later rewrote holds the Director's words, and
    locking it on the strength of the person who wrote the version that is gone would spend a
    person's authority on a machine's sentence.
    """
    root(store)
    interpret(store, submit(store, "dir-human"))
    interpret(
        store,
        submit(store, "dir-machine", author=machine_author("dir-alma")),
        text="Scenes end on a reveal.",
        action=PlanEditAction.UPDATE,
    )

    outcome = repair(store)

    assert outcome.locked == ()
    [refused] = outcome.refused
    assert refused.directive_id == "dir-machine"
    assert refused.refused == constraint_locks.MACHINE_AUTHORED


def test_a_rollback_clears_the_lineage_because_it_reads_no_directive(store: SqliteStore) -> None:
    """A restored item's authority is not recoverable from the proposal that restored it.

    `rollback_proposal` carries no readings by construction, so after one there is no applied
    proposal saying which directive the current words came from — and the safe answer to "who
    said this" is to leave the item alone and report it.

    This is also the ordering regression. Every proposal here shares one `created_at`, and
    `plan_proposals` orders on `(created_at, proposal_id)` — so under the clock these three sort
    on a content hash and the rollback lands wherever its hash falls. Walking
    `base_plan_revision_id -> resulting_plan_revision_id` is what makes the answer the chain's
    rather than the digest's.
    """
    root(store)
    before = interpret(store, submit(store, "dir-tone")).before
    current = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert current is not None
    undoing = next(
        stored
        for stored in store.plan_proposals(BOOK_ID, BRANCH_ID)
        if stored.resulting_plan_revision_id == current.plan_revision_id
    )
    accept_plan_proposal(
        store,
        rollback_proposal(current, before, rollback_of=undoing.proposal.proposal_id),
        project_id=PROJECT_ID,
        created_at=STAMP,
        actor="test",
    )
    # Put it back a second time, this time with no directive able to claim it.
    interpret(store, submit(store, "dir-second"))
    head = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert head is not None
    restored = next(
        stored
        for stored in store.plan_proposals(BOOK_ID, BRANCH_ID)
        if stored.status is PlanProposalStatus.APPLIED
        and stored.proposal.rollback_of is not None
    )

    lineage = constraint_locks.produced_by(store.plan_proposals(BOOK_ID, BRANCH_ID))

    assert restored.proposal.readings == ()
    # The rollback cleared it; the second interpretation re-attributed it.
    assert lineage["constraint-scene-endings"] == "dir-second"


def test_the_lineage_is_recovered_from_proposals_because_the_directive_column_is_empty(
    store: SqliteStore,
) -> None:
    """The field that should have carried this was emptied by the same defect.

    `narrative_planner` fills `produced_constraint_ids` from the constraints it minted *locked*,
    so a run that locked none records none — which is exactly what `serial.db` holds for every
    interpretive directive on the pilot.
    """
    root(store)
    interpret(store, submit(store, "dir-tone"))

    assert store.load_directive("dir-tone").produced_constraint_ids == ()
    lineage = constraint_locks.produced_by(store.plan_proposals(BOOK_ID, BRANCH_ID))
    assert lineage["constraint-scene-endings"] == "dir-tone"
