"""Every role's prompt has a declared size, and no reader-facing rule may speak in schema.

**Why this file exists.** On 2026-08-25 the operator read four generated book listings and
found sentences that meant nothing — *"The rank lands on everyone in the depot in the same
breath"* — and asked the question this suite could not answer: *"why was the text generated in
the first place, what sort of insanity was provided in the generator"*. The answer was that the
listing prompt made **sixteen demands of a hundred-word artifact**, eleven of them rules written
for scene prose, and the model met them by compressing four clauses into one 79-word sentence.

Nobody could have found that by reading the code, because the assembled prompt existed nowhere:
each role built its own by concatenation at call time, and no number anywhere said how big it
had got. That is the shape of every instruction failure this project has had. The rules grow one
well-argued clause at a time, each defensible on its own, and the total is never looked at.

**So the totals are here, and they are ceilings rather than descriptions.** A clause added to
`house` lands in every role that stands on it; when that pushes a role over, the choice is to
take something out or to raise the number here on purpose and say why. Neither of those is
expensive. What was expensive was doing it by accident.

The second half of the file is the leak rail. Reader-facing rules may not contain this system's
own machinery vocabulary, because that has now failed twice in opposite directions: `standing`
reached a drafted chapter (§120), and the reader personas written to catch that kind of leak
were themselves reading for *"what the next rung costs"*, so they scored the jargon as a virtue.
"""

from __future__ import annotations

import pytest

from litharness.application import comprehension, overview, readers, titles, world_agent
from litharness.domain import house
from litharness.domain import writers as writers_domain

#: One writer, fixed, so a budget is about the rules rather than about whose dossier is longest.
WRITER = writers_domain.CAST["ferreira"]


def _roles() -> dict[str, str]:
    """Every assembled system prompt this system actually sends, by the role that sends it."""
    return {
        "listing writer": overview._system(WRITER),
        "title writer": overview.title_system(WRITER),
        "title lookup": titles.render_check_request("a title").system or "",
        "architect seed": world_agent.render_seed_request("a listing", WRITER).system or "",
        "architect grow": (
            world_agent.render_grow_request("prose", logical_id="s1", writer=WRITER).system or ""
        ),
        "scene writer floor": (floor := house.with_house_rules(
            "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
            "no commentary, no summary of what you wrote. The context below is established and "
            "may be relied on; do not contradict it."
        )),
        # **The floor plus who is writing, which was unreachable until 2026-08-25.**
        # `render_prompt` has taken a dossier since 2026-08-20 and `make_plan_selector` had no
        # way to pass one, so the row above was the whole of what a drafter was ever sent. It
        # is a separate row rather than a replacement because `None` is still the default and
        # still the control, and the two totals are four demands apart.
        "scene writer, cast": f"{WRITER.render()}\n\n{floor}",
        "measurement reader": readers.pool(readers.MEASUREMENT)[0].system(),
        "steering reader": readers.pool(readers.STEERING)[0].system(),
        "screen reader": comprehension.READERS[0].system(),
    }


#: **Measured 2026-08-25 and set at what was there**, so this starts as a ratchet rather than as
#: a cut somebody has to justify twice. The listing's nine is the only one that has been through
#: a subtraction: it was sixteen that morning, and the drop from sixteen to nine took the longest
#: sentence in a generated listing from 79 words to 31 and the mean length from 135 to 83.
#:
#: **The listing went 9 -> 10 on 2026-08-25, and the raise is what this file is for.**
#: Removing the house floor from that call to stop the cramming also removed `READER`'s
#: numbers prohibition; number density went from 25.9 per thousand words to 43.2, against
#: 8.0 in the market's own listings. The clause came back as one line and the ceiling moved
#: with it, on purpose and in writing, which is the whole difference from how it left.
#:
#: **A format fact added 2026-08-25 without a raise: it joined an existing line.** A census on
#: `platform_priors.panel`, whose counters were frozen under §104 for a different arm,
#: put six of six market listings at **exactly zero em dashes** against our median of
#: 11.78 per thousand words. The same census found our lyric index at *half* the
#: market's, so this is a punctuation habit and not purple prose.
#:
#: **It brushes a rail and the reasoning is recorded rather than assumed.** `em_dash` is a
#: registered prose axis whose hypothesis is still VOID, and `legal_dossier` refuses any
#: instruction naming it — it rejected a dossier written the same morning. The guard does
#: not fire on a task string, and the claim being made is about an artifact's format, the
#: same kind as "no headings": the axis concerns scene prose measured against reader
#: response, and this is a listing measured against its market. Scoped to the listing for
#: exactly that reason; the scene path keeps the axis untouched.
#:
#: **Every role went up by one on 2026-08-25, for one clause in `house`.** The operator:
#: *"think of progression fantasy/litrpg readers as dragons hoarding gold ... they like to
#: hoard perma abilities and passive effects. Losing words goes against this."*
#: `house.ACCUMULATION` is that, and it is deliberately one sentence: written as three it
#: moved the scene writer from 27 demands to 30 and the Architect from 41 to 44 for a
#: single idea. This table is the only reason anybody saw that before it shipped.
#:
#: **11 -> 12 on 2026-08-25 for the genre's own nouns**, which is the largest gap measured
#: that day: ten market listings average 3.8 of them each (magic, monsters, system, reborn,
#: heroes) and eight of ours contained one between them. Nothing forbade them; the model was
#: avoiding them unprompted.
#:
#: **12 -> 13 for second person as a format fact.** Second-person-as-protagonist is 0 of 10
#: in the market and was two or three of eight in every round of ours. The numbers clause
#: was reworded in the same commit and cost nothing: its affirmative permission ("only
#: where the world itself counts it") was licensing floor ninety and eight ranks of nine,
#: and prohibition-only is both shorter and what the standing constraint in `house` says.
#:
#: The Architect's forty-two is the largest and is not yet defended by anything. It is the whole
#: house floor plus its own tool essay, and no measurement says which half it needs.
#:
#: **Two roles joined the table on 2026-08-25 without changing: they were already being sent
#: and had no ceiling.** `_roles()` is what this file measures, and a role assembled only
#: inside its own call site is one nobody can see the size of — which is the exact failure
#: recorded at the top of this file, one level down. `overview.title_system` was extracted for
#: no other purpose than to be countable here. Ten is four demands of dossier plus six of job;
#: the lookup's six carry no dossier because that role writes nothing.
BUDGET: dict[str, int] = {
    "title writer": 10,
    "title lookup": 6,
    "listing writer": 14,
    "architect seed": 42,
    "architect grow": 42,
    "scene writer floor": 28,
    "scene writer, cast": 32,
    "measurement reader": 4,
    "steering reader": 4,
    "screen reader": 5,
}

