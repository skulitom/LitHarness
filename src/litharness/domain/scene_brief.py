"""A scene-sized planning handoff, separate from the prose that proposed the book."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PREFIX = "litharness.scene-brief.v1\n"
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["situation", "pursuit", "changes", "future_dependencies"],
    "properties": {
        "situation": {"type": "string", "minLength": 1},
        "pursuit": {"type": "string", "minLength": 1},
        "changes": {
            "type": "array", "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "future_dependencies": {
            "type": "array", "items": {"type": "string", "minLength": 1},
        },
    },
}


@dataclass(frozen=True, slots=True)
class SceneBrief:
    situation: str
    pursuit: str
    changes: tuple[str, ...]
    future_dependencies: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> SceneBrief:
        if set(payload) != set(SCHEMA["required"]):
            raise ValueError("scene brief must carry only situation, pursuit, changes, "
                             "and future_dependencies")

        def text(value: Any, field: str) -> str:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"scene brief {field} must be non-empty text")
            return value.strip()

        def texts(field: str, *, required: bool = False) -> tuple[str, ...]:
            value = payload[field]
            if not isinstance(value, list) or (required and not value):
                qualifier = "non-empty " if required else ""
                raise ValueError(f"scene brief {field} must be a {qualifier}list")
            return tuple(text(entry, field) for entry in value)

        return cls(
            situation=text(payload["situation"], "situation"),
            pursuit=text(payload["pursuit"], "pursuit"),
            changes=texts("changes", required=True),
            future_dependencies=texts("future_dependencies"),
        )

    @classmethod
    def from_text(cls, value: str) -> SceneBrief | None:
        """Read our tagged plans strictly; untagged legacy/author plans stay untouched."""
        value = value.strip()
        if not value.startswith("litharness.scene-brief."):
            return None
        if not value.startswith(PREFIX):
            raise ValueError("unsupported scene brief version")
        payload = json.loads(value[len(PREFIX):])
        if not isinstance(payload, Mapping):
            raise ValueError("scene brief must be an object")
        return cls.from_payload(payload)

    def to_text(self) -> str:
        return PREFIX + json.dumps({
            "situation": self.situation,
            "pursuit": self.pursuit,
            "changes": list(self.changes),
            "future_dependencies": list(self.future_dependencies),
        }, ensure_ascii=False, sort_keys=True)

    def render(self) -> str:
        lines = [
            "Planned scene. Established prose, world rules and author locks take precedence. "
            "Develop the action in fresh prose; the wording here is planning material.",
            f"Starting situation: {self.situation}",
            f"Immediate pursuit: {self.pursuit}",
            "Intended changes, in causal order:",
            *(f"- {change}" for change in self.changes),
        ]
        if self.future_dependencies:
            lines += [
                "Later-story dependencies to preserve, not events or explanations to insert now:",
                *(f"- {dependency}" for dependency in self.future_dependencies),
            ]
        return "\n".join(lines)


def render_plan(value: str) -> str:
    brief = SceneBrief.from_text(value)
    return brief.render() if brief is not None else value
