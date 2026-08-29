"""The progression-event cadence census: how often the market's LitRPG moves a number.

Research code, outside `src/`: nothing here is imported by the package and nothing generation-side
may read it. It answers one operator question — *"not just progress inside the opening, readers
expect constant and regular progress"* — by turning "constant and regular" into a distribution
over the market's own chapters, which is what `comic-beats-results.md` did for levity.

**This census is code-only. No model is called, nothing is ranked, and no bar is declared.**
That inverts the comic-beat census's error profile and the inversion is the first thing to
understand about every number here:

- the comic locator had **measured reliability (0.537) and verified precision** — every beat
  carried an anchor checked against the page — so its counts were noisy and honest;
- these counters have **reliability 1.0 by construction and unmeasured precision**. The same
  chapter always returns the same count. Whether a located span is really a progression event
  is not checked by anything in this file, and that is the largest residual (see
  `PRE_REGISTRATION["residuals"]`).

**Events per 1,000 words is a density of located FURNITURE AND PHRASING, not of pleasure.**
A chapter with more of them is not better. Whether any of them lands is not asked, not
schema'd, and not derivable from anything here.

Two commands:

    materialise   one batched pass over the two cached shards -> a gitignored intermediate
    census        counters over that intermediate -> a committed results JSON of numbers only

The pass is deliberately wider than this census needs — every genre, every chapter of every
story — because a sibling track reads the same intermediate for a vocabulary census and one
scan is cheaper than two. Sampling happens downstream, never in the pass. The width also buys
this census its one free validity arm: chapters the market did **not** tag `LitRPG` are the
control group these counters must score below, and if they do not, the counters are measuring
something other than progression.

**Corpus rule (RS1, and `corpus_io`'s own):** market text lives only in the gitignored
intermediate under `derived/`. The committed results file carries ids and numbers and never a
quoted span of anyone else's prose.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Imported after the path insert above, which is what makes it importable: this module runs
# under the MirrorBench interpreter, where the package is not installed.
import corpus_io  # isort: skip

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"
RESULTS = HERE / "results"

#: The descriptor half of `voice-descriptors.json`'s pool. These fictions supplied the material
#: a descriptor set was derived from, so they may not also serve as the market baseline that
#: set is measured against. They are carried through the intermediate with `quarantined=True`
#: rather than dropped from it: a visible subtraction survives review, a silent omission reads
#: as the corpus.
QUARANTINE_SOURCE = RESULTS / "voice-descriptors.json"


# --------------------------------------------------------------------------- the frozen block

#: Everything that defines what a progression event IS. Changing any of it changes the
#: instrument, so it is content-addressed and `--selftest` refuses a drift.
#:
#: Patterns are written for `re.IGNORECASE | re.MULTILINE` over character-normalised text with
#: line structure preserved.
PRE_REGISTRATION: dict[str, Any] = {
    "instrument": "progression_cadence.v0",
    "question": (
        "At what density, how early, and how evenly do published market chapters place "
        "locatable progression events?"
    ),
    "corrections": {
        "frame_alone_is_a_scene_divider": (
            "CORRECTED BEFORE ANY READING WAS PUBLISHED, and recorded rather than quietly "
            "fixed. The first run's family mix showed `system_block` at 83% of the "
            "NOT-LitRPG control's located events, which is not credible for a population "
            "that mostly has no system: the frame pattern was matching `***` and `---` "
            "scene dividers, which every fiction uses. A run of frame characters with no "
            "furniture line in it is now a divider and not an event. "
            "**This is not a rubric fitted to its answers.** A scene divider is not a "
            "progression event independently of what the count comes out at, the rule was "
            "stated before the re-run rather than tuned against it, and its declared "
            "direction is to LOWER both populations' densities."
        ),
        "frame_characters_stripped_before_classifying": (
            "A line inside a drawn box — leading and trailing box or rule characters around "
            "real content — is classified on its content. Without this a box-drawn status "
            "sheet scored zero, which was recall lost to typography and is the exact bias "
            "the sentence rule exists to avoid."
        ),
    },
    "unit_rules": {
        "block_run": (
            "Consecutive system-furniture lines are ONE event, however long the run. A run "
            "continues across at most one blank line; a second blank line ends it. A status "
            "sheet is one notification, not twenty. A run made only of frame characters is a "
            "scene divider and no event at all."
        ),
        "sentence": (
            "Outside furniture runs, at most ONE event per sentence, family assigned by "
            "priority. Sentence rather than line, because a prose-mode chapter writes long "
            "paragraphs and a per-line rule would under-count it against a furniture-mode "
            "chapter — the typography bias this instrument most needs to avoid."
        ),
        "priority": ["system_block", "level_up", "capability_gain", "stat_delta"],
    },
    "normalisation": (
        "NFKC; curly quotes and dashes folded to ASCII; horizontal whitespace collapsed "
        "WITHIN a line; line structure preserved because furniture is a line shape."
    ),
    "families": {
        "system_block": (
            "A run of interface lines the character reads rather than the narrator speaks: a "
            "whole line bracketed [..] or angled <..>, a frame line of box/rule characters, or "
            "a short 'Name: value' line carrying a digit and no sentence punctuation."
        ),
        "level_up": (
            "Explicit advancement language: levelling, ranking up, breaking through, "
            "class change."
        ),
        "capability_gain": (
            "Acquiring a named capability: a skill, spell, title, perk, class, technique."
        ),
        "stat_delta": (
            "A number moving: a signed delta, an arrow between two numbers, a counted award."
        ),
    },
    "patterns": {
        # -- system furniture, evaluated per line -------------------------------------------
        "furniture_bracketed": r"^\**\[[^\]]{1,200}\]\**[.!?]?$",
        "furniture_angled": r"^\**<[^>]{1,200}>\**[.!?]?$",
        "furniture_frame": r"^[=\-_~*—─-╿\s]{3,}$",
        # The fullwidth colon is deliberate and is not a typo for the ASCII one: translated
        # serials are a real part of this market and write their stat lines with it.
        "furniture_statline": (
            r"^\**[A-Za-z][A-Za-z '/()-]{0,28}\**\s*[:：]\s*"  # noqa: RUF001
            r"\**[^.!?\n]{0,40}\d[^.!?\n]{0,40}\**$"
        ),
        # A bracketed line is furniture only if it is not one of these. Front-matter, author
        # asides and navigation are the three shapes that share the typography and mean
        # nothing about progression.
        "furniture_reject": (
            r"^\**[\[<]?\s*(?:a/?n|author'?s? note|t/?n|translator|tl|edit|note|p\.?s\.?|"
            r"prev(?:ious)?|next|table of contents|toc|index|chapter\s+\d|patreon|discord|"
            r"advance chapters?|support|donate|vote|rating|spoiler|image|img|picture)\b"
        ),
        # -- inline families, evaluated per sentence ----------------------------------------
        "level_up": (
            r"\b(?:level(?:l?ed)?[\s-]?up|levels?\s+up|rank(?:ed)?[\s-]?up|class\s+change|"
            r"evolv(?:ed|es|ing)\s+into|advanc(?:ed|es)\s+to|promoted\s+to|ascend(?:ed|s)\s+to|"
            r"brok\w*\s+through\s+to|reached\s+(?:level|rank|tier|stage|grade)|"
            r"now\s+(?:a\s+|an\s+)?(?:level|rank|tier)\s)\b"
        ),
        "capability_gain": (
            r"\b(?:learn(?:ed|t)|acquired|obtained|unlocked|gained|received|awakened|mastered)\b"
            r"[^.!?\n]{0,40}?\b(?:skill|ability|spell|technique|title|perk|trait|class|feat|"
            r"talent|power|art)s?\b"
            r"|\bnew\s+(?:skill|ability|spell|title|perk|class|technique|power)s?\b"
        ),
        "stat_delta": (
            r"\b\d[\d,]*\s*(?:→|->|=>)\s*\d[\d,]*\b"
            r"|(?<![\w.])\+\s?\d[\d,]*\b"
            r"|\b(?:gain(?:ed|s)?|earn(?:ed|s)?|receiv(?:ed|es)|award(?:ed|s)?)\b"
            r"[^.!?\n]{0,30}?\b\d[\d,]*\s*(?:xp|exp|experience|mana|gold|coins?|credits?|"
            r"points?|levels?|stat\s+points?)\b"
        ),
    },
    "reported": [
        "density: events per 1,000 words, pooled and per era cohort",
        "coverage: share of chapters with zero events",
        "earliness: share of chapters with an event inside the first 500 and 1,000 words",
        "regularity: median word gap between consecutive events, and the gap CV",
        "family share of located events",
        "validity arm: LitRPG-tagged against not-LitRPG-tagged on the same counters",
        "length residual: Spearman(density, chapter words)",
    ],
    "declares_no_bar": (
        "No target cadence is declared here. A bar needs §81/§85/§87/§89's four attainability "
        "checks — range at the real n, direction, independent unit, non-empty subgroup — and "
        "this file runs none of them. It names a distribution and stops."
    ),
    "residuals": [
        "PRECISION IS UNMEASURED. Reliability is 1.0 by construction because the counters are "
        "deterministic; nothing here checks that a located span is a progression event. The "
        "cheapest fix is a model-audited subsample of located spans, and it is not run here.",
        "RECALL IS UNMEASURED, and is the direction a prose-mode chapter loses on: progression "
        "carried entirely by implication and no phrase from the lexicons scores zero.",
        "The counters were written by reading this genre's conventions, not fitted to any "
        "sample; but they were also never held out from one, so they are a prior and not a "
        "trained classifier.",
        "Chapter text is whatever the shard holds, including any front matter the exclusion "
        "list misses.",
    ],
}


def registration_digest() -> str:
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


#: Pinned. `--selftest` fails if the frozen block moves, and `census` refuses to write a
#: results file under any other digest.
REGISTRATION_DIGEST = registration_digest()


# --------------------------------------------------------------------------- the counters

_P = PRE_REGISTRATION["patterns"]
_FLAGS = re.IGNORECASE
_RE_BRACKETED = re.compile(_P["furniture_bracketed"], _FLAGS)
_RE_ANGLED = re.compile(_P["furniture_angled"], _FLAGS)
_RE_FRAME = re.compile(_P["furniture_frame"], _FLAGS)
_RE_STATLINE = re.compile(_P["furniture_statline"], _FLAGS)
_RE_REJECT = re.compile(_P["furniture_reject"], _FLAGS)
_RE_LEVEL_UP = re.compile(_P["level_up"], _FLAGS)
_RE_CAPABILITY = re.compile(_P["capability_gain"], _FLAGS)
_RE_STAT_DELTA = re.compile(_P["stat_delta"], _FLAGS)

INLINE_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("level_up", _RE_LEVEL_UP),
    ("capability_gain", _RE_CAPABILITY),
    ("stat_delta", _RE_STAT_DELTA),
)

FAMILIES = ("system_block", "level_up", "capability_gain", "stat_delta")

# Every key here is an "ambiguous" character on purpose — folding them to ASCII is the
# whole job, so the lint that flags them is flagging the intent.
_FOLD = {
    "‘": "'", "’": "'", "“": '"', "”": '"',  # noqa: RUF001
    "–": "-", "—": "-", "−": "-", " ": " ",  # noqa: RUF001
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def normalise(text: str) -> str:
    """NFKC, folded punctuation, horizontal whitespace collapsed inside lines.

    Line structure survives on purpose: a furniture line is recognised by being a whole line,
    so a normaliser that reflowed paragraphs would delete the signal it is meant to preserve.
    """
    text = unicodedata.normalize("NFKC", text)
    for bad, good in _FOLD.items():
        text = text.replace(bad, good)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))


#: Box, rule and bold characters that wrap a drawn status line without being its content.
_EDGE = "|*=-_~+ ─-╿│┃"


def _classify(line: str) -> str:
    """`""` for ordinary prose, `"frame"` for a bare rule, `"furniture"` for a real line.

    Frame is kept separate from furniture rather than folded into it because the two are the
    same typography doing opposite jobs: `***` between two paragraphs is a scene divider that
    every fiction on the platform uses, and the same characters around a status line are its
    box. Only the second is an event, and telling them apart needs the run, not the line.
    """
    if not line or _RE_REJECT.match(line):
        return ""
    if _RE_FRAME.match(line):
        return "frame" if len(re.sub(r"\s", "", line)) >= 3 else ""
    # A line inside a drawn box is classified on what the box contains.
    inner = line.strip(_EDGE).strip()
    if not inner or _RE_REJECT.match(inner):
        return ""
    if _RE_BRACKETED.match(inner) or _RE_ANGLED.match(inner) or _RE_STATLINE.match(inner):
        return "furniture"
    return ""


def _is_furniture(line: str) -> bool:
    return _classify(line) == "furniture"


@dataclass(frozen=True, slots=True)
class Event:
    """One located progression event: where it is in words, and which family located it."""

    word_offset: int
    family: str


def locate(text: str) -> list[Event]:
    """Every progression event in one chapter, in text order.

    The two unit rules do all the work of not double-counting. A furniture RUN is one event
    however many lines it holds, and a sentence outside a run yields at most one event whatever
    else matches inside it.
    """
    events: list[Event] = []
    lines = normalise(text).split("\n")

    words_before: list[int] = []
    running = 0
    for line in lines:
        words_before.append(running)
        running += len(line.split())

    # Pass 1: furniture runs. A run survives one blank line so a status sheet with spacing
    # stays one notification, and it is an event only if it holds at least one real furniture
    # line — a run of nothing but rule characters is a scene divider.
    kinds = [_classify(line) for line in lines]
    furniture_line = [kind != "" for kind in kinds]
    start: int | None = None
    has_furniture = False
    blanks = 0

    def close(at_start: int | None, real: bool) -> None:
        if at_start is not None and real:
            events.append(Event(words_before[at_start], "system_block"))

    for index, line in enumerate(lines):
        kind = kinds[index]
        if kind:
            if start is None:
                start = index
                has_furniture = False
            has_furniture = has_furniture or kind == "furniture"
            blanks = 0
        elif not line and start is not None:
            blanks += 1
            if blanks > 1:
                close(start, has_furniture)
                start, has_furniture, blanks = None, False, 0
        else:
            close(start, has_furniture)
            start, has_furniture, blanks = None, False, 0
    close(start, has_furniture)

    # Pass 2: inline families, over sentences that are not inside furniture.
    for index, line in enumerate(lines):
        if furniture_line[index] or not line:
            continue
        offset = 0
        for sentence in _SENTENCE_SPLIT.split(line):
            if not sentence:
                continue
            for family, pattern in INLINE_FAMILIES:
                if pattern.search(sentence):
                    events.append(Event(words_before[index] + offset, family))
                    break
            offset += len(sentence.split())

    events.sort(key=lambda event: (event.word_offset, FAMILIES.index(event.family)))
    return events


@dataclass(frozen=True, slots=True)
class ChapterCadence:
    """One chapter's cadence, reduced to the numbers the census aggregates."""

    fiction_id: int
    chapter_id: int
    words: int
    litrpg: bool
    quarantined: bool
    cohort: str | None
    events: int
    per_1k: float
    first_event_words: int | None
    median_gap: float | None
    gap_cv: float | None
    by_family: dict[str, int]

    @property
    def first_event_fraction(self) -> float | None:
        if self.first_event_words is None or not self.words:
            return None
        return self.first_event_words / self.words


