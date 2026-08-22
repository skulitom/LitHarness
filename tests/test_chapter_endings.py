"""Pins for the pure locator and descriptors in research/quality-measurement/chapter_endings.py.

These tests pin what the module's own docstrings claim about its pure functions: how blocks are
located and normalised around system voice, and what each deterministic counter answers on
hand-built text whose correct answer is stated before running anything.

They establish nothing beyond that: no corpus was measured, no rate has a direction, and no
claim is made here that any counter detects anything — the module itself declines to classify a
chapter-hook shape, so these tests cannot assert one either.
"""

from __future__ import annotations

import pytest

chapter_endings = pytest.importorskip(
    "chapter_endings",
    reason="research module; needs the quality-measurement directory on the path",
)

# -- _normalised -------------------------------------------------------------------------


def test_normalised_collapses_runs_of_whitespace_within_a_block():
    assert chapter_endings._normalised("Hello   world\n\t  again") == "Hello world again"


def test_normalised_removes_an_inline_status_line_but_keeps_the_lines_around_it():
    block = "He read it.\n[STATUS] x \u2014 y\nHe read it again."
    assert chapter_endings._normalised(block) == "He read it. He read it again."


def test_normalised_returns_empty_for_a_block_that_is_only_system_voice():
    assert chapter_endings._normalised("[STATUS] x \u2014 y") == ""


def test_normalised_returns_empty_for_an_empty_block():
    assert chapter_endings._normalised("") == ""


# -- paragraphs --------------------------------------------------------------------------


def test_paragraphs_keeps_blank_line_separated_blocks_in_order():
    assert chapter_endings.paragraphs("A.\n\nB.\n\nC.") == ["A.", "B.", "C."]


def test_paragraphs_splits_on_a_whitespace_only_separator_line():
    assert chapter_endings.paragraphs("A.\n \t \nB.") == ["A.", "B."]


def test_paragraphs_merges_a_block_carrying_an_inline_status_line_into_one_paragraph():
    text = "First.\n\nHe read it.\n[STATUS] x \u2014 y\nHe read it again.\n"
    assert chapter_endings.paragraphs(text) == ["First.", "He read it. He read it again."]


def test_paragraphs_drops_a_block_whose_only_sentence_carries_an_all_caps_tag():
    # `axes.strip_system` replaces any line carrying a bracketed all-caps tag, prose included,
    # so such a block normalises to nothing and must not be reported as a zero-word paragraph.
    assert chapter_endings.paragraphs("He wrote [NOTE] down.") == []


def test_paragraphs_returns_empty_list_for_a_text_that_is_only_system_voice():
    assert chapter_endings.paragraphs("[STATUS] x \u2014 y\n") == []


def test_paragraphs_returns_empty_list_for_an_empty_text():
    assert chapter_endings.paragraphs("") == []


# -- final_paragraph ---------------------------------------------------------------------


def test_final_paragraph_skips_a_trailing_system_line_to_reach_prose():
    status = "He put the ledger down.\n\n[STATUS] Silas \u2014 Loop 2 | Day 1\n"
    assert chapter_endings.final_paragraph(status) == "He put the ledger down."


def test_final_paragraph_joins_the_last_blocks_lines_around_an_inline_status_line():
    inline = "First.\n\nHe read it.\n[STATUS] x \u2014 y\nHe read it again.\n"
    assert chapter_endings.final_paragraph(inline) == "He read it. He read it again."


def test_final_paragraph_returns_empty_for_a_text_that_is_only_system_voice():
    assert chapter_endings.final_paragraph("[STATUS] x \u2014 y\n") == ""


def test_final_paragraph_returns_empty_for_an_empty_text():
    assert chapter_endings.final_paragraph("") == ""


# -- last_line ---------------------------------------------------------------------------


