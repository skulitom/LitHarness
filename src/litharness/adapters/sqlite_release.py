"""The release queue's persistence: rows an operator moves, and nothing a program posts from.

**Its own capability repository** for `CONTRIBUTING.md`'s reason: cohesive persistence
behaviour with one invariant, and the facade gets thin delegates. The invariant is the state
machine of `domain/release.py` — every move past `staged` carries an operator's name — and it
is enforced twice: `transition` refuses in the domain, and migration 039's CHECKs refuse in the
schema, so a row a program filled in past `staged` cannot exist by either route.

**No decision row is written here, and that is a decision.** The roster's accept and refuse
write a `PolicyDecision` because admitting a writer is a judgment about a candidate. Staging,
approving and recording a post are not judgments about prose; they are an operator's acts on a
copy already accepted through the gate ladder, and putting them in `policy_decisions` would
have the spend ledger and the digest read a publication act as an acceptance. The row carries
who moved it, when, and (for a withdrawal) why, and that is the whole record.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from litharness.adapters.sqlite_errors import IntegrityFailure
from litharness.adapters.sqlite_jobs import TransactionFactory
from litharness.domain.release import (
    IllegalRelease,
    ReleaseEntry,
    ReleaseStatus,
    transition,
)

_COLUMNS = (
    "release_id, book_id, branch_id, revision_id, chapter_number, chapter_stem, title, "
    "fragment_sha256, plain_sha256, author_note, tags_json, scheduled_slot, status, staged_at, "
    "approved_at, approved_by, posted_at, posted_by, withdrawn_at, withdrawn_by, "
    "withdrawn_reason"
)

_LIVE = "('staged', 'approved', 'posted')"


def _tags(raw: str, *, release_id: str) -> tuple[str, ...]:
    payload = json.loads(raw)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise IntegrityFailure(f"release {release_id} has a malformed tags_json")
    return tuple(payload)


def _entry_from_row(row: sqlite3.Row) -> ReleaseEntry:
    return ReleaseEntry(
        release_id=row["release_id"],
        book_id=row["book_id"],
        branch_id=row["branch_id"],
        revision_id=row["revision_id"],
        chapter_number=row["chapter_number"],
        chapter_stem=row["chapter_stem"],
        title=row["title"],
        fragment_sha256=row["fragment_sha256"],
        plain_sha256=row["plain_sha256"],
        author_note=row["author_note"],
        tags=_tags(row["tags_json"], release_id=row["release_id"]),
        scheduled_slot=row["scheduled_slot"],
        status=ReleaseStatus(row["status"]),
        staged_at=row["staged_at"],
        approved_at=row["approved_at"],
        approved_by=row["approved_by"],
        posted_at=row["posted_at"],
        posted_by=row["posted_by"],
        withdrawn_at=row["withdrawn_at"],
        withdrawn_by=row["withdrawn_by"],
        withdrawn_reason=row["withdrawn_reason"],
    )


class SqliteReleaseRepository:
    """Persistence capability for the operator-gated release queue."""

    def __init__(self, connection: sqlite3.Connection, transaction: TransactionFactory) -> None:
        self._connection = connection
        self._transaction = transaction

    def _live(
        self, connection: sqlite3.Connection, book_id: str, branch_id: str, chapter_number: int
    ) -> ReleaseEntry | None:
        row = connection.execute(
            f"SELECT {_COLUMNS} FROM release_queue WHERE book_id = ? AND branch_id = ? "
            f"AND chapter_number = ? AND status IN {_LIVE}",
            (book_id, branch_id, chapter_number),
        ).fetchone()
        return _entry_from_row(row) if row is not None else None

    def stage_release(self, entry: ReleaseEntry) -> bool:
        """Put a staged entry on the queue. `False` when this exact copy is already staged.

        One live entry per chapter: a chapter with a staged, approved or posted entry refuses
        a second one by name, so the operator withdraws the old copy before a re-drafted
        chapter can be staged. The refusal is made here rather than left to the partial unique
        index so it names the entry in the way; the index is the backstop.
        """
        if entry.status is not ReleaseStatus.STAGED:
            raise IllegalRelease("only a staged entry enters the queue")
        with self._transaction() as connection:
            live = self._live(connection, entry.book_id, entry.branch_id, entry.chapter_number)
            if live is not None and live.release_id != entry.release_id:
                raise IllegalRelease(
                    f"chapter {entry.chapter_number} already has a live entry "
                    f"{live.release_id} ({live.status.value}) at fragment "
                    f"{live.fragment_sha256[:12]}; withdraw it before staging another copy"
                )
            cursor = connection.execute(
                f"INSERT OR IGNORE INTO release_queue ({_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.release_id,
                    entry.book_id,
                    entry.branch_id,
                    entry.revision_id,
                    entry.chapter_number,
                    entry.chapter_stem,
                    entry.title,
                    entry.fragment_sha256,
                    entry.plain_sha256,
                    entry.author_note,
                    json.dumps(list(entry.tags)),
                    entry.scheduled_slot,
                    entry.status.value,
                    entry.staged_at,
                    entry.approved_at,
                    entry.approved_by,
                    entry.posted_at,
                    entry.posted_by,
                    entry.withdrawn_at,
                    entry.withdrawn_by,
                    entry.withdrawn_reason,
                ),
            )
            return cursor.rowcount > 0

    def release_entry(self, release_id: str) -> ReleaseEntry | None:
        row = self._connection.execute(
            f"SELECT {_COLUMNS} FROM release_queue WHERE release_id = ?", (release_id,)
        ).fetchone()
        return _entry_from_row(row) if row is not None else None

    def release_entries(
        self, book_id: str, branch_id: str, *, status: ReleaseStatus | None = None
    ) -> list[ReleaseEntry]:
        """The queue for one book, in chapter order and then staging order."""
        clauses = ["book_id = ?", "branch_id = ?"]
        params: list[Any] = [book_id, branch_id]
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        rows = self._connection.execute(
            f"SELECT {_COLUMNS} FROM release_queue WHERE {' AND '.join(clauses)} "
            "ORDER BY chapter_number, staged_at, release_id",
            params,
        )
        return [_entry_from_row(row) for row in rows]

    def live_release(
        self, book_id: str, branch_id: str, chapter_number: int
    ) -> ReleaseEntry | None:
        return self._live(self._connection, book_id, branch_id, chapter_number)

    def move_release(
        self,
        release_id: str,
        to: ReleaseStatus,
        *,
        at: str,
        by: str,
        reason: str | None = None,
    ) -> ReleaseEntry:
        """Move one entry under an operator's name, through `domain/release.transition`."""
        with self._transaction() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM release_queue WHERE release_id = ?", (release_id,)
            ).fetchone()
            if row is None:
                raise IllegalRelease(f"no release entry {release_id}")
            moved = transition(_entry_from_row(row), to, at=at, by=by, reason=reason)
            connection.execute(
                "UPDATE release_queue SET status = ?, approved_at = ?, approved_by = ?, "
                "posted_at = ?, posted_by = ?, withdrawn_at = ?, withdrawn_by = ?, "
                "withdrawn_reason = ? WHERE release_id = ?",
                (
                    moved.status.value,
                    moved.approved_at,
                    moved.approved_by,
                    moved.posted_at,
                    moved.posted_by,
                    moved.withdrawn_at,
                    moved.withdrawn_by,
                    moved.withdrawn_reason,
                    release_id,
                ),
            )
            return moved


__all__ = ["SqliteReleaseRepository"]
