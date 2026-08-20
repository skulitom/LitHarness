"""The shared validation harness every force competes on. See plan/force-program.md.

A **force** is a candidate valence channel: a quantity computed *from what a passage does to a
model*, obtained without asking any model a question and without asking any human anything. The
programme's whole claim rests on forces being held to one standard, so the standard lives here
rather than being restated — and re-decided — inside each track.

**Why a separate module rather than a package under `src/`.** Same reason as every other file in
this directory: nothing here is imported by `litharness`, nothing is gated on it, and it must run
under the MirrorBench interpreter, which has torch and does not have the package. It imports only
stdlib plus two siblings (`latent_fixtures.clopper_pearson`, `ablate.rewhitespace`), and it never
imports torch itself — a force that needs a GPU builds its own inference and hands this module
numbers.

**The three things this module refuses to let a track do.**

1. *Declare a bar it has not checked.* :func:`attainability` computes, for an n, the count needed
   for the 0.52 point bar and the count needed for a Clopper-Pearson lower bound clear of 0.50,
   and every result file prints that table beside its verdict. Seven declarations in this
   repository named a quantity that could not do what it said (§89's rulebook), and the check is
   what caught them.
2. *Fold a refusal into a pass or a fail.* :data:`STATES` are verdicts in their own right.
   `INERT_GENERATOR` is §90.5's, `NOT_SCREENABLE` is §94.6's, `INSUFFICIENT_N` is §1.2's, and
   none of them is a NULL that can be quoted as "the force does not work".
3. *Run without controls.* :func:`placebo_pairs` and :func:`sham_pairs` are built from the same
   corpus rows a force is about to read, so an arm that skips them has to skip them visibly.

**The exactness of the placebo is bought rather than hoped for.** :func:`text_seed` derives every
stochastic step's RNG seed from the digest of the text being acted on, so byte-identical inputs
produce byte-identical outputs and the placebo difference is `0.000000`. That is §89.4's
arithmetic-check role, which a placebo whose sides merely *look* the same cannot play. Whether
the hardware honours it is measured before it is assumed — `determinism_probe.py`.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import rewhitespace  # noqa: E402
from latent_fixtures import clopper_pearson  # noqa: E402

CORPUS = HERE / "corpora" / "taste-benchmark.json"
SIDECAR = HERE / "results" / "taste-benchmark-corpus.json"
RESULTS = HERE / "results"

#: §79's point bar. Not this programme's to move.
POINT_BAR = 0.52
ALPHA = 0.05

#: §1.2's rule, declared numerically before any force ran so that it cannot be shopped for
#: later: a stratum whose *interval* bar demands more than this rate may return INSUFFICIENT_N
#: instead of FAIL when its point estimate clears. At the programme's n this admits the two
#: `crossed` halves (0.6324, 0.6377), F3 (0.7500) and FX's pilot (1.0000), and admits neither
#: `aligned` (0.5903) nor `crossed` (0.5912) — the two strata that decide whether a force passes.
INSUFFICIENT_N_ABOVE = 0.60

#: Ties are excluded from the interval and counted, which is §89.1's unit rule rather than §77's
#: `half_win`: a rate resting on few decided comparisons is the failure §87.3 catalogued (1.000
#: on eleven decisions). Both readings print; the bar binds on the decided-pairs interval.
MIN_DECIDED_SHARE = 0.90

#: The controls §1.3 rides on every force, named so that `arm_status` can refuse an arm that
#: simply omitted one. Absence is the failure mode: a missing control looks like a clean run.
REQUIRED_CONTROLS = ("placebo_identical", "rewhitespace_sham")

#: The two pinned local families. §94.5's lesson as a constant: one family's artifact reads as a
#: finding until a second family refuses it.
#:
#: **Each family carries two heads, and the split is `surprisal.py`'s argument rather than a
#: convenience.** The `base` head is the pretrained checkpoint, because *"an instruction-tuned
#: model's distribution is shaped by preference training toward assistant register, which is a
#: different distribution from 'what does published fiction do next'"* — and F1, F2 and F3 are
#: all statements about that distribution. The `chat` head is the instruction-tuned checkpoint,
#: used by exactly one track: FX, whose telephone chain needs a model that can be *told* to
#: retell. Which head an arm uses is recorded in its result file, because the two are different
#: instruments and a run that does not say which one it used cannot be compared with anything.
FAMILIES: dict[str, dict[str, str]] = {
    "gemma-3-4b": {
        "lineage": "google/gemma-3",
        "base": "google/gemma-3-4b-pt",
        "base_revision": "cc012e0a6d0787b4adcc0fa2c4da74402494554d",
        "chat": "google/gemma-3-4b-it",
        "chat_revision": "093f9f388b31de276ce2de164bdc2081324b9767",
    },
    # **Qwen2.5-3B was retired for Qwen3.5-4B on 2026-08-21, and the architectural argument for
    # the swap did not survive measurement.** Recorded that way round because the prediction is
    # the instructive part.
    #
    # Predicted from the configs: Qwen2.5-3B runs full attention on all 36 layers where
    # Qwen3.5-4B is hybrid like gemma-3 — 8 full layers of 32, same 16 query heads, position
    # ceiling 262,144 rather than 32,768 — so the newer model should have bought head-room on
    # exactly the axis that binds every teacher-forced budget here.
    #
    # Measured on this card, single pass, prefix plus target:
    #
    #     tokens     Qwen2.5-3B (retired)      Qwen3.5-4B (pinned)
    #      7,801     14.7 GiB    2.2 s         17.1 GiB    3.2 s
    #     11,701     25.4 GiB   43.5 s         28.1 GiB   62.4 s
    #     15,601     40.2 GiB  285.5 s         43.1 GiB  183.6 s
    #     19,501     OOM                       (23,401 OOM)
    #
    # **It is worse at every length we can reach, by about 2.5 GiB.** Peak is dominated by
    # resident weights plus *one* layer's attention matrix, and both families have 16 query heads
    # so that matrix is identical; a 4B model simply carries ~2.5 GiB more weight than a 3B one.
    # Fewer full-attention layers reduces *time* at long context, not peak memory, and at the
    # lengths this card admits it is not visibly faster either.
    #
    # So the swap does **not** raise SINGLE_PASS_CEILING; 8,192 stands, with less margin than
    # before. What it buys is a current model and a second lineage architecturally closer to
    # gemma-3, which makes a future SPLIT_FAMILY likelier to be about lineage than about routing.
    #
    # Note what was *not* chosen. `Qwen/Qwen3-4B-Base` is also newer than 2.5 and would have been
    # far worse: 32 query heads and full attention on every layer, i.e. double the matrix at
    # equal length. "Later version" and "better instrument" are different claims, and neither of
    # them is "cheaper instrument".
    "qwen3.5-4b": {
        "lineage": "alibaba/qwen3.5",
        "base": "Qwen/Qwen3.5-4B-Base",
        "base_revision": "1001bb4d826a52d1f399e183466143f4da7b741b",
        "chat": "Qwen/Qwen3.5-4B",
        "chat_revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
    },
}

#: The family this programme ran on before 2026-08-20, kept as a record rather than as a fixture.
#: §98's F3 result was computed on it, so an artifact naming `qwen2.5-3b` is not stale — it is
#: correctly labelled with the family it used, and re-running F3 against the new pin produces a
#: *different* reading rather than a corrected one.
RETIRED_FAMILIES: dict[str, dict[str, str]] = {
    "qwen2.5-3b": {
        "lineage": "alibaba/qwen2.5",
        "base": "Qwen/Qwen2.5-3B",
        "base_revision": "3aab1f1954e9cc14eb9509a215f9e5ca08227a9b",
        "chat": "Qwen/Qwen2.5-3B-Instruct",
        "chat_revision": "aa8e72537993ba99e69dfaafa59ed015b17504d1",
        "retired": "2026-08-20, for Qwen3.5-4B; full attention on all 36 layers made it the "
                   "binding constraint on every teacher-forced context budget",
    },
}

#: Verdicts that are not pass/fail. Every one of them is a sentence some earlier entry had to
#: learn to say instead of a number.
STATES = (
    "PASS",
    "FAIL",
    "INSUFFICIENT_N",
    "DEGRADED_STRATUM",
    "INERT_GENERATOR",
    "NOT_SCREENABLE",
    "SPLIT_FAMILY",
    "VOID",
    "NOT_RUN",
)

PRE_REGISTRATION: dict[str, Any] = {
    "programme": "plan/force-program.md",
    "ledger": "plan/stage-0-decisions.md §95",
    "written_before": "any continuation sampled, any logprob read, any chain run",
    "axiom": "no solicited human judgment, ever — not hired, not operator, not one blinded pair",
    "label": "conversion = followers / total_views, BEHAVIOUR class at STORY grain (§82)",
    "point_bar": POINT_BAR,
    "interval_bar": "Clopper-Pearson 95% lower bound clear of 0.50",
    "binding_half": "interval, at every n in this programme (verified, not asserted)",
    "strata": "aligned and crossed, never averaged; the crossed halves are a contrast not a bar",
    "insufficient_n_above": INSUFFICIENT_N_ABOVE,
    "min_decided_share": MIN_DECIDED_SHARE,
    "controls": {
        "placebo_identical": "exactly zero effect; arithmetic check, not a null (§89.4)",
        "rewhitespace_sham": "reads nothing, or the force is reading formatting and is VOID "
                             "(§78.1)",
    },
    "families": FAMILIES,
    "family_rule": "reported per family, never pooled; disagreement is SPLIT_FAMILY",
    "clustering_caveat": "0 pairs share an author across their sides; 43 authors recur across "
                         "pairs (51 of 562 slots) — a caveat on every interval, printed with "
                         "every result (§89.2)",
}


# ------------------------------------------------------------------------------- identity


def digest(text: str) -> str:
    """Sixteen hex characters of sha256. The key every cache and every seed derives from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def text_seed(text: str, replicate: int = 0) -> int:
    """A 32-bit RNG seed that is a pure function of the text and the replicate index.

    This is the whole mechanism behind `placebo_identical` reading exactly zero. Seeding on
    `(pair_id, side, k)` — the obvious choice — gives byte-identical sides *different* samples,
    and then the placebo reads sampling noise and cannot play the arithmetic-check role §89.4
    gave it. Seeding on the text means identical text is identical everywhere downstream.
    """
    material = f"{digest(text)}|{replicate}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big")


