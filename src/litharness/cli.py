"""The operator surface: the session that drives ticks, and what a human runs to look inside.

One book runs as one foreground session driving `tick` in one process (stage-0 §57).
Ctrl+C is the pause; restarting is safe because ticks are idempotent and a job lease left
behind by a killed process expires and is reclaimed on the next tick.

**Exit codes are `tick`'s contract with whatever drives it.** 0 means the tick did what it
was asked, including finding nothing to do — a quiet system is a healthy one. 1 is
reserved for a unit that failed or parked, which is a fact a human should eventually see
but not an emergency. 2 is an operational fault: the database is locked, the migrations
are missing, the disk is full. A driver should retry 2 on the next iteration and never
treat it as the system reporting on its work.

The tick deliberately does **not** swallow storage errors. A locked database means another
writer is mid-flight, and the correct response is to exit and let the next iteration pick
it up — not to wait, and certainly not to force it.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters import contracts_fixtures, evaluation_artifact
from litharness.adapters.continuity_cli import ContinuityCliRunner
from litharness.adapters.sqlite_store import MigrationsMissing, SqliteStore, StoredEvent
from litharness.application import architect, comprehension, world_agent
from litharness.application import export as export_module
from litharness.application import library as library_module
from litharness.application import overview as overview_mod
from litharness.application import readers as readers_mod
from litharness.application import status as status_module
from litharness.application import world as world_mod
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.directive_planner import DIRECTIVE_PLAN, make_directive_plan_handler
from litharness.application.director import DIRECT, make_director_handler
from litharness.application.evaluation import (
    CompositeEvaluator,
    ContinuityEvaluator,
    Evaluator,
    InProcessEvaluator,
)
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.narrative_planner import (
    NARRATIVE_PLAN,
    make_narrative_plan_handler,
)
from litharness.application.outline import BOOK_OUTLINE, make_outline_handler
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.planner import make_plan_selector
from litharness.application.repair import (
    EVALUATE_REVISION,
    REPAIR_FINDING,
    SCENE_SUMMARY,
    evaluation_job_for,
    make_evaluation_handler,
    make_repair_handler,
)
from litharness.application.summarize import make_summary_handler
from litharness.domain import characters as characters_mod
from litharness.domain import directors as directors_domain
from litharness.domain import extraction, house, propagation
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_domain
from litharness.domain import writers as writers_domain
from litharness.domain.beats import SIX_BEAT, arc_template, beats_for
from litharness.domain.budget import BudgetPolicy, Spend
from litharness.domain.budget import check as budget_check
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus, directive_id_for
from litharness.domain.draft import DraftPolicy
from litharness.domain.events import Event, EventType
from litharness.domain.exceptions import ExceptionStatus
from litharness.domain.failures import OperationalFailure
from litharness.domain.findings import Finding
from litharness.domain.findings import Status as finding_status
from litharness.domain.generation import CompletionRequest, CompletionResult
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plan_refinement import (
    PlanProposalStatus,
    StoredPlanProposal,
    rollback_proposal,
)
from litharness.domain.plans import import_plan, premise_of, scene_plan_for
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decision_id_for,
)
from litharness.domain.promises import Promise, normalise_kind, promise_id_for
from litharness.domain.revision import Revision, import_manuscript, new_book
from litharness.domain.state import import_state
from litharness.providers import ProviderRegistry, build_default_registry

#: Exit codes, which are how whatever drives `tick` reads the outcome. See the module
#: docstring.
EXIT_OK = 0
EXIT_ATTENTION = 1
EXIT_FAULT = 2

DEFAULT_DB = "litharness.db"

#: Where `--database` looks when nobody passed one. **This exists so an agent's command line
#: can be exactly `litharness world <view>`**: a tool allowance is only a containment if it
#: can be written narrowly, and `Bash(litharness world:*)` stops being narrow the moment a
#: `--database` flag has to sit between the binary and the subcommand. The flag still wins
#: where it is given, so every existing invocation is unchanged.
DATABASE_ENV = "LITHARNESS_DATABASE"


def _now() -> float:
    return time.time()


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _env_flag(name: str) -> bool:
    """A boolean from the environment, for a flag a machine should be able to set once.

    A cron entry does not pass flags; it inherits an environment. Only a true-saying
    value is true — an unset variable and `=maybe` are both "no", because a flag that
    read any non-empty string as true would make `=0` mean yes.
    """
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _store(args: argparse.Namespace) -> SqliteStore:
    return SqliteStore.open(args.database)


def _draft_policy(args: argparse.Namespace) -> DraftPolicy:
    """Generation policy from the command line, defaulting to `DraftPolicy`'s.

    Only the target is exposed. The shape bounds are gates, and §1a.1's warning applies to
    both directions — an operator who could lower `min_chars` to make a run go green would
    have turned the one deterministic check on drafts into a formality.
    """
    default = DraftPolicy()
    return DraftPolicy(
        target_words=(
            args.target_words if args.target_words is not None else default.target_words
        )
    )


def _budget(args: argparse.Namespace) -> BudgetPolicy:
    """Ceilings from the command line, defaulting to `BudgetPolicy`'s.

    Passing 0 for a ceiling means "refuse everything" and is useful for a dry run; passing
    -1 means unbounded, which has to be *asked for* rather than being what you get by
    forgetting a flag.
    """

    def ceiling(value: float | None) -> Any:
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
        # **`-1` has to mean the same thing on every ceiling.** This one alone was passed
        # through raw, so the documented idiom for "unbounded" set a ceiling of -$1.00 —
        # and `check` refuses on `spent >= ceiling`, so $0.00 spent meets it and *every*
        # call is refused on the first tick. An operator following the README to disable
        # the dollar ceiling stopped the system dead instead.
        max_cost_usd_per_day=ceiling(args.max_cost_usd_per_day),
    )


def _director_id(store: SqliteStore, args: argparse.Namespace) -> str:
    """Resolve `--director` to a registered personality's id, or the empty string.

    Accepts a name or an id, because an operator types a name and the store keys on a content
    address. **An unregistered name is refused loudly rather than defaulted to no director**: a
    typo that silently produced the control arm would be the worst possible failure for an
    experiment whose whole question is whether the arms differ.
    """
    wanted = (getattr(args, "director", "") or "").strip()
    if not wanted:
        return ""
    for director in store.directors():
        if wanted in {director.name, director.director_id}:
            return director.director_id
    raise SystemExit(
        f"litharness: no director {wanted!r} is registered. Admitting a personality is an "
        "operator act — `litharness directors --register <name>` — and a typo here would "
        "silently give you the no-director control arm"
    )


def _conductor(store: SqliteStore, args: argparse.Namespace) -> Conductor:
    # The pinned provider, or the padded fake when LITHARNESS_FAKE_PAD_CHARS asks for a
    # model-free run. No selection flags survive provider plurality: an unhealthy
    # provider parks the unit, it never degrades the book.
    registry = build_default_registry()
    evaluators: list[Evaluator] = [InProcessEvaluator()]
    if args.continuity_evaluator_command:
        evaluators.append(
            ContinuityEvaluator(
                ContinuityCliRunner((str(args.continuity_evaluator_command),)),
                args.project,
            )
        )
    evaluator: Evaluator = (
        evaluators[0] if len(evaluators) == 1 else CompositeEvaluator(evaluators)
    )
    return Conductor(
        store=store,
        holder=args.holder,
        project_id=args.project,
        registry=registry,
        # §4.1's "work selection is a policy over the book's state", replacing the FIFO
        # placeholder. It drains the queue first, so retries and hand-enqueued work still
        # outrank planning; only when nothing is claimable does it materialise a beat.
        select=make_plan_selector(
            project_id=args.project,
            policy=_draft_policy(args),
            outline=not args.no_outline,
            director_id=_director_id(store, args),
            # The shape the operator asked for. At the default of one it asserts
            # nothing and the prompt is unchanged.
            scenes_per_chapter=args.chapter_scenes,
            **(
                {"token_budget": args.context_budget}
                if args.context_budget is not None
                else {}
            ),
        ),
        handlers={
            DIRECTIVE_PLAN: make_directive_plan_handler(store, args.project, actor=args.holder),
            # The Director role. Registered unconditionally — a kind with no queued work
            # costs nothing — while the *minting* sits behind `--director` above, which is
            # what keeps the personality operator-selectable and the no-director arm the
            # control (`plan/director-role.md` §6).
            DIRECT: make_director_handler(registry, store, args.project),
            NARRATIVE_PLAN: make_narrative_plan_handler(
                registry,
                store,
                args.project,
                budget=_budget(args),
                actor=args.holder,
            ),
            # **The policy has to reach the handler as well as the selector.** It reached
            # only the selector, so `--target-words 400` shaped the prompt while the handler
            # gated and recorded against `DraftPolicy()`'s 900: `policy_config_digest` cited
            # a target nobody asked for, and the accepted gate's detail read "N words against
            # a target of 900" for a run that asked for 400. The digest exists to make the
            # inputs that shaped a scene readable off the decision, and it was reporting a
            # different run's.
            SCENE_DRAFT: make_scene_draft_handler(
                registry,
                store,
                args.project,
                policy=_draft_policy(args),
                budget=_budget(args),
                schedule_evaluation=True,
                schedule_summary=True,
            ),
            # The producer for the context packet's evicted-scene slot. A mechanical call
            # class, so it routes to a local model even in production (§15), and the lowest
            # priority in the system, so it never outranks writing the next scene.
            SCENE_SUMMARY: make_summary_handler(registry, store, args.project),
            # Narrative Planning v0: one statement per scene, so the rising span stops
            # asking twenty-five scenes the same question (§52's first taxonomy entry).
            BOOK_OUTLINE: make_outline_handler(
                registry, store, args.project, budget=_budget(args), actor=args.holder
            ),
            EVALUATE_REVISION: make_evaluation_handler(
                evaluator, store, args.project
            ),
            REPAIR_FINDING: make_repair_handler(
                registry, store, args.project, budget=_budget(args)
            ),
        },
    )


# -- subcommands ----------------------------------------------------------------------


def cmd_tick(args: argparse.Namespace) -> int:
    """One bounded unit of work. This is what the session's loop invokes."""
    store = _store(args)
    loop = _conductor(store, args)
    published: tuple[Path, tuple[library_module.PublishedBook, ...]] | None = None
    try:
        result = loop.tick(_now())
        if not args.no_library:
            # **After the tick and inside the same store session, but outside anything the
            # tick commits.** The library is derived output: a filesystem failure here must
            # not fail a unit of work that already landed, and a republish that raced the
            # commit would show the previous revision. Suppressed rather than propagated for
            # the same reason — a full disk is a reason to stop publishing, not to stop
            # writing the book.
            with suppress(OSError):
                published = _publish_library(args, store)
    finally:
        store.close()

    print(f"{result.outcome.value} tick={result.tick_id}", end="")
    if result.job_id:
        print(f" job={result.job_id}", end="")
    print(f" reconciled={result.reconciled} ingested={result.ingested}")
    if published is not None:
        root, books = published
        moved = [book for book in books if book.rewritten]
        if moved:
            # Only when something was actually written. A line on every tick saying nothing
            # changed is a line nobody reads, and the whole point of the folder is that a
            # change is visible.
            print(
                f"  library: {root} · "
                + ", ".join(f"{book.title} {book.summary}" for book in moved)
            )
    if result.outcome in {TickOutcome.JOB_FAILED, TickOutcome.JOB_PARKED}:
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        report = status_module.collect(
            store,
            _now(),
            budget=_budget(args),
            # The CLI is the only caller that knows whether the sibling evaluator is wired,
            # so it is the only one that can report the pack being off.
            continuity_evaluator=args.continuity_evaluator_command is not None,
        )
    finally:
        store.close()

    print(json.dumps(report.as_dict(), indent=2) if args.json else report.render())
    return EXIT_OK


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
        book_id=args.book,
        branch_id=args.branch,
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
        # **Who wrote it, on every line.** A machine-authored directive that looked exactly
        # like a person's on the operator surface would be the listing half of the laundering
        # path the author column closed (`plan/director-role.md` §1).
        who = item.author or "human"
        print(
            f"{item.directive_id}  {item.kind.value:<14} p{item.precedence:<4} "
            f"{who:<28} {item.body}"
        )
    machine = sum(1 for item in items if directors_domain.is_machine_author(item.author))
    print(f"({len(items)} {args.status}, {machine} written by a director)")
    return EXIT_OK


