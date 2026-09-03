"""Reader checkpoints and the licensed path from evidence to story planning.

The observation request is frozen onto a durable job.  Complete panels remain inert while
their mechanism is experimental; a qualified panel may be interpreted into one immutable
intervention, which can submit a machine-authored directive through the normal plan lane.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from litharness.application import readers
from litharness.application.conductor import JobHandler
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import PlanningStore, ReaderControlStore, TextGenerator
from litharness.domain.audience import Reader
from litharness.domain.budget import BudgetPolicy, BudgetVerdict
from litharness.domain.budget import check as budget_check
from litharness.domain.directives import Directive, DirectiveKind, directive_id_for
from litharness.domain.directors import machine_author
from litharness.domain.editorial import (
    EditorialDecision,
    EditorialIntervention,
    ReaderMechanism,
    ReaderMechanismStatus,
    ReaderObservation,
    evidence_digest_for,
    intervention_id_for,
    mechanism_version_id_for,
    observation_id_for,
)
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.generation import CompletionRequest, Sampler
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.nodes import NodeKind
from litharness.domain.plan_refinement import PlanRevision
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decide,
    decision_id_for,
)
from litharness.domain.revision import Revision
from litharness.domain.serials import SerialShape
from litharness.domain.text import content_hash, stop_point

READER_OBSERVE = "reader_observe"
EDITORIAL_INTERPRET = "editorial_interpret"
READER_OBSERVE_PRIORITY = 250
EDITORIAL_INTERPRET_PRIORITY = 450
MECHANISM_ID = "reader.anticipation.v0"
CONTROLLER_PROFILE = "editorial.reader.v0"

EDITORIAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "need", "rationale", "directive_body", "target_logical_ids"],
    "properties": {
        "decision": {
            "type": "string",
            "enum": [decision.value for decision in EditorialDecision],
        },
        "need": {"type": "string"},
        "rationale": {"type": "string"},
        "directive_body": {"type": "string"},
        "target_logical_ids": {"type": "array", "items": {"type": "string"}},
    },
}


class ReaderControlOutputError(ValueError):
    pass


def _response_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [text for item in value.values() for text in _response_strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _response_strings(item)]
    return []


def copies_reader_language(body: str, responses: Sequence[Mapping[str, Any]]) -> bool:
    """Whether direction repeats a reader's phrasing instead of abstracting its need."""
    body_words = re.findall(r"[\w']+", body.casefold())
    if len(body_words) < 6:
        return False
    rendered = " ".join(body_words)
    for response in responses:
        for text in _response_strings(response):
            words = re.findall(r"[\w']+", text.casefold())
            if len(words) >= 6 and " ".join(words) in rendered:
                return True
            if len(words) >= 8:
                for index in range(len(words) - 7):
                    if " ".join(words[index : index + 8]) in rendered:
                        return True
    return False


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _steering(roster: Sequence[Reader]) -> tuple[Reader, ...]:
    """The roster, if every reader on it steers. A measurement reader in a steering panel would
    put a reader that judges the prose among those that shape it (§97.1)."""
    wrong = [reader.reader_id for reader in roster if reader.pool != readers.STEERING]
    if wrong:
        raise ValueError(f"{wrong} are not steering readers and may not sit on a checkpoint panel")
    return tuple(roster)


def mechanism_spec_digest(roster: Sequence[Reader]) -> str:
    """The digest that names a mechanism version, over the steering roster it reads with.

    **The roster is an argument since stage-0 §221**, when the LitRPG readers moved behind
    `packs/litrpg` and the application layer stopped reaching for a module constant. The
    persona system text was always hashed here, so for the same readers the bytes are the same:
    every stored `spec_digest` still resolves and every frozen job still validates. The
    composition root passes the pack's steering roster.
    """
    return payload_digest(
        {
            "mechanism_id": MECHANISM_ID,
            "profile": readers.ANTICIPATE_PROFILE,
            "schema": readers.ANTICIPATION_SCHEMA,
            "reader_personas": [
                {"reader_id": reader.reader_id, "system": reader.system()}
                for reader in _steering(roster)
            ],
            "stop_rule": "text.stop_point.v0",
            "context_rule": {
                "recent_full_chapters": readers.RECENT_FULL_CHAPTERS,
                "recalled_summary_chapters": readers.RECALLED_SUMMARY_CHAPTERS,
            },
        }
    )


