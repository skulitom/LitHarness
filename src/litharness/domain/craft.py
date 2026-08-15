"""§10.2's craft instrumentation: proxies logged per scene, advisory and unable to gate.

**Read the disclaimer before the code, because the code is the easy part.** §1a.3 orders what
quality means here, and the four items that move a reader most are the four these metrics do
not touch:

1. dramatic function — does the scene change something, or only convey information
2. progression as drama rather than bookkeeping
3. escalation and payoff on a cadence a reader can feel
4. voice, and dialogue that distinguishes characters

§10.6 established, by measurement rather than by opinion, that **items 1 to 4 cannot be
reached from defect fixtures at all**: `scene_change_profile` ranks the mystery upside down
(scene 6,
the confession and arrest, carries zero state records; scene 1, pure exposition, carries the
most), `silent_ledger` fires on the fixture's best prose, `progression_cost` is satisfied by
inserting a token gold decrement, and Burrows Delta separates within-book from between-book by
0.6% over a program containing 77 words of dialogue.

What is left, and what this module measures, is items 5 and 6 — line-level craft and AI tells.
§1a.1 is blunt about what that is worth: *"beware the metric that is easy because it is
shallow"*. These are instrumentation, not a verdict, and the module is built so that no
caller can mistake one for the other: `craft_gates` marks every result `blocking=False`, and
`PolicyDecision.__post_init__` raises if a blocking craft gate arrives without a
`calibration_id`. The bar is structural in two places rather than promised in one.

**Every metric here is named by the plan.** Sentence-length distribution and dialogue ratio
are §10.2's own list; the tricolon habit and "the same three sentence shapes" are §1a.3 item 6
verbatim. That is the entire selection rule — §10.6 exists because these proxies get
re-proposed otherwise, and inventing a fifth one on a hunch is how its findings get quietly
overwritten.

**`scene_echo` is the fifth, and the rule above is why it needs a defence rather than a
mention.** Two things separate it from the proxies §10.6 refuted. It was **measured before it
was built**: the obvious form — whole-book compression ratio — turned out to track scene count
rather than authorship, since a machine-written six-scene book scored 0.704 against human books
at 0.625 and 0.757, and only the pairwise form survived that control. And it makes a **claim of
a different kind**: the four above assert something about quality, which is why they need human
judgment to be worth anything; this asserts that two scenes are largely the same text, which is
checkable without asking anyone. It is still advisory, still uncalibrated, and still cannot
gate — but "this scene is a copy of that one" is a fact rather than an opinion, and §10.6's
finding is about opinions.

It exists because a Book Zero run passed every gate in this system while writing the same scene
repeatedly: fifteen accepted scenes, zero exceptions, `verify` clean, and scene 13 was scene 12
with two words changed and a digit incremented.

**All four have since been measured against published LitRPG, and all four failed.** See
`plan/craft-profile.json`, built by `tools/build_craft_profile.py` over ~13,000 LitRPG-tagged
chapters from a 1.61M-chapter RoyalRoad corpus. Holding the era fixed — 2025 chapters whose
author declared `AI-Assisted Content` against 2025 chapters that did not — every rank AUC
falls within 0.06 of chance:

    dialogue_ratio            0.445      opening_shape_repetition  0.455
    sentence_length_cv        0.461      tricolon_rate             0.528

`tricolon_rate` scores 0.629 against *pre-2023* chapters, which looks like a result until the
control is read beside it: undeclared 2025 chapters score 0.606 against the same baseline. The
metric is detecting the **year**, not the machine. That is the confound the era control exists
to expose, and it fired on the one metric that looked promising.

So these are **not AI-tell detectors** and this module must not be read as claiming they are.
Three caveats keep the finding from being stronger than it is: the declared-AI cohort is 55
stories, self-declaration is certainly under-reported, and the cohorts differ wildly in
maturity (median followers 16, 88 and 314), so a separation could have been story-size rather
than prose. That makes this "no separation detected, with named confounds" rather than "proven
no signal" — which is still the most anyone has measured about them, and strictly better than
the unmeasured hope they carried before.

**What they are still good for is anchoring.** `percentile_of` places a generated scene
against the published distribution, so "the 99th percentile of published LitRPG for tricolon
rate" is a fact about an outlier even though the metric does not sort machine from human. That
is a smaller claim than the module started with, and it is the one the evidence supports.

**A metric reports a number, never a judgment.** No metric here has a threshold, a pass, or a
direction. Those are properties of a *calibration* (`domain/calibration.py`), which is a claim
about human judgment that has to be earned; a threshold living beside the measurement would be
a guess wearing the measurement's authority.
"""

