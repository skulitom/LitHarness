"""Hermetic pins on the pure arithmetic of `taste_benchmark.py`.

What these tests pin: the pair-admission constraints in `_candidates` (label gap floor, length
and view tolerances, which side is named high); the bucket routing that splits `aligned` on the
sign of its view residual; the interleaved selector's story disjointness, scarcity ordering,
per-stratum limit and best-match-first order; the balance table's medians and counts; the
prose-blind scoring whose headline property is that no popularity rule clears 0.50 in *both*
strata; and the pre-registered verdict gates (ABSENT before VOID before the bar, band edges
inclusive, lower bounds strictly above 0.50, `pick_longer_chapter_not_shown` excluded from the
ranking). Every expected value below was derived by hand from the docstrings and code before
running anything.

What they do not establish: that the corpus builds, that any judge agrees with anything, or that
the pre-registered bar is meetable. Nothing here reads a shard, a results file, a database, or
calls a model — `build`, `run`, `main`, `_story_pool` and the elicitation path are all out of
scope, and the module has no `selftest`.
"""

from __future__ import annotations

import argparse
import math
from typing import Any

import pytest

taste_benchmark = pytest.importorskip(
    "taste_benchmark",
    reason="research module; needs the quality-measurement directory on the path",
)


def _story(work_id: str, *, conversion: float, views: int, followers: int,
           words: int) -> dict[str, Any]:
    return {"work_id": work_id, "conversion": conversion, "views": views,
            "followers": followers, "words": words}


