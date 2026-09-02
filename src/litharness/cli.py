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
import dataclasses
import json
import os
import shutil
import sqlite3
import sys
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters import contracts_fixtures, evaluation_artifact
from litharness.adapters.continuity_cli import ContinuityCliRunner
from litharness.adapters.sqlite_store import MigrationsMissing, SqliteStore, StoredEvent
from litharness.application import concept as concept_mod
from litharness.application import covers, recruiter, revoice, titles, world_agent
from litharness.application import exemplars as exemplars_mod
from litharness.application import export as export_module
from litharness.application import library as library_module
from litharness.application import overview as overview_mod
from litharness.application import readers as readers_mod
from litharness.application import roster as roster_mod
from litharness.application import status as status_module
from litharness.application import world as world_mod
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.directive_planner import DIRECTIVE_PLAN, make_directive_plan_handler
from litharness.application.director import (
    DIRECT,
    make_director_handler,
)
from litharness.application.director import (
    render_request as render_director_request,
)
from litharness.application.editorial import (
    EDITORIAL_INTERPRET,
    MECHANISM_ID,
    READER_OBSERVE,
    experimental_mechanism,
    make_editorial_interpret_handler,
    make_reader_observation_handler,
    mechanism_spec_digest,
)
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
from litharness.application.narrative_planner import (
    render_request as render_narrative_request,
)
from litharness.application.outline import (
    BOOK_OUTLINE,
    make_outline_handler,
    render_outline_request,
)
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.planner import make_plan_selector, plan_progress
from litharness.application.planner import render_prompt as render_scene_prompt
from litharness.application.repair import (
    EVALUATE_REVISION,
    REPAIR_FINDING,
    SCENE_SUMMARY,
    evaluation_job_for,
    make_evaluation_handler,
    make_repair_handler,
    render_repair_request,
)
from litharness.application.reviser import render_revision_request
from litharness.application.summarize import (
    SUMMARY_SCHEMA,
    make_summary_handler,
    render_summary_prompt,
)
from litharness.domain import characters as characters_mod
from litharness.domain import directors as directors_domain
from litharness.domain import (
    extraction,
    gamesystem,
    genre,
    house,
    integrity,
    propagation,
    schema_words,
)
from litharness.domain import rivals as rivals_mod
from litharness.domain import state as state_mod
from litharness.domain import text as text_mod
from litharness.domain import voice as voice_domain
from litharness.domain import worlds as worlds_domain
from litharness.domain import writers as writers_domain
from litharness.domain.beats import Beat, BeatTemplate, TemplateMismatch, arc_template, beats_for
from litharness.domain.budget import BudgetPolicy, Spend
from litharness.domain.budget import check as budget_check
from litharness.domain.context import (
    CAST,
    CONSTRAINTS,
    FACTS,
    PREMISE,
    PRIOR_PROSE,
    SUMMARIES,
    THREADS,
    ContextPacket,
    PackedItem,
    count_tokens,
)
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus, directive_id_for
from litharness.domain.draft import DraftPolicy
from litharness.domain.editorial import (
    QualificationEvidence,
    ReaderMechanism,
    ReaderMechanismStatus,
    mechanism_version_id_for,
)
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.exceptions import ExceptionStatus
from litharness.domain.failures import OperationalFailure
from litharness.domain.findings import Finding, Severity
from litharness.domain.findings import Status as finding_status
from litharness.domain.generation import CompletionRequest, CompletionResult
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plan_refinement import (
    PlanProposalStatus,
    PlanRevision,
    StoredPlanProposal,
    rollback_proposal,
)
from litharness.domain.plans import (
    FIRST_PERSON_CONSTRAINT,
    FIRST_PERSON_PLAN_ID,
    import_plan,
    premise_of,
    scene_plan_for,
)
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decision_id_for,
)
from litharness.domain.promises import Promise, normalise_kind, promise_id_for
from litharness.domain.revision import Revision, append_scenes, import_manuscript, new_book
from litharness.domain.salience import (
    build_state_continuity_items,
    ecological_manifest,
    evidence_census,
    private_battery,
    public_battery,
)
from litharness.domain.serials import SerialShape, arcs_of, beats_for_serial
from litharness.domain.state import import_state
from litharness.providers import ProviderRegistry, build_default_registry
from litharness.providers.cli import subprocess_runner

#: Exit codes, which are how whatever drives `tick` reads the outcome. See the module
#: docstring.
EXIT_OK = 0
EXIT_ATTENTION = 1
EXIT_FAULT = 2

DEFAULT_DB = "litharness.db"
SERIAL_POSITION_CAPACITY = 100_000

#: Where `--database` looks when nobody passed one. **This exists so an agent's command line
#: can be exactly `litharness world <view>`**: a tool allowance is only a containment if it
#: can be written narrowly, and an allowance naming `litharness world` subcommands stops being
#: narrow the moment a `--database` flag has to sit between the binary and the subcommand. The
#: flag still wins where it is given, so every existing invocation is unchanged.
DATABASE_ENV = "LITHARNESS_DATABASE"

#: Where the installation's roster lives, when it lives anywhere at all. **Without this, "a
#: roster belongs to the installation" was a comment and not a behaviour**: `--writer` resolved
#: through whatever `--database` was open, so an accepted writer could not reach a fresh book
#: database — serial pilot 13 hit that as a free exit-2 and bridged it by cloning the entire
#: store through `litharness backup`, which drags every unrelated table along. Set this (or
#: `--roster-database`, which wins) to the roster store's path and the roster suite, the
#: Recruiter, `revoice` and every `--writer` resolution use it; unset, everything falls back to
#: the open database and nothing changes. It is one home rather than an export/import pair
#: because a copy is where the rails die quietly: a second path that writes `accepted` rows,
#: and a refusal (§149, terminal by design) that keeps drafting in every database that imported
#: the writer before the operator said no. Stage-0 §151 records the choice.
ROSTER_DATABASE_ENV = "LITHARNESS_ROSTER_DATABASE"

#: **The shelf and the form reach the Recruiter's child process through the environment, never
#: its command line**, which is `DATABASE_ENV`'s argument twice more. A flag between the binary
#: and the subcommand widens the allowance to every command this CLI has; and a value the agent
#: types is a value the agent chose, where the form is a registered arm that the runner stamps.
#: The shelf variable also makes "one recruit call per specialization" mechanical, and it is
#: what `roster accept` reads to refuse an admission from inside a run in flight.
RECRUIT_SHELF_ENV = "LITHARNESS_RECRUIT_SHELF"
RECRUIT_SHAPE_ENV = "LITHARNESS_RECRUIT_SHAPE"

#: `--writer`'s help for the four subcommand overrides, in one place. A parser is built before
#: `--database` is parsed, so it can name the compiled cast and cannot enumerate a roster; four
#: copies of that sentence would drift.
_WRITER_OVERRIDE_HELP = (
    f"the compiled cast ({', '.join(writers_domain.CAST)}), or any accepted writer on the "
    "roster (--roster-database's when one is configured, else this database's), which "
    "`litharness roster show` lists; overrides the global --writer"
)

#: **The listing loop's first refusing gate, and the only market-derived number under `src/`.**
#: A listing above this many coordinator tokens per hundred words is redrawn rather than kept.
#:
#: The value sits just above the maximum observed across the sixty admitted published
#: listings the research side already holds (5.8823...), so at this ceiling nothing this
#: market actually publishes is refused and three of the twenty-one listings this project
#: has drawn are. The two decimals are rounded UP for exactly that reason: 5.88 reads as the
#: maximum and refuses the listing that set it, which the durable test in
#: `tests/test_listing_coordinator_gate.py` caught before this shipped. A p90 ceiling
#: was measured and rejected: it refuses a tenth of the market's own listings, and the standing
#: lesson is that a recall-tuned refusal gate has inverted error costs.
#:
#: It is a scalar and not a corpus: it reconstructs no prose, carries no style, and is consumed
#: to refuse rather than to generate. `plan/stage-0-decisions.md` §147 records the derivation,
#: the four attainability checks behind it, and why it sits outside RS1's purpose;
#: `plan/reader-read-5.md` §4.1 is the read that found the defect. Re-derive it research-side.
LISTING_COORDINATOR_CEILING = 5.89

#: How many times the listing loop will draw before keeping what it has. Bounded so a writer
#: locked into one construction cannot spend the loop in a redraw cycle; on exhaustion the
#: least-chained draw is kept and the gate on the decision row records the failure.
LISTING_DRAW_ATTEMPTS = 3


def _creation_template(scenes: int, shape: SerialShape) -> tuple[BeatTemplate, bool]:
    """The sheet for a new structure and whether that structure is an endless serial.

    New production defaults to complete arcs.  Explicit short books remain a supported finite
    fixture/pilot shape; they use their whole-book sheet and are never mistaken for an open arc.
    Once a structure reaches one full arc, partial trailing arcs are refused.
    """
    if scenes < shape.scenes_per_arc:
        return arc_template(scenes), False
    if scenes % shape.scenes_per_arc:
        raise TemplateMismatch(
            f"an open-ended serial is planned in complete arcs of "
            f"{shape.scenes_per_arc} scenes; asked for {scenes}"
        )
    return arc_template(shape.scenes_per_arc), True


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


def _roster_database(args: argparse.Namespace) -> Path:
    """Where the roster lives: the installation's store when one is configured, else the open
    database. The fallback is what every invocation before `--roster-database` existed got."""
    configured: Path | None = getattr(args, "roster_database", None)
    return configured if configured is not None else Path(args.database)


def _roster_store(args: argparse.Namespace) -> SqliteStore:
    """The store the roster suite, the Recruiter and `revoice` operate on.

    These commands are roster-native: the rows they read, the proposals and decisions they
    write, and the exemplars a voiced writer's `exemplar_digest` points at all belong beside
    each other, so the whole command targets one store rather than splitting a writer from its
    provenance across two files.
    """
    return SqliteStore.open(_roster_database(args))


def _installed_writer(
    args: argparse.Namespace, name: str, store: SqliteStore | None
) -> tuple[writers_domain.Writer | None, str]:
    """`_resolve_writer`, read against the installation's roster when one is configured.

    **The configured roster replaces the open database's, it is not consulted beside it.** Two
    sources of truth would mean a stale row in a book database could shadow the installation's
    answer — including a refusal, which §149 makes terminal — and which of the two answered
    would be invisible in the output. When nothing is configured, or the configured path is the
    open database, this is exactly `_resolve_writer` and behaviour is unchanged.

    The roster store is opened only for the lookup and closed before returning: a `Writer` is a
    frozen value, so nothing downstream needs the connection that produced it. `SqliteStore.open`
    creates the file the way `--database` does — a configured path is a deliberate location, and
    a mistyped one cannot resolve silently: an empty roster refuses every stored name loudly and
    resolves nothing but the compiled cast, which no roster could have changed.
    """
    wanted = getattr(args, "roster_database", None)
    if wanted is None or Path(wanted).resolve() == Path(args.database).resolve():
        return _resolve_writer(name, store)
    if not name.strip():
        return None, ""
    with SqliteStore.open(wanted) as roster_store:
        return _resolve_writer(name, roster_store)


def _draft_policy(args: argparse.Namespace) -> DraftPolicy:
    """Generation policy from the command line, defaulting to `DraftPolicy`'s.

    Only the target is exposed. The shape bounds are gates, and §1a.1's warning applies to
    both directions — an operator who could lower `min_chars` to make a run go green would
    have turned the one deterministic check on drafts into a formality.
    """
    default = DraftPolicy()
    return DraftPolicy(
        target_words=(args.target_words if args.target_words is not None else default.target_words)
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


def _say(text: str) -> None:
    """Print model-written text, in UTF-8, whether stdout is a console or a file.

    **`print` goes through the console's own codec, which on this host is cp1252**, and every
    piece of prose a model returns is full of things cp1252 cannot represent. `_write_document`
    records the same defect for exports; this is the operator surface's half of it, and it was
    found the expensive way: `architect seed` ran for sixteen minutes, declared 278 records, and
    then died on `UnicodeEncodeError: '\\u2192'` while printing the agent's closing report —
    the one artifact that says what it built and what it left open, lost to an arrow.

    `sys.stdout.flush()` first, so text already buffered above this stays in order.
    """
    stream = getattr(sys.stdout, "buffer", None)
    if stream is None:  # a capturing or text-only stdout, e.g. under pytest's capsys
        print(text)
        return
    sys.stdout.flush()
    stream.write(text.encode("utf-8") + b"\n")
    stream.flush()


def _rivals(args: argparse.Namespace) -> tuple[rivals_mod.Rival, ...]:
    """The admitted competitor pool, or empty when the operator supplied none.

    **The package never goes looking for these**, which is what keeps RS1 intact: nothing under
    `src/litharness/` may reference a corpus, and a loader that knew where RoyalRoad listings
    live would be one. An operator hands in a JSON list and `rivals.admit_all` either admits
    every row or refuses the file naming the one that failed.

    Empty is the control arm and is what every reading before 2026-08-26 measured: a reader with
    no named competitor, choosing against a page this system only told them was full.
    """
    path = getattr(args, "rivals", None)
    if not path:
        return ()
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"litharness: {path} is not a list of rivals")
    try:
        return rivals_mod.admit_all(rows)
    except rivals_mod.IllegalRival as error:
        raise SystemExit(f"litharness: {path}: {error}") from error


def _resolve_writer(
    name: str, store: SqliteStore | None = None
) -> tuple[writers_domain.Writer | None, str]:
    """The writer a `--writer` name means, or `None` and the reason it is nobody.

    **The accepted roster first, then the compiled cast**, which is
    `plan/handoff-writer-recruiter.md`'s word — but the order is safe only because the two
    namespaces cannot overlap. `writers.RESERVED_NAMES` refuses a stored row named after a cast
    writer or a probe, so for every name that can legitimately exist both orders return the same
    writer. The order then costs nothing and buys what the brief wanted: an accepted recruit is
    castable without editing Python, ever.

    The collision check below is a second lock and is not decoration — the write-time guard
    cannot see the case where `CAST` grows *later* to a name a stored writer already holds.
    Where it fires **nothing resolves**, and neither writer is silently preferred.

    **`BUILTIN` is reserved but not resolvable.** Those ten measure whether a dossier binds at
    all; not one reads the genre this project publishes in and none has ever reached a prompt,
    so making `--writer geology` draft a book would be a behaviour change nobody asked for.

    **A proposed writer is not a writer yet.** `roster accept` is a person's act with a decision
    row behind it, and a recruit that could draft merely by being named would make that act
    optional, which is the rail the whole roster is built around.

    `store` is `None` where a caller has no database open and must not create one:
    `SqliteStore.open` creates and migrates the file, so `prompts`, which has never touched a
    store, would otherwise leave a `litharness.db` behind for an inspection command.

    Returns its reason rather than raising it, because three of the four callers print and
    return `EXIT_FAULT`; `_selected_writer` is the raising wrapper for the conductor, where
    `_director_id`'s `SystemExit` is the established shape.
    """
    wanted = name.strip()
    if not wanted:
        return None, ""
    if store is not None:
        rows = store.roster_rows(name=wanted)
        if rows:
            if wanted in writers_domain.RESERVED_NAMES:
                return None, (
                    f"litharness: {wanted!r} names both a stored writer and a compiled one. "
                    "The compiled controls the roster is read against must not be shadowed; "
                    "rename or discard the stored row"
                )
            if any(
                row["status"] == writers_domain.RosterStatus.ACCEPTED.value for row in rows
            ):
                return store.accepted_writer(wanted), ""
            # **A refused writer is excluded here exactly as a proposed one is, but it must not
            # be told the same thing.** The acceptance sentence points at a command that cannot
            # work on it — `roster refuse` is terminal and `roster accept` skips a refused row —
            # so an operator following that advice gets "no proposed writer named" and no idea
            # why. A changed mind is a new proposal, and that is what this says (stage-0 §149).
            if all(
                row["status"] == writers_domain.RosterStatus.REFUSED.value for row in rows
            ):
                return None, (
                    f"litharness: writer {wanted!r} was refused, and a refusal is terminal. "
                    "There is no un-refuse: declare the dossier again to propose it afresh, "
                    "which is legal under this name because only acceptance holds one"
                )
            return None, (
                f"litharness: writer {wanted!r} is proposed but not accepted. Acceptance is an "
                "operator act and carries a decision row; a machine may not cast a writer it "
                f"drafted. `litharness roster accept {wanted}`"
            )
    writer = writers_domain.CAST.get(wanted)
    if writer is None:
        return None, (
            f"litharness: no writer named {wanted!r}; the cast is "
            f"{', '.join(writers_domain.CAST)}, and `litharness roster show` lists every "
            "writer the roster holds"
        )
    return writer, ""


def _concept_from(path: str | os.PathLike[str] | None) -> concept_mod.Concept | None:
    """The settled concept at `path`, `None` for none, and a refusal for one that will not read.

    Refused before any paid call, like every other input this CLI reads off disk (§19.1): a
    concept the stages cannot use is a fault to name at the one moment naming it is free.
    """
    if not path:
        return None
    try:
        return concept_mod.Concept.from_text(Path(path).read_text(encoding="utf-8"))
    except (OSError, concept_mod.MalformedConcept) as error:
        raise SystemExit(f"litharness: {path}: {error}") from error


def _selected_shelf(args: argparse.Namespace) -> exemplars_mod.Shelf | None:
    """Resolve `--exemplars` to the shelf the writer is shown, or `None` for the control.

    `_selected_writer`'s rule: a directory that does not exist, or holds no exemplar, is refused
    loudly rather than defaulted to nothing, because a mistyped path that silently produced the
    control arm is the worst failure available to a run whose question is whether the arms
    differ (stage-0 §196).
    """
    root = getattr(args, "exemplars", "") or ""
    if not root:
        return None
    try:
        return exemplars_mod.load_shelf(
            Path(root), limit=int(getattr(args, "exemplars_limit", exemplars_mod.DEFAULT_LIMIT))
        )
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"litharness: --exemplars: {error}") from error


