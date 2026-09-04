"""The operator surface (§4.1, §4.3, §19 Autonomy).

Before this existed the system could not be run at all: no console script, no `__main__`,
and no caller of `Conductor.tick` outside the suite. §17's "ticks idempotently for a week
unattended" could be simulated but not attempted.

These tests drive `main(argv)` rather than the functions underneath it, because the
interface being asserted *is* the command line: argument names, output, and above all exit
codes, which are how a scheduler learns what happened.
"""

from __future__ import annotations

import contextlib
import io
import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.editorial import experimental_mechanism
from litharness.application.handlers import SCENE_DRAFT
from litharness.cli import EXIT_ATTENTION, EXIT_FAULT, EXIT_OK, build_parser, main
from litharness.domain.directives import DirectiveStatus
from litharness.domain.editorial import QualificationEvidence
from litharness.domain.events import EventType
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.nodes import NodeKind
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decision_id_for,
)
from litharness.domain.revision import new_book
from litharness.packs import litrpg

#: The steering roster the mechanism is registered over: the house's, by its moved name.
ROSTER = litrpg.LITRPG.steering


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


def test_status_reports_the_queue_and_exits_zero(db, capsys) -> None:
    run(db, "init")
    run(db, "tick")
    capsys.readouterr()
    assert run(db, "status") == EXIT_OK
    out = capsys.readouterr().out
    assert "jobs" in out
    assert "needs attention 0" in out


def test_status_json_is_machine_readable(db, capsys) -> None:
    run(db, "init")
    run(db, "tick")
    capsys.readouterr()
    run(db, "status", "--json")
    report = json.loads(capsys.readouterr().out)
    assert report["needs_attention"] == 0
    assert report["digest"]["ticks"] == 1
    assert "jobs" in report and "spend" in report


def test_status_surfaces_units_that_need_attention_and_still_exits_zero(db, capsys) -> None:
    """The count is shown to the operator driving the session; status is not an external
    monitor, so nothing keys on its exit code."""
    run(db, "init")
    store = SqliteStore.open(db)
    store.enqueue(Job(job_id="mystery-1", job_kind="no_such_handler"))
    store.close()
    for _ in range(4):
        run(db, "tick")
    capsys.readouterr()

    assert run(db, "status") == EXIT_OK
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


# --- backup and verify ---------------------------------------------------------------


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

    assert (
        run(
            db,
            "enqueue",
            "draft-1",
            "--revision",
            revision_id,
            "--node",
            "scene-1",
            "--prompt",
            "Draft the study scene.",
        )
        == EXIT_OK
    )
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


def test_a_refused_scene_count_leaves_no_trace_of_the_book(db) -> None:
    """`arc_template` refuses a book of fewer scenes than named beats — but it was consulted
    only after the decision, revision, premise and any seed state were durably committed, so
    `new --scenes 1` raised *and* half-created the book. A create that fails must fail whole:
    what remains is invisible to the operator who was told nothing was made, and their retry
    under the same ids collides with the wreckage of the refused one."""
    run(db, "init")

    assert (
        run(db, "new", "Book Zero", "--premise", "a harness learns to write", "--scenes", "1")
        == EXIT_FAULT
    )

    store = SqliteStore.open(db)
    try:
        assert store.branches() == []
        assert store.read_log() == []
        counts = {
            table: store._connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            for table in (
                "revisions",
                "node_versions",
                "policy_decisions",
                "plan_items",
                "state_records",
                "events",
            )
        }
        assert counts == dict.fromkeys(counts, 0), counts
    finally:
        store.close()


def test_a_serial_extends_in_place_without_moving_existing_scene_addresses(db) -> None:
    run(db, "init")
    assert (
        run(
            db,
            "new",
            "Endless Road",
            "--premise",
            "Every gate takes something different.",
            "--book",
            "serial-book",
            "--branch",
            "main",
        )
        == EXIT_OK
    )
    with SqliteStore.open(db) as store:
        before = store.head("serial-book", "main")
        assert before is not None
        positions = {
            node.logical_id: node.position_key
            for node in before.nodes
            if node.kind is not NodeKind.BOOK
        }
        versions = before.version_ids

    assert run(db, "extend", "--book", "serial-book", "--branch", "main") == EXIT_OK

    with SqliteStore.open(db) as store:
        after = store.head("serial-book", "main")
        assert after is not None
        scenes = [node for node in after.nodes if node.kind is NodeKind.SCENE]
        assert len(scenes) == 48, "the default extension adds one complete six-chapter arc"
        for logical_id, position in positions.items():
            assert after.node(logical_id).position_key == position
            assert after.version_ids[logical_id] == versions[logical_id]


