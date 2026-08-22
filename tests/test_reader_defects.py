"""Hand-derived pins on the two pure functions of ``reader_defects``.

``identity`` is the untouched-scene control side of every arm, so it must return its input
verbatim and ignore ``strength`` completely — any edit it made would silently corrupt every
comparison anchored on it. ``verdict`` is the pre-registered reading of win rates: the per-arm
positional-bias band is checked first (anything outside 0.40-0.60, or not a float, voids the
arm before its rate is looked at), then the point thresholds classify DETECTS / BLIND / PREFERS,
and the stricter second ladder additionally demands the two-way interval exclude 0.50 in the
claimed direction before a threshold-clearing arm may stand. The roll-up lists and the
formatting-confound note are derived from those classifications.

These tests establish only the classification arithmetic on inputs whose correct answer was
stated before running anything. They do not establish that the transforms manufacture their
defects, that any elicited number is real, or that the pre-registration prose says anything in
particular: everything here is dictionary and string handling, with no database, corpus,
results file, model call, subprocess, or sleep involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

reader_defects = pytest.importorskip(
    "reader_defects",
    reason="research module; needs the quality-measurement directory on the path",
)

MATCHED = "interiority_vs_matched"
CONFOUNDED = "interiority_vs_original"
STATS = "stat_flatten_vs_original"
ALL_ARMS = (MATCHED, CONFOUNDED, STATS)


def rates(**overrides: float) -> dict[str, float]:
    """Every arm present at the null 0.5 unless a test overrides named arms."""
    values: dict[str, float] = {arm: 0.5 for arm in ALL_ARMS}
    values.update(overrides)
    return values


def bias(**overrides: float) -> dict[str, dict[str, float]]:
    """Every arm's positional bias at mid-band 0.5 unless a test overrides named arms."""
    return {arm: {"chose_A_rate": overrides.get(arm, 0.5)} for arm in ALL_ARMS}


# --------------------------------------------------------------------------- identity


def test_identity_returns_the_text_it_was_given_unchanged():
    scene = "Rook counted the coins twice.\n\n“Forty-five,” he said — and lied."
    assert reader_defects.identity(scene, 1.0) == scene


def test_identity_preserves_an_empty_string():
    assert reader_defects.identity("", 1.0) == ""


def test_identity_preserves_a_whitespace_only_string():
    text = "  \n\n\t\n"
    assert reader_defects.identity(text, 1.0) == text


def test_identity_ignores_the_strength_argument_entirely():
    scene = "The gate stood open."
    for strength in (-1.0, 0.0, 1.0, 100.0):
        assert reader_defects.identity(scene, strength) == scene


# ------------------------------------------------------------- verdict: registered ladder


def test_a_win_rate_of_exactly_0_40_classifies_detects():
    result = reader_defects.verdict(rates(**{MATCHED: 0.40}), bias())
    assert result["per_arm"][MATCHED] == "DETECTS"


def test_a_win_rate_just_above_0_40_classifies_blind():
    result = reader_defects.verdict(rates(**{MATCHED: 0.41}), bias())
    assert result["per_arm"][MATCHED] == "BLIND"


def test_a_win_rate_of_exactly_0_60_classifies_prefers():
    result = reader_defects.verdict(rates(**{STATS: 0.60}), bias())
    assert result["per_arm"][STATS] == "PREFERS"


def test_a_win_rate_just_below_0_60_classifies_blind():
    result = reader_defects.verdict(rates(**{STATS: 0.59}), bias())
    assert result["per_arm"][STATS] == "BLIND"


def test_a_chose_A_rate_of_exactly_0_60_stays_in_the_bias_band():
    # Both band endpoints are inclusive, so 0.60 biases the arm rather than voiding it.
    result = reader_defects.verdict(rates(**{MATCHED: 0.30}), bias(**{MATCHED: 0.60}))
    assert result["per_arm"][MATCHED] == "DETECTS"


def test_a_chose_A_rate_just_above_0_60_voids_the_arm_regardless_of_its_win_rate():
    result = reader_defects.verdict(rates(**{MATCHED: 0.30}), bias(**{MATCHED: 0.61}))
    assert result["per_arm"][MATCHED] == "VOID"


def test_a_chose_A_rate_just_below_0_40_voids_the_arm_regardless_of_its_win_rate():
    result = reader_defects.verdict(rates(**{MATCHED: 0.30}), bias(**{MATCHED: 0.39}))
    assert result["per_arm"][MATCHED] == "VOID"


def test_a_non_float_chose_A_rate_voids_the_arm():
    partial_bias = {
        MATCHED: {"chose_A_rate": 1},
        CONFOUNDED: {"chose_A_rate": 0.5},
        STATS: {"chose_A_rate": 0.5},
    }
    result = reader_defects.verdict(rates(), partial_bias)
    assert result["per_arm"][MATCHED] == "VOID"


def test_an_arm_with_no_bias_entry_voids_while_the_others_classify():
    partial = {CONFOUNDED: {"chose_A_rate": 0.5}, STATS: {"chose_A_rate": 0.5}}
    result = reader_defects.verdict(rates(), partial)
    assert result["per_arm"][MATCHED] == "VOID"
    assert result["per_arm"][CONFOUNDED] == "BLIND"
    assert result["per_arm"][STATS] == "BLIND"


