"""Where a chapter's last paragraph is, and four things about it that need no model.

**Locator and deterministic descriptors only. Nothing here classifies a shape.** stage-0 §104.4
registered *chapter-hook shapes* — "what a chapter's last paragraph does, as a small closed set
of located contrasts" — as a mining-side property under §97.4, gated on an anchor set that is
three verified summits of eleven. That gate is an operator decision and this file does not touch
it: "a question opened / a reversal / an arrival / a threat named / a price paid" is a located
*contrast* judgment, a regex for it is the shallow-because-easy metric §1a.1 refuses, and a model
asked for it is a new verbal protocol with no validity evidence. What is admissible before the
anchor set lands is the **locator** and counters that read characters, which is what this is.

**Measurement only.** Nothing here feeds a prompt, a directive, a beat function or the axis
registry; no counter in this file is admitted anywhere. Every number it prints is descriptive and
**no bar is declared** — not one of these quantities has a direction anybody has earned.

**Two venvs, for `opening_counters.py`'s reason.** The RoyalRoad shards are parquet and only
`C:/DEV/MirrorBench/.venv` can read them; `corpus_io.generated_scenes` imports the package, which
that interpreter does not have. So the substrates run apart and a third pass merges them:

    uv run python research/quality-measurement/chapter_endings.py --substrate local
    C:/DEV/MirrorBench/.venv/Scripts/python.exe \
        research/quality-measurement/chapter_endings.py --substrate royalroad
    uv run python research/quality-measurement/chapter_endings.py --substrate report

Each writes a JSON file beside this script; the merged numbers are quoted in
`chapter-endings-census.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections.abc import Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

from litharness.domain.axes import strip_system  # noqa: E402

LOCAL_JSON = HERE / "chapter-endings-local.json"
ROYALROAD_JSON = HERE / "chapter-endings-royalroad.json"

#: How many RoyalRoad LitRPG chapters to draw. Larger than `opening_counters`' 2000 because the
#: descriptors here are per-chapter booleans, and a rate near zero needs more draws than a mean
#: does before its confidence interval is narrower than the thing being described.
ROYALROAD_TARGET = 3000

#: A blank line, which is what separates paragraphs in every source here — the export writer's
#: own separator, and RoyalRoad's after its HTML is flattened.
_BLANK_LINE = re.compile(r"\n[ \t]*\n")

#: A double quote in any of the four spellings this corpus uses. The own-generated books use
#: ASCII `"` exclusively and the RoyalRoad shards use curly quotes almost exclusively, so a rule
#: written for either alone scores zero on the other.
_QUOTES = (
    "\"'"
    "\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
    "\N{RIGHT SINGLE QUOTATION MARK}"
)

#: Trailing punctuation to look past when asking whether a paragraph ends on a question. A
#: closing quote after the mark is the ordinary spelling of a line of dialogue that asks
#: something, and a rule that missed it would report the genre's commonest question as none.
_CLOSERS = (
    "\"')]* "
    "\N{RIGHT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
    "\N{HORIZONTAL ELLIPSIS}"
)


def _normalised(block: str) -> str:
    """One block of text with its system voice removed and its whitespace collapsed.

    `axes.strip_system` substitutes a **space**, not the empty string, so a block that was
    nothing but a `[STATUS]` line comes back as `" "` and reads as truthy. Collapsing before
    testing for emptiness is what stops every system-line ending being counted as a prose
    paragraph of zero words.
    """
    return " ".join(strip_system(block).split())


def paragraphs(chapter_text: str) -> list[str]:
    """The chapter's prose paragraphs, in order, with system-voice lines excluded.

    System lines are dropped **within** a block rather than by splitting on them, so a paragraph
    that carries a status line in its middle stays one paragraph. That is the difference between
    describing the prose and describing where the system voice happened to fall.
    """
    return [
        prose for block in _BLANK_LINE.split(chapter_text) if (prose := _normalised(block))
    ]


def final_paragraph(chapter_text: str) -> str:
    """**The locator.** The last prose paragraph a reader arrives at, system voice excluded.

    Empty for a text that is nothing but system voice, which is a reading rather than a failure:
    such a chapter has no final prose paragraph and reporting a zero-word one would be a
    measurement of something that is not there.
    """
    found = paragraphs(chapter_text)
    return found[-1] if found else ""


def last_line(chapter_text: str) -> str:
    """The literal last non-empty line, system voice **included** — what a reader sees last."""
    lines = [line for line in chapter_text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def is_system_line(line: str) -> bool:
    """Whether this line is entirely system voice, by `axes.strip_system`'s own definition.

    Asked by stripping rather than by a second pattern: a line that survives stripping as
    nothing was nothing but system voice, and reusing the function keeps this census and every
    axis counter reading the same `_SYSTEM` — which is wider than `[STATUS]` alone (any
    bracketed all-caps tag, and any bold span).
    """
    return bool(line.strip()) and not strip_system(line).strip()


def is_dialogue(paragraph: str) -> bool:
    """Whether the paragraph opens or closes on a quotation mark.

    Deliberately shallow and named as such: this counts a *typographic* fact, not "the chapter
    ends on speech". A paragraph of narration that ends on a quoted phrase scores true and a
    line of unquoted dialogue scores false. It is reported because it is checkable, not because
    it is the question.
    """
    if not paragraph:
        return False
    return paragraph[0] in _QUOTES or paragraph[-1] in _QUOTES


def ends_on_question(paragraph: str) -> bool:
    """Whether the paragraph's last sentence is a question, looking past closing punctuation."""
    trimmed = paragraph.rstrip(_CLOSERS)
    return trimmed.endswith("?")


