"""A reified occurrence's parts cannot precede the occurrence in model-facing state."""

from __future__ import annotations

from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness.application.model_context import at_scene
from litharness.domain import context, state, worlds
from litharness.domain.revision import new_book
from tests.helpers import canon


def _records(key: str | None) -> list[lc.StateRecord]:
    return [
        canon("gain", worlds.TYPE_PREDICATE, worlds.CHANGE, order_key=key),
        canon("gain", worlds.PARTICIPANT_ROLE, object_ref="mara"),
        canon("gain", worlds.EFFECT_ROLE, 1, object_ref="step"),
        canon("gain", worlds.MANIFESTS_PREDICATE, "The new step takes hold."),
        canon("mara", "wants", "find home"),
        canon("step", worlds.MANIFESTS_PREDICATE, "Contact redirects the fall."),
    ]


@pytest.mark.parametrize("key, present", [("s3", False), ("s1", True), ("s2", True), (None, True)])
def test_draft_context_keeps_change_parts_at_their_anchor_boundary(
    key: str | None, present: bool,
) -> None:
    records = _records(key)
    packet = context.assemble(
        new_book("book", "branch", title="Book", scenes=3),
        "scene-2",
        state_records=records,
        story_time_cutoff="s2",
    )

    text = packet.render()
    assert ("gain happened" in text) is present
    assert ("The new step takes hold." in text) is present
    assert "mara wants find home" in text
    assert "Contact redirects the fall." in text
    if not present:
        assert "gain participant" not in text and "gain effect" not in text
        omissions = {item.item_id: item.reason for item in packet.omitted}
        assert {record.record_id for record in records[:4]} <= omissions.keys()
        assert all("change 'gain'" in omissions[record.record_id] for record in records[1:4])


@pytest.mark.parametrize("key, present", [("s3", False), ("s1", True), ("s2", True), (None, True)])
def test_planning_context_keeps_change_parts_at_their_anchor_boundary(
    key: str | None, present: bool,
) -> None:
    view = at_scene(
        new_book("book", "branch", title="Book", scenes=3),
        _records(key),
        "scene-2",
        moment=state.StateMoment.THROUGH,
        story_order_key="s2",
    )

    assert any(record.subject == "gain" for record in view.active_records) is present
    assert ("The new step takes hold." in str(view.to_jsonable())) is present
    assert "mara wants find home" in view.lines
    assert any("Contact redirects the fall." in line for line in view.lines)


def test_unplaceable_change_keeps_its_parts_out_of_the_unplaced_planning_fallback() -> None:
    view = at_scene(
        new_book("book", "branch", title="Book", scenes=3),
        _records("0120"),
        "scene-1",
        moment=state.StateMoment.ENTERING,
    )

    assert "unplaced_only" in view.temporal_scope
    assert {record.subject for record in view.active_records} == {"mara", "step"}
    assert "The new step takes hold." not in str(view.to_jsonable())


@pytest.mark.parametrize("pov, present", [(None, False), ("other", False), ("mara", True)])
def test_change_parts_cannot_bypass_the_anchors_pov_restriction(
    pov: str | None, present: bool,
) -> None:
    records = _records(None)
    records[0] = replace(records[0], pov_visibility=["mara"])
    revision = new_book("book", "branch", title="Book", scenes=3)
    packet = context.assemble(
        revision,
        "scene-2",
        state_records=records,
        story_time_cutoff="s2",
        pov_character_id=pov,
    )

    assert ("The new step takes hold." in packet.render()) is present
    assert "Contact redirects the fall." in packet.render()
    view = at_scene(revision, records, "scene-2", moment=state.StateMoment.THROUGH)
    assert {record.subject for record in view.active_records} == {"mara", "step"}


@pytest.mark.parametrize("moment, present", [
    (state.StateMoment.ENTERING, False), (state.StateMoment.THROUGH, True),
])
def test_change_parts_follow_the_anchors_same_scene_evidence(
    moment: state.StateMoment, present: bool,
) -> None:
    records = _records("s2")
    records[0] = replace(records[0], evidence=[lc.EvidenceSpan(
        source=lc.ResourceRef(
            project_id="11111111-1111-5111-8111-111111111111",
            book_id="22222222-2222-5222-8222-222222222222",
            branch_id="33333333-3333-5333-8333-333333333333",
            logical_id="scene-2",
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
        start=10,
        end=20,
        content_sha256="0" * 64,
    )])
    revision = new_book("book", "branch", title="Book", scenes=3)
    packet = context.assemble(
        revision, "scene-2", state_records=records,
        story_time_cutoff="s2", state_moment=moment,
    )
    view = at_scene(revision, records, "scene-2", moment=moment, story_order_key="s2")

    assert ("The new step takes hold." in packet.render()) is present
    assert any(record.subject == "gain" for record in view.active_records) is present


@pytest.mark.parametrize("subject", ["gain", "mara"])
def test_a_proposed_change_anchor_cannot_hide_existing_accepted_facts(subject: str) -> None:
    records = [
        *_records(None),
        replace(
            worlds.world_record(
                subject, worlds.TYPE_PREDICATE, value=worlds.CHANGE, order_key="s3",
            ),
            record_id="proposed-change",
        ),
    ]
    revision = new_book("book", "branch", title="Book", scenes=3)
    packet = context.assemble(
        revision, "scene-2", state_records=records, story_time_cutoff="s2",
    )
    view = at_scene(
        revision, records, "scene-2", moment=state.StateMoment.THROUGH, story_order_key="s2",
    )

    assert "The new step takes hold." in packet.render()
    assert "mara wants find home" in packet.render()
    assert {record.subject for record in view.active_records} == {"gain", "mara", "step"}
    assert "proposed-change" not in {record.record_id for record in view.active_records}
