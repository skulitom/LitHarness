"""The library: what the system has written, on disk, in two shapes for two readers.

`export` renders one revision for a human and has always been able to; what it lacked was a
cadence and a place. This module is that — a folder republished as the books move, so
"check on progress" is opening a file rather than remembering a command.

**Two shapes, because they have opposite requirements.**

- The **reading copy** is `export`'s document unchanged: the whole book, with derived front
  matter, a progress table, and undrafted scenes rendered as visible placeholders. Its whole
  value is that two copies a day apart differ in a way you can read at a glance, and the gaps
  are the most useful thing on the page.
- The **pastable copy** is per chapter and must contain *none* of that. A progress table pasted
  into a chapter body publishes the scaffolding; a placeholder publishes the words
  `[not yet drafted]` to readers. So a chapter holding an undrafted scene is **withheld and
  counted**, never emitted with a hole in it, and the front matter is absent rather than
  suppressed.

**One scene is one chapter by default, and that is a refusal rather than a choice.** Production
books hold no chapter nodes and no assembly scheme is decided — `pair-draw` already refuses
chapter grain on exactly that ground rather than improvising one. Grouping is available
(`scenes_per_chapter`) because a real serial wants it, and it is an operator act: the tool does
not decide how many scenes make a chapter.

**What the pastable file deliberately does not contain: a title heading.** A serial platform
takes the chapter title in its own field, so a heading in the body is published twice. The
filename carries the title instead.

**The HTML is a fragment, not a document**, and that is what makes one artifact serve both paste
routes: a browser renders a bare run of `<p>` elements perfectly well, so "open it and copy"
works, and there is no `<head>` to strip if it goes into an editor's HTML source view instead.
Only `<p>`, `<blockquote>` and `<hr>` are ever emitted, with no classes, ids or styles — the
conservative subset every rich-text editor preserves. **This is not verified against any
particular platform's editor from inside this repository**, which is why a `.txt` sits beside
every fragment: if the HTML route mangles, blank-line-separated plain text pastes as paragraphs
in every editor there is.

**This is a copy button and not the publication pillar (§62).** That pillar was cut, and what it
was measured to lack was "no chapter-release unit, no hook placement, no recap generation, no
per-chapter export, no publication policy object, no posting scheduler, no publication table".
This adds exactly one of those seven — the per-chapter export, as a file format — and none of
the other six. §62 also settled what publishing *is* here: "publication is that export, run when
the book clears §1a.5's bar." No book has cleared it. *(§126: that bar is the continuation
one, measured on a simulated readership — which is what keeps the gate from being circular,
since a bar needing real readers would have required publishing to learn whether to.)*
These files are for reading, and pasting
one anywhere is an operator decision that condition already governs.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from litharness.application.export import NOT_DRAFTED, BookExport, collect
from litharness.application.ports import ExportStore
from litharness.domain.nodes import Node, NodeKind

#: The folder name, resolved **beside the database it is derived from** rather than against
#: the working directory (`root_for`). That is what lets publishing be on by default without
#: littering: a run against `bz3.db` in the repository writes `book-library/` there, and a test
#: against a database in a temporary directory writes into that temporary directory and takes
#: its output away with it.
#:
#: It supersedes `exports/`, which held hand-run one-off renders and was never a default.
#: Gitignored for the reason that one is: it is derived from the store on every publish, and a
#: generated tree in the index would leave the working copy permanently dirty for every
#: parallel session sharing this repository.
LIBRARY_DIRNAME = "book-library"

#: Kept as the bare relative path for callers that have no database to sit beside.
DEFAULT_ROOT = Path(LIBRARY_DIRNAME)

#: Where the per-book publish state lives: which revision each shelf was built from, so a
#: republish over an unchanged book is a no-op. Dotted so it sorts out of the way of the books.
STATE_FILENAME = ".state.json"


def root_for(database: Path | str) -> Path:
    """The library folder for this database: beside it, named `book-library`.

    Beside rather than under the working directory because the library is *derived from* one
    store and belongs with it. It also makes an on-by-default publish safe: nothing can write
    a folder into whatever directory a command happened to be run from.
    """
    return Path(database).expanduser().resolve().parent / LIBRARY_DIRNAME


#: One scene per chapter. See the module docstring: no assembly scheme is decided, and this
#: is the only grouping that asserts nothing.
DEFAULT_SCENES_PER_CHAPTER = 1

#: A system-voice line: the bracketed all-caps tag the genre puts its state on. Restated from
#: `domain/axes.py`'s `_SYSTEM_LINE` rather than imported, because that one is a *counter's*
#: definition and this one is a *rendering* choice — they agree today and should be free to
#: stop agreeing without one silently changing the other's meaning.
_SYSTEM_LINE = re.compile(r"\[[A-Z][A-Z ]+\]")

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

#: The listing a reader meets before chapter one, written into every shelf. What
#: `application/overview.py` produces and what `new --premise` stores are the same string,
#: so a book seeded either way has one here.
OVERVIEW_FILENAME = "overview.txt"

NOTES_FILENAME = "NOTES.md"

#: The notes template, written once and never overwritten. It exists because a human read is
#: not only a progress check: `plan/reader-judge-loop.md` §2.1 makes "a human read named a
#: defect" the first of exactly two doors an axis can enter the registry by, and the first
#: human read of a generated book is what produced all three registered axes. A read with
#: somewhere to put what it noticed is a defect harvest; a read without one is a memory.
NOTES_TEMPLATE = """# Reading notes

