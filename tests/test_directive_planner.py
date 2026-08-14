"""The exact, non-model lane from explicit direction into immutable plans."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.directive_planner import (
    DIRECTIVE_PLAN,
    constraint_logical_id,
    make_directive_plan_handler,
)
from litharness.application.planner import make_plan_selector
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.revision import build_revision
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision

START = 1_760_000_000.0
STAMP = "2026-08-14T12:00:00Z"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    opened = SqliteStore.open(tmp_path / "directive-planner.db")
    opened.commit_revision(make_revision(), created_at=STAMP)
    opened.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text="A thief must repay an impossible debt.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            )
        ],
        created_at=STAMP,
    )
    return opened


def submit_ingested(store: SqliteStore, directive: Directive) -> None:
    assert store.submit_directive(directive, received_at=STAMP)
    store.mark_directive_ingested(directive.directive_id, ingested_at=STAMP)


def loop(store: SqliteStore) -> Conductor:
    return Conductor(
        store=store,
        holder="planner-test",
        project_id=PROJECT_ID,
        select=make_plan_selector(),
        handlers={
            DIRECTIVE_PLAN: make_directive_plan_handler(
                store, PROJECT_ID, actor="planner-test"
            )
        },
    )


def test_explicit_constraint_is_applied_verbatim_before_scene_work(
    store: SqliteStore,
) -> None:
    body = "No combat in the midpoint; resolve it through negotiation."
    directive = Directive(
        directive_id="dir-no-combat",
        kind=DirectiveKind.CONSTRAINT,
        body=body,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
    )
    submit_ingested(store, directive)
    store.enqueue(
        Job(
            job_id="older-scene-work",
            job_kind="scene_draft",
            payload={"book_id": BOOK_ID, "branch_id": BRANCH_ID},
        )
    )

    result = loop(store).tick(START)

    assert result.outcome is TickOutcome.RAN_JOB
    assert result.job_id != "older-scene-work"
    assert store.load_job("older-scene-work").status is JobStatus.CANCELLED
    assert store.plan_epoch(BOOK_ID, BRANCH_ID) == 1
    applied = store.load_directive(directive.directive_id)
    assert applied.status is DirectiveStatus.APPLIED
    [logical_id] = applied.produced_constraint_ids
    assert logical_id == constraint_logical_id(directive.directive_id)
    item = store.plan_revision(BOOK_ID, BRANCH_ID).item(logical_id)  # type: ignore[union-attr]
    assert item.text == body
    assert item.locked and item.kind is lc.PlanKind.CONSTRAINT


def test_unscoped_constraint_resolves_only_when_exactly_one_branch_exists(
    store: SqliteStore,
) -> None:
    directive = Directive(
        directive_id="dir-single-book",
        kind=DirectiveKind.VETO,
        body="Never resolve the debt with a hidden inheritance.",
    )
    submit_ingested(store, directive)

    assert loop(store).tick(START).outcome is TickOutcome.RAN_JOB

    applied = store.load_directive(directive.directive_id)
    assert (applied.book_id, applied.branch_id) == (None, None)
    assert applied.interpretation == f"The director vetoes: {directive.body}"
    [logical_id] = applied.produced_constraint_ids
    item = store.plan_revision(BOOK_ID, BRANCH_ID).item(logical_id)  # type: ignore[union-attr]
    assert item.text == applied.interpretation
    assert item.locked


def test_controls_remain_queued_outside_both_planning_lanes(
    store: SqliteStore,
) -> None:
    directive = Directive(
        directive_id="dir-control",
        kind=DirectiveKind.CONTROL,
        body="Pause after this chapter.",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
    )
    submit_ingested(store, directive)

    assert loop(store).tick(START).outcome is TickOutcome.NO_WORK
    assert store.load_directive(directive.directive_id).status is DirectiveStatus.RECEIVED
    assert store.job_counts_by_status() == {}


def test_unscoped_direction_is_not_guessed_across_multiple_branches(
    store: SqliteStore,
) -> None:
    other = build_revision("book-other", "branch-other", make_revision().nodes)
    store.commit_revision(other, created_at=STAMP)
    store.record_plan_items(
        other.book_id,
        other.branch_id,
        [
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text="A second book.",
                authority=lc.PlanAuthority.INTENDED,
            )
        ],
        created_at=STAMP,
    )
    directive = Directive(
        directive_id="dir-ambiguous",
        kind=DirectiveKind.CONSTRAINT,
        body="Keep the ending quiet.",
    )
    submit_ingested(store, directive)

    assert loop(store).tick(START).outcome is TickOutcome.NO_WORK
    assert store.load_directive(directive.directive_id).status is DirectiveStatus.RECEIVED
    assert store.job_counts_by_status() == {}


def test_replay_after_plan_commit_is_an_idempotent_success(store: SqliteStore) -> None:
    directive = Directive(
        directive_id="dir-replay",
        kind=DirectiveKind.CONSTRAINT,
        body="Keep the debt visible in every chapter.",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
    )
    submit_ingested(store, directive)
    handler = make_directive_plan_handler(store, PROJECT_ID)
    job = Job(
        job_id="directive-replay",
        job_kind=DIRECTIVE_PLAN,
        payload={
            "directive_id": directive.directive_id,
            "book_id": BOOK_ID,
            "branch_id": BRANCH_ID,
        },
    )

    assert handler(job, START) == ()
    first_head = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert handler(job, START + 1) == ()

    assert store.plan_revision(BOOK_ID, BRANCH_ID) == first_head
    assert len(store.plan_history(BOOK_ID, BRANCH_ID)) == 2
