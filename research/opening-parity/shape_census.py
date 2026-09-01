"""Code-only counts over the manifest's openings: how each is told, and where its system shows.

Descriptive, model-free, and the same counters for ours and the summits. Five counts per
opening, each a plain integer or position and none a quality:

- `words`, `paragraphs`
- `first_person_marks`: `I`, `I'm`, `my` as whole words — how much of the chapter is told from
  inside the person
- `interior_verbs`: thought, wondered, realised, knew, decided and their kin — the narrator
  reporting a mind
- `machine_lines`: lines the book prints as a machine (`[STATUS]`, `[OFFER]`, any bracketed
  tag), and the word position of the first
- `blurb_words`

Run over the registered manifest; no third-party text is printed, only counts:

    uv run python research/opening-parity/shape_census.py --manifest MANIFEST

where MANIFEST is `research/opening-parity/manifest.json`.

The market anchors are read from the shelf and the derived folder (both gitignored); the
counts may be committed, the text never is (RS1, and the derived folder's own rule).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

_FIRST_PERSON = re.compile(r"\b(?:I|I'm|I\u2019m|my)\b")
_INTERIOR = re.compile(
    r"\b(?:thought|wondered|realized|realised|figured|knew|felt|decided|hoped|guessed|"
    r"supposed|reckoned)\b",
    re.IGNORECASE,
)
_MACHINE_LINE = re.compile(r"^\s*\[[A-Z][A-Z ]*\]")


def census(text: str) -> dict[str, Any]:
    words = text.split()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    lines = text.splitlines()
    first_machine: int | None = None
    seen = 0
    machine = 0
    for line in lines:
        if _MACHINE_LINE.match(line):
            machine += 1
            if first_machine is None:
                first_machine = seen
        seen += len(line.split())
    return {
        "words": len(words),
        "paragraphs": len(paragraphs),
        "first_person_marks": len(_FIRST_PERSON.findall(text)),
        "interior_verbs": len(_INTERIOR.findall(text)),
        "machine_lines": machine,
        "first_machine_line_at_word": first_machine,
    }


def run(manifest_path: Path, root: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for side in ("ours", "summits"):
        for entry in manifest[side]:
            chapter = (root / entry["chapter"]).read_text(encoding="utf-8")
            row = {"side": side, "label": entry["label"], **census(chapter)}
            blurb = entry.get("blurb")
            row["blurb_words"] = (
                len((root / blurb).read_text(encoding="utf-8").split()) if blurb else None
            )
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    rows = run(Path(args.manifest), Path(args.root))
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    header = (
        "side", "label", "words", "paras", "1st-person", "interior", "machine", "first@", "blurb",
    )
    print(" | ".join(header))
    for row in rows:
        print(" | ".join(str(row[key]) for key in (
            "side", "label", "words", "paragraphs", "first_person_marks", "interior_verbs",
            "machine_lines", "first_machine_line_at_word", "blurb_words",
        )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