def measure(
    text: str,
    *,
    fiction_id: int,
    chapter_id: int,
    litrpg: bool,
    quarantined: bool,
    cohort: str | None,
) -> ChapterCadence:
    words = len(text.split())
    events = locate(text)
    offsets = [event.word_offset for event in events]
    gaps = [b - a for a, b in pairwise(offsets)]
    by_family = {family: sum(1 for e in events if e.family == family) for family in FAMILIES}
    median_gap = statistics.median(gaps) if gaps else None
    gap_cv: float | None = None
    if len(gaps) >= 2:
        mean_gap = statistics.fmean(gaps)
        gap_cv = (statistics.pstdev(gaps) / mean_gap) if mean_gap else None
    return ChapterCadence(
        fiction_id=fiction_id,
        chapter_id=chapter_id,
        words=words,
        litrpg=litrpg,
        quarantined=quarantined,
        cohort=cohort,
        events=len(events),
        per_1k=(len(events) * 1000 / words) if words else 0.0,
        first_event_words=offsets[0] if offsets else None,
        median_gap=median_gap,
        gap_cv=gap_cv,
        by_family=by_family,
    )


# --------------------------------------------------------------------------- the shard pass


GENRE_TAG = corpus_io.GENRE_TAG
MIN_WORDS = 300
INTERMEDIATE_COLUMNS = [
    "fiction_id", "chapter_id", "words", "release_datetime", "followers",
    "tags", "litrpg", "quarantined", "cohort", "text",
]


