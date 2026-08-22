"""Track FM: a market in judge-configurations, betting on which side converts. GATED.

**The gate: at least one force clears §1.2's bars on the held-out split.** Until then this module
ships a design and a dry-run and buys nothing — the dry-run drives the whole mechanism through
constructed forecasters whose behaviour is known in advance, so the arithmetic has executed
before the first real bet, which is `axiom_battery`'s discipline applied to a market.

**Why a market rather than an average.** Forces are not commensurable: F1 returns a window index,
F2 a slope, F3 a slope over a different unit, and averaging them means inventing weights. A
market makes each configuration state a **probability** on the one question every force is
actually answering — *which side of this pair converts?* — and then pays them by a proper scoring
rule on pairs they have never seen. A configuration that is confidently wrong goes bankrupt. No
weights are chosen; they are the surviving bankrolls.

**Nothing human is ever solicited.** Settlement is instant and already downloaded: `conversion`
sits in the corpus sidecar, computed from behaviour nobody in this project asked anyone for.

**The survivor is a candidate, not a judge.** It is `FORECAST`-class at `STORY` grain (§95's
promotion, exactly as §86 pre-registered it), which licenses nothing, refuses nothing and selects
nothing. Before it could ever be *seated* it faces §6.2's battery: a forecast analog of §86.7's
axioms, and §86's T3 exploitation budget instrumented from the first optimization step — because
a selector trained against scraped behaviour is precisely what T3 exists to bound, and
instrumenting that afterwards measures a horse that has already left.

**E4/E5 are admitted as competitors and only as competitors** (operator §7.6: YES). §8's
anti-scope forbids pairwise preference elicitation everywhere else in the programme; the
exception is recorded in `plan/force-program.md` §6.3 so a later session finds a decision rather
than an inconsistency. They ask a model a question. They are here to be beaten by things that
do not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from force_harness import (  # noqa: E402
    RESULTS,
    ForcePair,
    attainability_table,
    load_pairs,
    provenance,
)

#: Every configuration starts here, and bankruptcy is the exit. Units are arbitrary; only ratios
#: are read, which is why the starting stake is a round number rather than a calibrated one.
STARTING_BANKROLL = 100.0

#: The stake fraction per bet. Kelly on a proper scoring rule would compound the confident and
#: bury everyone else in two dozen bets; a flat fraction keeps the ranking a statement about
#: forecast quality rather than about leverage.
STAKE_FRACTION = 0.05

#: A bankroll at or below this is bankrupt and the configuration stops betting. It is recorded
#: with the bet number that killed it, never dropped from the table — a competitor that died is
#: evidence, and a leaderboard listing only survivors is a leaderboard that has hidden its nulls.
BANKRUPT_AT = 1.0

#: Probabilities are clipped before scoring. An unclipped log score is unbounded, so one
#: confident error decides the whole market and the ranking becomes a statement about a single
#: pair. Declared before any bet, per §89's rulebook.
CLIP = 0.02

#: The held-out split. Story- and author-disjoint by construction (§89.2), and split by a stable
#: hash of `pair_id` so the same pairs are held out on every run and in every process.
HOLDOUT_SHARE = 0.5

PRE_REGISTRATION: dict[str, Any] = {
    "track": "FM the market",
    "status": "GATED — design and dry-run only until a force clears §1.2's bars",
    "question_every_competitor_answers": "P(the high-conversion side is side A) for a pair it "
                                         "has never seen",
    "scoring_rule": "log score (primary, proper); Brier printed beside it",
    "clip": CLIP,
    "bankroll": {
        "start": STARTING_BANKROLL,
        "stake_fraction": STAKE_FRACTION,
        "bankrupt_at": BANKRUPT_AT,
        "rule": "bankroll *= exp(stake_fraction * (log_score - log(0.5))) — a configuration "
                "beating a coin grows and one below it shrinks, at a rate no leverage choice "
                "can inflate",
    },
    "presentation": "the two sides are swapped on a deterministic, label-blind coin derived "
                    "from pair_id, so the settled outcome varies and a competitor is paid for "
                    "being right rather than for being loud. Corrected 2026-08-20: the first "
                    "implementation settled every bet as 'yes', which made the ranking a "
                    "function of stated confidence alone.",
    "promotion_rule": "the surviving ensemble is the inverse-log-score-weighted average of "
                      "every configuration that is still solvent AND beat a coin over the full "
                      "held-out sequence, and it is a FORECAST-class CANDIDATE — never a judge, "
                      "never a licence. Solvency alone admitted a coin and a constant 0.95.",
    "settlement": "instant, already downloaded; conversion sits in the corpus sidecar and "
                  "nothing human is solicited",
    "holdout": "story- and author-disjoint, split by a stable hash of pair_id",
    "e4_e5": "admitted as asking baselines to be beaten (operator §7.6: YES); they are never a "
             "valence channel and never a judge",
    "battery_before_seat": "a forecast analog of §86.7 — calibration, resolution, refinement, "
                           "format invariance, dose monotonicity — plus §86's T3 exploitation "
                           "budget instrumented from the first optimization step",
    "declared_before": "the first bet",
}


# ------------------------------------------------------------------------------ mechanism


@dataclass
class Competitor:
    """One judge-configuration in the market."""

    name: str
    #: pair -> P(high side converts). A force wraps its own statistic into this shape; nothing
    #: else about a force is visible to the market, which is what makes them comparable.
    forecast: Callable[[ForcePair], float | None]
    bankroll: float = STARTING_BANKROLL
    bets: int = 0
    abstentions: int = 0
    log_scores: list[float] = field(default_factory=list)
    brier: list[float] = field(default_factory=list)
    #: The stated probability and the realised outcome for every settled bet, kept so the
    #: calibration curve can plot an empirical rate that varies instead of the constant 1.0 it
    #: was forced to print while every truth was 'yes'.
    forecasts: list[float] = field(default_factory=list)
    outcomes: list[int] = field(default_factory=list)
    bankrupt_at_bet: int | None = None
    #: Declared per competitor and printed: does it ask a model a question? The programme's whole
    #: claim is about the ones that do not, so the column has to exist.
    asks: bool = False

    @property
    def solvent(self) -> bool:
        return self.bankroll > BANKRUPT_AT and self.bankrupt_at_bet is None


def clip(probability: float) -> float:
    return min(max(probability, CLIP), 1.0 - CLIP)


def presented(pair: ForcePair) -> tuple[ForcePair, int]:
    """The pair as a competitor sees it, plus the truth about what it was shown.

    **The outcome has to vary or the market ranks confidence.** `ForcePair` always carries the
    high-conversion text in `high`, so settling every bet as "yes" made the mean log score the
    log geometric mean of the stated probability and nothing else: a perfectly calibrated force
    at 0.52 scored -0.6923 while `lambda _: 0.95` scored -0.0513, and the accuracy a real force
    would have needed to out-earn a text-blind constant was **0.9920**. The committed dry run
    duly handed the `oracle` a bankroll of 10836.81 and 0.8804 of the promoted ensemble. The
    overconfidence diagnostic could not fire either: with truth pinned at 1, every forecaster
    whose mass sits above 0.51 beats the coin by construction.

    So the sides are swapped on a coin derived from `pair_id` — deterministic, so the same pairs
    are presented the same way in every process and forever, and label-blind, so the swap cannot
    encode the answer. `outcome` is 1 when the side shown as `high` really is the high-conversion
    one. This is what the pre-registration always said the question was: *P(the high-conversion
    side is side A)*. The code simply never asked it.
    """
    stamp = int(hashlib.sha256(f"present|{pair.pair_id}".encode()).hexdigest()[:8], 16)
    if stamp % 2 == 0:
        return pair, 1
    return ForcePair(
        pair_id=pair.pair_id, stratum=pair.stratum,
        high=pair.low, low=pair.high,
        high_meta=pair.low_meta, low_meta=pair.high_meta,
    ), 0


def settle(competitor: Competitor, probability: float | None, outcome: int) -> None:
    """One pair, settled against the outcome the presentation actually produced.

    `probability` is P(the side shown as `high` is the high-conversion one); `outcome` is whether
    it was. A competitor with no signal sits at 0.5 and neither grows nor shrinks; one that is
    merely confident is now paid log(1-p) half the time and goes bankrupt for it.
    """
    if probability is None:
        competitor.abstentions += 1
        return
    p = clip(probability)
    realised = p if outcome else 1.0 - p
    competitor.bets += 1
    competitor.log_scores.append(math.log(realised))
    competitor.brier.append((outcome - p) ** 2)
    competitor.forecasts.append(p)
    competitor.outcomes.append(outcome)
    competitor.bankroll *= math.exp(STAKE_FRACTION * (math.log(realised) - math.log(0.5)))
    if competitor.bankroll <= BANKRUPT_AT and competitor.bankrupt_at_bet is None:
        competitor.bankrupt_at_bet = competitor.bets


def holdout(pairs: Sequence[ForcePair], share: float = HOLDOUT_SHARE) -> list[ForcePair]:
    """A stable, label-blind split. The same pairs are held out in every process, forever."""
    kept = []
    for pair in pairs:
        stamp = int(hashlib.sha256(pair.pair_id.encode("utf-8")).hexdigest()[:8], 16)
        if (stamp % 1000) / 1000.0 < share:
            kept.append(pair)
    return kept


def run_market(competitors: Sequence[Competitor], pairs: Sequence[ForcePair]) -> dict[str, Any]:
    """Every competitor bets on every held-out pair, in a fixed order, and is paid immediately."""
    for pair in sorted(pairs, key=lambda p: p.pair_id):
        shown, outcome = presented(pair)
        for competitor in competitors:
            if not competitor.solvent:
                continue
            settle(competitor, competitor.forecast(shown), outcome)
    table: list[dict[str, Any]] = []
    for competitor in competitors:
        n = len(competitor.log_scores)
        table.append({
            "name": competitor.name,
            "asks_a_model_a_question": competitor.asks,
            "bets": competitor.bets,
            "abstentions": competitor.abstentions,
            "bankroll": round(competitor.bankroll, 4),
            "mean_log_score": round(statistics.fmean(competitor.log_scores), 4) if n else None,
            "mean_brier": round(statistics.fmean(competitor.brier), 4) if n else None,
            "beats_coin": (statistics.fmean(competitor.log_scores) > math.log(0.5)) if n else None,
            "bankrupt_at_bet": competitor.bankrupt_at_bet,
            "solvent": competitor.solvent,
        })
    table.sort(key=lambda row: (-(row["bankroll"] or 0), row["name"]))
    survivors = [row for row in table if row["solvent"]]
    return {
        "pairs": len(pairs),
        "leaderboard": table,
        "survivors": [row["name"] for row in survivors],
        "promotion": promotion(competitors),
        "no_survivors_is_a_result": not survivors,
    }


def promotion(competitors: Sequence[Competitor]) -> dict[str, Any]:
    """The surviving ensemble, and the sentence that says what it is not."""
    solvent = [c for c in competitors if c.solvent and c.log_scores]
    # **Solvency is not skill, and the ensemble takes only what beat a coin.** A flat stake means
    # a competitor scoring a little below log(0.5) shrinks slowly and is still standing at the
    # end of a 146-bet sequence; weighting by `1/|mean log score|` then handed it a share. The
    # committed dry run promoted `coin` at 0.0628 and a constant 0.95 at 0.0357 — a
    # FORECAST-class candidate part-built from a coin and from something that loses to one.
    beat_coin = [c for c in solvent if statistics.fmean(c.log_scores) > math.log(0.5)]
    if not beat_coin:
        return {
            "status": "NO_SURVIVOR",
            "why": "no configuration beat a coin over the held-out sequence; the market's answer "
                   "is that none of them forecasts this label, which is a result and not a "
                   "failed run",
            "solvent_but_below_coin": sorted(c.name for c in solvent),
        }
    weights = {c.name: 1.0 / abs(statistics.fmean(c.log_scores)) for c in beat_coin}
    total = sum(weights.values())
    return {
        "status": "FORECAST_CLASS_CANDIDATE",
        "members": {name: round(w / total, 4) for name, w in weights.items()},
        "what_it_is_not": "not a judge, not a licence, not a member of veto_for, not accepted by "
                          "plan_search's judge path. §95's promotion of FORECAST is exactly "
                          "§86's pre-registered text and not one word further.",
        "before_any_seat": PRE_REGISTRATION["battery_before_seat"],
    }


# ------------------------------------------------------- the battery a survivor faces first


def calibration_curve(competitor: Competitor, bins: int = 5) -> list[dict[str, Any]]:
    """A reliability diagram whose empirical rate is measured rather than asserted.

    The previous version printed `empirical_rate: 1.0` in every bin with a note explaining that
    the number was true by construction — an honest note under a diagram that could not say
    anything. With the presentation coin the outcome varies, so a bin's empirical rate is the
    share of its bets that came in, and a forecaster whose mass sits at 0.9 while only half its
    bets land is now visibly overconfident instead of merely suspected of it.
    """
    if not competitor.forecasts:
        return []
    edges = [i / bins for i in range(bins + 1)]
    out = []
    for low, high in pairwise(edges):
        members = [
            (p, o) for p, o in zip(competitor.forecasts, competitor.outcomes, strict=True)
            if low <= p < high or (high == 1.0 and p == 1.0)
        ]
        if not members:
            continue
        out.append({
            "bin": [round(low, 2), round(high, 2)],
            "n": len(members),
            "mean_forecast": round(statistics.fmean(p for p, _ in members), 4),
            "empirical_rate": round(statistics.fmean(float(o) for _, o in members), 4),
        })
    return out


def t3_exploitation_budget() -> dict[str, Any]:
    """§86's T3, instrumented from step zero rather than measured after the fact.

    Not run here — there is no optimization step yet, because the gate is closed. What this
    function ships is the *instrument*: the quantities to record from the first time anything is
    selected against a force, so that Goodhart drift is visible while it is happening.
    """
    return {
        "status": "NOT_RUN",
        "why": "no optimization step exists; the FM gate is closed",
        "recorded_from_step_zero": [
            "the force's score on the selected candidate and on the rejected ones",
            "the force's score on a held-out set never used for selection, same step",
            "the gap between the two, which is the exploitation signal",
            "the a priori counters (§88) on the same candidates, which no optimizer may see",
            "divergence between the two pinned families, which rises first under Goodhart",
        ],
        "kill": "selection stops when the held-out score falls while the selected score rises "
                "for two consecutive steps",
    }


# -------------------------------------------------------------------------------- dry run


def constructed_competitors() -> list[Competitor]:
    """Forecasters whose behaviour is known before the run. The null through the real plumbing.

    Six, each testing one property of the mechanism: a coin must neither grow nor shrink, an
    oracle that reads the presentation must survive, an anti-oracle must go bankrupt, an
    abstainer must never bet, a prose-blind popularity rule must do well in `aligned` and badly
    in `crossed` — which is §79's whole design and the reason the market cannot be run on one
    stratum — and **a merely confident constant must now lose**, which is the property the
    market did not have.

    `oracle` and `anti_oracle` read `high_meta["conversion"]`, i.e. they are told the answer.
    That is what an oracle is for: it proves the settlement pays a correct forecast and punishes
    a wrong one. Under the old constant truth they did not need to read anything, and a constant
    0.95 was indistinguishable from knowing — which is precisely the defect.
    """
    def popularity(pair: ForcePair) -> float | None:
        hi = pair.high_meta.get("followers")
        lo = pair.low_meta.get("followers")
        if not hi or not lo:
            return None
        return 0.75 if hi > lo else 0.25

    def truth(pair: ForcePair) -> float | None:
        hi = pair.high_meta.get("conversion")
        lo = pair.low_meta.get("conversion")
        if hi is None or lo is None:
            return None
        return 0.95 if hi > lo else 0.05

    return [
        Competitor("coin", lambda _: 0.5),
        Competitor("oracle", truth),
        Competitor("anti_oracle", lambda p: None if (v := truth(p)) is None else 1.0 - v),
        Competitor("abstainer", lambda _: None),
        Competitor("prose_blind_followers", popularity),
        Competitor("confident_constant", lambda _: 0.95),
    ]


def dry_run(pairs: Sequence[ForcePair]) -> dict[str, Any]:
    competitors = constructed_competitors()
    held = holdout(pairs)
    result = run_market(competitors, held)
    by_name = {c.name: c for c in competitors}
    checks = {
        "coin_is_flat": abs(by_name["coin"].bankroll - STARTING_BANKROLL) < 1e-9,
        "oracle_grows": by_name["oracle"].bankroll > STARTING_BANKROLL,
        "anti_oracle_bankrupt": by_name["anti_oracle"].bankrupt_at_bet is not None,
        "abstainer_never_bet": by_name["abstainer"].bets == 0,
        # The check the market was missing, and the one that would have caught B8 on the day the
        # dry run was committed: confidence without information must lose to a coin. It used to
        # earn a bankroll of 10836.81 and 0.8804 of the promoted ensemble.
        "confidence_alone_loses": (
            by_name["confident_constant"].bankroll < by_name["coin"].bankroll
        ),
        "oracle_beats_confidence": (
            by_name["oracle"].bankroll > by_name["confident_constant"].bankroll
        ),
        "popularity_split_by_stratum": True,
    }
    per_stratum = {}
    for stratum in ("aligned", "crossed"):
        members = [p for p in held if p.stratum == stratum]
        # By name, not by position. `constructed_competitors()[-1]` silently became a different
        # competitor the moment one was appended to the list, and the per-stratum block went on
        # reporting its numbers under the popularity rule's name.
        fresh = Competitor("prose_blind_followers", {
            c.name: c.forecast for c in constructed_competitors()
        }["prose_blind_followers"])
        run_market([fresh], members)
        per_stratum[stratum] = {
            "bets": fresh.bets,
            "mean_log_score": round(statistics.fmean(fresh.log_scores), 4)
            if fresh.log_scores else None,
            "bankroll": round(fresh.bankroll, 4),
        }
    aligned = per_stratum["aligned"]["mean_log_score"]
    crossed = per_stratum["crossed"]["mean_log_score"]
    if aligned is not None and crossed is not None:
        checks["popularity_split_by_stratum"] = aligned > crossed
    return {
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "market": result,
        "prose_blind_by_stratum": per_stratum,
        "calibration_example": calibration_curve(by_name["oracle"]),
        "reading": (
            "the mechanism does what it was declared to do on forecasters whose behaviour was "
            "known in advance, and the prose-blind popularity rule scores in `aligned` and loses "
            "in `crossed` — which is §79's design working, and the reason a market run on one "
            "stratum would promote a popularity proxy"
            if all(checks.values())
            else "the dry run failed a check; the mechanism is wrong and no real bet may be "
                 "placed against it"
        ),
    }


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    coin = Competitor("coin", lambda _: 0.5)
    for i in range(50):
        settle(coin, 0.5, i % 2)
    check(abs(coin.bankroll - STARTING_BANKROLL) < 1e-9, f"coin drifted to {coin.bankroll}")

    # A forecaster is good or bad by whether it *tracks the outcome*, not by how loudly it speaks.
    good = Competitor("good", lambda _: 0.9)
    bad = Competitor("bad", lambda _: 0.1)
    for i in range(200):
        outcome = i % 2
        settle(good, 0.9 if outcome else 0.1, outcome)
        settle(bad, 0.1 if outcome else 0.9, outcome)
    check(good.bankroll > STARTING_BANKROLL, "a good forecaster must grow")
    check(bad.bankrupt_at_bet is not None, "a bad forecaster must go bankrupt")

    # **The B8 check, at the level of the scoring rule itself.** A constant 0.95 against a truth
    # that varies must lose to a coin; under the old constant truth it beat every honest entry
    # and took 0.8804 of the promoted ensemble.
    loud = Competitor("loud", lambda _: 0.95)
    flat = Competitor("flat", lambda _: 0.5)
    for i in range(200):
        settle(loud, 0.95, i % 2)
        settle(flat, 0.5, i % 2)
    check(loud.bankroll < flat.bankroll, "confidence without information must lose to a coin")
    check(
        statistics.fmean(loud.log_scores) < math.log(0.5),
        f"a confident constant must score below the coin, got {statistics.fmean(loud.log_scores)}",
    )
    # `settle` records the killing bet; `run_market` is what stops calling it. Testing the stop
    # through a raw settle loop would test the loop, not the market — the first version of this
    # check did exactly that and failed for it.
    doomed = Competitor("doomed", lambda _: 0.05)
    market_pairs = [
        ForcePair(pair_id=f"m{i:03d}", stratum="aligned", high="a", low="b") for i in range(300)
    ]
    run_market([doomed], market_pairs)
    check(doomed.bankrupt_at_bet == doomed.bets, "the market must stop betting a bankrupt entry")
    check(doomed.bets < len(market_pairs), "a bankrupt entry must not bet on every pair")

    wild = Competitor("wild", lambda _: 0.0)
    settle(wild, 0.0, 1)
    check(math.isfinite(wild.log_scores[0]), "an unclipped log score would be -inf")
    check(abs(math.exp(wild.log_scores[0]) - CLIP) < 1e-12, "clipping must be at the declared CLIP")

    abst = Competitor("abstain", lambda _: None)
    settle(abst, None, 1)
    check(abst.bets == 0 and abst.abstentions == 1, "abstention is not a bet")
    check(promotion([abst])["status"] == "NO_SURVIVOR", "no scored survivor must say so")

    # The holdout is stable and label-blind.
    fake = [ForcePair(pair_id=f"p{i}", stratum="aligned", high="a", low="b") for i in range(400)]
    first = {p.pair_id for p in holdout(fake)}
    second = {p.pair_id for p in holdout(fake)}
    check(first == second, "the holdout must be stable across calls")
    check(0.4 < len(first) / len(fake) < 0.6, f"holdout share {len(first) / len(fake)}")

    for message in failures:
        print(f"FAIL {message}")
    print(f"force_market selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default=str(RESULTS / "force-fm-dryrun.json"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    pairs = load_pairs()
    held = holdout(pairs)
    report = provenance(
        track="FM",
        pre_registration_track=PRE_REGISTRATION,
        gate={
            "status": "CLOSED",
            "condition": "at least one force clears §1.2's bars on the held-out split",
            "consequence": "design and dry-run only; no configuration is funded and E4/E5 are "
                           "not bought",
        },
        holdout_sizes={
            "aligned": sum(1 for p in held if p.stratum == "aligned"),
            "crossed": sum(1 for p in held if p.stratum == "crossed"),
        },
        attainability=attainability_table({
            "holdout_aligned": sum(1 for p in held if p.stratum == "aligned"),
            "holdout_crossed": sum(1 for p in held if p.stratum == "crossed"),
        }),
        dry_run=dry_run(pairs) if args.dry_run else {"status": "NOT_RUN"},
        t3_exploitation_budget=t3_exploitation_budget(),
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.dry_run:
        print(json.dumps(report["dry_run"]["checks"], indent=2))
        print(json.dumps(report["dry_run"]["prose_blind_by_stratum"], indent=2))
        print("\n" + report["dry_run"]["reading"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
