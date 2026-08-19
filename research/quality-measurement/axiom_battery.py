"""Tier 0 of the unanchored-judge programme: the axioms a judge satisfies before it costs anything.

Every arm in this repository so far has asked whether the panel can see a *defect*. This module
asks something prior and cheaper: whether the instrument obeys the rules any preference relation
has to obey before the word "preference" applies to it at all. The axioms are **disqualifiers**.
Passing them licenses nothing whatever. Failing any one of them ends a candidate before it reaches
the external-label benchmark (§79), the cross-lineage tier, or a single paid reader.

**This tier has teeth because the week's two kills were both axiom failures.** §79.1 killed the
default panel on 368 comparisons at chose-A 0.64 — a position axiom, not a taste question. §70's
absolute instrument died on a positivity floor — a range axiom. Neither needed a human, a label, or
a benchmark. What follows is the general form of that observation, run before the money.

**And the first run is expected to disqualify the incumbent, which is stated here so that it
cannot later be reported as a surprise.** §78 already measured this panel preferring blank lines at
0.0417 with clean bias, so A1 is predicted to fail; roughly half of the ~25 per-arm bias estimates
the repo owns are outside the band, so A6 is at risk on any arm whose pairs are near-twins. A tier
whose likely first result is "the default panel is not a coherent preference relation" is worth $25
precisely because that sentence currently has no measurement behind it.

    A0  indifference       two byte-identical texts. The panel must decline to choose.
    A1  format invariance  the same text under both paragraph-separator conventions, which is
                           §78.1's silent downgrade elicited directly rather than inferred.
    A2  dose monotonicity  a nested damage ladder. Preference for the damaged side must not
                           rise as damage rises, and must fall somewhere.
    A3  transitivity       the same ladder read as a tournament. Cycles are incoherence.
    A4  paraphrase         the same pairs under a semantically identical rephrasing of the
        stability          question. A verdict that is a property of the wording is not a verdict.
    A5  within-item        resamples of every cell. Between-pair variance must exceed within-cell
        consistency        variance — §70's ICC gate in its pairwise form.
    A6  position           per-arm chose-A in 0.40-0.60, computed on every arm above at no extra
                           cost, because §79.1 established that bias is a property of the *pair*
                           and may never be inherited across material.

**Three of these have never been elicited in this project and one of them is embarrassing.**
`Elicitor.variant_win_rate` says in its own docstring that "the original compared against itself is
0.5 by construction and never elicited" — an assumption that has been load-bearing since §70 and
has never been checked. A0 checks it. A1 elicits §78.1's separator downgrade directly, which until
now was visible only as the gap between a confounded arm and its matched twin (§81's 0.1111 against
0.3889); a direct measurement prices the confound instead of bounding it. A4 is new, and it does
double duty: the within-lineage agreement it measures is exactly the **floor** the cross-lineage
tier needs, because two lineages that agree no better than one lineage agrees with its own
rephrasing are one judge in costumes.

**What is deliberately NOT re-bought.** `rewhitespace` is not an arm. §78 and §81 both record why
it cannot be this design's floor — it perturbs layout without destroying it, its number is on the
ledger twice, and both readings are void on bias. A1 replaces it with the edit that actually
happened to seven arms, which is a different and more useful measurement. The external label (§79)
is not here either: an axiom battery that graded agreement with an outcome would be a benchmark,
and this tier exists to be cheaper than one.

**The ladder is nested by construction, and that is the difference between this arm and every dose
claim in the ledger.** `ablate.paragraph_shuffle` draws a fresh sample of paragraphs at each
strength, so its rungs are not subsets of one another and "more damaged" is an assumption about the
transform rather than a fact about the texts. `_nested_ladder` rotates a *prefix* of one fixed
permutation, so every position displaced at a low dose is displaced at every higher one, and the
certificate written into the result file records the displaced count, the word-multiset identity
and the layout identity of every rung. If the certificate is not monotone the scene is dropped
before the first call — a deterministic failure that costs nothing.

**The battery is jointly non-trivial and `--selftest` proves it rather than asserting it.** Ten
synthetic oracles — the perfect judge, the coin, the position answerer, the constant tie, the damage
seeker, the length preferrer, a deliberately cyclic judge, a wording-sensitive judge, a noisy one,
and a judge that manufactures a choice on pairs it cannot separate — run through the whole
arithmetic offline, before a call is ever made. The assertions are that the perfect oracle clears
every axiom, that **every other oracle is disqualified by at least one named axiom**, and that
A0 through A4 each have an oracle they are the *sole* cause of death for, which is what makes those
five arms non-redundant rather than decorative. A5 and A6 have no sole-cause oracle and the reason
is recorded in the selftest output rather than hidden: an instrument noisy enough to fail an
aggregate reliability floor also blurs the ladder A2 reads, and a slot preference big enough to
leave the band also shows as a non-tie on the identity arm. A battery some degenerate strategy
passes licenses nothing, and this is the one property of it that can be checked for free.

**A dry run is a draw from the null and the null is expected to be DISQUALIFIED.** `--dry-run`
answers from a hash of the request key, uniformly over the three choices, so it is the coin oracle
wearing the real plumbing. If a dry run ever reads CLEARED, the arithmetic is broken and not the
judge.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import statistics
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import paragraphs as paragraphs_of  # noqa: E402
from corpus_io import generated_scenes  # noqa: E402
from elicit import (  # noqa: E402
    PANEL_MODEL,
    Comparison,
    Elicitor,
    digest,
    positional_bias,
)
from personas import PAIR_QUESTIONS, PANEL  # noqa: E402

# --------------------------------------------------------------------------- pre-registration

#: The nested damage ladder, as fractions of paragraphs displaced. Rung 0 is the layout-normalised
#: original; A0 elicits the identity pair on the raw text separately.
LADDER_DOSES: tuple[float, ...] = (0.0, 0.25, 0.50, 1.0)

#: The paraphrase arm's second wording, registered in `personas.PAIR_QUESTIONS`. Checked at import
#: rather than at the first call: `pair_turn` raises on an unregistered question, and discovering
#: that after the ladder has been paid for would waste the run.
PARAPHRASE_QUESTION = "preference_paraphrase"
if PARAPHRASE_QUESTION not in PAIR_QUESTIONS:  # pragma: no cover - import-time guard
    raise ImportError(
        f"{PARAPHRASE_QUESTION!r} is not registered in personas.PAIR_QUESTIONS; A4 cannot run"
    )

#: Bars, fixed before the first elicitation. None of them moves afterwards. Where a bar is a rate
#: the reading is on the **interval**, never the point estimate — §81's arm cleared a point
#: threshold by 0.011 with an interval spanning 0.5, and the correct rule was declared after the
#: fact, which is the mistake this line exists to avoid.
TIE_FLOOR = 0.50
BIAS_BAND = (0.40, 0.60)
CYCLE_NULL_QUANTILE = 0.05
MONOTONE_NULL_QUANTILE = 0.95
PARAPHRASE_MARGIN = 0.10
DETERMINED_FLOOR = 0.50
ICC_AGGREGATE_FLOOR = 0.50

#: Minimum decided comparisons before a positional-bias band may be *read*. Added mid-run on
#: simulation evidence with the elicited verdicts unread — see `PRE_REGISTRATION_CORRECTED` and
#: §86.6. Below this count the band fails a correct judge for having behaved correctly: a judge
#: that ties 79% of the time on an identity pair (the rate §85 measured on layout-only shams)
#: leaves about 10 decided comparisons pooled across six scenes, and at that count an *unbiased*
#: judge violates 0.40-0.60 by sampling alone 35% of the time. 30 is where the standard error of
#: a rate (<= 0.091) falls under the band's half-width.
BIAS_MIN_DECIDED = 30
NULL_DRAWS = 4_000

#: **Declared after the first elicitation began and before any elicited verdict was read**, on
#: the evidence of a simulation rather than of the run: the battery as registered disqualifies a
#: genuinely good *stochastic* judge 83-100% of the time, because three of its seven axioms read a
#: positional band off a handful of decided comparisons. `--operating-characteristic` is that
#: measurement and it runs offline for nothing. Both readings are computed and reported for every
#: run; neither is selected. §81's rule one instrument over: the rule as registered is reported,
#: the defect in the rule is recorded beside it, and nothing is retro-passed.
PRE_REGISTRATION_CORRECTED: dict[str, str] = {
    "provenance": (
        "written while the first paid run was in flight, from `--operating-characteristic`, with "
        "no elicited verdict inspected. It changes no request text, so every comparison already "
        "bought replays unchanged and the correction costs nothing in quota"
    ),
    "bias_floor": (
        "a positional band is read only on arms carrying at least BIAS_MIN_DECIDED decided "
        "comparisons. Below that the arm reports bias_readable false and cannot fail on bias. The "
        "identity and format arms will usually sit below the floor for a *correct* judge, and "
        "that is the finding rather than a gap: a judge that properly declines to choose between "
        "identical texts cannot have its slot preference estimated on them"
    ),
    "unchanged": (
        "every other bar, including the 0.40-0.60 band itself, the tie floor, the monotonicity "
        "rule, the cycle null and the aggregate-reliability floor. The correction is about how "
        "many comparisons a band needs before it may be read, not about where the band sits"
    ),
    "known_residual": (
        "A3's cycle null and A4's paraphrase floor still treat scenes as independent, and the "
        "operating characteristic shows A3 degrading from 0.16 to 0.57 as scene heterogeneity "
        "rises. Reported and not repaired here, because a clustered null needs a heterogeneity "
        "parameter that would be chosen rather than measured"
    ),
}

PRE_REGISTRATION: dict[str, str] = {
    "status": (
        "declared before the first elicitation. Six axioms, each a disqualifier; a candidate "
        "failing any one is out of the programme and no other tier is bought for it"
    ),
    "A0_indifference": (
        "two byte-identical copies of the same scene. The panel must answer `neither` on at least "
        "0.50 of non-refused comparisons, and among the decided remainder chose-A must sit inside "
        "0.40-0.60. FAIL on either. A judge that picks a side between identical texts has "
        "reported on position, and every preference it states elsewhere inherits that. This pair "
        "has been assumed to be 0.5 by construction since §70 and has never been elicited"
    ),
    "A1_format_invariance": (
        "the same scene against itself with only the paragraph separator changed, which is the "
        "edit `_join` performs on every transform routing through `paragraphs` (§78.1). Same bars "
        "as A0. **The axiom is already refuted at a stronger dose and the prediction is registered "
        "here rather than discovered afterwards**: §78 measured a full flatten (newlines 858->90, "
        "blank lines 420->45) at a win rate of 0.0417 on Haiku and 0.0000 on Opus with textbook "
        "positional bias 0.5000, so this instrument is not format-invariant and the default panel "
        "is PREDICTED TO FAIL A1. What this arm buys is the magnitude at the *mild* dose — the "
        "separator downgrade that silently rides on seven registered ablations — which is "
        "currently known only as the 0.2778 gap between §81's matched arm (0.3889) and its "
        "formatting-confounded twin (0.1111), and that twin is void on bias at 0.6111. A "
        "prediction that can be wrong is the point: if the mild dose ties, the confound riding on "
        "those seven arms is smaller than the ledger currently has to assume"
    ),
    "A2_dose_monotonicity": (
        "a nested ladder at doses (0.0, 0.25, 0.50, 1.0) of paragraphs displaced, every rung "
        "sharing the base's word multiset and layout. A scene is ORDERED when its three win rates "
        "against the base are non-increasing in dose AND the top rung's rate is strictly below "
        "0.5 — monotonicity alone is satisfied by a judge that ties everything, so the second "
        "clause is what makes the arm non-vacuous. That clause is a floor the instrument already "
        "clears: §70 measured 0.906 detection on this material, so it admits nothing new. The "
        "null is simulated at the actual n with a coin judge answering the same number of "
        "comparisons per pair, and the bar is that null's 95th percentile — a hand-derived 1/6 "
        "would ignore the tie structure the instrument actually produces"
    ),
    "A3_transitivity": (
        "the same ladder read as a tournament over four texts, per (scene, persona), each edge "
        "the majority verdict of both orientations. The statistic is 3-cycles per tournament over "
        "the four triangles. A random tournament carries 1.0 cycles in expectation; the bar is "
        "the 5th percentile of the null simulated at the actual number of tournaments, not the "
        "expectation. If fewer than 0.50 of triangles are determined the arm is UNREADABLE rather "
        "than passed: a judge that ties everything has not demonstrated coherence"
    ),
    "A4_paraphrase_stability": (
        "the ladder's base-vs-top pair re-asked under a semantically identical rephrasing that "
        "preserves four invariants declared here — the tie option at equal prominence, the "
        "keep-reading act, the reason-code request, and plain register with no rubric. Agreement "
        "across wordings must not fall more than 0.10 below agreement across resamples of the "
        "SAME wording. The floor is measured in the same pass, because an instrument that "
        "disagrees with itself cannot be asked to agree with a rephrasing"
    ),
    "A5_within_item_consistency": (
        "ICC(1) over **every pair in the battery except the paraphrase arm**, replicates being "
        "(persona, sample) cells. The pair set has to include the identity and format arms and "
        "not only the ladder: a judge that is right about every rung answers all ladder pairs "
        "identically, so between-pair variance computed inside the ladder alone is zero for a "
        "*perfect* judge and the statistic would kill the thing it is meant to certify. The bar "
        "is on the **aggregate** the arms actually report, not on a single comparison: "
        "Spearman-Brown at the battery's replicate width, lower bound above 0.50, with ICC(1) "
        "reported beside it. Gating the single-comparison figure would disqualify an instrument "
        "that is noisy per call and perfectly usable at panel width, which is a bar about the "
        "wrong quantity. A constant judge leaves both undefined and FAILS rather than passing on "
        "a null — §70's positivity floor in its pairwise form. Bootstrap draws that resample only "
        "constant pairs are undefined too; their share is reported rather than silently dropped"
    ),
    "A6_position": (
        "chose-A within 0.40-0.60 per arm, reported for every arm at no extra cost. Never pooled "
        "across arms and never inherited from another experiment: §79.1 established that "
        "positional bias is a property of the pair, at 0.356 on 368 comparisons"
    ),
    "reading": (
        "PASS licenses nothing. It says the candidate is coherent enough to be worth paying to "
        "test against a label. FAIL ends the candidate. The failure is the more informative "
        "outcome because it is the cheaper one"
    ),
    "no_bar_moves": (
        "if an axiom fails narrowly the failure is recorded as a failure. §81's lesson: the rule "
        "as registered is reported, the defect in the rule is written down beside it, and nothing "
        "is retro-passed"
    ),
    "dry_run_expectation": (
        "a dry run answers uniformly over (A, B, neither) from a request hash. It is the coin "
        "oracle in the real plumbing and it must read DISQUALIFIED. A dry run reading CLEARED is "
        "a broken statistic, not a good judge"
    ),
}


# --------------------------------------------------------------------------- fixtures

def layout_normal(text: str) -> str:
    """The text as `ablate._join(ablate.paragraphs(...))` renders it: §78.1's downgrade, isolated.

    Seven arms in §78.1's audit lost the blank line this way without anybody choosing it, and the
    only evidence about what that costs is indirect — §78's 0.0417 and §81's 0.1111, both void on
    bias. This function is that edit and nothing else, so A1 can price it.
    """
    return "\n".join(paragraphs_of(text))


def _nested_ladder(text: str, doses: tuple[float, ...]) -> list[dict[str, Any]] | None:
    """Rungs sharing one word multiset and one layout, with damage nested across doses.

    Rung k rotates the first `m_k` positions of a single fixed permutation, so every position
    displaced at a low dose is displaced at every higher one — the nesting `paragraph_shuffle`
    does not have, because it re-samples which paragraphs move at every strength. Returns None
    when the scene cannot carry a strictly increasing ladder (too few paragraphs), which drops the
    scene before it costs a call.
    """
    blocks = paragraphs_of(text)
    if len(blocks) < len(doses) + 2:
        return None
    order = list(range(len(blocks)))
    random.Random(int(digest(["axiom-ladder", text])[:8], 16)).shuffle(order)

    rungs: list[dict[str, Any]] = []
    seen_counts: list[int] = []
    for dose in doses:
        count = 0 if dose <= 0 else min(len(blocks), max(2, round(dose * len(blocks))))
        picked = sorted(order[:count])
        out = list(blocks)
        for index, position in enumerate(picked):
            out[position] = blocks[picked[(index + 1) % len(picked)]] if picked else out[position]
        rungs.append({
            "dose": dose,
            "displaced": count,
            "text": "\n".join(out),
            "blocks": len(blocks),
        })
        seen_counts.append(count)

    base = rungs[0]
    for rung in rungs:
        rung["words_match_base"] = sorted(rung["text"].split()) == sorted(base["text"].split())
        rung["blocks_match_base"] = (
            len(paragraphs_of(rung["text"])) == len(paragraphs_of(base["text"])))
    if seen_counts != sorted(set(seen_counts)) or len(set(seen_counts)) != len(seen_counts):
        return None
    if not all(rung["words_match_base"] and rung["blocks_match_base"] for rung in rungs):
        return None
    if any(rungs[index]["text"] == base["text"] for index in range(1, len(rungs))):
        return None
    return rungs


@dataclass(frozen=True, slots=True)
class Pair:
    """One elicitable comparison. `left` is passed as the original, `right` as the variant, so
    `Comparison.chose_variant` reads as "the panel preferred `right`"."""

    pair_id: str
    arm: str
    scene: str
    left: str
    right: str
    left_dose: float
    right_dose: float
    question: str = "preference"
    samples: int = 1


def build_pairs(scenes: list[tuple[str, str]], *, samples: int,
                doses: tuple[float, ...] = LADDER_DOSES) -> tuple[list[Pair], list[dict[str, Any]]]:
    """Every pair the battery elicits, with the ladder certificate for the record.

    Ordered so the cheap disqualifiers come first: a candidate that picks a side between two
    identical texts is out, and the ladder should not be paid for after that.
    """
    pairs: list[Pair] = []
    certificate: list[dict[str, Any]] = []
    for scene_id, text in scenes:
        rungs = _nested_ladder(text, doses)
        if rungs is None:
            certificate.append({"scene": scene_id, "usable": False,
                                "why": "no strictly increasing nested ladder on this scene"})
            continue
        normal = layout_normal(text)
        certificate.append({
            "scene": scene_id, "usable": True, "layout_changed": normal != text,
            "rungs": [{k: v for k, v in rung.items() if k != "text"} for rung in rungs],
        })
        pairs.append(Pair(f"{scene_id}|A0", "A0_indifference", scene_id, text, text, 0.0, 0.0))
        if normal != text:
            pairs.append(Pair(f"{scene_id}|A1", "A1_format_invariance", scene_id,
                              text, normal, 0.0, 0.0))
        for low, high in itertools.combinations(range(len(rungs)), 2):
            resampled = samples if low == 0 and high > 0 else 1
            pairs.append(Pair(
                f"{scene_id}|L{low}{high}", "A2_A3_ladder", scene_id,
                rungs[low]["text"], rungs[high]["text"],
                rungs[low]["dose"], rungs[high]["dose"], samples=resampled,
            ))
        top = len(rungs) - 1
        pairs.append(Pair(
            f"{scene_id}|P0{top}", "A4_paraphrase", scene_id,
            rungs[0]["text"], rungs[top]["text"], rungs[0]["dose"], rungs[top]["dose"],
            question=PARAPHRASE_QUESTION,
        ))
    return pairs, certificate


# --------------------------------------------------------------------------- statistics

def _scored(comparisons: list[Comparison], model: str | None = None) -> list[Comparison]:
    return [c for c in comparisons
            if not c.refused and c.choice is not None and (model is None or c.model == model)]


def tie_rate(comparisons: list[Comparison]) -> float:
    scored = _scored(comparisons)
    if not scored:
        return float("nan")
    return sum(1 for c in scored if c.choice == "neither") / len(scored)


def right_win_rate(comparisons: list[Comparison]) -> float:
    """P(the panel preferred `right`), ties at half. NaN on an empty set rather than 0.5, because
    "no data" and "indifference" are different facts and §70 conflated them once already."""
    scored = _scored(comparisons)
    if not scored:
        return float("nan")
    return sum(0.5 if c.choice == "neither" else float(c.chose_variant)
               for c in scored) / len(scored)


def _edge(comparisons: list[Comparison]) -> int | None:
    """Which side a cell prefers: +1 right, -1 left, None undetermined."""
    rate = right_win_rate(comparisons)
    if rate != rate or abs(rate - 0.5) < 1e-9:
        return None
    return 1 if rate > 0.5 else -1


def cycles_in(tournament: dict[tuple[int, int], int | None], nodes: int) -> tuple[int, int]:
    """3-cycles and determined triangles in a tournament over `nodes` rungs."""
    cyclic = determined = 0
    for triple in itertools.combinations(range(nodes), 3):
        edges = [tournament.get((low, high)) for low, high in itertools.combinations(triple, 2)]
        if any(edge is None for edge in edges):
            continue
        determined += 1
        # Edges are (a<b), (a<c), (b<c) with +1 meaning "the higher-indexed rung wins".
        ab, ac, bc = edges
        wins = Counter()
        wins[triple[1] if ab == 1 else triple[0]] += 1
        wins[triple[2] if ac == 1 else triple[0]] += 1
        wins[triple[2] if bc == 1 else triple[1]] += 1
        if set(wins.values()) == {1}:
            cyclic += 1
    return cyclic, determined


def icc_one(cells: dict[str, list[float]]) -> float:
    """ICC(1) over groups with replicate scores. NaN when total variance is zero.

    A constant instrument leaves every variance statistic undefined, which §70 met as a positivity
    floor and reported as undefined rather than as a passing zero. Same choice here.
    """
    groups = [values for values in cells.values() if len(values) >= 2]
    if len(groups) < 2:
        return float("nan")
    sizes = [len(values) for values in groups]
    flat = [value for values in groups for value in values]
    grand = statistics.fmean(flat)
    k = statistics.fmean(sizes)
    between = sum(len(values) * (statistics.fmean(values) - grand) ** 2
                  for values in groups) / (len(groups) - 1)
    within_df = sum(sizes) - len(groups)
    if within_df <= 0:
        return float("nan")
    within = sum((value - statistics.fmean(values)) ** 2
                 for values in groups for value in values) / within_df
    if between + (k - 1) * within == 0:
        return float("nan")
    return (between - within) / (between + (k - 1) * within)


def spearman_brown(icc: float, replicates: float) -> float:
    """Reliability of a mean of `replicates` ratings, given the single-rating reliability.

    The arms report aggregates, so the aggregate is the quantity a reliability bar belongs on. A
    judge at ICC(1) = 0.1 read over 12 cells carries ICC(12) = 0.57, which is a usable instrument
    and would be disqualified by a bar set on the single call.
    """
    if icc != icc or replicates <= 0 or 1 + (replicates - 1) * icc == 0:
        return float("nan")
    return replicates * icc / (1 + (replicates - 1) * icc)


def bootstrap_icc(cells: dict[str, list[float]], *, draws: int = 2_000,
                  seed: str = "") -> dict[str, float]:
    """Percentile bounds over a resample of *pairs*, with the undefined draws counted.

    A draw that happens to pick only pairs the judge answered identically has zero between-pair
    variance and no ICC. Dropping those silently would narrow the interval by exactly the amount
    the data does not support, so their share is returned and reported.
    """
    keys = sorted(cells)
    if len(keys) < 2:
        return {"low": float("nan"), "high": float("nan"), "undefined_share": 1.0}
    rng = random.Random(int(digest(["icc", seed, keys])[:8], 16))
    width = statistics.fmean(len(values) for values in cells.values())
    values: list[float] = []
    aggregate: list[float] = []
    undefined = 0
    for _ in range(draws):
        picked = [keys[rng.randrange(len(keys))] for _ in keys]
        estimate = icc_one({f"{key}#{index}": cells[key] for index, key in enumerate(picked)})
        if estimate == estimate:
            values.append(estimate)
            aggregate.append(spearman_brown(estimate, width))
        else:
            undefined += 1
    if not values:
        return {"low": float("nan"), "high": float("nan"), "aggregate_low": float("nan"),
                "replicates": width, "undefined_share": 1.0}
    values.sort()
    aggregate.sort()
    return {
        "low": values[int(CYCLE_NULL_QUANTILE * len(values))],
        "high": values[min(len(values) - 1, int(0.95 * len(values)))],
        "aggregate_low": aggregate[int(CYCLE_NULL_QUANTILE * len(aggregate))],
        "replicates": round(width, 2),
        "undefined_share": round(undefined / draws, 4),
    }


def _coin_rates(rng: random.Random, draws: int) -> float:
    return sum(rng.choice((0.0, 0.5, 1.0)) for _ in range(draws)) / draws


def monotone_null(scenes: int, per_pair: int, *, draws: int = NULL_DRAWS,
                  seed: str = "") -> float:
    """The 95th percentile of a coin judge's ORDERED-scene count, simulated at the actual n.

    Not a derived 1/6: the instrument produces ties, ties make exact equalities common, and the
    registered rule requires a strict end-to-end decrease. Both facts move the null, so it is
    simulated with the same number of comparisons per pair the run actually buys.
    """
    rng = random.Random(int(digest(["monotone-null", seed, scenes, per_pair])[:8], 16))
    counts = []
    for _ in range(draws):
        ordered = 0
        for _ in range(scenes):
            rates = [_coin_rates(rng, per_pair) for _ in range(3)]
            if rates[0] >= rates[1] >= rates[2] and rates[2] < 0.5:
                ordered += 1
        counts.append(ordered)
    counts.sort()
    return counts[min(len(counts) - 1, int(MONOTONE_NULL_QUANTILE * len(counts)))]


def cycle_null(tournaments: int, per_pair: int, *, draws: int = NULL_DRAWS,
               seed: str = "") -> float:
    """The 5th percentile of a coin judge's mean cycles per tournament, at the actual n."""
    rng = random.Random(int(digest(["cycle-null", seed, tournaments, per_pair])[:8], 16))
    means = []
    for _ in range(draws):
        cyclic = determined = 0
        for _ in range(tournaments):
            edges = {}
            for low, high in itertools.combinations(range(len(LADDER_DOSES)), 2):
                rate = _coin_rates(rng, per_pair)
                edges[(low, high)] = None if abs(rate - 0.5) < 1e-9 else (1 if rate > 0.5 else -1)
            found, total = cycles_in(edges, len(LADDER_DOSES))
            cyclic += found
            determined += total
        means.append(cyclic / max(1, tournaments))
    means.sort()
    return means[min(len(means) - 1, int(CYCLE_NULL_QUANTILE * len(means)))]


