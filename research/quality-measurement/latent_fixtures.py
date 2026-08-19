"""The paired fixture families Track P scores, and the exact test that scores them.

Every family in this file is a **paired** design: one scene, two texts, differing by one named
thing. That is not a convenience — it is what makes a 4B-scale probe measurable at all on eight
scenes. An unpaired classifier over 16 texts in 2,560 dimensions separates anything; a paired
one has to find a direction that transfers to a scene it has never seen, and the null for that
is exact rather than asymptotic.

**The statistic, and why it is a sign count rather than an AUC.** For each scene the probe is
fitted on every *other* scene and asked one question about the held-out pair: did it score the
positive side above the negative side? The statistic is `k`, the number of scenes ordered
correctly, out of `G`. Its null distribution is not assumed — :func:`exact_flip_null` enumerates
all `2**G` within-pair label flips, re-runs the whole leave-one-scene-out pipeline under each,
and reports the fraction reaching `k` or better. At `G = 8` that is 256 refits and the smallest
attainable p-value is 0.0039; at `G = 10`, 1,024 refits and 0.0010. A sampled null would be
strictly worse and there is no reason to take one.

**Why a paired sign count is immune to the failure that voided §83 and §85's twin arms.** Those
arms void on *positional* bias: the panel is shown two texts in an order and answers the slot.
A probe scores one text at a time and never sees a pair, so there is no slot to prefer. The
pairing here happens after scoring, in arithmetic we control.

**Three of the families are built to fail.** `repair_placebo` returned byte-identical text in
§85, so its two sides are the same string and its label is unlearnable by construction: a probe
that "separates" it has a bug, not a finding. `states_tea_vs_sober` is §83's placebo — two fair
copies of one scene differing by an inert clause and a sampling draw — and separating it means
the probe reads draw noise, which would make every other state arm uninterpretable.
`rewhitespace_vs_original` is §78.1's formatting sham. These are the floor, and they are scored
before anything else is read.

**The surface baseline is steelmanned on purpose.** `features()` from `authorship_tells` is the
z-scored space the directive names as P0, and on one family it is blind *by construction of the
feature list* rather than because the information is absent: `strip_system` deletes the
`[STATUS]` line, which is the only place `stat_flatten` edits, and no feature counts digits
anyway. Reporting "the probe beat P0 on stat_flatten" from that would be an artifact of an
omission we control. So :data:`P0_PLUS` adds the three features that would see it, and the
pre-registered rule is that an internal claim must beat **both** baselines.

Stdlib plus numpy only, and no `litharness` import, so this runs under either interpreter — the
activation side of Track P needs the MirrorBench venv (torch), and the fixtures and P0 must be
readable from the same process. See RUNBOOK.md.
"""

from __future__ import annotations

import json
import random
import re
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import product
from math import comb
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import (  # noqa: E402
    filler_inject,
    interiority_deplete_matched,
    interiority_strip,
    rewhitespace,
    stat_flatten,
)
from authorship_tells import FEATURE_NAMES, features, strip_system  # noqa: E402

RESULTS = HERE / "results"
CORPORA = HERE / "corpora"

#: §83's retells and §85's repairs, both written by `claude-opus-5` over the same eight scenes.
STATES_JSONL = RESULTS / "writer-states-gen-raw.jsonl"
REPAIRS_JSONL = RESULTS / "repair-gen-raw.jsonl"
#: This system's own drafted prose, committed (`corpus_leak_audit.OURS`), so family C needs no
#: `litharness` import and no `toll.db`.
SCENES_JSON = CORPORA / "toll-scenes.json"

#: §79's matched-pair benchmark corpus — **third-party RoyalRoad prose**, gitignored, and a build
#: product of `taste_benchmark.py --build`. It lives in the main checkout rather than in a
#: worktree, so both locations are tried and neither is created.
#:
#: **Nothing derived from this file may carry its text.** The activation dump keys on digests, the
#: results JSON carries `pair_id` and verdicts only, and `corpus_leak_audit` refuses a committed
#: `.npz` outright. That chain is the reason this family can be measured at all in a public repo.
BENCHMARK_JSON_CANDIDATES = (
    CORPORA / "taste-benchmark.json",
    Path("C:/DEV/LitHarness/research/quality-measurement/corpora/taste-benchmark.json"),
)

