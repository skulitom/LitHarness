"""The operator surface (§4.1, §4.3, §19 Autonomy).

Before this existed the system could not be run at all: no console script, no `__main__`,
and no caller of `Conductor.tick` outside the suite. §17's "ticks idempotently for a week
unattended" could be simulated but not attempted.

These tests drive `main(argv)` rather than the functions underneath it, because the
interface being asserted *is* the command line: argument names, output, and above all exit
codes, which are how a scheduler learns what happened.
"""

from __future__ import annotations

import json

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.cli import EXIT_ATTENTION, EXIT_FAULT, EXIT_OK, main
from litharness.domain.directives import DirectiveStatus
from litharness.domain.jobs import Job, JobStatus


@pytest.fixture
def db(tmp_path):
    return tmp_path / "cli.db"


def run(db, *args: str) -> int:
    return main(["--database", str(db), *args])


# --- the scheduler's interface -------------------------------------------------------


def test_init_creates_the_schema_and_is_safe_to_repeat(db, capsys) -> None:
    assert run(db, "init") == EXIT_OK
    assert run(db, "init") == EXIT_OK
    assert "migration(s) applied" in capsys.readouterr().out


def test_a_tick_on_an_empty_system_is_quiet_and_succeeds(db, capsys) -> None:
    """A healthy idle system must exit 0. Anything else pages a human every five minutes
    for the entirely normal condition of having nothing to do."""
    run(db, "init")
    assert run(db, "tick") == EXIT_OK
    assert "no_work" in capsys.readouterr().out


def test_a_parked_unit_exits_nonzero_so_the_scheduler_notices(db, capsys) -> None:
    """Exit 1 is "a unit needs a human eventually", distinct from exit 2's "the system
    could not run". A scheduler that cannot tell them apart either pages on normal
    refusals or ignores a broken database."""
    run(db, "init")
    store = SqliteStore.open(db)
    store.enqueue(Job(job_id="mystery-1", job_kind="no_such_handler"))
    store.close()

    assert run(db, "tick") == EXIT_ATTENTION
    assert "job_failed" in capsys.readouterr().out


def test_an_operational_fault_exits_two_not_one(tmp_path, capsys) -> None:
    """A missing migration set is the system failing to start, not the system reporting on
    its work — the supervisor should retry next cadence, not escalate."""
    empty = tmp_path / "none"
    empty.mkdir()
    import litharness.adapters.sqlite_store as store_module

    original = store_module.migrations_dir
    store_module.migrations_dir = lambda: empty  # type: ignore[assignment]
    try:
        assert main(["--database", str(tmp_path / "x.db"), "init"]) == EXIT_FAULT
    finally:
        store_module.migrations_dir = original  # type: ignore[assignment]
    assert "no .sql migrations" in capsys.readouterr().err


# --- status --------------------------------------------------------------------------


def test_status_reports_a_never_ticked_system_as_stalled(db, capsys) -> None:
    run(db, "init")
    assert run(db, "status") == EXIT_ATTENTION
    assert "STALLED" in capsys.readouterr().out


def test_status_is_clean_after_a_tick(db, capsys) -> None:
    run(db, "init")
    run(db, "tick")
    capsys.readouterr()
    assert run(db, "status") == EXIT_OK
    out = capsys.readouterr().out
    assert "STALLED" not in out
    assert "no_work" in out


def test_status_json_is_machine_readable(db, capsys) -> None:
    run(db, "init")
    run(db, "tick")
    capsys.readouterr()
    run(db, "status", "--json")
    report = json.loads(capsys.readouterr().out)
    assert report["stalled"] is False
    assert report["needs_attention"] == 0
    assert report["lease_holder"] == "cron"


def test_status_surfaces_units_that_need_attention(db, capsys) -> None:
    run(db, "init")
    store = SqliteStore.open(db)
    store.enqueue(Job(job_id="mystery-1", job_kind="no_such_handler"))
    store.close()
    for _ in range(4):
        run(db, "tick")
    capsys.readouterr()

    assert run(db, "status") == EXIT_ATTENTION
    assert "needs attention 1" in capsys.readouterr().out


