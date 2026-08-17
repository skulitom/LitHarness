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
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters import contracts_fixtures, evaluation_artifact
from litharness.adapters.continuity_cli import ContinuityCliRunner
from litharness.adapters.sqlite_store import MigrationsMissing, SqliteStore
from litharness.application import export as export_module
from litharness.application import status as status_module
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.directive_planner import DIRECTIVE_PLAN, make_directive_plan_handler
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
from litharness.domain import audit, calibration, extraction, impact, propagation

# Aliased: `build_parser` binds a local `craft` for the subparser, and a module named the
# same thing would work only by scope luck.
from litharness.domain import craft as craft_domain
from litharness.domain import state as state_mod
from litharness.domain.beats import SIX_BEAT, arc_template
from litharness.domain.budget import BudgetPolicy
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus, directive_id_for
from litharness.domain.draft import DraftPolicy
from litharness.domain.events import Event, EventType
from litharness.domain.exceptions import ExceptionStatus
from litharness.domain.findings import Status as finding_status
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.plan_refinement import PlanProposalStatus, rollback_proposal
from litharness.domain.plans import import_plan, premise_of
from litharness.domain.policy import Outcome, PolicyDecision, decision_id_for
from litharness.domain.revision import import_manuscript, new_book
from litharness.domain.state import import_state
from litharness.providers import build_default_registry

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

    `plan/provider-adapters.md` §5 says provider selection "is config, versioned like every
    other policy, never hardcoded", and it was hardcoded — so the only way to run a book on
    local models was to pass flags on every invocation. These two variables are how a
    machine says "free by default here" without changing the order this project ships,
    which §5 and §1a settle on prose quality rather than on cost.
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


def _conductor(store: SqliteStore, args: argparse.Namespace) -> Conductor:
    registry = build_default_registry(
        args.prefer, refuse_billing=args.no_billing, model=args.model
    )
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
            **(
                {"token_budget": args.context_budget}
                if args.context_budget is not None
                else {}
            ),
        ),
        handlers={
            DIRECTIVE_PLAN: make_directive_plan_handler(store, args.project, actor=args.holder),
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
    try:
        result = loop.tick(_now())
    finally:
        store.close()

    print(f"{result.outcome.value} tick={result.tick_id}", end="")
    if result.job_id:
        print(f" job={result.job_id}", end="")
    print(f" reconciled={result.reconciled} ingested={result.ingested}")
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
    for item in items:
        flag = "BLOCKS" if item.blocks else "      "
        print(
            f"{item.finding_id}  {flag}  {item.severity.value:<8} {item.status.value:<20} "
            f"{item.rule_or_critic_id or item.category}"
        )
        print(f"    {item.message}")
        if item.logical_id:
            print(f"    at {item.logical_id}")
    blocking = sum(1 for item in items if item.blocks)
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
        print(f"  litharness judge {sample.sample_id} --keep-reading|--would-stop|--not-sure")
        print()
    counts = {"pending": sum(1 for item in pending if item.pending)}
    print(f"({len(pending)} sample(s), {counts['pending']} awaiting a reader)")
    return EXIT_OK


def cmd_judge(args: argparse.Namespace) -> int:
    """Record one human judgment. The only input to this system nothing else can supply.

    §1a.5's bar is "a majority of sampled chapters earn *I would keep reading* from readers
    who were not told what produced them", so that is the question asked rather than a rubric.
    `--not-sure` is a real answer: §10.4 asks for abstention to be measured, and a scale with
    no way to decline pushes a reader into a verdict they do not hold.
    """
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
    finally:
        store.close()

    digest = calibration.verdicts_digest_for(verdicts)
    today = _stamp(_now())[:10]
    for item in items:
        why = item.why_not_promotable(today, digest)
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
            "threshold out of; run tools/build_craft_profile.py",
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
        population: calibration.Population | None = None
        if evidence_class is calibration.EvidenceClass.POPULATION:
            built = _population_from_profile(args)
            if isinstance(built, int):
                return built
            population, digest, threshold = built
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
    # Checked against the digest for its own class, and against the answered count this store
    # actually holds — the comparison nothing anywhere was making, which is why a row claiming
    # fifty held-out judgments promoted against a store holding two.
    against = (
        craft_domain.profile_digest()
        if record.evidence_class is calibration.EvidenceClass.POPULATION
        else current
    )
    why = record.why_not_promotable(today, against, answered=len(answered))
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
    if why is None:
        print("    BLOCKING-ELIGIBLE: this metric may now park a scene it refuses")
    else:
        print(f"    advisory — not promotable: {why}")
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
    records: list[lc.StateRecord] = []
    if args.state:
        snapshot = lc.parse_artifact(
            lc.StateSnapshot, json.loads(Path(args.state).read_text(encoding="utf-8"))
        )
        records = list(import_state(snapshot, book_id=book_id, branch_id=branch_id).records)

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
    finally:
        store.close()

    print(revision.revision_id)
    print(f"  book={book_id} branch={branch_id}")
    print(f"  {args.scenes} empty scene(s); template {template.template_id}")
    print(f"  {len(records)} seed state record(s)")
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

    conflicted = [item for item in proposals if item.status is PlanProposalStatus.CONFLICTED]
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
        "LITHARNESS_NO_OUTLINE. The control arm of the measurement in §54, and the right "
        "flag for a book somebody outlines by hand — a scene with no statement drafts "
        "exactly as it did before outlines existed",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LITHARNESS_MODEL"),
        help="the Ollama model to generate with, e.g. phi4:latest; also read from "
        "LITHARNESS_MODEL. Ollama only, because the CLI adapters take vendor model names "
        "from a different namespace. Scene length is a property of the generator, and until "
        "this flag existed every run used the qwen3:4b default whatever the record says",
    )
    parser.add_argument(
        "--prefer",
        default=os.environ.get("LITHARNESS_PREFER"),
        help="put this provider first, e.g. ollama for a local run; also read from "
        "LITHARNESS_PREFER. It stays a preference: an unhealthy choice still falls back, "
        "and the fallback is recorded",
    )
    parser.add_argument(
        "--no-billing",
        action="store_true",
        default=_env_flag("LITHARNESS_NO_BILLING"),
        help="refuse every billing provider for this run; also read from "
        "LITHARNESS_NO_BILLING. Not the same as --prefer: a preference for a free provider "
        "still bills the moment that provider blips",
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

    judge = sub.add_parser("judge", help="record one human verdict on a sampled scene")
    judge.add_argument("sample_id")
    answer = judge.add_mutually_exclusive_group(required=True)
    answer.add_argument("--keep-reading", action="store_true")
    answer.add_argument("--would-stop", action="store_true")
    answer.add_argument(
        "--not-sure", action="store_true", help="abstention is a real answer and is measured"
    )
    judge.add_argument("--note", help="what you noticed; the most useful field here")
    judge.add_argument("--by", help="who read it (defaults to --holder)")
    judge.set_defaults(func=cmd_judge)

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
        help="what the numbers are about: judgment (humans read our scenes), population "
        "(published-corpus distribution), behaviour (aggregate reader behaviour on other "
        "authors' stories). Required, because a default would hand the permissive class to "
        "a caller that said nothing",
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
    new.add_argument("--book", help="book id; a fresh uuid by default")
    new.add_argument("--branch", help="branch id; a fresh uuid by default")
    new.set_defaults(func=cmd_new)

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