def _args(**overrides: float) -> argparse.Namespace:
    values: dict[str, Any] = {
        "min_conversion_ratio": 2.0, "max_log_word_gap": 0.10, "max_log_view_gap": 0.30,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _side(work_id: str, views: int = 100) -> dict[str, Any]:
    """The only fields `_select_interleaved` and `_bucket` read."""
    return {"work_id": work_id, "views": views}


def _entry(high_id: str, low_id: str, cost: float, *, high_views: int = 100,
           low_views: int = 50) -> tuple[dict[str, Any], dict[str, Any], float]:
    return (_side(high_id, high_views), _side(low_id, low_views), cost)


# --------------------------------------------------------------------------- _excerpt


def test_excerpt_starts_a_fifth_of_the_way_in_and_cuts_on_paragraph_boundaries():
    paragraphs = [" ".join(f"{i}_{k}" for k in range(10)) for i in range(10)]
    text = "\n\n".join(paragraphs)
    # 10 blocks of 10 words; target = int(0.2 * 100) = 20 words in, so the window opens at
    # block 2 and stops once 30 words are gathered: blocks 2, 3 and 4 exactly.
    assert taste_benchmark._excerpt(text, 30) == "\n\n".join(paragraphs[2:5])


def test_excerpt_returns_a_short_text_intact_when_it_fits_the_window():
    text = "alpha beta gamma\n\ndelta epsilon zeta"
    assert taste_benchmark._excerpt(text) == text


def test_excerpt_falls_back_to_single_newlines_and_joins_with_blank_lines():
    lines = [" ".join(f"l{i}w{k}" for k in range(5)) for i in range(8)]
    text = "\n".join(lines)
    # One double-newline block is below the 4-block floor, so the split falls back to single
    # newlines: 8 blocks of 5 words, target 8, window opens at line 2 and gathers three lines,
    # re-joined with blank lines between them.
    assert taste_benchmark._excerpt(text, 15) == "\n\n".join(lines[2:5])


def test_excerpt_of_an_empty_string_is_an_empty_string():
    assert taste_benchmark._excerpt("") == ""


def test_excerpt_of_whitespace_only_text_is_returned_unchanged():
    text = "\n\n \n\n"
    assert taste_benchmark._excerpt(text) == text


# --------------------------------------------------------------------------- _bucket


def test_bucket_routes_crossed_pairs_to_the_crossed_bucket_whatever_the_view_sign():
    high = _side("h", views=10_000)
    low = _side("l", views=25_000)
    assert taste_benchmark._bucket("crossed", high, low) == "crossed"
    assert taste_benchmark._bucket("crossed", low, high) == "crossed"


def test_bucket_splits_aligned_on_whether_the_high_side_has_more_views():
    more = _side("h", views=12_000)
    less = _side("l", views=11_000)
    assert taste_benchmark._bucket("aligned", more, less) == "aligned+"
    assert taste_benchmark._bucket("aligned", less, more) == "aligned-"


def test_bucket_calls_an_aligned_pair_with_equal_views_aligned_minus():
    tie = _side("h", views=12_000)
    other = _side("l", views=12_000)
    assert taste_benchmark._bucket("aligned", tie, other) == "aligned-"


# --------------------------------------------------------------------------- _candidates

# One compliant pair, reused across tests: s_hi carries four times s_lo's conversion, near-
# identical length, and (unless a test says otherwise) more followers and views, so it is
# admissible for `aligned` and inadmissible for `crossed`.
S_HI = dict(conversion=0.02, views=20_000, followers=400, words=2_000)
S_LO = dict(conversion=0.005, views=21_000, followers=380, words=1_950)


def test_candidates_names_the_higher_conversion_side_high_regardless_of_input_order():
    low_first = _story("lo", **S_LO)
    high_second = _story("hi", **S_HI)
    candidates = taste_benchmark._candidates([low_first, high_second], _args(), "aligned")
    assert [(pair[0]["work_id"], pair[1]["work_id"]) for pair in candidates] == [("hi", "lo")]


def test_candidates_admits_a_pair_exactly_at_the_conversion_ratio_floor():
    edge_hi = _story("hi", conversion=0.010, views=20_000, followers=400, words=2_000)
    lo = _story("lo", conversion=0.005, views=21_000, followers=380, words=1_950)
    # 0.010 is not strictly below 2 x 0.005, so the pair survives the floor.
    assert len(taste_benchmark._candidates([edge_hi, lo], _args(), "aligned")) == 1


def test_candidates_drops_a_pair_just_below_the_conversion_ratio_floor():
    under_hi = _story("hi", conversion=0.0099, views=20_000, followers=400, words=2_000)
    lo = _story("lo", conversion=0.005, views=21_000, followers=380, words=1_950)
    assert taste_benchmark._candidates([under_hi, lo], _args(), "aligned") == []


def test_candidates_drops_an_aligned_pair_whose_view_gap_exceeds_the_tolerance():
    wide_hi = _story("hi", conversion=0.02, views=15_000, followers=400, words=2_000)
    lo = _story("lo", conversion=0.005, views=7_000, followers=380, words=1_950)
    # log10(15000/7000) ~= 0.331, outside the 0.30 factor-of-two tolerance.
    assert taste_benchmark._candidates([wide_hi, lo], _args(), "aligned") == []


def test_candidates_keeps_an_aligned_pair_whose_view_gap_is_within_the_tolerance():
    hi = _story("hi", conversion=0.02, views=15_000, followers=400, words=2_000)
    lo = _story("lo", conversion=0.005, views=8_000, followers=380, words=1_950)
    # log10(15000/8000) ~= 0.273, inside the tolerance.
    assert len(taste_benchmark._candidates([hi, lo], _args(), "aligned")) == 1


def test_candidates_drops_a_pair_whose_word_gap_exceeds_the_tolerance():
    long_hi = _story("hi", conversion=0.02, views=20_000, followers=400, words=1_400)
    lo = _story("lo", conversion=0.005, views=20_000, followers=380, words=1_000)
    # log10(1400/1000) ~= 0.146, outside the 0.10 tolerance.
    assert taste_benchmark._candidates([long_hi, lo], _args(), "aligned") == []


def test_candidates_keeps_a_pair_whose_word_gap_is_within_the_tolerance():
    hi = _story("hi", conversion=0.02, views=20_000, followers=400, words=1_100)
    lo = _story("lo", conversion=0.005, views=20_000, followers=380, words=1_000)
    assert len(taste_benchmark._candidates([hi, lo], _args(), "aligned")) == 1


def test_candidates_costs_an_aligned_pair_by_view_gap_plus_word_gap():
    hi = _story("hi", conversion=0.02, views=20_000, followers=400, words=2_000)
    lo = _story("lo", conversion=0.005, views=10_000, followers=380, words=1_000)
    args = _args(max_log_view_gap=0.35, max_log_word_gap=0.35)
    candidates = taste_benchmark._candidates([hi, lo], args, "aligned")
    expected = math.log10(20_000 / 10_000) + math.log10(2_000 / 1_000)
    assert candidates[0][2] == pytest.approx(expected)


def test_candidates_crossed_rejects_a_pair_whose_high_side_has_more_followers():
    followed_hi = _story("hi", conversion=0.02, views=10_000, followers=400, words=2_000)
    lo = _story("lo", conversion=0.005, views=30_000, followers=380, words=1_950)
    # The view direction is fine for crossed; only the follower sign disqualifies it.
    assert taste_benchmark._candidates([followed_hi, lo], _args(), "crossed") == []


def test_candidates_crossed_rejects_a_pair_whose_high_side_has_more_views():
    read_hi = _story("hi", conversion=0.02, views=30_000, followers=100, words=2_000)
    lo = _story("lo", conversion=0.005, views=10_000, followers=500, words=1_950)
    assert taste_benchmark._candidates([read_hi, lo], _args(), "crossed") == []


def test_candidates_crossed_keeps_a_pair_pointing_away_from_the_label_and_costs_only_words():
    hi = _story("hi", conversion=0.02, views=10_000, followers=100, words=2_000)
    lo = _story("lo", conversion=0.005, views=30_000, followers=500, words=1_950)
    candidates = taste_benchmark._candidates([hi, lo], _args(), "crossed")
    # The view gap here is ~0.477, far beyond the aligned tolerance, yet crossed still admits
    # the pair because crossed prices length alone.
    assert len(candidates) == 1
    assert candidates[0][2] == pytest.approx(math.log10(2_000 / 1_950))


def test_candidates_needs_two_stories_to_form_any_pair():
    solo = _story("hi", **S_HI)
    assert taste_benchmark._candidates([], _args(), "aligned") == []
    assert taste_benchmark._candidates([solo], _args(), "aligned") == []
    assert taste_benchmark._candidates([], _args(), "crossed") == []


# --------------------------------------------------------------------------- _balance


def _picked_pair(high: dict[str, Any], low: dict[str, Any]) -> dict[str, Any]:
    return {"high": high, "low": low, "match_cost": 0.0}


def _covariate_side(**overrides: float) -> dict[str, Any]:
    """A side carrying every field `_balance` reads, with the fields under test overridden."""
    values: dict[str, Any] = {"views": 1_000, "followers": 100, "favorites": 10,
                              "words": 2_000, "conversion": 0.01}
    values.update(overrides)
    return values


def test_balance_reports_medians_ratios_and_counts_for_each_field():
    pairs = [
        _picked_pair(
            _covariate_side(views=20_000, followers=500, conversion=0.02),
            _covariate_side(views=10_000, followers=100, conversion=0.01),
        ),
        _picked_pair(
            _covariate_side(views=30_000, followers=700, conversion=0.04),
            _covariate_side(views=9_000, followers=90, conversion=0.005),
        ),
    ]
    balance = taste_benchmark._balance(pairs)
    assert set(balance) == {"views", "followers", "favorites", "words", "conversion"}
    assert balance["views"] == {
        "high_median": 25_000.0, "low_median": 9_500.0, "median_ratio": 2.6316,
        "high_side_larger_in_pairs": 2, "of_pairs": 2,
    }
    assert balance["conversion"]["median_ratio"] == 4.0
    assert balance["followers"]["high_side_larger_in_pairs"] == 2


def test_balance_gives_a_null_ratio_when_the_low_median_is_zero():
    pairs = [
        _picked_pair(_covariate_side(favorites=10), _covariate_side(favorites=0)),
        _picked_pair(_covariate_side(favorites=30), _covariate_side(favorites=0)),
    ]
    favorites = taste_benchmark._balance(pairs)["favorites"]
    assert favorites["median_ratio"] is None
    assert favorites["low_median"] == 0
    assert favorites["high_side_larger_in_pairs"] == 2


def test_balance_counts_a_tied_field_as_not_high_side_larger():
    pairs = [
        _picked_pair(_covariate_side(words=2_000), _covariate_side(words=2_000)),
        _picked_pair(_covariate_side(words=2_100), _covariate_side(words=2_100)),
    ]
    words = taste_benchmark._balance(pairs)["words"]
    assert words["median_ratio"] == 1.0
    assert words["high_side_larger_in_pairs"] == 0


def test_balance_of_no_pairs_is_empty():
    assert taste_benchmark._balance([]) == {}


# --------------------------------------------------------------------------- prose_blind


def _meta_pair(stratum: str, high: dict[str, Any], low: dict[str, Any]) -> dict[str, Any]:
    return {"stratum": stratum, "high": high, "low": low}


def _rule_side(**overrides: int) -> dict[str, int]:
    """A side carrying every field the prose-blind rules read, with one covariate set."""
    values: dict[str, int] = {"followers": 0, "views": 0, "favorites": 0,
                              "excerpt_words": 0, "words": 0}
    values.update(overrides)
    return values


def _labelled_meta() -> dict[str, Any]:
    """One aligned and one crossed pair whose covariate signs are fixed by hand.

    The aligned high side has more of everything; the crossed high side has *fewer* followers
    and views but more favourites and slightly longer text, which is what the strata definition
    forces and what no popularity rule can survive in both.
    """
    aligned = _meta_pair(
        "aligned",
        {"followers": 500, "views": 20_000, "favorites": 50, "excerpt_words": 1_000,
         "words": 4_000},
        {"followers": 100, "views": 18_000, "favorites": 10, "excerpt_words": 998,
         "words": 3_980},
    )
    crossed = _meta_pair(
        "crossed",
        {"followers": 90, "views": 9_000, "favorites": 60, "excerpt_words": 999,
         "words": 3_900},
        {"followers": 400, "views": 25_000, "favorites": 5, "excerpt_words": 997,
         "words": 3_700},
    )
    return {"pairs": [aligned, crossed]}


def test_prose_blind_scores_popularity_rules_one_in_aligned_and_zero_in_crossed():
    report = taste_benchmark.prose_blind(_labelled_meta())
    assert report["pick_more_followers"]["per_stratum"] == {"aligned": 1.0, "crossed": 0.0}
    assert report["pick_more_views"]["per_stratum"] == {"aligned": 1.0, "crossed": 0.0}
    assert report["pick_fewer_followers"]["per_stratum"] == {"aligned": 0.0, "crossed": 1.0}
    assert report["pick_fewer_views"]["per_stratum"] == {"aligned": 0.0, "crossed": 1.0}


def test_prose_blind_caps_every_view_and_follower_rule_at_zero_across_strata():
    report = taste_benchmark.prose_blind(_labelled_meta())
    for name in ("pick_more_followers", "pick_fewer_followers",
                 "pick_more_views", "pick_fewer_views"):
        assert report[name]["min_across_strata"] == 0.0


def test_prose_blind_gives_a_full_score_to_a_rule_that_holds_in_both_strata():
    # Favourites is higher on the high-conversion side in both pairs, so unlike the follower
    # and view rules it is not forced to zero anywhere.
    report = taste_benchmark.prose_blind(_labelled_meta())
    assert report["pick_more_favorites"]["per_stratum"] == {"aligned": 1.0, "crossed": 1.0}
    assert report["pick_more_favorites"]["min_across_strata"] == 1.0


def test_prose_blind_rounds_partial_accuracy_to_four_decimals():
    pairs = [
        _meta_pair("aligned", _rule_side(followers=2), _rule_side(followers=1)),
        _meta_pair("aligned", _rule_side(followers=2), _rule_side(followers=1)),
        _meta_pair("aligned", _rule_side(followers=1), _rule_side(followers=2)),
        _meta_pair("aligned", _rule_side(followers=1), _rule_side(followers=2)),
    ]
    report = taste_benchmark.prose_blind({"pairs": pairs})
    assert report["pick_more_followers"]["per_stratum"] == {"aligned": 0.5}


def test_prose_blind_ignores_pairs_from_unknown_strata():
    meta = _labelled_meta()
    meta["pairs"].append(_meta_pair("acclaim", {"followers": 9}, {"followers": 1}))
    report = taste_benchmark.prose_blind(meta)
    assert report["pick_more_followers"]["per_stratum"] == {"aligned": 1.0, "crossed": 0.0}


def test_prose_blind_without_pairs_reports_null_minima_for_every_rule():
    report = taste_benchmark.prose_blind({})
    for entry in report.values():
        assert entry["per_stratum"] == {}
        assert entry["min_across_strata"] is None


def test_prose_blind_reports_only_the_strata_that_are_present():
    only_aligned = {
        "pairs": [_meta_pair("aligned", _rule_side(followers=2), _rule_side(followers=1))],
    }
    entry = taste_benchmark.prose_blind(only_aligned)["pick_more_followers"]
    assert entry["per_stratum"] == {"aligned": 1.0}
    assert entry["min_across_strata"] == 1.0


# --------------------------------------------------------------------------- verdict


def _in_band_bias() -> dict[str, dict[str, Any]]:
    return {"aligned": {"chose_A_rate": 0.52}, "crossed": {"chose_A_rate": 0.48}}


def _zero_blind_baseline() -> dict[str, dict[str, Any]]:
    return {"pick_more_followers": {"min_across_strata": 0.0}}


def _clearing_intervals() -> dict[str, dict[str, Any]]:
    return {"aligned": {"low": 0.55}, "crossed": {"low": 0.51}}


def test_verdict_passes_when_both_strata_beat_the_blind_minimum_and_clear_half():
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, _in_band_bias(),
        _zero_blind_baseline(), _clearing_intervals(),
    )
    assert outcome["outcome"] == "PASSES"
    assert outcome["min_agreement"] == 0.58
    assert outcome["best_prose_blind_min"] == 0.0
    assert outcome["lower_bounds"] == {"aligned": 0.55, "crossed": 0.51}


