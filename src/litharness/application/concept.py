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

from litharness.application import precision
from litharness.application.discovery import Discovery
from litharness.application.overview import FIRST_PERSON_ASK
from litharness.domain import house, schema_words
from litharness.domain.generation import CompletionRequest
from litharness.domain.invention import InventionSeed
from litharness.domain.writers import Writer

CONCEPT_PROFILE = "writer.concept.v1"
DISCOVERY_CONCEPT_PROFILE = "writer.concept.discovery.v5"

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
    #: A proposed early use of the magical advantage; the planner chooses its placement.
    first_use: str
    want: str
    system: SystemConcept
    threat: Threat
    turn: Turn
    first_arc: FirstArc
    debts: tuple[Debt, ...]
    second_system: SecondSystem | None = None
    discovery: Discovery | None = None
    author_brief: str = ""
    invention_seed: InventionSeed | None = None

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
        """A concept off a model answer or a file, or `MalformedConcept` naming the field."""
        author_brief = payload.get("author_brief", "")
        if not isinstance(author_brief, str):
            raise MalformedConcept("author_brief must be text")
        seed = None
        if payload.get("invention_seed") is not None:
            try:
                seed = InventionSeed.from_payload(_mapping(payload, "invention_seed"))
            except ValueError as error:
                raise MalformedConcept(str(error)) from error
        system = _mapping(payload, "system")
        steps = system.get("steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < MIN_STEPS:
            raise MalformedConcept(
                f"system.steps must be a count of at least {MIN_STEPS}, not {steps!r}"
            )
        turn = _mapping(payload, "turn")
        when = _text(turn, "when", "turn.when")
        if when not in TURN_WHEN:
            raise MalformedConcept(f"turn.when must be one of {', '.join(TURN_WHEN)}; got {when!r}")
        second_raw = payload.get("second_system")
        second: SecondSystem | None = None
        if second_raw is not None:
            if not isinstance(second_raw, Mapping):
                raise MalformedConcept("second_system must be an object or null")
            second = SecondSystem(
                name=_text(second_raw, "name", "second_system.name"),
                manner=_text(second_raw, "manner", "second_system.manner"),
                kept=_text(second_raw, "kept", "second_system.kept"),
            )
        arc = _mapping(payload, "first_arc")
        debts_raw = payload.get("debts")
        if not isinstance(debts_raw, Sequence) or isinstance(debts_raw, str):
            raise MalformedConcept("debts must be a list")
        if not MIN_DEBTS <= len(debts_raw) <= MAX_DEBTS:
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
        discovery = None
        if "discovery" in payload:
            try:
                discovery = Discovery.from_payload(_mapping(payload, "discovery"))
            except ValueError as error:
                raise MalformedConcept(str(error)) from error
        return cls(
            person_before=_text(payload, "person_before"),
            exception=_text(payload, "exception"),
            first_use=_text(payload, "first_use"),
            want=_text(payload, "want"),
            system=SystemConcept(
                name=_text(system, "name", "system.name"),
                manner=_text(system, "manner", "system.manner"),
                look=_text(system, "look", "system.look"),
                steps=steps,
                strongest_known=_text(system, "strongest_known", "system.strongest_known"),
                pays=_text(system, "pays", "system.pays"),
            ),
            threat=Threat(
                what=_text(threat, "what", "threat.what"),
                first_reach=_text(threat, "first_reach", "threat.first_reach"),
            ),
            turn=Turn(event=_text(turn, "event", "turn.event"), when=when),
            first_arc=FirstArc(
                opens=_text(arc, "opens", "first_arc.opens"),
                middle=_text(arc, "middle", "first_arc.middle"),
                closes=_text(arc, "closes", "first_arc.closes"),
            ),
            debts=tuple(debts),
            second_system=second,
            discovery=discovery,
            author_brief=author_brief,
            invention_seed=seed,
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

        # Generation provenance is not editable prose or an instruction for this model.
        visit({k: v for k, v in self.to_jsonable().items() if k != "invention_seed"}, "")
        return fields, protected

    def has_quantities(self) -> bool:
        fields, _ = self.precision_material()
        return precision.has_quantities(fields)

    def with_precision_edits(self, edits: Mapping[str, Any]) -> Concept:
        """Prepare all invented prose after development; never edit structural values."""
        fields, _ = self.precision_material()
        prepared = precision.apply_edits(fields, edits)
        payload = self.to_jsonable()
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
            "first_use": self.first_use,
            "want": self.want,
            "system": {
                "name": self.system.name,
                "manner": self.system.manner,
                "look": self.system.look,
                "steps": self.system.steps,
                "strongest_known": self.system.strongest_known,
                "pays": self.system.pays,
            },
            "threat": {"what": self.threat.what, "first_reach": self.threat.first_reach},
            "turn": {"event": self.turn.event, "when": self.turn.when},
            "second_system": (
                None
                if self.second_system is None
                else {
                    "name": self.second_system.name,
                    "manner": self.second_system.manner,
                    "kept": self.second_system.kept,
                }
            ),
            "first_arc": {
                "opens": self.first_arc.opens,
                "middle": self.first_arc.middle,
                "closes": self.first_arc.closes,
            },
            "debts": [
                {"subject": debt.subject, "owed": debt.owed, "due_scene": debt.due_scene}
                for debt in self.debts
            ],
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

    def render(self) -> str:
        """The complete concept for inspection and planning.

        Plain labels, and none of this system's own machinery words in them
        (`house.MACHINERY_WORDS`): these labels originally also reached the listing writer.
        """
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
            f"What a step up buys: {self.system.pays}",
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
        lines.append("What the book owes, and the scene each is due by:")
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
            "The book this listing sells, as its writer conceived it:",
            f"The person: {self.person_before}",
            f"Their pursuit and why it matters: {self.want}",
        ]
        if self.discovery:
            lines.extend(
                (
                    f"The world they encounter: {self.discovery.world}",
                    f"Opening source material: {self.discovery.opening}",
                    f"What growing capability makes possible: {self.discovery.growth}",
                )
            )
        else:
            lines.extend(
                (
                    f"Opening source material: {self.first_arc.opens}",
                    f"Their magical advantage: {self.exception}",
                    f"What growing capability makes possible: {self.system.pays}",
                    f"The obstacle or danger: {self.threat.what}",
                )
            )
        # A turn before the opening is part of the setup, even in legacy two-system books.
        if self.turn.when == BEFORE_CHAPTER_ONE:
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
        lines.extend(
            (
                f"The person's background: {self.person_before}",
                f"The magical possibility to support: {self.exception}",
                f"The system, {self.system.name}: {self.system.manner}",
                f"Its appearance: {self.system.look}",
                f"Its advancement span: {self.system.steps} steps. "
                f"Strongest known: {self.system.strongest_known}",
                f"What advancement enables: {self.system.pays}",
                f"The world's danger: {self.threat.what}",
            )
        )
        if self.turn.when == BEFORE_CHAPTER_ONE:
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

    def for_outline(self) -> dict[str, Any]:
        """Story foundations without the generated opening's scene choreography.

        Keep world possibilities, pursuits, later commitments and carry-over conditions.
        The full concept remains stored; author locks reach planning separately, unchanged.
        """
        material = self.to_jsonable()
        material.pop("invention_seed", None)
        del material["first_use"]
        del material["first_arc"]["opens"]
        del material["threat"]["first_reach"]
        if self.discovery is not None:
            del material["discovery"]["opening"]
        return {
            **material,
            "horizon": {
                "steps": self.system.steps,
                "strongest_known": self.system.strongest_known,
                "pays": self.system.pays,
            },
        }

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
    "prepared inside it and not paid."
)


