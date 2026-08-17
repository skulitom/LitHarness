"""§61 Add 3: plan-level search licensed by calibration.

The tests that matter most are the ones that catch a tournament *appearing* to work.
`test_losers_never_reach_commit_revision_and_the_lineage_stays_linear` is the important
one: K candidates drafted against one frozen base could each be committed, each
overwriting the head — six accepted decisions, one scene of prose, no error anywhere
(§21's documented failure). Only the lineage length and the revision count distinguish a
tournament from a fork, so that is what the test asserts.

The judge path is exercised only with a synthetic calibration, deliberately: no
PREFERENCE calibration for `judge.span_select.v0` exists in production, the path ships
dormant behind that check, and the synthetic row in these tests is the only thing that
may open it — the gate being the license is the design under test, not a gap in it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.plan_search import (
    JUDGE_METRIC_ID,
    PLAN_SEARCH,
    SPAN_SELECT,
    PlanSearchOutputError,
    _alternatives,
    judge_license,
    make_plan_search_handler,
    make_span_select_handler,
    plan_search_job_id,
    span_select_job,
    span_select_job_id,
)
from litharness.application.planner import make_plan_selector
from litharness.application.repair import (
    calibration_licenses,
    make_repair_handler,
    repair_job_for,
)
from litharness.domain.budget import BudgetPolicy, Spend
from litharness.domain.budget import check as budget_check
from litharness.domain.calibration import (
    Calibration,
    Direction,
    EvidenceClass,
    Grain,
    calibration_id_for,
)
from litharness.domain.candidates import (
    CandidateStatus,
    SpanCandidate,
    candidate_id_for,
    evidence_complete,
    select_winner,
    sibling_samples,
)
from litharness.domain.draft import gate_draft
from litharness.domain.events import EventType, payload_digest
from litharness.domain.findings import Finding as DomainFinding
from litharness.domain.findings import Severity, Status
from litharness.domain.generation import (
    CompletionRequest,
    CompletionResult,
    Resolution,
    Usage,
)
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.nodes import NodeKind
from litharness.domain.plans import scene_plan_for
from litharness.domain.policy import GateKind, Outcome, VerdictSource
from litharness.domain.preference import (
    INTERNAL_PROTOCOL,
    PairVerdict,
    pair_verdicts_digest_for,
)
from litharness.domain.revision import Revision, new_book, node_version_id
from litharness.domain.text import canonicalize, content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision, span_for

START = 1_760_000_000.0
TICK = 300.0
STAMP = "2026-08-17T00:00:00Z"
PREMISE = "A courier in a debt-ledger city must clear a guild debt before it compounds."

#: A second book for the parked-span-never-stalls test. Higher than BOOK_ID so
#: least-progressed-first visits the parked book before this one.
BOOK_B = "44444444-4444-5444-8444-444444444444"
BRANCH_B = "55555555-5555-5555-8555-555555555555"

STATEMENTS = [
    "Kestrel delivers a summons to the Guild counting-house and is made to wait.",
    "The ledger clerk names her debt aloud in front of the queue.",
    "She takes an off-books courier run to the dye works to cover the interest.",
]


def prose_for(statement: str) -> str:
    """Distinct, gate-clearing prose per alternative — the fixture half of the claim."""
    line = (
        f"Kestrel moves through the ward. {statement} "
        "The lantern gutters and the ledger waits for its entry."
    )
    return " ".join([line] * 4)


class _Named:
    def __init__(self, name: str) -> None:
        self.name = name


class ScriptedGenerator:
    """One stub, three request shapes: alternatives, judge verdicts, candidate drafts.

    Dispatch is on the requested schema rather than on call order, because the handlers
    under test are entitled to reorder their calls without the suite noticing — what the
    suite pins is which calls were made at all (`draft_calls`, `judge_calls`).
    """

    def __init__(
        self,
        alternatives: Sequence[str] = (),
        *,
        judge: str = "first",
        replacement: str = "Rook tallied the coins once more",
    ) -> None:
        self.alternatives = list(alternatives)
        self.judge = judge
        self.replacement = replacement
        self.requests: list[CompletionRequest] = []

    def resolve(self, call_class: str = "generation"):  # type: ignore[no-untyped-def]
        return _Named("stub"), Resolution("stub")

    def reset_health(self) -> None:  # pragma: no cover - conductor courtesy
        return None

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        properties = (request.schema or {}).get("properties", {})
        if "alternatives" in properties:
            parsed = {"alternatives": [{"statement": s} for s in self.alternatives]}
            result = CompletionResult(
                text="{}", provider="stub", model="stub-v1",
                usage=Usage(100, 300), parsed=parsed, schema_requested=True,
            )
        elif "verdict" in properties:
            result = CompletionResult(
                text="{}", provider="stub", model="stub-v1",
                usage=Usage(60, 10), parsed={"verdict": self.judge},
                schema_requested=True,
            )
        elif "replacement" in properties:
            result = CompletionResult(
                text="{}", provider="stub", model="stub-v1",
                usage=Usage(80, 40), parsed={"replacement": self.replacement},
                schema_requested=True,
            )
        else:
            statement = request.prompt.rsplit(" This scene: ", 1)[-1]
            result = CompletionResult(
                text=prose_for(statement), provider="stub", model="stub-v1",
                usage=Usage(200, 500),
            )
        return result, Resolution("stub")

    @property
    def draft_calls(self) -> list[CompletionRequest]:
        return [r for r in self.requests if r.schema is None]

    @property
    def judge_calls(self) -> list[CompletionRequest]:
        return [
            r
            for r in self.requests
            if "verdict" in (r.schema or {}).get("properties", {})
        ]


@pytest.fixture
def store(tmp_path) -> SqliteStore:  # type: ignore[no-untyped-def]
    return SqliteStore.open(tmp_path / "search.db")


def a_book(
    store: SqliteStore, *, book_id: str = BOOK_ID, branch_id: str = BRANCH_ID
) -> Revision:
    revision = new_book(book_id, branch_id, title="Book", scenes=6)
    store.commit_revision(revision, created_at=STAMP)
    store.record_plan_items(
        book_id,
        branch_id,
        [
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text=PREMISE,
                authority=lc.PlanAuthority.CANONICAL_IN_PROSE,
                locked=True,
            )
        ],
        created_at=STAMP,
    )
    return revision


def search_job(store: SqliteStore, revision: Revision, logical_id: str = "scene-1") -> Job:
    """A `plan_search` job shaped as the selector mints it, for direct handler tests."""
    epoch = store.plan_epoch(revision.book_id, revision.branch_id)
    plan = store.plan_revision(revision.book_id, revision.branch_id)
    assert plan is not None
    payload: dict[str, object] = {
        "revision_id": revision.revision_id,
        "book_id": revision.book_id,
        "branch_id": revision.branch_id,
        "logical_id": logical_id,
        "prompt": "CONTEXT.\n\nNow write scene one of six. Dramatic function: setup.",
        "system": "You are drafting one scene of a novel.",
        "profile": "default",
        "plan_revision_id": plan.plan_revision_id,
        "plan_epoch": epoch,
        "selected_by": {
            "ordinal": 1,
            "of_total": 6,
            "plan_epoch": epoch,
            "story_order_key": "s1",
        },
    }
    job_id = plan_search_job_id(revision.book_id, revision.branch_id, logical_id, epoch)
    return Job(
        job_id=job_id,
        job_kind=PLAN_SEARCH,
        payload=payload,
        input_digest=input_digest_for(payload),
        attempts=1,
        status=JobStatus.RUNNING,
    )


def _conductor(store: SqliteStore, gen: ScriptedGenerator, **kwargs) -> Conductor:  # type: ignore[no-untyped-def]
    from litharness.application.plan_search import (
        make_plan_search_handler as search_handler,
    )

    return Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        select=make_plan_selector(project_id=PROJECT_ID, plan_search=True, **kwargs),
        handlers={
            PLAN_SEARCH: search_handler(gen, store, PROJECT_ID),
            SPAN_SELECT: make_span_select_handler(gen, store, PROJECT_ID),
            SCENE_DRAFT: make_scene_draft_handler(gen, store, PROJECT_ID),
        },
    )


def _answer_for(store: SqliteStore, preferred_address: str | None) -> int:
    """Answer every pending internal sample; prefer `preferred_address` where present.

    A pair not containing the preferred member is answered TIE, which counts nothing
    under the internal frame's declared DROP policy but still completes the evidence.
    """
    answered = 0
    for sample in store.pair_samples(pending_only=True):
        if sample.protocol_id != INTERNAL_PROTOCOL.protocol_id:
            continue
        if preferred_address is None or sample.left_addr == preferred_address:
            verdict = PairVerdict.PREFER_FIRST
        elif sample.right_addr == preferred_address:
            verdict = PairVerdict.PREFER_SECOND
        else:
            verdict = PairVerdict.TIE
        assert store.record_pair_verdict(
            sample.sample_id, verdict, at=STAMP, by="reader-1", recognized=False
        )
        answered += 1
    return answered


def _judge_calibration(
    store: SqliteStore,
    *,
    expires_at: str | None = None,
    threshold: float = 0.5,
    measured_at: str = STAMP,
) -> Calibration:
    """The synthetic license: a current PREFERENCE row ON the selection task.

    Its digest is the answered pair-verdict digest at mint time (Add 1's staleness
    wiring), which for a fresh store is the digest over the empty verdict set.
    `threshold` and `measured_at` are parameters so a test can record a *second*,
    distinct measurement — the id derives from what was measured, so two rows need to
    have measured something different.
    """
    answered = [s for s in store.pair_samples() if s.verdict is not None]
    digest = pair_verdicts_digest_for(answered)
    calibration = Calibration(
        calibration_id=calibration_id_for(
            JUDGE_METRIC_ID,
            threshold,
            digest,
            direction=Direction.BELOW,
            correct=17,
            holdout_size=50,
            flagged=17,
            selection_family_size=1,
            clusters=3,
            evidence_class=EvidenceClass.PREFERENCE,
            grain=Grain.UNIT,
        ),
        metric_id=JUDGE_METRIC_ID,
        holdout_size=50,
        threshold=threshold,
        direction=Direction.BELOW,
        verdicts_digest=digest,
        measured_at=measured_at,
        evidence_class=EvidenceClass.PREFERENCE,
        grain=Grain.UNIT,
        expires_at=expires_at,
        flagged=17,
        correct=17,
        selection_family_size=1,
        clusters=3,
    )
    assert store.record_calibration(calibration)
    return calibration


# --- the distinctness gate ---------------------------------------------------------------


def test_k_way_collapse_is_refused_by_the_distinctness_gate() -> None:
    """K collapsed alternatives are one plan drafted K times — the exact sampler-variation
    crutch this design refuses — so the gate refuses them before any draft is paid for."""
    collapsed = [STATEMENTS[0], f"  {STATEMENTS[0].upper()}  ", STATEMENTS[2]]
    with pytest.raises(PlanSearchOutputError, match="more than once"):
        _alternatives({"alternatives": [{"statement": s} for s in collapsed]}, 3)


def test_a_wrong_count_of_alternatives_is_refused() -> None:
    with pytest.raises(PlanSearchOutputError, match="exactly 3"):
        _alternatives({"alternatives": [{"statement": STATEMENTS[0]}]}, 3)


def test_a_collapsed_tournament_retries_without_spending_a_single_draft(
    store: SqliteStore,
) -> None:
    """The refusal is one call's spend, not K+1: the distinctness gate sits between the
    plan call and the drafts, and `decide` classifies it as a fair second draw."""
    revision = a_book(store)
    gen = ScriptedGenerator(alternatives=[STATEMENTS[0]] * 3)
    handler = make_plan_search_handler(gen, store, PROJECT_ID)

    handler(search_job(store, revision), START)

    assert gen.draft_calls == [], "a collapsed search must not draft"
    assert len(gen.requests) == 1
    decision = store.latest_decision_for(
        plan_search_job_id(BOOK_ID, BRANCH_ID, "scene-1", 0)
    )
    assert decision is not None and decision.outcome is Outcome.RETRY
    assert store.span_candidates(BOOK_ID, BRANCH_ID) == []


# --- the K-times budget projection -------------------------------------------------------


def test_the_budget_projects_k_times_spend_before_the_first_call(
    store: SqliteStore,
) -> None:
    """A ceiling one draft would clear refuses the whole tournament up front — the map's
    named risk is a tournament that dies mid-flight after paying for part of itself, and
    the proof is that zero provider calls were made."""
    revision = a_book(store)
    gen = ScriptedGenerator(alternatives=STATEMENTS)
    tight = BudgetPolicy(max_tokens_per_day=50_000)
    handler = make_plan_search_handler(gen, store, PROJECT_ID, budget=tight)
    job = search_job(store, revision)

    events = handler(job, START)

    assert gen.requests == [], "the refusal must land before the first call"
    decision = store.latest_decision_for(job.job_id)
    assert decision is not None and decision.outcome is Outcome.PARK
    assert decision.gates[0].gate is GateKind.BUDGET
    assert decision.invocations == 0 and decision.total_tokens == 0
    assert [event.event_type for event in events] == [EventType.BUDGET_EXHAUSTED]
    assert store.span_candidates(BOOK_ID, BRANCH_ID) == []
    # The same ceiling admits ONE draft-sized call: what refused was the K projection.
    single = budget_check(
        tight,
        Spend(),
        provider="stub",
        prompt_chars=len(str(job.payload["prompt"])),
        max_output_tokens=4096,
    )
    assert single.allowed


# --- the tournament: candidates, sibling pairs, the park ---------------------------------


def _park_tournament(
    store: SqliteStore, gen: ScriptedGenerator | None = None
) -> tuple[Revision, Job, ScriptedGenerator]:
    revision = a_book(store)
    gen = gen or ScriptedGenerator(alternatives=STATEMENTS)
    handler = make_plan_search_handler(gen, store, PROJECT_ID)
    job = search_job(store, revision)
    handler(job, START)
    return revision, job, gen


def test_sibling_pairs_are_minted_both_orientations_at_c_k_2(store: SqliteStore) -> None:
    """3 candidates -> C(3,2)=3 unordered pairs -> 6 presented sibling rows, both
    orientations of every pair, all under the built-in internal frame."""
    _revision, job, _gen = _park_tournament(store)

    candidates = store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job.job_id)
    assert len(candidates) == 3
    assert all(c.status is CandidateStatus.CANDIDATE for c in candidates)

    samples = store.pair_samples()
    assert len(samples) == 6
    by_pair: dict[str, set[int]] = {}
    for sample in samples:
        assert sample.protocol_id == INTERNAL_PROTOCOL.protocol_id
        assert sample.book_id == BOOK_ID
        by_pair.setdefault(sample.pair_id, set()).add(sample.orientation)
    assert len(by_pair) == 3
    assert all(orientations == {0, 1} for orientations in by_pair.values())
    # And the queue can render them: every member address resolves to a corpus row.
    excerpt_ids = {excerpt.excerpt_id for excerpt in store.excerpts()}
    for sample in samples:
        assert sample.left_addr.removeprefix("exc:") in excerpt_ids
        assert sample.right_addr.removeprefix("exc:") in excerpt_ids


def test_an_unlicensed_tournament_parks_naming_the_awaited_evidence(
    store: SqliteStore,
) -> None:
    """The judge path is REFUSED without a current calibration — the settlement is a PARK
    whose reason (the exception queue's summary, via `_settle`) says exactly what evidence
    is awaited — and no judge call is ever made."""
    _revision, job, gen = _park_tournament(store)

    assert gen.judge_calls == []
    decision = store.latest_decision_for(job.job_id)
    assert decision is not None and decision.outcome is Outcome.PARK
    assert decision.reason is not None
    assert "awaiting reader verdicts on 3 sibling pair(s)" in decision.reason
    assert JUDGE_METRIC_ID in decision.reason
    # Aggregated spend: one plan call plus K drafts, on the ONE settlement decision.
    assert decision.invocations == 4
    assert decision.total_tokens > 0
    assert judge_license(store, "2026-08-17") is None


def test_a_replayed_tournament_converges_without_repaying_the_provider(
    store: SqliteStore,
) -> None:
    """Reclaim-and-replay (the 600s lease risk): the decision landed atomically with the
    candidates, so the re-run finds both and returns without a single new call."""
    _revision, job, gen = _park_tournament(store)
    calls = len(gen.requests)

    handler = make_plan_search_handler(gen, store, PROJECT_ID)
    events = handler(replace(job, attempts=2), START + TICK)

    assert events == []
    assert len(gen.requests) == calls
    assert len(store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job.job_id)) == 3


# --- winner arithmetic -------------------------------------------------------------------


def _hand_candidates(count: int = 3) -> list[SpanCandidate]:
    out = []
    for index in range(count):
        text = canonicalize(prose_for(STATEMENTS[index]))
        out.append(
            SpanCandidate(
                candidate_id=candidate_id_for(
                    text=text,
                    statement=STATEMENTS[index],
                    alternative_index=index,
                    base_revision_id="rev-base",
                    job_id="plansearch-hand",
                ),
                job_id="plansearch-hand",
                book_id=BOOK_ID,
                branch_id=BRANCH_ID,
                logical_id="scene-1",
                alternative_index=index,
                statement=STATEMENTS[index],
                text=text,
                base_revision_id="rev-base",
                plan_epoch=0,
                created_at=STAMP,
            )
        )
    return out


def _answered(candidates: list[SpanCandidate], prefer: SpanCandidate | None):
    """Both orientations of every pair, answered; `prefer` wins where present."""
    answered = []
    for sample in sibling_samples(candidates, sampled_at=STAMP):
        if prefer is None:
            verdict = PairVerdict.TIE
        elif sample.left_addr == prefer.address:
            verdict = PairVerdict.PREFER_FIRST
        elif sample.right_addr == prefer.address:
            verdict = PairVerdict.PREFER_SECOND
        else:
            verdict = PairVerdict.TIE
        answered.append(
            replace(sample, verdict=verdict, recognized=False, reader_id="reader-1")
        )
    return answered


def test_the_winner_is_the_highest_canonical_win_count() -> None:
    candidates = _hand_candidates()
    prefer = candidates[1]
    winner, counts = select_winner(candidates, _answered(candidates, prefer))
    assert winner.candidate_id == prefer.candidate_id
    # Preferred in both orientations against each of two rivals: four decisive wins.
    assert counts[prefer.candidate_id] == 4
    assert sum(counts.values()) == 4  # the rivals' pair was a tie, which counts nothing


def test_an_undecided_tournament_resolves_by_candidate_id() -> None:
    """All ties: zero decisive judgments everywhere, so the deterministic tie-break is
    the whole selection — by candidate id, a content address, repeatable anywhere."""
    candidates = _hand_candidates()
    winner, counts = select_winner(candidates, _answered(candidates, None))
    assert sum(counts.values()) == 0
    assert winner.candidate_id == min(c.candidate_id for c in candidates)


def test_evidence_needs_both_orientations_of_every_pair() -> None:
    candidates = _hand_candidates()
    answered = _answered(candidates, candidates[0])
    assert evidence_complete(candidates, answered)
    assert not evidence_complete(candidates, answered[:-1])


# --- the full human-path tournament under the conductor ----------------------------------


def test_losers_never_reach_commit_revision_and_the_lineage_stays_linear(
    store: SqliteStore,
) -> None:
    """The §21 proof, extended to a tournament: after a full search-draft-judge-commit
    cycle the store's history holds the import and exactly ONE new revision — the winner's
    — and the losers' rebuilt revision ids exist nowhere. Six accepted siblings would pass
    every per-scene assertion; only the history says whether the branch forked."""
    a_book(store)
    gen = ScriptedGenerator(alternatives=STATEMENTS)
    loop = _conductor(store, gen)

    first = loop.tick(START)
    assert first.outcome is TickOutcome.JOB_PARKED

    job_id = plan_search_job_id(BOOK_ID, BRANCH_ID, "scene-1", 0)
    candidates = store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job_id)
    preferred = next(c for c in candidates if c.alternative_index == 1)
    assert _answer_for(store, preferred.address) == 6

    second = loop.tick(START + TICK)
    assert second.outcome is TickOutcome.RAN_JOB
    assert second.job_id == span_select_job_id(BOOK_ID, BRANCH_ID, "scene-1", 0)

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    assert len(store.lineage(head.revision_id)) == 2, "the branch forked or stalled"
    assert head.node("scene-1").content == preferred.text
    row = store._connection.execute("SELECT COUNT(*) AS n FROM revisions").fetchone()
    assert int(row["n"]) == 2, "a loser reached commit_revision"
    base = store.load_revision(preferred.base_revision_id)
    for loser in candidates:
        if loser.candidate_id == preferred.candidate_id:
            continue
        rebuilt = gate_draft(base, "scene-1", loser.text)
        assert rebuilt.revision is not None
        with pytest.raises(KeyError):
            store.load_revision(rebuilt.revision.revision_id)

    after = store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job_id)
    statuses = {c.candidate_id: c.status for c in after}
    assert statuses.pop(preferred.candidate_id) is CandidateStatus.SELECTED
    assert set(statuses.values()) == {CandidateStatus.DISCARDED}

    # The winning statement reached the plan through ONE acceptance: single epoch bump.
    assert store.plan_epoch(BOOK_ID, BRANCH_ID) == 1
    item = scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1")
    assert item is not None and item.text == preferred.statement

    # The selection rationale is a non-blocking HUMAN annotation on the ACCEPT decision.
    decision = store.latest_decision_for(second.job_id)
    assert decision is not None and decision.outcome is Outcome.ACCEPT
    annotation = next(
        gate
        for gate in decision.gates
        if gate.rule_or_critic_id == "preference.span_select.v0"
    )
    assert not annotation.blocking
    assert annotation.verdict_source is VerdictSource.HUMAN
    assert annotation.detail is not None and preferred.candidate_id in annotation.detail


def test_a_second_tournament_extends_the_lineage_linearly(store: SqliteStore) -> None:
    """Two consecutive tournaments: two commits, three revisions, one line — the linear
    head lineage invariant holding under repeated K-way search."""
    a_book(store)
    gen = ScriptedGenerator(alternatives=STATEMENTS)
    loop = _conductor(store, gen)

    assert loop.tick(START).outcome is TickOutcome.JOB_PARKED
    _answer_for(store, None)
    assert loop.tick(START + TICK).outcome is TickOutcome.RAN_JOB

    # Scene 2's tournament mints under the bumped epoch (the winner's plan acceptance).
    third = loop.tick(START + 2 * TICK)
    assert third.outcome is TickOutcome.JOB_PARKED
    assert third.job_id == plan_search_job_id(BOOK_ID, BRANCH_ID, "scene-2", 1)
    _answer_for(store, None)
    assert loop.tick(START + 3 * TICK).outcome is TickOutcome.RAN_JOB

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    assert len(store.lineage(head.revision_id)) == 3
    drafted = [
        node.logical_id
        for node in head.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content
    ]
    assert drafted == ["scene-1", "scene-2"]


def test_a_parked_span_never_stalls_other_work(store: SqliteStore) -> None:
    """§4.2: the parked tournament is book A's one draft in flight, so book A's drafting
    waits on evidence — and the Conductor works elsewhere: book B proceeds on the very
    next tick instead of queueing behind A's verdicts."""
    a_book(store)
    a_book(store, book_id=BOOK_B, branch_id=BRANCH_B)
    gen = ScriptedGenerator(alternatives=STATEMENTS)
    loop = _conductor(store, gen)

    first = loop.tick(START)
    assert first.outcome is TickOutcome.JOB_PARKED
    assert first.job_id == plan_search_job_id(BOOK_ID, BRANCH_ID, "scene-1", 0)

    second = loop.tick(START + TICK)
    assert second.outcome is TickOutcome.JOB_PARKED
    assert second.job_id == plan_search_job_id(BOOK_B, BRANCH_B, "scene-1", 0)

    # Both books parked awaiting verdicts: honestly nothing to do.
    assert loop.tick(START + 2 * TICK).outcome is TickOutcome.NO_WORK


def test_winner_revision_rebuilds_to_the_same_content_address(
    store: SqliteStore,
) -> None:
    """Re-gating the stored winning text against the stored base reproduces the same
    revision id — the property that lets the tournament persist texts instead of
    revisions, and the reason a replayed selection converges on the same commit."""
    _revision, job, _gen = _park_tournament(store)
    candidate = store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job.job_id)[0]
    base = store.load_revision(candidate.base_revision_id)

    once = gate_draft(base, candidate.logical_id, candidate.text)
    again = gate_draft(base, candidate.logical_id, candidate.text)
    assert once.revision is not None and again.revision is not None
    assert once.revision.revision_id == again.revision.revision_id

    _answer_for(store, candidate.address)
    select = span_select_job(
        BOOK_ID, BRANCH_ID, candidate.logical_id, 0, search_job_id=job.job_id
    )
    handler = make_span_select_handler(ScriptedGenerator(), store, PROJECT_ID)
    handler(replace(select, attempts=1, status=JobStatus.RUNNING), START + TICK)

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == once.revision.revision_id


