"""Export the 20 fitness texts (from scratchpad COPIES of the stores) and the current-pipeline
candidate books to texts.json. Read-only with respect to the repository: the stores opened are
copies under scratchpad/power/fitness_copy, bytecode writing is disabled so no __pycache__ lands
in the repo, and chapter files are only read."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(r"C:\DEV\LitHarness")
QM = REPO / "research" / "quality-measurement"
sys.path.insert(0, str(QM))
OUT = Path(__file__).resolve().parent

import feed_substrate  # noqa: E402  (imports ablate, bcr, corpus_io, feed_core; no side effects)

fitness = feed_substrate.fitness_texts(OUT / "fitness_copy")


def chapter_files_txt(chapters_dir: Path) -> list[Path]:
    # numeric sort (NOT cost_that_bites.volume_text's lexical p.name sort)
    files = list(chapters_dir.glob("Chapter*.txt"))
    return sorted(files, key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))


def chapter_files_md(book_dir: Path) -> list[Path]:
    files = list(book_dir.glob("chapter-*.md"))
    return sorted(files, key=lambda p: int(p.stem.split("-")[1]))


candidates: dict[str, dict] = {}


def add(name: str, files: list[Path], source: str, lexical_files: list[Path] | None = None):
    text = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in files)
    entry = {"source": source, "chapters": len(files), "text": text,
             "files": [str(p.relative_to(REPO)) for p in files]}
    if lexical_files is not None:
        entry["lexical_order_differs"] = [p.name for p in lexical_files] != [p.name for p in files]
    candidates[name] = entry


# 1. full-book trial A1 (the-last-anchorage), 24 chapters: both the md drafts and the library export
a1 = REPO / "runs" / "full-book-trial-20260919" / "books" / "A1"
add("full-book-trial-A1 (chapter-N.md)", chapter_files_md(a1), "runs/full-book-trial-20260919/books/A1")
lib = a1 / "library" / "the-last-anchorage" / "chapters"
add("full-book-trial-A1 (library ChapterN.txt)", chapter_files_txt(lib), str(lib.relative_to(REPO)),
    lexical_files=sorted(lib.glob("Chapter*.txt"), key=lambda p: p.name))

# 2. connected-chapters 2026-09-16 books
for book in sorted((REPO / "runs" / "connected-chapters-20260916" / "books").iterdir()):
    if book.is_dir():
        add(f"connected-chapters-{book.name} (chapter-N.md)", chapter_files_md(book), str(book.relative_to(REPO)))

# 3. Loadstitch (Wren) in book-library
ls = REPO / "book-library" / "loadstitch" / "chapters"
add("loadstitch (ChapterN.txt)", chapter_files_txt(ls), str(ls.relative_to(REPO)))

(OUT / "texts.json").write_text(
    json.dumps({"fitness": fitness, "candidates": candidates}, ensure_ascii=False), encoding="utf-8"
)
print(len(fitness), "fitness texts;", len(candidates), "candidates")
for name, text in fitness:
    print(name, len(text.split()))
for name, entry in candidates.items():
    print(name, entry["chapters"], len(entry["text"].split()), entry.get("lexical_order_differs"))