def experimental_mechanism(*, registered_at: str, roster: Sequence[Reader]) -> ReaderMechanism:
    spec = mechanism_spec_digest(roster)
    status = ReaderMechanismStatus.EXPERIMENTAL
    return ReaderMechanism(
        mechanism_id=MECHANISM_ID,
        version_id=mechanism_version_id_for(MECHANISM_ID, status, spec),
        status=status,
        spec_digest=spec,
        registered_at=registered_at,
    )


def checkpoint_id_for(revision_id: str, logical_id: str, chapter_index: int) -> str:
    digest = payload_digest(
        {
            "revision_id": revision_id,
            "logical_id": logical_id,
            "chapter_index": chapter_index,
        }
    )
    return f"rcheck-{sha256(digest.encode()).hexdigest()[:24]}"


def _request_payload(request: CompletionRequest) -> dict[str, Any]:
    return {
        "prompt": request.prompt,
        "system": request.system,
        "schema": request.schema,
        "max_output_tokens": request.max_output_tokens,
        "profile": request.profile,
        "timeout_seconds": request.timeout_seconds,
        "call_class": request.call_class,
        "sampler": asdict(request.sampler) if request.sampler is not None else None,
        "allowed_tools": list(request.allowed_tools),
    }


def _request_from(payload: object) -> CompletionRequest:
    if not isinstance(payload, Mapping):
        raise ReaderControlOutputError("reader job has no frozen request")
    sampler = payload.get("sampler")
    return CompletionRequest(
        prompt=str(payload.get("prompt") or ""),
        system=str(payload["system"]) if payload.get("system") is not None else None,
        schema=dict(payload["schema"]) if isinstance(payload.get("schema"), Mapping) else None,
        max_output_tokens=int(payload.get("max_output_tokens") or 4096),
        profile=str(payload.get("profile") or "default"),
        timeout_seconds=float(payload.get("timeout_seconds") or 300.0),
        call_class=str(payload.get("call_class") or "generation"),
        sampler=Sampler(**dict(sampler)) if isinstance(sampler, Mapping) else None,
        allowed_tools=tuple(str(item) for item in (payload.get("allowed_tools") or ())),
    )


def _prior_memory(
    observations: Sequence[ReaderObservation], reader_id: str, mechanism_version_id: str
) -> str:
    earlier = [
        item
        for item in observations
        if item.reader_id == reader_id
        and item.mechanism_version_id == mechanism_version_id
    ]
    if not earlier:
        return ""
    return json.dumps(earlier[-1].response, sort_keys=True, ensure_ascii=False)