from __future__ import annotations

import gzip
import json
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

from litharness.domain.policy import GateKind, GateOutcome, VerdictSource

#: Sentence terminators, kept deliberately crude. A real sentence splitter would be better and
#: is not worth a dependency here: these are advisory numbers and a splitter that mis-handles
#: "Mr." changes a coefficient of variation in the third decimal. Recorded so nobody later
#: mistakes the crudeness for an oversight.
_SENTENCE_END = re.compile(r"[.!?]+[\s\"'\u201d\u2019]*")
_WORD = re.compile(r"[\w'\u2019-]+", re.UNICODE)
#: Straight and curly pairs both, because canonicalization is NFC and does not unify quotes.
_DIALOGUE = re.compile("[\"“]([^\"“”]*)[\"”]")
#: Three coordinated items: "a, b, and c" — §1a.3 item 6's "tricolon habit", the single most
#: recognisable shape in generated prose.
_TRICOLON = re.compile(
    r"\b[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,3},\s+[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,3},"
    r"\s+(?:and|or)\s+[\w'\u2019-]+",
    re.IGNORECASE,
)

#: How many leading tokens define a sentence's "shape" for repetition purposes. Two, because
#: one collapses every sentence starting "The" and three splits near-identical openings apart.
_SHAPE_TOKENS = 2

#: Edge punctuation stripped before two words are called equal, so that a repeated span is
#: not broken by the comma that ends it. Both quote families, since canonicalization is NFC
#: and does not unify them. Spelled with escapes for the same reason `_WORD` is: the dashes
#: and curly quotes are confusable with ASCII on sight, and this is the one place where the
#: difference is the whole point.
_SPAN_TRIM = ".,;:!?\"'()[]\u2014\u2013\u2026\u201c\u201d\u2018\u2019"


@dataclass(frozen=True, slots=True)
class CraftMetric:
    """One measured number, with what it is and what it is not.

    `caveat` is a required field rather than an optional docstring: a metric travelling
    without the reason it cannot be trusted is a metric that will be trusted.
    """

    metric_id: str
    value: float
    #: What §1a.3 item this gestures at, and why it is not evidence about it.
    caveat: str
    detail: str | None = None


def sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_END.split(text) if part.strip()]
    return parts


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def sentence_length_variation(text: str) -> CraftMetric:
    """Coefficient of variation of sentence lengths — §1a.3 item 5, "varied sentence rhythm".

    A ratio rather than a standard deviation so that a scene of long sentences and a scene of
    short ones are comparable; raw sd tracks mean length, which is a style choice rather than
    a defect.
    """
    lengths = [len(words(sentence)) for sentence in sentences(text)]
    lengths = [length for length in lengths if length]
    if len(lengths) < 2:
        value = 0.0
    else:
        mean = statistics.fmean(lengths)
        value = (statistics.pstdev(lengths) / mean) if mean else 0.0
    return CraftMetric(
        metric_id="craft.sentence_length_cv.v0",
        value=round(value, 4),
        caveat=(
            "§1a.3 item 5 only. Uniform rhythm is one symptom of flat prose and varied "
            "rhythm is not evidence of good prose; no threshold has been calibrated"
        ),
        detail=f"{len(lengths)} sentence(s)",
    )


