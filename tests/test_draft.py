"""Slice 4: a job that carries its input, a shape gate, and a provider-backed handler.

The gate under test here is the one that separates *drafting* from *revising*. PLAN.md
§1a.2 forbids open-ended "improve this" loops and §12 makes unchanged text structurally
ineligible for revision, and the mechanism that enforces both is `gate_draft` refusing to
touch a node that already has prose. `test_a_draft_will_not_overwrite_existing_prose` is
therefore not a boundary-condition test; it is the one that keeps the architecture honest,
which is why it names the reason in its assertion.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import (
    SCENE_DRAFT,
    HandlerInputError,
    make_scene_draft_handler,
)
from litharness.domain.audit import AuditSample, Verdict
from litharness.domain.calibration import (
    MIN_HOLDOUT,
    Calibration,
    Direction,
    EvidenceClass,
    Grain,
    calibration_id_for,
    verdicts_digest_for,
)
from litharness.domain.craft import measure
from litharness.domain.draft import DraftPolicy, gate_draft
from litharness.domain.events import EventType, payload_digest
from litharness.domain.findings import Status as FindingStatus
from litharness.domain.integrity import DUPLICATE_RULE
from litharness.domain.jobs import IllegalTransition, Job, JobStatus, input_digest_for
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
    gates_for_draft,
    policy_digest,
)
from litharness.domain.revision import Revision, build_revision
from litharness.providers.base import CompletionRequest, CompletionResult, Usage
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, PROMOTABLE_FLAGS

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


def test_an_accepted_draft_records_what_was_asked_for_beside_what_arrived() -> None:
    """The shortfall that blocks §17 Stage 3, made legible without becoming a gate.

    `target_words` is an instruction and deliberately not a limit — §1a.1's "beware the
    metric that is easy *because* it is shallow", since a 900-word floor would pass a scene
    that rambles to 900 and refuse a taut one. That reasoning stands and this does not touch
    it: the draft below is 19% of target and is still **accepted**.

    What changes is that the record no longer omits the delivered length. Measured across
    every stored run — 45 scenes over six books — the mean scene is **172 words against a
    900-word target, 19%**, ranging 14% to 40%. Stage 3's low end of 50,000 words needs 291
    scenes at that rate. `policy_config_digest` already cites what was *asked*; nothing
    carried what *arrived*, so the one number that decides whether Stage 3 is reachable
    existed only as a hand-measured note in a docstring.
    """
    short = " ".join(["word"] * 170)

    outcome = gate_draft(blank_revision(), "scene-1", short)
    [gate] = gates_for_draft(outcome)

    assert outcome.accepted, "a target is not a limit; this must still land"
    assert outcome.words == 170
    assert outcome.target_words == DraftPolicy().target_words
    assert gate.passed and gate.detail is not None
    assert "170 words" in gate.detail and "900" in gate.detail


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
    return ProviderRegistry(provider), provider


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
    #
    # **The sampler is part of that config**, and this assertion is what says so. The
    # decision records `profile`, and a profile *name* resolves to decoding settings through
    # a module constant — so without the sampler in the digest, changing `generation.PROSE`'s
    # temperature would leave every stored digest identical while every scene written after
    # it came from a different generator. The digest is the answer to "were these two scenes
    # written under the same configuration", and the name alone cannot answer it.
    from litharness.application.handlers import draft_sampler
    from litharness.domain import generation

    expected_sampler = draft_sampler(store.load_job("draft-1"), "default")
    assert decision.policy_config_digest == policy_digest(DraftPolicy(), expected_sampler)
    assert decision.policy_config_digest != policy_digest(DraftPolicy())
    assert decision.policy_config_digest != policy_digest(
        DraftPolicy(), replace(expected_sampler, temperature=generation.PROSE.temperature + 0.1)
    )


def test_a_retry_draws_a_different_sample_of_the_same_frozen_request() -> None:
    """The defect that made the retry ladder cost three calls to receive one answer.

    The prompt is frozen onto the job payload at plan time and re-read verbatim on every
    attempt; `Job.fail` changes status, attempts and error and never the payload. With a
    constant seed and `temperature=0.0` the provider therefore received byte-identical
    inputs on attempt 2 and 3, returned what it returned on attempt 1, met the identical
    gate refusal, and poisoned the unit — a ladder with one rung, climbed three times.

    Both halves are asserted because either alone is satisfiable by a bug: a seed that never
    moves passes the second, and a random seed passes the first.
    """
    from litharness.application.handlers import draft_sampler

    payload = {"revision_id": "r-1", "logical_id": "scene-1", "prompt": "Draft it."}
    job = Job(
        job_id="draft-1",
        job_kind=SCENE_DRAFT,
        payload=payload,
        input_digest=input_digest_for(payload),
    )

    first = draft_sampler(job, "default")
    second = draft_sampler(replace(job, attempts=1), "default")
    assert first.seed != second.seed, "a retry must not re-ask the identical question"
    assert first.seed == draft_sampler(job, "default").seed, (
        "the same job at the same attempt must replay to the same prose"
    )
    # A distinct scene is a distinct sample path, which a pinned constant could not give.
    other = {**payload, "logical_id": "scene-2"}
    assert (
        draft_sampler(replace(job, input_digest=input_digest_for(other)), "default").seed
        != first.seed
    )


def test_schema_shaped_work_stays_greedy_and_carries_no_seed() -> None:
    """A seed at temperature zero is a number in a record that changed no output.

    Measured: three distinct seeds against one unchanged request returned byte-identical
    text on both models tested, because greedy decoding samples nothing. Recording one
    anyway would be provenance that reads as an explanation and explains nothing — and
    extraction *wants* to be greedy, so this is the one place the old global was right.
    """
    from litharness.application.handlers import draft_sampler

    job = Job(job_id="x-1", job_kind=SCENE_DRAFT, input_digest="d")
    mechanical = draft_sampler(job, "mechanical")
    assert mechanical.temperature == 0.0
    assert mechanical.seed is None
    assert draft_sampler(replace(job, attempts=2), "mechanical") == mechanical


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
    marked dead by a single failed probe stayed dead for the life of the process. The
    per-tick reset now clears negative verdicts only — which is exactly what this needs:
    the failed probe is forgotten, the recovery is kept."""
    provider = FlakyProvider()
    registry = ProviderRegistry(provider)
    seeded(store)
    conductor = conductor_for(store, registry)

    first = conductor.tick(START)
    second = conductor.tick(START + 300.0)

    assert first.outcome is TickOutcome.JOB_FAILED  # probe 1: unhealthy
    assert second.outcome is TickOutcome.RAN_JOB  # probe 2, after the reset: healthy
    assert provider.probes == 2


