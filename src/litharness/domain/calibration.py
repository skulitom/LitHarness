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

**Precision has a floor, and the floor is a confidence bound rather than an estimate.** §10.4
asks for "usable precision at an acceptable workload"; §10.5 adds that audit disagreement
re-opens calibration. Numbers with no minimum are a rubber stamp, so the minimums are named
constants here and a calibration below them cannot be promoted. They are **not** measured
values — nothing in this project has measured what precision is usable, and the constants say
so. What *is* derived is the bar the numbers must clear: a stored point estimate at 0.80 is
not a claim that precision is 0.80, and 14 correct flags of 17 made that concrete by passing
every check this module had at a true lower bound of 0.566. `exact_lower_bound` is that
arithmetic, and the counts it needs are what the record stores.

**Nothing here computes a calibration.** Fitting a threshold to human verdicts is a statistics
problem this module deliberately does not solve, because solving it before any verdicts exist
would be fitting to an empty set. What it does is refuse to let a threshold in without the
evidence attached — which is the part that has to exist *before* the data, not after.
"""

from __future__ import annotations

import enum
import math
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

#: Family-wise two-sided confidence level for the precision bound below. `MIN_PRECISION` says
#: how good the metric must be; this says how sure we must be that it is. Two-sided rather
#: than one-sided so the bar keeps the lineage of the `MIN_FLAGGED = 17` it replaces — 17 was
#: derived as the smallest perfect flagged set whose two-sided 95% bound clears 0.80, and a
#: silent switch to one-sided would have moved that to 14 while looking like a refactor.
#:
#: A one-sided limit is defensible — the claim *is* directional — and is deliberately not
#: taken, for the same reason `MAX_REFERENCE_EXCEEDANCE` refuses only the incoherent: which
#: convention to declare belongs to whoever first has evidence to promote. It is a module
#: constant rather than a stored column so that it cannot become the knob a maintainer turns
#: after a near miss.
PROMOTION_ALPHA = 0.05


def exact_lower_bound(correct: int, flagged: int, alpha: float = PROMOTION_ALPHA) -> float:
    """Clopper-Pearson lower confidence limit on precision, at two-sided level `alpha`.

    **The check `MIN_FLAGGED` was a proxy for, done exactly.** That constant ruled out the
    case it was written for — a metric that fires twice, gets it right, and reports 1.00 —
    and its own comment said it did not make `MIN_PRECISION` a confidence bound in general.
    It did not: 14 correct flags out of 17 on a holdout of 50 passed every check this module
    had, at a true lower bound of **0.566**. The bound is what the floor was reaching for, so
    the floor is gone and this is the bar.

    `L` solves `P(Bin(flagged, L) >= correct) = alpha / 2` and is computed by bisection on
    that tail, which is increasing in `p`. No `scipy`: the sum is a few hundred terms of
    exact-integer binomial coefficients taken in log space, and a promotion bar the project
    cannot recompute from arithmetic it owns is a bar it has to take somebody's word for.
    Verified against every row of `research/certified-bounded-revision` Appendix B.

    Two properties the callers rely on: `L <= correct / flagged` always, so this check
    subsumes the point-estimate check it replaces; and `L` is increasing in `correct` and
    decreasing in `alpha`, so neither more evidence nor a stricter level can help a gate.
    """
    if not 0 <= correct <= flagged or flagged <= 0:
        raise ValueError(f"{correct} correct of {flagged} flagged is not a count pair")
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha {alpha} is not a confidence level")
    if correct == 0:
        return 0.0
    tail = alpha / 2.0

    def at_least(p: float) -> float:
        """`P(Bin(flagged, p) >= correct)`, summed in log space so large `n` cannot overflow."""
        if p <= 0.0:
            return 0.0
        if p >= 1.0:
            return 1.0
        log_p, log_q = math.log(p), math.log1p(-p)
        total = 0.0
        for i in range(correct, flagged + 1):
            total += math.exp(
                math.lgamma(flagged + 1)
                - math.lgamma(i + 1)
                - math.lgamma(flagged - i + 1)
                + i * log_p
                + (flagged - i) * log_q
            )
        return total

    low, high = 0.0, 1.0
    for _ in range(200):
        mid = (low + high) / 2.0
        if at_least(mid) < tail:
            low = mid
        else:
            high = mid
    return low


#: A population gate's control cohort may cross the reference cohort's threshold at most this
#: many times as often before the threshold is refused. **A placed constant, and the one that
#: guards this whole route's epistemic claim** — it has no derivation behind it the way
#: `PROMOTION_ALPHA`'s bound does, and it is the lever a maintainer will reach for the first time a
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
#: **Derived rather than placed.** `research/quality-measurement/build_craft_profile.py`
#: indexes a stop at
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
    #: `precision` is computed over. `None` means the measurement did not record it, which is
    #: not promotable: an unrecorded flagged count is indistinguishable from a flagged count
    #: of one, and a bound over one flag is 0.025.
    flagged: int | None = None
    #: How many of `flagged` the human agreed with — the numerator, as an integer.
    #:
    #: **This replaced a stored `precision: float`, and the replacement is the point.** A
    #: float numerator is not a sufficient statistic: `exact_lower_bound` needs the counts,
    #: and a row storing 0.8235 cannot say whether that was 14 of 17 or 140 of 170, which are
    #: the same rate and different evidence. Worse, the pair was never checked for coherence
    #: — `precision=0.83, flagged=17` implies 14.11 correct flags and was accepted, so a
    #: malformed record could present itself as exact evidence. Counts make that
    #: unrepresentable rather than merely refused, and `precision` is now derived from them.
    correct: int | None = None
    #: How many candidate gates were safety-tested against this holdout — thresholds tried,
    #: directions tried, metrics tried, all of it.
    #:
    #: **The field that makes the bound honest, and the one nothing anywhere recorded.** The
    #: bound assumes the threshold was fixed before the labels were seen. Scan ten thresholds
    #: and keep the best and it was not, and no digest reveals this: a content address over
    #: the verdicts is identical whether one candidate was tested or a hundred. So the count
    #: is declared and the level is divided by it, which is the union bound over candidates.
    #: The cost is real rather than philosophical — at a perfect score the flags needed to
    #: clear 0.80 go 17, 24, 35 for one, ten and a hundred candidates.
    #:
    #: `1` is the honest value only for a threshold fixed in advance on separate selection
    #: data. It is not a default, for the reason `evidence_class` is not: the permissive
    #: answer must be said rather than inherited.
    selection_family_size: int | None = None
    #: Independent books or generation runs the flagged set spans.
    #:
    #: **Without this the bound is a narrower number resting on the same unexamined
    #: assumption, which is worse than no bound.** Fifty scenes from one book are not fifty
    #: independent trials — they share generator, prompt profile, arc position and revision
    #: history — and a binomial interval over them is a confident statement about one
    #: observation. The project earned this in BRIEF §2 Pass 5 ("check within-book
    #: reliability (ICC) before believing any per-book statistic") and already fixed it in
    #: `research/quality-measurement/evaluate.py`, whose AUCs are chapter-resampled. The
    #: promotion path had no cluster concept at all, so the lesson was half-applied.
    #:
    #: Only the incoherent case is refused: fewer than two clusters is one observation
    #: wearing an interval. A stricter bar — cluster bootstrap, or a cap on how much one book
    #: may contribute — is defensible and deliberately not taken, because it needs per-cluster
    #: counts nobody has yet measured. Recording the number is what makes that fixable later.
    clusters: int | None = None
    recall: float | None = None
    note: str | None = None

    @property
    def precision(self) -> float | None:
        """Point precision, derived. `None` when the counts to derive it were not recorded.

        A property rather than a field so there is one source of truth and no arithmetic to
        disagree with itself. It is reporting, not evidence: `exact_lower_bound` is the
        number promotion turns on, and it is always the smaller of the two.
        """
        if self.correct is None or not self.flagged:
            return None
        return self.correct / self.flagged

    @property
    def precision_lower_bound(self) -> float | None:
        """The bound promotion turns on, at the level this row's candidate family earns."""
        if self.correct is None or not self.flagged or not self.selection_family_size:
            return None
        if not 0 <= self.correct <= self.flagged:
            return None
        return exact_lower_bound(
            self.correct, self.flagged, PROMOTION_ALPHA / self.selection_family_size
        )

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
        prose — `MIN_HOLDOUT` counts judgments, and the precision bound is computed over
        flags on those judgments — and applying them to a corpus percentile does not make the
        percentile validated, it makes the bar meaningless. The class picks the checks; the
        checks do not generalise.

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
        """Coherence of the counts, then the bound they support, then currency.

        **The precision floor moved from the estimate to its lower confidence limit**, which
        is the whole of this module's change and the reason `MIN_FLAGGED` is gone. The old
        pair — point precision at least 0.80, at least 17 flags — admitted 14 correct of 17
        on a holdout of 50, whose exact bound is 0.566. Because the limit never exceeds the
        estimate, one check now does the work of the two it replaces and does it at every
        precision instead of only at a perfect one.
        """
        if answered is not None and self.holdout_size > answered:
            return (
                f"claims {self.holdout_size} held-out judgment(s) against a store holding "
                f"{answered} answered; the digest clause cannot catch this, because the "
                "digest of the smaller set matches itself"
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
        if self.flagged > self.holdout_size:
            return (
                f"fired on {self.flagged} of {self.holdout_size} held-out judgment(s), which "
                "is more flags than judgments; the measurement is not about this holdout"
            )
        if self.correct is None:
            return (
                "does not record how many of its flags the human agreed with; a stored rate "
                "is not a sufficient statistic, and the confidence bound promotion turns on "
                "cannot be reconstructed from it"
            )
        if not 0 <= self.correct <= self.flagged:
            return (
                f"records {self.correct} correct flag(s) out of {self.flagged}, which is not "
                "a count pair; the two numbers describe different sets"
            )
        if self.selection_family_size is None or self.selection_family_size < 1:
            return (
                "does not record how many candidate gates were safety-tested against this "
                "holdout; a threshold chosen by scanning is not a threshold fixed in advance, "
                "and no digest over the verdicts can tell the two apart. Declare 1 if the "
                "threshold was fixed before these labels were seen"
            )
        if self.clusters is None or not 2 <= self.clusters <= self.flagged:
            return (
                f"spans {self.clusters} independent book(s) or run(s) across {self.flagged} "
                "flag(s); flags from a single cluster share generator, prompt and arc "
                "position, so a binomial bound over them is a confident interval around one "
                "observation"
            )
        bound = self.precision_lower_bound
        assert bound is not None  # every input it needs was checked above
        if bound < MIN_PRECISION:
            level = PROMOTION_ALPHA / self.selection_family_size
            return (
                f"has {self.correct} correct of {self.flagged} flag(s) — point precision "
                f"{self.correct / self.flagged:.2f} — but its exact lower confidence bound "
                f"is {bound:.3f}, below the {MIN_PRECISION:.2f} floor. At "
                f"{self.selection_family_size} candidate(s) the two-sided level is "
                f"{level:.4f}; the estimate clearing the floor is not the estimate being "
                "above it with confidence"
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
    correct: int | None,
    holdout_size: int,
    flagged: int | None,
    selection_family_size: int | None = None,
    clusters: int | None = None,
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
            "correct": correct,
            "holdout_size": holdout_size,
            "flagged": flagged,
            "selection_family_size": selection_family_size,
            "clusters": clusters,
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
    # The bound, not the estimate, because the bound is what licensed the refusal. An
    # operator reading "precision 0.82" beside a scene this gate stopped would be reading the
    # number that did *not* clear the bar.
    bound = calibration.precision_lower_bound
    assert bound is not None  # only reached through `promoted_gate`, which checked the counts
    return (
        f"{common}; precision at least {bound:.2f} "
        f"({calibration.correct}/{calibration.flagged} flags) on "
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
    "MIN_HOLDOUT",
    "MIN_PRECISION",
    "MIN_TAIL_SUPPORT",
    "PROMOTION_ALPHA",
    "Calibration",
    "Direction",
    "EvidenceClass",
    "Grain",
    "NotPromotable",
    "Population",
    "calibration_id_for",
    "exact_lower_bound",
    "promoted_gate",
    "verdicts_digest_for",
    "veto_for",
]