#: §79's two strata, never averaged. In `aligned` every prose-blind popularity covariate points
#: at the conversion label; in `crossed` every one points away from it. A judge reading prose
#: agrees with the label in both; a judge proxying popularity agrees in one and disagrees in the
#: other, and their mean is 0.5 — which is why `PRE_REGISTRATION["never_average"]` exists in
#: `taste_benchmark.py` and why the statistic here is a minimum across strata rather than a mean.
CONVERSION_STRATA = ("aligned", "crossed")


# ------------------------------------------------------------------------------- the corpus


@dataclass(frozen=True)
class Pair:
    """One scene's two texts. `positive` is the arm named first in the family's label."""

    family: str
    scene: str
    positive: str
    negative: str
    positive_arm: str
    negative_arm: str


def _rows(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def originals() -> dict[str, str]:
    """The drafted scenes, by unit id. Ten of them; the generated fixtures cover the first eight."""
    payload = json.loads(SCENES_JSON.read_text(encoding="utf-8"))
    return {scene["unit_id"]: scene["text"] for scene in payload["scenes"]}


def _generated(path: Path, arm_key: str) -> dict[tuple[str, str], str]:
    """Non-refused generations keyed by (scene, arm). Refusals carry empty text and are dropped."""
    out: dict[tuple[str, str], str] = {}
    for row in _rows(path):
        if row.get("refused") or not row.get("text", "").strip():
            continue
        out[(row["scene"], row[arm_key])] = row["text"]
    return out


def states() -> dict[tuple[str, str], str]:
    """§83's 32 near-twin retells, keyed by (scene, state)."""
    return _generated(STATES_JSONL, "state")


def repairs() -> dict[tuple[str, str], str]:
    """§85's 32 certified revisions and exemplar retells, keyed by (scene, arm)."""
    return _generated(REPAIRS_JSONL, "arm")


# ------------------------------------------------------------------------------- the families


def _pairs_from(
    family: str,
    left: dict[tuple[str, str], str],
    right: dict[tuple[str, str], str],
    positive_arm: str,
    negative_arm: str,
) -> list[Pair]:
    scenes = sorted(
        {scene for scene, arm in left if arm == positive_arm}
        & {scene for scene, arm in right if arm == negative_arm}
    )
    return [
        Pair(family, scene, left[(scene, positive_arm)], right[(scene, negative_arm)],
             positive_arm, negative_arm)
        for scene in scenes
    ]


def _transform_family(
    family: str,
    source: dict[str, str],
    positive: Callable[[str, float], str],
    negative: Callable[[str, float], str] | None,
    *,
    strength: float = 1.0,
) -> list[Pair]:
    """A manufactured family: the transform against the original, or against a matched transform."""
    out: list[Pair] = []
    for scene in sorted(source, key=lambda s: (len(s), s)):
        text = source[scene]
        neg = negative(text, strength) if negative is not None else text
        out.append(
            Pair(family, scene, positive(text, strength), neg,
                 positive.__name__, negative.__name__ if negative else "original")
        )
    return out


def build_families() -> dict[str, list[Pair]]:
    """Every paired family constructible from committed fixtures, with no network and no db.

    Ordering is deliberate: the three floors first, so a reader who scans the output meets the
    controls before any arm that could be read as a result.
    """
    src = originals()
    st = states()
    rp = repairs()
    orig_as_arms = {(scene, "original"): text for scene, text in src.items()}

    fams: dict[str, list[Pair]] = {
        # --- floors. Any separation here invalidates the arms below it.
        "placebo_identical": _pairs_from("placebo_identical", rp, orig_as_arms,
                                         "repair_placebo", "original"),
        "states_tea_vs_sober": _pairs_from("states_tea_vs_sober", st, st, "tea", "sober"),
        "rewhitespace_sham": _transform_family("rewhitespace_sham", src, rewhitespace, None),
        # --- the panel-BLIND arm (§81). Ground truth manufactured, three values per scene.
        "stat_flatten": _transform_family("stat_flatten", src, stat_flatten, None),
        # --- the panel's one clean interval (§85) and its damage-direction twin (§81).
        "repair_interiority": _pairs_from("repair_interiority", rp, orig_as_arms,
                                          "repair_interiority", "original"),
        "interiority_strip_matched": _transform_family(
            "interiority_strip_matched", src, interiority_strip, interiority_deplete_matched),
        # --- the near-twin states the panel answered a side on (§83).
        "states_drunk_vs_sober": _pairs_from("states_drunk_vs_sober", st, st, "drunk", "sober"),
        "states_trip_vs_sober": _pairs_from("states_trip_vs_sober", st, st, "trip", "sober"),
        # --- certified single-variable repair the panel could not read (§85, bias 0.6949).
        "repair_emdash": _pairs_from("repair_emdash", rp, orig_as_arms,
                                     "repair_emdash", "original"),
        # --- the demonstrated-voice lever (§85), against the sober retell it is measured from.
        "exemplar_vs_sober": _pairs_from("exemplar_vs_sober", rp, st, "exemplar", "sober"),
        # --- a gross-damage rung, present so the ladder has a rung P0 must win.
        "filler_inject": _transform_family("filler_inject", src, filler_inject, None),
    }
    return {name: pairs for name, pairs in fams.items() if pairs}


def benchmark_path() -> Path | None:
    """The §79 corpus, if this machine has it. Absent is a normal state, not an error."""
    return next((path for path in BENCHMARK_JSON_CANDIDATES if path.is_file()), None)


def conversion_families() -> dict[str, list[Pair]]:
    """§79's conversion pairs, one family per stratum, or nothing if the corpus is absent.

    The positive side is the **higher-converting** story, so `k / G` is literally agreement with
    the external label — the same quantity §79's 0.52 bar is denominated in, which is what makes
    this the one family in the file that a direction may be read from at all.

    The group is the pair. §79 selects pairs disjoint at story level, so leaving one out holds out
    two whole stories and there is no near-duplicate to straddle a split.
    """
    path = benchmark_path()
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[Pair]] = {}
    for stratum in CONVERSION_STRATA:
        rows = payload.get(f"axis_conversion_{stratum}", [])
        family = f"conversion_{stratum}"
        out[family] = [
            Pair(family, row["pair_id"], row["high"], row["low"], "rr_high", "rr_low")
            for row in rows
        ]
    return {name: pairs for name, pairs in out.items() if pairs}


