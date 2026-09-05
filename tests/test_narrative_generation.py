"""Production regressions for concept delivery, short-book planning and safe observation."""

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, exemplars, tells_pass
from litharness.application.handlers import SCENE_DRAFT, TELLS_GATE, make_scene_draft_handler
from litharness.application.outline import BOOK_OUTLINE, make_outline_handler
from litharness.application.planner import make_plan_selector, packet_for, plan_progress
from litharness.domain import context, plans, tells
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.draft import DraftPolicy
from litharness.domain.events import EventType
from litharness.domain.jobs import JobStatus
from litharness.domain.nodes import LockKind
from litharness.domain.policy import Outcome
from litharness.domain.revision import new_book
from tests.conftest import PROJECT_ID
from tests.test_concept import _example
from tests.test_draft import PROSE, registry_with, seeded
from tests.test_outline import DISTINCT, START, StubPlanner, a_book, with_schedule


def _concept_book(store: SqliteStore):  # type: ignore[no-untyped-def]
    intended = concept.Concept.from_payload(_example())
    revision = a_book(store, scenes=6, extra_plan_items=(intended.plan_item(),))
    return revision, intended


def test_six_scene_concept_is_planned_before_its_first_draft(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision, _ = _concept_book(store)
        select = make_plan_selector(project_id=PROJECT_ID, scenes_per_chapter=2)
        job = select(store, "planner", START, 60.0)
        assert job is not None and job.job_kind == BOOK_OUTLINE
        provider = StubPlanner(with_schedule(6))
        make_outline_handler(provider, store, PROJECT_ID)(job, START)
        store.save_job(replace(job, status=JobStatus.SUCCEEDED))

        draft = select(store, "writer", START + 1, 60.0)
        assert draft is not None and draft.job_kind == SCENE_DRAFT
        assert draft.payload["prompt"].endswith(DISTINCT[0])
        for index in range(6):
            item = plans.scene_plan_for(
                store.plan_items(revision.book_id, revision.branch_id), f"scene-{index + 1}"
            )
            assert item is not None and item.text == DISTINCT[index]
        assert "progression_beat" not in draft.payload["selected_by"]
        assert draft.payload["selected_by"]["scene_plan_mode"] == "concept"
        assert "Print that line exactly once" not in draft.payload["system"]
        assert "When this scene changes that state" in draft.payload["system"]
        assert draft.payload["context"]["sections"]["intentions"] == 1
        assert len(provider.requests) == 1
        request = provider.requests[0]
        assert "say in one sentence" not in request.system  # type: ignore[attr-defined]
        assert request.timeout_seconds == 900.0  # type: ignore[attr-defined]
        payload = json.loads(request.prompt)  # type: ignore[attr-defined]
        assert [s["chapter"] for s in payload["scenes"]] == [1, 1, 2, 2, 3, 3]
        assert payload["book_concept"]["first_arc"] == _example()["first_arc"]
        assert not any("four to eight milestones" in rule for rule in payload["rules"])


def test_concept_chapter_ending_keeps_its_plan_and_author_locks(tmp_path: Path) -> None:
    lock = lc.PlanItem(
        logical_id="author-ending",
        kind=lc.PlanKind.CONSTRAINT,
        text="End chapter one after the protagonist makes her decision.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    with SqliteStore.open(tmp_path / "book.db") as store:
        intended = concept.Concept.from_payload(_example())
        revision = a_book(store, scenes=6, extra_plan_items=(intended.plan_item(), lock))
        select = make_plan_selector(project_id=PROJECT_ID, scenes_per_chapter=2)
        outline = select(store, "planner", START, 60.0)
        assert outline is not None
        make_outline_handler(StubPlanner(with_schedule(6)), store, PROJECT_ID)(outline, START)
        store.save_job(replace(outline, status=JobStatus.SUCCEEDED))
        accepted = replace(
            revision,
            revision_id="",
            parent_revision_id=revision.revision_id,
            nodes=tuple(
                replace(node, content=PROSE) if node.logical_id == "scene-1" else node
                for node in revision.nodes
            ),
        )
        store.commit_revision(accepted, created_at="2026-08-16T00:01:00Z")
        ending = select(store, "writer", START + 1, 60.0)
        assert ending is not None and ending.payload["logical_id"] == "scene-2"
        assert ending.payload["prompt"].endswith(DISTINCT[1])
        assert "read or been offered and has not yet answered" not in ending.payload["prompt"]
        assert lock.text in ending.payload["system"]
        assert lock.text in ending.payload["system"].split("AUTHOR-LOCKED STORY DECISIONS")[1]


@pytest.mark.parametrize("status", [JobStatus.RUNNING, JobStatus.PARKED, JobStatus.SUCCEEDED])
def test_missing_scene_plans_never_fall_through_to_generic_drafting(
    tmp_path: Path, status: JobStatus
) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        _concept_book(store)
        select = make_plan_selector(project_id=PROJECT_ID)
        job = select(store, "planner", START, 60.0)
        assert job is not None
        store.save_job(replace(job, status=status))
        assert select(store, "writer", START + 1, 60.0) is None
        assert (
            store._connection.execute(
                "SELECT count(*) FROM jobs WHERE job_kind = ?", (SCENE_DRAFT,)
            ).fetchone()[0]
            == 0
        )


def test_explicit_no_outline_control_still_drafts_a_concept(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        _concept_book(store)
        job = make_plan_selector(project_id=PROJECT_ID, outline=False)(store, "writer", START, 60.0)
        assert job is not None and job.job_kind == SCENE_DRAFT
        assert "Planned story" in job.payload["prompt"]


@pytest.mark.parametrize(
    "status", [JobStatus.RUNNING, JobStatus.PARKED, JobStatus.POISONED, JobStatus.SUCCEEDED]
)
def test_missing_concept_predecessor_holds_successors(tmp_path: Path, status: JobStatus) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision, _ = _concept_book(store)
        select = make_plan_selector(project_id=PROJECT_ID, outline=False)
        first = select(store, "writer", START, 60.0)
        assert first is not None and first.payload["logical_id"] == "scene-1"
        store.save_job(replace(first, status=status))
        assert select(store, "writer", START + 1, 60.0) is None
        progress = plan_progress(store, revision.book_id, revision.branch_id)
        assert progress.drafted == 0 and not progress.complete
        assert progress.blocked_reason is not None
        assert "scene-1" in progress.blocked_reason and status.value in progress.blocked_reason
        assert store.job_counts_by_status() == {status.value: 1}


def test_locked_empty_concept_scene_is_missing_not_complete(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision, _ = _concept_book(store)
        locked = replace(
            revision,
            revision_id="",
            nodes=tuple(
                replace(node, lock=LockKind.PUBLISHED) if node.logical_id == "scene-1" else node
                for node in revision.nodes
            ),
            parent_revision_id=revision.revision_id,
        )
        store.commit_revision(locked, created_at="2026-08-16T00:01:00Z")
        progress = plan_progress(store, revision.book_id, revision.branch_id)
        assert progress.drafted == 0 and not progress.complete
        assert "scene-1 has no prose" in (progress.blocked_reason or "")
        assert (
            make_plan_selector(project_id=PROJECT_ID, outline=False)(store, "writer", START, 60.0)
            is None
        )


def test_missing_predecessor_does_not_stall_another_book(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        first_book, _ = _concept_book(store)
        select = make_plan_selector(project_id=PROJECT_ID, outline=False)
        first = select(store, "writer", START, 60.0)
        assert first is not None
        store.save_job(replace(first, status=JobStatus.PARKED))
        other = new_book("other-book", "other-branch", title="Another book", scenes=6)
        store.commit_revision(other, created_at="2026-08-16T00:01:00Z")
        store.record_plan_items(
            other.book_id,
            other.branch_id,
            store.plan_items(first_book.book_id, first_book.branch_id),
            created_at="2026-08-16T00:01:00Z",
        )
        store.record_state_records(
            other.book_id,
            other.branch_id,
            store.state_records(first_book.book_id, first_book.branch_id),
            created_at="2026-08-16T00:01:00Z",
        )
        next_job = select(store, "writer", START + 1, 60.0)
        assert next_job is not None
        assert next_job.payload["book_id"] == other.book_id
        assert next_job.payload["logical_id"] == "scene-1"


def test_accepting_recovered_predecessor_releases_next_scene(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision, _ = _concept_book(store)
        select = make_plan_selector(project_id=PROJECT_ID, outline=False)
        first = select(store, "writer", START, 60.0)
        assert first is not None
        store.save_job(replace(first, status=JobStatus.PARKED))
        store.save_job(
            replace(first, status=JobStatus.QUEUED, lease_holder=None, lease_expires_at=None)
        )
        recovered = select(store, "writer", START + 1, 60.0)
        assert recovered is not None and recovered.job_id == first.job_id
        accepted = replace(
            revision,
            revision_id="",
            nodes=tuple(
                replace(node, content=PROSE) if node.logical_id == "scene-1" else node
                for node in revision.nodes
            ),
            parent_revision_id=revision.revision_id,
        )
        store.commit_revision(accepted, created_at="2026-08-16T00:01:00Z")
        store.save_job(replace(recovered, status=JobStatus.SUCCEEDED))
        next_job = select(store, "writer", START + 2, 60.0)
        assert next_job is not None and next_job.payload["logical_id"] == "scene-2"


def test_replanning_a_failed_predecessor_reissues_that_scene(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision, _ = _concept_book(store)
        select = make_plan_selector(project_id=PROJECT_ID, outline=False)
        first = select(store, "writer", START, 60.0)
        assert first is not None
        store.save_job(replace(first, status=JobStatus.POISONED))
        store.bump_plan_epoch(
            revision.book_id,
            revision.branch_id,
            at="2026-08-16T00:01:00Z",
            reason="retry failed predecessor",
        )
        next_job = select(store, "writer", START + 1, 60.0)
        assert next_job is not None and next_job.payload["logical_id"] == "scene-1"
        assert next_job.job_id != first.job_id


def test_writer_receives_budgeted_story_intentions_separate_from_canon(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision, intended = _concept_book(store)
        beat = beats_for(revision, arc_template(6))[0]
        packet = packet_for(store, revision, beat)
        (item,) = packet.sections[context.INTENTIONS]
        assert item.source_logical_id == concept.CONCEPT_PLAN_ID
        assert item.authority is lc.StateAuthority.PROPOSED
        assert item.tokens == context.count_tokens(item.text)
        assert intended.first_use in item.text
        assert intended.first_arc.closes in item.text
        assert intended.want in item.text
        assert item not in packet.sections.get(context.FACTS, ())
        assert "not events that have already happened" in packet.render()
        assert intended.first_use not in packet.render_constraints()

        # A tight packet must refuse instead of silently dropping the book's intent.
        with pytest.raises(context.ContextBudgetTooSmall, match="planned story"):
            packet_for(store, revision, beat, token_budget=1600)


def test_tells_observation_preserves_negation_and_reports_excess() -> None:
    original = "Since then, the candidates had been attempting nothing whatsoever."
    result = tells_pass.observe(original, limits=dict.fromkeys(tells.FAMILIES, 0.0))
    assert result.text == original
    assert result.before == result.after
    assert result.left > 0
    assert result.rewritten == result.calls == 0
    assert result.to_jsonable()["mode"] == "observe"


def test_production_shelf_cannot_trigger_sentence_rewrites(tmp_path: Path) -> None:
    shelf_root = tmp_path / "shelf" / "Example"
    shelf_root.mkdir(parents=True)
    (shelf_root / "Chapter1.txt").write_text("Rain filled the courtyard.", encoding="utf-8")
    shelf = exemplars.load_shelf(shelf_root.parent)
    assert shelf is not None
    with SqliteStore.open(tmp_path / "book.db") as store:
        registry, provider = registry_with(PROSE)
        seeded(store)
        job = store.claim_next("writer", now=START, duration=60.0)
        assert job is not None
        make_scene_draft_handler(registry, store, PROJECT_ID, shelf=shelf)(job, START)
        accepted = [
            entry.event
            for entry in store.read_log()
            if entry.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
        ]
        assert len(accepted) == 1
        event = accepted[0]
        assert store.load_revision(event.revision_id or "").node("scene-1").content == PROSE
        assert provider.calls == 1
        assert event.payload["tells"]["mode"] == "observe"
        assert event.payload["tells"]["rewritten"] == event.payload["tells"]["calls"] == 0
        decision = store.decisions_for_job(job.job_id)[-1]
        assert decision.outcome is Outcome.ACCEPT
        gate = next(g for g in decision.gates if g.rule_or_critic_id == TELLS_GATE)
        assert not gate.blocking and not gate.passed

        assert event.payload["raw_draft"]["text"] == PROSE
        assert event.payload["raw_draft"]["sha256"] == sha256(PROSE.encode()).hexdigest()


@pytest.mark.parametrize("accepted", [True, False])
def test_raw_provider_text_survives_stripping_and_refusal(tmp_path: Path, accepted: bool) -> None:
    raw = PROSE.replace("The System said", "The System—said") + "\r\n"
    with SqliteStore.open(tmp_path / "book.db") as store:
        registry, _ = registry_with(raw)
        seeded(store)
        job = store.claim_next("writer", now=START, duration=60.0)
        assert job is not None
        returned = make_scene_draft_handler(
            registry,
            store,
            PROJECT_ID,
            policy=DraftPolicy(min_chars=1 if accepted else len(raw) + 100),
        )(job, START)
        events = [entry.event for entry in store.read_log()] + list(returned)
        event = next(e for e in events if "raw_draft" in e.payload)
        assert event.payload["accepted"] is accepted
        assert event.payload["raw_draft"]["text"] == raw
        assert event.payload["raw_draft"]["sha256"] == sha256(raw.encode()).hexdigest()
        if accepted:
            assert store.load_revision(event.revision_id or "").node("scene-1").content != raw


@pytest.mark.parametrize("chapters", [None, {"scene-1": True}, {"scene-1": 0}])
def test_malformed_chapter_coordinates_are_refused_before_generation(
    tmp_path: Path, chapters: object
) -> None:
    from litharness.application.outline import OutlineOutputError

    with SqliteStore.open(tmp_path / "book.db") as store:
        _concept_book(store)
        job = make_plan_selector(project_id=PROJECT_ID)(store, "planner", START, 60.0)
        assert job is not None
        job = replace(job, payload={**job.payload, "chapter_by_scene": chapters})
        provider = StubPlanner(with_schedule(6))
        with pytest.raises(OutlineOutputError, match="chapter_by_scene"):
            make_outline_handler(provider, store, PROJECT_ID)(job, START)
        assert provider.requests == []