# --------------------------------------------------------------------------- judges

Elicit = Callable[[Pair], list[Comparison]]


def panel_elicitor(elicitor: Elicitor) -> Elicit:
    """The real channel. `pair_question` is set per pair, which the cache tolerates because its
    key is the exact request text — a paraphrase misses the cache for exactly the affected records
    and replays everything else, which is the RUNBOOK's stated behaviour rather than a surprise."""

    def run(pair: Pair) -> list[Comparison]:
        elicitor.pair_question = pair.question
        return elicitor.compare_pair(pair.pair_id, pair.left, pair.right, n=pair.samples)

    return run


def oracle_elicitor(oracle: Callable[[Pair, str, int, int], str],
                    personas: tuple[Any, ...] = PANEL) -> Elicit:
    """A synthetic judge in the real arithmetic. Used only by `--selftest`."""

    def run(pair: Pair) -> list[Comparison]:
        out = []
        for persona in personas:
            for sample in range(pair.samples):
                for orientation in (0, 1):
                    choice = oracle(pair, persona.persona_id, sample, orientation)
                    out.append(Comparison(
                        pair_id=pair.pair_id, persona_id=persona.persona_id, sample=sample,
                        model="oracle", orientation=orientation, choice=choice,
                        reason_code="none", refused=choice is None,
                    ))
        return out

    return run