def describe(text: str) -> dict[str, object]:
    """Every descriptor for one unit, plus the penultimate paragraph as its own control.

    **The penultimate is not decoration.** On RoyalRoad the last block of a chapter is often an
    author's note rather than the story, and nothing deterministic separates the two — so the
    final-paragraph numbers there carry a contamination of unknown size. The paragraph before it
    is drawn from the same chapters under the same rule and is not where a note goes, so the gap
    between the two is a bound on how much of the final-paragraph reading is the note. On the
    own-generated books there are no notes and the two should differ only as prose does.
    """
    found = paragraphs(text)
    final = found[-1] if found else ""
    penultimate = found[-2] if len(found) > 1 else ""
    tail = last_line(text)
    return {
        "paragraphs": len(found),
        "final_words": len(final.split()),
        "final_dialogue": is_dialogue(final),
        "final_question": ends_on_question(final),
        "last_line_is_system": is_system_line(tail),
        "penultimate_words": len(penultimate.split()),
        "penultimate_dialogue": is_dialogue(penultimate),
        "penultimate_question": ends_on_question(penultimate),
    }


def summarise(rows: list[dict[str, object]]) -> dict[str, object]:
    """Rates and a word-count distribution. Empty in, `{"n": 0}` out — never a zero that reads
    like a measurement."""
    if not rows:
        return {"n": 0}
    words = sorted(int(row["final_words"]) for row in rows)
    penult = sorted(int(row["penultimate_words"]) for row in rows)

    def rate(key: str) -> float:
        return round(100.0 * sum(1 for row in rows if row[key]) / len(rows), 2)

    return {
        "n": len(rows),
        "final_words": {
            "min": words[0],
            "median": statistics.median(words),
            "mean": round(statistics.fmean(words), 2),
            "max": words[-1],
        },
        "penultimate_words_median": statistics.median(penult),
        "pct_final_dialogue": rate("final_dialogue"),
        "pct_final_question": rate("final_question"),
        "pct_last_line_is_system": rate("last_line_is_system"),
        "pct_penultimate_dialogue": rate("penultimate_dialogue"),
        "pct_penultimate_question": rate("penultimate_question"),
    }


# -- substrate (a): this system's own prose ----------------------------------------------


def published_chapters() -> list[tuple[str, str]]:
    """The assembled chapters as a reader receives them. **Chapter grain, and the only one.**

    `book-library/` is the only place in this repository where an assembled chapter exists, and
    the whole census is about chapter endings — so this is the primary substrate even though it
    is two units, and the scene-grain sources below are the wider, weaker colour. Preferring the
    folder over the store is `opening_counters`' decision for its reason: assembling here would
    be a second implementation of `library.chapters_for` that could drift.
    """
    shelf = REPO / "book-library"
    return [
        (f"{path.parent.parent.name}/{path.stem}", path.read_text(encoding="utf-8"))
        for path in sorted(shelf.glob("*/chapters/*.txt"))
    ]


