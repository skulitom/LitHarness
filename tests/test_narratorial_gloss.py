"""Stage-0 §171: the narrating-the-inference clause, and the two lines it must not cross.

**The defect this file exists for is a construction, not a topic.** A narrator explains one
person's gesture or phrase by asserting a rule about what people in general do or mean — the
reader's own inference performed for them, in a voice that steps outside the moment to do it.
§156 measured it against the market's own chapters and found ours above the genre's rate on
both of the assertions it counts separately; that entry and `results/register-census.json` own
every number and none of them is repeated here or anywhere a model can read. Three reads named
the shape in three books by three writers, which is what took it from a tic to a house rule.

Four things are asserted, and they fail for four different reasons.

**The sign and the addressee.** The prohibition-signed test is the pair this module is
corrected for most often: §138 says a rule here may say what fails and may not enumerate what
succeeds, and §154 says a demand whose object is a reader state has no addressee at all. A
narrator's sentence is a thing a writer puts on a page and can put fewer of.

**The boundary, which is the whole difficulty.** A character's read of one specific moment is
this genre's ordinary free indirect style, and a clause that reached it would delete presence
by construction — §163's lesson, learned when a truth-keyed removal test was cut from the
clause above this one. So the prohibition is armed by the *rule about people* and by nothing
else, and `test_the_clause_reaches_the_general_rule_and_not_a_character_s_own_read` is what
stops a later edit widening it into a ban on narrated inference.

**The tier that was deliberately not reached.** §156's first tier has two arms and this clause
answers one of them on purpose. The other asserts no rule about anybody, so reaching it would
reach free indirect inference itself. The narrowing is pinned rather than remembered.

**What may not travel with it.** No count, no rate and no word of the chapter under read: the
census is an instrument that reads our prose, and a prompt built to satisfy it would be the
instrument measuring its own instruction.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import pytest

from litharness.application import planner
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house

#: The demand §171 added, held by its operative words rather than whole, so a later re-scope of
#: its object does not have to edit an assertion about its punctuation.
_GLOSS = "a rule about what people in general do or mean"

#: The delimiter that carries the boundary. It hangs off a semicolon inside the sentence it
#: bounds rather than standing as its own permission (§161.5's pattern, third use), so it costs
#: no demand and cannot be obeyed as an instruction to go and do something.
_DELIMITER = "what somebody in the scene makes of it is not that"


def _clause() -> str:
    (found,) = [item for item in house.demands(house.READER) if _GLOSS in item]
    return found


def test_the_clause_is_prohibition_signed_and_names_what_a_writer_emits() -> None:
    """`house`'s standing constraint and §154's second axis, applied before this ships.

    The awe clause failed both at once and nobody checked it against the rule the same file
    had adopted hours earlier. This one fails a narrator's sentence — a thing a writer emits
    and can emit fewer of — and names no state of anybody's mind.
    """
    clause = _clause()
    assert clause.startswith("What fails is a narrator")
    for reader_state in ("wants", "wondering", "feels", "invites", "excited", "why the reader"):
        assert reader_state not in clause.lower()


def test_the_clause_reaches_the_general_rule_and_not_a_character_s_own_read() -> None:
    """The boundary, and it is the reason this clause was hard rather than long.

    Free indirect perception that stays inside one character's read of one specific moment is
    the genre's ordinary register: somebody seeing another person decide a thing dramatises,
    where a rule about people legislates. §156's own counter draws the line in the same place,
    excluding an inference attributed to a character as interiority. Two halves hold it here —
    the prohibition is armed only by the general rule, and the delimiter says whose reading
    falls outside it — and a later widening has to break one of them.
    """
    clause = _clause()
    assert _GLOSS in clause
    assert _DELIMITER in clause
    # The delimiter is inside the sentence, so it delimits rather than permits and costs no
    # demand. A permission-only clause measured at more than six times a prohibition's yield.
    assert f"; {_DELIMITER}" in clause
    for perception in ("notices", "thinks", "realis", "wonders", "interior", "point of view"):
        assert perception not in clause.lower()


def test_the_clause_does_not_reach_the_subjectless_import_gloss() -> None:
    """The narrowing §171 chose, pinned so it cannot be widened without a decision.

    §156's first tier has two arms. The one this answers states a rule about people; the other
    is an import gloss with no subject at all, which asserts nothing about anybody in general
    and is the larger of the two on our own shelf. Reaching it would reach ordinary free
    indirect inference and delete presence by construction — §163's lesson about a filter keyed
    too wide, learned in this same constant. The prohibition therefore stays armed by its rule
    about people: strip that phrase and the clause forbids narrated inference itself.
    """
    clause = _clause()
    bare_inference = clause.replace(_GLOSS, "")
    assert "people" not in bare_inference
    assert "which meant" not in house.READER.lower()
    assert "explaining what one person did or said with a rule" in clause


def test_the_clause_carries_no_instance_list_and_no_number() -> None:
    """Two refusals in one, and each has cost this module something already.

    Three clauses here were cut for being recited and each was an instance list; an invented
    instance is the shape that came back as a formula in five listings of eight. And no
    quantity from the census may ride into a prompt: §156's counters read our prose, so a rule
    quoting one of their numbers would be the instrument writing its own instruction.
    """
    clause = _clause()
    assert "—" not in clause
    assert ":" not in clause
    assert not any(character.isdigit() for character in clause)


@pytest.mark.parametrize(
    "word",
    ("kettle", "hollis", "mender", "hurry", "ashamed", "beforehand", "opposite", "twice"),
)
def test_no_word_of_the_chapter_under_read_became_prompt_text(word: str) -> None:
    """§97.1, mechanically, on the draw that produced this entry.

    A defect harvest is the operator's side of the loop and the chapter is a test fixture. A
    word lifted out of it — or out of the read naming it — is that diagnostic laundered into a
    prompt with the evidence still inside, which is the one thing the debugging workflow
    forbids outright. Naming the class needs the words the counter itself is built from, and
    those are the instrument's rather than any read's.
    """
    assert word not in house.READER.lower()


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §171's one clause."""
    assert word not in _clause().lower()


def test_the_clause_does_not_collide_with_the_floor_above_it() -> None:
    """§129's tier order, checked rather than assumed.

    `house.CLARITY` outranks this constant, and the two could have contradicted each other:
    a gloss of this kind makes its moment *more* followable, which is exactly why four reads
    of a clarity floor never caught it. The clause is bounded to the general rule and says
    nothing about explaining in general, so CLARITY's demands are untouched — and where a
    sentence genuinely cannot be followed without one, the tier order decides it and no
    exemption sentence is needed here. An exemption would have been a permission anyway.
    """
    clause = _clause()
    assert "Every sentence can be followed the first time it is read." in house.CLARITY
    assert "somebody works it out, or does not" in house.CLARITY
    assert "follow" not in clause.lower()
    assert "explain" in clause.lower() and _GLOSS in clause


def test_the_gloss_demand_rides_the_scene_writers_live_assembled_prompt() -> None:
    """The clause is worth nothing if it reaches a constant and not a call.

    Named distinctly from `test_scene_economy.py`'s equivalent so a ledger citation resolves
    to one test: `tests/test_architecture.py` checks that a cited name exists, and two files
    sharing one name would make the citation ambiguous rather than wrong.

    `render_prompt` is the path every drafted scene goes through and the floor arrives on it
    through `with_house_rules`. Asserted against the live assembly rather than against
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
            query_id="narratorial-gloss",
            target_logical_id="s1",
            book_id="book",
            branch_id="main",
            base_revision_id="r0",
        ),
    )
    assert _GLOSS in system
    assert _DELIMITER in system
