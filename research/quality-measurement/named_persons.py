"""Distributions for *how many names a chapter introduces*, the counter the 2026-08-22 read
nominated.

**Measurement only.** Nothing here feeds a prompt, a directive, or any generation path, and
nothing here admits an axis or declares a bar. `plan/reader-read-2.md` records how a counter
enters the registry — an operator act over a measured distribution — and stage-0 §81, §85, §87
and §89 record four separate occasions on which a bar was declared over a quantity that could
not do what it said. This produces the distribution and stops.

**What nominated it.** The operator read chapters 1 and 2 of *What Takes* and named *"too many
names and characters mentioned too fast into the story"* (`plan/reader-read-3.md` note 2). C6 —
*"in the first three hundred words of a scene, name at most three things a reader is expected to
remember"* — was in every drafting prompt and was honoured in every scene: the eight openings
score 2, 3, 1, 2, 3, 1, 2, 2 real names. **The budget is a scene-opening budget and it resets
four times a chapter.** Nothing bounds a chapter, which is the unit a reader receives.

**What this counts, and it is not what the module is named.** `domain/axes`' locator finds
capitalised tokens the book also writes mid-sentence. It cannot tell a person from a place, an
institution, or a month: on chapter 2 of *What Takes* it returns `February` and `Marker` beside
`Orne Marrow`. Separating those is a judgment and there is no instrument for it here, so every
figure below is **distinct proper names a chapter introduces**, and the operator's own hand
count of *persons* is reported beside it rather than replaced by it. Do not read a name count as
a person count, and do not classify a name as major or minor — that is the same judgment wearing
a different hat.

**Two known artefacts of the locator, carried rather than fixed.** Fixing a counter after seeing
its answer is the failure `platform_priors.py` freezes its matchers to avoid.

1. *Contractions.* `I'll`, `I'd`, `I've` satisfy every clause of `_is_candidate` and the book
   writes them mid-sentence, so they are "proven" names. Measured on *What Takes*: five across
   the eight scene openings, affecting four scenes. Reported in their own column, never dropped
   silently.
2. *A forename met before its surname counts twice.* The fold in
   `opening_proper_noun_names` only collapses a bare token into a fuller name when the fuller
   name has one candidate component, so `Doss` at word 198 and `Doss Orley` at word 924 are two
   introductions. Reported as measured.

**Two venvs, because one of them has pyarrow and the other is the repository.** The RoyalRoad
shards are parquet and only `C:/DEV/MirrorBench/.venv` can read them; everything else runs under
`uv run python`. The counter has no dependencies beyond the standard library, which is what lets
one implementation serve both:

    uv run python research/quality-measurement/named_persons.py --substrate local
    C:/DEV/MirrorBench/.venv/Scripts/python.exe \
        research/quality-measurement/named_persons.py --substrate royalroad
    uv run python research/quality-measurement/named_persons.py --substrate report

Each writes a JSON file beside this script; `--substrate report` merges them into the numbers
quoted in `named-persons-results.md`. A substrate that cannot be read reports **NOT RUN with its
reason**, in the table, never omitted.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))

from litharness.domain.axes import (  # noqa: E402
    proper_noun_introductions,
    strip_system,
)

LOCAL_JSON = HERE / "results" / "named-persons-local.json"
ROYALROAD_JSON = HERE / "results" / "named-persons-royalroad.json"

#: How many RoyalRoad chapters to draw. `opening_counters.py`'s figure, for the same reason it
#: gives: a wider baseline makes any one chapter's percentile less an artefact of where the cut
#: fell. It is a sample size, not a threshold.
ROYALROAD_TARGET = 2000

#: Quantiles reported for every distribution. **No bar is declared anywhere in this file** —
#: these are the shape of the population, not a line anything must clear. A chapter-grain
#: introduction budget, if the operator ever wants one, takes its number from here and the
#: setting of it is the operator's act.
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)

#: The locator's known contraction artefact. Matched on the emitted name rather than re-derived
#: from the text, so this list can only ever *report* the class and never change what was
#: counted. See the module docstring, artefact 1.
CONTRACTIONS = ("I'll", "I'd", "I've", "I'm", "I\N{RIGHT SINGLE QUOTATION MARK}ll",
                "I\N{RIGHT SINGLE QUOTATION MARK}d", "I\N{RIGHT SINGLE QUOTATION MARK}ve",
                "I\N{RIGHT SINGLE QUOTATION MARK}m")


@dataclass(frozen=True, slots=True)
class Chapter:
    """One chapter's introductions, as a reader receives them."""

    unit_id: str
    words: int
    #: `(name, token offset)` in reading order, exactly as the locator emitted them.
    introductions: tuple[tuple[str, int], ...]

    @property
    def contractions(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.introductions if name in CONTRACTIONS)

    @property
    def raw(self) -> int:
        return len(self.introductions)

    @property
    def net(self) -> int:
        """Introductions with the contraction artefact removed. Reported beside `raw`, never
        instead of it."""
        return self.raw - len(self.contractions)

    @property
    def per_1k(self) -> float:
        return round(1000.0 * self.net / self.words, 3) if self.words else 0.0

    def to_jsonable(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "words": self.words,
            "raw": self.raw,
            "net": self.net,
            "per_1k": self.per_1k,
            "contractions": list(self.contractions),
            "introductions": [
                {"name": name, "offset": offset} for name, offset in self.introductions
            ],
        }


