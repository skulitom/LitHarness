"""The reader control plane: versioned evidence, qualification, and plan-bound direction."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.editorial import (
    EDITORIAL_INTERPRET,
    READER_OBSERVE,
    copies_reader_language,
    enqueue_ready_editorial_panel,
    experimental_mechanism,
    make_editorial_interpret_handler,
    make_reader_observation_handler,
    mechanism_spec_digest,
    reader_jobs_for_checkpoint,
)
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.domain.editorial import (
    EditorialDecision,
    ReaderMechanism,
    ReaderMechanismStatus,
    mechanism_version_id_for,
)
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import build_revision
from litharness.domain.serials import SerialShape
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import PROJECT_ID, make_revision

STAMP = "2026-08-27T12:00:00Z"
NOW = 1_777_800_000.0


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "editorial.db")


def _qualified() -> ReaderMechanism:
    spec = mechanism_spec_digest()
    evidence = "held-out-transfer-2026-08-27"
    status = ReaderMechanismStatus.QUALIFIED
    return ReaderMechanism(
        mechanism_id="reader.anticipation.v0",
        version_id=mechanism_version_id_for("reader.anticipation.v0", status, spec, evidence),
        status=status,
        spec_digest=spec,
        evidence_digest=evidence,
        registered_at=STAMP,
    )


def _record_panel(store: SqliteStore, mechanism: ReaderMechanism, *, chapter_index: int = 2):
    revision = make_revision()
    store.commit_revision(revision, created_at=STAMP)
    jobs = reader_jobs_for_checkpoint(
        revision,
        "scene-4",
        chapter_index=chapter_index,
        summaries={},
        prior_observations=(),
        mechanism=mechanism,
        shape=SerialShape(scenes_per_chapter=2, chapters_per_arc=3),
    )
    handler = make_reader_observation_handler(ProviderRegistry(FakeProvider()), store, PROJECT_ID)
    for job in jobs:
        handler(job, NOW)
    return revision, jobs


def test_the_mechanism_version_addresses_status_spec_and_evidence() -> None:
    experimental = experimental_mechanism(registered_at=STAMP)
    qualified = _qualified()

    assert experimental.version_id != qualified.version_id
    assert not experimental.may_steer
    assert qualified.may_steer
    assert not EditorialDecision.CHALLENGE_LOCK.dispatches_direction
    assert EditorialDecision.SATISFY.dispatches_direction
    with pytest.raises(ValueError, match="evidence digest"):
        ReaderMechanism(
            mechanism_id=qualified.mechanism_id,
            version_id=mechanism_version_id_for(
                qualified.mechanism_id,
                ReaderMechanismStatus.QUALIFIED,
                qualified.spec_digest,
            ),
            status=ReaderMechanismStatus.QUALIFIED,
            spec_digest=qualified.spec_digest,
            registered_at=STAMP,
        )


def test_reader_wording_cannot_be_transcribed_into_live_direction() -> None:
    response = {
        "hoping_for": [
            "Rook opens the hidden western gate before the second dawn breaks"
        ]
    }

    assert copies_reader_language(
        "Have Rook open the hidden western gate before the second dawn breaks.",
        (response,),
    )
    assert not copies_reader_language(
        "Force a costly choice that resolves the immediate obstacle while creating a new debt.",
        (response,),
    )


def test_reader_jobs_freeze_the_request_and_record_exact_provenance(
    store: SqliteStore,
) -> None:
    mechanism = experimental_mechanism(registered_at=STAMP)
    store.register_reader_mechanism(mechanism)
    revision, jobs = _record_panel(store, mechanism)

    assert len(jobs) == 4
    assert {job.job_kind for job in jobs} == {READER_OBSERVE}
    assert all(job.payload["request"]["prompt"] for job in jobs)
    observations = store.reader_observations(revision.book_id, revision.branch_id)
    assert len(observations) == 4
    assert {item.source_job_id for item in observations} == {job.job_id for job in jobs}
    assert {item.mechanism_version_id for item in observations} == {mechanism.version_id}
    assert all(item.prompt_digest and item.schema_digest for item in observations)
    assert store.spend_on(observations[0].observed_at[:10]).invocations == 4

    tampered_payload = dict(jobs[0].payload)
    tampered_payload["reader_id"] = "somebody-else"
    provider = FakeProvider()
    with pytest.raises(ValueError, match="input digest"):
        make_reader_observation_handler(
            ProviderRegistry(provider), store, PROJECT_ID
        )(replace(jobs[0], job_id="tampered-job", payload=tampered_payload), NOW)
    assert provider.calls == 0


def test_an_experimental_panel_is_durable_but_cannot_enqueue_direction(
    store: SqliteStore,
) -> None:
    mechanism = experimental_mechanism(registered_at=STAMP)
    store.register_reader_mechanism(mechanism)
    revision, _jobs = _record_panel(store, mechanism)

    assert store.ready_reader_panels() == []
    assert not enqueue_ready_editorial_panel(store)
    assert store.editorial_interventions(revision.book_id, revision.branch_id) == []
    assert store.pending_directives() == []


def test_withdrawing_a_qualified_mechanism_closes_queued_and_future_steering(
    store: SqliteStore,
) -> None:
    qualified = _qualified()
    store.register_reader_mechanism(qualified)
    revision = make_revision()
    store.commit_revision(revision, created_at=STAMP)
    store.record_plan_items(
        revision.book_id,
        revision.branch_id,
        (
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text="Rook must clear his debt.",
                authority=lc.PlanAuthority.INTENDED,
            ),
        ),
        created_at=STAMP,
    )
    _record_panel(store, qualified)
    assert enqueue_ready_editorial_panel(store)
    job = next(
        item
        for item in store.jobs_by_status(JobStatus.QUEUED)
        if item.job_kind == EDITORIAL_INTERPRET
    )

    withdrawn = ReaderMechanism(
        mechanism_id=qualified.mechanism_id,
        version_id=mechanism_version_id_for(
            qualified.mechanism_id,
            ReaderMechanismStatus.WITHDRAWN,
            qualified.spec_digest,
        ),
        status=ReaderMechanismStatus.WITHDRAWN,
        spec_digest=qualified.spec_digest,
        registered_at="2026-08-27T13:00:00Z",
    )
    store.register_reader_mechanism(withdrawn)
    provider = FakeProvider()

    assert store.ready_reader_panels() == []
    with pytest.raises(ValueError, match="current qualified version"):
        make_editorial_interpret_handler(
            ProviderRegistry(provider), store, PROJECT_ID
        )(job, NOW + 10)
    assert provider.calls == 0
    assert store.editorial_interventions(revision.book_id, revision.branch_id) == []


def test_accepting_the_last_scene_of_a_chapter_atomically_schedules_the_panel(
    store: SqliteStore,
) -> None:
    mechanism = experimental_mechanism(registered_at=STAMP)
    store.register_reader_mechanism(mechanism)
    base = build_revision(
        "book-checkpoint",
        "main",
        (
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node.text_node(
                "scene-1", NodeKind.SCENE, "020", "Aster found the stair.", parent_logical_id="book"
            ),
            Node.text_node(
                "scene-2", NodeKind.SCENE, "030", "Aster paid the toll.", parent_logical_id="book"
            ),
            Node.text_node(
                "scene-3",
                NodeKind.SCENE,
                "040",
                "Aster crossed the gate.",
                parent_logical_id="book",
            ),
            Node(
                logical_id="scene-4",
                kind=NodeKind.SCENE,
                position_key="050",
                parent_logical_id="book",
            ),
        ),
    )
    store.commit_revision(base, created_at=STAMP)
    prose = (
        "Aster put one hand against the final door and felt the debt-mark answer. "
        "The corridor behind her filled with the measured tread of the collectors, while "
        "the lock offered one impossible bargain after another. She named the promise she "
        "had kept, not the power she wanted, and the hinges opened on a room full of dawn. "
    ) * 3
    payload = {
        "revision_id": base.revision_id,
        "book_id": base.book_id,
        "branch_id": base.branch_id,
        "logical_id": "scene-4",
        "prompt": "Draft the end of chapter two.",
        "selected_by": {
            "ordinal": 4,
            "of_total": 6,
            "chapter_index": 2,
            "chapter_scene_index": 2,
            "chapter_scenes": 2,
            "chapter_end": True,
        },
    }
    job = Job(
        job_id="draft-checkpoint",
        job_kind=SCENE_DRAFT,
        payload=payload,
        input_digest=input_digest_for(payload),
    )
    provider = FakeProvider(responses=[prose])
    make_scene_draft_handler(
        ProviderRegistry(provider),
        store,
        PROJECT_ID,
        reader_mechanism=mechanism,
        reader_shape=SerialShape(scenes_per_chapter=2, chapters_per_arc=3),
    )(job, NOW)

    queued = store.jobs_by_status(JobStatus.QUEUED)
    assert len(queued) == 4
    assert {item.job_kind for item in queued} == {READER_OBSERVE}
    assert {item.payload["checkpoint_id"] for item in queued} == {
        queued[0].payload["checkpoint_id"]
    }


def test_a_qualified_panel_becomes_an_intervention_then_a_machine_directive(
    store: SqliteStore,
) -> None:
    mechanism = _qualified()
    store.register_reader_mechanism(mechanism)
    revision = make_revision()
    store.commit_revision(revision, created_at=STAMP)
    store.record_plan_items(
        revision.book_id,
        revision.branch_id,
        (
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text="Rook must clear his debt without becoming the System's collector.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            ),
            lc.PlanItem(
                logical_id="author-lock",
                kind=lc.PlanKind.CONSTRAINT,
                text="Rook never knowingly harms a debtor.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            ),
        ),
        created_at=STAMP,
    )
    _revision, _jobs = _record_panel(store, mechanism)

    assert enqueue_ready_editorial_panel(store)
    queued = store.jobs_by_status(status=JobStatus.QUEUED)
    job = next(item for item in queued if item.job_kind == EDITORIAL_INTERPRET)
    frozen = json.dumps(job.payload["request"], sort_keys=True)
    assert "Rook never knowingly harms a debtor" in frozen
    assert "reader_observations" in frozen

    provider = FakeProvider()
    handler = make_editorial_interpret_handler(ProviderRegistry(provider), store, PROJECT_ID)
    handler(job, NOW + 10)

    interventions = store.editorial_interventions(revision.book_id, revision.branch_id)
    assert len(interventions) == 1
    intervention = interventions[0]
    assert intervention.directive_id is not None
    assert len(intervention.evidence_observation_ids) == 4
    directive = store.load_directive(intervention.directive_id)
    assert directive.author and directive.author.startswith("director:reader-controller:")
    assert directive.metadata["evidence_digest"] == intervention.evidence_digest
    assert not directive.target_logical_ids
    assert store.pending_directives() == [directive]

    handler(job, NOW + 20)
    assert provider.calls == 1
    assert store.pending_directives() == [directive]
