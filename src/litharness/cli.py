"""The operator surface: what cron runs, and what a human runs to look inside.

Until this module existed the system could not be operated at all. §4.1 specifies "a
cron-style tick (Windows Task Scheduler / cron; every 5-15 minutes) launches or wakes the
Conductor", and there was no launchable target — no console script, no `__main__`, and no
caller of `Conductor.tick` outside the test suite. §17's Stage 0 exit criterion ("the
Conductor ticks idempotently for a week unattended") could not be attempted, only
simulated.

**Exit codes are the interface to the scheduler, so they are part of the contract.**
0 means the tick did what it was asked, including finding nothing to do — a quiet system
is a healthy one and must not page anyone. 1 is reserved for a unit that failed or parked,
which is a fact a human should eventually see but not an emergency. 2 is an operational
fault: the database is locked, the migrations are missing, the disk is full. A supervisor
should retry 2 on the next cadence and never treat it as the system reporting on its work.

The tick deliberately does **not** swallow storage errors. A locked database means another
tick is mid-flight, and the correct response is to exit and let the next cadence pick it
up — not to wait, and certainly not to force it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from litharness.adapters.sqlite_store import MigrationsMissing, SqliteStore
from litharness.application import status as status_module
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus, directive_id_for
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.providers import build_default_registry

#: Exit codes, which are how the scheduler reads the outcome. See the module docstring.
EXIT_OK = 0
EXIT_ATTENTION = 1
EXIT_FAULT = 2

DEFAULT_DB = "litharness.db"


def _now() -> float:
    return time.time()


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _store(args: argparse.Namespace) -> SqliteStore:
    return SqliteStore.open(args.database)


def _conductor(store: SqliteStore, args: argparse.Namespace) -> Conductor:
    registry = build_default_registry()
    return Conductor(
        store=store,
        holder=args.holder,
        project_id=args.project,
        registry=registry,
        handlers={
            SCENE_DRAFT: make_scene_draft_handler(registry, store, args.project),
        },
    )


# -- subcommands ----------------------------------------------------------------------


def cmd_tick(args: argparse.Namespace) -> int:
    """One bounded unit of work. This is what the scheduler invokes."""
    store = _store(args)
    try:
        result = _conductor(store, args).tick(_now())
    finally:
        store.close()

    print(f"{result.outcome.value} tick={result.tick_id}", end="")
    if result.job_id:
        print(f" job={result.job_id}", end="")
    print(
        f" reconciled={result.reconciled} dispatched={result.dispatched}"
        f" ingested={result.ingested}"
    )
    if result.outcome in {TickOutcome.JOB_FAILED, TickOutcome.JOB_PARKED}:
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        report = status_module.collect(store, _now())
    finally:
        store.close()

    print(json.dumps(report.as_dict(), indent=2) if args.json else report.render())
    # A stalled or backed-up system is worth a non-zero exit so `status` is usable in a
    # cheap external check without parsing its output.
    return EXIT_ATTENTION if (report.stalled or report.needs_attention) else EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    """Create the database and apply migrations. Safe to re-run."""
    store = _store(args)
    try:
        applied = [
            row["name"]
            for row in store._connection.execute(
                "SELECT name FROM schema_migrations ORDER BY name"
            )
        ]
    finally:
        store.close()
    print(f"{args.database}: {len(applied)} migration(s) applied")
    for name in applied:
        print(f"  {name}")
    return EXIT_OK


def cmd_directive(args: argparse.Namespace) -> int:
    """Drop direction into the inbox. The next tick ingests it."""
    now = _now()
    stamp = _stamp(now)
    kind = DirectiveKind(args.kind)
    directive = Directive(
        directive_id=directive_id_for(kind, args.text, stamp),
        kind=kind,
        body=args.text,
        received_at=stamp,
    )
    store = _store(args)
    try:
        fresh = store.submit_directive(directive, received_at=stamp)
    finally:
        store.close()
    print(f"{'accepted' if fresh else 'duplicate'} {directive.directive_id}")
    return EXIT_OK


def cmd_directives(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        items = store.directives_by_status(DirectiveStatus(args.status))
    finally:
        store.close()
    for item in items:
        print(f"{item.directive_id}  {item.kind.value:<14} p{item.precedence:<4} {item.body}")
    print(f"({len(items)} {args.status})")
    return EXIT_OK


def cmd_jobs(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        if args.status:
            jobs = store.jobs_by_status(JobStatus(args.status))
            for job in jobs:
                print(
                    f"{job.job_id}  {job.job_kind:<14} attempts={job.attempts} "
                    f"{job.error or ''}"
                )
            print(f"({len(jobs)} {args.status})")
        else:
            for name, count in store.job_counts_by_status().items():
                print(f"{name:<12} {count}")
    finally:
        store.close()
    return EXIT_OK


def cmd_revive(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        job = store.revive(args.job_id)
    finally:
        store.close()
    print(f"revived {job.job_id} -> {job.status.value}")
    return EXIT_OK


def cmd_enqueue(args: argparse.Namespace) -> int:
    payload = {
        "revision_id": args.revision,
        "logical_id": args.node,
        "prompt": args.prompt,
    }
    store = _store(args)
    try:
        store.enqueue(
            Job(
                job_id=args.job_id,
                job_kind=SCENE_DRAFT,
                payload=payload,
                input_digest=input_digest_for(payload),
                priority=args.priority,
            )
        )
    finally:
        store.close()
    print(f"enqueued {args.job_id}")
    return EXIT_OK


def cmd_pause(args: argparse.Namespace) -> int:
    now = _now()
    store = _store(args)
    try:
        store.set_control("paused", "true", at=_stamp(now), by=args.holder)
    finally:
        store.close()
    print("paused; ticks will report 'paused' until resumed")
    return EXIT_OK


def cmd_resume(args: argparse.Namespace) -> int:
    now = _now()
    store = _store(args)
    try:
        store.set_control("paused", "false", at=_stamp(now), by=args.holder)
    finally:
        store.close()
    print("resumed")
    return EXIT_OK


def cmd_backup(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        store.backup_to(args.destination)
    finally:
        store.close()
    print(f"backed up to {args.destination}")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    """Rebuild every revision from canonical records — §19's integrity check."""
    store = _store(args)
    try:
        count = store.verify_integrity()
    finally:
        store.close()
    print(f"{count} revision(s) rebuild cleanly")
    return EXIT_OK