# --------------------------------------------------------------------------------- corpus


@dataclass(frozen=True, slots=True)
class ForcePair:
    """One matched pair, with the text on both sides and the covariates a control might need."""

    pair_id: str
    stratum: str
    high: str
    low: str
    #: Sidecar covariates for the high-conversion and low-conversion sides. Empty when the
    #: sidecar is absent, which is a state a caller must handle rather than a default to paper
    #: over: the view-gap split cannot be computed without it.
    high_meta: dict[str, Any] = field(default_factory=dict)
    low_meta: dict[str, Any] = field(default_factory=dict)

    @property
    def sides(self) -> tuple[tuple[str, str], ...]:
        return (("high", self.high), ("low", self.low))

    def view_gap(self) -> float | None:
        """|log10(view ratio)|, or None where the sidecar cannot supply it."""
        hi = self.high_meta.get("views")
        lo = self.low_meta.get("views")
        if not hi or not lo:
            return None
        return abs(math.log10(hi / lo))


AXIS_KEYS = {"aligned": "axis_conversion_aligned", "crossed": "axis_conversion_crossed"}


def load_pairs(strata: Sequence[str] = ("aligned", "crossed")) -> list[ForcePair]:
    """The B4 corpus with text, joined to the committed covariate sidecar by `pair_id`.

    Raises rather than returning an empty list when the corpus is missing: a force reporting
    "0 pairs, agreement undefined" on a machine that simply has not built the corpus is the
    silent-success failure mode `mirrorbench.models.preflight` exists to refuse.
    """
    if not CORPUS.is_file():
        raise SystemExit(
            f"{CORPUS} is absent. It is gitignored third-party prose and regenerates with:\n"
            f"  uv run python {HERE / 'taste_benchmark.py'} --build"
        )
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    meta = _sidecar_by_pair()
    pairs: list[ForcePair] = []
    for stratum in strata:
        for row in payload[AXIS_KEYS[stratum]]:
            side_meta = meta.get(row["pair_id"], {})
            pairs.append(
                ForcePair(
                    pair_id=row["pair_id"],
                    stratum=stratum,
                    high=row["high"],
                    low=row["low"],
                    high_meta=side_meta.get("high", {}),
                    low_meta=side_meta.get("low", {}),
                )
            )
    return pairs


