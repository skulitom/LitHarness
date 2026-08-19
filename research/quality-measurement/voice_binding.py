"""Track V: how deep does the voice lever bind, and does it survive a revision?

Stage-0 §89. §85 measured the demonstrated-voice channel **open** — an exemplar-conditioned retell
moves the register — and §87.1 measured selection reaching only a third to a half of one certified
revision, so revision rather than selection is where the budget belongs. That leaves two questions
about the only working register lever this project has, and the operator funded both:

* **dose** — is the movement a function of how much voice is demonstrated, or does one passage do
  everything a lever can do? Exemplar doses 0, 1, 2, 4, 8 across 8 scenes, nested so that dose 8
  contains dose 4 contains dose 2 contains dose 1.
* **persistence** — a lever that resets on first use is a demo. Each moved scene is revised once
  through §85's certified path; does the voice hold or drift back?

**The control is the whole design, and it is a borrowing control rather than a placebo.** A model
shown eight passages of somebody's prose can move toward them two ways: by picking up the deep
features the register is made of, or by lifting their phrases. Those are different findings and a
centroid distance cannot tell them apart. So every output is measured for n-gram overlap against
**both** the passages it was shown and a held-out pool it was never shown (`rr_mid`, same source,
same frame, never in any dose). Movement is deep-feature movement only if shown-overlap rises no
faster than held-out overlap; if it rises faster, the lever is mimicry and the entry says so.

**What this cannot say.** Nothing about quality. Register movement is not improvement, §82 governs
verbatim, and a scene that has moved toward a human exemplar's feature centroid has moved, not
improved. The reader question stays with §80's batch.

Generation over `claude -p` at `claude-opus-5`, ~$0.23 a generation by §85's measurement — 48
generations, about $11.20. Runs under `uv run python`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from authorship_tells import FEATURE_NAMES, features, strip_system  # noqa: E402
from corpus_io import generated_scenes  # noqa: E402
from repair_generation import (  # noqa: E402
    REVISION_RULES,
    TASKS,
    exemplar_system,
    feature_scale,
    pick_exemplars,
    word_similarity,
    z_distance,
)
from writer_states import SOBER, Generator, retell_turn, writer_system  # noqa: E402

RESULTS = HERE / "results"

#: The nested dose ladder. Nested rather than independently drawn so that a difference between two
#: rungs is *more voice* and not *different voice* — an unnested ladder confounds dose with which
#: passages happened to be picked, which is the confound `ablate.py`'s own ladder exists to avoid.
DOSES: tuple[int, ...] = (0, 1, 2, 4, 8)

#: The pool the exemplars are drawn from, ordered by interiority density (`pick_exemplars`' rule,
#: reused rather than re-derived) — §74's named defect, so if voice demonstration works at all the
#: demonstration should carry the property the register lacks.
SHOWN_POOL = "rr_high"

#: The pool that is **never shown at any dose**. Same corpus, same frame, same excerpt length, so
#: an n-gram overlap against it is the rate at which this generator writes phrases that look like
#: mid-tier RoyalRoad prose without having been shown any. That rate is the null the shown-overlap
#: has to beat before movement can be called mimicry.
HELD_OUT_POOL = "rr_mid"

#: Length of the n-gram whose reuse counts as borrowing. Long enough that shared idiom is rare and
#: short enough to catch a lifted clause; §57 measured this project's longest unintended repeat at
#: seventeen words, so eight is comfortably inside "not a coincidence" without being a whole line.
BORROW_N = 8

#: Windows' `CreateProcess` command-line ceiling. **A transport constraint that caps this arm's
#: ladder, discovered by spending eight generations on it.**
#:
#: `claude -p` passes the system prompt as an argv element, so the whole voice block travels on the
#: command line. Measured on this pool: dose 1 is 5,747 characters, dose 2 is 11,674, dose 4 is
#: 25,478 and **dose 8 is 48,529** — and the scene text rides in a second argv element beside it.
#: Dose 8 therefore cannot be sent from this machine at all, and the first run of this module
#: reported `transport_error:FileNotFoundError` on all eight of its dose-8 calls, which is what
#: `CreateProcess` returns when the line is too long.
#:
#: **A dose that cannot be sent is NOT_RUNNABLE and is not a measurement about the lever** — the
#: same distinction §87.3 drew for `gpt-oss:20b`, where folding a broken load into "ineligible"
#: would have reported a model as answering a question it never saw. So the ladder is checked
#: against this ceiling *before* anything is spent, unreachable rungs are recorded with their
#: measured size, and the persistence arm runs off the highest rung that actually ran.
ARGV_LIMIT = 32767

#: Headroom for the executable path, the flags, and the scene text in the neighbouring argv slot.
#: Deliberately generous: the failure mode is silent on the calling side and costs a generation.
ARGV_HEADROOM = 12000


def dose_fits(system: str) -> bool:
    """Can this dose's voice block travel on a Windows command line beside its scene?"""
    return len(system) + ARGV_HEADROOM <= ARGV_LIMIT


