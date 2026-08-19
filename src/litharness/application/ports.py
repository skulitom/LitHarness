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
from litharness.domain.candidates import CandidateStatus, SpanCandidate
from litharness.domain.craft import CraftMetric
from litharness.domain.directions import AxisDirection
from litharness.domain.directives import Directive, DirectiveStatus
from litharness.domain.directors import Director
from litharness.domain.events import Event
from litharness.domain.exceptions import ExceptionRecord
from litharness.domain.feedback import (
    DifferenceStatus,
    DiscardReason,
    JudgeDiscard,
    LocatedDifference,
    SceneFeedback,
)
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
from litharness.domain.pools import PoolRegistration
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


class JobReader(Protocol):
    """Read one queued unit by id.

    Separate from `JobQueue`, which is the *claiming* contract: selection needs to read the
    payload of the tournament job that produced its candidates — the record of what was
    actually asked, frozen at enqueue — and giving every claiming caller a load method would
    invite exactly the rebuild-at-render-time this design forbids (invariant I5).
    """

    def load_job(self, job_id: str) -> Job: ...


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


class SpanCandidateRepository(Protocol):
    """The tournament's persistence (§61 Add 3): candidate drafts awaiting selection.

    A sibling of `PreferenceRepository` rather than an extension of it, for the reason
    every repository here is a sibling: a candidate is not a pair sample and not a
    revision — it is a draft that must never reach `commit_revision`, parked in its own
    table with its own content-derived identity. `commit_tournament` is the module's one
    commit seam, mirroring `commit_revision`: everything a tournament produces — corpus
    rows, candidates, sibling samples, the follow-up job and the settlement decision —
    lands in one transaction, so a crashed handler replays into convergence instead of
    into half a tournament.
    """

    def span_candidates(
        self,
        book_id: str,
        branch_id: str,
        *,
        logical_id: str | None = ...,
        job_id: str | None = ...,
        status: CandidateStatus | None = ...,
    ) -> list[SpanCandidate]: ...

    def pending_span_candidates(self) -> list[SpanCandidate]: ...

    def set_span_candidate_status(
        self, candidate_id: str, status: CandidateStatus
    ) -> bool: ...

    def commit_tournament(
        self,
        *,
        protocol: PreferenceProtocol,
        excerpts: Sequence[ComparisonExcerpt],
        candidates: Sequence[SpanCandidate],
        samples: Sequence[PairSample],
        decision: PolicyDecision,
        decided_at: str,
        events: Sequence[Event] = ...,
        jobs: Sequence[Job] = ...,
    ) -> None: ...


class FeedbackRepository(Protocol):
    """The reader -> writer loop's persistence (`plan/reader-judge-loop.md`).

    A sibling of `PreferenceRepository` for the reason every repository here is a sibling,
    and here the separation is load-bearing rather than tidy: a **located difference is not
    a pair verdict**. §86.1 records that the human-only property of `EvidenceClass.PREFERENCE`
    was prose in an enum docstring while the judge path wrote through the same pair table, so
    the half of this design that runs at *volume* writes no PREFERENCE-shaped row at all. It
    has no laundering surface by construction rather than by filter.
    """

    def pool_registration(self) -> PoolRegistration | None: ...

    def record_pool_registration(
        self, registration: PoolRegistration, *, events: Sequence[Event] = ...
    ) -> bool: ...

    def axis_directions(self, *, axis_id: str | None = ...) -> list[AxisDirection]: ...

    def record_axis_direction(
        self, direction: AxisDirection, *, events: Sequence[Event] = ...
    ) -> bool: ...

    def located_differences(
        self,
        *,
        book_id: str | None = ...,
        branch_id: str | None = ...,
        status: DifferenceStatus | None = ...,
    ) -> list[LocatedDifference]: ...

    def record_located_differences(
        self, differences: Sequence[LocatedDifference], *, events: Sequence[Event] = ...
    ) -> int: ...

    def record_judge_discards(
        self, discards: Sequence[JudgeDiscard], *, events: Sequence[Event] = ...
    ) -> int: ...

    def judge_discards(
        self,
        *,
        book_id: str | None = ...,
        reason: DiscardReason | None = ...,
        limit: int | None = ...,
    ) -> list[JudgeDiscard]: ...

    def spend_located_difference(self, difference_id: str) -> bool: ...

    def record_scene_feedback(self, record: SceneFeedback) -> bool: ...

    def scene_feedback(self, *, revision_id: str | None = ...) -> list[SceneFeedback]: ...


