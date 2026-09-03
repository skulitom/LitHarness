"""Sample the market's window-printing stories and dump their furniture for one reader.

Deliverable 1 of `plan/handoff-market-fit.md`, registered in `PREREG.md` beside this file.
Reads the cached LitRPG shards through `corpus_io` under the MirrorBench interpreter, finds
every story that prints at least one window (the system-displays census's window: a run of
two or more furniture lines, `system_displays.runs_of`), draws a seeded sample, and writes
two things. `sample.json` is committed: the seed, the population, and per sampled story the
counts and the shared field labels the displays census already publishes
(`field_labels.json`'s eighty). The furniture dump is never committed: `--dump` points
outside the tree, one file per story, and one reader turns it into `shapes.jsonl` by hand.
No model, no bar, and no corpus text in anything committed (RS1).

    export MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe
    PYTHONUTF8=1 "$MB" research/quality-measurement/system-fit/sample.py --dump <scratch dir>

`--files <glob>...` reads local text files instead of the shards (each file one chapter, its
parent directory the story), which is how the four shelf anchors are tallied and how the
script is exercised without a corpus pass; `--out` then names the tally file.
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
DISPLAYS = RESEARCH / "system-displays"
sys.path.insert(0, str(RESEARCH))
sys.path.insert(0, str(DISPLAYS))
import changes  # noqa: E402  # isort: skip
import corpus_io  # noqa: E402  # isort: skip
import evolution  # noqa: E402  # isort: skip
import field_labels as fl  # noqa: E402  # isort: skip
import growth  # noqa: E402  # isort: skip
import system_displays as sd  # noqa: E402  # isort: skip

SEED = 20260903
SIZE = 60
#: How much furniture one story's dump keeps: the first window lines and the first notice
#: lines in release order, after duplicates are dropped. A story that prints its window forty
#: times prints one shape, and a reader reads it once.
MAX_WINDOW_LINES = 110
MAX_NOTICE_LINES = 50


def shared_labels(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {row["label"] for row in data["labels_by_stories"]}


def units_from_files(patterns: list[str]):
    for pattern in patterns:
        for name in sorted(glob.glob(pattern)):  # noqa: PTH207  # an absolute pattern
            path = Path(name)
            yield corpus_io.Unit(
                unit_id=f"file:{path.stem}",
                source="file",
                text=path.read_text(encoding="utf-8", errors="replace"),
                position=0,
                work_id=path.parent.name,
            )


def furniture_of(text: str) -> tuple[list[list[str]], list[str]]:
    """The windows (as blocks of furniture lines) and the single notice lines of a chapter,
    by the displays census's own reading of what a window is."""
    lines = text.splitlines()
    classes = sd.classify_lines(text)
    windows: list[list[str]] = []
    notices: list[str] = []
    for start, end in sd.runs_of(classes, lines):
        furniture = [i for i in range(start, end) if classes[i] == "furniture"]
        if not furniture:
            continue
        block = [lines[i] for i in furniture]
        if len(furniture) == 1:
            notices.append(block[0])
        else:
            windows.append(block)
    return windows, notices


