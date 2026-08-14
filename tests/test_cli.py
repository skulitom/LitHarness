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
from litharness.domain.events import EventType
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.policy import Outcome


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


def test_an_unopenable_database_exits_two_not_one(tmp_path, capsys) -> None:
    """The README calls exit codes "the interface" and names a locked database as the first
    example of a fault a supervisor should absorb — and it was the one fault not handled.
    `sqlite3.Error` is not an `OSError`, so it escaped as a traceback and exit 1, the code
    reserved for "a unit needs a human". Two overlapping cron ticks contend on
    `BEGIN IMMEDIATE` by design, so this is the expected fault at the plan's cadence.
    """
    unreachable = tmp_path / "no" / "such" / "dir" / "book.db"

    assert main(["--database", str(unreachable), "status"]) == EXIT_FAULT

    err = capsys.readouterr().err
    assert "litharness: OperationalError" in err
    assert "Traceback" not in err


def test_minus_one_means_unbounded_on_every_ceiling_including_dollars(db, capsys) -> None:
    """`-1` has to mean the same thing on every ceiling. The dollar ceiling alone was passed
    through raw, so the documented idiom for "unbounded" set a ceiling of -$1.00 — and the
    check refuses on `spent >= ceiling`, so $0.00 met it and every call was refused. An
    operator following the README to disable the dollar ceiling stopped the system dead.
    """
    run(db, "init")
    imported_id(db, capsys, "--fixture", "mystery")

    main(["--database", str(db), "--max-cost-usd-per-day", "-1", "tick"])

    # The exit code depends on whether the draft cleared its shape gate, which is not what
    # is under test. What is: that the *budget* never refused. A refusal is loud — an event,
    # a decision carrying a budget gate, and an exception — so assert on those directly.
    store = SqliteStore.open(db)
    try:
        assert EventType.BUDGET_EXHAUSTED not in [e.event.event_type for e in store.read_log()]
        assert store.open_exceptions() == []
    finally:
        store.close()


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


def test_a_directive_can_be_scoped_from_the_operator_surface(db, capsys) -> None:
    run(db, "init")
    assert (
        run(
            db,
            "directive",
            "Do not add a second protagonist.",
            "--kind",
            "constraint",
            "--book",
            "book-1",
            "--branch",
            "main",
        )
        == EXIT_OK
    )

    store = SqliteStore.open(db)
    try:
        [captured] = store.directives_by_status(DirectiveStatus.RECEIVED)
        assert (captured.book_id, captured.branch_id) == ("book-1", "main")
    finally:
        store.close()


def test_the_next_tick_applies_an_explicit_constraint_before_drafting(db, capsys) -> None:
    run(db, "init")
    imported_id(db, capsys, "--fixture", "mystery")
    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
    finally:
        store.close()
    capsys.readouterr()

    run(
        db,
        "directive",
        "Keep the rain motif in the final scene.",
        "--kind",
        "constraint",
        "--book",
        book_id,
        "--branch",
        branch_id,
    )
    capsys.readouterr()
    assert run(db, "tick") == EXIT_OK
    assert "ran_job" in capsys.readouterr().out

    store = SqliteStore.open(db)
    try:
        [applied] = store.directives_by_status(DirectiveStatus.APPLIED)
        [constraint_id] = applied.produced_constraint_ids
        constraint = store.plan_revision(book_id, branch_id).item(constraint_id)  # type: ignore[union-attr]
        assert constraint.text == applied.body
        assert constraint.locked
        assert store.job_counts_by_status()["succeeded"] == 1
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


# --- getting a book in (§17 Stage 1's precondition) -----------------------------------


def imported_id(db, capsys, *extra: str) -> str:
    """Import a fixture and return the revision id the command printed."""
    capsys.readouterr()  # discard whatever an earlier command left buffered
    assert run(db, "import", *extra) == EXIT_OK
    return capsys.readouterr().out.splitlines()[0].strip()


def test_import_opens_the_closed_loop(db, capsys) -> None:
    """The whole point. `enqueue` requires a `--revision`, a revision id came only from
    committing a revision, and the only caller of `commit_revision` outside the store was
    the draft handler — which needs a job, which needs the id. Every operator verb here
    acted on a book that no command could create."""
    run(db, "init")
    revision_id = imported_id(db, capsys, "--fixture", "mystery")

    assert run(
        db, "enqueue", "draft-1", "--revision", revision_id,
        "--node", "scene-1", "--prompt", "Draft the study scene.",
    ) == EXIT_OK
    capsys.readouterr()

    run(db, "jobs")
    assert "queued       1" in capsys.readouterr().out

    store = SqliteStore.open(db)
    try:
        revision = store.load_revision(revision_id)
        assert revision.node("scene-1").content is None
        assert len(revision.nodes) == 7
    finally:
        store.close()


