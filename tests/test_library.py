"""The library: reading copies to check progress against, and chapters that survive a paste.

The tests worth reading are the refusals and the absences. A chapter holding an undrafted
scene is withheld rather than emitted with a hole in it, because a hole pasted into a serial
publishes the words `[not yet drafted]` to readers. And the pastable file contains none of what
makes the reading copy useful — no progress table, no revision id, no title heading — because
every one of those would be published as if it were prose.
"""

from __future__ import annotations

import json
import re
import shutil

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.export import collect
from litharness.application.library import (
    DEFAULT_CHAPTERS_PER_VOLUME,
    DEFAULT_SCENES_PER_CHAPTER,
    LIBRARY_DIRNAME,
    NOTES_FILENAME,
    NOTES_TEMPLATE,
    SHELF_MARKER_FILENAME,
    STATE_FILENAME,
    chapters_for,
    index_markdown,
    paste_fragment,
    paste_plain,
    publish,
    root_for,
    shelf_slug,
    slugify,
    volumes_for,
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
                    f"scene-{index + 1}",
                    NodeKind.SCENE,
                    keys[index],
                    DRAFTED,
                    parent_logical_id="book",
                    title=title,
                )
            )
        else:
            nodes.append(
                Node(
                    logical_id=f"scene-{index + 1}",
                    kind=NodeKind.SCENE,
                    position_key=keys[index],
                    parent_logical_id="book",
                    title=title,
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
    assert chapter.stem == f"Chapter{chapter.number}"


def test_only_the_conservative_tag_subset_is_emitted(tmp_path) -> None:
    """Prose carries no classes, ids or styles, and only tags every rich-text editor
    preserves. The claim "this pastes correctly" is not one this repository can verify against
    a particular editor, so the artifact stays inside the subset where it does not need to.

    The status panel is the one element outside this subset, and it pays for its `<table>` by
    carrying its styling inline; the fixture line here is unparseable on purpose, so what this
    test pins is the prose."""
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
    scene = Node.text_node("scene-1", NodeKind.SCENE, "010", "He wrote <3 & meant it.", title="S")
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


PANEL_LINE = "[STATUS] Mira Kell — Hold 3 | Carried 2/3"


def a_scene_with_a_status_line() -> Node:
    return Node.text_node(
        "scene-1",
        NodeKind.SCENE,
        "010",
        f"She read it twice.\n\n{PANEL_LINE}\n\nThen she closed it.",
        title="S",
    )


def test_a_status_line_becomes_a_panel_in_the_pastable_chapter() -> None:
    """Setting a sheet apart is not the same as drawing it: a blockquote is still a sentence
    with pipes in it. The `<table>` is the one widening of the paste subset, and it buys the
    widening with inline styles, which is the half of CSS a rich-text editor keeps."""
    fragment = paste_fragment([a_scene_with_a_status_line()])

    assert "<table style=" in fragment
    assert '<th colspan="2" scope="colgroup" style=' in fragment
    assert "Mira Kell" in fragment and "<blockquote>" not in fragment
    assert "class=" not in fragment and " id=" not in fragment
    assert fragment.count("<p>") == 2, "the prose around it is still classless prose"


def test_the_plain_text_chapter_keeps_the_status_line_exactly() -> None:
    """The panel is an HTML rendering choice and touches nothing else. The line's format is
    load-bearing — `domain/extraction.py` parses it — so the `.txt` route carries it as
    written, and stays the fallback if the HTML route ever mangles."""
    plain = paste_plain([a_scene_with_a_status_line()])

    assert PANEL_LINE in plain
    assert "<" not in plain


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
        ("scene-1",),
        ("scene-2",),
        ("scene-3",),
        ("scene-4",),
    ]


def test_grouping_names_the_chapter_and_never_the_scenes(tmp_path) -> None:
    """A chapter is named for what it is to a reader, and the file is named the same way.

    It used to be titled `Scene 1 (1-4)` and filed as `01-scene-1-1-4`, so the unit of *work*
    reached the one artifact that exists to be handed to a reader — and the title travels to a
    serial platform in its own field, which would have published the harness's vocabulary under
    the book's name. The scene is internal; nothing a reader receives may name one.
    """
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        document = a_document(store, drafted=4, total=4)
    finally:
        store.close()
    chapters, _ = chapters_for(document, scenes_per_chapter=2)
    assert len(chapters) == 2
    assert [chapter.title for chapter in chapters] == ["Chapter 1", "Chapter 2"]
    assert [chapter.stem for chapter in chapters] == ["Chapter1", "Chapter2"]
    assert "<hr>" in chapters[0].fragment, "a scene break inside a grouped chapter"
    assert "* * *" in chapters[0].plain


def test_release_volumes_package_one_endless_serial_without_resetting_it(tmp_path) -> None:
    """The volume is a release window, never another book or an inferred ending."""
    assert DEFAULT_CHAPTERS_PER_VOLUME == 50
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / "library"
    try:
        document = a_document(store, drafted=102, total=112)
        chapters, _ = chapters_for(document)
        volumes = volumes_for(chapters, total_chapters=112)
        assert [(v.first_chapter, v.last_chapter) for v in volumes] == [
            (1, 50),
            (51, 100),
            (101, 112),
        ]
        [book] = publish(store, root=root, generated_at=STAMP)
    finally:
        store.close()

    assert [volume.withheld for volume in book.volumes] == [0, 0, 10]
    shelf = root / book.slug
    assert (shelf / f"{book.slug}.md").is_file(), "the whole-serial reading copy remains"
    volume_two = shelf / "volumes" / "Volume2"
    assert (volume_two / "chapters" / "Chapter51.txt").is_file()
    assert (volume_two / "chapters" / "Chapter100.txt").is_file()
    assert not (volume_two / "chapters" / "Chapter1.txt").exists()

    manifest = json.loads((volume_two / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["book_id"] == book.book_id
    assert manifest["revision_id"] == book.revision_id
    assert manifest["open_ended_serial"] is True
    assert manifest["continuity_scope"] == {
        "kind": "serial_prefix",
        "through_global_chapter": 100,
        "verified": False,
    }
    third = (shelf / "volumes" / "Volume3" / "Volume3.md").read_text(encoding="utf-8")
    assert "## Chapter 112" in third and "[not yet drafted]" in third


def test_changing_release_window_repackages_an_unchanged_serial_and_removes_stale_volumes(
    tmp_path,
) -> None:
    store = SqliteStore.open(tmp_path / "l.db")
    root = tmp_path / "library"
    try:
        a_document(store, drafted=112, total=112)
        [first] = publish(store, root=root, generated_at=STAMP)
        assert len(first.volumes) == 3
        [second] = publish(
            store,
            root=root,
            generated_at=STAMP,
            chapters_per_volume=100,
        )
    finally:
        store.close()
    assert second.rewritten and len(second.volumes) == 2
    assert not (root / second.slug / "volumes" / "Volume3").exists()


def test_the_plain_text_fallback_is_blank_line_separated() -> None:
    """Here because the HTML claim is unverifiable from this repository. Plain text with blank
    lines pastes as paragraphs in every editor there is, so the uncertainty costs one small
    file rather than a failed publish."""
    plain = paste_plain([Node.text_node("scene-1", NodeKind.SCENE, "010", DRAFTED, title="S")])
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
    assert "covers/cover-NN.png" in index


def test_slugify_falls_back_rather_than_producing_an_empty_name() -> None:
    assert slugify("The Vane House", "book-id") == "the-vane-house"
    assert slugify("!!!", "abcdefghijklmno") == "abcdefghijkl"


# -- two books, one title: the shelf collision (serial pilot 15b §7) -----------------------

KETTLE = "What the Kettle Remembers"
FIRST_BOOK = "44444444-4444-5444-8444-444444444444"
FIRST_BRANCH = "55555555-5555-5555-8555-555555555555"
SECOND_BOOK = "66666666-6666-5666-8666-666666666666"
SECOND_BRANCH = "77777777-7777-5777-8777-777777777777"


def a_kettle_book(book_id: str, branch_id: str, prose: str) -> object:
    """One drafted scene under the shared title, for a book with its own identity."""
    keys = initial_keys(1)
    nodes = [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title=KETTLE),
        Node.text_node(
            "scene-1", NodeKind.SCENE, keys[0], prose, parent_logical_id="book", title="Scene 1"
        ),
    ]
    return build_revision(book_id, branch_id, nodes)


def test_shelf_slug_suffixes_only_a_colliding_newcomer(tmp_path) -> None:
    """The first book to publish a name keeps it; a different book arriving at the same name
    carries a short id suffix. A book with no id has nothing to disambiguate with."""
    assert shelf_slug(tmp_path, "The Road", FIRST_BOOK) == "the-road"
    shelf = tmp_path / "the-road"
    shelf.mkdir()
    (shelf / SHELF_MARKER_FILENAME).write_text(
        json.dumps({"book_id": FIRST_BOOK}), encoding="utf-8"
    )
    assert shelf_slug(tmp_path, "The Road", FIRST_BOOK) == "the-road"
    assert shelf_slug(tmp_path, "The Road", SECOND_BOOK) == "the-road--66666666"
    assert shelf_slug(tmp_path, "The Road", "") == "the-road"


def test_two_books_sharing_a_title_do_not_share_a_shelf(tmp_path) -> None:
    """The defect as it happened: pilot 15 draw 1 and pilot 15b draw 2 carried one title from
    two databases, both resolved `book-library/what-the-kettle-remembers/`, and the redraw
    republished over draw 1's reading copy — which had to be archived by hand. The newcomer
    now publishes beside, not over."""
    root = tmp_path / LIBRARY_DIRNAME
    first_store = SqliteStore.open(tmp_path / "serial15.db")
    try:
        first_store.commit_revision(
            a_kettle_book(FIRST_BOOK, FIRST_BRANCH, "The kettle held its first hour."),
            created_at=STAMP,
        )
        [first] = publish(first_store, root=root, generated_at=STAMP)
    finally:
        first_store.close()
    second_store = SqliteStore.open(tmp_path / "serial15b.db")
    try:
        second_store.commit_revision(
            a_kettle_book(SECOND_BOOK, SECOND_BRANCH, "The redraw held a different hour."),
            created_at=STAMP,
        )
        [second] = publish(second_store, root=root, generated_at=STAMP)
    finally:
        second_store.close()

    assert first.slug == "what-the-kettle-remembers"
    assert second.slug == "what-the-kettle-remembers--66666666"
    first_copy = (root / first.slug / f"{first.slug}.md").read_text(encoding="utf-8")
    assert "its first hour" in first_copy, "the redraw must not republish over draw 1"
    second_copy = (root / second.slug / f"{second.slug}.md").read_text(encoding="utf-8")
    assert "a different hour" in second_copy
    marker = json.loads(
        (root / second.slug / SHELF_MARKER_FILENAME).read_text(encoding="utf-8")
    )
    assert marker["book_id"] == SECOND_BOOK


def test_a_suffixed_shelf_keeps_its_name_after_the_bare_one_frees_up(tmp_path) -> None:
    """Once suffixed, always suffixed: a shelf changing name because some other folder was
    deleted would be a shelf moving behind the operator's back — the thing the whole rule
    exists to prevent."""
    root = tmp_path / LIBRARY_DIRNAME
    first_store = SqliteStore.open(tmp_path / "one.db")
    try:
        first_store.commit_revision(
            a_kettle_book(FIRST_BOOK, FIRST_BRANCH, "The kettle held its first hour."),
            created_at=STAMP,
        )
        [first] = publish(first_store, root=root, generated_at=STAMP)
    finally:
        first_store.close()
    second_store = SqliteStore.open(tmp_path / "two.db")
    try:
        second_store.commit_revision(
            a_kettle_book(SECOND_BOOK, SECOND_BRANCH, "The redraw held a different hour."),
            created_at=STAMP,
        )
        [second] = publish(second_store, root=root, generated_at=STAMP)
        assert second.slug == "what-the-kettle-remembers--66666666"
        shutil.rmtree(root / first.slug)
        [again] = publish(second_store, root=root, generated_at=STAMP, force=True)
    finally:
        second_store.close()
    assert again.slug == second.slug
    assert not (root / first.slug).exists(), "the freed bare name is not re-claimed"


def test_a_shelf_published_before_the_marker_existed_keeps_its_name(tmp_path) -> None:
    """Legacy shelves carry no `.book.json`. The volume manifests already say whose the shelf
    is, and a shelf that cannot say at all counts as the publisher's — either way an existing
    shelf never moves and the book keeps its clean name."""
    root = tmp_path / LIBRARY_DIRNAME
    store = SqliteStore.open(tmp_path / "l.db")
    try:
        store.commit_revision(
            a_kettle_book(FIRST_BOOK, FIRST_BRANCH, "The kettle held its first hour."),
            created_at=STAMP,
        )
        [book] = publish(store, root=root, generated_at=STAMP)
        shelf = root / book.slug

        (shelf / SHELF_MARKER_FILENAME).unlink()
        [from_manifests] = publish(store, root=root, generated_at=STAMP, force=True)
        assert from_manifests.slug == book.slug
        assert (shelf / SHELF_MARKER_FILENAME).is_file(), "the marker is restored on publish"

        (shelf / SHELF_MARKER_FILENAME).unlink()
        shutil.rmtree(shelf / "volumes")
        [adopted] = publish(store, root=root, generated_at=STAMP, force=True)
        assert adopted.slug == book.slug
    finally:
        store.close()


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
    import litharness_contracts as lc

    from litharness.cli import EXIT_OK, main

    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK

    # The house genre floor (`domain/genre.py`) refuses to draft a book whose canon holds no
    # starting sheet, so this synthetic book is seeded one at creation — `new --state`, the
    # same door the module docstring names — rather than left to drift and never tick at all.
    state_path = tmp_path / "seed-state.json"
    state_path.write_text(
        json.dumps(
            lc.to_jsonable(
                lc.StateSnapshot(
                    meta=lc.ArtifactMeta(
                        schema_version="1.0.0",
                        artifact_id="state-seed-toll-road",
                        artifact_kind="state_snapshot",
                        created_at=STAMP,
                        actor="test",
                        tool=lc.ToolIdentity(name="test", version="0.1.0"),
                        source_revisions=[],
                    ),
                    book_id=BOOK_ID,
                    branch_id=BRANCH_ID,
                    revision_id="state-seed-toll-road",
                    records=[
                        lc.StateRecord(
                            record_id="seed-status",
                            kind=lc.StateRecordKind.ASSERTION,
                            subject="rook",
                            predicate="status_snapshot",
                            # A mapping since §158: the floor asks for a sheet the
                            # status-line machinery can render numbers from.
                            value={"level": 1},
                            authority=lc.StateAuthority.ACCEPTED_CANON,
                        )
                    ],
                )
            )
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "--database",
                str(db),
                "new",
                "The Toll Road",
                "--premise",
                "A debtor works off an impossible debt.",
                "--scenes",
                "6",
                "--state",
                str(state_path),
            ]
        )
        == EXIT_OK
    )
    root = tmp_path / LIBRARY_DIRNAME
    for _ in range(16):
        main(["--database", str(db), "tick"])
        if list(root.glob("*/chapters/*.html")):
            break
    assert (root / "README.md").is_file(), "no flag was passed and the library exists"
    assert list(root.glob("*/chapters/*.html")), "and it holds pastable chapters"


def test_no_library_turns_the_cadence_off(tmp_path, monkeypatch) -> None:
    from litharness.cli import EXIT_OK, main

    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    main(["--database", str(db), "--no-library", "tick"])
    assert not (tmp_path / LIBRARY_DIRNAME).exists()
