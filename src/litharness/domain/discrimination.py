"""The E6 frame, frozen: the one question about prose a machine has been measured able to answer.

Three independent attempts asked a machine for a **verdict** on prose and all three died — the
T0 axiom battery disqualified the incumbent panel at a positional bias of 0.8151 over 568 decided
comparisons, §89's E1/E2 are VOID on their own precondition at 0.6408 over 142, and the persona
reader's absolute form answered "keep reading" to 195 of 196 passages. **One frame survived.**
Asked to *name the single most salient difference* between two passages, the same model on the
same pairs cleared all three B6 families — 40/40, 30/32, 18/36 against measured nulls — reported
*"the passages are identical"* on the placebo and *"double spaces after periods"* on the sham.

So this module carries that question and its scoring, and carries them **byte-for-byte**.
`tests/test_reader_judge_loop.py` compares `E6_QUESTION`, `E6_SCHEMA` and `AXIS_MATCHERS` against
`research/quality-measurement/elicitation_study.py` and fails on any divergence. A reworded
question is a different protocol with no validity evidence behind it; a matcher edited after
reading responses is a rubric fitted to its own answers.

**What this frame does and does not buy, stated as narrowly as §89 states it.** E6 reports a
*difference*, never a preference. It can staff a discrimination layer; it cannot staff a
preference layer; JudgeBench A2's verdict layer is still empty and §82 is untouched. The
deterministic counter — never the judge — decides which side of an axis a text sits on. The judge
supplies exactly one thing the counter cannot: which axis, of several present, is the salient one.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from litharness.domain.axes import AXES

#: E6's turn, byte-for-byte from `elicitation_study.E6_QUESTION`. The second line is doing real
#: work and is not decoration: E6 is not a preference protocol, and a model that answered which
#: passage it preferred would be back in the channel measured 4,676x more about position than
#: about the passages.
E6_QUESTION = (
    "Two passages. Name the single most salient difference between them, in one sentence.\n\n"
    "Describe what the difference is, not which passage you prefer."
)

E6_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"difference": {"type": "string"}},
    "required": ["difference"],
    "additionalProperties": False,
}

#: One JSON object out; the passages are input. `elicitation_study.ANSWER_MAX_TOKENS`.
ANSWER_MAX_TOKENS = 160

#: Which B6 family's matcher owns each registered axis. The matchers are keyed by *family* below
#: so they stay byte-comparable with the research module; this is the only translation, and it is
#: one line rather than a reworded matcher.
FAMILY_FOR_AXIS: Mapping[str, str] = {
    "stat_flatten": "stat_flatten",
    "interiority": "interiority_strip_matched",
    "em_dash": "repair_emdash",
}

#: `elicitation_study.AXIS_MATCHERS`, byte-for-byte. Deliberately generous about vocabulary and
#: strict about topic: a model that says "the numbers in the status block are gone" and one that
#: says "B has no quantities" should both count, because what is under test is whether the axis
#: reached the output at all, not whether the model shares our terminology.
AXIS_MATCHERS: dict[str, str] = {
    "stat_flatten": (
        r"\b(number|numeric|numeral|digit|figure|quantit|stat|stats|statistic|status|value|"
        r"score|count|percent|damage|hp\b|mp\b|xp\b|level|tier|metric|readout|specific)\w*"
    ),
    "interiority_strip_matched": (
        r"\b(interior|inner|internal|introspect|thought|thinking|feel|feeling|felt|emotion|"
        r"reflect|reaction|psycholog|mind|mental|consciousness|subjectiv|perspective|"
        r"first[- ]person|access to)\w*"
    ),
    "repair_emdash": (
        r"(\bem[- ]?dash|\bdash(es)?\b|\bpunctuat|\bhyphen|\bcomma|\bsentence structure|"
        r"\bclause|—)"
    ),
}

#: The response that clears the placebo control: the model saying there is nothing there.
_IDENTICAL = re.compile(
    r"\b(identical|no (discernible |meaningful |apparent )?difference|the same|"
    r"indistinguishable|nothing)\b",
    re.IGNORECASE,
)

#: The response that clears the sham control: the model naming formatting as formatting.
_FORMATTING = re.compile(
    r"\b(whitespace|white space|spacing|space[sd]?|indent|line break|blank line|"
    r"paragraph break|formatting)\b",
    re.IGNORECASE,
)

#: §89's orientation band, inherited rather than re-derived. E6 asks for no choice, so
#: `positional_bias` has nothing to count and reporting it would be a precondition that cannot
#: fail; what can still go wrong is the report channel working in one slot and not the other.
ORIENTATION_BAND = 0.2

#: Responses needed before the orientation reading says anything. §89's `DECIDED_FLOOR`, and it
#: is honest rather than convenient: below it the check reads UNREADABLE and the judge half stays
#: shut, which is the sequencing this design already requires.
ORIENTATION_FLOOR = 30


def axis_named(axis_id: str, said: str) -> bool:
    """Did this response name `axis_id`'s axis? Deterministic; the matcher above is frozen."""
    pattern = AXIS_MATCHERS.get(FAMILY_FOR_AXIS[axis_id])
    if pattern is None:
        return False
    return re.search(pattern, said, flags=re.IGNORECASE) is not None


