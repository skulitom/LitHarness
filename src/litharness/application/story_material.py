"""One source for invented developments; optional coordinates never enter active views.

References establish structural consistency, not the meaning or quality of model prose.
Author instructions are held separately by Concept and are never classified here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from litharness.domain.events import payload_digest

VERSION = "story-material.v1"
HORIZONS = ("before_opening", "first_arc", "later", "unresolved")
_TEXT = {"type": "string", "minLength": 1}
_REFS = {"type": "array", "items": _TEXT, "uniqueItems": True}


def _schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _array(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": _schema(properties)}


SCHEMA = _schema(
    {
        "version": {"type": "string", "enum": [VERSION]},
        "world": _TEXT,
        "experience_brief": _TEXT,
        "developments": _array(
            {
                "id": _TEXT,
                "statement": _TEXT,
                "depends_on": _REFS,
                "horizon": {"type": "string", "enum": list(HORIZONS)},
            }
        ),
        "first_use_id": _TEXT,
        "turn_id": _TEXT,
        "questions": _array({"subject": _TEXT, "development_ids": _REFS}),
        "staging_options": _array({"id": _TEXT, "statement": _TEXT, "development_ids": _REFS}),
        "placement_suggestions": _array(
            {
                "development_id": _TEXT,
                "chapter": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
                "scene": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
            }
        ),
    }
)

PLANNING_RULE = (
    "book_concept.story_material is the single source of generated story intentions. "
    "Its developments have stable ids within source_id; questions, first_use_id and turn_id "
    "refer to those developments rather than retelling them. Preserve their consequences, "
    "participant interests, capability limits and necessary dependencies. staging_options "
    "are revisable physical arrangements. The experience_brief proposes what the character "
    "wants, does, experiences and chooses next; give connected activity room for consequence "
    "and response. Choose coverage within the actual writing_layout. Optional generated "
    "coordinates are withheld; no generated proposal creates an author deadline. The "
    "unchanged author brief, applicable author locks, accepted facts and actual open_promises "
    "take priority. before_opening is proposed setup; first_arc, later and unresolved are "
    "scope bounds, not proof of completion or permission to resolve future material now. "
    "On continuation reconcile these same ids with earlier_accepted_scenes and "
    "story_state_at_arc_entry. Neither a prior outline nor an arc number establishes that "
    "a development happened. Carry remaining consequences forward; do not repeat completed "
    "acquisitions, disclosures or settlements. Record changes of coverage explicitly."
)


def _object(value: Any, keys: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{name} must contain exactly {', '.join(sorted(keys))}")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _refs(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list of references")
    refs = tuple(_text(v, name) for v in value)
    if len(set(refs)) != len(refs):
        raise ValueError(f"{name} has duplicate references")
    return refs


@dataclass(frozen=True, slots=True)
class Development:
    id: str
    statement: str
    depends_on: tuple[str, ...]
    horizon: str


@dataclass(frozen=True, slots=True)
class Question:
    subject: str
    development_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StagingOption:
    id: str
    statement: str
    development_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Placement:
    development_id: str
    chapter: int | None
    scene: int | None


@dataclass(frozen=True, slots=True)
class StoryMaterial:
    world: str
    experience_brief: str
    developments: tuple[Development, ...]
    first_use_id: str
    turn_id: str
    questions: tuple[Question, ...]
    staging_options: tuple[StagingOption, ...]
    placement_suggestions: tuple[Placement, ...]
    version: str = VERSION

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> StoryMaterial:
        data = _object(payload, set(SCHEMA["properties"]), "story_material")
        if data["version"] != VERSION:
            raise ValueError("unsupported story_material.version")
        rows: dict[str, list[Mapping[str, Any]]] = {}
        for name in ("developments", "questions", "staging_options", "placement_suggestions"):
            if not isinstance(data[name], list):
                raise ValueError(f"story_material.{name} must be a list")
            keys = set(SCHEMA["properties"][name]["items"]["properties"])
            rows[name] = [_object(row, keys, name) for row in data[name]]
        developments = tuple(
            Development(
                _text(row["id"], "development.id"),
                _text(row["statement"], "development.statement"),
                _refs(row["depends_on"], "development.depends_on"),
                _text(row["horizon"], "development.horizon"),
            )
            for row in rows["developments"]
        )
        ids = {d.id for d in developments}
        if not developments or len(ids) != len(developments):
            raise ValueError("developments need unique ids and cannot be empty")
        if any(d.horizon not in HORIZONS for d in developments):
            raise ValueError("unsupported development.horizon")
        if any(d.id in d.depends_on or not set(d.depends_on) <= ids for d in developments):
            raise ValueError("invalid development dependency")
        pending = {d.id: set(d.depends_on) for d in developments}
        while pending:
            ready = {key for key, parents in pending.items() if not parents & pending.keys()}
            if not ready:
                raise ValueError("cyclic development dependencies")
            pending = {key: parents for key, parents in pending.items() if key not in ready}
        first_use = _text(data["first_use_id"], "first_use_id")
        turn = _text(data["turn_id"], "turn_id")
        if first_use not in ids or turn not in ids:
            raise ValueError("first_use_id and turn_id must reference developments")
        questions = tuple(
            Question(
                _text(row["subject"], "question.subject"),
                _refs(row["development_ids"], "question.development_ids"),
            )
            for row in rows["questions"]
        )
        if not 2 <= len(questions) <= 4 or len({q.subject for q in questions}) != len(questions):
            raise ValueError("questions need two to four distinct subjects")
        options = tuple(
            StagingOption(
                _text(row["id"], "staging.id"),
                _text(row["statement"], "staging.statement"),
                _refs(row["development_ids"], "staging.development_ids"),
            )
            for row in rows["staging_options"]
        )
        option_ids = {s.id for s in options}
        if option_ids & ids or len(option_ids) != len(options):
            raise ValueError("staging ids must be unique and distinct from development ids")
        references = [q.development_ids for q in questions] + [s.development_ids for s in options]
        for refs in references:
            if not refs or not set(refs) <= ids:
                raise ValueError("questions and staging must reference existing developments")
        placements = []
        placed: set[str] = set()
        for row in rows["placement_suggestions"]:
            target = _text(row["development_id"], "placement.development_id")
            if target not in ids or target in placed:
                raise ValueError("placement needs an existing, uniquely placed development")
            placed.add(target)
            if row["chapter"] is None and row["scene"] is None:
                raise ValueError("placement needs a chapter or scene coordinate")
            for key in ("chapter", "scene"):
                value = row[key]
                if value is not None and (type(value) is not int or value < 1):
                    raise ValueError(f"placement.{key} must be a positive integer or null")
            placements.append(Placement(target, row["chapter"], row["scene"]))
        return cls(
            _text(data["world"], "story_material.world"),
            _text(data["experience_brief"], "story_material.experience_brief"),
            developments,
            first_use,
            turn,
            questions,
            options,
            tuple(placements),
        )

    def to_jsonable(self) -> dict[str, Any]:
        # asdict retains tuples; JSON normalization also supplies lists to validation.
        return json.loads(json.dumps(asdict(self)))  # type: ignore[no-any-return]

    def for_planning(self) -> dict[str, Any]:
        material = self.to_jsonable()
        del material["placement_suggestions"]
        return {
            **material,
            "source_id": payload_digest(material),
            "authority": "generated_proposal",
        }

    def render_intentions(self) -> str:
        material = self.for_planning()
        # World properties have their own projection. The Architect supports referenced
        # intentions without another copy of the setting or the planner's experience brief.
        del material["world"]
        del material["experience_brief"]
        return json.dumps(material, ensure_ascii=False, indent=2)

    @property
    def protected_paths(self) -> set[str]:
        """Provenance, coordinates and references are not quantity-editable prose."""
        paths = {"version", "first_use_id", "turn_id"}
        for index, development in enumerate(self.developments):
            paths.update({f"developments.{index}.id", f"developments.{index}.horizon"})
            paths.update(
                f"developments.{index}.depends_on.{j}" for j in range(len(development.depends_on))
            )
        for group in ("questions", "staging_options"):
            for index, item in enumerate(getattr(self, group)):
                if group == "staging_options":
                    paths.add(f"{group}.{index}.id")
                paths.update(
                    f"{group}.{index}.development_ids.{j}" for j in range(len(item.development_ids))
                )
        paths.update(
            f"placement_suggestions.{i}.development_id"
            for i in range(len(self.placement_suggestions))
        )
        return paths
