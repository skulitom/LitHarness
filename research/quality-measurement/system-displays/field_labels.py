"""Which fields the market's windows carry: a label tally and a value-kind tally, no model.

The second half of the system-displays census (`FINDINGS.md`, *what is owed*), for phase 2 of
`plan/system-generality.md`: the field labels that recur across stories' windows, and what
kind of value each label carries (a number, a current/maximum pair, a percentage, a name or
text, a list). Labels are tallied by *stories carrying them*, so one story's forty windows
count once. Output: `field_labels.json` beside this file; counts and label words only.

    export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
    "$MB" research/quality-measurement/system-displays/field_labels.py --limit 0
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import corpus_io  # noqa: E402  # isort: skip
import system_displays as sd  # noqa: E402  # isort: skip

_NUMBER = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?$")
_PAIRED = re.compile(r"^\d[\d,]*\s*/\s*\d[\d,]*$")
_PERCENT = re.compile(r"^\d[\d,.]*\s*%$")
_CHANGE = re.compile(r"^\S.*(?:→|->|=>)\s*\S")
_LIST = re.compile(r",|;|\band\b")


def kind_of(value: str) -> str:
    text = value.strip()
    if _PAIRED.match(text):
        return "paired"
    if _PERCENT.match(text):
        return "percent"
    if _NUMBER.match(text):
        return "number"
    if _CHANGE.match(text):
        return "change"
    if sd.is_zero(text):
        return "blank"
    if _LIST.search(text) and len(text) > 12:
        return "list"
    if re.search(r"\d", text):
        return "number_with_text"
    return "name_or_text"


def normalise_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path, default=HERE / "field_labels.json")
    args = parser.parse_args(argv)

    stories_by_label: dict[str, set[str]] = defaultdict(set)
    kinds_by_label: dict[str, Counter[str]] = defaultdict(Counter)
    kinds_all: Counter[str] = Counter()
    stories_with_windows: set[str] = set()
    fields_seen = 0
    read = 0
    for unit in corpus_io.royalroad_chapters(limit=args.limit):
        read += 1
        lines = unit.text.splitlines()
        classes = sd.classify_lines(unit.text)
        for start, end in sd.runs_of(classes, lines):
            furniture = [i for i in range(start, end) if classes[i] == "furniture"]
            if len(furniture) < 2:
                continue
            stories_with_windows.add(unit.work_id)
            for i in furniture:
                for label, value in sd.fields_on(lines[i]):
                    key = normalise_label(label)
                    if not key or len(key) > 30:
                        continue
                    fields_seen += 1
                    kind = kind_of(value)
                    stories_by_label[key].add(unit.work_id)
                    kinds_by_label[key][kind] += 1
                    kinds_all[kind] += 1
        if read % 5000 == 0:
            print(f"  read {read}", file=sys.stderr, flush=True)

    ranked = sorted(stories_by_label.items(), key=lambda item: -len(item[1]))
    top = [
        {
            "label": label,
            "stories": len(stories),
            "share_of_window_stories": round(len(stories) / max(1, len(stories_with_windows)), 3),
            "kinds": dict(kinds_by_label[label].most_common(4)),
        }
        for label, stories in ranked[:80]
    ]
    out = {
        "chapters_read": read,
        "stories_with_windows": len(stories_with_windows),
        "fields_seen": fields_seen,
        "value_kinds": dict(kinds_all.most_common()),
        "labels_by_stories": top,
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8", newline="\n")
    print(
        f"chapters {read}; stories with windows {len(stories_with_windows)}; fields {fields_seen}"
    )
    print("value kinds:", dict(kinds_all.most_common()))
    for row in top[:40]:
        share = row["share_of_window_stories"]
        print(f"  {row['label']:24} stories={row['stories']:4} ({share:.2f}) {row['kinds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