def test_verdict_fails_when_an_interval_lower_bound_sits_exactly_at_half():
    intervals = {"aligned": {"low": 0.55}, "crossed": {"low": 0.50}}
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, _in_band_bias(),
        _zero_blind_baseline(), intervals,
    )
    assert outcome["outcome"] == "FAILS"
    assert outcome["lower_bounds"]["crossed"] == 0.50


def test_verdict_fails_when_the_minimum_does_not_beat_the_best_prose_blind_minimum():
    baselines = {"pick_more_followers": {"min_across_strata": 0.5}}
    outcome = taste_benchmark.verdict(
        {"aligned": 0.45, "crossed": 0.55}, _in_band_bias(), baselines,
        _clearing_intervals(),
    )
    assert outcome["outcome"] == "FAILS"
    assert "NOT beaten" in outcome["why"]


def test_verdict_excludes_the_not_shown_length_rule_from_the_prose_blind_ranking():
    baselines = {
        "pick_longer_chapter_not_shown": {"min_across_strata": 1.0},
        "pick_more_followers": {"min_across_strata": 0.0},
    }
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, _in_band_bias(), baselines,
        _clearing_intervals(),
    )
    assert outcome["best_prose_blind_min"] == 0.0
    assert outcome["outcome"] == "PASSES"