def cmd_directors(args: argparse.Namespace) -> int:
    """The admitted personalities, or admit one.

    **Admission is an operator act**, for the reason §84 gives for fixture admission: a rule the
    code could apply is a rule somebody could satisfy without having done the work. The three
    built-ins are examples written to exercise the distinctness control, not recommendations —
    nothing here claims any of them is a good director.
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        if args.register:
            source = directors_domain.BUILTIN.get(args.register)
            if source is None and not args.brief:
                print(
                    f"litharness: {args.register!r} is not a built-in personality. Give "
                    "--brief to write one, or pick from: "
                    + ", ".join(sorted(directors_domain.BUILTIN)),
                    file=sys.stderr,
                )
                return EXIT_FAULT
            try:
                director = (
                    directors_domain.build(args.register, args.brief)
                    if args.brief is not None
                    # `source` is not None here: the branch above returned when a name is
                    # neither a built-in nor accompanied by a brief.
                    else source
                )
            except directors_domain.IllegalBrief as error:
                print(f"litharness: {error}", file=sys.stderr)
                return EXIT_FAULT
            assert director is not None
            fresh = store.record_director(director, registered_at=stamp)
            print(
                f"{director.director_id} {'admitted' if fresh else 'already admitted'} "
                f"as {director.name}"
            )
        admitted = store.directors()
        for director in admitted:
            print(f"{director.director_id}  {director.name}")
            print(f"  {director.brief}")
            if director.note:
                print(f"  ({director.note})")
        if not admitted:
            print("(no director admitted; the loop runs with no direction, which is the control)")
        print("  A brief says what the book is about, never what good prose is.")
    finally:
        store.close()
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


def _finding_row(item: Finding) -> dict[str, Any]:
    """One finding as an agent reads it. Shared by `findings --json` and the dossier, so
    the two verbs an agent chains cannot describe the same row differently."""
    return {
        "finding_id": item.finding_id,
        "severity": item.severity.value,
        "status": item.status.value,
        "blocks": item.blocks,
        "category": item.category,
        "subtype": item.subtype,
        "rule_or_critic_id": item.rule_or_critic_id,
        "logical_id": item.logical_id,
        "message": item.message,
        "deterministic": item.deterministic,
    }


def cmd_findings(args: argparse.Namespace) -> int:
    """What the evaluators say is wrong, worst first.

    Distinct from `exceptions`, and the distinction matters operationally: an exception is
    something *policy could not resolve* and is waiting on a human; a finding is something a
    *detector* reported, most of which policy resolves by itself with a retry. A director who
    had to read both queues the same way would stop reading either.
    """
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        items = store.findings(
            book_id, branch_id, logical_id=args.node, open_only=not args.all
        )
    finally:
        store.close()
    blocking = sum(1 for item in items if item.blocks)
    if args.json:
        print(
            json.dumps(
                {
                    "book_id": book_id,
                    "branch_id": branch_id,
                    "open_only": not args.all,
                    "findings": [_finding_row(item) for item in items],
                    "shown": len(items),
                    "blocking": blocking,
                },
                indent=2,
            )
        )
        return EXIT_ATTENTION if blocking else EXIT_OK
    for item in items:
        flag = "BLOCKS" if item.blocks else "      "
        print(
            f"{item.finding_id}  {flag}  {item.severity.value:<8} {item.status.value:<20} "
            f"{item.rule_or_critic_id or item.category}"
        )
        print(f"    {item.message}")
        if item.logical_id:
            print(f"    at {item.logical_id}")
    print(f"({len(items)} shown, {blocking} blocking)")
    return EXIT_ATTENTION if blocking else EXIT_OK


def cmd_ingest(args: argparse.Namespace) -> int:
    """Take an evaluator's findings into the store, which is how a sibling's detectors gate.

    §8.4 keeps the LitRPG rule and predicate vocabulary in ContinuityEvaluation, and §13 keeps
    siblings depending on contracts rather than on each other — so the integration is a file
    of a shared schema, read here. Re-ingesting the same artifact writes nothing: finding ids
    are content-derived and the insert ignores duplicates, so a detector re-run converges
    rather than growing the queue, and a status a human already set is not overwritten.
    """
    evaluation = evaluation_artifact.load_findings(args.path)
    run_id, findings = evaluation.run_id, evaluation.findings
    stamp = _stamp(_now())
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        written = store.record_findings(
            book_id,
            branch_id,
            findings,
            created_at=stamp,
            revision_id=head.revision_id if head else None,
            events=[
                Event(
                    event_type=EventType.EVALUATION_COMPLETED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=head.revision_id if head else None,
                    payload={
                        "run_id": run_id,
                        "findings": len(findings),
                        "blocking": sum(1 for item in findings if item.blocks),
                        "source": str(args.path),
                    },
                )
            ],
        )
    finally:
        store.close()
    blocking = sum(1 for item in findings if item.blocks)
    print(f"{run_id}: {len(findings)} finding(s), {written} new, {blocking} blocking")
    if blocking:
        print("  the gate refuses a candidate for the nodes these land on until they close")
    # **An incomplete evaluation is not a passing one**, and until this the two were
    # indistinguishable: a run whose every detector failed printed "0 finding(s), 0 new,
    # 0 blocking" and exited 0 over a book with six planted defects. The absence of a finding
    # from a run that did not finish is not evidence of absence.
    #
    # EXIT_ATTENTION, not EXIT_FAULT. Fault means "retry next cadence" and a detector that
    # could not resolve its evidence will fail identically on the next tick — the artifact
    # was read fine, the *evaluation* did not complete, and that is a fact about the book's
    # quality signal that a human should see. The findings that did arrive are still
    # ingested, because dropping them would trade one silent gap for another.
    if not evaluation.complete:
        print(
            f"  INCOMPLETE: {len(evaluation.errors)} detector error(s) — "
            f"{evaluation.summarise_errors()}",
            file=sys.stderr,
        )
        print(
            "  a clean result from an evaluation that did not finish is not a clean book",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_dismiss(args: argparse.Namespace) -> int:
    """Mark a finding intentional or false, so a deliberate device stops blocking.

    Both golden fixtures ship negative controls — the rain-on-glass motif, Julian's alibi —
    which a *correct* detector flags and a correct policy must not refuse forever. Without
    this verb the only way past one would be to weaken the detector, trading a true positive
    for a quiet queue.
    """
    status = (
        finding_status.FALSE_POSITIVE if args.false_positive
        else finding_status.ACCEPTED_INTENTIONAL
    )
    stamp = _stamp(_now())
    store = _store(args)
    try:
        changed = store.set_finding_status(
            args.finding_id,
            status,
            events=[
                Event(
                    event_type=EventType.FINDING_STATUS_CHANGED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    payload={"finding_id": args.finding_id, "status": status.value},
                )
            ],
        )
    finally:
        store.close()
    if not changed:
        print(f"litharness: no finding {args.finding_id}", file=sys.stderr)
        return EXIT_ATTENTION
    print(f"{args.finding_id} -> {status.value}")
    return EXIT_OK


#: Absences that mean the dossier could not answer the question it was asked, so `why`
#: exits non-zero on them.
#:
#: **The `verify` idiom, per scene.** `unattributed_revisions` exists because §19's integrity
#: clause was asserted rather than checked, and a forensic read needs the same discipline: a
#: dossier printing nothing where a decision belongs reads exactly like a scene that had no
#: decision to print. Every gap is named in the `absent` list; only these three mean the
#: question went unanswered. A book drafted with `--no-outline` has no plan statement,
#: which is not a fault — it is a fact about that book, printed and exit 0.
UNANSWERED = ("prose", "decision", "prompt")


def _gate_row(gate: GateOutcome) -> dict[str, Any]:
    """One rung of the ladder as stored. `_gate_to_row` in the store is the write side."""
    return {
        "gate": gate.gate.value,
        "rule_or_critic_id": gate.rule_or_critic_id,
        "passed": gate.passed,
        "blocking": gate.blocking,
        "verdict_source": gate.verdict_source.value,
        "vetoes": [veto.value for veto in gate.vetoes],
        "detail": gate.detail,
        "calibration_id": gate.calibration_id,
    }


def _decision_row(decision: PolicyDecision) -> dict[str, Any]:
    """One policy decision, whole. A refusal is carried as fully as an acceptance."""
    return {
        "decision_id": decision.decision_id,
        "outcome": decision.outcome.value,
        "attempt": decision.attempt,
        "job_id": decision.job_id,
        "logical_id": decision.logical_id,
        "base_revision_id": decision.base_revision_id,
        "resulting_revision_id": decision.resulting_revision_id,
        "provider": decision.provider,
        "model": decision.model,
        "profile": decision.profile,
        "fell_back_from": list(decision.fell_back_from),
        "invocations": decision.invocations,
        "total_tokens": decision.total_tokens,
        "cost_usd": decision.cost_usd,
        "policy_config_digest": decision.policy_config_digest,
        "reason": decision.reason,
        "gates": [_gate_row(gate) for gate in decision.gates],
    }


def _scenes_of(revision: Revision) -> list[Node]:
    return [
        node
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and not node.tombstoned
    ]


def _scene_node(head: Revision, wanted: str) -> Node | None:
    """The scene `--scene` names: a logical id, or a 1-based place in reading order.

    Both, because the two callers differ. A logical id is what every other verb prints and
    what an agent chains from; an ordinal is what a human reading the book has. `new_book`
    mints `scene-3`, so a digit resolves through that id first and falls back to counting —
    an imported book whose scenes are named otherwise still answers `--scene 3`.
    """
    scenes = _scenes_of(head)
    by_id = {node.logical_id: node for node in scenes}
    if wanted in by_id:
        return by_id[wanted]
    if wanted.isdigit():
        derived = f"scene-{int(wanted)}"
        if derived in by_id:
            return by_id[derived]
        index = int(wanted) - 1
        if 0 <= index < len(scenes):
            return scenes[index]
    return None


def _introduced_in(
    store: SqliteStore, head: Revision, logical_id: str
) -> tuple[str | None, int]:
    """The revision that put the head's current prose into this scene, and how deep it sits.

    Walked oldest-first along the lineage and remembered on every *change* of the node's
    content hash, so a scene a repair rewrote reports the repair rather than the first
    draft — the decision an operator wants is the one that produced the text they are
    reading. Revisions predating the node are skipped rather than assumed empty.
    """
    previous: str | None = None
    introduced: str | None = None
    depth = 0
    for index, revision_id in enumerate(reversed(store.lineage(head.revision_id))):
        try:
            node = store.load_revision(revision_id).node(logical_id)
        except KeyError:
            continue
        if node.content_sha256 != previous:
            previous = node.content_sha256
            if node.content:
                introduced, depth = revision_id, index + 1
    return introduced, depth


def _payload_prompt(job: Job | None) -> dict[str, Any] | None:
    """The frozen prompt off the job payload, or None when the unit carries no prose to send.

    A payload with no prompt is not always a defect — an evaluation unit has none at
    all —
    but for a scene dossier it is still a gap, which is why this returns None rather than an
    empty string and lets the caller record the absence.
    """
    if job is None:
        return None
    prompt = job.payload.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return None
    system = job.payload.get("system")
    return {"system": system if isinstance(system, str) else None, "prompt": prompt}


def _scene_dossier(
    store: SqliteStore, book_id: str, branch_id: str, node: Node, head: Revision
) -> dict[str, Any]:
    """Every stored row that explains one scene, joined, with the gaps named.

    **Nothing here is computed from the prose.** Every field is a column somebody wrote at
    the time, which is what makes the answer a record rather than a re-reading: the prompt is
    the one actually sent (frozen at enqueue, invariant I5), the gate ladder is the one that
    ran. A dossier that re-rendered the prompt from live tables would be answering a
    question about today.
    """
    logical_id = node.logical_id
    absent: list[str] = []
    introduced, depth = _introduced_in(store, head, logical_id)
    if introduced is None:
        absent.append("prose")

    decision = None if introduced is None else store.decision_for_revision(introduced)
    if introduced is not None and decision is None:
        absent.append("decision")

    job_id = decision.job_id if decision else None
    job: Job | None = None
    if job_id:
        with suppress(KeyError):
            job = store.load_job(job_id)
    prompt = _payload_prompt(job)
    if prompt is None:
        absent.append("prompt")

    payload: dict[str, Any] = dict(job.payload) if job is not None else {}
    plan_item = scene_plan_for(store.plan_items(book_id, branch_id), logical_id)
    if plan_item is None:
        absent.append("plan_item")

    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "logical_id": logical_id,
        "scene": {
            "title": node.title,
            "position_key": node.position_key,
            "accepted_in": introduced,
            "lineage_depth": depth or None,
            "head_revision_id": head.revision_id,
            "chars": len(node.content or ""),
            "content_sha256": node.content_sha256,
            "lock": node.lock.value,
        },
        "decision": _decision_row(decision) if decision else None,
        "attempts": [
            _decision_row(item) for item in (store.decisions_for_job(job_id) if job_id else [])
        ],
        "job": None
        if job is None
        else {
            "job_id": job.job_id,
            "job_kind": job.job_kind,
            "status": job.status.value,
            "attempts": job.attempts,
            "priority": job.priority,
            "input_digest": job.input_digest,
        },
        "prompt": prompt,
        "selected_by": payload.get("selected_by"),
        "context": payload.get("context"),
        "context_omitted": payload.get("context_omitted"),
        "plan_item": None
        if plan_item is None
        else {
            "plan_item_id": plan_item.logical_id,
            "text": plan_item.text,
            "locked": plan_item.locked,
            "authority": plan_item.authority.value,
        },
        "findings": [
            _finding_row(item)
            for item in store.findings(
                book_id, branch_id, logical_id=logical_id, open_only=False
            )
        ],
        "absent": absent,
    }


def _render_dossier(dossier: dict[str, Any]) -> str:
    """The same dict `--json` prints, as lines. One source, so the two cannot disagree."""
    scene: dict[str, Any] = dossier["scene"]
    lines = [
        f"{dossier['logical_id']}  {scene['title'] or '(untitled)'}  "
        f"[{dossier['book_id']}/{dossier['branch_id']}]"
    ]

    def field(label: str, value: str) -> None:
        lines.append(f"  {label:<13} {value}")

    # **An undrafted scene is a different report, not a report full of gaps.** Saying "no
    # policy decision explains this revision" of a scene that has no revision would send a
    # reader looking for an attribution failure that is not there; the scene simply has not
    # been written. `absent` already draws the line — the renderer has to draw it too.
    undrafted = scene["accepted_in"] is None
    if undrafted:
        field("prose", "ABSENT - no accepted revision carries this scene yet")
        field("decision", "n/a - nothing has been accepted here, so nothing decided it")
    else:
        field(
            "accepted in",
            f"{scene['accepted_in']}  (step {scene['lineage_depth']} of the lineage)",
        )
        field("prose", f"{scene['chars']} char(s), sha256 {scene['content_sha256']}")

    decision: dict[str, Any] | None = dossier["decision"]
    if decision is None and not undrafted:
        field(
            "decision",
            "ABSENT - no policy decision explains this revision (§19; `verify` counts these)",
        )
    elif decision is not None:
        cost = (
            "cost not reported"
            if decision["cost_usd"] is None
            else f"${decision['cost_usd']:.4f}"
        )
        field(
            "decision",
            f"{decision['decision_id']}  {decision['outcome']}  attempt {decision['attempt']}",
        )
        field(
            "",
            f"{decision['provider'] or '?'}/{decision['model'] or '?'}  "
            f"profile {decision['profile'] or '?'}",
        )
        field(
            "",
            f"{decision['invocations']} call(s), {decision['total_tokens']} token(s), {cost}",
        )
        field("", f"config {decision['policy_config_digest'] or '(none)'}")
        if decision["reason"]:
            field("", f"reason: {decision['reason']}")
        if not decision["gates"]:
            field("gates", "(none recorded on this decision)")
        for index, gate in enumerate(decision["gates"]):
            mark = "PASS" if gate["passed"] else "FAIL"
            weight = "blocking" if gate["blocking"] else "advisory"
            field(
                "gates" if index == 0 else "",
                f"{mark}  {gate['gate']:<10}{gate['rule_or_critic_id']:<26}"
                f"{gate['verdict_source']}  {weight}",
            )
            if gate["vetoes"]:
                field("", f"        vetoes: {', '.join(gate['vetoes'])}")
            if gate["detail"]:
                field("", f"        {gate['detail']}")

    attempts: list[dict[str, Any]] = dossier["attempts"]
    if len(attempts) > 1:
        # The ladder across attempts, not just the rung that landed. A scene accepted on the
        # third try was refused twice and those refusals are on record.
        ladder = ", ".join(f"{item['attempt']}:{item['outcome']}" for item in attempts)
        field("attempts", f"{len(attempts)} decision(s) on this job - {ladder}")

    job: dict[str, Any] | None = dossier["job"]
    if job is None:
        field("job", "ABSENT - no queued unit is on record for this scene")
    else:
        field(
            "job",
            f"{job['job_id']}  {job['job_kind']}  {job['status']}  "
            f"{job['attempts']} attempt(s)",
        )

    selected = dossier["selected_by"]
    if isinstance(selected, dict):
        field(
            "selected by",
            f"beat {selected.get('ordinal')}/{selected.get('of_total')} "
            f"{selected.get('beat_function')}  template {selected.get('template_id')}",
        )
        field(
            "",
            f"plan epoch {selected.get('plan_epoch')}  "
            f"predicate {selected.get('predicate')}  "
            f"story order {selected.get('story_order_key')}",
        )

    context = dossier["context"]
    if isinstance(context, dict):
        field(
            "context",
            f"{context.get('items')} item(s), {context.get('tokens')}/"
            f"{context.get('budget')} token(s)  query {context.get('query_id')}",
        )
        sections = context.get("sections")
        if isinstance(sections, dict) and sections:
            field(
                "", "  ".join(f"{name} {count}" for name, count in sorted(sections.items()))
            )

    omitted = dossier["context_omitted"]
    if isinstance(omitted, list):
        # **Printed even when empty.** This is the honest half of the packet: a baseline that
        # packs by priority rather than relevance drops things a scorer would have kept, and
        # a scene that ignores canon is usually a scene whose canon is on this list.
        field("omitted", f"{len(omitted)} context item(s) the packet could not hold")
        for item in omitted:
            if isinstance(item, dict):
                field("", f"  {item.get('source')}  {item.get('reason')}")

    plan_item = dossier["plan_item"]
    if plan_item is None:
        field("plan item", "ABSENT - the plan holds no statement for this scene")
    else:
        field(
            "plan item",
            f"{plan_item['plan_item_id']}  "
            f"{'locked' if plan_item['locked'] else 'unlocked'}  {plan_item['authority']}",
        )
        field("", plan_item["text"])

    findings: list[dict[str, Any]] = dossier["findings"]
    blocking = sum(1 for item in findings if item["blocks"])
    field("findings", f"{len(findings)} recorded, {blocking} blocking")
    for item in findings:
        field(
            "",
            f"  {item['finding_id']}  {item['severity']:<8}{item['status']:<20}"
            f"{item['rule_or_critic_id'] or item['category']}",
        )
        field("", f"    {item['message']}")

    if dossier["absent"]:
        field("absent", ", ".join(dossier["absent"]))

    prompt = dossier["prompt"]
    lines.append("")
    if prompt is None:
        lines.append("(no rendered prompt on record for this scene)")
    else:
        # **Last, and whole.** The prompt is the thing this verb exists to show and also the
        # longest thing here, so it follows the summary rather than burying it.
        lines.append(f"--- system ({len(prompt['system'] or '')} char(s)) ---")
        lines.append(prompt["system"] or "(none)")
        lines.append("")
        lines.append(f"--- prompt ({len(prompt['prompt'])} char(s)) ---")
        lines.append(prompt["prompt"])
    return "\n".join(lines)


def cmd_why(args: argparse.Namespace) -> int:
    """Every stored row that explains one scene, joined into one dossier.

    **The read side of provenance the write side has always kept.** The rendered prompt is
    frozen on the job payload at enqueue and every attempt has a policy decision — and
    none of it was printed by any command, so the only way to look at any of it was to
    open the SQLite file. That is the
    entry §31 closed for plans and §39 closed for state, closed here for prompts and
    decisions.

    Read-only and fenced. `plan/serial-pilot-1.md` §6 keeps diagnostics on the operator's
    side of the loop, so nothing this prints is a channel back into generation: it answers a
    question and never carries an answer.
    """
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        if head is None:
            print(f"litharness: no head for {book_id}/{branch_id}", file=sys.stderr)
            return EXIT_ATTENTION
        node = _scene_node(head, args.scene)
        if node is None:
            known = ", ".join(item.logical_id for item in _scenes_of(head)) or "(none)"
            print(
                f"litharness: no scene {args.scene} in this book. Known scenes: {known}",
                file=sys.stderr,
            )
            return EXIT_ATTENTION
        dossier = _scene_dossier(store, book_id, branch_id, node, head)
    finally:
        store.close()

    print(json.dumps(dossier, indent=2) if args.json else _render_dossier(dossier))
    return EXIT_ATTENTION if set(dossier["absent"]) & set(UNANSWERED) else EXIT_OK


def _event_row(stored: StoredEvent) -> dict[str, Any]:
    return {
        "sequence": stored.sequence,
        "event_type": stored.event.event_type.value,
        "created_at": stored.event.created_at,
        "actor": stored.event.actor,
        "book_id": stored.event.book_id,
        "branch_id": stored.event.branch_id,
        "revision_id": stored.event.revision_id,
        "causation_id": stored.event.causation_id,
        "correlation_id": stored.event.correlation_id,
        "payload": stored.event.payload,
    }


def cmd_events(args: argparse.Namespace) -> int:
    """The event log in the order it was written: what happened, across every table.

    `migrations/021_foreground_loop.sql` calls this table the provenance record and the store
    writes it in the same transaction as every state change it describes, so it is the one
    view that crosses jobs, decisions, plans and findings without a join. It had no reader at
    all — `read_log` was called only by the suite.

    `--since` takes either the sequence the store orders on, which the trailing cursor line
    prints, or an ISO-8601 instant compared against the stamp. The stamps are Z-normalised,
    so a prefix like 2026-08-13 is a valid one. Output is bounded by `--limit` and the cursor
    says where to resume, because an agent reading a long log needs both.
    """
    store = _store(args)
    try:
        since = int(args.since) if args.since and args.since.isdigit() else 0
        stored = store.read_log(since=since)
    finally:
        store.close()

    if args.since and not args.since.isdigit():
        stored = [item for item in stored if item.event.created_at >= args.since]
    wanted = set(args.type or ())
    if wanted:
        stored = [item for item in stored if item.event.event_type.value in wanted]
    if args.book:
        stored = [item for item in stored if item.event.book_id == args.book]
    matched = len(stored)
    shown = stored if args.limit <= 0 else stored[: args.limit]
    cursor = shown[-1].sequence if shown else since

    if args.json:
        print(
            json.dumps(
                {
                    "events": [_event_row(item) for item in shown],
                    "matched": matched,
                    "shown": len(shown),
                    "next_since": cursor,
                },
                indent=2,
            )
        )
        return EXIT_OK

    for item in shown:
        event = item.event
        scope = event.revision_id or event.book_id or "-"
        print(
            f"{item.sequence:>6}  {event.created_at}  {event.event_type.value:<28}"
            f"{event.actor:<12}{scope}"
        )
        if event.payload:
            rendered = json.dumps(event.payload, sort_keys=True, ensure_ascii=False)
            if len(rendered) > 96:
                rendered = f"{rendered[:96]}... (--json carries it whole)"
            print(f"        {rendered}")
    if not shown:
        # An empty log and a filter that matched nothing look identical otherwise, and they
        # are different answers to "what happened".
        print("(no event matches; nothing was written, or nothing was filtered in)")
        return EXIT_OK
    print(f"({len(shown)} of {matched} matching event(s); next --since {cursor})")
    return EXIT_OK


def cmd_replan(args: argparse.Namespace) -> int:
    """Reissue every still-draftable beat of a book under a fresh plan epoch.

    **Named by two docstrings and a migration comment before it existed.**
    `handlers._stale_base` says "clearing it is an operator act — `replan` mints fresh work
    against the current head", and migration 011 says "bumping the epoch changes every
    derived id for the book, so `replan` reissues exactly the beats that are still
    draftable". `bump_plan_epoch` had one caller and it was a test. This is the same defect
    family as `ProviderRegistry.reset_health`, which documented "called at the start of a
    tick" and had no non-test caller until slice 4 — a promise in prose that nothing kept.

    It is the recovery verb for the two states `revive` cannot reach. A **poisoned** unit
    spent its attempt budget and burned its derived id forever; a **parked** unit whose head
    has since moved would be revived onto a stale base and escalate. Bumping the epoch
    changes every derived id for the book, so the next tick plans the still-empty beats
    afresh against the current head and silently skips the ones already drafted — because
    "draftable" is derived from the manuscript, not from a status column that could disagree
    with it.

    It does **not** clear what stopped the work. A beat blocked by a finding will block again
    on the next attempt unless the finding is dismissed first; this reissues the unit, it
    does not overrule the gate.
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        epoch = store.bump_plan_epoch(
            book_id, branch_id, at=stamp, reason=args.reason or "replan"
        )
        head = store.head(book_id, branch_id)
        blocking = [
            item
            for item in store.findings(book_id, branch_id, open_only=True)
            if item.blocks
        ]
        store.append_events(
            [
                Event(
                    event_type=EventType.PLAN_CHANGED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=head.revision_id if head else None,
                    payload={"plan_epoch": epoch, "reason": args.reason or "replan"},
                )
            ]
        )
    finally:
        store.close()
    print(f"plan epoch {epoch}; still-draftable beats will be reissued on the next tick")
    if blocking:
        print(
            f"  {len(blocking)} blocking finding(s) remain — reissued work will be refused "
            "again until they are dismissed or repaired"
        )
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_readers(args: argparse.Namespace) -> int:
    """Put the simulated readership on a drafted scene, and record what it did.

    Two lanes over one chapter. The measurement pool spends a reading budget and either
    carries on, puts it down, or comes back later; the steering pool says what it is hoping
    happens next. Nobody is in both, so what steers the next chapter is never what measured
    this one.

    The hopes reach the writer by themselves: `planner.direction_for` reads them off this
    store on the next draft. Nothing here writes a prompt.
    """
    store = _store(args)
    stamp = _stamp(_now())
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        if head is None:
            print("litharness: this branch has no revision", file=sys.stderr)
            return EXIT_FAULT
        node = head.node(args.scene) if args.scene else None
        if node is None:
            drafted = [
                item
                for item in head.nodes
                if item.kind is NodeKind.SCENE and (item.content or '').strip()
            ]
            if not drafted:
                print("no drafted scene to read")
                return EXIT_OK
            node = drafted[-1]
        chapter = (node.content or '').strip()
        if not chapter:
            print(f"litharness: {node.logical_id} has no prose", file=sys.stderr)
            return EXIT_FAULT

        registry = build_default_registry()
        spend = _StageSpend()
        # `_forge_call` adds to the stage tally AND to `run`, so they must be different
        # objects or every call is counted twice — which it was, on the first live run.
        calls = _ForgeCalls(
            registry=registry, store=store, args=args, stamp=stamp,
            run=_StageSpend(), premise=spend, screen=spend,
        )

        choices: dict[str, Any] = {}
        wishes: dict[str, Any] = {}
        for reader in readers_mod.READERS:
            if reader.pool == readers_mod.MEASUREMENT:
                request = readers_mod.render_choice_request(reader, chapter)
            else:
                request = readers_mod.render_anticipation_request(reader, chapter)
            result, refusal = _forge_call(request, calls=calls, spend=spend)
            parsed = result.parsed if result is not None else None
            if not isinstance(parsed, Mapping):
                if refusal:
                    print(f"  {reader.reader_id}: {refusal}", file=sys.stderr)
                continue
            if reader.pool == readers_mod.MEASUREMENT:
                choices[reader.reader_id] = parsed
                store.record_reader_read(
                    book_id, branch_id, head.revision_id, node.logical_id,
                    reader_id=reader.reader_id, pool=reader.pool, created_at=stamp,
                    choice=str(parsed.get("next") or ""),
                    because=str(parsed.get("because") or ""),
                )
            else:
                wishes[reader.reader_id] = parsed
                store.record_reader_read(
                    book_id, branch_id, head.revision_id, node.logical_id,
                    reader_id=reader.reader_id, pool=reader.pool, created_at=stamp,
                    hoping_for=[str(x) for x in (parsed.get("hoping_for") or [])],
                    dreading=[str(x) for x in (parsed.get("dreading") or [])],
                )

        reading = readers_mod.Reading.of(choices)
        wanting = readers_mod.Anticipation.of(wishes)
        gates = (
            GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id=readers_mod.CONTINUE_PROFILE,
                passed=True,
                blocking=False,
                detail=(
                    f"{node.logical_id}: {reading.carried_on} of "
                    f"{reading.answered} carried on"
                ),
            ),
        )
        store.record_decision(
            PolicyDecision(
                decision_id=decision_id_for(f"read:{head.revision_id}:{node.logical_id}", 0, gates),
                outcome=Outcome.ACCEPT,
                gates=gates,
                profile=readers_mod.CONTINUE_PROFILE,
                provider=spend.provider,
                model=spend.model,
                invocations=spend.invocations,
                total_tokens=spend.total_tokens,
                cost_usd=spend.cost_usd,
                reason="the simulated readership read one chapter; nothing here ranks or refuses",
            ),
            decided_at=stamp,
        )
    finally:
        store.close()

    print(f"{node.logical_id}")
    print(
        f"  carried on {reading.carried_on}/{reading.answered}"
        f"  put down {reading.put_down}  later {reading.come_back}"
    )
    for reader_id, choice, because in reading.said:
        print(f"    {reader_id}: {choice} - {because}")
    if wanting.hoping_for:
        print("  hoping for:")
        for item in wanting.hoping_for:
            print(f"    - {item}")
    if wanting.dreading:
        print("  would be disappointed by:")
        for item in wanting.dreading:
            print(f"    - {item}")
    return EXIT_OK

