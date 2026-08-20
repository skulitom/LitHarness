"""Track F1: does strong prose hold the model's continuations in its register for longer?

The programme's flagship, and the arm that gives it its name. Every measurement this repository
has made of "which passage is better" has gone through a *question* — a verdict, a preference, a
named difference — and §89.4 measured the verdict channel dead at two ten-thousandths of the
answer distribution. This asks nothing. It seeds a model with a passage, lets it write, and
measures **how long the passage's register survives in what the model produces**. If well-made
prose bends the generation field harder, that is a valence channel obtained without a slot, a
position or a question.

    seed  --> K continuations --> trajectory in z-space --> when does it leave the seed's
                                                            register for the model's median?

**The confound is named before the run and it is not a small one.** Garish prose also binds: a
seed far from the model's median in feature space will hold its continuations longer for reasons
that have nothing to do with quality. So the covariate is the seed's own t=0 distance from the
median, the adjustment is a **label-blind** nuisance regression — the fit never sees
`conversion` — and the bar is declared on the *residual*. The raw number cannot tell the
hypothesis from the confound and is printed anyway, because both readings print (§89.2).

**Two alternatives are pre-registered against each other**, which is what makes this a test
rather than a demonstration: `monotone` — residual binding separates the sides at the bars — and
`inverted_u` — binding rises with distinctiveness and then falls, which is what "garish" looks
like if it is real.

Bars, controls, refusal states and the two-family rule are `force_harness`'s and are not
restated. Generation, pinning and the governor are `force_gpu`'s. Runs under the MirrorBench
interpreter only.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import force_gpu  # noqa: E402
import force_remote  # noqa: E402
from authorship_tells import FEATURE_NAMES, features  # noqa: E402
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
    pair_agreement,
    placebo_pairs,
    provenance,
    residualise,
    sham_pairs,
    sham_verdict,
    stratified_subsample,
    unit_key,
    verdict,
    view_gap_halves,
)
from force_harness import force_verdict as headline_verdict  # noqa: E402

#: Derived text of third-party prose lives here and nowhere else. Gitignored wholesale
#: (plan/force-program.md §1.6): a continuation of a RoyalRoad excerpt carries that excerpt's
#: register and often its sentences, so it is excerpt-bearing by the same rule that gitignores
#: the corpus it derives from.
DERIVED = HERE / "derived"

K = 8
MAX_NEW_TOKENS = 512
WINDOW_WORDS = 100
STRIDE_WORDS = 25

#: `words` is excluded and the exclusion is load-bearing. It is a feature in
#: `authorship_tells.features` on purpose — there, length is a confound that must be visible —
#: but here every window is the same length by construction, so its spread is an artifact of the
#: last, short window and it would put the seed (1,000 words) at an enormous z-distance from
#: every window (100 words) for a reason that is about windowing and not about prose.
EXCLUDED = ("words",)
ACTIVE = tuple(name for name in FEATURE_NAMES if name not in EXCLUDED)

#: The seed's own register anchor is the centroid of the seed's windows, not the feature row of
#: the whole seed. Like for like: a rate measured over 1,000 words and a rate measured over 100
#: are not the same statistic, and comparing them would make the trajectory's first step an
#: artifact of the change in window size.
SEED_WINDOWS = True

#: The neutral pool. Own-generated prose — the one un-memorised source this project owns. It
#: rides every run and its centroid is reported as a diagnostic; **it is no longer the anchor**,
#: for the reason in :data:`PILOT_CORRECTIONS`.
NEUTRAL_POOL = HERE / "corpora" / "toll-scenes.json"
NEUTRAL_SEEDS = 8

#: **Two corrections the first pilot forced, recorded rather than quietly made.** Both criteria
#: are label-blind — neither looks at `conversion`, and the pilot's own agreement is discarded,
#: which §2.5 declared in advance precisely so this correction would be available without being
#: a result. This is §94.6's shape twice over: there P5's first formulation read the wrong share
#: and the next pilot caught it; here the anchor and the reduction were both wrong and the same
#: kind of run caught them.
PILOT_CORRECTIONS: dict[str, Any] = {
    "anchor": {
        "declared": "M = centroid of continuations from the own-generated neutral pool",
        "measured": "censoring rate 0.979 — almost no continuation ever left the seed's "
                    "register for that anchor, because own-generated LitRPG with [STATUS] "
                    "blocks is not a neutral centre: it is its own register, and every "
                    "RoyalRoad continuation sits far from it at every window",
        "corrected_to": "M = centroid of EVERY continuation window in the run, pooled across "
                        "both strata, both sides and the neutral pool — literally the model's "
                        "median continuation on this material",
        "why_not_circular": "CORRECTED 2026-08-20 after adversarial review: the first version "
                            "built M from every continuation in the run, including the control "
                            "sides — and both controls are made from the HIGH side, so M was "
                            "64.9% high-derived against 33.8% low and the claim that it 'cannot "
                            "create a systematic high/low difference' was false. M is now built "
                            "from live pairs and the neutral pool only.",
        "after_correction": "censoring rate 0.250 on the same cached generations",
        "criterion": "censoring rate — label-blind",
    },
    "replicate_reduction": {
        "declared": "median over K",
        "corrected_to": "mean over K",
        "why": "the crossover index is a small integer, so a median over eight replicates takes "
               "few distinct values and pairs tie constantly; a mean takes eighths and the "
               "decided share stays above the declared 0.90 floor. The tie rate is the "
               "label-blind criterion §2.5 named in advance.",
    },
}

#: The sham is expensive — every sham side is a fresh batch of K continuations — so it runs on a
#: declared subsample rather than the full corpus, and the subsample is the first N pair_ids in
#: sorted order so it is a rule and not a draw. At n=100 the interval can refuse a sham effect
#: of 0.60 or larger, which is the size that would matter.
SHAM_PAIRS = 100

PRE_REGISTRATION: dict[str, Any] = {
    "track": "F1 register half-life",
    "hypothesis": "strong prose holds the model's continuations in its register longer before "
                  "they decay to the model's median centroid",
    "asks_nothing": "the seed goes in as raw prose on a pretrained head; no instruction, no "
                    "question, no slot, no position",
    "primary_statistic": "crossover window index — the first window at which distance to the "
                         "seed's register exceeds distance to the model median",
    "secondary_statistic": "exponential half-life of r_w - 0.5; DIAGNOSTIC, because a fit is a "
                           "functional-form assumption and the primary read may not rest on one",
    "censoring": "a continuation that never crosses within L is censored at the last window and "
                 "ranks above every observed value; the censoring rate prints",
    "replicates": K,
    "replicate_reduction": "median over K",
    "confound": "distinctiveness — garish prose also binds",
    "covariate": "seed's t=0 z-distance from the model median centroid",
    "adjustment": "label-blind nuisance regression; the fit never sees conversion",
    "bar_declared_on": "the residual agreement, because the raw number cannot tell the "
                       "hypothesis from the confound",
    "alternatives": {
        "monotone": "residual crossover separates high- from low-conversion sides at the bars",
        "inverted_u": "a quadratic term in the covariate is signed for an interior peak — "
                      "binding rises with distinctiveness and then falls",
    },
    "window_words": WINDOW_WORDS,
    "stride_words": STRIDE_WORDS,
    "max_new_tokens": MAX_NEW_TOKENS,
    "excluded_features": list(EXCLUDED),
    "z_scale": "the run's own per-feature population sd over every window in the run; "
               "run-dependent, so numbers are not comparable across runs and the scale's digest "
               "is recorded",
    "neutral_pool": "own-generated prose (corpora/toll-scenes.json), NEUTRAL_SEEDS seeds x K",
    "sham_subsample": SHAM_PAIRS,
    "pilot_may_set": "only L, and only from the censoring rate; the label is never consulted, "
                     "and the pilot's own agreement is not a result",
}


# ---------------------------------------------------------------------------- trajectories


#: **F1's feature space is blind to layout, and that is why its sham certified nothing.**
#: :func:`windows` joins words with a single space, so no window ever contains a newline — and
#: `ablate.rewhitespace` changes newlines and intra-line spacing and nothing else. Measured on
#: 100 real sham pairs: **100 of 100 produced byte-identical feature rows**. The sham's agreement
#: was therefore sampling noise on identical inputs, and the reading it appeared to certify —
#: "this force does not read layout" — was never tested. Two consequences, both recorded rather
#: than papered over: `paragraph_len_mean` is a constant 100.0 in every window (so the space is
#: 22 features, not 23), and a whitespace sham cannot be F1's formatting control at all. A
#: control for F1 has to perturb something that survives windowing.
SHAM_IS_INVISIBLE_TO_THIS_SPACE = True


def windows(text: str, *, size: int = WINDOW_WORDS, stride: int = STRIDE_WORDS) -> list[str]:
    """Overlapping word windows. The trajectory's time axis, in words rather than tokens.

    Words, because every feature in this space is a rate per 1k words and a token window would
    make the axis depend on which family's tokenizer produced it — two families' trajectories
    would then not be the same measurement.
    """
    parts = text.split()
    if len(parts) < size:
        return [" ".join(parts)] if parts else []
    return [
        " ".join(parts[start : start + size])
        for start in range(0, len(parts) - size + 1, stride)
    ]


def rows(text: str) -> list[dict[str, float]]:
    return [features(window) for window in windows(text)]


def centroid(feature_rows: Sequence[dict[str, float]]) -> dict[str, float]:
    return {name: statistics.fmean([row[name] for row in feature_rows]) for name in ACTIVE}


def scale_of(feature_rows: Sequence[dict[str, float]]) -> dict[str, float]:
    return {
        name: statistics.pstdev([row[name] for row in feature_rows]) if len(feature_rows) > 1
        else 0.0
        for name in ACTIVE
    }


def z_distance(
    row: dict[str, float], anchor: dict[str, float], scale: dict[str, float]
) -> float:
    """L2 over per-feature z-deltas, zero-spread features skipped. `repair_generation`'s."""
    total = 0.0
    for name in ACTIVE:
        sd = scale.get(name, 0.0)
        if sd > 0:
            total += ((row[name] - anchor[name]) / sd) ** 2
    return total ** 0.5


