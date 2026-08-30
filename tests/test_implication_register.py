"""Stage-0 §179, moved by §187: one prohibition for two register families, at one address.

**The defect this file exists for was not a rule being broken.** Read 11 named two things
separately: a construction — a narrator asserting an absence or a universal access that the
surrounding words already give — and a principle about the whole register, that what a passage
implies is not restated to the reader. Every demand on the house floor was read against all three
flagged instances first (§154's audit order) and each missed by its object: the unmet-term clause
fails a *name*, and a restatement is made of words the reader already has; the two-ways clause
fails a sentence with two readings, and these have one reading and it is the right one; §168's
clause has the unit wrong, its object being a **passage** where the defect is five words hung on
the end of a sentence; §171's has the object wrong, failing a *generalisation used as
explanation* where an absence asserted about one moment generalises about nobody.

**The clause shipped at two addresses and left both on 2026-08-30** (§187). It is now in
`application/reviser.py`, once. **Removing only one of the two was the thing to get wrong here**,
and `test_the_floor_and_the_listing_carry_the_same_sentence` is the name that now holds the
other side of the identity it used to hold: leaving the listing's copy standing would have given
a withdrawn rule its sole home at the one production role that stands on no house floor, which
inverts §179's own reason for writing it there. `plan/agent-impact/` is the measurement — every
family alive at the thirteenth read is clause-addressed, and no register clause moved a sentence
metric across ten chapters — and the operator's word at that report is the other half of §127's
brake.

**Why this clause can live under containment, which is what qualified it to move.** Both arms
name something a rewrite can drop without touching an event, a name or a number: an absence
nothing had put in question, and a restatement of what the sentence carrying it already gave.
A demand whose only compliant response is refused by the containment check one function later
would land with its sign multiplied by zero (§154), and this one is not that.

Five things are asserted about the clause, and they fail for five different reasons.

**One clause and not two.** `test_the_second_arm_names_the_first_as_its_general_case` holds the
decision that made this one sentence: the negative-space construction is the special case of the
principle where the thing already given is an absence, so the second arm reads *anything else* —
which is a subsumption marker rather than §171's refused second rule wearing one terminator.

**The two arms are bounded differently, and the asymmetry is what keeps §163 out.** A restatement
needs a source, so that arm is keyed to the sentence it sits in and cannot reach a callback a
chapter later. An absence needs no source to be empty, so that arm is keyed to nothing having put
the thing in question and reaches a bare assertion standing alone.

**The boundary is a concession inside the sentence.** An absence that is genuinely news is the
shape a filter one notch wider would delete, and this genre's suspense is built from it.

**No word list.** The construction has two surface forms and both are built from ordinary
quantifiers; naming those words would suppress the words instead of the construction, which is
what every deleted word list in this repository was deleted for.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import pytest

from litharness.application import overview, planner, reviser
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house
from litharness.domain import writers as writers_domain

#: The demand §179 added, held by its operative words rather than whole, so a later re-scope of
#: either arm does not have to edit an assertion about its punctuation.
_IMPLICATION = "naming an absence or a permission"

#: Invented material of the flagged shapes, and invented is the whole point (§97.1): a sentence
#: lifted out of the listing under read would be the operator's diagnostic laundered into the
#: repository with the evidence still inside. Nothing here reaches a prompt, and
#: `test_no_fixture_of_this_file_reaches_any_prompt` is what keeps that true. They are recorded
#: in the shape a later counter would want them — the tell and its near-neighbour, side by side —
#: because §156's census is the standing example of a detector that could only be trusted once
#: its own refusals were written down beside its hits.
TELL_FIXTURE: tuple[str, ...] = (
    # An absence: the lamps coming on together is what already gives the reader the rest.
    "The lamps came on along the whole street at dusk, and nobody had thrown a switch.",
    # A permission: naming an access that nothing had suggested was restricted.
    "They kept the notice board by the gate, where anyone at all could stand and read it.",
    # A restatement: the second clause states what the first one already implies.
    "The rope was frayed most of the way through and it would not hold a man.",
)

#: The boundary the clause must not cross. An absence carrying a fact the reader could not have
#: supplied is not the tell, and a filter that deleted it would delete what this genre's suspense
#: is made of — §163's lesson, which cost `house` a clause already.
INFORMATIVE_FIXTURE: tuple[str, ...] = (
    "The lamps on that street had been dark since the flood.",
    "Nobody had come down from the upper floor in three days.",
)


def _clause(text: str) -> str:
    (found,) = [item for item in house.demands(text) if _IMPLICATION in item]
    return found


def test_the_floor_and_the_listing_carry_the_same_sentence() -> None:
    """The two addresses, and the guard now holds the identity of an absence instead.

    **Inverted by §187 and the name is kept deliberately.** From 2026-08-30 this asserted that
    `house.READER` and `overview._TASK` carried one sentence byte-identical; it now asserts that
    neither carries it and that `reviser._TASK` does. The name survives because
    `tests/test_architecture.py` holds every ledger citation to an existing test and §179 cites
    this one — a deleted name breaks the citation and a renamed one resolves a reader to nothing.

    What made the pair worth asserting is what makes the removal worth asserting: a rule with two
    homes drifts in one of them, and a rule removed from one home is exactly that drift with the
    sign flipped. The listing does not stand on the house floor (`overview._system`), so a half
    removal here would have left the withdrawn clause live at the one role a floor edit cannot
    reach.
    """
    assert _IMPLICATION not in house.READER
    assert _IMPLICATION not in house.HOUSE_RULES
    assert _IMPLICATION not in overview._TASK
    assert _IMPLICATION in reviser._TASK


def test_the_second_arm_names_the_first_as_its_general_case() -> None:
    """The one-clause decision, held in the words that carry it, and they travelled unchanged.

    Two clauses would have cost two demands at six house numbers and at the listing's, and §127's
    brake is that a second rule against one complaint is the shape this project has measured
    failing four times. `anything else` is what makes this one rule: it says the absence arm is an
    instance of the implication arm rather than a separate prohibition sharing a terminator, which
    is the evasion §171 refused when it declined to hang its clause off an existing sentence.

    **The counts moved on 2026-08-30 for §187 and they moved down**, which is the first time
    either number in this test has fallen. `house.READER` 12 -> 10: §171's gloss and §179's own
    clause both left for the reviser. `overview._TASK` 14 -> 13: this clause's second copy left
    with it. They are asserted exactly rather than with `<=`, because a bound here would stop this
    file noticing the next silent growth — `test_scene_economy`'s reason unchanged, and
    `tests/test_prompt_budget.py` owns the ceilings themselves.
    """
    clause = _clause(reviser._TASK)
    assert clause.startswith("What fails is")
    head, _semicolon, _tail = clause.partition(";")
    assert "anything else" in head
    assert len(house.demands(house.READER)) == 10
    assert len(house.demands(overview._TASK)) == 13


def test_the_two_arms_are_bounded_differently_and_neither_reaches_a_passage() -> None:
    """The asymmetry that keeps §163's failure mode out of a clause about redundancy.

    **Repointed to `reviser._TASK` by §187; the assertion is unchanged, which is the claim.**
    The clause moved byte-identical, so a bound argued at one address is the bound in force at
    the next, and nothing was redrafted under cover of the move.

    The implication arm is keyed to one sentence: a window of one cannot delete a deliberate echo
    across a scene or a callback a chapter later. The absence arm carries no window at all, and
    has to — an assertion standing as its own sentence has no neighbour to have implied it, and a
    window-keyed rule would miss the shape that named the family. Any wider unit in this clause
    would make it §168's clause a second time at the wrong altitude.
    """
    clause = _clause(reviser._TASK).lower()
    assert "its own sentence" in clause
    for wider in ("passage", "paragraph", "chapter", "earlier", "anywhere", "book"):
        assert wider not in clause


def test_the_boundary_is_a_concession_inside_the_sentence() -> None:
    """§161.5's pattern, and the reason a permission was not written instead.

    §138 measured a permission-only clause returning more than six times what a prohibition-only
    one did, worse than silence. So what protects an absence that is genuinely news is a delimiter
    sharing the prohibition's own terminator, never a sentence of its own. The delimiter names a
    different test from the head's — what the reader could not have supplied, against what the
    sentence already gives — rather than the head's negation, which would carry no boundary at
    all.
    """
    clause = _clause(reviser._TASK)
    head, semicolon, tail = clause.partition(";")
    assert semicolon, "the concession must share the prohibition's sentence"
    assert "is not that" in tail
    # The reader appears only in the delimiter. The object of the demand is a clause — a thing a
    # writer emits — which is §154's axis applied before the clause shipped rather than after a
    # read finds it inert.
    assert "reader" not in head.lower()


@pytest.mark.parametrize(
    "quantifier",
    ("nobody", "no one", "no-one", "anyone", "anybody", "everyone", "everybody", "somebody"),
)
def test_the_clause_names_none_of_the_words_the_construction_is_built_from(
    quantifier: str,
) -> None:
    """The word-list refusal, and it is load-bearing rather than stylistic.

    **Checked at one address since §187** — the clause has one home again, so the loop over two
    is gone rather than the check.

    Both surface forms of this construction are built from ordinary quantifiers standing as the
    subject. A prohibition naming those words would suppress the words rather than the
    configuration — the failure every deleted word list in this repository was deleted for, and
    §163's lesson about a filter keyed wide enough to delete presence. The clause names a
    configuration instead, and holds no quantifier in that position: what it does say about
    something *nothing* had put in question describes the text's prior state rather than a word a
    writer is being steered off.
    """
    assert quantifier not in _clause(reviser._TASK).lower()


def test_the_clause_carries_no_instance_list() -> None:
    """Three clauses in `house` were cut for being recited, and each was an instance list.

    §168, §171 and §176 all shipped without one for the same reason, and this clause names a
    configuration rather than a vocabulary, so it has nothing an instance would add. The instances
    that named the family are in this file, where a detector can read them and a prompt cannot.
    """
    clause = _clause(reviser._TASK)
    assert "—" not in clause
    assert ":" not in clause
    assert clause.count(",") == 1


def test_the_new_clause_is_not_the_narrating_the_inference_prohibition_again() -> None:
    """§171 is the closest neighbour and the objects are different — now at the same address.

    **Both clauses moved to `reviser._TASK` on 2026-08-30 (§187), so this test matters more than
    it did.** On the floor they were two demands in one constant; here they are two demands in
    one instruction, and the case for keeping them apart is unchanged: §171 fails a narrator
    explaining one person's act with a rule about people in general, while an absence asserted
    about one moment states no rule and generalises about nobody. A merge would produce a count
    named for a defect it does not measure, and §150.4 deleted a field for exactly that.
    """
    clause = _clause(reviser._TASK)
    for other in ("narrator", "people in general", "however true"):
        assert other not in clause
    gloss = [item for item in house.demands(reviser._TASK) if "people in general" in item]
    assert len(gloss) == 1 and gloss[0] != clause


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied at §179's one remaining address."""
    assert word not in _clause(reviser._TASK).lower()


