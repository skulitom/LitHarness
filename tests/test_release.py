"""The release queue: an operator moves a chapter's copy through four states, and no program
posts it (stage-0 §221, partially reversing §62 and keeping its one settled sentence).

What is worth reading here is the refusals. An entry cannot exist without the platform's
AI-Generated tag; no state past `staged` can be reached without an operator's name; a chapter
the book has re-drafted under a staged entry cannot be approved; a second live entry for one
chapter is refused by name; and the command line has no `post`. The copy an operator pastes is
written under its hash and survives a republish, so what was approved is what gets pasted.

No model reads, ranks or judges anything here, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import library
from litharness.application import release as release_app
from litharness.application.export import collect
from litharness.cli import EXIT_FAULT, EXIT_OK, build_parser, main
from litharness.domain import release
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.revision import build_revision
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID

STAMP = "2026-09-03T12:00:00Z"
LATER = "2026-09-10T18:00:00Z"
TAGS = (release.AI_GENERATED_TAG, "LitRPG")
FRAGMENT = "a" * 64
PLAIN = "b" * 64


def _entry(**overrides: object) -> release.ReleaseEntry:
    fields: dict[str, object] = {
        "book_id": BOOK_ID,
        "branch_id": BRANCH_ID,
        "revision_id": "rev-1",
        "chapter_number": 3,
        "chapter_stem": "Chapter3",
        "title": "The Road",
        "fragment_sha256": FRAGMENT,
        "plain_sha256": PLAIN,
        "tags": TAGS,
        "scheduled_slot": "2026-09-10",
        "staged_at": STAMP,
    }
    fields.update(overrides)
    return release.stage(**fields)  # type: ignore[arg-type]


# --- the domain: four states, operator names, the tag --------------------------------------


def test_an_entry_addresses_its_chapter_and_its_copy_by_hash() -> None:
    entry = _entry()
    assert entry.release_id == release.release_id_for(BOOK_ID, BRANCH_ID, 3, FRAGMENT)
    assert entry.status is release.ReleaseStatus.STAGED
    assert entry.live
    assert release.AI_GENERATED_TAG in entry.author_note
    assert release.REPOSITORY_URL in entry.author_note
    with pytest.raises(release.IllegalRelease, match="address"):
        release.ReleaseEntry(**{**entry.to_jsonable(), "release_id": "rel-elsewhere"} | {
            "tags": entry.tags, "status": entry.status
        })


def test_the_ai_generated_tag_is_required_not_defaulted() -> None:
    with pytest.raises(release.IllegalRelease, match="required field"):
        _entry(tags=("LitRPG",))
    with pytest.raises(release.IllegalRelease, match="required field"):
        _entry(tags=())


def test_every_state_past_staged_carries_an_operator_name() -> None:
    entry = _entry()
    with pytest.raises(release.IllegalRelease, match="operator's name"):
        release.transition(entry, release.ReleaseStatus.APPROVED, at=LATER, by="")
    approved = release.transition(entry, release.ReleaseStatus.APPROVED, at=LATER, by="artem")
    assert (approved.approved_by, approved.approved_at) == ("artem", LATER)
    posted = release.transition(approved, release.ReleaseStatus.POSTED, at=LATER, by="artem")
    assert posted.posted_by == "artem" and posted.status is release.ReleaseStatus.POSTED
    with pytest.raises(release.IllegalRelease, match="reason"):
        release.transition(entry, release.ReleaseStatus.WITHDRAWN, at=LATER, by="artem")


def test_the_transitions_are_the_four_and_posted_is_terminal() -> None:
    entry = _entry()
    with pytest.raises(release.IllegalRelease, match="cannot become posted"):
        release.transition(entry, release.ReleaseStatus.POSTED, at=LATER, by="artem")
    approved = release.transition(entry, release.ReleaseStatus.APPROVED, at=LATER, by="artem")
    posted = release.transition(approved, release.ReleaseStatus.POSTED, at=LATER, by="artem")
    with pytest.raises(release.IllegalRelease, match="nothing"):
        release.transition(
            posted, release.ReleaseStatus.WITHDRAWN, at=LATER, by="artem", reason="x"
        )
    withdrawn = release.transition(
        approved, release.ReleaseStatus.WITHDRAWN, at=LATER, by="artem", reason="re-drafted"
    )
    assert not withdrawn.live
    with pytest.raises(release.IllegalRelease, match="nothing"):
        release.transition(withdrawn, release.ReleaseStatus.STAGED, at=LATER, by="artem")


# --- the store: one live entry per chapter, and the schema's own refusals -------------------


@pytest.fixture
def store(tmp_path: Path) -> SqliteStore:
    with SqliteStore.open(tmp_path / "release.db") as opened:
        yield opened


def test_the_store_keeps_one_live_entry_per_chapter_and_converges_on_the_same_copy(
    store: SqliteStore,
) -> None:
    entry = _entry()
    assert store.stage_release(entry)
    assert not store.stage_release(entry), "the same copy staged twice is one row"
    other = _entry(fragment_sha256="c" * 64)
    with pytest.raises(release.IllegalRelease, match="already has a live entry"):
        store.stage_release(other)
    store.move_release(
        entry.release_id, release.ReleaseStatus.WITHDRAWN, at=LATER, by="artem", reason="moved"
    )
    assert store.stage_release(other), "a withdrawn entry frees the chapter's slot"
    assert store.live_release(BOOK_ID, BRANCH_ID, 3) == other
    assert [item.release_id for item in store.release_entries(BOOK_ID, BRANCH_ID)] == [
        entry.release_id,
        other.release_id,
    ]


def test_the_schema_refuses_a_row_without_the_tag_or_without_a_name(store: SqliteStore) -> None:
    """Belt and braces: the domain refuses first, and the CHECKs refuse a row written past it."""
    import sqlite3

    connection = store._connection
    columns = (
        "release_id, book_id, branch_id, revision_id, chapter_number, chapter_stem, title, "
        "fragment_sha256, plain_sha256, author_note, tags_json, scheduled_slot, status, staged_at"
    )
    base = ["rel-x", BOOK_ID, BRANCH_ID, "rev", 1, "Chapter1", "T", FRAGMENT, PLAIN, "note"]
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            f"INSERT INTO release_queue ({columns}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [*base, '["LitRPG"]', "slot", "staged", STAMP],
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            f"INSERT INTO release_queue ({columns}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [*base, '["AI-Generated"]', "slot", "approved", STAMP],
        )


# --- the application: the copy is what the queue references, by hash ------------------------


DRAFTED = (
    "Rook counted the coins twice.\n\n"
    "He knew the lantern cost twenty.\n\n"
    "[STATUS] Rook - Level 2, HP 19/22"
)


def _book(*, drafted: int, total: int = 4, text: str = DRAFTED):
    keys = initial_keys(total)
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="The Road")]
    for index in range(total):
        if index < drafted:
            nodes.append(
                Node.text_node(
                    f"scene-{index + 1}",
                    NodeKind.SCENE,
                    keys[index],
                    text if index else text.replace("twice", "once"),
                    parent_logical_id="book",
                    title=f"Scene {index + 1}",
                )
            )
        else:
            nodes.append(
                Node(
                    logical_id=f"scene-{index + 1}",
                    kind=NodeKind.SCENE,
                    position_key=keys[index],
                    parent_logical_id="book",
                    title=f"Scene {index + 1}",
                )
            )
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


def _stage(store: SqliteStore, root: Path, chapter: int = 1):
    return release_app.stage_chapter(
        store,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        chapter_number=chapter,
        scenes_per_chapter=1,
        scheduled_slot="2026-09-10",
        tags=TAGS,
        root=root,
        generated_at=STAMP,
        staged_at=STAMP,
    )


def test_staging_writes_the_copy_under_its_hash_and_the_entry_references_it(
    store: SqliteStore, tmp_path: Path
) -> None:
    store.commit_revision(_book(drafted=2), created_at=STAMP)
    root = tmp_path / "book-library"
    entry, (html_copy, text_copy) = _stage(store, root)
    document = collect(store, book_id=BOOK_ID, branch_id=BRANCH_ID, generated_at=STAMP)
    chapters, _ = library.chapters_for(document, scenes_per_chapter=1)
    assert entry.fragment_sha256 == content_hash(chapters[0].fragment)
    assert html_copy.name == f"Chapter1-{entry.fragment_sha256[:12]}.html"
    assert html_copy.parent.name == "release"
    assert content_hash(html_copy.read_text(encoding="utf-8")) == entry.fragment_sha256
    assert content_hash(text_copy.read_text(encoding="utf-8")) == entry.plain_sha256
    assert store.release_entry(entry.release_id) == entry


def test_a_republish_never_touches_the_staged_copy(store: SqliteStore, tmp_path: Path) -> None:
    """`chapters/` is rewritten on every tick and stale files are removed; `release/` is the
    queue's and is never deleted, so the approved copy is still there to paste from."""
    store.commit_revision(_book(drafted=2), created_at=STAMP)
    root = tmp_path / "book-library"
    _, (html_copy, _text) = _stage(store, root)
    library.publish(store, root=root, generated_at=STAMP)
    library.publish(store, root=root, generated_at=LATER, force=True)
    assert html_copy.is_file()


