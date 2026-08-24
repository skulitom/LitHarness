"""The feed continuation reader's seating controls and its patterned-reader attainability table.

Pure arithmetic over `feed_core.FeedSession` sequences plus seeded simulation: no I/O, no model
call, no clock. Every interval here is `bcr`'s — `cluster_interval`, `equivalence`, `Interval`
are reused, never re-derived, because two instruments that computed intervals differently would
be two definitions of "inside the band".

**Two lessons from stage-0 §94.6-§94.7 are encoded structurally rather than remembered.**

1. *Sizing is simulated over patterned session-level readers.* The BCR sized its controls from
   twelve independent coins per session; the real readers committed to one allocation pattern
   per session, the fetches inside a session were perfectly correlated, and the declared batch
   could not have met the band at any size budgeted (§94.7: the interval came out 2.8x wider
   than the table assumed). So `sessions_needed` draws each session's shares from a *pattern*
   — the `mixture` model picks one of `PATTERNS` per session, which is the correlated world
   phi4 actually presented — and never from independent per-read coins.

2. *Degeneracy is read off the slot share, never the target share.* The orientation rotation
   moves the target between slots, so a rigidly positional reader scores maximal target-share
   variance and would look maximally discriminating (§94.6's second formulation defect, caught
   by the next pilot). `fp5_non_degenerate` therefore measures the across-session standard
   deviation of each **slot**'s read share — the quantity that is constant for every fixed
   pattern and variable for a content-driven allocator — and `fp5_operating_characteristic`
   pins both halves of that property.

And one refusal is structural: while `feed_core.CONTROL_MIN_SESSIONS` is `None`,
`equivalence_control` returns verdict **"UNSIZED"** — never PASS, never FAIL. A control sized
by guesswork certifies nothing; the number is read off `sessions_needed`' table and set in a
commit that cites it.
"""

from __future__ import annotations

import random
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bcr  # noqa: E402
import feed_core  # noqa: E402

# ------------------------------------------------------------------ derived shape, not new policy

#: Centre of every equivalence band: one slot of the registered feed. The BCR centred on 0.5;
#: a four-book feed generalises the placebo to 1/4, and every control below reads it rather
#: than restating it.
CENTRE = 1.0 / feed_core.FEED_SIZE

#: Full reads one session's budget buys at the registered prices: 24 units at 3 a read.
READS_PER_SESSION = feed_core.BUDGET_UNITS // feed_core.READ_COST

# ---------------------------------------------------------------------------- the patterned readers

#: The session-level reader models the attainability table simulates. The first six are fixed
#: patterns — a reader commits to them for a whole session, which is what §94.6's pilot found
#: (`ABABAB...`, `AAAA...`, all-in-per-session) — and they ignore `bias` because a rule that
#: rigid has no free minute to tilt. `sticky` and `dirichlet` model content-driven readers,
#: whose allocation responds to the material, and those two apply `bias`.
PATTERNS: tuple[str, ...] = (
    "all_in_0",
    "all_in_1",
    "all_in_2",
    "all_in_3",
    "round_robin",
    "hold_then_switch",
    "sticky",
    "dirichlet",
)

#: The subset whose slot-share vector is constant across sessions by construction. This is the
#: half `fp5` exists to catch, and the half `fp5_operating_characteristic` asserts exactly 0.0.
FIXED_PATTERNS: tuple[str, ...] = PATTERNS[:6]

#: Stay-probability of the `sticky` Markov walk: mostly the reader keeps their book, sometimes
#: the feed wins. Seeded, so one (pattern, session, seed) triple always draws the same walk.
STAY_PROBABILITY = 0.8

#: Switch rates at which `fp5`'s diagnostic names the pattern rather than shrugs. These name;
#: they never bar — the bar is `feed_core.DEGENERATE_SD` on the slot-share sd alone.
_ROTATING_RATE = 0.75
_FIXED_RATE = 0.25


def _rng(pattern: str, session_index: int, seed: int) -> random.Random:
    """One seeded generator per (pattern, session, seed) triple, reproducible everywhere."""
    return random.Random(f"{pattern}:{session_index}:{seed}")


