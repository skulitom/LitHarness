"""Production handoffs preserve author/canon context without repeating the treatment."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, outline, planner
from litharness.domain import context, house, worlds
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.plans import scene_plan_for, scene_plan_line
from litharness.domain.scene_brief import PREFIX, SceneBrief, render_plan
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.helpers import accepted
from tests.test_concept import _discovery, _example
from tests.test_outline import START, StubPlanner, _job, a_book, payload_for


def brief_payload() -> dict:
    return {
        "situation": "The path has vanished under water.",
        "pursuit": "Reach the stranded companion.",
        "changes": ["She freezes a stepping stone.", "The companion crosses before it melts."],
        "future_dependencies": ["The companion has not learned who sent the flood."],
    }


def outlined_payload(count: int = 6) -> dict:
    payload = payload_for(count)
    payload["scenes"] = [
        {
            "ordinal": entry["ordinal"],
            "brief": {**brief_payload(), "changes": [entry["statement"]]},
        }
        for entry in payload["scenes"]
    ]
    return {**payload, "milestones": []}


def test_brief_round_trip_preserves_order_and_keeps_storage_syntax_out_of_the_prompt():
    brief = SceneBrief.from_payload(brief_payload())
    assert SceneBrief.from_text(brief.to_text()) == brief
    rendered = scene_plan_line(brief.to_text())
    assert PREFIX not in rendered
    assert rendered.index(brief.changes[0]) < rendered.index(brief.changes[1])
    assert brief.future_dependencies[0] in rendered
    assert "not events or explanations to insert now" in rendered
    assert "author locks take precedence" in rendered
    plain = "An author's existing plan.\nKeep its wording."
    assert render_plan(plain) == plain
    assert scene_plan_line(plain) == f" This scene: {plain}"
    empty_future = SceneBrief.from_payload({**brief_payload(), "future_dependencies": []})
    assert "Later-story dependencies" not in empty_future.render()


@pytest.mark.parametrize("change", [
    {"situation": " "}, {"pursuit": None}, {"changes": []}, {"changes": "an action"},
    {"changes": [False]}, {"future_dependencies": None}, {"future_dependencies": [""]},
    {"rating": "excellent"},
])
def test_malformed_briefs_are_not_silently_treated_as_legacy_plans(change):
    with pytest.raises(ValueError):
        SceneBrief.from_payload({**brief_payload(), **change})


@pytest.mark.parametrize("text", [
    PREFIX + "[]", PREFIX + "{}", PREFIX + "{", "litharness.scene-brief.v9\n{}",
])
def test_malformed_stored_briefs_refuse_instead_of_leaking_serialized_text(text):
    with pytest.raises(ValueError):
        render_plan(text)


def test_author_brief_is_owned_by_the_operator_and_excluded_from_precision_edits():
    discovery = concept.Discovery.from_payload(_discovery())
    original = "Keep both sisters alive.\nThe journey lasts eleven days."
    drawn = concept.Concept.from_development(
        {**_example(), "author_brief": "a model replacement"}, discovery, author_brief=original
    )
    assert concept.Concept.from_text(drawn.to_text()).author_brief == original
    assert drawn.for_outline()["author_brief"] == original
    fields, protected = drawn.precision_material()
    assert "author_brief" not in fields
    assert protected["author_brief"] == original
    assert drawn.with_precision_edits({"edits": []}).author_brief == original
    assert replace(drawn, author_brief="Avoid the name The Standing.").machinery_names() == ()
    with pytest.raises(concept.MalformedConcept, match="author_brief"):
        concept.Concept.from_payload({**_example(), "author_brief": 11})


@pytest.mark.parametrize("malformed_brief", [False, True])
def test_outline_rejects_unusable_concept_response_before_persisting(tmp_path, malformed_brief):
    drawn = concept.Concept.from_payload({**_example(), "discovery": _discovery()})
    with SqliteStore.open(tmp_path / "reject.db") as store:
        a_book(store, scenes=6, extra_plan_items=(drawn.plan_item(),))
        before = store.plan_revision(BOOK_ID, BRANCH_ID)
        response = {**payload_for(6), "milestones": []}
        if malformed_brief:
            response = outlined_payload()
            response["scenes"][0]["brief"]["changes"] = []
        outline.make_outline_handler(StubPlanner(response), store, PROJECT_ID)(_job(store), START)
        assert store.plan_revision(BOOK_ID, BRANCH_ID) == before
        assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1") is None


@pytest.mark.parametrize("author_brief", ["", "Keep the companion alive.\nUse third person."])
def test_production_outline_to_draft_handoff_excludes_source_but_preserves_canon(
    tmp_path, author_brief
):
    drawn = concept.Concept.from_payload({
        **_example(), "discovery": _discovery(), "author_brief": author_brief,
    })
    lock = lc.PlanItem(
        logical_id="author-limit", kind=lc.PlanKind.CONSTRAINT,
        text="The companion survives every crossing.",
        authority=lc.PlanAuthority.INTENDED, locked=True,
    )
    rule = accepted(worlds.world_record(
        "ice", worlds.WORLD_RULE_PREDICATE, value="Freezing a stone consumes heat from her hand."
    ))
    with SqliteStore.open(tmp_path / "handoff.db") as store:
        revision = a_book(store, scenes=6, extra_plan_items=(drawn.plan_item(), lock))
        store.record_state_records(BOOK_ID, BRANCH_ID, [rule], created_at="2026-09-08T00:00:00Z")
        registry = StubPlanner(outlined_payload())
        outline.make_outline_handler(registry, store, PROJECT_ID)(_job(store), START)
        request = registry.requests[0]
        assert request.schema == outline.CONCEPT_OUTLINE_SCHEMA
        assert house.CLARITY not in request.system
        source = json.loads(request.prompt)["book_concept"]
        assert source["discovery"] == drawn.discovery.to_jsonable()
        plan = scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1")
        assert plan is not None and not plan.locked
        assert plan.authority is lc.PlanAuthority.INTENDED
        brief = SceneBrief.from_text(plan.text)
        assert brief is not None
        job = planner.make_plan_selector(project_id=PROJECT_ID)(store, "writer", START + 1, 60)
        assert job is not None and job.job_kind != outline.BOOK_OUTLINE
        system, prompt = job.payload["system"], job.payload["prompt"]
        assert brief.render() in prompt
        assert PREFIX not in prompt
        source_entry = next(
            entry for entry in job.payload["prompt_sources"]["entries"]
            if entry["kind"] == "scene_plan"
        )
        assert source_entry["source"]["source_logical_id"] == plan.logical_id
        assert source_entry["source"]["rendered_equals_stored"] is False
        assert lock.text in system and str(rule.value) in system
        assert drawn.discovery.opening not in prompt
        assert drawn.first_arc.closes not in prompt
        assert drawn.system.strongest_known not in prompt
        if author_brief:
            assert author_brief in prompt

        beat = beats_for(revision, arc_template(6))[0]
        before = planner.packet_for(store, revision, beat).render()
        # A prose-only change in the discarded proposal cannot affect the writer packet.
        revised = replace(
            drawn, discovery=replace(drawn.discovery, opening="Unused proposal wording.")
        )
        items = store.plan_items(BOOK_ID, BRANCH_ID)
        store.record_plan_items(BOOK_ID, BRANCH_ID, [
            revised.plan_item() if item.logical_id == concept.CONCEPT_PLAN_ID else item
            for item in items
        ], created_at="2026-09-08T01:00:00Z")
        assert planner.packet_for(store, revision, beat).render() == before
        # Ordinary author/directive plan edits must not resurrect the full treatment.
        store.record_plan_items(BOOK_ID, BRANCH_ID, [
            replace(item, text="Cross by the upstream route.") if item.logical_id == plan.logical_id
            else item for item in store.plan_items(BOOK_ID, BRANCH_ID)
        ], created_at="2026-09-08T02:00:00Z")
        assert planner.packet_for(store, revision, beat).render() == before
        packet = planner.packet_for(store, revision, beat)
        assert all(item.authority is lc.StateAuthority.ACCEPTED_CANON
                   for item in packet.sections[context.RULES])
