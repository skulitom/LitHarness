"""Track FX: is literary quality memetic fitness — what survives being retold?

The black swan. Low prior, capped budget, kill fast, included because if it works it reframes the
goal from "what does a reader prefer" to "what does a culture keep". Oral tradition selected for
transmissibility for thousands of years before anyone wrote a review; this measures it directly.

    hop 0   the passage
    hop k   "retell this from memory for a new reader" -> hop k+1's input

R = 4 replicate chains per side, J = 6 hops, **families alternating every hop** so no single
family's artifact compounds down a chain. §94.5 is why: one family read a word-identical
reordering as *deletion* on 22 of 30 cells and another on 3 of 30, and a chain run entirely on
the first would have manufactured a decay curve out of one model's confabulation.

**The adversary is pre-registered, and it says the headline hypothesis is probably false.**
Simplicity wins transmission — the nursery-rhyme effect — so a monotone "better prose survives
more" is the outcome to expect *not* to see. The declared informative read is the
**style-versus-skeleton decomposition**: the black-swan result is high-conversion sides'
distinctive features surviving more hops *while skeletons decay equally*. Both halves print.

**Kill condition, declared before the pilot:** close with the negative recorded, and the pilot's
cost as the last line, if placebo chains diverge, if the sham moves anything, or if every measure
saturates by hop 2. At n = 8 the interval bar demands 8 of 8, so the pilot **cannot clear a bar
and is not asked to** — it is a kill screen, and `force_harness`'s INSUFFICIENT_N rule is what
keeps its arithmetic honest.

Chain outputs are derivative third-party text: local-only, gitignored, audited, never committed.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import force_gpu  # noqa: E402
from authorship_tells import features  # noqa: E402
from force_harness import (  # noqa: E402
    FAMILIES,
    RESULTS,
    Checkpoint,
    ForcePair,
    attainability_table,
    control_verdict,
    digest,
    load_pairs,
    pair_agreement,
    placebo_pairs,
    provenance,
    sham_pairs,
    sham_verdict,
    stratified_subsample,
    unit_key,
    verdict,
)
from register_halflife import (  # noqa: E402
    ACTIVE,
    centroid,
    neutral_pool,
    rows,
    scale_of,
    z_distance,
)

DERIVED = HERE / "derived"

HOPS = 6
CHAINS = 4
PILOT_PAIRS = 8
MAX_NEW_TOKENS = 384

#: Frozen. FX is the only track in this programme that instructs a model, and the instruction is
#: a constant under a test rather than a string a later run may improve: an instruction that
#: drifts between hops or between families makes the decay curve a curve about the prompt.
INSTRUCTION = (
    "Retell this from memory for a new reader who has not seen it. "
    "Write it as prose, not as notes or a summary."
)

#: Skeleton = the original's most frequent content words. A deterministic extractor, committed
#: before the first hop: entity and proposition survival in the only form something with no
#: parser can honestly compute, and stopwords stripped so the measure is about *what happened*
#: rather than about English.
SKELETON_WORDS = 40
# U+2019 is deliberate: RoyalRoad prose uses the curly apostrophe far more often
# than the straight one, and a pattern that misses it splits contractions in two.
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")  # noqa: RUF001
STOPWORDS = frozenset(
    """
