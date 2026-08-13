"""The reading copy (`application/export.py`).

What is under test is mostly what the document *refuses* to hide: an undrafted scene has to
appear as a gap rather than be skipped, the front matter has to count what is actually there
rather than what was planned, and prose has to survive the trip without silently
restructuring the document it lands in. A book export that quietly drops the empty scenes
reads as finished, which is the one thing this system must never claim on its own behalf.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export
from litharness.cli import EXIT_FAULT, EXIT_OK, main
from litharness.domain.nodes import LockKind, Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.revision import build_revision
from tests.conftest import BOOK_ID, BRANCH_ID

STAMP = "2026-08-13T14:02:11Z"
OTHER_BOOK = "44444444-4444-5444-8444-444444444444"


def book(*, drafted: int = 2, scenes: int = 4, title: str | None = "The Hollow Ledger"):
    """A book whose first ``drafted`` scenes carry prose and whose rest are empty."""
    keys = initial_keys(scenes)
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title=title)]
    for index in range(scenes):
        common = {
            "logical_id": f"scene-{index + 1}",
            "kind": NodeKind.SCENE,
            "position_key": keys[index],
            "parent_logical_id": "book",
            "title": f"Scene the {index + 1}",
        }
        if index < drafted:
            nodes.append(
                Node.text_node(content=f"Rook counted the coins twice — {index + 1}.", **common)
            )
        else:
            nodes.append(Node(**common))
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "export.db"
    main(["--database", str(path), "init"])
    return path


def commit(db, revision, *, at: str = STAMP) -> str:
    store = SqliteStore.open(db)
    try:
        store.commit_revision(revision, created_at=at)
    finally:
        store.close()
    return revision.revision_id


def collect(db, **kwargs) -> export.BookExport:
    store = SqliteStore.open(db)
    try:
        return export.collect(
            store,
            book_id=kwargs.pop("book_id", BOOK_ID),
            branch_id=kwargs.pop("branch_id", BRANCH_ID),
            generated_at=STAMP,
            **kwargs,
        )
    finally:
        store.close()


def run(db, *args: str) -> int:
    return main(["--database", str(db), *args])


# --- the gaps are the point ----------------------------------------------------------


def test_an_undrafted_scene_is_a_visible_gap_not_an_omission(db) -> None:
    """The whole reason a director reads this is to see how far off the book is. A document
    that skips the empty scenes reads as a finished short book rather than an unfinished
    long one, and nothing on the page would contradict it."""
    commit(db, book(drafted=2, scenes=4))
    document = collect(db)

    markdown = document.as_markdown()
    assert markdown.count(export.NOT_DRAFTED) == 2
    assert "Scene the 4" in markdown, "an undrafted scene keeps its heading"
    assert export.NOT_DRAFTED in document.as_html()


def test_the_front_matter_counts_what_is_there(db) -> None:
    commit(db, book(drafted=2, scenes=4))
    document = collect(db)

    assert (document.drafted, document.total) == (2, 4)
    # Seven whitespace-delimited tokens a scene, in the two that have any — the standalone
    # em-dash is one of them, which is what "approximate" means here and why nothing in the
    # system bills against this number.
    assert document.words == 14
    assert "2 of 4 scene(s) drafted" in document.as_markdown()
    assert [scene.state for scene in document.scenes] == [
        "drafted",
        "drafted",
        "not yet drafted",
        "not yet drafted",
    ]


def test_progress_between_two_revisions_is_readable_as_a_diff(db) -> None:
    """Two exports a day apart have to differ in a way you can read, which is the whole of
    "see progress over time". Revisions are immutable, so the older one stays exportable."""
    first = commit(db, book(drafted=1, scenes=4))
    later = book(drafted=3, scenes=4)
    commit(db, build_revision(BOOK_ID, BRANCH_ID, later.nodes, parent=first), at=STAMP)

    assert "1 of 4 scene(s) drafted" in collect(db, revision_id=first).as_markdown()
    assert "3 of 4 scene(s) drafted" in collect(db).as_markdown()


def test_a_content_locked_empty_scene_is_not_merely_pending(db) -> None:
    """A tick will never fill it — `gate_draft` refuses a locked node — so counting it with
    the scenes that are simply waiting would misstate how far off the book is."""
    revision = book(drafted=1, scenes=2)
    nodes = [
        replace(node, lock=LockKind.CONTENT) if node.logical_id == "scene-2" else node
        for node in revision.nodes
    ]
    commit(db, build_revision(BOOK_ID, BRANCH_ID, nodes))

    assert collect(db).scenes[1].state == "locked, empty"


# --- prose survives the trip ---------------------------------------------------------


def test_prose_cannot_restructure_the_document_it_lands_in(db) -> None:
    """A line of prose beginning `#` becomes a heading and silently joins the book's own
    outline; a line of `---` turns the paragraph above it into one. Both are corruption of
    what the document claims, as against styling a phrase, which is the author's business.
    """
    keys = initial_keys(1)
    nodes = [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="T"),
        Node.text_node(
            "scene-1",
            NodeKind.SCENE,
            keys[0],
            "He read the sign.\n# CLOSED\n---\nAnd *left* quietly.",
            parent_logical_id="book",
            title="The Sign",
        ),
    ]
    commit(db, build_revision(BOOK_ID, BRANCH_ID, nodes))

    markdown = collect(db).as_markdown()
    assert "\n\\# CLOSED\n" in markdown
    assert "\n\\---\n" in markdown
    assert "*left*" in markdown, "inline emphasis is the author's, and is left alone"


def test_html_escapes_prose_as_text(db) -> None:
    """Markdown gets a structural-only compromise; HTML cannot have one, because a stray
    `<` swallows everything up to the next `>` and the loss is silent."""
    keys = initial_keys(1)
    nodes = [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="T & Co"),
        Node.text_node(
            "scene-1",
            NodeKind.SCENE,
            keys[0],
            "First.\n\n<not a tag> & so on.",
            parent_logical_id="book",
            title="A <script> in the title",
        ),
    ]
    commit(db, build_revision(BOOK_ID, BRANCH_ID, nodes))

    rendered = collect(db).as_html()
    assert "&lt;not a tag&gt; &amp; so on." in rendered
    assert "<script>" not in rendered
    assert rendered.count("<p>") == 2, "a blank line is a paragraph break"


def test_a_pipe_in_a_title_does_not_split_the_progress_table(db) -> None:
    keys = initial_keys(1)
    nodes = [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="T"),
        Node(
            logical_id="scene-1",
            kind=NodeKind.SCENE,
            position_key=keys[0],
            parent_logical_id="book",
            title="Rook | Marrow",
        ),
    ]
    commit(db, build_revision(BOOK_ID, BRANCH_ID, nodes))

    row = next(
        line for line in collect(db).as_markdown().splitlines() if "Rook" in line and "|" in line
    )
    assert r"Rook \| Marrow" in row
    delimiters = row.count("|") - row.count(r"\|")
    assert delimiters == 5, "four cells, so five delimiters; an unescaped pipe would make six"


def test_heading_level_follows_the_tree_not_the_kind(db) -> None:
    """A scene directly under the book and a scene under a chapter are at different depths
    and must not both be `<h2>`, or the outline contradicts the manuscript."""
    keys = initial_keys(2)
    nodes = [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="T"),
        Node(
            logical_id="ch-1",
            kind=NodeKind.CHAPTER,
            position_key=keys[0],
            parent_logical_id="book",
            title="One",
        ),
        Node.text_node(
            "scene-1", NodeKind.SCENE, keys[0], "Prose.", parent_logical_id="ch-1", title="Deep"
        ),
        Node.text_node(
            "scene-2", NodeKind.SCENE, keys[1], "Prose.", parent_logical_id="book", title="Shallow"
        ),
    ]
    commit(db, build_revision(BOOK_ID, BRANCH_ID, nodes))

    markdown = collect(db).as_markdown()
    assert "## One" in markdown
    assert "### 1. Deep" in markdown
    assert "## 2. Shallow" in markdown


# --- selection and refusal -----------------------------------------------------------


def test_a_single_book_needs_no_arguments(db) -> None:
    commit(db, book())
    store = SqliteStore.open(db)
    try:
        assert export.resolve_branch(store, None, None) == (BOOK_ID, BRANCH_ID)
    finally:
        store.close()


def test_two_books_are_ambiguous_rather_than_defaultable(db, capsys) -> None:
    """Picking the first would export whichever book sorted lowest and say nothing about
    the other, which is a wrong document rather than an error."""
    commit(db, book())
    commit(db, build_revision(OTHER_BOOK, BRANCH_ID, book().nodes))

    assert run(db, "export") == EXIT_FAULT
    err = capsys.readouterr().err
    assert "2 branches match" in err
    assert OTHER_BOOK in err and BOOK_ID in err


def test_a_mistyped_revision_is_a_fault_not_a_traceback(db, capsys) -> None:
    """`KeyError` is not in the CLI's fault handler, so left as it was this escaped under
    the exit code reserved for "a unit needs a human"."""
    commit(db, book())

    assert run(db, "export", "--revision", "nope") == EXIT_FAULT
    err = capsys.readouterr().err
    assert "no revision nope" in err
    assert "Traceback" not in err


def test_a_revision_from_another_book_is_refused(db) -> None:
    """Its front matter would carry this book's provenance, and provenance is most of why
    the front matter exists."""
    commit(db, book())
    foreign = commit(db, build_revision(OTHER_BOOK, BRANCH_ID, book().nodes))

    with pytest.raises(ValueError, match="belongs to book"):
        collect(db, revision_id=foreign)


def test_an_empty_store_says_what_to_do_about_it(db, capsys) -> None:
    assert run(db, "export") == EXIT_FAULT
    assert "litharness import" in capsys.readouterr().err


# --- the command line ----------------------------------------------------------------


def test_the_suffix_picks_the_format_and_the_flag_overrides_it(db, tmp_path) -> None:
    commit(db, book())

    assert run(db, "export", str(tmp_path / "a.html")) == EXIT_OK
    assert run(db, "export", str(tmp_path / "b.md")) == EXIT_OK
    assert run(db, "export", str(tmp_path / "c.md"), "--format", "html") == EXIT_OK

    assert (tmp_path / "a.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert (tmp_path / "b.md").read_text(encoding="utf-8").startswith("# The Hollow Ledger")
    assert (tmp_path / "c.md").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_the_document_is_written_as_utf8(db, tmp_path) -> None:
    """The default encoding on this platform is cp1252, which cannot represent an em-dash —
    and a book is made of them. Written implicitly this raises on the first scene that uses
    one, on Windows only, which is the worst way to find out."""
    commit(db, book())
    destination = tmp_path / "book.md"

    assert run(db, "export", str(destination)) == EXIT_OK
    assert "—" in destination.read_text(encoding="utf-8")


def test_writing_to_a_file_reports_progress_on_stdout(db, tmp_path, capsys) -> None:
    commit(db, book(drafted=2, scenes=4))

    assert run(db, "export", str(tmp_path / "book.md")) == EXIT_OK
    out = capsys.readouterr().out
    assert "2 of 4 scene(s) drafted" in out
    assert "markdown from revision" in out


def test_stdout_carries_the_book_and_nothing_else(db, capsys) -> None:
    """The summary line would land in the middle of the document."""
    commit(db, book())

    assert run(db, "export") == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("# The Hollow Ledger")
    assert "scene(s) drafted ·" in out, "the front matter still says how far along it is"
    assert "from revision" not in out
