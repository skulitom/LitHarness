"""Genre-lexicon overlap for a forged world: how much of its vocabulary the shelf already has.

**Measurement only, and no bar.** Nothing here feeds a prompt, a directive or any generation
path. `plan/world-architect.md` §6 registers this as M2 and registers it *without* a threshold,
because a ceiling on overlap would be a bar on a distribution nobody has measured — and this
repository already has the cautionary case. `opening_proper_nouns` was nominated for a named
reader defect and then placed the complained-about chapter at the **68.5th percentile** of
published LitRPG openings, so it did not discriminate the defect it was built for. The forge's K
candidates are a distribution and this reports it.

**The RoyalRoad `description` column has never been read by anything in this repository.**
`corpus_io.royalroad_chapters` requests twelve columns and that is not one of them; a grep for
`description` across `src/` and `research/` finds only `argparse` and an unrelated promise field.
So this is a new read of an existing local corpus, on the measurement side of RS1: blurb and tag
text enters a *counter* and never a generation prompt.

**Two venvs, because one of them has pyarrow and the other is the repository** — the pattern
`opening_counters.py` established:

    C:/DEV/MirrorBench/.venv/Scripts/python.exe \
        research/quality-measurement/world_lexicon.py --substrate royalroad
    uv run python research/quality-measurement/world_lexicon.py \
        --substrate worlds --forge pilot2/direct/forge.json

`--substrate report` merges the two and prints the overlap distribution over the K candidates.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))

#: **The lexicon lives in the gitignored derived-text root, and that is a rule rather than a
#: preference.** It is 17,541 words distilled out of 22,397 third-party blurbs; a word list is
#: not reproducible prose, but `corpus_leak_audit.DERIVED_TEXT_ROOTS` exists precisely so that
#: nobody has to re-litigate where the line falls each time, and the audit refuses a walk that
#: cannot cover a committed list this long anyway. What is committed is the *report* — the
#: overlap shares — which names no blurb and quotes nothing.
DERIVED = HERE / "derived"
LEXICON_JSON = DERIVED / "world-lexicon-royalroad.json"
WORLDS_JSON = HERE / "world-lexicon-worlds.json"

#: The pinned snapshot `corpus_io.SNAPSHOT_REVISION` names, restated rather than imported: this
#: file runs under a venv where `litharness` is importable but `corpus_io`'s own module path is
#: not guaranteed, and `corpus_io`'s docstring makes the same argument for duplicating
#: `era_cohort` — "any disagreement is a finding; a silent shared import would hide one".
SNAPSHOT_REVISION = "0e4df3f22999a7b7fa13b1e7564a09b5f3eb964e"
CACHE = (
    Path.home()
    / ".cache/huggingface/hub/datasets--OmniAICreator--RoyalRoad-1.61M"
    / "snapshots"
    / SNAPSHOT_REVISION
    / "data"
)

#: Every shard that happens to be cached. Not a fixed list, because the point of the lexicon is
#: coverage rather than comparability against a prior run — and the file records which shards it
#: read so a later run can tell whether it is looking at the same shelf.
SHARD_GLOB = "train-*-of-00047.parquet"

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")

#: Words that are in every blurb on the shelf and say nothing about a world. Kept deliberately
#: short: a long stop list is a way of quietly deciding the answer, and the counter is crude on
#: purpose (`domain/worlds.py::key_nouns` says so about its own half).
_STOP_WORDS = (
    "the and for with that this from they them their there when what will your you have has "
    "had was were are but not all one two into out about after before over under more most "
    "some any can could would should may might must who whom whose which while than then now "
    "new world story book chapter novel series read reading write writing author fiction"
)
_STOP = frozenset(_STOP_WORDS.split())

#: How many distinct fictions a word must appear in before it counts as the shelf's vocabulary.
#: **Five, and the reason is the direction of the error.** At a floor of one, a single author's
#: invented noun joins the lexicon and every later world that coined the same word reads as
#: derivative; at a high floor the lexicon collapses to English. Five is a placed number, stated
#: as placed, and the sensitivity is reported alongside the headline so the choice is visible.
DEFAULT_FLOOR = 5


def _shards() -> list[Path]:
    return sorted(CACHE.glob(SHARD_GLOB)) if CACHE.is_dir() else []


def build_lexicon(floor: int = DEFAULT_FLOOR) -> dict[str, object]:
    """Words that appear in at least `floor` distinct fictions' blurbs, plus every tag word.

    One row per chapter with fiction metadata denormalised onto it, so the fiction is
    deduplicated on `fiction_id` before anything is counted — otherwise a fiction with 900
    cached chapters would weigh 900 times a fiction with one.
    """
    import pyarrow.parquet as pq  # only this substrate needs it

    shards = _shards()
    if not shards:
        raise SystemExit(f"no cached shards under {CACHE}")
    seen: set[int] = set()
    per_word: Counter[str] = Counter()
    tag_words: Counter[str] = Counter()
    fictions = 0
    for shard in shards:
        table = pq.read_table(shard, columns=["fiction_id", "description", "tags"])
        for row in table.to_pylist():
            fiction_id = row.get("fiction_id")
            if fiction_id in seen:
                continue
            seen.add(fiction_id)
            fictions += 1
            blurb = row.get("description") or ""
            for word in {w.casefold() for w in _WORD.findall(blurb)}:
                if word not in _STOP:
                    per_word[word] += 1
            try:
                tags = json.loads(row.get("tags") or "[]")
            except (TypeError, ValueError):
                tags = []
            for tag in tags:
                for word in _WORD.findall(str(tag)):
                    folded = word.casefold()
                    if folded not in _STOP:
                        tag_words[folded] += 1
    lexicon = sorted(word for word, count in per_word.items() if count >= floor)
    return {
        "snapshot": SNAPSHOT_REVISION,
        "shards": [shard.name for shard in shards],
        "fictions": fictions,
        "floor": floor,
        "blurb_vocabulary": len(per_word),
        "lexicon_size": len(lexicon),
        "tag_vocabulary_size": len(tag_words),
        "lexicon": lexicon,
        "tag_words": sorted(tag_words),
        # Reported so the floor's effect is visible rather than buried in one number.
        "sensitivity": {
            str(alternative): sum(1 for count in per_word.values() if count >= alternative)
            for alternative in (1, 2, 5, 10, 25, 100)
        },
    }


def world_nouns(forge_path: Path) -> dict[str, object]:
    """Each candidate's key nouns, read off its records rather than off its prose."""
    from litharness.application import architect  # repo venv only
    from litharness.domain import worlds

    forged = json.loads(forge_path.read_text(encoding="utf-8"))
    rows = []
    for bundle in forged["candidates"]:
        candidate = architect.Candidate(bundle["index"], bundle["world"])
        nouns = worlds.key_nouns(architect.records_for(candidate))
        rows.append(
            {
                "index": bundle["index"],
                "title": bundle["title"],
                "domain": bundle["report"]["domain"],
                "geometry": bundle["report"]["geometry"],
                "key_nouns": list(nouns),
            }
        )
    return {
        "forge": str(forge_path),
        "architect_id": forged["architect_id"],
        "prompt_shape": forged.get("prompt_shape"),
        "candidates": rows,
    }