def trajectory(
    continuation: str,
    seed_anchor: dict[str, float],
    median: dict[str, float],
    scale: dict[str, float],
) -> tuple[list[float], list[float]]:
    """(distance to seed register, distance to model median) per window."""
    to_seed: list[float] = []
    to_median: list[float] = []
    for row in rows(continuation):
        to_seed.append(z_distance(row, seed_anchor, scale))
        to_median.append(z_distance(row, median, scale))
    return to_seed, to_median


def crossover(to_seed: Sequence[float], to_median: Sequence[float]) -> tuple[int, bool]:
    """(index, censored). The first window where the seed's pull loses to the median's."""
    for index, (seed_d, median_d) in enumerate(zip(to_seed, to_median, strict=True)):
        if seed_d > median_d:
            return index, False
    return len(to_seed), True


def half_life(to_seed: Sequence[float], to_median: Sequence[float]) -> float:
    """Exponential fit to r_w - 0.5, in windows. DIAGNOSTIC; the primary read is the crossover.

    `r_w = d(median) / (d(seed) + d(median))` starts near 1 when the continuation sits in the
    seed's register and decays toward 0.5 when the two anchors are equidistant. Fitted in logs by
    least squares over the windows where the residual is positive; NaN where fewer than three
    are, which is a refusal rather than a zero.
    """
    ys: list[float] = []
    xs: list[float] = []
    for index, (seed_d, median_d) in enumerate(zip(to_seed, to_median, strict=True)):
        total = seed_d + median_d
        if total <= 0:
            continue
        residual = median_d / total - 0.5
        if residual > 1e-6:
            xs.append(float(index))
            ys.append(math.log(residual))
    if len(xs) < 3:
        return float("nan")
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    if denominator == 0:
        return float("nan")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denominator
    if slope >= 0:
        return float("inf")
    return -math.log(2) / slope


