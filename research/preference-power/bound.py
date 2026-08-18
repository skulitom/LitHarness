"""A cell-aggregated twin of `preference.win_rate_lower_bound`, and the proof it is that function.

The study in `simulate.py` needs the §61 bound evaluated a few million times. The shipped
estimator walks every observation inside every one of its 2,000 resamples, which is the right
shape for a store holding one panel's verdicts and the wrong shape for a Monte Carlo sweep. So
this module computes the same number by walking *cells* — one entry per (reader, pair) that has
any judgment in it — instead of observations.

**The twin must be the shipped function, not a defensible approximation of it, or the study
measures something nobody ships.** Two facts make that achievable rather than aspirational.
First, the resampled rate is a ratio of two bilinear forms: with `nr` the reader multiplicities
and `np` the pair multiplicities, `total = nr' C np` and `won = nr' S np`, where `C` counts the
judgments in a cell and `S` sums their scores. Aggregating a cell before weighting it is
therefore algebra, not approximation. Second — and this is the part that would normally sink an
equality claim — floating-point addition is not associative, so re-ordering a sum usually
perturbs it. It does not here: scores are exactly {0.0, 0.5, 1.0}, multiplicities are small
integers, every product is a dyadic rational well inside 2**53, and sums of such values are
computed exactly in binary64 regardless of order. The two orderings agree bit for bit, and
`verify_equivalence` below asserts that rather than assuming it.

The RNG is reproduced rather than replaced. `win_rate_lower_bound` seeds `Random` from a
`payload_digest` of the judgment set itself, so the bound is a fact about the evidence and not
about a session; a twin that seeded itself differently would still be *an* estimator with the
same distribution, but it would not be the one whose operating characteristics this study claims
to report. `seed_for` reconstructs the digest exactly, including the sorted tuple form the
shipped code hashes.

Run the equivalence check on its own:

    uv run python research/preference-power/bound.py
"""

from __future__ import annotations

import math
from random import Random

from litharness.domain.events import payload_digest
from litharness.domain.preference import (
    BOOTSTRAP_RESAMPLES,
    PairOutcome,
    TiePolicy,
    WinObservation,
    win_rate_lower_bound,
)

#: Score of each outcome, mirroring `preference._SCORE`. Duplicated rather than imported because
#: it is private there, and a study that reached into a private mapping would break silently on a
#: rename instead of loudly — `verify_equivalence` is what keeps the copy honest.
SCORE = {PairOutcome.WIN: 1.0, PairOutcome.TIE: 0.5, PairOutcome.LOSS: 0.0}


def seed_for(judgments: list[WinObservation]) -> int:
    """The integer seed `win_rate_lower_bound` derives from this judgment set.

    Reproduced exactly: the shipped code hashes `{"judgments": sorted((pair, reader, outcome))}`
    and takes the first 16 hex characters as a 64-bit seed. The sort is over tuples and the JSON
    rendering turns them into arrays, so the digest depends on the *set* of judgments and not on
    the order they were recorded — which is the property that makes a replayed draw reproduce a
    bound, and the property this study inherits for free.
    """
    material = payload_digest(
        {"judgments": sorted((j.pair_id, j.reader_id, j.outcome.value) for j in judgments)}
    )
    return int(material[:16], 16)


def _analysis(judgments: list[WinObservation], tie_policy: TiePolicy) -> list[WinObservation]:
    """The rows the shipped code seeds from: ties dropped first under `DROP`.

    Mirrors `preference._analysis_set`, which runs *before* the digest is taken — so a tie
    policy of `DROP` changes the seed as well as the sample. Getting this wrong produces a twin
    that is right on average and never equal, which is exactly the failure this module exists to
    rule out.
    """
    if tie_policy is TiePolicy.DROP:
        return [j for j in judgments if j.outcome is not PairOutcome.TIE]
    return list(judgments)


