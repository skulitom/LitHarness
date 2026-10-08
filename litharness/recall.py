"""Long-context recall: passages of chapters the plan request cannot carry whole, found by EmbeddingGemma 2 on a
local Ollama. Each chapter's vectors are kept beside it, and a changed chapter or model embeds it again."""
from __future__ import annotations

import json
import math
import operator
from pathlib import Path
import re
import urllib.request

from . import files

MODEL, URL, DIMS, PASSAGE, BUDGET = "embeddinggemma-2:270m", "http://127.0.0.1:11434/api/embed", 256, 900, 6_000


def embed(texts: list[str]) -> list[list[float]]:
    """Unit vectors from the local Ollama, cut to DIMS (Matryoshka) and renormalized; nothing leaves the box."""
    request = urllib.request.Request(URL, json.dumps({"model": MODEL, "input": texts}).encode("utf-8"),
                                     {"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            vectors = json.loads(response.read())["embeddings"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f"Recall from chapter 3 on needs {MODEL} on Ollama at {URL}: {error}") from error
    if len(vectors) != len(texts):
        raise ValueError(f"Ollama returned {len(vectors)} vectors for {len(texts)} texts")
    return [[round(x / norm, 5) for x in v[:DIMS]] for v in vectors for norm in [math.hypot(*v[:DIMS]) or 1.0]]


def passages(chapter: str) -> list[str]:
    """Paragraphs joined in order up to PASSAGE characters; a scene break always ends a passage."""
    out, current = [], ""
    for paragraph in (p.strip() for p in re.split(r"\n[ \t]*\n", chapter) if p.strip()):
        if current and (paragraph == "***" or len(current) + len(paragraph) > PASSAGE):
            out, current = out + [current], ""
        current = current if paragraph == "***" else f"{current}\n\n{paragraph}".strip()
    return out + [current] * bool(current)


def index(root: Path, k: int) -> list[tuple[str, list[float]]]:
    """Chapter k's passages with their vectors, embedded once per chapter text, model and cut."""
    body, cache = files.read(root / f"ch{k:02d}" / "chapter.md"), root / f"ch{k:02d}" / "vectors.json"
    stamp = {"model": MODEL, "dims": DIMS, "passage": PASSAGE, "chapter": files.sha(body.encode())}
    found = files.load(cache) if cache.is_file() else {}
    if {name: found.get(name) for name in stamp} != stamp:
        chunks = passages(body)
        found = stamp | {"passages": chunks, "vectors": embed([f"title: none | text: {c}" for c in chunks])}
        files.save(cache, found)
    return list(zip(found["passages"], found["vectors"]))


def recall(root: Path, n: int, query: str, room: int) -> str:
    """For chapter n's plan: passages of chapters 1 to n-2 closest to any line of the query, best first until
    room (at most BUDGET) characters are used, then put back in story order. Before chapter 3 there are none."""
    lines = [line.strip(" \t-*") for line in query.splitlines() if not line.startswith("#")]
    lines, room = [line for line in lines if len(line) > 12], min(room, BUDGET)
    if n < 3 or room < PASSAGE or not lines:
        return ""
    pool = [(k, i, text, vector) for k in range(1, n - 1) for i, (text, vector) in enumerate(index(root, k))]
    asked = embed([f"task: search result | query: {line}" for line in lines])
    score = {(k, i): max(sum(map(operator.mul, q, v)) for q in asked) for k, i, _, v in pool}
    chosen, used = [], 0
    for k, i, text, _ in sorted(pool, key=lambda p: -score[p[0], p[1]]):
        if used + len(text) + 7 <= room:
            chosen, used = chosen + [(k, i, text)], used + len(text) + 7
    return "\n\n***\n\n".join(text for _, _, text in sorted(chosen))