class Story:
    def __init__(self, work_id: str) -> None:
        self.work_id = work_id
        self.chapters = 0
        self.words = 0
        self.windows = 0
        self.widest = 0
        self.fields_seen = 0
        self.zero_fields = 0
        self.labels: dict[str, Counter[str]] = defaultdict(Counter)
        self.notices: Counter[str] = Counter()
        self.choice_screens = 0
        self.options: list[int] = []
        self.item_boxes = 0
        self.quest_cards = 0
        self.names: set[str] = set()
        self.verbs: Counter[str] = Counter()
        self.arrows: Counter[str] = Counter()
        self.furniture_lines = 0
        #: The dump: (release date, unit id, kind, line), kept in memory only for the sample.
        self.window_lines: list[tuple[str, str, list[str]]] = []
        self.notice_lines: list[tuple[str, str, str]] = []

    def add(self, unit: corpus_io.Unit) -> None:
        self.chapters += 1
        self.words += len(sd.cadence.prose_only(unit.text, version=sd.VERSION).split())
        windows, notices = furniture_of(unit.text)
        stamp = unit.released_at or ""
        for block in windows:
            self.windows += 1
            self.furniture_lines += len(block)
            fields = [pair for line in block for pair in sd.fields_on(line)]
            self.widest = max(self.widest, len(fields))
            self.fields_seen += len(fields)
            for label, value in fields:
                key = fl.normalise_label(label)
                if key and len(key) <= 30:
                    self.labels[key][fl.kind_of(value)] += 1
                if sd.is_zero(value):
                    self.zero_fields += 1
                match = changes._ARROW.search(value)
                if match is not None:
                    try:
                        a = float(match.group("start").replace(",", ""))
                        b = float(match.group("end").replace(",", ""))
                    except ValueError:
                        continue
                    if match.group("end")[0] in "+-":
                        way = "up" if b > 0 else ("down" if b < 0 else "same")
                    else:
                        way = "up" if b > a else ("down" if b < a else "same")
                    self.arrows[way] += 1
            head = " ".join(sd._inner(line) for line in block[:2])
            option_lines = sum(1 for line in block if sd._OPTION_LINE.match(sd._inner(line)))
            if sd._CHOICE_WORD.search(sd._inner(block[0])) or option_lines >= 2:
                self.choice_screens += 1
                self.options.append(option_lines if option_lines >= 2 else max(0, len(block) - 1))
            if sd._ITEM.search(head):
                self.item_boxes += 1
            if sd._QUEST.search(head):
                self.quest_cards += 1
            self.window_lines.append((stamp, unit.unit_id, block))
        for line in notices:
            self.furniture_lines += 1
            self.notices[sd.notice_family(line)] += 1
            self.notice_lines.append((stamp, unit.unit_id, line))
        for line in [line for block in windows for line in block] + notices:
            for match in growth._NAME.finditer(line):
                name = " ".join(match.group(1).split())
                if 1 <= len(name.split()) <= growth._MAX_WORDS:
                    self.names.add(name.lower())
            for family, pattern in evolution.FAMILIES.items():
                if pattern.search(line):
                    self.verbs[family] += 1

    def tally(self, shared: set[str], prefix: str) -> dict[str, Any]:
        labels = {
            label: dict(kinds.most_common())
            for label, kinds in sorted(self.labels.items())
            if label in shared
        }
        other = [kinds for label, kinds in self.labels.items() if label not in shared]
        other_kinds: Counter[str] = Counter()
        for kinds in other:
            other_kinds.update(kinds)
        return {
            "story": f"{prefix}:{self.work_id}",
            "chapters": self.chapters,
            "words": self.words,
            "windows": self.windows,
            "widest_window": self.widest,
            "fields_seen": self.fields_seen,
            "zero_fields": self.zero_fields,
            "labels": labels,
            "other_labels": len(other),
            "other_label_kinds": dict(other_kinds.most_common()),
            "notices": dict(self.notices),
            "choice_screens": self.choice_screens,
            "options_per_screen": self.options,
            "item_boxes": self.item_boxes,
            "quest_cards": self.quest_cards,
            "bracketed_names": len(self.names),
            "verb_families": dict(self.verbs),
            "arrows": dict(self.arrows),
            "furniture_lines": self.furniture_lines,
        }

    def dump(self, path: Path, tally: dict[str, Any]) -> int:
        """The furniture one reader reads, in release order, duplicates dropped, capped."""
        seen: set[str] = set()
        out: list[str] = [json.dumps(tally, ensure_ascii=False), "", "## windows"]
        kept = 0
        for _stamp, unit_id, block in sorted(self.window_lines, key=lambda item: item[:2]):
            fresh = []
            for line in block:
                key = sd.cadence.normalise(line).casefold()
                if key in seen:
                    continue
                seen.add(key)
                fresh.append(line)
            if not fresh:
                continue
            if kept + len(fresh) > MAX_WINDOW_LINES:
                fresh = fresh[: max(0, MAX_WINDOW_LINES - kept)]
                if not fresh:
                    break
            out.append(f"[{unit_id}]")
            out.extend(fresh)
            out.append("")
            kept += len(fresh)
        out.append("## notices")
        notices = 0
        for _stamp, unit_id, line in sorted(self.notice_lines, key=lambda item: item[:2]):
            key = sd.cadence.normalise(line).casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(f"[{unit_id}] {line}")
            notices += 1
            if notices >= MAX_NOTICE_LINES:
                break
        path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
        return kept + notices


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--size", type=int, default=SIZE)
    parser.add_argument("--limit", type=int, default=0, help="chapters to read; 0 is all")
    parser.add_argument("--files", nargs="*", help="local text files instead of the shards")
    parser.add_argument("--dump", type=Path, required=True, help="a directory outside the tree")
    parser.add_argument("--out", type=Path, default=HERE / "sample.json")
    parser.add_argument("--labels", type=Path, default=DISPLAYS / "field_labels.json")
    args = parser.parse_args(argv)

    shared = shared_labels(args.labels)
    stories: dict[str, Story] = {}
    read = 0
    units = (
        units_from_files(args.files)
        if args.files
        else corpus_io.royalroad_chapters(limit=args.limit)
    )
    for unit in units:
        read += 1
        stories.setdefault(unit.work_id, Story(unit.work_id)).add(unit)
        if read % 5000 == 0:
            print(f"  read {read} chapters, {len(stories)} stories", file=sys.stderr, flush=True)

    population = sorted(work_id for work_id, story in stories.items() if story.windows >= 1)
    if args.files:
        sample = population
    else:
        sample = sorted(
            random.Random(args.seed).sample(population, min(args.size, len(population)))
        )
    prefix = "shelf" if args.files else "rr"
    args.dump.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for work_id in sample:
        story = stories[work_id]
        tally = story.tally(shared, prefix)
        tally["dump_lines"] = story.dump(args.dump / f"{work_id}.txt", tally)
        rows.append(tally)
    out = {
        "registered": sha256((HERE / "PREREG.md").read_bytes()).hexdigest(),
        "run_at": datetime.now(tz=UTC).isoformat(),
        "classifier": f"progression_cadence {sd.VERSION}",
        "source": "files" if args.files else "royalroad shards",
        "seed": args.seed,
        "chapters_read": read,
        "stories_read": len(stories),
        "population_with_windows": len(population),
        "sample_size": len(sample),
        "stories": rows,
    }
    args.out.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    print(
        f"chapters {read}; stories {len(stories)}; with windows {len(population)}; "
        f"sampled {len(sample)}; dump in {args.dump}"
    )
    for row in rows:
        print(
            f"  {row['story']:14} ch={row['chapters']:3} windows={row['windows']:3} "
            f"widest={row['widest_window']:2} names={row['bracketed_names']:3} "
            f"choice={row['choice_screens']} item={row['item_boxes']} quest={row['quest_cards']} "
            f"notices={sum(row['notices'].values())} dump={row['dump_lines']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
