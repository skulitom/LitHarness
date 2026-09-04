"""Order recovery across the chapters the operator read: the reassembly instrument, unchanged.

`PREREG.md` beside this file owns the stimuli, the two classes and the reading fixed before
spend; this script buys the cells and writes the numbers. The instrument is
`../reassembly/run.py` imported by path — its system prompt, schema, thirty paragraphs, three
seeds, the repair rule and both scorers — and its SHA-256 is written into the result so a cell
here is provably the same measurement as a cell there. Every measurable is code. Nothing here
tunes a reader.

    uv run python research/quality-measurement/reassembly-reads/run.py --dry-run \
        --library C:/DEV/LitHarness/book-library --runs C:/DEV/LitHarness/runs
    uv run python research/quality-measurement/reassembly-reads/run.py --run --yes \
        --library C:/DEV/LitHarness/book-library --runs C:/DEV/LitHarness/runs

The shelf and the run folders are gitignored build products that live in the primary checkout,
so a linked worktree passes both roots explicitly; a missing chapter refuses the run by name
rather than reporting a census short by one.

**`raw.jsonl` is flushed per record**, because `RUNBOOK.md` tells a later session that a run's
stdout is buffered and its JSONL is therefore the progress bar. This script's handle buffered
too, so for the first arm that promise was false and the file sat at zero bytes through the
first fifteen calls; the fix is to make the promise true rather than to document an exception
to it. `elicit`'s cache has always flushed per record, which is why it is the progress bar the
runbook means.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
QUALITY = HERE.parent
REPO = QUALITY.parents[1]
INSTRUMENT = QUALITY / "reassembly" / "run.py"
PRIOR_RESULTS = QUALITY / "reassembly" / "results.json"

#: Subscription-equivalent cap, read from each result's own cost and stopped at between calls.
CAP_USD = 30.0

#: The registered alpha of the one interval here (`feed_core.CONTROL_ALPHA`'s value, restated
#: rather than imported so this script depends on the instrument alone).
ALPHA = 0.10
RESAMPLES = 2_000

#: The stimuli and their classes, fixed in PREREG.md: (name, root, relative path, class).
STIMULI: tuple[tuple[str, str, str, str], ...] = (
    ("reappraisal", "library", "reappraisal/chapters/Chapter1.txt", "S"),
    ("what-takes", "library", "what-takes/chapters/Chapter1.txt", "S"),
    ("a-good-take", "library", "a-good-take/chapters/Chapter1.txt", "S"),
    ("patch-notes-for-the-apocalypse", "library",
     "patch-notes-for-the-apocalypse/chapters/Chapter1.txt", "S"),
    ("the-rainwright-s-apprentice-has-no-licence", "library",
     "the-rainwright-s-apprentice-has-no-licence/chapters/Chapter1.txt", "S"),
    ("unlicensed-weather", "library", "unlicensed-weather/chapters/Chapter1.txt", "S"),
    ("what-the-kettle-remembers-draw2", "runs",
     "pilots/pilot15/shelf-draw-2/chapters/Chapter1.txt", "S"),
    ("what-the-kettle-remembers", "library",
     "what-the-kettle-remembers/chapters/Chapter1.txt", "S"),
    ("reading-the-ladder-wrong", "library", "reading-the-ladder-wrong/chapters/Chapter1.txt", "S"),
    ("the-station-keeps-score", "library", "the-station-keeps-score/chapters/Chapter1.txt", "S"),
    ("failed-delivery-notice--c7497693", "library",
     "failed-delivery-notice--c7497693/chapters/Chapter1.txt", "S"),
    ("signed-for-by-nobody", "library", "signed-for-by-nobody/chapters/Chapter1.txt", "S"),
    ("the-station-keeps-score--435c41f9", "library",
     "the-station-keeps-score--435c41f9/chapters/Chapter1.txt", "T"),
    ("the-station-keeps-score--fa09c89c", "library",
     "the-station-keeps-score--fa09c89c/chapters/Chapter1.txt", "T"),
    ("the-game-nobody-plays-anymore", "library",
     "the-game-nobody-plays-anymore/chapters/Chapter1.txt", "T"),
    ("nineteen-floors-down", "library", "nineteen-floors-down/chapters/Chapter1.txt", "T"),
    ("the-line-nobody-else-has--0ffc8699", "library",
     "the-line-nobody-else-has--0ffc8699/chapters/Chapter1.txt", "T"),
    ("the-ratchet-counts-down", "library", "the-ratchet-counts-down/chapters/Chapter1.txt", "T"),
    ("ground-held", "library", "ground-held/chapters/Chapter1.txt", "T"),
)

#: Cells already bought under the instrument, reused by pointer and never bought again:
#: our stimulus name -> the key in `../reassembly/results.json`.
REUSED: dict[str, str] = {"the-ratchet-counts-down": "ours-draw1"}


def load_instrument() -> Any:
    """`../reassembly/run.py` as a module, byte for byte, with its digest."""
    spec = importlib.util.spec_from_file_location("reassembly_instrument", INSTRUMENT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the instrument at {INSTRUMENT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def instrument_digest() -> str:
    return hashlib.sha256(INSTRUMENT.read_bytes()).hexdigest()


def stimulus_path(root: str, relative: str, *, library: Path, runs: Path) -> Path:
    base = library if root == "library" else runs
    return base / relative


def class_difference(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """T minus S on per-chapter mean tau, chapters as the unit, stratified percentile bootstrap.

    Seeded from a digest of the values so the same evidence gives the same interval on every
    machine and nobody can re-run hoping for a kinder quantile (`bcr.cluster_interval`'s rule).
    Fewer than two chapters in either class refuses rather than manufacturing a bound.
    """
    s_values = sorted(row["mean_tau"] for row in rows.values() if row["class"] == "S")
    t_values = sorted(row["mean_tau"] for row in rows.values() if row["class"] == "T")
    if len(s_values) < 2 or len(t_values) < 2:
        return {"interval": None, "why": "fewer than two chapters in a class", "s": len(s_values),
                "t": len(t_values)}
    material = json.dumps({"s": s_values, "t": t_values}, sort_keys=True)
    rng = random.Random(int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16))
    point = statistics.fmean(t_values) - statistics.fmean(s_values)
    draws: list[float] = []
    for _ in range(RESAMPLES):
        s_draw = [s_values[rng.randrange(len(s_values))] for _ in s_values]
        t_draw = [t_values[rng.randrange(len(t_values))] for _ in t_values]
        draws.append(statistics.fmean(t_draw) - statistics.fmean(s_draw))
    draws.sort()
    tail = max(1, int(-(-(ALPHA / 2.0) * len(draws) // 1)))
    low, high = draws[tail - 1], draws[len(draws) - tail]
    return {
        "point": point,
        "low": low,
        "high": high,
        "alpha": ALPHA,
        "resamples": RESAMPLES,
        "s": len(s_values),
        "t": len(t_values),
        "above_zero": low > 0.0,
        "below_zero": high < 0.0,
    }


def describe(rows: dict[str, dict[str, Any]], anchors: dict[str, float]) -> dict[str, Any]:
    """The description PREREG.md fixes: classes side by side, the interval, the list-shaped."""
    anchor_low, anchor_high = min(anchors.values()), max(anchors.values())
    classes: dict[str, Any] = {}
    for name in ("S", "T"):
        taus = {key: row["mean_tau"] for key, row in rows.items() if row["class"] == name}
        classes[name] = {
            "chapters": len(taus),
            "mean": statistics.fmean(taus.values()) if taus else None,
            "min": min(taus.values()) if taus else None,
            "max": max(taus.values()) if taus else None,
            "per_chapter": dict(sorted(taus.items(), key=lambda item: item[1])),
        }
    difference = class_difference(rows)
    if difference.get("interval", "present") is None:
        reading = "UNREADABLE"
    elif difference["above_zero"]:
        reading = "RECOVERABILITY_RUNS_WITH_THE_CHAPTER_LEVEL_ITEMS"
    elif difference["below_zero"]:
        reading = "INVERTED"
    else:
        reading = "NO_SEPARATION"
    return {
        "reading": reading,
        "anchors_range": [anchor_low, anchor_high],
        "classes": classes,
        "t_minus_s": difference,
        "below_anchors_range": sorted(
            key for key, row in rows.items() if row["mean_tau"] < anchor_low
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--library", default=str(REPO / "book-library"))
    parser.add_argument("--runs", default=str(REPO / "runs"))
    parser.add_argument("--cap-usd", type=float, default=CAP_USD)
    args = parser.parse_args(argv)
    if args.cap_usd > CAP_USD:
        parser.error(f"--cap-usd {args.cap_usd} is above the registered cap {CAP_USD}")
    instrument = load_instrument()
    library, runs = Path(args.library), Path(args.runs)
    prior = json.loads(PRIOR_RESULTS.read_text(encoding="utf-8"))["summary"]
    anchors = {
        key: float(block["mean_tau"]) for key, block in prior.items() if key.startswith("shelf-")
    }

    texts: dict[str, list[str]] = {}
    missing: list[str] = []
    for name, root, relative, _class in STIMULI:
        if name in REUSED:
            continue
        path = stimulus_path(root, relative, library=library, runs=runs)
        if not path.is_file():
            missing.append(f"{name}: {path}")
            continue
        texts[name] = instrument.paragraphs_of(path.read_text(encoding="utf-8"))
    classes = {name: cls for name, _root, _relative, cls in STIMULI}
    for name, parts in texts.items():
        words = sum(len(part.split()) for part in parts)
        print(f"{name:42s} {classes[name]}  {len(parts):2d} paragraphs, {words:5d} words")
    for name, key in REUSED.items():
        print(f"{name:42s} {classes[name]}  reused from ../reassembly/results.json[{key!r}]")
    print(f"instrument sha256 {instrument_digest()}")
    if missing:
        print("missing stimuli; nothing runs until every chapter is found:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1
    calls = len(texts) * len(instrument.SEEDS)
    print(
        f"{len(texts)} new stimuli x {len(instrument.SEEDS)} seeds = {calls} calls; "
        f"cap ${args.cap_usd:.2f}"
    )
    if not args.run:
        print("dry run; nothing bought")
        return 0
    if not args.yes:
        print("refusing to spend without --yes")
        return 2

    from litharness.providers import ProviderError, build_default_registry

    registry = build_default_registry()
    spent = 0.0
    failures = 0
    stopped = False
    rows: list[dict[str, Any]] = []
    with (HERE / "raw.jsonl").open("a", encoding="utf-8") as sink:
        for name, parts in texts.items():
            labels = [instrument.label(i) for i in range(len(parts))]
            for seed in instrument.SEEDS:
                if spent >= args.cap_usd:
                    stopped = True
                    break
                order = instrument.shuffled(parts, seed)
                shown = [instrument.label(i) for i in order]
                try:
                    result, _ = registry.complete(instrument.render(parts, order))
                except ProviderError as error:
                    failures += 1
                    row = {
                        "stimulus": name, "class": classes[name], "seed": seed,
                        "failed": str(error)[:160], "shown": shown,
                    }
                    sink.write(json.dumps(row) + "\n")
                    sink.flush()
                    rows.append(row)
                    print(f"  {name} seed {seed}: transport failure {str(error)[:80]}")
                    continue
                spent += float(result.cost_usd or 0.0)
                parsed = result.parsed if isinstance(result.parsed, dict) else {}
                raw_answer = [str(x) for x in (parsed.get("order") or [])]
                answer, flagged = instrument.repair(raw_answer, labels, shown)
                row = {
                    "stimulus": name,
                    "class": classes[name],
                    "seed": seed,
                    "tau": round(instrument.kendall_tau(answer, labels), 4),
                    "adjacent": round(instrument.adjacent_kept(answer, labels), 4),
                    "flagged": flagged,
                    "answer": raw_answer,
                    "shown": shown,
                    "cost_usd": result.cost_usd,
                }
                sink.write(json.dumps(row) + "\n")
                sink.flush()
                rows.append(row)
                note = " (repaired)" if flagged else ""
                print(
                    f"  {name} seed {seed}: tau {row['tau']} adjacent {row['adjacent']}{note}"
                    f"  ${spent:.2f}"
                )
            if stopped:
                break

    summary: dict[str, dict[str, Any]] = {}
    for name in texts:
        mine = [row for row in rows if row["stimulus"] == name and "tau" in row]
        if not mine:
            continue
        taus = [float(row["tau"]) for row in mine]
        adjs = [float(row["adjacent"]) for row in mine]
        summary[name] = {
            "class": classes[name],
            "mean_tau": round(statistics.fmean(taus), 4),
            "min_tau": round(min(taus), 4),
            "mean_adjacent": round(statistics.fmean(adjs), 4),
            "seeds_answered": len(mine),
            "paragraphs": len(texts[name]),
        }
    for name, key in REUSED.items():
        block = prior[key]
        summary[name] = {
            "class": classes[name],
            "mean_tau": float(block["mean_tau"]),
            "min_tau": float(block["min_tau"]),
            "mean_adjacent": float(block["mean_adjacent"]),
            "seeds_answered": len(instrument.SEEDS),
            "paragraphs": int(block["paragraphs"]),
            "reused_from": f"../reassembly/results.json[{key!r}]",
        }
    complete = {name: block for name, block in summary.items() if block["seeds_answered"] >= 2}
    result_file = {
        "instrument": str(INSTRUMENT.relative_to(REPO)),
        "instrument_sha256": instrument_digest(),
        "seeds": list(instrument.SEEDS),
        "paragraphs": instrument.PARAGRAPHS,
        "cap_usd": args.cap_usd,
        "spent_usd": round(spent, 4),
        "stopped_at_cap": stopped,
        "transport_failures": failures,
        "stimuli_planned": len(STIMULI),
        "stimuli_with_two_or_more_seeds": len(complete),
        "summary": summary,
        "description": describe(complete, anchors),
        "warnings": (["stopped at the cap: the plan is not covered"] if stopped else [])
        + ([f"{failures} transport failure(s); read before any number"] if failures else []),
    }
    (HERE / "results.json").write_text(
        json.dumps(result_file, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result_file["description"], indent=2))
    print(f"spent ${spent:.2f}; transport failures {failures}; stopped {stopped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
