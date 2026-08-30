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

import json
from typing import Any

import pytest

from litharness.application import (
    overview,
    planner,
    readers,
    recruiter,
    revoice,
    titles,
    world_agent,
)
from litharness.cli import EXIT_OK, _prompt_pressure, main
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import extraction as extraction_domain
from litharness.domain import house
from litharness.domain import voice as voice_domain
from litharness.domain import writers as writers_domain
from litharness.domain.generation import CompletionRequest

#: One writer, fixed, so a budget is about the rules rather than about whose dossier is longest.
WRITER = writers_domain.CAST["ferreira"]

#: A descriptor with the shape a real one has and none of its provenance. The numbers do not
#: matter to a demand count and are never sent anywhere from this file; what matters is that
#: `render_exemplar_request` cannot be called without one, which is the design rule this
#: fixture inherits rather than works around.
DESCRIPTOR = voice_domain.StyleDescriptor(
    sentence_words_mean=11.5,
    sentence_words_sd=6.0,
    sentence_words_p10=3.0,
    sentence_words_p50=10.0,
    sentence_words_p90=21.0,
    paragraph_sentences_mean=2.5,
    connective_density=5.25,
    person=voice_domain.Person.THIRD,
    tense=voice_domain.Tense.PAST,
)


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
        "scene writer floor": (
            floor := house.with_house_rules(
                "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
                "no commentary, no summary of what you wrote. The context below is established and "
                "may be relied on; do not contradict it."
            )
        ),
        # **The floor plus who is writing, which was unreachable until 2026-08-25.**
        # `render_prompt` has taken a dossier since 2026-08-20 and `make_plan_selector` had no
        # way to pass one, so the row above was the whole of what a drafter was ever sent. It
        # is a separate row rather than a replacement because `None` is still the default and
        # still the control, and the two totals are four demands apart.
        "scene writer, cast": f"{WRITER.render()}\n\n{floor}",
        "measurement reader": readers.pool(readers.MEASUREMENT)[0].system(),
        "steering reader": readers.pool(readers.STEERING)[0].system(),
        # **Three rows rather than one, because the three dossier forms are three prompts.**
        # They differ by one clause and by nothing else, so a divergence between them is a
        # divergence in the registered arm rather than in the role, and one number could not
        # show it.
        "recruiter, single image": (
            recruiter.render_recruit_request("cozy-fantasy", shape="single-image").system or ""
        ),
        "recruiter, several with beat": (
            recruiter.render_recruit_request(
                "cozy-fantasy", shape="several-with-beat"
            ).system
            or ""
        ),
        "recruiter, several no beat": (
            recruiter.render_recruit_request("cozy-fantasy", shape="several-no-beat").system
            or ""
        ),
        # **Two rows, and both are deliberately floorless**, which is why they are small. A
        # passage nobody reads becomes the paragraph that rides the system message of every
        # scene call its writer ever makes, so `revoice` inherits `recruiter`'s recorded
        # reason for carrying no craft doctrine of its own rather than the scene writer's
        # reason for carrying all of it.
        "revoice draw": (
            revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR).system or ""
        ),
        "revoice rewrite": (
            revoice.render_rewrite_request(
                dossier=WRITER.dossier, exemplar="A passage."
            ).system
            or ""
        ),
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
#:
#: **14 -> 15 on 2026-08-26, and it is a restoration rather than a growth.** Two of
#: `house.CLARITY`'s six clauses came back to this call: the unmet-term clause and the paragraph
#: clause. Both were lost when the house floor was stripped to stop the cramming, and both are
#: the operator's named complaints about *Patch Notes For Earth* — *"wtf is a patch of notes"*
#: and *"sentences don't have relations to each other"*. What makes this a raise worth making
#: rather than §127's fourth rule is that the text already exists in `house` and reaches every
#: other role; the listing was the one call it had been dropped from.
#: **The Recruiter joined at 24 on 2026-08-28, measured and set at what is there**, so it starts
#: as a ratchet rather than as a cut somebody has to justify twice. Eight of the twenty-four are
#: its tool essay, which is the half a role holding commands cannot do without, and the rest is
#: the shelf, the appetite rule, the R1 refusal, the form and the one shape clause. It sits
#: between the listing's 15 and the Architect's 42, and it carries **no house floor at all** —
#: which is the reason it is this small and is a decision recorded in `application/recruiter.py`
#: rather than an economy: a role whose output rides in every scene call may not be told what
#: good prose is, because the paraphrase would ride there with it.
#:
#: Three rows at the same number because the three forms differ by one clause. If they ever
#: diverge, the divergence is in the registered arm rather than in the role.
BUDGET: dict[str, int] = {
    "title writer": 10,
    "title lookup": 6,
    # **Raised 24 -> 25 on 2026-08-29, deliberately and for one named sentence.** The house
    # genre had been living nowhere (`plan/house-genre-constraint.md`; pilot 13 §8.2), carried
    # by whichever dossiers happened to be system-shaped, and the first recruit whose was not
    # drew a book with no system in it. The sentence added to `_RECRUIT` names the mechanical
    # floor that now refuses such a book rather than naming the genre — §136's reason — and it
    # is prohibition-shaped rather than a recipe, which is §138's. This is the choice this file
    # asks for: take something out, or raise the number on purpose and say why. Nothing was
    # taken out, because the twenty-four that were here are the tool essay and the refusals,
    # and the recruiter still carries no house floor.
    "recruiter, single image": 25,
    "recruiter, several with beat": 25,
    "recruiter, several no beat": 25,
    # **Raised 15 -> 16 on 2026-08-30, and the demand it pays for arrived from another row**
    # (§174). The standing readership direction — the protagonist's pre-story life is one the
    # audience has lived — was live prompt text in `house.READER`, and this is the one role that
    # does not stand on the floor, so the call that decides who a book's person is was the single
    # call the direction never reached. Moving it here costs a demand that the floor gives back:
    # `house-floor` goes 25 -> 24 in the same commit and every row standing on it drops by one,
    # which is this table's own trade made in the order it asks for — take something out, then
    # raise what is left on purpose. No ceiling below was lowered to match, because every number
    # here is a maximum and §154's precedent is that counts moving down argue for nothing.
    #
    # **Raised 16 -> 17 on 2026-08-30 for one sentence, and this row is the one the read named**
    # (§179). Read 11 flagged a construction — a narrator asserting an absence or a universal
    # access the surrounding words already give — and both of its instances are in a **listing**,
    # which is the one production role that does not stand on the house floor. So the clause
    # `house.READER` gained the same day could not reach the artifact the defect was found in,
    # and the same sentence ships at both addresses, byte-identical and asserted so by
    # `tests/test_implication_register.py`. **A subtraction was looked for first**, which is the
    # order this file asks for, and there is none available that §138 has not already priced: the
    # format line and the number clause are measured against this market, the two `house.CLARITY`
    # clauses are a 2026-08-26 restoration of text lost by accident, and §174's demand is one day
    # old. So it pays here and says why. The floor's own six rows do **not** move for this clause
    # — see `HOUSE_BUDGET`.
    "listing writer": 17,
    # **Raised 42 -> 44 on 2026-08-29, for three sentences that replace an absence** (§163).
    # The seed ask named a ladder and named nothing that hands out its rungs, so the model
    # supplied the nearest issuer it knows and the book got an institution: pilot 14's
    # scheduled progression beats fired on time and landed in guild paperwork ranks
    # (`plan/first-principles-litrpg-core.md` §2). `_SYSTEM` is the occupant. It went in at six
    # sentences and was cut to three against this ceiling, which is the trade this file asks
    # for made in the order it asks for it — take something out first, then raise what is left
    # on purpose. Nothing else came out: the seed's own ask was re-aimed rather than extended,
    # so the capability half moved into `_SYSTEM` instead of being stated twice.
    # `architect grow` is untouched at 41 and stays on 42; advancement is the beats' path and
    # the grow ask already covers what a chapter made true.
    #
    # **Raised 44 -> 45 on 2026-08-29 for one house clause, and the raise is where a house edit
    # surfaces** (§171). The floor carried one demand of headroom against `HOUSE_BUDGET` and this
    # row carried none, so the floor's slack was unusable without moving this number — which is
    # the inconsistency this table exists to make visible rather than a cost of the clause. The
    # occupant is `house.READER`'s narrating-the-inference prohibition, at the third
    # read-confirmed sighting of a construction §156 measured above the genre's own rate. Nothing
    # came out to pay for it and the alternatives were both worse: hanging it off an existing
    # sentence would have cost zero demands by evading this counter, and putting it in the
    # drafting call's own prompt would have put craft doctrine back in a role file, which is the
    # failure `domain/house.py` exists to end. **At this role it lands inert** — the Architect
    # declares a world through tools and narrates nothing, so by §154 the referent is empty — and
    # that is the honest price: a demand the seed cannot use, against a rule the roles that write
    # prose need in the one place that does not drift.
    #
# **Raised 45 -> 46 on 2026-08-30 for one `house.CLARITY` clause** (§176), and this is the
    # first raise since §171 predicted its own successor's cost. It predicted four numbers; the
    # true count is six, corrected in place at §171.4 — the floor plus **five** rows carry the
    # whole of `HOUSE_RULES` and every one of them sat at zero headroom. The occupant is a
    # prohibition against a comparison to a thing lacking the quality compared for, at the
    # fourth read to name the figure-clarity family and the first clause of any kind against
    # it. **At this role it lands inert** — the Architect declares a world through tools and
    # writes no comparisons, so by §154 the referent is empty — which is §171's honest price
    # paid again at the same address and for the same reason.
    #
    # **And 46 -> 47 the same day for one sentence that is not inert** (§173). Read 10's
    # central item is that a rendered status line arriving at a number-move reads as noise
    # because the system is not a thing anybody in the book opens or weighs, and that the
    # deliberation over what to take next is a large part of what a reader of this genre is
    # here for. `gamesystem.SystemDef` had a graph, a ladder and a scale and **no fork**;
    # `plan/house-genre-constraint.md` had queued exactly that gap. `_SYSTEM`'s fourth
    # sentence is the ask for one, and it lands at the only role whose act is a `world
    # declare`, which is what makes it addressable here (§154) where the §176 clause above is
    # not. **The alternative was measured and refused**: the three predicates are also written
    # into `world vocabulary`, which costs nothing because that command's output is a tool
    # result and not a counted prompt — and §163's own finding is that an omission from *that*
    # surface is indistinguishable from a prohibition. Documenting alone would have shipped a
    # schema no world ever declares, which is §160's history exactly. The two raises crossed
    # in flight on separate tracks; each names its own occupant, and this row carries both.
    "architect seed": 47,
    # **42 -> 43 on 2026-08-30, the §176 clause.** §163's note above says this row "stays
    # on 42", which was true of §163's seed-only raise and is not a rule: this row stands on the
    # whole house floor, so a floor clause lands here as surely as it lands on the scene writer.
    # Inert at this role for the seed's reason. §173 adds nothing here — its sentence is
    # seed-only.
    "architect grow": 43,
    # **28 -> 29 and 32 -> 33 on 2026-08-30, the §176 clause.** These two rows are the
    # ones the raise is actually for: the drafting call is where comparisons are written, so
    # this is the one place the demand is neither inert nor a delimiter. The four-demand gap
    # between the rows is the cast dossier and is unchanged.
    "scene writer floor": 29,
    "scene writer, cast": 33,
    "measurement reader": 4,
    "steering reader": 4,
    # Measured 2026-08-28 and set at what was there, the ratchet this file exists to be. Both
    # sit far under the recruiter's 24 because neither carries the house floor and neither has
    # a shape clause; the rewrite is larger than the draw because five gates on what comes back
    # are five things the prompt says will refuse it.
    "revoice draw": 9,
    "revoice rewrite": 14,
}

