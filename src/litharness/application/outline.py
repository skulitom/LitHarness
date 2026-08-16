"""Narrative Planning v0: one statement per scene, so twenty-five beats stop being one beat.

**The measured defect this exists for.** `arc_template(30)` yields **25 `rising` beats out of
30**, and `render_prompt` puts the beat's title and its function word into the prompt and
nothing else from the plan — so twenty-five of the thirty (ordinals 3-17 and 19-28; the turn
sits at 18) are asked, from the planning side, *"Scene N — dramatic function: rising"* and
differ only in the integer. Book Zero's answer was five near-copies of an earlier scene and a ledger
that moved once in thirty, and §52 records both as the same root cause seen in two layers:
the book re-issues its own errand because nothing told it not to.

**A statement of what happens, not a richer function word.** Giving the rising span a longer
vocabulary — "complication", "setback", "reversal" — would differentiate the *label* and leave
the content mandate exactly as empty as before; two scenes labelled "complication" still have
no reason to differ. What stops scene 11 re-running scene 10's errand is scene 11 having its
own errand.

**One call for the whole book, and that is the design rather than a saving.** A per-scene call
would ask a model to invent scene 11 without having seen what scene 10 is for, which is the
condition that produces the duplication in the first place. Asked once, with the premise and
every beat's function in view, the model has to make the scenes differ from *each other* —
and `_statements` refuses the proposal if it did not, so the defect arrives as a
refused plan rather than as thirty scenes of prose nobody reads until later.

**It writes plan items and therefore inherits every property of the plan.** `PlanKind.SCENE_PLAN`
and `PlanItem.scope` have been in the contract with no producer since 1.0 — `domain/plans.py`
says so in its own docstring, "not one is a `scene_plan`; not one carries a `scope`". Going
through `PlanProposal` means the outline is versioned, attributable to a recorded decision,
rolled back by `revert-plan` like any other plan movement, and refused if the base moved under
it. None of that had to be built here.

What this is **not**, so the gap stays visible: it is not a foreshadow-payoff ledger and not a
progression schedule. §20.6's ordering trap still holds for the second — the schedule needs a
level curve the game-mechanics pack owns, and the litrpg fixture has no XP figure to build one
from. `open_threads` already carries promises; nothing here schedules their payoff.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import OutlineStore, TextGenerator
from litharness.domain.beats import Beat, beats_for, template_for
from litharness.domain.budget import BudgetPolicy
from litharness.domain.budget import check as budget_check
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.generation import CompletionRequest, CompletionResult, Resolution
from litharness.domain.jobs import Job
from litharness.domain.patch import Veto
from litharness.domain.plan_refinement import (
    PlanConflict,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalError,
    PlanRevision,
    apply_plan_proposal,
)
from litharness.domain.plans import premise_of, scene_plan_for, scene_plan_id_for
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decide,
    decision_id_for,
)

#: Job kind this handler answers to.
BOOK_OUTLINE = "book_outline"

#: Frozen generation profile, recorded in provenance like every other model call here.
PROFILE = "planner.outline.v0"

#: Ranks above scene drafting (0) and below director direction (500+). A scene drafted before
#: its statement exists would be drafted against the empty plan this module exists to fill, so
#: the outline has to be claimed first — and it is one call for the whole book, so it delays
#: the first scene by one tick and no more.
OUTLINE_PRIORITY = 300

#: Words per statement, asked for rather than enforced. A statement is an instruction to the
#: generator, not prose, and one that runs long starts writing the scene instead of placing it.
TARGET_WORDS = 25


class OutlineOutputError(Exception):
    """The model's outline is not one this handler can turn into a plan."""


OUTLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "rationale", "expected_outcome", "scenes"],
    "properties": {
        "summary": {"type": "string"},
        "rationale": {"type": "string"},
        "expected_outcome": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ordinal", "statement"],
                "properties": {
                    "ordinal": {"type": "integer"},
                    "statement": {"type": "string"},
                },
            },
        },
    },
}


def outline_job_id(book_id: str, branch_id: str, epoch: int) -> str:
    """Derived, and epoch-versioned for `beat_job_id`'s reason.

    `idempotency_key` is UNIQUE, so a poisoned outline would burn its id forever and "plan
    this book again" would be inexpressible. `replan` bumps the epoch and this follows it.
    """
    material = payload_digest(
        {"book_id": book_id, "branch_id": branch_id, "plan_epoch": epoch}
    )
    return f"outline-{material[:24]}"


