"""One canonical event shape for recorded policy decisions.

Policy decisions are emitted by drafting, plan refinement, and pre-flight refusal paths.
Keeping their envelope construction in each handler made fields drift: some events carried
``attempt`` and ``gates`` while others omitted them, even though they represented the same
artifact. This module is deliberately small and pure so every producer shares one audit
shape without sharing handler logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from litharness.domain.events import Event, EventType
from litharness.domain.policy import PolicyDecision

_RESERVED_PAYLOAD_KEYS = frozenset(
    {"decision_id", "job_id", "outcome", "attempt", "reason", "gates"}
)


def policy_decision_event(
    decision: PolicyDecision,
    *,
    project_id: str,
    created_at: str,
    actor: str = "litharness",
    book_id: str | None = None,
    branch_id: str | None = None,
    revision_id: str | None = None,
    causation_id: str | None = None,
    correlation_id: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> Event:
    """Project a decision into the stable event-log representation.

    Callers may attach domain-specific details, but cannot replace the canonical fields.
    That turns accidental payload drift into an immediate error instead of an audit query
    that works for one producer and silently misses another.
    """
    extra = dict(details or {})
    overlap = sorted(_RESERVED_PAYLOAD_KEYS & extra.keys())
    if overlap:
        raise ValueError(f"policy event details replace reserved fields: {overlap}")
    payload: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "job_id": decision.job_id,
        "outcome": decision.outcome.value,
        "attempt": decision.attempt,
        "reason": decision.reason,
        "gates": [
            {"id": gate.rule_or_critic_id, "passed": gate.passed}
            for gate in decision.gates
        ],
        **extra,
    }
    return Event(
        event_type=EventType.POLICY_DECISION_RECORDED,
        project_id=project_id,
        created_at=created_at,
        actor=actor,
        book_id=book_id,
        branch_id=branch_id,
        revision_id=revision_id,
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload=payload,
    )


__all__ = ["policy_decision_event"]
