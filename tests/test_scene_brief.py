"""Production handoffs preserve author/canon context without repeating the treatment."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, outline, planner
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.domain import context, house, worlds
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.plan_refinement import (
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalError,
)
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


@pytest.mark.parametrize("locked_concept", [False, True])
def test_no_outline_writer_uses_foundations_unless_the_full_concept_is_author_locked(
    tmp_path, locked_concept, monkeypatch
):
    original = "Keep the companion alive.\nUse third person."
    drawn = concept.Concept.from_payload({
        **_example(), "discovery": _discovery(), "author_brief": original,
    })
    source_item = replace(drawn.plan_item(), locked=locked_concept)
    rule = accepted(worlds.world_record(
        "ice", worlds.WORLD_RULE_PREDICATE, value="Freezing a stone consumes heat from her hand."
    ))
    with SqliteStore.open(tmp_path / "no-outline.db") as store:
        revision = a_book(store, scenes=6, extra_plan_items=(source_item,))
        store.record_state_records(BOOK_ID, BRANCH_ID, [rule], created_at="2026-09-08T00:00:00Z")
        registry = StubPlanner(outlined_payload())
        monkeypatch.setattr(cli, "build_default_registry", lambda: registry)
        args = cli.build_parser().parse_args([
            "--project", PROJECT_ID, "--no-outline", "--target-words", "1800",
            "--chapter-scenes", "1", "--arc-chapters", "6", "tick",
        ])
        job = cli._conductor(store, args).select(store, "writer", START, 60)
        assert job is not None and job.job_kind == planner.SCENE_DRAFT
        assert not registry.requests
        assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1") is None
        assert concept.concept_of(store.plan_items(BOOK_ID, BRANCH_ID)) == drawn
        beat = beats_for(revision, arc_template(6))[0]
        packet = planner.packet_for(store, revision, beat)
        source = next(item for item in packet.sections[context.INTENTIONS]
                      if item.source_logical_id == concept.CONCEPT_PLAN_ID)
        assert source.authority is lc.StateAuthority.PROPOSED
        system, prompt = job.payload["system"], job.payload["prompt"]
        assert source.text in prompt
        assert str(rule.value) in system
        assert "1800 words" in system
        assert "chapter 1 (1 of this arc); scene 1 of 1" in prompt
        assert "Print that line exactly once" not in system
        assert "status update at the result" in system
        assert "no update is required" in system
        if locked_concept:
            assert source.text == drawn.render()
            assert original in source.text
            assert drawn.discovery.opening in source.text
            assert drawn.first_use in source.text
            assert drawn.threat.first_reach in source.text
        else:
            label, material = source.text.split("\n", 1)
            assert "future intentions" in label
            foundation = json.loads(material)
            assert foundation == drawn.for_outline()
            assert foundation["author_brief"] == original
            assert foundation["discovery"]["world"] == drawn.discovery.world
            assert foundation["discovery"]["growth"] == drawn.discovery.growth
            assert foundation["person_before"] == drawn.person_before
            assert foundation["want"] == drawn.want
            assert foundation["system"] == drawn.to_jsonable()["system"]
            assert "opening" not in foundation["discovery"]
            assert "first_use" not in foundation
            assert "first_reach" not in foundation["threat"]
            assert "opens" not in foundation["first_arc"]
            for excluded in (drawn.discovery.opening, drawn.first_use, drawn.threat.first_reach):
                assert excluded not in prompt


@pytest.mark.parametrize("author_brief", ["", "Keep the companion alive.\nUse third person."])
@pytest.mark.parametrize("locked_concept", [False, True])
def test_production_outline_to_draft_handoff_excludes_source_but_preserves_canon(
    tmp_path, author_brief, locked_concept, monkeypatch
):
    drawn = concept.Concept.from_payload({
        **_example(), "discovery": _discovery(), "author_brief": author_brief,
    })
    lock = lc.PlanItem(
        logical_id="author-limit", kind=lc.PlanKind.CONSTRAINT,
        text="The companion survives every crossing.",
        authority=lc.PlanAuthority.INTENDED, locked=True,
    )
    timing = lc.PlanItem(
        logical_id="author-timing", kind=lc.PlanKind.CONSTRAINT,
        text="The first successful cast occurs in this scene.",
        authority=lc.PlanAuthority.INTENDED, locked=True,
        scope=lc.ResourceRef(
            project_id=PROJECT_ID, book_id=BOOK_ID, branch_id=BRANCH_ID,
            logical_id="scene-1", kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
    )
    rule = accepted(worlds.world_record(
        "ice", worlds.WORLD_RULE_PREDICATE, value="Freezing a stone consumes heat from her hand."
    ))
    with SqliteStore.open(tmp_path / "handoff.db") as store:
        source_item = replace(drawn.plan_item(), locked=locked_concept)
        revision = a_book(store, scenes=6, extra_plan_items=(source_item, lock, timing))
        store.record_state_records(BOOK_ID, BRANCH_ID, [rule], created_at="2026-09-08T00:00:00Z")
        registry = StubPlanner(outlined_payload())
        monkeypatch.setattr(cli, "build_default_registry", lambda: registry)
        args = cli.build_parser().parse_args([
            "--project", PROJECT_ID, "--target-words", "1300",
            "--chapter-scenes", "1", "--arc-chapters", "6", "tick",
        ])
        conductor = cli._conductor(store, args)
        outline_job = conductor.select(store, "worker", START, 60)
        assert outline_job is not None and outline_job.job_kind == outline.BOOK_OUTLINE
        conductor.handlers[outline.BOOK_OUTLINE](outline_job, START)
        request = registry.requests[0]
        assert json.loads(request.prompt)["target_scene_words"] == 1300
        chapters = [item["chapter"] for item in json.loads(request.prompt)["scenes"]]
        assert chapters == list(range(1, 7))
        planning_rules = json.loads(request.prompt)["rules"]
        assert all(rule in planning_rules for rule in outline.SCENE_HANDOFF_RULES)
        routed_locks = json.loads(request.prompt)["author_locks"]
        expected_locks = (lock, timing, source_item) if locked_concept else (lock, timing)
        assert {item["logical_id"]: item for item in routed_locks} == {
            item.logical_id: lc.to_jsonable(item) for item in expected_locks
        }
        decision = store.latest_decision_for(outline_job.job_id)
        assert decision is not None
        assert decision.policy_config_digest == outline._policy_digest(target_scene_words=1300)
        assert decision.policy_config_digest != outline._policy_digest()
        assert request.schema == outline.CONCEPT_OUTLINE_SCHEMA
        assert house.CLARITY not in request.system
        source = json.loads(request.prompt)["book_concept"]
        assert source == drawn.for_outline()
        assert source["discovery"] == {
            "version": drawn.discovery.to_jsonable()["version"],
            "world": drawn.discovery.world, "growth": drawn.discovery.growth,
        }
        assert "first_use" not in source
        assert "first_reach" not in source["threat"]
        assert "opens" not in source["first_arc"]
        assert source["person_before"] == drawn.person_before
        assert source["want"] == drawn.want
        assert source["system"] == drawn.to_jsonable()["system"]
        assert source["second_system"] == drawn.to_jsonable()["second_system"]
        assert source["turn"] == drawn.to_jsonable()["turn"]
        assert source["debts"] == drawn.to_jsonable()["debts"]
        assert source["first_arc"]["closes"] == drawn.first_arc.closes
        assert concept.concept_of(store.plan_items(BOOK_ID, BRANCH_ID)) == drawn
        plan = scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1")
        assert plan is not None and not plan.locked
        assert plan.authority is lc.PlanAuthority.INTENDED
        brief = SceneBrief.from_text(plan.text)
        assert brief is not None
        job = conductor.select(store, "writer", START + 1, 60)
        assert job is not None and job.job_kind != outline.BOOK_OUTLINE
        system, prompt = job.payload["system"], job.payload["prompt"]
        assert "1300 words" in system
        assert "chapter 1 (1 of this arc); scene 1 of 1" in prompt
        assert all(rule not in system + prompt for rule in outline.SCENE_HANDOFF_RULES)
        assert brief.render() in prompt
        assert PREFIX not in prompt
        source_entry = next(
            entry for entry in job.payload["prompt_sources"]["entries"]
            if entry["kind"] == "scene_plan"
        )
        assert source_entry["source"]["source_logical_id"] == plan.logical_id
        assert source_entry["source"]["rendered_equals_stored"] is False
        assert lock.text in system and timing.text in system and str(rule.value) in system
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
        # Accepted updates to either the concept or scene plan must not resurrect
        # the full treatment. Importing existing item IDs would silently do nothing.
        updates = [
            (revised.plan_item(), "2026-09-08T01:00:00Z"),
            (replace(plan, text="Cross by the upstream route."), "2026-09-08T02:00:00Z"),
        ]
        for updated_item, stamp in updates:
            prior = store.plan_revision(BOOK_ID, BRANCH_ID)
            assert prior is not None
            assert prior.item(updated_item.logical_id).text != updated_item.text
            proposal = PlanProposal(
                base_plan_revision_id=prior.plan_revision_id,
                summary=f"Update {updated_item.logical_id}",
                rationale="Exercise treatment containment after a real accepted plan edit.",
                expected_outcome="The new plan text is stored without leaking the treatment.",
                edits=(PlanEdit(PlanEditAction.UPDATE, updated_item.logical_id, updated_item),),
            )
            if locked_concept and updated_item.logical_id == source_item.logical_id:
                with pytest.raises(PlanProposalError, match="locked plan item"):
                    accept_plan_proposal(
                        store, proposal, project_id=PROJECT_ID, created_at=stamp,
                        actor="handoff-test",
                    )
                assert store.plan_revision(BOOK_ID, BRANCH_ID) == prior
                continue
            application = accept_plan_proposal(
                store, proposal, project_id=PROJECT_ID, created_at=stamp,
                actor="handoff-test",
            )
            current = store.plan_revision(BOOK_ID, BRANCH_ID)
            assert current is not None and current == application.after
            assert current.plan_revision_id != prior.plan_revision_id
            assert current.parent_plan_revision_id == prior.plan_revision_id
            assert current.item(updated_item.logical_id).text == updated_item.text
            acceptance = store.decision_for_revision(current.plan_revision_id)
            assert acceptance is not None and acceptance.accepted
            assert acceptance.base_revision_id == prior.plan_revision_id
            assert acceptance.resulting_revision_id == current.plan_revision_id
            assert planner.packet_for(store, revision, beat).render() == before
        packet = planner.packet_for(store, revision, beat)
        assert all(item.authority is lc.StateAuthority.ACCEPTED_CANON
                   for item in packet.sections[context.RULES])