#: The floor everything else inherits. Broken out because a clause added here is added to every
#: role at once, which is exactly how the scene writer reached twenty-seven without a decision.
#:
#: **25 -> 26 on 2026-08-30, and this row is where the reason for all six raises belongs** (§176).
#: Read 10 named three sentences nobody would say, and every demand on the floor was read against
#: them first (§154's audit order): the unmet-term clause fails a *name*, and none of the three
#: carries one; the two-ways clause fails a sentence with two readings available, and these have
#: one reading each and it is the wrong one; the object clause fails an object *acting*, and a
#: quality is not an act. What was left were the two sentences that open and close the rule, and
#: those name the standard rather than a page surface — the half a writer cannot act on. So the
#: gap was structural, which is the only thing §168.2 licenses a new clause for.
#:
#: **The subtraction was looked for first and refused, which is the order this file asks for.**
#: The candidate was `CLARITY`'s own opening sentence: affirmative, its object an abstraction,
#: unaddressable, and §168 removed one of exactly that shape to pay for its clause. It stays,
#: because its second half carries the following-rather-than-explaining correction this constant
#: was corrected twice in one day to get, and §127 is explicit that removing a rule which encodes
#: a measured correction is a decision to be made against a measurement rather than against a
#: mood. This track has no measurement, so it pays at the ceiling instead and says so.
#:
#: **The pronoun half of the same read cost nothing.** Widening the paragraph clause's scope from
#: one *person* to one person or object is a scope word on a rule whose object, remedy and
#: concession are untouched, so `house.demands` reads the same count — §161.5's in-place pattern,
#: widened rather than narrowed. Only the figure half needed a sentence.
#:
#: **Unmoved on 2026-08-30 by the implication clause, and the standing headroom is now spent**
#: (§179). §174 took a demand off this floor the same day §176 raised six ceilings for one, so
#: every row standing on `house` has been carrying exactly one demand of slack: the floor at 25
#: against this 26, `architect seed` at 46 against 47, `architect grow` at 42 against 43, the two
#: scene rows at 28 and 32 against 29 and 33, and `SCENE_MAXIMAL_BUDGET` at 44 against 45. One
#: sentence added to `house.READER` lands once in each and moves no number here. **That is the
#: last free clause**: the next one added to the floor raises all six, which §171.4 and §176.4
#: each had to discover by arithmetic — writing it down before the fact is what this table is
#: for. The listing pays separately and does move, because it is the one role with no floor
#: under it.
HOUSE_BUDGET = 26


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


