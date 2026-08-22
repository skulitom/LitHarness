"""Hand-derived pins on the pure arithmetic of `research/quality-measurement/axiom_battery.py`.

These tests establish that the battery's fixture builders and statistics compute what their
derivations say they compute: layout normalisation, the nested damage ladder, the pair census,
the tie/win/edge readings of a comparison cell, ICC(1) and its Spearman-Brown lift, the pair
bootstrap, and the coin-judge null simulators. Every expected value below was computed by hand
from the function's construction before it was ever executed.

They do NOT establish that any real judge satisfies any axiom, that the bars are well chosen,
or that the null simulators have the shape their quantiles claim — the simulators are checked
only for reproducibility under a fixed seed and for their degenerate zero-scene inputs. Nothing
here touches a database, the corpus, the cache, a transport, or a model.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

axiom_battery = pytest.importorskip(
    "axiom_battery",
    reason="research module; needs the quality-measurement directory on the path",
)

#: Six distinct paragraphs under the canonical blank-line convention, so the default four-dose
#: ladder clears its size gate (len(doses) + 2) and every displaced position is observable.
SCENE = "\n\n".join(f"para {index}" for index in range(6))
BLOCKS = [f"para {index}" for index in range(6)]

PARAPHRASE = axiom_battery.PARAPHRASE_QUESTION


def comp(choice: str | None, *, orientation: int = 0, refused: bool = False) -> Any:
    """One comparison whose reading is known by construction."""
    return axiom_battery.Comparison(
        pair_id="pair", persona_id="p", sample=0, model="m", orientation=orientation,
        choice=choice, reason_code="none", refused=refused,
    )


class ScriptedRng:
    """Stands in for `random.Random` so `_coin_rates`' answer is stated, not sampled."""

    def __init__(self, script: list[float]) -> None:
        self._next = iter(script)

    def choice(self, _options: tuple[float, ...]) -> float:
        return next(self._next)


# --------------------------------------------------------------------------- layout_normal


def test_layout_normal_downgrades_blank_line_separators_to_single_newlines():
    # The §78.1 downgrade itself: even canonical blank-line-separated prose comes back joined
    # with bare newlines, which is the edit A1 prices.
    assert axiom_battery.layout_normal("alpha\n\nbeta\n\ngamma") == "alpha\nbeta\ngamma"


def test_layout_normal_collapses_blank_line_runs_to_single_newlines():
    assert axiom_battery.layout_normal("alpha\n\n\n\nbeta") == "alpha\nbeta"
    assert axiom_battery.layout_normal("alpha\n\nbeta\n\n") == "alpha\nbeta"


def test_layout_normal_strips_whitespace_surrounding_each_paragraph():
    assert axiom_battery.layout_normal("  alpha  \n\n\tbeta\n") == "alpha\nbeta"


def test_layout_normal_returns_the_empty_string_for_empty_input():
    assert axiom_battery.layout_normal("") == ""


def test_layout_normal_treats_both_separator_conventions_as_fixed_points():
    # A single paragraph is its own normal form...
    assert axiom_battery.layout_normal("solo") == "solo"
    # ...and so is prose already separated by bare newlines: the downgrade is a no-op there,
    # which is exactly why build_pairs emits no format pair for such a scene.
    assert axiom_battery.layout_normal("alpha\nbeta") == "alpha\nbeta"


# --------------------------------------------------------------------------- _nested_ladder


def test_nested_ladder_rejects_a_scene_below_doses_plus_two_paragraphs():
    five = "\n\n".join(BLOCKS[:5])
    assert axiom_battery._nested_ladder(five, axiom_battery.LADDER_DOSES) is None
    assert axiom_battery._nested_ladder("", axiom_battery.LADDER_DOSES) is None
    assert axiom_battery._nested_ladder("only", axiom_battery.LADDER_DOSES) is None


