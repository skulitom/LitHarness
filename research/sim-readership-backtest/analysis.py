"""PREREG §§5-9's arithmetic over parsed stage-2 answers: accuracy, the primary interval, the
control quantities, and the one place the registered decision rule is assembled.

This module is deliberately dumb. Every function here is pure arithmetic over `Vote` records
or outcome vectors — no I/O, no clock, no model call, no corpus access, no pyarrow anywhere.
`arms.py` produces the votes; this module says what they add up to; `backtest.py` feeds them.
Nothing here solicits or reports a quality judgement: the only vocabulary is behavioural
(continue A / continue B / neither), per the closed scope axiom.

Seed policy, registered: the pair bootstrap seeds `Random` from sha256 over the joined outcome
bits, so a re-run over the same outcomes reproduces the same bound bit for bit and nothing
except the outcome vector re-rolls it. The retired clustered estimator documented in
`research/preference-power/FINDINGS.md` §1 inherited the same discipline from
`win_rate_lower_bound`'s payload digest; this module keeps it for its own primary. The
label-shuffle null derives each draw's seed from the
caller's seed material plus the draw index, so a shuffle run replays exactly too.

Boundaries, refused by name rather than papered over: fewer than ten outcomes raises instead of
producing an interval — a bound computed from a handful of pairs is §85's zero-width defect
waiting, not a number. The VOID comparisons themselves live in `verdicts` alone; every other
function reports descriptive quantities and judges none of them, because a control whose
threshold is smeared across three helpers is a threshold nobody can audit."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from random import Random
from typing import Any

#: Registered alpha (PREREG §9): 2,000-resample percentile bootstrap, one candidate, no division.
ALPHA = 0.05

#: Registered resample count of the pair-bootstrap interval (PREREG §9).
BOOTSTRAP_RESAMPLES = 2000

#: Below this many decided pairs a bootstrap lower bound is refused, not reported.
MIN_OUTCOMES = 10

#: C3's void line: the shuffle clear-share may reach chance (expected ~alpha/2), but if it
#: exceeds three times that expectation the analysis path leaks the label and everything is void.
SHUFFLE_CLEAR_LIMIT = 3 * ALPHA / 2

#: The AMENDED minimum decided votes for one sham to set the floor (PREREG's "Post-hoc
#: amendment (2026-08-31)", part 1). It is not the registered rule: the registration set no
#: minimum, so `sham_floor`'s parameter defaults to 0 and the registered floor still computes
#: bit for bit. A caller that wants the amended floor passes this constant and says so.
#:
#: The arithmetic, and it is the only reason for the number — never which verdict it produces.
#: The per-sham statistic is d = |k/n - 1/2| over n decided votes, so its attainable set is
#: {j/(2n) : j = n mod 2, 0 <= j <= n}: lattice spacing 1/n, maximum 0.5 at unanimity.
#:   * n = 2 attains {0, 0.5} and nothing between. That statistic reports whether the panel
#:     split, not by how much — resolution, not deviation, which is the defect measured.
#:   * Bare non-degeneracy (some value strictly inside (0, 0.5) must exist) needs only n >= 3.
#:   * Under the sham's own null — two windows of ONE book, so the true continue-share is 0.5 —
#:     the maximum is attained by chance with probability 2 * 2**-n = 2**(1-n). Requiring that
#:     to sit at or under the programme's registered ALPHA: 2**(1-n) <= 0.05 <=> n - 1 >=
#:     log2(20) = 4.3219 <=> n >= 5.3219, i.e. **n >= 6** (n = 5 gives 0.0625 > 0.05; n = 6
#:     gives 0.03125). This is the binding criterion and the constant below.
#:   * The strictest available criterion was measured and refused: lattice spacing no coarser
#:     than PREREG §7's registered +0.05 margin needs 1/n <= 0.05, i.e. n >= 20 — the whole
#:     per-sham vote budget (10 personas x 2 orders) with not one "neither". The pilot measured
#:     2-14 decided of 20, so that criterion empties the control at every attainable size, and
#:     a control that cannot fire is the §120.2 defect the sham arm exists to avoid.
#: What the guard does NOT do: repair the max-not-pooled estimator's own noise. Under the null
#: E|d| is 0.156 at n = 6 and 0.113 at n = 12, and the floor is a max over twelve shams; the
#: amendment states that consequence in numbers rather than leaving it implied.
SHAM_MIN_DECIDED = 6


@dataclass(frozen=True, slots=True)
class Vote:
    """One parsed stage-2 answer.

    `choice` is the schema-constrained behavioural action ("A" | "B" | "neither"); "neither"
    means the persona would abandon both books and is an undecided observation, never scored.
    `high_was` records which slot held the higher-conversion member of the pair *this order*,
    so scoring survives the both-orders rotation. `reason` is the at-most-one reason code from
    the closed list; it travels with the vote but nothing here reads it.
    """

    pair_id: str
    arm: str
    persona_id: str
    order: int
    choice: str  # "A" | "B" | "neither"
    reason: str
    high_was: str  # "A" or "B"


# ------------------------------------------------------------------------------- the score


def correct(vote: Vote) -> bool | None:
    """True when the choice named the higher-outcome slot, False for the lower, None for
    "neither" — undecided, counted elsewhere, never scored."""
    if vote.choice == "neither":
        return None
    return vote.choice == vote.high_was


# ------------------------------------------------------------------------ PREREG §6 aggregate


def aggregate_by_pair(votes: Sequence[Vote], persona_ids: Collection[str]) -> dict[str, Any]:
    """The registered aggregate prediction per pair, restricted to the given personas.

    Per pair: the unweighted mean over the given personas and both orders of decided votes for
    each side (a_share/b_share over decided votes); the predicted side is the majority, and a
    pair with a tied or empty decided vote is undecided — counted, reported, never broken by a
    coin. "Neither" is excluded from the side counts but kept in every pair's tally and in the
    per-persona neither-rates.

    The restriction is load-bearing (PREREG §6): only the reward split decides qualification,
    so a holdout persona's votes must not move these numbers — which is why the neither-rate
    table is keyed by the given ids and nobody else.
    """
    allowed = set(persona_ids)
    relevant = [v for v in votes if v.persona_id in allowed]

    tally: dict[str, dict[str, int]] = {}
    for v in relevant:
        counts = tally.setdefault(v.pair_id, {"a": 0, "b": 0, "neither": 0})
        if v.choice == "A":
            counts["a"] += 1
        elif v.choice == "B":
            counts["b"] += 1
        else:
            counts["neither"] += 1

    pairs: dict[str, dict[str, Any]] = {}
    n_decided_pairs = 0
    n_undecided_pairs = 0
    for pair_id, counts in tally.items():
        decided = counts["a"] + counts["b"]
        if counts["a"] > counts["b"]:
            predicted: str | None = "A"
        elif counts["b"] > counts["a"]:
            predicted = "B"
        else:
            predicted = None
        if predicted is None:
            n_undecided_pairs += 1
        else:
            n_decided_pairs += 1
        pairs[pair_id] = {
            "predicted": predicted,
            "decided": predicted is not None,
            "a_votes": counts["a"],
            "b_votes": counts["b"],
            "a_share": counts["a"] / decided if decided else None,
            "b_share": counts["b"] / decided if decided else None,
            "n_decided": decided,
            "neither": counts["neither"],
        }

    neither_rates: dict[str, float | None] = {}
    for persona_id in sorted(allowed):
        own = [v for v in relevant if v.persona_id == persona_id]
        neither_rates[persona_id] = (
            sum(v.choice == "neither" for v in own) / len(own) if own else None
        )

    return {
        "pairs": pairs,
        "n_pairs": len(pairs),
        "n_decided_pairs": n_decided_pairs,
        "n_undecided_pairs": n_undecided_pairs,
        "neither_rate_by_persona": neither_rates,
    }


# --------------------------------------------------------------- the primary interval (§9)


def _seed_from_bits(outcomes: Sequence[int]) -> int:
    """The integer seed content-derived from the outcome vector itself.

    sha256 over the joined bits, first 16 hex characters as a 64-bit seed — the same shape
    the retired clustered estimator used for its payload digest. The seed depends on the sequence of
    outcomes and on nothing else: no clock, no counter, no caller identity. A re-run of the
    same outcomes is the same bound; anything else re-rolls it deliberately.
    """
    material = ",".join("1" if o else "0" for o in outcomes)
    return int(sha256(material.encode()).hexdigest()[:16], 16)


def _short_vector_error(n: int) -> ValueError:
    return ValueError(
        f"{n} outcome(s) is below the registered minimum of {MIN_OUTCOMES}: a bootstrap bound "
        "from fewer pairs is the zero-width defect waiting (stage-0 §85), so it is refused "
        "rather than reported"
    )


def pair_bootstrap_lower_bound(
    outcomes: Sequence[int], *, alpha: float = ALPHA, resamples: int = BOOTSTRAP_RESAMPLES
) -> float:
    """The PRIMARY interval's lower end: a pair-resampled percentile bootstrap of accuracy.

    Each resample draws `len(outcomes)` pairs with replacement under the content-derived seed
    and keeps the mean; the reported number is the alpha/2 percentile of those means (the floor
    rank, so alpha=0.05 over 2,000 resamples takes the 51st smallest). Deterministic: same
    outcomes in, same bound out, forever.

    Fewer than ten outcomes raises with a named message — see `_short_vector_error`.
    """
    n = len(outcomes)
    if n < MIN_OUTCOMES:
        raise _short_vector_error(n)
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must lie strictly between 0 and 1, got {alpha!r}")
    rng = Random(_seed_from_bits(outcomes))
    values = [int(o) for o in outcomes]
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    rank = min(int(resamples * alpha / 2), resamples - 1)
    return means[rank]


# ------------------------------------------------------------------------- control quantities


def positional_rate(votes: Sequence[Vote]) -> dict[str, Any]:
    """Panel-level first-position rate over decided votes: the share naming slot "A".

    The positional VOID comparison against the largest true-pair effect belongs to `verdicts`;
    this only measures. Undecided votes are excluded from the rate everywhere; a panel with no
    decided votes reports rate None rather than dividing by zero.
    """
    decided = [v for v in votes if v.choice in ("A", "B")]
    buckets: dict[int, list[bool]] = {}
    for v in decided:
        buckets.setdefault(v.order, []).append(v.choice == "A")
    by_order = {
        order: {"rate": sum(picks) / len(picks), "n": len(picks)}
        for order, picks in sorted(buckets.items())
    }
    first_position = sum(1 for v in decided if v.choice == "A")
    return {
        "rate": first_position / len(decided) if decided else None,
        "n": len(decided),
        "by_order": by_order,
    }


def sham_floor(
    votes_by_sham: Mapping[str, Sequence[Vote]], *, min_decided: int = 0
) -> dict[str, Any]:
    """Per sham pair |continue-share - 0.5| over decided votes; the floor is the LARGEST
    per-sham deviation, never pooled (the K2 form).

    Pooling would let twelve quiet shams dilute one loud one; the floor therefore reads each
    sham alone and takes the max. A "neither" is undecided here too. A sham with no decided
    votes has no defined deviation (None) and cannot set the floor; if no sham has any, the
    floor is 0.0 — nothing observed deviated.

    `min_decided` is the amendment's seam and **defaults to the registered rule, which set no
    minimum**: at 0 this function is the registration, byte for byte, and the pilot's committed
    floor recomputes from its own votes. A caller passing `SHAM_MIN_DECIDED` gets the amended
    floor, where a sham below the minimum keeps its measured deviation in `per_sham` — nothing
    is hidden — but carries `counts_toward_floor: False` and cannot raise the max. The reason
    is `SHAM_MIN_DECIDED`'s arithmetic and nothing else.

    `n_qualifying` rides out with the floor because a floor of 0.0 has two very different
    meanings — twelve shams that all sat at chance, or no sham allowed to speak — and a caller
    that cannot tell them apart will read an unmeasured control as a passed one. `verdicts`
    reads exactly this field to refuse that reading.
    """
    per_sham: dict[str, dict[str, Any]] = {}
    floor = 0.0
    n_qualifying = 0
    for sham_id, votes in votes_by_sham.items():
        decided = [v for v in votes if v.choice in ("A", "B")]
        share = sum(v.choice == "A" for v in decided) / len(decided) if decided else None
        deviation = abs(share - 0.5) if share is not None else None
        counts = deviation is not None and len(decided) >= min_decided
        per_sham[sham_id] = {
            "continue_share": share,
            "deviation": deviation,
            "n_decided": len(decided),
            "counts_toward_floor": counts,
        }
        if counts:
            n_qualifying += 1
            if deviation is not None and deviation > floor:
                floor = deviation
    return {
        "floor": floor,
        "min_decided": min_decided,
        "n_qualifying": n_qualifying,
        "per_sham": per_sham,
    }


# ------------------------------------------------------------------------- the C3 label shuffle


def label_shuffle(
    outcomes: Sequence[int], *, seed_material: str, draws: int = 200
) -> dict[str, Any]:
    """The C3 null: flip each outcome with p=0.5 per draw, report how often the primary bound
    still clears 0.5.

    Each draw's seed derives deterministically from `seed_material` and the draw index, so a
    shuffle run replays exactly. Expected clear-share is ~alpha/2; a share above
    `SHUFFLE_CLEAR_LIMIT` means the analysis leaks the label — but the void mapping lives in
    `verdicts`, not here. Outcomes must be 0/1; anything else is refused before any draw.
    """
    n = len(outcomes)
    if n < MIN_OUTCOMES:
        raise _short_vector_error(n)
    if any(o not in (0, 1) for o in outcomes):
        raise ValueError(f"outcomes must be 0/1 accuracies, got {sorted(set(outcomes))}")
    clears = 0
    for d in range(draws):
        rng = Random(int(sha256(f"{seed_material}|{d}".encode()).hexdigest()[:16], 16))
        flipped = [o ^ 1 if rng.random() < 0.5 else o for o in outcomes]
        if pair_bootstrap_lower_bound(flipped) > 0.5:
            clears += 1
    return {
        "draws": draws,
        "clears": clears,
        "clear_share": clears / draws if draws > 0 else 0.0,
    }


# ------------------------------------------------------------------------- §120 health signature


def health_signature(
    votes: Sequence[Vote],
    damage_pair_ids: Collection[str],
    sham_pair_ids: Collection[str],
) -> dict[str, Any]:
    """§120's signature, descriptive only: per-persona accuracy on damage pairs (expect
    convergence — a population that agrees on gross damage can see) and per-persona deviation
    on shams (expect scatter — a population that agrees on everything is a diff-spotter).

    Both tables are reported and neither is judged: no verdict field exists here, by design.
    """
    damage_ids = set(damage_pair_ids)
    sham_ids = set(sham_pair_ids)

    hits: dict[str, list[bool]] = {}
    sham_picks: dict[str, list[bool]] = {}
    for v in votes:
        if v.pair_id in damage_ids:
            if (scored := correct(v)) is not None:
                hits.setdefault(v.persona_id, []).append(scored)
        elif v.pair_id in sham_ids and v.choice in ("A", "B"):
            sham_picks.setdefault(v.persona_id, []).append(v.choice == "A")

    damage = {
        persona_id: {"accuracy": sum(scores) / len(scores), "n_decided": len(scores)}
        for persona_id, scores in sorted(hits.items())
    }
    sham = {
        persona_id: {
            "deviation": abs(sum(picks) / len(picks) - 0.5),
            "n_decided": len(picks),
        }
        for persona_id, picks in sorted(sham_picks.items())
    }
    return {"damage": damage, "sham": sham}


# ------------------------------------------------------------------------- §9 decision rule


def verdicts(
    primary_outcomes: Sequence[int],
    *,
    largest_true_effect: float,
    positional: Mapping[str, Any],
    sham: Mapping[str, Any],
    damage_outcomes: Sequence[int],
    shuffle: Mapping[str, Any],
    n_target: int = 200,
) -> dict[str, Any]:
    """The registered decision rule (PREREG §9), assembled once, with named outcomes.

    Precedence, documented here because it is the rule: `insufficient_n` fires before any VOID
    (an arm below target has no confirmatory look to void); every VOID fires before
    qualification (a voided arm cannot qualify on a strong point estimate). Within the VOIDs
    the order is positional, sham, shuffle, damage — the record names whichever fired first.

      "insufficient_n"   len(primary_outcomes) < n_target
      "void_positional"  positional deviation |rate - 0.5| >= largest_true_effect
      "void_sham_unmeasured"  a minimum was applied and NO sham qualified to set the floor
      "void_sham"        sham floor >= largest_true_effect
      "void_shuffle"     shuffle clear-share > 3 * (alpha / 2)  — analysis leaks the label
      "damage_failed"    damage bootstrap lower bound <= 0.5
      "qualified"        primary lower bound > 0.5 AND none of the above fired
      "not_qualified"    otherwise

    `void_sham_unmeasured` exists only on the amended path and cannot fire on the registered
    one: it is reachable only when the caller passed a `min_decided` above 0 (the registration
    set none) and every sham fell under it, leaving a floor of 0.0 that means "nothing was
    allowed to speak" rather than "nothing deviated". A control that did not measure cannot
    certify, so it voids rather than passing quietly.

    The returned record carries every input number beside the verdict, because a verdict that
    cannot be audited from its own record is not a verdict. With fewer than ten primary
    outcomes the primary bound is reported as None (the bootstrap refuses) and the verdict is
    insufficient_n at any sane target. The damage bound is always computed and therefore
    inherits the ten-outcome refusal.
    """
    primary_lb = (
        pair_bootstrap_lower_bound(primary_outcomes)
        if len(primary_outcomes) >= MIN_OUTCOMES
        else None
    )
    damage_lb = pair_bootstrap_lower_bound(damage_outcomes)
    positional_rate_value = positional.get("rate")
    positional_deviation = (
        abs(positional_rate_value - 0.5) if positional_rate_value is not None else None
    )
    sham_floor_value: float = sham["floor"]
    sham_min_decided = int(sham.get("min_decided", 0))
    sham_n_qualifying = sham.get("n_qualifying")
    sham_unmeasured = sham_min_decided > 0 and sham_n_qualifying == 0
    clear_share: float = shuffle["clear_share"]

    fired: list[str] = []
    if len(primary_outcomes) < n_target:
        fired.append("insufficient_n")
    elif positional_deviation is not None and positional_deviation >= largest_true_effect:
        fired.append("void_positional")
    elif sham_unmeasured:
        fired.append("void_sham_unmeasured")
    elif sham_floor_value >= largest_true_effect:
        fired.append("void_sham")
    elif clear_share > SHUFFLE_CLEAR_LIMIT:
        fired.append("void_shuffle")
    elif damage_lb <= 0.5:
        fired.append("damage_failed")

    if fired:
        verdict: str = fired[0]
    elif primary_lb is not None and primary_lb > 0.5:
        verdict = "qualified"
    else:
        verdict = "not_qualified"

    return {
        "verdict": verdict,
        "fired": fired,
        "n_primary": len(primary_outcomes),
        "n_target": n_target,
        "primary_lower_bound": primary_lb,
        "largest_true_effect": largest_true_effect,
        "positional_deviation": positional_deviation,
        "sham_floor": sham_floor_value,
        "sham_min_decided": sham_min_decided,
        "sham_n_qualifying": sham_n_qualifying,
        "shuffle_clear_share": clear_share,
        "damage_lower_bound": damage_lb,
    }
