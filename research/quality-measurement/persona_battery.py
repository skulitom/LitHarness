"""Gate 0 and gate 1 of the persona-reader validity program, run against manufactured damage.

`personas.py` supplies the readers, `elicit.py` the calls, `ablate.py` the ground truth and
`evaluate.py` the pass/fail ladder. This is the thin driver: what belongs here is *which*
passages, how many samples, and the arithmetic for the kill conditions
`plan/persona-reader-validity.md` §8 pre-registers. Every methodological choice lives in the
four instruments.

**Gate 0 runs first because it is the cheapest kill.** BRIEF.md §2 Pass 5 earned the rule — check
within-unit reliability before believing any per-unit statistic — and tree-Haar scale energy died
to it at `ICC(1) = 0.270`, its within-book sd equal to its between-book sd. The protocol's `n >= 5`
samples per persona per boundary is the first thing in this project that makes the same quantity
computable for a model-based reader. A panel whose within-passage sample variance matches its
between-passage variance is noise wearing a verdict, and no amount of downstream ablation
rescues it.

**Gate 1 is `evaluate.verdict()`'s existing ladder, not a new threshold.** The panel is reduced
to one scalar per passage — the would-stop rate — and scored on all four rungs in order: detect
above 0.55, `margin = (detect - 0.5) - |sham - 0.5|` above 0.05 read per sham, the §1a.1
word-count incumbent, then the chapter-resampled paired interval. `direction=+1` because damage
is declared to *raise* would-stop. Nothing new is invented; the panel inherits the rung that
actually finished CDG, which is the word count one.

**Passages must be prose the panel's model has not memorised, and the default refuses to be
convenient about it.** BRIEF.md §2 Pass 6's transferable rule is that a model-based measure
validated on published fiction either runs on un-memorised text or measures its familiarity term
explicitly — the rename sham moved CDG 2.0x further than the strongest real degrader, upward and
dose-monotone, while real damage sat at chance. So `--passages` (a directory of `litharness
export` output) and `--fixtures` (this project's own golden scenes) are the supported sources,
and pointing this at the published corpus needs `--published`, which stamps a memorisation
warning into the summary and cannot be un-stamped.

**The manipulation set is `ablate.PERSONA_SET`, and de-stake is the arm that carries the reader
claim.** §5 of the protocol names de-stake, filler-inject, voice-flatten and confusion-inject,
with character-rename and re-whitespace as the placebo pair. Present now: `destake` with its
matched control `deplete_matched`, `dialogue_flatten` (voice-flatten), `rename_entities` and
`rewhitespace` (the placebo pair, exactly), plus the structural set the CDG battery already used.
`filler_inject` covers the fourth, and is the only arm that *adds* words — which also forces
§1a.1's word-count incumbent to separate two arms whose lengths move in opposite directions for
the same declared damage direction. **Still absent: confusion-inject**, because it has to know
what a passage's referents are and the only thing that knows is a generator, which
`ablate.dialogue_flatten`'s docstring already refused to admit to this ground truth. A gate-1 pass
therefore leaves one named damage class untested, and the entry recording it has to say so.

**Filler's confound is checked interventionally, not argued away.** Canned filler is not in the
passage's voice, so a reader may be answering "these lines do not belong" rather than "this is
padded". `filler_reason_signature` in the summary reads which codes the filler arm actually drew:
`padding` is the intended response and `flat-voice` is the intrusion's signature, so a filler arm
dominated by `flat-voice` has measured a style intrusion and not bloat.

**De-stake is read against `deplete_matched` or it is not read at all.** The two arms delete the
*same number of words* — verified exact on the chapters this was built against — and differ only
in which sentences went: stake-bearing versus zero-stake. So `destake` minus `deplete_matched` is
the effect of removing stakes with length, position and quantity of deletion held fixed, and it
is the one number in this summary that speaks to the protocol's central hypothesis. If the two
move the panel equally, the stake lexicon selected nothing a reader noticed and the
reader-specific reading is unsupported — the `tricolon_rate` shape, where the headline survived
exactly as long as it took to read the control beside it. `stake_coverage` is reported per
passage because de-stake can only remove what the lexicon finds, and a null over low-stakes
passages is a report of absence rather than a result.

**Every numeric threshold gets its null simulated at the actual n.** Also Pass 5: the log-log
slope estimator was biased low at small n and manufactured 0.03 of effect from nothing. The
inter-persona rank correlation is the threshold most exposed to it here — with a handful of
passages and five binary samples, the sampling distribution of a pairwise correlation between
two noisy persona means is wide — so the observed value is reported beside a simulated null at
this run's own dimensions rather than against the pre-registered 0.9 alone.

Run offline. This spends money:

    uv run --extra persona python research/quality-measurement/persona_battery.py --fixtures
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import _SENT, DOSES, PERSONA_SET, paragraphs, stake_score, variants  # noqa: E402
from elicit import (  # noqa: E402
    PANEL_MODEL,
    SPOT_MODEL,
    Elicitor,
    digest,
    positional_bias,
)
from evaluate import evaluate, spearman  # noqa: E402
from personas import PANEL  # noqa: E402

#: Calls above which the run refuses without `--yes`. Two calls per cell, and a cell is one
#: (passage, persona, sample) — a full 30-passage sweep is five figures of calls, which is not a
#: thing to start by accident from a command line.
CALL_GUARD = 2_000
NULL_REPLICATES = 2_000
NULL_SEED = 20260817


def icc1(groups: list[list[float]]) -> dict[str, float]:
    """One-way random-effects ICC(1) over per-group replicates.

    The quantity Pass 5 demanded and this project had never run: the share of total variance
    that sits *between* units rather than within them. Near zero means the replicates of one
    unit disagree as much as different units do, which is the reading that killed tree-Haar.

    Unequal group sizes are handled by using the mean replicate count, which is the standard
    approximation and is honest here because the schedule is balanced by construction — an
    unbalanced call is a run with refusals in it, and the refusal count is reported beside this.
    """
    usable = [group for group in groups if len(group) >= 2]
    if len(usable) < 2:
        return {"icc1": float("nan"), "groups": len(usable), "k_mean": 0.0,
                "ms_between": float("nan"), "ms_within": float("nan")}
    k_mean = statistics.fmean(len(group) for group in usable)
    grand = statistics.fmean(value for group in usable for value in group)
    means = [statistics.fmean(group) for group in usable]
    ms_between = k_mean * sum((mean - grand) ** 2 for mean in means) / (len(usable) - 1)
    within_df = sum(len(group) - 1 for group in usable)
    ms_within = sum(
        (value - mean) ** 2 for group, mean in zip(usable, means, strict=True) for value in group
    ) / within_df if within_df else float("nan")
    denominator = ms_between + (k_mean - 1) * ms_within
    value = (ms_between - ms_within) / denominator if denominator else float("nan")
    return {
        "icc1": round(value, 4) if not math.isnan(value) else float("nan"),
        "groups": len(usable),
        "k_mean": round(k_mean, 2),
        "ms_between": round(ms_between, 5),
        "ms_within": round(ms_within, 5),
    }


def variance_split(cells: dict[tuple[str, str], float]) -> dict[str, float]:
    """Persona main effect against passage main effect, as sums of squares.

    The caricature kill condition: if the response tracks the costume harder than the text, the
    persona term dominates and the instrument is a persona machine rather than a reader. Reported
    as a ratio so the pre-registered comparison (`persona >= passage`) is one number to read.
    """
    if not cells:
        return {"persona_ss": 0.0, "passage_ss": 0.0, "ratio": float("nan")}
    passages = sorted({passage for passage, _ in cells})
    personas = sorted({persona for _, persona in cells})
    grand = statistics.fmean(cells.values())

    def group_ss(keys: list[str], index: int) -> float:
        total = 0.0
        for key in keys:
            values = [v for k, v in cells.items() if k[index] == key]
            if values:
                total += len(values) * (statistics.fmean(values) - grand) ** 2
        return total

    passage_ss = group_ss(passages, 0)
    persona_ss = group_ss(personas, 1)
    return {
        "persona_ss": round(persona_ss, 5),
        "passage_ss": round(passage_ss, 5),
        "ratio": round(persona_ss / passage_ss, 4) if passage_ss else float("inf"),
    }


def inter_persona_rho(cells: dict[tuple[str, str], float]) -> dict[str, object]:
    """Mean pairwise rank correlation between personas over shared passages.

    The collapse kill condition (>= 0.9 means one judge in costumes), reported beside a null
    simulated at this run's own dimensions — Pass 5's rule, and load-bearing here: with few
    passages and binary samples, independent personas produce a wide correlation distribution
    and a bare 0.9 threshold would be read against an assumed-narrow one.
    """
    passages = sorted({passage for passage, _ in cells})
    personas = sorted({persona for _, persona in cells})
    series: dict[str, list[float]] = {}
    for persona in personas:
        column = [cells.get((passage, persona)) for passage in passages]
        if all(value is not None for value in column):
            series[persona] = [float(value) for value in column]  # type: ignore[arg-type]

    # NaN is a real outcome here, not an edge case: `spearman` divides by a zero variance, so a
    # persona whose stop-rate is *constant across passages* correlates with nothing. That is
    # exactly what the positivity floor looks like — a reader that never stops — so undefined
    # pairs are counted and reported rather than silently dropped or silently averaged.
    #
    # Averaging them was the first version's bug, and it was invisible until `selftest` printed a
    # null p95 of -0.14 for independent personas, which no correlation null can have.
    # `statistics.fmean` of anything containing NaN is NaN, and `sorted()` on a list containing
    # NaN does not raise — it returns a silently mis-ordered list, because every NaN comparison
    # is False — so one constant draw in a replicate poisoned that replicate's mean and the
    # poisoned means then corrupted the percentile they were sorted for. At a 0.33 base rate,
    # 0.8% of twelve-passage draws come out constant, which is ~6% of replicates with four
    # personas: frequent enough to wreck the quantile, rare enough never to look like a bug.
    pairs = [
        (a, b, spearman(series[a], series[b]))
        for a, b in itertools.combinations(sorted(series), 2)
    ]
    defined = [rho for _, _, rho in pairs if not math.isnan(rho)]
    observed = statistics.fmean(defined) if defined else float("nan")

    base_rate = statistics.fmean(cells.values()) if cells else 0.0
    rng = random.Random(NULL_SEED)
    n_passages, n_personas = len(passages), max(len(series), 2)
    null: list[float] = []
    for _ in range(NULL_REPLICATES):
        draws = [
            [float(rng.random() < base_rate) for _ in range(n_passages)]
            for _ in range(n_personas)
        ]
        sim = [
            rho
            for rho in (spearman(a, b) for a, b in itertools.combinations(draws, 2))
            if not math.isnan(rho)
        ]
        if sim:
            null.append(statistics.fmean(sim))
    null.sort()
    return {
        "mean_rho": round(observed, 4) if defined else float("nan"),
        "pairs": [
            {"a": a, "b": b, "rho": None if math.isnan(rho) else round(rho, 4)}
            for a, b, rho in pairs
        ],
        "undefined_pairs": len(pairs) - len(defined),
        "undefined_note": (
            "a pair is undefined when one persona's rate is constant across passages — read it "
            "with the positivity floor, not as missing data"
        ),
        "null_p95": round(null[int(0.95 * (len(null) - 1))], 4) if null else float("nan"),
        "null_replicates": len(null),
        "null_discarded": NULL_REPLICATES - len(null),
        "note": "independent-persona null simulated at this run's passages x base rate",
    }


def _split(units: list[tuple[str, str]], n_scored: int) -> tuple[list[tuple[str, str]], list[str]]:
    """Scored passages and a transplant donor pool, disjoint where the source allows it.

    `transplant` grafts a length-matched run from a donor into the host, and `evaluate` pairs
    host `index` with `donors[index % len(donors)]`. Handing it the scored list itself therefore
    makes every host its own donor — a graft from a text into itself, which is not the degrader
    the ablation claims to be and would enter the detect rate as a near-null. So donors come from
    the passages *beyond* the scored slice; when the source has none to spare, the scored list is
    rotated by one, which keeps host and donor distinct for any set larger than one.
    """
    scored = units[:n_scored]
    spare = [text for _, text in units[n_scored:]]
    if spare:
        return scored, spare
    if len(scored) > 1:
        texts = [text for _, text in scored]
        return scored, texts[1:] + texts[:1]
    return scored, []


def stake_coverage(text: str) -> dict[str, float]:
    """How much stake-bearing material a passage has, before any manipulation runs.

    Reported per passage because `destake` can only remove what the lexicon finds: a passage
    with no scoring sentences contributes nothing to that arm, and `variants` drops the
    unchanged text rather than emitting a mislabelled pair. Without this number a run over
    low-stakes passages would report a null for de-stake that was really a report of absence.
    """
    sentences = [piece for block in paragraphs(text) for piece in _SENT.split(block)]
    scored = [piece for piece in sentences if stake_score(piece) > 0]
    words = sum(len(piece.split()) for piece in scored)
    total_words = max(len(text.split()), 1)
    return {
        "sentences": len(sentences),
        "stake_sentences": len(scored),
        "stake_sentence_share": round(len(scored) / max(len(sentences), 1), 4),
        "stake_word_share": round(words / total_words, 4),
    }


#: Which arm carries a claim, declared here so it is declared *before* the data rather than
#: chosen after it. This is the answer to the selection-family question, and the answer is not an
#: alpha division: `research/preference-power/FINDINGS.md` §7 measured what dividing alpha does to
#: this family of estimator — it divides the *rank* the bootstrap reads, down to the 3rd of 2,000
#: at C=20, where Monte Carlo noise dominates the data and one fixed verdict set certifies under
#: 35% of seeds. A correction that turns a bound into a seed lottery is not a correction.
#:
#: The protocol never needed one. §5 names a single primary comparison in advance — de-stake
#: against its matched-deletion control — so the family is C=1 and there is nothing to divide.
#: The placebos are controls rather than discoveries: they were declared to sit at chance, and a
#: control confirming its own prediction adds no comparison. Everything else is **exploratory**
#: and is labelled so in the summary, because an arm that happens to move must not be readable as
#: a result. An interesting exploratory arm is a hypothesis for a fresh run, not a finding.
PRE_REGISTRATION: dict[str, str] = {
    "destake": "primary",
    "deplete_matched": "primary-control",
    "rename_entities": "placebo",
    "respell": "placebo",
    "rewhitespace": "placebo",
    "filler_inject": "exploratory",
    "dialogue_flatten": "exploratory",
    "paragraph_shuffle": "exploratory",
    "sentence_shuffle": "exploratory",
    "connective_scramble": "exploratory",
    "transplant": "exploratory",
    "sentence_deletion": "exploratory",
}


def annotate_arms(per_ablation: dict[str, dict[str, float]]) -> dict[str, object]:
    """Tag each arm with the standing it was given before the run.

    Carried in the summary so the reading order is fixed by the record rather than by whoever
    reads it: one primary comparison, three controls that must sit at chance, and a set of
    exploratory arms that can generate hypotheses and cannot close them.
    """
    tagged = {
        key: {**row, "standing": PRE_REGISTRATION.get(key, "unregistered")}
        for key, row in per_ablation.items()
    }
    unregistered = sorted(k for k, v in tagged.items() if v["standing"] == "unregistered")
    return {
        "arms": tagged,
        "primary_comparison": "destake minus deplete_matched",
        "family_size": 1,
        "unregistered_arms": unregistered,
        "reading": (
            "one primary comparison declared before the data, so the family is C=1 and no alpha "
            "division applies — FINDINGS.md §7 measured that dividing alpha turns this bound into "
            "a seed lottery. Placebos are controls, not comparisons. Exploratory arms generate "
            "hypotheses for a fresh run and cannot close one"
        ),
    }


def two_way_ci(
    cells: dict[tuple[str, str], tuple[float, int]],
    *, draws: int = 2000, seed: int = 11,
) -> tuple[float, float]:
    """95% interval for a rate, resampling **both** cluster margins: passages and personas.

    **`evaluate.cluster_ci` is anti-conservative for this instrument, and the amount was
    measured rather than suspected.** It resamples passages only, pooling the four personas
    inside each passage as if independent — but a taste-anchored panel is heterogeneous *by
    construction*, which is exactly the condition `research/preference-power/FINDINGS.md` §5
    identifies as governing the bound: "whichever cluster dimension is small and heterogeneous".
    Four personas is as starved as a dimension gets.

    Measured under the null at this battery's own n (10 passages x 4 personas x 2 orientations,
    4,000 replicates, nominal one-sided 2.5%):

        sigma_persona   one-way   two-way
                  0.0     4.70%     0.33%
                  0.4     8.60%     1.00%
                  0.8    17.97%     3.12%
                  1.2    23.88%     4.83%

    The one-way interval also *narrows* as heterogeneity rises (0.202 to 0.176 mean width), which
    is the mechanism rather than a curiosity: between-persona variance never enters the resample,
    so pooling more correlated observations inside a passage makes each passage's rate look more
    precise than it is. Two-way errs conservative where one-way errs anti-conservative, at roughly
    double the width — and that width is the evidence: ten passages and four personas do not
    support a narrow bound. Conservative is the direction this project already chose for the same
    reason §69 chose over-invalidation.

    The resampling shape is the bilinear form `research/preference-power/bound.py` verifies for
    the shipped estimator: with `na` the passage multiplicities and `nb` the persona
    multiplicities, `total = na' C nb` and `won = na' S nb`. Aggregating a cell before weighting
    it is algebra, not approximation.
    """
    passages = sorted({a for a, _ in cells})
    personas = sorted({b for _, b in cells})
    if len(passages) < 2 or len(personas) < 2:
        return (0.0, 1.0)
    rng = random.Random(seed)
    rates: list[float] = []
    for _ in range(draws):
        na: dict[str, int] = {}
        for _ in passages:
            key = passages[rng.randrange(len(passages))]
            na[key] = na.get(key, 0) + 1
        nb: dict[str, int] = {}
        for _ in personas:
            key = personas[rng.randrange(len(personas))]
            nb[key] = nb.get(key, 0) + 1
        won = total = 0.0
        for (a, b), (score, count) in cells.items():
            weight = na.get(a, 0) * nb.get(b, 0)
            if weight:
                won += weight * score
                total += weight * count
        if total:
            rates.append(won / total)
    if not rates:
        return (0.0, 1.0)
    rates.sort()
    return (round(rates[round(0.025 * (len(rates) - 1))], 4),
            round(rates[round(0.975 * (len(rates) - 1))], 4))


def pairwise_interval(comparisons: list[Any], panel_model: str,
                      tie_policy: str) -> dict[str, object]:
    """The two-way interval over every scored comparison, with its own reading attached."""
    cells: dict[tuple[str, str], tuple[float, int]] = {}
    for comparison in comparisons:
        if comparison.model != panel_model or comparison.refused:
            continue
        if comparison.choice == "neither" and tie_policy == "drop":
            continue
        score = 0.5 if comparison.choice == "neither" else float(comparison.chose_variant)
        passage = comparison.pair_id.split("|")[0]
        key = (passage, comparison.persona_id)
        prior_score, prior_count = cells.get(key, (0.0, 0))
        cells[key] = (prior_score + score, prior_count + 1)
    low, high = two_way_ci(cells)
    return {
        "low": low,
        "high": high,
        "passages": len({a for a, _ in cells}),
        "personas": len({b for _, b in cells}),
        "reading": (
            "resamples passages and personas both; `gate1.paired_ci` resamples passages only and "
            "over-rejects at 3.8-23.9% against a nominal 2.5% at this n. Read the fourth rung of "
            "`evaluate.verdict()` against this interval, not that one"
        ),
    }


def filler_reason_signature(by_variant: dict[str, list], panel_model: str) -> dict[str, object]:
    """Which reason codes the filler arm drew, against the codes everything else drew.

    The interventional check on `filler_inject`'s confound. Canned filler is out of voice, so the
    arm can move a panel for the wrong reason; the protocol's rule is that a reason code is valid
    only if a repair aimed at it would move the verdict, and the weaker version available here is
    whether the *intended* code dominates. `padding` is the intended response, `flat-voice` is the
    intrusion's signature, and a filler arm reading mostly `flat-voice` has measured the intrusion.

    Reported as counts and a ratio rather than a verdict, because the threshold is not
    pre-registered and inventing one after seeing the data is the move this project keeps
    refusing.
    """
    filler: dict[str, int] = {}
    baseline: dict[str, int] = {}
    for variant_id, samples in by_variant.items():
        bucket = filler if "|filler_inject@" in variant_id else baseline
        for sample in samples:
            if sample.model != panel_model or sample.refused or not sample.reason_code:
                continue
            bucket[sample.reason_code] = bucket.get(sample.reason_code, 0) + 1
    total = sum(filler.values())
    padding = filler.get("padding", 0)
    flat = filler.get("flat-voice", 0)
    return {
        "available": total > 0,
        "filler_codes": dict(sorted(filler.items(), key=lambda kv: -kv[1])),
        "other_codes": dict(sorted(baseline.items(), key=lambda kv: -kv[1])),
        "filler_samples": total,
        "padding_share": round(padding / total, 4) if total else None,
        "flat_voice_share": round(flat / total, 4) if total else None,
        "reading": (
            "`padding` is the intended response to injected filler; `flat-voice` is the "
            "signature of the out-of-voice confound. A filler arm dominated by flat-voice has "
            "measured a style intrusion rather than bloat. No threshold is pre-registered — "
            "these are counts, not a verdict"
        ),
    }


def source_label(args: argparse.Namespace) -> str:
    """Which corpus this run scored, and whether the panel model has plausibly memorised it.

    **Total over the sources on purpose, and it raises rather than defaulting.** The first
    version was a chained conditional ending in `else "published"`, and `--book-db` — added
    afterwards — fell straight through it: a run on this system's own un-memorised prose recorded
    itself as having scored the published corpus. The memorisation warning was keyed separately
    and stayed correct, so nothing failed; the summary simply described a different experiment
    from the one that ran. A default is how that happens, so there is not one.
    """
    if args.book_db:
        return "generated:book-db"
    if args.passages:
        return "generated:export-dir"
    if args.fixtures:
        return "fixture:golden"
    if args.published:
        return "published:memorised"
    raise SystemExit("no passage source; load_passages should already have refused")


def _destake_comparison(per_ablation: dict[str, dict[str, float]]) -> dict[str, object]:
    """`destake` against its matched-deletion control, which is the reader claim in one row.

    Both arms are degraders under `direction=+1`, so both contribute to the headline detect rate
    and neither is credited as a sham. The comparison lives here instead: a positive difference
    means removing *stake-bearing* sentences moved the panel further toward would-stop than
    removing the same word count of neutral ones. A difference at or below zero says the lexicon
    found nothing a reader responded to, and the de-stake arm is deletion wearing a name.
    """
    destake_row = per_ablation.get("destake")
    matched_row = per_ablation.get("deplete_matched")
    if not destake_row or not matched_row:
        return {
            "available": False,
            "note": "one arm produced no variants — see stake_coverage; a passage with no "
                    "scoring sentences yields an unchanged text, which `variants` drops",
        }
    difference = destake_row["mean_delta"] - matched_row["mean_delta"]
    return {
        "available": True,
        "destake": destake_row,
        "deplete_matched": matched_row,
        "mean_delta_difference": round(difference, 5),
        "destake_dose_rho": destake_row["dose_rho"],
        "matched_dose_rho": matched_row["dose_rho"],
        "reading": (
            "positive difference = removing stakes moved would-stop further than removing the "
            "same word count of neutral sentences; at or below zero the de-stake arm is deletion"
        ),
    }


def load_passages(args: argparse.Namespace) -> tuple[list[tuple[str, str]], list[str]]:
    """`(passages, donors)` from whichever source was named. Memorised sources need a flag."""
    if args.book_db:
        from corpus_io import generated_scenes

        scenes = generated_scenes(
            args.book_db, book=args.book, branch=args.branch, min_words=args.min_words
        )
        if not scenes:
            raise SystemExit(
                f"no drafted scenes of at least {args.min_words} words in {args.book_db}"
            )
        units = [(scene.unit_id, scene.text) for scene in scenes]
        return _split(units, args.n_passages)
    if args.passages:
        root = Path(args.passages)
        files = sorted(path for path in root.glob("**/*.txt") if path.is_file())
        if not files:
            raise SystemExit(f"no .txt passages under {root}")
        units = [(f"export:{path.stem}", path.read_text(encoding="utf-8")) for path in files]
        return _split(units, args.n_passages)
    if args.fixtures:
        from corpus_io import fixture_scenes

        units = [(scene.unit_id, scene.text) for scene in fixture_scenes()]
        return _split(units, args.n_passages)
    if args.published:
        from corpus_io import mol_chapters

        units = [(chapter.unit_id, chapter.text) for chapter in mol_chapters()]
        return _split(units, args.n_passages)
    raise SystemExit(
        "name a passage source: --passages DIR (litharness export), --fixtures, "
        "or --published (memorised; stamps a warning into the summary)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_argument_group("passage source")
    source.add_argument("--book-db", help="a book database; drafted scenes, un-memorised")
    source.add_argument("--book", help="book id, when the database holds more than one")
    source.add_argument("--branch", help="branch id, when the book has more than one")
    source.add_argument("--min-words", type=int, default=200,
                        help="skip scenes shorter than this (--book-db only)")
    source.add_argument("--passages", help="directory of exported generated scenes (.txt)")
    source.add_argument("--fixtures", action="store_true", help="this project's golden scenes")
    source.add_argument("--published", action="store_true",
                        help="published corpus; memorised by the scoring model (stamped)")
    parser.add_argument("--pairwise", action="store_true",
                        help="blinded, position-swapped preference against each variant's "
                             "own original (§70 addendum 3). Replaces the absolute verdict, "
                             "which measured out as a constant function")
    parser.add_argument("--pair-question", choices=("preference", "intensity"),
                        default="preference",
                        help="preference asks which the reader would rather keep reading; "
                             "intensity asks which hit harder. Same pairs, different response "
                             "variable — run both to see which discriminates")
    parser.add_argument("--tie-policy", choices=("half_win", "drop"), default="half_win",
                        help="how `neither` scores. Declared before the run, per §61")
    parser.add_argument("--gate0", action="store_true",
                        help="reliability only: score the originals, run no ablations. The "
                             "protocol's first gate and roughly a fifteenth of the calls")
    parser.add_argument("--n-passages", type=int, default=3)
    parser.add_argument("--n-samples", type=int, default=5,
                        help="samples per persona per passage; the protocol floor is 5")
    parser.add_argument("--transport", choices=("cli", "sdk", "ollama"), default="cli",
                        help="cli routes through `claude -p` on the local install's own "
                             "auth (a subscription); sdk needs an API key; ollama runs a "
                             "local model — free, offline, seeded, and schema-enforced")
    parser.add_argument("--rest-ratio", type=float, default=None,
                        help="ollama only: sleep this multiple of each call after it. The "
                             "temperature governor is the real protection; this is coarse")
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--spot-model", default=SPOT_MODEL)
    parser.add_argument("--no-spot", action="store_true", help="skip frontier spot checks")
    parser.add_argument("--fidelity", action="store_true",
                        help="run the held-out anchor probe. Off by default and a diagnostic "
                             "rather than a gate — see the docstring")
    parser.add_argument("--doses", default=None,
                        help="comma-separated ablation strengths, e.g. '1.0' to screen at full "
                             "dose only. Default is ablate.DOSES (0.15,0.35,0.65,1.0). See the "
                             "screen-then-confirm note in the docstring before narrowing it")
    parser.add_argument("--dry-run", action="store_true", help="build the schedule, call nothing")
    parser.add_argument("--yes", action="store_true", help="proceed past the call guard")
    parser.add_argument("--cache", default="persona-raw.jsonl",
                        help="append-only call log under results/. Give a concurrent run its "
                             "own file: the write lock is per-process, so two batteries "
                             "sharing one log can interleave a line and corrupt it")
    parser.add_argument("--out", default="persona-gate01.json")
    args = parser.parse_args()

    doses = DOSES
    if args.doses:
        doses = tuple(sorted({float(piece) for piece in args.doses.split(",") if piece.strip()}))
        if not doses or any(not 0.0 < dose <= 1.0 for dose in doses):
            raise SystemExit(f"--doses must be strengths in (0, 1]; got {args.doses!r}")

    passages, donors = load_passages(args)
    original_of = {passage_id: text for passage_id, text in passages}

    # The variant schedule, precomputed so each opaque scorer call can be attributed — the same
    # digest-keyed mapping `cdg_battery.py` uses, and for the same reason: `ablate` seeds every
    # transformation from the text itself, so regenerating variants reproduces them exactly.
    #
    # The donor indexing must be `evaluate`'s own (`donors[index % len(donors)]`) or the
    # transplant variants this map is built from are not the ones the harness will score. The
    # first version used `index + 1` and every transplant fell through to "unmapped" — visible
    # only because the printout names each variant, which is the argument for printing them.
    variant_of: dict[str, tuple[str, str, float]] = {}
    for index, (passage_id, text) in enumerate(passages):
        donor = donors[index % len(donors)] if donors else ""
        for key, _sign, _item, dose, damaged in variants(
            text, donor=donor, doses=doses, ablations=PERSONA_SET
        ):
            variant_of[digest(damaged)] = (passage_id, key, dose)

    cells_per_variant = len(PANEL) * args.n_samples
    scored_units = len(passages) if args.gate0 else len(variant_of)
    planned_calls = 2 * scored_units * cells_per_variant
    label = "original(s)" if args.gate0 else "variants"
    print(f"{len(passages)} passage(s) -> {scored_units} {label} x {cells_per_variant} cells "
          f"= ~{planned_calls} calls on {args.model}", file=sys.stderr)
    if planned_calls > CALL_GUARD and not (args.yes or args.dry_run):
        raise SystemExit(
            f"refusing {planned_calls} calls above the {CALL_GUARD} guard; pass --yes if that "
            "is the intended spend"
        )

    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    started = time.time()

    with Elicitor(
        results_dir / args.cache,
        model=args.model,
        spot_model=None if args.no_spot else args.spot_model,
        transport=args.transport,
        pair_question=args.pair_question,
        **({} if args.rest_ratio is None else {'rest_ratio': args.rest_ratio}),
        dry_run=args.dry_run,
    ) as elicitor:

        fidelity = []
        if args.fidelity:
            print("persona fidelity (diagnostic, not a gate)", file=sys.stderr)
            for persona in PANEL:
                score = elicitor.fidelity(persona)
                fidelity.append(score)
                print(f"  {persona.persona_id:<10} verdict={score['verdict_agreement']} "
                      f"reason={score['reason_agreement']} ({score['matched']}/"
                      f"{score['held_out']} matched)", file=sys.stderr)

        # Per-sample records for gate 0 and the decomposition, filled as the scorer runs.
        by_variant: dict[str, list[object]] = {}

        def scorer(text: str) -> float:
            text_digest = digest(text)
            passage_id, key, dose = variant_of.get(text_digest, ("unmapped", "unmapped", -1.0))
            variant_id = f"{passage_id}|{key}@{dose}"
            samples = elicitor.panel(variant_id, text, n=args.n_samples)
            by_variant[variant_id] = list(samples)
            panel_only = [s for s in samples if s.model == args.model and not s.refused]
            print(f"  [{len(by_variant):3d}] {variant_id:<44} "
                  f"stop={sum(1 for s in panel_only if s.would_stop)}/{len(panel_only)}",
                  file=sys.stderr, flush=True)
            if not panel_only:
                return 0.5
            return sum(1 for s in panel_only if s.would_stop) / len(panel_only)

        comparisons: list[Any] = []

        def pair_scorer(text: str) -> float:
            """P(the panel prefers this variant over its own original). See `variant_win_rate`.

            The original scores 0.5 without being elicited: a text compared against itself is
            indifference by construction, and spending calls to rediscover that would buy
            nothing. `evaluate` takes the original's score as each chapter's baseline, so 0.5 is
            exactly the value it should be subtracting.
            """
            text_digest = digest(text)
            passage_id, key, dose = variant_of.get(text_digest, ("unmapped", "unmapped", -1.0))
            if key == "original":
                return 0.5
            original = original_of.get(passage_id)
            if original is None:
                return 0.5
            pair_id = f"{passage_id}|{key}@{dose}"
            batch = elicitor.compare_pair(pair_id, original, text, n=args.n_samples)
            comparisons.extend(batch)
            by_variant[pair_id] = list(batch)
            scored = [c for c in batch if c.model == args.model and not c.refused]
            ties = sum(1 for c in scored if c.choice == "neither")
            chose = sum(1 for c in scored if c.chose_variant)
            values = [
                0.5 if c.choice == "neither" else (1.0 if c.chose_variant else 0.0)
                for c in scored
                if not (c.choice == "neither" and args.tie_policy == "drop")
            ]
            rate = sum(values) / len(values) if values else 0.5
            print(f"  [{len(by_variant):3d}] {pair_id:<46} variant {chose}/{len(scored)} "
                  f"(ties {ties}) -> {rate:.2f}", file=sys.stderr, flush=True)
            return rate

        result = None
        if args.pairwise:
            # Blinded, position-swapped preference — §70 addendum 3. Damage is declared to
            # *lower* the variant's win rate, so `direction` is -1 here where the absolute
            # instrument used +1.
            result = evaluate(
                pair_scorer,
                [text for _, text in passages],
                metric="persona_panel.pairwise.v0",
                donors=donors,
                direction=-1,
                doses=doses,
                ablations=PERSONA_SET,
            )
        elif args.gate0:
            # Reliability only. Gate 0 asks whether repeated samples of one passage agree more
            # than samples of different passages, and that question is answered by the originals
            # alone — running the ablation ladder to answer it would spend fifteen times the
            # calls on variants no statistic here reads. The protocol orders the gates this way
            # for exactly this reason: the cheapest kill goes first.
            for _passage_id, text in passages:
                scorer(text)
        else:
            result = evaluate(
                scorer,
                [text for _, text in passages],
                metric="persona_panel.would_stop.v0",
                donors=donors,
                direction=+1,
                doses=doses,
                ablations=PERSONA_SET,
            )

        spend = elicitor.spend()
        api_calls, replayed = elicitor.api_calls, elicitor.replayed

    # ------------------------------------------------------------------ the kill conditions

    flat = [s for samples in by_variant.values() for s in samples]  # type: ignore[union-attr]
    scored = [s for s in flat if s.model == args.model and not s.refused]  # type: ignore[attr-defined]
    refusals = sum(1 for s in flat if s.refused)  # type: ignore[attr-defined]

    # **The absolute instrument's kill conditions do not transfer to the pairwise one**, and are
    # reported as not-applicable rather than computed over a different unit. ICC, the caricature
    # split, the collapse correlation and the positivity floor are all statements about a
    # per-passage *rating*; a comparison has no rating to decompose. Their pairwise analogues are
    # `positional_bias` (§69's own check) and the sham arms inside `gate1`. Running the old
    # arithmetic over `Comparison` objects would produce numbers with the old names and a
    # different meaning, which is the conflation `EvidenceClass` exists to stop one layer down.
    if args.pairwise:
        summary_kills: dict[str, object] = {
            "not_applicable": (
                "ICC, caricature, collapse and the positivity floor describe a per-passage "
                "rating; the pairwise instrument produces choices, not ratings. Its analogues "
                "are `positional_bias` and the sham arms in `gate1.per_ablation`"
            ),
            "reason_code_counts": dict(sorted(
                collections.Counter(
                    c.reason_code for c in scored if getattr(c, "reason_code", None)
                ).items(), key=lambda kv: -kv[1],
            )),
            "tie_rate": round(
                sum(1 for c in scored if getattr(c, "choice", None) == "neither")
                / max(len(scored), 1), 4,
            ),
        }

    per_persona_icc: dict[str, object] = {}
    for persona in (() if args.pairwise else PANEL):
        groups = [
            [float(s.would_stop) for s in samples  # type: ignore[union-attr]
             if s.persona_id == persona.persona_id and s.model == args.model and not s.refused]
            for samples in by_variant.values()
        ]
        per_persona_icc[persona.persona_id] = icc1(groups)

    pooled_groups = [] if args.pairwise else [
        [float(s.would_stop) for s in samples  # type: ignore[union-attr]
         if s.model == args.model and not s.refused]
        for samples in by_variant.values()
    ]

    cells: dict[tuple[str, str], float] = {}
    for variant_id, samples in ({} if args.pairwise else by_variant).items():
        for persona in PANEL:
            mine = [s for s in samples  # type: ignore[union-attr]
                    if s.persona_id == persona.persona_id and s.model == args.model
                    and not s.refused]
            if mine:
                cells[(variant_id, persona.persona_id)] = statistics.fmean(
                    float(s.would_stop) for s in mine
                )

    base_rate = (
        float("nan") if args.pairwise or not scored
        else statistics.fmean(float(s.would_stop) for s in scored)
    )
    reason_counts: dict[str, int] = {}
    for sample in (() if args.pairwise else scored):
        code = sample.reason_code or "unset"  # type: ignore[attr-defined]
        reason_counts[code] = reason_counts.get(code, 0) + 1

    summary = {
        "metric": "persona_panel.would_stop.v0",
        "protocol": "plan/persona-reader-validity.md",
        "entry": "plan/stage-0-decisions.md §70",
        "transport": args.transport,
        "panel_model": args.model,
        "spot_model": None if args.no_spot else args.spot_model,
        "personas": [persona.persona_id for persona in PANEL],
        "n_samples": args.n_samples,
        "doses": list(doses),
        "mode": "pairwise" if args.pairwise else ("gate0" if args.gate0 else "absolute"),
        "tie_policy": args.tie_policy,
        "pair_question": args.pair_question,
        "positional_bias": positional_bias(comparisons) if comparisons else None,
        "pairwise_two_way_ci": (
            pairwise_interval(comparisons, args.model, args.tie_policy)
            if comparisons else None
        ),
        "passages": [passage_id for passage_id, _ in passages],
        "passage_source": source_label(args),
        "variants_scored": len(by_variant),
        "api_calls": api_calls,
        "replayed_calls": replayed,
        "refused_samples": refusals,
        "usage": spend,
        "minutes": round((time.time() - started) / 60, 1),
        "persona_fidelity_diagnostic": fidelity or "not run (--fidelity)",
        "gate0_icc_pooled": None if args.pairwise else icc1(pooled_groups),
        "gate0_icc_per_persona": per_persona_icc,
        "gate1": {
            "detect_auc": result.detect_auc,
            "sham_auc": result.sham_auc,
            "margin": result.margin,
            "length_auc": result.length_auc,
            "paired_rate": result.paired_rate,
            "paired_ci": list(result.paired_ci),
            "paired_n": result.paired_n,
            "per_ablation": result.per_ablation,
            "pre_registration": annotate_arms(result.per_ablation),
            "notes": result.notes,
            "verdict": result.verdict(),
        } if result is not None else {
            "verdict": "NOT RUN — --gate0 scored the originals only, no ablation ladder"
        },
        "stake_coverage": {
            passage_id: stake_coverage(text) for passage_id, text in passages
        },
        "filler_reason_signature": filler_reason_signature(by_variant, args.model),
        "destake_vs_matched_deletion": (
            _destake_comparison(result.per_ablation) if result is not None
            else {"available": False, "note": "--gate0 ran no ablations"}
        ),
        "kill_conditions": summary_kills if args.pairwise else {
            "caricature": variance_split(cells),
            "collapse": inter_persona_rho(cells),
            "positivity_floor": {
                "would_stop_base_rate": round(base_rate, 4)
                if not math.isnan(base_rate) else float("nan"),
                "scored_samples": len(scored),
                "note": "a rate at or near 0 on passages a human majority stops on is dead as "
                        "a stop predictor; the human majority is gate 2's to supply",
            },
            "reason_code_counts": dict(sorted(reason_counts.items(), key=lambda kv: -kv[1])),
        },
    }
    if args.published:
        summary["MEMORISATION WARNING"] = (
            "scored on published prose the panel model has very likely memorised; BRIEF.md §2 "
            "Pass 6 measured familiarity swinging a model-based score 2.0x further than the "
            "strongest real degrader. Gate 0/1 numbers from this run bound nothing."
        )
    if args.dry_run:
        summary["DRY RUN"] = (
            "no model was called. Verdicts are hashed from request keys and carry no signal, so "
            "every rate here is a draw from the null — the point is that the arithmetic ran, not "
            "what it returned. Nothing in this file is evidence about anything."
        )

    out = results_dir / args.out
    out.write_text(json.dumps(summary, indent=1, default=str) + "\n", encoding="utf-8")
    if args.pairwise:
        bias = summary["positional_bias"] or {}
        print(f"\npositional bias (chose-A rate): {bias.get('chose_A_rate')} "
              f"over {bias.get('decided')} decided", file=sys.stderr)
    else:
        print(f"\ngate 0 pooled ICC(1): {summary['gate0_icc_pooled']['icc1']}", file=sys.stderr)
    print(f"gate 1: {summary['gate1']['verdict']}", file=sys.stderr)
    print(f"written to {out}", file=sys.stderr)


def selftest() -> None:
    """The kill-condition arithmetic against panels whose answers are known in advance.

    `evaluate.selftest`'s doctrine, one layer up: a statistic that reports 0.85 for a real panel
    is only believable if it reports the right thing for panels whose behaviour is stipulated.
    Three cases, each asserted rather than printed, because a selftest whose failures scroll past
    is a selftest nobody runs twice.

    - **noise** — every sample an independent coin flip. `ICC(1)` must land near zero and the
      caricature ratio must not blow up. This is the case a `--dry-run` produces, so if it ever
      reports a reliable panel, dry-run output has started looking like evidence.
    - **reliable** — samples agree within a passage and passages differ. `ICC(1)` must be high.
      Without this case, an ICC implementation that always returns ~0 would pass the noise test
      and silently kill every real panel that ever runs.
    - **costume** — every persona answers from its own fixed bias and ignores the passage. The
      caricature ratio must exceed 1, which is the pre-registered kill.
    """
    rng = random.Random(4)
    passages = [f"p{index}" for index in range(12)]
    personas = [persona.persona_id for persona in PANEL]

    noise = [[float(rng.random() < 0.5) for _ in range(5)] for _ in passages]
    noise_icc = icc1(noise)["icc1"]
    assert -0.35 < noise_icc < 0.35, f"noise panel reported ICC {noise_icc}"

    # Per-passage rates far apart, samples within a passage nearly unanimous.
    reliable = [
        [float(rng.random() < (0.05 if index % 2 else 0.95)) for _ in range(5)]
        for index, _ in enumerate(passages)
    ]
    reliable_icc = icc1(reliable)["icc1"]
    assert reliable_icc > 0.5, f"reliable panel reported ICC {reliable_icc}"

    passage_driven = {
        (passage, persona): float(index % 2 == 0)
        for index, passage in enumerate(passages)
        for persona in personas
    }
    assert variance_split(passage_driven)["ratio"] < 1.0, "passage-driven panel read as caricature"

    bias = {
        persona: (position + 1) / (len(personas) + 1)
        for position, persona in enumerate(personas)
    }
    costume = {
        (passage, persona): bias[persona]
        for passage in passages
        for persona in personas
    }
    costume_ratio = variance_split(costume)["ratio"]
    assert costume_ratio > 1.0, f"costume panel reported caricature ratio {costume_ratio}"

    identical = {
        (passage, persona): float(index % 3 == 0)
        for index, passage in enumerate(passages)
        for persona in personas
    }
    collapse = inter_persona_rho(identical)
    assert collapse["mean_rho"] > 0.9, f"identical personas reported rho {collapse['mean_rho']}"
    assert not math.isnan(float(collapse["null_p95"])), "collapse null did not simulate"

    print(f"noise ICC {noise_icc:+.4f} | reliable ICC {reliable_icc:+.4f} | "
          f"costume ratio {costume_ratio:.2f} | collapsed rho {collapse['mean_rho']:.3f} "
          f"(null p95 {collapse['null_p95']})")
    print("SELFTEST OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