def _databases() -> list[Path]:
    """Every own-generated book database on this machine, in a fixed order."""
    found = [
        REPO / "serial.db",
        REPO / "exports" / "book-snapshots.db",
        HERE / "corpora" / "toll.db",
    ]
    found += sorted((HERE / "corpora" / "fitness").glob("fitness-*.db"))
    # Existence-filtered rather than assumed: every one of these is gitignored or untracked and
    # lives in the primary checkout only, so a linked worktree finds none of them. `run_local`
    # records which were read, because a loader that silently found nothing would report a
    # census of zero as a measurement (`comic_beats.py`'s stated reason for its own flags).
    return [path for path in found if path.exists()]


def generated_units(min_words: int) -> list[tuple[str, str, str]]:
    """(work, unit_id, text) for every drafted scene in every own-generated database.

    Through `corpus_io.generated_scenes`, which reads the export path rather than the tables, so
    what is measured is what `litharness export` would show a reader. Branches are enumerated
    rather than defaulted: `export.resolve_branch` refuses a store holding more than one book,
    and `fitness-00.db` holds two.
    """
    import corpus_io

    from litharness.adapters.sqlite_store import SqliteStore

    out: list[tuple[str, str, str]] = []
    for path in _databases():
        store = SqliteStore.open(str(path))
        try:
            branches = [(book, branch) for book, branch, _ in store.branches()]
        finally:
            store.close()
        for book_id, branch_id in branches:
            units = corpus_io.generated_scenes(
                path, book=book_id, branch=branch_id, min_words=min_words
            )
            for unit in units:
                title = str(unit.meta.get("book_title") or book_id[:8])
                out.append((f"{path.stem}:{title}", unit.unit_id, unit.text))
    return out


def run_local(min_words: int) -> dict[str, object]:
    chapters = published_chapters()
    scenes = generated_units(min_words)
    per_chapter = {name: describe(text) for name, text in chapters}
    per_scene = [
        {"work": work, "unit_id": unit_id, **describe(text)} for work, unit_id, text in scenes
    ]
    works = sorted({row["work"] for row in per_scene})
    return {
        "min_words": min_words,
        "databases_read": [path.name for path in _databases()],
        "published_chapters": {
            "grain": "chapter",
            "source": "book-library/*/chapters/*.txt",
            "per_unit": per_chapter,
            "summary": summarise(list(per_chapter.values())),
        },
        "generated_scenes": {
            "grain": "scene",
            "source": "corpus_io.generated_scenes over "
            + ", ".join(path.name for path in _databases()),
            "works": len(works),
            "summary": summarise(per_scene),
            "per_unit": per_scene,
        },
    }


# -- substrate (b): the cached RoyalRoad cohort ------------------------------------------


def _rows(units: Iterable[object]) -> list[dict[str, object]]:
    out = []
    for unit in units:
        row = describe(unit.text)  # type: ignore[attr-defined]
        row["cohort"] = unit.meta["cohort"]  # type: ignore[attr-defined]
        row["work_id"] = unit.work_id  # type: ignore[attr-defined]
        out.append(row)
    return out


