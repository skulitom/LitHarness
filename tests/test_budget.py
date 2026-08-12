"""Budget ceilings: the fourth gate of §4.2, and the half of §19 Economics that was missing.

The distinction under test throughout is *metered* versus *enforced*. Every policy decision
already recorded invocations and tokens; nothing stopped anything. A system that measures
its spend and cannot refuse is instrumented, not budgeted, and §18 keeps budget enforcement
absolutely.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.domain.budget import (
    DEFAULT_TAX_TOKENS,
    HARNESS_TAX_TOKENS,
    BudgetPolicy,
    Spend,
    check,
    projected_tokens,
)
from litharness.domain.events import EventType
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.policy import GateKind, Outcome, PolicyDecision
from tests.conftest import PROJECT_ID
from tests.test_draft import PROSE, START, blank_revision, registry_with

UNLIMITED = BudgetPolicy(
    max_tokens_per_operation=None,
    max_tokens_per_day=None,
    max_invocations_per_day=None,
)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "budget.db")


# --- projection ----------------------------------------------------------------------


def test_the_harness_tax_dominates_a_small_call() -> None:
    """The §15 measurement, and why invocations are a ceiling in their own right: a call
    costs ~24k input tokens for `claude -p` before the prompt is even considered."""
    tiny = projected_tokens("claude_code", prompt_chars=40, max_output_tokens=100)
    assert tiny > HARNESS_TAX_TOKENS["claude_code"]
    assert tiny - HARNESS_TAX_TOKENS["claude_code"] < 200


def test_an_unknown_provider_is_assumed_expensive() -> None:
    """Guessing low is the failure that spends money you had refused, so an unrecognised
    provider makes the budget more cautious rather than less."""
    assert projected_tokens("something_new", 0, 0) == DEFAULT_TAX_TOKENS
    assert projected_tokens("ollama", 0, 0) == 0


# --- the ceilings --------------------------------------------------------------------


def test_a_call_within_every_ceiling_is_allowed() -> None:
    verdict = check(
        BudgetPolicy(), Spend(), provider="ollama", prompt_chars=400, max_output_tokens=1000
    )
    assert verdict.allowed and verdict.ceiling is None


def test_an_oversized_single_operation_is_refused() -> None:
    verdict = check(
        BudgetPolicy(max_tokens_per_operation=1000),
        Spend(),
        provider="claude_code",
        prompt_chars=0,
        max_output_tokens=0,
    )
    assert not verdict.allowed
    assert verdict.ceiling == "max_tokens_per_operation"


def test_the_invocation_ceiling_refuses_where_tokens_would_not() -> None:
    """The ceiling token counts cannot express. A thousand tiny calls can cost more than a
    handful of long ones and look cheaper on every token report."""
    policy = BudgetPolicy(max_invocations_per_day=10, max_tokens_per_day=None)
    verdict = check(
        policy,
        Spend(invocations=10, tokens=0),
        provider="ollama",
        prompt_chars=1,
        max_output_tokens=1,
    )
    assert not verdict.allowed
    assert verdict.ceiling == "max_invocations_per_day"


def test_the_daily_token_ceiling_counts_the_projection_not_just_the_past() -> None:
    """A ceiling that only looks backwards is crossed by the very call it was asked to
    judge — the one failure mode that makes the whole gate pointless."""
    policy = BudgetPolicy(max_tokens_per_day=30_000, max_invocations_per_day=None)
    verdict = check(
        policy,
        Spend(tokens=20_000),
        provider="claude_code",
        prompt_chars=0,
        max_output_tokens=0,
    )
    assert not verdict.allowed
    assert verdict.ceiling == "max_tokens_per_day"


def test_dollars_are_never_the_only_ceiling() -> None:
    """`claude -p` on a subscription reports no cost and Ollama's cost is hardware time, so
    a dollars-only budget fails open on exactly the providers used by default."""
    policy = BudgetPolicy(
        max_tokens_per_operation=None,
        max_tokens_per_day=None,
        max_invocations_per_day=None,
        max_cost_usd_per_day=10.0,
    )
    generous = check(
        policy,
        Spend(tokens=10**9, cost_usd=0.0),
        provider="claude_code",
        prompt_chars=0,
        max_output_tokens=0,
    )
    assert generous.allowed, "this is the fail-open case the token ceilings exist to cover"

    exhausted = check(
        policy, Spend(cost_usd=10.0), provider="ollama", prompt_chars=0, max_output_tokens=0
    )
    assert not exhausted.allowed and exhausted.ceiling == "max_cost_usd_per_day"


# --- enforcement in the loop ---------------------------------------------------------


def seeded(store: SqliteStore) -> None:
    revision = blank_revision()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    payload = {
        "revision_id": revision.revision_id,
        "logical_id": "scene-1",
        "prompt": "Draft the opening scene.",
    }
    store.enqueue(
        Job(
            job_id="draft-1",
            job_kind=SCENE_DRAFT,
            payload=payload,
            input_digest=input_digest_for(payload),
        )
    )


def conductor_for(store: SqliteStore, registry, budget: BudgetPolicy) -> Conductor:
    return Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        handlers={
            SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID, budget=budget)
        },
    )


def test_an_exhausted_budget_refuses_before_the_provider_is_called(store: SqliteStore) -> None:
    """The whole point of the gate. A check that runs after the call records an overrun; it
    does not prevent one."""
    registry, provider = registry_with(PROSE)
    seeded(store)

    result = conductor_for(store, registry, BudgetPolicy(max_invocations_per_day=0)).tick(START)

    assert provider.calls == 0, "the provider was called despite an exhausted budget"
    assert result.outcome is TickOutcome.JOB_PARKED
    assert store.load_job("draft-1").status is JobStatus.POISONED


def test_a_budget_refusal_is_recorded_as_a_gate_result(store: SqliteStore) -> None:
    """Auditable through the same path as a shape refusal, not a special case an operator
    has to know to look for."""
    registry, _ = registry_with(PROSE)
    seeded(store)

    conductor_for(store, registry, BudgetPolicy(max_invocations_per_day=0)).tick(START)

    [decision] = store.decisions_for_job("draft-1")
    assert decision.outcome is Outcome.PARK
    assert decision.gates[0].gate is GateKind.BUDGET
    assert decision.gates[0].passed is False
    # Nothing was spent, which is what refusing in front means.
    assert decision.invocations == 0
    assert decision.total_tokens == 0


def test_a_budget_refusal_emits_budget_exhausted(store: SqliteStore) -> None:
    registry, _ = registry_with(PROSE)
    seeded(store)

    conductor_for(store, registry, BudgetPolicy(max_invocations_per_day=0)).tick(START)

    kinds = [entry.event.event_type for entry in store.read_log()]
    assert EventType.BUDGET_EXHAUSTED in kinds


def test_spend_accumulates_from_recorded_decisions(store: SqliteStore) -> None:
    """Derived from the decisions rather than kept as a counter: a counter and the decisions
    it summarises can disagree after a crash, with no way to tell which is right."""
    registry, _ = registry_with(PROSE)
    seeded(store)
    conductor_for(store, registry, UNLIMITED).tick(START)

    day = store.read_log()[0].event.created_at[:10]
    spend = store.spend_on(day)
    assert spend.invocations == 1
    assert spend.tokens == 30


def test_cost_in_dollars_survives_to_storage(store: SqliteStore) -> None:
    """It was parsed from the provider envelope and then dropped: `policy_decisions` had no
    column, so the one number an operator reconciles against a bill was lost at the last
    step before storage."""
    store.record_decision(
        PolicyDecision(decision_id="dec-1", outcome=Outcome.ACCEPT, job_id="j", cost_usd=1.25),
        decided_at="2026-08-12T00:00:00Z",
    )
    assert store.load_decision("dec-1").cost_usd == 1.25
    assert store.spend_on("2026-08-12").cost_usd == 1.25


def test_a_generous_budget_does_not_interfere(store: SqliteStore) -> None:
    registry, provider = registry_with(PROSE)
    seeded(store)
    result = conductor_for(store, registry, UNLIMITED).tick(START)
    assert result.outcome is TickOutcome.RAN_JOB
    assert provider.calls == 1


# --- provider outages cost time, not work --------------------------------------------


class DeadProvider:
    """Present, non-billing, and failing every health probe — an outage, not a bad unit."""

    name = "dead"
    bills = False

    def __init__(self) -> None:
        self.probes = 0

    def health(self) -> bool:
        self.probes += 1
        return False

    def complete(self, request):  # pragma: no cover - never reached
        raise AssertionError("an unhealthy provider was called")


def test_a_sustained_outage_never_poisons_a_unit(store: SqliteStore) -> None:
    """The failure this replaces: `ProviderUnavailable` is raised before any work is
    attempted, yet it was charged against the attempt budget — so at the plan's 5-minute
    cadence `max_attempts=3` made any outage longer than fifteen minutes permanently poison
    every unit it touched. Poisoned is terminal *and* burns the idempotency key, so the
    work could not even be resubmitted.
    """
    from litharness.providers.registry import ProviderRegistry

    registry = ProviderRegistry(providers=[DeadProvider()], order=["dead"])
    seeded(store)
    conductor = conductor_for(store, registry, UNLIMITED)

    for index in range(12):  # an hour of outage at the 5-minute cadence
        conductor.tick(START + index * 300.0)

    job = store.load_job("draft-1")
    assert job.status is JobStatus.QUEUED, "an outage poisoned a unit that never ran"
    assert job.attempts == 0, "infrastructure failure was charged against the unit"


def test_the_unit_runs_normally_once_the_provider_returns(store: SqliteStore) -> None:
    """And the requeue is not a leak: the work is still there to do afterwards."""
    registry, provider = registry_with(PROSE)
    dead = DeadProvider()
    from litharness.providers.registry import ProviderRegistry

    outage = ProviderRegistry(providers=[dead], order=["dead"])
    seeded(store)

    conductor_for(store, outage, UNLIMITED).tick(START)
    assert store.load_job("draft-1").status is JobStatus.QUEUED

    result = conductor_for(store, registry, UNLIMITED).tick(START + 300.0)
    assert result.outcome is TickOutcome.RAN_JOB
    assert provider.calls == 1
