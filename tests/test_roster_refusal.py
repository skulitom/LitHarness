"""Refusal: the operator's NO, and the four ways it has to stay quiet (stage-0 §149).

Migration 035 pinned `status` to two words and declined a third — *"with no retired status in
this migration the way through is a new name"*. 036 adds `refused` because a new name answers
"this dossier was wrong" and has never answered "this writer is not wanted". The rail is
unchanged: a `refused` row without a `decision_id` is as unrepresentable as an `accepted` one,
because a refusal is also a person.

What must stay true, and each of these fails by doing something quiet rather than by raising:

1. **A refused writer is never swept up by a bare `roster accept`**, which takes every proposal.
2. **A refused writer never resolves through `--writer`**, exactly as a proposed one does not.
3. **`roster check` never complains about one.** The row an operator most wants to turn down is
   the one with an illegal dossier, and that is also the row `legal_dossier` complains about;
   if refusal did not silence it, `check` would exit 2 forever over a settled decision.
4. **Nothing is ever deleted, and there is no un-refuse.** A changed mind is a new proposal.

`test_migration_036_rebuilds_the_table_without_touching_a_row` is the safety net under the
first table rebuild in these migrations: it builds a store at 035, fills it, and proves 036
carries every byte across.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore, migrations_dir
from litharness.application import roster as roster_mod
from litharness.cli import _resolve_writer
from litharness.domain import writers
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decision_id_for,
)

DOSSIER = (
    "You write the kind of fantasy where the stakes are a bakery, a bad harvest and "
    "somebody's estranged aunt. What you love is competence at low volume. You want a "
    "reader to close a chapter feeling like they could stay."
)


@pytest.fixture
def store(tmp_path):
    with SqliteStore.open(tmp_path / "roster.db") as opened:
        yield opened


def _propose(store: SqliteStore, name: str = "okafor", **kwargs) -> writers.Writer:
    writer = writers.build(
        name,
        kwargs.pop("dossier", DOSSIER),
        interests=kwargs.pop("interests", ("cozy fantasy", "small towns")),
    )
    store.record_proposed_writer(
        writer,
        specialization=kwargs.pop("specialization", "cozy-fantasy"),
        shape=kwargs.pop("shape", "several-no-beat"),
        proposed_at=kwargs.pop("proposed_at", "2026-08-28T00:00:00Z"),
    )
    return writer


def _decision(kind: str, writer_ids: tuple[str, ...], reason: str) -> PolicyDecision:
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id=f"roster.{kind}.v0",
        passed=True,
        blocking=False,
        detail="test",
    )
    return PolicyDecision(
        decision_id=decision_id_for(f"roster-{kind}:" + "+".join(writer_ids), 0, (gate,)),
        outcome=Outcome.PARK if kind == "refuse" else Outcome.ACCEPT,
        gates=(gate,),
        reason=reason,
    )


def _refuse(store: SqliteStore, *writer_ids: str, at: str = "2026-08-28T02:00:00Z") -> int:
    return store.refuse_writers(
        writer_ids,
        decision=_decision("refuse", writer_ids, "a person turned these writers down: no"),
        refused_at=at,
    )


def _accept(store: SqliteStore, *writer_ids: str, at: str = "2026-08-28T01:00:00Z") -> int:
    return store.accept_writers(
        writer_ids,
        decision=_decision("accept", writer_ids, "a person put these writers on the roster"),
        accepted_at=at,
    )


# ------------------------------------------------------------------ the transition


def test_refusing_moves_the_row_and_points_it_at_the_decision_that_carried_it(store) -> None:
    writer = _propose(store)

    assert _refuse(store, writer.writer_id) == 1

    row = store.roster_rows(writer_id=writer.writer_id)[0]
    assert row["status"] == writers.RosterStatus.REFUSED.value
    assert row["refused_at"] == "2026-08-28T02:00:00Z"
    assert row["accepted_at"] is None
    assert row["decision_id"] is not None


def test_a_refused_row_cannot_exist_without_a_decision_to_point_at(store) -> None:
    """036's CHECK, doing for refusal what 035's did for admission."""
    writer = _propose(store)

    with pytest.raises(sqlite3.IntegrityError), store.transaction() as connection:
        connection.execute(
            "UPDATE roster_writers SET status = 'refused', refused_at = ? "
            "WHERE writer_id = ?",
            ("2026-08-28T02:00:00Z", writer.writer_id),
        )


def test_a_bare_accept_never_sweeps_up_a_refused_writer(store) -> None:
    """The whole point of the status: `roster accept` with no names takes every proposal."""
    kept = _propose(store, "kept")
    turned_down = _propose(store, "turned")
    _refuse(store, turned_down.writer_id)

    proposed = store.roster_rows(status=writers.RosterStatus.PROPOSED)
    assert [row["writer_id"] for row in proposed] == [kept.writer_id]

    assert _accept(store, *(row["writer_id"] for row in proposed)) == 1
    assert store.roster_rows(writer_id=turned_down.writer_id)[0]["status"] == "refused"


def test_a_refused_writer_cannot_be_accepted_even_when_named(store) -> None:
    """`accept_writers` moves `proposed -> accepted` and has no other direction."""
    writer = _propose(store)
    _refuse(store, writer.writer_id)

    assert _accept(store, writer.writer_id) == 0
    assert store.roster_rows(writer_id=writer.writer_id)[0]["status"] == "refused"


def test_refusing_the_same_writer_twice_moves_nothing_and_mints_no_second_row(store) -> None:
    """There is no un-refuse, and there is no re-refuse either: the transition is one-way."""
    writer = _propose(store)
    _refuse(store, writer.writer_id)

    assert _refuse(store, writer.writer_id, at="2026-08-29T00:00:00Z") == 0
    row = store.roster_rows(writer_id=writer.writer_id)[0]
    assert row["refused_at"] == "2026-08-28T02:00:00Z"


def test_an_illegal_dossier_can_still_be_refused(store) -> None:
    """The row an operator most wants to turn down is the one `accept` raises on.

    `accept_writers` builds a `Writer` from each row, which runs `legal_dossier`; a refusal
    path that did the same would raise on exactly the dossier a later-registered prose axis
    made illegal, leaving it stuck as `proposed` with no verb able to touch it.
    """
    writer = _propose(store)
    with store.transaction() as connection:
        connection.execute(
            "UPDATE roster_writers SET dossier = ? WHERE writer_id = ?",
            ("this dossier asserts that its prose is beautiful.", writer.writer_id),
        )

    assert _refuse(store, writer.writer_id) == 1
    assert store.roster_rows(writer_id=writer.writer_id)[0]["status"] == "refused"


# ------------------------------------------------------------------ staying quiet


def test_a_refused_writer_does_not_resolve_and_says_why(store) -> None:
    writer = _propose(store)
    _refuse(store, writer.writer_id)

    resolved, message = _resolve_writer("okafor", store)

    assert resolved is None
    assert "refused" in message
    # It must NOT send the operator to `roster accept`, which can no longer touch this row.
    assert "roster accept" not in message
    assert "declare" in message


def test_roster_check_never_complains_about_a_refused_writer(store) -> None:
    writer = _propose(store)
    with store.transaction() as connection:
        connection.execute(
            "UPDATE roster_writers SET dossier = ? WHERE writer_id = ?",
            ("this dossier asserts that its prose is beautiful.", writer.writer_id),
        )

    # While it is still proposed the illegal dossier is a complaint, as it should be.
    assert not roster_mod.check(store.roster_rows())["ok"]

    _refuse(store, writer.writer_id)
    report = roster_mod.check(store.roster_rows())

    assert report["ok"]
    assert report["complaints"] == []
    assert report["refused"] == 1
    assert report["proposed"] == 0


def test_a_refusal_frees_the_name_for_a_fresh_proposal(store) -> None:
    """A changed mind is a new proposal: the unique index covers `accepted` alone."""
    first = _propose(store, "okafor")
    _refuse(store, first.writer_id)

    second = _propose(store, "okafor", interests=("cozy fantasy", "harvests"))
    assert _accept(store, second.writer_id) == 1

    resolved, message = _resolve_writer("okafor", store)
    assert message == ""
    assert resolved is not None
    assert resolved.writer_id == second.writer_id


# ------------------------------------------------------------------ the rebuild


def test_migration_036_rebuilds_the_table_without_touching_a_row(tmp_path: Path) -> None:
    """Every byte and every id survives the first table rebuild in these migrations.

    Built at 035 so the copy is real rather than simulated: the store is opened against a
    migrations directory holding everything up to 035, filled with a proposed row and an
    accepted one (which exercises the live foreign key into `policy_decisions`), then reopened
    against the full set so 036 runs over populated data.

    **The rows go in through SQL rather than through the adapter**, because the adapter is
    written against the current schema — `_COLUMNS` names `refused_at` — and cannot address a
    035 table at all. That is the right dependency: this test is about the migration, and
    reaching for the repository here would only prove the repository matches itself.
    """
    staged = tmp_path / "migrations"
    staged.mkdir()
    for path in sorted(migrations_dir().glob("*.sql")):
        if path.name < "036":
            (staged / path.name).write_bytes(path.read_bytes())

    database = tmp_path / "roster.db"
    proposed_id, accepted_id = "wtr-kept0000", "wtr-signed000"
    with SqliteStore.open(database, migrations=staged) as old:
        with old.transaction() as connection:
            connection.execute(
                "INSERT INTO policy_decisions (decision_id, outcome, reason, gates, decided_at)"
                " VALUES ('dec-036', 'accept', 'a person put this writer on the roster', "
                "'[]', '2026-08-28T01:00:00Z')"
            )
            connection.execute(
                "INSERT INTO roster_writers (writer_id, name, dossier, interests_json, "
                "note, specialization, shape, status, proposed_at) "
                "VALUES (?, 'kept', ?, '[\"cozy fantasy\"]', 'keep me', 'cozy-fantasy', "
                "'several-no-beat', 'proposed', '2026-08-28T00:00:00Z')",
                (proposed_id, DOSSIER),
            )
            connection.execute(
                "INSERT INTO roster_writers (writer_id, name, dossier, interests_json, "
                "note, specialization, shape, status, proposed_at, accepted_at, decision_id) "
                "VALUES (?, 'signed', ?, '[\"cozy fantasy\"]', '', 'cozy-fantasy', "
                "'several-no-beat', 'accepted', '2026-08-28T00:00:00Z', "
                "'2026-08-28T01:00:00Z', 'dec-036')",
                (accepted_id, DOSSIER),
            )
        before = [
            dict(row)
            for row in old._connection.execute(
                "SELECT * FROM roster_writers ORDER BY writer_id"
            )
        ]
    assert "refused_at" not in before[0]

    # Reopening against the real directory is what applies 036.
    with SqliteStore.open(database) as migrated:
        after = [
            dict(row)
            for row in migrated._connection.execute(
                "SELECT * FROM roster_writers ORDER BY writer_id"
            )
        ]

    assert len(after) == len(before) == 2
    for old_row, new_row in zip(before, after, strict=True):
        assert new_row["refused_at"] is None
        assert {k: v for k, v in new_row.items() if k != "refused_at"} == old_row

    assert {row["writer_id"] for row in after} == {proposed_id, accepted_id}

    with closing(sqlite3.connect(database)) as con:
        indexes = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' "
                "AND tbl_name = 'roster_writers' AND name NOT LIKE 'sqlite_%'"
            )
        }
        keys = list(con.execute("PRAGMA foreign_key_list(roster_writers)"))
        broken = list(con.execute("PRAGMA foreign_key_check"))

    assert indexes == {
        "roster_writers_name_idx",
        "roster_writers_status_idx",
        "roster_writers_specialization_idx",
        "roster_accepted_name_idx",
    }
    assert [key[2] for key in keys] == ["policy_decisions"]
    assert broken == []