def cmd_characters(args: argparse.Namespace) -> int:
    """Everything canon holds about each person, one sheet each.

    The writer's own view, printed. `state` shows the rows; this shows the people they add
    up to — what somebody is, wants, sounds like, can do, where they stand, and who does
    what about them. `--csv` writes the same thing as a table to open in a spreadsheet.
    """
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        records = store.state_records(book_id, branch_id)
    finally:
        store.close()

    people = characters_mod.cast(records)
    if args.subject:
        people = tuple(c for c in people if c.subject == args.subject)
    if not people:
        print("no cast on record for this branch")
        print("  a world reaches canon through `forge --pick`, then `new --state`")
        return EXIT_OK

    if args.csv:
        rows = characters_mod.rows(people)
        with args.csv.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{len(rows)} character(s) -> {args.csv}")
        return EXIT_OK

    if args.json:
        print(json.dumps([c.to_jsonable() for c in people], ensure_ascii=False, indent=2))
        return EXIT_OK

    print(characters_mod.render(people))
    return EXIT_OK

def _scalar(text: str | None) -> object:
    """A `--value` as the type it plainly is: 34 is a number, everything else is prose.

    **Written because a 317-record world had every one of its reveal scenes stored as
    `"34"`.** argparse hands over text, the store JSON-encodes what it is given, and
    `worlds.reveal_scenes` keeps only genuine ints — so fifteen scheduled disclosures were
    invisible and nothing complained, because a reveal that does not parse looks exactly
    like a reveal nobody scheduled.

    Only scalars are coerced, so no sentence is at risk: `json.loads` on prose raises and
    the text is kept. A value that really is meant to be the string `34` is written
    `--value '\"34\"'`, which is the only case this changes and the rarer one by far.
    """
    if text is None:
        return None
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    return parsed if isinstance(parsed, int | float | bool) else text

def _read_text(source: str) -> str:
    """A file's text, or stdin for `-`. The listing is prose and prose lives in files."""
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def cmd_architect(args: argparse.Namespace) -> int:
    """Put the Architect on this book's world, holding the world suite and nothing else.

    **An agent, because a world is not a thing you fill in once.** The operator, 2026-08-24:
    *"in what world would a one-shot structured call be a good idea for writing a book... The
    world would obviously evolve and grow with every chapter"*. `seed` builds enough world to
    stand the first chapters under a listing readers have already been shown; `grow` runs after
    a chapter and keeps the world holding — what the chapter established, what now contradicts,
    and what was declared and has still never been said.

    **What it can do is the allowance and not a promise.** `world_agent.ALLOWED_TOOLS` is
    `Bash(litharness world:*)`: this agent runs the world suite and has no other tool. Every
    record it writes is PROPOSED, so it proposes a world and cannot install one — `world accept`
    is the separate act that carries a decision row.

    The database reaches the child through `LITHARNESS_DATABASE`, which is why that variable
    exists: a `--database` flag between the binary and the subcommand would force the allowance
    to widen to every command this CLI has.
    """
    database = str(Path(args.database).resolve())
    os.environ[DATABASE_ENV] = database

    writer = writers_domain.CAST.get(args.writer) if args.writer else None
    if args.writer and writer is None:
        print(
            f"litharness: no writer named {args.writer!r}; the cast is "
            f"{', '.join(writers_domain.CAST)}",
            file=sys.stderr,
        )
        return EXIT_FAULT

    store = _store(args)
    stamp = _stamp(_now())
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        before = len(store.state_records(book_id, branch_id))
        if args.job == "seed":
            overview = _read_text(args.overview)
            if not overview.strip():
                print("litharness: an empty listing is nothing to build on", file=sys.stderr)
                return EXIT_FAULT
            request = world_agent.render_seed_request(overview, writer)
        else:
            head = store.head(book_id, branch_id)
            if head is None:
                print("litharness: this branch has no revision", file=sys.stderr)
                return EXIT_FAULT
            node = head.node(args.scene) if args.scene else None
            if node is None:
                drafted = [
                    item
                    for item in head.nodes
                    if item.kind is NodeKind.SCENE and (item.content or "").strip()
                ]
                if not drafted:
                    print("no drafted scene for the Architect to read")
                    return EXIT_OK
                node = drafted[-1]
            request = world_agent.render_grow_request(
                node.content or "", logical_id=node.logical_id, writer=writer
            )

        registry = build_default_registry()
        spend = _StageSpend()
        calls = _ForgeCalls(
            registry=registry, store=store, args=args, stamp=stamp,
            run=spend, premise=spend, screen=spend,
        )
        result, refusal = _forge_call(request, calls=calls, spend=spend)
        if result is None:
            print(f"litharness: {refusal}", file=sys.stderr)
            return EXIT_FAULT

        after = store.state_records(book_id, branch_id)
        proposed = sum(
            1 for record in after if record.authority is lc.StateAuthority.PROPOSED
        )
        complaints = worlds_domain.validate(after)
        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id=request.profile,
            passed=not complaints,
            blocking=False,
            detail=(
                f"{len(after) - before} record(s) added; {proposed} proposed; "
                f"{len(complaints)} complaint(s)"
            ),
        )
        store.record_decision(
            PolicyDecision(
                decision_id=decision_id_for(
                    f"architect:{args.job}:{book_id}:{branch_id}:{stamp}", 0, (gate,)
                ),
                outcome=Outcome.ACCEPT,
                gates=(gate,),
                profile=request.profile,
                provider=spend.provider,
                model=spend.model,
                invocations=spend.invocations,
                total_tokens=spend.total_tokens,
                cost_usd=spend.cost_usd,
                reason=(
                    "the Architect worked the world through its own commands; every record "
                    "it wrote is a proposal"
                ),
            ),
            decided_at=stamp,
        )
    finally:
        store.close()

    print(result.text.strip())
    print()
    print(f"  {len(after) - before} record(s) added, {proposed} awaiting `world accept`")
    for complaint in complaints:
        print(f"  ! {complaint}")
    return EXIT_OK


def cmd_prompts(args: argparse.Namespace) -> int:
    """Print the system prompt each role is actually sent, with the size of it.

    **The assembled prompt existed nowhere until this.** Every role built its own by
    concatenation at call time, so the only way to know what a writer was told was to run one
    and read the transcript — and the consequence was a listing prompt that had grown to sixteen
    demands for a hundred-word artifact without anybody deciding it should.

    `tests/test_prompt_budget.py` holds the ceilings and fails when one is passed. This is the
    same numbers to look at before you add a clause rather than after.
    """
    writer = writers_domain.CAST.get(args.writer or "ferreira")
    if writer is None:
        print(
            f"litharness: no writer named {args.writer!r}; the cast is "
            f"{', '.join(writers_domain.CAST)}",
            file=sys.stderr,
        )
        return EXIT_FAULT

    roles: dict[str, str] = {
        "listing": overview_mod._system(writer),
        "architect-seed": world_agent.render_seed_request("a listing", writer).system or "",
        "architect-grow": (
            world_agent.render_grow_request("prose", logical_id="s1", writer=writer).system or ""
        ),
        "scene": house.with_house_rules(
            "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
            "no commentary, no summary of what you wrote. The context below is established and "
            "may be relied on; do not contradict it."
        ),
        "house-floor": house.HOUSE_RULES,
        "reader-measurement": readers_mod.pool(readers_mod.MEASUREMENT)[0].system(),
        "reader-steering": readers_mod.pool(readers_mod.STEERING)[0].system(),
        "screen-reader": comprehension.READERS[0].system(),
    }

    if args.role:
        if args.role not in roles:
            print(
                f"litharness: no role {args.role!r}; the roles are {', '.join(roles)}",
                file=sys.stderr,
            )
            return EXIT_FAULT
        text = roles[args.role]
        counted = house.demands(text)
        if args.json:
            print(json.dumps({"role": args.role, "chars": len(text),
                              "demands": list(counted)}, ensure_ascii=False, indent=2))
            return EXIT_OK
        print(text)
        print()
        print(f"  {len(counted)} demand(s), {len(text)} characters")
        return EXIT_OK

    rows = {
        role: {"chars": len(text), "demands": len(house.demands(text))}
        for role, text in roles.items()
    }
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(f"{'role':22s} {'chars':>7s} {'demands':>8s}")
    for role, row in rows.items():
        print(f"{role:22s} {row['chars']:7d} {row['demands']:8d}")
    print()
    print("  `--role <name>` prints one in full. Ceilings: tests/test_prompt_budget.py")
    return EXIT_OK