# --- the promotion path (§10.4) ------------------------------------------------------


def _calibrate(db, **overrides: str) -> int:
    args = {
        "--metric": "craft.tricolon_rate.v0",
        "--threshold": "4.0",
        "--direction": "above",
        "--holdout": "50",
        "--flagged": "20",
        "--correct": "20",
        # 1 candidate and 2 clusters are the permissive answers, so the helper states them
        # rather than letting a default supply evidence the caller never declared.
        "--selection-family": "1",
        "--clusters": "2",
        # Required, and there is no default: a caller that says nothing about what its
        # numbers are about must not be handed the class that may claim quality.
        "--evidence-class": "judgment",
    }
    args.update(overrides)
    return run(db, "calibrate", *[part for pair in args.items() for part in pair])


def _answered(db, n: int = 50) -> None:
    """Put `n` answered audit samples in the store, so a claimed holdout is a real one.

    Every test below that expects BLOCKING-ELIGIBLE needs this now, and needing it *is* the
    fix: `why_not_promotable` compares `holdout_size` against the answered samples the store
    holds, and nothing had ever made that comparison. `--holdout 50 --flagged 20 --correct 20`
    against an empty store cleared every floor and promoted, and the digest clause was
    structurally unable to catch it because the digest of the empty set matches itself.
    """
    from litharness.domain.audit import AuditSample, Verdict

    store = SqliteStore.open(db)
    try:
        for index in range(n):
            sample = AuditSample(
                sample_id=f"cli-holdout-{index}",
                book_id="book-1",
                branch_id="branch-1",
                revision_id=f"rev-{index}",
                logical_id=f"scene-{index}",
                sampled_at="2026-08-01",
                rate=1.0,
                bucket=index,
            )
            store.record_audit_sample(sample)
            store.record_verdict(
                sample.sample_id, Verdict.KEEP_READING, at="2026-08-01", by="reader"
            )
    finally:
        store.close()


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


# --- the canon the book believes ------------------------------------------------------


def test_state_lists_what_the_book_believes_in_story_order(db, capsys) -> None:
    """**Twenty-eight verbs and none could answer "what does this book hold as true".**

    That layer gates every draft — the integrity gate refuses a candidate contradicting it,
    the context packet hands it to the generator, and propagation reads changes out of it —
    and the only way to look at it was to open the SQLite file.

    Story order, because a ledger read out of order is not a ledger. It is also the view that
    makes the arithmetic visible to a human: the in-process detector checks disagreement at a
    single position and cannot see a balance that stops adding up across them, so an operator
    reading this column is the one who notices.
    """
    run(db, "init")
    imported_id(db, capsys, "--fixture", "litrpg", "--keep-content")
    capsys.readouterr()

    assert run(db, "state") == EXIT_OK

    out = capsys.readouterr().out
    ledger = [line for line in out.splitlines() if "status_snapshot" in line]
    assert [line.split()[0] for line in ledger] == ["s1", "s2", "s3", "s4", "s5", "s6"]
    assert "gold=45" in ledger[0] and "gold=0" in ledger[-1]
    # Nineteen the fixture holds, and the twentieth is the sheet the import declared from the
    # fixture's first snapshot, in the file's own order (§205).
    assert "20 record(s)" in out
    assert "status_sheet" in out
    # The fixture's own note on its planted ledger defect, printed with the record it is
    # about. An operator reading this column is exactly who §8.3 planted it for.
    assert "the ledger-correct value is 20" in out


def test_state_narrows_to_one_subject(db, capsys) -> None:
    """A book's canon is mostly not about the thing you are looking at. The litrpg fixture
    holds nineteen records across five subjects, and the ledger is one of them."""
    run(db, "init")
    imported_id(db, capsys, "--fixture", "litrpg", "--keep-content")
    capsys.readouterr()

    assert run(db, "state", "--subject", "system") == EXIT_OK

    out = capsys.readouterr().out
    assert "rule_hp_ceiling" in out
    assert "status_snapshot" not in out, "another subject's records are not this subject's"


