"""A reading copy of the book as it stands, with the gaps left visible.

Until this module existed there was no way to *read* what the system had written. The prose
lives in `node_versions` rows keyed by content address, `backup` produces another database,
and `verify` proves every revision rebuilds without printing a word of it. A director could
see that four scenes had been accepted and could not see the book.

**Undrafted scenes are rendered as placeholders, never omitted.** A document that silently
skips the empty nodes reads as a finished short book rather than an unfinished long one, and
the gap is the single most useful thing on the page — it is what the next tick will fill.
The same reasoning puts a progress table in the front matter instead of leaving the reader
to infer completeness from length: two exports a day apart should differ in a way you can
read at a glance, which is what "see progress over time" means mechanically.

**The front matter is derived, never stored.** Every number on it — scene count, word count,
drafted-versus-empty — is recomputed from the revision being exported. Persisting a progress
row would create a second source of truth for a fact the manuscript already answers, and the
two would eventually disagree; the export would then be the one that lies, because it is the
one nobody re-derives.

**Markdown escaping is structural only.** Scene prose is passed through as Markdown, so
`*italics*` an author wrote survive. The exception is the handful of constructs that would
restructure the *document* rather than style a phrase: a line of prose beginning `#` becomes
a heading and silently joins the book's own hierarchy, and a line of `---` becomes a
thematic break or turns the paragraph above it into a heading. Those are escaped. The
distinction is between markup that changes how a sentence looks, which is the author's
business, and markup that changes what the document's outline claims, which is corruption.

**This is a source document, not a PDF.** Rendering type is a typesetting problem with a
mature answer on every platform, and shipping a PDF writer here would mean owning font
metrics, hyphenation and page breaking in a repository whose only runtime dependency is its
own contracts package. The HTML output carries print CSS — `@page` margins, chapter page
breaks, orphan and widow control — so a browser's "Save as PDF" produces a readable book;
`pandoc export.md -o book.pdf` is the other path. Both are one command, and neither is a
font table this project has to maintain.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from litharness.application.ports import ExportStore
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plans import premise_of

#: Written into an undrafted scene in place of prose. Deliberately conspicuous in both
#: formats: this is the thing the reader is meant to notice.
NOT_DRAFTED = "[not yet drafted]"

#: Line-leading constructs that would restructure the document. See the module docstring.
_STRUCTURAL_MARKDOWN = re.compile(r"^(?:#{1,6}(?:\s|$)|-{3,}\s*$|={3,}\s*$)")


def _words(content: str | None) -> int:
    """Whitespace-delimited tokens. An approximation, and reported as one — nothing in this
    system pays per word, so a typesetter's count would be precision without a consumer."""
    return len(content.split()) if content else 0


@dataclass(frozen=True, slots=True)
class SceneProgress:
    """One scene's line in the progress table."""

    logical_id: str
    ordinal: int
    title: str | None
    words: int
    drafted: bool
    #: A content lock. Reported because a locked empty scene will *never* be drafted by a
    #: tick, so counting it as merely pending would misstate how far off the book is.
    locked: bool = False

    @property
    def label(self) -> str:
        return self.title or f"Scene {self.ordinal}"

    @property
    def state(self) -> str:
        if self.drafted:
            return "locked" if self.locked else "drafted"
        return "locked, empty" if self.locked else "not yet drafted"


