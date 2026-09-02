"""Sentence-length census: the shelf's placed openings beside every chapter on the library shelf.

No model, no score, no bar. Prints, per chapter, the count of sentences, the mean and median
length in words, the 90th and 95th percentiles, the longest, and the share of sentences over
thirty, forty and fifty words, plus the count per thousand words over the shelf's own longest
sentence. Uses the tells module's own sentence splitter and machine-line filter, so the figures
are the ones the counter at the drafting ladder's seat would see (stage-0 §199, §199.4).

    uv run python tools/sentence_census.py --library book-library --limit 3

`--limit` is how many placed openings form the shelf, in the shelf's own order, the same flag
the ladder runs under; the shelf's longest sentence is the long family's threshold.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean, median

from litharness.application.exemplars import load_shelf
from litharness.domain import tells


def lengths(text: str) -> list[int]:
    out: list[int] = []
    for paragraph in text.split("\n\n"):
        if not paragraph.strip() or tells.is_machine_line(paragraph):
            continue
        out.extend(len(s.split()) for s in tells.sentences_of(paragraph) if s.split())
    return out


def row(name: str, text: str, long_words: float) -> str:
    found = sorted(lengths(text))
    if not found:
        return f"{name:40} (no sentences)"
    n = len(found)
    words = tells.word_count(text) or 1
    p90 = found[int(0.9 * (n - 1))]
    p95 = found[int(0.95 * (n - 1))]
    shares = "  ".join(
        f">{bound}w {sum(1 for x in found if x > bound) / n:5.1%}" for bound in (30, 40, 50)
    )
    over = 1000.0 * sum(1 for x in found if x > long_words) / words
    return (
        f"{name:40} n={n:4} mean={mean(found):5.1f} median={median(found):4.0f} "
        f"p90={p90:3} p95={p95:3} max={found[-1]:3}  {shares}  over shelf/1k={over:4.1f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--library", type=Path, default=Path("book-library"))
    parser.add_argument("--limit", type=int, default=3, help="placed openings on the shelf")
    args = parser.parse_args(argv)
    shelf = load_shelf(args.library, limit=args.limit)
    if shelf is None or not shelf.exemplars:
        print(f"no shelf under {args.library}")
        return 1
    longest = float(max(tells.longest_sentence(ex.chapter) for ex in shelf.exemplars))
    print(f"shelf ({len(shelf.exemplars)} placed openings; longest sentence {longest:.0f} words):")
    for exemplar in shelf.exemplars:
        print(row("  " + exemplar.name, exemplar.chapter, longest))
    print("library chapters:")
    for folder in sorted(p for p in args.library.iterdir() if p.is_dir()):
        chapter = folder / "chapters" / "Chapter1.txt"
        if chapter.exists():
            print(row("  " + folder.name, chapter.read_text(encoding="utf-8"), longest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