def cells_for(
    judgments: list[WinObservation], tie_policy: TiePolicy
) -> tuple[list[tuple[int, int, int, float]], int, int]:
    """Collapse an analysis set into `(reader_ix, pair_ix, count, score_sum)` cells.

    Applies the declared tie policy first, because `DROP` removes rows from the analysis set
    entirely and can therefore remove a reader or a pair from the cluster count — a panel that
    ties often is a panel with fewer clusters than it recruited, which is one of the things the
    study exists to price. Reader and pair indices follow the shipped code's sorted order so the
    two implementations agree on which cluster is which; nothing downstream depends on that, but
    a twin that permuted the labels would make a debugging session impossible.
    """
    rows = _analysis(judgments, tie_policy)
    readers = sorted({j.reader_id for j in rows})
    pairs = sorted({j.pair_id for j in rows})
    reader_ix = {r: i for i, r in enumerate(readers)}
    pair_ix = {p: i for i, p in enumerate(pairs)}
    acc: dict[tuple[int, int], list[float]] = {}
    for j in rows:
        key = (reader_ix[j.reader_id], pair_ix[j.pair_id])
        entry = acc.get(key)
        if entry is None:
            acc[key] = [1.0, SCORE[j.outcome]]
        else:
            entry[0] += 1.0
            entry[1] += SCORE[j.outcome]
    cells = [(r, p, int(c), s) for (r, p), (c, s) in acc.items()]
    return cells, len(readers), len(pairs)


def _resampled_rates(
    cells: list[tuple[int, int, int, float]],
    n_readers: int,
    n_pairs: int,
    *,
    seed: int,
    resamples: int,
) -> list[float]:
    """The sorted bootstrap rates every bound is a quantile of — the whole cost of the estimator.

    Refuses below two clusters in either dimension for the shipped reason: an interval clustered
    over fewer than two of either is one observation wearing an interval. The refusal is a real
    outcome of a panel design, not an error to be swallowed — `simulate.py` counts how often a
    design lands here, because a panel that cannot be bounded at all is a panel that wasted its
    whole budget, and that is a cost the power number alone would hide.
    """
    if not cells:
        raise ValueError("no decisive judgment to bound a rate over")
    if n_readers < 2 or n_pairs < 2:
        raise ValueError(
            f"{n_readers} reader cluster(s) and {n_pairs} pair cluster(s); an interval "
            "clustered over fewer than two of either is one observation wearing an interval"
        )
    rng = Random(seed)
    draw = rng.randrange
    rates: list[float] = []
    append = rates.append
    for _ in range(resamples):
        reader_w = [0] * n_readers
        for _ in range(n_readers):
            reader_w[draw(n_readers)] += 1
        pair_w = [0] * n_pairs
        for _ in range(n_pairs):
            pair_w[draw(n_pairs)] += 1
        total = 0.0
        won = 0.0
        for r, p, count, score_sum in cells:
            weight = reader_w[r] * pair_w[p]
            if weight:
                total += weight * count
                won += weight * score_sum
        if total:
            append(won / total)
    if not rates:
        raise ValueError(
            "every bootstrap resample was empty; the judgments are too sparsely crossed over "
            "readers and pairs to bound"
        )
    rates.sort()
    return rates


