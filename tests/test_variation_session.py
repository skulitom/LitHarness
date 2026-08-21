"""The bounded variation session: many attempts, one commit, and every ceiling separate."""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.evaluation import EvaluationRequest
from litharness.application.repair import (
    EVALUATE_REVISION,
    REPAIR_FINDING,
    make_evaluation_handler,
    repair_job_for,
)
from litharness.application.variation import (
    ACTION_SCHEMA,
    VARIATION_STEP,
    make_variation_repair_handler,
    make_variation_step_handler,
    variation_step_job,
)
from litharness.domain.budget import BudgetPolicy
from litharness.domain.findings import Status
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.patch import Veto
from litharness.domain.policy import Outcome
from litharness.domain.variation import (
    REPEATED_FAILURE_LIMIT,
    ActionKind,
    AttemptOutcome,
    MalformedAction,
    SessionLimits,
    SessionOutcome,
    SessionStatus,
    VariationObjective,
    parse_action,
    session_id_for,
)
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision
from tests.test_draft import START
from tests.test_repair_workflow import FINDING_ID, LocatedNameEvaluator

#: The scene the fixture book opens with, and the four characters the planted finding locates.
#: Every proposal in this module replaces exactly that span, because a finding licenses a span
#: and never a rewrite.
ORIGINAL_NAME = "Rook"
CORRECTED_NAME = "Mara"

#: Long enough that the repaired node exceeds `PatchPolicy.max_length_ratio` against the
#: ~70-character scene, so the shape gate refuses it for `LENGTH_MOVEMENT` rather than for
#: anything about what it says. Checked rather than assumed: the assertion in
#: `test_every_attempt_is_recorded_including_the_ones_a_gate_refused` reads the stored veto.
TOO_LONG = "Mara " * 40


def day_of(now: float) -> str:
    """The day key `spend_on` reads, derived the way the handlers derive it."""
    return datetime.fromtimestamp(now, tz=UTC).date().isoformat()


def action(kind: ActionKind, **fields: object) -> str:
    return json.dumps({"action": kind.value, **fields}, sort_keys=True)


def propose(replacement: str, strategy: str = "local_patch") -> str:
    return action(ActionKind.PROPOSE_CANDIDATE, replacement=replacement, strategy=strategy)


@pytest.fixture
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "variation.db")


def seed(store: SqliteStore) -> str:
    """A committed book with one located, blocking, span-carrying complaint against scene 1."""
    revision = make_revision()
    store.commit_revision(revision, created_at="2026-08-21T00:00:00Z")
    findings = LocatedNameEvaluator().evaluate(
        EvaluationRequest(revision=revision, logical_id="scene-1")
    ).findings
    assert len(findings) == 1
    store.record_findings(
        BOOK_ID,
        BRANCH_ID,
        findings,
        created_at="2026-08-21T00:00:00Z",
        revision_id=revision.revision_id,
    )
    return revision.revision_id




def enqueue_repair(store: SqliteStore) -> str:
    finding = store.load_finding(FINDING_ID)
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    job = repair_job_for(
        finding,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        revision_id=head.revision_id,
        repair_depth=1,
    )
    assert job is not None
    assert store.enqueue(job)
    return job.job_id


def build(
    store: SqliteStore,
    responses: list[str],
    *,
    limits: SessionLimits | None = None,
    budget: BudgetPolicy | None = None,
    evaluator: bool = False,
) -> tuple[Conductor, FakeProvider]:
    provider = FakeProvider(responses=list(responses))
    registry = ProviderRegistry(provider)
    handlers = {
        REPAIR_FINDING: make_variation_repair_handler(
            registry, store, PROJECT_ID, limits=limits, budget=budget
        ),
        VARIATION_STEP: make_variation_step_handler(
            registry, store, PROJECT_ID, budget=budget
        ),
    }
    if evaluator:
        handlers[EVALUATE_REVISION] = make_evaluation_handler(
            LocatedNameEvaluator(), store, PROJECT_ID
        )
    return (
        Conductor(
            store=store,
            holder="worker-a",
            project_id=PROJECT_ID,
            registry=registry,
            handlers=handlers,
        ),
        provider,
    )


def session_of(store: SqliteStore, job_id: str):
    session = store.variation_session(
        session_id_for(job_id, VariationObjective.CANDIDATE_REPAIR)
    )
    assert session is not None
    return session


