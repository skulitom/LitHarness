"""Pins for the pure counters of research/quality-measurement/number_context.py.

Every case here is hand-derived from text on disk. The mundane fixtures are read 8 §4.1's own
exhaustive list for *Unlicensed Weather* chapter 1, held as detector material and nothing else
(§97.1); the refused cases are shapes a first version actually drew and a hand-check rejected,
so each narrowing has a receipt that fails if it is ever loosened back.

Nothing here claims a number in any family harms a reader. These tests pin what the counter
counts.
"""

from __future__ import annotations

import pytest

number_context = pytest.importorskip(
    "number_context",
    reason="research module; needs the quality-measurement directory on the path",
)


def families(text: str) -> list[str]:
    return [family for _surface, family in number_context.family_of(text)]


def test_the_modules_own_selftest_passes() -> None:
    """The frozen block, the fixtures, the refusals and the unit rules, in one call."""
    assert number_context.selftest() == []


def test_every_operator_named_item_lands_in_its_hand_counted_family() -> None:
    """Read 8 §4.1's list is the ground truth this instrument exists to reproduce."""
    for text, expected in number_context.FIXTURE_MUNDANE:
        assert expected in families(text), text


def test_every_hand_checked_false_positive_stays_refused() -> None:
    """`one` as a pronoun, and the indefinite article the registration refuses to count."""
    for text in number_context.FIXTURE_REFUSED:
        located = [
            family
            for family in families(text)
            if family in {*number_context.MUNDANE_CORE, "object_count"}
            or family.startswith("system")
        ]
        assert located == [], (text, located)


def test_an_hour_of_rain_is_refused_and_the_registration_says_so() -> None:
    """The operator's own list has one member this instrument cannot see, on purpose.

    `a` and `an` are not numerals. Admitting them would sweep in every indefinite noun phrase
    in the language, which is not precision -- so the recall hole is declared in
    `PRE_REGISTRATION["refused"]` rather than patched with a special case.
    """
    assert families("An hour of rain on your table by noon.") == []
    assert "indefinite_article_durations" in number_context.PRE_REGISTRATION["refused"]


def test_the_head_window_stops_at_a_preposition_once_a_head_is_found() -> None:
    """`the first surprise of the morning` is an enumeration and not a duration.

    A first version walked a flat four-token window and reached `morning` past `surprise`,
    reporting a calendar mention where the numeral enumerates surprises. The partitive `of` is
    only transparent BEFORE a head has been seen, which is what keeps `four of the guild's
    jars` a count of jars.
    """
    assert families("That was the first surprise of the morning.") == ["ordinal_enumeration"]
    assert families("Four of the guild's jars rode in a frame.") == ["object_count"]


def test_ordinality_is_read_off_the_last_token_of_a_merged_run() -> None:
    """`twenty-second` opens on a cardinal and is an ordinal, and a first version disagreed."""
    assert families("At the twenty-second jar she stopped.") == ["ordinal_enumeration"]


def test_adjectives_and_quantity_modifiers_do_not_hide_a_closed_lexicon_head() -> None:
    assert families("He waited two long days.") == ["calendar_duration"]
    assert families("He waited three more days.") == ["calendar_duration"]


def test_adjacent_numerals_are_one_mention_and_an_arrow_is_two() -> None:
    """The unit rule, and the status-block case that corrected it.

    Adjacency in the token list is not adjacency on the line: the tokeniser emits no `->`, so
    `Strength 14 -> 17` was being merged into a single mention and a five-number status block
    reported three.
    """
    assert len(number_context.locate("She counted twenty-two jars, then two or three more.")) == 2
    assert len(number_context.locate("[Strength 14 -> 17]")) == 2