@pytest.mark.parametrize(
    "word",
    ("screen", "bites", "weak", "building", "spoon", "unsaid", "disrespect", "overexplain"),
)
def test_no_word_of_the_read_11_items_became_prompt_text(word: str) -> None:
    """§97.1, mechanically, on the read that produced this entry.

    **Widened by §187 to the clause at its new address.** A rule that travels between prompts is
    a rule that could pick up a word on the way, so all three texts are checked: the two it left,
    whole, and the clause it became. The third is scoped to the clause rather than to the whole
    instruction for the reason `tests/test_plain_diction.py` records against its own version of
    this test — a word list built from one read is evidence about one clause.

    A defect harvest is the operator's side of the loop. A noun lifted out of the listing under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright. Both
    halves are checked: the words of the flagged instances and the words of the direction that
    named them.
    """
    assert word not in house.HOUSE_RULES.lower()
    assert word not in overview._TASK.lower()
    assert word not in _clause(reviser._TASK).lower()


@pytest.mark.parametrize("fixture", TELL_FIXTURE + INFORMATIVE_FIXTURE)
def test_no_fixture_of_this_file_reaches_any_prompt(fixture: str) -> None:
    """A fixture is detector material, and the way one becomes prompt text is by being handy.

    These sentences are invented rather than lifted for §97.1's reason, and they still may not
    travel: `house` has cut three clauses for being recited back, and every one of them was an
    example somebody thought was harmless where it stood. Checked at the clause's new address
    too, since §187 gave the fixtures a third prompt to leak into.
    """
    assert fixture not in house.HOUSE_RULES
    assert fixture not in overview._TASK
    assert fixture not in reviser.revision_system()