#: Families whose two sides are the same string, or differ only by formatting or a sampling
#: draw. They are scored first and nothing above them is read if one of them separates.
FLOOR_FAMILIES = ("placebo_identical", "states_tea_vs_sober", "rewhitespace_sham")

#: The one family whose *identity* is the point. Everywhere else a byte-identical pair is a
#: scene the transform found nothing to do to, and it is dropped with the drop recorded — §81
#: reports `interiority_vs_matched` at nine passages out of ten for exactly this reason, and a
#: scene contributing a guaranteed-unscoreable delta would drag `k` down as if the probe had
#: failed on it.
IDENTITY_FAMILY = "placebo_identical"


def drop_degenerate(family: str, pairs: list[Pair]) -> tuple[list[Pair], list[str]]:
    """Remove pairs whose two sides are the same string, and name the scenes removed."""
    if family == IDENTITY_FAMILY:
        return pairs, []
    kept = [pair for pair in pairs if pair.positive != pair.negative]
    dropped = [pair.scene for pair in pairs if pair.positive == pair.negative]
    return kept, dropped


# ------------------------------------------------------------------------------- the baseline

_DIGIT = re.compile(r"\d")
_QUESTION_SLOT = re.compile(r"\?")


def p0_features(text: str, *, steelman: bool) -> dict[str, float]:
    """P0's vector for one text.

    The plain form is `authorship_tells.features` over system-stripped prose, which is the
    z-scored space §83 and §85 measure register movement in — the directive's P0.

    The steelman adds the three counts that would see `stat_flatten`, measured on the **unstripped**
    text. `strip_system` deletes the `[STATUS]` line and that line is the only thing the transform
    edits, so without these a probe beating P0 on that family would be beating an omission of ours
    rather than a limit of surface measurement. They are reported as a separate baseline, never
    merged into the first, because §83's and §85's centroid numbers are in the plain space and a
    silently widened feature set would make those incomparable.
    """
    row = dict(features(strip_system(text)))
    if steelman:
        words = max(len(text.split()), 1)
        system_lines = [line for line in text.splitlines() if re.search(r"\[[A-Z][A-Z ]+\]", line)]
        system_text = "\n".join(system_lines)
        row["digit_per_1k"] = 1000.0 * len(_DIGIT.findall(text)) / words
        row["system_digit_count"] = float(len(_DIGIT.findall(system_text)))
        row["system_slot_count"] = float(len(_QUESTION_SLOT.findall(system_text)))
    return row


