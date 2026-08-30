"""Stage-0 §176, split by §187: the figure clause moved to the reviser, the scope word stayed.

**The defect this file exists for was not a rule being broken.** Read 10 named three sentences
in one chapter as ones nobody would say: a pronoun whose nearest noun is not the thing it stands
for, a comparison to something that does not have the quality it is made for, and a line of
dialogue naming an object by a description last given a passage earlier. Every demand in
`house.CLARITY` was read against them first, and each missed by its object — the unmet-term
clause fails a *name*, the two-ways clause fails a sentence with two readings *available*, the
object clause fails an object *acting*.

**§176 shipped two edits and §187 treated them differently, which is the finding this file now
holds.** The figure clause is register: its object is how a sentence reads, it is one of the four
clause-addressed families still alive at the thirteenth read, and `plan/agent-impact/` reports no
clause on this floor moving a sentence metric across ten chapters. It left for
`application/reviser.py`, byte-identical. **The pronoun widening did not move and is not
register.** It is antecedent mechanics on a clause read 2 measured — inside a paragraph a pronoun
points at one thing only — and its whole content is whether a reader can work out who the
sentence is about, which is the comprehension side of the line §187 draws. It cost no demand
going in and it costs none staying.
`test_the_pronoun_clause_now_reaches_objects_and_kept_its_remedy` is the one to read.

Four things are asserted, and they fail for four different reasons.

**The object.** `test_the_new_demand_fails_a_comparison_and_not_figuration_at_large` is the
guard that survives the move: scoping the prohibition to comparisons is what keeps it off
ordinary metaphor by construction rather than by exemption, and §163 is the standing record of
what a filter keyed one notch wider costs. It binds harder at the reviser, whose output replaces
every sentence the book ships.

**The boundary.** The concession sits inside the sentence, after a semicolon, so the clause
reaches a comparison the reader cannot complete and never a comparison as such.

**The price, now paid backwards.** §176 raised six ceilings for the figure clause; §187 lowers
them, and `tests/test_prompt_budget.py` owns those numbers. This file owns the shape that keeps
the free half free.

**What is deliberately not reached.** The third instance — a description standing in for a thing
that has a plain name — is refused and stated before the fact, because every wording that
reaches it and the comparison together forbids ordinary anaphora.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import pytest

from litharness.application import planner, reviser
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house

#: The demand §176 added, held by its operative words rather than whole, so a later re-scope of
#: its object does not have to edit an assertion about its punctuation.
_COMPARISON = "a comparison to a thing that does not have the quality"

#: The clause §176 widened. Its scope word is the only thing that moved; the remedy and the
#: concession below are asserted untouched, because a widening that quietly rewrites a measured
#: remedy is a new rule wearing an old sentence. **§187 left this one exactly where it was.**
_PRONOUN = "a pronoun points at one person or object only"


def _clause() -> str:
    """The figure clause at its §187 address. `reviser._TASK` is now its one home."""
    (found,) = [item for item in house.demands(reviser._TASK) if _COMPARISON in item]
    return found


def test_the_figure_clause_left_the_floor_and_the_scope_word_did_not() -> None:
    """§187's split, pinned as one assertion because the split is the decision.

    Two edits shipped together under §176 and only one is register. The comparison prohibition
    is gone from the floor and from every role standing on it; the pronoun's scope word is still
    in `house.CLARITY`, still widened, and still riding every prose call. A later track that
    removes clauses by their entry number rather than by their object breaks this test, which is
    what it is for.
    """
    assert _COMPARISON not in house.CLARITY
    assert _COMPARISON not in house.HOUSE_RULES
    assert _COMPARISON in reviser._TASK
    assert _PRONOUN in house.CLARITY


def test_the_new_demand_fails_a_comparison_and_not_figuration_at_large() -> None:
    """The object that keeps §163's failure mode out of a clause aimed at figures.

    **Repointed to `reviser._TASK` by §187; the assertion is unchanged and that is the claim.**
    The clause moved byte-identical, so the object argued at one address is the object in force
    at the next — and it matters more here, because this stage rewrites every sentence the book
    ships rather than shaping one drafting call.

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
    """Three clauses in `house` were cut for being recited, and each was an instance list.

    §168 and §171 both shipped without one for the same reason, and this clause names a
    configuration rather than a vocabulary, so it has nothing an instance would add.
    """
    clause = _clause()
    assert "—" not in clause
    assert ":" not in clause
    assert clause.count(",") == 0