def test_the_clause_rides_the_scene_writers_live_assembled_prompt() -> None:
    """The name is kept and what it asserts is inverted, which is §187's whole content.

    **Until 2026-08-30 this asserted the clause reached the drafting call. It now asserts it does
    not**, and that the reviser's live assembled system message carries it instead.

    `render_prompt` is the path every drafted scene goes through, and the house floor arrives on
    it through `with_house_rules`. Asserted against the live assembly rather than against
    `HOUSE_RULES`, because a copy is the failure `tests/test_prompt_budget.py` was founded on —
    and an absence read off a constant is exactly the kind of claim that goes stale silently.
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
            query_id="implication-register",
            target_logical_id="s1",
            book_id="book",
            branch_id="main",
            base_revision_id="r0",
        ),
    )
    assert _IMPLICATION not in system
    assert _clause(reviser._TASK) in reviser.revision_system()


def test_the_clause_rides_the_listing_call_which_carries_no_floor_under_it() -> None:
    """The second address, through the live request — and it is now an absence at both.

    **Inverted by §187**, and the pair this test was written to assert is the pair that decided
    the removal: the clause was in the assembled system message and the house floor was not, so
    the listing's copy was the only home a floor edit could not reach. Removing the floor's half
    alone would have promoted a withdrawn rule to sole occupancy of that call. The second half of
    the assertion is unchanged and still load-bearing: if a later track ever puts the floor back
    under this call, this test is where that shows up.
    """
    request = overview.render_overview_request("", writers_domain.CAST["ferreira"])
    system = request.system or ""
    assert _IMPLICATION not in system
    assert house.HOUSE_RULES not in system
