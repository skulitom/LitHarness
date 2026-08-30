"""Stage-0 §179: one prohibition for two register families, at the floor and at the listing.

**The defect this file exists for was not a rule being broken.** Read 11 named two things
separately: a construction — a narrator asserting an absence or a universal access that the
surrounding words already give — and a principle about the whole register, that what a passage
implies is not restated to the reader. Every demand on the house floor was read against all three
flagged instances first (§154's audit order) and each missed by its object: the unmet-term clause
fails a *name*, and a restatement is made of words the reader already has; the two-ways clause
fails a sentence with two readings, and these have one reading and it is the right one; §168's
clause has the unit wrong, its object being a **passage** where the defect is five words hung on
the end of a sentence; §171's has the object wrong, failing a *generalisation used as
explanation* where an absence asserted about one moment generalises about nobody. A sentence that
breaks no rule is a gap, not an enforcement failure, and that is the one condition §168.2
licenses a new clause for.

**And the address was half the finding.** Both instances of the construction are in a **listing**,
and §174 had established the day before that the listing is the one production role standing on no
house floor. So a register clause added to `house` would have reached every role except the one
whose output was under read. The same sentence therefore ships at two addresses, byte-identical,
and `test_the_floor_and_the_listing_carry_the_same_sentence` is what makes a drift between them a
test failure rather than a thing somebody notices later.

Five things are asserted, and they fail for five different reasons.

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

from litharness.application import overview, planner
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
    """The two addresses, and the guard that keeps them one rule instead of two.

    The listing does not stand on the house floor (`overview._system`), so a register clause in
    `house` cannot reach the artifact read 11's instances were found in. A second statement of a
    rule with a canonical home is what this file's subject already is — `overview` records two
    `house.CLARITY` clauses on the same footing — and the honest version of that arrangement is
    an assertion rather than a note, because the 2026-08-26 restoration had to establish the same
    identity by reading both files.
    """
    assert _clause(house.READER) == _clause(overview._TASK)


def test_the_second_arm_names_the_first_as_its_general_case() -> None:
    """The one-clause decision, held in the words that carry it.

    Two clauses would have cost two demands at six house numbers and at the listing's, and §127's
    brake is that a second rule against one complaint is the shape this project has measured
    failing four times. `anything else` is what makes this one rule: it says the absence arm is an
    instance of the implication arm rather than a separate prohibition sharing a terminator, which
    is the evasion §171 refused when it declined to hang its clause off an existing sentence.
    """
    clause = _clause(house.READER)
    assert clause.startswith("What fails is")
    head, _semicolon, _tail = clause.partition(";")
    assert "anything else" in head
    # One demand at each address, not two. Asserted exactly rather than with `<=`, because a
    # bound here would stop this file noticing the next silent growth — `test_scene_economy`'s
    # reason unchanged, and `tests/test_prompt_budget.py` owns the ceilings themselves. The task
    # text is counted rather than the assembled role: the budget file's 18 is this 14 plus the
    # four demands of a cast dossier, and a ceiling that moved when a writer's dossier grew
    # would be a ceiling on dossiers.
    #
    # **13 -> 14 on 2026-08-30, and the growth is not this clause's** (§183). The house genre
    # gained its first surface at the listing, one sentence, and the budget row moved 17 -> 18
    # with it. The exact assertion is what made that visible in this file rather than silently,
    # which is what an exact assertion is for; §179's own clause is unchanged and still one
    # demand at both addresses.
    assert len(house.demands(house.READER)) == 12
    assert len(house.demands(overview._TASK)) == 14


def test_the_two_arms_are_bounded_differently_and_neither_reaches_a_passage() -> None:
    """The asymmetry that keeps §163's failure mode out of a clause about redundancy.

    The implication arm is keyed to one sentence: a window of one cannot delete a deliberate echo
    across a scene or a callback a chapter later. The absence arm carries no window at all, and
    has to — an assertion standing as its own sentence has no neighbour to have implied it, and a
    window-keyed rule would miss the shape that named the family. Any wider unit in this clause
    would make it §168's clause a second time at the wrong altitude.
    """
    clause = _clause(house.READER).lower()
    assert "its own sentence" in clause
    for wider in ("passage", "paragraph", "chapter", "scene", "earlier", "anywhere", "book"):
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
    clause = _clause(house.READER)
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

    Both surface forms of this construction are built from ordinary quantifiers standing as the
    subject. A prohibition naming those words would suppress the words rather than the
    configuration — the failure every deleted word list in this repository was deleted for, and
    §163's lesson about a filter keyed wide enough to delete presence. The clause names a
    configuration instead, and holds no quantifier in that position: what it does say about
    something *nothing* had put in question describes the text's prior state rather than a word a
    writer is being steered off.
    """
    for address in (house.READER, overview._TASK):
        assert quantifier not in _clause(address).lower()


