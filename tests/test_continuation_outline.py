"""Accepted prose anchors only the unwritten suffix through planning and drafting."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, outline, planner
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import make_scene_draft_handler
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.repair import SCENE_SUMMARY
from litharness.domain import genre, serials, staging
from litharness.domain.nodes import LockKind
from litharness.domain.plan_refinement import PlanEdit, PlanEditAction, PlanProposal
from litharness.domain.plans import scene_plan_for
from litharness.domain.policy import Outcome
from litharness.domain.promises import Promise
from litharness.domain.text import content_hash
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_concept import _discovery, _example
from tests.test_outline import START, StubPlanner, _job, a_book, payload_for
from tests.test_scene_brief import outlined_payload

STAMP = "2026-09-09T00:00:00Z"
OPENING = (
    "Mira crossed the fallen bridge and found her companion beneath the trees. His coat "
    "had caught on a broken branch. She helped him free it, then stopped beside the trail. "
    "Beyond the trees the abandoned tower was visible through the mist. He pointed toward "
    "its doorway. Mira took his hand and led him along the path until the ground grew firm."
)
SECOND = (
    "The tower door was swollen shut. Mira set down her pack and pressed against it with "
    "her shoulder, feeling the rotten wood give beneath her coat. Her companion lifted "
    "the latch from the other side of the frame. Together they eased the door aside. "
    "The room beyond smelled of wet stone, and a trail of footprints led to the stairs."
)


def _args(*, no_outline=False, scenes=6):
    return cli.build_parser().parse_args([
        "--project", PROJECT_ID, "--target-words", "1800", "--chapter-scenes", "1",
        "--arc-chapters", str(scenes), *(["--no-outline"] if no_outline else []), "tick",
    ])


def _frozen_job(store):
    job = _job(store)
    return replace(job, payload={
        **job.payload,
        "manuscript_revision_id": store.head(BOOK_ID, BRANCH_ID).revision_id,
        "base_plan_revision_id": store.plan_revision(BOOK_ID, BRANCH_ID).plan_revision_id,
    })


def _source():
    return concept.Concept.from_payload({
        **_example(), "discovery": _discovery(),
        "author_brief": "Write Chapter 1, about 2000 words. Keep both companions alive.",
    }).plan_item()


def test_accepted_chapter_flows_through_suffix_outline_into_chapters_two_and_three(
    tmp_path, monkeypatch,
):
    lock = lc.PlanItem(
        logical_id="third-chapter-lock", kind=lc.PlanKind.CONSTRAINT,
        text="Keep the tower door open in Chapter 3.", authority=lc.PlanAuthority.INTENDED,
        locked=True, scope=lc.ResourceRef(
            project_id=PROJECT_ID, book_id=BOOK_ID, branch_id=BRANCH_ID,
            logical_id="scene-3", kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
    )
    summary = {
        "setting": "The path to the tower.", "characters": "Mira and her companion.",
        "events": "Mira found her companion and they followed the path.",
        "delta": {"who": "Mira", "what_changed": "companionship", "from": "alone",
                  "to": "reunited"},
        "open": "Reach the tower.", "promises_opened": [{
            "subject": "follow_companion", "description": "Reach the tower together.",
            "kind": "plot", "due_hint": None,
            "evidence_quote": "He pointed toward its doorway.",
        }], "promises_paid": [],
    }
    writer = ProviderRegistry(FakeProvider(responses=[OPENING, json.dumps(summary), SECOND]))
    monkeypatch.setattr(cli, "build_default_registry", lambda: writer)
    with SqliteStore.open(tmp_path / "roundtrip.db") as store:
        a_book(store, scenes=6, extra_plan_items=(_source(), lock))
        draft = make_scene_draft_handler(writer, store, PROJECT_ID,
                                        policy=cli._draft_policy(_args()), schedule_summary=True)
        first = Conductor(
            store=store, holder="first", project_id=PROJECT_ID, registry=writer,
            select=cli._conductor(store, _args(no_outline=True)).select,
            handlers={planner.SCENE_DRAFT: draft},
        ).tick(START)
        assert first.outcome is TickOutcome.RAN_JOB
        assert store.latest_decision_for(first.job_id).accepted
        fixed = store.head(BOOK_ID, BRANCH_ID)
        fixed_text = fixed.node("scene-1").content
        base = store.plan_revision(BOOK_ID, BRANCH_ID)
        original = serials.beats_for_serial(fixed, serials.SerialShape(1, 6))
        store.record_state_records(BOOK_ID, BRANCH_ID, [lc.StateRecord(
            record_id=f"want-{index}", kind=lc.StateRecordKind.ASSERTION,
            subject="mira", predicate="wants", value=value,
            authority=lc.StateAuthority.ACCEPTED_CANON,
            story_position=lc.StoryPosition(order_key=original[index-1].story_order_key),
        ) for index, value in ((1, "reach the tower"), (6, "leave the valley"))], created_at=STAMP)
        store.record_promise(BOOK_ID, BRANCH_ID, Promise(
            promise_id="tower-debt", subject="mira", description="Find the tower's owner.",
            opened_at_key=original[0].story_order_key, due_key=original[5].story_order_key,
            opened_by_revision=fixed.revision_id,
        ))
        response = outlined_payload(5)
        response["payoff_windows"] = [
            {"subject": "mira", "first_scene": 5, "last_scene": 5},
            {"subject": "follow_companion", "first_scene": 1, "last_scene": 1},
        ]
        model = StubPlanner(response)
        composed = cli._conductor(store, _args())
        select = composed.select
        planned = Conductor(
            store=store, holder="continuation", project_id=PROJECT_ID, registry=writer,
            select=select, handlers={
                outline.BOOK_OUTLINE: outline.make_outline_handler(model, store, PROJECT_ID),
                planner.SCENE_DRAFT: make_scene_draft_handler(
                    writer, store, PROJECT_ID, policy=cli._draft_policy(_args()),
                ),
                SCENE_SUMMARY: composed.handlers[SCENE_SUMMARY],
            },
        )
        summarized = planned.tick(START + 1)
        assert summarized.outcome is TickOutcome.RAN_JOB
        assert store.load_job(summarized.job_id).job_kind == SCENE_SUMMARY
        learned_debt = next(p for p in store.promises(BOOK_ID, BRANCH_ID)
                            if p.subject == "follow_companion")
        assert learned_debt.opened_at_key == original[0].story_order_key
        assert learned_debt.due_key == original[5].story_order_key
        assert learned_debt.opened_logical_id == "scene-1"
        result = planned.tick(START + 2)
        assert result.outcome is TickOutcome.RAN_JOB
        queued = store.load_job(result.job_id)
        assert queued.payload["manuscript_revision_id"] == fixed.revision_id
        assert queued.payload["base_plan_revision_id"] == base.plan_revision_id
        decision = store.latest_decision_for(result.job_id)
        assert decision.accepted, decision.reason
        body = json.loads(model.requests[0].prompt)
        scope = body["continuation_scope"]
        assert scope["accepted_history"] == [{
            "scene": "scene-1", "content_hash": content_hash(fixed_text),
            "kind": "accepted_prose", "text": fixed_text,
        }]
        assert scope["requested_scenes"][0] == {
            "ordinal": 1, "original_ordinal": 2, "scene": "scene-2",
            "chapter": 2, "story_order_key": original[1].story_order_key,
        }
        assert body["scenes"][1]["chapter"] == 3
        assert "third-chapter-lock" in body["scenes"][1]["author_lock_ids"]
        assert "third-chapter-lock" not in body["scenes"][0].get("author_lock_ids", [])
        assert body["book_concept"]["author_brief"] == (
            concept.Concept.from_text(_source().text).author_brief
        )
        assert body["story_state_at_arc_entry"]["boundary"]["scene"] == "scene-2"
        state = json.dumps(body["story_state_at_arc_entry"])
        assert "reach the tower" in state and "leave the valley" not in state
        assert store.head(BOOK_ID, BRANCH_ID) == fixed
        assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1") is None
        assert store.plan_revision(BOOK_ID, BRANCH_ID).item(lock.logical_id) == lock
        assert all(not scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), f"scene-{i}").locked
                   for i in range(2, 7))
        debt = next(p for p in store.promises(BOOK_ID, BRANCH_ID) if p.subject == "mira")
        assert debt.window_start_key == debt.window_end_key == original[5].story_order_key
        second = planned.tick(START + 3)
        assert second.outcome is TickOutcome.RAN_JOB
        second_job = store.load_job(second.job_id)
        assert second_job.job_kind == planner.SCENE_DRAFT
        assert second_job.payload["logical_id"] == "scene-2"
        assert fixed_text in second_job.payload["prompt"]
        assert response["scenes"][0]["brief"]["changes"][0] in second_job.payload["prompt"]
        assert store.latest_decision_for(second.job_id).accepted
        third = select(store, "third", START + 4, 60)
        assert third.job_kind == planner.SCENE_DRAFT and third.payload["logical_id"] == "scene-3"
        assert SECOND in third.payload["prompt"]
        assert lock.text in third.payload["system"]
        assert response["scenes"][1]["brief"]["changes"][0] in third.payload["prompt"]
        assert store.head(BOOK_ID, BRANCH_ID).node("scene-1").content == fixed_text
        assert len(model.requests) == 1


@pytest.mark.parametrize("fault", [
    "gap", "locked", "locked-plan", "empty", "stale-head", "stale-plan", "legacy",
])
def test_ambiguous_or_changed_continuation_scope_refuses_before_provider(tmp_path, fault):
    with SqliteStore.open(tmp_path / "refuse.db") as store:
        locked_plan = lc.PlanItem(
            logical_id="scene-2-plan", kind=lc.PlanKind.SCENE_PLAN, text="Keep this exact plan.",
            authority=lc.PlanAuthority.INTENDED, locked=True,
        )
        head = a_book(store, scenes=6, extra_plan_items=(
            _source(), *((locked_plan,) if fault == "locked-plan" else ()),
        ))
        head = head.replacing([head.node("scene-1").with_content(OPENING)])
        store.commit_revision(head, created_at=STAMP)
        if fault == "gap":
            head = head.replacing([head.node("scene-3").with_content(SECOND)])
        if fault == "locked":
            head = head.replacing([replace(head.node("scene-2"), lock=LockKind.CONTENT)])
        if fault == "empty":
            head = head.replacing([head.node("scene-1").with_content(" ")])
        store.commit_revision(head, created_at=STAMP)
        job = _job(store) if fault == "legacy" else _frozen_job(store)
        if fault == "stale-head":
            store.commit_revision(head.replacing([head.node("scene-2").with_content(SECOND)]),
                                  created_at=STAMP)
        if fault == "stale-plan":
            base = store.plan_revision(BOOK_ID, BRANCH_ID)
            item = lc.PlanItem(logical_id="new-direction", kind=lc.PlanKind.CONSTRAINT,
                               text="Continue by daylight.", authority=lc.PlanAuthority.INTENDED)
            accept_plan_proposal(store, PlanProposal(
                base_plan_revision_id=base.plan_revision_id,
                summary="New direction", rationale="Author request", expected_outcome="Daylight",
                edits=(PlanEdit(PlanEditAction.CREATE, item.logical_id, item),),
            ), project_id=PROJECT_ID, created_at=STAMP)
        model = StubPlanner(outlined_payload(5))
        outline.make_outline_handler(model, store, PROJECT_ID)(job, START)
        assert model.requests == []
        assert store.latest_decision_for(job.job_id).outcome is Outcome.PARK


def test_history_is_bounded_and_uses_only_summaries_of_current_accepted_bytes(monkeypatch):
    from litharness.domain.revision import new_book

    head = new_book(BOOK_ID, BRANCH_ID, title="History", scenes=12)
    head = head.replacing([head.node(f"scene-{i}").with_content(f"Accepted event {i}.")
                           for i in range(1, 12)])
    summaries = {f"scene-{i}": {content_hash(head.node(f"scene-{i}").content): f"Summary {i}."}
                 for i in range(1, 11)}
    summaries["scene-10"] = {"stale-hash": "A discarded event."}
    history = outline._continuation_history(head, "scene-12", summaries)
    assert len(history["accepted_history"]) == outline.CONTINUATION_HISTORY_SCENES
    assert history["history_omitted_count"] == 3
    assert "discarded" not in json.dumps(history)
    assert history["accepted_history"][-1]["text"] == head.node("scene-11").content
    monkeypatch.setattr(outline, "CONTINUATION_HISTORY_TOKENS", 3)
    summaries["scene-11"] = {content_hash(head.node("scene-11").content): "Found it."}
    fallback = outline._continuation_history(head, "scene-12", summaries)
    assert fallback["accepted_history"][-1]["kind"] == "derived_summary"
    with pytest.raises(outline.OutlineOutputError, match="no current summary"):
        outline._continuation_history(head, "scene-12", {})


@pytest.mark.parametrize("prefix", [1, 5, 6])
def test_prefix_plans_are_preserved_short_suffixes_work_and_frozen_replay_converges(
    tmp_path, prefix,
):
    fixed_plan = lc.PlanItem(
        logical_id="scene-1-plan", kind=lc.PlanKind.SCENE_PLAN, text="Accepted opening direction.",
        authority=lc.PlanAuthority.INTENDED, locked=True,
    )
    with SqliteStore.open(tmp_path / "suffix.db") as store:
        head = a_book(store, scenes=6, extra_plan_items=(_source(), fixed_plan))
        head = head.replacing([head.node(f"scene-{i}").with_content(OPENING)
                               for i in range(1, prefix + 1)])
        store.commit_revision(head, created_at=STAMP)
        job = _frozen_job(store)
        before = store.plan_revision(BOOK_ID, BRANCH_ID)
        model = StubPlanner(outlined_payload(6-prefix))
        handler = outline.make_outline_handler(model, store, PROJECT_ID)
        handler(job, START)
        decision = store.latest_decision_for(job.job_id)
        assert decision.accepted, decision.reason
        after = store.plan_revision(BOOK_ID, BRANCH_ID)
        assert after.item(fixed_plan.logical_id) == fixed_plan
        for i in range(2, prefix + 1):
            assert scene_plan_for(after.items, f"scene-{i}") is None
        if prefix == 6:
            assert after == before and model.requests == []
        else:
            body = json.loads(model.requests[0].prompt)
            assert len(body["scenes"]) == 6-prefix
            assert body["scenes"][0]["ordinal"] == 1
            handler(job, START + 1)
            assert len(model.requests) == 1
            assert store.latest_decision_for(job.job_id) == decision
        assert store.head(BOOK_ID, BRANCH_ID) == head


@pytest.mark.parametrize("advance_at", ["provider", "commit"])
def test_manuscript_advancement_during_generation_cannot_accept_the_stale_plan(
    tmp_path, monkeypatch, advance_at,
):
    with SqliteStore.open(tmp_path / "racing.db") as store:
        head = a_book(store, scenes=6, extra_plan_items=(_source(),))
        head = head.replacing([head.node("scene-1").with_content(OPENING)])
        store.commit_revision(head, created_at=STAMP)
        before = store.plan_revision(BOOK_ID, BRANCH_ID)
        job = _frozen_job(store)
        model = StubPlanner(outlined_payload(5))

        def advance():
            store.commit_revision(
                head.replacing([head.node("scene-2").with_content(SECOND)]), created_at=STAMP,
            )

        if advance_at == "provider":
            complete = model.complete

            def changed_call(request):
                advance()
                return complete(request)

            monkeypatch.setattr(model, "complete", changed_call)
        else:
            commit = store.commit_plan_application

            def changed_commit(application, **kwargs):
                advance()
                return commit(application, **kwargs)

            monkeypatch.setattr(store, "commit_plan_application", changed_commit)
        outline.make_outline_handler(model, store, PROJECT_ID)(job, START)
        assert len(model.requests) == 1
        assert store.plan_revision(BOOK_ID, BRANCH_ID) == before
        assert store.head(BOOK_ID, BRANCH_ID).node("scene-2").content == SECOND
        decision = store.latest_decision_for(job.job_id)
        assert not decision.accepted and "manuscript changed" in decision.reason
        assert decision.total_tokens > 0


def test_original_concept_debt_coordinates_translate_to_local_response_positions(tmp_path):
    payload = {**_example(), "discovery": _discovery()}
    payload["debts"][0]["due_scene"] = 6
    payload["debts"][1]["due_scene"] = 24
    payload["first_arc"]["closes"] += " by scene 24"
    source = concept.Concept.from_payload(payload)
    with SqliteStore.open(tmp_path / "coordinates.db") as store:
        head = a_book(store, scenes=24, extra_plan_items=(source.plan_item(),))
        head = head.replacing([head.node("scene-1").with_content(OPENING)])
        store.commit_revision(head, created_at=STAMP)
        original = serials.beats_for_serial(head, serials.SerialShape(1, 24))
        job = _frozen_job(store)
        job = replace(job, payload={**job.payload, "arc_index": 1,
                                   "scenes_per_chapter": 1, "chapters_per_arc": 24})
        for due in (6, 24):
            store.record_promise(BOOK_ID, BRANCH_ID, Promise(
                promise_id=f"debt-{due}", subject=f"subject-{due}", description="Find its origin.",
                opened_at_key=original[0].story_order_key, due_key=original[due-1].story_order_key,
                opened_by_revision=head.revision_id,
            ))
        response = outlined_payload(23)
        response["payoff_windows"] = [{"subject": f"subject-{due}", "first_scene": due-1,
                                        "last_scene": due-1} for due in (6, 24)]
        response["milestones"] = [{"ordinal": 5, "state": {"level": 2}}]
        model = StubPlanner(response)
        outline.make_outline_handler(model, store, PROJECT_ID)(job, START)
        decision = store.latest_decision_for(job.job_id)
        assert decision.accepted, decision.reason
        body = json.loads(model.requests[0].prompt)
        assert body["book_concept"] == source.for_outline()
        assert [item["due_by_scene"] for item in body["open_promises"]] == [5, 23]
        mapping = body["continuation_scope"]["requested_scenes"]
        assert [(mapping[i-2]["ordinal"], mapping[i-2]["original_ordinal"])
                for i in (6, 24)] == [(5, 6), (23, 24)]
        debts = {row.subject: row for row in store.promises(BOOK_ID, BRANCH_ID)}
        assert debts["subject-6"].window_end_key == original[5].story_order_key
        assert debts["subject-24"].window_end_key == original[23].story_order_key
        milestones = [r for r in store.state_records(BOOK_ID, BRANCH_ID)
                      if r.authority is lc.StateAuthority.PROPOSED]
        assert len(milestones) == 1
        assert milestones[0].story_position.order_key == original[5].story_order_key


def test_legacy_continuation_keeps_original_cadence_and_opening_bounds(tmp_path):
    with SqliteStore.open(tmp_path / "legacy.db") as store:
        head = a_book(store, scenes=12, sheet=False)
        head = head.replacing([head.node(f"scene-{i}").with_content(OPENING)
                               for i in range(1, 5)])
        store.commit_revision(head, created_at=STAMP)
        response = payload_for(8)
        model = StubPlanner(response)
        job = _frozen_job(store)
        outline.make_outline_handler(model, store, PROJECT_ID)(job, START)
        decision = store.latest_decision_for(job.job_id)
        assert decision.accepted, decision.reason
        for local, original in enumerate(range(5, 13)):
            expected = staging.with_bound(genre.with_beat(
                response["scenes"][local]["statement"], original, 12,
            ), original)
            stored = scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), f"scene-{original}")
            assert stored.text == expected
