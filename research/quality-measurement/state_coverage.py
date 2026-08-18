"""Does the state record track the quantity the story actually charges people in?

§74's first defect, in the form that survives the two proxies which already died on it. A human
read the book and said the stats were monotone and meaningless — and the sharper version of that
complaint is not about variance at all. `The Toll Road` prices its tolls in **days off a man's
remaining life**: 7, 9, 5 and 6 days charged across ten scenes. That is the quantity with unusual
purchase on this world, it was invented by the premise, and the `[STATUS]` block tracks generic
HP / MP / Gold beside it and never once shows the debt or the days left. The interesting number
exists in the prose and is absent from the record.

**Two proxies already died here and this module is shaped by how.** `progression_cost` was
satisfied by inserting a token gold decrement beside each level-up — the cheapest repair that
satisfies it *is the disease*. `silent_ledger` fires on the fixture's best prose, because the
only way to satisfy it is to push prose toward machine register. Both measured **annotation
density**: how much ledger there is. Neither could tell a ledger that tracks the story from one
that tracks nothing, because density is the same either way.

So this measures *correspondence*, not density: the set of units the prose charges people in,
against the set of units the record keeps. A book that tracks nothing scores zero and so does a
book that tracks ten things none of which anyone pays. Padding the ledger cannot raise it — the
only repair that does is tracking the thing the story charges, which is the defect itself rather
than a proxy for it. That puts it in `scene_echo`'s class from §2 Pass 5: mechanically checkable,
claiming nothing about quality.

**The human control is computed in the same pass and it can kill this outright.** If published
LitRPG chapters score near zero on cost coverage too, then authors routinely charge in units they
do not track, the measure describes the genre rather than a defect, and it is refuted before it
is used — which is precisely how `tricolon_rate` should have been read the first time. §2's
first method rule, applied to a metric this file wants to be true.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

#: Words whose presence near a quantity means somebody is being charged. Deliberately about
#: *transaction* rather than about change: "he walked 7 miles" is a quantity and not a cost, and
#: a lexicon that caught it would score travelogues as economies.
_COST = re.compile(
    r"\b(?:toll|tolls|paid|pays|pay|cost|costs|owe|owes|owed|debt|debts|price|priced|prices|"
    r"charge|charged|charges|spend|spends|spent|fee|fees|levy|due|forfeit|deduct|deducted|"
    r"balance|ledger|account|purchase|bought|buy|sell|sold|wager|stake|staked)\b", re.I)

#: A quantity and the unit it is counted in. The unit is what gets compared with the record.
_QUANTITY = re.compile(r"\b(\d[\d,]*)\s+([a-z][a-z-]{2,})\b", re.I)

#: Field names inside the system voice, in the three shapes this genre actually uses.
#:
#: **The first version of this recognised only our own format and that made the control
#: vacuous.** `_STATUS_LINE` alone matched a bracketed `[STATUS]` tag, which is what `The Toll
#: Road` emits and what **0.0% of 1,200 human RoyalRoad chapters** contain. Every human chapter
#: therefore had an empty tracked set and scored zero coverage by construction, and the run
#: reported the measure REFUTED on a control that could not have passed. Published LitRPG writes
#: its sheets as `Name: Dix` / `Level: 0` line runs and as `[ Strength : 0.1 ( Tier 0 ) ]`
#: bracket runs; both are read here now.
_STATUS_LINE = re.compile(r"^.*\[(?:STATUS|STATS|SHEET|CHARACTER)\].*$", re.MULTILINE)
_FIELD = re.compile(
    r"([A-Za-z][A-Za-z ]{1,18}?)\s*[:=]?\s*([\d?]+(?:\s*/\s*[\d?]+)?)(?=\s*\||\s*$)"
)
#: `Label: 12`, `[ Label : 0.1 ...]`, `Label - 12/30`. Anchored to a short line so ordinary prose
#: containing a colon does not enter, and the label is capped at four words for the same reason.
_SHEET_FIELD = re.compile(
    r"^[\s\[|>*_-]*([A-Za-z][A-Za-z '-]{1,28}?)\s*[:=]\s*\[?\s*([\d?]+(?:[.,]\d+)?"
    r"(?:\s*/\s*[\d?]+)?)",
    re.MULTILINE,
)

#: Units that are never a game resource however they are phrased — they are how prose counts
#: ordinary nouns. Without this, "three men" and "two doors" enter as tracked-worthy currencies.
_NOT_A_RESOURCE = frozenset({
    "men", "man", "women", "woman", "people", "steps", "paces", "feet", "inches", "miles",
    "times", "others", "more", "hours", "minutes", "seconds", "years", "months", "weeks",
    "of", "and", "the", "them", "him", "her", "it", "was", "were", "had", "has",
})

#: Words that license a tracked value going up. Absent them, an increase is unexplained.
_LICENSE = re.compile(
    r"\b(?:heal\w*|rest\w*|slept|sleep|sleeping|bandag\w*|salve|potion|mend\w*|tended|"
    r"recover\w*|restored?|regain\w*|level(?:ed| up)|ate|eating|drank|drink\w*|treated)\b", re.I)


def cost_units(text: str, *, window: int = 60) -> dict[str, int]:
    """Units the prose charges somebody in, with how often. Empty is a legitimate answer.

    A quantity counts as a cost when a transaction word sits within `window` characters of it.
    Proximity rather than parsing, and the looseness is in the safe direction: it over-collects,
    which lowers coverage, which makes the measure harder to pass rather than easier.
    """
    found: dict[str, int] = {}
    for match in _QUANTITY.finditer(text):
        unit = match.group(2).lower().rstrip("s") or match.group(2).lower()
        if unit in _NOT_A_RESOURCE or f"{unit}s" in _NOT_A_RESOURCE:
            continue
        start = max(0, match.start() - window)
        if _COST.search(text[start : match.end() + window]):
            found[unit] = found.get(unit, 0) + 1
    return found


def tracked_units(text: str) -> set[str]:
    """Field names the system voice keeps a running value for, in any of the three shapes."""
    names: set[str] = set()
    for line in _STATUS_LINE.findall(text):
        for segment in line.split("|"):
            match = _FIELD.search(segment)
            if match:
                names.add(match.group(1).strip().lower())
    for match in _SHEET_FIELD.finditer(text):
        label = match.group(1).strip().lower()
        # Four words is a stat name; more is a sentence that happened to contain a colon.
        if 1 <= len(label.split()) <= 4:
            names.add(label)
    cleaned = {name.rstrip("s") or name for name in names}
    return {name for name in cleaned if name and name not in _NOT_A_RESOURCE}


def coverage(text: str) -> dict[str, Any]:
    """Share of charged units the record keeps. `None` when the prose charges nobody anything."""
    costs = cost_units(text)
    tracked = tracked_units(text)
    if not costs:
        return {"cost_units": {}, "tracked": sorted(tracked), "coverage": None,
                "reason": "no cost expressions found; the check does not apply to this text"}
    hit = {unit for unit in costs if any(unit in name or name in unit for name in tracked)}
    weighted = sum(costs[unit] for unit in hit) / sum(costs.values())
    return {
        "cost_units": costs,
        "tracked": sorted(tracked),
        "covered": sorted(hit),
        "uncovered": sorted(set(costs) - hit),
        "coverage": round(len(hit) / len(costs), 4),
        "weighted_coverage": round(weighted, 4),
    }


def unexplained_gains(scenes: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Tracked values that rise between scenes with nothing in the prose licensing the rise.

    Not a style measure and not a proxy for one — a straight continuity check, which is why it
    lives beside the coverage measure rather than inside it. `state.contradiction.v0` ships to
    catch this class and did not catch this instance.
    """
    history: dict[str, tuple[int, str]] = {}
    flags: list[dict[str, Any]] = []
    for unit_id, text in scenes:
        licensed = bool(_LICENSE.search(text))
        for line in _STATUS_LINE.findall(text):
            for segment in line.split("|"):
                match = _FIELD.search(segment)
                if not match:
                    continue
                name = match.group(1).strip().lower()
                raw = match.group(2).split("/")[0].strip()
                if not raw.isdigit():
                    continue
                value = int(raw)
                previous = history.get(name)
                if previous and value > previous[0] and not licensed:
                    flags.append({
                        "field": name, "from": previous[0], "to": value,
                        "from_scene": previous[1], "to_scene": unit_id,
                        "delta": value - previous[0],
                    })
                history[name] = (value, unit_id)
    return flags


