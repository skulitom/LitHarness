"""Conductor gates: leadership, idempotency, crash recovery, and the endurance property.

Stage 0's exit clause is "the Conductor ticks idempotently for a week unattended (no-op
workload)". A week of wall-clock waiting is not a test, so the endurance property is
measured over the *tick count* a week produces at the plan's 5-minute cadence, with time
injected. That is a real measurement of the thing that would break — unbounded state
growth and non-idempotent accumulation — and it is not a measurement of process uptime.
Said plainly here so the distinction does not get lost downstream.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import (
    Conductor,
    TickOutcome,
    no_op_handler,
)
from litharness.domain.events import MAX_DELIVERY_ATTEMPTS, Event, EventType, OutboxEntry
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.revision import Revision
from tests.conftest import PROJECT_ID

START = 1_760_000_000.0
TICK_SECONDS = 300.0  # the plan's 5-minute heartbeat


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "conductor.db")


def conductor(store: SqliteStore, holder: str = "worker-a", **kwargs) -> Conductor:
    kwargs.setdefault("handlers", {"noop": no_op_handler})
    return Conductor(store=store, holder=holder, project_id=PROJECT_ID, **kwargs)


class CollectingDispatcher:
    """A sink that records what it was handed and can be told to refuse."""

    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.delivered: list[OutboxEntry] = []

    def __call__(self, entry: OutboxEntry) -> bool:
        if not self.accept:
            return False
        self.delivered.append(entry)
        return True


# --- leadership --------------------------------------------------------------------


def test_only_one_instance_is_the_conductor(store: SqliteStore) -> None:
    first = conductor(store, "worker-a")
    second = conductor(store, "worker-b")
    assert first.tick(START).outcome is TickOutcome.NO_WORK
    assert second.tick(START + 1).outcome is TickOutcome.NOT_LEADER


def test_a_tick_that_loses_the_lease_does_nothing_at_all(store: SqliteStore) -> None:
    """Not merely "no job" — a non-leader must not reconcile or dispatch either."""
    store.enqueue(Job(job_id="j1", job_kind="noop"))
    conductor(store, "worker-a").tick(START)
    ticks_before = store.tick_count()

    loser = conductor(store, "worker-b")
    result = loser.tick(START + 1)
    assert result.outcome is TickOutcome.NOT_LEADER
    assert result.reconciled == 0 and result.dispatched == 0
    assert store.tick_count() == ticks_before, "a non-leader recorded a tick"


def test_leadership_transfers_once_the_lease_expires(store: SqliteStore) -> None:
    first = conductor(store, "worker-a", lease_duration=60.0)
    assert first.tick(START).outcome is TickOutcome.NO_WORK
    second = conductor(store, "worker-b", lease_duration=60.0)
    assert second.tick(START + 30).outcome is TickOutcome.NOT_LEADER
    assert second.tick(START + 120).outcome is TickOutcome.NO_WORK
    assert store.instance_lease_holder("conductor", START + 121) == "worker-b"


def test_pause_stops_work_but_still_records_the_tick(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="noop"))
    paused = conductor(store, paused=True)
    assert paused.tick(START).outcome is TickOutcome.PAUSED
    assert store.load_job("j1").status is JobStatus.QUEUED
    assert store.tick_count() == 1


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


# --- outbox dispatch ---------------------------------------------------------------


def test_the_tick_drains_the_outbox_send_then_mark(store: SqliteStore, revision: Revision) -> None:
    store.commit_revision(
        revision,
        created_at="2026-08-12T00:00:00Z",
        events=[
            Event(
                event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
                project_id=PROJECT_ID,
                created_at="2026-08-12T00:00:00Z",
                revision_id=revision.revision_id,
            )
        ],
    )
    sink = CollectingDispatcher()
    result = conductor(store, dispatch=sink).tick(START)
    assert result.dispatched == 1
    assert len(sink.delivered) == 1
    assert store.pending_outbox() == []


def test_a_refused_delivery_stays_pending_and_counts_the_attempt(
    store: SqliteStore, revision: Revision
) -> None:
    """Undelivered must never be marked sent — that would be silent loss."""
    store.append_events(
        [
            Event(
                event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
                project_id=PROJECT_ID,
                created_at="2026-08-12T00:00:00Z",
                revision_id=revision.revision_id,
            )
        ]
    )
    refusing = CollectingDispatcher(accept=False)
    result = conductor(store, dispatch=refusing).tick(START)
    assert result.dispatched == 0
    pending = store.pending_outbox()
    assert len(pending) == 1 and pending[0].delivery_attempts == 1


def test_the_default_dispatcher_leaves_events_pending(
    store: SqliteStore, revision: Revision
) -> None:
    """No sink configured means no delivery claimed. The honest default."""
    store.append_events(
        [
            Event(
                event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
                project_id=PROJECT_ID,
                created_at="2026-08-12T00:00:00Z",
                revision_id=revision.revision_id,
            )
        ]
    )
    conductor(store).tick(START)
    assert len(store.pending_outbox()) == 1


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


# --- endurance ---------------------------------------------------------------------


A_WEEK_OF_TICKS = 7 * 24 * 12  # 2016 ticks at the plan's 5-minute cadence


def test_a_week_of_no_op_ticks_changes_nothing(store: SqliteStore) -> None:
    """Stage 0's endurance criterion, measured over tick count rather than wall clock.

    What would actually fail here: unbounded state growth (a table that gains a row per
    tick beyond the tick record itself), non-idempotent digest accumulation, or a lease
    that stops renewing and locks the instance out of its own role.
    """
    subject = conductor(store)
    now = START
    outcomes = set()
    for _ in range(A_WEEK_OF_TICKS):
        outcomes.add(subject.tick(now).outcome)
        now += TICK_SECONDS

    assert outcomes == {TickOutcome.NO_WORK}, f"unexpected outcomes over a week: {outcomes}"
    assert store.tick_count() == A_WEEK_OF_TICKS
    assert store.queued_count() == 0
    assert store.read_log() == []
    assert store.pending_outbox() == []
    assert store.verify_integrity() == 0

    # State growth is bounded to the tick log itself: no revisions, jobs, or events.
    counts = {
        table: store._connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        for table in ("revisions", "node_versions", "events", "outbox", "jobs")
    }
    assert counts == dict.fromkeys(counts, 0), counts

    # The digest accumulated exactly once per tick, spread across the seven days.
    days = {
        Conductor._day(START + index * TICK_SECONDS) for index in range(A_WEEK_OF_TICKS)
    }
    assert sum(store.digest(day).get("ticks", 0) for day in days) == A_WEEK_OF_TICKS


def test_replaying_ticks_across_a_week_never_double_counts(store: SqliteStore) -> None:
    subject = conductor(store)
    instants = [START + index * TICK_SECONDS for index in range(200)]
    for instant in instants:
        subject.tick(instant)
    # Replay every instant a second time, as a retried cron invocation would.
    replayed = [subject.tick(instant).outcome for instant in instants]

    assert set(replayed) == {TickOutcome.REPLAYED}
    assert store.tick_count() == len(instants)
    # Sum over distinct *days*, not distinct instants: many instants share a day, and
    # summing per-instant counts the same day's total repeatedly.
    days = {Conductor._day(instant) for instant in instants}
    assert sum(store.digest(day).get("ticks", 0) for day in days) == len(instants)


# --- the outbox does not spin (§19 Autonomy) ----------------------------------------


def test_a_week_of_ticks_with_a_refusing_sink_stays_bounded(
    store: SqliteStore, revision: Revision
) -> None:
    """The failure `test_a_week_of_no_op_ticks_changes_nothing` structurally cannot see.

    That test asserts the outbox is empty, so the workload that exposes this is excluded
    from it by construction. With a permanently refusing sink the old loop re-attempted the
    first 50 pending entries every tick forever: over this same horizon the head entries
    reached 2016 delivery attempts while entries 51 and beyond reached zero — an unbounded
    spin and permanent head-of-line starvation at once.
    """
    events = [
        Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=PROJECT_ID,
            created_at="2026-08-12T00:00:00Z",
            revision_id=revision.revision_id,
            payload={"n": index},
        )
        for index in range(60)
    ]
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z", events=events)
    loop = conductor(store)

    for index in range(A_WEEK_OF_TICKS):
        loop.tick(START + index * TICK_SECONDS)

    states = store.outbox_counts_by_state()
    assert states.get("pending", 0) == 0, "an entry is still being retried after a week"
    assert states["failed"] == 60

    attempts = [
        row["delivery_attempts"]
        for row in store._connection.execute("SELECT delivery_attempts FROM outbox")
    ]
    # Bounded, and bounded *equally* — no entry starved behind the head.
    assert max(attempts) == MAX_DELIVERY_ATTEMPTS
    assert min(attempts) == MAX_DELIVERY_ATTEMPTS


def test_a_transient_outage_still_delivers_once_the_sink_returns(
    store: SqliteStore, revision: Revision
) -> None:
    """Backoff must not become a drop. The terminal state is a floor for a sink that is
    never coming back, not a punishment for one that blinked."""
    event = Event(
        event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
        project_id=PROJECT_ID,
        created_at="2026-08-12T00:00:00Z",
        revision_id=revision.revision_id,
        payload={"n": 1},
    )
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z", events=[event])
    dispatcher = CollectingDispatcher(accept=False)
    loop = conductor(store, dispatch=dispatcher)

    loop.tick(START)
    # Still pending, one attempt recorded — and invisible to a drain a second later,
    # because it is inside its backoff window. `pending_outbox()` without `now` is the
    # operator's view: everything queued, backoff ignored.
    assert store.pending_outbox()[0].delivery_attempts == 1
    assert store.pending_outbox(now=START + 1) == []

    dispatcher.accept = True
    # Far enough ahead to clear the backoff window.
    loop.tick(START + 7200.0)

    assert store.pending_outbox() == []
    assert store.outbox_counts_by_state() == {"sent": 1}


def test_delivery_attempts_grow_far_slower_than_ticks(
    store: SqliteStore, revision: Revision
) -> None:
    """The property that actually distinguishes backoff from a spin.

    Not "the next tick skips it" — the schedule starts at 120s and the cadence is 300s, so
    the first couple of retries legitimately land on the next tick. What matters is that
    the *rate* decays: over a day of ticks a permanently refused entry is attempted a
    handful of times, not 288. The old loop attempted it once per tick, forever.
    """
    event = Event(
        event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
        project_id=PROJECT_ID,
        created_at="2026-08-12T00:00:00Z",
        revision_id=revision.revision_id,
        payload={"n": 1},
    )
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z", events=[event])
    loop = conductor(store)

    a_day = 24 * 12  # 288 ticks at the 5-minute cadence
    for index in range(a_day):
        loop.tick(START + index * TICK_SECONDS)

    attempts = store._connection.execute(
        "SELECT delivery_attempts AS n FROM outbox"
    ).fetchone()["n"]
    assert attempts == MAX_DELIVERY_ATTEMPTS
    assert attempts < a_day / 10, "delivery is still being attempted at close to tick rate"