#: The floor everything else inherits. Broken out because a clause added here is added to every
#: role at once, which is exactly how the scene writer reached twenty-seven without a decision.
HOUSE_BUDGET = 25


@pytest.mark.parametrize("role", sorted(BUDGET))
def test_a_role_prompt_stays_inside_its_declared_budget(role: str) -> None:
    """No role grows without somebody choosing to let it.

    The failure this refuses is not a large prompt. It is a large prompt nobody decided on: every
    clause in the sixteen that broke the listing was added deliberately and none of the sixteen
    was.
    """
    text = _roles()[role]
    counted = house.demands(text)
    assert len(counted) <= BUDGET[role], (
        f"{role} now makes {len(counted)} demands against a budget of {BUDGET[role]}. "
        f"Take one out, or raise the budget here and say why. The last three added to a "
        f"hundred-word listing cost it a 79-word sentence.\n"
        + "\n".join(f"  {index + 1:2d}. {item}" for index, item in enumerate(counted))
    )


def test_the_house_floor_is_the_thing_that_grows_everywhere_at_once() -> None:
    """`house` has no call site of its own and reaches every role that has one."""
    counted = house.demands(house.HOUSE_RULES)
    assert len(counted) <= HOUSE_BUDGET, (
        f"the house floor now makes {len(counted)} demands against {HOUSE_BUDGET}, and every "
        "role that stands on it just grew by the same amount"
    )


#: Roles whose prompts shape prose a reader will read. The exemptions are the two kinds of call
#: that must name the machinery to work at all: a schema-filling call has to name the fields it
#: fills, and the Architect's tool essay has to name the commands it runs.
#:
#: **`title lookup` is not here, and the boundary is the one `house` already states**: what the
#: text shapes, not where it lives. That role reports what other people have published and
#: shapes no word a reader of this book will read. `title writer` shapes the few words above
#: the blurb, so it is.
READER_FACING = (
    "listing writer",
    "title writer",
    "measurement reader",
    "steering reader",
    "screen reader",
)


@pytest.mark.parametrize("role", READER_FACING)
def test_a_reader_facing_prompt_never_speaks_in_this_system_s_own_vocabulary(role: str) -> None:
    """The words this repository uses for its own machinery stay out of reader-facing text.

    **Both directions have failed.** §120 measured `standing` reaching a chapter as *"hotter than
    a girl at her standing should be able to manage"*. And the reader personas built to catch
    that were written to read for *"a climb with rules — what the next rung costs"*, so they
    rewarded the register they existed to detect; four listings scored well while using it, and
    the operator's reading was that something was seriously wrong with the readers.
    """
    text = _roles()[role].lower()
    found = sorted(word for word in house.MACHINERY_WORDS if word in text)
    assert not found, (
        f"{role} speaks this system's own vocabulary: {found}. A rule that shapes prose a "
        "reader will read may not name the machinery; a schema call and a tool essay may, and "
        "those are not in READER_FACING."
    )


def test_the_house_floor_itself_is_reader_facing() -> None:
    """It reaches every one of them, so it is held to the same rail."""
    found = sorted(word for word in house.MACHINERY_WORDS if word in house.HOUSE_RULES.lower())
    assert not found, f"the house floor speaks this system's own vocabulary: {found}"
