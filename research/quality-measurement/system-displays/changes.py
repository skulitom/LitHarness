"""Which way the market's window values move: a census of changes written with an arrow.

Phase 4 of `plan/system-generality.md` asks whether a book's numbers may fall (a loss, a
level down, a spend) or only rise (§113's *numbers go up*). The field census found 3 percent
of window fields written as a change (*80 → 160*); this reads each such change and counts
whether the end is above, below, or equal to the start, by label; an end written
with a sign (*171 → +29*) is an increment and counts by its sign. Counts and label words
only, no text; no model.

    export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
    "$MB" research/quality-measurement/system-displays/changes.py
"""

from __future__ import annotations

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

_ARROW = re.compile(
    r"(?P<start>[-+]?\d[\d,]*(?:\.\d+)?)\s*%?\s*(?:→|->|=>)\s*(?P<end>[-+]?\d[\d,]*(?:\.\d+)?)"
)


def main() -> int:
    direction: Counter[str] = Counter()
    by_label: dict[str, Counter[str]] = defaultdict(Counter)
    stories_with_falls: set[str] = set()
    stories_with_changes: set[str] = set()
    falls: list[dict[str, str]] = []
    read = 0
    for unit in corpus_io.royalroad_chapters():
        read += 1
        lines = unit.text.splitlines()
        classes = sd.classify_lines(unit.text)
        for start, end in sd.runs_of(classes, lines):
            for i in range(start, end):
                if classes[i] != "furniture":
                    continue
                for label, value in sd.fields_on(lines[i]):
                    match = _ARROW.search(value)
                    if match is None:
                        continue
                    try:
                        a = float(match.group("start").replace(",", ""))
                        b = float(match.group("end").replace(",", ""))
                    except ValueError:
                        continue
                    # `171 → +29` is an increment written after the arrow, not a fall: a
                    # signed end value is a delta, and its sign is the direction (found by
                    # reading the first run's falls, seventeen of thirty-eight were these).
                    signed = match.group("end")[0] in "+-"
                    if signed:
                        way = "up" if b > 0 else ("down" if b < 0 else "same")
                    else:
                        way = "up" if b > a else ("down" if b < a else "same")
                    direction[way] += 1
                    by_label[label.strip().lower()][way] += 1
                    stories_with_changes.add(unit.work_id)
                    if way == "down":
                        stories_with_falls.add(unit.work_id)
                        # The label and the arrow value only: furniture, not prose.
                        falls.append(
                            {"work": unit.work_id, "label": label.strip(), "value": match.group(0)}
                        )
        if read % 5000 == 0:
            print(f"  read {read}", file=sys.stderr, flush=True)
    labels_down = sorted(
        ((label, dict(counts)) for label, counts in by_label.items() if counts.get("down")),
        key=lambda item: -item[1]["down"],
    )[:25]
    out = {
        "chapters_read": read,
        "changes": dict(direction),
        "stories_with_changes": len(stories_with_changes),
        "stories_with_falls": len(stories_with_falls),
        "labels_falling_most": labels_down,
        "falls": falls,
    }
    (HERE / "changes.json").write_text(json.dumps(out, indent=2), encoding="utf-8", newline="\n")
    print("chapters", read, "changes", dict(direction))
    print("stories with changes", len(stories_with_changes), "with falls", len(stories_with_falls))
    for label, counts in labels_down[:15]:
        print(f"  {label:24} {counts}")
    for fall in falls:
        print(f"  fall {fall['work']:>8} {fall['label']:24} {fall['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
