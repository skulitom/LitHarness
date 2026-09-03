"""`tools/replay_books.py`: a stored book replays identically, a tampered one does not, and
the store on disk is never written to.

The four real stores live under the primary checkout's gitignored `runs/`, so the suite
cannot replay them; what it can pin is the tool's three rules on a book built here the way the
draft handler builds one — a root revision with an empty scene, the seed written beside it, a
`scene_draft` job carrying the plan-stated position, and the accepted revision committed with
the records `extract_state` minted from the scene's own line.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import litharness_contracts as lc

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.handlers import SCENE_DRAFT
from litharness.domain import extraction, worlds
from litharness.domain.jobs import Job
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import build_revision, node_version_id
from tools.replay_books import compare_with_baseline, main, replay_store

BOOK = "22222222-2222-5222-8222-222222222222"
BRANCH = "33333333-3333-5333-8333-333333333333"
PROJECT = "11111111-1111-5111-8111-111111111111"

_SHEET = {
    "fields": [
        {"label": "Seamwork", "name": "rung", "paired": False},
        {"label": "Reach", "name": "reach", "paired": False},
        {"label": "Carried", "name": "carried", "paired": True},
    ]
}
_OPENING = {"carried": 4, "carried_max": 5, "reach": 3, "rung": 2}

SCENE = "Mira counted the seams twice.\n\n[STATUS] Mira — Seamwork 2 | Reach 4 | Carried 3/5\n"
OTHER = "Mira counted the seams twice.\n\n[STATUS] Mira — Seamwork 3 | Reach 4 | Carried 3/5\n"


def _seed() -> list[lc.StateRecord]:
    canon = lc.StateAuthority.ACCEPTED_CANON
    return [
        worlds.world_record("mira", extraction.SHEET_PREDICATE, value=_SHEET, authority=canon),
        worlds.world_record("mira", extraction.STATUS_PREDICATE, value=_OPENING, authority=canon),
        worlds.world_record(
            "mira", worlds.ENTITY_ROLE_PREDICATE, value="protagonist", authority=canon
        ),
    ]


def _write_book(path: Path, *, drafted: str, stored_from: str) -> tuple[lc.StateRecord, ...]:
    """A book whose accepted scene prints `drafted`, with the records minted from
    `stored_from` beside it; the two differ only in the tampered case."""
    book = Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")
    empty = Node(
        logical_id="scene-1", kind=NodeKind.SCENE, position_key="020", parent_logical_id="book"
    )
    root = build_revision(BOOK, BRANCH, [book, empty])
    with SqliteStore.open(path) as store:
        store.commit_revision(root, created_at="2026-09-03T00:00:00Z")
        store.record_state_records(BOOK, BRANCH, _seed(), created_at="2026-09-03T00:00:01Z")
        store.enqueue(
            Job(
                job_id="beat-scene-1",
                job_kind=SCENE_DRAFT,
                payload={
                    "revision_id": root.revision_id,
                    "logical_id": "scene-1",
                    "prompt": "",
                    "selected_by": {"story_order_key": "s1", "ordinal": 1, "of_total": 1},
                },
            )
        )
        known = tuple(store.state_records(BOOK, BRANCH))
        scene = Node.text_node("scene-1", NodeKind.SCENE, "020", drafted, parent_logical_id="book")
        source = Node.text_node(
            "scene-1", NodeKind.SCENE, "020", stored_from, parent_logical_id="book"
        )
        minted = extraction.extract_state(
            source.content or "",
            known=known,
            project_id=PROJECT,
            book_id=BOOK,
            branch_id=BRANCH,
            logical_id="scene-1",
            version_id=node_version_id(source),
            stated_order_key="s1",
        )
        accepted = build_revision(BOOK, BRANCH, [book, scene], parent=root.revision_id)
        store.commit_revision(accepted, created_at="2026-09-03T00:00:02Z", state_records=minted)
    return minted


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_book_drafted_through_the_handler_replays_identically_and_is_not_written_to(
    tmp_path: Path,
) -> None:
    database = tmp_path / "book" / "serial.db"
    database.parent.mkdir()
    minted = _write_book(database, drafted=SCENE, stored_from=SCENE)
    assert [record.predicate for record in minted] == [extraction.STATUS_PREDICATE]
    before = _digest(database)

    report = replay_store(database.parent, scratch=tmp_path / "scratch")

    assert _digest(database) == before, "the replay wrote to the store it was reading"
    (book,) = report["books"]
    (scene,) = book["scenes"]
    assert scene["skipped"] is None
    assert scene["identical"], scene["differences"]
    assert scene["expected"] == scene["replayed"] == [minted[0].record_id]
    assert scene["position"] == "s1"
    # The seed, as the handler saw it: three records, none of this scene's own.
    assert scene["known"] == 3
    assert (
        scene["derived"]["system_voice_example"]
        == "[STATUS] Mira — Seamwork 2 | Reach 4 | Carried 3/5"
    )
    assert scene["derived"]["state_as_it_stands"][1] == {
        "carried": 3,
        "carried_max": 5,
        "reach": 4,
        "rung": 2,
    }


def test_a_store_whose_records_do_not_match_its_prose_is_reported_line_by_line(
    tmp_path: Path,
) -> None:
    database = tmp_path / "book" / "serial.db"
    database.parent.mkdir()
    _write_book(database, drafted=SCENE, stored_from=OTHER)

    report = replay_store(database, scratch=tmp_path / "scratch")

    (scene,) = report["books"][0]["scenes"]
    assert not scene["identical"]
    assert any(line.startswith("stored but not re-minted") for line in scene["differences"])
    assert any(line.startswith("re-minted but not stored") for line in scene["differences"])


def test_the_command_reports_and_exits_nonzero_only_on_a_difference_or_a_moved_baseline(
    tmp_path: Path, capsys: object
) -> None:
    good = tmp_path / "good" / "serial.db"
    good.parent.mkdir()
    _write_book(good, drafted=SCENE, stored_from=SCENE)
    baseline = tmp_path / "before.json"
    assert main(["--store", str(good.parent), "--out", str(baseline)]) == 0
    assert main(["--store", str(good.parent), "--baseline", str(baseline)]) == 0

    # A baseline from a different book: the derived lines and the minted ids have moved.
    other = tmp_path / "other" / "serial.db"
    other.parent.mkdir()
    _write_book(other, drafted=OTHER, stored_from=OTHER)
    assert main(["--store", str(other.parent), "--baseline", str(baseline)]) == 1
    report = json.loads(baseline.read_text(encoding="utf-8"))
    moved = compare_with_baseline(report, report)
    assert moved == []

    bad = tmp_path / "bad" / "serial.db"
    bad.parent.mkdir()
    _write_book(bad, drafted=SCENE, stored_from=OTHER)
    assert main(["--store", str(bad.parent)]) == 1
    # An absent store is reported and skipped, never a failure: a fresh clone has no books.
    assert main(["--store", str(tmp_path / "nowhere")]) == 0


def test_a_scene_that_sits_in_the_root_revision_is_skipped_as_never_drafted(
    tmp_path: Path,
) -> None:
    database = tmp_path / "serial.db"
    book = Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")
    scene = Node.text_node("scene-1", NodeKind.SCENE, "020", SCENE, parent_logical_id="book")
    with SqliteStore.open(database) as store:
        store.commit_revision(
            build_revision(BOOK, BRANCH, [book, scene]), created_at="2026-09-03T00:00:00Z"
        )
    report = replay_store(database, scratch=tmp_path / "scratch")
    (entry,) = report["books"][0]["scenes"]
    assert entry["skipped"] is not None
    assert "root revision" in entry["skipped"]
