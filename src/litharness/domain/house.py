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
_CLARITY_CONTEXT = (
    "Every sentence can be followed the first time it is read.\n"
    "Establish where the viewpoint character is and who the relevant people are to them; "
    "make spatial relationships clear before an action depends on them.\n"
    "Give unfamiliar names and terms enough context to grasp their meaning in the scene, "
    "including a brief explanation when needed.\n"
)
_GENERAL_ACCESS = (
    "Let the reader follow what the viewpoint character notices, knows and believes, "
    "including uncertainty, before a choice depends on it.\n"
    "Keep the order of events and the connections between them clear."
)
_PERCEPTUAL_ACCESS = (
    "Keep narration within what the viewpoint character can perceive from their position, "
    "remember or infer; other minds and unseen events remain inferred or reported.\n"
    "Connect new information through what draws or redirects their attention, leaving "
    "routine glances and movements implicit when easy to follow."
)
_CLARITY_REFERENCES = (
    "Use clear references so the reader knows who perceives or acts and what changes."
)
CLARITY = f"{_CLARITY_CONTEXT}{_GENERAL_ACCESS}\n{_CLARITY_REFERENCES}"
SCENE_CLARITY = f"{_CLARITY_CONTEXT}{_PERCEPTUAL_ACCESS}\n{_CLARITY_REFERENCES}"


# Shared precision policy for invention and prose; stage-0 decision 244.
QUANTITY_DETAIL = (
    "Use relative scale and duration for ordinary description. Give an exact quantity "
    "only when a character must compare, spend or act against that value, or a required "
    "system display gives it; do not manufacture a calculation or countdown to justify "
    "incidental detail, treat a number in a plan as an instruction to narrate it, or "
    "change established values and their arithmetic when leaving a quantity unspoken."
)

# Character attention remains relevant after the opening's genre offer is established.
_SCENE_ATTENTION = (
    "Emotions and assumptions shape what the viewpoint character notices, expects and "
    "chooses. Make room for the relationships, places and concerns that give those choices "
    "meaning; a passage can establish these without advancing an external event."
)
OPENING_OFFER = (
    "The opening shows what this book is offering: something a person could come to be able to "
    "do, and somewhere the reader has not been. A reader who reaches the end of the opening "
    "scene without seeing either has been given no reason to start another."
)
_MAGICAL_OFFER = (
    "The reader is measuring themselves against the offer, and that is the whole of why they "
    "are here. A power with one use invites nobody in, and neither does one the reader meets "
    "as a summary of what it could be rather than on the page. A story that names its own "
    f"ceiling has told the reader where to stop.\n{QUANTITY_DETAIL}"
)
READER = f"{_SCENE_ATTENTION}\n{OPENING_OFFER}\n{_MAGICAL_OFFER}"

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

def with_house_rules(
    system: str, *, opening: bool = True, limited_viewpoint: bool = False,
) -> str:
    """Append shared rules within the requested drafting scope.

    Default callers and opening drafts retain the complete block. Continuations keep
    comprehension, character attention and quantity guidance; the book's own mechanics
    and author directions reach drafting separately from general genre appeals.
    Named-viewpoint drafting uses perceptual access in place of general event clarity;
    planning, world building and content-preserving revision retain their existing scope.
    """
    body = system.strip()
    clarity = SCENE_CLARITY if limited_viewpoint else CLARITY
    rules = f"{clarity}\n\n{READER}\n\n{ACCUMULATION}" if opening else (
        f"{clarity}\n\n{_SCENE_ATTENTION}\n{QUANTITY_DETAIL}"
    )
    return f"{body}\n\n{rules}" if body else rules


def with_clarity_floor(system: str) -> str:
    """Append only CLARITY for a rewrite that cannot change story contents.

    READER and ACCUMULATION would ask that role to change facts outside its remit.
    The distinct helper makes the chosen scope visible at each call site and uses
    the same spacing as with_house_rules.
    """
    body = system.strip()
    return f"{body}\n\n{CLARITY}" if body else CLARITY
