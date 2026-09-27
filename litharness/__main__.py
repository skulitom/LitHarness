"""python -m litharness VERB. Exit codes: 0 done, 1 needs a person, 2 fault."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from . import checks, files, serial, sheet, transport


def check(path: Path, stage: str, slug: str | None) -> tuple[list[str], str]:
    """Every deterministic check on any text; without a serial it is chapter 1 with no plan or bible."""
    raw, root = files.read(path).replace("\r\n", "\n"), files.home() / "serials" / slug if slug else None

    def stored(name: str) -> str:
        return files.read(root / name) if root and (root / name).is_file() else ""

    found = re.fullmatch(r"ch(\d\d)", path.resolve().parent.name)
    inside = bool(root and found and path.resolve().parent.parent == root.resolve())
    n = int(found[1]) if inside else 0 if stage == "plan" and not root else 1
    bible = stored("ch00/bible.md")
    ranks = sheet.ladder(checks.section(bible, "System") or "")
    if stage != "chapter":
        return checks.hard(stage, raw, n=n, ranks=ranks), ""
    body, counts = checks.normalize(raw)
    plan, before = stored(f"ch{n:02d}/plan.md"), sheet.read(stored(f"ch{n - 1:02d}/sheet.txt"))
    context = {"target": files.load(root / "serial.json")["words"] if root else 1500, "n": n,
               "before": before, "ranks": ranks}
    fails = checks.hard("chapter", body, raw=raw, rise_plan=checks.planned(plan), **context)
    return fails, checks.report(body, raw=raw, plan=plan, bible=bible, normalized=counts, **context)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="litharness", description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)
    opening = verbs.add_parser("opening", help="plan and draft one opening chapter in two calls")
    opening.add_argument("--brief", type=Path, required=True)
    opening.add_argument("--words", type=int, default=4000)
    opening.add_argument("--resume", action="store_true")
    test = verbs.add_parser("check", help="every deterministic check on any text; no calls")
    test.add_argument("file", type=Path)
    test.add_argument("--stage", choices=("pitch", "plan", "chapter"), default="chapter")
    test.add_argument("--serial")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if args.verb == "check":
        try:
            fails, report = check(args.file, args.stage, args.serial)
        except (OSError, ValueError) as fault:
            print(f"fault: {fault}", file=sys.stderr)
            return 2
        print("\n".join(fails or ["hard checks: all pass"]) + ("\n\n" + report if report else ""))
        return 1 if fails else 0
    box = files.box_lock()
    try:
        files.lock(box, f"opening {args.brief.stem}")
    except files.Held as held:
        print(f"box held by: {held}", file=sys.stderr)
        return 1
    try:
        root, result = serial.opening(args.brief, args.words, transport.native_binary(), args.resume)
    except (files.Held, FileExistsError) as error:
        print(f"{error}; pass --resume to continue, or wait for the holder", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    finally:
        files.unlock(box)
    print(f"Saved {result['word_count']} words to {root / 'chapter.md'}")
    if result["length_warning"]:
        print("Length is outside the requested range; preserved without automatic rewriting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
