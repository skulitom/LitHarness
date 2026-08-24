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
from litharness.application import architect, comprehension, constraint_locks
from litharness.application import export as export_module
from litharness.application import library as library_module
from litharness.application import status as status_module
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.directive_planner import DIRECTIVE_PLAN, make_directive_plan_handler
from litharness.application.director import DIRECT, make_director_handler
from litharness.application.evaluation import (
    CompositeEvaluator,
    ContinuityEvaluator,
    Evaluator,
    InProcessEvaluator,
)
from litharness.application.feedback_loop import live_directions, readings, resolve
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.judge_panel import machine_judge_id, run_batch
from litharness.application.narrative_planner import (
    NARRATIVE_PLAN,
    make_narrative_plan_handler,
)
from litharness.application.outline import BOOK_OUTLINE, make_outline_handler
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.plan_search import (
    PLAN_SEARCH,
    SPAN_SELECT,
    TOURNAMENT_SOURCE,
    make_plan_search_handler,
    make_span_select_handler,
)
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
from litharness.application.variation import (
    VARIATION_STEP,
    make_variation_repair_handler,
    make_variation_step_handler,
)
from litharness.domain import (
    audit,
    calibration,
    extraction,
    impact,
    preference,
    propagation,
)
from litharness.domain import axes as axes_domain