def test_nested_ladder_accepts_exactly_doses_plus_two_paragraphs():
    six = "\n\n".join(BLOCKS)
    rungs = axiom_battery._nested_ladder(six, axiom_battery.LADDER_DOSES)
    assert rungs is not None
    assert [rung["displaced"] for rung in rungs] == [0, 2, 3, 6]
    assert [rung["dose"] for rung in rungs] == list(axiom_battery.LADDER_DOSES)


def test_nested_ladder_displaces_strictly_more_positions_at_each_higher_dose():
    rungs = axiom_battery._nested_ladder(SCENE, axiom_battery.LADDER_DOSES)
    assert rungs is not None
    moved: list[set[int]] = []
    for rung in rungs:
        rendered = rung["text"].split("\n")
        assert len(rendered) == len(BLOCKS)
        moved.append({i for i, (before, after) in enumerate(zip(BLOCKS, rendered,
                                                                 strict=True))
                      if before != after})
    assert [len(group) for group in moved] == [0, 2, 3, 6]
    assert moved[0] < moved[1] < moved[2] < moved[3]
    assert moved[-1] == set(range(len(BLOCKS)))


def test_nested_ladder_keeps_every_rung_on_the_base_word_multiset_and_block_count():
    rungs = axiom_battery._nested_ladder(SCENE, axiom_battery.LADDER_DOSES)
    assert rungs is not None
    base_words = sorted(SCENE.split())
    for rung in rungs:
        assert sorted(rung["text"].split()) == base_words
        assert rung["blocks"] == len(BLOCKS)
        assert rung["words_match_base"] is True
        assert rung["blocks_match_base"] is True


def test_nested_ladder_leaves_the_zero_dose_rung_at_the_layout_normalised_original():
    rungs = axiom_battery._nested_ladder(SCENE, axiom_battery.LADDER_DOSES)
    assert rungs is not None
    assert rungs[0]["text"] == axiom_battery.layout_normal(SCENE)
    assert all(rungs[k]["text"] != rungs[0]["text"] for k in range(1, len(rungs)))


def test_nested_ladder_rejects_doses_whose_displacement_counts_collapse():
    # Five paragraphs at doses (0.0, 0.25, 0.50): the counts come out [0, max(2, round(1.25)),
    # max(2, round(2.5))] = [0, 2, 2] — the two damaged rungs displace the same amount, so no
    # strictly increasing ladder exists and the scene must be dropped before it costs a call.
    five = "\n\n".join(BLOCKS[:5])
    assert axiom_battery._nested_ladder(five, (0.0, 0.25, 0.50)) is None


# --------------------------------------------------------------------------- build_pairs

FULL = "full"


def usable_scene(samples: int) -> tuple[list[Any], list[dict[str, Any]]]:
    return axiom_battery.build_pairs([(FULL, SCENE)], samples=samples,
                                     doses=(0.0, 0.5, 1.0))


def test_build_pairs_emits_identity_format_three_ladder_pairs_and_paraphrase_for_a_scene():
    pairs, _ = usable_scene(samples=3)
    assert [(pair.pair_id, pair.arm) for pair in pairs] == [
        (f"{FULL}|A0", "A0_indifference"),
        (f"{FULL}|A1", "A1_format_invariance"),
        (f"{FULL}|L01", "A2_A3_ladder"),
        (f"{FULL}|L02", "A2_A3_ladder"),
        (f"{FULL}|L12", "A2_A3_ladder"),
        (f"{FULL}|P02", "A4_paraphrase"),
    ]
    assert [(pair.left_dose, pair.right_dose) for pair in pairs] == [
        (0.0, 0.0), (0.0, 0.0), (0.0, 0.5), (0.0, 1.0), (0.5, 1.0), (0.0, 1.0),
    ]


def test_build_pairs_puts_the_identity_arm_first_and_the_paraphrase_arm_last():
    pairs, _ = usable_scene(samples=3)
    identity = pairs[0]
    assert identity.arm == "A0_indifference"
    assert identity.left == identity.right == SCENE
    paraphrase = pairs[-1]
    assert paraphrase.question == PARAPHRASE
    assert all(pair.question == "preference" for pair in pairs[:-1])


