"""Evaluator capability and the durable input/output shapes used by Stage 2.

The application owns when evaluation runs and what a completed run means. Detector
implementations stay behind ``Evaluator``: LitHarness's store-aware contradiction check runs
in-process, while ContinuityEvaluation satisfies the same port through a versioned live-book
bundle and an optional subprocess adapter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol, cast

import litharness_contracts as lc

from litharness.domain.events import payload_digest
from litharness.domain.findings import DetectorInput, Finding
from litharness.domain.integrity import (
    CONTRADICTION_RULE,
    DUPLICATE_RULE,
    run_detectors,
)
from litharness.domain.nodes import NodeKind
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.text import content_hash

GAME_SYSTEM_DETECTOR_IDS = (
    "ledger.gold.v0",
    "stats.ceiling.v0",
    "stats.level_monotonic.v0",
    "causality.acquisition.v0",
    "thread.transition.v0",
    "inventory.ghost.v0",
)
LIVE_BUNDLE_VERSION = "1.0.0"
LIVE_POLICY_VERSION = "litrpg-game-system-v0"


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    revision: Revision
    logical_id: str
    records: tuple[lc.StateRecord, ...] = ()
    plan_items: tuple[lc.PlanItem, ...] = ()
    required_rule_ids: tuple[str, ...] = ()
    created_at: str = "1970-01-01T00:00:00Z"


@dataclass(frozen=True, slots=True)
class EvaluationError:
    stage: str
    reason: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    run_id: str
    findings: tuple[Finding, ...] = ()
    errors: tuple[EvaluationError, ...] = ()
    checked_rule_ids: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.errors

    def summarise_errors(self) -> str:
        return "; ".join(
            f"{error.stage}: {error.reason}"
            + (f" ({error.detail})" if error.detail else "")
            for error in self.errors
        )


class Evaluator(Protocol):
    """Run deterministic or independently calibrated checks over one revision."""

    def evaluate(self, request: EvaluationRequest) -> EvaluationRun: ...


class BundleRunner(Protocol):
    """Transport a live bundle and return a shared EvaluationArtifact mapping."""

    def __call__(self, bundle: dict[str, Any]) -> dict[str, Any]: ...


class InProcessEvaluator:
    """The store-aware check only LitHarness can run: contradictory accepted state."""

    def evaluate(self, request: EvaluationRequest) -> EvaluationRun:
        subject = DetectorInput(
            book_id=request.revision.book_id,
            branch_id=request.revision.branch_id,
            logical_id=request.logical_id,
            candidate=request.revision.node(request.logical_id).content,
            records=request.records,
            plan_items=request.plan_items,
            # **Excluding this node, or every scene is a perfect copy of itself.** Unlike the
            # draft handler, which compares a candidate against the base revision it is not
            # yet part of, this evaluates a revision the scene is already *in* — so the
            # exclusion is load-bearing rather than tidy, and a detector that found a
            # 900-word self-overlap on every scene in the book would be worse than none.
            prior_prose=tuple(
                (node.logical_id, node.content)
                for node in request.revision.in_reading_order()
                if node.kind is NodeKind.SCENE
                and node.content
                and node.logical_id != request.logical_id
            ),
        )
        findings = tuple(run_detectors(subject))
        material = payload_digest(
            {
                "revision_id": request.revision.revision_id,
                "logical_id": request.logical_id,
                "rules": [CONTRADICTION_RULE, DUPLICATE_RULE],
                "findings": [finding.finding_id for finding in findings],
            }
        )
        return EvaluationRun(
            run_id=f"run-{sha256(material.encode()).hexdigest()[:24]}",
            findings=findings,
            checked_rule_ids=(CONTRADICTION_RULE, DUPLICATE_RULE),
        )


def _meta(
    *, artifact_id: str, artifact_kind: str, created_at: str, source: lc.ResourceRef
) -> lc.ArtifactMeta:
    return lc.ArtifactMeta(
        schema_version="1.0.0",
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        created_at=created_at,
        actor="litharness",
        tool=lc.ToolIdentity(name="litharness", version="0.1.0"),
        source_revisions=[source],
    )


def _live_record(
    record: lc.StateRecord, request: EvaluationRequest, project_id: str
) -> lc.StateRecord | None:
    """Re-anchor resolvable prose evidence and omit stale imported future-state records."""
    payload = lc.to_jsonable(record)
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return None
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("source"), dict):
            return None
        source = item["source"]
        if source.get("kind") != lc.ResourceKind.MANUSCRIPT_SCENE.value:
            continue
        logical_id = str(source.get("logical_id", ""))
        try:
            node = request.revision.node(logical_id)
        except KeyError:
            return None
        text = node.content
        start, end = item.get("start"), item.get("end")
        if (
            text is None
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end < start
            or end > len(text)
            or content_hash(text[start:end]) != item.get("content_sha256")
        ):
            return None
        source.update(
            {
                "project_id": project_id,
                "book_id": request.revision.book_id,
                "branch_id": request.revision.branch_id,
                "version_id": node_version_id(node),
            }
        )
    return cast(lc.StateRecord, lc.from_jsonable(lc.StateRecord, payload))


def live_bundle_for(
    request: EvaluationRequest,
    *,
    project_id: str,
    detector_ids: Sequence[str] = GAME_SYSTEM_DETECTOR_IDS,
) -> dict[str, Any]:
    """Build ContinuityEvaluation's versioned process boundary from shared artifacts."""
    source = lc.ResourceRef(
        project_id=project_id,
        book_id=request.revision.book_id,
        branch_id=request.revision.branch_id,
        logical_id="book",
        kind=lc.ResourceKind.MANUSCRIPT_BOOK,
        version_id=request.revision.revision_id,
    )
    records = tuple(
        resolved
        for record in request.records
        if (resolved := _live_record(record, request, project_id)) is not None
    )
    state_material = [lc.to_jsonable(record) for record in records]
    plan_material = [lc.to_jsonable(item) for item in request.plan_items]
    state_id = f"state-live-{payload_digest({'records': state_material})[:24]}"
    plan_id = f"plan-live-{payload_digest({'items': plan_material})[:24]}"
    manuscript = request.revision.to_contract(
        _meta(
            artifact_id=f"manuscript-live-{request.revision.revision_id[:24]}",
            artifact_kind="manuscript_revision",
            created_at=request.created_at,
            source=source,
        )
    )
    state = lc.StateSnapshot(
        meta=_meta(
            artifact_id=state_id,
            artifact_kind="state_snapshot",
            created_at=request.created_at,
            source=source,
        ),
        book_id=request.revision.book_id,
        branch_id=request.revision.branch_id,
        revision_id=state_id,
        records=list(records),
    )
    plans = lc.PlanSnapshot(
        meta=_meta(
            artifact_id=plan_id,
            artifact_kind="plan_snapshot",
            created_at=request.created_at,
            source=source,
        ),
        book_id=request.revision.book_id,
        branch_id=request.revision.branch_id,
        revision_id=plan_id,
        items=list(request.plan_items),
    )
    request_material = {
        "revision": request.revision.revision_id,
        "state": state_id,
        "plan": plan_id,
        "detectors": list(detector_ids),
        "targets": [request.logical_id],
    }
    request_id = f"request-{payload_digest(request_material)[:24]}"
    return {
        "schema_version": LIVE_BUNDLE_VERSION,
        "request_id": request_id,
        "created_at": request.created_at,
        "project_id": project_id,
        "policy_version": LIVE_POLICY_VERSION,
        "detector_ids": list(detector_ids),
        "target_logical_ids": [request.logical_id],
        "manuscript_revision": lc.to_jsonable(manuscript),
        "state_snapshot": lc.to_jsonable(state),
        "plan_snapshot": lc.to_jsonable(plans),
        "facts": {
            "closed_world": {"possession_item_ids": [], "knowledge": []},
            "state_assertions": [],
            "item_uses": [],
            "item_events": [],
            "actions": [],
            "knowledge_grants": [],
            "knowledge_uses": [],
            "temporal_claims": [],
            "intentional_exceptions": [],
        },
    }


