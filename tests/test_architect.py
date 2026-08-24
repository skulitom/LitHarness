"""The Architect: the gates a forged world clears, and the ordering it is forbidden to do.

Grades `plan/world-architect.md` §2's three rails and §4's collapse refusal. What it deliberately
does **not** grade is whether any world is good — there is no quality ordering over worlds in this
project, `test_the_architect_ranks_nothing_and_cannot_learn_to` enforces the absence by import
ban rather than by intent, and every claim about a world here is arithmetic over its own records.

The end-to-end test runs the seam that matters: a bundle written to disk, `forge --pick`, then
`new --state … --promises …`, with **no provider call anywhere in it**. That is the path
`tools/serial-pilot-2-setup.ps1` walks, so a break in it fails here rather than nine ticks into a
pilot.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import litharness_contracts as lc
import pytest

from litharness.application import architect
from litharness.cli import main
from litharness.domain import worlds
from litharness.domain.findings import DetectorInput
from litharness.domain.integrity import detect_cardinality_violations
from litharness.domain.promises import PROMISE_OPEN
from tests.conftest import BOOK_ID, BRANCH_ID


def world(
    *,
    title: str = "The Long Weight",
    domain: str = "assay and provenance",
    geometry: str = "graph",
    rule_domains: tuple[str, ...] = ("economy", "law", "daily_life"),
    answer: str = "the tide is aimed at the assay house, not the city",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A world that clears every gate, so a test can break exactly one thing at a time."""
    built: dict[str, Any] = {
        "title": title,
        "domain": domain,
        "geometry": geometry,
        "progression_means": "your read of a thing gets longer, never stronger",
        "inversion": "no combat class exists; the removed slot is filled by standing",
        # **Written as the protagonist's situation and naming him**, which is what the rule
        # added on 2026-08-22 asks a world for and what `gate_candidate` checks arithmetically.
        # It still varies with `domain`, so two fixtures built from different domains carry
        # different premises and the collapse gate has something to compare.
        "premise": (
            f"Silas, a junior hand in {domain}, is the one the provenance rule does not bind."
        ),
        "protagonist": {
            "id": "silas",
            "exception": "provenance",
            "edge": "he prices a thing the assay has not seen, and the price holds",
            # The same string the cast entry carries: two declarations of one fact produce one
            # record, because `records_for` keys on content and `add` drops the duplicate.
            "wants": "to be read once by someone who matters",
            "price": "every reading he signs is checked twice, and the second check is not his",
            # Below the top of the one ordinal chain this world declares, which is what the rule
            # added on 2026-08-22 asks for and what `_ladder_complaints` checks by membership.
            "standing": {"criterion": "assay_grade", "rung": "second_seal"},
        },
        "systems": [
            {
                "id": "assay",
                "name": "the assay",
                "logic": "every made thing carries the history of its making",
                "manifests_as": "a printed line of provenance nobody reads aloud",
                "rules": [
                    {
                        "id": "provenance",
                        "rule": "history fixes price",
                        "manifests_as": "a price quoted twice for identical objects",
                        "consequences": [
                            {"domain": name, "consequence": f"what follows in {name}"}
                            for name in rule_domains
                        ],
                    }
                ],
                "criterion": {
                    "id": "assay_grade",
                    "comparator": "ordinal",
                    "evaluates": "appraiser",
                    # Lowest first and three long, so the chain is one a rung's place can be
                    # counted on: `third_seal` is 1, `first_seal` is 3.
                    "ranks": [
                        {
                            "id": "third_seal",
                            "visible_form": "a lead seal on the cuff that greens in a week",
                            "cost_to_reach": "a year of unpaid readings",
                        },
                        {
                            "id": "second_seal",
                            "visible_form": "a brass seal, worn at the throat",
                            "cost_to_reach": "a ruined reputation somewhere else",
                        },
                        {
                            "id": "first_seal",
                            "visible_form": "a silver seal nobody is allowed to hand back",
                            "cost_to_reach": "the name of whoever held it before you",
                        },
                    ],
                },
            }
        ],
        "cast": [
            {
                "id": "silas",
                "is_a": "a junior clerk",
                "wants": "to be read once by someone who matters",
                "false_belief": "the ledger is only counting coin",
                "secret": "he has been shorting his own readings for a year",
                "voice_tag": "prices everything, apologises for none of it",
                "relationships": [
                    {"predicate": "owes", "target": "marta", "note": "nine months of rent"}
                ],
            },
            {"id": "marta", "is_a": "the bursar, and his landlord"},
        ],
        "creatures": [
            {
                "id": "ash_fox",
                "is_a": "a fox the colour of banked ash",
                "mechanism": "it hunts by heat rather than by scent",
                "ecology": "it follows kiln smoke and dies in a cold winter",
                "human_use": "kiln-keepers keep one to find a crack in a wall",
                "behaviour": "it sits on whatever is warmest and refuses to move",
                "manifests_as": "a shape on the kiln that nobody wants to shift",
            }
        ],
        "mysteries": [
            {
                "id": "the_tide",
                "question": "what is the tide actually aimed at",
                "answer": answer,
                "disclosed_at_scene": 7,
                "kind": "mystery",
            }
        ],
        "cardinality": [
            {
                "id": "one_seal",
                "predicate": "possessed_by",
                "scope": "carrier",
                "group_key": "subject,order_key",
                "maximum": 1,
            }
        ],
        "graph_line": {
            "label": "SYSTEM",
            "edges": [
                {"phrase": "is recognised as", "predicate": "recognized_by"},
                # The printed form a change of standing is announced in, which a world with a
                # ladder owes: `[SYSTEM] Silas now stands at second seal`.
                {"phrase": "now stands at", "predicate": worlds.STANDS_AT_PREDICATE},
            ],
        },
        "directives": [
            {"kind": "constraint", "text": "Every reading costs the minutes it takes."}
        ],
    }
    if extra:
        built.update(extra)
    return built


def payload(*worlds_: dict[str, Any]) -> dict[str, Any]:
    return {"worlds": list(worlds_)}


#: The scene count the fixture world is written against: its one reveal lands at scene 7, so a
#: run of eight scenes settles it and the `every answer lands after the last scene` gate is
#: satisfied by construction rather than by luck.
SCENES = 8


def candidate(**kwargs: Any) -> architect.Candidate:
    return architect.Candidate(0, world(**kwargs))


def detector(records: list[lc.StateRecord]) -> DetectorInput:
    """The cardinality detector's input, so an enforcement claim can be made over forged canon."""
    return DetectorInput(
        book_id=BOOK_ID, branch_id=BRANCH_ID, logical_id="scene-1", records=tuple(records)
    )


def gate(entry: architect.Candidate | dict[str, Any]) -> tuple[str, ...]:
    """`gate_candidate` at this file's scene count, so no test has to repeat it."""
    if isinstance(entry, dict):
        entry = architect.Candidate(0, entry)
    return architect.gate_candidate(entry, scenes=SCENES)


# --- the shape and collapse gates ---------------------------------------------------------------


def test_the_forge_asks_for_exactly_k() -> None:
    with pytest.raises(architect.ArchitectOutputError, match="exactly 3"):
        architect.worlds_from(payload(world(), world(domain="b", geometry="cycle")), 3)


def test_a_forge_over_one_candidate_is_not_a_search() -> None:
    with pytest.raises(architect.ArchitectInputError, match="at least 2"):
        architect.render_world_request("anything", k=1)


@pytest.mark.parametrize(
    "second,axis",
    [
        ({"geometry": "cycle"}, "domain"),
        ({"domain": "coopering"}, "geometry"),
    ],
)
def test_a_collapsed_forge_is_refused_before_a_scene_is_paid_for(
    second: dict[str, Any], axis: str
) -> None:
    """Two worlds that agree on a declared axis are one world in two hats.

    Stricter than `plan_search._alternatives`, which compares whole statements for exact equality
    after casefolding and therefore cannot catch a re-worded collapse. Here the axes are declared,
    so the check runs on the declaration.
    """
    with pytest.raises(architect.ArchitectOutputError, match=f"{axis} value"):
        architect.worlds_from(payload(world(), world(**second)), 2)


def test_a_geometry_outside_the_list_is_refused_by_name() -> None:
    with pytest.raises(architect.ArchitectOutputError, match="spiral"):
        architect.worlds_from(payload(world(geometry="spiral"), world(domain="b")), 2)


def test_two_distinct_worlds_pass_the_shape_gate() -> None:
    forged = architect.worlds_from(
        payload(world(), world(title="Salt Court", domain="salvage law", geometry="threshold")), 2
    )
    assert [item.index for item in forged] == [0, 1]
    assert architect.spread(forged) is not None


# --- the per-candidate gates -----------------------------------------------------------------


def test_a_clear_world_has_nothing_to_complain_about() -> None:
    assert gate(candidate()) == ()
    assert worlds.validate(architect.records_for(candidate())) == ()


def test_a_rule_that_reaches_two_domains_of_life_is_refused() -> None:
    """Uniqueness lives in consequences more than in names, so this is the load-bearing gate."""
    [complaint] = gate(candidate(rule_domains=("economy", "law")))
    assert "reaches 2 domain(s)" in complaint
    assert f"the floor is {architect.CONSEQUENCE_FLOOR}" in complaint


def test_three_consequences_in_one_domain_do_not_reach_the_floor() -> None:
    [complaint] = gate(candidate(rule_domains=("economy", "economy", "economy")))
    assert "reaches 1 domain(s)" in complaint


def test_a_rank_you_are_told_rather_than_shown_is_refused() -> None:
    unseen = world()
    unseen["systems"][0]["criterion"]["ranks"][0]["visible_form"] = ""
    complaints = gate(unseen)
    assert any("no form a reader can see" in complaint for complaint in complaints)


def test_a_rank_that_costs_nothing_is_refused() -> None:
    free = world()
    free["systems"][0]["criterion"]["ranks"][1]["cost_to_reach"] = "  "
    complaints = gate(free)
    assert any("costs nothing to reach" in complaint for complaint in complaints)


def test_a_mystery_with_no_answer_is_refused_by_the_number_that_motivated_it() -> None:
    empty = world()
    empty["mysteries"] = []
    [complaint] = gate(empty)
    assert "40 opened and 0 paid" in complaint

    unanswered = world(answer="   ")
    assert any(
        "records no answer" in complaint
        for complaint in gate(unanswered)
    )


def test_a_world_whose_every_answer_lands_after_the_last_scene_is_refused() -> None:
    """The defect the first live forge produced, and it produced it by doing as it was told.

    With no scene count in the prompt, one forged world scheduled its four answers at scenes 17,
    25, 33 and 41 — sensible for an open-ended serial and useless for the eight scenes actually
    being written, which would have opened four debts and paid none. That is the measured
    40-opened-0-paid defect reproduced by the machinery built to fix it, so the count goes in the
    prompt and the gate checks it.
    """
    late = world()
    late["mysteries"][0]["disclosed_at_scene"] = 41
    [complaint] = gate(late)
    assert "every answer lands after scene 8" in complaint
    assert "earliest is 41" in complaint
    # And a world with one answer inside the run is fine however far the others land.
    mixed = world()
    mixed["mysteries"] = [
        {**mixed["mysteries"][0], "id": "near", "disclosed_at_scene": 6},
        {**mixed["mysteries"][0], "id": "far", "disclosed_at_scene": 41},
    ]
    assert gate(mixed) == ()