def test_verdict_is_absent_when_either_stratum_lacks_agreement():
    partial = taste_benchmark.verdict(
        {"aligned": 0.62}, _in_band_bias(), _zero_blind_baseline(), _clearing_intervals(),
    )
    assert partial["outcome"] == "ABSENT"
    assert "needs both strata" in partial["why"]
    empty = taste_benchmark.verdict({}, {}, {}, {})
    assert empty["outcome"] == "ABSENT"


def test_verdict_absent_takes_precedence_over_an_out_of_band_bias():
    bias = {"aligned": {"chose_A_rate": 0.9}}
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62}, bias, _zero_blind_baseline(), _clearing_intervals(),
    )
    assert outcome["outcome"] == "ABSENT"


def test_verdict_voids_when_positional_bias_leaves_the_band():
    bias = {"aligned": {"chose_A_rate": 0.61}, "crossed": {"chose_A_rate": 0.48}}
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, bias, _zero_blind_baseline(),
        _clearing_intervals(),
    )
    assert outcome["outcome"] == "VOID"
    assert "positional bias outside 0.40-0.60" in outcome["why"]


def test_verdict_keeps_bias_exactly_at_the_band_edges():
    bias = {"aligned": {"chose_A_rate": 0.60}, "crossed": {"chose_A_rate": 0.40}}
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, bias, _zero_blind_baseline(),
        _clearing_intervals(),
    )
    assert outcome["outcome"] == "PASSES"


