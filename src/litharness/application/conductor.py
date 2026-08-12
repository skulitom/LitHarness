"""The Conductor: a durable scheduler with a policy seam where the gates will go.

§4.1 fixes the tick contract: ingest directives, reconcile state, select work, execute one
bounded unit, commit artifacts and events atomically, update the digest. This module is
that loop, in that order.

**Ingest is first, and the ordering is the requirement.** A directive that arrived since
the last tick must be able to influence what this tick selects; if selection ran first, the
directive would sit unread for a full cycle behind the very work it was meant to redirect.
Only the *capture* half exists — interpreting a directive into versioned plan constraints
needs the Narrative Planner (§9), which does not — so directives are drained, recorded, and
left in `RECEIVED`. That is deliberate and it is visible: unread direction shows up as a
growing `RECEIVED` count and as `interpreted: false` in the event log, rather than as
either silence or an invented reading.

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
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain.events import Event, EventType, OutboxEntry
from litharness.domain.exceptions import ExceptionKind, ExceptionRecord, exception_id_for
from litharness.domain.failures import TransientFailure
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.policy import Outcome, PolicyDecision

DEFAULT_SCOPE = "conductor"


class TickOutcome(enum.StrEnum):
    NOT_LEADER = "not_leader"
    PAUSED = "paused"
    NO_WORK = "no_work"
    RAN_JOB = "ran_job"
    JOB_FAILED = "job_failed"
    #: Terminal by policy decision (§4.2 park/escalate), not by error.
    JOB_PARKED = "job_parked"
    REPLAYED = "replayed"


@dataclass(frozen=True, slots=True)
class TickResult:
    tick_id: str
    outcome: TickOutcome
    job_id: str | None = None
    reconciled: int = 0
    dispatched: int = 0
    #: Directives drained from the inbox this tick (§4.3).
    ingested: int = 0
    events: tuple[Event, ...] = ()

    @property
    def did_work(self) -> bool:
        return self.outcome in {
            TickOutcome.RAN_JOB,
            TickOutcome.JOB_FAILED,
            TickOutcome.JOB_PARKED,
        }


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


class HealthResettable(Protocol):
    """Anything holding per-tick cached health verdicts. `ProviderRegistry` satisfies it.

    Typed structurally rather than importing the registry, so `application` keeps its one
    -way dependency on `providers` at the handler layer instead of the loop.
    """

    def reset_health(self) -> None: ...


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
    #: Cleared once per leading tick. `ProviderRegistry.reset_health` documents "called at
    #: the start of a tick" and had no caller, so a provider marked dead by one failed
    #: probe stayed dead for the life of the process and never recovered. Harmless while
    #: nothing owned a registry; a real bug the moment a handler does.
    registry: HealthResettable | None = None

    # -- tick -----------------------------------------------------------------

    def tick(self, now: float) -> TickResult:
        tick_id = self._tick_id(now)

        if not self.store.acquire_instance_lease(
            self.scope, self.holder, now, self.lease_duration
        ):
            # Another instance is the Conductor. Do nothing — not even reconcile.
            return TickResult(tick_id, TickOutcome.NOT_LEADER)

        # Durable, not in-memory. §4.1 runs this as a cron tick, so every tick is a fresh
        # process and a dataclass field would be reconstructed as False every time — the
        # pause control was unreachable in exactly the deployment the plan specifies.
        if self.paused or self.store.is_paused():
            self._finish(tick_id, now, TickOutcome.PAUSED, None, 0, 0)
            return TickResult(tick_id, TickOutcome.PAUSED)

        # Fresh health verdicts for this tick. Deliberately after the leadership guard —
        # a non-leader must not touch shared state, and deliberately before reconcile, so
        # every probe in the tick sees one consistent verdict per provider.
        if self.registry is not None:
            self.registry.reset_health()

        # §4.1 step 1. Ingest runs *before* selection, which is the whole ordering
        # requirement: a directive that arrived since the last tick must be able to
        # influence what this tick picks up, and must never mutate a job already running.
        ingested = self._ingest_directives(now)

        # Reconcile is two distinct recoveries, and both are needed. `reclaim_expired`
        # rescues a unit whose holder crashed mid-job; `requeue_failed` advances a unit that
        # failed cleanly. Omitting the second leaves FAILED jobs inert forever — no retry,
        # no poison, no escalation — which is the bug this loop shipped with until the
        # non-starvation test caught it.
        reconciled = len(self.store.reclaim_expired(now)) + len(self.store.requeue_failed())
        dispatched = self._drain_outbox(now)

        job = self.select(self.store, self.holder, now, self.job_lease_duration)
        if job is None:
            outcome = TickOutcome.NO_WORK
            if not self._finish(tick_id, now, outcome, None, reconciled, dispatched):
                return TickResult(tick_id, TickOutcome.REPLAYED)
            return TickResult(
                tick_id,
                outcome,
                reconciled=reconciled,
                dispatched=dispatched,
                ingested=ingested,
            )

        outcome, events = self._run(job, now)
        if not self._finish(tick_id, now, outcome, job.job_id, reconciled, dispatched):
            return TickResult(tick_id, TickOutcome.REPLAYED, job_id=job.job_id)
        return TickResult(
            tick_id,
            outcome,
            job_id=job.job_id,
            reconciled=reconciled,
            dispatched=dispatched,
            ingested=ingested,
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
        except TransientFailure as error:
            # **Infrastructure failure must not consume the unit's attempt budget.**
            # `ProviderUnavailable` is raised by `resolve` *before* any work is attempted,
            # so the candidate was never produced and nothing about this unit is wrong.
            # Charging it was the difference between "a provider blipped" and "every unit
            # touched during a 15-minute outage is permanently poisoned": three ticks at
            # the plan's cadence spends `max_attempts`, and poisoned is terminal and burns
            # the idempotency key, so the work could not even be resubmitted.
            # `transition_to(RUNNING)` already incremented attempts; restore the count so
            # the outage costs time rather than the unit's budget.
            requeued = replace(
                running.transition_to(JobStatus.QUEUED), attempts=job.attempts
            ).released()
            self.store.save_job(requeued)
            self.store.append_events(
                [
                    self._event(
                        EventType.PROVIDER_FELL_BACK,
                        {"job_id": job.job_id, "error": str(error), "requeued": True},
                        now,
                    )
                ]
            )
            self.store.bump_digest(self._day(now), "provider_unavailable")
            return TickOutcome.JOB_FAILED, ()
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

        # **The handler returning is not the same as the work succeeding.** §4.2's ladder
        # produces accept | retry | repair | regenerate | park | escalate, and until this
        # branch existed the loop marked every non-raising handler SUCCEEDED — so a
        # candidate the policy engine *escalated* was counted as a success in the digest
        # and its unit silently dropped off the queue. Neither parked, nor visible, nor
        # bounded: gone. The decision is read back from storage rather than returned by the
        # handler because `JobHandler` returns events by contract, and widening that
        # contract for one handler's benefit would make every future handler carry it.
        decision = self.store.latest_decision_for(job.job_id)
        outcome = decision.outcome if decision is not None else Outcome.ACCEPT
        return self._settle(running, outcome, decision, now, events)

    def _settle(
        self,
        running: Job,
        outcome: Outcome,
        decision: PolicyDecision | None,
        now: float,
        events: Sequence[Event],
    ) -> tuple[TickOutcome, Sequence[Event]]:
        """Apply one §4.2 decision to the job row, the digest and the event log."""
        reason = (decision.reason if decision else None) or outcome.value

        if outcome is Outcome.ACCEPT:
            self.store.save_job(running.transition_to(JobStatus.SUCCEEDED))
            self.store.bump_digest(self._day(now), "jobs_succeeded")
            return TickOutcome.RAN_JOB, events

        if outcome in {Outcome.RETRY, Outcome.REGENERATE, Outcome.REPAIR}:
            # `fail` already poisons once the attempt budget is spent, so a retry ladder
            # that never converges still terminates. This is the existing bounded-retry
            # path; the change is only that policy decides to enter it.
            self.store.save_job(running.fail(reason))
            self.store.bump_digest(self._day(now), "jobs_retried")
            return TickOutcome.JOB_FAILED, events

        # **Two vocabularies meet here, and they do not use the same words.** At the
        # decision layer §4.2 says *park* (the unit is stuck, move on) and *escalate* (a
        # human is needed). At the job layer this codebase already said *poisoned* (the
        # attempt budget is spent) and now says *parked* (stopped by decision, revivable).
        # They line up crosswise, and pretending otherwise would give the operator the
        # wrong word for the state they are looking at:
        #
        #   Outcome.PARK      — `decide` returns this only on attempt exhaustion, which is
        #                       precisely what POISONED has always meant. Not revivable:
        #                       reviving without changing anything just spends the budget
        #                       again.
        #   Outcome.ESCALATE  — no retry can resolve the veto (a locked node, a missing
        #                       target). Terminal, but the blocker is external and a human
        #                       can clear it, so PARKED and revivable — plus an exception,
        #                       because §4.2's failure mode is "a parked unit *plus an
        #                       exception*", and a stuck unit nobody is told about is just
        #                       a lost one.
        if outcome is Outcome.PARK:
            self.store.save_job(running.transition_to(JobStatus.POISONED, error=reason).released())
            self.store.bump_digest(self._day(now), "jobs_poisoned")
            return TickOutcome.JOB_PARKED, events

        parked = running.transition_to(JobStatus.PARKED, error=reason).released()
        self.store.save_job(parked)
        self.store.bump_digest(self._day(now), "jobs_parked")
        self.store.bump_digest(self._day(now), "exceptions_raised")
        # The queue, not just the event. An event is a fact in a log; answering "what is
        # waiting for me" from events alone means replaying the stream and reconstructing
        # which escalations were since resolved.
        self.store.raise_exception(
            ExceptionRecord(
                exception_id=exception_id_for(
                    running.job_id,
                    ExceptionKind.REPEATED_GATE_FAILURE,
                    decision.decision_id if decision else None,
                ),
                kind=ExceptionKind.REPEATED_GATE_FAILURE,
                summary=reason,
                job_id=running.job_id,
                logical_id=decision.logical_id if decision else None,
                decision_id=decision.decision_id if decision else None,
                raised_at=self._timestamp(now),
                attempts=parked.attempts,
            )
        )
        raised = [
            self._event(
                EventType.EXCEPTION_RAISED,
                {
                    "job_id": running.job_id,
                    "outcome": outcome.value,
                    "reason": reason,
                    "decision_id": decision.decision_id if decision else None,
                    "attempts": parked.attempts,
                },
                now,
            )
        ]
        self.store.append_events(raised)
        return TickOutcome.JOB_PARKED, [*events, *raised]

    def _ingest_directives(self, now: float) -> int:
        """Drain the direction inbox (§4.3), recording each arrival as an event.

        **Capture only.** Converting a directive into versioned plan constraints needs the
        Narrative Planner (§9), which does not exist, so a directive is marked ingested and
        left in `RECEIVED`. That is deliberate and visible: `directives_by_status(RECEIVED)`
        grows, which reads as "queued and unread" rather than as work silently dropped. The
        alternative — not capturing until an interpreter exists — loses direction the
        director gives today.
        """
        pending = self.store.pending_directives()
        if not pending:
            return 0
        stamp = self._timestamp(now)
        events = [
            self._event(
                EventType.DIRECTIVE_INGESTED,
                {
                    "directive_id": directive.directive_id,
                    "kind": directive.kind.value,
                    "precedence": directive.precedence,
                    "status": directive.status.value,
                    # Named rather than implied, so a reader of the log is not left to
                    # infer why nothing acted on it.
                    "interpreted": False,
                    "awaiting": "narrative_planner",
                },
                now,
            )
            for directive in pending
        ]
        self.store.append_events(events)
        for directive in pending:
            self.store.mark_directive_ingested(directive.directive_id, ingested_at=stamp)
        self.store.bump_digest(self._day(now), "directives_ingested", len(pending))
        return len(pending)

    def _drain_outbox(self, now: float, limit: int = 50) -> int:
        """Send-then-mark, with a refused delivery backed off rather than retried at once.

        `now` is not decorative: without it this loop re-attempted the first 50 pending
        entries on *every* tick forever. Measured over the week the endurance test
        simulates, the head entries reached 2016 delivery attempts while entries 51 and
        beyond reached zero — an unbounded spin and permanent head-of-line starvation at
        once, both invisible because the endurance test asserts an empty outbox.
        """
        sent = 0
        for entry in self.store.pending_outbox(limit, now=now):
            if self.dispatch(entry):
                self.store.mark_sent(entry.idempotency_key)
                sent += 1
            elif self.store.record_delivery_attempt(entry.idempotency_key, now=now):
                self.store.bump_digest(self._day(now), "outbox_failed")
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
