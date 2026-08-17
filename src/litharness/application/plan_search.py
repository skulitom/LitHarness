"""Plan-level search (§61 Add 3): K alternative beat-plans per span, drafted and judged.

Selection pressure is applied at the structure level only. One `plan_search` job asks the
generator for K structurally distinct beat-plan statements for ONE span in ONE structured
call, drafts each alternative off the same frozen base, gates every candidate with the PURE
gates, persists the survivors as `span_candidates`, mints sibling pairs over them through
Add 1's engine, and parks the span pending selection. One `span_select` job — enqueued by
the selector when the parked tournament's evidence is ready, or immediately when the judge
path is licensed — picks the winner by pairwise judgment and commits it through the normal
accept path, exactly once.

**Why one call carries the K-way diversity.** The pinned provider drops sampler parameters
entirely (measured; providers map), so "K draws at different seeds" is K identical requests
wearing different numbers. Instructed distinctness in one structured call is the diversity
mechanism, and the deterministic distinctness gate — `_alternatives`, the `_statements`
pattern — refuses K-way collapse one layer before anything is drafted from it.

**Why losers can exist at all under §21.** One draft in flight per book is load-bearing
twice (`any_unfinished` in the selector, `_stale_base` in the draft handler), and K-way
drafting is compatible with it for exactly one reason: `gate_draft` is pure and returns an
un-persisted Revision, so K candidates are generated and gated off one frozen base inside
one job and NONE of them touches `commit_revision`. The winner's Revision is *rebuilt*
deterministically at selection time — content addressing makes re-gating the stored text
against the stored base reproduce the same revision id — and committed with the full gate
ladder re-run, stale-base check included. Losers are never passed to `commit_revision`;
they become `discarded` rows, kept as records.

**Why the judge ships dormant.** The judge path is permitted ONLY when a current
PREFERENCE-class calibration exists whose metric id names the selection task
(`judge.span_select.v0`), is current today, and whose digest matches the answered
pair-verdict set per Add 1's wiring. BRIEF §6.6 is the reason passive flag precision cannot
license this: retry is rejection sampling, selection shifts the deployment distribution
away from the passive one any flag calibration was measured on — so the calibration must be
ON the K-sibling winner-prediction task itself. No such row exists today; the human path is
the production path, and the gate being the license is the entire point.

**Budget discipline.** The whole tournament's spend — the plan call plus K draft calls, or
every judge call — is projected against the ceilings BEFORE the first call, because a
tournament that dies mid-flight after paying for part of it is the exact failure the
pre-flight gate exists to prevent. All candidate spend aggregates onto the job's final
decision, and the settlement decision is recorded LAST (the Conductor settles on
`latest_decision_for`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

import litharness_contracts as lc

from litharness.application.conductor import JobHandler

# Private siblings imported deliberately: the craft ladder and the seed modulus each have
# exactly one definition, and a second copy here is the drift `draft_block`'s "one function,
# two callers" rule exists to prevent. Same package, same layer.
from litharness.application.handlers import _SEED_MODULUS, _craft_ladder
from litharness.application.outline import TARGET_WORDS
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import PlanSearchStore, SpanSelectStore, TextGenerator
from litharness.application.repair import evaluation_job_for, summary_job_for
from litharness.domain.audit import DEFAULT_RATE, draw
from litharness.domain.beats import Beat, beats_for, template_for
from litharness.domain.budget import BudgetPolicy, BudgetVerdict, Spend
from litharness.domain.budget import check as budget_check
from litharness.domain.calibration import Calibration, EvidenceClass
from litharness.domain.candidates import (
    CandidateStatus,
    SpanCandidate,
    candidate_id_for,
    evidence_complete,
    select_winner,
    sibling_samples,
    tournament_samples,
)
from litharness.domain.craft import CraftMetric, measure
from litharness.domain.draft import DraftOutcome, DraftPolicy, draft_block, gate_draft
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.extraction import extract_state
from litharness.domain.findings import DetectorInput
from litharness.domain.findings import Finding as DomainFinding
from litharness.domain.generation import (
    PROFILES,
    CompletionRequest,
    CompletionResult,
    Sampler,
)
from litharness.domain.integrity import gate_integrity, gate_standing
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.nodes import NodeKind
from litharness.domain.patch import Veto
from litharness.domain.plan_refinement import (
    PlanConflict,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
)
from litharness.domain.plans import (
    premise_of,
    scene_plan_for,
    scene_plan_id_for,
    scene_plan_line,
)
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decide,
    decision_id_for,
    gates_for_draft,
)
from litharness.domain.preference import (
    INTERNAL_PROTOCOL,
    ComparisonExcerpt,
    PairSample,
    PairVerdict,
    pair_verdicts_digest_for,
)
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.text import content_hash

#: Job kinds this module answers to.
PLAN_SEARCH = "plan_search"
SPAN_SELECT = "span_select"

#: Between outline (300) and interpretive direction (500+): a tournament must not outrank
#: the director, and it must outrank ordinary scene drafting because it IS this span's
#: drafting — a scene_draft claimed first against the same span would fork the work.
PLAN_SEARCH_PRIORITY = 350

#: Above `PLAN_SEARCH_PRIORITY`: selection finishes spend the tournament already paid for,
#: so it is claimed before a fresh tournament starts paying for more.
SPAN_SELECT_PRIORITY = 360

#: Frozen generation profiles, recorded in provenance like every other model call here.
PROFILE = "planner.plan_search.v0"
SELECT_PROFILE = "selector.span_select.v0"

#: The metric id a judge calibration must carry to license the judge path. §6.6: the
#: calibration must be ON the K-sibling winner-prediction task, because selection shifts
#: the deployment distribution away from the passive one a flag calibration was measured
#: on — passive flag precision cannot license this, whatever its bound.
JUDGE_METRIC_ID = "judge.span_select.v0"

#: `ComparisonExcerpt.source` prefix for candidate texts registered as corpus rows. Named
#: so the operator draw (`cmd_pair_draw`) can keep tournament excerpts OUT of the external
#: comparison corpus — a candidate of ours drawn as the "published-human" side would
#: contaminate the superiority frame with a comparison against ourselves.
TOURNAMENT_SOURCE = "plan-search"

#: Chars of headroom the budget projection adds per candidate draft for the appended
#: statement line. Statements are asked for at ~`TARGET_WORDS` words; over-projecting is
#: the safe direction (the failure of guessing low is spending money the gate refused).
_STATEMENT_ALLOWANCE = 512

#: What one candidate draft call is projected to allow. Read off the request type's own
#: default rather than restated, so the projection cannot drift from the call it prices.
_DRAFT_MAX_OUTPUT = CompletionRequest(prompt="").max_output_tokens


class PlanSearchInputError(Exception):
    """The job payload does not describe work this module can do — fails the job."""


class PlanSearchOutputError(Exception):
    """The model's alternatives are not ones this handler can turn into a tournament."""


ALTERNATIVES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["alternatives"],
    "properties": {
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["statement"],
                "properties": {"statement": {"type": "string"}},
            },
        }
    },
}

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict"],
    "properties": {
        "verdict": {"type": "string", "enum": ["first", "second", "tie", "not_sure"]}
    },
}

