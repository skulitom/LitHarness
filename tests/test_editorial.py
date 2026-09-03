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
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.domain.editorial import (
    EditorialDecision,
    QualificationEvidence,
    ReaderMechanism,
    ReaderMechanismStatus,
    mechanism_version_id_for,
)
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plan_refinement import (
    DirectiveReading,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
)
from litharness.domain.revision import build_revision
from litharness.domain.serials import SerialShape
from litharness.packs import litrpg
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import PROJECT_ID, make_revision

STAMP = "2026-08-27T12:00:00Z"
NOW = 1_777_800_000.0

#: The steering roster every mechanism below is registered over: the house's, by the name it
#: moved to (stage-0 §221). The control plane used to reach for it as a module constant; the
#: digest it computes from these readers is the digest it always computed.
ROSTER = litrpg.LITRPG.steering


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "editorial.db")


def _qualification_payload() -> dict[str, object]:
    candidate = experimental_mechanism(registered_at=STAMP, roster=ROSTER)
    return {
        "candidate_version_id": candidate.version_id,
        "mechanism_id": candidate.mechanism_id,
        "mechanism_spec_digest": candidate.spec_digest,
        "battery_registration_digest": "a" * 64,
        "battery_manifest_digest": "b" * 64,
        "registered_bar_digest": "c" * 64,
        "source_artifact_digests": ["d" * 64, "e" * 64],
        "holdout_books": 2,
        "heldout_transformations": True,
        "edit_fingerprint_passed": True,
        "memorisation_controls_passed": True,
        "full_volume_passed": True,
        "cross_volume_passed": True,
        "growing_serial_passed": True,
        "transfer_passed": True,
        "operator_acceptance_passed": True,
        "decided_at": STAMP,
    }


def _qualified() -> ReaderMechanism:
    spec = mechanism_spec_digest(ROSTER)
    evidence = QualificationEvidence.from_payload(_qualification_payload()).evidence_digest
    status = ReaderMechanismStatus.QUALIFIED
    return ReaderMechanism(
        mechanism_id="reader.anticipation.v0",
        version_id=mechanism_version_id_for("reader.anticipation.v0", status, spec, evidence),
        status=status,
        spec_digest=spec,
        evidence_digest=evidence,
        registered_at=STAMP,
    )


def _register_qualified(store: SqliteStore) -> ReaderMechanism:
    candidate = experimental_mechanism(registered_at=STAMP, roster=ROSTER)
    store.register_reader_mechanism(candidate)
    qualified = _qualified()
    store.register_reader_mechanism(qualified, evidence=_qualification_payload())
    return qualified


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
        roster=ROSTER,
    )
    handler = make_reader_observation_handler(
        ProviderRegistry(FakeProvider()), store, PROJECT_ID, roster=ROSTER
    )
    for job in jobs:
        handler(job, NOW)
    return revision, jobs


def test_the_mechanism_version_addresses_status_spec_and_evidence() -> None:
    experimental = experimental_mechanism(registered_at=STAMP, roster=ROSTER)
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


def test_qualification_requires_the_registered_current_experimental_candidate(
    store: SqliteStore,
) -> None:
    with pytest.raises(ValueError, match="candidate is not registered"):
        store.register_reader_mechanism(_qualified(), evidence=_qualification_payload())


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
    mechanism = experimental_mechanism(registered_at=STAMP, roster=ROSTER)
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
            ProviderRegistry(provider), store, PROJECT_ID, roster=ROSTER
        )(replace(jobs[0], job_id="tampered-job", payload=tampered_payload), NOW)
    assert provider.calls == 0


def test_an_experimental_panel_is_durable_but_cannot_enqueue_direction(
    store: SqliteStore,
) -> None:
    mechanism = experimental_mechanism(registered_at=STAMP, roster=ROSTER)
    store.register_reader_mechanism(mechanism)
    revision, _jobs = _record_panel(store, mechanism)

    assert store.ready_reader_panels() == []
    assert not enqueue_ready_editorial_panel(store)
    assert store.editorial_interventions(revision.book_id, revision.branch_id) == []
    assert store.pending_directives() == []


