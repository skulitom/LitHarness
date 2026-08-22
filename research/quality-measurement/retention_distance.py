"""Track F2: does well-made prose survive context distance in the model's memory?

Transportation, measured mechanically. A passage is read once, then pushed away behind a wall of
neutral distractor text, then the model is asked — not in words, but by teacher forcing — how
much of it still helps:

    treated   [ passage ] [ distractor, D tokens ] [ probe window ]
    control   [ filler  ] [ distractor, D tokens ] [ probe window ]

    uplift(D) = logP(committed target tokens | treated) - logP(same tokens | control)

`filler` is own-generated prose of **exactly matched token length**, so the two conditions differ
in *what* sat at the far end of the context and not in *how far away* it was. Nothing is sampled
and nothing is asked; both conditions are single forward passes.

**The statistic is the decay slope, not the level.** A passage that is merely easy to predict
scores a large uplift at every distance; a passage that *sticks* loses less of it as the distance
grows. The side with the shallower decay wins, and `uplift(0.5k)` prints beside the slope as a
diagnostic so the two claims cannot be confused.

**The extractor is committed before any site is chosen, and the reason is arithmetic.** A
retention force that picks rare tokens on one side and common ones on the other measures rarity.
So sites are drawn from a label-blind unigram table built over the corpus itself, and the two
sides of a pair are then **trimmed to a frequency-matched subset** — pairs that cannot supply
`MIN_SITES` matched sites are dropped and *counted*, never silently.

Bars, controls and refusal states are `force_harness`'s. Runs under the MirrorBench interpreter.
"""

from __future__ import annotations

import argparse
import json
import math
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
from force_harness import (  # noqa: E402
    FAMILIES,
    RESULTS,
    Checkpoint,
    ForcePair,
    arm_status,
    attainability_table,
    combine_families,
    control_verdict,
    digest,
    load_pairs,
    ols_slope,
    pair_agreement,
    placebo_pairs,
    provenance,
    sham_pairs,
    sham_verdict,
    stratified_subsample,
    unit_key,
    verdict,
    view_gap_halves,
)
from force_harness import force_verdict as headline_verdict  # noqa: E402

DERIVED = HERE / "derived"
NEUTRAL_POOL = HERE / "corpora" / "toll-scenes.json"

#: Equally spaced in log2 by construction — the statistic is a slope over log2(D), so unequal
#: spacing would weight one distance more than another for a reason nobody declared.
#:
#: **Amended 2026-08-20, before F2 ran at full n and for a reason that has nothing to do with any
#: result.** The declared ladder was (512, 2048, 8192), a factor of four per rung. Forward-pass
#: cost is roughly linear in context length, so the 8k rung alone was about 64% of F2's whole
#: bill — and after the box went down and the governor went back to a 25-33% duty cycle, that
#: ladder priced F2 at ~8.4 GPU-hours per family and made the **two-family minimum
#: unaffordable**. A single-family F2 claims nothing by construction (§1.4), so the choice was
#: between a shorter ladder on two families and a longer ladder on one.
#:
#: A factor of three per rung keeps the log spacing exact, keeps three rungs, and costs about
#: 55% of the original. What it gives up is honest and is stated rather than buried: the longest
#: distance is **4,608 tokens rather than 8,192**, so F2 now measures survival across a shorter
#: stretch of context than the design asked for, and a force that would only separate beyond 4.6k
#: tokens is one this run cannot see. The criterion for the change is GPU-hours, which is
#: label-blind, and no F2 number existed at any n when it was made.
DISTANCES = (512, 1536, 4608)

#: Sites per side, and the floor below which a pair is dropped rather than measured thin.
SITES = 12
MIN_SITES = 6

#: The probe window is a re-presentation of the passage's own opening, in words. Long enough to
#: hold twelve well-spaced sites, short enough that the pass is cheap.
PROBE_WORDS = 220

#: Frequency matching tolerance, in log10 units of corpus unigram count. 0.5 is a factor of ~3.
FREQ_TOLERANCE = 0.5