def dialogue_ratio(text: str) -> CraftMetric:
    """Share of characters inside quotation marks — §10.2's own list.

    Reported because §10.2 asks for it, and with the warning §10.6 earned: the entire golden
    program contains 77 words of dialogue, so nothing in this project has any idea what value
    is good. It is a distribution to accumulate, not a number to act on.
    """
    quoted = sum(len(match.group(0)) for match in _DIALOGUE.finditer(text))
    value = (quoted / len(text)) if text else 0.0
    return CraftMetric(
        metric_id="craft.dialogue_ratio.v0",
        value=round(value, 4),
        caveat=(
            "§10.2 asks for it; §10.6 measured that the program holds 77 words of dialogue "
            "in total, so no baseline exists for what this number should be"
        ),
    )


def tricolon_rate(text: str) -> CraftMetric:
    """Three-item coordinated lists per thousand words — §1a.3 item 6, named verbatim.

    The one metric here aimed at a tell rather than at a texture, and the one most likely to
    survive calibration, because "the tricolon habit" is a specific reproducible behaviour
    rather than a quality abstraction.
    """
    count = len(_TRICOLON.findall(text))
    total = len(words(text))
    value = (1000.0 * count / total) if total else 0.0
    return CraftMetric(
        metric_id="craft.tricolon_rate.v0",
        value=round(value, 4),
        caveat=(
            "§1a.3 item 6. A tricolon is a legitimate figure; a *rate* is the hypothesis, "
            "and it is untested against any human judgment"
        ),
        detail=f"{count} in {total} word(s)",
    )


def opening_shape_repetition(text: str) -> CraftMetric:
    """Share of sentences sharing the modal opening — §1a.3 item 6, "the same three shapes".

    Keyed on the first two tokens, lowercased. One token collapses everything beginning "The";
    three splits near-identical openings apart. The choice is arbitrary within that range and
    is recorded rather than tuned, because tuning it against the fixtures would be fitting a
    proxy to six scenes.
    """
    shapes = [
        " ".join(words(sentence)[:_SHAPE_TOKENS]).lower()
        for sentence in sentences(text)
    ]
    shapes = [shape for shape in shapes if shape]
    if len(shapes) < 2:
        return CraftMetric(
            metric_id="craft.opening_shape_repetition.v0",
            value=0.0,
            caveat="§1a.3 item 6. Fewer than two sentences; nothing to compare",
        )
    modal = max(set(shapes), key=shapes.count)
    value = shapes.count(modal) / len(shapes)
    return CraftMetric(
        metric_id="craft.opening_shape_repetition.v0",
        value=round(value, 4),
        caveat=(
            "§1a.3 item 6. Deliberate anaphora scores identically to an exhausted model; "
            "only a human reading tells them apart, which is what §10.5's audit is for"
        ),
        detail=f"modal opening {modal!r} in {shapes.count(modal)}/{len(shapes)}",
    )


#: System-voice blocks, stripped before two scenes are compared. The litrpg fixture's own plan
#: says it outright — "a status block appears in every scene; repetition of the block format is
#: intentional and must not be flagged as an echo" — and measured, leaving them in drops the
#: fixture's closest pair from 0.766 to 0.591, which would make a genre convention the most
#: repetitive thing in the book.
_SYSTEM_BLOCK = re.compile(r"^\[(?:STATUS|INVENTORY|SKILLS|QUESTS)\].*$", re.MULTILINE)

#: Compressor level, pinned so the number is reproducible across machines and runs.
_GZIP_LEVEL = 9


def _compressed(text: str) -> int:
    return len(gzip.compress(text.encode("utf-8"), _GZIP_LEVEL))


