"""The Conductor: a durable scheduler with a policy seam where the gates will go.

§4.1 fixes the tick contract: ingest directives, reconcile state, select work, execute one
bounded unit, commit artifacts and events atomically, update the digest. This module is
that loop, in that order.

**Ingest is first, and the ordering is the requirement.** A directive that arrived since
the last tick must be able to influence what this tick selects; if selection ran first, the
directive would sit unread for a full cycle behind the very work it was meant to redirect.
Interpretation remains a later work unit rather than part of ingestion itself: directives
are drained and recorded first, then the selector can materialise deterministic constraints
or bounded Narrative Planner work before prose. Unresolved direction stays visibly
`RECEIVED` rather than disappearing as silence or an invented reading.

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

from litharness.application.ports import ApplicationStore, TextGenerator
from litharness.domain.directives import VERBATIM_KINDS
from litharness.domain.events import Event, EventType, OutboxEntry
from litharness.domain.exceptions import ExceptionKind, ExceptionRecord, exception_id_for
from litharness.domain.failures import OperationalFailure, ParkedFailure, TransientFailure
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


def null_dispatcher(entry: OutboxEntry) -> bool:
    """Deliver nowhere and say so, which is the honest default when no sink is configured.
    Marking undelivered events as sent would be silent loss dressed as success.

    Named rather than private since `adapters.notifications` gave the outbox somewhere real
    to drain: with two dispatchers the choice belongs to the composition root, and a
    composition root that cannot name the default it is choosing has to express "no sink"
    by omitting an argument — which is how this stayed the *only* dispatcher for nine
    slices without anyone deciding that it should be.
    """
    return False


class WorkSelector(Protocol):
    """Chooses the next unit. The seam where §4.1's state-aware policy will live."""

    def __call__(
        self, store: ApplicationStore, holder: str, now: float, duration: float
    ) -> Job | None: ...


def fifo_selector(
    store: ApplicationStore, holder: str, now: float, duration: float
) -> Job | None:
    """Skeleton policy: oldest claimable queued job wins.

    Deliberately not the real thing. §4.1 wants selection to be a policy over the book's
    state — unblocked beats to draft, findings by severity, derived artifacts to recompute —
    which needs a plan graph and a findings store that do not exist yet. FIFO is honest
    about being a placeholder; a cleverer arbitrary ordering would not be.
    """
    return store.claim_next(holder, now=now, duration=duration)


