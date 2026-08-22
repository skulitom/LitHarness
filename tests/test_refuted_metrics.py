"""Exact-value pins on the frozen arithmetic of ``refuted_metrics.py``.

That module declares itself FROZEN: changed arithmetic there would silently detach the
committed craft profile and the recorded per-scene rows from the code that produced them.
These tests make any such change loud. Each expected number was derived by hand from the
function's docstring and code, on hand-built inputs whose correct answer can be stated
before running anything, and includes the degenerate cases — empty text, punctuation-only
text, a single sentence — and, where a function classifies (sentence-count floor,
conjunction acceptance, modal-opening share), a case on each side of the boundary.

What they do not establish: that any of these metrics detects anything. BRIEF.md §2 Pass 2
refuted exactly that claim for all four proxies, so these pins say nothing about quality,
authorship, or AI-tells — only that the arithmetic stays where the refutation measured it.
They also deliberately do not touch anything in the module's orbit that reads a database,
a results file, or a corpus, or that calls a model or spawns a process; everything below
is pure string arithmetic. The module exposes no hermetic ``selftest``, so behaviour is
checked directly throughout.
"""

from __future__ import annotations

import pytest

refuted_metrics = pytest.importorskip(
    "refuted_metrics",
    reason="research module; needs the quality-measurement directory on the path",
)


# --- sentences ------------------------------------------------------------------------


def test_sentences_splits_on_terminators_and_strips_surrounding_whitespace():
    assert refuted_metrics.sentences("  Go now.  Then stop. ") == ["Go now", "Then stop"]


def test_sentences_treats_a_run_of_terminator_punctuation_as_one_break():
    assert refuted_metrics.sentences("Wait?! Really... Okay.") == ["Wait", "Really", "Okay"]


def test_sentences_returns_text_without_a_terminator_as_one_sentence():
    assert refuted_metrics.sentences("no punctuation anywhere here") == [
        "no punctuation anywhere here"
    ]


def test_sentences_returns_an_empty_list_for_empty_text():
    assert refuted_metrics.sentences("") == []


# --- words ----------------------------------------------------------------------------


def test_words_splits_on_non_word_characters_and_drops_punctuation():
    assert refuted_metrics.words("Hello, world! Run.") == ["Hello", "world", "Run"]


def test_words_keeps_hyphens_and_curly_apostrophes_inside_tokens():
    # U+2019 is the right single quotation mark, spelled out here for ruff's RUF001.
    assert refuted_metrics.words("don\u2019t stop — well-known") == [
        "don\u2019t",
        "stop",
        "well-known",
    ]


def test_words_returns_no_tokens_for_empty_and_punctuation_only_text():
    assert refuted_metrics.words("") == []
    assert refuted_metrics.words("... !!!") == []


# --- sentence_length_variation ----------------------------------------------------------


def test_sentence_length_variation_is_the_cv_of_word_counts_over_three_sentences():
    # Lengths [1, 2, 3]: mean 2, pstdev sqrt(2/3), cv = sqrt(2/3)/2 = 0.40824829...
    metric = refuted_metrics.sentence_length_variation("Go. Stop now. Now go home.")
    assert metric.value == 0.4082
    assert metric.detail == "3 sentence(s)"


def test_sentence_length_variation_is_zero_for_two_equal_length_sentences():
    # Both sentences carry 2 words, so pstdev is 0 while the two-sentence path runs.
    assert refuted_metrics.sentence_length_variation("Two words. Four words.").value == 0.0


def test_sentence_length_variation_is_zero_below_two_sentences():
    assert refuted_metrics.sentence_length_variation("Only one sentence here.").value == 0.0


def test_sentence_length_variation_is_zero_for_empty_text_without_crashing():
    metric = refuted_metrics.sentence_length_variation("")
    assert metric.value == 0.0
    assert metric.detail == "0 sentence(s)"


def test_sentence_length_variation_is_zero_when_no_sentence_has_words():
    assert refuted_metrics.sentence_length_variation(". . .").value == 0.0