What you noticed, in your own words. This file is never overwritten.

**Why it is worth writing anything down.** A named defect from a human read is one of the two
ways a new axis can enter the registry (`plan/reader-judge-loop.md` §2.1) — the other is a
nomination from the judge discard corpus. All three axes the system currently measures came
from one read of one book that named three things: flat stats, no interiority, em dashes. So a
read is a defect harvest, and each defect is a candidate axis with its provenance attached.

**What is useful to write.** What you noticed, where, and what it did to the reading. A defect
that can be pointed at is a defect a counter can be built for; "chapter four dragged" is a
feeling, and "nothing changed between the start and end of chapter four" is an axis.

**One caveat on this read.** It is not blinded — the reading copy carries a progress table and
a revision id, and `audit` deliberately shows neither. That does not make what you noticed
wrong; it means a note from here is evidence of the same class as the first human read, and
not of the blinded pairwise class. That class is no longer reachable at all: the scope axiom
(stage-0 §95) forbids soliciting judgment, so an unblinded operator note is not a weaker version
of some better evidence that might be bought later — it is a different thing entirely, and what
it is good for is *locating* a defect a counter can be built for.

---

"""


def slugify(title: str, fallback: str) -> str:
    """A filename-safe name for a book. Falls back to the id when a title is unusable."""
    slug = _SLUG_STRIP.sub("-", title.strip().lower()).strip("-")
    return slug or fallback[:12]


@dataclass(frozen=True, slots=True)
class Chapter:
    """One pastable unit: the scenes it holds, and the two renderings of them."""

    #: Which chapter this is, counted from the grouping rather than from the scenes inside
    #: it, so a withheld chapter leaves a gap in the numbering instead of renaming the ones
    #: after it. Chapter 3 stays chapter 3 when chapter 2 is not ready.
    number: int
    #: The first scene's ordinal. Provenance only: nothing a reader sees is derived from it.
    ordinal: int
    title: str
    logical_ids: tuple[str, ...]
    words: int
    fragment: str
    plain: str

    @property
    def stem(self) -> str:
        """`Chapter3` — the filename an operator pastes from.

        **It used to be `03-scene-3-3-4`, and that was the harness talking.** The stem was
        built from the first scene's title and the scene range it covered, so the unit of work
        reached the one artifact that exists to be handed to a reader. A scene is internal; the
        file is not."""
        return f"Chapter{self.number}"


@dataclass(frozen=True, slots=True)
class PublishedBook:
    """One book's place in the library, and what was held back from it."""

    book_id: str
    branch_id: str
    slug: str
    title: str
    summary: str
    drafted: int
    total: int
    words: int
    chapters: tuple[Chapter, ...]
    #: Chapters not emitted because they hold a scene with no prose yet. Counted rather than
    #: dropped: a pastable set that silently skipped its gaps would read as a finished serial.
    withheld: int
    #: The revision this shelf was built from, and when. Together they are what makes a
    #: republish over an unchanged book a no-op — and what lets the index answer "is this
    #: current" with a fact rather than with the time somebody last ran the command.
    revision_id: str = ""
    published_at: str = ""
    #: False when this shelf was already current and nothing was written for it.
    rewritten: bool = True


