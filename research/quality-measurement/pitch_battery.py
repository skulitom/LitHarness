"""Can a simulated reader tell a damaged *pitch* from the pitch it was damaged from?

**Why a pitch and not prose.** Every reader measurement this project has run scores ~1,000 words
of drafted scene, which costs a book to produce — roughly $6 and half an hour before anything can
be read. A forged world's premise is ~120 words and exists the moment the forge returns, so this
is the earliest and cheapest place in the pipeline a reader can be put. On 2026-08-23 the operator
refused six forged worlds in a row on the strength of their premises alone, which is the same
judgment this asks a panel for.

**What it is not.** It is not a picker. §61(5), §105.1 and §107.5 stand: no model ranks or selects
among candidates without the containment the log requires for it, and `plan/world-architect.md` §2
keeps `forge --pick` a person's act. This measures whether the panel can detect damage it did not
choose — a validity question with a mechanical ground truth — and a panel that can do that has
earned nothing more than the right to be read as a diagnostic beside the gate complaints.

**The ladder it inherits.** `persona_battery`'s gate 0 died on the absolute verdict (195 of 196
`keep-reading`, every variance statistic undefined) and its pairwise form cleared gate 1 on prose
(detect 0.9056, sham 0.7833, margin 0.1223). So this is pairwise from the start, position-swapped
by `Elicitor.compare_pair`, and read per sham rather than pooled — BRIEF.md §2 Pass 6's rule,
earned when an inverted sham response inflated a margin by subtraction.

**The damage is `ablate.PITCH_SET` and its ground truth is code.** Three of the four defects the
operator named have a deterministic form (stage-0 §116, §118, §119); the fourth — a premise
written as mood rather than as a pitch — needs a rewriter, so it is absent, and no result here
speaks to it. Two of the three read the world's own declared vocabulary, so the jargon a premise
is damaged with is the jargon that world actually coined.

Pre-registration: `plan/pitch-reader-validity.md`. Run it after that file exists, not before.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
from elicit import Elicitor, positional_bias  # noqa: E402
from personas import GENRE_PANEL  # noqa: E402

#: Above this many planned calls the run refuses without `--yes`. `persona_battery` carries the
#: same guard for the same reason: a schedule is easy to widen by one flag and expensive to widen
#: by one flag.
CALL_GUARD = 400


#: Which arm needs which of the world's own declared vocabularies. `rename_entities` and
#: `respell` are `ablate`'s standing sham pair and take none of it.
EXTRA = {"jargonise": ("terms",), "ladder_first": ("rungs",), "neutral_first": ("places",),
         "rename_pitch": ("names",)}


def humanise(identifier: str) -> str:
    """`rank_black_temper` → `black temper`. The world's own coinage, minus its prefix."""
    body = identifier.split("_", 1)[1] if "_" in identifier else identifier
    return body.replace("_", " ").strip()


def pitches_from(paths: list[Path]) -> list[dict[str, Any]]:
    """Every candidate in every forge bundle, with the vocabulary its damage needs.

    A premise is only usable here if the world also declares what `jargonise` and `ladder_first`
    substitute in — its own terms and its own chain. A world that declares neither is reported
    rather than dropped silently, because an arm that cannot reach a unit is absence and not a
    null (`persona_battery.stake_coverage` records the same distinction for de-stake).
    """
    out = []
    for path in paths:
        forged = json.loads(path.read_text(encoding="utf-8"))
        for candidate in forged["candidates"]:
            world = candidate["world"]
            rungs: list[str] = []
            for system in world.get("systems", []):
                criterion = system.get("criterion") or {}
                if criterion.get("comparator") == "ordinal" and criterion.get("ranks"):
                    rungs = [humanise(str(r.get("id", ""))) for r in criterion["ranks"]]
                    break
            terms = [humanise(str(c.get("id", ""))) for c in world.get("capabilities", [])]
            terms += rungs
            places = [humanise(str(p.get("id", ""))) for p in world.get("places", [])]
            # First names only, taken from the cast's declared ids: a premise writes `theo_grange`
            # as "Theo Grange", and renaming the given name consistently is the surface change a
            # sham wants. Renaming both halves from the same pool would produce two people.
            names = tuple(
                humanise(str(member.get("id", ""))).split(" ")[0].title()
                for member in world.get("cast", [])
                if humanise(str(member.get("id", "")))
            )
            out.append({
                "pitch_id": f"{path.parent.name}:{candidate['index'] + 1}",
                "title": candidate["title"],
                "premise": candidate["premise"],
                "terms": tuple(t for t in terms if t),
                "rungs": tuple(r for r in rungs if r),
                "places": tuple(p for p in places if p),
                "names": names,
            })
    return out