def _side(pair: Pair, orientation: int, prefer_right: bool) -> str:
    """Translate "prefer the right-hand text" into the slot it occupies at this orientation."""
    right_slot = "B" if orientation == 0 else "A"
    left_slot = "A" if orientation == 0 else "B"
    return right_slot if prefer_right else left_slot


def _oracles() -> dict[str, Callable[[Pair, str, int, int], str]]:
    """Nine judges with known pathologies, and what each one is here to prove.

    The perfect judge must clear every axiom; every other judge must die somewhere; and `cyclic`,
    `wording` and `noisy` must die at A3, A4 and A5 specifically, which is what makes those three
    arms non-redundant. This dictionary is the argument that the battery is jointly non-trivial,
    executed rather than asserted.
    """

    def rng_for(pair: Pair, persona: str, sample: int, orientation: int) -> random.Random:
        return random.Random(int(digest([pair.pair_id, persona, sample, orientation])[:8], 16))

    def perfect(pair, persona, sample, orientation):
        if pair.left_dose == pair.right_dose:
            return "neither"
        return _side(pair, orientation, pair.right_dose < pair.left_dose)

    def coin(pair, persona, sample, orientation):
        return rng_for(pair, persona, sample, orientation).choice(("A", "B", "neither"))

    def position(pair, persona, sample, orientation):
        return "A"

    def always_tie(pair, persona, sample, orientation):
        return "neither"

    def damage_seeker(pair, persona, sample, orientation):
        if pair.left_dose == pair.right_dose:
            return "neither"
        return _side(pair, orientation, pair.right_dose > pair.left_dose)

    def verbose(pair, persona, sample, orientation):
        if len(pair.left) == len(pair.right):
            return perfect(pair, persona, sample, orientation)
        return _side(pair, orientation, len(pair.right) > len(pair.left))

    def cyclic(pair, persona, sample, orientation):
        if pair.left_dose == pair.right_dose:
            return "neither"
        rungs = list(LADDER_DOSES)
        low, high = rungs.index(pair.left_dose), rungs.index(pair.right_dose)
        return _side(pair, orientation, (high - low) % len(rungs) == 1)

    def wording(pair, persona, sample, orientation):
        answer = perfect(pair, persona, sample, orientation)
        if pair.question == PARAPHRASE_QUESTION and answer in ("A", "B"):
            return "B" if answer == "A" else "A"
        return answer

    def noisy(pair, persona, sample, orientation):
        draw = rng_for(pair, persona, sample, orientation)
        if draw.random() < 0.2:
            return perfect(pair, persona, sample, orientation)
        return draw.choice(("A", "B", "neither"))

    def unseparable_forced(pair, persona, sample, orientation):
        """Correct wherever a difference exists, and manufactures a choice where none does.

        This is not a strawman: it is §83's measured failure, where near-twin pairs drove the
        panel to 0.73-0.83 chose-A because a forced choice on unseparable texts has to come from
        somewhere. It splits its slots evenly, so the bias check passes and only A0 catches it —
        which is the argument for A0 existing.
        """
        if pair.left != pair.right:
            return perfect(pair, persona, sample, orientation)
        return "A" if rng_for(pair, persona, sample, orientation).random() < 0.5 else "B"

    return {"perfect": perfect, "coin": coin, "position": position, "always_tie": always_tie,
            "damage_seeker": damage_seeker, "verbose": verbose, "cyclic": cyclic,
            "wording": wording, "noisy": noisy, "unseparable_forced": unseparable_forced}


