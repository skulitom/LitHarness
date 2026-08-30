"""Stage-0 §181, moved by §187: the diction clause, its object, and the surface it lost.

**The defect this file exists for was named three times before it got a rule.** Read 7 quoted two
words it could not cash, read 8 a third, and read 11 named the family: a thing given the word its
occupation uses where everyday speech has one for the same thing — in prose, and in a name the
world calls its own. Every demand in `house.CLARITY` was read against it first (§154's audit
order) and each missed by its object: the unmet-term pair fails a name *invented because the world
wanted one*, and a word borrowed out of a real occupation is not invented; the two-ways clause
fails a sentence with two readings *available*; the object clause fails an object *acting*; the
comparison clause fails a *comparison*; the paragraph clause's scope is a pronoun.

**The clause left `house.CLARITY` on 2026-08-30 and is now in `application/reviser.py`** (§187),
and this one has the shortest record of any clause in the removal: it shipped after read 11, and
read 12's own record states that a member of its family was on the page despite it — an
enforcement failure recorded against the clause on the very next read — and read 13 named the
family again. `plan/agent-impact/` counts it among the four clause-addressed families still alive
at the last read, and the operator's word at that report is the other half of §127's brake.

**One thing was lost by the move and it is recorded rather than smoothed.** §181's own novelty
was that this clause was not inert at the Architect: that role's every act is a `world declare`
whose subject is a name it chose, so one prohibition governed the token two roles emit. The
reviser rewrites prose and declares no worlds, so the naming half has no surface any more.
`test_the_clause_rides_both_live_assembled_prompts` now holds that loss instead of that reach,
and `test_the_architect_seed_keeps_one_home_for_the_naming_rule` records what the seed still has:
its own rule asking for short plain words, which §163 shipped and this track did not touch.

**The object is where the word came from, and the reason is a measurement that already exists.**
§156.3 counted rare words in our chapters against the market's own and put ours *inside the
genre's range* — so a clause failing a word for being uncommon would legislate against the texture
the genre itself has, on the wrong side of a number this project already has. Provenance is not
frequency: it is a property the writer holds when they choose the word, which is what makes the
demand checkable on the page rather than in a reader's head. *A word the reader would have to look
up* is a reader state, and §154 is the record of what a reader state costs a clause. That argument
travelled with the sentence, which moved byte-identical.

No model reads, ranks or judges anything here, no counter is proposed, and no bar is declared.
"""

from __future__ import annotations

import pytest

from litharness.application import planner, reviser, world_agent
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house, writers

#: The demand §181 added, held by its operative words rather than whole, so a later re-scope of
#: its object does not have to edit an assertion about its punctuation.
_DICTION = "a specialist's word where ordinary speech has one"


def _clause() -> str:
    """The clause at its §187 address. `reviser._TASK` is now its one home."""
    (found,) = [item for item in house.demands(reviser._TASK) if _DICTION in item]
    return found


def test_the_clause_is_gone_from_the_floor_and_from_every_role_standing_on_it() -> None:
    """§187's removal, pinned at the constant and at the two roles the clause actually reached.

    The floor is not a place a clause can be half removed from: `with_house_rules` is the single
    assembly, so an absence here is an absence at the drafting call, the Architect and every
    other role that stands on it. Asserted at three addresses rather than one because the reach
    was the thing §181 was proud of, and the reach is what ended.
    """
    assert _DICTION not in house.CLARITY
    assert _DICTION not in house.HOUSE_RULES
    assert _DICTION in reviser._TASK


def test_the_new_demand_fails_a_words_provenance_and_never_its_rarity() -> None:
    """The object that keeps this clause on the right side of §156.3's measurement.

    **Repointed to `reviser._TASK` by §187; the assertion is unchanged and that is the claim.**
    The clause moved byte-identical, so the measurement that shaped its object still governs it,
    and nothing was redrafted under cover of the move.

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

    This matters more at the §187 address than it did on the floor: a rewriting stage that
    swapped every precise noun for a vague one would strip the page while obeying its brief, and
    the exclusion is what stops that without a permission having to be written (§138).
    """
    clause = _clause()
    assert "where ordinary speech has one for the same thing" in clause
    assert ";" not in clause


