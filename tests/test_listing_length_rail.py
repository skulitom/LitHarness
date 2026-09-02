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
