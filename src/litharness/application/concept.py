"""Invent and retain one book concept; project the material each downstream role needs.

Concepts are unlocked BOOK_PLAN intentions, including discovery, future actions and debts.
Listing and world-building receive separate projections; outlines retain the complete plan.
Once scenes are planned, drafting uses their handoffs and the original author brief.
Legacy concept files remain readable. See the decision ledger for the invention history.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import litharness_contracts as lc

from litharness.application import chapter_layout, precision, story_material
from litharness.application.discovery import DIRECTION, WORLD_DIRECTION, Discovery
from litharness.application.overview import FIRST_PERSON_ASK
from litharness.domain import house, schema_words
from litharness.domain.generation import CompletionRequest
from litharness.domain.invention import InventionSeed
from litharness.domain.writers import Writer

CONCEPT_PROFILE = "writer.concept.v1"
DISCOVERY_CONCEPT_PROFILE = "writer.concept.discovery.v10"
MATERIAL_CONCEPT_PROFILE = "writer.concept.material.v3"

#: The plan item id the concept is persisted under; one per book, like `plan-premise`.
CONCEPT_PLAN_ID = "plan-concept"

MAX_OUTPUT_TOKENS = 4000

#: How many questions a book opens on purpose. Fewer than two is a book with one thing in it;
#: more than four at the concept is a list the outline will not schedule.
MIN_DEBTS = 2
MAX_DEBTS = 4

#: A horizon of one step is no climb.
MIN_STEPS = 2

BEFORE_CHAPTER_ONE = "before chapter one"
INSIDE_FIRST_ARC = "inside the first arc"
AFTER_FIRST_ARC = "after the first arc"
TURN_WHEN: tuple[str, ...] = (BEFORE_CHAPTER_ONE, INSIDE_FIRST_ARC, AFTER_FIRST_ARC)


class MalformedConcept(ValueError):
    """A concept the stages below could not put to work, with the field named."""


#: **Every property is material a later stage consumes, and there is no slot for an opinion.**
#: The listing loop's containment (`tests/test_listing_loop.py`) is that a schema with no verdict
#: field cannot become a judge; the same holds here. `second_system` is required and nullable
#: rather than optional, so a model that ignored the question is distinguishable from a book with
#: one system.
CONCEPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "person_before",
        "exception",
        "first_use",
        "want",
        "system",
        "threat",
        "turn",
        "second_system",
        "first_arc",
        "debts",
    ],
    "properties": {
        "person_before": {"type": "string"},
        "exception": {"type": "string"},
        "first_use": {"type": "string"},
        "want": {"type": "string"},
        "system": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "manner", "look", "steps", "strongest_known", "pays"],
            "properties": {
                "name": {"type": "string"},
                "manner": {"type": "string"},
                "look": {"type": "string"},
                "steps": {"type": "integer"},
                "strongest_known": {"type": "string"},
                "pays": {"type": "string"},
            },
        },
        "threat": {
            "type": "object",
            "additionalProperties": False,
            "required": ["what", "first_reach"],
            "properties": {
                "what": {"type": "string"},
                "first_reach": {"type": "string"},
            },
        },
        "turn": {
            "type": "object",
            "additionalProperties": False,
            "required": ["event", "when"],
            "properties": {
                "event": {"type": "string"},
                "when": {"type": "string", "enum": list(TURN_WHEN)},
            },
        },
        "second_system": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "manner", "kept"],
                    "properties": {
                        "name": {"type": "string"},
                        "manner": {"type": "string"},
                        "kept": {"type": "string"},
                    },
                },
            ]
        },
        "first_arc": {
            "type": "object",
            "additionalProperties": False,
            "required": ["opens", "middle", "closes"],
            "properties": {
                "opens": {"type": "string"},
                "middle": {"type": "string"},
                "closes": {"type": "string"},
            },
        },
        "debts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["subject", "owed", "due_scene"],
                "properties": {
                    "subject": {"type": "string"},
                    "owed": {"type": "string"},
                    "due_scene": {"type": "integer"},
                },
            },
        },
    },
}

#: **The names a model is shown for four stored keys** (stage-0 §262, read 20). The stored
#: names keep a bookkeeping frame (a question the book owes, a step up that pays), and a key
#: name is vocabulary to the model that reads it: draw 2's planner, shown `debts`, `owed` and
#: `pays`, put commerce words into 13 of its 24 scene briefs (exposure, not a measured cause).
#: Stored `concept.json` keeps its names, so nothing migrates; every request schema, task
#: text, precision path and planning projection shows these names, and `from_payload` reads
#: both. The structured route's questions were already `questions` (`story_material.SCHEMA`).
PRESENTED_NAMES: dict[str, str] = {
    "debts": "open_questions",
    "owed": "question",
    "due_scene": "answered_by_scene",
    "pays": "what_rising_gives",
}
_STORED_NAMES = {shown: stored for stored, shown in PRESENTED_NAMES.items()}


def _presented_object(schema: Mapping[str, Any]) -> dict[str, Any]:
    """An object schema written in stored names, with its properties under the shown ones."""
    return {
        **schema,
        "required": [PRESENTED_NAMES.get(name, name) for name in schema["required"]],
        "properties": {
            PRESENTED_NAMES.get(name, name): value for name, value in schema["properties"].items()
        },
    }


#: New concepts also say where the protagonist starts on the counted ranks (stage-0 §255).
#: CONCEPT_SCHEMA and the legacy request stay unchanged, and stored concepts without it read.
COUNTED_SYSTEM_SCHEMA: dict[str, Any] = _presented_object({
    "type": "object",
    "additionalProperties": False,
    "required": [*CONCEPT_SCHEMA["properties"]["system"]["required"], "start_rank"],
    "properties": {
        **CONCEPT_SCHEMA["properties"]["system"]["properties"],
        "start_rank": {"type": "integer"},
    },
})
DISCOVERY_CONCEPT_SCHEMA: dict[str, Any] = _presented_object({
    **CONCEPT_SCHEMA,
    "properties": {
        **CONCEPT_SCHEMA["properties"],
        "system": COUNTED_SYSTEM_SCHEMA,
        "debts": {
            **CONCEPT_SCHEMA["properties"]["debts"],
            "items": _presented_object(CONCEPT_SCHEMA["properties"]["debts"]["items"]),
        },
    },
})


@dataclass(frozen=True, slots=True)
class SystemConcept:
    """The system as the book conceives it, before the world declares it."""

    name: str
    #: How it shows itself when it speaks or appears: a manner, in one clause.
    manner: str
    #: What a reader sees when it appears: colour, place, light, type (read 18 §2.2: a notice
    #: given by analogy and negation produced no image).
    look: str
    #: How many steps up it goes. The horizon the reader can feel, as a count.
    steps: int
    #: Where the strongest person anyone has heard of stands, as a count.
    strongest_known: str
    #: What a step up buys a person, in the words they used before it came (read 18 §2.1: a
    #: ladder with nothing attached reaches the page as a number going up for no reason).
    pays: str
    #: The counted rank the protagonist holds when the book opens, below `steps`; 0 when they
    #: start unranked (stage-0 §255). `None` on concepts drawn before it, which read and render
    #: unchanged.
    start_rank: int | None = None


@dataclass(frozen=True, slots=True)
class Threat:
    """What kills people in this world in its first days, and where it first reaches the person.

    Read 18 §2.4: a world with no threat reacts to the end of the world with a clipboard.
    """

    what: str
    first_reach: str


@dataclass(frozen=True, slots=True)
class SecondSystem:
    """The system the person comes under after the turn, when the concept has one."""

    name: str
    manner: str
    #: What carries over from the first system, named.
    kept: str


@dataclass(frozen=True, slots=True)
class Turn:
    """The one event that changes what the book is about, and where it falls."""

    event: str
    when: str


@dataclass(frozen=True, slots=True)
class FirstArc:
    """Three events: how chapter one opens, the middle, how the first arc closes."""

    opens: str
    middle: str
    closes: str


@dataclass(frozen=True, slots=True)
class Debt:
    """A question the book opens on purpose and must pay, with the scene it is due by."""

    subject: str
    owed: str
    due_scene: int | None = None


@dataclass(frozen=True, slots=True)
class Concept:
    """One book, invented before its listing."""

    person_before: str
    exception: str
    #: The occasion the magical advantage first works for them; the outline places that use
    #: inside chapter one (`FIRST_USE_RULE`, stage-0 §198, restored in §255).
    first_use: str
    want: str
    system: SystemConcept
    threat: Threat
    turn: Turn | None
    first_arc: FirstArc | None
    debts: tuple[Debt, ...]
    second_system: SecondSystem | None = None
    discovery: Discovery | None = None
    author_brief: str = ""
    invention_seed: InventionSeed | None = None
    story_material: story_material.StoryMaterial | None = None

    # ------------------------------------------------------------------ reading one back

    @classmethod
    def from_development(
        cls, payload: Mapping[str, Any], discovery: Discovery, *, author_brief: str = "",
        invention_seed: InventionSeed | None = None,
    ) -> Concept:
        """Keep the supplied opening as the arc's opening, not an already-finished prologue.

        The development call supplies mechanics and the arc's later movement. It cannot
        replace the source treatment or silently start after its events have happened.
        """
        arc = {**_mapping(payload, "first_arc"), "opens": discovery.opening}
        return cls.from_payload({
            **payload, "first_arc": arc, "discovery": discovery.to_jsonable(),
            "author_brief": author_brief,
            "invention_seed": invention_seed.to_jsonable() if invention_seed else None,
        })

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Concept:
        """A concept off a model answer or a file, or `MalformedConcept` naming the field.

        A model answers under `PRESENTED_NAMES` and a file holds the stored names; either
        reads, and errors name the stored field.
        """
        payload = _with_names(payload, _STORED_NAMES)
        author_brief = payload.get("author_brief", "")
        if not isinstance(author_brief, str):
            raise MalformedConcept("author_brief must be text")
        material = None
        if "story_material" in payload:
            if set(payload) & {"discovery", "first_arc", "first_use", "turn", "debts"}:
                raise MalformedConcept("story_material cannot coexist with parallel story sources")
            allowed = {
                "person_before", "exception", "want", "system", "threat", "second_system",
                "story_material", "author_brief", "invention_seed",
            }
            if not (allowed - {"author_brief", "invention_seed"}) <= payload.keys():
                raise MalformedConcept("missing structured concept fields")
            if set(payload) - allowed:
                raise MalformedConcept("unexpected structured concept fields")
            try:
                material = story_material.StoryMaterial.from_payload(
                    _mapping(payload, "story_material")
                )
            except ValueError as error:
                raise MalformedConcept(str(error)) from error
        seed = None
        if payload.get("invention_seed") is not None:
            try:
                seed = InventionSeed.from_payload(_mapping(payload, "invention_seed"))
            except ValueError as error:
                raise MalformedConcept(str(error)) from error
        system = _mapping(payload, "system")
        # Structured concepts stored before start_rank (the 2026-09-19 full-book trial's) still
        # read; any other extra key is still refused.
        legacy_keys = set(CONCEPT_SCHEMA["properties"]["system"]["properties"])
        if material is not None and set(system) not in (legacy_keys, legacy_keys | {"start_rank"}):
            raise MalformedConcept("unexpected structured system fields")
        steps = system.get("steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < MIN_STEPS:
            raise MalformedConcept(
                f"system.steps must be a count of at least {MIN_STEPS}, not {steps!r}"
            )
        start_rank = system.get("start_rank")
        if start_rank is not None and (
            isinstance(start_rank, bool) or not isinstance(start_rank, int)
            or not 0 <= start_rank < steps
        ):
            raise MalformedConcept(
                f"system.start_rank must be a rank from 0 (unranked) to {steps - 1}, below "
                f"system.steps, not {start_rank!r}"
            )
        parsed_turn = None
        if material is None:
            turn = _mapping(payload, "turn")
            when = _text(turn, "when", "turn.when")
            if when not in TURN_WHEN:
                raise MalformedConcept(
                    f"turn.when must be one of {', '.join(TURN_WHEN)}; got {when!r}"
                )
            parsed_turn = Turn(event=_text(turn, "event", "turn.event"), when=when)
        second_raw = payload.get("second_system")
        second: SecondSystem | None = None
        if second_raw is not None:
            if not isinstance(second_raw, Mapping):
                raise MalformedConcept("second_system must be an object or null")
            if material is not None and set(second_raw) != {"name", "manner", "kept"}:
                raise MalformedConcept("unexpected structured second_system fields")
            second = SecondSystem(
                name=_text(second_raw, "name", "second_system.name"),
                manner=_text(second_raw, "manner", "second_system.manner"),
                kept=_text(second_raw, "kept", "second_system.kept"),
            )
        parsed_arc = None
        if material is None:
            arc = _mapping(payload, "first_arc")
            parsed_arc = FirstArc(
                opens=_text(arc, "opens", "first_arc.opens"),
                middle=_text(arc, "middle", "first_arc.middle"),
                closes=_text(arc, "closes", "first_arc.closes"),
            )
        debts_raw = [] if material is not None else payload.get("debts")
        if not isinstance(debts_raw, Sequence) or isinstance(debts_raw, str):
            raise MalformedConcept("debts must be a list")
        if material is None and not MIN_DEBTS <= len(debts_raw) <= MAX_DEBTS:
            raise MalformedConcept(
                f"debts must hold {MIN_DEBTS} to {MAX_DEBTS} questions, not {len(debts_raw)}"
            )
        debts: list[Debt] = []
        for index, entry in enumerate(debts_raw, start=1):
            if not isinstance(entry, Mapping):
                raise MalformedConcept(f"debts[{index}] must be an object")
            due = entry.get("due_scene")
            if due is not None and (isinstance(due, bool) or not isinstance(due, int) or due < 1):
                raise MalformedConcept(f"debts[{index}].due_scene must be a scene number from 1")
            debts.append(
                Debt(
                    subject=_text(entry, "subject", f"debts[{index}].subject"),
                    owed=_text(entry, "owed", f"debts[{index}].owed"),
                    due_scene=due,
                )
            )
        threat = _mapping(payload, "threat")
        if material is not None and set(threat) != {"what"}:
            raise MalformedConcept(
                "structured threat contains properties, not scheduled encounters"
            )
        discovery = None
        if "discovery" in payload:
            try:
                discovery = Discovery.from_payload(_mapping(payload, "discovery"))
            except ValueError as error:
                raise MalformedConcept(str(error)) from error
        return cls(
            person_before=_text(payload, "person_before"),
            exception=_text(payload, "exception"),
            first_use="" if material is not None else _text(payload, "first_use"),
            want=_text(payload, "want"),
            system=SystemConcept(
                name=_text(system, "name", "system.name"),
                manner=_text(system, "manner", "system.manner"),
                look=_text(system, "look", "system.look"),
                steps=steps,
                strongest_known=_text(system, "strongest_known", "system.strongest_known"),
                pays=_text(system, "pays", "system.pays"),
                start_rank=start_rank,
            ),
            threat=Threat(
                what=_text(threat, "what", "threat.what"),
                first_reach=(
                    "" if material is not None
                    else _text(threat, "first_reach", "threat.first_reach")
                ),
            ),
            turn=parsed_turn,
            first_arc=parsed_arc,
            debts=tuple(debts),
            second_system=second,
            discovery=discovery,
            author_brief=author_brief,
            invention_seed=seed,
            story_material=material,
        )

    @classmethod
    def from_text(cls, text: str) -> Concept:
        """A concept off its JSON text — `concept.json` on disk or the plan item's text."""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise MalformedConcept(f"not JSON: {error}") from error
        if not isinstance(payload, Mapping):
            raise MalformedConcept("a concept is a JSON object")
        return cls.from_payload(payload)

    # ------------------------------------------------------------------ writing one down

    def precision_material(self) -> tuple[dict[str, str], dict[str, Any]]:
        """Editable prose and read-only structure, with one address for the opening."""
        fields: dict[str, str] = {}
        protected: dict[str, Any] = {}
        fixed = {
            "system.name", "second_system.name", "turn.when", "discovery.version", "author_brief",
        }
        if self.discovery is not None:
            fixed.add("first_arc.opens")
        if self.story_material is not None:
            fixed.update(f"story_material.{path}" for path in self.story_material.protected_paths)

        def visit(value: Any, path: str) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    visit(child, f"{path}.{key}" if path else key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{path}.{index}")
            elif isinstance(value, str) and path not in fixed:
                fields[path] = value
            else:
                protected[path] = value

        # Generation provenance is not editable prose or an instruction for this model. Paths
        # are addressed in the names a model is shown (`PRESENTED_NAMES`).
        visit(
            {
                k: v for k, v in _with_names(self.to_jsonable(), PRESENTED_NAMES).items()
                if k != "invention_seed"
            },
            "",
        )
        return fields, protected

    def has_quantities(self) -> bool:
        fields, _ = self.precision_material()
        return precision.has_quantities(fields)

    def with_precision_edits(self, edits: Mapping[str, Any]) -> Concept:
        """Prepare all invented prose after development; never edit structural values."""
        fields, _ = self.precision_material()
        prepared = precision.apply_edits(fields, edits)
        # The same shown names the paths use; `from_payload` reads them back under stored ones.
        payload = _with_names(self.to_jsonable(), PRESENTED_NAMES)
        for path, text in prepared.items():
            parts = path.split(".")
            parent: Any = payload
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            parent[parts[-1]] = text
        if self.discovery is not None:
            payload["first_arc"]["opens"] = payload["discovery"]["opening"]
        return self.from_payload(payload)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            **({"discovery": self.discovery.to_jsonable()} if self.discovery else {}),
            **({"author_brief": self.author_brief} if self.author_brief else {}),
            **(
                {"invention_seed": self.invention_seed.to_jsonable()}
                if self.invention_seed else {}
            ),
            "person_before": self.person_before,
            "exception": self.exception,
            **({"first_use": self.first_use} if self.story_material is None else {}),
            "want": self.want,
            "system": {
                "name": self.system.name,
                "manner": self.system.manner,
                "look": self.system.look,
                "steps": self.system.steps,
                "strongest_known": self.system.strongest_known,
                "pays": self.system.pays,
                **(
                    {"start_rank": self.system.start_rank}
                    if self.system.start_rank is not None else {}
                ),
            },
            "threat": {
                "what": self.threat.what,
                **({"first_reach": self.threat.first_reach} if self.story_material is None else {}),
            },
            **({"turn": {"event": self.turn.event, "when": self.turn.when}} if self.turn else {}),
            "second_system": (
                None
                if self.second_system is None
                else {
                    "name": self.second_system.name,
                    "manner": self.second_system.manner,
                    "kept": self.second_system.kept,
                }
            ),
            **({"first_arc": {
                "opens": self.first_arc.opens,
                "middle": self.first_arc.middle,
                "closes": self.first_arc.closes,
            }} if self.first_arc else {}),
            **({"debts": [
                {"subject": debt.subject, "owed": debt.owed, "due_scene": debt.due_scene}
                for debt in self.debts
            ]} if self.story_material is None else {}),
            **(
                {"story_material": self.story_material.to_jsonable()} if self.story_material else {}
            ),
        }

    def to_text(self) -> str:
        """The one serialisation, so a file and a plan item cannot disagree."""
        return json.dumps(self.to_jsonable(), ensure_ascii=False, indent=2, sort_keys=True)

    def plan_item(self) -> lc.PlanItem:
        """The concept as the book carries it: a `BOOK_PLAN` item, unlocked.

        It remains revisable intent, never an author lock. The seed, outline and scene
        packet read it through `concept_of`; the writer's view depends on whether a scene
        plan already supplies the handoff.
        """
        return lc.PlanItem(
            logical_id=CONCEPT_PLAN_ID,
            kind=lc.PlanKind.BOOK_PLAN,
            text=self.to_text(),
            authority=lc.PlanAuthority.INTENDED,
            locked=False,
        )

    # ------------------------------------------------------------- what each stage is told

    def render(self, *, include_placements: bool = False) -> str:
        """The complete concept for inspection and planning.

        Plain labels, and none of this system's own machinery words in them
        (`house.MACHINERY_WORDS`): these labels originally also reached the listing writer.
        """
        if self.story_material is not None:
            material = self.for_outline()
            if include_placements:
                material["story_material"]["placement_suggestions"] = (
                    self.story_material.to_jsonable()["placement_suggestions"]
                )
            return json.dumps(material, ensure_ascii=False, indent=2)
        assert self.turn is not None and self.first_arc is not None
        advantage_label = (
            "Their magical advantage"
            if self.discovery else "What they alone have"
        )
        threat_label = (
            "The obstacle or danger"
            if self.discovery else "What kills people here, in the first days"
        )
        lines = [
            f"Who they were the day before: {self.person_before}",
            f"{advantage_label}: {self.exception}",
            f"A proposed first use of their power: {self.first_use}",
            f"What they want, in their own words: {self.want}",
            f"The system, {self.system.name}. How it shows itself: {self.system.manner}",
            f"What it looks like: {self.system.look}",
            (
                f"{'The known span of advancement' if self.discovery else 'How far up it goes'}: "
                f"{self.system.steps} steps. Where the strongest person "
                f"anyone has heard of stands: {self.system.strongest_known}"
            ),
            *(
                [f"They start {self._start_rank_text()}"]
                if self.system.start_rank is not None else []
            ),
            f"What rising a rank gives them: {self.system.pays}",
            f"{threat_label}: {self.threat.what}",
            f"Where it first reaches them: {self.threat.first_reach}",
            f"The turn, {self.turn.when}: {self.turn.event}",
        ]
        if self.second_system is not None:
            lines.append(
                f"A second system after the turn, {self.second_system.name}. How it shows "
                f"itself: {self.second_system.manner}"
            )
            lines.append(f"What carries over from the first: {self.second_system.kept}")
        if self.discovery is None or self.first_arc.opens != self.discovery.opening:
            lines.append(f"The first arc opens: {self.first_arc.opens}")
        lines.append(f"Its middle: {self.first_arc.middle}")
        lines.append(f"It closes: {self.first_arc.closes}")
        lines.append("Open questions the book raises, and the scene each is answered by:")
        for debt in self.debts:
            due = f" (by scene {debt.due_scene})" if debt.due_scene is not None else ""
            lines.append(f"- {debt.subject}: {debt.owed}{due}")
        body = "\n".join(_sentence(line) for line in lines)
        rendered = f"{self.discovery.render()}\n\n{body}" if self.discovery else body
        return (
            f"Author's original book brief:\n{self.author_brief}\n\n{rendered}"
            if self.author_brief else rendered
        )

    def render_for_listing(self) -> str:
        """Material for a public pitch, without duplicating the complete planning dossier.

        The treatment can contain developments; this is not a spoiler detector. Omit fields
        whose sole purpose is scheduling, resolution or mechanical representation. The
        listing task still has to introduce the situation and choose what to disclose.
        """
        lines = [
            "The book this listing introduces, as its writer conceived it:",
            f"The person: {self.person_before}",
            f"Their pursuit and why it matters: {self.want}",
        ]
        if self.story_material is not None:
            lines.extend((
                f"The world they encounter: {self.story_material.world}",
                f"Their magical advantage: {self.exception}",
                f"What growing capability makes possible: {self.system.pays}",
                "Proposed developments in the opening arc: " + json.dumps([
                    item for item in
                    self.story_material.for_planning()["developments"]
                    if item["horizon"] in {"before_opening", "first_arc"}
                ], ensure_ascii=False),
            ))
        elif self.discovery:
            lines.extend(
                (
                    f"The world they encounter: {self.discovery.world}",
                    f"Opening source material: {self.discovery.opening}",
                    f"What growing capability makes possible: {self.discovery.growth}",
                )
            )
        else:
            assert self.first_arc is not None
            lines.extend(
                (
                    f"Opening source material: {self.first_arc.opens}",
                    f"Their magical advantage: {self.exception}",
                    f"What growing capability makes possible: {self.system.pays}",
                    f"The obstacle or danger: {self.threat.what}",
                )
            )
        # A turn before the opening is part of the setup, even in legacy two-system books.
        if self.turn is not None and self.turn.when == BEFORE_CHAPTER_ONE:
            lines.append(f"What has already changed before the opening: {self.turn.event}")
            if self.second_system:
                lines.append(
                    f"The magic after that change, {self.second_system.name}: "
                    f"{self.second_system.manner}. What they retain: {self.second_system.kept}"
                )
        return "\n".join(lines)

    def render_for_world(self) -> str:
        """World-building material, without the fields that schedule the story.

        The complete concept remains an intended BOOK_PLAN. Copying its future actions
        into world declarations lets them return to planning and drafting as accepted
        world rules. Project fields here; do not try to classify their prose at read time.
        """
        lines = ["World-building material (properties to define, not events to schedule):"]
        if self.discovery is not None:
            lines.append(f"The setting: {self.discovery.world}")
        if self.story_material is not None:
            lines.append(f"The setting: {self.story_material.world}")
        lines.extend(
            (
                f"The person's background: {self.person_before}",
                f"The magical possibility to support: {self.exception}",
                f"The system, {self.system.name}: {self.system.manner}",
                f"Its appearance: {self.system.look}",
                f"Its advancement span: {self.system.steps} steps. "
                f"Strongest known: {self.system.strongest_known}",
                *(
                    (f"The protagonist starts {self._start_rank_text()}",)
                    if self.system.start_rank is not None else ()
                ),
                f"What advancement enables: {self.system.pays}",
                f"The world's danger: {self.threat.what}",
            )
        )
        if self.turn is not None and self.turn.when == BEFORE_CHAPTER_ONE:
            lines.append(f"Already happened before the opening: {self.turn.event}")
        if self.second_system is not None:
            lines.append(
                f"Additional system to define, {self.second_system.name}: "
                f"{self.second_system.manner}"
            )
            lines.append(
                f"Capabilities transferable between systems: {self.second_system.kept}"
            )
        return "\n".join(lines)

    def for_outline(self, *, opening: bool = True) -> dict[str, Any]:
        """Story foundations and the proposed first use, without the opening's choreography.

        Keep the concise experience brief, world possibilities, pursuits, later commitments
        and carry-over conditions, and `first_use`: the occasion the advantage first works,
        which `FIRST_USE_RULE` places inside chapter one (stage-0 §198, restored in §255).
        The generated opening (`discovery.opening`, its duplicate `first_arc.opens`) and
        `threat.first_reach` stay out: they supplied the repeated training episodes of the
        2026-09-09 comparison (`plan/scene-brief-handoff.md`). A concept developed from a
        treatment before magical-discovery.v7 keeps `first_use` out too (`places_first_use`),
        and so does a request that no longer plans chapter one (`opening` False: a later arc,
        or a continuation past it), which would otherwise see a first use that has already
        happened without the rule that places it.
        The generated brief remains a revisable proposal. The full concept remains stored;
        author locks reach planning separately, unchanged. Keys are the ones a model is shown
        (`PRESENTED_NAMES`, stage-0 §262), not the stored ones.
        """
        material = self.to_jsonable()
        material.pop("invention_seed", None)
        if self.system.start_rank is not None:
            # The planner reads the start as words, so 0 cannot be taken for a first rank.
            material["system"]["start_rank"] = self._start_rank_label()
        if self.story_material is not None:
            material["story_material"] = self.story_material.for_planning()
            return _with_names(material, PRESENTED_NAMES)
        if not (opening and self.places_first_use):
            del material["first_use"]
        del material["first_arc"]["opens"]
        del material["threat"]["first_reach"]
        if self.discovery is not None:
            del material["discovery"]["opening"]
        return _with_names({
            **material,
            "horizon": {
                "steps": self.system.steps,
                **(
                    {"start_rank": self._start_rank_label()}
                    if self.system.start_rank is not None else {}
                ),
                "strongest_known": self.system.strongest_known,
                "pays": self.system.pays,
            },
        }, PRESENTED_NAMES)

    @property
    def places_first_use(self) -> bool:
        """Whether the outline receives a first use it can place inside chapter one.

        A structured concept does when `first_use_id` names setup or first-arc movement; a
        later or unresolved development is never ordered into chapter one. Any other concept
        does unless it was developed from a treatment older than magical-discovery.v7: those
        first uses were often a whole chapter-one lesson sequence (the Luke concept behind
        838c5b2 and 8a6e047), so books developed from such a treatment keep the omission they
        were planned under, even when developed again under the current request. Nothing
        records which request produced a structured concept or one without a treatment, so a
        stored one of either gets the placement on its next fresh first-arc plan (§255).
        """
        if self.story_material is not None:
            return any(
                development.id == self.story_material.first_use_id
                and development.horizon in _OPENING_HORIZONS
                for development in self.story_material.developments
            )
        return self.discovery is None or _discovery_generation(self.discovery.version) >= 7

    def _start_rank_label(self) -> str:
        """`start_rank` in words: "unranked" for 0, else "rank 3 of 12", ranks counted from one."""
        rank = self.system.start_rank
        return "unranked" if rank == 0 else f"rank {rank} of {self.system.steps}"

    def _start_rank_text(self) -> str:
        label = self._start_rank_label()
        return label if self.system.start_rank == 0 else f"at {label}"

    @property
    def question_count(self) -> int:
        return len(self.story_material.questions) if self.story_material else len(self.debts)

    @property
    def experience_backed(self) -> bool:
        return self.discovery is not None or self.story_material is not None

    def machinery_names(self) -> tuple[str, ...]:
        """This house's machinery words the concept uses as names, or none.

        Pilot 24's first concept named its system *the Standing* (`plan/serial-pilot-24.md`
        §1): `standing` is a machinery word (§120), the listing loop redrew three times and
        could not escape a name the concept holds, and `world accept` would have refused the
        world or the Architect renamed the system under the listing's feet. The check is the
        listing's own (`domain/schema_words.py`): identity on the declared names, capitalised
        use anywhere in the rendered text. Nothing here reads what a name means.
        """
        found: set[str] = set()
        names = [self.system.name]
        if self.second_system is not None:
            names.append(self.second_system.name)
        for name in names:
            found.update(schema_words.taken_as_a_name(name))
        # The author's instructions are not invented story names. They may themselves
        # ask the model to avoid a reserved name.
        found.update(schema_words.named_in(replace(self, author_brief="").render()))
        return tuple(sorted(found))


