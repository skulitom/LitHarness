"""Sample located hits of every bench.py detector family, 20 from ours and 20 from genre chapters 1-3.

    python experiments/2026-09-28-genre-baseline/audit.py SLUG
The hits carry genre text, so they go to $LITHARNESS_HOME/corpora/genre/audit-hits.json, never into the repo.
Precision is judged per family and per half; a family under 0.8 on either half is reported as loose.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bench  # noqa: E402
from litharness import files  # noqa: E402

PER_HALF, SEED = 20, 20260928
FAMILIES = {
    "furniture": lambda s: bench.furniture(s),
    "progression": lambda s: bool(bench.LVL.search(s) or bench.CAP.search(s) or bench.DELTA.search(s)),
    "trade": lambda s: bool(bench.LEX["trade"].search(s)),
    "violence": lambda s: bool(bench.LEX["viol"].search(s)),
    "interior": lambda s: bool(bench.LEX["inter"].search(s)),
    "skips": lambda s: bool(bench.LEX["skips"].search(s)),
    "numbers": lambda s: bool(bench.LEX["numbers"].search(s)),
}


def hits(texts: list[tuple[str, str]], family: str) -> list[dict]:
    """(source, line) pairs whose line fires the family; the match is named so a reviewer judges that word."""
    test, found = FAMILIES[family], []
    for source, text in texts:
        for number, line in enumerate(bench.normalize(text).split("\n"), 1):
            line = line.strip()
            if line and test(line):
                pattern = {"trade": "trade", "violence": "viol", "interior": "inter", "skips": "skips",
                           "numbers": "numbers"}.get(family)
                match = bench.LEX[pattern].search(line).group() if pattern else ""
                found.append({"source": f"{source}:{number}", "line": line[:400], "match": match})
    return found


def main(slug: str) -> None:
    rng = random.Random(SEED)
    root = files.home() / "serials" / slug
    ours = [(f"{p.parent.name}/chapter.md", files.read(p)) for p in sorted(root.glob("ch[0-9][0-9]/chapter.md"))]
    manifest = files.load(bench.MANIFEST)["fictions"]
    top = [f for f in manifest if f["stratum"] == "top" and f["litrpg"]]
    genre = [(f"{f['fiction_id']}/ch{n:02d}", files.read(bench.CORPUS / str(f["fiction_id"]) / f"ch{n:02d}.txt"))
             for f in top for n in (1, 2, 3)]
    out = {}
    for family in FAMILIES:
        mine, theirs = hits(ours, family), hits(genre, family)
        out[family] = {"ours": rng.sample(mine, min(PER_HALF, len(mine))),
                       "genre": rng.sample(theirs, min(PER_HALF, len(theirs)))}
    path = bench.CORPUS / "audit-hits.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(path, {f: (len(v["ours"]), len(v["genre"])) for f, v in out.items()})


if __name__ == "__main__":
    main(sys.argv[1])
