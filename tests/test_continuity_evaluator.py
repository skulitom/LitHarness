"""The process boundary to ContinuityEvaluation stays shared-contract-only."""

from __future__ import annotations

import json
import sys

import litharness_contracts as lc
import pytest

from litharness.adapters.continuity_cli import (
    ContinuityCliRunner,
    ContinuityProcessError,
)
from litharness.adapters.contracts_fixtures import fixture_findings
from litharness.application.evaluation import (
    GAME_SYSTEM_DETECTOR_IDS,
    ContinuityEvaluator,
    EvaluationRequest,
    live_bundle_for,
)
from litharness.domain.revision import node_version_id
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision


def _record(record_id: str, *, valid_hash: bool = True) -> lc.StateRecord:
    revision = make_revision()
    node = revision.node("scene-1")
    assert node.content is not None
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate="status_snapshot",
        value={"level": 1, "hp": 10, "hp_max": 10, "mp": 5, "mp_max": 5, "gold": 3},
        story_position=lc.StoryPosition(order_key="s1"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        evidence=[
            lc.EvidenceSpan(
                source=lc.ResourceRef(
                    project_id="foreign-project",
                    book_id="foreign-book",
                    branch_id="foreign-branch",
                    logical_id="scene-1",
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                    version_id="foreign-version",
                ),
                start=0,
                end=4,
                content_sha256=(
                    content_hash(node.content[:4]) if valid_hash else content_hash("nope")
                ),
            )
        ],
    )


def test_live_bundle_reanchors_resolvable_evidence_and_omits_stale_records() -> None:
    revision = make_revision()
    bundle = live_bundle_for(
        EvaluationRequest(
            revision=revision,
            logical_id="scene-1",
            records=(_record("valid"), _record("stale", valid_hash=False)),
            created_at="2026-08-14T00:00:00Z",
        ),
        project_id=PROJECT_ID,
    )

    [record] = bundle["state_snapshot"]["records"]
    assert record["record_id"] == "valid"
    source = record["evidence"][0]["source"]
    assert source == {
        "project_id": PROJECT_ID,
        "book_id": BOOK_ID,
        "branch_id": BRANCH_ID,
        "logical_id": "scene-1",
        "kind": "manuscript_scene",
        "version_id": node_version_id(revision.node("scene-1")),
    }
    assert bundle["detector_ids"] == list(GAME_SYSTEM_DETECTOR_IDS)
    assert bundle["target_logical_ids"] == ["scene-1"]


def test_continuity_evaluator_maps_shared_artifact_and_checked_rules() -> None:
    raw = json.loads(fixture_findings("litrpg").read_text(encoding="utf-8"))
    raw["detector_runs"] = [
        {"detector_id": detector_id, "version": "0.1.0", "finding_count": 1}
        for detector_id in GAME_SYSTEM_DETECTOR_IDS
    ]
    evaluator = ContinuityEvaluator(lambda bundle: raw, PROJECT_ID)

    run = evaluator.evaluate(EvaluationRequest(revision=make_revision(), logical_id="scene-1"))

    assert run.complete
    assert run.findings
    assert run.checked_rule_ids == tuple(sorted(GAME_SYSTEM_DETECTOR_IDS))


def test_continuity_evaluator_turns_transport_failure_into_incomplete_run() -> None:
    def fail(bundle):
        raise ContinuityProcessError("offline")

    run = ContinuityEvaluator(fail, PROJECT_ID).evaluate(
        EvaluationRequest(revision=make_revision(), logical_id="scene-1")
    )

    assert not run.complete
    assert run.checked_rule_ids == ()
    assert run.errors[0].stage == "continuity_evaluation.process"
    assert run.errors[0].reason == "ContinuityProcessError"


def test_cli_runner_streams_json_without_a_shell(tmp_path) -> None:
    script = tmp_path / "evaluator.py"
    script.write_text(
        "import json, sys\n"
        "bundle = json.load(sys.stdin)\n"
        "print(json.dumps({'request_id': bundle['request_id']}))\n",
        encoding="utf-8",
    )
    runner = ContinuityCliRunner((sys.executable, str(script)))

    assert runner({"request_id": "request-1"}) == {"request_id": "request-1"}


def test_cli_runner_reports_nonzero_exit(tmp_path) -> None:
    script = tmp_path / "broken.py"
    script.write_text("raise SystemExit(7)\n", encoding="utf-8")

    with pytest.raises(ContinuityProcessError, match="exited 7"):
        ContinuityCliRunner((sys.executable, str(script)))({"request_id": "request-1"})