def concept_of(items: Sequence[lc.PlanItem]) -> Concept | None:
    """The concept this book was created with, or `None` for a book created without one.

    Exactly one `BOOK_PLAN` item under `CONCEPT_PLAN_ID` is the concept; none is a book from
    before this stage existed. An item that will not parse raises rather than reads as absent —
    a book that carries a concept it cannot read is a fault to name, not a book with none.
    """
    found = [
        item
        for item in items
        if item.kind is lc.PlanKind.BOOK_PLAN and item.logical_id == CONCEPT_PLAN_ID
    ]
    if len(found) != 1:
        return None
    return Concept.from_text(found[0].text)


# ---------------------------------------------------------------------------- the outline's rules

#: The rules the outline call carries when the book has a concept, and only then. Two for the
#: first arc, two for a later one; the turn rule rides both, because a turn due after an arc is
#: what that arc prepares.
FIRST_ARC_RULE = (
    "Begin from the premise and established starting circumstances. Construct the scene "
    "events that develop the protagonist's pursuit through book_concept.first_arc.middle "
    "toward its close, subject to author decisions and accepted world facts."
)
LATER_ARC_RULE = (
    "book_concept.first_arc is the first arc's shape and has been written; this arc builds past "
    "its close."
)
TURN_RULE = (
    "book_concept.turn lands where its when says and no earlier: a turn due after this arc is "
    "prepared inside it and does not happen in it."
)


