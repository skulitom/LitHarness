"""A standing benchmark: does a judge configuration agree with a label nobody told it about?

§77 asked this with eight pairs and §77.1 records why the answer did not hold. The arm was void on
its own positional-bias precondition, and the two sides were not comparable: median view counts of
213,623 against 837.5, a **255x** gap. And §56.6 item 4 had already refused selection from
conversion deciles on 2026-08-17, because the deciles are recoverable from prose-blind `followers`
at AUC 0.814 ([craft-corpus.md](craft-corpus.md) §4.1).

**Matching alone cannot fix that, and the reason is arithmetic rather than statistical.** The label
is `conversion = followers / total_views`, a ratio of the two prose-blind quantities anyone would
want to hold fixed. Balance the denominator and the numerator becomes a *perfect* predictor: the
first build of this module matched views to within a factor of two and got followers imbalanced 7.6x
with the high-conversion side larger in **21 of 21** pairs. That is forced —
`followers_hi/followers_lo = (conv_hi/conv_lo) x (views_hi/views_lo)`, so with a conversion gap of
2x and a view gap under 2x the follower ordering cannot come out any other way. Balance followers
instead and views takes the role. **For any pair with a real label gap, at least one prose-blind
popularity covariate orders the pair, and no choice of tolerances removes both.**

**So the confound's sign becomes the instrument.** Pairs are selected into two strata:

    aligned    views matched to within a factor of two, so the high-conversion side necessarily
               carries more followers (measured: 4.65x). Every popularity rule points AT the label.
    crossed    the high-conversion side carries FEWER followers and fewer views (measured: 0.635x
               followers, 0.122x views). Every popularity rule points AWAY from the label.

Length is matched in both. **A judge reading prose should agree with the label in both strata; a
judge proxying popularity agrees in one and must disagree in the other.** No single fixed
prose-blind rule can clear 0.50 in both, by construction, which is what makes
`min(agreement_aligned, agreement_crossed)` a bar rather than a number. Averaging the strata would
destroy exactly this property, so the benchmark never averages them.

**What a judge candidate may vary, and what it may not.** Model, transport, the pair question, and
which of the existing personas sit on the panel. It may **not** introduce a new persona or a new
rubric: §77's 2x2 measured one plain word outperforming four authored personas, and a criterion this
project writes cannot be evidence about a judge this project is selecting. The point of an external
label is that the ordering comes from outside.

A second axis ships and is **declared unusable for licensing**: `acclaim` puts Mother of Learning
against a conversion-median RoyalRoad chapter. MoL is famous and comes from a Wayback capture rather
than the shards, so it is neither platform-matched nor recognition-free. It is reported because it
is the arm §77 could actually read, not because it is clean.

**The corpus ceiling is 66 matched pairs, not hundreds.** The two cached shards hold 107 pre-LLM
LitRPG stories clearing a 10,000-view floor at 1,500-6,000 words, one chapter per story because
`conversion` is a fiction-level constant. That caps disjoint pairs at 53 and yields 34 aligned plus
32 crossed before disjointness is enforced across strata. Reaching hundreds means the 45 uncached
shards of the 47-shard dataset, which is a disk-and-network decision rather than a code one.

Build with `--build` under the interpreter that has pyarrow, then run judges against it. The corpus
holds third-party prose and is gitignored; `--build` also writes a text-free metadata sidecar with
every pair's covariates, which is the auditable record and is committed.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

#: Words per excerpt, matching `taste_calibration.EXCERPT_WORDS` so the two runs are comparable.
EXCERPT_WORDS = 1_000

#: Minimum total views for a story to carry a readable conversion ratio. Below this the denominator
#: is too small for `followers / total_views` to mean anything: §77.1's high-conversion pool sat at
#: 174-1,667 views, where a single follower moves the label by 0.006.
MIN_VIEWS = 10_000

#: Minimum high/low conversion ratio inside a pair. A matched pair whose sides differ by 10% on a
#: noisy label is not a test of anything.
MIN_CONVERSION_RATIO = 2.0

#: Tolerances in log10 units. 0.30 is a factor of two. §77.1's pairs sat at 2.4 (255x) on views.
MAX_LOG_VIEW_GAP = 0.30
MAX_LOG_WORD_GAP = 0.10

#: The two strata, by what the prose-blind covariates do relative to the label. `aligned` has every
#: popularity rule pointing at the label; `crossed` has every one pointing away from it.
STRATA = ("aligned", "crossed")


def _excerpt(text: str, words: int = EXCERPT_WORDS, *, start_fraction: float = 0.2) -> str:
    """A paragraph-aligned window from inside the text. `taste_calibration.excerpt`'s logic."""
    from taste_calibration import excerpt

    return excerpt(text, words, start_fraction=start_fraction)


