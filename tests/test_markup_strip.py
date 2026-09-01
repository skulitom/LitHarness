"""The markup strip: markdown emphasis and headings leave the prose, the words stay, the count
comes back, and a machine line passes through untouched.

Pilot 21's first draw under the exemplar shelf printed `**Nobody**` on the pastable page
(`plan/serial-pilot-21.md` §5.1) — the one defect of the read that was a character rather than
a register, and so the one that gets `strip_em_dash`'s treatment rather than a clause.
"""

from __future__ import annotations

from litharness.domain.draft import strip_em_dash, strip_markup


def test_emphasis_and_headings_go_and_the_words_and_count_stay() -> None:
    text = (
        "# Chapter One\n\n"
        "At the top, where a name should have gone, one word: **Nobody**.\n\n"
        "She said *think status*, and I thought it. A **bold** claim and an *aside*.\n"
    )
    stripped, removed = strip_markup(text)
    assert stripped == (
        "Chapter One\n\n"
        "At the top, where a name should have gone, one word: Nobody.\n\n"
        "She said think status, and I thought it. A bold claim and an aside.\n"
    )
    assert removed == 5


def test_a_machine_line_and_a_scene_break_and_arithmetic_pass_through() -> None:
    text = (
        "[STATUS] Danny — Rank 1 | Push 1 | **Hold** 0\n\n"
        "* * *\n\n"
        "Three times four is 3 * 4, which is twelve.\n\n"
        "[OFFER] Class — Hand: opens Break | Wall: opens Bind\n"
    )
    stripped, removed = strip_markup(text)
    assert stripped == text
    assert removed == 0


def test_a_text_with_no_markers_is_returned_as_it_was() -> None:
    text = "Plain prose with nothing to remove.\n"
    assert strip_markup(text) == (text, 0)


def test_the_two_strips_compose_in_the_ladder_s_order() -> None:
    text = "He stood — and **waited**.\n"
    dashed, marks = strip_em_dash(text)
    stripped, markup = strip_markup(dashed)
    assert marks == 1
    assert markup == 1
    assert stripped == "He stood, and waited.\n"
