"""Application seam for accepting an already-produced Narrative Planner proposal."""

from __future__ import annotations

from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import PlanRefinementStore
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.plan_refinement import (
    PlanApplication,
    PlanProposal,
    apply_plan_proposal,
)
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decision_id_for,
)


def _default_acceptance_decision(
    proposal: PlanProposal, application: PlanApplication
) -> PolicyDecision:
    """Attribute programmatic proposals that do not arrive through a provider job."""
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.plan_proposal.v0",
        passed=True,
    )
    return PolicyDecision(
        decision_id=decision_id_for(
            f"plan-proposal:{proposal.proposal_id}",
            0,
            (gate,),
        ),
        outcome=Outcome.ACCEPT,
        gates=(gate,),
        base_revision_id=application.before.plan_revision_id,
        resulting_revision_id=application.after.plan_revision_id,
        provider=proposal.provider,
        model=proposal.model,
        profile=proposal.profile,
        policy_config_digest=payload_digest(
            {"rule": gate.rule_or_critic_id, "proposal_id": proposal.proposal_id}
        ),
        reason="validated programmatic plan proposal",
    )


def accept_plan_proposal(
    store: PlanRefinementStore,
    proposal: PlanProposal,
    *,
    project_id: str,
    created_at: str,
    actor: str = "litharness",
    decision: PolicyDecision | None = None,
) -> PlanApplication:
    """Validate and atomically accept a proposal if its baseline is still the head.

    Producing the proposal may involve a slow model call. This function intentionally does
    not: it re-reads the head, performs deterministic validation, and lets the store compare
    the baseline again inside its write transaction. A provider job may supply its metered
    decision; programmatic proposals receive a deterministic acceptance decision so storage
    never advances a plan head without attribution.
    """
    base = store.plan_revision_for_id(proposal.base_plan_revision_id)
    application = apply_plan_proposal(base, proposal)
    accepted_decision = decision or _default_acceptance_decision(proposal, application)
    if (
        accepted_decision.outcome is not Outcome.ACCEPT
        or accepted_decision.base_revision_id != base.plan_revision_id
        or accepted_decision.resulting_revision_id != application.after.plan_revision_id
    ):
        raise ValueError("plan decision does not accept this application")
    event = Event(
        event_type=EventType.PLAN_CHANGED,
        project_id=project_id,
        created_at=created_at,
        actor=actor,
        book_id=base.book_id,
        branch_id=base.branch_id,
        revision_id=application.after.plan_revision_id,
        causation_id=(proposal.readings[0].directive_id if len(proposal.readings) == 1 else None),
        correlation_id=proposal.proposal_id,
        payload={
            "proposal_id": proposal.proposal_id,
            "base_plan_revision_id": base.plan_revision_id,
            "summary": proposal.summary,
            "rationale": proposal.rationale,
            "expected_outcome": proposal.expected_outcome,
            "edit_count": len(proposal.edits),
            "directive_ids": [reading.directive_id for reading in proposal.readings],
            "rollback_of": proposal.rollback_of,
        },
    )
    events = [
        event,
        policy_decision_event(
            accepted_decision,
            project_id=project_id,
            created_at=created_at,
            actor=actor,
            book_id=base.book_id,
            branch_id=base.branch_id,
            revision_id=application.after.plan_revision_id,
            causation_id=proposal.proposal_id,
            correlation_id=accepted_decision.decision_id,
        )
    ]
    store.commit_plan_application(
        application,
        created_at=created_at,
        interpreted_at=created_at,
        events=events,
        decision=accepted_decision,
    )
    return application


__all__ = ["accept_plan_proposal"]