# --- the happy path -------------------------------------------------------------------


def test_a_session_commits_the_first_mechanically_valid_candidate(
    store: SqliteStore,
) -> None:
    """Propose, evaluate, commit — three ticks, three actions, one revision."""
    base = seed(store)
    job_id = enqueue_repair(store)
    conductor, provider = build(
        store,
        [
            propose(CORRECTED_NAME),
            action(ActionKind.EVALUATE_CANDIDATE),
            action(ActionKind.COMMIT),
        ],
        evaluator=True,
    )

    assert conductor.tick(START).outcome is TickOutcome.RAN_JOB
    assert conductor.tick(START + 1).outcome is TickOutcome.RAN_JOB
    assert conductor.tick(START + 2).outcome is TickOutcome.RAN_JOB

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    assert head.revision_id != base
    assert head.node("scene-1").content.startswith(CORRECTED_NAME)
    assert provider.calls == 3

    session = session_of(store, job_id)
    assert session.status is SessionStatus.CLOSED
    assert session.outcome is SessionOutcome.COMMITTED
    assert (session.steps, session.provider_calls, session.evaluations) == (3, 3, 1)

    attempts = store.variation_attempts(session.session_id)
    assert [attempt.outcome for attempt in attempts] == [AttemptOutcome.COMMITTED]
    assert attempts[0].strategy == "local_patch"

    # The acceptance is attributable exactly as any other accepted revision is.
    decision = store.decision_for_revision(head.revision_id)
    assert decision is not None and decision.outcome is Outcome.ACCEPT
    assert decision.resulting_revision_id == head.revision_id

    # And the same verification the fixed path schedules, at the same depth.
    queued = store.jobs_by_status(JobStatus.QUEUED)
    assert [job.job_kind for job in queued] == [EVALUATE_REVISION]
    assert queued[0].payload["verification_of_finding_id"] == FINDING_ID

    assert conductor.tick(START + 3).outcome is TickOutcome.RAN_JOB
    assert store.load_finding(FINDING_ID).status is Status.FIXED
    assert store.verify_integrity() == 2


def test_a_refused_candidate_is_recorded_and_the_session_tries_again(
    store: SqliteStore,
) -> None:
    """The refusal comes back as diagnostics, and the next proposal commits."""
    seed(store)
    job_id = enqueue_repair(store)
    conductor, _ = build(
        store,
        [
            propose(TOO_LONG, strategy="structural"),
            action(ActionKind.EVALUATE_CANDIDATE),
            propose(CORRECTED_NAME),
            action(ActionKind.EVALUATE_CANDIDATE),
            action(ActionKind.COMMIT),
        ],
    )
    for offset in range(5):
        assert conductor.tick(START + offset).outcome is TickOutcome.RAN_JOB

    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.COMMITTED
    attempts = store.variation_attempts(session.session_id)
    assert [attempt.outcome for attempt in attempts] == [
        AttemptOutcome.REJECTED_GATE,
        AttemptOutcome.COMMITTED,
    ]
    assert [attempt.strategy for attempt in attempts] == ["structural", "local_patch"]


def test_every_attempt_is_recorded_including_the_ones_a_gate_refused(
    store: SqliteStore,
) -> None:
    """The full gate vector is stored, not a summary — passing gates included."""
    seed(store)
    job_id = enqueue_repair(store)
    conductor, _ = build(
        store, [propose(TOO_LONG), action(ActionKind.EVALUATE_CANDIDATE)]
    )
    conductor.tick(START)
    conductor.tick(START + 1)

    (attempt,) = store.variation_attempts(
        session_of(store, job_id).session_id
    )
    assert attempt.outcome is AttemptOutcome.REJECTED_GATE
    assert attempt.evaluation, "the vector is stored, not just a verdict"
    assert Veto.LENGTH_MOVEMENT in attempt.evaluation[0].vetoes
    assert "length_movement" in attempt.diagnostics
    assert attempt.evaluations == 1
    assert not attempt.gates_passed
    # The patch is retrievable exactly as proposed, by reference rather than inline.
    stored = store.variation_patch(attempt.patch_digest)
    assert stored is not None
    assert stored["ops"][0]["new_text"] == TOO_LONG


