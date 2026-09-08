"""Public listing and title requests, plus deterministic listing shape checks.

A supplied concept selects the public-listing brief; an absent concept retains the
legacy invention task. Both optionally use a writer identity, without the shared
scene-writing rules. Callers own transport, redraw policy and persistence.

Shape counters describe text, not reader interest or literary quality. Task wording
is author direction, not a validated quality mechanism. Historical experiments and
reversals belong in plan/stage-0-decisions.md; prompt budgets are checked in
tests/test_prompt_budget.py.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer

# Separate profiles retain the identity of legacy and supplied-concept requests.
OVERVIEW_PROFILE = "writer.overview.v0"
CONCEPT_OVERVIEW_PROFILE = "writer.overview.concept.v2"
TITLE_PROFILE = "writer.title.v0"

MAX_OUTPUT_TOKENS = 4000

_COORDINATORS = re.compile(r"\b(?:and|then)\b", re.IGNORECASE)


def coordinator_density(listing: str) -> float:
    """Count "and" and "then" per hundred whitespace-delimited words.

    This is a shape counter, not a quality score. Empty text has density zero.
    """
    words = len(listing.split()) or 1
    return 100 * len(_COORDINATORS.findall(listing)) / words


def keep_least_chained(drawn: list[str]) -> str:
    """Keep the lowest-density draw, breaking ties by original order.

    The caller supplies a bounded redraw history; an empty history is an error.
    Selection is deterministic and uses no model judgment.
    """
    if not drawn:
        raise ValueError("a redraw loop that drew nothing has nothing to keep")
    return min(drawn, key=coordinator_density)


def chains_too_hard(listing: str, *, ceiling: float) -> bool:
    """Whether coordinator density exceeds the caller's policy ceiling."""
    return coordinator_density(listing) > ceiling


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def longest_sentence(listing: str) -> int:
    """Return the longest sentence's word count, or zero for empty text.

    Sentence boundaries are punctuation followed by whitespace, not a language parser.
    """
    parts = (part for part in _SENTENCE_END.split(listing.strip()) if part.strip())
    return max((len(part.split()) for part in parts), default=0)


def sentence_ceiling(blurbs: Sequence[str]) -> int | None:
    """Return the largest sentence word count across nonempty blurbs, or None."""
    lengths = [longest_sentence(blurb) for blurb in blurbs if blurb.strip()]
    return max(lengths) if lengths else None


def runs_too_long(listing: str, *, ceiling: int | None) -> bool:
    """Whether a sentence exceeds the ceiling; None disables the check."""
    return ceiling is not None and longest_sentence(listing) > ceiling


# Legacy invention-and-listing task, used when no concept is supplied.
_TASK = (
    "You are writing the listing for a new serial: the few lines a reader meets on the front "
    "page of a serial-fiction site, and the only thing that decides whether they open chapter "
    "one.\n"
    "A reader meeting this has not started the book. Not an account of the world. The life "
    "whoever this happens to had before it began is one plain clause saying who they were the "
    "day before, and no more: a listing with none has given the reader nobody to stand beside, "
    "and one with more has become an account of it.\n"
    "Exactness spent on floors, ranks, counts and lengths of time is space the hook needed.\n"
    "A sentence a reader can take two ways has failed, and so has one that asserts what nobody "
    "in the story could know yet.\n"
    "The book this promises is one where the person opens something and reads their own "
    "capabilities in it, and the promise names one of them they did not have before; a promise "
    "missing either half is for a book this house does not publish.\n"
    "A reader scanning a list has to see what kind of book this is and what the person is "
    "after: name the magic, the system, the monsters, the dungeon in plain words rather than "
    "implying them, and say what the person is trying to get.\n"
    "Whoever this happens to did not spend the years before the book mastering one trade: a "
    "person who arrives already good at what the book will ask of them has nowhere to go.\n"
    "A term the reader has not met needs a reason to be there before it needs anything else, "
    "and then a consequence rather than a definition: the sentence carrying it says what it "
    "does to somebody.\n"
    "A paragraph holds together or it is not a paragraph: a sentence that could be lifted out "
    "and dropped anywhere in the listing has failed.\n"
    "No title, no headings, no tags, no word about the author, and no dashes: this market's "
    "listings punctuate with full stops and commas. The person this happens to is he or she or "
    "I, and never you. About a hundred words."
)


