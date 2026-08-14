"""Score a candidate craft metric against manufactured ground truth, controls included.

Takes any `scorer: (text) -> float` and returns the numbers that decide whether it survives.
The controls are not optional arguments — they are computed in the same pass and reported
beside the headline, because `plan/craft-corpus.md` §2 makes that a rule and every proxy in the
refutation ledger died to a control that was computed afterwards or not at all.

**Four numbers, and the headline is the least important of them.**

1. `detect_auc` — rank AUC separating degraded texts from their originals. The headline.
2. `sham_auc` — the same statistic against `SHAMS`, which change the text and should not change
   quality. **This is the era control's analogue.** A metric with detect 0.85 and sham 0.80 has
   found *edited-ness*, not damage, and is dead exactly as `tricolon_rate` was dead at 0.629
   against a control of 0.606. The reported margin `detect_auc - sham_auc` is the real result.
3. `dose_rho` — Spearman of score against ablation strength, per degrader. Monotonicity is the
   claim; detection at full strength alone is detection of vandalism.
4. `length_auc` — the same separation achieved by raw word count. §1a.1's shallow incumbent. A
   metric that does not beat it is measuring length.

**Paired by construction.** Every comparison is within one chapter: the degraded text and its
own original. Author, era, story, genre, tags, maturity and cadence are identical on both sides
of every pair, which is the property the refutation ledger says the between-cohort designs never
had. What it costs is that a within-chapter effect says nothing about between-chapter ranking,
and `paired_rate` is reported rather than `detect_auc` alone for that reason: the fraction of
pairs scored in the right direction is the statistic that matches the design.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from ablate import DEGRADERS, DOSES, SHAMS, variants

Scorer = Callable[[str], float]


def auc(positive: Sequence[float], negative: Sequence[float]) -> float:
    """Rank AUC with ties at half. Copied in behaviour from `tools/build_craft_profile.py`.

    Reimplemented rather than imported so this file runs under either interpreter, and checked
    against that one in `selftest()` — a silently divergent AUC would make every number here
    incomparable with the committed profile.
    """
    if not positive or not negative:
        return 0.5
    merged = sorted([(v, 1) for v in positive] + [(v, 0) for v in negative])
    index = 0
    rank_sum = 0.0
    while index < len(merged):
        stop = index
        while stop + 1 < len(merged) and merged[stop + 1][0] == merged[index][0]:
            stop += 1
        average = (index + stop) / 2.0 + 1.0
        for position in range(index, stop + 1):
            if merged[position][1] == 1:
                rank_sum += average
        index = stop + 1
    n_pos, n_neg = len(positive), len(negative)
    return round((rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg), 4)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")

    def ranks(values: Sequence[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            average = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = average
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def binomial_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson interval. Used on `paired_rate`, where the null is exactly 0.5.

    Wilson rather than normal-approximation because the rates of interest here sit near 0.5
    and near 1.0 at small n, and the normal interval is badly wrong at the top end — which is
    the end a promising result lands on.
    """
    if trials == 0:
        return (0.0, 1.0)
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