def _sidecar_by_pair() -> dict[str, dict[str, Any]]:
    if not SIDECAR.is_file():
        return {}
    rows = json.loads(SIDECAR.read_text(encoding="utf-8"))["pairs"]
    return {row["pair_id"]: row for row in rows}


def view_gap_halves(pairs: Iterable[ForcePair]) -> dict[str, list[ForcePair]]:
    """§89.2's split: the tighter-matched half of `crossed` against the looser half.

    A rule and not a threshold, because every threshold worth naming is empty — zero of 137
    crossed pairs match views within a factor of two, the tightest sits at 2.1x and the median
    at 12.2x. The split always populates and its size is n/2, so attainability is computable
    before any label is read.
    """
    crossed = [p for p in pairs if p.stratum == "crossed" and p.view_gap() is not None]
    ordered = sorted(crossed, key=lambda p: (p.view_gap(), p.pair_id))
    half = len(ordered) // 2
    return {"crossed_tight": ordered[:half], "crossed_loose": ordered[half:]}


# ------------------------------------------------------------------------------- controls


def stratified_subsample(pairs: Sequence[ForcePair], count: int) -> list[ForcePair]:
    """`count` pairs spread evenly across the list, rather than the first `count` of it.

    `load_pairs` returns `aligned` and then `crossed`, so a head slice — which is what the
    controls used until this was caught — draws a subsample **entirely from one stratum**. A sham
    that only ever sees `aligned` certifies that a force ignores formatting on half the corpus and
    says nothing about the other half, which is precisely the half §79 built to be adversarial.

    Deterministic by construction: an even stride, no draw, so the same pairs are shammed on every
    run and in every process.
    """
    if count <= 0 or count >= len(pairs):
        return list(pairs)
    stride = len(pairs) / count
    return [pairs[int(index * stride)] for index in range(count)]


def placebo_pairs(pairs: Sequence[ForcePair]) -> list[ForcePair]:
    """Byte-identical sides. The effect must read exactly zero or the arithmetic is broken."""
    return [
        ForcePair(
            pair_id=f"placebo:{p.pair_id}",
            stratum="placebo_identical",
            high=p.high,
            low=p.high,
            high_meta=p.high_meta,
            low_meta=p.high_meta,
        )
        for p in pairs
    ]


def sham_pairs(pairs: Sequence[ForcePair], strength: float = 1.0) -> list[ForcePair]:
    """One side re-whitespaced, the other untouched. Not one character of any word changes.

    §78.1's control in the pairwise frame: `high` is assigned arbitrarily to the untouched side,
    so a force that reads nothing but prose has no reason to prefer either and must land on an
    interval containing 0.50. A force that prefers one systematically is reading layout, and
    §78's em-dash finding is what a reading like that looks like when nobody checks.
    """
    # A pair whose transform changed nothing is not a control, it is a placebo wearing a sham's
    # name — and it dilutes the sham's denominator with a guaranteed tie. Measured: 3 of 281 high
    # sides are `rewhitespace` no-ops, and one of them is index 0, which `stratified_subsample`
    # draws at every size — so every sham subsample on every track contained one.
    out = []
    for p in pairs:
        low = rewhitespace(p.high, strength)
        if low == p.high:
            continue
        out.append(ForcePair(
            pair_id=f"sham:{p.pair_id}",
            stratum="rewhitespace_sham",
            high=p.high,
            low=low,
            high_meta=p.high_meta,
            low_meta=p.high_meta,
        ))
    return out


# ----------------------------------------------------------------------------- the bars


def required_k_point(n: int, bar: float = POINT_BAR) -> int:
    """Smallest k with k/n >= bar."""
    return math.ceil(bar * n - 1e-12)


@lru_cache(maxsize=4096)
def required_k_interval(n: int, alpha: float = ALPHA) -> int | None:
    """Smallest k whose Clopper-Pearson lower bound clears 0.50, or None if no k does.

    Bisected rather than walked. `clopper_pearson` sums a binomial tail inside sixty bisection
    steps, so a linear walk over k costs O(n**2) tail sums and the attainability table for a few
    hundred candidate n takes minutes — measured, when the first version of this made the
    selftest time out. The bound rises monotonically in k, which is what makes bisection valid.
    """
    if n <= 0:
        return None
    if clopper_pearson(n, n, alpha=alpha)[0] <= 0.50:
        return None
    low, high = 0, n
    while low < high:
        middle = (low + high) // 2
        if clopper_pearson(middle, n, alpha=alpha)[0] > 0.50:
            high = middle
        else:
            low = middle + 1
    return low


def attainability(n: int, *, label: str = "") -> dict[str, Any]:
    """The §87 check, as a computed row rather than a habit.

    Printed beside every declaration. `binding` names which half of the bar is the one a force
    actually has to clear, and `required_rate` is the number to look at before believing a
    stratum can produce a result at all — F3's 0.7500 and FX's 1.0000 are why §1.2's
    INSUFFICIENT_N rule exists.
    """
    if n <= 0:
        return {"label": label, "n": n, "attainable": False, "why": "empty stratum"}
    k_point = required_k_point(n)
    k_interval = required_k_interval(n)
    binding = "interval" if k_interval is not None and k_interval >= k_point else "point"
    required = (k_interval if binding == "interval" else k_point) / n
    return {
        "label": label,
        "n": n,
        "k_point_0_52": k_point,
        "k_interval_cp_gt_0_50": k_interval,
        "binding": binding,
        "required_rate": round(required, 4),
        "attainable": k_interval is not None and k_interval <= n,
        "insufficient_n_available": round(required, 4) > INSUFFICIENT_N_ABOVE,
    }


#: The smallest n whose interval bar still demands 0.6000 or less — i.e. the smallest stratum
#: that can still *refute* rather than only fail for want of power. Computed, not chosen: see
#: :func:`selftest`. A binding stratum that drops below it after per-pair drops is reported as
#: DEGRADED_STRATUM, because a force cannot be failed at an n where failure was the only
#: available outcome.
MIN_REFUTING_N = 110

