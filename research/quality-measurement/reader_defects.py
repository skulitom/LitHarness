"""Can the panel see the two reader-named defects that no ablation had ever manufactured?

§74's human read named three defects in `The Toll Road` and the finding that reframed the
programme was structural: all three sit in **both** copies of every ablation pair, so a battery
that validates a panel on telling a spoiled copy from an original cannot see them however well it
scores. `ablate.READER_DEFECT_SET` closed the manufacturing gap on paper. Until now nothing ran it
— `interiority_strip` and `stat_flatten` were referenced by `ablate.py` and by §74 and by nothing
else. This module runs them.

    interiority_vs_matched    the primary arm. interiority_strip against a control that removes
                              the same word count from sentences reporting no inner state, so the
                              only difference between the two texts is *which* sentences went
    interiority_vs_original   the same arm against the untouched scene. Reported, and declared
                              confounded: interiority_strip routes through `_rebuild`, which
                              downgrades the paragraph separator (§78.1), so this pair differs by
                              formatting as well as by interiority
    stat_flatten_vs_original  the stat arm. `stat_flatten` preserves layout exactly, so its
                              comparison against the original is clean

No layout sham runs: `SHAM_NOT_RUN` records why, and the primary arm is built so that it needs
none.

**The primary arm is a two-variant comparison and that is the whole design.** §78 is the reason:
the em-dash result died because the variant differed from the original by layout before it differed
by punctuation, and every guard in place was a length guard that could not see it. The defence is
not a better guard, it is a comparison where the confounds are *identical on both sides*.
`interiority_strip` and `interiority_deplete_matched` both pass through `_rebuild`, so both carry
the same separator downgrade; both remove the same word count (446 against 447 over the ten
scenes); both are seeded-random in their selection so neither becomes "delete the opening". What
remains is sentences reporting a mind against sentences reporting a body, which is the only claim
the arm makes.

**§74's stated control was the wrong one and §78.1 records it.** That entry called
`deplete_matched` the interiority arm's matched control "exactly as `destake` has".
`deplete_matched` takes its budget from `_stake_plan`, so it is matched to `destake`: it removes
748 words where `interiority_strip` removes 446, and a control deleting 1.68x the text is the
length confound it exists to remove. `interiority_deplete_matched` is the control that matches.

**`stat_flatten` was predicted to be a near-null and it is not.** §74 expected "nothing left to
flatten" because the book's stat lines are already `Level 2 | HP x/22 | MP ?/? | Gold ?` with nine
of twelve slots carrying no information. Measured: the arm blanks **30 values across the ten
scenes**, three per scene — `Level`, `HP` and `MP` — which is precisely the three informative slots
that were left. So the arm does manufacture the defect, by finishing it: it takes the stat block
from three live values to none. The prediction of a null was wrong in the useful direction, and the
arm is a real test rather than a formality.

**Neither outcome is failure, and the acceptance criterion is per arm.** A panel that detects the
defect has given us an axis a reader model could be optimised on. A panel that cannot see it, or
prefers it, has given us a mapped hole — a defect one human found in one read that no instrument in
this repository can detect, which is worth more than a confirmation because it bounds what the
machine panel may ever be trusted to select on. §74's em-dash arm was read the same two-sided way,
and that is the only reason its withdrawal in §78 was legible instead of invisible.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import (  # noqa: E402
    interiority_deplete_matched,
    interiority_strip,
    stat_flatten,
)
from corpus_io import generated_scenes  # noqa: E402
from elicit import PANEL_MODEL, Elicitor, positional_bias  # noqa: E402
from persona_battery import pairwise_interval  # noqa: E402


#: `(key, left, right, reading)`. `left` and `right` are functions of the scene text; the win rate
#: `compare_pair` reports is P(the panel preferred `right`). `identity` is the untouched scene.
def identity(text: str, strength: float) -> str:
    return text


ARMS: tuple[tuple[str, Any, Any, str], ...] = (
    ("interiority_vs_matched", interiority_deplete_matched, interiority_strip,
     "below 0.5 — the panel prefers the text that kept its interiority. PRIMARY: word-matched "
     "and formatting-matched, so only the choice of deleted sentences differs"),
    ("interiority_vs_original", identity, interiority_strip,
     "below 0.5 — but confounded by the §78.1 separator downgrade; read only beside the primary"),
    ("stat_flatten_vs_original", identity, stat_flatten,
     "below 0.5 — the panel prefers live stat values. Layout-preserving, so this one is clean"),
)

#: **`rewhitespace` is deliberately not an arm here, and not paying for it is the point.** §78
#: measured why it cannot serve as this design's floor: it perturbs layout without destroying it, so
#: it is the weaker edit in the dimension that turned out to matter. Its number is already recorded
#: twice — 0.4375 on Haiku and 0.4813 on Opus, both void on positional bias (§74, Addendum 1) — and
#: re-eliciting 80 comparisons to reproduce a figure the ledger already calls unusable is spend
#: without information. What replaces it is structural: the primary arm's two sides carry identical
#: formatting, so there is no layout difference left for a floor to bound.
SHAM_NOT_RUN = "rewhitespace: see §74 Addendum 1 and §78; already measured, declared not a floor"

#: Pre-registered before the first call, per arm, with every branch named so that none can be
#: reported afterwards as the one that was expected.
PRE_REGISTRATION: dict[str, str] = {
    "precondition": (
        "per-arm positional bias within 0.40-0.60. Pooling was wrong in §74 and the per-arm rule "
        "is pre-registered here rather than adopted mid-run"
    ),
    "primary": (
        "interiority_vs_matched is the arm that decides the interiority question. "
        "interiority_vs_original is confounded by formatting and cannot license a reading on its "
        "own; if the two disagree, the difference between them is the size of the §78.1 confound "
        "and is itself the finding"
    ),
    "detects": (
        "win rate <= 0.40: the panel prefers the text retaining the feature, so it detects the "
        "defect. This is an axis a reader model could be optimised on in the human's direction"
    ),
    "blind": (
        "0.40 < win rate < 0.60: the panel cannot see the defect. A mapped hole — a human found "
        "it in one read and no instrument here detects it, so nothing may be selected on this axis"
    ),
    "prefers": (
        "win rate >= 0.60: the panel prefers the defect. A mapped hole of the worse kind and a "
        "hard prohibition: a reader model in the loop would select FOR it, which is what §74 "
        "believed it had shown about the em dash before §78 withdrew the number"
    ),
    "no_sham_floor": (
        "no layout sham is run. §78 measured why rewhitespace cannot be this design's floor, and "
        "the primary arm needs none: its two sides carry identical formatting by construction, so "
        "there is no layout difference for a floor to bound. See SHAM_NOT_RUN"
    ),
}


def verdict(rates: dict[str, float], per_arm_bias: dict[str, dict[str, Any]]) -> dict[str, object]:
    """The pre-registered branches, read per arm, precondition first."""
    def band(arm: str) -> bool:
        value = per_arm_bias.get(arm, {}).get("chose_A_rate")
        return isinstance(value, float) and 0.40 <= value <= 0.60

    per_arm: dict[str, str] = {}
    for key, _left, _right, _reading in ARMS:
        if key not in rates:
            per_arm[key] = "ABSENT"
        elif not band(key):
            per_arm[key] = "VOID"
        elif rates[key] <= 0.40:
            per_arm[key] = "DETECTS"
        elif rates[key] >= 0.60:
            per_arm[key] = "PREFERS"
        else:
            per_arm[key] = "BLIND"

    interiority = per_arm.get("interiority_vs_matched", "ABSENT")
    stats = per_arm.get("stat_flatten_vs_original", "ABSENT")
    confound = None
    if {per_arm.get("interiority_vs_matched"), per_arm.get("interiority_vs_original")} == {
        "DETECTS", "BLIND"
    }:
        confound = (
            "the formatting-matched and formatting-confounded interiority arms disagree, which "
            "sizes the §78.1 separator downgrade directly: the confounded arm is reading layout"
        )
    return {
        "per_arm": per_arm,
        "interiority": interiority,
        "stats": stats,
        "mapped_holes": [
            name for name, outcome in (("interiority", interiority), ("stat_flatten", stats))
            if outcome in {"BLIND", "PREFERS"}
        ],
        "optimisable_axes": [
            name for name, outcome in (("interiority", interiority), ("stat_flatten", stats))
            if outcome == "DETECTS"
        ],
        "confound_note": confound,
        "conditions": PRE_REGISTRATION,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    units = generated_scenes(args.book_db, book=args.book, min_words=args.min_words)
    units = units[: args.scenes]
    if len(units) < 2:
        raise SystemExit(f"need at least 2 scenes, got {len(units)}")

    planned = len(units) * len(ARMS) * 4 * 2
    if planned > args.guard and not args.yes:
        raise SystemExit(f"{planned} calls exceeds the {args.guard} guard; pass --yes")

    report: dict[str, Any] = {
        "book_db": str(args.book_db),
        "scenes": [unit.unit_id for unit in units],
        "panel_model": args.model,
        "transport": args.transport,
        "tie_policy": args.tie_policy,
        "planned_calls": planned,
        "protocol": "plan/stage-0-decisions.md §79",
        "expectations": {key: reading for key, _l, _r, reading in ARMS},
    }

    # What each transform did, reported beside the preference so that "the panel saw the
    # interiority go" and "the panel saw text go" stay separable — §78's lesson is that a
    # transform's own report is the only place a silent second edit becomes visible.
    edits: dict[str, dict[str, float]] = {}
    for key, left_fn, right_fn, _reading in ARMS:
        left_words = sum(len(left_fn(u.text, 1.0).split()) for u in units)
        right_words = sum(len(right_fn(u.text, 1.0).split()) for u in units)
        left_paras = sum(left_fn(u.text, 1.0).count("\n\n") for u in units)
        right_paras = sum(right_fn(u.text, 1.0).count("\n\n") for u in units)
        edits[key] = {
            "left_words": left_words,
            "right_words": right_words,
            "word_gap_pct": round(100.0 * (right_words - left_words) / max(left_words, 1), 3),
            "left_paragraph_breaks": left_paras,
            "right_paragraph_breaks": right_paras,
            "layout_matched": left_paras == right_paras,
        }
    report["transform"] = edits

    every: list[Any] = []
    per_arm: dict[str, list[float]] = {key: [] for key, _l, _r, _e in ARMS}
    with Elicitor(
        Path(args.cache), model=args.model, spot_model=None, spot_fraction=0.0,
        transport=args.transport, pair_question=args.pair_question, dry_run=args.dry_run,
    ) as elicitor:
        for unit in units:
            for key, left_fn, right_fn, _reading in ARMS:
                left, right = left_fn(unit.text, 1.0), right_fn(unit.text, 1.0)
                if left.strip() == right.strip():
                    # Identical sides would score 0.5 by construction: a manufactured tie rather
                    # than a measurement. Scene 3 has no interiority verb, so both interiority
                    # arms are legitimately absent there.
                    continue
                comparisons = elicitor.compare_pair(f"{unit.unit_id}|{key}", left, right, n=1)
                every.extend(comparisons)
                values = [
                    0.5 if c.choice == "neither" else float(c.chose_variant)
                    for c in comparisons
                    if not c.refused
                    and not (c.choice == "neither" and args.tie_policy == "drop")
                ]
                if values:
                    per_arm[key].append(statistics.fmean(values))
            print(f"  {unit.unit_id}: {len(every)} comparisons", file=sys.stderr, flush=True)

        rates = {
            key: round(statistics.fmean(values), 4)
            for key, values in per_arm.items() if values
        }
        report["win_rates"] = rates
        report["pairs_per_arm"] = {key: len(values) for key, values in per_arm.items() if values}
        report["positional_bias"] = positional_bias(every)
        report["per_arm_bias"] = {
            key: positional_bias([c for c in every if c.pair_id.endswith(f"|{key}")])
            for key, _l, _r, _e in ARMS
        }
        report["intervals"] = {
            key: pairwise_interval(
                [c for c in every if c.pair_id.endswith(f"|{key}")], args.model, args.tie_policy
            )
            for key in rates
        }
        report["refused"] = sum(1 for c in every if c.refused)
        report["comparisons"] = len(every)
        report["ladder"] = verdict(rates, report["per_arm_bias"])
        report["spend"] = elicitor.spend()
        report["api_calls"] = elicitor.api_calls
        report["replayed"] = elicitor.replayed
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--book")
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=10)
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument(
        "--pair-question", default="preference", choices=("preference", "intensity")
    )
    parser.add_argument("--tie-policy", default="half_win", choices=("half_win", "drop"))
    parser.add_argument("--guard", type=int, default=340)
    parser.add_argument("--cache", default=str(HERE / "results" / "reader-defects-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "reader-defects.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["win_rates"], indent=2))
    print(json.dumps({k: v.get("chose_A_rate") for k, v in report["per_arm_bias"].items()},
                     indent=2))
    print(json.dumps({k: v for k, v in report["ladder"].items() if k != "conditions"}, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
