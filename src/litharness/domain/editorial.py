"""Durable reader evidence and the editorial decisions made from it.

Reader observations are evidence, not instructions.  A qualified mechanism may turn a
complete panel into an editorial intervention; only an intervention that elects to act is
allowed to enter the existing directive and immutable-plan path.
"""

from __future__ import annotations

import enum
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


__all__ = [
    "EditorialDecision",
    "EditorialIntervention",
    "ReaderMechanism",
    "ReaderMechanismStatus",
    "ReaderObservation",
    "evidence_digest_for",
    "intervention_id_for",
    "mechanism_version_id_for",
    "observation_id_for",
]
