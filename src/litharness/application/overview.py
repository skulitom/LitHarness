"""The book overview: what a reader sees before they open chapter one, and who writes it.

**This is the forge's job without the forge.** A world used to be assembled by an Architect with
its own identity and its own rule essay, K at a time, and an operator picked one — which is a
human production step, and §126's objective is fiction produced *without* a human production
loop. The operator, 2026-08-24: *"we just don't need a forge"*, and *"we need to pass to the
writer we are writing book overview and they are tasked in creating a compelling idea readers
will love (with a hook). But the core loop of feedback should be the same (simulated reader)."*

So: one writer from `writers.CAST`, one overview, and the same two-pool readership that reads
the chapters. Nothing here ranks anything and nothing chooses between candidates — there are no
candidates. The steering pool says what it hoped the book would be; the writer revises; the
measurement pool, which never steers, says whether it would open chapter one.

**The task text is deliberately short.** Three rules in `architect._RULES` were assertions about
what this genre's reader wants, written into a prompt addressed to nobody. A cast writer who
reads the genre knows what a hook is, and `domain/house.py` already carries the floor. Adding a
paragraph here about what makes an overview good would rebuild the rule essay one level up.
"""

from __future__ import annotations

from litharness.domain.generation import CompletionRequest
from litharness.domain.writers import Writer, system_for

#: Frozen profiles, one per stage, so a draft and a revision are separable on the decision rows.
OVERVIEW_PROFILE = "writer.overview.v0"
REVISION_PROFILE = "writer.overview.revise.v0"

MAX_OUTPUT_TOKENS = 4000

_TASK = (
    "You are writing the listing for a new serial: the overview a reader meets before they open "
    "chapter one, and the only thing that decides whether they do. Write it as prose a reader "
    "reads, not as a pitch to an editor and not as a summary of a plot. No title, no headings, "
    "no tags, no word about the author. Around two hundred words."
)


def render_overview_request(brief: str, writer: Writer | None = None) -> CompletionRequest:
    """One overview, from a brief that may be empty.

    An empty brief is legitimate and is the control the old forge kept for the same reason: a
    book built from no direction at all is what a directed one is read against.
    """
    ask = brief.strip() or "Anything you would most want to read."
    return CompletionRequest(
        prompt=f"What this book is to be about:\n{ask}",
        system=system_for(_TASK, writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=OVERVIEW_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


def render_revision_request(
    brief: str, overview: str, direction: str, writer: Writer | None = None
) -> CompletionRequest:
    """The same writer, the same job, having heard what readers hoped it would be.

    **The direction goes in the prompt rather than the system message**, and that is the one
    thing this does differently from `planner.render_prompt`. §133 measured a wish list rendered
    into a system prompt at 5,476 characters against 2,920 — two thirds of everything the writer
    was told — and the draft that came back serviced it. Here the reader material sits beside
    the thing it is about, where it reads as what people said rather than as the instructions.
    """
    ask = brief.strip() or "Anything you would most want to read."
    return CompletionRequest(
        prompt=(
            f"What this book is to be about:\n{ask}\n\n"
            f"The listing you wrote:\n{overview.strip()}\n\n"
            f"{direction}\n\n"
            "Write the listing again."
        ),
        system=system_for(_TASK, writer),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        profile=REVISION_PROFILE,
        call_class="generation",
        timeout_seconds=600.0,
    )


def render_appetite(hoping_for: tuple[str, ...], dreading: tuple[str, ...]) -> str:
    """What the steering pool said, as the writer reads it. Empty when nobody wanted anything.

    Reported as what readers said, never as an instruction — `readers.Anticipation.render`'s
    rule, and the same reason: the writer decides what to do about it.
    """
    if not hoping_for and not dreading:
        return ""
    blocks = ["READERS WHO SAW THIS LISTING, ASKED WHAT THEY HOPED THE BOOK WOULD BE."]
    if hoping_for:
        blocks.append("Hoping for:\n" + "\n".join(f"- {item}" for item in hoping_for))
    if dreading:
        blocks.append(
            "Would drop it by chapter three for:\n"
            + "\n".join(f"- {item}" for item in dreading)
        )
    return "\n\n".join(blocks)


__all__ = [
    "MAX_OUTPUT_TOKENS",
    "OVERVIEW_PROFILE",
    "REVISION_PROFILE",
    "render_appetite",
    "render_overview_request",
    "render_revision_request",
]