def test_health_is_probed_once_per_tick_not_once_per_call(store: SqliteStore) -> None:
    """A healthy verdict now outlives the tick (the probe is billed work — see
    `ProviderRegistry.reset_health`); within the tick, the handler's resolve-for-budget
    and the completion itself must still share one probe."""
    provider = FlakyProvider()
    provider.probes = 1  # already healthy
    registry = ProviderRegistry(provider)
    seeded(store)
    conductor_for(store, registry).tick(START)
    assert provider.probes == 2  # exactly one probe inside the tick


def test_test_mode_still_blocks_a_billing_provider_through_the_handler(
    store: SqliteStore,
) -> None:
    """The billing guard has to hold on the path that actually spends money.

    It used to hold by filtering, which surfaced as `ProviderUnavailable` and a quiet
    requeue. The pinned registry refuses instead: `BillingGuardViolation` is a loud
    defect report — a test that wires a paid provider is misconfigured, not suffering an
    outage — so the job fails with the guard's name on it and the provider is never
    called, never even probed."""

    class Paid:
        name = "paid"
        bills = True

        def health(self) -> bool:  # pragma: no cover - the guard runs before the probe
            raise AssertionError("a test run paid for a health probe")

        def complete(self, request: CompletionRequest) -> CompletionResult:  # pragma: no cover
            raise AssertionError("a test run reached a paid provider")

    registry = ProviderRegistry(Paid())
    seeded(store)

    result = conductor_for(store, registry).tick(START)

    assert result.outcome is TickOutcome.JOB_FAILED
    job = store.load_job("draft-1")
    assert job.status is JobStatus.FAILED
    assert "BillingGuardViolation" in (job.error or "")


# --- the acceptance policy engine ----------------------------------------------------


