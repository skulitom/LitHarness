"""Write the arguments the `volume-arc-review` workflow takes, from a volume run folder.

The workflow (`.claude/workflows/volume-arc-review.js`) reads one drafted arc through six
lenses on Opus, refutes each finding against the text, and harvests what survives. It takes
one JSON object; this script assembles it from what `tools/volume_run.py` leaves on disk
so nobody retypes a concept into a prompt: the shelf's chapter files for the arc, the
concept and listing, the Architect's own seed report as the world summary, the concept's
named debts, and the previous arc's harvest so findings are not repeated.

    uv run python tools/arc_review_args.py --run runs/volume1 --arc 2 \
        --chapters 13-24 --out runs/volume1/review-arc2-args.json

Nothing here reads the store or spends anything.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def chapter_range(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)-(\d+)", text.strip())
    if not match:
        raise argparse.ArgumentTypeError("--chapters takes FIRST-LAST, e.g. 13-24")
    first, last = int(match.group(1)), int(match.group(2))
    if first < 1 or last < first:
        raise argparse.ArgumentTypeError("--chapters needs 1 <= FIRST <= LAST")
    return first, last


def debts_of(concept: dict[str, object]) -> str:
    rows = concept.get("debts") if isinstance(concept, dict) else None
    if not isinstance(rows, list):
        return ""
    return "; ".join(
        f"{row.get('subject')}: {row.get('owed')} (by scene {row.get('due_scene')})"
        for row in rows
        if isinstance(row, dict)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run", type=Path, required=True, help="the volume run folder")
    parser.add_argument("--arc", type=int, required=True)
    parser.add_argument("--chapters", type=chapter_range, required=True, help="FIRST-LAST")
    parser.add_argument(
        "--shelf",
        type=Path,
        help="the book's shelf folder; found under <run>/book-library by default",
    )
    parser.add_argument("--prior-harvest", type=Path, help="the previous arc's HARVEST file")
    parser.add_argument(
        "--world-summary", type=Path, help="defaults to <run>/world-seed-report.txt when present"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    run: Path = args.run
    shelf = args.shelf
    if shelf is None:
        shelves = [p for p in (run / "book-library").glob("*") if (p / "chapters").is_dir()]
        if len(shelves) != 1:
            print(
                f"arc_review_args: {len(shelves)} shelf folder(s) under "
                f"{run / 'book-library'}; pass --shelf",
                file=sys.stderr,
            )
            return 2
        shelf = shelves[0]
    first, last = args.chapters
    chapters = []
    for number in range(first, last + 1):
        path = shelf / "chapters" / f"Chapter{number}.txt"
        if not path.exists():
            print(f"arc_review_args: {path} is not on the shelf yet", file=sys.stderr)
            return 1
        chapters.append({"chapter": number, "path": str(path.resolve())})
    title = (run / "title.txt").read_text(encoding="utf-8").strip()
    concept_text = (run / "concept.txt").read_text(encoding="utf-8")
    concept_json = json.loads((run / "concept.json").read_text(encoding="utf-8"))
    world_path = args.world_summary or (run / "world-seed-report.txt")
    world = world_path.read_text(encoding="utf-8") if world_path.exists() else ""
    prior = args.prior_harvest.read_text(encoding="utf-8") if args.prior_harvest else ""
    payload = {
        "title": title,
        "arc": args.arc,
        "chapters": chapters,
        "concept": concept_text,
        "listing": (run / "listing.txt").read_text(encoding="utf-8"),
        "worldSummary": world
        + "\n\nRead-only world views: `uv run litharness --database "
        + str((run / "serial.db").resolve())
        + " world rules` (also world ladders, world cast, state --subject <id>). Read-only only; "
        "never run tick, accept, declare or any paid verb.",
        "priorHarvest": prior,
        "debts": debts_of(concept_json),
    }
    args.out.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(
        f"wrote {args.out}: arc {args.arc}, chapters {first}-{last}, "
        f"{len(prior)} chars of prior harvest"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
