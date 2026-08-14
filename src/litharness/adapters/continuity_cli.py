"""Subprocess transport for ContinuityEvaluation's live-bundle command."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


class ContinuityProcessError(RuntimeError):
    """The configured evaluator could not return a readable artifact."""


@dataclass(frozen=True, slots=True)
class ContinuityCliRunner:
    command: tuple[str, ...]
    timeout_seconds: float = 120.0

    def __init__(self, command: Sequence[str], *, timeout_seconds: float = 120.0) -> None:
        if not command:
            raise ValueError("continuity evaluator command cannot be empty")
        object.__setattr__(self, "command", tuple(command))
        object.__setattr__(self, "timeout_seconds", timeout_seconds)

    def __call__(self, bundle: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        try:
            completed = subprocess.run(
                [*self.command, "--bundle", "-", "--output", "-"],
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ContinuityProcessError(
                f"could not run {self.command[0]!r}: {type(error).__name__}: {error}"
            ) from error
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic"
            raise ContinuityProcessError(
                f"continuity evaluator exited {completed.returncode}: {detail[:2000]}"
            )
        try:
            artifact = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise ContinuityProcessError(
                f"continuity evaluator returned invalid JSON: {error}"
            ) from error
        if not isinstance(artifact, dict):
            raise ContinuityProcessError("continuity evaluator returned a non-object artifact")
        return artifact


__all__ = ["ContinuityCliRunner", "ContinuityProcessError"]