def _selected_writer(
    args: argparse.Namespace, store: SqliteStore | None = None
) -> writers_domain.Writer | None:
    """Resolve `--writer` to a writer, or `None` for the anonymous control.

    `_director_id`'s rule, for `_director_id`'s reason: **an unregistered name is refused
    loudly rather than defaulted to nobody**, because a typo that silently produced the
    control arm is the worst failure available to a run whose whole question is whether the
    arms differ. A name that is declared but not yet accepted is refused for that reason and
    for a second one: casting a proposal would be the machine hiring itself. The subcommands
    that had their own `--writer` before this was global keep it and win where both are given —
    `argparse.SUPPRESS` is what lets an unset one fall through to the global rather than
    overwriting it with `None`.
    """
    writer, reason = _installed_writer(args, getattr(args, "writer", "") or "", store)
    if reason:
        raise SystemExit(reason)
    return writer


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
    evaluator: Evaluator = evaluators[0] if len(evaluators) == 1 else CompositeEvaluator(evaluators)
    reader_mechanism = None
    if args.reader_checkpoints:
        baseline = experimental_mechanism(registered_at=_stamp(_now()))
        store.register_reader_mechanism(baseline)
        reader_mechanism = store.current_reader_mechanism(baseline.mechanism_id)
        if (
            reader_mechanism is not None
            and reader_mechanism.spec_digest != baseline.spec_digest
        ):
            raise SystemExit(
                "litharness: the current reader mechanism uses a specification this "
                "installation does not implement"
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
            chapters_per_arc=args.arc_chapters,
            chapters_per_volume=args.volume_chapters,
            open_ended=True,
            # Who is drafting. `None` without `--writer`, which is what every book written
            # before 2026-08-25 got and what this is read against.
            writer=_selected_writer(args, store),
            # How this shelf sounds (§196): `None` without `--exemplars`, which is every
            # book drafted before the shelf existed and the control it is read against.
            shelf=_selected_shelf(args),
            **({"token_budget": args.context_budget} if args.context_budget is not None else {}),
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
                reader_mechanism=reader_mechanism,
                reader_shape=SerialShape(args.chapter_scenes, args.arc_chapters),
                # **The reviser is off unless asked for** (§196, the operator's drop after the
                # keep/modify/drop milestone): two settled-listing A/Bs found no sentence win
                # the battery would accept, at 109% of the writer's cost, and reads 13 to 15
                # landed on its output. `--revise` is the arm that keeps it reachable.
                revise=bool(getattr(args, "revise", False)),
                shelf=_selected_shelf(args),
            ),
            READER_OBSERVE: make_reader_observation_handler(
                registry, store, args.project, budget=_budget(args)
            ),
            EDITORIAL_INTERPRET: make_editorial_interpret_handler(
                registry, store, args.project, budget=_budget(args)
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
            EVALUATE_REVISION: make_evaluation_handler(evaluator, store, args.project),
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
        # **The blocked books, asked of the same function the tick's selector consults.**
        # `plan_progress` has carried the refusal since §155.2 and the selector has honoured
        # it, but no command printed it — pilot 14 §7 watched a floored book return `no_work`
        # under a report reading `jobs {}` / `needs attention 0`, so a stopped board and a
        # board at rest were the same screen. Computed under the policy and serial shape
        # `cmd_tick` hands its selector, because the answer depends on both: the sentence
        # printed here is the sentence the next tick refuses with, not a second opinion.
        policy = _draft_policy(args)
        shape = SerialShape(args.chapter_scenes, args.arc_chapters)
        blocked = []
        for book_id, branch_id, _ in store.branches():
            progress = plan_progress(
                store, book_id, branch_id, policy=policy, serial_shape=shape
            )
            if progress.blocked_reason is not None:
                blocked.append(
                    status_module.BlockedBook(book_id, branch_id, progress.blocked_reason)
                )
        report = status_module.collect(
            store,
            _now(),
            budget=_budget(args),
            # The CLI is the only caller that knows whether the sibling evaluator is wired,
            # so it is the only one that can report the pack being off.
            continuity_evaluator=args.continuity_evaluator_command is not None,
            blocked=blocked,
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
            for row in store._connection.execute("SELECT name FROM schema_migrations ORDER BY name")
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
                print(f"{job.job_id}  {job.job_kind:<14} attempts={job.attempts} {job.error or ''}")
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
        items = store.findings(book_id, branch_id, logical_id=args.node, open_only=not args.all)
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
        finding_status.FALSE_POSITIVE
        if args.false_positive
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


def _introduced_in(store: SqliteStore, head: Revision, logical_id: str) -> tuple[str | None, int]:
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

    # **The text the reviser replaced, when there is one** (§187). Scoped to the revision that
    # introduced this scene's prose, so what comes back is the *pair*: this row's text against
    # the node content beside it. Absence is not a gap and is deliberately not on `absent` —
    # a scene drafted with the stage held back, or drafted before §187, has no such text
    # because the accepted prose is the writer's own. Nothing is computed from either string
    # here; §97.1 keeps this verb on the operator's side and a diff is a reader's act.
    kept = (
        [
            item
            for item in store.pre_revision_drafts(book_id, branch_id, logical_id=logical_id)
            if item.revision_id == introduced
        ]
        if introduced is not None
        else []
    )

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
            for item in store.findings(book_id, branch_id, logical_id=logical_id, open_only=False)
        ],
        "draft_before_revision": None
        if not kept
        else {
            "draft_id": kept[0].draft_id,
            "attempt": kept[0].attempt,
            "drafted_by": kept[0].drafted_by,
            "revised_by": kept[0].revised_by,
            "chars": len(kept[0].content),
            "content_sha256": kept[0].content_sha256,
            "em_dashes_removed": kept[0].em_dashes_removed,
            "recorded_at": kept[0].recorded_at,
            # **The text itself, so the diff needs no second tool.** The report that
            # commissioned this had to open a copy of the store to reach what no verb could
            # answer; `why --json` beside `export` is now the whole pair.
            "content": kept[0].content,
        },
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
            "cost not reported" if decision["cost_usd"] is None else f"${decision['cost_usd']:.4f}"
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
            f"{job['job_id']}  {job['job_kind']}  {job['status']}  {job['attempts']} attempt(s)",
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
            field("", "  ".join(f"{name} {count}" for name, count in sorted(sections.items())))

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

    # **Named and not printed, which is the rule this renderer already keeps for prose.**
    # `scene` above prints a length and a hash and sends the reader to `export` for the text;
    # the draft is prose too and gets the same treatment. `--json` carries both strings, so the
    # diff the attribution report could not compute is two verbs away and neither of them
    # opens the database. The prompt at the bottom is printed whole because a prompt is not
    # prose. Silence here means the accepted prose is the writer's own.
    kept: dict[str, Any] | None = dossier["draft_before_revision"]
    if kept is not None:
        field(
            "draft",
            f"{kept['chars']} char(s), sha256 {kept['content_sha256']} "
            f"({kept['em_dashes_removed']} em dash(es) removed)",
        )
        field(
            "",
            f"written by {kept['drafted_by']}, replaced by {kept['revised_by']} "
            f"on attempt {kept['attempt']}",
        )
        field("", "the text is in `--json`; the prose that replaced it is in `export`")

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
        epoch = store.bump_plan_epoch(book_id, branch_id, at=stamp, reason=args.reason or "replan")
        head = store.head(book_id, branch_id)
        blocking = [
            item for item in store.findings(book_id, branch_id, open_only=True) if item.blocks
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


def _mechanism_payload(store: SqliteStore, mechanism: ReaderMechanism) -> dict[str, object]:
    return {
        "mechanism_id": mechanism.mechanism_id,
        "version_id": mechanism.version_id,
        "status": mechanism.status.value,
        "spec_digest": mechanism.spec_digest,
        "evidence_digest": mechanism.evidence_digest,
        "registered_at": mechanism.registered_at,
        "evidence": store.reader_mechanism_evidence(mechanism.version_id),
    }


def cmd_reader_mechanism(args: argparse.Namespace) -> int:
    """Inspect, qualify, or withdraw the chapter-reader mechanism without a model call."""
    store = _store(args)
    stamp = _stamp(_now())
    try:
        current = store.current_reader_mechanism(MECHANISM_ID)
        if args.mechanism_action == "status":
            payload = None if current is None else _mechanism_payload(store, current)
            if args.json:
                _say(json.dumps(payload, ensure_ascii=False, indent=2))
            elif payload is None:
                print(f"{MECHANISM_ID}: unregistered")
            else:
                print(f"{MECHANISM_ID}: {payload['status']} {payload['version_id']}")
            return EXIT_OK

        if current is None:
            baseline = experimental_mechanism(registered_at=stamp)
            store.register_reader_mechanism(baseline)
            current = baseline

        if args.mechanism_action == "qualify":
            if current.status is not ReaderMechanismStatus.EXPERIMENTAL:
                raise ValueError("only the current experimental version may be qualified")
            raw = json.loads(args.evidence.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("qualification evidence must be one JSON object")
            evidence = QualificationEvidence.from_payload(raw)
            evidence.validate_for(MECHANISM_ID, mechanism_spec_digest())
            if evidence.candidate_version_id != current.version_id:
                raise ValueError("qualification evidence does not address the current candidate")
            qualified = ReaderMechanism(
                mechanism_id=MECHANISM_ID,
                version_id=mechanism_version_id_for(
                    MECHANISM_ID,
                    ReaderMechanismStatus.QUALIFIED,
                    current.spec_digest,
                    evidence.evidence_digest,
                ),
                status=ReaderMechanismStatus.QUALIFIED,
                spec_digest=current.spec_digest,
                evidence_digest=evidence.evidence_digest,
                registered_at=stamp,
            )
            store.register_reader_mechanism(qualified, evidence=raw)
            result = qualified
        elif args.mechanism_action == "withdraw":
            withdrawal = {
                "withdrawn_version_id": current.version_id,
                "reason": args.reason.strip(),
                "withdrawn_at": stamp,
            }
            if not withdrawal["reason"]:
                raise ValueError("withdrawal requires a reason")
            evidence_digest = payload_digest(withdrawal)
            result = ReaderMechanism(
                mechanism_id=MECHANISM_ID,
                version_id=mechanism_version_id_for(
                    MECHANISM_ID,
                    ReaderMechanismStatus.WITHDRAWN,
                    current.spec_digest,
                    evidence_digest,
                ),
                status=ReaderMechanismStatus.WITHDRAWN,
                spec_digest=current.spec_digest,
                evidence_digest=evidence_digest,
                registered_at=stamp,
            )
            store.register_reader_mechanism(result, evidence=withdrawal)
        else:
            raise ValueError(f"unknown mechanism action {args.mechanism_action}")

        payload = _mechanism_payload(store, result)
        if args.json:
            _say(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"{result.mechanism_id}: {result.status.value} {result.version_id}")
        return EXIT_OK
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"litharness: {error}", file=sys.stderr)
        return EXIT_FAULT
    finally:
        store.close()


def cmd_reader_evidence_audit(args: argparse.Namespace) -> int:
    """Census code-certifiable scene interventions and long-context coverage."""
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        if head is None:
            raise ValueError("this branch has no revision")
        census = evidence_census(
            head,
            store.state_records(book_id, branch_id),
            store.promises(book_id, branch_id),
            shape=SerialShape(args.chapter_scenes, args.arc_chapters),
        )
        items = build_state_continuity_items(census, head)
        manifest = ecological_manifest(census, items)
        report = {"census": census.to_payload(), "ecological_manifest": manifest}
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / "evidence-audit.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (args.out / "battery.public.json").write_text(
                json.dumps(public_battery(items), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (args.out / "battery.private.json").write_text(
                json.dumps(private_battery(census, items), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.json:
            _say(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            counts = census.to_payload()["candidate_counts"]
            assert isinstance(counts, dict)
            print(f"{book_id}/{branch_id} evidence census {census.digest}")
            for family, count in counts.items():
                print(f"  {family}: {count}")
            print(f"  ecological state items: {len(items)}")
            print("  no model called; no mechanism qualified")
        return EXIT_OK
    except (KeyError, OSError, ValueError) as error:
        print(f"litharness: {error}", file=sys.stderr)
        return EXIT_FAULT
    finally:
        store.close()


def cmd_readers(args: argparse.Namespace) -> int:
    """Put the simulated readership on a drafted scene, and record what it did.

    Two lanes over one chapter. The measurement pool spends a reading budget and either
    carries on, puts it down, or comes back later; the steering pool says what it is hoping
    happens next. Nobody is in both, so what steers the next chapter is never what measured
    this one.

    This command is an explicit experimental probe. Its legacy rows are reports only: raw
    answers do not reach a scene prompt or a plan. The automatic, versioned checkpoint path is
    enabled separately with `--reader-checkpoints`, and remains inert until its mechanism has
    qualifying evidence.
    """
    store = _store(args)
    stamp = _stamp(_now())
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        if args.history:
            mechanism = store.current_reader_mechanism("reader.anticipation.v0")
            if mechanism is None:
                print("reader.anticipation.v0: unregistered")
            else:
                evidence = (
                    f" evidence={mechanism.evidence_digest}"
                    if mechanism.evidence_digest
                    else ""
                )
                print(
                    f"{mechanism.mechanism_id}: {mechanism.status.value} "
                    f"{mechanism.version_id}{evidence}"
                )
            observations = store.reader_observations(book_id, branch_id)
            interventions = store.editorial_interventions(book_id, branch_id)
            realizations = store.intervention_realizations(book_id, branch_id)
            print(
                f"{book_id}/{branch_id}: {len(observations)} versioned observation(s), "
                f"{len(interventions)} editorial intervention(s), "
                f"{len(realizations)} accepted realization(s)"
            )
            for observation in observations:
                print(
                    f"  observation {observation.observation_id} "
                    f"checkpoint={observation.checkpoint_id} "
                    f"reader={observation.reader_id} "
                    f"mechanism={observation.mechanism_version_id} "
                    f"source={observation.logical_id}@"
                    f"{observation.source_content_hash[:12]} "
                    f"model={observation.provider}/{observation.model}"
                )
            for intervention in interventions:
                routed = (
                    f" directive={intervention.directive_id}"
                    if intervention.directive_id
                    else ""
                )
                print(
                    f"  intervention {intervention.intervention_id} "
                    f"{intervention.decision.value} "
                    f"checkpoint={intervention.checkpoint_id}{routed}"
                )
            for realization in realizations:
                print(
                    f"  realization {realization.realization_id} "
                    f"intervention={realization.intervention_id} "
                    f"target={realization.logical_id}@{realization.content_hash[:12]} "
                    f"plan={realization.plan_revision_id[:12]}"
                )
            return EXIT_OK
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
                print("no drafted scene to read")
                return EXIT_OK
            node = drafted[-1]
        chapter = (node.content or "").strip()
        if not chapter:
            print(f"litharness: {node.logical_id} has no prose", file=sys.stderr)
            return EXIT_FAULT

        registry = build_default_registry()
        spend = _StageSpend()
        # `_completion_call` adds to the stage tally AND to `run`, so they must be different
        # objects or every call is counted twice — which it was, on the first live run.
        calls = _ProviderCalls(
            registry=registry,
            store=store,
            args=args,
            stamp=stamp,
            run=_StageSpend(),
        )

        # **Every reader is stopped at the same place, and the passage is cut once rather
        # than per reader.** `text.stop_point` is §124's rule; a chapter of one paragraph has
        # no future in it and is read whole rather than refused, because the alternative is a
        # command that fails on a short scene for a reason nobody asked about.
        try:
            passage = text_mod.stop_point(chapter)
        except ValueError:
            passage = chapter
        stored_summaries = store.scene_summaries(book_id, branch_id)
        current_summaries: dict[str, str] = {}
        for scene in head.in_reading_order():
            if scene.kind is not NodeKind.SCENE or not scene.content:
                continue
            current = stored_summaries.get(scene.logical_id, {}).get(
                text_mod.content_hash(scene.content)
            )
            if current is not None:
                current_summaries[scene.logical_id] = current
        reading_context = readers_mod.accumulated_passage(
            head,
            node.logical_id,
            passage,
            summaries=current_summaries,
            shape=SerialShape(args.chapter_scenes, args.arc_chapters),
        )
        previous_reads = store.reader_reads(book_id, branch_id)
        reading_order = [
            scene.logical_id
            for scene in head.in_reading_order()
            if scene.kind is NodeKind.SCENE and not scene.tombstoned
        ]
        earlier_scene_ids = reading_order[: reading_order.index(node.logical_id)]
        pool_of_rivals = _rivals(args)

        choices: dict[str, Any] = {}
        wishes: dict[str, Any] = {}
        for reader in readers_mod.READERS:
            memory = readers_mod.prior_reading_memory(
                previous_reads,
                reader.reader_id,
                earlier_logical_ids=earlier_scene_ids,
            )
            drawn = None
            first = True
            if reader.pool == readers_mod.MEASUREMENT:
                if pool_of_rivals:
                    key = f"{head.revision_id}|{node.logical_id}|{reader.reader_id}"
                    drawn = rivals_mod.draw(pool_of_rivals, key)
                    first = rivals_mod.ours_first(key)
                # **The title only.** A rival whose blurb is on the page has been read for
                # free, which is §94's defect one object across; going to look has to cost
                # this chapter or the currency is not currency.
                request = readers_mod.render_choice_request(
                    reader,
                    reading_context,
                    drawn.title if drawn else "",
                    prior_memory=memory,
                )
            else:
                request = readers_mod.render_anticipation_request(
                    reader, reading_context, prior_memory=memory
                )
            result, refusal = _completion_call(request, calls=calls, spend=spend)
            parsed = result.parsed if result is not None else None
            if not isinstance(parsed, Mapping):
                if refusal:
                    print(f"  {reader.reader_id}: {refusal}", file=sys.stderr)
                continue
            if reader.pool == readers_mod.MEASUREMENT:
                choices[reader.reader_id] = parsed
                store.record_reader_read(
                    book_id,
                    branch_id,
                    head.revision_id,
                    node.logical_id,
                    reader_id=reader.reader_id,
                    pool=reader.pool,
                    created_at=stamp,
                    choice=str(parsed.get("next") or ""),
                    because=str(parsed.get("because") or ""),
                    rival_id=drawn.rival_id if drawn else None,
                    ours_first=first if drawn else None,
                )
            else:
                wishes[reader.reader_id] = parsed
                store.record_reader_read(
                    book_id,
                    branch_id,
                    head.revision_id,
                    node.logical_id,
                    reader_id=reader.reader_id,
                    pool=reader.pool,
                    created_at=stamp,
                    felt=str(parsed.get("felt") or ""),
                    expect_next=str(parsed.get("expect_next") or ""),
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
                    f"{node.logical_id}: {reading.carried_on} of {reading.answered} carried on"
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
        f"  left for another book {reading.left_for_other}"
        f"  put down {reading.put_down}  later {reading.come_back}"
    )
    for reader_id, choice, because in reading.said:
        _say(f"    {reader_id}: {choice} - {because}")
    for label, items in (
        ("it left them", wanting.felt),
        ("they expect next", wanting.expect_next),
        ("they are hoping for", wanting.hoping_for),
        ("they are dreading", wanting.dreading),
    ):
        if items:
            print(f"  {label}:")
            for item in items:
                _say(f"    - {item}")
    return EXIT_OK


def _listing_title(
    listing: str,
    *,
    writer: writers_domain.Writer | None,
    attempts: int,
    check: bool,
    calls: _ProviderCalls,
    spend: _StageSpend,
) -> tuple[str, titles.Availability | None, tuple[str, ...]]:
    """A title for this listing that a lookup did not find already in use.

    **The retry is the loop's, and what it retries on is a fact rather than a verdict.** A
    title comes back, `titles.read` decides in code whether an exact match was reported, and a
    match sends the taken name back to the same writer as a prohibition. Nothing ranks the
    titles against each other and nothing keeps a scoreboard — the previous title is not
    "worse", it is unavailable, which is the only thing this system is allowed to know about a
    title (§61(5), §105.1).

    Returns the title, its availability (or `None` when the lookup was not run) and every
    title the loop had to abandon. **An `UNKNOWN` verdict stops the retry**: a lookup that did
    not happen is not evidence of a collision, and burning three title calls on an outage
    would spend the writer's attempts on the environment's problem (§19.1).

    **§178's check runs before the lookup and out of the same attempt budget.** A title built
    out of this repository's own machinery vocabulary is dropped, named back to the writer as
    its own prohibition, and redrawn; it is checked first because it is free and the lookup is
    not. Serial Pilot 16's *Reading The Ladder Wrong* is the case. It does **not** join
    `abandoned`, which is the taken-title prohibition and would be saying something false about
    a title nobody has published. The listing loop is where the word is usually minted and is
    checked there too; this is the surface the operator actually named, so it is checked on its
    own rather than trusted to stay clean because its source was.
    """
    abandoned: list[str] = []
    machinery: tuple[str, ...] = ()
    title = ""
    availability: titles.Availability | None = None
    for _ in range(max(1, attempts)):
        request = overview_mod.render_title_request(
            listing, writer, tuple(abandoned), machinery
        )
        result, refusal = _completion_call(request, calls=calls, spend=spend)
        if result is None:
            print(f"  title: {refusal}", file=sys.stderr)
            break
        title = overview_mod.clean_title(result.text)
        if not title:
            break
        if leaked := schema_words.named_in(title):
            print(
                f"  title: {title!r} names {', '.join(leaked)}, this system's own word for the "
                "machinery; redrawing",
                file=sys.stderr,
            )
            # Not appended to `abandoned`: that list becomes the "already the title of a
            # published book" prohibition, and this title is not published by anybody. Two
            # reasons to drop a title, two prohibitions, neither lying about the other.
            machinery = tuple(sorted(set(machinery) | set(leaked)))
            continue
        if not check:
            break
        lookup = titles.render_check_request(title)
        found, refusal = _completion_call(lookup, calls=calls, spend=spend)
        availability = titles.read(
            title,
            found.parsed if found is not None else None,
            searches=titles.searches_reported(found.raw) if found is not None else 0,
            refusal=refusal,
        )
        if availability.verdict != titles.TAKEN:
            break
        abandoned.append(title)
    if title and (kept := schema_words.named_in(title)):
        # Out of attempts with the word still in it. Kept rather than blanked — a book with no
        # title is worse — and said out loud for `listing_chained`'s reason: the run's operator
        # is the one who can act on it, and a silent fallback is how a gate stops being one.
        print(
            f"litharness: kept the title {title!r} after {attempts} draw(s); it names "
            f"{', '.join(kept)}, this system's own word for the machinery",
            file=sys.stderr,
        )
    return title, availability, tuple(abandoned)


def cmd_listing(args: argparse.Namespace) -> int:
    """The listing loop: a writer, a readership, a listing, a title, and then a book.

    **This closes the earlier script-only listing workflow.** As of 2026-08-25, measured listing
    rounds were still driven by scratch scripts, so the artifact being improved could not be
    produced by the package. The command now owns the surviving sequence in one place:

    1. one writer from `writers.CAST` drafts a listing under a brief that may be empty;
    2. the experimental appetite pool records what it hopes the book turns out to be;
    3. the writer titles the original listing, and a lookup says whether that title is already
       somebody's;
    4. the measurement pool says whether it would open chapter one.

    **Nobody is in both pools and nothing here picks a winner.** There is one listing. Appetite
    answers are retained as experimental evidence and never sent back to a writer; the screen is
    a reading of the listing and not a gate on it, which is why a low start rate prints and does
    not refuse. A later listing intervention mechanism must earn qualification independently.

    **`--scenes` is what closes the hand-move this loop had at the end.** The title reached a
    person, who retyped it into `new`. A generated title that a human has to carry is a human
    in the production loop (§126), so the loop creates the book itself — same title, same
    listing as the premise, and `new`'s own decision row and events, because it calls it.
    """
    stamp = _stamp(_now())

    # **The scene count is checked before the first call, not after the last one.** §19.1: a
    # refusal reached before the work costs time, never the unit — and `arc_template` refuses a
    # book of fewer scenes than it has named beats. Left to `cmd_new` at the end, `--scenes 4`
    # would raise after a listing, four appetite reads, a title, a lookup and four
    # browsing reads had all been paid for.
    if args.scenes:
        try:
            shape = SerialShape(args.chapter_scenes, args.arc_chapters)
            _creation_template(args.scenes, shape)
        except (TemplateMismatch, ValueError) as error:
            print(f"litharness: {error}", file=sys.stderr)
            return EXIT_FAULT

    brief = _read_text(args.brief_file) if args.brief_file else (args.brief or "")
    concept = _concept_from(getattr(args, "concept", None))
    store = _store(args)
    try:
        # **Resolved inside the store's lifetime, because a writer can now be a record.** The
        # refusal still lands before the first paid call, which is the property §19.1 asks for;
        # what moved is only that the roster is reachable when the name is looked up.
        writer, reason = _installed_writer(args, getattr(args, "writer", "") or "", store)
        if reason:
            print(reason, file=sys.stderr)
            return EXIT_FAULT

        registry = build_default_registry()
        run = _StageSpend()
        spend = _StageSpend()
        calls = _ProviderCalls(
            registry=registry,
            store=store,
            args=args,
            stamp=stamp,
            run=run,
        )

        # Draw, then check the one shape property the fifth read named and the market bounds.
        # Deterministic throughout: a counter decides, never a model, and the comparison is
        # against a frozen scalar rather than against another candidate.
        #
        # **§178 adds the second reason to redraw, and this is where the leak is minted.**
        # Serial Pilot 16's listing coined *"It called itself the Ladder"* under an empty brief,
        # and `ladder` is this repository's word for §113's chain. Everything downstream then
        # carried it faithfully — the title is drawn from this listing, and the Architect is
        # told the world has to keep what it promised — so catching it at the world alone would
        # have left a book whose blurb promises a Ladder the world is forbidden to name. The
        # check belongs at the mint, and it is the same loop: a second frozen predicate over
        # the returned string, no model consulted, no extra call unless one fires.
        # **The second shape rail, and its number is the shelf's** (read 17, §3.1): no
        # sentence longer than the longest in the blurbs the operator placed. With no shelf
        # there is no ceiling and the loop is what it was.
        shelf = _selected_shelf(args)
        length_ceiling = (
            overview_mod.sentence_ceiling(
                [exemplar.blurb for exemplar in shelf.exemplars if exemplar.blurb]
            )
            if shelf is not None
            else None
        )
        drawn: list[str] = []
        for _attempt in range(LISTING_DRAW_ATTEMPTS):
            drafted, refusal = _completion_call(
                overview_mod.render_overview_request(
                    brief,
                    writer,
                    person=getattr(args, "person", None),
                    blurbs=exemplars_mod.render_blurbs(shelf) if shelf is not None else None,
                    concept=concept.render_for_listing() if concept is not None else None,
                ),
                calls=calls,
                spend=spend,
            )
            if drafted is None:
                print(f"litharness: {refusal}", file=sys.stderr)
                return EXIT_FAULT
            drawn.append(drafted.text.strip())
            machinery = schema_words.named_in(drawn[-1])
            chained = overview_mod.chains_too_hard(
                drawn[-1], ceiling=LISTING_COORDINATOR_CEILING
            )
            too_long = overview_mod.runs_too_long(drawn[-1], ceiling=length_ceiling)
            if not chained and not machinery and not too_long:
                break
            if machinery:
                print(
                    f"  redrawing: the listing names {', '.join(machinery)}, which is this "
                    "system's own word for the machinery and not this book's",
                    file=sys.stderr,
                )
            elif chained:
                print(
                    f"  redrawing: {overview_mod.coordinator_density(drawn[-1]):.2f} "
                    f"coordinators/100w over the {LISTING_COORDINATOR_CEILING} ceiling",
                    file=sys.stderr,
                )
            else:
                print(
                    f"  redrawing: a {overview_mod.longest_sentence(drawn[-1])}-word sentence, "
                    f"over the shelf's {length_ceiling}",
                    file=sys.stderr,
                )
        # Keep a draw that named none of our words if the loop got one, and otherwise keep what
        # the loop already kept. Two frozen predicates in a fixed order is still a total order
        # over counters rather than a preference among candidates (§61(5) is about a MODEL
        # ranking; nothing here reads the prose), and the fallback is `listing_chained`'s
        # existing shape: run out of attempts, keep the best draw, and say so on the way past.
        clean = [
            draw
            for draw in drawn
            if not schema_words.named_in(draw)
            and not overview_mod.runs_too_long(draw, ceiling=length_ceiling)
        ]
        listing = overview_mod.keep_least_chained(clean or drawn)
        listing_density = overview_mod.coordinator_density(listing)
        listing_redraws = len(drawn) - 1
        listing_chained = listing_density > LISTING_COORDINATOR_CEILING
        if listing_chained:
            print(
                f"litharness: kept a listing at {listing_density:.2f} coordinators/100w after "
                f"{len(drawn)} draw(s); the gate on the decision row records it",
                file=sys.stderr,
            )
        if overview_mod.runs_too_long(listing, ceiling=length_ceiling):
            print(
                f"litharness: kept a listing with a {overview_mod.longest_sentence(listing)}-word "
                f"sentence over the shelf's {length_ceiling} after {len(drawn)} draw(s); the gate "
                "on the decision row records it",
                file=sys.stderr,
            )
        if kept_machinery := schema_words.named_in(listing):
            # Said out loud rather than refused, because the loop has spent its attempts and a
            # book with no listing is worse than a listing carrying our word. What it buys is
            # that the operator reading this run knows to expect the word downstream.
            print(
                f"litharness: kept a listing naming {', '.join(kept_machinery)} after "
                f"{len(drawn)} draw(s); expect it in the title and the world",
                file=sys.stderr,
            )

        # The steering lane. A reader who does not answer is skipped rather than counted as
        # wanting nothing: `Anticipation.of` reads only what came back.
        wishes: dict[str, Any] = {}
        for reader in readers_mod.pool(readers_mod.STEERING):
            request = readers_mod.render_appetite_request(reader, listing)
            result, refusal = _completion_call(request, calls=calls, spend=spend)
            if result is not None and isinstance(result.parsed, Mapping):
                wishes[reader.reader_id] = result.parsed
            elif refusal:
                print(f"  {reader.reader_id}: {refusal}", file=sys.stderr)
        wanted = readers_mod.Anticipation.of(wishes)
        first = listing

        title, availability, abandoned = _listing_title(
            listing,
            writer=writer,
            attempts=args.title_attempts,
            check=not args.no_title_check,
            calls=calls,
            spend=spend,
        )

        # The measurement lane, over the artifact a reader actually meets: the title above the
        # blurb. `--no-title-to-readers` is the control arm and renders what every round before
        # a title existed rendered.
        shown = "" if args.no_title_to_readers else title
        ours = "\n\n".join((shown, listing)) if shown else listing
        pool_of_rivals = _rivals(args)
        choices: dict[str, Any] = {}
        picks: list[dict[str, Any]] = []
        for reader in readers_mod.pool(readers_mod.MEASUREMENT):
            if pool_of_rivals:
                # **The pairing with an external label on it.** A different competitor per
                # reader, so one screen measures this listing against several published books
                # rather than against one; and a swapped, unlabelled order, because a pairwise
                # choice with neither measures position (§89's 4,676x).
                key = f"{title}|{reader.reader_id}"
                rival = rivals_mod.draw(pool_of_rivals, key)
                ours_leads = rivals_mod.ours_first(key)
                request = readers_mod.render_pick_request(reader, ours, rival.render(), ours_leads)
            else:
                request = readers_mod.render_start_request(reader, listing, shown)
            result, refusal = _completion_call(request, calls=calls, spend=spend)
            if result is None or not isinstance(result.parsed, Mapping):
                if refusal:
                    print(f"  {reader.reader_id}: {refusal}", file=sys.stderr)
                continue
            if not pool_of_rivals:
                choices[reader.reader_id] = result.parsed
                continue
            chose = str(result.parsed.get("next") or "")
            picks.append(
                {
                    "reader": reader.reader_id,
                    "chose": readers_mod.side_of(chose, ours_leads),
                    "rival": rival.to_jsonable(),
                    "ours_first": ours_leads,
                    "because": str(result.parsed.get("because") or "").strip(),
                }
            )
        browsing = readers_mod.Browsing.of(choices)
        paired = readers_mod.Pairing.of(picks)

        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id=overview_mod.OVERVIEW_PROFILE,
            passed=not listing_chained,
            blocking=False,
            detail=(
                f"{len(listing.split())} words; "
                f"{listing_density:.2f} coordinators/100w vs the "
                f"{LISTING_COORDINATOR_CEILING} ceiling"
                + f"; longest sentence {overview_mod.longest_sentence(listing)} words"
                + (f" vs the shelf's {length_ceiling}" if length_ceiling is not None else "")
                + (f" after {listing_redraws} redraw(s)" if listing_redraws else "")
                + "; "
                + (
                    f"{paired.ours} of {paired.answered} chose it over a published book"
                    if paired.answered
                    else f"{browsing.started} of {browsing.answered} would start it"
                )
                + f"; title {title!r} "
                + f"{availability.verdict if availability else 'unchecked'}"
            ),
        )
        store.record_decision(
            PolicyDecision(
                decision_id=decision_id_for(f"listing:{stamp}:{title}", 0, (gate,)),
                outcome=Outcome.ACCEPT,
                gates=(gate,),
                profile=overview_mod.OVERVIEW_PROFILE,
                provider=spend.provider,
                model=spend.model,
                invocations=spend.invocations,
                total_tokens=spend.total_tokens,
                cost_usd=spend.cost_usd,
                reason=(
                    "one writer wrote and titled one listing; experimental appetite answers "
                    "were recorded but did not rewrite it, and measurement readers said whether "
                    "they would start. Nothing here ranked or steered"
                ),
            ),
            decided_at=stamp,
        )
    finally:
        store.close()

    bundle = {
        "brief": brief.strip(),
        "writer": writer.name if writer else None,
        "draft": first,
        "listing": listing,
        "title": title,
        "titles_abandoned": list(abandoned),
        "availability": availability.to_jsonable() if availability else None,
        "appetite": wanted.to_jsonable(),
        "appetite_status": "experimental_observation_only",
        "browsing": browsing.to_jsonable(),
        "paired": paired.to_jsonable() if paired.answered else None,
        "title_shown_to_readers": bool(shown),
    }
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "listing.txt").write_text(listing + "\n", encoding="utf-8")
        (args.out / "title.txt").write_text(title + "\n", encoding="utf-8")
        (args.out / "listing.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    # **`--json` changes what is printed and never what is done.** A reporting flag that also
    # skipped creating the book would make the machine-readable path a different command from
    # the readable one, which is the shape of defect §125 recorded: an artifact written by a
    # branch nobody read back.
    if args.json:
        _say(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        _say(title or "(no title)")
        print()
        _say(listing)
        print()
        print(f"  {len(listing.split())} words, writer {writer.name if writer else '(none)'}")
        if availability is not None:
            _say(f"  {availability.render()}")
        for name in abandoned:
            print(f"  abandoned {name!r}: already somebody's")
        if paired.answered:
            print(
                f"  against published books: ours {paired.ours}/{paired.answered}"
                f"  theirs {paired.theirs}  neither {paired.neither}"
                f"  (ours first in {paired.ours_first_share:.0%} of pairs)"
            )
            for reader_id, side, rival_title, _first, because in paired.said:
                _say(f"    {reader_id}: {side} over {rival_title!r} - {because}")
        else:
            print(
                f"  would start it {browsing.started}/{browsing.answered}"
                f"  passed {browsing.passed}  saved {browsing.saved}"
            )
            for reader_id, choice, because in browsing.said:
                _say(f"    {reader_id}: {choice} - {because}")
        if args.out:
            print(f"  {args.out}/listing.txt, title.txt, listing.json")

    if args.scenes:
        created = argparse.Namespace(**vars(args))
        created.title = title or "Untitled"
        created.premise = listing
        # No seed state, deliberately — not an omission (§158). A starting sheet restates
        # world facts, and at listing time there is no world to restate: the Architect has
        # not run. A `--state` here would be a sheet authored blind, which is the licence
        # pilot 12 §3 refused. The sanctioned path for a listing-created book is `world
        # declare <subject> status_snapshot --value '{...}'` then `world accept`, once the
        # facts it restates are canon; `cmd_new` prints the floor's advisory pointing there.
        created.state = None
        created.promises = None
        return cmd_new(created)
    return EXIT_OK


def cmd_concept(args: argparse.Namespace) -> int:
    """The concept stage: one writer invents the book before its listing (stage-0 §197).

    One call, one concept, no readers and no title: the artifact is cheap and the operator can
    read it before the listing, the seed and the chapters are paid for. `--out` writes it as
    the settled file `listing --concept` and `new --concept` read, byte for byte, which is what
    makes a redraw under one concept a redraw. Nothing here ranks: a second draw is a second
    book.
    """
    stamp = _stamp(_now())
    brief = _read_text(args.brief_file) if args.brief_file else (args.brief or "")
    store = _store(args)
    try:
        writer, reason = _installed_writer(args, getattr(args, "writer", "") or "", store)
        if reason:
            print(reason, file=sys.stderr)
            return EXIT_FAULT
        registry = build_default_registry()
        run = _StageSpend()
        spend = _StageSpend()
        calls = _ProviderCalls(registry=registry, store=store, args=args, stamp=stamp, run=run)
        shelf = _selected_shelf(args)
        request = concept_mod.render_concept_request(
            brief,
            writer,
            scenes=args.scenes,
            person=getattr(args, "person", None),
            blurbs=exemplars_mod.render_blurbs(shelf) if shelf is not None else None,
        )
        result, refusal = _completion_call(request, calls=calls, spend=spend)
        if result is None or not isinstance(result.parsed, Mapping):
            print(f"litharness: {refusal or 'the concept came back unparsed'}", file=sys.stderr)
            return EXIT_FAULT
        try:
            concept = concept_mod.Concept.from_payload(result.parsed)
        except concept_mod.MalformedConcept as error:
            print(f"litharness: the concept is unusable: {error}", file=sys.stderr)
            return EXIT_FAULT
        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id=concept_mod.CONCEPT_PROFILE,
            passed=True,
            blocking=False,
            detail=(
                f"{len(concept.debts)} debt(s); the turn {concept.turn.when}; "
                + ("two systems" if concept.second_system is not None else "one system")
            ),
        )
        store.record_decision(
            PolicyDecision(
                decision_id=decision_id_for(f"concept:{stamp}", 0, (gate,)),
                outcome=Outcome.ACCEPT,
                gates=(gate,),
                profile=concept_mod.CONCEPT_PROFILE,
                provider=spend.provider,
                model=spend.model,
                invocations=spend.invocations,
                total_tokens=spend.total_tokens,
                cost_usd=spend.cost_usd,
                reason="one writer invented one book; nothing ranked or chose among candidates",
            ),
            decided_at=stamp,
        )
    finally:
        store.close()

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "concept.json").write_text(concept.to_text() + "\n", encoding="utf-8")
        (args.out / "concept.txt").write_text(concept.render() + "\n", encoding="utf-8")
    if args.json:
        _say(concept.to_text())
    else:
        _say(concept.render())
        print(f"  writer {writer.name if writer else '(none)'}")
        if args.out:
            print(f"  {args.out}/concept.json, concept.txt")
    return EXIT_OK


def cmd_cover(args: argparse.Namespace) -> int:
    """Generate several cover-art routes and finish each as an exact publication asset.

    The database is the normal handoff; its title, premise and revision locate the cover in the
    same derived shelf as the reading copy. The listing bundle remains the pre-database route.
    Explicit values override either source only when deliberately set.

    Cover *art* is sampled; publication text is not. Codex is asked for text-free 2:3 art and
    `application.covers` draws the title and author itself, identically for every candidate.
    This is also why a run makes a set instead of asking an image model for a contact sheet:
    every variant is an independent route and every final cover has the same measurable shape.
    """
    bundle: Mapping[str, Any] = {}
    if args.bundle:
        loaded = json.loads(args.bundle.read_text(encoding="utf-8"))
        if not isinstance(loaded, Mapping):
            raise ValueError(f"cover bundle must be a JSON object: {args.bundle}")
        bundle = loaded

    title = (args.title or str(bundle.get("title") or "")).strip()
    if args.description_file:
        description = _read_text(args.description_file)
    else:
        description = args.description or str(bundle.get("listing") or bundle.get("brief") or "")
    book_id = ""
    branch_id = ""
    revision_id = ""
    if args.book or args.branch or not title or not description.strip():
        store = _store(args)
        try:
            book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
            document = export_module.collect(
                store,
                book_id=book_id,
                branch_id=branch_id,
                generated_at=_stamp(_now()),
            )
        finally:
            store.close()
        title = title or document.title
        description = description if description.strip() else document.premise or ""
        revision_id = document.revision_id
    spec = covers.CoverSpec(
        title=title,
        description=description,
        author=args.author,
        art_direction=args.art_direction,
        book_id=book_id,
        branch_id=branch_id,
        revision_id=revision_id,
        volume=args.volume,
    )
    supplied = tuple(args.art or ())
    count = (
        len(supplied)
        if supplied
        else (args.variants if args.variants is not None else covers.DEFAULT_VARIANTS)
    )
    library_root = _library_root(args)
    # The same shelf the library publisher resolves, suffix and all, so a colliding book's
    # covers land beside its own reading copy rather than inside the first book's shelf. A
    # bundle-only run consulted no store, so it has no identity to resolve a collision with
    # and the bare title names the shelf as it always has.
    shelf = library_root / (
        library_module.shelf_slug(library_root, spec.title, spec.book_id)
        if spec.book_id
        else library_module.slugify(spec.title, "cover")
    )
    default_output = (
        shelf / "volumes" / f"Volume{spec.volume}" / "covers"
        if spec.volume is not None
        else shelf / "covers"
    )
    output = args.out or default_output
    result = covers.create_cover_set(
        output,
        spec,
        variants=count,
        supplied_art=supplied,
        references=tuple(args.reference or ()),
        font_path=args.font,
        timeout=args.timeout,
        force=args.force,
        generated_at=_stamp(_now()),
        runner=subprocess_runner,
        codex_executable=_codex_executable(),
    )
    for cover_path in result.covers:
        print(cover_path)
    print(f"manifest: {result.manifest}")
    return EXIT_OK


def _codex_executable() -> str:
    """Resolve the installed Codex launcher to something `CreateProcess` can execute.

    npm puts an extensionless POSIX shim before `codex.cmd` on Windows. PowerShell skips that
    shim, but Python's `subprocess` finds it and `CreateProcess` returns WinError 5. Resolve the
    Windows launcher explicitly; elsewhere the ordinary executable is the right one.
    """
    names = ("codex.cmd", "codex.exe") if os.name == "nt" else ("codex",)
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return names[0]


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
        print("  run `architect seed`, inspect `world check`, then `world accept`")
        return EXIT_OK

    if args.csv:
        rows = characters_mod.rows(people)
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
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
    """A `--value` as the type it plainly is: 34 is a number, `{"level": 1}` is a sheet,
    everything else is prose.

    **Written because a 317-record world had every one of its reveal scenes stored as
    `"34"`.** argparse hands over text, the store JSON-encodes what it is given, and
    `worlds.reveal_scenes` keeps only genuine ints — so fifteen scheduled disclosures were
    invisible and nothing complained, because a reveal that does not parse looks exactly
    like a reveal nobody scheduled.

    **A JSON object is kept for the number's own reason** (§158). Everything that reads a
    `status_snapshot` reads fields out of a mapping, and while this function round-tripped
    objects back to their raw string, the one seeding path that can reach a listing-created
    book — `world declare` then `world accept` — could not produce a sheet the status-line
    machinery renders from: Serial Pilot 14's book cleared the genre floor and was never
    asked for a status line (§2.2, §7). An object is as plainly typed as 34 and the original
    hazard does not extend to it: `json.loads` on prose raises and the text is kept, and no
    sentence parses as `{...}` by accident. Arrays still round-trip as prose because nothing
    reads a list-valued record; widen again when something does.

    A value that really is meant to be the string `34` — or the string `{"a": 1}` — is
    written `--value '\"34\"'`, which is the only case coercion changes and the rarer one
    by far.
    """
    if text is None:
        return None
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    return parsed if isinstance(parsed, int | float | bool | dict) else text


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

    **What it can do is the allowance and not a promise.** `world_agent.ALLOWED_TOOLS`
    enumerates every world command except `accept`: this agent runs the world suite and has no
    other tool, and the matcher refuses it the one command that installs (§146.9 measured the
    refusal; the earlier `Bash(litharness world:*)` glob did not refuse it). Every record it
    writes is PROPOSED, so it proposes a world and cannot install one — `world accept` is the
    separate act that carries a decision row.

    The database reaches the child through `LITHARNESS_DATABASE`, which is why that variable
    exists: a `--database` flag between the binary and the subcommand would force the allowance
    to widen to every command this CLI has.
    """
    database = str(Path(args.database).resolve())
    os.environ[DATABASE_ENV] = database

    store = _store(args)
    stamp = _stamp(_now())
    try:
        writer, reason = _installed_writer(args, getattr(args, "writer", "") or "", store)
        if reason:
            print(reason, file=sys.stderr)
            return EXIT_FAULT

        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        before = len(store.state_records(book_id, branch_id))
        if args.job == "seed":
            # **The book's own premise is the default, and that is a correctness fix rather
            # than a convenience.** This prompt opens "The listing this book was sold on", and
            # a `--overview` file is a second copy of a listing that already exists in the
            # store — so the one way to seed a world against a listing the readers never saw
            # was to pass the wrong file. `listing --scenes` writes the listing in as the
            # premise; this reads it back.
            source = "--overview"
            if args.overview:
                overview = _read_text(args.overview)
            else:
                source = "the book's premise"
                overview = premise_of(store.plan_items(book_id, branch_id)) or ""
            if not overview.strip():
                print(
                    f"litharness: an empty listing is nothing to build on ({source})",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            concept = concept_mod.concept_of(store.plan_items(book_id, branch_id))
            print(f"  seeding under {source}" + (" and the book's concept" if concept else ""))
            request = world_agent.render_seed_request(overview, writer, concept=concept)
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
        calls = _ProviderCalls(
            registry=registry,
            store=store,
            args=args,
            stamp=stamp,
            run=_StageSpend(),
        )
        result, refusal = _completion_call(request, calls=calls, spend=spend)
        if result is None:
            print(f"litharness: {refusal}", file=sys.stderr)
            return EXIT_FAULT

        after = store.state_records(book_id, branch_id)
        proposed = sum(1 for record in after if record.authority is lc.StateAuthority.PROPOSED)
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

    _say(result.text.strip())
    print()
    print(f"  {len(after) - before} record(s) added, {proposed} awaiting `world accept`")
    for complaint in complaints:
        print(f"  ! {complaint}")
    return EXIT_OK


#: A descriptor for `prompts` to render the draw with, and for nothing else. **Numbers with no
#: provenance, deliberately**: a real one is distilled on the measurement side and reaches this
#: process through `--descriptor`, so a specimen with a corpus behind it would put a value here
#: that RS1 says may not be in the package at all.
_SPECIMEN_DESCRIPTOR = voice_domain.StyleDescriptor(
    sentence_words_mean=14.0,
    sentence_words_sd=8.0,
    sentence_words_p10=4.0,
    sentence_words_p50=12.0,
    sentence_words_p90=27.0,
    paragraph_sentences_mean=3.0,
    connective_density=7.0,
    person=voice_domain.Person.THIRD,
    tense=voice_domain.Tense.PAST,
)


def _prompt_pressure(
    request: CompletionRequest,
    *,
    context: Mapping[str, Any] | None = None,
    omitted: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Deterministic signs that material is crowding or repeating inside one request."""
    material_lines = [
        line.strip()[1:].strip()
        for line in request.prompt.splitlines()
        if line.strip().startswith("-")
    ]
    normalised = [
        " ".join(
            "".join(character if character.isalnum() else " " for character in line.lower()).split()
        )
        for line in material_lines
    ]
    repeated = [
        {"text": line, "occurrences": count}
        for line, count in Counter(normalised).items()
        if line and count > 1
    ]
    sections = dict(context.get("sections") or {}) if context else {}
    section_total = sum(
        count
        for count in sections.values()
        if isinstance(count, int) and not isinstance(count, bool)
    )
    dominant = [
        {"section": name, "items": count, "share": count / section_total}
        for name, count in sections.items()
        if section_total and isinstance(count, int) and count >= 8 and count / section_total >= 0.5
    ]
    return {
        "context_items": context.get("items") if context else None,
        "context_tokens": context.get("tokens") if context else None,
        "context_budget": context.get("budget") if context else None,
        "section_items": sections,
        "dominant_sections": dominant,
        "omitted_items": len(omitted),
        "repeated_material_lines": repeated,
    }


def _prompt_row(
    role: str,
    request: CompletionRequest,
    *,
    source: str,
    context: Mapping[str, Any] | None = None,
    omitted: Sequence[Mapping[str, Any]] = (),
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    counted = house.demands(request.system or "")
    return {
        "role": role,
        "source": source,
        **({"provenance": dict(provenance)} if provenance else {}),
        "prompt_chars": len(request.prompt),
        "system_chars": len(request.system or ""),
        "schema_chars": len(request.schema_instruction),
        "tool_chars": len(",".join(request.allowed_tools)),
        "input_chars": request.input_chars,
        "demands": list(counted),
        "allowed_tools": list(request.allowed_tools),
        "pressure": _prompt_pressure(request, context=context, omitted=omitted),
        "system": request.system or "",
        "prompt": request.prompt,
        "schema_instruction": request.schema_instruction,
    }


def _print_prompt_row(row: Mapping[str, Any]) -> None:
    print(f"SOURCE: {row['source']}")
    provenance = row.get("provenance")
    if provenance:
        print(f"PROVENANCE: {json.dumps(provenance, sort_keys=True, ensure_ascii=False)}")
    print("\nSYSTEM (ROLE):")
    print(row["system"] or "[none]")
    print("\nPROMPT (MATERIAL AND TASK):")
    print(row["prompt"] or "[none]")
    if row["schema_instruction"]:
        print("\nSYSTEM (TRANSPORT-ADDED SCHEMA):")
        print(row["schema_instruction"])
    print("\nALLOWED TOOLS:")
    print(", ".join(row["allowed_tools"]) or "[none]")
    pressure = row["pressure"]
    print("\nCONTEXT PRESSURE:")
    if pressure["context_items"] is None:
        print("  not recorded (this is a representative request)")
    else:
        print(
            f"  {pressure['context_items']} item(s), {pressure['context_tokens']}/"
            f"{pressure['context_budget']} token(s), {pressure['omitted_items']} omitted"
        )
        sections = pressure["section_items"]
        if sections:
            print("  " + "  ".join(f"{name} {count}" for name, count in sections.items()))
    if pressure["repeated_material_lines"]:
        print(
            "  repeated material: "
            + "; ".join(
                f"{item['occurrences']}x {item['text']}"
                for item in pressure["repeated_material_lines"]
            )
        )
    if pressure["dominant_sections"]:
        print(
            "  dominant section: "
            + "; ".join(
                f"{item['section']} {item['items']} ({item['share']:.0%})"
                for item in pressure["dominant_sections"]
            )
        )
    print()
    print(
        f"  {len(row['demands'])} explicit system demand(s), {row['input_chars']} "
        "effective input characters"
    )


def _stored_scene_prompt(args: argparse.Namespace) -> int:
    if args.role not in (None, "scene"):
        print("litharness: --scene can inspect only the scene role", file=sys.stderr)
        return EXIT_FAULT
    store = _store(args)
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        if head is None:
            print(f"litharness: no head for {book_id}/{branch_id}", file=sys.stderr)
            return EXIT_ATTENTION
        node = _scene_node(head, args.scene)
        if node is None:
            print(f"litharness: no scene {args.scene} in this book", file=sys.stderr)
            return EXIT_ATTENTION
        dossier = _scene_dossier(store, book_id, branch_id, node, head)
    finally:
        store.close()
    frozen = dossier["prompt"]
    if not isinstance(frozen, Mapping):
        print(
            f"litharness: no stored prompt explains {node.logical_id}; try `why --scene "
            f"{node.logical_id}`",
            file=sys.stderr,
        )
        return EXIT_ATTENTION
    context = dossier["context"] if isinstance(dossier["context"], Mapping) else None
    omitted = dossier["context_omitted"] if isinstance(dossier["context_omitted"], list) else []
    job = dossier["job"] if isinstance(dossier["job"], Mapping) else {}
    row = _prompt_row(
        "scene",
        CompletionRequest(prompt=frozen["prompt"], system=frozen.get("system")),
        source="stored_request",
        context=context,
        omitted=omitted,
        provenance={
            "book_id": book_id,
            "branch_id": branch_id,
            "logical_id": node.logical_id,
            "job_id": job.get("job_id"),
            "input_digest": job.get("input_digest"),
        },
    )
    if args.json:
        print(json.dumps(row, ensure_ascii=False, indent=2))
    else:
        _print_prompt_row(row)
    return EXIT_OK


def cmd_prompts(args: argparse.Namespace) -> int:
    """Print representative requests, or one exact frozen scene request with ``--scene``.

    **The assembled prompt existed nowhere until this.** Every role built its own by
    concatenation at call time, so the only way to know what a writer was told was to run one
    and read the transcript — and the consequence was a listing prompt that had grown to sixteen
    demands for a hundred-word artifact without anybody deciding it should.

    `tests/test_prompt_budget.py` holds the ceilings and fails when one is passed. This is the
    same numbers to look at before you add a clause rather than after.
    """
    if args.scene:
        return _stored_scene_prompt(args)

    # **The store is opened only when the name needs it, and that is not an optimisation.**
    # `SqliteStore.open` creates and migrates the file, so resolving unconditionally would make
    # an inspection command that has never touched a database leave one behind in whatever
    # directory it was run from.
    wanted = (getattr(args, "writer", "") or "").strip() or "ferreira"
    store = (
        _store(args)
        if wanted not in writers_domain.CAST and args.database.exists()
        else None
    )
    try:
        writer, reason = _installed_writer(args, wanted, store)
    finally:
        if store is not None:
            store.close()
    if reason:
        print(reason, file=sys.stderr)
        return EXIT_FAULT

    premise = "A debtor discovers the road beneath the city is collecting people, not coins."
    scene_text = (
        "Rook counted the toll twice. The gate opened only after it took the memory of his "
        "brother's face.\n\nOn the far side, somebody who knew his name was waiting."
    )
    beat = Beat("scene-1", 1, 24, None, "setup", "arc.24", "s000001")

    def specimen_item(
        item_id: str,
        kind: lc.ContextItemKind,
        source_logical_id: str,
        source_kind: lc.ResourceKind,
        text: str,
        authority: lc.StateAuthority = lc.StateAuthority.DERIVED,
    ) -> PackedItem:
        return PackedItem(
            item_id=item_id,
            kind=kind,
            source_logical_id=source_logical_id,
            source_kind=source_kind,
            text=text,
            tokens=count_tokens(text),
            authority=authority,
        )

    packet = ContextPacket(
        query_id="prompt-inspector",
        target_logical_id="scene-1",
        book_id="specimen-book",
        branch_id="main",
        base_revision_id="specimen-revision",
        sections={
            PREMISE: (
                specimen_item(
                    "plan-premise",
                    lc.ContextItemKind.PLAN,
                    "plan-premise",
                    lc.ResourceKind.PLAN,
                    premise,
                ),
            ),
            CONSTRAINTS: (
                specimen_item(
                    "constraint-cost",
                    lc.ContextItemKind.AUTHOR_RULE,
                    "constraint-cost",
                    lc.ResourceKind.PLAN,
                    "Every crossing takes a specific memory; no cost may be reversed.",
                    lc.StateAuthority.AUTHOR_LOCKED,
                ),
            ),
            THREADS: (
                specimen_item(
                    "promise-waiting",
                    lc.ContextItemKind.THREAD,
                    "promise-waiting",
                    lc.ResourceKind.THREAD,
                    "owes: identify who knew Rook would cross and why they were waiting",
                ),
            ),
            CAST: (
                specimen_item(
                    "cast:rook",
                    lc.ContextItemKind.FACT,
                    "rook",
                    lc.ResourceKind.ENTITY,
                    "rook (the protagonist)\n  is: an indebted courier\n  wants: to return home",
                    lc.StateAuthority.ACCEPTED_CANON,
                ),
            ),
            FACTS: (
                specimen_item(
                    "rook-location",
                    lc.ContextItemKind.FACT,
                    "rook-location",
                    lc.ResourceKind.ASSERTION,
                    "rook location below_city",
                    lc.StateAuthority.ACCEPTED_CANON,
                ),
            ),
            SUMMARIES: (
                specimen_item(
                    "summary:scene-0",
                    lc.ContextItemKind.SUMMARY,
                    "scene-0",
                    lc.ResourceKind.MANUSCRIPT_SCENE,
                    "Rook learns that the city toll accepts memories as payment.",
                ),
            ),
            PRIOR_PROSE: (
                specimen_item(
                    "prose:scene-0",
                    lc.ContextItemKind.EXACT_PROSE,
                    "scene-0",
                    lc.ResourceKind.MANUSCRIPT_SCENE,
                    scene_text,
                    lc.StateAuthority.ACCEPTED_CANON,
                ),
            ),
        },
    )
    # The shelf the writer would be shown under `--exemplars` (§196), so what this inspector
    # prints is what a scene call carries; without the flag the request is what it always was.
    shelf = _selected_shelf(args)
    scene_system, scene_prompt = render_scene_prompt(
        beat,
        book_title="The Deep Ledger",
        packet=packet,
        target_words=900,
        scene_plan="Rook pays a cost that changes what returning home would mean.",
        writer=writer,
        shelf=shelf,
    )
    base = PlanRevision(
        "specimen-book",
        "main",
        (
            lc.PlanItem(
                logical_id="plan-premise",
                kind=lc.PlanKind.PREMISE,
                text=premise,
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            ),
        ),
    )
    direction = Directive(
        directive_id="specimen-directive",
        kind=DirectiveKind.ARC_NOTE,
        body="Make the descent cost Rook a relationship he expected to keep.",
        book_id="specimen-book",
        branch_id="main",
    )
    summary_system, summary_prompt = render_summary_prompt(scene_text)
    repair_finding = Finding(
        finding_id="specimen-finding",
        category="continuity",
        severity=Severity.MAJOR,
        message="The toll contradicts the established cost.",
        rule_or_critic_id="continuity.specimen.v0",
        logical_id="scene-1",
    )
    measurement = readers_mod.pool(readers_mod.MEASUREMENT)[0]
    steering = readers_mod.pool(readers_mod.STEERING)[0]
    roles: dict[str, CompletionRequest] = {
        "listing": overview_mod.render_overview_request(
            premise,
            writer,
            blurbs=exemplars_mod.render_blurbs(shelf) if shelf is not None else None,
        ),
        "concept": concept_mod.render_concept_request(
            premise,
            writer,
            scenes=SerialShape().scenes_per_arc,
            blurbs=exemplars_mod.render_blurbs(shelf) if shelf is not None else None,
        ),
        "title": overview_mod.render_title_request("A debtor takes the road below.", writer),
        "title-lookup": titles.render_check_request("The Deep Ledger", writer),
        "architect-seed": world_agent.render_seed_request("A debtor takes the road below.", writer),
        "architect-grow": world_agent.render_grow_request(
            scene_text, logical_id="scene-1", writer=writer
        ),
        # Three rows rather than one, because the three dossier forms are three prompts and a
        # role assembled only inside its own call site is one nobody can see the size of.
        "recruit-single-image": recruiter.render_recruit_request(
            "cozy-fantasy", shape="single-image"
        ),
        "recruit-several-with-beat": recruiter.render_recruit_request(
            "cozy-fantasy", shape="several-with-beat"
        ),
        "recruit-several-no-beat": recruiter.render_recruit_request(
            "cozy-fantasy", shape="several-no-beat"
        ),
        # The two revoicing calls. Both floorless on purpose, which is why they read small
        # beside the recruiter: `application/revoice.py` carries the argument.
        #
        # **The cast control is used where `--writer` is unset rather than the row being
        # omitted, and that is not a convenience.** Every other role here has an anonymous arm
        # because every other role can run without a writer; a draw cannot. A passage drawn by
        # nobody is nobody's voice, and there is nothing to rewrite a dossier *into*. So
        # `revoice` has no no-writer control by construction, and this row shows what an
        # operator would actually send.
        "revoice-draw": revoice.render_exemplar_request(
            writer or writers_domain.CAST["ferreira"], descriptor=_SPECIMEN_DESCRIPTOR
        ),
        "revoice-rewrite": revoice.render_rewrite_request(
            dossier=(writer or writers_domain.CAST["ferreira"]).dossier,
            exemplar="A specimen passage, kept short.",
        ),
        "outline": render_outline_request(premise, (beat,), base=base, serial_arc_index=1),
        "narrative-planner": render_narrative_request(base, direction, ("scene-1",)),
        "scene": CompletionRequest(prompt=scene_prompt, system=scene_system),
        "summarizer": CompletionRequest(
            prompt=summary_prompt,
            system=summary_system,
            schema=SUMMARY_SCHEMA,
            profile="scene-summary.v0",
        ),
        "director": render_director_request(
            directors_domain.BUILTIN["delver"],
            premise=premise,
            statements=(("scene-1", "Rook pays the first toll."),),
            summaries=(("scene-1", "Rook crossed and lost a memory."),),
            drafted=1,
            of_total=24,
            open_promises=("Who was waiting across the gate",),
            current_state=("rook location below_city",),
            open_ended=True,
        ),
        "reader-measurement": readers_mod.render_choice_request(
            measurement, scene_text, "Another Serial"
        ),
        "reader-steering": readers_mod.render_anticipation_request(steering, scene_text),
        "repair": render_repair_request(
            repair_finding,
            scene_text,
            0,
            25,
            scene_plan="Rook pays the first toll.",
            facts=("rook debt unpaid",),
        ),
        # The reviser sees a drafted scene and the material behind it, so the inspector shows
        # it the same fixture the repair row uses rather than a second invented one.
        "reviser": render_revision_request(scene_text, material="Rook owes the first toll."),
        "house-floor": CompletionRequest(prompt="", system=house.HOUSE_RULES),
    }

    if args.role:
        if args.role not in roles:
            print(
                f"litharness: no role {args.role!r}; the roles are {', '.join(roles)}",
                file=sys.stderr,
            )
            return EXIT_FAULT
        request = roles[args.role]
        row = _prompt_row(args.role, request, source="representative_specimen")
        if args.json:
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return EXIT_OK
        _print_prompt_row(row)
        return EXIT_OK

    rows = {
        role: {
            "prompt_chars": len(request.prompt),
            "system_chars": len(request.system or ""),
            "schema_chars": len(request.schema_instruction),
            "tool_chars": len(",".join(request.allowed_tools)),
            "input_chars": request.input_chars,
            "demands": len(house.demands(request.system or "")),
        }
        for role, request in roles.items()
    }
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK
    print(
        f"{'role':22s} {'prompt':>7s} {'system':>7s} {'schema':>7s} "
        f"{'tools':>7s} {'total':>7s} {'demands':>8s}"
    )
    for role, row in rows.items():
        print(
            f"{role:22s} {row['prompt_chars']:7d} {row['system_chars']:7d} "
            f"{row['schema_chars']:7d} {row['tool_chars']:7d} {row['input_chars']:7d} "
            f"{row['demands']:8d}"
        )
    print()
    print("  `--role <name>` prints one in full. Ceilings: tests/test_prompt_budget.py")
    return EXIT_OK


def cmd_roster(args: argparse.Namespace) -> int:
    """The roster: read it, offer it a writer, or put one on it.

    **`cmd_world`'s shape, and the divergences are deliberate.** Every read view prints JSON,
    because both an agent and an operator read these, and `application/roster.py` holds the
    views and no logic. There is no `--book` and no `--branch`: a world belongs to a book where
    a roster does not, and the shorter command line is part of what keeps the Recruiter's
    allowance narrow. The whole suite operates on `_roster_store`, so a configured
    `--roster-database` makes the roster the installation's rather than the open database's
    (stage-0 §151).

    **`declare` refuses where `world declare` warns, and the two are not the same case.** A
    world is built one record at a time and is transiently incoherent by nature — a question
    owes an answer, a rung owes a chain — so refusing there taught an agent to work around the
    tool and left a 317-record world with zero questions in it. A dossier arrives whole in one
    command, so no companion record can make a legal one look illegal; and
    `Writer.__post_init__` runs `legal_dossier`, so warning would mean storing raw columns no
    `Writer` can ever be built from, which is a poisoned row the resolution path raises on
    forever rather than leniency. What replaces the warning is `roster check --dossier`: free,
    writes no record, and exits zero whatever it finds. Serial Pilot 7's own conclusion is that
    the fix which removes the reason to probe is a tool fix and not a rule, and that is the fix.

    **`accept` has no `--force`, unlike `world accept`.** A world may contradict itself and an
    operator may want the contradiction on the record; an illegal dossier is not a contradiction
    to be recorded, it is a prose axis about to enter every scene call for a whole book, and R1
    has no override.

    **Every view writes through `_say` rather than `print`**, and that is not tidiness. This
    host's stdout codec is cp1252: `roster vocabulary` names the em dash as the character it
    refuses, which cp1252 mangles into a byte no UTF-8 reader can parse, and a dossier for the
    shelf called *Chinese Cultivation (in English)* can hold characters cp1252 cannot encode at
    all — which kills `roster show` outright, for every writer on the roster, permanently.
    `_say` records what that class of defect already cost once: an `architect seed` run of
    sixteen minutes died printing its own closing report.
    """
    stamp = _stamp(_now())

    if args.view == "vocabulary":
        _say(json.dumps(roster_mod.vocabulary(), ensure_ascii=False, indent=2))
        return EXIT_OK

    if args.view == "check" and (args.dossier or args.dossier_file):
        # **Always EXIT_OK, including when the dossier is illegal, and that is the point.** A
        # rehearsal that exits nonzero is a rehearsal an agent stops running, and an agent that
        # stops rehearsing goes back to learning the interface by writing records. The verdict
        # is in the payload where a machine reads it, not in the exit code where a tool harness
        # reads it as an error.
        text = _read_text(args.dossier_file) if args.dossier_file else (args.dossier or "")
        _say(json.dumps(roster_mod.rehearse(text), ensure_ascii=False, indent=2))
        return EXIT_OK

    store = _roster_store(args)
    try:
        if args.view == "show":
            status = (
                writers_domain.RosterStatus(args.status) if args.status else None
            )
            rows = store.roster_rows(name=args.name, status=status)
            payload = roster_mod.show(
                rows, store.roster_rows(), with_dossier=args.dossier
            )
            _say(json.dumps(payload, ensure_ascii=False, indent=2))
            return EXIT_OK

        if args.view == "check":
            payload = roster_mod.check(store.roster_rows())
            _say(json.dumps(payload, ensure_ascii=False, indent=2))
            return EXIT_OK if payload["ok"] else EXIT_FAULT

        if args.view == "declare":
            if args.dossier and args.dossier_file:
                print(
                    "litharness: give --dossier or --dossier-file, not both",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            dossier = (
                _read_text(args.dossier_file) if args.dossier_file else (args.dossier or "")
            )
            if not dossier.strip():
                print(
                    "litharness: a writer with no dossier is not a writer. Pass --dossier "
                    'with the paragraph in one quoted argument; `litharness roster check '
                    '--dossier "..."` reads it back to you first and costs nothing',
                    file=sys.stderr,
                )
                return EXIT_FAULT

            # **A flag that disagrees with the run it is inside is refused rather than
            # preferred.** This is what makes "one shelf per call" and "do not standardise on
            # one form" mechanical instead of prose: a recruit run stamps both, and a
            # declaration that contradicts the stamp would put a dossier in the wrong cell of a
            # registered arm with nothing on the record saying so.
            for flag, env, label in (
                (args.specialization, RECRUIT_SHELF_ENV, "specialization"),
                (args.shape, RECRUIT_SHAPE_ENV, "shape"),
            ):
                standing = os.environ.get(env, "").strip()
                if flag and standing and flag != standing:
                    print(
                        f"litharness: --{label} {flag!r} disagrees with the run in flight, "
                        f"which is recruiting {standing!r}. This call belongs to that run",
                        file=sys.stderr,
                    )
                    return EXIT_FAULT
            specialization = args.specialization or os.environ.get(
                RECRUIT_SHELF_ENV, ""
            ).strip()
            shape = args.shape or os.environ.get(RECRUIT_SHAPE_ENV, "").strip()
            if not specialization or not shape:
                print(
                    "litharness: a declaration needs --specialization and --shape; "
                    "`litharness roster vocabulary` names both vocabularies",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            # **Checked here and not only on the flag**, because a value taken from the
            # environment has never met `argparse`'s `choices`. The shape is refused in the
            # adapter; the shelf was not, so a mistyped variable landed a row on a shelf that
            # does not exist, `roster check` then reported it forever, and `declare` has no
            # retraction to undo it with. Both vocabularies are refused in one place now.
            if specialization not in roster_mod.SPECIALIZATIONS:
                print(
                    f"litharness: {specialization!r} is not one of the twelve shelves; "
                    f"they are {', '.join(roster_mod.SPECIALIZATIONS)}",
                    file=sys.stderr,
                )
                return EXIT_FAULT

            if reason := roster_mod.reserved_name(args.name):
                print(reason, file=sys.stderr)
                return EXIT_FAULT

            try:
                writer = writers_domain.build(
                    args.name,
                    dossier,
                    interests=tuple(args.interests),
                    note=args.note or "",
                )
                fresh = store.record_proposed_writer(
                    writer,
                    specialization=specialization,
                    shape=shape,
                    proposed_at=stamp,
                )
            except writers_domain.IllegalDossier as error:
                # **Nothing is written on this path**, and the record-free half is the property
                # that matters: a refused dossier leaves no row for a later reader to wonder at.
                print(f"litharness: {error}", file=sys.stderr)
                print(
                    '  try `litharness roster check --dossier "..."` first; it costs nothing '
                    "and writes nothing",
                    file=sys.stderr,
                )
                return EXIT_FAULT

            payload = {
                "writer_id": writer.writer_id,
                "name": writer.name,
                "status": writers_domain.RosterStatus.PROPOSED.value,
                "specialization": specialization,
                "shape": shape,
                "interests": list(writer.interests),
                "dossier_words": len(dossier.split()),
                "new": bool(fresh),
                "says": (
                    f"{writer.name} for {specialization}, {shape}, "
                    f"{len(writer.interests)} interest(s), {len(dossier.split())} words"
                ),
            }
            if args.json:
                _say(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                verb = "declared" if fresh else "already on record"
                print(f"{verb}: {payload['says']}  [proposed]")
                print(f"  {writer.writer_id}  awaiting `roster accept`")
            return EXIT_OK

        # accept
        #
        # **The second lock on the no-model-hires rail, and it is a mechanism rather than a
        # promise.** The first is `recruiter.ALLOWED_TOOLS`, which enumerates four commands and
        # does not name this one. This is the lock that does not depend on how a
        # `Bash(prefix:*)` rule is matched: `cmd_recruit` exports the shelf it is recruiting
        # for, so while a run is in flight nothing in that process tree can admit a writer,
        # however it reached this command.
        if os.environ.get(RECRUIT_SHELF_ENV, "").strip():
            print(
                "litharness: a recruit run is in flight; acceptance is an operator act and is "
                "refused from inside one. Let the run finish and accept it yourself",
                file=sys.stderr,
            )
            return EXIT_FAULT

        proposed = store.roster_rows(status=writers_domain.RosterStatus.PROPOSED)
        # **A writer id is accepted here as well as a name, and that is the way out of a dead
        # end rather than a convenience.** Two proposals may legitimately share a name — an
        # edited dossier is a different writer — and where they do, neither can be named
        # unambiguously. Without an id to point at, an operator holding two `stroud` proposals
        # could accept neither of them and could not clear them either, because `declare` has
        # no retraction.
        wanted = set(args.names)
        rows = [
            row
            for row in proposed
            if not wanted or row["name"] in wanted or row["writer_id"] in wanted
        ]
        missing = sorted(
            wanted
            - {row["name"] for row in proposed}
            - {row["writer_id"] for row in proposed}
        )
        if missing:
            print(
                f"litharness: no proposed writer named {', '.join(missing)}; "
                "`litharness roster show` lists what is declared",
                file=sys.stderr,
            )
            return EXIT_FAULT
        if not rows:
            print("nothing proposed; the roster is unchanged")
            return EXIT_OK

        # **The legality check runs again here, and it is not a formality.** The registered
        # prose-axis vocabulary grows as the reader loop admits axes, so a dossier declared
        # last month passed a smaller vocabulary than the one governing the prompt it is about
        # to ride in. This is also the only place the check can be non-vacuous, which is why
        # `roster_rows` returns raw columns: a reader that built `Writer` objects would raise
        # on an illegal row rather than return it, so it could only ever hand this loop rows
        # that had already passed.
        admitted: list[tuple[str, str]] = []
        refused: list[str] = []
        for row in rows:
            try:
                writers_domain.legal_dossier(row["dossier"])
                writers_domain.refuse_reserved_name(row["name"])
            except writers_domain.IllegalDossier as error:
                refused.append(f"{row['name']}: {error}")
                continue
            admitted.append((row["name"], row["writer_id"]))

        # **A name two of them share is reported here rather than raised in the adapter**, and
        # the rest of the batch still goes through. `roster_accepted_name_idx` guarantees one
        # answer per name and `accept_writers` raises if this is ever wrong, but a raise makes
        # a bare `roster accept` fail entirely, which is the wrong response to a condition the
        # roster deliberately allows: two proposals under one name are what an edited dossier
        # looks like. The operator picks by id, which is why `accept` takes one.
        on_roster = {
            row["name"]: row["writer_id"]
            for row in store.roster_rows(status=writers_domain.RosterStatus.ACCEPTED)
        }
        by_name: dict[str, list[str]] = {}
        for name, writer_id in admitted:
            by_name.setdefault(name, []).append(writer_id)
        contested = {
            name
            for name, ids in by_name.items()
            if len(ids) > 1 or name in on_roster
        }
        for name in sorted(contested):
            ids = by_name[name]
            held = on_roster.get(name)
            refused.append(
                f"{name}: {'already on the roster as ' + held + '; ' if held else ''}"
                f"{len(ids)} proposal(s) here answer to this name ({', '.join(ids)}), and "
                f"`--writer {name}` has to have one answer. Name the one you want by its id"
            )
        admitted = [pair for pair in admitted if pair[0] not in contested]

        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="roster.accept.v0",
            passed=not refused,
            blocking=False,
            detail=(
                f"{len(admitted)} writer(s) accepted onto the roster: "
                + ", ".join(f"{name} {wid}" for name, wid in admitted)
                + (
                    f"; {len(refused)} refused by legal_dossier: " + "; ".join(refused)
                    if refused
                    else ""
                )
            ),
        )
        decision = PolicyDecision(
            # **Derived from the writers, never from the clock.** A timestamp in the material
            # makes a replayed acceptance mint a second decision row for one judgment, which is
            # the opposite of what `decision_id_for` is for.
            decision_id=decision_id_for(
                "roster-accept:" + "+".join(sorted(wid for _, wid in admitted)), 0, (gate,)
            ),
            outcome=Outcome.ACCEPT,
            gates=(gate,),
            reason=(
                "a person put these writers on the roster; legality was checked again at "
                "acceptance because the registered axis vocabulary grows between a "
                "declaration and this act, and nothing here ranked or chose between dossiers"
            ),
        )
        moved = (
            store.accept_writers(
                [wid for _, wid in admitted], decision=decision, accepted_at=stamp
            )
            if admitted
            else 0
        )
    finally:
        store.close()

    print(f"accepted {moved} of {len(rows)} proposed writer(s)")
    for name, wid in admitted:
        print(f"  {wid}  {name}")
    for line in refused:
        print(f"  ! left proposed: {line}", file=sys.stderr)
    return EXIT_FAULT if refused and not admitted else EXIT_OK


def cmd_roster_refuse(args: argparse.Namespace) -> int:
    """Turn proposed writers down, as one decision with a reason on it.

    **`accept`'s twin, and the three differences are all the same argument.** A bare `accept`
    with no names takes every proposal, because admitting the pile is the ordinary end of a
    recruit run; a bare `refuse` names nothing on purpose — `names` is required — because
    sweeping the pile into the bin is not an ordinary act and a fat-fingered one would be
    unrecoverable. `--reason` is required for the same weight of act: migration 036 makes a
    refused row point at a decision, and a decision row with an empty reason is a signature on
    a blank line. And there is no `--force`, because there is nothing here to override.

    **There is no un-refuse, and the schema is why there does not need to be.** A changed mind
    is a new proposal under the same name: `roster_accepted_name_idx` covers `accepted` alone,
    so refusing releases the name completely. A verb that walked a row backwards would be the
    one path by which a refusal could quietly stop having happened.
    """
    stamp = _stamp(_now())
    store = _roster_store(args)
    try:
        # The same in-flight guard `accept` carries. A refusal is an operator act by exactly
        # the same argument, and a recruit run holding the pen must not be able to type it.
        if os.environ.get(RECRUIT_SHELF_ENV, "").strip():
            print(
                "litharness: a recruit run is in flight; refusal is an operator act and is "
                "refused from inside one. Let the run finish and refuse it yourself",
                file=sys.stderr,
            )
            return EXIT_FAULT

        reason = args.reason.strip()
        if not reason:
            print("litharness: --reason cannot be blank", file=sys.stderr)
            return EXIT_FAULT

        proposed = store.roster_rows(status=writers_domain.RosterStatus.PROPOSED)
        wanted = set(args.names)
        rows = [
            row
            for row in proposed
            if row["name"] in wanted or row["writer_id"] in wanted
        ]
        missing = sorted(
            wanted
            - {row["name"] for row in proposed}
            - {row["writer_id"] for row in proposed}
        )
        if missing:
            print(
                f"litharness: no proposed writer named {', '.join(missing)}; "
                "`litharness roster show` lists what is declared. A writer already accepted "
                "or already refused is not a proposal and cannot be refused",
                file=sys.stderr,
            )
            return EXIT_FAULT
        if not rows:
            print("nothing proposed; the roster is unchanged")
            return EXIT_OK

        # **No `legal_dossier` pass here, unlike `accept`.** An illegal dossier is the row an
        # operator most wants to turn down, and re-checking it would refuse the refusal.
        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="roster.refuse.v0",
            passed=True,
            blocking=False,
            detail=(
                f"{len(rows)} writer(s) refused: "
                + ", ".join(f"{row['name']} {row['writer_id']}" for row in rows)
            ),
        )
        decision = PolicyDecision(
            # Derived from the writers and the reason, never from the clock: replaying one
            # refusal must converge on its row rather than mint a second. The reason is in the
            # material because refusing the same writer for a different stated reason is a
            # different judgment.
            decision_id=decision_id_for(
                "roster-refuse:"
                + "+".join(sorted(row["writer_id"] for row in rows))
                + ":"
                + reason,
                0,
                (gate,),
            ),
            # **`PARK`, because `Outcome` has no rejection member and inventing one is not
            # this change's to make.** It is contract-bound through `to_contract`, so a
            # seventh member moves `litharness-contracts` — the same boundary 035 hit when it
            # wanted an `EventType` for a roster admission and recorded its absence instead.
            # `PARK` is the honest fit of the six: terminal by `is_terminal`, and already the
            # word this system uses for work that ends here rather than going round again.
            outcome=Outcome.PARK,
            gates=(gate,),
            reason=f"a person turned these writers down: {reason}",
        )
        moved = store.refuse_writers(
            [row["writer_id"] for row in rows], decision=decision, refused_at=stamp
        )
    finally:
        store.close()

    print(f"refused {moved} of {len(rows)} proposed writer(s)")
    for row in rows:
        print(f"  {row['writer_id']}  {row['name']}")
    return EXIT_OK


def cmd_recruit(args: argparse.Namespace) -> int:
    """Put the Recruiter on one shelf, holding the roster's read views and declare.

    **`cmd_architect`'s pattern, one shelf at a time.** The database, the shelf and the form
    reach the child through the environment, which is why those variables exist: a flag between
    the binary and the subcommand would force the allowance to widen to every command this CLI
    has. Everything the agent declares is proposed, and unlike the world suite the allowance is
    enumerated rather than wildcarded, so `roster accept` is not a string this run can type.

    **It runs with no writer of its own.** The premise lock this exists to break lives in the
    four cast dossiers, and a cast writer drafting a colleague's dossier is that lock at one
    remove; `writer=None` is the same anonymous control every call made before a cast existed.

    **One shelf per call, and `--all` is refused.** Three independent reasons, each sufficient:
    `claude -p` fails under box load and the failure is silent-ish, so twelve agent runs in one
    process is twelve chances at that inside a single decision row; `_completion_call` checks
    the budget per call, so a twelve-shelf run refused partway through could not say which
    shelves got done; and the brief says one recruit call per specialization. `roster show`'s
    `unstaffed` list makes the operator's shell loop one line and every iteration resumable.
    """
    # **The slate's own assignment is the default**, so the twelve-shelf loop is one flag per
    # call and a form nobody typed is a form nobody can mistype. An explicit `--shape` still
    # wins and is recorded on the row and in the decision's profile.
    shape = args.shape or recruiter.shape_for(args.specialization)
    # **The child is handed the roster's home, not whatever book database happened to be
    # open.** The Recruiter's declares belong in the installation's roster when one is
    # configured, and the child reads its database from the environment.
    database = str(Path(_roster_database(args)).resolve())
    previous = {
        DATABASE_ENV: os.environ.get(DATABASE_ENV),
        RECRUIT_SHELF_ENV: os.environ.get(RECRUIT_SHELF_ENV),
        RECRUIT_SHAPE_ENV: os.environ.get(RECRUIT_SHAPE_ENV),
    }
    os.environ[DATABASE_ENV] = database
    os.environ[RECRUIT_SHELF_ENV] = args.specialization
    os.environ[RECRUIT_SHAPE_ENV] = shape

    stamp = _stamp(_now())
    declared: list[dict[str, Any]] = []
    result = None
    # **The store is opened inside the `try`, so a failure to open it does not leave the three
    # variables set in this process.** Outside it, an unopenable database left
    # `LITHARNESS_RECRUIT_SHELF` behind and the next `roster accept` was refused as though a run
    # were in flight — which matters for the in-process driver the tests use, and for anything
    # that calls `main` twice.
    store = None
    try:
        store = _roster_store(args)
        before = {row["writer_id"] for row in store.roster_rows()}
        standing = [
            row["name"] for row in store.roster_rows(specialization=args.specialization)
        ]
        if standing:
            print(f"  {len(standing)} already on this shelf: {', '.join(standing)}")

        request = recruiter.render_recruit_request(args.specialization, shape=shape)
        registry = build_default_registry()
        spend = _StageSpend()
        calls = _ProviderCalls(
            registry=registry,
            store=store,
            args=args,
            stamp=stamp,
            run=_StageSpend(),
        )
        result, refusal = _completion_call(request, calls=calls, spend=spend)
        if result is None:
            print(f"litharness: {refusal}", file=sys.stderr)
            return EXIT_FAULT

        declared = [
            row for row in store.roster_rows() if row["writer_id"] not in before
        ]
        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id=request.profile,
            passed=len(declared) == 1,
            blocking=False,
            detail=(
                f"{len(declared)} writer(s) declared for {args.specialization} in the "
                f"{shape} form, all proposed"
                + (f": {', '.join(row['name'] for row in declared)}" if declared else "")
                + (f"; note: {args.note}" if args.note else "")
            ),
        )
        store.record_decision(
            PolicyDecision(
                # The stamp belongs in this material and does not belong in acceptance's: two
                # recruit runs on one shelf are two distinct paid events and must not collapse
                # into one row, where two acceptances of one writer are one judgment replayed.
                decision_id=decision_id_for(
                    f"recruit:{args.specialization}:{shape}:{stamp}", 0, (gate,)
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
                    "the Recruiter drafted a dossier through its own commands; everything it "
                    "declared is a proposal, nothing here ranked one dossier against another, "
                    "and no writer reaches a drafting prompt until a person runs `roster "
                    "accept`"
                ),
            ),
            decided_at=stamp,
        )
    finally:
        if store is not None:
            store.close()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    _say(result.text.strip())
    print()
    for row in declared:
        print(f"  {row['writer_id']}  {row['name']}  awaiting `roster accept`")
    if not declared:
        # **A paid call that produced no record is the silent shape this repository keeps
        # finding, and a shell loop over the twelve has to know which shelves to run again.**
        # `cmd_architect` returns EXIT_OK for a zero-record run; this deliberately does not.
        print("litharness: the Recruiter declared nobody", file=sys.stderr)
        return EXIT_ATTENTION
    return EXIT_OK


def _descriptor_from(path: str) -> voice_domain.StyleDescriptor:
    """A style descriptor read from a file, or a `SystemExit` naming what is wrong with it.

    **The only door a descriptor comes through, and it is a file rather than flags.** Eight
    numbers and two labels as ten command-line arguments is ten chances to transpose two of
    them, and a descriptor is content-addressed — a transposition does not fail, it mints a
    different aim under a different id and nothing says so.
    `research/quality-measurement/voice_descriptors.py --emit` writes exactly this shape.
    """
    raw = json.loads(_read_text(path))
    if not isinstance(raw, dict):
        raise SystemExit(f"litharness: {path} is not a descriptor object")
    try:
        return voice_domain.StyleDescriptor(
            person=voice_domain.Person(raw.pop("person", "")),
            tense=voice_domain.Tense(raw.pop("tense", "")),
            **{key: float(value) for key, value in raw.items()},
        )
    except (TypeError, ValueError, voice_domain.MalformedDescriptor) as error:
        raise SystemExit(
            f"litharness: {path} is not a usable descriptor: {error}. It needs exactly the "
            "fields `voice.StyleDescriptor` declares, and `voice_descriptors.py --emit` "
            "writes them"
        ) from error


def cmd_revoice(args: argparse.Namespace) -> int:
    """Draw a passage as this writer, then re-mint the writer with its dossier written that way.

    **Two paid calls and one proposal, and nothing in between is a choice.** The writer draws a
    passage aimed by a descriptor; the passage is kept by its content address; an anonymous
    rewriter returns the dossier saying the same things in that register; five gates read what
    came back; and a **new** writer mints, carrying the exemplar digest as addressed material.
    `application/revoice.py` holds both prompts and the gates, and the rail it holds is that a
    refusal is a refusal: there is no redraw here, because drawing again and keeping the one
    that passed is selection among candidates by preference (§61(5), §105.1), which §146.8
    refused when a census hit could have been redrawn away.

    **Nothing is edited.** `plan/dossier-voice-direction.md`'s anti-scope is explicit that
    populating an exemplar mints a new writer rather than mutating one, and content addressing
    makes that structural rather than polite: the parent's row is untouched and the child is a
    different id.

    **The name, and the one place this is awkward on purpose.** A child keeps its parent's name,
    which is legal for a proposal and refused at acceptance while the parent is accepted — the
    partial index holds one accepted writer per name. The way through is the operator's and it
    is two recorded acts rather than a flag: `roster refuse` the parent, then `roster accept`
    the child, which migration 036 exists to make possible. A compiled cast writer cannot be
    re-minted under its own name at all, because `refuse_reserved_name` protects the controls
    the roster is read against, so revoicing one needs `--name` and says so.
    """
    stamp = _stamp(_now())
    descriptor = _descriptor_from(args.descriptor)
    # The roster store, and the parent resolves against it directly rather than through
    # `_installed_writer`: this store *is* the installation's roster when one is configured,
    # and the exemplar row the child's `exemplar_digest` points at must land beside the row
    # that carries the digest.
    store = _roster_store(args)
    try:
        parent, reason = _resolve_writer(args.writer, store)
        if parent is None:
            print(reason or f"litharness: no writer named {args.writer!r}", file=sys.stderr)
            return EXIT_FAULT
        name = (args.name or parent.name).strip()
        if reserved := roster_mod.reserved_name(name):
            print(reserved, file=sys.stderr)
            print(
                "  a re-minted writer needs a name of its own here: pass --name. The compiled "
                "controls the roster is read against must not be shadowed by a stored row",
                file=sys.stderr,
            )
            return EXIT_FAULT

        rows = store.roster_rows(name=parent.name)
        specialization = args.specialization or (rows[0]["specialization"] if rows else "")
        shape = args.shape or (rows[0]["shape"] if rows else "")
        if not specialization or not shape:
            print(
                "litharness: this writer has no stored shelf or form to inherit, so a re-mint "
                "needs --specialization and --shape. A recruit carries both and a compiled cast "
                "writer carries neither; an unlabelled row drops out of the registered arm "
                "without saying so",
                file=sys.stderr,
            )
            return EXIT_FAULT

        registry = build_default_registry()
        spend = _StageSpend()
        calls = _ProviderCalls(
            registry=registry, store=store, args=args, stamp=stamp, run=_StageSpend()
        )

        draw = revoice.render_exemplar_request(parent, descriptor=descriptor)
        drawn, refusal = _completion_call(draw, calls=calls, spend=spend)
        if drawn is None:
            print(f"litharness: the draw returned nothing: {refusal}", file=sys.stderr)
            return EXIT_FAULT
        passage = drawn.text.strip()
        digest = store.record_exemplar(
            passage=passage,
            drawn_by=parent.writer_id,
            descriptor=descriptor,
            profile=draw.profile,
            drawn_at=stamp,
        )

        rewrite = revoice.render_rewrite_request(dossier=parent.dossier, exemplar=passage)
        returned, refusal = _completion_call(rewrite, calls=calls, spend=spend)
        if returned is None:
            print(f"litharness: the rewrite returned nothing: {refusal}", file=sys.stderr)
            print(f"  the passage is kept as {digest}", file=sys.stderr)
            return EXIT_FAULT

        try:
            dossier = revoice.accept_rewrite(
                original=parent.dossier, exemplar=passage, returned=returned.text
            )
            child = writers_domain.build(
                name,
                dossier,
                interests=parent.interests,
                exemplar_digest=digest,
                note=(
                    args.note
                    or f"voiced from {parent.writer_id} against {descriptor.descriptor_id}"
                ),
            )
            fresh = store.record_proposed_writer(
                child, specialization=specialization, shape=shape, proposed_at=stamp
            )
        except writers_domain.IllegalDossier as error:
            # **Nothing is written on this path except the passage**, which was already kept and
            # is kept deliberately: it was paid for, it addresses itself, and a second run that
            # drew it again would converge on the same row. What does not exist is a writer.
            print(f"litharness: the rewrite was refused: {error}", file=sys.stderr)
            print(f"  the passage is kept as {digest}; no writer was minted", file=sys.stderr)
            return EXIT_FAULT

        gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id=rewrite.profile,
            passed=True,
            blocking=False,
            detail=(
                f"{name} re-minted as {child.writer_id} from {parent.writer_id}, aimed by "
                f"{descriptor.descriptor_id}, exemplar {digest}, "
                f"{len(dossier.split())} words, proposed"
                + ("" if fresh else "; already on record")
            ),
        )
        store.record_decision(
            PolicyDecision(
                decision_id=decision_id_for(
                    f"revoice:{parent.writer_id}:{digest}:{stamp}", 0, (gate,)
                ),
                outcome=Outcome.ACCEPT,
                gates=(gate,),
                profile=rewrite.profile,
                provider=spend.provider,
                model=spend.model,
                invocations=spend.invocations,
                total_tokens=spend.total_tokens,
                cost_usd=spend.cost_usd,
                reason=(
                    "a writer drew one passage as itself and its dossier was rewritten to read "
                    "like it; nothing ranked two candidates, nothing was redrawn, the parent is "
                    "untouched, and the re-mint is a proposal until a person accepts it"
                ),
            ),
            decided_at=stamp,
        )
    finally:
        store.close()

    print(f"{name}: re-minted as {child.writer_id} [proposed]")
    print(f"  from {parent.writer_id}, aimed by {descriptor.descriptor_id}")
    print(f"  passage {digest}, {len(passage.split())} words")
    print(f"  dossier {len(dossier.split())} words; `roster show --dossier` reads it back")
    if name == parent.name:
        print(
            f"  both writers answer to {name!r}. Only one may be accepted: `roster refuse "
            f"{parent.writer_id}` first if the parent is on the roster"
        )
    return EXIT_OK


def _finish_drawn_systems(
    store: SqliteStore, book_id: str, branch_id: str, stamp: str
) -> tuple[int, tuple[str, ...]]:
    """Mint the configuration a seed-drawn system cannot declare for itself (stage-0 §165).

    **`world accept` is where this belongs, because here is where a person acted.**
    `magnitude_scale` is mint-only by §163.2's decision — documenting it would invite a second
    declaration beside the drawn one — and the Architect's `declare` path never constructs a
    `SystemDef`. So a seed could draw an issuer, a ladder, governed capabilities and a
    prerequisite graph and still be told *"this book declares no game system"*, with no
    documented way to fill the one slot that decides it. That is Serial Pilot 15 §2.1.

    Canon is re-read **after** promotion so a scale is never derived from a proposal this accept
    declined to carry, and `gamesystem.completion_records` returns only the two predicates only
    it can mint: nothing here declares a rung, a capability, an edge or a sheet.

    **And it stops rather than finishing a system that would block the book, which is measured
    rather than anticipated.** `genre.has_starting_sheet` is §160's ratchet: a book that declares
    a game system must hold a sheet that is a real position in it, and until a system is declared
    that half never runs. Serial Pilot 15 declared *both* a system whose columns are the rung and
    six capability ids **and** a hand-written sheet of `rung`, `reach`, `carried` and `standing` —
    two half-models that do not correspond. Finishing its system took that book from drafting to
    `blocked` on a real run of this command, which is a fix breaking a book to report a gap. The
    two shapes are told apart here rather than in `gamesystem`, because the question is the
    floor's and `genre` is what owns it — `gamesystem` cannot import it without closing a cycle.
    """
    canon = [
        record
        for record in store.state_records(book_id, branch_id)
        if state_mod.is_canon(record)
    ]
    completions, unfinished = gamesystem.completion_records(canon)
    if not completions:
        return 0, unfinished
    finished = [
        dataclasses.replace(record, authority=lc.StateAuthority.ACCEPTED_CANON)
        for record in completions
    ]
    if genre.has_starting_sheet(canon) and not genre.has_starting_sheet([*canon, *finished]):
        printed = ", ".join(field_.name for field_ in extraction.sheet_for(canon).fields)
        columns = ", ".join(
            key
            for system in gamesystem.systems_of([*canon, *finished])
            for key in system.value_keys
        )
        return 0, (
            *unfinished,
            "a system is drawn and was left unfinished on purpose: this book prints a sheet of "
            f"({printed}) and the system's own columns are ({columns}), so declaring the system "
            "would put the book under the rule that a sheet must be a position in its system and "
            "stop it drafting. The sheet and the system are two descriptions of different books; "
            "one of them has to give, and neither is this command's to choose",
        )
    written = store.record_state_records(book_id, branch_id, finished, created_at=stamp)
    return written, unfinished


def _report_completion(completed: int, unfinished: Sequence[str]) -> None:
    """Say what was finished and, for anything that was not, why — never silently."""
    if completed:
        print(
            f"  {completed} record(s) minted to finish a drawn system: the scale its own "
            "numbers imply, and the digest that identifies it"
        )
    for reason in unfinished:
        # A system the world drew and this could not finish leaves `system_gap` open, and an
        # operator reading that gap is owed the reason it is still open rather than the gap's
        # own default sentence about a world that declared nothing.
        print(f"  not finished: {reason}")


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
    that is the rail enforced by `world accept` — an agent with this tool cannot put a fact
    into a book, only offer one.
    """
    store = _store(args)
    stamp = _stamp(_now())
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        records = store.state_records(book_id, branch_id)
        # **What this world says, as against what has ever been written into it.** Every view
        # below except `show` reads the resolved set: a proposal a later declaration or an
        # accepted record already replaced is not part of the world and reporting it is how
        # `world ladders` came to print `[]` for a world whose three chains resolve. `show` is
        # the exception on purpose — it is the provenance view, and an Architect that cannot
        # see what it proposed last chapter proposes it again.
        declared_at = store.state_record_times(book_id, branch_id)
        in_force = integrity.in_force(records, declared_at=declared_at)

        if args.view == "accept":
            proposals = [
                record for record in records if record.authority is lc.StateAuthority.PROPOSED
            ]
            if not proposals:
                # **Completion still runs, and that is what makes an accepted book fixable.**
                # Serial Pilot 15's world was already accepted when its system was found to be
                # unfinishable, and there is no retraction to re-propose it with. Accept is the
                # person-gate whether or not it has anything to promote, so running it again on
                # a world with nothing outstanding finishes a drawn system and says so.
                completed, unfinished = _finish_drawn_systems(store, book_id, branch_id, stamp)
                print("nothing proposed; canon is unchanged")
                _report_completion(completed, unfinished)
                return EXIT_OK
            # **A declaration a later one replaced is not carried, and this is what makes the
            # Architect usable at all.** `world declare` appends and has no retraction, so an
            # agent that improves its own record writes a second one into the same slot;
            # accepting both makes `state.contradiction.v1` fire MAJOR and blocking on every
            # scene, three attempts each, until the unit poisons. Measured on Serial Pilot 7:
            # four such pairs and not one word of the book could be drafted. Nothing is
            # demoted — `promote_state_records` is only ever upward — the replaced records
            # simply stay the proposals they already were, and `world summary` still counts
            # them. See `integrity.superseded`.
            #
            # **Every record, not just the proposals, and that is the second round's fix.** A
            # proposal left behind by a first accept sits in a slot canon now holds; among the
            # proposals alone nothing supersedes it, so it used to promote and put two values
            # in one canon slot — MAJOR, blocking, every scene refused. Passing canon in is
            # what lets it be recognised as already answered. Canon is never replaced by this,
            # so `carried` is still only ever a subset of the proposals.
            replaced = integrity.superseded(records, declared_at=declared_at)
            carried = [record for record in proposals if record.record_id not in set(replaced)]
            complaints = worlds_domain.validate(in_force)
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
            # **§178's refusal, and it is deliberately its own branch.** A world naming its
            # system out of this repository's own vocabulary is not a world contradicting
            # itself, so folding it into `validate` would make the sentence above false for
            # half the worlds it printed on. Serial Pilot 16 accepted `ladder is_a Ladder` and
            # `rung is_a Rung` cleanly, and `Rung` was a printed column on the page twice in
            # chapter one before anybody read it. Same `--force`, because the override is the
            # operator's for the same reason it is on the line above: this refuses a name, and
            # a person is allowed to decide a name is what the book wants.
            machinery = schema_words.world_complaints(in_force)
            if machinery and not args.force:
                for complaint in machinery:
                    print(f"litharness: {complaint}", file=sys.stderr)
                print(
                    f"litharness: {len(proposals)} proposal(s) not accepted; {len(machinery)} "
                    "world-facing name(s) are this system's own words for its machinery. "
                    "Rename with `world declare`, or --force to accept them anyway.",
                    file=sys.stderr,
                )
                return EXIT_FAULT
            moved = store.promote_state_records(
                book_id,
                branch_id,
                [record.record_id for record in carried],
                authority=lc.StateAuthority.ACCEPTED_CANON,
                created_at=stamp,
            )
            completed, unfinished = _finish_drawn_systems(store, book_id, branch_id, stamp)
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="world.accept.v0",
                passed=not complaints,
                blocking=False,
                detail=(
                    f"{moved} proposal(s) accepted; {len(replaced)} replaced by a later "
                    f"declaration; {len(complaints)} complaint(s); "
                    f"{completed} system record(s) minted; {len(unfinished)} system(s) unfinished"
                    + (
                        "; replaced: "
                        + ", ".join(
                            f"{record.subject} {record.predicate}"
                            for record in proposals
                            if record.record_id in set(replaced)
                        )
                        if replaced
                        else ""
                    )
                ),
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
                        "ranked or chose between them, and a declaration a later one "
                        "replaced was left as the proposal it already was"
                    ),
                ),
                decided_at=stamp,
            )
            print(f"accepted {moved} of {len(proposals)} proposal(s) into canon")
            _report_completion(completed, unfinished)
            if replaced:
                # **Named, not just counted.** Without the fix a redeclaration was a loud
                # blocking finding on every scene; with it, it is a record quietly not
                # carried. That is the right outcome and the wrong volume, so the slots go
                # on the page and into the decision's detail — a drop nobody can see is the
                # shape of defect this repository keeps finding.
                print(
                    f"  {len(replaced)} left proposed: a later declaration filled the same "
                    "slot, and accepting both is a blocking contradiction on every scene"
                )
                by_id = {record.record_id: record for record in records}
                for record_id in replaced:
                    record = by_id[record_id]
                    print(f"    {record.subject} {record.predicate}")
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
            print(json.dumps(world_mod.presence(in_force, scenes), ensure_ascii=False, indent=2))
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
            # **The second list is the one that matters, and it is second because the first
            # one lies about it.** `not_yet_coherent` is a promise that the rest of the world
            # will settle this, and for a question awaiting its answer or a rung awaiting its
            # chain that promise is kept. A record written into the wrong slot reads
            # identically in that list and nothing will ever settle it: there is no
            # retraction, and `integrity.disagreement_key` makes a correction that changes the
            # subject, the edge or the story position a *different* slot, so `world accept`
            # carries both. Serial Pilot 13's first seed read a membership complaint about six
            # `consequence` edges, took it for transient, and left six dead records in canon;
            # Serial Pilot 12's read eleven complaints naming standings and diagnosed the CLI.
            # Both were told something true under a heading that made it sound temporary.
            warnings = worlds_domain.slot_warnings(record)
            written = store.record_state_records(book_id, branch_id, [record], created_at=stamp)
            payload: Any = {
                "record_id": record.record_id,
                "authority": record.authority.value,
                "new": bool(written),
                "says": state_mod.describe(record),
                "not_yet_coherent": new_complaints,
                "will_not_resolve": list(warnings),
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                verb = "declared" if written else "already on record"
                print(f"{verb}: {payload['says']}  [{record.authority.value}]")
                for complaint in new_complaints:
                    print(f"  ! not yet coherent: {complaint}", file=sys.stderr)
                for warning in warnings:
                    print(f"  !! will not resolve: {warning}", file=sys.stderr)
            return EXIT_OK
    finally:
        store.close()

    if args.view == "show":
        payload = world_mod.declarations(records, subject=args.subject)
    elif args.view == "rules":
        payload = world_mod.rules(in_force)
    elif args.view == "ladders":
        payload = world_mod.ladders(in_force)
    elif args.view == "abilities":
        payload = world_mod.abilities(in_force, holder=args.holder)
    elif args.view == "cast":
        payload = world_mod.cast(in_force)
    elif args.view == "threads":
        payload = world_mod.threads(in_force, at=args.at)
    elif args.view == "vocabulary":
        payload = world_mod.vocabulary()
    elif args.view == "check":
        payload = world_mod.check(in_force)
    else:
        payload = world_mod.summary(records, in_force)

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


@dataclass
class _StageSpend:
    """One command stage's provider spend, summed across its calls for a decision row."""

    invocations: int = 0
    total_tokens: int = 0
    #: `None` until a provider reports dollars, which is `_StageSpend`'s rule and the reason
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
class _ProviderCalls:
    """Everything a multi-call command needs to call a provider and account for it.

    **The running total is why this is an object.** `store.spend_on` reads the decision
    ledger, while listing, reading, and Architect commands record their decisions only after
    all their calls finish. `run` carries what this invocation has already spent, and every
    budget check is made against the ledger plus that.
    """

    registry: ProviderRegistry
    store: SqliteStore
    args: argparse.Namespace
    stamp: str
    #: Everything this command has spent so far.
    run: _StageSpend

    def spent_today(self) -> Spend:
        return self.store.spend_on(self.stamp[:10]).plus(
            invocations=self.run.invocations,
            tokens=self.run.total_tokens,
            cost_usd=self.run.cost_usd or 0.0,
        )


def _completion_call(
    request: CompletionRequest, *, calls: _ProviderCalls, spend: _StageSpend
) -> tuple[CompletionResult | None, str]:
    """One budget-checked model call, or `None` and an operational refusal reason."""
    provider, _ = calls.registry.resolve(request.call_class)
    verdict = budget_check(
        _budget(calls.args),
        calls.spent_today(),
        provider=provider.name,
        prompt_chars=request.input_chars,
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
    shape = SerialShape(args.chapter_scenes, args.arc_chapters)
    try:
        template, serial_mode = _creation_template(args.scenes, shape)
    except TemplateMismatch as error:
        print(f"litharness: {error}", file=sys.stderr)
        return EXIT_FAULT
    revision = new_book(
        book_id,
        branch_id,
        title=args.title,
        scenes=args.scenes,
        position_capacity=SERIAL_POSITION_CAPACITY,
    )
    # `arc_template` refuses fewer scenes than named beats, and it must refuse *before* the
    # store opens: a raise after `commit_revision` would leave the book, decision, premise
    # and seed state durably committed behind a command that reported failure.

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
    # **Grammatical person is a position the book is created with, or it is nobody's.** Read 4
    # found the writer choosing third person eight scenes out of eight with nothing anywhere
    # deciding it; `--person first` seeds one locked constraint beside the premise, and it reaches
    # every scene call the way a director's own constraint does. Absent, nothing is seeded and
    # the book is the book it always was.
    seeded_items = [premise]
    if getattr(args, "person", None) == "first":
        seeded_items.append(
            lc.PlanItem(
                logical_id=FIRST_PERSON_PLAN_ID,
                kind=lc.PlanKind.CONSTRAINT,
                text=FIRST_PERSON_CONSTRAINT,
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            )
        )
    # **The concept rides beside the premise, unlocked** (§197). `plans.constraints_of` carries
    # only locked items into the scene call, so the writer is never handed the turn; the seed
    # and the outline read it back through `concept.concept_of`, and its debts open below.
    concept = _concept_from(getattr(args, "concept", None))
    if concept is not None:
        seeded_items.append(concept.plan_item())
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
    entries: object = None
    if args.promises:
        entries = json.loads(Path(args.promises).read_text(encoding="utf-8"))
    elif concept is not None:
        # The concept's debts, through the same loader, so one path opens both kinds.
        entries = concept.promise_entries()
    if entries is not None:
        planned_beats = (
            beats_for_serial(revision, shape) if serial_mode else beats_for(revision, template)
        )
        keys = [beat.story_order_key for beat in planned_beats]
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
                    isinstance(due, int) and not isinstance(due, bool) and 1 <= due <= len(keys)
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
            seeded_items,
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
                    payload={
                        "items": len(seeded_items),
                        "premise": True,
                        "person": getattr(args, "person", None),
                        "concept": concept is not None,
                    },
                )
            ],
        )
        if records:
            store.record_state_records(book_id, branch_id, records, created_at=stamp)
        for promise in promise_rows:
            store.record_promise(book_id, branch_id, promise)
    finally:
        store.close()

    print(revision.revision_id)
    print(f"  book={book_id} branch={branch_id}")
    print(f"  {args.scenes} empty scene(s); template {template.template_id}")
    print(f"  {len(records)} seed state record(s)")
    if concept is not None:
        print(
            f"  concept seeded as {concept_mod.CONCEPT_PLAN_ID}; {len(promise_rows)} debt(s) "
            "opened from it for the world to hold answers to"
        )
    elif promise_rows:
        print(f"  {len(promise_rows)} seeded promise(s), each with an answer already in canon")
    if graph_fault:
        print(f"  graph line declared and UNUSABLE, so this book has none: {graph_fault}")
    # **The report half of the house genre floor**, and the condition is the floor's own
    # predicate rather than a count. `not records` let any record at all silence this, which is
    # how pilot 13's book — canon full, no status snapshot anywhere in it — was created,
    # outlined and drafted without the advisory ever printing. The sentence comes from
    # `domain/genre.NO_SHEET`, so what is said here and what the floor refuses with cannot
    # drift apart.
    if not genre.has_starting_sheet(records):
        print(f"  {genre.NO_SHEET}")
        print(
            "  this book will not draft until one is seeded: `new --state`, `import "
            "--state`, or — once its world is accepted — `world declare <subject> "
            "status_snapshot --value '{...}' --order-key <key>` then `world accept`"
        )
    return EXIT_OK


def cmd_extend(args: argparse.Namespace) -> int:
    """Append complete planned arcs to the same canonical serial.

    This is structural growth, not a sequel and not a new volume. Character/state/promise
    ledgers remain on the same book and release volumes continue to be derived windows over
    its chapter numbers.
    """
    if args.arcs < 1:
        print("litharness: --arcs must be at least 1", file=sys.stderr)
        return EXIT_FAULT
    store = _store(args)
    stamp = _stamp(_now())
    try:
        book_id, branch_id = export_module.resolve_branch(store, args.book, args.branch)
        head = store.head(book_id, branch_id)
        if head is None:
            print("litharness: this branch has no revision", file=sys.stderr)
            return EXIT_FAULT
        shape = SerialShape(args.chapter_scenes, args.arc_chapters)
        arcs = arcs_of(head, shape)
        partial = (
            shape.scenes_per_arc - len(arcs[-1].scene_ids) if arcs and not arcs[-1].closed else 0
        )
        count = partial + (args.arcs - (1 if partial else 0)) * shape.scenes_per_arc
        if count <= 0:
            count = shape.scenes_per_arc
        extended = append_scenes(head, count)
        decision = PolicyDecision(
            decision_id=decision_id_for(f"extend:{extended.revision_id}", 0, ()),
            outcome=Outcome.ACCEPT,
            base_revision_id=head.revision_id,
            resulting_revision_id=extended.revision_id,
            reason=(f"extended the open serial by {count} scene(s) to a complete planned arc"),
        )
        store.commit_revision(
            extended,
            created_at=stamp,
            decision=decision,
            events=[
                Event(
                    event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
                    project_id=args.project,
                    created_at=stamp,
                    actor=args.holder,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=extended.revision_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "extended": True,
                        "scenes_added": count,
                        "open_ended_serial": True,
                    },
                )
            ],
        )
    except ValueError as error:
        print(f"litharness: {error}", file=sys.stderr)
        return EXIT_FAULT
    finally:
        store.close()
    total = sum(1 for node in extended.nodes if node.kind is NodeKind.SCENE and not node.tombstoned)
    print(
        f"extended {book_id}/{branch_id} by {count} scene(s); {total} planned scene(s) now, "
        "same open-ended serial"
    )
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
    change_set = lc.parse_artifact(lc.ChangeSet, json.loads(args.path.read_text(encoding="utf-8")))
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
                f"litharness: no plan revision {args.plan_revision}; `litharness plans` lists them",
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
        proposal = rollback_proposal(current, target, rollback_of=undoing.proposal.proposal_id)
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
        plan = import_plan(snapshot, book_id=revision.book_id, branch_id=revision.branch_id)
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
        chapters_per_volume=args.volume_chapters,
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
                f"{len(book.chapters)} pastable chapter(s), "
                f"{len(book.volumes)} release volume(s){held}  [{state}]"
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
        help=(f"SQLite database path (default: ${DATABASE_ENV}, else {DEFAULT_DB})"),
    )
    parser.add_argument(
        "--roster-database",
        type=Path,
        default=(
            Path(os.environ[ROSTER_DATABASE_ENV])
            if os.environ.get(ROSTER_DATABASE_ENV, "").strip()
            else None
        ),
        help=(
            "where the installation's writer roster lives; --writer resolution, the roster "
            "suite, recruit and revoice all use it, so an accepted writer reaches a fresh "
            f"book database (default: ${ROSTER_DATABASE_ENV}, else --database)"
        ),
    )
    parser.add_argument(
        "--holder",
        default="session",
        help="identity recorded on tick ids and job leases (default: session)",
    )
    parser.add_argument(
        "--max-tokens-per-operation",
        type=int,
        default=None,
        help="refuse one call projected above this; -1 for unbounded",
    )
    parser.add_argument(
        "--max-tokens-per-day",
        type=int,
        default=None,
        help="daily token ceiling; -1 for unbounded",
    )
    parser.add_argument(
        "--max-invocations-per-day",
        type=int,
        default=None,
        help="daily call ceiling — the one tokens cannot express (§15); -1 for unbounded",
    )
    parser.add_argument(
        "--max-cost-usd-per-day",
        type=float,
        default=None,
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
            Path(os.environ["LITHARNESS_LIBRARY"]) if os.environ.get("LITHARNESS_LIBRARY") else None
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
        "--revise",
        action="store_true",
        default=_env_flag("LITHARNESS_REVISE"),
        help="rewrite the drafted scene for sentence and paragraph structure before gating it "
        "(§185's reviser); also read from LITHARNESS_REVISE. **Off by default since "
        "2026-09-02** (stage-0 §196): the operator dropped the stage after two settled-listing "
        "A/Bs found no sentence win its own battery would accept. With it set a second call is "
        "made and a second decision written; without it the frozen policy digest is the one "
        "every scene drafted before the reviser existed already carries",
    )
    parser.add_argument(
        "--no-revise",
        action="store_true",
        default=_env_flag("LITHARNESS_NO_REVISE"),
        help="accepted and does nothing: the reviser is off unless --revise is given. Kept so "
        "a recipe written for §185's control arm still parses",
    )
    parser.add_argument(
        "--chapter-scenes",
        type=int,
        default=4,
        help="how many scenes make one chapter, and the position each scene is told "
        "it holds when it is drafted (default: 4). This same shape drives planning, reader "
        "context, and release packaging, so those roles do not silently mean different "
        "chapters",
    )
    parser.add_argument(
        "--arc-chapters",
        type=int,
        default=6,
        help="chapters in one closed dramatic arc (default: 6). The serial has no ending; "
        "arcs close locally and keep stable beat assignments when later arcs are appended",
    )
    parser.add_argument(
        "--volume-chapters",
        type=int,
        default=library_module.DEFAULT_CHAPTERS_PER_VOLUME,
        help="chapters per derived release volume in the book library; 50 by default. This "
        "changes packaging only: the canonical book remains one open-ended serial and its "
        "state, promises, characters, and chapter numbering continue across boundaries",
    )
    parser.add_argument(
        "--exemplars",
        default=os.environ.get("LITHARNESS_EXEMPLARS", ""),
        help="a directory of openings the operator placed by hand, one folder per book holding "
        "Chapter1.txt and optionally blurb.txt, shown to the scene writer as how this shelf "
        "sounds and to the listing writer as how its listings sound (stage-0 §196). Also read "
        "from LITHARNESS_EXEMPLARS. Off by default and no shelf is the control. The directory "
        "must sit outside the repository's tracked tree: nothing shown is ever committed, and a "
        "draft sharing a run of consecutive words with an exemplar is refused on the ladder",
    )
    parser.add_argument(
        "--exemplars-limit",
        type=int,
        default=int(os.environ.get("LITHARNESS_EXEMPLARS_LIMIT", exemplars_mod.DEFAULT_LIMIT)),
        help="how many exemplars from that directory are shown, in the order exemplars.json "
        f"names or else by folder name; {exemplars_mod.DEFAULT_LIMIT} by default",
    )
    parser.add_argument(
        "--writer",
        default=os.environ.get("LITHARNESS_WRITER", ""),
        help="who drafts this book: the compiled cast "
        f"({', '.join(writers_domain.CAST)}), or any writer this database's roster has "
        "accepted. A parser is built before --database is read, so the four are named here "
        "and the roster is looked up; `litharness roster show` lists it. Also read from "
        "LITHARNESS_WRITER. Off by default and no writer is the control — until 2026-08-25 "
        "there was no way to pass one at all and every scene was drafted by nobody. An "
        "unknown name, and a name declared but not yet accepted, are refused rather than "
        "ignored",
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
    parser.add_argument(
        "--reader-checkpoints",
        action="store_true",
        default=_env_flag("LITHARNESS_READER_CHECKPOINTS"),
        help="schedule versioned steering-reader observations at completed chapter boundaries; "
        "also read from LITHARNESS_READER_CHECKPOINTS. The bundled mechanism is experimental, "
        "so its observations are recorded but cannot steer until a qualified mechanism version "
        "with an evidence digest is registered",
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
        "--dismiss",
        action="store_true",
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
    new.add_argument(
        "--premise",
        required=True,
        help="what the book is about; the planner "
        "reports a book without one as blocked rather than drafting it",
    )
    new.add_argument(
        "--scenes",
        type=int,
        default=SerialShape().scenes_per_arc,
        help="how many planned scene nodes to create (default: one complete 24-scene arc). "
        "Production plans only structurally complete arcs; extend the same serial for more",
    )
    new.add_argument("--state", type=Path, help="a StateSnapshot to seed canon with")
    new.add_argument(
        "--person",
        choices=("first", "third"),
        default=None,
        help="which grammatical person the story is told in. `first` seeds one locked "
        "constraint beside the premise that every scene call then carries; `third` and "
        "the default seed nothing, which is the book as it was before this existed",
    )
    new.add_argument(
        "--promises",
        type=Path,
        help="debts to open before scene one, each with a due scene; the answers live in the "
        "seed snapshot. Without it the ledger only ever holds what a scene invented",
    )
    new.add_argument(
        "--concept",
        type=Path,
        help="the settled concept (`concept.json` from `litharness concept`) this book is "
        "created from: persisted beside the premise as an unlocked plan item the scene "
        "writer never sees, read back by the world seed and the outline, and its debts "
        "opened as promises before scene one",
    )
    new.add_argument("--book", help="book id; a fresh uuid by default")
    new.add_argument("--branch", help="branch id; a fresh uuid by default")
    new.set_defaults(func=cmd_new)

    extend = sub.add_parser(
        "extend",
        help="append complete planned arcs to the same open-ended serial",
    )
    extend.add_argument(
        "--arcs",
        type=int,
        default=1,
        help="complete this many additional arcs (default: 1); a partial planned arc is "
        "completed first",
    )
    extend.add_argument("--book", help="book id; defaults to the only branch")
    extend.add_argument("--branch", help="branch id; defaults to the only matching branch")
    extend.set_defaults(func=cmd_extend)

    state = sub.add_parser("state", help="what this book holds as true, in story order")
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
    prompts.add_argument("--scene", help="inspect the exact stored request for this scene")
    prompts.add_argument("--book")
    prompts.add_argument("--branch")
    prompts.add_argument(
        "--writer",
        default=argparse.SUPPRESS,
        help=_WRITER_OVERRIDE_HELP,
    )
    prompts.add_argument("--json", action="store_true")
    prompts.set_defaults(func=cmd_prompts)

    seed = architect_sub.add_parser(
        "seed", help="build enough world to stand the first chapters, under a listing"
    )
    seed.add_argument(
        "--overview",
        help="a file, or - for stdin. Defaults to this book's own premise, which is the "
        "listing it was created under",
    )
    seed.add_argument(
        "--writer",
        default=argparse.SUPPRESS,
        help=_WRITER_OVERRIDE_HELP,
    )
    seed.add_argument("--book")
    seed.add_argument("--branch")
    seed.set_defaults(func=cmd_architect)

    grow = architect_sub.add_parser(
        "grow", help="after a chapter: keep the world coherent and spend what it declared"
    )
    grow.add_argument("--scene", help="a scene logical id; the latest drafted one by default")
    grow.add_argument(
        "--writer",
        default=argparse.SUPPRESS,
        help=_WRITER_OVERRIDE_HELP,
    )
    grow.add_argument("--book")
    grow.add_argument("--branch")
    grow.set_defaults(func=cmd_architect)

    # The Recruiter's tool suite, and the world suite's ordering: the views first, then the
    # agent that holds them. One parser per view rather than a `--view` flag, for `world`'s
    # reason — an agent reads `--help` to find out what it can do. No `--book` and no
    # `--branch` anywhere in it: a world belongs to a book where a roster does not, and the
    # shorter command line is part of what keeps the allowance narrow. The roster belongs to
    # the installation only where `--roster-database` or LITHARNESS_ROSTER_DATABASE says where
    # that is; without one it belongs to the open database, which is what serial pilot 13 hit
    # when an accepted writer could not reach a fresh book database (stage-0 §151).
    roster_cmd = sub.add_parser(
        "roster", help="the writers this installation holds, or offer it a new one"
    )
    roster_sub = roster_cmd.add_subparsers(dest="view", required=True)

    show_writers = roster_sub.add_parser(
        "show", help="every writer the roster holds, and which shelves have nobody"
    )
    show_writers.add_argument("--name", help="one writer")
    show_writers.add_argument(
        "--status", choices=[status.value for status in writers_domain.RosterStatus]
    )
    show_writers.add_argument(
        "--dossier",
        action="store_true",
        help="include each dossier's prose. Off by default: four one-paragraph exemplars in "
        "the same form are what a model asked to write a fifth will copy, and reading a "
        "colleague's dossier should be a deliberate act",
    )
    show_writers.add_argument("--json", action="store_true", help="ignored; output is JSON")
    show_writers.set_defaults(func=cmd_roster, view="show")

    check_writers = roster_sub.add_parser(
        "check", help="what is wrong by arithmetic; exits 2 when anything is"
    )
    check_writers.add_argument(
        "--dossier",
        help="rehearse this candidate instead of auditing the roster: says what would refuse "
        "it, writes no record, costs nothing, and always exits zero",
    )
    check_writers.add_argument("--dossier-file", dest="dossier_file")
    check_writers.add_argument("--json", action="store_true", help="ignored; output is JSON")
    check_writers.set_defaults(func=cmd_roster, view="check")

    vocabulary = roster_sub.add_parser(
        "vocabulary",
        help="every field a writer declaration takes, and the shape each one has",
    )
    vocabulary.add_argument("--json", action="store_true", help="ignored; output is JSON")
    vocabulary.set_defaults(func=cmd_roster, view="vocabulary")

    declare_writer = roster_sub.add_parser(
        "declare", help="offer the roster a new writer (proposed, never on the roster)"
    )
    declare_writer.add_argument("name")
    declare_writer.add_argument(
        "--dossier",
        help="the whole dossier as one quoted paragraph; no line breaks are needed and none "
        "of the four shipped dossiers has one",
    )
    declare_writer.add_argument(
        "--dossier-file",
        dest="dossier_file",
        help="the dossier as a file, or - for stdin. The operator's path: a Recruiter holds "
        "four `litharness roster ...` commands and nothing else, so it can neither write a "
        "file nor pipe into one",
    )
    declare_writer.add_argument(
        "--interest",
        dest="interests",
        action="append",
        default=[],
        metavar="SUBJECT",
        help="a named subject, once per subject, in order. Order is addressed material: "
        "reordering mints a different writer",
    )
    declare_writer.add_argument(
        "--specialization",
        choices=sorted(roster_mod.SPECIALIZATIONS),
        help="which of the twelve shelves this writer is for. Set for you inside a recruit run",
    )
    declare_writer.add_argument(
        "--shape",
        choices=sorted(roster_mod.SHAPES),
        help="the deliberate dossier form. No default: the forms are a registered arm and a "
        "default would standardise on one of them without anybody deciding to",
    )
    declare_writer.add_argument("--note")
    declare_writer.add_argument("--json", action="store_true")
    declare_writer.set_defaults(func=cmd_roster, view="declare")

    accept_writers = roster_sub.add_parser(
        "accept", help="put declared writers on the roster, as one decision"
    )
    accept_writers.add_argument(
        "names",
        nargs="*",
        metavar="NAME_OR_ID",
        help="which writers, by name or by writer id; every proposed one when you name none. "
        "An id is how you pick between two proposals that share a name, which is what an "
        "edited dossier looks like",
    )
    accept_writers.set_defaults(func=cmd_roster, view="accept")

    refuse_writers = roster_sub.add_parser(
        "refuse", help="turn declared writers down, as one decision with a reason on it"
    )
    refuse_writers.add_argument(
        "names",
        nargs="+",
        metavar="NAME_OR_ID",
        help="which writers, by name or by writer id. **Required, unlike `accept`**: taking "
        "the whole pile is the ordinary end of a recruit run, and binning it is not",
    )
    refuse_writers.add_argument(
        "--reason",
        required=True,
        help="why, in one line, recorded on the decision row. Required: a refused writer "
        "points at a decision, and a decision with an empty reason is a signature on a blank "
        "line. It is stored, never sent to a model",
    )
    refuse_writers.set_defaults(func=cmd_roster_refuse, view="refuse")

    # `recruit_cmd`, not `recruit`: `application/recruiter.py` is imported at the top of this
    # file and a local would shadow it, which is the lesson `arch` already records.
    recruit_cmd = sub.add_parser(
        "recruit",
        help="put the Recruiter on one shelf, holding the roster's read views and declare",
    )
    recruit_cmd.add_argument(
        "--specialization",
        required=True,
        choices=sorted(roster_mod.SPECIALIZATIONS),
        help="which of the twelve shelves to recruit for. One per call: an agent run is "
        "unbounded in turns and this box runs one arm at a time",
    )
    recruit_cmd.add_argument(
        "--shape",
        choices=sorted(roster_mod.SHAPES),
        help="the dossier form to ask for. Defaults to this shelf's own cell in the slate "
        "registered before any draw (`recruiter.SLATE`, and `recruiter.shape_for` reads it), "
        "which is the assignment stage-0 §146 pre-registered. Passing one overrides it and "
        "the override is recorded on the row and in the decision's profile — but a form typed "
        "by hand is a form that can be mistyped, and a mistyped one files a recruit into the "
        "wrong cell of the arm with nothing saying so",
    )
    recruit_cmd.add_argument(
        "--note", help="operator annotation for the decision row. Never sent to the model"
    )
    recruit_cmd.set_defaults(func=cmd_recruit)

    # **Its own verb rather than a flag on `recruit`, and the separation is containment.** A
    # recruit run holds four `litharness roster ...` commands so an agent can write the record
    # it cannot otherwise reach; these two calls return text this process writes down itself, so
    # they hold no allowance at all. A flag would put a paid draw inside a run whose whole
    # allowance argument is about what an agent may type.
    revoice_cmd = sub.add_parser(
        "revoice",
        help="draw a passage as this writer, then re-mint it with its dossier written that way",
    )
    revoice_cmd.add_argument(
        "--writer",
        required=True,
        help="the writer to draw as and re-mint from. Resolved the way `--writer` always is: "
        "the accepted roster first, then the compiled cast. The parent is never edited",
    )
    revoice_cmd.add_argument(
        "--descriptor",
        required=True,
        metavar="PATH",
        help="the derived style descriptor that aims the draw, as a JSON object with the fields "
        "`voice.StyleDescriptor` declares. Required and not defaulted: an unaimed draw is our "
        "own register coming back in a costume, which is the circularity this path exists to "
        "escape. The measurement side's distiller writes one file per serial; see the module "
        "docstring of `application/revoice.py` for where a descriptor legally comes from",
    )
    revoice_cmd.add_argument(
        "--name",
        help="the name the re-minted writer takes. Defaults to the parent's, which is legal for "
        "a proposal and refused at acceptance while the parent is accepted; a compiled cast "
        "writer cannot be re-minted under its own name at all and needs this",
    )
    revoice_cmd.add_argument(
        "--specialization",
        choices=sorted(roster_mod.SPECIALIZATIONS),
        help="inherited from the parent's stored row. Needed only where there is no row to "
        "inherit from, which is every compiled cast writer",
    )
    revoice_cmd.add_argument(
        "--shape",
        choices=sorted(roster_mod.SHAPES),
        help="inherited from the parent's stored row, for the same reason and in the same case. "
        "The re-mint stays in the cell its parent was drafted into, because voice is a second "
        "variable beside the form and not a replacement for it",
    )
    revoice_cmd.add_argument(
        "--note", help="operator annotation. Never sent to a model and not addressed material"
    )
    revoice_cmd.set_defaults(func=cmd_revoice)

    listing = sub.add_parser(
        "listing",
        help="write the listing a reader meets, title it, and stand the book up under it",
    )
    listing.add_argument(
        "--brief",
        default="",
        help="what this book is to be about: a story, a situation, a constraint somebody "
        "cares about. NOT a shelf label — §136 measured the two words `progression fantasy` "
        "outweighing every rule in the prompt. Empty is legitimate and is the control",
    )
    listing.add_argument("--brief-file", help="the brief as a file, or - for stdin")
    listing.add_argument(
        "--writer",
        default=argparse.SUPPRESS,
        help=_WRITER_OVERRIDE_HELP,
    )
    listing.add_argument(
        "--scenes",
        type=int,
        default=0,
        help="create the book too, with this many empty scenes, titled with the title the "
        "loop just wrote. Without it the loop only reports, and moving the title into `new` "
        "is a person's job — which is a human in the production loop (§126)",
    )
    listing.add_argument("--out", type=Path, help="write listing.txt, title.txt and the bundle")
    listing.add_argument(
        "--person",
        choices=("first", "third"),
        default=None,
        help="which grammatical person the book is told in: `first` asks the listing for it "
        "and, with --scenes, seeds the book's locked constraint (see `new --person`)",
    )
    listing.add_argument("--json", action="store_true")
    listing.add_argument(
        "--title-attempts",
        type=int,
        default=3,
        help="how many titles to try before giving up on finding a free one",
    )
    listing.add_argument(
        "--no-title-check",
        action="store_true",
        help="do not look up whether the title is already in use. The lookup costs a call "
        "with web search behind it; skipping it means nobody has checked",
    )
    listing.add_argument(
        "--no-title-to-readers",
        action="store_true",
        help="screen the listing without its title, which is what every round before a title "
        "existed measured, and is the control arm for whether the title is what unstuck the "
        "browsing pool",
    )
    listing.add_argument(
        "--rivals",
        help="a JSON list of published books to spend the reading slot on instead: each with "
        "title, listing, rating, genre and optionally ratings. Every row must clear "
        "`domain/rivals.admit` — above four stars, in one of this readership's genres — and "
        "one bad row refuses the file. Without it there is no named competitor, which is the "
        "control arm and is what every round before 2026-08-26 measured",
    )
    listing.add_argument(
        "--concept",
        type=Path,
        help="write the listing from this settled concept (`concept.json` from `litharness "
        "concept`), shown under the brief as material; with --scenes the book carries it "
        "(see `new --concept`)",
    )
    listing.add_argument("--book", help="book id, when --scenes creates one")
    listing.add_argument("--branch", help="branch id, when --scenes creates one")
    listing.set_defaults(func=cmd_listing)

    concept = sub.add_parser(
        "concept",
        help="invent the book before its listing: one writer, one concept, written to disk "
        "for `listing --concept` (stage-0 §197)",
    )
    concept.add_argument(
        "--brief",
        default="",
        help="what this book is to be about: a story, a situation, a constraint somebody "
        "cares about; never a shelf label (§136). Empty is legitimate",
    )
    concept.add_argument("--brief-file", help="the brief as a file, or - for stdin")
    concept.add_argument(
        "--writer",
        default=argparse.SUPPRESS,
        help=_WRITER_OVERRIDE_HELP,
    )
    concept.add_argument(
        "--scenes",
        type=int,
        default=SerialShape().scenes_per_arc,
        help="how many scenes the first arc has, so the debts are due by scene numbers the "
        "outline can schedule (default: one arc)",
    )
    concept.add_argument(
        "--person",
        choices=("first", "third"),
        default=None,
        help="which grammatical person the book is told in; `first` asks for it as a position",
    )
    concept.add_argument("--out", type=Path, help="write concept.json and concept.txt here")
    concept.add_argument("--json", action="store_true")
    concept.set_defaults(func=cmd_concept)

    cover = sub.add_parser(
        "cover",
        help="generate several cover options and finish each at Royal Road's 400x600 size",
    )
    cover.add_argument(
        "--out",
        type=Path,
        help="override the default book-library/<book>/covers output directory (or "
        "book-library/<book>/volumes/VolumeN/covers with --volume)",
    )
    cover.add_argument(
        "--bundle",
        type=Path,
        help="listing.json from `litharness listing`; supplies title and story description",
    )
    cover.add_argument("--title", help="publication title; overrides the bundle title")
    cover.add_argument(
        "--author",
        default="Skulitom",
        help="publication name at the bottom (default: Skulitom)",
    )
    description = cover.add_mutually_exclusive_group()
    description.add_argument(
        "--description",
        help="story context for the art; overrides the listing in --bundle",
    )
    description.add_argument(
        "--description-file",
        help="story context as UTF-8 text, or - for stdin; overrides --bundle",
    )
    cover.add_argument(
        "--art-direction",
        default="",
        help="optional visual constraint shared by every variant (palette, motif, exclusions)",
    )
    cover.add_argument(
        "--variants",
        type=int,
        help=f"independent Codex generations (default {covers.DEFAULT_VARIANTS}, max "
        f"{covers.MAX_VARIANTS}); ignored when --art supplies the set",
    )
    cover.add_argument(
        "--art",
        action="append",
        type=Path,
        help="finish existing art instead of calling Codex; repeat for several options",
    )
    cover.add_argument(
        "--reference",
        action="append",
        type=Path,
        help="visual reference attached to every Codex generation; repeat as needed",
    )
    cover.add_argument(
        "--font",
        type=Path,
        help="TrueType/OpenType font for reproducible publication typography",
    )
    cover.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="seconds allowed for each Codex image-generation session (default: 900)",
    )
    cover.add_argument(
        "--force",
        action="store_true",
        help="replace only the named cover artifacts when they already exist",
    )
    cover.add_argument("--book", help="book id; defaults to the only branch in the database")
    cover.add_argument("--branch", help="branch id; defaults to the only matching branch")
    cover.add_argument(
        "--volume",
        type=int,
        help="target this release volume. It keeps the same canonical book and writes under "
        "volumes/VolumeN/covers; omit for a serial-level cover",
    )
    cover.set_defaults(func=cmd_cover)

    mechanism = sub.add_parser(
        "reader-mechanism",
        help="inspect or change the evidence-gated chapter-reader mechanism",
    )
    mechanism_actions = mechanism.add_subparsers(
        dest="mechanism_action", required=True
    )
    mechanism_status = mechanism_actions.add_parser(
        "status", help="show the current version and its qualification evidence"
    )
    mechanism_status.add_argument("--json", action="store_true")
    mechanism_status.set_defaults(func=cmd_reader_mechanism)
    mechanism_qualify = mechanism_actions.add_parser(
        "qualify", help="register a qualified version from a complete evidence artifact"
    )
    mechanism_qualify.add_argument("--evidence", type=Path, required=True)
    mechanism_qualify.add_argument("--json", action="store_true")
    mechanism_qualify.set_defaults(func=cmd_reader_mechanism)
    mechanism_withdraw = mechanism_actions.add_parser(
        "withdraw", help="make withdrawal current and close queued/future steering"
    )
    mechanism_withdraw.add_argument("--reason", required=True)
    mechanism_withdraw.add_argument("--json", action="store_true")
    mechanism_withdraw.set_defaults(func=cmd_reader_mechanism)

    evidence_audit = sub.add_parser(
        "reader-evidence-audit",
        help="count code-certifiable scene interventions without making a model call",
    )
    evidence_audit.add_argument("--book")
    evidence_audit.add_argument("--branch")
    evidence_audit.add_argument("--out", type=Path)
    evidence_audit.add_argument("--json", action="store_true")
    evidence_audit.set_defaults(func=cmd_reader_evidence_audit)

    read = sub.add_parser("readers", help="put the simulated readership on a drafted scene")
    read.add_argument("--scene", help="a scene logical id; the latest drafted one by default")
    read.add_argument(
        "--history",
        action="store_true",
        help="inspect versioned checkpoint observations and editorial interventions without "
        "making a model call",
    )
    read.add_argument(
        "--rivals",
        help="a JSON list of published books to spend the reading slot on instead: each with "
        "title, listing, rating, genre and optionally ratings. Every row must clear "
        "`domain/rivals.admit` — above four stars, in one of this readership's genres — and "
        "one bad row refuses the file. Without it there is no named competitor, which is the "
        "control arm and is what every round before 2026-08-26 measured",
    )

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

    replan = sub.add_parser("replan", help="reissue still-draftable beats under a fresh plan epoch")
    replan.add_argument("--book")
    replan.add_argument("--branch")
    replan.add_argument("--reason", help="recorded on the PlanChanged event")
    replan.set_defaults(func=cmd_replan)

    backup = sub.add_parser("backup", help="online backup (safe while ticking)")
    backup.add_argument("destination", type=Path)
    backup.set_defaults(func=cmd_backup)

    export = sub.add_parser("export", help="a reading copy of the book as it stands, gaps and all")
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
    except (
        OSError,
        FileExistsError,
        ValueError,
        sqlite3.Error,
        directors_domain.IllegalBrief,
    ) as error:
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
        #
        # **`IllegalBrief` is here for the same reason and was found the same way.** It is a
        # bare `Exception`, so once a dossier could live in a database rather than only in
        # source, `litharness prompts --writer <name>` on a stored dossier that a later-
        # registered prose axis has made illegal escaped as a traceback and exit 1 — while
        # `roster check` reported the same row as a fault and exited 2. A refusal this system
        # writes itself must not reach an operator as a stack trace.
        print(f"litharness: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FAULT


if __name__ == "__main__":  # pragma: no cover - exercised via __main__.py
    raise SystemExit(main())
