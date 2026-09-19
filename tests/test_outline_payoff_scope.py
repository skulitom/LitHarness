"""Later arcs schedule only feasible promises using response-local coordinates."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import outline
from litharness.domain import serials
from litharness.domain.promises import Promise
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_continuation_outline import OPENING, STAMP, _frozen_job
from tests.test_outline import START, StubPlanner, a_book, payload_for


def test_second_arc_preserves_overdue_debt_and_schedules_only_eligible_scenes(tmp_path):
    with SqliteStore.open(tmp_path / "book.db") as store:
        head = a_book(store, scenes=12, sheet=False)
        head = head.replacing([head.node(f"scene-{i}").with_content(OPENING)
                               for i in range(1, 7)])
        store.commit_revision(head, created_at=STAMP)
        beats = serials.beats_for_serial(head, serials.SerialShape(1, 6))
        promises = [Promise(
            promise_id=subject, subject=subject, description="An unresolved obligation.",
            opened_at_key=beats[opened-1].story_order_key,
            due_key=beats[due-1].story_order_key if due else None,
            opened_by_revision=head.revision_id,
        ) for subject, opened, due in [("overdue", 1, 6), ("current", 2, 9),
                                      ("later", 11, None)]]
        for promise in promises:
            store.record_promise(BOOK_ID, BRANCH_ID, promise)
        response = payload_for(6)
        response["payoff_windows"] = [
            {"subject": "current", "first_scene": 1, "last_scene": 3},
            {"subject": "later", "first_scene": 5, "last_scene": 6},
        ]
        model = StubPlanner(response)
        job = _frozen_job(store)
        job = replace(job, payload={**job.payload, "arc_index": 2, "scenes_per_chapter": 1,
                                   "chapters_per_arc": 6,
                                   "chapter_by_scene": {f"scene-{i}": i for i in range(7, 13)}})
        outline.make_outline_handler(model, store, PROJECT_ID)(job, START)
        decision = store.latest_decision_for(job.job_id)
        assert decision.accepted, decision.reason
        body = json.loads(model.requests[0].prompt)
        assert body.get("continuation_scope") is None
        assert outline.COORDINATE_RULE in body["rules"]
        assert [(s["ordinal"], s["chapter"], s["story_order_key"]) for s in body["scenes"]] == [
            (local, local + 6, beats[local + 5].story_order_key) for local in range(1, 7)
        ]
        owed = {p["subject"]: p for p in body["open_promises"]}
        assert owed["overdue"]["schedulable_scene_ordinals"] == []
        assert owed["overdue"]["due_by_scene"] == beats[5].story_order_key
        assert owed["current"]["schedulable_scene_ordinals"] == [1, 2, 3]
        assert owed["later"]["schedulable_scene_ordinals"] == [5, 6]
        saved = {p.subject: p for p in store.promises(BOOK_ID, BRANCH_ID, open_only=True)}
        assert saved["overdue"] == promises[0]
        assert saved["current"].window_end_key == beats[8].story_order_key
        assert saved["later"].window_start_key == beats[10].story_order_key
        assert store.head(BOOK_ID, BRANCH_ID) == head
        for subject, first, last, reason in [("overdue", 1, 1, "after .* is due"),
                                           ("current", 7, 9, "does not exist")]:
            with pytest.raises(outline.OutlineOutputError, match=reason):
                outline._payoff_windows({"payoff_windows": [
                    {"subject": subject, "first_scene": first, "last_scene": last},
                ]}, beats[6:], promises)


@pytest.mark.parametrize("template", [outline.OUTLINE_SCHEMA, outline.CONCEPT_OUTLINE_SCHEMA,
                                     outline.CHAPTER_OUTLINE_SCHEMA,
                                     outline.STRUCTURED_OUTLINE_SCHEMA,
                                     outline.STRUCTURED_CHAPTER_OUTLINE_SCHEMA])
def test_response_schema_rejects_book_coordinates_without_mutating_templates(template):
    from jsonschema import Draft202012Validator

    from litharness.domain.revision import new_book
    from litharness.providers.codex_schema import prepare_codex_schema

    head = new_book(BOOK_ID, BRANCH_ID, title="Coordinates", scenes=12)
    beats = serials.beats_for_serial(head, serials.SerialShape(1, 6))[6:]
    before = deepcopy(template)
    schema = outline._response_schema(template, beats)
    assert template == before
    properties = schema["properties"]
    native = prepare_codex_schema({"type": "object", "required": ["payoff_windows"],
                                   "properties": {"payoff_windows": properties["payoff_windows"]}})
    for name in ("first_scene", "last_scene"):
        field = properties["payoff_windows"]["items"]["properties"][name]
        assert field["enum"] == list(range(1, 7))
        assert Draft202012Validator(field).is_valid(1)
        assert not Draft202012Validator(field).is_valid(7)
        assert native["properties"]["payoff_windows"]["items"]["properties"][name] == field
    for name in ("milestones", "standing_milestones"):
        assert properties[name]["items"]["properties"]["ordinal"]["enum"] == list(range(1, 7))
    unpositioned = [replace(beat, story_order_key=None) for beat in beats]
    assert "enum" not in outline._response_schema(template, unpositioned)["properties"][
        "payoff_windows"]["items"]["properties"]["first_scene"]
    assert outline._response_schema(template, []) == template