def _story_pool(args: argparse.Namespace) -> list[dict[str, Any]]:
    """One chapter per story, pre-LLM only, above the views floor.

    One chapter per story because `conversion` is a fiction-level constant — verified: the
    `(followers, total_views)` tuple does not vary across a fiction's chapters — so a second chapter
    adds text without adding a labelled unit. Eight chapters of one fiction in a stratum is a
    stratum of one, which is the defect `taste_calibration.dump`'s own comment records.

    `human_pre_llm` is filtered rather than trusted: `royalroad_chapters` yields every cohort
    `era_cohort` can label, so §77's pools admitted 2025 and declared-AI chapters and the eight
    pairs it happened to compare were pre-LLM by luck.
    """
    from corpus_io import royalroad_chapters

    pool: dict[str, dict[str, Any]] = {}
    for unit in royalroad_chapters(shards=tuple(args.shards), min_words=args.min_words,
                                   limit=args.limit):
        if unit.meta.get("cohort") != "human_pre_llm":
            continue
        views = float(unit.meta.get("total_views") or 0)
        conversion = unit.meta.get("conversion")
        if not conversion or views < args.min_views or unit.work_id in pool:
            continue
        words = len(unit.text.split())
        if words > args.max_words:
            continue
        pool[unit.work_id] = {
            "unit_id": unit.unit_id, "work_id": unit.work_id, "conversion": float(conversion),
            "views": views, "followers": float(unit.meta.get("followers") or 0),
            "favorites": float(unit.meta.get("favorites") or 0), "words": words,
            "released_at": unit.released_at, "text": unit.text,
        }
    return sorted(pool.values(), key=lambda s: s["conversion"])


def _candidates(stories: list[dict[str, Any]], args: argparse.Namespace,
                stratum: str) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    """Every (high, low, cost) pair admissible for one stratum. Length is matched in both."""
    out = []
    for first, second in itertools.combinations(stories, 2):
        high, low = (first, second) if first["conversion"] > second["conversion"] else (
            second, first)
        if high["conversion"] < args.min_conversion_ratio * low["conversion"]:
            continue
        word_gap = abs(math.log10(high["words"] / low["words"]))
        if word_gap > args.max_log_word_gap:
            continue
        view_gap = abs(math.log10(high["views"] / low["views"]))
        if stratum == "aligned":
            if view_gap > args.max_log_view_gap:
                continue
            cost = view_gap + word_gap
        else:
            # The high-conversion side must be the less-followed *and* less-read one, so that
            # "pick more followers" and "pick more views" both point at the low-conversion side.
            if not (high["followers"] < low["followers"] and high["views"] < low["views"]):
                continue
            cost = word_gap
        out.append((high, low, cost))
    return out