def test_last_line_returns_the_literal_last_non_empty_line_including_system_voice():
    status = "He put the ledger down.\n\n[STATUS] Silas \u2014 Loop 2 | Day 1\n"
    assert chapter_endings.last_line(status) == "[STATUS] Silas \u2014 Loop 2 | Day 1"


def test_last_line_preserves_surrounding_whitespace_on_that_line():
    text = "A.\n\n   tail line   "
    assert chapter_endings.last_line(text) == "   tail line   "


def test_last_line_returns_empty_when_every_line_is_blank():
    assert chapter_endings.last_line("  \n\t\n") == ""
    assert chapter_endings.last_line("") == ""


# -- is_system_line ----------------------------------------------------------------------


def test_is_system_line_true_for_a_bracketed_all_caps_tag_line():
    assert chapter_endings.is_system_line("[STATUS] Silas \u2014 Loop 2 | Day 1")


def test_is_system_line_true_for_a_prose_line_that_carries_an_all_caps_tag():
    assert chapter_endings.is_system_line("He wrote [NOTE] down.")


def test_is_system_line_false_for_plain_prose_and_for_lowercase_tags():
    assert not chapter_endings.is_system_line("He shrugged.")
    assert not chapter_endings.is_system_line("[status] lowercase")


def test_is_system_line_true_only_for_a_line_that_is_entirely_a_bold_span():
    assert chapter_endings.is_system_line("**Chapter Two**")
    assert not chapter_endings.is_system_line("plain **bold** plain")


def test_is_system_line_false_for_empty_and_whitespace_only_input():
    assert not chapter_endings.is_system_line("")
    assert not chapter_endings.is_system_line("   ")


# -- is_dialogue -------------------------------------------------------------------------


def test_is_dialogue_true_when_the_paragraph_opens_on_a_quote():
    assert chapter_endings.is_dialogue('"Ferrous."')
    assert chapter_endings.is_dialogue("\u201cCome in.\u201d")


def test_is_dialogue_true_when_narration_ends_on_a_quotation_mark():
    assert chapter_endings.is_dialogue('He shrugged. "Ferrous."')
    assert chapter_endings.is_dialogue("She waved. \u201cGo.\u201d")


def test_is_dialogue_true_for_a_paragraph_ending_on_an_apostrophe():
    assert chapter_endings.is_dialogue("goin'")


def test_is_dialogue_false_for_narration_even_when_it_ends_in_other_punctuation():
    # A question mark or full stop is not a quotation mark; this is a typographic fact only.
    assert not chapter_endings.is_dialogue("What now?")
    assert not chapter_endings.is_dialogue("He shrugged.")


def test_is_dialogue_false_for_an_empty_paragraph():
    assert not chapter_endings.is_dialogue("")


# -- ends_on_question --------------------------------------------------------------------


def test_ends_on_question_true_for_a_bare_question_with_trailing_whitespace():
    assert chapter_endings.ends_on_question("Did he?")
    assert chapter_endings.ends_on_question("Really?   ")


def test_ends_on_question_looks_past_a_closing_quote_after_the_mark():
    assert chapter_endings.ends_on_question('"You hear me?"')
    assert chapter_endings.ends_on_question("Ready?\u201d")


def test_ends_on_question_false_for_a_statement_quoted_or_not():
    assert not chapter_endings.ends_on_question("He did not ask.")
    assert not chapter_endings.ends_on_question("\u201cNever.\u201d")


def test_ends_on_question_false_for_an_empty_string():
    assert not chapter_endings.ends_on_question("")


# -- describe ----------------------------------------------------------------------------


def test_describe_counts_three_paragraphs_and_describes_final_and_penultimate():
    text = (
        "Opening scene.\n"
        "\n"
        '"You hear me?"\n'
        "\n"
        "The gate closed.\n"
        "[STATUS] SILAS \u2014 LOOP 2 | DAY 1\n"
        "He walked home.\n"
    )
    assert chapter_endings.describe(text) == {
        "paragraphs": 3,
        "final_words": 6,  # The gate closed. He walked home.
        "final_dialogue": False,
        "final_question": False,
        "last_line_is_system": False,
        "penultimate_words": 3,  # "You hear me?"
        "penultimate_dialogue": True,
        "penultimate_question": True,
    }


