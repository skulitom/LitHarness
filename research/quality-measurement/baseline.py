"""The incumbents' numbers, on the units a challenger will be scored on.

A new craft metric is only interesting against a baseline, and this project does not have one
in a usable form: `plan/craft-profile.json` reports the four refuted metrics as *cohort
percentiles* over RoyalRoad, which cannot be compared against a challenger measured per
chapter within a story. So this recomputes all four on the exact units the experiments use.

Two baselines, because a challenger can beat the wrong one:

- **`--within-story`** — the four metrics' chapter-to-chapter variation inside one story,
  against `position`. Every refuted proxy was measured *between* cohorts; measuring the
  incumbents within a story is what makes "the challenger explains variance the incumbents
  do not" a checkable sentence rather than a claim.
- **`--fixture`** — the four metrics over the six golden mystery scenes, against the two
  known anchors (scene 6 is the dramatic peak, scene 1 the floor). Nobody has recorded what
  the incumbents do on that ordering. If one of them happens to rank it right way up, a
  challenger that also does has shown nothing.

Also computes **word count** as a fifth incumbent, deliberately. §1a.1 warns about the metric
that is easy because it is shallow, and length correlates with almost everything; a challenger
that does not beat raw length is measuring length.

    python research/quality-measurement/baseline.py --fixture --within-story
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
# Contracts by path, not by install. Two interpreters are in play — LitHarness's own venv for
# CPU work and MirrorBench's for anything touching torch — and only the first has the package
# installed. Adding the sibling checkout's source root makes these scripts runnable under
# either, which matters because a GPU experiment still needs `measure` for its baseline.
sys.path.insert(0, str(Path("C:/DEV/litharness-contracts/src")))

from corpus_io import Unit, by_story, fixture_scenes, mol_chapters, royalroad_chapters

from litharness.domain.craft import measure


def spearman(xs: list[float], ys: list[float]) -> tuple[float, int]:
    """Rank correlation and n. Rank-based because none of these metrics is remotely normal."""
    n = len(xs)
    if n < 3:
        return float("nan"), n

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            average = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = average
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den = (
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    ) ** 0.5
    return (num / den if den else float("nan")), n


def metrics_of(unit: Unit) -> dict[str, float]:
    row = {metric.metric_id: metric.value for metric in measure(unit.text)}
    # The shallow incumbent, included so a challenger has to beat it explicitly.
    row["baseline.word_count"] = float(unit.words)
    return row


def fixture_baseline() -> dict[str, object]:
    """What the incumbents say about the one ordering whose ground truth is known.

    Reported as the rank of scene 6 and scene 1 rather than a correlation: the fixture supplies
    two anchors on a six-item list, not a full ordering, and a Spearman against a made-up
    ordering of the middle four would be inventing ground truth.
    """
    scenes = fixture_scenes("mystery")
    rows = {scene.position: metrics_of(scene) for scene in scenes}
    out: dict[str, object] = {"scenes": {str(k): v for k, v in rows.items()}}
    verdicts = {}
    for metric_id in next(iter(rows.values())):
        values = [(rows[position][metric_id], position) for position in sorted(rows)]
        # Rank 1 = highest value. Direction is unknown for every one of these metrics, which
        # is itself the point: with no calibrated direction, "ranks it right way up" is not a
        # question the incumbents can even be asked. Both directions are reported.
        descending = [p for _, p in sorted(values, key=lambda pair: -pair[0])]
        verdicts[metric_id] = {
            "order_high_to_low": descending,
            "scene6_rank_desc": descending.index(6) + 1,
            "scene1_rank_desc": descending.index(1) + 1,
            # The fixture claim: scene 6 (peak) should separate from scene 1 (floor). A metric
            # that puts them adjacent has not distinguished the two anchors in either
            # direction, which is a cleaner statement than picking a direction post hoc.
            "separates_anchors": abs(descending.index(6) - descending.index(1)) >= 3,
        }
    out["verdicts"] = verdicts
    return out


def within_story_baseline(units: list[Unit], label: str) -> dict[str, object]:
    """Incumbent variation inside one work, against position and length.

    `position` is here because it is the confound that killed the comment-count proxy, and a
    challenger correlating with position is at risk of the same death. Recording what the
    incumbents do against position is what makes that comparison possible.
    """
    rows = [metrics_of(unit) for unit in units]
    positions = [float(unit.position) for unit in units]
    lengths = [float(unit.words) for unit in units]
    out: dict[str, object] = {"work": label, "n": len(units)}
    stats = {}
    for metric_id in rows[0]:
        values = [row[metric_id] for row in rows]
        rho_pos, n = spearman(values, positions)
        rho_len, _ = spearman(values, lengths)
        stats[metric_id] = {
            "mean": round(statistics.fmean(values), 6),
            "sd": round(statistics.pstdev(values), 6),
            # Coefficient of variation: how much does this metric move at all inside one
            # story? A metric that is flat within a work cannot rank scenes within a work,
            # whatever it does between cohorts.
            "cv_within_work": round(
                statistics.pstdev(values) / statistics.fmean(values), 4
            ) if statistics.fmean(values) else None,
            "rho_vs_position": round(rho_pos, 4),
            "rho_vs_length": round(rho_len, 4),
            "n": n,
        }
    out["metrics"] = stats
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--within-story", action="store_true")
    parser.add_argument("--royalroad-stories", type=int, default=5)
    parser.add_argument(
        "--out", type=Path,
        default=Path("research/quality-measurement/results/baseline.json"),
    )
    args = parser.parse_args()

    report: dict[str, object] = {}

    if args.fixture:
        report["fixture_mystery"] = fixture_baseline()
        verdicts = report["fixture_mystery"]["verdicts"]  # type: ignore[index]
        print("golden mystery fixture — do the incumbents separate the two known anchors?")
        for metric_id, verdict in verdicts.items():
            print(
                f"  {metric_id:<40} order(high-to-low)={verdict['order_high_to_low']}  "
                f"scene6=#{verdict['scene6_rank_desc']} scene1=#{verdict['scene1_rank_desc']}  "
                f"separates={verdict['separates_anchors']}"
            )

    if args.within_story:
        mol = mol_chapters()
        report["within_story_mol"] = within_story_baseline(mol, "mother-of-learning")
        print(f"\nwithin-story: Mother of Learning, {len(mol)} chapters")
        for metric_id, stats in report["within_story_mol"]["metrics"].items():  # type: ignore[index]
            print(
                f"  {metric_id:<40} cv={stats['cv_within_work']}  "
                f"rho_pos={stats['rho_vs_position']:+.4f}  rho_len={stats['rho_vs_length']:+.4f}"
            )

        stories = by_story(list(royalroad_chapters(limit=6000)), min_chapters=12)
        picked = sorted(stories, key=lambda k: -len(stories[k]))[: args.royalroad_stories]
        rr = []
        print(f"\nwithin-story: RoyalRoad, {len(picked)} stories")
        for work_id in picked:
            chapters = stories[work_id]
            # Positions are recovered by release order inside the story; the shards are not
            # story-ordered, so this is the only position information available.
            ordered = [
                replace(chapter, position=index)
                for index, chapter in enumerate(chapters, start=1)
            ]
            entry = within_story_baseline(ordered, f"rr:{work_id}")
            rr.append(entry)
            cohort = chapters[0].meta.get("cohort")
            tricolon = entry["metrics"]["craft.tricolon_rate.v0"]  # type: ignore[index]
            print(
                f"  {work_id:<12} n={len(chapters):>3} {cohort:<18} "
                f"tricolon cv={tricolon['cv_within_work']} "
                f"rho_pos={tricolon['rho_vs_position']:+.4f}"
            )
        report["within_story_royalroad"] = rr

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