def test_an_arm_missing_from_the_rates_is_absent_while_the_others_classify():
    present = rates()
    del present[STATS]
    result = reader_defects.verdict(present, bias())
    assert result["per_arm"][STATS] == "ABSENT"
    assert result["per_arm"][MATCHED] == "BLIND"
    assert result["per_arm"][CONFOUNDED] == "BLIND"


# ------------------------------------------------------------------ verdict: strict ladder


def test_a_detects_with_an_interval_wholly_below_0_50_stays_detects_in_the_strict_ladder():
    intervals = {MATCHED: {"low": 0.1667, "high": 0.4444}}
    result = reader_defects.verdict(rates(**{MATCHED: 0.30}), bias(), intervals)
    assert result["per_arm"][MATCHED] == "DETECTS"
    assert result["per_arm_strict"][MATCHED] == "DETECTS"


def test_a_detects_whose_interval_contains_0_50_is_undecided_in_the_strict_ladder():
    # §81's actual shape: the threshold cleared by a hundredth over an interval spanning the null.
    intervals = {MATCHED: {"low": 0.1667, "high": 0.6667}}
    result = reader_defects.verdict(rates(**{MATCHED: 0.3889}), bias(), intervals)
    assert result["per_arm"][MATCHED] == "DETECTS"
    assert result["per_arm_strict"][MATCHED] == "UNDECIDED"


def test_a_prefers_with_an_interval_wholly_above_0_50_stays_prefers_in_the_strict_ladder():
    intervals = {STATS: {"low": 0.55, "high": 0.85}}
    result = reader_defects.verdict(rates(**{STATS: 0.70}), bias(), intervals)
    assert result["per_arm"][STATS] == "PREFERS"
    assert result["per_arm_strict"][STATS] == "PREFERS"


def test_an_interval_touching_0_50_at_its_low_end_does_not_clear_the_strict_rule():
    intervals = {MATCHED: {"low": 0.50, "high": 0.70}}
    result = reader_defects.verdict(rates(**{MATCHED: 0.30}), bias(), intervals)
    assert result["per_arm_strict"][MATCHED] == "UNDECIDED"


def test_missing_intervals_make_threshold_clearing_arms_undecided_in_the_strict_ladder():
    result = reader_defects.verdict(rates(**{MATCHED: 0.30, STATS: 0.70}), bias())
    assert result["per_arm_strict"][MATCHED] == "UNDECIDED"
    assert result["per_arm_strict"][STATS] == "UNDECIDED"


def test_a_blind_arm_stays_blind_in_the_strict_ladder_whatever_its_interval():
    intervals = {CONFOUNDED: {"low": 0.48, "high": 0.52}}
    result = reader_defects.verdict(rates(), bias(), intervals)
    assert result["per_arm"][CONFOUNDED] == "BLIND"
    assert result["per_arm_strict"][CONFOUNDED] == "BLIND"


# ------------------------------------------------------------ verdict: roll-ups and notes


def test_a_blind_interiority_arm_and_a_detecting_stat_arm_split_the_roll_up_lists():
    result = reader_defects.verdict(rates(**{STATS: 0.30}), bias())
    assert result["interiority"] == "BLIND"
    assert result["stats"] == "DETECTS"
    assert result["mapped_holes"] == ["interiority"]
    assert result["optimisable_axes"] == ["stat_flatten"]
    # Without intervals even a detecting arm cannot stand on the strict ladder.
    assert result["optimisable_axes_strict"] == []


def test_the_strict_optimisable_axes_drop_arms_whose_interval_contains_0_50():
    intervals = {
        MATCHED: {"low": 0.20, "high": 0.40},
        STATS: {"low": 0.10, "high": 0.90},
    }
    result = reader_defects.verdict(rates(**{MATCHED: 0.30, STATS: 0.30}), bias(), intervals)
    assert result["optimisable_axes"] == ["interiority", "stat_flatten"]
    assert result["optimisable_axes_strict"] == ["interiority"]


def test_the_confound_note_names_both_interiority_rates_and_their_gap():
    result = reader_defects.verdict(rates(**{MATCHED: 0.30, CONFOUNDED: 0.50}), bias())
    note = result["confound_note"]
    assert isinstance(note, str)
    assert "0.3" in note
    assert "0.5" in note
    assert "0.2000" in note


def test_the_confound_note_is_none_when_the_confounded_arm_is_missing_from_the_rates():
    present = rates()
    del present[CONFOUNDED]
    result = reader_defects.verdict(present, bias())
    assert result["confound_note"] is None


def test_empty_rates_and_empty_bias_classify_every_arm_absent_without_crashing():
    result = reader_defects.verdict({}, {}, None)
    assert set(result["per_arm"].values()) == {"ABSENT"}
    assert set(result["per_arm_strict"].values()) == {"ABSENT"}
    assert result["interiority"] == "ABSENT"
    assert result["stats"] == "ABSENT"
    assert result["mapped_holes"] == []
    assert result["optimisable_axes"] == []
    assert result["optimisable_axes_strict"] == []
    assert result["confound_note"] is None

