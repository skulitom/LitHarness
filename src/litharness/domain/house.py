"""Shared writing instructions and stable prompt assembly helpers.

CLARITY governs comprehension; READER governs scene purpose and the opening's
offer; ACCUMULATION carries the direction that acquired abilities are kept.
QUANTITY_DETAIL also reaches invention before incidental precision becomes source
material. These are author directions, not validated measures of literary quality.

Keep shared wording here and choose its scope at the call site. Sentence revision
uses the clarity floor because it cannot change the story's contents. Listings
have separate tasks in application/overview.py. Sentence-register rules removed
from this floor are recorded in plan/stage-0-decisions.md, section 187.

When changing a shared rule, inspect the clauses counted by demands and the writing
action each addresses. Do not enumerate successful story content as a formula.
tests/test_prompt_budget.py guards prompt growth and internal-vocabulary leakage;
the decision ledger preserves the experiments and reversals behind these choices.
"""

from __future__ import annotations

# Following unfamiliar material does not require explaining every term.
CLARITY = (
    "Clarity is the floor, and it is about following rather than about explaining. Every "
    "sentence can be followed the first time it is read.\n"
    "A term the reader has not met needs a reason to be there before it needs anything "
    "else, and then a consequence rather than a definition: the sentence carrying it says "
    "what it does to somebody. What fails is a name invented because the world wanted one "
    "and handed over to be carried while it buys the reader nothing, and the test is "
    "whether they could say what it changes for the person it happens to.\n"
    "A sentence a reader can take two ways has failed, and the writer is the last person who "
    "can see it: `a sheet of directions in his brother's small hand` is handwriting to whoever "
    "wrote it and a hand inside the box to whoever reads it. Prefer the reading nobody can "
    "trip on.\n"
    "Objects act or speak when the story gives them that literal capability. Otherwise, "
    "keep figurative descriptions clear about who perceives or acts.\n"
    "A paragraph holds together or it is not a paragraph. Inside one, a pronoun points at one "
    "person or object only — where two are in play, use their names, however plain that reads. "
    "A reader who has to reread a paragraph to find out whose brother died has been thrown out "
    "of the book, and the sentences were all fine."
)


# Shared precision policy for invention and prose; stage-0 decision 244.
QUANTITY_DETAIL = (
    "Use relative scale and duration for ordinary description. Give an exact quantity "
    "only when a character must compare, spend or act against that value, or a required "
    "system display gives it; do not manufacture a calculation or countdown to justify "
    "incidental detail, treat a number in a plan as an instruction to narrate it, or "
    "change established values and their arithmetic when leaving a quantity unspoken."
)

# Scene purpose and the magical progression offer, not a scene-to-summary rule.
READER = (
    "Detail that only establishes "
    "who somebody is — the steps of a job, the order of a routine — is not why the reader "
    "came. What fails is a passage that settles nothing in the scene it sits in, however "
    "much it establishes. Every scene moves the thing the book is about closer or further "
    "away.\n"
    "The opening shows what this book is offering: something a person could come to be able to "
    "do, and somewhere the reader has not been. A reader who reaches the end of the opening "
    "scene without seeing either has been given no reason to start another.\n"
    "The reader is measuring themselves against the offer, and that is the whole of why they "
    "are here. A power with one use invites nobody in, and neither does one the reader meets "
    "as a summary of what it could be rather than on the page. A story that names its own "
    f"ceiling has told the reader where to stop.\n{QUANTITY_DETAIL}"
)

# The retained-capability direction is separate from scene comprehension.
ACCUMULATION = (
    "A power that is spent, used up or traded away costs the reader the thing they came "
    "for: what this genre's reader collects is what the person KEEPS."
)

# Stable separators are part of the assembled prompt.
HOUSE_RULES = f"{CLARITY}\n\n{READER}\n\n{ACCUMULATION}"


# Internal vocabulary excluded from prose-shaping instructions by prompt-budget tests.
# Schema-filling and tool-teaching prompts must still be able to name their fields.
MACHINERY_WORDS: frozenset[str] = frozenset(
    {
        "rung",
        "rungs",
        "ladder",
        "standing",
        "criterion",
        "criteria",
        "manifests_as",
        "cardinality",
        "order_key",
        "logical_id",
        "predicate",
        "object_ref",
        "story_position",
        "reveal_scene",
        "entity_role",
        "graph_line",
        "packet",
        "canon",
    }
)


def demands(text: str) -> tuple[str, ...]:
    """Split instruction text at line breaks and sentence-ending punctuation.

    This deliberately simple counter guards prompt budgets; it is not a semantic
    measure of instruction complexity. Empty pieces are discarded.
    """
    import re

    return tuple(
        part.strip()
        for line in text.split("\n")
        for part in re.split(r"(?<=[.!?])\s+", line)
        if part.strip()
    )

def with_house_rules(system: str) -> str:
    """Append all shared rules, or return them alone for an empty system.

    Centralized spacing keeps prompt bytes stable for content-addressed replay.
    """
    body = system.strip()
    return f"{body}\n\n{HOUSE_RULES}" if body else HOUSE_RULES


def with_clarity_floor(system: str) -> str:
    """Append only CLARITY for a rewrite that cannot change story contents.

    READER and ACCUMULATION would ask that role to change facts outside its remit.
    The distinct helper makes the chosen scope visible at each call site and uses
    the same spacing as with_house_rules.
    """
    body = system.strip()
    return f"{body}\n\n{CLARITY}" if body else CLARITY
