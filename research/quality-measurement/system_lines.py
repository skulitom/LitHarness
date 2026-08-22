"""How often the genre's system voice is on the page, and whether a digit on it ever changes.

**A deterministic counter with no bar, and the bar is deliberately absent.**
`plan/handoff-numbers-go-up.md` Task 6 and boundary 4: "the number should move at least every N
words" is the operator's to set over a measured distribution, and this file is the distribution.
Nothing here is admitted to the axis registry, nothing gates anything, and no direction is
declared for any column — not one of these quantities has a direction anybody has earned.
`BRIEF.md` §2 is the ledger of what happens when that discipline slips.

**It reuses `domain/axes` rather than writing a second regex**, which is the same argument
`chapter_endings.py` makes for reusing `strip_system`: two matchers for one notion of "system
voice" would make a disagreement between two experiments a disagreement about parsing.
`_SYSTEM_LINE` locates a bracketed all-caps tag, `strip_system` removes the system voice from
prose so the word count is a prose word count, and `system_digit_count` counts digits on the
unstripped system lines.

## What it cannot see, named rather than footnoted

- **`_SYSTEM_LINE` reads a bracketed all-caps tag and nothing else.** `chapter-endings-census.md`
  §3.2 measured the cost of exactly this on one corpus: the 21-book fitness corpus renders its
  system voice as *unbracketed* ALL-CAPS readouts and contains **zero** bracketed tags. So a
  chapter whose system voice is unbracketed reads here as a chapter with none, and the RoyalRoad
  numbers below are a floor rather than an estimate.
- **`digits_differ` is the cheapest "did a number move" a regex can see, and it is very cheap.**
  It asks whether any two *consecutive* system lines in a chapter differ in their digit
  sequence. It cannot tell a rise from a fall, cannot tell a level from a page number, cannot
  see a change carried across a chapter boundary, and reads two lines about different subjects
  as one comparison. What it can do is separate a chapter whose readouts are literally identical
  from one whose readouts are not, which is the floor under "the numbers go up" and is reported
  as that and nothing more.
- **No cohort claim.** The era columns are printed because `tricolon_rate` died to exactly that
  control (0.629 against pre-2023, 0.606 for the *undeclared* 2025 control — the metric detected
  the year), so any new counter over this corpus prints its era split whether or not anybody
  expects one. Nothing is concluded from the split here.

## Two interpreters, for `chapter_endings.py`'s reason

The RoyalRoad shards are parquet and only `C:/DEV/MirrorBench/.venv` can read them;
`corpus_io.generated_scenes` imports the package, which that interpreter does not have. So the
substrates run apart and a third pass merges them:

    uv run python research/quality-measurement/system_lines.py --substrate local
    C:/DEV/MirrorBench/.venv/Scripts/python.exe \
        research/quality-measurement/system_lines.py --substrate royalroad
    uv run python research/quality-measurement/system_lines.py --substrate report

Each writes a JSON file beside this script. **A leg that cannot run is recorded as NOT RUN with
its reason, in the table, never omitted** — a loader that silently found nothing would report a
census of zero as a measurement.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections.abc import Iterable, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

from litharness.domain.axes import (  # noqa: E402
    _SYSTEM_LINE,
    strip_system,
    system_digit_count,
)

LOCAL_JSON = HERE / "results" / "system-lines-local.json"
ROYALROAD_JSON = HERE / "results" / "system-lines-royalroad.json"

_DIGITS = re.compile(r"\d+")


def describe(text: str) -> dict[str, Any]:
    """Every counter this file has, for one unit of prose. Deterministic, no model."""
    lines = [line for line in text.splitlines() if _SYSTEM_LINE.search(line)]
    prose_words = max(len(strip_system(text).split()), 1)
    runs = [tuple(_DIGITS.findall(line)) for line in lines]
    return {
        "words": len(text.split()),
        "prose_words": prose_words,
        "system_lines": len(lines),
        "system_lines_per_1k": round(1000.0 * len(lines) / prose_words, 4),
        "has_system_line": bool(lines),
        "digits_on_system_lines": system_digit_count(text),
        # The floor under "the numbers go up": any two consecutive system lines whose digit
        # sequences are not identical. False for a chapter with fewer than two system lines,
        # which is not the same as a chapter whose numbers did not move — see the docstring.
        "digits_differ": any(
            earlier != later for earlier, later in pairwise(runs)
        ),
        "comparable_pairs": max(len(runs) - 1, 0),
    }


def summarise(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    per_1k = [float(row["system_lines_per_1k"]) for row in rows]
    with_lines = [row for row in rows if row["has_system_line"]]
    pairs = [row for row in rows if row["comparable_pairs"]]
    return {
        "n": len(rows),
        "median_words": statistics.median(float(row["words"]) for row in rows),
        "pct_with_a_system_line": round(100.0 * len(with_lines) / len(rows), 2),
        "system_lines_per_1k_mean": round(statistics.fmean(per_1k), 4),
        "system_lines_per_1k_median": round(statistics.median(per_1k), 4),
        "digits_on_system_lines_mean": round(
            statistics.fmean(float(row["digits_on_system_lines"]) for row in rows), 3
        ),
        # Denominator is units with at least two system lines, because a unit with fewer has
        # no comparison to make and counting it as "did not move" would be an omission of ours
        # reported as a fact about the prose.
        "units_with_two_or_more_system_lines": len(pairs),
        "pct_of_those_whose_digits_differ": (
            round(100.0 * sum(1 for row in pairs if row["digits_differ"]) / len(pairs), 2)
            if pairs
            else None
        ),
    }


# -- substrate (a): this system's own prose ----------------------------------------------


def published_chapters(shelf: Path) -> list[tuple[str, str]]:
    """The assembled chapters as a reader receives them. `chapter_endings.published_chapters`."""
    return [
        (f"{path.parent.parent.name}/{path.stem}", path.read_text(encoding="utf-8"))
        for path in sorted(shelf.glob("*/chapters/*.txt"))
    ]


def _databases(corpora: Path, extra: Sequence[str]) -> list[Path]:
    """Own-generated book databases, in a fixed order. Existence-filtered and reported.

    `chapter_endings._databases`' list, plus whatever `--database` names — a linked worktree
    finds none of the defaults, because every one of them is gitignored and lives in the primary
    checkout only. That is why `--corpora` and `--database` exist and why `run_local` records
    which paths were actually read: a loader that silently found nothing would report a census
    of zero as a measurement.
    """
    found = [
        REPO / "serial.db",
        REPO / "serial3.db",
        REPO / "exports" / "book-snapshots.db",
        corpora / "toll.db",
        *(Path(name) for name in extra),
    ]
    found += sorted((corpora / "fitness").glob("fitness-*.db"))
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in found:
        resolved = path.resolve()
        if path.exists() and resolved not in seen:
            seen.add(resolved)
            ordered.append(path)
    return ordered


def generated_units(databases: Sequence[Path], min_words: int) -> list[tuple[str, str, str]]:
    """(work, unit_id, text) for every drafted scene in every database given.

    Branches are enumerated rather than defaulted: `export.resolve_branch` refuses a store
    holding more than one book, and at least one on this machine does.
    """
    import corpus_io

    from litharness.adapters.sqlite_store import SqliteStore

    out: list[tuple[str, str, str]] = []
    for path in databases:
        store = SqliteStore.open(str(path))
        try:
            branches = [(book, branch) for book, branch, _ in store.branches()]
        finally:
            store.close()
        for book_id, branch_id in branches:
            units = corpus_io.generated_scenes(
                path, book=book_id, branch=branch_id, min_words=min_words
            )
            for unit in units:
                title = str(unit.meta.get("book_title") or book_id[:8])
                out.append((f"{path.stem}:{title}", unit.unit_id, unit.text))
    return out


def run_local(
    min_words: int, shelf: Path, corpora: Path, extra: Sequence[str]
) -> dict[str, Any]:
    databases = _databases(corpora, extra)
    chapters = published_chapters(shelf)
    per_chapter = {name: describe(text) for name, text in chapters}
    scenes = generated_units(databases, min_words)
    per_scene = [
        {"work": work, "unit_id": unit_id, **describe(text)} for work, unit_id, text in scenes
    ]
    return {
        "min_words": min_words,
        "shelf": str(shelf),
        "corpora": str(corpora),
        "databases_read": [str(path) for path in databases],
        "published_chapters": {
            "grain": "chapter",
            "source": f"{shelf.name}/*/chapters/*.txt",
            "per_unit": per_chapter,
            "summary": summarise(list(per_chapter.values())),
        },
        "generated_scenes": {
            "grain": "scene",
            "source": "corpus_io.generated_scenes over "
            + (", ".join(path.name for path in databases) or "(none found)"),
            "works": len(sorted({row["work"] for row in per_scene})),
            "summary": summarise(per_scene),
            "per_unit": per_scene,
        },
    }


# -- substrate (b): the cached RoyalRoad cohort ------------------------------------------


def _rows(units: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for unit in units:
        row = describe(unit.text)
        row["cohort"] = unit.meta["cohort"]
        row["work_id"] = unit.work_id
        out.append(row)
    return out


def run_royalroad(limit: int) -> dict[str, Any]:
    """Chapter grain over the two cached shards, with the era split printed unasked."""
    import corpus_io

    units = list(corpus_io.royalroad_chapters(limit=limit))
    rows = _rows(units)
    by_cohort = {
        cohort: summarise([row for row in rows if row["cohort"] == cohort])
        for cohort in sorted({str(row["cohort"]) for row in rows})
    }
    # Within story, because every confound this directory has killed was a between-story one.
    stories = corpus_io.by_story(units)
    per_story = {
        story: summarise(_rows(chapters)) for story, chapters in sorted(stories.items())
    }
    shares = [
        float(note["pct_with_a_system_line"])
        for note in per_story.values()
        if note.get("n")
    ]
    return {
        "limit": limit,
        "source": "corpus_io.royalroad_chapters (shards 3 and 30, LitRPG tag)",
        "summary": summarise(rows),
        "by_cohort": by_cohort,
        "within_story": {
            "stories": len(per_story),
            "mean_of_story_means_pct_with_a_system_line": (
                round(statistics.fmean(shares), 2) if shares else None
            ),
            "stories_with_at_least_one_system_line_chapter": sum(
                1 for share in shares if share > 0
            ),
        },
    }


# -- the merge ------------------------------------------------------------------------------


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def render(local: dict[str, Any] | None, royalroad: dict[str, Any] | None) -> str:
    """One table, with a NOT RUN row and its reason for any leg that did not run."""
    columns = [
        ("n", "n"),
        ("median_words", "median words"),
        ("pct_with_a_system_line", "% with ≥1 system line"),
        ("system_lines_per_1k_median", "system lines / 1k (median)"),
        ("system_lines_per_1k_mean", "system lines / 1k (mean)"),
        ("digits_on_system_lines_mean", "digits on them (mean)"),
        ("units_with_two_or_more_system_lines", "units with ≥2 system lines"),
        ("pct_of_those_whose_digits_differ", "% of those whose digits differ"),
    ]
    legs: list[tuple[str, dict[str, Any] | None, str]] = [
        (
            "published chapters",
            (local or {}).get("published_chapters", {}).get("summary") if local else None,
            "run `--substrate local`",
        ),
        (
            "own drafted scenes",
            (local or {}).get("generated_scenes", {}).get("summary") if local else None,
            "run `--substrate local`",
        ),
        (
            "RoyalRoad LitRPG",
            (royalroad or {}).get("summary") if royalroad else None,
            "run `--substrate royalroad` under C:/DEV/MirrorBench/.venv",
        ),
    ]
    header = "| | " + " | ".join(label for _, label in columns) + " |"
    lines = [header, "|" + "---|" * (len(columns) + 1)]
    for name, note, reason in legs:
        if not note or not note.get("n"):
            lines.append(f"| {name} | **NOT RUN** — {reason} |" + " |" * (len(columns) - 1))
            continue
        cells = [
            "—" if note.get(key) is None else str(note.get(key)) for key, _ in columns
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        "Descriptive. No bar is declared for any column. `_SYSTEM_LINE` reads a bracketed "
        "all-caps tag and nothing else, so every share here is a floor; `digits differ` "
        "compares consecutive system lines and cannot tell a rise from a fall."
    )
    if royalroad and royalroad.get("by_cohort"):
        lines.append("")
        lines.append("| RoyalRoad cohort | n | % with ≥1 system line | lines / 1k (median) |")
        lines.append("|---|---|---|---|")
        for cohort, note in royalroad["by_cohort"].items():
            lines.append(
                f"| `{cohort}` | {note.get('n')} | {note.get('pct_with_a_system_line')} | "
                f"{note.get('system_lines_per_1k_median')} |"
            )
        lines.append("")
        lines.append(
            "The era split is printed because `tricolon_rate` died to exactly this control. "
            "Nothing is concluded from it here."
        )
    if royalroad and royalroad.get("within_story"):
        note = royalroad["within_story"]
        lines.append("")
        lines.append(
            f"Within story, at five chapters minimum: **{note['stories']} stories**, mean of "
            f"story means {note['mean_of_story_means_pct_with_a_system_line']}% of chapters "
            "with a system line, and "
            f"**{note['stories_with_at_least_one_system_line_chapter']} of them have at least "
            "one such chapter**. Reported because every confound this directory has killed was "
            "a between-story one."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # The table carries `≥` and `—`, and this box's console is cp1252. Reconfigured rather than
    # the characters replaced: the same string is what gets pasted into the results note.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--substrate", choices=("local", "royalroad", "report"), required=True
    )
    parser.add_argument("--min-words", type=int, default=200)
    parser.add_argument(
        "--shelf",
        type=Path,
        default=REPO / "book-library",
        help="where the assembled chapters live; a linked worktree has none of its own",
    )
    parser.add_argument(
        "--corpora",
        type=Path,
        default=HERE / "corpora",
        help="where toll.db and fitness/*.db live; a linked worktree has none of its own",
    )
    parser.add_argument(
        "--database",
        action="append",
        default=[],
        help="an extra own-generated book database to read; repeatable",
    )
    parser.add_argument("--limit", type=int, default=0, help="RoyalRoad chapters; 0 is all")
    args = parser.parse_args(argv)

    LOCAL_JSON.parent.mkdir(parents=True, exist_ok=True)
    if args.substrate == "local":
        payload = run_local(args.min_words, args.shelf, args.corpora, args.database)
        LOCAL_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload["published_chapters"]["summary"], indent=2))
        print(json.dumps(payload["generated_scenes"]["summary"], indent=2))
        print(f"databases read: {payload['databases_read']}")
        return 0
    if args.substrate == "royalroad":
        payload = run_royalroad(args.limit)
        ROYALROAD_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload["summary"], indent=2))
        return 0
    print(render(_load(LOCAL_JSON), _load(ROYALROAD_JSON)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
