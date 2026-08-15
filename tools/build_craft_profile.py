"""Build a craft reference profile from published LitRPG. §10.6's corpus, partially.

Run offline, never from the loop:

    uv run --extra corpus python tools/build_craft_profile.py --out plan/craft-profile.json

**What this supplies and what it does not.** §10.6 asks for a corpus of *good* prose so a
proxy can be tested for whether it separates good from weak. This is not that. It is a corpus
of **published** LitRPG, which gives two things that are worth having and one that is not:

- **A reference distribution.** Every metric in `domain/craft.py` currently reports a number
  with nothing to compare it to. Against this profile the same number becomes "the 99th
  percentile of published LitRPG", which is a *fact* rather than a hypothesis, and §1a.5's
  first bar — "blinded genre readers cannot reliably distinguish accepted chapters from
  published human LitRPG at the same tier" — is a statement about exactly this population.
- **A testable hypothesis for §1a.3 item 6, "absence of AI tells".** Two independent handles
  exist in the corpus and they confound differently, so both are computed: RoyalRoad's
  self-declared `AI-Assisted Content` warning, and *release date* — chapters published before
  2023 predate general LLM availability, which is a cleaner human baseline than "nobody ticked
  the box". A metric that separates these cohorts is measuring something real about machine
  prose. One that does not, is not, and the number says so.
- **Not a quality signal.** The dataset card advertises `overall_score`, `style_score`,
  `story_score`, `grammar_score` and `character_score`; **all five columns are 100% null** in
  the data — verified across two full shards, 68,676 chapters. What is populated is
  engagement: followers, favourites, views, rating *counts*. §1a.1 is explicit that the easy
  metric is the shallow one, and popularity is a function of update cadence, tags, cover art,
  launch timing and an author's existing audience at least as much as of the prose. So
  engagement is recorded in the profile as context and **is never used as a label**.

**No prose is stored.** The output is percentiles and counts. That keeps the artifact small
enough to commit, keeps the repository free of other people's copyrighted fiction, and means
the profile can be checked into a public repo without redistributing the corpus. The dataset
id and revision are recorded so the profile can be rebuilt and disputed.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from litharness.domain.craft import METRICS, band_for, measure

DATASET = "OmniAICreator/RoyalRoad-1.61M"

#: Shards chosen for what they contain rather than at random, and the reason is the whole
#: design: the corpus is ordered so that low shard numbers are recent (2025) and high ones are
#: older (2021-22). One of each gives the pre-LLM baseline and the post-LLM cohort.
DEFAULT_SHARDS = (3, 30)

#: The tag that makes a chapter part of the population this system is trying to write in.
GENRE_TAG = "LitRPG"

#: Chapters released before this predate general LLM availability. A blunt line, and named as
#: one: it does not make a 2022 chapter certainly human, it makes the cohort overwhelmingly so.
PRE_LLM_YEAR = "2023"

AI_WARNING = "AI-Assisted Content"

#: A chapter shorter than this is a note, an author's message, or a stub, and its metrics are
#: noise. Applied to both cohorts equally so it cannot shift the comparison.
MIN_WORDS = 300


def cohort_of(row: dict[str, Any]) -> str | None:
    """Which comparison group this chapter belongs to, or None to skip it."""
    warnings = json.loads(row.get("warnings") or "[]")
    date = row.get("release_datetime") or ""
    year = date[:4]
    declared = AI_WARNING in warnings
    if year and year < PRE_LLM_YEAR:
        # Pre-LLM. A declaration here is almost certainly a later edit to the story's
        # metadata rather than a fact about this chapter, so it is excluded rather than
        # counted either way.
        return None if declared else "human_pre_llm"
    if year >= "2025":
        return "declared_ai_2025" if declared else "undeclared_2025"
    return None


def percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def at(p: float) -> float:
        index = min(len(ordered) - 1, max(0, round(p * (len(ordered) - 1))))
        return round(ordered[index], 6)

    return {
        "p01": at(0.01), "p05": at(0.05), "p25": at(0.25), "p50": at(0.50),
        "p75": at(0.75), "p95": at(0.95), "p99": at(0.99),
        "mean": round(statistics.fmean(ordered), 6),
        "sd": round(statistics.pstdev(ordered), 6) if len(ordered) > 1 else 0.0,
    }


def auc(positive: list[float], negative: list[float]) -> float:
    """Rank AUC: P(a random positive scores above a random negative), ties at half.

    The separation statistic, chosen because it is threshold-free — reporting a single
    accuracy would bake in a cutoff nobody has justified, and §10.4 says a threshold is a
    property of a *calibration*. 0.5 is no separation; the distance from 0.5 is the signal.
    """
    if not positive or not negative:
        return 0.5
    merged = sorted([(v, 1) for v in positive] + [(v, 0) for v in negative])
    index = 0
    rank_sum = 0.0
    while index < len(merged):
        stop = index
        while stop + 1 < len(merged) and merged[stop + 1][0] == merged[index][0]:
            stop += 1
        average = (index + stop) / 2.0 + 1.0
        for position in range(index, stop + 1):
            if merged[position][1] == 1:
                rank_sum += average
        index = stop + 1
    n_pos, n_neg = len(positive), len(negative)
    return round((rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg), 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("plan/craft-profile.json"))
    parser.add_argument("--shards", type=int, nargs="*", default=list(DEFAULT_SHARDS))
    parser.add_argument("--limit", type=int, default=0, help="chapters per shard; 0 = all")
    args = parser.parse_args()

    try:
        import pyarrow.parquet as pq
        from huggingface_hub import hf_hub_download
    except ImportError:  # pragma: no cover - the extra is optional by design
        print(
            "this tool needs the corpus extra: uv sync --extra corpus", file=sys.stderr
        )
        return 2

    samples: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    #: The same samples again, split by the chapter's own length. Keyed
    #: (cohort, band) -> metric_id -> values.
    banded: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    band_counts: dict[tuple[str, str], int] = defaultdict(int)
    engagement: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    stories: dict[str, set[int]] = defaultdict(set)
    revision = "unknown"

    columns = ["tags", "warnings", "release_datetime", "text", "fiction_id", "followers"]
    for shard in args.shards:
        path = hf_hub_download(
            DATASET, f"data/train-{shard:05d}-of-00047.parquet", repo_type="dataset"
        )
        revision = Path(path).parent.name if revision == "unknown" else revision
        table = pq.read_table(path, columns=columns)
        rows = table.to_pylist()
        if args.limit:
            rows = rows[: args.limit]
        print(f"shard {shard}: {len(rows)} chapters", file=sys.stderr)
        for row in rows:
            if GENRE_TAG not in json.loads(row.get("tags") or "[]"):
                continue
            cohort = cohort_of(row)
            if cohort is None:
                continue
            text = row.get("text") or ""
            words = len(text.split())
            if words < MIN_WORDS:
                continue
            counts[cohort] += 1
            stories[cohort].add(int(row["fiction_id"]))
            engagement[cohort].append(float(row.get("followers") or 0))
            band = band_for(words)
            if band is not None:
                band_counts[(cohort, band)] += 1
            for metric in measure(text):
                samples[cohort][metric.metric_id].append(metric.value)
                if band is not None:
                    banded[(cohort, band)][metric.metric_id].append(metric.value)

    metric_ids = [fn("x. y.").metric_id for fn in METRICS]
    profile: dict[str, Any] = {
        "source": {
            "dataset": DATASET,
            "revision": revision,
            "shards": args.shards,
            "genre_tag": GENRE_TAG,
            "min_words": MIN_WORDS,
        },
        "disclaimer": (
            "Published LitRPG, not good LitRPG. The dataset's five score columns "
            "(overall/style/story/grammar/character) are 100% null in the data despite being "
            "advertised on the card; engagement is recorded as context and is never used as a "
            "label (§1a.1). This profile anchors a metric to a population. It is not evidence "
            "that any metric tracks quality, which §1a.4 says only human judgment supplies."
        ),
        "cohorts": {
            name: {
                "chapters": counts[name],
                "stories": len(stories[name]),
                "followers_median": (
                    round(statistics.median(engagement[name]), 1) if engagement[name] else 0.0
                ),
                "metrics": {
                    metric_id: percentiles(samples[name][metric_id])
                    for metric_id in metric_ids
                },
                # The stratified ladders, and the only ones `percentile_of` will read. The
                # pooled block above stays because it describes the cohort, but a pooled
                # percentile answers a question nobody asked: the corpus median chapter is
                # over twice a scene target, and `opening_shape_repetition` falls
                # monotonically with length, so pooling put a 900-word scene at the 50th
                # percentile where its own band says the 19th.
                "bands": {
                    band: {
                        "chapters": band_counts[(name, band)],
                        "metrics": {
                            metric_id: percentiles(banded[(name, band)][metric_id])
                            for metric_id in metric_ids
                        },
                    }
                    for band in sorted(
                        {key[1] for key in band_counts if key[0] == name},
                        key=lambda label: int(label.split("-")[0]),
                    )
                },
            }
            for name in sorted(counts)
        },
        "separation": {
            metric_id: {
                # The comparison that isolates the *declaration*: same platform, same year,
                # same genre tag, differing only in whether the author ticked the box. This
                # is the one to read.
                "declared_ai_vs_undeclared_2025": auc(
                    samples["declared_ai_2025"][metric_id],
                    samples["undeclared_2025"][metric_id],
                ),
                # The two era comparisons, kept because reading them together is what exposes
                # the confound: if undeclared-2025 separates from pre-LLM as strongly as
                # declared-AI does, the metric is detecting the year rather than the machine.
                "declared_ai_2025_vs_human_pre_llm": auc(
                    samples["declared_ai_2025"][metric_id],
                    samples["human_pre_llm"][metric_id],
                ),
                "undeclared_2025_vs_human_pre_llm": auc(
                    samples["undeclared_2025"][metric_id],
                    samples["human_pre_llm"][metric_id],
                ),
            }
            for metric_id in metric_ids
        },
        "separation_note": (
            "Rank AUC. 0.5 is no separation; distance from 0.5 is the signal and the "
            "direction says which cohort scores higher. Read "
            "`declared_ai_vs_undeclared_2025` first — it holds the era fixed. The era "
            "comparisons are the control: where undeclared-2025 separates from pre-LLM as "
            "strongly as declared-AI does, the metric is measuring the year, not the "
            "machine. Chapters cluster by story (a few hundred stories supply thousands of "
            "chapters), so the effective sample is the story count, not the chapter count. "
            "None of these is evidence about craft; §1a.4 says only human judgment is."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # `newline="\n"` because this is a committed artifact and the tool runs on Windows too;
    # without it the profile lands with CRLF and every rebuild is a whole-file diff.
    args.out.write_text(
        json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(f"wrote {args.out}", file=sys.stderr)
    for name, data in profile["cohorts"].items():
        print(f"  {name:<20} {data['chapters']:>6} chapters, {data['stories']:>5} stories",
              file=sys.stderr)
    for metric_id, seps in profile["separation"].items():
        print(f"  {metric_id:<40} {seps}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