# ---------------------------------------------------------------------------
# The conditional region of the scene prompt — §161.8's named gap.
#
# The two scene rows above are the floor and the floor plus a dossier, and everything
# `planner.render_prompt` appends *per book state* — the status-line ask, the progression
# milestone, the standing schedule, its printed-line form, the length ask, the criterion brief —
# sat outside every row in `BUDGET`. Three tracks edited clauses in that region in one week and
# each computed its before-and-after by hand, which is this file's founding failure one level
# down: text that is sent and that no number describes.
# ---------------------------------------------------------------------------

#: The smallest inputs `render_prompt` accepts. The conditional region lives entirely in the
#: system message and everything book-shaped lives in the prompt, so an empty packet loses
#: nothing this file measures. It also renders **no locked block**, which is a decision rather
#: than a convenience: `render_constraints` grows one line per locked item, so a ceiling over it
#: would be a ceiling on how much a director may lock — book data, not rule text, and rule text
#: is what this file ceilings.
_BEAT = beats_domain.Beat(
    logical_id="s1",
    ordinal=1,
    of_total=1,
    title=None,
    function="setup",
    template_id=beats_domain.SIX_BEAT.template_id,
)

_PACKET = context_domain.ContextPacket(
    query_id="prompt-budget",
    target_logical_id="s1",
    book_id="book",
    branch_id="main",
    base_revision_id="r0",
)

