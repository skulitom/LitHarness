"""The surgical pass: each located tell said again, verified by code, batched by family.

`domain/tells.py` finds the sentences and holds the page to the shelf's own rate; this module
asks a model to say the located sentences again and lets the locator decide, one sentence at a
time, whether the shape is gone. The model is never asked whether anything is good, never shown
the page, and never given a rule about prose in general: it is handed the located sentences of
one family with the sentence before and after each for its facts, and one line saying what to
leave out. A sentence the locator still finds a shape in after two batched tries is left as
drafted and the record says so. A page under the shelf's ceiling on a family is not touched for
that family, and a book with no shelf is not touched at all.

**Why a rewrite and not a redraw, and why code and not a clause.** The listing loop redraws a
hundred words on a counter; a scene is two thousand and a redraw is a fresh set of the same
defaults (§105). Five clauses on the house floor were measured moving no sentence metric (§187).
What has removed a tell in this house is code at a seat after the model and before the gate —
the em-dash strip, the markup strip — and this is that seat for the tells a strip cannot reach.

**Why batched** (§199.3). The first version asked for one sentence per call, and the transport
charged the harness tax on every one: sixty-one calls at about forty-six thousand tokens each,
$10.44 on a $6.90 chapter. A family's located sentences now travel in one request and come back
labelled, and only the ones the locator refuses go out again, once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from litharness.domain import tells
from litharness.domain.generation import CompletionRequest

REWRITE_PROFILE = "tells.rewrite.v0"
MAX_OUTPUT_TOKENS = 4000
#: Two batched tries per family, then what is left stays as drafted: a third is a redraw by
#: another name.
ATTEMPTS = 2

#: One line per family, rendered only for the family the batch carries. Each names what to
#: leave out of a sentence; none is a rule about the page.
FAMILY_ASKS: Mapping[str, str] = {
    tells.ABSENCE: "Say what is there rather than what is not.",
    tells.PARADOX: "Say it once, without turning it back on itself.",
    # Named literally, because the family holds two shapes (the located habit and the
    # *the way a dropped thing coils* simile) and an ask about habit left the simile standing.
    tells.THE_WAY: "Say it without the words 'the way'.",
    tells.ECHO: "Say the phrase once.",
    tells.CHAINED_AND: "Break it into more than one sentence, with at most one and in each.",
}

_SYSTEM = (
    "You are asked to say some sentences of a novel again, each on its own. Keep every fact "
    "and every name in each and its length about the same. Return only JSON of the form "
    '{"sentences": [{"label": "S1", "text": "..."}]}, one entry per label given.'
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sentences"],
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "text"],
                "properties": {"label": {"type": "string"}, "text": {"type": "string"}},
            },
        }
    },
}


def rewrite_system(family: str) -> str:
    return f"{_SYSTEM}\n{FAMILY_ASKS[family]}"


@dataclass(frozen=True, slots=True)
class Item:
    """One located sentence in a batch, with its neighbours for its facts."""

    label: str
    located: tells.Located
    before: str
    after: str


def render_rewrite_request(items: Sequence[Item], family: str) -> CompletionRequest:
    """The family's located sentences, labelled, each with the sentence before and after it."""
    blocks = []
    for item in items:
        block = f"[{item.label}]"
        if item.before.strip():
            block += f"\nThe sentence before it: {item.before.strip()}"
        block += f"\nThe sentence: {item.located.text.strip()}"
        if item.after.strip():
            block += f"\nThe sentence after it: {item.after.strip()}"
        blocks.append(block)
    return CompletionRequest(
        prompt="\n\n".join(blocks),
        system=rewrite_system(family),
        schema=SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REWRITE_PROFILE,
        call_class="generation",
        timeout_seconds=300.0,
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


def _acceptable(original: str, replacement: str | None) -> str | None:
    """The locator's verdict and two bounds; the accepted text, or `None`.

    A rewrite that came back on more than one line is joined on spaces, since the chained-and
    ask asks for more than one sentence. **No family at all, not merely the one being said
    again** (§199.1): a rewrite that trades one shape for another is refused.
    """
    if replacement is None:
        return None
    text = " ".join(part.strip() for part in replacement.splitlines() if part.strip())
    if not text or tells.is_machine_line(text):
        return None
    words, was = len(text.split()), len(original.split())
    if words > 2 * was + 4 or words * 3 < was:
        return None
    return text if not tells.locate(text) else None


def _neighbours(text: str, located: tells.Located) -> tuple[str, str]:
    parts = tells.sentences_of(text.split("\n\n")[located.paragraph])
    before = parts[located.sentence - 1] if located.sentence > 0 else ""
    after = parts[located.sentence + 1] if located.sentence + 1 < len(parts) else ""
    return before, after


def _needed(text: str, family: str, limits: Mapping[str, float]) -> list[tells.Located]:
    """The located sentences of a family, as many as the ceiling asks, in reading order."""
    rate = tells.density(text)[family]
    ceiling = limits.get(family, 0.0)
    if rate <= ceiling:
        return []
    found = [item for item in tells.locate(text) if item.family == family]
    words = tells.word_count(text) or 1
    allowed = int(ceiling * words / 1000.0)
    return found[: max(0, len(found) - allowed)]


def apply(
    text: str,
    *,
    limits: Mapping[str, float] | None,
    complete: Callable[[CompletionRequest], Mapping[str, Any] | None],
    attempts: int = ATTEMPTS,
) -> TellsResult:
    """Say the located sentences again, family by family, until the page is under the shelf.

    Families in the reads' order. For each, the sentences over the ceiling go out in one
    request; every answer is checked by the locator; the accepted ones are put back from the
    end of the page forward so no index moves under another; what was refused goes out once
    more. With no shelf there is no ceiling and the text is returned as it was, with no call.
    """
    before = tells.density(text)
    if limits is None:
        return TellsResult(text, before, before, 0, 0, 0)
    rewritten = left = calls = 0
    for family in tells.FAMILIES:
        pending = _needed(text, family, limits)
        for _attempt in range(attempts):
            if not pending:
                break
            items = [
                Item(f"S{index + 1}", located, *_neighbours(text, located))
                for index, located in enumerate(pending)
            ]
            calls += 1
            answer = complete(render_rewrite_request(items, family))
            returned: dict[str, str] = {}
            if isinstance(answer, Mapping):
                for entry in answer.get("sentences") or ():
                    if isinstance(entry, Mapping):
                        returned[str(entry.get("label", ""))] = str(entry.get("text", ""))
            accepted: list[tuple[tells.Located, str]] = []
            refused: list[tells.Located] = []
            for item in items:
                kept = _acceptable(item.located.text, returned.get(item.label))
                if kept is None:
                    refused.append(item.located)
                else:
                    accepted.append((item.located, kept))
            for located, kept in sorted(
                accepted, key=lambda pair: (pair[0].paragraph, pair[0].sentence), reverse=True
            ):
                text = tells.replace_sentence(text, located, kept)
            rewritten += len(accepted)
            # Re-locate what was refused against the text as it now stands, since indices in
            # a paragraph shift when an earlier sentence became two.
            still = {item.text for item in refused}
            pending = [
                item for item in tells.locate(text) if item.family == family and item.text in still
            ]
        left += len(pending)
    return TellsResult(text, before, tells.density(text), rewritten, left, calls)


__all__ = [
    "ATTEMPTS",
    "FAMILY_ASKS",
    "REWRITE_PROFILE",
    "SCHEMA",
    "Item",
    "TellsResult",
    "apply",
    "render_rewrite_request",
    "rewrite_system",
]
