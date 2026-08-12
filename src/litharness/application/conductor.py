"""The Conductor: a durable scheduler with a policy seam where the gates will go.

§4.1 fixes the tick contract: ingest directives, reconcile state, select work, execute one
bounded unit, commit artifacts and events atomically, update the digest. This module is
that loop, with directive ingestion (§4.3) deliberately absent — the plan's Stage 0 scope
is "Conductor skeleton (tick, lease, job selection, digest stub)", and a directive inbox
without the Narrative Planner to interpret it would be a queue that nothing can read.

Three properties matter more than the loop itself.

**Ticks are idempotent.** A tick id is derived from `(holder, instant)`, and recording one
is `INSERT OR IGNORE`, so replaying a tick — the realistic case being a cron invocation
retried after a crash at the wrong moment — cannot double-count work or the digest. This is
what Stage 0's "ticks idempotently for a week unattended" actually asks for, and
`test_a_week_of_no_op_ticks_changes_nothing` measures it over the tick count a week
produces rather than over a week of waiting.

**Exactly one instance is the Conductor.** Every tick starts by claiming an instance lease.
A tick that loses the claim returns `NOT_LEADER` and does nothing at all — it does not
reconcile, select, or dispatch, because each of those mutates shared state. The job-level
lease is a separate mechanism answering a different question; see the migration comment.

**One bounded unit per tick.** The loop executes at most one job, then returns. A blocked or
failing unit therefore cannot starve the queue or spin: it fails, its attempts increment,
and either it requeues or it poisons (§4.2's "the failure mode is a parked unit, never a
spin loop").

Time is injected everywhere. A scheduler whose correctness depends on the wall clock cannot
be tested without waiting, and this one is tested over two thousand simulated ticks.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain.events import Event, EventType, OutboxEntry
from litharness.domain.jobs import Job, JobStatus

DEFAULT_SCOPE = "conductor"


class TickOutcome(enum.StrEnum):
    NOT_LEADER = "not_leader"
    PAUSED = "paused"
    NO_WORK = "no_work"
    RAN_JOB = "ran_job"
    JOB_FAILED = "job_failed"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True)
class TickResult:
    tick_id: str
    outcome: TickOutcome
    job_id: str | None = None
    reconciled: int = 0
    dispatched: int = 0
    events: tuple[Event, ...] = ()

    @property
    def did_work(self) -> bool:
        return self.outcome in {TickOutcome.RAN_JOB, TickOutcome.JOB_FAILED}


class JobHandler(Protocol):
    """Executes one unit of work and returns the events it wants committed.

    A handler must not write to the store itself. It returns events, and the Conductor
    commits them with the job's status change in one transaction — which is the only way
    "no accepted artifact without its event" survives a crash mid-handler.
    """

    def __call__(self, job: Job, now: float) -> Sequence[Event]: ...


class Dispatcher(Protocol):
    """Delivers one outbox entry. Returning False leaves it pending for a later tick."""

    def __call__(self, entry: OutboxEntry) -> bool: ...


def _null_dispatcher(entry: OutboxEntry) -> bool:
    """Default: deliver nowhere and say so, so the outbox stays honest until a real sink
    exists. Marking undelivered events as sent would be silent loss dressed as success."""
    return False


class WorkSelector(Protocol):
    """Chooses the next unit. The seam where §4.1's state-aware policy will live."""

    def __call__(
        self, store: SqliteStore, holder: str, now: float, duration: float
    ) -> Job | None: ...


def fifo_selector(store: SqliteStore, holder: str, now: float, duration: float) -> Job | None:
    """Skeleton policy: oldest claimable queued job wins.

    Deliberately not the real thing. §4.1 wants selection to be a policy over the book's
    state — unblocked beats to draft, findings by severity, derived artifacts to recompute —
    which needs a plan graph and a findings store that do not exist yet. FIFO is honest
    about being a placeholder; a cleverer arbitrary ordering would not be.
    """
    return store.claim_next(holder, now=now, duration=duration)