# --- dialogue_ratio ---------------------------------------------------------------------


def test_dialogue_ratio_counts_quoted_characters_including_the_quote_marks():
    # '"Hi."' contributes 5 characters of the 14-character text: 5/14 = 0.35714285...
    assert refuted_metrics.dialogue_ratio('"Hi." He said.').value == 0.3571


def test_dialogue_ratio_is_one_when_the_whole_text_is_quoted():
    assert refuted_metrics.dialogue_ratio('"ab"').value == 1.0


def test_dialogue_ratio_matches_curly_quotes_like_straight_ones():
    assert refuted_metrics.dialogue_ratio("“ab”").value == 1.0


def test_dialogue_ratio_sums_every_quoted_span_in_the_text():
    # '"a"' and '"c"' contribute 3 characters each of the 9-character text: 6/9.
    assert refuted_metrics.dialogue_ratio('"a" b "c"').value == 0.6667


def test_dialogue_ratio_is_zero_without_a_closing_quote():
    assert refuted_metrics.dialogue_ratio('"never closed').value == 0.0


def test_dialogue_ratio_is_zero_for_empty_text():
    assert refuted_metrics.dialogue_ratio("").value == 0.0


# --- tricolon_rate ----------------------------------------------------------------------


def test_tricolon_rate_scores_one_list_of_four_words_at_250_per_thousand():
    metric = refuted_metrics.tricolon_rate("red, white, and blue")
    assert metric.value == 250.0
    assert metric.detail == "1 in 4 word(s)"


def test_tricolon_rate_accepts_or_as_the_coordinating_conjunction():
    assert refuted_metrics.tricolon_rate("fast, cheap, or dirty").value == 250.0


def test_tricolon_rate_normalises_by_the_total_word_count():
    # One list among 7 words: 1000/7 = 142.85714285...
    metric = refuted_metrics.tricolon_rate("He chose red, white, and blue threads.")
    assert metric.value == 142.8571


def test_tricolon_rate_rejects_a_two_item_list_without_the_serial_comma():
    # "bread, butter and jam" has no comma before "and", so the pattern cannot close.
    assert refuted_metrics.tricolon_rate("bread, butter and jam").value == 0.0


def test_tricolon_rate_rejects_conjunctions_other_than_and_or():
    assert refuted_metrics.tricolon_rate("up, down, nor sideways").value == 0.0


def test_tricolon_rate_is_zero_for_empty_and_punctuation_only_text():
    assert refuted_metrics.tricolon_rate("").value == 0.0
    assert refuted_metrics.tricolon_rate("...").value == 0.0


# --- opening_shape_repetition ------------------------------------------------------------


def test_opening_shape_repetition_shares_the_modal_two_token_opening():
    # Openings: "the old", "the old", "a dog" — the modal one holds 2 of 3.
    metric = refuted_metrics.opening_shape_repetition(
        "The old king rode. The old queen waited. A dog barked."
    )
    assert metric.value == 0.6667


def test_opening_shape_repetition_lowercases_the_openings():
    # "THE END" and "The end" are the same shape; the modal shape holds 2 of 3.
    metric = refuted_metrics.opening_shape_repetition(
        "THE END came. The end stayed. A page turned."
    )
    assert metric.value == 0.6667


def test_opening_shape_repetition_is_one_when_every_opening_matches():
    metric = refuted_metrics.opening_shape_repetition("He ran far. He ran fast. He ran home.")
    assert metric.value == 1.0


def test_opening_shape_repetition_splits_a_two_way_tie_evenly():
    assert refuted_metrics.opening_shape_repetition("Alpha beta. Gamma delta.").value == 0.5


def test_opening_shape_repetition_is_zero_for_a_single_sentence():
    assert refuted_metrics.opening_shape_repetition("Just one.").value == 0.0


def test_opening_shape_repetition_is_zero_for_empty_text():
    assert refuted_metrics.opening_shape_repetition("").value == 0.0
