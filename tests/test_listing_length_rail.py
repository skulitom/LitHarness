"""The listing's second shape rail: no sentence longer than the shelf's own listings run to.

Read 17 (`plan/reader-read-17.md` §3.1): a thirty-three-word sentence the operator *had to
decrypt*, chained on commas and *because* where the coordinator counter looks for *and*. The
ceiling is read off the blurbs the operator placed on the shelf (stage-0 §196), so the number is
the market's; with no shelf there is no ceiling and the loop is byte-identical to what it was.
Arithmetic over text, never a judgment; a listing under the ceiling is not good, it is merely
not that.
"""

from __future__ import annotations

from litharness.application import overview


def _sentence(words: int) -> str:
    return " ".join(f"w{index}" for index in range(words)) + "."


BLURBS = (
    f"{_sentence(4)} {_sentence(9)} {_sentence(2)}",
    f"{_sentence(6)} {_sentence(14)}",
)


def test_the_longest_sentence_is_counted_in_words_and_split_on_stops() -> None:
    assert overview.longest_sentence("One two three. Four five? Six!") == 3
    assert overview.longest_sentence("") == 0
    assert overview.longest_sentence("No stop at the end at all") == 7
    assert overview.longest_sentence(BLURBS[0]) == 9


#: Draw 2 of the restored-directions draw (read 20), our own output: a sentence that ends inside
#: its closing quote, then a paragraph break. The old splitter read the two as one 14-word
#: sentence (stage-0 §262).
DRAW_2 = (
    "Anchor lets him brace a makeshift bridge. Reedstep could carry him across fragile "
    "vegetation. Everyone else gets one permanent skill. His interface reads \u201cSkill "
    "capacity: Unbounded.\u201d\n\n"
    "Each new ability starts at Skill Rank 0. Raising his Personal Rank takes harder trials, "
    "not just collecting kernels."
)


def test_a_closing_quote_or_a_paragraph_break_ends_a_sentence() -> None:
    parts = overview.sentences(DRAW_2)
    assert len(parts) == 6
    assert "His interface reads \u201cSkill capacity: Unbounded.\u201d" in parts
    assert "Each new ability starts at Skill Rank 0." in parts
    # Saved on disk the listing has Windows line ends; the split is the same.
    assert overview.sentences(DRAW_2.replace("\n", "\r\n")) == parts
    assert overview.sentences("A line with no stop\n\nThen a sentence.") == [
        "A line with no stop",
        "Then a sentence.",
    ]
    assert overview.sentences("She said 'Go.' He went.") == ["She said 'Go.'", "He went."]
    assert overview.longest_sentence(DRAW_2) == 11
    # The shelf's ceiling is counted by the same splitter, so it moves with the listing's side.
    assert overview.sentence_ceiling([DRAW_2]) == 11


def test_a_dialogue_attribution_stays_with_its_quote() -> None:
    """A closing quote after . ! or ? and then a lowercase word is an attribution, not a new
    sentence: the splitter before §262 kept it with its quote, and a split there would shorten
    a shelf blurb's longest sentence and lengthen a run of short ones (stage-0 §262)."""
    assert overview.sentences('"Run!" she said. Then she ran.') == [
        '"Run!" she said.',
        "Then she ran.",
    ]
    assert overview.sentences("“Question?” he asked.") == ["“Question?” he asked."]
    assert overview.sentences("'Go.'  he said, and went.") == ["'Go.'  he said, and went."]
    # A capital after the quote still starts a sentence, as it did.
    assert overview.sentences("She said 'Go.' He went.") == ["She said 'Go.'", "He went."]
    assert overview.longest_sentence('"Run!" she yelled at the dark.') == 6


def test_the_ceiling_is_the_shelf_s_longest_and_none_without_a_shelf() -> None:
    assert overview.sentence_ceiling(BLURBS) == 14
    assert overview.sentence_ceiling(()) is None
    assert overview.sentence_ceiling(("", "   ")) is None


def test_a_listing_runs_too_long_only_against_a_ceiling() -> None:
    long = f"{_sentence(3)} {_sentence(15)}"
    assert overview.longest_sentence(long) == 15
    assert overview.runs_too_long(long, ceiling=14)
    assert not overview.runs_too_long(long, ceiling=15)
    # No shelf, no ceiling: the loop as it was.
    assert not overview.runs_too_long(long, ceiling=None)