def _blocks(content: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]


def paste_fragment(scenes: Sequence[Node]) -> str:
    """The chapter body as minimal semantic HTML, and nothing else.

    Escaped as text, exactly as `export._paragraphs` escapes it and for the same reason: a
    stray `<` in prose swallows everything up to the next `>` and the loss is silent.

    System-voice lines become `<blockquote>`. That is a rendering choice rather than a fact
    about the prose, and it is made because a stat block set as an ordinary paragraph reads as
    a sentence — the genre sets it apart, and every rich-text editor keeps a blockquote.
    """
    parts: list[str] = []
    for index, scene in enumerate(scenes):
        if index:
            # A scene break inside a grouped chapter. `<hr>` rather than a row of asterisks
            # because it survives a paste as structure instead of as three characters.
            parts.append("<hr>")
        for block in _blocks(scene.content or ""):
            tag = "blockquote" if _SYSTEM_LINE.search(block) else "p"
            parts.append(f"<{tag}>{html.escape(block)}</{tag}>")
    return "\n".join(parts) + "\n"


def paste_plain(scenes: Sequence[Node]) -> str:
    """The same body as blank-line-separated plain text.

    The fallback, and it is here because the claim "this HTML pastes correctly" is not one this
    repository can verify against any particular editor. Plain text with blank lines between
    paragraphs pastes as paragraphs everywhere, so the uncertainty costs one small file rather
    than a failed publish.
    """
    parts: list[str] = []
    for index, scene in enumerate(scenes):
        if index:
            parts.append("* * *")
        parts.extend(_blocks(scene.content or ""))
    return "\n\n".join(parts) + "\n"


def _scene_nodes(document: BookExport) -> list[Node]:
    return [node for node in document.body if node.kind is NodeKind.SCENE]


def chapters_for(
    document: BookExport, *, scenes_per_chapter: int = DEFAULT_SCENES_PER_CHAPTER
) -> tuple[tuple[Chapter, ...], int]:
    """Group this book's scenes into pastable chapters, withholding the incomplete ones.

    Returns the chapters and how many groups were withheld. A group is withheld whole: a
    chapter that dropped its undrafted scene and kept the rest would publish a jump-cut, which
    is worse than publishing nothing because nothing is visible and a jump-cut is not.
    """
    scenes = _scene_nodes(document)
    ordinals = {scene.logical_id: scene.ordinal for scene in document.scenes}
    chapters: list[Chapter] = []
    withheld = 0
    size = max(scenes_per_chapter, 1)
    for start in range(0, len(scenes), size):
        group = scenes[start : start + size]
        number = start // size + 1
        if any(not (node.content or "").strip() for node in group):
            withheld += 1
            continue
        ordinal = ordinals.get(group[0].logical_id, number)
        chapters.append(
            Chapter(
                number=number,
                ordinal=ordinal,
                # **Named for what it is to a reader.** The title travels to a serial platform
                # in its own field, so a scene's title reaching it would publish the harness's
                # vocabulary under the book's name.
                title=f"Chapter {number}",
                logical_ids=tuple(node.logical_id for node in group),
                words=sum(len((node.content or "").split()) for node in group),
                fragment=paste_fragment(group),
                plain=paste_plain(group),
            )
        )
    return tuple(chapters), withheld


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def publish_book(
    document: BookExport,
    *,
    root: Path,
    scenes_per_chapter: int = DEFAULT_SCENES_PER_CHAPTER,
) -> PublishedBook:
    """Write one book's shelf: the reading copies, the pastable chapters, and the notes file."""
    slug = slugify(document.title, document.book_id)
    shelf = root / slug
    _write(shelf / f"{slug}.md", document.as_markdown(scenes_per_chapter))
    _write(shelf / f"{slug}.html", document.as_html(scenes_per_chapter))

    if document.premise:
        # **The listing, on its own, in the shelf.** It is inside both reading copies
        # already, as a blockquote under the front matter — and a platform's description
        # field cannot reach into a blockquote. This is the same argument the pastable
        # chapters are built on: the file a person copies from should contain exactly what
        # they are pasting and nothing else. Plain text for the same reason the chapters
        # carry a `.txt` beside the fragment.
        _write(shelf / OVERVIEW_FILENAME, document.premise.strip() + "\n")

    chapters, withheld = chapters_for(document, scenes_per_chapter=scenes_per_chapter)
    folder = shelf / "chapters"
    # **Stale chapters are removed, and this is the one destructive act in the module.** A
    # chapter file left behind after its scene was repaired would be the copy somebody pastes,
    # and it would be wrong in the way that is hardest to notice: readable, plausible, and not
    # what the book says. Only files this function writes are eligible, so nothing an operator
    # put in the folder is touched.
    keep = {f"{chapter.stem}.html" for chapter in chapters} | {
        f"{chapter.stem}.txt" for chapter in chapters
    }
    if folder.is_dir():
        for existing in folder.iterdir():
            if existing.is_file() and existing.name not in keep:
                existing.unlink()
    for chapter in chapters:
        _write(folder / f"{chapter.stem}.html", chapter.fragment)
        _write(folder / f"{chapter.stem}.txt", chapter.plain)

    notes = shelf / NOTES_FILENAME
    if not notes.exists():
        # Written once. Overwriting somebody's reading notes with a template on the next tick
        # is the kind of data loss that is discovered a week later.
        _write(notes, NOTES_TEMPLATE)

    return PublishedBook(
        book_id=document.book_id,
        branch_id=document.branch_id,
        slug=slug,
        title=document.title,
        summary=document.summary,
        drafted=document.drafted,
        total=document.total,
        words=document.words,
        chapters=chapters,
        withheld=withheld,
    )