def _dirichlet_weights(
    rng: random.Random, *, target_slot: int, bias: float
) -> list[float]:
    """One allocation vector drawn from Dirichlet(1, 1, 1, 1), tilted toward the target.

    The raw draw is four unit-gamma variates normalised. `bias` then interpolates the target's
    weight toward certainty — `bias` 1.0 puts every read on the target, 0.0 changes nothing —
    and rescales the other three slots proportionally so the vector stays a distribution.
    """
    raw = [rng.gammavariate(1.0, 1.0) for _ in range(feed_core.FEED_SIZE)]
    total = sum(raw)
    alloc = [value / total for value in raw]
    tilted_target = alloc[target_slot] + bias * (1.0 - alloc[target_slot])
    rest = 1.0 - tilted_target
    base_rest = 1.0 - alloc[target_slot]
    if base_rest <= 0.0:
        return [1.0 if index == target_slot else 0.0 for index in range(feed_core.FEED_SIZE)]
    return [
        tilted_target if index == target_slot else value * (rest / base_rest)
        for index, value in enumerate(alloc)
    ]


def _draw_slot(rng: random.Random, weights: Sequence[float]) -> int:
    """One categorical draw over slot indices from `weights`."""
    u = rng.random()
    cumulative = 0.0
    for index, weight in enumerate(weights):
        cumulative += weight
        if u < cumulative:
            return index
    return len(weights) - 1


def simulate_share(
    pattern: str,
    session_index: int,
    seed: int,
    *,
    target_slot: int = 0,
    bias: float = 0.0,
    reads: int = READS_PER_SESSION,
) -> float:
    """One session's **target** read share under `pattern`, deterministic in its inputs.

    The registered session runs `BUDGET_UNITS // READ_COST` = 8 full reads; `reads` exists so
    a caller can pose the question at another count, and 0 or fewer answers the neutral
    1/FEED_SIZE rather than dividing by zero.

    How each pattern applies `bias` (0.0 = unbiased):

    - `all_in_k` — every read on slot k. **Ignores `bias`**, and says so: a reader that never
      opens the other books is not tiltable, that is what makes it fixed.
    - `round_robin` — cycles the feed in reveal order, phase set by `session_index`.
      **Ignores `bias`**: a strict rotator has no free minute to redistribute.
    - `hold_then_switch` — first half of the reads on one slot, second half on another, both
      chosen deterministically from `(session_index, seed)`. **Ignores `bias`** for the same
      reason as the other fixed patterns.
    - `sticky` — a Markov walk over slots with stay-probability `STAY_PROBABILITY`; at each
      step, with probability `bias`, the walk is overridden and the target is read instead
      (the walk position does not move on an overridden step).
    - `dirichlet` — the session's allocation is drawn once from Dirichlet(1, 1, 1, 1) and the
      reads are multinomial on it; `bias` tilts the drawn allocation toward the target as
      `_dirichlet_weights` documents.

    An unknown pattern is a programming error and raises, rather than silently resembling one
    of the registered readers.
    """
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern {pattern!r}; registered: {', '.join(PATTERNS)}")
    if reads < 1:
        return CENTRE
    if pattern.startswith("all_in_"):
        return 1.0 if int(pattern[-1]) == target_slot else 0.0
    if pattern == "round_robin":
        start = session_index % feed_core.FEED_SIZE
        hits = sum(
            1 for step in range(reads) if (start + step) % feed_core.FEED_SIZE == target_slot
        )
        return hits / reads
    if pattern == "hold_then_switch":
        first = (session_index + seed) % feed_core.FEED_SIZE
        second = (first + 1 + session_index % (feed_core.FEED_SIZE - 1)) % feed_core.FEED_SIZE
        half = reads // 2
        hits = (half if first == target_slot else 0) + (
            reads - half if second == target_slot else 0
        )
        return hits / reads
    rng = _rng(pattern, session_index, seed)
    if pattern == "sticky":
        current = session_index % feed_core.FEED_SIZE
        hits = 0
        for _step in range(reads):
            if bias > 0.0 and rng.random() < bias:
                hits += 1
                continue
            if current == target_slot:
                hits += 1
            if rng.random() > STAY_PROBABILITY:
                current = (current + 1) % feed_core.FEED_SIZE
        return hits / reads
    # dirichlet: one allocation per session, multinomial reads on it.
    weights = _dirichlet_weights(rng, target_slot=target_slot, bias=bias)
    hits = sum(1 for _read in range(reads) if _draw_slot(rng, weights) == target_slot)
    return hits / reads


