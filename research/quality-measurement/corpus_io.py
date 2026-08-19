"""Uniform access to every prose source on this machine, for craft-measurement experiments.

Research code, deliberately outside `src/`: nothing here is imported by the package, nothing
here is gated on, and it depends on pyarrow and a 12.5GB corpus that CI must never need. It
exists so that four candidate measurement designs read their inputs the same way and a
disagreement between two experiments is a disagreement about method rather than about parsing.

**No prose is written back out.** Loaders yield text in memory; every artifact this directory
commits is numbers.

Three sources, in ascending order of how much they can prove:

- `fixture_scenes` — the golden 6-scene books. ~130 words a scene, which is far too small to
  measure anything and exactly the right size for a *falsification*: the mystery's dramatic
  ordering is known (scene 6, the confession and arrest, is the peak; scene 1, pure
  exposition, is the floor) and `scene_change_profile` died by ranking it upside down.
- `mol_chapters` — Mother of Learning, 108 chapters of real published serial prose at ~7k
  words each, with 386 reader reviews carrying five score columns. One book, so any
  between-story confound is held fixed by construction and any within-story confound
  (position, publication date) is wide open.
- `royalroad_chapters` — the two cached shards. The only source with cohort structure: era,
  declared-AI, author, story, and an engagement label.
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

#: Fallback only. The golden books ship inside `litharness_contracts` as of 0.2.0 and
#: `fixture_scenes` asks the package for them; this checkout path is what it falls back to
#: under an interpreter that does not have the package installed — MirrorBench's venv, which
#: `baseline.py` explains is in play for anything touching torch.
CONTRACTS = Path("C:/DEV/litharness-contracts")
MOL = Path("C:/DEV/BookCrawler/data/mother-of-learning-20220313")
HF_CACHE = Path.home() / ".cache/huggingface/hub/datasets--OmniAICreator--RoyalRoad-1.61M"

#: Which shard is which cohort. Not arbitrary: the corpus is ordered so low shard numbers are
#: recent. `build_craft_profile.py` (beside this file since the archive move) picked the same
#: two and its cohort logic is the reference for anything computed here.
SHARDS = {3: "recent", 30: "older"}

GENRE_TAG = "LitRPG"
AI_WARNING = "AI-Assisted Content"
PRE_LLM_YEAR = "2023"


@dataclass(frozen=True, slots=True)
class Unit:
    """One measurable span of prose, with everything a control might need to hold fixed.

    `meta` carries source-specific fields rather than the dataclass growing a column per
    source: an experiment that needs `followers` knows it is reading RoyalRoad, and an
    experiment that does not should not be able to reach for it by accident.
    """

    unit_id: str
    source: str
    text: str
    #: Position within its parent work, 1-based. The confound that killed the comment-count
    #: proxy, so it is a first-class field rather than something to recover later.
    position: int
    work_id: str
    author_id: str | None = None
    #: ISO date. The confound that killed `tricolon_rate`; same reasoning as `position`.
    released_at: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def words(self) -> int:
        return len(self.text.split())


# --------------------------------------------------------------------------- fixtures


def fixture_scenes(book: str = "mystery") -> list[Unit]:
    """The six golden scenes in reading order.

    Ordering ground truth for `mystery`, from PLAN.md §10.6's own falsification of
    `scene_change_profile`: scene 6 is the dramatic peak and scene 1 is the flattest. That is
    two anchors on a six-item list, not a full ranking, and an experiment claiming more from
    this fixture than "did it get those two right" is over-reading 800 words.
    """
    # Imported here rather than at module scope: the other loaders in this file are used from
    # interpreters that do not have `litharness_contracts` installed (see CONTRACTS above),
    # and only this function needs it.
    try:
        from litharness_contracts.fixtures import golden_path

        path = golden_path(book, "manuscript.json")
    except ImportError:
        path = CONTRACTS / "src/litharness_contracts/fixtures/golden" / book / "manuscript.json"
    manuscript = json.loads(path.read_text(encoding="utf-8"))
    units = []
    for node in manuscript["nodes"]:
        if node.get("kind") != "scene":
            continue
        logical = str(node["logical_id"])
        units.append(
            Unit(
                unit_id=f"{book}:{logical}",
                source="fixture",
                text=node.get("content") or "",
                position=int(logical.rsplit("-", 1)[-1]),
                work_id=book,
                meta={"title": node.get("title")},
            )
        )
    return sorted(units, key=lambda unit: unit.position)


# --------------------------------------------------------------------- generated prose


#: A fixed stamp for `export.collect`. The generated-at field only reaches the rendered
#: document's front matter, which this loader discards — and a wall-clock value would put the
#: run time into an otherwise deterministic read.
_EXPORT_STAMP = "1970-01-01T00:00:00Z"


def generated_scenes(
    database: str | Path,
    *,
    book: str | None = None,
    branch: str | None = None,
    revision: str | None = None,
    min_words: int = 200,
) -> list[Unit]:
    """Drafted scenes from a book database — this system's own prose, in reading order.

    **The only un-memorised source in this file, and that is the whole reason it exists.**
    BRIEF.md §2 Pass 6's transferable rule is that a model-based measure validated on published
    fiction either runs on text the scoring model provably has not memorised or measures its
    familiarity term explicitly; §3's status note names this system's own generated prose as the
    one remaining untried direction, *and* prices it in the same sentence — no published-reader
    label reaches it. Both halves are true of what this returns: gates 0 and 1 of
    `plan/persona-reader-validity.md` can run on it honestly, and gate 3 cannot.

    Reads through `application/export.collect` rather than querying tables, so it sees exactly
    the prose `litharness export` would show a reader — one revision, live nodes, reading order,
    with the same branch-resolution rules. A scene that has not been drafted carries no content
    and is skipped rather than emitted empty; `min_words` drops the stubs that are technically
    drafted and too short for a paragraph-level ablation to do anything to.

    Imported lazily for the reason the rest of this module gives: these loaders are called from
    interpreters that do not have this project installed, and only this one needs it.
    """
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application import export as export_module
    from litharness.domain.nodes import NodeKind

    store = SqliteStore.open(str(database))
    try:
        book_id, branch_id = export_module.resolve_branch(store, book, branch)
        document = export_module.collect(
            store,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=revision,
            generated_at=_EXPORT_STAMP,
        )
    finally:
        store.close()

    ordinals = {scene.logical_id: scene.ordinal for scene in document.scenes}
    units: list[Unit] = []
    for node in document.body:
        if node.kind is not NodeKind.SCENE or not node.content:
            continue
        if len(node.content.split()) < min_words:
            continue
        units.append(
            Unit(
                unit_id=f"gen:{node.logical_id}",
                source="generated",
                text=node.content,
                position=ordinals.get(node.logical_id, 0),
                work_id=document.book_id,
                meta={
                    "title": node.title,
                    "branch_id": document.branch_id,
                    "revision_id": document.revision_id,
                    "book_title": document.title,
                },
            )
        )
    return sorted(units, key=lambda unit: unit.position)


# ------------------------------------------------------------------------------- MoL


def mol_chapters() -> list[Unit]:
    """Mother of Learning, in publication order, from the Wayback capture.

    `source_capture_timestamp` is carried into `meta` deliberately. It is the field that
    refuted the comment-count proxy — the archive looked at different chapters on different
    days — so any experiment over this book that produces a per-chapter number owes a control
    against it, and the control is only computable if the field travels with the text.
    """
    index = MOL / "chapters.csv"
    units = []
    with index.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("content_status") != "available":
                continue
            body = MOL / row["content_file"]
            if not body.is_file():
                continue
            units.append(
                Unit(
                    unit_id=f"mol:{row['chapter_id']}",
                    source="mol",
                    text=body.read_text(encoding="utf-8"),
                    position=int(row["position"]),
                    work_id="mother-of-learning",
                    author_id="nobody103",
                    released_at=(row.get("published_at") or "")[:10] or None,
                    meta={
                        "title": row.get("title"),
                        "word_count": int(row["word_count"]) if row.get("word_count") else None,
                        "capture_timestamp": row.get("source_capture_timestamp"),
                    },
                )
            )
    return sorted(units, key=lambda unit: unit.position)


def mol_reviews() -> list[dict[str, Any]]:
    """Reader reviews with their five score columns.

    Returned raw rather than typed, because the first job of any experiment using these is to
    establish what is actually populated. `plan/craft-corpus.md` §4.5 records five score
    columns advertised on a dataset card and 100% null in the data; the lesson is to check
    rather than to model.
    """
    with (MOL / "reviews.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


# ------------------------------------------------------------------------- RoyalRoad


#: The dataset snapshot every number in this directory was measured against. Resolution was
#: originally `snapshots/*` glob, `matches[-1]` — which is not a pin: a cache refresh would
#: swap the corpus underneath every committed result and nothing would say so. A different
#: snapshot is different evidence, exactly as a rebuilt craft profile is (`calibration.py`
#: refuses a stale `profile_digest` for the same reason) — bump this deliberately, and re-run
#: whatever cites the corpus when you do.
SNAPSHOT_REVISION = "0e4df3f22999a7b7fa13b1e7564a09b5f3eb964e"


@lru_cache(maxsize=2)
def _shard_path(shard: int) -> Path:
    name = f"train-{shard:05d}-of-00047.parquet"
    path = HF_CACHE / "snapshots" / SNAPSHOT_REVISION / "data" / name
    if not path.is_file():
        others = sorted(HF_CACHE.glob(f"snapshots/*/data/{name}"))
        hint = f"; the cache holds {[p.parts[-3][:12] for p in others]}" if others else ""
        raise FileNotFoundError(
            f"shard {shard} at pinned snapshot {SNAPSHOT_REVISION[:12]} is not in the HF "
            f"cache{hint}. A different snapshot is different evidence — update "
            "SNAPSHOT_REVISION deliberately and re-run what cites the corpus."
        )
    return path


def era_cohort(released_at: str | None, warnings_json: str | None) -> str | None:
    """The cohort a chapter belongs to, or None to skip it.

    Reproduced from `build_craft_profile.py::cohort_of` rather than imported, because
    that tool is a committed artifact-builder and this is research code that must be free to
    disagree with it. Any disagreement is a finding; a silent shared import would hide one.
    """
    warnings = json.loads(warnings_json or "[]")
    year = (released_at or "")[:4]
    declared = AI_WARNING in warnings
    if not year:
        return None
    if year < PRE_LLM_YEAR:
        # A pre-LLM chapter whose story later declared AI assistance says nothing about this
        # chapter, so it is dropped rather than counted either way.
        return None if declared else "human_pre_llm"
    if year >= "2025":
        return "declared_ai_2025" if declared else "undeclared_2025"
    return None


def royalroad_chapters(
    *,
    shards: tuple[int, ...] = tuple(SHARDS),
    genre_tag: str | None = GENRE_TAG,
    min_words: int = 300,
    limit: int = 0,
) -> Iterator[Unit]:
    """Stream chapters from the cached shards, tagged with cohort and engagement.

    A generator because two shards are 497MB of parquet and materialising every LitRPG chapter
    as a `Unit` costs more memory than any experiment here needs at once.

    `conversion = followers / total_views` is computed here rather than at each call site, and
    it is the one derived field that gets a name: it is `plan/craft-corpus.md` §3's measured
    label, and a second, subtly different definition appearing in one experiment is how two
    results stop being comparable.
    """
    import pyarrow.parquet as pq

    columns = [
        "tags", "warnings", "release_datetime", "text", "fiction_id",
        "followers", "favorites", "total_views", "chapter_id", "title",
        # Added under stage-0 §89, for two confounds the pairing could not see without them.
        # `author` — §79 selects pairs disjoint at *story* level, which is not the same as
        # disjoint at author level; at 107 stories the pool held 105 authors and the gap was
        # ignorable, and the expansion to 616 makes it something to measure rather than assume.
        # `average_views` — mean views per chapter, the only unexploited rate covariate, and
        # `round(total_views / average_views)` recovers a fiction's true published chapter count
        # (`pages` is 100% null), which is per-story maturity independent of which shards are
        # cached. Both are recorded and neither changes selection.
        "author", "average_views",
    ]
    emitted = 0
    for shard in shards:
        table = pq.read_table(_shard_path(shard), columns=columns)
        for row in table.to_pylist():
            if genre_tag is not None and genre_tag not in json.loads(row.get("tags") or "[]"):
                continue
            cohort = era_cohort(row.get("release_datetime"), row.get("warnings"))
            if cohort is None:
                continue
            text = row.get("text") or ""
            if len(text.split()) < min_words:
                continue
            views = float(row.get("total_views") or 0)
            followers = float(row.get("followers") or 0)
            yield Unit(
                unit_id=f"rr:{row.get('chapter_id')}",
                source="royalroad",
                text=text,
                # Not a true chapter index: the shards are not story-ordered, so position
                # within a story has to be recovered by sorting on release date per fiction.
                # Left at 0 so that nothing reads it as one by accident.
                position=0,
                work_id=str(row.get("fiction_id")),
                released_at=(row.get("release_datetime") or "")[:10] or None,
                meta={
                    "cohort": cohort,
                    "shard": shard,
                    "followers": followers,
                    "favorites": float(row.get("favorites") or 0),
                    "total_views": views,
                    "conversion": (followers / views) if views else None,
                    "title": row.get("title"),
                    "author": row.get("author"),
                    "average_views": float(row.get("average_views") or 0),
                },
            )
            emitted += 1
            if limit and emitted >= limit:
                return


def by_story(units: list[Unit], *, min_chapters: int = 5) -> dict[str, list[Unit]]:
    """Group into stories with enough chapters for a within-story design, ordered by release.

    The whole reason to bother: every measurement in the refutation ledger compared chapters
    *across* stories, where era, author, maturity and cadence all vary at once. Grouping is
    what makes the confound-free comparison available, and `min_chapters` is what stops a
    two-chapter story contributing a within-story statistic computed on one pair.
    """
    grouped: dict[str, list[Unit]] = {}
    for unit in units:
        grouped.setdefault(unit.work_id, []).append(unit)
    ordered = {}
    for work_id, chapters in grouped.items():
        if len(chapters) < min_chapters:
            continue
        chapters.sort(key=lambda unit: (unit.released_at or "", unit.unit_id))
        # Positions are deliberately *not* assigned here. Release order inside a shard is the
        # only ordering available and it is not the story's chapter order — a shard holds an
        # arbitrary slice of each fiction — so stamping `position` would manufacture an index
        # a caller would reasonably read as the real one. Callers that need a within-sequence
        # index assign it themselves and own the claim.
        ordered[work_id] = chapters
    return ordered


if __name__ == "__main__":
    print("fixtures:", len(fixture_scenes("mystery")), "mystery scenes,",
          len(fixture_scenes("litrpg")), "litrpg scenes")
    chapters = mol_chapters()
    print("mol:", len(chapters), "chapters,", sum(unit.words for unit in chapters), "words")
    reviews = mol_reviews()
    print("mol reviews:", len(reviews), "rows; columns:", sorted(reviews[0]) if reviews else "-")
    try:
        sample = list(royalroad_chapters(limit=200))
    except Exception as exc:  # pragma: no cover - research script
        print("royalroad:", type(exc).__name__, exc, file=sys.stderr)
    else:
        print("royalroad:", len(sample), "chapters sampled;",
              len({unit.work_id for unit in sample}), "stories")