def test_a_commit_request_is_refused_when_no_candidate_has_passed_the_gates(
    store: SqliteStore,
) -> None:
    """The mediated surface enforces the precondition; the manuscript never moves."""
    base = seed(store)
    job_id = enqueue_repair(store)
    conductor, _ = build(
        store,
        [
            propose(TOO_LONG),
            action(ActionKind.EVALUATE_CANDIDATE),
            action(ActionKind.COMMIT),
        ],
    )
    for offset in range(3):
        assert conductor.tick(START + offset).outcome is TickOutcome.RAN_JOB

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == base
    session = session_of(store, job_id)
    assert session.is_open, "a refused action bounds the session, it does not end it"
    assert session.steps == 3


# --- stalls ---------------------------------------------------------------------------


def test_the_same_patch_proposed_twice_closes_the_session(store: SqliteStore) -> None:
    """The gates are pure, so re-running them cannot change the verdict."""
    seed(store)
    job_id = enqueue_repair(store)
    conductor, provider = build(
        store,
        [
            propose(TOO_LONG),
            action(ActionKind.EVALUATE_CANDIDATE),
            propose(TOO_LONG),
        ],
    )
    for offset in range(3):
        conductor.tick(START + offset)
    stalled = conductor.tick(START + 3)

    assert stalled.outcome is TickOutcome.JOB_PARKED
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.STALLED_REPEAT_PATCH
    assert provider.calls == 3, "the stall is detected in front of the fourth call"


def test_repeated_identical_gate_refusals_close_the_session(store: SqliteStore) -> None:
    """Three refusals with one signature is evidence about the situation, not the output."""
    seed(store)
    job_id = enqueue_repair(store)
    variants = [f"{TOO_LONG}{index}" for index in range(REPEATED_FAILURE_LIMIT)]
    script: list[str] = []
    for variant in variants:
        script += [propose(variant), action(ActionKind.EVALUATE_CANDIDATE)]
    conductor, provider = build(store, script)

    for offset in range(len(script)):
        conductor.tick(START + offset)
    stalled = conductor.tick(START + len(script))

    assert stalled.outcome is TickOutcome.JOB_PARKED
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.STALLED_REPEATED_GATE
    assert provider.calls == len(script)
    assert len(store.variation_attempts(session.session_id)) == REPEATED_FAILURE_LIMIT


def test_unusable_responses_are_counted_and_bounded_rather_than_failing_the_job(
    store: SqliteStore,
) -> None:
    """A model that answers badly costs calls, not the unit's Conductor attempts."""
    seed(store)
    job_id = enqueue_repair(store)
    script = [json.dumps({"action": "rewrite_everything"})] * REPEATED_FAILURE_LIMIT
    conductor, _ = build(store, script)

    for offset in range(REPEATED_FAILURE_LIMIT):
        assert conductor.tick(START + offset).outcome is TickOutcome.RAN_JOB
    stalled = conductor.tick(START + REPEATED_FAILURE_LIMIT)

    assert stalled.outcome is TickOutcome.JOB_PARKED
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.STALLED_MALFORMED
    assert session.malformed == REPEATED_FAILURE_LIMIT
    assert session.steps == 0, "an unusable response executes no action"
    assert session.provider_calls == REPEATED_FAILURE_LIMIT


# --- ceilings -------------------------------------------------------------------------


def test_a_tripped_ceiling_parks_the_session_and_names_which_one(
    store: SqliteStore,
) -> None:
    seed(store)
    job_id = enqueue_repair(store)
    limits = SessionLimits(max_steps=3, max_provider_calls=4, max_evaluations=1)
    conductor, provider = build(
        store, [action(ActionKind.INSPECT_LINEAGE)] * 3, limits=limits
    )

    for offset in range(3):
        assert conductor.tick(START + offset).outcome is TickOutcome.RAN_JOB
    refused = conductor.tick(START + 3)

    assert refused.outcome is TickOutcome.JOB_PARKED
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.REFUSED_LIMIT
    assert session.outcome_detail is not None
    assert session.outcome_detail.startswith("max_steps")
    assert provider.calls == 3, "the ceiling is checked in front of the call"
    assert session.lineage_inspections == 3

    # Parked, not poisoned, and the exception queue names the ceiling.
    step_job = store.jobs_by_status(JobStatus.PARKED)
    assert [job.job_kind for job in step_job] == [VARIATION_STEP]
    assert any(
        "max_steps" in record.summary for record in store.open_exceptions()
    ), "a refusal an operator can act on reaches the queue an operator reads"