# --------------------------------------------------------------------------- the battery

@dataclass
class Battery:
    """Every axiom's arithmetic over one candidate's comparisons."""

    comparisons: dict[str, list[Comparison]] = field(default_factory=dict)
    pairs: list[Pair] = field(default_factory=list)
    model: str = "oracle"

    def by_arm(self, arm: str) -> list[Comparison]:
        keys = [pair.pair_id for pair in self.pairs if pair.arm == arm]
        return [c for key in keys for c in self.comparisons.get(key, [])]

    # -- A0 / A1 -----------------------------------------------------------
    def indifference(self, arm: str, key: str) -> dict[str, Any]:
        comparisons = self.by_arm(arm)
        scored = _scored(comparisons)
        ties = tie_rate(comparisons)
        bias = positional_bias(comparisons)
        chose_a = bias.get("chose_A_rate", float("nan"))
        decided = bias.get("decided", 0)
        band_ok = decided == 0 or BIAS_BAND[0] <= float(chose_a) <= BIAS_BAND[1]
        readable = int(decided) >= BIAS_MIN_DECIDED
        verdict = "UNREADABLE" if not scored else (
            "PASS" if (ties >= TIE_FLOOR and band_ok) else "FAIL"
        )
        corrected = "UNREADABLE" if not scored else (
            "PASS" if (ties >= TIE_FLOOR and (band_ok or not readable)) else "FAIL"
        )
        return {
            "axiom": key, "comparisons": len(scored),
            "tie_rate": round(ties, 4) if scored else None,
            "tie_floor": TIE_FLOOR, "positional_bias": bias, "verdict": verdict,
            "verdict_corrected": corrected,
            "bias_readable": readable, "bias_min_decided": BIAS_MIN_DECIDED,
            "reading": (
                "two texts that are identical in content; anything but a tie is a report on "
                "position or on layout, and the win rate is not reported because there is no "
                "variant to win"
            ),
        }

    # -- A2 ----------------------------------------------------------------
    def monotonicity(self) -> dict[str, Any]:
        per_scene: dict[str, list[float]] = {}
        for pair in self.pairs:
            if pair.arm != "A2_A3_ladder" or pair.left_dose != 0.0:
                continue
            per_scene.setdefault(pair.scene, []).append(right_win_rate(
                self.comparisons.get(pair.pair_id, [])))
        usable = {scene: rates for scene, rates in per_scene.items()
                  if len(rates) == 3 and all(rate == rate for rate in rates)}
        ordered = [scene for scene, rates in usable.items()
                   if rates[0] >= rates[1] >= rates[2] and rates[2] < 0.5]
        widths = [len(_scored(self.comparisons.get(pair.pair_id, [])))
                  for pair in self.pairs
                  if pair.arm == "A2_A3_ladder" and pair.left_dose == 0.0]
        per_pair = max(2, round(statistics.median(widths))) if widths else 2
        bar = monotone_null(len(usable), per_pair, seed=self.model) if usable else 0
        return {
            "axiom": "A2_dose_monotonicity", "scenes": len(usable), "ordered": len(ordered),
            "null_95th": bar, "per_scene_rates": {k: [round(r, 4) for r in v]
                                                  for k, v in sorted(usable.items())},
            "verdict": "UNREADABLE" if not usable else ("PASS" if len(ordered) > bar else "FAIL"),
            "reading": (
                "the damaged side's win rate against the base must not rise with dose and must "
                "fall somewhere; all-ties is not monotonicity. The bar is a coin judge's 95th "
                "percentile at this n, simulated with the tie structure the run actually produced"
            ),
        }

    # -- A3 ----------------------------------------------------------------
    def transitivity(self) -> dict[str, Any]:
        doses = list(LADDER_DOSES)
        tournaments: dict[tuple[str, str], dict[tuple[int, int], int | None]] = {}
        for pair in self.pairs:
            if pair.arm != "A2_A3_ladder":
                continue
            low, high = doses.index(pair.left_dose), doses.index(pair.right_dose)
            for persona in {c.persona_id for c in self.comparisons.get(pair.pair_id, [])}:
                cell = [c for c in self.comparisons.get(pair.pair_id, [])
                        if c.persona_id == persona]
                tournaments.setdefault((pair.scene, persona), {})[(low, high)] = _edge(cell)
        cyclic = determined = triangles = 0
        for edges in tournaments.values():
            found, total = cycles_in(edges, len(doses))
            cyclic += found
            determined += total
            triangles += len(list(itertools.combinations(range(len(doses)), 3)))
        share = determined / triangles if triangles else 0.0
        mean_cycles = cyclic / len(tournaments) if tournaments else float("nan")
        bar = cycle_null(len(tournaments), 2, seed=self.model) if tournaments else float("nan")
        if not tournaments or share < DETERMINED_FLOOR:
            verdict = "UNREADABLE"
        else:
            verdict = "PASS" if mean_cycles < bar else "FAIL"
        return {
            "axiom": "A3_transitivity", "tournaments": len(tournaments),
            "cycles": cyclic, "mean_cycles": round(mean_cycles, 4) if tournaments else None,
            "null_5th": round(bar, 4) if bar == bar else None,
            "determined_share": round(share, 4), "determined_floor": DETERMINED_FLOOR,
            "verdict": verdict,
            "reading": (
                "a preference relation over four texts that contains a cycle is not a preference "
                "relation. Ties leave a triangle undetermined rather than acyclic, so a judge "
                "that declines everything reads UNREADABLE and not PASS"
            ),
        }

    # -- A4 ----------------------------------------------------------------
    def paraphrase(self) -> dict[str, Any]:
        canonical = {pair.scene: pair for pair in self.pairs
                     if pair.arm == "A2_A3_ladder" and pair.left_dose == 0.0
                     and pair.right_dose == LADDER_DOSES[-1]}
        rephrased = {pair.scene: pair for pair in self.pairs if pair.arm == "A4_paraphrase"}
        across: list[float] = []
        within: list[float] = []
        for scene, pair in canonical.items():
            base = self.comparisons.get(pair.pair_id, [])
            alt = self.comparisons.get(rephrased[scene].pair_id, []) if scene in rephrased else []
            cells: dict[tuple[str, int], list[Comparison]] = {}
            for comparison in _scored(base):
                cells.setdefault((comparison.persona_id, comparison.orientation), []).append(
                    comparison)
            for group in cells.values():
                if len(group) >= 2:
                    modal = Counter(c.choice for c in group).most_common(1)[0][1]
                    within.append(modal / len(group))
            for comparison in _scored(alt):
                twin = [c for c in _scored(base)
                        if c.persona_id == comparison.persona_id
                        and c.orientation == comparison.orientation]
                if twin:
                    modal = Counter(c.choice for c in twin).most_common(1)[0][0]
                    across.append(1.0 if comparison.choice == modal else 0.0)
        floor = statistics.fmean(within) if within else float("nan")
        agreement = statistics.fmean(across) if across else float("nan")
        readable = across and within
        return {
            "axiom": "A4_paraphrase_stability",
            "across_wording": round(agreement, 4) if across else None,
            "within_wording_floor": round(floor, 4) if within else None,
            "margin": PARAPHRASE_MARGIN, "n_across": len(across), "n_within": len(within),
            "verdict": ("UNREADABLE" if not readable else
                        ("PASS" if agreement >= floor - PARAPHRASE_MARGIN else "FAIL")),
            "reading": (
                "the floor is the instrument's agreement with its own resamples under one "
                "wording. A judge cannot be asked to survive a rephrasing more reliably than it "
                "survives itself, and the same number is the within-lineage floor the "
                "cross-lineage tier compares against"
            ),
        }

    # -- A5 ----------------------------------------------------------------
    def consistency(self) -> dict[str, Any]:
        cells: dict[str, list[float]] = {}
        for pair in self.pairs:
            if pair.arm == "A4_paraphrase":
                continue
            grouped: dict[tuple[str, int], list[Comparison]] = {}
            for comparison in _scored(self.comparisons.get(pair.pair_id, [])):
                grouped.setdefault((comparison.persona_id, comparison.sample), []).append(
                    comparison)
            scores = [right_win_rate(group) for group in grouped.values()]
            if len(scores) >= 2:
                cells[pair.pair_id] = scores
        estimate = icc_one(cells)
        bounds = bootstrap_icc(cells, seed=self.model)
        low, aggregate_low = bounds["low"], bounds["aggregate_low"]
        return {
            "axiom": "A5_within_item_consistency", "pairs": len(cells),
            "icc1": round(estimate, 4) if estimate == estimate else None,
            "interval": ([round(low, 4), round(bounds["high"], 4)] if low == low else None),
            "replicates": bounds["replicates"], "aggregate_floor": ICC_AGGREGATE_FLOOR,
            "aggregate_icc_low": (round(aggregate_low, 4)
                                  if aggregate_low == aggregate_low else None),
            "undefined_bootstrap_share": bounds["undefined_share"],
            "verdict": ("UNREADABLE" if len(cells) < 2 else
                        ("FAIL" if estimate != estimate or aggregate_low != aggregate_low
                         or aggregate_low <= ICC_AGGREGATE_FLOOR else "PASS")),
            "reading": (
                "between-pair variance against within-cell variance, over the whole battery's "
                "pairs. An undefined ICC is a FAIL and not a pass on a null: §70's constant "
                "instrument left every variance statistic undefined and that was the kill, not an "
                "absence of evidence"
            ),
        }

    # -- A6 ----------------------------------------------------------------
    def position(self) -> dict[str, Any]:
        arms = {}
        for arm in sorted({pair.arm for pair in self.pairs}):
            bias = positional_bias(self.by_arm(arm))
            chose_a = bias.get("chose_A_rate", float("nan"))
            in_band = bool(bias.get("decided", 0)) and (
                BIAS_BAND[0] <= float(chose_a) <= BIAS_BAND[1])
            arms[arm] = {"bias": bias, "in_band": in_band}
        readable = [arm for arm, row in arms.items() if row["bias"].get("decided", 0)]
        estimable = [arm for arm, row in arms.items()
                     if int(row["bias"].get("decided", 0)) >= BIAS_MIN_DECIDED]
        return {
            "axiom": "A6_position", "arms": arms, "band": list(BIAS_BAND),
            "bias_min_decided": BIAS_MIN_DECIDED, "estimable_arms": estimable,
            "verdict": ("UNREADABLE" if not readable else
                        ("PASS" if all(arms[arm]["in_band"] for arm in readable) else "FAIL")),
            "verdict_corrected": ("UNREADABLE" if not estimable else
                                  ("PASS" if all(arms[arm]["in_band"] for arm in estimable)
                                   else "FAIL")),
            "reading": (
                "per arm, never pooled and never inherited. §79.1 measured 0.356 on 368 "
                "comparisons and called positional bias a property of the pair; an arm outside "
                "the band is unreadable whatever it says about prose"
            ),
        }

    def verdict(self) -> dict[str, Any]:
        axioms = [
            self.indifference("A0_indifference", "A0_indifference"),
            self.indifference("A1_format_invariance", "A1_format_invariance"),
            self.monotonicity(),
            self.transitivity(),
            self.paraphrase(),
            self.consistency(),
            self.position(),
        ]
        rows = {row["axiom"]: row for row in axioms}

        def read(field: str) -> dict[str, Any]:
            hit = sorted(k for k, r in rows.items() if r.get(field, r["verdict"]) == "FAIL")
            unread = sorted(k for k, r in rows.items()
                            if r.get(field, r["verdict"]) == "UNREADABLE")
            return {
                "overall": ("CLEARED" if not hit and not unread else
                            ("DISQUALIFIED" if hit else "UNREADABLE")),
                "failed": hit, "unreadable": unread,
            }

        as_registered = read("verdict")
        corrected = read("verdict_corrected")
        failed, unreadable = as_registered["failed"], as_registered["unreadable"]
        overall = as_registered["overall"]
        return {
            "overall": overall, "failed": failed, "unreadable": unreadable, "axioms": rows,
            "as_registered": as_registered, "corrected": corrected,
            "two_readings": (
                "`as_registered` is the rule committed before the first call; `corrected` adds "
                "only the decided-count floor below which a positional band may not be read, "
                "declared mid-run from simulation with no elicited verdict inspected. Both are "
                "printed, neither is selected, and a disagreement between them is a fact about "
                "the battery rather than about the judge"
            ),
            "reading": (
                "CLEARED means the candidate is coherent enough to be worth paying to test "
                "against a label. It is not evidence about taste and licenses nothing"
            ),
        }


