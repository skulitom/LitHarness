"""Stage-0 §181: the diction clause, why its object is provenance, and what it will not reach.

**The defect this file exists for was named three times before it got a rule.** Read 7 quoted two
words it could not cash, read 8 a third, and read 11 named the family: a thing given the word its
occupation uses where everyday speech has one for the same thing — in prose, and in a name the
world calls its own. Every demand in `house.CLARITY` was read against it first (§154's audit
order) and each missed by its object: the unmet-term pair fails a name *invented because the world
wanted one*, and a word borrowed out of a real occupation is not invented; the two-ways clause
fails a sentence with two readings *available*; the object clause fails an object *acting*; the
comparison clause fails a *comparison*; the paragraph clause's scope is a pronoun. What was left
were the two sentences that open and close the rule, which name the standard rather than a page
surface. A sentence that breaks no rule is a gap, and that is the one condition §168.2 licenses a
new clause for.

**The object is where the word came from, and the reason is a measurement that already exists.**
§156.3 counted rare words in our chapters against the market's own and put ours *inside the
genre's range* — so a clause failing a word for being uncommon would legislate against the texture
the genre itself has, on the wrong side of a number this project already has. Provenance is not
frequency: it is a property the writer holds when they choose the word, which is what makes the
demand checkable on the page rather than in a reader's head. *A word the reader would have to look
up* is a reader state, and §154 is the record of what a reader state costs a clause.

**Two surfaces, one clause, and the Architect half is the new thing here.** §171 and §176 both
paid a ceiling at the Architect for demands that land inert there, because that role narrates
nothing. This one does not: its every act is a `world declare` whose subject is a name it chose,
so the same prohibition governs the token both roles emit. `test_the_clause_rides_both_live
_assembled_prompts` is the one to read.

No model reads, ranks or judges anything here, no counter is proposed, and no bar is declared.
"""

from __future__ import annotations

import pytest

from litharness.application import planner, world_agent
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house, writers

#: The demand §181 added, held by its operative words rather than whole, so a later re-scope of
#: its object does not have to edit an assertion about its punctuation.
_DICTION = "a specialist's word where ordinary speech has one"


def _clause() -> str:
    (found,) = [item for item in house.demands(house.CLARITY) if _DICTION in item]
    return found


def test_the_new_demand_fails_a_words_provenance_and_never_its_rarity() -> None:
    """The object that keeps this clause on the right side of §156.3's measurement.

    That entry counted rare unigrams in our chapters against 64,931 market ones and found our
    median inside the genre's own range — the finding being that the class is real and does not
    separate us, so **a vocabulary floor is not supported by it**. A clause that failed a word for
    being rare, unusual or hard would therefore be a rule written against a number the project
    already holds, and it would delete the concrete noun this genre is made of. What is failed
    instead is where the word was got from, which nothing in §156 measured and which the writer
    knows at the moment of writing.
    """
    clause = _clause()
    assert clause.startswith("What fails is")
    for rarity in ("rare", "uncommon", "unusual", "obscure", "difficult", "hard", "complex"):
        assert rarity not in clause.lower()


def test_the_demand_is_addressable_and_names_no_reader_state() -> None:
    """§154's axis, applied before the clause shipped rather than after a read finds it inert.

    The awe clause failed by naming what a reader should feel: a reader state is not a token a
    writer can emit, so the demand had no page surface and went inert with an earlier clause
    occupying its slot. What this one fails is a word on the page. The obvious wording — *a word
    the reader has to look up* — is exactly the shape that failed, and it is why the reader does
    not appear in this sentence at all.
    """
    clause = _clause()
    assert "reader" not in clause.lower()
    for state in ("look up", "know", "understand", "confus", "exclud"):
        assert state not in clause.lower()


def test_the_object_excludes_the_precise_noun_by_construction_and_not_by_exemption() -> None:
    """§176's form, and §163's warning about a filter keyed one notch wider.

    The genre's pleasure is in things named exactly, and a rule against precise nouns would
    delete presence the way a truth-keyed removal test once did. The delimiter is inside the
    object: where ordinary speech has no word for the same thing there is nothing to fail, so
    a scalpel stays a scalpel and no exemption had to be written for it. Because the exclusion
    is structural, the clause needs no concession — and so, unlike §176's, it carries none.
    """
    clause = _clause()
    assert "where ordinary speech has one for the same thing" in clause
    assert ";" not in clause


