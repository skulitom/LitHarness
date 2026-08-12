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

import litharness_contracts as lc

from litharness.adapters import contracts_fixtures
from litharness.adapters.sqlite_store import MigrationsMissing, SqliteStore
from litharness.application import status as status_module
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.domain.budget import BudgetPolicy
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus, directive_id_for
from litharness.domain.events import Event, EventType
from litharness.domain.exceptions import ExceptionStatus
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.policy import Outcome, PolicyDecision, decision_id_for
from litharness.domain.revision import import_manuscript
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


def _budget(args: argparse.Namespace) -> BudgetPolicy:
    """Ceilings from the command line, defaulting to `BudgetPolicy`'s.

    Passing 0 for a ceiling means "refuse everything" and is useful for a dry run; passing
    -1 means unbounded, which has to be *asked for* rather than being what you get by
    forgetting a flag.
    """

    def ceiling(value: int | None) -> int | None:
        return None if value is not None and value < 0 else value

    default = BudgetPolicy()
    return BudgetPolicy(
        max_tokens_per_operation=ceiling(
            args.max_tokens_per_operation
            if args.max_tokens_per_operation is not None
            else default.max_tokens_per_operation
        ),
        max_tokens_per_day=ceiling(
            args.max_tokens_per_day
            if args.max_tokens_per_day is not None
            else default.max_tokens_per_day
        ),
        max_invocations_per_day=ceiling(
            args.max_invocations_per_day
            if args.max_invocations_per_day is not None
            else default.max_invocations_per_day
        ),
        max_cost_usd_per_day=args.max_cost_usd_per_day,
    )