def _bucket(stratum: str, high: dict[str, Any], low: dict[str, Any]) -> str:
    """The selection bucket a pair belongs to. `aligned` splits by the sign of its view residual.

    **Why the split exists, measured.** The first balanced build matched views inside `aligned` to
    within a factor of two but did not control the *direction* of what was left, and higher
    conversion correlates with fewer views, so 15 of 23 aligned pairs had the high-conversion side
    less-viewed. "Pick the less-viewed side" then scored 0.652 in `aligned` and 1.000 in `crossed` —
    a minimum of 0.652, so a prose-blind rule cleared 0.50 in *both* strata and the bar the whole
    design rests on was no longer 0.50. Filling the two signs evenly drives that rule back to
    chance inside `aligned`, which restores the property: no fixed popularity rule can clear 0.50
    in both strata at once.
    """
    if stratum != "aligned":
        return stratum
    return "aligned+" if high["views"] > low["views"] else "aligned-"


#: Which stratum each selection bucket reports into.
_STRATUM_OF = {"crossed": "crossed", "aligned+": "aligned", "aligned-": "aligned"}


def _select_interleaved(
    candidates: dict[str, list[tuple[dict[str, Any], dict[str, Any], float]]],
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    """Fill both strata evenly from one disjoint story pool, best-matched pair first.

    **Interleaved rather than stratum-at-a-time, and the first build shows why.** Taking `crossed`
    to exhaustion first gave it 37 pairs and left `aligned` 7, because both strata draw from the
    same 107 stories and disjointness is enforced across them. The bar is
    `min(agreement_aligned, agreement_crossed)`, so the benchmark's power is set by its *smaller*
    stratum: 37 and 7 is a worse instrument than 22 and 22 despite having more pairs in total.

    Greedy within a stratum because the tolerances are hard constraints — a pair either balances or
    is not emitted, so a better assignment buys a few more pairs rather than better ones.
    """
    queues: dict[str, list[tuple[dict[str, Any], dict[str, Any], float]]] = {
        bucket: [] for bucket in _STRATUM_OF
    }
    for stratum, entries in candidates.items():
        for high, low, cost in entries:
            queues[_bucket(stratum, high, low)].append((high, low, cost))
    for bucket in queues:
        queues[bucket].sort(key=lambda entry: entry[2])

    cursors = dict.fromkeys(queues, 0)
    picked: dict[str, list[dict[str, Any]]] = {stratum: [] for stratum in STRATA}
    per_bucket: dict[str, int] = dict.fromkeys(queues, 0)
    used: set[str] = set()
    while True:
        progressed = False
        # Serve the bucket that is furthest behind, ranked first on its stratum's total so a scarce
        # stratum is never starved by a plentiful one, then on the bucket's own count so `aligned`'s
        # two view-signs fill evenly.
        order = sorted(
            queues,
            key=lambda name: (len(picked[_STRATUM_OF[name]]), per_bucket[name],
                              STRATA.index(_STRATUM_OF[name])),
        )
        for bucket in order:
            stratum = _STRATUM_OF[bucket]
            if limit and len(picked[stratum]) >= limit:
                continue
            queue, index = queues[bucket], cursors[bucket]
            while index < len(queue):
                high, low, cost = queue[index]
                index += 1
                if high["work_id"] in used or low["work_id"] in used:
                    continue
                used |= {high["work_id"], low["work_id"]}
                picked[stratum].append(
                    {"high": high, "low": low, "match_cost": round(cost, 4)})
                per_bucket[bucket] += 1
                progressed = True
                break
            cursors[bucket] = index
            if progressed:
                break
        if not progressed:
            return picked


def _balance(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in ("views", "followers", "favorites", "words", "conversion"):
        highs = [pair["high"][field] for pair in pairs]
        lows = [pair["low"][field] for pair in pairs]
        if not highs:
            continue
        out[field] = {
            "high_median": round(statistics.median(highs), 6),
            "low_median": round(statistics.median(lows), 6),
            "median_ratio": (round(statistics.median(highs) / statistics.median(lows), 4)
                             if statistics.median(lows) else None),
            "high_side_larger_in_pairs": sum(
                1 for pair in pairs if pair["high"][field] > pair["low"][field]),
            "of_pairs": len(pairs),
        }
    return out


def build(args: argparse.Namespace) -> int:
    """Select both strata and write the corpus plus a text-free metadata sidecar."""
    from corpus_io import mol_chapters

    stories = _story_pool(args)
    if len(stories) < 4:
        raise SystemExit(f"only {len(stories)} stories cleared the floor; nothing to pair")

    selected = _select_interleaved(
        {stratum: _candidates(stories, args, stratum) for stratum in STRATA}, args.pairs
    )

    corpus: dict[str, Any] = {}
    meta_pairs: list[dict[str, Any]] = []

    def covariates(side: dict[str, Any]) -> dict[str, Any]:
        # `excerpt_words` is the length the judge can actually perceive. `words` is the source
        # chapter's, which the excerpting erases: a rule over it is a rule over something no judge
        # ever sees, so it cannot be a route by which one scores without reading. Both are recorded
        # and the prose-blind table ranks on the excerpt.
        out = {key: side[key] for key in
               ("unit_id", "work_id", "conversion", "views", "followers", "favorites", "words",
                "released_at")}
        out["excerpt_words"] = len(_excerpt(side["text"]).split())
        return out

    for stratum in STRATA:
        corpus[f"axis_conversion_{stratum}"] = [
            {"pair_id": f"{stratum}{index}", "high": _excerpt(pair["high"]["text"]),
             "low": _excerpt(pair["low"]["text"])}
            for index, pair in enumerate(selected[stratum])
        ]
        meta_pairs += [
            {"pair_id": f"{stratum}{index}", "stratum": stratum,
             "match_cost": pair["match_cost"],
             "high": covariates(pair["high"]), "low": covariates(pair["low"])}
            for index, pair in enumerate(selected[stratum])
        ]

    mol = mol_chapters()
    middle = len(stories) // 2
    acclaim = []
    for offset, unit in enumerate(mol[: args.acclaim_pairs or 0]):
        index = middle + offset
        if not 0 <= index < len(stories):
            break
        acclaim.append({"pair_id": f"accl{offset}", "mol": _excerpt(unit.text),
                        "rr": _excerpt(stories[index]["text"]),
                        "rr_unit_id": stories[index]["unit_id"]})
    corpus["axis_acclaim"] = acclaim

    meta = {
        "protocol": "plan/stage-0-decisions.md §79",
        "built_from": {
            "shards": list(args.shards), "limit": args.limit, "min_words": args.min_words,
            "max_words": args.max_words, "min_views": args.min_views, "cohort": "human_pre_llm",
            "min_conversion_ratio": args.min_conversion_ratio,
            "max_log_view_gap": args.max_log_view_gap,
            "max_log_word_gap": args.max_log_word_gap,
        },
        "stories_clearing_floor": len(stories),
        "max_disjoint_pairs_possible": len(stories) // 2,
        "pairs_per_stratum": {stratum: len(selected[stratum]) for stratum in STRATA},
        "acclaim_pairs": len(acclaim),
        "excerpt_words": EXCERPT_WORDS,
        "balance": {stratum: _balance(selected[stratum]) for stratum in STRATA},
        "pairs": meta_pairs,
        "note": (
            "high/low name the conversion label only. conversion = followers/views, so no pair "
            "with a real label gap can balance both popularity covariates; the strata carry the "
            "confound in opposite directions instead. `aligned` has every prose-blind popularity "
            "rule pointing at the label and `crossed` has every one pointing away, so no single "
            "fixed rule clears 0.50 in both. The bar is the minimum across strata, never the mean."
        ),
    }
    Path(args.corpus).parent.mkdir(parents=True, exist_ok=True)
    Path(args.corpus).write_text(json.dumps(corpus, indent=1), encoding="utf-8")
    Path(args.meta).parent.mkdir(parents=True, exist_ok=True)
    Path(args.meta).write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: value for key, value in meta.items() if key != "pairs"}, indent=2))
    print(f"wrote {args.corpus} (gitignored, holds third-party prose)")
    print(f"wrote {args.meta} (text-free, committed)")
    return 0