# --- staleness ---------------------------------------------------------------------------


def test_a_plan_epoch_bump_cancels_queued_tournaments(store: SqliteStore) -> None:
    """The extended filter: `plan_search` and `span_select` carry plan-derived frozen
    state exactly as `scene_draft` does, so a plan change cancels all three — and leaves
    a non-plan-derived kind untouched."""
    a_book(store)
    scoped = {"book_id": BOOK_ID, "branch_id": BRANCH_ID}
    for job_id, kind in (
        ("q-draft", "scene_draft"),
        ("q-search", PLAN_SEARCH),
        ("q-select", SPAN_SELECT),
        ("q-summary", "scene_summary"),
    ):
        assert store.enqueue(
            Job(job_id=job_id, job_kind=kind, payload=dict(scoped))
        )

    store.bump_plan_epoch(BOOK_ID, BRANCH_ID, at=STAMP, reason="test bump")

    assert store.load_job("q-draft").status is JobStatus.CANCELLED
    assert store.load_job("q-search").status is JobStatus.CANCELLED
    assert store.load_job("q-select").status is JobStatus.CANCELLED
    assert store.load_job("q-summary").status is JobStatus.QUEUED


def test_a_stale_tournament_discards_with_a_recorded_decision(
    store: SqliteStore,
) -> None:
    """The head moved while the span was parked (legal — a parked unit never stalls the
    queue). The candidates are evidence about a base that no longer exists; committing
    one would fork the branch, so the selection discards them all and says so."""
    revision, job, _gen = _park_tournament(store)
    moved = revision.replacing(
        [revision.node("scene-2").with_content("The gatekeeper wanted five more. " * 12)]
    )
    store.commit_revision(moved, created_at=STAMP)
    _answer_for(store, None)

    select = span_select_job(BOOK_ID, BRANCH_ID, "scene-1", 0, search_job_id=job.job_id)
    handler = make_span_select_handler(ScriptedGenerator(), store, PROJECT_ID)
    handler(replace(select, attempts=1, status=JobStatus.RUNNING), START + TICK)

    candidates = store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job.job_id)
    assert {c.status for c in candidates} == {CandidateStatus.DISCARDED}
    decision = store.latest_decision_for(select.job_id)
    assert decision is not None and decision.outcome is Outcome.ESCALATE
    assert decision.reason is not None and "stale" in decision.reason
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == moved.revision_id
    row = store._connection.execute("SELECT COUNT(*) AS n FROM revisions").fetchone()
    assert int(row["n"]) == 2, "a stale tournament committed anyway"