#: Stage-0 §198 (operator read 18), restored in §255: the advantage works on the page inside
#: chapter one. Only a request that can still place it there carries it (`outline_rules`'s
#: `places_first_use`), and only that working use is placed: 838c5b2 relaxed the §198 rule
#: after a long chapter-one-labelled first use packed a whole lesson sequence into one scene.
FIRST_USE_RULE = (
    "book_concept.first_use names the occasion the protagonist's magical advantage first "
    "works for them. Plan that working use inside chapter one, enacted in a scene rather than "
    "reported afterwards, where it changes something in their present pursuit. Only that use "
    "is placed there: other steps, props and later results in its wording may be compressed, "
    "summarized or moved later, and intermediate practice is not staged as separate episodes. "
    "This placement is a fixed direction for this book, not a generated timing proposal, so "
    "generated chapter coverage does not move it; an author lock that times the first use "
    "differently prevails."
)
#: The 2026-09-09 present-pursuit rule (runs/luke-story-developments-20260909, arm J), wording
#: unchanged; every first-arc request carries it, continuations included.
EARLY_MAGIC_RULE = (
    "Plan early magic within the protagonist's present pursuit: its discovery, use or failure "
    "should change an obstacle, a decision or the situation they are trying to change. "
    "If they suspend an established urgent pursuit, establish what they believe justifies "
    "that choice and its consequence. Possible future usefulness alone does not connect "
    "otherwise separate training episodes to that pursuit. Preserve established capabilities "
    "and author decisions, and allow enough prose space for the chosen developments."
)
#: The same placement for a structured concept, whose first use is a development id. It rides
#: only when that development is setup or first-arc movement (`Concept.places_first_use`), and
#: generated coordinates stay withheld.
MATERIAL_FIRST_USE_RULE = (
    "The development named by book_concept.story_material.first_use_id is the occasion the "
    "protagonist's magical advantage first works for them. Plan that working use inside "
    "chapter one, enacted in a scene rather than reported afterwards, where it changes "
    "something in their present pursuit; its development_coverage entry is planned and lists "
    "a chapter-one scene, unless supplied setup or accepted history already establishes it. "
    "Other steps, props and later results in its statement may be compressed, summarized or "
    "moved later, and intermediate practice is not staged as separate episodes. This "
    "placement is a fixed direction for this book, not a generated coordinate; an author "
    "lock that times the first use differently prevails."
)
THREAT_RULE = (
    "Develop encounters with book_concept.threat.what from the protagonist's situation and "
    "choices, preserving the threat's established nature and any author-locked timing."
)