def scene_echo(text: str, others: Sequence[str]) -> CraftMetric:
    """How close this scene is to the nearest *other* scene, by compression distance.

    Normalised compression distance, `(C(xy) - min(C(x), C(y))) / max(C(x), C(y))`: 1.0 means
    the two scenes share nothing, and low means one is largely the other. No model, no
    dependency, deterministic.

    **This exists because a Book Zero run passed every gate while writing the same scene
    repeatedly.** Fifteen accepted scenes, zero exceptions, `verify` clean — and scene 13 was
    scene 12 with "breath hitched" changed to "chest tightened" and a digit incremented. The
    shape gate saw the right length, the integrity gate saw no contradiction (the ledger was
    frozen, so nothing to contradict), and nothing else in this system looks at prose at all.
    That book is §1a's stated nightmare with every mechanical check green.

    **The minimum is the signal and the median is not**, which is the whole of what the
    measurement found. Median NCD across two human books and two machine books sat at
    0.71-0.82 with no separation at all; the minimum was 0.72-0.77 everywhere except the
    duplicated pair, which scored **0.089**. So this is a duplicate detector rather than a
    craft score, and reporting a book's average would be reporting noise.

    **Advisory by construction**, like every metric here: `craft_gates` builds nothing
    blocking and `PolicyDecision` raises on a blocking craft gate with no calibration (§10.4).
    "These two scenes are the same scene" is mechanically checkable and would be a fair
    candidate for promotion — but promotion runs through §10.4's evidence bar like anything
    else, and this has none yet.
    """
    stripped = _SYSTEM_BLOCK.sub("", text).strip()
    candidates = [
        cleaned
        for other in others
        if (cleaned := _SYSTEM_BLOCK.sub("", other).strip())
    ]
    if not stripped or not candidates:
        return CraftMetric(
            metric_id="craft.scene_echo.v0",
            value=1.0,
            caveat="§1a.3 item 6. Nothing to compare against; reported as maximally distinct",
        )
    mine = _compressed(stripped)
    nearest = 1.0
    for candidate in candidates:
        theirs = _compressed(candidate)
        joint = _compressed(f"{stripped}\n\n{candidate}")
        nearest = min(nearest, (joint - min(mine, theirs)) / max(mine, theirs))
    return CraftMetric(
        metric_id="craft.scene_echo.v0",
        value=round(max(nearest, 0.0), 4),
        caveat=(
            "§1a.3 item 6. Compression distance to the nearest other scene, system-voice "
            "blocks stripped. The minimum separates a duplicate; the median measures nothing"
        ),
        detail=f"nearest of {len(candidates)} other scene(s)",
    )


#: The shortest run of words worth reporting. Eight, because shorter runs are idiom — "he
#: didn't know what to say", "for the first time in his life" — and a metric that fires on
#: those is reporting English. Measured: published serials carry a *median* longest
#: cross-chapter span of 10-12 words, so eight sits just under the observed noise floor.
_MIN_SPAN = 8

#: Stop looking once a span is this long. The difference between "180 words repeated" and
#: "240 words repeated" changes no decision anyone would make, and the cap is what keeps a
#: wholly duplicated scene from costing quadratic time in the drafting loop.
_SPAN_CAP = 200


def _span_tokens(text: str) -> tuple[list[str], list[str]]:
    """Words as written and words folded for comparison, positionally aligned.

    Folding is case and edge punctuation only. Comparison is on whole words rather than
    characters so that a match cannot begin mid-word — the same reason `_identifier_words`
    exists in `domain/propagation.py`, arrived at there by the same bug.
    """
    original = _SYSTEM_BLOCK.sub("", text).split()
    folded = [word.lower().strip(_SPAN_TRIM) for word in original]
    return original, folded


