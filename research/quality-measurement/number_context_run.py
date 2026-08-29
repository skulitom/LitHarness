"""Run the number-context counters over our shelf and the market, and write the report.

The counters and their frozen registration are `number_context.py`; this is only the driver.
It reads Track A's derived intermediate rather than the parquet shards directly, so the
expensive scan was paid once for several tracks.

    C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/number_context_run.py

The MirrorBench interpreter, because the intermediate is parquet (CLAUDE.md). A full pass is a
real CPU job and this box has hard-shut-down under two at once, so one sustained job at a time.
`--ours-only` needs no parquet and no interpreter switch, and is the half to iterate on.

**What is subtracted, visibly.** The 26 descriptor-half fiction ids of stage-0 §150.1 are
dropped from the market half before any ours-versus-market number, and both row counts are
reported so the subtraction's size stays legible. They are also summarised on their own line,
never pooled.

**Where the corpus rule bites.** The committed results file carries ids and numbers only. The
market hand-check sample -- short spans around located hits, which is the only way a precision
claim about the other half can be re-checked rather than remembered -- is written to a separate
sidecar under the gitignored `derived/` tree and is never committed.
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

import number_context as nc  # noqa: E402

INTERMEDIATE = HERE / "derived" / "rr-chapters"
RESULTS = HERE / "results" / "number-context.json"
SIDECAR = HERE / "derived" / "number-context-handcheck.json"

#: Populations, in the order they are reported. `ours` is the shelf; the two market halves are
#: the comparison and the validity arm at once.
OURS = "ours"
MARKET_LITRPG = "market_litrpg"
MARKET_OTHER = "market_not_litrpg"
QUARANTINED = "quarantined_descriptor_half"
#: The same two market halves restricted to rows that read as English prose. Reported beside
#: the unrestricted ones and never instead of them.
MARKET_LITRPG_EN = "market_litrpg_english"
MARKET_OTHER_EN = "market_not_litrpg_english"

#: **A reporting parameter, not a bar.** Real English prose runs about 0.35-0.45 on
#: `number_context.english_share`; 0.10 is an order of magnitude below that, so it separates
#: "not English" from "English" rather than dividing English chapters against each other. It
#: was fixed at a linguistically obvious floor rather than chosen after looking at what the
#: split did to any number, and the unrestricted populations are reported in full beside it so
#: the choice can be refused.
ENGLISH_FLOOR = 0.10

#: Every per-chapter quantity the census distributes. Densities are per 1,000 words.
REPORTED_DENSITIES = (
    "system_magnitude",
    "system_ordinal",
    "system_any",
    "calendar_duration",
    "age",
    "money",
    "measure",
    "mundane_core",
    "object_count",
    "ordinal_enumeration",
    "multiplicative",
    "unanchored",
    "mentions",
    "spelled",
    "digits",
)


def quantiles(values: list[float]) -> dict[str, Any]:
    """The distribution, and never a bar over it."""
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
        "p10": at(0.10),
        "p25": at(0.25),
        "p50": at(0.50),
        "p75": at(0.75),
        "p90": at(0.90),
        "max": round(ordered[-1], 4),
        "zero_share": round(sum(1 for v in ordered if v == 0.0) / len(ordered), 4),
    }


class Population:
    """One group's per-chapter series, kept as lists so every statistic is recomputable."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.series: dict[str, list[float]] = {name: [] for name in REPORTED_DENSITIES}
        self.words: list[float] = []
        self.english: list[float] = []
        self.system_share: list[float] = []
        self.magnitude_share: list[float] = []
        self.totals: Counter[str] = Counter()
        self.fictions: dict[int, dict[str, list[float]]] = {}
        self.with_system = 0
        self.with_magnitude = 0
        self.with_mundane = 0
        self.chapters = 0

    def add(self, row: nc.ChapterNumbers, *, fiction_id: int) -> None:
        counts = {
            **row.by_family,
            "system_any": row.system_any,
            "mundane_core": row.mundane_core,
            "mentions": row.mentions,
            "spelled": row.spelled,
            "digits": row.digits,
        }
        self.chapters += 1
        self.words.append(float(row.words))
        self.english.append(row.english_share)
        for name in REPORTED_DENSITIES:
            density = row.per_1k(counts[name])
            self.series[name].append(density)
            self.fictions.setdefault(fiction_id, {}).setdefault(name, []).append(density)
        self.totals.update(counts)
        self.totals["words"] += row.words
        self.totals["furniture_lines"] += row.furniture_lines
        if row.system_share_of_anchored is not None:
            self.system_share.append(row.system_share_of_anchored)
        if row.magnitude_share_of_anchored is not None:
            self.magnitude_share.append(row.magnitude_share_of_anchored)
        self.with_system += 1 if row.system_any else 0
        self.with_magnitude += 1 if row.by_family["system_magnitude"] else 0
        self.with_mundane += 1 if row.mundane_core else 0

    def report(self) -> dict[str, Any]:
        if not self.chapters:
            return {"label": self.label, "chapters": 0}
        pooled = self.totals
        words = pooled["words"] or 1

        def pooled_per_1k(name: str) -> float:
            return round(pooled[name] * 1000 / words, 4)

        per_fiction = {
            name: quantiles(
                [statistics.fmean(series[name]) for series in self.fictions.values()]
            )
            for name in ("system_magnitude", "system_any", "mundane_core", "object_count")
        }
        return {
            "label": self.label,
            "chapters": self.chapters,
            "distinct_fictions": len(self.fictions),
            "words": {
                "total": pooled["words"],
                "median": round(statistics.median(self.words), 1),
            },
            "english_share": quantiles(self.english),
            "share_below_english_floor": round(
                sum(1 for value in self.english if value < ENGLISH_FLOOR) / self.chapters, 4
            ),
            "density_per_1k": {
                name: quantiles(self.series[name]) for name in REPORTED_DENSITIES
            },
            "pooled_per_1k": {name: pooled_per_1k(name) for name in REPORTED_DENSITIES},
            "totals": {name: pooled[name] for name in (*REPORTED_DENSITIES, "furniture_lines")},
            "coverage": {
                "share_with_any_system_number": round(self.with_system / self.chapters, 4),
                "share_with_a_system_MAGNITUDE": round(
                    self.with_magnitude / self.chapters, 4
                ),
                "share_with_a_mundane_core_number": round(
                    self.with_mundane / self.chapters, 4
                ),
            },
            "system_share_of_anchored": quantiles(self.system_share),
            "magnitude_share_of_anchored": quantiles(self.magnitude_share),
            "per_fiction_density_per_1k": per_fiction,
        }