def test_build_pairs_sets_the_format_pair_right_side_to_the_downgraded_layout():
    pairs, _ = usable_scene(samples=3)
    fmt = next(pair for pair in pairs if pair.pair_id == f"{FULL}|A1")
    assert fmt.left == SCENE
    assert fmt.right == axiom_battery.layout_normal(SCENE)
    assert fmt.right == "\n".join(BLOCKS)


def test_build_pairs_resamples_only_pairs_against_the_undamaged_base_rung():
    pairs, _ = usable_scene(samples=3)
    samples_by_id = {pair.pair_id: pair.samples for pair in pairs}
    assert samples_by_id[f"{FULL}|L01"] == 3
    assert samples_by_id[f"{FULL}|L02"] == 3
    assert samples_by_id[f"{FULL}|L12"] == 1
    assert samples_by_id[f"{FULL}|P02"] == 1


def test_build_pairs_certificate_records_rungs_without_their_texts():
    _, certificate = usable_scene(samples=3)
    assert len(certificate) == 1
    entry = certificate[0]
    assert entry["scene"] == FULL
    assert entry["usable"] is True
    assert entry["layout_changed"] is True
    assert [rung["displaced"] for rung in entry["rungs"]] == [0, 3, 6]
    assert all(set(rung) == {"dose", "displaced", "blocks", "words_match_base",
                             "blocks_match_base"} for rung in entry["rungs"])
    assert all("text" not in rung for rung in entry["rungs"])


def test_build_pairs_marks_an_unusable_scene_unusable_and_emits_no_pairs_for_it():
    pairs, certificate = axiom_battery.build_pairs(
        [("thin", "one\n\ntwo"), (FULL, SCENE)], samples=1, doses=(0.0, 0.5, 1.0),
    )
    assert certificate[0]["scene"] == "thin"
    assert certificate[0]["usable"] is False
    assert certificate[0]["why"]
    assert certificate[1]["usable"] is True
    assert pairs and all(pair.scene == FULL for pair in pairs)


def test_build_pairs_skips_the_format_pair_when_layout_normalisation_is_a_no_op():
    # Bare-newline prose normalises to itself, so an A1 pair would be a second identity
    # comparison; the census must leave it out and record that layout did not change.
    flat = "\n".join(BLOCKS[:5])  # five paragraphs: still above the ladder size gate
    pairs, certificate = axiom_battery.build_pairs(
        [("flat", flat)], samples=1, doses=(0.0, 0.5, 1.0),
    )
    assert all(pair.arm != "A1_format_invariance" for pair in pairs)
    assert len(pairs) == 5
    assert certificate[0]["layout_changed"] is False
    assert certificate[0]["usable"] is True


def test_build_pairs_returns_two_empty_lists_for_no_scenes():
    assert axiom_battery.build_pairs([], samples=3) == ([], [])


# --------------------------------------------------------------------------- tie_rate


def test_tie_rate_is_the_scored_share_of_neither_choices():
    cell = [comp("A"), comp("neither"), comp("neither"), comp("B")]
    assert axiom_battery.tie_rate(cell) == pytest.approx(0.5)


def test_tie_rate_excludes_refused_comparisons_from_both_terms():
    cell = [comp("A", refused=True), comp("neither")]
    assert axiom_battery.tie_rate(cell) == pytest.approx(1.0)


def test_tie_rate_reads_zero_when_no_scored_comparison_ties():
    assert axiom_battery.tie_rate([comp("A"), comp("B")]) == pytest.approx(0.0)


def test_tie_rate_reports_nan_when_nothing_was_scored():
    assert math.isnan(axiom_battery.tie_rate([]))
    assert math.isnan(axiom_battery.tie_rate([comp(None)]))
    assert math.isnan(axiom_battery.tie_rate([comp("A", refused=True)]))