INDEX_PREAMBLE = """# Library

What the system has written, republished as the books move. Everything here is derived from
the store on every publish, so nothing in this folder is a source of truth and editing a file
here changes no book — except `NOTES.md`, which is yours and is never overwritten.

Each book has a shelf:

- `<book>.md` and `<book>.html` — the **reading copy**: the whole book with a progress table,
  and undrafted scenes shown as visible gaps. The gaps are the point; two copies a day apart
  differ in a way you can read at a glance.
- `chapters/NN-title.html` — one **pastable** chapter each, as minimal HTML with no title
  heading (a serial platform takes the title in its own field, so a heading in the body is
  published twice). Open one in a browser, select all, copy.
- `chapters/NN-title.txt` — the same chapter as plain text, for any editor the HTML route
  does not survive.
- `NOTES.md` — what you noticed. Worth writing: a named defect from a human read is one of
  only two ways a new axis enters the registry, and all three the system measures today came
  from one read of one book.

**A chapter holding an undrafted scene is withheld, not emitted with a hole in it.** The count
is in the table below.

**These files are not a publication.** §62 settled what publishing is here — the export, run
when the book clears the bar of PLAN §1a.5 — and no book has cleared it. Pasting one anywhere is a
decision that condition governs, and nothing in this folder asserts otherwise.

**One caveat if you read here and then direct.** Reading your own book and dropping a directive
is the intended workflow (§4.3: direct, don't operate). What it makes you is a *steering* reader
— so your reader id belongs in the steering pool and never in the measurement pool, or the
prose you shaped and the prose you later judge would be the same prose, which is precisely what
the measurement firewall exists to prevent. `litharness pools --who <your-id>` says which side
you are on.
"""


