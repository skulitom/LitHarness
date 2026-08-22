"""Pins the pure arithmetic of the FX transmission-chain measures, derived by hand.

What is pinned: the deterministic extractors (`content_words`, `skeleton`), the decay measures
built on them (`skeleton_retention`, `mutation_rate`), the register-ratio measure
(`style_retention`), the basin-convergence ratio (`attractor`), the kill-condition classifier
(`saturated`), the per-side reduction (`measure_side`), and the module selftest. Every expected
value below is computed from the functions' docstrings and code before running, using a
single-feature z-scale (`comma_per_1k`) so distances reduce to one readable number.

What is *not* established: that chains run (`run_chain` samples a model through `force_gpu`),
that any corpus, results file, database or checkpoint is read, that retellings actually decay,
or that the pilot's kill conditions fire on real data. The surface-count feature space itself
(`authorship_tells.features`, `register_halflife.z_distance`) is treated as given here; it has
its own coverage. Nothing here pins the value or ordering of a module-level constant.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

transmission_chains = pytest.importorskip(
    "transmission_chains",
    reason="research module; needs the quality-measurement directory on the path",
)

# A z-scale with spread on exactly one feature makes every z-distance in this file the absolute
# difference of that feature's two values, so each expected number below is hand-computable.
# Anchors need no other keys: z_distance skips every feature whose sd is zero or missing.
COMMA_SCALE = {"comma_per_1k": 1.0}


def prose(seed: str, commas: int, words: int) -> str:
    """`words` whitespace-separated tokens, the first `commas` of them comma-suffixed."""
    tokens = [f"{seed}{i}" for i in range(words)]
    for i in range(commas):
        tokens[i] += ","
    return " ".join(tokens)


# ------------------------------------------------------------------------------- content_words


def test_content_words_lowercases_strips_stopwords_and_keeps_order_and_duplicates():
    assert transmission_chains.content_words("The cat and the DOG dog") == ["cat", "dog", "dog"]


def test_content_words_on_an_empty_string_is_empty():
    assert transmission_chains.content_words("") == []


def test_content_words_finds_nothing_in_text_without_letter_initial_tokens():
    assert transmission_chains.content_words("123 456?! ...; :") == []


def test_content_words_keeps_contracted_and_hyphenated_tokens_whole():
    # Both apostrophes: the module deliberately handles U+2019 because RoyalRoad uses it.
    assert transmission_chains.content_words("Don't well-known don’t") == [  # noqa: RUF001
        "don't",
        "well-known",
        "don’t",  # noqa: RUF001
    ]


# ------------------------------------------------------------------------------------ skeleton


def test_skeleton_takes_the_most_frequent_content_words_up_to_size():
    text = "cat cat cat dog dog bird"
    # bird is below the cut at size 2 and above it at size 3: both sides of the rank boundary.
    assert transmission_chains.skeleton(text, size=2) == {"cat", "dog"}
    assert transmission_chains.skeleton(text, size=3) == {"cat", "dog", "bird"}


def test_skeleton_of_empty_or_all_stopword_text_is_empty():
    assert transmission_chains.skeleton("", size=5) == set()
    assert transmission_chains.skeleton("the the of and", size=5) == set()


def test_skeleton_returns_every_distinct_content_word_when_size_exceeds_vocabulary():
    assert transmission_chains.skeleton("alpha beta alpha", size=40) == {"alpha", "beta"}


def test_skeleton_never_contains_a_stopword_however_often_it_occurs():
    assert "the" not in transmission_chains.skeleton("the cat cat the the dog", size=40)


# -------------------------------------------------------------------------- skeleton_retention


def test_skeleton_retention_of_identical_text_is_one():
    text = "apple banana cherry date"
    assert transmission_chains.skeleton_retention(text, text) == 1.0


def test_skeleton_retention_is_the_recall_share_of_bones_present():
    # Bones are {apple, banana, cherry, date}; the retelling keeps two and adds three new
    # words, which must not raise recall: it is a share of bones, not of the retelling.
    original = "apple banana cherry date"
    retold = "apple banana x y z"
    assert transmission_chains.skeleton_retention(original, retold) == pytest.approx(0.5)


def test_skeleton_retention_with_no_overlap_is_zero():
    original = "apple banana cherry date"
    retold = "nothing whatsoever survives here"
    assert transmission_chains.skeleton_retention(original, retold) == 0.0


def test_skeleton_retention_with_an_empty_original_is_zero():
    assert transmission_chains.skeleton_retention("", "anything at all") == 0.0
    assert transmission_chains.skeleton_retention("", "") == 0.0


def test_skeleton_retention_with_an_empty_retold_is_zero():
    assert transmission_chains.skeleton_retention("apple banana cherry date", "") == 0.0


# ------------------------------------------------------------------------------- mutation_rate


def test_mutation_rate_of_identical_text_is_zero():
    text = "alpha beta gamma"
    assert transmission_chains.mutation_rate(text, text) == 0.0


def test_mutation_rate_is_one_minus_the_jaccard_overlap():
    # Sets {alpha, beta, gamma} and {alpha, beta, delta}: union 4, intersection 2, rate 1/2.
    assert transmission_chains.mutation_rate("alpha beta gamma", "alpha beta delta") == 0.5


def test_mutation_rate_of_disjoint_vocabulary_is_one():
    assert transmission_chains.mutation_rate("alpha beta", "gamma delta") == 1.0


def test_mutation_rate_ignores_case_and_stopwords():
    assert transmission_chains.mutation_rate("The Cat", "cat THE") == 0.0


def test_mutation_rate_with_both_texts_empty_is_zero():
    assert transmission_chains.mutation_rate("", "") == 0.0


def test_mutation_rate_with_one_empty_side_is_full_mutation():
    assert transmission_chains.mutation_rate("", "word") == 1.0
    assert transmission_chains.mutation_rate("word", "") == 1.0


# ----------------------------------------------------------------------------- style_retention


def test_style_retention_exceeds_one_half_when_text_sits_nearer_its_origin():
    # Text has comma_per_1k = 125 (8 words, 1 comma). Distance to an origin at 0 is 125, to a
    # median at 375 is 250, so the voice survived: 250 / 375 = 2/3, above the 0.5 line.
    text = prose("w", commas=1, words=8)
    origin = {"comma_per_1k": 0.0}
    median = {"comma_per_1k": 375.0}
    result = transmission_chains.style_retention(text, origin, median, COMMA_SCALE)
    assert result == pytest.approx(2 / 3)


def test_style_retention_below_one_half_when_text_sits_nearer_the_model_median():
    # Same text, anchors swapped: now the median is the near pole, so the voice is lost.
    text = prose("w", commas=1, words=8)
    origin = {"comma_per_1k": 375.0}
    median = {"comma_per_1k": 0.0}
    result = transmission_chains.style_retention(text, origin, median, COMMA_SCALE)
    assert result == pytest.approx(1 / 3)


def test_style_retention_is_exactly_one_half_at_equal_distance_to_both_anchors():
    text = prose("w", commas=1, words=8)
    origin = {"comma_per_1k": 0.0}
    median = {"comma_per_1k": 250.0}
    assert transmission_chains.style_retention(text, origin, median, COMMA_SCALE) == 0.5


def test_style_retention_returns_one_half_when_the_z_scale_has_no_spread():
    # No feature contributes, so neither anchor can be nearer; this must degrade to the
    # neutral 0.5 rather than divide by zero — anchors may even be missing every key.
    text = prose("w", commas=3, words=8)
    assert transmission_chains.style_retention(text, {}, {}, {}) == 0.5
    assert transmission_chains.style_retention("", {}, {}, {}) == 0.5


def test_style_retention_handles_an_empty_text_without_crashing():
    # An empty text produces no windows, so the fallback single feature row is used; its
    # comma rate is 0, sitting exactly on the origin and maximally far from the median.
    origin = {"comma_per_1k": 0.0}
    median = {"comma_per_1k": 250.0}
    assert transmission_chains.style_retention("", origin, median, COMMA_SCALE) == 1.0


# ----------------------------------------------------------------------------------- attractor


def test_attractor_ratio_exceeds_one_when_sides_differ_more_than_chains_within_a_side():
    # Rates: high side 0 and 0, low side 200 and 400 (10-word texts, so each comma is 100).
    # Within: (0 + 200) / 2 = 100. Between: (200 + 400 + 200 + 400) / 4 = 300. Ratio 3.0.
    high_hop = [prose("ha", 0, 10), prose("hb", 0, 10)]
    low_hop = [prose("la", 2, 10), prose("lb", 4, 10)]
    out = transmission_chains.attractor([high_hop], [low_hop], {}, COMMA_SCALE)
    assert out == [{"hop": 0, "within_side": 100.0, "between_side": 300.0, "ratio": 3.0}]


def test_attractor_ratio_drops_below_one_when_chains_within_a_side_diverge_more():
    # Rates: high side 0 and 600, low side 250 and 350 (20-word texts, each comma worth 50).
    # Within: (600 + 100) / 2 = 350. Between: (250 + 350 + 350 + 250) / 4 = 300. Ratio 6/7.
    high_hop = [prose("ha", 0, 20), prose("hb", 12, 20)]
    low_hop = [prose("la", 5, 20), prose("lb", 7, 20)]
    out = transmission_chains.attractor([high_hop], [low_hop], {}, COMMA_SCALE)
    assert out == [{"hop": 0, "within_side": 350.0, "between_side": 300.0, "ratio": 0.8571}]


def test_attractor_reports_a_nan_ratio_when_no_chain_differs_within_either_side():
    # Four distinct texts, identical comma rates: within collapses to zero and the ratio is
    # undefined. This is the degenerate value the function must survive, not crash on.
    hop = [prose(f"s{i}", 0, 10) for i in range(4)]
    out = transmission_chains.attractor([hop[:2]], [hop[2:]], {}, COMMA_SCALE)
    assert out[0]["hop"] == 0
    assert out[0]["within_side"] == 0.0
    assert out[0]["between_side"] == 0.0
    assert math.isnan(out[0]["ratio"])


def test_attractor_labels_every_hop_in_order():
    high_hop = [prose("ha", 0, 10), prose("hb", 0, 10)]
    low_hop = [prose("la", 2, 10), prose("lb", 4, 10)]
    out = transmission_chains.attractor([high_hop, high_hop], [low_hop, low_hop], {}, COMMA_SCALE)
    assert [row["hop"] for row in out] == [0, 1]


# ---------------------------------------------------------------------------------- saturated


def curve(values: list[float]) -> list[dict[str, float]]:
    """A hop curve whose three measures all carry the same value at each hop."""
    return [{"skeleton": v, "style": v, "mutation": v} for v in values]


def test_saturated_true_when_every_measure_is_flat():
    assert transmission_chains.saturated(curve([0.5] * 4)) is True


def test_saturated_false_when_every_measure_keeps_moving():
    assert transmission_chains.saturated(curve([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])) is False


@pytest.mark.parametrize("length", [0, 1, 2])
def test_saturated_false_with_fewer_than_three_hops_no_matter_how_fast_it_moves(length):
    assert transmission_chains.saturated(curve([0.0, 1.0][:length])) is False


def test_saturated_true_when_late_drift_stays_under_ten_percent_of_the_first_step():
    # First step 0.5 (threshold 0.05); the largest later drift is 0.03125, under it. All
    # three keys behave identically, so saturation requires every one of them to stall.
    assert transmission_chains.saturated(curve([0.0, 0.5, 0.53125, 0.53125])) is True


def test_saturated_false_when_late_drift_exceeds_ten_percent_of_the_first_step():
    # Same shape, but the later drift of 0.0625 crosses the 0.05 threshold.
    assert transmission_chains.saturated(curve([0.0, 0.5, 0.5625, 0.5625])) is False


def test_saturated_true_when_post_first_step_drift_stays_under_the_absolute_floor():
    # First step is tiny (0.001), so a drift of 0.007 clears the relative bar easily — yet
    # it sits under the absolute 0.01 floor, which wins.
    assert transmission_chains.saturated(curve([0.0, 0.001, 0.008, 0.008])) is True


def test_saturated_false_when_post_first_step_drift_exceeds_the_absolute_floor():
    # Same tiny first step, but a drift of 0.019 crosses both bars.
    assert transmission_chains.saturated(curve([0.0, 0.001, 0.02, 0.02])) is False


def test_saturated_false_when_even_one_measure_is_still_moving():
    moving = [
        {"skeleton": 0.5, "style": 0.5, "mutation": m} for m in (0.0, 0.2, 0.4, 0.6)
    ]
    assert transmission_chains.saturated(moving) is False


# -------------------------------------------------------------------------------- measure_side


PASSAGE = "alpha beta gamma delta epsilon zeta"
RETELL = "alpha beta gamma delta epsilon eta"  # one bone swapped: zeta -> eta
MEDIAN_AT_ORIGIN = {"comma_per_1k": 0.0}  # these texts carry no commas, so style pins at 0.5


def test_measure_side_tracks_skeleton_and_mutation_across_hops():
    history = [[PASSAGE], [RETELL]]
    measured = transmission_chains.measure_side(history, PASSAGE, MEDIAN_AT_ORIGIN, COMMA_SCALE)
    # Hop 0 repeats the passage verbatim: full skeleton, no mutation. Hop 1 swaps one bone of
    # six for an outsider (eta): five bones survive, so recall is 5/6, and the two vocabularies
    # of six words share five, so the Jaccard rate is 1 - 5/7 = 2/7. Comma-free texts sit on
    # both anchors' comma value, so style degrades to the neutral 0.5 at every hop.
    assert measured["per_hop"][0] == {"skeleton": 1.0, "style": 0.5, "mutation": 0.0}
    assert measured["per_hop"][1]["skeleton"] == pytest.approx(5 / 6)
    assert measured["per_hop"][1]["mutation"] == pytest.approx(2 / 7)
    assert measured["per_hop"][1]["style"] == 0.5
    assert measured["skeleton_auc"] == pytest.approx((1.0 + 5 / 6) / 2)
    assert measured["mutation_mean"] == pytest.approx((0.0 + 2 / 7) / 2)
    assert measured["style_auc"] == 0.5
    assert measured["final_skeleton"] == pytest.approx(5 / 6)
    assert measured["final_style"] == 0.5


def test_measure_side_averages_parallel_chains_without_changing_identical_chain_values():
    single = transmission_chains.measure_side(
        [[PASSAGE], [RETELL]], PASSAGE, MEDIAN_AT_ORIGIN, COMMA_SCALE
    )
    twin = transmission_chains.measure_side(
        [[PASSAGE, PASSAGE], [RETELL, RETELL]], PASSAGE, MEDIAN_AT_ORIGIN, COMMA_SCALE
    )
    assert twin == single


def test_measure_side_on_a_single_hop_that_repeats_the_passage_never_mutates():
    measured = transmission_chains.measure_side(
        [[PASSAGE, PASSAGE]], PASSAGE, MEDIAN_AT_ORIGIN, COMMA_SCALE
    )
    assert measured["per_hop"] == [{"skeleton": 1.0, "style": 0.5, "mutation": 0.0}]
    assert measured["final_skeleton"] == 1.0
    assert measured["mutation_mean"] == 0.0


# ------------------------------------------------------------------------------------ selftest


def test_module_selftest_reports_zero_failures():
    assert transmission_chains.selftest() == 0

