"""Stage 2: evaluation creates located work and only re-detection closes it."""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import fixture_manuscript, fixture_state
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
    EVALUATION_PRIORITY,
    MAX_AUTO_REPAIRS,
    REPAIR_FINDING,
    evaluation_job_for,
    make_evaluation_handler,
    make_repair_handler,
    repair_job_for,
)
from litharness.domain.events import EventType
from litharness.domain.findings import Finding, Severity, Status
from litharness.domain.jobs import JobStatus
from litharness.domain.revision import import_manuscript, node_version_id
from litharness.domain.state import import_state
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
    return ProviderRegistry(provider), provider


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


# --- severity reaches the queue -------------------------------------------------------


def _located(finding_id: str, severity: Severity, revision) -> Finding:
    node = revision.node("scene-1")
    text = node.content or ""
    span = lc.EvidenceSpan(
        source=lc.ResourceRef(
            project_id=PROJECT_ID,
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            logical_id="scene-1",
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            version_id=node_version_id(node),
        ),
        start=0,
        end=4,
        content_sha256=content_hash(text[:4]),
    )
    return Finding(
        finding_id=finding_id,
        category="continuity",
        severity=severity,
        message=f"a {severity.value} complaint",
        rule_or_critic_id=f"rule.{severity.value}.v0",
        logical_id="scene-1",
        confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
        run_id="run-severity",
        source={"primary_span": lc.to_jsonable(span)},
    )


def test_the_worse_complaint_is_claimed_first_however_it_was_queued(
    store: SqliteStore,
) -> None:
    """§4.1 asks for "findings to repair (severity-ordered)" by name, and severity reached the
    queue and stopped there: every repair was minted at one constant priority, so a critical
    complaint waited behind a minor one that happened to be enqueued first.

    Enqueued worst-last on purpose — insertion order and severity order disagree here, which
    is the only arrangement that can tell them apart.
    """
    revision = make_revision()
    store.commit_revision(revision, created_at="2026-08-14T00:00:00Z")
    # MAJOR and CRITICAL, because `repair_job_for` mints nothing for a finding that does
    # not block — a minor complaint annotates and is never repaired automatically.
    for finding_id, severity in (
        ("f-major", Severity.MAJOR),
        ("f-critical", Severity.CRITICAL),
    ):
        finding = _located(finding_id, severity, revision)
        store.record_findings(
            BOOK_ID,
            BRANCH_ID,
            (finding,),
            created_at="2026-08-14T00:00:00Z",
            revision_id=revision.revision_id,
        )
        job = repair_job_for(
            finding,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            revision_id=revision.revision_id,
            repair_depth=1,
        )
        assert job is not None
        store.enqueue(job)

    claimed = store.claim_next("worker-a", now=START, duration=300.0)

    assert claimed is not None
    assert claimed.payload["finding_id"] == "f-critical"


def test_a_repair_still_outranks_every_evaluation(store: SqliteStore) -> None:
    """Severity rides on top of the band rather than replacing it. The lowest repairable
    complaint must not fall below an evaluation, or the ladder's two stages interleave."""
    revision = make_revision()
    lowest = repair_job_for(
        _located("f-major", Severity.MAJOR, revision),
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        revision_id=revision.revision_id,
        repair_depth=1,
    )
    assert lowest is not None
    assert lowest.priority > EVALUATION_PRIORITY


# --- a repair that changes a fact reaches the scenes that state it --------------------


def _litrpg(store: SqliteStore):
    """The litrpg fixture, prose intact, with the state records that place its scenes.

    Real material rather than a constructed book, because the property under test is that
    extraction, the change producer and the propagation rules agree about a *ledger* — and a
    two-scene fixture would let all three agree about nothing.
    """
    source = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript("litrpg").read_text(encoding="utf-8")),
    )
    revision = import_manuscript(source, preserve_content=True).revision
    snapshot = lc.parse_artifact(
        lc.StateSnapshot, json.loads(fixture_state("litrpg").read_text(encoding="utf-8"))
    )
    imported = import_state(snapshot, book_id=revision.book_id, branch_id=revision.branch_id)
    store.commit_revision(revision, created_at="2026-08-14T00:00:00Z")
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        imported.records,
        created_at="2026-08-14T00:00:00Z",
    )
    return revision


def _finding_over(revision, quote: str, logical_id: str = "scene-2") -> Finding:
    """A located complaint spanning `quote` in that scene, which one repair may replace."""
    node = revision.node(logical_id)
    text = node.content or ""
    start = text.index(quote)
    end = start + len(quote)
    span = lc.EvidenceSpan(
        source=lc.ResourceRef(
            project_id=PROJECT_ID,
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            logical_id=logical_id,
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            version_id=node_version_id(node),
        ),
        start=start,
        end=end,
        content_sha256=content_hash(text[start:end]),
    )
    return Finding(
        finding_id="f-gold-ledger",
        category="continuity",
        severity=Severity.MAJOR,
        message="The balance after the lantern should be 33.",
        rule_or_critic_id="ledger.balance.v0",
        logical_id=logical_id,
        confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
        run_id="run-ledger",
        source={"primary_span": lc.to_jsonable(span)},
    )


