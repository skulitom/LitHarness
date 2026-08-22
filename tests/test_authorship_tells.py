"""Hand-derived pins for the pure functions of research/quality-measurement/authorship_tells.py.

Pinned: ``strip_system``'s two removal rules and where they stop; ``features``' arithmetic on
prose whose counts were tallied by hand before anything was run; ``_matrix``' column alignment
against the active feature list; and the direction of the logistic wrappers (``loo_auc``,
``_score_all``, ``coefficients``, ``null_distribution``) on toy feature tables whose right
answer — perfect separation, perfect reversal, or exact chance — follows from construction.

Not established: nothing here touches a corpus, database, results file, or model call, so none
of it says whether our prose separates from human LitRPG, what the tells are at n=10 against
real cohorts, or what any AUC is worth beyond the toy tables. The module has no hermetic
``selftest`` to call, so every check exercises a function directly. The model-based tests skip
where scikit-learn is absent, matching the module's own lazy imports.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

authorship_tells = pytest.importorskip(
    "authorship_tells",
    reason="research module; needs the quality-measurement directory on the path",
)

SEED = 7


def feature_row(**overrides: float) -> dict[str, float]:
    """A feature table whose every entry is 0.0 unless named, so one column carries signal."""
    base = {name: 0.0 for name in authorship_tells.FEATURE_NAMES}
    base.update(overrides)
    return base


def high_em_rows(count: int) -> list[dict[str, float]]:
    return [feature_row(em_per_1k=100.0) for _ in range(count)]


def flat_rows(count: int) -> list[dict[str, float]]:
    return [feature_row() for _ in range(count)]


# --- strip_system -----------------------------------------------------------


def test_strip_system_removes_a_bolded_header_and_a_bracketed_tag_line():
    # Each removed span becomes one space: the bold rule takes "**Status**", the line rule
    # takes the whole "[HP RESTORED] body text" line, and the flanking lines survive.
    text = "Intro.\n**Status**\n[HP RESTORED] body text\nOutro."
    assert authorship_tells.strip_system(text) == "Intro.\n \n \nOutro."


def test_strip_system_leaves_prose_without_system_markers_unchanged():
    assert authorship_tells.strip_system("plain prose here.") == "plain prose here."


def test_strip_system_keeps_lowercase_and_single_letter_bracket_tags():
    # The tag rule wants [A-Z][A-Z ]+: a lowercase tag and a one-letter tag both fall short,
    # so this line must survive untouched.
    text = "keep [quest update] and [A] markers"
    assert authorship_tells.strip_system(text) == text


def test_strip_system_takes_the_whole_line_when_a_two_letter_tag_appears():
    assert authorship_tells.strip_system("see [HP] rise") == " "


def test_strip_system_of_empty_text_is_empty_text():
    assert authorship_tells.strip_system("") == ""


# --- features ---------------------------------------------------------------


def test_features_matches_hand_counts_on_a_two_sentence_sample():
    # "I felt it. He ran!": 5 words, 1 interior verb (felt), 1 first-person (I),
    # 1 third-person (He), sentences of 3 and 2 words, one block, 5 unique tokens,
    # word lengths 1+4+3+2+4=14. Every number below was tallied by hand.
    got = authorship_tells.features("I felt it. He ran!")
    assert got["words"] == 5.0
    assert got["interior_per_1k"] == 200.0
    assert got["first_person_per_1k"] == 200.0
    assert got["third_person_per_1k"] == 200.0
    assert got["body_per_1k"] == 0.0
    assert got["body_to_interior"] == 0.0
    assert got["sentence_len_mean"] == 2.5
    assert got["sentence_len_cv"] == pytest.approx(0.2)  # pstdev 0.5 over mean 2.5
    assert got["paragraph_len_mean"] == 5.0
    assert got["type_token"] == 1.0
    assert got["word_len_mean"] == 2.8
    assert got["dialogue_ratio"] == 0.0


def test_features_on_empty_text_returns_finite_zeros_rather_than_crashing():
    got = authorship_tells.features("")
    assert set(got) == set(authorship_tells.FEATURE_NAMES)
    assert all(math.isfinite(value) for value in got.values())
    assert got["type_token"] == 0.0
    assert got["sentence_len_cv"] == 0.0


def test_features_prices_em_dashes_at_rate_per_thousand_words():
    # "yes — no — maybe" splits into 5 whitespace tokens holding 2 em dashes: 1000*2/5.
    assert authorship_tells.features("yes — no — maybe")["em_per_1k"] == 400.0


def test_features_counts_question_and_exclaim_marks_per_thousand_words():
    # "Wow! Really?" is 2 words carrying one mark of each kind: 500 per thousand apiece.
    got = authorship_tells.features("Wow! Really?")
    assert got["question_per_1k"] == 500.0
    assert got["exclaim_per_1k"] == 500.0


def test_features_gives_zero_length_variance_with_a_single_sentence():
    # One sentence means no spread to measure: cv collapses to 0 instead of dividing by n-1.
    got = authorship_tells.features("One sentence only.")
    assert got["sentence_len_mean"] == 3.0
    assert got["sentence_len_cv"] == 0.0


# --- _matrix ----------------------------------------------------------------


def test_matrix_changes_exactly_one_entry_when_one_feature_value_changes():
    rows = [{name: 7.0 for name in authorship_tells.FEATURE_NAMES} for _ in range(3)]
    before = authorship_tells._matrix(rows)
    assert before.shape == (3, len(authorship_tells.ACTIVE))
    changed = [dict(row) for row in rows]
    changed[1]["em_per_1k"] = 9.0
    after = authorship_tells._matrix(changed)
    assert int((before != after).sum()) == 1


def test_matrix_of_no_rows_is_empty_without_crashing():
    empty = authorship_tells._matrix([])
    assert empty.shape[0] == 0


def test_matrix_raises_key_error_when_a_row_lacks_an_active_feature():
    with pytest.raises(KeyError):
        authorship_tells._matrix([{"em_per_1k": 1.0}])


# --- loo_auc ----------------------------------------------------------------


def test_loo_auc_is_one_when_only_the_positives_carry_a_feature():
    pytest.importorskip("sklearn")
    # Every held-out positive outranks every negative by construction.
    assert authorship_tells.loo_auc(high_em_rows(3), flat_rows(4), SEED) == 1.0


def test_loo_auc_is_zero_when_only_the_negatives_carry_a_feature():
    pytest.importorskip("sklearn")
    # Roles swapped: every held-out positive falls below every negative.
    assert authorship_tells.loo_auc(flat_rows(3), high_em_rows(4), SEED) == 0.0


def test_loo_auc_is_exactly_chance_when_both_classes_are_identical():
    pytest.importorskip("sklearn")
    # No column varies, so every score equals every other and each pair pays 0.5.
    assert authorship_tells.loo_auc(flat_rows(3), flat_rows(4), SEED) == 0.5


# --- _score_all -------------------------------------------------------------


def test_score_all_puts_separated_negatives_below_zero():
    pytest.importorskip("sklearn")
    scores = authorship_tells._score_all(high_em_rows(3), flat_rows(4), SEED)
    assert len(scores) == 4
    assert all(score < 0 for score in scores)


def test_score_all_puts_negatives_above_zero_when_negatives_carry_the_feature():
    pytest.importorskip("sklearn")
    scores = authorship_tells._score_all(flat_rows(3), high_em_rows(4), SEED)
    assert all(score > 0 for score in scores)


def test_score_all_returns_one_equal_score_when_both_classes_are_identical():
    pytest.importorskip("sklearn")
    scores = authorship_tells._score_all(flat_rows(3), flat_rows(4), SEED)
    assert len(scores) == 4
    assert len(set(scores)) == 1


# --- coefficients -----------------------------------------------------------


def test_coefficients_rank_the_separating_feature_first_with_positive_sign():
    pytest.importorskip("sklearn")
    pairs = authorship_tells.coefficients(high_em_rows(3), flat_rows(4), SEED)
    assert pairs[0][0] == "em_per_1k"
    assert pairs[0][1] > 0
    # Every active feature is reported exactly once, largest magnitude first throughout.
    assert [name for name, _ in pairs] == list(authorship_tells.ACTIVE)
    assert all(abs(pairs[i][1]) >= abs(pairs[i + 1][1]) for i in range(len(pairs) - 1))


def test_coefficients_rank_the_separating_feature_first_with_negative_sign():
    pytest.importorskip("sklearn")
    pairs = authorship_tells.coefficients(flat_rows(3), high_em_rows(4), SEED)
    assert pairs[0][0] == "em_per_1k"
    assert pairs[0][1] < 0


def test_coefficients_collapse_to_zero_when_both_classes_are_identical():
    pytest.importorskip("sklearn")
    pairs = authorship_tells.coefficients(flat_rows(3), flat_rows(4), SEED)
    assert len(pairs) == len(authorship_tells.ACTIVE)
    assert all(abs(weight) < 1e-9 for _, weight in pairs)


# --- null_distribution ------------------------------------------------------


def test_null_distribution_returns_replicates_sorted_within_the_auc_range():
    pytest.importorskip("sklearn")
    mixed = high_em_rows(3) + flat_rows(3)
    aucs = authorship_tells.null_distribution(mixed, size=2, replicates=4, seed=SEED)
    assert len(aucs) == 4
    assert aucs == sorted(aucs)
    assert all(0.0 <= auc <= 1.0 for auc in aucs)


def test_null_distribution_repeats_identically_under_the_same_seed():
    pytest.importorskip("sklearn")
    mixed = high_em_rows(3) + flat_rows(3)
    first = authorship_tells.null_distribution(mixed, size=2, replicates=4, seed=SEED)
    second = authorship_tells.null_distribution(mixed, size=2, replicates=4, seed=SEED)
    assert first == second


def test_null_distribution_sits_at_exact_chance_when_every_row_is_identical():
    pytest.importorskip("sklearn")
    # Any draw splits identical rows into identical halves, so each replicate is 0.5.
    aucs = authorship_tells.null_distribution(flat_rows(6), size=2, replicates=3, seed=SEED)
    assert aucs == [0.5, 0.5, 0.5]

