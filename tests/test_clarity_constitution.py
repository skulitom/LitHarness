"""The clarity constitution, enforced by construction rather than by review.

`plan/handoff-clarity-first.md` boundary 1: `domain/house.py`'s CLARITY rule outranks every
other writing instruction, and anything in the generation path that tells a model to withhold
explanation is deleted entirely. Boundary 2: non-contradiction is not a review finding, it is
a property this file pins — every instruction string that reaches a model in the generation
path is collected and checked against the contradiction class's vocabulary, so a never-explain
that gets written again fails here before it reaches a forge. The rows this construction test
stands over are `plan/clarity-audit-2026-08-24.md`'s: C1 to C6 deleted the written instances,
C2 closed the forge's `tone_note` channel (the one that minted new members at run time) and
routed the surviving directive kinds through `directors.legal_brief`, so a forge-authored
directive faces the same legality rail a Director-authored one does — and a refusal is named
in the report, never silent.
"""

from __future__ import annotations

import json
from typing import Any

from litharness.application import architect, comprehension, outline
from litharness.domain import house, world_brief
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.promises import Promise
from litharness.domain.revision import new_book
from tests.conftest import BOOK_ID, BRANCH_ID

#: The contradiction class's vocabulary, matched case-insensitively over every instruction
#: string the generation path renders. Additions are welcome — a new way of telling a model
#: to withhold belongs here the day somebody notices it. Removals need the ledger: taking a
#: pattern off this list re-opens a channel `plan/handoff-clarity-first.md` boundary 1
#: closed, and only a stage-0 entry may record that.
WITHHOLD_PATTERNS: tuple[str, ...] = (
    "never explain",
    "is never explained",
    "never an explanation",
    "do not explain",
    "don't explain",
    "stay mysterious",
    "never reaches the page",
    "never define",
    "do not define",
)


def _descriptions(node: Any) -> list[str]:
    """Every `description` string in a JSON-schema tree, depth first."""
    found: list[str] = []
    if isinstance(node, dict):
        value = node.get("description")
        if isinstance(value, str):
            found.append(value)
        for item in node.values():
            found.extend(_descriptions(item))
    elif isinstance(node, list):
        for item in node:
            found.extend(_descriptions(item))
    return found


def _outline_rules() -> list[str]:
    """The rule list one rendered outline request carries, milestone and payoff lanes included.

    Rendered rather than read off a constant because the milestone and payoff rules are
    written inline in `render_outline_request`: a seed makes the milestone lane render (where
    C6's deleted debt-story frame lived) and an open promise makes the payoff lane render.
    The world and ladder lanes draw from `world_brief.WORLD_RULES` and
    `world_brief.LADDER_RULES`, which the caller collects as constants.
    """
    beats = beats_for(new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8), arc_template(8))

    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    owed = Promise(
        promise_id="p1",
        subject="the tide",
        description="what is the tide actually aimed at",
        opened_at_key="s1",
        due_key="s8",
        opened_by_revision="rev-1",
    )
    request = outline.render_outline_request(
        "A junior appraiser can read a made thing's history by touch.",
        beats,
        base=_Base(),  # type: ignore[arg-type]
        seed={"gold": 5},
        promises=(owed,),
    )
    rules = json.loads(request.prompt)["rules"]
    assert any("milestones" in rule for rule in rules), "the milestone lane did not render"
    assert any("payoff_windows" in rule for rule in rules), "the payoff lane did not render"
    return list(rules)


def test_no_generation_instruction_tells_a_model_to_withhold_explanation() -> None:
    """Boundary 1, over every instruction string the generation path renders.

    The collection is the audit's: the Architect's rules, its two shape rules and its system
    message, every description its world schema carries, the planner's world and ladder rules,
    the outline call's rendered rule list (all lanes) and its protagonist rule, and the house
    rules themselves. A string that tells a model to withhold — never explain, stay
    mysterious, keep vocabulary off the page — contradicts CLARITY and may not exist here.

    **The premise call and the comprehension screen joined the collection on 2026-08-24**, with
    the two stages they added to a forge (`plan/handoff-clarity-remaining.md` T3, T4). The
    premise ask is the one prompt in this system that writes what a reader will actually read,
    so a withhold instruction there would be the worst-placed one in the repository; the
    readers' systems and their answer schema are model-facing strings in the generation path
    and are collected for the same reason everything else here is.
    """
    strings: list[str] = [
        *architect._RULES,
        architect._DISTINCTNESS_RULE,
        architect._DOMAIN_FIRST_RULE,
        architect._SYSTEM_MESSAGE,
        architect._PREMISE_SYSTEM,
        architect._PREMISE_ASK,
        *_descriptions(architect.WORLDS_SCHEMA),
        *(reader.system() for reader in comprehension.READERS),
        comprehension._ASK,
        *_descriptions(comprehension.ANSWER_SCHEMA),
        *world_brief.WORLD_RULES,
        *world_brief.LADDER_RULES,
        *outline.PROTAGONIST_RULES,
        *_outline_rules(),
        house.HOUSE_RULES,
    ]
    assert len(strings) > 30, "the collection shrank; something stopped being collected"
    for text in strings:
        lowered = text.lower()
        for pattern in WITHHOLD_PATTERNS:
            assert pattern not in lowered, (pattern, text)


def test_the_forge_cannot_emit_a_tone_note() -> None:
    """C2's first half: the run-time minting channel is closed at the schema and at the lane.

    The 2026-08-24 forges emitted "Never explain how any of it works" as a `tone_note` —
    craft doctrine contradicting CLARITY, arriving through a kind no legality rail read. The
    kind is gone from the forge schema, and a stored answer that still carries one (live
    databases are history and are not edited) is dropped by `directives_for`.
    """
    directive = architect.WORLDS_SCHEMA["properties"]["worlds"]["items"]["properties"][
        "directives"
    ]["items"]
    assert "tone_note" not in directive["properties"]["kind"]["enum"]

    candidate = architect.Candidate(
        0,
        {
            "directives": [
                {"kind": "tone_note", "text": "Never explain how any of it works."},
                {"kind": "constraint", "text": "Every reading costs the minutes it takes."},
            ]
        },
    )
    carried = architect.directives_for(candidate)
    assert [entry["kind"] for entry in carried] == ["constraint"]


def test_a_forge_directive_carrying_craft_doctrine_is_refused() -> None:
    """C2's second half: the surviving kinds pass `legal_brief`, and a refusal is named.

    A forge `constraint` is a world fact stated as a standing rule; prose doctrine wearing
    that kind faces the same rail a Director's brief does. The refusal is not silent — the
    report names each dropped entry as `kind: reason`, so a forge that had a directive
    refused shows it.
    """
    candidate = architect.Candidate(
        0,
        {
            "directives": [
                {"kind": "constraint", "text": "avoid em dashes"},
                {"kind": "constraint", "text": "Every reading costs the minutes it takes."},
            ]
        },
    )
    carried = architect.directives_for(candidate)
    assert [entry["text"] for entry in carried] == [
        "Every reading costs the minutes it takes."
    ]

    report = architect.report(candidate, scenes=8)
    [refused] = report["directives_refused"]
    assert refused.startswith("constraint: ")
    assert "em_dash" in refused