def quarantined_ids(path: Path = QUARANTINE_SOURCE) -> frozenset[int]:
    """The descriptor half's fiction ids, read from the artifact that defined them."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    pool = payload.get("pool") or []
    ids = {int(row["fiction_id"]) for row in pool if row.get("half") == "descriptor"}
    if not ids:  # the older shape carried the same set under its own key
        ids = {int(row["fiction_id"]) for row in payload.get("serial_descriptors") or []}
    return frozenset(ids)


def materialise(
    out_dir: Path,
    *,
    shards: Sequence[int] = tuple(corpus_io.SHARDS),
    min_words: int = MIN_WORDS,
    batch_size: int = 400,
) -> dict[str, Any]:
    """One batched pass over the shards into a gitignored parquet intermediate.

    Batched rather than `read_table().to_pylist()` because the point of the pass is to be the
    only one anybody runs: a whole shard of full chapter text materialised as Python objects is
    a memory spike no downstream consumer should have to repeat.

    Nothing is filtered by genre. The `litrpg` and `quarantined` booleans are carried as
    columns so every downstream half is an explicit subtraction.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "chapters.parquet"
    quarantine = quarantined_ids()

    schema = pa.schema([
        ("fiction_id", pa.int64()), ("chapter_id", pa.int64()), ("words", pa.int32()),
        ("release_datetime", pa.string()), ("followers", pa.float64()),
        ("tags", pa.string()), ("litrpg", pa.bool_()), ("quarantined", pa.bool_()),
        ("cohort", pa.string()), ("text", pa.string()),
    ])
    source_columns = [
        "fiction_id", "chapter_id", "release_datetime", "followers",
        "tags", "warnings", "text",
    ]

    seen = 0
    kept = 0
    per_shard: dict[str, int] = {}
    writer = pq.ParquetWriter(target, schema, compression="zstd")
    try:
        for shard in shards:
            shard_kept = 0
            handle = pq.ParquetFile(corpus_io._shard_path(shard))
            for batch in handle.iter_batches(batch_size=batch_size, columns=source_columns):
                rows: dict[str, list[Any]] = {name: [] for name in INTERMEDIATE_COLUMNS}
                for row in batch.to_pylist():
                    seen += 1
                    text = row.get("text") or ""
                    words = len(text.split())
                    if words < min_words:
                        continue
                    tags_raw = row.get("tags") or "[]"
                    try:
                        tags = json.loads(tags_raw)
                    except (TypeError, ValueError):
                        tags = []
                    fiction_id = int(row.get("fiction_id") or 0)
                    rows["fiction_id"].append(fiction_id)
                    rows["chapter_id"].append(int(row.get("chapter_id") or 0))
                    rows["words"].append(words)
                    rows["release_datetime"].append(row.get("release_datetime") or "")
                    rows["followers"].append(float(row.get("followers") or 0))
                    rows["tags"].append(tags_raw)
                    rows["litrpg"].append(GENRE_TAG in tags)
                    rows["quarantined"].append(fiction_id in quarantine)
                    rows["cohort"].append(
                        corpus_io.era_cohort(row.get("release_datetime"), row.get("warnings"))
                    )
                    rows["text"].append(text)
                if rows["fiction_id"]:
                    writer.write_table(pa.Table.from_pydict(rows, schema=schema))
                    kept += len(rows["fiction_id"])
                    shard_kept += len(rows["fiction_id"])
            per_shard[str(shard)] = shard_kept
    finally:
        writer.close()

    manifest = {
        "instrument": PRE_REGISTRATION["instrument"],
        "registration_digest": REGISTRATION_DIGEST,
        "scanned_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "snapshot_revision": corpus_io.SNAPSHOT_REVISION,
        "shards": list(shards),
        "shard_cohorts": {str(k): v for k, v in corpus_io.SHARDS.items()},
        "filter": {
            "genre_tag": None,
            "min_words": min_words,
            "note": (
                "No genre filter and no per-story sampling. `litrpg` and `quarantined` are "
                "columns, not filters, so every downstream half subtracts explicitly."
            ),
        },
        "rows_seen": seen,
        "rows_kept": kept,
        "rows_per_shard": per_shard,
        "quarantined_fiction_ids": sorted(quarantine),
        "columns": INTERMEDIATE_COLUMNS,
        "parquet": target.name,
        "corpus_rule": (
            "Gitignored. Market text never leaves derived/; committed artifacts carry ids and "
            "numbers only."
        ),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="",
    )
    return manifest


