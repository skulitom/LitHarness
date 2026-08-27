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

from litharness.domain.budget import Spend
from litharness.domain.directives import Directive, DirectiveStatus
from litharness.domain.directors import Director
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

    Separate from `JobQueue`, which is the *claiming* contract: giving every claiming caller
    a load method would invite exactly the rebuild-at-render-time this design forbids
    (invariant I5).
    """

    def load_job(self, job_id: str) -> Job: ...


class DecisionRepository(Protocol):
    def latest_decision_for(self, job_id: str) -> PolicyDecision | None: ...

    def record_decision(self, decision: PolicyDecision, *, decided_at: str) -> bool: ...

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

    def promises(self, book_id: str, branch_id: str, *, open_only: bool = ...) -> list[Promise]: ...

    def record_promise(self, book_id: str, branch_id: str, promise: Promise) -> bool: ...

    def pay_promise(
        self,
        book_id: str,
        branch_id: str,
        promise_id: str,
        *,
        paid_at_key: str,
        paid_by_revision: str,
    ) -> bool: ...


class PayoffScheduler(Protocol):
    """Proposing when an open promise should be paid (W2, §94).

    **Split from `PromiseRepository` rather than added to it**, following `PlanReader` /
    `PlanWriter` and `StateRepository` / `StateWriter`: `PlanningStore` composes the promise
    reader with the comment "read-only; nothing on the planning path writes here", and folding
    a write into that protocol would make the comment false by construction while every caller
    stayed honest. Exactly one store composes this — the outline handler's — because exactly
    one call proposes windows.
    """

    def schedule_payoff_window(
        self,
        book_id: str,
        branch_id: str,
        promise_id: str,
        *,
        window_start_key: str,
        window_end_key: str,
        plan_revision_id: str,
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
    SummaryRepository,
    # W2: open promises go into the outline request and the windows it answers with come back
    # here. The one store that composes `PayoffScheduler`, because the one call that has the
    # whole beat sheet in view is the only one entitled to say where a debt should be paid.
    PromiseRepository,
    PayoffScheduler,
    OperationsRepository,
    Protocol,
):
    """What the outline handler reads and writes: the manuscript's beats, the plan it edits,
    the decision that attributes the edit, the ledger it schedules payment against, and the
    day's spend it is checked against."""


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
    # Read-only: the detector-input assembly hands `promise.overdue.v0` the open ledger
    # rows, the way it hands `detect_duplicate_scene` the prior prose. The draft path
    # never writes a promise — only the summary handler does.
    PromiseRepository,
    Protocol,
):
    pass


class NarrativePlanningStore(
    DirectiveInbox,
    ManuscriptReader,
    PlanReader,
    PlanWriter,
    DecisionRepository,
    # Read-only, and only for `world_brief.brief_for`. A plan statement is the sentence a
    # writer is told to execute, and until this line existed the model writing it had seen the
    # premise and the beat sheet and nothing else while the writer was handed 229 established
    # facts out of a forged world. `OutlineStore` already composes this; the two roles write
    # the same kind of sentence and had different sight of the book.
    StateRepository,
    SummaryRepository,
    Protocol,
):
    """Reads the manuscript as well as the plan, because a plan item that is *about* a scene
    has to name a scene the book actually has — and the book, not the plan, is what says
    which those are. Reads canon too, for the world the statement has to be written against."""


class PlanRefinementStore(PlanReader, PlanWriter, Protocol):
    pass


class DirectorStore(
    ManuscriptReader,
    PlanReader,
    SummaryRepository,
    PromiseRepository,
    StateRepository,
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
    PlanReader,
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
    SummaryRepository,
    PromiseRepository,
    EventRepository,
    OperationsRepository,
    ExceptionRepository,
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
    "PayoffScheduler",
    "PlanRefinementStore",
    "PlanningStore",
    "PromiseRepository",
    "RepairStore",
    "StatusStore",
    "TextGenerator",
]
