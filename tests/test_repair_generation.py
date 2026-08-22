"""Hermetic pins on the pure mechanics of ``repair_generation.py``.

Pinned: em-dash counting outside protected system-voice spans, word-sequence
similarity, z-scored distance with zero-spread features skipped, the population
feature scale, the three branches of the deterministic ``compliance`` verdict,
exemplar selection by interiority density, and the fact that the two prompt builders
render and carry the scene and passages they are handed. Every expected number below
was derived by hand from the docstrings and the code before anything was run.

Not established: anything about ``run``, ``main``, model calls, cache replays,
database reads or the CLI; nothing here touches ``corpora/``, ``results/`` or
``derived/``. The module has no ``selftest()``. Passing these tests says the
arithmetic and the verdict branches behave as written; it says nothing about whether
any generated repair actually moves a measured axis.
"""

from __future__ import annotations

import math

import pytest

repair_generation = pytest.importorskip(
    "repair_generation",
    reason="research module; needs the quality-measurement directory on the path",
)

#: Wide enough that each compliance test isolates exactly one pre-registered threshold.
PLACEBO_BAND = {"interior": 0.5, "interior_drift": 0.25, "em": 1.0}


# --------------------------------------------------------------------- prose_em_count


def test_prose_em_count_counts_each_unprotected_dash():
    # Two prose dashes, nothing protected: one per finditer match.
    assert repair_generation.prose_em_count("He ran — fast. Then — gone.") == 2


def test_prose_em_count_of_empty_text_is_zero():
    assert repair_generation.prose_em_count("") == 0


def test_prose_em_count_counts_no_dash_inside_a_bold_header():
    # The whole **...** span is protected, dash included.
    assert repair_generation.prose_em_count("**TOLL PAID — 9 days**") == 0


def test_prose_em_count_counts_only_the_dash_outside_the_bold_header():
    text = "**TOLL PAID — 9 days**\nHe ran — fast."
    assert repair_generation.prose_em_count(text) == 1


def test_prose_em_count_counts_no_dash_on_a_status_line():
    assert repair_generation.prose_em_count("[STATUS] wren — Level 2 | HP x/22") == 0


# -------------------------------------------------------------------- word_similarity


def test_word_similarity_of_identical_text_is_one():
    text = "the quick brown fox jumps"
    assert repair_generation.word_similarity(text, text) == 1.0


def test_word_similarity_scores_three_shared_words_of_four_as_three_quarters():
    # 2 * 3 matches / (4 + 4) words = 0.75
    assert repair_generation.word_similarity("a b c d", "a b c e") == 0.75


def test_word_similarity_rounds_to_four_places():
    # 2 * 4 matches / (6 + 6) words = 0.6666...
    assert repair_generation.word_similarity("a b c d e f", "a b c x y f") == 0.6667


def test_word_similarity_against_empty_text_is_zero():
    assert repair_generation.word_similarity("a b c", "") == 0.0


def test_word_similarity_of_two_empty_texts_is_one_without_crashing():
    assert repair_generation.word_similarity("", "") == 1.0


# ------------------------------------------------------------------------- z_distance


def test_z_distance_sums_squared_z_deltas_across_features():
    # ((3 - 1) / 2)^2 + ((1 - 1) / 5)^2 = 1 + 0
    row = {"a": 3.0, "b": 1.0}
    anchor = {"a": 1.0, "b": 1.0}
    scale = {"a": 2.0, "b": 5.0}
    assert repair_generation.z_distance(row, anchor, scale) == 1.0


def test_z_distance_combines_features_in_quadrature_and_rounds_to_four_places():
    # (2 / 1)^2 + (4 / 2)^2 = 8, sqrt(8) = 2.82842...
    row = {"a": 2.0, "b": 4.0}
    anchor = {"a": 0.0, "b": 0.0}
    scale = {"a": 1.0, "b": 2.0}
    assert repair_generation.z_distance(row, anchor, scale) == 2.8284


def test_z_distance_skips_a_feature_whose_scale_is_zero():
    # b swings wildly but has zero spread, so only a contributes: (10 / 2)^2 = 25.
    row = {"a": 10.0, "b": 999.0}
    anchor = {"a": 0.0, "b": -999.0}
    scale = {"a": 2.0, "b": 0.0}
    assert repair_generation.z_distance(row, anchor, scale) == 5.0


def test_z_distance_with_an_empty_scale_is_zero():
    assert repair_generation.z_distance({"a": 1.0}, {"a": 2.0}, {}) == 0.0


