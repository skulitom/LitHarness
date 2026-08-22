"""Hand-computed pins on the pure arithmetic of research/quality-measurement/persona_battery.py.

Every expected value here is worked out on paper from the function's own code before the test
runs: sums of squares for toy 2x2 grids, rank algebra for three-point series, a lexicon-scored
sentence counted by hand, and bootstrap intervals collapsed by feeding every cell the same rate
so no resample can move them. Together they pin that the kill-condition statistics report the
stipulated number for panels whose behaviour is stipulated.

They do not establish anything about the gates themselves. Nothing here calls a model, reads a
database, corpus or results file, spawns a process, or decides whether a real panel is
reliable — a passing run means the arithmetic is the arithmetic the protocol names, nothing more.
"""

from __future__ import annotations

import math

import pytest

persona_battery = pytest.importorskip(
    "persona_battery",
    reason="research module; needs the quality-measurement directory on the path",
)
elicit = pytest.importorskip(
    "elicit",
    reason="research module; supplies the Comparison and Sample records",
)


def _sample(model: str, *, reason_code: str | None = None, refused: bool = False) -> elicit.Sample:
    return elicit.Sample(
        passage_id="p1",
        persona_id="a",
        sample=0,
        model=model,
        stage1="",
        verdict=None,
        reason_code=reason_code,
        refused=refused,
        request_digest="d",
    )


def _comparison(
    pair_id: str,
    persona_id: str,
    *,
    model: str = "m1",
    orientation: int = 0,
    choice: str | None = "B",
    refused: bool = False,
) -> elicit.Comparison:
    return elicit.Comparison(
        pair_id=pair_id,
        persona_id=persona_id,
        sample=0,
        model=model,
        orientation=orientation,
        choice=None if refused else choice,
        reason_code=None,
        refused=refused,
    )


# --------------------------------------------------------------------- variance_split


def test_variance_split_reads_a_persona_driven_panel_above_the_caricature_boundary():
    # grand 0.5; passage means 0.3/0.7 -> passage_ss 2(.04)+2(.04)=0.16;
    # persona means 0.2/0.8 -> persona_ss 2(.09)+2(.09)=0.36; ratio 0.36/0.16 = 2.25.
    cells = {("p1", "a"): 0.0, ("p1", "b"): 0.6, ("p2", "a"): 0.4, ("p2", "b"): 1.0}
    split = persona_battery.variance_split(cells)
    assert split["persona_ss"] == 0.36
    assert split["passage_ss"] == 0.16
    assert split["ratio"] == 2.25


def test_variance_split_reads_a_passage_driven_panel_below_the_caricature_boundary():
    # Same grid transposed: passage_ss 0.36, persona_ss 0.16, ratio 0.4444.
    cells = {("p1", "a"): 0.0, ("p1", "b"): 0.4, ("p2", "a"): 0.6, ("p2", "b"): 1.0}
    split = persona_battery.variance_split(cells)
    assert split["persona_ss"] == 0.16
    assert split["passage_ss"] == 0.36
    assert split["ratio"] == 0.4444


def test_variance_split_scores_a_panel_that_varies_only_by_passage_at_zero_ratio():
    cells = {("p1", "a"): 0.0, ("p1", "b"): 0.0, ("p2", "a"): 1.0, ("p2", "b"): 1.0}
    split = persona_battery.variance_split(cells)
    assert split["persona_ss"] == 0.0
    assert split["passage_ss"] == 1.0
    assert split["ratio"] == 0.0


def test_variance_split_returns_an_infinite_ratio_when_only_the_persona_term_varies():
    cells = {("p1", "a"): 0.0, ("p1", "b"): 1.0, ("p2", "a"): 0.0, ("p2", "b"): 1.0}
    split = persona_battery.variance_split(cells)
    assert split["persona_ss"] == 1.0
    assert split["passage_ss"] == 0.0
    assert math.isinf(split["ratio"])


def test_variance_split_reports_nan_for_an_empty_grid():
    split = persona_battery.variance_split({})
    assert split["persona_ss"] == 0.0
    assert split["passage_ss"] == 0.0
    assert math.isnan(split["ratio"])


