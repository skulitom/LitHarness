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

from litharness.domain.craft import MIN_BAND_CHAPTERS
from litharness.domain.events import payload_digest
from litharness.domain.patch import Veto
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

#: Held-out judgments the metric must actually have **fired on**, and unlike the two above
#: this one is derived rather than placed.
#:
#: `MIN_HOLDOUT` alone does not constrain it, because precision is computed over the flagged
#: set and not over the holdout: a metric that flags one scene out of fifty and happens to be
#: right scores precision 1.00 on a holdout of 50 and clears both floors. `recall` would have
#: caught that and is optional, so it cannot be relied on to.
#:
#: 17 is the smallest flagged set whose two-sided 95% Clopper-Pearson lower bound on a
#: *perfect* score clears `MIN_PRECISION` — 0.025**(1/17) = 0.805, against 0.794 at 16.
#:
#: **What that does and does not buy, stated precisely because the first draft of this
#: comment overclaimed it.** The floor rules out the case it was written for: a metric that
#: fires once or twice, gets it right, and reports precision 1.00. It does *not* make
#: `MIN_PRECISION` a confidence bound in general — at 17 flags and an observed 0.80 the
#: lower bound is far below 0.80, and the code enforces the point estimate at every
#: precision rather than requiring more flags as precision falls. Enforcing the bound at the
#: *observed* precision is the stricter and more principled bar; it is deliberately not
#: taken here, because it would redefine what `MIN_PRECISION` means and that is a decision
#: for whoever first has evidence to promote, not for the commit that wired the path.
MIN_FLAGGED = 17


#: A population gate's control cohort may cross the reference cohort's threshold at most this
#: many times as often before the threshold is refused. **A placed constant, and the one that
#: guards this whole route's epistemic claim** — it has no derivation behind it the way
#: `MIN_FLAGGED` does, and it is the lever a maintainer will reach for the first time a
#: population gate refuses something they wanted. 2.0 says: a line the reference cohort crosses
#: 1% of the time may not be crossed more than 2% of the time by prose of the same era that
#: nobody suspects. `tricolon_rate` fails it at better than five times that.
MAX_CONTROL_RATIO = 2.0

#: The share of the reference cohort a threshold may refuse before it stops being a threshold.
#:
#: **Derived from `MAX_CONTROL_RATIO` rather than placed, which is why it sits here.** The
#: control clause below refuses a threshold when `control_exceedance > MAX_CONTROL_RATIO *
#: reference_exceedance`. Exceedance is a share and cannot exceed 1.0, so once the reference
#: cohort crosses the line more than `1 / MAX_CONTROL_RATIO` of the time there is no control
#: value that can fail the clause — **the guard that carries this whole route's epistemic claim
#: becomes arithmetically unfalsifiable, and it does so silently.**
#:
#: The only inertness guard before this was `reference_exceedance <= 0.0`, which catches a gate
#: that can never fire and nothing at the other end. A threshold crossed by 99% of published
#: human LitRPG in its own band was promotable, would have refused almost every scene, and
#: would have carried a control clause incapable of objecting — the two failures reinforcing
#: rather than catching each other.
#:
#: A stricter bar is defensible and deliberately not taken: an out-of-distribution claim
#: arguably belongs at p95 or beyond (exceedance ~0.05), and 0.5 admits a threshold at the
#: median. That is a judgment about what "out of distribution" should mean, and it belongs to
#: whoever first has evidence to promote — the same reasoning `MIN_FLAGGED` records for not
#: enforcing a confidence bound. This constant refuses only what is incoherent.
MAX_REFERENCE_EXCEEDANCE = 1.0 / MAX_CONTROL_RATIO

#: Chapters that must actually sit at or beyond a quantile stop before it may be a threshold.
#: **Derived rather than placed.** `tools/build_craft_profile.py` indexes a stop at
#: `round(p * (n - 1))`, so a p99 over a 200-chapter band rests on two observations and a p99
#: is exactly where a population threshold wants to live. Measured against the committed
#: profile, the reference cohort's bands give 3, 5, 21, 37 and 6 observations at p99 — so five
#: refuses the 300-700 band outright and clears the 700-1100 band, the one bracketing
#: `DraftPolicy.target_words`, by one. A control that fails on real data.
MIN_TAIL_SUPPORT = 5


