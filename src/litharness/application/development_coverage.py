"""Account for source developments in an outline without certifying their enactment."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from litharness.application.story_material import StoryMaterial
from litharness.domain.scene_brief import READER_SCHEMA

PREFIX = "litharness.development-coverage.v1\n"
_TEXT = {"type": "string", "minLength": 1}
_ENTRY: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["development_id", "disposition", "scene_ordinals", "reason"],
    "properties": {
        "development_id": _TEXT,
        "disposition": {"type": "string", "enum": ["planned", "established", "deferred"]},
        "scene_ordinals": {
            "type": "array", "uniqueItems": True,
            "items": {"type": "integer", "minimum": 1},
        },
        "reason": _TEXT,
    },
}
SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["source_id", "entries"],
    "properties": {
        "source_id": _TEXT,
        "entries": {"type": "array", "minItems": 1, "items": _ENTRY},
    },
}
RULE = (
    "Before allocating scenes, decide what connected change this requested sequence reaches "
    "within its prose budget. Development ids and dependencies are causal units, not chapter "
    "boundaries: several prerequisite developments may belong in one chapter, and a development "
    "may span chapters when its consequences need that space. Preserve necessary causes, "
    "character responses and author constraints while grouping or summarizing activity. "
    "Return development_coverage for every supplied development exactly once, using the exact "
    "source_id. planned lists the response-local scene ordinals that enact it; established "
    "names setup or accepted history that already establishes it; deferred explains what stays "
    "outside this request and why. Established and deferred entries have no scene ordinals. "
    "A mention or offer is not enactment. For partial enactment use planned, list its scenes, "
    "and identify the remaining consequence in reason. For established entries cite the supplied "
    "setup or accepted history, never an earlier plan alone. Keep the summary, expected_outcome, "
    "chapter coverage and scene briefs consistent with these allocations. Preserve later and "
    "unresolved bounds; this accounting imposes no reward quota or generated author deadline."
)
READER_RULE = (
    "Each scene brief also returns reader_facts: select only facts the reader needs to understand "
    "in this scene for its pursuit, personal stakes or changed choice to make sense. Background "
    "in situation is not automatically a disclosure instruction. If a defining past act matters "
    "now, identify the act and its consequence instead of replacing it with generic shame or "
    "fear. Use an empty list when no such fact needs establishing. Select from supplied character "
    "and story material; do not invent a quota or repeat the whole biography. Distinguish what "
    "the reader can learn from what other characters know. Respect viewpoint access, author "
    "locks, established disclosures and future reveal limits. Facts reserved for later remain "
    "in future_dependencies, not reader_facts."
)


def outline_schema(base: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(base)
    schema["required"].append("development_coverage")
    schema["properties"]["development_coverage"] = SCHEMA
    properties = schema["properties"]
    scenes = (properties["chapters"]["items"]["properties"]["scenes"]
              if "chapters" in properties else properties["scenes"])
    scenes["items"]["properties"]["brief"] = READER_SCHEMA
    return schema


def to_text(
    payload: Any, material: StoryMaterial, scene_ids: Mapping[int, str],
) -> str:
    """Check source identity and coordinates, then store stable scene ids, never a score."""
    if not isinstance(payload, Mapping) or set(payload) != {"source_id", "entries"}:
        raise ValueError("development coverage needs source_id and entries")
    source_id = material.for_planning()["source_id"]
    if payload["source_id"] != source_id:
        raise ValueError("development coverage refers to a different story source")
    entries = payload["entries"]
    if not isinstance(entries, list):
        raise ValueError("development coverage entries must be a list")
    expected = {development.id for development in material.developments}
    normalized = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != set(_ENTRY["required"]):
            raise ValueError("development coverage entry has missing or unknown fields")
        identity = entry["development_id"]
        if not isinstance(identity, str) or identity not in expected or identity in normalized:
            raise ValueError("development coverage repeats or invents a development")
        disposition = entry["disposition"]
        if disposition not in ("planned", "established", "deferred"):
            raise ValueError("development coverage has an unknown disposition")
        ordinals = entry["scene_ordinals"]
        if (not isinstance(ordinals, list)
                or any(type(n) is not int or n not in scene_ids for n in ordinals)
                or len(set(ordinals)) != len(ordinals)):
            raise ValueError("development coverage has invalid scene ordinals")
        if bool(ordinals) != (disposition == "planned"):
            raise ValueError("only planned developments must name one or more scenes")
        reason = entry["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("development coverage needs an allocation reason")
        normalized[identity] = {
            "development_id": identity, "disposition": disposition,
            "scene_ids": [scene_ids[n] for n in sorted(ordinals)], "reason": reason.strip(),
        }
    if set(normalized) != expected:
        raise ValueError("development coverage must account for every supplied development")
    return PREFIX + json.dumps({
        "source_id": source_id,
        "requested_scene_ids": list(scene_ids.values()),
        "entries": [normalized[d.id] for d in material.developments],
    }, ensure_ascii=False, sort_keys=True)
