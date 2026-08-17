"""Does the revealed-preference label separate anything a shallow incumbent does not?

**The question that has to be answered before §4.3, not after it.** `plan/craft-corpus.md` §4.1
proposes calibrating craft proxies against `conversion = followers / total_views`, and §4.3
proposes a model critic scored against the same label — "the only instrument on this list that
could reach §1a.3 items 1-4". Both inherit one untested assumption: that the label separates
*prose* from prose. It has never been checked. `results/` holds `baseline.json` and nothing
else, and `corpus_io.royalroad_chapters` has computed `conversion` since it was written with no
consumer.

**Why this and not the critic first.** A critic scored against a label that separates nothing is
uninterpretable, and a critic scored against a label that a prose-blind baseline separates just
as well is `tricolon_rate` in a fourth costume — 0.629 that dies to a control of 0.606. The
label side is CPU-only, runs on the two cached shards, and can refute the whole direction in an
afternoon. BRIEF.md's closing rule is that refuting is worth as much as confirming.

**Three controls, computed in the same pass, because §2 makes that a rule.**

1. **Prose-blind baselines.** `log(total_views)`, `followers`, chapters-in-shard, and mean
   chapter length read no prose at all. If one of them separates conversion deciles as well as
   a craft metric, the craft metric is measuring story size, and §3's "Spearman rho = 0.438
   against raw followers, so it is not popularity restated" is a weaker guarantee than it
   sounds - rho = 0.438 leaves plenty of room for a size effect to dominate a decile split.
2. **Era.** The control that killed `tricolon_rate`. Reported for every metric against the same
   stories, so a metric that separates the year rather than the reader is visible in the row.
3. **A permuted-label null at this exact n.** The deciles are small; an AUC of 0.60 on 30
   stories a side is not obviously outside chance, and asserting it is how a project talks
   itself into a finding. The 5th/95th percentile of AUC under 400 shuffles is the band any
   headline has to clear.

**The unit is the story, not the chapter, and that is forced.** The label is story-level
(`plan/craft-corpus.md` §4.1: "a per-scene proxy is validated against an outcome one level up
… it argues for chapter-aggregated metrics per story"). Scoring chapters and testing chapters
would count one story's engagement once per chapter and manufacture significance out of chapter
counts.

Reads the two cached shards, writes numbers, redistributes no prose.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))

from corpus_io import royalroad_chapters  # noqa: E402
from evaluate import auc  # noqa: E402

from litharness.domain.craft import (  # noqa: E402
    dialogue_ratio,
    opening_shape_repetition,
    sentence_length_variation,
    tricolon_rate,
)

#: The four instrumented craft metrics, all four already refuted as AI-tell detectors
#: (`plan/craft-corpus.md` §2). Refuted *as AI-tell detectors* is a different claim from
#: refuted against engagement, and nobody has asked them this question.
CRAFT = {
    "dialogue_ratio": lambda text: dialogue_ratio(text).value,
    "opening_shape_repetition": lambda text: opening_shape_repetition(text).value,
    "sentence_length_cv": lambda text: sentence_length_variation(text).value,
    "tricolon_rate": lambda text: tricolon_rate(text).value,
    # §1a.1's shallow incumbent, and the one that decides whether the rest is interpretable.
    "word_count": lambda text: float(len(text.split())),
}

#: Read no prose whatsoever. Any of these matching a craft metric's AUC is the finding.
#:
#: **`followers` and `log_views` are the label's own numerator and denominator, and are
#: reported as diagnostics rather than as controls.** `conversion = followers / total_views`,
#: so neither is independent of the split; what they answer is *which component drives it*.
#: A `followers` AUC near 1.0 says the top conversion decile is simply the popular stories —
#: which is §1a.1's warning arriving as a measurement, and would mean §3's "rho = 0.438 against
#: raw followers, so it is not popularity restated" does not survive a decile split even
#: though it holds across the middle of the distribution. `chapters_seen` and `mean_words` are
#: the honest controls: neither appears in the label's arithmetic.
PROSE_BLIND = ("chapters_seen", "mean_words", "log_views", "followers")

#: The subset of `PROSE_BLIND` that is a control rather than a diagnostic — the verdict reads
#: only these, so a mechanically-related column cannot decide the experiment.
INDEPENDENT_BLIND = ("chapters_seen", "mean_words")


def summarise_stories(
    *, shards: tuple[int, ...], min_chapters: int, min_views: float, limit: int
) -> list[dict[str, Any]]:
    """One row per story: its label, its cohort, and every metric averaged over its chapters."""
    stories: dict[str, dict[str, Any]] = {}
    for unit in royalroad_chapters(shards=shards, limit=limit):
        meta = unit.meta
        if meta.get("conversion") is None:
            continue
        row = stories.setdefault(
            unit.work_id,
            {
                "work_id": unit.work_id,
                "conversion": float(meta["conversion"]),
                "followers": float(meta["followers"]),
                "total_views": float(meta["total_views"]),
                "cohorts": [],
                "scores": {name: [] for name in CRAFT},
            },
        )
        row["cohorts"].append(meta["cohort"])
        for name, scorer in CRAFT.items():
            # A metric that dies on one chapter is data about that metric, not a reason to
            # abandon 13,000 others; the story is dropped later if it ends up short a column.
            with contextlib.suppress(Exception):
                row["scores"][name].append(float(scorer(unit.text)))

    out: list[dict[str, Any]] = []
    for row in stories.values():
        chapters = len(row["cohorts"])
        if chapters < min_chapters or row["total_views"] < min_views:
            continue
        means = {
            name: statistics.fmean(values)
            for name, values in row["scores"].items()
            if values
        }
        if len(means) < len(CRAFT):
            continue
        # The story's cohort is its chapters' majority. A story straddling the 2023 line is
        # dropped rather than assigned, because the era control is the point.
        distinct = set(row["cohorts"])
        cohort = row["cohorts"][0] if len(distinct) == 1 else None
        out.append(
            {
                "work_id": row["work_id"],
                "conversion": row["conversion"],
                "cohort": cohort,
                "chapters_seen": float(chapters),
                "log_views": math.log10(max(row["total_views"], 1.0)),
                "followers": row["followers"],
                "mean_words": means["word_count"],
                **means,
            }
        )
    return out


def deciles(rows: list[dict[str, Any]], key: str = "conversion") -> tuple[list, list]:
    """Top and bottom decile by the label. §4.4's own selection rule."""
    ordered = sorted(rows, key=lambda row: row[key])
    size = max(1, len(ordered) // 10)
    return ordered[-size:], ordered[:size]


def separation(top: list, bottom: list, name: str) -> float:
    return auc([row[name] for row in top], [row[name] for row in bottom])


def permuted_band(
    rows: list[dict[str, Any]], name: str, *, draws: int = 400, seed: int = 11
) -> tuple[float, float]:
    """5th/95th percentile of AUC when the label is shuffled — the null at this exact n."""
    rng = random.Random(seed)
    labels = [row["conversion"] for row in rows]
    values = [row[name] for row in rows]
    aucs = []
    for _ in range(draws):
        rng.shuffle(labels)
        paired = sorted(zip(labels, values, strict=True))
        size = max(1, len(paired) // 10)
        aucs.append(
            auc([v for _, v in paired[-size:]], [v for _, v in paired[:size]])
        )
    aucs.sort()
    low = aucs[int(0.05 * len(aucs))]
    high = aucs[min(len(aucs) - 1, int(0.95 * len(aucs)))]
    return round(low, 4), round(high, 4)


def era_auc(rows: list[dict[str, Any]], name: str) -> float:
    """The tricolon control: does this metric separate the year instead of the reader?"""
    recent = [row[name] for row in rows if row["cohort"] == "undeclared_2025"]
    older = [row[name] for row in rows if row["cohort"] == "human_pre_llm"]
    return auc(recent, older) if recent and older else float("nan")


def report(rows: list[dict[str, Any]], *, draws: int) -> dict[str, Any]:
    top, bottom = deciles(rows)
    names = [*CRAFT, *PROSE_BLIND]
    table = []
    for name in names:
        low, high = permuted_band(rows, name, draws=draws)
        headline = separation(top, bottom, name)
        table.append(
            {
                "metric": name,
                "reads_prose": name in CRAFT,
                "conversion_auc": headline,
                "null_p05": low,
                "null_p95": high,
                # The only column that decides anything: a headline inside its own null band
                # is not a finding, whatever it looks like.
                "outside_null": not (low <= headline <= high),
                "era_auc": round(era_auc(rows, name), 4),
            }
        )

    best_prose = max(
        (row for row in table if row["reads_prose"]),
        key=lambda row: abs(row["conversion_auc"] - 0.5),
    )
    # Only the independent baselines may decide the verdict. `followers` and `log_views` are
    # in the label's own arithmetic and would win by construction.
    best_blind = max(
        (row for row in table if row["metric"] in INDEPENDENT_BLIND),
        key=lambda row: abs(row["conversion_auc"] - 0.5),
    )
    components = {
        row["metric"]: row["conversion_auc"]
        for row in table
        if row["metric"] in ("followers", "log_views")
    }
    return {
        "stories": len(rows),
        "decile_size": len(top),
        "cohorts": {
            cohort: sum(1 for row in rows if row["cohort"] == cohort)
            for cohort in {row["cohort"] for row in rows}
        },
        "permutation_draws": draws,
        "table": table,
        "verdict": _verdict(best_prose, best_blind),
        "best_prose_metric": best_prose["metric"],
        "best_prose_auc": best_prose["conversion_auc"],
        "best_independent_blind_metric": best_blind["metric"],
        "best_independent_blind_auc": best_blind["conversion_auc"],
        # Diagnostic, not control: how much of the decile split is each half of the ratio.
        "label_components": components,
        # The rescue, computed whether or not the unstratified result needs it — §2's rule is
        # that the control goes in the same pass, and a rescue run only after a bad headline
        # is a rescue nobody can trust.
        "stratified_by_followers": stratified(rows, by="followers"),
        "stratified_by_length": stratified(rows, by="mean_words"),
    }


def stratified(rows: list[dict[str, Any]], *, by: str, bands: int = 3) -> dict[str, Any]:
    """Decile AUC computed *inside* strata of a confound, which is the only rescue available.

    **This is the measurement that decides whether an unstratified prose-blind win is fatal.**
    If `followers` separates the conversion deciles overall but the craft metrics separate them
    *within* a follower band, the label carries prose information that story size was masking.
    If they do not, the unstratified result stands and the label is size.

    Costs sample size, and says so: each band gets its own decile split, so a 354-story table
    in three bands is three 118-story splits with 11 a side. The per-band AUCs are pooled by
    weighting on band size, and `min_band` is reported so a pooled number computed over bands
    too small to split is visible rather than implied.
    """
    ordered = sorted(rows, key=lambda row: row[by])
    size = max(1, len(ordered) // bands)
    strata = [ordered[i : i + size] for i in range(0, len(ordered), size)][:bands]
    out: dict[str, Any] = {"by": by, "bands": bands, "min_band": min(len(s) for s in strata)}
    pooled: dict[str, float] = {}
    for name in CRAFT:
        weighted, total = 0.0, 0
        per_band = []
        for stratum in strata:
            if len(stratum) < 20:
                continue
            top, bottom = deciles(stratum)
            value = separation(top, bottom, name)
            per_band.append(round(value, 4))
            weighted += value * len(stratum)
            total += len(stratum)
        pooled[name] = round(weighted / total, 4) if total else float("nan")
        out.setdefault("per_band", {})[name] = per_band
    out["pooled_auc"] = pooled
    return out


def _verdict(best_prose: dict[str, Any], best_blind: dict[str, Any]) -> str:
    """What the numbers license saying, and nothing more.

    Written as a function so the reading is committed before the numbers are seen, which is
    the discipline every entry in the refutation ledger was written after failing.
    """
    prose_margin = abs(best_prose["conversion_auc"] - 0.5)
    blind_margin = abs(best_blind["conversion_auc"] - 0.5)
    if not best_prose["outside_null"]:
        return (
            "NO SEPARATION. The best prose-reading metric is inside its own permuted-label "
            "null band, so this label does not separate prose at story grain at this n. A "
            "model critic scored against it would produce an uninterpretable number; §4.3 "
            "needs a different label or a larger sample before it is worth running."
        )
    if blind_margin >= prose_margin:
        return (
            "SEPARATION IS PROSE-BLIND. A baseline that reads no prose separates the deciles "
            "at least as well as the best craft metric, so the label is carrying story size "
            "rather than writing. Any §4.3 critic must take the prose-blind baseline as a "
            "covariate from line one, and must beat it rather than beat chance."
        )
    return (
        "PROSE SEPARATES, PROVISIONALLY. The best prose-reading metric is outside its null "
        "band and beats every prose-blind baseline. Read the era column before believing it: "
        "a metric whose era AUC matches its conversion AUC is separating the year. This is "
        "necessary and not sufficient for §4.3."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", default="3,30")
    parser.add_argument("--min-chapters", type=int, default=3)
    parser.add_argument("--min-views", type=float, default=1000.0)
    parser.add_argument("--limit", type=int, default=0, help="0 = every LitRPG chapter")
    parser.add_argument("--draws", type=int, default=400)
    parser.add_argument("--out", type=Path, default=HERE / "results" / "conversion.json")
    args = parser.parse_args()

    rows = summarise_stories(
        shards=tuple(int(s) for s in args.shards.split(",")),
        min_chapters=args.min_chapters,
        min_views=args.min_views,
        limit=args.limit,
    )
    if len(rows) < 40:
        raise SystemExit(
            f"only {len(rows)} stories survive the filters; a decile split needs more. "
            "Lower --min-chapters or --min-views, or add shards."
        )
    result = report(rows, draws=args.draws)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"{result['stories']} stories, decile {result['decile_size']} a side")
    print(f"cohorts: {result['cohorts']}\n")
    print(
        f"{'metric':<26} {'prose':>6} {'conv_auc':>9} {'null_p05':>9} {'null_p95':>9} "
        f"{'outside':>8} {'era_auc':>8}"
    )
    for row in result["table"]:
        print(
            f"{row['metric']:<26} {row['reads_prose']!s:>6} "
            f"{row['conversion_auc']:>9.4f} {row['null_p05']:>9.4f} "
            f"{row['null_p95']:>9.4f} {row['outside_null']!s:>8} {row['era_auc']:>8.4f}"
        )
    for key in ("stratified_by_followers", "stratified_by_length"):
        block = result[key]
        print(
            f"\nwithin {block['by']} bands (n={block['bands']}, "
            f"smallest band {block['min_band']}): pooled decile AUC"
        )
        for name, value in block["pooled_auc"].items():
            print(f"  {name:<26} {value:>7}   per band {block['per_band'][name]}")

    print(f"\n{result['verdict']}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