class EvidenceClass(enum.StrEnum):
    """What a calibration's numbers are *about*. The dispatcher, not a label beside them.

    **The conflation this exists to end.** `Calibration`'s fields name only numbers —
    `precision`, `holdout_size`, `verdicts_digest` — and `why_not_promotable` checked their
    internal coherence and never their referent. So a percentile computed over 13,000
    strangers' chapters could fill every field without any single field being false, and the
    record as a whole still claimed something nobody measured. Corpus evidence was not
    refused here; it was *unlabelled*, which is worse, because the refusal looked like it was
    working.

    These are not three grades of one thing. They have different referents, and a gate may
    make only the claim its referent supports:

    - `JUDGMENT` — a human's answer about one of *our* units at the grain being gated. This
      is the only class that may say a scene is not good enough.
    - `POPULATION` — membership in a named published cohort at matched length and genre. It
      may refuse, and what it refuses on is "this value is outside the range published LitRPG
      of this length occupies". Not quality. A different veto, so the record cannot be read
      as the claim it was not measured for.
    - `BEHAVIOUR` — reader behaviour aggregated over other authors' whole stories, e.g.
      `followers / total_views`. Recordable, rankable, and it refuses nothing, because its
      grain is `STORY` and nothing in this system gates a story.
    - `UNCLASSIFIED` — what a row recorded before this existed reads as. Never promotable,
      and it is a refusal by name rather than a silent default: an unclassified row is not a
      judgment row that forgot to say so.
    """

    JUDGMENT = "judgment"
    POPULATION = "population"
    BEHAVIOUR = "behaviour"
    UNCLASSIFIED = "unclassified"


class Grain(enum.StrEnum):
    """The unit an evidence set's label is attached to.

    Ordered coarse-to-fine by `finer_than`. Expressed as a field rather than left implicit
    because the ecological fallacy is otherwise invisible to every check in this module: a
    story-level label and a scene-level metric fill the same columns identically.
    """

    UNIT = "unit"
    CHAPTER = "chapter"
    STORY = "story"

    def covers(self, decision: Grain) -> bool:
        """Whether evidence at this grain may license a refusal of a `decision`-grain unit."""
        rank = {Grain.UNIT: 0, Grain.CHAPTER: 1, Grain.STORY: 2}
        return rank[self] <= rank[decision]