def shelf_chapters(shelf: Path) -> list[tuple[str, str, str]]:
    """`(book, chapter, text)` for every reading copy on the shelf."""
    return [
        (path.parent.parent.name, path.name, path.read_text(encoding="utf-8"))
        for path in sorted(shelf.glob("*/chapters/*.txt"))
    ]


def _repo_relative(path: Path) -> str:
    """The path as the repository sees it, or its bare name when it lives outside."""
    try:
        return str(path.relative_to(HERE.parents[1]))
    except ValueError:
        return path.name


def _ratio(top: float | None, bottom: float | None) -> float | None:
    return round(top / bottom, 3) if top and bottom else None


def validity_arm(groups: dict[str, Population]) -> dict[str, Any]:
    """The control that says whether the system counter is measuring this genre at all."""
    genre = groups[MARKET_LITRPG].report()
    control = groups[MARKET_OTHER].report()
    if not genre.get("chapters") or not control.get("chapters"):
        return {"ran": False}

    def coverage(report: dict[str, Any], key: str) -> float | None:
        value = report["coverage"].get(key)
        return float(value) if value is not None else None

    return {
        "reading": (
            "A genre whose defining artifact is a system the character reads must carry more "
            "system numbers than everything else on the platform, or this counter is locating "
            "something other than a system. **Coverage is the statistic to believe**: a single "
            "large stat table contributes as many mentions as it holds numbers, so the mean "
            "density is heavy-tailed while a share of chapters cannot be moved by one outlier. "
            "A separation near 1 would refute the instrument, not the genre."
        ),
        "litrpg_pooled_system_magnitude_per_1k": genre["pooled_per_1k"]["system_magnitude"],
        "not_litrpg_pooled_system_magnitude_per_1k": control["pooled_per_1k"][
            "system_magnitude"
        ],
        "magnitude_pooled_separation": _ratio(
            genre["pooled_per_1k"]["system_magnitude"],
            control["pooled_per_1k"]["system_magnitude"],
        ),
        "litrpg_share_with_a_system_magnitude": coverage(
            genre, "share_with_a_system_MAGNITUDE"
        ),
        "not_litrpg_share_with_a_system_magnitude": coverage(
            control, "share_with_a_system_MAGNITUDE"
        ),
        "magnitude_coverage_separation": _ratio(
            coverage(genre, "share_with_a_system_MAGNITUDE"),
            coverage(control, "share_with_a_system_MAGNITUDE"),
        ),
        "litrpg_pooled_mundane_core_per_1k": genre["pooled_per_1k"]["mundane_core"],
        "not_litrpg_pooled_mundane_core_per_1k": control["pooled_per_1k"]["mundane_core"],
        "mundane_pooled_separation": _ratio(
            genre["pooled_per_1k"]["mundane_core"],
            control["pooled_per_1k"]["mundane_core"],
        ),
        "note_on_the_mundane_row": (
            "The mundane row is NOT a validity check and no direction is registered for it. It "
            "is printed beside the system row because a counter that separated the genre on "
            "BOTH families equally would be reading chapter length or numeral density rather "
            "than context, and that reading has to be available."
        ),
    }