def reader_jobs_for_checkpoint(
    revision: Revision,
    logical_id: str,
    *,
    chapter_index: int,
    summaries: Mapping[str, Mapping[str, str]],
    prior_observations: Sequence[ReaderObservation],
    mechanism: ReaderMechanism,
    shape: SerialShape,
    roster: Sequence[Reader],
) -> tuple[Job, ...]:
    """Freeze one steering request per reader of `roster` at a completed chapter boundary."""
    if mechanism.status is ReaderMechanismStatus.WITHDRAWN:
        return ()
    node = revision.node(logical_id)
    prose = (node.content or "").strip()
    if not prose:
        return ()
    try:
        passage = stop_point(prose)
    except ValueError:
        passage = prose
    current_summaries = {
        scene.logical_id: summary
        for scene in revision.in_reading_order()
        if scene.kind is NodeKind.SCENE
        and scene.content
        and (summary := summaries.get(scene.logical_id, {}).get(content_hash(scene.content)))
        is not None
    }
    context = readers.accumulated_passage(
        revision,
        logical_id,
        passage,
        summaries=current_summaries,
        shape=shape,
    )
    checkpoint_id = checkpoint_id_for(revision.revision_id, logical_id, chapter_index)
    panel = _steering(roster)
    jobs: list[Job] = []
    for reader in panel:
        request = readers.render_anticipation_request(
            reader,
            context,
            prior_memory=_prior_memory(
                prior_observations, reader.reader_id, mechanism.version_id
            ),
        )
        request_payload = _request_payload(request)
        payload: dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "mechanism_version_id": mechanism.version_id,
            "book_id": revision.book_id,
            "branch_id": revision.branch_id,
            "revision_id": revision.revision_id,
            "logical_id": logical_id,
            "chapter_index": chapter_index,
            "reader_id": reader.reader_id,
            "pool": reader.pool,
            "panel_size": len(panel),
            "source_content_hash": node.content_sha256 or content_hash(node.content or ""),
            "persona_digest": payload_digest(
                {"reader_id": reader.reader_id, "system": reader.system()}
            ),
            "prompt_digest": payload_digest({"prompt": request.prompt}),
            "system_digest": payload_digest({"system": request.effective_system}),
            "schema_digest": payload_digest({"schema": request.schema}),
            "context_digest": payload_digest({"context": context}),
            "reader_context": context,
            "request": request_payload,
        }
        digest = input_digest_for(payload)
        job_id = f"reader-{sha256(digest.encode()).hexdigest()[:24]}"
        jobs.append(
            Job(
                job_id=job_id,
                job_kind=READER_OBSERVE,
                idempotency_key=job_id,
                payload=payload,
                input_digest=digest,
                priority=READER_OBSERVE_PRIORITY,
            )
        )
    return tuple(jobs)


def _budget_gate(verdict: BudgetVerdict) -> GateOutcome:
    return GateOutcome(
        gate=GateKind.BUDGET,
        rule_or_critic_id=f"budget.{verdict.ceiling}.v0",
        passed=verdict.allowed,
        detail=verdict.reason,
    )


def _budget_refusal(
    store: ReaderControlStore,
    job: Job,
    request: CompletionRequest,
    verdict: BudgetVerdict,
    *,
    now: float,
    profile: str,
    project_id: str,
) -> Sequence[Event]:
    gate = _budget_gate(verdict)
    decision = PolicyDecision(
        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
        outcome=Outcome.PARK,
        gates=(gate,),
        job_id=job.job_id,
        attempt=job.attempts,
        profile=profile,
        policy_config_digest=payload_digest(
            {"profile": profile, "request": _request_payload(request)}
        ),
        reason=verdict.reason,
    )
    store.record_decision(decision, decided_at=_stamp(now))
    return (
        Event(
            event_type=EventType.BUDGET_EXHAUSTED,
            project_id=project_id,
            created_at=_stamp(now),
            book_id=str(job.payload["book_id"]) if job.payload.get("book_id") else None,
            branch_id=str(job.payload["branch_id"]) if job.payload.get("branch_id") else None,
            revision_id=(
                str(job.payload["revision_id"]) if job.payload.get("revision_id") else None
            ),
            payload={
                "job_id": job.job_id,
                "ceiling": verdict.ceiling,
                "reason": verdict.reason,
                "projected_tokens": verdict.projected_tokens,
            },
        ),
    )