def read_intermediate(out_dir: Path, *, batch_size: int = 400) -> Iterator[ChapterCadence]:
    """Stream the intermediate and measure each chapter. Text is never yielded."""
    import pyarrow.parquet as pq

    handle = pq.ParquetFile(out_dir / "chapters.parquet")
    columns = ["fiction_id", "chapter_id", "litrpg", "quarantined", "cohort", "text"]
    for batch in handle.iter_batches(batch_size=batch_size, columns=columns):
        for row in batch.to_pylist():
            yield measure(
                row["text"],
                fiction_id=row["fiction_id"],
                chapter_id=row["chapter_id"],
                litrpg=bool(row["litrpg"]),
                quarantined=bool(row["quarantined"]),
                cohort=row["cohort"],
            )


# --------------------------------------------------------------------------- the distribution


def _quantiles(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {}
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
        "sd": round(statistics.pstdev(ordered), 4) if len(ordered) > 1 else 0.0,
        "p5": at(0.05), "p10": at(0.10), "p25": at(0.25), "p50": at(0.50),
        "p75": at(0.75), "p90": at(0.90), "p95": at(0.95),
        "max": round(ordered[-1], 4),
    }


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 3:
        return None

    def rank(values: Sequence[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        index = 0
        while index < len(order):
            stop = index
            while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
                stop += 1
            shared = (index + stop) / 2 + 1
            for position in range(index, stop + 1):
                ranks[order[position]] = shared
            index = stop + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den = (
        sum((a - mx) ** 2 for a in rx) ** 0.5 * sum((b - my) ** 2 for b in ry) ** 0.5
    )
    return round(num / den, 4) if den else None


def summarise(rows: Sequence[ChapterCadence], *, label: str) -> dict[str, Any]:
    """Every number this census reports about one population, and no verdict about it."""
    if not rows:
        return {"label": label, "n": 0}
    densities = [row.per_1k for row in rows]
    words = [float(row.words) for row in rows]
    with_events = [row for row in rows if row.events]
    firsts = [row for row in with_events if row.first_event_words is not None]
    gapped = [row for row in rows if row.median_gap is not None]
    cved = [row for row in rows if row.gap_cv is not None]
    family_totals = {
        family: sum(row.by_family[family] for row in rows) for family in FAMILIES
    }
    located = sum(family_totals.values()) or 1
    return {
        "label": label,
        "n": len(rows),
        "distinct_fictions": len({row.fiction_id for row in rows}),
        "words": {"median": round(statistics.median(words), 1)},
        "density_per_1k": _quantiles(densities),
        "absolute_events": _quantiles([float(row.events) for row in rows]),
        "coverage": {
            "with_at_least_one": len(with_events),
            "share_with_at_least_one": round(len(with_events) / len(rows), 4),
            "zero_event_chapters": len(rows) - len(with_events),
            "share_zero": round((len(rows) - len(with_events)) / len(rows), 4),
        },
        "earliness": {
            "share_event_in_first_500_words": round(
                sum(1 for r in firsts if (r.first_event_words or 0) < 500) / len(rows), 4
            ),
            "share_event_in_first_1000_words": round(
                sum(1 for r in firsts if (r.first_event_words or 0) < 1000) / len(rows), 4
            ),
            "first_event_words": _quantiles(
                [float(r.first_event_words or 0) for r in firsts]
            ),
            "first_event_fraction_of_chapter": _quantiles(
                [r.first_event_fraction or 0.0 for r in firsts]
            ),
        },
        "regularity": {
            "median_gap_words": _quantiles([row.median_gap or 0.0 for row in gapped]),
            "gap_cv": _quantiles([row.gap_cv or 0.0 for row in cved]),
            "chapters_with_two_or_more": len(gapped),
        },
        "family_share": {
            family: round(count / located, 4) for family, count in family_totals.items()
        },
        "family_totals": family_totals,
        "length_residual_spearman_density_words": _spearman(densities, words),
    }


def census(out_dir: Path) -> dict[str, Any]:
    """Read the intermediate once and produce every declared population's numbers."""
    rows = list(read_intermediate(out_dir))
    market = [row for row in rows if not row.quarantined]
    litrpg = [row for row in market if row.litrpg]
    not_litrpg = [row for row in market if not row.litrpg]

    populations = {
        "litrpg_market": summarise(litrpg, label="LitRPG-tagged, quarantine subtracted"),
        "not_litrpg_control": summarise(
            not_litrpg, label="not LitRPG-tagged, quarantine subtracted"
        ),
        "quarantined_descriptor_half": summarise(
            [row for row in rows if row.quarantined and row.litrpg],
            label="LitRPG, descriptor half — reported, never pooled",
        ),
    }
    for cohort in ("human_pre_llm", "undeclared_2025", "declared_ai_2025"):
        populations[f"litrpg_{cohort}"] = summarise(
            [row for row in litrpg if row.cohort == cohort], label=f"LitRPG, {cohort}"
        )

    genre = populations["litrpg_market"]
    control = populations["not_litrpg_control"]

    def ratio(top: float | None, bottom: float | None) -> float | None:
        return round(top / bottom, 3) if top and bottom else None
    return {
        "instrument": PRE_REGISTRATION["instrument"],
        "registration_digest": REGISTRATION_DIGEST,
        "computed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "manifest": json.loads((out_dir / "manifest.json").read_text(encoding="utf-8")),
        "chapters_measured": len(rows),
        "quarantine_subtracted": sum(1 for row in rows if row.quarantined),
        "populations": populations,
        "validity_arm": {
            "reading": (
                "These counters must separate the genre from everything else. A separation "
                "near 1 would say they locate ordinary narration rather than progression. "
                "**The median ratio is not the statistic**: the control's median density is "
                "0.0, so a ratio over it is undefined and would read as a triumph. Mean "
                "density and coverage are reported instead, and coverage is the one to "
                "believe — it is a share, so no outlier chapter can move it."
            ),
            "litrpg_mean_per_1k": genre["density_per_1k"].get("mean"),
            "not_litrpg_mean_per_1k": control["density_per_1k"].get("mean"),
            "mean_separation": ratio(
                genre["density_per_1k"].get("mean"), control["density_per_1k"].get("mean")
            ),
            "litrpg_share_with_an_event": genre["coverage"].get("share_with_at_least_one"),
            "not_litrpg_share_with_an_event": control["coverage"].get(
                "share_with_at_least_one"
            ),
            "coverage_separation": ratio(
                genre["coverage"].get("share_with_at_least_one"),
                control["coverage"].get("share_with_at_least_one"),
            ),
            "control_family_share": control.get("family_share"),
        },
        "declares_no_bar": PRE_REGISTRATION["declares_no_bar"],
        "residuals": PRE_REGISTRATION["residuals"],
    }


# --------------------------------------------------------------------------- selftest


_SELFTEST_FURNITURE = """He opened the door.

[Level Up!]
[Strength +2]
[New Skill: Ember Cut]

The room was cold.
"""

_SELFTEST_PROSE = (
    "He had advanced to the third grade of the guild that morning, and it still did not "
    "feel real. Later he learned a new skill from the old smith. Nothing else happened."
)


def selftest() -> int:
    """Fails if the frozen block moves or either unit rule stops holding."""
    failures: list[str] = []

    if registration_digest() != REGISTRATION_DIGEST:
        failures.append("the frozen block moved; this is a different instrument")

    furniture = locate(_SELFTEST_FURNITURE)
    if len(furniture) != 1:
        failures.append(
            f"a three-line notification located {len(furniture)} events, not 1 — the "
            "block-run rule is broken and every furniture chapter is inflated"
        )
    elif furniture[0].family != "system_block":
        failures.append(f"the run was located as {furniture[0].family}")

    prose = locate(_SELFTEST_PROSE)
    if len(prose) != 2:
        failures.append(
            f"two progression sentences located {len(prose)} events, not 2 — the "
            "one-per-sentence rule is broken"
        )
    families = {event.family for event in prose}
    if families != {"level_up", "capability_gain"}:
        failures.append(f"prose families were {sorted(families)}")

    if locate("Nothing happens here. Nobody gains anything at all."):
        failures.append("inert prose located an event")

    aside = locate("[A/N: sorry for the late chapter, exams!]\n\nHe walked on.")
    if aside:
        failures.append("an author's note was counted as system furniture")

    # The correction, pinned as a property. A scene divider is the single most common line
    # shape on the platform and it is not a progression event.
    for divider in ("He stopped.\n\n***\n\nShe did not.", "One.\n\n---\n\nTwo.", "A.\n\n~~~\n\nB."):
        if locate(divider):
            failures.append(f"a scene divider was counted as an event: {divider!r}")

    boxed = locate("=====\n| Strength: 14 |\n| Level: 3 |\n=====\n\nHe closed it.")
    if len(boxed) != 1:
        failures.append(
            f"a box-drawn status sheet located {len(boxed)} events, not 1 — either the box "
            "hid its own content or the run rule broke"
        )

    for name in ("empty", "blank"):
        if locate("" if name == "empty" else "   \n\n  "):
            failures.append(f"{name} text located an event")

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"selftest OK — registration_digest {REGISTRATION_DIGEST}")
    return 0


# --------------------------------------------------------------------------- cli


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "command", choices=("materialise", "census", "selftest"), help="what to run"
    )
    parser.add_argument(
        "--out",
        default=str(DERIVED / "rr-chapters"),
        help="the gitignored intermediate directory",
    )
    parser.add_argument("--results", default=str(RESULTS / "progression-cadence.json"))
    parser.add_argument("--min-words", type=int, default=MIN_WORDS)
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()

    out_dir = Path(args.out)
    if args.command == "materialise":
        if selftest():
            return 1
        manifest = materialise(out_dir, min_words=args.min_words)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    payload = census(out_dir)
    target = Path(args.results)
    target.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""` because this file is committed and the repository is LF: Python's default
    # text mode would translate every "\n" to CRLF on this box and the diff would be the whole
    # file every run.
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="",
    )
    print(f"wrote {target}")
    print(json.dumps(payload["validity_arm"], indent=2))
    for name, population in payload["populations"].items():
        if population.get("n"):
            print(
                f"{name}: n={population['n']} "
                f"median/1k={population['density_per_1k']['p50']} "
                f"zero={population['coverage']['share_zero']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