@dataclass
class Conductor:
    store: ApplicationStore
    holder: str
    project_id: str
    handlers: dict[str, JobHandler] = field(default_factory=dict)
    select: WorkSelector = fifo_selector
    dispatch: Dispatcher = null_dispatcher
    scope: str = DEFAULT_SCOPE
    lease_duration: float = 300.0
    job_lease_duration: float = 600.0
    paused: bool = False
    #: Cleared once per leading tick. `ProviderRegistry.reset_health` documents "called at
    #: the start of a tick" and had no caller, so a provider marked dead by one failed
    #: probe stayed dead for the life of the process and never recovered. Harmless while
    #: nothing owned a registry; a real bug the moment a handler does.
    registry: TextGenerator | None = None

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
            diagnostic = error.diagnostic()
            self.store.append_events(
                [
                    self._event(
                        EventType.PROVIDER_FELL_BACK,
                        {
                            "job_id": job.job_id,
                            "error": str(error),
                            "requeued": True,
                            **diagnostic,
                        },
                        now,
                    )
                ]
            )
            self.store.bump_digest(self._day(now), "provider_unavailable")
            return TickOutcome.JOB_FAILED, ()
        except ParkedFailure as error:
            # Retrying unchanged cannot clear authentication, invalid-request, or context
            # overflow failures. Give back the candidate attempt exactly as for a transient
            # outage, but park instead of requeueing so the cadence cannot spin on it.
            stopped = replace(running, attempts=job.attempts)
            final = stopped.transition_to(JobStatus.PARKED, error=str(error)).released()
            self.store.save_job(final)
            diagnostic = error.diagnostic()
            failed_event = self._event(
                EventType.JOB_FAILED,
                {
                    "job_id": job.job_id,
                    "error": str(error),
                    "parked": True,
                    **diagnostic,
                },
                now,
            )
            self.store.append_events([failed_event])
            self.store.bump_digest(self._day(now), "jobs_parked")
            self.store.bump_digest(self._day(now), "provider_blocked")
            raised = self._raise_exception(
                final,
                None,
                f"{error.classification}: {error}",
                now,
                exhausted=False,
                kind=ExceptionKind.PROVIDER_UNAVAILABLE,
            )
            return TickOutcome.JOB_PARKED, [failed_event, *raised]
        except Exception as error:  # a handler failure is data, not a crash
            failed = running.fail(f"{type(error).__name__}: {error}")
            self.store.save_job(failed)
            diagnostic = error.diagnostic() if isinstance(error, OperationalFailure) else {}
            self.store.append_events(
                [
                    self._event(
                        EventType.JOB_FAILED,
                        {"job_id": job.job_id, "error": str(error), **diagnostic},
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
        # attempt budget is spent) and *parked* (stopped by decision, revivable). Both
        # outcomes are terminal and both file an exception; the only thing that differs is
        # *which* terminal state, and that is a fact about the attempt budget rather than
        # about the word policy used. Deriving it from the word is what this branch used to
        # do, and it was wrong twice over — see below.
        #
        #   POISONED  — the attempt budget really is spent. Not revivable: reviving without
        #               changing anything just spends it again.
        #   PARKED    — stopped while attempts remain, because no retry can resolve the
        #               refusal (a locked node, a missing target, a daily ceiling). The
        #               blocker is external and a human can clear it, so `revive` works.
        #
        # **The correction.** This code asserted, in a comment, that "`decide` returns PARK
        # only on attempt exhaustion" and mapped PARK straight to POISONED. The budget gate
        # falsifies the premise: `handlers` parks on attempt 1 when the daily ceiling
        # refuses a call. So a refusal that resolves itself at midnight was made terminal
        # and unrevivable, and its idempotency key burned so the work could not even be
        # resubmitted — §19's "parked units are visible and revivable" measurably false on
        # the first refusal an operator with real ceilings meets. It is the same shape as
        # the provider-outage bug two branches up, which this project has already paid to
        # learn once: an outage must cost time, not work. So must a ceiling.
        stopped = running
        if decision is not None and decision.refused_before_work:
            # Nothing was generated and nothing was spent, so the attempt that
            # `transition_to(RUNNING)` charged is given back. Without this, three ticks
            # under a ceiling poison a unit that never ran — which is exactly how the
            # outage bug killed work, one layer down.
            stopped = replace(running, attempts=max(running.attempts - 1, 0))

        # **And the same premise broke a third time.** The correction above replaced "PARK
        # means exhaustion" with "PARK at the ceiling means exhaustion", which held only
        # while every parkable refusal happened to arrive at the ceiling. `PARKABLE` ends
        # that: a craft gate refuses at *any* attempt number, ahead of the budget check, so
        # a refusal landing on attempt 3 is indistinguishable here from a budget spent —
        # and the unit would poison, become unrevivable, vanish from `jobs --status parked`
        # and carry an exception reading "attempt budget spent" about a budget that was not
        # what stopped it. The decision now says which it was rather than the count implying
        # it, because the count has been wrong about this twice.
        parked_by_policy = decision is not None and decision.parked_by_veto
        exhausted = (
            outcome is Outcome.PARK
            and stopped.attempts >= stopped.max_attempts
            and not parked_by_policy
        )
        status = JobStatus.POISONED if exhausted else JobStatus.PARKED
        final = stopped.transition_to(status, error=reason).released()
        self.store.save_job(final)
        self.store.bump_digest(self._day(now), "jobs_poisoned" if exhausted else "jobs_parked")
        # **Attempt exhaustion raises an exception too, and this is the modal case.** Only
        # ESCALATE filed one at first, which meant the *common* way a unit dies — three
        # length vetoes, three shape failures — produced a poisoned row and an empty
        # exception queue. §17 lists "exception queue functioning" as a Stage 1 exit
        # criterion, and it was false for the failure an operator will actually meet.
        # `REPEATED_GATE_FAILURE` is reused rather than a new kind added: the contract's
        # enum has no attempt-exhaustion member, a minor for one word is not worth it, and
        # the distinction is already carried by the status the exception points at.
        #
        # **A parkable veto is the exception to it, and the whole point of the class.**
        # §4.2 reserves escalation for what policy *could not resolve*; a craft refusal is
        # policy resolving — the scene does not go in, and that is a decision, not a
        # failure. Filing an exception anyway would put every refusal in the queue a human
        # is asked to clear, which is exactly the director interruption `PARKABLE` was
        # chosen over `ESCALATE` to avoid, arriving one layer below the choice. The unit is
        # still visible, in `jobs --status parked` where a refusal belongs and where the
        # README says to look for it.
        if parked_by_policy:
            return TickOutcome.JOB_PARKED, list(events)
        raised = self._raise_exception(final, decision, reason, now, exhausted=exhausted)
        return TickOutcome.JOB_PARKED, [*events, *raised]

    def _raise_exception(
        self,
        job: Job,
        decision: PolicyDecision | None,
        reason: str,
        now: float,
        *,
        exhausted: bool,
        kind: ExceptionKind = ExceptionKind.REPEATED_GATE_FAILURE,
    ) -> Sequence[Event]:
        """File the escalation in the queue *and* the log.

        The queue is what answers "what is waiting for me"; an event alone would mean
        replaying the stream and reconstructing which escalations were since resolved.
        """
        summary = (
            f"attempt budget spent after {job.attempts} attempts: {reason}"
            if exhausted
            else reason
        )
        self.store.bump_digest(self._day(now), "exceptions_raised")
        self.store.raise_exception(
            ExceptionRecord(
                exception_id=exception_id_for(
                    job.job_id,
                    kind,
                    decision.decision_id if decision else None,
                ),
                kind=kind,
                summary=summary,
                job_id=job.job_id,
                logical_id=decision.logical_id if decision else None,
                decision_id=decision.decision_id if decision else None,
                raised_at=self._timestamp(now),
                attempts=job.attempts,
            )
        )
        raised = [
            self._event(
                EventType.EXCEPTION_RAISED,
                {
                    "job_id": job.job_id,
                    "outcome": job.status.value,
                    "reason": summary,
                    "decision_id": decision.decision_id if decision else None,
                    "attempts": job.attempts,
                },
                now,
            )
        ]
        self.store.append_events(raised)
        return raised

    def _ingest_directives(self, now: float) -> int:
        """Drain the direction inbox (§4.3), recording each arrival as an event.

        Ingestion itself never interprets. Explicit constraints and vetoes can be picked up
        by the deterministic verbatim lane during selection later in this tick; everything
        else remains visibly `RECEIVED` for the Narrative Planner.
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
                    "awaiting": (
                        "directive_verbatim"
                        if directive.kind in VERBATIM_KINDS
                        else "narrative_planner"
                    ),
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
    "null_dispatcher",
]
