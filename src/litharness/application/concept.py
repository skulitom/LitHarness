"""The concept: the book invented before its listing, one stage above where the pipeline began.

**What was measured, and it is the first fault the settled-listing loop found in the listing
itself** (`plan/serial-pilot-21.md` §5.4). Four draws under one listing gave the system its
voice, the chapter its story, the narrator his and the listener theirs, and the fourth read's
engagement half found no horizon a reader could feel: *everybody on Earth got a sheet*, said
once, then a shed, a second monster that was the first one again, and the first grade of a climb
whose length the page never states. Both anchors close their first chapter on a scale — a
numbered universe; a multiverse and a herald — and ours closed on an appointment. The cause was
upstream of every prompt the loop had touched: the listing's own horizon was *off nights for
good*, and the world seed is shown the listing and nothing above it
(`world_agent.render_seed_request`), so the world it builds is the world the listing sold.
Nothing in the pipeline held a book-level idea — no turn, no horizon, no shape for the first
arc, no debt opened on purpose — and the operator's question of the same day, whether the
pipeline could invent a premise with a turn in it, had the answer *no*: it executed briefed
premises and invented none.

**So: one writer, one concept, drawn before the listing and never chosen among.** The concept
is material and not a rule essay one level up (§154): every field names a thing a later stage
puts to work. The listing is written from it (`overview.render_overview_request`), the seed is
told what the world has to be able to hold (`world_agent.render_seed_request`), the outline
plans the first arc against it (`outline.render_outline_request`), and its debts open the
promise ledger before scene one (`new --concept`), which is the ledger the listing path never
wrote to. Nothing here ranks (§61(5)): one concept per book, drawn once; a second draw is a
second book.

**Where it lives.** The concept is an unlocked `BOOK_PLAN` item. The seed and outline
read it through `concept_of`; the scene packet renders it in a budgeted intentions section,
separate from established facts and author locks. Future plans are not past events or
permission to disclose a secret early. Concept-backed books require scene plans before
drafting, even when their short beat sheets contain no repeated function labels.

**Two systems, and what this house can and cannot print yet.** The operator's example premise
puts one person under a second system after a turn, keeping some of the first's grants. The
concept can say so, the seed is asked to declare both, and the drafting side reads the one
system whose columns the printed line has (`extraction._printing_system`). What is not built is
the swap itself: a book whose printed line changes systems mid-serial needs a sheet with a
position, and `extraction.sheet_for` still abstains to the default on two declared sheets. A
two-system book therefore opens after its turn, or holds the turn past the first arc, until that
half exists; the ledger entry says so.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import litharness_contracts as lc

from litharness.application.overview import FIRST_PERSON_ASK
from litharness.domain import schema_words
from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer

CONCEPT_PROFILE = "writer.concept.v0"

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
    #: The first time the exception works for them, inside chapter one (read 18 §3: every
    #: chapter this house had drawn ended with its person worse off or merely offered something).
    first_use: str
    want: str
    system: SystemConcept
    threat: Threat
    turn: Turn
    first_arc: FirstArc
    debts: tuple[Debt, ...]
    second_system: SecondSystem | None = None

    # ------------------------------------------------------------------ reading one back

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Concept:
        """A concept off a model answer or a file, or `MalformedConcept` naming the field."""
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

    def to_jsonable(self) -> dict[str, Any]:
        return {
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
        packet read it through `concept_of`, with the packet labelling it as planned story.
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
        """The concept as a person reads it, and as the listing writer and the seed are shown it.

        Plain labels, and none of this system's own machinery words in them
        (`house.MACHINERY_WORDS`): the listing writer reads this block and a word here reaches a
        reader at one remove.
        """
        lines = [
            f"Who they were the day before: {self.person_before}",
            f"What they alone have, from the first chapter: {self.exception}",
            f"The first time it works, in chapter one: {self.first_use}",
            f"What they want, in their own words: {self.want}",
            f"The system, {self.system.name}. How it shows itself: {self.system.manner}",
            f"What it looks like: {self.system.look}",
            (
                f"How far up it goes: {self.system.steps} steps. Where the strongest person "
                f"anyone has heard of stands: {self.system.strongest_known}"
            ),
            f"What a step up buys: {self.system.pays}",
            f"What kills people here, in the first days: {self.threat.what}",
            f"Where it first reaches them: {self.threat.first_reach}",
            f"The turn, {self.turn.when}: {self.turn.event}",
        ]
        if self.second_system is not None:
            lines.append(
                f"A second system after the turn, {self.second_system.name}. How it shows "
                f"itself: {self.second_system.manner}"
            )
            lines.append(f"What carries over from the first: {self.second_system.kept}")
        lines.append(f"The first arc opens: {self.first_arc.opens}")
        lines.append(f"Its middle: {self.first_arc.middle}")
        lines.append(f"It closes: {self.first_arc.closes}")
        lines.append("What the book owes, and the scene each is due by:")
        for debt in self.debts:
            due = f" (by scene {debt.due_scene})" if debt.due_scene is not None else ""
            lines.append(f"- {debt.subject}: {debt.owed}{due}")
        return "\n".join(_sentence(line) for line in lines)

    def render_for_listing(self) -> str:
        """Material under the listing's brief: the book the listing is selling."""
        return f"The book this listing sells, as its writer conceived it:\n{self.render()}"

    def render_for_seed(self) -> str:
        """Material under the listing in the seed prompt: what the world has to be able to hold."""
        heading = "What the book is to become, which the world has to be able to hold:"
        return f"{heading}\n{self.render()}"

    def for_outline(self) -> dict[str, Any]:
        """The complete concept, including what survives its turn, with the horizon view.

        An abbreviated view previously omitted `second_system.kept`, so the planner could
        schedule gains inconsistent with the state the concept intended to carry forward.
        Keep the existing horizon key for the outline rules without discarding other fields.
        """
        return {
            **self.to_jsonable(),
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
        found.update(schema_words.named_in(self.render()))
        return tuple(sorted(found))

    def promise_entries(self) -> list[dict[str, Any]]:
        """The debts in the shape `new --promises` reads, so one loader opens both."""
        return [
            {"subject": debt.subject, "description": debt.owed, "due_scene": debt.due_scene}
            for debt in self.debts
        ]


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
    "Plan this arc from book_concept.first_arc.opens to book_concept.first_arc.closes, through "
    "its middle: each is an event the scenes reach, not a mood."
)
LATER_ARC_RULE = (
    "book_concept.first_arc is the first arc's shape and has been written; this arc builds past "
    "its close."
)
TURN_RULE = (
    "book_concept.turn lands where its when says and no earlier: a turn due after this arc is "
    "prepared inside it and not paid."
)


