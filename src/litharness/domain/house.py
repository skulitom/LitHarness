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

# Reader orientation and viewpoint knowledge support sentence-level clarity.
CLARITY = (
    "Every sentence can be followed the first time it is read.\n"
    "Establish where the viewpoint character is and who the relevant people are to them; "
    "make spatial relationships clear before an action depends on them.\n"
    "Give unfamiliar names and terms enough context to grasp their meaning in the scene, "
    "including a brief explanation when needed.\n"
    "Let the reader follow what the viewpoint character notices, knows and believes, "
    "including uncertainty, before a choice depends on it.\n"
    "Keep the order of events and the connections between them clear.\n"
    "Use clear references so the reader knows who perceives or acts and what changes."
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
    "Emotions and assumptions shape what the viewpoint character notices, expects and "
    "chooses. Make room for the relationships, places and concerns that give those choices "
    "meaning; a passage can establish these without advancing an external event.\n"
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