_JUDGE_VERDICTS: dict[str, PairVerdict] = {
    "first": PairVerdict.PREFER_FIRST,
    "second": PairVerdict.PREFER_SECOND,
    "tie": PairVerdict.TIE,
    "not_sure": PairVerdict.NOT_SURE,
}


@dataclass(frozen=True, slots=True)
class PlanSearchPolicy:
    """How wide the search is. Named so the decision record can cite the value used.

    K defaults to 3 per the §61 acceptance experiment's design (K=3, search book vs
    no-search book). It is a policy field rather than a constant because the experiment's
    arms are operator-selectable, and an arm that could only be produced by editing code
    would be a control nobody could reproduce.
    """

    k: int = 3

    def __post_init__(self) -> None:
        if self.k < 2:
            raise ValueError(
                f"a plan search over {self.k} alternative(s) is not a search; "
                "K must be at least 2"
            )


def plan_search_job_id(
    book_id: str, branch_id: str, logical_id: str, epoch: int
) -> str:
    """Derived and epoch-versioned, for `outline_job_id`'s reason (§22 house style).

    `idempotency_key` is UNIQUE, so a poisoned tournament would burn its id forever and
    "search this span again" would be inexpressible; `replan` bumps the epoch and this
    follows it. The prompt and the base revision are excluded for `beat_job_id`'s reasons.
    """
    material = payload_digest(
        {
            "book_id": book_id,
            "branch_id": branch_id,
            "logical_id": logical_id,
            "plan_epoch": epoch,
        }
    )
    return f"plansearch-{material[:24]}"


def span_select_job_id(
    book_id: str, branch_id: str, logical_id: str, epoch: int
) -> str:
    """The selection sibling of `plan_search_job_id`, derived the same way."""
    material = payload_digest(
        {
            "book_id": book_id,
            "branch_id": branch_id,
            "logical_id": logical_id,
            "plan_epoch": epoch,
            "kind": SPAN_SELECT,
        }
    )
    return f"spanselect-{material[:24]}"


def span_select_job(
    book_id: str,
    branch_id: str,
    logical_id: str,
    plan_epoch: int,
    *,
    search_job_id: str,
) -> Job:
    """The selection unit for one parked tournament, ready to enqueue."""
    payload: dict[str, Any] = {
        "book_id": book_id,
        "branch_id": branch_id,
        "logical_id": logical_id,
        "plan_epoch": plan_epoch,
        "search_job_id": search_job_id,
    }
    job_id = span_select_job_id(book_id, branch_id, logical_id, plan_epoch)
    return Job(
        job_id=job_id,
        job_kind=SPAN_SELECT,
        idempotency_key=job_id,
        payload=payload,
        input_digest=input_digest_for(payload),
        priority=SPAN_SELECT_PRIORITY,
    )


