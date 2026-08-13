"""§12 step 6: the integrity gate, and the one detector that is structurally LitHarness's.

Until this module existed the wired ladder was a single gate, `shape.draft.v0`, so *accepted*
meant "a string of plausible length" — §17's Stage 1 exit clause about planted defects being
caught by gates had nothing to be caught by. This is the gate. What it is not is a detector
suite: §8.4 puts the LitRPG rule and predicate vocabulary in ContinuityEvaluation's pack, and
§13 forbids depending on a sibling, so those findings arrive as an `EvaluationArtifact` and
are ingested (`adapters/evaluation_artifact.py`).

**The gate's job is the part that is genuinely policy**, and it is worth listing because it
looks trivial until each line is wrong once:

1. A finding blocks on **severity and status together**, never severity alone. Both fixtures
   ship negative controls — an intentional motif, a deliberate lie — which a *correct*
   detector emits and a correct policy must not refuse.
2. An **uncalibrated model critic may not block** (§10.4), so a finding whose
   `confidence_basis` is not `deterministic` annotates. This is the same invariant
   `PolicyDecision.__post_init__` enforces from the other end; enforcing it here as well means
   a non-deterministic finding cannot even reach the constructor that would raise on it.
3. The gate runs **over findings against this node**, not over the whole book. A defect in
   scene 2 must not park the job drafting scene 5 — §4.1's "a blocked item never stalls the
   queue" — and, more sharply, blocking every subsequent beat on an old finding would convert
   one defect into a stalled book.

**`state.contradiction.v0` is the one check implemented here, and it is here because no
sibling can do it.** It is a property of *this store's* records rather than of a fixture's
prose: two canon records asserting different values for the same subject and predicate at the
same story position, with no supersession between them. ContinuityEvaluation evaluates a
finished manuscript it is handed; it never sees a LitHarness store mid-run, and the corruption
this catches — §12 step 5's extraction writing a record that contradicts one already accepted
— can only happen inside the loop. It reads records and nothing else, so no amount of prose
phrasing satisfies or defeats it.

It emits **zero findings on both golden fixtures**, which is the negative-control leg §8.3
demands and the reason it can be turned on blocking without a calibration programme: a check
that fires on a conforming book is not a floor, it is a tax.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain.findings import (
    DetectorInput,
    Finding,
    Severity,
    Status,
    finding_id_for,
    vetoes_for,
    worst,
)
from litharness.domain.policy import GateKind, GateOutcome, VerdictSource

#: This module's own rule id, in the vocabulary the fixtures use for theirs.
CONTRADICTION_RULE = "state.contradiction.v0"

#: The gate's id in a recorded policy decision, alongside `shape.draft.v0`.
INTEGRITY_GATE = "integrity.findings.v0"


def _value_key(value: Any) -> str:
    """A stable comparison key for a record value, which the contract types as `Any`.

    JSON with sorted keys rather than `repr`, so `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` are
    the same value and not a contradiction. Getting this wrong would make the detector fire on
    two identical status snapshots whose keys were written in a different order — a finding
    about dict iteration order, reported as a continuity defect.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def detect_contradictions(subject: DetectorInput) -> list[Finding]:
    """Canon records that disagree with each other at the same story position.

    Grouped on `(subject, predicate, order_key)` — the position is part of the key on purpose.
    A stat that moves between scenes is a story; the same stat holding two values *at one
    moment* is a defect. Dropping the position from the key would report every ordinary change
    in the book, which on the litrpg fixture is every status snapshot after the first.

    Only canon takes part. A `PROPOSED` record is a candidate no decision has accepted, and
    two proposals disagreeing is what proposals are for.
    """
    canon = [record for record in subject.records if state_mod.is_canon(record)]
    groups: dict[tuple[str, str, str], list[lc.StateRecord]] = {}
    for record in canon:
        key = (record.subject, record.predicate, state_mod.order_key_of(record) or "")
        groups.setdefault(key, []).append(record)

    findings: list[Finding] = []
    for (subject_id, predicate, order_key), members in sorted(groups.items()):
        distinct = {_value_key(record.value): record for record in members}
        if len(distinct) < 2:
            continue
        conflicting = state_mod.in_story_order(distinct.values())
        claim = {
            "subject": subject_id,
            "predicate": predicate,
            "order_key": order_key,
            "values": sorted(distinct),
            "records": sorted(record.record_id for record in conflicting),
        }
        findings.append(
            Finding(
                finding_id=finding_id_for(CONTRADICTION_RULE, subject_id, claim),
                category=lc.FindingCategory.WORLD_RULE.value,
                severity=Severity.MAJOR,
                status=Status.OPEN,
                subtype="contradictory_records",
                rule_or_critic_id=CONTRADICTION_RULE,
                logical_id=subject.logical_id,
                confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
                message=(
                    f"{subject_id} {predicate} holds {len(distinct)} different values at "
                    f"story position {order_key or '(unplaced)'}: "
                    + ", ".join(sorted(distinct))
                ),
                source={"claim": claim},
            )
        )
    return findings