a about after all also am an and any are as at be been before being but by can could did do
does down each even for from get got had has have he her here hers him his how i if in into
is it its just like me more most my no not now of off on once one only or other our out over
own said same she should so some such than that the their them then there these they this
those through to too under up very was we were what when where which while who why will with
would you your
    """.split()  # noqa: SIM905
)

PRE_REGISTRATION: dict[str, Any] = {
    "track": "FX transmission chains",
    "hypothesis": "literary quality is memetic fitness — what survives retelling",
    "prior": "low; included because a positive result reframes the goal",
    "adversary_pre_registered": "simplicity wins transmission (the nursery-rhyme effect), so "
                                "the monotone hypothesis is probably false and the "
                                "style-versus-skeleton decomposition is the informative read",
    "black_swan_outcome": "high-conversion sides' distinctive features survive more hops while "
                          "skeletons decay equally",
    "hops": HOPS,
    "chains": CHAINS,
    "pilot_pairs": PILOT_PAIRS,
    "family_alternation": "families alternate every hop so no single family's artifact "
                          "compounds (§94.5)",
    "measures": {
        "skeleton_retention": f"recall of the original's top-{SKELETON_WORDS} content words",
        "style_retention": "z-distance to the original's register against z-distance to the "
                           "model median centroid",
        "mutation_rate": "one minus content-word overlap between consecutive hops",
        "attractor": "between-side chain distance against within-side chain distance; "
                     "convergence to one basin is the interesting negative",
    },
    "kill_conditions": [
        "placebo chains diverge",
        "the sham moves anything",
        "all measures saturate by hop 2",
    ],
    "bar": "none — at n=8 the interval demands 8 of 8; this is a kill screen, not a bar arm",
    "instruction": INSTRUCTION,
}


# ------------------------------------------------------------------------------- extractors


def content_words(text: str) -> list[str]:
    return [w for w in (m.group(0).lower() for m in _WORD.finditer(text)) if w not in STOPWORDS]


def skeleton(text: str, size: int = SKELETON_WORDS) -> set[str]:
    counts = Counter(content_words(text))
    return {word for word, _ in counts.most_common(size)}


def skeleton_retention(original: str, retold: str) -> float:
    bones = skeleton(original)
    if not bones:
        return 0.0
    present = set(content_words(retold))
    return len(bones & present) / len(bones)


def mutation_rate(previous: str, current: str) -> float:
    before, after = set(content_words(previous)), set(content_words(current))
    if not before and not after:
        return 0.0
    return 1.0 - len(before & after) / len(before | after)


def style_retention(
    text: str, origin: dict[str, float], median: dict[str, float], scale: dict[str, float]
) -> float:
    """Distance to the original's register against distance to the model's median.

    Above 0.5 means the text still sits nearer its origin than the model's centre — the voice has
    survived the hop. It is a *ratio* rather than a raw distance so that a retelling getting
    shorter, which changes every rate feature at once, does not read as style loss on its own.
    """
    row = centroid(rows(text)) if rows(text) else features(text)
    to_origin = z_distance(row, origin, scale)
    to_median = z_distance(row, median, scale)
    total = to_origin + to_median
    return 0.5 if total <= 0 else to_median / total


# ------------------------------------------------------------------------------------ chain


def run_chain(
    families: Sequence[str],
    passage: str,
    cache: Checkpoint,
    governor: force_gpu.Governor,
    *,
    hops: int,
    chains: int,
    max_new_tokens: int,
) -> list[list[str]]:
    """`chains` parallel retellings, `hops` deep. Returns hop-major: [hop][chain]."""
    current = [passage] * chains
    history: list[list[str]] = []
    for hop in range(hops):
        family = families[hop % len(families)]
        model_id, revision = force_gpu.resolve(family, "chat")
        key = unit_key(
            "fx", model_id, revision, digest(" ".join(current)), hop, chains,
            max_new_tokens, digest(INSTRUCTION),
        )
        row = cache.get(key)
        if row is None:
            prompts = [force_gpu.chat_prompt(family, INSTRUCTION, text) for text in current]
            produced = force_gpu.sample_batch(
                family, prompts, max_new_tokens=max_new_tokens, head="chat", governor=governor,
                # The chat template already emits the family's BOS; tokenising its output with
                # add_special_tokens=True would prepend a second one.
                add_special_tokens=False,
            )
            row = cache.put(key, {"outputs": produced, "family": family, "hop": hop})
        current = row["outputs"]
        history.append(current)
    return history


def measure_side(
    history: Sequence[Sequence[str]],
    passage: str,
    median: dict[str, float],
    scale: dict[str, float],
) -> dict[str, Any]:
    origin_rows = rows(passage)
    origin = centroid(origin_rows) if origin_rows else features(passage)
    per_hop: list[dict[str, float]] = []
    previous = [passage] * len(history[0])
    for hop_outputs in history:
        per_hop.append({
            "skeleton": statistics.fmean(
                [skeleton_retention(passage, text) for text in hop_outputs]
            ),
            "style": statistics.fmean(
                [style_retention(text, origin, median, scale) for text in hop_outputs]
            ),
            "mutation": statistics.fmean(
                [mutation_rate(a, b)
                 for a, b in zip(previous, hop_outputs, strict=True)]
            ),
        })
        previous = list(hop_outputs)
    return {
        "per_hop": per_hop,
        "skeleton_auc": statistics.fmean([row["skeleton"] for row in per_hop]),
        "style_auc": statistics.fmean([row["style"] for row in per_hop]),
        "mutation_mean": statistics.fmean([row["mutation"] for row in per_hop]),
        "final_skeleton": per_hop[-1]["skeleton"],
        "final_style": per_hop[-1]["style"],
    }


def attractor(
    high_history: Sequence[Sequence[str]],
    low_history: Sequence[Sequence[str]],
    median: dict[str, float],
    scale: dict[str, float],
) -> list[dict[str, float]]:
    """Do chains from opposite sides converge to one basin?

    Between-side distance against within-side distance, per hop. If the ratio falls toward 1 the
    two texts have become the same text as far as this feature space can tell, which is the
    negative result worth having: the model, not the prose, is deciding where a retelling lands.
    """
    out: list[dict[str, float]] = []
    for hop, (highs, lows) in enumerate(zip(high_history, low_history, strict=True)):
        high_rows = [centroid(rows(t)) or features(t) for t in highs]
        low_rows = [centroid(rows(t)) or features(t) for t in lows]
        within = statistics.fmean(
            [z_distance(a, b, scale) for i, a in enumerate(high_rows) for b in high_rows[i + 1 :]]
            + [z_distance(a, b, scale) for i, a in enumerate(low_rows) for b in low_rows[i + 1 :]]
        )
        between = statistics.fmean(
            [z_distance(a, b, scale) for a in high_rows for b in low_rows]
        )
        out.append({
            "hop": hop,
            "within_side": round(within, 4),
            "between_side": round(between, 4),
            "ratio": round(between / within, 4) if within > 0 else float("nan"),
        })
    return out


def saturated(per_hop: Sequence[dict[str, float]]) -> bool:
    """Did every measure stop moving by hop 2? One of the three declared kill conditions."""
    if len(per_hop) < 3:
        return False
    for key in ("skeleton", "style", "mutation"):
        early = abs(per_hop[1][key] - per_hop[0][key])
        late = max(abs(per_hop[i + 1][key] - per_hop[i][key]) for i in range(1, len(per_hop) - 1))
        if late > 0.1 * max(early, 1e-9) and late > 0.01:
            return False
    return True


# ------------------------------------------------------------------------------------- run


def run(args: argparse.Namespace) -> dict[str, Any]:
    pairs = load_pairs()
    by_stratum: dict[str, list[ForcePair]] = {}
    for pair in pairs:
        by_stratum.setdefault(pair.stratum, []).append(pair)
    live = [p for rows_ in by_stratum.values() for p in rows_[: args.pairs // 2]]
    # Stratified, not head-sliced: `load_pairs` returns aligned then crossed, so `live[:n]`
    # would draw both controls entirely from `aligned` and certify nothing about the
    # stratum §79 built to be adversarial.
    placebo = placebo_pairs(stratified_subsample(live, args.placebo))
    sham = sham_pairs(stratified_subsample(live, args.sham))

    governor = force_gpu.Governor(rest_ratio=args.rest_ratio)
    DERIVED.mkdir(parents=True, exist_ok=True)
    cache = Checkpoint(DERIVED / "fx-chains.jsonl")
    families = list(args.families)

    histories: dict[tuple[str, str], list[list[str]]] = {}
    for pair in live + placebo + sham:
        for side, text in pair.sides:
            histories[(pair.pair_id, side)] = run_chain(
                families, text, cache, governor,
                hops=args.hops, chains=args.chains, max_new_tokens=args.tokens,
            )

    # One z-space for the whole run, built from every text it produced plus the neutral pool, so
    # a hop-5 retelling and a hop-0 passage are measured in the same units.
    every: list[dict[str, float]] = []
    for history in histories.values():
        for hop_outputs in history:
            for text in hop_outputs:
                every.extend(rows(text))
    for pair in live + placebo + sham:
        for _, text in pair.sides:
            every.extend(rows(text))
    pool_rows: list[dict[str, float]] = []
    for scene in neutral_pool():
        pool_rows.extend(rows(scene))
    every.extend(pool_rows)
    scale = scale_of(every)
    median = centroid(pool_rows) if pool_rows else centroid(every)

    measured: dict[str, dict[str, Any]] = {}
    for pair in live + placebo + sham:
        measured[pair.pair_id] = {
            side: measure_side(histories[(pair.pair_id, side)], text, median, scale)
            for side, text in pair.sides
        }

    # Placebo: byte-identical sides run byte-identical chains, so every measure differs by
    # exactly zero. This is also the only check in the programme that would catch a chain
    # confabulating a difference out of identical text — §94.5's failure, in chain form.
    placebo_effect = 0.0
    for pair in placebo:
        row = measured[pair.pair_id]
        for key in ("skeleton_auc", "style_auc", "mutation_mean"):
            placebo_effect = max(placebo_effect, abs(row["high"][key] - row["low"][key]))

    skeleton_scores = {
        pid: {side: row[side]["skeleton_auc"] for side in row} for pid, row in measured.items()
    }
    style_scores = {
        pid: {side: row[side]["style_auc"] for side in row} for pid, row in measured.items()
    }

    report: dict[str, Any] = {
        "placebo_identical": control_verdict(
            "placebo_identical", placebo_effect, tolerance=args.placebo_tolerance, kind="exact"
        ),
        "rewhitespace_sham": sham_verdict(
            "rewhitespace_sham", *pair_agreement(style_scores, sham)
        ),
        "governor": governor.report(),
        "cache": cache.provenance(),
    }
    for label, scores in (("skeleton", skeleton_scores), ("style", style_scores)):
        for stratum in ("aligned", "crossed"):
            members = [p for p in live if p.stratum == stratum]
            if members:
                report[f"{label}__{stratum}"] = verdict(
                    f"{label}__{stratum}", *pair_agreement(scores, members)
                )

    pooled_hops = [
        {
            key: statistics.fmean([
                measured[p.pair_id][side]["per_hop"][hop][key]
                for p in live for side in ("high", "low")
            ])
            for key in ("skeleton", "style", "mutation")
        }
        for hop in range(args.hops)
    ]
    attractors = [
        attractor(histories[(p.pair_id, "high")], histories[(p.pair_id, "low")], median, scale)
        for p in live
    ]
    pooled_attractor = [
        {
            "hop": hop,
            "ratio": statistics.fmean([
                run_[hop]["ratio"] for run_ in attractors
                if run_[hop]["ratio"] == run_[hop]["ratio"]
            ]),
        }
        for hop in range(args.hops)
    ]

    kills: list[str] = []
    if report["placebo_identical"]["status"] == "VOID":
        kills.append("placebo chains diverged")
    if report["rewhitespace_sham"]["status"] == "VOID":
        kills.append("the whitespace sham moved a measure")
    if saturated(pooled_hops):
        kills.append("every measure saturated by hop 2")

    decomposition = {
        "skeleton_aligned": report.get("skeleton__aligned", {}).get("agreement"),
        "skeleton_crossed": report.get("skeleton__crossed", {}).get("agreement"),
        "style_aligned": report.get("style__aligned", {}).get("agreement"),
        "style_crossed": report.get("style__crossed", {}).get("agreement"),
        "reading": "the declared informative read: the black-swan outcome is style surviving "
                   "more on the high-conversion side while skeleton decays equally",
    }

    return provenance(
        track="FX",
        pre_registration_track=PRE_REGISTRATION,
        pairs=len(live),
        attainability=attainability_table({"fx_pilot": len(live)}),
        hop_curve=pooled_hops,
        attractor=pooled_attractor,
        style_vs_skeleton=decomposition,
        per_stratum={k: v for k, v in report.items() if "__" in k},
        controls={k: report[k] for k in ("placebo_identical", "rewhitespace_sham")},
        governor=report["governor"],
        cache=report["cache"],
        kill_conditions_fired=kills,
        status="KILLED" if kills else "PILOT_READ",
        reading=(
            f"FX closes on the pre-registered kill condition: {'; '.join(kills)}. The negative "
            "is recorded and the pilot's cost is the last line of this arm."
            if kills
            else "FX's pilot survives its kill conditions; the style-versus-skeleton "
                 "decomposition above is the read, and at n=8 no bar was available to clear"
        ),
    )


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    original = "The bridge groaned. Marek counted the planks and the river took the seventh."
    check(skeleton_retention(original, original) == 1.0, "a text must retain its own skeleton")
    check(skeleton_retention(original, "nothing here at all whatsoever") < 0.2, "no overlap")
    check("the" not in skeleton(original), "stopwords must be stripped from the skeleton")

    check(mutation_rate(original, original) == 0.0, "identical text must not mutate")
    check(mutation_rate(original, "entirely different vocabulary appears") == 1.0, "full mutation")

    flat = [{"skeleton": 0.5, "style": 0.5, "mutation": 0.5} for _ in range(6)]
    check(saturated(flat), "a flat curve must read as saturated")
    moving = [{"skeleton": 0.9 - 0.1 * i, "style": 0.9 - 0.1 * i, "mutation": 0.1 * i}
              for i in range(6)]
    check(not saturated(moving), "a steadily moving curve must not read as saturated")

    scale = {name: 1.0 for name in ACTIVE}
    origin = {name: 0.0 for name in ACTIVE}
    median = {name: 10.0 for name in ACTIVE}
    near = style_retention(original, origin, median, scale)
    check(0.0 <= near <= 1.0, f"style retention must be a share, got {near}")

    for message in failures:
        print(f"FAIL {message}")
    print(f"transmission_chains selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--families", nargs="+", default=list(FAMILIES))
    parser.add_argument("--pairs", type=int, default=PILOT_PAIRS)
    parser.add_argument("--hops", type=int, default=HOPS)
    parser.add_argument("--chains", type=int, default=CHAINS)
    parser.add_argument("--tokens", type=int, default=MAX_NEW_TOKENS)
    parser.add_argument("--sham", type=int, default=4)
    parser.add_argument("--placebo", type=int, default=4)
    parser.add_argument("--placebo-tolerance", type=float, default=0.0)
    parser.add_argument("--rest-ratio", type=float, default=force_gpu.DEFAULT_REST_RATIO)
    parser.add_argument("--out", default=str(RESULTS / "force-fx.json"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "kill_conditions_fired": report["kill_conditions_fired"],
        "hop_curve": report["hop_curve"],
        "style_vs_skeleton": report["style_vs_skeleton"],
    }, indent=2))
    print("\n" + report["reading"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
