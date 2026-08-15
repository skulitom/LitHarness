"""The acceptance policy engine: §4.2's ladder, as a decision that can be recorded.

Slice 4 put gate results into an event payload dict, which was honest about being
provisional and useless as an audit surface — you could not ask "why was this accepted"
without parsing prose out of a free-form map. Contracts 1.1.0 added
`PolicyDecisionRecord`, so this module is the shape that fills it.

Three things here are decisions rather than mechanics, and each one is the kind that gets
silently invented if it is not written down.

**A veto that a retry cannot fix must not consume the retry budget.** `CONTENT_LOCKED`
means a human locked the node; `UNKNOWN_TARGET` means the job is wrong, not the output.
Retrying either burns budget to reach the same refusal three times and then parks the unit
with an attempts-exhausted message that hides the real cause. So vetoes are partitioned:
`RETRYABLE` earns another bounded attempt, `REGENERABLE` earns a fresh candidate, and
everything else escalates immediately with the veto as the reason.

**Every gate result carries where its verdict came from, and a blocking gate may not
believe the model that wrote the text.** MirrorBench's finding is that model self-report
is not a correctness signal, and PLAN.md §20.8 asks for exactly this discriminator. It is
enforced here rather than documented: `PolicyDecision.__post_init__` raises if a blocking
gate carries `MODEL_SELF_REPORT`, so the invariant fails loudly at construction instead of
quietly at review time.

**Passing gates are recorded too.** A decision listing only failures cannot distinguish a
candidate that cleared the full ladder from one that was never checked — and "which gates
ran" is the question an audit actually asks first.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain.draft import DraftOutcome, DraftPolicy
from litharness.domain.events import payload_digest
from litharness.domain.patch import PatchOutcome, PatchPolicy, Veto

#: Vetoes a bounded retry can plausibly fix: the model produced the wrong *output*.
#:
#: `CONTINUITY_BREACH` is classified here rather than escalated, and the reasoning is worth
#: keeping because it is the first veto in this set that is about the *book* rather than the
#: string. A blocking finding says the candidate contradicts established state — which is a
#: property of the text, produced against a context packet that already carried the state it
#: contradicts. So another attempt against the same packet is a fair second try, and after
#: `max_attempts` the unit parks and files an exception, which is where a defect the model
#: cannot write its way out of belongs. Escalating on attempt 1 instead would send a human
#: every scene the model fumbled once.
RETRYABLE: frozenset[Veto] = frozenset(
    {
        Veto.EMPTY_DRAFT,
        Veto.EMPTY_PATCH,
        Veto.SHAPE_NOT_CONFORMING,
        Veto.LENGTH_MOVEMENT,
        Veto.CONTINUITY_BREACH,
        # A patch that claimed too much of the node. Classified beside `LENGTH_MOVEMENT`
        # rather than beside the stale-input vetoes, and for the same reason: the inputs
        # were fine and the *output* overreached, so a second attempt against the same
        # located complaint is a fair try at a narrower one.
        Veto.CITED_SCOPE_EXCEEDED,
    }
)

#: Vetoes that mean the *candidate* was built against stale or malformed inputs. A fresh
#: candidate against a re-read base can fix these; repeating the same one cannot.
REGENERABLE: frozenset[Veto] = frozenset(
    {
        Veto.STALE_BASE_VERSION,
        Veto.STALE_BASE_CONTENT,
        Veto.SPAN_OUT_OF_RANGE,
        Veto.SPAN_HASH_MISMATCH,
        Veto.OVERLAPPING_SPANS,
        Veto.UNSUPPORTED_OP,
    }
)

#: Vetoes that end the unit *here*, without another generation and without an escalation.
#:
#: `CRAFT_BELOW_BAR` is the only member and the reasoning is the whole decision, so it is
#: recorded rather than implied. A promoted craft gate refuses prose that a calibrated metric
#: places on the failing side of its threshold. Each of the other three things the ladder
#: could do to that refusal is worse:
#:
#: **Retry is rejection sampling against the gate.** Another attempt against the same context
#: packet produces different text that is measured by the same metric, and the accepted
#: candidate is by construction the one that beat it. At `max_attempts` that is best-of-three
#: optimisation against a craft proxy — a weaker form of the coupling
#: [plan/craft-corpus.md](../../../plan/craft-corpus.md) §4.2 calls non-negotiable to prevent,
#: but the same shape, and it would arrive as a side effect of a retry class rather than as a
#: decision anyone took.
#:
#: **Escalation breaks the product claim.** A gate firing on 5% of scenes is one director
#: interruption per twenty accepted, in a system whose whole claim is that it runs without
#: one. §4.2 already reserves escalation for what *policy could not resolve*, and a craft
#: refusal is policy resolving: the scene does not go in.
#:
#: **Silently accepting is what the system does today.** That is the gap, not the fallback.
#:
#: Parking is the option that keeps all three properties. The refusal stands, the book
#: continues — findings are node-scoped for exactly this reason, so a weak scene 3 does not
#: stop scene 6 — and the parked unit is revivable, so the director's `revive` is the way
#: past it, as it already is for a standing finding.
#:
#: **What it does not yet do, stated because the first draft of this comment claimed it
#: did.** A parked unit is not an *unjudged sample*. `handlers` records craft metrics and
#: draws the §10.5 audit sample inside the acceptance branch, after `commit_revision` — a
#: refused candidate commits no revision, so it produces neither, and its text is discarded.
#: So the gate does not currently fill the audit queue as a by-product of refusing, which
#: would have been the best argument for this classification. Making it do so is not a
#: one-liner: `AuditSample` is keyed `sha256(revision_id, logical_id)` and a refused
#: candidate has no revision id, so it needs an address for text that was never accepted.
#: Recorded as a gap rather than fixed in passing, because what `verdicts_digest` content-
#: addresses would change with it.
PARKABLE: frozenset[Veto] = frozenset({Veto.CRAFT_BELOW_BAR})

# Everything else — CONTENT_LOCKED, UNKNOWN_TARGET, TARGET_HAS_NO_CONTENT,
# UNLICENSED_DELETION, PRESERVATION_BREACH — escalates. Deliberately the default: a veto
# nobody has classified should reach a human, not silently earn three more model calls.

#: Gates that run *before* the generation, by `rule_or_critic_id`. See `refused_before_work`:
#: membership here means a refusal costs the day rather than the unit, so a gate is added
#: only when retrying it is provably pointless — the condition cannot change because of
#: anything the candidate does. Budget is recognised by its `GateKind` rather than by id,
#: since every ceiling mints a rule id of its own (`budget.<ceiling>.v0`).
PRE_FLIGHT: frozenset[str] = frozenset({"integrity.standing.v0"})


class GateKind(enum.StrEnum):
    SHAPE = "shape"
    INTEGRITY = "integrity"
    CRAFT = "craft"
    BUDGET = "budget"

    def to_contract(self) -> lc.GateKind:
        return lc.GateKind(self.value)


class VerdictSource(enum.StrEnum):
    DETERMINISTIC = "deterministic"
    CALIBRATED_CRITIC = "calibrated_critic"
    UNCALIBRATED_CRITIC = "uncalibrated_critic"
    HUMAN = "human"
    #: Recorded so it can be refused, never so it can be trusted.
    MODEL_SELF_REPORT = "model_self_report"

    def to_contract(self) -> lc.VerdictSource:
        return lc.VerdictSource(self.value)


class Outcome(enum.StrEnum):
    ACCEPT = "accept"
    RETRY = "retry"
    REPAIR = "repair"
    REGENERATE = "regenerate"
    PARK = "park"
    ESCALATE = "escalate"

    def to_contract(self) -> lc.PolicyOutcome:
        return lc.PolicyOutcome(self.value)

    @property
    def is_terminal(self) -> bool:
        """Whether this outcome ends the unit of work rather than scheduling more."""
        return self in {Outcome.ACCEPT, Outcome.PARK, Outcome.ESCALATE}


class UntrustedVerdict(Exception):
    """A blocking gate tried to rely on the generating model's word for its own output."""