# --------------------------------------------------------------------------- right_win_rate


def test_right_win_rate_weights_a_tie_at_half_a_right_win():
    # Two right wins, one tie, one left loss: (1 + 1 + 0.5 + 0) / 4.
    cell = [comp("B"), comp("B"), comp("neither"), comp("A")]
    assert axiom_battery.right_win_rate(cell) == pytest.approx(0.625)


def test_right_win_rate_reads_the_variant_side_through_the_orientation_swap():
    # At orientation 1 the variant sat in slot A, so choosing A is a right win and choosing
    # B a right loss — the same physical slot reads oppositely across orientations.
    assert axiom_battery.right_win_rate([comp("A", orientation=1)]) == pytest.approx(1.0)
    assert axiom_battery.right_win_rate([comp("B", orientation=1)]) == pytest.approx(0.0)


def test_right_win_rate_reads_pure_slot_preference_as_indifference_across_orientations():
    # A judge that always picks slot A wins the variant half the time once orientations are
    # swapped: (0 + 1) / 2. The statistic cannot see this bias on its own.
    cell = [comp("A", orientation=0), comp("A", orientation=1)]
    assert axiom_battery.right_win_rate(cell) == pytest.approx(0.5)


def test_right_win_rate_reports_nan_rather_than_indifference_when_nothing_was_scored():
    assert math.isnan(axiom_battery.right_win_rate([]))
    assert math.isnan(axiom_battery.right_win_rate([comp("B", refused=True)]))


# --------------------------------------------------------------------------- _edge


def test_edge_signs_the_cell_by_whether_the_rate_clears_one_half():
    for_right = [comp("B"), comp("B"), comp("A")]
    against = [comp("A"), comp("A"), comp("B")]
    assert axiom_battery._edge(for_right) == 1
    assert axiom_battery._edge(against) == -1


def test_edge_returns_none_for_a_cell_balanced_exactly_at_one_half():
    assert axiom_battery._edge([comp("B"), comp("A")]) is None


def test_edge_returns_none_for_tied_empty_and_refused_only_cells():
    assert axiom_battery._edge([comp("neither"), comp("neither")]) is None
    assert axiom_battery._edge([]) is None
    assert axiom_battery._edge([comp("B", refused=True)]) is None


# --------------------------------------------------------------------------- cycles_in


def test_cycles_in_scores_a_transitive_triangle_as_determined_and_acyclic():
    # Every edge favours the higher-indexed rung: 0 < 1 < 2.
    upward = {(0, 1): 1, (0, 2): 1, (1, 2): 1}
    assert axiom_battery.cycles_in(upward, 3) == (0, 1)
    # Rung 0 dominates both others: still one determined, acyclic triangle.
    dominant = {(0, 1): -1, (0, 2): -1, (1, 2): -1}
    assert axiom_battery.cycles_in(dominant, 3) == (0, 1)


def test_cycles_in_counts_either_orientation_of_a_three_cycle_as_cyclic():
    one_way = {(0, 1): -1, (0, 2): 1, (1, 2): -1}  # 0 beats 1 beats 2 beats 0
    other_way = {(0, 1): 1, (0, 2): -1, (1, 2): 1}  # the same cycle reversed
    assert axiom_battery.cycles_in(one_way, 3) == (1, 1)
    assert axiom_battery.cycles_in(other_way, 3) == (1, 1)


def test_cycles_in_scores_all_four_triangles_of_a_transitive_four_node_tournament():
    upward = {(low, high): 1 for low in range(4) for high in range(low + 1, 4)}
    assert axiom_battery.cycles_in(upward, 4) == (0, 4)


def test_cycles_in_skips_triangles_containing_an_undetermined_edge():
    tournament = {(low, high): 1 for low in range(4) for high in range(low + 1, 4)}
    tournament[(0, 1)] = None  # exactly the two triangles through (0, 1) touch it
    assert axiom_battery.cycles_in(tournament, 4) == (0, 2)


