"""Tells census: every family, narration beside speech, the shelf's placed openings beside ours.

No model, no score, no bar. For each chapter and each family the counter locates (stage-0
§199 to §199.6), the count of located sentences, how many of those sit inside quoted speech,
and the narration rate per thousand words; the shelf's own rates are the ceilings the drafting
ladder holds a page to. The speech split uses the same quoted-span reading the counter uses.

    uv run python tools/tells_census.py --library book-library --limit 3

`--limit` is how many placed openings form the shelf, in the shelf's own order, the same flag
the ladder runs under. `--all-quoted` also prints the count the counter would have given
before §199.6, with speech included, so the rule's effect on each chapter is visible.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from litharness.application.exemplars import load_shelf
from litharness.domain import tells


def _located_in_speech(text: str, long_words: float | None) -> dict[str, tuple[int, int]]:
    """Per family: (located by the counter, located sentences that are mostly speech)."""
    paragraphs = text.split("\n\n")
    out: dict[str, tuple[int, int]] = {}
    for family in tells.FAMILIES:
        found = [i for i in tells.locate(text, long_words=long_words) if i.family == family]
        speech = sum(1 for i in found if tells.is_speech(paragraphs[i.paragraph], i.text))
        out[family] = (len(found), speech)
    return out


def row(name: str, text: str, long_words: float | None) -> str:
    words = tells.word_count(text) or 1
    cells = []
    for family, (found, speech) in _located_in_speech(text, long_words).items():
        cells.append(f"{family[:7]:7} {found:3} ({speech:2} sp) {1000.0 * found / words:4.1f}/1k")
    return f"{name:34} " + "  ".join(cells)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--library", type=Path, default=Path("book-library"))
    parser.add_argument("--limit", type=int, default=3, help="placed openings on the shelf")
    args = parser.parse_args(argv)
    shelf = load_shelf(args.library, limit=args.limit)
    if shelf is None or not shelf.exemplars:
        print(f"no shelf under {args.library}")
        return 1
    limits = tells.ceilings(exemplar.chapter for exemplar in shelf.exemplars)
    long_words = limits[tells.LONG_WORDS] if limits else None
    print(f"shelf ({len(shelf.exemplars)} placed openings); ceilings per 1k words:")
    if limits:
        ceilings = {k: v for k, v in limits.items() if k != tells.LONG_WORDS}
        print("  " + "  ".join(f"{k[:7]:7} {v:4.1f}" for k, v in ceilings.items()))
    for exemplar in shelf.exemplars:
        print(row("  " + exemplar.name, exemplar.chapter, long_words))
    print("library chapters (located, of which mostly speech, rate per 1k):")
    for folder in sorted(p for p in args.library.iterdir() if p.is_dir()):
        chapter = folder / "chapters" / "Chapter1.txt"
        if chapter.exists():
            print(row("  " + folder.name[:32], chapter.read_text(encoding="utf-8"), long_words))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