# ------------------------------------------------------------------------------ generation


def neutral_pool() -> list[str]:
    payload = json.loads(NEUTRAL_POOL.read_text(encoding="utf-8"))
    return [scene["text"] for scene in payload["scenes"][:NEUTRAL_SEEDS]]


def continuations_for(
    family: str,
    text: str,
    cache: Checkpoint,
    governor: force_gpu.Governor,
    *,
    k: int = K,
    max_new_tokens: int = MAX_NEW_TOKENS,
    remote: force_remote.Ledger | None = None,
    remote_model: str = "claude-haiku-4-5",
    cache_salt: str = "",
    from_cache_only: bool = False,
) -> list[str]:
    """K continuations, replayed from the digest-keyed cache when they already exist.

    The key is every input that could change the answer — family, revision, head, text digest,
    K, length, sampling — and never a label. A cache keyed `(pair, side)` replays numbers
    computed on texts that no longer exist the moment a transform is edited; RUNBOOK's rule, and
    the reason `placebo_identical` costs nothing here: its two sides are the same text, so its
    generations are the high side's, already on disk.
    """
    if remote is not None:
        # The remote transport has no revision to key on and no token cap to record, so the key
        # carries the model name and the frozen instruction instead. A cache keyed on anything
        # less would replay continuations produced under a different prompt.
        # The word cap and the short-drop floor are IN the key. They change what a cached row
        # contains without changing the text it came from, so a key that omitted them would
        # replay un-normalised continuations beside normalised ones — RUNBOOK's rule about
        # keying a cache on every input that could change the answer.
        # `cache_salt` participates **only when it is set**, and that is not a nicety. Appending
        # an empty string still changes the digest, so adding the parameter at all orphaned every
        # one of the 531 seeds this arm had already paid for — a resumed run would have re-bought
        # ~$50 of continuations to produce identical numbers. A cache key must change when the
        # measurement changes and not when the signature does.
        parts = [
            "f1-remote", remote_model, digest(force_remote.CONTINUATION_SYSTEM),
            digest(text), k,
            force_remote.CONTINUATION_WORDS, force_remote.MIN_CONTINUATION_WORDS,
        ]
        if cache_salt:
            parts.append(cache_salt)
        key = unit_key(*parts)
        row = cache.get(key)
        if row is not None:
            return row["continuations"]
        if from_cache_only:
            # Re-scoring what a paid run banked, buying nothing. The corrections that followed
            # the adversarial review are all in the *scoring*, not the generation, so the same
            # 531 seeds re-read under fixed arithmetic give corrected numbers for free.
            return []
        try:
            produced, tally = force_remote.continuations(
                text, model=remote_model, k=k, ledger=remote
            )
        except force_remote.CeilingReached:
            # **The ceiling stops buying; it does not discard what was bought.** Returning empty
            # here drops this pair and counts it, so the run still reports a reading over the
            # pairs it could afford, with the shortfall visible as `dropped_before_scoring` and
            # a stratum that falls under MIN_REFUTING_N reading DEGRADED_STRATUM rather than
            # FAIL. The earlier behaviour — abandon everything and return NOT_RUN — threw away
            # a corpus that had already been paid for.
            return []
        cache.put(key, {
            "continuations": produced, "text_digest": digest(text),
            "family": "haiku-4-5", "tally": tally,
        })
        return produced

    model_id, revision = force_gpu.resolve(family, "base")
    key = unit_key(
        "f1", model_id, revision, digest(text), k, max_new_tokens,
        force_gpu.TEMPERATURE, force_gpu.TOP_P,
    )
    row = cache.get(key)
    if row is not None:
        return row["continuations"]
    produced = force_gpu.sample_continuations(
        family, text, k=k, max_new_tokens=max_new_tokens, head="base", governor=governor
    )
    cache.put(key, {"continuations": produced, "text_digest": digest(text), "family": family})
    return produced


# --------------------------------------------------------------------------------- scoring