def test_the_wall_clock_ceiling_runs_off_the_injected_clock(store: SqliteStore) -> None:
    seed(store)
    job_id = enqueue_repair(store)
    limits = SessionLimits(max_wall_seconds=60.0)
    conductor, _ = build(store, [action(ActionKind.INSPECT_LINEAGE)], limits=limits)

    assert conductor.tick(START).outcome is TickOutcome.RAN_JOB
    late = conductor.tick(START + 3600)

    assert late.outcome is TickOutcome.JOB_PARKED
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.REFUSED_LIMIT
    assert session.outcome_detail is not None
    assert session.outcome_detail.startswith("max_wall_seconds")


def test_the_day_budget_refuses_in_front_of_the_first_call(store: SqliteStore) -> None:
    """The session's own ceilings do not replace the governor that bounds the day."""
    seed(store)
    job_id = enqueue_repair(store)
    conductor, provider = build(
        store,
        [propose(CORRECTED_NAME)],
        budget=BudgetPolicy(max_tokens_per_operation=1),
    )

    refused = conductor.tick(START)

    assert refused.outcome is TickOutcome.JOB_PARKED
    assert provider.calls == 0
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.REFUSED_BUDGET
    assert session.provider_calls == 0
    # The attempt is given back, because nothing was generated (`refused_before_work`).
    assert store.load_job(store.jobs_by_status(JobStatus.PARKED)[0].job_id).attempts == 0


def test_the_session_spend_reaches_the_budget_governor(store: SqliteStore) -> None:
    """Every step's call is on a decision row, because `spend_on` sums nothing else.

    The failure this pins is silent and expensive: a session makes one provider call per
    action, and a loop whose calls never reached `policy_decisions` would spend a dozen of
    them per finding while the day's budget gate reported the day untouched.
    """
    seed(store)
    enqueue_repair(store)
    conductor, _ = build(store, [action(ActionKind.INSPECT_LINEAGE)] * 2)
    conductor.tick(START)
    conductor.tick(START + 1)

    spend = store.spend_on(day_of(START))
    assert spend.invocations == 2
    assert spend.tokens > 0


# --- durability -----------------------------------------------------------------------


def test_a_session_resumes_across_a_restart_because_its_state_is_rows(
    store: SqliteStore,
) -> None:
    """A fresh Conductor with fresh handlers continues the session it did not open."""
    seed(store)
    job_id = enqueue_repair(store)
    first, _ = build(store, [propose(CORRECTED_NAME)])
    assert first.tick(START).outcome is TickOutcome.RAN_JOB

    second, _ = build(
        store, [action(ActionKind.EVALUATE_CANDIDATE), action(ActionKind.COMMIT)]
    )
    assert second.tick(START + 1).outcome is TickOutcome.RAN_JOB
    assert second.tick(START + 2).outcome is TickOutcome.RAN_JOB

    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.COMMITTED
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    assert head.node("scene-1").content.startswith(CORRECTED_NAME)


def test_a_replayed_step_does_not_re_spend_its_provider_call(store: SqliteStore) -> None:
    """The recorded ACCEPT is the guard a reclaimed lease meets.

    A holder that dies after `commit_variation_step` leaves the step job RUNNING; the lease
    expires, `reclaim_expired` requeues it, and the handler runs again on work that is already
    recorded. Without the guard that second run pays for the same action twice.
    """
    seed(store)
    job_id = enqueue_repair(store)
    conductor, provider = build(store, [action(ActionKind.INSPECT_LINEAGE)])
    assert conductor.tick(START).outcome is TickOutcome.RAN_JOB
    assert provider.calls == 1

    opening = store.load_job(job_id)
    assert opening.status is JobStatus.SUCCEEDED
    exhausted = FakeProvider(responses=[])
    replay = make_variation_repair_handler(
        ProviderRegistry(exhausted), store, PROJECT_ID
    )
    assert replay(opening, START + 1) == ()
    assert exhausted.calls == 0
    assert session_of(store, job_id).provider_calls == 1


