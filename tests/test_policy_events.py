"""The audit event for a policy decision has one shape across every producer."""

from __future__ import annotations

import pytest

from litharness.application.policy_events import policy_decision_event
from litharness.domain.events import EventType
from litharness.domain.policy import GateKind, GateOutcome, Outcome, PolicyDecision


def decision() -> PolicyDecision:
    gate = GateOutcome(GateKind.SHAPE, "shape.example.v0", False, detail="not safe")
    return PolicyDecision(
        decision_id="decision-1",
        outcome=Outcome.RETRY,
        gates=(gate,),
        job_id="job-1",
        attempt=2,
        reason="try again",
    )


def test_policy_event_has_one_complete_canonical_payload() -> None:
    event = policy_decision_event(
        decision(),
        project_id="project-1",
        created_at="2026-08-14T12:00:00Z",
        book_id="book-1",
        details={"finding_ids": ["finding-1"]},
    )

    assert event.event_type is EventType.POLICY_DECISION_RECORDED
    assert event.payload == {
        "decision_id": "decision-1",
        "job_id": "job-1",
        "outcome": "retry",
        "attempt": 2,
        "reason": "try again",
        "gates": [{"id": "shape.example.v0", "passed": False}],
        "finding_ids": ["finding-1"],
    }


def test_policy_event_details_cannot_replace_a_canonical_field() -> None:
    with pytest.raises(ValueError, match=r"reserved fields.*outcome"):
        policy_decision_event(
            decision(),
            project_id="project-1",
            created_at="2026-08-14T12:00:00Z",
            details={"outcome": "accept"},
        )