def side_statistics(
    text: str,
    produced: Sequence[str],
    median: dict[str, float],
    scale: dict[str, float],
) -> dict[str, float]:
    """One side's numbers: median crossover over K, the half-life, and the covariate."""
    seed_rows = rows(text)
    seed_anchor = centroid(seed_rows) if seed_rows else {}
    crossings: list[int] = []
    censored = 0
    lives: list[float] = []
    for continuation in produced:
        to_seed, to_median = trajectory(continuation, seed_anchor, median, scale)
        if not to_seed:
            continue
        index, was_censored = crossover(to_seed, to_median)
        crossings.append(index)
        censored += int(was_censored)
        life = half_life(to_seed, to_median)
        if math.isfinite(life):
            lives.append(life)
    if not crossings:
        return {}
    return {
        # Mean, not median: see PILOT_CORRECTIONS. The crossover index is a small integer, so a
        # median over eight replicates takes few distinct values and the pair comparison ties
        # constantly; a mean takes eighths and the decided share clears the declared floor.
        "crossover": statistics.fmean(crossings),
        "censored_share": censored / len(crossings),
        "half_life": statistics.median(lives) if lives else float("nan"),
        # The covariate: how far the seed's own register sits from the model's median. Computed
        # from the seed alone, so it is available before a single continuation is read.
        "distinctiveness": z_distance(seed_anchor, median, scale) if seed_anchor else 0.0,
        "replicates": len(crossings),
    }


def score_pairs(
    pairs: Sequence[ForcePair],
    family: str,
    cache: Checkpoint,
    governor: force_gpu.Governor,
    *,
    k: int,
    max_new_tokens: int,
    remote: force_remote.Ledger | None = None,
    workers: int = force_remote.DEFAULT_WORKERS,
    from_cache_only: bool = False,
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Generate for every side, then build the run's z-space from every window it produced."""
    # **Seeds are deduplicated by digest before anything is generated**, which matters more on
    # the remote transport than locally: `placebo_identical` builds both its sides from the high
    # side's text, so a naive walk would buy the same continuations twice. Sequentially the cache
    # absorbs that; in parallel two workers miss the cache together and both pay.
    # **The neutral pool goes first**, and the ordering is load-bearing rather than tidy. Every
    # trajectory in the run is measured against the model-median anchor the pool defines, so a
    # run that spends its budget on pairs and then hits the spend ceiling before the pool has
    # no anchor and nothing it bought can be scored. Eight seeds, generated before the 622 that
    # depend on them.
    pool_texts = neutral_pool()
    wanted: dict[str, str] = {digest(text): text for text in pool_texts}
    for pair in pairs:
        for _, text in pair.sides:
            wanted.setdefault(digest(text), text)

    # **The placebo must not share the deduplicated generation set, and this is what made F1's
    # first full run unreadable.** `placebo_identical` builds both sides from the same text, so
    # dedup by digest hands both sides *one* list of continuations — numerically identical by
    # construction, every pair a tie, `decided = 0`. On the local transport that is exactly the
    # intended arithmetic check (§89.4), because seeding on the text digest makes byte-identical
    # sides byte-identical anyway. On the remote transport it is the opposite of the intended
    # test: §1.7 downgraded the placebo to an *equivalence* check against sampling noise, and
    # that requires the two sides to be sampled **independently**. Dedup silently removed the
    # only thing the remote placebo measures. So the placebo's low side is generated under its
    # own key when the transport is non-deterministic, and pays for itself.
    placebo_low: dict[str, str] = {}
    if remote is not None:
        for pair in pairs:
            if pair.stratum == "placebo_identical":
                placebo_low[f"placebo-low|{pair.pair_id}"] = pair.low

    generated: dict[str, list[str]] = {}
    if remote is not None and len(wanted) > 1:
        from concurrent.futures import ThreadPoolExecutor

        # Whole seeds run in parallel; the K replicates *inside* a seed stay sequential so the
        # 26k-token prefix is written once and read K-1 times. Four workers is
        # `elicit.CLI_MAX_WORKERS`, reused rather than re-chosen.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    continuations_for, family, text, cache, governor,
                    k=k, max_new_tokens=max_new_tokens, remote=remote,
                    from_cache_only=from_cache_only,
                ): key
                for key, text in wanted.items()
            }
            for future in futures:
                generated[futures[future]] = future.result()
    else:
        for key, text in wanted.items():
            generated[key] = continuations_for(
                family, text, cache, governor, k=k, max_new_tokens=max_new_tokens, remote=remote,
                from_cache_only=from_cache_only,
            )

    for label, text in placebo_low.items():
        generated[label] = continuations_for(
            family, text, cache, governor, k=k, max_new_tokens=max_new_tokens,
            remote=remote, cache_salt=label, from_cache_only=from_cache_only,
        )

    produced: dict[tuple[str, str], list[str]] = {}
    for pair in pairs:
        for side, text in pair.sides:
            key = digest(text)
            if side == "low" and f"placebo-low|{pair.pair_id}" in generated:
                key = f"placebo-low|{pair.pair_id}"
            produced[(pair.pair_id, side)] = generated[key]

    pool_continuations: list[str] = []
    for text in pool_texts:
        pool_continuations.extend(generated.get(digest(text), []))

    # The run's own unit system, built from every window the run produced — continuations and
    # seeds alike, so a seed's distance is measured in the same units as a window's.
    every_row: list[dict[str, float]] = []
    for texts in produced.values():
        for continuation in texts:
            every_row.extend(rows(continuation))
    for continuation in pool_continuations:
        every_row.extend(rows(continuation))
    for pair in pairs:
        for _, text in pair.sides:
            every_row.extend(rows(text))
    if len(every_row) < 2:
        return {}, {"status": "NOT_SCREENABLE", "why": "no windows produced"}
    scale = scale_of(every_row)

    # The anchor, corrected: M is the centroid of EVERY continuation window in the run. The
    # own-generated pool's centroid rides along as a diagnostic and the distance between the two
    # is printed, because the pilot found that anchoring on the pool censored 97.9% of
    # trajectories — own-generated LitRPG is its own register, not a neutral centre.
    # **The anchor is built from live pairs and the neutral pool only.** `produced` also holds the
    # control sides, and both controls are made *from the high side*: the placebo duplicates it
    # and the sham re-whitespaces it. Including them made M 64.9% high-derived material against
    # 33.8% low — so `PILOT_CORRECTIONS["anchor"]["why_not_circular"]`, which claimed the anchor
    # "cannot create a systematic high/low difference", was false in fact. It shifted M by 0.0824
    # z-units, in the direction that favours the label.
    live_ids = {
        pair.pair_id for pair in pairs
        if pair.stratum not in ("placebo_identical", "rewhitespace_sham")
    }
    continuation_rows: list[dict[str, float]] = []
    for (pair_id, _side), texts in produced.items():
        if pair_id not in live_ids:
            continue
        for continuation in texts:
            continuation_rows.extend(rows(continuation))
    pool_rows: list[dict[str, float]] = []
    for continuation in pool_continuations:
        pool_rows.extend(rows(continuation))
    continuation_rows.extend(pool_rows)
    median = centroid(continuation_rows) if continuation_rows else centroid(every_row)
    pool_median = centroid(pool_rows) if pool_rows else median

    scores: dict[str, dict[str, float]] = {}
    covariate: dict[str, float] = {}
    half_lives: dict[str, float] = {}
    censored: list[float] = []
    for pair in pairs:
        row: dict[str, float] = {}
        for side, text in pair.sides:
            stats = side_statistics(text, produced[(pair.pair_id, side)], median, scale)
            if not stats:
                continue
            row[side] = stats["crossover"]
            covariate[f"{pair.pair_id}|{side}"] = stats["distinctiveness"]
            half_lives[f"{pair.pair_id}|{side}"] = stats["half_life"]
            censored.append(stats["censored_share"])
        if len(row) == 2:
            scores[pair.pair_id] = row
    context = {
        "scale_digest": digest(json.dumps(scale, sort_keys=True)),
        "median_digest": digest(json.dumps(median, sort_keys=True)),
        "anchor": "centroid of every continuation window in the run (corrected; see "
                  "PILOT_CORRECTIONS)",
        "pool_anchor_distance_DIAGNOSTIC": round(
            z_distance(pool_median, median, scale), 4
        ),
        "neutral_pool_seeds": len(pool_texts),
        "neutral_pool_continuations": len(pool_continuations),
        "censoring_rate": round(statistics.fmean(censored), 4) if censored else None,
        "windows_in_scale": len(every_row),
        "covariate": covariate,
        "half_lives": half_lives,
    }
    return scores, context


