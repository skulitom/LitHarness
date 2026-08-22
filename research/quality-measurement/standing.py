"""Where the protagonist stands, scene by scene, read off a book's own record. No model.

**Counters only, and no bar.** `plan/handoff-numbers-go-up.md` boundary 4: how often a standing
should move is the operator's to set over a measured distribution, and this file is one leg of
that distribution. Every number here is descriptive, nothing is admitted to the axis registry,
nothing gates anything, and no direction is declared for any quantity — not one of them has a
direction anybody has earned. `BRIEF.md` §2 is the ledger of what happens to a proxy declared
before its control ran.

**It measures a declared fact, not a judgment.** A standing is `subject stands_at → rung` on a
chain the world declared; a rise is that rung's 1-based place in the chain going up. There is no
reading of whether the rise was earned, whether it landed, or whether the prose around it is any
good — those are the questions this project has no instrument for, and inventing one here would
be the shallow-because-easy metric §1a.1 refuses.

Four things it can see and one it cannot, stated so the table is not read as more than it is:

- it sees **canon** standings, which are the ones the *page printed* plus the one the forge
  declared at the opening. A scheduled standing is `PROPOSED` and is counted separately, as a
  plan rather than as an event;
- it sees the **graph lines** a book printed, by counting what `extract_graph_facts` read back —
  so a line the world never declared a form for is invisible here exactly as it is to the parser;
- it sees the **cost** channel only as far as the summary's own `DELTA` fields go: whether the
  scene reported a value shift at all, and whether the summary names something paid;
- it sees **every other subject**'s standings beside the protagonist's, which is P4;
- it does **not** see a rise the prose narrated without printing the declared line. That is the
  measurement's own blind spot and the reason the graph-line rule exists upstream: the chain is
  *declare → ask → print → read*, and a book that skips *print* reads here as a book that did
  not rise.

Runs under `uv run python` — it imports the package and opens a book database. The RoyalRoad
shards are not involved, so there is no second interpreter here.

    uv run python research/quality-measurement/standing.py --database serial5.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

import litharness_contracts as lc  # noqa: E402

from litharness.domain import extraction as extraction_mod  # noqa: E402
from litharness.domain import state as state_mod  # noqa: E402
from litharness.domain import worlds as worlds_mod  # noqa: E402

#: The summary fields a cost shows up in, if it shows up at all. `application/summarize.py`
#: owns the ask; this only reads what came back. Named here rather than imported so that a
#: change to the ask is a visible mismatch rather than a silent re-definition of "paid".
_COST_WORDS = (
    "paid",
    "pays",
    "pay",
    "cost",
    "costs",
    "gave up",
    "gives up",
    "forfeit",
    "spent",
    "spends",
    "lost",
    "loses",
    "surrender",
    "traded",
)


@dataclass
class Move:
    """One change of standing on the record, with everything a reader of the table needs."""

    subject: str
    criterion: str
    order_key: str
    rung: str
    index: int | None
    previous: int | None
    canon: bool
    #: The scene whose prose this was read off, from the record's own evidence span. `None` for
    #: a standing the forge declared and for one the outline scheduled — neither came off a page.
    logical_id: str | None = None

    @property
    def direction(self) -> str:
        if self.index is None or self.previous is None:
            return "unplaced"
        if self.index > self.previous:
            return "rise"
        if self.index < self.previous:
            return "drop"
        return "lateral"


@dataclass
class BookStanding:
    """Everything this file can say about one book, as counts."""

    database: str
    book_id: str
    branch_id: str
    protagonist: str | None
    criterion: str | None
    chain: tuple[str, ...] = ()
    moves: list[Move] = field(default_factory=list)
    scheduled: list[Move] = field(default_factory=list)
    others: dict[str, list[Move]] = field(default_factory=dict)
    graph_lines_read: int = 0
    words: int = 0
    scenes: int = 0
    first_rise_scene: int | None = None
    first_rise_word_offset: int | None = None
    scenes_between_rises: list[int] = field(default_factory=list)
    summaries: int = 0
    delta_non_null: int = 0
    zero_delta_findings: int = 0
    priced_rises: int = 0

    def to_jsonable(self) -> dict[str, Any]:
        rises = [move for move in self.moves if move.direction == "rise"]
        return {
            "database": self.database,
            "book_id": self.book_id,
            "protagonist": self.protagonist,
            "criterion": self.criterion,
            "chain": list(self.chain),
            "rungs": len(self.chain),
            "scenes": self.scenes,
            "words": self.words,
            "canon_standings": len(self.moves),
            "rises": len(rises),
            "drops": sum(1 for move in self.moves if move.direction == "drop"),
            "lateral": sum(1 for move in self.moves if move.direction == "lateral"),
            "scheduled_standings": len(self.scheduled),
            "scheduled_rises": sum(
                1 for move in self.scheduled if move.direction == "rise"
            ),
            "first_rise_scene": self.first_rise_scene,
            "first_rise_word_offset": self.first_rise_word_offset,
            "scenes_between_rises": self.scenes_between_rises,
            "graph_lines_read": self.graph_lines_read,
            "graph_lines_per_1k_words": (
                round(1000 * self.graph_lines_read / self.words, 3) if self.words else None
            ),
            "summaries": self.summaries,
            "delta_non_null": self.delta_non_null,
            "zero_delta_findings": self.zero_delta_findings,
            "priced_rises": self.priced_rises,
            # P4: the same counts for everyone else, so "the protagonist's" is a count beside
            # another count and never a bar. Nobody is ranked here.
            "other_subjects": {
                subject: {
                    "standings": len(moves),
                    "rises": sum(1 for move in moves if move.direction == "rise"),
                }
                for subject, moves in sorted(self.others.items())
            },
        }


def _records(connection: sqlite3.Connection, book_id: str, branch_id: str) -> list[lc.StateRecord]:
    rows = connection.execute(
        "SELECT record_json FROM state_records WHERE book_id = ? AND branch_id = ? "
        "AND retracted_by_revision_id IS NULL",
        (book_id, branch_id),
    ).fetchall()
    return [lc.from_jsonable(lc.StateRecord, json.loads(row[0])) for row in rows]


def _moves(
    records: Sequence[lc.StateRecord], subject: str, *, canon: bool
) -> list[Move]:
    """This subject's standings in story order, each with the rung it left behind.

    Canon and proposals are read apart rather than merged: the page and the plan are different
    claims and a table that added them would report a book as having risen because somebody
    scheduled a rise.
    """
    rows = [
        record
        for record in records
        if record.predicate == worlds_mod.STANDS_AT_PREDICATE
        and record.object_ref
        and record.subject == subject
        and state_mod.is_canon(record) is canon
    ]
    rows.sort(key=lambda record: state_mod.order_key_of(record) or "")
    out: list[Move] = []
    previous: int | None = None
    for record in rows:
        criterion = str(record.value or "").strip() or worlds_mod.criterion_of_rung(
            records, record.object_ref or ""
        )
        index = (
            worlds_mod.rung_index(records, criterion, record.object_ref or "")
            if criterion
            else None
        )
        out.append(
            Move(
                subject=subject,
                criterion=criterion or "",
                order_key=state_mod.order_key_of(record) or "",
                rung=record.object_ref or "",
                index=index,
                previous=previous,
                canon=canon,
                logical_id=next(
                    (span.source.logical_id for span in record.evidence), None
                ),
            )
        )
        if index is not None:
            previous = index
    return out


def measure(database: Path) -> BookStanding:
    """One book's standings, prose and summaries, with no model anywhere in the path."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        book_id, branch_id = connection.execute(
            "SELECT book_id, branch_id FROM plan_revisions LIMIT 1"
        ).fetchone()
        records = _records(connection, book_id, branch_id)
        summary_rows = connection.execute(
            "SELECT logical_id, summary, delta_json FROM scene_summaries "
            "WHERE book_id = ? AND branch_id = ?",
            (book_id, branch_id),
        ).fetchall()
        zero_delta = connection.execute(
            "SELECT COUNT(*) FROM findings WHERE book_id = ? AND branch_id = ? "
            "AND subtype = 'zero_delta'",
            (book_id, branch_id),
        ).fetchone()[0]
    finally:
        connection.close()

    canon = [record for record in records if state_mod.is_canon(record)]
    subjects = worlds_mod.entities_with_role(canon, "protagonist")
    protagonist = subjects[0] if subjects else None
    chain: tuple[str, ...] = ()
    criterion: str | None = None
    if protagonist is not None:
        standing = worlds_mod.standing_of(records, protagonist)
        if len(standing) == 1:
            [(criterion, _)] = standing.items()
            chain = worlds_mod.ladder_of(records, criterion)

    note = BookStanding(
        database=str(database),
        book_id=book_id,
        branch_id=branch_id,
        protagonist=protagonist,
        criterion=criterion,
        chain=chain,
        summaries=len(summary_rows),
        delta_non_null=sum(1 for row in summary_rows if row["delta_json"]),
        zero_delta_findings=int(zero_delta),
    )
    if protagonist is not None:
        note.moves = _moves(records, protagonist, canon=True)
        note.scheduled = _moves(records, protagonist, canon=False)

    # Every other subject that carries a standing, which is P4. Read off canon and reported as
    # a count beside the protagonist's, never as a comparison anybody wins.
    on_a_ladder = {
        record.subject
        for record in canon
        if record.predicate == worlds_mod.STANDS_AT_PREDICATE and record.object_ref
    } - {protagonist}
    note.others = {
        subject: _moves(records, subject, canon=True) for subject in sorted(on_a_ladder)
    }

    _read_prose(note, database, records)
    _price(note, summary_rows)
    return note