# ------------------------------------------------------------------------------ the scorable subset


def scorable(sessions: Sequence[feed_core.FeedSession]) -> list[feed_core.FeedSession]:
    """The scorable subset: every step answered and at least one action taken."""
    return [session for session in sessions if session.scorable]


def _unscorable_count(sessions: Sequence[feed_core.FeedSession]) -> int:
    return len(sessions) - len(scorable(sessions))


# ----------------------------------------------------------------------------------- the controls


def slot_share_table(sessions: Sequence[feed_core.FeedSession]) -> dict[str, Any]:
    """Per slot letter: the per-session read shares and their mean, plus the session dossiers.

    The raw material every control below reads and the shape a result file stores: nothing
    here judges, everything here survives being looked at again.
    """
    usable = scorable(sessions)
    return {
        "sessions": len(usable),
        "unscorable": _unscorable_count(sessions),
        "slots": {
            slot: {
                "per_session": [session.read_share_of(slot) for session in usable],
                "mean": (
                    statistics.fmean(session.read_share_of(slot) for session in usable)
                    if usable
                    else None
                ),
            }
            for slot in feed_core.SLOTS
        },
        "target_read_share": [session.target_read_share for session in usable],
        "skim_rate": [session.skim_rate for session in usable],
        "abandonment_step": [session.abandonment_step for session in usable],
    }


def _name_switch_pattern(mean_switch_rate: float) -> str | None:
    """Which fixed pattern a switch rate names, or None between the named extremes."""
    if mean_switch_rate >= _ROTATING_RATE:
        return "rotating through the feed"
    if mean_switch_rate <= _FIXED_RATE:
        return "never leaves one book"
    return None


def fp5_non_degenerate(sessions: Sequence[feed_core.FeedSession]) -> dict[str, Any]:
    """The generalised P5: is any slot's read share moving across sessions?

    The statistic is the mean over the four slots of the across-session standard deviation of
    that slot's read share, and it must exceed `feed_core.DEGENERATE_SD`. On the **slot**
    share, never the target share — §94.6's second formulation defect: the rotation moves the
    target between slots, so a rigidly positional reader scores maximal target-share variance
    while its slot vector is perfectly constant.

    Beside the verdict, as diagnostics and never as bars: the mean `read_switch_rate`, and the
    fixed pattern the failure names — a switch rate near 1.0 is a reader rotating through the
    feed, near 0.0 one that never leaves a book. Fewer than two scorable sessions is
    UNREADABLE, not PASS: a degeneracy check that cannot fail is not a check.
    """
    usable = scorable(sessions)
    dropped = _unscorable_count(sessions)
    if len(usable) < 2:
        return {
            "verdict": "UNREADABLE",
            "why": f"{len(usable)} scorable session(s); degeneracy needs at least two to vary",
            "statistic": None,
            "floor": feed_core.DEGENERATE_SD,
            "unscorable": dropped,
        }
    per_slot_sd = {
        slot: statistics.pstdev(session.read_share_of(slot) for session in usable)
        for slot in feed_core.SLOTS
    }
    statistic = statistics.fmean(per_slot_sd.values())
    mean_switch_rate = statistics.fmean(session.read_switch_rate for session in usable)
    return {
        "verdict": "PASS" if statistic > feed_core.DEGENERATE_SD else "FAIL",
        "statistic": statistic,
        "floor": feed_core.DEGENERATE_SD,
        "per_slot_sd": per_slot_sd,
        "mean_read_switch_rate": mean_switch_rate,
        "named_pattern": _name_switch_pattern(mean_switch_rate),
        "unscorable": dropped,
    }