def test_the_new_demand_carries_no_instance_list_and_no_word_list() -> None:
    """Three clauses in `house` were cut for being recited, and each was an instance list.

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
    """The name is kept and what it asserts is replaced, and the replacement is a loss.

    **Until 2026-08-30 the two prompts were the drafting call and the Architect seed** — the
    reach §181 was written for, one prohibition governing the token two roles emit. §187 removed
    the clause from the floor, so it reaches neither. The two live prompts asserted here are now
    the pair that tells the truth about the move: the drafting call, which no longer carries it,
    and the reviser, which does.

    **The Architect loss has no replacement and is not asserted away.** That role declares names
    and the reviser does not, so the naming half of this clause has no surface in the pipeline
    any more. `tests/test_prompt_budget.py`'s `architect seed` row records the same fact from the
    other side, as the one demand of the five it lost that was not already inert there.

    The name survives the inversion because `tests/test_architecture.py` holds every ledger
    citation to an existing test and §181 cites this one; a deleted name breaks the citation and
    a renamed one resolves a reader to nothing.
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
    assert _DICTION not in system
    seed = world_agent.render_seed_request("a listing", None)
    assert _DICTION not in (seed.system or "")
    assert _DICTION in reviser.revision_system()


def test_the_architect_seed_keeps_one_home_for_the_naming_rule() -> None:
    """The refusal, as a guard rather than as a paragraph in the ledger.

    `_SYSTEM` already tells the Architect what to declare, and §181 refused to write a naming
    rule into it as well because a rule in two texts is two texts to disagree with each other —
    the defect §152 found at four addresses. **After §187 that refusal is what the seed has
    left**: the house floor no longer carries a diction prohibition at all, so `_SYSTEM`'s own
    words are the whole of what the seed is told about naming. They are the ones §163 shipped for
    grants and this track left exactly as they were, deliberately — re-adding the removed clause
    here under a different name would be the two-homes defect arriving by the back door.
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

    **Widened by §187 to the clause at its new address**, because a rule that travels between
    prompts could pick up a word on the way. **Scoped to the clause and not to the whole
    instruction, which the first draft of this got wrong**: run over `revision_system()` entire it
    failed on *folding*, a word in the reviser's own pre-existing folded-fact prohibition that has
    nothing to do with read 11. A word list built from one read is evidence about one clause; run
    over text this track did not write, it asserts that somebody else's rule could not be written
    in English. The floor half stays whole because the floor is what this clause left.

    A defect harvest is the operator's side of the loop. A noun lifted out of the chapter under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright.
    Loaded words only: this clause and the read share ordinary English like *thing* and *word*,
    and a test that failed on those would be asserting the clause could not be written in
    English rather than that nothing was lifted.
    """
    assert word not in house.HOUSE_RULES.lower()
    assert word not in _clause().lower()


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §181's one clause."""
    assert word not in _clause().lower()


def test_the_clause_does_not_prime_the_architects_institutional_register() -> None:
    """The guard outlives the surface it was written for, and is kept for the second reason.

    §181 wrote this because the house floor is read on every seed, so an occupation named in
    the clause could teach a world to declare one — §156.1's finding that the institutional lean
    is not in our text only stays true if nobody adds one anywhere the Architect reads.
    **After §187 the Architect no longer reads this clause**, so that reason has lapsed. The
    second reason has not: the clause is now in the one prompt whose output *replaces* the book's
    own sentences, and read 7 and read 8 both named institutional register on the page. A naming
    of an occupation here would reach prose directly rather than through a declaration.
    """
    clause = _clause().lower()
    for institution in ("guild", "charter", "licence", "license", "tribunal", "trade", "craft"):
        assert institution not in clause


def test_the_writer_dossier_path_carries_the_clause_too() -> None:
    """The name is kept and what it asserts is inverted, which is §187's content at this file.

    **Until 2026-08-30 a cast writer's system prompt carried this clause through the floor.** It
    does not now, and the second half of the assertion is what makes the first one meaningful:
    the floor still reaches that path, and still carries the clauses §187 kept. So this is a
    removal of one demand from the writer's prompt rather than a writer who stopped standing on
    the house rules — which is the misreading a bare absence would invite.

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
    assembled = writers.system_for("Write the scene.", writer)
    assert _DICTION not in assembled
    assert house.CLARITY in assembled