def run_battery(pairs: list[Pair], elicit: Elicit, *, model: str) -> Battery:
    battery = Battery(pairs=pairs, model=model)
    for pair in pairs:
        battery.comparisons[pair.pair_id] = elicit(pair)
    return battery


# ------------------------------------------------------------------- operating characteristic

#: Scenarios for `operating_characteristic`, each a *good* judge with a different amount of the
#: heterogeneity the repo has measured. `beta` is the logit weight on the dose gap, `tau_null` the
#: tie rate on a pair with no real difference (§85 measured 0.79 on layout-only shams, which is
#: where the default comes from), `scene_sd` and `persona_sd` the random effects — the repo's
#: `variance_split` ratios of 0.0028-0.0342 say the passage dimension dominates the persona one by
#: 5-19x, which is why they are never set equal here.
OC_SCENARIOS: tuple[tuple[str, dict[str, float]], ...] = (
    ("homogeneous", {"beta": 3.0, "tau_null": 0.79, "scene_sd": 0.0, "persona_sd": 0.0}),
    ("measured_heterogeneity", {"beta": 3.0, "tau_null": 0.79, "scene_sd": 0.6,
                                "persona_sd": 0.15}),
    ("strong_heterogeneity", {"beta": 3.0, "tau_null": 0.79, "scene_sd": 1.2,
                              "persona_sd": 0.15}),
    ("weak_dose_response", {"beta": 1.5, "tau_null": 0.79, "scene_sd": 0.6, "persona_sd": 0.15}),
    ("forced_choice_habit", {"beta": 3.0, "tau_null": 0.35, "scene_sd": 0.6, "persona_sd": 0.15}),
)


