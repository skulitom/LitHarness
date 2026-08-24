"""Blinding's contract, checked without any corpus: identity out, craft untouched.

What this file pins (PREREG.md §4): every stripped class with a constructed positive that
asserts both the removal and the count, and a near-miss negative per class that must
survive; the paragraph-structure guarantees; the digest being sha256 of the blinded output,
stable across calls and sensitive to one byte; idempotence; the empty-text edge; and
`first_words`' extend-to-the-boundary rule. Every expected value below was derived by hand
from the design before anything ran. No parquet shard is touched and no network is used.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest"
if str(RESEARCH) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(RESEARCH))

import pytest  # noqa: E402

blinding = pytest.importorskip("blinding", reason="research module; imported by path")

#: sha256 of the empty byte string, computed by hand as the reference for empty output.
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ----------------------------------------------------------------------------------- title


def test_a_multiword_title_is_redacted_in_every_normalised_form_and_counted() -> None:
    blinded = blinding.blind(
        "The Ashborn Wake legend grew.\n\nHe cursed the ashborn wake quietly.",
        title="Ashborn Wake",
        author="Morgan Vale",
    )
    assert blinded.text == "The [redacted] legend grew.\n\nHe cursed the [redacted] quietly."
    assert blinded.removed["title"] == 2


def test_title_matching_unifies_quote_glyphs_and_collapsed_spaces() -> None:
    blinded = blinding.blind(
        "the king's shadow falls.\n\nUnder the KING\u2019S SHADOW they marched.",
        title="King\u2019s Shadow",
        author="Morgan Vale",
    )
    assert blinded.text == (
        "the [redacted] falls.\n\nUnder the [redacted] they marched."
    )
    assert blinded.removed["title"] == 2


def test_an_unmarked_lowercase_short_title_mid_sentence_survives() -> None:
    text = "the rise of the empire was swift."
    blinded = blinding.blind(text, title="Rise", author="Morgan Vale")
    assert blinded.text == text
    assert blinded.removed["title"] == 0


def test_a_short_title_with_distinguishing_typography_is_redacted_and_counted() -> None:
    blinded = blinding.blind(
        'The scroll read "Rise" in gold, and *Rise* glowed on the spine.',
        title="Rise",
        author="Morgan Vale",
    )
    assert blinded.text == (
        "The scroll read [redacted] in gold, and [redacted] glowed on the spine."
    )
    assert blinded.removed["title"] == 2


def test_a_titlecased_short_title_mid_sentence_is_redacted_but_not_at_a_sentence_start() -> None:
    blinded = blinding.blind(
        "Rise was all he said.\n\nthe comet's Rise began at dusk.",
        title="Rise",
        author="Morgan Vale",
    )
    assert blinded.text == "Rise was all he said.\n\nthe comet's [redacted] began at dusk."
    assert blinded.removed["title"] == 1


# ---------------------------------------------------------------------------------- author


def test_the_author_name_and_its_handle_forms_are_redacted_and_counted() -> None:
    blinded = blinding.blind(
        "Story by Morgan Vale, all rights reserved.\n\nMorgan Vale presents a tale.",
        title="Emberfall",
        author="Morgan Vale",
    )
    assert blinded.text == "Story [redacted], all rights reserved.\n\n[redacted] a tale."
    assert blinded.removed["author"] == 2




# ------------------------------------------------------------------------- chapter_heading


def test_chapter_heading_lines_are_removed_whole_and_counted() -> None:
    blinded = blinding.blind(
        "Chapter 1: Emberfall\nDawn came late.\nch. 2 - The Deep\nMore dawn.",
        title="Emberfall",
        author="Morgan Vale",
    )
    assert blinded.text == "Dawn came late.\nMore dawn."
    assert blinded.removed["chapter_heading"] == 2


def test_a_heading_word_on_an_eighty_one_character_line_survives_while_eighty_is_removed() -> None:
    line_80 = "Chapter " + "x" * 72  # exactly 80 characters
    line_81 = "Chapter " + "x" * 73  # one character over the limit
    assert len(line_80) == 80 and len(line_81) == 81
    blinded = blinding.blind(f"{line_80}\n\n{line_81}", title="Emberfall", author="Morgan Vale")
    assert blinded.text == line_81
    assert blinded.removed["chapter_heading"] == 1


def test_a_character_named_chapman_is_not_taken_for_a_chapter_heading() -> None:
    text = "Mrs Chapman opened the door."
    blinded = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    assert blinded.text == text
    assert blinded.removed["chapter_heading"] == 0


def test_a_sentence_about_being_parted_is_not_taken_for_a_part_heading() -> None:
    text = "She parted the curtains at dawn."
    blinded = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    assert blinded.text == text
    assert blinded.removed["chapter_heading"] == 0


# ------------------------------------------------------------------------------------- url


def test_url_tokens_are_removed_and_counted() -> None:
    blinded = blinding.blind(
        "Archived at https://example.com/fic/42 for readers.\n\nMirrors live at "
        "www.example.org now.",
        title="Emberfall",
        author="Morgan Vale",
    )
    # The token is removed in place; the surrounding spacing is prose-adjacent and left as is.
    assert blinded.text == "Archived at  for readers.\n\nMirrors live at  now."
    assert "http" not in blinded.text
    assert "www" not in blinded.text
    assert blinded.removed["url"] == 2


# -------------------------------------------------------------------------------- platform


def test_platform_plug_lines_are_removed_whole_and_counted() -> None:
    blinded = blinding.blind(
        "You can read ahead on Patreon.\n\nThe harbour bell rang twice.",
        title="Emberfall",
        author="Morgan Vale",
    )
    assert blinded.text == "The harbour bell rang twice."
    assert blinded.removed["platform"] == 1


def test_the_roadhouse_is_not_taken_for_royal_road() -> None:
    text = "The roadhouse smelled of rain and woodsmoke."
    blinded = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    assert blinded.text == text
    assert blinded.removed["platform"] == 0


# ----------------------------------------------------------------------------- author_note


def test_an_authors_note_block_is_removed_through_the_next_blank_line() -> None:
    blinded = blinding.blind(
        "Dawn came late.\n\nAuthor's note: thanks for reading! Next up on Friday.\n"
        "Enjoy, friends!\n\nDusk came earlier.",
        title="Emberfall",
        author="Morgan Vale",
    )
    assert blinded.text == "Dawn came late.\n\nDusk came earlier."
    assert blinded.removed["author_note"] == 1


def test_prose_mentioning_the_author_is_not_taken_for_an_authors_note() -> None:
    text = "The author noted the date in her journal.\n\nShe wrote all night."
    blinded = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    assert blinded.text == text
    assert blinded.removed["author_note"] == 0


# ------------------------------------------------------------------ paragraph structure


def test_paragraph_boundaries_are_preserved_when_nothing_spans_them() -> None:
    blinded = blinding.blind(
        "Emberfall burned first.\n\nNothing here is a marker.\n\nRemember Emberfall always.",
        title="Emberfall",
        author="Morgan Vale",
    )
    expected = (
        "[redacted] burned first.\n\nNothing here is a marker.\n\nRemember [redacted] always."
    )
    assert blinded.text == expected
    assert blinded.text.count("\n\n") == 2
    assert blinded.removed["title"] == 2


def test_a_fully_removed_paragraph_leaves_no_double_blank_residue() -> None:
    blinded = blinding.blind(
        "First prose stands.\n\nSupport me on Patreon!\n\nSecond prose follows.",
        title="Emberfall",
        author="Morgan Vale",
    )
    assert blinded.text == "First prose stands.\n\nSecond prose follows."
    assert "\n\n\n" not in blinded.text


def test_removing_a_support_plug_line_does_not_merge_its_neighbours() -> None:
    blinded = blinding.blind(
        "Top line stands.\nFind me on Patreon today.\nBottom line stands.",
        title="Emberfall",
        author="Morgan Vale",
    )
    assert blinded.text == "Top line stands.\nBottom line stands."
    assert blinded.text.count("\n") == 1

def test_an_author_name_inside_larger_words_survives() -> None:
    text = "She did it remarkably well.\n\nIt was written by Marker."
    blinded = blinding.blind(text, title="Emberfall", author="Mark")
    assert blinded.text == text
    assert blinded.removed["author"] == 0



# ---------------------------------------------------------------------------------- digest


def test_the_digest_is_the_sha256_of_the_blinded_output_and_stable_across_calls() -> None:
    text = "The harbour bell rang at dawn."
    first = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    second = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    assert first.digest == second.digest
    assert len(first.digest) == 64
    int(first.digest, 16)  # full-length lowercase hex
    assert first.digest == hashlib.sha256(first.text.encode("utf-8")).hexdigest()


def test_changing_one_byte_of_the_input_changes_the_digest() -> None:
    before = blinding.blind("The harbour bell rang.", title="Emberfall", author="Morgan Vale")
    after = blinding.blind("The Harbour bell rang.", title="Emberfall", author="Morgan Vale")
    assert before.digest != after.digest


# --------------------------------------------------------------------- idempotence / empty


def test_blinding_an_already_blinded_text_removes_nothing_and_changes_nothing() -> None:
    text = (
        "Chapter 1: Cold Open\n"
        "Vessa rode toward Emberfall.\n"
        "Story by Morgan Vale, apparently.\n"
        "\n"
        "Follow on Patreon!\n"
        "Author's note: enjoy!\n"
    )
    first = blinding.blind(text, title="Emberfall", author="Morgan Vale")
    assert first.text == "Vessa rode toward [redacted].\nStory [redacted], apparently."
    assert first.removed == {
        "title": 1,
        "author": 1,
        "chapter_heading": 1,
        "url": 0,
        "platform": 1,
        "author_note": 1,
    }
    second = blinding.blind(first.text, title="Emberfall", author="Morgan Vale")
    assert second.text == first.text
    assert all(count == 0 for count in second.removed.values())


def test_empty_text_returns_an_empty_blinded_with_all_zero_counts() -> None:
    blinded = blinding.blind("", title="Emberfall", author="Morgan Vale")
    assert blinded.text == ""
    assert blinded.digest == EMPTY_SHA256
    assert blinded.removed == dict.fromkeys(blinding.STRIPPED_CLASSES, 0)


# ------------------------------------------------------------------------------ first_words

FIRST_WORDS_TEXT = "one two three four five.\n\nSix seven eight nine."


def test_first_words_extend_to_the_end_of_the_paragraph_holding_word_n() -> None:
    # Word 2 sits mid-paragraph; cutting there would slice the paragraph in half, so the
    # whole first paragraph is shown instead.
    assert blinding.first_words(FIRST_WORDS_TEXT, 2) == "one two three four five."


def test_exactly_n_words_at_a_paragraph_boundary_stop_at_that_boundary() -> None:
    # The first paragraph holds exactly 5 words.
    assert blinding.first_words(FIRST_WORDS_TEXT, 5) == "one two three four five."


def test_n_words_crossing_a_boundary_pull_in_the_next_paragraph() -> None:
    # Word 6 is the paragraph-2 opener, so paragraph 2 must be shown whole.
    assert blinding.first_words(FIRST_WORDS_TEXT, 6) == FIRST_WORDS_TEXT


def test_fewer_than_n_words_returns_the_whole_text() -> None:
    text = "only three words here."
    assert blinding.first_words(text, 50) == text


def test_non_positive_n_returns_empty_without_crashing() -> None:
    assert blinding.first_words(FIRST_WORDS_TEXT, 0) == ""
    assert blinding.first_words(FIRST_WORDS_TEXT, -3) == ""
