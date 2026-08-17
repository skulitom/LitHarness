"""Score a candidate craft metric against manufactured ground truth, controls included.

Takes any `scorer: (text) -> float` and returns the numbers that decide whether it survives.
The controls are not optional arguments — they are computed in the same pass and reported
beside the headline, because `plan/craft-corpus.md` §2 makes that a rule and every proxy in the
refutation ledger died to a control that was computed afterwards or not at all.

**Four numbers, and the headline is the least important of them.**

1. `detect_auc` — the rate at which a chapter's degraded variants move the score in the
   declared damage direction (ties at half), averaged over chapters. This is the rank AUC of
   each chapter's variants against that chapter's own original, so 0.5 is chance. The headline.
2. `sham_auc` — the same statistic against `SHAMS`, which change the text and should not change
   quality. **This is the era control's analogue.** A metric with detect 0.85 and sham 0.80 has
   found *edited-ness*, not damage, and is dead exactly as `tricolon_rate` was dead at 0.629
   against a control of 0.606. The reported margin charges the sham as a distance from chance,
   in either direction — see `Result.margin` for the measured reason.
3. `dose_rho` — Spearman of score against ablation strength, per degrader. Monotonicity is the
   claim; detection at full strength alone is detection of vandalism.
4. `length_auc` — the same within-chapter statistic computed for raw word count. §1a.1's
   shallow incumbent. Five of six degraders preserve length exactly, so their variants tie at
   half and this number is `sentence_deletion`'s — which is the honest shape: length can only
   claim what length can see, and a metric has to beat what it claims.

**Paired by construction — in the statistics, not only in the design.** Every comparison is
within one chapter: the degraded text and its own original. Author, era, story, genre, tags,
maturity and cadence are identical on both sides of every pair, which is the property the
refutation ledger says the between-cohort designs never had. The first version of this file
said that while computing `detect_auc` as a *pooled* AUC of all originals against all degraded
texts — mostly cross-chapter comparisons, which readmit exactly the chapter-level differences
the pairing was built to hold fixed. Every `_auc` here is now a mean of within-chapter
comparisons. What pairing costs is that a within-chapter effect says nothing about
between-chapter ranking, and nothing here claims one. `paired_ci` is a chapter-resampled
bootstrap rather than a Wilson interval over pooled pairs, because ~24 pairs that share one
original, one author and one stretch of one story are not 24 independent trials — the Wilson
interval was narrower than the evidence supported, and it fed the clause that separates
UNDETERMINED from SURVIVES, which is the clause a false survivor would enter through.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from ablate import DEGRADERS, DOSES, SHAMS, variants

Scorer = Callable[[str], float]


def auc(positive: Sequence[float], negative: Sequence[float]) -> float:
    """Rank AUC with ties at half. Copied in behaviour from `tools/build_craft_profile.py`.

    Reimplemented rather than imported so this file runs under either interpreter, and checked
    in `selftest()` against the O(n²) pairwise definition on tie-heavy draws — tie handling is
    where rank implementations usually diverge, and it is the check that keeps this and the
    `tools/` twin comparable. **If you change tie handling here, change it there**, or two
    experiments stop being comparable and nothing will say so.
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


def directional_rate(deltas: Sequence[float], direction: int) -> float:
    """Fraction of deltas that moved in the declared direction, ties at half.

    Over one chapter's variants this *is* the rank AUC of the variants against the chapter's
    single original — P(variant on the damaged side of its own original), ties split — which
    is why the fields it feeds keep the `_auc` suffix and the 0.5-is-chance reading.
    """
    moved = sum(1.0 if delta * direction > 0 else 0.5 if delta == 0 else 0.0 for delta in deltas)
    return moved / len(deltas)


