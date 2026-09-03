"""How often the market's furniture says a thing changed into another: a census, no model.

Phase 4 of `plan/system-generality.md` names a merge (two capabilities into one, as a change
that retires two and grants one). The genre writes that as a notice: *[Basic Archery] has
evolved into [Eagle Eye]*, *skills merged*, *upgraded to*, *fused*. This reads every LitRPG
chapter in the shards and counts furniture lines carrying such a verb, by family and by
story, beside the plain gain notices (*acquired*, *learned*, *obtained*) for scale. Counts
and verb families only, no text.

    export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
    "$MB" research/quality-measurement/system-displays/evolution.py
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

FAMILIES: dict[str, re.Pattern[str]] = {
    "evolve": re.compile(r"\bevolv(?:e|es|ed|ing)\b", re.I),
    "upgrade": re.compile(r"\bupgrad(?:e|es|ed|ing)\b", re.I),
    "merge_fuse": re.compile(r"\b(?:merg(?:e|es|ed|ing)|fus(?:e|es|ed|ing|ion))\b", re.I),
    "transform": re.compile(r"\b(?:transform(?:s|ed|ing)?|mutat(?:e|es|ed|ion))\b", re.I),
    "replace": re.compile(r"\b(?:replac(?:e|es|ed)|becomes?|turned into)\b", re.I),
    "lost_removed": re.compile(r"\b(?:lost|removed|revoked|stripped|drained|cursed)\b", re.I),
    "gain_plain": re.compile(
        r"\b(?:acquired|learned|obtained|gained|unlocked|awarded|granted)\b", re.I
    ),
}


def main() -> int:
    lines_by_family: Counter[str] = Counter()
    stories_by_family: dict[str, set[str]] = defaultdict(set)
    furniture_lines = 0
    read = 0
    stories: set[str] = set()
    for unit in corpus_io.royalroad_chapters():
        read += 1
        stories.add(unit.work_id)
        lines = unit.text.splitlines()
        classes = sd.classify_lines(unit.text)
        for start, end in sd.runs_of(classes, lines):
            for i in range(start, end):
                furniture_lines += 1
                for family, pattern in FAMILIES.items():
                    if pattern.search(lines[i]):
                        lines_by_family[family] += 1
                        stories_by_family[family].add(unit.work_id)
        if read % 5000 == 0:
            print(f"  read {read}", file=sys.stderr, flush=True)
    change_families = ("evolve", "upgrade", "merge_fuse", "transform", "replace")
    stories_changing = set().union(*(stories_by_family[f] for f in change_families))
    out = {
        "chapters_read": read,
        "stories_read": len(stories),
        "furniture_lines": furniture_lines,
        "lines_by_family": dict(lines_by_family),
        "stories_by_family": {family: len(found) for family, found in stories_by_family.items()},
        "stories_with_any_change_verb": len(stories_changing),
        "stories_with_plain_gain": len(stories_by_family["gain_plain"]),
    }
    (HERE / "evolution.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