#: Candidate targets must be distinctive. Words at or above this corpus count are too common to
#: carry retrieval information; words below the floor are typographical noise and typos.
MAX_COUNT = 400
MIN_COUNT = 2

# U+2019 is deliberate: RoyalRoad prose uses the curly apostrophe far more often
# than the straight one, and a pattern that misses it splits contractions in two.
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")  # noqa: RUF001

PRE_REGISTRATION: dict[str, Any] = {
    "track": "F2 retention under distance",
    "hypothesis": "well-made prose survives context distance in the model's memory better than "
                  "flat prose",
    "asks_nothing": "two teacher-forced forward passes per condition; nothing is sampled",
    "primary_statistic": "OLS slope of uplift over log2(distance); the side with the SHALLOWER "
                         "decay wins",
    "diagnostic": "uplift at the shortest distance — raw memorability, a different claim",
    "distances": list(DISTANCES),
    "conditions": "treated = passage + distractor + probe; control = token-length-matched "
                  "own-generated filler + same distractor + same probe",
    "extractor": "committed before any site is chosen: label-blind corpus unigram counts, "
                 f"candidates with {MIN_COUNT} <= count < {MAX_COUNT}, not window-initial, "
                 "then trimmed to a frequency-matched subset across the pair's two sides",
    "sites": SITES,
    "min_sites": MIN_SITES,
    "freq_tolerance_log10": FREQ_TOLERANCE,
    "drops": "a pair short of MIN_SITES matched sites is dropped and COUNTED; the drop list "
             "prints (§89's no-silent-caps rail)",
    "distractor": "own-generated prose (corpora/toll-scenes.json), repeated deterministically",
    "placebo": "byte-identical sides give byte-identical forward passes; the effect is exactly "
               "zero or the arithmetic is broken",
}


# ------------------------------------------------------------------------------- extractor


def corpus_counts(pairs: Sequence[ForcePair]) -> Counter[str]:
    """Label-blind unigram counts over every excerpt in the corpus.

    Label-blind is the load-bearing word: this table never sees `conversion`, so using it to
    choose probe sites cannot import the answer into the question. It is built from the corpus
    rather than shipped, so it needs no external frequency list and no second third-party
    dependency — and it is a table of counts, held in memory, never written out.
    """
    counts: Counter[str] = Counter()
    for pair in pairs:
        for _, text in pair.sides:
            counts.update(word.lower() for word in _WORD.findall(text))
    return counts


def probe_window(text: str) -> str:
    return " ".join(text.split()[:PROBE_WORDS])


def candidate_sites(window: str, counts: Counter[str]) -> list[tuple[int, str, float]]:
    """(word index, word, log10 count) for every candidate target in the probe window.

    Not window-initial, because a first token has no left context to be predicted from, and the
    uplift there would be an artifact of where the window was cut.
    """
    out: list[tuple[int, str, float]] = []
    for index, raw in enumerate(window.split()):
        if index < 8:
            continue
        match = _WORD.search(raw)
        if not match:
            continue
        word = match.group(0).lower()
        count = counts.get(word, 0)
        if not MIN_COUNT <= count < MAX_COUNT:
            continue
        out.append((index, word, math.log10(count)))
    return out


def matched_sites(
    high_window: str, low_window: str, counts: Counter[str]
) -> tuple[list[int], list[int]]:
    """Frequency-matched site sets for the two sides. Greedy, deterministic, order-independent.

    Each side's candidates are sorted by rarity, then paired across sides while the log-count gap
    stays inside the declared tolerance. What comes back is two site lists of equal length whose
    frequency profiles match — the property that stops this force from measuring rarity.
    """
    high = sorted(candidate_sites(high_window, counts), key=lambda row: (row[2], row[0]))
    low = sorted(candidate_sites(low_window, counts), key=lambda row: (row[2], row[0]))
    chosen_high: list[int] = []
    chosen_low: list[int] = []
    used: set[int] = set()
    for index_h, _, freq_h in high:
        if len(chosen_high) >= SITES:
            break
        for position, (index_l, _, freq_l) in enumerate(low):
            if position in used or abs(freq_h - freq_l) > FREQ_TOLERANCE:
                continue
            chosen_high.append(index_h)
            chosen_low.append(index_l)
            used.add(position)
            break
    return chosen_high, chosen_low