def cluster_ci(
    chapter_counts: Sequence[tuple[int, int]], draws: int = 2000, seed: int = 11
) -> tuple[float, float]:
    """95% chapter-resampled bootstrap interval for the pooled win rate.

    Replaces a Wilson interval over pooled pairs. Wilson answers the right question only for
    independent trials, and these are not: every chapter contributes ~24 pairs that share one
    original, one author and one stretch of one story, so the effective sample size sits
    nearer the chapter count than the pair count. Resampling whole chapters keeps that
    dependence inside every draw, and the interval widens accordingly — the honest direction,
    since this interval feeds the clause that separates UNDETERMINED from SURVIVES and a
    too-narrow interval is how a false survivor gets minted.

    Deterministic: the seed is fixed, so a re-run reports the interval its predecessor did.
    Fewer than two chapters support no resampling — one cluster drawn from itself has width
    zero and would dress certainty in interval notation — so the interval is (0.0, 1.0), which
    no verdict clause can read as evidence.
    """
    usable = [(wins, pairs) for wins, pairs in chapter_counts if pairs]
    if len(usable) < 2:
        return (0.0, 1.0)
    rng = random.Random(seed)
    rates: list[float] = []
    for _ in range(draws):
        wins = 0
        pairs = 0
        for _ in range(len(usable)):
            w, p = usable[rng.randrange(len(usable))]
            wins += w
            pairs += p
        rates.append(wins / pairs)
    rates.sort()
    low = rates[round(0.025 * (draws - 1))]
    high = rates[round(0.975 * (draws - 1))]
    return (round(low, 4), round(high, 4))