def test_z_distance_of_identical_row_and_anchor_is_zero():
    assert repair_generation.z_distance({"a": 3.0}, {"a": 3.0}, {"a": 2.0}) == 0.0


# ---------------------------------------------------------------------- feature_scale


def test_feature_scale_returns_population_sd_per_feature():
    # x over {1, 3}: mean 2, squared deviations 1 and 1, /2 -> sd 1.0; y never moves.
    rows = [{"x": 1.0, "y": 5.0}, {"x": 3.0, "y": 5.0}]
    assert repair_generation.feature_scale(rows) == {"x": 1.0, "y": 0.0}


def test_feature_scale_over_three_rows_matches_the_population_formula():
    # x over {1, 3, 5}: variance (4 + 0 + 4) / 3 = 8/3.
    rows = [{"x": 1.0}, {"x": 3.0}, {"x": 5.0}]
    assert repair_generation.feature_scale(rows)["x"] == pytest.approx(math.sqrt(8.0 / 3.0))


def test_feature_scale_of_a_single_row_is_zero_for_every_feature():
    assert repair_generation.feature_scale([{"x": 7.5, "y": -2.0}]) == {"x": 0.0, "y": 0.0}


# --------------------------------------------------------------------- pick_exemplars


#: Index 0 has no interiority verb; index 1 has one over seven words; index 2 has
#: two over nine, so the density ranking is 2 > 1 > 0.
EXEMPLAR_POOL = [
    "He watched the road.",
    "He felt the road pull at him.",
    "He knew the gate and he wondered about it.",
]


def test_pick_exemplars_ranks_indices_by_interiority_density():
    assert repair_generation.pick_exemplars(EXEMPLAR_POOL) == [2, 1]


def test_pick_exemplars_with_count_one_returns_only_the_densest_index():
    assert repair_generation.pick_exemplars(EXEMPLAR_POOL, count=1) == [2]


def test_pick_exemplars_with_a_count_larger_than_the_pool_returns_all_indices_ranked():
    assert repair_generation.pick_exemplars(EXEMPLAR_POOL, count=5) == [2, 1, 0]


def test_pick_exemplars_on_an_empty_pool_returns_nothing():
    assert repair_generation.pick_exemplars([], count=2) == []


def test_pick_exemplars_breaks_equal_density_ties_by_pool_order():
    tied = ["He felt it.", "He felt it."]
    assert repair_generation.pick_exemplars(tied) == [0, 1]


# ------------------------------------------------------------------- prompt builders


def test_exemplar_system_numbers_and_carries_each_passage_in_order():
    prompt = repair_generation.exemplar_system(["first excerpt.", "second excerpt."])
    assert "VOICE PASSAGE 1\n\nfirst excerpt." in prompt
    assert "VOICE PASSAGE 2\n\nsecond excerpt." in prompt
    assert prompt.index("VOICE PASSAGE 1") < prompt.index("VOICE PASSAGE 2")


def test_exemplar_system_presents_passages_as_voice_inside_the_frame():
    prompt = repair_generation.exemplar_system(["an excerpt."])
    assert "voice of the passages" in prompt
    assert prompt.index("voice of the passages") < prompt.index("VOICE PASSAGE")


def test_exemplar_system_with_no_passages_still_renders_the_frame():
    prompt = repair_generation.exemplar_system([])
    assert "novelist" in prompt
    assert "VOICE PASSAGE" not in prompt


def test_reviser_turn_carries_the_arm_task_above_the_scene():
    turn = repair_generation.reviser_turn("repair_emdash", "The gate opened.")
    assert repair_generation.TASKS["repair_emdash"] in turn
    assert turn.endswith("\n\n---\n\nThe gate opened.")


def test_reviser_turn_differs_between_two_arms_only_in_the_task_block():
    emdash = repair_generation.reviser_turn("repair_emdash", "scene")
    placebo = repair_generation.reviser_turn("repair_placebo", "scene")
    swapped = emdash.replace(
        repair_generation.TASKS["repair_emdash"],
        repair_generation.TASKS["repair_placebo"],
    )
    assert swapped == placebo


def test_reviser_turn_with_an_empty_scene_still_renders_the_separator():
    turn = repair_generation.reviser_turn("repair_placebo", "")
    assert repair_generation.TASKS["repair_placebo"] in turn
    assert turn.endswith("---\n\n")


# ------------------------------------------------------------------------- compliance


