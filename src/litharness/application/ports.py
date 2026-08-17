"""Capabilities required by application workflows: persistence, and model access.

Application code coordinates storage but must not know that the current adapter is SQLite.
These structural protocols describe behavior at use-case boundaries. ``SqliteStore``
satisfies them without inheritance, leaving a future split store, in-memory harness, or
remote adapter free to implement only the capabilities a workflow actually needs.

`TextGenerator` extends the same treatment to the other side. Persistence had fifteen
protocols here while generation had a concrete `ProviderRegistry` import in three handlers,
so half the layer was inverted and half was not — and `conductor.HealthResettable` typed that
very registry structurally, which meant the direction was already agreed and applied
unevenly. `tests/test_architecture.py` now forbids `application` importing `providers` at
all, so this file is the only description of a generator the layer has.
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
from litharness.domain.events import Event
from litharness.domain.exceptions import ExceptionRecord
from litharness.domain.findings import Finding
from litharness.domain.findings import Status as FindingStatus
from litharness.domain.generation import (
    CompletionRequest,
    CompletionResult,
    Resolution,
)
from litharness.domain.jobs import Job
from litharness.domain.plan_refinement import PlanApplication, PlanRevision
from litharness.domain.policy import PolicyDecision
from litharness.domain.preference import (
    ComparisonExcerpt,
    PairSample,
    PairVerdict,
    PreferenceProtocol,
)
from litharness.domain.promises import Promise
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


class StateWriter(Protocol):
    def record_state_records(
        self,
        book_id: str,
        branch_id: str,
        records: Sequence[lc.StateRecord],
        *,
        created_at: str,
        source_revision_id: str | None = ...,
        events: Sequence[Event] = ...,
    ) -> int: ...

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


class PreferenceRepository(Protocol):
    """The pairwise preference engine's persistence (§61 Add 1).

    A sibling of `AuditRepository` rather than an extension of it, so that contract stays
    exactly what its existing implementors satisfy — a pair sample is a different thing
    with a different identity, not a second meaning for an audit method to grow.
    """

    def excerpts(self) -> list[ComparisonExcerpt]: ...

    def record_excerpt(
        self, excerpt: ComparisonExcerpt, *, events: Sequence[Event] = ...
    ) -> bool: ...

    def protocols(self) -> list[PreferenceProtocol]: ...

    def record_protocol(
        self, protocol: PreferenceProtocol, *, events: Sequence[Event] = ...
    ) -> bool: ...

    def pair_samples(self, *, pending_only: bool = ...) -> list[PairSample]: ...

    def record_pair_sample(
        self, sample: PairSample, *, events: Sequence[Event] = ...
    ) -> bool: ...

    def record_pair_verdict(
        self,
        sample_id: str,
        verdict: PairVerdict,
        *,
        at: str,
        by: str,
        recognized: bool,
        note: str | None = ...,
        events: Sequence[Event] = ...,
    ) -> bool: ...


class EventRepository(Protocol):
    def append_events(self, events: Iterable[Event]) -> None: ...


class OperationsRepository(Protocol):
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

    def bump_digest(self, day: str, metric: str, value: int = ...) -> None: ...

    def digest(self, day: str) -> dict[str, int]: ...


class ExceptionRepository(Protocol):
    def raise_exception(self, record: ExceptionRecord) -> bool: ...

    def open_exceptions(self, limit: int = ...) -> list[ExceptionRecord]: ...


class SummaryRepository(Protocol):
    """What an accepted scene contained, for the packet that can no longer hold its prose."""

    def record_scene_summary(
        self,
        book_id: str,
        branch_id: str,
        logical_id: str,
        *,
        content_hash: str,
        summary: str,
        model: str,
        profile: str,
        created_at: str,
        delta: dict[str, Any] | None = ...,
        promises: dict[str, Any] | None = ...,
    ) -> bool: ...

    def scene_summaries(self, book_id: str, branch_id: str) -> dict[str, dict[str, str]]: ...


class PromiseRepository(Protocol):
    """The promise/payoff ledger (§61 Add 2): model-sourced rows, deterministic reads.

    A sibling of `StateRepository` rather than an extension of it, for the reason the
    extraction-state map makes binding: a promise folded into THREAD records would empty
    `open_threads` (which tests `value == "open"` by exact equality), collide with the
    contradiction detector's grouping, and trip `has_story_vocabulary`'s registry check.
    A separate table with its own reader sidesteps all three.
    """

    def promises(
        self, book_id: str, branch_id: str, *, open_only: bool = ...
    ) -> list[Promise]: ...

    def record_promise(
        self, book_id: str, branch_id: str, promise: Promise
    ) -> bool: ...

    def pay_promise(
        self,
        book_id: str,
        branch_id: str,
        promise_id: str,
        *,
        paid_at_key: str,
        paid_by_revision: str,
    ) -> bool: ...


class SummaryStore(
    ManuscriptReader,
    StateRepository,
    SummaryRepository,
    # The extended summary call reports promises opened and paid; the handler maintains the
    # ledger from that answer, so the write half lives here and nowhere on the draft path.
    PromiseRepository,
    # For the zero-delta INFO annotation (`craft.scene_delta.v0`): a scene whose summary
    # reports no value shift gets a finding on the record, never a gate change.
    FindingRepository,
    Protocol,
):
    pass


class OutlineStore(
    ManuscriptReader,
    PlanReader,
    PlanWriter,
    DecisionRepository,
    StateRepository,
    StateWriter,
    OperationsRepository,
    Protocol,
):
    """What the outline handler reads and writes: the manuscript's beats, the plan it edits,
    the decision that attributes the edit, and the day's spend it is checked against."""


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
    SummaryRepository,
    # Read-only: `packet_for` surfaces open promises in the packet's THREADS section so
    # generation gets to see the ledger. Nothing on the planning path writes here.
    PromiseRepository,
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
    # The craft ladder's per-class staleness dispatch reads answered pair verdicts for
    # `EvidenceClass.PREFERENCE` rows, the same way it reads answered audit samples for
    # judgment rows. Read-only from the draft path; nothing on a tick writes here.
    PreferenceRepository,
    # Read-only: the detector-input assembly hands `promise.overdue.v0` the open ledger
    # rows, the way it hands `detect_duplicate_scene` the prior prose. The draft path
    # never writes a promise — only the summary handler does.
    PromiseRepository,
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
    # Read-only, and the reason it is here is one line of the report: a book whose canon
    # states game state on the page is one the six-rule LitRPG pack should be checking, and
    # `speaks_system_voice` reads that off the records rather than off a genre flag. The
    # writer half is a separate protocol, so status gains no ability to mutate state.
    StateRepository,
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
    PreferenceRepository,
    SummaryRepository,
    PromiseRepository,
    EventRepository,
    OperationsRepository,
    ExceptionRepository,
    Protocol,
):
    """Aggregate accepted by the composition root and pluggable work selectors."""


