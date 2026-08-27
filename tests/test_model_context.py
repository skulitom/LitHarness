"""Model-facing state is explicit about time and never exposes later canon as current."""

from __future__ import annotations

import litharness_contracts as lc

from litharness.application.model_context import at_scene, current, planning_records
from litharness.domain import state, worlds
from litharness.domain.revision import new_book


def _fact(record_id: str, value: str, order_key: str | None) -> lc.StateRecord:
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.ASSERTION,
        subject="mara",
        predicate="wants",
        value=value,
        story_position=(lc.StoryPosition(order_key=order_key) if order_key else None),
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def test_a_planning_view_is_bounded_and_collapses_superseded_state() -> None:
    revision = new_book("book", "branch", title="Book", scenes=3)
    records = (
        _fact("want-1", "escape", "s1"),
        _fact("want-2", "hide", "s2"),
        _fact("want-3", "return", "s3"),
    )

    view = at_scene(revision, records, "scene-2", moment=state.StateMoment.THROUGH)

    assert view.lines == ("mara wants hide",)
    assert [record.record_id for record in view.superseded_records] == ["want-1"]
    assert view.to_jsonable()["boundary"] == {
        "moment": "through",
        "temporal_scope": "bounded",
        "coordinate_source": "serial_ordinal",
        "scene": "scene-2",
        "scene_ordinal": 2,
        "story_order_key": "s2",
    }


def test_an_unknown_story_coordinate_abstains_instead_of_leaking_future_state() -> None:
    revision = new_book("book", "branch", title="Book", scenes=2)
    timeless = _fact("timeless", "freedom", None)
    positioned = _fact("positioned", "the ending", "chapter-two")

    view = at_scene(
        revision,
        (timeless, positioned),
        "scene-1",
        moment=state.StateMoment.ENTERING,
    )

    assert view.lines == ("mara wants freedom",)
    assert "unplaced_only" in view.temporal_scope


def test_attested_story_time_wins_over_reading_ordinal_for_an_analepsis() -> None:
    revision = new_book("book", "branch", title="Book", scenes=3)
    span = lc.EvidenceSpan(
        source=lc.ResourceRef(
            project_id="11111111-1111-5111-8111-111111111111",
            book_id="22222222-2222-5222-8222-222222222222",
            branch_id="33333333-3333-5333-8333-333333333333",
            logical_id="scene-3",
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
        start=0,
        end=1,
        content_sha256="0" * 64,
    )
    flashback = lc.StateRecord(
        record_id="flashback-want",
        kind=lc.StateRecordKind.ASSERTION,
        subject="mara",
        predicate="wants",
        value="escape",
        story_position=lc.StoryPosition(order_key="s1"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        evidence=[span],
    )
    later = _fact("later-want", "return", "s2")

    view = at_scene(
        revision,
        (flashback, later),
        "scene-3",
        moment=state.StateMoment.THROUGH,
    )

    assert view.story_order_key == "s1"
    assert view.coordinate_source == "evidence_attested"
    assert view.lines == ("mara wants escape",)


def test_current_state_uses_the_furthest_accepted_scene() -> None:
    blank = new_book("book", "branch", title="Book", scenes=3)
    revision = blank.replacing([blank.node("scene-3").with_content("Accepted later scene.")])
    records = tuple(
        _fact(f"want-{n}", value, f"s{n}")
        for n, value in enumerate(("escape", "hide", "return"), start=1)
    )

    assert current(revision, records).lines == ("mara wants return",)


def test_planning_world_keeps_reveal_design_without_future_mutable_state() -> None:
    revision = new_book("book", "branch", title="Book", scenes=3)
    disclosure = worlds.world_record(
        "disclosure",
        worlds.DISCLOSED_TO,
        value=worlds.READER,
        object_ref="claim-gate",
        order_key="s3",
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    records = (
        _fact("want-now", "escape", "s1"),
        _fact("want-future", "return", "s3"),
        worlds.world_record(
            "claim-gate",
            worlds.CLAIM_CONTENT,
            value="The gate is choosing replacements.",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        disclosure,
    )
    view = at_scene(revision, records, "scene-1", moment=state.StateMoment.THROUGH)

    planned = planning_records(records, view)

    assert "want-now" in {record.record_id for record in planned}
    assert "want-future" not in {record.record_id for record in planned}
    assert disclosure.record_id in {record.record_id for record in planned}
    payload = view.to_jsonable()
    assert "choosing replacements" not in str(payload["established_facts"])
    assert payload["undisclosed_record_count"] == 1