def test_verdict_voids_when_a_stratums_positional_bias_was_never_measured():
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, {}, _zero_blind_baseline(),
        _clearing_intervals(),
    )
    assert outcome["outcome"] == "VOID"


def test_verdict_fails_when_intervals_are_missing_entirely():
    outcome = taste_benchmark.verdict(
        {"aligned": 0.62, "crossed": 0.58}, _in_band_bias(), _zero_blind_baseline(), {},
    )
    assert outcome["outcome"] == "FAILS"


# --------------------------------------------------------------------------- _select_interleaved


def test_select_interleaved_skips_used_stories_and_keeps_walking_the_queue():
    candidates = {
        "crossed": [
            _entry("a", "b", 0.01),
            _entry("a", "c", 0.03),  # "a" already picked; must be passed over, not fatal.
            _entry("d", "e", 0.05),
        ],
    }
    picked = taste_benchmark._select_interleaved(candidates, 0)
    assert [(pair["high"]["work_id"], pair["low"]["work_id"])
            for pair in picked["crossed"]] == [("a", "b"), ("d", "e")]
    assert picked["aligned"] == []


def test_select_interleaved_serves_a_scarce_stratum_before_crossed_claims_its_stories():
    # "y" appears in both strata. Aligned is served first, so its claim on "y" stands and the
    # cheaper crossed pair that wanted "y" is dropped rather than starving aligned.
    candidates = {
        "aligned": [_entry("x", "y", 0.5)],
        "crossed": [_entry("y", "z", 0.001)],
    }
    picked = taste_benchmark._select_interleaved(candidates, 0)
    assert [(pair["high"]["work_id"], pair["low"]["work_id"])
            for pair in picked["aligned"]] == [("x", "y")]
    assert picked["crossed"] == []