def test_compliance_certifies_an_emdash_repair_that_clears_every_check():
    # Prose dash rewritten away (1 -> 0 <= 10% of 1), header untouched; similarity is
    # 2 * 6 shared words over 7 + 6 = 12/13 = 0.9231 >= 0.80; no interior verb moves.
    original = "**GATE — OPEN**\nHe ran — fast."
    variant = "**GATE — OPEN**\nHe ran fast."
    row = repair_generation.compliance("repair_emdash", original, variant, PLACEBO_BAND)
    assert row["prose_em_before"] == 1
    assert row["prose_em_after"] == 0
    assert row["similarity"] == 0.9231
    assert row["interior_delta"] == 0.0
    assert row["system_voice_ok"] is True
    assert row["complies"] is True


def test_compliance_passes_an_emdash_repair_leaving_exactly_ten_percent_of_the_dashes():
    # Ten prose dashes; nine sentences rewritten, one dash survives: 1 <= 0.10 * 10.
    # Similarity is 2 * 21 / (30 + 21) = 42/51 = 0.8235 >= 0.80, so only this rule binds.
    original = " ".join(f"w{i} — v{i}" for i in range(10))
    variant = " ".join(f"w{i} v{i}" for i in range(9)) + " w9 — v9"
    row = repair_generation.compliance("repair_emdash", original, variant, PLACEBO_BAND)
    assert row["prose_em_before"] == 10
    assert row["prose_em_after"] == 1
    assert row["complies"] is True


def test_compliance_fails_an_emdash_repair_leaving_more_than_ten_percent_of_the_dashes():
    # Two surviving dashes against ten originals: 2 > 0.10 * 10, everything else clears
    # (similarity 2 * 22 / (30 + 22) = 44/52 = 0.8462 >= 0.80).
    original = " ".join(f"w{i} — v{i}" for i in range(10))
    variant = " ".join(f"w{i} v{i}" for i in range(8)) + " w8 — v8 w9 — v9"
    row = repair_generation.compliance("repair_emdash", original, variant, PLACEBO_BAND)
    assert row["prose_em_before"] == 10
    assert row["prose_em_after"] == 2
    assert row["complies"] is False


def test_compliance_fails_an_emdash_repair_that_lost_its_protected_span():
    # The header vanishes, so survival fails although the prose-dash rule, similarity
    # (2 * 14 / (18 + 14) = 28/32 = 0.875 >= 0.80) and interiority all clear.
    original = (
        "**GATE — POSTED**\n"
        "He ran fast. He walked home. He sat down. He stood up. He — paused."
    )
    variant = "He ran fast. He walked home. He sat down. He stood up. He paused."
    row = repair_generation.compliance("repair_emdash", original, variant, PLACEBO_BAND)
    assert row["prose_em_before"] == 1
    assert row["prose_em_after"] == 0
    assert row["system_voice_ok"] is False
    assert row["complies"] is False


def test_compliance_certifies_an_interiority_repair_within_the_word_growth_cap():
    # One "felt" added to twenty sentences: interior rises by 1000/82 = 12.195 per 1k
    # (>= max(2 * 0.25, 0.5)), growth 100 * 2 / 80 = 2.5% <= 12%, similarity high.
    original = " ".join(["He watched the gate."] * 20)
    variant = original.replace("He watched the gate.", "He felt the gate watch him.", 1)
    row = repair_generation.compliance(
        "repair_interiority", original, variant, PLACEBO_BAND
    )
    assert row["interior_delta"] == 12.195
    assert row["word_growth_pct"] == 2.5
    assert row["system_voice_ok"] is True
    assert row["complies"] is True


def test_compliance_fails_an_interiority_repair_growing_past_twelve_percent():
    # Four words become six: growth 50% > 12%, while the interiority rise (166.667),
    # similarity (2 * 4 / (4 + 6) = 0.8 >= 0.60) and em drift all clear.
    row = repair_generation.compliance(
        "repair_interiority",
        "He watched the gate.",
        "He felt watched by the gate.",
        PLACEBO_BAND,
    )
    assert row["word_growth_pct"] == 50.0
    assert row["complies"] is False


def test_compliance_records_no_verdict_for_the_placebo_arm():
    row = repair_generation.compliance(
        "repair_placebo", "He ran — fast.", "He ran fast.", PLACEBO_BAND
    )
    assert row["complies"] is None
    assert row["prose_em_before"] == 1
    assert row["prose_em_after"] == 0


def test_compliance_on_two_empty_texts_records_degenerate_measures_without_crashing():
    row = repair_generation.compliance("repair_placebo", "", "", PLACEBO_BAND)
    assert row["complies"] is None
    assert row["similarity"] == 1.0
    assert row["word_growth_pct"] == 0.0
    assert row["system_voice_ok"] is True