def test_the_pronoun_clause_now_reaches_objects_and_kept_its_remedy() -> None:
    """The half of read 10 that cost nothing, and the guard on how it cost nothing.

    **The half §187 kept, and the reason is the line that entry draws.** A clause whose object
    is how a sentence sounds went to the reviser; a clause whose object is whether a reader can
    assemble what the sentence says stayed on the floor. This is the second kind: the paragraph
    clause has said since read 2 that inside a paragraph a pronoun points at one person only,
    read 10's first instance is that same mechanism with a thing in the slot, and what is at
    stake is a reader having to reread to find out who is meant.

    A scope word is the whole edit: if the remedy or the concession ever moves, this stopped
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

**The floor read 25, not §176's 26, since §174 landed the same day**: the readership
    clause left `house.READER` for the listing task, so CLARITY's 13 stood beside READER's 11.

    **Corrected in place 2026-08-30, twice, as two more clauses crossed in flight.** §179's
    implication prohibition joined `house.READER` (13 beside 12, floor 26, spending §174's
    headroom), and §181's diction prohibition joined CLARITY (14 beside 12, floor 27 — the
    raise §176.4 predicted, landed one merge later than either track expected;
    `tests/test_prompt_budget.py` carries the six ceilings it moved). The two halves of this
    assertion exist so a later edit has to say which constant it touched.

    **Corrected in place again the same day, and this time both numbers fell** (§187). CLARITY
    14 -> 11: this file's own figure clause left for the reviser, and §180's and §181's went with
    it. The floor 27 -> 22, the two READER removals included. **The scope word is still not in
    either count**, which is the arithmetic this test was written to hold: it was free when it
    arrived and it is free now that its sentence-mate has gone, because a widening is a word and
    not a demand.
    """
    assert len(house.demands(house.CLARITY)) == 11
    assert len(house.demands(house.HOUSE_RULES)) == 22


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
    different chapter: one ledger citation, one test. **Widened by §187 to the clause at its new
    address**, because a rule that travels between prompts could pick up a word on the way, and
    scoped to the clause rather than to the whole instruction for the reason
    `tests/test_plain_diction.py` records against its own version of this test.

    A defect harvest is the operator's side of the loop. A noun lifted out of the chapter under
    read — or a word of the read itself — is that diagnostic laundered into a prompt with the
    evidence still inside, and it is the one thing the debugging workflow forbids outright. The
    three sentences are fixtures in this file's docstring and go nowhere else.
    """
    assert word not in house.HOUSE_RULES.lower()
    assert word not in _clause().lower()


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_the_new_clause_does_not_speak_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §176's one clause."""
    assert word not in _clause().lower()


def test_both_edits_ride_the_scene_writers_live_assembled_prompt() -> None:
    """The name is kept and half of what it asserts is inverted, which is §187's split exactly.

    **Until 2026-08-30 both edits rode this call. One still does.** The pronoun widening is on
    the drafting call's live assembled system message, where pronouns are written; the comparison
    prohibition is not, and rides the reviser instead. Keeping the name is deliberate:
    `tests/test_architecture.py` holds every ledger citation to an existing test, and this file's
    entry is cited — a deleted name breaks the citation and a renamed one resolves to nothing.

    `render_prompt` is the path every drafted scene goes through, and the house floor arrives
    on it through `with_house_rules`. Asserted against the live assembly rather than against
    `HOUSE_RULES`, because a copy is the failure `tests/test_prompt_budget.py` was founded on,
    and an absence read off a constant goes stale silently.
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
    assert _COMPARISON not in system
    assert _PRONOUN in system

    revising = reviser.revision_system()
    assert _COMPARISON in revising
    # The pronoun clause reaches the reviser too, and by a route this track did not touch: the
    # reviser stands on `CLARITY` entire (§185), so the half that stayed is live at both roles.
    assert _PRONOUN in revising