#: A control with fewer decided pairs than this cannot fail. At n <= 5 the Clopper-Pearson
#: interval contains 0.50 for *every* possible outcome, so `sham_verdict(4, 4, 4)` — the
#: whitespace side winning every pair — returned PASS. A control whose rejection region is empty
#: is not a control that passed; FX shipped a `--sham` default of 4, so its declared kill "the
#: sham moves anything" was unreachable at its own default.
MIN_SCREENING_N = 12


def verdict(
    label: str,
    wins: int,
    decided: int,
    n_total: int,
    *,
    alpha: float = ALPHA,
    n_before_drops: int | None = None,
    binding: bool = False,
) -> dict[str, Any]:
    """One stratum's reading, with the refusal states kept out of pass/fail.

    `wins` counts pairs the force put the high-conversion side ahead on, among `decided` pairs;
    `n_total` includes ties. The interval is computed on decided pairs, which is §89.1's unit
    rule — but a rate resting on few decisions is exactly §87.3's inflated 1.000, so a decided
    share below :data:`MIN_DECIDED_SHARE` returns INERT_GENERATOR and no rate at all.
    """
    row = attainability(decided, label=label)
    out: dict[str, Any] = {
        "stratum": label,
        "pairs": n_total,
        "decided": decided,
        "ties": n_total - decided,
        "wins": wins,
        "attainability": row,
        "clustering_caveat": PRE_REGISTRATION["clustering_caveat"],
    }
    # Drops are counted against the stratum's original size, never hidden inside its denominator.
    # `pair_agreement` skips a pair it has no score for, so without this the tie guard would be
    # computed over the survivors and a force that scored 40 of 137 pairs would report a clean
    # decided share. §89's no-silent-caps rail, in the one place it could silently bite.
    if n_before_drops is not None and n_before_drops != n_total:
        out["dropped_before_scoring"] = n_before_drops - n_total
        out["n_before_drops"] = n_before_drops
    # **Ties and drops are different failures and get different states.** The tie share is taken
    # over the pairs that were actually SCORED — a statistic mostly made of ties has said nothing
    # about prose — while pairs the run never scored are attrition and belong to the stratum's
    # size, not to the generator's behaviour. Folding them together mislabels a truncated corpus
    # as an inert one and vice versa.
    #
    # INERT_GENERATOR is tested before DEGRADED_STRATUM: the other order published every
    # tie-driven inert reading on a small binding stratum as a corpus-power complaint that
    # explicitly acquits the force — live in force-f1-haiku.json's crossed raw diagnostic, which
    # was 58/65 = 0.892, below the 0.90 floor, and printed as DEGRADED.
    if decided == 0 or (n_total and decided / n_total < MIN_DECIDED_SHARE):
        out["status"] = "INERT_GENERATOR"
        out["why"] = (
            f"{decided} of {n_total} scored pairs decided, below the declared "
            f"{MIN_DECIDED_SHARE} share; a statistic mostly made of ties has said nothing"
        )
        return out
    if n_total == 0:
        out["status"] = "NOT_RUN"
        out["why"] = "no pairs in this stratum"
        return out
    rate = wins / decided
    low, high = clopper_pearson(wins, decided, alpha=alpha)
    out["agreement"] = round(rate, 4)
    out["clopper_pearson"] = [low, high]
    out["point_bar_cleared"] = rate >= POINT_BAR
    out["interval_bar_cleared"] = low > 0.50
    # **The power guards run after the bars, and only on a stratum that did not clear them.**
    # Their whole argument is that *a FAIL* at this n would be a statement about power — which
    # says nothing about a stratum that cleared both bars. Guarding first meant a small stratum
    # with decisive agreement was published as a power complaint: 95 of 100 gives a lower bound
    # of 0.887 and used to read DEGRADED_STRATUM, with prose explaining that it could not refute.
    if out["point_bar_cleared"] and out["interval_bar_cleared"]:
        out["status"] = "PASS"
        return out
    # Two ways a miss can be about power rather than about the force, and they are one branch
    # because they carry the same consequence:
    #
    #   not attainable                no k at all clears the interval bar at this n. n=5 was a
    #                                 hole in the ladder — perfect agreement returned
    #                                 INSUFFICIENT_N at n=2-4 and PASS at n>=6 but FAIL at 5.
    #   insufficient_n_available      some k clears it, but the rate it demands is above the
    #                                 declared ceiling for calling a miss a refutation.
    #
    # **The second is read at this n rather than compared against a threshold, because it is not
    # monotone in n.** `required_rate` moves in sawteeth: n ∈ {111, 113, 116, 118} each demand
    # 0.6017 to 0.6036 — above the 0.6000 ceiling — yet each sits above `MIN_REFUTING_N` and so
    # counted as able to refute. F3's `aligned` stratum is exactly 118, so this was not a corner
    # case: the arm that most needed the guard was the one that stepped over it. The constant
    # survives as the declared headline figure and as what the selftest pins.
    unattainable = not row.get("attainable", True)
    if unattainable or row.get("insufficient_n_available"):
        # DEGRADED_STRATUM is the same refusal with a cause attached: this stratum arrived here
        # by losing pairs, so the shortfall is attrition and a re-run can repair it. Without the
        # drop test the two are indistinguishable in the artifact, and "the corpus was always
        # this small" reads exactly like "the run threw half of it away".
        degraded = binding and n_before_drops is not None and n_before_drops > n_total
        out["status"] = "DEGRADED_STRATUM" if degraded else "INSUFFICIENT_N"
        shortfall = (
            f"no k clears the interval bar at n={decided}"
            if unattainable else
            f"the interval bar at n={decided} demands {row['required_rate']}, above the "
            f"declared {INSUFFICIENT_N_ABOVE} ceiling for calling a miss a refutation"
        )
        out["why"] = shortfall + (
            f"; the stratum reached this n by losing {n_before_drops - n_total} of "
            f"{n_before_drops} pairs before scoring, so the shortfall is attrition rather than "
            "a corpus that was always this size"
            if degraded else
            f" (the headline floor is n={MIN_REFUTING_N}, but the requirement is sawtoothed in "
            "n, so it is read at this n rather than compared to it)"
        )
        return out
    out["status"] = "FAIL"
    return out


