"""The pure correspondence arithmetic of state_coverage.py, pinned at the unit level.

These tests fix what `cost_units`, `tracked_units`, `coverage` and `unexplained_gains` return
for inputs whose correct answer is derivable by hand from the module's own rules: which units
the prose charges in, which field names the system voice keeps, how the two sets meet, and when
a tracked rise counts as unexplained. They do not establish that the measure separates our books
from published LitRPG — that is the human-control question the module itself defers — and they
say nothing about the corpus loaders, the report assembly, or the lexicons being complete.

Hermetic: no corpus, no database, no model, no subprocess. Everything here is regex and
arithmetic over strings the tests construct.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

state_coverage = pytest.importorskip(
    "state_coverage",
    reason="research module; needs the quality-measurement directory on the path",
)


# --- cost_units -----------------------------------------------------------------


def test_cost_units_counts_the_units_a_transaction_word_sits_beside():
    text = "The toll took 7 days of his remaining life. He paid 9 coppers for passage."
    # "toll" sits within the 60-char window before "7 days"; "paid" before "9 coppers".
    # Units are singularised: "days" -> "day", "coppers" -> "copper".
    assert state_coverage.cost_units(text) == {"day": 1, "copper": 1}


def test_cost_units_counts_a_repeated_unit_once_per_charge():
    text = "The toll is 5 silver today, and tomorrow the toll rises to 8 silver."
    assert state_coverage.cost_units(text) == {"silver": 2}


def test_cost_units_ignores_a_quantity_no_transaction_word_sits_within_the_window():
    # "toll" is more than 60 characters before the quantity, so it falls outside the window.
    text = "toll " + "a" * 90 + " 4 gems at the gate."
    assert state_coverage.cost_units(text) == {}


def test_cost_units_never_counts_the_ordinary_noun_units():
    # "miles" is excluded by the not-a-resource lexicon even though "paid" sits within
    # the window of "12 miles" — proximity alone does not make travel a cost.
    text = "The toll was 40 gold, and the road ran 12 miles before he paid for bread."
    assert state_coverage.cost_units(text) == {"gold": 1}


def test_cost_units_skips_units_shorter_than_three_letters():
    # The quantity pattern needs a unit of at least three letters, so "5 kg" is not a match.
    assert state_coverage.cost_units("He paid 5 kg of salt.") == {}


def test_cost_units_of_empty_text_is_empty():
    assert state_coverage.cost_units("") == {}


# --- tracked_units --------------------------------------------------------------


def test_status_line_fields_enter_the_tracked_set():
    text = "[STATUS] HP: 10 | Mana: 5 | Gold: 100"
    assert state_coverage.tracked_units(text) == {"hp", "mana", "gold"}


def test_colon_sheet_lines_enter_the_tracked_set():
    text = "Strength: 45\nLevel: 3"
    assert state_coverage.tracked_units(text) == {"strength", "level"}


def test_bracket_sheet_fields_enter_the_tracked_set():
    text = "[ Strength : 0.1 ( Tier 0 ) ]\n[ Agility : 3 ]"
    assert state_coverage.tracked_units(text) == {"strength", "agility"}


def test_plural_labels_are_singled_before_entering_the_tracked_set():
    text = "Tolls: 4\nGems: 9\nDays: 6"
    assert state_coverage.tracked_units(text) == {"toll", "gem", "day"}

# --- coverage -------------------------------------------------------------------


def test_coverage_is_full_when_the_record_tracks_every_charged_unit():
    text = "The toll is 10 gold.\n[STATUS] HP: 5 | Gold: 100"
    result = state_coverage.coverage(text)
    assert result["cost_units"] == {"gold": 1}
    assert result["tracked"] == ["gold", "hp"]
    assert result["covered"] == ["gold"]
    assert result["uncovered"] == []
    assert result["coverage"] == 1.0
    assert result["weighted_coverage"] == 1.0


def test_coverage_matches_a_tracked_name_that_merely_contains_the_unit():
    # The record keeps "Gold Coins"; the prose charges in "gold". Either-direction
    # substring matching makes that a hit.
    text = "The toll is 10 gold.\nGold Coins: 5"
    result = state_coverage.coverage(text)
    assert result["covered"] == ["gold"]
    assert result["coverage"] == 1.0


def test_coverage_counts_a_unit_uncovered_when_no_tracked_name_relates_to_it():
    # The prose charges in silver and days; the sheet keeps silver but not days.
    text = (
        "Each crossing costs 3 silver and 6 days of his life.\n"
        "[STATUS] HP: 5/5 | Level: 2\n"
        "[ Silver : 12 ]"
    )
    result = state_coverage.coverage(text)
    assert result["cost_units"] == {"silver": 1, "day": 1}
    assert result["tracked"] == ["hp", "level", "silver"]
    assert result["covered"] == ["silver"]
    assert result["uncovered"] == ["day"]
    assert result["coverage"] == 0.5
    assert result["weighted_coverage"] == 0.5


def test_coverage_weights_by_how_often_each_unit_is_charged():
    # Two charges in gold and one in days, with only gold tracked: half the distinct
    # units are covered but two-thirds of the charges are.
    text = (
        "The toll takes 4 gold. The toll takes 9 gold again, and 6 days pass "
        "beyond the ledger.\n"
        "Gold: 13"
    )
    result = state_coverage.coverage(text)
    assert result["cost_units"] == {"gold": 2, "day": 1}
    assert result["coverage"] == 0.5
    assert result["weighted_coverage"] == pytest.approx(2 / 3, abs=1e-3)


def test_coverage_is_none_when_the_prose_charges_nobody():
    result = state_coverage.coverage("He walked 7 miles and counted 12 paces.")
    assert result["cost_units"] == {}
    assert result["tracked"] == []
    assert result["coverage"] is None
    assert result["reason"]


def test_coverage_of_empty_text_is_none_with_no_units_or_tracking():
    result = state_coverage.coverage("")
    assert result["cost_units"] == {}
    assert result["tracked"] == []
    assert result["coverage"] is None


# --- unexplained_gains ----------------------------------------------------------


def test_a_tracked_value_rising_between_scenes_without_license_is_flagged():
    scenes = [("s1", "[STATUS] HP: 10"), ("s2", "[STATUS] HP: 15")]
    assert state_coverage.unexplained_gains(scenes) == [{
        "field": "hp", "from": 10, "to": 15,
        "from_scene": "s1", "to_scene": "s2", "delta": 5,
    }]


def test_a_rise_licensed_by_the_prose_is_not_flagged():
    scenes = [("s1", "[STATUS] HP: 10"), ("s2", "He drank a healing potion. [STATUS] HP: 15")]
    assert state_coverage.unexplained_gains(scenes) == []


def test_a_falling_or_unchanged_value_is_never_flagged():
    scenes = [
        ("s1", "[STATUS] HP: 10 | Mana: 4"),
        ("s2", "[STATUS] HP: 4 | Mana: 4"),
    ]
    assert state_coverage.unexplained_gains(scenes) == []


def test_only_the_rising_field_is_flagged_when_other_fields_fall():
    scenes = [
        ("s1", "[STATUS] HP: 10 | XP: 5"),
        ("s2", "[STATUS] HP: 6 | XP: 9"),
    ]
    assert state_coverage.unexplained_gains(scenes) == [{
        "field": "xp", "from": 5, "to": 9,
        "from_scene": "s1", "to_scene": "s2", "delta": 4,
    }]


def test_fraction_values_flag_on_the_numerator():
    scenes = [("s1", "[STATUS] HP: 8/20"), ("s2", "[STATUS] HP: 12/20")]
    assert state_coverage.unexplained_gains(scenes) == [{
        "field": "hp", "from": 8, "to": 12,
        "from_scene": "s1", "to_scene": "s2", "delta": 4,
    }]


def test_non_numeric_values_are_skipped_without_crashing():
    scenes = [("s1", "[STATUS] HP: ?/?"), ("s2", "[STATUS] HP: ?/30")]
    assert state_coverage.unexplained_gains(scenes) == []


def test_bracket_sheet_values_do_not_feed_the_gain_check():
    # The gain check reads only the [STATUS]-line shape, so bracket-sheet rises are
    # invisible to it by construction.
    scenes = [("s1", "[ Gold : 5 ]"), ("s2", "[ Gold : 9 ]")]
    assert state_coverage.unexplained_gains(scenes) == []


def test_unexplained_gains_of_no_scenes_is_empty():
    assert state_coverage.unexplained_gains([]) == []



def test_not_a_resource_words_never_enter_the_tracked_set():
    # Labels are singularised first ("Was" would become "wa" and slip through), so these
    # are chosen because their stripped forms are themselves in the not-a-resource lexicon.
    text = "Men: 3\nIt: 5\nHad: 4\nThem: 6\nGold: 7"
    assert state_coverage.tracked_units(text) == {"gold"}


def test_a_four_word_label_tracks_and_a_five_word_label_does_not():
    # Four words is a stat name; five is a sentence that happened to contain a colon.
    # The surviving label is singularised like any other: trailing "s" stripped.
    text = "Debt Of Lost Days: 7\nThe Toll Of Passing Days: 7"
    assert state_coverage.tracked_units(text) == {"debt of lost day"}


def test_tracked_units_of_empty_text_is_empty():
    assert state_coverage.tracked_units("") == set()