@dataclass(frozen=True, slots=True)
class BookExport:
    """A revision rendered for a human, with its own completeness stated on the front."""

    book_id: str
    branch_id: str
    revision_id: str
    generated_at: str
    title: str
    premise: str | None
    #: Reading order, live nodes only, the book root already removed — its title is the
    #: document's title and rendering it again would produce two.
    body: tuple[Node, ...]
    scenes: tuple[SceneProgress, ...]

    @property
    def drafted(self) -> int:
        return sum(1 for scene in self.scenes if scene.drafted)

    @property
    def total(self) -> int:
        return len(self.scenes)

    @property
    def words(self) -> int:
        return sum(scene.words for scene in self.scenes)

    @property
    def summary(self) -> str:
        return f"{self.drafted} of {self.total} scene(s) drafted · {self.words:,} word(s)"

    # -- markdown -------------------------------------------------------------

    def chapter_groups(
        self, scenes_per_chapter: int = 1
    ) -> list[tuple[str, tuple[SceneProgress, ...]]]:
        """The book as a reader receives it: numbered chapters holding scenes.

        One scene is one chapter by default, which asserts nothing. What it buys is that no
        output has to name a scene in order to say where something sits.
        """
        size = max(scenes_per_chapter, 1)
        groups: list[tuple[str, tuple[SceneProgress, ...]]] = []
        for start in range(0, len(self.scenes), size):
            groups.append((f"Chapter {len(groups) + 1}", tuple(self.scenes[start : start + size])))
        return groups

    def reading_summary(self, scenes_per_chapter: int = 1) -> str:
        """The completeness line for the document itself, counted in chapters.

        `summary` stays counted in scenes because its readers are operator surfaces — the tick
        log — where the unit of work is the right unit. The document is not one of those: it
        is the thing being read, so it says how many chapters are whole.
        """
        groups = self.chapter_groups(scenes_per_chapter)
        whole = sum(1 for _, group in groups if all(scene.drafted for scene in group))
        return f"{whole} of {len(groups)} chapter(s) complete · {self.words:,} word(s)"

    def as_markdown(self, scenes_per_chapter: int = 1) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"*{self.reading_summary(scenes_per_chapter)} · {self.generated_at}*",
            "",
            f"- revision `{self.revision_id}`",
            f"- book `{self.book_id}` · branch `{self.branch_id}`",
            "",
        ]
        if self.premise:
            lines += [f"> **Premise.** {_markdown_safe(self.premise)}", ""]
        lines += self._progress_table(scenes_per_chapter)
        lines += ["", "---", ""]

        chapters = self.chapter_groups(scenes_per_chapter)
        # **A book that asserts its own structure keeps it, and gets no synthetic chapters on
        # top.** Parts and chapters in the manuscript are the author's; the grouping below is
        # this harness's way of giving a flat book a reader-facing unit, and running both
        # would put two competing outlines over one text.
        flat = all(node.kind is NodeKind.SCENE for node in self.body)
        opens = {group[0].logical_id: title for title, group in chapters if group} if flat else {}
        for node, level in _levelled(self.body):
            title = opens.get(node.logical_id)
            if title is not None:
                lines += [f"## {title}", ""]
            lines += _markdown_node(node, level, self._ordinals, first=title is not None)
        return "\n".join(lines).rstrip() + "\n"

    def _progress_table(self, scenes_per_chapter: int = 1) -> list[str]:
        """Gap visibility at the grain the reader is handed, which is the chapter.

        A per-scene table was the last place the word "scene" reached a reader, so "2 of 4
        drafted" reports the same gap without teaching the vocabulary."""
        rows = ["| Chapter | Words | State |", "| --- | --: | --- |"]
        for title, group in self.chapter_groups(scenes_per_chapter):
            drafted = sum(1 for scene in group if scene.drafted)
            words = sum(scene.words for scene in group if scene.drafted)
            state = "complete" if drafted == len(group) else f"{drafted} of {len(group)} drafted"
            rows.append(f"| {_cell(title)} | {words:,} | {state} |")
        return rows

    @property
    def _ordinals(self) -> dict[str, int]:
        return {scene.logical_id: scene.ordinal for scene in self.scenes}

    # -- html -----------------------------------------------------------------

    def as_html(self, scenes_per_chapter: int = 1) -> str:
        parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{html.escape(self.title)}</title>",
            f"<style>{_PRINT_CSS}</style>",
            "</head>",
            "<body>",
            '<header class="front">',
            f"<h1>{html.escape(self.title)}</h1>",
            f'<p class="summary">{html.escape(self.reading_summary(scenes_per_chapter))}</p>',
            f'<p class="provenance">revision <code>{html.escape(self.revision_id)}</code>'
            f"<br>book <code>{html.escape(self.book_id)}</code>"
            f" · branch <code>{html.escape(self.branch_id)}</code>"
            f"<br>exported {html.escape(self.generated_at)}</p>",
        ]
        if self.premise:
            parts.append(
                f'<blockquote class="premise"><strong>Premise.</strong> '
                f"{html.escape(self.premise)}</blockquote>"
            )
        parts += self._progress_html(scenes_per_chapter)
        parts.append("</header>")

        flat = all(node.kind is NodeKind.SCENE for node in self.body)
        opens = (
            {
                group[0].logical_id: title
                for title, group in self.chapter_groups(scenes_per_chapter)
                if group
            }
            if flat
            else {}
        )
        for node, level in _levelled(self.body):
            title = opens.get(node.logical_id)
            if title is not None:
                parts.append(f"<h2>{html.escape(title)}</h2>")
            parts += _html_node(node, level, self._ordinals, first=title is not None)
        parts += ["</body>", "</html>"]
        return "\n".join(parts) + "\n"

    def _progress_html(self, scenes_per_chapter: int = 1) -> list[str]:
        rows = [
            '<table class="progress">',
            "<thead><tr><th>Chapter</th><th>Words</th><th>State</th></tr></thead>",
            "<tbody>",
        ]
        for title, group in self.chapter_groups(scenes_per_chapter):
            drafted = sum(1 for scene in group if scene.drafted)
            words = sum(scene.words for scene in group if scene.drafted)
            complete = drafted == len(group)
            state = "complete" if complete else f"{drafted} of {len(group)} drafted"
            rows.append(
                f'<tr class="{"drafted" if complete else "pending"}">'
                f"<td>{html.escape(title)}</td><td>{words:,}</td>"
                f"<td>{html.escape(state)}</td></tr>"
            )
        rows += ["</tbody>", "</table>"]
        return rows