def named_axes(said: str, among: Sequence[str]) -> tuple[str, ...]:
    """Which of `among` this response named, in registry order.

    `among` is always the set of axes the **counter** separates this pair on. That is what keeps
    the frozen matchers used the way §89 scored them — asked whether a known candidate axis
    reached the output — while leaving the counter, not the judge, to own which side is which.
    """
    return tuple(axis for axis in AXES if axis in among and axis_named(axis, said))


def whitespace_sham(text: str) -> str:
    """A whitespace-only variant: two spaces after a sentence end, nothing else touched.

    The transform whose response §89 quotes — *"Passage A uses single spaces after periods;
    Passage B uses double spaces after periods"* — and it is the control that shows the channel
    is not selectively losing prose. Deterministic and RNG-free, unlike `ablate.rewhitespace`,
    because a control that re-rolled would not be reproducible per batch.
    """
    return re.sub(r"(?<=[.!?]) (?=[A-Z\"'“])", "  ", text)


class ControlVerdict(enum.StrEnum):
    """What a control says about the batch it rode along with."""

    CLEAR = "clear"
    CONFABULATED = "confabulated"
    UNANSWERED = "unanswered"


def placebo_verdict(said: str | None) -> ControlVerdict:
    """Two byte-identical passages. The judge must decline to invent a difference.

    Cleared by saying they are the same **or** by naming no registered axis at all: §89's own
    placebo response is a sentence about identity, and a response that wanders without naming an
    axis has still not confabulated one. Failed only by naming a prose axis that is not there.
    """
    if not said or not said.strip():
        return ControlVerdict.UNANSWERED
    if _IDENTICAL.search(said):
        return ControlVerdict.CLEAR
    if named_axes(said, tuple(AXES)):
        return ControlVerdict.CONFABULATED
    return ControlVerdict.CLEAR


def sham_verdict(said: str | None) -> ControlVerdict:
    """A whitespace-only variant. Naming formatting is correct; naming prose is not."""
    if not said or not said.strip():
        return ControlVerdict.UNANSWERED
    if _FORMATTING.search(said):
        return ControlVerdict.CLEAR
    if named_axes(said, tuple(AXES)):
        return ControlVerdict.CONFABULATED
    return ControlVerdict.CLEAR


class OrientationReading(enum.StrEnum):
    UNREADABLE = "unreadable"
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"


@dataclass(frozen=True, slots=True)
class OrientationCheck:
    reading: OrientationReading
    responses: int
    fires_first: float | None
    fires_second: float | None

    @property
    def gap(self) -> float | None:
        if self.fires_first is None or self.fires_second is None:
            return None
        return abs(self.fires_first - self.fires_second)


def orientation_check(
    rows: Sequence[tuple[int, bool]], *, floor: int = ORIENTATION_FLOOR
) -> OrientationCheck:
    """`(orientation, named_anything)` rows to §89's symmetry reading.

    Accumulated over a book rather than over one batch, and the reason is arithmetic: a K=3
    tournament yields six responses, so a per-batch check at a thirty-response floor would read
    UNREADABLE forever and be a precondition that cannot fail — the exact defect §89 item 7
    caught in a withholding gate.
    """
    counts = {0: [0, 0], 1: [0, 0]}
    for orientation, named in rows:
        cell = counts[orientation]
        cell[0] += int(named)
        cell[1] += 1
    rates = {
        side: (cell[0] / cell[1] if cell[1] else None) for side, cell in counts.items()
    }
    total = sum(cell[1] for cell in counts.values())
    first, second = rates[0], rates[1]
    if total < floor or first is None or second is None:
        reading = OrientationReading.UNREADABLE
    elif abs(first - second) <= ORIENTATION_BAND:
        reading = OrientationReading.SYMMETRIC
    else:
        reading = OrientationReading.ASYMMETRIC
    return OrientationCheck(
        reading=reading, responses=total, fires_first=first, fires_second=second
    )


__all__ = [
    "ANSWER_MAX_TOKENS",
    "AXIS_MATCHERS",
    "E6_QUESTION",
    "E6_SCHEMA",
    "FAMILY_FOR_AXIS",
    "ORIENTATION_BAND",
    "ORIENTATION_FLOOR",
    "ControlVerdict",
    "OrientationCheck",
    "OrientationReading",
    "axis_named",
    "named_axes",
    "orientation_check",
    "placebo_verdict",
    "sham_verdict",
    "whitespace_sham",
]