def test_describe_leaves_penultimate_fields_empty_for_a_single_paragraph_text():
    described = chapter_endings.describe("One paragraph only.")
    assert described["paragraphs"] == 1
    assert described["penultimate_words"] == 0
    assert described["penultimate_dialogue"] is False
    assert described["penultimate_question"] is False


def test_describe_reports_zero_words_when_the_text_is_only_system_voice():
    described = chapter_endings.describe("[STATUS] x \u2014 y\n")
    assert described["paragraphs"] == 0
    assert described["final_words"] == 0
    assert described["last_line_is_system"] is True
    assert described["final_dialogue"] is False
    assert described["final_question"] is False


def test_describe_reports_nothing_measurable_for_an_empty_text():
    described = chapter_endings.describe("")
    assert described["paragraphs"] == 0
    assert described["final_words"] == 0
    assert described["last_line_is_system"] is False
    assert described["final_dialogue"] is False
    assert described["final_question"] is False


# -- summarise ---------------------------------------------------------------------------


def test_summarise_of_no_rows_is_exactly_n_zero():
    assert chapter_endings.summarise([]) == {"n": 0}


def test_summarise_computes_rates_and_word_distribution_over_hand_counted_rows():
    def row(
        fw: int, pw: int, fd: bool, fq: bool, ll: bool, pd: bool, pq: bool
    ) -> dict[str, object]:
        return {
            "final_words": fw,
            "penultimate_words": pw,
            "final_dialogue": fd,
            "final_question": fq,
            "last_line_is_system": ll,
            "penultimate_dialogue": pd,
            "penultimate_question": pq,
        }

    rows = [
        row(10, 4, True, False, True, False, False),
        row(2, 8, False, True, False, True, True),
        row(6, 4, True, False, False, False, False),
    ]
    # final words sorted [2, 6, 10]: median 6, mean 6.0. Penultimate sorted [4, 4, 8]: median 4.
    # Dialogue 2/3, everything else 1/3 of three rows.
    assert chapter_endings.summarise(rows) == {
        "n": 3,
        "final_words": {"min": 2, "median": 6, "mean": 6.0, "max": 10},
        "penultimate_words_median": 4,
        "pct_final_dialogue": 66.67,
        "pct_final_question": 33.33,
        "pct_last_line_is_system": 33.33,
        "pct_penultimate_dialogue": 33.33,
        "pct_penultimate_question": 33.33,
    }


def test_summarise_aggregates_describe_rows_from_constructed_texts():
    heard = '"You hear me?"\n\nDid the gate close?'
    ran = 'He ran.\n\n"Why now?"\n'
    ended = "[STATUS] END \u2014 LOOP\n"
    summary = chapter_endings.summarise(
        [
            chapter_endings.describe(heard),
            chapter_endings.describe(ran),
            chapter_endings.describe(ended),
        ]
    )
    # Final words [4, 2, 0]: min 0, median 2, mean 2.0, max 4. Penultimate [3, 2, 0]: median 2.
    # Questions 2/3; dialogue, system tail and both penultimate rates 1/3 of three rows.
    assert summary == {
        "n": 3,
        "final_words": {"min": 0, "median": 2, "mean": 2.0, "max": 4},
        "penultimate_words_median": 2,
        "pct_final_dialogue": 33.33,
        "pct_final_question": 66.67,
        "pct_last_line_is_system": 33.33,
        "pct_penultimate_dialogue": 33.33,
        "pct_penultimate_question": 33.33,
    }


# -- the module's own selftest -----------------------------------------------------------


def test_module_selftest_passes_without_touching_any_substrate():
    chapter_endings.selftest()