# ------------------------------------------------------------------- inter_persona_rho


def _grid(
    values_a: list[float], values_b: list[float] | None = None
) -> dict[tuple[str, str], float]:
    values_b = values_a if values_b is None else values_b
    cells: dict[tuple[str, str], float] = {}
    for index, value in enumerate(values_a):
        cells[(f"p{index}", "a")] = value
    for index, value in enumerate(values_b):
        cells[(f"p{index}", "b")] = value
    return cells


def test_inter_persona_rho_scores_two_identical_persona_rankings_at_one():
    rho = persona_battery.inter_persona_rho(_grid([0.0, 1.0, 0.0]))
    assert rho["mean_rho"] == 1.0
    assert rho["undefined_pairs"] == 0
    assert rho["pairs"] == [{"a": "a", "b": "b", "rho": 1.0}]


def test_inter_persona_rho_scores_opposite_persona_rankings_at_minus_one():
    rho = persona_battery.inter_persona_rho(_grid([0.0, 1.0, 0.0], [1.0, 0.0, 1.0]))
    assert rho["mean_rho"] == -1.0
    assert rho["undefined_pairs"] == 0
    assert rho["pairs"] == [{"a": "a", "b": "b", "rho": -1.0}]


def test_inter_persona_rho_marks_a_constant_persona_pair_undefined_and_leaves_the_mean_nan():
    rho = persona_battery.inter_persona_rho(_grid([0.5, 0.5, 0.5], [0.0, 1.0, 0.0]))
    assert rho["undefined_pairs"] == 1
    assert rho["pairs"][0]["rho"] is None
    assert math.isnan(rho["mean_rho"])
    # The null is simulated at this run's own dimensions even when the observation is undefined.
    assert rho["null_replicates"] > 0
    assert not math.isnan(float(rho["null_p95"]))


def test_inter_persona_rho_excludes_a_persona_with_missing_cells_from_the_pairs():
    cells = _grid([0.0, 1.0, 0.0])
    del cells[("p2", "b")]  # persona b never scored p2, so its column is incomplete
    rho = persona_battery.inter_persona_rho(cells)
    assert rho["pairs"] == []
    assert rho["undefined_pairs"] == 0
    assert math.isnan(rho["mean_rho"])
    assert rho["null_replicates"] > 0


def test_inter_persona_rho_simulates_no_null_for_empty_cells():
    rho = persona_battery.inter_persona_rho({})
    assert math.isnan(rho["mean_rho"])
    assert rho["pairs"] == []
    assert rho["null_replicates"] == 0
    assert math.isnan(rho["null_p95"])


# ------------------------------------------------------------------------------- _split


def test_split_donates_the_unscored_tail_when_there_are_spares():
    units = [("k1", "t1"), ("k2", "t2"), ("k3", "t3"), ("k4", "t4")]
    scored, donors = persona_battery._split(units, 2)
    assert scored == [("k1", "t1"), ("k2", "t2")]
    assert donors == ["t3", "t4"]
    assert not set(donors) & {text for _, text in scored}


def test_split_rotates_the_scored_texts_when_every_unit_is_scored():
    units = [("k1", "t1"), ("k2", "t2")]
    scored, donors = persona_battery._split(units, 5)
    assert scored == units
    assert donors == ["t2", "t1"]
    assert all(
        host_text != donor_text for (_, host_text), donor_text in zip(scored, donors, strict=True)
    )


def test_split_supplies_no_donors_for_a_single_unit():
    scored, donors = persona_battery._split([("k1", "only")], 1)
    assert scored == [("k1", "only")]
    assert donors == []


def test_split_survives_an_empty_unit_list():
    assert persona_battery._split([], 3) == ([], [])


# ----------------------------------------------------------------------- stake_coverage


