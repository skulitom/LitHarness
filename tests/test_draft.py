"""Slice 4: a job that carries its input, a shape gate, and a provider-backed handler.

The gate under test here is the one that separates *drafting* from *revising*. PLAN.md
§1a.2 forbids open-ended "improve this" loops and §12 makes unchanged text structurally
ineligible for revision, and the mechanism that enforces both is `gate_draft` refusing to
touch a node that already has prose. `test_a_draft_will_not_overwrite_existing_prose` is
therefore not a boundary-condition test; it is the one that keeps the architecture honest,
which is why it names the reason in its assertion.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import (
    SCENE_DRAFT,
    HandlerInputError,
    make_scene_draft_handler,
)
from litharness.domain.draft import DraftPolicy, gate_draft
from litharness.domain.events import EventType, payload_digest
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.nodes import LockKind, Node, NodeKind
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    UntrustedVerdict,
    VerdictSource,
    decide,
    decision_id_for,
    policy_digest,
)
from litharness.domain.revision import Revision, build_revision
from litharness.providers.base import CompletionRequest, CompletionResult, Usage
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0
PROSE = (
    "Rook set the lantern on the ledger stone and counted what the night had cost him. "
    "Forty-five gold in, twenty gone to the flame, five more to the gatekeeper who had "
    "not once looked up from his tally. The System said nothing, which was its own kind "
    "of accounting. He pressed his thumb to the wicket and felt the hounds turn behind "
    "him, and did not run, because running was what the debt wanted."
)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "draft.db")


def blank_revision() -> Revision:
    """A book whose scene-1 has no prose yet — the state a draft job exists to resolve."""
    return build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node(
                logical_id="scene-1",
                kind=NodeKind.SCENE,
                position_key="010",
                parent_logical_id="book",
            ),
        ],
    )


# --- the job payload -----------------------------------------------------------------


def test_a_job_carries_its_input_through_storage(store: SqliteStore) -> None:
    """The gap that actually blocked wiring: `input_digest` is a hash, not an input."""
    payload = {"revision_id": "r-1", "logical_id": "scene-1", "prompt": "Draft it."}
    store.enqueue(
        Job(
            job_id="draft-1",
            job_kind=SCENE_DRAFT,
            payload=payload,
            input_digest=input_digest_for(payload),
        )
    )
    reloaded = store.load_job("draft-1")
    assert reloaded.payload == payload
    assert reloaded.input_digest == payload_digest(payload)


def test_a_job_without_a_payload_stores_null_not_an_empty_object(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="noop-1", job_kind="noop"))
    assert store.load_job("noop-1").payload == {}
    row = store._connection.execute(
        "SELECT payload FROM jobs WHERE job_id = ?", ("noop-1",)
    ).fetchone()
    assert row["payload"] is None


def test_input_digest_is_insensitive_to_key_order(store: SqliteStore) -> None:
    """One digest definition, shared with events — otherwise dedupe silently diverges."""
    assert input_digest_for({"a": 1, "b": 2}) == input_digest_for({"b": 2, "a": 1})


# --- claim ordering ------------------------------------------------------------------


def test_priority_outranks_insertion_order(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="low", job_kind="noop"))
    store.enqueue(Job(job_id="high", job_kind="noop", priority=10))
    claimed = store.claim_next("worker-a", now=START, duration=60.0)
    assert claimed is not None and claimed.job_id == "high"


def test_equal_priority_still_claims_in_insertion_order(store: SqliteStore) -> None:
    """The FIFO guarantee `fifo_selector` documents must survive the ORDER BY change.

    This also pins the assumption the migration's index rests on: with `rowid` absent from
    the index key, ties must still break on ascending rowid.
    """
    for index in range(5):
        store.enqueue(Job(job_id=f"job-{index}", job_kind="noop"))
    claimed = [
        store.claim_next(f"worker-{index}", now=START, duration=60.0) for index in range(5)
    ]
    assert [job.job_id for job in claimed if job] == [f"job-{index}" for index in range(5)]


def test_priority_ties_break_on_insertion_not_on_id(store: SqliteStore) -> None:
    """Insert in an order that disagrees with lexical id order, so a stray ORDER BY job_id
    would pass the previous test and fail this one."""
    for job_id in ("zulu", "alpha", "mike"):
        store.enqueue(Job(job_id=job_id, job_kind="noop", priority=3))
    claimed = [store.claim_next(f"w-{n}", now=START, duration=60.0) for n in range(3)]
    assert [job.job_id for job in claimed if job] == ["zulu", "alpha", "mike"]


# --- the shape gate ------------------------------------------------------------------


def test_a_conforming_draft_fills_an_empty_node() -> None:
    outcome = gate_draft(blank_revision(), "scene-1", PROSE)
    assert outcome.accepted
    assert outcome.revision is not None
    assert outcome.revision.node("scene-1").content == PROSE
    assert outcome.chars == len(PROSE)


def test_a_draft_will_not_overwrite_existing_prose() -> None:
    """§1a.2 and §12 in one assertion: rewriting needs a located complaint, so it must
    route through `apply_patch` rather than through a fresh generation."""
    revision = gate_draft(blank_revision(), "scene-1", PROSE).revision
    assert revision is not None

    outcome = gate_draft(revision, "scene-1", PROSE.replace("Rook", "Someone else"))

    assert not outcome.accepted
    assert outcome.veto_kinds == (Veto.TARGET_HAS_NO_CONTENT,)
    assert "apply_patch" in outcome.vetoes[0].detail


def test_overwrite_is_possible_only_by_explicit_policy() -> None:
    revision = gate_draft(blank_revision(), "scene-1", PROSE).revision
    assert revision is not None
    outcome = gate_draft(
        revision, "scene-1", PROSE.upper(), policy=DraftPolicy(allow_overwrite=True)
    )
    assert outcome.accepted


def test_a_non_conforming_answer_is_a_veto_not_an_exception() -> None:
    """§4.2 ladder step 1: a bad shape earns a bounded retry, never a dead unit of work."""
    outcome = gate_draft(blank_revision(), "scene-1", PROSE, conforms=False)
    assert outcome.veto_kinds == (Veto.SHAPE_NOT_CONFORMING,)


@pytest.mark.parametrize("text", ["", "   ", "\n\n\t"])
def test_an_empty_draft_is_refused(text: str) -> None:
    assert gate_draft(blank_revision(), "scene-1", text).veto_kinds == (Veto.EMPTY_DRAFT,)


def test_a_stub_draft_is_refused_by_the_length_floor() -> None:
    assert gate_draft(blank_revision(), "scene-1", "Too short.").veto_kinds == (
        Veto.LENGTH_MOVEMENT,
    )


def test_a_runaway_draft_is_refused_by_the_ceiling() -> None:
    outcome = gate_draft(blank_revision(), "scene-1", "word " * 5000)
    assert outcome.veto_kinds == (Veto.LENGTH_MOVEMENT,)


def test_a_content_locked_node_refuses_a_draft() -> None:
    revision = build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node(
                logical_id="scene-1",
                kind=NodeKind.SCENE,
                position_key="010",
                parent_logical_id="book",
                lock=LockKind.PUBLISHED,
            ),
        ],
    )
    assert gate_draft(revision, "scene-1", PROSE).veto_kinds == (Veto.CONTENT_LOCKED,)


def test_an_unknown_target_is_refused() -> None:
    assert gate_draft(blank_revision(), "scene-99", PROSE).veto_kinds == (Veto.UNKNOWN_TARGET,)


def test_the_gate_persists_nothing() -> None:
    """It returns a revision; committing is the Conductor's job, because only the
    Conductor can put the revision, its events and the job row in one transaction."""
    original = blank_revision()
    gate_draft(original, "scene-1", PROSE)
    assert original.node("scene-1").content is None


# --- the handler, end to end ---------------------------------------------------------


def registry_with(text: str) -> tuple[ProviderRegistry, FakeProvider]:
    provider = FakeProvider()
    request = CompletionRequest(prompt="Draft scene 1.", call_class="generation")

    def complete(_: CompletionRequest) -> CompletionResult:
        provider.calls += 1
        return CompletionResult(
            text=text, provider="fake", model="fake-deterministic-v1", usage=Usage(10, 20)
        )

    provider.complete = complete  # type: ignore[method-assign]
    assert request.prompt
    return ProviderRegistry(providers=[provider], order=["fake"]), provider


def seeded(store: SqliteStore, payload_extra: dict | None = None) -> Revision:
    revision = blank_revision()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    payload = {
        "revision_id": revision.revision_id,
        "logical_id": "scene-1",
        "prompt": "Draft the opening scene.",
        **(payload_extra or {}),
    }
    store.enqueue(
        Job(
            job_id="draft-1",
            job_kind=SCENE_DRAFT,
            payload=payload,
            input_digest=input_digest_for(payload),
        )
    )
    return revision


def conductor_for(store: SqliteStore, registry: ProviderRegistry) -> Conductor:
    return Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        handlers={
            SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID),
        },
    )


def test_a_model_written_scene_passes_the_gate_and_becomes_a_revision(
    store: SqliteStore,
) -> None:
    """The first time in this codebase that generated text reaches accepted canon."""
    registry, provider = registry_with(PROSE)
    base = seeded(store)

    result = conductor_for(store, registry).tick(START)

    assert result.outcome is TickOutcome.RAN_JOB
    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    assert provider.calls == 1

    accepted = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
    ]
    assert len(accepted) == 1
    assert accepted[0].payload["accepted"] is True
    assert accepted[0].payload["parent_revision_id"] == base.revision_id

    committed = store.load_revision(accepted[0].revision_id or "")
    assert committed.node("scene-1").content == PROSE
    assert store.verify_integrity() == 2

    # §19: every mutation attributable to a recorded policy decision. Checkable, not
    # merely asserted in prose — the revision resolves back to the decision that took it.
    decision = store.decision_for_revision(committed.revision_id)
    assert decision is not None
    assert decision.outcome is Outcome.ACCEPT
    assert decision.provider == "fake"
    assert decision.base_revision_id == base.revision_id


def test_a_refused_draft_commits_no_revision_but_records_the_candidate(
    store: SqliteStore,
) -> None:
    """A gate failure must leave a trace. Silence would make the refusal unauditable and
    hide a provider that had started returning stubs."""
    registry, _ = registry_with("Too short.")
    seeded(store)

    conductor_for(store, registry).tick(START)

    events = [entry.event for entry in store.read_log()]
    assert [event.event_type for event in events] == [
        EventType.MANUSCRIPT_CANDIDATE_CREATED,
        EventType.POLICY_DECISION_RECORDED,
    ]
    assert events[0].payload["accepted"] is False
    assert events[0].payload["vetoes"] == [Veto.LENGTH_MOVEMENT.value]
    # One revision only: the base. Nothing was accepted.
    assert store.verify_integrity() == 1

    # A refusal is recorded as fully as an acceptance. A decision trail with holes where
    # the failures were cannot answer "why is this unit stuck".
    [decision] = store.decisions_for_job("draft-1")
    assert decision.outcome is Outcome.RETRY
    assert decision.failed_vetoes == (Veto.LENGTH_MOVEMENT,)
    assert decision.resulting_revision_id is None


def test_the_decision_record_carries_the_provenance_section_2_requires(
    store: SqliteStore,
) -> None:
    """§2: every generated claim traceable to inputs, tool/model versions, and the policy
    that accepted it.

    This assertion used to run against a free-form event payload, because contracts had no
    policy decision record. It has one as of 1.1.0, so the same guarantee is now checked
    against the artifact that owns it — which is what §20.3's consumer-first sequencing
    was for.
    """
    registry, _ = registry_with(PROSE)
    seeded(store)
    conductor_for(store, registry).tick(START)

    [decision] = store.decisions_for_job("draft-1")
    assert decision.job_id == "draft-1"
    assert decision.logical_id == "scene-1"
    assert decision.base_revision_id
    assert decision.provider == "fake"
    assert decision.model == "fake-deterministic-v1"
    assert decision.profile == "default"
    assert decision.fell_back_from == ()
    assert decision.invocations == 1
    assert decision.total_tokens == 30
    assert decision.gates and decision.gates[0].rule_or_critic_id == "shape.draft.v0"
    # The frozen policy the decision was made under, so a later threshold change reads as
    # a different config rather than as unexplained drift in behaviour.
    assert decision.policy_config_digest == policy_digest(DraftPolicy())


def test_replaying_the_job_converges_instead_of_duplicating(store: SqliteStore) -> None:
    """The Conductor commits handler events and the job row in two transactions, so a
    crash between them replays the job. Content addressing is what makes that safe."""
    registry, _ = registry_with(PROSE)
    seeded(store)
    handler = make_scene_draft_handler(registry, store, PROJECT_ID)
    job = store.claim_next("worker-a", now=START, duration=600.0)
    assert job is not None

    handler(job, START)
    handler(job, START)

    assert store.verify_integrity() == 2  # base + one accepted, not two accepted
    assert len(store.read_log()) == 1


def test_a_malformed_payload_fails_the_job_rather_than_committing_anything(
    store: SqliteStore,
) -> None:
    registry, _ = registry_with(PROSE)
    revision = blank_revision()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    store.enqueue(Job(job_id="draft-1", job_kind=SCENE_DRAFT, payload={"prompt": "no target"}))

    result = conductor_for(store, registry).tick(START)

    assert result.outcome is TickOutcome.JOB_FAILED
    assert "HandlerInputError" in (store.load_job("draft-1").error or "")
    assert store.verify_integrity() == 1


def test_the_handler_raises_handler_input_error_directly(store: SqliteStore) -> None:
    registry, _ = registry_with(PROSE)
    handler = make_scene_draft_handler(registry, store, PROJECT_ID)
    with pytest.raises(HandlerInputError):
        handler(Job(job_id="x", job_kind=SCENE_DRAFT, payload={}), START)


# --- the health-verdict cache --------------------------------------------------------


class FlakyProvider:
    """Unhealthy on the first probe, healthy afterwards."""

    name = "flaky"
    bills = False

    def __init__(self) -> None:
        self.probes = 0

    def health(self) -> bool:
        self.probes += 1
        return self.probes > 1

    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult(text=PROSE, provider=self.name, model="flaky-v1")


def test_a_recovered_provider_is_usable_on_a_later_tick(store: SqliteStore) -> None:
    """`reset_health` documented a per-tick caller it never had. Without one, a provider
    marked dead by a single failed probe stayed dead for the life of the process."""
    provider = FlakyProvider()
    registry = ProviderRegistry(providers=[provider], order=["flaky"])
    seeded(store)
    conductor = conductor_for(store, registry)

    first = conductor.tick(START)
    second = conductor.tick(START + 300.0)

    assert first.outcome is TickOutcome.JOB_FAILED  # probe 1: unhealthy
    assert second.outcome is TickOutcome.RAN_JOB  # probe 2, after the reset: healthy
    assert provider.probes == 2


def test_health_is_probed_once_per_tick_not_once_per_call(store: SqliteStore) -> None:
    provider = FlakyProvider()
    provider.probes = 1  # already healthy
    registry = ProviderRegistry(providers=[provider], order=["flaky"])
    seeded(store)
    conductor_for(store, registry).tick(START)
    assert provider.probes == 2  # exactly one probe inside the tick


def test_test_mode_still_blocks_a_billing_provider_through_the_handler(
    store: SqliteStore,
) -> None:
    """The billing guard has to hold on the path that actually spends money."""

    class Paid:
        name = "paid"
        bills = True

        def health(self) -> bool:
            return True

        def complete(self, request: CompletionRequest) -> CompletionResult:  # pragma: no cover
            raise AssertionError("a test run reached a paid provider")

    registry = ProviderRegistry(providers=[Paid()], order=["paid"])
    seeded(store)

    result = conductor_for(store, registry).tick(START)

    assert result.outcome is TickOutcome.JOB_FAILED
    assert "no healthy provider" in (store.load_job("draft-1").error or "")


# --- the acceptance policy engine ----------------------------------------------------


def shape_gate(passed: bool, *vetoes: Veto) -> GateOutcome:
    return GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.draft.v0",
        passed=passed,
        vetoes=vetoes,
    )


def test_all_gates_passing_accepts() -> None:
    outcome, reason = decide(
        (shape_gate(True),), job_id="j", attempt=1, max_attempts=3
    )
    assert outcome is Outcome.ACCEPT
    assert reason is None


def test_a_retryable_veto_earns_another_attempt() -> None:
    outcome, _ = decide(
        (shape_gate(False, Veto.LENGTH_MOVEMENT),), job_id="j", attempt=1, max_attempts=3
    )
    assert outcome is Outcome.RETRY


def test_a_stale_base_regenerates_rather_than_retrying() -> None:
    """Repeating the same candidate against the same stale base cannot succeed; a fresh
    one against a re-read base can."""
    outcome, _ = decide(
        (shape_gate(False, Veto.STALE_BASE_CONTENT),), job_id="j", attempt=1, max_attempts=3
    )
    assert outcome is Outcome.REGENERATE


def test_an_unfixable_veto_escalates_immediately_without_burning_the_budget() -> None:
    """The ordering decision in `decide`, and the reason it is not an implementation
    detail: a locked node must be reported as locked on the first attempt, not as
    "attempts exhausted" on the fourth with the real cause buried."""
    outcome, reason = decide(
        (shape_gate(False, Veto.CONTENT_LOCKED),), job_id="j", attempt=1, max_attempts=3
    )
    assert outcome is Outcome.ESCALATE
    assert "content_locked" in (reason or "")


def test_an_unclassified_veto_escalates_rather_than_defaulting_to_retry() -> None:
    """Escalation is the default for a veto nobody has classified. A default of retry
    would spend three model calls to rediscover an unknown failure."""
    outcome, _ = decide(
        (shape_gate(False, Veto.PRESERVATION_BREACH),), job_id="j", attempt=1, max_attempts=3
    )
    assert outcome is Outcome.ESCALATE


def test_an_exhausted_budget_parks_rather_than_spinning() -> None:
    """§4.2: the failure mode is a parked unit, never a spin loop."""
    outcome, reason = decide(
        (shape_gate(False, Veto.EMPTY_DRAFT),), job_id="j", attempt=3, max_attempts=3
    )
    assert outcome is Outcome.PARK
    assert "exhausted" in (reason or "")


def test_a_blocking_gate_may_not_trust_the_generating_model() -> None:
    """MirrorBench's central invariant, enforced at construction rather than documented.

    A model's report on its own output is not a correctness signal, so a decision that
    tried to build one into a blocking gate must fail loudly here rather than quietly at
    review time.
    """
    with pytest.raises(UntrustedVerdict, match="not a correctness signal"):
        PolicyDecision(
            decision_id="d-1",
            outcome=Outcome.ACCEPT,
            gates=(
                GateOutcome(
                    gate=GateKind.CRAFT,
                    rule_or_critic_id="craft.selfscore.v0",
                    passed=True,
                    verdict_source=VerdictSource.MODEL_SELF_REPORT,
                    blocking=True,
                ),
            ),
        )


def test_a_self_reported_verdict_is_allowed_when_it_does_not_gate() -> None:
    """Recorded so it can be refused, not banned from the record. An annotation that
    never blocks is evidence about the model, and worth keeping."""
    decision = PolicyDecision(
        decision_id="d-1",
        outcome=Outcome.ACCEPT,
        gates=(
            GateOutcome(
                gate=GateKind.CRAFT,
                rule_or_critic_id="craft.selfscore.v0",
                passed=True,
                verdict_source=VerdictSource.MODEL_SELF_REPORT,
                blocking=False,
            ),
        ),
    )
    assert decision.accepted


def test_an_uncalibrated_craft_gate_may_not_block() -> None:
    """§10.4: a critic becomes blocking only after held-out calibration. Until then it
    annotates, and this is what stops "until then" from lasting forever by accident."""
    with pytest.raises(UntrustedVerdict, match="calibration"):
        PolicyDecision(
            decision_id="d-1",
            outcome=Outcome.ACCEPT,
            gates=(
                GateOutcome(
                    gate=GateKind.CRAFT,
                    rule_or_critic_id="craft.pacing.v0",
                    passed=True,
                    verdict_source=VerdictSource.UNCALIBRATED_CRITIC,
                    blocking=True,
                ),
            ),
        )


def test_a_decision_survives_a_round_trip_through_storage(store: SqliteStore) -> None:
    decision = PolicyDecision(
        decision_id="dec-1",
        outcome=Outcome.RETRY,
        gates=(shape_gate(False, Veto.LENGTH_MOVEMENT, Veto.EMPTY_DRAFT),),
        job_id="draft-1",
        logical_id="scene-1",
        attempt=2,
        provider="fake",
        fell_back_from=("claude_code",),
        total_tokens=30,
        reason="length_movement",
    )
    assert store.record_decision(decision, decided_at="2026-08-12T00:00:00Z") is True
    assert store.load_decision("dec-1") == decision


def test_recording_the_same_decision_twice_is_a_no_op(store: SqliteStore) -> None:
    """Content-derived ids, for the same reason ticks have them: a job replayed after a
    crash must not accumulate duplicate rows for one judgment."""
    decision = PolicyDecision(decision_id="dec-1", outcome=Outcome.ACCEPT, job_id="draft-1")
    assert store.record_decision(decision, decided_at="2026-08-12T00:00:00Z") is True
    assert store.record_decision(decision, decided_at="2026-08-12T99:99:99Z") is False
    # One row, and the first write wins — a replay must not rewrite the original timestamp.
    assert store.decisions_for_job("draft-1") == [decision]


def test_the_decision_id_is_stable_for_the_same_judgment() -> None:
    gates = (shape_gate(False, Veto.EMPTY_DRAFT),)
    assert decision_id_for("j", 1, gates) == decision_id_for("j", 1, gates)
    assert decision_id_for("j", 1, gates) != decision_id_for("j", 2, gates)


def test_a_replayed_job_records_one_decision_not_two(store: SqliteStore) -> None:
    registry, _ = registry_with(PROSE)
    seeded(store)
    handler = make_scene_draft_handler(registry, store, PROJECT_ID)
    job = store.claim_next("worker-a", now=START, duration=600.0)
    assert job is not None

    handler(job, START)
    handler(job, START)

    assert len(store.decisions_for_job("draft-1")) == 1


def test_every_event_type_exists_in_the_contract() -> None:
    """`Event.to_contract` calls `lc.EventType(self.value)`, which raises on an unknown
    string — so a member added here but not upstream fails at insert time, deep inside a
    handler, rather than at import. This is the cheap check that keeps the two enums
    honest with each other."""
    import litharness_contracts as lc

    for member in EventType:
        assert lc.EventType(member.value).value == member.value