def _good_judge_run(pairs: list[Pair], rng: random.Random, *, beta: float, tau_null: float,
                    scene_sd: float, persona_sd: float, tie_slope: float = 1.2) -> Battery:
    """One synthetic run of a judge that is genuinely invariant, monotone and wording-stable."""
    scenes = {pair.scene for pair in pairs}
    scene_effect = {scene: rng.gauss(0, scene_sd) for scene in scenes}
    persona_effect = {persona.persona_id: rng.gauss(0, persona_sd) for persona in PANEL}
    battery = Battery(pairs=pairs, model="operating-characteristic")
    for pair in pairs:
        gap = pair.right_dose - pair.left_dose
        out: list[Comparison] = []
        for persona in PANEL:
            for sample in range(pair.samples):
                for orientation in (0, 1):
                    if pair.left == pair.right or gap == 0:
                        choice = ("neither" if rng.random() < tau_null
                                  else rng.choice(("A", "B")))
                    else:
                        latent = (-beta * gap + scene_effect[pair.scene]
                                  + persona_effect[persona.persona_id])
                        if rng.random() < tau_null * math.exp(-tie_slope * abs(latent)):
                            choice = "neither"
                        else:
                            prefer_right = rng.random() < 1 / (1 + math.exp(-latent))
                            choice = _side(pair, orientation, prefer_right)
                    out.append(Comparison(
                        pair_id=pair.pair_id, persona_id=persona.persona_id, sample=sample,
                        model="operating-characteristic", orientation=orientation,
                        choice=choice, reason_code="none", refused=False))
        battery.comparisons[pair.pair_id] = out
    return battery