#: Predictors that read no prose. Each guesses which side carries the higher conversion label from
#: one covariate. Both directions of each are included on purpose: in `aligned` the "more" rules
#: score near 1.0 and in `crossed` the "fewer" rules do, which is the point — a rule's *minimum*
#: across the two strata is what a judge has to beat, and by construction none of them can clear
#: 0.50 there. Reported per stratum so the arithmetic is visible rather than asserted.
PROSE_BLIND_RULES = {
    "pick_more_followers": lambda high, low: high["followers"] > low["followers"],
    "pick_fewer_followers": lambda high, low: high["followers"] < low["followers"],
    "pick_more_views": lambda high, low: high["views"] > low["views"],
    "pick_fewer_views": lambda high, low: high["views"] < low["views"],
    "pick_more_favorites": lambda high, low: high["favorites"] > low["favorites"],
    "pick_longer_excerpt": lambda high, low: high["excerpt_words"] > low["excerpt_words"],
    # Over the source chapter rather than the excerpt, so it is NOT a route a judge could take:
    # `_excerpt` cuts both sides to about `EXCERPT_WORDS`. Reported to show the selection is
    # length-balanced at source too, and excluded from the bar for that reason.
    "pick_longer_chapter_not_shown": lambda high, low: high["words"] > low["words"],
}