def introductions_in(text: str) -> tuple[tuple[str, int], ...]:
    """Every distinct name a text introduces, with the offset of its first appearance.

    The whole text is the window: a chapter is the unit the read judged, and a window would be
    the scene-opening budget C6 already carries. `strip_system` first, because a `[STATUS]` line
    is not prose a reader is asked to hold names out of — the same guard `opening_proper_nouns`
    applies through its own tokeniser call.
    """
    body = strip_system(text)
    return proper_noun_introductions(body, window=len(body.split()) + 1)


def chapter_for(unit_id: str, text: str) -> Chapter:
    return Chapter(unit_id, len(text.split()), introductions_in(text))


def protagonist_share(text: str, protagonist: str) -> float | None:
    """Share of all name mentions in this text that are the protagonist's, or `None` when no
    protagonist id is known.

    **A whole-word case-folded count over the id's own parts**, which is the same rule
    `worlds.key_nouns` applies to a subject id and carries the same crudeness: a protagonist
    whose id shares a part with a place name is over-counted, and the count is reported so that
    can be seen rather than asserted away.

    `None` rather than `0.0` for a book with no declared protagonist, because "nobody is named
    as the protagonist" and "the protagonist is never mentioned" are different facts. Every
    book drafted before 2026-08-22 is the first.
    """
    wanted = {part.casefold() for part in protagonist.split("_") if len(part) > 2}
    if not wanted:
        return None
    mentions = sum(1 for token in _folded_tokens(text) if token in wanted)
    total = _name_mentions(text)
    return round(mentions / total, 3) if total else None


def _folded_tokens(text: str) -> list[str]:
    """Whitespace tokens with edge punctuation and case removed. Deliberately not `_tokens`:
    that one tracks sentence position for the locator, and this one is counting mentions of a
    name the locator has already proved."""
    return [
        word.strip(".,;:!?\"'()[]\N{RIGHT SINGLE QUOTATION MARK}").casefold()
        for word in strip_system(text).split()
    ]


def _name_mentions(text: str) -> int:
    """How many tokens in the text are one of the names the locator proved.

    Mentions rather than introductions: the read's third note is about *share of attention*
    ("in scene 1 he is named nine times to Ossary's seven"), which is a mention count and not a
    first-appearance count.
    """
    proven = {name for name, _ in introductions_in(text)}
    if not proven:
        return 0
    parts = {part.casefold() for name in proven for part in name.split()}
    return sum(1 for token in _folded_tokens(text) if token in parts)


def describe(values: list[float]) -> dict[str, object]:
    """Quantiles and moments for one population. Empty in, empty out — a substrate that could
    not be read reports that rather than a zero that looks like a measurement.
    `opening_counters.describe`, restated so the two files can be read side by side."""
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 3),
        "sd": round(statistics.pstdev(ordered), 3) if len(ordered) > 1 else 0.0,
        "min": ordered[0],
        "max": ordered[-1],
        "median": round(statistics.median(ordered), 3),
        "quantiles": {str(q): round(_quantile(ordered, q), 3) for q in QUANTILES},
    }