def shape_gate(passed: bool, *vetoes: Veto) -> GateOutcome:
    return GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.draft.v0",
        passed=passed,
        vetoes=vetoes,
    )


def craft_gate(passed: bool, *vetoes: Veto) -> GateOutcome:
    """A promoted craft gate, which `calibration.promoted_gate` is the only real producer of.

    Built by hand here because `decide` is pure and total over gate results: what is under
    test is the ladder's response to the veto, not the evidence that earned it.
    """
    return GateOutcome(
        gate=GateKind.CRAFT,
        rule_or_critic_id="craft.tricolon_rate.v0",
        passed=passed,
        blocking=True,
        vetoes=vetoes,
        calibration_id="cal-test",
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


def test_a_craft_refusal_parks_rather_than_escalating_or_retrying() -> None:
    """The decision `PARKABLE` records, checked here because all three alternatives are
    plausible enough that a later reader would otherwise reclassify it.

    Not ESCALATE: a gate firing on 5% of scenes would be one director interruption per
    twenty accepted, in a system whose claim is that it runs without one. Not RETRY: another
    attempt is measured by the same metric, so the accepted candidate would be the one that
    beat it — rejection sampling against a craft proxy, arriving as a side effect of a retry
    class rather than as a decision anyone took.
    """
    outcome, reason = decide(
        (craft_gate(False, Veto.CRAFT_BELOW_BAR),), job_id="j", attempt=1, max_attempts=3
    )
    assert outcome is Outcome.PARK
    assert "craft_below_bar" in (reason or "")
    assert "exhausted" not in (reason or ""), "it parks on its own cause, not on the budget"


def test_a_craft_refusal_parks_on_the_first_attempt() -> None:
    """It is never charged the attempts it was never going to use. Parking on attempt 3
    would spend two generations to reach a refusal the first one already established."""
    for attempt in (1, 2, 3):
        outcome, _ = decide(
            (craft_gate(False, Veto.CRAFT_BELOW_BAR),),
            job_id="j",
            attempt=attempt,
            max_attempts=3,
        )
        assert outcome is Outcome.PARK, f"attempt {attempt}"


def test_a_craft_refusal_beside_a_retryable_veto_still_parks() -> None:
    """The precedence in `decide`, and the safe direction to be wrong in. The mixed case is
    unreachable today because craft is measured only on a draft shape already accepted — but
    if it becomes reachable, the retry must not become the door the rejection-sampling
    channel opens through."""
    outcome, _ = decide(
        (craft_gate(False, Veto.CRAFT_BELOW_BAR), shape_gate(False, Veto.LENGTH_MOVEMENT)),
        job_id="j",
        attempt=1,
        max_attempts=3,
    )
    assert outcome is Outcome.PARK


def test_a_craft_refusal_beside_an_unclassified_veto_still_escalates() -> None:
    """Parking must not swallow a veto nobody has classified. Escalation stays the default
    for the unknown, which is the invariant the `PARKABLE` check is inserted after."""
    outcome, reason = decide(
        (craft_gate(False, Veto.CRAFT_BELOW_BAR), shape_gate(False, Veto.CONTENT_LOCKED)),
        job_id="j",
        attempt=1,
        max_attempts=3,
    )
    assert outcome is Outcome.ESCALATE
    assert "content_locked" in (reason or "")


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


# --- the ladder is enforced, not just recorded ---------------------------------------


def seeded_with_prose(store: SqliteStore) -> None:
    """A book whose scene-1 already has prose, so a draft job against it must be refused
    with a veto no retry can fix."""
    revision = blank_revision()
    filled = gate_draft(revision, "scene-1", PROSE).revision
    assert filled is not None
    # The parent has to exist too: revisions carry a FK to their parent, which is what
    # makes lineage unbroken rather than merely recorded.
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    store.commit_revision(filled, created_at="2026-08-12T00:00:01Z")
    payload = {
        "revision_id": filled.revision_id,
        "logical_id": "scene-1",
        "prompt": "Draft the opening scene.",
    }
    store.enqueue(
        Job(job_id="draft-1", job_kind=SCENE_DRAFT, payload=payload,
            input_digest=input_digest_for(payload))
    )


def test_an_escalated_unit_is_parked_not_counted_as_a_success(store: SqliteStore) -> None:
    """The bug this replaces: `_run` marked the job SUCCEEDED whenever the handler did not
    raise, so a candidate the policy engine ESCALATED was dropped off the queue and
    counted in `jobs_succeeded`. Not parked, not visible, not bounded — gone."""
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)

    result = conductor_for(store, registry).tick(START)

    assert result.outcome is TickOutcome.JOB_PARKED
    job = store.load_job("draft-1")
    assert job.status is JobStatus.PARKED
    assert job.status.needs_attention

    [decision] = store.decisions_for_job("draft-1")
    assert decision.outcome is Outcome.ESCALATE

    day = store.read_log()[0].event.created_at[:10]
    digest = store.digest(day)
    assert digest.get("jobs_succeeded", 0) == 0
    assert digest["jobs_parked"] == 1
    assert digest["exceptions_raised"] == 1