def _read_prose(
    note: BookStanding, database: Path, records: Sequence[lc.StateRecord]
) -> None:
    """Scene count, word count, printed graph lines, and where the first rise sits in words.

    Imported lazily and failing soft: a store whose export path cannot resolve a branch is a
    store this leg says nothing about, and a crashing counter would take the whole table with
    it. What it cannot read is recorded as `None` rather than as zero — `BRIEF.md`'s standing
    rule that an absent measurement is not a measured absence.
    """
    try:
        import corpus_io
    except ImportError:  # pragma: no cover - the loader is beside this file
        return
    try:
        units = corpus_io.generated_scenes(database, min_words=0)
    except Exception:
        return

    note.scenes = len(units)
    note.words = sum(unit.words for unit in units)
    line = extraction_mod.graph_line_for(
        [record for record in records if state_mod.is_canon(record)]
    )
    if line is not None:
        note.graph_lines_read = sum(
            len(line.pattern.findall(unit.text)) for unit in units
        )

    rises = [move for move in note.moves if move.direction == "rise"]
    if not rises:
        return
    # **The scene is the one the record's own evidence names, not one derived from an ordinal.**
    # `domain/state.py` forbids deriving an order key from a scene and the inverse is no safer:
    # a standing read off prose carries the span it was read from, and that span carries the
    # logical id. A rise with no evidence — the forge's opening declaration — is not a rise the
    # page produced and contributes no offset.
    positions = {unit.unit_id.removeprefix("gen:"): unit.position for unit in units}
    by_position = {unit.position: unit for unit in units}
    placed = [
        positions[move.logical_id]
        for move in rises
        if move.logical_id and move.logical_id in positions
    ]
    if not placed:
        return
    note.first_rise_scene = placed[0]
    note.first_rise_word_offset = sum(
        by_position[position].words
        for position in sorted(by_position)
        if position <= placed[0]
    )
    note.scenes_between_rises = [
        later - earlier for earlier, later in pairwise(placed)
    ]


