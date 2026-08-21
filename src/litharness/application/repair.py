"""Stage 2's durable evaluation, located repair, and re-detection workflow."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.evaluation import (
    EvaluationRequest,
    Evaluator,
    matching_finding,
)
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import EvaluationStore, RepairStore, TextGenerator
from litharness.domain import propagation
from litharness.domain.budget import BudgetPolicy
from litharness.domain.budget import check as budget_check
from litharness.domain.calibration import Calibration, NotPromotable, veto_for
from litharness.domain.events import Event, EventType
from litharness.domain.extraction import extract_state
from litharness.domain.findings import UNRESOLVED_STATUSES, Finding, primary_span_of
from litharness.domain.generation import CompletionRequest
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.patch import PatchPolicy, apply_patch
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decide,
    decision_id_for,
    gates_for_patch,
    patch_policy_digest,
)
from litharness.domain.revision import Revision, node_version_id

EVALUATE_REVISION = "evaluate_revision"
REPAIR_FINDING = "repair_finding"
SCENE_SUMMARY = "scene_summary"
EVALUATION_PRIORITY = 80

#: Summarising an accepted scene ranks *below* everything, including drafting.
#:
#: It is the only job in the system whose value is entirely in the future: a summary is read
#: only once the budget stops holding that scene's prose, which on a long book is dozens of
#: scenes later. Ranking it above a draft would spend a tick compressing scene 3 while scene
#: 9 waits to be written — and unlike an evaluation, nothing is blocked on the answer. It is
#: a mechanical call, so it costs a local model and not the billing chain (§15).
SUMMARY_PRIORITY = 40
#: Base claim priority for a repair. The finding's severity is added on top, so a critical
#: complaint is claimed before a minor one that happened to be enqueued first.
#:
#: **This is the last half of `jobs.priority` that was still unused, and the plan named it.**
#: §20.4 recorded the column as inert because "nothing yet generates repair work for a finding
#: to prioritise, so a severity ordering would sort a queue whose entries all came from the
#: same beat template". Stage 2's repair chain ended that, and a constant priority then meant
#: severity — the one ordering §4.1 asks for by name, "findings to repair (severity-ordered)" —
#: reached the queue and stopped there.
REPAIR_PRIORITY = 100
MAX_AUTO_REPAIRS = 3
#: Nodes one accepted repair may queue a re-check of. A six-scene book cannot exceed it;
#: a novel can, and the difference between the reached set and the enqueued set is recorded
#: on `ImpactAnalyzed` so a truncation is visible rather than looking like full coverage.
MAX_PROPAGATED_EVALUATIONS = 12

_REPAIR_SCHEMA = {
    "type": "object",
    "required": ["replacement"],
    "properties": {"replacement": {"type": "string"}},
    "additionalProperties": False,
}


class EvaluationIncomplete(RuntimeError):
    """A detector run errored or omitted a rule required to verify a repair."""


class RepairInputError(ValueError):
    """A repair job no longer identifies a located, actionable finding."""


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _job_id(prefix: str, payload: dict[str, object]) -> tuple[str, str]:
    digest = input_digest_for(payload)
    return f"{prefix}-{digest[:24]}", digest


def evaluation_job_for(
    *,
    book_id: str,
    branch_id: str,
    revision_id: str,
    logical_id: str,
    verification_of_finding_id: str | None = None,
    repair_depth: int = 0,
) -> Job:
    payload: dict[str, object] = {
        "book_id": book_id,
        "branch_id": branch_id,
        "revision_id": revision_id,
        "logical_id": logical_id,
    }
    if verification_of_finding_id is not None:
        payload["verification_of_finding_id"] = verification_of_finding_id
    if repair_depth:
        payload["repair_depth"] = repair_depth
    job_id, digest = _job_id("eval", payload)
    return Job(
        job_id=job_id,
        job_kind=EVALUATE_REVISION,
        idempotency_key=job_id,
        input_digest=digest,
        payload=payload,
        priority=EVALUATION_PRIORITY,
    )


def summary_job_for(
    *,
    book_id: str,
    branch_id: str,
    revision_id: str,
    logical_id: str,
    content_hash: str,
) -> Job:
    """One job: say what this scene contained, so the packet can carry it after eviction.

    **`content_hash` is in the payload and in the idempotency key**, so the unit of work is
    "summarise *this text*" rather than "summarise this node". Every accepted draft mints a
    new revision id for the whole book, so keying on the revision would re-summarise every
    scene in the book on every acceptance — forty calls to draft the forty-first scene. Keyed
    on the scene's own text, a repaired scene earns a new job and an untouched one earns
    none.
    """
    payload: dict[str, object] = {
        "book_id": book_id,
        "branch_id": branch_id,
        "revision_id": revision_id,
        "logical_id": logical_id,
        "content_hash": content_hash,
    }
    job_id, digest = _job_id("summary", payload)
    return Job(
        job_id=job_id,
        job_kind=SCENE_SUMMARY,
        idempotency_key=job_id,
        input_digest=digest,
        payload=payload,
        priority=SUMMARY_PRIORITY,
    )


def cited_calibration_id(finding: Finding) -> str | None:
    """The calibration a finding's claim cites, or None when it cites none.

    Carried in the contract finding's free-form `claim` — the field a calibrated detector
    owns — rather than in a new column: no calibrated finding exists in production today,
    and the citation's shape is pinned by the tests that exercise the license.
    """
    claim = finding.source.get("claim")
    if not isinstance(claim, dict):
        return None
    cited = claim.get("calibration_id")
    return cited if isinstance(cited, str) and cited else None


def calibration_licenses(
    finding: Finding, calibrations: Sequence[Calibration], *, today: str
) -> bool:
    """Whether a *current* calibration licenses a scoped repair of this finding.

    §61 Add 3's item 5, and the whole of it: the cited `calibration_id` must be present,
    its stored row must be current today, and its evidence class must be one whose
    promotion the domain accepts — checked through `veto_for`, which is total over the
    enum precisely so a class with no refusal license raises here instead of inheriting
    one. §1a.2's discipline is untouched on both sides of this check: an *uncalibrated*
    non-blocking finding still licenses nothing, and what a calibrated one licenses is
    still a span-scoped patch under `licensed_by_finding_id` — never freeform revision.

    No such finding exists today; the calibrations table holds no row a claim could cite.
    This path is exercised by tests with a synthetic row, which is the intended state:
    the gate is the license, and the license opens when the evidence does.
    """
    cited = cited_calibration_id(finding)
    if cited is None:
        return False
    row = next(
        (item for item in calibrations if item.calibration_id == cited), None
    )
    if row is None or not row.is_current(today):
        return False
    try:
        veto_for(row.evidence_class)
    except NotPromotable:
        return False
    return True


def repair_job_for(
    finding: Finding,
    *,
    book_id: str,
    branch_id: str,
    revision_id: str,
    repair_depth: int,
    calibrated: bool = False,
) -> Job | None:
    """One repair unit for a finding the licensing predicate accepts, else None.

    **The predicate, and its one extension (§61 Add 3, item 5).** The original license —
    blocking AND deterministic AND span-carrying — stands unchanged. The extension is
    exactly one new disjunct: a finding that carries a primary span AND cites a current
    calibration (`calibrated`, computed by the caller via `calibration_licenses`) may
    license a scoped repair even when non-blocking. The span requirement is common to both
    arms and non-negotiable: without a located span there is nothing `apply_patch` can
    license, and relaxing it would weaken the `UNLICENSED_DELETION` guarantee — the exact
    trade the planning-drafting map warns the generalization against.
    """
    span = primary_span_of(finding)
    if span is None or not ((finding.blocks and finding.deterministic) or calibrated):
        return None
    payload: dict[str, object] = {
        "book_id": book_id,
        "branch_id": branch_id,
        "revision_id": revision_id,
        "logical_id": span.source.logical_id,
        "finding_id": finding.finding_id,
        "repair_depth": repair_depth,
    }
    job_id, digest = _job_id("repair", payload)
    return Job(
        job_id=job_id,
        job_kind=REPAIR_FINDING,
        idempotency_key=job_id,
        input_digest=digest,
        payload=payload,
        # Severity rides on top of the band rather than replacing it: a repair still outranks
        # every evaluation, and within repairs the worse complaint is claimed first. Deriving
        # it here rather than storing it on the payload keeps one source of truth — the
        # finding's own severity — for an ordering that would otherwise drift the first time a
        # severity was corrected after the job was minted.
        priority=REPAIR_PRIORITY + finding.severity.rank,
    )


def propagated_evaluations(
    known: Sequence[lc.StateRecord],
    extracted: Sequence[lc.StateRecord],
    *,
    revision: Revision,
    book_id: str,
    branch_id: str,
    logical_id: str,
    repair_depth: int,
) -> tuple[tuple[Job, ...], tuple[str, ...]]:
    """Evaluations for the nodes this repair's change reaches, and the full reached set.

    **Bounded twice, because §4.2's failure mode is a parked unit and never a spin loop.**
    A propagated evaluation costs a depth level, so a chain of repair-propagate-repair
    terminates at `MAX_AUTO_REPAIRS` hops rather than walking the book forever; at the last
    depth it enqueues nothing at all rather than minting jobs the evaluation handler would
    refuse. And the fan-out per acceptance is capped, because one repair should not be able to
    queue a re-check of every scene in a novel.

    Both the reached set and the enqueued set are returned so the caller can record them
    separately. They differ exactly when a cap bit, and a cap nobody can see reads as full
    coverage.
    """
    if repair_depth + 1 > MAX_AUTO_REPAIRS:
        return (), ()
    changes = propagation.changes_between(known, extracted)
    if not changes:
        return (), ()
    result = propagation.propagate_changes(
        changes,
        edited=(logical_id,),
        book=propagation.book_from(revision, known),
    )
    # Manuscript nodes only. Nothing in this system re-evaluates a state record, so a job
    # naming one would park for want of anything to do with it.
    drafted = {node.logical_id for node in revision.nodes}
    reached = tuple(
        sorted(
            target
            for target in result.logical_ids
            if target != logical_id and target in drafted
        )
    )
    return (
        tuple(
            evaluation_job_for(
                book_id=book_id,
                branch_id=branch_id,
                revision_id=revision.revision_id,
                logical_id=target,
                repair_depth=repair_depth + 1,
            )
            for target in reached[:MAX_PROPAGATED_EVALUATIONS]
        ),
        reached,
    )


def make_evaluation_handler(
    evaluator: Evaluator,
    store: EvaluationStore,
    project_id: str,
) -> JobHandler:
    """Persist a complete run and materialise repair work in the same transaction."""

    def handle(job: Job, now: float) -> Sequence[Event]:
        try:
            book_id = str(job.payload["book_id"])
            branch_id = str(job.payload["branch_id"])
            revision_id = str(job.payload["revision_id"])
            logical_id = str(job.payload["logical_id"])
            repair_depth = int(job.payload.get("repair_depth", 0))
        except (KeyError, TypeError, ValueError) as error:
            raise EvaluationIncomplete(f"evaluation job payload is incomplete: {error}") from error
        if not 0 <= repair_depth <= MAX_AUTO_REPAIRS:
            raise EvaluationIncomplete(f"invalid repair_depth: {repair_depth}")

        revision = store.load_revision(revision_id)
        head = store.head(book_id, branch_id)
        if head is not None:
            revision = head
        verification_id = job.payload.get("verification_of_finding_id")
        stored_findings = {
            finding.finding_id: finding for finding in store.findings(book_id, branch_id)
        }
        original = stored_findings.get(str(verification_id)) if verification_id else None
        if verification_id and original is None:
            raise EvaluationIncomplete(
                f"verification finding {verification_id} is not in {book_id}/{branch_id}"
            )
        required = (
            (original.rule_or_critic_id,)
            if original is not None and original.rule_or_critic_id is not None
            else ()
        )
        run = evaluator.evaluate(
            EvaluationRequest(
                revision=revision,
                logical_id=logical_id,
                records=tuple(store.state_records(book_id, branch_id)),
                plan_items=tuple(store.plan_items(book_id, branch_id)),
                required_rule_ids=required,
                created_at=_timestamp(now),
            )
        )
        missing_rules = tuple(sorted(set(required) - set(run.checked_rule_ids)))
        complete = run.complete and not missing_rules

        fixed_id: str | None = None
        if (
            original is not None
            and original.status in UNRESOLVED_STATUSES
            and complete
            and matching_finding(original, run.findings) is None
        ):
            fixed_id = original.finding_id

        repairs: list[Job] = []
        persistent = matching_finding(original, run.findings) if original is not None else None
        if complete and repair_depth < MAX_AUTO_REPAIRS:
            # Read once, only when a repair could be minted: the calibrated-license arm
            # asks whether a finding's cited calibration is current *today*, so the check
            # runs at mint time and again at claim time in the repair handler.
            calibrations = store.calibrations()
            today = _timestamp(now)[:10]
            ordered = sorted(
                run.findings,
                key=lambda finding: (-finding.severity.rank, finding.finding_id),
            )
            for finding in ordered:
                # One repair is followed by one re-detection. If the same complaint remains,
                # repeating with a fresh content-derived job id would be an unbounded loop.
                if persistent is finding:
                    continue
                existing = stored_findings.get(finding.finding_id)
                candidate = existing or finding
                repair = repair_job_for(
                    candidate,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision.revision_id,
                    repair_depth=repair_depth + 1,
                    calibrated=calibration_licenses(
                        candidate, calibrations, today=today
                    ),
                )
                if repair is not None:
                    repairs.append(repair)
                    break

        stamp = _timestamp(now)
        evaluation_event = Event(
            event_type=EventType.EVALUATION_COMPLETED,
            project_id=project_id,
            created_at=stamp,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=revision.revision_id,
            causation_id=job.job_id,
            payload={
                "job_id": job.job_id,
                "run_id": run.run_id,
                "logical_id": logical_id,
                "complete": complete,
                "finding_count": len(run.findings),
                "checked_rule_ids": list(run.checked_rule_ids),
                "missing_rule_ids": list(missing_rules),
                "errors": [
                    {"stage": error.stage, "reason": error.reason, "detail": error.detail}
                    for error in run.errors
                ],
                "verification_of_finding_id": str(verification_id) if verification_id else None,
            },
        )
        events = [evaluation_event]
        if fixed_id is not None:
            events.append(
                Event(
                    event_type=EventType.FINDING_STATUS_CHANGED,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision.revision_id,
                    causation_id=job.job_id,
                    payload={
                        "finding_id": fixed_id,
                        "status": "fixed",
                        "run_id": run.run_id,
                        "verified": True,
                    },
                )
            )
        store.commit_evaluation(
            book_id,
            branch_id,
            revision.revision_id,
            run.findings,
            created_at=stamp,
            events=events,
            jobs=repairs,
            fixed_finding_id=fixed_id,
        )

        if not complete:
            details = run.summarise_errors()
            if missing_rules:
                details = "; ".join(
                    part
                    for part in (details, f"rules not checked: {', '.join(missing_rules)}")
                    if part
                )
            raise EvaluationIncomplete(details or "evaluation did not complete")
        return ()

    return handle


def _repair_prompt(finding: Finding, text: str, start: int, end: int) -> str:
    return (
        "Repair only the exact passage identified below. Return JSON with one string field "
        "named replacement. Do not include commentary and do not rewrite surrounding text.\n\n"
        f"Finding: {finding.message}\n"
        f"Rule: {finding.rule_or_critic_id or finding.category}\n"
        f"Exact passage: {text[start:end]!r}\n"
        f"Before: {text[max(0, start - 300):start]!r}\n"
        f"After: {text[end:end + 300]!r}"
    )


def make_repair_handler(
    registry: TextGenerator,
    store: RepairStore,
    project_id: str,
    *,
    policy: PatchPolicy | None = None,
    budget: BudgetPolicy | None = None,
    call_class: str = "generation",
) -> JobHandler:
    """Generate one replacement span, apply it mechanically, then enqueue verification."""
    patch_policy = policy or PatchPolicy()
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        try:
            book_id = str(job.payload["book_id"])
            branch_id = str(job.payload["branch_id"])
            logical_id = str(job.payload["logical_id"])
            finding_id = str(job.payload["finding_id"])
            repair_depth = int(job.payload["repair_depth"])
        except (KeyError, TypeError, ValueError) as error:
            raise RepairInputError(f"repair job payload is incomplete: {error}") from error
        if not 1 <= repair_depth <= MAX_AUTO_REPAIRS:
            raise RepairInputError(f"invalid repair_depth: {repair_depth}")

        prior = store.latest_decision_for(job.job_id)
        if prior is not None and prior.outcome is Outcome.ACCEPT:
            return ()

        finding = next(
            (
                candidate
                for candidate in store.findings(book_id, branch_id)
                if candidate.finding_id == finding_id
            ),
            None,
        )
        if finding is None:
            raise RepairInputError(f"finding {finding_id} is not in {book_id}/{branch_id}")
        # The mint-time license, re-checked at claim time: a blocking finding may have
        # been dismissed since the job was minted, and a calibrated license may have
        # lapsed with its calibration — either way the repair no longer has a license
        # and quietly completing is the honest outcome (the job was legitimate work).
        if not finding.blocks and not calibration_licenses(
            finding, store.calibrations(), today=_timestamp(now)[:10]
        ):
            return ()
        span = primary_span_of(finding)
        if span is None or span.source.logical_id != logical_id:
            raise RepairInputError(f"finding {finding_id} has no usable primary span")

        revision = store.head(book_id, branch_id)
        if revision is None:
            raise RepairInputError(f"no head for {book_id}/{branch_id}")
        node = revision.node(logical_id)
        text = node.content
        if text is None:
            raise RepairInputError(f"repair target {logical_id} carries no text")
        start, end = int(span.start), int(span.end)

        request = CompletionRequest(
            prompt=_repair_prompt(finding, text, start, end),
            schema=_REPAIR_SCHEMA,
            profile="repair",
            max_output_tokens=1024,
            call_class=call_class,
        )
        provider, _ = registry.resolve(call_class)
        day = _timestamp(now)[:10]
        budget_verdict = budget_check(
            budget_policy,
            store.spend_on(day),
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
            decision = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.PARK,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision.revision_id,
                attempt=job.attempts,
                reason=budget_verdict.reason,
            )
            store.record_decision(decision, decided_at=_timestamp(now))
            decision_event = policy_decision_event(
                decision,
                project_id=project_id,
                created_at=_timestamp(now),
                book_id=book_id,
                branch_id=branch_id,
                revision_id=revision.revision_id,
            )
            return (
                Event(
                    event_type=EventType.BUDGET_EXHAUSTED,
                    project_id=project_id,
                    created_at=_timestamp(now),
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision.revision_id,
                    payload={"job_id": job.job_id, "reason": budget_verdict.reason},
                ),
                decision_event,
            )

        result, resolution = registry.complete(request)
        replacement = None if result.parsed is None else result.parsed.get("replacement")
        ops = []
        if isinstance(replacement, str):
            ops.append(
                lc.PatchOp(
                    kind=lc.PatchOpKind.REPLACE_SPAN,
                    target_span=span,
                    new_text=replacement,
                )
            )
        patch = lc.BoundedPatch(
            meta=lc.ArtifactMeta(
                schema_version="1.0.0",
                artifact_id=f"patch-{job.job_id}",
                artifact_kind="bounded_patch",
                created_at=_timestamp(now),
                actor=result.provider,
                tool=lc.ToolIdentity(name=result.provider, version=result.model),
            ),
            target=lc.ResourceRef(
                project_id=project_id,
                book_id=book_id,
                branch_id=branch_id,
                logical_id=logical_id,
                kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                version_id=span.source.version_id,
            ),
            base_version_id=span.source.version_id or "",
            base_content_sha256=node.content_sha256 or "",
            ops=ops,
            idempotency_key=job.idempotency_key or job.job_id,
            licensed_by_finding_id=finding_id,
        )
        outcome = apply_patch(revision, patch, patch_policy)
        gates = gates_for_patch(outcome)
        verdict, reason = decide(
            gates,
            job_id=job.job_id,
            attempt=job.attempts,
            max_attempts=job.max_attempts,
        )
        accepted = outcome.accepted and outcome.revision is not None
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, gates),
            outcome=verdict,
            gates=gates,
            job_id=job.job_id,
            logical_id=logical_id,
            base_revision_id=revision.revision_id,
            resulting_revision_id=(
                outcome.revision.revision_id if outcome.revision is not None else None
            ),
            attempt=job.attempts,
            provider=result.provider,
            model=result.model,
            profile=request.profile,
            fell_back_from=tuple(resolution.fell_back_from),
            invocations=result.invocations,
            total_tokens=result.usage.total,
            cost_usd=result.cost_usd,
            policy_config_digest=patch_policy_digest(patch_policy),
            reason=reason,
        )
        stamp = _timestamp(now)
        decision_event = policy_decision_event(
            decision,
            project_id=project_id,
            created_at=stamp,
            actor=result.provider,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=decision.resulting_revision_id or revision.revision_id,
            details={"finding_id": finding_id},
        )
        if not accepted:
            store.record_decision(decision, decided_at=stamp)
            return (
                Event(
                    event_type=EventType.MANUSCRIPT_CANDIDATE_CREATED,
                    project_id=project_id,
                    created_at=stamp,
                    actor=result.provider,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision.revision_id,
                    payload={
                        "job_id": job.job_id,
                        "finding_id": finding_id,
                        "accepted": False,
                        "vetoes": [veto.value for gate in gates for veto in gate.vetoes],
                    },
                ),
                decision_event,
            )

        assert outcome.revision is not None and outcome.node_after is not None
        records = tuple(store.state_records(book_id, branch_id))
        extracted = extract_state(
            outcome.node_after.content or "",
            known=records,
            project_id=project_id,
            book_id=book_id,
            branch_id=branch_id,
            logical_id=logical_id,
            version_id=node_version_id(outcome.node_after),
            replacing_logical_id=logical_id,
        )
        verification = evaluation_job_for(
            book_id=book_id,
            branch_id=branch_id,
            revision_id=outcome.revision.revision_id,
            logical_id=logical_id,
            verification_of_finding_id=finding_id,
            repair_depth=repair_depth,
        )
        # **A repair that changes a fact leaves every scene stating it stale, and nothing
        # noticed.** The evaluation this repair schedules re-checks the repaired node and only
        # that one — so correcting a price in scene 2 left six downstream balances wrong, the
        # book reported clean, and the defect was invisible to every gate the system has. This
        # is §17 Stage 2's loop, closed with the two halves that were already here: extraction
        # says what the repaired prose now asserts, and `changes_between` reads the difference
        # against the canon being retracted. Nothing is minted and nothing is guessed; a
        # change the producer cannot read reaches nothing and says so.
        propagated, reached = propagated_evaluations(
            records,
            extracted,
            revision=outcome.revision,
            book_id=book_id,
            branch_id=branch_id,
            logical_id=logical_id,
            repair_depth=repair_depth,
        )
        acceptance = Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=project_id,
            created_at=stamp,
            actor=result.provider,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=outcome.revision.revision_id,
            payload={
                "decision_id": decision.decision_id,
                "job_id": job.job_id,
                "logical_id": logical_id,
                "finding_id": finding_id,
                "accepted": True,
                "repair": True,
                "parent_revision_id": revision.revision_id,
                "touched_spans": [list(span_) for span_ in outcome.touched_spans],
            },
        )
        events: tuple[Event, ...] = (acceptance, decision_event)
        if reached:
            events += (
                Event(
                    event_type=EventType.IMPACT_ANALYZED,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=outcome.revision.revision_id,
                    causation_id=job.job_id,
                    payload={
                        "job_id": job.job_id,
                        "logical_id": logical_id,
                        "reached": list(reached),
                        # Recorded separately because they differ whenever the fan-out cap or
                        # the depth cap bites, and a cap that truncates silently reads as
                        # "everything was covered" when it was not.
                        "enqueued": [str(unit.payload["logical_id"]) for unit in propagated],
                        "repair_depth": repair_depth,
                    },
                ),
            )
        store.commit_revision(
            outcome.revision,
            created_at=stamp,
            events=events,
            state_records=extracted,
            retract_state_for_nodes=(logical_id,),
            jobs=(verification, *propagated),
            decision=decision,
        )
        return (decision_event,)

    return handle


__all__ = [
    "EVALUATE_REVISION",
    "MAX_AUTO_REPAIRS",
    "REPAIR_FINDING",
    "SCENE_SUMMARY",
    "SUMMARY_PRIORITY",
    "EvaluationIncomplete",
    "RepairInputError",
    "calibration_licenses",
    "cited_calibration_id",
    "evaluation_job_for",
    "make_evaluation_handler",
    "make_repair_handler",
    "propagated_evaluations",
    "repair_job_for",
    "summary_job_for",
]