def test_the_scene_count_reaches_the_prompt() -> None:
    request = architect.render_world_request("x", k=2, scenes=8)
    assert '"scenes_being_written_now": 8' in request.prompt
    assert "inside the 8 scenes being written now" in request.prompt


def test_a_book_of_no_scenes_has_nowhere_to_put_a_reveal() -> None:
    with pytest.raises(architect.ArchitectInputError, match="nowhere to put a reveal"):
        architect.render_world_request("x", k=2, scenes=0)


def test_a_creature_that_is_a_renamed_stock_monster_is_refused_field_by_field() -> None:
    thin = world()
    thin["creatures"][0]["mechanism"] = ""
    thin["creatures"][0]["ecology"] = ""
    complaints = gate(thin)
    assert any("declares no mechanism" in complaint for complaint in complaints)
    assert any("declares no ecology" in complaint for complaint in complaints)


@pytest.mark.parametrize(
    "ordinary",
    [
        "the port's franchise is the right to stand at the rail on assize day",
        "a ward may surrender its franchise and lose a decade of goodwill",
        "the relay series of marks runs north from the datum",
        # The second measured false positive, 2026-08-23: a bare `like in` refused a world
        # over an old voice reciting a field, and the guard fires exactly once across the 30
        # worlds forged before that date — that once.
        "reciting what a field looked like in a year before the listeners were born",
    ],
)
def test_ordinary_legal_english_is_not_a_borrowed_reference(ordinary: str) -> None:
    """The measured false positive, kept runnable.

    The first live `domain_first` forge refused **two of three** worlds on a bare
    `\\bfranchise\\b` — a port whose franchise is the vote, a ward surrendering its franchise —
    in worlds literalising salvage law and civic charter. A guard that refuses legitimate
    material is `directors._CRAFT_INSTRUCTION`'s recorded failure in a third costume.
    """
    legal = world()
    legal["systems"][0]["logic"] = ordinary
    assert not [
        complaint
        for complaint in gate(legal)
        if "RS1" in complaint
    ]


@pytest.mark.parametrize(
    "borrowed",
    [
        "inspired by the great work",
        "a riff on the old ladder",
        "it works like the Tempest Crown series",
        # The narrowed form of the phrase removed from the case-insensitive list: still
        # caught when what follows it is a named thing.
        "the grades work like in The Bright Ladder",
        "SEAL™",
    ],
)
def test_an_answer_that_compares_itself_to_something_outside_it_is_refused(
    borrowed: str,
) -> None:
    """RS1 / C3 at the gate as well as in the prompt, and honest about being shallow.

    A vocabulary guard is not comprehension: this catches the shapes a model reaches for when it
    borrows and would not catch a borrowed idea in original words. What it buys is that the
    forge cannot ship an output that names its own source.
    """
    leaky = world()
    leaky["systems"][0]["logic"] = f"every made thing carries its history, {borrowed}"
    complaints = gate(leaky)
    assert any("RS1" in complaint for complaint in complaints)


#: One fixed instant, so a recorded spend can be read back on a known day.
FROZEN = 1787500000.0