P0_NAMES: tuple[str, ...] = FEATURE_NAMES
P0_PLUS_NAMES: tuple[str, ...] = (*FEATURE_NAMES, "digit_per_1k", "system_digit_count",
                                  "system_slot_count")


# ------------------------------------------------------------------------------- the test


def gram(deltas: list[list[float]]) -> list[list[float]]:
    """The `G x G` matrix of inner products between scenes' difference vectors.

    **This is the whole test, and the reason the exhaustive null is affordable.** With the
    estimator fixed to a mean of paired differences, leave-one-scene-out has a closed form. Let
    `S` be the sum of every difference vector; the direction fitted without scene *i* is
    proportional to `S - d_i`, and normalising it cannot change a sign, so the held-out scene is
    ordered correctly exactly when

        (S - d_i) . d_i > 0

    Under a flip vector `e` in {+1,-1}^G the same quantity is `e_i (M e)_i - M_ii` where `M` is
    this matrix. So every one of the `2**G` re-runs is a `G x G` matrix-vector product rather
    than a refit over 2,560 dimensions: at ten scenes that is 1,024 products of a 10x10 matrix,
    which is milliseconds, against the hours a literal refit costs. The numbers are identical by
    algebra rather than by approximation, and `tests/test_latent_probe.py` asserts it against the
    literal implementation on random data.
    """
    width = len(deltas)
    return [
        [sum(a * b for a, b in zip(deltas[i], deltas[j], strict=True)) for j in range(width)]
        for i in range(width)
    ]


def signs_from_gram(
    matrix: list[list[float]], flips: tuple[int, ...] | None = None
) -> list[int]:
    """Held-out orderings under one flip vector. See :func:`gram` for the algebra."""
    size = len(matrix)
    eps = flips or (1,) * size
    out: list[int] = []
    for i in range(size):
        projected = sum(eps[j] * matrix[i][j] for j in range(size))
        out.append(1 if eps[i] * projected - matrix[i][i] > 0 else 0)
    return out


def paired_direction(deltas: list[list[float]]) -> list[float]:
    """The mean difference vector, scaled to unit length. The whole estimator.

    Fourteen training points in 2,560 dimensions do not support a fitted classifier with
    hyperparameters; every choice would be a fork in the path and none could be validated on
    eight scenes. A mean of paired differences has no hyperparameter to tune, which is the only
    reason a held-out sign test on it means what it appears to mean.
    """
    width = len(deltas[0])
    mean = [statistics.fmean(row[i] for row in deltas) for i in range(width)]
    norm = sum(value * value for value in mean) ** 0.5
    return [value / norm for value in mean] if norm > 0 else mean


def loso_signs(deltas: list[list[float]], flips: tuple[int, ...] | None = None) -> list[int]:
    """Leave-one-scene-out: is the held-out difference aligned with the other scenes' direction?

    `flips` relabels scene *s* by multiplying its difference vector by ±1 — the exact null this
    design admits, since swapping which side of a pair is called positive is the only relabelling
    that respects the pairing.
    """
    signs = flips or (1,) * len(deltas)
    flipped = [[sign * value for value in row] for sign, row in zip(signs, deltas, strict=True)]
    out: list[int] = []
    for held in range(len(flipped)):
        train = [row for index, row in enumerate(flipped) if index != held]
        direction = paired_direction(train)
        score = sum(a * b for a, b in zip(direction, flipped[held], strict=True))
        # A score of exactly 0.0 is not a failure and not a success: it is a pair the readout
        # cannot order at all, which on a byte-identical pair is the only honest answer. It is
        # counted as a miss so that `k` never rewards an unscoreable pair, and
        # `unscoreable_pairs` reports how many there were beside every `k`.
        out.append(1 if score > 0 else 0)
    return out