#: Rules excluded from the bar because the judge cannot perceive the quantity they read.
NOT_A_ROUTE = frozenset({"pick_longer_chapter_not_shown"})


def prose_blind(meta: dict[str, Any]) -> dict[str, Any]:
    """Per-stratum accuracy of every prose-blind rule, plus its minimum across strata."""
    out: dict[str, Any] = {}
    for name, rule in PROSE_BLIND_RULES.items():
        per_stratum: dict[str, float] = {}
        for stratum in STRATA:
            pairs = [p for p in meta.get("pairs", []) if p["stratum"] == stratum]
            if not pairs:
                continue
            hits = sum(1 for pair in pairs if rule(pair["high"], pair["low"]))
            per_stratum[stratum] = round(hits / len(pairs), 4)
        out[name] = {
            "per_stratum": per_stratum,
            "min_across_strata": round(min(per_stratum.values()), 4) if per_stratum else None,
        }
    return out


#: Pre-registered before this benchmark's first elicitation and written into every report, so a
#: candidate cannot be read against a bar chosen after its number arrived.
PRE_REGISTRATION: dict[str, str] = {
    "precondition": (
        "per-stratum positional bias within 0.40-0.60, read on the point estimate exactly as §74 "
        "and §77 read it. Not loosened: these strata carry more pairs than the 63-comparison arm "
        "that rule voided, so the estimate is tighter rather than more forgiving"
    ),
    "bar": (
        "min(agreement_aligned, agreement_crossed) must exceed the best prose-blind rule's own "
        "minimum across the same strata, and the interval lower bound in EACH stratum must clear "
        "0.50. The minimum is the statistic because conversion = followers/views makes some "
        "popularity rule perfect within any single stratum"
    ),
    "never_average": (
        "the strata are never pooled or averaged. A popularity-proxying judge scores near 1.0 in "
        "aligned and near 0.0 in crossed, and their mean is 0.5 — indistinguishable from a coin "
        "and from a genuine partial signal. Pooling would discard the only discriminating "
        "structure the corpus has"
    ),
    "primary_axis": (
        "conversion, both strata. acclaim is reported and cannot license a judge: MoL is famous "
        "and off-platform, so recognition explains agreement without a claim about prose (§77.1)"
    ),
    "passes": (
        "bar met with bias in band in both strata: this configuration orders matched human prose "
        "on a label nobody told it about, against the popularity covariates in one stratum, and "
        "may be considered for the §72 judge licence"
    ),
    "fails": (
        "otherwise. A judge that cannot do this has no external warrant, whatever it scores on "
        "our own reason vocabulary (§77's reason codes are ours; §56.3 refused the raw bar)"
    ),
}


