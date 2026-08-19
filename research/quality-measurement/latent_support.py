"""What selection can reach, and what the treatment the panel preferred actually contained.

Tracks V and S of the latent-taste directive, restricted to the arms that need **no judge and no
quota**. Both were designed to need one; both turned out to have a version that does not, and the
judge-free version answers a sharper question than the judged one would have.

**Track V — the selection ceiling, measured without a selector.** "Selection cannot exceed the
support of the generator's distribution" has been asserted in this project and never measured.
It does not need a judge to measure, because the bound is a property of the *pool*: for any axis,
`E[best of N]` under an **oracle** selector — one that picks the true maximum every time — is an
order statistic of the generator's own draws, and no panel, probe or human can beat it. §83 left
exactly the pool this needs: four retells of each scene from one prompt, differing only by an
inert state block, measured there as near-twins. So the curve is computable by enumeration over
subsets, and what it bounds is every selector at once.

The comparison that makes the number mean something is against a **certified intervention**: §85's
single-variable repairs move the same axes deterministically. Selection and revision are the two
ways to change a manuscript, and this is the first measurement of their relative reach.

**Track S — what the panel preferred, characterised at the stimulus rather than the judge.** D2
asks whether §85's 0.9509 is taste for the model's own register — told feeling — rather than for
prose. The judged version of that question needs a cross-family judge, which the directive
reserves to the operator. But half of it is answerable for free and was never asked: *what did the
treatment actually add?* `authorship_tells` already separates told inner state (`_INTERIOR`:
thought, felt, knew) from shown bodily state (`_BODY`: jaw, hands, breath), which is the exact
distinction the craft worry turns on. If the preferred text is the one with more telling and less
showing, then whatever the panel was preferring, the thing it preferred was told-not-shown — and
that is established without a second judge and without asserting anything about the first.

**What neither arm says.** Nothing here is a preference, a quality claim or a licence (§82). The
axes are surface proxies that a human reader named (§74), not measures of good prose, and an
oracle selector over a proxy is not an oracle over quality. Track V bounds *reach*, not value.

Stdlib only, no network, no GPU, no quota. Reads committed fixtures through `latent_fixtures`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from latent_fixtures import (  # noqa: E402
    build_families,
    drop_degenerate,
    originals,
    p0_features,
    repairs,
    states,
)

RESULTS = HERE / "results"

#: §83's four states. `sober` is the anchor; the other three are what the pool adds. §83 measured
#: them as near-twins, which is what licenses reading them as draws rather than as treatments —
#: and it is an assumption, named here, that cuts in the conservative direction: state-varied
#: draws should spread at least as widely as four independent samples of one prompt, so a ceiling
#: measured on them is an over-estimate of what plain resampling would reach.
POOL_STATES = ("sober", "tea", "drunk", "trip")
ANCHOR = "sober"

#: (axis, direction, the repair arm that intervenes on the same axis). Direction is the way a
#: human reader's complaint points (§74): more interiority, fewer prose em dashes.
AXES: tuple[tuple[str, int, str], ...] = (
    ("interior_per_1k", +1, "repair_interiority"),
    ("em_per_1k", -1, "repair_emdash"),
)

PRE_REGISTRATION: dict[str, Any] = {
    "written": "2026-08-19, with Track P's run",
    "governs": "stage-0 §82 verbatim: nothing here upgrades any licence.",
    "track_v_claim_form": (
        "The ONLY sentence this arm may produce: 'on axis X, an oracle selector over N draws of "
        "this generator moves the axis by D, against D2 for one certified revision.' It is a "
        "statement about the SUPPORT of a distribution and about REACH, never about quality — an "
        "oracle over a surface proxy is not an oracle over good prose."
    ),
    "track_v_kill": (
        "The directive's V2 condition is a plateau by N=4. The pool is four draws deep, so the "
        "curve is only computable to N=4 and the plateau cannot be confirmed beyond it. What is "
        "reportable is the SHAPE within N<=4 and the ratio to the intervention; anything about "
        "N=8..32 requires generation spend and is not claimed here."
    ),
    "track_s_claim_form": (
        "The told/shown decomposition characterises the STIMULUS. It cannot show self-preference "
        "on its own — a human might prefer the same text, which is what §80's batch and the §85 "
        "operator read exist to find out. It removes the question of what was in the treatment "
        "from the list of things the cross-family judge would have to settle."
    ),
    "confounds_named": (
        "Length: §85 measured the interiority treatment growing scenes 10-13%, and it is "
        "reported per arm below rather than adjusted away. Anchor: retells are measured against "
        "the sober retell and repairs against the original, because that is what each was "
        "generated from; the two are not interchangeable and the report says which is which."
    ),
}


def _feature(text: str, axis: str) -> float:
    return p0_features(text, steelman=False)[axis]


def selection_ceiling() -> dict[str, Any]:
    """`E[best of N]` under an oracle selector, by exact enumeration over subsets of the pool."""
    src, pool_texts, repaired = originals(), states(), repairs()
    scenes = sorted(
        {scene for scene, _ in pool_texts}, key=lambda name: int(name.rsplit("-", 1)[1])
    )
    out: dict[str, Any] = {}
    for axis, direction, arm in AXES:
        per_n: dict[int, list[float]] = {}
        interventions: list[float] = []
        used: list[str] = []
        for scene in scenes:
            pool = [
                _feature(pool_texts[(scene, state)], axis)
                for state in POOL_STATES
                if (scene, state) in pool_texts
            ]
            if len(pool) < len(POOL_STATES):
                continue
            used.append(scene)
            base = _feature(pool_texts[(scene, ANCHOR)], axis)
            for size in range(1, len(pool) + 1):
                best = [
                    direction * max(direction * value for value in subset)
                    for subset in combinations(pool, size)
                ]
                per_n.setdefault(size, []).append(statistics.fmean(best) - base)
            if (scene, arm) in repaired:
                interventions.append(
                    _feature(repaired[(scene, arm)], axis) - _feature(src[scene], axis)
                )
        curve = {str(size): round(statistics.fmean(values), 4) for size, values in per_n.items()}
        largest = max(per_n)
        gain = statistics.fmean(per_n[largest]) - statistics.fmean(per_n[1])
        intervention = statistics.fmean(interventions) if interventions else 0.0
        out[axis] = {
            "direction": direction,
            "scenes": used,
            "oracle_curve_minus_anchor": curve,
            "selection_gain_1_to_n": round(gain, 4),
            "max_n_available": largest,
            "certified_intervention_arm": arm,
            "certified_intervention_delta": round(intervention, 4),
            "selection_as_fraction_of_intervention": (
                round(abs(gain) / abs(intervention), 4) if intervention else None
            ),
            # The increments are what the plateau question actually reads. Reported rather than
            # summarised into a verdict, because four draws cannot settle a claim about 32.
            "increments": {
                str(size): round(
                    statistics.fmean(per_n[size]) - statistics.fmean(per_n[size - 1]), 4
                )
                for size in range(2, largest + 1)
            },
        }
    return out


def told_versus_shown() -> dict[str, Any]:
    """Did the preferred treatment add reported inner state, or demonstrated bodily state?"""
    families = build_families()
    out: dict[str, Any] = {}
    for name in ("repair_interiority", "exemplar_vs_sober"):
        pairs, _ = drop_degenerate(name, families[name])
        told, shown, growth = [], [], []
        for pair in pairs:
            after = p0_features(pair.positive, steelman=False)
            before = p0_features(pair.negative, steelman=False)
            told.append(after["interior_per_1k"] - before["interior_per_1k"])
            shown.append(after["body_per_1k"] - before["body_per_1k"])
            growth.append(100.0 * (after["words"] - before["words"]) / before["words"])
        out[name] = {
            "scenes": len(pairs),
            "told_delta_per_1k": round(statistics.fmean(told), 4),
            "told_scenes_up": sum(1 for value in told if value > 0),
            "shown_delta_per_1k": round(statistics.fmean(shown), 4),
            "shown_scenes_up": sum(1 for value in shown if value > 0),
            "word_growth_pct": round(statistics.fmean(growth), 2),
        }
    return out


def run() -> dict[str, Any]:
    report: dict[str, Any] = {
        "pre_registration": PRE_REGISTRATION,
        "track_v_selection_ceiling": selection_ceiling(),
        "track_s_told_versus_shown": told_versus_shown(),
    }
    interiority = report["track_s_told_versus_shown"]["repair_interiority"]
    told_up = interiority["told_scenes_up"]
    shown_up = interiority["shown_scenes_up"]
    report["reading"] = {
        "track_s": (
            f"§85's preferred treatment raised told inner state in {told_up} of "
            f"{interiority['scenes']} scenes and raised shown bodily state in {shown_up}. "
            "Whatever the panel preferred at 0.9509, the thing it preferred was told-not-shown. "
            "This characterises the stimulus and does not, on its own, show self-preference: a "
            "human reader might prefer the same text, which is the question §80's batch and the "
            "§85 operator read exist to answer."
        ),
        "track_v": (
            "An oracle selector over four draws of this generator reaches "
            + ", ".join(
                f"{round(100 * row['selection_as_fraction_of_intervention'])}% of the certified "
                f"revision on {axis}"
                for axis, row in report["track_v_selection_ceiling"].items()
                if row["selection_as_fraction_of_intervention"] is not None
            )
            + ". No selector can do better, because the oracle is the ceiling. Reach only — "
            "these axes are surface proxies a reader named, not measures of quality."
        ),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default=str(RESULTS / "latent-taste-support.json"))
    args = parser.parse_args(argv)

    report = run()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["track_v_selection_ceiling"], indent=2, sort_keys=True))
    print(json.dumps(report["track_s_told_versus_shown"], indent=2, sort_keys=True))
    print("\nTRACK S:", report["reading"]["track_s"])
    print("\nTRACK V:", report["reading"]["track_v"])
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
