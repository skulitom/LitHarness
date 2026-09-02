"""The reassembly instrument: shuffled paragraphs, a reader's ordering, scored by rank correlation.

`PREREG.md` beside this file owns the design and the reading fixed before spend; this script
buys the cells and writes the numbers. Every measurable is code. Nothing here tunes a reader.

    uv run python research/quality-measurement/reassembly/run.py --dry-run
    uv run python research/quality-measurement/reassembly/run.py --run --yes

Six stimuli (two of ours, the four placed openings), the first thirty paragraphs of each,
three seeds each, one plain reader. Results land in `results.json`, raw answers in `raw.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from litharness.domain.generation import CompletionRequest
from litharness.providers import build_default_registry

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIBRARY = REPO / "book-library"
STIMULI = {
    "ours-draw1": LIBRARY / "the-ratchet-counts-down" / "chapters" / "Chapter1.txt",
    "ours-draw2": LIBRARY / "the-ratchet-counts-down--0993282c" / "chapters" / "Chapter1.txt",
    "shelf-primal-hunter": LIBRARY / "PrimalHunter" / "Chapter1.txt",
    "shelf-defiance": LIBRARY / "DefianceOfTheFall" / "Chapter1.txt",
    "shelf-randidly": LIBRARY / "RandidlyGhosthound" / "Chapter1.txt",
    "shelf-gam3": LIBRARY / "TheGam3" / "Chapter1.txt",
}
PARAGRAPHS = 30
SEEDS = (11, 23, 37)
PROFILE = "reassembly.v0"
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["order"],
    "properties": {"order": {"type": "array", "items": {"type": "string"}}},
}
SYSTEM = (
    "You are reading one chapter of a serial novel whose paragraphs have been shuffled. Put "
    "them back in the order the chapter reads. Return only JSON of the form "
    '{"order": ["P03", "P01", ...]}, every label exactly once and nothing else.'
)


def paragraphs_of(text: str) -> list[str]:
    parts = [part.strip() for part in text.replace("\r\n", "\n").split("\n\n") if part.strip()]
    if len(parts) < 8:
        # A file with single newlines between paragraphs (the shelf's Gam3), as the parity
        # driver treated it.
        parts = [part.strip() for part in text.replace("\r\n", "\n").split("\n") if part.strip()]
    return parts[:PARAGRAPHS]


def label(index: int) -> str:
    return f"P{index + 1:02d}"


def shuffled(paragraphs: list[str], seed: int) -> list[int]:
    order = list(range(len(paragraphs)))
    random.Random(seed).shuffle(order)
    return order


def render(paragraphs: list[str], order: list[int]) -> CompletionRequest:
    body = "\n\n".join(f"[{label(index)}]\n{paragraphs[index]}" for index in order)
    return CompletionRequest(
        prompt=f"The shuffled paragraphs:\n\n{body}",
        system=SYSTEM,
        schema=SCHEMA,
        max_output_tokens=800,
        profile=PROFILE,
        call_class="generation",
        timeout_seconds=300.0,
    )


def repair(answer: list[str], labels: list[str], shown: list[str]) -> tuple[list[str], bool]:
    """Every label once: repeats dropped, omissions appended in the shuffled order; flagged."""
    seen: list[str] = []
    for item in answer:
        if item in labels and item not in seen:
            seen.append(item)
    missing = [item for item in shown if item not in seen]
    return seen + missing, bool(missing) or len(seen) != len(answer)


def kendall_tau(answer: list[str], labels: list[str]) -> float:
    """Tau-a over every pair: 1 is the true order, 0 chance, negative reversed."""
    position = {item: index for index, item in enumerate(answer)}
    n = len(labels)
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if position[labels[i]] < position[labels[j]]:
                concordant += 1
            else:
                discordant += 1
    pairs = n * (n - 1) / 2
    return (concordant - discordant) / pairs if pairs else 0.0


def adjacent_kept(answer: list[str], labels: list[str]) -> float:
    position = {item: index for index, item in enumerate(answer)}
    kept = sum(
        1
        for i in range(len(labels) - 1)
        if position[labels[i + 1]] == position[labels[i]] + 1
    )
    return kept / (len(labels) - 1) if len(labels) > 1 else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    texts = {
        name: paragraphs_of(path.read_text(encoding="utf-8")) for name, path in STIMULI.items()
    }
    for name, parts in texts.items():
        words = sum(len(p.split()) for p in parts)
        print(f"{name:20s} {len(parts):2d} paragraphs, {words:5d} words")
    if not args.run:
        print("dry run; nothing bought")
        return 0
    if not args.yes:
        print("refusing to spend without --yes")
        return 2
    registry = build_default_registry()
    rows: list[dict[str, object]] = []
    with (HERE / "raw.jsonl").open("a", encoding="utf-8") as sink:
        for name, parts in texts.items():
            labels = [label(i) for i in range(len(parts))]
            for seed in SEEDS:
                order = shuffled(parts, seed)
                shown = [label(i) for i in order]
                result, _ = registry.complete(render(parts, order))
                parsed = result.parsed if isinstance(result.parsed, dict) else {}
                raw_answer = [str(x) for x in (parsed.get("order") or [])]
                answer, flagged = repair(raw_answer, labels, shown)
                row = {
                    "stimulus": name,
                    "seed": seed,
                    "tau": round(kendall_tau(answer, labels), 4),
                    "adjacent": round(adjacent_kept(answer, labels), 4),
                    "flagged": flagged,
                    "answer": raw_answer,
                    "shown": shown,
                }
                sink.write(json.dumps(row) + "\n")
                rows.append(row)
                note = " (repaired)" if flagged else ""
                print(f"  {name} seed {seed}: tau {row['tau']} adjacent {row['adjacent']}{note}")
    summary: dict[str, dict[str, float]] = {}
    for name in STIMULI:
        mine = [row for row in rows if row["stimulus"] == name]
        taus = [float(row["tau"]) for row in mine]
        adjs = [float(row["adjacent"]) for row in mine]
        summary[name] = {
            "mean_tau": round(sum(taus) / len(taus), 4),
            "min_tau": round(min(taus), 4),
            "mean_adjacent": round(sum(adjs) / len(adjs), 4),
            "paragraphs": len(texts[name]),
        }
    (HERE / "results.json").write_text(
        json.dumps({"seeds": SEEDS, "summary": summary}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