def operating_characteristic(pairs: list[Pair], *, draws: int = 120) -> dict[str, Any]:
    """P(disqualify | a genuinely good but *stochastic* judge), at the battery's own geometry.

    **The selftest is not this measurement and cannot be.** Its perfect oracle is deterministic,
    and the question a disqualifier tier has to answer is what it does to a judge that is right on
    average and noisy per call. Seven conjunctive bars compound, so the answer is not any single
    bar's false-fail rate — which is BRIEF §6 item 4 pointed at the battery instead of at a
    threshold scan.

    **This is a simulation whose parameters were chosen, not measured**, so it is an argument about
    the arithmetic rather than evidence about any judge. It is reported for exactly that: to say
    how much of a DISQUALIFIED verdict could be the battery.
    """
    rows: dict[str, Any] = {}
    for label, params in OC_SCENARIOS:
        rng = random.Random(int(digest(["oc", label])[:8], 16))
        counts = {"as_registered": Counter(), "corrected": Counter()}
        per_axiom: Counter = Counter()
        for _ in range(draws):
            verdict = _good_judge_run(pairs, rng, **params).verdict()
            for reading in counts:
                counts[reading][verdict[reading]["overall"]] += 1
            for key in verdict["corrected"]["failed"]:
                per_axiom[key] += 1
        rows[label] = {
            "params": params,
            "as_registered": {k: round(v / draws, 3) for k, v in counts["as_registered"].items()},
            "corrected": {k: round(v / draws, 3) for k, v in counts["corrected"].items()},
            "corrected_fail_by_axiom": {k: round(v / draws, 3)
                                        for k, v in sorted(per_axiom.items(),
                                                           key=lambda kv: -kv[1])},
        }
    return {
        "draws": draws, "scenarios": rows,
        "reading": (
            "the fraction of runs on which a GOOD judge is disqualified. Under the rule as "
            "registered this ran 0.83-1.00, which is why the decided-count floor was declared; "
            "under the corrected rule the residual driver is A3, whose null treats scenes as "
            "independent and whose false-fail rate therefore rises with scene heterogeneity"
        ),
    }


# --------------------------------------------------------------------------- selftest