def test_a_withheld_or_absent_chapter_cannot_be_staged(store: SqliteStore, tmp_path: Path) -> None:
    store.commit_revision(_book(drafted=2), created_at=STAMP)
    with pytest.raises(release.IllegalRelease, match="not pastable"):
        _stage(store, tmp_path / "book-library", chapter=3)


def test_approval_refuses_when_the_book_moved_under_the_entry(
    store: SqliteStore, tmp_path: Path
) -> None:
    store.commit_revision(_book(drafted=2), created_at=STAMP)
    root = tmp_path / "book-library"
    entry, _copies = _stage(store, root)
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    moved = head.replacing([head.node("scene-1").with_content("Rook counted nothing at all.")])
    store.commit_revision(moved, created_at=LATER)
    with pytest.raises(release.IllegalRelease, match="stage the chapter again"):
        release_app.approve(
            store, entry.release_id, by="artem", at=LATER, scenes_per_chapter=1, generated_at=LATER
        )


def test_approve_then_record_posted_under_an_operator_name(
    store: SqliteStore, tmp_path: Path
) -> None:
    store.commit_revision(_book(drafted=2), created_at=STAMP)
    entry, _copies = _stage(store, tmp_path / "book-library")
    with pytest.raises(release.IllegalRelease, match="cannot become posted"):
        release_app.record_posted(store, entry.release_id, by="artem", at=LATER)
    approved = release_app.approve(
        store, entry.release_id, by="artem", at=LATER, scenes_per_chapter=1, generated_at=LATER
    )
    assert approved.status is release.ReleaseStatus.APPROVED
    posted = release_app.record_posted(store, entry.release_id, by="artem", at=LATER)
    assert posted.status is release.ReleaseStatus.POSTED
    assert posted.posted_by == "artem"
    assert store.release_entry(entry.release_id) == posted


