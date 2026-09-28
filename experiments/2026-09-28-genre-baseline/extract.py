"""Extract the genre corpus bench.py places our chapters in, from the cached RoyalRoad-1.61M shards.

Run with the MirrorBench interpreter (it has pyarrow) under runs/box.lock:
    C:/DEV/MirrorBench/.venv/Scripts/python.exe experiments/2026-09-28-genre-baseline/extract.py select|text|port
Text lands only in $LITHARNESS_HOME/corpora/genre/<fiction_id>/chNN.txt. This folder keeps a text-free
manifest.json (ids, titles, strata, chapter ids, word counts, sha256) and port.json (numbers only).
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SNAPSHOT = Path.home() / ".cache/huggingface/hub/datasets--OmniAICreator--RoyalRoad-1.61M/snapshots" / \
    "0e4df3f22999a7b7fa13b1e7564a09b5f3eb964e" / "data"
DERIVED = Path("C:/DEV/LitHarness-archive/tree/research/quality-measurement/derived/rr-chapters/chapters.parquet")
CORPUS = Path(os.environ.get("LITHARNESS_HOME") or Path.home() / "LitHarness-data") / "corpora" / "genre"
SELECTION = CORPUS / "selection.json"  # the intermediate stays beside the text, out of the repo
# The descriptor half of the incumbent's voice-descriptor run (stage-0 150.1): they aimed a writer, so no
# ours-versus-market comparison may include them.
QUARANTINE = {47017, 47021, 47118, 47127, 47199, 47434, 47621, 47923, 47982, 47986, 48117, 48157, 48176, 48402,
              48951, 49031, 49032, 107121, 107125, 107252, 107692, 108451, 108458, 109037, 109390, 109427}
GENRE, OFF = {"LitRPG", "Progression"}, {"LitRPG", "Progression", "GameLit"}
TOP_FOLLOWERS, OFF_PER_ERA, SEED, CHAPTERS = 1000, 30, 20260928, 12
ORDINAL = re.compile(r"^\s*(?:chapter|ch\.?|episode|part)\s*0*(\d+)\b", re.I)
LATE_BOOK = re.compile(r"^\s*(?:book|vol(?:ume)?|b)\s*0*([2-9]|\d\d+)\b", re.I)
NUMBER = re.compile(r"(\d+)")
PARATEXT = re.compile(r"^\s*(?:\(?\s*(?:a/?n|author'?s?\s+notes?|t/?n|translator'?s?\s+notes?)\b|.*\b(?:patreon|discord|"
                      r"ko-?fi|advance(?:d)?\s+chapters?|topwebfiction|top\s+web\s+fiction|rate\s+and\s+review)\b)", re.I)
META = ["fiction_id", "title", "author", "tags", "warnings", "followers", "chapter_id", "chapter_title", "release_datetime"]


def shards() -> list[Path]:
    return sorted(SNAPSHOT.glob("train-*.parquet"))


def era(year: str) -> str:
    return {"2021": "2021-22", "2022": "2021-22", "2024": "2024-25", "2025": "2024-25"}.get(year, "other")


def openings(rows: list[dict]) -> tuple[list[dict] | None, str]:
    """Chapters 1..12 in reading order, by title ordinals or else a clean release order; None for stubs."""
    rows = sorted(rows, key=lambda r: (r["release_datetime"] or "", r["chapter_id"]))
    ordinals: dict[int, dict] = {}
    for row in rows:
        found = ORDINAL.match(row["chapter_title"] or "")
        if found:
            ordinals.setdefault(int(found[1]), row)
    if {1, 2, 3} <= ordinals.keys():
        run = [n for n in range(1, CHAPTERS + 1) if n in ordinals]
        run = run[:next((i for i, n in enumerate(run) if n != i + 1), len(run))]
        return [ordinals[n] for n in run], "ordinals"
    picked, numbers = rows[:CHAPTERS], []
    for row in picked[:3]:
        title = row["chapter_title"] or ""
        if LATE_BOOK.match(title) or "stub" in title.lower():
            return None, "late book or stub"
        found = NUMBER.search(title)
        numbers.append(int(found[1]) if found else None)
    known = [n for n in numbers if n is not None]
    if len(picked) < 3 or (known and known[0] > 1) or any(b - a != 1 for a, b in zip(known, known[1:])):
        return None, "not an opening"
    return picked, "release order"


def select() -> None:
    fictions, where = collections.defaultdict(list), {}
    for shard in shards():
        handle = pq.ParquetFile(shard)
        for group in range(handle.num_row_groups):
            for row in handle.read_row_group(group, columns=META).to_pylist():
                fictions[row["fiction_id"]].append(row)
                where[row["chapter_id"]] = (shard.name, group)
    candidates, reasons = [], collections.Counter()
    for fid, rows in fictions.items():
        head, tags = rows[0], set(json.loads(rows[0]["tags"] or "[]"))
        stratum = "top" if tags & GENRE else "off" if not tags & OFF else None
        if stratum is None or (head["followers"] or 0) < TOP_FOLLOWERS:
            continue
        if fid in QUARANTINE or "AI-Assisted Content" in json.loads(head["warnings"] or "[]") or "stub" in (head["title"] or "").lower():
            reasons["quarantined, declared AI or stub"] += 1
            continue
        chapters, how = openings(rows)
        if chapters is None:
            reasons[how] += 1
            continue
        year = min((r["release_datetime"] or "9999")[:4] for r in rows)
        candidates.append({"fiction_id": fid, "title": head["title"], "author": head["author"], "stratum": stratum,
                           "litrpg": "LitRPG" in tags, "era": era(year), "followers": head["followers"], "how": how,
                           "chapters": [{"n": i + 1, "chapter_id": int(r["chapter_id"]), "shard": where[r["chapter_id"]][0],
                                         "row_group": where[r["chapter_id"]][1]} for i, r in enumerate(chapters)]})
    candidates.sort(key=lambda c: -c["followers"])
    seen, chosen = set(), []
    for c in candidates:  # one fiction per author: the most followed
        if (c["stratum"], c["author"]) not in seen:
            seen.add((c["stratum"], c["author"]))
            chosen.append(c)
    top = [c for c in chosen if c["stratum"] == "top"]
    rng, off = random.Random(SEED), []
    for name in ("2021-22", "2024-25"):
        pool = [c for c in chosen if c["stratum"] == "off" and c["era"] == name]
        off += rng.sample(pool, min(OFF_PER_ERA, len(pool)))
    for c in off:
        c["chapters"] = c["chapters"][:3]
    for c in top + off:
        c.pop("author")
    SELECTION.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"snapshot": SNAPSHOT.parent.name, "seed": SEED, "rejected": dict(reasons), "fictions": top + off},
              open(SELECTION, "w", encoding="utf-8"), indent=1)
    print(f"top {len(top)} ({sum(c['litrpg'] for c in top)} LitRPG-tagged), off-genre {len(off)}; rejected {dict(reasons)}")


def text() -> None:
    chosen = json.load(open(SELECTION, encoding="utf-8"))
    wanted = collections.defaultdict(set)
    for c in chosen["fictions"]:
        for ch in c["chapters"]:
            wanted[(ch["shard"], ch["row_group"])].add(ch["chapter_id"])
    texts = {}
    for (shard, group), ids in sorted(wanted.items()):
        for row in pq.ParquetFile(SNAPSHOT / shard).read_row_group(group, columns=["chapter_id", "text"]).to_pylist():
            if int(row["chapter_id"]) in ids:
                texts[int(row["chapter_id"])] = row["text"] or ""
    manifest, dropped = [], collections.Counter()
    for c in chosen["fictions"]:
        chapters = []
        for ch in c["chapters"]:
            lines = texts.get(ch["chapter_id"], "").replace("\r\n", "\n").split("\n")
            kept = [line for line in lines if not PARATEXT.match(line)]
            body = "\n".join(kept).strip() + "\n"
            paragraphs = [line for line in kept if line.strip()]
            words = len(re.findall(r"\w+", body))
            if ch["n"] <= 3 and (words < 300 or len(paragraphs) < 10):
                break
            path = CORPUS / str(c["fiction_id"]) / f"ch{ch['n']:02d}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode("utf-8"))
            chapters.append({"n": ch["n"], "chapter_id": ch["chapter_id"], "words": words,
                             "paratext_lines": len(lines) - len(kept), "sha256": hashlib.sha256(body.encode()).hexdigest()})
        if len(chapters) < 3:
            dropped["chapter 1-3 under 300 words or 10 paragraphs"] += 1
            continue
        manifest.append({k: c[k] for k in ("fiction_id", "title", "stratum", "litrpg", "era", "followers", "how")} |
                        {"chapters": chapters})
    head = json.dumps({"snapshot": chosen["snapshot"], "seed": chosen["seed"], "dropped": dict(dropped)})[:-1]
    rows = ",\n".join(json.dumps(f, separators=(",", ":")) for f in manifest)  # one fiction a line keeps it small
    (HERE / "manifest.json").write_text(f'{head}, "fictions": [\n{rows}\n]}}\n', encoding="utf-8")
    print(f"kept {len(manifest)} fictions, {sum(len(f['chapters']) for f in manifest)} chapters; dropped {dict(dropped)}")


def port() -> None:
    """Does bench.py's compact counter land near the incumbent's published market numbers (155.1, 202)?"""
    sys.path.insert(0, str(ROOT))
    import bench
    table = pq.read_table(DERIVED, columns=["fiction_id", "release_datetime", "litrpg", "quarantined", "text"])
    rows = [r for r in table.to_pylist() if r["litrpg"] and not r["quarantined"]]
    measured = [(r, bench.measure(r["text"] or "")) for r in rows]
    events = sorted(m["events_v0_k"] for _, m in measured)
    q = lambda p: events[min(len(events) - 1, int(p * len(events)))]
    first = [m["first_event_word"] for _, m in measured]
    by_fiction = collections.defaultdict(list)
    for r, m in measured:
        by_fiction[r["fiction_id"]].append((r["release_datetime"] or "", m))
    early = [m for items in by_fiction.values() for _, m in sorted(items, key=lambda x: x[0])[:3]]
    result = {"chapters": len(rows), "fictions": len(by_fiction),
              "events_k_median_p75_p90": [q(0.5), q(0.75), q(0.9)], "incumbent_155": [0.0, 1.26, 3.60],
              "share_without_event": sum(e == 0 for e in events) / len(events), "incumbent_155_without": 0.510,
              "event_in_first_500": sum(f is not None and f < 500 for f in first) / len(first), "incumbent_155_500": 0.225,
              "earliest3_any_display": sum(m["system_lines"] > 0 for m in early) / len(early),
              "incumbent_202_any_display": 0.31, "earliest3_chapters": len(early)}
    json.dump(result, open(HERE / "port.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    {"select": select, "text": text, "port": port}[sys.argv[1]]()
