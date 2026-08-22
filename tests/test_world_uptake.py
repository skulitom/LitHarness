"""Arithmetic for `research/quality-measurement/world_uptake.py`, and the two controls in it.

**Why research code has tests in this suite**, for `test_world_lexicon.py`'s reason: the
properties below are the ones a reader cannot check by eye, and a census over two eight-scene
runs and twenty-one control books would discover them only after it had run. Neither corpus is
touched here — the point is the algebra, the enumeration and the shape of the sham.

**Nothing here asserts a bar.** The census reports distributions; the one pass/fail quantity in
that module is the sham's own share against `SHAM_CEILING`, and what is pinned below is that the
sham *can* fire and *can* stay quiet, which is the property a control has to have before its
answer means anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(RESEARCH))

import world_uptake  # noqa: E402

from litharness.domain import worlds  # noqa: E402


def test_the_selftest_passes() -> None:
    """Every research module here that skipped its selftest shipped a defect a dry run had."""
    assert world_uptake.selftest() == 0


def test_a_minted_suffix_is_not_part_of_a_name() -> None:
    """`records_for` mints `_secret`, `_belief`, `_nature`, `_view`, `_reveal` and `_joint`.

    Ten of the pilot world's twenty-eight claims are `<subject>_secret`. Left in, the word
    *secret* appearing once anywhere in 7,812 words would name all ten of them at once — a
    counter measuring the record pattern's vocabulary instead of the world's. Only a trailing
    suffix is dropped, so a world that genuinely coins a thing called a secret keeps it.
    """
    assert world_uptake._id_tokens("c_wren_holt_secret") == {"wren", "holt"}
    assert world_uptake._id_tokens("s_the_call_nature") == {"call"}
    assert world_uptake._id_tokens("m_secret_valley") == {"secret", "valley"}


def test_whole_word_means_letters_and_nothing_else() -> None:
    """The tokenisation is the counting rule, and it is registered as crude in both directions.

    An apostrophe and a hyphen are boundaries, so *watermaster's* yields `watermaster` and
    *gate-moth* yields both halves. There is no stemming, so the plural id part `watermasters`
    does **not** match the singular possessive on the page — which is a real miss the census
    reports rather than repairs, because inflecting the matcher after seeing which features it
    missed is the failure `platform_priors.py` freezes its matchers to avoid.
    """
    assert "watermaster" in world_uptake._words("the watermaster's order")
    assert "watermasters" not in world_uptake._words("the watermaster's order")
    assert {"gate", "moth"} <= world_uptake._words("a gate-moth on the row")
    assert world_uptake._words("1449") == set()


def test_the_enumeration_covers_the_kinds_the_projection_leaves_out() -> None:
    """`domain/worlds.py::features` counts what a reader must *see* and excludes cast, places
    and institutions on purpose. This census asks a different question — what is ever named —
    and a cast member nobody names is exactly the thing it exists to count, so its enumeration
    is deliberately the wider one and this pins that they differ."""
    records = [
        worlds.world_record("c_ada_serrell", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
        worlds.world_record("c_ada_serrell", "is_a", value="Watermaster of the Kettle Basin"),
        worlds.world_record("r_first_in_time", worlds.WORLD_RULE_PREDICATE, value="Oldest first."),
        worlds.world_record(
            "r_first_in_time", worlds.CONSEQUENCE_PREDICATE, value="Fields sell on a date.",
            object_ref="economy",
        ),
    ]
    found = world_uptake.features_of(records, scenes=8)
    kinds = {feature.kind for feature in found}
    assert kinds == {"entity", "rule", "consequence"}
    assert "c_ada_serrell" not in worlds.features(records)
    cast = next(f for f in found if f.feature_id == "c_ada_serrell")
    # **`Watermaster` is absent, and that is the shipped rule rather than a miss here.**
    # `key_nouns`' inner-capital lookbehind exists so that a sentence-initial `Not` never
    # becomes a coined name, and it costs a sentence-initial `Watermaster` in the same breath.
    # The census inherits the cost rather than patching it, and reports it: the whole reason
    # `i_watermasters_office` can only be reached through its plural id part is this line.
    assert cast.wide == {"serrell", "kettle", "basin"}


def test_the_sham_can_fire_and_can_stay_quiet() -> None:
    """A control that cannot fail is not a control, and one that always fails is not either."""
    records = [
        worlds.world_record("c_ada_serrell", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
    ]
    found = world_uptake.features_of(records, scenes=8)
    loud = world_uptake.sham(
        found, [("a", "Serrell signed it.")], ordinary=frozenset(), leg="wide"
    )
    assert loud["median_share_per_book"] == 1.0
    assert loud["verdicts"]["median_per_book"] == "FIRES ABOVE ITS CEILING"
    assert [row["token"] for row in loud["colliding_tokens"]] == ["serrell"]

    quiet = world_uptake.sham(
        found, [("a", "Nobody signed anything.")], ordinary=frozenset(), leg="wide"
    )
    assert quiet["median_share_per_book"] == 0.0
    assert quiet["verdicts"]["median_per_book"] == "PASS"
    assert quiet["colliding_tokens"] == []


def test_narrowing_to_coined_forms_removes_the_shelf_and_nothing_else() -> None:
    """The `coined` leg is `wide` minus what the genre already owns, and both are always
    reported. The narrowing is defined against the RoyalRoad shelf rather than against the sham
    corpus on purpose: a narrowing defined by the control it has to survive is a control that
    cannot fire."""
    records = [
        worlds.world_record("c_ada_serrell", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
        worlds.world_record("p_kettle_basin", worlds.ENTITY_ROLE_PREDICATE, value="place"),
    ]
    found = {f.feature_id: f for f in world_uptake.features_of(records, scenes=8)}
    shelf = frozenset({"kettle", "basin"})
    assert found["p_kettle_basin"].names(shelf, leg="wide") == {"kettle", "basin"}
    assert found["p_kettle_basin"].names(shelf, leg="coined") == frozenset()
    assert found["c_ada_serrell"].names(shelf, leg="coined") == {"serrell"}


def test_a_hidden_claim_is_never_pooled_with_the_rest() -> None:
    """The hidden section is *supposed* to go unnamed. Counting its silence beside the ordinary
    features would make the design working look like the world failing to reach the page."""
    records = [
        worlds.world_record("m_the_tide", worlds.CLAIM_CONTENT, value="the tide is aimed"),
        worlds.world_record("m_the_tide", worlds.QUESTION_PREDICATE, value="what is it for"),
        worlds.world_record("m_the_tide", worlds.REVEAL_SCENE, value=7),
        worlds.world_record("c_ada_serrell", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
    ]
    found = world_uptake.features_of(records, scenes=8)
    assert {f.feature_id for f in found if f.hidden_at_start} == {"m_the_tide"}
    report = world_uptake.census(
        found,
        [{"ordinal": 1, "scene_plan": "", "prose": "Serrell watched the tide."}],
        premise="A book.",
        ordinary=frozenset(),
        leg="wide",
    )
    assert report["all_declared_features"]["raw"]["declared"] == 1
    assert report["hidden_claims"]["raw"]["declared"] == 1


def test_the_premise_baseline_is_subtracted_from_the_name_set_and_not_from_the_page() -> None:
    """Control B. The planner and the writer both read the premise, so a name the premise
    already carries proves nothing about whether 329 records reached the page. What is removed
    is the *name*, never the prose — removing words from the page would change what every other
    feature is measured against."""
    records = [
        worlds.world_record("c_wren_holt", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
        worlds.world_record("c_ada_serrell", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
    ]
    found = world_uptake.features_of(records, scenes=8)
    report = world_uptake.census(
        found,
        [{"ordinal": 1, "scene_plan": "", "prose": "Wren found Serrell at the gate."}],
        premise="Wren Holt rides ditch for the watermaster.",
        ordinary=frozenset(),
        leg="wide",
    )
    raw = report["all_declared_features"]["raw"]
    beyond = report["all_declared_features"]["beyond_premise"]
    assert raw["ever_named_in_prose"] == 2
    assert beyond["nameable"] == 1, "the premise already carried Wren Holt"
    assert beyond["ever_named_in_prose"] == 1


def test_the_packet_fact_block_is_read_off_the_prompt_the_writer_was_handed() -> None:
    """Not reassembled from the records: the packet drops whatever the budget could not hold,
    and the frozen prompt is what was actually asked. On Serial Pilot 2 the two agree because
    `context_omitted` is 0 for the whole book; on any run where they disagree the prompt wins."""
    prompt = (
        "Premise: x\n\nEstablished facts:\n- Rule -- the river answers a date.\n"
        "- Serrell holds no date at all.\n\n"
        "True, and the reader has not been told -- x:\n- a secret nobody may state\n"
    )
    facts = world_uptake.packet_facts(prompt)
    assert facts == ("Rule -- the river answers a date.", "Serrell holds no date at all.")
    measured = world_uptake.packet_fact_uptake(
        facts,
        "Serrell signed it and said nothing.",
        vocabulary=frozenset({"serrell", "river"}),
        premise="A book about a river.",
    )
    assert measured["countable"] == 2
    assert measured["never_named"] == 1
    # `river` is the premise's; only Serrell is evidence the records reached the page.
    assert measured["named_beyond_premise"] == 1
