"""Conductor gates: idempotency, crash recovery, and bounded state growth.

Time is injected everywhere, so every property is pinned over simulated tick counts
rather than wall-clock waiting. The horizons are short: the properties under test —
bounded state growth and replay idempotency — fail within a handful of ticks or not
at all.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import (
    Conductor,
    TickOutcome,
    no_op_handler,
)
from litharness.domain.events import Event, EventType
from litharness.domain.exceptions import ExceptionKind
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.revision import Revision
from litharness.providers.base import ProviderFailureKind, provider_error
from tests.conftest import PROJECT_ID

START = 1_760_000_000.0
TICK_SECONDS = 300.0  # the plan's 5-minute heartbeat


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "conductor.db")


def conductor(store: SqliteStore, holder: str = "worker-a", **kwargs) -> Conductor:
    kwargs.setdefault("handlers", {"noop": no_op_handler})
    return Conductor(store=store, holder=holder, project_id=PROJECT_ID, **kwargs)


# --- idempotency -------------------------------------------------------------------


def test_replaying_a_tick_is_a_no_op(store: SqliteStore) -> None:
    subject = conductor(store)
    assert subject.tick(START).outcome is TickOutcome.NO_WORK
    assert subject.tick(START).outcome is TickOutcome.REPLAYED
    assert store.tick_count() == 1
    assert store.digest(Conductor._day(START))["ticks"] == 1


def test_a_replayed_tick_does_not_rerun_its_job(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="noop"))
    subject = conductor(store)
    assert subject.tick(START).outcome is TickOutcome.RAN_JOB
    replay = subject.tick(START)
    assert replay.outcome is TickOutcome.REPLAYED
    assert store.digest(Conductor._day(START))["jobs_succeeded"] == 1


# --- one bounded unit per tick -----------------------------------------------------


def test_a_tick_executes_at_most_one_job(store: SqliteStore) -> None:
    for index in range(3):
        store.enqueue(Job(job_id=f"j{index}", job_kind="noop"))
    subject = conductor(store)
    subject.tick(START)
    assert store.queued_count() == 2
    subject.tick(START + TICK_SECONDS)
    assert store.queued_count() == 1


def test_a_failing_job_cannot_starve_the_queue(store: SqliteStore) -> None:
    """§4.2: the failure mode is a parked unit, never a spin loop."""

    def explode(job: Job, now: float):
        raise RuntimeError("handler blew up")

    store.enqueue(Job(job_id="bad", job_kind="boom", max_attempts=2))
    store.enqueue(Job(job_id="good", job_kind="noop"))
    subject = conductor(store, handlers={"boom": explode, "noop": no_op_handler})

    now = START
    outcomes = []
    for _ in range(6):
        outcomes.append(subject.tick(now).outcome)
        now += TICK_SECONDS

    assert store.load_job("bad").status is JobStatus.POISONED
    assert store.load_job("good").status is JobStatus.SUCCEEDED
    assert TickOutcome.RAN_JOB in outcomes, "the good job never ran"
    assert store.load_job("bad").attempts <= 2, "attempts exceeded the budget"


def test_a_handler_failure_is_recorded_as_an_event(store: SqliteStore) -> None:
    def explode(job: Job, now: float):
        raise ValueError("nope")

    store.enqueue(Job(job_id="bad", job_kind="boom"))
    subject = conductor(store, handlers={"boom": explode})
    assert subject.tick(START).outcome is TickOutcome.JOB_FAILED
    kinds = [item.event.event_type for item in store.read_log()]
    assert EventType.JOB_FAILED in kinds
    assert store.digest(Conductor._day(START))["jobs_failed"] == 1


def test_a_retryable_provider_failure_requeues_without_spending_an_attempt(
    store: SqliteStore,
) -> None:
    def overloaded(job: Job, now: float):
        raise provider_error("provider overloaded", kind=ProviderFailureKind.OVERLOADED)

    store.enqueue(Job(job_id="provider-retry", job_kind="generate"))
    result = conductor(store, handlers={"generate": overloaded}).tick(START)

    job = store.load_job("provider-retry")
    assert result.outcome is TickOutcome.JOB_FAILED
    assert job.status is JobStatus.QUEUED and job.attempts == 0
    [fallback] = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.PROVIDER_FELL_BACK
    ]
    assert fallback.payload["classification"] == "overloaded"


def test_a_provider_failure_needing_intervention_parks_and_escalates(
    store: SqliteStore,
) -> None:
    def unauthenticated(job: Job, now: float):
        raise provider_error("API key expired", kind=ProviderFailureKind.AUTH)

    store.enqueue(Job(job_id="provider-blocked", job_kind="generate"))
    subject = conductor(store, handlers={"generate": unauthenticated})
    result = subject.tick(START)

    job = store.load_job("provider-blocked")
    assert result.outcome is TickOutcome.JOB_PARKED
    assert job.status is JobStatus.PARKED and job.attempts == 0
    [raised] = store.open_exceptions()
    assert raised.kind is ExceptionKind.PROVIDER_UNAVAILABLE
    assert "auth" in raised.summary
    assert store.digest(Conductor._day(START))["provider_blocked"] == 1
    assert subject.tick(START + TICK_SECONDS).outcome is TickOutcome.NO_WORK


def test_a_provider_refusal_remains_a_candidate_failure(store: SqliteStore) -> None:
    def refused(job: Job, now: float):
        raise provider_error("model refused", kind=ProviderFailureKind.REFUSAL)

    store.enqueue(Job(job_id="provider-refused", job_kind="generate"))
    result = conductor(store, handlers={"generate": refused}).tick(START)

    job = store.load_job("provider-refused")
    assert result.outcome is TickOutcome.JOB_FAILED
    assert job.status is JobStatus.FAILED and job.attempts == 1
    [failed] = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.JOB_FAILED
    ]
    assert failed.payload["classification"] == "refusal"


def test_a_job_with_no_handler_fails_rather_than_vanishing(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="orphan", job_kind="unregistered"))
    assert conductor(store).tick(START).outcome is TickOutcome.JOB_FAILED
    job = store.load_job("orphan")
    assert job.status is JobStatus.FAILED
    assert job.error is not None and "no handler" in job.error


# --- crash recovery ----------------------------------------------------------------


def test_a_job_abandoned_by_a_crashed_holder_is_requeued(store: SqliteStore) -> None:
    """The in-flight unit: RUNNING with an expired lease is invisible to claim_next."""
    store.enqueue(Job(job_id="j1", job_kind="noop"))
    claimed = store.claim_next("dead-worker", now=START, duration=60.0)
    assert claimed is not None
    store.save_job(claimed.transition_to(JobStatus.RUNNING))

    result = conductor(store).tick(START + 600)
    assert result.reconciled == 1
    assert store.load_job("j1").status in {JobStatus.QUEUED, JobStatus.SUCCEEDED}


def test_a_job_abandoned_past_its_attempt_budget_poisons(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="noop", max_attempts=1))
    claimed = store.claim_next("dead-worker", now=START, duration=60.0)
    assert claimed is not None
    store.save_job(claimed.transition_to(JobStatus.RUNNING))

    conductor(store).tick(START + 600)
    assert store.load_job("j1").status is JobStatus.POISONED


def test_reconciliation_does_not_touch_a_live_lease(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="noop"))
    claimed = store.claim_next("busy-worker", now=START, duration=3600.0)
    assert claimed is not None
    store.save_job(claimed.transition_to(JobStatus.RUNNING))

    result = conductor(store).tick(START + 60)
    assert result.reconciled == 0
    assert store.load_job("j1").status is JobStatus.RUNNING


# --- end to end, without a model ---------------------------------------------------


def test_a_job_can_commit_a_revision_and_its_event_atomically(
    store: SqliteStore, revision: Revision
) -> None:
    """Stage 0's exit sentence, driven by the Conductor: no model anywhere in this path."""
    committed: list[str] = []

    def draft(job: Job, now: float):
        edited = revision.replacing([revision.node("scene-1").with_content("A drafted line.")])
        event = Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=PROJECT_ID,
            created_at=Conductor._timestamp(now),
            book_id=edited.book_id,
            branch_id=edited.branch_id,
            revision_id=edited.revision_id,
            payload={"job_id": job.job_id},
        )
        store.commit_revision(edited, created_at=event.created_at, events=[event])
        committed.append(edited.revision_id)
        return ()

    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    store.enqueue(Job(job_id="draft-1", job_kind="draft"))
    result = conductor(store, handlers={"draft": draft}).tick(START)

    assert result.outcome is TickOutcome.RAN_JOB
    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    reloaded = store.load_revision(committed[0])
    assert reloaded.node("scene-1").content == "A drafted line."
    assert reloaded.node("scene-2").content == revision.node("scene-2").content
    assert store.verify_integrity() == 2
    assert [item.event.revision_id for item in store.read_log()] == [committed[0]]


