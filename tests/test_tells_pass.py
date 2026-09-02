"""The surgical pass: one located sentence said again, verified by the locator, or left.

No model call: `complete` is a fake that answers with scripted sentences. The pass may not
touch a page under the shelf's ceiling, may not touch a book with no shelf, and may not keep a
rewrite the locator still finds the family in.
"""

from __future__ import annotations

from litharness.application import tells_pass
from litharness.domain import tells
from litharness.domain.generation import CompletionRequest

PLAIN = "Ryan drove because Nick was still shaking. The plate came up with the bar."
ABSENT = "He mapped the storm drains for a hobby nobody understood."
PAGE = f"{PLAIN}\n\n{ABSENT} It was late."
ZERO = dict.fromkeys(tells.FAMILIES, 0.0)


def _answering(*answers: str | None):
    """A fake provider answering the scripted sentences in order, then the last one forever."""
    seen: list[CompletionRequest] = []

    def complete(request: CompletionRequest) -> str | None:
        seen.append(request)
        index = min(len(seen) - 1, len(answers) - 1)
        return answers[index]

    complete.seen = seen  # type: ignore[attr-defined]
    return complete


def test_a_located_sentence_over_the_shelf_is_said_again_and_the_rate_falls() -> None:
    complete = _answering("He mapped the storm drains for a hobby of his own.")
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 1 and result.left == 0 and result.calls == 1
    assert result.before[tells.ABSENCE] > 0.0 and result.after[tells.ABSENCE] == 0.0
    assert "hobby of his own" in result.text
    assert PLAIN in result.text and "It was late." in result.text
    request = complete.seen[0]  # type: ignore[attr-defined]
    assert ABSENT in request.prompt
    assert "The sentence before it:" not in request.prompt, "first in its paragraph"
    assert "It was late." in request.prompt, "the sentence after it rides for its facts"
    assert tells_pass.FAMILY_ASKS[tells.ABSENCE] in (request.system or "")
    assert request.profile == tells_pass.REWRITE_PROFILE


def test_a_rewrite_the_locator_still_finds_is_refused_and_the_sentence_is_left() -> None:
    complete = _answering("Nobody ever understood the hobby.", "Nothing about it made sense.")
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 0 and result.left == 1 and result.calls == 2
    assert result.text == PAGE


def test_a_failed_call_or_a_runaway_answer_leaves_the_sentence() -> None:
    too_long = " ".join(["word"] * 60)
    complete = _answering(None, too_long)
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 0 and result.left == 1 and result.text == PAGE


def test_a_page_under_the_shelf_and_a_book_with_no_shelf_are_untouched() -> None:
    complete = _answering("anything")
    generous = dict.fromkeys(tells.FAMILIES, 1000.0)
    result = tells_pass.apply(PAGE, limits=generous, complete=complete)
    assert result.text == PAGE and result.calls == 0
    assert result.detail.endswith("nothing over the shelf")
    none = tells_pass.apply(PAGE, limits=None, complete=complete)
    assert none.text == PAGE and none.calls == 0 and none.before == none.after


def test_the_pass_stops_at_the_ceiling_rather_than_rewriting_every_sentence() -> None:
    page = "\n\n".join([ABSENT, "Nothing came up the drain.", PLAIN])
    words = tells.word_count(page)
    # One absence per page is the shelf's rate here: the pass rewrites one and stops.
    limits = {**ZERO, tells.ABSENCE: 1000.0 / words}
    complete = _answering(
        "He mapped the storm drains for a hobby of his own.", "Water came up the drain."
    )
    result = tells_pass.apply(page, limits=limits, complete=complete)
    assert result.rewritten == 1 and result.calls == 1
    assert result.after[tells.ABSENCE] <= limits[tells.ABSENCE]


def test_the_rewrite_ask_names_one_sentence_and_no_rule_about_the_page() -> None:
    system = tells_pass.rewrite_system(tells.CHAINED_AND)
    assert "one sentence" in system and "Return only the sentence" in system
    assert tells_pass.FAMILY_ASKS[tells.CHAINED_AND] in system
    assert tells_pass.FAMILY_ASKS[tells.ABSENCE] not in system, "one family's line, not all"