def run_royalroad(limit: int) -> dict[str, object]:
    """The genre baseline, with its era cohorts computed in the same pass.

    BRIEF.md §2's headline is `tricolon_rate` separating declared-AI prose from pre-2023 at
    0.629 while its *undeclared* 2025 control separated at 0.606 — the metric detected the year.
    So a RoyalRoad rate reported here without its cohort split is not a result in this
    repository, and the split is free: `corpus_io.era_cohort` labels every unit already.

    **Drawn per shard, and the first pass was drawn wrong.** `royalroad_chapters` streams shard
    3 then shard 30 and stops at a single global `limit`, so a limit smaller than shard 3's
    LitRPG population returns **no pre-2023 chapters at all** — the run that produced the first
    numbers here reported two 2025 cohorts and silently no control era, which is the one cohort
    BRIEF.md §2 exists to insist on. Half the budget per shard is the fix, and it is stated
    rather than quietly corrected because the failure looks identical to a corpus that has no
    old chapters in it.
    """
    import corpus_io

    units = [
        unit
        for shard in sorted(corpus_io.SHARDS)
        for unit in corpus_io.royalroad_chapters(
            shards=(shard,), limit=max(1, limit // len(corpus_io.SHARDS))
        )
    ]
    rows = _rows(units)
    cohorts = {
        name: summarise([row for row in rows if row["cohort"] == name])
        for name in sorted({str(row["cohort"]) for row in rows})
    }
    # Within-story, because every confound this directory has killed was a between-story one.
    stories = corpus_io.by_story(units)
    per_story = {
        work_id: summarise(_rows(chapters)) for work_id, chapters in stories.items()
    }
    story_rates = [
        float(entry["pct_final_question"])
        for entry in per_story.values()
        if entry.get("n")
    ]
    return {
        "limit": limit,
        "genre_tag": corpus_io.GENRE_TAG,
        "shards": sorted(corpus_io.SHARDS),
        "snapshot": corpus_io.SNAPSHOT_REVISION,
        "overall": summarise(rows),
        "by_cohort": cohorts,
        "stories": {
            "n": len(per_story),
            "min_chapters": 5,
            "pct_final_question": {
                "mean_of_story_means": (
                    round(statistics.fmean(story_rates), 3) if story_rates else None
                ),
                "stories_with_any": sum(1 for rate in story_rates if rate > 0),
            },
        },
    }


def run_report() -> dict[str, object]:
    local = json.loads(LOCAL_JSON.read_text(encoding="utf-8"))
    try:
        royalroad: dict[str, object] = json.loads(ROYALROAD_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        royalroad = {
            "status": "NOT RUN",
            "reason": "no chapter-endings-royalroad.json beside this script; run "
            "`--substrate royalroad` under the MirrorBench interpreter",
        }
    return {
        "published_chapters": local["published_chapters"]["summary"],
        "generated_scenes": local["generated_scenes"]["summary"],
        "generated_works": local["generated_scenes"]["works"],
        "royalroad": royalroad.get("overall", royalroad),
        "royalroad_by_cohort": royalroad.get("by_cohort"),
        "royalroad_stories": royalroad.get("stories"),
    }


def selftest() -> None:
    """The locator's own cases, run on every invocation because it has no test module.

    `tests/` may not import from `research/`, so the cheapest place a locator's behaviour can be
    pinned is beside it — and an unpinned locator that silently returns the status line is a
    census of the wrong thing that looks exactly like a census of the right one.
    """
    status = "He put the ledger down.\n\n[STATUS] Silas \u2014 Loop 2 | Day 1\n"
    assert final_paragraph(status) == "He put the ledger down."
    assert last_line(status) == "[STATUS] Silas \u2014 Loop 2 | Day 1"
    assert is_system_line(last_line(status))
    assert describe(status)["last_line_is_system"] is True

    inline = "First.\n\nHe read it.\n[STATUS] x \u2014 y\nHe read it again.\n"
    assert final_paragraph(inline) == "He read it. He read it again."

    assert final_paragraph("[STATUS] x \u2014 y\n") == ""
    assert describe("[STATUS] x \u2014 y\n")["final_words"] == 0

    assert is_dialogue('"Ferrous."')
    assert is_dialogue('He shrugged. "Ferrous."')
    assert not is_dialogue("He shrugged.")
    assert ends_on_question('"You hear me?"')
    assert ends_on_question("Did he?")
    assert not ends_on_question("He did not ask.")
    assert describe("A.\n\nB.\n\nC.\n")["penultimate_words"] == 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--substrate", choices=("local", "royalroad", "report"), required=True)
    parser.add_argument(
        "--min-words",
        type=int,
        default=200,
        help="drop drafted scenes shorter than this; `corpus_io.generated_scenes`' own default",
    )
    parser.add_argument("--limit", type=int, default=ROYALROAD_TARGET)
    args = parser.parse_args(argv)
    selftest()

    if args.substrate == "local":
        payload = run_local(args.min_words)
        LOCAL_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        printable: dict[str, object] = {
            "published_chapters": payload["published_chapters"]["summary"],  # type: ignore[index]
            "generated_scenes": payload["generated_scenes"]["summary"],  # type: ignore[index]
        }
    elif args.substrate == "royalroad":
        payload = run_royalroad(args.limit)
        ROYALROAD_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        printable = {
            "overall": payload["overall"],
            "by_cohort": payload["by_cohort"],
            "stories": payload["stories"],
        }
    else:
        printable = payload = run_report()

    print(json.dumps(printable, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
