"""The surgical pass: each located tell said again, one sentence at a time, verified by code.

`domain/tells.py` finds the sentences and holds the page to the shelf's own rate; this module
asks a model to say one located sentence again and lets the locator decide whether the shape is
gone. The model is never asked whether anything is good, never shown the page, and never given
a rule about prose in general: it is handed one sentence, the sentence before and after it for
its facts, and one line saying what to leave out. If the shape is still there after two tries
the sentence is left as drafted and the record says so. A page under the shelf's ceiling on a
family is not touched for that family, and a book with no shelf is not touched at all.

**Why a rewrite and not a redraw, and why code and not a clause.** The listing loop redraws a
hundred words on a counter; a scene is two thousand and a redraw is a fresh set of the same
defaults (§105: the agentic path bought nothing). Five clauses on the house floor were measured
moving no sentence metric (§187). What has removed a tell in this house is code at a seat after
the model and before the gate — the em-dash strip, the markup strip — and this is that seat
for the tells a strip cannot reach, because a sentence built on an absence has to be said again
rather than deleted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from litharness.domain import tells
from litharness.domain.generation import CompletionRequest

REWRITE_PROFILE = "tells.rewrite.v0"
MAX_OUTPUT_TOKENS = 400
#: Two tries per sentence, then it stays as drafted: a third try is a redraw by another name.
ATTEMPTS = 2

#: One line per family, rendered only for the family the sentence carries. Each names what to
#: leave out of one sentence; none is a rule about the page.
FAMILY_ASKS: Mapping[str, str] = {
    tells.ABSENCE: "Say what is there rather than what is not.",
    tells.PARADOX: "Say it once, without turning it back on itself.",
    tells.THE_WAY: "Show what the person does now, not what they always do.",
    tells.ECHO: "Say the phrase once.",
    tells.CHAINED_AND: "Break it into more than one sentence, with at most one and in each.",
}

_SYSTEM = (
    "You are asked to say one sentence of a novel again. Keep every fact and every name in "
    "it and its length about the same. Return only the sentence."
)


def rewrite_system(family: str) -> str:
    return f"{_SYSTEM}\n{FAMILY_ASKS[family]}"


def render_rewrite_request(
    sentence: str, family: str, *, before: str = "", after: str = ""
) -> CompletionRequest:
    """One sentence, the two beside it for its facts, and one line for the family."""
    context = ""
    if before.strip():
        context += f"The sentence before it:\n{before.strip()}\n\n"
    if after.strip():
        context += f"The sentence after it:\n{after.strip()}\n\n"
    return CompletionRequest(
        prompt=f"{context}The sentence:\n{sentence.strip()}",
        system=rewrite_system(family),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REWRITE_PROFILE,
        call_class="generation",
        timeout_seconds=120.0,
    )


@dataclass(frozen=True, slots=True)
class TellsResult:
    """What the pass did to one text: the rates before and after, and how many sentences moved."""

    text: str
    before: dict[str, float]
    after: dict[str, float]
    rewritten: int
    left: int
    calls: int

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "before": {family: round(rate, 2) for family, rate in self.before.items()},
            "after": {family: round(rate, 2) for family, rate in self.after.items()},
            "rewritten": self.rewritten,
            "left": self.left,
            "calls": self.calls,
        }

    @property
    def detail(self) -> str:
        moved = ", ".join(
            f"{family} {self.before[family]:.1f}->{self.after[family]:.1f}"
            for family in tells.FAMILIES
            if self.before[family] != self.after[family]
        )
        return (
            f"{self.rewritten} sentence(s) said again, {self.left} left as drafted, "
            f"{self.calls} call(s)" + (f"; {moved}" if moved else "; nothing over the shelf")
        )


def _acceptable(original: str, replacement: str | None, family: str) -> bool:
    """The locator's verdict, and two bounds so a rewrite cannot become a paragraph or nothing."""
    if replacement is None:
        return False
    text = replacement.strip()
    if not text or "\n" in text or tells.is_machine_line(text):
        return False
    words, was = len(text.split()), len(original.split())
    if words > 2 * was + 4 or words * 3 < was:
        return False
    return family not in {item.family for item in tells.locate(text)}


def apply(
    text: str,
    *,
    limits: Mapping[str, float] | None,
    complete: Callable[[CompletionRequest], str | None],
    attempts: int = ATTEMPTS,
) -> TellsResult:
    """Say the located sentences again, family by family, until the page is under the shelf.

    Families in the reads' order; within a family, in reading order; the rate is recomputed
    after every replacement so no sentence is touched once the family is under its ceiling.
    With no shelf there is no ceiling and the text is returned as it was, with no call made.
    """
    before = tells.density(text)
    if limits is None:
        return TellsResult(text, before, before, 0, 0, 0)
    rewritten = left = calls = 0
    for family in tells.FAMILIES:
        for located in [item for item in tells.locate(text) if item.family == family]:
            if tells.density(text)[family] <= limits.get(family, 0.0):
                break
            neighbours = tells.sentences_of(text.split("\n\n")[located.paragraph])
            before_sentence = neighbours[located.sentence - 1] if located.sentence > 0 else ""
            after_sentence = (
                neighbours[located.sentence + 1]
                if located.sentence + 1 < len(neighbours)
                else ""
            )
            replaced = False
            for _attempt in range(attempts):
                calls += 1
                answer = complete(
                    render_rewrite_request(
                        located.text, family, before=before_sentence, after=after_sentence
                    )
                )
                if _acceptable(located.text, answer, family):
                    assert answer is not None
                    text = tells.replace_sentence(text, located, answer)
                    replaced = True
                    break
            if replaced:
                rewritten += 1
            else:
                left += 1
    return TellsResult(text, before, tells.density(text), rewritten, left, calls)


__all__ = [
    "ATTEMPTS",
    "FAMILY_ASKS",
    "REWRITE_PROFILE",
    "TellsResult",
    "apply",
    "render_rewrite_request",
    "rewrite_system",
]