def test_the_new_demand_carries_no_instance_list_and_no_word_list() -> None:
    """Three clauses in this module were cut for being recited, and each was an instance list.

    A word list is refused twice over: by that history, and by boundary 3 as the operator
    amended it — a list of forbidden words is a hack over the underlying problem, and it makes
    coinage the way out. This clause names a provenance rather than a vocabulary, so an instance
    would only give the model something to recite.
    """
    clause = _clause()
    assert "—" not in clause
    assert ":" not in clause
    assert clause.count(",") == 0


def test_the_elliptical_idiom_is_not_reached_and_ordinary_ellipsis_is_not_forbidden() -> None:
    """§176.6's form: the arm deliberately left alone, asserted before a census can find it.

    The same read named a line whose verb is simply missing — a compressed construction, not a
    borrowed word, so this clause does not touch it. Every wording found that reaches both keys
    on a sentence leaving something out, and that forbids the way people actually speak. So no
    clause here may speak about what a sentence omits.
    """
    clause = _clause()
    for omission in ("leaves out", "omit", "missing", "unstated", "implied", "short form"):
        assert omission not in clause.lower()


def test_the_clause_rides_both_live_assembled_prompts() -> None:
    """The two surfaces, on the calls rather than on the constant.

    A clause is worth nothing if it reaches a constant and not a call, and a copy is the failure
    `tests/test_prompt_budget.py` was founded on. The drafting call is where nouns are chosen.
    The Architect is the other half and is what makes this demand different from the two floor
    clauses before it: §171's and §176's both land inert there, because that role narrates
    nothing and writes no comparisons, while every act it *does* take is a `world declare` whose
    subject is a name it chose. One prohibition, two roles, one home — a second copy in
    `world_agent._SYSTEM` was refused as §152's two-homes defect made in advance.
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
            query_id="plain-diction",
            target_logical_id="s1",
            book_id="book",
            branch_id="main",
            base_revision_id="r0",
        ),
    )
    assert _DICTION in system
    seed = world_agent.render_seed_request("a listing", None)
    assert _DICTION in (seed.system or "")


def test_the_architect_seed_keeps_one_home_for_the_naming_rule() -> None:
    """The refusal, as a guard rather than as a paragraph in the ledger.

    `_SYSTEM` already tells the Architect what to declare and the house floor already tells it
    what fails; a naming rule written into both is two texts to disagree with each other, which
    is the defect §152 found at four addresses. The seed's own naming words are the ones §163
    shipped for grants and are left exactly as they were.
    """
    assert _DICTION not in world_agent._SYSTEM
    assert "specialist" not in world_agent._SEED.lower()
    assert "named in short plain words with no digits in them" in world_agent._SYSTEM


@pytest.mark.parametrize(
    "word",
    ("folding", "ruler", "assay", "laboratory", "phone", "queue", "awning", "trestle", "thumb"),
)
def test_no_word_of_the_read_11_items_became_prompt_text(word: str) -> None:
    """§97.1, mechanically, on the three reads that produced this entry.

    A defect harvest is the operator's side of the loop. A noun lifted out of the chapter under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright.
    Loaded words only: this clause and the read share ordinary English like *thing* and *word*,
    and a test that failed on those would be asserting the clause could not be written in
    English rather than that nothing was lifted.
    """
    assert word not in house.HOUSE_RULES.lower()


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §181's one clause."""
    assert word not in _clause().lower()


def test_the_clause_does_not_prime_the_architects_institutional_register() -> None:
    """The house floor is not covered by the Architect's own guard, so it is covered here.

    `test_the_architect_task_text_names_no_institution` reads `_SEED`, `_GROW` and `_TOOLS`, and
    §156.1's finding — the institutional lean is not in our text — only stays true if nobody adds
    one anywhere the Architect reads. The floor is read on every seed, so the naming of an
    occupation in this clause is held to the same family, and to the schema's own role values
    besides: a word the menu prints is a word this text could teach a world to declare.
    """
    clause = _clause().lower()
    for institution in ("guild", "charter", "licence", "license", "tribunal", "trade", "craft"):
        assert institution not in clause


def test_the_writer_dossier_path_carries_the_clause_too() -> None:
    """A cast writer's system prompt is the dossier plus the floor, and the floor is not optional.

    `house.with_house_rules` is the single assembly every role goes through, and the reason it is
    a function is that each role that grew its own concatenation grew its own spacing. Asserted
    on a writer rather than on the empty case, because the cast path is the one a real book uses.
    """
    writer = writers.build(
        name="A Writer",
        dossier=(
            "Spent eleven years reading tide tables for a working harbour and still argues "
            "about what the numbers in them are actually measuring."
        ),
    )
    assert _DICTION in writers.system_for("Write the scene.", writer)
