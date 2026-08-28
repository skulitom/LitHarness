"""Distil a market voice into numbers, and ask first whether the numbers can tell serials apart.

**What this is for.** `plan/dossier-voice-direction.md` settles where the example text for a
voice may come from, and its answer is that market prose may not enter a generation prompt — not
for copyright, which was that note's own corrected overclaim, but for measurement independence.
The market is this project's yardstick, and an artifact that is a partial function of the
measurement corpus makes every ours-versus-market number partly a measurement of the market
against itself. The permitted middle is a **derived style descriptor**: numbers and closed
labels, never prose. *The corpus aims; the pretrained prior executes.*

**And the question that comes before any of that is whether a descriptor can differentiate at
all**, which is free to answer and is what this module answers first. A descriptor is meant to
give one writer a different aim from another's. If the market's serials are more like each other
than each is like itself, then every descriptor is approximately the same descriptor, every
writer is aimed at the same voice, and the voice-exhibited arm homogenises the roster instead of
varying it — the exact opposite of what it exists to do. That is a between-serial versus
within-serial variance question over text already on disk, and `PRE_REGISTRATION` below fixes the
reading before the first shard is opened.

**Two halves that must never meet, and the partition is written before extraction.** One sample
cannot both aim generation and measure it. Distil sentence length from a serial, aim writers at
it, then measure our sentence length against a pool containing that serial, and the comparison is
partly our own aim measured against itself. So the pool is split by a rule: rank by followers,
alternate down the ranking into `descriptor` and `measurement`. Alternating rather than cutting
keeps the follower distribution approximately matched, which matters because register may covary
with popularity. Descriptors come from the `descriptor` half only, and nothing here reads the
other half for anything but its manifest row.

**Nothing prose-bearing is written at any point.** `rival_pool.py` writes third-party text under
`derived/` because a rival *is* a listing somebody else wrote; a descriptor is arithmetic, so the
chapters are streamed, measured and dropped. The committed artifact carries ids, counts and
numbers. Reproducibility comes from `fiction_id` and `chapter_id` in the manifest, not from a
copy of the text.

**The arithmetic is `litharness.domain.voice.distill` and is not reimplemented here**, which is
the one place this module reaches across the wall in the permitted direction. The measurement
side and the generation side must compute one voice the same way or a descriptor is a target
nothing can be read against; two implementations of one statistic is the second-home defect this
project keeps finding. RS1 holds in the direction that matters — the package computes arithmetic
and never names a corpus, which `tests/test_corpus_leak_audit.py` now checks.

    C:/DEV/MirrorBench/.venv/Scripts/python.exe research/quality-measurement/voice_descriptors.py

The MirrorBench interpreter, because this reads the parquet shards (CLAUDE.md). One sustained
job at a time on this box, CPU jobs included; the two shards are 497MB.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import fields as dataclass_fields
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))

import corpus_io  # noqa: E402

from litharness.domain import rivals as rivals_mod  # noqa: E402
from litharness.domain import voice as voice_mod  # noqa: E402

RESULTS = HERE / "results"

#: Which position in a serial's own run a chapter has to hold to be measured.
#:
#: **Three rather than one, and the third is what makes the pre-check computable at all.** With a
#: single chapter per serial there is no within-serial term, so between-versus-within cannot be
#: formed and the descriptor channel would go to a paid draw with no attainability check behind
#: it. Position 1 is included and reported separately because an opening is its own register — a
#: hook — and a descriptor dragged by hooks is a descriptor of hooks.
POSITIONS: tuple[int, ...] = (1, 5, 15)

#: A serial needs at least this many of `POSITIONS` present to contribute. Two, because two is
#: where a within-serial term starts existing.
MIN_POSITIONS = 2

#: **Tense is assumed rather than measured, and it is recorded here rather than buried in a
#: call.** `voice.person_of` derives person mechanically from a closed pronoun class; no
#: equally defensible detector for tense exists, because its closed auxiliaries are reliable
#: in narration and unreliable inside dialogue, where present-tense speech sits in past-tense
#: prose. Past is the genre's overwhelming default and the assumption is stated so a later
#: reader knows it was one.
#:
#: It touches nothing this module concludes: `descriptor_id` changes with it, and every ICC
#: below is computed over `NUMERIC_FIELDS`, which tense is not in. A descriptor actually used
#: to aim a draw should carry a tense somebody established for that serial.
ASSUMED_TENSE = voice_mod.Tense.PAST

#: Written before the first shard was opened, every branch named so none can be reported
#: afterwards as the expected one. `writer_states.PRE_REGISTRATION` is the shape.
#:
#: **No bar is declared and none is owed.** §61's four attainability checks attach to declaring a
#: threshold on a measured quantity; what is registered below is a *direction* with a kill
#: condition, and a flat result refutes it rather than failing it. §146.5 is the precedent.
PRE_REGISTRATION: dict[str, str] = {
    "question": (
        "can a per-serial style descriptor differentiate one writer's aim from another's, or "
        "are the market's serials more like each other than each is like itself"
    ),
    "predicted": (
        "for each numeric descriptor field, between-serial variance exceeds within-serial "
        "variance: ICC(1) > 0 on every field, and above 0.5 on sentence_words_mean, which is "
        "the field a reader would name first if asked how two serials differ"
    ),
    "refuted": (
        "ICC(1) at or below 0 on sentence_words_mean. A descriptor then carries no per-serial "
        "signal on the field it was most expected to, every writer aimed by one is aimed at "
        "approximately the same voice, and the voice-exhibited arm homogenises the roster "
        "rather than varying it. That is a result and it is the cheap one: it arrives before "
        "any paid draw"
    ),
    "unreadable": (
        "fewer than 10 serials clear MIN_POSITIONS, or the median serial holds fewer chapters "
        "than half its recovered published count. The first leaves ICC estimated on too few "
        "groups to mean anything; the second means the shards hold a sample rather than a run "
        "and 'position 5' is not position 5"
    ),
    "openings": (
        "reported twice, with position 1 and without it, and the pair is description rather "
        "than a claim. An opening is its own register, so a descriptor computed over openings "
        "is a descriptor of hooks; if the two readings disagree in direction, the without-1 "
        "reading is the one the arm would use and the disagreement is the finding"
    ),
    "no_bar": (
        "nothing here declares a bar over anything. The 0.5 in 'predicted' is a registered "
        "direction on one named field, not a threshold anything passes or fails"
    ),
}

#: The numeric fields an ICC is computed over: every `StyleDescriptor` field that is a number.
#: Derived from the dataclass rather than listed, so a field added there is analysed here without
#: anybody remembering.
NUMERIC_FIELDS: tuple[str, ...] = tuple(
    field_.name for field_ in dataclass_fields(voice_mod.StyleDescriptor)
    if field_.type == "float"
)


def registration_digest() -> str:
    """The registration's own address, written into every artifact this module produces.

    So a result identifies the registration it ran under, which is the shape
    `brief_capability`'s frozen conditions already keep. A registration edited after a run
    produces a different digest and the artifact stops matching it, loudly.
    """
    material = json.dumps(PRE_REGISTRATION, sort_keys=True).encode()
    return sha256(material).hexdigest()[:16]


def _chapters(shards: tuple[int, ...]) -> dict[int, list[dict[str, Any]]]:
    """Every genre-tagged chapter in the shards, grouped by fiction.

    **Read directly rather than through `corpus_io.royalroad_chapters`, and the reason is the
    position index.** That loader drops chapters below a word floor and outside an era cohort,
    which is correct for what it is for and fatal here: position is *rank within a serial's own
    published run*, and ranking what survived a filter would call the fifth surviving chapter
    "position 5". Nothing is dropped before the ordering is taken.
    """
    import pyarrow.parquet as pq

    columns = [
        "fiction_id", "chapter_id", "release_datetime", "text", "tags",
        "followers", "total_views", "average_views",
    ]
    by_fiction: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for shard in shards:
        table = pq.read_table(corpus_io._shard_path(shard), columns=columns)
        for row in table.to_pylist():
            tags = json.loads(row.get("tags") or "[]")
            if corpus_io.GENRE_TAG not in tags:
                continue
            fiction = row.get("fiction_id")
            if fiction is None:
                continue
            by_fiction[int(fiction)].append(row)
    return by_fiction


def _published_chapters(rows: list[dict[str, Any]]) -> int | None:
    """A fiction's true published chapter count, recovered from its own rate covariates.

    `round(total_views / average_views)`, which `corpus_io` records as the way to get a
    fiction's maturity independent of which shards are cached — `pages` is 100% null. This is
    the coverage check: it says whether the shards hold a serial's run or a sample of it, which
    is the difference between "position 5" meaning position 5 and meaning nothing.
    """
    for row in rows:
        total = float(row.get("total_views") or 0)
        average = float(row.get("average_views") or 0)
        if total > 0 and average > 0:
            return round(total / average)
    return None


def pool(shards: tuple[int, ...]) -> list[dict[str, Any]]:
    """The follower-ranked pool, partitioned before anything is measured.

    `rivals.MIN_FOLLOWERS` is the floor and is not restated: it is the package's own constant for
    "a serial anybody would call successful", and a second copy here would be a second home for a
    threshold that has one.

    **The partition is a rule, applied to a deterministic ranking, and written into the manifest
    before a descriptor exists.** Ties break on `fiction_id` so two runs over the same shards
    partition identically.
    """
    by_fiction = _chapters(shards)
    entries: list[dict[str, Any]] = []
    for fiction, rows in by_fiction.items():
        followers = max(int(row.get("followers") or 0) for row in rows)
        if followers < rivals_mod.MIN_FOLLOWERS:
            continue
        ordered = sorted(
            rows, key=lambda row: (row.get("release_datetime") or "", row["chapter_id"])
        )
        entries.append(
            {
                "fiction_id": fiction,
                "followers": followers,
                "held": len(ordered),
                "published": _published_chapters(ordered),
                "chapters": ordered,
            }
        )
    entries.sort(key=lambda entry: (-entry["followers"], entry["fiction_id"]))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
        entry["half"] = "descriptor" if rank % 2 else "measurement"
    return entries


def descriptors_for(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """One descriptor per held position for one serial. Chapters are measured and dropped."""
    out: list[dict[str, Any]] = []
    for position in POSITIONS:
        if position > len(entry["chapters"]):
            continue
        row = entry["chapters"][position - 1]
        text = row.get("text") or ""
        if not text.strip():
            continue
        try:
            descriptor = voice_mod.distill(
                [text],
                person=voice_mod.person_of(text),
                tense=ASSUMED_TENSE,
            )
        except voice_mod.MalformedDescriptor:
            continue
        out.append(
            {
                "fiction_id": entry["fiction_id"],
                "chapter_id": row["chapter_id"],
                "position": position,
                "words": len(text.split()),
                "descriptor_id": descriptor.descriptor_id,
                **{name: getattr(descriptor, name) for name in NUMERIC_FIELDS},
                "person": str(descriptor.person),
            }
        )
    return out


def icc(groups: list[list[float]]) -> float | None:
    """One-way random-effects ICC(1) over unequal group sizes, or None when it cannot be formed.

    **The statistic `BRIEF.md` §2 names**, which asks for within-unit reliability before anybody
    believes a per-unit number. Here the unit is a serial and the replicates are its own
    chapters: ICC(1) at or below zero says a serial's chapters differ from each other as much as
    from another serial's, and a per-serial descriptor is then a per-chapter accident with a
    serial's name on it.

    Negative values are returned rather than clamped to zero. A clamp would turn the refutation
    branch of `PRE_REGISTRATION` into a value that reads as a weak pass.
    """
    usable = [group for group in groups if len(group) >= 2]
    if len(usable) < 2:
        return None
    counts = [len(group) for group in usable]
    total = sum(counts)
    grand = statistics.fmean(value for group in usable for value in group)
    means = [statistics.fmean(group) for group in usable]
    between = sum(
        count * (mean - grand) ** 2 for count, mean in zip(counts, means, strict=True)
    ) / (len(usable) - 1)
    within_df = total - len(usable)
    if within_df <= 0:
        return None
    within = sum(
        (value - mean) ** 2
        for group, mean in zip(usable, means, strict=True)
        for value in group
    ) / within_df
    # The size correction for unequal groups, as in a one-way random-effects model.
    size = (total - sum(count**2 for count in counts) / total) / (len(usable) - 1)
    denominator = between + (size - 1) * within
    if denominator == 0:
        return None
    return (between - within) / denominator


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Between-serial against within-serial, per field, with and without the opening."""
    def _icc(subset: list[dict[str, Any]]) -> dict[str, float | None]:
        grouped: dict[str, dict[int, list[float]]] = {
            field: defaultdict(list) for field in NUMERIC_FIELDS
        }
        for row in subset:
            for field in NUMERIC_FIELDS:
                grouped[field][row["fiction_id"]].append(float(row[field]))
        return {field: icc(list(grouped[field].values())) for field in NUMERIC_FIELDS}

    return {
        "all_positions": _icc(rows),
        "without_opening": _icc([row for row in rows if row["position"] != 1]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shards",
        default=",".join(str(shard) for shard in corpus_io.SHARDS),
        help="comma-separated shard numbers; the cached pair by default",
    )
    parser.add_argument(
        "--out",
        default=str(RESULTS / "voice-descriptors.json"),
        help="where the numbers land. Ids, counts and statistics only; no prose is ever written",
    )
    args = parser.parse_args(argv)

    shards = tuple(int(part) for part in args.shards.split(",") if part.strip())
    entries = pool(shards)
    half = [entry for entry in entries if entry["half"] == "descriptor"]
    rows = [row for entry in half for row in descriptors_for(entry)]

    by_fiction: dict[int, int] = defaultdict(int)
    for row in rows:
        by_fiction[row["fiction_id"]] += 1
    contributing = [fiction for fiction, count in by_fiction.items() if count >= MIN_POSITIONS]

    coverage = [
        entry["held"] / entry["published"]
        for entry in half
        if entry["published"]
    ]
    payload = {
        # **The key is `pre_registration` and not `registration`**, which is a leak-audit
        # convention rather than a naming preference: `corpus_leak_audit.OURS_FIELDS` names
        # that block as project-authored, so a registration that grows past the 120-word
        # excerpt threshold is recognised as ours rather than reported as an excerpt.
        "pre_registration": PRE_REGISTRATION,
        "registration_digest": registration_digest(),
        "shards": list(shards),
        "min_followers": rivals_mod.MIN_FOLLOWERS,
        "positions": list(POSITIONS),
        "assumed_tense": str(ASSUMED_TENSE),
        "pool": [
            {
                "fiction_id": entry["fiction_id"],
                "rank": entry["rank"],
                "half": entry["half"],
                "followers": entry["followers"],
                "chapters_held": entry["held"],
                "chapters_published": entry["published"],
            }
            for entry in entries
        ],
        "descriptors": rows,
        "serials_contributing": len(contributing),
        "coverage_median": (statistics.median(coverage) if coverage else None),
        "analysis": analyse(rows),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )

    print(f"registration {payload['registration_digest']}")
    print(f"pool {len(entries)} serial(s) over followers >= {rivals_mod.MIN_FOLLOWERS}: "
          f"{sum(1 for e in entries if e['half'] == 'descriptor')} descriptor, "
          f"{sum(1 for e in entries if e['half'] == 'measurement')} measurement")
    print(f"descriptor half: {len(rows)} chapter(s) over {len(by_fiction)} serial(s); "
          f"{len(contributing)} clear MIN_POSITIONS={MIN_POSITIONS}")
    median = payload["coverage_median"]
    print(f"coverage: median held/published = "
          f"{median:.2f}" if median is not None else "coverage: unrecoverable")
    if len(contributing) < 10 or (median is not None and median < 0.5):
        print("UNREADABLE by the registered condition; the ICCs below are printed and are not "
              "a result")
    for label, table in payload["analysis"].items():
        print(f"  {label}:")
        for field, value in table.items():
            print(f"    {field:28s} {'n/a' if value is None else f'{value:+.4f}'}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