def repeated_span(text: str, others: Sequence[str]) -> CraftMetric:
    """The longest run of words this scene repeats verbatim from another accepted scene.

    **This exists because `scene_echo` provably misses the defect it was built for.** A
    `llama3.2` run emitted this paragraph byte-identical in scenes 5 and 6 —

        "Rook's gaze snapped back to Marrow, his mind racing with possibilities. He knew
        that he was in trouble, but he also knew that he couldn't give up now."

    — and the whole-scene compression distance between those two scenes is **0.695**, more
    than twice `scene_echo`'s 0.30 alarm. NCD is a ratio over the whole scene, so a fixed
    duplicated span is diluted by everything around it, and the longer the scenes grow the
    better it hides. Measured across a corpus: 43 chapter-pairs whose whole-unit NCD is
    0.711-0.926 contain a near-verbatim paragraph pair.

    **It reports its own evidence, and that is the point of the design.** The four proxies
    §10.6 refuted all failed the same way — a number that had to be interpreted got
    interpreted as a quality claim. "These 28 words appear in scene 5 and again in scene 6"
    is checkable by eye in the `detail` field, so there is nothing left to interpret. It was
    also chosen over the compression form on evidence: a repeated-trigram counter reproduced
    the compression statistic's entire separation (AUC 1.000 to 1.000, 0.558 against 0.589
    on the honest contrast), so the gzip curve was drawing a picture of an n-gram count.

    **It says nothing about who wrote the text, and the docstring has to say so or the
    metric will be read as an AI tell within a release.** Longest verbatim cross-chapter
    span, measured over 24 published RoyalRoad serials: pre-2023 human **70 words**,
    undeclared 2025 human **93 words**, declared-AI 2025 91 words — against 59 for this
    project's own worst machine book. Human serials carry recaps, epigraphs and quoted
    prophecies and repeat them exactly. A long span is evidence of repetition and of nothing
    else.

    Zero means no run of `_MIN_SPAN` words or longer, not "no repetition". Advisory like
    everything here: `craft_gates` marks it non-blocking and it carries no calibration.
    """
    _, folded = _span_tokens(text)
    index: dict[tuple[str, ...], list[tuple[int, list[str]]]] = {}
    for other in others:
        _, other_folded = _span_tokens(other)
        for start in range(len(other_folded) - _MIN_SPAN + 1):
            key = tuple(other_folded[start : start + _MIN_SPAN])
            index.setdefault(key, []).append((start, other_folded))

    original = _SYSTEM_BLOCK.sub("", text).split()
    best, best_at = 0, 0
    for position in range(len(folded) - _MIN_SPAN + 1):
        for start, other_folded in index.get(tuple(folded[position : position + _MIN_SPAN]), ()):
            length = _MIN_SPAN
            while (
                position + length < len(folded)
                and start + length < len(other_folded)
                and folded[position + length] == other_folded[start + length]
            ):
                length += 1
            if length > best:
                best, best_at = length, position
        if best >= _SPAN_CAP:
            break

    quoted = " ".join(original[best_at : best_at + best])
    return CraftMetric(
        metric_id="craft.repeated_span.v0",
        value=float(best),
        caveat=(
            "§1a.3 item 6. Longest run of words shared verbatim with another accepted scene, "
            "system-voice blocks stripped. Evidence of repetition only — published human "
            "serials repeat recaps up to 93 words and score higher than this project's own "
            "worst machine book"
        ),
        detail=(
            f"{best} words, first at word {best_at}: {quoted[:160]}"
            if best
            else f"no run of {_MIN_SPAN}+ words shared with {len(others)} other scene(s)"
        ),
    )


#: The metric set, in a fixed order so a decision record's gate list is stable.
METRICS = (
    sentence_length_variation,
    dialogue_ratio,
    tricolon_rate,
    opening_shape_repetition,
)


#: Every metric id `measure` reports. `scene_echo` is not in `METRICS` because it cannot be
#: computed from one scene alone, so "one result per entry in METRICS" stopped being the
#: invariant — this is the one that replaced it, and it pins the ids rather than the count.
MEASURED_IDS = (
    "craft.sentence_length_cv.v0",
    "craft.dialogue_ratio.v0",
    "craft.tricolon_rate.v0",
    "craft.opening_shape_repetition.v0",
    "craft.scene_echo.v0",
    "craft.repeated_span.v0",
)


def measure(text: str, others: Sequence[str] = ()) -> tuple[CraftMetric, ...]:
    """Every craft metric over one scene's prose. Pure, deterministic, model-free.

    `others` is the book's other accepted scenes. Every metric in `METRICS` reads one scene
    alone; the last two cannot, because "this scene is a copy of another" is not a property a
    scene has by itself. They also disagree by design — `scene_echo` measures the whole
    scene and dilutes a local duplicate, `repeated_span` finds the local duplicate and says
    nothing about the whole — and the pair is kept because the case that separates them was
    measured in a real run, not imagined.
    """
    return (
        *(metric(text) for metric in METRICS),
        scene_echo(text, others),
        repeated_span(text, others),
    )