# --------------------------------------------------------------------------------- scoring


def _site_logprobs(
    per_token: Sequence[float], token_ids: Sequence[int], window: str, sites: Sequence[int],
    family: str,
) -> list[float]:
    """Map word indices to token positions by re-tokenising the window's prefixes.

    Word indices are family-independent — the trajectory of a measurement should not depend on
    whose tokenizer read it — but a logprob lives on a token, so the map has to be built per
    family. The first token of the word is the one scored: it carries the prediction.
    """
    words = window.split()
    out: list[float] = []
    for site in sites:
        # **No trailing space.** A trailing space tokenises as its own token, so `prefix + " "`
        # counts one too many and the logprob is read at the token *after* the matched site —
        # measured on both pinned tokenizers, 6,744 of 6,744 sites off by exactly one. The whole
        # point of `matched_sites` is that the scored token is frequency-matched across the two
        # sides; scoring its successor throws that away (the review measured mean |Δlog10|
        # rising from 0.175 at the matched word to 1.143 at the scored position, with 35% of
        # scored words above the MAX_COUNT reject ceiling). Leading-space tokenisation already
        # attaches the space to the *following* token, which is the one we want.
        prefix = " ".join(words[:site])
        offset = force_gpu.count_tokens(family, prefix)
        if 0 <= offset < len(per_token):
            out.append(per_token[offset])
    return out


def uplift_for_side(
    family: str,
    passage: str,
    window: str,
    sites: Sequence[int],
    filler: str,
    distractors: dict[int, str],
    cache: Checkpoint,
    governor: force_gpu.Governor,
    *,
    from_cache_only: bool = False,
) -> dict[int, float]:
    """Uplift at every declared distance, for one side.

    `from_cache_only` scores what a previous run banked and computes nothing. It is what makes an
    interrupted arm reportable: F2 stopped at 1,364 of 1,686 units when a parallel session took
    the card, and those units are a real partial measurement — throwing them away because the
    run did not reach the end would be discarding paid work for tidiness.
    """
    model_id, revision = force_gpu.resolve(family, "base")
    out: dict[int, float] = {}
    for distance in DISTANCES:
        key = unit_key(
            "f2", model_id, revision, digest(passage), digest(window),
            tuple(sites), distance, PROBE_WORDS,
            # **The two texts read from `corpora/toll-scenes.json` are part of the measurement
            # and now part of its key.** The distractor is what the model reads between the
            # passage and the probe window; the filler is the control side's entire prefix.
            # Change either and every uplift changes — but the key did not mention them, so a
            # rerun after editing the pool replayed the stale rows and reported
            # `computed_units: 0` beside a slope of 0.1413 that the current corpus produces as
            # 0.0402. A cache is only a cache when its key names everything the value depends
            # on; otherwise it is a way of publishing an old experiment under a new corpus.
            digest(distractors[distance]), digest(filler),
            # `offset-v2` marks the site-alignment fix. Rows cached before it hold uplifts read
            # one token past the matched site and are a different measurement, not a cheaper one.
            "offset-v2",
        )
        row = cache.get(key)
        if row is None and from_cache_only:
            continue
        if row is None:
            treated_prefix = passage + "\n\n" + distractors[distance] + "\n\n"
            control_prefix = filler + "\n\n" + distractors[distance] + "\n\n"
            treated, ids = force_gpu.token_logprobs(
                family, treated_prefix, window, head="base", governor=governor
            )
            control, _ = force_gpu.token_logprobs(
                family, control_prefix, window, head="base", governor=governor
            )
            picked_t = _site_logprobs(treated, ids, window, sites, family)
            picked_c = _site_logprobs(control, ids, window, sites, family)
            if not picked_t or len(picked_t) != len(picked_c):
                row = cache.put(key, {"uplift": None, "sites_scored": 0})
            else:
                row = cache.put(key, {
                    "uplift": statistics.fmean(
                        [t - c for t, c in zip(picked_t, picked_c, strict=True)]
                    ),
                    "sites_scored": len(picked_t),
                })
        if row["uplift"] is not None:
            out[distance] = row["uplift"]
    return out


