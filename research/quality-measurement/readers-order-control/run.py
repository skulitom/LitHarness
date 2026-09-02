"""The readers' order control: the same chapter ordered, paragraph-shuffled and sentence-shuffled.

`PREREG.md` beside this file owns the design and the decision table; this script buys the cells
and writes the numbers. Every measurable is code. Nothing here tunes a reader.

    uv run python research/quality-measurement/readers-order-control/run.py --dry-run
    uv run python research/quality-measurement/readers-order-control/run.py --run --yes

The chapter is read off the shelf's pastable page (scene 2 is the text after the scene break);
the rival is drawn from the derived pool on a fixed key so every cell names the same book.
Results land in `results.json` beside this file and the raw answers in `raw.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from litharness.application import readers
from litharness.domain import rivals as rivals_mod
from litharness.domain import text as text_mod
from litharness.providers import build_default_registry

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHAPTER = REPO / "book-library" / "the-ratchet-counts-down" / "chapters" / "Chapter1.txt"
RIVALS = REPO / "research" / "quality-measurement" / "derived" / "rivals.json"
SEED = 20260902
COPIES = ("ordered", "paragraphs", "sentences")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z][a-z']{3,}")
_STOP = frozenset(
    (
        "that", "this", "with", "from", "they", "them", "their", "there", "then", "than",
        "were", "when", "what", "have", "been", "into", "over", "your", "will", "would",
        "could", "about", "which", "where", "while", "after", "before", "because",
    )
)


def scene_two(chapter: str) -> str:
    parts = chapter.split("\n* * *\n")
    return parts[-1].strip()


def shuffled_paragraphs(text: str, seed: int) -> str:
    paragraphs = [part for part in text.split("\n\n") if part.strip()]
    movable = [index for index, part in enumerate(paragraphs) if not part.startswith("[")]
    order = movable[:]
    random.Random(seed).shuffle(order)
    out = list(paragraphs)
    for slot, source in zip(movable, order, strict=True):
        out[slot] = paragraphs[source]
    return "\n\n".join(out)


def shuffled_sentences(text: str, seed: int) -> str:
    rng = random.Random(seed)
    out = []
    for part in text.split("\n\n"):
        if not part.strip() or part.startswith("["):
            out.append(part)
            continue
        sentences = [s for s in _SENTENCE_END.split(part.strip()) if s]
        rng.shuffle(sentences)
        out.append(" ".join(sentences))
    return "\n\n".join(out)


def content_words(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if word not in _STOP}


def overlap(expectation: str, continuation: str) -> float:
    a, b = content_words(expectation), content_words(continuation)
    return len(a & b) / len(a | b) if a | b else 0.0


def specificity(expectation: str) -> float:
    words = expectation.split()
    if not words:
        return 0.0
    numbers = len(re.findall(r"\b\d[\d,./]*\b", expectation))
    names = len(re.findall(r"(?<![.!?]\s)\b[A-Z][a-z]{2,}\b", expectation))
    return 100.0 * (numbers + names) / len(words)


def build(chapter: str) -> dict[str, dict[str, str]]:
    scene = scene_two(chapter)
    copies = {
        "ordered": scene,
        "paragraphs": shuffled_paragraphs(scene, SEED),
        "sentences": shuffled_sentences(scene, SEED),
    }
    built: dict[str, dict[str, str]] = {}
    for name, full in copies.items():
        passage = text_mod.stop_point(full)
        built[name] = {"passage": passage, "continuation": full[len(passage) :].strip()}
    return built


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    chapter = CHAPTER.read_text(encoding="utf-8")
    built = build(chapter)
    pool = rivals_mod.admit_all(json.loads(RIVALS.read_text(encoding="utf-8")))
    rival = rivals_mod.draw(pool, "readers-order-control")
    for name, copy in built.items():
        passage_words = len(copy["passage"].split())
        continuation_words = len(copy["continuation"].split())
        print(f"{name:11s} passage {passage_words:4d} words, continuation {continuation_words:4d}")
    print(f"rival: {rival.title}")
    if not args.run:
        print("dry run; nothing bought")
        return 0
    if not args.yes:
        print("refusing to spend without --yes")
        return 2
    registry = build_default_registry()
    raw = HERE / "raw.jsonl"
    rows: list[dict[str, object]] = []
    with raw.open("a", encoding="utf-8") as sink:
        for name, copy in built.items():
            for reader in readers.READERS:
                if reader.pool == readers.MEASUREMENT:
                    request = readers.render_choice_request(reader, copy["passage"], rival.title)
                else:
                    request = readers.render_anticipation_request(reader, copy["passage"])
                result, _ = registry.complete(request)
                parsed = result.parsed if isinstance(result.parsed, dict) else {}
                row: dict[str, object] = {
                    "copy": name,
                    "reader": reader.reader_id,
                    "pool": reader.pool,
                    "answer": parsed,
                    "text": result.text,
                }
                if reader.pool == readers.STEERING:
                    expectation = str(parsed.get("expect_next") or "")
                    row["overlap"] = round(overlap(expectation, copy["continuation"]), 4)
                    row["specificity"] = round(specificity(expectation), 2)
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows.append(row)
                said = str(parsed.get("next") or parsed.get("choice") or "")[:20]
                print(f"  {name} {reader.reader_id}: {said} {row.get('overlap', '')}")
    summary: dict[str, dict[str, float]] = {}
    for name in COPIES:
        mine = [row for row in rows if row["copy"] == name]
        choices = []
        for row in mine:
            if row["pool"] != readers.MEASUREMENT:
                continue
            answer = row["answer"] if isinstance(row["answer"], dict) else {}
            choices.append(str(answer.get("next") or answer.get("choice") or ""))
        carried = sum(1 for choice in choices if "carry" in choice or "continue" in choice)
        overlaps = [float(row["overlap"]) for row in mine if "overlap" in row]
        specs = [float(row["specificity"]) for row in mine if "specificity" in row]
        summary[name] = {
            "carried_on": carried,
            "answered": len(choices),
            "mean_overlap": round(sum(overlaps) / len(overlaps), 4) if overlaps else 0.0,
            "mean_specificity": round(sum(specs) / len(specs), 2) if specs else 0.0,
        }
    (HERE / "results.json").write_text(
        json.dumps({"rival": rival.title, "seed": SEED, "summary": summary}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