def test_state_says_which_records_the_system_read_out_of_its_own_prose(db, capsys) -> None:
    """Imported canon and extracted canon are different claims. One is the author's word and
    one is this system's reading of prose it generated, and an operator deciding whether to
    trust a fact needs to know which — the same reason a plan-placed story position carries a
    note saying so."""
    run(db, "init")
    imported_id(db, capsys, "--fixture", "litrpg", "--keep-content")
    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
        store.record_state_records(
            book_id,
            branch_id,
            [
                lc.StateRecord(
                    record_id="rec-x-extracted",
                    kind=lc.StateRecordKind.ASSERTION,
                    subject="rook",
                    predicate="status_snapshot",
                    value={"gold": 7},
                    story_position=lc.StoryPosition(order_key="s7"),
                    authority=lc.StateAuthority.ACCEPTED_CANON,
                    predicate_registry_version="litharness.systemvoice.v0",
                    note="story position s7 stated by the plan, not attested by the book",
                )
            ],
            created_at="2026-08-15T00:00:00Z",
        )
    finally:
        store.close()
    capsys.readouterr()

    assert run(db, "state") == EXIT_OK

    out = capsys.readouterr().out
    [extracted] = [line for line in out.splitlines() if line.startswith("s7")]
    assert "read" in extracted, "the provenance of an extracted record must be on its line"
    assert "stated by the plan" in out
    assert "1 read from this book's own prose" in out


def test_a_book_with_no_state_says_so_rather_than_printing_nothing(db, capsys) -> None:
    """An empty list and a book nobody has read look identical otherwise."""
    from litharness.adapters.contracts_fixtures import fixture_manuscript

    run(db, "init")
    # A manuscript on its own: no plan, no snapshot. The entry point an operator uses for a
    # book this system will write from nothing.
    imported_id(db, capsys, "--path", str(fixture_manuscript("mystery")))
    capsys.readouterr()

    assert run(db, "state") == EXIT_OK
    assert "no state on record" in capsys.readouterr().out


# --- plan history and rollback -------------------------------------------------------


def _book_with_two_plan_revisions(db, capsys) -> tuple[str, str]:
    """Import a fixture, then move the plan once — model-free.

    An explicit `constraint` takes the deterministic verbatim lane (§28), so this produces
    a real second plan revision with a real applied proposal behind it and never reaches a
    provider.
    """
    run(db, "init")
    imported_id(db, capsys, "--fixture", "mystery")
    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
    finally:
        store.close()
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
    run(db, "tick")
    capsys.readouterr()
    return book_id, branch_id


def test_plans_lists_the_lineage_newest_first_and_what_produced_each(db, capsys) -> None:
    """An operator could not see the plan's history at all: `plan_history` had no caller
    outside the tests, so the only way to read what direction had done to a book was to
    open the SQLite file."""
    _book_with_two_plan_revisions(db, capsys)

    assert run(db, "plans") == EXIT_OK

    out = capsys.readouterr().out
    assert "HEAD" in out
    assert "(2 revision(s)" in out
    assert "Apply constraint directive verbatim" in out, "a lineage of bare hashes would not"
    assert "from directive dir-" in out
    assert "imported" in out, "the root must be distinguishable from a proposed revision"