# -- rendering helpers --------------------------------------------------------------


def _markdown_safe(text: str) -> str:
    """Escape line-leading constructs that would restructure the document, nothing else."""
    return "\n".join(
        "\\" + line if _STRUCTURAL_MARKDOWN.match(line) else line for line in text.split("\n")
    )


def _cell(text: str) -> str:
    """A table cell. An unescaped pipe in a scene title splits the row into two columns and
    the rest of the table renders shifted, which looks like a bug in the book."""
    return _markdown_safe(text).replace("|", r"\|").replace("\n", " ")


def _levelled(body: tuple[Node, ...]) -> list[tuple[Node, int]]:
    """Pair each node with its heading level, derived from its depth below the book root.

    Depth rather than kind, because the tree is what the manuscript actually asserts: a
    scene directly under the book and a scene under a part-and-chapter are at different
    depths and should not both be `<h2>`. Clamped at 6, which is where HTML stops.
    """
    parents = {node.logical_id: node.parent_logical_id for node in body}
    levelled = []
    for node in body:
        depth, cursor = 0, parents.get(node.logical_id)
        while cursor is not None and cursor in parents:
            depth += 1
            cursor = parents[cursor]
        levelled.append((node, min(2 + depth, 6)))
    return levelled


def _heading(node: Node, ordinals: dict[str, int]) -> str:
    if node.kind is NodeKind.SCENE:
        ordinal = ordinals.get(node.logical_id)
        prefix = f"{ordinal}. " if ordinal else ""
        return f"{prefix}{node.title}" if node.title else f"Scene {ordinal or ''}".strip()
    return node.title or node.logical_id


#: The break between two scenes inside one chapter. A reader sees a pause; nobody sees a
#: scene number.
SCENE_BREAK = "* * *"