# --- the judge path ----------------------------------------------------------------------


def test_the_judge_path_is_licensed_only_by_a_current_preference_calibration(
    store: SqliteStore,
) -> None:
    """Dormant by construction: no row licenses nothing; an expired row licenses nothing;
    a current PREFERENCE row on the selection task licenses the judge."""
    assert judge_license(store, "2026-08-17") is None
    expired = _judge_calibration(
        store, expires_at="2026-01-01", threshold=0.45, measured_at="2026-01-01T00:00:00Z"
    )
    assert judge_license(store, "2026-08-17") is None
    current = _judge_calibration(store)
    assert expired.calibration_id != current.calibration_id
    license_row = judge_license(store, "2026-08-17")
    assert license_row is not None
    assert license_row.calibration_id == current.calibration_id


def test_a_licensed_judge_selects_through_the_same_pair_machinery(
    store: SqliteStore,
) -> None:
    """With the synthetic license: the tournament completes instead of parking, the
    selection is enqueued immediately, the judge's verdicts land as ordinary pair rows
    with the calibration id as reader provenance, and the rationale annotates the ACCEPT
    decision citing the calibration — never as a blocking gate."""
    a_book(store)
    calibration = _judge_calibration(store)
    gen = ScriptedGenerator(alternatives=STATEMENTS, judge="first")
    loop = _conductor(store, gen)

    first = loop.tick(START)
    assert first.outcome is TickOutcome.RAN_JOB, "a licensed tournament must not park"
    search_id = plan_search_job_id(BOOK_ID, BRANCH_ID, "scene-1", 0)
    settled = store.latest_decision_for(search_id)
    assert settled is not None and settled.outcome is Outcome.ACCEPT

    second = loop.tick(START + TICK)
    assert second.outcome is TickOutcome.RAN_JOB
    assert second.job_id == span_select_job_id(BOOK_ID, BRANCH_ID, "scene-1", 0)
    assert len(gen.judge_calls) == 6, "both orientations of every pair, one call each"

    samples = store.pair_samples()
    assert all(sample.verdict is not None for sample in samples)
    assert {sample.reader_id for sample in samples} == {calibration.calibration_id}
    assert all(sample.recognized is False for sample in samples)

    # "Prefer the presented-first passage" cancels across orientations, so the winner is
    # the deterministic tie-break — and the commit happened exactly once.
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and len(store.lineage(head.revision_id)) == 2
    candidates = store.span_candidates(BOOK_ID, BRANCH_ID, job_id=search_id)
    winner = min(
        (c for c in candidates), key=lambda c: c.candidate_id
    )
    assert head.node("scene-1").content == winner.text

    decision = store.latest_decision_for(second.job_id)
    assert decision is not None and decision.outcome is Outcome.ACCEPT
    annotation = next(
        gate for gate in decision.gates if gate.rule_or_critic_id == JUDGE_METRIC_ID
    )
    assert not annotation.blocking
    assert annotation.verdict_source is VerdictSource.CALIBRATED_CRITIC
    assert annotation.calibration_id == calibration.calibration_id