def _shape_decision(
    job: Job,
    *,
    passed: bool,
    result: Any,
    resolution: Any,
    profile: str,
    policy_digest: str,
    detail: str | None = None,
) -> PolicyDecision:
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.reader_control_json.v0",
        passed=passed,
        detail=None if passed else (detail or "provider did not return the requested object"),
    )
    outcome, reason = decide(
        (gate,), job_id=job.job_id, attempt=job.attempts, max_attempts=job.max_attempts
    )
    return PolicyDecision(
        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
        outcome=outcome,
        gates=(gate,),
        job_id=job.job_id,
        attempt=job.attempts,
        provider=result.provider,
        model=result.model,
        profile=profile,
        fell_back_from=tuple(resolution.fell_back_from),
        invocations=result.invocations,
        total_tokens=result.usage.total,
        cost_usd=result.cost_usd,
        policy_config_digest=policy_digest,
        reason=reason,
    )


def _validate_observation_job(
    store: ReaderControlStore,
    job: Job,
    request: CompletionRequest,
    roster: Sequence[Reader],
) -> None:
    if not job.input_digest or job.input_digest != input_digest_for(job.payload):
        raise ReaderControlOutputError("reader job input digest does not match its payload")
    reader_id = str(job.payload.get("reader_id") or "")
    persona = next(
        (item for item in _steering(roster) if item.reader_id == reader_id),
        None,
    )
    if persona is None or job.payload.get("pool") != readers.STEERING:
        raise ReaderControlOutputError("reader observation job is not from the steering roster")
    mechanism = store.reader_mechanism(str(job.payload.get("mechanism_version_id") or ""))
    current = store.current_reader_mechanism(mechanism.mechanism_id)
    if (
        mechanism.status is ReaderMechanismStatus.WITHDRAWN
        or (current is not None and current.status is ReaderMechanismStatus.WITHDRAWN)
        or mechanism.spec_digest != mechanism_spec_digest(roster)
    ):
        raise ReaderControlOutputError("reader observation job names an unsupported mechanism")
    if (
        request.system != persona.system()
        or request.profile != readers.ANTICIPATE_PROFILE
        or request.schema != readers.ANTICIPATION_SCHEMA
    ):
        raise ReaderControlOutputError("reader observation job persona or profile has drifted")
    context = job.payload.get("reader_context")
    if not isinstance(context, str) or not context.strip():
        raise ReaderControlOutputError("reader observation job has no frozen reading context")
    expected = {
        "persona_digest": payload_digest(
            {"reader_id": persona.reader_id, "system": persona.system()}
        ),
        "prompt_digest": payload_digest({"prompt": request.prompt}),
        "system_digest": payload_digest({"system": request.effective_system}),
        "schema_digest": payload_digest({"schema": request.schema}),
        "context_digest": payload_digest({"context": context}),
    }
    for key, digest in expected.items():
        if job.payload.get(key) != digest:
            raise ReaderControlOutputError(f"reader job {key} does not match its frozen input")
    revision = store.load_revision(str(job.payload.get("revision_id") or ""))
    if (revision.book_id, revision.branch_id) != (
        job.payload.get("book_id"),
        job.payload.get("branch_id"),
    ):
        raise ReaderControlOutputError("reader job revision is outside its recorded branch")
    node = revision.node(str(job.payload.get("logical_id") or ""))
    source_hash = node.content_sha256 or content_hash(node.content or "")
    if source_hash != job.payload.get("source_content_hash"):
        raise ReaderControlOutputError("reader job source hash does not match its revision")