def bound_from_cells(
    cells: list[tuple[int, int, int, float]],
    n_readers: int,
    n_pairs: int,
    *,
    alpha: float,
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> float:
    """The §61 lower bound, computed over cells instead of observations."""
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha {alpha} is not a confidence level")
    rates = _resampled_rates(cells, n_readers, n_pairs, seed=seed, resamples=resamples)
    index = max(0, math.ceil((alpha / 2.0) * len(rates)) - 1)
    return rates[min(index, len(rates) - 1)]


def bounds_at(
    cells: list[tuple[int, int, int, float]],
    n_readers: int,
    n_pairs: int,
    *,
    alphas: tuple[float, ...],
    seed: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> list[float]:
    """Every requested alpha's bound out of ONE bootstrap, on the shipped rank convention.

    The 2,000 resamples are the entire cost; reading several quantiles off the sorted rates is
    free. That matters because the estimator turned out to be far more conservative than its
    nominal level, which makes a type-I event rare and a rare-event rate expensive to measure —
    2,000 replicates of a 0.1% event is two events, and two events distinguish nothing. Reading
    a whole coverage curve instead turns the same compute into an answer to the question that
    actually spends money: **what alpha would have to be requested for the bound to hold at a
    true 2.5%**.

    Every element uses `win_rate_lower_bound`'s exact index rule, so `bounds_at(..., (0.05,))[0]`
    is that function's return value and not an approximation of it.
    """
    for alpha in alphas:
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha {alpha} is not a confidence level")
    rates = _resampled_rates(cells, n_readers, n_pairs, seed=seed, resamples=resamples)
    out = []
    for alpha in alphas:
        index = max(0, math.ceil((alpha / 2.0) * len(rates)) - 1)
        out.append(rates[min(index, len(rates) - 1)])
    return out


def twin_bound(judgments: list[WinObservation], *, alpha: float, tie_policy: TiePolicy) -> float:
    """`win_rate_lower_bound`'s signature, served by the cell path."""
    cells, n_readers, n_pairs = cells_for(judgments, tie_policy)
    return bound_from_cells(
        cells,
        n_readers,
        n_pairs,
        alpha=alpha,
        seed=seed_for(_analysis(judgments, tie_policy)),
    )


def verify_equivalence(trials: int = 60, *, verbose: bool = True) -> int:
    """Assert the twin equals the shipped function bit for bit, over adversarial shapes.

    Covers the shapes most likely to break an equality claim rather than a random sample of easy
    ones: the two-cluster floor where the bound is degenerate, all-win and all-loss sets where
    the rate sits on a boundary, heavy-tie sets under both policies (which is where `DROP`
    changes the seed as well as the sample), ragged incomplete designs where most cells are
    empty, and duplicated observations in one cell, which is the position-swap shape the
    estimator was written for. A refusal counts as agreement only if both sides refuse.
    """
    rng = Random(20260818)
    shapes = [(2, 2), (2, 5), (5, 2), (3, 7), (5, 5), (8, 20), (12, 40), (20, 15)]
    checked = 0
    for trial in range(trials):
        n_readers, n_pairs = shapes[trial % len(shapes)]
        tie_policy = TiePolicy.HALF_WIN if trial % 2 else TiePolicy.DROP
        alpha = (0.05, 0.01, 0.05 / 3.0)[trial % 3]
        mode = trial % 5
        judgments: list[WinObservation] = []
        for r in range(n_readers):
            for p in range(n_pairs):
                if mode == 3 and rng.random() < 0.55:
                    continue  # ragged incomplete design: most cells empty
                for _ in range(2 if mode == 4 else 1):  # position swap: two rows per cell
                    if mode == 0:
                        outcome = PairOutcome.WIN
                    elif mode == 1:
                        outcome = PairOutcome.LOSS
                    elif mode == 2:
                        outcome = rng.choice(
                            [PairOutcome.TIE, PairOutcome.TIE, PairOutcome.WIN, PairOutcome.LOSS]
                        )
                    else:
                        outcome = rng.choice([PairOutcome.WIN, PairOutcome.LOSS, PairOutcome.TIE])
                    judgments.append(
                        WinObservation(
                            pair_id=f"pair-{p:03d}",
                            reader_id=f"rdr-{r:03d}",
                            outcome=outcome,
                        )
                    )
        shipped_error: ValueError | None = None
        expected = 0.0
        try:
            expected = win_rate_lower_bound(judgments, alpha=alpha, tie_policy=tie_policy)
        except ValueError as exc:
            shipped_error = exc
        try:
            got = twin_bound(judgments, alpha=alpha, tie_policy=tie_policy)
        except ValueError as twin_exc:
            if shipped_error is None:
                raise AssertionError(
                    f"trial {trial}: twin refused ({twin_exc}) but shipped returned {expected}"
                ) from twin_exc
            checked += 1
            continue
        if shipped_error is not None:
            raise AssertionError(
                f"trial {trial}: shipped refused ({shipped_error}) but twin returned {got}"
            )
        assert got == expected, (
            f"trial {trial} ({n_readers}x{n_pairs}, {tie_policy}, alpha={alpha}): "
            f"twin {got!r} != shipped {expected!r}"
        )
        checked += 1
    if verbose:
        print(f"equivalence: {checked}/{trials} shapes agree bit for bit with win_rate_lower_bound")
    return checked


if __name__ == "__main__":
    verify_equivalence()