def test_a_closed_session_ignores_a_step_job_left_behind(store: SqliteStore) -> None:
    seed(store)
    job_id = enqueue_repair(store)
    conductor, _ = build(
        store,
        [
            propose(CORRECTED_NAME),
            action(ActionKind.EVALUATE_CANDIDATE),
            action(ActionKind.COMMIT),
        ],
    )
    for offset in range(3):
        conductor.tick(START + offset)
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.COMMITTED

    provider = FakeProvider(responses=[])
    handler = make_variation_step_handler(
        ProviderRegistry(provider), store, PROJECT_ID
    )
    left_over = variation_step_payload(session.session_id)
    assert handler(left_over, START + 9) == ()
    assert provider.calls == 0


def variation_step_payload(session_id: str) -> Job:
    """A step job for a session, minted the way the session mints its own."""
    return variation_step_job(
        session_id=session_id,
        ordinal=99,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-1",
        finding_id=FINDING_ID,
        repair_depth=1,
    )


# --- knowledge ------------------------------------------------------------------------


def test_knowledge_is_derived_from_repeated_refusals_and_records_its_consultation(
    store: SqliteStore,
) -> None:
    """Two identical refusals mint one evidence-linked claim; reading it is recorded."""
    seed(store)
    job_id = enqueue_repair(store)
    conductor, _ = build(
        store,
        [
            propose(TOO_LONG + "a"),
            action(ActionKind.EVALUATE_CANDIDATE),
            propose(TOO_LONG + "b"),
            action(ActionKind.EVALUATE_CANDIDATE),
            action(ActionKind.CONSULT_KNOWLEDGE),
        ],
    )
    for offset in range(5):
        conductor.tick(START + offset)

    session = session_of(store, job_id)
    items = store.knowledge_items(target_key=session.target_key)
    assert len(items) == 1
    item = items[0]
    assert item.veto == Veto.LENGTH_MOVEMENT.value
    assert item.observations == 2
    assert len(item.evidence) == 2
    attempt_ids = {
        attempt.attempt_id for attempt in store.variation_attempts(session.session_id)
    }
    assert set(item.evidence) <= attempt_ids, "evidence links resolve to real attempts"
    assert item.consultations == 1
    assert session.consulted_item_ids == (item.item_id,)


# --- the licence ----------------------------------------------------------------------


def test_a_lapsed_licence_closes_the_session_without_touching_the_manuscript(
    store: SqliteStore,
) -> None:
    base = seed(store)
    job_id = enqueue_repair(store)
    store.set_finding_status(FINDING_ID, Status.FALSE_POSITIVE)
    conductor, provider = build(store, [propose(CORRECTED_NAME)])

    result = conductor.tick(START)

    assert result.outcome is TickOutcome.RAN_JOB, "a moot unit is not a failed one"
    assert provider.calls == 0
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.STALE_BASE
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == base


def test_stop_ends_the_session_and_leaves_the_complaint_standing(
    store: SqliteStore,
) -> None:
    base = seed(store)
    job_id = enqueue_repair(store)
    conductor, _ = build(
        store, [action(ActionKind.STOP, reason="the span cannot be repaired in place")]
    )

    stopped = conductor.tick(START)

    assert stopped.outcome is TickOutcome.JOB_PARKED
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.STOPPED
    assert session.outcome_detail == "the span cannot be repaired in place"
    assert store.load_finding(FINDING_ID).status is Status.OPEN
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == base


# --- the mediated surface -------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"action": "shell"},
        {"action": "propose_candidate"},
        {"action": "propose_candidate", "replacement": ""},
    ],
)
def test_the_mediated_surface_refuses_anything_it_does_not_name(payload) -> None:
    with pytest.raises(MalformedAction):
        parse_action(payload)


def test_the_surface_is_exactly_six_actions_and_the_schema_says_so() -> None:
    assert len(ActionKind) == 6
    assert ACTION_SCHEMA["properties"]["action"]["enum"] == [
        member.value for member in ActionKind
    ]


def test_the_variation_loop_imports_no_selection_machinery() -> None:
    """A structural guarantee that the loop cannot order candidates by anything.

    The session commits the first mechanically valid candidate. `select_winner` and the
    pairwise preference engine are the two places in this package that rank prose, and a loop
    that grew an import of either would be one call away from choosing between valid
    candidates — which no instrument here is entitled to do. Cheaper to forbid the import than
    to review every future edit for the call.
    """
    banned = {"litharness.domain.candidates", "litharness.domain.preference"}
    for module in ("domain/variation.py", "application/variation.py"):
        path = Path(__file__).parents[1] / "src" / "litharness" / module
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not imported & banned, f"{module} imports selection machinery"


