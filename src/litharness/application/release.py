"""The release queue as an operator works it: stage a chapter's copy, approve it, record the
post, withdraw it. Nothing here posts anything (stage-0 §221).

**What was approved is what gets pasted.** `stage_chapter` renders the chapter exactly as
`application/library.py` renders the pastable copy, hashes both renderings, and writes the
copy under its hash into the shelf's `release/` folder, which a tick's republish never touches.
`approve` re-renders the chapter from the store's head and refuses if the hash has moved: a
book re-drafted under a staged entry needs a new entry, never a quiet update of the old one.
`record_posted` is the operator saying, after the fact, that the approved copy went up.

**No selection, no verdict.** Which chapter is staged is the operator's act, taken by chapter
number; the queue does not choose, order, or judge (§61(5), §105.1), and a chapter that is not
pastable — withheld for an undrafted scene, or beyond the book — is refused by name rather than
skipped.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from litharness.application import library
from litharness.application.export import collect
from litharness.application.ports import ReleaseStore
from litharness.domain import release as release_domain
from litharness.domain.release import IllegalRelease, ReleaseEntry, ReleaseStatus
from litharness.domain.text import content_hash


def _pastable_chapter(
    store: ReleaseStore,
    *,
    book_id: str,
    branch_id: str,
    chapter_number: int,
    scenes_per_chapter: int,
    generated_at: str,
) -> tuple[library.Chapter, str, str]:
    """The chapter as the library would paste it now, with the head's revision and title."""
    document = collect(store, book_id=book_id, branch_id=branch_id, generated_at=generated_at)
    chapters, withheld = library.chapters_for(document, scenes_per_chapter=scenes_per_chapter)
    chapter = next((item for item in chapters if item.number == chapter_number), None)
    if chapter is None:
        raise IllegalRelease(
            f"chapter {chapter_number} is not pastable: the book has {len(chapters)} pastable "
            f"chapter(s) at {scenes_per_chapter} scene(s) per chapter and {withheld} withheld "
            "for an undrafted scene"
        )
    return chapter, document.revision_id, document.title


def stage_chapter(
    store: ReleaseStore,
    *,
    book_id: str,
    branch_id: str,
    chapter_number: int,
    scenes_per_chapter: int,
    scheduled_slot: str,
    tags: Sequence[str],
    root: Path,
    generated_at: str,
    staged_at: str,
    note: str | None = None,
) -> tuple[ReleaseEntry, tuple[Path, Path]]:
    """Stage one chapter's pastable copy and write it under its hash. Returns the entry and
    the two files (`.html`, `.txt`) the operator pastes from.

    The tags are the operator's, `AI-Generated` among them or the entry refuses to exist; the
    author note is the disclosure template unless the operator hands one in.
    """
    chapter, revision_id, title = _pastable_chapter(
        store,
        book_id=book_id,
        branch_id=branch_id,
        chapter_number=chapter_number,
        scenes_per_chapter=scenes_per_chapter,
        generated_at=generated_at,
    )
    entry = release_domain.stage(
        book_id=book_id,
        branch_id=branch_id,
        revision_id=revision_id,
        chapter_number=chapter_number,
        chapter_stem=chapter.stem,
        title=title,
        fragment_sha256=content_hash(chapter.fragment),
        plain_sha256=content_hash(chapter.plain),
        tags=tags,
        scheduled_slot=scheduled_slot,
        staged_at=staged_at,
        note=note,
    )
    store.stage_release(entry)
    shelf = root / library.shelf_slug(root, title, book_id)
    copies = library.write_release_copy(shelf, chapter, fragment_sha256=entry.fragment_sha256)
    return entry, copies


def approve(
    store: ReleaseStore,
    release_id: str,
    *,
    by: str,
    at: str,
    scenes_per_chapter: int,
    generated_at: str,
) -> ReleaseEntry:
    """Approve a staged entry under an operator's name, if the book still renders that copy."""
    entry = store.release_entry(release_id)
    if entry is None:
        raise IllegalRelease(f"no release entry {release_id}")
    chapter, _revision_id, _title = _pastable_chapter(
        store,
        book_id=entry.book_id,
        branch_id=entry.branch_id,
        chapter_number=entry.chapter_number,
        scenes_per_chapter=scenes_per_chapter,
        generated_at=generated_at,
    )
    if content_hash(chapter.fragment) != entry.fragment_sha256:
        raise IllegalRelease(
            f"{release_id} was staged at fragment {entry.fragment_sha256[:12]} and the book "
            f"now renders chapter {entry.chapter_number} at "
            f"{content_hash(chapter.fragment)[:12]}; withdraw it and stage the chapter again"
        )
    return store.move_release(release_id, ReleaseStatus.APPROVED, at=at, by=by)


def record_posted(store: ReleaseStore, release_id: str, *, by: str, at: str) -> ReleaseEntry:
    """The operator says the approved copy went up. Recorded after the fact; never done."""
    return store.move_release(release_id, ReleaseStatus.POSTED, at=at, by=by)


def withdraw(
    store: ReleaseStore, release_id: str, *, by: str, at: str, reason: str
) -> ReleaseEntry:
    return store.move_release(release_id, ReleaseStatus.WITHDRAWN, at=at, by=by, reason=reason)


def show(store: ReleaseStore, *, book_id: str, branch_id: str) -> list[ReleaseEntry]:
    return store.release_entries(book_id, branch_id)


__all__ = ["approve", "record_posted", "show", "stage_chapter", "withdraw"]
