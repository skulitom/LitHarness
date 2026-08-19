"""Reader verdicts to a **direction** on a named axis: the half of the loop only humans can staff.

A direction is one bit — which pole of an axis readers preferred — plus the interval that bit
rests on. It is not a score, it is not a gate, and it licenses refusing nothing. What it licenses
is the other half of the composition rule: a judge may only speak on an axis a reader has given a
direction to (`plan/reader-judge-loop.md` §0.2).

**The contrast comes from sibling candidates, not from transforms.** `--plan-search` already
drafts K alternatives per span and `domain/candidates.py` already mints every sibling pair, both
orientations, through the same table humans judge. A sibling pair is admitted as evidence for
axis X when `axes.separating` returns exactly X — single-axis by *measurement* rather than by
construction. That is weaker than a certified single-variable transform and the weakness is
stated rather than buried: two drafts of one beat differ on everything unregistered as well.

**The cell, not the comparison, is the unit — and that correction is bought.** §89's rulebook
records a 30-decided floor that could not bind because "four personas gave one judge four times,
64 -> 16 cells". The same failure is available here from the other side: both orientations of one
pair answered by one reader are **one** decision, not two, and a floor counted in comparisons
would read a position-swapped pair as twice the evidence it is. So observations are collapsed to
`(reader, pair)` cells first, and a reader who *flips with position* has said nothing and
collapses to a tie — which is what the swap exists to detect.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256

from litharness.domain import axes as axes_mod
from litharness.domain.axes import Pole
from litharness.domain.events import payload_digest
from litharness.domain.pools import Pool
from litharness.domain.preference import (
    DESCRIPTIVE_CLUSTER_FLOOR,
    PairOutcome,
    PairSample,
    PairVerdict,
    TiePolicy,
    WinObservation,
    observed_win_rate,
    win_rate_lower_bound,
)

#: The confidence level a direction is bounded at. `PROMOTION_ALPHA`'s lineage: two-sided, so
#: the pair of checks below (HIGH clears, or LOW clears) is exactly one two-sided test at this
#: level and only one of them can ever fire.
DIRECTION_ALPHA = 0.05

#: Floors, declared before any verdict exists and verified attainable by `attainability` rather
#: than asserted. Each is bought by a measurement:
#:
#: - `MIN_CELLS` is §89's 30-decided floor, moved into the unit that can carry it.
#: - `MIN_READER_CLUSTERS` is `DESCRIPTIVE_CLUSTER_FLOOR` and is not a round number chosen here:
#:   `win_rate_lower_bound` refuses fewer than two clusters of either dimension, and its own
#:   docstring records that below roughly five per dimension the percentile bootstrap is
#:   *descriptive rather than calibrated* — two readers by two pairs, all wins, and the "97.5%
#:   lower bound" is 1.0 from four observations. Reading a direction off a descriptive number
#:   would be reading an interval that has not earned its level.
#: - `MIN_PAIR_CLUSTERS` clears the same floor with margin: pairs are cheap and readers are not.
MIN_CELLS = 30
MIN_READER_CLUSTERS = DESCRIPTIVE_CLUSTER_FLOOR
MIN_PAIR_CLUSTERS = 8

#: The bar itself. A lower bound strictly above this reads a direction.
DIRECTION_BAR = 0.5


class WhyNot(enum.StrEnum):
    """Why an axis has no direction. A named refusal, never a silent absence.

    §89's rulebook is the reason these are enumerated rather than rendered as a sentence: five
    of seven declared quantities that could not do their job were caught by a dry run printing
    *which* precondition was unmet, and "no direction" alone would have hidden every one of them.
    """

    NO_EVIDENCE = "no_evidence"
    TOO_FEW_CELLS = "too_few_cells"
    TOO_FEW_READERS = "too_few_readers"
    TOO_FEW_PAIRS = "too_few_pairs"
    BAR_NOT_CLEARED = "bar_not_cleared"


def direction_id_for(*, axis_id: str, preferred: Pole, verdicts_digest: str) -> str:
    """Content address over what a direction claims and the evidence it claims it from.

    So re-establishing the same direction from the same verdicts is idempotent, and a
    direction established from *moved* verdicts is a new row rather than an overwrite — the
    evidence trail `record_calibration` keeps for the same reason.
    """
    material = "\x00".join((axis_id, preferred.value, verdicts_digest)).encode()
    return f"dir-{sha256(material).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class AxisDirection:
    """A reader-established direction on one axis, and the evidence it rests on."""

    axis_id: str
    preferred: Pole
    #: Win rate of the `HIGH` side, so a `LOW` direction reads below 0.5 and the number never
    #: changes meaning with the answer.
    high_win_rate: float
    lower_bound: float
    alpha: float
    cells: int
    readers: int
    pairs: int
    #: The content address of the steering verdict set this was computed from. **The retirement
    #: mechanism**, and §72's expiry-on-use pattern moved one instrument over: a direction whose
    #: digest has moved is stale and emits nothing until it is re-established. Evidence moving
    #: under a claim retires the claim.
    verdicts_digest: str
    established_at: str
    note: str = ""

    @property
    def direction_id(self) -> str:
        return direction_id_for(
            axis_id=self.axis_id,
            preferred=self.preferred,
            verdicts_digest=self.verdicts_digest,
        )

    def stale_against(self, digest: str) -> bool:
        return self.verdicts_digest != digest


@dataclass(frozen=True, slots=True)
class DirectionReading:
    """What the evidence says about one axis, whether or not it says a direction."""

    axis_id: str
    direction: AxisDirection | None
    why_not: WhyNot | None
    cells: int
    readers: int
    pairs: int
    high_win_rate: float | None = None
    high_lower_bound: float | None = None
    low_lower_bound: float | None = None
    #: Pairs the counter separated on this axis but on more than one axis at once. Reported
    #: because it is the yield number that decides whether siblings can staff this at all
    #: (`plan/reader-judge-loop.md` §3.1), and a silently dropped pair reads as a pair that never
    #: existed.
    multi_axis_pairs: int = 0
    hypothesis_status: str = "untested"


def _cell_outcome(outcomes: Sequence[PairOutcome]) -> PairOutcome:
    """One `(reader, pair)` cell's decision, over however many orientations it holds.

    A reader who prefers the same text in both presented orders has decided; one who prefers
    whichever came first has not, and collapses to a tie. That is not a convention — it is the
    only reading under which a position-swapped design measures anything, and the alternative
    (counting both orientations as independent trials) is how §79.1's 0.64 and §86.6's 0.8151
    would enter a bound as evidence rather than as bias.
    """
    wins = sum(1 for outcome in outcomes if outcome is PairOutcome.WIN)
    losses = sum(1 for outcome in outcomes if outcome is PairOutcome.LOSS)
    if wins > losses:
        return PairOutcome.WIN
    if losses > wins:
        return PairOutcome.LOSS
    return PairOutcome.TIE


def axis_observations(
    samples: Sequence[PairSample],
    texts: Mapping[str, str],
    axis_id: str,
    *,
    reader_pool: Callable[[str], Pool],
) -> tuple[tuple[WinObservation, ...], int]:
    """Steering-pool cells bearing on `axis_id`, and the count of multi-axis pairs skipped.

    The outcome is scored for the **`HIGH` side**: `WIN` means the reader preferred the text
    with more of the counted thing. Excluded, each for a reason that already exists in this
    engine: an unanswered row, a recognised one (§61 pre-registration (3)), an abstention, a
    member whose text is not resolvable, a pair the counter ties, a pair more than one counter
    separates, and any verdict from a measurement-pool reader (`plan/reader-judge-loop.md` §1.3
    — calibrating on measurement-pool verdicts and then steering is the same contamination with
    one extra hop).
    """
    per_cell: dict[tuple[str, str], list[PairOutcome]] = {}
    multi_axis: set[str] = set()
    for sample in samples:
        if sample.verdict is None or sample.recognized or sample.reader_id is None:
            continue
        if sample.verdict is PairVerdict.NOT_SURE:
            continue
        if reader_pool(sample.reader_id) is not Pool.STEERING:
            continue
        left = texts.get(sample.left_addr)
        right = texts.get(sample.right_addr)
        if left is None or right is None or left == right:
            continue
        separating = axes_mod.separating(left, right)
        if separating != (axis_id,):
            if axis_id in separating:
                multi_axis.add(sample.pair_id)
            continue
        high = axes_mod.higher(axis_id, left, right)
        if high is None:  # unreachable while `separating` reports this axis; belt and braces.
            continue
        if sample.verdict is PairVerdict.TIE:
            outcome = PairOutcome.TIE
        else:
            preferred = (
                left if sample.verdict is PairVerdict.PREFER_FIRST else right
            )
            outcome = PairOutcome.WIN if preferred == high else PairOutcome.LOSS
        per_cell.setdefault((sample.reader_id, sample.pair_id), []).append(outcome)
    observations = tuple(
        WinObservation(pair_id=pair_id, reader_id=reader_id, outcome=_cell_outcome(found))
        for (reader_id, pair_id), found in sorted(per_cell.items())
    )
    return observations, len(multi_axis)


def observations_digest(observations: Sequence[WinObservation]) -> str:
    """Content address over the cells a direction was computed from."""
    return payload_digest(
        {
            "cells": sorted(
                (o.pair_id, o.reader_id, o.outcome.value) for o in observations
            )
        }
    )


def _bound(
    observations: Sequence[WinObservation], *, alpha: float, tie_policy: TiePolicy
) -> float | None:
    try:
        return win_rate_lower_bound(
            observations, alpha=alpha, tie_policy=tie_policy
        )
    except ValueError:
        return None


def _inverted(observations: Sequence[WinObservation]) -> tuple[WinObservation, ...]:
    flip = {
        PairOutcome.WIN: PairOutcome.LOSS,
        PairOutcome.LOSS: PairOutcome.WIN,
        PairOutcome.TIE: PairOutcome.TIE,
    }
    return tuple(
        WinObservation(pair_id=o.pair_id, reader_id=o.reader_id, outcome=flip[o.outcome])
        for o in observations
    )


def read_direction(
    axis_id: str,
    samples: Sequence[PairSample],
    texts: Mapping[str, str],
    *,
    reader_pool: Callable[[str], Pool],
    established_at: str,
    alpha: float = DIRECTION_ALPHA,
    tie_policy: TiePolicy = TiePolicy.DROP,
) -> DirectionReading:
    """What the steering readers say about this axis, and why they say nothing when they do.

    **The bar, and I7's four checks, run in order.** *Range*: a win rate and both bounds live in
    [0, 1] and the bar 0.5 is interior. *Direction*: the `HIGH` bound above 0.5 reads HIGH, the
    same statistic on inverted outcomes reads LOW, and only one can fire. *Unit*: decisive cells
    under the declared tie policy. *Non-emptiness*: the three floors above, plus a bootstrap
    spread strictly greater than zero, because a zero-width band is §85's measured defect and
    `win_rate_lower_bound` reaches one at its own cluster floor.
    """
    observations, multi_axis = axis_observations(
        samples, texts, axis_id, reader_pool=reader_pool
    )
    readers = len({o.reader_id for o in observations})
    pairs = len({o.pair_id for o in observations})
    decisive = [o for o in observations if o.outcome is not PairOutcome.TIE]
    cells = len(decisive) if tie_policy is TiePolicy.DROP else len(observations)

    def refuse(why: WhyNot) -> DirectionReading:
        return DirectionReading(
            axis_id=axis_id,
            direction=None,
            why_not=why,
            cells=cells,
            readers=readers,
            pairs=pairs,
            multi_axis_pairs=multi_axis,
            hypothesis_status="untested",
        )

    if not observations:
        return refuse(WhyNot.NO_EVIDENCE)
    if cells < MIN_CELLS:
        return refuse(WhyNot.TOO_FEW_CELLS)
    if readers < MIN_READER_CLUSTERS:
        return refuse(WhyNot.TOO_FEW_READERS)
    if pairs < MIN_PAIR_CLUSTERS:
        return refuse(WhyNot.TOO_FEW_PAIRS)

    high_bound = _bound(observations, alpha=alpha, tie_policy=tie_policy)
    low_bound = _bound(_inverted(observations), alpha=alpha, tie_policy=tie_policy)
    if high_bound is None or low_bound is None:
        return refuse(WhyNot.NO_EVIDENCE)
    rate = observed_win_rate(observations, tie_policy=tie_policy)

    # **A zero-width band was going to be refused here, and checking the bar against its own
    # operating characteristic is what caught it.** Both one-sided bounds summing to 1.0 means
    # every resample returned the same rate — which at the two-reader floor is §85's zero-width
    # defect, and at these floors is *unanimity*: thirty cells over five readers and eight pairs
    # all pointing one way. Refusing that would have been a bar wrong in the direction of false
    # failure, which is precisely what T0's registered bar did to a good judge 82-100% of the
    # time before its operating characteristic was measured. The cluster floors above are what
    # excludes the four-observation case, so the width check was doing nothing the floors did
    # not already do and was throwing away the strongest evidence this channel can produce.
    preferred: Pole | None = None
    if high_bound > DIRECTION_BAR:
        preferred = Pole.HIGH
    elif low_bound > DIRECTION_BAR:
        preferred = Pole.LOW
    if preferred is None:
        return _with_numbers(refuse(WhyNot.BAR_NOT_CLEARED), rate, high_bound, low_bound)

    axis = axes_mod.AXES[axis_id]
    direction = AxisDirection(
        axis_id=axis_id,
        preferred=preferred,
        high_win_rate=rate,
        lower_bound=high_bound if preferred is Pole.HIGH else low_bound,
        alpha=alpha,
        cells=cells,
        readers=readers,
        pairs=pairs,
        verdicts_digest=observations_digest(observations),
        established_at=established_at,
    )
    return DirectionReading(
        axis_id=axis_id,
        direction=direction,
        why_not=None,
        cells=cells,
        readers=readers,
        pairs=pairs,
        high_win_rate=rate,
        high_lower_bound=high_bound,
        low_lower_bound=low_bound,
        multi_axis_pairs=multi_axis,
        hypothesis_status=(
            "confirmed" if preferred is axis.hypothesis else "refuted"
        ),
    )


def _with_numbers(
    reading: DirectionReading, rate: float, high: float, low: float
) -> DirectionReading:
    from dataclasses import replace

    return replace(
        reading, high_win_rate=rate, high_lower_bound=high, low_lower_bound=low
    )


@dataclass(frozen=True, slots=True)
class Attainability:
    """Whether the declared bar can do what it says, computed rather than asserted.

    **I7's second half is what this exists for.** T0's own registered bar disqualified a *good*
    judge 82-100% of the time until its operating characteristic was measured, so a bar can be
    wrong in the direction of false failure as easily as false pass. `smallest_clearing_k` is the
    first check; `power` is the second, and a bar that rejects a true 0.65 most of the time is
    broken whatever its floor says.
    """

    readers: int
    pairs: int
    cells: int
    smallest_clearing_k: int | None
    power: Mapping[float, float] = field(default_factory=dict)
    #: Cells needed for `TARGET_POWER` at each true rate. **The number the floors do not
    #: give you**, and it is the honest half of this report: `MIN_CELLS` is a coherence floor
    #: inherited from §89, not a sample size, and at the minimum shape a true 0.65 clears the
    #: bar about a fifth of the time. An operator sizing a batch needs this column, and a
    #: report that printed only the floor would let them buy thirty judgments and conclude
    #: from a null that the axis has no direction.
    cells_for_power: Mapping[float, int | None] = field(default_factory=dict)

    @property
    def attainable(self) -> bool:
        return self.smallest_clearing_k is not None


def _synthetic(readers: int, pairs: int, cells: int, wins: int) -> list[WinObservation]:
    """`cells` cells spread evenly over `readers` x `pairs`, `wins` of them won.

    Evenly rather than randomly: an attainability number that moved with a seed would be a
    property of the seed. Cells are laid out round-robin so both cluster dimensions are crossed,
    which is the shape `win_rate_lower_bound` needs and the shape a real queue produces.
    """
    out: list[WinObservation] = []
    for index in range(cells):
        out.append(
            WinObservation(
                pair_id=f"pair-{index % pairs}",
                reader_id=f"reader-{index % readers}",
                outcome=PairOutcome.WIN if index < wins else PairOutcome.LOSS,
            )
        )
    return out


#: The power an operator should size a batch to. Conventional rather than measured, and
#: labelled as such: nothing in this project has measured what power a direction deserves, and
#: 0.8 is the number every field uses when it has not.
TARGET_POWER = 0.8

#: Where the sample-size sweep gives up, and how coarsely it steps. A rate this close to
#: indifference needs more judgments than this project will ever buy, and saying so beats
#: searching forever; the step is the granularity the answer is honest to.
_SIZING_CEILING = 400
_SIZING_STEP = 10


def _smallest_clearing_k(
    *, readers: int, pairs: int, cells: int, alpha: float, tie_policy: TiePolicy
) -> int | None:
    """Fewest wins out of `cells` whose bound clears the bar, by bisection.

    Bisection is exact here rather than an approximation: at a fixed layout the bound is
    monotone in the win count — swapping a loss for a win raises every resample's rate — so
    the clearing set is an upward-closed interval and its least element is what bisection
    finds. A linear scan found the same numbers and cost eight times as much.
    """
    if _bound(
        _synthetic(readers, pairs, cells, cells), alpha=alpha, tie_policy=tie_policy
    ) is None:
        return None
    if (
        _bound(_synthetic(readers, pairs, cells, cells), alpha=alpha, tie_policy=tie_policy)
        or 0.0
    ) <= DIRECTION_BAR:
        return None
    low, high = 0, cells
    while low < high:
        middle = (low + high) // 2
        bound = _bound(
            _synthetic(readers, pairs, cells, middle), alpha=alpha, tie_policy=tie_policy
        )
        if bound is not None and bound > DIRECTION_BAR:
            high = middle
        else:
            low = middle + 1
    return low


def attainability(
    *,
    readers: int = MIN_READER_CLUSTERS,
    pairs: int = MIN_PAIR_CLUSTERS,
    cells: int = MIN_CELLS,
    alpha: float = DIRECTION_ALPHA,
    tie_policy: TiePolicy = TiePolicy.DROP,
    true_rates: Sequence[float] = (0.55, 0.60, 0.65, 0.70, 0.80),
    size: bool = True,
) -> Attainability:
    """The smallest k that clears the bar at this shape, the bar's power, and a sample size.

    **I7's second half is what this exists for.** T0's own registered bar disqualified a
    *good* judge 82-100% of the time until its operating characteristic was measured, so a bar
    can be wrong in the direction of false failure as easily as false pass.
    `smallest_clearing_k` is the first check; `power` is the second, and `cells_for_power` is
    the one an operator actually spends money against — `MIN_CELLS` is a coherence floor
    inherited from §89, not a sample size, and the two are easy to confuse exactly once.

    Power is computed at the deterministic layout below rather than by resampling readers:
    with `cells` cells and a true rate p the number of wins is Binomial(cells, p), and the bar
    fires exactly when that count reaches `smallest_clearing_k`, because the bound is monotone
    in the win count at a fixed layout. So the power is one binomial tail, exact, no seed.

    `size=False` skips the sample-size sweep, which is the expensive half — every step runs a
    fresh bootstrap — for callers that only need the floor's own characteristic.
    """
    smallest = _smallest_clearing_k(
        readers=readers, pairs=pairs, cells=cells, alpha=alpha, tie_policy=tie_policy
    )
    power: dict[float, float] = {}
    sizing: dict[float, int | None] = {}
    if smallest is not None:
        for rate in true_rates:
            power[rate] = _binomial_tail(cells, smallest, rate)
        if size:
            # One sweep for every rate: the clearing k at a given cell count does not depend
            # on the true rate, so recomputing it per rate was five times the work for the
            # same table.
            table: list[tuple[int, int]] = []
            for step in range(MIN_CELLS, _SIZING_CEILING, _SIZING_STEP):
                found = _smallest_clearing_k(
                    readers=readers, pairs=pairs, cells=step, alpha=alpha,
                    tie_policy=tie_policy,
                )
                if found is not None:
                    table.append((step, found))
            for rate in true_rates:
                sizing[rate] = next(
                    (
                        step
                        for step, k in table
                        if _binomial_tail(step, k, rate) >= TARGET_POWER
                    ),
                    None,
                )
    return Attainability(
        readers=readers,
        pairs=pairs,
        cells=cells,
        smallest_clearing_k=smallest,
        power=power,
        cells_for_power=sizing,
    )


def _binomial_tail(n: int, k: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Exact, by summation — n is thirty-ish."""
    from math import comb

    return sum(comb(n, i) * (p**i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1))


__all__ = [
    "DIRECTION_ALPHA",
    "DIRECTION_BAR",
    "MIN_CELLS",
    "MIN_PAIR_CLUSTERS",
    "MIN_READER_CLUSTERS",
    "TARGET_POWER",
    "Attainability",
    "AxisDirection",
    "DirectionReading",
    "WhyNot",
    "attainability",
    "axis_observations",
    "direction_id_for",
    "observations_digest",
    "read_direction",
]