# Aliased: `build_parser` binds a local `craft` for the subparser, and a module named the
# same thing would work only by scope luck.
from litharness.domain import craft as craft_domain
from litharness.domain import directions as directions_domain
from litharness.domain import directors as directors_domain
from litharness.domain import feedback as feedback_domain
from litharness.domain import pools as pools_domain
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_domain
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
            plan_search=args.plan_search,
            director_id=_director_id(store, args),
            # The same shape the library publishes at, so a book is grouped for a reader and
            # drafted against that grouping instead of against two that can disagree. At the
            # default of one it asserts nothing and the prompt is unchanged.
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
            # **Two handlers, one job kind, and the operator picks which serves it.** The
            # evaluation handler's licence predicate is untouched either way — a repair is
            # minted for a located, span-carrying, blocking-or-calibrated finding and for
            # nothing else — so the two paths are comparable on identical work, which is what
            # the comparison in `plan/variation-session.md` needs and what a separate job kind
            # would have quietly destroyed.
            REPAIR_FINDING: (
                make_variation_repair_handler(
                    registry, store, args.project, budget=_budget(args)
                )
                if args.variation_repair
                else make_repair_handler(
                    registry, store, args.project, budget=_budget(args)
                )
            ),
            # Registered unconditionally, like every kind here: a session opened under
            # `--variation-repair` and still running when the flag is dropped must still be
            # able to close, and an unhandled kind fails three times and poisons in silence.
            VARIATION_STEP: make_variation_step_handler(registry, store, args.project),
            # §61 Add 3: the tournament and its selection. Registered unconditionally —
            # like every handler here, a kind with no queued work costs nothing — while
            # the *minting* of tournaments sits behind `--plan-search` above, which is
            # what keeps the search arm operator-selectable.
            PLAN_SEARCH: make_plan_search_handler(
                registry,
                store,
                args.project,
                draft_policy=_draft_policy(args),
                budget=_budget(args),
            ),
            SPAN_SELECT: make_span_select_handler(
                registry,
                store,
                args.project,
                draft_policy=_draft_policy(args),
                budget=_budget(args),
                schedule_evaluation=True,
                schedule_summary=True,
                actor=args.holder,
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
        print(
            "  A brief says what the book is about. What good prose is comes from readers "
            "through the axis admission path, never from direction."
        )
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


def cmd_audit(args: argparse.Namespace) -> int:
    """The scenes §10.5 drew for human reading, and the prose to read.

    Prints the text, not a reference to it. The scarce input in this whole programme is a
    human's attention — measured at roughly 57 seconds per judgment in RevisionJudge, which
    has collected two — and making a reader go and find the scene spends that attention on
    navigation. `--next` prints one and stops, which is the shape of the thing someone
    actually does between other tasks.
    """
    store = _store(args)
    try:
        pending = store.audit_samples(pending_only=not args.all)
        texts: dict[str, str | None] = {}
        for sample in pending[: 1 if args.next else len(pending)]:
            revision = store.load_revision(sample.revision_id)
            with suppress(KeyError):
                texts[sample.sample_id] = revision.node(sample.logical_id).content
    finally:
        store.close()

    shown = pending[: 1 if args.next else len(pending)]
    for sample in shown:
        state = sample.verdict.value if sample.verdict else "PENDING"
        print(f"{sample.sample_id}  {state:<13} {sample.logical_id}  ({sample.sampled_at})")
        if args.quiet:
            continue
        # Deliberately no provenance: §10.3 wants blinded judgments, and telling the reader
        # which provider wrote it, or that a gate passed it, is exactly the contamination
        # RevisionBench measured as a 43-65% positional artifact in model judges.
        print()
        print(texts.get(sample.sample_id) or "  (no prose at that node)")
        print()
        print(f"  litharness read {sample.sample_id} --keep-reading|--would-stop|--not-sure")
        print()
    counts = {"pending": sum(1 for item in pending if item.pending)}
    print(f"({len(pending)} sample(s), {counts['pending']} awaiting a reader)")
    return EXIT_OK


def cmd_read(args: argparse.Namespace) -> int:
    """Record one human READER verdict. The only input to this system nothing else can supply.

    §1a.5's bar is "a majority of sampled chapters earn *I would keep reading* from readers
    who were not told what produced them", so that is the question asked rather than a rubric.
    `--not-sure` is a real answer: §10.4 asks for abstention to be measured, and a scale with
    no way to decline pushes a reader into a verdict they do not hold.

    **This verb was called `judge` and the name was backwards.** Under the Reader/Judge split
    a READER owns valence — would I keep reading — and a JUDGE owns location and axis and
    never valence. What this records is a reader's verdict, so `read` is what it is called.
    `judge` still works and warns; the cost of the rename is small now and grows with every
    row (`plan/reader-judge-loop.md` §8).
    """
    if getattr(args, "deprecated_verb", False):
        print(
            "litharness: `judge` is the old name for `read` and still records the same row. "
            "Under the Reader/Judge split a reader owns valence and a judge owns location, "
            "so this verb is `read`",
            file=sys.stderr,
        )
    verdict = (
        audit.Verdict.KEEP_READING if args.keep_reading
        else audit.Verdict.WOULD_STOP if args.would_stop
        else audit.Verdict.NOT_SURE
    )
    stamp = _stamp(_now())
    store = _store(args)
    try:
        recorded = store.record_verdict(
            args.sample_id,
            verdict,
            at=stamp,
            by=args.by or args.holder,
            note=args.note,
            events=[
                Event(
                    event_type=EventType.EVALUATION_COMPLETED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.by or args.holder,
                    payload={
                        "sample_id": args.sample_id,
                        "verdict": verdict.value,
                        "audit": True,
                    },
                )
            ],
        )
    finally:
        store.close()
    if not recorded:
        print(
            f"litharness: no unanswered sample {args.sample_id}. A verdict is never "
            "overwritten — the first reading is the blind one",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    print(f"{args.sample_id} -> {verdict.value}")
    return EXIT_OK


#: What the human write paths say to a reader id wearing the machine prefix.
#:
#: **The prefix was opt-in at one write site and unowned everywhere else, and separating the
#: Reader and Judge roles makes that worse rather than better** — the whole point of the split
#: is to run judges at volume, and volume is what turns an open path into a laundered pool.
#: `analysable_judgments` cuts `judge:` rows from the PREFERENCE denominator (§86.6), so a
#: *human* row wearing the prefix would vanish from the count silently, and nothing owned the
#: namespace in the other direction either. Refusing here makes the prefix mean exactly one
#: thing: written by the in-process judge path.
_RESERVED_READER_COMPLAINT = (
    "litharness: reader id {reader} starts with the reserved machine prefix "
    f"'{preference.MACHINE_READER_PREFIX}'. That prefix marks rows a machine wrote, which "
    "`analysable_judgments` excludes from every PREFERENCE holdout — a human judgment "
    "wearing it would be silently uncounted. Use a name that is not reserved"
)


def _sample_pool(
    store: SqliteStore,
    sample: preference.PairSample,
    registration: pools_domain.PoolRegistration,
) -> pools_domain.Pool | None:
    """Which side of the firewall this pair sits on, or None when it cannot be decided.

    Two shapes, because a pair has two shapes. A **mixed** pair — ours against the matched
    published corpus, which is §61's own comparison — takes its pool from the revision node it
    contains. A **sibling** pair is two candidate texts, and its pool is the pool of the *span*
    those candidates were drafted for, so all K siblings share one side and a span can never be
    half-steering.

    None rather than a guess when neither resolves: routing a verdict under an undecidable pool
    is exactly the silent contamination the firewall exists to prevent, and the caller refuses.
    """
    for address in (sample.left_addr, sample.right_addr):
        member = preference.Member.parse(address)
        if member.kind is preference.MemberKind.REVISION_NODE:
            assert member.revision_id is not None and member.logical_id is not None
            return pools_domain.passage_pool(
                member.revision_id, member.logical_id, registration
            )
    spans = {
        candidate.address: (candidate.base_revision_id, candidate.logical_id)
        for book_id, branch_id, _ in store.branches()
        for candidate in store.span_candidates(book_id, branch_id)
    }
    for address in (sample.left_addr, sample.right_addr):
        found = spans.get(address)
        if found is not None:
            return pools_domain.passage_pool(found[0], found[1], registration)
    return None


def _routing_complaint(
    store: SqliteStore, sample: preference.PairSample, reader: str
) -> str | None:
    """The reason this reader may not answer this sample, or None when they may.

    Enforced at the write site rather than checked in analysis, because §61's claim dies on
    *contamination*, not on a mis-labelled row: once a steering-pool reader has answered a
    measurement pair, no later filter can un-shape the prose that reader's verdicts went on to
    influence. `plan/reader-judge-loop.md` §1.4 lists this as one of four mechanical locks and
    lists the one residual it cannot close.
    """
    registration = store.pool_registration()
    if registration is None:
        return (
            "no pool registration. The measurement firewall is declared once, before the "
            "first verdict is routed — `litharness pools register` "
            "(plan/reader-judge-loop.md §1)"
        )
    pool = _sample_pool(store, sample, registration)
    if pool is None:
        return (
            f"sample {sample.sample_id} resolves to no span, so which side of the firewall "
            "it sits on cannot be decided. A verdict routed under an undecidable pool is the "
            "contamination the split exists to prevent"
        )
    reader_side = pools_domain.reader_pool(reader, registration)
    if reader_side is not pool:
        return (
            f"reader {reader} is in the {reader_side.value} pool and this pair is "
            f"{pool.value}. §61's claim dies if the prose was shaped by the readers who "
            "later judge it, so the two pools are answered by disjoint sets of people"
        )
    return None


def _registration_or_complaint(store: SqliteStore) -> pools_domain.PoolRegistration | None:
    registration = store.pool_registration()
    if registration is None:
        print(
            "litharness: no pool registration. The measurement firewall is declared once, "
            "before the first verdict is routed — `litharness pools register` "
            "(plan/reader-judge-loop.md §1)",
            file=sys.stderr,
        )
    return registration


def cmd_pools(args: argparse.Namespace) -> int:
    """Show the measurement firewall, or declare it.

    §61's claim — a clustered lower bound on win rate against matched published prose —
    **dies if the prose was shaped by the readers who later judge it**, and once reader
    verdicts reach a draft prompt that stops being hypothetical. So readers and comparison
    passages are split before the first verdict is routed, and the split is declared here
    rather than defaulted: a firewall nobody declared is §61 pre-registration (4)'s own
    failure — the frame *is* the claim, and a frame chosen by a constant in a source file was
    not declared by anyone.
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        if args.register:
            registration = pools_domain.PoolRegistration(
                registration_id=pools_domain.registration_id_for(
                    reader_salt=args.reader_salt,
                    reader_steering_share=args.reader_share,
                    passage_salt=args.passage_salt,
                    passage_steering_share=args.passage_share,
                ),
                registered_at=stamp,
                reader_salt=args.reader_salt,
                reader_steering_share=args.reader_share,
                passage_salt=args.passage_salt,
                passage_steering_share=args.passage_share,
                note=args.note or "",
            )
            existing = store.pool_registration()
            if (
                existing is not None
                and existing.registration_id != registration.registration_id
            ):
                print(
                    f"litharness: {existing.registration_id} is already the active split, "
                    f"declared {existing.registered_at}. A firewall that could be moved "
                    "after the verdicts arrived would not be one",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            fresh = store.record_pool_registration(registration)
            print(
                f"{registration.registration_id} "
                f"{'declared' if fresh else 'already declared'}"
            )
        active = store.pool_registration()
        if active is None:
            print("(no split declared; nothing may be routed)")
            return EXIT_ATTENTION
        print(f"{active.registration_id}  declared {active.registered_at}")
        print(
            f"  readers  steering share {active.reader_steering_share:.3f}  "
            f"salt {active.reader_salt}"
        )
        print(
            f"  passages steering share {active.passage_steering_share:.3f}  "
            f"salt {active.passage_salt}"
        )
        if active.note:
            print(f"  note: {active.note}")
        for reader in args.who or ():
            print(f"  {reader} -> {pools_domain.reader_pool(reader, active).value}")
        print(f"  {pools_domain.RESIDUAL}")
    finally:
        store.close()
    return EXIT_OK


def cmd_axes(args: argparse.Namespace) -> int:
    """The registered axes, their counters, the hypothesis each tests, and how each got in.

    The hypotheses are printed and are **not** what steers anything: they are the §74 human
    read's three named defects written down before readers answer, so the answer can be
    reported as confirming or refuting something rather than as a discovery. §78.3's em-dash
    arm is VOID with its estimate leaning toward the mark, so at least one may well be wrong.
    """
    for axis in axes_domain.AXES.values():
        print(f"{axis.axis_id:<14} counter {axis.counter_id}")
        print(f"  hypothesis: readers prefer {axis.hypothesis.value}")
        print(f"    high: {axis.high_phrase}")
        print(f"    low:  {axis.low_phrase}")
        print(f"  admitted via: {axis.admitted_via}")
        print(f"  {axis.provenance}")
    if args.text:
        text = args.text.read_text(encoding="utf-8")
        print(f"\ncounters over {args.text}:")
        for axis_id, value in axes_domain.counts(text).items():
            print(f"  {axis_id:<14} {value:.4f}")
    return EXIT_OK


def cmd_directions(args: argparse.Namespace) -> int:
    """What steering readers say about each axis, and what it would take to say anything.

    Every registered axis prints a row, including the silent ones. §89's rulebook is the
    reason: five of seven declared quantities that could not do their job were caught by a
    dry run printing *which* precondition was unmet, and a listing that omitted the axes with
    no evidence would have hidden every one of them.
    """
    stamp = _stamp(_now())
    if args.attainability:
        report = directions_domain.attainability()
        print(
            f"bar: clustered lower bound > {directions_domain.DIRECTION_BAR} at alpha "
            f"{directions_domain.DIRECTION_ALPHA}"
        )
        print(
            f"floors: {directions_domain.MIN_CELLS} decided cells, "
            f"{directions_domain.MIN_READER_CLUSTERS} readers, "
            f"{directions_domain.MIN_PAIR_CLUSTERS} pairs"
        )
        if not report.attainable:
            print(
                "UNATTAINABLE: no win count at the declared shape clears the bar. The bar "
                "cannot do what it says and must be changed before anything is spent"
            )
            return EXIT_ATTENTION
        clearing = report.smallest_clearing_k or 0
        print(
            f"smallest clearing k: {clearing} of {report.cells} cells "
            f"({clearing / report.cells:.3f})"
        )
        print(
            f"true rate   power at {report.cells} cells   cells for "
            f"{directions_domain.TARGET_POWER:.0%} power"
        )
        for rate, power in sorted(report.power.items()):
            needed = report.cells_for_power.get(rate)
            shown = str(needed) if needed is not None else f">{400}"
            print(f"  {rate:.2f}            {power:.3f}                {shown}")
        print(
            "  A bar that rejects a true 0.65 most of the time is wrong in the direction of "
            "false failure; T0's own bar disqualified a good judge 82-100% of the time until "
            "this was measured."
        )
        print(
            "  The floor is a COHERENCE floor, not a sample size. Read the last column "
            "before buying a batch: at a true 0.60 the floor fires under a tenth of the time, "
            "and a null from thirty judgments would say nothing about the axis."
        )
        return EXIT_OK

    store = _store(args)
    try:
        if store.pool_registration() is None and _registration_or_complaint(store) is None:
            return EXIT_FAULT
        rows = readings(store, at=stamp)
        live, stale = live_directions(store)
        established = {direction.axis_id for direction in live}
        stale_axes = {direction.axis_id for direction in stale}
        for reading in rows:
            state = (
                "ESTABLISHED"
                if reading.axis_id in established
                else "STALE"
                if reading.axis_id in stale_axes
                else "-"
            )
            if reading.direction is not None:
                detail = (
                    f"prefers {reading.direction.preferred.value} "
                    f"(bound {reading.direction.lower_bound:.4f}, "
                    f"hypothesis {reading.hypothesis_status})"
                )
            else:
                detail = f"no direction: {reading.why_not.value if reading.why_not else '-'}"
            print(
                f"{reading.axis_id:<14} {state:<12} cells {reading.cells:<4} "
                f"readers {reading.readers:<3} pairs {reading.pairs:<3} {detail}"
            )
            if reading.multi_axis_pairs:
                print(
                    f"  {reading.multi_axis_pairs} pair(s) moved this axis and another at "
                    "once, so they carry no single-axis evidence"
                )
        if args.establish:
            written = 0
            for reading in rows:
                if reading.direction is None:
                    continue
                if store.record_axis_direction(
                    reading.direction,
                    events=[
                        Event(
                            event_type=EventType.EVALUATION_COMPLETED,
                            project_id=args.project,
                            created_at=stamp,
                            actor=args.holder,
                            payload={
                                "axis_id": reading.axis_id,
                                "preferred_pole": reading.direction.preferred.value,
                                "lower_bound": reading.direction.lower_bound,
                                "direction": True,
                            },
                        )
                    ],
                ):
                    written += 1
            print(f"{written} direction(s) established")
    finally:
        store.close()
    return EXIT_OK


def cmd_feedback(args: argparse.Namespace) -> int:
    """What would reach the next draft prompt for this book, and why it is usually nothing.

    Read-only: it resolves without spending anything, so an operator can see the loop's state
    without moving it. `resolve` marks nothing spent — only the planner does, and only after
    the job carrying the item exists.
    """
    store = _store(args)
    try:
        head = store.head(args.book, args.branch)
        materialised = resolve(
            store, book_id=args.book, branch_id=args.branch, head=head
        )
        if materialised.feedback.empty:
            registration = store.pool_registration()
            live, stale = live_directions(store) if registration else ((), ())
            reason = (
                "no pool registration"
                if registration is None
                else "no live direction"
                if not live
                else "no minted located difference on a directed axis"
            )
            if args.json:
                # **`empty` is a fact with a reason, not a null.** An agent that read an
                # absent key here would have to guess between "the loop is off" and "the
                # loop is on and had nothing to say", which are opposite diagnoses.
                print(
                    json.dumps(
                        {
                            "book_id": args.book,
                            "branch_id": args.branch,
                            "empty": True,
                            "reason": reason,
                            "digest": materialised.feedback.digest,
                            "dropped": materialised.feedback.dropped,
                            "items": [],
                            "spend": [],
                            "stale_directions": len(stale),
                        },
                        indent=2,
                    )
                )
                return EXIT_OK
            print(f"(nothing would reach the prompt: {reason})")
            if stale:
                print(
                    f"  {len(stale)} direction(s) stale: the verdicts moved under them "
                    "(`litharness directions --establish` re-measures)"
                )
            return EXIT_OK
        if args.json:
            # Measured on both branches rather than assumed zero on this one. A set can be
            # non-empty *and* have directions gone stale under it, and a key that reported 0
            # because nothing had looked would be the report inventing a fact.
            stale_here = (
                live_directions(store)[1] if store.pool_registration() else ()
            )
            print(
                json.dumps(
                    {
                        "book_id": args.book,
                        "branch_id": args.branch,
                        "empty": False,
                        "reason": None,
                        "digest": materialised.feedback.digest,
                        "dropped": materialised.feedback.dropped,
                        "items": list(materialised.feedback.to_payload()),
                        "spend": list(materialised.spend),
                        "stale_directions": len(stale_here),
                    },
                    indent=2,
                )
            )
            return EXIT_OK
        print(materialised.feedback.render())
        print()
        print(
            f"digest {materialised.feedback.digest}  "
            f"dropped {materialised.feedback.dropped}"
        )
        if materialised.spend:
            print(
                f"  {len(materialised.spend)} located item(s) would be spent by the next "
                "enqueue; a located item is one-shot"
            )
    finally:
        store.close()
    return EXIT_OK


def cmd_contrast(args: argparse.Namespace) -> int:
    """Run one judge batch over a span's sibling candidates: what differs, and where.

    The judge is asked E6's question verbatim and never which passage is better. It refuses
    before spending when no reader has given any axis a direction, because discrimination
    without direction cannot say which way to move and half a signal is not worth buying.
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        candidates = store.span_candidates(
            args.book, args.branch, logical_id=args.logical_id
        )
        if not candidates:
            print(f"litharness: no candidates for {args.logical_id}", file=sys.stderr)
            return EXIT_ATTENTION
        registry = build_default_registry()
        result = run_batch(
            registry,
            store,
            candidates,
            judge_id=machine_judge_id(args.judge),
            created_at=stamp,
        )
        print(f"{result.batch_id or '(no batch)'}  {result.verdict.value}  {result.calls} call(s)")
        for name, reading in sorted(result.controls.items()):
            print(f"  control {name}: {reading}")
        if result.orientation is not None:
            print(
                f"  orientation {result.orientation.reading.value} over "
                f"{result.orientation.responses} response(s)"
            )
        print(
            f"  discarded: {result.unnamed} unnamed, {result.ambiguous} ambiguous, "
            f"{result.undirected} on an undirected axis, {result.unseparated} unseparated"
        )
        # **Written for every batch, void ones included, and before the usability check.**
        # An unmatched sentence is a field report about a salient difference the axis registry
        # cannot yet name — the same object §74's human read produced, from a channel that runs
        # at volume — and a corpus not persisted from the first batch is gone.
        kept = store.record_judge_discards(result.discards)
        if kept:
            print(f"  {kept} judge sentence(s) retained in the discard corpus")
        if not result.usable:
            return EXIT_ATTENTION
        written = store.record_located_differences(result.differences)
        print(f"{written} located difference(s) recorded")
        for difference in result.differences:
            print(f"  {difference.axis_id:<14} {difference.span[:80]}")
    finally:
        store.close()
    return EXIT_OK


def cmd_discards(args: argparse.Namespace) -> int:
    """Judge sentences that located nothing, verbatim — the corpus for axes we cannot yet name.

    **Read-only, and the rail matters more than the report.** These sentences may *nominate* a
    candidate axis; they may never *validate* one. A matcher drafted from them and then scored
    against them is a rubric fitted to its own answers, which is the failure the frozen
    `AXIS_MATCHERS` exists to prevent. A nominated axis takes the full admission path: a
    deterministic counter, an E6-family validation on fresh pairs this corpus never touched,
    and a reader-established direction, before it emits anything.
    """
    store = _store(args)
    try:
        reason = (
            feedback_domain.DiscardReason(args.reason) if args.reason else None
        )
        rows = store.judge_discards(
            book_id=args.book, reason=reason, limit=args.limit
        )
        counts: dict[str, int] = {}
        for row in store.judge_discards(book_id=args.book):
            counts[row.reason.value] = counts.get(row.reason.value, 0) + 1
        if not counts:
            print("(no judge sentences recorded; the discrimination channel has not run)")
            return EXIT_OK
        print("  ".join(f"{name} {count}" for name, count in sorted(counts.items())))
        print()
        for row in rows:
            flag = "" if row.batch_ok else "  [batch VOID: evidence about the judge]"
            print(f"{row.reason.value:<12} {row.logical_id:<12} slot {row.orientation}{flag}")
            print(f"  {row.sentence}")
            if row.separating:
                print(f"  counters separating this pair: {row.separating}")
        print()
        print(
            "  These may nominate a candidate axis and may never validate one: a matcher "
            "drafted from these sentences and scored against them is a rubric fitted to its "
            "own answers (plan/reader-judge-loop.md §2)."
        )
    finally:
        store.close()
    return EXIT_OK


def cmd_blame(args: argparse.Namespace) -> int:
    """Per accepted scene, in order: one axis's counter beside the feedback live when it drafted.

    **The read side of invariant I4.** When a counter trend turns, this answers "which standing
    direction or located item was in the prompt when it turned" the way a bisect answers which
    commit — from rows that already exist, with no new writes and no thresholds.

    It renders values and provenance and never a score: per I2 there is no aggregate here to
    read as a quality number, and per I3 nothing it prints can refuse anything.
    """
    store = _store(args)
    try:
        head = store.head(args.book, args.branch)
        if head is None:
            print(f"litharness: no head for {args.book}/{args.branch}", file=sys.stderr)
            return EXIT_ATTENTION
        # Latest row per node, by the order the store returns (recorded_at ascending).
        by_node: dict[str, feedback_domain.SceneFeedback] = {
            record.logical_id: record for record in store.scene_feedback()
        }
        rows: list[dict[str, Any]] = []
        for node in head.in_reading_order():
            if node.kind is not NodeKind.SCENE or not node.content or node.tombstoned:
                continue
            found = by_node.get(node.logical_id)
            rows.append(
                {
                    "logical_id": node.logical_id,
                    "value": axes_domain.count(args.axis, node.content),
                    # **null is "nobody recorded" and [] is "recorded, and empty".** I4's
                    # negative case survives the trip through JSON only while those two keep
                    # different values here, and an agent reading a missing key would collapse
                    # them into one wrong answer.
                    "items": None if found is None else [dict(item) for item in found.items],
                    "digest": None if found is None else found.digest,
                    "dropped": None if found is None else found.dropped,
                    "revision_id": None if found is None else found.revision_id,
                }
            )
        if args.json:
            print(
                json.dumps(
                    {
                        "book_id": args.book,
                        "branch_id": args.branch,
                        "axis": args.axis,
                        "counter_id": axes_domain.AXES[args.axis].counter_id,
                        "scenes": rows,
                    },
                    indent=2,
                )
            )
            return EXIT_OK
        print(f"axis {args.axis} ({axes_domain.AXES[args.axis].counter_id})")
        for row in rows:
            items = row["items"]
            if items is None:
                shaped = "(no provenance row: drafted before the loop existed)"
            elif not items:
                shaped = "(empty feedback set)"
            else:
                shaped = "; ".join(
                    f"{item.get('role')}:{item.get('axis_id')}"
                    f"->{item.get('preferred_pole')}"
                    for item in items
                )
            print(f"  {row['logical_id']:<14} {row['value']:>9.4f}  {shaped}")
            if row["dropped"]:
                print(f"                             {row['dropped']} item(s) dropped by the cap")
        if not rows:
            print("  (no accepted scene carries prose yet)")
    finally:
        store.close()
    return EXIT_OK


#: Absences that mean the dossier could not answer the question it was asked, so `why`
#: exits non-zero on them.
#:
#: **The `verify` idiom, per scene.** `unattributed_revisions` exists because §19's integrity
#: clause was asserted rather than checked, and a forensic read needs the same discipline: a
#: dossier printing nothing where a decision belongs reads exactly like a scene that had no
#: decision to print. Every gap is named in the `absent` list; only these three mean the
#: question went unanswered. A book drafted with `--no-outline` has no plan statement and a
#: scene older than the reader loop has no provenance row, and neither is a fault — they are
#: facts about that book, printed and exit 0.
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

    A payload with no prompt is not always a defect — the tournament handler appends one
    alternative per candidate to a shared prompt, and an evaluation unit has none at all —
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
    ran, and the feedback set is the one the payload carried. A dossier that re-rendered the
    prompt from live tables would be answering a question about today.
    """
    logical_id = node.logical_id
    absent: list[str] = []
    introduced, depth = _introduced_in(store, head, logical_id)
    if introduced is None:
        absent.append("prose")

    decision = None if introduced is None else store.decision_for_revision(introduced)
    if introduced is not None and decision is None:
        absent.append("decision")

    recorded = None
    if introduced is not None:
        for record in store.scene_feedback(revision_id=introduced):
            if record.logical_id == logical_id:
                recorded = record
                break
        if recorded is None:
            absent.append("scene_feedback")

    # The job id off the decision when there is one and off the provenance row when there is
    # not. Two independent columns naming the same unit is what lets an unattributed scene
    # still show the prompt it was drafted from.
    job_id = (decision.job_id if decision else None) or (
        recorded.job_id if recorded else None
    )
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

    metrics: list[dict[str, Any]] = []
    if introduced is not None:
        metrics = [
            {"metric_id": metric_id, "value": value}
            for _, measured_node, metric_id, value in store.craft_metrics(
                revision_id=introduced
            )
            if measured_node == logical_id
        ]

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
        # **The payload's set and the revision's row are two different facts.** One is what
        # was materialised at enqueue, the other what the acceptance projected onto the prose
        # that came back. They agree in the normal case, and carrying both is what would make
        # a disagreement visible at all.
        "payload_feedback": None
        if job is None
        else {
            "items": payload.get("feedback"),
            "digest": payload.get("feedback_digest"),
            "dropped": payload.get("feedback_dropped"),
        },
        "scene_feedback": None
        if recorded is None
        else {
            "digest": recorded.digest,
            "items": [dict(item) for item in recorded.items],
            "dropped": recorded.dropped,
            "job_id": recorded.job_id,
            "recorded_at": recorded.recorded_at,
        },
        "plan_item": None
        if plan_item is None
        else {
            "plan_item_id": plan_item.logical_id,
            "text": plan_item.text,
            "locked": plan_item.locked,
            "authority": plan_item.authority.value,
        },
        "craft_metrics": metrics,
        "findings": [
            _finding_row(item)
            for item in store.findings(
                book_id, branch_id, logical_id=logical_id, open_only=False
            )
        ],
        "span_candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "alternative_index": candidate.alternative_index,
                "status": candidate.status.value,
                "statement": candidate.statement,
                "chars": len(candidate.text),
                "job_id": candidate.job_id,
                "plan_epoch": candidate.plan_epoch,
            }
            for candidate in store.span_candidates(
                book_id, branch_id, logical_id=logical_id
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

    payload_feedback = dossier["payload_feedback"]
    if isinstance(payload_feedback, dict):
        items = payload_feedback["items"]
        count = "no key" if not isinstance(items, list) else f"{len(items)}"
        field(
            "feedback",
            f"frozen on the payload: {count} item(s), dropped {payload_feedback['dropped']}",
        )
        field("", f"digest {payload_feedback['digest']}")
        if isinstance(items, list):
            for item in items:
                field("", f"  {item}")
            if not items:
                # `[]` and "nobody recorded" are different facts, and this is where they part.
                field("", "  (an explicit empty set: drafted with no feedback)")

    recorded = dossier["scene_feedback"]
    if recorded is None and not undrafted:
        field("provenance", "ABSENT - no scene feedback row (drafted before the loop existed)")
    elif recorded is not None:
        field(
            "provenance",
            f"recorded on the revision: {len(recorded['items'])} item(s), "
            f"dropped {recorded['dropped']}, at {recorded['recorded_at']}",
        )
        field("", f"digest {recorded['digest']}")

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

    metrics: list[dict[str, Any]] = dossier["craft_metrics"]
    field(
        "craft",
        "  ".join(f"{item['metric_id']} {item['value']:.4f}" for item in metrics)
        if metrics
        else "no advisory measurement recorded for this scene",
    )

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

    candidates: list[dict[str, Any]] = dossier["span_candidates"]
    if candidates:
        lost = sum(1 for item in candidates if item["status"] != "selected")
        field("candidates", f"{len(candidates)} recorded, {lost} that did not win")
        for item in candidates:
            field(
                "",
                f"  #{item['alternative_index']}  {item['status']:<10}{item['chars']} char(s)",
            )
            field("", f"    {item['statement']}")

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
    frozen on the job payload at enqueue, every attempt has a policy decision, losing
    tournament drafts stay in the candidate table — and none of it was printed by any
    command, so the only way to look at any of it was to open the SQLite file. That is the
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


def cmd_calibrations(args: argparse.Namespace) -> int:
    """What evidence exists that any craft metric predicts human judgment.

    Expected to print nothing for a long time, and that is the honest state: §10.6's reference
    corpus is human authoring work and §19.1 records the Quality clause as not started. An
    empty list here is the measure of the gap, in the same way the unread directive count
    measures direction the planner cannot read.
    """
    store = _store(args)
    try:
        items = store.calibrations(metric_id=args.metric)
        verdicts = [
            (sample.sample_id, sample.verdict.value)
            for sample in store.audit_samples()
            if sample.verdict is not None
        ]
        pair_samples = store.pair_samples()
    finally:
        store.close()

    # Per-class, the same dispatch the craft ladder runs at every draft: a class checked
    # against another class's digest is either falsely stale forever or never stale at all,
    # and both misreadings have already happened once each in this file's history. The
    # answered counts ride along for the same reason — a listing that skipped the
    # holdout-vs-store comparison would print BLOCKING-ELIGIBLE for a row the ladder
    # refuses, and the operator reads the listing.
    digests: dict[calibration.EvidenceClass, str | None] = {
        calibration.EvidenceClass.JUDGMENT: calibration.verdicts_digest_for(verdicts),
        calibration.EvidenceClass.POPULATION: craft_domain.profile_digest(),
        calibration.EvidenceClass.PREFERENCE: preference.pair_verdicts_digest_for(
            pair_samples
        ),
    }
    answered_counts = {
        calibration.EvidenceClass.JUDGMENT: len(verdicts),
        calibration.EvidenceClass.PREFERENCE: len(
            preference.analysable_judgments(pair_samples)
        ),
    }
    today = _stamp(_now())[:10]
    for item in items:
        why = item.why_not_promotable(
            today,
            digests.get(item.evidence_class),
            answered=answered_counts.get(item.evidence_class),
        )
        if why is None and item.evidence_class is calibration.EvidenceClass.PREFERENCE:
            # Sound and current, and still may not block: preference evidence licenses
            # selection between candidates (§61 Add 3), and `veto_for` refuses it a veto.
            state = "selection-only"
        else:
            state = "BLOCKING-ELIGIBLE" if why is None else "advisory"
        print(f"{item.calibration_id}  {state:<18} {item.metric_id}")
        print(f"    {_evidence_line(item)}; fails {item.direction.value} {item.threshold}")
        if why is not None:
            print(f"    not promotable: {why}")
    print(f"({len(items)} calibration(s); {len(verdicts)} verdict(s) on record)")
    if not items:
        print(
            "  no craft metric may block. §10.4 promotes a critic only on measured held-out "
            f"precision whose lower confidence bound clears {calibration.MIN_PRECISION:.2f} "
            f"on {calibration.MIN_HOLDOUT} judgments; §10.6's reference corpus is the gate."
        )
    return EXIT_OK


def _evidence_line(record: calibration.Calibration) -> str:
    """What a judgment row's numbers say, led by the bound rather than by the estimate.

    The estimate is printed second and in parentheses because it is the number that reads as
    the result and is not the one promotion turns on — 14 of 17 flags is a confident-looking
    0.82 and a bound of 0.566.
    """
    bound = record.precision_lower_bound
    if bound is None:
        return (
            f"counts not recorded ({record.correct}/{record.flagged} flags, family "
            f"{record.selection_family_size}) on {record.holdout_size} held-out"
        )
    return (
        f"precision at least {bound:.3f} (point {record.precision:.2f}, "
        f"{record.correct}/{record.flagged} flags across {record.clusters} cluster(s), "
        f"{record.selection_family_size} candidate(s)) on {record.holdout_size} held-out"
    )


def _population_from_profile(
    args: argparse.Namespace,
) -> tuple[calibration.Population, str, float] | int:
    """Derive a population calibration's threshold and control from the built profile.

    Returns `(population, profile_digest, threshold)`, or an exit code on refusal.

    **The threshold is read, never typed**, and `--threshold` is ignored for this class. A
    corpus-derived line is a *stop in a distribution*; letting a human supply the number
    would let them park it wherever nothing crosses it, which is the inert gate the domain
    then refuses on `reference_exceedance == 0`. Reading it means the only choices left are
    which cohort, which band and which stop — each of them nameable, and each recorded.

    **The control is computed here rather than accepted from the caller**, for the reason
    `research/quality-measurement/BRIEF.md` §2 spends a table on: the control has to be
    measured in the same pass as the headline or the headline means nothing. Passing it as a
    flag would make "forgot to measure the control" and "measured it and it was fine"
    indistinguishable on the command line.
    """
    missing = [
        name
        for name, value in (
            ("--cohort", args.cohort),
            ("--control-cohort", args.control_cohort),
            ("--band", args.band),
            ("--quantile", args.quantile),
        )
        if not value
    ]
    if missing:
        print(
            f"litharness: a population calibration needs {', '.join(missing)}; a threshold "
            "with no named cohort, band, stop and control is a number with no referent",
            file=sys.stderr,
        )
        return EXIT_FAULT
    if args.cohort == args.control_cohort:
        print(
            "litharness: the control cohort must differ from the reference cohort; a cohort "
            "compared against itself is a control that cannot fail",
            file=sys.stderr,
        )
        return EXIT_FAULT

    profile = craft_domain.load_profile()
    digest = craft_domain.profile_digest(profile)
    if digest is None:
        print(
            "litharness: no craft profile is built, so there is no distribution to read a "
            "threshold out of; run research/quality-measurement/build_craft_profile.py",
            file=sys.stderr,
        )
        return EXIT_FAULT
    threshold = craft_domain.quantile_stop(
        args.metric,
        cohort=args.cohort,
        band=args.band,
        quantile=args.quantile,
        profile=profile,
    )
    if threshold is None:
        print(
            f"litharness: {args.metric} has no {args.quantile} stop for {args.cohort} at "
            f"{args.band}; the band may be unbuilt or below the "
            f"{craft_domain.MIN_BAND_CHAPTERS}-chapter floor",
            file=sys.stderr,
        )
        return EXIT_FAULT

    reference_n = craft_domain.band_chapters(cohort=args.cohort, band=args.band, profile=profile)
    control_n = craft_domain.band_chapters(
        cohort=args.control_cohort, band=args.band, profile=profile
    )
    direction = calibration.Direction(args.direction)
    reference_exceedance = _exceedance(
        args.metric, args.cohort, args.band, threshold, direction, profile
    )
    control_exceedance = _exceedance(
        args.metric, args.control_cohort, args.band, threshold, direction, profile
    )
    tail = round(float(args.quantile[1:]) / 100.0, 4)
    # The index `build_craft_profile` reads the stop from, so the counts below are the number
    # of observations the estimate actually rests on rather than a share of the band.
    stop_index = round(tail * (reference_n - 1))
    population = calibration.Population(
        metric_id=args.metric,
        cohort=args.cohort,
        band=args.band,
        quantile=args.quantile,
        reference_n=reference_n,
        # **How many chapters sit on the *failing* side of the stop, which depends on the
        # direction.** This was `reference_n - stop_index` unconditionally, which is the
        # upper tail — right for ABOVE and inverted for BELOW. A p01/BELOW gate reported
        # ≈0.99n where its failing tail holds ≈0.01n, so `MIN_TAIL_SUPPORT` — the guard
        # against a tail estimated from noise — was cleared by roughly two orders of
        # magnitude by the arithmetic rather than by the evidence. Measured on the committed
        # profile's `human_pre_llm` 700-1100 band (n=419): 415 reported against 5 actual.
        tail_support=(
            reference_n - stop_index
            if direction is calibration.Direction.ABOVE
            else stop_index + 1
        ),
        control_cohort=args.control_cohort,
        control_n=control_n,
        reference_exceedance=reference_exceedance,
        control_exceedance=control_exceedance,
        profile_digest=digest,
    )
    return population, digest, threshold


def _exceedance(
    metric_id: str,
    cohort: str,
    band: str,
    threshold: float,
    direction: calibration.Direction,
    profile: dict[str, Any],
) -> float:
    """Share of a cohort's band on the failing side of `threshold`, from the stored ladder.

    Interpolated off the same seven stops `percentile_of` uses, because the profile stores no
    prose. Approximate, and the right precision for the question: the control clause asks
    whether one cohort crosses a line several times as often as another, not whether it does
    so at the fourth decimal.
    """
    stops = (
        profile.get("cohorts", {})
        .get(cohort, {})
        .get("bands", {})
        .get(band, {})
        .get("metrics", {})
        .get(metric_id, {})
    )
    if not stops:
        return 0.0
    ladder = [
        (0.01, stops["p01"]), (0.05, stops["p05"]), (0.25, stops["p25"]),
        (0.50, stops["p50"]), (0.75, stops["p75"]), (0.95, stops["p95"]),
        (0.99, stops["p99"]),
    ]
    if direction is calibration.Direction.ABOVE:
        below = next((p for p, value in ladder if value >= threshold), 0.99)
        return round(max(0.0, 1.0 - below), 6)
    below = next((p for p, value in reversed(ladder) if value <= threshold), 0.01)
    return round(max(0.0, below), 6)


def cmd_calibrate(args: argparse.Namespace) -> int:
    """Record measured evidence that one metric predicts human judgment at one threshold.

    The write verb `calibrations` had no counterpart. `SqliteStore.record_calibration` has
    existed since migration 014 with no caller outside the tests, which meant the only route
    to a blocking craft gate ran through writing Python against the store — so the promotion
    path was unreachable by the operator who is supposed to authorise it.

    **This command records; it does not promote.** The numbers are the measurer's, and the
    only thing checked at write time is that they are internally coherent. Whether the
    calibration may block is `why_not_promotable`'s answer, recomputed at every draft against
    the verdict set as it stands then — so it is printed here as information rather than
    enforced here as a precondition. Recording a calibration that cannot yet promote is a
    legitimate and expected act: it is how evidence accumulates toward one that can.

    `--verdicts-digest` defaults to the digest of the store's current answered verdicts,
    which is right when the measurement was made against this store and wrong if it was made
    elsewhere. Passing it explicitly is how a measurement computed off-line says so.
    """
    if args.recall is not None and not 0.0 <= args.recall <= 1.0:
        print(f"litharness: recall {args.recall} is not a proportion", file=sys.stderr)
        return EXIT_FAULT
    if args.flagged > args.holdout:
        print(
            f"litharness: the metric cannot have fired on {args.flagged} of {args.holdout} "
            "held-out judgments; more flags than judgments means the two numbers describe "
            "different sets",
            file=sys.stderr,
        )
        return EXIT_FAULT
    if not 0 <= args.correct <= args.flagged:
        print(
            f"litharness: {args.correct} correct of {args.flagged} flag(s) is not a count "
            "pair; the human cannot have agreed with more flags than the metric raised",
            file=sys.stderr,
        )
        return EXIT_FAULT

    evidence_class = calibration.EvidenceClass(args.evidence_class)
    grain = calibration.Grain(args.grain)

    store = _store(args)
    try:
        # **The digest a row is checked against is derived from its class, never typed.**
        # `--verdicts-digest` is gone; see the flag's own deletion note in `build_parser`.
        # A judgment row is addressed by the answered verdicts this store holds; a population
        # row by the profile build its threshold was read out of. The two can never collide,
        # so a corpus measurement can no longer inherit the audit digest and promote by
        # omission.
        answered = [
            sample for sample in store.audit_samples() if sample.verdict is not None
        ]
        current = calibration.verdicts_digest_for(
            (sample.sample_id, sample.verdict.value)
            for sample in answered
            if sample.verdict is not None
        )
        # The preference class's evidence lives in the pair table, so both its digest and
        # its answered count come from there. Counting the audit queue instead would let a
        # claimed pair holdout clear the answered-count check on the strength of the wrong
        # population — `answered` is just an int to the domain, so this caller is the check.
        pair_answered = [
            sample for sample in store.pair_samples() if sample.verdict is not None
        ]
        pair_digest = preference.pair_verdicts_digest_for(pair_answered)
        population: calibration.Population | None = None
        if evidence_class is calibration.EvidenceClass.POPULATION:
            built = _population_from_profile(args)
            if isinstance(built, int):
                return built
            population, digest, threshold = built
        elif evidence_class is calibration.EvidenceClass.PREFERENCE:
            digest, threshold = pair_digest, args.threshold
        else:
            digest, threshold = current, args.threshold
        record = calibration.Calibration(
            calibration_id=calibration.calibration_id_for(
                args.metric,
                threshold,
                digest,
                direction=calibration.Direction(args.direction),
                correct=args.correct,
                holdout_size=args.holdout,
                flagged=args.flagged,
                selection_family_size=args.selection_family,
                clusters=args.clusters,
                evidence_class=evidence_class,
                grain=grain,
            ),
            metric_id=args.metric,
            holdout_size=args.holdout,
            threshold=threshold,
            direction=calibration.Direction(args.direction),
            verdicts_digest=digest,
            measured_at=_stamp(_now()),
            expires_at=args.expires,
            flagged=args.flagged,
            correct=args.correct,
            selection_family_size=args.selection_family,
            clusters=args.clusters,
            recall=args.recall,
            note=args.note,
            evidence_class=evidence_class,
            grain=grain,
            population=population,
        )
        inserted = store.record_calibration(record)
        # Report the row that is *on record*, never the one just built. They differ whenever
        # the insert was ignored, and the difference is the whole point: a caller told
        # "BLOCKING-ELIGIBLE" about numbers the store rejected would act on a gate that does
        # not exist. Re-read rather than assume, because the assumption is what broke.
        stored = [
            item for item in store.calibrations(metric_id=args.metric)
            if item.calibration_id == record.calibration_id
        ]
    finally:
        store.close()


    record = stored[0] if stored else record
    today = _stamp(_now())[:10]
    # Checked against the digest for its own class, and against the answered count of its
    # own holdout population — the comparison nothing anywhere was making, which is why a
    # row claiming fifty held-out judgments promoted against a store holding two. For a
    # preference row both come from the pair table: fifty answered audit scenes say nothing
    # about how many pair judgments exist.
    if record.evidence_class is calibration.EvidenceClass.POPULATION:
        against = craft_domain.profile_digest()
    elif record.evidence_class is calibration.EvidenceClass.PREFERENCE:
        against = pair_digest
    else:
        against = current
    # Analysable rows only: recognised judgments and abstentions are excluded from
    # analysis, so they must not license a holdout claim. Protocols pool, as the digest
    # pools — over-invalidation is the safe direction.
    answered_count = (
        len(preference.analysable_judgments(pair_answered))
        if record.evidence_class is calibration.EvidenceClass.PREFERENCE
        else len(answered)
    )
    why = record.why_not_promotable(today, against, answered=answered_count)
    verb = "recorded" if inserted else "already on record"
    print(f"{record.calibration_id}  {verb}  {record.metric_id}")
    print(f"    evidence: {record.evidence_class.value} at {record.grain.value} grain")
    if record.population is not None:
        print(
            f"    {record.population.quantile} of {record.population.cohort} at "
            f"{record.population.band} words (n={record.population.reference_n}, "
            f"{record.population.tail_support} at the tail); control "
            f"{record.population.control_cohort} exceeds "
            f"{record.population.control_exceedance:.4f} against "
            f"{record.population.reference_exceedance:.4f}"
        )
    else:
        print(f"    {_evidence_line(record)}")
    print(f"    fails {record.direction.value} {record.threshold}")
    if why is None and record.evidence_class is calibration.EvidenceClass.PREFERENCE:
        # Sound, current, and still not a gate: preference evidence licenses selection
        # between candidates (§61 Add 3), never absolute refusal of one text, and
        # `veto_for` refuses it a veto with zero code. Printing BLOCKING-ELIGIBLE here
        # would announce a gate that can never be built.
        print("    selection-only: sound evidence, and preference may never block")
    elif why is None:
        print("    BLOCKING-ELIGIBLE: this metric may now park a scene it refuses")
    else:
        print(f"    advisory — not promotable: {why}")
    return EXIT_OK


# -- the pairwise preference engine (§61 Add 1) --------------------------------------------


def cmd_corpus_add(args: argparse.Namespace) -> int:
    """Add one matched published-human excerpt: the other side of the external comparison.

    Source, genre and era are required because they are the matching covariates — §56.3
    measured revealed labels selecting story size and era rather than prose, so an excerpt
    that cannot say what it was matched on is a comparison against a confound waiting to be
    reported as a result.
    """
    text = args.path.read_text(encoding="utf-8") if args.path else sys.stdin.read()
    if not text.strip():
        print("litharness: an empty excerpt is not prose anyone can prefer", file=sys.stderr)
        return EXIT_FAULT
    excerpt = preference.ComparisonExcerpt.from_text(
        text, source=args.source, genre=args.genre, era=args.era, added_at=_stamp(_now())
    )
    store = _store(args)
    try:
        inserted = store.record_excerpt(excerpt)
    finally:
        store.close()
    verb = "recorded" if inserted else "already on record"
    print(f"{excerpt.excerpt_id}  {verb}  ({excerpt.words} words, {excerpt.source}, "
          f"{excerpt.genre}, {excerpt.era})")
    return EXIT_OK


def cmd_protocol(args: argparse.Namespace) -> int:
    """Pre-register one comparison frame. §61 pre-registration (4): the frame *is* the claim.

    Declared once: the protocol id derives from the frame, the tie policy and the grain,
    with the declaration date outside the hash — so re-declaring the same frame collides
    with the original and is refused by name rather than re-stamped with a newer date, which
    would be exactly the quiet re-registration a pre-registration exists to prevent.
    """
    tie_policy = preference.TiePolicy(args.tie_policy)
    grain = preference.PairGrain(args.grain)
    protocol = preference.PreferenceProtocol(
        protocol_id=preference.protocol_id_for(args.frame, tie_policy=tie_policy, grain=grain),
        comparator_frame=args.frame,
        tie_policy=tie_policy,
        grain=grain,
        declared_at=_stamp(_now()),
    )
    store = _store(args)
    try:
        inserted = store.record_protocol(protocol)
        stored = next(
            item for item in store.protocols() if item.protocol_id == protocol.protocol_id
        )
    finally:
        store.close()
    if not inserted:
        print(
            f"litharness: protocol {protocol.protocol_id} was already declared at "
            f"{stored.declared_at}. A pre-registration is declared once; the original "
            "declaration stands",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    print(f"{protocol.protocol_id}  declared  ({tie_policy.value} ties, {grain.value} grain)")
    print(f"    frame: {protocol.comparator_frame}")
    return EXIT_OK


def _scene_candidates(
    store: SqliteStore,
    *,
    pool: pools_domain.Pool | None = None,
    registration: pools_domain.PoolRegistration | None = None,
) -> tuple[list[tuple[str, str | None]], int]:
    """Accepted scenes with prose, addressed at the branch head, and how many were held back.

    Revision-addressed on purpose: revision ids are content-addressed, so a drawn pair pins
    exactly the text a reader judged even after the book moves on.

    **`pool` is the passage half of the measurement firewall, applied at the draw.** A pair
    nobody in the matching reader pool may answer is a queue that cannot drain, so the filter
    belongs here rather than at the verdict. The count of what it held back is returned rather
    than swallowed: a bound coverage that says nothing reads as "covered everything" when it
    did not.
    """
    candidates: list[tuple[str, str | None]] = []
    held = 0
    for book_id, _branch_id, head in store.branches():
        revision = store.load_revision(head)
        for node in revision.nodes:
            if node.kind is not NodeKind.SCENE or node.tombstoned or not node.content:
                continue
            if pool is not None and (
                pools_domain.passage_pool(head, node.logical_id, registration) is not pool
            ):
                held += 1
                continue
            candidates.append((preference.revision_address(head, node.logical_id), book_id))
    return candidates, held


def cmd_pair_draw(args: argparse.Namespace) -> int:
    """Draw blinded pairs for a protocol — content-derived, replay-convergent, no RNG.

    The draw refuses to run without a stored protocol (§59's discipline: required, no
    default), because a judgment collected under no declared frame is a number whose claim
    gets chosen after the fact. `--siblings` draws system-vs-system pairs under the
    built-in internal-v0 frame, recording it first; the external-comparison frame must be
    declared by the operator before the first reader is paid (§61 pre-registration 4).
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        if args.siblings and not args.protocol:
            protocol = preference.INTERNAL_PROTOCOL
            store.record_protocol(protocol)
        else:
            if not args.protocol:
                print(
                    "litharness: a draw needs --protocol; declare the comparison frame "
                    "first (`litharness protocol`) — the frame is the claim (§61)",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            found = [
                item for item in store.protocols() if item.protocol_id == args.protocol
            ]
            if not found:
                print(
                    f"litharness: no protocol {args.protocol} on record; a pair drawn "
                    "under no stored protocol is refused. Declare it with "
                    "`litharness protocol`",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            [protocol] = found
        if protocol.grain is preference.PairGrain.CHAPTER:
            print(
                "litharness: chapter-grain drawing is not built — production books hold "
                "no chapter nodes and no assembly scheme is decided, so scene grain ships "
                "first rather than improvising one",
                file=sys.stderr,
            )
            return EXIT_FAULT
        # **The passage half of the measurement firewall, applied at the draw.** A sibling
        # pair is steering evidence and an external pair is §61's own comparison, so a span
        # answers one question or the other and never both — that is what keeps a passage's
        # own reader verdicts out of the prose that passage is later compared as. The split
        # must exist first: a pair drawn before the firewall was declared could not have been
        # routed by it, which is what "before the first verdict is routed" means.
        registration = _registration_or_complaint(store)
        if registration is None:
            return EXIT_FAULT
        wanted = (
            pools_domain.Pool.STEERING if args.siblings else pools_domain.Pool.MEASUREMENT
        )
        candidates, held = _scene_candidates(
            store, pool=wanted, registration=registration
        )
        if held:
            print(
                f"({held} scene(s) held back by the measurement firewall: they are on the "
                f"other side of the split from {wanted.value})"
            )
        if not candidates:
            print(
                "0 pair(s) drawn: no accepted scene on the "
                f"{wanted.value} side holds prose yet"
            )
            return EXIT_OK
        if args.siblings:
            corpus = [address for address, _ in candidates]
        else:
            # Tournament candidates (§61 Add 3) live in the corpus table so the pair
            # queue can render them, and they are OUR prose — drawn into the external
            # frame they would sit on the comparator side of the superiority claim,
            # which is a comparison against ourselves wearing the human corpus's label.
            corpus = [
                preference.excerpt_address(excerpt.excerpt_id)
                for excerpt in store.excerpts()
                if not excerpt.source.startswith(TOURNAMENT_SOURCE)
            ]
            if not corpus:
                print(
                    "0 pair(s) drawn: the comparison corpus is empty. Add matched "
                    "published-human excerpts with `litharness corpus-add`"
                )
                return EXIT_OK
        samples = preference.draw_pairs(
            candidates, corpus, protocol, args.rate, sampled_at=stamp
        )
        inserted = sum(1 for sample in samples if store.record_pair_sample(sample))
    finally:
        store.close()
    pair_count = len({sample.pair_id for sample in samples})
    print(
        f"{pair_count} pair(s) drawn at rate {args.rate} -> {len(samples)} presented "
        f"sample(s) ({inserted} new) under {protocol.protocol_id}"
    )
    return EXIT_OK


def _member_text(store: SqliteStore, excerpts: dict[str, str], address: str) -> str | None:
    member = preference.Member.parse(address)
    if member.kind is preference.MemberKind.CORPUS_EXCERPT:
        assert member.excerpt_id is not None  # Member.__post_init__ enforced it
        return excerpts.get(member.excerpt_id)
    assert member.revision_id is not None and member.logical_id is not None
    try:
        return store.load_revision(member.revision_id).node(member.logical_id).content
    except KeyError:
        return None


def cmd_pairs(args: argparse.Namespace) -> int:
    """The blinded pair queue: both texts, no provenance, presented order per the row.

    Deliberately nothing that says which side is which — not the addresses, not the
    protocol internals, not which member is ours. cmd_audit's blinding discipline, doubled:
    RevisionBench measured 43-65% positional artifacts in judges told nothing at all, and a
    reader told which side is the system is not blind in any sense worth recording.
    """
    store = _store(args)
    try:
        samples = store.pair_samples(pending_only=args.pending)
        if args.reader:
            # **The queue one reader may actually answer.** Without this the operator hands
            # a reader a list and half of it is refused at the verdict, which teaches the
            # reader that the tool is broken rather than that the firewall is working.
            samples = [
                sample
                for sample in samples
                if _routing_complaint(store, sample, args.reader) is None
            ]
        excerpts = {excerpt.excerpt_id: excerpt.text for excerpt in store.excerpts()}
        texts: dict[str, tuple[str | None, str | None]] = {
            sample.sample_id: (
                _member_text(store, excerpts, sample.left_addr),
                _member_text(store, excerpts, sample.right_addr),
            )
            for sample in samples
        }
    finally:
        store.close()

    for sample in samples:
        state = sample.verdict.value if sample.verdict else "PENDING"
        print(f"{sample.sample_id}  {state:<13} {sample.grain.value}  ({sample.sampled_at})")
        if args.quiet:
            continue
        first, second = texts.get(sample.sample_id, (None, None))
        print()
        print("  FIRST:")
        print(first or "  (no prose at that address)")
        print()
        print("  SECOND:")
        print(second or "  (no prose at that address)")
        print()
        print(
            f"  litharness pair-judge {sample.sample_id} "
            "prefer_first|prefer_second|tie|not_sure --reader <id> --recognized yes|no"
        )
        print()
    pending = sum(1 for sample in samples if sample.pending)
    print(f"({len(samples)} sample(s), {pending} awaiting a reader)")
    return EXIT_OK


def cmd_pair_judge(args: argparse.Namespace) -> int:
    """Record one pairwise preference verdict, relative to presented position.

    `--recognized` is §61 pre-registration (3) and is a required yes/no, not an optional
    flag: §58 measured a scorer's familiarity with published text swinging a score several
    times harder than real damage, the matched corpus includes some of the genre's
    most-read serials, and a judgment that never answered the question cannot be excluded
    — an absent answer is not "no", it is a judgment this engine may not analyse. The
    answer is stored and a recognised row is excluded from analysis, never dropped,
    because the exclusion count is itself a finding.
    """
    verdict = preference.PairVerdict(args.verdict)
    recognized = args.recognized == "yes"
    if not args.reader.strip():
        print(
            "litharness: --reader must name who judged; the reader is a cluster "
            "dimension of the bound, and an anonymous judgment cannot cluster",
            file=sys.stderr,
        )
        return EXIT_FAULT
    if preference.is_machine_reader(args.reader):
        print(_RESERVED_READER_COMPLAINT.format(reader=args.reader), file=sys.stderr)
        return EXIT_FAULT
    stamp = _stamp(_now())
    store = _store(args)
    try:
        sample = next(
            (item for item in store.pair_samples() if item.sample_id == args.sample_id),
            None,
        )
        if sample is not None and all(
            item.protocol_id != sample.protocol_id for item in store.protocols()
        ):
            # Unreachable through this CLI's own draw, which refuses protocol-less pairs;
            # belt and braces against rows arriving by any other road.
            print(
                f"litharness: sample {args.sample_id} references no stored protocol; "
                "judging under an undeclared frame is refused (§61: the frame is the claim)",
                file=sys.stderr,
            )
            return EXIT_FAULT
        if sample is not None:
            complaint = _routing_complaint(store, sample, args.reader)
            if complaint is not None:
                print(f"litharness: {complaint}", file=sys.stderr)
                return EXIT_FAULT
        recorded = store.record_pair_verdict(
            args.sample_id,
            verdict,
            at=stamp,
            by=args.reader,
            recognized=recognized,
            note=args.note,
            events=[
                Event(
                    event_type=EventType.EVALUATION_COMPLETED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.reader,
                    payload={
                        "sample_id": args.sample_id,
                        "verdict": verdict.value,
                        "recognized": recognized,
                        "pair": True,
                    },
                )
            ],
        )
    finally:
        store.close()
    if not recorded:
        print(
            f"litharness: no unanswered pair sample {args.sample_id}. A verdict is never "
            "overwritten — the first reading is the blind one",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    suffix = "  (recognised — stored, excluded from analysis)" if recognized else ""
    print(f"{args.sample_id} -> {verdict.value}{suffix}")
    return EXIT_OK


def cmd_win_rate(args: argparse.Namespace) -> int:
    """The system's win rate under one protocol, led by the clustered lower bound.

    The bound, not the estimate, is what any claim turns on (§59: 14 of 17 reads as a
    confident 0.82 and bounds at 0.566). `--alpha` is the two-sided level for *this*
    protocol's evidence alone; the headline claim additionally divides it by the
    candidate-book count when more than one book could have been reported — §61
    pre-registration (5), §6.4's selection family applied to the claim itself.
    """
    store = _store(args)
    try:
        protocols = [
            item for item in store.protocols() if item.protocol_id == args.protocol
        ]
        if not protocols:
            print(
                f"litharness: no protocol {args.protocol} on record",
                file=sys.stderr,
            )
            return EXIT_FAULT
        [protocol] = protocols
        answered = [
            sample
            for sample in store.pair_samples()
            if sample.protocol_id == args.protocol and sample.verdict is not None
        ]
    finally:
        store.close()

    # One judgment per (pair, orientation, protocol, reader), earliest first. Today the
    # only producer mints one queue row per (pair, orientation, protocol), so duplicates
    # cannot exist — but the sample identity supports pre-assigned per-reader rows, and
    # the day one coexists with an unassigned row answered by the same reader, counting
    # both would double one reader's one opinion. The earliest judged row is the blind
    # first reading, which is the one this engine trusts everywhere else.
    earliest: dict[tuple[str, int, str, str], preference.PairSample] = {}
    for sample in sorted(answered, key=lambda item: (item.judged_at or "", item.sample_id)):
        key = (sample.pair_id, sample.orientation, sample.protocol_id, sample.reader_id or "")
        earliest.setdefault(key, sample)
    answered = list(earliest.values())

    recognized = abstained = internal = ties = decisive = 0
    orientation_decisive = {0: 0, 1: 0}
    orientation_wins = {0: 0, 1: 0}
    observations: list[preference.WinObservation] = []
    for sample in answered:
        if sample.recognized:
            recognized += 1
            continue
        if preference.system_side(sample.left_addr, sample.right_addr) is None:
            internal += 1
            continue
        if sample.verdict is preference.PairVerdict.NOT_SURE:
            abstained += 1
            continue
        outcome = preference.system_outcome(sample)
        assert outcome is not None  # every exclusion was counted above
        if outcome is preference.PairOutcome.TIE:
            ties += 1
        else:
            decisive += 1
            orientation_decisive[sample.orientation] += 1
            if outcome is preference.PairOutcome.WIN:
                orientation_wins[sample.orientation] += 1
        observations.append(
            preference.WinObservation(
                pair_id=sample.pair_id,
                reader_id=sample.reader_id or "",
                outcome=outcome,
            )
        )

    print(f"protocol {protocol.protocol_id} ({protocol.tie_policy.value} ties)")
    print(
        f"    {decisive} decisive, {ties} tie(s), {recognized} excluded by recognition, "
        f"{abstained} abstention(s), {internal} system-vs-system (no human side)"
    )
    if decisive:
        # Position is a recorded fact, so the split is reportable — and must be: for
        # mixed pairs orientation 0 is always human-first (the addresses sort that way),
        # so a pooled rate over an unbalanced queue quietly weights one presentation.
        parts: list[str] = []
        for orientation in (0, 1):
            count = orientation_decisive[orientation]
            if count:
                rate = orientation_wins[orientation] / count
                parts.append(f"orientation {orientation}: {count} decisive, observed {rate:.3f}")
            else:
                parts.append(f"orientation {orientation}: 0 decisive")
        print("    " + "; ".join(parts))
    if not observations:
        print(
            "    no analysable judgment yet; the counts above are the honest measure of "
            "the gap"
        )
        return EXIT_OK
    if decisive and (orientation_decisive[0] == 0 or orientation_decisive[1] == 0):
        print(
            "    no bound: every decisive judgment was collected at one presented order. "
            "A rate over a single orientation cannot separate preference from the 43-65% "
            "positional artifact RevisionBench measured; judge the position-swapped "
            "complements first",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    low_side, high_side = sorted((orientation_decisive[0], orientation_decisive[1]))
    if decisive and low_side * 2 < high_side:
        print(
            f"    positional imbalance: {orientation_decisive[0]} vs "
            f"{orientation_decisive[1]} decisive judgments by orientation is worse than "
            "2:1; the position-swapped complements are sitting unanswered"
        )
    try:
        observed = preference.observed_win_rate(
            observations, tie_policy=protocol.tie_policy
        )
        bound = preference.win_rate_lower_bound(
            observations, alpha=args.alpha, tie_policy=protocol.tie_policy
        )
    except ValueError as error:
        print(f"    no bound: {error}", file=sys.stderr)
        return EXIT_ATTENTION
    print(
        f"    win rate at least {bound:.3f} (observed {observed:.3f}) at two-sided "
        f"alpha {args.alpha}"
    )
    # The clusters the bound actually rested on: ties leave the analysis set under a
    # drop policy, mirroring what the bound itself did.
    analysis = [
        observation
        for observation in observations
        if protocol.tie_policy is preference.TiePolicy.HALF_WIN
        or observation.outcome is not preference.PairOutcome.TIE
    ]
    reader_clusters = len({observation.reader_id for observation in analysis})
    pair_clusters = len({observation.pair_id for observation in analysis})
    floor = preference.DESCRIPTIVE_CLUSTER_FLOOR
    if reader_clusters < floor or pair_clusters < floor:
        print(
            f"    caveat: {reader_clusters} reader and {pair_clusters} pair cluster(s) — "
            "the bootstrap under-covers at this size, so the bound is descriptive; the "
            "promotion floors are the real gate"
        )
    print(
        "    the headline claim divides alpha by the candidate-book count "
        "(§61 pre-registration 5)"
    )
    return EXIT_OK


def cmd_craft(args: argparse.Namespace) -> int:
    """The advisory numbers, and what they are not.

    §1a.1: "beware the metric that is easy *because* it is shallow". These measure §1a.3 items
    5 and 6 — line-level craft and AI tells — and touch none of items 1 to 4, which are the
    ones that move a reader. Printed with that on the page rather than in a doc nobody opens.
    """
    store = _store(args)
    try:
        rows = store.craft_metrics(metric_id=args.metric)
    finally:
        store.close()

    by_metric: dict[str, list[float]] = {}
    for _, _, metric_id, value in rows:
        by_metric.setdefault(metric_id, []).append(value)
    for metric_id, values in sorted(by_metric.items()):
        low, high = min(values), max(values)
        mean = sum(values) / len(values)
        print(f"{metric_id:<40} n={len(values):<5} mean={mean:.4f}  [{low:.4f}, {high:.4f}]")
    print(f"({len(rows)} measurement(s) over {len(by_metric)} metric(s))")
    print(
        "  advisory only — §1a.3 items 5 and 6, and nothing about dramatic function, "
        "progression, escalation or voice. `calibrations` shows what may block."
    )
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
        # information for the person choosing, not a refusal of the forge. `plan_search`'s
        # `_refusal_gate` is the same shape for the same reason — a loser's defect made
        # standing would park work that has nothing to do with it.
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

    **The engine existed as a scorer with nothing to score.** `domain/impact.py` grades a
    blast-radius prediction against the gold suites and ships three baselines for it to beat;
    no code produced a prediction. `domain/propagation.py` is the prediction, and this is the
    surface an operator reaches it through.

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
    # Node granularity, in-sample, four cases — said at the surface rather than in a doc,
    # because a prediction that travels without its caveat becomes a claim nobody checked.
    print(f"  {impact.CAVEAT}")
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


def cmd_lock_constraints(args: argparse.Namespace) -> int:
    """Lock the plan constraints a person's directive produced, which reach no packet unlocked.

    **The defect is one boolean and its blast radius is the whole book.**
    `plans.constraints_of` selects on `locked`, so an unlocked constraint sits in the plan, is
    counted by `litharness plans`, and is shown to no writer ever. Serial Pilot 1's tone note
    became five such constraints — close third person, dry and exact, concrete specifics,
    dramatize rather than summarize, and *scenes end on movement or cost* — and all eight
    scenes of that book were drafted without one word of them.

    `acf0e05` fixed the minting rule, and a minting rule cannot reach a plan already minted,
    which is what this is for. It changes `locked` and never a word of text, it refuses any
    constraint it cannot trace back to a directive a *person* wrote, and it proposes nothing on
    a second run — so it is safe to leave in an operator's hands, which is where it stays
    rather than running on every tick.

    Like every accepted plan proposal this advances the plan epoch and cancels queued scene
    jobs, so the next tick replans the still-draftable beats against the locked plan. Scenes
    already accepted are untouched: revisions are immutable, and re-drafting one is `revise`.
    """
    stamp = _stamp(_now())
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.plan_revision(book_id, branch_id)
        if head is None:
            print("litharness: this branch has no plan", file=sys.stderr)
            return EXIT_FAULT
        if args.dry_run:
            # The same two functions the live path runs, with the write left out, so what is
            # reported is what would happen rather than a second implementation of it.
            outcome = constraint_locks.LockOutcome(
                constraint_locks.lock_candidates(
                    head,
                    produced=constraint_locks.produced_by(
                        store.plan_proposals(book_id, branch_id)
                    ),
                    directives=_cited_directives(store, book_id, branch_id),
                ),
                None,
            )
        else:
            outcome = constraint_locks.lock_directed_constraints(
                store,
                book_id=book_id,
                branch_id=branch_id,
                project_id=args.project,
                created_at=stamp,
                actor=args.holder,
            )
    finally:
        store.close()

    if not outcome.candidates:
        print("every constraint in this plan is already locked; nothing to do")
        return EXIT_OK
    for logical_id in outcome.locked:
        print(f"{'would lock' if args.dry_run else 'locked'} {logical_id}")
    if outcome.application is not None:
        print(
            f"  new plan revision {outcome.application.after.plan_revision_id[:12]}; "
            "the plan epoch advanced and the next tick replans still-draftable beats"
        )
        print("  scenes already accepted keep the prompts they were drafted from")
    elif outcome.locked:
        print("  --dry-run: nothing was written")
    else:
        print("no unlocked constraint here carries a person's authority; nothing to lock")
    for candidate in outcome.refused:
        print(f"  refused {candidate.logical_id}: {candidate.refused}")
    if outcome.refused:
        print(
            "    a lock is a person's authority, so an item this cannot attribute to a "
            "person keeps the standing it already has"
        )
        return EXIT_ATTENTION
    return EXIT_OK


def _cited_directives(
    store: SqliteStore, book_id: str, branch_id: str
) -> dict[str, Directive]:
    """The directives this branch's applied proposals cite, for the read-only preview."""
    produced = constraint_locks.produced_by(store.plan_proposals(book_id, branch_id))
    found: dict[str, Directive] = {}
    for directive_id in set(produced.values()):
        try:
            found[directive_id] = store.load_directive(directive_id)
        except KeyError:
            continue
    return found


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


def cmd_export(args: argparse.Namespace) -> int:
    """A reading copy of the book as it stands. See `application/export.py`.

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
        default=Path(DEFAULT_DB),
        help=f"SQLite database path (default: {DEFAULT_DB})",
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
        "--context-budget",
        type=int,
        default=None,
        help="tokens of context a scene is drafted against. Raise it with --target-words: "
        "measured, a 900-word scene binds the default 6000 at scene 5 and leaves the packet "
        "holding three prior scenes",
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
        "--plan-search",
        action="store_true",
        default=_env_flag("LITHARNESS_PLAN_SEARCH"),
        help="draft each span by tournament (§61 Add 3): K alternative beat-plans, K "
        "candidate drafts, pairwise selection, one committed winner; also read from "
        "LITHARNESS_PLAN_SEARCH. Off by default — this is the search arm of the K=3 "
        "acceptance experiment (research/plan-search/RUNBOOK.md), and the default is "
        "its control",
    )
    parser.add_argument(
        "--variation-repair",
        action="store_true",
        default=_env_flag("LITHARNESS_VARIATION_REPAIR"),
        help="repair a located finding with a bounded variation session instead of one "
        "fixed attempt: the model proposes an edit, the deterministic gates judge it, the "
        "exact refusal comes back, and it proposes again within the session's own ceilings; "
        "also read from LITHARNESS_VARIATION_REPAIR. Off by default — the fixed path is the "
        "control arm of the comparison in plan/variation-session.md. It orders nothing and "
        "commits the first mechanically valid candidate",
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
        "--chapter-scenes",
        type=int,
        default=library_module.DEFAULT_SCENES_PER_CHAPTER,
        help="how many scenes make one pastable chapter, and the position each scene is told "
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

    audit_cmd = sub.add_parser(
        "audit", help="scenes drawn for human reading (§10.5), with the prose to read"
    )
    audit_cmd.add_argument(
        "--next", action="store_true", help="print one pending sample and stop"
    )
    audit_cmd.add_argument(
        "--all", action="store_true", help="include samples already judged"
    )
    audit_cmd.add_argument(
        "--quiet", action="store_true", help="list the samples without printing prose"
    )
    audit_cmd.set_defaults(func=cmd_audit)

    # `read` and its deprecated alias `judge`. Same arguments, same rows, one warning — under
    # the Reader/Judge split a READER owns valence and a JUDGE owns location, and this verb
    # records a reader's verdict. See `cmd_read`.
    for verb in ("read", "judge"):
        reader_verb = sub.add_parser(
            verb,
            help=(
                "record one human reader verdict on a sampled scene"
                if verb == "read"
                else "deprecated alias for `read`"
            ),
        )
        reader_verb.add_argument("sample_id")
        answer = reader_verb.add_mutually_exclusive_group(required=True)
        answer.add_argument("--keep-reading", action="store_true")
        answer.add_argument("--would-stop", action="store_true")
        answer.add_argument(
            "--not-sure",
            action="store_true",
            help="abstention is a real answer and is measured",
        )
        reader_verb.add_argument(
            "--note", help="what you noticed; the most useful field here"
        )
        reader_verb.add_argument("--by", help="who read it (defaults to --holder)")
        reader_verb.set_defaults(func=cmd_read, deprecated_verb=verb == "judge")

    pools = sub.add_parser(
        "pools", help="the measurement firewall: who steers and who measures (§61)"
    )
    pools.add_argument(
        "--register", action="store_true", help="declare the split; refused once one exists"
    )
    pools.add_argument("--reader-salt", default="reader-pool-v1")
    pools.add_argument("--reader-share", type=float, default=0.5)
    pools.add_argument("--passage-salt", default="passage-pool-v1")
    pools.add_argument("--passage-share", type=float, default=0.5)
    pools.add_argument("--note", help="why this split, in the operator's own words")
    pools.add_argument(
        "--who", action="append", help="print which pool a reader id falls in"
    )
    pools.set_defaults(func=cmd_pools)

    axes_cmd = sub.add_parser(
        "axes", help="the named axes feedback may be about, and their counters"
    )
    axes_cmd.add_argument(
        "--text", type=Path, help="count every axis over one file of prose"
    )
    axes_cmd.set_defaults(func=cmd_axes)

    directions = sub.add_parser(
        "directions", help="what steering readers say about each axis, and what is missing"
    )
    directions.add_argument(
        "--establish",
        action="store_true",
        help="record every direction that clears its bar (an operator act, like `calibrate`)",
    )
    directions.add_argument(
        "--attainability",
        action="store_true",
        help="check the bar can do what it says: smallest clearing k, and power",
    )
    directions.set_defaults(func=cmd_directions)

    feedback_cmd = sub.add_parser(
        "feedback", help="what would reach the next draft prompt for a book, and why"
    )
    feedback_cmd.add_argument("--book", required=True)
    feedback_cmd.add_argument("--branch", required=True)
    feedback_cmd.add_argument("--json", action="store_true", help="machine-readable output")
    feedback_cmd.set_defaults(func=cmd_feedback)

    contrast = sub.add_parser(
        "contrast", help="run one judge batch over a span's candidates (E6, never a verdict)"
    )
    contrast.add_argument("--book", required=True)
    contrast.add_argument("--branch", required=True)
    contrast.add_argument("--logical-id", required=True)
    contrast.add_argument(
        "--judge", default="unnamed", help="the model staffing the judge role, for provenance"
    )
    contrast.set_defaults(func=cmd_contrast)

    discards = sub.add_parser(
        "discards",
        help="judge sentences that located nothing — the corpus for axes we cannot yet name",
    )
    discards.add_argument("--book")
    discards.add_argument(
        "--reason", choices=[member.value for member in feedback_domain.DiscardReason]
    )
    discards.add_argument("--limit", type=int, default=40)
    discards.set_defaults(func=cmd_discards)

    blame = sub.add_parser(
        "blame",
        help="counter value beside the feedback live when each scene was drafted",
    )
    blame.add_argument("--book", required=True)
    blame.add_argument("--branch", required=True)
    blame.add_argument("--axis", required=True, choices=sorted(axes_domain.AXES))
    blame.add_argument("--json", action="store_true", help="machine-readable output")
    blame.set_defaults(func=cmd_blame)

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

    calibrations = sub.add_parser(
        "calibrations", help="evidence that a craft metric predicts human judgment"
    )
    calibrations.add_argument("--metric")
    calibrations.set_defaults(func=cmd_calibrations)

    calibrate = sub.add_parser(
        "calibrate",
        help="record measured held-out evidence for one craft metric at one threshold",
    )
    calibrate.add_argument("--metric", required=True, help="the metric id being calibrated")
    calibrate.add_argument(
        "--threshold", type=float, required=True, help="the value at which it starts failing"
    )
    calibrate.add_argument(
        "--direction",
        required=True,
        choices=[member.value for member in calibration.Direction],
        help="which side of the threshold is the failing side; guessing inverts the gate",
    )
    calibrate.add_argument(
        "--holdout", type=int, required=True, help="held-out judgments it was measured on"
    )
    calibrate.add_argument(
        "--flagged",
        type=int,
        required=True,
        help="how many of the holdout it fired on",
    )
    # **`--precision` is replaced by counts rather than kept beside them.** A rate cannot be
    # turned back into the confidence bound promotion now turns on, and the operator typing
    # 0.83 beside 17 flags was asserting 14.11 correct ones. Counts are also what the measurer
    # actually has in front of them; the rate was always a division they did first.
    calibrate.add_argument(
        "--correct",
        type=int,
        required=True,
        help="how many of --flagged the human agreed with; precision is derived from the pair",
    )
    calibrate.add_argument(
        "--selection-family",
        type=int,
        required=True,
        help="candidate gates safety-tested against this holdout — thresholds, directions and "
        "metrics tried. 1 only if the threshold was fixed before these labels were seen; the "
        "confidence level is divided by this",
    )
    calibrate.add_argument(
        "--clusters",
        type=int,
        required=True,
        help="independent books or generation runs the flagged set spans; flags from one book "
        "are not independent trials",
    )
    calibrate.add_argument("--recall", type=float)
    calibrate.add_argument(
        "--expires", help="ISO date after which this stops being current evidence"
    )
    # **`--verdicts-digest` is deleted rather than defaulted.** It read
    # `args.verdicts_digest or current`, so omitting it stamped this store's own answered-audit
    # digest onto numbers measured against thirteen thousand strangers' chapters — which then
    # matched the digest `_craft_ladder` recomputes at every draft, so the staleness clause
    # could never fire and the row promoted. Its one documented legitimate use was "measured
    # elsewhere", and "elsewhere" is now a *class* rather than an omission: a population
    # calibration derives its digest from the profile it read the stop out of. There is no
    # longer a case where a human should be typing an evidence digest.
    calibrate.add_argument(
        "--evidence-class",
        required=True,
        choices=[
            member.value
            for member in calibration.EvidenceClass
            if member is not calibration.EvidenceClass.UNCLASSIFIED
        ],
        help="what the numbers are about: judgment (humans read our scenes), preference "
        "(humans chose between paired texts, §61), population (published-corpus "
        "distribution), behaviour (aggregate reader behaviour on other authors' stories). "
        "Required, because a default would hand the permissive class to a caller that "
        "said nothing",
    )
    calibrate.add_argument(
        "--grain",
        default=calibration.Grain.UNIT.value,
        choices=[member.value for member in calibration.Grain],
        help="the unit the label is attached to. A craft gate refuses a scene, so evidence "
        "labelled per story refuses nothing however large its sample",
    )
    calibrate.add_argument(
        "--cohort",
        help="population only: the profile cohort the threshold is read from",
    )
    calibrate.add_argument(
        "--control-cohort",
        help="population only: the cohort holding the confound fixed, measured in the same "
        "band at the same threshold. Required for a population calibration — a number with "
        "no control beside it is what the refutation ledger is a list of",
    )
    calibrate.add_argument(
        "--band", help="population only: the length band, e.g. 700-1100"
    )
    calibrate.add_argument(
        "--quantile",
        help="population only: the stored ladder stop the threshold must equal, e.g. p99. "
        "The threshold is looked up rather than typed",
    )
    calibrate.add_argument("--note")
    calibrate.set_defaults(func=cmd_calibrate)

    corpus_add = sub.add_parser(
        "corpus-add",
        help="add one matched published-human excerpt to the comparison corpus (§61)",
    )
    corpus_add.add_argument(
        "path", type=Path, nargs="?", help="text file to read; stdin if omitted"
    )
    corpus_add.add_argument(
        "--source",
        required=True,
        help="where the excerpt is from, e.g. a serial title. A matching covariate, "
        "required rather than defaulted",
    )
    corpus_add.add_argument(
        "--genre", required=True, help="matching covariate, e.g. litrpg"
    )
    corpus_add.add_argument(
        "--era",
        required=True,
        help="matching covariate, e.g. pre-2023 — the confound the craft profile's "
        "control cohort exists to hold fixed",
    )
    corpus_add.set_defaults(func=cmd_corpus_add)

    protocol_cmd = sub.add_parser(
        "protocol",
        help="pre-register a pairwise comparison frame — the frame is the claim (§61)",
    )
    protocol_cmd.add_argument(
        "--frame",
        required=True,
        help="the comparator sampling frame, as prose: what population the other side is "
        "drawn from and what question the reader answers. Declared before the first "
        "reader is paid",
    )
    protocol_cmd.add_argument(
        "--tie-policy",
        required=True,
        choices=[member.value for member in preference.TiePolicy],
        help="how a tie enters the win rate: half_win counts it as half a win, drop "
        "excludes it. Declared before the first judgment (§61 pre-registration 2)",
    )
    protocol_cmd.add_argument(
        "--grain",
        required=True,
        choices=[member.value for member in preference.PairGrain],
        help="what a reader is handed: one scene, or one chapter (chapter drawing is not "
        "yet built)",
    )
    protocol_cmd.set_defaults(func=cmd_protocol)

    pair_draw = sub.add_parser(
        "pair-draw",
        help="draw blinded pairs for a protocol — content-derived, never random",
    )
    pair_draw.add_argument(
        "--protocol", help="a declared protocol id; required unless --siblings"
    )
    pair_draw.add_argument(
        "--siblings",
        action="store_true",
        help="draw system-vs-system pairs under the built-in internal-v0 frame "
        "(selection evidence, not the external published-human comparison)",
    )
    pair_draw.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="share of the pair space to draw, by bucket arithmetic on pair identity. "
        "1.0 draws the whole cross product; raising a rate later draws a superset of "
        "every earlier draw, never a reshuffle",
    )
    pair_draw.set_defaults(func=cmd_pair_draw)

    pairs_cmd = sub.add_parser(
        "pairs", help="the blinded pair queue: both texts, no provenance"
    )
    pairs_cmd.add_argument(
        "--pending", action="store_true", help="only samples awaiting a reader"
    )
    pairs_cmd.add_argument(
        "--quiet", action="store_true", help="list the samples without printing prose"
    )
    pairs_cmd.add_argument(
        "--reader",
        help="show only what this reader may answer under the measurement firewall",
    )
    pairs_cmd.set_defaults(func=cmd_pairs)

    pair_judge = sub.add_parser(
        "pair-judge", help="record one pairwise preference verdict"
    )
    pair_judge.add_argument("sample_id")
    pair_judge.add_argument(
        "verdict",
        choices=[member.value for member in preference.PairVerdict],
        help="relative to presented position; not_sure is abstention and is measured",
    )
    pair_judge.add_argument(
        "--reader", required=True, help="who judged it — a cluster dimension of the bound"
    )
    pair_judge.add_argument(
        "--recognized",
        required=True,
        choices=["yes", "no"],
        help="did the reader recognise either passage? Required, because a judgment that "
        "never answered the question cannot be excluded — §58 measured familiarity "
        "swinging a score several times harder than real damage. yes is stored and "
        "excluded from analysis (§61 pre-registration 3)",
    )
    pair_judge.add_argument("--note", help="what the reader noticed")
    pair_judge.set_defaults(func=cmd_pair_judge)


    win_rate = sub.add_parser(
        "win-rate",
        help="win rate against the matched corpus, led by its clustered lower bound",
    )
    win_rate.add_argument("--protocol", required=True, help="the declared protocol id")
    win_rate.add_argument(
        "--alpha",
        type=float,
        default=calibration.PROMOTION_ALPHA,
        help="two-sided confidence level for this protocol alone; the headline claim "
        "divides it by the candidate-book count (§61 pre-registration 5)",
    )
    win_rate.set_defaults(func=cmd_win_rate)

    craft = sub.add_parser("craft", help="advisory craft measurements, and their limits")
    craft.add_argument("--metric")
    craft.set_defaults(func=cmd_craft)

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

    lock_constraints = sub.add_parser(
        "lock-constraints",
        help="lock the plan constraints a person's directive produced; unlocked, they are in "
        "the plan and in no prompt",
    )
    lock_constraints.add_argument("--book")
    lock_constraints.add_argument("--branch")
    lock_constraints.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be locked and what would be refused, and write nothing",
    )
    lock_constraints.set_defaults(func=cmd_lock_constraints)

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
