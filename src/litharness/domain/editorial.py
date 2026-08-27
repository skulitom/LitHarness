"""Durable reader evidence and the editorial decisions made from it.

Reader observations are evidence, not instructions.  A qualified mechanism may turn a
complete panel into an editorial intervention; only an intervention that elects to act is
allowed to enter the existing directive and immutable-plan path.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from litharness.domain.events import payload_digest


class ReaderMechanismStatus(enum.StrEnum):
    EXPERIMENTAL = "experimental"
    QUALIFIED = "qualified"
    WITHDRAWN = "withdrawn"


class EditorialDecision(enum.StrEnum):
    SATISFY = "satisfy"
    DEFER = "defer"
    SUBVERT = "subvert"
    REFUSE = "refuse"
    CHALLENGE_LOCK = "challenge_lock"

    @property
    def dispatches_direction(self) -> bool:
        return self in {EditorialDecision.SATISFY, EditorialDecision.SUBVERT}


_QUALIFICATION_FIELDS = frozenset(
    {
        "candidate_version_id",
        "mechanism_id",
        "mechanism_spec_digest",
        "battery_registration_digest",
        "battery_manifest_digest",
        "registered_bar_digest",
        "source_artifact_digests",
        "holdout_books",
        "heldout_transformations",
        "edit_fingerprint_passed",
        "memorisation_controls_passed",
        "full_volume_passed",
        "cross_volume_passed",
        "growing_serial_passed",
        "transfer_passed",
        "operator_acceptance_passed",
        "decided_at",
    }
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    """The complete, digest-addressed evidence required to let one mechanism steer.

    This object verifies the *shape and declared outcomes* of a reviewed experiment. It does
    not infer those outcomes from prose or manufacture a bar. The source artifacts and the
    separately registered bar remain the auditable ground truth.
    """

    candidate_version_id: str
    mechanism_id: str
    mechanism_spec_digest: str
    battery_registration_digest: str
    battery_manifest_digest: str
    registered_bar_digest: str
    source_artifact_digests: tuple[str, ...]
    holdout_books: int
    heldout_transformations: bool
    edit_fingerprint_passed: bool
    memorisation_controls_passed: bool
    full_volume_passed: bool
    cross_volume_passed: bool
    growing_serial_passed: bool
    transfer_passed: bool
    operator_acceptance_passed: bool
    decided_at: str

    def __post_init__(self) -> None:
        for name in (
            "candidate_version_id",
            "mechanism_id",
            "mechanism_spec_digest",
            "battery_registration_digest",
            "battery_manifest_digest",
            "registered_bar_digest",
            "decided_at",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"qualification evidence requires {name}")
        for name in (
            "mechanism_spec_digest",
            "battery_registration_digest",
            "battery_manifest_digest",
            "registered_bar_digest",
        ):
            if _SHA256.fullmatch(str(getattr(self, name))) is None:
                raise ValueError(f"qualification evidence {name} must be a SHA-256 digest")
        if self.holdout_books < 2:
            raise ValueError("qualification evidence needs at least two held-out books")
        if not self.source_artifact_digests or any(
            _SHA256.fullmatch(digest) is None for digest in self.source_artifact_digests
        ):
            raise ValueError("qualification evidence needs SHA-256 source artifact digests")
        checks = (
            self.heldout_transformations,
            self.edit_fingerprint_passed,
            self.memorisation_controls_passed,
            self.full_volume_passed,
            self.cross_volume_passed,
            self.growing_serial_passed,
            self.transfer_passed,
            self.operator_acceptance_passed,
        )
        if not all(checks):
            raise ValueError("every registered qualification control must have passed")

    def to_payload(self) -> dict[str, Any]:
        return {
            "candidate_version_id": self.candidate_version_id,
            "mechanism_id": self.mechanism_id,
            "mechanism_spec_digest": self.mechanism_spec_digest,
            "battery_registration_digest": self.battery_registration_digest,
            "battery_manifest_digest": self.battery_manifest_digest,
            "registered_bar_digest": self.registered_bar_digest,
            "source_artifact_digests": list(self.source_artifact_digests),
            "holdout_books": self.holdout_books,
            "heldout_transformations": self.heldout_transformations,
            "edit_fingerprint_passed": self.edit_fingerprint_passed,
            "memorisation_controls_passed": self.memorisation_controls_passed,
            "full_volume_passed": self.full_volume_passed,
            "cross_volume_passed": self.cross_volume_passed,
            "growing_serial_passed": self.growing_serial_passed,
            "transfer_passed": self.transfer_passed,
            "operator_acceptance_passed": self.operator_acceptance_passed,
            "decided_at": self.decided_at,
        }

    @property
    def evidence_digest(self) -> str:
        return payload_digest(self.to_payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> QualificationEvidence:
        if set(payload) != _QUALIFICATION_FIELDS:
            raise ValueError("qualification evidence has missing or unregistered fields")
        digests = payload["source_artifact_digests"]
        if not isinstance(digests, list) or not all(isinstance(item, str) for item in digests):
            raise ValueError("source_artifact_digests must be a list of strings")
        boolean_fields = _QUALIFICATION_FIELDS - {
            "candidate_version_id",
            "mechanism_id",
            "mechanism_spec_digest",
            "battery_registration_digest",
            "battery_manifest_digest",
            "registered_bar_digest",
            "source_artifact_digests",
            "holdout_books",
            "decided_at",
        }
        if any(type(payload[name]) is not bool for name in boolean_fields):
            raise ValueError("qualification control results must be booleans")
        holdout_books = payload["holdout_books"]
        if not isinstance(holdout_books, int) or isinstance(holdout_books, bool):
            raise ValueError("holdout_books must be an integer")
        return cls(
            candidate_version_id=str(payload["candidate_version_id"]),
            mechanism_id=str(payload["mechanism_id"]),
            mechanism_spec_digest=str(payload["mechanism_spec_digest"]),
            battery_registration_digest=str(payload["battery_registration_digest"]),
            battery_manifest_digest=str(payload["battery_manifest_digest"]),
            registered_bar_digest=str(payload["registered_bar_digest"]),
            source_artifact_digests=tuple(digests),
            holdout_books=holdout_books,
            heldout_transformations=payload["heldout_transformations"],
            edit_fingerprint_passed=payload["edit_fingerprint_passed"],
            memorisation_controls_passed=payload["memorisation_controls_passed"],
            full_volume_passed=payload["full_volume_passed"],
            cross_volume_passed=payload["cross_volume_passed"],
            growing_serial_passed=payload["growing_serial_passed"],
            transfer_passed=payload["transfer_passed"],
            operator_acceptance_passed=payload["operator_acceptance_passed"],
            decided_at=str(payload["decided_at"]),
        )

    def validate_for(self, mechanism_id: str, spec_digest: str) -> None:
        if (self.mechanism_id, self.mechanism_spec_digest) != (mechanism_id, spec_digest):
            raise ValueError("qualification evidence addresses another mechanism specification")


def mechanism_version_id_for(
    mechanism_id: str,
    status: ReaderMechanismStatus,
    spec_digest: str,
    evidence_digest: str | None = None,
) -> str:
    digest = payload_digest(
        {
            "mechanism_id": mechanism_id,
            "status": status.value,
            "spec_digest": spec_digest,
            "evidence_digest": evidence_digest,
        }
    )
    return f"rmech-{sha256(digest.encode()).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class ReaderMechanism:
    mechanism_id: str
    version_id: str
    status: ReaderMechanismStatus
    spec_digest: str
    registered_at: str
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.mechanism_id.strip() or not self.spec_digest.strip():
            raise ValueError("a reader mechanism needs an id and a specification digest")
        expected = mechanism_version_id_for(
            self.mechanism_id, self.status, self.spec_digest, self.evidence_digest
        )
        if self.version_id != expected:
            raise ValueError(f"mechanism version {self.version_id} does not address this record")
        if self.status is ReaderMechanismStatus.QUALIFIED and not self.evidence_digest:
            raise ValueError("a qualified reader mechanism needs an evidence digest")

    @property
    def may_steer(self) -> bool:
        return self.status is ReaderMechanismStatus.QUALIFIED


def observation_id_for(source_job_id: str) -> str:
    return f"robs-{sha256(source_job_id.encode()).hexdigest()[:24]}"


def evidence_digest_for(observation_ids: tuple[str, ...]) -> str:
    return payload_digest({"observation_ids": sorted(observation_ids)})


@dataclass(frozen=True, slots=True)
class ReaderObservation:
    observation_id: str
    source_job_id: str
    checkpoint_id: str
    mechanism_version_id: str
    book_id: str
    branch_id: str
    revision_id: str
    logical_id: str
    reader_id: str
    pool: str
    panel_size: int
    source_content_hash: str
    persona_digest: str
    prompt_digest: str
    system_digest: str
    schema_digest: str
    context_digest: str
    profile: str
    provider: str
    model: str
    response: dict[str, Any]
    observed_at: str

    def __post_init__(self) -> None:
        if self.observation_id != observation_id_for(self.source_job_id):
            raise ValueError(f"observation {self.observation_id} does not address its job")
        if self.panel_size < 1:
            raise ValueError("reader panel size must be positive")
        for name in (
            "checkpoint_id",
            "mechanism_version_id",
            "book_id",
            "branch_id",
            "revision_id",
            "logical_id",
            "reader_id",
            "pool",
            "source_content_hash",
            "persona_digest",
            "prompt_digest",
            "system_digest",
            "schema_digest",
            "context_digest",
            "profile",
            "provider",
            "model",
            "observed_at",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"reader observation requires {name}")


def intervention_id_for(controller_job_id: str, evidence_digest: str) -> str:
    material = payload_digest(
        {"controller_job_id": controller_job_id, "evidence_digest": evidence_digest}
    )
    return f"edit-{sha256(material.encode()).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class EditorialIntervention:
    intervention_id: str
    controller_job_id: str
    checkpoint_id: str
    mechanism_version_id: str
    book_id: str
    branch_id: str
    source_revision_id: str
    source_logical_id: str
    decision: EditorialDecision
    need: str
    rationale: str
    evidence_observation_ids: tuple[str, ...]
    evidence_digest: str
    target_logical_ids: tuple[str, ...] = ()
    directive_id: str | None = None
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        expected_evidence = evidence_digest_for(self.evidence_observation_ids)
        if self.evidence_digest != expected_evidence:
            raise ValueError("editorial intervention evidence digest does not match its rows")
        expected_id = intervention_id_for(self.controller_job_id, self.evidence_digest)
        if self.intervention_id != expected_id:
            raise ValueError(f"intervention {self.intervention_id} does not address this record")
        if not self.need.strip() or not self.rationale.strip():
            raise ValueError("an editorial intervention needs a need and a rationale")
        if self.decision.dispatches_direction != bool(self.directive_id):
            raise ValueError("only satisfy/subvert interventions may dispatch a directive")


def realization_id_for(intervention_id: str, revision_id: str, logical_id: str) -> str:
    digest = payload_digest(
        {
            "intervention_id": intervention_id,
            "revision_id": revision_id,
            "logical_id": logical_id,
        }
    )
    return f"ereal-{sha256(digest.encode()).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class InterventionRealization:
    """A target scene accepted under a plan produced by an editorial intervention."""

    realization_id: str
    intervention_id: str
    directive_id: str
    plan_revision_id: str
    book_id: str
    branch_id: str
    logical_id: str
    revision_id: str
    content_hash: str
    recorded_at: str

    def __post_init__(self) -> None:
        expected = realization_id_for(self.intervention_id, self.revision_id, self.logical_id)
        if self.realization_id != expected:
            raise ValueError("intervention realization does not address its accepted scene")
        for name in (
            "intervention_id",
            "directive_id",
            "plan_revision_id",
            "book_id",
            "branch_id",
            "logical_id",
            "revision_id",
            "content_hash",
            "recorded_at",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"intervention realization requires {name}")


__all__ = [
    "EditorialDecision",
    "EditorialIntervention",
    "InterventionRealization",
    "QualificationEvidence",
    "ReaderMechanism",
    "ReaderMechanismStatus",
    "ReaderObservation",
    "evidence_digest_for",
    "intervention_id_for",
    "mechanism_version_id_for",
    "observation_id_for",
    "realization_id_for",
]
