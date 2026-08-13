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

**Every metric here is named by the plan and none was refuted.** Sentence-length distribution
and dialogue ratio are §10.2's own list; the tricolon habit and "the same three sentence
shapes" are §1a.3 item 6 verbatim. That is the entire selection rule — §10.6 exists because
these proxies get re-proposed otherwise, and inventing a tenth one on a hunch is how its
findings get quietly overwritten.

**A metric reports a number, never a judgment.** No metric here has a threshold, a pass, or a
direction. Those are properties of a *calibration* (`domain/calibration.py`), which is a claim
about human judgment that has to be earned; a threshold living beside the measurement would be
a guess wearing the measurement's authority.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

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


#: The metric set, in a fixed order so a decision record's gate list is stable.
METRICS = (
    sentence_length_variation,
    dialogue_ratio,
    tricolon_rate,
    opening_shape_repetition,
)


def measure(text: str) -> tuple[CraftMetric, ...]:
    """Every craft metric over one scene's prose. Pure, deterministic, model-free."""
    return tuple(metric(text) for metric in METRICS)


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
    "CraftMetric",
    "craft_gates",
    "dialogue_ratio",
    "measure",
    "opening_shape_repetition",
    "sentence_length_variation",
    "sentences",
    "tricolon_rate",
    "words",
]