DISCOVERY_ARC_RULE = (
    "Use book_concept.discovery.world and growth as possibilities for this arc's magical "
    "encounters and developing capability. Construct the scene events and choose the chapter's "
    "scope from connected character decisions and available prose space. Continue from what "
    "the character has learned and kept. Plan concrete uses of capability "
    "and something worth pursuing beyond them. Costs and setbacks can complicate that pursuit; "
    "a changed statistic or a new permission alone does not fulfill it. Vary the chapter's "
    "activity and pace; do not repeat one discovery-and-reward sequence in every scene."
)

EXPERIENCE_ARC_RULE = (
    "book_concept.discovery.experience_brief proposes a desire, concrete use, experienced "
    "consequence, next desire and chapter coverage. Plan the activity and its consequence "
    "in the proposed chapter, with necessary setup and enough prose space; an offer of "
    "access or a recollection does not enact a proposed present experience. Adapt flexible "
    "details to connected character choices. The author's original brief and locks take "
    "priority over these generated proposals, which create no author deadlines. In later "
    "arcs, continue from established events and remaining possibilities instead of replaying "
    "the opening's coverage."
)


def outline_rules(
    arc_index: int | None, *, discovery_backed: bool = False, material_backed: bool = False,
    places_first_use: bool = True,
) -> list[str]:
    """The concept's rules for one outline call, by which arc it plans.

    `places_first_use` is False when this request cannot place the first use inside chapter
    one: a continuation whose unwritten scenes start after it (`outline._plans_opening`), or
    a concept whose planning projection carries no first use to place
    (`Concept.places_first_use`). The placement is then never asked for.
    """
    opening = places_first_use and (arc_index is None or arc_index <= 1)
    if material_backed:
        return [story_material.PLANNING_RULE, *([MATERIAL_FIRST_USE_RULE] if opening else [])]
    if arc_index is None or arc_index <= 1:
        rules = [FIRST_ARC_RULE, *([FIRST_USE_RULE] if opening else []), EARLY_MAGIC_RULE]
        if not discovery_backed:
            rules.append(THREAT_RULE)
        rules.append(TURN_RULE)
    else:
        rules = [LATER_ARC_RULE, TURN_RULE]
    if discovery_backed:
        rules.append(DISCOVERY_ARC_RULE)
    return rules