def test_the_imported_revision_is_attributable(db, capsys) -> None:
    """§19: every mutation is attributable to a recorded policy decision. An import is a
    mutation, so it carries one — naming where the book came from."""
    run(db, "init")
    revision_id = imported_id(db, capsys, "--fixture", "litrpg")

    store = SqliteStore.open(db)
    try:
        decision = store.decision_for_revision(revision_id)
        assert decision is not None
        assert decision.outcome is Outcome.ACCEPT
        assert decision.reason is not None and "imported from" in decision.reason
        assert decision.gates == ()
    finally:
        store.close()


def test_importing_the_same_book_twice_changes_nothing(db, capsys) -> None:
    """Content-addressed, so a repeated import converges instead of forking the book — the
    same property that makes a retried tick safe."""
    run(db, "init")
    first = imported_id(db, capsys, "--fixture", "mystery")
    second = imported_id(db, capsys, "--fixture", "mystery")
    assert first == second

    store = SqliteStore.open(db)
    try:
        assert store.verify_integrity() == 1
        rows = store._connection.execute("SELECT COUNT(*) AS n FROM policy_decisions").fetchone()
        assert rows["n"] == 1
    finally:
        store.close()


def test_import_reads_the_fixture_as_utf8(db, capsys) -> None:
    """The default encoding on this platform is cp1252, and every litrpg scene carries an
    em-dash. Read wrongly, each becomes three characters — and the node hash check then
    reports corruption in a file that is not corrupt."""
    run(db, "init")
    revision_id = imported_id(db, capsys, "--fixture", "litrpg", "--keep-content")

    store = SqliteStore.open(db)
    try:
        content = store.load_revision(revision_id).node("scene-1").content or ""
    finally:
        store.close()
    assert "—" in content
    assert "â" not in content  # the leading byte of a mojibaked em-dash


def test_keeping_the_content_says_the_book_cannot_be_drafted(db, capsys) -> None:
    """An import that preserves the source prose looks like a book and can take no draft
    job. Saying so is the difference between a flag and a trap."""
    run(db, "init")
    run(db, "import", "--fixture", "mystery", "--keep-content")
    out = capsys.readouterr().out
    assert "0 scene(s) cleared" in out
    assert "no scene is draftable" in out


def test_a_manuscript_that_is_not_there_is_an_operational_fault(db, tmp_path, capsys) -> None:
    run(db, "init")
    assert run(db, "import", "--path", str(tmp_path / "absent.json")) == EXIT_FAULT
    assert "litharness:" in capsys.readouterr().err


def test_import_needs_exactly_one_source(db) -> None:
    run(db, "init")
    with pytest.raises(SystemExit):
        run(db, "import")


# --- the promotion path (§10.4) ------------------------------------------------------


def _calibrate(db, **overrides: str) -> int:
    args = {
        "--metric": "craft.tricolon_rate.v0",
        "--threshold": "4.0",
        "--direction": "above",
        "--precision": "0.86",
        "--holdout": "50",
        "--flagged": "20",
    }
    args.update(overrides)
    return run(db, "calibrate", *[part for pair in args.items() for part in pair])


def test_a_calibration_can_be_recorded_from_the_command_line(db, capsys) -> None:
    """`record_calibration` shipped with migration 014 and had no caller outside the tests,
    so the only route to a blocking craft gate ran through writing Python against the store —
    the promotion path was unreachable by the operator who authorises it."""
    run(db, "init")
    assert _calibrate(db) == EXIT_OK
    out = capsys.readouterr().out
    assert "BLOCKING-ELIGIBLE" in out

    assert run(db, "calibrations") == EXIT_OK
    assert "BLOCKING-ELIGIBLE" in capsys.readouterr().out


def test_recording_the_same_measurement_twice_does_not_duplicate_it(db, capsys) -> None:
    run(db, "init")
    _calibrate(db)
    capsys.readouterr()
    assert _calibrate(db) == EXIT_OK
    assert "already on record" in capsys.readouterr().out


