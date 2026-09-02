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
from pathlib import Path
from typing import Any

import pytest

from litharness.application import (
    concept,
    exemplars,
    overview,
    planner,
    readers,
    recruiter,
    reviser,
    revoice,
    tells_pass,
    titles,
    world_agent,
)
from litharness.cli import EXIT_OK, _prompt_pressure, main
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import extraction as extraction_domain
from litharness.domain import house, tells
from litharness.domain import progression as progression_domain
from litharness.domain import voice as voice_domain
from litharness.domain import writers as writers_domain
from litharness.domain.generation import CompletionRequest

#: One writer, fixed, so a budget is about the rules rather than about whose dossier is longest.
WRITER = writers_domain.CAST["ferreira"]

#: A concept with a second system, the one shape that adds a sentence to the seed (§197).
_TWO_SYSTEM_CONCEPT = concept.Concept.from_payload(
    {
        "person_before": "a physics dropout on nights",
        "exception": "the one the portal failed to kill",
        "first_use": "he walks out of it alive.",
        "want": "to belong in a room",
        "system": {
            "name": "the Tally",
            "manner": "in a clerk's voice.",
            "look": "grey lines on the inside of the eye.",
            "steps": 12,
            "strongest_known": "the seventh step.",
            "pays": "a night without running.",
        },
        "threat": {"what": "what came through with it.", "first_reach": "the market, night one."},
        "turn": {"event": "the portal holds him eleven years.", "when": "before chapter one"},
        "second_system": {
            "name": "the Accord",
            "manner": "as a voice that bargains.",
            "kept": "his endurance.",
        },
        "first_arc": {"opens": "he walks out.", "middle": "an offer.", "closes": "he takes it."},
        "debts": [
            {"subject": "the silence", "owed": "why the Tally went quiet.", "due_scene": 5},
            {"subject": "the years", "owed": "what the portal did with them.", "due_scene": 6},
        ],
    }
)

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
        # **Floorless like the listing, and reader-facing like it** (§197): the concept's
        # rendering is shown to the listing writer as material, so a machinery word in this
        # task is one remove from a reader.
        "concept writer": concept._system(WRITER),
        # **The tells rewriter, one sentence at a time** (§199): reader-facing, since its answer
        # replaces a sentence on the page; three lines and one family's line, the largest of
        # the five shown.
        "tells rewriter": tells_pass.rewrite_system(tells.CHAINED_AND),
        # **The seed with a second system, which only a two-system concept renders.** One
        # sentence over the plain seed row, and a row of its own so the number is visible.
        "architect seed, second system": (
            world_agent.render_seed_request(
                "a listing", WRITER, concept=_TWO_SYSTEM_CONCEPT
            ).system
            or ""
        ),
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
        # **The one row that stands on `CLARITY` and on neither rule below it** (§185, §129's
        # tier order read literally). It is not the floorless case the two rows above are and
        # it is not the whole-floor case the scene writer is: a role whose object is a sentence
        # gets the rule whose every demand has a sentence for its object, and the two rules
        # about what a story contains are refused by a mechanical check one function later.
        "reviser": reviser.revision_system(),
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
    # **The concept writer, new on 2026-09-02** (§197): eleven task sentences and the dossier,
    # set at what is there, like every row since §187. **Raised 15 -> 18 the same day for §198**:
    # the prize a step buys, the want in pre-system words, and the threat, each one sentence,
    # after read 18 found the ladder reaching the page as a number going up for no reason and
    # the arrival of the System met with a clipboard.
    "concept writer": 18,
    # **The tells rewriter, new on 2026-09-02** (§199): the three lines every rewrite carries and
    # the one line for the family, four.
    "tells rewriter": 4,
    # The plain seed's row plus the one second-system sentence.
    "architect seed, second system": 44,
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
    #
    # **Raised 17 -> 18 on 2026-08-30 for the house genre, which had never had a surface at the
    # call that invents the premise** (§183). The genre is mandatory and `domain/genre.py`
    # refuses a book that cannot speak system voice — but that floor sits at the *seed*, which
    # runs after the premise exists, and the listing is the promise a reader buys. Three listings
    # were refused at the coordinator's gate in one day for promising a different kind of book.
    # **A subtraction was looked for first**, in the order this file asks for, and refused at
    # every candidate: the number clause and the format line are measured against this market
    # (§138), the two `house.CLARITY` clauses are a restoration of text lost by accident, and the
    # genre-noun clause is the nearest neighbour and the one §127's brake covers outright —
    # removing it took four writers to 0, 0, 0, 0 of the genre's own nouns, so it encodes a
    # measurement and does not come out against a mood. This row pays alone because it is still
    # the one production role with no house floor under it. The clause is one sentence carrying
    # both halves of the constraint, so it costs one demand here and 236 characters, and both
    # numbers are written down in `application/overview.py` rather than only the one this counter
    # can see (§171's evasion, named against itself).
    #
    # **18 -> 17 on 2026-08-30, and this row falls alone because it stands alone** (§187). §179's
    # implication prohibition shipped at two addresses byte-identical — here and on
    # `house.READER` — and it comes out of both in one edit. Removing only the floor's half would
    # have left a withdrawn rule with its sole home at the one production role that stands on no
    # floor, which inverts §179's own reason for writing it here. This row does not move with
    # `HOUSE_BUDGET`'s five, because no house floor sits under it; its -1 is the clause's own.
    #
    # **17 -> 18 on 2026-09-01, the opening-parity track, and it is one clause re-signed rather
    # than one added.** The task's second sentence forbade the life the person had before the
    # book began, written against listings that opened on backstory. Measured against the
    # market's summits (`research/opening-parity/PREREG.md` §2: the two anchors the operator
    # placed on the shelf and the four highest-follower local LitRPG openings), every blurb
    # gives that life in one plain clause before the thing that changes, and ours gave none —
    # the reader is handed a cook, a mender and an apprentice with nobody to stand beside. The
    # sentence now names both failures, none and more than one, which `house.demands` reads as
    # two demands where it read one.
    "listing writer": 18,
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
    #
    # **48 -> 43 on 2026-08-30, five demands off the floor beneath it** (§187). Four of the five
    # were inert here by the record above — §171's and §176's own raises say so, because the
    # Architect narrates nothing and writes no comparisons — so this row gives back demands it
    # was paying for and could not use, which is §171.4's honest price being unwound. **One of
    # the five was not inert**: §181's specialist's-word prohibition reached this role, since
    # every act it takes is a `world declare` whose subject is a name it chose. That loss is real
    # and is recorded rather than smoothed. `_SYSTEM`'s own naming rule is untouched and still
    # asks for short plain words, so the seed is not left silent on the subject; what it no
    # longer carries is a prohibition on where a word was borrowed from.
    "architect seed": 43,
    # **42 -> 43 on 2026-08-30, the §176 clause.** §163's note above says this row "stays
    # on 42", which was true of §163's seed-only raise and is not a rule: this row stands on the
    # whole house floor, so a floor clause lands here as surely as it lands on the scene writer.
    # Inert at this role for the seed's reason. §173 adds nothing here — its sentence is
    # seed-only.
    #
    # **44 -> 39 on 2026-08-30** (§187), the same five demands off the same floor. Inert here for
    # the seed's reason and for §181's exception too: the grow call declares as the seed does.
    "architect grow": 39,
    # **28 -> 29 and 32 -> 33 on 2026-08-30, the §176 clause.** These two rows are the
    # ones the raise is actually for: the drafting call is where comparisons are written, so
    # this is the one place the demand is neither inert nor a delimiter. The four-demand gap
    # between the rows is the cast dossier and is unchanged.
    #
    # **30 -> 25 and 34 -> 29 on 2026-08-30** (§187), and these two rows are the ones the removal
    # is actually about. The drafting call is where every one of the five clauses was live and
    # none was inert, so this is where the audit's finding bites: five demands rode every scene
    # call of every book, and across ten chapters no sentence metric moved under them. The four
    # that are register are now at the reviser, which is the stage the battery measured moving
    # that axis; §180's is not ported because the reviser's own instruction already carried it.
    # The four-demand gap between the rows is still the cast dossier and is still unchanged.
    "scene writer floor": 25,
    "scene writer, cast": 29,
    "measurement reader": 4,
    "steering reader": 4,
    # Measured 2026-08-28 and set at what was there, the ratchet this file exists to be. Both
    # sit far under the recruiter's 24 because neither carries the house floor and neither has
    # a shape clause; the rewrite is larger than the draw because five gates on what comes back
    # are five things the prompt says will refuse it.
    "revoice draw": 9,
    "revoice rewrite": 14,
    # **The Reviser joined at 28 on 2026-08-30, measured and set at what is there** (§185), so
    # it starts as a ratchet like every row above it. Fourteen of the twenty-eight are
    # `house.CLARITY` entire and move only when the floor does — this row therefore rises with
    # a floor clause exactly as the two Architect rows and the two scene rows do, and a later
    # track adding one should expect **seven** numbers to move rather than six.
    #
    # The other fourteen are the role's own: three of containment stated as instruction, six
    # prohibitions against the structures reads 10 to 12 named, and the rest the frame and the
    # return contract. Every one of the six is prohibition-signed, which
    # `tests/test_reviser.py` asserts over the text rather than about it — §138 measured the
    # permission form of one clause at more than six times the prohibition form and worse than
    # silence, and a role whose whole job is a register is the last place to spend that.
    #
    # **28 -> 30 on 2026-08-30, and this is the only row in this table that rises** (§187). It is
    # two movements in opposite directions netting +2, and both belong in the open. The floor
    # half falls with everything else: `house.CLARITY` 14 -> 11, so the fourteen this row
    # inherited are eleven, and the note above predicting **seven** numbers moving with a floor
    # clause is confirmed in the falling direction. The role's own half rises 14 -> 19: four
    # prohibitions moved here from `house` byte-identical (§171's gloss, §179's absence and
    # restatement, §176's comparison, §181's specialist's word) and one is new — a prohibition
    # on a relation left unstated across a *pair* of sentences, which is the audit's own ask.
    #
    # **This raise is what the removal is for and it is not a subtraction looked for and
    # refused.** The order this file asks for is take something out, then raise what is left on
    # purpose; here the taking-out is the same commit, at six other rows, and the net across the
    # table is strongly negative. What is bought is ownership: the reviser is the one stage the
    # battery measured moving the sentence axis, and two of the four ported clauses are aimed at
    # defects this stage was measured *producing* — the gloss counter reads higher on its prose
    # than on the writer's from the same listing, and the pair clause exists because this stage
    # answered a chained sentence by cutting it in two and leaving the relation unsaid. §180's
    # chained-action prohibition was **not** ported, and that is why the rise is five and not
    # six: this file already carried that prohibition before the floor's copy existed.
    # 30 -> 31 on 2026-09-01 for §194: the located manner-gloss prohibition, reads 13-14's
    # twice-named item, recorded at read 14 as this instruction's next tuning. The reviser
    # is the one role sentence register is added to since §187, so its ceiling moves where
    # the writer-facing ones fell; tested as the turn-3 A/B variant before adoption.
    "reviser": 31,
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
#: **Unmoved on 2026-08-30 by the implication clause (§179), then moved by the diction clause
#: (§181) — the same day, two tracks crossing.** §174 took a demand off this floor the day §176
#: raised six ceilings for one, so every row standing on `house` carried exactly one demand of
#: slack; §179 spent it (one sentence to `house.READER`, no number moved). §181's diction
#: prohibition on the clarity side is the clause after the last free one, and it raises all
#: six: the floor to 27, `architect seed` to 48, `architect grow` to 44, the two scene rows to
#: 30 and 34, `SCENE_MAXIMAL_BUDGET` to 46. That is §176.4's prediction arriving two entries
#: later than it said. The listing pays separately (17 since §179), the one role with no floor
#: under it.
#:
#: **And unmoved again by §180 the same day, by subtraction**: the chained-sentence prohibition
#: went onto `house.CLARITY` and `CLARITY`'s closing line came off in the same edit — the
#: subtraction §176.5 looked for and half-refused (it protects the rule's *opening* sentence,
#: which carries a twice-made correction under §127's brake; the closing one restates a
#: standard, encodes no measurement, and by §154 is the half a writer cannot act on). Four
#: house edits in one day: the ceilings moved once, for §181, and this note is the crossing
#: written down.
#:
#: **27 -> 22 on 2026-08-30, and it is the first fall this number has ever taken** (§187). Every
#: raise recorded above bought a clause; this one removes five, and the reason each came out is
#: written on its own clause in `domain/house.py`. **The measurement is `plan/agent-impact/` and
#: the direction is the operator's, which is what §127's brake asks for.** That brake is against
#: removing a rule which encodes a measured correction *against a mood* — §176.5 and §181 both
#: cite it, and both were right to, because neither of those tracks had a measurement. This one
#: has the audit: every defect family still alive at the thirteenth read is clause-addressed, no
#: clause on this floor moved a sentence metric across ten chapters, and one of the four removed
#: was recorded being broken on the very next read after it shipped. The operator's word at that
#: report — take the register clauses out of the prompts — is the other half.
#:
#: **What left, by constant.** `CLARITY` 14 -> 11: §176's comparison prohibition, §180's
#: chained-action prohibition, §181's specialist's-word prohibition. `READER` 12 -> 10: §171's
#: narratorial gloss, §179's absence-and-restatement prohibition. `ACCUMULATION` is untouched at
#: one. **What stayed and why the line falls where it does**: a clause whose object is how a
#: sentence sounds went, and a clause whose object is whether a reader can assemble what it says
#: stayed — so the unmet-term pair, the two-ways clause, the object-acting clause and the
#: paragraph trio are all still here, and §176's pronoun scope word stays with the paragraph
#: clause it widened, being antecedent mechanics rather than register. §168's passage clause
#: stays for a second reason: the reads stopped naming its family.
#:
#: **Five rows fall with this one and one rises.** The floor lands once in each row standing on
#: it: `architect seed` 48 -> 43, `architect grow` 44 -> 39, the two scene rows 30 -> 25 and
#: 34 -> 29, `SCENE_MAXIMAL_BUDGET` 46 -> 41. The listing pays its own -1, and the reviser rises
#: +2 net; both are written on their own rows. **Every number here is set at what is now there
#: rather than left high**, which is the opposite of what §174's note says about counts moving
#: down arguing for nothing — that entry declined to *lower* a ceiling as an argument, and this
#: one lowers them so the next clause added to this floor has to be a decision again rather than
#: slack somebody found. A ratchet that keeps five demands of headroom is not a ratchet.
HOUSE_BUDGET = 22


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
_OFFER_LINE = "[OFFER] warrant — hull: opens binding, carrying | watch: opens appraising"
#: A shelf of one short exemplar (§196). Its text lands in the *prompt*, which this file does
#: not count; what the system gains is `SHELF_SYSTEM`, one sentence, priced below.
_SHELF = exemplars.Shelf(
    root=Path(),
    exemplars=(
        exemplars.Exemplar(
            name="Placed", title="Placed", chapter="One opening.", blurb=None,
            digest="0" * 16, words=2,
        ),
    ),
)
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
    "offer_line": ({"status_example": _STATUS_EXAMPLE}, {"offer_line": _OFFER_LINE}),
    "exemplars": ({}, {"shelf": _SHELF}),
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
    # **Joined 2026-09-01 at what is there, the opening-parity track**: one sentence saying the
    # book prints the fork where it is put in front of the person, and the line itself. Nested
    # inside `status_example` because a fork needs the sheet it is a fork in. The ways and what
    # each opens are the book's own words (`gamesystem.offer_line`), so the payload line is
    # furniture and not a demand about prose.
    "offer_line": 2,
    # **Joined 2026-09-02 at what is there** (§196): the one sentence saying whose the shelf's
    # chapters are and that no name, place, thing or line of theirs may appear. The chapters
    # themselves are material in the prompt and are not demands.
    "exemplars": 1,
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
#:
#: **46 -> 41 on 2026-08-30** (§187), by that same arithmetic run backwards: five demands off the
#: floor, once each in this total. The off-by-one against the summed rows is unchanged and is
#: still the length ask's leading space, which is the check that this fell by the floor's five
#: and not by anything in the conditional region — `SCENE_CONDITIONAL_BUDGET` is untouched, and
#: no branch in `planner.py` was edited by this track. **This is the number the audit's finding
#: is about**: it is the largest prompt a scene drafter is ever sent, five of its demands were
#: register clauses, and no sentence metric moved under them across ten chapters.
#:
#: **41 -> 43 on 2026-09-01 for the `offer_line` conditional** (the opening-parity track): the
#: one new branch in `planner.render_prompt`, priced at its own row above and landing twice here
#: as one sentence and one furniture line. The off-by-one against the summed rows is unchanged.
#:
#: **43 -> 44 on 2026-09-02 for the `exemplars` conditional** (§196): one sentence in the system
#: when a shelf is shown, and the shelf's chapters in the prompt where nothing here counts them.
SCENE_MAXIMAL_BUDGET = 44


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


