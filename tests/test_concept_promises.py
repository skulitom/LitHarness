"""Proposed outcomes reach planning; accepted prose can independently open commitments."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, outline, planner
from litharness.application.handlers import make_scene_draft_handler
from litharness.application.repair import summary_job_for
from litharness.application.summarize import make_summary_handler
from litharness.domain import context
from litharness.domain.jobs import JobStatus
from litharness.domain.promises import promise_id_for
from litharness.domain.serials import SerialShape, beats_for_serial
from litharness.domain.text import content_hash
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_concept import _discovery, _example
from tests.test_continuation_outline import OPENING, SECOND
from tests.test_outline import SEED, START, StubPlanner
from tests.test_scene_brief import outlined_payload
from tests.test_summarize import StubGenerator

STAMP = "2026-09-09T00:00:00Z"
SHAPE = SerialShape(1, 6)
SUBJECT = "the_tower_door"
OPENING_QUOTE = "The tower door was barred from the inside."
PAYMENT_QUOTE = "The keeper admitted that she had barred the tower door."
FIRST = OPENING + " " + OPENING_QUOTE
NEXT = SECOND + " " + PAYMENT_QUOTE
OBSERVED = "Find whoever barred the tower door."


def _create(tmp_path, *, with_concept=True, explicit=False, first_person=False):
    intended = concept.Concept.from_payload({
        **_example(), "discovery": _discovery(),
        "author_brief": "Write a magical adventure about finding a missing companion.",
        "debts": [{
            "subject": "the tower door",
            "owed": "The keeper barred the door to protect the tower's hidden garden.",
            "due_scene": 5,
        }, _example()["debts"][1]],
    })
    concept_path = tmp_path / "concept.json"
    concept_path.write_text(intended.to_text(), encoding="utf-8")
    explicit_path = tmp_path / "promises.json"
    debt = intended.debts[0]
    explicit_path.write_text(json.dumps([{
        "subject": debt.subject, "description": debt.owed, "due_scene": debt.due_scene,
    }]), encoding="utf-8")
    database = tmp_path / "book.db"
    common = ["--database", str(database), "--project", PROJECT_ID,
              "--chapter-scenes", "1", "--arc-chapters", "6"]
    assert cli.main([*common, "init"]) == cli.EXIT_OK
    assert cli.main([
        *common, "new", "The Tower", "--premise", "A traveler searches for her companion.",
        "--scenes", "6", "--book", BOOK_ID, "--branch", BRANCH_ID,
        *(["--concept", str(concept_path)] if with_concept else []),
        *(["--promises", str(explicit_path)] if explicit else []),
        *(["--person", "first"] if first_person else []),
    ]) == cli.EXIT_OK
    with SqliteStore.open(database) as store:
        store.record_state_records(BOOK_ID, BRANCH_ID, [lc.StateRecord(
            record_id="starting-sheet", kind=lc.StateRecordKind.ASSERTION,
            subject="mira", predicate="status_snapshot", value=dict(SEED),
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )], created_at=STAMP)
    return database, intended


def _select(*, outlined):
    return planner.make_plan_selector(
        project_id=PROJECT_ID, outline=outlined, scenes_per_chapter=1,
        chapters_per_arc=6, open_ended=True,
    )


def _summarize(store, registry, head, scene, text, now):
    job = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=head.revision_id,
        logical_id=scene, content_hash=content_hash(text),
    )
    handler = make_summary_handler(registry, store, PROJECT_ID, serial_shape=SHAPE)
    handler(job, now)
    return handler, job


def test_new_concept_debts_reach_initial_outline_without_becoming_reader_owed_threads(
    tmp_path, capsys,
):
    database, intended = _create(tmp_path, first_person=True)
    report = capsys.readouterr().out
    assert "2 proposed debt(s) retained for planning" in report
    assert "explicit promise(s) opened" not in report
    with SqliteStore.open(database) as store:
        original = store.head(BOOK_ID, BRANCH_ID)
        items = store.plan_items(BOOK_ID, BRANCH_ID)
        assert concept.concept_of(items) == intended
        assert store.promises(BOOK_ID, BRANCH_ID) == []
        first = beats_for_serial(original, SHAPE)[0]
        packet = planner.packet_for(store, original, first)
        assert not packet.sections.get(context.THREADS)
        assert intended.author_brief in packet.render()
        assert cli.FIRST_PERSON_CONSTRAINT in packet.render_constraints()
        assert intended.debts[0].owed not in packet.render()

        select = _select(outlined=True)
        job = select(store, "planner", START, 60)
        assert job is not None and job.job_kind == outline.BOOK_OUTLINE
        source = StubPlanner(outlined_payload(6))
        outline.make_outline_handler(source, store, PROJECT_ID)(job, START)
        assert store.latest_decision_for(job.job_id).accepted
        store.save_job(replace(job, status=JobStatus.SUCCEEDED))
        request = json.loads(source.requests[0].prompt)
        assert request["book_concept"]["debts"] == intended.for_outline()["debts"]
        assert request["open_promises"] is None
        assert cli.FIRST_PERSON_CONSTRAINT in [item["text"] for item in request["author_locks"]]
        writer = select(store, "writer", START + 1, 60)
        assert writer is not None and writer.job_kind == planner.SCENE_DRAFT
        assert cli.FIRST_PERSON_CONSTRAINT in writer.payload["system"]
        assert writer.payload["context"]["sections"].get("threads", 0) == 0
        assert concept.concept_of(store.plan_items(BOOK_ID, BRANCH_ID)) == intended
        assert store.head(BOOK_ID, BRANCH_ID) == original


@pytest.mark.parametrize("with_concept", [False, True])
def test_explicit_promises_survive_even_when_their_text_matches_a_concept_debt(
    tmp_path, capsys, with_concept,
):
    database, intended = _create(tmp_path, with_concept=with_concept, explicit=True)
    assert "1 explicit promise(s) opened" in capsys.readouterr().out
    with SqliteStore.open(database) as store:
        head = store.head(BOOK_ID, BRANCH_ID)
        beats = beats_for_serial(head, SHAPE)
        (promise,) = store.promises(BOOK_ID, BRANCH_ID)
        assert promise.subject == SUBJECT and promise.description == intended.debts[0].owed
        assert promise.opened_by_revision == head.revision_id
        assert promise.opened_at_key == beats[0].story_order_key
        assert promise.due_key == beats[4].story_order_key
        assert promise.model == "" and promise.opened_logical_id is None
        packet = planner.packet_for(store, head, beats[0])
        (thread,) = packet.sections[context.THREADS]
        assert thread.source_logical_id == promise.promise_id
        assert promise.description in thread.text
        assert store.promises(BOOK_ID, BRANCH_ID) == [promise]


@pytest.mark.parametrize("explicit", [False, True])
def test_accepted_same_subject_observation_reaches_outline_and_writer_then_is_paid(
    tmp_path, explicit,
):
    database, intended = _create(tmp_path, explicit=explicit)
    drafts = ProviderRegistry(FakeProvider(responses=[FIRST, NEXT]))
    observation = StubGenerator({
        "setting": "Outside the tower.", "characters": "Mira and her companion.",
        "events": "The travelers found the door barred.", "open": OBSERVED,
        "promises_opened": [{"subject": "the tower door", "description": OBSERVED,
                              "due_hint": 5, "evidence_quote": OPENING_QUOTE}],
        "promises_paid": [],
    })
    with SqliteStore.open(database) as store:
        created = store.head(BOOK_ID, BRANCH_ID)
        before = store.promises(BOOK_ID, BRANCH_ID)
        assert len(before) == int(explicit)
        draft = make_scene_draft_handler(drafts, store, PROJECT_ID)
        first = _select(outlined=False)(store, "writer", START, 60)
        assert first is not None and first.job_kind == planner.SCENE_DRAFT
        draft(first, START)
        assert store.latest_decision_for(first.job_id).accepted
        store.save_job(replace(first, status=JobStatus.SUCCEEDED))
        accepted = store.head(BOOK_ID, BRANCH_ID)
        assert accepted.node("scene-1").content == FIRST
        summarize, summary_job = _summarize(
            store, observation, accepted, "scene-1", FIRST, START + 1,
        )
        (opened,) = store.promises(BOOK_ID, BRANCH_ID)
        assert opened.promise_id == promise_id_for(BOOK_ID, SUBJECT)
        if explicit:
            assert opened == before[0]
            assert opened.opened_by_revision == created.revision_id
        else:
            assert opened.description == OBSERVED
            assert opened.model == "stub-v1"
            assert opened.opened_by_revision == accepted.revision_id
            assert opened.opened_logical_id == "scene-1"
            assert opened.opened_content_hash == content_hash(FIRST)
            assert FIRST[opened.opened_start:opened.opened_end] == OPENING_QUOTE
        summarize(summary_job, START + 2)
        assert store.promises(BOOK_ID, BRANCH_ID) == [opened]

        select = _select(outlined=True)
        outline_job = select(store, "planner", START + 3, 60)
        assert outline_job is not None and outline_job.job_kind == outline.BOOK_OUTLINE
        response = outlined_payload(5)
        response["payoff_windows"] = [{"subject": SUBJECT, "first_scene": 4, "last_scene": 4}]
        source = StubPlanner(response)
        outline.make_outline_handler(source, store, PROJECT_ID)(outline_job, START + 3)
        assert store.latest_decision_for(outline_job.job_id).accepted
        store.save_job(replace(outline_job, status=JobStatus.SUCCEEDED))
        request = json.loads(source.requests[0].prompt)
        assert request["book_concept"]["debts"] == intended.for_outline()["debts"]
        assert [(row["subject"], row["owed"]) for row in request["open_promises"]] == [
            (SUBJECT, opened.description),
        ]
        second = select(store, "writer", START + 4, 60)
        assert second is not None and second.payload["logical_id"] == "scene-2"
        assert opened.description in second.payload["prompt"]
        second_packet = planner.packet_for(store, accepted, beats_for_serial(accepted, SHAPE)[1])
        assert opened.promise_id in {item.source_logical_id
                                     for item in second_packet.sections[context.THREADS]}
        draft(second, START + 4)
        assert store.latest_decision_for(second.job_id).accepted
        store.save_job(replace(second, status=JobStatus.SUCCEEDED))
        progressed = store.head(BOOK_ID, BRANCH_ID)
        assert progressed.node("scene-1").content == FIRST
        assert progressed.node("scene-2").content == NEXT

        payment = StubGenerator({
            "setting": "Inside the tower.", "characters": "Mira and the keeper.",
            "events": "The keeper explained the barred door.", "open": "", "promises_opened": [],
            "promises_paid": [{"subject": SUBJECT, "evidence_quote": PAYMENT_QUOTE}],
        })
        settle, payment_job = _summarize(store, payment, progressed, "scene-2", NEXT, START + 5)
        (paid,) = store.promises(BOOK_ID, BRANCH_ID)
        assert paid.status == "paid" and paid.promise_id == opened.promise_id
        assert paid.description == opened.description and paid.model == opened.model
        assert paid.opened_by_revision == opened.opened_by_revision
        assert paid.opened_content_hash == opened.opened_content_hash
        assert paid.paid_by_revision == progressed.revision_id
        assert paid.paid_logical_id == "scene-2" and paid.paid_content_hash == content_hash(NEXT)
        assert NEXT[paid.paid_start:paid.paid_end] == PAYMENT_QUOTE
        summarize(summary_job, START + 6)
        settle(payment_job, START + 7)
        assert store.promises(BOOK_ID, BRANCH_ID) == [paid]
        third = select(store, "writer", START + 8, 60)
        assert third is not None and third.payload["logical_id"] == "scene-3"
        third_packet = planner.packet_for(
            store, progressed, beats_for_serial(progressed, SHAPE)[2],
        )
        assert paid.promise_id not in {item.source_logical_id
                                      for item in third_packet.sections[context.THREADS]}
        assert concept.concept_of(store.plan_items(BOOK_ID, BRANCH_ID)) == intended