#: Payloads with the shape the real extractors produce and none of their provenance —
#: `DESCRIPTOR`'s convention. The two status lines go through `render_status_line` itself, so
#: the default sheet's shape cannot drift away from what this file measures; the other three
#: are written to their renderers' documented one-line forms (`standing_target`'s sentence,
#: `GraphLine.render`, `criterion_brief`'s `- criterion: comparator — ladder` line).
#:
#: **Every payload is held to one line, and that is the convention rather than an accident.**
#: `house.demands` counts what the payload occupies, so a brief with three declared criteria
#: costs two more than this fixture does. That spend is the book's — it scales with what a world
#: declares, not with what anybody wrote in `planner.py` — and a ceiling that moved when a world
#: declared a second criterion would be a ceiling on worlds. One line prices the instruction
#: clauses plus the payload's floor, which is the half a track editing clauses can change.
_STATUS_EXAMPLE = extraction_domain.render_status_line(
    "Kestrel", {"level": 3, "hp": 18, "hp_max": 20, "mp": 6, "mp_max": 10, "gold": 12}
)
_PROGRESSION = extraction_domain.render_status_line(
    "Kestrel", {"level": 4, "hp": 20, "hp_max": 20, "mp": 8, "mp_max": 10, "gold": 30}
)
_STANDING = "Kestrel stands at courier (1 of 3); the book's plan has them at gate-runner (2 of 3)"
_STANDING_LINE = "[STANDING] Kestrel stands at courier"
_CRITERIA = "- guild_rank: outranks — courier then gate-runner then warden"


def _scene_system(**conditionals: Any) -> str:
    """The system message the planner actually assembles, through the live path."""
    system, _prompt = planner.render_prompt(
        _BEAT, book_title=None, packet=_PACKET, **conditionals
    )
    return system