def test_the_clause_carries_no_instance_list() -> None:
    """Three clauses in `house` were cut for being recited, and each was an instance list.

    §168, §171 and §176 all shipped without one for the same reason, and this clause names a
    configuration rather than a vocabulary, so it has nothing an instance would add. The instances
    that named the family are in this file, where a detector can read them and a prompt cannot.
    """
    clause = _clause(house.READER)
    assert "—" not in clause
    assert ":" not in clause
    assert clause.count(",") == 1


def test_the_new_clause_is_not_the_narrating_the_inference_prohibition_again() -> None:
    """§171 is the closest neighbour on this constant, and the objects are different.

    §171 fails a narrator explaining one person's act with a rule about people in general. An
    absence asserted about one moment states no rule and generalises about nobody, so that clause
    could not reach read 11's instances — which is why this one exists. The two stay separate
    demands: a merge would produce a count named for a defect it does not measure, and §150.4
    deleted a field for exactly that.
    """
    clause = _clause(house.READER)
    for other in ("narrator", "people in general", "however true"):
        assert other not in clause
    assert len([item for item in house.demands(house.READER) if item.startswith("What fails")]) == 3


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied at both of §179's addresses."""
    for address in (house.READER, overview._TASK):
        assert word not in _clause(address).lower()


@pytest.mark.parametrize(
    "word",
    ("screen", "bites", "weak", "building", "spoon", "unsaid", "disrespect", "overexplain"),
)
def test_no_word_of_the_read_11_items_became_prompt_text(word: str) -> None:
    """§97.1, mechanically, on the read that produced this entry.

    A defect harvest is the operator's side of the loop. A noun lifted out of the listing under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright. Both
    halves are checked: the words of the flagged instances and the words of the direction that
    named them.
    """
    assert word not in house.HOUSE_RULES.lower()
    assert word not in overview._TASK.lower()


@pytest.mark.parametrize("fixture", TELL_FIXTURE + INFORMATIVE_FIXTURE)
def test_no_fixture_of_this_file_reaches_any_prompt(fixture: str) -> None:
    """A fixture is detector material, and the way one becomes prompt text is by being handy.

    These sentences are invented rather than lifted for §97.1's reason, and they still may not
    travel: `house` has cut three clauses for being recited back, and every one of them was an
    example somebody thought was harmless where it stood.
    """
    assert fixture not in house.HOUSE_RULES
    assert fixture not in overview._TASK


def test_the_clause_rides_the_scene_writers_live_assembled_prompt() -> None:
    """A clause is worth nothing if it reaches a constant and not a call.

    `render_prompt` is the path every drafted scene goes through, and the house floor arrives on
    it through `with_house_rules`. Asserted against the live assembly rather than against
    `HOUSE_RULES`, because a copy is the failure `tests/test_prompt_budget.py` was founded on.
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
    assert _clause(house.READER) in system


def test_the_clause_rides_the_listing_call_which_carries_no_floor_under_it() -> None:
    """The second address, through the live request rather than through the constant.

    The assertion that matters is the pair: the clause is in the assembled system message, and
    the house floor is not — which is the whole reason a second statement had to be written. If a
    later track ever puts the floor back under this call, this test is where that shows up, and
    the duplicate becomes a subtraction to make rather than a drift to chase.
    """
    request = overview.render_overview_request("", writers_domain.CAST["ferreira"])
    system = request.system or ""
    assert _clause(overview._TASK) in system
    assert house.HOUSE_RULES not in system