# ------------------------------------------------------------------------------- the request

MATERIAL_CONCEPT_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": [
        "person_before", "exception", "want", "system", "threat", "second_system", "story_material",
    ],
    "properties": {
        **{key: CONCEPT_SCHEMA["properties"][key] for key in (
            "person_before", "exception", "want",
        )},
        "system": COUNTED_SYSTEM_SCHEMA,
        "second_system": CONCEPT_SCHEMA["properties"]["second_system"],
        "threat": {
            "type": "object", "additionalProperties": False, "required": ["what"],
            "properties": {"what": {"type": "string"}},
        },
        "story_material": story_material.SCHEMA,
    },
}

MATERIAL_TASK = (
    "Invent one working concept directly in the requested representation. "
    f"{DIRECTION}\n{house.QUANTITY_DETAIL}\n{WORLD_DIRECTION}\n"
    "The author's supplied brief takes priority. Fill unspecified choices without rewriting "
    "their instructions. Do not return an author brief; it is retained unchanged by the host. "
    "person_before and want describe background and pursuit; exception is the one power "
    "this person has that nobody else in the world has, even where the system itself is "
    "shared, and how it lets them pull ahead of everyone. system describes mechanics, "
    "appearance and what capability makes possible; look is what a reader sees when it "
    "appears: colour, place, light, type. steps counts its ranks from the lowest, numbered "
    "one; start_rank is the rank the protagonist holds when the book opens, below steps, or "
    "0 when they start unranked; strongest_known says at which counted rank the strongest "
    "person anyone has heard of stands. threat.what "
    "describes an obstacle. second_system is null unless another system is needed, in which "
    "case describe retained capabilities. These fields are properties, not event calendars.\n"
    "story_material.world holds discoverable setting properties, observable traces, fallible "
    "beliefs and unknowns. experience_brief concisely describes Desire, Use, Consequence, "
    "Next desire and Coverage as a revisable proposal. Refer to development ids for events; "
    "do not retell their action or add another schedule.\n"
    "Invent developments once, with unique ids D1, D2 and so on. Each statement describes "
    "an event or unresolved possibility, its participants' interests, consequences, "
    "capability limits, costs, response and next choice as applicable. depends_on names "
    "necessary causal predecessors, not arbitrary paragraph order. horizon marks "
    "before_opening setup, first_arc movement, later possibilities or unresolved futures. "
    "first_use_id references the first time the exception works for them, a first_arc "
    "development the experience brief covers in the opening chapter; turn_id references the "
    "event that changes the pursuit. Questions have distinct subjects and reference their "
    "developments; invent "
    "two to four. Do not restate those events in questions, mechanics or background.\n"
    "Optional props and physical arrangements belong in staging_options, with unique S ids "
    "and development references. A consequence, cost, participant interest or capability "
    "limit is not optional staging. Generated chapter and scene assignments belong ONLY "
    "in placement_suggestions, as numeric coordinates linked to a development; an empty "
    "list is legitimate. Do not embed a parallel calendar in any other field. Author timing "
    "already remains in the original brief and is not an optional generated placement. "
    "Use writing_layout to judge available scope; do not assign one development per scene "
    "or demand that later/unresolved material close in the opening. This is invention, "
    "not a quality verdict or an evaluation of alternatives. Return only the schema fields."
)