def overlap(nouns: list[str], lexicon: set[str], tags: set[str]) -> dict[str, object]:
    if not nouns:
        return {"n": 0}
    in_blurbs = [word for word in nouns if word in lexicon]
    in_tags = [word for word in nouns if word in tags]
    either = {*in_blurbs, *in_tags}
    return {
        "n": len(nouns),
        "share_in_blurbs": round(len(in_blurbs) / len(nouns), 4),
        "share_in_tags": round(len(in_tags) / len(nouns), 4),
        "share_in_either": round(len(either) / len(nouns), 4),
        "shared": sorted(either),
        "coined": sorted(set(nouns) - either),
    }


def report() -> dict[str, object]:
    lexicon_blob = json.loads(LEXICON_JSON.read_text(encoding="utf-8"))
    worlds_blob = json.loads(WORLDS_JSON.read_text(encoding="utf-8"))
    lexicon = set(lexicon_blob["lexicon"])
    tags = set(lexicon_blob["tag_words"])
    rows = []
    for candidate in worlds_blob["candidates"]:
        measured = overlap(candidate["key_nouns"], lexicon, tags)
        rows.append({**{k: candidate[k] for k in ("index", "title", "domain")}, **measured})
    shares = [row["share_in_either"] for row in rows if row.get("n")]
    return {
        "lexicon": {
            key: lexicon_blob[key]
            for key in ("fictions", "floor", "lexicon_size", "tag_vocabulary_size", "shards")
        },
        "prompt_shape": worlds_blob.get("prompt_shape"),
        "candidates": rows,
        # **A distribution, and no bar.** See the module docstring.
        "distribution": (
            {
                "n": len(shares),
                "min": min(shares),
                "median": statistics.median(shares),
                "max": max(shares),
            }
            if shares
            else {"n": 0}
        ),
    }


def selftest() -> int:
    """Runs with no corpus and no forge: the arithmetic, not the substrate."""
    measured = overlap(
        ["assay", "corvessa", "seal"], {"assay", "seal"}, {"progression"}
    )
    assert measured["share_in_blurbs"] == round(2 / 3, 4), measured
    assert measured["coined"] == ["corvessa"], measured
    assert overlap([], set(), set()) == {"n": 0}
    print("world_lexicon selftest: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--substrate", choices=("royalroad", "worlds", "report", "selftest"), required=True
    )
    parser.add_argument("--forge", type=Path, help="a forge.json written by `litharness forge`")
    parser.add_argument("--floor", type=int, default=DEFAULT_FLOOR)
    args = parser.parse_args(argv)

    if args.substrate == "selftest":
        return selftest()
    if args.substrate == "royalroad":
        blob = build_lexicon(args.floor)
        DERIVED.mkdir(parents=True, exist_ok=True)
        LEXICON_JSON.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
        print(
            f"{blob['fictions']} fiction(s) over {len(blob['shards'])} shard(s); "
            f"lexicon {blob['lexicon_size']} word(s) at floor {blob['floor']}"
        )
        return 0
    if args.substrate == "worlds":
        if args.forge is None:
            raise SystemExit("--substrate worlds needs --forge")
        blob = world_nouns(args.forge)
        WORLDS_JSON.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
        for row in blob["candidates"]:
            print(f"[{row['index'] + 1}] {row['title']}: {len(row['key_nouns'])} key noun(s)")
        return 0
    print(json.dumps(report(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
