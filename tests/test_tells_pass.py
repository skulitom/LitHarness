"""The surgical pass: located sentences said again in one batch per family, verified by the
locator one by one, or left.

No model call: `complete` is a fake that answers scripted batches. The pass may not touch a page
under the shelf's ceiling, may not touch a book with no shelf, may not keep a rewrite the
locator still finds a shape in, and may not spend more than two calls on a family.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from litharness.application import tells_pass
from litharness.domain import tells
from litharness.domain.generation import CompletionRequest

PLAIN = "Ryan drove because Nick was still shaking. The plate came up with the bar."
ABSENT = "He mapped the storm drains for a hobby nobody understood."
PAGE = f"{PLAIN}\n\n{ABSENT} It was late."
ZERO = dict.fromkeys(tells.FAMILIES, 0.0)


def _answering(*batches: Mapping[str, Any] | None):
    """A fake provider answering the scripted batches in order, then the last one forever."""
    seen: list[CompletionRequest] = []

    def complete(request: CompletionRequest) -> Mapping[str, Any] | None:
        seen.append(request)
        index = min(len(seen) - 1, len(batches) - 1)
        return batches[index]

    complete.seen = seen  # type: ignore[attr-defined]
    return complete


def _batch(*texts: str) -> dict[str, Any]:
    return {"sentences": [{"label": f"S{i + 1}", "text": text} for i, text in enumerate(texts)]}


def test_a_located_sentence_over_the_shelf_is_said_again_and_the_rate_falls() -> None:
    complete = _answering(_batch("He mapped the storm drains for a hobby of his own."))
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 1 and result.left == 0 and result.calls == 1
    assert result.before[tells.ABSENCE] > 0.0 and result.after[tells.ABSENCE] == 0.0
    assert "hobby of his own" in result.text
    assert PLAIN in result.text and "It was late." in result.text
    request = complete.seen[0]  # type: ignore[attr-defined]
    assert "[S1]" in request.prompt and ABSENT in request.prompt
    assert "The sentence before it" not in request.prompt, "first in its paragraph"
    assert "It was late." in request.prompt, "the sentence after it rides for its facts"
    assert tells_pass.FAMILY_ASKS[tells.ABSENCE] in (request.system or "")
    assert request.profile == tells_pass.REWRITE_PROFILE
    assert request.schema is tells_pass.SCHEMA


def test_a_family_s_sentences_travel_in_one_request_and_only_the_refused_go_out_again() -> None:
    page = "\n\n".join([ABSENT, "Nothing came up the drain.", PLAIN])
    first = _batch("He mapped the storm drains for a hobby of his own.", "Nobody ever came.")
    second = _batch("Water came up the drain.")
    complete = _answering(first, second)
    result = tells_pass.apply(page, limits=ZERO, complete=complete)
    assert result.calls == 2 and result.rewritten == 2 and result.left == 0
    assert result.after[tells.ABSENCE] == 0.0
    retry = complete.seen[1]  # type: ignore[attr-defined]
    assert "Nothing came up the drain." in retry.prompt
    assert "hobby nobody understood" not in retry.prompt, "the accepted one does not go again"


def test_a_rewrite_that_trades_one_family_for_another_is_refused() -> None:
    """§199.1: on pilot 24's redraw the echo rose while absence fell. A sentence said again
    without its absence but with a phrase repeated is not a sentence said again."""
    traded = "He mapped the storm drains, mapped the storm drains, for a hobby of his own."
    assert tells.ECHO in {item.family for item in tells.locate(traded)}
    complete = _answering(
        _batch(traded), _batch("He mapped the storm drains for a hobby of his own.")
    )
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 1 and result.calls == 2
    assert "hobby of his own." in result.text
    assert "mapped the storm drains, mapped" not in result.text


def test_a_rewrite_the_locator_still_finds_after_two_tries_is_left() -> None:
    complete = _answering(
        _batch("Nobody ever understood the hobby."), _batch("Nothing about it made sense.")
    )
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 0 and result.left == 1 and result.calls == 2
    assert result.text == PAGE


def test_a_split_answer_is_joined_and_kept_when_it_clears_the_shape() -> None:
    """§199.3: the chained-and ask asks for more than one sentence, and the first version
    refused every answer that came back on two lines."""
    chained = (
        "I had one resit left, sports science, and I kept not sitting it, and she kept telling "
        "her sister I'd graduated, and that's about the size of me."
    )
    page = f"{PLAIN}\n\n{chained} It was late."
    complete = _answering(
        _batch(
            "I had one resit left, sports science.\nI kept not sitting it. She kept telling "
            "her sister I'd graduated. That was the size of me."
        )
    )
    result = tells_pass.apply(page, limits=ZERO, complete=complete)
    assert result.rewritten == 1 and result.after[tells.CHAINED_AND] == 0.0
    assert "\n" not in result.text.split("\n\n")[1]
    assert "It was late." in result.text


def test_a_failed_call_or_a_runaway_answer_leaves_the_sentence() -> None:
    too_long = " ".join(["word"] * 60)
    complete = _answering(None, _batch(too_long))
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 0 and result.left == 1 and result.text == PAGE


def test_a_page_under_the_shelf_and_a_book_with_no_shelf_are_untouched() -> None:
    complete = _answering(_batch("anything"))
    generous = dict.fromkeys(tells.FAMILIES, 1000.0)
    result = tells_pass.apply(PAGE, limits=generous, complete=complete)
    assert result.text == PAGE and result.calls == 0
    assert result.detail.endswith("nothing over the shelf")
    none = tells_pass.apply(PAGE, limits=None, complete=complete)
    assert none.text == PAGE and none.calls == 0 and none.before == none.after


def test_the_pass_stops_at_the_ceiling_rather_than_rewriting_every_sentence() -> None:
    page = "\n\n".join([ABSENT, "Nothing came up the drain.", PLAIN])
    words = tells.word_count(page)
    # One absence per page is the shelf's rate here: the pass sends one and stops.
    limits = {**ZERO, tells.ABSENCE: 1000.0 / words}
    complete = _answering(_batch("He mapped the storm drains for a hobby of his own."))
    result = tells_pass.apply(page, limits=limits, complete=complete)
    assert result.rewritten == 1 and result.calls == 1
    assert result.after[tells.ABSENCE] <= limits[tells.ABSENCE]
    request = complete.seen[0]  # type: ignore[attr-defined]
    assert "[S2]" not in request.prompt, "only as many as the ceiling asks"


def test_the_rewrite_ask_names_the_sentences_and_no_rule_about_the_page() -> None:
    system = tells_pass.rewrite_system(tells.CHAINED_AND)
    assert "Return only JSON" in system
    assert tells_pass.FAMILY_ASKS[tells.CHAINED_AND] in system
    assert tells_pass.FAMILY_ASKS[tells.ABSENCE] not in system, "one family's line, not all"
