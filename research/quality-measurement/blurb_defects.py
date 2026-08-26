"""Count the defects the operator keeps naming, and check the counter against the market.

**Why this exists, in the operator's words, 2026-08-26:** *"I feel like I keep giving the same
feedback back and nothing changes otherwise."* That is correct and it is a process defect rather
than a taste disagreement. Five defect classes have been named repeatedly across three sessions
— unexplained jargon, vagueness, over-specificity, sentences that do not connect, titles that
describe rather than name — and **not one of them has a counter**. So each one has to be caught
by a person reading, every time, which is exactly the loop §126 exists to remove.

**The instrument is not new and that is the point.** `application/comprehension.py` already asks
four readers to quote every word used as if they already knew it; `plan/handoff-listing-loop.md`
set it aside for blurbs — *"the comprehension screen over-flags a listing. About a third of what
it quotes as uncashable, the same reader also files as a hook. Calibration unproven for blurbs."*
Unproven, not refuted, and there was no way to prove it. There is now: 42 published serials above
a thousand followers and 1,151 below twenty-five, from the same shards, are an external label
this counter can be checked against.

### The reading, fixed before the run

Let **U** be the mean count of uncashable terms per blurb.

| | reading |
| --- | --- |
| LOW - HIGH >= 0.5, intervals disjoint | the counter tracks the market's own
  outcome, and its count on our listings is admissible as a located defect |
| the intervals overlap | uncalibrated for blurbs, as the handoff said. It may be
  reported beside a listing and may gate nothing |
| HIGH > LOW | it counts something the market rewards. Withdrawn for blurbs, and
  the handoff's caution becomes a refutation |

**Nothing here gates anything and nothing here ranks.** The count is arithmetic over what four
readers quoted; no model is asked whether a blurb is good, and there is no field in which one
could say so.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from litharness.application import comprehension  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

DERIVED = HERE / "derived"
RESULTS = HERE / "results"


def screen(registry: Any, text: str) -> dict[str, Any]:
    """Four readers over one blurb. Returns the count and what each one could not cash."""
    answers: dict[str, Any] = {}
    for reader in comprehension.READERS:
        request = comprehension.render_reader_request(reader, text)
        try:
            result, _ = registry.complete(request)
        except Exception as error:  # an outage is a fact about the day, not about the blurb
            print(f"    {reader.reader_id}: {str(error)[:100]}", file=sys.stderr)
            continue
        if isinstance(result.parsed, dict):
            answers[reader.reader_id] = result.parsed
    outcome = comprehension.ScreenResult.of(answers)
    block = outcome.to_jsonable()
    return {
        "undefined_total": block.get("undefined_total"),
        "answered": len(answers),
        "words": sorted(
            {
                str(word).strip().casefold()
                for answer in answers.values()
                for word in (answer.get("undefined_words") or [])
                if str(word).strip()
            }
        ),
    }


def band(values: list[float]) -> tuple[float, float, float]:
    """Mean and a normal-approximation 95% interval. Wide at this n and reported as such."""
    if not values:
        return (float("nan"),) * 3
    mean = statistics.mean(values)
    if len(values) < 2:
        return (mean, mean, mean)
    half = 1.96 * statistics.stdev(values) / (len(values) ** 0.5)
    return (round(mean - half, 2), round(mean, 2), round(mean + half, 2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--high", default=str(DERIVED / "rivals.json"))
    parser.add_argument("--low", default=str(DERIVED / "rivals-low.json"))
    parser.add_argument("--ours", nargs="*", default=[])
    parser.add_argument("--each", type=int, default=6, help="blurbs per tier")
    parser.add_argument("--out", type=Path, default=RESULTS / "blurb-defects.json")
    args = parser.parse_args(argv)

    high = sorted(
        json.loads(Path(args.high).read_text(encoding="utf-8")),
        key=lambda row: -int(row["followers"] or 0),
    )[: args.each]
    low = json.loads(Path(args.low).read_text(encoding="utf-8"))[: args.each]
    registry = build_default_registry()

    tiers: dict[str, list[dict[str, Any]]] = {}
    for name, rows in (("high", high), ("low", low)):
        tiers[name] = []
        for row in rows:
            got = screen(registry, f"{row['title']}\n\n{row['listing']}")
            got["source"] = row["source"]
            got["followers"] = row["followers"]
            tiers[name].append(got)
            print(f"  {name:5} {row['followers']:>6} followers  "
                  f"uncashable {got['undefined_total']}  {got['words'][:6]}")

    tiers["ours"] = []
    for raw in args.ours:
        bundle = json.loads(Path(raw).read_text(encoding="utf-8"))
        for key in ("draft", "listing"):
            if not bundle.get(key):
                continue
            page = f"{bundle.get('title') or ''}\n\n{bundle[key]}".strip()
            got = screen(registry, page)
            got["source"] = f"{Path(raw).parent.name}:{key}"
            tiers["ours"].append(got)
            print(f"  {'ours':5} {got['source']:>20}  uncashable {got['undefined_total']}  "
                  f"{got['words'][:6]}")

    report = {
        name: {
            "n": len(rows),
            "mean_interval": band([float(r["undefined_total"] or 0) for r in rows]),
            "counts": [r["undefined_total"] for r in rows],
            "rows": rows,
        }
        for name, rows in tiers.items()
        if rows
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    for name, block in report.items():
        low_b, mean, high_b = block["mean_interval"]
        print(f"  {name:5} n={block['n']}  uncashable/blurb {mean}  95% [{low_b}, {high_b}]")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