def _price(note: BookStanding, summary_rows: Sequence[sqlite3.Row]) -> None:
    """P5: for each rise read back, does the same scene's summary name a cost. A count only.

    A word list, and it is named as a word list. It cannot tell a price paid from a price
    mentioned, and it is reported because it is checkable rather than because it is the
    question — the same caveat `chapter_endings.is_dialogue` carries for the same reason.
    """
    if not note.moves:
        return
    by_scene = {
        row["logical_id"]: f"{row['summary'] or ''} {row['delta_json'] or ''}".casefold()
        for row in summary_rows
    }
    note.priced_rises = sum(
        1
        for move in note.moves
        if move.direction == "rise"
        and move.logical_id
        and any(word in by_scene.get(move.logical_id, "") for word in _COST_WORDS)
    )


def render(notes: Sequence[BookStanding]) -> str:
    """One table. Descriptive, and it says so in the last line rather than in a footnote."""
    header = (
        "| book | rungs | scenes | rises | drops | lateral | scheduled rises | "
        "first rise (scene / words) | graph lines / 1k | DELTA non-null | priced rises |"
    )
    lines = [header, "|" + "---|" * 11]
    for note in notes:
        body = note.to_jsonable()
        first = (
            f"{body['first_rise_scene']} / {body['first_rise_word_offset']}"
            if body["first_rise_scene"] is not None
            else "—"
        )
        per_1k = body["graph_lines_per_1k_words"]
        lines.append(
            f"| {Path(note.database).name} | {body['rungs']} | {body['scenes']} | "
            f"{body['rises']} | {body['drops']} | {body['lateral']} | "
            f"{body['scheduled_rises']} | {first} | "
            f"{per_1k if per_1k is not None else '—'} | "
            f"{body['delta_non_null']} of {body['summaries']} | {body['priced_rises']} |"
        )
    lines.append("")
    lines.append(
        "Descriptive. No bar is declared for any column: how often a standing should move is "
        "the operator's to set over this distribution, and a rise the prose narrated without "
        "printing the declared line is invisible to every column here."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        action="append",
        required=True,
        help="a book database to read; repeatable",
    )
    parser.add_argument("--json", type=Path, help="write the per-book counts here")
    args = parser.parse_args(argv)

    notes = [measure(Path(name)) for name in args.database]
    print(render(notes))
    if args.json:
        args.json.write_text(
            json.dumps([note.to_jsonable() for note in notes], indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
