"""Executable pins for the research claim/evidence boundary.

These tests prove record shape and content addressing, not the truth of any research claim.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import epistemic_governance as governance
import pytest


def _ref(
    kind: str, path: str = "research/result.json", content: bytes = b"result"
) -> dict[str, str]:
    return {"kind": kind, "path": path, "sha256": hashlib.sha256(content).hexdigest()}


def _claim(status: str, artifacts: list[dict[str, str]]) -> dict[str, object]:
    return {
        "schema": governance.SCHEMA,
        "claim_id": "reader-mechanism-v1",
        "statement": "The registered mechanism survives its registered controls.",
        "status": status,
        "artifacts": artifacts,
    }


@pytest.mark.parametrize(
    ("status", "artifacts"),
    [
        ("conjecture", []),
        ("registered", [_ref("registration")]),
        ("observed", [_ref("registration"), _ref("raw_result")]),
        (
            "supported",
            [_ref("registration"), _ref("derived_result"), _ref("control_result")],
        ),
        (
            "refuted",
            [_ref("registration"), _ref("raw_result"), _ref("control_result")],
        ),
        (
            "qualified",
            [
                _ref("registration"),
                _ref("raw_result"),
                _ref("control_result"),
                _ref("qualification"),
            ],
        ),
    ],
)
def test_each_claim_state_has_one_unambiguous_minimum_shape(
    status: str, artifacts: list[dict[str, str]]
) -> None:
    record = governance.parse_claim(_claim(status, artifacts))
    assert record.status.value == status
    assert len(record.digest) == 64


@pytest.mark.parametrize(
    ("status", "artifacts", "message"),
    [
        ("registered", [], "registration artifact"),
        ("observed", [_ref("registration")], "raw or derived result"),
        (
            "supported",
            [_ref("registration"), _ref("raw_result")],
            "control result",
        ),
        (
            "qualified",
            [_ref("registration"), _ref("raw_result"), _ref("control_result")],
            "qualification artifact",
        ),
    ],
)
def test_prose_cannot_promote_a_claim_without_the_required_artifact_kinds(
    status: str, artifacts: list[dict[str, str]], message: str
) -> None:
    with pytest.raises(governance.ClaimValidationError, match=message):
        governance.parse_claim(_claim(status, artifacts))


def test_earlier_states_reject_artifacts_that_imply_a_later_state() -> None:
    with pytest.raises(governance.ClaimValidationError, match="registered claims cannot cite"):
        governance.parse_claim(
            _claim("registered", [_ref("registration"), _ref("raw_result")])
        )


def test_records_reject_summary_fields_and_escaping_paths() -> None:
    payload = _claim("conjecture", [])
    payload["consensus"] = "Every agent agrees."
    with pytest.raises(governance.ClaimValidationError, match="unknown consensus"):
        governance.parse_claim(payload)

    with pytest.raises(governance.ClaimValidationError, match="repo-relative POSIX"):
        governance.parse_claim(_claim("registered", [_ref("registration", "../claim.md")]))


def test_verification_detects_changed_evidence_bytes(tmp_path: Path) -> None:
    result = tmp_path / "research" / "result.json"
    result.parent.mkdir()
    result.write_bytes(b"result")
    record = governance.parse_claim(_claim("registered", [_ref("registration")]))
    governance.verify_artifacts(record, tmp_path)

    result.write_bytes(b"a later agent rewrote the artifact")
    with pytest.raises(governance.ClaimValidationError, match="artifact digest changed"):
        governance.verify_artifacts(record, tmp_path)


def test_agent_guidance_points_to_the_canonical_boundary() -> None:
    root = Path(__file__).resolve().parents[1]
    guidance = (root / "AGENTS.md").read_text(encoding="utf-8")
    protocol = (
        root / "research" / "quality-measurement" / "EPISTEMIC_GOVERNANCE.md"
    ).read_text(encoding="utf-8")

    assert "Agent prose is not evidence." in guidance
    assert "EPISTEMIC_GOVERNANCE.md" in guidance
    for status in governance.ClaimStatus:
        assert f"`{status.value.upper()}`" in protocol
