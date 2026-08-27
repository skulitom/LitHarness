"""Model-backed plan proposals for direction that cannot be applied mechanically.

This is deliberately smaller than the Narrative Planner described in PLAN.md §9. It reads
one premise, arc, tone, or chapter directive and proposes bounded edits against one frozen
plan revision. The model never writes the plan directly: its JSON is parsed into domain
types, every edit is validated (including locks and the single-premise invariant), and the
proposal is accepted only if the same plan revision is still current.

Explicit constraints and vetoes stay in ``directive_planner`` because a model would add risk
without adding interpretation. Controls stay outside both lanes because pause/resume/kill are
operator state, not story planning.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.model_context import StoryStateView, planning_records
from litharness.application.model_context import current as current_state_view
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import NarrativePlanningStore, TextGenerator
from litharness.domain import world_brief
from litharness.domain.beats import scene_nodes
from litharness.domain.budget import BudgetPolicy
from litharness.domain.budget import check as budget_check
from litharness.domain.directives import INTERPRETIVE_KINDS, Directive, DirectiveStatus
from litharness.domain.directors import is_machine_author
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.generation import (
    CompletionRequest,
    CompletionResult,
    Resolution,
)
from litharness.domain.jobs import Job
from litharness.domain.patch import Veto
from litharness.domain.plan_refinement import (
    DirectiveReading,
    PlanConflict,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalError,
    PlanRevision,
    apply_plan_proposal,
)
from litharness.domain.plans import scene_plan_for
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decide,
    decision_id_for,
)
from litharness.domain.text import content_hash
from litharness.domain.world_brief import WorldBrief

NARRATIVE_PLAN = "narrative_plan"
PROFILE = "planner.directive.v0"
MAX_EDITS = 12

_PLAN_KINDS = tuple(kind.value for kind in lc.PlanKind if kind is not lc.PlanKind.UNKNOWN)
_AUTHORITIES = (lc.PlanAuthority.INTENDED.value, lc.PlanAuthority.POSSIBLE.value)

PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "rationale",
        "expected_outcome",
        "interpretation",
        "edits",
    ],
    "properties": {
        "summary": {"type": "string"},
        "rationale": {"type": "string"},
        "expected_outcome": {"type": "string"},
        "interpretation": {"type": "string"},
        "edits": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_EDITS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "action",
                    "logical_id",
                    "kind",
                    "text",
                    "authority",
                    "locked",
                    "scope",
                    "reason",
                ],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [action.value for action in PlanEditAction],
                    },
                    "logical_id": {"type": "string"},
                    # Delete uses the sentinel "none" for fields whose values are ignored.
                    # Keeping every key required satisfies strict structured-output providers.
                    "kind": {"type": "string", "enum": [*_PLAN_KINDS, "none"]},
                    "text": {"type": "string"},
                    "authority": {
                        "type": "string",
                        "enum": [*_AUTHORITIES, "none"],
                    },
                    "locked": {"type": "boolean"},
                    # **A scene plan that cannot say which scene it is for is unreachable.**
                    # `plans.scene_plan_for` matches on scope first and a derived id second,
                    # and a directive-minted item can satisfy neither, so before this field
                    # existed every scene plan a chapter note produced sat in the plan looking
                    # complete and reached no draft. Measured on Serial Pilot 1: eight correct
                    # scene plans, none of them addressable. "none" for items that scope to the
                    # book rather than to one scene.
                    "scope": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


class NarrativePlanOutputError(PlanProposalError):
    """A provider answer is JSON but not a safe, applicable plan proposal."""


def _accepted_scene_target(
    item: lc.PlanItem | None, accepted_scene_ids: Sequence[str]
) -> str | None:
    if item is None:
        return None
    return next(
        (
            logical_id
            for logical_id in accepted_scene_ids
            if scene_plan_for((item,), logical_id) is item
        ),
        None,
    )


def narrative_job_id(directive_id: str, epoch: int) -> str:
    """Stable within one recovery epoch; ``replan`` deliberately creates a fresh unit."""
    material = payload_digest({"directive_id": directive_id, "epoch": epoch, "lane": PROFILE})
    return f"narrative-{sha256(material.encode()).hexdigest()[:24]}"


def is_interpretive_actionable(directive: Directive) -> bool:
    return directive.status is DirectiveStatus.RECEIVED and directive.kind in INTERPRETIVE_KINDS


def render_request(
    base: PlanRevision,
    directive: Directive,
    scene_ids: Sequence[str] = (),
    *,
    world: WorldBrief | None = None,
    current_state: StoryStateView | None = None,
    accepted_summaries: Sequence[tuple[str, str]] = (),
    accepted_scene_ids: Sequence[str] = (),
) -> CompletionRequest:
    """Freeze the plan, the book's scenes, and the original direction into one request.

    **The scene list is not decoration.** A `scene_plan` reaches a draft only when it is scoped
    to a scene, and a model cannot scope to an id it was never shown — so before the book's
    scenes were named here, a chapter note could produce eight perfect scene plans that no
    scene could ever find.

    **The world is keyword-only, and the position matters.** `scene_ids` is
    positional-or-keyword and its one call site passes it positionally; adding a second
    positional slot to a function whose third argument is already an optional sequence is how a
    later caller silently passes a brief as a list of scenes. It is absent from the payload for
    a book with no world, so a book that declares none renders the bytes it always did.

    Accepted summaries, per-scene status and current state are one structural manuscript
    context, separate from the editable plan. They contain no prose. Their absence preserves
    the old request for direct callers, while the production handler always supplies them when
    a manuscript head exists.
    """
    plan_payload = [lc.to_jsonable(item) for item in base.items]
    accepted = frozenset(accepted_scene_ids)
    summaries = dict(accepted_summaries)
    manuscript_context = {
        "scenes": [
            {
                "scene": logical_id,
                "status": "accepted" if logical_id in accepted else "draftable",
                **({"accepted_summary": summaries[logical_id]} if logical_id in summaries else {}),
            }
            for logical_id in scene_ids
        ],
        **(
            {"current_story_state": current_state.to_jsonable()}
            if current_state is not None
            else {}
        ),
    }
    prompt = json.dumps(
        {
            "base_plan_revision_id": base.plan_revision_id,
            # See the docstring: spread rather than assigned, so no key exists without a world.
            **({"world": world.to_jsonable()} if world is not None else {}),
            "scenes_in_reading_order": list(scene_ids),
            **({"manuscript_context": manuscript_context} if scene_ids else {}),
            "directive": {
                "directive_id": directive.directive_id,
                "kind": directive.kind.value,
                "body": directive.body,
                "precedence": directive.precedence,
                "target_logical_ids": list(directive.target_logical_ids),
            },
            "current_plan_items": plan_payload,
            "rules": [
                "Return between 1 and 12 concrete edits.",
                "Never update or delete a locked item.",
                "The result must contain exactly one premise.",
                "Use authority intended or possible; never claim canonical_in_prose.",
                "For delete, set kind and authority to none, text to empty, and locked false.",
                "Preserve an existing logical_id when updating it.",
                "If target_logical_ids is non-empty, update or delete only those items.",
                "Interpret the director's words; do not overwrite or paraphrase the input.",
                "Set scope to the scene's id from scenes_in_reading_order for any item that "
                "is about one scene, and above all for every scene_plan: an unscoped scene "
                "plan reaches no scene and shapes nothing.",
                "Set scope to none for items about the whole book or a chapter.",
                "A constraint must be locked to reach a scene at all: unlocked constraints are "
                "filtered out of every context packet. Set locked true on any constraint you "
                "want the prose to obey.",
            ]
            + (list(world_brief.WORLD_RULES) if world is not None else []),
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return CompletionRequest(
        prompt=prompt,
        system=(
            "You are the Narrative Planner for a versioned novel plan. Propose a minimal "
            "set of plan edits that implements the director's directive. Return only the "
            "requested JSON. You do not apply edits and cannot override locked items."
        ),
        schema=PROPOSAL_SCHEMA,
        max_output_tokens=4096,
        profile=PROFILE,
        call_class="generation",
    )


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NarrativePlanOutputError(f"proposal {key} must be a non-empty string")
    return value


def _scope_from(
    raw: object,
    index: int,
    *,
    existing: lc.PlanItem | None,
    scene_ids: Sequence[str],
    base: PlanRevision,
    project_id: str,
) -> lc.ResourceRef | None:
    """What this plan item is *about*, when the model says so and the book agrees.

    **The narrow opening, and its narrowness is the argument.** A model may scope an item only
    to a scene this book actually has; anything else is refused rather than coerced, because a
    scope naming a node that does not exist is a plan item addressed to nowhere and would fail
    the same silent way the missing scope did. `scene_ids` empty means the caller is not in a
    position to check, and then this preserves what was there before rather than trusting an
    unvalidated answer.
    """
    if not isinstance(raw, str) or not raw.strip() or raw.strip().lower() == "none":
        return existing.scope if existing is not None else None
    wanted = raw.strip()
    if not scene_ids:
        return existing.scope if existing is not None else None
    if wanted not in scene_ids:
        raise NarrativePlanOutputError(
            f"edit {index} scopes to {wanted!r}, which is not a scene in this book"
        )
    return lc.ResourceRef(
        project_id=project_id,
        book_id=base.book_id,
        branch_id=base.branch_id,
        logical_id=wanted,
        kind=lc.ResourceKind.MANUSCRIPT_SCENE,
    )


def proposal_from_model(
    payload: Mapping[str, Any],
    *,
    base: PlanRevision,
    directive: Directive,
    result: CompletionResult,
    scene_ids: Sequence[str] = (),
    accepted_scene_ids: Sequence[str] = (),
    project_id: str = "",
) -> PlanProposal:
    """Parse the shallow provider payload into strict domain objects."""
    raw_edits = payload.get("edits")
    if not isinstance(raw_edits, list) or not 1 <= len(raw_edits) <= MAX_EDITS:
        raise NarrativePlanOutputError(
            f"proposal edits must contain between 1 and {MAX_EDITS} items"
        )

    current = {item.logical_id: item for item in base.items}
    edits: list[PlanEdit] = []
    for index, raw in enumerate(raw_edits):
        if not isinstance(raw, Mapping):
            raise NarrativePlanOutputError(f"edit {index} must be an object")
        try:
            action = PlanEditAction(raw["action"])
        except (KeyError, TypeError, ValueError) as error:
            raise NarrativePlanOutputError(f"edit {index} has an invalid action") from error
        logical_id = raw.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id:
            raise NarrativePlanOutputError(f"edit {index} requires logical_id")
        reason = raw.get("reason", "")
        if not isinstance(reason, str):
            raise NarrativePlanOutputError(f"edit {index} reason must be a string")
        if (
            action in {PlanEditAction.UPDATE, PlanEditAction.DELETE}
            and directive.target_logical_ids
            and logical_id not in directive.target_logical_ids
        ):
            raise NarrativePlanOutputError(
                f"edit {index} targets {logical_id!r}, outside the directive's targets"
            )

        if action is PlanEditAction.DELETE:
            existing = current.get(logical_id)
            accepted_target = _accepted_scene_target(existing, accepted_scene_ids)
            if accepted_target is not None:
                raise NarrativePlanOutputError(
                    f"edit {index} targets accepted scene {accepted_target!r}; "
                    "the narrative-planning lane cannot revise accepted manuscript"
                )
            edits.append(PlanEdit(action, logical_id, reason=reason))
            continue

        try:
            kind = lc.PlanKind(raw["kind"])
            authority = lc.PlanAuthority(raw["authority"])
        except (KeyError, TypeError, ValueError) as error:
            raise NarrativePlanOutputError(
                f"edit {index} has an invalid kind or authority"
            ) from error
        if kind is lc.PlanKind.UNKNOWN or authority not in {
            lc.PlanAuthority.INTENDED,
            lc.PlanAuthority.POSSIBLE,
        }:
            raise NarrativePlanOutputError(f"edit {index} uses a reserved kind or authority")
        text = raw.get("text")
        locked = raw.get("locked")
        if not isinstance(text, str) or not text.strip():
            raise NarrativePlanOutputError(f"edit {index} text must be non-empty")
        if not isinstance(locked, bool):
            raise NarrativePlanOutputError(f"edit {index} locked must be boolean")

        scope = _scope_from(
            raw.get("scope"),
            index,
            existing=current.get(logical_id),
            scene_ids=scene_ids,
            base=base,
            project_id=project_id,
        )
        existing = current.get(logical_id)
        if locked and is_machine_author(directive.author):
            # **A machine-authored directive may not mint a locked plan item, whatever the
            # model returned.** The lock is the human director's authority: a locked constraint
            # lands in the packet's CONSTRAINTS section at priority 2 and is effectively never
            # dropped, so a Director that could set it would put its own words in every
            # subsequent prompt wearing a person's standing (`plan/director-role.md` §1).
            # Downgraded rather than refused, because the *direction* is legitimate and only
            # its authority is not — refusing would throw away a usable proposal to punish one
            # boolean the model had no reason to know it could not set.
            locked = False
        elif kind is lc.PlanKind.CONSTRAINT:
            # **And the symmetric rule, which is the one that was missing.** `locked` is not a
            # style preference: `plans.constraints_of` selects on it, so an *unlocked*
            # constraint reaches no context packet at all. The model was never told that, and
            # duly returned `locked: false` for every constraint it minted from the tone note —
            # so on both Serial Pilot runs the drafting prompt carried only the four verbatim
            # constraints, and not one word of "close third person", "dry, exact", "dramatize
            # rather than summarize" or "avoid rule-of-three flourishes" ever reached a scene.
            #
            # The plan showed them. `litharness plans` reported them. They shaped nothing.
            #
            # A constraint a *person* directed carries that person's authority by construction,
            # exactly as the branch above denies it to a machine. The two together mean the lock
            # follows the author rather than a boolean the model guesses at.
            locked = True
        item = lc.PlanItem(
            logical_id=logical_id,
            kind=kind,
            text=text,
            authority=authority,
            locked=locked,
            scope=scope,
            links=list(existing.links) if existing is not None else [],
        )
        accepted_target = _accepted_scene_target(item, accepted_scene_ids)
        if accepted_target is not None:
            raise NarrativePlanOutputError(
                f"edit {index} targets accepted scene {accepted_target!r}; "
                "the narrative-planning lane cannot revise accepted manuscript"
            )
        edits.append(PlanEdit(action, logical_id, item, reason))

    produced = tuple(
        edit.logical_id
        for edit in edits
        if edit.item is not None and edit.item.kind is lc.PlanKind.CONSTRAINT and edit.item.locked
    )
    proposal = PlanProposal(
        base_plan_revision_id=base.plan_revision_id,
        summary=_text(payload, "summary"),
        rationale=_text(payload, "rationale"),
        expected_outcome=_text(payload, "expected_outcome"),
        edits=tuple(edits),
        readings=(
            DirectiveReading(
                directive.directive_id,
                _text(payload, "interpretation"),
                produced,
            ),
        ),
        provider=result.provider,
        model=result.model,
        profile=PROFILE,
    )
    application = apply_plan_proposal(base, proposal)
    no_ops = [
        applied.logical_id
        for applied in application.applied_edits
        if applied.before is not None
        and applied.after is not None
        and lc.to_jsonable(applied.before) == lc.to_jsonable(applied.after)
    ]
    if no_ops:
        raise NarrativePlanOutputError(f"proposal contains no-op edits: {sorted(no_ops)}")
    return proposal


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _policy_digest() -> str:
    return payload_digest({"profile": PROFILE, "schema": PROPOSAL_SCHEMA, "max_edits": MAX_EDITS})


def _candidate_decision(
    job: Job,
    base: PlanRevision,
    result: CompletionResult,
    resolution: Resolution,
    *,
    passed: bool,
    detail: str | None,
    resulting_revision_id: str | None = None,
    stale: bool = False,
) -> PolicyDecision:
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id=("shape.plan_base_current.v0" if stale else "shape.plan_proposal.v0"),
        passed=passed,
        vetoes=(
            () if passed else (Veto.STALE_BASE_VERSION if stale else Veto.SHAPE_NOT_CONFORMING,)
        ),
        detail=detail,
    )
    outcome, reason = decide(
        (gate,),
        job_id=job.job_id,
        attempt=job.attempts,
        max_attempts=job.max_attempts,
    )
    return PolicyDecision(
        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
        outcome=outcome,
        gates=(gate,),
        job_id=job.job_id,
        base_revision_id=base.plan_revision_id,
        resulting_revision_id=resulting_revision_id,
        attempt=job.attempts,
        provider=result.provider,
        model=result.model,
        profile=PROFILE,
        fell_back_from=tuple(resolution.fell_back_from),
        invocations=result.invocations,
        total_tokens=result.usage.total,
        cost_usd=result.cost_usd,
        policy_config_digest=_policy_digest(),
        reason=reason or detail,
    )


def make_narrative_plan_handler(
    registry: TextGenerator,
    store: NarrativePlanningStore,
    project_id: str,
    *,
    budget: BudgetPolicy | None = None,
    actor: str = "litharness",
) -> JobHandler:
    """Build the bounded provider → proposal → immutable plan handler."""
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        directive_id = job.payload.get("directive_id")
        book_id = job.payload.get("book_id")
        branch_id = job.payload.get("branch_id")
        scoped_values = (directive_id, book_id, branch_id)
        if not all(isinstance(value, str) and value for value in scoped_values):
            raise NarrativePlanOutputError(f"job {job.job_id} lacks directive_id/book_id/branch_id")
        assert isinstance(directive_id, str)
        assert isinstance(book_id, str)
        assert isinstance(branch_id, str)
        directive = store.load_directive(directive_id)
        if directive.status is DirectiveStatus.APPLIED:
            return ()
        if not is_interpretive_actionable(directive):
            raise NarrativePlanOutputError(
                f"directive {directive.directive_id} is not interpretive plan work"
            )
        if directive.book_id not in {None, book_id} or directive.branch_id not in {
            None,
            branch_id,
        }:
            raise NarrativePlanOutputError(
                f"job {job.job_id} scope disagrees with directive {directive.directive_id}"
            )
        base = store.plan_revision(book_id, branch_id)
        if base is None:
            raise NarrativePlanOutputError(
                f"directive {directive.directive_id} targets a branch with no plan"
            )
        # The scenes the plan may address, read off the manuscript rather than guessed. A
        # book with no head has no scenes to scope to, and an unscoped proposal is what it
        # got before this existed, so the empty tuple is the honest fallback.
        head = store.head(book_id, branch_id)
        if head is None:
            scene_ids: tuple[str, ...] = ()
            accepted_scene_ids: tuple[str, ...] = ()
            accepted_summaries: tuple[tuple[str, str], ...] = ()
        else:
            scene_ids = tuple(scene_nodes(head))
            accepted_scene_ids = tuple(
                logical_id for logical_id in scene_ids if head.node(logical_id).content
            )
            stored_summaries = store.scene_summaries(book_id, branch_id)
            summary_rows = (
                (
                    logical_id,
                    stored_summaries.get(logical_id, {}).get(
                        content_hash(head.node(logical_id).content or ""), ""
                    ),
                )
                for logical_id in accepted_scene_ids
            )
            accepted_summaries = tuple(
                (logical_id, summary) for logical_id, summary in summary_rows if summary
            )
        canon = tuple(store.state_records(book_id, branch_id))

        # **The world, read here rather than threaded from the caller.** Unlike the outline
        # handler this one holds no canon of its own, so the brief costs one query — and it is
        # the same query, on the same store, that `make_outline_handler` already makes. A book
        # with no world gets `None` and the request renders the bytes it always did.
        state_view = current_state_view(head, canon) if head is not None else None
        request = render_request(
            base,
            directive,
            scene_ids,
            world=world_brief.brief_for(
                planning_records(canon, state_view) if state_view is not None else canon
            ),
            current_state=state_view,
            accepted_summaries=accepted_summaries,
            accepted_scene_ids=accepted_scene_ids,
        )
        stamp = _stamp(now)
        day = stamp[:10]
        provider, _ = registry.resolve(request.call_class)
        verdict = budget_check(
            budget_policy,
            store.spend_on(day),
            provider=provider.name,
            prompt_chars=request.input_chars,
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            gate = GateOutcome(
                gate=GateKind.BUDGET,
                rule_or_critic_id=f"budget.{verdict.ceiling}.v0",
                passed=False,
                detail=verdict.reason,
            )
            decision = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.PARK,
                gates=(gate,),
                job_id=job.job_id,
                base_revision_id=base.plan_revision_id,
                attempt=job.attempts,
                profile=PROFILE,
                policy_config_digest=_policy_digest(),
                reason=verdict.reason,
            )
            store.record_decision(decision, decided_at=stamp)
            return (
                Event(
                    event_type=EventType.BUDGET_EXHAUSTED,
                    project_id=project_id,
                    created_at=stamp,
                    actor=actor,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "job_id": job.job_id,
                        "ceiling": verdict.ceiling,
                        "reason": verdict.reason,
                        "projected_tokens": verdict.projected_tokens,
                        "spent_today": store.spend_on(day).tokens,
                    },
                ),
            )

        result, resolution = registry.complete(request)
        try:
            if not result.conforms or result.parsed is None:
                raise NarrativePlanOutputError(
                    "provider response did not conform to the plan proposal schema"
                )
            proposal = proposal_from_model(
                result.parsed,
                base=base,
                directive=directive,
                result=result,
                scene_ids=scene_ids,
                accepted_scene_ids=accepted_scene_ids,
                project_id=project_id,
            )
            preview = apply_plan_proposal(base, proposal)
        except (PlanProposalError, TypeError, ValueError) as error:
            decision = _candidate_decision(
                job,
                base,
                result,
                resolution,
                passed=False,
                detail=f"{type(error).__name__}: {error}",
            )
            store.record_decision(decision, decided_at=stamp)
            return (
                policy_decision_event(
                    decision,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    actor=result.provider,
                ),
            )

        decision = _candidate_decision(
            job,
            base,
            result,
            resolution,
            passed=True,
            detail=None,
            resulting_revision_id=preview.after.plan_revision_id,
        )
        try:
            accept_plan_proposal(
                store,
                proposal,
                project_id=project_id,
                created_at=stamp,
                actor=result.provider,
                decision=decision,
            )
        except PlanConflict as error:
            stale = _candidate_decision(
                job,
                base,
                result,
                resolution,
                passed=False,
                detail=str(error),
                stale=True,
            )
            store.record_decision(stale, decided_at=stamp)
            return (
                policy_decision_event(
                    stale,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    actor=result.provider,
                ),
            )
        return ()

    return handle


__all__ = [
    "MAX_EDITS",
    "NARRATIVE_PLAN",
    "PROFILE",
    "PROPOSAL_SCHEMA",
    "NarrativePlanOutputError",
    "is_interpretive_actionable",
    "make_narrative_plan_handler",
    "narrative_job_id",
    "proposal_from_model",
    "render_request",
]
