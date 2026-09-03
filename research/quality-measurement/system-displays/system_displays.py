"""The market's system displays in chapters one to three: a census, no model, no bar.

Registered in `PREREG.md` beside this file (phase 0 of `plan/system-generality.md`). Reads
the cached LitRPG shards through `corpus_io`, classifies what is not prose with the cadence
census's furniture classifier so the two censuses agree on what a line is, and writes one row
of counts per chapter (never text) to `rows.jsonl` and the distributions to `results.json`.

    export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
    "$MB" research/quality-measurement/system-displays/system_displays.py --limit 0

`--limit N` reads at most N chapters from the shards (0 is every chapter), for a dry run.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import corpus_io  # noqa: E402  # isort: skip
import progression_cadence as cadence  # noqa: E402  # isort: skip

VERSION = "v2"
POSITIONS = (1, 2, 3)
FAMILIES = ("level_up", "capability", "stat_delta", "other")

_FIELD_COLON = re.compile(r"^\s*([A-Za-z][A-Za-z '\-/().]{0,40}?)\s*:\s*(.+?)\s*$")
_FIELD_SPACE = re.compile(
    r"^\s*([A-Za-z][A-Za-z '\-/().]{0,30}?)\s+([-+]?\d[\d,./%]*|N/A|n/a|None|---)\s*$"
)
_ZERO = re.compile(r"^(?:0+(?:[./]\d+)?%?|0/0|n/a|none|-{1,3}|\?+)$", re.IGNORECASE)
_CHOICE_WORD = re.compile(r"\b(choose|select|pick|option|options|choice|choices)\b", re.IGNORECASE)
_OPTION_LINE = re.compile(r"^\s*(?:\d+[.)]|[-•*>])\s+\S")
_ITEM = re.compile(
    r"\b(rarity|durability|damage|item|weapon|armou?r|common|uncommon|rare|epic|legendary|"
    r"mythic)\b",
    re.IGNORECASE,
)
_QUEST = re.compile(r"\b(quest|objective|objectives|reward|rewards)\b", re.IGNORECASE)


def _inner(line: str) -> str:
    return line.strip(cadence._EDGE).strip()


def classify_lines(text: str) -> list[str]:
    return [
        cadence._classify(cadence.normalise(line), version=VERSION) for line in text.splitlines()
    ]


def runs_of(classes: list[str]) -> list[tuple[int, int]]:
    """Maximal runs of non-prose lines, as (start, end) exclusive."""
    runs: list[tuple[int, int]] = []
    start = None
    for index, kind in enumerate([*classes, ""]):
        if kind and start is None:
            start = index
        elif not kind and start is not None:
            runs.append((start, index))
            start = None
    return runs


def field_of(line: str) -> tuple[str, str] | None:
    inner = _inner(line)
    match = _FIELD_COLON.match(inner) or _FIELD_SPACE.match(inner)
    if match is None:
        return None
    label, value = match.group(1).strip(), match.group(2).strip()
    if len(value) > 40:
        return None
    return label, value


def is_zero(value: str) -> bool:
    return bool(_ZERO.match(value.strip())) or value.strip() == ""


def notice_family(line: str) -> str:
    inner = _inner(line)
    if cadence._RE_LEVEL_UP.search(inner):
        return "level_up"
    if cadence._RE_CAPABILITY.search(inner):
        return "capability"
    if cadence._RE_STAT_DELTA.search(inner):
        return "stat_delta"
    return "other"


def measure_chapter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    classes = classify_lines(text)
    words = len(cadence.prose_only(text, version=VERSION).split())
    row: dict[str, Any] = {
        "words": words,
        "windows": 0,
        "fields": [],
        "total_fields": 0,
        "zero_fields": 0,
        "windows_with_zero": 0,
        "notices": dict.fromkeys(FAMILIES, 0),
        "choice_screens": 0,
        "options": [],
        "item_boxes": 0,
        "quest_cards": 0,
    }
    for start, end in runs_of(classes):
        furniture = [i for i in range(start, end) if classes[i] == "furniture"]
        if not furniture:
            continue
        if len(furniture) == 1:
            row["notices"][notice_family(lines[furniture[0]])] += 1
            continue
        row["windows"] += 1
        block = [lines[i] for i in furniture]
        found = [field_of(line) for line in block]
        fields = [f for f in found if f is not None]
        zeros = sum(1 for _, value in fields if is_zero(value))
        row["fields"].append(len(fields))
        row["total_fields"] += len(fields)
        row["zero_fields"] += zeros
        if zeros:
            row["windows_with_zero"] += 1
        head = " ".join(_inner(line) for line in block[:2])
        option_lines = sum(1 for line in block if _OPTION_LINE.match(_inner(line)))
        if _CHOICE_WORD.search(_inner(block[0])) or option_lines >= 2:
            row["choice_screens"] += 1
            row["options"].append(option_lines if option_lines >= 2 else max(0, len(block) - 1))
        if _ITEM.search(head):
            row["item_boxes"] += 1
        if _QUEST.search(head):
            row["quest_cards"] += 1
    row["any_display"] = bool(row["windows"] or sum(row["notices"].values()))
    return row


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    q = statistics.quantiles(ordered, n=4) if len(ordered) >= 2 else [ordered[0]] * 3
    return {
        "n": len(ordered),
        "median": statistics.median(ordered),
        "q1": q[0],
        "q3": q[2],
        "max": ordered[-1],
        "mean": round(statistics.fmean(ordered), 2),
    }


def _share(count: int, total: int) -> float | None:
    return round(count / total, 3) if total else None


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    groups: dict[str, list[dict[str, Any]]] = {"pooled": rows}
    for position in POSITIONS:
        groups[f"position_{position}"] = [r for r in rows if r["position"] == position]
    for name, group in groups.items():
        n = len(group)
        if not n:
            continue
        fields = [float(f) for r in group for f in r["fields"]]
        total_fields = sum(r["total_fields"] for r in group)
        zero_fields = sum(r["zero_fields"] for r in group)
        windows = sum(r["windows"] for r in group)
        windows_with_zero = sum(r["windows_with_zero"] for r in group)
        words = sum(r["words"] for r in group) or 1
        notices = {k: sum(r["notices"][k] for r in group) for k in FAMILIES}
        out[name] = {
            "chapters": n,
            "stories": len({r["work_id"] for r in group}),
            "share_any_display": _share(sum(1 for r in group if r["any_display"]), n),
            "share_with_window": _share(sum(1 for r in group if r["windows"]), n),
            "share_with_choice_screen": _share(sum(1 for r in group if r["choice_screens"]), n),
            "windows_per_chapter": round(windows / n, 2),
            "fields_per_window": _quantiles(fields),
            "share_fields_zero_or_blank": _share(zero_fields, total_fields),
            "share_windows_with_any_zero": _share(windows_with_zero, windows),
            "notices_per_1k_words": {k: round(1000.0 * v / words, 2) for k, v in notices.items()},
            "options_per_choice_screen": _quantiles(
                [float(o) for r in group for o in r["options"]]
            ),
            "item_boxes_per_chapter": round(sum(r["item_boxes"] for r in group) / n, 3),
            "quest_cards_per_chapter": round(sum(r["quest_cards"] for r in group) / n, 3),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--limit", type=int, default=0, help="chapters to read from the shards; 0 is all"
    )
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args(argv)

    by_story: dict[str, dict[int, corpus_io.Unit]] = defaultdict(dict)
    read = 0
    for unit in corpus_io.royalroad_chapters(limit=args.limit):
        read += 1
        if unit.position in POSITIONS:
            by_story[unit.work_id][unit.position] = unit
        if read % 5000 == 0:
            print(f"  read {read} chapters, {len(by_story)} stories", file=sys.stderr, flush=True)

    rows: list[dict[str, Any]] = []
    for work_id, chapters in by_story.items():
        if any(position not in chapters for position in POSITIONS):
            continue
        for position in POSITIONS:
            unit = chapters[position]
            row = measure_chapter(unit.text)
            row.update({"work_id": work_id, "position": position, "unit_id": unit.unit_id})
            rows.append(row)

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "rows.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "registered": sha256((HERE / "PREREG.md").read_bytes()).hexdigest(),
        "run_at": datetime.now(tz=UTC).isoformat(),
        "classifier": f"progression_cadence {VERSION}",
        "chapters_read": read,
        "stories_with_three_chapters": len({r["work_id"] for r in rows}),
        "summary": summarise(rows),
    }
    (args.out / "results.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8", newline="\n"
    )
    for name, block in summary["summary"].items():
        print(
            f"{name:11} chapters={block['chapters']:5} any={block['share_any_display']} "
            f"window={block['share_with_window']} choice={block['share_with_choice_screen']} "
            f"fields/window median={block['fields_per_window'].get('median')} "
            f"zero_fields={block['share_fields_zero_or_blank']} "
            f"windows_with_zero={block['share_windows_with_any_zero']} "
            f"notices/1k={block['notices_per_1k_words']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
