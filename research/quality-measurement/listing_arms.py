"""Draw listings under variants of the listing prompt and count them against the market.

**The objective is a distribution, not a reader.** `listing_arena.py` measured the readership
against 42 published serials and the readership picked *ours* 15 of 16 — K3 in
`plan/reader-calibration.md`, the inverted reading — so W cannot be optimised toward without
optimising away from what this market rewards. What can be optimised toward is the market's own
measured distribution, which the same 42 listings supply for free and which no model produced.

**Variants are built by surgery on `overview._TASK` rather than by copying it**, so the base
stays one string with one home and an arm is exactly the clause it removes or adds. An arm that
cannot find its clause raises instead of silently running the control — the failure mode that
would make two arms one arm.

    uv run python research/quality-measurement/listing_arms.py --arms base,no_genre,clarity

**Prose out, under `derived/`.** The counters and the digests are what may be committed.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from litharness.application import overview as overview_mod  # noqa: E402
from litharness.domain import house  # noqa: E402
from litharness.domain import writers as writers_mod  # noqa: E402
from litharness.domain.generation import CompletionRequest  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

DERIVED = HERE / "derived"
RESULTS = HERE / "results"

#: The clause measured out of distribution: 4-7 of the genre's own nouns in ours against a
#: market median of 2 (p90 = 6) over 42 published listings. Its own docstring pre-committed to
#: this — *"if the next round comes back at 3.8 by mentioning nouns rather than by being that
#: kind of book, the clause goes"* — and the condition is met in the overshoot direction.
GENRE_CLAUSE = (
    "A reader scanning a list has to see what kind of book this is and what the person is "
    "after: name the magic, the system, the monsters, the dungeon in plain words rather than "
    "implying them, and say what the person is trying to get.\n"
)

#: What replaces it in the `no_genre` arm: the half that says what a reader must be able to see,
#: with the menu of nouns removed. The menu is the part `house`'s standing constraint forbids —
#: a rule may say what fails, it may not enumerate what succeeds.
GENRE_REPLACEMENT = (
    "A reader scanning a list has to see what kind of book this is and what the person is "
    "after.\n"
)

#: The two clauses of `house.CLARITY` the listing prompt lost when the house floor came off and
#: never got back. They are, in order, the operator's two structural complaints of 2026-08-25:
#: *"wtf is a patch of notes"* and *"sentences don't have relations to each other ... spaghetti
#: mess"*.
CLARITY_CLAUSES = (
    "A term the reader has not met needs a reason to be there before it needs anything else, "
    "and then a consequence rather than a definition: the sentence carrying it says what it "
    "does to somebody.\n"
    "A paragraph holds together or it is not a paragraph: a sentence that could be lifted out "
    "and dropped anywhere in the listing has failed.\n"
)


def arm_task(name: str) -> str:
    """The listing task under one arm, by surgery on the shipped constant."""
    task = overview_mod._TASK
    if name == "base":
        return task
    if GENRE_CLAUSE not in task:
        raise SystemExit("the genre clause is not in _TASK any more; the arms need rewriting")
    if name == "no_genre":
        return task.replace(GENRE_CLAUSE, GENRE_REPLACEMENT)
    if name == "clarity":
        # Both factors at once. Kept as a named arm because it ran first, before the 2x2 was
        # laid out properly, and deleting it would delete four drawn listings from the record.
        return task.replace(GENRE_CLAUSE, GENRE_REPLACEMENT + CLARITY_CLAUSES)
    if name == "genre_clarity":
        # The cell the first sweep missed: the genre clause **kept** and the two clarity
        # clauses added. The evidence points here — base sat on the market median for genre
        # nouns (0,2,3,4 against 2) and dropping the clause overshot to zero.
        return task.replace(GENRE_CLAUSE, GENRE_CLAUSE + CLARITY_CLAUSES)
    raise SystemExit(f"no arm named {name!r}")


# ------------------------------------------------------------------------------ the counters

GENRE = re.compile(
    r"\b(magic|magical|monster|monsters|system|reborn|rebirth|hero|heroes|multiverse|skill|"
    r"skills|tutorial|dungeon|guild|guilds|loot|class|classes|level|levels|levelling|leveling|"
    r"quest|quests|mana|spell|spells|mage|cultivation|cultivator|demon|demons|goblin|dragon|"
    r"dragons|apocalypse|summon|summoned|isekai|litrpg|stat|stats|xp)\b",
    re.I,
)
NUM = re.compile(
    r"\b\d+(?:[.,]\d+)?\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|forty|fifty|hundred|thousand)\b",
    re.I,
)
SENT = re.compile(r"(?<=[.!?])\s+")


def panel(text: str) -> dict[str, float]:
    """Every counter, per listing. Only the market's own distribution is ever a target."""
    words = text.split()
    lengths = [len(part.split()) for part in SENT.split(text) if part.strip()] or [0]
    return {
        "words": len(words),
        "sentences": len(lengths),
        "longest": max(lengths),
        "mean_sentence": round(statistics.mean(lengths), 1),
        "genre_nouns": len(GENRE.findall(text)),
        "genre_per_1k": round(1000 * len(GENRE.findall(text)) / max(len(words), 1), 1),
        "num_per_1k": round(1000 * len(NUM.findall(text)) / max(len(words), 1), 1),
    }


