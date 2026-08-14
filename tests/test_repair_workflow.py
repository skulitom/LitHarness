"""Stage 2: evaluation creates located work and only re-detection closes it."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.evaluation import (
    EvaluationError,
    EvaluationRequest,
    EvaluationRun,
)
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.repair import (
    EVALUATE_REVISION,
    REPAIR_FINDING,
    evaluation_job_for,
    make_evaluation_handler,
    make_repair_handler,
)
from litharness.domain.findings import Finding, Severity, Status
from litharness.domain.jobs import JobStatus
from litharness.domain.revision import node_version_id
from litharness.domain.text import content_hash
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision
from tests.test_draft import PROSE, START, seeded

RULE_ID = "character.name.rook.v0"
FINDING_ID = "f-rook-name"


class LocatedNameEvaluator:
    """A deterministic test rule whose evidence moves with the evaluated revision."""

    def evaluate(self, request: EvaluationRequest) -> EvaluationRun:
        node = request.revision.node(request.logical_id)
        text = node.content or ""
        findings: tuple[Finding, ...] = ()
        if text.startswith("Rook "):
            span = lc.EvidenceSpan(
                source=lc.ResourceRef(
                    project_id=PROJECT_ID,
                    book_id=request.revision.book_id,
                    branch_id=request.revision.branch_id,
                    logical_id=request.logical_id,
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                    version_id=node_version_id(node),
                ),
                start=0,
                end=4,
                content_sha256=content_hash(text[:4]),
            )
            findings = (
                Finding(
                    finding_id=FINDING_ID,
                    category="continuity",
                    severity=Severity.MAJOR,
                    message="The established name is Mara, not Rook.",
                    rule_or_critic_id=RULE_ID,
                    logical_id=request.logical_id,
                    confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
                    run_id=f"run-{request.revision.revision_id[:12]}",
                    source={"primary_span": lc.to_jsonable(span)},
                ),
            )
        return EvaluationRun(
            run_id=f"run-{request.revision.revision_id[:12]}",
            findings=findings,
            checked_rule_ids=(RULE_ID,),
        )


class IncompleteEvaluator:
    def __init__(self, failure: str) -> None:
        self.failure = failure

    def evaluate(self, request: EvaluationRequest) -> EvaluationRun:
        if self.failure == "error":
            return EvaluationRun(
                run_id="run-error",
                errors=(EvaluationError("rule", "detector crashed"),),
                checked_rule_ids=(RULE_ID,),
            )
        return EvaluationRun(run_id="run-missing-rule")


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "repair.db")


def _registry() -> tuple[ProviderRegistry, FakeProvider]:
    provider = FakeProvider(responses=[PROSE, '{"replacement": "Mara"}'])
    return ProviderRegistry(providers=[provider], order=["fake"]), provider


def _state_record(record_id: str, revision, logical_id: str) -> lc.StateRecord:
    node = revision.node(logical_id)
    assert node.content is not None
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.ASSERTION,
        subject=logical_id,
        predicate="test.fact",
        value=True,
        story_position=lc.StoryPosition(order_key=logical_id),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
        evidence=[
            lc.EvidenceSpan(
                source=lc.ResourceRef(
                    project_id=PROJECT_ID,
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    logical_id=logical_id,
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                    version_id=node_version_id(node),
                ),
                start=0,
                end=4,
                content_sha256=content_hash(node.content[:4]),
            )
        ],
    )


def test_accepted_draft_is_evaluated_repaired_and_verified(store: SqliteStore) -> None:
    registry, provider = _registry()
    base = seeded(store, {"book_id": BOOK_ID, "branch_id": BRANCH_ID})
    conductor = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        handlers={
            SCENE_DRAFT: make_scene_draft_handler(
                registry,
                store,
                PROJECT_ID,
                audit_rate=0,
                schedule_evaluation=True,
            ),
            EVALUATE_REVISION: make_evaluation_handler(
                LocatedNameEvaluator(), store, PROJECT_ID
            ),
            REPAIR_FINDING: make_repair_handler(registry, store, PROJECT_ID),
        },
    )

    drafted = conductor.tick(START)
    assert drafted.outcome is TickOutcome.RAN_JOB
    queued = store.jobs_by_status(JobStatus.QUEUED)
    assert [job.job_kind for job in queued] == [EVALUATE_REVISION]
    assert store.decision_for_revision(store.head(BOOK_ID, BRANCH_ID).revision_id) is not None

    evaluated = conductor.tick(START + 1)
    assert evaluated.outcome is TickOutcome.RAN_JOB
    assert store.load_finding(FINDING_ID).status is Status.OPEN
    queued = store.jobs_by_status(JobStatus.QUEUED)
    assert [job.job_kind for job in queued] == [REPAIR_FINDING]

    repaired = conductor.tick(START + 2)
    assert repaired.outcome is TickOutcome.RAN_JOB
    repaired_head = store.head(BOOK_ID, BRANCH_ID)
    assert repaired_head is not None
    assert repaired_head.parent_revision_id != base.revision_id
    assert repaired_head.node("scene-1").content == f"Mara{PROSE[4:]}"
    assert store.load_finding(FINDING_ID).status is Status.OPEN
    queued = store.jobs_by_status(JobStatus.QUEUED)
    assert [job.job_kind for job in queued] == [EVALUATE_REVISION]

    verified = conductor.tick(START + 3)
    assert verified.outcome is TickOutcome.RAN_JOB
    assert store.load_finding(FINDING_ID).status is Status.FIXED
    assert store.jobs_by_status(JobStatus.QUEUED) == []
    assert provider.calls == 2
    assert store.verify_integrity() == 3


@pytest.mark.parametrize("failure", ["error", "missing-rule"])
def test_incomplete_verification_never_marks_a_finding_fixed(
    store: SqliteStore, failure: str
) -> None:
    accepted = make_revision()
    store.commit_revision(accepted, created_at="2026-08-14T00:00:00Z")
    finding = LocatedNameEvaluator().evaluate(
        EvaluationRequest(revision=accepted, logical_id="scene-1")
    ).findings
    assert len(finding) == 1
    store.record_findings(
        BOOK_ID,
        BRANCH_ID,
        finding,
        created_at="2026-08-14T00:00:00Z",
        revision_id=accepted.revision_id,
    )
    verification = evaluation_job_for(
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        revision_id=accepted.revision_id,
        logical_id="scene-1",
        verification_of_finding_id=FINDING_ID,
    )
    store.enqueue(verification)
    conductor = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        handlers={
            EVALUATE_REVISION: make_evaluation_handler(
                IncompleteEvaluator(failure), store, PROJECT_ID
            )
        },
    )

    result = conductor.tick(START + 100)

    assert result.outcome is TickOutcome.JOB_FAILED
    assert store.load_finding(FINDING_ID).status is Status.OPEN
    assert store.load_job(verification.job_id).status is JobStatus.FAILED
    assert store.jobs_by_status(JobStatus.QUEUED) == []


def test_persistent_complaint_stays_open_without_spawning_an_unbounded_loop(
    store: SqliteStore,
) -> None:
    revision = make_revision()
    store.commit_revision(revision, created_at="2026-08-14T00:00:00Z")
    findings = LocatedNameEvaluator().evaluate(
        EvaluationRequest(revision=revision, logical_id="scene-1")
    ).findings
    store.record_findings(
        BOOK_ID,
        BRANCH_ID,
        findings,
        created_at="2026-08-14T00:00:00Z",
        revision_id=revision.revision_id,
    )
    verification = evaluation_job_for(
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        revision_id=revision.revision_id,
        logical_id="scene-1",
        verification_of_finding_id=FINDING_ID,
        repair_depth=1,
    )
    store.enqueue(verification)
    conductor = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        handlers={
            EVALUATE_REVISION: make_evaluation_handler(
                LocatedNameEvaluator(), store, PROJECT_ID
            )
        },
    )

    result = conductor.tick(START)

    assert result.outcome is TickOutcome.RAN_JOB
    assert store.load_finding(FINDING_ID).status is Status.OPEN
    assert store.jobs_by_status(JobStatus.QUEUED) == []


def test_repair_reanchors_only_state_evidenced_by_the_changed_node(
    store: SqliteStore,
) -> None:
    base = make_revision()
    scene_one = _state_record("rec-scene-1", base, "scene-1")
    scene_two = _state_record("rec-scene-2", base, "scene-2")
    store.commit_revision(
        base,
        created_at="2026-08-14T00:00:00Z",
        state_records=(scene_one, scene_two),
    )
    node = base.node("scene-1")
    assert node.content is not None
    repaired = base.replacing((node.with_content(f"{node.content}!"),))
    reanchored = _state_record("rec-scene-1", repaired, "scene-1")

    store.commit_revision(
        repaired,
        created_at="2026-08-14T00:01:00Z",
        state_records=(reanchored,),
        retract_state_for_nodes=("scene-1",),
    )

    records = {record.record_id: record for record in store.state_records(BOOK_ID, BRANCH_ID)}
    assert set(records) == {"rec-scene-1", "rec-scene-2"}
    assert records["rec-scene-1"].evidence[0].source.version_id == node_version_id(
        repaired.node("scene-1")
    )
    assert records["rec-scene-2"].evidence[0].source.version_id == node_version_id(
        base.node("scene-2")
    )
    sources = {
        row["record_id"]: row["source_revision_id"]
        for row in store._connection.execute(
            "SELECT record_id, source_revision_id FROM state_records"
        )
    }
    assert sources == {
        "rec-scene-1": repaired.revision_id,
        "rec-scene-2": base.revision_id,
    }
