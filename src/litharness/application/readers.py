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


#: Eight readers, four a side. The two halves are written to be the same kind of person so that
#: a difference between the lanes is not a difference in who was asked.
READERS: tuple[Reader, ...] = (
    Reader(
        "climber_s", STEERING,
        "a climb with rules — what the next rung costs and what it lets somebody do",
        "figures that move without changing what anyone can do",
    ),
    Reader(
        "stranger_s", STEERING,
        "somebody dropped into a world whose rules they work out with what they already knew",
        "terms and ranks used as if I already knew them",
    ),
    Reader(
        "power_s", STEERING,
        "watching somebody go from nobody to dangerous, and feeling each step of it",
        "a protagonist who is already finished on page one",
    ),
    Reader(
        "regular_s", STEERING,
        "a place worth coming back to and people who get better slowly enough that I see it",
        "grimness for its own sake, or a story that skips the years it told me mattered",
    ),
    Reader(
        "climber_m", MEASUREMENT,
        "a climb with rules — what the next rung costs and what it lets somebody do",
        "figures that move without changing what anyone can do",
    ),
    Reader(
        "stranger_m", MEASUREMENT,
        "somebody dropped into a world whose rules they work out with what they already knew",
        "terms and ranks used as if I already knew them",
    ),
    Reader(
        "power_m", MEASUREMENT,
        "watching somebody go from nobody to dangerous, and feeling each step of it",
        "a protagonist who is already finished on page one",
    ),
    Reader(
        "regular_m", MEASUREMENT,
        "a place worth coming back to and people who get better slowly enough that I see it",
        "grimness for its own sake, or a story that skips the years it told me mattered",
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


__all__ = [
    "ANTICIPATE_PROFILE",
    "ANTICIPATION_SCHEMA",
    "BUDGET_CHAPTERS",
    "CALL_CLASS",
    "CHOICE_SCHEMA",
    "CONTINUE_PROFILE",
    "MEASUREMENT",
    "READERS",
    "STEERING",
    "Anticipation",
    "Reader",
    "Reading",
    "pool",
    "render_anticipation_request",
    "render_choice_request",
]
