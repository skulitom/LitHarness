"""What reaches a draft prompt, how it is composed from two sources, and how it retires.

**Neither source is a feedback signal alone.** A reader establishes, over few and expensive
verdicts, the *direction* of an axis. A judge applies, cheaply and per span, the
*discrimination* on that axis. Direction without discrimination cannot be applied to a draft;
discrimination without direction cannot say which way to move. So `FeedbackItem` cannot be
constructed without an `AxisDirection`, and `compose` discards a located difference whose axis has
none — the composition rule as a constructor precondition rather than a convention
(`plan/reader-judge-loop.md` §0.2).

**Named and located, never scalar.** There is no rating, no star, no 1-5 and no aggregate
quality number on any dataclass here, in the rendered text, or on the payload. That is invariant
I2 and it is enforced by there being no field to put one in. §10.4's boundary is the reason: a
number attached to a scene is one refactor away from a threshold, and a threshold is a gate.

**Nothing here can block.** This module does not import `domain.policy` and never will: a
feedback item has no path to a `GateOutcome`, cannot set `blocking`, cannot park a unit, and a
reader-derived gate would still be a gate. `tests/test_reader_judge_loop.py` asserts the
absence of the capability rather than trusting that no caller adds one.

**Retirement is three mechanisms, because accumulation is the failure mode.** Feedback that only
accumulates becomes an unreadable prompt and a system that cannot show improvement. (1) A located
item is one-shot: minted for one draft, `SPENT` when materialised, never materialised twice.
(2) A standing direction retires on staleness, by §72's expiry-on-use pattern — evidence moving
under a claim retires the claim. (3) An axis retires *by satisfaction* once the book's recent
accepted scenes already sit on the preferred side, which is the mechanism that lets the system
show improvement rather than repeating an instruction the prose already follows.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from litharness.domain.axes import AXES, Pole, count
from litharness.domain.directions import AxisDirection
from litharness.domain.events import payload_digest
from litharness.domain.pools import Pool

#: How many items may reach one prompt. Three, because that is one per registered axis and a
#: prompt carrying more than one instruction per axis is repeating itself.
#:
#: **The cap is reported, never silent.** `compose` returns what it dropped and the caller writes
#: it to the digest: a bound coverage that says nothing reads as "covered everything" when it did
#: not, which is the rail §89 names after four modules learned it the expensive way.
MAX_FEEDBACK_ITEMS = 3

#: How many recent accepted scenes must already sit on the preferred side before an axis stops
#: emitting located items for a book. Five is a placed number and is labelled as one: nothing has
#: measured how long a generator holds an instruction, and `research/quality-measurement/
#: feedback_ablation.py` is where that gets measured rather than guessed.
SATISFACTION_WINDOW = 5

#: Longest span quoted back into a prompt. A located difference is evidence, not an excerpt of
#: the book, and an unbounded quote is how a prompt grows without anyone deciding it should.
MAX_SPAN_CHARS = 220


class Role(enum.StrEnum):
    """Which role produced a unit of feedback. Recorded on every item and every verdict (I4)."""

    READER = "reader"
    JUDGE = "judge"


class DifferenceStatus(enum.StrEnum):
    """Where one located difference stands. One-shot, and no path back."""

    MINTED = "minted"
    SPENT = "spent"
    VOID = "void"


@dataclass(frozen=True, slots=True)
class LocatedDifference:
    """One judge output: an axis, a side, and a span. No valence and nowhere to put one.

    `sentence` is the judge's own answer, kept verbatim because it is the check the matcher
    cannot be — §89's credibility for E6 rests on responses like *"Passage A shows Wren's status
    with concrete values (Level 2, HP 19/22) while Passage B shows all status values as unknown
    (?)"*, and a stored match flag without the sentence behind it cannot be audited later.

    `high_address` is decided by the **counter**, never by the judge: the judge names which axis
    is salient and the deterministic layer decides which text is higher on it. So a judge cannot
    invert a direction, only fail to be useful.
    """

    difference_id: str
    batch_id: str
    book_id: str
    branch_id: str
    logical_id: str
    axis_id: str
    high_address: str
    low_address: str
    span: str
    sentence: str
    judge_id: str
    pool: Pool
    created_at: str
    status: DifferenceStatus = DifferenceStatus.MINTED

    def __post_init__(self) -> None:
        if self.axis_id not in AXES:
            raise ValueError(f"{self.axis_id} is not a registered axis")
        if self.high_address == self.low_address:
            raise ValueError("a located difference needs two sides")
        if not self.span.strip():
            raise ValueError("a difference with no span is not located")


class DiscardReason(enum.StrEnum):
    """Why a judge sentence produced no located difference. Distinct codes, because they are
    different facts about different things.

    `UNMATCHED` is a field report about a salient difference **the axis registry cannot yet
    name** — the same object the §74 human read produced, from a channel that runs at volume.
    `UNDIRECTED` is the composition rule biting: the axis is known and no reader has pointed
    it. `UNSEPARATED` is the judge claiming a difference *the material does not carry*, which
    is a judge-quality signal rather than a prose one. `AMBIGUOUS` is "the single most salient
    difference" turning out not to be single. `CONTROL` is a control response, retained
    because a confabulating judge's own sentence is the evidence that it confabulated.
    """

    UNMATCHED = "unmatched"
    UNDIRECTED = "undirected"
    UNSEPARATED = "unseparated"
    AMBIGUOUS = "ambiguous"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class JudgeDiscard:
    """One judge sentence that located nothing, kept verbatim with its provenance.

    **Counting these is not enough and that is the whole point of the table.** A sentence the
    matchers miss is the discovery corpus for every axis this registry does not have yet, and
    a corpus not persisted from the first batch is gone. So the sentence is stored as the
    judge said it, beside enough provenance to re-read it later: which pair, which batch,
    which slot the higher-counter text sat in, which model, and whether the batch's controls
    held.

    **The rail, and it is not negotiable.** This corpus may *nominate* a candidate axis; it
    may never *validate* one. A matcher drafted from these sentences and then scored against
    these sentences is a rubric fitted to its own answers, which is exactly what freezing
    `AXIS_MATCHERS` exists to prevent. A nominated axis follows the full admission path: a
    deterministic counter, an E6-family validation on **fresh pairs this corpus never
    touched**, and a reader-established direction, before it emits anything
    (`plan/reader-judge-loop.md` §2).
    """

    discard_id: str
    batch_id: str
    book_id: str
    branch_id: str
    logical_id: str
    reason: DiscardReason
    sentence: str
    #: Which slot the first-presented text occupied, so the corpus can be read for slot
    #: effects later without re-running anything.
    orientation: int
    #: The two texts' pair-member addresses, canonically ordered, or the control's own label.
    left_address: str
    right_address: str
    #: What the counters said separated this pair, comma-joined. Empty for a control and for
    #: a pair nothing separates — and those are different rows, which is why the reason code
    #: carries the meaning rather than this field.
    separating: str
    judge_id: str
    #: Whether the batch this rode in was usable. A sentence from a VOID batch is retained
    #: and marked, because it is evidence about the judge rather than about prose.
    batch_ok: bool
    created_at: str

    def __post_init__(self) -> None:
        if self.orientation not in (0, 1):
            raise ValueError(f"orientation {self.orientation} is not a bit")
        if not self.sentence.strip():
            raise ValueError(
                "an empty sentence is a call that failed, not a report to retain"
            )


def discard_id_for(
    *, batch_id: str, reason: str, left_address: str, right_address: str, sentence: str
) -> str:
    """Content address, so a replayed batch converges rather than growing the corpus.

    The sentence is in the hash because a judge asked the same question twice may answer
    differently, and two different answers to one pair are two field reports rather than a
    duplicate.
    """
    material = "\x00".join(
        (batch_id, reason, left_address, right_address, sentence)
    ).encode()
    return f"disc-{sha256(material).hexdigest()[:24]}"


def difference_id_for(
    *, batch_id: str, axis_id: str, high_address: str, low_address: str
) -> str:
    material = "\x00".join((batch_id, axis_id, high_address, low_address)).encode()
    return f"diff-{sha256(material).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class FeedbackItem:
    """One unit of feedback, ready to render. Cannot exist without a reader direction.

    The `AxisDirection` is held rather than flattened so the item carries its own licence: what
    makes this sayable is a measured reader preference, and an item that had only copied the
    pole would be a claim with its evidence removed.
    """

    role: Role
    direction: AxisDirection
    #: The located span, for a judge item; None for a standing reader item.
    span: str | None = None
    #: Where the span came from, so provenance survives into the payload.
    origin_id: str | None = None
    origin_logical_id: str | None = None

    def __post_init__(self) -> None:
        if self.role is Role.JUDGE and not (self.span and self.origin_id):
            raise ValueError(
                "a judge item is a *located* difference; without a span it is a preference, "
                "which is the frame this project has measured dead three times"
            )
        if self.role is Role.READER and self.span is not None:
            raise ValueError("a standing reader direction locates nothing and quotes nothing")

    @property
    def axis_id(self) -> str:
        return self.direction.axis_id

    def render(self) -> str:
        axis = AXES[self.axis_id]
        preferred = self.direction.preferred
        if self.role is Role.READER:
            return (
                f"Readers comparing two passages blind preferred the one with "
                f"{axis.phrase(preferred)}. Write toward that."
            )
        span = (self.span or "").strip()
        if len(span) > MAX_SPAN_CHARS:
            span = span[: MAX_SPAN_CHARS - 1].rstrip() + "…"
        toward = "Write toward that." if preferred is Pole.HIGH else "Write away from that."
        stance = (
            "readers' evidence prefers" if preferred is Pole.HIGH
            else "readers' evidence disprefers"
        )
        where = f" of {self.origin_logical_id}" if self.origin_logical_id else ""
        return (
            f"Two drafts{where} differed on {axis.phrase(Pole.HIGH)}; the one "
            f"{stance} reads: “{span}”. {toward}"
        )

    def to_payload(self) -> dict[str, object]:
        """The structured record that travels on the job payload beside the rendered text."""
        return {
            "role": self.role.value,
            "axis_id": self.axis_id,
            "preferred_pole": self.direction.preferred.value,
            "direction_digest": self.direction.verdicts_digest,
            "direction_lower_bound": self.direction.lower_bound,
            "span": self.span,
            "origin_id": self.origin_id,
            "origin_logical_id": self.origin_logical_id,
        }


#: The header the rendered block carries. It says *what kind of thing* this is, because the
#: context packet's own contract is "established and may be relied on; do not contradict it" and
#: craft guidance is neither established nor a fact about the story. Putting the two under one
#: heading is how an instruction becomes canon.
FEEDBACK_HEADER = (
    " Notes on this book's prose, from readers who compared passages blind and from a pass "
    "that located where two drafts differed. They are guidance about how to write, not facts "
    "about the story:"
)


@dataclass(frozen=True, slots=True)
class FeedbackSet:
    """The ordered items that shaped one draft, and the digest that identifies the set.

    **An empty set is a real object with a real digest.** I4's negative case: a scene drafted
    with no feedback records an explicit empty set, not a missing field, so "this scene had no
    feedback" and "nobody recorded whether this scene had feedback" are different rows rather
    than the same absence.
    """

    items: tuple[FeedbackItem, ...] = ()
    #: Items the cap dropped, reported rather than silently truncated.
    dropped: int = 0

    @property
    def empty(self) -> bool:
        return not self.items

    @property
    def digest(self) -> str:
        return payload_digest({"items": [item.to_payload() for item in self.items]})

    def render(self) -> str:
        """The system-message fragment, or the empty string when there is nothing to say."""
        if not self.items:
            return ""
        lines = "\n".join(f"- {item.render()}" for item in self.items)
        return f"{FEEDBACK_HEADER}\n{lines}"

    def to_payload(self) -> list[dict[str, object]]:
        return [item.to_payload() for item in self.items]

    def axes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.axis_id for item in self.items))


def satisfied(
    axis_id: str,
    direction: AxisDirection,
    recent_scenes: Sequence[str],
    *,
    window: int = SATISFACTION_WINDOW,
) -> bool:
    """Whether this book's recent prose already sits on the preferred side of this axis.

    Compared against the book's **own** running median rather than against an absolute band,
    for the reason `plan/reader-in-loop.md` §1 gives for relative fences: an absolute cap at the
    human band risks excluding everything the generator can produce, and a rule that always
    fires is a rule nobody can act on. A book with fewer than `window` scenes is never satisfied
    — there is not enough of it to say.
    """
    if len(recent_scenes) < window:
        return False
    values = [count(axis_id, text) for text in recent_scenes[-window:]]
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2.0
    )
    if direction.preferred is Pole.HIGH:
        return all(value >= median for value in values)
    return all(value <= median for value in values)


def compose(
    directions: Sequence[AxisDirection],
    located: Sequence[LocatedDifference],
    *,
    verdicts_digest: str,
    recent_scenes: Mapping[str, Sequence[str]] | None = None,
    max_items: int = MAX_FEEDBACK_ITEMS,
) -> FeedbackSet:
    """Compose the set that will shape the next draft, applying the rules that make it a signal.

    In order, and every step drops rather than degrades:

    1. A direction whose `verdicts_digest` has moved is **stale** and emits nothing (§72's
       expiry-on-use). Recomputing it silently would make the loop's own evidence unfalsifiable.
    2. A located difference on an axis with no direction is **discarded**: a judge may only
       speak on an axis a reader has given a direction to.
    3. An axis whose recent accepted scenes already sit on the preferred side is **satisfied**
       and emits no located item — it keeps its standing sentence, because the direction is
       still true, and stops repeating an instruction the prose already follows.
    4. Judge items are placed before reader items, because a located specimen from the book's
       own prose is the more actionable of the two, and the cap therefore falls on the standing
       sentences first.
    """
    live = {
        direction.axis_id: direction
        for direction in directions
        if not direction.stale_against(verdicts_digest)
    }
    scenes = recent_scenes or {}
    judge_items: list[FeedbackItem] = []
    seen_axes: set[str] = set()
    for difference in located:
        if difference.status is not DifferenceStatus.MINTED:
            continue
        direction = live.get(difference.axis_id)
        if direction is None or difference.axis_id in seen_axes:
            continue
        if satisfied(
            difference.axis_id, direction, tuple(scenes.get(difference.book_id, ()))
        ):
            continue
        seen_axes.add(difference.axis_id)
        judge_items.append(
            FeedbackItem(
                role=Role.JUDGE,
                direction=direction,
                span=difference.span,
                origin_id=difference.difference_id,
                origin_logical_id=difference.logical_id,
            )
        )
    reader_items = [
        FeedbackItem(role=Role.READER, direction=direction)
        for axis_id, direction in sorted(live.items())
        if axis_id not in seen_axes
    ]
    ordered = [*judge_items, *reader_items]
    kept = tuple(ordered[:max_items])
    return FeedbackSet(items=kept, dropped=max(0, len(ordered) - len(kept)))


EMPTY = FeedbackSet()


@dataclass(frozen=True, slots=True)
class SceneFeedback:
    """What shaped one accepted scene, keyed by the address the prose actually has.

    The job payload is the primary, crash-safe record — feedback is materialised into it at
    enqueue and the prompt is frozen there (I5). This is the queryable projection, and it exists
    as a row rather than a nullable column because "this scene had no feedback" and "nobody
    recorded whether this scene had feedback" are different facts that an absent row cannot tell
    apart. `items` is a JSON array and `[]` is a legitimate, expected value.
    """

    revision_id: str
    logical_id: str
    job_id: str
    digest: str
    items: tuple[Mapping[str, object], ...]
    dropped: int
    recorded_at: str

    @property
    def empty(self) -> bool:
        return not self.items


__all__ = [
    "EMPTY",
    "FEEDBACK_HEADER",
    "MAX_FEEDBACK_ITEMS",
    "MAX_SPAN_CHARS",
    "SATISFACTION_WINDOW",
    "DifferenceStatus",
    "DiscardReason",
    "FeedbackItem",
    "FeedbackSet",
    "JudgeDiscard",
    "LocatedDifference",
    "Role",
    "SceneFeedback",
    "compose",
    "difference_id_for",
    "discard_id_for",
    "satisfied",
]