#: Detectors that run inside the loop. One, and it is the one no sibling can run — see the
#: module docstring. The tuple is the extension point: a second in-process check is appended
#: here, and an out-of-process pack arrives through `standing` instead.
IN_PROCESS: tuple[Any, ...] = (detect_contradictions,)


def run_detectors(subject: DetectorInput) -> list[Finding]:
    return [finding for detector in IN_PROCESS for finding in detector(subject)]


def gate_integrity(
    subject: DetectorInput, *, standing: Sequence[Finding] = ()
) -> tuple[GateOutcome, list[Finding]]:
    """§4.2 ladder step 3. Returns the gate result and every finding that informed it.

    `standing` is what an evaluator already recorded against this node — ContinuityEvaluation's
    pack, ingested as an artifact — and is filtered to this node by the caller. Passing it in
    rather than querying makes the gate a pure function of its inputs, which is what lets the
    defect-injection suite plant a finding without a store.

    Findings that do not block are still **returned and recorded**. §4.2's decision record
    lists the gates that ran including the passing ones, and a minor finding dropped on the
    floor because it was not fatal is exactly the annotation §10.2 says to instrument from
    Book Zero onward.
    """
    findings = [*run_detectors(subject), *standing]
    blocking = [item for item in findings if item.blocks and item.deterministic]

    # §10.4 from the other end: a finding a model produced annotates until calibration
    # promotes it. Recorded as a detail so the decision says the critic *ran* — a gate whose
    # output vanishes when it disagrees is worse than one that never ran.
    advisory = [item for item in findings if item.blocks and not item.deterministic]

    detail_parts: list[str] = []
    if blocking:
        detail_parts.append(
            "; ".join(
                f"{item.rule_or_critic_id or item.category} [{item.severity.value}] "
                f"{item.message}"
                for item in blocking
            )
        )
    if advisory:
        detail_parts.append(
            f"{len(advisory)} uncalibrated finding(s) recorded but not blocking (§10.4): "
            + ", ".join(sorted({item.rule_or_critic_id or item.category for item in advisory}))
        )
    if not findings:
        detail_parts.append(f"{len(IN_PROCESS)} detector(s) ran, nothing found")

    gate = GateOutcome(
        gate=GateKind.INTEGRITY,
        rule_or_critic_id=INTEGRITY_GATE,
        passed=not blocking,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        vetoes=vetoes_for(blocking),
        detail="; ".join(part for part in detail_parts if part) or None,
    )
    return gate, findings


def summarise(findings: Sequence[Finding]) -> str:
    """One line for an operator. Worst severity first, because that is what gets read."""
    if not findings:
        return "no findings"
    top = worst(findings)
    blocking = sum(1 for item in findings if item.blocks)
    return (
        f"{len(findings)} finding(s), {blocking} blocking, worst "
        f"{top.value if top else 'unknown'}"
    )


__all__ = [
    "CONTRADICTION_RULE",
    "INTEGRITY_GATE",
    "IN_PROCESS",
    "detect_contradictions",
    "gate_integrity",
    "run_detectors",
    "summarise",
]