# A supplied concept owns the story; this task introduces it to a new reader.
_CONCEPT_TASK = (
    "Write the public listing for the supplied LitRPG fantasy serial, for someone who has read "
    "neither the book nor its plan. They are deciding whether to open chapter one.\n"
    "Give them an understandable situation and a reason to follow this person: what has "
    "changed, what they want to do about it, and why that matters to them. Select connected "
    "details from the material rather than summarising each field.\n"
    "Make the magical adventure and the game system's progression concrete through the "
    "abilities this person can develop and what those let them pursue. Use ordinary language "
    "before special terminology; retain an unfamiliar name only when it helps the reader follow "
    "the situation, without requiring a glossary or a lesson in the rules.\n"
    "Curiosity should concern what will happen, not what the sentences mean. The source "
    "includes developments a new reader has not reached: withhold their answers without "
    "withholding the setup needed to understand the pursuit.\n"
    "Keep the supplied character, motives and story intact; do not invent stakes, powers "
    "or promises to make the pitch more dramatic. Exact incidental counts and timestamps "
    "do not belong in the listing.\n"
    "Write about a hundred words of finished listing only, with no title, headings, tags, "
    "author commentary or dashes; use first or third person, never address the reader as "
    "the protagonist."
)


def _system(writer: Writer | None, *, supplied_concept: bool = False) -> str:
    """Combine the optional writer identity with the selected listing task."""
    task = _CONCEPT_TASK if supplied_concept else _TASK
    return f"{writer.render()}\n\n{task}" if writer is not None else task


# Point of view is book-specific material, not a standing system rule.
FIRST_PERSON_ASK = "Told by the person it happens to, as I."


def render_overview_request(
    brief: str,
    writer: Writer | None = None,
    *,
    person: str | None = None,
    blurbs: str | None = None,
    concept: str | None = None,
) -> CompletionRequest:
    """Build one listing request from an optional brief and supplied concept.

    A truthy concept selects the public-listing task and its separate profile; without
    one, the request uses the legacy invention task. An empty brief is valid.
    The optional blurbs precede the brief, the concept follows it, and first-person
    direction stays in the user message. No scene-writing rules are appended.
    """
    ask = brief.strip() or "Anything you would most want to read."
    if person == "first":
        ask = f"{ask}\n{FIRST_PERSON_ASK}"
    prompt = f"What this book is to be about:\n{ask}"
    if concept:
        prompt = f"{prompt}\n\n{concept}"
    if blurbs:
        prompt = f"{blurbs}\n\n{prompt}"
    return CompletionRequest(
        prompt=prompt,
        system=_system(writer, supplied_concept=bool(concept)),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=CONCEPT_OVERVIEW_PROFILE if concept else OVERVIEW_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


_TITLE_TASK = (
    "You are titling the serial whose listing is below. The title is the first thing on a page "
    "of a hundred others and the only part of a book anybody has to say out loud.\n"
    "Two to five words. No subtitle, no colon, no tagline, no series number, and no quotation "
    "marks around it.\n"
    "A title that could sit on any book in this genre has failed, and so has one that needs the "
    "listing beside it to make sense.\n"
    "Answer with the title and nothing else."
)


def title_system(writer: Writer | None) -> str:
    """Assemble the title system message for generation and prompt-budget inspection."""
    return f"{writer.render()}\n\n{_TITLE_TASK}" if writer is not None else _TITLE_TASK


def render_title_request(
    overview: str,
    writer: Writer | None = None,
    taken: tuple[str, ...] = (),
    machinery: tuple[str, ...] = (),
) -> CompletionRequest:
    """Build a title request from the listing and optional writer identity.

    Taken titles and detected machinery words are book-specific exclusions in the
    user message. Empty exclusions add nothing to the request.
    """
    material = f"The listing:\n\n{overview.strip()}"
    if taken:
        material += (
            "\n\nAlready the title of a published book, so it cannot be this one:\n"
            + "\n".join(f"- {name}" for name in taken)
        )
    if machinery:
        material += (
            "\n\nNot in the title, in any form: "
            + ", ".join(sorted(machinery))
            + ". That is the tooling's word for a part of the machinery, not this book's."
        )
    return CompletionRequest(
        prompt=material,
        system=title_system(writer),
        max_output_tokens=200,
        profile=TITLE_PROFILE,
        call_class="generation",
        timeout_seconds=300.0,
    )


def clean_title(text: str) -> str:
    """Take the first nonempty line and strip heading, quote and formatting wrappers."""
    line = next((part.strip() for part in text.strip().splitlines() if part.strip()), "")
    line = line.lstrip("#").strip()
    for wrapper in ('"', "'", "\u201c", "\u2018", "*", "_"):
        line = line.strip(wrapper).strip()
    return line.rstrip(".").strip()


__all__ = [
    "CONCEPT_OVERVIEW_PROFILE",
    "MAX_OUTPUT_TOKENS",
    "OVERVIEW_PROFILE",
    "TITLE_PROFILE",
    "clean_title",
    "render_overview_request",
    "render_title_request",
    "title_system",
]
