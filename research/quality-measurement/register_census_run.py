"""Run the two register counters over our shelf and the market, in one pass, and write the report.

The counters and their registration are `register_census.py`; this is only the driver. It reads
Track A's derived intermediate rather than the parquet shards directly, so the expensive scan was
paid once for two tracks.

    C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/register_census_run.py

The MirrorBench interpreter, because the intermediate is parquet (CLAUDE.md). One sustained job at
a time on this box, CPU jobs included.

**What is subtracted, visibly.** The 26 descriptor-half fiction ids of stage-0 §150.1 are dropped
from the market half before any ours-versus-market number, and both row counts are reported so the
subtraction's size stays legible.

**Where a sample is used and where it is not.** The unigram frequency base is the whole corpus,
because the tail is where `awnings` and `trestle` live and a sampled tail is noise. The bigram base
is a deterministic subsample, stated in the artifact as `bigram_base_chapters`: a full bigram table
over 67k chapters does not fit in memory beside the unigram one, and the box has hard-shut-down
once under exactly this kind of load. Ours and market are scored against the same table either way,
so the comparison is like-for-like; the absolute bigram rate is not comparable to anything else.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import register_census as rc  # noqa: E402

INTERMEDIATE = HERE / "derived" / "rr-chapters"
SHELF = Path(__file__).resolve().parent.parent.parent / "book-library"
RESULTS = HERE / "results" / "register-census.json"


def _quantiles(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)

    def at(fraction: float) -> float:
        if len(ordered) == 1:
            return round(ordered[0], 4)
        position = fraction * (len(ordered) - 1)
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 4)

    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 4),
        "p10": at(0.10), "p25": at(0.25), "p50": at(0.50), "p75": at(0.75), "p90": at(0.90),
        "max": round(ordered[-1], 4),
        "zero_share": round(sum(1 for v in ordered if v == 0.0) / len(ordered), 4),
    }


def _per_fiction(by_fiction: dict[tuple[int, str], list[float]]) -> dict[str, list[float]]:
    """Collapse each serial to one number per group, so the unit is a story rather than a chapter.

    Fifty chapters from one serial share author, prompt profile and arc position; a distribution
    over them is a confident statement about one observation. `BRIEF.md` §6(5).
    """
    collapsed: dict[str, list[float]] = {}
    for (_fiction_id, group), rates in by_fiction.items():
        collapsed.setdefault(group, []).append(statistics.fmean(rates))
    return collapsed


def _shelf_chapters() -> list[tuple[str, str]]:
    out = []
    for path in sorted(SHELF.glob("*/chapters/*.txt")):
        label = f"{path.parent.parent.name}/{path.name}"
        out.append((label, path.read_text(encoding="utf-8")))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-mod", type=int, default=27,
                        help="keep 1 market chapter in N for the friction half")
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--limit", type=int, default=0, help="stop after N rows (smoke test)")
    parser.add_argument("--hit-sample", type=int, default=120,
                        help="market tier-A hits to keep for hand-checking precision")
    args = parser.parse_args()

    import pyarrow.parquet as pq

    manifest = json.loads((INTERMEDIATE / "manifest.json").read_text(encoding="utf-8"))
    handle = pq.ParquetFile(INTERMEDIATE / "chapters.parquet")
    columns = ["fiction_id", "chapter_id", "words", "litrpg", "quarantined", "cohort", "text"]

    def scored(row: dict[str, Any]) -> bool:
        """Deterministic by chapter id, so pass 1 and pass 2 agree without storing a set."""
        return row["chapter_id"] % args.sample_mod == 0

    # ---- pass 1: gloss over everything; unigram base from HELD-OUT rows only; retain the sample
    unigrams: Counter[str] = Counter()
    gloss: dict[str, list[float]] = {}
    sample: list[dict[str, Any]] = []
    market_hits: list[dict[str, str]] = []
    # Per-fiction totals as well as per-chapter rates. Chapters from one serial share author,
    # tic and arc position, so a chapter-level distribution is a confident statement about far
    # fewer independent things than its n suggests — BRIEF.md §6(5), and the market sample made
    # it concrete: several sampled hits came from one story using `which meant` as a stylistic
    # tic. Both readings are reported and neither is called the real one.
    by_fiction: dict[tuple[int, str], list[float]] = {}
    seen = kept = quarantined_rows = base_rows = 0

    for batch in handle.iter_batches(batch_size=args.batch_size, columns=columns):
        for row in batch.to_pylist():
            seen += 1
            if args.limit and seen > args.limit:
                break
            text = row["text"] or ""
            if row["quarantined"]:
                quarantined_rows += 1
                continue                              # never in an ours-versus-market number
            kept += 1
            counts = rc.gloss_counts(text)
            words = max(1, int(row["words"] or 1))
            group = "market_litrpg" if row["litrpg"] else "market_other"
            for tier in ("tier_a", "tier_b"):
                rate = 1000.0 * counts[tier] / words
                gloss.setdefault(f"{group}|{tier}", []).append(rate)
                by_fiction.setdefault((row["fiction_id"], f"{group}|{tier}"), []).append(rate)
            # **Market hits are collected for hand-check, and this is not optional.** Precision
            # was hand-checked on our own chapters and nowhere else; a detector that is exact on
            # ours and loose on the market would manufacture the whole comparison out of its own
            # error rate. Every Nth tier-A hit is kept with enough surrounding text to judge it.
            if counts["tier_a"] and len(market_hits) < args.hit_sample:
                for tier_name in ("a1", "a2"):
                    for _shape, hit, at in rc.gloss_hits(text)[tier_name]:
                        start = max(0, text.rfind(".", 0, at) + 1)
                        end = text.find(".", at + len(hit))
                        market_hits.append({
                            "group": group,
                            "tier": tier_name,
                            "sentence": text[start: end + 1 if end > 0 else at + 120].strip(),
                        })
            if scored(row):
                sample.append({"text": text, "litrpg": bool(row["litrpg"])})
            else:
                unigrams.update(rc.tokens(text))       # base holds out everything it scores
                base_rows += 1
        if args.limit and seen > args.limit:
            break

    total_tokens = sum(unigrams.values())

    # ---- pass 2: bigram base over the same held-out rows, restricted to the scored vocabulary
    wanted: set[str] = set()
    for row in sample:
        wanted.update(rc.bigrams(rc.tokens(row["text"])))
    for _, text in _shelf_chapters():
        wanted.update(rc.bigrams(rc.tokens(text)))

    bigram_table: Counter[str] = Counter()
    bigram_total = 0
    seen2 = 0
    for batch in handle.iter_batches(batch_size=args.batch_size, columns=columns):
        for row in batch.to_pylist():
            seen2 += 1
            if args.limit and seen2 > args.limit:
                break
            if row["quarantined"] or scored(row):
                continue
            grams = rc.bigrams(rc.tokens(row["text"] or ""))
            bigram_total += len(grams)
            for gram in grams:
                if gram in wanted:
                    bigram_table[gram] += 1
        if args.limit and seen2 > args.limit:
            break

    # Ours, scored against the same base.
    ours = _shelf_chapters()
    for _label, text in ours:
        counts = rc.gloss_counts(text)
        words = max(1, len(rc.tokens(text)))
        for tier in ("tier_a", "tier_b"):
            gloss.setdefault(f"ours|{tier}", []).append(1000.0 * counts[tier] / words)

    friction: dict[str, list[float]] = {}
    names: dict[str, list[float]] = {}
    for _label, text in ours:
        out = rc.friction(text, unigrams, total=total_tokens)
        friction.setdefault("ours", []).append(out["rare_rate"])
        names.setdefault("ours", []).append(out["name_rate"])
    for row in sample:
        out = rc.friction(row["text"], unigrams, total=total_tokens)
        group = "market_litrpg" if row["litrpg"] else "market_other"
        friction.setdefault(group, []).append(out["rare_rate"])
        names.setdefault(group, []).append(out["name_rate"])

    bigram: dict[str, list[float]] = {}
    for _label, text in ours:
        bigram.setdefault("ours", []).append(
            rc.bigram_friction(text, bigram_table, total=bigram_total)["rare_bigram_rate"]
        )
    for row in sample:
        group = "market_litrpg" if row["litrpg"] else "market_other"
        bigram.setdefault(group, []).append(
            rc.bigram_friction(row["text"], bigram_table, total=bigram_total)["rare_bigram_rate"]
        )

    payload = {
        "instrument": "register_census.v0",
        "registration_digest": rc.registration_digest(),
        "pre_registration": rc.PRE_REGISTRATION,
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_intermediate": {
            "snapshot_revision": manifest.get("snapshot_revision"),
            "rows_kept_by_scan": manifest.get("rows_kept"),
        },
        "rows": {
            "seen": seen,
            "market_after_quarantine": kept,
            "quarantined_subtracted": quarantined_rows,
            "friction_sample": len(sample),
            "base_rows_held_out_from_scoring": base_rows,
            "sample_mod": args.sample_mod,
            "our_chapters": len(ours),
        },
        "frequency_base": {
            "tokens": total_tokens,
            "types": len(unigrams),
            "bigram_tokens": bigram_total,
            "bigram_types_tracked": len(bigram_table),
            "note": (
                "built from market chapters held out of scoring, so ours and the scored market "
                "sample sit equally outside it"
            ),
        },
        "gloss_per_1k": {k: _quantiles(v) for k, v in sorted(gloss.items())},
        "gloss_per_1k_by_fiction": {
            key: _quantiles(rates)
            for key, rates in sorted(_per_fiction(by_fiction).items())
        },
        "friction_rare_per_1k": {k: _quantiles(v) for k, v in sorted(friction.items())},
        "proper_noun_per_1k": {k: _quantiles(v) for k, v in sorted(names.items())},
        "bigram_friction_per_1k": {k: _quantiles(v) for k, v in sorted(bigram.items())},
        "market_tier_a_hits_for_hand_check": market_hits,
        "fixture_check": {
            "unigram_fixture_ranks": {
                word: unigrams.get(word, 0) for word in rc.FRICTION_FIXTURE_UNIGRAM
            },
            "note": (
                "counts of the operator's two rare words in the market's own text. A word the "
                "market uses freely is not friction, whatever it did to one reader"
            ),
        },
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"registration {payload['registration_digest']}")
    print(f"rows {json.dumps(payload['rows'])}")
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