class ContinuityEvaluator:
    """Adapter-facing evaluator that speaks only shared JSON artifacts."""

    def __init__(
        self,
        runner: BundleRunner,
        project_id: str,
        *,
        detector_ids: Sequence[str] = GAME_SYSTEM_DETECTOR_IDS,
    ) -> None:
        self._runner = runner
        self._project_id = project_id
        self._detector_ids = tuple(detector_ids)

    def evaluate(self, request: EvaluationRequest) -> EvaluationRun:
        try:
            raw = self._runner(
                live_bundle_for(
                    request,
                    project_id=self._project_id,
                    detector_ids=self._detector_ids,
                )
            )
            artifact = cast(
                lc.EvaluationArtifact,
                lc.parse_artifact(lc.EvaluationArtifact, raw),
            )
        except Exception as error:
            return EvaluationRun(
                run_id=f"run-error-{request.revision.revision_id[:16]}",
                errors=(
                    EvaluationError(
                        stage="continuity_evaluation.process",
                        reason=type(error).__name__,
                        detail=str(error),
                    ),
                ),
            )
        errors = tuple(
            EvaluationError(item.stage, item.reason, item.detail) for item in artifact.errors
        )
        failed_stages = {error.stage for error in errors}
        detector_runs = raw.get("detector_runs", [])
        checked = tuple(
            sorted(
                str(item["detector_id"])
                for item in detector_runs
                if isinstance(item, dict)
                and "detector_id" in item
                and str(item["detector_id"]) not in failed_stages
            )
        )
        return EvaluationRun(
            run_id=artifact.run_id,
            findings=tuple(
                Finding.from_contract(finding, run_id=artifact.run_id)
                for finding in artifact.findings
            ),
            errors=errors,
            checked_rule_ids=checked,
        )


