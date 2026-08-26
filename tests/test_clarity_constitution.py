"""The clarity constitution, enforced by construction rather than by review.

`plan/stage-0-decisions.md` §125/§129: `domain/house.py`'s CLARITY rule outranks every
other writing instruction, and anything in the generation path that tells a model to withhold
explanation is deleted entirely. Boundary 2: non-contradiction is not a review finding, it is
a property this file pins — every active instruction string that reaches a model in the
generation path is collected and checked against the contradiction class's vocabulary.
"""

from __future__ import annotations

import json

from litharness.application import outline, world_agent
from litharness.domain import house, world_brief
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.promises import Promise
from litharness.domain.revision import new_book
from litharness.domain.writers import CAST
from tests.conftest import BOOK_ID, BRANCH_ID

#: The contradiction class's vocabulary, matched case-insensitively over every instruction
#: string the generation path renders. Additions are welcome — a new way of telling a model
#: to withhold belongs here the day somebody notices it. Removals need the ledger: taking a
#: pattern off this list re-opens a channel `plan/stage-0-decisions.md` §125 closed,
#: and only a stage-0 entry may record that.
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

    The collection covers the Architect's seed and grow prompts, the planner's world and
    ladder rules, the outline call's rendered rule list, its protagonist rule, and the house
    rules themselves. A string that tells a model to withhold — never explain, stay mysterious,
    keep vocabulary off the page — contradicts CLARITY and may not exist here.
    """
    writer = CAST["ferreira"]
    strings: list[str] = [
        world_agent.render_seed_request("a listing", writer).system or "",
        world_agent.render_grow_request(
            "a chapter", logical_id="s1", writer=writer
        ).system
        or "",
        *world_brief.WORLD_RULES,
        *world_brief.LADDER_RULES,
        *outline.PROTAGONIST_RULES,
        *_outline_rules(),
        house.HOUSE_RULES,
    ]
    assert len(strings) > 15, "the collection shrank; something stopped being collected"
    for text in strings:
        lowered = text.lower()
        for pattern in WITHHOLD_PATTERNS:
            assert pattern not in lowered, (pattern, text)
