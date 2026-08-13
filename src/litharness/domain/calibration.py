"""§10.4's promotion path: the evidence a craft metric needs before it may refuse anything.

`GateResult.calibration_id` has been a contract field with no producer since 1.1.0, and
`GateKind.CRAFT` an enum member nothing constructed. `PolicyDecision.__post_init__` refuses to
build a blocking craft gate without a calibration id — a bar that has held perfectly for the
uninteresting reason that no craft gate of any kind existed. This module is the other half:
the thing that can satisfy the bar, built so that satisfying it requires evidence rather than
a string.

**Three rules, each of which is a way the bar could be passed without being met.**

**A calibration cites the judgments it was measured on.** `verdicts_digest` is a content
address over the verdict set. Without it, "precision 0.86" is a claim about a sample nobody
can reconstruct — the standard §8.3 refuses from a detector, and there is no reason to accept
it from a critic. A calibration whose digest does not match the current verdict set is
`stale_evidence`, not merely old.

**A calibration expires.** §19's Trust clause says blocking critics carry *current*
calibration evidence, and the word is load-bearing: output changes as the planner, the context
packet and the model change, so a threshold measured against last quarter's prose is a
statement about prose the system no longer writes. An expired calibration does not degrade the
gate to advisory — `promoted_gate` refuses to build the gate at all, because a gate that
silently stops blocking is worse than one that visibly cannot be built.

**Precision has a floor and the holdout has a size.** §10.4 asks for "usable precision at an
acceptable workload"; §10.5 adds that audit disagreement re-opens calibration. Numbers with no
minimum are a rubber stamp, so the minimums are named constants here and a calibration below
them cannot be promoted. They are **not** measured values — nothing in this project has
measured what precision is usable, and the constants say so.

**Nothing here computes a calibration.** Fitting a threshold to human verdicts is a statistics
problem this module deliberately does not solve, because solving it before any verdicts exist
would be fitting to an empty set. What it does is refuse to let a threshold in without the
evidence attached — which is the part that has to exist *before* the data, not after.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from litharness.domain.events import payload_digest
from litharness.domain.policy import GateKind, GateOutcome, UntrustedVerdict, VerdictSource

#: Held-out precision below which a metric may not block. A placeholder with a floor, not a
#: measurement: §10.4 says "usable precision at an acceptable workload" and nothing in this
#: project has established what usable is. Set high because the cost of a false refusal is a
#: wasted generation plus an operator's attention, and §1a.2's evidence is that models asked
#: to improve prose make it worse — so a gate that fires wrongly does not merely waste a call,
#: it invites the revision loop the plan forbids.
MIN_PRECISION = 0.80

#: Judgments a calibration must rest on. Also a placeholder with a floor, and worth reading
#: against the measured reality: RevisionJudge holds two collected verdicts. This constant is
#: therefore not a hurdle the project is close to clearing; it is a statement of what the
#: number would have to be before anyone should believe it.
MIN_HOLDOUT = 50


class Direction(enum.StrEnum):
    """Which side of the threshold fails.

    Explicit because a metric is not inherently directional — a high tricolon rate is a tell
    and a high sentence-length variation is not — and guessing inverts the gate silently,
    which is the failure mode that produces a confidently backwards quality signal.
    """

    ABOVE = "above"
    BELOW = "below"

    def fails(self, value: float, threshold: float) -> bool:
        return value > threshold if self is Direction.ABOVE else value < threshold


class NotPromotable(Exception):
    """A calibration was offered as promotion evidence and does not qualify."""


@dataclass(frozen=True, slots=True)
class Calibration:
    """Measured evidence that one metric predicts human judgment at one threshold."""

    calibration_id: str
    metric_id: str
    holdout_size: int
    precision: float
    threshold: float
    direction: Direction
    #: Content address of the verdict set this was measured on. See the module docstring.
    verdicts_digest: str
    measured_at: str
    #: ISO date after which this is no longer *current* evidence. None means never expires,
    #: which is a claim about a moving target and should be rare enough to notice.
    expires_at: str | None = None
    recall: float | None = None
    note: str | None = None

    def is_current(self, today: str) -> bool:
        return self.expires_at is None or today <= self.expires_at

    def blocks_at(self, value: float) -> bool:
        return self.direction.fails(value, self.threshold)

    def why_not_promotable(self, today: str, verdicts_digest: str | None = None) -> str | None:
        """The reason this may not become a blocking gate, or None if it may.

        Returns a reason rather than a boolean so the refusal can be recorded and read. "Not
        promotable" with no cause is the kind of answer that gets worked around.
        """
        if self.precision < MIN_PRECISION:
            return (
                f"held-out precision {self.precision:.2f} is below the {MIN_PRECISION:.2f} "
                "floor (§10.4: usable precision at an acceptable workload)"
            )
        if self.holdout_size < MIN_HOLDOUT:
            return (
                f"measured on {self.holdout_size} held-out judgment(s), below the "
                f"{MIN_HOLDOUT} floor"
            )
        if not self.is_current(today):
            return (
                f"expired {self.expires_at}; §19's Trust clause requires *current* "
                "calibration evidence, and output has changed since"
            )
        if verdicts_digest is not None and verdicts_digest != self.verdicts_digest:
            return (
                "the verdict set has changed since this was measured "
                f"({verdicts_digest[:12]} != {self.verdicts_digest[:12]}); "
                "§10.5 re-opens calibration on audit disagreement"
            )
        return None


def calibration_id_for(metric_id: str, threshold: float, verdicts_digest: str) -> str:
    """Derived from what was measured, so the same evidence names the same calibration."""
    material = payload_digest(
        {"metric": metric_id, "threshold": threshold, "verdicts": verdicts_digest}
    )
    return f"cal-{sha256(material.encode()).hexdigest()[:24]}"


def verdicts_digest_for(verdicts: Iterable[tuple[str, str]]) -> str:
    """Content address over a verdict set — (sample_id, verdict) pairs.

    Sorted before hashing, so the digest is a fact about *which* judgments were used and not
    about the order a query returned them in.
    """
    pairs = sorted((str(sample), str(verdict)) for sample, verdict in verdicts)
    return payload_digest({"verdicts": pairs})


def promoted_gate(
    calibration: Calibration,
    value: float,
    *,
    today: str,
    verdicts_digest: str | None = None,
) -> GateOutcome:
    """Build a **blocking** craft gate from calibrated evidence, or refuse to.

    The only function in this package that can produce one. `craft.craft_gates` builds
    annotations and has no branch that could reach here, so a metric cannot drift into
    blocking by a threshold being filled in somewhere — it has to come through this door, and
    this door checks.

    Raises `NotPromotable` rather than returning an advisory gate on failure. Degrading
    silently is how a gate everyone believes is on turns out to have been off.
    """
    reason = calibration.why_not_promotable(today, verdicts_digest)
    if reason is not None:
        raise NotPromotable(f"{calibration.metric_id}: {reason}")
    gate = GateOutcome(
        gate=GateKind.CRAFT,
        rule_or_critic_id=calibration.metric_id,
        passed=not calibration.blocks_at(value),
        # A deterministic proxy over prose, validated against human judgment. Not
        # `CALIBRATED_CRITIC`, which is for a model whose verdict was calibrated; the
        # distinction matters because MirrorBench's invariant is about model self-report and
        # this is arithmetic over text.
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        detail=(
            f"{value} vs threshold {calibration.threshold} ({calibration.direction.value}); "
            f"precision {calibration.precision:.2f} on {calibration.holdout_size} held-out"
        ),
        calibration_id=calibration.calibration_id,
    )
    # Belt and braces, and cheap: `PolicyDecision` enforces the same invariant, but a gate is
    # constructed here and validated there, so a caller that never builds a decision would
    # otherwise carry an unchecked blocking gate around.
    if gate.calibration_id is None:  # pragma: no cover - unreachable by construction
        raise UntrustedVerdict("a promoted craft gate must cite its calibration")
    return gate


__all__ = [
    "MIN_HOLDOUT",
    "MIN_PRECISION",
    "Calibration",
    "Direction",
    "NotPromotable",
    "calibration_id_for",
    "promoted_gate",
    "verdicts_digest_for",
]
