"""The library: reading copies to check progress against, and chapters that survive a paste.

The tests worth reading are the refusals and the absences. A chapter holding an undrafted
scene is withheld rather than emitted with a hole in it, because a hole pasted into a serial
publishes the words `[not yet drafted]` to readers. And the pastable file contains none of what
makes the reading copy useful — no progress table, no revision id, no title heading — because
every one of those would be published as if it were prose.
"""

from __future__ import annotations

import re

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.export import collect
from litharness.application.library import (
    DEFAULT_SCENES_PER_CHAPTER,
    LIBRARY_DIRNAME,
    NOTES_FILENAME,
    NOTES_TEMPLATE,
    STATE_FILENAME,
    chapters_for,
    index_markdown,
    paste_fragment,
    paste_plain,
    publish,
    root_for,
    slugify,
)
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.revision import build_revision
from tests.conftest import BOOK_ID, BRANCH_ID

STAMP = "2026-08-19T00:00:00Z"

DRAFTED = (
    "Rook counted the coins twice.\n\n"
    "He knew the lantern cost twenty.\n\n"
    "[STATUS] Rook - Level 2, HP 19/22"
)


def a_book(*, drafted: int, total: int = 4) -> object:
    """A book whose first `drafted` scenes carry prose and whose rest are empty."""
    keys = initial_keys(total)
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="The Road")]
    for index in range(total):
        title = f"Scene {index + 1}"
        if index < drafted:
            nodes.append(
                Node.text_node(
                    f"scene-{index + 1}", NodeKind.SCENE, keys[index], DRAFTED,
                    parent_logical_id="book", title=title,
                )
            )
        else:
            nodes.append(
                Node(
                    logical_id=f"scene-{index + 1}", kind=NodeKind.SCENE,
                    position_key=keys[index], parent_logical_id="book", title=title,
                )
            )
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


def a_document(store: SqliteStore, *, drafted: int, total: int = 4):
    store.commit_revision(a_book(drafted=drafted, total=total), created_at=STAMP)
    return collect(store, book_id=BOOK_ID, branch_id=BRANCH_ID, generated_at=STAMP)


# -- the withholding rule ------------------------------------------------------------------


def test_a_chapter_holding_an_undrafted_scene_is_withheld_and_counted(tmp_path) -> None:
    """A hole pasted into a serial publishes the placeholder to readers. Counted rather than
    dropped, because a pastable set that silently skipped its gaps would read as a finished
    serial — which is the one way this folder could mislead about progress."""
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=2, total=4)
    finally:
        store.close()
    chapters, withheld = chapters_for(document)
    assert len(chapters) == 2 and withheld == 2
    assert all("not yet drafted" not in chapter.fragment for chapter in chapters)
    assert all("not yet drafted" not in chapter.plain for chapter in chapters)


def test_a_group_is_withheld_whole_rather_than_losing_its_gap(tmp_path) -> None:
    """A chapter that dropped its undrafted scene and kept the rest would publish a jump-cut,
    which is worse than publishing nothing: nothing is visible and a jump-cut is not."""
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=3, total=4)
    finally:
        store.close()
    chapters, withheld = chapters_for(document, scenes_per_chapter=2)
    assert len(chapters) == 1, "scenes 3-4 hold a gap, so that whole chapter is withheld"
    assert withheld == 1
    assert chapters[0].logical_ids == ("scene-1", "scene-2")


# -- what a pastable file must not contain -------------------------------------------------


def test_the_pastable_chapter_carries_no_scaffolding(tmp_path) -> None:
    """Everything that makes the reading copy useful would be published as prose if it
    survived into a chapter body: the progress table, the revision id, the premise block."""
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=1, total=2)
    finally:
        store.close()
    [chapter], _ = chapters_for(document)
    assert document.revision_id not in chapter.fragment
    assert "Words" not in chapter.fragment and "State" not in chapter.fragment
    assert "<table" not in chapter.fragment
    assert "<h1" not in chapter.fragment and "<h2" not in chapter.fragment, (
        "a serial platform takes the chapter title in its own field, so a heading in the "
        "body is published twice"
    )
    assert chapter.title in chapter.stem or chapter.slug in chapter.stem