def test_a_plan_revision_can_be_restored_from_the_command_line(db, capsys) -> None:
    """`rollback_proposal` has been implemented, tested and unreachable: nothing in `src/`
    called it, so §19's reversibility clause held for prose and not for the plans that
    produce it. Restoring goes forward — the mistake and the correction both stay in the
    lineage — and the restored plan is a *new* revision, never the old one re-headed."""
    book_id, branch_id = _book_with_two_plan_revisions(db, capsys)
    store = SqliteStore.open(db)
    try:
        history = store.plan_history(book_id, branch_id)
        root_id = history[-1].plan_revision_id
        constrained = len(history[0].items)
    finally:
        store.close()
    capsys.readouterr()

    # EXIT_ATTENTION, because rolling back this constraint orphans the directive that
    # minted it — asserted on its own below. What is under test here is the lineage.
    assert run(db, "revert-plan", root_id) == EXIT_ATTENTION
    out = capsys.readouterr().out
    assert "restored" in out

    store = SqliteStore.open(db)
    try:
        after = store.plan_history(book_id, branch_id)
        head = after[0]
        assert len(after) == 3, "a rollback must add a revision rather than move the head back"
        assert head.plan_revision_id != root_id
        assert len(head.items) == constrained - 1
        assert [item.text for item in head.items] == [
            item.text for item in store.load_plan_revision(root_id).items
        ]
        # §19: every mutation is attributable. A plan the operator restored is no exception.
        decision = store.decision_for_revision(head.plan_revision_id)
        assert decision is not None and decision.outcome is Outcome.ACCEPT
    finally:
        store.close()


def test_a_restored_plan_says_which_direction_it_dropped(db, capsys) -> None:
    """The constraint being rolled back was minted from a director's directive, which stays
    APPLIED and goes on citing a plan item that no longer exists. That is recoverable — the
    directive is still on record and can be re-submitted — but only if the operator is told
    it happened rather than discovering it when the book drafts without the constraint."""
    book_id, branch_id = _book_with_two_plan_revisions(db, capsys)
    store = SqliteStore.open(db)
    try:
        root_id = store.plan_history(book_id, branch_id)[-1].plan_revision_id
    finally:
        store.close()
    capsys.readouterr()

    assert run(db, "revert-plan", root_id) == EXIT_ATTENTION

    out = capsys.readouterr().out
    assert "locked" in out, "a rollback is the one proposal that may move a locked item"
    assert "directive" in out


def test_restoring_the_plan_that_is_already_the_head_is_refused(db, capsys) -> None:
    book_id, branch_id = _book_with_two_plan_revisions(db, capsys)
    store = SqliteStore.open(db)
    try:
        head_id = store.plan_history(book_id, branch_id)[0].plan_revision_id
    finally:
        store.close()

    assert run(db, "revert-plan", head_id) == EXIT_FAULT
    assert "already matches" in capsys.readouterr().err


def test_restoring_a_plan_revision_that_does_not_exist_is_a_fault_not_a_traceback(
    db, capsys
) -> None:
    """A mistyped id is a bad argument, which the exit-code contract calls a fault. It must
    not escape as a `KeyError` traceback and exit 1 — the code reserved for "a unit needs a
    human" — which is the same defect the locked-database handler was written for."""
    _book_with_two_plan_revisions(db, capsys)

    assert run(db, "revert-plan", "plan-that-never-was") == EXIT_FAULT

    err = capsys.readouterr().err
    assert "no plan revision" in err and "Traceback" not in err


def test_a_book_whose_plan_was_never_proposed_has_nothing_to_restore(db, capsys) -> None:
    """The imported root is the whole lineage, so the only reachable target is the head
    itself. Saying so beats letting the operator find out from a proposal error about a
    baseline they never chose."""
    run(db, "init")
    imported_id(db, capsys, "--fixture", "mystery")
    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
        root_id = store.plan_history(book_id, branch_id)[0].plan_revision_id
    finally:
        store.close()
    capsys.readouterr()

    assert run(db, "revert-plan", root_id) == EXIT_FAULT
    assert "imported" in capsys.readouterr().err


# --- propagation ---------------------------------------------------------------------