#: The reference profile, beside the plan documents rather than inside the package: it is
#: evidence about the corpus, it is regenerated by a tool, and it is read by an operator at
#: least as often as by code.
PROFILE_PATH = Path(__file__).resolve().parents[3] / "plan" / "craft-profile.json"

#: The cohort a generated scene is compared against. Pre-LLM published LitRPG — the closest
#: thing available to §1a.5's "published human LitRPG", and chosen over the larger 2025 cohort
#: precisely because the 2025 one is of unknown provenance.
REFERENCE_COHORT = "human_pre_llm"


@lru_cache(maxsize=1)
def load_profile(path: str | None = None) -> dict[str, Any]:
    """The published-LitRPG reference distribution, or `{}` when it has not been built.

    Missing is a legitimate state and returns empty rather than raising: the profile is built
    by an offline tool against a 12.5GB corpus behind an optional extra, and a checkout that
    has not run it must still draft, gate and tick. Everything downstream degrades to "no
    anchor available", which is what it was before the profile existed.
    """
    target = Path(path) if path else PROFILE_PATH
    if not target.is_file():
        return {}
    loaded: dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
    return loaded


def percentile_of(
    metric: CraftMetric, *, cohort: str = REFERENCE_COHORT, profile: dict[str, Any] | None = None
) -> float | None:
    """Roughly where this measurement sits in published LitRPG, or None with no profile.

    Interpolated between the stored percentiles rather than computed from raw values, because
    the profile deliberately stores no prose. Approximate by construction, and that is the
    right precision for it: the useful statement is "far outside the published range", never
    "the 63rd percentile rather than the 61st".
    """
    data = profile if profile is not None else load_profile()
    cohorts: dict[str, Any] = data.get("cohorts", {})
    stops: dict[str, float] = cohorts.get(cohort, {}).get("metrics", {}).get(metric.metric_id, {})
    if not stops:
        return None
    ladder = [
        (0.01, stops["p01"]), (0.05, stops["p05"]), (0.25, stops["p25"]),
        (0.50, stops["p50"]), (0.75, stops["p75"]), (0.95, stops["p95"]),
        (0.99, stops["p99"]),
    ]
    if metric.value <= ladder[0][1]:
        return 0.01
    if metric.value >= ladder[-1][1]:
        return 0.99
    for (low_p, low_v), (high_p, high_v) in pairwise(ladder):
        if low_v <= metric.value <= high_v:
            if high_v == low_v:
                return low_p
            span = (metric.value - low_v) / (high_v - low_v)
            return round(low_p + span * (high_p - low_p), 4)
    return None  # pragma: no cover - the ladder is total over its own range


def craft_gates(metrics: tuple[CraftMetric, ...]) -> tuple[GateOutcome, ...]:
    """Project measurements into §4.2's ladder as *annotations*.

    `passed=True` and `blocking=False` on every one, unconditionally and without reading the
    value. That is not a placeholder for a threshold arriving later — it is §10.4's rule
    ("until then the Conductor treats it as annotation") expressed as code that has no branch
    to get wrong. A threshold arrives with a `Calibration`, and it arrives by a different
    route: `domain/calibration.py::promoted_gate`, which cannot be called without evidence.
    """
    return tuple(
        GateOutcome(
            gate=GateKind.CRAFT,
            rule_or_critic_id=metric.metric_id,
            passed=True,
            verdict_source=VerdictSource.DETERMINISTIC,
            blocking=False,
            detail=f"{metric.value} — {metric.caveat}"
            + (f" ({metric.detail})" if metric.detail else ""),
            calibration_id=None,
        )
        for metric in metrics
    )


__all__ = [
    "METRICS",
    "PROFILE_PATH",
    "REFERENCE_COHORT",
    "CraftMetric",
    "craft_gates",
    "dialogue_ratio",
    "load_profile",
    "measure",
    "opening_shape_repetition",
    "percentile_of",
    "repeated_span",
    "scene_echo",
    "sentence_length_variation",
    "sentences",
    "tricolon_rate",
    "words",
]