def test_a_forge_answer_that_does_not_conform_is_kept_on_disk_and_costed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The branch that lost two paid forges on 2026-08-23 by printing one line and returning.

    A K=3 answer had outgrown a single message and what came back was its tail — 1,553
    characters beginning mid-object, against 64,546 output tokens billed. The text was discarded
    unread, and with no decision recorded the spend never reached `store.spend_on`, which is what
    the daily ceiling reads. Diagnosing it took a wrapper around the provider and a second forge.
    """
    import litharness.cli as cli_module
    from litharness.providers.fake import FakeProvider
    from litharness.providers.registry import ProviderRegistry

    provider = FakeProvider()
    fragment = '{"text":"the tail of an answer whose head never arrived"}]}]}'
    provider.set_responses([fragment])
    monkeypatch.setattr(
        cli_module, "build_default_registry", lambda *a, **k: ProviderRegistry(provider)
    )
    # A fixed clock, so the day the spend is read back on is the day it was recorded under.
    monkeypatch.setattr(cli_module, "_now", lambda: FROZEN)

    out = tmp_path / "forge"
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    argv = ["--database", str(database), "forge", "a brief", "--k", "2", "--out", str(out)]
    assert main(argv) == 1

    # The answer is on disk rather than gone, and the bundle is not.
    assert (out / "refused.txt").read_text(encoding="utf-8") == fragment
    assert not (out / "forge.json").exists()

    # And the call is on the ledger, so the ceiling that reads recorded spend sees it.
    from litharness.adapters.sqlite_store import SqliteStore

    store = SqliteStore.open(database)
    try:
        spend = store.spend_on(cli_module._stamp(FROZEN)[:10])
    finally:
        store.close()
    assert spend.invocations == 1


def test_the_domain_is_the_engine_and_its_jargon_never_reaches_the_page() -> None:
    """Five worlds in a row were set inside a trade and written in its glossary.

    Assaying, grafting, surveying, bell-founding, dyeing. The rule asked for a real domain of
    human *work* and got the workshop, the yard and the vocabulary; the operator read two of
    them and named it — *"unnecessarily esoteric ... the words used are adding unnecessary
    complexity eg mordant"*. The physics stays, which is what makes a world argue back; where it
    belongs is what this asserts.
    """
    [rule] = [item for item in architect._RULES if "Literalise one real domain" in item]
    assert "the engine, not the setting" in rule
    assert "never reaches the page" in rule
    assert "not set inside that trade" in rule


def test_a_rule_asks_what_a_person_would_want_and_puts_it_at_the_top_of_the_ladder() -> None:
    """The question no rule in this module used to ask.

    Every other rule asks what a world *declares*: consequences, manifestations, rungs, costs,
    an inventory. None asked whether anybody would want what was declared, and the result was a
    countable, distinct inventory of chores — *"Readers want to feel cool and progress in
    meaningful ways"*. Like the ladder and protagonist rules beside it, this asks for a
    declaration and says nothing about outcomes, so the forbidden-verb list applies here too.
    """
    [rule] = [item for item in architect._RULES if "would want to be able to do" in item]
    assert "TOP of the ladder" in rule
    for forbidden in ("likeable", "compelling", "interesting", "best", "win", "succeed"):
        assert forbidden not in rule.lower(), forbidden
    # It is about the world's ladder and not about one person, so it must not have joined the
    # four rules `test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome` counts.
    assert "protagonist" not in rule


def test_a_rung_declares_what_it_lets_a_person_do_and_it_reaches_canon() -> None:
    """§114 measured the gap and built beside it; the operator named it again and it is closed.

    That entry counted 135 of 156 rungs across 24 worlds as an insignia and permission
    outnumbering capability 104 to 46, *"because `_RANK` has a slot for what a rung LOOKS like
    and one for what it COSTS and none for what it lets you do"*. Its answer was a capability
    inventory beside the ladder, which left the ladder a chain of standings. The operator read a
    premise forged on that ladder: *"readers want something the character gets and gets to keep
    forever \u2014 healing touch, strong healing touch, revival ... rarely interested in more
    conceptual growth"*.
    """
    ranks = architect.WORLDS_SCHEMA["properties"]["worlds"]["items"]["properties"]["systems"]
    ranks = ranks["items"]["properties"]["criterion"]["properties"]["ranks"]["items"]
    assert "grants" in ranks["required"]

    granted = world()
    chain = granted["systems"][0]["criterion"]["ranks"]
    for rank, power in zip(chain, ("reads a seam by touch", "reads a seam through a wall",
                                   "reads a seam a year after it closed"), strict=False):
        rank["grants"] = power
    records = architect.records_for(architect.Candidate(0, granted), scenes=SCENES)
    # On `is_a`, which is what a capability writes, so the packet sees one kind of fact.
    grants = {r.value for r in records if r.predicate == "is_a"}
    assert "reads a seam through a wall" in grants


def test_the_ladder_rule_asks_for_abilities_and_keeps_its_own_vocabulary_off_the_page() -> None:
    """Two clauses from one operator read: what a rung is, and what a premise may call it.

    *"Ladders mentioned again where ladders hold no place."* Said of a premise that reached the
    page with the sentence *"get high enough up the Low Hall's ladder"* \u2014 `ladder` and `rung`
    are this schema's words for a thing a reader meets as bronze and gold.
    """
    [rule] = [item for item in architect._RULES if "chain of abilities and not of" in item]
    assert "they keep it" in rule
    assert "is not a rung" in rule
    [furniture] = [item for item in architect._RULES if "FURNITURE and not its concept" in item]
    assert "never the book's" in furniture
    # `standing` joined `ladder` and `rung` after being measured on the page: three of eight
    # unfollowable terms in one premise were that single word.
    assert "and so is `standing`" in furniture
    assert "None of them appear in the premise" in furniture


# --- the pitch, the furniture, and the default nobody has to break -------------------------------
#
# **The operator's worked example, 2026-08-23, read against six forged worlds.** A biology graduate
# in a dead-end coffee job in a near-future with a neural implant dies, wakes as a child in a magic
# world with the AI merged into him, finds that magic here runs on cell biology, masters water
# magic with what he already knows, and joins an academy. Slow burn. It keeps every genre comfort
# and is fresh underneath; the six worlds kept none and were strange throughout.


def test_the_premise_rule_asks_for_a_pitch_rather_than_prose() -> None:
    """*"'wet cinder', 'because his body rings' ... are not things anybody says in any context"*.

    The rule asked for a person's situation and got literary flash fiction six times out of six,
    on a project whose standing register target is popcorn reading. What it asks for now is the
    sentence somebody says out loud when a friend asks what the book is about.
    """
    [rule] = [item for item in architect._RULES if "PITCH and not as prose" in item]
    assert "plain modern English" in rule
    assert "in the order things happen" in rule
    assert "no invented compound" in rule
    # The test that counts rules mentioning this person owns the forbidden-verb list; the pitch
    # clause lives inside one of them, so it is checked against the same list here.
    for forbidden in ("likeable", "compelling", "interesting", "hero", "succeed"):
        assert forbidden not in rule.lower(), forbidden


def test_the_ladder_is_declared_furniture_rather_than_the_world_it_furnishes() -> None:
    """*"Why do each of these options mention climbs and ladders ... stuck on these words"*.

    §113 made the rung the number a reader counts, which was the point and remains true. What it
    also did, unasked, was make the chain the thing every premise was about \u2014 six worlds forged
    on it opened on a ladder rather than on a person.
    """
    [rule] = [item for item in architect._RULES if "FURNITURE and not its concept" in item]
    # **Structure, not instance, and this assertion used to demand the instance.** It asserted
    # the literal words `bronze to gold`, which is the failure the operator named on the same
    # day: *"not every book has to have bronze and gold ... I was hoping you would generalize the
    # concept structure. Like Animal object in C++ if I mentioned cats and bunnies."* A test that
    # requires one world's vocabulary is a test that forbids every other world's.
    assert "whatever THIS world calls" in rule
    assert "no house style" in rule
    assert "bronze" not in rule.lower().split("metals")[0]
    assert "the premise is about the person rather than about the chain" in rule
    # And the counting clause §113 shipped is still in the same rule, unweakened.
    assert "the rung's position from the bottom of that chain" in rule


def test_a_rule_says_the_genre_s_own_furniture_is_welcome() -> None:
    """Originality was being read as strangeness, and the reader pays for that.

    `_DISTINCTNESS_RULE` refuses two worlds that differ only in their names, and the originality
    rule forbids naming or imitating a real work. Neither ever said that an academy, a
    tournament or a master worth impressing are what a reader came for.
    """
    [rule] = [item for item in architect._RULES if "furniture is WELCOME" in item]
    for comfort in ("academy", "tournament", "master worth impressing", "rival"):
        assert comfort in rule
    assert "Originality belongs in the engine underneath and in the person" in rule


def test_inverting_a_genre_default_is_optional_and_the_ladder_is_still_fenced() -> None:
    """Six worlds, six inversions, six worlds a reader would find alien.

    Nothing heals; nobody has a move-list; nothing is ever hidden. Each is a competent answer to
    *remove or invert exactly one default*, and together they are why the operator recognised
    none of these as the genre they asked for. The fence §113 built around the one default that
    is not on the table is unchanged.
    """
    [rule] = [item for item in architect._RULES if "remove or invert ONE default" in item]
    assert "You MAY" in rule
    assert "keeps every default" in rule
    assert "never this one" in rule
    assert "can rise, and the reader can count it" in rule


# --- what a world is allowed to be about --------------------------------------------------------
#
# **Measured over the 30 worlds forged before 2026-08-23** — four briefs, both prompt shapes,
# every pilot this project has run. Every one carries administrative vocabulary, at a median of
# 7.21 words per 1,000 of declared text and a minimum of 2.69, and 18 of the 30 name a register,
# a debt, a court, a deed or a clerk in the **premise**. The operator read three such premises on
# 2026-08-23 and refused all three: *"Anything related to debt or ledgers is a no no in a story"*.
# The rule text was where the bias came from; these check that it stays where it was put.


def test_no_rule_offers_a_debt_as_a_subject_or_a_market_as_an_interface() -> None:
    joined = " ".join(architect._RULES)
    assert "or a debt may leave this out" not in joined
    assert "a debt the book can never pay" not in joined
    assert "the exchange rate, who can cheat whom, what the law says" not in joined
    assert "NOT an exchange rate, a market, a court, a licence or a tariff" in joined
    assert "not an administration" in joined


def test_the_cost_rule_says_what_a_cost_is_paid_in() -> None:
    """A cost with no stated currency is what produced thirty worlds about money."""
    [rule] = [item for item in architect._RULES if "every gain has a cost" in item]
    assert "never in money" in rule
    assert "never in a debt" in rule


def test_a_premise_written_in_administration_is_refused() -> None:
    paperwork = world()
    paperwork["premise"] = (
        "Silas owes the ledger nine months of rent, and the register carries his name twice."
    )
    [complaint] = [item for item in gate(paperwork) if "administration" in item]
    for word in ("owes", "ledger", "rent", "register"):
        assert word in complaint
    assert not [item for item in gate(world()) if "administration" in item]


def test_the_administration_rate_is_reported_and_nothing_refuses_on_it() -> None:
    """A distribution, not a bar — §81, §85, §87 and §89 are four entries about why.

    The premise check is the refusal and it is a membership test; the rate is a number the
    operator reads beside the complaint. A world may be full of clerks and still be picked, and
    that is the operator's call rather than this gate's.
    """
    heavy = world()
    heavy["systems"][0]["logic"] = "the register, the ledger, the court and the clerk decide it"
    counters = architect.report(architect.Candidate(0, heavy), scenes=SCENES)
    assert counters["administration_per_1k"] > 0
    assert counters["administration_in_premise"] == []
    assert not [item for item in gate(heavy) if "administration" in item]


# --- whose book it is ---------------------------------------------------------------------------
#
# `plan/reader-read-3.md` note 1: the operator read two chapters of the first book drafted on a
# forged world and named the premise as the defect — a world premise is what is true of everyone,
# and the hook the genre runs on is an exception belonging to one person. Measured against this
# module, the words *protagonist*, *main character* and *hero* did not occur in it, and none of
# the world's five declared cast members reached either chapter.
#
# What these tests grade is that a world can *declare* one and that the declaration refers.
# Whether the hook is any good is not graded here and has no instrument in this project;
# `test_the_architect_ranks_nothing_and_cannot_learn_to` is what keeps it that way.


def test_a_world_that_names_no_protagonist_is_refused_at_the_forge() -> None:
    """Required of the forge, and refused there rather than downstream.

    `records_for` deliberately tolerates absence, because
    `test_the_pilot_package_regenerates_the_world_it_was_run_on` runs it over a world forged
    before the field existed. The refusal therefore lives where the model's answer arrives.
    """
    faceless = world()
    del faceless["protagonist"]
    with pytest.raises(architect.ArchitectOutputError, match="names no protagonist"):
        architect.worlds_from(payload(faceless, world(domain="b", geometry="cycle")), 2)


@pytest.mark.parametrize("field_name", ["id", "exception", "edge", "wants", "price"])
def test_an_empty_protagonist_field_is_refused_by_name(field_name: str) -> None:
    """Emptiness, not absence, because `minLength` is a request and not a guarantee.

    The 2026-08-22 forge returned a world whose `premise` was the empty string under a schema
    that asked for a string, conformed, and then failed the shape check — $1.48 for three worlds,
    one of them unusable (`pilot3/forge.db`, `dec-fb00e71c…`).
    """
    hollow = world()
    hollow["protagonist"] = {**hollow["protagonist"], field_name: "   "}
    with pytest.raises(architect.ArchitectOutputError, match=f"protagonist has no {field_name}"):
        architect.worlds_from(payload(hollow, world(domain="b", geometry="cycle")), 2)


def test_the_protagonist_reaches_canon_as_records_and_not_as_a_field() -> None:
    """Everything a world declares is a record here, and this is not the exception.

    The role is a *second* one on a cast member — `entity_roles` returns the roles a subject
    carries, plural, because a subject may be two things at once — so nothing has to choose
    between "cast" and "protagonist".
    """
    records = architect.records_for(candidate(), scenes=SCENES)
    assert worlds.entity_roles(records)["silas"] == ("cast", "protagonist")
    assert worlds.entities_with_role(records, "protagonist") == ("silas",)

    by_predicate = {
        record.predicate: record
        for record in records
        if record.subject == "silas" and record.object_ref is None
    }
    assert by_predicate[worlds.EDGE_PREDICATE].value.startswith("he prices a thing")
    assert by_predicate[worlds.PRICE_PREDICATE].value.startswith("every reading he signs")

    [exception] = [
        record
        for record in records
        if record.predicate == worlds.EXCEPTION_PREDICATE
    ]
    assert exception.subject == "silas"
    assert exception.object_ref == "provenance"
    assert exception.kind is lc.StateRecordKind.RELATIONSHIP

    # One `wants`, though two places in the answer declared it: `records_for` keys a record on
    # its content, so the cast entry's want and the protagonist's are one fact.
    assert len([r for r in records if r.subject == "silas" and r.predicate == "wants"]) == 1
    assert worlds.validate(records) == ()


def test_a_declared_protagonist_does_not_poison_its_own_book() -> None:
    """**The end-to-end check the first paid run had to discover for us.**

    Every detector in the wired ladder, over a world that declares a protagonist, with no scene
    and no prose — just the records `--pick` writes into canon. It must be silent. Two of eight
    scenes of *A Good Take* went parked and poisoned on 2026-08-22 because nothing ran this:
    the protagonist's second `entity_role` read as a contradiction, and a `wants` declared once
    on the cast entry and once on the protagonist read as another.

    `tests/test_integrity.py::test_a_subject_that_is_two_things_at_once_is_not_contradicting_itself`
    pins the detector half; this pins that the Architect does not hand it the input.
    """
    from litharness.domain.findings import DetectorInput
    from litharness.domain.integrity import run_detectors

    records = architect.records_for(
        candidate(), authority=lc.StateAuthority.ACCEPTED_CANON, scenes=SCENES
    )
    findings = run_detectors(
        DetectorInput(book_id="b", branch_id="br", logical_id="scene-1", records=records)
    )
    assert findings == [], [item.message for item in findings]


def test_a_want_declared_twice_reaches_canon_once_and_the_gate_says_when_they_differ() -> None:
    """`_ENTITY` carries `wants` for everybody and `_PROTAGONIST` restates it, so a world can
    say it twice. Canon takes the cast entry's, because two values in one slot is what
    `state.contradiction.v1` refuses — and the gate names the divergence at forge time rather
    than letting it surface as a poisoned scene."""
    agreeing = architect.records_for(candidate(), scenes=SCENES)
    assert len([r for r in agreeing if r.subject == "silas" and r.predicate == "wants"]) == 1
    assert gate(candidate()) == ()

    diverging = world()
    diverging["protagonist"] = {
        **diverging["protagonist"],
        "wants": "to be read once, by anybody at all",
    }
    records = architect.records_for(architect.Candidate(0, diverging), scenes=SCENES)
    [want] = [r for r in records if r.subject == "silas" and r.predicate == "wants"]
    assert want.value == "to be read once by someone who matters", "the cast entry wins"
    assert any("as the protagonist" in item for item in gate(diverging))


def test_an_exception_to_a_shape_reaches_the_shape_and_one_to_a_rule_does_not() -> None:
    """**The one derivation in `records_for`, and it is a definition rather than an inference.**

    "Silas is the exception to `one_seal`" and "`one_seal` does not govern silas" are the same
    fact said from the two ends of one edge, and `worlds.in_scope` reads only the second. A world
    that declared the first and forgot the second would hand the writer an exception the gate
    still refuses — decoration, which is what `plan/handoff-protagonist.md` Task 1 exists to
    prevent.

    An exception naming a *rule* has no maximum to except, so it gets the edge and nothing more.
    """
    to_a_shape = candidate(
        extra={
            "protagonist": {
                **world()["protagonist"],
                "exception": "one_seal",
            }
        }
    )
    records = architect.records_for(to_a_shape, scenes=SCENES)
    [shape] = worlds.cardinality_shapes(records)
    assert shape.except_subjects == ("silas",)

    # The fixture's own protagonist excepts a rule, and no shape is touched.
    [plain] = worlds.cardinality_shapes(architect.records_for(candidate(), scenes=SCENES))
    assert plain.except_subjects == ()


def test_a_shape_may_declare_its_own_exceptions_without_a_protagonist() -> None:
    """The second declaration site, so the field is not reachable only through one person."""
    declared = world()
    declared["cardinality"][0] = {**declared["cardinality"][0], "except": ["marta"]}
    [shape] = worlds.cardinality_shapes(
        architect.records_for(architect.Candidate(0, declared), scenes=SCENES)
    )
    assert shape.except_subjects == ("marta",)


@pytest.mark.parametrize(
    "change,complaint",
    [
        ({"id": "nobody"}, "not one of the declared cast"),
        ({"exception": "no_such_rule"}, "neither a declared rule nor a declared cardinality"),
    ],
)
def test_the_gate_complains_when_the_declaration_refers_to_nothing(
    change: dict[str, str], complaint: str
) -> None:
    """Membership, never taste. The gate asks whether the declaration *refers*.

    It never asks whether the hook is good, whether the edge is interesting, or whether this is
    the right person to write about — that question has no instrument here and inventing one
    would be the verdict channel `plan/world-architect.md` §2 keeps shut.
    """
    broken = world()
    broken["protagonist"] = {**broken["protagonist"], **change}
    assert any(complaint in item for item in gate(broken))


def test_the_gate_complains_when_the_premise_never_names_the_protagonist() -> None:
    """A premise that describes the world rather than this person's situation.

    Checked for the name and for nothing else: whether it is *written as* their situation is a
    judgment with no instrument, and whether it says their name is arithmetic.
    """
    worldly = world()
    worldly["premise"] = "A city discovers what its ledger has really been counting."
    assert any("never names" in item for item in gate(worldly))
    assert not architect.premise_names_protagonist(architect.Candidate(0, worldly))
    assert architect.premise_names_protagonist(candidate())


def test_a_word_that_merely_contains_the_id_does_not_count_as_naming() -> None:
    """Word boundaries rather than a bare substring.

    `worlds.key_nouns` records the same failure class from its own first live run, where `mour`
    and `ise` arrived out of the middle of longer ids.
    """
    inside = world()
    inside["premise"] = "The assay's silasine ledger counts what nobody reads."
    assert not architect.premise_names_protagonist(architect.Candidate(0, inside))


def test_the_report_counts_the_declaration_and_orders_nothing() -> None:
    note = architect.report(candidate(), scenes=SCENES)
    assert note["protagonist_declared"] is True
    assert note["exception_declared"] is True
    assert note["premise_names_protagonist"] is True
    # No score, no rank, no preference — the three counters are facts about one candidate.
    assert not {key for key in note if "score" in key or "rank" in key.split("_")}


def test_the_protagonist_rule_asks_for_a_declaration_and_never_an_outcome() -> None:
    """**Boundary 1 of `plan/handoff-protagonist.md`, asserted rather than trusted.**

    A protagonist is a declared fact of the world. No default instruction about how to *handle*
    one — open on the hero, make them likeable, show them winning, have them progress faster
    than anyone — may enter any prompt this system renders; that direction is the operator's.
    The operator's own words for the hook use exactly these verbs, which is why the rule that
    came out of them must not.

    The word *reader* is deliberately **not** on the list: the rules beside this one already say
    "a form a reader can SEE" and "teaches a reader that nothing here gets settled". It is this
    module's register for what shows on the page, and forbidding it here would be a rule about a
    word rather than about a boundary.

    **Every rule that mentions the protagonist, not just the one that introduced them.** Two more
    arrived on 2026-08-22 with `plan/handoff-numbers-go-up.md` — the ladder the reader counts and
    the amendment fencing it off from the inversion — and both are about a person the genre's own
    craft advice talks about in exactly the forbidden verbs. A test that checked only the first
    rule would let the second and third in.

    **The count is a tripwire and it has already fired once.** A fourth rule arrived the same day
    with `plan/handoff-ability-inventory.md` — the inventory of things a person can do — and this
    assertion is what made somebody run the forbidden list over it rather than assume. Raise it
    when you add a rule about this person, and only after reading the list below.
    """
    # **Word boundaries, not substrings, and this is the third measured false positive of the
    # shape.** `wince` contains `win` and `knowing` contains `win`, both of which this list
    # rejected while meaning to reject the verb. `_BORROWED` has now been narrowed twice for the
    # same reason (`franchise`, `like in`) and `architect._ADMINISTRATION` once (`court`); a
    # recall-tuned list run as a refusal has its error costs inverted, which
    # `directors._CRAFT_INSTRUCTION` recorded first. `winning` stays on the list in its own right,
    # so nothing is lost by matching whole words.
    rules = [item for item in architect._RULES if "protagonist" in item]
    # Five since 2026-08-23: the subject rule names this person once, in the list of
    # things a world may not be organised around. Read against the list below before the
    # count was raised, as this docstring asks.
    assert len(rules) == 5
    for rule in rules:
        lowered = rule.lower()
        for forbidden in (
            "win", "winning", "hero", "likeable", "likable", "sympathetic", "root for",
            "faster", "fastest", "strongest", "best", "succeed", "success", "triumph",
            "interesting", "compelling",
        ):
            assert not re.search(rf"{forbidden}", lowered), (forbidden, rule)
    [declaration] = [item for item in rules if "does not hold for them" in item.lower()]
    lowered = declaration.lower()
    assert "member of the cast" in lowered
    # **Measured, not stylistic.** The first live forge under this rule returned three worlds,
    # every one of which named a real declared id in `exception` and then glossed it in the
    # same field, and all three were refused by the gate for it. The ask now says which of the
    # two the field is, and this is where that stays said — for the standing's two id fields
    # as well, which are the same shape of ask and got the same answer before it was billed
    # twice.
    assert "its id alone" in lowered
    assert "not an id" in lowered
    assert architect._PROTAGONIST["properties"]["exception"]["pattern"] == "^[a-z0-9_]+$"
    standing = architect._STANDING["properties"]
    assert standing["criterion"]["pattern"] == "^[a-z0-9_]+$"
    assert standing["rung"]["pattern"] == "^[a-z0-9_]+$"
    assert "AN ID AND NOTHING ELSE" in standing["criterion"]["description"]
    assert "AN ID AND NOTHING ELSE" in standing["rung"]["description"]


# --- what a person can do -------------------------------------------------------------------
#
# `plan/reader-read-4.md` §1a and `plan/handoff-ability-inventory.md`. The operator read the first
# book forged with a declared protagonist and called its progression "boring accounting instead of
# nine unique abilities". Measured over the 24 worlds forged to that date: 135 of 156 criterion
# rungs are an insignia, permission beats capability 104 to 46, and `_RANK` — three properties,
# `additionalProperties: false` — has no slot for what a rung lets you do.
#
# *Nine* is the operator's word for an inventory and not a threshold. Nothing here counts up to
# it, gates on it, or lets `report` imply one.


def able(**kwargs: Any) -> dict[str, Any]:
    """The fixture world, plus three capabilities and a protagonist who starts with two."""
    built = world(**kwargs)
    built["capabilities"] = [
        {
            "id": "cap_read_a_seam",
            "is_a": "he can see where two things were joined, and when",
            "manifests_as": "He turns a thing to the light, once, and says a year out loud.",
            "costs": "His eyes go for an hour after, and he works blind through it.",
        },
        {
            "id": "cap_price_unseen",
            "is_a": "he can price a thing the assay has never seen",
            "manifests_as": "He names a figure before the book is open, and it holds.",
            "costs": "Every figure he names is checked twice, and the second check is not his.",
            "requires": ["cap_read_a_seam"],
            "taught_by": "marta",
        },
        {
            "id": "cap_sign_for_another",
            "is_a": "he can sign a reading in somebody else's name",
            "manifests_as": "Two hands on one page and only one of them shaking.",
            "costs": "The other name carries the fault if it is ever found.",
            # A capability may need a RUNG, which is where the ladder and the inventory meet.
            "requires": ["cap_price_unseen", "second_seal"],
        },
    ]
    built["protagonist"] = {
        **built["protagonist"],
        "capabilities": ["cap_read_a_seam", "cap_price_unseen"],
    }
    return built


def test_a_world_may_declare_an_inventory_and_the_gate_is_quiet_about_it() -> None:
    assert gate(able()) == ()
    records = architect.records_for(architect.Candidate(0, able()), scenes=SCENES)
    assert worlds.validate(records) == ()
    assert worlds.capabilities(records) == (
        "cap_price_unseen",
        "cap_read_a_seam",
        "cap_sign_for_another",
    )
    assert worlds.entity_roles(records)["cap_read_a_seam"] == ("capability",)


def test_a_capability_reaches_canon_as_records_and_not_as_a_field() -> None:
    records = architect.records_for(architect.Candidate(0, able()), scenes=SCENES)
    by = {
        (r.subject, r.predicate): r
        for r in records
        if r.subject.startswith("cap_") or r.predicate == worlds.CAN_DO
    }
    assert by[("cap_read_a_seam", "is_a")].value.startswith("he can see where")
    assert by[("cap_read_a_seam", worlds.MANIFESTS_PREDICATE)].value.startswith("He turns")
    assert by[("cap_read_a_seam", worlds.COSTS)].value.startswith("His eyes go")
    assert by[("cap_price_unseen", worlds.TAUGHT_BY)].object_ref == "marta"
    assert by[("cap_price_unseen", worlds.REQUIRES)].object_ref == "cap_read_a_seam"
    # The protagonist's own inventory, and only what the world declared.
    assert worlds.capabilities_of(records, "silas") == ("cap_price_unseen", "cap_read_a_seam")


def test_the_inventory_is_a_set_and_the_ladder_is_a_position() -> None:
    """**Boundary 6: a rung and a capability are different objects.** §113 built the ladder — a
    position in a recognised order, one per criterion. This is a set. They meet at exactly one
    edge, `requires`, where a capability may need a rung first; nothing collapses them, and a
    world may declare either, both or neither."""
    records = architect.records_for(architect.Candidate(0, able()), scenes=SCENES)
    [to_a_rung] = [
        r
        for r in records
        if r.predicate == worlds.REQUIRES and r.object_ref == "second_seal"
    ]
    assert to_a_rung.subject == "cap_sign_for_another"
    assert "second_seal" in worlds.rank_order(records, criterion="assay_grade")[0]
    assert worlds.capabilities(records) and "second_seal" not in worlds.capabilities(records)


@pytest.mark.parametrize(
    "mutate,complaint",
    [
        (
            lambda w: w["capabilities"][0].__setitem__("requires", ["cap_nothing"]),
            "which this world never declares",
        ),
        (
            lambda w: w["capabilities"][0].__setitem__("taught_by", "nobody_at_all"),
            "whom this world never declares",
        ),
        (
            lambda w: w["protagonist"].__setitem__("capabilities", ["cap_undeclared"]),
            "not one of the declared capabilities",
        ),
    ],
)
def test_the_gate_complains_when_the_inventory_refers_to_nothing(
    mutate: Any, complaint: str
) -> None:
    """Membership, never taste. The gate never asks whether an ability is interesting, whether
    there are enough of them, or whether this is a good set — that question has no instrument
    here and inventing one would be the verdict channel `plan/world-architect.md` §2 keeps shut.
    """
    broken = able()
    mutate(broken)
    assert any(complaint in item for item in gate(broken))


def test_the_report_counts_the_inventory_and_declares_no_bar() -> None:
    note = architect.report(architect.Candidate(0, able()), scenes=SCENES)
    assert note["capabilities_declared"] == 3
    assert note["protagonist_capabilities"] == 2
    assert note["requirement_depth"] == 2
    # A world that declares none reports zero, and zero is a fact about the world.
    plain = architect.report(candidate(), scenes=SCENES)
    assert plain["capabilities_declared"] == 0
    assert plain["protagonist_capabilities"] == 0
    assert plain["requirement_depth"] == 0
    # **No floor anywhere.** Nothing in the gate or the report mentions a minimum, and the
    # operator's "nine" is a word for an inventory rather than a threshold.
    assert not [item for item in gate(able()) if "at least" in item or "fewer" in item]


def test_the_operators_hook_is_enforced_on_a_world_the_forge_built() -> None:
    """**The enforcement demonstration, run through the forge instead of through fixtures.**

    `tests/test_worlds.py` shows the shape works over hand-built records. That is a claim about
    the vocabulary. This is the claim that matters for a paid run: a candidate as a model would
    return it — a `capabilities` list, a protagonist holding two of them, and a `cardinality`
    entry reading *at most one `can_do` per person* — goes through `records_for` and the
    protagonist is quiet **because `records_for` wrote the `excepts` edge itself**, off the
    `exception` field, with nobody hand-editing canon.

    The control is the same world with the exception pointed at the rule it originally named:
    same capabilities, same holder, same maximum, and now the protagonist blocks like anybody
    else. Which is the point — an exception is a declared fact about one person, not a hole.

    **Both halves are forged at `ACCEPTED_CANON`, which is not decoration.** `records_for`
    defaults to `PROPOSED` because a candidate is a proposal until `forge --pick`, and
    `detect_cardinality_violations` reads canon only — so a version of this test run at the
    default authority passes its first assertion by finding no shapes at all, which is the same
    false pass the `report()` readers were caught making. `--pick` is the call that promotes,
    and this is the authority it promotes to (`cli.py:3208`).
    """
    one_art = {
        "id": "one_art",
        "predicate": worlds.CAN_DO,
        "scope": "cast",
        "group_key": "subject",
        "maximum": 1,
    }
    excepted = able()
    excepted["cardinality"] = [*excepted["cardinality"], {**one_art, "except": ["silas"]}]
    excepted["protagonist"] = {**excepted["protagonist"], "exception": "one_art"}
    assert gate(excepted) == ()
    records = architect.records_for(architect.Candidate(0, excepted), scenes=SCENES,
                                    authority=lc.StateAuthority.ACCEPTED_CANON)
    # The edge nobody wrote by hand: the shape excepts the protagonist because the protagonist
    # named the shape.
    assert [
        r.object_ref
        for r in records
        if r.subject == "one_art" and r.predicate == worlds.EXCEPTS_PREDICATE
    ] == ["silas"]
    assert len(worlds.capabilities_of(records, "silas")) == 2
    assert detect_cardinality_violations(detector(records)) == []

    bound = able()
    bound["cardinality"] = [*bound["cardinality"], one_art]
    [violation] = detect_cardinality_violations(
        detector(
            architect.records_for(
                architect.Candidate(0, bound),
                scenes=SCENES,
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        )
    )
    assert violation.blocks
    assert "silas" in violation.message


def test_the_capability_rule_asks_for_a_declaration_and_never_a_performance() -> None:
    """**Boundary 1, asserted rather than trusted**, in the shape of the protagonist rule's test.

    The system may say a person can do a thing. It may not say how a scene should handle that:
    show it off, make it impressive, let them win with it. That direction is the operator's, and
    the genre's own craft advice about abilities is written in exactly these verbs.
    """
    [rule] = [item for item in architect._RULES if "`capabilities`" in item]
    lowered = rule.lower()
    for forbidden in (
        "show off", "impressive", "impress", "powerful", "awesome", "cool", "satisfying",
        "win", "winning", "triumph", "spectacular", "reader should", "make the reader",
        "exciting", "thrilling", "payoff",
    ):
        assert forbidden not in lowered, forbidden
    assert "distinct, nameable things" in lowered
    assert "a rank is where somebody stands" in lowered


# --- the world as records ---------------------------------------------------------------------


def test_every_record_a_world_makes_is_a_proposal() -> None:
    """Rail one, asserted over the whole output rather than at the constructor."""
    records = architect.records_for(candidate(), scenes=SCENES)
    assert records
    assert {record.authority for record in records} == {lc.StateAuthority.PROPOSED}
    assert {record.predicate_registry_version for record in records} == {worlds.REGISTRY_VERSION}


def test_the_records_carry_the_edges_nothing_in_this_repository_used_to_write() -> None:
    records = architect.records_for(candidate(), scenes=SCENES)
    assert sum(1 for record in records if record.object_ref) > 0
    assert worlds.entities_with_role(records, "creature") == ("ash_fox",)
    assert worlds.criteria(records) == {"assay_grade": "ordinal"}
    assert worlds.rank_order(records, criterion="assay_grade") == (
        ("second_seal", "first_seal"),
        ("third_seal", "second_seal"),
    )
    assert len(worlds.cardinality_shapes(records)) == 1


def test_a_cast_relationship_becomes_an_edge_the_store_can_check() -> None:
    """The capability nothing in this repository used to write.

    `object_ref` has been on every `StateRecord` since the contract shipped and no code in `src/`
    constructed one — the live serial's seven edges were typed by the operator. A cast whose ties
    live only in prose is a cast the store cannot check and `state.cardinality.v0` has nothing to
    count.
    """
    records = architect.records_for(candidate(), scenes=SCENES)
    ties = [
        record
        for record in records
        if record.subject == "silas" and record.predicate == "owes"
    ]
    assert len(ties) == 1
    assert ties[0].object_ref == "marta"
    assert ties[0].value == "nine months of rent"
    assert ties[0].kind is lc.StateRecordKind.RELATIONSHIP
    assert worlds.validate(records) == ()


def test_a_false_belief_and_a_secret_are_claims_rather_than_fields() -> None:
    """The gap between what is true, what a character holds and what the reader has been told."""
    records = architect.records_for(candidate(), scenes=SCENES)
    claims = worlds.claims(records)
    assert "silas_belief" in claims
    assert "silas_secret" in claims
    assert any(
        record.predicate == worlds.BELIEVES and record.object_ref == "silas_belief"
        for record in records
    )


def test_a_reveal_inside_the_book_gets_a_position_and_one_outside_it_does_not() -> None:
    """The key-width leak, pinned. `beats_for` mints `s1…s8` for eight scenes, so a two-digit
    `s04` compares *below* `s1` and a claim scheduled for scene four reads as already told at
    scene one. Measured on Serial Pilot 2 and fixed by minting in the book's own width — and by
    minting no position at all for a scene the book does not have."""
    records = architect.records_for(candidate(), scenes=SCENES)
    assert worlds.claims(records)["the_tide"].startswith("the tide is aimed")
    assert worlds.reveal_scenes(records) == {"the_tide": 7}
    assert worlds.disclosures(records)["the_tide"] == ("s7",)
    # Comparable to a beat key, which the two-digit form was not.
    assert len(worlds.undisclosed_claims(records, at="s1")) >= 1
    assert "the_tide" in {r.subject for r in worlds.undisclosed_claims(records, at="s1")}
    assert "the_tide" not in {r.subject for r in worlds.undisclosed_claims(records, at="s7")}

    # A hundred-scene book puts the same reveal at `s007`, still comparable to its own beats.
    wide = architect.records_for(candidate(), scenes=100)
    assert worlds.disclosures(wide)["the_tide"] == ("s007",)

    # And a reveal past the end of the run gets the ordinal and no position, so it stays hidden.
    far = world()
    far["mysteries"][0]["disclosed_at_scene"] = 41
    outside = architect.records_for(architect.Candidate(0, far), scenes=SCENES)
    assert worlds.reveal_scenes(outside) == {"the_tide": 41}
    assert worlds.disclosures(outside) == {}
    assert "the_tide" in {r.subject for r in worlds.undisclosed_claims(outside, at="s8")}
    assert worlds.validate(outside) == ()


def test_the_manifestation_counter_sees_every_declared_feature() -> None:
    note = architect.report(candidate(), scenes=SCENES)
    assert note["manifestation_coverage"] == 1.0
    assert note["min_consequence_domains"] == 3
    assert note["claims_with_answers"] >= 1
    assert note["key_nouns"]


def test_the_two_prompt_shapes_differ_and_carry_the_same_rules() -> None:
    direct = architect.render_world_request("salvage", k=3, shape=architect.DIRECT)
    domain_first = architect.render_world_request("salvage", k=3, shape=architect.DOMAIN_FIRST)
    assert direct.prompt != domain_first.prompt
    assert direct.schema == domain_first.schema
    for rule in architect._RULES:
        rendered = rule.format(scenes=6) if "{scenes}" in rule else rule
        assert rendered in direct.prompt
        assert rendered in domain_first.prompt
    assert "Work in this order" in domain_first.prompt
    assert "Work in this order" not in direct.prompt


def test_an_unknown_prompt_shape_is_refused_rather_than_defaulted() -> None:
    with pytest.raises(architect.ArchitectInputError, match="unknown prompt shape"):
        architect.render_world_request("x", shape="freeform")


# --- the rail that is enforced rather than declared ---------------------------------------------


def test_the_architect_ranks_nothing_and_cannot_learn_to() -> None:
    """No selection machinery, by import ban rather than by intent.

    §105.1's device, applied to the role that would be most tempting to give a taste: an
    Architect that could order its own candidates would be a quality judge with no validity
    licence, wearing the authority of the thing it generated.
    """
    source = Path(architect.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    forbidden = {
        "litharness.domain.candidates.select_winner",
        "litharness.domain.preference",
        "litharness.application.judge_panel",
        "litharness.application.plan_search",
    }
    assert not (imported & forbidden)
    for banned in ("select_winner", "win_rate", "PairVerdict", "Calibration"):
        assert banned not in source


# --- the seam a pilot walks --------------------------------------------------------------------


def test_a_forged_bundle_seeds_a_book_with_no_provider_call(tmp_path: Path) -> None:
    """`forge --pick` then `new --state … --promises …`, end to end, offline.

    The whole point of the bundle is that `new` consumes it *unchanged*, so this asserts the
    file the forge writes is parseable as a `StateSnapshot` by the same `parse_artifact` call
    `cmd_new` makes, and that the promises land as open rows with a due key from the book's own
    beat sheet rather than from a format string.

    **The pick is run without `--scenes` on purpose.** Serial Pilot 4 forged at eight and
    picked at the default six, and the reveal scheduled for the last scene came out with an
    ordinal and no disclosure position — `plan/serial-pilot-4.md` §5.6. The forge records the
    width now, so the operator carrying the number between two commands is no longer the only
    thing standing between an eight-scene book and a reveal that can never land.
    """
    out = tmp_path / "forge"
    out.mkdir()
    forged = architect.Candidate(0, world())
    bundle = architect.bundle_for(
        forged,
        book_id="00000000-0000-5000-8000-00000000aa01",
        branch_id="00000000-0000-5000-8000-00000000aa02",
        revision_id="00000000-0000-5000-8000-00000000aa03",
        architect_id=worlds.architect_id_for("a test brief"),
        created_at="2026-08-21T00:00:00Z",
        brief="a test brief",
        shape=architect.DIRECT,
        scenes=8,
    )
    (out / "forge.json").write_text(
        json.dumps(
            {
                "architect_id": bundle["architect_id"],
                "k": 1,
                "scenes": 8,
                "candidates": [bundle],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(["--database", str(database), "forge", "--out", str(out), "--pick", "1"]) == 0
    seed = out / "seed.json"
    snapshot = lc.parse_artifact(
        lc.StateSnapshot, json.loads(seed.read_text(encoding="utf-8"))
    )
    assert snapshot.meta.actor.startswith(worlds.ARCHITECT_AUTHOR_PREFIX)
    assert snapshot.records

    # **Every reveal the book is long enough to reach has a position.** The ordinal is stored
    # either way; the position is what `undisclosed_claims` reads, and a claim without one
    # stays hidden for the whole book.
    scheduled = worlds.reveal_scenes(snapshot.records)
    assert scheduled == {"the_tide": 7}
    disclosed = worlds.disclosures(snapshot.records)
    assert {
        claim: scene for claim, scene in scheduled.items() if scene <= 8
    }.keys() <= disclosed.keys()
    assert disclosed["the_tide"] == ("s7",)
    # And the file `new --scenes` is read off downstream carries the same width.
    assert json.loads((out / "directives.json").read_text(encoding="utf-8"))["scenes"] == 8

    assert (
        main(
            [
                "--database",
                str(database),
                "new",
                bundle["title"],
                "--premise",
                bundle["premise"],
                "--scenes",
                "8",
                "--state",
                str(seed),
                "--promises",
                str(out / "promises.json"),
            ]
        )
        == 0
    )

    from litharness.adapters.sqlite_store import SqliteStore

    store = SqliteStore.open(database)
    try:
        book_id, branch_id, _ = store.branches()[0]
        rows = store.promises(book_id, branch_id, open_only=True)
        assert [row.subject for row in rows] == ["the_tide"]
        assert rows[0].status == PROMISE_OPEN
        assert rows[0].due_key == "s7"
        assert rows[0].kind == "mystery"
        # **Canon, and only because a person picked.** The bundle on disk still holds the world
        # as proposed; the pick is what admitted it, and without that step every record would be
        # filtered out of the packet by `is_canon` and the serial would draft against a premise
        # and nothing else.
        records = store.state_records(book_id, branch_id)
        assert {record.authority for record in records} == {lc.StateAuthority.ACCEPTED_CANON}
        proposed = architect.records_for(forged)
        assert {record.authority for record in proposed} == {lc.StateAuthority.PROPOSED}

        # And the world now reaches the drafter: the criterion in the system message, the rules
        # in the packet, the answer to the mystery under the heading that forbids stating it.
        from litharness.domain import context as context_mod
        from litharness.domain.revision import Revision  # noqa: F401 - documents the head type

        head = store.head(book_id, branch_id)
        assert head is not None
        packet = context_mod.assemble(
            head,
            "scene-2",
            plan_items=store.plan_items(book_id, branch_id),
            state_records=records,
        )
        assert worlds.criterion_brief(records) is not None
        # Both kinds of hidden truth: the mystery's recorded answer, which has a scheduled
        # reveal, and a cast member's secret, which has none and is not owed one. The false
        # belief is in neither — it is not true, so it is carried by its `believes` edge.
        assert {item.text for item in packet.sections[context_mod.HIDDEN]} == {
            "the tide is aimed at the assay house, not the city",
            "he has been shorting his own readings for a year",
        }
        rendered = packet.render()
        assert "Rule — history fixes price" in rendered
        assert "never put it on the page" in rendered
    finally:
        store.close()


def test_the_pilot_package_regenerates_the_world_it_was_run_on() -> None:
    """`plan/serial-pilot-2-world.json` is the source; the 140KB seed is derived output.

    Serial Pilot 1 committed its seed because a person typed it. Pilot 2's seed is 327 records
    a function produced, so committing it would be a second copy of something derivable — and
    two copies of one artefact are one artefact and one thing to notice has drifted. What is
    committed is the model's answer; this pins that `records_for` still turns it back into
    exactly the snapshot the pilot ran on, which is the whole of what "reproducible" means here.
    """
    package = json.loads(
        (Path(__file__).resolve().parents[1] / "plan" / "serial-pilot-2-world.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = architect.Candidate(0, package["world"])
    records = architect.records_for(
        candidate, authority=lc.StateAuthority.ACCEPTED_CANON, scenes=8
    )
    again = architect.records_for(
        candidate, authority=lc.StateAuthority.ACCEPTED_CANON, scenes=8
    )
    # Deterministic to the record id, which is what makes the committed answer the source and
    # the 140KB snapshot derived output rather than a second copy.
    assert [r.record_id for r in records] == [r.record_id for r in again]
    assert {record.authority for record in records} == {lc.StateAuthority.ACCEPTED_CANON}
    assert worlds.validate(records) == ()
    # `include_subject=False` for the reason `gate_candidate`'s docstring records: this
    # world was forged and picked on 2026-08-21, and the subject check landed on
    # 2026-08-23. Its premise names a debt and a clerk, which is the finding rather than
    # a regression, and it is checked below.
    assert architect.gate_candidate(candidate, scenes=8, include_subject=False) == ()
    assert [
        item
        for item in architect.gate_candidate(candidate, scenes=8)
        if "administration" in item
    ]
    # **Two more records than the forge reported, and the difference is a fix.** The committed
    # `candidate_reports` are what the forge printed on 2026-08-22; `worlds.REVEAL_SCENE` landed
    # afterwards, storing each mystery's ordinal beside its position, so a regeneration is two
    # rows larger than the run record. The forge's numbers are left as the forge's numbers.
    # The forge positioned every mystery; the fix stores an ordinal for each and a position only
    # for the ones this book has a scene for, so the net gain is exactly the in-book positions.
    reported = package["candidate_reports"][package["picked"] - 1]["records"]
    assert len(records) - reported == len(worlds.disclosures(records))
    assert len(worlds.reveal_scenes(records)) == 6
    assert len(worlds.disclosures(records)) == 2

    # **The protagonist field is additive, and this is where "additive" is a test.** This world
    # was forged on 2026-08-22, before a world could declare whose book it was. It must therefore
    # produce not one record of the new vocabulary, gate as clean as it gated, and hand the
    # planner nothing new — the packet, the outline request and the drafting prompt of a book
    # whose canon declares no protagonist are the bytes they were.
    assert candidate.protagonist is None
    assert worlds.protagonist_brief(records) is None
    assert not [
        record
        for record in records
        if record.predicate
        in {
            worlds.EXCEPTION_PREDICATE,
            worlds.EDGE_PREDICATE,
            worlds.PRICE_PREDICATE,
            worlds.EXCEPTS_PREDICATE,
        }
        or (record.predicate == worlds.ENTITY_ROLE_PREDICATE and record.value == "protagonist")
    ]
    assert all(shape.except_subjects == () for shape in worlds.cardinality_shapes(records))
    note = architect.report(candidate, scenes=8)
    assert note["protagonist_declared"] is False
    assert note["exception_declared"] is False
    assert note["premise_names_protagonist"] is False
    # And the same for the inventory, added 2026-08-22: a world forged before capabilities
    # existed declares none, holds none, and has no prerequisite structure — and none of those
    # three zeros is a complaint.
    assert note["capabilities_declared"] == 0
    assert note["protagonist_capabilities"] == 0
    assert note["requirement_depth"] == 0
    assert not worlds.capabilities(records)


def test_a_debt_the_serial_settles_later_is_opened_without_a_due_date(tmp_path: Path) -> None:
    """An arc reveal at scene 41 is not late in an eight-scene opening.

    Measured on Serial Pilot 2: the forged world scheduled six reveals, four of them past the
    end of the two chapters being written. Clamping those to the final beat — which is what
    `cmd_new` did first — would have `promise.overdue.v0` annotate four debts as late in a book
    that was never going to reach them. `Promise.due_key` is `str | None` and `overdue_promises`
    skips a row with none, so the debt is on the ledger, reaches the packet as something owed,
    and nothing calls it late.
    """
    out = tmp_path / "forge"
    out.mkdir()
    far = world()
    far["mysteries"] = [
        {**far["mysteries"][0], "id": "near", "disclosed_at_scene": 3},
        {**far["mysteries"][0], "id": "far", "disclosed_at_scene": 41},
    ]
    bundle = architect.bundle_for(
        architect.Candidate(0, far),
        book_id="00000000-0000-5000-8000-00000000bb01",
        branch_id="00000000-0000-5000-8000-00000000bb02",
        revision_id="00000000-0000-5000-8000-00000000bb03",
        architect_id=worlds.architect_id_for("arc debts"),
        created_at="2026-08-22T00:00:00Z",
        brief="arc debts",
        shape=architect.DIRECT,
        scenes=8,
    )
    (out / "forge.json").write_text(
        json.dumps({"architect_id": bundle["architect_id"], "k": 1, "candidates": [bundle]}),
        encoding="utf-8",
    )
    database = tmp_path / "arc.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(["--database", str(database), "forge", "--out", str(out), "--pick", "1",
                 "--scenes", "8"]) == 0
    assert main(["--database", str(database), "new", bundle["title"], "--premise",
                 bundle["premise"], "--scenes", "8", "--state", str(out / "seed.json"),
                 "--promises", str(out / "promises.json")]) == 0

    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.promises import overdue_promises

    store = SqliteStore.open(database)
    try:
        book_id, branch_id, _ = store.branches()[0]
        rows = {row.subject: row for row in store.promises(book_id, branch_id)}
        assert rows["near"].due_key == "s3"
        assert rows["far"].due_key is None
        # At the last scene of the run, the near debt is overdue and the arc debt is not.
        late = overdue_promises(tuple(rows.values()), "s8")
        assert [row.subject for row in late] == ["near"]
    finally:
        store.close()


def test_picking_outside_the_field_is_refused_rather_than_clamped(tmp_path: Path) -> None:
    out = tmp_path / "forge"
    out.mkdir()
    (out / "forge.json").write_text(
        json.dumps({"architect_id": "arch-x", "k": 0, "candidates": []}), encoding="utf-8"
    )
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(["--database", str(database), "forge", "--out", str(out), "--pick", "1"]) == 2


def test_picking_before_forging_says_which_file_is_missing(tmp_path: Path) -> None:
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    assert (
        main(["--database", str(database), "forge", "--out", str(tmp_path / "nope"), "--pick", "1"])
        == 2
    )


# -- the width the two forge commands have to agree on ---------------------------------------
#
# `plan/serial-pilot-4.md` §5.6: the forge ran at eight scenes, the pick a day later took
# `DEFAULT_SCENES`, and the reveal the eight scenes existed to settle came out with an ordinal
# and no disclosure position — hidden for the whole book, silently. The number is recorded now.


def _forge_file(
    out: Path, *, scenes: int | None, mysteries: list[dict[str, Any]]
) -> dict[str, Any]:
    """A `forge.json` on disk, with or without the width the forge ran at.

    `scenes=None` writes the shape every file already on disk has: no key at all. That absence
    has to keep behaving exactly as it did, which is the second half of this fix.
    """
    built = world()
    built["mysteries"] = mysteries
    bundle = architect.bundle_for(
        architect.Candidate(0, built),
        book_id="00000000-0000-5000-8000-00000000cc01",
        branch_id="00000000-0000-5000-8000-00000000cc02",
        revision_id="00000000-0000-5000-8000-00000000cc03",
        architect_id=worlds.architect_id_for("width"),
        created_at="2026-08-23T00:00:00Z",
        brief="width",
        shape=architect.DIRECT,
        scenes=scenes if scenes is not None else architect.DEFAULT_SCENES,
    )
    forged: dict[str, Any] = {
        "architect_id": bundle["architect_id"],
        "k": 1,
        "candidates": [bundle],
    }
    if scenes is not None:
        forged["scenes"] = scenes
    out.mkdir(parents=True, exist_ok=True)
    (out / "forge.json").write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
    return bundle


def _positions(seed: Path) -> dict[str, tuple[str | None, ...]]:
    snapshot = lc.parse_artifact(lc.StateSnapshot, json.loads(seed.read_text(encoding="utf-8")))
    return worlds.disclosures(snapshot.records)


#: One reveal inside a six-scene book and one only an eight-scene book reaches — the shape of
#: the pilot 4 world, where `myst_why_reeves_takes_fail` landed at s4 and
#: `myst_where_the_fourth_grade_went` at s8 or nowhere at all.
LATE_REVEAL = [
    {
        "id": "near",
        "question": "what is the tide aimed at",
        "answer": "the assay house",
        "disclosed_at_scene": 3,
        "kind": "mystery",
    },
    {
        "id": "late",
        "question": "where the fourth grade went",
        "answer": "it was never assayed",
        "disclosed_at_scene": 8,
        "kind": "mystery",
    },
]


def test_a_pick_with_no_scenes_takes_the_width_the_forge_recorded(tmp_path: Path) -> None:
    """The measured defect, at the grain it was measured: one reveal at 3, one at 8.

    At `DEFAULT_SCENES` the late one keeps its ordinal and gets no position, which
    `undisclosed_claims` reads as hidden throughout — so the reveal the eight scenes exist to
    settle can never land. The recorded width is what the pick reads now.
    """
    out = tmp_path / "forge"
    _forge_file(out, scenes=8, mysteries=LATE_REVEAL)
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(["--database", str(database), "forge", "--out", str(out), "--pick", "1"]) == 0
    assert _positions(out / "seed.json") == {"near": ("s3",), "late": ("s8",)}


def test_a_scenes_flag_that_disagrees_with_the_forged_width_is_refused_naming_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Either number could be the wrong one, and only the operator knows which.

    Obeying the flag would silently drop the late reveal's position; obeying the record would
    silently overrule a person who typed a number. So it refuses, names both, and writes
    nothing — the bundle files are what a book gets seeded from.
    """
    out = tmp_path / "forge"
    _forge_file(out, scenes=8, mysteries=LATE_REVEAL)
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    assert (
        main(
            ["--database", str(database), "forge", "--out", str(out), "--pick", "1",
             "--scenes", "6"]
        )
        == 2
    )
    err = capsys.readouterr().err
    assert "--scenes 6" in err and "8 scene(s)" in err
    assert not (out / "seed.json").exists()

    # The same flag, agreeing, is an ordinary pick.
    assert (
        main(
            ["--database", str(database), "forge", "--out", str(out), "--pick", "1",
             "--scenes", "8"]
        )
        == 0
    )
    assert _positions(out / "seed.json") == {"near": ("s3",), "late": ("s8",)}