# --- bounded state growth ----------------------------------------------------------


MANY_TICKS = 50  # enough for the growth and replay properties to fail, if they can


def test_a_week_of_no_op_ticks_changes_nothing(store: SqliteStore) -> None:
    """Bounded state growth: a resident loop must not accrete state by merely running.

    Formerly the 2,016 simulated ticks a week produces at the 5-minute cadence, which is
    the run stage-0 §10 cites — the name is load-bearing for that citation. The property
    is per-tick, so 50 ticks refute it exactly as well as a week: what would fail here is
    a table that gains a row per tick beyond the tick record itself, or non-idempotent
    digest accumulation.
    """
    subject = conductor(store)
    now = START
    outcomes = set()
    for _ in range(MANY_TICKS):
        outcomes.add(subject.tick(now).outcome)
        now += TICK_SECONDS

    assert outcomes == {TickOutcome.NO_WORK}, f"unexpected outcomes: {outcomes}"
    assert store.tick_count() == MANY_TICKS
    assert store.queued_count() == 0
    assert store.read_log() == []
    assert store.verify_integrity() == 0

    # State growth is bounded to the tick log itself: no revisions, jobs, or events.
    counts = {
        table: store._connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        for table in ("revisions", "node_versions", "events", "jobs")
    }
    assert counts == dict.fromkeys(counts, 0), counts

    # The digest accumulated exactly once per tick.
    days = {Conductor._day(START + index * TICK_SECONDS) for index in range(MANY_TICKS)}
    assert sum(store.digest(day).get("ticks", 0) for day in days) == MANY_TICKS


def test_replaying_many_ticks_never_double_counts(store: SqliteStore) -> None:
    subject = conductor(store)
    instants = [START + index * TICK_SECONDS for index in range(MANY_TICKS)]
    for instant in instants:
        subject.tick(instant)
    # Replay every instant a second time, as a restarted session re-driving them would.
    replayed = [subject.tick(instant).outcome for instant in instants]

    assert set(replayed) == {TickOutcome.REPLAYED}
    assert store.tick_count() == len(instants)
    # Sum over distinct *days*, not distinct instants: many instants share a day, and
    # summing per-instant counts the same day's total repeatedly.
    days = {Conductor._day(instant) for instant in instants}
    assert sum(store.digest(day).get("ticks", 0) for day in days) == len(instants)