#: Early magic should matter, while a generated opportunity leaves room for planning.
FIRST_USE_RULE = (
    "Plan early magic within the protagonist's present pursuit: its discovery, use or failure "
    "should change an obstacle, a decision or the situation they are trying to change. "
    "If they suspend an established urgent pursuit, establish what they believe justifies "
    "that choice and its consequence. Possible future usefulness alone does not connect "
    "otherwise separate training episodes to that pursuit. Preserve established capabilities "
    "and author decisions, and allow enough prose space for the chosen developments."
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


def outline_rules(arc_index: int | None, *, discovery_backed: bool = False) -> list[str]:
    """The concept's rules for one outline call, by which arc it plans."""
    if arc_index is None or arc_index <= 1:
        rules = [FIRST_ARC_RULE, FIRST_USE_RULE, TURN_RULE]
        if not discovery_backed:
            rules.insert(2, THREAT_RULE)
    else:
        rules = [LATER_ARC_RULE, TURN_RULE]
    if discovery_backed:
        rules.append(DISCOVERY_ARC_RULE)
    return rules


# ------------------------------------------------------------------------------- the request

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
            "Preserve its magical encounter, character pursuit and growth direction while "
            "making their mechanics coherent.\n"
            f"{house.QUANTITY_DETAIL}\n"
            "Use person_before and want for this character; exception for their distinctive "
            "magical advantage, which need not be exclusive in the universe; first_use for "
            "a proposed early effective use, with chapter placement left to planning unless "
            "the author specifies it.\n"
            "system describes the game system that tracks actual personal capability, "
            "independently of institutional approval. Its appearance and feedback go in "
            "manner and look; it need not speak. steps is the known span of advancement, "
            "not a final ceiling; strongest_known shows what greater capability can do. pays names "
            "a useful change in what this character can do, including beyond their initial "
            "advantage.\n"
            "threat is the story's obstacle or danger and first_reach its encounter; a "
            "mass killing or world invasion is not required. The turn develops the pursuit; "
            "use second_system only if the treatment calls for it, preserving earned "
            "capabilities across any transition.\n"
            "first_arc develops the supplied opening into a middle and close; the opening "
            "has not happened yet and its developments may span chapters. debts names two to "
            "four questions with due_scene within the requested arc. Return only the "
            "schema fields; the original discovery treatment is retained separately."
        )
        # Discovery already made the creative choices. Mechanical development receives
        # that treatment and the author brief, without reopening the dossier's preferences.
        system = task
    return CompletionRequest(
        prompt=prompt,
        system=system,
        schema=CONCEPT_SCHEMA,
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


def _sentence(line: str) -> str:
    """A line that ends like a sentence, so a model's clause without a stop still reads."""
    return line if line.endswith((".", ":", "!", "?", ")")) else f"{line}."


__all__ = [
    "AFTER_FIRST_ARC",
    "BEFORE_CHAPTER_ONE",
    "CONCEPT_PLAN_ID",
    "CONCEPT_PROFILE",
    "CONCEPT_SCHEMA",
    "DISCOVERY_CONCEPT_PROFILE",
    "FIRST_ARC_RULE",
    "FIRST_USE_RULE",
    "INSIDE_FIRST_ARC",
    "LATER_ARC_RULE",
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