def render_outline_request(
    premise: str, beats: Sequence[Beat], *, base: PlanRevision
) -> CompletionRequest:
    """Freeze the premise and the whole beat sheet into one structured-output request.

    The *entire* sheet goes in, not a window: the model is being asked to make thirty scenes
    differ from one another, and it cannot do that against a sheet it can only see part of.
    """
    prompt = json.dumps(
        {
            "premise": premise,
            "base_plan_revision_id": base.plan_revision_id,
            "scenes": [
                {
                    "ordinal": beat.ordinal,
                    "of_total": beat.of_total,
                    "dramatic_function": beat.function,
                }
                for beat in beats
            ],
            "rules": [
                f"Return exactly {len(beats)} scenes, ordinals 1 to {len(beats)}, each once.",
                f"Each statement is about {TARGET_WORDS} words.",
                "State what happens in that scene: who acts, what they do, what changes.",
                "Every statement must be different from every other. Two scenes that could "
                "be swapped without the book noticing are one scene written twice.",
                "Do not write prose, dialogue, or description; this is an instruction to a "
                "writer, not the scene itself.",
                "Respect the dramatic function given for each scene.",
                "Later scenes must build on earlier ones rather than repeat them: nothing may "
                "be obtained, revealed, or resolved twice.",
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return CompletionRequest(
        prompt=prompt,
        system=(
            "You are the Narrative Planner for a novel. Given a premise and a beat sheet, "
            "say in one sentence what happens in each scene, so that a writer drafting any "
            "one scene knows what that scene is for and what the others are for. Return "
            "only the requested JSON."
        ),
        schema=OUTLINE_SCHEMA,
        max_output_tokens=8192,
        profile=PROFILE,
        call_class="generation",
    )


def _statements(payload: Mapping[str, Any], expected: int) -> list[str]:
    """The model's scenes as an ordinal-ordered list, or a refusal naming what was wrong.

    **Distinctness is checked here rather than hoped for**, and it is the one validation that
    is about the defect instead of about the schema. An outline whose statements repeat is the
    same failure this module exists to end, arriving one layer earlier — and one layer earlier
    is where it is cheap, because a refused proposal costs one call and a repeated scene costs
    a generation plus everything downstream of accepting it.
    """
    raw = payload.get("scenes")
    if not isinstance(raw, list):
        raise OutlineOutputError("outline must carry a list of scenes")
    if len(raw) != expected:
        raise OutlineOutputError(
            f"outline covers {len(raw)} scene(s); the book has {expected}"
        )

    by_ordinal: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise OutlineOutputError("each scene must be an object")
        ordinal = entry.get("ordinal")
        statement = entry.get("statement")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            raise OutlineOutputError(f"scene ordinal {ordinal!r} is not an integer")
        if not 1 <= ordinal <= expected:
            raise OutlineOutputError(
                f"scene ordinal {ordinal} is outside 1..{expected}"
            )
        if ordinal in by_ordinal:
            raise OutlineOutputError(f"scene {ordinal} is described more than once")
        if not isinstance(statement, str) or not statement.strip():
            raise OutlineOutputError(f"scene {ordinal} has no statement")
        by_ordinal[ordinal] = statement.strip()

    missing = sorted(set(range(1, expected + 1)) - set(by_ordinal))
    if missing:
        raise OutlineOutputError(f"outline says nothing about scene(s) {missing}")

    ordered = [by_ordinal[ordinal] for ordinal in range(1, expected + 1)]
    folded = [" ".join(statement.lower().split()) for statement in ordered]
    duplicates = sorted({value for value in folded if folded.count(value) > 1})
    if duplicates:
        raise OutlineOutputError(
            f"{len(duplicates)} statement(s) appear on more than one scene; an outline that "
            "repeats itself plans the duplication it exists to prevent"
        )
    return ordered


def outline_proposal(
    payload: Mapping[str, Any],
    *,
    base: PlanRevision,
    beats: Sequence[Beat],
    project_id: str,
    book_id: str,
    branch_id: str,
    result: CompletionResult,
) -> PlanProposal:
    """The model's outline as plan edits, one `SCENE_PLAN` item per beat.

    `scope` names the scene the statement is about, which is what makes the item reachable by
    `scene_plan_for` and keeps it out of every *other* scene's packet. `constraints_of` selects
    only locked constraints and promises, so a scene plan cannot leak into the constraint block
    of a scene it does not describe.

    `INTENDED` rather than `AUTHOR_LOCKED`: a model wrote it. Locking it would give a
    generated statement the standing of the director's own word, and `apply_plan_proposal`
    refuses to touch a locked item — so a wrong outline would be unfixable by the same
    machinery that produced it.
    """
    statements = _statements(payload, len(beats))
    # **CREATE where the statement is absent, UPDATE where it is already there.** A
    # create-only proposal cannot outline a *partially* outlined book, and partial is a state
    # the system reaches on its own: a manuscript that gains a scene keeps the statements for
    # the ones it had, and `narrative_planner`'s directive lane can delete a single scene plan
    # because they are deliberately unlocked. Measured before this branch existed — the
    # selector fired on the one missing beat, the handler's guard did not (it wanted *all*
    # present), and `apply_plan_proposal` raised `plan item 'scene-1-plan' already exists`
    # after the whole-book call had already been paid for, three times per plan epoch, with
    # nothing in the exception queue to show for it.
    present = {
        item.logical_id
        for item in base.items
        if item.kind is lc.PlanKind.SCENE_PLAN
    }
    edits = tuple(
        PlanEdit(
            action=(
                PlanEditAction.UPDATE
                if scene_plan_id_for(beat.logical_id) in present
                else PlanEditAction.CREATE
            ),
            logical_id=scene_plan_id_for(beat.logical_id),
            item=lc.PlanItem(
                logical_id=scene_plan_id_for(beat.logical_id),
                kind=lc.PlanKind.SCENE_PLAN,
                text=statement,
                authority=lc.PlanAuthority.INTENDED,
                locked=False,
                scope=lc.ResourceRef(
                    project_id=project_id,
                    book_id=book_id,
                    branch_id=branch_id,
                    logical_id=beat.logical_id,
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                ),
            ),
            reason=f"outline for scene {beat.ordinal} of {beat.of_total}",
        )
        for beat, statement in zip(beats, statements, strict=True)
    )
    return PlanProposal(
        base_plan_revision_id=base.plan_revision_id,
        summary=str(payload.get("summary") or f"outline for {len(beats)} scenes"),
        rationale=str(payload.get("rationale") or "every scene needs its own errand"),
        expected_outcome=str(
            payload.get("expected_outcome") or "each scene is planned distinctly"
        ),
        edits=edits,
        provider=result.provider,
        model=result.model,
        profile=PROFILE,
    )


def _policy_digest() -> str:
    """Content address of what shaped this outline, so a change to it reads as a change.

    The request is built from constants — the schema, the target length, the rules — none of
    which appear in the plan item the operator sees. Without this, editing them would leave
    every recorded decision byte-identical while every outline produced after it came from a
    different question.
    """
    return payload_digest(
        {
            "profile": PROFILE,
            "target_words": TARGET_WORDS,
            "schema": OUTLINE_SCHEMA,
        }
    )


def _decision(
    job: Job,
    base: PlanRevision,
    result: CompletionResult,
    resolution: Resolution,
    *,
    passed: bool,
    detail: str | None,
    resulting_revision_id: str | None = None,
) -> PolicyDecision:
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.outline.v0",
        passed=passed,
        # The model proposed the plan; a *deterministic* check over its shape and
        # distinctness is what passed or failed it. Never `MODEL_SELF_REPORT`, which
        # `PolicyDecision` refuses on a blocking gate anyway.
        verdict_source=VerdictSource.DETERMINISTIC,
        # Named, so `decide` can classify the refusal. A blocking gate that fails without a
        # veto escalates as "a blocking gate failed without naming a veto", and
        # `SHAPE_NOT_CONFORMING` is what a malformed structured answer already is elsewhere.
        vetoes=() if passed else (Veto.SHAPE_NOT_CONFORMING,),
        detail=detail,
    )
    # **`decide` rather than a hand-written RETRY, which is what this did and it was the only
    # handler in `application` that minted a failing outcome without consulting the ladder.**
    # The difference shows at the ceiling: a hard-coded RETRY on the third attempt requeues a
    # job the queue then poisons, and the POISONED path files no exception — so an outline
    # that could never conform went quiet and the book drafted every scene with no statement,
    # forever, with nothing in the operator's queue. `decide` escalates on exhaustion, which
    # is what puts it in front of a human.
    verdict, reason = decide(
        (gate,),
        job_id=job.job_id,
        attempt=job.attempts,
        max_attempts=job.max_attempts,
    )
    return PolicyDecision(
        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
        outcome=verdict,
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
        # The frozen configuration this outline was produced under. Omitted at first, which
        # is the same defect the sampler commit had just fixed one layer over: a schema or
        # target-length change would have left every stored digest identical while every
        # outline after it came from a different request.
        policy_config_digest=_policy_digest(),
        reason=detail if passed else (detail or reason),
    )


def make_outline_handler(
    registry: TextGenerator,
    store: OutlineStore,
    project_id: str,
    *,
    budget: BudgetPolicy | None = None,
    actor: str = "litharness",
) -> JobHandler:
    """Build the premise → outline → immutable plan handler."""
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        book_id = job.payload.get("book_id")
        branch_id = job.payload.get("branch_id")
        if not isinstance(book_id, str) or not isinstance(branch_id, str):
            raise OutlineOutputError(f"job {job.job_id} lacks book_id/branch_id")

        stamp = datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")
        base = store.plan_revision(book_id, branch_id)
        if base is None:
            raise OutlineOutputError(f"book {book_id} has no plan to outline against")
        premise = premise_of(base.items)
        if premise is None:
            raise OutlineOutputError(
                f"book {book_id} has no single premise; an outline of nothing is thirty "
                "scenes of plausible prose about nothing"
            )

        head = store.head(book_id, branch_id)
        if head is None:
            raise OutlineOutputError(f"book {book_id} has no manuscript to outline")
        beats = beats_for(head, template_for(head))

        # Already outlined: every beat has a statement. A no-op rather than a second call,
        # because a replayed job must converge and an outline is a whole-book generation.
        #
        # **`scene_plan_for` and not derived-id membership**, because the selector asks the
        # same question with the same function and the two must be complements. They were
        # not: the selector matched on scope-then-id while this matched on id alone, so a
        # statement scoped to a scene under a foreign id read *present* to one and *absent*
        # to the other — which spends a call and writes a second statement for a scene that
        # already had one.
        if all(
            scene_plan_for(base.items, beat.logical_id) is not None for beat in beats
        ):
            # Recorded rather than silent. A handler that returns no events *and* no decision
            # leaves the Conductor settling this attempt against whatever decision the job
            # last produced — which after a refused attempt is that refusal, so a job that
            # has nothing left to do settles as though it had failed.
            store.record_decision(
                PolicyDecision(
                    decision_id=decision_id_for(job.job_id, job.attempts, ()),
                    outcome=Outcome.ACCEPT,
                    gates=(),
                    job_id=job.job_id,
                    base_revision_id=base.plan_revision_id,
                    attempt=job.attempts,
                    profile=PROFILE,
                    policy_config_digest=_policy_digest(),
                    reason="every beat already carries a statement",
                ),
                decided_at=stamp,
            )
            return ()

        request = render_outline_request(premise, beats, base=base)
        day = stamp[:10]
        provider, _ = registry.resolve(request.call_class)
        verdict = budget_check(
            budget_policy,
            store.spend_on(day),
            provider=provider.name,
            prompt_chars=len(request.prompt),
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            gate = GateOutcome(
                gate=GateKind.BUDGET,
                rule_or_critic_id=f"budget.{verdict.ceiling}.v0",
                passed=False,
                detail=verdict.reason,
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.PARK,
                gates=(gate,),
                job_id=job.job_id,
                base_revision_id=base.plan_revision_id,
                attempt=job.attempts,
                profile=PROFILE,
                reason=verdict.reason,
            )
            store.record_decision(refusal, decided_at=stamp)
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
                        "decision_id": refusal.decision_id,
                        "job_id": job.job_id,
                        "ceiling": verdict.ceiling,
                        "reason": verdict.reason,
                    },
                ),
            )

        result, resolution = registry.complete(request)
        try:
            if not result.conforms or result.parsed is None:
                raise OutlineOutputError(
                    "provider response did not conform to the outline schema"
                )
            proposal = outline_proposal(
                result.parsed,
                base=base,
                beats=beats,
                project_id=project_id,
                book_id=book_id,
                branch_id=branch_id,
                result=result,
            )
            preview = apply_plan_proposal(base, proposal)
        except (OutlineOutputError, PlanProposalError, TypeError, ValueError) as error:
            # RETRY rather than escalate: the request is unchanged and a second draw of a
            # structured answer is a fair second try, exactly as a malformed scene draft is.
            refusal = _decision(
                job, base, result, resolution,
                passed=False, detail=f"{type(error).__name__}: {error}",
            )
            store.record_decision(refusal, decided_at=stamp)
            return (
                policy_decision_event(
                    refusal,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    actor=result.provider,
                ),
            )

        decision = _decision(
            job, base, result, resolution,
            passed=True, detail=None,
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
            stale = _decision(
                job, base, result, resolution, passed=False, detail=str(error)
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
    "BOOK_OUTLINE",
    "OUTLINE_PRIORITY",
    "OUTLINE_SCHEMA",
    "PROFILE",
    "TARGET_WORDS",
    "OutlineOutputError",
    "make_outline_handler",
    "outline_job_id",
    "outline_proposal",
    "render_outline_request",
]
