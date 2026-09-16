"""A scene-sized planning handoff, separate from the prose that proposed the book."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PREFIX = "litharness.scene-brief.v1\n"
READER_PREFIX = "litharness.scene-brief.v2\n"
TREATMENT = (
    "Give space to the moments that change a choice, expectation or relationship; necessary "
    "routine activity can pass in summary or omission while its causal facts remain clear. "
    "The changes below establish what develops, not equal-length episodes or a requirement "
    "to narrate every operation; allow the character's response to affect the next moment."
)
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
READER_SCHEMA: dict[str, Any] = {
    **SCHEMA,
    "required": [*SCHEMA["required"], "reader_facts"],
    "properties": {
        **SCHEMA["properties"],
        "reader_facts": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}


@dataclass(frozen=True, slots=True)
class SceneBrief:
    situation: str
    pursuit: str
    changes: tuple[str, ...]
    future_dependencies: tuple[str, ...] = ()
    # None retains the exact v1 storage contract; () is an explicit v2 empty selection.
    reader_facts: tuple[str, ...] | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> SceneBrief:
        schema = READER_SCHEMA if "reader_facts" in payload else SCHEMA
        if set(payload) != set(schema["required"]):
            raise ValueError("scene brief must carry exactly " + ", ".join(schema["required"]))

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
            reader_facts=texts("reader_facts") if "reader_facts" in payload else None,
        )

    @classmethod
    def from_text(cls, value: str) -> SceneBrief | None:
        """Read our tagged plans strictly; untagged legacy/author plans stay untouched."""
        value = value.strip()
        if not value.startswith("litharness.scene-brief."):
            return None
        prefix = next((p for p in (PREFIX, READER_PREFIX) if value.startswith(p)), None)
        if prefix is None:
            raise ValueError("unsupported scene brief version")
        payload = json.loads(value[len(prefix):])
        if not isinstance(payload, Mapping):
            raise ValueError("scene brief must be an object")
        if ("reader_facts" in payload) != (prefix == READER_PREFIX):
            raise ValueError("scene brief fields do not match its version")
        return cls.from_payload(payload)

    def to_text(self) -> str:
        prefix = READER_PREFIX if self.reader_facts is not None else PREFIX
        return prefix + json.dumps({
            "situation": self.situation,
            "pursuit": self.pursuit,
            "changes": list(self.changes),
            "future_dependencies": list(self.future_dependencies),
            **({"reader_facts": list(self.reader_facts)} if self.reader_facts is not None else {}),
        }, ensure_ascii=False, sort_keys=True)

    def render(self) -> str:
        lines = [
            "Planned scene. Established prose, world rules and author locks take precedence. "
            "Develop the action in fresh prose; the wording here is planning material.",
            TREATMENT,
            f"Starting situation: {self.situation}",
            f"Immediate pursuit: {self.pursuit}",
        ]
        if self.reader_facts:
            lines += [
                "Facts to establish for the reader in this scene:",
                "Make these facts understandable in the action, thought or narration available "
                "to this viewpoint. They need not be disclosed to other characters. Keep their "
                "meaning when compressing routine action; do not copy the planning wording.",
                *(f"- {fact}" for fact in self.reader_facts),
            ]
        lines += [
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