def render_plan_search_request(
    premise: str,
    beat: Beat,
    *,
    current: str | None,
    others: Sequence[tuple[int, str]],
    k: int,
) -> CompletionRequest:
    """Freeze one span's context into ONE structured request for K alternatives.

    The other scenes' statements go in whole, for the outline's reason inverted: the model
    is being asked to make K statements differ from each other AND from the rest of the
    book, and it cannot avoid re-issuing scene 10's errand without seeing what scene 10 is
    for. Locked items are simply not offered as something to edit — the schema returns
    statements for this one scene and nothing else, and locked-item edits are refused at
    apply time anyway; the rule below tells the model not to lean on them.
    """
    prompt = json.dumps(
        {
            "premise": premise,
            "scene": {
                "ordinal": beat.ordinal,
                "of_total": beat.of_total,
                "dramatic_function": beat.function,
            },
            "current_statement": current,
            "other_scenes": [
                {"ordinal": ordinal, "statement": statement}
                for ordinal, statement in others
            ],
            "rules": [
                f"Return exactly {k} alternative statements for this one scene.",
                f"Each statement is about {TARGET_WORDS} words.",
                "State what happens in that scene: who acts, what they do, what changes.",
                "The alternatives must be structurally distinct from one another: "
                "different events, different errands. Not one statement re-worded.",
                "Each must also differ from every other scene's statement; nothing may "
                "be obtained, revealed, or resolved twice.",
                "Respect the dramatic function given for the scene.",
                "Do not write prose, dialogue, or description; this is an instruction "
                "to a writer, not the scene itself.",
                "Propose statements for this scene only. Do not propose changes to any "
                "other scene, constraint, or locked plan item.",
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return CompletionRequest(
        prompt=prompt,
        system=(
            "You are the Narrative Planner for a novel, searching plan-space for one "
            "scene. Given the premise, the scene's place in the book, and every other "
            "scene's statement, propose structurally distinct alternatives for what this "
            "scene does. Return only the requested JSON."
        ),
        schema=ALTERNATIVES_SCHEMA,
        max_output_tokens=2048,
        profile=PROFILE,
        call_class="generation",
    )


def _alternatives(payload: Mapping[str, Any], k: int) -> list[str]:
    """The model's K statements, or a refusal naming what was wrong.

    **Distinctness is checked here rather than hoped for** — the `_statements` pattern, and
    it is the one validation that is about the mechanism instead of the schema. K collapsed
    alternatives are not a search; they are one plan drafted K times, which spends K draft
    calls to produce the sampler variation this design explicitly refuses to rely on.
    """
    raw = payload.get("alternatives")
    if not isinstance(raw, list):
        raise PlanSearchOutputError("the answer must carry a list of alternatives")
    if len(raw) != k:
        raise PlanSearchOutputError(
            f"{len(raw)} alternative(s) returned; the search asked for exactly {k}"
        )
    statements: list[str] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise PlanSearchOutputError(f"alternative {index} is not an object")
        statement = entry.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise PlanSearchOutputError(f"alternative {index} has no statement")
        statements.append(statement.strip())
    folded = [" ".join(statement.lower().split()) for statement in statements]
    duplicates = sorted({value for value in folded if folded.count(value) > 1})
    if duplicates:
        raise PlanSearchOutputError(
            f"{len(duplicates)} statement(s) appear more than once across the {k} "
            "alternatives; a collapsed search is one plan drafted K times, and the "
            "distinctness gate refuses it before any draft is paid for"
        )
    return statements


def tournament_sampler(job: Job, profile: str, alternative_index: int) -> Sampler:
    """`draft_sampler`'s derivation with the alternative index in the seed material.

    K draws inside one attempt would otherwise share one seed (the map's named risk) —
    harmless while the prompts differ per alternative and moot on the pinned provider,
    which drops samplers entirely, but a seed that says which candidate it decoded is the
    correct record either way. Temperature 0 still seeds nothing, exactly as upstream.
    """
    sampler = PROFILES.get(profile, PROFILES["default"])
    if sampler.temperature == 0.0:
        return sampler
    material = f"{job.input_digest or job.job_id}:{job.attempts}:{alternative_index}"
    return replace(
        sampler,
        seed=int(sha256(material.encode()).hexdigest()[:16], 16) % _SEED_MODULUS,
    )


class _LicenseReader(Protocol):
    """The two reads a judge-license check needs, stated structurally."""

    def calibrations(self, *, metric_id: str | None = ...) -> list[Calibration]: ...

    def pair_samples(self, *, pending_only: bool = ...) -> list[PairSample]: ...


def judge_license(store: _LicenseReader, today: str) -> Calibration | None:
    """The current PREFERENCE calibration that licenses the judge path, or None.

    Three clauses, all per Add 1's wiring: the newest row for `judge.span_select.v0` must
    be PREFERENCE class (a judge licensed by anything else is licensed by evidence about a
    different task), current today, and its digest must equal the answered pair-verdict
    digest — the same staleness address `_craft_ladder` checks for preference rows, so one
    new verdict re-opens the license exactly as it re-opens every other calibration. The
    table holds no such row today, and that emptiness is the design: the gate is the
    license, and the path ships dormant behind it.
    """
    rows = store.calibrations(metric_id=JUDGE_METRIC_ID)
    if not rows:
        return None
    current = rows[0]  # newest-first: the current evidence; older rows are history
    if current.evidence_class is not EvidenceClass.PREFERENCE:
        return None
    if not current.is_current(today):
        return None
    answered = [
        sample for sample in store.pair_samples() if sample.verdict is not None
    ]
    if current.verdicts_digest != pair_verdicts_digest_for(answered):
        return None
    return current


def _judge_request(left: str, right: str, *, call_class: str) -> CompletionRequest:
    """One blinded presentation: the internal frame's question over two bare texts.

    Blinded means the judge sees prose and nothing else — no statements, no provenance, no
    addresses. Position-swapped comes free of charge: both orientations of a pair are
    separate sibling samples, so each presented order is its own call and the positional
    artifact stays measurable instead of assumed away. Mechanical profile, because
    conformance is the point of a verdict call and creativity is its failure mode.
    """
    prompt = (
        f"{INTERNAL_PROTOCOL.comparator_frame}\n\n"
        f"PASSAGE ONE:\n{left}\n\n"
        f"PASSAGE TWO:\n{right}\n\n"
        'Answer with JSON: {"verdict": one of "first", "second", "tie", "not_sure"}.'
    )
    return CompletionRequest(
        prompt=prompt,
        system=(
            "You are comparing two passages blind. Say which you would rather keep "
            "reading, or tie, or not_sure. Return only the requested JSON."
        ),
        schema=JUDGE_SCHEMA,
        max_output_tokens=256,
        profile="mechanical",
        call_class=call_class,
    )


def _judge_verdict(result: CompletionResult) -> PairVerdict | None:
    """The judge's answer as a verdict, or None for one the schema did not hold.

    None is not an abstention — `NOT_SURE` is an answer, a malformed reply is not — so a
    non-conforming judge call leaves its sample unanswered rather than laundering a parse
    failure into evidence. An unanswered sample leaves the evidence incomplete and the
    selection parks revivably, which is the honest state.
    """
    if result.parsed is None:
        return None
    verdict = result.parsed.get("verdict")
    return _JUDGE_VERDICTS.get(verdict) if isinstance(verdict, str) else None


@dataclass
class _SpendTally:
    """Aggregate candidate spend, folded onto the job's ONE settlement decision.

    The map's named risk: `PolicyDecision` assumes one candidate per attempt, and the
    Conductor settles on `latest_decision_for` — so a K-way handler must aggregate spend
    onto the final decision rather than recording K partial ones, or the digest
    under-reports cost and the tick mis-settles.
    """

    invocations: int = 0
    tokens: int = 0
    cost: float | None = None
    provider: str | None = None
    model: str | None = None

    def add(self, result: CompletionResult) -> None:
        self.invocations += result.invocations
        self.tokens += result.usage.total
        if result.cost_usd is not None:
            self.cost = (self.cost or 0.0) + result.cost_usd
        self.provider = result.provider
        self.model = result.model


def _tournament_budget(
    policy: BudgetPolicy,
    spent: Spend,
    provider: str,
    calls: Sequence[tuple[int, int]],
) -> BudgetVerdict:
    """Project EVERY call of a tournament against the ceilings before the first is made.

    `budget_check` prices one call; this walks the whole sequence, accumulating each
    call's projection into the spend the next is checked against — so a tournament either
    fits entirely or is refused entirely, and can never die mid-flight after paying for
    part of itself (the map's named risk). The first refusing verdict is returned so the
    recorded gate names the ceiling that refused.
    """
    projected = spent
    verdict = BudgetVerdict(True)
    for prompt_chars, max_output_tokens in calls:
        verdict = budget_check(
            policy,
            projected,
            provider=provider,
            prompt_chars=prompt_chars,
            max_output_tokens=max_output_tokens,
        )
        if not verdict.allowed:
            return verdict
        projected = projected.plus(invocations=1, tokens=verdict.projected_tokens)
    return verdict


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _beat_for(revision: Revision, logical_id: str) -> Beat:
    """This span's beat, derived from the frozen base the way the selector derived it."""
    for beat in beats_for(revision, template_for(revision)):
        if beat.logical_id == logical_id:
            return beat
    raise PlanSearchInputError(f"no beat {logical_id} in {revision.revision_id[:12]}")


def _order_key(selected_by: Mapping[str, Any]) -> str | None:
    value = selected_by.get("story_order_key")
    return str(value) if value else None


@dataclass(frozen=True, slots=True)
class _GatedCandidate:
    """One alternative's draft, judged by the pure gates and never persisted as prose."""

    outcome: DraftOutcome
    integrity: GateOutcome | None
    findings: tuple[DomainFinding, ...]
    extracted: tuple[lc.StateRecord, ...]

    @property
    def survived(self) -> bool:
        return self.outcome.accepted and (
            self.integrity is None or self.integrity.passed
        )


class _GateReads(Protocol):
    """What the shared candidate-gating pass reads. Both handlers' stores satisfy it."""

    def state_records(
        self,
        book_id: str,
        branch_id: str,
        *,
        subject: str | None = ...,
        before: str | None = ...,
    ) -> list[lc.StateRecord]: ...

    def plan_items(
        self,
        book_id: str,
        branch_id: str,
        *,
        kind: lc.PlanKind | None = ...,
    ) -> list[lc.PlanItem]: ...

    def promises(
        self, book_id: str, branch_id: str, *, open_only: bool = ...
    ) -> list[Any]: ...


def _gate_candidate(
    store: _GateReads,
    base: Revision,
    logical_id: str,
    text: str,
    *,
    conforms: bool,
    policy: DraftPolicy,
    project_id: str,
    book_id: str,
    branch_id: str,
    selected_by: Mapping[str, Any],
) -> _GatedCandidate:
    """The PURE gates over one candidate: `gate_draft`, then `gate_integrity` off the same
    frozen base with the same `DetectorInput` assembly the draft handler uses.

    Nothing here writes. The extracted records ride along so the winner's commit can reuse
    them, and the findings are returned rather than recorded: a refused candidate's
    node-scoped finding, made *standing*, would park the surviving candidates' commit for a
    defect only the loser has — the draft handler's record-on-refusal trade is correct for
    a retry of one candidate and wrong for a tournament of siblings.
    """
    outcome = gate_draft(base, logical_id, text, conforms=conforms, policy=policy)
    if not outcome.accepted or outcome.node_after is None:
        return _GatedCandidate(outcome, None, (), ())
    stored_records = tuple(store.state_records(book_id, branch_id))
    extracted = extract_state(
        outcome.node_after.content or "",
        known=stored_records,
        project_id=project_id,
        book_id=book_id,
        branch_id=branch_id,
        logical_id=logical_id,
        version_id=node_version_id(outcome.node_after),
        stated_order_key=_order_key(selected_by),
    )
    subject = DetectorInput(
        book_id=book_id,
        branch_id=branch_id,
        logical_id=logical_id,
        candidate=text,
        records=stored_records + extracted,
        plan_items=tuple(store.plan_items(book_id, branch_id)),
        prior_prose=tuple(
            (node.logical_id, node.content)
            for node in base.in_reading_order()
            if node.kind is NodeKind.SCENE
            and node.content
            and node.logical_id != logical_id
        ),
        ordinal=int(selected_by.get("ordinal", 0) or 0),
        of_total=int(selected_by.get("of_total", 0) or 0),
        open_promises=tuple(store.promises(book_id, branch_id, open_only=True)),
        story_order_key=_order_key(selected_by),
    )
    integrity, findings = gate_integrity(subject)
    return _GatedCandidate(outcome, integrity, tuple(findings), extracted)


def _refusal_gate(index: int, gated: _GatedCandidate) -> GateOutcome:
    """One refused alternative as a NON-blocking gate on the settlement decision.

    Non-blocking because the tournament's verdict is about the tournament, not about any
    one candidate: a refused alternative drops out and the survivors proceed. Recording it
    on the decision — veto names, alternative index, detail — is what "refused candidate
    outcomes" means here; it is deliberately not a `span_candidates` row (the table's three
    statuses are the selection's vocabulary, and a candidate the gates refused never
    entered the selection) and not a separate `PolicyDecision` (per-candidate decisions
    for one attempt would collide on `decision_id_for` and race the settlement read).
    """
    if not gated.outcome.accepted:
        details = "; ".join(record.detail for record in gated.outcome.vetoes)
        return GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="shape.draft.v0",
            passed=False,
            blocking=False,
            vetoes=gated.outcome.veto_kinds,
            detail=f"alternative {index}: {details or 'refused'}",
        )
    assert gated.integrity is not None  # survived is false, so integrity failed
    return replace(
        gated.integrity,
        blocking=False,
        detail=f"alternative {index}: {gated.integrity.detail or 'integrity refused'}",
    )


def make_plan_search_handler(
    registry: TextGenerator,
    store: PlanSearchStore,
    project_id: str,
    *,
    policy: PlanSearchPolicy | None = None,
    draft_policy: DraftPolicy | None = None,
    budget: BudgetPolicy | None = None,
    call_class: str = "generation",
) -> JobHandler:
    """Build the K-alternatives → K candidate drafts → parked tournament handler."""
    search_policy = policy or PlanSearchPolicy()
    shape_policy = draft_policy or DraftPolicy()
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        payload = job.payload
        try:
            revision_id = str(payload["revision_id"])
            logical_id = str(payload["logical_id"])
            prompt = str(payload["prompt"])
            book_id = str(payload["book_id"])
            branch_id = str(payload["branch_id"])
            plan_epoch = int(payload["plan_epoch"])
        except (KeyError, TypeError, ValueError) as error:
            raise PlanSearchInputError(
                f"job {job.job_id} payload lacks tournament inputs: {error}"
            ) from error
        system = payload.get("system")
        selected_by: Mapping[str, Any] = payload.get("selected_by") or {}
        profile = str(payload.get("profile", "default"))
        stamp = _timestamp(now)
        day = stamp[:10]

        base = store.load_revision(revision_id)

        def decision_event(decision: PolicyDecision) -> Event:
            return policy_decision_event(
                decision,
                project_id=project_id,
                created_at=stamp,
                book_id=book_id,
                branch_id=branch_id,
                revision_id=revision_id,
                actor=decision.provider or "litharness",
            )

        # **Crash-after-commit convergence, the decision-before-commit pattern.** The
        # tournament's outcome (candidates, samples, settlement decision) lands in ONE
        # transaction; a reclaimed replay that finds the decision AND the candidate rows
        # has nothing left to do and must not re-pay K+1 provider calls to discover that.
        prior = store.latest_decision_for(job.job_id)
        if (
            prior is not None
            and prior.outcome in {Outcome.ACCEPT, Outcome.PARK}
            and store.span_candidates(
                book_id, branch_id, logical_id=logical_id, job_id=job.job_id
            )
        ):
            return []

        # **Stale pre-flight, before any spend.** The extended cancel filter clears the
        # QUEUED case when the plan moves; this clears the claimed-then-raced case and the
        # hand-enqueue. ESCALATE for `_stale_base`'s reason: the payload is frozen, so a
        # retry re-reads the same stale inputs forever, and clearing it is an operator act
        # (`replan` mints fresh work under the next epoch).
        head = store.head(book_id, branch_id)
        current_epoch = store.plan_epoch(book_id, branch_id)
        if current_epoch != plan_epoch or (
            head is not None and head.revision_id != revision_id
        ):
            moved = (
                f"planned under epoch {plan_epoch} against {revision_id[:12]}, but the "
                f"book is at epoch {current_epoch} with head "
                f"{head.revision_id[:12] if head is not None else 'none'}"
            )
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.stale_base.v0",
                passed=False,
                vetoes=(Veto.STALE_BASE_VERSION,),
                detail=moved,
            )
            stale = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.ESCALATE,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                reason=moved,
            )
            store.record_decision(stale, decided_at=stamp)
            return [decision_event(stale)]

        # Structural vetoes, still before any spend: a span that cannot receive a draft
        # cannot receive K of them, and a locked scene-plan item would refuse the winning
        # proposal at apply time — after the whole tournament was paid for.
        blocked = draft_block(base, logical_id, policy=shape_policy)
        plan_items = tuple(store.plan_items(book_id, branch_id))
        item = scene_plan_for(plan_items, logical_id)
        if blocked is not None or (item is not None and item.locked):
            detail = (
                blocked.detail
                if blocked is not None
                else f"scene plan item for {logical_id} is locked; alternatives touch "
                "only unlocked SCENE_PLAN items"
            )
            vetoes = (blocked.veto,) if blocked is not None else (Veto.CONTENT_LOCKED,)
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.plan_search.v0",
                passed=False,
                vetoes=vetoes,
                detail=detail,
            )
            refused = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.ESCALATE,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                reason=detail,
            )
            store.record_decision(refused, decided_at=stamp)
            return [decision_event(refused)]

        # Standing findings park in front of the spend, exactly as they do for one draft:
        # K candidates can neither cause nor clear a finding already on record.
        standing = store.findings(
            book_id, branch_id, logical_id=logical_id, open_only=True
        )
        standing_gate = gate_standing(standing)
        if not standing_gate.passed:
            parked = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (standing_gate,)),
                outcome=Outcome.PARK,
                gates=(standing_gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                reason=standing_gate.detail,
            )
            store.record_decision(parked, decided_at=stamp)
            return [decision_event(parked)]

        premise = premise_of(plan_items)
        if premise is None:
            raise PlanSearchInputError(
                f"book {book_id} has no single premise; K alternatives for a book about "
                "nothing are K kinds of nothing"
            )
        beat = _beat_for(base, logical_id)
        others = tuple(
            (other.ordinal, plan.text)
            for other in beats_for(base, template_for(base))
            if other.logical_id != logical_id
            and (plan := scene_plan_for(plan_items, other.logical_id)) is not None
        )
        request = render_plan_search_request(
            premise,
            beat,
            current=item.text if item is not None else None,
            others=others,
            k=search_policy.k,
        )

        # **K-times spend, projected BEFORE the first call.** One plan call plus K draft
        # calls; a refusal here costs the day and never the unit (`refused_before_work`
        # recognises the budget gate and the Conductor gives the attempt back).
        provider, _ = registry.resolve(call_class)
        calls = [(len(request.prompt), request.max_output_tokens)] + [
            (len(prompt) + _STATEMENT_ALLOWANCE, _DRAFT_MAX_OUTPUT)
        ] * search_policy.k
        budget_verdict = _tournament_budget(
            budget_policy, store.spend_on(day), provider.name, calls
        )
        if not budget_verdict.allowed:
            gate = GateOutcome(
                gate=GateKind.BUDGET,
                rule_or_critic_id=f"budget.{budget_verdict.ceiling}.v0",
                passed=False,
                detail=budget_verdict.reason,
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.PARK,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                reason=budget_verdict.reason,
            )
            store.record_decision(refusal, decided_at=stamp)
            return [
                Event(
                    event_type=EventType.BUDGET_EXHAUSTED,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=revision_id,
                    payload={
                        "decision_id": refusal.decision_id,
                        "job_id": job.job_id,
                        "ceiling": budget_verdict.ceiling,
                        "reason": budget_verdict.reason,
                        "projected_calls": len(calls),
                    },
                )
            ]

        # The ONE structured call that carries the K-way diversity.
        spend = _SpendTally()
        result, resolution = registry.complete(request)
        spend.add(result)
        try:
            if not result.conforms or result.parsed is None:
                raise PlanSearchOutputError(
                    "provider response did not conform to the alternatives schema"
                )
            statements = _alternatives(result.parsed, search_policy.k)
        except PlanSearchOutputError as error:
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.plan_search.v0",
                passed=False,
                vetoes=(Veto.SHAPE_NOT_CONFORMING,),
                detail=str(error),
            )
            verdict, reason = decide(
                (gate,),
                job_id=job.job_id,
                attempt=job.attempts,
                max_attempts=job.max_attempts,
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=verdict,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                provider=result.provider,
                model=result.model,
                profile=PROFILE,
                fell_back_from=tuple(resolution.fell_back_from),
                invocations=spend.invocations,
                total_tokens=spend.tokens,
                cost_usd=spend.cost,
                policy_config_digest=_policy_digest(search_policy),
                reason=str(error) or reason,
            )
            store.record_decision(refusal, decided_at=stamp)
            return [decision_event(refusal)]

        # K candidate drafts off the same frozen base, gated pure. Losers never reach
        # `commit_revision` — that sentence is the whole §21 compatibility argument.
        survivors: list[tuple[int, str, _GatedCandidate]] = []
        refusal_gates: list[GateOutcome] = []
        for index, statement in enumerate(statements):
            draft_request = CompletionRequest(
                prompt=prompt + scene_plan_line(statement),
                system=system if isinstance(system, str) else None,
                profile=profile,
                call_class=call_class,
                sampler=tournament_sampler(job, profile, index),
            )
            draft_result, _ = registry.complete(draft_request)
            spend.add(draft_result)
            gated = _gate_candidate(
                store,
                base,
                logical_id,
                draft_result.text,
                conforms=draft_result.conforms,
                policy=shape_policy,
                project_id=project_id,
                book_id=book_id,
                branch_id=branch_id,
                selected_by=selected_by,
            )
            if gated.survived:
                survivors.append((index, statement, gated))
            else:
                refusal_gates.append(_refusal_gate(index, gated))

        if not survivors:
            union = tuple(
                sorted({veto for gate in refusal_gates for veto in gate.vetoes})
            ) or (Veto.SHAPE_NOT_CONFORMING,)
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.plan_search.v0",
                passed=False,
                vetoes=union,
                detail=f"all {search_policy.k} candidates were refused by the pure gates",
            )
            verdict, reason = decide(
                (gate, *refusal_gates),
                job_id=job.job_id,
                attempt=job.attempts,
                max_attempts=job.max_attempts,
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(
                    job.job_id, job.attempts, (gate, *refusal_gates)
                ),
                outcome=verdict,
                gates=(gate, *refusal_gates),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                provider=spend.provider,
                model=spend.model,
                profile=PROFILE,
                fell_back_from=tuple(resolution.fell_back_from),
                invocations=spend.invocations,
                total_tokens=spend.tokens,
                cost_usd=spend.cost,
                policy_config_digest=_policy_digest(search_policy),
                reason=reason,
            )
            store.record_decision(refusal, decided_at=stamp)
            return [decision_event(refusal)]

        candidates = tuple(
            SpanCandidate(
                candidate_id=candidate_id_for(
                    text=gated.outcome.node_after.content or "",
                    statement=statement,
                    alternative_index=index,
                    base_revision_id=revision_id,
                    job_id=job.job_id,
                ),
                job_id=job.job_id,
                book_id=book_id,
                branch_id=branch_id,
                logical_id=logical_id,
                alternative_index=index,
                statement=statement,
                text=gated.outcome.node_after.content or "",
                base_revision_id=revision_id,
                plan_epoch=plan_epoch,
                created_at=stamp,
            )
            for index, statement, gated in survivors
            if gated.outcome.node_after is not None
        )
        # Candidates-as-corpus: registering the texts is what lets the pair queue render
        # them for a reader, and the source names the tournament so the operator draw can
        # keep them out of the external comparison frame.
        excerpts = tuple(
            ComparisonExcerpt.from_text(
                candidate.text,
                source=f"{TOURNAMENT_SOURCE} {job.job_id}",
                genre=f"internal:{book_id}",
                era=day,
                added_at=stamp,
            )
            for candidate in candidates
        )
        samples = (
            sibling_samples(candidates, sampled_at=stamp)
            if len(candidates) > 1
            else ()
        )

        license_row = judge_license(store, day)
        follow_up: tuple[Job, ...] = ()
        if license_row is not None or len(candidates) == 1:
            # Judge licensed (or nothing to judge): selection is enqueued immediately and
            # the tournament completes. The judge itself runs in the selection job.
            follow_up = (
                span_select_job(
                    book_id,
                    branch_id,
                    logical_id,
                    plan_epoch,
                    search_job_id=job.job_id,
                ),
            )
            settled = Outcome.ACCEPT
            reason = (
                f"{len(candidates)} candidate(s) persisted; selection enqueued "
                + (
                    f"under judge calibration {license_row.calibration_id}"
                    if license_row is not None
                    else "for the sole survivor"
                )
            )
        else:
            # **The human path: the span parks awaiting selection.** PARK with attempts
            # remaining settles the unit PARKED — revivable, visible, never stalling the
            # queue (§4.2: a parked unit is skipped, the Conductor works elsewhere) — and
            # the exception the Conductor files carries this reason, so the queue message
            # says exactly what evidence is awaited.
            settled = Outcome.PARK
            reason = (
                f"parked for selection: awaiting reader verdicts on "
                f"{len(samples) // 2} sibling pair(s) "
                f"({len(samples)} presented sample(s)) over {len(candidates)} "
                f"candidate(s) for {logical_id}; the judge path is unlicensed — no "
                f"current PREFERENCE calibration for {JUDGE_METRIC_ID}"
            )

        summary_gate = GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="shape.plan_search.v0",
            passed=True,
            detail=(
                f"{search_policy.k} alternatives, {len(candidates)} candidate(s) "
                f"survived the pure gates, {len(samples) // 2} sibling pair(s) minted"
            ),
        )
        gates = (summary_gate, standing_gate, *refusal_gates)
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, gates),
            outcome=settled,
            gates=gates,
            job_id=job.job_id,
            logical_id=logical_id,
            base_revision_id=revision_id,
            attempt=job.attempts,
            provider=spend.provider,
            model=spend.model,
            profile=PROFILE,
            fell_back_from=tuple(resolution.fell_back_from),
            invocations=spend.invocations,
            total_tokens=spend.tokens,
            cost_usd=spend.cost,
            policy_config_digest=_policy_digest(search_policy),
            reason=reason,
        )
        # One transaction: protocol, corpus rows, candidates, sibling samples, follow-up
        # job and the settlement decision — recorded LAST in effect, because it lands
        # atomically with everything it settles and nothing is recorded after it.
        store.commit_tournament(
            protocol=INTERNAL_PROTOCOL,
            excerpts=excerpts,
            candidates=candidates,
            samples=samples,
            decision=decision,
            decided_at=stamp,
            jobs=follow_up,
        )
        return [decision_event(decision)]

    return handle