# --- the repair-license extension --------------------------------------------------------


def _finding(
    revision: Revision,
    logical_id: str = "scene-1",
    *,
    severity: Severity = Severity.MINOR,
    basis: str = lc.ConfidenceBasis.HEURISTIC.value,
    calibration_id: str | None = None,
    with_span: bool = True,
) -> DomainFinding:
    node = revision.node(logical_id)
    source: dict[str, object] = {}
    if with_span:
        span = span_for(node, 0, 28, node_version_id(node))
        source["primary_span"] = lc.to_jsonable(span)
    if calibration_id is not None:
        source["claim"] = {"calibration_id": calibration_id}
    return DomainFinding(
        finding_id=f"f-{payload_digest(source)[:20]}",
        category="craft",
        severity=severity,
        message="calibrated craft complaint",
        status=Status.OPEN,
        rule_or_critic_id="craft.test_metric.v0",
        logical_id=logical_id,
        confidence_basis=basis,
        source=source,
    )


def _craft_calibration(store: SqliteStore, *, expires_at: str | None = None) -> Calibration:
    calibration = Calibration(
        calibration_id=calibration_id_for(
            "craft.test_metric.v0",
            0.8,
            "digest-craft",
            direction=Direction.ABOVE,
            correct=17,
            holdout_size=50,
            flagged=17,
            selection_family_size=1,
            clusters=3,
            evidence_class=EvidenceClass.JUDGMENT,
            grain=Grain.UNIT,
        ),
        metric_id="craft.test_metric.v0",
        holdout_size=50,
        threshold=0.8,
        direction=Direction.ABOVE,
        verdicts_digest="digest-craft",
        measured_at=STAMP,
        evidence_class=EvidenceClass.JUDGMENT,
        grain=Grain.UNIT,
        expires_at=expires_at,
        flagged=17,
        correct=17,
        selection_family_size=1,
        clusters=3,
    )
    assert store.record_calibration(calibration)
    return calibration