class CompositeEvaluator:
    """Run independent evaluator owners and merge their explicit results."""

    def __init__(self, evaluators: Sequence[Evaluator]) -> None:
        if not evaluators:
            raise ValueError("composite evaluator needs at least one implementation")
        self._evaluators = tuple(evaluators)

    def evaluate(self, request: EvaluationRequest) -> EvaluationRun:
        runs = tuple(evaluator.evaluate(request) for evaluator in self._evaluators)
        findings = {
            finding.finding_id: finding
            for run in runs
            for finding in run.findings
        }
        material = payload_digest(
            {
                "runs": [run.run_id for run in runs],
                "findings": sorted(findings),
                "errors": [
                    [error.stage, error.reason, error.detail]
                    for run in runs
                    for error in run.errors
                ],
            }
        )
        return EvaluationRun(
            run_id=f"run-composite-{material[:20]}",
            findings=tuple(findings[key] for key in sorted(findings)),
            errors=tuple(error for run in runs for error in run.errors),
            checked_rule_ids=tuple(
                sorted({rule for run in runs for rule in run.checked_rule_ids})
            ),
        )


def matching_finding(original: Finding, candidates: Sequence[Finding]) -> Finding | None:
    """The same defect class at the same node, independent of version-derived finding ids."""
    return next(
        (
            candidate
            for candidate in candidates
            if candidate.blocks
            and candidate.deterministic
            and candidate.logical_id == original.logical_id
            and candidate.rule_or_critic_id == original.rule_or_critic_id
            and candidate.category == original.category
        ),
        None,
    )


__all__ = [
    "GAME_SYSTEM_DETECTOR_IDS",
    "BundleRunner",
    "CompositeEvaluator",
    "ContinuityEvaluator",
    "EvaluationError",
    "EvaluationRequest",
    "EvaluationRun",
    "Evaluator",
    "InProcessEvaluator",
    "live_bundle_for",
    "matching_finding",
]