def test_select_interleaved_enforces_disjointness_within_a_stratum():
    candidates = {"crossed": [_entry("a", "b", 0.01), _entry("c", "d", 0.03)]}
    picked = taste_benchmark._select_interleaved(candidates, 0)
    used = [pair["high"]["work_id"] for pair in picked["crossed"]]
    used += [pair["low"]["work_id"] for pair in picked["crossed"]]
    assert sorted(used) == ["a", "b", "c", "d"]


def test_select_interleaved_picks_the_best_matched_pair_first_and_rounds_its_cost():
    candidates = {
        "crossed": [
            _entry("a", "b", 0.05),
            _entry("c", "d", 0.01),
            _entry("e", "f", 0.0123456),
        ],
    }
    picked = taste_benchmark._select_interleaved(candidates, 0)
    assert [pair["match_cost"] for pair in picked["crossed"]] == [0.01, 0.0123, 0.05]
    assert picked["crossed"][0]["high"]["work_id"] == "c"


def test_select_interleaved_respects_the_limit_in_each_stratum_separately():
    candidates = {
        "aligned": [_entry("a", "b", 0.01), _entry("c", "d", 0.02)],
        "crossed": [_entry("e", "f", 0.01), _entry("g", "h", 0.02)],
    }
    picked = taste_benchmark._select_interleaved(candidates, 1)
    assert len(picked["aligned"]) == 1
    assert len(picked["crossed"]) == 1


def test_select_interleaved_fills_aligneds_two_view_sign_buckets_evenly_under_a_limit():
    plus_one = _entry("h1", "l1", 0.01, high_views=200, low_views=100)
    minus_one = _entry("h3", "l3", 0.02, high_views=100, low_views=200)
    plus_two = _entry("h2", "l2", 0.03, high_views=300, low_views=150)
    minus_two = _entry("h4", "l4", 0.04, high_views=90, low_views=180)
    picked = taste_benchmark._select_interleaved(
        {"aligned": [plus_one, minus_one, plus_two, minus_two]}, 2,
    )
    pairs = picked["aligned"]
    assert [(pair["high"]["work_id"], pair["low"]["work_id"]) for pair in pairs] \
        == [("h1", "l1"), ("h3", "l3")]
    assert pairs[0]["high"]["views"] > pairs[0]["low"]["views"]
    assert pairs[1]["high"]["views"] < pairs[1]["low"]["views"]


def test_select_interleaved_of_no_candidates_is_two_empty_strata():
    assert taste_benchmark._select_interleaved({}, 0) == {"aligned": [], "crossed": []}
    empty_lists: dict[str, list[Any]] = {"aligned": [], "crossed": []}
    assert taste_benchmark._select_interleaved(empty_lists, 3) \
        == {"aligned": [], "crossed": []}