def equivalence_control(name: str, values: Sequence[float], *, centre: float) -> dict[str, Any]:
    """One equivalence check around `centre` at the registered band and alpha, via `bcr`.

    `centre` is 1/FEED_SIZE for the placebo and shams, and per-slot 1/FEED_SIZE for the
    positional reading. The interval arithmetic, the two-one-sided-test direction, and the
    imprecise/off_centre failure kinds are `bcr.equivalence`'s, unmodified — this wrapper
    contributes exactly one thing: **while `feed_core.CONTROL_MIN_SESSIONS` is None the
    verdict is "UNSIZED"**, with a note naming the attainability table as what sets it
    (§94.7 encoded structurally — a control sized by guesswork certifies nothing).
    """
    floor = feed_core.CONTROL_MIN_SESSIONS
    if floor is None:
        return {
            "control": name,
            "verdict": "UNSIZED",
            "why": (
                "feed_core.CONTROL_MIN_SESSIONS is unset; the patterned-reader attainability "
                "table (feed_controls.sessions_needed) sets it, in a commit that cites it"
            ),
            "observations": len(values),
            "band": [centre - feed_core.CONTROL_BAND, centre + feed_core.CONTROL_BAND],
            "centre": centre,
            "unscorable": 0,
        }
    result = bcr.equivalence(
        [(f"session-{index}", value) for index, value in enumerate(values)],
        band=feed_core.CONTROL_BAND,
        alpha=feed_core.CONTROL_ALPHA,
        centre=centre,
        min_sessions=floor,
        dimension="session",
        scope=name,
    )
    return {
        "control": name,
        "centre": centre,
        "unscorable": 0,
        **result,
    }


def positional_control(sessions: Sequence[feed_core.FeedSession]) -> dict[str, Any]:
    """The fp2 reading: per slot letter, is that slot's share of reads even?

    Each slot gets its own `equivalence_control` at centre 1/FEED_SIZE, plus the worst slot
    named — the one whose point estimate sits farthest from the centre — because a summary
    verdict that hid which position was favoured would be exactly the kind of number that
    cannot be argued with. Sessions must span rotations for this to mean anything at all
    (one rotation is one position wearing four), so the rotation counts are reported.
    """
    usable = scorable(sessions)
    per_slot = {
        slot: equivalence_control(
            f"p2_positional:{slot}",
            [session.read_share_of(slot) for session in usable],
            centre=CENTRE,
        )
        for slot in feed_core.SLOTS
    }
    measured = [
        (slot, result["point"]) for slot, result in per_slot.items() if "point" in result
    ]
    worst_slot = max(measured, key=lambda item: abs(item[1] - CENTRE))[0] if measured else None
    if any(result["verdict"] == "UNSIZED" for result in per_slot.values()):
        verdict = "UNSIZED"
    elif all(result["verdict"] == "PASS" for result in per_slot.values()):
        verdict = "PASS"
    elif any(result["verdict"] == "UNREADABLE" for result in per_slot.values()):
        verdict = "UNREADABLE"
    else:
        verdict = "FAIL"
    return {
        "control": "p2_positional",
        "verdict": verdict,
        "worst_slot": worst_slot,
        "slots": per_slot,
        "rotations": dict(sorted(Counter(session.rotation for session in usable).items())),
        "unscorable": _unscorable_count(sessions),
    }


#: Seed of the fp6 bootstrap. A fixed module constant rather than a parameter: a directional
#: verdict someone could re-run under fresh seeds until it flipped is not a verdict.
_FP6_SEED = 20260824


