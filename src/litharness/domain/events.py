"""The event log.

**Events are written in the same transaction as the state change they describe.** If a
revision is accepted, the `ManuscriptRevisionAccepted` event is committed atomically with
it. Anything else loses events on a crash between the two writes, and a lost event means
derived state can never be rebuilt (§19's recovery clause).

`idempotency_key` is derived from the event's own identity rather than randomly, so a
retry of the *same* logical event produces the same key and collapses on insert.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

import litharness_contracts as lc


class EventType(enum.StrEnum):
    """The contract's named types, restated so this package does not depend on the
    contract's enum ordering.

    The Conductor block was previously absent from the contract, and this module was the
    consumer that showed which members were actually needed. Contracts 1.1.0 added them
    (PLAN.md §20.3), so this enum now mirrors rather than anticipates — and
    `test_every_event_type_exists_in_the_contract` pins the two together, because
    `to_contract` calls `lc.EventType(self.value)` and a member missing upstream fails at
    insert time rather than at import."""

    PLAN_CHANGED = "PlanChanged"
    MANUSCRIPT_CANDIDATE_CREATED = "ManuscriptCandidateCreated"
    MANUSCRIPT_REVISION_ACCEPTED = "ManuscriptRevisionAccepted"
    STATE_CANDIDATES_EXTRACTED = "StateCandidatesExtracted"
    STATE_RECORDS_ACCEPTED = "StateRecordsAccepted"
    CONTEXT_PACKET_CREATED = "ContextPacketCreated"
    EVALUATION_COMPLETED = "EvaluationCompleted"
    FINDING_STATUS_CHANGED = "FindingStatusChanged"
    IMPACT_ANALYZED = "ImpactAnalyzed"
    RECOMPUTED = "ArtifactRecomputed"
    INVALIDATED = "ArtifactInvalidated"
    REVISION_PLAN_APPROVED = "RevisionPlanApproved"
    EXPORT_CREATED = "ExportCreated"
    JOB_FAILED = "JobFailed"

    # -- Conductor events, available as of contracts 1.1.0 (§4.1-4.3) -----------------
    TICK_COMPLETED = "TickCompleted"
    DIRECTIVE_INGESTED = "DirectiveIngested"
    POLICY_DECISION_RECORDED = "PolicyDecisionRecorded"
    EXCEPTION_RAISED = "ExceptionRaised"
    EXCEPTION_RESOLVED = "ExceptionResolved"
    DIGEST_PUBLISHED = "DigestPublished"
    PROVIDER_FELL_BACK = "ProviderFellBack"
    BUDGET_EXHAUSTED = "BudgetExhausted"

    def to_contract(self) -> lc.EventType:
        return lc.EventType(self.value)


def payload_digest(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(rendered.encode("utf-8")).hexdigest()


def derive_idempotency_key(
    event_type: EventType, *, revision_id: str | None, payload: dict[str, Any]
) -> str:
    """Content-derived, so replaying the same logical event collapses on insert."""
    return payload_digest(
        {"type": event_type.value, "revision_id": revision_id, "payload": payload}
    )


@dataclass(frozen=True, slots=True)
class Event:
    event_type: EventType
    project_id: str
    created_at: str
    actor: str = "litharness"
    book_id: str | None = None
    branch_id: str | None = None
    revision_id: str | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def idempotency_key(self) -> str:
        return derive_idempotency_key(
            self.event_type, revision_id=self.revision_id, payload=self.payload
        )

    @property
    def event_id(self) -> str:
        return f"evt-{self.idempotency_key[:24]}"

    def to_contract(self) -> lc.EventEnvelope:
        return lc.EventEnvelope(
            schema_version="1.0.0",
            event_id=self.event_id,
            event_type=self.event_type.to_contract(),
            created_at=self.created_at,
            actor=self.actor,
            project_id=self.project_id,
            idempotency_key=self.idempotency_key,
            book_id=self.book_id,
            branch_id=self.branch_id,
            revision_id=self.revision_id,
            causation_id=self.causation_id,
            correlation_id=self.correlation_id,
            payload=dict(self.payload),
            payload_digest=payload_digest(self.payload),
        )