def residual_scores(
    scores: dict[str, dict[str, float]], covariate: dict[str, float], *, quadratic: bool = False
) -> dict[str, dict[str, float]]:
    """The label-blind adjustment, applied side-wise and then re-paired."""
    flat = {
        f"{pair_id}|{side}": value
        for pair_id, row in scores.items()
        for side, value in row.items()
    }
    adjusted = residualise(flat, covariate, quadratic=quadratic)
    out: dict[str, dict[str, float]] = {}
    for key, value in adjusted.items():
        pair_id, side = key.rsplit("|", 1)
        out.setdefault(pair_id, {})[side] = value
    paired = {pair_id: row for pair_id, row in out.items() if len(row) == 2}

    # **A raw tie stays a tie, and this is the difference between a refusal and a refutation.**
    # `residualise` subtracts `a + b*x` from each side, so two sides with the *same* crossover
    # come out differing by `-b*(x_hi - x_lo)` — a decision whose sign is set entirely by the
    # covariate, with zero input from the statistic the bar is about. Measured on the real F1
    # run: the covariate explains essentially nothing (R^2 = 3.4e-05), every one of `aligned`'s
    # 17 raw ties was converted, and a raw INERT_GENERATOR became a residual FAIL. Both rails
    # die that way — `MIN_DECIDED_SHARE` can never fire on the reading the bar is declared on.
    for pair_id, row in paired.items():
        raw = scores.get(pair_id, {})
        if raw.get("high") is not None and raw.get("high") == raw.get("low"):
            midpoint = (row["high"] + row["low"]) / 2
            row["high"] = row["low"] = midpoint
    return paired


#: |t| for the quadratic term, two-sided at ALPHA on a large residual dof. The pre-registration
#: at `plan/force-program.md` says the inverted-U alternative fires when the quadratic term is
#: **significant**; the module weakened that to *signed*, which is not the same declaration and
#: is much easier to satisfy.
QUADRATIC_T = 1.96