def _markdown_node(
    node: Node, level: int, ordinals: dict[str, int], *, first: bool = True
) -> list[str]:
    """**A scene never gets a heading.** The scene is this system's unit of work, not the
    book's unit of reading, and a reader who is shown "Scene 5" has been shown the machinery.
    Author-made structure — parts, chapters a book actually has — keeps its heading, because
    that is the book asserting it rather than the harness leaking it."""
    if node.kind is NodeKind.SCENE:
        lines = [] if first else [SCENE_BREAK, ""]
    else:
        lines = [f"{'#' * level} {_markdown_safe(_heading(node, ordinals))}", ""]
    if node.kind is NodeKind.BLOCK:
        # §11 wants game-system displays rendered from their payload rather than from
        # prose. Nothing renders one yet, so the block's text is shown set apart and the
        # payload is left alone — inventing a presentation here would be the fastest way
        # to have two of them.
        body = node.content or NOT_DRAFTED
        lines += [f"> {line}" for line in _markdown_safe(body).split("\n")] + [""]
    elif node.content:
        lines += [_markdown_safe(node.content), ""]
    elif node.kind is NodeKind.SCENE:
        lines += [f"*{NOT_DRAFTED}*", ""]
    return lines


def _html_node(
    node: Node, level: int, ordinals: dict[str, int], *, first: bool = True
) -> list[str]:
    tag = f"h{level}"
    # "prose" rather than "scene": nothing styles this class, and the scene is internal, so
    # naming it here would leak the unit of work into the markup of the one artifact a reader
    # is handed. Author-made structure keeps its own kind.
    section = "prose" if node.kind is NodeKind.SCENE else node.kind.value
    parts = [f'<section class="{section}">']
    if node.kind is NodeKind.SCENE:
        # No heading, ever — see `_markdown_node`. An `<hr>` marks the pause between two
        # scenes inside one chapter, because it survives a paste as structure rather than as
        # three characters.
        if not first:
            parts.append("<hr>")
    else:
        parts.append(f"<{tag}>{html.escape(_heading(node, ordinals))}</{tag}>")
    if node.kind is NodeKind.BLOCK:
        body = node.content or NOT_DRAFTED
        parts.append(f'<aside class="block">{_paragraphs(body)}</aside>')
    elif node.content:
        parts.append(_paragraphs(node.content))
    elif node.kind is NodeKind.SCENE:
        parts.append(f'<p class="gap">{html.escape(NOT_DRAFTED)}</p>')
    parts.append("</section>")
    return parts


def _paragraphs(content: str) -> str:
    """Blank-line-separated prose as `<p>` elements, escaped as text.

    Escaped rather than passed through: HTML has no equivalent of the structural-only
    compromise Markdown gets, because a stray `<` in prose swallows everything up to the
    next `>` and the loss is silent.
    """
    blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
    return "\n".join(f"<p>{html.escape(block)}</p>" for block in blocks)


_PRINT_CSS = """
:root { --ink: #16130f; --faint: #6b6257; --rule: #ddd6cc; --gap: #b3402a; }
body { max-width: 34em; margin: 3rem auto; padding: 0 1.5rem;
  font: 12pt/1.65 "Iowan Old Style", Georgia, "Times New Roman", serif; color: var(--ink); }
h1 { font-size: 2rem; line-height: 1.2; margin: 0 0 .5rem; }
h2, h3, h4, h5, h6 { line-height: 1.25; margin: 2.5rem 0 .75rem; }
p { margin: 0; text-indent: 1.4em; }
p:first-of-type, .gap { text-indent: 0; }
.front { border-bottom: 1px solid var(--rule); padding-bottom: 2rem; margin-bottom: 1rem; }
.summary { font-weight: 600; text-indent: 0; }
.provenance { color: var(--faint); font-size: .8rem; text-indent: 0; margin-top: .5rem; }
.premise { border-left: 3px solid var(--rule); margin: 1.5rem 0; padding: 0 0 0 1rem;
  color: var(--faint); font-style: italic; }
.progress { border-collapse: collapse; width: 100%; margin-top: 1.5rem; font-size: .85rem; }
.progress th, .progress td { text-align: left; padding: .3rem .6rem .3rem 0;
  border-bottom: 1px solid var(--rule); }
.progress td:first-child, .progress td:nth-child(3) { text-align: right; }
.progress tr.pending { color: var(--gap); }
.gap { color: var(--gap); font-style: italic; }
aside.block { border: 1px solid var(--rule); padding: .75rem 1rem; margin: 1.5rem 0;
  font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace; font-size: .85rem; }
aside.block p { text-indent: 0; }
code { font-size: .85em; word-break: break-all; }
@media print {
  body { margin: 0; max-width: none; }
  h2 { break-before: page; }
  .front { break-after: page; border: 0; }
  h1, h2, h3, h4, h5, h6 { break-after: avoid; }
  p { orphans: 2; widows: 2; }
}
@page { margin: 2cm; }
""".strip()