def test_an_escalation_raises_an_exception_event(store: SqliteStore) -> None:
    """§4.2: the failure mode is a parked unit *plus an exception*. Silence would leave the
    unit stuck with nothing summoning a human."""
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)
    conductor_for(store, registry).tick(START)

    raised = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.EXCEPTION_RAISED
    ]
    assert len(raised) == 1
    assert raised[0].payload["job_id"] == "draft-1"
    assert "target_has_no_content" in raised[0].payload["reason"]


def test_a_retryable_refusal_requeues_and_stays_bounded(store: SqliteStore) -> None:
    """RETRY must re-enter the existing bounded ladder, not park. And the ladder must still
    terminate: a candidate that is always too short poisons on budget rather than spinning."""
    registry, _ = registry_with("Too short.")
    seeded(store)
    conductor = conductor_for(store, registry)

    outcomes = [conductor.tick(START + index * 300.0).outcome for index in range(6)]

    assert outcomes[0] is TickOutcome.JOB_FAILED
    assert store.load_job("draft-1").status is JobStatus.POISONED
    assert TickOutcome.RAN_JOB not in outcomes
    # Terminates rather than spinning: later ticks find nothing to do.
    assert outcomes[-1] is TickOutcome.NO_WORK


def test_parked_units_are_visible_to_an_operator(store: SqliteStore) -> None:
    """§19 Autonomy: "parked units and exceptions are visible and bounded". Until this
    existed the only job query was load_job(job_id), which requires already knowing the id
    of the job you have not heard about."""
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)
    conductor_for(store, registry).tick(START)

    assert store.job_counts_by_status() == {"parked": 1}
    assert [job.job_id for job in store.jobs_by_status(JobStatus.PARKED)] == ["draft-1"]


def test_a_parked_unit_can_be_revived_once_a_human_clears_the_blocker(
    store: SqliteStore,
) -> None:
    """Parked is terminal by policy, not by exhaustion, so the resolution is a decision
    rather than another attempt — and attempts reset, because a unit parked on a locked
    node has not spent its budget on failures of its own."""
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)
    conductor_for(store, registry).tick(START)

    revived = store.revive("draft-1")

    assert revived.status is JobStatus.QUEUED
    assert revived.attempts == 0
    assert revived.error is None
    assert store.queued_count() == 1


def test_a_poisoned_unit_is_not_revivable(store: SqliteStore) -> None:
    """Poisoning means the budget really was spent. Reviving without changing anything
    would just spend it again."""
    registry, _ = registry_with("Too short.")
    seeded(store)
    conductor = conductor_for(store, registry)
    for index in range(4):
        conductor.tick(START + index * 300.0)
    assert store.load_job("draft-1").status is JobStatus.POISONED

    with pytest.raises(IllegalTransition, match="not parked"):
        store.revive("draft-1")


# --- a craft refusal, through the whole ladder (§26) ----------------------------------


def registry_with_sequence(*texts: str) -> tuple[ProviderRegistry, FakeProvider]:
    """A provider whose output changes per call, so a unit can be driven to its ceiling."""
    provider = FakeProvider()

    def complete(_: CompletionRequest) -> CompletionResult:
        text = texts[min(provider.calls, len(texts) - 1)]
        provider.calls += 1
        return CompletionResult(
            text=text, provider="fake", model="fake-deterministic-v1", usage=Usage(10, 20)
        )

    provider.complete = complete  # type: ignore[method-assign]
    return ProviderRegistry(provider), provider


