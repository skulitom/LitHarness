"""The bounded variation session: what it is, what bounds it, and when it has stalled.

A variation session is a durable multi-attempt loop placed **in front of** the existing commit
path. One agent proposes a bounded edit, the deterministic gates judge it, the exact gate
vector comes back as diagnostics, and the agent proposes again — for as many attempts as the
session's own ceilings allow, and never one more. This module is the pure half: the vocabulary,
the identities, the ceiling arithmetic and the stall predicates. The provider calls, the store
and the Conductor wiring live in `application/variation.py`.

**It optimises nothing, and that is the design rather than a limitation of this first
version.** The loop it is modelled on (NVIDIA's AVO) works because its objective is ground
truth: a kernel is correct or it is not, a throughput is a measured number. This project has no
instrument entitled to order prose by quality — `research/quality-measurement/BRIEF.md` is the
ledger of twenty proxies that claimed to and died to a control — so a variation loop that
selected among valid candidates by any score would be a Goodhart machine wearing an audit
trail. `select_winner` exists one module over for the tournament, and nothing here resembles
it. Acceptance is lexicographic and only its first tier is in play: **mechanical feasibility**,
exactly as `gates_for_patch` and `decide` already define it, and the **first** candidate that
clears it is committed.

**Three properties this file is responsible for.**

*Every ceiling is separate and every refusal names one.* `check_limits` is total and ordered,
and a `LimitVerdict` carries the name of the ceiling that stopped the session. A fused budget
would answer "it ran out" for six situations that call for six different responses.

*Stalls are detected deterministically, not judged.* `detect_stall` reads only the session's own
attempt rows: the same patch proposed twice, or `REPEATED_FAILURE_LIMIT` consecutive attempts
refused by the same gate for the same veto, or the same number of unusable responses. It stops;
it never redirects. Choosing a *different strategy* in response to a stall is a supervisor's
job, and a supervisor is not built here — §4.2's failure mode is a parked unit, never a spin
loop, and stopping is what parks.

*Nothing here is a hidden conversation.* Everything the loop shows the model is re-rendered from
these values, so a session resumed after a restart sees what an uninterrupted one would have.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import litharness_contracts as lc

from litharness.domain.events import payload_digest
from litharness.domain.patch import PatchPolicy, Veto
from litharness.domain.policy import GateOutcome, patch_policy_digest

#: Consecutive identical failures before a session is declared stalled and closed.
#:
#: Three, and the number is inherited rather than invented: `Job.max_attempts` is 3 and
#: `MAX_AUTO_REPAIRS` is 3, both encoding this project's standing reading that a third
#: identical refusal is evidence about the *situation* rather than about the output. Two would
#: close a session that was one revision away from a legitimate second try at a transient
#: shape failure; four buys a fourth round trip to learn what the third already said. The
#: constant is shared by all three stall predicates so that "how many times is enough" has one
#: answer in this module rather than three.
REPEATED_FAILURE_LIMIT = 3


class VariationObjective(enum.StrEnum):
    """What a session is for. Exactly one member, and the enum exists to keep it that way.

    Candidate-local repair is the only objective any instrument in this repository can judge
    without inventing a quality ordering. Context-packing search and reward-guided prose
    selection are named in the design as *later* objectives behind their own gates; giving the
    column an enum means adding one is a migration and a decision rather than a string literal
    somebody typed.
    """

    CANDIDATE_REPAIR = "candidate_repair"


class SessionStatus(enum.StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class SessionOutcome(enum.StrEnum):
    """How a session ended. Every member is terminal and every one is typed on purpose.

    `REFUSED_LIMIT` and `REFUSED_BUDGET` are separate because they are different facts about
    different budgets: the first is this session's own ceiling, which an operator raises by
    configuring the session, and the second is the day's ceiling in `domain/budget.py`, which
    resolves itself at midnight. Collapsing them would report a configuration problem for a
    calendar one, which is the shape of mistake `refused_before_work` exists to stop the
    Conductor making one layer down.
    """

    COMMITTED = "committed"
    REFUSED_LIMIT = "refused_limit"
    REFUSED_BUDGET = "refused_budget"
    STALLED_REPEAT_PATCH = "stalled_repeat_patch"
    STALLED_REPEATED_GATE = "stalled_repeated_gate"
    STALLED_MALFORMED = "stalled_malformed"
    STOPPED = "stopped"
    STALE_BASE = "stale_base"


class AttemptOutcome(enum.StrEnum):
    """Where one attempt stands.

    `PROPOSED` and `EVALUATED` are non-terminal, and they exist because one mediated action per
    Conductor tick means a proposal necessarily outlives the tick that made it. Without them
    proposing and evaluating could not be two actions, and an attempt superseded between the
    two would leave no row — making "every attempt is recorded, including failures" false for
    exactly the attempts that failed earliest.
    """

    PROPOSED = "proposed"
    EVALUATED = "evaluated"
    COMMITTED = "committed"
    REJECTED_GATE = "rejected_gate"
    REJECTED_BUDGET = "rejected_budget"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"

    @property
    def is_terminal(self) -> bool:
        return self not in {AttemptOutcome.PROPOSED, AttemptOutcome.EVALUATED}


class ActionKind(enum.StrEnum):
    """The entire action surface. Six members, and nothing else is reachable.

    The agent is the model speaking through the provider registry with structured output; it
    does not hold a shell, a filesystem, or any tool. It names one of these and the harness
    executes it. A response naming anything else is a malformed response to be counted and
    bounded — never a capability to add, because the value of a mediated surface is entirely in
    what it refuses.
    """

    INSPECT_LINEAGE = "inspect_lineage"
    CONSULT_KNOWLEDGE = "consult_knowledge"
    PROPOSE_CANDIDATE = "propose_candidate"
    EVALUATE_CANDIDATE = "evaluate_candidate"
    COMMIT = "commit"
    STOP = "stop"


class MalformedAction(ValueError):
    """The model's structured response did not name an executable action.

    Counted against the session rather than raised out of the handler: a model that answers
    badly is a fact about the attempt, and turning it into a job failure would spend the unit's
    Conductor attempts on something the session's own ceilings already bound.
    """


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """One well-formed action, with the arguments its kind requires and no others."""

    kind: ActionKind
    replacement: str | None = None
    strategy: str = ""
    reason: str = ""


def parse_action(payload: Mapping[str, Any] | None) -> ActionRequest:
    """Read one structured response into an action, or refuse it by name.

    Total over the mediated surface and strict about arguments: `PROPOSE_CANDIDATE` without
    replacement text is not a proposal of nothing, it is a response the harness cannot execute,
    and treating it as an empty patch would send `EMPTY_PATCH` back to the model as though it
    had proposed something. The distinction is what keeps the malformed counter meaningful.
    """
    if not isinstance(payload, Mapping):
        raise MalformedAction("the response carried no object the schema could be read from")
    raw = payload.get("action")
    if not isinstance(raw, str):
        raise MalformedAction("the response named no action")
    try:
        kind = ActionKind(raw)
    except ValueError as error:
        names = ", ".join(sorted(member.value for member in ActionKind))
        raise MalformedAction(
            f"{raw!r} is not a mediated action; the surface is {names}"
        ) from error

    replacement = payload.get("replacement")
    strategy = payload.get("strategy")
    reason = payload.get("reason")
    if kind is ActionKind.PROPOSE_CANDIDATE and not isinstance(replacement, str):
        raise MalformedAction("propose_candidate carried no replacement text")
    if kind is ActionKind.PROPOSE_CANDIDATE and not replacement:
        raise MalformedAction("propose_candidate carried empty replacement text")
    return ActionRequest(
        kind=kind,
        replacement=replacement if isinstance(replacement, str) else None,
        strategy=strategy.strip() if isinstance(strategy, str) else "",
        reason=reason.strip() if isinstance(reason, str) else "",
    )


@dataclass(frozen=True, slots=True)
class SessionLimits:
    """What one session may spend, on six axes it can exhaust independently.

    **Every default is checked against what a session can actually reach**, because a ceiling
    that cannot bind is a declared bar that cannot do what it says. The minimum committed
    session is three actions — propose, evaluate, commit — so `max_steps` of 12 leaves room for
    three full attempt cycles and change; `max_provider_calls` sits above it because calls are
    always at least steps and the reverse ordering would make `max_steps` unreachable;
    `max_evaluations` sits below it because a session can spend every step evaluating and
    should meet a gate-run ceiling before an action ceiling when it does.

    `max_cost_usd` is `None` by default for the reason `BudgetPolicy` gives about its own
    dollar ceiling: the pinned provider on a subscription reports no dollars and the
    deterministic fake reports zero, so a dollars-only bound fails open on exactly the
    providers this system runs on. It is offered, never relied on.
    """

    max_steps: int = 12
    max_provider_calls: int = 16
    max_evaluations: int = 8
    max_tokens: int = 120_000
    max_wall_seconds: float = 900.0
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        if self.max_steps < 3:
            raise ValueError(
                "a session needs at least three steps to propose, evaluate and commit "
                "once; a lower ceiling cannot reach a commit and would refuse every "
                "session on arrival"
            )
        if self.max_provider_calls < self.max_steps:
            raise ValueError(
                "provider calls are always at least steps, so a call ceiling below the "
                "step ceiling leaves max_steps unreachable"
            )
        for name in ("max_evaluations", "max_tokens"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive to bound anything")
        if self.max_wall_seconds <= 0.0:
            raise ValueError("max_wall_seconds must be positive to bound anything")
        if self.max_cost_usd is not None and self.max_cost_usd <= 0.0:
            raise ValueError(
                "a non-positive dollar ceiling refuses every session on arrival; None is "
                "how unbounded is expressed"
            )

    def digest_material(self) -> dict[str, object]:
        return {
            "max_steps": self.max_steps,
            "max_provider_calls": self.max_provider_calls,
            "max_evaluations": self.max_evaluations,
            "max_tokens": self.max_tokens,
            "max_wall_seconds": self.max_wall_seconds,
            "max_cost_usd": self.max_cost_usd,
        }


@dataclass(frozen=True, slots=True)
class LimitVerdict:
    """Whether the session may take another action, and which ceiling said otherwise."""

    allowed: bool
    limit: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class StallVerdict:
    """Whether the session is making progress, and the typed outcome if it is not."""

    stalled: bool
    outcome: SessionOutcome | None = None
    reason: str | None = None


def session_id_for(job_id: str, objective: VariationObjective) -> str:
    """Content address of one session: derived from the unit of work that opened it.

    Derived rather than minted so a replayed repair job converges onto the session it already
    opened instead of opening a second one beside it — the same discipline every id in this
    store keeps, and the one that makes a reclaimed lease safe.
    """
    return f"vsn-{payload_digest({'job_id': job_id, 'objective': objective.value})[:24]}"


def attempt_id_for(session_id: str, ordinal: int, patch_digest: str) -> str:
    """Content address of one attempt within one session."""
    material = payload_digest(
        {"session_id": session_id, "ordinal": ordinal, "patch_digest": patch_digest}
    )
    return f"vat-{material[:24]}"


def knowledge_id_for(
    objective: VariationObjective, target_key: str, gate_rule_id: str, veto: str
) -> str:
    """Content address of one knowledge claim, over what the claim is *about*.

    The evidence is deliberately outside the address. An item says "patches touching this
    target keep failing this gate for this reason"; the attempts that showed it are support
    that accumulates, and folding them into the id would mint a fresh near-duplicate row for
    every new observation of one standing fact.
    """
    material = payload_digest(
        {
            "objective": objective.value,
            "target_key": target_key,
            "gate_rule_id": gate_rule_id,
            "veto": veto,
        }
    )
    return f"vkn-{material[:24]}"


def patch_digest_for(patch: lc.BoundedPatch) -> str:
    """Content address of what a patch *does*, with its provenance metadata excluded.

    **The exclusion is the whole mechanism of the repeat detector.** A bounded patch carries an
    `ArtifactMeta` with a creation timestamp and a per-job artifact id, so hashing the whole
    object would give the same edit a fresh address on every attempt and "this patch was
    proposed twice" would be unobservable. What is hashed is the target, the base the patch
    expects to find, the licence it claims, and the ops themselves — which is exactly the set
    that makes two proposals the same proposal.
    """
    return payload_digest(
        {
            "logical_id": patch.target.logical_id,
            "base_version_id": patch.base_version_id,
            "base_content_sha256": patch.base_content_sha256,
            "licensed_by_finding_id": patch.licensed_by_finding_id,
            "ops": [
                [
                    op.kind.value,
                    int(op.target_span.start),
                    int(op.target_span.end),
                    op.new_text or "",
                ]
                for op in patch.ops
            ],
        }
    )


def variation_config_digest(policy: PatchPolicy, limits: SessionLimits) -> str:
    """Content address of everything that shaped a session's behaviour but its prompt.

    `patch_policy_digest` alone would answer "what mechanical limits judged this candidate"
    and say nothing about how many candidates the session was allowed to try — and a session
    that committed on its first attempt and one that committed on its eighth are not the same
    run, however identical the patch policy. Recording both under one digest is what lets a
    later reader tell a behaviour change from a configuration change, which is the whole job
    `policy_config_digest` was given on the decision record.
    """
    return payload_digest(
        {"patch_policy": patch_policy_digest(policy), "limits": limits.digest_material()}
    )


def failure_signature(gates: Sequence[GateOutcome]) -> str:
    """What this candidate failed, canonically, so two failures can be compared.

    Blocking failures only, sorted, rule id paired with veto. A gate that failed without naming
    a veto still contributes its rule id, because "the same gate keeps refusing and will not say
    why" is a repetition worth detecting rather than one worth ignoring.
    """
    parts: list[str] = []
    for gate in gates:
        if gate.passed or not gate.blocking:
            continue
        if gate.vetoes:
            parts.extend(f"{gate.rule_or_critic_id}:{veto.value}" for veto in gate.vetoes)
        else:
            parts.append(f"{gate.rule_or_critic_id}:unnamed")
    return "; ".join(sorted(set(parts)))


@dataclass(frozen=True, slots=True)
class VariationAttempt:
    """One proposed edit, the vector the gates returned for it, and how it ended."""

    attempt_id: str
    session_id: str
    ordinal: int
    base_revision_id: str
    patch_digest: str
    outcome: AttemptOutcome
    created_at: str
    parent_attempt_id: str | None = None
    strategy: str = ""
    evaluation: tuple[GateOutcome, ...] = ()
    diagnostics: str = ""
    provider: str | None = None
    model: str | None = None
    tokens: int = 0
    cost_usd: float | None = None
    evaluations: int = 0
    wall_ms: int = 0
    abandon_reason: str | None = None

    def __post_init__(self) -> None:
        expected = attempt_id_for(self.session_id, self.ordinal, self.patch_digest)
        if self.attempt_id != expected:
            raise ValueError(
                f"attempt_id {self.attempt_id} does not address this attempt"
            )

    @property
    def signature(self) -> str:
        return failure_signature(self.evaluation)

    @property
    def gates_passed(self) -> bool:
        """Whether every blocking gate that ran on this attempt passed.

        False for an attempt that was never evaluated, which is the safe direction: the commit
        action's precondition reads this, and an unevaluated candidate must not be committable
        on the strength of a gate run that did not happen.
        """
        blocking = [gate for gate in self.evaluation if gate.blocking]
        return bool(blocking) and all(gate.passed for gate in blocking)

    def failing_vetoes(self) -> tuple[tuple[str, Veto], ...]:
        """Rule id and veto for each blocking refusal, for the knowledge derivation."""
        return tuple(
            (gate.rule_or_critic_id, veto)
            for gate in self.evaluation
            if gate.blocking and not gate.passed
            for veto in gate.vetoes
        )


@dataclass(frozen=True, slots=True)
class VariationSession:
    """One bounded session: its target, its ceilings, its live counters, and its ending."""

    session_id: str
    objective: VariationObjective
    book_id: str
    branch_id: str
    logical_id: str
    base_revision_id: str
    opened_by_job_id: str
    opened_at: str
    opened_at_epoch: float
    limits: SessionLimits = field(default_factory=SessionLimits)
    finding_id: str | None = None
    status: SessionStatus = SessionStatus.OPEN
    steps: int = 0
    provider_calls: int = 0
    evaluations: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    malformed: int = 0
    lineage_inspections: int = 0
    consulted_item_ids: tuple[str, ...] = ()
    outcome: SessionOutcome | None = None
    outcome_detail: str | None = None
    closed_at: str | None = None

    @property
    def target_key(self) -> str:
        """What a knowledge item is about: this node, on this branch of this book."""
        return f"{self.book_id}/{self.branch_id}/{self.logical_id}"

    @property
    def is_open(self) -> bool:
        return self.status is SessionStatus.OPEN

    def spent(
        self,
        *,
        steps: int = 0,
        provider_calls: int = 0,
        evaluations: int = 0,
        tokens: int = 0,
        cost_usd: float = 0.0,
        malformed: int = 0,
    ) -> VariationSession:
        return replace(
            self,
            steps=self.steps + steps,
            provider_calls=self.provider_calls + provider_calls,
            evaluations=self.evaluations + evaluations,
            tokens=self.tokens + tokens,
            cost_usd=self.cost_usd + cost_usd,
            malformed=self.malformed + malformed,
        )

    def inspecting_lineage(self) -> VariationSession:
        return replace(self, lineage_inspections=self.lineage_inspections + 1)

    def consulting(self, item_ids: Sequence[str]) -> VariationSession:
        merged = tuple(sorted(set(self.consulted_item_ids) | set(item_ids)))
        return replace(self, consulted_item_ids=merged)

    def closed(
        self, outcome: SessionOutcome, *, at: str, detail: str | None = None
    ) -> VariationSession:
        return replace(
            self,
            status=SessionStatus.CLOSED,
            outcome=outcome,
            outcome_detail=detail,
            closed_at=at,
        )


def check_limits(
    session: VariationSession, *, now: float, projected_tokens: int = 0
) -> LimitVerdict:
    """Whether this session may take another action, ordered and total.

    **Checked in front of the work, so a refusal costs the day rather than the unit.** The
    order is cheapest-and-most-specific first: the two counters that describe what the session
    has *done* (steps, calls), then what it has *run* (evaluations), then what it has *spent*
    (tokens, dollars), then how long it has been alive. Wall time is last because it is the
    only axis that can trip without the session having done anything at all, and a session
    that has exhausted a real budget should be told which one rather than told it is old.

    `projected_tokens` is the over-estimate of the call about to be made, in the same spirit as
    `projected_tokens` in `domain/budget.py`: a ceiling checked against spend already recorded
    is a ceiling the next call is free to cross.
    """
    limits = session.limits
    if session.steps >= limits.max_steps:
        return LimitVerdict(
            False,
            "max_steps",
            f"{session.steps} of {limits.max_steps} variation steps spent",
        )
    if session.provider_calls >= limits.max_provider_calls:
        return LimitVerdict(
            False,
            "max_provider_calls",
            f"{session.provider_calls} of {limits.max_provider_calls} provider calls spent",
        )
    if session.evaluations >= limits.max_evaluations:
        return LimitVerdict(
            False,
            "max_evaluations",
            f"{session.evaluations} of {limits.max_evaluations} evaluations spent",
        )
    projected = session.tokens + max(projected_tokens, 0)
    if projected >= limits.max_tokens:
        return LimitVerdict(
            False,
            "max_tokens",
            f"{session.tokens} spent and {projected_tokens} projected against a ceiling "
            f"of {limits.max_tokens} tokens",
        )
    if limits.max_cost_usd is not None and session.cost_usd >= limits.max_cost_usd:
        return LimitVerdict(
            False,
            "max_cost_usd",
            f"${session.cost_usd:.4f} of ${limits.max_cost_usd:.4f} spent",
        )
    elapsed = now - session.opened_at_epoch
    if elapsed >= limits.max_wall_seconds:
        return LimitVerdict(
            False,
            "max_wall_seconds",
            f"{elapsed:.1f}s elapsed against a ceiling of {limits.max_wall_seconds:.1f}s",
        )
    return LimitVerdict(True)


def detect_stall(
    attempts: Sequence[VariationAttempt], *, malformed: int
) -> StallVerdict:
    """Whether this session has stopped making progress. Deterministic, and it only stops.

    Three predicates, all read off the session's own rows and none of them a judgment:

    **The same patch twice.** Two attempts sharing a `patch_digest` means the agent re-proposed
    an edit it has already been told about. The gates are pure, so the second run cannot
    disagree with the first; running it would buy a re-refusal at the price of a provider call.

    **`REPEATED_FAILURE_LIMIT` consecutive refusals with the same signature.** The same gate
    refusing for the same veto three times running is evidence about the situation — a locked
    node, a span the model cannot satisfy, a base that will not accept an edit of this shape —
    and the fourth attempt is not a fresh try, it is the third one again.

    **The same number of unusable responses.** Counted separately from gate failures because it
    is a different fault: nothing was proposed at all, so no gate has said anything and the
    signature predicate above can never fire on it. This one is a running total rather than a
    consecutive run, and deliberately the stricter reading: a session that produced three
    unusable answers scattered among its steps has the same problem as one that produced three
    together, and the interleaving would only hide it.

    What this deliberately does not do is choose a *different* strategy in response. That is a
    supervisor's decision and no supervisor is built here; a stall closes the session, and the
    §4.2 ladder parks the unit, which is the failure mode this project asks for.
    """
    if malformed >= REPEATED_FAILURE_LIMIT:
        return StallVerdict(
            True,
            SessionOutcome.STALLED_MALFORMED,
            f"{malformed} responses named no executable action",
        )

    seen: dict[str, str] = {}
    for attempt in attempts:
        prior = seen.get(attempt.patch_digest)
        if prior is not None and prior != attempt.attempt_id:
            return StallVerdict(
                True,
                SessionOutcome.STALLED_REPEAT_PATCH,
                f"attempt {attempt.attempt_id} re-proposes the patch already recorded as "
                f"{prior}; the gates are pure, so the verdict cannot change",
            )
        seen.setdefault(attempt.patch_digest, attempt.attempt_id)

    refused = [
        attempt for attempt in attempts if attempt.outcome is AttemptOutcome.REJECTED_GATE
    ]
    tail = refused[-REPEATED_FAILURE_LIMIT:]
    if len(tail) == REPEATED_FAILURE_LIMIT:
        signatures = {attempt.signature for attempt in tail}
        if len(signatures) == 1 and tail[0].signature:
            return StallVerdict(
                True,
                SessionOutcome.STALLED_REPEATED_GATE,
                f"{REPEATED_FAILURE_LIMIT} consecutive attempts refused by "
                f"{tail[0].signature}",
            )
    return StallVerdict(False)


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    """One durable claim about repeated mechanical failure, with the attempts behind it."""

    item_id: str
    objective: VariationObjective
    target_key: str
    gate_rule_id: str
    veto: str
    statement: str
    evidence: tuple[str, ...] = ()
    observations: int = 0
    consultations: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""

    def __post_init__(self) -> None:
        expected = knowledge_id_for(
            self.objective, self.target_key, self.gate_rule_id, self.veto
        )
        if self.item_id != expected:
            raise ValueError(f"item_id {self.item_id} does not address this claim")


def derive_knowledge(
    session: VariationSession, attempts: Sequence[VariationAttempt], *, at: str
) -> tuple[KnowledgeItem, ...]:
    """The knowledge this session's attempts support, minted deterministically.

    An item is owed once **two** attempts of the session have failed the same gate for the same
    veto. Two rather than three, and deliberately below `REPEATED_FAILURE_LIMIT`: the stall
    predicate ends the session at three, so a threshold of three would mint every item at the
    moment the session closed and no session could ever consult what it had itself learned. At
    two the record exists while the loop is still running, which is the difference between a
    knowledge base and a post-mortem.

    Nothing model-written enters an item. The statement is assembled from the gate's own rule
    id and veto, so what a later session reads is a fact the gates asserted, not a diagnosis
    somebody generated about them.
    """
    counts: dict[tuple[str, str], list[str]] = {}
    for attempt in attempts:
        for rule_id, veto in attempt.failing_vetoes():
            counts.setdefault((rule_id, veto.value), []).append(attempt.attempt_id)

    items: list[KnowledgeItem] = []
    for (rule_id, veto_value), evidence in sorted(counts.items()):
        unique = tuple(sorted(set(evidence)))
        if len(unique) < 2:
            continue
        items.append(
            KnowledgeItem(
                item_id=knowledge_id_for(
                    session.objective, session.target_key, rule_id, veto_value
                ),
                objective=session.objective,
                target_key=session.target_key,
                gate_rule_id=rule_id,
                veto=veto_value,
                statement=(
                    f"patches to {session.target_key} have been refused {len(unique)} times "
                    f"by {rule_id} for {veto_value}"
                ),
                evidence=unique,
                observations=len(unique),
                first_seen_at=at,
                last_seen_at=at,
            )
        )
    return tuple(items)


def render_lineage(attempts: Sequence[VariationAttempt], *, limit: int = 12) -> str:
    """The attempt history as the model sees it, rebuilt from rows.

    This is the answer to "where does the session's memory live": nowhere but the table. A
    resumed session renders the same text an uninterrupted one would have, and an auditor can
    reproduce byte for byte what the model was shown at any step.
    """
    if not attempts:
        return "No attempts recorded yet."
    lines = []
    for attempt in attempts[-limit:]:
        detail = attempt.diagnostics or "no gate diagnostics recorded"
        lines.append(
            f"#{attempt.ordinal} [{attempt.strategy or 'unclassified'}] "
            f"{attempt.outcome.value}: {detail}"
        )
    return "\n".join(lines)


def render_knowledge(items: Sequence[KnowledgeItem]) -> str:
    """Matching knowledge claims as the model sees them."""
    if not items:
        return "No knowledge items match this target."
    return "\n".join(
        f"- {item.statement} (evidence: {', '.join(item.evidence)})" for item in items
    )


def encode_ids(item_ids: Sequence[str]) -> str:
    """JSON for an id list column. One definition, so the two sides cannot drift."""
    return json.dumps(list(item_ids), sort_keys=False, ensure_ascii=False)


def decode_ids(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    loaded = json.loads(raw)
    return tuple(str(item) for item in loaded) if isinstance(loaded, list) else ()


__all__ = [
    "REPEATED_FAILURE_LIMIT",
    "ActionKind",
    "ActionRequest",
    "AttemptOutcome",
    "KnowledgeItem",
    "LimitVerdict",
    "MalformedAction",
    "SessionLimits",
    "SessionOutcome",
    "SessionStatus",
    "StallVerdict",
    "VariationAttempt",
    "VariationObjective",
    "VariationSession",
    "attempt_id_for",
    "check_limits",
    "decode_ids",
    "derive_knowledge",
    "detect_stall",
    "encode_ids",
    "failure_signature",
    "knowledge_id_for",
    "parse_action",
    "patch_digest_for",
    "render_knowledge",
    "render_lineage",
    "session_id_for",
    "variation_config_digest",
]