# -- collection ---------------------------------------------------------------------


def collect(
    store: ExportStore,
    *,
    book_id: str,
    branch_id: str,
    generated_at: str,
    revision_id: str | None = None,
) -> BookExport:
    """Read a revision and everything the front matter needs to describe it.

    ``revision_id`` defaults to the branch head. Naming an older one is how two exports get
    compared: the revisions are immutable, so an export of revision N is reproducible
    forever apart from its `generated_at` stamp.
    """
    if revision_id is None:
        revision = store.head(book_id, branch_id)
        if revision is None:
            raise ValueError(
                f"no head revision for book {book_id} branch {branch_id}; "
                "`litharness import` is what creates one"
            )
    else:
        try:
            revision = store.load_revision(revision_id)
        except KeyError as error:
            # A mistyped revision id is a bad argument, and the CLI maps bad arguments onto
            # the operational exit code. `KeyError` is not in that handler, so left as it
            # was it escaped as a traceback under the exit code reserved for "a unit needs
            # a human" — the same confusion the locked-database case was fixed for.
            raise ValueError(f"no revision {revision_id} in this store") from error
        if (revision.book_id, revision.branch_id) != (book_id, branch_id):
            # Exporting a revision from a different book under this book's front matter
            # would produce a document whose provenance block is a lie, and provenance is
            # most of why the front matter exists.
            raise ValueError(
                f"revision {revision_id[:12]} belongs to book {revision.book_id} "
                f"branch {revision.branch_id}, not {book_id} {branch_id}"
            )

    ordered = revision.in_reading_order()
    # Filtered by kind rather than by identity: `Node` is a value type, so two structurally
    # identical nodes compare equal and an identity filter would drop whichever one it
    # matched first.
    title = next(
        (node.title for node in ordered if node.kind is NodeKind.BOOK and node.title), None
    )
    body = tuple(node for node in ordered if node.kind is not NodeKind.BOOK)

    scenes = tuple(
        SceneProgress(
            logical_id=node.logical_id,
            ordinal=index,
            title=node.title,
            words=_words(node.content),
            drafted=bool(node.content),
            locked=node.lock.freezes_content,
        )
        for index, node in enumerate(
            (node for node in body if node.kind is NodeKind.SCENE), start=1
        )
    )

    return BookExport(
        book_id=book_id,
        branch_id=branch_id,
        revision_id=revision.revision_id,
        generated_at=generated_at,
        title=title or "Untitled",
        premise=premise_of(store.plan_items(book_id, branch_id)),
        body=body,
        scenes=scenes,
    )


def resolve_branch(
    store: ExportStore, book_id: str | None, branch_id: str | None
) -> tuple[str, str]:
    """The branch to export, defaulting to the only one when there is exactly one.

    Most stores hold one book, and making an operator paste two UUIDs to read it would be
    ceremony. More than one is ambiguous rather than defaultable — picking the first would
    export whichever book sorted lowest and say nothing about the others — so it lists what
    it found and asks.
    """
    branches = store.branches()
    candidates = [
        (book, branch)
        for book, branch, _ in branches
        if (book_id is None or book == book_id) and (branch_id is None or branch == branch_id)
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not branches:
        raise ValueError("no book in this store; `litharness import` is what puts one in")
    known = "\n".join(f"  --book {book} --branch {branch}" for book, branch, _ in branches)
    if not candidates:
        raise ValueError(f"no branch matches that book and branch. Known branches:\n{known}")
    raise ValueError(
        f"{len(candidates)} branches match; name one with --book and --branch:\n{known}"
    )


__all__ = ["NOT_DRAFTED", "BookExport", "SceneProgress", "collect", "resolve_branch"]