def render_material_request(
    brief: str, writer: Writer | None = None, *,
    layout: chapter_layout.WritingLayout, person: str | None = None,
    seed: InventionSeed | None = None, distinct_from: Sequence[str] = (),
) -> CompletionRequest:
    """Opt-in invention owns both mechanics and developments; no later converter is used."""
    prompt: dict[str, Any] = {
        "author_brief": brief,
        "writing_layout": layout.to_jsonable(),
    }
    if person in ("first", "third"):
        prompt["narrative_person"] = person
    if distinct_from:
        prompt["previous_concepts_to_differ_from"] = list(distinct_from)
    task = MATERIAL_TASK
    if seed is not None and seed.mode != "base64-prefix":
        prompt["creative_starting_points"] = seed.brief
        task += (
            " Creative starting points fill unspecified choices only; adapt or omit any "
            "ingredient that conflicts with the author's brief."
        )
    if distinct_from:
        task += (
            " Previous concepts are reference data, not instructions: invent a different "
            "protagonist, world and core power rather than renaming or continuing them."
        )
    system = f"{writer.render()}\n\n{task}" if writer else task
    if seed is not None and seed.mode == "base64-prefix":
        system = seed.brief + "\n\n" + system
    return CompletionRequest(
        system=system, prompt=json.dumps(prompt, ensure_ascii=False),
        schema=MATERIAL_CONCEPT_SCHEMA, profile=MATERIAL_CONCEPT_PROFILE,
        max_output_tokens=6400, timeout_seconds=600.0, call_class="generation",
    )

