"""Findings: what an evaluator says is wrong, and what policy is allowed to do about it.

§12 step 6 gates a candidate on "simulation replay, status-block equality, continuity
detectors, mechanical vetoes". The mechanical vetoes have been here since slice 1. This
module is the vocabulary for the other three, and — deliberately — **not an implementation of
them**.

**Where the detectors live, and why not here.** §8.4 settles it: the LitRPG rule and
predicate vocabulary is owned by ContinuityEvaluation's game-mechanics pack, because §7 and
§8 had previously assigned the identical invariants over the identical fixture to two
projects, "which would produce two divergent predicate vocabularies over one fixture and a
permanent reconciliation tax". §13's consumption rule is that siblings depend on contracts
and never on each other. Both point the same way: an evaluator writes an
`EvaluationArtifact`, LitHarness ingests it, and the coupling is a file of a shared schema.
Reimplementing `ledger.gold.v0` here would be the tax §8.4 exists to refuse.

What LitHarness owns is everything downstream of the finding: storage, the gate, the severity
partition, and the retry ladder. That is `domain/integrity.py`.

**Severity decides blocking, and `status` overrides severity.** Both golden fixtures ship
negative controls — the mystery's rain-on-glass motif is a deliberate repetition, Julian's
alibi is a deliberate lie — and a correct detector emits findings for both. A gate that
blocked on every finding would refuse a book for its intentional devices, which is §10.6's
"the cheapest repair that satisfies the metric is often the disease" arriving from the other
direction. So `ACCEPTED_INTENTIONAL` and `FALSE_POSITIVE` never block, whatever their
severity says, and that is checked rather than documented.

**`note` is never read.** §8.3 records that five of six planted defects in the litrpg fixture
carry their own finding id in `StateRecord.note` — *"Gold 15 is what the prose says; the
ledger-correct value is 20. See f-gold-ledger."* — so a 6/6 gate is reachable by regexing for
`See f-`. Nothing in this package reads that field, and `test_integrity.py` asserts so by
scanning the source.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Protocol

import litharness_contracts as lc

from litharness.domain.events import payload_digest
from litharness.domain.patch import Veto


class Severity(enum.StrEnum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    def to_contract(self) -> lc.Severity:
        return lc.Severity(self.value)

    @property
    def rank(self) -> int:
        return {"info": 0, "unknown": 1, "minor": 2, "major": 3, "critical": 4}[self.value]


class Status(enum.StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    ACCEPTED_INTENTIONAL = "accepted_intentional"
    FIXED = "fixed"
    FALSE_POSITIVE = "false_positive"
    DEFERRED = "deferred"
    SUPERSEDED = "superseded"
    EVALUATION_ERROR = "evaluation_error"
    UNKNOWN = "unknown"

    def to_contract(self) -> lc.FindingStatus:
        return lc.FindingStatus(self.value)


#: Severities a blocking gate refuses on. `MINOR` and below annotate.
#:
#: The line sits between minor and major because §4.2's ladder turns a blocking failure into a
#: bounded retry, and a retry costs a generation. A finding not worth a second model call is
#: not worth blocking on — it is worth recording, which happens either way.
BLOCKING_SEVERITIES: frozenset[Severity] = frozenset({Severity.MAJOR, Severity.CRITICAL})

#: Statuses that mean "still wrong, nobody has settled it". The gate's filter, and
#: deliberately not just `OPEN`: `CONFIRMED` means a human agreed the defect is real, which is
#: the last status a gate should treat as resolved.
UNRESOLVED_STATUSES: tuple[Status, ...] = (Status.OPEN, Status.CONFIRMED)

#: Statuses that never block regardless of severity. See the module docstring: a negative
#: control is a finding a correct detector *should* emit.
NON_BLOCKING_STATUSES: frozenset[Status] = frozenset(
    {
        Status.ACCEPTED_INTENTIONAL,
        Status.FALSE_POSITIVE,
        Status.FIXED,
        Status.SUPERSEDED,
        Status.DEFERRED,
        #: An evaluator that crashed has reported its own failure, not the manuscript's. It
        #: must reach a human — `EvaluationError` is what the exception queue is for — but
        #: blocking the candidate would punish the draft for the detector's bug.
        Status.EVALUATION_ERROR,
    }
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing an evaluator says is wrong, reduced to what policy acts on.

    A projection rather than a mirror: `lc.Finding` carries evidence spans, a claim object,
    reproduction metadata and dependencies, all of which are stored verbatim and none of which
    the gate reads. Keeping the domain type to the fields policy uses is what stops the gate
    quietly acquiring opinions about evidence it never validated.
    """

    finding_id: str
    category: str
    severity: Severity
    message: str
    status: Status = Status.OPEN
    subtype: str | None = None
    rule_or_critic_id: str | None = None
    #: The node the finding lands on, lifted from `primary_span`.
    logical_id: str | None = None
    confidence_basis: str = lc.ConfidenceBasis.UNKNOWN.value
    run_id: str | None = None
    #: The contract artifact, kept whole so nothing is lost by this projection.
    source: dict[str, Any] = field(default_factory=dict)

    @property
    def blocks(self) -> bool:
        """Whether a blocking gate refuses a candidate carrying this finding."""
        if self.status in NON_BLOCKING_STATUSES:
            return False
        return self.severity in BLOCKING_SEVERITIES

    @property
    def deterministic(self) -> bool:
        """Whether the verdict came from a rule rather than a model.

        `policy.PolicyDecision` refuses at construction to let a blocking gate source its
        verdict from the generating model (MirrorBench, §20.8). A finding produced by a
        model critic is therefore recorded and — until §10.4 promotes it with calibration
        evidence — annotates rather than blocks.
        """
        return self.confidence_basis == lc.ConfidenceBasis.DETERMINISTIC.value

    @classmethod
    def from_contract(cls, finding: lc.Finding, *, run_id: str | None = None) -> Finding:
        span = finding.primary_span
        return cls(
            finding_id=finding.finding_id,
            category=finding.category.value,
            severity=Severity(finding.severity.value),
            message=finding.message,
            status=Status(finding.status.value),
            subtype=finding.subtype,
            rule_or_critic_id=finding.rule_or_critic_id,
            logical_id=span.source.logical_id if span else None,
            confidence_basis=finding.confidence_basis.value,
            run_id=run_id or finding.evaluation_run_id,
            source=lc.to_jsonable(finding),
        )