def test_a_system_magnitude_and_a_system_ordinal_are_different_columns() -> None:
    """The split our own shelf forced, and the reason a single `system` column would lie.

    Every system-anchored number on the shelf is an ordinal on a ladder word -- `fourth grade`,
    `THIRD TIER` -- and not one is a magnitude. A ladder position and a quantity on a sheet are
    different objects.
    """
    assert families("You'll want the fourth-grade price.") == ["system_ordinal"]
    assert families("He reached level 12 that morning.") == ["system_magnitude"]
    assert "system" not in number_context.FAMILIES


def test_a_labelled_slot_governs_its_number_but_at_that_point_does_not() -> None:
    """The preceding-anchor window is one token and its lexicon is deliberately narrow.

    `at that point three days later` puts a system word immediately before a mundane numeral.
    Admitting `point` as a preceding anchor turned a duration into a stat, so it is not one.
    """
    assert families("He reached rank 3 that year.") == ["system_magnitude"]
    assert families("At that point three days had gone.") == ["calendar_duration"]


def test_mundane_core_never_includes_object_count_or_ordinals() -> None:
    """The lowest-precision families are reported and never pooled into the headline.

    `object_count` finds its head by a stopword rule rather than a closed lexicon, and an
    ordinal date cannot be told from an ordinal enumeration without a parser. A count named for
    one defect that measures another is the lying column stage-0 §150.4 deleted a field for.
    """
    assert set(number_context.MUNDANE_CORE) == {
        "calendar_duration",
        "age",
        "money",
        "measure",
    }
    row = number_context.measure("She counted thirty jars over eight days.")
    assert row.by_family["object_count"] == 1
    assert row.by_family["calendar_duration"] == 1
    assert row.mundane_core == 1


def test_system_any_is_the_only_sum_and_both_halves_survive_it() -> None:
    row = number_context.measure("He reached level 12. You'll want the fourth-grade price.")
    assert row.by_family["system_magnitude"] == 1
    assert row.by_family["system_ordinal"] == 1
    assert row.system_any == 2


def test_a_status_block_is_system_by_location_and_a_scene_divider_is_nothing() -> None:
    """The furniture line shapes are copied from `progression_cadence.v0`, correction included.

    A run of frame characters is a scene divider that every fiction on the platform uses, and
    counting it would put every one of them inside a status block.
    """
    block = number_context.measure("[Mana: 240/300]\n[Level 12]")
    assert block.by_family["system_magnitude"] == 3
    assert number_context.measure("He stopped.\n\n***\n\nShe did not.").mentions == 0


def test_the_recorded_false_positive_is_still_recorded() -> None:
    """A measured error with no mechanical fix is kept visible, not quietly borne.

    `three levels of it below the lobby` is a parking structure. `levels` is also the anchor
    this genre's sheet uses, and nothing short of a sense disambiguator separates them, so both
    halves of every comparison carry the same small architectural contamination.
    """
    assert number_context.MEASURED_FALSE_POSITIVES
    for text, family in number_context.MEASURED_FALSE_POSITIVES:
        assert family in families(text)


def test_the_registration_declares_no_bar_and_names_its_direction() -> None:
    """`REGISTERED` under EPISTEMIC_GOVERNANCE means the direction was fixed before the run."""
    registration = number_context.PRE_REGISTRATION
    assert "REGISTERED DIRECTION" in registration["predicted"]
    declaration = registration["declares_no_bar"]
    assert declaration.startswith("No target density, ratio or floor is declared")
    assert "four attainability checks" not in declaration or "range at the real n" in declaration
    assert registration["residuals"]
    assert number_context.registration_digest() == number_context.REGISTRATION_DIGEST


def test_density_is_per_thousand_words_and_a_share_is_none_when_nothing_anchors() -> None:
    row = number_context.measure(" ".join(["word"] * 999 + ["days"]))
    assert row.words == 1000
    assert row.system_share_of_anchored is None
    counted = number_context.measure("eight days " + " ".join(["word"] * 998))
    assert counted.per_1k(counted.by_family["calendar_duration"]) == pytest.approx(1.0)