# --- the command line: four operator acts, and no post ---------------------------------------


def test_the_command_line_has_no_post() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["release", "post", "rel-x"])
    with pytest.raises(SystemExit):
        parser.parse_args(["release", "approve", "rel-x"])  # --by is required
    with pytest.raises(SystemExit):
        parser.parse_args(["release", "record-posted", "rel-x"])


def test_the_operator_stages_approves_and_records_from_the_command_line(
    tmp_path: Path, capsys
) -> None:
    db = tmp_path / "book.db"
    with SqliteStore.open(db) as store:
        store.commit_revision(_book(drafted=2), created_at=STAMP)
    def run(*args: str) -> int:
        # One scene per chapter, stated: the parser's default groups four, and a two-scene
        # book at that grain has no pastable chapter for the queue to stage.
        return main(["--database", str(db), "--chapter-scenes", "1", *args])

    assert (
        run("release", "stage", "--chapter", "1", "--slot", "2026-09-10", "--tag", "LitRPG")
        == EXIT_FAULT
    )
    assert "required field" in capsys.readouterr().err

    assert (
        run(
            "release", "stage", "--chapter", "1", "--slot", "2026-09-10",
            "--tag", "AI-Generated", "--tag", "LitRPG",
        )
        == EXIT_OK
    )
    shown = capsys.readouterr().out
    release_id = shown.split()[0]
    assert release_id.startswith("rel-")
    assert "paste from" in shown

    assert run("release", "show", "--json") == EXIT_OK
    [row] = json.loads(capsys.readouterr().out)
    assert row["status"] == "staged" and row["tags"] == ["AI-Generated", "LitRPG"]

    assert run("release", "approve", release_id, "--by", "artem") == EXIT_OK
    assert "approved by artem" in capsys.readouterr().out
    assert run("release", "record-posted", release_id, "--by", "artem", "--at", LATER) == EXIT_OK
    assert f"posted by artem at {LATER}" in capsys.readouterr().out
    assert run("release", "withdraw", release_id, "--by", "artem", "--reason", "x") == EXIT_FAULT
    assert "cannot become withdrawn" in capsys.readouterr().err
