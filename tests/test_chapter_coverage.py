"""Actual chapter membership survives invention, planning, persistence and continuation."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, discovery, outline, planner
from litharness.application.chapter_layout import WritingLayout
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.plan_refinement import apply_plan_proposal
from litharness.domain.plans import scene_plan_for
from litharness.domain.revision import new_book
from litharness.domain.serials import SerialShape, chapter_positions
from litharness.providers.base import parse_schema_payload
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_concept import _example, _scripted
from tests.test_experience_brief import EXPERIENCE, treatment
from tests.test_outline import START, StubPlanner, _job, a_book
from tests.test_scene_brief import outlined_payload


def source():
    return concept.Concept.from_development(
        _example(), treatment(), author_brief="Keep the brother on the ground until chapter three."
    )


def grouped(layout):
    payload = outlined_payload(layout.scene_count)
    payload["payoff_windows"] = []
    scenes = payload.pop("scenes")
    payload["chapters"] = [{
        "chapter": chapter,
        "intent": f"Develop the planned choices in chapter {chapter}.",
        "adaptation": "The author's timing takes priority over the generated opening proposal.",
        "scenes": [scenes[ordinal - 1] for ordinal in ordinals],
    } for chapter, ordinals in layout.chapters]
    return payload


@pytest.mark.parametrize("count,shape,target", [
    (6, SerialShape(1, 6), 1400), (8, SerialShape(4, 2), 700),
    (7, SerialShape(3, 3), 0), (3, SerialShape(2, 6), None),
])
def test_invention_layout_uses_manuscript_grouping_including_partial_chapters(count, shape, target):
    revision = new_book("b", "main", title="Layout", scenes=count)
    positions = chapter_positions(revision, shape)
    layout = WritingLayout.opening(count, shape, target)
    for row in layout.to_jsonable()["chapters"]:
        for ordinal in row["scene_ordinals"]:
            assert positions[f"scene-{ordinal}"].chapter_index == row["chapter"]
        if target is None:
            assert "target_words" not in row
        else:
            assert row["target_words"] == target * len(row["scene_ordinals"])
    assert layout.scene_count == count


@pytest.mark.parametrize("chapters,target", [
    ((), 0), (((1, (1,)), (1, (2,))), 0), (((1, (1, 1)),), 0),
    (((True, (1,)),), 0), (((1, (2,)),), 0), (((1, (2, 1)),), 0),
    (((1, (1,)),), -1), (((1, (1,)),), True),
])
def test_invalid_layout_cannot_describe_a_different_chapter_map(chapters, target):
    with pytest.raises(ValueError):
        WritingLayout(chapters, target)


def test_cli_supplies_identical_effective_layout_to_discovery_and_development(
    tmp_path, monkeypatch,
):
    calls = _scripted(treatment().to_jsonable(), _example(), {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", calls)
    out = tmp_path / "concept"
    assert cli.main([
        "--database", str(tmp_path / "book.db"), "--chapter-scenes", "2",
        "--arc-chapters", "3", "--target-words", "700", "concept", "--no-seed",
        "--brief", "Keep the brother on the ground until chapter three.",
        "--scenes", "6", "--out", str(out),
    ]) == cli.EXIT_OK
    received = [json.loads(request.prompt.rsplit("writing_layout:\n", 1)[1])
                for request in calls.seen[:2]]
    expected = WritingLayout.opening(6, SerialShape(2, 3), 700).to_jsonable()
    assert received[0] == received[1] == expected
    saved = concept.Concept.from_text((out / "concept.json").read_text(encoding="utf-8"))
    assert saved.author_brief == source().author_brief
    assert saved.discovery.experience_brief == EXPERIENCE
    assert "writing_layout" not in saved.author_brief


def test_direct_callers_can_omit_layout_but_cannot_supply_a_conflicting_count():
    assert "writing_layout" not in discovery.render_request("A garden").prompt
    with pytest.raises(ValueError, match="scene count disagrees"):
        concept.render_concept_request("A garden", scenes=6,
                                       layout=WritingLayout.opening(4, SerialShape(), 900))
    with pytest.raises(ValueError, match="no chapter"):
        WritingLayout.mapped([("s1", 1), ("s2", 2)], {"s1": 1}, 900)


def test_grouped_outline_is_persisted_with_revised_intent_and_exact_scene_handoff(
    tmp_path, monkeypatch,
):
    layout = WritingLayout.opening(6, SerialShape(2, 3), 700)
    response = grouped(layout)
    registry = StubPlanner(response)
    monkeypatch.setattr(cli, "build_default_registry", lambda: registry)
    args = cli.build_parser().parse_args([
        "--project", PROJECT_ID, "--chapter-scenes", "2", "--arc-chapters", "3",
        "--target-words", "700", "tick",
    ])
    with SqliteStore.open(tmp_path / "book.db") as store:
        a_book(store, scenes=6, extra_plan_items=(source().plan_item(),))
        conductor = cli._conductor(store, args)
        job = conductor.select(store, "planner", START, 60)
        assert job.job_kind == outline.BOOK_OUTLINE
        conductor.handlers[outline.BOOK_OUTLINE](job, START)
        assert store.latest_decision_for(job.job_id).accepted
        [request] = registry.requests
        payload = json.loads(request.prompt)
        assert payload["writing_layout"] == layout.to_jsonable()
        assert payload["book_concept"]["author_brief"] == source().author_brief
        assert payload["book_concept"]["discovery"]["experience_brief"] == EXPERIENCE
        assert request.schema == outline.CHAPTER_OUTLINE_SCHEMA
        assert parse_schema_payload(json.dumps(response), request.schema) == response
        assert parse_schema_payload(json.dumps(outlined_payload()), request.schema) is None
        items = store.plan_items(BOOK_ID, BRANCH_ID)
        coverage = [item for item in items if item.kind is lc.PlanKind.CHAPTER_PLAN]
        assert len(coverage) == 3
        first = next(item for item in coverage if item.logical_id == "chapter-coverage-scene-1")
        assert not first.locked and first.authority is lc.PlanAuthority.INTENDED
        kept = json.loads(first.text.split("\n", 1)[1])
        assert kept["scene_ids"] == ["scene-1", "scene-2"]
        assert kept["adaptation"] == response["chapters"][0]["adaptation"]
        draft = conductor.select(store, "writer", START + 1, 60)
        assert draft.job_kind == planner.SCENE_DRAFT
        assert "chapter 1 (1 of this arc); scene 1 of 2" in draft.payload["prompt"]
        planned_change = response["chapters"][0]["scenes"][0]["brief"]["changes"][0]
        assert planned_change in draft.payload["prompt"]
        assert source().author_brief in draft.payload["prompt"]
        assert kept["adaptation"] not in draft.payload["prompt"]
        assert "litharness.chapter-coverage" not in draft.payload["prompt"]
        assert concept.concept_of(items) == source()


@pytest.mark.parametrize("fault", ["swapped", "duplicate", "missing", "blank", "bool", "flat"])
def test_wrong_coverage_refuses_before_any_plan_or_schedule_is_written(tmp_path, fault):
    layout = WritingLayout.opening(6, SerialShape(1, 6), 1400)
    response = grouped(layout)
    if fault == "swapped":
        a, b = response["chapters"][:2]
        a["scenes"], b["scenes"] = b["scenes"], a["scenes"]
    elif fault == "duplicate":
        response["chapters"][1] = deepcopy(response["chapters"][0])
    elif fault == "missing":
        response["chapters"].pop()
    elif fault == "blank":
        response["chapters"][0]["adaptation"] = " "
    elif fault == "bool":
        response["chapters"][0]["scenes"][0]["ordinal"] = True
    else:
        response = outlined_payload()
    with SqliteStore.open(tmp_path / "refused.db") as store:
        a_book(store, scenes=6, extra_plan_items=(source().plan_item(),))
        before = store.plan_revision(BOOK_ID, BRANCH_ID)
        job = _job(store)
        job = replace(job, payload={**job.payload, "chapter_by_scene": {
            f"scene-{i}": i for i in range(1, 7)
        }})
        registry = StubPlanner(response)
        outline.make_outline_handler(registry, store, PROJECT_ID)(job, START)
        assert len(registry.requests) == 1
        assert not store.latest_decision_for(job.job_id).accepted
        assert store.plan_revision(BOOK_ID, BRANCH_ID) == before
        assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1") is None


def test_continuation_uses_response_ordinals_but_preserves_chapter_and_scene_identities(tmp_path):
    with SqliteStore.open(tmp_path / "suffix.db") as store:
        revision = a_book(store, scenes=6, extra_plan_items=(source().plan_item(),))
        original = beats_for(revision, arc_template(6))
        remaining = tuple(replace(beat, ordinal=i, of_total=4)
                          for i, beat in enumerate(original[2:], 1))
        mapping = {f"scene-{i}": (i - 1) // 2 + 1 for i in range(1, 7)}
        layout = WritingLayout.mapped([(b.logical_id, b.ordinal) for b in remaining], mapping, 700)
        assert layout.chapters == ((2, (1, 2)), (3, (3, 4)))
        payload = grouped(layout)
        registry = StubPlanner(payload)
        base = store.plan_revision(BOOK_ID, BRANCH_ID)
        request = outline.render_outline_request(
            "A garden", remaining, base=base, concept=source(), chapter_by_scene=mapping,
            target_scene_words=700, continuation_scope={"requested_scenes": []},
        )
        result, _ = registry.complete(request)
        proposal = outline.outline_proposal(
            payload, base=base, beats=remaining, original_beats=original, project_id=PROJECT_ID,
            book_id=BOOK_ID, branch_id=BRANCH_ID, result=result, chapter_by_scene=mapping,
        )
        after = apply_plan_proposal(base, proposal).after
        assert after.item(source().plan_item().logical_id) == source().plan_item()
        first = json.loads(after.item("chapter-coverage-scene-3").text.split("\n", 1)[1])
        assert first["chapter"] == 2 and first["scene_ids"] == ["scene-3", "scene-4"]
        assert scene_plan_for(after.items, "scene-1") is None
        assert scene_plan_for(after.items, "scene-2") is None
        assert scene_plan_for(after.items, "scene-3") is not None
        assert outline.CONTINUATION_RULE in json.loads(request.prompt)["rules"]
