"""Behavioural pins on the pure functions of `research/quality-measurement/writer_states.py`.

Pinned, by hand-derived expected values: `prose_report`'s countable lexical arithmetic
(word count, em dash and interiority rates per 1k, stake vocabulary via `stake_score`,
sentence rhythm, type-token ratio), `system_voice_survival`'s byte-for-byte protected-span
accounting, `verdict`'s pre-registered branch order with its positional-bias precondition
and tea floor, and the fact that `writer_system` and `retell_turn` assemble exactly the
pieces they are given.

Not established here: that any of these proxies measures quality, that simulated states move
prose, that the panel or generator behaves, that caching, resume or spend accounting works,
or anything that needs a database, corpus file, subprocess or model call. Hermetic by
construction: values in, values out.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

writer_states = pytest.importorskip(
    "writer_states",
    reason="research module; needs the quality-measurement directory on the path",
)


# --------------------------------------------------------------------- prose_report


def test_prose_report_derives_every_rate_from_a_hand_counted_text():
    # 9 words, one interiority verb (`felt`), two sentences of 3 and 6 words, and a second
    # sentence scoring 3 on stake_score (`failed` + `die` cost words, plus the `if`/`would`
    # conditional-modal bonus). Seven distinct case-folded stems over nine tokens.
    report = writer_states.prose_report("She felt fear. If she failed she would die.")
    assert report["words"] == 9
    assert report["em_per_1k"] == 0.0
    assert report["interiority_per_1k"] == pytest.approx(1000 / 9, abs=1e-3)
    assert report["stake_per_1k"] == pytest.approx(1000 / 3, abs=1e-3)
    assert report["sentence_mean"] == pytest.approx(4.5)
    assert report["sentence_sd"] == pytest.approx(1.5)
    assert report["ttr"] == pytest.approx(7 / 9, abs=1e-4)


def test_prose_report_counts_every_em_dash_occurrence():
    # Two dashes over six words: 1000 * 2 / 6 = 333.333 per 1k.
    report = writer_states.prose_report("He ran — and — fell.")
    assert report["words"] == 6
    assert report["em_per_1k"] == pytest.approx(333.333)


def test_prose_report_matches_interior_verbs_only_on_word_boundaries():
    # `Thoughts` must not count (the \b after `thought` fails before the s); `thought` does.
    report = writer_states.prose_report("Thoughts crowded in. Later he thought better.")
    assert report["interiority_per_1k"] == pytest.approx(1000 / 7, abs=1e-3)


def test_prose_report_of_an_empty_text_is_all_zeros():
    assert writer_states.prose_report("") == {
        "words": 0,
        "em_per_1k": 0.0,
        "interiority_per_1k": 0.0,
        "stake_per_1k": 0.0,
        "sentence_mean": 0.0,
        "sentence_sd": 0.0,
        "ttr": 0.0,
    }


def test_prose_report_of_whitespace_only_text_counts_zero_words():
    assert writer_states.prose_report("  \n\t ")["words"] == 0


# --------------------------------------------------------- system_voice_survival


ORIGINAL = "**TOLL PAID — 9 days**\nThe gate hummed.\n[STATUS] wren — Level 2\n"


def test_both_protected_spans_surviving_reports_two_kept_of_two():
    retell = ORIGINAL + "Extra prose around them changes nothing."
    assert writer_states.system_voice_survival(ORIGINAL, retell) == {
        "spans": 2,
        "kept": 2,
    }


def test_a_dropped_status_line_leaves_the_bold_span_as_the_only_one_kept():
    retell = "**TOLL PAID — 9 days**\nThe gate hummed.\n"
    assert writer_states.system_voice_survival(ORIGINAL, retell) == {
        "spans": 2,
        "kept": 1,
    }


def test_a_mangled_bold_span_is_not_counted_as_kept():
    # One character inside the bold header differs, so that span is lost even though the
    # STATUS line survived byte-for-byte.
    retell = "**TOLL PAID, 9 days**\nThe gate hummed.\n[STATUS] wren — Level 2\n"
    assert writer_states.system_voice_survival(ORIGINAL, retell) == {
        "spans": 2,
        "kept": 1,
    }


def test_an_original_without_protected_spans_reports_none_and_keeps_none():
    assert writer_states.system_voice_survival(
        "Plain prose carries no system voice.", "Plain prose carries no system voice."
    ) == {"spans": 0, "kept": 0}


def test_an_empty_retell_keeps_no_protected_span():
    assert writer_states.system_voice_survival(ORIGINAL, "") == {"spans": 2, "kept": 0}


# ------------------------------------------------------------------------- verdict


def _bias(rate: float) -> dict[str, dict[str, float]]:
    return {arm: {"chose_A_rate": rate} for arm in ("drunk", "trip", "tea")}


def test_a_rate_above_the_tea_floor_reads_preferred():
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.70, "trip": 0.30}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "PREFERRED"
    assert ladder["tea_floor"] == pytest.approx(0.0)
    assert ladder["tea_rate"] == pytest.approx(0.5)
    assert ladder["tea_clean"] is True
    assert "conditions" in ladder


def test_a_rate_below_the_tea_floor_reads_rejected():
    ladder = writer_states.verdict({"tea": 0.50, "trip": 0.30}, _bias(0.50))
    assert ladder["arms"]["trip"]["verdict"] == "REJECTED"


def test_a_rate_within_the_tea_floor_reads_inert_in_either_direction():
    # Tea at 0.44 sets the floor at 0.06; both 0.55 and 0.46 sit inside it.
    ladder = writer_states.verdict({"tea": 0.44, "drunk": 0.55, "trip": 0.46}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "INERT"
    assert ladder["arms"]["trip"]["verdict"] == "INERT"


def test_a_rate_exactly_on_the_tea_floor_is_inert():
    # Tea at 0.45 sets the floor at 0.05; 0.55 sits exactly on it and must read inert.
    ladder = writer_states.verdict({"tea": 0.45, "drunk": 0.55}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "INERT"


def test_a_rate_above_the_tea_floor_but_under_the_margin_reads_inert():
    # Zero floor, yet 0.59 is still under the 0.10 pre-registered margin.
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.59}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "INERT"


def test_a_rate_exactly_at_sixty_percent_reads_preferred():
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.60}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "PREFERRED"


def test_a_rate_exactly_at_forty_percent_reads_rejected():
    ladder = writer_states.verdict({"tea": 0.50, "trip": 0.40}, _bias(0.50))
    assert ladder["arms"]["trip"]["verdict"] == "REJECTED"


def test_a_biased_tea_arm_leaves_state_arms_unbounded():
    bias = {arm: {"chose_A_rate": 0.5} for arm in ("drunk", "trip")}
    bias["tea"] = {"chose_A_rate": 0.90}
    ladder = writer_states.verdict(
        {"tea": 0.62, "drunk": 0.70, "trip": 0.30},
        bias,
    )
    assert ladder["arms"]["drunk"]["verdict"] == "UNBOUNDED"
    assert ladder["arms"]["trip"]["verdict"] == "UNBOUNDED"
    assert ladder["tea_floor"] is None
    assert ladder["tea_clean"] is False


def test_an_unmeasured_tea_arm_leaves_state_arms_unbounded():
    ladder = writer_states.verdict({"drunk": 0.70}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "UNBOUNDED"
    assert ladder["tea_floor"] is None


def test_a_missing_rate_voids_that_arm():
    ladder = writer_states.verdict({"tea": 0.50}, _bias(0.50))
    assert ladder["arms"]["drunk"]["verdict"] == "VOID"


def test_a_missing_bias_entry_voids_that_arm():
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.70}, {})
    assert ladder["arms"]["drunk"]["verdict"] == "VOID"


def test_a_positional_bias_exactly_at_forty_percent_still_clears_the_precondition():
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.70}, _bias(0.40))
    assert ladder["arms"]["drunk"]["verdict"] == "PREFERRED"


def test_a_positional_bias_above_sixty_percent_voids_its_arm():
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.70}, _bias(0.61))
    assert ladder["arms"]["drunk"]["verdict"] == "VOID"


def test_an_integer_bias_value_does_not_clear_the_precondition():
    # Only a float rate clears the precondition; an int is treated as absent data.
    bias = {
        "drunk": {"chose_A_rate": 1},
        "trip": {"chose_A_rate": 0.5},
        "tea": {"chose_A_rate": 0.5},
    }
    ladder = writer_states.verdict({"tea": 0.50, "drunk": 0.70}, bias)
    assert ladder["arms"]["drunk"]["verdict"] == "VOID"


# --------------------------------------------------- writer_system and retell_turn


def test_writer_system_opens_with_the_identity_and_ends_with_the_state_block():
    prompt = writer_states.writer_system("drunk")
    assert prompt.startswith("You are a novelist")
    assert prompt.endswith(writer_states.STATES["drunk"])


def test_writer_system_varies_the_state_block_while_holding_the_identity_fixed():
    sober = writer_states.writer_system("sober")
    drunk = writer_states.writer_system("drunk")
    identity = "You are a novelist midway through drafting a serialized LitRPG novel"
    assert sober[: len(identity)] == drunk[: len(identity)]
    assert sober != drunk


def test_every_defined_state_renders_into_the_system_prompt():
    for state, block in writer_states.STATES.items():
        prompt = writer_states.writer_system(state)
        assert prompt.endswith(block)
        assert len(prompt) > len(block)


def test_writer_system_raises_on_an_unknown_state_key():
    with pytest.raises(KeyError):
        writer_states.writer_system("hallucinating")


def test_retell_turn_frames_the_scene_between_the_craft_rules_and_the_separator():
    scene = "Kade stepped through the gate and did not look back."
    turn = writer_states.retell_turn(scene)
    assert turn.startswith(writer_states.CRAFT_RULES)
    assert writer_states.CRAFT_RULES + "\n\n---\n\n" + scene == turn


def test_retell_turn_preserves_the_scene_byte_for_byte():
    scene = "Line one\nLine two — ok \n"
    assert writer_states.retell_turn(scene).endswith(scene)


def test_an_empty_scene_still_renders_the_craft_frame():
    assert writer_states.retell_turn("") == writer_states.CRAFT_RULES + "\n\n---\n\n"