class DirectorRepository(Protocol):
    """The Director role's persistence (`plan/director-role.md`).

    Admitted personalities and the directives they wrote. Separate from `DirectiveInbox`, which
    is the *drain* contract every consumer of direction already has: what a Director needs is the
    ability to write into that inbox and to count what it has already written, and widening the
    inbox protocol would hand every existing consumer a machine-authorship vocabulary it has no
    use for.
    """

    def directors(self) -> list[Director]: ...

    def director(self, director_id: str) -> Director | None: ...

    def record_director(
        self, director: Director, *, registered_at: str, events: Sequence[Event] = ...
    ) -> bool: ...

    def machine_directives(
        self, book_id: str, branch_id: str, *, live_only: bool = ...
    ) -> list[Directive]: ...

    def submit_directive(self, directive: Directive, *, received_at: str) -> bool: ...


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
    # The reader -> writer loop attaches at *enqueue*, which is why it is on the planning
    # store and not the draft store: the feedback set is materialised into the frozen
    # payload here, and a handler that rebuilt it at render time from live tables would
    # make every replay a different experiment (invariant I5). Read-only except
    # `spend_located_difference`, which is what makes a located item one-shot.
    FeedbackRepository,
    # Steering verdicts live in the pair table, and a direction's staleness is read off
    # them. Read-only from the planning path.
    PreferenceRepository,
    SpanCandidateRepository,
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
    # Write-only, and only `record_scene_feedback`: what shaped this scene is recorded
    # against the address the prose actually has, including the empty set for a scene
    # drafted with no feedback (invariant I4). The draft path never *reads* feedback —
    # it reads the frozen payload, which is the record of what was actually asked.
    FeedbackRepository,
    Protocol,
):
    pass


class PlanSearchStore(
    ManuscriptReader,
    PlanReader,
    DecisionRepository,
    FindingRepository,
    StateRepository,
    # Read-only, for the same DetectorInput assembly the draft handler uses: the ledger's
    # open rows feed `promise.overdue.v0` during candidate gating.
    PromiseRepository,
    # `calibrations` and `pair_samples`, read-only: the judge-license check is Add 1's
    # staleness wiring applied to the selection task's own calibration.
    AuditRepository,
    PreferenceRepository,
    SpanCandidateRepository,
    Protocol,
):
    """What one tournament reads and the one seam it writes through: the frozen base and
    plan it drafts against, the standing findings and spend it pre-flights on, and
    `commit_tournament` for everything it produces."""


class SpanSelectStore(
    ManuscriptReader,
    ManuscriptWriter,
    PlanReader,
    PlanWriter,
    DecisionRepository,
    FindingRepository,
    StateRepository,
    PromiseRepository,
    AuditRepository,
    PreferenceRepository,
    SpanCandidateRepository,
    # The search job's frozen payload is where the winner's feedback provenance lives.
    JobReader,
    # Write-only, and only `record_scene_feedback`: a tournament's winner is committed
    # here rather than by the draft handler, so this is where the winning scene's
    # provenance is recorded. Without it, exactly the scenes drafted under search — the
    # ones the loop actually steers — would be the scenes with no provenance row.
    FeedbackRepository,
    Protocol,
):
    """What selection reads and writes: the winner's commit through the normal accept
    path (`ManuscriptWriter`), the ONE plan acceptance (`PlanWriter`), the judge's
    verdicts through the same pair machinery, and the candidate statuses."""


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


class DirectorStore(
    ManuscriptReader,
    PlanReader,
    SummaryRepository,
    PromiseRepository,
    DirectorRepository,
    Protocol,
):
    """What one piece of direction is produced from: the book's SHAPE and never its prose.

    The absence is the interesting half of this protocol. There is no `ManuscriptWriter` here
    because a Director writes no prose, and the reader it does have is used for scene *nodes*
    and their statements — `application/director.py` never reads `node.content`. A role that
    cannot see the text cannot render a verdict on it, which turns "a Director may not evaluate
    prose" from an instruction into a property of what it was handed.
    """


class FeedbackLoopStore(FeedbackRepository, PreferenceRepository, Protocol):
    """What `application/feedback_loop.py` reads: the loop's own rows and the verdicts under
    them. Both halves are needed together and neither is enough alone — a direction is a
    *reading of pair verdicts*, so a store that had the directions and not the verdicts could
    not tell a live one from a stale one."""


class EvaluationStore(
    ManuscriptReader,
    PlanReader,
    FindingRepository,
    StateRepository,
    JobQueue,
    # Read-only: the repair-license extension (§61 Add 3, item 5) asks whether a finding
    # cites a *current* calibration before minting a repair for it, and `calibrations` is
    # the only read that answer needs.
    AuditRepository,
    Protocol,
):
    pass


class RepairStore(
    ManuscriptReader,
    ManuscriptWriter,
    FindingRepository,
    StateRepository,
    DecisionRepository,
    # Read-only, and the second enforcement of the same license the evaluation handler
    # checked at mint time: a calibration that lapsed between mint and claim must refuse
    # the repair at run time too, or the license outlives its evidence.
    AuditRepository,
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
    SpanCandidateRepository,
    SummaryRepository,
    PromiseRepository,
    EventRepository,
    OperationsRepository,
    ExceptionRepository,
    # The reader -> writer loop's rows, because work selection is where feedback is
    # materialised into the frozen payload (invariant I5) and where a located item is spent.
    FeedbackRepository,
    JobReader,
    # Work selection mints the Director's unit and enforces its bound, so it needs to see both
    # the admitted personalities and what this book's Director has already said.
    DirectorRepository,
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
    "PlanSearchStore",
    "PlanningStore",
    "PreferenceRepository",
    "PromiseRepository",
    "RepairStore",
    "SpanCandidateRepository",
    "SpanSelectStore",
    "StatusStore",
    "TextGenerator",
]