def control_verdict(
    label: str,
    effect: float,
    *,
    tolerance: float,
    kind: str,
) -> dict[str, Any]:
    """The placebo's arithmetic check. `kind` is 'exact' or 'equivalence'.

    `tolerance` is 0.0 under a bit-exact stack and the *measured* replay-noise scale otherwise —
    measured by `determinism_probe.py` before any force runs, never chosen after seeing a
    control fail. A tolerance picked after the fact is the bar-moving §89's rulebook is about.
    """
    ok = abs(effect) <= tolerance
    return {
        "control": label,
        "effect": effect,
        "tolerance": tolerance,
        "kind": kind,
        "status": "PASS" if ok else "VOID",
        "why": "" if ok else (
            "the placebo moved; byte-identical sides produced different numbers, so the "
            "run's arithmetic — not its prose reading — is what this result is about"
        ),
    }


def sham_verdict(label: str, wins: int, decided: int, n_total: int) -> dict[str, Any]:
    """A sham passes by reading NOTHING: an interval that contains 0.50.

    The direction a control has to fail in, per §94.2: insufficient evidence fails rather than
    passes is the right rule for a *seating* control, and the right rule for a sham is the
    mirror of it — a sham that shows an effect is disqualifying whichever way it points.
    """
    out: dict[str, Any] = {"control": label, "pairs": n_total, "decided": decided, "wins": wins}
    if decided < MIN_SCREENING_N:
        out["status"] = "NOT_SCREENABLE"
        out["why"] = (
            f"{decided} decided pairs is below the {MIN_SCREENING_N} floor at which this control "
            "has any rejection region at all; below it every outcome passes, so a PASS here "
            "would certify nothing"
        )
        return out
    low, high = clopper_pearson(wins, decided, alpha=ALPHA)
    out["agreement"] = round(wins / decided, 4)
    out["clopper_pearson"] = [low, high]
    contains_half = low <= 0.50 <= high
    out["status"] = "PASS" if contains_half else "VOID"
    if not contains_half:
        out["why"] = (
            "the whitespace sham moved the force; not one character of any word changed "
            "between the two sides, so the force is reading layout and the reading is VOID"
        )
    return out