def test_only_the_conservative_tag_subset_is_emitted(tmp_path) -> None:
    """No classes, ids or styles, and only tags every rich-text editor preserves. The claim
    "this pastes correctly" is not one this repository can verify against a particular
    editor, so the artifact stays inside the subset where it does not need to."""
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=2, total=2)
    finally:
        store.close()
    chapters, _ = chapters_for(document, scenes_per_chapter=2)
    tags = set(re.findall(r"<(/?[a-z0-9]+)", chapters[0].fragment))
    assert tags <= {"p", "/p", "blockquote", "/blockquote", "hr"}
    assert "class=" not in chapters[0].fragment
    assert "style=" not in chapters[0].fragment
    assert "<!DOCTYPE" not in chapters[0].fragment and "<head" not in chapters[0].fragment


def test_prose_is_escaped_as_text() -> None:
    """A stray `<` in prose swallows everything up to the next `>` and the loss is silent —
    `export._paragraphs`'s reason, and it applies with more force here because this output is
    pasted somewhere that renders it."""
    scene = Node.text_node(
        "scene-1", NodeKind.SCENE, "010", "He wrote <3 & meant it.", title="S"
    )
    fragment = paste_fragment([scene])
    assert "&lt;3 &amp; meant it." in fragment
    assert "<3" not in fragment


def test_system_voice_lines_are_set_apart() -> None:
    """A rendering choice rather than a fact about the prose: a stat block set as an ordinary
    paragraph reads as a sentence, and the genre sets it apart."""
    fragment = paste_fragment(
        [Node.text_node("scene-1", NodeKind.SCENE, "010", DRAFTED, title="S")]
    )
    assert "<blockquote>[STATUS] Rook - Level 2, HP 19/22</blockquote>" in fragment
    assert fragment.count("<p>") == 2, "the prose paragraphs stay paragraphs"


# -- grouping is an operator act ------------------------------------------------------------


def test_one_scene_is_one_chapter_by_default(tmp_path) -> None:
    """Production books hold no chapter nodes and no assembly scheme is decided — `pair-draw`
    already refuses chapter grain on exactly that ground rather than improvising one."""
    assert DEFAULT_SCENES_PER_CHAPTER == 1
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=4, total=4)
    finally:
        store.close()
    chapters, _ = chapters_for(document)
    assert len(chapters) == 4
    assert [chapter.logical_ids for chapter in chapters] == [
        ("scene-1",), ("scene-2",), ("scene-3",), ("scene-4",)
    ]


def test_grouping_names_the_range_it_covers(tmp_path) -> None:
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=4, total=4)
    finally:
        store.close()
    chapters, _ = chapters_for(document, scenes_per_chapter=2)
    assert len(chapters) == 2
    assert "1-2" in chapters[0].title and "3-4" in chapters[1].title
    assert "<hr>" in chapters[0].fragment, "a scene break inside a grouped chapter"
    assert "* * *" in chapters[0].plain


def test_the_plain_text_fallback_is_blank_line_separated() -> None:
    """Here because the HTML claim is unverifiable from this repository. Plain text with blank
    lines pastes as paragraphs in every editor there is, so the uncertainty costs one small
    file rather than a failed publish."""
    plain = paste_plain(
        [Node.text_node("scene-1", NodeKind.SCENE, "010", DRAFTED, title="S")]
    )
    assert "<" not in plain
    assert plain.count("\n\n") == 2


# -- the shelf ------------------------------------------------------------------------------