@dataclass(frozen=True, slots=True)
class Population:
    """The reference distribution a `POPULATION` calibration's threshold was read out of.

    **Every field here is a control or the material to compute one.** A threshold with no
    named control cohort measured in the same band in the same pass is the shape of every
    proxy in `research/quality-measurement/BRIEF.md` §2, and the ledger's own worked example
    is `tricolon_rate`: 0.629 against pre-2023 prose looks like this project's first working
    AI-tell detector for exactly as long as it takes to read the 0.606 beside it.
    """

    metric_id: str
    #: The cohort the threshold was read from, and the band it was read in.
    cohort: str
    band: str
    #: The stored ladder stop, e.g. "p99". The threshold must *equal* this stop, so it cannot
    #: be a number somebody typed — see `craft.quantile_stop`.
    quantile: str
    reference_n: int
    #: Chapters in the reference cohort at or beyond the stop. See `MIN_TAIL_SUPPORT`.
    tail_support: int
    #: The cohort that holds the confound fixed — era, in this corpus. Measured in the same
    #: band at the same threshold in the same pass.
    control_cohort: str
    control_n: int
    #: Share of each cohort on the failing side of the threshold.
    reference_exceedance: float
    control_exceedance: float
    #: Content address of the profile build the stop came from. `REFERENCE_COHORT` and
    #: `LENGTH_BANDS` are build-time choices, so a rebuilt profile is different evidence.
    profile_digest: str


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
    #: Content address of the evidence this was measured on — the answered verdict set for a
    #: `JUDGMENT` calibration, the craft profile build for a `POPULATION` one. Named for the
    #: judgment case because that is the only case that existed when it was added; what it
    #: is compared against is now chosen by `evidence_class` rather than assumed.
    verdicts_digest: str
    measured_at: str
    #: **Required, with no default, and that is the point.** A default would mean a caller
    #: that says nothing about its referent gets the most permissive class for free, which is
    #: exactly today's behaviour. The `calibrations` table is empty, so this is the last
    #: moment a required field costs nothing.
    evidence_class: EvidenceClass = EvidenceClass.UNCLASSIFIED
    #: The grain the label is attached to. `UNIT` for a verdict about one of our scenes;
    #: `STORY` for `followers / total_views`.
    grain: Grain = Grain.UNIT
    #: Present iff `evidence_class` is `POPULATION`.
    population: Population | None = None
    #: ISO date after which this is no longer *current* evidence. None means never expires,
    #: which is a claim about a moving target and should be rare enough to notice.
    expires_at: str | None = None
    #: How many of `holdout_size` the metric placed on the failing side — the denominator
    #: `precision` was computed over. `None` means the measurement did not record it, which
    #: is not promotable: an unrecorded flagged count is indistinguishable from a flagged
    #: count of one, and see `MIN_FLAGGED` for why that matters.
    flagged: int | None = None
    recall: float | None = None
    note: str | None = None

    def is_current(self, today: str) -> bool:
        return self.expires_at is None or today <= self.expires_at

    def blocks_at(self, value: float) -> bool:
        return self.direction.fails(value, self.threshold)

    def why_not_promotable(
        self,
        today: str,
        verdicts_digest: str | None = None,
        *,
        decision_grain: Grain = Grain.UNIT,
        answered: int | None = None,
    ) -> str | None:
        """The reason this may not become a blocking gate, or None if it may.

        Returns a reason rather than a boolean so the refusal can be recorded and read. "Not
        promotable" with no cause is the kind of answer that gets worked around.

        **A dispatcher over `evidence_class`, because the checks below are not general.**
        Every constant in the judgment branch is denominated in human answers about our own
        prose — `MIN_HOLDOUT` counts judgments, `MIN_FLAGGED` counts flags on those judgments
        — and applying them to a corpus percentile does not make the percentile validated, it
        makes the bar meaningless. The class picks the checks; the checks do not generalise.

        `decision_grain` is the grain of the thing being refused, so evidence coarser than
        the unit under judgment is refused ahead of every class-specific test. That single
        clause is what closes the ecological fallacy, and it closes it against the label this
        project most wants to use: `followers / total_views` is `STORY` grain, a craft gate
        refuses a scene, and so it can never promote one — at any *n*, at any AUC.

        `answered` is how many answered audit samples the store actually holds. Optional
        because the domain cannot query, and checked when given: nothing anywhere compared
        `holdout_size` against it, so a calibration claiming fifty held-out judgments against
        a store holding two was promotable, and the digest clause could not catch it because
        the digest of two verdicts matches the digest of two verdicts.
        """
        if self.evidence_class is EvidenceClass.UNCLASSIFIED:
            return (
                "does not name what its numbers are about; a calibration recorded before "
                "evidence classes existed is not a judgment calibration that forgot to say "
                "so. Re-record it naming the class"
            )
        if not self.grain.covers(decision_grain):
            return (
                f"its label is attached to a {self.grain.value}, and this gate refuses a "
                f"{decision_grain.value}. Evidence about whole stories cannot license the "
                "refusal of one scene, however large the sample"
            )
        if self.evidence_class is EvidenceClass.BEHAVIOUR:
            return (
                "aggregate reader behaviour over other authors' whole works is a claim about "
                "stories, not about a scene of ours; it may rank and select and may refuse "
                "nothing. A per-chapter outcome would move it to unit grain"
            )
        if self.evidence_class is EvidenceClass.POPULATION:
            return self._why_not_population(today, verdicts_digest)
        return self._why_not_judgment(today, verdicts_digest, answered)

    def _why_not_population(self, today: str, profile_digest: str | None) -> str | None:
        """Why a corpus-derived threshold may not refuse a scene for being out of range.

        Six conditions, and the fourth is the one the whole class turns on: the control
        cohort's exceedance at the same threshold in the same band, measured in the same
        pass, capped at `MAX_CONTROL_RATIO`. BRIEF §2's rule — "compute the control in the
        same pass" — expressed as an arithmetic refusal instead of as a habit.
        """
        population = self.population
        if population is None:
            return (
                "is a population calibration carrying no population: a threshold with no "
                "named cohort, band and control is a number with no referent"
            )
        if population.metric_id != self.metric_id:
            return (
                f"reads its threshold from {population.metric_id}'s distribution while "
                f"gating {self.metric_id}"
            )
        if population.reference_n < MIN_BAND_CHAPTERS:
            return (
                f"rests on {population.reference_n} chapters in band {population.band}, "
                f"below the {MIN_BAND_CHAPTERS} the band ladder itself requires"
            )
        if population.tail_support < MIN_TAIL_SUPPORT:
            return (
                f"its {population.quantile} stop rests on {population.tail_support} "
                f"observed chapter(s) at or beyond it, below the {MIN_TAIL_SUPPORT} floor — "
                "a tail estimated from that many is noise wearing a number's authority"
            )
        if population.reference_exceedance <= 0.0:
            return (
                "no chapter in the reference cohort crosses this threshold, so the gate can "
                "never fire. An inert gate is worse than an empty table: it retires the "
                "emptiness that is currently the honest measure of the gap"
            )
        if population.reference_exceedance > MAX_REFERENCE_EXCEEDANCE:
            return (
                f"the reference cohort {population.cohort} crosses this threshold "
                f"{population.reference_exceedance:.2%} of the time, above the "
                f"{MAX_REFERENCE_EXCEEDANCE:.0%} ceiling — a line most of the published "
                "prose it was derived from also crosses is not an out-of-distribution "
                "threshold, and above it the control clause below cannot fail whatever the "
                "control cohort does"
            )
        if population.control_n < MIN_BAND_CHAPTERS:
            return (
                f"its control cohort {population.control_cohort} holds "
                f"{population.control_n} chapters in band {population.band}; a control too "
                "small to have detected a violation is not a control"
            )
        allowed = MAX_CONTROL_RATIO * population.reference_exceedance
        if population.control_exceedance > allowed:
            ratio = population.control_exceedance / population.reference_exceedance
            return (
                f"the control cohort {population.control_cohort} crosses this threshold "
                f"{ratio:.1f}x as often as the reference cohort "
                f"({population.control_exceedance:.4f} against "
                f"{population.reference_exceedance:.4f}, cap {MAX_CONTROL_RATIO:.1f}x), so "
                "the threshold separates the cohorts rather than the prose — the tricolon "
                "result, arriving as a gate instead of as a table"
            )
        if not self.is_current(today):
            return (
                f"expired {self.expires_at}; §19's Trust clause requires *current* "
                "calibration evidence, and output has changed since"
            )
        if profile_digest is not None and profile_digest != self.verdicts_digest:
            return (
                "the reference profile has been rebuilt since this stop was read "
                f"({profile_digest[:12]} != {self.verdicts_digest[:12]}); the cohort and "
                "band boundaries are build-time choices, so a rebuild is different evidence"
            )
        return None

    def _why_not_judgment(
        self, today: str, verdicts_digest: str | None, answered: int | None
    ) -> str | None:
        """Today's seven checks, unchanged, plus the count nothing was comparing."""
        if answered is not None and self.holdout_size > answered:
            return (
                f"claims {self.holdout_size} held-out judgment(s) against a store holding "
                f"{answered} answered; the digest clause cannot catch this, because the "
                "digest of the smaller set matches itself"
            )
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
        if self.flagged is None:
            return (
                "does not record how many held-out judgments the metric fired on; precision "
                "is computed over the flagged set, so without it the number is unreadable"
            )
        if self.flagged < MIN_FLAGGED:
            return (
                f"fired on {self.flagged} of {self.holdout_size} held-out judgment(s), below "
                f"the {MIN_FLAGGED} floor — a precision measured over so few flags clears "
                f"{MIN_PRECISION:.2f} by luck at conventional confidence"
            )
        if self.flagged > self.holdout_size:
            return (
                f"fired on {self.flagged} of {self.holdout_size} held-out judgment(s), which "
                "is more flags than judgments; the measurement is not about this holdout"
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


def calibration_id_for(
    metric_id: str,
    threshold: float,
    verdicts_digest: str,
    *,
    direction: Direction,
    precision: float,
    holdout_size: int,
    flagged: int | None,
    evidence_class: EvidenceClass = EvidenceClass.UNCLASSIFIED,
    grain: Grain = Grain.UNIT,
) -> str:
    """Derived from what was measured, so the same evidence names the same calibration.

    **The measured numbers are part of the identity, and leaving them out was a bug with an
    operational bite.** The id was once derived from the metric, the threshold and the
    verdict digest alone, on the reading that a re-measurement moves the digest. It does not
    have to: measuring the same metric at the same threshold against the same holdout is
    exactly what a *corrected* measurement is. Two such rows collided, `record_calibration`
    is `INSERT OR IGNORE`, and so the correction was silently dropped while the caller was
    handed back an id and no error — the second measurement vanished and the first kept
    gating. `SqliteStore.record_calibration` promises "a second measurement is a second row
    with its own id"; this is the half of that promise that lives in the id.

    **`direction` is in here for a sharper version of the same reason.** It was the field
    left out of the first correction, and it is the worst one to leave out: `Direction`'s own
    docstring says guessing it "inverts the gate silently, which is the failure mode that
    produces a confidently backwards quality signal". A calibration recorded with the wrong
    direction is precisely the row someone re-records to fix — and with direction outside the
    id that correction collides with the inverted original, is dropped by INSERT OR IGNORE,
    and leaves the backwards gate live while reporting the fix as recorded.

    **`evidence_class` and `grain` are in here for the third instance of the same reason,
    and it is the sharpest.** The row someone re-records is the one whose class was wrong —
    a corpus measurement filed as a judgment is precisely the mistake this field exists to
    make sayable, and therefore precisely the mistake someone will correct. With the class
    outside the id, that correction collides with the mislabelled original, is dropped by
    `INSERT OR IGNORE`, and leaves the mislabelled row promoting while reporting the fix as
    recorded.
    """
    material = payload_digest(
        {
            "metric": metric_id,
            "threshold": threshold,
            "verdicts": verdicts_digest,
            "direction": direction.value,
            "precision": precision,
            "holdout_size": holdout_size,
            "flagged": flagged,
            "evidence_class": evidence_class.value,
            "grain": grain.value,
        }
    )
    return f"cal-{sha256(material.encode()).hexdigest()[:24]}"


def verdicts_digest_for(verdicts: Iterable[tuple[str, str]]) -> str:
    """Content address over a verdict set — (sample_id, verdict) pairs.

    Sorted before hashing, so the digest is a fact about *which* judgments were used and not
    about the order a query returned them in.
    """
    pairs = sorted((str(sample), str(verdict)) for sample, verdict in verdicts)
    return payload_digest({"verdicts": pairs})


def _detail(calibration: Calibration, value: float) -> str:
    """What the gate says about itself, in the vocabulary its evidence supports.

    A population gate reports a position in a distribution and names the cohort, the band and
    the control that licensed it. It never says "precision", because it has none: a
    percentile predicts nothing about a reader. The two branches exist so an operator reading
    a refusal cannot mistake which claim was made.
    """
    common = f"{value} vs threshold {calibration.threshold} ({calibration.direction.value})"
    population = calibration.population
    if calibration.evidence_class is EvidenceClass.POPULATION and population is not None:
        return (
            f"{common}; outside the {population.quantile} of {population.cohort} at "
            f"{population.band} words (n={population.reference_n}), control "
            f"{population.control_cohort} exceeds at {population.control_exceedance:.4f} "
            f"against {population.reference_exceedance:.4f}. A statement about range, "
            "not about quality"
        )
    return (
        f"{common}; precision {calibration.precision:.2f} on "
        f"{calibration.holdout_size} held-out"
    )


def veto_for(evidence_class: EvidenceClass) -> Veto:
    """The strongest claim this class of evidence licenses, as a veto.

    Total over the enum on purpose: a class with no mapping raises here rather than falling
    back to `CRAFT_BELOW_BAR`, because the fallback is the claim this module exists to
    stop being made for free.
    """
    if evidence_class is EvidenceClass.JUDGMENT:
        return Veto.CRAFT_BELOW_BAR
    if evidence_class is EvidenceClass.POPULATION:
        return Veto.CRAFT_OUT_OF_DISTRIBUTION
    raise NotPromotable(f"{evidence_class.value} evidence licenses no refusal")


def promoted_gate(
    calibration: Calibration,
    value: float,
    *,
    today: str,
    verdicts_digest: str | None = None,
    decision_grain: Grain = Grain.UNIT,
    answered: int | None = None,
) -> GateOutcome:
    """Build a **blocking** craft gate from calibrated evidence, or refuse to.

    The only function in this package that can produce one. `craft.craft_gates` builds
    annotations and has no branch that could reach here, so a metric cannot drift into
    blocking by a threshold being filled in somewhere — it has to come through this door, and
    this door checks.

    Raises `NotPromotable` rather than returning an advisory gate on failure. Degrading
    silently is how a gate everyone believes is on turns out to have been off.
    """
    reason = calibration.why_not_promotable(
        today, verdicts_digest, decision_grain=decision_grain, answered=answered
    )
    if reason is not None:
        raise NotPromotable(f"{calibration.metric_id}: {reason}")
    veto = veto_for(calibration.evidence_class)
    passed = not calibration.blocks_at(value)
    gate = GateOutcome(
        gate=GateKind.CRAFT,
        rule_or_critic_id=calibration.metric_id,
        passed=passed,
        # A deterministic proxy over prose, validated against human judgment. Not
        # `CALIBRATED_CRITIC`, which is for a model whose verdict was calibrated; the
        # distinction matters because MirrorBench's invariant is about model self-report and
        # this is arithmetic over text.
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        # Named, because `policy.decide` acts on the veto and a blocking gate that fails
        # without one escalates as "a blocking gate failed without naming a veto" — the
        # anonymous refusal that sends a human every scene the gate stops. Both craft vetoes
        # are classified `PARKABLE`, so this refusal parks the unit revivably instead.
        #
        # **The veto comes from the evidence class rather than being a constant**, and that
        # is the whole enforcement. A corpus percentile refusing a scene must not emit the
        # word "below bar": it did not measure a bar. `veto_for` is total over the enum, so
        # a future class with no mapping raises here instead of inheriting a quality claim.
        vetoes=() if passed else (veto,),
        detail=_detail(calibration, value),
        calibration_id=calibration.calibration_id,
    )
    # Belt and braces, and cheap: `PolicyDecision` enforces the same invariant, but a gate is
    # constructed here and validated there, so a caller that never builds a decision would
    # otherwise carry an unchecked blocking gate around.
    if gate.calibration_id is None:  # pragma: no cover - unreachable by construction
        raise UntrustedVerdict("a promoted craft gate must cite its calibration")
    return gate


__all__ = [
    "MAX_CONTROL_RATIO",
    "MAX_REFERENCE_EXCEEDANCE",
    "MIN_FLAGGED",
    "MIN_HOLDOUT",
    "MIN_PRECISION",
    "MIN_TAIL_SUPPORT",
    "Calibration",
    "Direction",
    "EvidenceClass",
    "Grain",
    "NotPromotable",
    "Population",
    "calibration_id_for",
    "promoted_gate",
    "verdicts_digest_for",
    "veto_for",
]