def test_stake_coverage_counts_one_stake_sentence_of_six_words_in_ten():
    # "die" opens the cost term (+1) and the if/will shape adds the conditional bonus, so the
    # first sentence scores 2 while the second scores 0; 6 of the 10 words are stake-bearing.
    text = "He will die if he stays. The garden was quiet."
    coverage = persona_battery.stake_coverage(text)
    assert coverage["sentences"] == 2
    assert coverage["stake_sentences"] == 1
    assert coverage["stake_sentence_share"] == 0.5
    assert coverage["stake_word_share"] == 0.6


def test_stake_coverage_reports_zero_when_no_sentence_carries_stake_vocabulary():
    coverage = persona_battery.stake_coverage("The garden was quiet. The path was long.")
    assert coverage == {
        "sentences": 2,
        "stake_sentences": 0,
        "stake_sentence_share": 0.0,
        "stake_word_share": 0.0,
    }



# ------------------------------------------------------------------------ annotate_arms


def test_annotate_arms_tags_known_arms_with_their_pre_registered_standing():
    rows = {
        "destake": {"mean_delta": 0.3},
        "deplete_matched": {"mean_delta": 0.2},
        "rename_entities": {"mean_delta": 0.1},
        "filler_inject": {"mean_delta": 0.05},
    }
    tagged = persona_battery.annotate_arms(rows)["arms"]
    assert tagged["destake"]["standing"] == "primary"
    assert tagged["deplete_matched"]["standing"] == "primary-control"
    assert tagged["rename_entities"]["standing"] == "placebo"
    assert tagged["filler_inject"]["standing"] == "exploratory"


def test_annotate_arms_labels_an_unknown_arm_unregistered():
    annotated = persona_battery.annotate_arms({"mystery_arm": {"mean_delta": 0.1}})
    assert annotated["arms"]["mystery_arm"]["standing"] == "unregistered"
    assert annotated["unregistered_arms"] == ["mystery_arm"]


def test_annotate_arms_declares_one_primary_comparison_of_family_size_one():
    annotated = persona_battery.annotate_arms({})
    assert annotated["primary_comparison"] == "destake minus deplete_matched"
    assert annotated["family_size"] == 1


def test_annotate_arms_does_not_mutate_the_rows_it_is_given():
    row = {"mean_delta": 0.3}
    annotated = persona_battery.annotate_arms({"destake": row})
    assert annotated["arms"]["destake"]["standing"] == "primary"
    assert row == {"mean_delta": 0.3}


def test_annotate_arms_survives_an_empty_per_ablation_dict():
    annotated = persona_battery.annotate_arms({})
    assert annotated["arms"] == {}
    assert annotated["unregistered_arms"] == []


# ---------------------------------------------------------------------------- two_way_ci


def test_two_way_ci_collapses_to_one_when_every_cell_wins():
    # Each cell is a (win-sum, trials) pair; a cell that won both its trials is (2.0, 2),
    # so every resample's pooled rate is exactly 1.0.
    cells = {
        ("p1", "a"): (2.0, 2),
        ("p1", "b"): (2.0, 2),
        ("p2", "a"): (2.0, 2),
        ("p2", "b"): (2.0, 2),
    }
    assert persona_battery.two_way_ci(cells) == (1.0, 1.0)


def test_two_way_ci_collapses_to_zero_when_no_cell_wins():
    cells = {
        ("p1", "a"): (0.0, 2),
        ("p1", "b"): (0.0, 2),
        ("p2", "a"): (0.0, 2),
        ("p2", "b"): (0.0, 2),
    }
    assert persona_battery.two_way_ci(cells) == (0.0, 0.0)


def test_two_way_ci_spans_the_full_unit_interval_below_two_passages():
    cells = {("p1", "a"): (1.0, 1), ("p1", "b"): (0.0, 1)}
    assert persona_battery.two_way_ci(cells) == (0.0, 1.0)


def test_two_way_ci_spans_the_full_unit_interval_below_two_personas():
    cells = {("p1", "a"): (1.0, 1), ("p2", "a"): (0.0, 1)}
    assert persona_battery.two_way_ci(cells) == (0.0, 1.0)


def test_two_way_ci_spans_the_full_unit_interval_for_empty_cells():
    assert persona_battery.two_way_ci({}) == (0.0, 1.0)