def _quantile(ordered: list[float], q: float) -> float:
    """Nearest-rank, so every reported value is one a text actually scored."""
    if len(ordered) == 1:
        return ordered[0]
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[index]


def percentile_of(value: float, population: list[float]) -> float | None:
    """Share of the population at or below `value`, as a percentage."""
    if not population:
        return None
    at_or_below = sum(1 for item in population if item <= value)
    return round(100.0 * at_or_below / len(population), 1)


# -- substrate (a): this system's own books, as published ---------------------------------


def own_chapters(root: Path | None = None) -> dict[str, list[Chapter]]:
    """Every assembled chapter under `book-library/`, grouped by shelf.

    **The published chapter is the unit, not the scene**, which is
    `opening_counters.reappraisal_chapters`' decision for the same reason: the scene is this
    system's unit of work and the read that nominated this counter judged a chapter. Reading
    the assembled form rather than reassembling it here keeps one implementation of
    `library.chapters_for`.

    `root` is a parameter because `book-library/` is gitignored derived output and a worktree
    does not have one — the shelves live in the checkout that ran the tick. A measurement run
    from a worktree points `--library` at that checkout and the result records which one, so a
    number can never be read as having come from a shelf it did not.
    """
    shelf_root = root or (REPO / "book-library")
    if not shelf_root.is_dir():
        return {}
    books: dict[str, list[Chapter]] = {}
    for shelf in sorted(shelf_root.iterdir()):
        chapters = sorted((shelf / "chapters").glob("Chapter*.txt")) if shelf.is_dir() else []
        if not chapters:
            continue
        books[shelf.name] = [
            chapter_for(f"{shelf.name}/{path.stem}", path.read_text(encoding="utf-8"))
            for path in chapters
        ]
    return books


def scenes_as_chapters(database: str, *, scenes_per_chapter: int = 4) -> list[Chapter]:
    """A book database's drafted scenes, grouped into the chapters a reader would receive.

    For a book whose shelf has not been published. `corpus_io.generated_scenes` is the loader —
    `CONTRIBUTING.md` says to use it rather than writing another — and `by_story` is what keeps
    two books in one database from being pooled into one sequence.
    """
    sys.path.insert(0, str(HERE))
    import corpus_io

    path = REPO / database
    if not path.exists():
        return []
    units = corpus_io.generated_scenes(path, min_words=0)
    out: list[Chapter] = []
    for work_id, chapters in sorted(corpus_io.by_story(units, min_chapters=1).items()):
        for index in range(0, len(chapters), scenes_per_chapter):
            block = chapters[index : index + scenes_per_chapter]
            out.append(
                chapter_for(
                    f"{work_id[:8]}/Chapter{index // scenes_per_chapter + 1}",
                    "\n\n".join(unit.text for unit in block),
                )
            )
    return out


# -- substrate (b): the cached RoyalRoad cohort -------------------------------------------


def royalroad(limit: int, genre_tag: str | None) -> tuple[list[Chapter], str | None]:
    """Chapters from the cached shards, or an empty list and the reason it is empty.

    A missing shard is **NOT RUN with a reason**, never a silent zero: a substrate that could
    not be read and a substrate that scored nothing are different facts, and only one of them
    is a measurement.
    """
    sys.path.insert(0, str(HERE))
    try:
        import corpus_io
    except ImportError as error:  # pragma: no cover - environment-dependent
        return [], f"corpus_io unavailable: {error}"
    try:
        units = list(
            corpus_io.royalroad_chapters(genre_tag=genre_tag, min_words=300, limit=limit)
        )
    except (FileNotFoundError, ImportError, ModuleNotFoundError) as error:
        return [], str(error)
    return [chapter_for(unit.unit_id, unit.text) for unit in units], None


# -- runners --------------------------------------------------------------------------------