def unscoreable(deltas: list[list[float]]) -> int:
    """Pairs whose difference vector is exactly zero, so no direction can order them."""
    return sum(1 for row in deltas if not any(row))


def clopper_pearson(successes: int, trials: int, *, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided interval for `k / G`, by bisection on the binomial tail.

    Used only where the pairs are genuinely independent — §79's conversion strata, which are
    disjoint at story level. It is **not** used on the manufactured families, where eight or ten
    variants of the same ten scenes are anything but independent and the flip null is the honest
    instrument. Bisection rather than a beta quantile so the module keeps its stdlib-only promise.
    """
    def tail(probability: float, at_least: int) -> float:
        return sum(
            comb(trials, i) * probability**i * (1 - probability) ** (trials - i)
            for i in range(at_least, trials + 1)
        )

    def bisect(target: float, at_least: int) -> float:
        # `tail` rises monotonically in `probability` for a fixed `at_least`, so BOTH bounds
        # bisect in the same direction. An earlier version flipped the comparison for the upper
        # bound and returned 0.0 for it — a wrong number rather than an error, which is the
        # failure mode this repository keeps having to catch.
        lower, upper = 0.0, 1.0
        for _ in range(60):
            middle = (lower + upper) / 2
            if tail(middle, at_least) < target:
                lower = middle
            else:
                upper = middle
        return round((lower + upper) / 2, 4)

    low = 0.0 if successes == 0 else bisect(alpha / 2, successes)
    high = 1.0 if successes == trials else bisect(1 - alpha / 2, successes + 1)
    return low, high


def sampled_flip_null(
    deltas: list[list[float]], *, draws: int = 20000, seed: int = 20260819
) -> dict[str, Any]:
    """The flip null where `2**G` is out of reach, by sampling instead of enumerating.

    §79's strata run 21 and 25 pairs, so exhaustive enumeration would be 2 million and 34 million
    re-runs. The estimator and the statistic are unchanged; only the null's coverage is. The
    Monte-Carlo standard error is reported beside the p-value so a reader can see how much of the
    number is sampling — a sampled p of 0.0 is reported as `< 1/draws`, never as zero.
    """
    matrix = gram(deltas)
    groups = len(deltas)
    observed = sum(signs_from_gram(matrix))
    rng = random.Random(seed)
    at_least = 0
    for _ in range(draws):
        flips = tuple(rng.choice((1, -1)) for _ in range(groups))
        if sum(signs_from_gram(matrix, flips)) >= observed:
            at_least += 1
    proportion = at_least / draws
    low, high = clopper_pearson(observed, groups)
    return {
        "groups": groups,
        "k": observed,
        "agreement": round(observed / groups, 4),
        "agreement_interval": [low, high],
        "p_sampled": round(proportion, 6),
        "p_note": None if at_least else f"no draw of {draws} reached k; p < {1 / draws}",
        "draws": draws,
        "mc_stderr": round((proportion * (1 - proportion) / draws) ** 0.5, 6),
        "seed": seed,
    }


def exact_flip_null(deltas: list[list[float]]) -> dict[str, Any]:
    """Enumerate every within-pair label flip and report where the observed `k` falls.

    Exhaustive rather than sampled: `2**G` is 256 at eight scenes and 1,024 at ten, so the null
    is the whole distribution and the p-value is exact. The observed assignment is one of the
    enumerated ones and is counted, which is what keeps the smallest attainable p at `1 / 2**G`
    rather than zero.
    """
    matrix = gram(deltas)
    groups = len(deltas)
    observed = sum(signs_from_gram(matrix))
    at_least = sum(
        1 for flips in product((1, -1), repeat=groups)
        if sum(signs_from_gram(matrix, flips)) >= observed
    )
    return {
        "groups": groups,
        "k": observed,
        "p_exact": round(at_least / 2 ** groups, 6),
        "null_size": 2 ** groups,
        "smallest_attainable_p": round(1.0 / 2 ** groups, 6),
    }
