"""Build the competitor pool the measurement readers spend their slot against.

**This is the corpus side of `litharness --rivals`, and it lives here for RS1's reason.**
Nothing under `src/litharness/` may reference a corpus (`tests/test_corpus_leak_audit.py`,
where the package-side check landed on 2026-08-28; until then the citation named a file that
checked something else), so the package takes a JSON file and refuses any row that does not
clear `domain/rivals.admit`. This is the only thing that knows where those rows come from.

**What a rival has to be**, from the operator, 2026-08-25/26: a **real** listing, **rated above
4 stars**, **in our genre**, and **a new one each time** so the pool samples the market rather
than pitting every book against one competitor. The parquet shards carry all four facts —
`description`, `overall_score`, `ratings`, `tags` — so nothing here is inferred.

**The output is prose somebody else wrote and is never committed.** It goes under
`derived/`, which `.gitignore` already covers for exactly this class: *"derived text of
third-party prose ... excerpt-bearing"*. What may be committed about a run is the digest and
the counts, which `--report` prints.

    C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/rival_pool.py

The MirrorBench interpreter, because this reads the parquet shards (CLAUDE.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))

import corpus_io  # noqa: E402

from litharness.domain import rivals as rivals_mod  # noqa: E402

DERIVED = HERE / "derived"

#: RoyalRoad's own tags, mapped onto the genre labels `domain/rivals.GENRES` admits. A tag this
#: does not name is not a genre this readership reads, which is a refusal rather than a gap.
TAG_GENRE: dict[str, str] = {
    "litrpg": "litrpg",
    "gamelit": "litrpg",
    "progression": "progression fantasy",
    "portal fantasy / isekai": "isekai",
    "reincarnation": "reincarnation",
    "dungeon": "dungeon core",
    "cultivation": "cultivation",
    "wuxia": "cultivation",
    "xianxia": "cultivation",
    "post apocalyptic": "system apocalypse",
}

#: The market's own listing length, measured under §138 on ten listings the operator supplied:
#: 40 to 146 words, median 100. A `description` far outside that is a different artifact — a
#: full author's note, an index of arcs — and pitting a hundred-word blurb against one is a
#: comparison of formats.
MIN_WORDS = 40
MAX_WORDS = 200


def _clean(description: str) -> str:
    """The blurb as a reader meets it: the HTML the field carries, unwrapped, and nothing else.

    Deliberately crude. A description with markup left in reads as a different artifact from
    ours in a way that has nothing to do with writing, and stripping tags is the whole of what
    is needed — anything cleverer would be editing somebody else's listing.
    """
    import re

    text = re.sub(r"<br\s*/?>", "\n", description, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def genre_of(tags: list[str]) -> str | None:
    """The first admitted genre this book is filed under, or None."""
    for tag in tags:
        named = TAG_GENRE.get(str(tag).strip().casefold())
        if named is not None:
            return named
    return None


def _percentile_of(value: float, population: list[int]) -> float:
    """Where a floor sits in the distribution it was chosen from. Reported, never fitted."""
    if not population:
        return float("nan")
    return 100.0 * sum(1 for item in population if item < value) / len(population)


def build(
    shards: tuple[int, ...],
    limit: int,
    *,
    max_followers: int = 0,
    skip_admit: bool = False,
) -> tuple[list[dict[str, Any]], list[int]]:
    """One row per fiction, deduplicated, every one of which clears `rivals.admit`.

    Deduplicated on `fiction_id` because the shards are keyed by *chapter*: a serial with 400
    chapters would otherwise be 400 rivals and the pool would be one book.
    """
    import pyarrow.parquet as pq

    columns = [
        "fiction_id", "title", "tags", "description",
        "overall_score", "ratings", "followers", "favorites", "total_views",
    ]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    #: Every genre-tagged fiction's following, admitted or not — the population the floor is
    #: reported against, so the bar can be checked rather than believed.
    genre_followers: list[int] = []
    for shard in shards:
        table = pq.read_table(corpus_io._shard_path(shard), columns=columns)
        for row in table.to_pylist():
            fiction = str(row.get("fiction_id") or "")
            if not fiction or fiction in seen:
                continue
            genre = genre_of(json.loads(row.get("tags") or "[]"))
            if genre is None:
                continue
            seen.add(fiction)
            genre_followers.append(int(row.get("followers") or 0))
            blurb = _clean(str(row.get("description") or ""))
            if not MIN_WORDS <= len(blurb.split()) <= MAX_WORDS:
                continue
            candidate = {
                "title": str(row.get("title") or "").strip(),
                "listing": blurb,
                "rating": row.get("overall_score"),
                "ratings": row.get("ratings"),
                "followers": row.get("followers"),
                "genre": genre,
                "source": f"royalroad:{fiction}",
            }
            if max_followers and int(row.get("followers") or 0) > max_followers:
                continue
            if not skip_admit:
                try:
                    rivals_mod.admit(candidate)
                except rivals_mod.IllegalRival:
                    continue
            rows.append(candidate)
            if limit and len(rows) >= limit:
                return rows, genre_followers
    return rows, genre_followers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", default="3,30", help="comma-separated shard numbers")
    parser.add_argument("--limit", type=int, default=60, help="0 for every admitted fiction")
    parser.add_argument("--out", type=Path, default=DERIVED / "rivals.json")
    parser.add_argument(
        "--max-followers",
        type=int,
        default=0,
        help="ceiling on followers, for building the LOW tier of a gradient control. Implies "
        "--skip-admit, since `rivals.admit` refuses anything under the floor by design",
    )
    parser.add_argument(
        "--skip-admit",
        action="store_true",
        help="emit rows that do not clear `rivals.admit`. Only ever for a control set: these "
        "are not rivals and may not be handed to `--rivals`",
    )
    args = parser.parse_args(argv)

    shards = tuple(int(part) for part in args.shards.split(",") if part.strip())
    rows, genre_followers = build(
        shards,
        args.limit,
        max_followers=args.max_followers,
        skip_admit=args.skip_admit or bool(args.max_followers),
    )
    if not rows:
        print("no fiction cleared the bar; nothing written", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    digest = sha256(
        "\x00".join(sorted(row["source"] for row in rows)).encode()
    ).hexdigest()[:16]
    follows = sorted(int(row["followers"] or 0) for row in rows)
    words = sorted(len(row["listing"].split()) for row in rows)
    # Numbers and a digest, which is what may be committed about a pool of somebody else's prose.
    print(f"{len(rows)} rival(s) -> {args.out}")
    print(f"  pool digest {digest}")
    print(f"  followers  min {follows[0]}  median {follows[len(follows)//2]}  max {follows[-1]}")
    print(f"  words      min {words[0]}  median {words[len(words)//2]}  max {words[-1]}")
    print(f"  floor {rivals_mod.MIN_FOLLOWERS} followers sits at the "
          f"{_percentile_of(rivals_mod.MIN_FOLLOWERS, genre_followers):.1f}th percentile of "
          f"{len(genre_followers)} genre-tagged fiction(s) in these shards")
    by_genre: dict[str, int] = {}
    for row in rows:
        by_genre[row["genre"]] = by_genre.get(row["genre"], 0) + 1
    print(f"  genres   {dict(sorted(by_genre.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