def verdict(agreement: dict[str, float], bias: dict[str, dict[str, Any]],
            baselines: dict[str, Any], intervals: dict[str, dict[str, Any]]) -> dict[str, object]:
    """The pre-registered decision. Minimum across strata, precondition first, never the mean."""
    present = [stratum for stratum in STRATA if stratum in agreement]
    if len(present) < len(STRATA):
        return {"outcome": "ABSENT",
                "why": f"needs both strata, have {present}",
                "conditions": PRE_REGISTRATION}
    void = {
        stratum: bias.get(stratum, {}).get("chose_A_rate") for stratum in STRATA
        if not (isinstance(bias.get(stratum, {}).get("chose_A_rate"), float)
                and 0.40 <= bias[stratum]["chose_A_rate"] <= 0.60)
    }
    if void:
        return {"outcome": "VOID", "why": f"positional bias outside 0.40-0.60: {void}",
                "conditions": PRE_REGISTRATION}

    judge_min = min(agreement[stratum] for stratum in STRATA)
    blind_mins = [entry["min_across_strata"] for name, entry in baselines.items()
                  if entry.get("min_across_strata") is not None and name not in NOT_A_ROUTE]
    best_blind_min = max(blind_mins) if blind_mins else 0.5
    lowers = {stratum: (intervals.get(stratum) or {}).get("low") for stratum in STRATA}
    clears = {
        stratum: isinstance(value, float) and value > 0.50 for stratum, value in lowers.items()
    }
    beats_blind = judge_min > best_blind_min
    if beats_blind and all(clears.values()):
        outcome = "PASSES"
        why = (f"minimum agreement {judge_min} beats the best prose-blind minimum "
               f"{best_blind_min}, and both lower bounds clear 0.50 ({lowers})")
    else:
        outcome = "FAILS"
        why = (f"minimum agreement {judge_min}; best prose-blind minimum {best_blind_min} "
               f"({'beaten' if beats_blind else 'NOT beaten'}); lower bounds {lowers} "
               f"(clears: {clears})")
    return {
        "outcome": outcome, "why": why, "agreement_per_stratum": agreement,
        "min_agreement": judge_min, "best_prose_blind_min": best_blind_min,
        "lower_bounds": lowers, "conditions": PRE_REGISTRATION,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    from elicit import Elicitor, positional_bias
    from persona_battery import pairwise_interval
    from personas import PANEL as ALL_PERSONAS

    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))

    panel = tuple(
        persona for persona in ALL_PERSONAS
        if not args.personas or persona.persona_id in args.personas
    )
    if not panel:
        raise SystemExit(f"no personas matched {args.personas}; have "
                         f"{[p.persona_id for p in ALL_PERSONAS]}")

    # `low` is the left slot and `high` the right, so the win rate `compare_pair` reports is
    # P(the judge preferred the higher-conversion side) — agreement with the label, directly.
    schedule: list[tuple[str, str, str, str]] = []
    for stratum in STRATA:
        entries = corpus.get(f"axis_conversion_{stratum}", [])
        for pair in (entries[: args.pairs] if args.pairs else entries):
            schedule.append((stratum, pair["pair_id"], pair["low"], pair["high"]))
    for pair in corpus.get("axis_acclaim", [])[: args.acclaim_pairs or 0]:
        schedule.append(("acclaim", pair["pair_id"], pair["rr"], pair["mol"]))

    planned = len(schedule) * len(panel) * 2
    if planned > args.guard and not args.yes:
        raise SystemExit(f"{planned} calls exceeds the {args.guard} guard; pass --yes")

    report: dict[str, Any] = {
        "protocol": "plan/stage-0-decisions.md §79",
        "judge": {
            "model": args.model, "transport": args.transport,
            "pair_question": args.pair_question,
            "personas": [persona.persona_id for persona in panel],
            "tie_policy": args.tie_policy,
        },
        "corpus_meta": {key: value for key, value in meta.items() if key != "pairs"},
        "planned_calls": planned,
        "prose_blind_baselines": prose_blind(meta),
        "pre_registration": PRE_REGISTRATION,
    }

    every: list[Any] = []
    per_axis: dict[str, list[float]] = {}
    with Elicitor(
        Path(args.cache), model=args.model, spot_model=None, spot_fraction=0.0,
        transport=args.transport, pair_question=args.pair_question, dry_run=args.dry_run,
    ) as elicitor:
        for axis, pair_id, left, right in schedule:
            if not left.strip() or not right.strip() or left.strip() == right.strip():
                continue
            comparisons = elicitor.compare_pair(f"{pair_id}|{axis}", left, right, n=1,
                                                personas=panel)
            every.extend(comparisons)
            values = [
                0.5 if comparison.choice == "neither" else float(comparison.chose_variant)
                for comparison in comparisons
                if not comparison.refused
                and not (comparison.choice == "neither" and args.tie_policy == "drop")
            ]
            if values:
                per_axis.setdefault(axis, []).append(statistics.fmean(values))
        print(f"  elicited {len(every)} comparisons", file=sys.stderr, flush=True)

        report["agreement"] = {
            axis: round(statistics.fmean(values), 4) for axis, values in per_axis.items()
        }
        report["pairs_per_axis"] = {axis: len(values) for axis, values in per_axis.items()}
        report["per_axis_bias"] = {
            axis: positional_bias([c for c in every if c.pair_id.endswith(f"|{axis}")])
            for axis in per_axis
        }
        report["intervals"] = {
            axis: pairwise_interval(
                [c for c in every if c.pair_id.endswith(f"|{axis}")], args.model, args.tie_policy
            )
            for axis in per_axis
        }
        report["positional_bias"] = positional_bias(every)
        report["refused"] = sum(1 for comparison in every if comparison.refused)
        report["comparisons"] = len(every)
        report["verdict"] = verdict(report["agreement"], report["per_axis_bias"],
                                   report["prose_blind_baselines"], report["intervals"])
        report["spend"] = elicitor.spend()
        report["replayed"] = elicitor.replayed
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--build", action="store_true",
                        help="select matched pairs from the shards and exit (needs pyarrow)")
    parser.add_argument("--corpus", default=str(HERE / "corpora" / "taste-benchmark.json"))
    parser.add_argument("--meta", default=str(HERE / "results" / "taste-benchmark-corpus.json"))
    parser.add_argument("--shards", type=int, nargs="+", default=[3, 30])
    parser.add_argument("--limit", type=int, default=0, help="0 reads every chapter in the shards")
    parser.add_argument("--min-words", type=int, default=1500)
    parser.add_argument("--max-words", type=int, default=6000)
    parser.add_argument("--min-views", type=int, default=MIN_VIEWS)
    parser.add_argument("--min-conversion-ratio", type=float, default=MIN_CONVERSION_RATIO)
    parser.add_argument("--max-log-view-gap", type=float, default=MAX_LOG_VIEW_GAP)
    parser.add_argument("--max-log-word-gap", type=float, default=MAX_LOG_WORD_GAP)
    parser.add_argument("--pairs", type=int, default=0,
                        help="0 uses every matched pair in each stratum")
    parser.add_argument("--acclaim-pairs", type=int, default=0)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument("--pair-question", default="preference",
                        choices=("preference", "intensity"))
    parser.add_argument("--personas", nargs="*", default=None,
                        help="persona ids to seat; default is the whole existing panel")
    parser.add_argument("--tie-policy", default="half_win", choices=("half_win", "drop"))
    parser.add_argument("--guard", type=int, default=600)
    parser.add_argument("--cache", default=str(HERE / "results" / "taste-benchmark-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "taste-benchmark.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.build:
        return build(args)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["agreement"], indent=2))
    print(json.dumps({k: v.get("chose_A_rate") for k, v in report["per_axis_bias"].items()},
                     indent=2))
    print(json.dumps({k: v["per_stratum"] for k, v in report["prose_blind_baselines"].items()},
                     indent=2))
    print(json.dumps({k: v for k, v in report["verdict"].items() if k != "conditions"}, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