def _policy_digest(policy: PlanSearchPolicy) -> str:
    """Content address of what shaped this tournament, for `_policy_digest`'s reason one
    module over: editing K or the schema must read as a different configuration."""
    return payload_digest(
        {
            "profile": PROFILE,
            "k": policy.k,
            "target_words": TARGET_WORDS,
            "schema": ALTERNATIVES_SCHEMA,
        }
    )


def _selection_annotation(
    winner: SpanCandidate,
    counts: Mapping[str, int],
    field: Sequence[SpanCandidate],
    license_row: Calibration | None,
) -> GateOutcome:
    """The selection rationale, as a NON-blocking annotation on the winner's decision.

    Never a blocking gate: the judge is a model reporting on model output, and
    `PolicyDecision` refuses `MODEL_SELF_REPORT` on blocking gates by construction —
    `VerdictSource`'s constraints stand. The judged path cites its licensing calibration
    (`CALIBRATED_CRITIC`); the human path is `HUMAN`; a sole survivor selected itself and
    says so deterministically.
    """
    decisive = sum(counts.values())
    tally = ", ".join(
        f"{candidate_id[:12]}={counts[candidate_id]}" for candidate_id in sorted(counts)
    )
    detail = (
        f"selected {winner.candidate_id} with {counts.get(winner.candidate_id, 0)} "
        f"canonical win(s) of {decisive} decisive judgment(s) over {len(field)} "
        f"candidate(s); wins: {tally or 'none'}"
    )
    if len(field) == 1:
        return GateOutcome(
            gate=GateKind.CRAFT,
            rule_or_critic_id="preference.span_select.v0",
            passed=True,
            verdict_source=VerdictSource.DETERMINISTIC,
            blocking=False,
            detail=f"sole surviving candidate {winner.candidate_id}; nothing to judge",
        )
    if license_row is not None:
        return GateOutcome(
            gate=GateKind.CRAFT,
            rule_or_critic_id=JUDGE_METRIC_ID,
            passed=True,
            verdict_source=VerdictSource.CALIBRATED_CRITIC,
            blocking=False,
            detail=detail,
            calibration_id=license_row.calibration_id,
        )
    return GateOutcome(
        gate=GateKind.CRAFT,
        rule_or_critic_id="preference.span_select.v0",
        passed=True,
        verdict_source=VerdictSource.HUMAN,
        blocking=False,
        detail=detail,
    )