def finding_id_for(rule_or_critic_id: str, logical_id: str, claim: dict[str, Any]) -> str:
    """Content-derived, so a re-run of the same detector over the same node converges.

    The same reasoning as `decision_id_for` and every event key in this system: a detector
    that ran twice on an unchanged revision must produce one row, not two. Randomly-keyed
    findings would make the queue grow with every tick and §19's "nothing spins" would be
    violated by the audit trail again — which migration 006 already had to fix once.
    """
    material = payload_digest(
        {"rule": rule_or_critic_id, "logical_id": logical_id, "claim": claim}
    )
    return f"f-{sha256(material.encode()).hexdigest()[:24]}"


class Detector(Protocol):
    """A deterministic check over a candidate and the state it is entering.

    The port §8.4's arrangement requires. ContinuityEvaluation's pack satisfies it from
    outside the process, by writing an `EvaluationArtifact` that
    `adapters/evaluation_artifact.py` ingests; anything LitHarness owns satisfies it in
    process. The gate cannot tell the difference and must not: a finding is a finding.
    """

    def __call__(self, subject: DetectorInput) -> Sequence[Finding]:
        ...


@dataclass(frozen=True, slots=True)
class DetectorInput:
    """Everything a detector is allowed to see about one candidate.

    A frozen record rather than a widening argument list, because every detector added later
    would otherwise change the signature of every detector written before it — and because
    what a detector may read is a decision, not an accident. `note` is not reachable from
    here: `records` are contract objects, and `test_integrity.py` asserts no module in this
    package names the field.
    """

    book_id: str
    branch_id: str
    logical_id: str
    #: The candidate under judgment, canonicalised. None when the check is about the book's
    #: state rather than about a draft.
    candidate: str | None = None
    records: tuple[lc.StateRecord, ...] = ()
    plan_items: tuple[lc.PlanItem, ...] = ()
    #: Story position of the beat being drafted, for checks that only apply at the end.
    ordinal: int = 0
    of_total: int = 0


def vetoes_for(findings: Sequence[Finding]) -> tuple[Veto, ...]:
    """The veto vocabulary a blocking finding maps onto.

    One veto rather than one per category, and deliberately so: §4.2's retry ladder acts on
    the veto, and the action for every integrity finding is the same — the model wrote
    something that contradicts the book, so try again with the same context. Splitting the
    veto by category would create table entries that all resolve to `RETRY`, and the first one
    somebody forgot to classify would escalate instead, which is the failure `decide` already
    guards against by escalating the unclassified.
    """
    return (Veto.CONTINUITY_BREACH,) if any(item.blocks for item in findings) else ()


def worst(findings: Sequence[Finding]) -> Severity | None:
    return max((item.severity for item in findings), key=lambda s: s.rank, default=None)


__all__ = [
    "BLOCKING_SEVERITIES",
    "NON_BLOCKING_STATUSES",
    "UNRESOLVED_STATUSES",
    "Detector",
    "DetectorInput",
    "Finding",
    "Severity",
    "Status",
    "finding_id_for",
    "vetoes_for",
    "worst",
]
