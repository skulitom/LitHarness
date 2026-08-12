"""Durable jobs and leases.

`litharness_contracts.JobRecord` already pins the parts that matter for interchange —
the `JobStatus` machine (including `poisoned` and `cancelled`), `idempotency_key`,
`input_digest`, `attempts`, `error`. What it has no concept of is a **lease**, and a
lease is what makes single-instance execution safe when the Conductor is started by a
cron tick that may overlap with a still-running one (§4.1).

So leases live here, in `Job`, and project onto the contract's `metadata`-free record by
being dropped. That is the honest state of things and the reason PLAN.md §20.3 lists
`lease_holder` / `lease_expires_at` as net-new 1.x fields: this module is the consumer
that now knows what they need to hold.

**Lease semantics.** A lease is a holder id plus an expiry. Claiming requires the job to
be unleased or its lease expired; renewal extends the expiry for the same holder;
release clears it. Expiry is wall-clock, which means a paused process can wake up
believing it still holds an expired lease — so every state-advancing write also checks
the lease, rather than trusting the claim from earlier in the tick. Time is injected
rather than read from the clock, because a scheduler whose correctness depends on the
clock has to be testable without waiting.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace

import litharness_contracts as lc


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    POISONED = "poisoned"

    @property
    def is_terminal(self) -> bool:
        return self in {
            JobStatus.SUCCEEDED,
            JobStatus.CANCELLED,
            JobStatus.POISONED,
        }

    def to_contract(self) -> lc.JobStatus:
        return lc.JobStatus(self.value)


#: Allowed transitions. Anything absent is a programming error, not a recoverable state:
#: silently permitting `succeeded -> running` would let a completed unit of work be
#: redone and double-commit its side effects.
TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    # `RUNNING -> QUEUED` is crash recovery, not a happy-path move: a holder that died
    # mid-job leaves the row RUNNING, and nothing would ever pick it up again because
    # `claim_next` only sees QUEUED. Reclaiming an expired lease is the only caller
    # (`SqliteStore.reclaim_expired`), and it requeues with attempts already counted so a
    # crash loop still poisons on budget rather than cycling forever. Omitting this edge is
    # what a first draft of this table did, and the symptom was a permanently stuck job.
    JobStatus.RUNNING: frozenset(
        {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.POISONED,
            JobStatus.QUEUED,
        }
    ),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED, JobStatus.POISONED, JobStatus.CANCELLED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
    JobStatus.POISONED: frozenset(),
}


class IllegalTransition(Exception):
    pass


class LeaseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Job:
    job_id: str
    job_kind: str
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    idempotency_key: str | None = None
    input_digest: str | None = None
    error: str | None = None
    #: Net-new relative to the contract — see the module docstring.
    lease_holder: str | None = None
    lease_expires_at: float | None = None
    max_attempts: int = 3

    # -- state machine --------------------------------------------------------

    def transition_to(self, status: JobStatus, *, error: str | None = None) -> Job:
        if status not in TRANSITIONS[self.status]:
            raise IllegalTransition(f"{self.status.value} -> {status.value} is not allowed")
        attempts = self.attempts + 1 if status is JobStatus.RUNNING else self.attempts
        return replace(self, status=status, attempts=attempts, error=error)

    def fail(self, error: str) -> Job:
        """Fail, and poison rather than requeue once the attempt budget is spent.

        The failure mode this prevents is the spin loop §4.2 forbids: a job that fails,
        requeues, fails again forever. Poisoned is terminal and visible.
        """
        failed = self.transition_to(JobStatus.FAILED, error=error)
        if failed.attempts >= self.max_attempts:
            return failed.transition_to(JobStatus.POISONED, error=error).released()
        return failed.released()

    # -- leases ---------------------------------------------------------------

    def is_leased_at(self, now: float) -> bool:
        return self.lease_expires_at is not None and self.lease_expires_at > now

    def claim(self, holder: str, now: float, duration: float) -> Job:
        if self.is_leased_at(now) and self.lease_holder != holder:
            raise LeaseError(
                f"job {self.job_id} is leased by {self.lease_holder} until {self.lease_expires_at}"
            )
        return replace(self, lease_holder=holder, lease_expires_at=now + duration)

    def renew(self, holder: str, now: float, duration: float) -> Job:
        if self.lease_holder != holder:
            raise LeaseError(f"job {self.job_id} is not held by {holder}")
        return replace(self, lease_expires_at=now + duration)

    def released(self) -> Job:
        return replace(self, lease_holder=None, lease_expires_at=None)

    def assert_held_by(self, holder: str, now: float) -> None:
        """Re-check the lease at the moment of a state-advancing write."""
        if self.lease_holder != holder or not self.is_leased_at(now):
            raise LeaseError(
                f"job {self.job_id} is no longer held by {holder} at {now}; refusing to advance"
            )

    # -- contract projection --------------------------------------------------

    def to_contract(self, meta: lc.ArtifactMeta) -> lc.JobRecord:
        return lc.JobRecord(
            meta=meta,
            job_id=self.job_id,
            job_kind=self.job_kind,
            status=self.status.to_contract(),
            attempts=self.attempts,
            idempotency_key=self.idempotency_key,
            input_digest=self.input_digest,
            error=self.error,
        )