def _apply_winner_statement(
    store: SpanSelectStore,
    winner: SpanCandidate,
    *,
    project_id: str,
    created_at: str,
    actor: str,
) -> None:
    """The winning alternative's statement, applied via ONE `accept_plan_proposal`.

    Exactly one acceptance and therefore exactly one epoch bump — the map's risk: K
    sequential acceptances would raise `PlanConflict` on the second and, forced through,
    would cancel and re-mint the book's queue K times. Idempotent on replay: a plan whose
    statement already reads the winner's returns before proposing, so a crash between the
    winner's commit and this application cannot double-bump the epoch when replayed. A
    conflict (the plan moved while the tournament was judged) is durably recorded by the
    store as a conflicted proposal; the committed scene stands either way.
    """
    plan = store.plan_revision(winner.book_id, winner.branch_id)
    if plan is None:  # pragma: no cover - a searched span always had a plan
        return
    existing = scene_plan_for(plan.items, winner.logical_id)
    if existing is not None and (
        existing.text == winner.statement or existing.locked
    ):
        return
    item_id = (
        existing.logical_id
        if existing is not None
        else scene_plan_id_for(winner.logical_id)
    )
    edit = PlanEdit(
        action=(
            PlanEditAction.UPDATE if existing is not None else PlanEditAction.CREATE
        ),
        logical_id=item_id,
        item=lc.PlanItem(
            logical_id=item_id,
            kind=lc.PlanKind.SCENE_PLAN,
            text=winner.statement,
            authority=lc.PlanAuthority.INTENDED,
            locked=False,
            scope=lc.ResourceRef(
                project_id=project_id,
                book_id=winner.book_id,
                branch_id=winner.branch_id,
                logical_id=winner.logical_id,
                kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            ),
        ),
        reason=f"plan-search winner for {winner.logical_id}",
    )
    proposal = PlanProposal(
        base_plan_revision_id=plan.plan_revision_id,
        summary=f"plan-search winner for {winner.logical_id}",
        rationale=(
            "the tournament's pairwise evidence selected this alternative; the plan "
            "records the statement the committed scene was actually drafted from"
        ),
        expected_outcome="the span's statement matches its committed prose",
        edits=(edit,),
        profile=SELECT_PROFILE,
    )
    # A conflict is recorded durably as a conflicted proposal by commit_plan_application:
    # the plan moved while the tournament was judged, and the newer direction wins. The
    # scene is committed either way — the statement simply stays the plan's own.
    with suppress(PlanConflict):
        accept_plan_proposal(
            store,
            proposal,
            project_id=project_id,
            created_at=created_at,
            actor=actor,
        )