@dataclass(frozen=True, slots=True)
class GateOutcome:
    gate: GateKind
    rule_or_critic_id: str
    passed: bool
    verdict_source: VerdictSource = VerdictSource.DETERMINISTIC
    blocking: bool = True
    vetoes: tuple[Veto, ...] = ()
    detail: str | None = None
    #: Absent on a blocking craft gate means uncalibrated, which §10.4 forbids.
    calibration_id: str | None = None

    def to_contract(self) -> lc.GateResult:
        return lc.GateResult(
            gate=self.gate.to_contract(),
            rule_or_critic_id=self.rule_or_critic_id,
            passed=self.passed,
            verdict_source=self.verdict_source.to_contract(),
            blocking=self.blocking,
            vetoes=[veto.value for veto in self.vetoes],
            detail=self.detail,
            calibration_id=self.calibration_id,
        )


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Why one candidate was accepted, refused, or escalated."""

    decision_id: str
    outcome: Outcome
    gates: tuple[GateOutcome, ...] = ()
    job_id: str | None = None
    logical_id: str | None = None
    base_revision_id: str | None = None
    resulting_revision_id: str | None = None
    attempt: int = 0
    #: Provenance of the candidate under judgment.
    provider: str | None = None
    model: str | None = None
    profile: str | None = None
    fell_back_from: tuple[str, ...] = ()
    invocations: int = 0
    total_tokens: int = 0
    #: None when the provider cannot report dollars — a subscription CLI, or local
    #: hardware. That is why it is never the only budget ceiling.
    cost_usd: float | None = None
    #: Digest of the frozen policy config, so a threshold change reads as a different
    #: config rather than as unexplained drift in behaviour.
    policy_config_digest: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        for gate in self.gates:
            if gate.blocking and gate.verdict_source is VerdictSource.MODEL_SELF_REPORT:
                raise UntrustedVerdict(
                    f"gate {gate.rule_or_critic_id} is blocking and sources its verdict "
                    "from the generating model's report on its own output; MirrorBench's "
                    "measurement is that this is not a correctness signal"
                )
            if (
                gate.blocking
                and gate.gate is GateKind.CRAFT
                and gate.calibration_id is None
            ):
                raise UntrustedVerdict(
                    f"craft gate {gate.rule_or_critic_id} is blocking without calibration "
                    "evidence; §10.4 promotes a critic only after measured held-out "
                    "precision, and until then it annotates"
                )

    @property
    def accepted(self) -> bool:
        return self.outcome is Outcome.ACCEPT

    @property
    def failed_vetoes(self) -> tuple[Veto, ...]:
        return tuple(veto for gate in self.gates if not gate.passed for veto in gate.vetoes)

    @property
    def parked_by_veto(self) -> bool:
        """Whether a parkable veto stopped this, rather than a spent attempt budget.

        The Conductor needs it for the reason it already needs `refused_before_work`, and it
        is the same bug in a third costume. `_settle` derives POISONED from
        `attempts >= max_attempts` alone, on a premise it states in a comment: "`decide`
        returns PARK only on attempt exhaustion". The budget gate falsified that once and
        the comment records the fix; `PARKABLE` falsifies it again, because a craft refusal
        parks at *any* attempt number — deliberately, since the check sits ahead of the
        budget so the unit is never charged attempts it was never going to use.

        Without this, a craft gate that happens to fire on the third attempt poisons the
        unit: unrevivable, absent from `jobs --status parked`, its derived job id burned,
        and its exception labelled "attempt budget spent" when the budget is not what
        stopped it. Which would make three claims false at once — `PARKABLE`'s own
        docstring, §26 of `plan/stage-0-decisions.md`, and the README — all of which promise
        that a craft refusal is revivable.
        """
        failing = [gate for gate in self.gates if gate.blocking and not gate.passed]
        return bool({veto for gate in failing for veto in gate.vetoes} & PARKABLE)

    @property
    def refused_before_work(self) -> bool:
        """Whether this refusal was reached *in front of* the work rather than about it.

        §4.2 gate 4 runs before `registry.complete`, which is the whole point of checking a
        ceiling in front of the spend rather than behind it. Nothing was generated, so there
        is no candidate to judge and nothing about the unit is wrong — the refusal is a fact
        about the day, or about the queue, and not about the work.

        The Conductor needs this because a unit refused before it ran must not be charged an
        attempt, exactly as `TransientFailure` already is not. A new pre-flight gate does not
        get this treatment by default; it has to be named in `PRE_FLIGHT` below, which is the
        safe direction to be wrong in.

        **The second entry was earned the same way the first was.** `integrity.standing.v0`
        refuses on a finding that was already on record before the attempt began — the
        candidate cannot have caused it and cannot clear it, so all three attempts meet the
        identical refusal and the unit poisons. The operator's correct response is to dismiss
        the finding, and under the old behaviour that arrived three ticks too late: the work
        was already terminal and its idempotency key burned. Which is, exactly, the failure
        §19.1 records for `ProviderUnavailable` and then again for the budget ceiling.
        """
        failing = [gate for gate in self.gates if gate.blocking and not gate.passed]
        return bool(failing) and all(
            gate.gate is GateKind.BUDGET or gate.rule_or_critic_id in PRE_FLIGHT
            for gate in failing
        )

    def to_contract(self, meta: lc.ArtifactMeta) -> lc.PolicyDecisionRecord:
        return lc.PolicyDecisionRecord(
            meta=meta,
            decision_id=self.decision_id,
            outcome=self.outcome.to_contract(),
            job_id=self.job_id,
            gates=[gate.to_contract() for gate in self.gates],
            provider=self.provider,
            model=self.model,
            profile=self.profile,
            fell_back_from=list(self.fell_back_from),
            invocations=self.invocations,
            total_tokens=self.total_tokens,
            cost_usd=self.cost_usd,
            policy_config_digest=self.policy_config_digest,
            attempt=self.attempt,
            resulting_revision_id=self.resulting_revision_id,
        )


def policy_digest(policy: DraftPolicy) -> str:
    """Content address of the frozen policy the decision was made under."""
    return payload_digest(
        {
            "min_chars": policy.min_chars,
            "max_chars": policy.max_chars,
            "allow_overwrite": policy.allow_overwrite,
            # A target rather than a limit, and recorded for exactly that reason: it shapes
            # every scene the book contains and no gate would ever mention it.
            "target_words": policy.target_words,
        }
    )


def patch_policy_digest(policy: PatchPolicy) -> str:
    """Content address of the mechanical limits applied to a repair."""
    return payload_digest(
        {
            "min_length_ratio": policy.min_length_ratio,
            "max_length_ratio": policy.max_length_ratio,
            "require_license_for_deletion": policy.require_license_for_deletion,
            "max_ops": policy.max_ops,
            "max_cited_fraction": policy.max_cited_fraction,
        }
    )


def decision_id_for(job_id: str, attempt: int, gates: tuple[GateOutcome, ...]) -> str:
    """Derived, not random, so a replayed job produces the same decision id and the row
    collapses on insert rather than accumulating duplicates of one judgment."""
    material = payload_digest(
        {
            "job_id": job_id,
            "attempt": attempt,
            "gates": [
                [g.gate.value, g.rule_or_critic_id, g.passed, sorted(v.value for v in g.vetoes)]
                for g in gates
            ],
        }
    )
    return f"dec-{sha256(material.encode()).hexdigest()[:24]}"


def gates_for_draft(outcome: DraftOutcome) -> tuple[GateOutcome, ...]:
    """Project a draft gate result into the recorded ladder.

    One gate today. It is still a list because §4.2's ladder is a list, and a decision
    record whose shape changes when the second gate arrives is a migration nobody
    scheduled.

    **An accepted draft carries its length against the length that was asked for.** The
    detail used to be populated only on refusal, so a passing gate said nothing at all and
    the delivered length appeared in no record. `target_words` is an instruction and stays
    one — §1a.1 is why it is not a floor — but "asked 900, wrote 172" is a mechanical fact
    about a generation, and it is the fact §17 Stage 3 turns on.
    """
    detail = "; ".join(record.detail for record in outcome.vetoes) or None
    if outcome.accepted and outcome.target_words:
        share = outcome.words / outcome.target_words
        detail = (
            f"{outcome.words} words against a target of {outcome.target_words} "
            f"({share:.0%})"
        )
    return (
        GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="shape.draft.v0",
            passed=outcome.accepted,
            verdict_source=VerdictSource.DETERMINISTIC,
            blocking=True,
            vetoes=outcome.veto_kinds,
            detail=detail,
        ),
    )


def gates_for_patch(outcome: PatchOutcome) -> tuple[GateOutcome, ...]:
    """Project the bounded-patch mechanics into the recorded policy ladder."""
    return (
        GateOutcome(
            gate=GateKind.SHAPE,
            rule_or_critic_id="shape.patch.v0",
            passed=outcome.accepted,
            verdict_source=VerdictSource.DETERMINISTIC,
            blocking=True,
            vetoes=outcome.veto_kinds,
            detail="; ".join(record.detail for record in outcome.vetoes) or None,
        ),
    )


def decide(
    gates: tuple[GateOutcome, ...],
    *,
    job_id: str,
    attempt: int,
    max_attempts: int,
) -> tuple[Outcome, str | None]:
    """Map gate results and the attempt budget onto §4.2's decision. Pure and total.

    The ordering matters and is the substance of the function: an unclassified veto
    escalates *before* the attempt budget is consulted, so a locked node is reported as
    locked on the first try rather than as "attempts exhausted" on the fourth. A parkable
    veto is checked in the same place and for the same reason — it parks on attempt 1
    carrying its own cause, rather than on attempt 3 carrying "attempts exhausted", and it
    is never charged the attempts it was never going to use.
    """
    failing = [gate for gate in gates if gate.blocking and not gate.passed]
    if not failing:
        return Outcome.ACCEPT, None

    vetoes = {veto for gate in failing for veto in gate.vetoes}
    if not vetoes:
        return Outcome.ESCALATE, "a blocking gate failed without naming a veto"

    unclassified = vetoes - RETRYABLE - REGENERABLE - PARKABLE
    if unclassified:
        names = ", ".join(sorted(veto.value for veto in unclassified))
        return Outcome.ESCALATE, f"no retry can resolve: {names}"

    # Ahead of the attempt budget, and ahead of `RETRYABLE`, so a candidate that fails a
    # parkable veto *and* a retryable one parks rather than earning the retry.
    #
    # **The mixed case is reachable**, and an earlier draft of this comment claimed it was
    # not on the grounds that craft is measured only on a shape-accepted draft. That is true
    # and irrelevant: `handlers` appends the integrity gate and the craft gates in the same
    # pass over the same accepted draft, so `CONTINUITY_BREACH` and `CRAFT_BELOW_BAR` fire
    # together whenever a candidate is both contradictory and weak.
    #
    # Parking still wins, for the reason `PARKABLE` exists: the retry would be licensed by
    # the continuity breach but *measured* by the craft metric too, so the candidate that
    # eventually passes is the one that beat the proxy — the rejection-sampling channel,
    # entered through the narrow door of a co-occurring veto. What the mixed case costs is a
    # legitimate second attempt at the contradiction, and the compensation is that the
    # reason names **every** failing veto rather than only the parkable one, so the breach
    # is on the record the director reads instead of being hidden by the refusal that
    # outranked it.
    if vetoes & PARKABLE:
        names = ", ".join(sorted(veto.value for veto in vetoes))
        return Outcome.PARK, f"{names}: held for judgment rather than redrafted"

    if attempt >= max_attempts:
        names = ", ".join(sorted(veto.value for veto in vetoes))
        return Outcome.PARK, f"attempt budget exhausted with {names} outstanding"

    if vetoes & REGENERABLE:
        return Outcome.REGENERATE, "candidate was built against stale or malformed inputs"
    return Outcome.RETRY, "; ".join(sorted(veto.value for veto in vetoes))


__all__ = [
    "PARKABLE",
    "PRE_FLIGHT",
    "REGENERABLE",
    "RETRYABLE",
    "GateKind",
    "GateOutcome",
    "Outcome",
    "PolicyDecision",
    "UntrustedVerdict",
    "VerdictSource",
    "decide",
    "decision_id_for",
    "gates_for_draft",
    "gates_for_patch",
    "patch_policy_digest",
    "policy_digest",
]