class Named(Protocol):
    """Anything that can say which provider it is.

    All three `resolve` call sites in `application` read `.name` and nothing else — they ask
    which provider *would* serve a call so the budget governor can price it before any work
    happens. Narrowing the return to this instead of `Provider` is what keeps the generation
    contract free of the provider vocabulary: `application` never needs `health()` or
    `complete()` on a single provider, only on the generator as a whole.
    """

    name: str


class TextGenerator(Protocol):
    """Model access as the application layer needs it. `ProviderRegistry` satisfies it.

    Three methods, because that is the entire surface `application` was using on the
    concrete registry — selection order, health caching, fallback, billing refusal and the
    test-mode guard are all `providers`' business and none of them appear here.

    `reset_health` folds in what `conductor.HealthResettable` described separately. Keeping
    two protocols for one object split the contract across two files for no gain: the loop
    resets health at the start of a tick, the handlers complete against the same object, and
    a reader had to visit both to learn what the layer required.
    """

    def resolve(self, call_class: str = "generation") -> tuple[Named, Resolution]:
        """Which provider would serve this call class, without making the call.

        Raises when none is healthy — the refusal reaches the caller before any work is
        attempted, which is why the conductor can treat it as a park rather than a failure.
        """
        ...

    def complete(self, request: CompletionRequest) -> tuple[CompletionResult, Resolution]:
        """Complete against the best healthy provider, reporting who served it.

        The `Resolution` travels with the result rather than being logged inside the
        implementation, because §5 rule 4 forbids a silent switch.
        """
        ...

    def reset_health(self) -> None:
        """Drop cached *negative* health verdicts, so an outage can heal. Called at the
        start of a tick; a positive verdict may outlive it, because the probe that bought
        it is a billed call."""
        ...


__all__ = [
    "ApplicationStore",
    "ConductorStore",
    "DraftStore",
    "EvaluationStore",
    "ExportStore",
    "JobQueue",
    "Named",
    "NarrativePlanningStore",
    "PlanRefinementStore",
    "PlanningStore",
    "PreferenceRepository",
    "PromiseRepository",
    "RepairStore",
    "StatusStore",
    "TextGenerator",
]