def run_local(library: Path | None = None) -> dict[str, object]:
    books = own_chapters(library)
    payload: dict[str, object] = {
        "substrate": "own books, book-library/*/chapters/*.txt",
        "library_root": str(library or (REPO / "book-library")),
        "books": {
            name: {
                "chapters": [chapter.to_jsonable() for chapter in chapters],
                "net_summary": describe([float(chapter.net) for chapter in chapters]),
                "per_1k_summary": describe([chapter.per_1k for chapter in chapters]),
            }
            for name, chapters in books.items()
        },
    }
    every = [chapter for chapters in books.values() for chapter in chapters]
    payload["all_own_chapters"] = {
        "net_summary": describe([float(chapter.net) for chapter in every]),
        "per_1k_summary": describe([chapter.per_1k for chapter in every]),
    }
    if not books:
        payload["not_run"] = (
            f"no Chapter*.txt under {library or (REPO / 'book-library')}; "
            "book-library/ is gitignored derived output, so a worktree has none — "
            "point --library at the checkout that ran the tick"
        )
    return payload


def run_royalroad() -> dict[str, object]:
    overall, overall_reason = royalroad(ROYALROAD_TARGET, None)
    litrpg, litrpg_reason = royalroad(ROYALROAD_TARGET, "LitRPG")
    return {
        "substrate": "cached RoyalRoad shards via corpus_io.royalroad_chapters",
        "overall": {
            "not_run": overall_reason,
            "net_summary": describe([float(chapter.net) for chapter in overall]),
            "per_1k_summary": describe([chapter.per_1k for chapter in overall]),
            "net_values": [chapter.net for chapter in overall],
            "per_1k_values": [chapter.per_1k for chapter in overall],
        },
        "litrpg": {
            "not_run": litrpg_reason,
            "net_summary": describe([float(chapter.net) for chapter in litrpg]),
            "per_1k_summary": describe([chapter.per_1k for chapter in litrpg]),
            "net_values": [chapter.net for chapter in litrpg],
            "per_1k_values": [chapter.per_1k for chapter in litrpg],
        },
    }


def run_report() -> dict[str, object]:
    local = json.loads(LOCAL_JSON.read_text(encoding="utf-8"))
    try:
        rr = json.loads(ROYALROAD_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        rr = {"overall": {"not_run": f"{ROYALROAD_JSON.name} has not been written"}}
    overall = rr.get("overall", {}).get("net_values") or []
    litrpg = rr.get("litrpg", {}).get("net_values") or []
    placed: dict[str, object] = {}
    for book, entry in local["books"].items():
        for chapter in entry["chapters"]:
            placed[chapter["unit_id"]] = {
                "book": book,
                "words": chapter["words"],
                "raw": chapter["raw"],
                "net": chapter["net"],
                "per_1k": chapter["per_1k"],
                "percentile_overall": percentile_of(chapter["net"], overall),
                "percentile_litrpg": percentile_of(chapter["net"], litrpg),
            }
    return {
        "own_chapters": placed,
        "own_summary": local["all_own_chapters"],
        "royalroad_overall": rr.get("overall", {}).get("net_summary")
        or {"not_run": rr.get("overall", {}).get("not_run")},
        "royalroad_litrpg": rr.get("litrpg", {}).get("net_summary")
        or {"not_run": rr.get("litrpg", {}).get("not_run")},
        "no_bar": (
            "Descriptive. No threshold is declared here and none is implied; a chapter-grain "
            "introduction budget is the operator's to set."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--substrate", choices=("local", "royalroad", "report"), required=True)
    parser.add_argument(
        "--library",
        default=None,
        help="a book-library/ root to read shelves from (default: this checkout's)",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="a book database to read scenes from when its shelf is unpublished",
    )
    args = parser.parse_args(argv)

    if args.substrate == "local":
        payload = run_local(Path(args.library) if args.library else None)
        if args.database:
            payload["from_database"] = {
                "database": args.database,
                "chapters": [
                    chapter.to_jsonable() for chapter in scenes_as_chapters(args.database)
                ],
            }
        LOCAL_JSON.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif args.substrate == "royalroad":
        payload = run_royalroad()
        ROYALROAD_JSON.parent.mkdir(parents=True, exist_ok=True)
        ROYALROAD_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        payload = run_report()

    printable = payload
    if args.substrate == "royalroad":
        printable = {
            "overall": payload["overall"]["net_summary"],  # type: ignore[index]
            "litrpg": payload["litrpg"]["net_summary"],  # type: ignore[index]
            "not_run": payload["overall"]["not_run"],  # type: ignore[index]
        }
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
