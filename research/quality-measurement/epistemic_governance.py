"""Validate content-addressed research claim records.

This module gives the epistemic states in ``EPISTEMIC_GOVERNANCE.md`` a small executable
boundary.  It does not decide whether a claim is true.  It checks that a claimed state has
the kinds of artifacts that state requires, and that every referenced artifact still has the
bytes the record names.

Usage::

    uv run python research/quality-measurement/epistemic_governance.py claim.json

The claim record is intentionally a pointer layer, not another results ledger.  Raw results,
registrations, controls, and qualification artifacts keep their existing canonical homes.
"""

from __future__ import annotations

import argparse
import enum
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SCHEMA = "litharness.epistemic-claim.v1"


class ClaimValidationError(ValueError):
    """A claim record is structurally invalid or points to changed evidence."""


class ClaimStatus(enum.StrEnum):
    CONJECTURE = "conjecture"
    REGISTERED = "registered"
    OBSERVED = "observed"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    QUALIFIED = "qualified"


class ArtifactKind(enum.StrEnum):
    REGISTRATION = "registration"
    RAW_RESULT = "raw_result"
    DERIVED_RESULT = "derived_result"
    CONTROL_RESULT = "control_result"
    QUALIFICATION = "qualification"
    LITERATURE = "literature"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    kind: ArtifactKind
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    claim_id: str
    statement: str
    status: ClaimStatus
    artifacts: tuple[ArtifactRef, ...]

    def canonical_payload(self) -> dict[str, object]:
        refs = sorted(self.artifacts, key=lambda ref: (ref.kind.value, ref.path, ref.sha256))
        return {
            "schema": SCHEMA,
            "claim_id": self.claim_id,
            "statement": self.statement,
            "status": self.status.value,
            "artifacts": [
                {"kind": ref.kind.value, "path": ref.path, "sha256": ref.sha256}
                for ref in refs
            ],
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


_TOP_LEVEL_KEYS = frozenset({"schema", "claim_id", "statement", "status", "artifacts"})
_ARTIFACT_KEYS = frozenset({"kind", "path", "sha256"})
_RESULT_KINDS = frozenset({ArtifactKind.RAW_RESULT, ArtifactKind.DERIVED_RESULT})
_HEX = frozenset("0123456789abcdef")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ClaimValidationError(f"{label} must be a JSON object with string keys")
    return value


def _exact_keys(value: Mapping[str, object], expected: frozenset[str], label: str) -> None:
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"missing {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown {', '.join(unknown)}")
        raise ClaimValidationError(f"{label} has " + "; ".join(parts))


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClaimValidationError(f"{label} must be a non-empty string")
    return value


def _artifact_ref(value: object, index: int) -> ArtifactRef:
    payload = _mapping(value, f"artifacts[{index}]")
    _exact_keys(payload, _ARTIFACT_KEYS, f"artifacts[{index}]")
    kind_text = _nonempty_string(payload["kind"], f"artifacts[{index}].kind")
    try:
        kind = ArtifactKind(kind_text)
    except ValueError as exc:
        choices = ", ".join(kind.value for kind in ArtifactKind)
        raise ClaimValidationError(
            f"artifacts[{index}].kind must be one of: {choices}"
        ) from exc

    path = _nonempty_string(payload["path"], f"artifacts[{index}].path")
    parsed_path = PurePosixPath(path)
    if (
        not parsed_path.parts
        or parsed_path.is_absolute()
        or "\\" in path
        or path != parsed_path.as_posix()
        or ".." in parsed_path.parts
        or ":" in parsed_path.parts[0]
    ):
        raise ClaimValidationError(
            f"artifacts[{index}].path must be a normalized repo-relative POSIX path"
        )

    digest = _nonempty_string(payload["sha256"], f"artifacts[{index}].sha256")
    if len(digest) != 64 or any(char not in _HEX for char in digest):
        raise ClaimValidationError(
            f"artifacts[{index}].sha256 must be 64 lowercase hexadecimal characters"
        )
    return ArtifactRef(kind=kind, path=path, sha256=digest)