#: Read 18 §3: the power works on the page inside chapter one, and the threat is seen doing
#: what it does before it reaches the person. Both are placements of material the concept
#: already holds, and neither names an effect on a reader.
FIRST_USE_RULE = (
    "book_concept.first_use happens inside the first chapter's scenes, on the page and not "
    "reported afterwards, and it works."
)
THREAT_RULE = (
    "book_concept.threat.first_reach is placed where the concept says, and what the threat "
    "does to people is on the page before it reaches the person."
)


def outline_rules(arc_index: int | None) -> list[str]:
    """The concept's rules for one outline call, by which arc it plans."""
    if arc_index is None or arc_index <= 1:
        return [FIRST_ARC_RULE, FIRST_USE_RULE, THREAT_RULE, TURN_RULE]
    return [LATER_ARC_RULE, TURN_RULE]


# ------------------------------------------------------------------------------- the request

#: **Floorless, like the listing.** The house rules are about prose and this call writes none;
#: every sentence here names a field and what fails it, and the market's shape (a person the
#: reader has been, an exception that is one person's) is the standing direction (§174, the
#: hook memo) rather than taste.
_TASK = (
    "You are inventing the book before a word of it exists: what a reader of this shelf tells "
    "a friend, months on, to make them start it. Answer the fields asked for and nothing else.\n"
    "Whoever it happens to is somebody this shelf's reader has been: one plain clause of who "
    "they were the day before.\n"
    "The exception is one power this person has that nobody else in the world has, and the "
    "first use is the first time it works for them, inside chapter one.\n"
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
    return CompletionRequest(
        prompt=prompt,
        system=_system(writer),
        schema=CONCEPT_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=CONCEPT_PROFILE,
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