#: Each block against the smallest prompt that can carry it, because two of the branches are
#: nested: `progression` renders only inside `status_example`'s branch and `standing_line` only
#: inside `standing`'s, so their cost is measured over a base that already pays for the parent.
_CONDITIONAL_ARMS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "status_example": ({}, {"status_example": _STATUS_EXAMPLE}),
    "progression": ({"status_example": _STATUS_EXAMPLE}, {"progression": _PROGRESSION}),
    "standing": ({}, {"standing": _STANDING}),
    "standing_line": ({"standing": _STANDING}, {"standing_line": _STANDING_LINE}),
    "target_words": ({}, {"target_words": 900}),
    "criteria": ({}, {"criteria": _CRITERIA}),
}

#: **Measured 2026-08-29 and set at what was there**, the ratchet this file exists to be: this
#: change raises nothing, and a ceiling here moves only in a later, deliberate commit with the
#: reason written down. The counts are marginal demands — what the branch adds to its base arm —
#: because that is the number the three tracks were computing by hand, and each is the
#: instruction's clauses plus one line of payload under the one-line convention above.
SCENE_CONDITIONAL_BUDGET: dict[str, int] = {
    "status_example": 4,
    "progression": 3,
    "standing": 3,
    "standing_line": 2,
    "target_words": 3,
    "criteria": 2,
}

#: The whole assembled scene prompt — floor plus every conditional present — which until now had
#: no number anywhere. **43 rather than the 44 the rows sum to, and the difference is real
#: rather than rounding**: the length ask is appended with a leading space, so when the standing
#: line's unterminated `[STANDING] …` tail is the text before it, `house.demands` reads the two
#: as one clause. The assembly is what a model is sent, so the assembly is what is priced. The
#: cast dossier is not in this row because its four demands are already the gap between the two
#: scene rows in `BUDGET`; measured with it, the total is 47, exactly additive.
#:
#: **43 -> 44 on 2026-08-29, the same house clause and the same raise as `architect seed`**
#: (§171). One demand added to the floor lands once in this total, which is what this row was
#: built to show: the drafting call is the role the narrating-the-inference prohibition is
#: actually for, and it is the one row here where the demand is not inert. The off-by-one against
#: the summed rows above is unchanged and still the length ask's leading space.
#:
#: **44 -> 45 on 2026-08-30 for one `house.CLARITY` clause** (§176), by the same arithmetic: one
#: demand on the floor, once in this total, and the off-by-one against the summed rows is still
#: the length ask's leading space. This is the sixth of the six numbers that clause moved, and
#: the reason for all of them is written at `HOUSE_BUDGET`.
SCENE_MAXIMAL_BUDGET = 45


def test_the_scene_floor_row_is_what_the_planner_actually_assembles() -> None:
    """The floor row above is a copy of `render_prompt`'s opening string, and copies drift.

    Until now nothing tied the copy to the live path: a track rewording the floor inside
    `planner.py` would leave `BUDGET`'s row measuring a prompt nobody sends, which is this
    file's founding failure wearing the file's own clothes.
    """
    assert _scene_system() == _roles()["scene writer floor"]


@pytest.mark.parametrize("block", sorted(SCENE_CONDITIONAL_BUDGET))
def test_a_scene_conditional_block_stays_inside_its_declared_budget(block: str) -> None:
    """No conditional branch grows without somebody choosing to let it.

    §161.5 edited two clauses in this region and had to prove demand-neutrality by hand;
    §161.8 named the absence of these rows as a live gap. The marginal count is computed over
    the live assembly path, so a clause added to a branch in `planner.py` lands here the same
    way a clause added to `house` lands in every role row.
    """
    base_kwargs, block_kwargs = _CONDITIONAL_ARMS[block]
    base_text = _scene_system(**base_kwargs)
    block_text = _scene_system(**base_kwargs, **block_kwargs)
    # The branch appends, so the base survives verbatim and the subtraction below is the
    # block's own cost rather than a difference between two unrelated prompts.
    assert block_text.startswith(base_text)
    added = len(house.demands(block_text)) - len(house.demands(base_text))
    assert added >= 1, (
        f"the {block} branch rendered nothing, so this row is measuring an absence — "
        "if the branch moved or was renamed, move this arm with it"
    )
    assert added <= SCENE_CONDITIONAL_BUDGET[block], (
        f"the scene prompt's {block} block now adds {added} demands against a budget of "
        f"{SCENE_CONDITIONAL_BUDGET[block]}. Take one out, or raise the budget here and say "
        "why. Every demand in this block rides every scene call of every book that declares "
        "the state it describes."
    )


