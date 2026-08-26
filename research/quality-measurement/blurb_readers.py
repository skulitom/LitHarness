"""Research-only reader panel retained for the completed blurb-location experiments.

This is not a production gate. The panel originally lived inside the retired Forge's
comprehension screen; the two still-useful blurb probes own their instrument here so removing
Forge cannot leave an application module pretending to be part of the current book workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litharness.domain.generation import CompletionRequest


@dataclass(frozen=True, slots=True)
class Reader:
    reader_id: str
    name: str
    reads_for: str
    drops_on: str

    def system(self) -> str:
        return (
            f"You are {self.name}. You read for {self.reads_for}. You stop reading on "
            f"{self.drops_on}. You answer questions about what you read in your own words, "
            "as yourself."
        )


READERS: tuple[Reader, ...] = (
    Reader(
        "climber",
        "the progression and cultivation reader",
        "watching somebody go from nothing to genuinely dangerous, and getting to feel "
        "every jump on the way",
        "numbers that go up without changing what anybody can do. I start a lot of serials "
        "and drop most of them inside three chapters",
    ),
    Reader(
        "stranger",
        "the isekai and portal reader",
        "somebody dropped into a world whose rules they have to work out, using what they "
        "already knew how to do",
        "words used as if I already knew them, or a newcomer who arrives fluent. Most portal "
        "stories lose me in the first chapter and I stop there",
    ),
    Reader(
        "regular",
        "the cozy, academy and slow-burn reader",
        "a place worth coming back to, and people who get better at something slowly enough "
        "that I see it happen",
        "grimness for its own sake, or a story that skips the years it told me mattered. I "
        "abandon more books than I finish and I do it without guilt",
    ),
    Reader(
        "mechanism",
        "the science-fiction and superhero reader",
        "powers with a mechanism under them, and consequences that follow from the mechanism "
        "rather than from what the scene needs",
        "hand-waving where the rule should be, or an ability that does whatever is convenient. "
        "I read the first chapter of most things and go no further",
    ),
)


DEFINITION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["can_do", "in_the_way", "expect_next", "undefined_words", "open_questions"],
    "properties": {
        "can_do": {
            "type": "string",
            "description": (
                "In your own words: what can this person do that nobody else can? One or two "
                "plain sentences. Do not reuse the text's phrasing."
            ),
        },
        "in_the_way": {
            "type": "string",
            "description": (
                "In your own words: what is in the way, or what does it cost them?"
            ),
        },
        "expect_next": {
            "type": "string",
            "description": "What kind of book is this, and what do you expect to happen next?",
        },
        "undefined_words": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Words or phrases used as if you already knew them, where you were never told "
                "what they mean. Quote each one. Empty list if none."
            ),
        },
        "open_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Things you expect the book itself to answer later — a hook, a withheld fact, "
                "something you want to read on for. These are not faults. Quote each one. "
                "Empty list if none."
            ),
        },
    },
}

_ASK = (
    "That is the back-cover copy of a book you just picked up. Answer in your own words, as if "
    "telling a friend — do not quote the text back."
)


def render_definition_request(reader: Reader, text: str) -> CompletionRequest:
    return CompletionRequest(
        prompt=f"{text.strip()}\n\n---\n\n{_ASK}",
        system=reader.system(),
        schema=DEFINITION_SCHEMA,
        max_output_tokens=1500,
        profile="research.blurb-definition-screen.v0",
        call_class="generation",
    )
