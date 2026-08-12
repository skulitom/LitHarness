"""The exception queue: what policy could not resolve, waiting for a human (§4.3).

§4.2 ends every unresolvable unit with "park + escalate", and §19 requires that parked
units *and exceptions* be visible and bounded. The escalation half emitted an event and
stopped there — and an event is a fact in a log, not a queue. Answering "what is waiting
for me" meant replaying the event stream and reconstructing which escalations had since
been resolved, which is both the derived state a table exists to avoid recomputing and the
kind of reconstruction that quietly disagrees with reality after a crash.

**An exception is bound to its decision, not just to its job.** `decision_id` is the link
back to the gate trail that produced it. Without it the human arrives at "this unit
stopped" and has to do the join by hand to learn *which gate* refused and why — which is
the entire question they came to answer.

**Resolving an exception does not restart the work.** They are separate acts on purpose:
`resolve` closes the human's side, `store.revive` returns the unit to the queue. A director
may well decide an escalation was correct and the unit should stay stopped, and collapsing
the two would make "I have seen this and it should not run" inexpressible.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain.events import payload_digest


class ExceptionKind(enum.StrEnum):
    REPEATED_GATE_FAILURE = "repeated_gate_failure"
    #: Two locked constraints cannot both be satisfied. Needs a director, not a retry.
    CONSTRAINT_CONFLICT = "constraint_conflict"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    #: Outward-facing posting always follows a configured policy (§3).
    PUBLICATION_DECISION = "publication_decision"
    INTEGRITY_VIOLATION = "integrity_violation"

    def to_contract(self) -> lc.ExceptionKind:
        return lc.ExceptionKind(self.value)


class ExceptionStatus(enum.StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    #: Closed deliberately without action — the escalation was right and the unit stays
    #: stopped. Distinct from RESOLVED so "I looked and did nothing" is a recordable
    #: answer rather than an absence.
    DISMISSED = "dismissed"

    def to_contract(self) -> lc.ExceptionStatus:
        return lc.ExceptionStatus(self.value)

    @property
    def is_open(self) -> bool:
        return self in {ExceptionStatus.OPEN, ExceptionStatus.ACKNOWLEDGED}


@dataclass(frozen=True, slots=True)
class ExceptionRecord:
    exception_id: str
    kind: ExceptionKind
    summary: str
    status: ExceptionStatus = ExceptionStatus.OPEN
    job_id: str | None = None
    logical_id: str | None = None
    decision_id: str | None = None
    raised_at: str | None = None
    resolved_at: str | None = None
    resolution: str | None = None
    attempts: int = 0

    def close(
        self, resolution: str, *, at: str, status: ExceptionStatus = ExceptionStatus.RESOLVED
    ) -> ExceptionRecord:
        if not status.is_open:
            return replace(self, status=status, resolution=resolution, resolved_at=at)
        raise ValueError(f"{status.value} does not close an exception")

    def to_contract(self, meta: lc.ArtifactMeta) -> lc.ExceptionRecord:
        return lc.ExceptionRecord(
            meta=meta,
            exception_id=self.exception_id,
            kind=self.kind.to_contract(),
            summary=self.summary,
            status=self.status.to_contract(),
            job_id=self.job_id,
            decision_id=self.decision_id,
            raised_at=self.raised_at,
            resolved_at=self.resolved_at,
            resolution=self.resolution,
            attempts=self.attempts,
        )


def exception_id_for(job_id: str, kind: ExceptionKind, decision_id: str | None) -> str:
    """Derived, so one escalation of one unit produces one exception however many times
    the tick that raised it is replayed."""
    material = payload_digest(
        {"job_id": job_id, "kind": kind.value, "decision_id": decision_id}
    )
    return f"exc-{sha256(material.encode()).hexdigest()[:24]}"


__all__ = [
    "ExceptionKind",
    "ExceptionRecord",
    "ExceptionStatus",
    "exception_id_for",
]