# -- wiring ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="litharness",
        description="Operate the LitHarness Conductor.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(DEFAULT_DB),
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--holder",
        default="cron",
        help="instance identity for the Conductor lease (default: cron)",
    )
    parser.add_argument(
        "--project",
        default="00000000-0000-5000-8000-000000000000",
        help="project id recorded on emitted events",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    tick = sub.add_parser("tick", help="run one bounded unit of work (what cron invokes)")
    tick.set_defaults(func=cmd_tick)

    status = sub.add_parser("status", help="is it alive, and is anything stuck")
    status.add_argument("--json", action="store_true", help="machine-readable output")
    status.set_defaults(func=cmd_status)

    init = sub.add_parser("init", help="create the database and apply migrations")
    init.set_defaults(func=cmd_init)

    directive = sub.add_parser("directive", help="drop direction into the inbox")
    directive.add_argument("text", help="what the director wants")
    directive.add_argument(
        "--kind",
        default=DirectiveKind.TONE_NOTE.value,
        choices=[kind.value for kind in DirectiveKind],
    )
    directive.set_defaults(func=cmd_directive)

    directives = sub.add_parser("directives", help="list captured direction")
    directives.add_argument(
        "--status",
        default=DirectiveStatus.RECEIVED.value,
        choices=[state.value for state in DirectiveStatus],
    )
    directives.set_defaults(func=cmd_directives)

    jobs = sub.add_parser("jobs", help="queue depth, or the units in one status")
    jobs.add_argument("--status", choices=[state.value for state in JobStatus])
    jobs.set_defaults(func=cmd_jobs)

    revive = sub.add_parser("revive", help="return a parked unit to the queue")
    revive.add_argument("job_id")
    revive.set_defaults(func=cmd_revive)

    enqueue = sub.add_parser("enqueue", help="queue a scene draft")
    enqueue.add_argument("job_id")
    enqueue.add_argument("--revision", required=True)
    enqueue.add_argument("--node", required=True, help="logical id of the node to draft")
    enqueue.add_argument("--prompt", required=True)
    enqueue.add_argument("--priority", type=int, default=0)
    enqueue.set_defaults(func=cmd_enqueue)

    pause = sub.add_parser("pause", help="stop doing work; ticks still record")
    pause.set_defaults(func=cmd_pause)

    resume = sub.add_parser("resume", help="undo pause")
    resume.set_defaults(func=cmd_resume)

    backup = sub.add_parser("backup", help="online backup (safe while ticking)")
    backup.add_argument("destination", type=Path)
    backup.set_defaults(func=cmd_backup)

    verify = sub.add_parser("verify", help="rebuild every revision from canonical records")
    verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result: int = args.func(args)
        return result
    except MigrationsMissing as error:
        print(f"litharness: {error}", file=sys.stderr)
        return EXIT_FAULT
    except (OSError, FileExistsError, ValueError) as error:
        # Operational faults — a locked or missing database, a backup destination that
        # already exists, a bad argument. Distinguished from EXIT_ATTENTION because a
        # supervisor should retry these next cadence rather than surface them as the
        # system reporting on its work.
        print(f"litharness: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FAULT


if __name__ == "__main__":  # pragma: no cover - exercised via __main__.py
    raise SystemExit(main())