def arm_status(controls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """An arm's status from its controls, before any stratum is read.

    §1.3 says the placebo and the sham ride **every** force, and the reason is that a force which
    has not been shown to ignore formatting has not been shown to be reading prose. So an
    unscreenable control is not a missing detail that a clean stratum can outvote:

        VOID             a control moved — the reading is disqualified (§78.1)
        NOT_SCREENABLE   a control could not be read at all, so nothing certifies the force

    The second case is the one worth having. A run whose budget or substrate ran out before the
    sham would otherwise report `READ` beside strata that look fine, and a reader would have no
    way to tell that the formatting control never happened.

    **The two names are required, and their absence is the failure this function most needed to
    catch.** `arm_status({})` returned `READ` — the loop over an empty dict finds no VOID and no
    unscreened name, so an arm that ran *no controls at all* certified itself. That is not a
    hypothetical: F3 skipped both controls and hard-coded `report["status"] = "READ"`, which is
    the same reading arrived at by hand. An arm is screened when the two named controls report,
    not when nothing objects.
    """
    missing = [name for name in REQUIRED_CONTROLS if name not in controls]
    if missing:
        return {
            "status": "NOT_SCREENABLE",
            "controls": {name: block.get("status", "NOT_RUN") for name, block in controls.items()},
            "missing_controls": missing,
            "why": f"{', '.join(missing)} did not run at all; §1.3 rides both controls on every "
                   "force, and an arm with no formatting control has not been shown to be "
                   "reading prose",
        }
    states = {name: block.get("status", "NOT_RUN") for name, block in controls.items()}
    if any(state == "VOID" for state in states.values()):
        return {
            "status": "VOID",
            "controls": states,
            "why": "a control moved; §78.1 disqualifies the reading rather than caveating it",
        }
    unscreened = [name for name, state in states.items()
                  if state in ("NOT_SCREENABLE", "NOT_RUN", "INERT_GENERATOR")]
    if unscreened:
        return {
            "status": "NOT_SCREENABLE",
            "controls": states,
            "why": f"{', '.join(unscreened)} could not be read, so nothing certifies that this "
                   "force is reading prose rather than formatting",
        }
    return {"status": "READ", "controls": states}


def combine_families(per_family: dict[str, dict[str, Any]], stratum: str) -> dict[str, Any]:
    """Two families, never pooled. Agreement in *direction* is the requirement.

    §94.5 in one function: `qwen3:14b` named displacement as deletion on 22 of 30 and
    `gemma3:12b` on 3 of 30, and a single-family run would have supported the wider sentence
    and been wrong. So a force is a force when both families read it, and a force one family
    reads and the other refuses claims nothing.
    """
    rows = {name: report.get(stratum, {}) for name, report in per_family.items()}
    statuses = {name: row.get("status", "NOT_RUN") for name, row in rows.items()}
    out: dict[str, Any] = {"stratum": stratum, "per_family": statuses, "never_pooled": True}
    # **The two-family minimum is enforced here or it is not enforced at all.** With one family
    # `all(status == "PASS")` is trivially true, so a single-lineage arm that cleared its strata
    # would have reported PASS — the exact claim §94.5 says cannot be made, in the function
    # written to prevent it. One family's artifact reads as a finding until a second refuses it.
    if len(statuses) < 2:
        out["status"] = "NOT_SCREENABLE"
        out["why"] = (
            f"{len(statuses)} family reported; the two-family minimum (§1.4) is not met, so no "
            "reading here is the force's however its strata came out"
        )
        return out
    if any(s in ("NOT_RUN", "NOT_SCREENABLE") for s in statuses.values()):
        out["status"] = "NOT_SCREENABLE"
        out["why"] = "a family could not be run; the two-family minimum is not met"
        return out
    if any(s == "VOID" for s in statuses.values()):
        out["status"] = "VOID"
        out["why"] = "a control failed on at least one family"
        return out
    if all(s == "PASS" for s in statuses.values()):
        out["status"] = "PASS"
        return out
    # **A refusal is not a disagreement, and it is tested first.** SPLIT_FAMILY says one family
    # *read* the force and another *read it the other way* — a substantive claim about lineage.
    # A family whose stratum was too small to refute, or whose statistic returned mostly ties,
    # made no reading at all, and describing it as dissent invents a finding out of an absence.
    # `force-f1-haiku.json` already holds a genuine DEGRADED `crossed`, so this fires on the
    # first real two-family run rather than in some constructed corner.
    #
    # DEGRADED_STRATUM outranks INERT_GENERATOR outranks INSUFFICIENT_N, and all three outrank
    # FAIL: a stratum that could not refute cannot contribute a FAIL to anything. The first
    # version let every one of them fall through to FAIL, which is exactly the folding-a-refusal
    # -into-a-verdict §1.5 forbids — caught by a three-pair smoke run.
    for refusal, why in (
        ("DEGRADED_STRATUM",
         "a family's stratum was too small to refute; no FAIL can be built from it"),
        ("INERT_GENERATOR",
         "a family's statistic was mostly ties, so that family made no reading to agree or "
         "disagree with"),
        ("INSUFFICIENT_N",
         "a family's stratum could not clear its interval bar at any outcome"),
    ):
        if any(s == refusal for s in statuses.values()):
            out["status"] = refusal
            out["why"] = why
            return out
    if any(s == "PASS" for s in statuses.values()):
        out["status"] = "SPLIT_FAMILY"
        out["why"] = (
            "one family reads the force and another does not; neither reading is reported as "
            "the force's, because §94.5 is the case where the single-family sentence was wrong"
        )
        return out
    out["status"] = "FAIL"
    return out


def force_verdict(
    per_family: dict[str, dict[str, Any]], combined: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """The one place a force's headline verdict is decided, and it reads the controls first.

    Two defects this replaces, both of which published `PASS` over evidence that forbade it:

    * `arm_status` was computed, written to `report["status"]`, and **read by nothing**. A run
      whose sham had moved — a VOID arm — could still publish a passing headline, because the
      headline consulted only the strata.
    * the fallback was `combined["aligned"]["status"]`, so an arm that cleared `aligned` and
      failed `crossed` — the exact signature `crossed` exists to catch — published the *aligned*
      status, i.e. `"PASS"`, beside prose saying it did not clear both strata.

    A refusal anywhere outranks everything: a force may only pass when both binding strata pass
    **and** every family's controls were readable.
    """
    arm_states = {name: block.get("status", "NOT_RUN") for name, block in per_family.items()}
    binding = {label: (combined.get(label) or {}).get("status", "NOT_RUN")
               for label in ("aligned", "crossed")}
    if not arm_states:
        return {"verdict": "NOT_RUN", "arm_states": arm_states, "binding": binding}
    for refusal in ("VOID", "NOT_SCREENABLE", "NOT_RUN", "INERT_GENERATOR"):
        if refusal in arm_states.values():
            return {
                "verdict": refusal,
                "arm_states": arm_states,
                "binding": binding,
                "why": f"a family's arm reads {refusal}; its controls do not license a reading",
            }
    if all(state == "PASS" for state in binding.values()):
        return {"verdict": "PASS", "arm_states": arm_states, "binding": binding}
    for refusal in ("VOID", "NOT_SCREENABLE", "DEGRADED_STRATUM", "INERT_GENERATOR",
                    "INSUFFICIENT_N", "NOT_RUN"):
        if refusal in binding.values():
            return {"verdict": refusal, "arm_states": arm_states, "binding": binding}
    return {"verdict": "FAIL", "arm_states": arm_states, "binding": binding}


# --------------------------------------------------------------------- pairing statistics


def pair_agreement(
    scores: dict[str, dict[str, float]],
    pairs: Sequence[ForcePair],
    *,
    higher_wins: bool = True,
) -> tuple[int, int, int]:
    """(wins, decided, total) for a per-side score, with exact ties excluded and counted.

    `scores[pair_id] = {"high": x, "low": y}`. `higher_wins=False` flips the direction for a
    force whose hypothesis says the good side scores *lower* — F2's decay slope is the case,
    and stating the direction at the call site rather than by sign convention is what keeps a
    later reader from having to reconstruct which way the hypothesis pointed.
    """
    wins = decided = total = 0
    for pair in pairs:
        row = scores.get(pair.pair_id)
        if row is None or row.get("high") is None or row.get("low") is None:
            continue
        total += 1
        hi, lo = row["high"], row["low"]
        if hi == lo:
            continue
        decided += 1
        if (hi > lo) == higher_wins:
            wins += 1
    return wins, decided, total


def residualise(
    values: dict[str, float],
    covariate: dict[str, float],
    *,
    quadratic: bool = False,
) -> dict[str, float]:
    """Label-blind nuisance regression: strip the covariate's linear (or quadratic) part.

    The regression never sees `conversion`. That is the property that makes adjusting for
    distinctiveness legitimate rather than circular: it is fitted on the sides pooled, with no
    access to which side of a pair is which, and the pair comparison then runs on residuals.
    """
    keys = [k for k in values if k in covariate]
    if len(keys) < 3:
        return dict(values)
    xs = [covariate[k] for k in keys]
    ys = [values[k] for k in keys]
    design = [[1.0, x] + ([x * x] if quadratic else []) for x in xs]
    coefficients = _least_squares(design, ys)
    if coefficients is None:
        return dict(values)
    out = {}
    for key, row in zip(keys, design, strict=True):
        fitted = sum(c * v for c, v in zip(coefficients, row, strict=True))
        out[key] = values[key] - fitted
    return out


def _least_squares(design: list[list[float]], target: list[float]) -> list[float] | None:
    """Normal equations with Gaussian elimination. Stdlib only, and small by construction."""
    width = len(design[0])
    normal = [[sum(r[i] * r[j] for r in design) for j in range(width)] + [
        sum(r[i] * y for r, y in zip(design, target, strict=True))] for i in range(width)]
    for col in range(width):
        pivot = max(range(col, width), key=lambda r: abs(normal[r][col]))
        if abs(normal[pivot][col]) < 1e-12:
            return None
        normal[col], normal[pivot] = normal[pivot], normal[col]
        for row in range(width):
            if row == col:
                continue
            factor = normal[row][col] / normal[col][col]
            for k in range(col, width + 1):
                normal[row][k] -= factor * normal[col][k]
    return [normal[i][width] / normal[i][i] for i in range(width)]


def least_squares_with_se(
    design: list[list[float]], target: list[float]
) -> tuple[list[float], list[float]] | None:
    """Coefficients **and their standard errors**, because a coefficient alone cannot be read.

    `_least_squares` returns point estimates, and every caller that only had point estimates
    ended up reading the sign of a number whose interval spans zero. F1's `inverted_u` is the
    case: it declared a pre-registered alternative READ on `quad < 0 and the peak is interior`,
    with no SE anywhere in the function. The fit it published was -0.017463 +/- 0.013543
    (t = -1.29, R^2 = 0.003), and on 2,000 synthetic samples with y independent of x the rule
    fired **42% of the time**.

    Ordinary OLS algebra: se_j = sqrt(sigma^2 * inv(X'X)_jj) with sigma^2 = RSS / (n - p).
    Returns None where the design is singular or there are no residual degrees of freedom —
    both are refusals, not zeros.
    """
    n, width = len(design), len(design[0])
    if n <= width:
        return None
    xtx = [[sum(r[i] * r[j] for r in design) for j in range(width)] for i in range(width)]
    xty = [sum(r[i] * y for r, y in zip(design, target, strict=True)) for i in range(width)]
    # Gauss-Jordan on [X'X | I], so the inverse falls out beside the solve.
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(width)] for i, row in enumerate(xtx)]
    for col in range(width):
        pivot = max(range(col, width), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [v / scale for v in aug[col]]
        for row in range(width):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [v - factor * w for v, w in zip(aug[row], aug[col], strict=True)]
    inverse = [row[width:] for row in aug]
    coefficients = [sum(inverse[i][j] * xty[j] for j in range(width)) for i in range(width)]
    residuals = [
        y - sum(c * v for c, v in zip(coefficients, row, strict=True))
        for row, y in zip(design, target, strict=True)
    ]
    sigma2 = sum(r * r for r in residuals) / (n - width)
    errors = [math.sqrt(max(sigma2 * inverse[i][i], 0.0)) for i in range(width)]
    return coefficients, errors


def ols_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Plain slope. Used where the statistic *is* a slope — F2's decay, F3's learnability."""
    if len(xs) < 2:
        return float("nan")
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    if denominator == 0:
        return float("nan")
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denominator


# ---------------------------------------------------------------------------- checkpoints


class Checkpoint:
    """Append-per-unit JSONL, keyed by a digest of everything that produced the row.

    Two jobs, and the second is the one this box has taught the hard way: it is a replay cache
    keyed on *inputs* rather than on labels — RUNBOOK's rule, because a cache keyed
    `(family, pair, side)` replays numbers computed on texts that no longer exist the moment a
    transform is edited — and it is a crash checkpoint, because the 4090 in this machine
    hard-shut-down at call 431 of the CDG battery and a run that has to start over is a run
    that will not be finished.
    """

    def __init__(self, path: Path) -> None:
        import threading

        # Appends come from several worker threads once the remote transport parallelises across
        # seeds; without this two writers interleave a line and the cache reloads as corrupt.
        self._write_lock = threading.Lock()
        self.path = Path(path)
        self._rows: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self._rows[row["key"]] = row
        self.replayed = 0
        self.computed = 0

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._rows.get(key)
        if row is not None:
            self.replayed += 1
        return row

    def put(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"key": key, **payload}
        self._rows[key] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        self.computed += 1
        return row

    def provenance(self) -> dict[str, Any]:
        return {
            "cache": str(self.path),
            "replayed_units": self.replayed,
            "computed_units": self.computed,
            "rows_on_disk": len(self._rows),
        }


def unit_key(*parts: Any) -> str:
    """A cache key from the *inputs*: family, revision, text digests, every knob that matters."""
    return digest("|".join(str(p) for p in parts))


# -------------------------------------------------------------------------------- reports


def attainability_table(sizes: dict[str, int]) -> list[dict[str, Any]]:
    """The table §1.2 prints. Computed here so no document and no module can disagree."""
    return [attainability(n, label=label) for label, n in sizes.items()]


def provenance(**extra: Any) -> dict[str, Any]:
    """The block every result file carries, so a number can be traced to what produced it."""
    return {"pre_registration": PRE_REGISTRATION, **extra}


# ------------------------------------------------------------------------------- selftest


def selftest() -> int:
    """Arithmetic first, on constructed inputs, before any GPU or any corpus is involved."""
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    # §89.2's published table is the reference: the harness reproduces it or it is wrong.
    for n, k_point, k_interval in ((144, 75, 85), (137, 72, 81), (68, 36, 43), (69, 36, 44)):
        row = attainability(n)
        check(row["k_point_0_52"] == k_point, f"n={n} point k {row['k_point_0_52']}!={k_point}")
        check(
            row["k_interval_cp_gt_0_50"] == k_interval,
            f"n={n} interval k {row['k_interval_cp_gt_0_50']}!={k_interval}",
        )
        check(row["binding"] == "interval", f"n={n} binding {row['binding']}")

    # The INSUFFICIENT_N rule admits exactly the strata §1.2 says it does, and no others.
    check(not attainability(144)["insufficient_n_available"], "aligned must not be excusable")
    check(not attainability(137)["insufficient_n_available"], "crossed must not be excusable")
    check(attainability(68)["insufficient_n_available"], "crossed-tight must be excusable")
    check(attainability(20)["insufficient_n_available"], "F3 must be excusable")

    # MIN_REFUTING_N is computed rather than chosen: the smallest n whose interval bar still
    # demands 0.6000 or less. A constant nobody can re-derive is a constant somebody will move.
    # Attainable AND refuting: below n=110 either no k clears the interval at all, or the rate
    # it demands is above the declared 0.6000 ceiling. The guard has to carry both halves —
    # the first draft omitted `attainable` and derived 5, where no k clears the interval and the
    # stratum is worse than excusable rather than better.
    smallest = min(
        n for n in range(2, 200)
        if attainability(n)["attainable"] and not attainability(n)["insufficient_n_available"]
    )
    check(smallest == MIN_REFUTING_N, f"MIN_REFUTING_N should be {smallest}, is {MIN_REFUTING_N}")
    # Truncation and ties are different states. 76 of 137 pairs SCORED, all of them decided:
    # that is attrition, and a stratum below the refuting floor may not refute.
    check(
        verdict("crossed", 40, 76, 76, n_before_drops=137, binding=True)["status"]
        == "DEGRADED_STRATUM",
        "a binding stratum below the refuting floor must not be failed",
    )
    # 137 scored but only 80 decided is 57 ties: the generator said nothing, which is a
    # different complaint from the corpus being small.
    check(
        verdict("crossed", 40, 80, 137, n_before_drops=137, binding=True)["status"]
        == "INERT_GENERATOR",
        "a tie-heavy stratum must read INERT_GENERATOR, not a corpus-power complaint",
    )
    dropped = verdict("crossed", 70, 120, 120, n_before_drops=137, binding=True)
    check(dropped.get("dropped_before_scoring") == 17, "drops must be counted, not hidden")

    # A stratum that clears the point bar and misses the interval: FAIL where the interval is
    # reachable, INSUFFICIENT_N only where it demands more than the declared ceiling.
    check(verdict("aligned", 80, 144, 144)["status"] == "FAIL", "aligned near-miss must FAIL")
    check(
        verdict("crossed_tight", 40, 68, 68)["status"] == "INSUFFICIENT_N",
        "crossed-tight near-miss must be INSUFFICIENT_N",
    )
    check(verdict("aligned", 90, 144, 144)["status"] == "PASS", "aligned 90/144 must PASS")

    # Ties are not evidence. A statistic mostly made of ties says nothing.
    check(
        verdict("aligned", 60, 100, 144)["status"] == "INERT_GENERATOR",
        "a 69% decided share must read INERT_GENERATOR",
    )

    # The placebo is exact by construction, so identical text seeds identical randomness.
    check(text_seed("abc", 3) == text_seed("abc", 3), "seed must be a pure function of text")
    check(text_seed("abc", 3) != text_seed("abd", 3), "different text must seed differently")
    check(text_seed("abc", 3) != text_seed("abc", 4), "replicates must differ")

    # The sham must change layout and not one character of any word.
    sample = "One line.  Two line.\n\nThree line. Four line."
    shammed = rewhitespace(sample, 1.0)
    check(sample.split() == shammed.split(), "rewhitespace changed a word")

    # Direction is stated at the call site, never inferred from a sign.
    scores = {"a": {"high": 2.0, "low": 1.0}, "b": {"high": 1.0, "low": 2.0},
              "c": {"high": 1.0, "low": 1.0}}
    fake = [ForcePair(pair_id=k, stratum="aligned", high="x", low="y") for k in scores]
    check(pair_agreement(scores, fake) == (1, 2, 3), "higher-wins pairing wrong")
    check(
        pair_agreement(scores, fake, higher_wins=False) == (1, 2, 3),
        "lower-wins pairing wrong",
    )

    # A sham that reads nothing passes; one that reads something is VOID either way it points.
    check(sham_verdict("sham", 50, 100, 100)["status"] == "PASS", "balanced sham must pass")
    check(sham_verdict("sham", 90, 100, 100)["status"] == "VOID", "one-sided sham must void")
    check(sham_verdict("sham", 10, 100, 100)["status"] == "VOID", "sham voids in both signs")

    # The placebo tolerance is applied, not assumed.
    check(control_verdict("p", 0.0, tolerance=0.0, kind="exact")["status"] == "PASS", "p exact")
    check(control_verdict("p", 1e-9, tolerance=0.0, kind="exact")["status"] == "VOID", "p void")

    # Two families are combined by direction, never by pooling.
    degraded = {"a": {"aligned": {"status": "DEGRADED_STRATUM"}},
                "b": {"aligned": {"status": "FAIL"}}}
    check(
        combine_families(degraded, "aligned")["status"] == "DEGRADED_STRATUM",
        "a degraded stratum must not combine into a FAIL",
    )
    both_pass = {"a": {"aligned": {"status": "PASS"}}, "b": {"aligned": {"status": "PASS"}}}
    split = {"a": {"aligned": {"status": "PASS"}}, "b": {"aligned": {"status": "FAIL"}}}
    check(combine_families(both_pass, "aligned")["status"] == "PASS", "both-pass")
    check(combine_families(split, "aligned")["status"] == "SPLIT_FAMILY", "split-family")

    # The nuisance regression removes what it is given and nothing else.
    covariate = {f"k{i}": float(i) for i in range(10)}
    values = {f"k{i}": 3.0 * i + 1.0 for i in range(10)}
    residuals = residualise(values, covariate)
    check(max(abs(v) for v in residuals.values()) < 1e-9, "linear residual must vanish")

    check(abs(ols_slope([1, 2, 3], [2, 4, 6]) - 2.0) < 1e-12, "ols slope wrong")

    # A control subsample must span the strata, not the head of the list.
    corpus = (
        [ForcePair(pair_id=f"a{i}", stratum="aligned", high="x", low="y") for i in range(144)]
        + [ForcePair(pair_id=f"c{i}", stratum="crossed", high="x", low="y") for i in range(137)]
    )
    picked = stratified_subsample(corpus, 60)
    check(len(picked) == 60, f"subsample size {len(picked)}")
    strata = {pair.stratum for pair in picked}
    check(strata == {"aligned", "crossed"}, f"subsample must span both strata, got {strata}")
    check(
        stratified_subsample(corpus, 60) == picked,
        "the subsample must be deterministic across calls",
    )
    check(len(stratified_subsample(corpus, 999)) == len(corpus), "an over-large ask returns all")

    for message in failures:
        print(f"FAIL {message}")
    print(f"force_harness selftest: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--attainability" in sys.argv:
        table = attainability_table(
            {
                "aligned": 144,
                "crossed": 137,
                "crossed_tight": 68,
                "crossed_loose": 69,
                "f3_fiction_pairs": 20,
                "fx_pilot_pairs": 8,
                "f1_pilot_pairs": 16,
            }
        )
        print(json.dumps(table, indent=2))
        raise SystemExit(0)
    raise SystemExit(selftest())