def test_a_calibrated_span_finding_licenses_a_repair_and_an_uncalibrated_one_does_not(
    store: SqliteStore,
) -> None:
    """The predicate's one extension, both sides: span + current calibration licenses a
    non-blocking finding; span alone does not; and the original blocking+deterministic
    license stands untouched."""
    revision = make_revision()
    calibration = _craft_calibration(store)
    today = "2026-08-17"

    cited = _finding(revision, calibration_id=calibration.calibration_id)
    assert not cited.blocks, "the extension is about non-blocking findings"
    assert calibration_licenses(cited, store.calibrations(), today=today)
    licensed = repair_job_for(
        cited,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        revision_id=revision.revision_id,
        repair_depth=1,
        calibrated=True,
    )
    assert licensed is not None

    uncited = _finding(revision)
    assert not calibration_licenses(uncited, store.calibrations(), today=today)
    assert (
        repair_job_for(
            uncited,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            revision_id=revision.revision_id,
            repair_depth=1,
            calibrated=False,
        )
        is None
    )

    blocking = _finding(
        revision,
        severity=Severity.MAJOR,
        basis=lc.ConfidenceBasis.DETERMINISTIC.value,
    )
    assert (
        repair_job_for(
            blocking,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            revision_id=revision.revision_id,
            repair_depth=1,
        )
        is not None
    )


