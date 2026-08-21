"""Distributions for `opening_proper_nouns`, the counter the 2026-08-21 read nominated.

**Measurement only.** Nothing here feeds a prompt, a directive, or any generation path, and
nothing here admits an axis. Per `plan/reader-read-2.md` a counter enters the registry by an
operator act over a measured distribution; this produces the distribution and stops.

**Two venvs, because one of them has pyarrow and the other is the repository.** The RoyalRoad
shards are 497MB of parquet and only `C:/DEV/MirrorBench/.venv` can read them, so that substrate
runs there and everything else runs under `uv run python`. The counter itself has no
dependencies beyond the standard library, which is what lets one implementation serve both:

    uv run python research/quality-measurement/opening_counters.py --substrate local
    C:/DEV/MirrorBench/.venv/Scripts/python.exe \
        research/quality-measurement/opening_counters.py --substrate royalroad

Each writes a JSON file beside this script; `--substrate report` merges them into the numbers
quoted in `opening-counters-results.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))

from litharness.domain.axes import (  # noqa: E402
    OPENING_WINDOW_WORDS,
    opening_proper_noun_names,
    opening_proper_nouns,
)

LOCAL_JSON = HERE / "opening-counters-local.json"
ROYALROAD_JSON = HERE / "opening-counters-royalroad.json"

#: How many RoyalRoad openings to draw. The brief asks for at least five hundred; more is
#: cheap once the shard is open, and a wider baseline makes the percentile of a single chapter
#: less of an artefact of where the cut fell.
ROYALROAD_TARGET = 2000

#: Quantiles reported for every distribution. No bar is declared anywhere in this file — these
#: are the shape of the population, not a threshold anything must clear.
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)


def describe(values: list[float]) -> dict[str, object]:
    """Quantiles and moments for one population. Empty in, empty out — a substrate that could
    not be read reports that rather than a zero that looks like a measurement."""
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 3),
        "sd": round(statistics.pstdev(ordered), 3) if len(ordered) > 1 else 0.0,
        "min": ordered[0],
        "max": ordered[-1],
        "quantiles": {
            str(q): round(_quantile(ordered, q), 3) for q in QUANTILES
        },
    }


def _quantile(ordered: list[float], q: float) -> float:
    """Nearest-rank, so every reported value is one a text actually scored."""
    if len(ordered) == 1:
        return ordered[0]
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def percentile_of(value: float, population: list[float]) -> float | None:
    """Share of the population at or below `value`, as a percentage."""
    if not population:
        return None
    at_or_below = sum(1 for item in population if item <= value)
    return round(100.0 * at_or_below / len(population), 1)


# -- substrate (a): Reappraisal, as published -------------------------------------------


def reappraisal_chapters() -> dict[str, str]:
    """The assembled chapters as a reader receives them.

    **The published chapter is the unit, not the scene.** The scene is this system's unit of
    work; the read that nominated this counter judged a chapter. Preferring `book-library/`
    over the store is the same decision: that folder holds the assembled form, and assembling
    it here would be a second implementation of `library.chapters_for` that could drift.
    """
    shelf = REPO / "book-library" / "reappraisal" / "chapters"
    if shelf.is_dir():
        return {
            path.stem: path.read_text(encoding="utf-8")
            for path in sorted(shelf.glob("Chapter*.txt"))
        }
    return _chapters_from_store()


def _chapters_from_store(database: str = "serial.db") -> dict[str, str]:
    """Fallback for a checkout with no published library. Read-only by URI, because this is a
    measurement and a measurement may not write to the thing it measures."""
    path = REPO / database
    if not path.exists():
        return {}
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT content FROM node_versions WHERE content IS NOT NULL ORDER BY rowid"
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        connection.close()
    scenes = [row[0] for row in rows if row[0] and row[0].strip()]
    return {
        f"Chapter{index + 1}": "\n\n".join(scenes[index * 4 : index * 4 + 4])
        for index in range((len(scenes) + 3) // 4)
    }


# -- substrate (b): The Toll Road, per-scene openings ------------------------------------

_TOLL_HEADING = re.compile(r"^## .*$", re.MULTILINE)


def toll_road_scenes() -> list[str]:
    """Per-scene prose from the export. Secondary colour only: these are scene openings, and a
    scene opening is not the unit the read judged."""
    path = REPO / "exports" / "the-toll-road.md"
    if not path.exists():
        return []
    parts = _TOLL_HEADING.split(path.read_text(encoding="utf-8"))
    return [part.strip() for part in parts[1:] if len(part.split()) >= 50]


# -- substrate (c): RoyalRoad ------------------------------------------------------------


def royalroad(limit: int, genre_tag: str | None) -> list[float]:
    sys.path.insert(0, str(HERE))
    import corpus_io

    values: list[float] = []
    for unit in corpus_io.royalroad_chapters(
        genre_tag=genre_tag, min_words=OPENING_WINDOW_WORDS, limit=limit
    ):
        values.append(opening_proper_nouns(unit.text))
    return values


# -- runners -----------------------------------------------------------------------------


def run_local() -> dict[str, object]:
    chapters = reappraisal_chapters()
    reappraisal = {
        name: {
            "count": opening_proper_nouns(text),
            "names": list(opening_proper_noun_names(text)),
            "words": len(text.split()),
        }
        for name, text in chapters.items()
    }
    toll = toll_road_scenes()
    return {
        "window_words": OPENING_WINDOW_WORDS,
        "reappraisal": reappraisal,
        "toll_road": {
            "per_scene": [opening_proper_nouns(text) for text in toll],
            "summary": describe([opening_proper_nouns(text) for text in toll]),
            "first_scene_names": list(opening_proper_noun_names(toll[0])) if toll else [],
        },
    }


def run_royalroad() -> dict[str, object]:
    overall = royalroad(ROYALROAD_TARGET, None)
    litrpg = royalroad(ROYALROAD_TARGET, "LitRPG")
    return {
        "window_words": OPENING_WINDOW_WORDS,
        "overall": {"summary": describe(overall), "values": overall},
        "litrpg": {"summary": describe(litrpg), "values": litrpg},
    }


def run_report() -> dict[str, object]:
    local = json.loads(LOCAL_JSON.read_text(encoding="utf-8"))
    rr = json.loads(ROYALROAD_JSON.read_text(encoding="utf-8"))
    overall = rr["overall"]["values"]
    litrpg = rr["litrpg"]["values"]
    placed = {}
    for name, entry in local["reappraisal"].items():
        placed[name] = {
            "count": entry["count"],
            "percentile_overall": percentile_of(entry["count"], overall),
            "percentile_litrpg": percentile_of(entry["count"], litrpg),
        }
    toll_values = local["toll_road"]["per_scene"]
    toll_median = statistics.median(toll_values) if toll_values else None
    return {
        "reappraisal": placed,
        "toll_road_median": toll_median,
        "toll_road_percentile_overall": (
            percentile_of(toll_median, overall) if toll_median is not None else None
        ),
        "royalroad_overall": rr["overall"]["summary"],
        "royalroad_litrpg": rr["litrpg"]["summary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--substrate", choices=("local", "royalroad", "report"), required=True)
    args = parser.parse_args(argv)

    if args.substrate == "local":
        payload = run_local()
        LOCAL_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif args.substrate == "royalroad":
        payload = run_royalroad()
        ROYALROAD_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        payload = run_report()

    printable = payload if args.substrate != "royalroad" else {
        "overall": payload["overall"]["summary"],  # type: ignore[index]
        "litrpg": payload["litrpg"]["summary"],  # type: ignore[index]
    }
    print(json.dumps(printable, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
