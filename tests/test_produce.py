"""The production runner owns restart boundaries, not model or acceptance policy."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.concept import Concept
from litharness.domain import extraction
from litharness.domain.jobs import Job
from tools import produce


@pytest.fixture
def production(monkeypatch):
    """Stub invention/world authoring; retain the real CLI, scheduler, gates and export."""
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    monkeypatch.setenv("LITHARNESS_NO_OUTLINE", "1")
    for key in ("LITHARNESS_WRITER", "LITHARNESS_DIRECTOR", "LITHARNESS_EXEMPLARS",
                "LITHARNESS_ROSTER_DATABASE", "LITHARNESS_REVISE"):
        monkeypatch.delenv(key, raising=False)
    calls = []

    def invent(args):
        calls.append("concept")
        payload = {
            "person_before": "a courier", "exception": "can cross the closed gate",
            "first_use": "crosses with medicine", "want": "to bring his brother home",
            "system": {
                "name": "Marks", "manner": "quiet", "look": "letters", "steps": 12,
                "strongest_known": "six", "pays": "access to roads",
            },
            "threat": {"what": "the flooded city", "first_reach": "the lower road"},
            "turn": {"event": "the gate closes", "when": "before chapter one"},
            "second_system": None,
            "first_arc": {"opens": "crosses", "middle": "finds brother", "closes": "returns"},
            "debts": [
                {"subject": "gate", "owed": "who closed it", "due_scene": 5},
                {"subject": "brother", "owed": "where he went", "due_scene": 6},
            ],
        }
        (args.out / "concept.json").write_text(
            Concept.from_payload(payload).to_text(), encoding="utf-8",
        )
        return cli.EXIT_OK

    def seed(args):
        calls.append("seed")
        records = [lc.StateRecord(
            record_id="starting-sheet", kind=lc.StateRecordKind.ASSERTION,
            subject="courier", predicate="status_snapshot",
            value={"level": 1, "hp": 10, "hp_max": 10, "gold": 10},
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )]
        records.append(extraction.declaration_from_snapshots(records))
        with SqliteStore.open(args.database) as store:
            store.record_state_records(args.book, args.branch, records, created_at="2026-09-26")
        return cli.EXIT_OK

    monkeypatch.setattr(cli, "cmd_concept", invent)
    monkeypatch.setattr(cli, "cmd_architect", seed)
    return calls


def start(root: Path, *extra: str) -> int:
    return produce.main([
        "start", str(root), "--brief", "A courier at a closed gate.",
        "--chapters", "1", "--chapter-scenes", "2", "--arc-chapters", "3", *extra,
    ])


def manifest(root: Path) -> dict:
    return json.loads((root / "run.json").read_text(encoding="utf-8"))


def test_resume_does_not_repeat_setup_or_draft_past_target(tmp_path, production, monkeypatch):
    root = tmp_path / "serial"
    assert start(root, "--max-ticks", "1") == cli.EXIT_ATTENTION
    saved = manifest(root)
    assert saved["ticks"] == 1
    # Resume must use the saved fake and planning settings, even in a changed shell.
    monkeypatch.delenv("LITHARNESS_FAKE_PAD_CHARS")
    monkeypatch.delenv("LITHARNESS_NO_OUTLINE")
    assert produce.main(["resume", str(root)]) == cli.EXIT_OK
    assert "LITHARNESS_FAKE_PAD_CHARS" not in os.environ
    assert production == ["concept", "seed"]
    saved = manifest(root)
    report = produce._snapshot(root, saved)
    assert report["scenes"] == 2
    assert report["chapters"] == 1
    assert all(report["jobs"].get(state, 0) == 0 for state in produce.ACTIVE)
    assert (root / "book.html").is_file()
    assert produce.main(["resume", str(root)]) == cli.EXIT_OK
    assert produce._snapshot(root, manifest(root)) == report


def test_failed_setup_retains_trace_and_retries_only_unfinished_stage(
    tmp_path, production, monkeypatch,
):
    root = tmp_path / "serial"
    original = cli.cmd_listing

    def interrupted(args):
        (args.out / "partial.txt").write_text("incomplete provider trace", encoding="utf-8")
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "cmd_listing", interrupted)
    assert start(root) == cli.EXIT_ATTENTION
    saved = manifest(root)
    assert saved["completed"] == ["concept"]
    assert saved["attempts"][-1]["exit_code"] is None
    partial = root / Path(saved["attempts"][-1]["log"]).parent / "partial.txt"
    monkeypatch.setattr(cli, "cmd_listing", original)
    assert produce.main(["resume", str(root)]) == cli.EXIT_OK
    assert production == ["concept", "seed"]
    assert partial.read_text(encoding="utf-8") == "incomplete provider trace"


def test_finishing_on_the_last_allowed_tick_still_exports(tmp_path, production):
    baseline = tmp_path / "baseline"
    assert start(baseline) == cli.EXIT_OK
    required_ticks = manifest(baseline)["ticks"]
    root = tmp_path / "bounded"
    assert start(root, "--max-ticks", str(required_ticks)) == cli.EXIT_OK
    assert manifest(root)["ticks"] == required_ticks
    assert manifest(root)["state"] == "complete"
    assert (root / "book.html").is_file()


def test_resume_preserves_attempt_directory_created_before_its_receipt(
    tmp_path, production, monkeypatch,
):
    root = tmp_path / "serial"
    original = produce._save

    def interrupted(path, value):
        if value["state"] == "running" and value["reason"] == "listing":
            raise KeyboardInterrupt
        original(path, value)

    monkeypatch.setattr(produce, "_save", interrupted)
    assert start(root) == cli.EXIT_ATTENTION
    assert manifest(root)["completed"] == ["concept"]
    orphan = root / "attempts" / "00002-listing"
    assert orphan.is_dir()
    marker = orphan / "interrupted.txt"
    marker.write_text("preserve this attempt", encoding="utf-8")
    monkeypatch.setattr(produce, "_save", original)
    assert produce.main(["resume", str(root)]) == cli.EXIT_OK
    assert marker.read_text(encoding="utf-8") == "preserve this attempt"
    assert production == ["concept", "seed"]
    numbers = [Path(row["log"]).parts[1].split("-")[0] for row in manifest(root)["attempts"]]
    assert len(numbers) == len(set(numbers))


def test_exhausted_job_prevents_false_completion_until_resolved(tmp_path, production):
    root = tmp_path / "serial"
    assert start(root) == cli.EXIT_OK
    with SqliteStore.open(root / "book.db") as store:
        store.enqueue(Job(job_id="unfinished", job_kind="unregistered", max_attempts=1))
    assert produce.main(["resume", str(root)]) == cli.EXIT_ATTENTION
    assert produce.main(["resume", str(root)]) == cli.EXIT_ATTENTION
    assert manifest(root)["state"] == "attention"
    with SqliteStore.open(root / "book.db") as store:
        [raised] = store.open_exceptions()
        assert raised.job_id == "unfinished"
        store.resolve_exception(raised.exception_id, "operator dismissed", at="2026-09-26")
    assert produce.main(["resume", str(root)]) == cli.EXIT_OK


def test_status_does_not_create_database_and_changed_input_is_refused(
    tmp_path, production, monkeypatch, capsys,
):
    root = tmp_path / "serial"
    monkeypatch.setattr(cli, "cmd_concept", lambda args: cli.EXIT_ATTENTION)
    assert start(root) == cli.EXIT_ATTENTION
    assert not (root / "book.db").exists()
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert produce.main(["status", str(root)]) == cli.EXIT_OK
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    (root / "brief.txt").write_text("changed", encoding="utf-8")
    assert produce.main(["resume", str(root)]) == cli.EXIT_FAULT
    assert "saved input changed" in capsys.readouterr().err
    assert not (root / "book.db").exists()


def test_existing_directory_and_missing_saved_book_are_not_replaced(tmp_path, production, capsys):
    root = tmp_path / "serial"
    assert start(root, "--max-ticks", "1") == cli.EXIT_ATTENTION
    before = (root / "run.json").read_bytes()
    assert start(root) == cli.EXIT_FAULT
    assert (root / "run.json").read_bytes() == before
    (root / "book.db").rename(root / "saved.db")
    assert produce.main(["resume", str(root)]) == cli.EXIT_FAULT
    assert "database is missing" in capsys.readouterr().err
    assert not (root / "book.db").exists()


def test_queued_only_tick_finishes_a_job_but_does_not_plan_more(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    db = tmp_path / "book.db"
    assert cli.main(["--database", str(db), "import", "--fixture", "litrpg"]) == 0
    with SqliteStore.open(db) as store:
        store.enqueue(Job(job_id="unfinished", job_kind="unknown"))
    assert cli.main(["--database", str(db), "tick", "--queued-only"]) == cli.EXIT_ATTENTION
    with SqliteStore.open(db) as store:
        assert store.load_job("unfinished").attempts == 1
    # A fresh book has draftable scenes; an empty queue must still stay idle.
    clean = tmp_path / "clean.db"
    assert cli.main(["--database", str(clean), "import", "--fixture", "litrpg"]) == 0
    capsys.readouterr()
    assert cli.main(["--database", str(clean), "tick", "--queued-only"]) == 0
    assert "no_work" in capsys.readouterr().out
    with SqliteStore.open(clean) as store:
        assert sum(store.job_counts_by_status().values()) == 0


def test_later_target_extends_the_same_serial_without_recreating_it(tmp_path, production):
    root = tmp_path / "serial"
    assert start(root) == cli.EXIT_OK
    original = manifest(root)
    with SqliteStore.open_read_only(root / "book.db") as store:
        head = store.head(original["book"], original["branch"])
        earlier = {node.logical_id: node.content_sha256 for node in head.nodes if node.content}
    assert produce.main(["resume", str(root), "--chapters", "4"]) == cli.EXIT_OK
    saved = manifest(root)
    report = produce._snapshot(root, saved)
    assert saved["book"] == original["book"]
    assert saved["branch"] == original["branch"]
    assert report["chapters"] == 4
    assert report["scenes"] == 8
    assert report["planned_scenes"] == 12
    with SqliteStore.open_read_only(root / "book.db") as store:
        head = store.head(saved["book"], saved["branch"])
        assert all(head.node(key).content_sha256 == digest for key, digest in earlier.items())
    assert production == ["concept", "seed"]
    assert produce.main(["resume", str(root), "--chapters", "2"]) == cli.EXIT_FAULT
    assert manifest(root)["target_chapters"] == 4


def test_competing_runner_cannot_take_the_run(tmp_path, production, capsys):
    root = tmp_path / "serial"
    assert start(root, "--max-ticks", "1") == cli.EXIT_ATTENTION
    before = (root / "run.json").read_bytes()
    with produce._exclusive(root):
        assert produce.main(["resume", str(root)]) == cli.EXIT_FAULT
    assert "already active" in capsys.readouterr().err
    assert (root / "run.json").read_bytes() == before


def test_budget_failure_reports_reason_and_does_not_retry_in_a_loop(
    tmp_path, production, capsys,
):
    root = tmp_path / "serial"
    # Listing reports a refused setup call as exit 2; the runner preserves that contract.
    assert start(root, "--max-invocations-per-day", "0") == cli.EXIT_FAULT
    saved = manifest(root)
    assert saved["state"] == "attention"
    assert len(saved["attempts"]) < 3
    assert "budget" in capsys.readouterr().out.lower()


def test_live_lease_and_other_book_are_reported_without_drafting(
    tmp_path, production, capsys,
):
    root = tmp_path / "serial"
    assert start(root) == cli.EXIT_OK
    with SqliteStore.open(root / "book.db") as store:
        store.enqueue(Job(job_id="lease-held-elsewhere", job_kind="unknown"))
        store.claim_next("other-holder", now=produce.time.time(), duration=3600)
    assert produce.main(["resume", str(root)]) == cli.EXIT_ATTENTION
    out = capsys.readouterr().out
    assert "lease-held-elsewhere" in out
    assert "resume after expiry" in out
    assert produce._snapshot(root, manifest(root))["scenes"] == 2
    assert cli.main(["--database", str(root / "book.db"), "import", "--fixture", "litrpg"]) == 0
    before = manifest(root)["attempts"]
    assert produce.main(["resume", str(root)]) == cli.EXIT_FAULT
    assert "another book or branch" in capsys.readouterr().err
    assert manifest(root)["attempts"] == before


def test_pending_migrations_stop_status_and_resume_without_changing_the_store(
    tmp_path, production, capsys,
):
    root = tmp_path / "serial"
    assert start(root, "--max-ticks", "1") == cli.EXIT_ATTENTION
    database = root / "book.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "DELETE FROM schema_migrations WHERE name = (SELECT max(name) FROM schema_migrations)"
        )
        connection.commit()
    finally:
        connection.close()
    before = database.read_bytes()
    assert produce.main(["status", str(root)]) == cli.EXIT_FAULT
    assert produce.main(["resume", str(root)]) == cli.EXIT_FAULT
    assert "migration(s) pending" in capsys.readouterr().err
    assert database.read_bytes() == before


def test_operational_stage_fault_keeps_exit_two(tmp_path, production, monkeypatch, capsys):
    def unavailable(args):
        raise OSError("provider executable is unavailable")

    monkeypatch.setattr(cli, "cmd_concept", unavailable)
    root = tmp_path / "serial"
    assert start(root) == cli.EXIT_FAULT
    assert manifest(root)["attempts"][-1]["exit_code"] == cli.EXIT_FAULT
    assert "provider executable is unavailable" in capsys.readouterr().out