@dataclass
class Conductor:
    store: SqliteStore
    holder: str
    project_id: str
    handlers: dict[str, JobHandler] = field(default_factory=dict)
    select: WorkSelector = fifo_selector
    dispatch: Dispatcher = _null_dispatcher
    scope: str = DEFAULT_SCOPE
    lease_duration: float = 300.0
    job_lease_duration: float = 600.0
    paused: bool = False

    # -- tick -----------------------------------------------------------------

    def tick(self, now: float) -> TickResult:
        tick_id = self._tick_id(now)

        if not self.store.acquire_instance_lease(
            self.scope, self.holder, now, self.lease_duration
        ):
            # Another instance is the Conductor. Do nothing — not even reconcile.
            return TickResult(tick_id, TickOutcome.NOT_LEADER)

        if self.paused:
            self._finish(tick_id, now, TickOutcome.PAUSED, None, 0, 0)
            return TickResult(tick_id, TickOutcome.PAUSED)

        # Reconcile is two distinct recoveries, and both are needed. `reclaim_expired`
        # rescues a unit whose holder crashed mid-job; `requeue_failed` advances a unit that
        # failed cleanly. Omitting the second leaves FAILED jobs inert forever — no retry,
        # no poison, no escalation — which is the bug this loop shipped with until the
        # non-starvation test caught it.
        reconciled = len(self.store.reclaim_expired(now)) + len(self.store.requeue_failed())
        dispatched = self._drain_outbox()

        job = self.select(self.store, self.holder, now, self.job_lease_duration)
        if job is None:
            outcome = TickOutcome.NO_WORK
            if not self._finish(tick_id, now, outcome, None, reconciled, dispatched):
                return TickResult(tick_id, TickOutcome.REPLAYED)
            return TickResult(tick_id, outcome, reconciled=reconciled, dispatched=dispatched)

        outcome, events = self._run(job, now)
        if not self._finish(tick_id, now, outcome, job.job_id, reconciled, dispatched):
            return TickResult(tick_id, TickOutcome.REPLAYED, job_id=job.job_id)
        return TickResult(
            tick_id,
            outcome,
            job_id=job.job_id,
            reconciled=reconciled,
            dispatched=dispatched,
            events=tuple(events),
        )

    # -- internals ------------------------------------------------------------

    def _tick_id(self, now: float) -> str:
        material = f"{self.scope}|{self.holder}|{now!r}".encode()
        return f"tick-{sha256(material).hexdigest()[:24]}"

    def _run(self, job: Job, now: float) -> tuple[TickOutcome, Sequence[Event]]:
        handler = self.handlers.get(job.job_kind)
        if handler is None:
            self.store.save_job(
                job.transition_to(JobStatus.RUNNING).fail(f"no handler for {job.job_kind}")
            )
            return TickOutcome.JOB_FAILED, ()

        running = job.transition_to(JobStatus.RUNNING)
        self.store.save_job(running)
        try:
            # Re-check the lease at the moment of doing work, not just at claim time.
            running.assert_held_by(self.holder, now)
            events = list(handler(running, now))
        except Exception as error:  # a handler failure is data, not a crash
            failed = running.fail(f"{type(error).__name__}: {error}")
            self.store.save_job(failed)
            self.store.append_events(
                [
                    self._event(
                        EventType.JOB_FAILED,
                        {"job_id": job.job_id, "error": str(error)},
                        now,
                    )
                ]
            )
            self.store.bump_digest(self._day(now), "jobs_failed")
            return TickOutcome.JOB_FAILED, ()

        self.store.append_events(events)
        self.store.save_job(running.transition_to(JobStatus.SUCCEEDED))
        self.store.bump_digest(self._day(now), "jobs_succeeded")
        return TickOutcome.RAN_JOB, events

    def _drain_outbox(self, limit: int = 50) -> int:
        """Send-then-mark. A refused delivery records the attempt and stays pending."""
        sent = 0
        for entry in self.store.pending_outbox(limit):
            if self.dispatch(entry):
                self.store.mark_sent(entry.idempotency_key)
                sent += 1
            else:
                self.store.record_delivery_attempt(entry.idempotency_key)
        return sent

    def _finish(
        self,
        tick_id: str,
        now: float,
        outcome: TickOutcome,
        job_id: str | None,
        reconciled: int,
        dispatched: int,
    ) -> bool:
        fresh = self.store.record_tick(
            tick_id=tick_id,
            holder=self.holder,
            started_at=now,
            outcome=outcome.value,
            job_id=job_id,
            reconciled=reconciled,
            dispatched=dispatched,
        )
        if fresh:
            self.store.bump_digest(self._day(now), "ticks")
        return fresh

    def _event(self, event_type: EventType, payload: dict[str, object], now: float) -> Event:
        return Event(
            event_type=event_type,
            project_id=self.project_id,
            created_at=self._timestamp(now),
            actor=self.holder,
            payload=dict(payload),
        )

    @staticmethod
    def _timestamp(now: float) -> str:
        return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _day(now: float) -> str:
        return datetime.fromtimestamp(now, tz=UTC).date().isoformat()


def no_op_handler(job: Job, now: float) -> Sequence[Event]:
    """The workload Stage 0's endurance criterion runs on: succeeds, emits nothing."""
    return ()


__all__ = [
    "Conductor",
    "Dispatcher",
    "JobHandler",
    "TickOutcome",
    "TickResult",
    "WorkSelector",
    "fifo_selector",
    "no_op_handler",
]