def run(args: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(Path(args.ours_json).read_text(encoding="utf-8"))
    scenes = [(entry["unit_id"], entry["text"]) for entry in payload["scenes"]]
    whole = "\n\n".join(text for _, text in scenes)

    report: dict[str, Any] = {
        "protocol": "plan/stage-0-decisions.md §76",
        "ours": {
            "scenes": len(scenes),
            "book_level": coverage(whole),
            "unexplained_gains": unexplained_gains(scenes),
        },
        "human": {},
    }

    from corpus_io import by_story, royalroad_chapters

    for shard, label in ((30, "pre_llm_2021_22"), (3, "post_llm_2025")):
        # **Book level on both sides, and the first run got this wrong.** Ours is one book of
        # ten scenes; a human *chapter* usually carries no status screen at all, so a
        # per-chapter median of 0.0 says "most chapters have no sheet" rather than "authors
        # charge in units they do not track". Grouping by story is what makes the two sides the
        # same measurement — the ecological-fallacy discipline `Grain.covers` enforces in the
        # promotion rules, arriving in a corpus statistic.
        chapters = list(royalroad_chapters(shards=(shard,), min_words=args.min_words,
                                           limit=args.limit))
        stories = by_story(chapters, min_chapters=args.min_chapters)
        rows, applicable = [], 0
        for units in stories.values():
            result = coverage("\n\n".join(unit.text for unit in units))
            if result["coverage"] is None:
                continue
            applicable += 1
            rows.append(float(result["coverage"]))
        if not rows:
            report["human"][label] = {"error": "no chapters with cost expressions"}
            continue
        rows.sort()
        report["human"][label] = {
            "stories_with_costs": applicable,
            "stories_seen": len(stories),
            "median_coverage": round(statistics.median(rows), 4),
            "mean_coverage": round(statistics.fmean(rows), 4),
            "p90": round(rows[min(int(0.90 * len(rows)), len(rows) - 1)], 4),
            "share_at_zero": round(sum(1 for value in rows if value == 0.0) / len(rows), 4),
        }
        print(f"  {label}: median {statistics.median(rows):.4f} over {applicable} chapters",
              file=sys.stderr, flush=True)

    ours = report["ours"]["book_level"]["coverage"]
    cohorts = [e for e in report["human"].values() if "median_coverage" in e]
    if ours is None or not cohorts:
        report["reading"] = "not computable"
        return report

    # **The reading is on the distribution, not on the median.** A first version refuted the
    # measure whenever the human median was near zero, which is wrong for a distribution where
    # most books score zero and a real minority do not: 59% of pre-LLM books sit at 0.0 while
    # the p90 reaches 0.5 and the mean 0.17. That is a measure with variance, not a constant,
    # and "the median is zero" is not the same claim as "this cannot separate anything".
    at_zero = min(entry["share_at_zero"] for entry in cohorts)
    p90 = max(entry["p90"] for entry in cohorts)
    if p90 <= 0.05:
        report["reading"] = (
            "REFUTED: no human book tracks what it charges in either, so this describes the "
            "genre rather than a defect"
        )
    elif ours <= 0.0 and at_zero >= 0.50:
        report["reading"] = (
            f"DOES NOT SEPARATE US: our coverage is {ours}, and {100 * at_zero:.0f}% of human "
            f"books are also at zero while the top decile reaches {p90}. The axis is real and "
            "has variance, but our book sits with the majority rather than outside it — so this "
            "formalisation does not capture the complaint that prompted it. The reading "
            "experience the human reported is not 'the ledger fails to track the toll', because "
            "most published LitRPG fails that too and is read anyway."
        )
    elif ours < statistics.fmean(entry["mean_coverage"] for entry in cohorts):
        report["reading"] = f"our coverage {ours} sits below the human mean"
    else:
        report["reading"] = f"our coverage {ours} is at or above the human mean"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ours-json",
                        default=str(HERE / "corpora" / "toll-scenes.json"))
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--limit", type=int, default=1500)
    parser.add_argument("--min-chapters", type=int, default=5,
                        help="chapters a story needs before it is a book-level comparison")
    parser.add_argument("--out", default=str(HERE / "results" / "state-coverage.json"))
    args = parser.parse_args(argv)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["ours"], indent=2))
    print(json.dumps(report["human"], indent=2))
    print("\nREADING:", report["reading"])
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
