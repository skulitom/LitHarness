"""Persistence capabilities required by application workflows.

Application code coordinates storage but must not know that the current adapter is SQLite.
These structural protocols describe behavior at use-case boundaries. ``SqliteStore``
satisfies them without inheritance, leaving a future split store, in-memory harness, or
remote adapter free to implement only the capabilities a workflow actually needs.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from typing import Any, Protocol

import litharness_contracts as lc

from litharness.domain.audit import AuditSample
from litharness.domain.budget import Spend
from litharness.domain.calibration import Calibration
from litharness.domain.craft import CraftMetric
from litharness.domain.directives import Directive, DirectiveStatus
from litharness.domain.events import Event, OutboxEntry
from litharness.domain.exceptions import ExceptionRecord
from litharness.domain.findings import Finding
from litharness.domain.findings import Status as FindingStatus
from litharness.domain.jobs import Job
from litharness.domain.plan_refinement import PlanApplication, PlanRevision
from litharness.domain.policy import PolicyDecision
from litharness.domain.revision import Revision


class BranchReader(Protocol):
    def branches(self) -> list[tuple[str, str, str]]: ...


class ManuscriptReader(BranchReader, Protocol):
    def head(self, book_id: str, branch_id: str) -> Revision | None: ...

    def load_revision(self, revision_id: str) -> Revision: ...


class ManuscriptWriter(Protocol):
    def commit_revision(
        self,
        revision: Revision,
        *,
        created_at: str,
        events: Sequence[Event] = ...,
        state_records: Sequence[lc.StateRecord] = ...,
        retract_state_from: Collection[str] = ...,
        retract_state_for_nodes: Collection[str] = ...,
        jobs: Sequence[Job] = ...,
        decision: PolicyDecision | None = ...,
    ) -> None: ...


class PlanReader(Protocol):
    def plan_items(
        self,
        book_id: str,
        branch_id: str,
        *,
        kind: lc.PlanKind | None = ...,
    ) -> list[lc.PlanItem]: ...

    def plan_revision(self, book_id: str, branch_id: str) -> PlanRevision | None: ...

    def plan_revision_for_id(self, plan_revision_id: str) -> PlanRevision: ...

    def plan_epoch(self, book_id: str, branch_id: str) -> int: ...


class PlanWriter(Protocol):
    def commit_plan_application(
        self,
        application: PlanApplication,
        *,
        created_at: str,
        interpreted_at: str,
        events: Sequence[Event],
        decision: PolicyDecision,
    ) -> None: ...


class DirectiveInbox(Protocol):
    def pending_directives(self, limit: int = ...) -> list[Directive]: ...

    def directives_by_status(self, status: DirectiveStatus) -> list[Directive]: ...

    def ingested_directives_by_status(self, status: DirectiveStatus) -> list[Directive]: ...

    def load_directive(self, directive_id: str) -> Directive: ...

    def mark_directive_ingested(self, directive_id: str, *, ingested_at: str) -> None: ...


class JobQueue(Protocol):
    def enqueue(self, job: Job) -> bool: ...

    def claim_next(self, holder: str, now: float, duration: float) -> Job | None: ...

    def save_job(self, job: Job) -> None: ...

    def reclaim_expired(self, now: float) -> list[Job]: ...

    def requeue_failed(self) -> list[Job]: ...

    def has_job(self, job_id: str) -> bool: ...

    def any_unfinished(self, job_ids: Sequence[str]) -> bool: ...

    def job_counts_by_status(self) -> dict[str, int]: ...


class DecisionRepository(Protocol):
    def latest_decision_for(self, job_id: str) -> PolicyDecision | None: ...

    def record_decision(
        self, decision: PolicyDecision, *, decided_at: str
    ) -> bool: ...

    def spend_on(self, day: str) -> Spend: ...


class FindingRepository(Protocol):
    def load_finding(self, finding_id: str) -> Finding: ...

    def findings(
        self,
        book_id: str,
        branch_id: str,
        *,
        logical_id: str | None = ...,
        status: FindingStatus | None = ...,
        open_only: bool = ...,
    ) -> list[Finding]: ...

    def record_findings(
        self,
        book_id: str,
        branch_id: str,
        findings: Sequence[Finding],
        *,
        created_at: str,
        revision_id: str | None = ...,
        events: Sequence[Event] = ...,
    ) -> int: ...

    def commit_evaluation(
        self,
        book_id: str,
        branch_id: str,
        revision_id: str,
        findings: Sequence[Finding],
        *,
        created_at: str,
        events: Sequence[Event],
        jobs: Sequence[Job] = ...,
        fixed_finding_id: str | None = ...,
    ) -> None: ...


class StateRepository(Protocol):
    def state_records(
        self,
        book_id: str,
        branch_id: str,
        *,
        subject: str | None = ...,
        before: str | None = ...,
    ) -> list[lc.StateRecord]: ...

class AuditRepository(Protocol):
    def audit_samples(self, *, pending_only: bool = ...) -> list[AuditSample]: ...

    def record_audit_sample(
        self, sample: AuditSample, *, events: Sequence[Event] = ...
    ) -> bool: ...

    def calibrations(self, *, metric_id: str | None = ...) -> list[Calibration]: ...

    def record_craft_metrics(
        self,
        revision_id: str,
        logical_id: str,
        metrics: Sequence[CraftMetric],
        *,
        measured_at: str,
    ) -> int: ...


class EventRepository(Protocol):
    def append_events(self, events: Iterable[Event]) -> None: ...

    def pending_outbox(
        self, limit: int = ..., *, now: float | None = ...
    ) -> list[OutboxEntry]: ...

    def mark_sent(self, idempotency_key: str) -> None: ...

    def record_delivery_attempt(self, idempotency_key: str, *, now: float) -> bool: ...

    def outbox_counts_by_state(self) -> dict[str, int]: ...


class OperationsRepository(Protocol):
    def acquire_instance_lease(
        self, scope: str, holder: str, now: float, duration: float
    ) -> bool: ...

    def instance_lease(self, scope: str) -> tuple[str | None, float | None]: ...

    def is_paused(self) -> bool: ...

    def record_tick(
        self,
        *,
        tick_id: str,
        holder: str,
        started_at: float,
        outcome: str,
        job_id: str | None,
        reconciled: int,
        dispatched: int,
    ) -> bool: ...

    def last_tick(self) -> dict[str, Any] | None: ...

    def bump_digest(self, day: str, metric: str, value: int = ...) -> None: ...

    def digest(self, day: str) -> dict[str, int]: ...


class ExceptionRepository(Protocol):
    def raise_exception(self, record: ExceptionRecord) -> bool: ...

    def open_exceptions(self, limit: int = ...) -> list[ExceptionRecord]: ...


class ConductorStore(
    JobQueue,
    DirectiveInbox,
    DecisionRepository,
    EventRepository,
    OperationsRepository,
    ExceptionRepository,
    Protocol,
):
    pass


class PlanningStore(
    JobQueue,
    DirectiveInbox,
    ManuscriptReader,
    PlanReader,
    StateRepository,
    OperationsRepository,
    Protocol,
):
    pass


class DraftStore(
    ManuscriptReader,
    ManuscriptWriter,
    PlanReader,
    DecisionRepository,
    FindingRepository,
    StateRepository,
    AuditRepository,
    Protocol,
):
    pass


class NarrativePlanningStore(
    DirectiveInbox,
    PlanReader,
    PlanWriter,
    DecisionRepository,
    Protocol,
):
    pass


class PlanRefinementStore(PlanReader, PlanWriter, Protocol):
    pass


class EvaluationStore(
    ManuscriptReader,
    PlanReader,
    FindingRepository,
    StateRepository,
    JobQueue,
    Protocol,
):
    pass


class RepairStore(
    ManuscriptReader,
    ManuscriptWriter,
    FindingRepository,
    StateRepository,
    DecisionRepository,
    Protocol,
):
    pass


class ExportStore(ManuscriptReader, PlanReader, Protocol):
    pass


class StatusStore(
    BranchReader,
    DirectiveInbox,
    JobQueue,
    DecisionRepository,
    FindingRepository,
    EventRepository,
    OperationsRepository,
    ExceptionRepository,
    Protocol,
):
    pass


class ApplicationStore(
    ManuscriptReader,
    ManuscriptWriter,
    PlanReader,
    PlanWriter,
    DirectiveInbox,
    JobQueue,
    DecisionRepository,
    FindingRepository,
    StateRepository,
    AuditRepository,
    EventRepository,
    OperationsRepository,
    ExceptionRepository,
    Protocol,
):
    """Aggregate accepted by the composition root and pluggable work selectors."""


__all__ = [
    "ApplicationStore",
    "ConductorStore",
    "DraftStore",
    "EvaluationStore",
    "ExportStore",
    "JobQueue",
    "NarrativePlanningStore",
    "PlanRefinementStore",
    "PlanningStore",
    "RepairStore",
    "StatusStore",
]
