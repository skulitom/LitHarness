"""Stage-0 §168: the economy block's unit, and the sentence that paid for it.

**The defect this file exists for was not a rule being broken.** Read 9 named 252 of one
scene's 943 words spent, across three speakers, on an object the text itself rules
inconsequential, before that scene's first story move. Every demand in the assembled prompt
was satisfied while it happened, and the two that could have caught it could not: the
compression demand's object is detail that establishes *who somebody is*, and a staged
handover of a fact is not that, while the movement demand's unit is the whole scene, and that
scene moved. A gap between an object and a unit is a gap no enforcement can close, which is
why the repair is a demand rather than a gate.

Three things are asserted, and they fail for three different reasons.

**The unit.** `test_the_economy_block_has_a_demand_whose_unit_is_smaller_than_a_scene` is the
one to read: without it the block is satisfiable by a scene that moves and spends a quarter of
itself on nothing.

**The boundary.** The clause reaches what a passage settles, never whether it was dramatised.
`planner`'s criterion block forbids a narrator reporting a change the reader was never shown,
and the length ask says the scene has room to play out in real time; a clause against staging
would contradict both. §163 removed a truth-keyed removal test from this same clause for
exactly that reason, and `test_the_clause_does_not_reintroduce_a_truth_keyed_removal_test`
stops it coming back by the door §168 opened.

**The price.** The new demand was paid for by subtracting an affirmative whose object was a
reader state (§154), not by raising a ceiling. `tests/test_prompt_budget.py` owns the number;
this file owns the shape that keeps it true.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import pytest

from litharness.application import planner
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house

#: The demand §168 added, held here by its operative words rather than whole, so a later
#: re-scope of its object does not have to edit an assertion about its punctuation.
_PASSAGE_UNIT = "a passage that settles nothing in the scene it sits in"

#: The sentence §168 removed to pay for it. Affirmative, and its object was what a reader
#: wants — the shape §154 measured landing with its sign multiplied by zero.
_THE_SUBTRACTED_AFFIRMATIVE = "Spend the words on what the reader opened this book for."


def test_the_economy_block_has_a_demand_whose_unit_is_smaller_than_a_scene() -> None:
    """The gap read 9 fell through, closed at the altitude it was measured at.

    The movement demand is kept — §163 established that it is what sorts detail now, in place
    of the truth test it replaced — so this asserts both: the scene-unit criterion survives,
    and a passage-unit prohibition now sits beside it.
    """
    demands = house.demands(house.READER)
    (passage,) = [item for item in demands if _PASSAGE_UNIT in item]
    assert passage.startswith("What fails is")
    assert any("Every scene moves the thing the book is about" in item for item in demands)


def test_the_new_demand_is_a_prohibition_and_names_a_thing_a_writer_puts_on_a_page() -> None:
    """`house`'s standing constraint and §154's second axis, applied to §168 before it ships.

    A rule here may say what fails and may not enumerate what succeeds, and a demand whose
    object is a reader state has no addressee. This clause fails a passage — a thing a writer
    emits and can emit fewer of — and names no state of anybody's mind.
    """
    (passage,) = [item for item in house.demands(house.READER) if _PASSAGE_UNIT in item]
    assert passage.startswith("What fails is")
    for reader_state in ("wants", "wondering", "feels", "invites", "excited", "why the reader"):
        assert reader_state not in passage.lower()


def test_the_clause_does_not_reintroduce_a_truth_keyed_removal_test() -> None:
    """§163's correction, and §168 is the first edit since that could have undone it.

    The removed half read *"if the events would be equally true with those specifics removed,
    remove them"*, and it deletes presence by construction: dramatisation is the specifics
    that leave the events equally true. §168's test is what the scene settles, which is a
    question about consequence rather than about truth, so neither the removed clause nor its
    vocabulary may reappear.
    """
    assert "equally true" not in house.READER
    assert "a line rather than a scene" not in house.READER
    (passage,) = [item for item in house.demands(house.READER) if _PASSAGE_UNIT in item]
    for removal in ("remove", "cut", "shorter", "trim", "equally true"):
        assert removal not in passage.lower()


def test_the_clause_reaches_what_a_passage_settles_and_never_whether_it_was_staged() -> None:
    """The boundary that keeps §168 from contradicting two demands already in the prompt.

    `planner`'s criterion block forbids a narrator reporting a change the reader was never
    shown, and the length ask says the scene plays out in real time. A prohibition on staging
    established material would contradict both at once, which is how §163's removed half
    failed. The concession is what carries the boundary: establishing is named insufficient
    rather than forbidden.
    """
    (passage,) = [item for item in house.demands(house.READER) if _PASSAGE_UNIT in item]
    assert "however much it establishes" in passage
    for staging in ("staged", "dramatis", "dramatiz", "scene rather than", "in summary"):
        assert staging not in passage.lower()


def test_the_new_demand_was_paid_for_and_not_added() -> None:
    """§161.5's demand-neutrality discipline, at a third use.

    The subtracted sentence's content survives in the two demands that follow it, both
    correctly signed and both addressable, so what went was a topic sentence for rules that
    no longer needed one. `tests/test_prompt_budget.py` owns the ceiling; this owns the shape
    the ceiling is measuring.

    **The two counts moved 11 -> 12 and 24 -> 25 on 2026-08-29 for §171**, which added the
    narrating-the-inference prohibition and paid for it at the budget file by raising one
    ceiling on purpose. What this test asserts is unchanged and is about §168: its own demand
    arrived free, and the sentence it removed has not come back. The counts are updated rather
    than loosened, because a `<=` here would stop the file noticing the next silent growth.

    **The floor moved 25 -> 26 on 2026-08-30 for §176**, a figure-clarity prohibition added to
    `house.CLARITY` and paid for at six ceilings. `house.READER` is untouched by it, which is
    why only the second count moves: this file's subject is the economy block, and a clause on
    the clarity floor lands beside it rather than in it.
    """
    assert _THE_SUBTRACTED_AFFIRMATIVE not in house.READER
    assert "Spend the words on" not in house.READER
    assert len(house.demands(house.READER)) == 12
    assert len(house.demands(house.HOUSE_RULES)) == 26


def test_the_new_demand_carries_no_instance_list() -> None:
    """Three clauses in this module were cut for being recited, and each was an instance list.

    §168 ships without one deliberately: the failure it names is a configuration rather than a
    vocabulary, and an invented instance is the shape that came back as a formula five listings
    out of eight.
    """
    (passage,) = [item for item in house.demands(house.READER) if _PASSAGE_UNIT in item]
    assert "—" not in passage
    assert ":" not in passage
    assert passage.count(",") <= 1


@pytest.mark.parametrize(
    "word",
    ("kettle", "dent", "patch", "ashfen", "mender", "supper", "superfocused", "details"),
)
def test_no_word_of_the_read_9_chapter_became_prompt_text(word: str) -> None:
    """§97.1, mechanically, on the read that produced this entry.

    Named for its own read rather than reusing `test_page_contract.py`'s wording, which §166
    cites for a different chapter: one ledger citation, one test.

    A defect harvest is the operator's side of the loop. A noun lifted out of the chapter under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright.
    """
    assert word not in house.READER.lower()


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_edited_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §168's one clause."""
    (passage,) = [item for item in house.demands(house.READER) if _PASSAGE_UNIT in item]
    assert word not in passage.lower()


def test_the_demand_rides_the_scene_writers_live_assembled_prompt() -> None:
    """The clause is worth nothing if it reaches a constant and not a call.

    `render_prompt` is the path every drafted scene goes through, and the house floor arrives
    on it through `with_house_rules`. Asserted against the live assembly rather than against
    `HOUSE_RULES`, because a copy is the failure `test_prompt_budget` was founded on.
    """
    system, _prompt = planner.render_prompt(
        beats_domain.Beat(
            logical_id="s1",
            ordinal=1,
            of_total=1,
            title=None,
            function="setup",
            template_id=beats_domain.SIX_BEAT.template_id,
        ),
        book_title=None,
        packet=context_domain.ContextPacket(
            query_id="scene-economy",
            target_logical_id="s1",
            book_id="book",
            branch_id="main",
            base_revision_id="r0",
        ),
    )
    assert _PASSAGE_UNIT in system
    assert _THE_SUBTRACTED_AFFIRMATIVE not in system