def test_cycles_in_reads_missing_edges_as_undetermined_rather_than_crashing():
    assert axiom_battery.cycles_in({}, 3) == (0, 0)
    assert axiom_battery.cycles_in({(1, 2): 1}, 3) == (0, 0)


def test_cycles_in_scores_no_triangles_below_three_nodes():
    assert axiom_battery.cycles_in({(0, 1): 1}, 2) == (0, 0)


# --------------------------------------------------------------------------- icc_one


def test_icc_one_is_one_when_groups_differ_and_do_not_vary_internally():
    # Between-group mean square = 1.0, within-group = 0, k = 2: (1 - 0) / (1 + 0).
    assert axiom_battery.icc_one({"a": [0.0, 0.0], "b": [1.0, 1.0]}) == pytest.approx(1.0)


def test_icc_one_is_minus_one_when_groups_vary_identically():
    # Both groups average 0.5, so between = 0 while within = 0.5: (0 - 0.5) / (0 + 0.5).
    assert axiom_battery.icc_one({"a": [0.0, 1.0], "b": [0.0, 1.0]}) == pytest.approx(-1.0)


def test_icc_one_blends_between_and_within_variance_into_one_fraction():
    # Means 0.5 and 2.5 around a grand mean of 1.5 give between = 4; within = 0.5; k = 2:
    # (4 - 0.5) / (4 + 0.5) = 7/9.
    assert axiom_battery.icc_one({"a": [0.0, 1.0], "b": [2.0, 3.0]}) == pytest.approx(7 / 9)


def test_icc_one_reports_nan_for_a_constant_instrument():
    # Zero between and zero within variance leaves the ratio 0/0 — undefined, not passing.
    assert math.isnan(axiom_battery.icc_one({"a": [1.0, 1.0], "b": [1.0, 1.0]}))


def test_icc_one_needs_two_groups_carrying_replicates():
    assert math.isnan(axiom_battery.icc_one({}))
    assert math.isnan(axiom_battery.icc_one({"a": [0.0, 1.0]}))
    assert math.isnan(axiom_battery.icc_one({"a": [0.0], "b": [1.0]}))


def test_icc_one_ignores_cells_without_replicates():
    # The singleton cell contributes nothing: the remaining two groups are the +1 case again.
    cells = {"a": [0.0, 0.0], "b": [1.0, 1.0], "c": [9.0]}
    assert axiom_battery.icc_one(cells) == pytest.approx(1.0)


# --------------------------------------------------------------------------- spearman_brown


def test_spearman_brown_lifts_point_one_icc_above_half_at_twelve_replicates():
    # 12 * 0.1 / (1 + 11 * 0.1) = 1.2 / 2.1.
    assert axiom_battery.spearman_brown(0.1, 12) == pytest.approx(1.2 / 2.1)


def test_spearman_brown_returns_the_single_rating_at_one_replicate():
    assert axiom_battery.spearman_brown(0.5, 1) == pytest.approx(0.5)
    assert axiom_battery.spearman_brown(-0.25, 1) == pytest.approx(-0.25)


def test_spearman_brown_keeps_a_perfect_rating_perfect_at_any_replicate_count():
    assert axiom_battery.spearman_brown(1.0, 8) == pytest.approx(1.0)


def test_spearman_brown_reports_nan_for_undefined_inputs():
    assert math.isnan(axiom_battery.spearman_brown(float("nan"), 12))
    assert math.isnan(axiom_battery.spearman_brown(0.1, 0))
    assert math.isnan(axiom_battery.spearman_brown(-0.25, -3))
    # 1 + (3 - 1) * (-0.5) = 0: the formula's pole, guarded rather than raised.
    assert math.isnan(axiom_battery.spearman_brown(-0.5, 3))


# --------------------------------------------------------------------------- bootstrap_icc