def make_reader_observation_handler(
    registry: TextGenerator,
    store: ReaderControlStore,
    project_id: str,
    *,
    roster: Sequence[Reader],
    budget: BudgetPolicy | None = None,
) -> JobHandler:
    """The handler that answers one frozen steering request, validated against `roster`."""
    budget_policy = budget or BudgetPolicy()
    panel = _steering(roster)

    def handle(job: Job, now: float) -> Sequence[Event]:
        existing = store.reader_observation_for_job(job.job_id)
        if existing is not None:
            return ()
        request = _request_from(job.payload.get("request"))
        _validate_observation_job(store, job, request, panel)
        provider, _ = registry.resolve(request.call_class)
        verdict = budget_check(
            budget_policy,
            store.spend_on(_stamp(now)[:10]),
            provider=provider.name,
            prompt_chars=request.input_chars,
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            return _budget_refusal(
                store,
                job,
                request,
                verdict,
                now=now,
                profile=request.profile,
                project_id=project_id,
            )
        result, resolution = registry.complete(request)
        parsed = result.parsed if isinstance(result.parsed, Mapping) else None
        policy_digest = payload_digest(
            {
                "mechanism_version_id": job.payload.get("mechanism_version_id"),
                "request": _request_payload(request),
            }
        )
        decision = _shape_decision(
            job,
            passed=parsed is not None,
            result=result,
            resolution=resolution,
            profile=request.profile,
            policy_digest=policy_digest,
        )
        if parsed is None:
            store.record_decision(decision, decided_at=_stamp(now))
            return (policy_decision_event(decision, project_id=project_id, created_at=_stamp(now)),)
        observation = ReaderObservation(
            observation_id=observation_id_for(job.job_id),
            source_job_id=job.job_id,
            checkpoint_id=str(job.payload["checkpoint_id"]),
            mechanism_version_id=str(job.payload["mechanism_version_id"]),
            book_id=str(job.payload["book_id"]),
            branch_id=str(job.payload["branch_id"]),
            revision_id=str(job.payload["revision_id"]),
            logical_id=str(job.payload["logical_id"]),
            reader_id=str(job.payload["reader_id"]),
            pool=str(job.payload["pool"]),
            panel_size=int(job.payload["panel_size"]),
            source_content_hash=str(job.payload["source_content_hash"]),
            persona_digest=str(job.payload["persona_digest"]),
            prompt_digest=str(job.payload["prompt_digest"]),
            system_digest=str(job.payload["system_digest"]),
            schema_digest=str(job.payload["schema_digest"]),
            context_digest=str(job.payload["context_digest"]),
            profile=request.profile,
            provider=result.provider,
            model=result.model,
            response=dict(parsed),
            observed_at=_stamp(now),
        )
        store.record_reader_observation(observation, decision=decision, decided_at=_stamp(now))
        return (
            policy_decision_event(
                decision,
                project_id=project_id,
                created_at=_stamp(now),
                actor=result.provider,
                book_id=observation.book_id,
                branch_id=observation.branch_id,
                revision_id=observation.revision_id,
            ),
        )

    return handle


def render_editorial_request(
    observations: Sequence[ReaderObservation],
    plan: PlanRevision,
    *,
    future_scene_ids: Sequence[str],
) -> CompletionRequest:
    locked = [
        {"logical_id": item.logical_id, "kind": item.kind.value, "text": item.text}
        for item in plan.items
        if item.locked
    ]
    ordinary = [
        {
            "logical_id": item.logical_id,
            "kind": item.kind.value,
            "text": item.text,
            "scope": item.scope.logical_id if item.scope else None,
        }
        for item in plan.items
        if not item.locked
    ]
    prompt = json.dumps(
        {
            "reader_observations": [
                {"reader_id": item.reader_id, "response": item.response} for item in observations
            ],
            "author_locked_decisions": locked,
            "current_plan": ordinary,
            "eligible_future_scene_ids": list(future_scene_ids),
            "decision_meanings": {
                "satisfy": "plan toward the underlying reader desire",
                "subvert": "meet the underlying desire by an unexpected story event",
                "defer": "the desire is useful but should be paid later",
                "refuse": "following it would weaken this book or merely average personas",
                "challenge_lock": "the evidence conflicts with an author lock; surface it, "
                "but do not override it",
            },
        },
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
    )
    return CompletionRequest(
        prompt=prompt,
        system=(
            "You are an editorial controller, not a prose critic and not a writer. Infer the "
            "shared underlying story need, if any, behind these independent observations. "
            "Reader predictions and wishes are evidence, not votes and not text to copy. "
            "Author-locked decisions are feasibility constraints. If the evidence conflicts "
            "with one, choose challenge_lock and describe the conflict; never override it. "
            "Use satisfy or subvert only when a concrete change to future story planning is "
            "warranted. For those two decisions, directive_body must state the desired story "
            "effect without reader quotations or prose-style advice. For every other decision "
            "directive_body must be empty. Return only the requested JSON."
        ),
        schema=EDITORIAL_SCHEMA,
        max_output_tokens=1400,
        profile=CONTROLLER_PROFILE,
        call_class="generation",
    )


def editorial_job_id(
    checkpoint_id: str, mechanism_version_id: str, plan_revision_id: str
) -> str:
    digest = payload_digest(
        {
            "checkpoint_id": checkpoint_id,
            "mechanism_version_id": mechanism_version_id,
            "plan_revision_id": plan_revision_id,
        }
    )
    return f"editorial-{sha256(digest.encode()).hexdigest()[:24]}"


def enqueue_ready_editorial_panel(store: PlanningStore) -> bool:
    """Reconcile one complete, qualified panel into a frozen controller job."""
    for panel in store.ready_reader_panels():
        observations = store.reader_observations(
            panel["book_id"],
            panel["branch_id"],
            checkpoint_id=panel["checkpoint_id"],
            mechanism_version_id=panel["mechanism_version_id"],
        )
        plan = store.plan_revision(panel["book_id"], panel["branch_id"])
        head = store.head(panel["book_id"], panel["branch_id"])
        if plan is None or head is None:
            continue
        job_id = editorial_job_id(
            panel["checkpoint_id"],
            panel["mechanism_version_id"],
            plan.plan_revision_id,
        )
        if store.has_job(job_id):
            continue
        future_ids = [
            node.logical_id
            for node in head.in_reading_order()
            if node.kind is NodeKind.SCENE and not (node.content or "").strip()
        ]
        request = render_editorial_request(observations, plan, future_scene_ids=future_ids)
        evidence_ids = tuple(item.observation_id for item in observations)
        payload: dict[str, Any] = {
            **panel,
            "plan_revision_id": plan.plan_revision_id,
            "evidence_observation_ids": list(evidence_ids),
            "evidence_digest": evidence_digest_for(evidence_ids),
            "eligible_future_scene_ids": future_ids,
            "request": _request_payload(request),
        }
        if store.enqueue(
            Job(
                job_id=job_id,
                job_kind=EDITORIAL_INTERPRET,
                idempotency_key=job_id,
                payload=payload,
                input_digest=input_digest_for(payload),
                priority=EDITORIAL_INTERPRET_PRIORITY,
            )
        ):
            return True
    return False


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReaderControlOutputError(f"editorial result requires {key}")
    return value.strip()


def _parse_editorial_payload(
    payload: Mapping[str, Any],
    *,
    eligible_scene_ids: set[str],
    reader_responses: Sequence[Mapping[str, Any]],
) -> tuple[EditorialDecision, str, str, str, tuple[str, ...]]:
    try:
        decision = EditorialDecision(payload["decision"])
    except (KeyError, TypeError, ValueError) as error:
        raise ReaderControlOutputError("editorial result has an invalid decision") from error
    need = _required_text(payload, "need")
    rationale = _required_text(payload, "rationale")
    raw_targets = payload.get("target_logical_ids")
    if not isinstance(raw_targets, list) or not all(isinstance(x, str) for x in raw_targets):
        raise ReaderControlOutputError("editorial target_logical_ids must be strings")
    targets = tuple(dict.fromkeys(str(x) for x in raw_targets))
    outside = sorted(set(targets) - eligible_scene_ids)
    if outside:
        raise ReaderControlOutputError(
            f"editorial result targets scenes that were not future work: {outside}"
        )
    body = str(payload.get("directive_body") or "").strip()
    if decision.dispatches_direction and not body:
        raise ReaderControlOutputError("satisfy/subvert requires directive_body")
    if not decision.dispatches_direction and body:
        raise ReaderControlOutputError("only satisfy/subvert may return directive_body")
    if body and copies_reader_language(body, reader_responses):
        raise ReaderControlOutputError(
            "editorial directive copies reader language instead of abstracting its need"
        )
    return decision, need, rationale, body, targets


def make_editorial_interpret_handler(
    registry: TextGenerator,
    store: ReaderControlStore,
    project_id: str,
    *,
    budget: BudgetPolicy | None = None,
) -> JobHandler:
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        if store.editorial_intervention_for_job(job.job_id) is not None:
            return ()
        if not job.input_digest or job.input_digest != input_digest_for(job.payload):
            raise ReaderControlOutputError(
                "editorial job input digest does not match its payload"
            )
        mechanism = store.reader_mechanism(str(job.payload.get("mechanism_version_id") or ""))
        current = store.current_reader_mechanism(mechanism.mechanism_id)
        if not mechanism.may_steer or current is None or current.version_id != mechanism.version_id:
            raise ReaderControlOutputError(
                f"reader mechanism {mechanism.version_id} is {mechanism.status.value}, "
                "not the current qualified version"
            )
        evidence_ids = tuple(str(x) for x in job.payload["evidence_observation_ids"])
        evidence_digest = evidence_digest_for(evidence_ids)
        if evidence_digest != job.payload.get("evidence_digest"):
            raise ReaderControlOutputError("editorial job evidence digest is inconsistent")
        stored_observations = store.reader_observations(
            str(job.payload["book_id"]),
            str(job.payload["branch_id"]),
            checkpoint_id=str(job.payload["checkpoint_id"]),
            mechanism_version_id=mechanism.version_id,
        )
        stored_ids = {item.observation_id for item in stored_observations}
        if stored_ids != set(evidence_ids):
            raise ReaderControlOutputError("editorial job evidence no longer matches the ledger")
        current_plan = store.plan_revision(
            str(job.payload["book_id"]), str(job.payload["branch_id"])
        )
        if current_plan is None:
            raise ReaderControlOutputError("editorial job targets a branch with no plan")
        planned_against = str(job.payload.get("plan_revision_id") or "")
        if current_plan.plan_revision_id != planned_against:
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.editorial_plan_superseded.v0",
                passed=True,
                blocking=False,
                detail=(
                    f"editorial request planned against {planned_against}; current plan is "
                    f"{current_plan.plan_revision_id}; selector may freeze a fresh request"
                ),
            )
            obsolete = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.ACCEPT,
                gates=(gate,),
                job_id=job.job_id,
                base_revision_id=planned_against or None,
                attempt=job.attempts,
                profile=CONTROLLER_PROFILE,
                policy_config_digest=payload_digest(
                    {
                        "planned_against": planned_against,
                        "current_plan": current_plan.plan_revision_id,
                    }
                ),
                reason=gate.detail,
            )
            store.record_decision(obsolete, decided_at=_stamp(now))
            return (
                policy_decision_event(
                    obsolete, project_id=project_id, created_at=_stamp(now)
                ),
            )
        request = _request_from(job.payload.get("request"))
        provider, _ = registry.resolve(request.call_class)
        verdict = budget_check(
            budget_policy,
            store.spend_on(_stamp(now)[:10]),
            provider=provider.name,
            prompt_chars=request.input_chars,
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            return _budget_refusal(
                store,
                job,
                request,
                verdict,
                now=now,
                profile=request.profile,
                project_id=project_id,
            )
        result, resolution = registry.complete(request)
        parsed = result.parsed if isinstance(result.parsed, Mapping) else None
        policy_digest = payload_digest(
            {
                "mechanism_version_id": mechanism.version_id,
                "request": _request_payload(request),
            }
        )
        shape = _shape_decision(
            job,
            passed=parsed is not None,
            result=result,
            resolution=resolution,
            profile=request.profile,
            policy_digest=policy_digest,
        )
        if parsed is None:
            store.record_decision(shape, decided_at=_stamp(now))
            return (policy_decision_event(shape, project_id=project_id, created_at=_stamp(now)),)
        eligible = {str(x) for x in (job.payload.get("eligible_future_scene_ids") or ())}
        try:
            editorial_decision, need, rationale, body, targets = _parse_editorial_payload(
                parsed,
                eligible_scene_ids=eligible,
                reader_responses=[item.response for item in stored_observations],
            )
        except ReaderControlOutputError as error:
            failure = _shape_decision(
                job,
                passed=False,
                result=result,
                resolution=resolution,
                profile=request.profile,
                policy_digest=policy_digest,
                detail=str(error),
            )
            store.record_decision(failure, decided_at=_stamp(now))
            return (policy_decision_event(failure, project_id=project_id, created_at=_stamp(now)),)
        stamp = _stamp(now)
        directive: Directive | None = None
        directive_id: str | None = None
        if editorial_decision.dispatches_direction:
            author = machine_author(f"reader-controller:{mechanism.version_id}")
            directive_id = directive_id_for(DirectiveKind.CHAPTER_NOTE, body, stamp, author)
            directive = Directive(
                directive_id=directive_id,
                kind=DirectiveKind.CHAPTER_NOTE,
                body=body,
                book_id=str(job.payload["book_id"]),
                branch_id=str(job.payload["branch_id"]),
                received_at=stamp,
                precedence=0,
                author=author,
                metadata={
                    "source": "reader_editorial_controller",
                    "mechanism_version_id": mechanism.version_id,
                    "checkpoint_id": str(job.payload["checkpoint_id"]),
                    "evidence_digest": evidence_digest,
                    "editorial_decision": editorial_decision.value,
                    "target_scene_ids": list(targets),
                },
            )
        intervention = EditorialIntervention(
            intervention_id=intervention_id_for(job.job_id, evidence_digest),
            controller_job_id=job.job_id,
            checkpoint_id=str(job.payload["checkpoint_id"]),
            mechanism_version_id=mechanism.version_id,
            book_id=str(job.payload["book_id"]),
            branch_id=str(job.payload["branch_id"]),
            source_revision_id=str(job.payload["revision_id"]),
            source_logical_id=str(job.payload["logical_id"]),
            decision=editorial_decision,
            need=need,
            rationale=rationale,
            evidence_observation_ids=evidence_ids,
            evidence_digest=evidence_digest,
            target_logical_ids=targets,
            directive_id=directive_id,
            created_at=stamp,
            metadata={
                "provider": result.provider,
                "model": result.model,
                "profile": request.profile,
            },
        )
        store.record_editorial_intervention(
            intervention, directive=directive, decision=shape, decided_at=stamp
        )
        return (
            policy_decision_event(
                shape,
                project_id=project_id,
                created_at=stamp,
                actor=result.provider,
                book_id=intervention.book_id,
                branch_id=intervention.branch_id,
                revision_id=intervention.source_revision_id,
                details={
                    "intervention_id": intervention.intervention_id,
                    "editorial_decision": intervention.decision.value,
                    "directive_id": intervention.directive_id,
                },
            ),
        )

    return handle


__all__ = [
    "CONTROLLER_PROFILE",
    "EDITORIAL_INTERPRET",
    "EDITORIAL_INTERPRET_PRIORITY",
    "EDITORIAL_SCHEMA",
    "MECHANISM_ID",
    "READER_OBSERVE",
    "READER_OBSERVE_PRIORITY",
    "checkpoint_id_for",
    "copies_reader_language",
    "editorial_job_id",
    "enqueue_ready_editorial_panel",
    "experimental_mechanism",
    "make_editorial_interpret_handler",
    "make_reader_observation_handler",
    "mechanism_spec_digest",
    "reader_jobs_for_checkpoint",
    "render_editorial_request",
]