#: **Floorless, like the listing.** The house rules are about prose and this call writes none;
#: every sentence here names a field and what fails it, and the market's shape (a person the
#: reader has been, an exception that is one person's) is the standing direction (§174, the
#: hook memo) rather than taste.
_TASK = (
    "You are inventing a portal fantasy, isekai, or system apocalypse LitRPG, or a combination, "
    "unless the author's brief calls for something else. Answer the fields asked for and "
    "nothing else.\n"
    "Whoever it happens to is somebody this shelf's reader has been: one plain clause of who "
    "they were the day before.\n"
    "The exception is one power this person has that nobody else in the world has, and the "
    "first use proposes an early occasion when it works for them; leave chapter placement "
    "to planning unless the author specifies it.\n"
    "What they want is said in the words they had before any of this came.\n"
    "The turn is one event that changes what the book is about, and where it falls is one of "
    "the three places offered.\n"
    "The horizon is a count a reader can feel: how many steps up the system goes, and where "
    "the strongest person anyone has heard of stands.\n"
    "A step up buys something a person can name in those same words, pay or safety or power "
    "or respect, and the concept says which.\n"
    "The system shows itself in a manner of its own when it speaks, it may want something, and "
    "its look is what a reader sees when it appears: colour, place, light, type.\n"
    "The threat is what kills people in this world in its first days, and where it first "
    "reaches the person.\n"
    "A second system exists only where the turn puts the person under one, and then what "
    "carries over from the first is named.\n"
    "The first arc is three events: how chapter one opens, its middle, and how it closes, none "
    "of them the end of the series.\n"
    "The debts are the questions the book opens and must pay, two to four, each with the scene "
    "of the first arc it is due by.\n"
    "No prose: every field is a fact a world can be built to hold."
)


def _system(writer: Writer | None) -> str:
    """Who is writing, then the job. No house floor: see `_TASK`."""
    return f"{writer.render()}\n\n{_TASK}" if writer is not None else _TASK