PRE_REGISTRATION: dict[str, Any] = {
    "written": "2026-08-19, before the first generation of this module",
    "arms": {
        "dose": "exemplar doses 0/1/2/4/8 x 8 scenes, nested; 40 generations",
        "persistence": (
            "each top-dose output revised once through repair_interiority; 8 generations. "
            "'Top dose' is the highest rung the transport can carry — see ARGV_LIMIT, which "
            "excluded dose 8 on this machine after the fact."
        ),
    },
    "primary": (
        "centroid distance in the run's own z-space between a generated scene and the centroid of "
        "the SHOWN exemplars. Falling with dose is the lever binding."
    ),
    "the_control_is_the_finding": (
        "Movement is read as deep-feature movement only if n-gram overlap with the shown passages "
        "rises no faster with dose than overlap with a held-out pool the model never saw. If shown "
        "overlap rises faster, the lever is mimicry and the centroid movement is a side effect of "
        "copying. Both curves print whatever they show."
    ),
    "persistence_reading": (
        "The certified revision is single-variable and on a different axis (interiority), so it "
        "should not move the voice centroid at all. If the revised scene's centroid distance "
        "returns toward the dose-0 value, the lever resets on first use and is a demo; if it "
        "holds, the voice survives the pipeline that would follow it."
    ),
    "no_dose_monotonicity_bar": (
        "No threshold is declared on the dose curve, and the reason is §89's own rule about bars "
        "the design cannot reach: with five rungs and eight scenes the exact permutation null on a "
        "monotone trend has a smallest attainable p of 2/5! = 0.0167 per scene, which is "
        "attainable, but the *shape* question ('does it plateau') is not a null-hypothesis "
        "question at all and dressing it as one would manufacture a verdict. The curve is reported "
        "with its increments and the plateau is described rather than tested."
    ),
    "what_it_cannot_say": (
        "Nothing about quality. Register movement is not improvement; §82 governs verbatim and a "
        "scene that moved toward a human exemplar's feature centroid has moved, not improved."
    ),
    "floor": (
        "Dose 0 is the same prompt with no voice block, so the dose-0 scenes are the anchor and "
        "any movement is measured against them. A dose-0 scene that already sits at the exemplar "
        "centroid would mean the z-space has no room and the arm says so rather than reporting a "
        "flat curve as a plateau."
    ),
}


def ngrams(text: str, n: int = BORROW_N) -> set[tuple[str, ...]]:
    """Lowercased word n-grams. Punctuation kept: a lifted clause keeps its commas."""
    words = text.lower().split()
    return {tuple(words[i:i + n]) for i in range(max(len(words) - n + 1, 0))}


def borrow_rate(text: str, pool: list[str], n: int = BORROW_N) -> float:
    """Share of the output's n-grams that also appear anywhere in `pool`.

    Denominated in the *output's* n-grams rather than the pool's, so a longer pool cannot inflate
    the rate by having more chances to match — which is exactly the asymmetry that would make the
    shown pool look more borrowed-from than the held-out one at dose 8.
    """
    mine = ngrams(text, n)
    if not mine:
        return 0.0
    theirs: set[tuple[str, ...]] = set()
    for passage in pool:
        theirs |= ngrams(passage, n)
    return round(len(mine & theirs) / len(mine), 6)


def centroid(rows: list[dict[str, float]]) -> dict[str, float]:
    """Per-feature mean. The exemplars' location in feature space."""
    return {name: statistics.fmean([row[name] for row in rows]) for name in FEATURE_NAMES}