def test_publish_writes_both_shapes_and_an_index(tmp_path) -> None:
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / "library"
    try:
        a_document(store, drafted=3, total=4)
        [book] = publish(store, root=root, generated_at=STAMP)
    finally:
        store.close()
    shelf = root / book.slug
    assert (shelf / f"{book.slug}.md").exists() and (shelf / f"{book.slug}.html").exists()
    assert len(list((shelf / "chapters").glob("*.html"))) == 3
    assert len(list((shelf / "chapters").glob("*.txt"))) == 3
    assert book.withheld == 1
    index = (root / "README.md").read_text(encoding="utf-8")
    assert book.title in index and "Withheld" in index
    reading = (shelf / f"{book.slug}.md").read_text(encoding="utf-8")
    assert "not yet drafted" in reading, (
        "the reading copy shows the gap; only the pastable copy withholds it"
    )


def test_the_notes_file_is_written_once_and_never_overwritten(tmp_path) -> None:
    """Overwriting somebody's reading notes with a template on the next tick is the kind of
    data loss discovered a week later."""
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / "library"
    try:
        a_document(store, drafted=2, total=2)
        [book] = publish(store, root=root, generated_at=STAMP)
        notes = root / book.slug / NOTES_FILENAME
        assert notes.read_text(encoding="utf-8") == NOTES_TEMPLATE
        notes.write_text(NOTES_TEMPLATE + "chapter two dragged\n", encoding="utf-8")
        publish(store, root=root, generated_at=STAMP)
        assert "chapter two dragged" in notes.read_text(encoding="utf-8")
    finally:
        store.close()


def test_the_notes_template_points_at_the_axis_admission_path() -> None:
    """The library is not only a progress check: a named defect from a human read is one of
    exactly two doors an axis can enter the registry by, and all three the system measures came
    from one read of one book."""
    assert "reader-judge-loop.md" in NOTES_TEMPLATE
    assert "not blinded" in NOTES_TEMPLATE, (
        "a note from here is evidence of the first-human-read class, not of a blinded "
        "reader's, and the file says so where it will be read"
    )


def test_a_stale_chapter_file_is_removed_on_republish(tmp_path) -> None:
    """A chapter left behind after its scene was repaired would be the copy somebody pastes,
    and it would be wrong in the way hardest to notice: readable, plausible, and not what the
    book says."""
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / "library"
    try:
        a_document(store, drafted=2, total=2)
        [book] = publish(store, root=root, generated_at=STAMP)
        stale = root / book.slug / "chapters" / "99-gone.html"
        stale.write_text("<p>from a scene that no longer exists</p>", encoding="utf-8")
        # `force`, because the head has not moved: the skip that makes a per-tick publish
        # cheap would otherwise leave the stale file exactly where it was.
        publish(store, root=root, generated_at=STAMP, force=True)
        assert not stale.exists()
        assert len(list((root / book.slug / "chapters").glob("*.html"))) == 2
    finally:
        store.close()


def test_the_index_says_the_library_is_not_a_publication() -> None:
    """§62 settled what publishing is here — the export, run when the book clears the bar —
    and no book has cleared it. The folder says so where somebody about to paste will read it."""
    index = index_markdown((), checked_at=STAMP)
    assert "not a publication" in index
    assert "steering pool" in index, (
        "reading your own book and directing makes you a steering reader; the caveat belongs "
        "where the reading happens"
    )


def test_slugify_falls_back_rather_than_producing_an_empty_name() -> None:
    assert slugify("The Vane House", "book-id") == "the-vane-house"
    assert slugify("!!!", "abcdefghijklmno") == "abcdefghijkl"


def test_publishing_an_empty_store_says_so(tmp_path) -> None:
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / "library"
    try:
        assert publish(store, root=root, generated_at=STAMP) == ()
    finally:
        store.close()
    assert "No book in this store yet" in (root / "README.md").read_text(encoding="utf-8")


# -- the cadence: on by default, and cheap because it skips what has not moved -------------