#: **The one branch that swaps rather than appends, and its budget is zero** (§186). On a scene
#: whose plan named a quantity as moving, the furniture ask shows the line the scene *leaves*
#: instead of the line it entered: one sentence is replaced by one sentence and one payload line
#: by one payload line, so the demand count cannot move and the row is a floor of nothing rather
#: than a ceiling on something. It is deliberately not an arm of `_CONDITIONAL_ARMS` — that
#: parametrisation asserts `block_text.startswith(base_text)` and `added >= 1`, both of which are
#: properties of a branch that *adds*, and neither of which this branch has or should acquire.
SCENE_MOVED_DEMANDS = 0

_STATUS_MOVED = progression_domain.MovedLine(
    line=extraction_domain.render_status_line(
        "Kestrel", {"level": 4, "hp": 18, "hp_max": 20, "mp": 6, "mp_max": 10, "gold": 12}
    ),
    name="Level",
    was=3,
    now=4,
)


def test_showing_the_line_a_scene_leaves_costs_no_demand() -> None:
    """§186's whole cost, measured over the live assembly rather than argued.

    The scheduled arm and the unscheduled one make the same number of demands because the
    scheduled one adds nothing: the two sentences after the payload line are the same string on
    both, and what differs is one clause and one set of numbers. A later edit that appends to
    this branch instead of swapping inside it lands here as a non-zero difference.
    """
    entering = _scene_system(status_example=_STATUS_EXAMPLE)
    leaving = _scene_system(status_example=_STATUS_EXAMPLE, status_moved=_STATUS_MOVED)

    assert leaving != entering
    added = len(house.demands(leaving)) - len(house.demands(entering))
    assert added == SCENE_MOVED_DEMANDS, (
        f"the moved status example now adds {added} demands where it is meant to add none. It "
        "swaps one sentence and one line; if it has started appending, say why here."
    )
    # And one printable line reaches the writer either way — §161.3's cardinality is the reason
    # the entering line is replaced rather than joined by the moved one.
    assert leaving.count("[STATUS]") == entering.count("[STATUS]") == 1


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
            offer_line=_OFFER_LINE,
            shelf=_SHELF,
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
#: **The Reviser is here and it is the least optional of the five** (§185). Every other row
#: shapes text a reader meets at one remove; this one rewrites the book's own sentences, so a
#: machinery word in it reaches the page directly. §120's instance — `standing` arriving in a
#: chapter as a thing a girl could be hot at — is the failure this rail exists for, and a role
#: whose output *replaces* drafted prose is where it would cost the most.
READER_FACING = (
    "listing writer",
    "concept writer",
    "tells rewriter",
    "title writer",
    "measurement reader",
    "steering reader",
    "reviser",
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
        "concept",
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
        "reviser",
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