def test_two_way_ci_stays_within_the_range_of_cell_rates():
    # Every replicate's rate is a weighted average of the per-cell rates 0.25 and 0.75
    # (score-sum over count), so no draw can land outside [0.25, 0.75].
    cells = {
        ("p1", "a"): (1.0, 4),
        ("p1", "b"): (1.0, 4),
        ("p2", "a"): (3.0, 4),
        ("p2", "b"): (3.0, 4),
    }
    low, high = persona_battery.two_way_ci(cells)
    assert 0.25 <= low <= high <= 0.75


# --------------------------------------------------------------------- pairwise_interval


def test_pairwise_interval_collapses_to_one_when_every_decided_choice_prefers_the_variant():
    comparisons = [
        _comparison("p1|destake@0.5", "a", orientation=0, choice="B"),
        _comparison("p2|destake@0.5", "a", orientation=1, choice="A"),
        _comparison("p1|destake@0.5", "b", orientation=1, choice="A"),
        _comparison("p2|destake@0.5", "b", orientation=0, choice="B"),
    ]
    interval = persona_battery.pairwise_interval(comparisons, "m1", "drop")
    assert interval["low"] == 1.0
    assert interval["high"] == 1.0


def test_pairwise_interval_collapses_to_zero_when_every_decided_choice_prefers_the_original():
    comparisons = [
        _comparison("p1|destake@0.5", "a", orientation=0, choice="A"),
        _comparison("p2|destake@0.5", "a", orientation=1, choice="B"),
        _comparison("p1|destake@0.5", "b", orientation=1, choice="B"),
        _comparison("p2|destake@0.5", "b", orientation=0, choice="A"),
    ]
    interval = persona_battery.pairwise_interval(comparisons, "m1", "drop")
    assert interval["low"] == 0.0
    assert interval["high"] == 0.0


def test_pairwise_interval_skips_refused_and_off_model_comparisons():
    comparisons = [
        _comparison("p1|destake@0.5", "a", model="m1"),
        _comparison("p2|destake@0.5", "b", model="other-model"),
        _comparison("p3|destake@0.5", "c", model="m1", refused=True),
    ]
    interval = persona_battery.pairwise_interval(comparisons, "m1", "drop")
    assert interval["passages"] == 1
    assert interval["personas"] == 1


def test_pairwise_interval_drops_a_tie_under_the_drop_policy():
    tie = _comparison("p1|destake@0.5", "a", choice="neither")
    interval = persona_battery.pairwise_interval([tie], "m1", "drop")
    assert interval["passages"] == 0
    assert interval["personas"] == 0
    assert interval["low"] == 0.0
    assert interval["high"] == 1.0


def test_pairwise_interval_counts_a_tied_comparison_when_the_policy_is_not_drop():
    tie = _comparison("p1|destake@0.5", "a", choice="neither")
    interval = persona_battery.pairwise_interval([tie], "m1", "keep")
    assert interval["passages"] == 1
    assert interval["personas"] == 1


def test_pairwise_interval_folds_repeat_comparisons_into_one_cell():
    comparisons = [
        _comparison("p1|destake@0.5", "a"),
        _comparison("p1|destake@0.5", "a"),
        _comparison("p1|destake@0.5", "b"),
        _comparison("p2|destake@0.5", "a"),
        _comparison("p2|destake@0.5", "b"),
    ]
    interval = persona_battery.pairwise_interval(comparisons, "m1", "drop")
    assert interval["passages"] == 2
    assert interval["personas"] == 2


def test_pairwise_interval_reports_no_cells_for_an_empty_list():
    interval = persona_battery.pairwise_interval([], "m1", "drop")
    assert interval["passages"] == 0
    assert interval["personas"] == 0
    assert interval["low"] == 0.0
    assert interval["high"] == 1.0



# --------------------------------------------------------------- filler_reason_signature