def decay_slope(uplifts: dict[int, float]) -> float | None:
    if len(uplifts) < len(DISTANCES):
        return None
    xs = [math.log2(d) for d in sorted(uplifts)]
    ys = [uplifts[d] for d in sorted(uplifts)]
    slope = ols_slope(xs, ys)
    return None if math.isnan(slope) else slope


def build_distractors(family: str, scenes: Sequence[str]) -> tuple[dict[int, str], str]:
    """Distractor flushes at every distance, plus a token-length-matched filler passage."""
    body = "\n\n".join(scenes[:6])
    filler_source = scenes[-1]
    return (
        {d: force_gpu.repeat_to_tokens(family, body, d) for d in DISTANCES},
        filler_source,
    )


def run_family(family: str, pairs: Sequence[ForcePair], args: argparse.Namespace) -> dict[str, Any]:
    governor = force_gpu.Governor(
        rest_ratio=args.rest_ratio, pause_above_c=args.pause_c,
        resume_below_c=args.resume_c,
    )
    DERIVED.mkdir(parents=True, exist_ok=True)
    cache = Checkpoint(DERIVED / f"f2-{family}.jsonl")
    scenes = [s["text"] for s in json.loads(NEUTRAL_POOL.read_text(encoding="utf-8"))["scenes"]]
    distractors, filler_source = build_distractors(family, scenes)

    # Symmetric per-pair seed cap, for the same reason F1 applies it: excerpt lengths were never
    # matched by §79's selection (max |log10 word ratio| 0.4549), and a longer passage simply has
    # more content to be retrieved from. The cut is per pair and recorded.
    live: list[ForcePair] = []
    seed_budget: list[dict[str, Any]] = []
    for pair in pairs:
        high, low, record = force_gpu.symmetric_seeds(family, pair.high, pair.low)
        live.append(ForcePair(
            pair_id=pair.pair_id, stratum=pair.stratum, high=high, low=low,
            high_meta=pair.high_meta, low_meta=pair.low_meta,
        ))
        seed_budget.append({"pair_id": pair.pair_id, **record})
    # Stratified, not head-sliced: `load_pairs` returns aligned then crossed, so `live[:n]`
    # would draw both controls entirely from `aligned` and certify nothing about the
    # stratum §79 built to be adversarial.
    placebo = placebo_pairs(stratified_subsample(live, args.placebo))
    sham = sham_pairs(stratified_subsample(live, args.sham))
    counts = corpus_counts(live)

    scores: dict[str, dict[str, float]] = {}
    levels: dict[str, dict[str, float]] = {}
    dropped: list[dict[str, Any]] = []
    for pair in live + placebo + sham:
        high_window = probe_window(pair.high)
        low_window = probe_window(pair.low)
        high_sites, low_sites = matched_sites(high_window, low_window, counts)
        if len(high_sites) < MIN_SITES:
            dropped.append({"pair_id": pair.pair_id, "matched_sites": len(high_sites),
                            "why": f"fewer than {MIN_SITES} frequency-matched sites"})
            continue
        row: dict[str, float] = {}
        level: dict[str, float] = {}
        for side, text, window, sites in (
            ("high", pair.high, high_window, high_sites),
            ("low", pair.low, low_window, low_sites),
        ):
            filler = force_gpu.truncate_to_tokens(
                family, filler_source, force_gpu.count_tokens(family, text)
            )
            uplifts = uplift_for_side(
                family, text, window, sites, filler, distractors, cache, governor,
                from_cache_only=args.from_cache_only,
            )
            slope = decay_slope(uplifts)
            if slope is None:
                continue
            row[side] = slope
            level[side] = uplifts[min(DISTANCES)]
        if len(row) == 2:
            scores[pair.pair_id] = row
            levels[pair.pair_id] = level

    report: dict[str, Any] = {
        "family": force_gpu.family_provenance(family, "base"),
        "governor": governor.report(),
        "cache": cache.provenance(),
        "dropped_pairs": dropped,
        "dropped_count": len(dropped),
        "seed_budget": {
            "cap_tokens": force_gpu.SEED_CAP_TOKENS,
            "pairs_truncated": sum(1 for r in seed_budget if r["truncated"]),
            "max_log10_token_ratio_before_cut": max(
                (r["log10_token_ratio"] for r in seed_budget), default=0.0
            ),
        },
        "attention_shape_caveat": (
            "gemma-3-4b attends 1,024 tokens on five layers in six and Qwen2.5-3B is fully "
            "global to 32k, so a SPLIT_FAMILY at D=8k may be architectural rather than about "
            "prose. Pre-registered in force_gpu.ATTENTION_SHAPE before the first pass."
        ),
    }

    placebo_effect = 0.0
    for pair in placebo:
        if pair.pair_id in scores:
            effect = abs(scores[pair.pair_id]["high"] - scores[pair.pair_id]["low"])
            placebo_effect = max(placebo_effect, effect)
    report["placebo_identical"] = control_verdict(
        "placebo_identical", placebo_effect, tolerance=args.placebo_tolerance, kind="exact"
    )
    report["rewhitespace_sham"] = sham_verdict(
        "rewhitespace_sham", *pair_agreement(scores, sham, higher_wins=True)
    )

    strata: dict[str, list[ForcePair]] = {
        "aligned": [p for p in live if p.stratum == "aligned"],
        "crossed": [p for p in live if p.stratum == "crossed"],
        **view_gap_halves(live),
    }
    for label, members in strata.items():
        if not members:
            continue
        # Shallower decay wins: the slope is negative and the good side's is closer to zero, so
        # `higher_wins` is the right direction and saying it here rather than by sign convention
        # is what keeps a later reader from having to reconstruct which way the hypothesis went.
        binding = label in ("aligned", "crossed")
        report[label] = verdict(
            label, *pair_agreement(scores, members, higher_wins=True),
            n_before_drops=len(members), binding=binding,
        )
        report[f"{label}__level_DIAGNOSTIC"] = verdict(
            label, *pair_agreement(levels, members, higher_wins=True),
            n_before_drops=len(members), binding=binding,
        )
    verdict_from_controls = arm_status({
        "placebo_identical": report["placebo_identical"],
        "rewhitespace_sham": report["rewhitespace_sham"],
    })
    report["status"] = verdict_from_controls["status"]
    if verdict_from_controls.get("why"):
        report["why"] = verdict_from_controls["why"]
    report["control_states"] = verdict_from_controls["controls"]
    return report