def _conductor(store: SqliteStore, args: argparse.Namespace) -> Conductor:
    registry = build_default_registry()
    return Conductor(
        store=store,
        holder=args.holder,
        project_id=args.project,
        registry=registry,
        handlers={
            SCENE_DRAFT: make_scene_draft_handler(
                registry, store, args.project, budget=_budget(args)
            ),
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
        report = status_module.collect(store, _now(), budget=_budget(args))
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


def cmd_exceptions(args: argparse.Namespace) -> int:
    """The queue §4.3 promised the director: what policy could not resolve."""
    store = _store(args)
    try:
        items = store.open_exceptions()
    finally:
        store.close()
    for item in items:
        print(f"{item.exception_id}  {item.kind.value:<22} job={item.job_id}")
        print(f"    {item.summary}")
    print(f"({len(items)} open)")
    return EXIT_ATTENTION if items else EXIT_OK


def cmd_resolve(args: argparse.Namespace) -> int:
    """Close the human's side. Deliberately does not requeue the unit — `revive` does that,
    because a director may decide the escalation was right and the work should stay
    stopped."""
    store = _store(args)
    try:
        closed = store.resolve_exception(
            args.exception_id,
            args.resolution,
            at=_stamp(_now()),
            status=ExceptionStatus.DISMISSED if args.dismiss else ExceptionStatus.RESOLVED,
        )
    finally:
        store.close()
    print(f"{closed.status.value} {closed.exception_id}")
    if closed.job_id:
        print(f"  the unit stays parked; `litharness revive {closed.job_id}` to requeue it")
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


def cmd_revert(args: argparse.Namespace) -> int:
    """Restore an earlier revision's content as a new head (§19 reversibility).

    Forward, never backward: the mistake and the correction both stay in the record.
    """
    store = _store(args)
    try:
        reverted = store.revert(
            args.book, args.branch, args.revision, created_at=_stamp(_now())
        )
    finally:
        store.close()
    print(f"reverted to {args.revision[:12]} as new head {reverted.revision_id[:12]}")
    return EXIT_OK


def cmd_import(args: argparse.Namespace) -> int:
    """Put a book into the store. Until this existed, nothing could.

    The system was a closed loop with no entry: `enqueue` requires `--revision`, a revision
    id is minted only by committing a revision, and the only caller of `commit_revision`
    outside the store was the draft handler — which needs a job, which needs the revision id
    nothing could produce. Every other operator verb here acts on a book that no command
    could create.

    The revision id is printed because it is the argument the next command takes.
    """
    path = args.path or contracts_fixtures.fixture_manuscript(args.fixture)
    # Explicit UTF-8. The default encoding on this platform is cp1252, which turns every
    # em-dash in the litrpg fixture into three characters; the node hash check catches it,
    # but as a corruption report about a file that is not corrupt.
    source = lc.parse_artifact(lc.ManuscriptRevision, json.loads(path.read_text(encoding="utf-8")))
    imported = import_manuscript(source, preserve_content=args.keep_content)
    revision = imported.revision
    stamp = _stamp(_now())

    # §19: every mutation is attributable to a recorded policy decision. An import is a
    # director's act rather than a gated one, so the decision carries no gate results — the
    # only checks that ran (a root-revision requirement, a per-node content hash) raise
    # before a decision exists, and recording them as passed would be a gate that cannot
    # fail. Keyed on the *resulting* revision so re-importing identical content collapses
    # onto one decision while a different import still gets its own.
    decision = PolicyDecision(
        decision_id=decision_id_for(f"import:{revision.revision_id}", 0, ()),
        outcome=Outcome.ACCEPT,
        resulting_revision_id=revision.revision_id,
        reason=f"imported from {imported.source_revision_id} ({path.name})",
    )
    accepted = Event(
        event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
        project_id=args.project,
        created_at=stamp,
        actor=args.holder,
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        revision_id=revision.revision_id,
        payload={
            "decision_id": decision.decision_id,
            "imported": True,
            "source_revision_id": imported.source_revision_id,
            "nodes": len(revision.nodes),
            "cleared": list(imported.cleared),
            "kept_locked": list(imported.kept_locked),
        },
    )

    store = _store(args)
    try:
        # Decision first, then the revision — the same order as the draft handler, for the
        # same reason: a crash between them leaves a decision pointing at a revision that
        # does not exist, which is detectable and harmless, rather than a revision no
        # decision explains, which is the thing §19 forbids.
        store.record_decision(decision, decided_at=stamp)
        store.commit_revision(revision, created_at=stamp, events=[accepted])
    finally:
        store.close()

    print(revision.revision_id)
    print(f"  book={revision.book_id} branch={revision.branch_id}")
    print(f"  {len(revision.nodes)} node(s) from {imported.source_revision_id[:12]}")
    print(f"  {len(imported.cleared)} scene(s) cleared and draftable")
    if imported.kept_locked:
        print(
            f"  {len(imported.kept_locked)} scene(s) left intact by a content lock and "
            f"NOT draftable: {', '.join(imported.kept_locked)}"
        )
    if args.keep_content:
        print("  --keep-content: no scene is draftable; a draft may only fill an empty node")
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
        "--max-tokens-per-operation", type=int, default=None,
        help="refuse one call projected above this; -1 for unbounded",
    )
    parser.add_argument(
        "--max-tokens-per-day", type=int, default=None,
        help="daily token ceiling; -1 for unbounded",
    )
    parser.add_argument(
        "--max-invocations-per-day", type=int, default=None,
        help="daily call ceiling — the one tokens cannot express (§15); -1 for unbounded",
    )
    parser.add_argument(
        "--max-cost-usd-per-day", type=float, default=None,
        help="daily dollar ceiling; applies only where the provider reports cost",
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

    exceptions = sub.add_parser("exceptions", help="what policy could not resolve")
    exceptions.set_defaults(func=cmd_exceptions)

    resolve = sub.add_parser("resolve", help="close an exception (does not requeue the unit)")
    resolve.add_argument("exception_id")
    resolve.add_argument("resolution", help="what you did about it")
    resolve.add_argument(
        "--dismiss", action="store_true",
        help="close without action: the escalation was right and the unit stays stopped",
    )
    resolve.set_defaults(func=cmd_resolve)

    pause = sub.add_parser("pause", help="stop doing work; ticks still record")
    pause.set_defaults(func=cmd_pause)

    resume = sub.add_parser("resume", help="undo pause")
    resume.set_defaults(func=cmd_resume)

    revert = sub.add_parser("revert", help="restore an earlier revision as the new head")
    revert.add_argument("revision", help="revision id to restore")
    revert.add_argument("--book", required=True)
    revert.add_argument("--branch", required=True)
    revert.set_defaults(func=cmd_revert)

    importer = sub.add_parser(
        "import", help="put a book into the store — the only command that creates a revision"
    )
    source = importer.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--fixture",
        choices=list(contracts_fixtures.FIXTURE_IDS),
        help="a golden book from the contracts checkout (§17 Stage 1 is graded on these)",
    )
    source.add_argument("--path", type=Path, help="a manuscript.json to import instead")
    importer.add_argument(
        "--keep-content",
        action="store_true",
        help="keep the source prose; the result has no draftable scene, so this is for "
        "inspection and not for generation",
    )
    importer.set_defaults(func=cmd_import)

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