def test_the_library_sits_beside_its_database_rather_than_the_working_directory(
    tmp_path,
) -> None:
    """**What makes publishing safe to have on by default.** Resolved against the store it is
    derived from, so nothing writes a folder into whatever directory a command was run from,
    and a run against a temporary database takes its output away with it."""
    assert root_for(tmp_path / "bz3.db") == tmp_path.resolve() / LIBRARY_DIRNAME
    assert root_for("bz3.db").name == LIBRARY_DIRNAME
    assert LIBRARY_DIRNAME == "book-library"


def test_a_book_whose_head_has_not_moved_is_not_rewritten(tmp_path) -> None:
    """Revisions are content-addressed, so "the head is what this shelf was built from" is an
    exact statement rather than a guess about timestamps. A quiet system rewrites nothing."""
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / LIBRARY_DIRNAME
    try:
        a_document(store, drafted=2, total=2)
        [first] = publish(store, root=root, generated_at="2026-08-19T00:00:00Z")
        assert first.rewritten
        chapter = root / first.slug / "chapters" / f"{first.chapters[0].stem}.html"
        chapter.write_text("<p>edited by hand</p>", encoding="utf-8")

        [second] = publish(store, root=root, generated_at="2026-08-19T06:00:00Z")
        assert not second.rewritten
        assert chapter.read_text(encoding="utf-8") == "<p>edited by hand</p>", (
            "an unchanged book is skipped entirely, not re-rendered"
        )
    finally:
        store.close()


def test_the_index_separates_when_it_was_checked_from_when_the_book_changed(
    tmp_path,
) -> None:
    """Collapsing them is how a folder starts lying about freshness: one restamped timestamp
    says "published just now" about a book nothing has touched for a week, which is exactly
    the reassurance somebody checking on progress must not be given."""
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / LIBRARY_DIRNAME
    try:
        a_document(store, drafted=2, total=2)
        publish(store, root=root, generated_at="2026-08-19T00:00:00Z")
        publish(store, root=root, generated_at="2026-08-19T06:00:00Z")
    finally:
        store.close()
    index = (root / "README.md").read_text(encoding="utf-8")
    assert "Last checked 2026-08-19T06:00:00Z" in index
    assert "2026-08-19T00:00:00Z" in index, "the Changed column keeps when it last moved"
    assert (root / STATE_FILENAME).is_file()


def test_a_corrupt_state_file_costs_a_republish_and_never_a_run(tmp_path) -> None:
    """The state file is a cache of a fact the store already holds. The books are the truth."""
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / LIBRARY_DIRNAME
    try:
        a_document(store, drafted=2, total=2)
        publish(store, root=root, generated_at="2026-08-19T00:00:00Z")
        (root / STATE_FILENAME).write_text("{not json", encoding="utf-8")
        [again] = publish(store, root=root, generated_at="2026-08-19T06:00:00Z")
        assert again.rewritten
    finally:
        store.close()


def test_a_tick_publishes_without_being_asked_and_writes_beside_the_database(
    tmp_path, monkeypatch
) -> None:
    """On by default is the point: a reading copy you have to remember to ask for is one
    nobody has. `--no-library` is the opt-out, and neither writes into the working directory."""
    from litharness.cli import EXIT_OK, main

    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main([
        "--database", str(db), "new", "The Toll Road",
        "--premise", "A debtor works off an impossible debt.", "--scenes", "6",
    ]) == EXIT_OK
    for _ in range(4):
        main(["--database", str(db), "tick"])
    root = tmp_path / LIBRARY_DIRNAME
    assert (root / "README.md").is_file(), "no flag was passed and the library exists"
    assert list(root.glob("*/chapters/*.html")), "and it holds pastable chapters"


def test_no_library_turns_the_cadence_off(tmp_path, monkeypatch) -> None:
    from litharness.cli import EXIT_OK, main

    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    main(["--database", str(db), "--no-library", "tick"])
    assert not (tmp_path / LIBRARY_DIRNAME).exists()