def test_withdrawing_a_qualified_mechanism_closes_queued_and_future_steering(
    store: SqliteStore,
) -> None:
    qualified = _register_qualified(store)
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
    mechanism = experimental_mechanism(registered_at=STAMP, roster=ROSTER)
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
        reader_roster=ROSTER,
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
    mechanism = _register_qualified(store)
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


def test_an_intervention_records_when_its_target_scene_is_accepted(
    store: SqliteStore,
) -> None:
    mechanism = _register_qualified(store)
    revision, _jobs = _record_panel(store, mechanism)
    future = Node(
        logical_id="scene-7",
        kind=NodeKind.SCENE,
        position_key="090",
        parent_logical_id="book",
    )
    extended = build_revision(
        revision.book_id,
        revision.branch_id,
        (*revision.nodes, future),
        parent=revision.revision_id,
    )
    store.commit_revision(extended, created_at=STAMP)
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
    assert enqueue_ready_editorial_panel(store)
    editorial_job = next(
        item
        for item in store.jobs_by_status(JobStatus.QUEUED)
        if item.job_kind == EDITORIAL_INTERPRET
    )
    controller = FakeProvider(
        responses=[
            json.dumps(
                {
                    "decision": "satisfy",
                    "need": "a consequential choice",
                    "rationale": "the panel converged on agency",
                    "directive_body": "Make the next choice visibly alter Rook's debt.",
                    "target_logical_ids": ["scene-7"],
                }
            )
        ]
    )
    make_editorial_interpret_handler(
        ProviderRegistry(controller), store, PROJECT_ID
    )(editorial_job, NOW + 10)
    [intervention] = store.editorial_interventions(revision.book_id, revision.branch_id)
    assert intervention.directive_id is not None
    base_plan = store.plan_revision(revision.book_id, revision.branch_id)
    assert base_plan is not None
    assert store.editorial_interventions_targeting(
        revision.book_id,
        revision.branch_id,
        "scene-7",
        base_plan.plan_revision_id,
    ) == []
    proposal = PlanProposal(
        base_plan_revision_id=base_plan.plan_revision_id,
        summary="Apply the qualified reader intervention",
        rationale="Give the targeted future scene the accepted story effect.",
        expected_outcome="The scene visibly changes Rook's debt.",
        edits=(
            PlanEdit(
                PlanEditAction.CREATE,
                "scene-7-reader-effect",
                lc.PlanItem(
                    logical_id="scene-7-reader-effect",
                    kind=lc.PlanKind.SCENE_PLAN,
                    text="Rook's choice visibly changes his debt.",
                    authority=lc.PlanAuthority.POSSIBLE,
                ),
            ),
        ),
        readings=(
            DirectiveReading(
                intervention.directive_id,
                "Make the choice change Rook's debt in scene 7.",
            ),
        ),
        provider="fake",
        model="fake-deterministic-v1",
        profile="narrative-planner.v0",
    )
    application = accept_plan_proposal(
        store,
        proposal,
        project_id=PROJECT_ID,
        created_at=STAMP,
    )
    plan = application.after
    payload = {
        "revision_id": extended.revision_id,
        "book_id": extended.book_id,
        "branch_id": extended.branch_id,
        "logical_id": "scene-7",
        "prompt": "Draft the targeted scene.",
        "plan_revision_id": plan.plan_revision_id,
        "selected_by": {"ordinal": 7, "of_total": 7},
    }
    draft_job = Job(
        job_id="draft-realization",
        job_kind=SCENE_DRAFT,
        payload=payload,
        input_digest=input_digest_for(payload),
    )
    make_scene_draft_handler(
        ProviderRegistry(FakeProvider(pad_to_chars=400)), store, PROJECT_ID
    )(draft_job, NOW + 20)

    [realization] = store.intervention_realizations(revision.book_id, revision.branch_id)
    assert realization.intervention_id == intervention.intervention_id
    assert realization.logical_id == "scene-7"
    assert realization.plan_revision_id == plan.plan_revision_id
