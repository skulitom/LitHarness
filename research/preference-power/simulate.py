"""What §61's bar costs: the operating characteristics of `win_rate_lower_bound`.

The preference engine shipped with an empty verdict store, and the README of the time called it
the instrument that could measure quality, "built and waiting on funded judgment". Nobody had
said how much judgment. (The channel was retired outright on 2026-08-19 by the scope axiom,
ledger §95; this module's finding is about the *estimator* and survives the retirement.)
This module answers that by simulation, using the shipped estimator itself
(via `bound.py`'s bit-identical twin) rather than a normal approximation to it.

**The bound's calibration is a function of reader heterogeneity, and the first pilot got that
backwards.** The failure worth fearing was a bar easier than it claims — a bound clearing 0.5
more than 2.5% of the time when the system merely equals its comparator. Run with no reader or
pair effect at all, the type-I rate is 0.05%-0.15% against a nominal 2.5%, which reads as an
estimator that under-rejects by a factor of 17-50. **That reading is an artifact of the one
assumption certainly false for a paid panel: that readers are interchangeable.** Sweeping the
heterogeneity surface at twelve readers, type-I climbs monotonically with `sigma_reader` and hits
2.5% — nominal, across the whole coverage curve and not merely its tail — at `sigma_reader = 0.8`.
The two-way bootstrap is calibrated exactly where real reader clustering exists, which is its job.

So the estimator is neither broken nor gratuitously wide. What it is, is **sensitive to a
quantity nobody has measured**: `sigma_reader` moves the interval's width by more than a factor
of three and decides whether the stated level is honest. And the sensitivity is not one-sided —
at small panels the error reverses, which is why `readers_grid` exists as its own sweep.

**A rare event cannot be measured by counting it, so the study reads a curve instead.** At a true
level near 0.1%, 2,000 replicates produce two events, and two events distinguish nothing across a
48-point grid. The 2,000 bootstrap resamples are the entire cost of a bound and reading further
quantiles off them is free, so every replicate returns its bound at a ladder of requested alphas
and the study reports the whole coverage curve. The headline number falls out of it directly:
**`alpha*`, the alpha that would have to be requested for the bound to hold at a true 2.5%.**
`alpha* >> 0.05` is conservatism stated in the units the project spends — because requesting a
level you do not need buys width you pay for in verdicts.

**The interaction term is the crux, which is why it is swept rather than footnoted.** The
estimator resamples two margins, readers and pairs. Main effects in either margin are exactly
what it is built to absorb. A reader-by-pair interaction is visible in neither margin, and it is
physically real here — the two position-swapped orientations of one pair judged by one reader
share it, which is precisely why the estimator groups them into a single cell. If anything can
spend the conservatism measured above, it is that term.

The generative model:

    logit P(system wins | reader r, pair p) = mu + u_r + v_p + w_rp
        u_r  ~ N(0, sigma_reader^2)       taste, shared across every pair r judges
        v_p  ~ N(0, sigma_pair^2)         quality, shared across every reader who judges p
        w_rp ~ N(0, sigma_inter^2)        idiosyncratic fit, unique to one cell

`mu` is SOLVED for, never set to `logit(target)`: adding logit-normal noise pulls the marginal
toward 0.5, and at target 0.70 with heavy heterogeneity the naive value delivers a true marginal
of 0.631. A power curve built on that would be mislabelled by seven points.

Ties do not move the null under either declared policy, which is worth stating because it is not
obvious. Under HALF_WIN the estimand is E[score] = 0.5*tau + (1-tau)*p, which is 0.5 exactly when
p = 0.5; under DROP the estimand is E[score | not a tie] = p. So `--tie-rate` is a power and cost
axis, never a calibration one.

Stdlib only, parallel by `multiprocessing`, on the house pattern: nothing in `src/` imports this
and it adds no dependency to a repo whose only runtime dependency is its own contracts package.

    uv run python research/preference-power/simulate.py --mode calibration --out cal.json
    uv run python research/preference-power/simulate.py --mode power --out pow.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from random import Random

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from bound import bounds_at  # noqa: E402

#: Monte Carlo replicates per design point. Matches `persona_battery.NULL_REPLICATES`, and the
#: arithmetic it has to satisfy here is: at a true rate of 0.025 the standard error over 2,000
#: replicates is sqrt(.025*.975/2000) = 0.0035, so a measured rate separates 2.5% from 5.0% by
#: seven standard errors. It does NOT resolve 0.1% from 0.2%, which is why `alpha_star` and not
#: the type-I count is the reported headline.
REPLICATES = 2_000

#: The shipped bound's own alpha. Two-sided by declaration, so the lower bound sits at the 2.5%
#: quantile of the resampled rates and the nominal one-sided level under test is 2.5%.
ALPHA = 0.05
NOMINAL = ALPHA / 2.0

#: The requested-alpha ladder every replicate is read at. Spans the shipped 0.05 up to values no
#: one would request, because the point is to find where the curve crosses a true 2.5% and the
#: null pilot says that crossing is far from 0.05. The ladder is fixed rather than adaptive so
#: every design point is read at identical quantiles and the rows stay comparable.
ALPHAS = (0.05, 0.10, 0.20, 0.35, 0.50, 0.70, 0.90, 0.98)


def expit(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def marginal(mu: float, sigma: float, *, nodes: int = 2001) -> float:
    """E[expit(mu + z)] for z ~ N(0, sigma^2), by trapezoid over +/- 8 sigma.

    Trapezoid rather than Gauss-Hermite because the stdlib carries no quadrature, the integrand
    is smooth and bounded in [0, 1], and this runs once per design point rather than once per
    replicate. Checked against the analytic sigma = 0 case: exact to machine precision on every
    grid point the study uses.
    """
    if sigma <= 0.0:
        return expit(mu)
    lo, hi = -8.0 * sigma, 8.0 * sigma
    step = (hi - lo) / (nodes - 1)
    norm = 1.0 / (sigma * math.sqrt(2.0 * math.pi))
    total = 0.0
    weight_sum = 0.0
    for i in range(nodes):
        z = lo + i * step
        w = norm * math.exp(-0.5 * (z / sigma) ** 2)
        if i in (0, nodes - 1):
            w *= 0.5
        total += w * expit(mu + z)
        weight_sum += w
    return total / weight_sum


def pin_mu(target: float, sigma: float) -> float:
    """Solve E[expit(mu + z)] = target for mu. Monotone in mu, so bisection cannot miss."""
    if not 0.0 < target < 1.0:
        raise ValueError(f"target {target} is not a win rate")
    lo, hi = -50.0, 50.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if marginal(mid, sigma) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def assignment(n_readers: int, n_pairs: int, k: int) -> list[list[int]]:
    """Which pairs each reader judges: a cyclic incomplete design.

    Cyclic rather than random because balance is the thing being priced. Reader r takes pairs
    (r*k + i) mod P, so when R*k is a multiple of P every pair is judged by exactly R*k/P readers
    and no pair becomes a singleton cluster by accident. A random assignment would put a ragged,
    uncontrolled replication count underneath every number in the sweep, and the estimator is
    known to behave differently at small cluster sizes — that is the whole subject.
    """
    if k > n_pairs:
        raise ValueError(f"a reader cannot judge {k} of {n_pairs} distinct pairs")
    return [[(r * k + i) % n_pairs for i in range(k)] for r in range(n_readers)]


def one_replicate(args: tuple) -> tuple[tuple[float, ...] | None, int, int]:
    """Simulate one panel; return (bounds at every alpha, n_analysable, n_paid).

    Returns `None` for the bounds when the estimator refuses — fewer than two clusters in either
    dimension after ties and recognition exclusion have taken their rows. A refusal is a real
    outcome of a panel design and is counted, not swallowed: a panel that cannot be bounded spent
    its whole budget for no number at all, which a power figure alone would hide.
    """
    (
        n_readers,
        n_pairs,
        k,
        orientations,
        mu,
        sigma_reader,
        sigma_pair,
        sigma_inter,
        tie_rate,
        exclusion_rate,
        tie_policy_half,
        seed,
    ) = args
    rng = Random(seed)
    gauss = rng.gauss
    random_ = rng.random

    reader_effect = [gauss(0.0, sigma_reader) if sigma_reader else 0.0 for _ in range(n_readers)]
    pair_effect = [gauss(0.0, sigma_pair) if sigma_pair else 0.0 for _ in range(n_pairs)]
    # Recognition is a property of the excerpt more than of the reader, so its propensity is
    # drawn per pair and applied per judgment: a famous passage is recognised by many readers,
    # which removes correlated rows and can empty a whole pair cluster. Modelling it as iid
    # dropout would understate exactly the damage that matters. Beta(4p, 4(1-p)) is deliberately
    # dispersed — most pairs nearly safe, a few badly exposed — rather than every pair carrying
    # the mean rate, which is the shape a recognisable-author corpus actually has.
    if exclusion_rate > 0.0:
        concentration = 4.0
        recognisability = [
            rng.betavariate(concentration * exclusion_rate, concentration * (1.0 - exclusion_rate))
            for _ in range(n_pairs)
        ]
    else:
        recognisability = [0.0] * n_pairs

    cells: list[tuple[int, int, int, float]] = []
    paid = 0
    for r, pairs in enumerate(assignment(n_readers, n_pairs, k)):
        u = reader_effect[r]
        for p in pairs:
            linear = mu + u + pair_effect[p]
            if sigma_inter:
                linear += gauss(0.0, sigma_inter)
            prob = expit(linear)
            count = 0
            score = 0.0
            for _ in range(orientations):
                paid += 1
                if recognisability[p] and random_() < recognisability[p]:
                    continue  # paid for, then excluded from analysis (§61 pre-registration 3)
                if tie_rate and random_() < tie_rate:
                    if tie_policy_half:
                        count += 1
                        score += 0.5
                    continue  # under DROP a tie leaves the analysis set entirely
                count += 1
                if random_() < prob:
                    score += 1.0
            if count:
                cells.append((r, p, count, score))

    if not cells:
        return None, 0, paid
    live_readers = {c[0] for c in cells}
    live_pairs = {c[1] for c in cells}
    analysable = sum(c[2] for c in cells)
    if len(live_readers) < 2 or len(live_pairs) < 2:
        return None, analysable, paid
    # Re-index onto the surviving clusters: the shipped estimator counts the clusters PRESENT in
    # the analysis set, so exclusion that empties a pair shrinks the cluster count rather than
    # leaving a zero column behind.
    reader_ix = {r: i for i, r in enumerate(sorted(live_readers))}
    pair_ix = {p: i for i, p in enumerate(sorted(live_pairs))}
    packed = [(reader_ix[r], pair_ix[p], c, s) for r, p, c, s in cells]
    try:
        values = bounds_at(
            packed,
            len(live_readers),
            len(live_pairs),
            alphas=ALPHAS,
            seed=rng.getrandbits(63),
        )
    except ValueError:
        return None, analysable, paid
    return tuple(values), analysable, paid


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    rate = successes / n
    centre = (rate + z * z / (2 * n)) / (1 + z * z / n)
    half = (z / (1 + z * z / n)) * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n))
    return max(0.0, centre - half), min(1.0, centre + half)


def alpha_star(coverage: list[float]) -> float:
    """The requested alpha whose true exceedance rate is `NOMINAL`, by linear interpolation.

    Exceedance rises monotonically in the requested alpha — a larger alpha reads a higher
    quantile of the same resampled rates — so a single crossing exists whenever the ladder
    brackets it. Returns `inf` when even the widest rung on the ladder still exceeds less often
    than nominal, which is itself the finding: the estimator cannot be made to spend its level at
    any alpha a person would request.
    """
    for i, value in enumerate(coverage):
        if value >= NOMINAL:
            if i == 0:
                return ALPHAS[0]
            lo_a, hi_a = ALPHAS[i - 1], ALPHAS[i]
            lo_c, hi_c = coverage[i - 1], coverage[i]
            if hi_c == lo_c:
                return hi_a
            return lo_a + (NOMINAL - lo_c) * (hi_a - lo_a) / (hi_c - lo_c)
    return float("inf")


def run_point(pool: Pool, point: dict, replicates: int) -> dict:
    sigma = math.sqrt(
        point["sigma_reader"] ** 2 + point["sigma_pair"] ** 2 + point["sigma_inter"] ** 2
    )
    mu = pin_mu(point["true_rate"], sigma)
    jobs = [
        (
            point["n_readers"],
            point["n_pairs"],
            point["k"],
            point["orientations"],
            mu,
            point["sigma_reader"],
            point["sigma_pair"],
            point["sigma_inter"],
            point["tie_rate"],
            point["exclusion_rate"],
            point["tie_policy_half"],
            (point["seed_base"] * 1_000_003 + i * 2_654_435_761) & 0x7FFF_FFFF,
        )
        for i in range(replicates)
    ]
    started = time.perf_counter()
    results = pool.map(one_replicate, jobs, chunksize=8)
    bounded = [b for b, _, _ in results if b is not None]
    refused = len(results) - len(bounded)
    total = len(results)

    truth = point["true_rate"]
    # Coverage is denominated over ALL replicates, refusals included: a refusal is a panel that
    # produced no bound and therefore did not exceed the truth. Denominating over the bounded
    # ones would report the behaviour of the panels that happened to work.
    coverage = [sum(1 for b in bounded if b[i] > truth) / total for i in range(len(ALPHAS))]
    cleared = sum(1 for b in bounded if b[0] > 0.5)
    clear_lo, clear_hi = wilson(cleared, total)
    shipped = sorted(b[0] for b in bounded)
    median_bound = shipped[len(shipped) // 2] if shipped else float("nan")

    analysable = sum(a for _, a, _ in results) / total
    paid = sum(p for _, _, p in results) / total
    # The iid yardstick: what a binomial 97.5% lower bound would have been on the same number of
    # analysable verdicts, pretending they were independent. The ratio of the two half-widths is
    # the conservatism expressed as a width, and its square is the verdict multiplier.
    iid_half = 1.96 * math.sqrt(truth * (1.0 - truth) / analysable) if analysable else float("nan")
    observed_half = truth - median_bound
    return {
        **point,
        "mu": mu,
        "sigma_total": sigma,
        "replicates": total,
        "coverage": coverage,
        "alpha_star": alpha_star(coverage),
        "clear_rate": cleared / total,
        "clear_lo": clear_lo,
        "clear_hi": clear_hi,
        "refused": refused,
        "median_bound": median_bound,
        "width_ratio": observed_half / iid_half if iid_half else float("nan"),
        "mean_analysable": analysable,
        "mean_paid": paid,
        "seconds": time.perf_counter() - started,
    }


def base_point(shape: tuple[int, int, int, int], **over) -> dict:
    n_readers, n_pairs, k, orientations = shape
    point = {
        "n_readers": n_readers,
        "n_pairs": n_pairs,
        "k": k,
        "orientations": orientations,
        "true_rate": 0.50,
        "sigma_reader": 0.0,
        "sigma_pair": 0.0,
        "sigma_inter": 0.0,
        "tie_rate": 0.0,
        "exclusion_rate": 0.0,
        "tie_policy_half": True,
        "seed_base": 20260818,
    }
    point.update(over)
    return point


def calibration_grid(shape: tuple[int, int, int, int]) -> list[dict]:
    """Where the conservatism is spent: the null across the heterogeneity surface."""
    return [
        base_point(shape, sigma_reader=sr, sigma_pair=sp, sigma_inter=si)
        for sr in (0.0, 0.4, 0.8)
        for sp in (0.0, 0.4, 0.8, 1.2)
        for si in (0.0, 0.4, 0.8, 1.2)
    ]


def readers_grid(shape: tuple[int, int, int, int]) -> list[dict]:
    """Is calibration governed by reader heterogeneity, or by heterogeneity *per reader*?

    The calibration sweep fixed twelve readers and found the bound calibrated at
    `sigma_reader = 0.8` and conservative below it. Two different mechanisms predict that same
    row and they give opposite advice. If what matters is `sigma_reader` alone, panel size buys
    power only. If what matters is the between-reader contribution to the variance of the mean —
    which falls as `sigma_reader^2 / R` — then a larger panel is *less* calibrated at fixed
    heterogeneity, and enlarging a panel to buy power would quietly buy conservatism back.

    Verdicts per reader are held constant at `k * orientations` so that growing R grows the study
    rather than redistributing it; total cost therefore rises with R, which is the honest
    comparison for someone choosing a panel.

    Even reader counts only: with P = 60 and k = 30 each pair is judged by exactly R/2 readers, so
    every row is a balanced design and the R axis varies panel size alone. An odd R would leave
    half the pairs with one reader and half with two, which is a second uncontrolled variable
    inside the one comparison this grid exists to make.
    """
    _, n_pairs, k, orientations = shape
    return [
        base_point(
            (readers, n_pairs, k, orientations),
            sigma_reader=sr,
            sigma_pair=0.4,
            sigma_inter=0.4,
        )
        for readers in (4, 6, 8, 12, 20, 30)
        for sr in (0.0, 0.4, 0.8, 1.2)
    ]


def pairs_grid(shape: tuple[int, int, int, int]) -> list[dict]:
    """The mirror of `readers_grid`: starve the PAIR dimension and add readers anyway.

    `readers_grid` puts the heterogeneity in the reader dimension and finds type-I falling as
    readers are added. An independent probe (the design panel's P2) held the pair pool at eight,
    put the heterogeneity in the *pair* dimension, and found the opposite — type-I climbing from
    2.2% to 4.9% as readers went from five to fifty. Both cannot be a rule about readers.

    The reconciliation this grid tests: the bound is governed by whichever cluster dimension is
    **small and heterogeneous**, and adding observations to the other dimension removes the
    binomial noise that was accidentally widening the interval and masking the shortfall. If that
    is right, type-I rises as P shrinks at fixed large R, and rises further at the larger
    `sigma_pair`.

    It is the operationally dangerous case, which is why it is worth its own run: a real panel
    scales the dimension it can buy — readers — while the pair pool is capped by how many scenes
    the book has. Full crossing (`k = P`) so that shrinking P starves the cluster count rather
    than merely thinning the assignment.
    """
    readers = 30
    return [
        base_point(
            (readers, n_pairs, n_pairs, shape[3]),
            sigma_reader=0.2,
            sigma_pair=sp,
            sigma_inter=0.4,
        )
        for n_pairs in (4, 6, 8, 12, 20, 40)
        for sp in (0.4, 1.2)
    ]


def power_grid(shape: tuple[int, int, int, int]) -> list[dict]:
    """What it takes to clear the bar, at the heterogeneity the calibration run says is real."""
    points = []
    for true_rate in (0.55, 0.60, 0.65, 0.70):
        for sr, sp, si in ((0.0, 0.0, 0.0), (0.4, 0.8, 0.4), (0.8, 1.2, 0.8)):
            for readers, pairs, k in (
                (8, 40, 20),
                (12, 60, 30),
                (20, 100, 40),
                (30, 150, 50),
            ):
                points.append(
                    base_point(
                        (readers, pairs, k, shape[3]),
                        true_rate=true_rate,
                        sigma_reader=sr,
                        sigma_pair=sp,
                        sigma_inter=si,
                    )
                )
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description="Operating characteristics of the §61 bound.")
    parser.add_argument(
        "--mode", choices=("calibration", "power", "readers", "pairs"), default="calibration"
    )
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--readers", type=int, default=12)
    parser.add_argument("--pairs", type=int, default=60)
    parser.add_argument("--k", type=int, default=30)
    parser.add_argument("--orientations", type=int, default=2)
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    shape = (args.readers, args.pairs, args.k, args.orientations)
    builder = {
        "calibration": calibration_grid,
        "power": power_grid,
        "readers": readers_grid,
        "pairs": pairs_grid,
    }[args.mode]
    points = builder(shape)
    print(
        f"mode={args.mode}  nominal one-sided level {NOMINAL:.1%}  "
        f"{args.replicates} replicates/point  {len(points)} points  {args.workers} workers"
    )
    print(f"alpha ladder: {ALPHAS}")
    print()
    if args.mode in ("calibration", "readers", "pairs"):
        header = (
            f"{'R':>4} {'P':>4} {'sR':>4} {'sP':>4} {'sI':>4} {'type-I':>8} "
            f"{'alpha*':>8} {'width':>6} {'median bd':>10} {'refused':>8} {'s':>4}"
        )
    else:
        header = (
            f"{'p':>5} {'sR':>4} {'sP':>4} {'sI':>4} {'R':>4} {'P':>5} {'verdicts':>9} "
            f"{'power':>8} {'95% CI':>18} {'median bd':>10} {'s':>4}"
        )
    print(header)
    print("-" * len(header))
    rows = []
    with Pool(args.workers) as pool:
        for point in points:
            row = run_point(pool, point, args.replicates)
            rows.append(row)
            if args.mode in ("calibration", "readers", "pairs"):
                star = row["alpha_star"]
                star_text = "  >0.98" if star == float("inf") else f"{star:>8.3f}"
                print(
                    f"{row['n_readers']:>4} {row['n_pairs']:>4} "
                    f"{row['sigma_reader']:>4.1f} {row['sigma_pair']:>4.1f} "
                    f"{row['sigma_inter']:>4.1f} {row['clear_rate']:>7.3%} {star_text} "
                    f"{row['width_ratio']:>6.2f} {row['median_bound']:>10.4f} "
                    f"{row['refused']:>8} {row['seconds']:>4.0f}"
                )
            else:
                print(
                    f"{row['true_rate']:>5.2f} {row['sigma_reader']:>4.1f} "
                    f"{row['sigma_pair']:>4.1f} {row['sigma_inter']:>4.1f} "
                    f"{row['n_readers']:>4} {row['n_pairs']:>5} {row['mean_paid']:>9.0f} "
                    f"{row['clear_rate']:>7.1%} [{row['clear_lo']:>6.1%},{row['clear_hi']:>6.1%}] "
                    f"{row['median_bound']:>10.4f} {row['seconds']:>4.0f}"
                )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"alphas": list(ALPHAS), "nominal": NOMINAL, "rows": rows}, handle, indent=2)
        print(f"\nwrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
