"""The status line as a panel: what draws one, what deliberately does not, and what it escapes.

The tests worth reading are the two divergences. This renderer is *looser* than the canon
parser on purpose — it draws a sheet whose numbers canon would refuse, because a reader who
cannot see the panel has no way to tell why. And it is *stricter* than a substring search on
purpose — a paragraph that mentions the system is prose, and half a paragraph in a table is
worse than none of it.
"""

from __future__ import annotations

from litharness.application.statusline import (
    parse_status_line,
    status_block,
    status_table_classed,
    status_table_inline,
)
from tests.conftest import FIXTURE_SHEET

LINE = "[STATUS] Mira Kell — Hold 3 | Carried 2/3 | Mending 4"


def test_a_status_line_names_its_subject_and_its_columns() -> None:
    status = parse_status_line(LINE)
    assert status is not None
    assert status.subject == "Mira Kell"
    assert status.cells == (("Hold", "3"), ("Carried", "2/3"), ("Mending", "4"))


def test_the_value_is_the_last_word_so_a_two_word_label_survives() -> None:
    """`Rain Tally 3` is one column with a two-word name, not a column called `Rain`."""
    status = parse_status_line("[STATUS] Aster — Rain Tally 3 | Debt 0")
    assert status is not None
    assert status.cells == (("Rain Tally", "3"), ("Debt", "0"))


def test_a_column_with_nothing_to_split_keeps_its_row() -> None:
    """A bare state word is still something the sheet says; dropping it would be the renderer
    editing the book."""
    status = parse_status_line("[STATUS] Aster — Poisoned | Debt 0")
    assert status is not None
    assert status.cells[0] == ("Poisoned", "")


def test_the_panel_is_a_table_headed_by_the_character() -> None:
    """The name is a spanning header cell rather than a caption: a caption is the element a
    rich-text editor is likeliest to drop, and losing it leaves numbers belonging to nobody."""
    status = parse_status_line(LINE)
    assert status is not None
    panel = status_table_classed(status)
    assert panel.startswith('<table class="status">')
    assert '<th colspan="2" scope="colgroup">Mira Kell</th>' in panel
    assert '<tr><th scope="row">Hold</th><td>3</td></tr>' in panel
    assert '<tr><th scope="row">Carried</th><td>2/3</td></tr>' in panel


def test_the_pastable_panel_carries_styles_and_no_class() -> None:
    """A fragment has no head by construction, so the only styling it can carry is inline —
    which is also the half a rich-text editor keeps when it drops the class."""
    status = parse_status_line(LINE)
    assert status is not None
    panel = status_table_inline(status)
    assert "class=" not in panel and "id=" not in panel
    assert panel.count("style=") == 1 + 1 + 2 * len(status.cells)
    assert "currentColor" in panel, "the panel has to read on a page whose palette it cannot see"


def test_a_line_canon_would_refuse_still_draws() -> None:
    """The deliberate divergence. `domain.extraction` knows the book's declared labels and
    wants numbers; this module knows the shape. A renderer that drew only accepted lines would
    leave the reader looking at raw text for a reason invisible from the page."""
    line = "[STATUS] Mira Kell — Hold three | Carried 2/3"
    assert FIXTURE_SHEET.pattern.search(line) is None
    assert parse_status_line(line) is not None


def test_prose_that_merely_mentions_the_system_is_not_a_panel() -> None:
    block = "She read it off the sheet. [STATUS] Mira Kell — Hold 3"
    assert parse_status_line(block) is None
    assert status_block(block, inline=True) is None


def test_a_block_is_a_panel_only_when_every_line_is_one() -> None:
    """Two sheets are two panels. One sheet and a sentence is a paragraph."""
    both = f"{LINE}\n[STATUS] Aster — Debt 0"
    rendered = status_block(both, inline=False)
    assert rendered is not None and rendered.count("<table") == 2
    assert status_block(f"{LINE}\nAnd then she closed it.", inline=False) is None


def test_a_line_without_the_dash_is_left_alone() -> None:
    """The shape is the contract. `library` still sets an unparseable system line apart as a
    blockquote, which is what the fixture line has always been."""
    assert parse_status_line("[STATUS] Rook - Level 2, HP 19/22") is None
    assert parse_status_line("[SKILL] Mending — Hold 3") is None


def test_the_panel_escapes_its_text() -> None:
    """A stray `<` swallows everything up to the next `>` and the loss is silent — the reason
    every other renderer here escapes, applied to the one that builds markup from a name."""
    status = parse_status_line("[STATUS] <Mira> — Hold <3")
    assert status is not None
    panel = status_table_classed(status)
    assert "&lt;Mira&gt;" in panel and "&lt;3" in panel
    assert "<Mira>" not in panel