def test_bootstrap_icc_bounds_coincide_when_every_defined_draw_admits_one_value():
    # Both cells are constant at different levels, so any draw mixing the two keys has zero
    # within variance and maximal between variance: ICC exactly 1. Draws repeating one key are
    # the only undefined ones, and they show up in the share instead of the interval.
    cells = {"a": [0.0, 0.0], "b": [1.0, 1.0]}
    report = axiom_battery.bootstrap_icc(cells, draws=64, seed="hand-derived")
    assert report["low"] == pytest.approx(1.0)
    assert report["high"] == pytest.approx(1.0)
    assert report["aggregate_low"] == pytest.approx(axiom_battery.spearman_brown(1.0, 2.0))
    assert report["replicates"] == pytest.approx(2.0)
    assert 0.0 < report["undefined_share"] < 1.0


def test_bootstrap_icc_counts_no_draw_undefined_when_every_cell_varies_internally():
    # Each cell carries within variance, so no resample — not even one that repeats a key —
    # can reach the zero-denominator case: the undefined share must be exactly zero.
    cells = {"a": [0.0, 1.0], "b": [2.0, 3.0]}
    report = axiom_battery.bootstrap_icc(cells, draws=48, seed="hand-derived")
    assert report["undefined_share"] == 0.0
    assert -1.0 <= report["low"] <= report["high"] <= 1.0
    assert report["replicates"] == pytest.approx(2.0)


def test_bootstrap_icc_reports_total_undefinedness_when_no_resample_has_variance():
    # Identical constant cells: between and within variance vanish for every possible draw.
    report = axiom_battery.bootstrap_icc({"a": [1.0, 1.0], "b": [1.0, 1.0]},
                                         draws=16, seed="hand-derived")
    assert report["undefined_share"] == 1.0
    assert math.isnan(report["low"])
    assert math.isnan(report["high"])
    assert report["replicates"] == pytest.approx(2.0)


def test_bootstrap_icc_refuses_to_resample_fewer_than_two_pairs():
    report = axiom_battery.bootstrap_icc({"only": [0.0, 1.0]}, draws=8, seed="hand-derived")
    assert math.isnan(report["low"])
    assert math.isnan(report["high"])
    assert report["undefined_share"] == 1.0


# --------------------------------------------------------------------------- _coin_rates


def test_coin_rates_means_exactly_the_values_its_rng_supplies():
    assert axiom_battery._coin_rates(ScriptedRng([0.0, 1.0, 0.5, 1.0]), 4) == (
        pytest.approx(0.625))
    assert axiom_battery._coin_rates(ScriptedRng([0.5] * 7), 7) == pytest.approx(0.5)


def test_coin_rates_stays_on_the_zero_half_one_scale_with_a_real_rng():
    single = axiom_battery._coin_rates(random.Random(20260822), 1)
    assert single in (0.0, 0.5, 1.0)
    mean = axiom_battery._coin_rates(random.Random(20260822), 21)
    assert 0.0 <= mean <= 1.0


# --------------------------------------------------------------------------- null simulators


def test_monotone_null_orders_no_scenes_when_there_are_no_scenes():
    assert axiom_battery.monotone_null(0, 30, draws=8, seed="m") == 0


def test_monotone_null_is_reproducible_under_a_fixed_seed_and_within_scene_count():
    first = axiom_battery.monotone_null(2, 20, draws=24, seed="m")
    second = axiom_battery.monotone_null(2, 20, draws=24, seed="m")
    assert first == second
    assert 0 <= first <= 2


def test_cycle_null_finds_no_cycles_when_there_are_no_tournaments():
    assert axiom_battery.cycle_null(0, 30, draws=8, seed="c") == 0.0


def test_cycle_null_is_reproducible_under_a_fixed_seed_and_never_negative():
    first = axiom_battery.cycle_null(1, 20, draws=24, seed="c")
    second = axiom_battery.cycle_null(1, 20, draws=24, seed="c")
    assert first == second
    assert first >= 0.0
