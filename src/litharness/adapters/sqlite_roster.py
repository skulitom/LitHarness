"""The writer roster: proposals a machine may write, and an admission only a decision carries.

**Why a capability repository rather than four methods on the facade.** `CONTRIBUTING.md` says
cohesive persistence behaviour goes in one of these and the facade gets a thin delegate.
`record_director` and its two readers are three straight row mappings with no state transition,
which is why they live on the facade; the roster is a status machine with a decision-row
invariant, and `sqlite_store.py` is long enough already.

**The one rail this module exists to hold.** `record_proposed_writer` has no parameter that
could write `accepted`, `accept_writers` is the only path that can, and it takes a
`PolicyDecision` it inserts in the same transaction. The recruiter brief's rail — *no model
hires* (stage-0 §146, standing on §61(5) and §105.1) — is therefore a shape of the code and
of the schema rather than a promise about how callers behave.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from litharness.adapters.sqlite_errors import IntegrityFailure
from litharness.adapters.sqlite_jobs import TransactionFactory
from litharness.domain import writers as writers_domain
from litharness.domain.policy import PolicyDecision
from litharness.domain.writers import IllegalDossier, RosterStatus, Writer


#: Its own Protocol rather than one imported from a sibling repository, which is the convention
#: `sqlite_plans.py` and `sqlite_audience.py` already keep: sharing the type would be the first
#: coupling between two capability repositories, and the facade is where they are meant to meet.
class DecisionInserter(Protocol):
    def __call__(
        self,
        connection: sqlite3.Connection,
        decision: PolicyDecision,
        *,
        decided_at: str,
    ) -> bool: ...


RowFilter = Callable[[sqlite3.Row], bool]

_COLUMNS = (
    "writer_id, name, dossier, interests_json, exemplar_digest, note, "
    "specialization, shape, status, proposed_at, accepted_at, refused_at, decision_id"
)


def _interests(raw: str, *, writer_id: str) -> tuple[str, ...]:
    """The stored interest list, in the order it was addressed in.

    A JSON array rather than a joined column because `writer_id_for` length-prefixes this field
    precisely so `("a", "b")` and `("a\\x1fb",)` cannot address to the same writer; a separator
    would hand that forgery back. Order is addressed material, so a decoder that returned a set
    or a sorted list would silently produce rows no `Writer` can be rebuilt from.
    """
    payload = json.loads(raw)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise IntegrityFailure(f"roster row {writer_id} has a malformed interests_json")
    return tuple(payload)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "writer_id": row["writer_id"],
        "name": row["name"],
        "dossier": row["dossier"],
        "interests": _interests(row["interests_json"], writer_id=row["writer_id"]),
        "exemplar_digest": row["exemplar_digest"],
        "note": row["note"],
        "specialization": row["specialization"],
        "shape": row["shape"],
        "status": row["status"],
        "proposed_at": row["proposed_at"],
        "accepted_at": row["accepted_at"],
        "refused_at": row["refused_at"],
        "decision_id": row["decision_id"],
    }


def _writer_from_row(row: Any) -> Writer:
    """A `Writer` from its stored columns, with the id read rather than recomputed.

    Passing the **stored** `writer_id` is what keeps `Writer.__post_init__`'s address check
    live: recomputing it here would make every row address itself by construction and the
    content address would stop being able to detect an edit made underneath it.
    """
    return Writer(
        writer_id=row["writer_id"],
        name=row["name"],
        dossier=row["dossier"],
        interests=tuple(row["interests"]),
        exemplar_digest=row["exemplar_digest"],
        note=row["note"],
    )


class SqliteRosterRepository:
    """Persistence capability for the writer roster and its one state transition."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        transaction: TransactionFactory,
        *,
        insert_decision: DecisionInserter,
    ) -> None:
        self._connection = connection
        self._transaction = transaction
        self._insert_decision = insert_decision

    def record_proposed_writer(
        self,
        writer: Writer,
        *,
        specialization: str,
        shape: str,
        proposed_at: str,
    ) -> bool:
        """Offer the roster one writer. `False` when this exact writer was already proposed.

        Idempotent on the content-addressed id, `record_director`'s semantics for
        `record_director`'s reason: re-declaring the same dossier converges, and an *edited*
        dossier is a different writer rather than a silent rewrite of the one already on record.

        **There is no parameter here that can write `accepted`**, and that is rail 4 held by the
        method's shape rather than by its caller's manners. The dossier and the interests are
        written exactly as given — no canonicalisation, no strip — because they are addressed
        material and normalising them here would store a row that no longer addresses its own id.

        No `events` parameter: no member of `EventType` describes a roster admission, and adding
        one means moving `litharness-contracts`, which is out of this task's scope. Stated so the
        next reader does not go looking for the event that should have been emitted.
        """
        writers_domain.refuse_reserved_name(writer.name)
        if shape not in writers_domain.DOSSIER_SHAPES:
            raise IllegalDossier(
                f"{shape!r} is not a dossier shape; the shapes are "
                f"{', '.join(sorted(writers_domain.DOSSIER_SHAPES))}. An unlabelled recruit "
                "drops out of the registered arm without saying so"
            )
        with self._transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO roster_writers ("
                "writer_id, name, dossier, interests_json, exemplar_digest, note, "
                "specialization, shape, status, proposed_at, accepted_at, decision_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                (
                    writer.writer_id,
                    writer.name,
                    writer.dossier,
                    json.dumps(list(writer.interests)),
                    writer.exemplar_digest,
                    writer.note,
                    specialization,
                    shape,
                    RosterStatus.PROPOSED.value,
                    proposed_at,
                ),
            )
            return cursor.rowcount > 0

    def roster_rows(
        self,
        *,
        writer_id: str | None = None,
        name: str | None = None,
        status: RosterStatus | None = None,
        specialization: str | None = None,
    ) -> list[dict[str, Any]]:
        """Raw columns, ordered by name then id so two reads of one roster agree.

        **Raw rather than validated `Writer` objects, and that is what makes the second
        legality check non-vacuous.** `Writer.__post_init__` runs `legal_dossier` first, so a
        reader that built `Writer`s would raise on exactly the row an operator needs to be shown
        — a dossier a *later*-registered prose axis made illegal — and could only ever hand
        `roster accept` rows that had already passed. `show`, `check` and `accept` have to be
        able to see such a row in order to name it.
        """
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("writer_id", writer_id),
            ("name", name),
            ("specialization", specialization),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return [
            _row_to_dict(row)
            for row in self._connection.execute(
                f"SELECT {_COLUMNS} FROM roster_writers{where} ORDER BY name, writer_id",
                params,
            )
        ]

    def accepted_writer(self, name: str) -> Writer | None:
        """The one accepted writer answering to `name`, or `None`.

        **The method's name is the rail: a proposal is not castable.** `roster accept` is a
        person's act with a decision row behind it, and a recruit that could draft merely by
        being named would make that act optional. `roster_accepted_name_idx` guarantees at most
        one row here, so this can never become a silent pick among candidates.

        It raises rather than skipping when a stored dossier is illegal, which is
        `directors()`' direction to fail in and the right one for the drafting path: a quiet
        skip would resolve to the anonymous control and the arm would report a difference
        between a writer and itself.
        """
        rows = self.roster_rows(name=name, status=RosterStatus.ACCEPTED)
        if not rows:
            return None
        return _writer_from_row(rows[0])

    def accept_writers(
        self,
        writer_ids: Sequence[str],
        *,
        decision: PolicyDecision,
        accepted_at: str,
    ) -> int:
        """Put proposed writers on the roster, as one decision. Returns how many moved.

        The decision is inserted **before** the updates because the foreign key is live: a row
        claiming `accepted` must point at a decision that already exists, which is the whole of
        why the CHECK and the FK are both in migration 035.

        Three refusals run inside the transaction, and each aborts the whole batch rather than
        leaving a partial one:

        * building each row's `Writer` runs `legal_dossier` and the address check by
          construction, which is R1's second pass;
        * `refuse_reserved_name` again, because the write-time guard cannot see the case that
          matters here — `CAST` growing later to a name a stored recruit already holds;
        * a name another accepted writer already answers to, **or a name two rows in this same
          batch share**, refused with both ids so the operator gets a sentence rather than a bare
          `sqlite3.IntegrityError`, which nothing in this package translates. The second half was
          missing and the index fired instead: two proposals under one name are legal by design —
          an edited dossier is a different writer — so a bare `roster accept` over both aborted
          on `UNIQUE constraint failed: roster_writers.name` naming neither of them.

        Nothing is ever demoted: the UPDATE moves `proposed -> accepted` and has no other
        direction, which is `promote_state_records`' rule kept here.
        """
        wanted = list(writer_ids)
        if not wanted:
            return 0
        with self._transaction() as connection:
            rows = [
                _row_to_dict(row)
                for writer_id in wanted
                for row in connection.execute(
                    f"SELECT {_COLUMNS} FROM roster_writers WHERE writer_id = ? "
                    "AND status = ?",
                    (writer_id, RosterStatus.PROPOSED.value),
                )
            ]
            taken = {
                row["name"]: row["writer_id"]
                for row in (
                    _row_to_dict(item)
                    for item in connection.execute(
                        f"SELECT {_COLUMNS} FROM roster_writers WHERE status = ?",
                        (RosterStatus.ACCEPTED.value,),
                    )
                )
            }
            for row in rows:
                _writer_from_row(row)
                writers_domain.refuse_reserved_name(row["name"])
                if row["name"] in taken:
                    raise IllegalDossier(
                        f"{row['name']!r} is already on the roster as {taken[row['name']]}; "
                        f"{row['writer_id']} cannot take the same name, because `--writer "
                        f"{row['name']}` has to have one answer. An edited dossier is a "
                        "different writer and needs a different name"
                    )
                # **Accumulated as the batch is walked, not just seeded from what is already
                # accepted.** Two proposals under one name are legal and expected; accepting
                # both is not, and without this line the partial index caught it inside the
                # UPDATE loop and reported `UNIQUE constraint failed` naming neither writer.
                taken[row["name"]] = row["writer_id"]
            self._insert_decision(connection, decision, decided_at=accepted_at)
            moved = 0
            for row in rows:
                cursor = connection.execute(
                    "UPDATE roster_writers SET status = ?, accepted_at = ?, decision_id = ? "
                    "WHERE writer_id = ? AND status = ?",
                    (
                        RosterStatus.ACCEPTED.value,
                        accepted_at,
                        decision.decision_id,
                        row["writer_id"],
                        RosterStatus.PROPOSED.value,
                    ),
                )
                moved += cursor.rowcount
            return moved

    def refuse_writers(
        self,
        writer_ids: Sequence[str],
        *,
        decision: PolicyDecision,
        refused_at: str,
    ) -> int:
        """Turn proposed writers down, as one decision. Returns how many moved.

        `accept_writers`' shape and its foreign-key ordering — the decision is inserted before
        the updates, because migration 036 makes a `refused` row without a `decision_id`
        unrepresentable exactly as 035 did for `accepted`. What differs is everything the
        acceptance path checks, and each omission is deliberate:

        * **No `Writer` is built from the row, and that is the point rather than an oversight.**
          `_writer_from_row` runs `legal_dossier`, so the acceptance path raises on a dossier a
          later-registered prose axis made illegal. That row is precisely the one an operator
          most needs to be able to refuse, and a refusal path that raised on it would leave it
          stuck as `proposed` forever with no verb that could touch it.
        * **No reserved-name check.** That guard protects the resolution namespace, and a
          refused writer never enters it.
        * **No collision check.** Refusing claims no name; `roster_accepted_name_idx` covers
          `accepted` alone, so a refusal quietly releases the name for a later proposal instead
          of competing for it.

        Nothing is demoted: the UPDATE moves `proposed -> refused` and has no other direction,
        so an accepted writer cannot be refused out of the roster by this path, and a refused
        one cannot be refused twice into a second decision row.
        """
        wanted = list(writer_ids)
        if not wanted:
            return 0
        with self._transaction() as connection:
            self._insert_decision(connection, decision, decided_at=refused_at)
            moved = 0
            for writer_id in wanted:
                cursor = connection.execute(
                    "UPDATE roster_writers SET status = ?, refused_at = ?, decision_id = ? "
                    "WHERE writer_id = ? AND status = ?",
                    (
                        RosterStatus.REFUSED.value,
                        refused_at,
                        decision.decision_id,
                        writer_id,
                        RosterStatus.PROPOSED.value,
                    ),
                )
                moved += cursor.rowcount
            return moved


__all__ = ["DecisionInserter", "SqliteRosterRepository"]