def with_a_failing_craft_gate(store: SqliteStore) -> None:
    """Record a calibration `PROSE` is certain to fail, and that clears every promotion bar.

    The threshold is derived from the measurement rather than written down, so the test
    cannot silently stop exercising the gate if the metric's definition moves.

    Keyed to `craft.scene_echo.v1` (originally `craft.dialogue_ratio.v0`) since the four
    refuted proxies were archived: the ladder only consults a calibration for a metric this
    draft measured, and `measure` no longer reports the archived ids. The derived
    threshold (`value + 1.0`, direction BELOW) fails for any measured value, so the re-key
    changes which id carries the gate and nothing about the park behaviour under test.
    """
    value = {metric.metric_id: metric.value for metric in measure(PROSE)}
    metric_id = "craft.scene_echo.v1"
    # **The holdout has to actually be in the store now.** `why_not_promotable` compares
    # `holdout_size` against the number of answered audit samples, because nothing ever did:
    # a row claiming fifty held-out judgments promoted against a store holding none, and the
    # digest clause could not catch it, since the digest of the empty set matches itself.
    for index in range(MIN_HOLDOUT):
        sample = AuditSample(
            sample_id=f"craft-holdout-{index}",
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
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
    digest = verdicts_digest_for(
        (item.sample_id, item.verdict.value)
        for item in store.audit_samples()
        if item.verdict is not None
    )
    store.record_calibration(
        Calibration(
            calibration_id=calibration_id_for(
                metric_id,
                value[metric_id] + 1.0,
                digest,
                direction=Direction.BELOW,
                correct=PROMOTABLE_FLAGS,
                holdout_size=MIN_HOLDOUT,
                flagged=PROMOTABLE_FLAGS,
                selection_family_size=1,
                clusters=2,
                evidence_class=EvidenceClass.JUDGMENT,
                grain=Grain.UNIT,
            ),
            metric_id=metric_id,
            holdout_size=MIN_HOLDOUT,
            flagged=PROMOTABLE_FLAGS,
            correct=PROMOTABLE_FLAGS,
            selection_family_size=1,
            clusters=2,
            evidence_class=EvidenceClass.JUDGMENT,
            grain=Grain.UNIT,
            threshold=value[metric_id] + 1.0,
            direction=Direction.BELOW,
            verdicts_digest=digest,
            measured_at="2026-08-01T00:00:00Z",
        )
    )


def book_scoped(store: SqliteStore) -> None:
    seeded(store, {"book_id": BOOK_ID, "branch_id": BRANCH_ID})


def test_a_craft_refusal_parks_the_unit_rather_than_accepting_it(store: SqliteStore) -> None:
    registry, _ = registry_with(PROSE)
    book_scoped(store)
    with_a_failing_craft_gate(store)

    result = conductor_for(store, registry).tick(START)

    assert result.outcome is TickOutcome.JOB_PARKED
    assert store.load_job("draft-1").status is JobStatus.PARKED
    [decision] = store.decisions_for_job("draft-1")
    assert decision.outcome is Outcome.PARK
    assert Veto.CRAFT_BELOW_BAR in decision.failed_vetoes


def test_a_craft_refusal_at_the_attempt_ceiling_is_still_revivable(store: SqliteStore) -> None:
    """The regression the review reproduced, and the third time this premise has broken.

    `_settle` derived POISONED from `attempts >= max_attempts` alone. A craft gate refuses
    at *any* attempt number — deliberately, since the check sits ahead of the budget — so a
    refusal landing on the last attempt was indistinguishable there from a spent budget. The
    unit poisoned: unrevivable, absent from `jobs --status parked`, its derived job id burnt,
    and its exception labelled "attempt budget spent" about a budget that was not what
    stopped it. Three claims this change added were false in exactly that case.

    Driven through real ticks rather than hand-seeded attempts: two genuinely short drafts
    burn attempts 1 and 2 on `LENGTH_MOVEMENT`, and the third clears shape and meets the
    craft gate.
    """
    registry, _ = registry_with_sequence("Too short.", "Too short.", PROSE)
    book_scoped(store)
    with_a_failing_craft_gate(store)
    conductor = conductor_for(store, registry)

    outcomes = [conductor.tick(START + index * 300.0).outcome for index in range(3)]

    assert outcomes == [
        TickOutcome.JOB_FAILED,
        TickOutcome.JOB_FAILED,
        TickOutcome.JOB_PARKED,
    ]
    job = store.load_job("draft-1")
    assert job.attempts == 3, "the ceiling really was reached"
    assert job.status is JobStatus.PARKED, "not POISONED — the budget is not what stopped it"
    assert [j.job_id for j in store.jobs_by_status(JobStatus.PARKED)] == ["draft-1"]
    store.revive("draft-1")
    assert store.load_job("draft-1").status is JobStatus.QUEUED


def test_a_retryable_veto_at_the_ceiling_still_poisons(store: SqliteStore) -> None:
    """The other direction of the same fix. Making a craft park revivable must not make an
    exhausted attempt budget revivable, which is what `POISONED` is for."""
    registry, _ = registry_with("Too short.")
    book_scoped(store)
    with_a_failing_craft_gate(store)
    conductor = conductor_for(store, registry)

    for index in range(3):
        conductor.tick(START + index * 300.0)

    assert store.load_job("draft-1").status is JobStatus.POISONED


def test_a_craft_refusal_files_no_exception(store: SqliteStore) -> None:
    """§4.2 reserves escalation for what policy could not resolve, and a craft refusal is
    policy *resolving*. Filing one anyway would put every refusal in the queue a human is
    asked to clear — the director interruption `PARKABLE` was chosen over `ESCALATE` to
    avoid, arriving one layer below the choice."""
    registry, _ = registry_with(PROSE)
    book_scoped(store)
    with_a_failing_craft_gate(store)
    conductor_for(store, registry).tick(START)

    assert [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.EXCEPTION_RAISED
    ] == []
    day = store.read_log()[0].event.created_at[:10]
    assert store.digest(day).get("exceptions_raised", 0) == 0
    assert store.digest(day)["jobs_parked"] == 1


# -- the duplicate-scene refusal, through the loop ----------------------------------------


def _written(seed: str, words: int = 300) -> str:
    return " ".join(f"{seed}{index}" for index in range(words))


def _book_with_one_written_scene() -> Revision:
    """scene-1 already accepted, scene-2 empty and draftable."""
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
                content=_written("alpha"),
            ),
            Node(
                logical_id="scene-2",
                kind=NodeKind.SCENE,
                position_key="020",
                parent_logical_id="book",
            ),
        ],
    )


