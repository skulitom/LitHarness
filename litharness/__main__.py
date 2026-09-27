"""python -m litharness VERB. Exit codes: 0 done, 1 needs a person, 2 fault."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import files, serial, transport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="litharness", description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)
    opening = verbs.add_parser("opening", help="plan and draft one opening chapter in two calls")
    opening.add_argument("--brief", type=Path, required=True)
    opening.add_argument("--words", type=int, default=4000)
    opening.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
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
