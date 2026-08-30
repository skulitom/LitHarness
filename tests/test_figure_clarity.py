"""Stage-0 §176: the figure-clarity clause, the scope word beside it, and what neither reaches.

**The defect this file exists for was not a rule being broken.** Read 10 named three sentences
in one chapter as ones nobody would say: a pronoun whose nearest noun is not the thing it stands
for, a comparison to something that does not have the quality it is made for, and a line of
dialogue naming an object by a description last given a passage earlier. Every demand in
`house.CLARITY` was read against them first, and each missed by its object — the unmet-term
clause fails a *name*, the two-ways clause fails a sentence with two readings *available*, the
object clause fails an object *acting*. What was left were the two sentences that open and close
the rule, and those name the standard rather than a page surface, so by §154 they are the half a
writer cannot act on. A sentence that breaks no rule is a gap, not an enforcement failure, and
that is the one condition §168.2 licenses a new clause for.

Four things are asserted, and they fail for four different reasons.

**The object.** `test_the_new_demand_fails_a_comparison_and_not_figuration_at_large` is the one
to read: scoping the prohibition to comparisons is what keeps it off ordinary metaphor by
construction rather than by exemption, and §163 is the standing record of what a filter keyed
one notch wider costs.

**The boundary.** The concession sits inside the sentence, after a semicolon, so the clause
reaches a comparison the reader cannot complete and never a comparison as such.

**The price of the scope word.** The pronoun widening changed one scope word and nothing else,
so it cost no demand anywhere. `tests/test_prompt_budget.py` owns the six ceilings the figure
clause did move; this file owns the shape that keeps the free half free.

**What is deliberately not reached.** The third instance — a description standing in for a thing
that has a plain name — is refused and stated before the fact, because every wording that
reaches it and the comparison together forbids ordinary anaphora.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import pytest

from litharness.application import planner
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house

#: The demand §176 added, held by its operative words rather than whole, so a later re-scope of
#: its object does not have to edit an assertion about its punctuation.
_COMPARISON = "a comparison to a thing that does not have the quality"

#: The clause §176 widened. Its scope word is the only thing that moved; the remedy and the
#: concession below are asserted untouched, because a widening that quietly rewrites a measured
#: remedy is a new rule wearing an old sentence.
_PRONOUN = "a pronoun points at one person or object only"


def _clause() -> str:
    (found,) = [item for item in house.demands(house.CLARITY) if _COMPARISON in item]
    return found


def test_the_new_demand_fails_a_comparison_and_not_figuration_at_large() -> None:
    """The object that keeps §163's failure mode out of a clause aimed at figures.

    A rule against figures whose literal reading is false deletes presence by construction: a
    room going cold, a stomach dropping and a voice being warm are all literally false and all
    decode instantly. Scoping the object to a *comparison* excludes every one of them without
    an exemption having to be written, which is why the wider vocabulary must stay out.
    """
    clause = _clause()
    assert clause.startswith("What fails is")
    for wider in ("metaphor", "figure", "image", "imagery", "simile", "literal"):
        assert wider not in clause.lower()


def test_the_boundary_is_a_concession_inside_the_sentence() -> None:
    """§161.5's pattern, and the reason a permission was not written instead.

    §138 measured a permission-only clause returning more than six times what a
    prohibition-only one did, worse than silence. So the thing that protects a stock likeness
    is a delimiter sharing the prohibition's own terminator, never a sentence of its own.
    """
    clause = _clause()
    head, semicolon, tail = clause.partition(";")
    assert semicolon, "the concession must share the prohibition's sentence"
    assert "is not that" in tail
    # The reader appears only in the delimiter. The object of the demand is a comparison — a
    # thing a writer emits — which is §154's axis applied before the clause shipped rather
    # than after a read finds it inert.
    assert "reader" not in head.lower()


def test_the_new_demand_carries_no_instance_list() -> None:
    """Three clauses in this module were cut for being recited, and each was an instance list.

    §168 and §171 both shipped without one for the same reason, and this clause names a
    configuration rather than a vocabulary, so it has nothing an instance would add.
    """
    clause = _clause()
    assert "—" not in clause
    assert ":" not in clause
    assert clause.count(",") == 0


def test_the_pronoun_clause_now_reaches_objects_and_kept_its_remedy() -> None:
    """The half of read 10 that cost nothing, and the guard on how it cost nothing.

    The paragraph clause has said since read 2 that inside a paragraph a pronoun points at one
    person only, and read 10's first instance is that mechanism with a thing in the slot. A
    scope word is the whole edit: if the remedy or the concession ever moves, this stopped
    being a widening and became a rewrite of a clause a measured read is standing on.
    """
    (pronoun,) = [item for item in house.demands(house.CLARITY) if _PRONOUN in item]
    assert "use their names" in pronoun
    assert "however plain that reads" in pronoun


def test_the_scope_word_cost_no_demand_and_the_figure_clause_cost_exactly_one() -> None:
    """The arithmetic §176 paid at the ceilings, held here so a later edit cannot blur it.

    `house.demands` is the counter every ceiling in `tests/test_prompt_budget.py` is computed
    from, and the claim being made is that one sentence was added and one word was widened.
    Counts are asserted exactly rather than with `<=`, because a bound here would stop this
    file noticing the next silent growth — `tests/test_scene_economy.py`'s reason unchanged.

    **The floor read 25, not §176's 26, once §174 landed the same day**: the readership clause
    left `house.READER` for the listing task, so CLARITY's 13 stood beside READER's 11. This
    file's own claim — one sentence added, one word widened, on the clarity side — was untouched
    by that departure.

    **14 and 26 since §181 took the headroom that crossing left.** The diction clause is the
    fourteenth demand on this rule, which is the growth these exact counts exist to make somebody
    decide on rather than notice later; the two §176 added and widened are asserted by shape in
    the tests above and are what this file is actually guarding.
    """
    assert len(house.demands(house.CLARITY)) == 14
    assert len(house.demands(house.HOUSE_RULES)) == 26


def test_the_third_instance_is_not_reached_and_the_clause_does_not_forbid_anaphora() -> None:
    """§171.2's form: the arm deliberately left alone, asserted before a census can find it.

    Read 10's third sentence names an object by a description the reader last met a passage
    earlier. Reaching it and the comparison with one clause requires keying on the reader
    having to go outside the sentence for what a phrase means, and that forbids a thing named
    in one sentence and *it* in the next — ordinary anaphora, and §163's failure mode exactly.
    So no clause here may speak about where a phrase's meaning lives.
    """
    clause = _clause()
    for outside in ("earlier", "elsewhere", "previous", "another sentence", "go back", "recall"):
        assert outside not in clause.lower()


@pytest.mark.parametrize(
    "word",
    ("seam", "kettle", "salt", "crock", "solidly", "morning", "mender", "human", "stayed"),
)
def test_no_word_of_the_read_10_chapter_became_prompt_text(word: str) -> None:
    """§97.1, mechanically, on the read that produced this entry.

    Named for its own read rather than reusing a sibling file's wording, which cites a
    different chapter: one ledger citation, one test.

    A defect harvest is the operator's side of the loop. A noun lifted out of the chapter under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright. The
    three sentences are fixtures in this file's docstring and go nowhere else.
    """
    assert word not in house.HOUSE_RULES.lower()


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §176's one clause."""
    assert word not in _clause().lower()


def test_both_edits_ride_the_scene_writers_live_assembled_prompt() -> None:
    """A clause is worth nothing if it reaches a constant and not a call.

    `render_prompt` is the path every drafted scene goes through, and the house floor arrives
    on it through `with_house_rules`. Asserted against the live assembly rather than against
    `HOUSE_RULES`, because a copy is the failure `tests/test_prompt_budget.py` was founded on.
    The drafting call is also the one role where neither edit is inert: it is where comparisons
    and pronouns are written.
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
            query_id="figure-clarity",
            target_logical_id="s1",
            book_id="book",
            branch_id="main",
            base_revision_id="r0",
        ),
    )
    assert _COMPARISON in system
    assert _PRONOUN in system
