"""The CLI half of the agent surface (stage-0 §241).

What an outside agent meets before any server exists: the opens that never create or migrate
a store, the verbs that gained `--json`, the ones whose JSON moved into `application/views.py`
byte for byte, `world check`'s exit, and `world declare-batch`. These drive `main(argv)` the
way `test_cli.py` does, because the command line is the interface under test; the store opens
are here rather than in `test_store.py` because they exist for this surface and its reasons.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import (
    MigrationsPending,
    SqliteStore,
    migrations_dir,
    pending_migrations,
)
from litharness.application import dossier as dossier_mod
from litharness.application import operations as operations_mod
from litharness.application import status as status_mod
from litharness.application import views as views_mod
from litharness.application import world as world_mod
from litharness.application import world_agent
from litharness.cli import EXIT_ATTENTION, EXIT_FAULT, EXIT_OK, build_parser, main
from litharness.domain.serials import SerialShape


def run(db: Path, *args: str) -> int:
    return main(["--database", str(db), *args])


@pytest.fixture
def db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    path = tmp_path / "surface.db"
    assert run(path, "init") == EXIT_OK
    assert run(path, "import", "--fixture", "litrpg") == EXIT_OK
    capsys.readouterr()
    return path


def _json_out(capsys: pytest.CaptureFixture[str]) -> object:
    out = capsys.readouterr().out
    return json.loads(out)


# --- the opens that never create or migrate ------------------------------------------


@pytest.mark.parametrize("view", world_mod.WORLD_VIEWS)
def test_cli_world_read_views_refuse_missing_stores_without_creating_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], view: str
) -> None:
    path = tmp_path / "missing.db"
    assert run(path, "world", view) == EXIT_FAULT
    assert "does not exist" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_cli_world_read_preserves_journal_mode_and_refuses_pending_migrations(
    db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A read through writable startup used to switch this file to WAL mode.
    with sqlite3.connect(db) as connection:
        assert connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    connection.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert run(db, "world", "threads") == EXIT_OK
    capsys.readouterr()
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert not Path(str(db) + "-wal").exists()

    lagging = _lagging_copy(db, tmp_path)
    before = hashlib.sha256(lagging.read_bytes()).hexdigest()
    assert run(lagging, "world", "threads") == EXIT_FAULT
    assert "migration(s) pending" in capsys.readouterr().err
    assert hashlib.sha256(lagging.read_bytes()).hexdigest() == before


def test_a_read_only_open_refuses_an_absent_path_and_creates_no_file(tmp_path: Path) -> None:
    """`SqliteStore.open` on a mistyped path minted a 700 KB store and reported an idle
    system at exit 0. The agent-facing open refuses, and leaves the directory as it was."""
    before = sorted(tmp_path.iterdir())
    with pytest.raises(FileNotFoundError, match="does not exist"):
        SqliteStore.open_read_only(tmp_path / "nope.db")
    with pytest.raises(FileNotFoundError, match="does not exist"):
        SqliteStore.open_existing(tmp_path / "nope.db")
    assert sorted(tmp_path.iterdir()) == before


def test_a_read_only_open_refuses_a_write(db: Path) -> None:
    """The containment is SQLite's `mode=ro`, not a promise: a `BEGIN IMMEDIATE` on that
    connection is accepted (WAL lets a reader take one) and the write itself is refused, so
    the test pins the write. The file's bytes are unchanged afterwards."""
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    with SqliteStore.open_read_only(db) as store:
        assert store.branches()
        with (
            pytest.raises(sqlite3.OperationalError, match="readonly"),
            store.transaction() as connection,
        ):
            connection.execute("INSERT INTO schema_migrations (name) VALUES ('zzz_probe.sql')")
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_a_read_only_open_answers_while_another_connection_holds_begin_immediate(
    db: Path,
) -> None:
    """A reader beside a ticking session: WAL readers do not wait on the writer's lock."""
    holder = sqlite3.connect(str(db), isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        started = time.monotonic()
        with SqliteStore.open_read_only(db) as store:
            assert len(store.branches()) == 1
        assert time.monotonic() - started < 1.0
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def _lagging_copy(db: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "lagging.db"
    shutil.copy(db, copy)
    connection = sqlite3.connect(str(copy))
    connection.execute(
        "DELETE FROM schema_migrations WHERE name = (SELECT max(name) FROM schema_migrations)"
    )
    connection.commit()
    connection.close()
    return copy


def test_a_read_only_open_refuses_a_store_with_pending_migrations(
    db: Path, tmp_path: Path
) -> None:
    """A store the migration set has moved past is refused by name and count, with the verb
    that applies them; `allow_pending` is how a status view still says how far it lags. (The
    lag is faked by deleting the last bookkeeping row, so `SqliteStore.open` would re-run a
    migration whose tables exist; that open is the operator's and is not exercised here.)"""
    copy = _lagging_copy(db, tmp_path)
    with pytest.raises(MigrationsPending, match=r"1 migration\(s\) pending.*status"):
        SqliteStore.open_read_only(copy)
    with SqliteStore.open_read_only(copy, allow_pending=True) as store:
        assert len(pending_migrations(store._connection, migrations_dir())) == 1
    with SqliteStore.open_read_only(db) as current:
        assert pending_migrations(current._connection, migrations_dir()) == []


def test_open_existing_never_migrates(db: Path, tmp_path: Path) -> None:
    copy = _lagging_copy(db, tmp_path)
    connection = sqlite3.connect(str(copy))
    before = connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    connection.close()
    with pytest.raises(MigrationsPending):
        SqliteStore.open_existing(copy)
    connection = sqlite3.connect(str(copy))
    assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == before
    connection.close()
    with SqliteStore.open_existing(db) as store:
        assert store.branches()


# --- the dossier, one source -----------------------------------------------------------


def test_the_dossier_keys_constant_is_the_dict_scene_dossier_builds(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(db, "why", "--scene", "1", "--json") == EXIT_ATTENTION
    dossier = _json_out(capsys)
    assert tuple(dossier) == dossier_mod.DOSSIER_KEYS


# --- the verbs that gained --json, and the ones whose JSON moved -----------------------


def test_state_json_rows_are_the_lines_the_text_view_prints(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(db, "state") == EXIT_OK
    text = capsys.readouterr().out
    assert run(db, "state", "--json") == EXIT_OK
    view = _json_out(capsys)
    assert isinstance(view, dict)
    assert set(view) == {"book_id", "branch_id", "records", "read_from_own_prose", "unplaced"}
    assert view["records"], "the litrpg fixture imports state"
    for row in view["records"]:
        assert set(row) == set(views_mod.StateRow.__annotations__)
        assert row["says"] in text
        assert row["provenance"] in {"read", "given"}
    assert f"({len(view['records'])} record(s), {view['read_from_own_prose']} read" in text


def test_jobs_json_always_carries_counts_even_on_an_empty_queue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The text form printed nothing at all on an empty queue, which is what a failed call
    prints too; the JSON form always carries a counts object."""
    path = tmp_path / "empty.db"
    assert run(path, "init") == EXIT_OK
    capsys.readouterr()
    assert run(path, "jobs") == EXIT_OK
    assert capsys.readouterr().out == ""
    assert run(path, "jobs", "--json") == EXIT_OK
    view = _json_out(capsys)
    assert view == {"counts": {}, "status": None, "jobs": []}
    assert run(path, "jobs", "--status", "parked", "--json") == EXIT_OK
    assert _json_out(capsys)["status"] == "parked"


def test_exceptions_and_directives_and_verify_print_json_when_asked(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(db, "exceptions", "--json") == EXIT_OK
    assert _json_out(capsys) == {"exceptions": [], "open": 0}
    assert run(db, "directive", "No combat in the midpoint.", "--kind", "constraint") == EXIT_OK
    capsys.readouterr()
    assert run(db, "directives", "--json") == EXIT_OK
    directives = _json_out(capsys)
    assert directives["status"] == "received"
    assert directives["machine_written"] == 0
    assert [row["body"] for row in directives["directives"]] == ["No combat in the midpoint."]
    assert directives["directives"][0]["author"] == "human"
    assert run(db, "verify", "--json") == EXIT_OK
    verify = _json_out(capsys)
    assert verify["rebuilt"] >= 1 and verify["unattributed"] == []


def test_characters_json_on_an_empty_cast_is_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`characters --json` printed two lines of prose on an empty cast. It is an object in
    both cases now, and the hint names the paid step for what it is."""
    path = tmp_path / "mystery.db"
    assert run(path, "init") == EXIT_OK
    assert run(path, "import", "--fixture", "mystery") == EXIT_OK
    capsys.readouterr()
    assert run(path, "characters", "--json") == EXIT_OK
    view = _json_out(capsys)
    assert view["characters"] == []
    assert view["hint"] == views_mod.NO_CAST_HINT
    assert "paid" in view["hint"]


def test_a_since_that_parses_as_nothing_is_refused_not_emptied(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--since notanumber` compared as a string against every stamp and matched nothing at
    exit 0, which read as "nothing happened". It is a refusal at exit 2 now."""
    assert run(db, "events", "--since", "notanumber") == EXIT_FAULT
    assert "BadSince" in capsys.readouterr().err
    assert run(db, "events", "--since", "2026-01-01", "--json") == EXIT_OK
    assert _json_out(capsys)["matched"] >= 1
    assert run(db, "events", "--since", "0", "--limit", "2", "--json") == EXIT_OK
    view = _json_out(capsys)
    assert view["shown"] == 2 and view["next_since"] == view["events"][-1]["sequence"]


def test_findings_events_and_plans_json_are_byte_identical_after_the_lift(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The three verbs whose JSON moved into `views.py` print the view dict and nothing
    else: the same `json.dumps(..., indent=2)` the CLI always printed."""
    with SqliteStore.open_read_only(db) as store:
        book_id, branch_id, _ = store.branches()[0]
        findings = views_mod.findings_view(
            store, book_id, branch_id, logical_id=None, open_only=True
        )
        events = views_mod.events_view(store, since=None, types=(), book_id=None, limit=50)
        plans = views_mod.plans_view(store, book_id, branch_id)
    assert run(db, "findings", "--json") == EXIT_OK
    assert capsys.readouterr().out == json.dumps(findings, indent=2) + "\n"
    assert run(db, "events", "--json") == EXIT_OK
    assert capsys.readouterr().out == json.dumps(events, indent=2) + "\n"
    assert run(db, "plans", "--json") == EXIT_OK
    assert capsys.readouterr().out == json.dumps(plans, indent=2) + "\n"


def test_the_status_reports_default_shape_is_the_parsers_default() -> None:
    """`status.report` assumes a serial shape when its caller states none; it must be the
    one `--chapter-scenes`/`--arc-chapters` default to, or the server's status names a
    different blocked book from the CLI's."""
    parser = build_parser()
    assert SerialShape(
        parser.get_default("chapter_scenes"), parser.get_default("arc_chapters")
    ) == status_mod.DEFAULT_SERIAL_SHAPE


def test_status_json_is_the_report_the_application_builds(
    db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(db, "status", "--json") == EXIT_OK
    printed = _json_out(capsys)
    with SqliteStore.open_read_only(db) as store:
        report = status_mod.report(store, time.time(), continuity_evaluator=False)
    built = report.as_dict()
    assert isinstance(printed, dict)
    printed.pop("now", None)
    built.pop("now", None)
    assert printed == built


# --- world check, and the batch verb ---------------------------------------------------


def _seeded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    path = tmp_path / "world.db"
    assert run(path, "init") == EXIT_OK
    assert (
        run(path, "new", "The Probe", "--premise", "A person climbs.", "--scenes", "6")
        == EXIT_OK
    )
    capsys.readouterr()
    return path


def test_world_check_exits_one_as_its_help_says(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The help said `exits 1 when anything is` and the code exited 2, so the Architect's
    tool harness showed an error banner over a valid verdict."""
    path = _seeded(tmp_path, capsys)
    assert run(path, "world", "declare", "sera", "asks", "--value", "who?") == EXIT_OK
    capsys.readouterr()
    code = run(path, "world", "check")
    check = _json_out(capsys)
    assert check["ok"] is False
    assert code == EXIT_ATTENTION
    top = next(
        action
        for action in build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    world_sub = next(
        action
        for action in top.choices["world"]._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    helps = {choice.dest: choice.help for choice in world_sub._choices_actions}
    assert "exits 1" in (helps["check"] or "")


def test_declare_batch_writes_the_good_records_and_names_the_refused_ones_by_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _seeded(tmp_path, capsys)
    records = json.dumps(
        [
            {"subject": "sera", "predicate": "is_a", "value": "Person"},
            {"subject": "sera", "predicate": "entity_role", "value": "cast", "order-key": "0100"},
            {"subject": "the-hollow", "predicate": "is_a", "value": "Place"},
        ]
    )
    code = run(path, "world", "declare-batch", "--records", records, "--json")
    batch = _json_out(capsys)
    assert code == EXIT_ATTENTION, "one refused record is a result to read"
    assert (batch["declared"], batch["refused"], batch["not_attempted"]) == (2, 1, 0)
    assert batch["results"][1]["index"] == 1
    assert "order-key" in batch["results"][1]["refused"]
    assert batch["results"][0]["authority"] == "proposed"
    assert batch["results"][2]["says"]
    assert run(path, "world", "show", "--subject", "the_hollow") == EXIT_OK
    assert _json_out(capsys)


def test_declare_batch_returns_the_check_in_the_same_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _seeded(tmp_path, capsys)
    records = json.dumps([{"subject": "sera", "predicate": "asks", "value": "who is she?"}])
    assert run(path, "world", "declare-batch", "--records", records, "--json") == EXIT_OK
    batch = _json_out(capsys)
    assert batch["check"]["ok"] is False
    assert any("asks" in complaint for complaint in batch["check"]["complaints"])
    assert run(path, "world", "declare-batch", "--records", "{}") == EXIT_FAULT
    assert "JSON array" in capsys.readouterr().err
    assert run(path, "world", "declare-batch", "--records", "not json") == EXIT_FAULT


def test_a_same_slot_redeclare_reports_what_it_supersedes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`world accept` leaves an earlier proposal in the same slot behind (§139); `declare`
    now says so at declare time, where the agent can still read it."""
    path = _seeded(tmp_path, capsys)
    assert run(path, "world", "declare", "sera", "is_a", "--value", "Person", "--json") == EXIT_OK
    first = _json_out(capsys)
    assert first["supersedes"] == []
    assert run(path, "world", "declare", "sera", "is_a", "--value", "Climber", "--json") == EXIT_OK
    second = _json_out(capsys)
    assert second["supersedes"] == [first["record_id"]]
    assert run(path, "world", "declare", "sera", "is_a", "--value", "Climber") == EXIT_OK
    assert "already on record" in capsys.readouterr().out


def test_world_declare_through_operations_mints_proposed_only(tmp_path: Path) -> None:
    path = tmp_path / "ops.db"
    assert run(path, "init") == EXIT_OK
    assert (
        run(path, "new", "The Probe", "--premise", "A person climbs.", "--scenes", "6")
        == EXIT_OK
    )
    with SqliteStore.open_existing(path) as store:
        book_id, branch_id, _ = store.branches()[0]
        result = operations_mod.declare_world_record(
            store,
            book_id,
            branch_id,
            operations_mod.WorldDeclaration("Sera", "is_a", value="Person"),
            stamp="2026-09-07T00:00:00Z",
            actor="tests",
            project_id="00000000-0000-5000-8000-000000000000",
        )
        assert result["authority"] == "proposed" and result["new"] is True
        records = store.state_records(book_id, branch_id, subject="sera")
        assert [record.authority.value for record in records] == ["proposed"]
        again = operations_mod.declare_world_record(
            store,
            book_id,
            branch_id,
            operations_mod.WorldDeclaration("Sera", "is_a", value="Person"),
            stamp="2026-09-07T00:00:01Z",
            actor="tests",
            project_id="00000000-0000-5000-8000-000000000000",
        )
        assert again["new"] is False


def test_a_declare_writes_an_event_carrying_its_actor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A proposal a server wrote and one the Architect wrote were the same row. The event
    beside it now says who, through what."""
    path = _seeded(tmp_path, capsys)
    assert (
        main(
            [
                *("--database", str(path), "--holder", "probe"),
                *("world", "declare", "sera", "is_a", "--value", "Person"),
            ]
        )
        == EXIT_OK
    )
    with SqliteStore.open_read_only(path) as store:
        rows = [
            item.event
            for item in store.read_log()
            if item.event.payload.get("via") == operations_mod.VIA_CLI
        ]
    assert [row.actor for row in rows] == ["probe"]
    assert rows[0].payload["subject"] == "sera" and rows[0].payload["authority"] == "proposed"


def test_the_declare_batch_verb_is_in_the_architects_allowance() -> None:
    assert "Bash(litharness world declare-batch:*)" in world_agent.ALLOWED_TOOLS