def test_the_license_requires_a_span_so_freeform_revision_stays_impossible(
    store: SqliteStore,
) -> None:
    """§1a.2 is load-bearing: a calibration without a located span licenses nothing,
    because without a span there is nothing `apply_patch` can license — the patch is
    still span-scoped and `licensed_by_finding_id`, never 'improve this'."""
    revision = make_revision()
    calibration = _craft_calibration(store)
    spanless = _finding(
        revision, calibration_id=calibration.calibration_id, with_span=False
    )
    assert calibration_licenses(spanless, store.calibrations(), today="2026-08-17")
    assert (
        repair_job_for(
            spanless,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            revision_id=revision.revision_id,
            repair_depth=1,
            calibrated=True,
        )
        is None
    )


def test_an_expired_or_selection_class_calibration_licenses_nothing(
    store: SqliteStore,
) -> None:
    """Current means current; and PREFERENCE evidence licenses selection between
    candidates, never a repair of one text — `veto_for`'s total-raise, reused."""
    revision = make_revision()
    expired = _craft_calibration(store, expires_at="2026-01-01")
    lapsed = _finding(revision, calibration_id=expired.calibration_id)
    assert not calibration_licenses(lapsed, store.calibrations(), today="2026-08-17")

    preference = _judge_calibration(store)
    relative = _finding(revision, calibration_id=preference.calibration_id)
    assert not calibration_licenses(relative, store.calibrations(), today="2026-08-17")