def test_a_forge_file_written_before_the_width_was_recorded_picks_as_it_always_did(
    tmp_path: Path,
) -> None:
    """No `scenes` key is every bundle already on disk, and none of them may start refusing.

    Absence means "nothing is recorded", not "recorded as six": the flag still decides, and
    with no flag the pick still falls back to `DEFAULT_SCENES` — which is the old behaviour,
    defect included. Parking those bundles over a fault none of them can be shown to have
    would be the cure doing more damage than the disease.
    """
    out = tmp_path / "forge"
    _forge_file(out, scenes=None, mysteries=LATE_REVEAL)
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0

    assert main(["--database", str(database), "forge", "--out", str(out), "--pick", "1"]) == 0
    assert _positions(out / "seed.json") == {"near": ("s3",)}

    assert (
        main(
            ["--database", str(database), "forge", "--out", str(out), "--pick", "1",
             "--scenes", "8"]
        )
        == 0
    )
    assert _positions(out / "seed.json") == {"near": ("s3",), "late": ("s8",)}


def test_the_forge_records_the_width_it_forged_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half that makes the pick's default possible, and the only test that runs the forge.

    A stub registry, so the generation branch runs with no provider anywhere. What is asserted
    is that `forge.json` carries the number every candidate's disclosure positions were minted
    at — a file that does not carry it is a file `--pick` has to guess about.
    """
    import litharness.cli as cli_module
    from litharness.providers.fake import FakeProvider
    from litharness.providers.registry import ProviderRegistry

    provider = FakeProvider()

    def two_worlds() -> str:
        # Two, and distinct in domain and geometry: `worlds_from` refuses K=1 as "not a search"
        # and refuses a K-way collapse.
        return json.dumps(
            {
                "worlds": [
                    world(),
                    world(title="Slack Water", domain="river ferry rights", geometry="cycle"),
                ]
            }
        )

    provider.set_responses([two_worlds()])
    monkeypatch.setattr(
        cli_module, "build_default_registry", lambda *a, **k: ProviderRegistry(provider)
    )

    out = tmp_path / "forge"
    database = tmp_path / "pilot.db"
    assert main(["--database", str(database), "init"]) == 0
    assert (
        main(["--database", str(database), "forge", "a brief", "--k", "2", "--out", str(out),
              "--scenes", "8"])
        == 0
    )
    assert json.loads((out / "forge.json").read_text(encoding="utf-8"))["scenes"] == 8

    # And with no flag it records the default rather than nothing, so the pick never guesses.
    other = tmp_path / "forge-default"
    provider.set_responses([two_worlds()])
    assert (
        main(["--database", str(database), "forge", "a brief", "--k", "2", "--out", str(other)])
        == 0
    )
    recorded = json.loads((other / "forge.json").read_text(encoding="utf-8"))["scenes"]
    assert recorded == architect.DEFAULT_SCENES


# -- re-materialising the pilot bundle -------------------------------------------------------
#
# `pilot2/` was gitignored and is gone; the committed world package is the source. Re-forging
# costs $1.53, yields a different world and needs a person to choose again, so a rerun on the
# same world re-materialises the bundle instead. `tools/rematerialise_forge_bundle.py`.


def _rematerialise():  # type: ignore[no-untyped-def]
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "tools" / "rematerialise_forge_bundle.py"
    spec = importlib.util.spec_from_file_location("rematerialise_forge_bundle", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_rematerialised_bundle_is_the_snapshot_the_pilot_ran_on(tmp_path: Path) -> None:
    """The seed the tool writes holds exactly `records_for`'s records, and they validate.

    This is the pin the whole rerun rests on: `serial-pilot-2-setup.ps1` refuses without a
    `seed.json`, and a seed that differed from the committed answer would put Serial Pilot 2's
    question to a different world while every command in the package still read the same.
    """
    tool = _rematerialise()
    out = tmp_path / "bundle"
    assert tool.main(["--out", str(out), "--created-at", "2026-08-22T00:00:00Z"]) == 0

    package = json.loads(
        (Path(__file__).resolve().parents[1] / "plan" / "serial-pilot-2-world.json").read_text(
            encoding="utf-8"
        )
    )
    expected = architect.records_for(
        architect.Candidate(package["picked"] - 1, package["world"]),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        scenes=8,
    )
    snapshot = lc.parse_artifact(
        lc.StateSnapshot,
        json.loads((out / "seed.json").read_text(encoding="utf-8")),
    )
    assert [record.record_id for record in snapshot.records] == [
        record.record_id for record in expected
    ]
    assert [lc.to_jsonable(record) for record in snapshot.records] == [
        lc.to_jsonable(record) for record in expected
    ]
    assert worlds.validate(snapshot.records) == ()
    assert {record.authority for record in snapshot.records} == {lc.StateAuthority.ACCEPTED_CANON}

    # The other two files are the ones `--pick` wrote, carried rather than rebuilt, and the
    # tool refuses unless they are the set this world produces.
    directives = json.loads((out / "directives.json").read_text(encoding="utf-8"))
    promises = json.loads((out / "promises.json").read_text(encoding="utf-8"))
    assert directives["title"] == package["world"]["title"]
    assert len(promises) == 6
    assert {row["subject"] for row in promises} >= {"m_holts_date", "m_orrin_last_call"}


def test_the_bundle_carries_the_ids_the_forge_minted_and_no_fresh_ones(tmp_path: Path) -> None:
    """Reproduced, not re-minted: `cmd_forge` derives all three uuids with `uuid5` over the
    architect id and the candidate's index, so a bundle materialised a day later carries the
    same ids the original did. `created_at` is the one field the package cannot recover, and
    nothing in the record depends on it — the records are identical either way, which is what
    the two runs below assert."""
    tool = _rematerialise()
    first, second = tmp_path / "a", tmp_path / "b"
    assert tool.main(["--out", str(first), "--created-at", "2026-08-22T00:00:00Z"]) == 0
    assert tool.main(["--out", str(second), "--created-at", "2030-01-01T00:00:00Z"]) == 0

    one = json.loads((first / "seed.json").read_text(encoding="utf-8"))
    two = json.loads((second / "seed.json").read_text(encoding="utf-8"))
    assert one["records"] == two["records"], "no record depends on the stamp"
    assert (one["book_id"], one["branch_id"], one["revision_id"]) == (
        two["book_id"],
        two["branch_id"],
        two["revision_id"],
    )
    assert one["meta"]["created_at"] != two["meta"]["created_at"]
    assert one["meta"]["artifact_id"] == "arch-e3b0c44298fc1c149afbf4c8-0"


def test_it_refuses_a_package_nobody_picked_and_a_bundle_that_already_exists(
    tmp_path: Path,
) -> None:
    """Two refusals, and neither is fussiness.

    A package with no `picked` is a forge whose operator act never happened, and a script that
    supplied one would be a machine wearing `VerdictSource.HUMAN` — the split `forge` exists
    to enforce. An existing bundle is `serial-pilot-2-setup.ps1`'s own refusal one step
    earlier: a directory silently rewritten under a run already using it is a book whose canon
    nobody can name afterwards.
    """
    tool = _rematerialise()
    package = json.loads(
        (Path(__file__).resolve().parents[1] / "plan" / "serial-pilot-2-world.json").read_text(
            encoding="utf-8"
        )
    )
    unpicked = tmp_path / "unpicked.json"
    unpicked.write_text(
        json.dumps({**package, "picked": None}, ensure_ascii=False), encoding="utf-8"
    )
    assert tool.main(["--out", str(tmp_path / "x"), "--world", str(unpicked)]) == 2
    assert not (tmp_path / "x").exists()

    out = tmp_path / "twice"
    assert tool.main(["--out", str(out), "--created-at", "2026-08-22T00:00:00Z"]) == 0
    assert tool.main(["--out", str(out), "--created-at", "2026-08-22T00:00:00Z"]) == 2


def test_a_scene_count_the_directives_were_not_written_for_is_refused(tmp_path: Path) -> None:
    """Story keys minted at one book length are not comparable to beat keys minted at another
    — run A's whole defect, one layer up (`"s1" > "s04"`, stage-0 §107.9.1 defect 10). The
    committed directives record the length they were written for, so the mismatch is a refusal
    rather than a book whose reveal schedule silently misses.

    And **omitting the flag reads the recorded length rather than a default**: the hand-carried
    scene count is the defect `plan/serial-pilot-4.md` §5.6 measured on `forge --pick`, and a
    tool that rebuilds the same bundle should not keep a hard-coded 8 for one pilot's world.
    """
    tool = _rematerialise()
    assert tool.main(["--out", str(tmp_path / "y"), "--scenes", "12"]) == 2
    assert not (tmp_path / "y").exists()

    plain = tmp_path / "recorded"
    given = tmp_path / "by-hand"
    assert tool.main(["--out", str(plain), "--created-at", "2026-08-23T00:00:00Z"]) == 0
    assert tool.main(["--out", str(given), "--scenes", "8", "--created-at",
                      "2026-08-23T00:00:00Z"]) == 0
    for name in ("seed.json", "directives.json", "promises.json"):
        assert (plain / name).read_text(encoding="utf-8") == (
            given / name
        ).read_text(encoding="utf-8")

    # A bundle recorded at some *other* width, so "reads the record" is distinguishable from
    # "happens to match the pilot the defaults were written for".
    narrow = world()
    narrow["mysteries"] = [dict(narrow["mysteries"][0], disclosed_at_scene=3)]
    candidate = architect.Candidate(0, narrow)
    package = tmp_path / "narrow-world.json"
    package.write_text(
        json.dumps(
            {"architect_id": "arch-narrow", "k": 2, "picked": 1, "world": narrow},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    directives = tmp_path / "narrow-directives.json"
    directives.write_text(
        json.dumps(
            {
                "source": str(package),
                "title": narrow["title"],
                "premise": narrow["premise"],
                "scenes": 6,
                "directives": [dict(item) for item in architect.directives_for(candidate)],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    promises = tmp_path / "narrow-promises.json"
    promises.write_text(
        json.dumps([dict(item) for item in architect.promises_for(candidate)], ensure_ascii=False),
        encoding="utf-8",
    )
    narrow_out = tmp_path / "narrow"
    assert (
        tool.main(
            ["--out", str(narrow_out), "--world", str(package), "--directives", str(directives),
             "--promises", str(promises), "--created-at", "2026-08-23T00:00:00Z"]
        )
        == 0
    )
    seed = lc.parse_artifact(
        lc.StateSnapshot, json.loads((narrow_out / "seed.json").read_text(encoding="utf-8"))
    )
    assert worlds.disclosures(seed.records) == {"the_tide": ("s3",)}


# --- the ladder the reader counts (plan/handoff-numbers-go-up.md Task 1) -----------------------


def _no_standing(entry: dict[str, Any]) -> dict[str, Any]:
    """The same world with its protagonist's standing removed — a world forged before 2026-08-22."""
    protagonist = {
        key: value for key, value in entry["protagonist"].items() if key != "standing"
    }
    return {**entry, "protagonist": protagonist}


