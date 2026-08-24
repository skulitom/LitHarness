"""Eligibility, matching cells, and deterministic divergent pairing for the sim-readership backtest.

Stage one of the pipeline PREREG.md fixes: raw shard rows become `Fiction` records, the
ineligible are refused with named reasons, the eligible are bucketed into matching cells, and
pairs form within each cell on divergent outcome — `conversion = followers / total_views`,
the platform's own acquisition-to-retention ratio (PREREG §1). Everything here is
deterministic and model-free: no model call, no network, no scraping, and the parquet shards
are touched by exactly one lazily-importing function (`load_fiction_rows`) that no test ever
calls, so every behaviour below is checked on synthetic dict rows whose correct answers are
stated before anything runs.

Boundaries inherited from PREREG.md and not re-argued here: star ratings are neither the
outcome nor a matching variable; declared-AI books are excluded from every arm; chapters 1-3
are identified by parsed title ordinal, falling back to release order only when the dump
provably holds the whole fiction (§2); one fiction and one author appear at most once across
the whole pair output (§79's disjointness, enforced at both grains in `divergent_pairs`).
Refusal slugs come out in a fixed order so refusal counts stay comparable across runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
_QUALITY = HERE.parent / "quality-measurement"
if str(_QUALITY) not in sys.path:
    sys.path.insert(0, str(_QUALITY))

import corpus_io  # noqa: E402  # sibling research module, imported by path

#: Chapter-title ordinal, parsed from the dump's free-text titles ("Chapter 12", "ch. 04",
#: "Part 3"); anything else parses to None and the chapter carries no ordinal claim.
_ORDINAL = re.compile(r"^\s*(?:chapter|ch\.?|episode|part)\s*0*(\d+)\b", re.IGNORECASE)

#: Sort sentinel so no-ordinal chapters sort after numbered ones at the same timestamp rather
#: than crashing the sort key. Larger than any plausible chapter ordinal.
_UNORDERED = 1 << 62

#: Raw-exposure floor (PREREG §1): total_views below this excludes a fiction outright — an
#: exposure guard, deliberately not an exposure model. This constant states the registered
#: value until PREREG stamps it at registration.
VIEW_FLOOR: int = 300

#: Lead tag families, in priority order: the first member present in a fiction's tags names
#: its half of the matching cell; a fiction carrying none lands in "other".
LEAD_TAGS: tuple[str, ...] = (
    "LitRPG",
    "Progression",
    "Portal Fantasy / Isekai",
    "High Fantasy",
    "Sci-fi",
)

#: A blurb under this many words cannot seed the P-arm's premise excerpt (PREREG §1's
#: "blurb present (>= 30 words)" matching term).
BLURB_MIN_WORDS = 30


@dataclass(frozen=True, slots=True)
class Chapter:
    """One chapter row: the ordinal parsed from its title (or None), and the prose.

    `text` is what the arms excerpt. The real dump carries no `words` column, so
    `words` derives from `text` unless a synthetic row supplies one directly.
    """

    chapter_id: str
    released_at: str  # ISO date-time string as the dump carries it
    ordinal: int | None
    words: int
    text: str = ""


@dataclass(frozen=True, slots=True)
class Fiction:
    """One fiction assembled from its denormalised shard rows.

    Field names mirror the dump columns; `tags` and `warnings` arrive as JSON strings and are
    decoded once here. `status` stays as recorded, including the dump's None — PREREG §1:
    status is unrecorded for 17,476 books and matches None to None.
    """

    fiction_id: str
    title: str
    author: str
    tags: tuple[str, ...]
    warnings: tuple[str, ...]
    description: str
    status: str | None
    followers: float
    total_views: float
    average_views: float
    first_release: str  # earliest chapter released_at; "" when no chapters
    chapters: tuple[Chapter, ...]  # sorted by (released_at, ordinal-or-large)


def _json_strings(raw: Any) -> tuple[str, ...]:
    """Decode a dump JSON array column ("exactly as the dump stores it") to a tuple.

    Missing, null, or malformed values degrade to empty rather than refusing the fiction:
    the dump's null-heavy columns are a fact about the crawl, not a reason to lose the book.
    """
    if not isinstance(raw, str) or not raw.strip():
        return ()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return tuple(str(item) for item in parsed)


def _ordinal_of(title: Any) -> int | None:
    if not isinstance(title, str):
        return None
    match = _ORDINAL.match(title)
    return int(match.group(1)) if match else None


def _chapter_from_row(row: Mapping[str, Any]) -> Chapter:
    text = str(row.get("text") or "")
    raw_words = row.get("words")
    return Chapter(
        chapter_id=str(row.get("chapter_id")),
        released_at=str(row.get("release_datetime") or ""),
        ordinal=_ordinal_of(row.get("chapter_title")),
        words=int(raw_words) if raw_words is not None else len(text.split()),
        text=text,
    )


def fiction_from_rows(rows: Sequence[Mapping[str, Any]]) -> Fiction:
    """Assemble one `Fiction` from the dump rows of a single `fiction_id`.

    Rows are the shards' denormalised chapter rows: every row carries the fiction-level
    columns (`fiction_id`, `title`, `author`, `tags`, `warnings`, `description`, `status`,
    `followers`, `total_views`, `average_views`) plus its own chapter columns (`chapter_id`,
    `chapter_title`, `release_datetime`, `text`; a synthetic `words` column is honoured
    when present — the real dump has none).

    Raises ValueError on an empty sequence or rows spanning more than one fiction_id —
    both are loader bugs upstream, not data conditions to absorb silently.
    """
    if not rows:
        raise ValueError("fiction_from_rows: empty row sequence")
    fiction_ids = {str(row.get("fiction_id")) for row in rows}
    if len(fiction_ids) != 1:
        raise ValueError(f"fiction_from_rows: mixed fiction_ids {sorted(fiction_ids)}")
    head = rows[0]
    chapters = sorted(
        (_chapter_from_row(row) for row in rows),
        key=lambda chapter: (
            chapter.released_at,
            chapter.ordinal if chapter.ordinal is not None else _UNORDERED,
        ),
    )
    status = head.get("status")
    return Fiction(
        fiction_id=str(head.get("fiction_id")),
        title=str(head.get("title") or ""),
        author=str(head.get("author") or ""),
        tags=_json_strings(head.get("tags")),
        warnings=_json_strings(head.get("warnings")),
        description=str(head.get("description") or ""),
        status=status if isinstance(status, str) else None,
        followers=float(head.get("followers") or 0),
        total_views=float(head.get("total_views") or 0),
        average_views=float(head.get("average_views") or 0),
        first_release=chapters[0].released_at if chapters else "",
        chapters=tuple(chapters),
    )


def recovered_chapter_count(fiction: Fiction) -> int | None:
    """Chapter count recovered as round(total_views / average_views); None at zero average.

    The count the dump lets us prove without trusting its chapter rows to be complete
    (PREREG §1's matching term). None means unrecoverable, which is its own cell band.
    """
    if fiction.average_views == 0:
        return None
    return round(fiction.total_views / fiction.average_views)


def conversion(fiction: Fiction) -> float | None:
    """The outcome variable: followers / total_views; None when views are 0."""
    if fiction.total_views == 0:
        return None
    return fiction.followers / fiction.total_views


def chapters_1_to_3(fiction: Fiction) -> tuple[Chapter, ...] | None:
    """The identified opening chapters per PREREG §2, or None when they cannot be identified.

    Parsed ordinals {1, 2, 3} all present wins outright — those chapters, in ordinal order.
    Otherwise, when the dump provably holds the whole fiction (cached chapter count >= the
    recovered count) and holds at least three chapters, release order identifies them. Any
    other shape returns None, which eligibility refuses as "no_ch123".
    """
    by_ordinal = {chapter.ordinal: chapter for chapter in fiction.chapters}
    if {1, 2, 3} <= by_ordinal.keys():
        return tuple(by_ordinal[ordinal] for ordinal in (1, 2, 3))
    recovered = recovered_chapter_count(fiction)
    if recovered is not None and len(fiction.chapters) >= recovered and len(fiction.chapters) >= 3:
        return fiction.chapters[:3]
    return None


def _cohort(fiction: Fiction) -> str | None:
    """The fiction's era cohort; the standing logic is delegated verbatim to `corpus_io`."""
    return corpus_io.era_cohort(fiction.first_release, json.dumps(list(fiction.warnings)))


def eligibility(fiction: Fiction) -> str | None:
    """None when the fiction may enter the main arms; otherwise the FIRST failing reason.

    The order is fixed (PREREG §1: refusal counts comparable across runs) and moves from
    identity to coverage to outcome: a declared-AI fiction is refused as such even when it
    would also fail the blurb check, because the tag's audience effect is why it leaves.
    "no_cohort" covers every date/warning shape `era_cohort` declines to label, including a
    pre-LLM book that later declared AI assistance — the corpus's own rule that such a record
    says nothing either way. "no_outcome" fires when conversion exists but is unusable for
    ratio pairing (zero, negative, or non-finite); conversion being None is not reachable
    here, because zero views has already failed the exposure floor by then.
    """
    cohort = _cohort(fiction)
    if cohort == "declared_ai_2025":  # corpus_io.era_cohort's declared-2025 label
        return "declared_ai"
    if cohort is None:
        return "no_cohort"
    if len(fiction.description.split()) < BLURB_MIN_WORDS:
        return "blurb_short"
    if chapters_1_to_3(fiction) is None:
        return "no_ch123"
    if fiction.total_views < VIEW_FLOOR:
        return "low_exposure"
    outcome = conversion(fiction)
    if outcome is None or not math.isfinite(outcome) or outcome <= 0:
        return "no_outcome"
    return None


def cell_key(fiction: Fiction) -> tuple[str, str, str, str]:
    """The matching cell: (cohort, lead tag family, chapter band, status-as-recorded).

    Band bounds are PREREG §1's: short < 8 <= mid < 25 <= long, on the recovered count;
    "unknown" when that count cannot be recovered. Status normalises None to "" so the dump's
    unrecorded statuses match each other (None to None) without widening the tuple's type.
    An empty cohort is only reachable for fictions `eligibility` already refused; callers
    pair within cells after that filter.
    """
    cohort = _cohort(fiction) or ""
    family = next((tag for tag in LEAD_TAGS if tag in fiction.tags), "other")
    recovered = recovered_chapter_count(fiction)
    if recovered is None:
        band = "unknown"
    elif recovered < 8:
        band = "short"
    elif recovered < 25:
        band = "mid"
    else:
        band = "long"
    return (cohort, family, band, fiction.status or "")


@dataclass(frozen=True, slots=True)
class Pair:
    """One divergent pair: content-addressed, high conversion first."""

    pair_id: str  # sha256[:16] over the two fiction_ids sorted — content-addressed
    high: str  # fiction_id of the higher-conversion member
    low: str
    cell: tuple[str, str, str, str]
    ratio: float  # high conversion / low conversion


def _pair_id(high_id: str, low_id: str) -> str:
    """sha256 hex prefix over the NUL-joined, sorted fiction ids — order-free by construction."""
    joined = "\x00".join(sorted((high_id, low_id)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def divergent_pairs(
    fictions: Sequence[Fiction], *, min_ratio: float = 3.0
) -> list[Pair]:
    """Pair within each cell on divergent outcome; one fiction and one author, once each.

    Greedy and deterministic. Fictions failing `eligibility` are skipped. Cells are
    processed in sorted key order. Within a cell, the pool holds that cell's survivors,
    repeatedly re-filtered against the ids and authors already committed ACROSS THE WHOLE
    OUTPUT (so a leftover member whose author a previous round spent leaves the pool rather
    than pairing again) and sorted ascending by (conversion, fiction_id). Each round: take
    the highest remaining; take the lowest remaining whose author differs from its (a
    conflicting lowest is skipped, not wasted — it simply cannot partner this high); if the
    ratio clears `min_ratio`, emit the pair and commit both members, otherwise drop only the
    high — it cannot clear the floor even against the easiest partner left. Ties break on
    fiction_id throughout, so the output is a pure function of the input set.
    """
    scored: dict[tuple[str, str, str, str], list[tuple[float, Fiction]]] = {}
    for fiction in fictions:
        if eligibility(fiction) is not None:
            continue
        outcome = conversion(fiction)
        if outcome is None or outcome <= 0 or not math.isfinite(outcome):
            continue  # unreachable past eligibility; kept so the invariant lives here too
        scored.setdefault(cell_key(fiction), []).append((outcome, fiction))

    pairs: list[Pair] = []
    used_authors: set[str] = set()
    used_ids: set[str] = set()
    for cell in sorted(scored):
        pool = sorted(
            ((outcome, fiction) for outcome, fiction in scored[cell]),
            key=lambda entry: (entry[0], entry[1].fiction_id),
        )
        while True:
            pool = [
                (outcome, fiction)
                for outcome, fiction in pool
                if fiction.fiction_id not in used_ids and fiction.author not in used_authors
            ]
            if len(pool) < 2:
                break
            high_outcome, high = pool.pop()
            low_index = next(
                (i for i, (_, candidate) in enumerate(pool) if candidate.author != high.author),
                None,
            )
            if low_index is None:
                break  # every remaining member shares the high's author; this cell is spent
            low_outcome, low = pool.pop(low_index)
            ratio = high_outcome / low_outcome
            if ratio < min_ratio:
                continue  # the floor excludes this near pair; the low stays in the pool
            used_authors.update((high.author, low.author))
            used_ids.update((high.fiction_id, low.fiction_id))
            pairs.append(
                Pair(
                    pair_id=_pair_id(high.fiction_id, low.fiction_id),
                    high=high.fiction_id,
                    low=low.fiction_id,
                    cell=cell,
                    ratio=ratio,
                )
            )
    return pairs


def excerpt_digest(text: str) -> str:
    """sha256 hex over the utf-8 bytes — the cache address for a blinded excerpt."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_fiction_rows(paths: Sequence[Path]) -> Iterator[list[dict[str, Any]]]:
    """Yield each fiction's denormalised row dicts from cached RoyalRoad parquet shards.

    The ONE parquet touch in this module, imported lazily so nothing else here — and no
    test — needs pyarrow. It runs under the MirrorBench venv
    (`C:/DEV/MirrorBench/.venv/Scripts/python.exe`), the only interpreter on this machine
    that carries pyarrow; everything else runs under `uv run`, which must never need it
    (`corpus_io.py`'s two-venv pattern). Rows come back grouped per fiction in first-seen
    shard order, ready for `fiction_from_rows`.
    """
    import pyarrow.parquet  # lazy by design; see the docstring

    grouped: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        table = pyarrow.parquet.read_table(path)
        for row in table.to_pylist():
            grouped.setdefault(str(row.get("fiction_id")), []).append(row)
    yield from grouped.values()