def test_a_calibrated_repair_flows_through_the_scoped_patch_path(
    store: SqliteStore,
) -> None:
    """End to end: a MINOR heuristic finding citing a current calibration reaches
    `apply_patch` as a span-scoped REPLACE_SPAN licensed by the finding id, and commits
    one child revision — the same bounded machinery every deterministic repair uses."""
    revision = make_revision()
    store.commit_revision(revision, created_at=STAMP)
    calibration = _craft_calibration(store)
    finding = _finding(revision, calibration_id=calibration.calibration_id)
    store.record_findings(BOOK_ID, BRANCH_ID, [finding], created_at=STAMP)

    job = repair_job_for(
        finding,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        revision_id=revision.revision_id,
        repair_depth=1,
        calibrated=calibration_licenses(
            finding, store.calibrations(), today="2026-08-17"
        ),
    )
    assert job is not None
    gen = ScriptedGenerator(replacement="Rook re-counted the coin stacks slowly")
    handler = make_repair_handler(gen, store, PROJECT_ID)
    handler(replace(job, attempts=1, status=JobStatus.RUNNING), START)

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id != revision.revision_id
    assert head.node("scene-1").content is not None
    assert head.node("scene-1").content.startswith("Rook re-counted")
    decision = store.latest_decision_for(job.job_id)
    assert decision is not None and decision.outcome is Outcome.ACCEPT


# --- the corpus stays uncontaminated -----------------------------------------------------


def test_tournament_excerpts_name_their_tournament_as_source(store: SqliteStore) -> None:
    """Candidates-as-corpus rows carry the tournament job in `source`, which is what the
    operator draw filters on to keep OUR prose off the comparator side of the external
    superiority frame."""
    _revision, job, _gen = _park_tournament(store)
    for excerpt in store.excerpts():
        assert excerpt.source == f"plan-search {job.job_id}"
        assert excerpt.genre == f"internal:{BOOK_ID}"


def test_candidate_text_round_trips_through_content_hash(store: SqliteStore) -> None:
    """The excerpt address in every sibling sample is the content hash of the stored
    candidate text — what makes the tournament's evidence auditable by arithmetic."""
    _revision, job, _gen = _park_tournament(store)
    for candidate in store.span_candidates(BOOK_ID, BRANCH_ID, job_id=job.job_id):
        assert candidate.address == f"exc:exc-{content_hash(candidate.text)[:24]}"