def test_a_forged_world_that_places_nobody_on_its_ladder_is_refused() -> None:
    """The forge must say where its protagonist starts; `records_for` must not require it.

    Measured on the four worlds forged before this rule (`plan/handoff-numbers-go-up.md`
    Task 0.2): two of them declared an ordinal criterion with a chain of four and five rungs,
    and **not one cast member of any of the four carried a standing on any chain**. A ladder
    with nobody on it is a costume with nobody in it, and nothing downstream complained because
    nothing downstream was looking.
    """
    with pytest.raises(architect.ArchitectOutputError, match="names no standing"):
        architect.worlds_from(
            payload(
                _no_standing(world()),
                world(domain="coopering", geometry="cycle"),
                world(domain="glassblowing", geometry="chain"),
            ),
            3,
        )
    for missing in ("criterion", "rung"):
        broken = world()
        broken["protagonist"] = {
            **broken["protagonist"],
            "standing": {**broken["protagonist"]["standing"], missing: ""},
        }
        with pytest.raises(architect.ArchitectOutputError, match=f"standing has no {missing}"):
            architect.worlds_from(
                payload(
                    broken,
                    world(domain="coopering", geometry="cycle"),
                    world(domain="glassblowing", geometry="chain"),
                ),
                3,
            )


def test_a_standing_round_trips_from_the_answer_to_a_rung_and_a_number() -> None:
    """`records_for` → `standing_of` / `rung_index`, which is the whole of "the number".

    The operator's direction is that the rank ladder *is* the number — bronze is 1 and gold is
    3 — so what a round trip has to preserve is the rung's place in the chain counting from the
    bottom, not an integer anybody stored.
    """
    records = architect.records_for(
        candidate(), authority=lc.StateAuthority.ACCEPTED_CANON, scenes=SCENES
    )
    assert worlds.ladder_of(records, "assay_grade") == (
        "third_seal",
        "second_seal",
        "first_seal",
    )
    assert worlds.standing_of(records, "silas") == {"assay_grade": "second_seal"}
    assert worlds.rung_index(records, "assay_grade", "third_seal") == 1
    assert worlds.rung_index(records, "assay_grade", "second_seal") == 2
    assert worlds.rung_index(records, "assay_grade", "first_seal") == 3
    assert worlds.criterion_of_rung(records, "second_seal") == "assay_grade"
    # The edge is flat and carries its criterion in the value slot, exactly as `precedes` does,
    # because the page can only print a flat edge and both copies have to read the same way.
    [standing] = [
        record for record in records if record.predicate == worlds.STANDS_AT_PREDICATE
    ]
    assert standing.subject == "silas"
    assert standing.object_ref == "second_seal"
    assert standing.value == "assay_grade"
    # Placed at the opening, so a milestone can be *after* it. An unplaced standing sits in
    # every window and could never be compared against a schedule.
    assert standing.story_position is not None
    assert standing.story_position.order_key == architect.story_key(1, scenes=SCENES)
    assert worlds.validate(records) == ()