def _rows(texts: list[str]) -> list[dict[str, float]]:
    return [dict(features(strip_system(text))) for text in texts]


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Both arms, sharing one generation cache."""
    units = generated_scenes(args.book_db, book=args.book, min_words=args.min_words)[: args.scenes]
    if len(units) < 2:
        raise SystemExit(f"need at least 2 scenes, got {len(units)}")
    human = json.loads(Path(args.human_json).read_text(encoding="utf-8"))
    shown_pool = human[SHOWN_POOL]
    held_out = human[HELD_OUT_POOL]
    if len(shown_pool) < max(DOSES):
        raise SystemExit(f"{SHOWN_POOL} holds {len(shown_pool)}, need {max(DOSES)}")

    # Nested by construction: `pick_exemplars` returns indices in a fixed order, so dose d is the
    # first d of that order and every rung contains the one below it.
    order = pick_exemplars(shown_pool, count=len(shown_pool))
    ladder = {dose: [shown_pool[i] for i in order[:dose]] for dose in DOSES}

    planned = len(units) * len(DOSES) + len(units)  # upper bound; unrunnable rungs drop out
    if planned > args.guard and not args.yes:
        raise SystemExit(f"{planned} generations exceeds the {args.guard} guard; pass --yes")

    report: dict[str, Any] = {
        "pre_registration": PRE_REGISTRATION,
        "scenes": [unit.unit_id for unit in units],
        "writer_model": args.writer_model,
        "doses": list(DOSES),
        "shown_pool": {"key": SHOWN_POOL, "size": len(shown_pool), "order": order[: max(DOSES)]},
        "held_out_pool": {"key": HELD_OUT_POOL, "size": len(held_out)},
        "planned_generations": planned,
    }

    # The ladder is filtered against the transport *before* anything is spent. A rung that cannot
    # be sent is recorded with the size that made it unsendable, so the entry says NOT_RUNNABLE
    # rather than reporting a rung of zero scenes as if the lever had failed there.
    systems = {dose: (writer_system(SOBER) if dose == 0 else exemplar_system(ladder[dose]))
               for dose in DOSES}
    runnable = [dose for dose in DOSES if dose_fits(systems[dose])]
    report["not_runnable"] = {
        str(dose): {
            "system_prompt_chars": len(systems[dose]),
            "argv_limit": ARGV_LIMIT,
            "why": "the voice block travels as an argv element and this rung exceeds the ceiling",
        }
        for dose in DOSES if dose not in runnable
    }
    report["runnable_doses"] = runnable
    top = max(runnable)
    if top != max(DOSES):
        report["persistence_runs_off"] = {
            "dose": top,
            "instead_of": max(DOSES),
            "why": (
                "the persistence arm revises the most-conditioned output there is, and the "
                "highest rung that ran is the most-conditioned output there is. Substituting the "
                "top *runnable* dose is not a choice about the result — the substitution is "
                "forced by the transport and would be identical whatever the numbers said."
            ),
        }

    outputs: dict[tuple[str, int], str] = {}
    revised: dict[str, str] = {}
    with Generator(Path(args.gen_cache), model=args.writer_model, dry_run=args.dry_run) as gen:
        for unit in units:
            for dose in runnable:
                system = systems[dose]
                record = gen.generate(
                    {"scene": unit.unit_id, "arm": "dose", "dose": dose},
                    system, retell_turn(unit.text),
                    dry_text=f"[dry:dose{dose}] {unit.text}",
                )
                if not record.get("refused"):
                    outputs[(unit.unit_id, dose)] = record["text"]
                print(f"  dose {dose} {unit.unit_id}", file=sys.stderr, flush=True)
        for unit in units:
            moved = outputs.get((unit.unit_id, top))
            if moved is None:
                continue
            record = gen.generate(
                {"scene": unit.unit_id, "arm": "persistence"},
                "You are the author of the scene below, midway through drafting a serialized "
                "LitRPG novel, returning tonight to revise your own pages.",
                REVISION_RULES.format(task=TASKS["repair_interiority"]) + f"\n\n---\n\n{moved}",
                dry_text=f"[dry:persist] {moved}",
            )
            if not record.get("refused"):
                revised[unit.unit_id] = record["text"]
            print(f"  persistence {unit.unit_id}", file=sys.stderr, flush=True)
        report["calls"] = {"api": gen.api_calls, "replayed": gen.replayed}

    every = list(outputs.values()) + list(revised.values()) + shown_pool[: top]
    if len(every) < 2:
        report["status"] = "NOT RUN — no generations survived"
        return report
    scale = feature_scale(_rows(every))
    exemplar_centroid = centroid(_rows(shown_pool[: top]))

    per_dose: dict[str, Any] = {}
    for dose in runnable:
        texts = [outputs[(u.unit_id, dose)] for u in units if (u.unit_id, dose) in outputs]
        if not texts:
            per_dose[str(dose)] = {"scenes": 0}
            continue
        per_dose[str(dose)] = {
            "scenes": len(texts),
            "centroid_distance": round(statistics.fmean(
                z_distance(row, exemplar_centroid, scale) for row in _rows(texts)), 4),
            "borrow_shown": round(statistics.fmean(
                borrow_rate(t, ladder[top]) for t in texts), 6),
            "borrow_held_out": round(statistics.fmean(
                borrow_rate(t, held_out) for t in texts), 6),
            "interior_per_1k": round(statistics.fmean(
                row["interior_per_1k"] for row in _rows(texts)), 3),
        }
    report["dose_arm"] = per_dose

    if revised:
        texts = list(revised.values())
        report["persistence_arm"] = {
            "scenes": len(texts),
            "centroid_distance": round(statistics.fmean(
                z_distance(row, exemplar_centroid, scale) for row in _rows(texts)), 4),
            "similarity_to_moved": round(statistics.fmean(
                word_similarity(outputs[(scene, top)], text)
                for scene, text in revised.items()), 4),
            "borrow_shown": round(statistics.fmean(
                borrow_rate(t, ladder[top]) for t in texts), 6),
        }
    report["reading"] = _reading(report)
    return report


def _reading(report: dict[str, Any]) -> dict[str, str]:
    """The two pre-registered readings, applied. Neither is a threshold."""
    doses = report.get("dose_arm") or {}
    rungs = [(int(d), row) for d, row in doses.items() if row.get("scenes")]
    rungs.sort()
    if len(rungs) < 2:
        return {"dose": "NOT READABLE — fewer than two populated rungs"}
    first, last = rungs[0][1], rungs[-1][1]
    moved = first["centroid_distance"] - last["centroid_distance"]
    shown_rise = last["borrow_shown"] - first["borrow_shown"]
    held_rise = last["borrow_held_out"] - first["borrow_held_out"]
    out = {
        "dose": (
            f"centroid distance {first['centroid_distance']} -> {last['centroid_distance']} "
            f"({moved:+.4f} over doses {rungs[0][0]}..{rungs[-1][0]}); "
            + ("the lever binds" if moved > 0 else "no movement toward the exemplars")
        ),
        "borrowing": (
            f"shown-overlap {shown_rise:+.6f} against held-out {held_rise:+.6f}: "
            + ("movement is not explained by borrowing — shown overlap rose no faster than the "
               "pool the model never saw"
               if shown_rise <= held_rise else
               "shown overlap rose FASTER than held-out; the lever is mimicry to that extent and "
               "the centroid movement cannot be read as deep-feature movement")
        ),
    }
    persistence = report.get("persistence_arm")
    if persistence and rungs:
        out["persistence"] = (
            f"after one certified revision the centroid distance is "
            f"{persistence['centroid_distance']} against {last['centroid_distance']} at dose "
            f"{rungs[-1][0]} and {first['centroid_distance']} at dose {rungs[0][0]}; "
            + ("the voice holds through the revision"
               if persistence["centroid_distance"] <= (
                   last["centroid_distance"] + first["centroid_distance"]) / 2
               else "the voice drifts back toward the unconditioned register — a lever that "
                    "resets on first use is a demo")
        )
    return out


def selftest() -> int:
    """The borrowing measure and the ladder's nesting, before any generation."""
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    check("identical text borrows everything",
          borrow_rate("a b c d e f g h i", ["a b c d e f g h i"]) == 1.0)
    check("disjoint text borrows nothing",
          borrow_rate("a b c d e f g h", ["z y x w v u t s"]) == 0.0)
    check("short text has no n-grams and returns 0", borrow_rate("a b", ["a b"]) == 0.0)
    check("the rate is denominated in the output",
          borrow_rate("a b c d e f g h", ["a b c d e f g h", "q " * 50]) == 1.0)
    ladder = {d: list(range(d)) for d in DOSES}
    for smaller, larger in pairwise(DOSES):
        check(f"dose {smaller} nests inside {larger}",
              set(ladder[smaller]) <= set(ladder[larger]))
    check("the pools are disjoint by name", SHOWN_POOL != HELD_OUT_POOL)
    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"voice_binding selftest: {'PASS' if not failures else str(len(failures)) + ' FAIL'}",
          file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--book", default=None)
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument("--writer-model", default="claude-opus-5")
    parser.add_argument("--human-json", default=str(HERE / "corpora" / "human-excerpts.json"))
    parser.add_argument("--gen-cache", default=str(RESULTS / "voice-binding-raw.jsonl"))
    parser.add_argument("--out", default=str(RESULTS / "voice-binding.json"))
    parser.add_argument("--guard", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if selftest():
        print("refusing to run: selftest failed", file=sys.stderr)
        return 1

    report = run(args)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.get("dose_arm", {}), indent=2))
    for key, line in (report.get("reading") or {}).items():
        print(f"\n{key}: {line}")
    print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
