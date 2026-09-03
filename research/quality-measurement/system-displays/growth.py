"""How many named system things a story carries: a census of bracketed names, no model.

Phase 4 of `plan/system-generality.md` asks whether a system may grow after the seed. The
engine draws five to eight grants at the seed (`gamesystem.MAX_ABILITIES`) and refuses a
ninth at acceptance. This reads every LitRPG chapter in the shards and counts, per story, the
distinct bracketed names on furniture lines (*[Basic Archery]*, *[Eye of the Viper]*), which
is how the genre writes a skill, a title or a class it has just handed out; and reports the
distribution over stories. Names only, no text; a floor, since the shards are sampled slices
of each story and a skill written without brackets is invisible here.

    export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
    "$MB" research/quality-measurement/system-displays/growth.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import corpus_io  # noqa: E402  # isort: skip
import system_displays as sd  # noqa: E402  # isort: skip

#: A bracketed name: letters, spaces, apostrophes and hyphens, two to forty characters, at
#: most five words. Digits are excluded so *[Level 12]* and *[HP: 40/40]* do not count.
_NAME = re.compile(r"\[([A-Za-z][A-Za-z' \-]{1,39})\]")
_MAX_WORDS = 5


def quantiles(values: list[int]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def at(q: float) -> float:
        index = min(len(ordered) - 1, round(q * (len(ordered) - 1)))
        return float(ordered[index])

    return {"p25": at(0.25), "p50": at(0.5), "p75": at(0.75), "p90": at(0.9), "max": at(1.0)}


def main() -> int:
    names_by_story: dict[str, set[str]] = defaultdict(set)
    chapters_by_story: dict[str, int] = defaultdict(int)
    read = 0
    for unit in corpus_io.royalroad_chapters():
        read += 1
        chapters_by_story[unit.work_id] += 1
        lines = unit.text.splitlines()
        classes = sd.classify_lines(unit.text)
        for start, end in sd.runs_of(classes, lines):
            for i in range(start, end):
                for match in _NAME.finditer(lines[i]):
                    name = " ".join(match.group(1).split())
                    if 1 <= len(name.split()) <= _MAX_WORDS:
                        names_by_story[unit.work_id].add(name.lower())
        if read % 5000 == 0:
            print(f"  read {read}", file=sys.stderr, flush=True)
    counts = {story: len(names) for story, names in names_by_story.items()}
    values = list(counts.values())
    over_eight = sum(1 for value in values if value > 8)
    per_chapter = [
        counts[story] / chapters_by_story[story] for story in counts if chapters_by_story[story]
    ]
    out = {
        "chapters_read": read,
        "stories_read": len(chapters_by_story),
        "stories_with_bracketed_names": len(counts),
        "distinct_names_per_story": quantiles(values),
        "stories_over_eight": over_eight,
        "share_over_eight": (over_eight / len(values)) if values else None,
        "names_per_sampled_chapter": quantiles([round(v) for v in per_chapter]),
    }
    (HERE / "growth.json").write_text(json.dumps(out, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