def index_markdown(books: Sequence[PublishedBook], *, checked_at: str) -> str:
    """The shelf listing, with the two times that answer different questions.

    **`Last checked` is when the publisher last looked; `Changed` is when that book last
    moved.** They are separated because collapsing them is how a folder starts lying about
    freshness: one restamped timestamp says "published just now" about a book nothing has
    touched for a week, which is exactly the reassurance somebody checking on progress must
    not be given.
    """
    lines = [INDEX_PREAMBLE, "", f"*Last checked {checked_at}*", ""]
    if not books:
        lines += ["No book in this store yet. `litharness new` or `litharness import`.", ""]
        return "\n".join(lines)
    lines += [
        "| Book | Drafted | Words | Chapters | Withheld | Changed |",
        "| --- | --: | --: | --: | --: | --- |",
    ]
    for book in books:
        lines.append(
            f"| [{book.title}]({book.slug}/{book.slug}.md) | {book.drafted}/{book.total} "
            f"| {book.words:,} | {len(book.chapters)} | {book.withheld} "
            f"| {book.published_at or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _read_state(root: Path) -> dict[str, dict[str, str]]:
    """What each shelf was last built from. A missing or unreadable file means "rebuild all".

    Unreadable rather than raising: this file is a cache of a fact the store already holds, so
    a corrupted one costs a republish and never a run. The books are the truth; this is only
    how the publisher avoids rewriting them for nothing.
    """
    path = root / STATE_FILENAME
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def publish(
    store: ExportStore,
    *,
    root: Path = DEFAULT_ROOT,
    generated_at: str,
    scenes_per_chapter: int = DEFAULT_SCENES_PER_CHAPTER,
    force: bool = False,
) -> tuple[PublishedBook, ...]:
    """Republish every book in the store. Pure output: reads the store, writes files.

    Every branch, rather than a resolved one: the library is the shelf, and a shelf that held
    whichever book sorted lowest would be the wrong thing to check progress against.

    **A book whose head has not moved is skipped, and that is what makes this safe to run on
    every tick.** Revisions are content-addressed, so "the head is the revision this shelf was
    built from" is an exact statement rather than a heuristic about timestamps. A quiet system
    therefore rewrites nothing but the index, and the index is rewritten every time because its
    job is to answer *is this current* — which needs the time somebody last checked as well as
    the time the content last changed. `force` is the escape hatch for a publisher change: the
    files are derived, so the way to adopt a new rendering is to rebuild them all.
    """
    state = {} if force else _read_state(root)
    published: list[PublishedBook] = []
    for book_id, branch_id, head_id in store.branches():
        known = state.get(book_id, {})
        if known.get("revision_id") == head_id and known.get("scenes_per_chapter") == str(
            scenes_per_chapter
        ):
            # Already current. The recorded `published_at` is kept rather than restamped: it
            # says when this book last *changed*, and overwriting it with now would turn the
            # index's most useful column into a synonym for "the publisher ran".
            document = collect(
                store, book_id=book_id, branch_id=branch_id, generated_at=generated_at
            )
            chapters, withheld = chapters_for(document, scenes_per_chapter=scenes_per_chapter)
            published.append(
                PublishedBook(
                    book_id=book_id,
                    branch_id=branch_id,
                    slug=slugify(document.title, book_id),
                    title=document.title,
                    summary=document.summary,
                    drafted=document.drafted,
                    total=document.total,
                    words=document.words,
                    chapters=chapters,
                    withheld=withheld,
                    revision_id=head_id,
                    published_at=known.get("published_at", generated_at),
                    rewritten=False,
                )
            )
            continue
        document = collect(store, book_id=book_id, branch_id=branch_id, generated_at=generated_at)
        book = publish_book(document, root=root, scenes_per_chapter=scenes_per_chapter)
        published.append(
            replace(
                book,
                revision_id=document.revision_id,
                published_at=generated_at,
                rewritten=True,
            )
        )
    _write(root / "README.md", index_markdown(published, checked_at=generated_at))
    _write(
        root / STATE_FILENAME,
        json.dumps(
            {
                book.book_id: {
                    "revision_id": book.revision_id,
                    "published_at": book.published_at,
                    "scenes_per_chapter": str(scenes_per_chapter),
                }
                for book in published
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return tuple(published)


__all__ = [
    "DEFAULT_ROOT",
    "DEFAULT_SCENES_PER_CHAPTER",
    "INDEX_PREAMBLE",
    "LIBRARY_DIRNAME",
    "NOTES_FILENAME",
    "NOTES_TEMPLATE",
    "NOT_DRAFTED",
    "STATE_FILENAME",
    "Chapter",
    "PublishedBook",
    "chapters_for",
    "index_markdown",
    "paste_fragment",
    "paste_plain",
    "publish",
    "publish_book",
    "root_for",
    "slugify",
]