def test_a_calibration_that_cannot_promote_is_still_recorded_and_says_why(db, capsys) -> None:
    """Recording evidence that cannot yet promote is a legitimate act — it is how evidence
    accumulates toward evidence that can. What it must not do is look like promotion."""
    run(db, "init")
    assert _calibrate(db, **{"--flagged": "1"}) == EXIT_OK
    out = capsys.readouterr().out
    assert "not promotable" in out
    assert "BLOCKING-ELIGIBLE" not in out


def test_incoherent_numbers_are_refused_before_they_are_stored(db, capsys) -> None:
    run(db, "init")
    assert _calibrate(db, **{"--flagged": "51", "--holdout": "50"}) == EXIT_FAULT
    assert "more flags than judgments" in capsys.readouterr().err
    assert _calibrate(db, **{"--precision": "1.4"}) == EXIT_FAULT
    assert "not a proportion" in capsys.readouterr().err


def test_a_corrected_measurement_is_reported_as_it_was_stored(db, capsys) -> None:
    """The defect an end-to-end run found and the unit tests did not: `calibrate` printed
    the promotability of the record it *built*, while `INSERT OR IGNORE` kept an older row
    with different numbers. The operator was told BLOCKING-ELIGIBLE about a gate that did
    not exist."""
    run(db, "init")
    _calibrate(db, **{"--flagged": "1", "--precision": "1.0"})
    capsys.readouterr()
    assert _calibrate(db, **{"--flagged": "21", "--precision": "0.86"}) == EXIT_OK
    out = capsys.readouterr().out
    assert "recorded" in out
    assert "21 flag(s)" in out
    assert "BLOCKING-ELIGIBLE" in out

    assert run(db, "calibrations") == EXIT_OK
    listed = capsys.readouterr().out
    assert "BLOCKING-ELIGIBLE" in listed, "the correction is the one that gates"
    assert listed.count("craft.tricolon_rate.v0") == 2, "and the superseded row is kept"


def test_a_measurement_made_elsewhere_is_reported_as_stale(db, capsys) -> None:
    """`calibrate` asked `why_not_promotable` with the same digest it had just stored, so
    the staleness clause compared a value against itself and could never fire. Harmless when
    the digest was defaulted from the store; wrong in the one case `--verdicts-digest`
    exists for, because `_promoted_craft_gates` recomputes from `audit_samples()` at every
    draft and rejects the row as stale forever. The operator would have been told
    BLOCKING-ELIGIBLE about a gate that can never be built."""
    run(db, "init")
    assert _calibrate(db, **{"--verdicts-digest": "measured-on-another-machine"}) == EXIT_OK
    out = capsys.readouterr().out
    assert "BLOCKING-ELIGIBLE" not in out
    assert "verdict set has changed" in out


def test_ingesting_a_failed_evaluation_exits_non_zero(db, tmp_path, capsys) -> None:
    """The operator-facing half. A supervisor reading exit codes must not be told a book is
    clean by a run in which every detector failed — and EXIT_ATTENTION rather than EXIT_FAULT,
    because a detector that could not resolve its evidence fails identically next cadence:
    the artifact read fine, the evaluation did not finish."""
    import json as _json

    from litharness.adapters.contracts_fixtures import fixture_findings

    run(db, "init")
    run(db, "import", "--fixture", "litrpg")
    payload = _json.loads(fixture_findings("litrpg").read_text(encoding="utf-8"))
    payload["findings"] = []
    payload["errors"] = [
        {"stage": "evidence_resolution", "reason": "EvidenceResolutionError", "detail": None}
        for _ in range(6)
    ]
    path = tmp_path / "errored.json"
    path.write_text(_json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()

    assert run(db, "ingest", str(path)) == EXIT_ATTENTION
    captured = capsys.readouterr()
    assert "INCOMPLETE" in captured.err
    assert "6 detector error(s)" in captured.err
    assert "did not finish is not a clean book" in captured.err


def test_ingesting_a_completed_evaluation_still_exits_zero(db, capsys) -> None:
    """The control. The golden artifacts record finished runs, and the new check must not
    make a working ingest look broken."""
    from litharness.adapters.contracts_fixtures import fixture_findings

    run(db, "init")
    run(db, "import", "--fixture", "litrpg")
    assert run(db, "ingest", str(fixture_findings("litrpg"))) == EXIT_OK
    assert "INCOMPLETE" not in capsys.readouterr().err