# --- the ceilings, as declared --------------------------------------------------------


def test_a_ceiling_that_could_not_bind_is_refused_at_construction() -> None:
    """The declared-bars rule, enforced where the bar is declared."""
    with pytest.raises(ValueError, match="three steps"):
        SessionLimits(max_steps=2)
    with pytest.raises(ValueError, match="max_steps unreachable"):
        SessionLimits(max_steps=12, max_provider_calls=8)
    with pytest.raises(ValueError, match="bound anything"):
        SessionLimits(max_evaluations=0)
    with pytest.raises(ValueError, match="bound anything"):
        SessionLimits(max_wall_seconds=0.0)
    with pytest.raises(ValueError, match="refuses every session"):
        SessionLimits(max_cost_usd=0.0)


def test_the_defaults_can_reach_a_commit_and_can_also_stop_one() -> None:
    limits = SessionLimits()
    assert limits.max_steps >= 3, "propose, evaluate, commit"
    assert limits.max_provider_calls >= limits.max_steps
    assert limits.max_evaluations < limits.max_steps, "a gate ceiling that can bind first"
    assert limits.max_cost_usd is None, "dollars are offered, never relied on"


# --- the comparison, pinned so its numbers stay reproducible ---------------------------


def test_the_comparison_harness_hands_both_arms_the_same_generator() -> None:
    """The reported result is a mechanism comparison, and this is what makes it one.

    `plan/variation-session.md` reports that the session bought no extra commits and cost
    2.25x the calls. That number only means anything if both arms drew the same replacements
    in the same order, so the property is pinned here rather than left to the reader of a
    tool nobody runs twice: the fixed path commits the first passing rung in one call, and the
    session commits the same rung through propose, evaluate and commit.
    """
    from tools.variation_repair_comparison import Case, run_case

    case = Case("sample", "scene-1", good_at=1)
    fixed = run_case(case, "fixed", budget=BudgetPolicy())
    session = run_case(case, "session", budget=BudgetPolicy())

    assert fixed.committed and session.committed
    assert (fixed.provider_calls, fixed.gate_runs) == (1, 1)
    assert (session.provider_calls, session.gate_runs) == (3, 2)
    assert session.outcome == "committed"


def test_the_stall_detector_stops_the_session_where_the_fixed_path_poisons() -> None:
    """Both arms give up at three, and the report says why that is not a coincidence.

    Every mechanical refusal reachable from a replacement string on these cases carries one
    signature, so `REPEATED_FAILURE_LIMIT` stops the session on the same attempt `max_attempts`
    stops the fixed path. It is the reason the session reaches no rung the fixed path cannot,
    and a change to either constant should fail here and be argued rather than absorbed.
    """
    from tools.variation_repair_comparison import Case, run_case

    case = Case("sample", "scene-1", good_at=4)
    fixed = run_case(case, "fixed", budget=BudgetPolicy())
    session = run_case(case, "session", budget=BudgetPolicy())

    assert not fixed.committed and not session.committed
    assert session.outcome == "stalled_repeated_gate"
    assert fixed.failures == session.failures == REPEATED_FAILURE_LIMIT


def test_an_unscripted_provider_exhausts_a_ceiling_rather_than_spinning(
    store: SqliteStore,
) -> None:
    """§4.2's failure mode, checked against the provider a model-free run actually uses.

    The deterministic fake synthesises a minimal object satisfying the schema, which for the
    action schema means the first enum member on every call, forever. A loop that chained
    itself on that answer would tick until somebody noticed. It exhausts `max_steps` instead
    and parks with the ceiling named.
    """
    seed(store)
    job_id = enqueue_repair(store)
    provider = FakeProvider()
    registry = ProviderRegistry(provider)
    conductor = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        handlers={
            REPAIR_FINDING: make_variation_repair_handler(registry, store, PROJECT_ID),
            VARIATION_STEP: make_variation_step_handler(registry, store, PROJECT_ID),
        },
    )

    outcomes = [conductor.tick(START + offset).outcome for offset in range(30)]

    assert TickOutcome.NO_WORK in outcomes, "the loop stops on its own"
    session = session_of(store, job_id)
    assert session.outcome is SessionOutcome.REFUSED_LIMIT
    assert session.steps == SessionLimits().max_steps
    assert provider.calls == SessionLimits().max_steps