def market_band(rivals: list[dict[str, Any]]) -> dict[str, tuple[float, float, float]]:
    """p10, median and p90 per counter over the published pool."""
    rows = [panel(row["listing"]) for row in rivals]
    band: dict[str, tuple[float, float, float]] = {}
    for key in rows[0]:
        values = sorted(float(row[key]) for row in rows)
        band[key] = tuple(  # type: ignore[assignment]
            values[int(p * (len(values) - 1))] for p in (0.10, 0.50, 0.90)
        )
    return band


def outside(got: dict[str, float], band: dict[str, tuple[float, float, float]]) -> list[str]:
    """Counters where a listing sits outside the market's p10-p90. The whole objective."""
    return [
        f"{key}={got[key]} vs {low}-{high}"
        for key, (low, _median, high) in band.items()
        if not low <= got[key] <= high
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", default="base,no_genre,clarity")
    parser.add_argument("--writers", default="halloran,vance,okonjo,ferreira")
    parser.add_argument("--rivals", default=str(DERIVED / "rivals.json"))
    parser.add_argument("--out", type=Path, default=DERIVED / "listing-arms.json")
    parser.add_argument("--report", type=Path, default=RESULTS / "listing-arms.json")
    args = parser.parse_args(argv)

    band = market_band(json.loads(Path(args.rivals).read_text(encoding="utf-8")))
    registry = build_default_registry()
    arms = [name.strip() for name in args.arms.split(",") if name.strip()]
    names = [name.strip() for name in args.writers.split(",") if name.strip()]

    drawn: list[dict[str, Any]] = []
    for arm in arms:
        task = arm_task(arm)
        demands = len(house.demands(task))
        for who in names:
            writer = writers_mod.CAST[who]
            request = CompletionRequest(
                prompt="What this book is to be about:\nAnything you would most want to read.",
                system=f"{writer.render()}\n\n{task}",
                max_output_tokens=overview_mod.MAX_OUTPUT_TOKENS,
                profile=overview_mod.OVERVIEW_PROFILE,
                call_class="generation",
                timeout_seconds=600.0,
            )
            try:
                result, _ = registry.complete(request)
            except Exception as error:  # an outage is a fact about the day, not about the arm
                print(f"  {arm}/{who}: {str(error)[:120]}", file=sys.stderr)
                continue
            listing = result.text.strip()
            got = panel(listing)
            drawn.append(
                {
                    "arm": arm,
                    "writer": who,
                    "task_demands": demands,
                    "listing": listing,
                    "digest": sha256(listing.encode()).hexdigest()[:12],
                    **got,
                    "outside": outside(got, band),
                }
            )
            print(f"  {arm:9} {who:9} {got['words']:4}w  genre {got['genre_nouns']:2}"
                  f"  longest {got['longest']:3}  outside: {drawn[-1]['outside'] or 'nothing'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(drawn, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {
                "market_band": {key: list(value) for key, value in band.items()},
                "arms": [
                    {key: value for key, value in row.items() if key != "listing"}
                    for row in drawn
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n{len(drawn)} listing(s) -> {args.out}")
    print(f"counters (no prose) -> {args.report}")
    for arm in arms:
        rows = [row for row in drawn if row["arm"] == arm]
        if not rows:
            continue
        genre = [row["genre_nouns"] for row in rows]
        clean = sum(1 for row in rows if not row["outside"])
        print(f"  {arm:9} genre nouns {sorted(genre)}  inside the band on every counter: "
              f"{clean}/{len(rows)}  (market median {band['genre_nouns'][1]:.0f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