def cmd_world(args: argparse.Namespace) -> int:
    """The Architect's tools: ask this world a question, or declare something new in it.

    **The interface is the CLI because that is what an agent already speaks.** The operator,
    2026-08-24: *"all our agents should interact with each other through cli tools, as it is
    native interface for them"*, and *"in what world would a one-shot structured call be a
    good idea for writing a book... The world would obviously evolve and grow with every
    chapter"*. A world assembled once, before scene one, in a single structured call is the
    shape this replaces.

    Every view prints JSON under `--json` and a person's version otherwise, because both an
    agent and an operator read these. `application/world.py` holds the views and no logic:
    each is a wrapper over something `domain/worlds.py` already computed.

    **`declare` writes a proposal, never canon.** `worlds.world_record` mints at PROPOSED and
    that is the rail (§5, `plan/world-architect.md` §2) — an agent with this tool cannot put a
    fact into a book, only offer one.
    """
    store = _store(args)
    stamp = _stamp(_now())
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        records = store.state_records(book_id, branch_id)

        if args.view == "accept":
            proposals = [
                record
                for record in records
                if record.authority is lc.StateAuthority.PROPOSED
            ]
            if not proposals:
                print("nothing proposed; canon is unchanged")
                return EXIT_OK
            complaints = worlds_domain.validate(records)
            if complaints and not args.force:
                for complaint in complaints:
                    print(f"litharness: {complaint}", file=sys.stderr)
                print(
                    f"litharness: {len(proposals)} proposal(s) not accepted; this world "
                    "contradicts itself. Fix it with `world declare`, or --force to accept "
                    "anyway and leave the contradiction on the record.",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            moved = store.promote_state_records(
                book_id,
                branch_id,
                [record.record_id for record in proposals],
                authority=lc.StateAuthority.ACCEPTED_CANON,
                created_at=stamp,
            )
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="world.accept.v0",
                passed=not complaints,
                blocking=False,
                detail=f"{moved} proposal(s) accepted; {len(complaints)} complaint(s)",
            )
            store.record_decision(
                PolicyDecision(
                    decision_id=decision_id_for(
                        f"world-accept:{book_id}:{branch_id}:{stamp}", 0, (gate,)
                    ),
                    outcome=Outcome.ACCEPT,
                    gates=(gate,),
                    reason=(
                        "the Architect's proposals were accepted into canon; nothing here "
                        "ranked or chose between them"
                    ),
                ),
                decided_at=stamp,
            )
            print(f"accepted {moved} of {len(proposals)} proposal(s) into canon")
            return EXIT_OK

        if args.view == "presence":
            head = store.head(book_id, branch_id)
            scenes = (
                {
                    node.logical_id: (node.content or "")
                    for node in head.nodes
                    if node.kind is NodeKind.SCENE
                }
                if head is not None
                else {}
            )
            print(
                json.dumps(
                    world_mod.presence(records, scenes), ensure_ascii=False, indent=2
                )
            )
            return EXIT_OK
        if args.view == "declare":
            record = worlds_domain.world_record(
                worlds_domain.normalise_id(args.subject),
                args.predicate,
                value=_scalar(args.value),
                object_ref=(worlds_domain.normalise_id(args.object) if args.object else None),
                order_key=args.order_key,
                note=args.note,
            )
            # **Warned, never refused, and that is the whole point of a staging area.**
            # A question owes an answer, a rung owes a chain, an edge owes both ends — so
            # an Architect building a world one record at a time is in a transiently
            # incoherent state almost continuously. The first agent to hold these tools hit
            # exactly that: `asks` refused because its `claim.content` had not landed yet,
            # and it worked around the tool rather than saying what it meant, leaving a
            # 317-record world with zero questions in it. `world accept` is the gate, and
            # it is the gate because that is where a proposal becomes canon.
            complaints = worlds_domain.validate([*records, record])
            fresh = worlds_domain.validate(records)
            new_complaints = [c for c in complaints if c not in fresh]
            written = store.record_state_records(
                book_id, branch_id, [record], created_at=stamp
            )
            payload: Any = {
                "record_id": record.record_id,
                "authority": record.authority.value,
                "new": bool(written),
                "says": state_mod.describe(record),
                "not_yet_coherent": new_complaints,
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                verb = "declared" if written else "already on record"
                print(f"{verb}: {payload['says']}  [{record.authority.value}]")
                for complaint in new_complaints:
                    print(f"  ! not yet coherent: {complaint}", file=sys.stderr)
            return EXIT_OK
    finally:
        store.close()

    if args.view == "show":
        payload = world_mod.declarations(records, subject=args.subject)
    elif args.view == "rules":
        payload = world_mod.rules(records)
    elif args.view == "ladders":
        payload = world_mod.ladders(records)
    elif args.view == "abilities":
        payload = world_mod.abilities(records, holder=args.holder)
    elif args.view == "cast":
        payload = world_mod.cast(records)
    elif args.view == "threads":
        payload = world_mod.threads(records, at=args.at)
    elif args.view == "vocabulary":
        payload = world_mod.vocabulary()
    elif args.view == "check":
        payload = world_mod.check(records)
    else:
        payload = world_mod.summary(records)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.view == "check" and not payload["ok"]:
        return EXIT_FAULT
    return EXIT_OK

def cmd_state(args: argparse.Namespace) -> int:
    """What this book holds as true, in story order (§11's objective story state).

    **The layer that gates every draft, and no verb could show it.** The integrity gate
    refuses a candidate contradicting these records, the context packet hands them to the
    generator as established facts, and propagation reads its changes out of them — and until
    this the only way to look at any of it was to open the SQLite file.

    Story order, because a ledger read out of order is not a ledger. That is also what makes
    this the view worth having: `state.contradiction.v0` checks disagreement at a *single*
    position and cannot see a balance that stops adding up across them, so where the optional
    ContinuityEvaluation pack is not configured, **the operator reading this column is the one
    who notices**. §4.3 calls that directing rather than operating, and it needs somewhere to
    look.

    Provenance is on every line because imported canon and extracted canon are different
    claims — one is the author's word, the other this system's reading of prose it generated —
    and an operator deciding whether to trust a fact needs to know which.
    """
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        records = store.state_records(book_id, branch_id, subject=args.subject)
    finally:
        store.close()

    if args.predicate:
        records = [item for item in records if item.predicate == args.predicate]
    ordered = state_mod.in_story_order(records)
    read_here = 0
    for record in ordered:
        position = state_mod.order_key_of(record) or "-"
        extracted = record.predicate_registry_version == extraction.REGISTRY_VERSION
        read_here += int(extracted)
        flags = "read" if extracted else "given"
        if not state_mod.is_canon(record):
            flags = f"{flags} {record.authority.value}"
        print(f"{position:<6} {flags:<10} {state_mod.describe(record)}")
        if record.note:
            print(f"       {record.note}")
        if record.pov_visibility:
            print(f"       known only to {', '.join(record.pov_visibility)}")

    if not ordered:
        # An empty list and a book nobody has read look identical otherwise. The mystery is a
        # book whose canon is real and whose *system voice* is empty by genre, so silence here
        # is a fact about this book rather than about the store.
        print("no state on record for this branch")
        print("  imported with `import --state`, or read back out of accepted prose")
        return EXIT_OK
    print(f"({len(ordered)} record(s), {read_here} read from this book's own prose)")
    unplaced = sum(1 for record in ordered if state_mod.order_key_of(record) is None)
    if unplaced:
        # Not an error: a starting sheet is true before the book begins. But an unplaced
        # record is invisible to the contradiction detector, which groups on position, so an
        # operator should know how much of their canon is not being checked.
        print(f"  {unplaced} unplaced — true of the book rather than of a moment in it")
    return EXIT_OK


def _forge_paths(out: Path) -> tuple[Path, Path, Path, Path]:
    return (out / "forge.json", out / "seed.json", out / "directives.json", out / "promises.json")


def _picked_scene_count(
    forged: dict[str, Any], requested: int | None, *, source: Path
) -> tuple[int | None, str]:
    """The width `--pick` mints story keys at, or `None` and the refusal that says why not.

    **The forge and the pick are two commands, and the number lived only in the operator's
    head between them.** Measured on Serial Pilot 4 (`plan/serial-pilot-4.md` §5.6): the forge
    ran at eight scenes, the pick was run a day later without `--scenes`, and `story_key` mints
    no position for a scene the book does not have — so the eight-scene reveal kept its ordinal
    and got no disclosure, and `undisclosed_claims` keeps a claim with no position hidden
    throughout. The reveal those eight scenes existed to settle could never land: 40-opened-0-
    paid, reproduced by the machinery built to stop producing it, and silently.

    So the forge records the width it forged at, and the pick reads it rather than guessing
    `DEFAULT_SCENES`. An explicit `--scenes` that *disagrees* is *refused rather than obeyed*,
    because either number could be the wrong one and only the operator knows which — the same
    refusal `tools/rematerialise_forge_bundle.py` already makes against the directive file it
    is handed, and for the same reason: a story key minted at one width does not compare to a
    beat key minted at another (`story_key`, and §110's measured leak).

    **A `forge.json` written before the width was recorded has no key, and that absence keeps
    the old behaviour exactly** — `--scenes` if given, `DEFAULT_SCENES` if not. Refusing those
    would park every bundle already on disk over a fault none of them can be shown to have.
    """
    recorded = forged.get("scenes")
    if recorded is not None and (
        not isinstance(recorded, int) or isinstance(recorded, bool) or recorded < 1
    ):
        return None, (
            f"litharness: {source} records a scene count of {recorded!r}, which is not a number "
            "of scenes; picking from it would mint story keys at a width nobody chose"
        )
    if recorded is None:
        return (architect.DEFAULT_SCENES if requested is None else requested), ""
    if requested is None or requested == recorded:
        return recorded, ""
    return None, (
        f"litharness: --scenes {requested} disagrees with {source}, which was forged at "
        f"{recorded} scene(s). A story key minted at one width is not comparable to a beat key "
        f"minted at another, and only you know which number is the wrong one. Re-run the pick "
        f"with --scenes {recorded}, or forge again at {requested}."
    )


def _screen_line(screen: Mapping[str, Any]) -> str:
    """One line about a candidate's comprehension screen, for stdout and for the gate detail.

    Reads the stored block rather than a `ScreenResult`, so the same sentence renders for a
    screen that ran, a screen the premise stage never reached, and a bundle read back off disk.
    """
    if "undefined_total" not in screen:
        return f"FAILED — {screen.get('reason') or 'no screen run'}"
    questions = sum(
        len(quoted) for quoted in (screen.get("open_questions_by_reader") or {}).values()
    )
    if screen.get("passed"):
        # The open questions are printed beside the pass and never against it: a pitch that
        # leaves questions it plans to answer is working.
        return f"passed (0 undefined, {questions} open question(s))"
    # The readers whose answers could be read are exactly the keys of `undefined_by_reader`;
    # everyone else either was never asked, was stopped, or answered in a shape the screen
    # could not read. `unanswered` names the ones a ceiling or a provider stopped, which is a
    # different fact from a garbled answer and is reported as one.
    readable = set(screen.get("undefined_by_reader") or {})
    stopped = dict(screen.get("unanswered") or {})
    unreadable = sorted(
        reader_id
        for reader_id in (screen.get("readers") or [])
        if reader_id not in readable and reader_id not in stopped
    )
    faults: list[str] = []
    if screen.get("undefined_total"):
        faults.append(
            f"{screen['undefined_total']} undefined across "
            f"{screen['readers_confused']} reader(s)"
        )
    if stopped:
        faults.append(
            f"{len(stopped)} reader(s) were stopped ({', '.join(sorted(stopped))})"
        )
    if unreadable:
        faults.append(
            f"{len(unreadable)} reader(s) answered unreadably ({', '.join(unreadable)})"
        )
    return "FAILED — " + ("; ".join(faults) or "the screen did not complete")


@dataclass
class _StageSpend:
    """What one stage of a forge cost, summed across its calls, for one decision row.

    A forge is three stages now — the world, the premises, the screen — and each spends
    separately. One row per stage rather than one row for the lot, because a stage whose cost
    is folded into another stage's total is a cost nobody can read back: `store.spend_on` is
    what the daily ceiling reads, and `plan/handoff-clarity-remaining.md` asks for the premise
    and screen spend to be separable from the world's.
    """

    invocations: int = 0
    total_tokens: int = 0
    #: `None` until a provider reports dollars, which is `_SpendTally`'s rule and the reason
    #: for it: `PolicyDecision.cost_usd` is `None` for a subscription CLI or local hardware,
    #: and a stage written down as `0.0` reads as free rather than as unpriced.
    cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None
    fell_back_from: tuple[str, ...] = ()

    def add(self, result: CompletionResult, resolution: Any) -> None:
        self.invocations += result.invocations
        self.total_tokens += result.usage.total
        if result.cost_usd is not None:
            self.cost_usd = (self.cost_usd or 0.0) + result.cost_usd
        self.provider = result.provider
        self.model = result.model
        self.fell_back_from = tuple(resolution.fell_back_from)


@dataclass
class _ForgeCalls:
    """Everything the premise and screen stages need to make a call and account for it.

    **The running total is why this is an object.** `store.spend_on` reads the decision
    ledger, and a forge records its decisions at the end — so a per-call ceiling that read
    only the ledger would be blind to the world call above it and to every premise and reader
    call before it in the same run, which is exactly the run the `--max-cost-usd-per-day`
    guard exists for. `run` carries what this invocation has already committed, and every
    check is made against the ledger plus that.
    """

    registry: ProviderRegistry
    store: SqliteStore
    args: argparse.Namespace
    stamp: str
    #: Everything this forge has spent so far, the world call included.
    run: _StageSpend
    #: The two stage tallies, each the body of one decision row.
    premise: _StageSpend
    screen: _StageSpend

    def spent_today(self) -> Spend:
        return self.store.spend_on(self.stamp[:10]).plus(
            invocations=self.run.invocations,
            tokens=self.run.total_tokens,
            cost_usd=self.run.cost_usd or 0.0,
        )


def _forge_call(
    request: CompletionRequest, *, calls: _ForgeCalls, spend: _StageSpend
) -> tuple[CompletionResult | None, str]:
    """One model call inside a forge, budget-checked, or `None` and the reason there is none.

    **Neither refusal raises.** A forge has already paid for its world by the time this runs,
    and the branch that discarded a paid answer unread is the one `cmd_forge`'s conformance
    comment records: two forges lost on 2026-08-23 because a failure printed a line and
    returned. A budget ceiling or a provider failure here costs one candidate its premise and
    nothing else — the forge still writes its files and still records every call it made.

    The reason it returns is an **operational** one — the environment refused, nothing about
    the work was wrong — and every caller keeps it apart from what a gate found. That is
    `domain/failures.py`'s distinction, and the forge needs it for a different reason than the
    Conductor does: a candidate marked "the premise never names Silas" is a fact about a
    paragraph a model wrote, and a candidate marked "the daily budget refused the call" is a
    fact about the day. Reading the second as the first is how a ceiling comes to look like a
    bad forge.
    """
    provider, _ = calls.registry.resolve(request.call_class)
    verdict = budget_check(
        _budget(calls.args),
        calls.spent_today(),
        provider=provider.name,
        prompt_chars=len(request.prompt),
        max_output_tokens=request.max_output_tokens,
    )
    if not verdict.allowed:
        return None, f"the daily budget refused the call: {verdict.reason}"
    try:
        result, resolution = calls.registry.complete(request)
    except OperationalFailure as error:
        return None, f"the provider failed: {error}"
    spend.add(result, resolution)
    calls.run.add(result, resolution)
    return result, ""


@dataclass(frozen=True, slots=True)
class _PremiseAttempt:
    """One try at a premise: the paragraph, what was wrong with it, and its screen.

    Three ways to fail and they are kept apart. `refusal` is operational — no paragraph was
    written because the environment said no. `complaints` are deterministic faults in a
    paragraph that *was* written. `screen` is what four readers made of a paragraph that had
    no faults. An attempt carries at most one of the three, and the bundle says which.
    """

    premise: str
    complaints: tuple[str, ...]
    refusal: str
    #: The screen block, or `None` when no reader was asked.
    screen: dict[str, Any] | None

    @property
    def usable(self) -> bool:
        return bool(self.screen and self.screen.get("passed"))

    @property
    def read(self) -> bool:
        """Whether four readers actually answered about this paragraph.

        A block exists for an attempt whose screen never ran — it carries the reason instead
        — so the presence of a block is not evidence that anybody read the premise.
        `undefined_total` is written only by `ScreenResult.to_jsonable`, so it is.
        """
        return self.screen is not None and "undefined_total" in self.screen

    @property
    def written(self) -> bool:
        """Whether a paragraph came back at all, faults or not."""
        return bool(self.premise.strip())

    def block(self) -> dict[str, Any]:
        """What lands in the bundle's `screen` key for this attempt."""
        if self.screen is not None:
            return self.screen
        return {
            "passed": False,
            "reason": self.refusal or "; ".join(self.complaints) or "no screen run",
        }


def _one_premise(candidate: architect.Candidate, *, calls: _ForgeCalls) -> _PremiseAttempt:
    """One premise call, and what is deterministically wrong with what came back.

    **The request is a pure function of the candidate and is rendered fresh every time.**
    Nothing a gate found, nothing a reader quoted, and nothing about a previous attempt may
    enter it — §97.1, and `plan/handoff-clarity-first.md` boundary 5 states the same rail from
    the other side: a failed premise is re-forged, never rewritten from the findings against
    it. A retry here is the identical ask asked again.
    """
    result, refusal = _forge_call(
        architect.render_premise_request(candidate), calls=calls, spend=calls.premise
    )
    if result is None:
        return _PremiseAttempt(premise="", complaints=(), refusal=refusal, screen=None)
    premise = result.text.strip()
    return _PremiseAttempt(
        premise=premise,
        complaints=architect.premise_complaints(premise, candidate),
        refusal="",
        screen=None,
    )


def _written_premise(candidate: architect.Candidate, *, calls: _ForgeCalls) -> _PremiseAttempt:
    """The premise stage for one candidate: one call, and one fresh retry if it complains."""
    attempt = _one_premise(candidate, calls=calls)
    if not attempt.complaints:
        return attempt
    return _one_premise(candidate, calls=calls)


def _screen_of(
    premise: str, *, calls: _ForgeCalls
) -> tuple[comprehension.ScreenResult | None, str, dict[str, str]]:
    """Four readers on one premise: the result, the reason no reader was asked, the refusals.

    **The four calls are priced one after another before any of them is made, and summing
    them into one check does not do that.** `budget.projected_tokens` charges the
    per-invocation harness tax **once**, and `budget.check` tests `invocations + 1`, not
    `+ 4` — so a batch handed the summed prompt chars and the summed output allowance is
    under-projected on both counters. Measured over a 1,200-character premise: the summed
    check projects 31,343 tokens against the 103,340 the four calls actually project, and
    against `max_invocations_per_day`'s 500 default it reserves one invocation for four.

    That is not a rounding difference, because of what a part-screen costs. A ceiling landing
    between readers leaves the attempt non-conforming — the readers who never answered did not
    say there were no undefined words — so a premise **no reader objected to** is marked
    screen-failed, excluded from `usable`, and refused by `--pick`, after a world call, a
    premise call and three reader calls have been paid for. So the check walks the requests
    against a running `Spend`, which is the only shape that can refuse *before* the first
    reader rather than in the middle.

    A provider failure can still stop a screen part-way, and that is a different fact: the
    refusals are returned so the record can say a reader was stopped rather than that a reader
    garbled an answer.
    """
    requests = [
        (reader, comprehension.render_reader_request(reader, premise))
        for reader in comprehension.READERS
    ]
    policy = _budget(calls.args)
    spent = calls.spent_today()
    for _, request in requests:
        provider, _ = calls.registry.resolve(request.call_class)
        verdict = budget_check(
            policy,
            spent,
            provider=provider.name,
            prompt_chars=len(request.prompt),
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            return None, f"the daily budget refused the screen: {verdict.reason}", {}
        # The projection is deliberately an over-estimate (`projected_tokens`' own docstring),
        # so advancing by it cannot let the ceiling be crossed by a call this loop cleared.
        spent = spent.plus(invocations=1, tokens=verdict.projected_tokens)
    answers: dict[str, Mapping[str, Any] | None] = {}
    refusals: dict[str, str] = {}
    for reader, request in requests:
        result, refusal = _forge_call(request, calls=calls, spend=calls.screen)
        if refusal:
            refusals[reader.reader_id] = refusal
        parsed = result.parsed if result is not None else None
        answers[reader.reader_id] = parsed if isinstance(parsed, Mapping) else None
    return comprehension.ScreenResult.of(answers), "", refusals


def _screened_premise(
    candidate: architect.Candidate, *, calls: _ForgeCalls
) -> _PremiseAttempt:
    """One candidate's premise, what was wrong with it, and the screen block for its bundle.

    **The whole of `plan/handoff-clarity-first.md` boundary 5 in one function.** The premise is
    written, checked deterministically, and shown to four readers; a premise that leaves any of
    them quoting a word they were never given is refused and **re-forged** — one fresh
    regeneration, one re-screen, and then the candidate is marked. There is no third attempt
    and no flag that skips the screen: no premise reaches the operator unscreened.

    The two retry budgets are separate on purpose and the handoff draws them that way: the
    premise stage's retry is for a paragraph that came back empty, unnamed or borrowed, and the
    screen's regeneration is for a paragraph that was fine by arithmetic and unreadable to a
    reader. A candidate can therefore cost at most three premise calls and eight reader calls.

    **What is carried is one paragraph and the screen of that same paragraph**, and the rule is
    written down because the obvious version of it loses work. A block describing a premise the
    bundle does not hold is worse than no block, so attempts are kept whole; and "the last
    attempt" would discard a paid, fault-free paragraph the moment a regeneration came back
    empty because a ceiling landed on it. So: the attempt that passed; failing that, the last
    attempt a screen actually read; failing that, the last attempt that produced a paragraph at
    all. **Every attempt is recorded** in the block's `attempts`, so a regeneration that was
    refused is visible even when the paragraph carried is the earlier one.
    """
    attempts: list[_PremiseAttempt] = []
    for attempt_index in range(2):
        # Attempt 2 is the screen's ONE fresh regeneration, and it gets no complaint retry of
        # its own: the premise stage already spent that budget on attempt 1.
        attempt = (
            _written_premise(candidate, calls=calls)
            if attempt_index == 0
            else _one_premise(candidate, calls=calls)
        )
        if attempt.complaints or attempt.refusal:
            # A paragraph that is empty, unnamed or borrowed is not worth four reader calls,
            # and the premise stage has already retried it once.
            attempts.append(attempt)
            break
        screen, refusal, refusals = _screen_of(attempt.premise, calls=calls)
        block = (
            screen.to_jsonable()
            if screen is not None
            else {"passed": False, "reason": refusal or "no screen run"}
        )
        if refusals:
            # Which readers were stopped rather than unreadable. `_screen_line` reads it, and
            # without it a ceiling and a garbled answer look identical in the record.
            block["unanswered"] = dict(refusals)
        attempts.append(replace(attempt, screen=block))
        if screen is not None and screen.passed:
            break

    chosen = next(
        (item for item in reversed(attempts) if item.usable),
        next(
            (item for item in reversed(attempts) if item.read),
            next((item for item in reversed(attempts) if item.written), attempts[-1]),
        ),
    )
    block = chosen.block()
    if len(attempts) > 1:
        block = {
            **block,
            "attempts": [
                {
                    "words": len(item.premise.split()),
                    "complaints": list(item.complaints),
                    "refusal": item.refusal,
                    "passed": item.usable,
                    "carried": item is chosen,
                }
                for item in attempts
            ],
        }
    return replace(chosen, screen=block)


def cmd_forge(args: argparse.Namespace) -> int:
    """A world, forged: brief → K candidates → premise → screen → a seed `new` consumes.

    **Three model stages and one decision row each.** The world is a structured call and
    carries no reader-facing prose; the premise is its own prose call per candidate; the
    comprehension screen is four genre readers per premise, and a premise passes only at zero
    words quoted as undefined by all four (`application/comprehension.py`). None of the three
    ranks anything: the screen refuses on a count, and what survives is presented in the order
    it was forged.

    Two invocations, deliberately, and the split is the second rail of
    `plan/world-architect.md` §2. The first generates and gates and then **stops** — no model
    orders the candidates, none is marked best, and the command exits with the report. The
    second, `--pick N`, is a person choosing, makes no provider call, records its own
    decision, and refuses a candidate whose premise the screen failed. §61(5)'s alpha division
    counts the candidates, which is why the count is on both rows.

    The bundles are written before the decision is recorded, because a forge whose files landed
    and whose decision did not is recoverable by re-running `--pick`, and one whose decision
    landed with no files is a row pointing at nothing.
    """
    out = Path(args.out)
    forge_path, seed_path, directives_path, promises_path = _forge_paths(out)
    stamp = _stamp(_now())

    if args.pick is not None:
        if not forge_path.exists():
            print(f"litharness: {forge_path} does not exist; run forge first", file=sys.stderr)
            return EXIT_FAULT
        forged = json.loads(forge_path.read_text(encoding="utf-8"))
        bundles = forged["candidates"]
        if not 1 <= args.pick <= len(bundles):
            print(
                f"litharness: --pick {args.pick} is outside 1..{len(bundles)}",
                file=sys.stderr,
            )
            return EXIT_FAULT
        chosen = bundles[args.pick - 1]
        # **A premise four readers could not follow is not picked, and there is no flag that
        # says otherwise.** `plan/handoff-clarity-first.md` boundary 5: a failed premise is
        # refused and re-forged, never hand-patched — rewriting it from what the readers quoted
        # is the contamination §97.1 exists to stop, and it would arrive here as an operator
        # editing `directives.json` by hand. A bundle with no `screen` key was forged before
        # the gate existed and picks exactly as it always did.
        screen = chosen.get("screen")
        if isinstance(screen, Mapping) and not screen.get("passed"):
            print(
                f"litharness: candidate {args.pick} did not pass the comprehension screen "
                f"({_screen_line(screen)}). The screen is four genre readers restating the "
                "premise, and it passes at zero words quoted as undefined. A premise that "
                "fails is re-forged rather than edited — rewriting it from what the readers "
                "quoted would feed a finding back into a prompt. Forge again and pick from "
                "what passes.",
                file=sys.stderr,
            )
            return EXIT_FAULT
        scenes, fault = _picked_scene_count(forged, args.scenes, source=forge_path)
        if scenes is None:
            print(fault, file=sys.stderr)
            return EXIT_FAULT
        # **The one place a forged world becomes canon, and the reason it is here.** The bundles
        # on disk hold the world as it was *proposed*; `context.assemble` filters proposals out
        # by `is_canon` before anything else happens, so a serial seeded from them would draft
        # against a premise and nothing else while looking, at every layer, exactly like the
        # book this role exists to stop producing. Admitting them at the *pick* is what makes
        # the operator's choice the decision that carries them, which is the rail
        # `plan/world-architect.md` §2 states and `cmd_import`'s own comment already applies to
        # a snapshot somebody typed: accepted on the director's authority.
        admitted = architect.snapshot_for(
            architect.Candidate(int(chosen["index"]), chosen["world"]),
            book_id=str(chosen["seed"]["book_id"]),
            branch_id=str(chosen["seed"]["branch_id"]),
            revision_id=str(chosen["seed"]["revision_id"]),
            architect_id=str(forged["architect_id"]),
            created_at=str(chosen["seed"]["meta"]["created_at"]),
            authority=lc.StateAuthority.ACCEPTED_CANON,
            # The book's own key width, so a reveal position is comparable to a beat key.
            # `story_key` records what went wrong when it was not, and `_picked_scene_count`
            # records what went wrong when the operator had to carry the number by hand.
            scenes=scenes,
        )
        seed_path.write_text(
            json.dumps(lc.to_jsonable(admitted), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        directives_path.write_text(
            json.dumps(
                {
                    "source": str(forge_path),
                    "title": chosen["title"],
                    "premise": chosen["premise"],
                    "scenes": scenes,
                    "directives": chosen["directives"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        promises_path.write_text(
            json.dumps(chosen["promises"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # The operator's act, recorded as one. `VerdictSource.HUMAN` because it is: a person
        # read K worlds and chose. Non-blocking, because nothing here refuses anything.
        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="architect.pick.v0",
            passed=True,
            verdict_source=VerdictSource.HUMAN,
            blocking=False,
            detail=f"candidate {args.pick} of {len(bundles)}",
        )
        decision = PolicyDecision(
            decision_id=decision_id_for(
                f"forge-pick:{forged['architect_id']}:{args.pick}", 0, (gate,)
            ),
            outcome=Outcome.ACCEPT,
            gates=(gate,),
            profile=architect.PROFILE,
            reason=(
                f"the operator chose world {args.pick} of {len(bundles)}; §61(5) divides the "
                f"confidence level by {len(bundles)}"
            ),
        )
        store = _store(args)
        try:
            store.record_decision(decision, decided_at=stamp)
        finally:
            store.close()
        print(f"{decision.decision_id}")
        note = chosen["report"]
        print(f"  {chosen['title']}  ({note['domain']}, {note['geometry']})")
        print(f"  seed        {seed_path}")
        print(f"  directives  {directives_path}")
        print(f"  promises    {promises_path}")
        print("")
        print("Next:")
        print(
            f"  litharness --database {args.database} new {chosen['title']!r} "
            f"--premise <the premise in {directives_path.name}> --scenes {scenes} "
            f"--state {seed_path} --promises {promises_path}"
        )
        return EXIT_OK

    brief = args.brief or ""
    architect_id = worlds_domain.architect_id_for(brief)
    # **The lane key carries the instant, and the reason is money already lost.**
    # `decision_id_for` derives an id from the key, the attempt and the gates' (kind, rule id,
    # passed) — deliberately, so a *replayed job* collapses onto one row instead of
    # accumulating duplicates of one judgment. A forge is not a replayed job: every invocation
    # is a fresh paid call, and two forges of the same brief and shape whose worlds fail the
    # same gates produce the same signature. Measured on `reader-book.db`: two K=2 forges of
    # "progression fantasy" ran on 2026-08-24 for $1.55 and $1.62, both with two failing world
    # gates, and the ledger holds **one** row — `record_decision` returns False on the second
    # and every call site ignores it, so $1.62 never reached `store.spend_on`, which is the
    # figure the daily ceiling reads. The stamp is data rather than a nonce, so the id is still
    # derived rather than random; `forge-pick` keeps the old key on purpose, because re-running
    # the same pick makes no call and *should* collapse.
    lane = f"{architect_id}:{args.shape}:{stamp}"
    # The width every candidate is forged at, resolved once so the file can record it. What
    # `--pick` does with that record is `_picked_scene_count`.
    scenes = architect.DEFAULT_SCENES if args.scenes is None else args.scenes
    try:
        request = architect.render_world_request(
            brief, k=args.k, shape=args.shape, scenes=scenes
        )
    except architect.ArchitectInputError as error:
        print(f"litharness: {error}", file=sys.stderr)
        return EXIT_FAULT

    registry = build_default_registry()
    store = _store(args)
    try:
        provider, _ = registry.resolve(request.call_class)
        verdict = budget_check(
            _budget(args),
            store.spend_on(stamp[:10]),
            provider=provider.name,
            prompt_chars=len(request.prompt),
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            print(f"litharness: {verdict.reason}", file=sys.stderr)
            return EXIT_ATTENTION
        result, resolution = registry.complete(request)
        if not result.conforms or result.parsed is None:
            # **The answer is kept and the spend is recorded, because neither was true and it
            # cost two forges to find out.** On 2026-08-23 two of three K=3 forges landed here
            # and this branch printed one line and returned: the paid answer was discarded
            # unread, and because no decision was recorded, `store.spend_on` — which the budget
            # ceiling reads — never saw the money. Diagnosing it needed a wrapper around the
            # provider to catch the envelope a second time.
            #
            # What the kept answer said, once it could be read: 64,546 output tokens including
            # 23,630 of thinking, and a `result` holding 1,553 characters that begin mid-object.
            # The answer had outgrown a single message and what came back was its tail. The
            # conforming forge beside it ran to 57,862 output tokens, so the size is the
            # diagnosis and the output token count is printed here for the next person.
            out.mkdir(parents=True, exist_ok=True)
            refused_path = out / "refused.txt"
            refused_path.write_text(result.text, encoding="utf-8")
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.forge.conforms.v0",
                passed=False,
                detail=(
                    f"the answer does not conform to the world schema "
                    f"({result.usage.output_tokens} output token(s)); kept at {refused_path}"
                ),
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(f"forge:{lane}", 0, (gate,)),
                outcome=Outcome.ESCALATE,
                gates=(gate,),
                profile=architect.PROFILE,
                provider=result.provider,
                model=result.model,
                fell_back_from=tuple(resolution.fell_back_from),
                invocations=result.invocations,
                total_tokens=result.usage.total,
                cost_usd=result.cost_usd,
                reason=gate.detail,
            )
            store.record_decision(refusal, decided_at=stamp)
            print(
                "litharness: the forge returned an answer that does not conform to the "
                f"schema; {result.usage.output_tokens} output token(s), kept at "
                f"{refused_path}. An answer this size is usually one message short of "
                "whole — forge fewer worlds (--k 2) rather than retrying at the same width",
                file=sys.stderr,
            )
            return EXIT_ATTENTION
        try:
            candidates = architect.worlds_from(result.parsed, args.k)
        except architect.ArchitectOutputError as error:
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.forge.v0",
                passed=False,
                detail=str(error),
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(f"forge:{lane}", 0, (gate,)),
                outcome=Outcome.ESCALATE,
                gates=(gate,),
                profile=architect.PROFILE,
                provider=result.provider,
                model=result.model,
                fell_back_from=tuple(resolution.fell_back_from),
                invocations=result.invocations,
                total_tokens=result.usage.total,
                cost_usd=result.cost_usd,
                reason=str(error),
            )
            store.record_decision(refusal, decided_at=stamp)
            print(f"litharness: {error}", file=sys.stderr)
            return EXIT_ATTENTION

        # **The premise, written as prose, and then screened before anybody reads it.**
        # `plan/handoff-clarity-first.md` boundaries 4 and 5: the world above is data and the
        # paragraph a reader will actually read is its own call, and no premise reaches the
        # operator unscreened. Both stages run per candidate, and neither can refuse the
        # forge — a candidate that fails is carried with its faults and marked unusable, which
        # is the same rail the world gates already run on: information for the person choosing,
        # not a refusal of work the world call has already been paid for.
        premise_spend = _StageSpend()
        screen_spend = _StageSpend()
        # Seeded with the world call, so the first premise call's ceiling check sees the money
        # this run has already spent rather than only what the ledger has been told about.
        run_spend = _StageSpend()
        run_spend.add(result, resolution)
        calls = _ForgeCalls(
            registry=registry,
            store=store,
            args=args,
            stamp=stamp,
            run=run_spend,
            premise=premise_spend,
            screen=screen_spend,
        )
        written = [_screened_premise(candidate, calls=calls) for candidate in candidates]

        bundles = [
            {
                **architect.bundle_for(
                    candidate,
                    book_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"litharness://forge/{architect_id}/{candidate.index}/book")),
                    branch_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"litharness://forge/{architect_id}/{candidate.index}/branch")),
                    revision_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"litharness://forge/{architect_id}/{candidate.index}/revision")),
                    architect_id=architect_id,
                    created_at=stamp,
                    brief=brief,
                    shape=args.shape,
                    premise=attempt.premise,
                    scenes=scenes,
                ),
                # Beside the premise it screened, in the bundle `--pick` reads. A bundle with
                # no `screen` key was forged before the gate existed and picks as it always
                # did; absence keeps old behaviour, which is this repository's standing pattern
                # for a field added to an artefact already on disk.
                "screen": attempt.block(),
                # **Two keys because there are two kinds of fault.** A complaint is a fact
                # about a paragraph a model wrote; a refusal is a fact about the day — a
                # ceiling or a provider. `domain/failures.py` keeps that line for the
                # Conductor's retry budget, and the forge keeps it so a budget ceiling never
                # reads back as a bad premise.
                "premise_complaints": list(attempt.complaints),
                "premise_refusal": attempt.refusal,
            }
            for candidate, attempt in zip(candidates, written, strict=True)
        ]
        # Per candidate, and **non-blocking every one of them**: a world that fails a gate is
        # information for the person choosing, not a refusal of the forge — a loser's defect
        # made standing would park work that has nothing to do with it.
        gates = tuple(
            GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="architect.world.v0",
                passed=not bundle["report"]["gate_complaints"],
                blocking=False,
                detail=(
                    f"world {bundle['index'] + 1}: "
                    + (
                        "; ".join(bundle["report"]["gate_complaints"])
                        if bundle["report"]["gate_complaints"]
                        else "clear"
                    )
                ),
            )
            for bundle in bundles
        )
        # **`usable` now means clear of the gates AND readable**, which is the whole point of
        # the screen: a world nobody can be pitched is not a candidate, however well it
        # declares itself. The two halves stay separable in the file — `gate_complaints` on the
        # report, `screen` beside it — so a forge that produced good worlds and bad pitches
        # reads as that rather than as a bad forge.
        usable = sum(
            1
            for bundle in bundles
            if not bundle["report"]["gate_complaints"] and bundle["screen"].get("passed")
        )
        forged = {
            "architect_id": architect_id,
            "brief": brief,
            "prompt_shape": args.shape,
            "k": args.k,
            # **The number the operator used to have to carry between two commands.** Every
            # disclosure position in every candidate was minted at this width; `--pick` reads
            # it from here rather than defaulting, and refuses a `--scenes` that disagrees.
            "scenes": scenes,
            "created_at": stamp,
            "provider": result.provider,
            "model": result.model,
            "profile": architect.PROFILE,
            "usage_total_tokens": result.usage.total,
            "cost_usd": result.cost_usd,
            # The pair above is the world call's, which is what this file has always recorded.
            # The premise and the screen are separate calls for separate money, and their rows
            # in the decision ledger are the authority (`store.spend_on` reads those, and the
            # daily ceiling reads `spend_on`); these two are here so that an operator deciding
            # whether to forge again can see what a forge costs without opening the database.
            "premise_spend": {
                "profile": architect.PREMISE_PROFILE,
                "invocations": premise_spend.invocations,
                "usage_total_tokens": premise_spend.total_tokens,
                "cost_usd": premise_spend.cost_usd,
            },
            "screen_spend": {
                "profile": comprehension.SCREEN_PROFILE,
                "readers": [reader.reader_id for reader in comprehension.READERS],
                "invocations": screen_spend.invocations,
                "usage_total_tokens": screen_spend.total_tokens,
                "cost_usd": screen_spend.cost_usd,
            },
            "spread": architect.spread(candidates),
            "usable": usable,
            "candidates": bundles,
        }
        out.mkdir(parents=True, exist_ok=True)
        forge_path.write_text(
            json.dumps(forged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        decision = PolicyDecision(
            decision_id=decision_id_for(f"forge:{lane}", 0, gates),
            outcome=Outcome.ACCEPT,
            gates=gates,
            profile=architect.PROFILE,
            provider=result.provider,
            model=result.model,
            fell_back_from=tuple(resolution.fell_back_from),
            invocations=result.invocations,
            total_tokens=result.usage.total,
            cost_usd=result.cost_usd,
            reason=(
                f"{args.k} world(s) forged under prompt shape {args.shape!r}, {usable} clear of "
                "every gate and of the comprehension screen; no model ordered them and none is "
                "marked best"
            ),
        )
        store.record_decision(decision, decided_at=stamp)

        # **One row per stage, because a forge spends three times now.** Non-blocking per
        # candidate for the same reason the world gates are: neither stage refuses the forge,
        # and a candidate that failed one is information for the person choosing.
        #
        # Each lane derives its decision id from its own key. `decision_id_for` hashes the key,
        # the attempt and the gates' (kind, rule id, passed) — not the spend — so two lanes
        # sharing a key and a gate signature would collide, `record_decision`'s INSERT OR
        # IGNORE would drop the second, and its money would never reach `spend_on`, which is
        # what the daily ceiling reads. `--pick` already keeps its lane apart the same way.
        premise_gates = tuple(
            GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id=architect.PREMISE_PROFILE,
                passed=not bundle["premise_complaints"] and not bundle["premise_refusal"],
                blocking=False,
                # An operational refusal is labelled as one on the row, so a day the ceiling
                # stopped does not read back as a day the model wrote bad premises.
                detail=(
                    f"world {bundle['index'] + 1}: "
                    + (
                        f"not written ({bundle['premise_refusal']})"
                        if bundle["premise_refusal"]
                        else "; ".join(bundle["premise_complaints"]) or "clear"
                    )
                ),
            )
            for bundle in bundles
        )
        premise_decision = PolicyDecision(
            decision_id=decision_id_for(
                f"forge-premise:{lane}", 0, premise_gates
            ),
            outcome=Outcome.ACCEPT,
            gates=premise_gates,
            profile=architect.PREMISE_PROFILE,
            provider=premise_spend.provider,
            model=premise_spend.model,
            fell_back_from=premise_spend.fell_back_from,
            invocations=premise_spend.invocations,
            total_tokens=premise_spend.total_tokens,
            cost_usd=premise_spend.cost_usd,
            reason=(
                f"{premise_spend.invocations} premise call(s) over {args.k} candidate(s); the "
                "premise is written as prose by its own call and never as a cell of the world "
                "schema"
            ),
        )
        store.record_decision(premise_decision, decided_at=stamp)

        screened = sum(1 for bundle in bundles if bundle["screen"].get("passed"))
        screen_gates = tuple(
            GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id=comprehension.SCREEN_PROFILE,
                passed=bool(bundle["screen"].get("passed")),
                blocking=False,
                detail=f"world {bundle['index'] + 1}: {_screen_line(bundle['screen'])}",
            )
            for bundle in bundles
        )
        screen_decision = PolicyDecision(
            decision_id=decision_id_for(
                f"forge-screen:{lane}", 0, screen_gates
            ),
            outcome=Outcome.ACCEPT,
            gates=screen_gates,
            profile=comprehension.SCREEN_PROFILE,
            provider=screen_spend.provider,
            model=screen_spend.model,
            fell_back_from=screen_spend.fell_back_from,
            invocations=screen_spend.invocations,
            total_tokens=screen_spend.total_tokens,
            cost_usd=screen_spend.cost_usd,
            reason=(
                f"{screened} of {args.k} premise(s) read by all four readers with nothing "
                "quoted as undefined; the screen refuses on a count and orders nothing"
            ),
        )
        store.record_decision(screen_decision, decided_at=stamp)
    finally:
        store.close()

    # All three, because a forge spends three times and an operator looking for what the
    # premises or the screen cost needs the row id to look them up by.
    print(decision.decision_id)
    print(f"  premise  {premise_decision.decision_id}")
    print(f"  screen   {screen_decision.decision_id}")
    print(
        f"  {args.k} world(s), {usable} clear of every gate and screened; shape {args.shape}"
    )
    spread_value = forged["spread"]
    print(f"  within-forge spread {spread_value:.4f}" if spread_value is not None else "")
    for bundle in bundles:
        note = bundle["report"]
        print(
            f"  [{bundle['index'] + 1}] {bundle['title']} — {note['domain']}, "
            f"{note['geometry']}: {note['records']} records ({note['edges']} edges), "
            f"{note['rules']} rule(s) at min {note['min_consequence_domains']} domain(s), "
            f"manifestation {note['manifestation_coverage']:.2f}, "
            f"{note['claims_with_answers']} answered claim(s)"
        )
        for complaint in note["gate_complaints"]:
            print(f"        gate: {complaint}")
        for complaint in bundle["premise_complaints"]:
            print(f"        premise: {complaint}")
        if bundle["premise_refusal"]:
            print(f"        premise: NOT WRITTEN — {bundle['premise_refusal']}")
        print(f"        screen: {_screen_line(bundle['screen'])}")
        for reader_id, quoted in sorted(
            (bundle["screen"].get("undefined_by_reader") or {}).items()
        ):
            if quoted:
                print(f"          {reader_id}: {', '.join(quoted)}")
        for complaint in note["validator_complaints"][:5]:
            print(f"        world: {complaint}")
    print(f"  {forge_path}")
    print("")
    # The candidates a person may choose among, listed rather than ordered: a screen-failed
    # premise is refused by `--pick`, so saying which ones are pickable is the difference
    # between a refusal the operator can act on and one they run into.
    pickable = [
        str(bundle["index"] + 1) for bundle in bundles if bundle["screen"].get("passed")
    ]
    print(
        f"Choose one — a person, not a model:  litharness forge --out {out} --pick <n>"
        + (f"    ({', '.join(pickable)} passed the screen)" if pickable else "")
    )
    if not pickable:
        # **`EXIT_ATTENTION`, and the alternative was an inconsistency worth naming.** The same
        # daily ceiling reached one call earlier — at the world call — prints and returns
        # `EXIT_ATTENTION`; reached during the premise or screen stages it would have exited 0
        # with a file nobody can pick from. A forge with nothing pickable is exactly what code
        # 1 is for: a fact a human should eventually see, and not an emergency.
        print("  No premise passed the screen. Forge again; a failed premise is not edited.")
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_new(args: argparse.Namespace) -> int:
    """Create an empty book of N scenes from a premise — Stage 3's entry point.

    **Every revision in this system came from `import`, and `import` needs a manuscript
    file.** So a book could only exist if someone had already written one, and §17 Stage 3
    asks for 50-80k words produced *from a premise*. `SIX_BEAT` compounded it: exactly six
    functions, and `beats_for` refuses any book that is not exactly six scenes, so even a
    hand-written 60-scene manuscript could not be planned.

    Scenes are created empty, which is what draftable means here — `gate_draft` fills an
    empty node and refuses to overwrite content. The premise becomes the one plan item the
    planner requires; without it every tick reports the book blocked.

    `--state` seeds canon the way `import` does, and for a LitRPG book it is not optional in
    practice: a book whose canon holds no status snapshot is never asked for system voice, so
    it writes none, so §12 step 5 reads nothing back. One starting sheet closes that.
    """
    stamp = _stamp(_now())
    book_id = args.book or str(uuid.uuid4())
    branch_id = args.branch or str(uuid.uuid4())
    revision = new_book(book_id, branch_id, title=args.title, scenes=args.scenes)
    # `arc_template` refuses fewer scenes than named beats, and it must refuse *before* the
    # store opens: a raise after `commit_revision` would leave the book, decision, premise
    # and seed state durably committed behind a command that reported failure.
    template = arc_template(args.scenes)

    # Attributed like every other mutation (§19). An author's act, so no gate results: the
    # only check that runs is the scene count, and it raises before a decision exists.
    decision = PolicyDecision(
        decision_id=decision_id_for(f"new:{revision.revision_id}", 0, ()),
        outcome=Outcome.ACCEPT,
        resulting_revision_id=revision.revision_id,
        reason=f"created {args.scenes} empty scene(s) from a premise",
    )
    premise = lc.PlanItem(
        logical_id="plan-premise",
        kind=lc.PlanKind.PREMISE,
        text=args.premise,
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    # **A debt with a settlement date, seeded before the first scene exists.** The measured
    # defect is the project's oldest: 40 promises opened and 0 paid on the live serial, 32 and 0
    # before it — every one of them opened by the summary handler out of a scene that had just
    # been written, with nothing anywhere holding the answer. A forged reveal arrives with its
    # answer in canon and its scene here, so the ledger has something to pay with. It also makes
    # `open_promises` non-empty at the book's *first* outline, which is the guard that made
    # `_payoff_windows` unreachable on pass one.
    #
    # Keys come from `beats_for`, never from a format string: `Beat.story_order_key` derives its
    # width from the scene count and a hand-padded key would sort wrong against the book's own.
    # A non-chronological template mints none, and then this abstains rather than guessing.
    promise_rows: list[Promise] = []
    if args.promises:
        entries = json.loads(Path(args.promises).read_text(encoding="utf-8"))
        keys = [beat.story_order_key for beat in beats_for(revision, template)]
        if keys and all(key is not None for key in keys):
            opened_key = str(keys[0])
            final_key = str(keys[-1])
            for entry in entries if isinstance(entries, list) else ():
                subject = extraction.normalise_subject(str(entry.get("subject") or ""))
                description = str(entry.get("description") or "").strip()
                if not subject or not description:
                    continue
                # **A debt the serial settles later has no due date in *this* book, and
                # pretending otherwise makes it overdue on the last page.** Measured on Serial
                # Pilot 2: the forged world scheduled reveals at scenes 4, 7, 26, 41, 63 and 92,
                # and clamping the last four to the final beat would have `promise.overdue.v0`
                # annotate four arc debts as late in a two-chapter opening that was never going
                # to reach them. `Promise.due_key` is `str | None` and `overdue_promises` skips
                # a row with none, so the honest encoding already exists: the debt is on the
                # ledger, it reaches the packet as something owed, and nothing calls it late.
                due = entry.get("due_scene")
                inside = (
                    isinstance(due, int)
                    and not isinstance(due, bool)
                    and 1 <= due <= len(keys)
                )
                due_key = str(keys[due - 1]) if inside else None
                if due is None:
                    due_key = final_key
                promise_rows.append(
                    Promise(
                        promise_id=promise_id_for(book_id, subject),
                        subject=subject,
                        description=description,
                        opened_at_key=opened_key,
                        due_key=due_key,
                        opened_by_revision=revision.revision_id,
                        # No model wrote this row and the ledger has no column that says so.
                        # `model` is empty rather than filled with a lie, and the limit is
                        # stated here rather than discovered later: `promise.overdue.v0` reads
                        # every row as model-sourced because most are.
                        model="",
                        kind=normalise_kind(entry.get("kind")),
                    )
                )

    records: list[lc.StateRecord] = []
    graph_fault: str | None = None
    if args.state:
        snapshot = lc.parse_artifact(
            lc.StateSnapshot, json.loads(Path(args.state).read_text(encoding="utf-8"))
        )
        records = list(import_state(snapshot, book_id=book_id, branch_id=branch_id).records)
        # **A sheet the extractor cannot build a line from is refused before the book
        # exists.** Falling back to the default would ask every scene for a form this book's
        # own canon does not use, so it would extract nothing and look exactly like a book
        # that established nothing — the silence `domain/extraction.py` says no gate catches.
        # Raised here, where the only cost is a command that did nothing.
        try:
            extraction.sheet_for(records)
        except extraction.MalformedSheet as error:
            raise SystemExit(f"litharness: {args.state}: {error}") from error
        # **Reported rather than refused, and the asymmetry with the sheet is deliberate.** A
        # malformed sheet is dangerous because a default waits behind it, so the book would be
        # read in a form its own canon does not use. A graph line has no default: the fallback
        # is "this book has no graph line", which most books are in and which costs nothing.
        # So this is a lost capability, not a corrupted one — and the operator hears about it
        # here, at the one moment when doing something about it is free.
        graph_fault = extraction.graph_line_fault(records)

    store = _store(args)
    try:
        store.record_decision(decision, decided_at=stamp)
        store.commit_revision(
            revision,
            created_at=stamp,
            events=[
                Event(
                    event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision.revision_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "created": True,
                        "scenes": args.scenes,
                        "title": args.title,
                    },
                )
            ],
        )
        store.record_plan_items(
            book_id,
            branch_id,
            [premise],
            created_at=stamp,
            events=[
                Event(
                    event_type=EventType.PLAN_CHANGED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision.revision_id,
                    payload={"items": 1, "premise": True},
                )
            ],
        )
        if records:
            store.record_state_records(
                book_id, branch_id, records, created_at=stamp
            )
        for promise in promise_rows:
            store.record_promise(book_id, branch_id, promise)
    finally:
        store.close()

    print(revision.revision_id)
    print(f"  book={book_id} branch={branch_id}")
    print(f"  {args.scenes} empty scene(s); template {template.template_id}")
    print(f"  {len(records)} seed state record(s)")
    if promise_rows:
        print(f"  {len(promise_rows)} seeded promise(s), each with an answer already in canon")
    if graph_fault:
        print(f"  graph line declared and UNUSABLE, so this book has none: {graph_fault}")
    if not records:
        print("  no state seeded — a LitRPG book needs a starting sheet to speak system voice")
    return EXIT_OK


def cmd_propagate(args: argparse.Namespace) -> int:
    """What a change reaches beyond what it edits (§17 Stage 2's propagation engine).

    A `ChangeSet` is read from a file of the shared schema, exactly as `ingest` reads an
    `EvaluationArtifact` — §13 keeps a sibling's output a contract rather than an import, and
    nothing in this repo yet derives semantic changes from an accepted revision, so the
    producer is outside it by construction as well as by design.

    **Reporting and acting are separate.** The report costs nothing; `--enqueue` costs model
    calls over a book the operator may not want re-checked yet. Only manuscript nodes are
    enqueued: nothing in this system re-evaluates a state record, and a job naming one would
    park for want of a handler.

    **An unreadable change exits non-zero.** `pov_changed`, `plan_changed` and `rule_changed`
    are in the contract's vocabulary and have no rule here, so an empty result for one of them
    means "nobody looked" — which must not print the same as a change that was read and
    reached nothing. This is `ingest`'s incomplete-evaluation rule applied to the same class
    of silence.
    """
    change_set = lc.parse_artifact(
        lc.ChangeSet, json.loads(args.path.read_text(encoding="utf-8"))
    )
    stamp = _stamp(_now())
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        if head is None:
            print(f"litharness: no revision on {book_id}/{branch_id}", file=sys.stderr)
            return EXIT_FAULT
        result = propagation.propagate(
            change_set,
            propagation.book_from(head, store.state_records(book_id, branch_id)),
        )
        # Manuscript nodes only, and derived from the head rather than from the prediction:
        # a change set may name a state record or an entity, and neither is a thing a
        # revision can be evaluated at.
        nodes = sorted(
            logical_id
            for logical_id in result.logical_ids
            if any(node.logical_id == logical_id for node in head.nodes)
        )
        queued = 0
        if args.enqueue:
            for logical_id in nodes:
                queued += int(
                    store.enqueue(
                        evaluation_job_for(
                            book_id=book_id,
                            branch_id=branch_id,
                            revision_id=head.revision_id,
                            logical_id=logical_id,
                        )
                    )
                )
        store.append_events(
            [
                Event(
                    event_type=EventType.IMPACT_ANALYZED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=head.revision_id,
                    payload={
                        "change_set_id": change_set.change_set_id,
                        "reached": len(result.logical_ids),
                        "nodes": nodes,
                        "complete": result.complete,
                        "unhandled": list(result.unhandled),
                        "enqueued": queued,
                    },
                )
            ]
        )
    finally:
        store.close()

    for target in sorted(result.targets, key=lambda item: (item.rule, item.logical_id)):
        print(f"{target.logical_id:<28} {target.rule}")
        print(f"    {target.reason}")
    if not result.targets:
        print("this change reaches nothing beyond what it edits")
    print(
        f"({len(result.logical_ids)} reached, {len(nodes)} of them draftable node(s); "
        f"{queued} evaluation(s) enqueued)"
    )
    if nodes and not args.enqueue:
        print("  `--enqueue` queues an evaluation for each; without it this only reports")
    if not result.complete:
        print(
            f"  INCOMPLETE: no rule reads {', '.join(result.unhandled)} — this change was "
            "not analysed, which is not the same as it reaching nothing",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    return EXIT_OK


def _proposal_row(stored: StoredPlanProposal) -> dict[str, Any]:
    """The proposal behind one plan revision. A revision no proposal produced reads as null,
    which is the root of the lineage rather than a step whose proposal went missing."""
    return {
        "proposal_id": stored.proposal.proposal_id,
        "summary": stored.proposal.summary,
        "rollback_of": stored.proposal.rollback_of,
        "directives": [reading.directive_id for reading in stored.proposal.readings],
    }


def cmd_plans(args: argparse.Namespace) -> int:
    """The plan's lineage, newest first, and the proposal that produced each step.

    **`plan_history` had no caller outside the tests**, which is the shape §19.1 keeps
    recording: the only way to read what direction had done to a book was to open the SQLite
    file. It is the read half of `revert-plan` — an operator cannot restore a revision they
    cannot see, and a lineage of bare content hashes would not tell them which one to pick,
    so each is printed with the summary of the change that made it.

    A revision no proposal produced is the plan the book was imported with. Saying so
    distinguishes "the root" from "a step whose proposal is missing", which are the same
    blank line otherwise.
    """
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        history = store.plan_history(book_id, branch_id)
        proposals = store.plan_proposals(book_id, branch_id)
    finally:
        store.close()

    applied = {
        stored.resulting_plan_revision_id: stored
        for stored in proposals
        if stored.status is PlanProposalStatus.APPLIED
    }
    conflicted = [item for item in proposals if item.status is PlanProposalStatus.CONFLICTED]
    if args.json:
        print(
            json.dumps(
                {
                    "book_id": book_id,
                    "branch_id": branch_id,
                    "revisions": [
                        {
                            "plan_revision_id": revision.plan_revision_id,
                            "head": index == 0,
                            "items": len(revision.items),
                            "locked": sum(1 for item in revision.items if item.locked),
                            "proposal": None
                            if applied.get(revision.plan_revision_id) is None
                            else _proposal_row(applied[revision.plan_revision_id]),
                        }
                        for index, revision in enumerate(history)
                    ],
                    "conflicted": [
                        {
                            "proposal_id": item.proposal.proposal_id,
                            "error": item.error or "conflicted",
                        }
                        for item in conflicted
                    ],
                },
                indent=2,
            )
        )
        return EXIT_OK
    for index, revision in enumerate(history):
        locked = sum(1 for item in revision.items if item.locked)
        print(
            f"{revision.plan_revision_id}  {'HEAD' if index == 0 else '    '}  "
            f"{len(revision.items)} item(s), {locked} locked"
        )
        stored = applied.get(revision.plan_revision_id)
        if stored is None:
            print("    imported; no proposal produced it, and nothing precedes it")
            continue
        print(f"    {stored.proposal.summary}")
        if stored.proposal.rollback_of:
            print(f"    a rollback of {stored.proposal.rollback_of}")
        directives = [reading.directive_id for reading in stored.proposal.readings]
        if directives:
            print(f"    from directive {', '.join(directives)}")

    print(f"({len(history)} revision(s), {len(conflicted)} proposal(s) that did not apply)")
    for item in conflicted:
        print(f"  {item.proposal.proposal_id}  {item.error or 'conflicted'}")
    if len(history) > 1:
        print("  `litharness revert-plan <id>` restores one of these as a new head")
    return EXIT_OK


def cmd_revert_plan(args: argparse.Namespace) -> int:
    """Restore an earlier plan revision as the new head (§19 reversibility, for plans).

    **`domain/plan_refinement.rollback_proposal` was implemented, tested, documented — and
    unreachable.** Nothing in `src/` called it, so §19's "every mutation is reversible" held
    for prose, which has `revert`, and not for the plans that produce it. This is the same
    defect family as `reset_health` and `bump_plan_epoch`: a promise whose only caller is a
    test.

    Forward, exactly like `revert`. The restored plan is a *new* revision whose content
    matches the target, so the change being undone and the undoing both stay in the lineage,
    and rolling back a rollback composes. A rollback is also the one proposal permitted to
    move a **locked** item — that is what makes it able to undo a director's constraint —
    so the count of locked items it moved is reported rather than left to be discovered.

    It does not touch prose. Accepting the restored plan advances the branch's plan epoch
    and cancels queued scene jobs in the same transaction, so the next tick plans the
    still-draftable beats against the restored plan; scenes already accepted under the old
    one stay accepted, and `revert` is the verb for those.
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        current = store.plan_revision(book_id, branch_id)
        if current is None:
            print("litharness: this branch has no plan to restore", file=sys.stderr)
            return EXIT_FAULT
        try:
            target = store.plan_revision_for_id(args.plan_revision)
        except KeyError:
            # A mistyped id is a bad argument, which the exit-code contract calls a fault.
            # Letting the KeyError escape would exit 1 — "a unit needs a human" — which is
            # the defect the locked-database handler was added for.
            print(
                f"litharness: no plan revision {args.plan_revision}; "
                "`litharness plans` lists them",
                file=sys.stderr,
            )
            return EXIT_FAULT
        undoing = next(
            (
                stored
                for stored in store.plan_proposals(book_id, branch_id)
                if stored.status is PlanProposalStatus.APPLIED
                and stored.resulting_plan_revision_id == current.plan_revision_id
            ),
            None,
        )
        if undoing is None:
            # The head is the imported root, so the lineage is one revision long and the
            # only reachable target is the head itself. Saying that beats letting the
            # operator meet a proposal error about a baseline they never chose.
            print(
                "litharness: the plan head is the one the book was imported with; "
                "nothing precedes it to restore",
                file=sys.stderr,
            )
            return EXIT_FAULT
        proposal = rollback_proposal(
            current, target, rollback_of=undoing.proposal.proposal_id
        )
        application = accept_plan_proposal(
            store,
            proposal,
            project_id=args.project,
            created_at=stamp,
            actor=args.holder,
        )
        # A constraint minted from a directive can be rolled back out from under it: the
        # directive stays APPLIED and goes on citing a plan item that no longer exists.
        # That is recoverable — the direction is still on record and can be resubmitted —
        # but only if the operator is told, rather than finding out when the book drafts
        # without the constraint they thought was in force.
        restored_ids = {item.logical_id for item in application.after.items}
        orphaned = [
            directive.directive_id
            for directive in store.directives_by_status(DirectiveStatus.APPLIED)
            if directive.book_id in {None, book_id}
            and directive.branch_id in {None, branch_id}
            and set(directive.produced_constraint_ids) - restored_ids
        ]
    finally:
        store.close()

    tally = Counter(edit.action.value for edit in application.applied_edits)
    moved_locked = sum(
        1
        for edit in application.applied_edits
        if (edit.before is not None and edit.before.locked)
        or (edit.after is not None and edit.after.locked)
    )
    print(
        f"restored {target.plan_revision_id[:12]} as new plan revision "
        f"{application.after.plan_revision_id[:12]}"
    )
    print(
        f"  {len(application.applied_edits)} item(s) changed: "
        + ", ".join(f"{count} {action}" for action, count in sorted(tally.items()))
    )
    print("  the plan epoch advanced; the next tick replans the still-draftable beats")
    if moved_locked:
        print(
            f"  {moved_locked} locked item(s) moved — a rollback is the only proposal "
            "permitted to, which is what lets it undo a director's constraint"
        )
    if orphaned:
        print(
            f"  {len(orphaned)} applied directive(s) now cite a plan item the restored plan "
            f"does not have: {', '.join(orphaned)}"
        )
        print("    the direction is still on record; resubmit it if it should still hold")
        return EXIT_ATTENTION
    return EXIT_OK


def cmd_revert(args: argparse.Namespace) -> int:
    """Restore an earlier revision's content as a new head (§19 reversibility).

    Forward, never backward: the mistake and the correction both stay in the record.
    """
    store = _store(args)
    try:
        reverted = store.revert(
            args.book,
            args.branch,
            args.revision,
            created_at=_stamp(_now()),
            project_id=args.project,
            actor=args.holder,
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

    # The plan travels with the manuscript. Importing one without the other produces a book
    # the planner cannot draft — `premise_of` returns None and every tick reports the book
    # blocked — so they are one operation, and a fixture without a readable plan says so
    # rather than importing half a book.
    plan_items: list[lc.PlanItem] = []
    plan_source: str | None = None
    plans_path = args.plans or (
        contracts_fixtures.fixture_plans(args.fixture) if args.fixture else None
    )
    if plans_path is not None:
        snapshot = lc.parse_artifact(
            lc.PlanSnapshot, json.loads(Path(plans_path).read_text(encoding="utf-8"))
        )
        plan = import_plan(
            snapshot, book_id=revision.book_id, branch_id=revision.branch_id
        )
        plan_items, plan_source = list(plan.items), plan.source_revision_id

    # Objective story state travels with the manuscript for the same reason the plan does,
    # and it is the third of the three artifacts a golden book ships. It is *optional* where
    # the plan is not: a book without a premise cannot be drafted at all, while a book
    # without state records drafts with a thinner packet — worse, but not blocked. A
    # regenerated book starts with none by definition, since records are extracted from
    # accepted prose.
    state_records: list[lc.StateRecord] = []
    state_source: str | None = None
    state_path = args.state or (
        contracts_fixtures.fixture_state(args.fixture) if args.fixture else None
    )
    if state_path is not None:
        state_snapshot = lc.parse_artifact(
            lc.StateSnapshot, json.loads(Path(state_path).read_text(encoding="utf-8"))
        )
        imported_state = import_state(
            state_snapshot, book_id=revision.book_id, branch_id=revision.branch_id
        )
        state_records = list(imported_state.records)
        state_source = imported_state.source_revision_id

    store = _store(args)
    try:
        # Decision first, then the revision — the same order as the draft handler, for the
        # same reason: a crash between them leaves a decision pointing at a revision that
        # does not exist, which is detectable and harmless, rather than a revision no
        # decision explains, which is the thing §19 forbids.
        store.record_decision(decision, decided_at=stamp)
        store.commit_revision(revision, created_at=stamp, events=[accepted])
        if plan_items:
            store.record_plan_items(
                revision.book_id,
                revision.branch_id,
                plan_items,
                created_at=stamp,
                source_revision_id=plan_source,
                events=[
                    Event(
                        event_type=EventType.PLAN_CHANGED,
                        project_id=args.project,
                        created_at=stamp,
                        actor=args.holder,
                        book_id=revision.book_id,
                        branch_id=revision.branch_id,
                        revision_id=revision.revision_id,
                        payload={
                            "items": len(plan_items),
                            "source_revision_id": plan_source,
                        },
                    )
                ],
            )
        if state_records:
            store.record_state_records(
                revision.book_id,
                revision.branch_id,
                state_records,
                created_at=stamp,
                source_revision_id=state_source,
                events=[
                    Event(
                        event_type=EventType.STATE_RECORDS_ACCEPTED,
                        project_id=args.project,
                        created_at=stamp,
                        actor=args.holder,
                        book_id=revision.book_id,
                        branch_id=revision.branch_id,
                        revision_id=revision.revision_id,
                        payload={
                            "records": len(state_records),
                            "source_revision_id": state_source,
                            # Accepted on the director's authority, not extracted from prose
                            # this system generated. Recorded because the distinction is the
                            # whole of what §12 step 5 will add, and an event log that did
                            # not say so would make the two indistinguishable later.
                            "extracted": False,
                        },
                    )
                ],
            )
    finally:
        store.close()

    print(revision.revision_id)
    print(f"  book={revision.book_id} branch={revision.branch_id}")
    print(f"  {len(revision.nodes)} node(s) from {imported.source_revision_id[:12]}")
    print(f"  {len(imported.cleared)} scene(s) cleared and draftable")
    if plan_items:
        premise = premise_of(plan_items)
        print(f"  {len(plan_items)} plan item(s); premise: {'yes' if premise else 'MISSING'}")
    else:
        print("  no plan imported — the planner will report this book blocked")
    if state_records:
        threads = len(state_mod.open_threads(state_records))
        restricted = sum(1 for record in state_records if record.pov_visibility)
        print(
            f"  {len(state_records)} state record(s); {threads} open thread(s), "
            f"{restricted} POV-restricted"
        )
    else:
        print("  no state imported — scenes draft against plan and prose only")
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


#: Output formats by destination suffix. `--format` overrides; markdown is the fallback
#: for stdout and for a destination whose name says nothing.
_FORMATS = {".md": "markdown", ".markdown": "markdown", ".html": "html", ".htm": "html"}


def _write_document(destination: Path | None, text: str) -> None:
    """Write the document, in UTF-8, whether it goes to a file or to stdout.

    Both halves are explicit for the same reason `import` reads explicitly: the default
    encoding on this platform is cp1252, which cannot represent an em-dash — and a book is
    made of them. To a file that would raise; to a *redirected* stdout it would also raise,
    so `litharness export > book.md` would die on the first scene that used one. `print`
    goes through the console's own codec, so the bytes are written here instead.
    """
    if destination is not None:
        destination.write_text(text, encoding="utf-8")
        return
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:  # a capturing or text-only stdout, e.g. under pytest's capsys
        print(text)
        return
    sys.stdout.flush()
    stream.write(text.encode("utf-8"))
    stream.flush()


def _library_root(args: argparse.Namespace) -> Path:
    """Where this run's library lives: `--library` if given, else beside the database.

    Beside the database rather than under the working directory, which is what makes
    publishing safe to have on by default — nothing writes a folder into whatever directory a
    command happened to be run from, and a test against a temporary database takes its output
    away with it.
    """
    return args.library or library_module.root_for(args.database)


def _publish_library(
    args: argparse.Namespace, store: SqliteStore
) -> tuple[Path, tuple[library_module.PublishedBook, ...]]:
    """Republish, returning where and what. Shared by `library` and every tick."""
    root = _library_root(args)
    return root, library_module.publish(
        store,
        root=root,
        generated_at=_stamp(_now()),
        scenes_per_chapter=args.chapter_scenes,
        force=getattr(args, "force", False),
    )


def cmd_library(args: argparse.Namespace) -> int:
    """Republish the library: reading copies, pastable chapters, and the index.

    Not called `publish`, and the name is doing work. §62 settled what publication means here
    — the export, run when the book clears §1a.5's bar (the continuation one, §126) — and no book
    has cleared it. A verb
    called `publish` would make a claim the tool is in no position to make; this one writes
    files and says so.
    """
    store = _store(args)
    try:
        root, published = _publish_library(args, store)
        for book in published:
            held = f", {book.withheld} chapter(s) withheld" if book.withheld else ""
            state = "rewritten" if book.rewritten else "already current"
            print(
                f"{root / book.slug}  {book.title}  {book.summary}  "
                f"{len(book.chapters)} pastable chapter(s){held}  [{state}]"
            )
        if not published:
            print("(no book in this store yet)")
        print(f"{root / 'README.md'}: the index")
    finally:
        store.close()
    return EXIT_OK


def cmd_export(args: argparse.Namespace) -> int:
    """A reading copy of the book as it stands, and its listing beside it.

    See `application/export.py`. Writing to a file also writes `overview.txt` next to it
    when the book has a premise, which is what `new --premise` stores and what the listing
    written by `application/overview.py` becomes. The operator asked for it as its own file;
    it was already inside the document, where a site's description field cannot reach it.

    Not a PDF: the output is Markdown or print-ready HTML, and `pandoc book.md -o book.pdf`
    or a browser's "Save as PDF" is the last step. That keeps font metrics and page breaking
    out of a repository whose only runtime dependency is its own contracts package.
    """
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        document = export_module.collect(
            store,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=args.revision,
            generated_at=_stamp(_now()),
        )
    finally:
        store.close()

    suffix = args.destination.suffix.lower() if args.destination else ""
    fmt = args.format or _FORMATS.get(suffix, "markdown")
    _write_document(
        args.destination, document.as_html() if fmt == "html" else document.as_markdown()
    )
    if args.destination is not None:
        # Only when the document went to a file — on stdout this would land in the middle
        # of the book.
        print(f"{args.destination}: {document.summary}")
        print(f"  {fmt} from revision {document.revision_id[:12]}")
        if document.premise:
            # **The listing, on its own, beside the book.** It is already inside the
            # document — `Document.premise` renders it as a blockquote in both formats —
            # but the thing a reader meets first is the thing most often wanted on its own,
            # and a hundred words buried in a blockquote at the top of a novel is not that.
            # Plain text because a listing is what a site's description field takes.
            overview = args.destination.with_name("overview.txt")
            overview.write_text(document.premise.strip() + "\n", encoding="utf-8")
            print(f"  {overview}: {len(document.premise.split())} words")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    """Rebuild every revision from canonical records — §19's integrity check.

    Reports attribution as well as reconstruction. §19's Integrity clause is one sentence
    covering both, and only the reconstruction half was ever checked: `revert` committed
    revisions no decision explained, and nothing would have said so.
    """
    store = _store(args)
    try:
        count = store.verify_integrity()
        unattributed = store.unattributed_revisions()
    finally:
        store.close()
    print(f"{count} revision(s) rebuild cleanly")
    if unattributed:
        print(f"{len(unattributed)} revision(s) no policy decision explains:")
        for revision_id in unattributed:
            print(f"  {revision_id}")
        return EXIT_ATTENTION
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
        default=Path(os.environ.get(DATABASE_ENV, DEFAULT_DB)),
        help=(
            "SQLite database path "
            f"(default: ${DATABASE_ENV}, else {DEFAULT_DB})"
        ),
    )
    parser.add_argument(
        "--holder",
        default="session",
        help="identity recorded on tick ids and job leases (default: session)",
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
    parser.add_argument(
        "--continuity-evaluator-command",
        type=Path,
        default=os.environ.get("LITHARNESS_CONTINUITY_EVALUATOR"),
        help="ContinuityEvaluation executable; also read from LITHARNESS_CONTINUITY_EVALUATOR",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=(
            Path(os.environ["LITHARNESS_LIBRARY"])
            if os.environ.get("LITHARNESS_LIBRARY")
            else None
        ),
        help=f"where the library lives; also read from LITHARNESS_LIBRARY. Defaults to "
        f"{library_module.LIBRARY_DIRNAME}/ BESIDE THE DATABASE rather than under the "
        "working directory, because the library is derived from one store and belongs with "
        "it",
    )
    parser.add_argument(
        "--no-library",
        action="store_true",
        default=_env_flag("LITHARNESS_NO_LIBRARY"),
        help="do not republish after a tick. On by default is the point: a reading copy you "
        "have to remember to ask for is one nobody has. A book whose head has not moved is "
        "skipped, so a quiet system rewrites nothing",
    )
    parser.add_argument(
        "--context-budget",
        type=int,
        default=None,
        help="tokens of context a scene is drafted against. The default is 200,000 (§132) and "
        "does not bind for any book this project has produced; it exists for a long serial. "
        "Lower it to make the packet evict on purpose",
    )
    parser.add_argument(
        "--target-words",
        type=int,
        default=None,
        help="how long a scene to ask the generator for. A target, not a gate: nothing "
        "refuses a scene for missing it, and it is recorded in every decision's policy "
        "digest because it shapes every scene in the book",
    )
    parser.add_argument(
        "--no-outline",
        action="store_true",
        default=_env_flag("LITHARNESS_NO_OUTLINE"),
        help="do not plan a statement for each scene before drafting; also read from "
        "LITHARNESS_NO_OUTLINE. The right flag for a book somebody outlines by hand — a "
        "scene with no statement drafts exactly as it did before outlines existed. "
        "(Formerly §54's control arm; that measurement concluded, §57/§65)",
    )
    parser.add_argument(
        "--chapter-scenes",
        type=int,
        default=1,
        help="how many scenes make one chapter, and the position each scene is told "
        "it holds when it is drafted. One by default, which asserts nothing: production books "
        "hold no chapter nodes and no assembly scheme is decided, so grouping is an operator "
        "act rather than a guess the tool makes. Above one, the drafting prompt carries "
        "`Chapter c, scene k of n` and nothing else about it - where the scene sits, never "
        "what to do there",
    )
    parser.add_argument(
        "--director",
        default=os.environ.get("LITHARNESS_DIRECTOR", ""),
        help="run this registered Director (name or id): a personality that says what the "
        "book is about, one directive per six accepted scenes, and never a word about the "
        "prose; also read from LITHARNESS_DIRECTOR. Off by default — a director is an arm "
        "and no director is its control (plan/director-role.md §6). An unregistered name is "
        "refused rather than ignored",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    tick = sub.add_parser("tick", help="run one bounded unit of work")
    tick.set_defaults(func=cmd_tick)

    status = sub.add_parser("status", help="queue depth, attention counts, digest and spend")
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
    directive.add_argument("--book", help="limit direction to this book")
    directive.add_argument("--branch", help="limit direction to this branch")
    directive.set_defaults(func=cmd_directive)

    directives = sub.add_parser("directives", help="list captured direction")
    directives.add_argument(
        "--status",
        default=DirectiveStatus.RECEIVED.value,
        choices=[state.value for state in DirectiveStatus],
    )
    directives.set_defaults(func=cmd_directives)

    directors_cmd = sub.add_parser(
        "directors", help="admitted director personalities, or admit one"
    )
    directors_cmd.add_argument(
        "--register",
        help="admit a personality by name: a built-in, or a new one with --brief",
    )
    directors_cmd.add_argument(
        "--brief",
        help="the standing instruction, about the story and never about the prose",
    )
    directors_cmd.set_defaults(func=cmd_directors)

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
        "--plans",
        type=Path,
        help="a plans.json to import alongside; implied by --fixture. Without a premise "
        "the planner reports the book blocked rather than drafting it",
    )
    importer.add_argument(
        "--state",
        type=Path,
        help="a state.json to import alongside; implied by --fixture. Open threads and "
        "POV-visible knowledge for the context packet — without it scenes draft against "
        "the plan and prior prose only",
    )
    importer.add_argument(
        "--keep-content",
        action="store_true",
        help="keep the source prose; the result has no draftable scene, so this is for "
        "inspection and not for generation",
    )
    importer.set_defaults(func=cmd_import)

    findings = sub.add_parser(
        "findings", help="what the evaluators say is wrong, worst severity first"
    )
    findings.add_argument("--book")
    findings.add_argument("--branch")
    findings.add_argument("--node", help="only findings landing on this logical id")
    findings.add_argument(
        "--all",
        action="store_true",
        help="include closed and dismissed findings, not just the unresolved ones",
    )
    findings.add_argument("--json", action="store_true", help="machine-readable output")
    findings.set_defaults(func=cmd_findings)

    ingest = sub.add_parser(
        "ingest", help="take an evaluator's EvaluationArtifact into the findings store"
    )
    ingest.add_argument("path", type=Path, help="an EvaluationArtifact JSON file")
    ingest.add_argument("--book")
    ingest.add_argument("--branch")
    ingest.set_defaults(func=cmd_ingest)

    dismiss = sub.add_parser(
        "dismiss", help="mark a finding intentional, so a deliberate device stops blocking"
    )
    dismiss.add_argument("finding_id")
    dismiss.add_argument(
        "--false-positive",
        action="store_true",
        help="the detector was wrong, rather than the device being deliberate",
    )
    dismiss.set_defaults(func=cmd_dismiss)

    why = sub.add_parser(
        "why",
        help="one scene's dossier: the prompt it was sent, the decision that took it, and "
        "everything recorded beside them",
    )
    why.add_argument(
        "--scene",
        required=True,
        help="a scene's logical id, or its 1-based place in reading order",
    )
    why.add_argument("--book")
    why.add_argument("--branch")
    why.add_argument("--json", action="store_true", help="machine-readable output")
    why.set_defaults(func=cmd_why)

    events = sub.add_parser(
        "events", help="the event log in write order - what happened, across every table"
    )
    events.add_argument(
        "--since",
        help="a sequence number from an earlier read's cursor line, or an ISO-8601 instant",
    )
    events.add_argument(
        "--type",
        action="append",
        choices=[member.value for member in EventType],
        help="only this event type; repeatable",
    )
    events.add_argument("--book", help="only events carrying this book id")
    events.add_argument(
        "--limit", type=int, default=50, help="how many to print; 0 for all (default: 50)"
    )
    events.add_argument("--json", action="store_true", help="machine-readable output")
    events.set_defaults(func=cmd_events)

    new = sub.add_parser(
        "new", help="create an empty book of N scenes from a premise (Stage 3's entry point)"
    )
    new.add_argument("title")
    new.add_argument("--premise", required=True, help="what the book is about; the planner "
                     "reports a book without one as blocked rather than drafting it")
    new.add_argument("--scenes", type=int, default=len(SIX_BEAT),
                     help="how many scenes to create, all empty and draftable")
    new.add_argument("--state", type=Path, help="a StateSnapshot to seed canon with")
    new.add_argument(
        "--promises",
        type=Path,
        help="debts to open before scene one, each with a due scene; the answers live in the "
        "seed snapshot. Without it the ledger only ever holds what a scene invented",
    )
    new.add_argument("--book", help="book id; a fresh uuid by default")
    new.add_argument("--branch", help="branch id; a fresh uuid by default")
    new.set_defaults(func=cmd_new)

    forge = sub.add_parser(
        "forge",
        help="build K worlds from a brief, gate them, and stop — the Architect "
        "(plan/world-architect.md)",
    )
    forge.add_argument(
        "brief",
        nargs="?",
        default="",
        help="a genre, a real domain, a mood, or nothing. Nothing is legitimate and is the "
        "control a directed forge is read against",
    )
    forge.add_argument(
        "--k",
        type=int,
        default=architect.DEFAULT_K,
        help="how many worlds to forge in one call; the collapse gate refuses a K-way collapse",
    )
    forge.add_argument(
        "--shape",
        choices=list(architect.PROMPT_SHAPES),
        default=architect.DIRECT,
        help="which prompt shape to use; which one measures better is a question, not a setting",
    )
    forge.add_argument(
        "--out",
        type=Path,
        default=Path("forge"),
        help="where the candidates and the chosen seed are written",
    )
    forge.add_argument(
        "--pick",
        type=int,
        help="choose one of the forged worlds. A person's act: it makes no provider call, no "
        "model ranks anything, and the choice is recorded as its own decision",
    )
    forge.add_argument(
        "--scenes",
        type=int,
        default=None,
        help="how many scenes the book being forged for has. Story keys are minted at this "
        f"width (default {architect.DEFAULT_SCENES}), and the forge records it — so `--pick` "
        "takes the forged width when this is omitted, and refuses when it is given and "
        "disagrees",
    )
    forge.set_defaults(func=cmd_forge)

    state = sub.add_parser(
        "state", help="what this book holds as true, in story order"
    )
    state.add_argument("--subject", help="one subject's records, e.g. a character id")
    state.add_argument("--predicate", help="one predicate, e.g. status_snapshot")
    state.add_argument("--book")
    state.add_argument("--branch")
    state.set_defaults(func=cmd_state)

    characters = sub.add_parser(
        "characters", help="everything canon holds about each person, one sheet each"
    )
    characters.add_argument("--subject", help="one character id")
    characters.add_argument("--csv", type=Path, help="write the cast as a table")
    characters.add_argument("--json", action="store_true")
    characters.add_argument("--book")
    characters.add_argument("--branch")
    characters.set_defaults(func=cmd_characters)

    # The Architect's tool suite. One parser per view rather than a single `--view` flag,
    # because an agent reads `--help` to find out what it can do and a flag with seven
    # values documents itself as one thing.
    world = sub.add_parser(
        "world", help="ask this world a question, or declare something new in it"
    )
    world_sub = world.add_subparsers(dest="view", required=True)
    for name, helptext in (
        ("summary", "how big this world is and where the holes are"),
        ("show", "every declaration, in story order, with provenance"),
        ("rules", "the declared rules and the domains their consequences reach"),
        ("ladders", "ordinal criteria, their rungs lowest-first, and who stands where"),
        ("abilities", "what a person can do here, and who holds what"),
        ("cast", "who is in this world, by role, and who the protagonist is"),
        ("threads", "open questions, where each is answered, what is still untold"),
        ("vocabulary", "every predicate and role this world's language admits"),
        ("presence", "which coined names have reached the page and which have not"),
        ("check", "what is wrong by arithmetic; exits 1 when anything is"),
    ):
        view = world_sub.add_parser(name, help=helptext)
        view.add_argument("--book")
        view.add_argument("--branch")
        view.add_argument("--json", action="store_true", help="ignored; output is JSON")
        if name == "show":
            view.add_argument("--subject", help="one subject id")
        if name == "abilities":
            view.add_argument("--holder", help="one subject id")
        if name == "threads":
            view.add_argument("--at", help="a story position; what is open as of there")
        view.set_defaults(func=cmd_world)

    declare = world_sub.add_parser(
        "declare", help="offer this world a new record (PROPOSED, never canon)"
    )
    declare.add_argument("subject")
    declare.add_argument("predicate")
    declare.add_argument("--value")
    declare.add_argument("--object", help="another subject id, for a relationship")
    declare.add_argument("--order-key", dest="order_key", help="where in story time")
    declare.add_argument("--note")
    declare.add_argument("--json", action="store_true")
    declare.add_argument("--book")
    declare.add_argument("--branch")
    declare.set_defaults(func=cmd_world)

    accept = world_sub.add_parser(
        "accept",
        help="accept every proposal on this branch into canon, as one decision",
    )
    accept.add_argument(
        "--force",
        action="store_true",
        help="accept even where the world contradicts itself",
    )
    accept.add_argument("--json", action="store_true")
    accept.add_argument("--book")
    accept.add_argument("--branch")
    accept.set_defaults(func=cmd_world)

    # `arch`, not `architect`: the module of that name is imported at the top of this file
    # and a local would shadow it inside this function.
    arch = sub.add_parser(
        "architect",
        help="put the Architect on this world, holding the world suite and nothing else",
    )
    architect_sub = arch.add_subparsers(dest="job", required=True)

    prompts = sub.add_parser(
        "prompts", help="what each role is actually told, and how much of it there is"
    )
    prompts.add_argument("--role", help="print one role in full")
    prompts.add_argument("--writer", help=f"one of: {', '.join(writers_domain.CAST)}")
    prompts.add_argument("--json", action="store_true")
    prompts.set_defaults(func=cmd_prompts)

    seed = architect_sub.add_parser(
        "seed", help="build enough world to stand the first chapters, under a listing"
    )
    seed.add_argument("--overview", required=True, help="a file, or - for stdin")
    seed.add_argument("--writer", help=f"one of: {', '.join(writers_domain.CAST)}")
    seed.add_argument("--book")
    seed.add_argument("--branch")
    seed.set_defaults(func=cmd_architect)

    grow = architect_sub.add_parser(
        "grow", help="after a chapter: keep the world coherent and spend what it declared"
    )
    grow.add_argument("--scene", help="a scene logical id; the latest drafted one by default")
    grow.add_argument("--writer", help=f"one of: {', '.join(writers_domain.CAST)}")
    grow.add_argument("--book")
    grow.add_argument("--branch")
    grow.set_defaults(func=cmd_architect)

    read = sub.add_parser(
        "readers", help="put the simulated readership on a drafted scene"
    )
    read.add_argument("--scene", help="a scene logical id; the latest drafted one by default")
    read.add_argument("--book")
    read.add_argument("--branch")
    read.set_defaults(func=cmd_readers)

    library_cmd = sub.add_parser(
        "library",
        help="republish the reading copies and pastable chapters (not a publication; §62)",
    )
    library_cmd.add_argument(
        "--force",
        action="store_true",
        help="rebuild every shelf even when its book has not moved. The way to adopt a "
        "changed rendering: the files are derived, so the fix is to derive them again",
    )
    library_cmd.set_defaults(func=cmd_library)

    propagate = sub.add_parser(
        "propagate", help="what a change reaches beyond what it edits, from a ChangeSet"
    )
    propagate.add_argument("path", type=Path, help="a ChangeSet JSON file")
    propagate.add_argument(
        "--enqueue",
        action="store_true",
        help="queue an evaluation for each reached scene; without it this only reports",
    )
    propagate.add_argument("--book")
    propagate.add_argument("--branch")
    propagate.set_defaults(func=cmd_propagate)

    plans = sub.add_parser(
        "plans", help="the plan's lineage, newest first, and what produced each revision"
    )
    plans.add_argument("--book")
    plans.add_argument("--branch")
    plans.add_argument("--json", action="store_true", help="machine-readable output")
    plans.set_defaults(func=cmd_plans)

    revert_plan = sub.add_parser(
        "revert-plan", help="restore an earlier plan revision as the new plan head"
    )
    revert_plan.add_argument(
        "plan_revision", help="plan revision id to restore; `litharness plans` lists them"
    )
    revert_plan.add_argument("--book")
    revert_plan.add_argument("--branch")
    revert_plan.set_defaults(func=cmd_revert_plan)

    replan = sub.add_parser(
        "replan", help="reissue still-draftable beats under a fresh plan epoch"
    )
    replan.add_argument("--book")
    replan.add_argument("--branch")
    replan.add_argument("--reason", help="recorded on the PlanChanged event")
    replan.set_defaults(func=cmd_replan)

    backup = sub.add_parser("backup", help="online backup (safe while ticking)")
    backup.add_argument("destination", type=Path)
    backup.set_defaults(func=cmd_backup)

    export = sub.add_parser(
        "export", help="a reading copy of the book as it stands, gaps and all"
    )
    export.add_argument(
        "destination",
        type=Path,
        nargs="?",
        help="file to write; stdout if omitted. The suffix picks the format",
    )
    export.add_argument(
        "--format",
        choices=["markdown", "html"],
        help="overrides the suffix; markdown by default. HTML carries print CSS, so a "
        "browser's Save as PDF produces a readable book",
    )
    export.add_argument("--book", help="required only when the store holds more than one")
    export.add_argument("--branch")
    export.add_argument(
        "--revision",
        help="an older revision instead of the head — how two exports get compared",
    )
    export.set_defaults(func=cmd_export)

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
    except (OSError, FileExistsError, ValueError, sqlite3.Error) as error:
        # Operational faults — a locked or missing database, a backup destination that
        # already exists, a bad argument. Distinguished from EXIT_ATTENTION because a
        # driver should retry these next iteration rather than surface them as the
        # system reporting on its work.
        #
        # **`sqlite3.Error` is not an `OSError`**, which made the one fault this contract
        # names first — a locked database — the one it did not handle: it escaped as an
        # unhandled traceback and exit 1, the code reserved for "a unit needs a human".
        # A driver built on the documented contract escalated the fault it was told to
        # absorb. An operator command contends with the ticking session on
        # `BEGIN IMMEDIATE` by design, so this is the *expected* fault, not an exotic one.
        print(f"litharness: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FAULT


if __name__ == "__main__":  # pragma: no cover - exercised via __main__.py
    raise SystemExit(main())