def parse_claim(value: object) -> ClaimRecord:
    """Parse and validate the epistemic meaning of one JSON-compatible claim record."""

    payload = _mapping(value, "claim")
    _exact_keys(payload, _TOP_LEVEL_KEYS, "claim")
    if payload["schema"] != SCHEMA:
        raise ClaimValidationError(f"claim.schema must be {SCHEMA!r}")

    claim_id = _nonempty_string(payload["claim_id"], "claim.claim_id")
    statement = _nonempty_string(payload["statement"], "claim.statement")
    status_text = _nonempty_string(payload["status"], "claim.status")
    try:
        status = ClaimStatus(status_text)
    except ValueError as exc:
        choices = ", ".join(status.value for status in ClaimStatus)
        raise ClaimValidationError(f"claim.status must be one of: {choices}") from exc

    artifact_values = payload["artifacts"]
    if not isinstance(artifact_values, Sequence) or isinstance(artifact_values, (str, bytes)):
        raise ClaimValidationError("claim.artifacts must be a JSON array")
    artifacts = tuple(_artifact_ref(item, index) for index, item in enumerate(artifact_values))
    if len(set(artifacts)) != len(artifacts):
        raise ClaimValidationError("claim.artifacts contains a duplicate reference")

    kinds = {artifact.kind for artifact in artifacts}
    allowed = {
        ClaimStatus.CONJECTURE: {ArtifactKind.LITERATURE},
        ClaimStatus.REGISTERED: {ArtifactKind.LITERATURE, ArtifactKind.REGISTRATION},
        ClaimStatus.OBSERVED: {
            ArtifactKind.LITERATURE,
            ArtifactKind.REGISTRATION,
            ArtifactKind.RAW_RESULT,
            ArtifactKind.DERIVED_RESULT,
            ArtifactKind.CONTROL_RESULT,
        },
        ClaimStatus.SUPPORTED: {
            ArtifactKind.LITERATURE,
            ArtifactKind.REGISTRATION,
            ArtifactKind.RAW_RESULT,
            ArtifactKind.DERIVED_RESULT,
            ArtifactKind.CONTROL_RESULT,
        },
        ClaimStatus.REFUTED: {
            ArtifactKind.LITERATURE,
            ArtifactKind.REGISTRATION,
            ArtifactKind.RAW_RESULT,
            ArtifactKind.DERIVED_RESULT,
            ArtifactKind.CONTROL_RESULT,
        },
        ClaimStatus.QUALIFIED: set(ArtifactKind),
    }[status]
    unexpected = sorted(kind.value for kind in kinds - allowed)
    if unexpected:
        raise ClaimValidationError(
            f"{status.value} claims cannot cite artifact kind(s): {', '.join(unexpected)}"
        )

    if status is not ClaimStatus.CONJECTURE and ArtifactKind.REGISTRATION not in kinds:
        raise ClaimValidationError(f"{status.value} claims require a registration artifact")
    if status in {
        ClaimStatus.OBSERVED,
        ClaimStatus.SUPPORTED,
        ClaimStatus.REFUTED,
        ClaimStatus.QUALIFIED,
    } and not kinds.intersection(_RESULT_KINDS):
        raise ClaimValidationError(f"{status.value} claims require a raw or derived result")
    if status in {ClaimStatus.SUPPORTED, ClaimStatus.REFUTED, ClaimStatus.QUALIFIED} and (
        ArtifactKind.CONTROL_RESULT not in kinds
    ):
        raise ClaimValidationError(f"{status.value} claims require a control result")
    if status is ClaimStatus.QUALIFIED and ArtifactKind.QUALIFICATION not in kinds:
        raise ClaimValidationError("qualified claims require a qualification artifact")

    return ClaimRecord(
        claim_id=claim_id,
        statement=statement,
        status=status,
        artifacts=artifacts,
    )


def verify_artifacts(record: ClaimRecord, repo_root: Path) -> None:
    """Verify every referenced file is inside ``repo_root`` and matches its recorded digest."""

    root = repo_root.resolve()
    for artifact in record.artifacts:
        path = (root / artifact.path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ClaimValidationError(f"artifact escapes repository: {artifact.path}") from exc
        if not path.is_file():
            raise ClaimValidationError(f"artifact does not exist: {artifact.path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != artifact.sha256:
            raise ClaimValidationError(
                f"artifact digest changed: {artifact.path} "
                f"(expected {artifact.sha256}, got {actual})"
            )


def _repo_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / ".git").exists():
            return candidate
    raise ClaimValidationError(f"cannot find repository root above {start}")


def load_and_verify(path: Path) -> ClaimRecord:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClaimValidationError(f"cannot read {path}: {exc}") from exc
    record = parse_claim(payload)
    verify_artifacts(record, _repo_root(path.parent))
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", nargs="+", type=Path, help="claim-record JSON file(s)")
    args = parser.parse_args(argv)
    failed = False
    for path in args.claims:
        try:
            record = load_and_verify(path)
        except ClaimValidationError as exc:
            failed = True
            print(f"{path}: INVALID: {exc}")
        else:
            print(f"{path}: {record.status.value.upper()} {record.claim_id} {record.digest}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