def fp6_skim_price(
    cheap: Sequence[feed_core.FeedSession], flat: Sequence[feed_core.FeedSession]
) -> dict[str, Any]:
    """Does skim usage fall when a skim costs what a read costs?

    Per-session skim rates under the registered prices (`cheap`) and under the skim priced at
    the read price (`flat`). The registered kill is **directional and nothing more**: the 90%
    percentile bootstrap interval (sessions as the unit, `bcr`'s imported resample count,
    seeded from a fixed module constant) on mean(cheap) - mean(flat) must sit strictly above
    zero. There is no effect-size bar to miss and no magnitude to argue with — a reader whose
    skim usage does not fall at all is not economising, and the skim channel is an artifact.

    Below two scorable sessions on either side the answer is UNREADABLE: a direction read off
    one pair of sessions is a coin wearing a p-value.
    """
    cheap_usable = scorable(cheap)
    flat_usable = scorable(flat)
    dropped = _unscorable_count(cheap) + _unscorable_count(flat)
    if len(cheap_usable) < 2 or len(flat_usable) < 2:
        return {
            "verdict": "UNREADABLE",
            "why": (
                f"{len(cheap_usable)} scorable cheap-side and {len(flat_usable)} scorable "
                "flat-side session(s); a direction needs at least two a side"
            ),
            "unscorable": dropped,
        }
    cheap_rates = [session.skim_rate for session in cheap_usable]
    flat_rates = [session.skim_rate for session in flat_usable]
    difference = statistics.fmean(cheap_rates) - statistics.fmean(flat_rates)
    rng = random.Random(_FP6_SEED)
    resamples = bcr._resamples()
    means: list[float] = []
    for _resample in range(resamples):
        cheap_draw = [cheap_rates[rng.randrange(len(cheap_rates))] for _ in cheap_usable]
        flat_draw = [flat_rates[rng.randrange(len(flat_rates))] for _ in flat_usable]
        means.append(statistics.fmean(cheap_draw) - statistics.fmean(flat_draw))
    means.sort()
    alpha = feed_core.CONTROL_ALPHA
    tail = max(1, int(-(-(alpha / 2.0) * len(means) // 1)))
    low, high = means[tail - 1], means[len(means) - tail]
    return {
        "verdict": "direction_holds" if low > 0.0 else "direction_fails",
        "cheap": {
            "rates": cheap_rates,
            "mean": statistics.fmean(cheap_rates),
            "unscorable": _unscorable_count(cheap),
        },
        "flat": {
            "rates": flat_rates,
            "mean": statistics.fmean(flat_rates),
            "unscorable": _unscorable_count(flat),
        },
        "difference": difference,
        "interval": [low, high],
        "alpha": alpha,
        "resamples": resamples,
        "unscorable": dropped,
    }


# ------------------------------------------------------- attainability over readers somebody is


#: Candidate batch sizes the attainability table prices. Deliberately the same ladder the BCR
#: ended up reading §94.7's correction from.
_CANDIDATE_SESSIONS: tuple[int, ...] = (16, 24, 32, 48, 64, 96)

#: Bias values that put each reader model's mean target share near the labelled level. Only
#: `sticky` and `dirichlet` respond to bias, and in the `mixture` they carry 2 of the 8
#: pattern slots, so the mixture needs a stronger tilt for the same shift: expected mixture
#: mean ≈ 0.25 + (2/8) · 0.75 · bias, dirichlet mean ≈ 0.25 + 0.75 · bias. The observed means
#: are reported beside each cell so the label can be checked against the simulation.
_BIAS_NEAR_35: dict[str, float] = {"mixture": 0.53, "dirichlet": 0.13}
_BIAS_NEAR_45: dict[str, float] = {"mixture": 1.0, "dirichlet": 0.27}

_ROLES: tuple[str, ...] = ("uniform", "near_0.35", "near_0.45")

_MODELS: tuple[str, ...] = ("mixture", "dirichlet")


def _cell_seed(seed: int, trial: int, role_index: int) -> int:
    """Injective integer cell address for (seed, trial, role), trials < 1000 per role."""
    return seed * 1_000_000 + role_index * 1_000 + trial


def _model_shares(
    model: str, seed: int, trial: int, role_index: int, bias: float
) -> list[float]:
    """One simulated batch at the largest candidate size; smaller sizes are its prefixes.

    Prefixes, deliberately: with common random numbers across candidate sizes, a difference
    in the table between two sizes is the effect of the batch size alone, not of two draws.
    """
    cell = _cell_seed(seed, trial, role_index)
    if model == "dirichlet":
        return [
            simulate_share("dirichlet", index, cell, target_slot=0, bias=bias)
            for index in range(_CANDIDATE_SESSIONS[-1])
        ]
    pattern_rng = random.Random(f"mixture-patterns:{cell}")
    shares: list[float] = []
    for index in range(_CANDIDATE_SESSIONS[-1]):
        pattern = PATTERNS[pattern_rng.randrange(len(PATTERNS))]
        shares.append(simulate_share(pattern, index, cell, target_slot=0, bias=bias))
    return shares


def sessions_needed(*, seed: int, trials: int = 200) -> dict[str, Any]:
    """How many sessions before the equivalence band is attainable — simulated, per reader.

    The table `feed_core.CONTROL_MIN_SESSIONS` must be read from before any paid run. For each
    candidate count and each reader model: the probability the equivalence interval at the
    registered band sits inside the band at true-uniform allocation (an unbiased reader
    passing), and the same probability at biases putting the mean target share near 0.35 and
    near 0.45 (a biased reader slipping through — must stay low, or the control cannot fail).

    Two reader models, and neither is independent coins:

    - `mixture` draws each session's pattern uniformly from `PATTERNS` — the session-level
      correlated world §94.7 found, where a reader commits to one allocation per session and
      the effective sample size is the session count.
    - `dirichlet` is the content-driven allocator, whose per-session noise is smaller and
      whose bands close sooner.

    Deterministic under `seed`; states its own trial count; reports the observed mean share
    beside each labelled bias so the labels are checkable rather than asserted.
    """
    band = feed_core.CONTROL_BAND
    alpha = feed_core.CONTROL_ALPHA
    models: dict[str, Any] = {}
    for model in _MODELS:
        biases = [0.0, _BIAS_NEAR_35[model], _BIAS_NEAR_45[model]]
        passes = [[0] * len(_CANDIDATE_SESSIONS) for _ in _ROLES]
        share_totals = [0.0] * len(_ROLES)
        for trial in range(trials):
            for role_index in range(len(_ROLES)):
                shares = _model_shares(model, seed, trial, role_index, biases[role_index])
                share_totals[role_index] += statistics.fmean(shares)
                for size_index, size in enumerate(_CANDIDATE_SESSIONS):
                    values = [
                        (f"session-{index}", share)
                        for index, share in enumerate(shares[:size])
                    ]
                    interval = bcr.cluster_interval(values, alpha=alpha)
                    if interval is not None and interval.inside(band, centre=CENTRE):
                        passes[role_index][size_index] += 1
        by_size: dict[str, Any] = {}
        for size_index, size in enumerate(_CANDIDATE_SESSIONS):
            by_size[str(size)] = {
                "pass_at_uniform": passes[0][size_index] / trials,
                "pass_near_0.35": passes[1][size_index] / trials,
                "pass_near_0.45": passes[2][size_index] / trials,
            }
        by_size["observed_mean_share"] = {
            "uniform": share_totals[0] / trials,
            "near_0.35": share_totals[1] / trials,
            "near_0.45": share_totals[2] / trials,
        }
        models[model] = {
            "by_sessions": by_size,
            "bias_used": dict(zip(_ROLES, biases, strict=True)),
        }
    return {
        "trials": trials,
        "candidates": list(_CANDIDATE_SESSIONS),
        "centre": CENTRE,
        "band": band,
        "alpha": alpha,
        "reads_per_session": READS_PER_SESSION,
        "patterns": list(PATTERNS),
        "models": models,
        "reading": (
            "set feed_core.CONTROL_MIN_SESSIONS from the first row whose pass_at_uniform is "
            "high and whose pass_near_0.45 stays low, per reader model; a control sized "
            "before this table is read certifies nothing"
        ),
    }


# --------------------------------------------------------- fp5's operating characteristic


def _fixed_pattern_actions(pattern: str) -> tuple[tuple[str, str], ...]:
    """One fixed pattern's action tuple, held to the same slots every session.

    The operating characteristic asks whether one behaviour's slot-share vector varies across
    sessions — so the slot choices here are part of the behaviour, fixed, not redrawn. A
    population of all-in readers each committed to a *different* slot is a mixture, and fp5
    scoring it nonzero is correct: the mixture is not one fixed pattern.
    """
    half = READS_PER_SESSION // 2
    if pattern.startswith("all_in_"):
        slot = feed_core.SLOTS[int(pattern[-1])]
        return tuple(("read", slot) for _ in range(READS_PER_SESSION))
    if pattern == "round_robin":
        return tuple(
            ("read", feed_core.SLOTS[index % feed_core.FEED_SIZE])
            for index in range(READS_PER_SESSION)
        )
    if pattern == "hold_then_switch":
        return tuple([("read", "A")] * half + [("read", "D")] * (READS_PER_SESSION - half))
    raise ValueError(f"{pattern!r} is not a fixed pattern")


def _synthetic_sessions(
    actions: tuple[tuple[str, str], ...], count: int, *, model: str = "simulation"
) -> list[feed_core.FeedSession]:
    return [
        feed_core.FeedSession(
            feed_id="simulation",
            arm="simulation",
            model=model,
            rotation=index % feed_core.FEED_SIZE,
            replicate=0,
            dose=0.0,
            actions=actions,
        )
        for index in range(count)
    ]


def fp5_operating_characteristic(*, seed: int = 94_607, trials: int = 60) -> dict[str, Any]:
    """fp5's two halves, checked the way a driver selftest calls them: cheap, deterministic.

    First half, **asserted rather than sampled**: every fixed pattern scores exactly 0.0 on
    fp5's statistic — one behaviour, held to the same slots, produces the same slot-share
    vector every session, so there is nothing across sessions for a standard deviation to
    see — and therefore FAILs against the floor. Second half, sampled under the seed: the
    dirichlet allocator clears `feed_core.DEGENERATE_SD` in at least 95% of trials, because
    a content-driven allocator's allocations move and fp5 must see that movement.
    """
    sessions_per_set = 12
    fixed: dict[str, dict[str, Any]] = {}
    for pattern in FIXED_PATTERNS:
        sessions = _synthetic_sessions(_fixed_pattern_actions(pattern), sessions_per_set)
        result = fp5_non_degenerate(sessions)
        statistic = result["statistic"]
        if statistic != 0.0:  # asserted, not sampled: a fixed pattern has no variance to see
            raise AssertionError(
                f"fixed pattern {pattern!r} scored {statistic} on fp5; must score exactly 0.0"
            )
        fixed[pattern] = {"statistic": statistic, "verdict": result["verdict"]}
    cleared = 0
    for trial in range(trials):
        sessions: list[feed_core.FeedSession] = []
        for index in range(sessions_per_set):
            generator = random.Random(f"dirichlet:{seed}:{trial}:{index}")
            weights = _dirichlet_weights(generator, target_slot=0, bias=0.0)
            actions = tuple(
                ("read", feed_core.SLOTS[_draw_slot(generator, weights)])
                for _ in range(READS_PER_SESSION)
            )
            sessions.append(
                feed_core.FeedSession(
                    feed_id="simulation",
                    arm="simulation",
                    model="dirichlet",
                    rotation=index % feed_core.FEED_SIZE,
                    replicate=trial,
                    dose=0.0,
                    actions=actions,
                )
            )
        if fp5_non_degenerate(sessions)["statistic"] > feed_core.DEGENERATE_SD:
            cleared += 1
    rate = cleared / trials
    if rate < 0.95:
        raise AssertionError(
            f"dirichlet allocator cleared DEGENERATE_SD in only {rate:.0%} of trials"
        )
    return {
        "trials": trials,
        "sessions_per_set": sessions_per_set,
        "floor": feed_core.DEGENERATE_SD,
        "fixed_patterns": fixed,
        "dirichlet_clear_rate": rate,
        "required_clear_rate": 0.95,
        "reading": (
            "fp5 is 0.0 and FAIL on every fixed pattern by construction, and fires on the "
            "content-driven allocator; a seat where neither half behaves is not a measurement"
        ),
    }