@dataclass
class Result:
    """One candidate metric's verdict, with every control beside the headline."""

    metric: str
    n_chapters: int
    detect_auc: float = 0.5
    sham_auc: float = 0.5
    length_auc: float = 0.5
    paired_rate: float = 0.5
    paired_ci: tuple[float, float] = (0.0, 1.0)
    paired_n: int = 0
    per_ablation: dict[str, dict[str, float]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def margin(self) -> float:
        """detect minus sham. The number that is actually the result."""
        return round(self.detect_auc - self.sham_auc, 4)

    def verdict(self) -> str:
        """A one-line reading, phrased so it can say "dead" without hedging."""
        if abs(self.detect_auc - 0.5) < 0.05:
            return "DEAD — does not separate damaged prose from its own original"
        if abs(self.margin) < 0.05:
            return (
                f"DEAD — detect {self.detect_auc} but sham {self.sham_auc}; it is responding "
                "to the text having been edited, not to the damage"
            )
        if abs(self.detect_auc - 0.5) <= abs(self.length_auc - 0.5):
            return (
                f"DEAD — raw word count separates as well ({self.length_auc}); §1a.1's "
                "shallow incumbent is not beaten"
            )
        if self.paired_ci[0] <= 0.5:
            return (
                f"UNDETERMINED — paired rate {self.paired_rate} but its 95% interval "
                f"{self.paired_ci} includes chance"
            )
        return (
            f"SURVIVES this rung — detect {self.detect_auc} against sham {self.sham_auc} "
            f"(margin {self.margin}), paired {self.paired_rate} CI {self.paired_ci}"
        )


def evaluate(
    scorer: Scorer,
    texts: Iterable[str],
    *,
    metric: str,
    donors: Sequence[str] = (),
    doses: tuple[float, ...] = DOSES,
    direction: int = -1,
) -> Result:
    """Run the ablation ladder and every control over a set of chapters.

    `direction` says which way damage is expected to move the score: -1 if damage lowers it,
    +1 if damage raises it. It is required rather than inferred, for the reason
    `calibration.Direction`'s own docstring gives — a guessed direction inverts the result
    silently, "the failure mode that produces a confidently backwards quality signal". Nothing
    here fits the direction to the data.
    """
    chapters = list(texts)
    degrader_keys = {ablation.key for ablation in DEGRADERS}
    sham_keys = {ablation.key for ablation in SHAMS}

    originals: list[float] = []
    original_lengths: list[float] = []
    degraded: list[float] = []
    degraded_lengths: list[float] = []
    shammed: list[float] = []
    per_key: dict[str, list[tuple[float, float]]] = {}
    wins = 0
    pairs = 0

    for index, text in enumerate(chapters):
        donor = donors[index % len(donors)] if donors else ""
        base: float | None = None
        for key, _sign, _item, dose, damaged in variants(text, donor=donor, doses=doses):
            score = scorer(damaged)
            length = float(len(damaged.split()))
            if key == "original":
                base = score
                originals.append(score)
                original_lengths.append(length)
                continue
            if base is None:  # pragma: no cover - `variants` yields the original first
                continue
            if key in degrader_keys:
                degraded.append(score)
                degraded_lengths.append(length)
                per_key.setdefault(key, []).append((dose, score - base))
                # The paired test: did this chapter's own damaged copy move the expected way?
                pairs += 1
                if (score - base) * direction > 0:
                    wins += 1
            elif key in sham_keys:
                shammed.append(score)

    result = Result(metric=metric, n_chapters=len(chapters))
    # Orientation: `auc(positive, negative)` reads "positive scores above negative". Damage is
    # put on whichever side `direction` says it should be *higher* on, so a surviving metric
    # always reports an AUC above 0.5 and the number means the same thing for every candidate.
    if direction < 0:
        result.detect_auc = auc(originals, degraded)
        result.sham_auc = auc(originals, shammed)
        result.length_auc = auc(original_lengths, degraded_lengths)
    else:
        result.detect_auc = auc(degraded, originals)
        result.sham_auc = auc(shammed, originals)
        result.length_auc = auc(degraded_lengths, original_lengths)

    result.paired_rate = round(wins / pairs, 4) if pairs else 0.5
    result.paired_ci = binomial_ci(wins, pairs)
    result.paired_n = pairs

    for key, observations in sorted(per_key.items()):
        dose_values = [dose for dose, _ in observations]
        deltas = [delta for _, delta in observations]
        signed = [delta * direction for delta in deltas]
        result.per_ablation[key] = {
            "n": len(observations),
            "mean_delta": round(statistics.fmean(deltas), 5) if deltas else 0.0,
            # Positive dose_rho means more damage moves the score further in the expected
            # direction. This is the monotonicity claim, and it is per-ablation because a
            # metric can be monotone in shuffling and flat in dialogue flattening — which is
            # information about *which item* it reaches, not noise to be averaged away.
            "dose_rho": round(spearman(dose_values, signed), 4),
            "hit_rate": round(sum(1 for s in signed if s > 0) / len(signed), 4),
        }

    if result.length_auc > 0.6:
        result.notes.append(
            f"length alone separates at {result.length_auc}; `sentence_deletion` is the only "
            "length-changing degrader and dominates this number — rerun without it to read "
            "the rest"
        )
    if not shammed:
        result.notes.append("no sham variants were produced; the control did not run")
    return result


def selftest() -> None:
    """Three scorers with known answers, because an evaluation harness needs its own control.

    A harness that reports 0.85 for a real metric is only believable if it reports the right
    thing for scorers whose answers are known in advance. The middle case is the one worth
    reading, and it is why this harness exists rather than a plain AUC:

    - **random** — must land at chance and must be called dead.
    - **change-detector** — an oracle that perfectly answers "was this text modified at all".
      It scores `detect = 1.0`, which is a perfect headline, **and it must still be called
      dead**, because it scores `sham = 1.0` too. This is the `tricolon_rate` failure exactly:
      a number that looks like the project's first working detector until the control is read
      beside it. If this case ever reports SURVIVES, the sham control has stopped working and
      nothing else in this directory can be believed.
    - **damage-detector** — an oracle that responds to degraders and ignores shams. The only
      one that may survive.
    """
    import random as _random
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from corpus_io import mol_chapters

    chapters = [unit.text for unit in mol_chapters()[:8]]
    donors = [unit.text for unit in mol_chapters()[60:68]]

    noise = _random.Random(0)
    blind = evaluate(
        lambda text: noise.random(), chapters, metric="control.random", donors=donors
    )
    print(f"random scorer      detect={blind.detect_auc} sham={blind.sham_auc} "
          f"paired={blind.paired_rate} {blind.paired_ci}")
    print(f"  -> {blind.verdict()}")

    originals = set(chapters)
    changed = evaluate(
        lambda text: 0.0 if text in originals else -1.0,
        chapters, metric="control.change_detector", donors=donors,
    )
    print(f"change-detector    detect={changed.detect_auc} sham={changed.sham_auc} "
          f"margin={changed.margin} paired={changed.paired_rate}")
    print(f"  -> {changed.verdict()}")

    # The positive control. Built by scoring the *sham* variants as undamaged, which is the
    # information a real metric would have to earn: shams are edits that preserve craft, and
    # a metric that survives here is one that tells edit from damage rather than text from
    # text. Constructed by regenerating the sham variants and treating membership as the
    # oracle's knowledge, so nothing about the degraders leaks into it.
    unharmed = set(originals)
    for index, text in enumerate(chapters):
        donor = donors[index % len(donors)]
        for _key, sign, _item, _dose, variant in variants(text, donor=donor):
            if sign == 0:
                unharmed.add(variant)
    damage = evaluate(
        lambda text: 0.0 if text in unharmed else -1.0,
        chapters, metric="control.damage_detector", donors=donors,
    )
    print(f"damage-detector    detect={damage.detect_auc} sham={damage.sham_auc} "
          f"margin={damage.margin} paired={damage.paired_rate} {damage.paired_ci}")
    print(f"  -> {damage.verdict()}")


if __name__ == "__main__":
    selftest()
