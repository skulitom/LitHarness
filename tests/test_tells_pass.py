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
    assert "[S2]" in request.prompt, "every located sentence travels (§199.7)"
    assert "Nothing came up the drain." in result.text, (
        "but only as many as the ceiling asks go back"
    )


def test_the_rewrite_ask_names_the_sentences_and_no_rule_about_the_page() -> None:
    system = tells_pass.rewrite_system(tells.CHAINED_AND)
    assert "Return only JSON" in system
    assert tells_pass.FAMILY_ASKS[tells.CHAINED_AND] in system
    assert tells_pass.FAMILY_ASKS[tells.ABSENCE] not in system, "one family's line, not all"


def test_a_long_sentence_is_said_again_as_shorter_ones_and_kept_under_the_shelf_s_longest() -> None:
    """§199.4: the ask names the shelf's number; an answer that is still one long sentence is
    refused by the locator, and one that came back as two short ones is kept."""
    long_one = (
        "He got them turned in the chamber under the apron, took them back along the route "
        "with the man first, the woman after, the kid in scrubs last, silent."
    )
    assert len(long_one.split()) > 20 and not tells.locate(long_one), "long and nothing else"
    page = f"{PLAIN}\n\n{long_one} It was late."
    limits = {**ZERO, tells.LONG_WORDS: 20.0}
    still_long = (
        "He got them turned in the chamber under the apron and took them back with the man "
        "first, the woman after, the kid in scrubs last, silent, all of it."
    )
    assert len(still_long.split()) > 20
    two = "He got them turned in the chamber under the apron. He took them back, the man first."
    complete = _answering(_batch(still_long), _batch(two))
    result = tells_pass.apply(page, limits=limits, complete=complete)
    assert result.rewritten == 1 and result.left == 0 and result.calls == 2
    assert result.before[tells.LONG] > 0.0 and result.after[tells.LONG] == 0.0
    assert two in result.text and "It was late." in result.text
    request = complete.seen[0]  # type: ignore[attr-defined]
    assert "none longer than 20 words" in (request.system or "")
    assert "{long_words}" not in (request.system or "")
    assert tells_pass.rewrite_system(tells.CHAINED_AND) == tells_pass.rewrite_system(
        tells.CHAINED_AND, long_words=20.0
    ), "the number reaches only the long family's ask"


def test_the_absence_ask_names_its_words_and_a_verbatim_answer_is_refused() -> None:
    """§199.7: asked to say what is there rather than what is not, the model gave back three of
    eleven sentences unchanged and kept *nothing* in three more; the ask now names the words,
    like the located habit's, and the locator refuses the unchanged sentence as before."""
    ask = tells_pass.FAMILY_ASKS[tells.ABSENCE]
    assert "'nobody'" in ask and "'nothing'" in ask and "'not'" in ask
    complete = _answering(
        _batch(ABSENT), _batch("He mapped the storm drains for a hobby of his own.")
    )
    result = tells_pass.apply(PAGE, limits=ZERO, complete=complete)
    assert result.rewritten == 1 and result.calls == 2


def test_whole_sentence_families_go_first_so_a_split_clears_the_words_too() -> None:
    """§199.7: a sentence carrying the long family and an absence is asked of the long family
    first; split into two short sentences with the absence gone, nothing is left for the
    absence batch and it makes no call."""
    long_absent = (
        "He mapped the storm drains for a hobby nobody understood, and he walked them at night "
        "with a torch in his teeth and a notebook in his back pocket, every foot of it on his "
        "boots."
    )
    page = f"{PLAIN}\n\n{long_absent}"
    limits = {**ZERO, tells.LONG_WORDS: 20.0}
    complete = _answering(
        _batch(
            "He mapped the storm drains for a hobby of his own. He walked them at night with a "
            "torch in his teeth."
        )
    )
    result = tells_pass.apply(page, limits=limits, complete=complete)
    assert result.calls == 1 and result.rewritten == 1 and result.left == 0
    first = complete.seen[0]  # type: ignore[attr-defined]
    assert tells_pass.FAMILY_ASKS[tells.LONG].split("{")[0] in (first.system or "")
    assert result.after[tells.ABSENCE] == 0.0 and result.after[tells.LONG] == 0.0
    assert tells_pass.PASS_ORDER[0] == tells.LONG and tells_pass.PASS_ORDER[-1] == tells.ABSENCE
    assert set(tells_pass.PASS_ORDER) == set(tells.FAMILIES)


def test_the_batch_carries_every_located_sentence_and_puts_back_the_earliest_accepted() -> None:
    """§199.7: three absences, a ceiling that allows one; all three travel, the model clears
    all three, and the two earliest go back so the page sits at the shelf's rate."""
    page = "\n\n".join([ABSENT, "Nothing came up the drain.", "Nobody answered.", PLAIN])
    words = tells.word_count(page)
    limits = {**ZERO, tells.ABSENCE: 1000.0 / words}
    complete = _answering(
        _batch(
            "He mapped the storm drains for a hobby of his own.",
            "Water came up the drain.",
            "The line stayed silent.",
        )
    )
    result = tells_pass.apply(page, limits=limits, complete=complete)
    assert result.calls == 1 and result.rewritten == 2 and result.left == 0
    assert "hobby of his own" in result.text and "Water came up the drain." in result.text
    assert "Nobody answered." in result.text, "the third stays: the shelf has absences too"
    assert result.after[tells.ABSENCE] <= limits[tells.ABSENCE]
