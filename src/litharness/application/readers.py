"""The simulated readership: what it does with a chapter, and what it hopes happens next.

Two calls, two disjoint sets of readers, and the split is the whole safety argument.

**Measurement readers** answer one behavioural question under a declared budget — carry on,
put it down, or come back later. Behaviour rather than a verdict, because §89 measured the
verdict channel running 4,676x position over text and §97.4 states that no verdict slot exists
anywhere in a sim. The budget is not decoration: §94's continuation saturated at 195 of 196
because continuing was free.

**Steering readers** say what they are hoping happens next, and what they are dreading. That is
E6 — naming what is there — which is the one elicitation frame that survived §87-§89. It needs
no counter and no axis, which is why it can carry what the deleted prose-axis loop could not:
the operator's *"understand anticipation of the simulated readers to predict and provide what
the reader secretly or not so secretly desires"*.

**Nobody is in both sets.** A claim about prose shaped by the readers who then judge it is
circular, which is what §97.1 always guarded and what `pools.py` enforced in 189 lines. Here it
is two frozen rosters and one assertion, because a reader's pool is decided when it is written
down rather than drawn.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from litharness.domain.generation import CompletionRequest

#: Frozen profiles, one per lane, so the two spends are separable on the decision rows.
CONTINUE_PROFILE = "reader.continue.v0"
ANTICIPATE_PROFILE = "reader.anticipate.v0"
#: The blurb stage's two, kept separate from the chapter stage's so the spends are
#: separable on the decision rows and so a mixed run cannot be read as one number.
START_PROFILE = "reader.start.v0"
APPETITE_PROFILE = "reader.appetite.v0"

CALL_CLASS = "generation"

#: What a reader is told they have left. Small on purpose: an unbounded reader continues out of
#: politeness, which is the failure §94 measured.
BUDGET_CHAPTERS = 2

STEERING = "steering"
MEASUREMENT = "measurement"


@dataclass(frozen=True, slots=True)
class Reader:
    """One avid genre reader. `pool` is fixed here and may not be chosen at call time."""

    reader_id: str
    pool: str
    reads_for: str
    drops_on: str

    def system(self) -> str:
        return (
            f"You read a lot of LitRPG and progression fantasy — several serials at once, and "
            f"you drop most of what you start. You read for {self.reads_for}. You stop reading "
            f"on {self.drops_on}. You answer as yourself, in your own words, briefly."
        )


#: Eight readers, four a side, and the two halves are the same four people so that a
#: difference between the lanes is never a difference in who was asked.
#:
#: **Written in a reader's words and not in this repository's.** The first roster read for
#: "a climb with rules — what the next rung costs", which is `domain/worlds.py` vocabulary
#: put in a reader's mouth; it then reported back the same words as praise, and every number
#: measured with it leaned toward books that talked like the schema. Nothing below is a term
#: this system uses for its own machinery.
READERS: tuple[Reader, ...] = (
    Reader(
        "power_s", STEERING,
        "watching somebody go from nothing to genuinely dangerous, and getting to feel every "
        "jump on the way",
        "a main character who is already the strongest thing in the room on page one",
    ),
    Reader(
        "elsewhere_s", STEERING,
        "getting dropped somewhere impossible and working out how it runs at the same time the "
        "character does",
        "names and titles thrown around like I am supposed to already know them",
    ),
    Reader(
        "magic_s", STEERING,
        "the magic itself — what it actually does, how strange it gets, and somebody working "
        "out a use for it that nobody else had",
        "a world where the magic turns out to be a job with forms to fill in",
    ),
    Reader(
        "binge_s", STEERING,
        "somewhere I want to keep coming back to, people I like being around, and the next good "
        "thing always close enough to reach",
        "misery with nothing to look forward to, or a book that skips the part it told me to "
        "care about",
    ),
    Reader(
        "power_m", MEASUREMENT,
        "watching somebody go from nothing to genuinely dangerous, and getting to feel every "
        "jump on the way",
        "a main character who is already the strongest thing in the room on page one",
    ),
    Reader(
        "elsewhere_m", MEASUREMENT,
        "getting dropped somewhere impossible and working out how it runs at the same time the "
        "character does",
        "names and titles thrown around like I am supposed to already know them",
    ),
    Reader(
        "magic_m", MEASUREMENT,
        "the magic itself — what it actually does, how strange it gets, and somebody working "
        "out a use for it that nobody else had",
        "a world where the magic turns out to be a job with forms to fill in",
    ),
    Reader(
        "binge_m", MEASUREMENT,
        "somewhere I want to keep coming back to, people I like being around, and the next good "
        "thing always close enough to reach",
        "misery with nothing to look forward to, or a book that skips the part it told me to "
        "care about",
    ),
)


def pool(name: str) -> tuple[Reader, ...]:
    return tuple(reader for reader in READERS if reader.pool == name)


#: Behaviour, not a verdict. The three words are the BCR's (§97.4) and nothing else is offered.
CHOICE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["next", "because"],
    "properties": {
        "next": {
            "type": "string",
            "enum": ["carry_on", "put_it_down", "come_back_later"],
            "description": "What you actually do with your remaining reading time.",
        },
        "because": {
            "type": "string",
            "description": "One sentence, in your own words. Not a review.",
        },
    },
}

#: What they want to happen. Named, never rated — E6's shape.
ANTICIPATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["hoping_for", "dreading", "expect_next"],
    "properties": {
        "hoping_for": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things you find yourself WANTING to happen. Quote nothing; say "
                           "what you want. Empty list if you want nothing in particular.",
        },
        "dreading": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things you would be disappointed or annoyed by. Empty if none.",
        },
        "expect_next": {
            "type": "string",
            "description": "What you think actually happens next, in one or two sentences.",
        },
    },
}

_BUDGET = (
    f"You have time for about {BUDGET_CHAPTERS} more chapters today, across everything you "
    f"are part-way through. This is one of them."
)


def render_choice_request(reader: Reader, chapter: str) -> CompletionRequest:
    """A measurement reader, one chapter, one behavioural choice under a budget."""
    if reader.pool != MEASUREMENT:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not measure")
    return CompletionRequest(
        prompt=f"{chapter}\n\n---\n\n{_BUDGET} What do you do?",
        system=reader.system(),
        schema=CHOICE_SCHEMA,
        max_output_tokens=600,
        profile=CONTINUE_PROFILE,
        call_class=CALL_CLASS,
    )


def render_anticipation_request(reader: Reader, chapter: str) -> CompletionRequest:
    """A steering reader, one chapter, what they are hoping for.

    No budget clause and no choice: this reader is not deciding anything, only saying what they
    want. Mixing the two would put a decision beside a wish and let one colour the other.
    """
    if reader.pool != STEERING:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not steer")
    return CompletionRequest(
        prompt=(
            f"{chapter}\n\n---\n\nYou are part-way through this book. What are you hoping "
            "happens next, and what would disappoint you?"
        ),
        system=reader.system(),
        schema=ANTICIPATION_SCHEMA,
        max_output_tokens=800,
        profile=ANTICIPATE_PROFILE,
        call_class=CALL_CLASS,
    )


#: **The browsing behaviours, and they are not the reading ones.** §97.4 gives a sim a
#: behavioural vocabulary and no verdict slot; `CHOICE_SCHEMA`'s three words are what somebody
#: part-way through a book does. Somebody looking at an overview has not started, so
#: "carry on" is not available to them and offering it would be asking about an act they
#: cannot perform. These three are the platform's own: open it now, scroll past, or shelve it.
START_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["next", "because"],
    "properties": {
        "next": {
            "type": "string",
            "enum": ["start_reading", "pass_on_it", "save_for_later"],
            "description": "What you actually do with this listing.",
        },
        "because": {
            "type": "string",
            "description": "One sentence, in your own words. Not a review.",
        },
    },
}

#: What a browsing reader hopes a book will turn out to be. Same E6 shape as
#: `ANTICIPATION_SCHEMA` and deliberately a different schema: `expect_next` is a question about
#: a story in progress, and a reader who has read a blurb has no next.
APPETITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["hoping_for", "dreading"],
    "properties": {
        "hoping_for": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What you are hoping this book turns out to be. Say what you want.",
        },
        "dreading": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What would make you drop it by chapter three. Empty if none.",
        },
    },
}

#: **The browsing cost, and it is the one §94 said was missing.** Continuation saturated at
#: 195 of 196 because continuing was free; a blurb has the same problem worse, since nodding at
#: a listing costs nothing at all. What is scarce on this platform is not attention in the
#: abstract but the slot: a reader following several serials starts very few new ones, and the
#: competition is the rest of the page rather than nothing.
_SLOT = (
    "You are scrolling a list of new serials. You are already following several and you have "
    "room for maybe one more this month, so most of what you look at you scroll past. The "
    "rest of the page is full of other people's books."
)


def render_start_request(reader: Reader, overview: str) -> CompletionRequest:
    """A measurement reader, one overview, one behavioural choice against the rest of the page."""
    if reader.pool != MEASUREMENT:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not measure")
    return CompletionRequest(
        prompt=f"{overview}\n\n---\n\n{_SLOT} What do you do?",
        system=reader.system(),
        schema=START_SCHEMA,
        max_output_tokens=600,
        profile=START_PROFILE,
        call_class=CALL_CLASS,
    )


def render_appetite_request(reader: Reader, overview: str) -> CompletionRequest:
    """A steering reader, one overview, what they are hoping it turns out to be.

    No slot clause and no choice, for `render_anticipation_request`'s reason: a reader deciding
    something and a reader wanting something are two calls, because put together each colours
    the other.
    """
    if reader.pool != STEERING:
        raise ValueError(f"{reader.reader_id} is a {reader.pool} reader and may not steer")
    return CompletionRequest(
        prompt=(
            f"{overview}\n\n---\n\nThis is the listing for a serial that has not been "
            "written yet. What are you hoping it turns out to be, and what would make you "
            "drop it by chapter three?"
        ),
        system=reader.system(),
        schema=APPETITE_SCHEMA,
        max_output_tokens=800,
        profile=APPETITE_PROFILE,
        call_class=CALL_CLASS,
    )


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(text for item in value if isinstance(item, str) and (text := item.strip()))


@dataclass(frozen=True, slots=True)
class Reading:
    """What the measurement pool did with one chapter."""

    carried_on: int
    put_down: int
    come_back: int
    asked: int
    #: (reader_id, choice, because)
    said: tuple[tuple[str, str, str], ...]

    @property
    def answered(self) -> int:
        return self.carried_on + self.put_down + self.come_back

    @property
    def continuation(self) -> float | None:
        """Share who carried straight on. `None` when nobody answered."""
        return self.carried_on / self.answered if self.answered else None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "asked": self.asked,
            "answered": self.answered,
            "carried_on": self.carried_on,
            "put_down": self.put_down,
            "come_back_later": self.come_back,
            "continuation": self.continuation,
            "said": [
                {"reader": r, "next": c, "because": b} for r, c, b in self.said
            ],
        }

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> Reading:
        counts = {"carry_on": 0, "put_it_down": 0, "come_back_later": 0}
        said: list[tuple[str, str, str]] = []
        for reader in pool(MEASUREMENT):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            choice = str(answer.get("next") or "")
            if choice not in counts:
                continue
            counts[choice] += 1
            said.append((reader.reader_id, choice, str(answer.get("because") or "").strip()))
        return cls(
            carried_on=counts["carry_on"],
            put_down=counts["put_it_down"],
            come_back=counts["come_back_later"],
            asked=len(pool(MEASUREMENT)),
            said=tuple(said),
        )


@dataclass(frozen=True, slots=True)
class Anticipation:
    """What the steering pool wants to happen next. The direction."""

    hoping_for: tuple[str, ...]
    dreading: tuple[str, ...]
    answered: int

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "answered": self.answered,
            "hoping_for": list(self.hoping_for),
            "dreading": list(self.dreading),
        }

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> Anticipation:
        hoping: list[str] = []
        dreading: list[str] = []
        answered = 0
        for reader in pool(STEERING):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            answered += 1
            hoping.extend(_strings(answer.get("hoping_for")))
            dreading.extend(_strings(answer.get("dreading")))
        return cls(
            hoping_for=tuple(dict.fromkeys(hoping)),
            dreading=tuple(dict.fromkeys(dreading)),
            answered=answered,
        )

    def render(self) -> str:
        """The direction, as the writer reads it. Empty when nobody wanted anything.

        Reported as what readers said, not as an instruction: the writer decides what to do
        about it. An empty string renders nothing, which is what a book with no reads gets.
        """
        if not self.hoping_for and not self.dreading:
            return ""
        blocks = [
            "READERS OF THIS BOOK, ASKED WHAT THEY WANT NEXT.",
            "This is what your readers are actually hoping for. It outranks every craft rule "
            "you have been given and is outranked only by being followable.",
        ]
        if self.hoping_for:
            blocks.append(
                "Hoping for:\n" + "\n".join(f"- {item}" for item in self.hoping_for)
            )
        if self.dreading:
            blocks.append(
                "Would be disappointed by:\n" + "\n".join(f"- {item}" for item in self.dreading)
            )
        return "\n\n".join(blocks)



@dataclass(frozen=True, slots=True)
class Browsing:
    """What the measurement pool did with one overview. `Reading`'s shape, browsing's verbs."""

    started: int
    passed: int
    saved: int
    asked: int
    #: (reader_id, choice, because)
    said: tuple[tuple[str, str, str], ...]

    @property
    def answered(self) -> int:
        return self.started + self.passed + self.saved

    @property
    def start_rate(self) -> float | None:
        """Share who would open chapter one. `None` when nobody answered."""
        return self.started / self.answered if self.answered else None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "asked": self.asked,
            "answered": self.answered,
            "started": self.started,
            "passed": self.passed,
            "saved_for_later": self.saved,
            "start_rate": self.start_rate,
            "said": [{"reader": r, "next": c, "because": b} for r, c, b in self.said],
        }

    @classmethod
    def of(cls, answers: Mapping[str, Mapping[str, Any] | None]) -> Browsing:
        counts = {"start_reading": 0, "pass_on_it": 0, "save_for_later": 0}
        said: list[tuple[str, str, str]] = []
        for reader in pool(MEASUREMENT):
            answer = answers.get(reader.reader_id)
            if not isinstance(answer, Mapping):
                continue
            choice = str(answer.get("next") or "")
            if choice not in counts:
                continue
            counts[choice] += 1
            said.append((reader.reader_id, choice, str(answer.get("because") or "").strip()))
        return cls(
            started=counts["start_reading"],
            passed=counts["pass_on_it"],
            saved=counts["save_for_later"],
            asked=len(pool(MEASUREMENT)),
            said=tuple(said),
        )


__all__ = [
    "ANTICIPATE_PROFILE",
    "ANTICIPATION_SCHEMA",
    "APPETITE_PROFILE",
    "APPETITE_SCHEMA",
    "BUDGET_CHAPTERS",
    "CALL_CLASS",
    "CHOICE_SCHEMA",
    "CONTINUE_PROFILE",
    "MEASUREMENT",
    "READERS",
    "START_PROFILE",
    "START_SCHEMA",
    "STEERING",
    "Anticipation",
    "Browsing",
    "Reader",
    "Reading",
    "pool",
    "render_anticipation_request",
    "render_appetite_request",
    "render_choice_request",
    "render_start_request",
]