@dataclass
class Result:
    """One candidate metric's verdict, with every control beside the headline."""

    metric: str
    n_chapters: int
    #: Mean over chapters of the within-chapter damaged-side rate; 0.5 is chance.
    detect_auc: float = 0.5
    #: The same statistic over sham variants. Distance from 0.5 is bad in either direction.
    sham_auc: float = 0.5
    #: The same statistic computed for raw word count in place of the metric.
    length_auc: float = 0.5
    #: Pooled fraction of degraded variants moved strictly the declared way; a tie is not
    #: evidence of movement, so ties count against — stricter than the `_auc` fields.
    paired_rate: float = 0.5
    #: Chapter-resampled bootstrap 95% interval for `paired_rate` — see `cluster_ci`.
    paired_ci: tuple[float, float] = (0.0, 1.0)
    paired_n: int = 0
    per_ablation: dict[str, dict[str, float]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def margin(self) -> float:
        """Detect's height above chance minus the sham's distance from chance, either way.

        The first formulation was `detect_auc - sham_auc`, and the first CDG battery measured
        why that is wrong: its sham moved *opposite* to the declared damage direction (sham
        0.28 against detect 0.52), and the subtraction rewarded the wrong-way movement with a
        margin of +0.23 — the control that should have spent the result was credited to it.
        A sham response is disqualifying whichever way it points, so it is charged as a
        distance. A metric moving *with* damage and *away* from shams is the only shape that
        scores here.
        """
        return round((self.detect_auc - 0.5) - abs(self.sham_auc - 0.5), 4)

    def verdict(self) -> str:
        """A one-line reading, phrased so it can say "dead" without hedging."""
        if self.detect_auc < 0.55:
            return (
                f"DEAD — detect {self.detect_auc}: damage does not move the score in the "
                "declared direction"
            )
        if self.margin < 0.05:
            return (
                f"DEAD — detect {self.detect_auc} but sham at {self.sham_auc}; it is "
                "responding to the text having been edited, not to the damage"
            )
        if self.detect_auc - 0.5 <= abs(self.length_auc - 0.5):
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
    here fits the direction to the data, and movement *against* the declared direction is
    never credited: a metric that separates the wrong way is dead, not inverted.
    """
    chapters = list(texts)
    degrader_keys = {ablation.key for ablation in DEGRADERS}
    sham_keys = {ablation.key for ablation in SHAMS}

    per_key: dict[str, list[tuple[float, float]]] = {}
    detect_rates: list[float] = []
    sham_rates: list[float] = []
    length_rates: list[float] = []
    chapter_pairs: list[tuple[int, int]] = []
    wins = 0
    pairs = 0

    for index, text in enumerate(chapters):
        donor = donors[index % len(donors)] if donors else ""
        base: float | None = None
        base_length = 0.0
        degrader_deltas: list[float] = []
        length_deltas: list[float] = []
        sham_deltas: list[float] = []
        for key, _sign, _item, dose, damaged in variants(text, donor=donor, doses=doses):
            score = scorer(damaged)
            length = float(len(damaged.split()))
            if key == "original":
                base = score
                base_length = length
                continue
            if base is None:  # pragma: no cover - `variants` yields the original first
                continue
            if key in degrader_keys:
                degrader_deltas.append(score - base)
                length_deltas.append(length - base_length)
                per_key.setdefault(key, []).append((dose, score - base))
            elif key in sham_keys:
                sham_deltas.append(score - base)
        # The paired test: did this chapter's own damaged copies move the expected way?
        # Wins are strict — a tie is not evidence of movement.
        chapter_wins = sum(1 for delta in degrader_deltas if delta * direction > 0)
        wins += chapter_wins
        pairs += len(degrader_deltas)
        chapter_pairs.append((chapter_wins, len(degrader_deltas)))
        if degrader_deltas:
            detect_rates.append(directional_rate(degrader_deltas, direction))
            length_rates.append(directional_rate(length_deltas, direction))
        if sham_deltas:
            sham_rates.append(directional_rate(sham_deltas, direction))

    result = Result(metric=metric, n_chapters=len(chapters))
    result.detect_auc = round(statistics.fmean(detect_rates), 4) if detect_rates else 0.5
    result.sham_auc = round(statistics.fmean(sham_rates), 4) if sham_rates else 0.5
    result.length_auc = round(statistics.fmean(length_rates), 4) if length_rates else 0.5
    result.paired_rate = round(wins / pairs, 4) if pairs else 0.5
    result.paired_ci = cluster_ci(chapter_pairs)
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
            f"raw length separates at {result.length_auc}; `sentence_deletion` is the only "
            "length-changing degrader and every other variant ties at half, so this is "
            "deletion's number — read the metric's own `sentence_deletion` row against it"
        )
    if not sham_rates:
        result.notes.append("no sham variants were produced; the control did not run")
    return result


def selftest() -> None:
    """Scorers with known answers, because an evaluation harness needs its own control.

    A harness that reports 0.85 for a real metric is only believable if it reports the right
    thing for scorers whose answers are known in advance. First `auc` itself is checked
    against the O(n²) definition it compresses; then three scorers run, and the middle case
    is the one worth reading — it is why this harness exists rather than a plain AUC:

    - **random** — must land at chance and must be called dead.
    - **change-detector** — an oracle that perfectly answers "was this text modified at all".
      It scores `detect = 1.0`, which is a perfect headline, **and it must still be called
      dead**, because it scores `sham = 1.0` too. This is the `tricolon_rate` failure exactly:
      a number that looks like the project's first working detector until the control is read
      beside it. If this case ever reports SURVIVES, the sham control has stopped working and
      nothing else in this directory can be believed.
    - **damage-detector** — an oracle that responds to degraders and ignores shams. The only
      one that may survive.

    Each expectation is asserted, not only printed — a selftest whose failures scroll past is
    a selftest nobody runs twice.
    """
    import random as _random
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from corpus_io import mol_chapters

    # `auc` against the pairwise definition, on small integer grids because collisions are
    # where rank implementations diverge. Tolerance is the 4-decimal rounding `auc` applies.
    check = _random.Random(1)
    for _ in range(300):
        pos = [check.randrange(6) / 2.0 for _ in range(check.randrange(1, 9))]
        neg = [check.randrange(6) / 2.0 for _ in range(check.randrange(1, 9))]
        brute = sum(
            1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg
        ) / (len(pos) * len(neg))
        assert abs(auc(pos, neg) - brute) <= 5.1e-5, (pos, neg, auc(pos, neg), brute)
    print("auc matches the pairwise definition over 300 tie-heavy draws")

    chapters = [unit.text for unit in mol_chapters()[:8]]
    donors = [unit.text for unit in mol_chapters()[60:68]]

    noise = _random.Random(0)
    blind = evaluate(
        lambda text: noise.random(), chapters, metric="control.random", donors=donors
    )
    print(f"random scorer      detect={blind.detect_auc} sham={blind.sham_auc} "
          f"paired={blind.paired_rate} {blind.paired_ci}")
    print(f"  -> {blind.verdict()}")
    assert blind.verdict().startswith("DEAD"), blind.verdict()

    originals = set(chapters)
    changed = evaluate(
        lambda text: 0.0 if text in originals else -1.0,
        chapters, metric="control.change_detector", donors=donors,
    )
    print(f"change-detector    detect={changed.detect_auc} sham={changed.sham_auc} "
          f"margin={changed.margin} paired={changed.paired_rate}")
    print(f"  -> {changed.verdict()}")
    assert changed.verdict().startswith("DEAD"), changed.verdict()

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
    assert damage.verdict().startswith("SURVIVES"), damage.verdict()


if __name__ == "__main__":
    selftest()
