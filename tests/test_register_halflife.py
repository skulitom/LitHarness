"""What the pure arithmetic of ``register_halflife`` pins, on constructed inputs.

These tests pin the model-free core of the module: how text is cut into overlapping word
windows, how feature rows average into a centroid and spread into a z-scale, how a window's
two anchor distances collapse into one number, when a trajectory reads as crossed rather than
censored, how the diagnostic half-life is fitted and when it refuses, how the label-blind
residual adjustment is applied and re-paired, and when the inverted-U alternative may be
called significant. Every expected value is derived by hand from the definitions.

They establish nothing about generation, transports, caches, whether track F1 works on real
prose, or anything measured by the sibling force modules. ``neutral_pool`` reads a corpus file
and is deliberately untouched; ``score_pairs`` and the CLI need a model and are out of scope.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

register_halflife = pytest.importorskip(
    "register_halflife",
    reason="research module; needs the quality-measurement directory on the path",
)

ACTIVE = register_halflife.ACTIVE


def _row(**overrides: float) -> dict[str, float]:
    """A full feature row over ACTIVE with every value at 1.0 unless overridden."""
    base = {name: 1.0 for name in ACTIVE}
    base.update(overrides)
    return base


def _unit_scale() -> dict[str, float]:
    return {name: 1.0 for name in ACTIVE}


# --------------------------------------------------------------------------------- windows


def test_windows_steps_by_stride_over_a_long_text():
    assert register_halflife.windows("a b c d e f", size=4, stride=2) == [
        "a b c d",
        "c d e f",
    ]


def test_windows_of_text_exactly_one_window_long_yield_that_one_window():
    assert register_halflife.windows("a b c", size=3, stride=1) == ["a b c"]


def test_windows_slide_up_to_the_last_full_window_inclusive():
    assert register_halflife.windows("a b c d", size=3, stride=1) == ["a b c", "b c d"]


def test_windows_of_text_shorter_than_the_size_are_one_partial_window():
    assert register_halflife.windows("hello world", size=100, stride=25) == ["hello world"]


def test_windows_of_an_empty_text_are_empty():
    assert register_halflife.windows("") == []


# ------------------------------------------------------------------ centroid / scale_of


def test_centroid_averages_each_feature_across_rows():
    first = ACTIVE[0]
    rows = [_row(**{first: 1.0}), _row(**{first: 3.0}), _row(**{first: 5.0})]
    result = register_halflife.centroid(rows)
    assert result[first] == pytest.approx(3.0)
    assert all(result[name] == pytest.approx(1.0) for name in ACTIVE if name != first)


def test_centroid_returns_only_active_features_and_ignores_extra_keys():
    first = ACTIVE[0]
    # Real feature rows carry `words`, whose spread across windows is a windowing artifact.
    rows = [{**_row(**{first: 1.0}), "words": 1.0}, {**_row(**{first: 3.0}), "words": 5000.0}]
    result = register_halflife.centroid(rows)
    assert set(result) == set(ACTIVE)
    assert result[first] == pytest.approx(2.0)


def test_centroid_of_a_single_row_is_that_row():
    row = _row(**{ACTIVE[0]: 7.0})
    result = register_halflife.centroid([row])
    assert all(result[name] == row[name] for name in ACTIVE)


def test_scale_of_two_rows_is_half_their_absolute_spread():
    first = ACTIVE[0]
    scale = register_halflife.scale_of([_row(**{first: 1.0}), _row(**{first: 3.0})])
    assert scale[first] == pytest.approx(1.0)
    assert all(scale[name] == 0.0 for name in ACTIVE if name != first)


def test_scale_of_a_constant_feature_is_zero_spread():
    scale = register_halflife.scale_of([_row(), _row(), _row()])
    assert all(scale[name] == 0.0 for name in ACTIVE)


def test_scale_of_a_single_row_reports_zero_for_every_feature():
    scale = register_halflife.scale_of([_row(**{ACTIVE[0]: 9.0})])
    assert all(scale[name] == 0.0 for name in ACTIVE)


def test_scale_of_three_rows_is_the_population_standard_deviation():
    first = ACTIVE[0]
    rows = [_row(**{first: v}) for v in (1.0, 2.0, 3.0)]
    assert register_halflife.scale_of(rows)[first] == pytest.approx(math.sqrt(2.0 / 3.0))


# ---------------------------------------------------------------------------- z_distance


def test_z_distance_of_identical_row_and_anchor_is_zero():
    assert register_halflife.z_distance(_row(), _row(), _unit_scale()) == 0.0


def test_z_distance_counts_a_one_standard_deviation_gap_as_one():
    first = ACTIVE[0]
    row = _row(**{first: 2.0})
    anchor = _row(**{first: 1.0})
    assert register_halflife.z_distance(row, anchor, _unit_scale()) == pytest.approx(1.0)


def test_z_distance_adds_orthogonal_deviations_in_quadrature():
    first, second = ACTIVE[0], ACTIVE[1]
    row = _row(**{first: 3.0, second: 0.0})
    anchor = _row(**{first: 1.0, second: 1.0})
    # +2 sd in the first feature and -1 sd in the second: sqrt(4 + 1).
    result = register_halflife.z_distance(row, anchor, _unit_scale())
    assert result == pytest.approx(math.sqrt(5.0))


def test_z_distance_skips_features_the_scale_reports_as_zero_spread():
    first = ACTIVE[0]
    row = _row(**{first: 101.0})
    anchor = _row(**{first: 1.0})
    scale = {name: 0.0 for name in ACTIVE}
    assert register_halflife.z_distance(row, anchor, scale) == 0.0


def test_z_distance_treats_a_scale_entry_missing_entirely_as_zero_spread():
    first = ACTIVE[0]
    row = _row(**{first: 101.0})
    anchor = _row(**{first: 1.0})
    scale = {name: 1.0 for name in ACTIVE if name != first}
    assert register_halflife.z_distance(row, anchor, scale) == 0.0



# ------------------------------------------------------------------------------- rows


def test_rows_returns_one_feature_row_per_window():
    text = " ".join(f"word{i}" for i in range(150))
    assert len(register_halflife.rows(text)) == len(register_halflife.windows(text)) == 3


def test_rows_of_an_empty_text_have_no_rows():
    assert register_halflife.rows("") == []


def test_rows_carry_every_active_feature():
    for row in register_halflife.rows("some ordinary prose in a small window"):
        assert set(ACTIVE) <= set(row)


# ---------------------------------------------------------------------------- trajectory


def test_trajectory_returns_one_distance_pair_per_window():
    continuation = " ".join(f"w{i}" for i in range(150))
    anchor = _row()
    median = {name: 2.0 for name in ACTIVE}
    to_seed, to_median = register_halflife.trajectory(continuation, anchor, median, _unit_scale())
    assert len(to_seed) == len(to_median) == len(register_halflife.windows(continuation)) == 3


def test_trajectory_of_the_anchor_built_from_a_continuation_itself_sits_at_zero():
    continuation = "alpha beta gamma delta epsilon"
    anchor = register_halflife.centroid(register_halflife.rows(continuation))
    to_seed, to_median = register_halflife.trajectory(continuation, anchor, anchor, _unit_scale())
    assert len(to_seed) == len(to_median) == 1
    assert to_seed[0] == 0.0
    assert to_median[0] == 0.0


def test_trajectory_of_an_empty_continuation_is_two_empty_lists():
    assert register_halflife.trajectory("", _row(), _row(), _unit_scale()) == ([], [])


# ------------------------------------------------------------------------------ crossover


def test_crossover_reports_the_first_window_where_the_seed_pull_loses():
    to_seed = [0.0, 0.0, 3.0]
    to_median = [5.0, 5.0, 2.0]
    assert register_halflife.crossover(to_seed, to_median) == (2, False)


def test_crossover_never_crosses_while_the_distances_stay_equal():
    # The comparison is strict: a window equidistant between the anchors is still held.
    assert register_halflife.crossover([1.0, 2.0], [1.0, 2.0]) == (2, True)


def test_crossover_can_lose_at_the_very_first_window():
    assert register_halflife.crossover([2.0], [1.0]) == (0, False)


def test_crossover_of_an_empty_trajectory_is_censored_at_index_zero():
    assert register_halflife.crossover([], []) == (0, True)


# ------------------------------------------------------------------------------ half_life


def test_half_life_of_a_residual_that_halves_every_window_is_one():
    # seed held at 1, medians chosen so r_w = median/(seed+median) - 0.5 hits 0.4, 0.2, 0.1:
    # log-linear with slope -ln 2, so the exponential half-life is exactly one window.
    to_seed = [1.0, 1.0, 1.0]
    to_median = [9.0, 7.0 / 3.0, 1.5]
    assert register_halflife.half_life(to_seed, to_median) == pytest.approx(1.0, rel=1e-9)


def test_half_life_skips_a_window_whose_distances_sum_to_zero():
    # The same decay shifted one window later; the leading zero-total window must drop out
    # rather than divide by zero or shift the fit off its indices.
    to_seed = [0.0, 1.0, 1.0, 1.0]
    to_median = [0.0, 9.0, 7.0 / 3.0, 1.5]
    assert register_halflife.half_life(to_seed, to_median) == pytest.approx(1.0, rel=1e-9)


def test_half_life_of_a_rising_residual_does_not_decay():
    to_seed = [1.0, 1.0, 1.0]
    to_median = [9.0, 12.0, 15.0]  # r rises: 0.4, 12/13 - 0.5, 0.4375
    assert register_halflife.half_life(to_seed, to_median) == math.inf


def test_half_life_refuses_fewer_than_three_positive_residuals():
    assert math.isnan(register_halflife.half_life([1.0, 1.0], [9.0, 7.0 / 3.0]))


def test_half_life_of_all_zero_totals_is_nan_rather_than_a_crash():
    assert math.isnan(register_halflife.half_life([], []))
    assert math.isnan(register_halflife.half_life([0.0, 0.0, 0.0], [0.0, 0.0, 0.0]))


# ------------------------------------------------------------------------ side_statistics


PLAIN_SEED = "he said nothing and the road went on past the last house"
LOUD_SIDE = "stop! wait, who goes there? really: listen and go now"


def test_side_statistics_with_the_median_parked_on_the_seed_censors_every_replicate():
    # Median == seed anchor makes both distances the same call, and the crossover comparison
    # is strict, so no window ever crosses: every replicate dies at its last window.
    anchor = register_halflife.centroid(register_halflife.rows(PLAIN_SEED))
    produced = ["calm words about weather", "more calm words about stone", "quiet words on rain"]
    stats = register_halflife.side_statistics(PLAIN_SEED, produced, anchor, _unit_scale())
    assert stats["crossover"] == 1.0
    assert stats["censored_share"] == 1.0
    assert stats["replicates"] == 3
    assert stats["distinctiveness"] == 0.0
    assert math.isnan(stats["half_life"])


def test_side_statistics_continuation_identical_to_the_median_crosses_immediately():
    # The continuation IS the median, so its distance there is exactly zero and any other
    # anchor sits strictly farther: window 0 loses the seed's pull at once.
    median = register_halflife.centroid(register_halflife.rows(LOUD_SIDE))
    both_rows = register_halflife.rows(PLAIN_SEED) + register_halflife.rows(LOUD_SIDE)
    scale = register_halflife.scale_of(both_rows)
    stats = register_halflife.side_statistics(PLAIN_SEED, [LOUD_SIDE], median, scale)
    assert stats["crossover"] == 0.0
    assert stats["censored_share"] == 0.0
    assert stats["replicates"] == 1
    assert stats["distinctiveness"] > 0.0
    assert math.isnan(stats["half_life"])  # one window cannot support the fit


def test_side_statistics_without_any_surviving_trajectory_returns_empty():
    anchor = register_halflife.centroid(register_halflife.rows(PLAIN_SEED))
    assert register_halflife.side_statistics(PLAIN_SEED, [], anchor, _unit_scale()) == {}
    assert register_halflife.side_statistics(PLAIN_SEED, [""], anchor, _unit_scale()) == {}


# ------------------------------------------------------------------------- residual_scores


def test_residual_scores_strips_a_covariate_that_explains_every_value():
    scores = {f"p{i}": {"high": 3.0 * i, "low": 3.0 * i + 1.5} for i in range(6)}
    covariate = {}
    for i in range(6):
        covariate[f"p{i}|high"] = float(i)
        covariate[f"p{i}|low"] = float(i) + 0.5  # every value is exactly 3x its covariate
    adjusted = register_halflife.residual_scores(scores, covariate)
    assert len(adjusted) == 6
    assert all(set(row) == {"high", "low"} for row in adjusted.values())
    assert max(abs(v) for row in adjusted.values() for v in row.values()) < 1e-9


def test_residual_scores_keeps_a_raw_tie_a_tie_after_adjustment():
    # Both pairs tie raw. Adjustment would split them by covariate alone; the rule pins them
    # back together at their midpoint, so a refusal cannot become a refutation.
    scores = {"a": {"high": 0.0, "low": 0.0}, "q": {"high": 5.0, "low": 5.0}}
    covariate = {"a|high": 0.0, "a|low": 1.0, "q|high": 0.0, "q|low": 10.0}
    adjusted = register_halflife.residual_scores(scores, covariate)
    assert adjusted["a"]["high"] == adjusted["a"]["low"]
    assert adjusted["q"]["high"] == adjusted["q"]["low"]


def test_residual_scores_drops_a_pair_that_only_has_one_side():
    scores = {"full": {"high": 1.0, "low": 2.0}, "half": {"high": 3.0}}
    covariate = {"full|high": 0.0, "full|low": 1.0, "half|high": 2.0}
    adjusted = register_halflife.residual_scores(scores, covariate)
    assert set(adjusted) == {"full"}


# ------------------------------------------------------------------------------ inverted_u


def _grid_covariate(low: int, high: int) -> dict[str, float]:
    return {f"k{x}": float(x) for x in range(low, high + 1)}


def test_inverted_u_reads_an_exact_inverted_parabola_as_a_significant_interior_peak():
    covariate = _grid_covariate(-6, 6)
    values = {key: -(x * x) for key, x in covariate.items()}
    result = register_halflife.inverted_u(covariate, values)
    assert result["status"] == "READ"
    assert result["significant"] is True
    assert result["interior_peak"] is True
    assert result["quadratic"] == pytest.approx(-1.0, rel=1e-6)
    assert result["peak_at"] == pytest.approx(0.0, abs=1e-6)



def test_inverted_u_reads_a_line_with_symmetric_even_noise_as_not_significant():
    # y = 5x + 10*(-1)^x on x = -6..6: the perturbation is even in x, so the odd (linear) and
    # even (quadratic) contrasts decouple and the quadratic term's |t| is about 0.56 by hand --
    # real signal in the fit, but far below the significance bar.
    covariate = _grid_covariate(-6, 6)
    values = {f"k{x}": 5.0 * x + 10.0 * (-1) ** x for x in range(-6, 7)}
    result = register_halflife.inverted_u(covariate, values)
    assert result["status"] == "READ"
    assert result["significant"] is False
    assert result["interior_peak"] is False
    assert result["quadratic_t"] is not None
    assert abs(result["quadratic_t"]) < 1.5


def test_inverted_u_counts_only_keys_present_in_both_inputs():
    covariate = _grid_covariate(0, 11)
    values = {f"k{x}": float(-(x * x)) for x in range(0, 14)}  # two keys with no covariate
    result = register_halflife.inverted_u(covariate, values)
    assert result["status"] == "READ"
    assert result["n"] == 12


def test_inverted_u_ignores_non_finite_values():
    covariate = _grid_covariate(0, 12)
    values = {key: -(x * x) for key, x in covariate.items()}
    values["k5"] = float("nan")
    result = register_halflife.inverted_u(covariate, values)
    assert result["status"] == "READ"
    assert result["n"] == 12


def test_inverted_u_refuses_below_twelve_shared_keys():
    covariate = _grid_covariate(0, 10)
    values = {key: -(x * x) for key, x in covariate.items()}
    result = register_halflife.inverted_u(covariate, values)
    assert result == {"status": "INSUFFICIENT_N", "n": 11}


# ------------------------------------------------------------------------------- selftest


def test_module_selftest_passes():
    assert register_halflife.selftest() == 0

