"""The exemplar shelf (stage-0 §196): what crosses, how it is framed, and what may not come back.

The operator reversed RS1 on 2026-09-02 for openings he placed on a shelf by hand. These tests
pin the containment that made the reversal safe: a shelf is loaded only from a directory the
operator names and never written; it reaches the writer as a headed block in the prompt and one
prohibition in the system; the ladder refuses a draft that shares a run of consecutive words
with an exemplar; absent a shelf every prompt, listing and ladder is byte-identical to what it
was; and the reviser is off unless asked for.

No model call, no store, no corpus: every shelf here is written under `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litharness.application import exemplars, overview
from litharness.application.planner import render_prompt
from litharness.cli import build_parser
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain.patch import Veto
from litharness.domain.policy import RETRYABLE

_PH = (
    "It was just another dull Monday morning at the depot, and the belt had been running since "
    "ten with nobody watching it.\n\nBy noon every screen in the building showed the same three "
    "words, and the shed went quiet in a way it never had.\n\nThen the message told us what we "
    "were worth, one line each, and mine was not the line I expected to read."
)
_DOTF = (
    "The forest was silent when the sky went dark and the voice began.\n\nIt read out planets "
    "and grades and adjustments as though nobody were listening, and I was listening.\n\nWhen "
    "it asked me to roll I did not know what a roll was, and I rolled anyway."
)


def _shelf(tmp_path: Path, *, order: list[str] | None = None) -> Path:
    root = tmp_path / "shelf"
    for name, text, blurb in (
        ("PrimalHunter", _PH, "An ordinary Monday, and the world changed."),
        ("DefianceOfTheFall", _DOTF, None),
        ("TheGam3", "Alan cared only about the game.\n" * 40, "Aliens invaded."),
    ):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / exemplars.CHAPTER_FILE).write_text(text, encoding="utf-8")
        if blurb:
            (folder / exemplars.BLURB_FILE).write_text(blurb, encoding="utf-8")
    if order is not None:
        (root / exemplars.ORDER_FILE).write_text(json.dumps({"order": order}), encoding="utf-8")
    return root


def test_the_shelf_loads_in_the_operator_s_order_and_never_writes(tmp_path: Path) -> None:
    root = _shelf(tmp_path, order=["PrimalHunter", "DefianceOfTheFall", "TheGam3"])
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    shelf = exemplars.load_shelf(root)
    assert shelf is not None
    assert [e.name for e in shelf.exemplars] == ["PrimalHunter", "DefianceOfTheFall"]
    assert shelf.exemplars[0].title == "Primal Hunter"
    assert shelf.exemplars[0].blurb == "An ordinary Monday, and the world changed."
    assert shelf.exemplars[1].blurb is None
    assert sorted(str(p.relative_to(root)) for p in root.rglob("*")) == before
    # No order file: name order. A limit takes the first that many.
    unordered = exemplars.load_shelf(_shelf(tmp_path / "b"), limit=3)
    assert unordered is not None
    assert [e.name for e in unordered.exemplars] == ["DefianceOfTheFall", "PrimalHunter", "TheGam3"]
    assert exemplars.load_shelf(None) is None
    with pytest.raises(FileNotFoundError):
        exemplars.load_shelf(tmp_path / "nowhere")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="no folder"):
        exemplars.load_shelf(empty)


def test_a_long_chapter_is_cut_at_a_paragraph_and_a_single_newline_file_is_paragraphed(
    tmp_path: Path,
) -> None:
    root = _shelf(tmp_path, order=["TheGam3"])
    shelf = exemplars.load_shelf(root, limit=1, chapter_words=100)
    assert shelf is not None
    gam3 = shelf.exemplars[0]
    assert gam3.title == "The Gam3"
    assert 100 <= gam3.words < 110
    assert "\n\n" in gam3.chapter
    assert gam3.record() == {
        "name": "TheGam3", "title": "The Gam3", "digest": gam3.digest, "words": gam3.words,
    }
    assert "chapter" not in gam3.record()


def test_the_scene_prompt_carries_the_block_before_the_packet_and_the_system_one_sentence(
    tmp_path: Path,
) -> None:
    shelf = exemplars.load_shelf(_shelf(tmp_path, order=["PrimalHunter", "DefianceOfTheFall"]))
    beat = beats_domain.Beat(
        logical_id="s1", ordinal=1, of_total=1, title=None, function="setup",
        template_id=beats_domain.SIX_BEAT.template_id,
    )
    packet = context_domain.ContextPacket(
        query_id="exemplars", target_logical_id="s1", book_id="book", branch_id="main",
        base_revision_id="r0",
    )
    system, prompt = render_prompt(beat, book_title="Mine", packet=packet, shelf=shelf)
    plain_system, plain_prompt = render_prompt(beat, book_title="Mine", packet=packet)
    assert system == f"{plain_system}\n{exemplars.SHELF_SYSTEM}"
    assert prompt.startswith(exemplars.OPENINGS_HEADING)
    assert "— Primal Hunter, chapter one —" in prompt
    assert "— Defiance Of The Fall, chapter one —" in prompt
    assert prompt.endswith(plain_prompt)
    assert prompt.index(_DOTF.split("\n\n")[0]) < prompt.index("Now write")
    # The control: no shelf, nothing added.
    assert render_prompt(beat, book_title="Mine", packet=packet, shelf=None) == (
        plain_system, plain_prompt
    )


def test_the_listing_is_shown_the_blurbs_above_the_brief_and_only_when_there_are_any(
    tmp_path: Path,
) -> None:
    shelf = exemplars.load_shelf(_shelf(tmp_path, order=["PrimalHunter", "DefianceOfTheFall"]))
    assert shelf is not None
    block = exemplars.render_blurbs(shelf)
    assert block is not None
    assert block.startswith(exemplars.BLURBS_HEADING)
    assert "— Primal Hunter —\nAn ordinary Monday" in block
    assert "Defiance" not in block  # no blurb on disk, no entry
    shown = overview.render_overview_request("A cook.", None, blurbs=block)
    plain = overview.render_overview_request("A cook.", None)
    assert shown.system == plain.system
    assert shown.prompt == f"{block}\n\n{plain.prompt}"
    only_dotf = exemplars.load_shelf(_shelf(tmp_path / "d", order=["DefianceOfTheFall"]), limit=1)
    assert only_dotf is not None
    assert exemplars.render_blurbs(only_dotf) is None


def test_a_draft_that_lifts_a_run_from_an_exemplar_is_refused_and_a_short_echo_is_not(
    tmp_path: Path,
) -> None:
    shelf = exemplars.load_shelf(_shelf(tmp_path, order=["PrimalHunter", "DefianceOfTheFall"]))
    assert shelf is not None
    lifted = (
        "Owen went in. By noon every screen in the building showed the same three words, and "
        "he sat down."
    )
    gate = exemplars.gate_exemplar_leak(lifted, shelf)
    assert gate is not None
    assert gate.passed is False
    assert gate.blocking is True
    assert gate.vetoes == (Veto.EXEMPLAR_LEAK,)
    assert "Primal Hunter" in gate.detail
    assert Veto.EXEMPLAR_LEAK in RETRYABLE
    six = "Every screen in the building showed a different word."  # shares six, under the limit
    clean = exemplars.gate_exemplar_leak(six, shelf)
    assert clean is not None and clean.passed is True and clean.vetoes == ()
    assert exemplars.gate_exemplar_leak(lifted, None) is None
    found = exemplars.leak(lifted, shelf)
    assert found is not None
    assert found[0] == "Primal Hunter"
    assert found[1] >= exemplars.LEAK_RUN_WORDS
    assert exemplars.leak(six, shelf) is None


def test_the_flags_parse_and_the_reviser_is_off_unless_asked_for() -> None:
    parser = build_parser()
    args = parser.parse_args(["--exemplars", "somewhere", "--exemplars-limit", "3", "status"])
    assert args.exemplars == "somewhere"
    assert args.exemplars_limit == 3
    assert parser.parse_args(["status"]).exemplars == ""
    assert parser.parse_args(["status"]).revise is False
    assert parser.parse_args(["--revise", "status"]).revise is True
    # The old control flag still parses and changes nothing.
    assert parser.parse_args(["--no-revise", "status"]).revise is False