def inverted_u(covariate: dict[str, float], values: dict[str, float]) -> dict[str, Any]:
    """The pre-registered alternative: is the quadratic term **significantly** signed?

    **What this rule used to be, and what it did.** `inside = quad < 0 and the peak is interior`
    — no standard error, no interval, nothing between a coefficient's sign and a published
    reading. The fit it declared READ on the real run was quadratic -0.017463 +/- 0.013543, i.e.
    t = -1.29 with R^2 = 0.003; run against 2,000 synthetic samples whose y is independent of x,
    the same rule fires **42% of the time**. A pre-registered alternative that a coin satisfies
    two times in five is not an alternative, and `plan/force-program.md` had said "significant"
    all along — the weakening happened here, silently, in the implementation.

    The caller is now responsible for handing over **live sides only**. The previous call site
    passed the whole `scores` dict, which carries the placebo and sham sides: 168 of its 578
    rows were controls and 105 were exact duplicates of other rows, and `n: 578` was published
    as a sample size for a fit over material that was two-thirds re-used.
    """
    keys = [k for k in values if k in covariate and math.isfinite(values[k])]
    if len(keys) < 12:
        return {"status": "INSUFFICIENT_N", "n": len(keys)}
    xs = [covariate[k] for k in keys]
    ys = [values[k] for k in keys]
    design = [[1.0, x, x * x] for x in xs]
    from force_harness import least_squares_with_se

    fit = least_squares_with_se(design, ys)
    if fit is None:
        return {"status": "NOT_SCREENABLE",
                "why": "design matrix is singular or has no residual degrees of freedom"}
    (_, linear, quad), (_, _, quad_se) = fit
    t_stat = quad / quad_se if quad_se else float("inf") if quad else 0.0
    peak = -linear / (2 * quad) if quad else float("nan")
    significant = abs(t_stat) >= QUADRATIC_T
    inside = bool(significant and quad < 0 and min(xs) < peak < max(xs))
    return {
        "status": "READ",
        "n": len(keys),
        "linear": round(linear, 6),
        "quadratic": round(quad, 6),
        "quadratic_se": round(quad_se, 6),
        "quadratic_t": round(t_stat, 4) if math.isfinite(t_stat) else None,
        "significance_bar": QUADRATIC_T,
        "significant": significant,
        "peak_at": round(peak, 4) if math.isfinite(peak) else None,
        "covariate_range": [round(min(xs), 4), round(max(xs), 4)],
        "interior_peak": inside,
        "reading": (
            "binding rises with distinctiveness and then falls — the garish-prose shape"
            if inside
            else "no significant interior peak; the inverted-U alternative is not what this run "
                 "shows" if significant or abs(t_stat) < QUADRATIC_T else
            "no interior peak"
        ),
    }


# ------------------------------------------------------------------------------------- run


def _seed_budget_summary(rows: Sequence[dict[str, Any]], *, remote: bool) -> dict[str, Any]:
    """The §95.4 length confound, summarised in whichever unit the transport could measure.

    The two transports cap in different units — tokens locally, words remotely, because no
    tokenizer is reachable through `claude -p` — and the ratio key differs with them. Reading one
    key and hoping is how the first Haiku smoke run died on a `KeyError` after paying for nine
    seeds, which is the cheapest place that bug was ever going to be found.
    """
    key = "log10_word_ratio" if remote else "log10_token_ratio"
    ratios = [row[key] for row in rows if key in row]
    return {
        "unit": "words" if remote else "tokens",
        "cap": 900 if remote else force_gpu.SEED_CAP_TOKENS,
        "pairs": len(rows),
        "pairs_truncated": sum(1 for row in rows if row.get("truncated")),
        "max_log10_ratio_before_cut": max(ratios, default=0.0),
        "pairs_over_0_04": sum(1 for ratio in ratios if ratio > 0.04),
    }