def _seed_duplicate_job(store: SqliteStore) -> Revision:
    revision = _book_with_one_written_scene()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    payload = {
        "revision_id": revision.revision_id,
        "logical_id": "scene-2",
        "prompt": "Draft the second scene.",
        "book_id": BOOK_ID,
        "branch_id": BRANCH_ID,
    }
    store.enqueue(
        Job(
            job_id="draft-dupe",
            job_kind=SCENE_DRAFT,
            payload=payload,
            input_digest=input_digest_for(payload),
        )
    )
    return revision


def test_a_scene_that_copies_another_is_refused_and_the_beat_parks_revivably(
    store: SqliteStore,
) -> None:
    """§19.1's rule applied to the newest gate: **a gate is not finished when it refuses
    correctly; it is finished when the operator can get past it.**

    Book Zero's second live run produced no duplicates at all — maximum pairwise similarity
    0.131 across fourteen scenes — so the in-loop path could not be observed by pointing a
    model at it. The gate is validated against the stored run by replay; this is the part
    replay cannot show, driven deterministically instead.

    **The tick sequence is `JOB_FAILED` then `JOB_PARKED`, and the second half is the design
    rather than a shortfall.** `CONTINUITY_BREACH` is classified `RETRYABLE`, so attempt 1's
    refusal is charged against the unit and issues a retry — but the finding it produced now
    *stands* against the beat, and the pre-flight gate parks attempt 2 before spending a
    second generation on it. Slice 9 measured that trade at 12 calls and 8,599 tokens before
    against 3 and 1,912 after, and
    `test_a_scene_contradicting_established_canon_is_refused_and_writes_nothing` pins the
    identical sequence for the contradiction detector. So a duplicate costs **one** generation
    and then waits for a human, revivably, which is what the operator's route is for.
    """
    registry, provider = registry_with_sequence(_written("alpha"), _written("beta"))
    _seed_duplicate_job(store)
    conductor = conductor_for(store, registry)

    outcomes = [conductor.tick(START + index).outcome for index in range(2)]
    assert outcomes == [TickOutcome.JOB_FAILED, TickOutcome.JOB_PARKED]
    assert provider.calls == 1, "the park costs no second generation"

    [refused, parked] = store.decisions_for_job("draft-dupe")
    assert refused.outcome is Outcome.RETRY, "the ladder classifies a copy as retryable"
    assert Veto.CONTINUITY_BREACH in {v for g in refused.gates for v in g.vetoes}
    assert any(
        gate.rule_or_critic_id == "integrity.findings.v0" and not gate.passed
        for gate in refused.gates
    )
    assert parked.outcome is Outcome.PARK
    assert any(
        gate.rule_or_critic_id == "integrity.standing.v0" and not gate.passed
        for gate in parked.gates
    ), "the second refusal is the pre-flight one, reached in front of the work"

    # And the copy is nowhere: the beat's node is still empty rather than holding it.
    assert store.load_revision(refused.base_revision_id).node("scene-2").content is None