def _rename_change_set(tmp_path, book_id: str, branch_id: str, name: str = "Julian"):
    """A ChangeSet artifact of the shared schema, as a sibling would hand one over.

    §13 keeps the integration a file of a contract rather than an import, exactly as
    `ingest` reads an `EvaluationArtifact`.
    """
    path = tmp_path / "change-set.json"
    path.write_text(
        json.dumps(
            {
                "meta": {
                    "schema_version": "1.0.0",
                    "artifact_id": "cs-cli-1",
                    "artifact_kind": "change_set",
                    "created_at": "2026-08-14T00:00:00Z",
                    "actor": "operator",
                    "tool": {"name": "litharness-tests", "version": "0.1.0"},
                },
                "change_set_id": "cs-cli-1",
                "base_revision": "unused",
                "target_branch": branch_id,
                "actor": "author",
                "operations": [
                    {"kind": "rename", "logical_source_id": "entity:julian", "detail": {}}
                ],
                "idempotency_key": "idem-cli-1",
                "extracted_changes": [
                    {
                        "kind": "entity_renamed",
                        "subject": "julian",
                        "before": name,
                        "after": "Adrian",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _imported_mystery(db, capsys) -> tuple[str, str]:
    run(db, "init")
    imported_id(db, capsys, "--fixture", "mystery", "--keep-content")
    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
    finally:
        store.close()
    capsys.readouterr()
    return book_id, branch_id


def test_propagate_reports_what_a_change_reaches_and_why(db, tmp_path, capsys) -> None:
    """`domain/impact.py` scored blast-radius predictions against the gold suites and nothing
    produced one; `domain/propagation.py` now does, and this is the surface an operator has
    to it. Reasons are printed with the ids because the output is a proposal to spend model
    calls over somebody's book."""
    book_id, branch_id = _imported_mystery(db, capsys)
    path = _rename_change_set(tmp_path, book_id, branch_id)

    assert run(db, "propagate", str(path)) == EXIT_OK

    out = capsys.readouterr().out
    assert "scene-3" in out and "scene-5" in out and "scene-6" in out
    assert "scene-1" not in out, "a scene that never says the name is not reached"
    assert "entity_renamed" in out
    assert "spells 'Julian'" in out


def test_propagate_records_the_analysis_as_an_event(db, tmp_path, capsys) -> None:
    """`ImpactAnalyzed` has been in the contract's `EventType` since 1.0 with no producer
    anywhere. An analysis an operator acted on and the log does not carry is a decision with
    no record, which is the shape §19's audit clause exists to refuse."""
    book_id, branch_id = _imported_mystery(db, capsys)
    run(db, "propagate", str(_rename_change_set(tmp_path, book_id, branch_id)))

    store = SqliteStore.open(db)
    try:
        [analysed] = [
            entry.event
            for entry in store.read_log()
            if entry.event.event_type is EventType.IMPACT_ANALYZED
        ]
    finally:
        store.close()
    assert analysed.payload["change_set_id"] == "cs-cli-1"
    # Three scenes that spell the name and three records that carry it as subject or value.
    assert analysed.payload["reached"] == 6
    assert analysed.payload["nodes"] == ["scene-3", "scene-5", "scene-6"]
    assert analysed.payload["complete"] is True


def test_propagate_enqueues_evaluation_only_when_asked(db, tmp_path, capsys) -> None:
    """Reporting and acting are separate verbs on purpose: the report costs nothing and the
    work costs model calls over a book the operator may not want re-checked yet. State
    records are not enqueued — nothing re-evaluates a record, and a job naming one would park
    for want of a handler."""
    book_id, branch_id = _imported_mystery(db, capsys)
    path = _rename_change_set(tmp_path, book_id, branch_id)

    run(db, "propagate", str(path))
    store = SqliteStore.open(db)
    try:
        assert store.job_counts_by_status() == {}
    finally:
        store.close()
    capsys.readouterr()

    assert run(db, "propagate", str(path), "--enqueue") == EXIT_OK
    assert "3 evaluation(s)" in capsys.readouterr().out

    store = SqliteStore.open(db)
    try:
        queued = store.jobs_by_status(JobStatus.QUEUED)
        assert {job.payload["logical_id"] for job in queued} == {
            "scene-3",
            "scene-5",
            "scene-6",
        }
    finally:
        store.close()


def test_enqueueing_the_same_analysis_twice_queues_nothing_new(db, tmp_path, capsys) -> None:
    """Job ids are content-derived, so a re-run converges rather than doubling the queue —
    the same property `ingest` has, and the reason a propagation report is safe to act on
    twice."""
    book_id, branch_id = _imported_mystery(db, capsys)
    path = _rename_change_set(tmp_path, book_id, branch_id)
    run(db, "propagate", str(path), "--enqueue")
    capsys.readouterr()

    assert run(db, "propagate", str(path), "--enqueue") == EXIT_OK
    assert "0 evaluation(s)" in capsys.readouterr().out

    store = SqliteStore.open(db)
    try:
        assert len(store.jobs_by_status(JobStatus.QUEUED)) == 3
    finally:
        store.close()


def test_a_change_the_engine_cannot_read_exits_non_zero(db, tmp_path, capsys) -> None:
    """The property that makes an empty result trustworthy. `pov_changed` is in the
    contract's vocabulary and has no rule, so "nothing propagates" here would mean "nobody
    looked" — indistinguishable from a clean analysis unless it says so and exits non-zero,
    exactly as an incomplete evaluation does."""
    book_id, branch_id = _imported_mystery(db, capsys)
    path = tmp_path / "unreadable.json"
    source = json.loads(_rename_change_set(tmp_path, book_id, branch_id).read_text("utf-8"))
    source["extracted_changes"] = [{"kind": "pov_changed", "subject": "mara"}]
    path.write_text(json.dumps(source), encoding="utf-8")

    assert run(db, "propagate", str(path)) == EXIT_ATTENTION

    captured = capsys.readouterr()
    assert "pov_changed" in captured.err
    assert "no rule" in captured.err


def test_a_surface_only_change_reaches_nothing_and_is_still_a_clean_run(
    db, tmp_path, capsys
) -> None:
    """Zero targets and exit 0 — the case that must stay distinguishable from the one above.
    §17 names it: a typography edit that propagates rewrites conforming prose."""
    book_id, branch_id = _imported_mystery(db, capsys)
    path = tmp_path / "surface.json"
    source = json.loads(_rename_change_set(tmp_path, book_id, branch_id).read_text("utf-8"))
    source["extracted_changes"] = [{"kind": "surface_only"}]
    path.write_text(json.dumps(source), encoding="utf-8")

    assert run(db, "propagate", str(path)) == EXIT_OK
    assert "nothing" in capsys.readouterr().out.lower()


def test_the_environment_default_is_off_unless_it_says_a_true_thing(db, monkeypatch) -> None:
    """An unset variable and `LITHARNESS_NO_OUTLINE=maybe` are both "no". A flag that read
    any non-empty string as true would make `=0` mean yes. (This used to exercise
    `LITHARNESS_NO_BILLING`, retired with provider selection; the parsing property is
    generic and lives on with the surviving env flag.)"""
    monkeypatch.setenv("LITHARNESS_NO_OUTLINE", "0")
    assert build_parser().parse_args(["tick"]).no_outline is False
    monkeypatch.setenv("LITHARNESS_NO_OUTLINE", "true")
    assert build_parser().parse_args(["tick"]).no_outline is True


def test_the_retired_forge_command_is_not_registered() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["forge"])


def test_reader_checkpoints_are_explicit_and_history_is_read_only_surface(monkeypatch) -> None:
    monkeypatch.delenv("LITHARNESS_READER_CHECKPOINTS", raising=False)
    assert build_parser().parse_args(["tick"]).reader_checkpoints is False
    assert build_parser().parse_args(["--reader-checkpoints", "tick"]).reader_checkpoints is True
    assert build_parser().parse_args(["readers", "--history"]).history is True


def test_reader_history_inspects_without_registering_or_calling_a_model(db, capsys) -> None:
    _imported_mystery(db, capsys)
    capsys.readouterr()

    assert run(db, "readers", "--history") == EXIT_OK

    shown = capsys.readouterr().out
    assert "reader.anticipation.v0: unregistered" in shown
    assert "0 versioned observation(s), 0 editorial intervention(s)" in shown


def test_reader_mechanism_qualification_requires_the_complete_evidence_artifact(
    db, tmp_path, capsys
) -> None:
    assert run(db, "init") == EXIT_OK
    candidate = experimental_mechanism(registered_at="2026-08-27T12:00:00Z", roster=ROSTER)
    with SqliteStore.open(db) as store:
        store.register_reader_mechanism(candidate)
    evidence: dict[str, object] = {
        "candidate_version_id": candidate.version_id,
        "mechanism_id": candidate.mechanism_id,
        "mechanism_spec_digest": candidate.spec_digest,
        "battery_registration_digest": "a" * 64,
        "battery_manifest_digest": "b" * 64,
        "registered_bar_digest": "c" * 64,
        "source_artifact_digests": ["d" * 64, "e" * 64],
        "holdout_books": 2,
        "heldout_transformations": True,
        "edit_fingerprint_passed": True,
        "memorisation_controls_passed": True,
        "full_volume_passed": True,
        "cross_volume_passed": True,
        "growing_serial_passed": True,
        "transfer_passed": True,
        "operator_acceptance_passed": True,
        "decided_at": "2026-08-27T13:00:00Z",
    }
    assert QualificationEvidence.from_payload(evidence).evidence_digest
    artifact = tmp_path / "qualification.json"
    artifact.write_text(json.dumps(evidence), encoding="utf-8")
    capsys.readouterr()

    assert run(db, "reader-mechanism", "qualify", "--evidence", str(artifact)) == EXIT_OK
    assert "qualified" in capsys.readouterr().out
    assert run(db, "reader-mechanism", "withdraw", "--reason", "transfer regressed") == EXIT_OK
    assert "withdrawn" in capsys.readouterr().out


def test_reader_mechanism_refuses_an_evidence_artifact_with_a_failed_control(
    db, tmp_path, capsys
) -> None:
    assert run(db, "init") == EXIT_OK
    candidate = experimental_mechanism(registered_at="2026-08-27T12:00:00Z", roster=ROSTER)
    with SqliteStore.open(db) as store:
        store.register_reader_mechanism(candidate)
    artifact = tmp_path / "failed.json"
    artifact.write_text(
        json.dumps(
            {
                "candidate_version_id": candidate.version_id,
                "mechanism_id": candidate.mechanism_id,
                "mechanism_spec_digest": candidate.spec_digest,
                "battery_registration_digest": "a" * 64,
                "battery_manifest_digest": "b" * 64,
                "registered_bar_digest": "c" * 64,
                "source_artifact_digests": ["d" * 64, "e" * 64],
                "holdout_books": 2,
                "heldout_transformations": True,
                "edit_fingerprint_passed": False,
                "memorisation_controls_passed": True,
                "full_volume_passed": True,
                "cross_volume_passed": True,
                "growing_serial_passed": True,
                "transfer_passed": True,
                "operator_acceptance_passed": True,
                "decided_at": "2026-08-27T13:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    capsys.readouterr()

    assert run(db, "reader-mechanism", "qualify", "--evidence", str(artifact)) == EXIT_FAULT
    assert "every registered qualification control" in capsys.readouterr().err


def test_reader_evidence_audit_is_call_free_and_writes_private_keys_separately(
    db, tmp_path, capsys
) -> None:
    _imported_mystery(db, capsys)
    out = tmp_path / "audit"
    capsys.readouterr()

    assert run(db, "reader-evidence-audit", "--out", str(out), "--json") == EXIT_OK

    report = json.loads(capsys.readouterr().out)
    assert report["ecological_manifest"]["promotion_bar"] is None
    assert "candidates" not in report["census"]
    assert "expected_value" not in json.dumps(report)
    assert (out / "evidence-audit.json").exists()
    public = json.loads((out / "battery.public.json").read_text(encoding="utf-8"))
    assert public["version"].endswith("public.v1")
    private = json.loads((out / "battery.private.json").read_text(encoding="utf-8"))
    assert "never pass this file to a reader" in private["warning"]


def test_model_written_text_reaches_a_redirected_stdout_in_utf8() -> None:
    """The operator surface's half of `_write_document`'s encoding rule, and it cost a run.

    `print` goes through the console's own codec, which is cp1252 on this host. Measured
    2026-08-25: `architect seed` ran for sixteen minutes, declared 278 records, and then died
    on `UnicodeEncodeError` printing the agent's closing report — the one artifact that says
    what it built and what it left open — because the report contained an arrow. The store had
    already committed; what was lost was the only human-readable account of it.
    """
    from litharness.cli import _say

    class Buffered:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def flush(self) -> None:
            pass

    stream = Buffered()
    with contextlib.redirect_stdout(stream):  # type: ignore[arg-type]
        _say("a → b — c")
    assert stream.buffer.getvalue() == "a → b — c\n".encode()


def test_saying_something_still_works_where_stdout_has_no_buffer() -> None:
    """pytest's capsys is exactly that stdout, so the fallback is not hypothetical."""
    from litharness.cli import _say

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        _say("plain")
    assert captured.getvalue() == "plain\n"


def test_the_architects_allowance_is_every_world_command_except_accept() -> None:
    """The omission is the containment, and the list may not rot in either direction.

    §146.9 measured the two facts this shape rests on, on `claude` 2.1.236 through the
    production argv: an enumerated allowance is enforced — the omitted command is refused, and
    the refusal lands in the envelope's `permission_denials` — where the single glob
    `Bash(litharness world:*)` this replaced let `litharness world accept` run, leaving the
    Architect's inability to self-accept resting on prompt text. Deriving the set from the real
    parser keeps both failure directions loud: a new world subcommand cannot arrive
    pre-allowed, and one forgotten in the allowance surfaces as this assertion rather than as
    an agent's silently refused turn. The live half is
    `test_live_the_shipped_allowances_enforce_their_own_boundaries`.
    """
    import argparse

    from litharness.application import world_agent

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

    allowed = set()
    for entry in world_agent.ALLOWED_TOOLS:
        assert entry.startswith("Bash(litharness world ") and entry.endswith(":*)"), entry
        assert "," not in entry, "the CLI transport joins the allowance with a comma"
        allowed.add(entry.removeprefix("Bash(litharness world ").removesuffix(":*)"))

    assert allowed == set(world_sub.choices) - {"accept"}
    assert world_agent.render_seed_request("a listing").allowed_tools == world_agent.ALLOWED_TOOLS
    assert (
        world_agent.render_grow_request("prose", logical_id="s1").allowed_tools
        == world_agent.ALLOWED_TOOLS
    )


# --- the dossier of a scene nobody accepted (§234) -----------------------------------------


def test_why_finds_the_unit_of_a_scene_nobody_accepted(db, capsys) -> None:
    """`jobs` counted a parked unit and `why --scene` said no unit was on record, because the
    dossier reached a job only through the decision that accepted a revision. Pilot 25 draw 6
    held one parked and one poisoned unit, each invisible to the verb the skill sends a reader
    to for *a scene was never written*. The unit is found by the scene it names, its latest
    decision stands in for the one that never accepted, and the frozen prompt prints."""
    run(db, "init")
    store = SqliteStore.open(db)
    revision = new_book("book-why", "main", title="The Why", scenes=2)
    store.commit_revision(revision, created_at="2026-09-04T00:00:00Z")
    gate = GateOutcome(
        gate=GateKind.INTEGRITY,
        rule_or_critic_id="integrity.progression.v0",
        passed=False,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        vetoes=(Veto.PROGRESSION_UNMOVED,),
        detail="Coat was named as moving here; grey_coat reads 1 at s2 before and after",
    )
    store.enqueue(
        Job(
            job_id="beat-parked",
            job_kind=SCENE_DRAFT,
            status=JobStatus.PARKED,
            attempts=3,
            payload={
                "revision_id": revision.revision_id,
                "book_id": "book-why",
                "branch_id": "main",
                "logical_id": "scene-2",
                "prompt": "Now write scene two, in which the coat is buttoned.",
                "system": "You draft.",
            },
        )
    )
    store.record_decision(
        PolicyDecision(
            decision_id=decision_id_for("beat-parked", 3, (gate,)),
            outcome=Outcome.PARK,
            gates=(gate,),
            job_id="beat-parked",
            logical_id="scene-2",
            base_revision_id=revision.revision_id,
            attempt=3,
            reason="attempt budget exhausted with progression_unmoved outstanding",
        ),
        decided_at="2026-09-04T00:01:00Z",
    )
    store.close()

    assert run(db, "why", "--scene", "2") in (EXIT_OK, EXIT_ATTENTION)
    shown = capsys.readouterr().out
    assert "beat-parked  scene_draft  parked  3 attempt(s)" in shown
    assert "latest on an unfinished unit" in shown
    assert "grey_coat reads 1 at s2 before and after" in shown
    assert "Now write scene two, in which the coat is buttoned." in shown
    assert "ABSENT - no queued unit" not in shown

    assert run(db, "why", "--scene", "2", "--json") in (EXIT_OK, EXIT_ATTENTION)
    dossier = json.loads(capsys.readouterr().out)
    assert dossier["job"]["job_id"] == "beat-parked"
    assert dossier["decision"]["outcome"] == Outcome.PARK.value
    assert "prompt" not in dossier["absent"]