def make_span_select_handler(
    registry: TextGenerator,
    store: SpanSelectStore,
    project_id: str,
    *,
    draft_policy: DraftPolicy | None = None,
    budget: BudgetPolicy | None = None,
    call_class: str = "generation",
    audit_rate: float = DEFAULT_RATE,
    schedule_evaluation: bool = False,
    schedule_summary: bool = False,
    actor: str = "litharness",
) -> JobHandler:
    """Build the selection handler: judge if licensed, humans otherwise, one commit."""
    shape_policy = draft_policy or DraftPolicy()
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        payload = job.payload
        try:
            book_id = str(payload["book_id"])
            branch_id = str(payload["branch_id"])
            logical_id = str(payload["logical_id"])
            plan_epoch = int(payload["plan_epoch"])
            search_job_id = str(payload["search_job_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise PlanSearchInputError(
                f"job {job.job_id} payload lacks selection inputs: {error}"
            ) from error
        stamp = _timestamp(now)
        day = stamp[:10]

        rows = store.span_candidates(
            book_id, branch_id, logical_id=logical_id, job_id=search_job_id
        )
        if not rows:
            raise PlanSearchInputError(
                f"job {job.job_id} names tournament {search_job_id}, which persisted "
                "no candidates"
            )
        live = [row for row in rows if row.status is CandidateStatus.CANDIDATE]

        def decision_event(
            decision: PolicyDecision, *, revision_id: str | None = None
        ) -> Event:
            return policy_decision_event(
                decision,
                project_id=project_id,
                created_at=stamp,
                book_id=book_id,
                branch_id=branch_id,
                revision_id=revision_id or decision.base_revision_id,
                actor=decision.provider or actor,
            )

        prior = store.latest_decision_for(job.job_id)
        replayed = (
            prior is not None
            and prior.outcome is Outcome.ACCEPT
            and prior.resulting_revision_id is not None
        )
        if replayed and not live:
            return []  # committed and finalized; nothing left to converge
        if not live:
            # Already resolved without a commit (a stale discard on an earlier attempt,
            # then a revive). Nothing to select is a completed unit, not a failed one.
            done = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, ()),
                outcome=Outcome.ACCEPT,
                gates=(),
                job_id=job.job_id,
                logical_id=logical_id,
                attempt=job.attempts,
                profile=SELECT_PROFILE,
                reason=f"tournament {search_job_id} already resolved; no live candidate",
            )
            store.record_decision(done, decided_at=stamp)
            return [decision_event(done)]

        base_id = live[0].base_revision_id
        base = store.load_revision(base_id)

        if replayed:
            # Crash between the winner's commit and finalization: the arithmetic is
            # deterministic over the stored verdicts, so recompute and finish. The plan
            # application below returns early if it already landed.
            winner, _counts = select_winner(live, store.pair_samples())
            _apply_winner_statement(
                store, winner, project_id=project_id, created_at=stamp, actor=actor
            )
            for candidate in live:
                store.set_span_candidate_status(
                    candidate.candidate_id,
                    CandidateStatus.SELECTED
                    if candidate.candidate_id == winner.candidate_id
                    else CandidateStatus.DISCARDED,
                )
            return []

        # **A stale tournament is discarded with a recorded decision.** The head moved
        # while the span was parked (another span committed — legal, a parked unit never
        # stalls the queue) or the plan epoch advanced under a claimed job. The frozen
        # base is gone, so the candidates are evidence about a book that no longer
        # exists; committing one would fork the branch, which is §21's documented failure.
        head = store.head(book_id, branch_id)
        current_epoch = store.plan_epoch(book_id, branch_id)
        if current_epoch != plan_epoch or (
            head is not None and head.revision_id != base_id
        ):
            moved = (
                f"tournament {search_job_id} is stale: drafted under epoch {plan_epoch} "
                f"against {base_id[:12]}, but the book is at epoch {current_epoch} with "
                f"head {head.revision_id[:12] if head is not None else 'none'}; "
                f"{len(live)} candidate(s) discarded"
            )
            for candidate in live:
                store.set_span_candidate_status(
                    candidate.candidate_id, CandidateStatus.DISCARDED
                )
            gate = GateOutcome(
                gate=GateKind.SHAPE,
                rule_or_critic_id="shape.stale_base.v0",
                passed=False,
                vetoes=(Veto.STALE_BASE_VERSION,),
                detail=moved,
            )
            stale = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.ESCALATE,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=base_id,
                attempt=job.attempts,
                profile=SELECT_PROFILE,
                reason=moved,
            )
            store.record_decision(stale, decided_at=stamp)
            return [decision_event(stale)]

        # -- evidence -----------------------------------------------------------------
        spend = _SpendTally()
        license_row = judge_license(store, day) if len(live) > 1 else None
        if license_row is not None:
            pending = [
                sample
                for sample in tournament_samples(live, store.pair_samples())
                if sample.verdict is None
            ]
            if pending:
                texts = {candidate.address: candidate.text for candidate in live}
                requests = [
                    _judge_request(
                        texts[sample.left_addr],
                        texts[sample.right_addr],
                        call_class=call_class,
                    )
                    for sample in pending
                ]
                provider, _ = registry.resolve(call_class)
                budget_verdict = _tournament_budget(
                    budget_policy,
                    store.spend_on(day),
                    provider.name,
                    [(len(r.prompt), r.max_output_tokens) for r in requests],
                )
                if not budget_verdict.allowed:
                    gate = GateOutcome(
                        gate=GateKind.BUDGET,
                        rule_or_critic_id=f"budget.{budget_verdict.ceiling}.v0",
                        passed=False,
                        detail=budget_verdict.reason,
                    )
                    refusal = PolicyDecision(
                        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                        outcome=Outcome.PARK,
                        gates=(gate,),
                        job_id=job.job_id,
                        logical_id=logical_id,
                        base_revision_id=base_id,
                        attempt=job.attempts,
                        profile=SELECT_PROFILE,
                        reason=budget_verdict.reason,
                    )
                    store.record_decision(refusal, decided_at=stamp)
                    return [
                        Event(
                            event_type=EventType.BUDGET_EXHAUSTED,
                            project_id=project_id,
                            created_at=stamp,
                            book_id=book_id,
                            branch_id=branch_id,
                            revision_id=base_id,
                            payload={
                                "decision_id": refusal.decision_id,
                                "job_id": job.job_id,
                                "ceiling": budget_verdict.ceiling,
                                "reason": budget_verdict.reason,
                                "projected_calls": len(requests),
                            },
                        )
                    ]
                for sample, request in zip(pending, requests, strict=True):
                    judged, _resolution = registry.complete(request)
                    spend.add(judged)
                    verdict_value = _judge_verdict(judged)
                    if verdict_value is not None:
                        # The SAME pair-sample machinery humans use; reader_id is the
                        # judge's calibration id — provenance, not a person, and the
                        # write-once discipline (verdict IS NULL) holds unchanged.
                        store.record_pair_verdict(
                            sample.sample_id,
                            verdict_value,
                            at=stamp,
                            by=license_row.calibration_id,
                            recognized=False,
                            note=f"model judge under {license_row.calibration_id}",
                        )

        samples = store.pair_samples()
        if len(live) > 1 and not evidence_complete(live, samples):
            required = len(tournament_samples(live, samples))
            answered = sum(
                1
                for sample in tournament_samples(live, samples)
                if sample.verdict is not None
            )
            waiting = (
                f"awaiting verdicts: {answered} of {required} sibling sample(s) "
                f"answered for tournament {search_job_id}; the span stays parked and "
                "the selector re-enqueues selection when the evidence is complete"
            )
            parked = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, ()),
                outcome=Outcome.PARK,
                gates=(),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=base_id,
                attempt=job.attempts,
                provider=spend.provider,
                model=spend.model,
                profile=SELECT_PROFILE,
                invocations=spend.invocations,
                total_tokens=spend.tokens,
                cost_usd=spend.cost,
                reason=waiting,
            )
            store.record_decision(parked, decided_at=stamp)
            return [decision_event(parked)]

        winner, counts = select_winner(live, samples)

        # -- the winner, through the normal accept path -------------------------------
        # Standing findings first, in front of nothing this time (the spend is judged),
        # but standing between the tournament and the head exactly as it stands between
        # a planner and a draft: a finding on record refuses the commit revivably.
        standing = store.findings(
            book_id, branch_id, logical_id=logical_id, open_only=True
        )
        standing_gate = gate_standing(standing)
        if not standing_gate.passed:
            parked = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (standing_gate,)),
                outcome=Outcome.PARK,
                gates=(standing_gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=base_id,
                attempt=job.attempts,
                profile=SELECT_PROFILE,
                reason=standing_gate.detail,
            )
            store.record_decision(parked, decided_at=stamp)
            return [decision_event(parked)]

        # Rebuilt deterministically: re-gating the stored winning text against the stored
        # base reproduces the same content-addressed revision id — the property the
        # tournament's whole no-commit design rests on, and a pinned test asserts it.
        beat = _beat_for(base, logical_id)
        selected_by: dict[str, Any] = {
            "ordinal": beat.ordinal,
            "of_total": beat.of_total,
            "story_order_key": beat.story_order_key,
        }
        gated = _gate_candidate(
            store,
            base,
            logical_id,
            winner.text,
            conforms=True,
            policy=shape_policy,
            project_id=project_id,
            book_id=book_id,
            branch_id=branch_id,
            selected_by=selected_by,
        )
        outcome = gated.outcome
        gates = gates_for_draft(outcome)
        craft_metrics: tuple[CraftMetric, ...] = ()
        if outcome.accepted and gated.integrity is not None:
            gates = (*gates, standing_gate, gated.integrity)
            craft_metrics = measure(
                winner.text,
                [
                    node.content
                    for node in base.in_reading_order()
                    if node.kind is NodeKind.SCENE
                    and node.content
                    and node.logical_id != logical_id
                ],
            )
            gates = (
                *gates,
                *_craft_ladder(
                    store,
                    craft_metrics,
                    today=day,
                    words=len(winner.text.split()),
                ),
            )
        accepted = outcome.accepted and all(
            gate.passed for gate in gates if gate.blocking
        )
        gates = (*gates, _selection_annotation(winner, counts, live, license_row))

        if gated.findings:
            store.record_findings(
                book_id,
                branch_id,
                list(gated.findings),
                created_at=stamp,
                revision_id=base_id,
            )

        verdict, reason = decide(
            gates,
            job_id=job.job_id,
            attempt=job.attempts,
            max_attempts=job.max_attempts,
        )
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, gates),
            outcome=verdict,
            gates=gates,
            job_id=job.job_id,
            logical_id=logical_id,
            base_revision_id=base_id,
            resulting_revision_id=(
                outcome.revision.revision_id
                if accepted and outcome.revision is not None
                else None
            ),
            attempt=job.attempts,
            provider=spend.provider,
            model=spend.model,
            profile=SELECT_PROFILE,
            invocations=spend.invocations,
            total_tokens=spend.tokens,
            cost_usd=spend.cost,
            policy_config_digest=payload_digest(
                {"profile": SELECT_PROFILE, "judge": license_row is not None}
            ),
            reason=reason or decision_reason(winner, counts),
        )
        if not accepted:
            store.record_decision(decision, decided_at=stamp)
            failed = [gate for gate in gates if gate.blocking and not gate.passed]
            return [
                Event(
                    event_type=EventType.MANUSCRIPT_CANDIDATE_CREATED,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "job_id": job.job_id,
                        "logical_id": logical_id,
                        "accepted": False,
                        "candidate_id": winner.candidate_id,
                        "vetoes": [
                            veto.value for gate in failed for veto in gate.vetoes
                        ],
                    },
                ),
                decision_event(decision),
            ]

        assert outcome.revision is not None  # accepted implies a revision
        acceptance = Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=project_id,
            created_at=stamp,
            actor=spend.provider or actor,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=outcome.revision.revision_id,
            payload={
                "decision_id": decision.decision_id,
                "job_id": job.job_id,
                "logical_id": logical_id,
                "accepted": True,
                "chars": outcome.chars,
                "parent_revision_id": base_id,
                "candidate_id": winner.candidate_id,
                "search_job_id": search_job_id,
            },
        )
        commit_events = [acceptance]
        if gated.extracted:
            commit_events.append(
                Event(
                    event_type=EventType.STATE_CANDIDATES_EXTRACTED,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=outcome.revision.revision_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "logical_id": logical_id,
                        "count": len(gated.extracted),
                        "record_ids": sorted(
                            record.record_id for record in gated.extracted
                        ),
                    },
                )
            )
        follow_up_jobs: tuple[Job, ...] = ()
        if schedule_evaluation:
            follow_up_jobs = (
                evaluation_job_for(
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=outcome.revision.revision_id,
                    logical_id=logical_id,
                ),
            )
        if schedule_summary:
            follow_up_jobs = (
                *follow_up_jobs,
                summary_job_for(
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=outcome.revision.revision_id,
                    logical_id=logical_id,
                    content_hash=content_hash(winner.text),
                ),
            )
        store.commit_revision(
            outcome.revision,
            created_at=stamp,
            events=commit_events,
            state_records=gated.extracted,
            jobs=follow_up_jobs,
            decision=decision,
        )
        store.record_craft_metrics(
            outcome.revision.revision_id,
            logical_id,
            craft_metrics,
            measured_at=stamp,
        )
        audit_sample = draw(
            book_id=book_id,
            branch_id=branch_id,
            revision_id=outcome.revision.revision_id,
            logical_id=logical_id,
            sampled_at=stamp,
            rate=audit_rate,
        )
        if audit_sample is not None:
            store.record_audit_sample(audit_sample)

        # Finalize: ONE plan acceptance (single epoch bump), then the statuses. Losers
        # become discarded records; they were never passed to commit_revision.
        _apply_winner_statement(
            store, winner, project_id=project_id, created_at=stamp, actor=actor
        )
        for candidate in live:
            store.set_span_candidate_status(
                candidate.candidate_id,
                CandidateStatus.SELECTED
                if candidate.candidate_id == winner.candidate_id
                else CandidateStatus.DISCARDED,
            )
        return [decision_event(decision, revision_id=outcome.revision.revision_id)]

    return handle


def decision_reason(winner: SpanCandidate, counts: Mapping[str, int]) -> str:
    """One line for the accepted decision when the ladder itself had nothing to say."""
    return (
        f"tournament winner {winner.candidate_id} committed with "
        f"{counts.get(winner.candidate_id, 0)} canonical win(s)"
    )


__all__ = [
    "ALTERNATIVES_SCHEMA",
    "JUDGE_METRIC_ID",
    "PLAN_SEARCH",
    "PLAN_SEARCH_PRIORITY",
    "PROFILE",
    "SELECT_PROFILE",
    "SPAN_SELECT",
    "SPAN_SELECT_PRIORITY",
    "TOURNAMENT_SOURCE",
    "PlanSearchInputError",
    "PlanSearchOutputError",
    "PlanSearchPolicy",
    "judge_license",
    "make_plan_search_handler",
    "make_span_select_handler",
    "plan_search_job_id",
    "render_plan_search_request",
    "span_select_job",
    "span_select_job_id",
    "tournament_sampler",
]