def run_family(
    family: str,
    pairs: Sequence[ForcePair],
    args: argparse.Namespace,
) -> dict[str, Any]:
    is_remote = family == "haiku-4-5"
    governor = force_gpu.Governor(rest_ratio=args.rest_ratio)
    ledger = force_remote.Ledger(ceiling_usd=args.ceiling_usd) if is_remote else None
    DERIVED.mkdir(parents=True, exist_ok=True)
    cache = Checkpoint(DERIVED / f"f1-{family}.jsonl")

    # Both sides of every pair are cut to the SAME token count before anything is generated.
    # §79 matched pairs on the source chapter's word count and never on the excerpt's: 23 of 281
    # pairs differ by more than 0.04 in |log10 word ratio| and one differs by 2.85x. A fixed
    # prompt ceiling would cut the longer side only, and a force that read seed length would
    # score on that. The cut is per pair, symmetric, and recorded.
    live: list[ForcePair] = []
    seed_budget: list[dict[str, Any]] = []
    for pair in pairs:
        if is_remote:
            high, low, record = force_remote.symmetric_seeds_by_words(
                pair.high, pair.low, cap=args.seed_words
            )
        else:
            high, low, record = force_gpu.symmetric_seeds(family, pair.high, pair.low)
        live.append(ForcePair(
            pair_id=pair.pair_id, stratum=pair.stratum, high=high, low=low,
            high_meta=pair.high_meta, low_meta=pair.low_meta,
        ))
        seed_budget.append({"pair_id": pair.pair_id, **record})

    # Stratified, not head-sliced: `load_pairs` returns aligned then crossed, so `live[:n]`
    # would draw both controls entirely from `aligned`.
    placebo = placebo_pairs(stratified_subsample(live, args.placebo))
    sham = sham_pairs(stratified_subsample(live, args.sham))
    # **Controls are generated before the corpus, not after it.** §1.3 rides the placebo and the
    # sham on every force, and `arm_status` makes an unscreened control disqualifying — so an arm
    # that spends its budget on pairs and runs out before the sham reports NOT_SCREENABLE with
    # nothing to show for the spend. Buying the controls first means a shortfall trims *n*
    # instead, which `DEGRADED_STRATUM` already handles and which leaves a certified reading on
    # whatever the budget did reach. The placebo is free either way: its sides are the high
    # sides, so it dedups to nothing.
    try:
        scores, context = score_pairs(
            sham + placebo + live, family, cache, governor,
            k=args.k, max_new_tokens=args.tokens, remote=ledger, workers=args.workers,
            from_cache_only=args.from_cache_only,
        )
    except force_remote.CeilingReached as stop:  # pragma: no cover - now handled per seed
        # The ceiling is a stop, not an exception to swallow. Everything bought is on disk and a
        # resumed run replays it; what this refuses to do is report a partial corpus as a result.
        return {
            "family": force_remote.provenance(args.remote_model),
            "status": "NOT_RUN",
            "why": str(stop),
            "ledger": ledger.report() if ledger else None,
            "cache": cache.provenance(),
        }
    if not scores:
        return {"family": force_gpu.family_provenance(family, "base"),
                "status": "NOT_SCREENABLE", "why": context.get("why", "no scores")}

    covariate = context.pop("covariate")
    report: dict[str, Any] = {
        "family": (
            force_remote.provenance(args.remote_model) if is_remote
            else force_gpu.family_provenance(family, "base")
        ),
        "context": context,
        "governor": governor.report(),
        "cache": cache.provenance(),
        "ledger": ledger.report() if ledger else None,
        "pilot_corrections": PILOT_CORRECTIONS,
        "seed_budget": _seed_budget_summary(seed_budget, remote=is_remote),
    }

    # The placebo first, because a failed arithmetic check means nothing below it is about
    # prose. Its effect is the largest absolute difference between two byte-identical sides.
    placebo_effect = 0.0
    for pair in placebo:
        row = scores.get(pair.pair_id)
        if row:
            placebo_effect = max(placebo_effect, abs(row["high"] - row["low"]))
    if is_remote:
        # §1.7's pre-registered branch. No seed parameter exists on this transport, so
        # byte-identical sides cannot produce byte-identical outputs and the placebo cannot be
        # the exact arithmetic check §89.4 made it. It is read the way a sham is read instead:
        # identical sides must yield an agreement whose interval contains 0.50. Strictly weaker,
        # and labelled rather than quietly substituted.
        placebo_read = sham_verdict("placebo_identical", *pair_agreement(scores, placebo))
        if placebo_read.get("status") == "NOT_SCREENABLE":
            placebo_read["why"] = (
                "the placebo decided nothing: every pair tied. On a non-deterministic transport "
                "that means the two sides were not sampled independently, so the equivalence "
                "test §1.7 declared had nothing to measure."
            )
        report["placebo_identical"] = {
            **placebo_read,
            "kind": "equivalence",
            "why_downgraded": "no determinism on the remote transport; §1.7's declared branch",
            "observed_max_abs_effect": placebo_effect,
        }
    else:
        report["placebo_identical"] = control_verdict(
            "placebo_identical", placebo_effect, tolerance=args.placebo_tolerance, kind="exact"
        )

    sham_wins, sham_decided, sham_total = pair_agreement(scores, sham)
    # The sham is reported and explicitly refused as a certification: see
    # SHAM_IS_INVISIBLE_TO_THIS_SPACE. Whatever agreement it shows is noise on identical inputs.
    report["rewhitespace_sham"] = {
        **sham_verdict("rewhitespace_sham", sham_wins, sham_decided, sham_total),
        "status": "NOT_SCREENABLE",
        "why": "F1's windows join words with a single space, so no window contains a newline, "
               "and `rewhitespace` changes only newlines and intra-line spacing. Measured: 100 "
               "of 100 sham pairs produce byte-identical feature rows. This control perturbs "
               "nothing this feature space can see and certifies nothing.",
        "measured_identical_feature_rows": "100/100",
    }

    strata: dict[str, list[ForcePair]] = {
        "aligned": [p for p in live if p.stratum == "aligned"],
        "crossed": [p for p in live if p.stratum == "crossed"],
        **view_gap_halves(live),
    }
    residual = residual_scores(scores, covariate)
    for label, members in strata.items():
        if not members:
            continue
        # Every stratum is binding for the purpose of the refuting floor. The halves were
        # exempted, so they bypassed MIN_REFUTING_N and emitted FAILs at n=28 and n=37 — the
        # same pairs that are refused a refutation when read whole as `crossed`.
        binding = True
        raw = verdict(
            label, *pair_agreement(scores, members),
            n_before_drops=len(members), binding=binding,
        )
        adjusted = verdict(
            label, *pair_agreement(residual, members),
            n_before_drops=len(members), binding=binding,
        )
        # Both readings print. The bar is declared on the residual, and saying which is which
        # in the file rather than in a document is what keeps the two from being swapped later.
        report[label] = {**adjusted, "reading": "residual (BAR)"}
        report[f"{label}__raw_DIAGNOSTIC"] = {**raw, "reading": "raw (DIAGNOSTIC)"}

    # **Live sides only.** `scores` carries the placebo and sham sides too, and both controls are
    # built from the HIGH side — so the fit was run over material that was two-thirds re-used
    # (168 of 578 rows were controls, 105 were exact duplicates of other rows) while publishing
    # `n: 578` as though it were a sample size.
    live_ids = {pair.pair_id for pair in live}
    flat_live = {
        f"{p}|{s}": v for p, row in scores.items() if p in live_ids for s, v in row.items()
    }
    report["inverted_u_alternative"] = inverted_u(covariate, flat_live)
    report["half_life_secondary_DIAGNOSTIC"] = {
        "median": round(statistics.median(
            [v for v in context["half_lives"].values() if math.isfinite(v)]
        ), 4) if any(math.isfinite(v) for v in context["half_lives"].values()) else None,
        "finite_share": round(statistics.fmean(
            [1.0 if math.isfinite(v) else 0.0 for v in context["half_lives"].values()]
        ), 4) if context["half_lives"] else None,
        "note": "secondary and diagnostic; the primary read is the crossover index",
    }
    context.pop("half_lives", None)
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

    per_family: dict[str, dict[str, Any]] = {}
    for family in args.families:
        per_family[family] = run_family(family, pairs, args)
        # Only the local families hold weights. `force_gpu.free()` imports torch, which the
        # remote transport neither has nor needs — calling it unconditionally is what killed the
        # first Haiku smoke run *after* it had finished the science and written nothing.
        if family in FAMILIES:
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
        track="F1",
        pre_registration_track=PRE_REGISTRATION,
        pairs=len(pairs),
        stratum_sizes=sizes,
        attainability=attainability_table(sizes),
        per_family=per_family,
        combined=combined,
        force_verdict=headline["verdict"],
        force_verdict_detail=headline,
        reading=(
            "F1 clears both binding strata on both families: the model's generation field bends "
            "toward the higher-converting side, measured with no question asked"
            if headline["verdict"] == "PASS"
            else "F1 does not clear both binding strata; the per-family and per-stratum rows "
                 "below say which reading failed and in which of the declared ways"
        ),
    )


