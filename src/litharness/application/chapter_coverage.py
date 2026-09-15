"""Validate a planner's chapter grouping; retain its intentions without rating them."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from litharness.application.chapter_layout import WritingLayout
from litharness.domain.scene_brief import SCHEMA as SCENE_BRIEF_SCHEMA

CHAPTERS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object", "additionalProperties": False,
        "required": ["chapter", "intent", "adaptation", "scenes"],
        "properties": {
            "chapter": {"type": "integer", "minimum": 1},
            "intent": {"type": "string", "minLength": 1},
            "adaptation": {"type": "string", "minLength": 1},
            "scenes": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["ordinal", "brief"],
                    "properties": {
                        "ordinal": {"type": "integer"}, "brief": SCENE_BRIEF_SCHEMA,
                    },
                },
            },
        },
    },
}


@dataclass(frozen=True, slots=True)
class ChapterCoverage:
    chapter: int
    ordinals: tuple[int, ...]
    intent: str
    adaptation: str

    def to_text(self, scene_ids: Mapping[int, str]) -> str:
        return "litharness.chapter-coverage.v1\n" + json.dumps({
            "chapter": self.chapter,
            "scene_ids": [scene_ids[ordinal] for ordinal in self.ordinals],
            "intent": self.intent,
            "adaptation": self.adaptation,
        }, ensure_ascii=False, sort_keys=True)


def reconcile(
    payload: Mapping[str, Any], layout: WritingLayout,
) -> tuple[list[Mapping[str, Any]], tuple[ChapterCoverage, ...]]:
    """Flatten only after exact chapter membership agrees with the supplied layout.

    The interpretation inside intent/adaptation is the planner's proposal. This validates
    coordinates and required text, not semantic fidelity, feasibility or enjoyment.
    """
    raw = payload.get("chapters")
    if not isinstance(raw, list) or len(raw) != len(layout.chapters):
        raise ValueError("chapter coverage must describe each requested chapter exactly once")
    if "scenes" in payload:
        raise ValueError("chapter coverage must put scenes inside their actual chapters")
    expected = dict(layout.chapters)
    rows: dict[int, tuple[ChapterCoverage, list[Mapping[str, Any]]]] = {}
    for entry in raw:
        if not isinstance(entry, Mapping) or set(entry) != {
            "chapter", "intent", "adaptation", "scenes",
        }:
            raise ValueError("chapter coverage needs chapter, intent, adaptation and scenes")
        chapter = entry["chapter"]
        if type(chapter) is not int or chapter not in expected or chapter in rows:
            raise ValueError("chapter coverage repeats or invents a chapter")
        for field in ("intent", "adaptation"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(f"chapter coverage {field} must be non-empty text")
        scenes = entry["scenes"]
        if not isinstance(scenes, list) or not scenes:
            raise ValueError("chapter coverage needs a non-empty scene list")
        ordinals = []
        for scene in scenes:
            if not isinstance(scene, Mapping) or type(scene.get("ordinal")) is not int:
                raise ValueError("chapter coverage needs integer scene ordinals")
            ordinals.append(scene["ordinal"])
        if sorted(ordinals) != list(expected[chapter]):
            raise ValueError(f"chapter {chapter} must contain scenes {list(expected[chapter])}")
        rows[chapter] = (
            ChapterCoverage(chapter, expected[chapter], entry["intent"].strip(),
                            entry["adaptation"].strip()), scenes,
        )
    return (
        [scene for chapter, _ in layout.chapters for scene in rows[chapter][1]],
        tuple(rows[chapter][0] for chapter, _ in layout.chapters),
    )
