"""Stage-0 §174: the readership reaches the call that chooses the person, and it goes alone.

**The direction.** The operator, 2026-08-23, on two forged premises whose protagonists were a
51-year-old optician and a veteran veterinary nurse: the audience is young and a protagonist's
pre-story life has to be one that audience has lived. Read 10 (2026-08-30) failed a book on the
same axis from the other side — a village mender already settled at her craft. The two are one
property: **the person does not arrive already good at what the book will ask of them.**

**Why this file exists rather than a clause review.** The direction was not missing. It was live
prompt text in `house.READER` for a week, and it failed three ways at once — a permission
enumerating three instances of what succeeds, a conditional false for anybody native to the
book's own world, and a subject every role standing on the floor receives already fixed by the
listing (§154). The listing is the one role that does not stand on the floor, so the single call
that decides who a book's person is was the single call the direction never reached. Each of the
three is asserted below, because a clause that comes back wearing any one of them is the same
failure again.

**The demographic is the half that may not travel.** An audience is a targeting decision and
belongs in `PLAN.md` and the ledger; what a prompt may carry is the structural consequence.
`test_no_prompt_this_system_sends_names_the_readership_by_demographic` is the rail, and it is
deliberately tiny: four words, aimed at one failure that actually happened, not a lexicon.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import re

import pytest

from litharness.application import overview, readers
from litharness.domain import house
from litharness.domain import writers as writers_domain

#: The demand §174 added, held by its operative words so a later rewording of its cost half does
#: not have to edit an assertion about the whole sentence.
_PRIOR_LIFE = "did not spend the years before the book mastering one trade"

#: The ban this clause is placed *away* from and depends on: it keeps the biography off the page,
#: which is what stops a constraint on the prior life being answered by narrating one. §154
#: narrowed it to the prior life after five listings of eight opened on a mundane job.
_BIOGRAPHY_BAN = "not the life whoever this happens to had before it began"

#: What the removed clause enumerated. Held verbatim rather than paraphrased: this is a
#: regression guard against that exact text returning, not a list of words nobody may write.
_ENUMERATED = (
    "a degree they are not using",
    "a job that covers the rent",
    "for no professional reason",
)

#: The conditional that made the clause silent in the case it was written for. A protagonist
#: native to the book's own world never satisfies it.
_CONDITIONAL = "came from somewhere like our own world"

#: Prompt text this system sends that shapes prose a reader will read. `overview._TASK` is not
#: assembled through `house.with_house_rules`, which is the fact the whole entry turns on, so it
#: is listed here by hand rather than derived from the floor.
def _reader_facing() -> dict[str, str]:
    return {
        "house floor": house.HOUSE_RULES,
        "listing task": overview._TASK,
        "title task": overview._TITLE_TASK,
        "measurement reader": readers.pool(readers.MEASUREMENT)[0].system(),
        "steering reader": readers.pool(readers.STEERING)[0].system(),
    }


def _clause() -> str:
    (found,) = [item for item in house.demands(overview._TASK) if _PRIOR_LIFE in item]
    return found


def test_the_prior_life_constraint_is_one_demand_of_the_listing_task() -> None:
    """One sentence, one demand, and the ceiling that paid for it knows about it.

    `house.demands` splits on sentences and line breaks, so a clause written as two lands as two
    and a ceiling raised for one would be short by one. `tests/test_prompt_budget.py` is where
    the raise is argued; this is what says the raise bought what it was argued for.
    """
    assert _clause()


def test_the_prior_life_constraint_is_prohibition_signed() -> None:
    """§138's finding, applied to the clause that motivated re-reading it.

    A permission is what comes back and a prohibition is what stops. The removed version was
    permission-signed and enumerated three lives that succeed; this one names a history that
    fails and offers nothing to reach for.
    """
    clause = _clause()
    assert clause.startswith("Whoever this happens to did not spend")
    for instance in _ENUMERATED:
        assert instance not in clause


def test_the_prior_life_constraint_carries_no_conditional_that_excludes_a_native_protagonist(
) -> None:
    """The failure read 10 found, pinned so a later edit cannot reintroduce it.

    The removed clause was guarded by *"if the person came from somewhere like our own world"*,
    which is false for a protagonist born in the book's own world — the exact premise the
    direction was written against. The constraint holds whatever world the person came from.
    """
    assert _CONDITIONAL not in overview._TASK
    assert "if " not in _clause().lower()


def test_the_constraint_lives_at_the_call_that_chooses_the_person_and_nowhere_else() -> None:
    """One rule, one home, and the home is the altitude where the property is decided.

    Everything downstream of the listing receives the person already named by it, so a rule about
    who they were lands there with its sign multiplied by zero (§154). The house floor is every
    one of those roles at once, which is why the clause is gone from it.
    """
    assert _PRIOR_LIFE in overview._system(writers_domain.CAST["ferreira"])
    assert _PRIOR_LIFE not in house.HOUSE_RULES
    for instance in (*_ENUMERATED, _CONDITIONAL):
        assert instance not in house.HOUSE_RULES


def test_the_listing_still_keeps_the_biography_off_the_page() -> None:
    """The demand this one leans on, and dropping it would turn this one into a licence.

    A constraint on the years before the book, standing beside no ban on narrating them, is
    answered by narrating them — which is the mundane-job opening §154 narrowed this ban to
    stop. The two are a pair and this is what says so.
    """
    assert _BIOGRAPHY_BAN in overview._TASK


@pytest.mark.parametrize("word", ("male", "female", "twenties", "demographic"))
def test_no_prompt_this_system_sends_names_the_readership_by_demographic(word: str) -> None:
    """Who the audience is decides what gets written; it is not a thing to write.

    The audience is stated in `PLAN.md` and in the ledger and moves by operator direction alone
    (§126). A prompt saying it out loud is a targeting decision arriving in every book as an
    instruction, and it was one until 2026-08-30.
    """
    pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
    named = sorted(role for role, text in _reader_facing().items() if pattern.search(text))
    assert not named, (
        f"{named} name the readership by demographic. What a prompt may carry is the structural "
        "consequence — who the person is not — and never who is reading."
    )
