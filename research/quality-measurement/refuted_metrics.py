"""The four refuted craft proxies, archived off the accept path. Frozen: measured, failed, kept.

These four functions — `sentence_length_variation`, `dialogue_ratio`, `tricolon_rate`,
`opening_shape_repetition` — were §10.2's instrumented craft metrics, computed per accepted
scene until BRIEF.md §2 Pass 2 retired them. The refutation record, moved here verbatim from
`domain/craft.py`'s module docstring when the functions moved:

**All four have since been measured against published LitRPG, and all four failed.** See
`plan/craft-profile.json`, built by `build_craft_profile.py` beside this module over ~13,000
LitRPG-tagged chapters from a 1.61M-chapter RoyalRoad corpus. Holding the era fixed — 2025
chapters whose author declared `AI-Assisted Content` against 2025 chapters that did not —
every rank AUC falls within 0.06 of chance:

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

What the archive changed and what it did not. The accept path stopped computing these four per
accepted scene — `domain/craft.py` now measures only the two duplicate-detection metrics — and
the craft table records only metrics with a live calibration candidate. The committed profile,
its separation table, and the historical rows in every database remain the measured record.
This module keeps the arithmetic runnable for that record: `build_craft_profile.py` and
`conversion_separation.py` import from here.

**Frozen.** This project's rule is that changed arithmetic is a new metric id; changed
arithmetic *here* would be worse — it would silently detach the committed profile and the
recorded per-scene rows from the code that produced them, with no id to say so.
"""

from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from litharness.domain.craft import CraftMetric

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


def sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_END.split(text) if part.strip()]


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


#: The archived accept-path metric set, byte-for-byte the tuple `domain/craft.py` carried, in
#: the fixed order the historical decision records hashed their gates in.
METRICS = (
    sentence_length_variation,
    dialogue_ratio,
    tricolon_rate,
    opening_shape_repetition,
)