def variants_for(pitch: dict[str, Any]) -> list[tuple[str, str, int]]:
    """`(arm, text, sign)` for one pitch — every arm in `ablate.PITCH_SET` at full dose.

    **One dose, and it is declared rather than discovered.** `ablate.DOSES` exists because a
    metric that fires only on vandalism has shown nothing, and monotonicity across dose is the
    claim a *metric* owes. This is not a metric: it is a panel answering a forced choice, and the
    schedule is already four-way multiplied by persona and orientation. Dose is the first thing
    to add if this clears, and until it does the result reads as detection at full strength only.
    """
    built = []
    for ablation in ablate.PITCH_SET:
        # Only the pitch arms take the world's vocabulary; the shams are `ablate`'s existing
        # two-argument degraders and must be called the way every other battery calls them.
        extra = {key: pitch[key] for key in EXTRA.get(ablation.key, ())}
        text = ablation.apply(pitch["premise"], 1.0, **extra)
        if text.strip() == pitch["premise"].strip():
            continue          # the arm could not reach this pitch; reported as coverage
        built.append((ablation.key, text, ablation.sign))
    return built


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forge", nargs="+", required=True,
                        help="forge.json bundles; every candidate in each becomes a unit")
    parser.add_argument("--n-pitches", type=int, default=6)
    parser.add_argument("--n-samples", type=int, default=1,
                        help="per persona per orientation; both orientations always run")
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--transport", choices=("cli", "sdk", "ollama"), default="cli")
    parser.add_argument("--tie-policy", choices=("half_win", "drop"), default="half_win")
    parser.add_argument("--cache", default="pitch-raw.jsonl")
    parser.add_argument("--out", default="pitch-gate1.json")
    parser.add_argument("--dry-run", action="store_true", help="build the schedule, call nothing")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    pitches = pitches_from([Path(p) for p in args.forge])[: args.n_pitches]
    schedule = [(pitch, variants_for(pitch)) for pitch in pitches]
    planned = sum(len(v) for _, v in schedule) * args.n_samples * 4 * 2   # personas x orientations

    print(f"{len(pitches)} pitch(es), {sum(len(v) for _, v in schedule)} variant(s), "
          f"{planned} planned call(s)", file=sys.stderr)
    for pitch, built in schedule:
        reached = ", ".join(key for key, _, _ in built)
        print(f"  {pitch['pitch_id']:<16} {pitch['title'][:28]:<28} "
              f"{len(pitch['terms']):2d} term(s), "
              f"{len(pitch['rungs'])} rung(s) -> {reached}", file=sys.stderr)
    if planned > CALL_GUARD and not args.yes:
        raise SystemExit(f"refusing {planned} calls above the {CALL_GUARD} guard; pass --yes")
    if args.dry_run:
        return

    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    started = time.time()
    per_arm: dict[str, list[float]] = {}
    reasons: dict[str, dict[str, int]] = {}
    per_cell: list[dict[str, Any]] = []
    comparisons: list[Any] = []

    with Elicitor(
        results_dir / args.cache,
        model=args.model,
        spot_model=None,
        transport=args.transport,
        pair_question="preference",
        dry_run=args.dry_run,
    ) as elicitor:
        for pitch, built in schedule:
            for arm, text, sign in built:
                pair_id = f"{pitch['pitch_id']}|{arm}@1.0"
                # **`GENRE_PANEL`, not `PANEL`.** The operator's readership: enthusiasts of the
                # eleven genres this project writes in, each of whom puts down at least one book
                # the genre loves. `PANEL` stays where §70's recorded numbers can still be
                # reproduced against it.
                batch = elicitor.compare_pair(
                    pair_id, pitch["premise"], text, n=args.n_samples, personas=GENRE_PANEL
                )
                comparisons.extend(batch)
                scored = [c for c in batch if c.model == args.model and not c.refused]
                values = [
                    0.5 if c.choice == "neither" else (1.0 if c.chose_variant else 0.0)
                    for c in scored
                    if not (c.choice == "neither" and args.tie_policy == "drop")
                ]
                rate = sum(values) / len(values) if values else 0.5
                per_arm.setdefault(arm, []).append(rate)
                # **The direction half, and it costs nothing because it was already being
                # collected.** Every `Comparison` carries the reason code the persona gave, from a
                # vocabulary whose whole design is that each code names something a repair could
                # aim at. A rate says the panel noticed; the codes say what it noticed, which is
                # the only part of this a person can act on. It stays on the operator's side of
                # the loop — §97.1 and the `debug-book` rule: nothing diagnosed from a record may
                # feed a prompt.
                for comparison in scored:
                    if comparison.reason_code and comparison.reason_code != "none":
                        reasons.setdefault(arm, {})
                        reasons[arm][comparison.reason_code] = (
                            reasons[arm].get(comparison.reason_code, 0) + 1
                        )
                per_cell.append({
                    "pitch_id": pitch["pitch_id"], "arm": arm, "sign": sign,
                    "variant_win_rate": round(rate, 4), "n_scored": len(scored),
                    "refused": len(batch) - len(scored),
                })
                print(f"  [{len(per_cell):3d}] {pair_id:<34} variant preferred "
                      f"{rate:.3f} ({len(scored)} draws)", file=sys.stderr)
        spend = elicitor.spend()

    # --- the arithmetic, and every rung of it is pre-registered -------------------------------
    #
    # `variant_win_rate` is P(panel prefers the damaged pitch). Damage is declared to LOWER it,
    # so `detect` is stated as the distance below indifference and a degrader that raises it has
    # failed in the direction that matters rather than merely failed.
    summary_arms = {}
    for arm, rates in sorted(per_arm.items()):
        mean = statistics.fmean(rates)
        summary_arms[arm] = {
            "n_pitches": len(rates),
            "variant_win_rate": round(mean, 4),
            "below_indifference": round(0.5 - mean, 4),
            "spread": round(max(rates) - min(rates), 4),
        }
    # **Read off `ablate` rather than typed here, because typing them here is what went wrong.**
    # The first run of this battery renamed the shams to `rename_pitch`/`respell_pitch` and left
    # this set naming the old pair, so `shams` was empty, `worst_sham_effect` came out 0.0, and
    # every margin was reported against nothing — inflated by exactly the amount the shams moved.
    # That is BRIEF.md §2 Pass 6's arithmetic error arriving by a different road, and it was
    # caught by a sham effect of 0.0 being impossible beside two shams that plainly moved.
    # `PITCH_SHAMS` and not `sign == 0`: `neutral_first` is also sign 0 and is a matched
    # control that is *expected* to move the panel. Reading the sham floor off it would
    # subtract a real effect from a real effect.
    shams = [a.key for a in ablate.PITCH_SHAMS if a.key in summary_arms]
    sham_effect = max(
        (abs(summary_arms[k]["variant_win_rate"] - 0.5) for k in shams), default=0.0
    )
    for block in summary_arms.values():
        block["margin_vs_worst_sham"] = round(
            abs(block["variant_win_rate"] - 0.5) - sham_effect, 4
        )

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "panel": [p.persona_id for p in GENRE_PANEL],
        "panel_model": args.model,
        "transport": args.transport,
        "pair_question": "preference",
        "tie_policy": args.tie_policy,
        "n_pitches": len(pitches),
        "pitches": [{k: p[k] for k in ("pitch_id", "title")} for p in pitches],
        "arms": summary_arms,
        # Most-cited first, so the summary reads as "when the panel preferred the original over
        # the jargonised copy, what it said it was reacting to".
        "reasons_by_arm": {
            arm: dict(sorted(counts.items(), key=lambda kv: -kv[1]))
            for arm, counts in sorted(reasons.items())
        },
        "worst_sham_effect": round(sham_effect, 4),
        # The ladder arm is read against its matched control or it is not read at all — the same
        # rule `destake` is read under against `deplete_matched`.
        "ladder_minus_matched": round(
            summary_arms.get("ladder_first", {}).get("variant_win_rate", 0.5)
            - summary_arms.get("neutral_first", {}).get("variant_win_rate", 0.5), 4
        ),
        "positional_bias": positional_bias(comparisons),
        "cells": per_cell,
        "spend": spend,
        "wall_seconds": round(time.time() - started, 1),
    }
    (results_dir / args.out).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in
                      ("arms", "reasons_by_arm", "worst_sham_effect", "ladder_minus_matched",
                       "positional_bias")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