def test_dismissing_a_duplicate_finding_lets_the_beat_be_written(
    store: SqliteStore,
) -> None:
    """The operator's way past it, which is the half that makes the gate finished.

    Walking this is what this project records as the thing that actually catches defects —
    §19.1 twice. Dismiss the finding, revive the unit, and the next generation lands: the
    provider's second answer is different prose and nothing refuses it.
    """
    registry, provider = registry_with_sequence(_written("alpha"), _written("beta"))
    _seed_duplicate_job(store)
    conductor = conductor_for(store, registry)
    conductor.tick(START)
    conductor.tick(START + 1)

    [finding] = [
        item
        for item in store.findings(BOOK_ID, BRANCH_ID)
        if item.rule_or_critic_id == DUPLICATE_RULE
    ]
    # What `litharness dismiss` writes: the operator saying this one is deliberate. A
    # legitimate recap is the false positive this gate can produce, and this is the route
    # past it — the same verb the golden fixtures' negative controls need.
    store.set_finding_status(finding.finding_id, FindingStatus.ACCEPTED_INTENTIONAL)
    store.revive("draft-dupe")

    conductor.tick(START + 2)

    # Asserted on the book rather than on `decisions_for_job(...)[-1]`, which is not the
    # chronological last: that query orders by `attempt`, and `revive` resets the counter, so
    # the post-revive acceptance is written at a *lower* attempt than the park that preceded
    # it. `test_dismissing_the_finding_then_reviving_lets_the_beat_through` asserts on the
    # node for the same reason.
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    landed = head.node("scene-2").content
    assert landed is not None and landed.startswith("beta"), (
        "dismissing the finding did not unblock the beat"
    )
    assert provider.calls == 2, "and it cost exactly one more generation"
    assert any(
        decision.outcome is Outcome.ACCEPT
        for decision in store.decisions_for_job("draft-dupe")
    )


def test_the_duplicate_refusal_is_attributable_like_every_other_mutation(
    store: SqliteStore,
) -> None:
    """§19's integrity clause reaches refusals as well as acceptances: a candidate refused by
    this gate leaves a recorded decision naming the rule and carrying its evidence, so
    "why was this scene not written" is a query rather than a guess."""
    registry, _ = registry_with_sequence(_written("alpha"), _written("beta"))
    _seed_duplicate_job(store)
    conductor_for(store, registry).tick(START)

    [refusal] = store.decisions_for_job("draft-dupe")
    [gate] = [g for g in refusal.gates if g.rule_or_critic_id == "integrity.findings.v0"]
    assert not gate.passed
    # The count is in the gate's detail and the evidence in the finding it summarises.
    stored = store.findings(BOOK_ID, BRANCH_ID)
    [finding] = [f for f in stored if f.rule_or_critic_id == DUPLICATE_RULE]
    assert finding.blocks and finding.deterministic
    assert "scene-1" in finding.message
    assert "alpha0" in finding.message
