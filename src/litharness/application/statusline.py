"""The system line, rendered as the panel the genre reads it as rather than as a sentence.

`[STATUS] Mira Kell — Hold 3 | Carried 2/3 | Mending 4` is a *display* in the fiction: the
character opens a sheet and reads columns off it. Every HTML surface this repository publishes
rendered it as running prose — an indented `<p>` in the reading copy, a `<blockquote>` in the
pastable chapter — so the one place in a chapter that is supposed to look like a machine
talking looked like a paragraph with pipes in it. Operator read 10 named it.

**This is a rendering module and holds no contract.** The `.txt` outputs and the writer's
instruction are untouched, and `domain/extraction.py` remains the only parser whose reading of
the line means anything: the line's own pattern is what canon is built from, and it is stricter than
this — it knows the book's declared field labels and requires their values to be numbers. The
pattern here knows only the shape, because a renderer that could not draw a panel for a line
canon had not accepted would leave the reader looking at the raw text for a reason invisible
from the page. The two are deliberately not the same regular expression, for the reason
`library._SYSTEM_LINE` is not `axes._SYSTEM_LINE`: a counter's definition and a renderer's
choice should be free to stop agreeing without one silently changing the other's meaning.

**Two renderings, because the two artifacts have opposite constraints.** A reading copy carries
a stylesheet, so it gets `class="status"` and nothing else. A pastable chapter has no `<head>`
by construction, so its table carries inline styles — which is also the half of CSS that
survives a paste into a rich-text editor, where a class name does not.

**A block becomes a panel only when the whole block is status lines.** A paragraph that merely
contains one is prose that mentions the system, and turning half of it into a table would lose
the other half.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

#: The shape, and only the shape. The subject runs to a dash because that is how both the
#: genre and the line's own template write it; the en dash is accepted beside the
#: em dash because a model that reaches for one reaches for the other. Both are written as
#: escapes rather than as themselves, so nobody has to tell three dashes apart in a diff.
_STATUS_LINE = re.compile(
    r"^\[STATUS\][^\S\n]*(?P<subject>[^\n|]*?)[^\S\n]*[\u2014\u2013][^\S\n]*"
    r"(?P<columns>[^\n]+)$"
)

#: One column split into what it is called and what it says. The value is the last run of
#: non-space characters, so a two-word label (`Rain Tally 3`) keeps both of its words.
_COLUMN = re.compile(r"^(?P<label>\S.*?)[^\S\n]+(?P<value>\S+)$")


@dataclass(frozen=True, slots=True)
class StatusLine:
    """One status line as a panel wants it: whose sheet, and what is on it."""

    subject: str
    #: Label and value per column. A column with nothing to split on keeps its whole text as
    #: the label and an empty value, so a bare state word still gets a row rather than being
    #: silently dropped.
    cells: tuple[tuple[str, str], ...]


def parse_status_line(line: str) -> StatusLine | None:
    """The panel this line describes, or `None` when it is not one.

    `None` rather than a raise: every block of prose in the book is offered to this function,
    and almost none of them are status lines.
    """
    match = _STATUS_LINE.match(line.strip())
    if match is None:
        return None
    subject = (match["subject"] or "").strip()
    if not subject:
        return None
    cells: list[tuple[str, str]] = []
    for raw in match["columns"].split("|"):
        column = " ".join(raw.split())
        if not column:
            continue
        parts = _COLUMN.match(column)
        cells.append((parts["label"], parts["value"]) if parts else (column, ""))
    if not cells:
        return None
    return StatusLine(subject=subject, cells=tuple(cells))


#: Inline styling for the pastable panel, held to the properties a serial platform's own table
#: editor writes onto cells — border, width, alignment, padding, weight, font — so nothing here
#: is a declaration a rich-text editor has to decide whether to keep. Colours are never fixed:
#: Royal Road flips pure white and pure black between its light and dark themes (its authors'
#: table guide records it), so every edge is drawn in `currentColor` and takes whatever the
#: reader's theme paints the text. Sizes are relative for the same reason: the panel cannot
#: see the page it lands on.
_EDGE = "border:1px solid currentColor;"
_PANEL = (
    "border-collapse:collapse;width:100%;"
    "font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.85em;line-height:1.45;"
)
_NAME = _EDGE + "text-align:left;padding:.45em .8em;font-weight:700;"
_LABEL = _EDGE + "text-align:left;padding:.38em .8em;font-weight:400;"
_VALUE = _EDGE + "text-align:right;padding:.38em .8em;font-weight:700;"


def _table(status: StatusLine, *, panel: str, name: str, label: str, value: str) -> str:
    """The one markup shape both renderings share; the four arguments are the only difference.

    The name is a spanning header cell rather than a `<caption>` because a caption is the
    element rich-text editors are likeliest to drop, and losing it would leave a panel of
    numbers belonging to nobody.
    """
    rows = "".join(
        f'<tr><th scope="row"{label}>{html.escape(cell_label)}</th>'
        f"<td{value}>{html.escape(cell_value)}</td></tr>"
        for cell_label, cell_value in status.cells
    )
    return (
        f"<table{panel}>"
        f'<thead><tr><th colspan="2" scope="colgroup"{name}>'
        f"{html.escape(status.subject)}</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def status_table_inline(status: StatusLine) -> str:
    """The panel for a document with no stylesheet: the pastable chapter, and the volume."""
    return _table(
        status,
        panel=f' style="{_PANEL}"',
        name=f' style="{_NAME}"',
        label=f' style="{_LABEL}"',
        value=f' style="{_VALUE}"',
    )


def status_table_classed(status: StatusLine) -> str:
    """The panel for a reading copy, which carries `export`'s stylesheet in its head."""
    return _table(status, panel=' class="status"', name="", label="", value="")


def status_block(block: str, *, inline: bool) -> str | None:
    """The panel for one block of prose, or `None` when the block is not one.

    Every line has to parse. A block holding two status lines is one character's sheet and
    another's, which is two panels; a block holding a status line and a sentence is prose.
    """
    lines = [line for line in block.strip().split("\n") if line.strip()]
    parsed = [parse_status_line(line) for line in lines]
    if not parsed or any(status is None for status in parsed):
        return None
    render = status_table_inline if inline else status_table_classed
    return "\n".join(render(status) for status in parsed if status is not None)


__all__ = [
    "StatusLine",
    "parse_status_line",
    "status_block",
    "status_table_classed",
    "status_table_inline",
]
