"""Hand-derived checks on the pure arithmetic of summary_reliability.

These tests pin the behaviour every reliability read passes through: name and token
normalisation out of prose or subject lists; the Jaccard convention that two empty sets score
full agreement while one empty set scores none; feature extraction treating missing fields as
absences rather than default zeros; within-versus-between separation over pooled pairs; the
ICC(1) classification ladder (empty grid / constant field / measured, with the perfect and
noise-saturated ends of the scale); level-2 retention including the loose any-word match; and
the structure, cast discipline, and determinism of the dry-run synthetic summary. Every
expected value is stated by hand from each function's docstring and code before it is checked,
including hand-worked ICC mean squares, not recorded from a run.

What they do not establish: whether the shipped summariser is actually reliable. No model is
called, no transport runs, no database or results file is read, and nothing here sleeps or
spawns a process — so none of these tests can produce a separation, an ICC, or a retention
number for real scenes. The CLI, the cache path, the level-2 window pipeline, and the
validity of the metrics themselves are all out of scope.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

summary_reliability = pytest.importorskip(
    "summary_reliability",
    reason="research module; needs the quality-measurement directory on the path",
)

#: The cast the dry-run stand-in draws its character names from.
_SYNTHETIC_CAST = {"mira", "the courier", "vel", "the toll-keeper", "anneke"}


def _features(characters: str) -> dict:
    """A features row whose only varying input is the characters string."""
    return summary_reliability.features({"characters": characters})


# ---------------------------------------------------------------------------- normalisation


def test_name_set_splits_prose_names_and_strips_noise_words():
    assert summary_reliability._name_set("Mira, the toll-keeper and Vel") == frozenset(
        {"mira", "toll keeper", "vel"}
    )


def test_name_set_also_splits_on_semicolons_and_ampersands():
    assert summary_reliability._name_set("Anneke; Mira & Vel") == frozenset(
        {"mira", "vel", "anneke"}
    )


def test_name_set_collapses_duplicate_names_to_one_member():
    assert summary_reliability._name_set("The Debt and the debt") == frozenset({"debt"})


def test_name_set_reads_subject_keys_out_of_dicts_in_a_list_beside_plain_strings():
    raw = [{"subject": "the river"}, {}, {"subject": "the bank"}, "Mira"]
    assert summary_reliability._name_set(raw) == frozenset({"river", "bank", "mira"})


def test_name_set_drops_an_item_made_only_of_noise_words():
    assert summary_reliability._name_set("his, her, and their") == frozenset()


def test_name_set_returns_empty_for_an_empty_string_a_non_string_and_an_empty_list():
    assert summary_reliability._name_set("") == frozenset()
    assert summary_reliability._name_set(None) == frozenset()
    assert summary_reliability._name_set([]) == frozenset()


def test_token_set_keeps_content_words_longer_than_two_letters():
    assert summary_reliability._token_set("The Debt is owed by her") == frozenset(
        {"debt", "owed"}
    )


def test_token_set_drops_tokens_of_two_letters_or_fewer():
    assert summary_reliability._token_set("to be or not") == frozenset({"not"})


def test_token_set_json_encodes_a_non_string_before_tokenising_it():
    assert summary_reliability._token_set(["ab", "cdef"]) == frozenset({"cdef"})


def test_token_set_returns_empty_for_an_empty_string_and_an_empty_list():
    assert summary_reliability._token_set("") == frozenset()
    assert summary_reliability._token_set([]) == frozenset()


def test_token_set_stays_at_whole_words_where_name_set_joins_adjacent_ones():
    raw = "Mira, the toll-keeper and Vel"
    assert summary_reliability._token_set(raw) == frozenset({"mira", "toll", "keeper", "vel"})
    assert summary_reliability._name_set(raw) == frozenset({"mira", "toll keeper", "vel"})


# ------------------------------------------------------------------------------ jaccard


def test_jaccard_is_intersection_over_union():
    left = frozenset({"a", "b"})
    right = frozenset({"b", "c"})
    assert summary_reliability.jaccard(left, right) == pytest.approx(1 / 3)


def test_jaccard_scores_identical_sets_one_and_disjoint_sets_zero():
    assert summary_reliability.jaccard(frozenset({"a"}), frozenset({"a"})) == 1.0
    assert summary_reliability.jaccard(frozenset({"a"}), frozenset({"b"})) == 0.0


def test_jaccard_scores_two_empty_sets_as_agreement_but_one_empty_as_none():
    assert summary_reliability.jaccard(frozenset(), frozenset()) == 1.0
    assert summary_reliability.jaccard(frozenset({"a"}), frozenset()) == 0.0


# ------------------------------------------------------------------------------- features


def test_features_counts_scalars_and_builds_sets_from_a_full_summary():
    result = summary_reliability.features(
        {
            "setting": "a dark room",
            "characters": "Mira and Vel",
            "delta": {"who": "Mira", "what_changed": "trust"},
            "promises_opened": [{"subject": "the debt"}, "an older debt"],
            "promises_paid": [],
        }
    )
    assert result["delta_present"] == 1.0
    assert result["n_promises_opened"] == 2.0
    assert result["n_promises_paid"] == 0.0
    assert result["n_characters"] == 2.0
    # Prose joins only setting and characters here: "a dark room Mira and Vel".
    assert result["prose_words"] == 6.0
    assert result["characters"] == frozenset({"mira", "vel"})
    # "an older debt" loses its noise article; the dict entry keeps only its subject.
    assert result["promises_opened"] == frozenset({"debt", "older debt"})
    assert result["promises_paid"] == frozenset()


def test_features_reads_a_delta_with_text_as_present_and_an_unanswered_shape_as_absent():
    answered = summary_reliability.features({"delta": {"who": "Mira", "what_changed": "trust"}})
    unanswered = summary_reliability.features({"delta": {"who": "Mira", "what_changed": ""}})
    assert answered["delta_present"] == 1.0
    assert unanswered["delta_present"] == 0.0


def test_features_treats_every_missing_field_as_an_absence_without_crashing():
    result = summary_reliability.features({})
    assert result["delta_present"] == 0.0
    assert result["n_promises_opened"] == 0.0
    assert result["n_characters"] == 0.0
    assert result["prose_words"] == 0.0
    assert result["characters"] == frozenset()
    assert result["promises_opened"] == frozenset()


def test_features_counts_a_null_promise_list_as_zero_openings_not_a_crash():
    result = summary_reliability.features({"promises_opened": None})
    assert result["n_promises_opened"] == 0.0
    assert result["promises_opened"] == frozenset()


# ----------------------------------------------------------------------------- separation


def test_separation_hits_the_ceiling_when_replicates_agree_and_units_share_nothing():
    grid = {
        "a": [_features("Mira"), _features("Mira")],
        "b": [_features("Vel"), _features("Vel")],
    }
    report = summary_reliability.separation(grid, "characters")
    assert report["within"] == 1.0
    assert report["between"] == 0.0
    assert report["separation"] == 1.0
    assert report["within_pairs"] == 2
    assert report["between_pairs"] == 4


def test_separation_is_zero_when_the_field_is_identical_inside_and_across_units():
    grid = {
        "a": [_features("Mira"), _features("Mira")],
        "b": [_features("Mira"), _features("Mira")],
    }
    report = summary_reliability.separation(grid, "characters")
    assert report["within"] == 1.0
    assert report["between"] == 1.0
    assert report["separation"] == 0.0


def test_separation_goes_negative_when_within_disagreement_mirrors_between_disagreement():
    grid = {
        "a": [_features("Mira"), _features("Vel")],
        "b": [_features("Mira"), _features("Vel")],
    }
    report = summary_reliability.separation(grid, "characters")
    assert report["within"] == 0.0
    assert report["between"] == 0.5
    assert report["separation"] == -0.5


def test_separation_reports_a_partially_shared_unit_as_a_fractional_positive_gap():
    grid = {
        "a": [_features("Mira"), _features("Mira and Vel")],
        "b": [_features("Vel"), _features("Anneke")],
    }
    report = summary_reliability.separation(grid, "characters")
    assert report["within"] == 0.25
    assert report["between"] == 0.125
    assert report["separation"] == 0.125


def test_separation_returns_nan_within_for_single_record_units_but_still_scores_between():
    grid = {"a": [_features("Mira")], "b": [_features("Vel")]}
    report = summary_reliability.separation(grid, "characters")
    assert math.isnan(report["within"])
    assert report["within_pairs"] == 0
    assert report["between"] == 0.0


def test_separation_survives_an_empty_grid_with_nan_and_zero_pair_counts():
    report = summary_reliability.separation({}, "characters")
    assert math.isnan(report["within"])
    assert math.isnan(report["between"])
    assert math.isnan(report["separation"])
    assert report["within_pairs"] == 0
    assert report["between_pairs"] == 0


# ------------------------------------------------------------------------- numeric_report


def test_numeric_report_labels_an_empty_grid():
    assert summary_reliability.numeric_report({}, "x") == {"status": "empty"}


def test_numeric_report_labels_a_field_that_never_varies_as_constant():
    grid = {"a": [{"x": 2.0}, {"x": 2.0}], "b": [{"x": 2.0}]}
    report = summary_reliability.numeric_report(grid, "x")
    assert report["status"] == "constant"
    assert report["value"] == 2.0
    assert report["n"] == 3


def test_numeric_report_scores_purely_between_unit_variance_as_icc_of_exactly_one():
    # ms_between = 2 * ((0-5)^2 + (10-5)^2) / 1 = 100, ms_within = 0, so ICC = 100/100.
    grid = {"a": [{"x": 0.0}, {"x": 0.0}], "b": [{"x": 10.0}, {"x": 10.0}]}
    report = summary_reliability.numeric_report(grid, "x")
    assert report["status"] == "measured"
    assert float(report["icc1"]) == 1.0
    assert float(report["ms_within"]) == 0.0
    assert report["mean"] == 5.0
    assert report["sd"] == 5.0


def test_numeric_report_scores_within_noise_equal_to_between_spread_as_icc_of_minus_one():
    # Identical spreads inside each unit: ms_between = 0, ms_within = 50, so ICC = -50/50.
    grid = {"a": [{"x": 0.0}, {"x": 10.0}], "b": [{"x": 0.0}, {"x": 10.0}]}
    report = summary_reliability.numeric_report(grid, "x")
    assert report["status"] == "measured"
    assert float(report["icc1"]) == -1.0


def test_numeric_report_reports_a_nan_icc_without_crashing_when_no_group_has_two_replicates():
    grid = {"a": [{"x": 1.0}], "b": [{"x": 3.0}]}
    report = summary_reliability.numeric_report(grid, "x")
    assert report["status"] == "measured"
    assert math.isnan(float(report["icc1"]))
    assert report["groups"] == 0


# ------------------------------------------------------------------------------- retention


def test_retention_is_full_when_the_upper_summary_carries_the_window_subject_exactly():
    parts = [summary_reliability.features({"promises_opened": [{"subject": "the debt"}]})]
    whole = summary_reliability.features({"promises_opened": [{"subject": "the debt"}]})
    assert summary_reliability.retention(parts, whole) == 1.0


def test_retention_counts_a_multi_word_subject_carried_by_any_single_word():
    parts = [summary_reliability.features({"promises_opened": [{"subject": "old mill debt"}]})]
    whole = summary_reliability.features({"characters": "mill"})
    assert summary_reliability.retention(parts, whole) == 1.0


def test_retention_is_half_when_only_one_of_two_window_subjects_survives_upward():
    parts = [
        summary_reliability.features(
            {"promises_opened": [{"subject": "the debt"}, {"subject": "the courier"}]}
        )
    ]
    whole = summary_reliability.features({"characters": "the courier arrives"})
    assert summary_reliability.retention(parts, whole) == 0.5


def test_retention_is_zero_when_no_window_subject_appears_above_it():
    parts = [summary_reliability.features({"promises_opened": [{"subject": "the vault"}]})]
    whole = summary_reliability.features({"characters": "nothing here"})
    assert summary_reliability.retention(parts, whole) == 0.0


def test_retention_is_nan_when_the_windows_opened_no_promises_at_all():
    whole = summary_reliability.features({"characters": "anyone"})
    assert math.isnan(summary_reliability.retention([], whole))
    assert math.isnan(summary_reliability.retention([summary_reliability.features({})], whole))


# -------------------------------------------------------------------------------- overlaps


def test_overlaps_matches_when_a_subject_word_equals_a_whole_carried_entry():
    assert summary_reliability._overlaps("old mill debt", {"mill"}) is True


def test_overlaps_does_not_split_carried_entries_into_words():
    assert summary_reliability._overlaps("north gate", {"gate house"}) is False


def test_overlaps_requires_an_exact_word_so_near_matches_do_not_count():
    assert summary_reliability._overlaps("debts", {"debt"}) is False
    assert summary_reliability._overlaps("old mill", {"new gate"}) is False


# ----------------------------------------------------------------------- synthetic summary


def test_synthetic_summary_decodes_to_the_schema_shape_with_fixed_prose_fields():
    decoded = json.loads(summary_reliability._synthetic_summary("key"))
    assert set(decoded) == {
        "setting",
        "characters",
        "events",
        "open",
        "delta",
        "promises_opened",
        "promises_paid",
    }
    assert decoded["setting"] == "a room, after dark"
    assert decoded["events"] == "words were exchanged and one of them left"
    assert decoded["open"] == "what the other one meant by it"


def test_synthetic_summary_draws_characters_only_from_the_cast_sorted_and_unique():
    for key in ("key-a", "key-b", "key-c"):
        decoded = json.loads(summary_reliability._synthetic_summary(key))
        who = decoded["characters"].split(", ")
        assert who
        assert len(set(who)) == len(who)
        assert who == sorted(who)
        assert set(who) <= _SYNTHETIC_CAST


def test_synthetic_summary_opens_exactly_one_thread_numbered_below_seven():
    decoded = json.loads(summary_reliability._synthetic_summary("key"))
    (opened,) = decoded["promises_opened"]
    subject = opened["subject"]
    assert subject.startswith("thread-")
    assert int(subject.removeprefix("thread-")) < 7


def test_synthetic_summary_leaves_promises_paid_either_empty_or_a_single_thread():
    decoded = json.loads(summary_reliability._synthetic_summary("key"))
    paid = decoded["promises_paid"]
    if not paid:
        return
    (subject,) = paid
    assert subject.startswith("thread-")
    assert int(subject.removeprefix("thread-")) < 7


def test_synthetic_summary_attributes_any_present_delta_to_its_first_named_character():
    seen_absent = False
    seen_present = False
    for index in range(24):
        decoded = json.loads(summary_reliability._synthetic_summary(f"k{index}"))
        first_character = decoded["characters"].split(", ")[0]
        delta = decoded["delta"]
        if delta is None:
            seen_absent = True
            continue
        assert delta["what_changed"] == "standing"
        assert delta["from"] == "held"
        assert delta["to"] == "spent"
        assert delta["who"] == first_character
        seen_present = True
    assert seen_absent
    assert seen_present


def test_synthetic_summary_is_identical_when_called_twice_with_the_same_key():
    assert (
        summary_reliability._synthetic_summary("same-key")
        == summary_reliability._synthetic_summary("same-key")
    )


# -------------------------------------------------------------------------------- selftest


def test_module_selftest_passes_without_a_transport():
    assert summary_reliability.selftest() is None



