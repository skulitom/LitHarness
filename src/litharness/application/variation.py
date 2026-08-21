"""The bounded variation session: one mediated action per tick, in front of the commit path.

This is the durable multi-attempt loop the fixed repair path does not have. `repair.py` spends
one provider call, applies whatever came back, and lets the Conductor's retry ladder decide
whether to spend another — so the model never sees *why* its patch was refused, and each retry
starts from the same blank page as the last. Here the refusal comes back as the exact gate
vector, the attempt is recorded whether it passed or failed, and the next proposal is written
against that record.

**What is deliberately not imported from the loop this is modelled on.** AVO's agentic
variation step works because its objective is ground truth. Ours is not: nothing in this
repository is entitled to order prose by quality, so a loop that chose among *valid* candidates
by any score would be optimising a proxy and calling it progress. Acceptance here is
lexicographic and only the first tier is in play — mechanical feasibility, exactly as
`gates_for_patch` and `decide` already define it — and the session commits the **first**
candidate that clears it and stops. There is no ranking anywhere in this module and no place to
put one.

**One action per Conductor tick, one job per action, and the id carries the ordinal.** A job id
is content-derived and `insert_job` is `INSERT OR IGNORE`, so a re-enqueued id is silence and a
`SUCCEEDED` row is terminal with its key burned. A session therefore chains: each step mints the
next step's job inside the same transaction that records its own outcome, exactly as
`plan_search` mints `span_select`. The session's state lives in its rows and never in a
conversation, so a restart resumes with what an uninterrupted run would have had, and a replayed
tick finds a recorded ACCEPT and returns without re-spending the call.

**Where the boundaries sit, stated because they are what makes this safe to run.** The agent
holds six typed actions and nothing else — no shell, no filesystem, no store access. The commit
action does not commit: it *requests* acceptance from `decide`, and the existing policy path
remains the only authority over whether prose moves. Every ceiling is enforced separately and a
refusal names the one that stopped it. Stalls are detected from the rows and close the session;
nothing here redirects a stalled session onto a different strategy, because choosing a strategy
is a supervisor's judgment and no supervisor is built.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import TextGenerator, VariationStore
from litharness.application.repair import (
    MAX_AUTO_REPAIRS,
    calibration_licenses,
    evaluation_job_for,
    propagated_evaluations,
)
from litharness.domain.budget import BudgetPolicy, projected_tokens
from litharness.domain.budget import check as budget_check
from litharness.domain.events import Event, EventType
from litharness.domain.extraction import extract_state
from litharness.domain.findings import Finding, primary_span_of
from litharness.domain.generation import CompletionRequest
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.patch import PatchPolicy, apply_patch
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decide,
    decision_id_for,
    gates_for_patch,
)
from litharness.domain.revision import node_version_id
from litharness.domain.variation import (
    ActionKind,
    ActionRequest,
    AttemptOutcome,
    KnowledgeItem,
    MalformedAction,
    SessionLimits,
    SessionOutcome,
    VariationAttempt,
    VariationObjective,
    VariationSession,
    attempt_id_for,
    check_limits,
    derive_knowledge,
    detect_stall,
    parse_action,
    patch_digest_for,
    render_knowledge,
    render_lineage,
    session_id_for,
    variation_config_digest,
)

VARIATION_STEP = "variation_step"

#: One band above the highest repair claim, and for `SPAN_SELECT_PRIORITY`'s reason.
#:
#: A repair claims at `REPAIR_PRIORITY` plus the finding's severity rank, which tops out at 104
#: for a critical complaint. A session's next step outranks all of them because finishing a
#: session spends money the system has already committed: leaving an open session behind a
#: freshly minted repair means two sessions in flight, both holding attempts, both counting
#: against the day's budget, and neither closing. The step ceiling is what bounds the loop; this
#: band is only what stops a queue of half-finished sessions from accumulating.
VARIATION_STEP_PRIORITY = 110

#: The action surface as a schema, derived from the enum so the two cannot drift.
#:
#: `additionalProperties` is declared and `parse_schema_payload` does not enforce it — shallow
#: validation is that module's stated design — so the harness validates the action and its
#: arguments itself in `parse_action`. That is the right place for it anyway: an unusable
#: response is a fact about the attempt to be counted and bounded, not a schema violation to be
#: raised out of a handler.
ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {"type": "string", "enum": [member.value for member in ActionKind]},
        "replacement": {"type": "string"},
        "strategy": {"type": "string"},
        "reason": {"type": "string"},
    },
    "additionalProperties": False,
}

_ACTION_RULE = "shape.variation_action.v0"
_SESSION_RULE = "shape.variation_session.v0"
_LIMIT_RULE = "budget.variation.{limit}.v0"
_MAX_OUTPUT_TOKENS = 2048


@dataclass(frozen=True, slots=True)
class _Provenance:
    """What one provider call cost and who served it, carried to the decision record.

    A record rather than a dict of keyword arguments: the call's provenance travels through
    four different recording paths in this module and every one of them writes it onto a
    `PolicyDecision`, so a typed carrier is what keeps the day's spend accountable — anything
    not written to a decision row is invisible to `spend_on` and therefore to the budget gate.
    """

    provider: str | None = None
    model: str | None = None
    tokens: int = 0
    invocations: int = 0
    cost_usd: float | None = None
    fell_back_from: tuple[str, ...] = ()


#: The provenance of a refusal that happened in front of any provider call.
#:
#: A session that trips a ceiling or detects a stall has spent nothing on the step that
#: reports it, and the decision it records must say so — an invocation count that guessed
#: high here would be spend the budget governor charges the day for and nobody incurred.
_UNSPENT = _Provenance()


class _Advance(Protocol):
    """Take exactly one mediated action on an open session."""

    def __call__(
        self,
        session: VariationSession,
        job: Job,
        now: float,
        *,
        repair_depth: int,
    ) -> Sequence[Event]: ...


class VariationInputError(ValueError):
    """A variation job no longer identifies a session or a located, actionable finding."""


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def variation_step_job(
    *,
    session_id: str,
    ordinal: int,
    book_id: str,
    branch_id: str,
    logical_id: str,
    finding_id: str,
    repair_depth: int,
    priority: int = VARIATION_STEP_PRIORITY,
) -> Job:
    """The unit of work for one mediated action.

    **`ordinal` is in the payload because it has to be in the id.** Job ids are content-derived
    and insertion is `INSERT OR IGNORE`, so a session that minted one job per step without a
    discriminator would enqueue its first step and then silently enqueue nothing ever again —
    the same trick `span_select_job_id` uses to distinguish itself from the tournament job that
    produced it. `repair_depth` rides along because the verification and propagation this
    session may eventually schedule must sit at the same depths the fixed path would have used;
    a session that lost it would restart the repair-propagate cascade from zero.
    """
    payload: dict[str, object] = {
        "kind": VARIATION_STEP,
        "session_id": session_id,
        "ordinal": ordinal,
        "book_id": book_id,
        "branch_id": branch_id,
        "logical_id": logical_id,
        "finding_id": finding_id,
        "repair_depth": repair_depth,
    }
    digest = input_digest_for(payload)
    job_id = f"varstep-{digest[:24]}"
    return Job(
        job_id=job_id,
        job_kind=VARIATION_STEP,
        idempotency_key=job_id,
        input_digest=digest,
        payload=payload,
        priority=priority,
    )


def render_variation_request(
    *,
    session: VariationSession,
    attempts: Sequence[VariationAttempt],
    knowledge: Sequence[KnowledgeItem],
    finding: Finding,
    text: str,
    start: int,
    end: int,
    call_class: str,
) -> CompletionRequest:
    """Everything the agent is shown, rebuilt from rows every step.

    **The lineage and the knowledge base are behind actions rather than always present**, and
    that is a design choice with two effects worth naming. It keeps the packet bounded, so a
    long session does not grow its own prompt until the context is mostly its own failures. And
    it makes consultation *observable*: a knowledge item that reached a prompt has a recorded
    consultation against it, which is the only way to tell later whether the knowledge base did
    anything at all. What is always present is the current complaint, the passage, and the last
    attempt's diagnostics — the minimum a next proposal needs.
    """
    latest = attempts[-1] if attempts else None
    last_line = (
        "No attempt has been evaluated yet."
        if latest is None
        else (
            f"Most recent attempt #{latest.ordinal} ({latest.outcome.value}): "
            f"{latest.diagnostics or 'no gate diagnostics recorded'}"
        )
    )
    sections = [
        "You are repairing one located complaint in one passage of a manuscript, one "
        "mediated action at a time. Reply with JSON naming exactly one action.",
        "",
        "Actions:",
        "  inspect_lineage    — show every attempt this session has already made.",
        "  consult_knowledge  — show what repeated failures on this passage have established.",
        "  propose_candidate  — supply `replacement`, the exact text to put in place of the "
        "cited passage, and `strategy` (structural or local_patch).",
        "  evaluate_candidate — run the deterministic gates over the proposal you last made.",
        "  commit             — request acceptance of a proposal that has passed the gates.",
        "  stop               — end the session, supplying `reason`.",
        "",
        "The gates are mechanical and pure: they check the passage still hashes as expected, "
        "that the replacement preserves everything outside the cited span, that the length "
        "does not run away, and that the patch does not claim more of the scene than a "
        "located complaint licenses. They do not judge quality and neither should you.",
        "",
        f"Finding: {finding.message}",
        f"Rule: {finding.rule_or_critic_id or finding.category}",
        f"Exact passage: {text[start:end]!r}",
        f"Before: {text[max(0, start - 300):start]!r}",
        f"After: {text[end:end + 300]!r}",
        "",
        f"Steps used: {session.steps} of {session.limits.max_steps}. "
        f"Evaluations used: {session.evaluations} of {session.limits.max_evaluations}.",
        last_line,
    ]
    if session.lineage_inspections:
        sections += ["", "Lineage:", render_lineage(attempts)]
    if session.consulted_item_ids:
        sections += ["", "Knowledge:", render_knowledge(knowledge)]
    return CompletionRequest(
        prompt="\n".join(sections),
        schema=ACTION_SCHEMA,
        profile="variation",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        call_class=call_class,
    )


def _action_gate(detail: str, *, passed: bool = True) -> GateOutcome:
    """What the mediated surface did with one response, recorded and never blocking.

    **Non-blocking is the load-bearing word.** A refused action — a malformed response, a commit
    requested for a candidate that has not passed the gates — must be recorded and must not veto
    the unit of work, because the unit of work is *one action* and it executed exactly as the
    mediated surface says it should. Making it blocking would send `decide` down the retry
    ladder, fail the step job, and spend the Conductor's attempt budget on a bound the session's
    own ceilings already hold; three of those poison the step job and orphan the session, which
    is the one failure here with no recovery short of an operator `revive`.
    """
    return GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id=_ACTION_RULE,
        passed=passed,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=False,
        detail=detail,
    )


def _session_gate(detail: str) -> GateOutcome:
    """The summary gate a closing session carries. Passing, exactly as a parked tournament's is.

    The session ran; what it produced is the outcome on its own row. A *failing* gate here would
    have to name a veto or escalate for want of one, and neither is true of a session that
    stopped because it was told to stop.
    """
    return GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id=_SESSION_RULE,
        passed=True,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        detail=detail,
    )


def _candidate_event(
    session: VariationSession,
    attempt: VariationAttempt,
    *,
    project_id: str,
    created_at: str,
    revision_id: str,
    actor: str,
) -> Event:
    """One attempt, on the log.

    The payload carries `session_id` and the attempt ordinal because event identity is a digest
    over type, revision and payload alone — not over the actor or the timestamp. Two attempts of
    one session against one revision would otherwise collapse onto a single row and the log
    would show one candidate where the store holds four.
    """
    return Event(
        event_type=EventType.MANUSCRIPT_CANDIDATE_CREATED,
        project_id=project_id,
        created_at=created_at,
        actor=actor,
        book_id=session.book_id,
        branch_id=session.branch_id,
        revision_id=revision_id,
        payload={
            "session_id": session.session_id,
            "attempt_id": attempt.attempt_id,
            "attempt_ordinal": attempt.ordinal,
            "logical_id": session.logical_id,
            "finding_id": session.finding_id,
            "strategy": attempt.strategy,
            "outcome": attempt.outcome.value,
            "accepted": attempt.outcome is AttemptOutcome.COMMITTED,
            "vetoes": [
                veto.value
                for gate in attempt.evaluation
                if not gate.passed
                for veto in gate.vetoes
            ],
        },
    )


def make_variation_repair_handler(
    registry: TextGenerator,
    store: VariationStore,
    project_id: str,
    *,
    policy: PatchPolicy | None = None,
    budget: BudgetPolicy | None = None,
    limits: SessionLimits | None = None,
    call_class: str = "generation",
) -> JobHandler:
    """Serve `repair_finding` by opening a bounded session and taking its first action.

    **An alternative handler for the same job kind, rather than a new kind.** The evaluation
    handler's licence predicate is untouched: a repair is still minted only for a finding that
    carries a primary span and either blocks deterministically or cites a current calibration.
    What changes is who serves the resulting unit — which is a composition decision the operator
    makes with a flag, and which keeps the two paths comparable on identical work.

    The opening tick takes the session's first action rather than only opening it. A tick spent
    on bookkeeping would make every session cost one more tick than the fixed path for reasons
    that have nothing to do with the loop, and the comparison this design owes would be measuring
    that instead.
    """
    advance = _make_advance(
        registry, store, project_id, policy=policy, budget=budget, call_class=call_class
    )
    session_limits = limits or SessionLimits()

    def handle(job: Job, now: float) -> Sequence[Event]:
        try:
            book_id = str(job.payload["book_id"])
            branch_id = str(job.payload["branch_id"])
            logical_id = str(job.payload["logical_id"])
            finding_id = str(job.payload["finding_id"])
            repair_depth = int(job.payload["repair_depth"])
        except (KeyError, TypeError, ValueError) as error:
            raise VariationInputError(f"repair job payload is incomplete: {error}") from error
        if not 1 <= repair_depth <= MAX_AUTO_REPAIRS:
            raise VariationInputError(f"invalid repair_depth: {repair_depth}")

        prior = store.latest_decision_for(job.job_id)
        if prior is not None and prior.outcome is Outcome.ACCEPT:
            return ()

        session_id = session_id_for(job.job_id, VariationObjective.CANDIDATE_REPAIR)
        session = store.variation_session(session_id)
        if session is None:
            revision = store.head(book_id, branch_id)
            if revision is None:
                raise VariationInputError(f"no head for {book_id}/{branch_id}")
            session = VariationSession(
                session_id=session_id,
                objective=VariationObjective.CANDIDATE_REPAIR,
                book_id=book_id,
                branch_id=branch_id,
                logical_id=logical_id,
                base_revision_id=revision.revision_id,
                opened_by_job_id=job.job_id,
                opened_at=_timestamp(now),
                opened_at_epoch=now,
                limits=session_limits,
                finding_id=finding_id,
            )
        if not session.is_open:
            return ()
        return advance(session, job, now, repair_depth=repair_depth)

    return handle


def make_variation_step_handler(
    registry: TextGenerator,
    store: VariationStore,
    project_id: str,
    *,
    policy: PatchPolicy | None = None,
    budget: BudgetPolicy | None = None,
    call_class: str = "generation",
) -> JobHandler:
    """Serve one already-open session's next action.

    Registered unconditionally in the composition root even when sessions are not being minted,
    for the reason every handler there is: an unhandled job kind fails three times and poisons
    silently, and a kind with no queued work costs nothing.
    """
    advance = _make_advance(
        registry, store, project_id, policy=policy, budget=budget, call_class=call_class
    )

    def handle(job: Job, now: float) -> Sequence[Event]:
        try:
            session_id = str(job.payload["session_id"])
            repair_depth = int(job.payload["repair_depth"])
        except (KeyError, TypeError, ValueError) as error:
            raise VariationInputError(f"variation step payload is incomplete: {error}") from error

        prior = store.latest_decision_for(job.job_id)
        if prior is not None and prior.outcome is Outcome.ACCEPT:
            return ()

        session = store.variation_session(session_id)
        if session is None:
            raise VariationInputError(f"no variation session {session_id}")
        # A closed session's step job is a no-op rather than an error: the step that closed the
        # session had already minted this one, and a queued job for a session that has since
        # committed is exactly the state a crash between the two would leave.
        if not session.is_open:
            return ()
        return advance(session, job, now, repair_depth=repair_depth)

    return handle


def _make_advance(
    registry: TextGenerator,
    store: VariationStore,
    project_id: str,
    *,
    policy: PatchPolicy | None,
    budget: BudgetPolicy | None,
    call_class: str,
) -> _Advance:
    """Build the one function both handlers are: take exactly one mediated action."""
    patch_policy = policy or PatchPolicy()
    budget_policy = budget or BudgetPolicy()

    def advance(
        session: VariationSession, job: Job, now: float, *, repair_depth: int
    ) -> Sequence[Event]:
        stamp = _timestamp(now)
        attempts = tuple(store.variation_attempts(session.session_id))
        config_digest = variation_config_digest(patch_policy, session.limits)

        def close(
            updated: VariationSession,
            outcome: SessionOutcome,
            reason: str,
            *,
            gates: tuple[GateOutcome, ...],
            verdict: Outcome,
            provenance: _Provenance = _UNSPENT,
            attempt_rows: Sequence[VariationAttempt] = (),
            extra_events: Sequence[Event] = (),
        ) -> Sequence[Event]:
            decision = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, gates),
                outcome=verdict,
                gates=gates,
                job_id=job.job_id,
                logical_id=session.logical_id,
                base_revision_id=session.base_revision_id,
                attempt=job.attempts,
                provider=provenance.provider,
                model=provenance.model,
                profile="variation",
                fell_back_from=provenance.fell_back_from,
                invocations=provenance.invocations,
                total_tokens=provenance.tokens,
                cost_usd=provenance.cost_usd,
                policy_config_digest=config_digest,
                reason=reason,
            )
            closed = updated.closed(outcome, at=stamp, detail=reason)
            decision_event = policy_decision_event(
                decision,
                project_id=project_id,
                created_at=stamp,
                book_id=session.book_id,
                branch_id=session.branch_id,
                revision_id=session.base_revision_id,
                details={"session_id": session.session_id, "session_outcome": outcome.value},
            )
            events = (*extra_events, decision_event)
            store.commit_variation_step(
                closed,
                at=stamp,
                attempts=attempt_rows,
                knowledge=derive_knowledge(closed, attempts, at=stamp),
                decision=decision,
                events=events,
            )
            return events

        def step(
            updated: VariationSession,
            gate: GateOutcome,
            *,
            provenance: _Provenance,
            attempt_rows: Sequence[VariationAttempt] = (),
            patches: Sequence[tuple[str, str]] = (),
            knowledge: Sequence[KnowledgeItem] = (),
            consulted: Sequence[str] = (),
            extra_events: Sequence[Event] = (),
        ) -> Sequence[Event]:
            """Record one non-terminal action and mint the next step, in one transaction.

            The decision is ACCEPT and the gate it carries is non-blocking, so the Conductor
            settles the step SUCCEEDED whatever the action's own result was. That is the honest
            reading: the unit of work is one mediated action, it executed, and whether the
            candidate it produced was any good is a fact recorded on the attempt row — where it
            carries the full gate vector, which a decision row could not.
            """
            gates = (gate,)
            decision = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, gates),
                outcome=Outcome.ACCEPT,
                gates=gates,
                job_id=job.job_id,
                logical_id=session.logical_id,
                base_revision_id=session.base_revision_id,
                attempt=job.attempts,
                provider=provenance.provider,
                model=provenance.model,
                profile="variation",
                fell_back_from=provenance.fell_back_from,
                invocations=provenance.invocations,
                total_tokens=provenance.tokens,
                cost_usd=provenance.cost_usd,
                policy_config_digest=config_digest,
                reason=gate.detail,
            )
            follow_up = variation_step_job(
                session_id=session.session_id,
                ordinal=updated.provider_calls + 1,
                book_id=session.book_id,
                branch_id=session.branch_id,
                logical_id=session.logical_id,
                finding_id=session.finding_id or "",
                repair_depth=repair_depth,
            )
            decision_event = policy_decision_event(
                decision,
                project_id=project_id,
                created_at=stamp,
                actor=provenance.provider or "litharness",
                book_id=session.book_id,
                branch_id=session.branch_id,
                revision_id=session.base_revision_id,
                details={"session_id": session.session_id, "step": updated.steps},
            )
            events = (*extra_events, decision_event)
            store.commit_variation_step(
                updated,
                at=stamp,
                attempts=attempt_rows,
                patches=patches,
                knowledge=knowledge,
                consulted=consulted,
                decision=decision,
                events=events,
                jobs=(follow_up,),
            )
            return events

        # -- the licence, re-checked every step ------------------------------------------
        #
        # The fixed path re-checks at claim time because a finding can be dismissed between
        # mint and run. A session spans many ticks, so it re-checks every step: a licence that
        # lapsed three steps ago must not buy a fourth proposal.
        finding = next(
            (
                candidate
                for candidate in store.findings(session.book_id, session.branch_id)
                if candidate.finding_id == session.finding_id
            ),
            None,
        )
        if finding is None:
            return close(
                session,
                SessionOutcome.STALE_BASE,
                f"finding {session.finding_id} is no longer in "
                f"{session.book_id}/{session.branch_id}",
                gates=(_session_gate("the complaint this session repairs is gone"),),
                verdict=Outcome.ACCEPT,
            )
        if not finding.blocks and not calibration_licenses(
            finding, store.calibrations(), today=stamp[:10]
        ):
            return close(
                session,
                SessionOutcome.STALE_BASE,
                f"finding {finding.finding_id} no longer licenses a repair",
                gates=(_session_gate("the repair licence lapsed while the session ran"),),
                verdict=Outcome.ACCEPT,
            )
        span = primary_span_of(finding)
        if span is None or span.source.logical_id != session.logical_id:
            return close(
                session,
                SessionOutcome.STALE_BASE,
                f"finding {finding.finding_id} has no usable primary span",
                gates=(_session_gate("the complaint no longer locates a passage"),),
                verdict=Outcome.ACCEPT,
            )

        revision = store.head(session.book_id, session.branch_id)
        if revision is None:
            raise VariationInputError(f"no head for {session.book_id}/{session.branch_id}")
        node = revision.node(session.logical_id)
        text = node.content
        if text is None:
            return close(
                session,
                SessionOutcome.STALE_BASE,
                f"repair target {session.logical_id} carries no text",
                gates=(_session_gate("the passage this session repairs carries no text"),),
                verdict=Outcome.ACCEPT,
            )
        start, end = int(span.start), int(span.end)

        # -- stalls and ceilings, both in front of the spend ------------------------------
        stall = detect_stall(attempts, malformed=session.malformed)
        if stall.stalled:
            assert stall.outcome is not None and stall.reason is not None
            return close(
                session,
                stall.outcome,
                stall.reason,
                gates=(_session_gate(stall.reason),),
                verdict=Outcome.PARK,
            )

        knowledge_items = store.knowledge_items(
            objective=session.objective, target_key=session.target_key
        )
        request = render_variation_request(
            session=session,
            attempts=attempts,
            knowledge=knowledge_items,
            finding=finding,
            text=text,
            start=start,
            end=end,
            call_class=call_class,
        )
        provider, _ = registry.resolve(call_class)
        projected = projected_tokens(
            provider.name, len(request.prompt), request.max_output_tokens
        )
        verdict = check_limits(session, now=now, projected_tokens=projected)
        if not verdict.allowed:
            assert verdict.limit is not None and verdict.reason is not None
            gate = GateOutcome(
                gate=GateKind.BUDGET,
                rule_or_critic_id=_LIMIT_RULE.format(limit=verdict.limit),
                passed=False,
                detail=verdict.reason,
            )
            return close(
                session,
                SessionOutcome.REFUSED_LIMIT,
                f"{verdict.limit}: {verdict.reason}",
                gates=(gate,),
                verdict=Outcome.PARK,
            )

        budget_verdict = budget_check(
            budget_policy,
            store.spend_on(stamp[:10]),
            provider=provider.name,
            prompt_chars=len(request.prompt),
            max_output_tokens=request.max_output_tokens,
        )
        if not budget_verdict.allowed:
            gate = GateOutcome(
                gate=GateKind.BUDGET,
                rule_or_critic_id=f"budget.{budget_verdict.ceiling}.v0",
                passed=False,
                detail=budget_verdict.reason,
            )
            exhausted = Event(
                event_type=EventType.BUDGET_EXHAUSTED,
                project_id=project_id,
                created_at=stamp,
                book_id=session.book_id,
                branch_id=session.branch_id,
                revision_id=session.base_revision_id,
                payload={
                    "job_id": job.job_id,
                    "session_id": session.session_id,
                    "reason": budget_verdict.reason,
                },
            )
            return close(
                session,
                SessionOutcome.REFUSED_BUDGET,
                budget_verdict.reason or "the day's budget refused this call",
                gates=(gate,),
                verdict=Outcome.PARK,
                extra_events=(exhausted,),
            )

        # -- one provider call, one action -----------------------------------------------
        result, resolution = registry.complete(request)
        spent = session.spent(
            provider_calls=1,
            tokens=result.usage.total,
            cost_usd=result.cost_usd or 0.0,
        )
        provenance = _Provenance(
            provider=result.provider,
            model=result.model,
            tokens=result.usage.total,
            invocations=result.invocations,
            cost_usd=result.cost_usd,
            fell_back_from=tuple(resolution.fell_back_from),
        )

        try:
            action: ActionRequest = parse_action(result.parsed)
        except MalformedAction as error:
            unusable = spent.spent(malformed=1)
            return step(
                unusable,
                _action_gate(f"unusable response: {error}", passed=False),
                provenance=provenance,
            )

        spent = spent.spent(steps=1)

        if action.kind is ActionKind.INSPECT_LINEAGE:
            return step(
                spent.inspecting_lineage(),
                _action_gate(
                    f"inspect_lineage over {len(attempts)} recorded attempt(s)"
                ),
                provenance=provenance,
            )

        if action.kind is ActionKind.CONSULT_KNOWLEDGE:
            item_ids = [item.item_id for item in knowledge_items]
            return step(
                spent.consulting(item_ids),
                _action_gate(
                    f"consult_knowledge matched {len(item_ids)} item(s) for "
                    f"{session.target_key}"
                ),
                consulted=item_ids,
                provenance=provenance,
            )

        if action.kind is ActionKind.STOP:
            return close(
                spent,
                SessionOutcome.STOPPED,
                action.reason or "the session stopped without giving a reason",
                gates=(_session_gate(f"stop: {action.reason or 'no reason given'}"),),
                verdict=Outcome.PARK,
                provenance=provenance,
            )

        if action.kind is ActionKind.PROPOSE_CANDIDATE:
            assert action.replacement is not None
            patch = _build_patch(
                node_content_sha256=node.content_sha256 or "",
                span=span,
                replacement=action.replacement,
                project_id=project_id,
                session=session,
                finding_id=finding.finding_id,
                job=job,
                created_at=stamp,
                actor=result.provider,
                model=result.model,
            )
            digest = patch_digest_for(patch)
            ordinal = len(attempts) + 1
            proposal = VariationAttempt(
                attempt_id=attempt_id_for(session.session_id, ordinal, digest),
                session_id=session.session_id,
                ordinal=ordinal,
                base_revision_id=revision.revision_id,
                patch_digest=digest,
                outcome=AttemptOutcome.PROPOSED,
                created_at=stamp,
                parent_attempt_id=attempts[-1].attempt_id if attempts else None,
                strategy=action.strategy or "unclassified",
                diagnostics="proposed, not yet evaluated",
                provider=result.provider,
                model=result.model,
                tokens=result.usage.total,
                cost_usd=result.cost_usd,
                wall_ms=result.wall_ms,
            )
            # A proposal supersedes whatever was still in flight. Recorded rather than
            # deleted, because an attempt the session walked away from is evidence about the
            # session and the row is the only place it survives.
            superseded = tuple(
                replace(attempt, outcome=AttemptOutcome.SUPERSEDED)
                for attempt in attempts
                if not attempt.outcome.is_terminal
            )
            payload = json.dumps(lc.to_jsonable(patch), sort_keys=True, ensure_ascii=False)
            return step(
                spent,
                _action_gate(
                    f"propose_candidate #{ordinal} [{proposal.strategy}] "
                    f"replacing {end - start} character(s)"
                ),
                attempt_rows=(*superseded, proposal),
                patches=((digest, payload),),
                extra_events=(
                    _candidate_event(
                        session,
                        proposal,
                        project_id=project_id,
                        created_at=stamp,
                        revision_id=revision.revision_id,
                        actor=result.provider,
                    ),
                ),
                provenance=provenance,
            )

        pending = next(
            (
                attempt
                for attempt in reversed(attempts)
                if attempt.outcome is AttemptOutcome.PROPOSED
            ),
            None,
        )
        if action.kind is ActionKind.EVALUATE_CANDIDATE:
            if pending is None:
                return step(
                    spent,
                    _action_gate(
                        "evaluate_candidate with no proposal outstanding", passed=False
                    ),
                    provenance=provenance,
                )
            outcome = apply_patch(revision, _load_patch(store, pending), patch_policy)
            gates = gates_for_patch(outcome)
            # Read from the patch outcome, not from the projected gate: `gates_for_patch`
            # joins every veto's detail into one string, and the pairing of a veto with the
            # reason it fired is exactly what the next proposal needs.
            diagnostics = (
                "; ".join(f"{record.veto.value}: {record.detail}" for record in outcome.vetoes)
                or "every mechanical gate passed"
            )
            evaluated = replace(
                pending,
                evaluation=gates,
                diagnostics=diagnostics,
                outcome=(
                    AttemptOutcome.EVALUATED
                    if outcome.accepted
                    else AttemptOutcome.REJECTED_GATE
                ),
                evaluations=pending.evaluations + 1,
            )
            after = tuple(
                evaluated if attempt.attempt_id == evaluated.attempt_id else attempt
                for attempt in attempts
            )
            return step(
                spent.spent(evaluations=1),
                _action_gate(f"evaluate_candidate #{evaluated.ordinal}: {diagnostics}"),
                attempt_rows=(evaluated,),
                knowledge=derive_knowledge(session, after, at=stamp),
                extra_events=(
                    _candidate_event(
                        session,
                        evaluated,
                        project_id=project_id,
                        created_at=stamp,
                        revision_id=revision.revision_id,
                        actor=result.provider,
                    ),
                ),
                provenance=provenance,
            )

        # -- commit: a *request*, judged by the existing policy path and nothing else -----
        candidate = next(
            (
                attempt
                for attempt in reversed(attempts)
                if attempt.outcome is AttemptOutcome.EVALUATED and attempt.gates_passed
            ),
            None,
        )
        if candidate is None:
            return step(
                spent,
                _action_gate(
                    "commit with no evaluated candidate that passed every blocking gate",
                    passed=False,
                ),
                provenance=provenance,
            )

        outcome = apply_patch(revision, _load_patch(store, candidate), patch_policy)
        commit_gates = gates_for_patch(outcome)
        settled, reason = decide(
            commit_gates,
            job_id=job.job_id,
            attempt=job.attempts,
            max_attempts=job.max_attempts,
        )
        if not (outcome.accepted and outcome.revision is not None):
            # The head moved between the evaluation and the request. The candidate is stale
            # rather than wrong; the session keeps its ceilings and proposes again against the
            # base it can now see.
            diagnostics = (
                "; ".join(f"{record.veto.value}: {record.detail}" for record in outcome.vetoes)
                or reason
                or "the commit request was refused"
            )
            refused = replace(
                candidate,
                evaluation=commit_gates,
                diagnostics=diagnostics,
                outcome=AttemptOutcome.REJECTED_GATE,
            )
            after = tuple(
                refused if attempt.attempt_id == refused.attempt_id else attempt
                for attempt in attempts
            )
            return step(
                spent,
                _action_gate(f"commit refused for #{refused.ordinal}: {diagnostics}", passed=False),
                attempt_rows=(refused,),
                knowledge=derive_knowledge(session, after, at=stamp),
                provenance=provenance,
            )

        assert outcome.node_after is not None
        records = tuple(store.state_records(session.book_id, session.branch_id))
        extracted = extract_state(
            outcome.node_after.content or "",
            known=records,
            project_id=project_id,
            book_id=session.book_id,
            branch_id=session.branch_id,
            logical_id=session.logical_id,
            version_id=node_version_id(outcome.node_after),
            replacing_logical_id=session.logical_id,
        )
        verification = evaluation_job_for(
            book_id=session.book_id,
            branch_id=session.branch_id,
            revision_id=outcome.revision.revision_id,
            logical_id=session.logical_id,
            verification_of_finding_id=finding.finding_id,
            repair_depth=repair_depth,
        )
        # The same verification and the same propagation the fixed path schedules, from the
        # same function. A session-committed repair that re-checked only itself would leave
        # every scene the change reaches stale — the defect §17's Stage 2 closed, and the one
        # a second commit path would silently reopen.
        propagated, reached = propagated_evaluations(
            records,
            extracted,
            revision=outcome.revision,
            book_id=session.book_id,
            branch_id=session.branch_id,
            logical_id=session.logical_id,
            repair_depth=repair_depth,
        )
        gates = (
            *commit_gates,
            _action_gate(
                f"commit accepted attempt #{candidate.ordinal} after "
                f"{spent.steps} action(s) and {spent.evaluations} evaluation(s)"
            ),
        )
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, gates),
            outcome=settled,
            gates=gates,
            job_id=job.job_id,
            logical_id=session.logical_id,
            base_revision_id=revision.revision_id,
            resulting_revision_id=outcome.revision.revision_id,
            attempt=job.attempts,
            provider=result.provider,
            model=result.model,
            profile="variation",
            fell_back_from=tuple(resolution.fell_back_from),
            invocations=result.invocations,
            total_tokens=result.usage.total,
            cost_usd=result.cost_usd,
            policy_config_digest=config_digest,
            reason=reason,
        )
        committed = replace(candidate, outcome=AttemptOutcome.COMMITTED)
        closed = spent.closed(
            SessionOutcome.COMMITTED,
            at=stamp,
            detail=(
                f"attempt {candidate.ordinal} of {len(attempts)} committed after "
                f"{spent.steps} action(s)"
            ),
        )
        acceptance = Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=project_id,
            created_at=stamp,
            actor=result.provider,
            book_id=session.book_id,
            branch_id=session.branch_id,
            revision_id=outcome.revision.revision_id,
            payload={
                "decision_id": decision.decision_id,
                "job_id": job.job_id,
                "session_id": session.session_id,
                "attempt_ordinal": candidate.ordinal,
                "logical_id": session.logical_id,
                "finding_id": finding.finding_id,
                "accepted": True,
                "repair": True,
                "variation": True,
                "parent_revision_id": revision.revision_id,
                "touched_spans": [list(offsets) for offsets in outcome.touched_spans],
            },
        )
        decision_event = policy_decision_event(
            decision,
            project_id=project_id,
            created_at=stamp,
            actor=result.provider,
            book_id=session.book_id,
            branch_id=session.branch_id,
            revision_id=outcome.revision.revision_id,
            details={
                "session_id": session.session_id,
                "finding_id": finding.finding_id,
            },
        )
        events: tuple[Event, ...] = (acceptance, decision_event)
        if reached:
            events += (
                Event(
                    event_type=EventType.IMPACT_ANALYZED,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=session.book_id,
                    branch_id=session.branch_id,
                    revision_id=outcome.revision.revision_id,
                    causation_id=job.job_id,
                    payload={
                        "job_id": job.job_id,
                        "session_id": session.session_id,
                        "logical_id": session.logical_id,
                        "reached": list(reached),
                        "enqueued": [str(unit.payload["logical_id"]) for unit in propagated],
                        "repair_depth": repair_depth,
                    },
                ),
            )
        store.commit_variation_step(
            closed,
            at=stamp,
            attempts=(committed,),
            knowledge=derive_knowledge(session, attempts, at=stamp),
            decision=decision,
            events=events,
            jobs=(verification, *propagated),
            revision=outcome.revision,
            state_records=extracted,
            retract_state_for_nodes=(session.logical_id,),
        )
        return (decision_event,)

    return advance


def _build_patch(
    *,
    node_content_sha256: str,
    span: lc.EvidenceSpan,
    replacement: str,
    project_id: str,
    session: VariationSession,
    finding_id: str,
    job: Job,
    created_at: str,
    actor: str,
    model: str,
) -> lc.BoundedPatch:
    """One span replacement, licensed by the finding that located it.

    Identical in shape to the fixed path's patch and deliberately so: the session's authority
    over prose is exactly the fixed path's authority, and the only thing it adds is more tries
    at the same bounded edit. `licensed_by_finding_id` is what keeps the deletion guarantee, and
    the target span is the finding's own — the agent supplies replacement text and never a
    location.
    """
    return lc.BoundedPatch(
        meta=lc.ArtifactMeta(
            schema_version="1.0.0",
            artifact_id=f"patch-{job.job_id}",
            artifact_kind="bounded_patch",
            created_at=created_at,
            actor=actor,
            tool=lc.ToolIdentity(name=actor, version=model),
        ),
        target=lc.ResourceRef(
            project_id=project_id,
            book_id=session.book_id,
            branch_id=session.branch_id,
            logical_id=session.logical_id,
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            version_id=span.source.version_id,
        ),
        base_version_id=span.source.version_id or "",
        base_content_sha256=node_content_sha256,
        ops=[
            lc.PatchOp(
                kind=lc.PatchOpKind.REPLACE_SPAN,
                target_span=span,
                new_text=replacement,
            )
        ],
        idempotency_key=job.idempotency_key or job.job_id,
        licensed_by_finding_id=finding_id,
    )


def _load_patch(store: VariationStore, attempt: VariationAttempt) -> lc.BoundedPatch:
    """The patch an attempt proposed, as it was proposed.

    Read back rather than rebuilt. Rebuilding would produce whatever this code would construct
    today against whatever the head is now, which is precisely the substitution that would make
    a re-evaluation silently disagree with the evaluation it is meant to repeat.
    """
    payload = store.variation_patch(attempt.patch_digest)
    if payload is None:
        raise VariationInputError(
            f"attempt {attempt.attempt_id} references patch {attempt.patch_digest}, "
            "which is not in the store"
        )
    patch: lc.BoundedPatch = lc.from_jsonable(lc.BoundedPatch, payload)
    return patch


__all__ = [
    "ACTION_SCHEMA",
    "VARIATION_STEP",
    "VARIATION_STEP_PRIORITY",
    "VariationInputError",
    "make_variation_repair_handler",
    "make_variation_step_handler",
    "render_variation_request",
    "variation_step_job",
]
