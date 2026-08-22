"""What the pure windowing arithmetic of taste_calibration pins, checked by hand.

These tests cover only `excerpt`, `window` and `stakes_window`: paragraph alignment, the
one-fifth / three-tenths entry points, the word-budget stop, the single-newline fallback,
and the stake-vocabulary density selection with its sixty-percent floor. Every expected
string below is derived from the function's code on constructed input whose answer is
stated before running anything.

They establish nothing about the experiment itself: no corpus read, no model call, no arm
scheduling, no report reading, and no claim that stake vocabulary measures actual stakes —
`stake_score`'s own docstring refuses that, and so do these tests.
"""

from __future__ import annotations

import pytest

taste_calibration = pytest.importorskip(
    "taste_calibration",
    reason="research module; needs the quality-measurement directory on the path",
)


def _para(tag: str, words: int, stake_words: tuple[str, ...] = ()) -> str:
    """A `words`-word paragraph whose tokens are lexicon-inert unless `stake_words` says so."""
    fillers = [f"{tag}w{index}" for index in range(words - len(stake_words))]
    return " ".join(list(stake_words) + fillers)


# --------------------------------------------------------------------------- excerpt


def test_excerpt_starts_a_fifth_in_and_returns_paragraphs_until_the_budget_is_met():
    paras = [_para(f"p{i}", 10) for i in range(1, 11)]  # 10 x 10 = 100 words
    text = "\n\n".join(paras)
    # target = int(0.2 * 100) = 20 -> first block reached after 20 words is index 2;
    # picking stops once 30 words are gathered: blocks 2, 3, 4.
    assert taste_calibration.excerpt(text, words=30) == \
        "\n\n".join([paras[2], paras[3], paras[4]])


def test_excerpt_returns_every_paragraph_when_total_words_equal_the_budget():
    paras = [_para(f"p{i}", 25) for i in range(1, 5)]  # 4 x 25 = 100 words
    text = "\n\n".join(paras)
    assert taste_calibration.excerpt(text, words=100) == text


def test_excerpt_one_word_short_of_the_budget_windows_instead_of_returning_everything():
    paras = [_para(f"p{i}", 25) for i in range(1, 5)]  # same text, 100 words
    text = "\n\n".join(paras)
    # target = int(0.2 * 100) = 20 -> after block 0 the seen count is already 25 >= 20,
    # so the window starts at index 1 and runs to the end of the text.
    assert taste_calibration.excerpt(text, words=99) == \
        "\n\n".join([paras[1], paras[2], paras[3]])


def test_excerpt_falls_back_to_single_newlines_when_double_newlines_yield_one_block():
    lines = [_para(f"l{i}", 10) for i in range(1, 7)]  # 6 x 10 = 60 words
    text = "\n".join(lines)
    # Double-newline splitting finds one block, so the fallback splits on "\n" instead:
    # target = int(0.2 * 60) = 12 -> start at line index 2, stop at 20 words: lines 2 and 3.
    # Picked blocks are rejoined with blank lines even though they were split on single ones.
    assert taste_calibration.excerpt(text, words=20) == "\n\n".join([lines[2], lines[3]])


def test_excerpt_of_empty_text_is_empty_string_without_raising():
    assert taste_calibration.excerpt("", words=30) == ""


def test_excerpt_of_whitespace_only_text_returns_the_text_unchanged():
    text = "\n\n   \n\n\t\n\n"
    assert taste_calibration.excerpt(text, words=30) == text


# ----------------------------------------------------------------------------- window


def test_window_cuts_in_three_tenths_deep_until_the_word_budget():
    paras = [_para(f"p{i}", 10) for i in range(1, 11)]  # 10 x 10 = 100 words
    text = "\n\n".join(paras)
    # target = int(0.3 * 100) = 30 -> first block reached after 30 words is index 3;
    # picking stops once 25 words are gathered: blocks 3, 4, 5.
    assert taste_calibration.window(text, words=25) == \
        "\n\n".join([paras[3], paras[4], paras[5]])


def test_window_of_empty_text_is_empty_string_without_raising():
    assert taste_calibration.window("") == ""


def test_window_of_text_shorter_than_the_budget_returns_everything():
    text = "alpha beta gamma delta"
    assert taste_calibration.window(text, words=700) == text


# ---------------------------------------------------------------------- stakes_window


def test_stakes_window_selects_the_run_with_highest_stake_vocabulary_density():
    paras = [_para(f"p{i}", 10) for i in range(8)]
    paras[3] = _para("d3", 10, ("danger",))
    paras[4] = _para("d4", 10, ("danger",))
    text = "\n\n".join(paras)
    # Budget 20 -> every candidate window is two blocks. Only blocks 3+4 carry stake
    # vocabulary (score 1 each), so density 2/20 beats every other start's 1/20 or 0.
    assert taste_calibration.stakes_window(text, words=20) == \
        "\n\n".join([paras[3], paras[4]])


def test_stakes_window_keeps_the_earliest_of_two_equally_dense_runs():
    paras = [_para(f"p{i}", 10) for i in range(8)]
    for index in (1, 2, 5, 6):
        paras[index] = _para(f"d{index}", 10, ("danger",))
    text = "\n\n".join(paras)
    # Runs 1+2 and 5+6 both score 2/20; the comparison is strict, so the later tie never
    # displaces the earlier run.
    assert taste_calibration.stakes_window(text, words=20) == \
        "\n\n".join([paras[1], paras[2]])


def test_stakes_window_does_not_pick_a_denser_start_whose_remaining_words_are_below_floor():
    paras = [
        _para("a", 30),
        _para("b", 30, ("danger",)),          # score 1
        _para("c", 30, ("danger",)),          # score 1
        _para("d", 30),
        _para("e", 20, ("danger", "death", "ruin", "doom", "fail")),  # score 5
    ]
    text = "\n\n".join(paras)
    # Budget 100, floor 60. Starts 0-2 evaluate (densities 2/120, 7/110, 6/80); start 2
    # wins at 6/80. Start 3 has only 50 remaining words < 60, so it is never evaluated —
    # its 5/50 would otherwise beat start 2. The pick runs blocks 2, 3, 4 to exhaustion.
    assert taste_calibration.stakes_window(text, words=100) == "\n\n".join(paras[2:])


def test_stakes_window_of_empty_text_is_empty_string_without_raising():
    assert taste_calibration.stakes_window("", words=1000) == ""


def test_stakes_window_of_text_far_shorter_than_the_budget_returns_the_whole_text():
    text = "alpha beta\ngamma delta"
    # Total 10 words against a 600-word floor: nothing qualifies as a start, so every
    # block is picked — and blocks are always rejoined with blank lines, even when the
    # fallback split them on single newlines.
    assert taste_calibration.stakes_window(text, words=1000) == "alpha beta\n\ngamma delta"