def selftest() -> int:
    """Trajectory arithmetic on constructed inputs. No GPU, no corpus."""
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    text = " ".join(f"word{i}" for i in range(250))
    got = windows(text)
    check(len(got) == (250 - WINDOW_WORDS) // STRIDE_WORDS + 1, f"window count {len(got)}")
    check(all(len(w.split()) == WINDOW_WORDS for w in got), "windows must be equal length")
    check(windows("short text") == ["short text"], "a short text is one window")

    check("words" not in ACTIVE, "`words` must be excluded from the F1 space")

    # A trajectory that starts at the seed and walks to the median crosses in the middle.
    to_seed = [0.0, 1.0, 2.0, 3.0, 4.0]
    to_median = [4.0, 3.0, 2.0, 1.0, 0.0]
    index, censored = crossover(to_seed, to_median)
    check((index, censored) == (3, False), f"crossover {index},{censored}")
    index, censored = crossover([0.0, 0.1], [5.0, 5.0])
    check((index, censored) == (2, True), "a never-crossing trajectory must be censored")

    # `r_w` is a *ratio*, so a decay needs the two distances to move against each other: a
    # constant distance-to-seed leaves r pinned at 1 whatever the median does. The first version
    # of this check held to_seed at zero and read `inf`, which was the check being wrong rather
    # than the fit.
    life = half_life([0.1, 0.5, 1.0, 2.0], [4.0, 3.0, 2.0, 1.0])
    check(math.isfinite(life) and life > 0, f"half-life must be finite and positive, got {life}")
    check(math.isinf(half_life([0.0] * 4, [4.0, 2.0, 1.0, 0.5])), "a flat ratio must not decay")
    check(math.isnan(half_life([1.0], [1.0])), "too few points must refuse, not return zero")

    # The residual adjustment strips a covariate that explains everything.
    scores = {f"p{i}": {"high": 2.0 * i + 1, "low": 2.0 * i + 3} for i in range(8)}
    flat_cov: dict[str, float] = {}
    for i in range(8):
        flat_cov[f"p{i}|high"] = float(i)
        flat_cov[f"p{i}|low"] = float(i) + 1
    adjusted = residual_scores(scores, flat_cov)
    check(len(adjusted) == 8, "every pair must survive the adjustment")
    check(
        max(abs(v) for row in adjusted.values() for v in row.values()) < 1e-6,
        "a covariate that explains everything must leave nothing",
    )

    up = inverted_u({f"k{i}": float(i) for i in range(20)},
                    {f"k{i}": -((i - 10) ** 2) for i in range(20)})
    check(up["interior_peak"], "a true inverted U must be detected")
    down = inverted_u({f"k{i}": float(i) for i in range(20)},
                      {f"k{i}": 3.0 * i for i in range(20)})
    check(not down["interior_peak"], "a straight line must not read as an inverted U")

    for message in failures:
        print(f"FAIL {message}")
    print(f"register_halflife selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--families", nargs="+", default=list(FAMILIES))
    parser.add_argument("--pairs", type=int, default=0, help="cap per stratum; 0 = full corpus")
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--tokens", type=int, default=MAX_NEW_TOKENS)
    parser.add_argument("--sham", type=int, default=SHAM_PAIRS)
    parser.add_argument("--placebo", type=int, default=24)
    parser.add_argument("--placebo-tolerance", type=float, default=0.0)
    parser.add_argument("--rest-ratio", type=float, default=force_gpu.DEFAULT_REST_RATIO)
    parser.add_argument("--from-cache-only", action="store_true",
                        help="re-score what a previous run banked and buy nothing")
    parser.add_argument("--remote-model", default="claude-haiku-4-5")
    parser.add_argument("--workers", type=int, default=force_remote.DEFAULT_WORKERS,
                        help="concurrent SEEDS on the remote transport; replicates inside a "
                             "seed stay sequential so the 26k prefix is cached")
    parser.add_argument("--ceiling-usd", type=float,
                        default=force_remote.DEFAULT_CEILING_USD)
    parser.add_argument("--seed-words", type=int, default=900,
                        help="symmetric per-pair seed cap in WORDS on the remote transport")
    parser.add_argument("--out", default=str(RESULTS / "force-f1.json"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    # One remote arm at a time. Three copies of F1 once raced the same cache and bought 108
    # seeds twice; the lock is what makes "relaunch" mean replace rather than add.
    if any(family == "haiku-4-5" for family in args.families):
        DERIVED.mkdir(parents=True, exist_ok=True)
        with force_remote.SingleRun(DERIVED / "f1-remote.lock", label="F1 remote arm"):
            report = run(args)
    else:
        report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["combined"], indent=2))
    print(f"\nF1 verdict: {report['force_verdict']}\n{report['reading']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