def _repair_tick(
    store: SqliteStore,
    revision,
    quote: str,
    replacement: str,
    *,
    repair_depth: int = 1,
):
    """One repair through the real handler. Depth starts at 1: a repair is always spawned by
    an evaluation, and `make_repair_handler` refuses a job claiming otherwise."""
    finding = _finding_over(revision, quote)
    store.record_findings(
        revision.book_id,
        revision.branch_id,
        (finding,),
        created_at="2026-08-14T00:00:00Z",
        revision_id=revision.revision_id,
    )
    provider = FakeProvider(responses=[json.dumps({"replacement": replacement})])
    registry = ProviderRegistry(provider)
    job = repair_job_for(
        finding,
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        revision_id=revision.revision_id,
        repair_depth=repair_depth,
    )
    assert job is not None
    store.enqueue(job)
    conductor = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        handlers={REPAIR_FINDING: make_repair_handler(registry, store, PROJECT_ID)},
    )
    return conductor.tick(START)


def test_a_repair_that_changes_a_fact_re_evaluates_the_scenes_that_state_it(
    store: SqliteStore,
) -> None:
    """The loop §17 Stage 2 names, and the defect it closes: the evaluation a repair schedules
    re-checks the repaired node and *only* that one, so correcting the lantern's price in
    scene 2 left four downstream balances wrong while every gate reported the book clean.

    Nothing here is guessed. Extraction says what the repaired prose now asserts, the producer
    reads the difference against the canon being retracted, and the rules carry it forward.
    """
    revision = _litrpg(store)

    assert _repair_tick(store, revision, "Gold 25", "Gold 33").outcome is TickOutcome.RAN_JOB

    queued = {
        str(job.payload["logical_id"]): job for job in store.jobs_by_status(JobStatus.QUEUED)
    }
    assert set(queued) == {"scene-2", "scene-3", "scene-4", "scene-5", "scene-6"}
    # scene-2 is the verification of the repair itself; the rest are what the change reached.
    assert queued["scene-2"].payload.get("verification_of_finding_id") == "f-gold-ledger"
    assert all(
        queued[name].payload.get("verification_of_finding_id") is None
        for name in ("scene-3", "scene-4", "scene-5", "scene-6")
    )
    assert queued["scene-3"].payload["repair_depth"] == 2


def test_the_propagated_work_is_recorded_as_an_analysis(store: SqliteStore) -> None:
    """In the acceptance's own transaction. Work an operator did not ask for and cannot see a
    reason for is the shape §19's audit clause refuses — and the reached set is recorded
    beside the enqueued set, so a cap that bit is visible instead of reading as coverage."""
    revision = _litrpg(store)

    _repair_tick(store, revision, "Gold 25", "Gold 33")

    [analysed] = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.IMPACT_ANALYZED
    ]
    assert analysed.payload["logical_id"] == "scene-2"
    assert analysed.payload["reached"] == ["scene-3", "scene-4", "scene-5", "scene-6"]
    assert analysed.payload["enqueued"] == analysed.payload["reached"]


def test_a_repair_that_changes_no_fact_propagates_nothing(store: SqliteStore) -> None:
    """The control, and the one that keeps this affordable. A repair rewording a sentence must
    not queue a re-check of the book: most repairs change no fact at all, and an engine firing
    on every acceptance would multiply the cost of every repair by the length of the book."""
    revision = _litrpg(store)

    assert (
        _repair_tick(store, revision, "barrelhead", "counter").outcome
        is TickOutcome.RAN_JOB
    )

    queued = [str(job.payload["logical_id"]) for job in store.jobs_by_status(JobStatus.QUEUED)]
    assert queued == ["scene-2"], "only the repair's own verification"
    assert not [
        entry
        for entry in store.read_log()
        if entry.event.event_type is EventType.IMPACT_ANALYZED
    ]


def test_propagation_stops_at_the_repair_depth_that_bounds_the_chain(
    store: SqliteStore,
) -> None:
    """§4.2: the failure mode is a parked unit, never a spin loop. A propagated evaluation
    costs a depth level, so repair-propagate-repair terminates rather than walking the book —
    and at the last depth it queues nothing rather than minting jobs the evaluation handler
    would refuse for an out-of-range depth."""
    revision = _litrpg(store)

    _repair_tick(store, revision, "Gold 25", "Gold 33", repair_depth=MAX_AUTO_REPAIRS)

    queued = [str(job.payload["logical_id"]) for job in store.jobs_by_status(JobStatus.QUEUED)]
    assert queued == ["scene-2"]