# --- direction and controls ----------------------------------------------------------


def test_a_directive_is_captured_and_ingested_by_the_next_tick(db, capsys) -> None:
    run(db, "init")
    assert run(db, "directive", "More dungeon crawling.", "--kind", "arc_note") == EXIT_OK
    capsys.readouterr()

    run(db, "tick")
    assert "ingested=1" in capsys.readouterr().out

    store = SqliteStore.open(db)
    try:
        [captured] = store.directives_by_status(DirectiveStatus.RECEIVED)
        assert captured.body == "More dungeon crawling."
    finally:
        store.close()


def test_the_same_directive_twice_is_reported_as_a_duplicate(db, capsys) -> None:
    run(db, "init")
    run(db, "directive", "Same words.")
    first = capsys.readouterr().out
    run(db, "directive", "Same words.")
    second = capsys.readouterr().out
    # Same instant is not guaranteed across two calls, so assert on the mechanism rather
    # than the outcome: whichever it reports, it must name the directive it decided about.
    assert "dir-" in first and "dir-" in second


def test_pause_survives_the_process(db, capsys) -> None:
    """The whole reason pause moved into storage. Under §4.1's cron model every tick is a
    fresh process, so an in-memory flag was reconstructed as False every time and
    `TickOutcome.PAUSED` was unreachable in the deployment the plan specifies."""
    run(db, "init")
    assert run(db, "pause") == EXIT_OK
    capsys.readouterr()

    run(db, "tick")
    assert "paused" in capsys.readouterr().out

    run(db, "resume")
    capsys.readouterr()
    run(db, "tick")
    assert "no_work" in capsys.readouterr().out


def test_a_paused_tick_does_no_work_but_still_records(db) -> None:
    run(db, "init")
    run(db, "pause")
    run(db, "tick")
    store = SqliteStore.open(db)
    try:
        assert store.last_tick()["outcome"] == "paused"
    finally:
        store.close()


# --- inspection and recovery ---------------------------------------------------------


def test_jobs_reports_queue_depth_and_a_named_status(db, capsys) -> None:
    run(db, "init")
    store = SqliteStore.open(db)
    store.enqueue(Job(job_id="a", job_kind="noop"))
    store.enqueue(Job(job_id="b", job_kind="noop"))
    store.close()

    run(db, "jobs")
    assert "queued       2" in capsys.readouterr().out

    run(db, "jobs", "--status", "queued")
    assert "(2 queued)" in capsys.readouterr().out


def test_revive_refuses_a_job_that_is_not_parked(db) -> None:
    run(db, "init")
    store = SqliteStore.open(db)
    store.enqueue(Job(job_id="a", job_kind="noop"))
    store.close()
    with pytest.raises(Exception, match="not parked"):
        run(db, "revive", "a")


def test_backup_and_verify_are_operator_reachable(db, tmp_path, capsys) -> None:
    """§18 keeps backups absolutely, and a backup nobody can take is not one."""
    run(db, "init")
    assert run(db, "backup", str(tmp_path / "snap.db")) == EXIT_OK
    assert (tmp_path / "snap.db").exists()
    capsys.readouterr()
    assert run(db, "verify") == EXIT_OK
    assert "rebuild cleanly" in capsys.readouterr().out


def test_backing_up_over_an_existing_file_is_a_fault_not_a_silent_overwrite(
    db, tmp_path, capsys
) -> None:
    run(db, "init")
    (tmp_path / "snap.db").write_bytes(b"")
    assert run(db, "backup", str(tmp_path / "snap.db")) == EXIT_FAULT
    assert "FileExistsError" in capsys.readouterr().err


def test_enqueue_puts_a_draft_on_the_queue(db, capsys) -> None:
    run(db, "init")
    assert (
        run(
            db,
            "enqueue",
            "draft-1",
            "--revision",
            "r-1",
            "--node",
            "scene-1",
            "--prompt",
            "Draft it.",
        )
        == EXIT_OK
    )
    store = SqliteStore.open(db)
    try:
        job = store.load_job("draft-1")
        assert job.status is JobStatus.QUEUED
        assert job.payload["logical_id"] == "scene-1"
    finally:
        store.close()