def test_filler_reason_signature_reads_padding_as_the_majority_filler_code():
    by_variant = {
        "p1|filler_inject@0.5": [
            _sample("m1", reason_code="padding"),
            _sample("m1", reason_code="padding"),
            _sample("m1", reason_code="flat-voice"),
        ],
        "p1|original@0.0": [_sample("m1", reason_code="voice-drift")],
    }
    signature = persona_battery.filler_reason_signature(by_variant, "m1")
    assert signature["available"] is True
    assert signature["filler_codes"] == {"padding": 2, "flat-voice": 1}
    assert list(signature["filler_codes"]) == ["padding", "flat-voice"]
    assert signature["other_codes"] == {"voice-drift": 1}
    assert signature["filler_samples"] == 3
    assert signature["padding_share"] == 0.6667
    assert signature["flat_voice_share"] == 0.3333


def test_filler_reason_signature_keeps_non_filler_variant_codes_out_of_the_filler_bucket():
    by_variant = {"p1|destake@0.5": [_sample("m1", reason_code="padding")]}
    signature = persona_battery.filler_reason_signature(by_variant, "m1")
    assert signature["available"] is False
    assert signature["filler_codes"] == {}
    assert signature["filler_samples"] == 0
    assert signature["padding_share"] is None
    assert signature["flat_voice_share"] is None
    assert signature["other_codes"] == {"padding": 1}


def test_filler_reason_signature_skips_refused_off_model_and_uncoded_samples():
    by_variant = {
        "p1|filler_inject@0.5": [
            _sample("m1", reason_code="padding", refused=True),
            _sample("other-model", reason_code="padding"),
            _sample("m1", reason_code=None),
            _sample("m1", reason_code="flat-voice"),
        ],
    }
    signature = persona_battery.filler_reason_signature(by_variant, "m1")
    assert signature["filler_codes"] == {"flat-voice": 1}
    assert signature["filler_samples"] == 1
    assert signature["flat_voice_share"] == 1.0


def test_filler_reason_signature_reports_nothing_without_filler_samples():
    signature = persona_battery.filler_reason_signature({}, "m1")
    assert signature["available"] is False
    assert signature["filler_samples"] == 0
    assert signature["padding_share"] is None


# ------------------------------------------------------------------ _destake_comparison


def test_destake_comparison_reports_a_positive_difference_when_destake_moved_further():
    per_ablation = {
        "destake": {"mean_delta": 0.30, "dose_rho": 0.82},
        "deplete_matched": {"mean_delta": 0.12, "dose_rho": 0.41},
    }
    comparison = persona_battery._destake_comparison(per_ablation)
    assert comparison["available"] is True
    assert comparison["mean_delta_difference"] == 0.18
    assert comparison["destake_dose_rho"] == 0.82
    assert comparison["matched_dose_rho"] == 0.41


def test_destake_comparison_reports_zero_difference_when_both_arms_moved_alike():
    per_ablation = {
        "destake": {"mean_delta": 0.25, "dose_rho": 0.5},
        "deplete_matched": {"mean_delta": 0.25, "dose_rho": 0.5},
    }
    comparison = persona_battery._destake_comparison(per_ablation)
    assert comparison["available"] is True
    assert comparison["mean_delta_difference"] == 0.0


def test_destake_comparison_reports_a_negative_difference_when_the_control_moved_further():
    per_ablation = {
        "destake": {"mean_delta": 0.05, "dose_rho": 0.2},
        "deplete_matched": {"mean_delta": 0.20, "dose_rho": 0.7},
    }
    comparison = persona_battery._destake_comparison(per_ablation)
    assert comparison["available"] is True
    assert comparison["mean_delta_difference"] == -0.15


def test_destake_comparison_reports_unavailable_when_an_arm_is_missing():
    comparison = persona_battery._destake_comparison({"destake": {"mean_delta": 0.3}})
    assert comparison["available"] is False
    assert "note" in comparison


def test_destake_comparison_reports_unavailable_for_an_empty_per_ablation():
    comparison = persona_battery._destake_comparison({})
    assert comparison["available"] is False
    assert "note" in comparison


# ------------------------------------------------------------------------------ selftest


def test_the_module_selftest_holds_on_its_stipulated_panels():
    assert persona_battery.selftest() is None


