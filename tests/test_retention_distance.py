"""Hermetic pins on retention_distance's extractor arithmetic.

What these tests pin: the pure text and arithmetic layer of Track F2 — that `probe_window` cuts
the opening words, that `candidate_sites` admits only in-band, non-initial words, that
`matched_sites` pairs across a pair's two sides inside the declared half-decade tolerance and
never reuses a partner, that `decay_slope` fits uplift over log2 distance and refuses an
incomplete ladder, and that `corpus_counts` builds a label-blind unigram table over both sides
of every pair. Every expected value is derived by hand from a constructed input.

What they do not establish: nothing here touches a model, a tokenizer, a corpus file, a results
file or the CLI, so nothing here says the F2 *measurement* works. `build_distractors`,
`_site_logprobs` and `uplift_for_side` all go through `force_gpu` and are out of scope, as are
`run_family`, `run` and `main`. The one `selftest()` call is a smoke pin, not a substitute for
the direct assertions beside it.
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import pytest

retention_distance = pytest.importorskip(
    "retention_distance",
    reason="research module; needs the quality-measurement directory on the path",
)


def _padded_window(*candidates: str) -> str:
    """A probe window whose candidate slots start exactly at index 8."""
    return " ".join(("pad",) * 8 + candidates)


# ----------------------------------------------------------------------------- probe_window


def test_probe_window_joins_the_opening_words_with_single_spaces():
    assert retention_distance.probe_window("alpha  beta\ngamma\t\tdelta") == (
        "alpha beta gamma delta"
    )


def test_probe_window_returns_a_short_text_unchanged():
    assert retention_distance.probe_window("one two three") == "one two three"


def test_probe_window_of_the_empty_string_is_the_empty_string():
    assert retention_distance.probe_window("") == ""


def test_probe_window_cuts_a_long_text_to_the_declared_opening_words():
    words = [f"w{i}" for i in range(400)]
    window = retention_distance.probe_window(" ".join(words))
    assert window == " ".join(f"w{i}" for i in range(retention_distance.PROBE_WORDS))
    assert "w399" not in window


# --------------------------------------------------------------------------- candidate_sites


def test_candidate_sites_keeps_only_in_band_words_after_the_first_eight():
    counts = Counter({"low": 2, "mid": 50, "scarce": 1, "ceiling": 400, "huge": 5000})
    window = "mid " + "pad " * 7 + "low mid scarce ceiling huge unknown"
    sites = retention_distance.candidate_sites(window, counts)
    # Index 0 is "mid" — frequent enough, but window-initial, so excluded. Count 2 sits on the
    # floor and is kept; 1 is below it, 400 on the ceiling and 5000 above it, all rejected;
    # "unknown" has no table entry and must read as count zero, not a crash.
    assert sites == [(8, "low", math.log10(2)), (9, "mid", math.log10(50))]


def test_candidate_sites_reads_words_out_of_punctuation_and_case():
    counts = Counter({"twas-brilliant": 5, "don't": 9})
    window = _padded_window("'Twas-brilliant,", "DON'T,")
    assert retention_distance.candidate_sites(window, counts) == [
        (8, "twas-brilliant", math.log10(5)),
        (9, "don't", math.log10(9)),
    ]
def test_candidate_sites_skips_tokens_with_no_letters_at_all():
    counts = Counter({"kept": 7})
    window = _padded_window("...", "@@@", "kept")
    assert retention_distance.candidate_sites(window, counts) == [(10, "kept", math.log10(7))]


def test_candidate_sites_on_a_window_shorter_than_nine_words_returns_nothing():
    assert retention_distance.candidate_sites("a b c d e f g h", Counter({"a": 10})) == []
    assert retention_distance.candidate_sites("", Counter({"a": 10})) == []


# ----------------------------------------------------------------------------- matched_sites


def test_matched_sites_pairs_inside_half_a_decade_and_refuses_just_beyond_it():
    # log10(63/20) = log10(3.15) = 0.498 — inside the 0.5 tolerance; log10(64/20) = log10(3.2)
    # = 0.505 — outside it. Same high side, one word swapped on the low side flips the answer.
    counts = Counter({"a": 20, "b": 63, "c": 64})
    high = _padded_window("a")
    inside = _padded_window("b")
    outside = _padded_window("c")
    assert retention_distance.matched_sites(high, inside, counts) == ([8], [8])
    assert retention_distance.matched_sites(high, outside, counts) == ([], [])


def test_matched_sites_never_reuses_a_low_side_partner_nor_crosses_the_tolerance():
    # Two high-side candidates, but only one low-side word within tolerance: the second high
    # site must stay unmatched rather than share "b" or pair with the far-too-rare "c".
    counts = Counter({"a": 20, "b": 63, "c": 350})
    high = _padded_window("a", "a")
    low = _padded_window("b", "c")
    chosen_high, chosen_low = retention_distance.matched_sites(high, low, counts)
    assert chosen_high == [8]
    assert chosen_low == [8]
    assert high.split()[chosen_high[0]] == "a"
    assert low.split()[chosen_low[0]] == "b"


def test_matched_sites_returns_at_most_twelve_pairs_when_both_sides_offer_more():
    # Fifteen words per side, all within a factor of 2.4 of each other, so frequency is never
    # the binding constraint — the per-side cap is. Letters only: a digit would leave the
    # candidate extractor holding a truncated word that is not in the table.
    words = ["az", "bz", "cz", "dz", "ez", "fz", "gz", "hz", "iz", "jz", "kz", "lz", "mz",
             "nz", "oz"]
    counts = Counter({word: 10 + i for i, word in enumerate(words)})
    high = _padded_window(*words)
    low = _padded_window(*words)
    chosen_high, chosen_low = retention_distance.matched_sites(high, low, counts)
    assert len(chosen_high) == len(chosen_low) == retention_distance.SITES
    # Sorted by rarity, the candidates pair in placement order: w0 (count 10) first, w14 last.
    assert chosen_high == list(range(8, 8 + retention_distance.SITES))
    assert chosen_low == list(range(8, 8 + retention_distance.SITES))


def test_matched_sites_on_windows_without_candidates_returns_two_empty_lists():
    counts = Counter({"a": 20})
    assert retention_distance.matched_sites("", "", counts) == ([], [])
    assert retention_distance.matched_sites("only pads here", "only pads here", counts) == ([], [])


# ------------------------------------------------------------------------------ decay_slope


def test_decay_slope_fits_an_exactly_linear_uplift_over_log2_distance():
    # The declared distances are equally spaced in log2 by a step of log2(3), so an uplift that
    # drops 1.0 per rung has hand-derivable slope -1/log2(3).
    ladder = dict(zip(retention_distance.DISTANCES, (3.0, 2.0, 1.0), strict=True))
    slope = retention_distance.decay_slope(ladder)
    assert slope == pytest.approx(-1.0 / math.log2(3))


def test_decay_slope_is_exactly_zero_for_an_uplift_that_never_decays():
    ladder = dict.fromkeys(retention_distance.DISTANCES, 5.0)
    assert retention_distance.decay_slope(ladder) == 0.0


def test_decay_slope_refuses_an_incomplete_ladder_instead_of_fitting_it():
    ladder = dict(zip(retention_distance.DISTANCES[:2], (1.0, 0.5), strict=True))
    assert retention_distance.decay_slope(ladder) is None
    assert retention_distance.decay_slope({}) is None


def test_decay_slope_does_not_depend_on_the_order_the_distances_were_inserted():
    forward = dict(zip(retention_distance.DISTANCES, (3.0, 2.0, 1.0), strict=True))
    backward = dict(reversed(list(forward.items())))
    assert retention_distance.decay_slope(backward) == retention_distance.decay_slope(forward)


# ----------------------------------------------------------------------------- corpus_counts


def test_corpus_counts_lowercases_and_strips_punctuation_across_both_sides_of_a_pair():
    pair = retention_distance.ForcePair(
        pair_id="t1", stratum="aligned",
        # A hyphen sits *inside* the word pattern, so "--" does not split; a comma does.
        high="Cat cat DOG.", low="bird's bird's, dog",
    )
    counts = retention_distance.corpus_counts([pair])
    assert counts == Counter({"cat": 2, "dog": 2, "bird's": 2})


def test_corpus_counts_keeps_a_curly_apostrophe_inside_one_word():
    pair = retention_distance.ForcePair(
        pair_id="t2", stratum="aligned", high="don’t", low=""  # noqa: RUF001
    )
    counts = retention_distance.corpus_counts([pair])
    assert counts == Counter({"don’t": 1})  # noqa: RUF001


def test_corpus_counts_accumulates_across_pairs_and_survives_empty_sides():
    pairs = [
        retention_distance.ForcePair(pair_id="t3", stratum="aligned", high="echo echo", low=""),
        retention_distance.ForcePair(pair_id="t4", stratum="aligned", high="", low="echo faint"),
    ]
    assert retention_distance.corpus_counts(pairs) == Counter({"echo": 3, "faint": 1})


def test_corpus_counts_over_no_pairs_is_an_empty_counter():
    assert retention_distance.corpus_counts([]) == Counter()


# ---------------------------------------------------------------------------------- selftest


def test_the_module_selftest_passes():
    assert retention_distance.selftest() == 0
