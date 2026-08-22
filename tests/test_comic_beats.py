"""The pure text and arithmetic functions of `comic_beats.py`, pinned on hand-derived cases.

These tests cover only the functions that take values and return values: the counting rule's
normalisation and findability (`normalise`, `relaxed`, `locate`, `score_answer`, `public_beats`),
the sign-test arithmetic (`one_sided_sign_p`, `attainable_p`, `required_k`, `median_ci`,
`paired_reading`), the distribution helpers (`describe`, `percentile_of`, `_ranks`, `spearman`),
and the small classifiers and reducers over result rows (`apply_window`, `hygiene`, `scoreable`,
`strip_subset`, `noise_subset`, `prose_beats`, `certify`, `_kind_mix`, `_length_matched`,
`reliability`, `_headline`, `render`, `digest`, `registration_digest`, `_synthetic_answer`).
Every expected value is stated from the docstring and code before running anything.

What they do not establish: that the instrument measures anything real, that any frozen prompt,
schema or threshold is right, that the arms produce correct numbers, or anything at all about the
code paths that read corpora, results files or caches, call a model, or spawn a process. The one
`selftest()` call is a smoke check that the module's own gate passes; every other assertion here
checks behaviour directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

comic_beats = pytest.importorskip(
    "comic_beats",
    reason="research module; needs the quality-measurement directory on the path",
)

#: A page with the typography models actually retype: curly quotes, an em dash, a bold span.
PAGE = (
    "Silas smiled.\n\n"
    "**TOLL PAID \u2014 9 days**\n\n"
    "\u201cA joke at somebody\u2019s expense,\u201d he said. "
    "He said nothing at all about the toll and walked on through the gate."
)


def _clean_row(unit_id: str, cohort: str, density: float, counted: int = 1) -> dict:
    """A minimal scoreable census row."""
    return {
        "unit_id": unit_id,
        "cohort": cohort,
        "counted": counted,
        "density_per_1k": density,
        "refused": False,
        "unparseable": False,
        "confabulated": 0,
        "relaxed_only": 0,
        "bad_kind": 0,
        "duplicate": 0,
        "over_length": 0,
    }


# ------------------------------------------------------------------------------ digests


def test_digest_is_independent_of_dict_key_order():
    assert comic_beats.digest({"a": 1, "b": [2, 3]}) == comic_beats.digest({"b": [2, 3], "a": 1})


def test_digest_is_a_twenty_character_lowercase_hex_string():
    value = comic_beats.digest({"payload": [1, 2, 3]})
    assert len(value) == 20
    assert value == value.lower()
    int(value, 16)  # must not raise


def test_digest_distinguishes_payloads_that_differ_only_in_a_leaf_value():
    assert comic_beats.digest({"a": 1}) != comic_beats.digest({"a": 2})
    assert comic_beats.digest(1) != comic_beats.digest("1")


def test_registration_digest_is_stable_across_calls_and_twenty_characters():
    first = comic_beats.registration_digest()
    second = comic_beats.registration_digest()
    assert first == second
    assert len(first) == 20


# ------------------------------------------------------------------- normalise and relaxed


def test_normalise_casefolds_and_collapses_whitespace():
    assert comic_beats.normalise("He said NOTHING.") == "he said nothing."
    assert comic_beats.normalise("a\n\n  b") == "a b"


def test_normalise_folds_curly_quotes_dashes_and_ellipsis_to_ascii():
    assert comic_beats.normalise("\u201cHello,\u201d he said\u2026") == '"hello," he said...'
    assert comic_beats.normalise("yes\u2014no") == "yes-no"
    assert comic_beats.normalise("\u2018maybe\u2019") == "'maybe'"


def test_normalise_folds_nbsp_into_a_collapsed_space():
    assert comic_beats.normalise("a\u00a0\u00a0b") == "a b"


def test_normalise_applies_nfkc_so_the_fi_ligature_becomes_plain_letters():
    assert comic_beats.normalise("\ufb01ne") == "fine"


def test_normalise_of_the_empty_string_is_the_empty_string():
    assert comic_beats.normalise("") == ""


def test_relaxed_drops_every_non_alphanumeric_character():
    assert comic_beats.relaxed("He said nothing.") == "hesaidnothing"
    assert comic_beats.relaxed("Room 12\u201314") == "room1214"


def test_relaxed_of_punctuation_only_text_is_empty_and_does_not_crash():
    assert comic_beats.relaxed("!!!") == ""
    assert comic_beats.relaxed("") == ""


# ------------------------------------------------------------------------------- locate

HAYSTACK = "Silas smiled. A joke at somebody's expense, told flat."
HAYSTACK_NORM = comic_beats.normalise(HAYSTACK)
HAYSTACK_RELAXED = comic_beats.relaxed(HAYSTACK)


def test_locate_finds_an_anchor_and_reports_its_offset_in_the_normalised_text():
    found = comic_beats.locate("A JOKE AT SOMEBODY'S EXPENSE", HAYSTACK_NORM, HAYSTACK_RELAXED)
    assert found["findable"] is True
    # "Silas smiled. " is 14 characters of the normalised text.
    assert found["offset"] == 14
    assert found["words"] == 5
    assert found["over_length"] is False


def test_locate_gives_anchors_the_same_hash_when_they_normalise_alike():
    straight = comic_beats.locate("somebody's expense", HAYSTACK_NORM, HAYSTACK_RELAXED)
    curly = comic_beats.locate("somebody\u2019s expense", HAYSTACK_NORM, HAYSTACK_RELAXED)
    assert straight["hash"] == curly["hash"]


def test_locate_reports_an_unfindable_anchor_as_a_negative_offset_and_not_findable():
    found = comic_beats.locate("wholly invented clause", HAYSTACK_NORM, HAYSTACK_RELAXED)
    assert found["offset"] == -1
    assert found["findable"] is False
    assert found["relaxed_findable"] is False


def test_locate_marks_a_punctuation_only_mismatch_relaxed_findable_but_not_strict():
    # The strict needle carries a trailing mark the page does not have; the loose match survives.
    strict_miss = comic_beats.locate("somebody's expense!", HAYSTACK_NORM, HAYSTACK_RELAXED)
    assert strict_miss["findable"] is False
    assert strict_miss["relaxed_findable"] is True


def test_locate_flags_an_anchor_over_twelve_words_and_not_one_of_exactly_twelve():
    twelve = "he said nothing at all about the toll and walked on through"
    thirteen = twelve + " the"
    assert comic_beats.locate(twelve, HAYSTACK_NORM, HAYSTACK_RELAXED)["over_length"] is False
    assert comic_beats.locate(thirteen, HAYSTACK_NORM, HAYSTACK_RELAXED)["over_length"] is True


def test_locate_of_an_empty_anchor_reports_not_findable_without_crashing():
    found = comic_beats.locate("", HAYSTACK_NORM, HAYSTACK_RELAXED)
    assert found["findable"] is False
    assert found["relaxed_findable"] is False
    assert found["offset"] == -1
    assert found["words"] == 0
    assert found["over_length"] is False


# ------------------------------------------------------------------------- score_answer


def _page_payload(entries: list) -> dict:
    return {"beats": entries}


def test_score_answer_counts_findable_anchors_of_known_kinds():
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "A joke at somebody's expense", "kind": "deadpan"},
        {"anchor": "TOLL PAID \u2014 9 days", "kind": "system_voice"},
    ]))
    assert scored["unparseable"] is False
    assert scored["returned"] == 2
    assert scored["counted"] == 2
    assert scored["confabulated"] == 0
    assert scored["by_kind"] == {"deadpan": 1, "system_voice": 1}
    # A straight apostrophe finds a curly-apostrophe page: the fold runs on both sides.
    assert scored["beats"][0]["kind"] == "deadpan"


def test_score_answer_collapses_a_retyped_anchor_to_a_duplicate_not_a_second_beat():
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "A joke at somebody's expense", "kind": "deadpan"},
        {"anchor": "a joke at somebody\u2019s expense", "kind": "quip"},
    ]))
    assert scored["counted"] == 1
    assert scored["duplicate"] == 1


def test_score_answer_counts_an_over_long_findable_anchor_and_reports_the_length():
    long_anchor = "he said nothing at all about the toll and walked on through the"
    assert len(long_anchor.split()) == 13
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": long_anchor, "kind": "quip"},
    ]))
    assert scored["counted"] == 1
    assert scored["over_length"] == 1


def test_score_answer_reports_a_confabulated_anchor_outside_the_count():
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "the sky invented this wholly", "kind": "absurd"},
    ]))
    assert scored["returned"] == 1
    assert scored["counted"] == 0
    assert scored["confabulated"] == 1
    assert scored["relaxed_only"] == 0


def test_score_answer_reports_a_loose_only_match_as_confabulated_and_relaxed_only():
    # Dropping the apostrophe breaks the strict match but not the alphanumeric-only one.
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "A joke at somebodys expense", "kind": "banter"},
    ]))
    assert scored["counted"] == 0
    assert scored["confabulated"] == 1
    assert scored["relaxed_only"] == 1


def test_score_answer_drops_kinds_outside_the_closed_set_into_bad_kind():
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "He said nothing", "kind": "hilarious"},
        "plain junk, not even a dict",
    ]))
    assert scored["counted"] == 0
    assert scored["bad_kind"] == 2
    assert scored["returned"] == 2


def test_score_answer_treats_a_missing_anchor_field_as_a_confabulation_not_a_crash():
    scored = comic_beats.score_answer(PAGE, _page_payload([{"kind": "quip"}]))
    assert scored["counted"] == 0
    assert scored["confabulated"] == 1
    assert scored["returned"] == 1


def test_score_answer_reports_a_payload_without_a_beats_list_as_unparseable():
    for payload in (None, [], {"beats": "no"}, {}):
        scored = comic_beats.score_answer(PAGE, payload)
        assert scored["unparseable"] is True
        assert scored["counted"] == 0
        assert scored["returned"] == 0
        assert scored["beats"] == []


def test_score_answer_reads_an_empty_beats_list_as_a_zero_and_not_a_parse_failure():
    scored = comic_beats.score_answer(PAGE, _page_payload([]))
    assert scored["unparseable"] is False
    assert scored["counted"] == 0
    assert scored["returned"] == 0


# ------------------------------------------------------------------------- public_beats


def test_public_beats_without_quote_carries_offset_words_hash_and_no_anchor_text():
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "Silas smiled.", "kind": "deadpan"},
    ]))
    published = comic_beats.public_beats(scored, quote=False)
    assert published == [{
        "kind": "deadpan",
        "offset": scored["beats"][0]["offset"],
        "words": 2,
        "hash": scored["beats"][0]["hash"],
    }]
    assert "anchor" not in published[0]


def test_public_beats_with_quote_keeps_the_anchor_verbatim():
    scored = comic_beats.score_answer(PAGE, _page_payload([
        {"anchor": "Silas smiled.", "kind": "deadpan"},
    ]))
    published = comic_beats.public_beats(scored, quote=True)
    assert published[0]["anchor"] == "Silas smiled."


def test_public_beats_of_an_answer_with_no_beats_is_an_empty_list_on_both_settings():
    scored = comic_beats.score_answer(PAGE, _page_payload([]))
    assert comic_beats.public_beats(scored, quote=False) == []
    assert comic_beats.public_beats(scored, quote=True) == []


# ------------------------------------------------------------------- the sign-test arithmetic


def test_one_sided_sign_p_of_a_perfect_run_is_exactly_one_over_two_to_the_n():
    assert comic_beats.one_sided_sign_p(8, 8) == 1 / 256


def test_one_sided_sign_p_of_a_five_and_five_split_is_the_enumerated_binomial_tail():
    # P(X >= 5) for X ~ Bin(10, 1/2) = (252 + 210 + 120 + 45 + 10 + 1) / 1024.
    assert comic_beats.one_sided_sign_p(5, 10) == pytest.approx(638 / 1024)


def test_one_sided_sign_p_of_zero_aligned_pairs_is_one():
    assert comic_beats.one_sided_sign_p(0, 10) == 1.0
    assert comic_beats.one_sided_sign_p(0, 0) == 1.0


def test_one_sided_sign_p_clamps_k_into_the_valid_range_without_crashing():
    assert comic_beats.one_sided_sign_p(99, 3) == 1 / 8
    assert comic_beats.one_sided_sign_p(-2, 3) == 1.0


def test_attainable_p_is_one_over_two_to_the_n_and_one_at_zero_pairs():
    assert comic_beats.attainable_p(5) == 1 / 32
    assert comic_beats.attainable_p(1) == 0.5
    assert comic_beats.attainable_p(0) == 1.0


def test_required_k_is_none_below_five_pairs_where_alpha_is_unreachable():
    # At n=4 the smallest attainable p is 1/16 = 0.0625, above alpha 0.05.
    assert comic_beats.required_k(4) is None


def test_required_k_at_the_five_pair_floor_demands_a_unanimous_run():
    # P(X >= 4 | 5) = 6/32 > 0.05 and P(X >= 5 | 5) = 1/32 <= 0.05.
    assert comic_beats.required_k(5) == 5


def test_required_k_at_ten_pairs_demands_nine_of_ten():
    # P(X >= 8 | 10) = 56/1024 ~ 0.0547 > 0.05 and P(X >= 9 | 10) = 11/1024 <= 0.05.
    assert comic_beats.required_k(10) == 9


def test_required_k_at_twenty_pairs_demands_fifteen_of_twenty():
    # P(X >= 14 | 20) = 60460/1048576 ~ 0.0577 and P(X >= 15 | 20) ~ 0.0207.
    assert comic_beats.required_k(20) == 15


def test_median_ci_on_seven_points_spans_the_second_to_sixth_order_statistics():
    # tail 0.05: cumulative 1/128 then 8/128 crosses it, so k=0 and the interval is [x2, x6].
    interval = comic_beats.median_ci([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    assert interval["n"] == 7
    assert interval["median"] == 4.0
    assert interval["lo"] == 2.0
    assert interval["hi"] == 6.0


def test_median_ci_at_full_confidence_spans_the_whole_observed_range():
    interval = comic_beats.median_ci([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], confidence=1.0)
    assert interval["lo"] == 1.0
    assert interval["hi"] == 7.0


def test_median_ci_of_no_values_reports_n_zero_and_no_bounds():
    interval = comic_beats.median_ci([])
    assert interval == {
        "n": 0, "median": None, "lo": None, "hi": None, "confidence": 0.90,
    }


def test_paired_reading_calls_a_unanimous_run_at_the_five_pair_floor_a_positive():
    reading = comic_beats.paired_reading(
        [1.0] * 5, name="t", positive_verdict="UP", null_verdict="NOT_UP",
    )
    assert reading["pairs_decided"] == 5
    assert reading["aligned"] == 5
    assert reading["p_one_sided"] == 0.03125
    assert reading["k_required"] == 5
    assert reading["attainable_floor"] == 0.03125
    assert reading["verdict"] == "UP"


def test_paired_reading_reports_insufficient_n_below_the_five_pair_floor():
    reading = comic_beats.paired_reading(
        [1.0] * 4, name="t", positive_verdict="UP", null_verdict="NOT_UP",
    )
    assert reading["verdict"] == "INSUFFICIENT_N"
    assert reading["k_required"] is None


def test_paired_reading_splits_a_required_k_boundary_between_null_and_positive():
    # required_k(6) is 6, so five aligned pairs of six is not evidence and six of six is.
    five_of_six = comic_beats.paired_reading(
        [1.0, 1.0, 1.0, 1.0, 1.0, -1.0], name="t",
        positive_verdict="UP", null_verdict="NOT_UP",
    )
    assert five_of_six["aligned"] == 5
    assert five_of_six["verdict"] == "NOT_UP"
    six_of_six = comic_beats.paired_reading(
        [1.0] * 6, name="t", positive_verdict="UP", null_verdict="NOT_UP",
    )
    assert six_of_six["verdict"] == "UP"


def test_paired_reading_undecided_pairs_leave_the_denominator_but_stay_in_the_interval():
    reading = comic_beats.paired_reading(
        [0.0, 0.0, 1.0, -1.0, 1.0, 1.0], name="t",
        positive_verdict="UP", null_verdict="NOT_UP",
    )
    assert reading["pairs_total"] == 6
    assert reading["pairs_decided"] == 4
    assert reading["pairs_undecided"] == 2
    # P(X >= 3 | 4) = 5/16, and four decided pairs cannot clear alpha.
    assert reading["p_one_sided"] == pytest.approx(5 / 16)
    assert reading["verdict"] == "INSUFFICIENT_N"
    assert reading["equivalence_bound"]["n"] == 6


def test_paired_reading_names_a_mixed_majority_with_the_null_verdict():
    reading = comic_beats.paired_reading(
        [1.0, -1.0, 1.0, -1.0, 1.0, 1.0], name="t",
        positive_verdict="UP", null_verdict="NOT_UP",
    )
    assert reading["aligned"] == 4
    assert reading["verdict"] == "NOT_UP"


# ------------------------------------------------------------------------------ jaccard


def test_jaccard_of_identical_anchor_sets_in_any_order_is_one():
    assert comic_beats.jaccard(["a", "b"], ["b", "a"]) == 1.0


def test_jaccard_of_disjoint_anchor_sets_is_zero():
    assert comic_beats.jaccard(["a"], ["b"]) == 0.0


def test_jaccard_of_partially_overlapping_sets_is_the_intersection_over_the_union():
    assert comic_beats.jaccard(["a", "b", "c"], ["b", "c", "d"]) == 0.5


def test_jaccard_collapses_repeats_within_a_side_before_comparing():
    assert comic_beats.jaccard(["a", "a", "b"], ["b"]) == 0.5


def test_jaccard_of_two_empty_sets_is_none_but_one_empty_side_is_zero():
    assert comic_beats.jaccard([], []) is None
    assert comic_beats.jaccard([], ["a"]) == 0.0


# ------------------------------------------------------------- describe and percentile_of


def test_describe_reports_n_mean_sd_and_the_nearest_rank_median():
    summary = comic_beats.describe([2.0, 4.0, 6.0])
    assert summary["n"] == 3
    assert summary["mean"] == 4.0
    assert summary["sd"] == pytest.approx(1.633, abs=1e-3)
    assert summary["min"] == 2.0
    assert summary["max"] == 6.0
    assert summary["quantiles"]["0.5"] == 4.0


def test_describe_of_no_values_is_n_zero_and_nothing_else():
    assert comic_beats.describe([]) == {"n": 0}


def test_percentile_of_is_the_share_of_the_population_at_or_below_the_value():
    assert comic_beats.percentile_of(5.0, [1.0, 5.0, 9.0]) == pytest.approx(66.7)
    assert comic_beats.percentile_of(0.5, [1.0, 2.0, 3.0, 4.0]) == 0.0
    assert comic_beats.percentile_of(99.0, [1.0, 2.0, 3.0, 4.0]) == 100.0


def test_percentile_of_an_empty_population_is_none():
    assert comic_beats.percentile_of(1.0, []) is None


# ---------------------------------------------------------------------- _synthetic_answer

TWELVE_WORDS = "one two three four five six seven eight nine ten eleven twelve"


def test_synthetic_answer_draws_a_deterministic_answer_from_the_key_alone():
    first = comic_beats._synthetic_answer("00000004abc", TWELVE_WORDS)
    second = comic_beats._synthetic_answer("00000004abc", TWELVE_WORDS)
    assert first == second
    payload = json.loads(first)
    # marker = 0x4: marker % 9 beats, kinds drawn from the closed set either way.
    assert len(payload["beats"]) == 4
    for beat in payload["beats"]:
        assert beat["kind"] in comic_beats.KINDS


def test_synthetic_answer_mixes_real_spans_and_invented_ones_by_the_key_bits():
    # marker = 1 has its low bit set, so its single anchor is a real span of the text;
    # marker = 2 has a clear low bit and a set next bit, so it is one invented then one real.
    real_payload = json.loads(comic_beats._synthetic_answer("00000001", TWELVE_WORDS))
    assert real_payload["beats"] == [
        {"anchor": "two three four five six seven", "kind": comic_beats.KINDS[1]},
    ]
    mixed = json.loads(comic_beats._synthetic_answer("00000002", TWELVE_WORDS))
    assert "(dry run) no such span" in mixed["beats"][0]["anchor"]
    assert mixed["beats"][1]["anchor"] == "two three four five six seven"


def test_synthetic_answer_with_a_key_whose_marker_is_a_multiple_of_nine_is_an_empty_list():
    assert json.loads(comic_beats._synthetic_answer("00000009", TWELVE_WORDS)) == {"beats": []}


def test_synthetic_answer_on_text_shorter_than_nine_words_clamps_its_span_without_crashing():
    answer = comic_beats._synthetic_answer("00000001", "only three words")
    payload = json.loads(answer)
    assert payload["beats"][0]["anchor"] == "only three words"


# ---------------------------------------------------------------------------- apply_window


def test_apply_window_keeps_units_at_exactly_the_window_edges():
    kept, excluded = comic_beats.apply_window([
        {"unit_id": "floor", "words": 800},
        {"unit_id": "ceiling", "words": 6000},
    ])
    assert [unit["unit_id"] for unit in kept] == ["floor", "ceiling"]
    assert excluded == []


def test_apply_window_reports_each_outside_unit_with_its_side_of_the_window():
    kept, excluded = comic_beats.apply_window([
        {"unit_id": "short", "words": 799},
        {"unit_id": "long", "words": 6001},
        {"unit_id": "fits", "words": 2000},
    ])
    assert [unit["unit_id"] for unit in kept] == ["fits"]
    assert excluded == [
        {"unit_id": "short", "words": 799, "reason": "below_min"},
        {"unit_id": "long", "words": 6001, "reason": "above_max"},
    ]


def test_apply_window_of_no_units_returns_two_empty_lists():
    assert comic_beats.apply_window([]) == ([], [])


# ------------------------------------------------------------------------------- hygiene


def test_hygiene_sums_the_drop_categories_and_rates_them_over_returned_anchors():
    rows = [
        {"returned": 4, "confabulated": 1, "relaxed_only": 1, "bad_kind": 0,
         "duplicate": 0, "over_length": 0, "unparseable": False, "refused": False},
        {"returned": 2, "confabulated": 1, "relaxed_only": 0, "bad_kind": 1,
         "duplicate": 0, "over_length": 0, "unparseable": True, "refused": False},
        {"returned": 0, "confabulated": 0, "relaxed_only": 0, "bad_kind": 0,
         "duplicate": 0, "over_length": 0, "unparseable": False, "refused": True},
    ]
    report = comic_beats.hygiene(rows)
    assert report["units"] == 3
    assert report["anchors_returned"] == 6
    assert report["confabulated"] == 2
    assert report["confabulation_rate"] == pytest.approx(0.3333)
    assert report["confabulated_per_unit"] == pytest.approx(0.6667)
    assert report["relaxed_only"] == 1
    assert report["bad_kind"] == 1
    assert report["unparseable_units"] == 1
    assert report["refused_units"] == 1


def test_hygiene_reports_no_confabulation_rate_when_no_anchor_was_returned():
    empty_arm = comic_beats.hygiene([])
    assert empty_arm["units"] == 0
    assert empty_arm["confabulation_rate"] is None
    assert empty_arm["confabulated_per_unit"] is None
    refused_only = comic_beats.hygiene([
        {"returned": 0, "confabulated": 0, "relaxed_only": 0, "bad_kind": 0,
         "duplicate": 0, "over_length": 0, "unparseable": False, "refused": True},
    ])
    assert refused_only["units"] == 1
    assert refused_only["confabulation_rate"] is None


def test_hygiene_gives_a_clean_arm_a_zero_rate_and_not_none():
    clean = comic_beats.hygiene([
        {"returned": 5, "confabulated": 0, "relaxed_only": 0, "bad_kind": 0,
         "duplicate": 0, "over_length": 0, "unparseable": False, "refused": False},
    ])
    assert clean["confabulation_rate"] == 0.0


# ----------------------------------------------------------------------------- scoreable


def test_scoreable_keeps_rows_that_neither_refused_nor_failed_to_parse():
    good = {"unit_id": "good", "refused": False, "unparseable": False}
    result = {
        "rows": [
            good,
            {"unit_id": "refused", "refused": True, "unparseable": False},
            {"unit_id": "garbage", "refused": False, "unparseable": True},
        ],
    }
    assert comic_beats.scoreable(result) == [good]


def test_scoreable_of_an_arm_with_no_rows_is_an_empty_list():
    assert comic_beats.scoreable({"rows": []}) == []


# --------------------------------------------------------------------------- strip_subset


def test_strip_subset_on_royalroad_takes_the_top_decile_by_located_density():
    census = {
        "substrate": "royalroad",
        "rows": [_clean_row(f"rr-{i:02d}", "cohort", density=float(i)) for i in range(20)],
    }
    # round(0.10 * 20) = 2, and the two densest chapters are rr-19 and rr-18.
    assert comic_beats.strip_subset(census) == ["rr-18", "rr-19"]


def test_strip_subset_on_royalroad_breaks_density_ties_by_unit_id():
    census = {
        "substrate": "royalroad",
        "rows": [_clean_row(unit_id, "c", density=1.0)
                 for unit_id in ("u-b", "u-a", "u-c", "u-d", "u-e",
                                 "u-f", "u-g", "u-h", "u-i", "u-j")],
    }
    assert comic_beats.strip_subset(census) == ["u-a"]


def test_strip_subset_on_royalroad_takes_nothing_from_fewer_than_ten_chapters():
    census = {
        "substrate": "royalroad",
        "rows": [_clean_row(f"rr-{i}", "cohort", density=float(i)) for i in range(4)],
    }
    assert comic_beats.strip_subset(census) == []


def test_strip_subset_off_royalroad_takes_own_units_at_or_above_three_counted_beats():
    census = {
        "substrate": "local",
        "rows": [
            _clean_row("own-rich", "own_chapter", density=3.0, counted=3),
            _clean_row("own-poor", "own_chapter", density=1.0, counted=2),
        ],
    }
    assert comic_beats.strip_subset(census) == ["own-rich"]


# --------------------------------------------------------------------------- noise_subset


def test_noise_subset_off_royalroad_is_every_scoreable_unit_id_sorted():
    census = {
        "substrate": "local",
        "rows": [
            _clean_row("z-unit", "own_chapter", density=1.0),
            _clean_row("a-unit", "own_chapter", density=2.0),
            _clean_row("skipped", "own_chapter", density=3.0, counted=0),
        ],
    }
    census["rows"][2]["unparseable"] = True
    assert comic_beats.noise_subset(census) == ["a-unit", "z-unit"]


def test_noise_subset_on_royalroad_draws_each_cohort_and_folds_in_the_strip_subset():
    # Two cohorts of one: each cohort's share round(40 * 1 / 2) covers its only member,
    # and the strip subset (round(0.10 * 2) = 0 chapters) adds nothing.
    census = {
        "substrate": "royalroad",
        "rows": [
            _clean_row("m1", "early", density=1.0),
            _clean_row("m2", "late", density=2.0),
        ],
    }
    assert comic_beats.noise_subset(census) == ["m1", "m2"]


def test_noise_subset_on_royalroad_applies_the_share_so_a_cohort_can_lose_members():
    # 50 scoreable rows: cohort "a" holds 3, so its share is round(40 * 3 / 50) = 2 and it
    # keeps only the two members with the smallest digest of their unit ids. The five densest
    # chapters are all in cohort "b", so the strip subset folds nothing back into cohort "a".
    a_ids = ["a-1", "a-2", "a-3"]
    rows = [_clean_row(unit_id, "a", density=1.0) for unit_id in a_ids]
    for i in range(47):
        rows.append(_clean_row(f"b-{i:02d}", "b", density=100.0 if i < 5 else 1.0))
    census = {"substrate": "royalroad", "rows": rows}
    noise = comic_beats.noise_subset(census)
    survivors = [unit_id for unit_id in a_ids if unit_id in noise]
    assert len(survivors) == 2
    assert survivors == sorted(a_ids, key=comic_beats.digest)[:2]
    # And the five densest chapters of cohort "b" ride in with the strip subset.
    assert {f"b-{i:02d}" for i in range(5)} <= set(noise)


def test_noise_subset_on_royalroad_carries_every_strip_unit_even_when_its_cohort_did_not():
    # 80 rows: cohort "a" holds only m1, whose share round(40 * 1 / 80) = round(0.5) = 0,
    # so only the fold-in can put m1 in the noise subset -- and m1 is the densest chapter,
    # hence the whole strip subset's reason to exist.
    rows = [_clean_row("m1", "a", density=999.0)]
    rows += [_clean_row(f"b-{i:02d}", "b", density=1.0) for i in range(79)]
    census = {"substrate": "royalroad", "rows": rows}
    noise = comic_beats.noise_subset(census)
    assert "m1" in noise
    assert noise == sorted(noise)
    assert set(noise) <= {row["unit_id"] for row in rows}


def test_noise_subset_of_an_arm_with_no_scoreable_rows_is_empty():
    assert comic_beats.noise_subset({"substrate": "royalroad", "rows": []}) == []


# ---------------------------------------------------------------------------- prose_beats


def test_prose_beats_subtracts_the_system_voice_beats_the_contract_cannot_touch():
    row = {"counted": 5, "by_kind": {"quip": 2, "system_voice": 2}}
    assert comic_beats.prose_beats(row) == 3


def test_prose_beats_of_a_row_with_no_system_voice_kind_is_the_whole_count():
    assert comic_beats.prose_beats({"counted": 5, "by_kind": {"quip": 5}}) == 5


def test_prose_beats_of_an_all_system_voice_count_is_zero():
    assert comic_beats.prose_beats({"counted": 2, "by_kind": {"system_voice": 2}}) == 0


# ------------------------------------------------------------------------------- certify


def test_certify_passes_an_unchanged_revision_with_a_full_similarity_and_zero_growth():
    report = comic_beats.certify("a b c d e f g h", "a b c d e f g h")
    assert report["certified"] is True
    assert report["similarity"] == 1.0
    assert report["word_growth_pct"] == 0.0
    assert report["reasons"] == []


def test_certify_fails_a_wholesale_rewrite_on_similarity():
    report = comic_beats.certify("a b c d e f g h", "z y x w v u t s")
    assert report["certified"] is False
    assert any("similarity" in reason for reason in report["reasons"])


def test_certify_accepts_growth_of_exactly_twelve_percent_and_no_more():
    original = " ".join(f"w{i:02d}" for i in range(50))
    at_bound = original + " " + " ".join(f"x{i:02d}" for i in range(6))
    over_bound = original + " " + " ".join(f"x{i:02d}" for i in range(7))
    assert comic_beats.certify(original, at_bound)["word_growth_pct"] == pytest.approx(12.0)
    assert comic_beats.certify(original, at_bound)["certified"] is True
    beyond = comic_beats.certify(original, over_bound)
    assert beyond["certified"] is False
    assert any("growth" in reason for reason in beyond["reasons"])


def test_certify_fails_when_a_protected_system_voice_span_was_mangled():
    mangled = comic_beats.certify(
        "**TOLL PAID \u2014 9 days**\n\nHe left.", "**TOLL PAID \u2013 9 days**\n\nHe left.",
    )
    assert mangled["protected_spans"] == 1
    assert mangled["protected_kept"] == 0
    assert mangled["certified"] is False
    assert any("protected spans" in reason for reason in mangled["reasons"])


def test_certify_passes_a_revision_that_preserves_its_protected_span_byte_for_byte():
    report = comic_beats.certify(
        "**TOLL PAID \u2014 9 days**\n\nHe left.",
        "**TOLL PAID \u2014 9 days**\n\nHe went.",
    )
    assert report["protected_spans"] == 1
    assert report["protected_kept"] == 1
    assert report["word_growth_pct"] == 0.0
    assert report["certified"] is True


def test_certify_of_two_empty_texts_certifies_without_crashing():
    report = comic_beats.certify("", "")
    assert report["certified"] is True
    assert report["word_growth_pct"] == 0.0


# ----------------------------------------------------------------------- ranks and spearman


def test_ranks_order_distinct_values_by_their_position():
    assert comic_beats._ranks([30.0, 10.0, 20.0]) == [3.0, 1.0, 2.0]


def test_ranks_split_tied_positions_as_the_average_of_their_places():
    assert comic_beats._ranks([10.0, 20.0, 20.0, 30.0]) == [1.0, 2.5, 2.5, 4.0]


def test_ranks_of_no_values_is_empty_and_of_one_value_is_rank_one():
    assert comic_beats._ranks([]) == []
    assert comic_beats._ranks([5.0]) == [1.0]


def test_spearman_scores_a_perfect_monotone_rise_one_and_a_fall_minus_one():
    assert comic_beats.spearman([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]) == 1.0
    assert comic_beats.spearman([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) == -1.0


def test_spearman_of_a_non_monotone_pair_is_its_rank_correlation():
    # Ranks x = [1, 2, 3], y = [1, 3, 2]: numerator 1 over a denominator of 2.
    assert comic_beats.spearman([1.0, 2.0, 3.0], [1.0, 3.0, 2.0]) == 0.5


def test_spearman_returns_none_for_too_few_pairs_length_mismatch_or_a_constant_side():
    assert comic_beats.spearman([1.0, 2.0], [1.0, 2.0]) is None
    assert comic_beats.spearman([1.0, 2.0, 3.0], [1.0, 2.0]) is None
    assert comic_beats.spearman([1.0, 2.0, 3.0], [7.0, 7.0, 7.0]) is None


# ------------------------------------------------------------------------------ _kind_mix


def test_kind_mix_totals_each_kind_across_rows_and_shares_them_over_the_grand_total():
    mix = comic_beats._kind_mix([
        {"by_kind": {"quip": 2, "banter": 1}},
        {"by_kind": {"quip": 1}},
    ])
    assert mix["total"] == 4
    assert mix["counts"]["quip"] == 3
    assert mix["counts"]["banter"] == 1
    assert mix["share"]["quip"] == 0.75
    assert mix["share"]["banter"] == 0.25
    # Kinds nobody located still appear, at zero, because the set is closed.
    assert mix["counts"]["callback"] == 0
    assert mix["share"]["callback"] == 0.0


def test_kind_mix_of_no_rows_reports_a_zero_total_and_an_empty_share_map():
    mix = comic_beats._kind_mix([])
    assert mix["total"] == 0
    assert mix["share"] == {}


# --------------------------------------------------------------------------- _length_matched


def _population_row(unit_id: str, words: int, density: float) -> dict:
    return {"unit_id": unit_id, "words": words, "density_per_1k": density}


def test_length_matched_compares_only_chapters_inside_the_thirty_percent_band():
    row = {"unit_id": "own", "words": 1000, "density_per_1k": 5.0}
    population = [
        _population_row("at-low-edge", 700, 1.0),   # exactly 1000 * (1 - 0.30)
        _population_row("just-below", 699, 8.0),
        _population_row("inside", 1000, 5.0),
        _population_row("at-high-edge", 1300, 9.0),  # exactly 1000 * (1 + 0.30)
        _population_row("just-above", 1301, 2.0),
    ]
    report = comic_beats._length_matched(row, population)
    assert report["band_words"] == [700, 1300]
    assert report["n"] == 3
    assert report["percentile"] == pytest.approx(66.7)
    assert report["summary"]["n"] == 3


def test_length_matched_with_no_population_in_its_band_reports_no_percentile():
    row = {"unit_id": "own", "words": 1000, "density_per_1k": 5.0}
    report = comic_beats._length_matched(row, [_population_row("far", 5000, 1.0)])
    assert report["n"] == 0
    assert report["percentile"] is None
    assert report["summary"] == {"n": 0}


# ----------------------------------------------------------------------------- reliability


def _census_of(densities: list[float]) -> dict:
    return {
        "substrate": "local",
        "rows": [
            _clean_row(f"u-{i}", "own_chapter", density=density)
            for i, density in enumerate(densities)
        ],
    }


def _repeat_payload(signed_counts: list[tuple[int, int]]) -> dict:
    return {
        "arm": "repeat",
        "pairs": [
            {"words": 1000, "census_counted": before, "repeat_counted": after}
            for before, after in signed_counts
        ],
    }


def test_reliability_splits_observed_variance_into_noise_and_a_true_part():
    # densities [0, 3]: observed sd 1.5. Pairs move by 0 and 2 beats/1k: difference sd 1.0,
    # so noise sd is 1/sqrt(2), true variance is 2.25 - 0.5 and reliability is 7/9.
    report = comic_beats.reliability(
        _census_of([0.0, 3.0]), _repeat_payload([(1, 1), (1, 3)]),
    )
    assert report["repeat_pairs"] == 2
    assert report["sd_of_paired_difference"] == pytest.approx(1.0)
    assert report["sd_single_measurement_noise"] == pytest.approx(0.7071, abs=1e-4)
    assert report["sd_population_observed"] == pytest.approx(1.5)
    assert report["sd_population_implied_true"] == pytest.approx(1.3229, abs=1e-4)
    assert report["reliability"] == pytest.approx(0.7778, abs=1e-4)
    assert report["correlation_ceiling"] == pytest.approx(0.8819, abs=1e-4)
    # r ~ 0.778: two averaged draws reach 0.8, three reach 0.9.
    assert report["draws_to_reach"]["0.8"] == 2
    assert report["draws_to_reach"]["0.9"] == 3


def test_reliability_clamps_the_implied_true_sd_at_zero_when_noise_exceeds_signal():
    report = comic_beats.reliability(
        _census_of([0.0, 3.0]), _repeat_payload([(1, 401), (1, 1)]),
    )
    assert report["sd_population_implied_true"] == 0.0
    assert report["correlation_ceiling"] == 0.0


def test_reliability_of_zero_paired_difference_is_a_perfect_one_point_zero():
    report = comic_beats.reliability(
        _census_of([0.0, 3.0]), _repeat_payload([(1, 1), (2, 2)]),
    )
    assert report["reliability"] == 1.0
    assert report["correlation_ceiling"] == 1.0
    assert report["draws_to_reach"]["0.8"] is None


def test_reliability_refuses_to_compute_without_two_densities_or_a_repeat_arm():
    one_row = _census_of([1.0])
    assert comic_beats.reliability(one_row, _repeat_payload([(1, 1)]))["verdict"] \
        == "NOT_COMPUTED"
    assert comic_beats.reliability(_census_of([1.0, 2.0]), None)["verdict"] == "NOT_COMPUTED"
    assert comic_beats.reliability(_census_of([1.0, 2.0]), {"arm": "repeat", "pairs": []})[
        "verdict"
    ] == "NOT_COMPUTED"


def test_reliability_needs_at_least_two_repeat_pairs_to_compute():
    census = _census_of([0.0, 3.0])
    report = comic_beats.reliability(census, _repeat_payload([(1, 3)]))
    assert report == {
        "verdict": "NOT_COMPUTED", "because": "fewer than two repeat pairs",
    }


# ------------------------------------------------------------------------------- _headline


def test_headline_renders_one_sentence_per_question_with_the_numbers_in_place():
    q1 = {"pooled": {"n": 249, "mean": 3.1,
                     "quantiles": {"0.5": 2.5, "0.95": 9.0}, "max": 12.0}}
    q2 = {"chapters": [{
        "unit_id": "reappraisal:Chapter_01", "density_per_1k": 2.9,
        "percentile_pooled": 61.0,
        "length_matched": {"percentile": 55.0, "n": 34},
    }]}
    q3 = {"royalroad": {
        "sham_vs_repeat": {"verdict": "LAYOUT_SEES"},
        "strip": {"against_placebo": {"verdict": "SEES"},
                  "refusal_state": {"verdict": "READABLE"}},
    }}
    headline = comic_beats._headline(q1, q2, q3)
    assert headline["q1"] == (
        "RoyalRoad LitRPG located levity runs at a median of 2.5 beats per 1,000 words over "
        "249 chapters (mean 3.1, p95 9.0, max 12.0)."
    )
    assert headline["q2"] == [
        "reappraisal:Chapter_01: 2.9/1k, 61.0th percentile pooled, "
        "55.0th among chapters of comparable length (n=34)."
    ]
    assert headline["q3"]["royalroad"] == {
        "sham": "LAYOUT_SEES", "strip_vs_placebo": "SEES", "strip_refusal": "READABLE",
    }
    # The field opens mid-sentence on purpose: it reads as "this is not ... a quality claim".
    assert "quality claim" in headline["what_this_is_not"]
    assert "not measured here" in headline["what_this_is_not"]


def test_headline_of_sparse_questions_reports_nones_and_empty_lists_without_crashing():
    headline = comic_beats._headline({"pooled": {}}, {"chapters": []}, {})
    assert headline["q2"] == []
    assert headline["q3"] == {}
    assert "None" in headline["q1"]


# ---------------------------------------------------------------------------------- render


def _render_payload() -> dict:
    return {
        "arm": "sham", "substrate": "local", "model": "panel-x", "transport": "cli",
        "dry_run": True, "transport_failures": 2,
        "failure_reasons": {"FileNotFoundError": 2}, "api_calls": 3, "replayed": 1,
        "spend": {"equivalent_usd": 0.5}, "hygiene": {"units": 2},
        "summary": {"pairs": 2},
        "rows": [
            {"density_per_1k": 2.5, "refused": False},
            {"density_per_1k": 9.9, "refused": True},
        ],
    }


def test_render_prints_transport_failures_hygiene_summary_and_scored_density_only(
    capsys,
):
    comic_beats.render(_render_payload())
    out = capsys.readouterr().out
    # Transport failures lead, per the runbook.
    assert "arm sham on local" in out
    assert "DRY RUN" in out
    assert "transport failures 2" in out
    assert "FileNotFoundError" in out
    assert '"units": 2' in out
    assert '"pairs": 2' in out
    # The refused row's density is not a datum and must not appear in the distribution.
    density_line = next(line for line in out.splitlines() if "density/1k" in line)
    assert '"n": 1' in density_line
    assert "2.5" in density_line
    assert "9.9" not in density_line


def test_render_of_a_payload_with_no_rows_or_summaries_prints_the_header_lines_only(capsys):
    comic_beats.render({
        "arm": "census", "substrate": "royalroad", "model": None,
        "transport": "sdk", "dry_run": False,
    })
    out = capsys.readouterr().out
    assert "arm census on royalroad" in out
    assert "density/1k" not in out
    assert "summary" not in out


# ------------------------------------------------------------------------------- selftest


def test_the_module_selftest_passes():
    assert comic_beats.selftest() == 0