def _english_control(groups: dict[str, Population]) -> dict[str, Any]:
    """How much of any ours-versus-market gap is the market not being in English.

    A non-English chapter scores near zero on every English lexicon in this module, so it
    depresses the market's mundane density and INFLATES the gap this census reports. The gap is
    therefore printed twice -- over every market row, and over the rows that read as English --
    and the second is the one to believe.
    """
    ours = groups[OURS]
    if not ours.chapters:
        return {"ran": False}

    def mundane(name: str) -> float | None:
        group = groups[name]
        if not group.chapters:
            return None
        return round(group.totals["mundane_core"] * 1000 / (group.totals["words"] or 1), 4)

    our_rate = mundane(OURS)
    rows = {
        name: {
            "chapters": groups[name].chapters,
            "pooled_mundane_core_per_1k": mundane(name),
            "ours_over_market": _ratio(our_rate, mundane(name)),
            "share_below_english_floor": (
                round(
                    sum(1 for v in groups[name].english if v < ENGLISH_FLOOR)
                    / groups[name].chapters,
                    4,
                )
                if groups[name].chapters
                else None
            ),
        }
        for name in (MARKET_LITRPG, MARKET_LITRPG_EN, MARKET_OTHER, MARKET_OTHER_EN)
        if groups[name].chapters
    }
    return {
        "english_floor": ENGLISH_FLOOR,
        "reading": (
            "`ours_over_market` is how many times our own pooled mundane-core density exceeds "
            "that population's. Compare the `_english` row against the row above it: the "
            "difference between them is the part of the gap that was the shards not being in "
            "English, and only the `_english` row is a comparison between two bodies of "
            "English prose."
        ),
        "our_pooled_mundane_core_per_1k": our_rate,
        "populations": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shelf",
        default=str(Path(__file__).resolve().parents[2] / "book-library"),
        help="our own reading copies; the repository's book-library by default",
    )
    parser.add_argument("--intermediate", default=str(INTERMEDIATE))
    parser.add_argument("--results", default=str(RESULTS))
    parser.add_argument("--sidecar", default=str(SIDECAR))
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--limit", type=int, default=0, help="stop after N market rows")
    parser.add_argument(
        "--ours-only", action="store_true", help="skip the market half entirely"
    )
    parser.add_argument("--hit-sample", type=int, default=150)
    parser.add_argument(
        "--hit-sample-mod",
        type=int,
        default=97,
        help="keep hand-check spans from 1 market chapter in N, deterministically",
    )
    args = parser.parse_args()

    failures = nc.selftest()
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        return 1

    groups: dict[str, Population] = {
        name: Population(name)
        for name in (
            OURS,
            MARKET_LITRPG,
            MARKET_OTHER,
            MARKET_LITRPG_EN,
            MARKET_OTHER_EN,
            QUARANTINED,
        )
    }
    cohorts: dict[str, Population] = {}

    # ---- ours. One fiction id per book, so the per-fiction collapse means the same thing on
    # both halves: a book, not a chapter.
    shelf = Path(args.shelf)
    books: dict[str, int] = {}
    our_books: dict[str, dict[str, Any]] = {}
    for book, _chapter, text in shelf_chapters(shelf):
        row = nc.measure(text)
        fiction_id = books.setdefault(book, -(len(books) + 1))
        groups[OURS].add(row, fiction_id=fiction_id)
        entry = our_books.setdefault(book, {"chapters": 0, "words": 0, "by_family": Counter()})
        entry["chapters"] += 1
        entry["words"] += row.words
        entry["by_family"].update(row.by_family)
    if not groups[OURS].chapters:
        print(f"no chapters under {shelf}", file=sys.stderr)
        return 1

    market_rows = quarantined_rows = 0
    hand_check: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}

    if not args.ours_only:
        import pyarrow.parquet as pq

        source = Path(args.intermediate)
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        handle = pq.ParquetFile(source / "chapters.parquet")
        columns = ["fiction_id", "chapter_id", "litrpg", "quarantined", "cohort", "text"]
        seen = 0
        for batch in handle.iter_batches(batch_size=args.batch_size, columns=columns):
            for record in batch.to_pylist():
                seen += 1
                if args.limit and seen > args.limit:
                    break
                row = nc.measure(record["text"] or "")
                if record["quarantined"]:
                    quarantined_rows += 1
                    groups[QUARANTINED].add(row, fiction_id=record["fiction_id"])
                    continue
                market_rows += 1
                litrpg = bool(record["litrpg"])
                groups[MARKET_LITRPG if litrpg else MARKET_OTHER].add(
                    row, fiction_id=record["fiction_id"]
                )
                if row.english_share >= ENGLISH_FLOOR:
                    groups[MARKET_LITRPG_EN if litrpg else MARKET_OTHER_EN].add(
                        row, fiction_id=record["fiction_id"]
                    )
                if litrpg and record["cohort"]:
                    key = f"litrpg_{record['cohort']}"
                    cohorts.setdefault(key, Population(key)).add(
                        row, fiction_id=record["fiction_id"]
                    )
                # Hand-check spans, deterministic by chapter id so a re-run keeps the same
                # sample. Precision was hand-checked on our own shelf and nowhere else, and a
                # detector exact on the half that motivated it and loose on the half it is
                # compared against manufactures the comparison out of its own error rate --
                # `register_census`'s lesson, applied before the fact.
                if (
                    len(hand_check) < args.hit_sample
                    and record["chapter_id"] % args.hit_sample_mod == 0
                ):
                    hand_check.extend(_spans(record, litrpg=litrpg))
            if args.limit and seen > args.limit:
                break

    payload: dict[str, Any] = {
        "instrument": nc.PRE_REGISTRATION["instrument"],
        "registration_digest": nc.REGISTRATION_DIGEST,
        "pre_registration": nc.PRE_REGISTRATION,
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_intermediate": {
            "snapshot_revision": manifest.get("snapshot_revision"),
            "rows_kept_by_scan": manifest.get("rows_kept"),
            "min_words": (manifest.get("filter") or {}).get("min_words"),
        },
        "rows": {
            "our_chapters": groups[OURS].chapters,
            "our_books": len(books),
            "market_rows_before_quarantine": market_rows + quarantined_rows,
            "quarantined_subtracted": quarantined_rows,
            "market_after_quarantine": market_rows,
        },
        "populations": {
            name: group.report()
            for name, group in groups.items()
            if group.chapters
        },
        "litrpg_cohorts": {name: group.report() for name, group in sorted(cohorts.items())},
        "our_books": {
            book: {
                "chapters": entry["chapters"],
                "words": entry["words"],
                "by_family": dict(entry["by_family"]),
            }
            for book, entry in sorted(our_books.items())
        },
        "validity_arm": validity_arm(groups),
        "english_control": _english_control(groups),
        "declares_no_bar": nc.PRE_REGISTRATION["declares_no_bar"],
        "residuals": nc.PRE_REGISTRATION["residuals"],
        "hand_check_sidecar": {
            # Repo-relative when it is inside the repo, and the bare name otherwise. A smoke
            # run points `--sidecar` at a scratch directory and `relative_to` raised there,
            # which failed the run after the whole scan had already been paid for.
            "path": _repo_relative(Path(args.sidecar)) if hand_check else None,
            "spans": len(hand_check),
            "rule": (
                "gitignored, never committed: it holds short spans of market prose so a "
                "precision claim about the market half can be re-checked rather than "
                "remembered"
            ),
        },
    }

    results = Path(args.results)
    results.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""` because this file is committed and the repository is LF.
    results.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="",
    )
    if hand_check:
        sidecar = Path(args.sidecar)
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(
            json.dumps(hand_check, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"registration {nc.REGISTRATION_DIGEST}")
    print(f"rows {json.dumps(payload['rows'])}")
    for name, report in payload["populations"].items():
        density = report["density_per_1k"]
        print(
            f"{name}: n={report['chapters']} "
            f"sys_mag p50={density['system_magnitude']['p50']} "
            f"mean={density['system_magnitude']['mean']} "
            f"| mundane_core p50={density['mundane_core']['p50']} "
            f"mean={density['mundane_core']['mean']} "
            f"| any-magnitude coverage="
            f"{report['coverage']['share_with_a_system_MAGNITUDE']}"
        )
    print(f"wrote {results}")
    return 0


def _spans(record: dict[str, Any], *, litrpg: bool) -> list[dict[str, Any]]:
    """Short spans around located mentions, for a hand-check of the market half's precision."""
    text = nc.normalise(record["text"] or "")
    words = text.split()
    out: list[dict[str, Any]] = []
    for mention in nc.locate(text):
        if mention.family in {"unanchored", "ordinal_enumeration"}:
            continue
        start = max(0, mention.word_offset - 10)
        out.append(
            {
                "fiction_id": record["fiction_id"],
                "chapter_id": record["chapter_id"],
                "litrpg": litrpg,
                "family": mention.family,
                "surface": mention.surface,
                "head": mention.head,
                "span": " ".join(words[start : mention.word_offset + 12]),
            }
        )
    return out


if __name__ == "__main__":
    raise SystemExit(main())