def selftest() -> dict[str, Any]:
    """Nine oracles through the whole arithmetic, offline, before a call is ever made.

    The assertions are the design claim: the perfect judge clears everything, every pathology dies
    somewhere, and the three arms that would otherwise be arguable — transitivity, paraphrase
    stability, within-item consistency — are each the *only* thing standing between a specific
    pathology and a clean sheet.
    """
    scenes = [(f"fixture-{index}", _fixture(index)) for index in range(6)]
    pairs, certificate = build_pairs(scenes, samples=3)
    assert pairs, "fixtures produced no pairs"
    assert all(entry["usable"] for entry in certificate), certificate

    results: dict[str, Any] = {}
    for name, oracle in _oracles().items():
        battery = run_battery(pairs, oracle_elicitor(oracle), model=f"oracle:{name}")
        results[name] = battery.verdict()

    perfect = results["perfect"]
    assert perfect["overall"] == "CLEARED", perfect
    for name, verdict in results.items():
        if name == "perfect":
            continue
        assert verdict["overall"] != "CLEARED", f"{name} passed the whole battery: {verdict}"

    def only_failure(name: str, axiom: str) -> None:
        others = [key for key in results[name]["failed"] + results[name]["unreadable"]
                  if key != axiom]
        assert axiom in results[name]["failed"] + results[name]["unreadable"], \
            f"{name} did not die at {axiom}: {results[name]}"
        assert not others, f"{name} also died at {others}, so {axiom} is not what caught it"

    only_failure("unseparable_forced", "A0_indifference")
    only_failure("verbose", "A1_format_invariance")
    only_failure("damage_seeker", "A2_dose_monotonicity")
    only_failure("cyclic", "A3_transitivity")
    only_failure("wording", "A4_paraphrase_stability")
    assert "A5_within_item_consistency" in results["noisy"]["failed"], results["noisy"]
    assert "A5_within_item_consistency" in results["always_tie"]["failed"], results["always_tie"]
    assert "A6_position" in results["position"]["failed"], results["position"]

    return {"oracles": {name: {"overall": row["overall"], "failed": row["failed"],
                               "unreadable": row["unreadable"]}
                        for name, row in results.items()},
            "pairs": len(pairs),
            "claim": (
                "the perfect oracle clears the battery; every pathology dies somewhere; and "
                "A0-A4 each have an oracle they are the SOLE cause of death for, which is what "
                "makes those five arms non-redundant rather than decorative"
            ),
            "limitation": (
                "A5 and A6 have no sole-cause oracle here and the reason is structural rather "
                "than an omission. An instrument noisy enough to fail an aggregate reliability "
                "floor also blurs the ladder A2 reads, and a slot preference large enough to "
                "leave the band also shows up as a non-tie on the identity arm. They are kept "
                "because they report *how much* of a verdict is resample noise and *where* the "
                "bias lives, which are quantities the licence needs even on a candidate that "
                "clears everything else"
            )}


def _fixture(index: int) -> str:
    """Eight paragraphs of shaped filler. Never sent to a model: `selftest` runs offline."""
    return "\n\n".join(
        f"Paragraph {block} of fixture {index}. " +
        " ".join(f"Sentence {sentence} carries a clause and then another one."
                 for sentence in range(3))
        for block in range(8)
    )


# --------------------------------------------------------------------------- cli

def load_scenes(options: argparse.Namespace) -> list[tuple[str, str]]:
    """This system's own prose, from the committed export by default.

    The RUNBOOK records that every reader number in §70 rests on a `toll.db` that is gitignored
    and does not survive a fresh clone. `corpora/toll-scenes.json` is the same scenes, committed,
    and `state_coverage.py` and `taste_calibration.py` already read it — so the default here is
    the portable one and `--book-db` is the override rather than the other way round.
    """
    if options.book_db:
        return [(unit.unit_id, unit.text)
                for unit in generated_scenes(options.book_db, min_words=options.min_words)]
    payload = json.loads(Path(options.scenes_json).read_text(encoding="utf-8"))
    return [(scene["unit_id"], scene["text"]) for scene in payload["scenes"]
            if len(scene["text"].split()) >= options.min_words]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scenes-json", default=str(HERE / "corpora" / "toll-scenes.json"),
                        help="the committed export; survives a fresh clone, which toll.db does not")
    parser.add_argument("--book-db", default=None,
                        help="read scenes from a book database instead of the committed export")
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=6)
    parser.add_argument("--samples", type=int, default=3,
                        help="resamples on the base-vs-rung pairs; A5 needs at least 2")
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument("--effort", default=None)
    parser.add_argument("--cache", default="axiom-battery-raw.jsonl")
    parser.add_argument("--out", default="axiom-battery.json")
    parser.add_argument("--selftest", action="store_true", help="offline oracles; no calls")
    parser.add_argument("--operating-characteristic", action="store_true",
                        help="P(disqualify | a good stochastic judge); offline, no calls")
    parser.add_argument("--dry-run", action="store_true", help="the null, through the plumbing")
    parser.add_argument("--yes", action="store_true", help="required before any paid call")
    options = parser.parse_args(argv)

    if options.selftest:
        print(json.dumps(selftest(), indent=2))
        return 0

    if options.operating_characteristic:
        scenes = load_scenes(options)[:options.scenes]
        pairs, _ = build_pairs(scenes, samples=options.samples)
        print(json.dumps(operating_characteristic(pairs), indent=2))
        return 0

    scenes = load_scenes(options)[:options.scenes]
    pairs, certificate = build_pairs(scenes, samples=options.samples)
    comparisons = sum(len(PANEL) * 2 * pair.samples for pair in pairs)
    print(f"{len(scenes)} scenes, {len(pairs)} pairs, {comparisons} comparisons, "
          f"~${comparisons * 0.032:.2f} at §81's measured rate")
    dropped = [entry for entry in certificate if not entry["usable"]]
    if dropped:
        print(f"dropped {len(dropped)} scene(s) with no strictly increasing nested ladder")
    if not options.yes and not options.dry_run:
        print("refusing to spend without --yes")
        return 2

    with Elicitor(HERE / "results" / options.cache, model=options.model, spot_model=None,
                  effort=options.effort, transport=options.transport,
                  dry_run=options.dry_run) as elicitor:
        battery = run_battery(pairs, panel_elicitor(elicitor), model=options.model)
        spend = elicitor.spend()
        calls = {"api_calls": elicitor.api_calls, "replayed_calls": elicitor.replayed}

    summary = {
        "pre_registration": PRE_REGISTRATION,
        "pre_registration_corrected": PRE_REGISTRATION_CORRECTED,
        "panel_model": options.model, "transport": options.transport,
        "personas": [persona.persona_id for persona in PANEL],
        "doses": list(LADDER_DOSES), "samples": options.samples,
        "scenes": [scene for scene, _ in scenes], "ladder_certificate": certificate,
        "pairs": len(pairs), "comparisons": comparisons,
        "dry_run": options.dry_run, "spend": spend, "calls": calls,
        "verdict": battery.verdict(),
        "selftest": selftest(),
        "operating_characteristic": operating_characteristic(pairs),
    }
    (HERE / "results" / options.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["verdict"], indent=2))
    if options.dry_run and summary["verdict"]["overall"] == "CLEARED":
        print("DEFECT: the null cleared the battery. The arithmetic is wrong, not the judge.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