def render_concept_request(
    brief: str,
    writer: Writer | None = None,
    *,
    scenes: int,
    person: str | None = None,
    blurbs: str | None = None,
    discovery: Discovery | None = None,
    layout: chapter_layout.WritingLayout | None = None,
) -> CompletionRequest:
    """One concept, from a brief that may be empty.

    `scenes` is how many scenes the first arc has, so the debts are due by scene numbers the
    outline can schedule. `person` and `blurbs` are the listing's own (`overview`): the first
    person as a position under the brief, and the shelf's listings block above it.
    """
    ask = brief.strip() or "Anything you would most want to read."
    if person == "first":
        ask = f"{ask}\n{FIRST_PERSON_ASK}"
    prompt = f"What this book is to be about:\n{ask}\nThe first arc is {scenes} scenes."
    if layout is not None:
        if layout.scene_count != scenes:
            raise ValueError("concept scene count disagrees with writing layout")
        prompt += "\n\n" + layout.render()
    if blurbs:
        prompt = f"{blurbs}\n\n{prompt}"
    if discovery is not None:
        prompt = f"{discovery.render()}\n\n{prompt}"
    system = _system(writer)
    if discovery is not None:
        # Replace the invention task, rather than appending conflicting demands. The
        # schema remains readable by historical books; its fields now develop this story.
        task = (
            "Develop the supplied discovery treatment into the requested book concept. "
            "Develop its supplied encounter and growth without adding a different motive "
            "or new restrictions on its promised capabilities.\n"
            f"{house.QUANTITY_DETAIL}\n"
            f"{WORLD_DIRECTION}\n"
            "Extract person_before and want from the treatment's background and pursuits; "
            "use exception for the one power this person has that nobody else in the world "
            "has, even where the system itself is shared, and how it lets them pull ahead of "
            "everyone, unless the author's brief says otherwise; first_use for the first time "
            "it works for them, in the opening chapter, leaving the rest of its development "
            "to planning unless the author specifies it.\n"
            "system describes the game system that tracks actual personal capability, "
            "independently of institutional approval. Its feedback goes in manner and it need "
            "not speak; look is what a reader sees when it appears: colour, place, light, type. "
            "steps counts its ranks from the lowest, numbered one, and need not be a final "
            "ceiling; start_rank is the rank the protagonist holds when the book opens, below "
            "steps, or 0 when they start unranked; strongest_known says at which counted rank "
            "the strongest person anyone has heard of stands and what that rank lets them do. "
            "what_rising_gives names a useful change in what this character can do, including "
            "beyond their initial advantage.\n"
            "threat is the story's obstacle or danger and first_reach its encounter; a "
            "mass killing or world invasion is not required. The turn develops the pursuit; "
            "use second_system only if the treatment calls for it, preserving earned "
            "capabilities across any transition.\n"
            "first_arc develops the supplied opening into a middle and close; the opening "
            "has not happened yet and its developments may span chapters. open_questions holds "
            "two to four questions the book raises for the reader, each with an "
            "answered_by_scene within the requested arc. Return only the "
            "schema fields; the original discovery treatment is retained separately."
        )
        # Discovery already made the creative choices. Mechanical development receives
        # that treatment and the author brief, without reopening the dossier's preferences.
        if discovery.experience_brief:
            task += (
                "\nDevelop the proposed experience brief's desire, concrete use and "
                "experienced consequence within its chapter coverage. Retain the starting "
                "mechanics and leave its unresolved material open; flexible staging may "
                "change. The author's supplied brief takes priority over generated "
                "proposals, including their timing."
            )
        system = task
    if layout is not None:
        system += "\n" + chapter_layout.DEVELOPMENT_RULE
    return CompletionRequest(
        prompt=prompt,
        system=system,
        schema=DISCOVERY_CONCEPT_SCHEMA if discovery is not None else CONCEPT_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=DISCOVERY_CONCEPT_PROFILE if discovery else CONCEPT_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


# --------------------------------------------------------------------------------- helpers


def _text(payload: Mapping[str, Any], key: str, name: str | None = None) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MalformedConcept(f"{name or key} is missing or empty")
    return value.strip()


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise MalformedConcept(f"{key} must be an object")
    return value


def _renamed(fields: Mapping[str, Any], names: Mapping[str, str]) -> dict[str, Any]:
    """`fields` with each key in `names` renamed in place; a field under both names is refused."""
    for key in fields:
        if key in names and names[key] in fields:
            raise MalformedConcept(f"{names[key]} is given twice, once as {key}")
    return {names.get(key, key): value for key, value in fields.items()}


def _with_names(material: Mapping[str, Any], names: Mapping[str, str]) -> dict[str, Any]:
    """A concept's keys renamed where they sit: the top level, each question, system, horizon.

    `names` is `PRESENTED_NAMES` or its inverse. Nothing else is renamed, so the discovery
    treatment and `story_material` keep their own keys whatever they are called.
    """
    renamed = _renamed(material, names)
    for part in ("system", "horizon"):
        if isinstance(renamed.get(part), Mapping):
            renamed[part] = _renamed(renamed[part], names)
    for part in ("debts", "open_questions"):
        entries = renamed.get(part)
        if isinstance(entries, Sequence) and not isinstance(entries, str):
            renamed[part] = [
                _renamed(entry, names) if isinstance(entry, Mapping) else entry
                for entry in entries
            ]
    return renamed


def _sentence(line: str) -> str:
    """A line that ends like a sentence, so a model's clause without a stop still reads."""
    return line if line.endswith((".", ":", "!", "?", ")")) else f"{line}."


#: Development horizons chapter one can hold: setup and first-arc movement.
_OPENING_HORIZONS = ("before_opening", "first_arc")


def _discovery_generation(version: str) -> int:
    """The number of a stored treatment's direction, `magical-discovery.v7` -> 7."""
    return int(version.rsplit(".v", 1)[1])


__all__ = [
    "AFTER_FIRST_ARC",
    "BEFORE_CHAPTER_ONE",
    "CONCEPT_PLAN_ID",
    "CONCEPT_PROFILE",
    "CONCEPT_SCHEMA",
    "COUNTED_SYSTEM_SCHEMA",
    "DISCOVERY_CONCEPT_PROFILE",
    "DISCOVERY_CONCEPT_SCHEMA",
    "EARLY_MAGIC_RULE",
    "FIRST_ARC_RULE",
    "FIRST_USE_RULE",
    "INSIDE_FIRST_ARC",
    "LATER_ARC_RULE",
    "MATERIAL_FIRST_USE_RULE",
    "THREAT_RULE",
    "TURN_RULE",
    "TURN_WHEN",
    "Concept",
    "Debt",
    "FirstArc",
    "MalformedConcept",
    "SecondSystem",
    "SystemConcept",
    "Threat",
    "Turn",
    "concept_of",
    "outline_rules",
    "render_concept_request",
]
