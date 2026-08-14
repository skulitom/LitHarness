"""A conservative, deterministic lane from explicit direction into the live plan.

The Narrative Planner will eventually interpret arc, tone, chapter, and premise notes with
a model. Explicit constraints and vetoes do not need that interpretation: changing their
words would add risk, while leaving them unread lets drafting continue against direction the
operator reasonably expects to be active.

This lane therefore does exactly one thing. A scoped or unambiguously resolvable
``constraint`` or ``veto`` becomes a locked plan constraint through a mechanical transform
and the same immutable, conflict-checked transaction as a future model proposal. Constraint
text stays exact; a veto gets an explicit deterministic label so its kind is not lost.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.ports import NarrativePlanningStore
from litharness.domain.directives import (
    VERBATIM_KINDS,
    Directive,
    DirectiveKind,
    DirectiveStatus,
)
from litharness.domain.events import Event, payload_digest
from litharness.domain.jobs import Job
from litharness.domain.plan_refinement import (
    DirectiveReading,
    PlanEdit,
    PlanEditAction,
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

DIRECTIVE_PLAN = "directive_plan"


class DirectivePlanInputError(ValueError):
    """The queued unit no longer identifies an applicable explicit directive."""


def directive_job_id(directive_id: str) -> str:
    """Stable identity for applying one immutable directive exactly once."""
    material = payload_digest({"directive_id": directive_id, "lane": "verbatim.v0"})
    return f"directive-{sha256(material.encode()).hexdigest()[:24]}"


def constraint_logical_id(directive_id: str) -> str:
    """Stable plan-item id without relying on model-generated identifiers."""
    return f"constraint-{sha256(directive_id.encode()).hexdigest()[:20]}"


def is_verbatim_actionable(directive: Directive) -> bool:
    """True only where preserving the original words is a complete interpretation."""
    return directive.status is DirectiveStatus.RECEIVED and directive.kind in VERBATIM_KINDS


def _constraint_text(directive: Directive) -> str:
    if directive.kind is DirectiveKind.VETO:
        # PlanItem has no VETO kind. Preserve the body but carry the directive's negative
        # semantics forward instead of turning "combat" into a positive constraint.
        return f"The director vetoes: {directive.body}"
    return directive.body


def proposal_for_verbatim_directive(
    directive: Directive, *, base_plan_revision_id: str
) -> PlanProposal:
    """Copy an explicit instruction into one locked constraint, with no paraphrase."""
    if not is_verbatim_actionable(directive):
        raise DirectivePlanInputError(
            f"directive {directive.directive_id} ({directive.kind.value}/"
            f"{directive.status.value}) is not eligible for verbatim application"
        )
    logical_id = constraint_logical_id(directive.directive_id)
    text = _constraint_text(directive)
    constraint = lc.PlanItem(
        logical_id=logical_id,
        kind=lc.PlanKind.CONSTRAINT,
        text=text,
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    return PlanProposal(
        base_plan_revision_id=base_plan_revision_id,
        summary=f"Apply {directive.kind.value} directive verbatim",
        rationale=(
            "Explicit constraints and vetoes are authoritative director words; copying "
            "them avoids adding a model interpretation."
        ),
        expected_outcome="Subsequent context packets include the exact locked instruction.",
        edits=(
            PlanEdit(
                PlanEditAction.CREATE,
                logical_id,
                constraint,
                "verbatim director instruction",
            ),
        ),
        readings=(DirectiveReading(directive.directive_id, text, (logical_id,)),),
        profile="directive.verbatim.v0",
    )


def make_directive_plan_handler(
    store: NarrativePlanningStore, project_id: str, *, actor: str = "litharness"
) -> JobHandler:
    """Accept one verbatim directive against the plan head current at execution time."""

    def handle(job: Job, now: float) -> Sequence[Event]:
        directive_id = job.payload.get("directive_id")
        if not isinstance(directive_id, str) or not directive_id:
            raise DirectivePlanInputError(
                f"job {job.job_id} payload lacks a non-empty directive_id"
            )
        directive = store.load_directive(directive_id)

        # Crash-after-commit replay: the plan transaction landed, the job status did not.
        # The directive's APPLIED state is the durable success marker.
        if directive.status is DirectiveStatus.APPLIED:
            return ()
        if not is_verbatim_actionable(directive):
            raise DirectivePlanInputError(
                f"directive {directive.directive_id} is no longer verbatim-actionable"
            )
        book_id = job.payload.get("book_id")
        branch_id = job.payload.get("branch_id")
        if not isinstance(book_id, str) or not isinstance(branch_id, str):
            raise DirectivePlanInputError(
                f"job {job.job_id} has no resolved book and branch"
            )
        if directive.book_id not in {None, book_id} or directive.branch_id not in {
            None,
            branch_id,
        }:
            raise DirectivePlanInputError(
                f"job {job.job_id} scope disagrees with directive {directive.directive_id}"
            )
        head = store.plan_revision(book_id, branch_id)
        if head is None:
            raise DirectivePlanInputError(
                f"directive {directive.directive_id} targets a branch with no plan"
            )

        proposal = proposal_for_verbatim_directive(
            directive, base_plan_revision_id=head.plan_revision_id
        )
        preview = apply_plan_proposal(head, proposal)
        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="shape.directive_verbatim.v0",
            passed=True,
        )
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
            outcome=Outcome.ACCEPT,
            gates=(gate,),
            job_id=job.job_id,
            base_revision_id=head.plan_revision_id,
            resulting_revision_id=preview.after.plan_revision_id,
            attempt=job.attempts,
            profile="directive.verbatim.v0",
            policy_config_digest=payload_digest({"lane": "directive.verbatim.v0"}),
        )
        stamp = datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")
        accept_plan_proposal(
            store,
            proposal,
            project_id=project_id,
            created_at=stamp,
            actor=actor,
            decision=decision,
        )
        # accept_plan_proposal commits the plan revision, directive reading, and PlanChanged
        # event atomically. Returning that event would make the Conductor append it again.
        return ()

    return handle


__all__ = [
    "DIRECTIVE_PLAN",
    "DirectivePlanInputError",
    "constraint_logical_id",
    "directive_job_id",
    "is_verbatim_actionable",
    "make_directive_plan_handler",
    "proposal_for_verbatim_directive",
]
