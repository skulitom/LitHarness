"""Exemplar passages: the thing a writer's `exemplar_digest` has always pointed at and never had.

**Its own capability repository rather than four methods on `sqlite_roster.py`.** `CONTRIBUTING.md`
puts cohesive persistence behaviour in one of these and gives the facade a thin delegate, and the
line between the two repositories is a real one: the roster is a status machine with a
decision-row invariant, and this is a content-addressed store with no status at all. A writer is
admitted or refused; a passage simply exists or does not. Putting them together would put two
different invariants behind one name, and `sqlite_roster.py`'s own docstring gives that argument
for not living on the facade.

**The one rail this module holds** is that a stored passage always addresses itself.
`record_exemplar` recomputes the digest from the passage and refuses a mismatch, rather than
trusting the caller's. That is not paranoia about callers: the digest is *addressed material in a
writer id*, so a row whose passage and digest disagree makes "which passage minted this writer"
answerable two ways, which is the failure the content address exists to prevent.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from litharness.adapters.sqlite_errors import IntegrityFailure
from litharness.adapters.sqlite_jobs import TransactionFactory
from litharness.domain import voice as voice_domain

_COLUMNS = (
    "exemplar_digest, passage, drawn_by, descriptor_id, descriptor_json, profile, drawn_at"
)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["descriptor_json"])
    if not isinstance(payload, dict):
        raise IntegrityFailure(
            f"exemplar {row['exemplar_digest']} has a malformed descriptor_json"
        )
    return {
        "exemplar_digest": row["exemplar_digest"],
        "passage": row["passage"],
        "drawn_by": row["drawn_by"],
        "descriptor_id": row["descriptor_id"],
        "descriptor": payload,
        "profile": row["profile"],
        "drawn_at": row["drawn_at"],
    }


class SqliteVoiceRepository:
    """Persistence capability for drawn exemplar passages."""

    def __init__(
        self, connection: sqlite3.Connection, transaction: TransactionFactory
    ) -> None:
        self._connection = connection
        self._transaction = transaction

    def record_exemplar(
        self,
        *,
        passage: str,
        drawn_by: str,
        descriptor: voice_domain.StyleDescriptor,
        profile: str,
        drawn_at: str,
    ) -> str:
        """Keep one drawn passage and return its digest. Idempotent on the content address.

        **The digest is computed here and is not a parameter**, which is the same move
        `writers.build` makes for a writer id: a value derived from the material cannot be
        supplied by a caller who derived it differently, and this one goes on to be addressed
        material in a writer id. `INSERT OR IGNORE` rather than a replace, so a second draw that
        happened to return byte-identical prose converges on the first row and does not silently
        rewrite the descriptor that aimed it.

        **`descriptor` is a `StyleDescriptor` rather than a mapping**, so the numbers stored are
        numbers the domain has already refused a NaN, a negative and an out-of-order quantile
        for. A dict parameter would let a row exist that `StyleDescriptor` could never be rebuilt
        from, which is `roster_rows`' documented problem arriving in a table with no operator
        surface to notice it.
        """
        digest = voice_domain.exemplar_digest_for(passage)
        with self._transaction() as connection:
            connection.execute(
                f"INSERT OR IGNORE INTO voice_exemplars ({_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    digest,
                    passage,
                    drawn_by,
                    descriptor.descriptor_id,
                    json.dumps(descriptor.as_labels(), sort_keys=True),
                    profile,
                    drawn_at,
                ),
            )
        return digest

    def exemplar(self, exemplar_digest: str) -> dict[str, Any] | None:
        """One stored passage, or `None`.

        Raises `IntegrityFailure` when the stored passage no longer addresses its own key, which
        is the only way a row here can go wrong and the reason the check is on the read rather
        than only on the write: an edit made underneath the table has to be found by whoever next
        asks what minted a writer, not by whoever made it.
        """
        rows = list(
            self._connection.execute(
                f"SELECT {_COLUMNS} FROM voice_exemplars WHERE exemplar_digest = ?",
                (exemplar_digest,),
            )
        )
        if not rows:
            return None
        record = _row_to_dict(rows[0])
        if voice_domain.exemplar_digest_for(record["passage"]) != exemplar_digest:
            raise IntegrityFailure(
                f"exemplar {exemplar_digest} does not address its own passage; something edited "
                "a stored column in place, and this digest is part of a writer id"
            )
        return record

    def exemplars_drawn_by(self, drawn_by: str) -> list[dict[str, Any]]:
        """Every passage this writer has drawn, oldest first.

        So a revoice run can see what a previous one already paid for. It is a read and never a
        pick: nothing here orders passages by anything but when they were drawn, and choosing
        among drawn passages by any other rule would be selection among candidates.
        """
        return [
            _row_to_dict(row)
            for row in self._connection.execute(
                f"SELECT {_COLUMNS} FROM voice_exemplars WHERE drawn_by = ? "
                "ORDER BY drawn_at, exemplar_digest",
                (drawn_by,),
            )
        ]


__all__ = ["SqliteVoiceRepository"]