def test_a_rung_in_two_chains_is_a_complaint_rather_than_a_guess() -> None:
    """Which ladder a standing counts on has to be one answer (boundary 9)."""
    entry = world()
    entry["systems"].append(
        {
            "id": "the_bench",
            "name": "the bench",
            "logic": "a second order over the same seals",
            "manifests_as": "a bench list read out on quarter-day",
            "rules": [],
            "criterion": {
                "id": "bench_grade",
                "comparator": "ordinal",
                "evaluates": "appraiser",
                "ranks": [
                    {"id": "second_seal", "visible_form": "brass", "cost_to_reach": "a year"},
                    {"id": "bench_two", "visible_form": "a chair", "cost_to_reach": "two years"},
                    {"id": "bench_one", "visible_form": "the chair", "cost_to_reach": "a name"},
                ],
            },
        }
    )
    records = architect.records_for(
        architect.Candidate(0, entry),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        scenes=SCENES,
    )
    assert worlds.criterion_of_rung(records, "second_seal") is None
    complaints = worlds.validate(records)
    assert any("sits in 2 chains" in item for item in complaints), complaints


def test_the_gate_counts_the_ladder_and_never_judges_it() -> None:
    """Five membership complaints, and silence for a world that declares no standing."""
    assert gate(candidate()) == ()

    # No chain long enough to count on.
    short = world()
    short["systems"][0]["criterion"]["ranks"] = short["systems"][0]["criterion"]["ranks"][:2]
    short["protagonist"]["standing"] = {"criterion": "assay_grade", "rung": "third_seal"}
    assert any("at least 3" in item for item in gate(short)), gate(short)

    # A criterion this world never declared.
    stray = world()
    stray["protagonist"]["standing"] = {"criterion": "nowhere", "rung": "second_seal"}
    assert any("not a criterion this world declares" in item for item in gate(stray))

    # A rung that is not on that criterion's chain.
    off = world()
    off["protagonist"]["standing"] = {"criterion": "assay_grade", "rung": "fourth_seal"}
    assert any("not a rank of assay_grade" in item for item in gate(off))

    # The top of the only ladder declared.
    top = world()
    top["protagonist"]["standing"] = {"criterion": "assay_grade", "rung": "first_seal"}
    assert any("nowhere on it to go" in item for item in gate(top))

    # A ladder and no printed form for a change of standing.
    silent = world()
    silent["graph_line"] = {
        "label": "SYSTEM",
        "edges": [{"phrase": "is recognised as", "predicate": "recognized_by"}],
    }
    assert any("no phrase whose predicate is" in item for item in gate(silent))
    del silent["graph_line"]
    assert any("declares a ladder and no graph_line" in item for item in gate(silent))

    # Silent for every world forged before 2026-08-22.
    assert architect._ladder_complaints(architect.Candidate(0, _no_standing(world()))) == ()


def test_the_report_counts_the_ladder_and_a_world_without_one_reports_zero() -> None:
    """Counters, and the no-ladder control is byte-identical records."""
    note = architect.report(candidate(), scenes=SCENES)
    assert note["ladders"] == 1
    assert note["rungs_per_ladder"] == {"assay_grade": 3}
    assert note["opening_rung_index"] == 2
    assert note["graph_line_declared"] is True
    assert note["inversion_text"] == world()["inversion"]
    # A counter, not a verdict: nothing in the report orders one candidate above another.
    assert not {key for key in note if "score" in key or "rank" in key.split("_")}

    bare = _no_standing(world())
    bare["systems"][0]["criterion"]["comparator"] = "set_inclusion"
    empty = architect.report(architect.Candidate(0, bare), scenes=SCENES)
    assert empty["ladders"] == 0
    assert empty["rungs_per_ladder"] == {}
    assert empty["opening_rung_index"] is None
    # And the records such a world makes are exactly the records it made before this existed:
    # no `stands_at` edge at all.
    records = architect.records_for(architect.Candidate(0, bare), scenes=SCENES)
    assert not [r for r in records if r.predicate == worlds.STANDS_AT_PREDICATE]
