"""Render one optional, contained rewrite of an unaccepted scene.

The rewrite receives the original material and the author's frozen lock block. It
makes no selection between candidates. Mechanical containment and the draft gates
remain the handler's responsibility; exact input delivery does not prove obedience.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from litharness.application.prompt_source_view import (
    COMPOSITION_COVERAGE,
    validated_prompt_sources,
)
from litharness.domain import house
from litharness.domain.generation import CompletionRequest

REVISION_PROFILE = "reviser.scene.v0"
# None uses the configured provider's model; this role does not choose a fallback.
REVISION_MODEL: str | None = None
MAX_OUTPUT_TOKENS = 4096
TIMEOUT_SECONDS = 600.0


_TASK = (
    "You are given one scene of a novel that is already written, and before it the material it "
    "was written from. Return that same scene rewritten, changing only how its sentences and "
    "its paragraphs are built.\n"
    "Nothing that happens changes: the same events in the same order with the same outcome, "
    "done and said by the same people in the same place. Nothing is added and nothing is cut. "
    "No name, no number and no fact that is not already in the scene you were given.\n"
    "A line beginning with a bracketed word in capitals is printed by the book as a machine "
    "rather than as prose. Reproduce each one character for character, where it already sits "
    "and as many times as it already appears; a check on the returned text compares them, and "
    "what fails it is discarded unread.\n"
    "What fails is a sentence hanging one happening on the next with no more between them than "
    "a conjunction or a comma, where one of them is the reason, the moment or the condition of "
    "another and the sentence never says which.\n"
    "What fails is a pair of sentences side by side where one is the reason, the moment or the "
    "condition of the other and neither says which.\n"
    "What fails is a phrase punctuated as a sentence with no verb of its own, and a phrase "
    "opening a sentence whose actor is not the subject of the clause it opens.\n"
    "What fails is a run of sentences beginning the same way.\n"
    "What fails is a perception belonging to somebody in the scene and reported about them "
    "where they are present to say it or to think it; one nobody there is placed to have is "
    "not that.\n"
    "What fails is a paragraph whose last sentence is about something its first sentence was "
    "not.\n"
    "What fails is a phrase folding a fact the reader has not been given into a modifier, so "
    "that the sentence reads as though they had it.\n"
    "What fails is a narrator explaining what one person did or said with a rule about what "
    "people in general do or mean, however true the rule is; what somebody in the scene makes "
    "of it is not that.\n"
    "What fails is a clause naming an absence or a permission nothing had put in question, or "
    "stating anything else its own sentence already implies; one carrying what the reader could "
    "not have supplied is not that.\n"
    "What fails is a comparison to a thing that does not have the quality it is being compared "
    "for; one a reader completes without stopping is not that.\n"
    "What fails is calling a thing by a specialist's word where ordinary speech has one for the "
    "same thing.\n"
    "What fails is a sentence explaining this moment by what a person always does or says; one "
    "showing what they do now is not that.\n"
    "Return the rewritten scene and nothing else: no heading, no preamble, no commentary, and "
    "nothing about what you changed."
)


def revision_system() -> str:
    """The unchanged clarity floor and sentence/paragraph rewrite task."""
    return house.with_clarity_floor(_TASK)


def revision_author_locks(
    payload: dict[str, Any], *, recorded_input_digest: str | None
) -> tuple[str | None, str | None]:
    """Recover the exact frozen lock insertion, or explain why revision must abstain.

    Empty text is a verified absence. None means the historical authority handoff
    cannot be established; it must not be treated as a book with no author locks.
    """
    recorded, reason = validated_prompt_sources(
        payload, recorded_input_digest=recorded_input_digest
    )
    if recorded is None:
        return None, reason
    context = recorded["context"]
    if (
        context.get("source") != "drafting_composition"
        or context.get("coverage") != COMPOSITION_COVERAGE
    ):
        return None, "revision_composition_not_established"
    for source_key, payload_key in (
        ("book_id", "book_id"),
        ("branch_id", "branch_id"),
        ("logical_id", "logical_id"),
        ("manuscript_revision_id", "revision_id"),
        ("plan_revision_id", "plan_revision_id"),
    ):
        if not isinstance(payload.get(payload_key), str) or not payload[payload_key]:
            return None, "revision_source_scope_not_recorded"
        if context.get(source_key) != payload[payload_key]:
            return None, "revision_source_scope_not_recorded"
    entries = recorded["entries"]
    blocks = [entry for entry in entries if entry["section"] == "locks"]
    items = [
        entry
        for entry in entries
        if entry["kind"] == "context_item" and entry["section"] == "constraints"
    ]
    if not blocks and not items:
        return "", None
    if len(blocks) != 1 or not items:
        return None, "revision_locks_ambiguous"
    block = blocks[0]
    if (
        block["stage"] != "system"
        or block["kind"] != "renderer"
        or block["source"].get("producer") != "application.planner.render_prompt:locks"
        or block["start"] == block["end"]
    ):
        return None, "revision_locks_invalid_renderer"
    for item in items:
        if (
            item["stage"] != "system"
            or not block["start"] <= item["start"] <= item["end"] <= block["end"]
            or item["source"]["authority"] != "author_locked"
            or item["source"]["source_kind"] != "plan"
            or item["source"].get("plan_revision_id") != payload["plan_revision_id"]
        ):
            return None, "revision_locks_invalid_item"
    # Renderer/item overlap is intentional. Distinct constraint bodies cannot overlap.
    ordered = sorted(items, key=lambda item: (item["start"], item["end"]))
    if any(left["end"] > right["start"] for left, right in pairwise(ordered)):
        return None, "revision_locks_overlapping_items"
    return payload["system"][block["start"] : block["end"]], None


def render_revision_request(
    scene: str,
    *,
    material: str | None = None,
    model: str | None = REVISION_MODEL,
    author_lock_system: str = "",
) -> CompletionRequest:
    """Keep the scene last and the original author-lock block last in SYSTEM.

    Material is the stored packet without the drafting instruction. The handler
    validates the separate lock handoff; an empty block preserves the old request.
    Standalone callers may still render a scene with no material.
    """
    body = scene.strip()
    if not body:
        raise ValueError("there is no scene here to revise")
    prompt = (
        f"THE MATERIAL THIS SCENE WAS WRITTEN FROM\n\n{material.strip()}\n\nTHE SCENE\n\n{body}"
        if material and material.strip()
        else f"THE SCENE\n\n{body}"
    )
    return CompletionRequest(
        prompt=prompt,
        system=revision_system() + author_lock_system,
        model=model,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REVISION_PROFILE,
        call_class="generation",
        timeout_seconds=TIMEOUT_SECONDS,
    )


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "REVISION_MODEL",
    "REVISION_PROFILE",
    "TIMEOUT_SECONDS",
    "render_revision_request",
    "revision_author_locks",
    "revision_system",
]