def run(args: argparse.Namespace) -> dict[str, Any]:
    pairs = load_pairs()
    if args.pairs:
        by_stratum: dict[str, list[ForcePair]] = {}
        for pair in pairs:
            by_stratum.setdefault(pair.stratum, []).append(pair)
        pairs = [p for rows_ in by_stratum.values() for p in rows_[: args.pairs]]

    per_family = {}
    for family in args.families:
        per_family[family] = run_family(family, pairs, args)
        force_gpu.free()

    sizes = {
        "aligned": sum(1 for p in pairs if p.stratum == "aligned"),
        "crossed": sum(1 for p in pairs if p.stratum == "crossed"),
        **{k: len(v) for k, v in view_gap_halves(pairs).items()},
    }
    combined = {
        label: combine_families(per_family, label)
        for label in ("aligned", "crossed", "crossed_tight", "crossed_loose")
    }
    headline = headline_verdict(per_family, combined)
    return provenance(
        track="F2",
        pre_registration_track=PRE_REGISTRATION,
        pairs=len(pairs),
        stratum_sizes=sizes,
        attainability=attainability_table(sizes),
        per_family=per_family,
        combined=combined,
        force_verdict=headline["verdict"],
        force_verdict_detail=headline,
        reading=(
            "F2 clears both binding strata on both families: what the higher-converting side "
            "left in the model survives distance better, measured with no question asked"
            if headline["verdict"] == "PASS"
            else "F2 does not clear both binding strata; the rows below say which reading "
                 "failed and in which of the declared ways"
        ),
    )


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    counts = Counter({"rare": 3, "scarce": 4, "common": 5000, "mid": 50})
    window = " ".join(["common"] * 8 + ["rare", "common", "mid", "scarce", "common"])
    sites = candidate_sites(window, counts)
    check([w for _, w, _ in sites] == ["rare", "mid", "scarce"], f"candidates {sites}")
    check(all(i >= 8 for i, _, _ in sites), "window-initial words must be excluded")

    # Frequency matching refuses a pairing that would compare a rare word with a common one.
    high = " ".join(["x"] * 8 + ["rare"])
    low = " ".join(["x"] * 8 + ["mid"])
    picked_h, picked_l = matched_sites(high, low, counts)
    check(not picked_h, f"a 1.2-decade gap must not match: {picked_h}, {picked_l}")
    low_close = " ".join(["x"] * 8 + ["scarce"])
    picked_h, picked_l = matched_sites(high, low_close, counts)
    check(len(picked_h) == 1 and len(picked_l) == 1, "a 0.12-decade gap must match")

    # The slope is over log2 distance and it refuses an incomplete ladder rather than fitting it.
    # Built from DISTANCES rather than from literals, so an amended ladder cannot leave a test
    # asserting a slope over distances the module no longer uses.
    check(decay_slope(dict(zip(DISTANCES[:2], [1.0, 0.5], strict=True))) is None,
          "a short ladder must refuse")
    step = math.log2(DISTANCES[1]) - math.log2(DISTANCES[0])
    check(
        abs((math.log2(DISTANCES[2]) - math.log2(DISTANCES[1])) - step) < 1e-9,
        f"DISTANCES must be equally spaced in log2; got {DISTANCES}",
    )
    ladder = dict(zip(DISTANCES, [2 * step, step, 0.0], strict=True))
    slope = decay_slope(ladder)
    check(slope is not None and abs(slope + 1.0) < 1e-9, f"slope {slope} on {DISTANCES}")

    check(len(probe_window(" ".join(["w"] * 500)).split()) == PROBE_WORDS, "probe window size")

    for message in failures:
        print(f"FAIL {message}")
    print(f"retention_distance selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--families", nargs="+", default=list(FAMILIES))
    parser.add_argument("--pairs", type=int, default=0)
    parser.add_argument("--sham", type=int, default=100)
    parser.add_argument("--placebo", type=int, default=24)
    parser.add_argument("--placebo-tolerance", type=float, default=0.0)
    parser.add_argument("--rest-ratio", type=float, default=force_gpu.DEFAULT_REST_RATIO)
    parser.add_argument("--from-cache-only", action="store_true",
                        help="score what a previous run banked and compute nothing; needs no GPU")
    parser.add_argument("--pause-c", type=int, default=force_gpu.PAUSE_ABOVE_C)
    parser.add_argument("--resume-c", type=int, default=force_gpu.RESUME_BELOW_C,
                        help="must sit just UNDER the between-calls floor; set too "
                             "low the hold never releases and the run stalls")
    parser.add_argument("--out", default=str(RESULTS / "force-f2.json"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["combined"], indent=2))
    print(f"\nF2 verdict: {report['force_verdict']}\n{report['reading']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
