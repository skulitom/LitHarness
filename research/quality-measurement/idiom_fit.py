"""How much of a listing is phrasing this genre actually uses. No model, only counting.

**Five instruments have now failed at the same thing**, and each failed differently enough that
the shape is legible. The pairwise screen returns our listings over published ones at 15/16,
16/16 with no declared taste, and **24 of 24 against the operator's own named favourites**. The
uncashable-term counter puts us at half the market's rate. Three quote-a-span probes come back
blind, blind, and *summits worse*. Every one of them is a language model reading text, and every
one prefers ours.

**What the last probe did show is where the difference is.** It flagged, in ours: *"One line
nerfed whatever used to keep monsters out of buildings"*, *"drop loot that works"*, *"two rules
in that changelog contradict each other"*. And in the operator's favourites: *"gifted with a
system"*, *"carve a path to greatness"*, *"the Guild of Arcane Regulation"*. Good recall on the
defect, no precision at all — and the difference between the two lists is not clarity. Every
phrase in the second list is **something people in this genre write**. The first list is not.

That is the operator's complaint, stated exactly, in every session:

> *"wtf is a patch of notes, nobody says that"* — `patch notes` is the term; `a patch of notes`
> is not English.
> *"lines are not things that get nerfed, incorrect use of terminology"*.
> *"keys don't take, they open things"*.
> *"'dropped flush' isn't a phrase I heard anyone ever say"*.
> *"sounds like somebody trying to describe a litrpg they read once"*.

Not unclear, not vague — **wrong in the way a fluent speaker of the genre hears instantly and a
model that produced it does not.** A model asked whether its own collocation is idiomatic is the
wrong instrument on principle, which is why every LLM probe has been blind to it.

**So this one has no model in it.** The corpus is 1.61M RoyalRoad chapters; it *is* a record of
what this genre's writers actually write. A phrase our listing uses that appears nowhere in tens
of millions of words of the genre is a phrase the genre does not use, and that is a count rather
than an opinion.

**Streamed against the candidates rather than tabulated.** Building a full n-gram table over the
shards costs gigabytes; the n-grams under test number a few thousand, so one pass counts exactly
those and holds nothing else. That is also what makes the result cheap to re-run per listing.

    C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/idiom_fit.py \\
        --summits derived/summit-set.json \
        --ours runs/pilots/pilot9/listing.json runs/pilots/pilot10/listing.json

The MirrorBench interpreter, because it reads the parquet shards (CLAUDE.md).

### The reading, fixed before the run

Per listing, the share of its content bigrams and trigrams that appear **zero** times in the
sampled genre text.

| | reading |
| --- | --- |
| ours > summits, intervals disjoint | the counter sees what the operator sees.
  First instrument in this project to do so, and the first that is not a model |
| intervals overlap | blind like the other five, and reported as such |
| summits > ours | it counts something the operator's favourites do more of. Withdrawn |

A named sanity check runs beside it and is not optional: the phrases the operator quoted as
wrong must score unseen, and the phrases they called clear must not. A counter that fails that
has not measured idiom, whatever the tiers do.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import statistics
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"
RESULTS = HERE / "results"

CACHE = (
    "C:/Users/artem/.cache/huggingface/hub/datasets--OmniAICreator--RoyalRoad-1.61M"
    "/snapshots/*/data/*.parquet"
)

#: Words carrying no collocation information. A bigram of two of these is grammar, not phrasing,
#: and counting it would swamp the signal with `of the` and `and then`.
_GLUE = frozenset(
    [
        "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "by", "for", "with",
        "from", "as", "is", "was", "are", "were", "be", "been", "being", "it", "its", "he", "she",
        "they", "them", "his", "her", "their", "you", "your", "i", "my", "me", "we", "our", "this",
        "that", "these", "those", "not", "no", "nor", "so", "if", "then", "than", "when", "while",
        "into", "out", "up", "down", "over", "under", "again", "once", "here", "there", "all",
        "any", "both", "each", "few", "more", "most", "other", "some", "such", "only", "own",
        "same", "too", "very", "can", "will", "just", "do", "does", "did", "done", "have", "has",
        "had", "having", "would", "could", "should", "may", "might", "must", "shall", "about",
        "after", "before", "between", "through", "during", "above", "below", "off", "across",
        "around"
    ]
)

_TOKEN = re.compile(r"[a-z']+")

#: Built from code points so this file stays ASCII; the curly apostrophe is one letter to a
#: reader and two tokens to a naive split.
_CURLY = chr(0x2019)
_NAME_TOKEN = "[A-Za-z'" + _CURLY + "]+"


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold().replace("\u2019", "'"))


#: Publishing furniture that appears in a blurb and is not phrasing: a serial's own status
#: notes, its shop links, its author's pen name. Measured 2026-08-26 — the first bigram run tied
#: the two tiers because the summits' unseen spans were `alex gilbert`, `bob stubbed`, `com max`
#: and `kindle select` while ours were `loot works`, `line nerfed` and `changelog contradict`.
#: Equal counts, and only one of the two lists is about how anybody writes.
_BOILERPLATE = frozenset(
    [
        "stubbed", "kindle", "amazon", "audible", "patreon", "discord", "royalroad", "rr",
        "com", "www", "http", "https", "chapter", "chapters", "update", "updates", "schedule",
        "release", "released", "week", "weekly", "daily", "upload", "uploads", "book",
        "series", "volume", "arc", "author", "pen",
    ]
)


def grams(
    text: str, sizes: tuple[int, ...] = (2, 3), *, drop_names: bool = True
) -> set[tuple[str, ...]]:
    """Content n-grams: non-glue at each end, and no proper noun or publishing furniture.

    Anchored on both ends so that `of the` never enters and `patch of notes` does — the glue in
    the middle is exactly where a mis-collocation lives.

    **Names are dropped and that is the whole difference between blind and not.** A blurb naming
    Andross, Callum or Alex Gilbert has unseen bigrams for a reason that is not phrasing, and a
    counter that cannot tell `alex gilbert` from `line nerfed` is counting how unusual somebody's
    signal is capitalisation mid-sentence; a word capitalised only at the start
    of a sentence is kept, since that is punctuation rather than a name.
    """
    words = tokens(text)
    names: set[str] = set()
    if drop_names:
        raw = re.findall(_NAME_TOKEN, text)
        starts = set()
        for index, word in enumerate(raw):
            if index and raw[index - 1][-1:] not in {".", "!", "?"} and word[:1].isupper():
                names.add(word.casefold().replace(_CURLY, "'"))
            elif word[:1].isupper():
                starts.add(word.casefold())
        # A word only ever seen sentence-initially is not evidence of a name.
        names -= starts - names
        names |= _BOILERPLATE
    out: set[tuple[str, ...]] = set()
    for size in sizes:
        for index in range(len(words) - size + 1):
            span = tuple(words[index : index + size])
            if span[0] in _GLUE or span[-1] in _GLUE:
                continue
            if names & set(span):
                continue
            out.add(span)
    return out


def count_in_corpus(
    wanted: set[tuple[str, ...]], shards: list[str], chapter_limit: int
) -> dict[tuple[str, ...], int]:
    """One streaming pass, counting only the n-grams under test. Memory is the candidate set."""
    import pyarrow.parquet as pq

    seen: dict[tuple[str, ...], int] = dict.fromkeys(wanted, 0)
    by_first: dict[str, list[tuple[str, ...]]] = {}
    for span in wanted:
        by_first.setdefault(span[0], []).append(span)

    read = 0
    for path in shards:
        table = pq.read_table(path, columns=["text"])
        for row in table.to_pylist():
            body = row.get("text") or ""
            if not body:
                continue
            words = tokens(body)
            for index, word in enumerate(words):
                for span in by_first.get(word, ()):
                    size = len(span)
                    if tuple(words[index : index + size]) == span:
                        seen[span] += 1
            read += 1
            if chapter_limit and read >= chapter_limit:
                return seen
    return seen


def score(
    text: str, counts: dict[tuple[str, ...], int], sizes: tuple[int, ...] = (2, 3)
) -> dict[str, Any]:
    spans = grams(text, sizes)
    unseen = sorted(" ".join(span) for span in spans if counts.get(span, 0) == 0)
    words = max(len(text.split()), 1)
    return {
        "grams": len(spans),
        "unseen": len(unseen),
        "unseen_share": round(len(unseen) / max(len(spans), 1), 4),
        "unseen_per_1k": round(1000 * len(unseen) / words, 1),
        "examples": unseen[:12],
    }


def band(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return (float("nan"),) * 3
    mean = statistics.mean(values)
    if len(values) < 2:
        return (mean, mean, mean)
    half = 1.96 * statistics.stdev(values) / (len(values) ** 0.5)
    return (round(mean - half, 4), round(mean, 4), round(mean + half, 4))


#: The named check. Left column: phrases the operator quoted as wrong. Right: phrases they called
#: clear, or that the last probe wrongly flagged in their own favourites. A counter that does not
#: split these has not measured idiom.
WRONG = ["a patch of notes", "one line nerfed", "loot that works", "dropped flush",
         "keys don't take", "repro steps"]
RIGHT = ["carve a path to greatness", "gifted with a system", "cast any spells",
         "magical gift", "the supernatural is real", "master magic"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summits", default=str(DERIVED / "summit-set.json"))
    parser.add_argument("--ours", nargs="+", required=True)
    parser.add_argument("--each", type=int, default=8)
    parser.add_argument("--chapters", type=int, default=60000, help="0 for every cached chapter")
    parser.add_argument(
        "--sizes",
        default="2,3",
        help="n-gram sizes. Trigrams are sparse: at 40,000 chapters the named check failed "
        "because half of every text's trigrams were unseen, including the operator's own "
        "favourites' — a sample-size failure rather than a counter failure",
    )
    parser.add_argument("--out", type=Path, default=RESULTS / "idiom-fit.json")
    args = parser.parse_args(argv)

    texts: list[dict[str, str]] = []
    for row in json.loads(Path(args.summits).read_text(encoding="utf-8"))[: args.each]:
        texts.append({"tier": "summits", "id": row["source"],
                      "text": f"{row['title']}\n\n{row['listing']}"})
    for raw in args.ours:
        bundle = json.loads(Path(raw).read_text(encoding="utf-8"))
        for key in ("draft", "listing"):
            if bundle.get(key):
                texts.append({"tier": "ours", "id": f"{Path(raw).parent.name}:{key}",
                              "text": f"{bundle.get('title') or ''}\n\n{bundle[key]}"})

    sizes = tuple(int(part) for part in args.sizes.split(",") if part.strip())
    wanted: set[tuple[str, ...]] = set()
    for entry in texts:
        wanted |= grams(entry["text"], sizes)
    # The named-check phrases are scored whole, whatever `--sizes` is, since the point of
    # them is the phrase and not its parts.
    probes = {phrase: tuple(tokens(phrase)) for phrase in WRONG + RIGHT}
    for parts in (tokens(p) for p in WRONG + RIGHT):
        wanted |= {tuple(parts[i : i + 2]) for i in range(len(parts) - 1)}
    wanted |= set(probes.values())

    shards = sorted(glob.glob(CACHE))  # noqa: PTH207 - an absolute cache path, not a tree walk
    print(f"{len(texts)} text(s), {len(wanted)} n-gram(s) under test, {len(shards)} shard(s)")
    counts = count_in_corpus(wanted, shards, args.chapters)
    corpus_hits = sum(counts.values())
    print(f"counted against {args.chapters or 'all'} chapters; {corpus_hits} total hit(s)")

    print("\nnamed check — phrases the operator quoted as wrong:")
    for phrase in WRONG:
        print(f"  {counts.get(probes[phrase], 0):>7}x  {phrase}")
    print("phrases the operator called clear:")
    for phrase in RIGHT:
        print(f"  {counts.get(probes[phrase], 0):>7}x  {phrase}")

    rows = [entry | score(entry["text"], counts, sizes) for entry in texts]
    print()
    for row in rows:
        print(f"  {row['tier']:8} {row['id'][:30]:<30} unseen {row['unseen']:>3}/{row['grams']:<3}"
              f" = {row['unseen_share']:.3f}   {row['examples'][:3]}")

    report: dict[str, Any] = {"chapters": args.chapters, "sizes": list(sizes), "tiers": {}}
    for tier in ("ours", "summits"):
        vals = [r["unseen_share"] for r in rows if r["tier"] == tier]
        report["tiers"][tier] = {"n": len(vals), "interval": band(vals), "shares": vals}
    report["named_check"] = {
        "wrong": {p: counts.get(probes[p], 0) for p in WRONG},
        "right": {p: counts.get(probes[p], 0) for p in RIGHT},
    }
    report["rows"] = [{k: v for k, v in r.items() if k != "text"} for r in rows]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    olow, omean, ohigh = report["tiers"]["ours"]["interval"]
    slow, smean, shigh = report["tiers"]["summits"]["interval"]
    verdict = ("OURS WORSE, disjoint" if olow > shigh
               else "summits worse, disjoint" if slow > ohigh else "overlap - blind")
    print(f"\n  unseen share   ours {omean} [{olow}, {ohigh}]   "
          f"summits {smean} [{slow}, {shigh}]   {verdict}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