def test_the_maximal_assembled_scene_prompt_stays_inside_its_declared_budget() -> None:
    """The largest prompt a scene drafter can be sent finally has a number.

    Floor plus every conditional, through the live path. This is the total the per-block rows
    cannot see: blocks join with spaces and newlines, and what a model reads is the join.
    """
    counted = house.demands(
        _scene_system(
            status_example=_STATUS_EXAMPLE,
            progression=_PROGRESSION,
            standing=_STANDING,
            standing_line=_STANDING_LINE,
            target_words=900,
            criteria=_CRITERIA,
        )
    )
    assert len(counted) <= SCENE_MAXIMAL_BUDGET, (
        f"the maximal assembled scene prompt now makes {len(counted)} demands against a "
        f"budget of {SCENE_MAXIMAL_BUDGET}. Take one out, or raise the budget here and say "
        "why.\n" + "\n".join(f"  {index + 1:2d}. {item}" for index, item in enumerate(counted))
    )


#: Roles whose prompts shape prose a reader will read. The exemptions are the two kinds of call
#: that must name the machinery to work at all: a schema-filling call has to name the fields it
#: fills, and the Architect's tool essay has to name the commands it runs.
#:
#: **`title lookup` is not here, and the boundary is the one `house` already states**: what the
#: text shapes, not where it lives. That role reports what other people have published and
#: shapes no word a reader of this book will read. `title writer` shapes the few words above
#: the blurb, so it is.
#:
#: **The three Recruiter rows are not here either, and the case is the Architect's**: a tool
#: essay has to name its commands. It is the closer call of the two, because what a Recruiter
#: writes is rendered into the system message of every scene call — so
#: `test_the_recruiter_prompt_is_a_tool_essay_and_would_pass_the_leak_rail_anyway` measures the
#: rail it is exempt from, and it passes. An exemption nobody checks is an exemption that grows.
READER_FACING = (
    "listing writer",
    "title writer",
    "measurement reader",
    "steering reader",
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


def test_effective_input_counts_system_schema_and_declared_tools() -> None:
    request = CompletionRequest(
        prompt="material",
        system="role",
        schema={"type": "object"},
        allowed_tools=("Bash(litharness world:*)",),
    )
    assert request.schema_instruction
    assert request.input_chars == sum(
        (
            len(request.prompt),
            len(request.effective_system),
            len(",".join(request.allowed_tools)),
        )
    )
    assert request.input_chars > len(request.prompt)


def test_prompt_inspector_covers_every_production_communication_role(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["prompts", "--json"]) == EXIT_OK
    rows = json.loads(capsys.readouterr().out)
    assert {
        "listing",
        "title",
        "title-lookup",
        "architect-seed",
        "architect-grow",
        "recruit-single-image",
        "recruit-several-with-beat",
        "recruit-several-no-beat",
        "outline",
        "narrative-planner",
        "scene",
        "summarizer",
        "director",
        "reader-measurement",
        "reader-steering",
        "repair",
    } <= set(rows)
    assert all(row["input_chars"] >= row["prompt_chars"] for row in rows.values())
    assert rows["summarizer"]["schema_chars"] > 0


def test_representative_prompt_inspection_labels_itself_and_carries_material(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["prompts", "--role", "scene", "--json"]) == EXIT_OK
    row = json.loads(capsys.readouterr().out)

    assert row["source"] == "representative_specimen"
    assert "AUTHOR-LOCKED STORY DECISIONS" in row["system"]
    assert "Who is in this story" in row["prompt"]
    assert len(row["prompt"]) > 500


def test_prompt_pressure_names_section_dominance_and_exact_repetition() -> None:
    request = CompletionRequest(prompt="- Same debt!\n- same debt\n- another fact")
    pressure = _prompt_pressure(
        request,
        context={
            "items": 40,
            "tokens": 1000,
            "budget": 2000,
            "sections": {"threads": 34, "facts": 6},
        },
    )

    assert pressure["dominant_sections"] == [{"section": "threads", "items": 34, "share": 0.85}]
    assert pressure["repeated_material_lines"] == [{"text": "same debt", "occurrences": 2}]
