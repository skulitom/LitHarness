"""The Judge role: located differences over a contrast pair, in the one frame that survived.

**What this is not.** It is not a critic, it does not score a scene, and it never says which
of two passages is better. Every single-passage frame this project has tested has died, and
every *verdict* frame has died too — T0 disqualified the incumbent panel at a positional bias
of 0.8151 over 568 decided comparisons, §89's E1/E2 are VOID at 0.6408 over 142, and a 4B
model's answer distribution at the verdict token is 4,676x position over text. So a judge here
is handed two passages and asked what differs, which is the one question the same model on the
same pairs answered 40/40, 30/32 and 18/36 against measured nulls.

**Which side is decided by the counter, never by the judge.** The judge names the salient axis
and the deterministic layer does everything else: `axes.higher` decides which text is higher,
`axes.locate` extracts the span by the counter's own definition. A judge that named the wrong
side therefore cannot invert a direction — it can only fail to be useful, which is the failure
mode worth having.

**A judge may only speak on an axis a reader has given a direction to.** `run_batch` refuses
outright when no live direction exists, before any call is made, because discrimination without
direction cannot say which way to move and paying for it would be paying for half a signal.

**Three controls ride every batch and two of them refuse.** A byte-identical placebo and a
whitespace-only sham are judged alongside the real pairs; naming a prose axis on either voids
the batch, so nothing it located is believed. The third — orientation symmetry, E6's substitute
for a positional precondition, since E6 asks for no choice and `positional_bias` would be a
check that cannot fail — accumulates over the book rather than the batch, because a K=3
tournament yields six responses against a thirty-response floor.

**A void batch still keeps its sentences.** They are marked `batch_ok = 0` and retained,
because a confabulating judge's own words are the evidence that it confabulated — and because
every sentence the matchers miss is a field report about a salient difference the axis registry
cannot yet name. That corpus may nominate a future axis; it may never validate one.

**The contrast surface is the tournament, and never §61's pairing.** Contrasting a candidate
against matched published prose is §61's own comparison, and spending it on steering destroys
the measurement it exists for.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from dataclasses import replace as dc_replace
from hashlib import sha256

from litharness.application.feedback_loop import live_directions
from litharness.application.ports import FeedbackLoopStore, TextGenerator
from litharness.domain import axes as axes_mod
from litharness.domain import discrimination as e6
from litharness.domain.candidates import SpanCandidate
from litharness.domain.feedback import (
    DifferenceStatus,
    DiscardReason,
    JudgeDiscard,
    LocatedDifference,
    difference_id_for,
    discard_id_for,
)
from litharness.domain.generation import CompletionRequest, CompletionResult
from litharness.domain.pools import Pool, passage_pool

#: The call class every judge call is billed under. Named so a budget report can separate the
#: discrimination channel from generation, and so `plan/provider-adapters.md` §3's mechanical
#: routing applies: conformance is the point of this call and creativity is its failure mode.
JUDGE_CALL_CLASS = "judgment"

#: The reserved judge-id prefix. **It is `preference.MACHINE_READER_PREFIX` restated, not
#: imported, and the two must not be unified.** That prefix marks a row in the *pair* table
#: that a machine wrote; this marks provenance in a table no human ever writes. Sharing the
#: constant would invite sharing the semantics, and the whole structural point of
#: `located_differences` is that it is not the pair table.
JUDGE_ID_PREFIX = "judge:"


class BatchVerdict(enum.StrEnum):
    """Whether a batch's output may be believed. A named refusal, never a silent zero."""

    OK = "ok"
    NO_DIRECTION = "no_direction"
    NOT_STEERING = "not_steering"
    TOO_FEW_CANDIDATES = "too_few_candidates"
    PLACEBO_CONFABULATED = "placebo_confabulated"
    SHAM_CONFABULATED = "sham_confabulated"
    ORIENTATION_ASYMMETRIC = "orientation_asymmetric"


@dataclass(frozen=True, slots=True)
class BatchResult:
    """One judge batch: what it located, what it refused, and why.

    Every discard is counted rather than dropped. §89's rulebook is the reason — a protocol
    that reports only its hits reads as precise when it was merely quiet, and four of the five
    quantities caught early there were caught by a dry run printing what it had skipped.
    """

    batch_id: str
    verdict: BatchVerdict
    differences: tuple[LocatedDifference, ...] = ()
    #: **Every sentence that located nothing, verbatim.** Returned rather than counted: an
    #: unmatched sentence is a field report about a salient difference the axis registry
    #: cannot yet name, from a channel that runs at volume, and a corpus not persisted from
    #: the first batch is gone. The caller writes these for *every* batch, void ones
    #: included, because a void batch's sentences are evidence about the judge.
    discards: tuple[JudgeDiscard, ...] = ()
    calls: int = 0
    #: Responses naming no registered axis the counter also separates.
    unnamed: int = 0
    #: Responses naming an axis with no reader direction — the composition rule biting.
    undirected: int = 0
    #: Responses naming more than one separating axis, so "the single most salient" was not.
    ambiguous: int = 0
    #: Pairs no registered counter separates: nothing for the judge to have been right about.
    unseparated: int = 0
    controls: Mapping[str, str] = field(default_factory=dict)
    orientation: e6.OrientationCheck | None = None

    @property
    def usable(self) -> bool:
        return self.verdict is BatchVerdict.OK


def batch_id_for(*, book_id: str, branch_id: str, logical_id: str, job_id: str) -> str:
    material = "\x00".join((book_id, branch_id, logical_id, job_id)).encode()
    return f"jb-{sha256(material).hexdigest()[:24]}"


def judge_request(
    left: str, right: str, *, call_class: str = JUDGE_CALL_CLASS
) -> CompletionRequest:
    """One E6 presentation. The question is `E6_QUESTION` and the schema is `E6_SCHEMA`.

    Blinded: the judge sees two passages and nothing else — no statements, no provenance, no
    addresses. Position-swapped by the caller, which runs both orientations so orientation
    symmetry has something to count.
    """
    return CompletionRequest(
        prompt=(
            f"PASSAGE ONE:\n{left}\n\nPASSAGE TWO:\n{right}\n\n{e6.E6_QUESTION}"
        ),
        system=(
            "You are describing the difference between two passages. Do not say which you "
            "prefer or which is better. Return only the requested JSON."
        ),
        schema=e6.E6_SCHEMA,
        max_output_tokens=e6.ANSWER_MAX_TOKENS,
        profile="mechanical",
        call_class=call_class,
    )


def said(result: CompletionResult) -> str | None:
    """The judge's sentence, or None for an answer the schema did not hold.

    None is not "no difference": a malformed reply is a call that failed, and treating it as
    a null result would launder a parse failure into a measurement — the same distinction
    `_judge_verdict` makes on the verdict path.
    """
    if result.parsed is None:
        return None
    difference = result.parsed.get("difference")
    return difference if isinstance(difference, str) and difference.strip() else None


def _orientation_rows(store: FeedbackLoopStore, book_id: str) -> list[tuple[int, bool]]:
    """Prior responses for this book, as `(orientation, named_anything)` rows.

    **Read from both tables, which is what makes the check honest.** A located difference is
    a response that named an axis; a discard row is a response that did not, and the discard
    corpus keeps every one of them with its orientation. Before that corpus existed this check
    could only see the hits, so unseen silence could only make the two slots look more equal —
    conservative, but blind in exactly the direction the check is about. It now sees both.

    Control rows are excluded: a placebo has no higher side, so its slot means nothing.
    """
    rows: list[tuple[int, bool]] = []
    for difference in store.located_differences(book_id=book_id):
        if difference.status is DifferenceStatus.VOID:
            continue
        rows.append((0 if difference.high_address < difference.low_address else 1, True))
    for discard in store.judge_discards(book_id=book_id):
        if discard.reason is DiscardReason.CONTROL or not discard.batch_ok:
            continue
        rows.append((discard.orientation, False))
    return rows


@dataclass
class _Discards:
    """Accumulator for the sentences that located nothing, with the batch's own provenance."""

    batch_id: str
    book_id: str
    branch_id: str
    logical_id: str
    judge_id: str
    created_at: str
    rows: list[JudgeDiscard] = field(default_factory=list)

    def add(
        self,
        *,
        reason: DiscardReason,
        sentence: str,
        orientation: int,
        left_address: str,
        right_address: str,
        separating: Sequence[str] = (),
    ) -> None:
        self.rows.append(
            JudgeDiscard(
                discard_id=discard_id_for(
                    batch_id=self.batch_id,
                    reason=reason.value,
                    left_address=left_address,
                    right_address=right_address,
                    sentence=sentence,
                ),
                batch_id=self.batch_id,
                book_id=self.book_id,
                branch_id=self.branch_id,
                logical_id=self.logical_id,
                reason=reason,
                sentence=sentence,
                orientation=orientation,
                left_address=left_address,
                right_address=right_address,
                separating=",".join(separating),
                judge_id=self.judge_id,
                # Provisional. `finish` rewrites it once the batch's verdict is known, so a
                # row can never claim its batch held when it did not.
                batch_ok=True,
                created_at=self.created_at,
            )
        )

    def finish(self, *, ok: bool) -> tuple[JudgeDiscard, ...]:
        return tuple(dc_replace(row, batch_ok=ok) for row in self.rows)


def run_batch(
    registry: TextGenerator,
    store: FeedbackLoopStore,
    candidates: Sequence[SpanCandidate],
    *,
    judge_id: str,
    created_at: str,
    call_class: str = JUDGE_CALL_CLASS,
) -> BatchResult:
    """Judge one span's siblings and return the located differences, or say why there are none.

    Refuses before spending in three cases, in this order: no live reader direction (the
    composition rule), a span outside the steering pool (the measurement firewall), and fewer
    than two candidates (nothing to contrast). Each is a `BatchVerdict` rather than an
    exception, because "there is nothing to say here" is the normal state of this channel and
    an exception would make the normal state look like a fault.

    **Every sentence the judge produces comes back**, located or not, in `discards`. The
    caller writes them whatever the verdict: an unmatched sentence is the discovery corpus for
    axes this registry does not have, and a sentence from a void batch is evidence about the
    judge. A batch that is refused *before spending* produces no sentences and therefore no
    rows, which is a different thing from a batch whose sentences were thrown away.
    """
    if not candidates:
        return BatchResult(batch_id="", verdict=BatchVerdict.TOO_FEW_CANDIDATES)
    first = candidates[0]
    batch_id = batch_id_for(
        book_id=first.book_id,
        branch_id=first.branch_id,
        logical_id=first.logical_id,
        job_id=first.job_id,
    )
    if len(candidates) < 2:
        return BatchResult(batch_id=batch_id, verdict=BatchVerdict.TOO_FEW_CANDIDATES)

    registration = store.pool_registration()
    pool = (
        passage_pool(first.base_revision_id, first.logical_id, registration)
        if registration is not None
        else None
    )
    if pool is not Pool.STEERING:
        return BatchResult(batch_id=batch_id, verdict=BatchVerdict.NOT_STEERING)

    live, _stale = live_directions(store)
    directed = {direction.axis_id for direction in live}
    if not directed:
        return BatchResult(batch_id=batch_id, verdict=BatchVerdict.NO_DIRECTION)

    calls = 0
    controls: dict[str, str] = {}
    bucket = _Discards(
        batch_id=batch_id,
        book_id=first.book_id,
        branch_id=first.branch_id,
        logical_id=first.logical_id,
        judge_id=judge_id,
        created_at=created_at,
    )

    # **The controls are bought first, so a confabulating judge costs two calls rather than
    # the whole batch.** Built from the first candidate's own text so the control is over the
    # same material the batch is about, not over a fixture the judge has never seen.
    placebo, _ = registry.complete(
        judge_request(first.text, first.text, call_class=call_class)
    )
    calls += 1
    placebo_said = said(placebo)
    placebo_reading = e6.placebo_verdict(placebo_said)
    controls["placebo"] = placebo_reading.value
    if placebo_said:
        bucket.add(
            reason=DiscardReason.CONTROL,
            sentence=placebo_said,
            orientation=0,
            left_address="control:placebo_identical",
            right_address="control:placebo_identical",
        )
    if placebo_reading is e6.ControlVerdict.CONFABULATED:
        return BatchResult(
            batch_id=batch_id,
            verdict=BatchVerdict.PLACEBO_CONFABULATED,
            calls=calls,
            controls=controls,
            discards=bucket.finish(ok=False),
        )
    sham_text = e6.whitespace_sham(first.text)
    if sham_text != first.text:
        sham, _ = registry.complete(
            judge_request(first.text, sham_text, call_class=call_class)
        )
        calls += 1
        sham_said = said(sham)
        sham_reading = e6.sham_verdict(sham_said)
        controls["sham"] = sham_reading.value
        if sham_said:
            bucket.add(
                reason=DiscardReason.CONTROL,
                sentence=sham_said,
                orientation=0,
                left_address="control:rewhitespace_sham",
                right_address="control:rewhitespace_sham",
            )
        if sham_reading is e6.ControlVerdict.CONFABULATED:
            return BatchResult(
                batch_id=batch_id,
                verdict=BatchVerdict.SHAM_CONFABULATED,
                calls=calls,
                controls=controls,
                discards=bucket.finish(ok=False),
            )
    else:
        # A text with no sentence-final single space cannot carry this sham. Reported rather
        # than silently skipped: a control that did not run is not a control that passed.
        controls["sham"] = "not_applicable"

    located: dict[str, LocatedDifference] = {}
    rows: list[tuple[int, bool]] = _orientation_rows(store, first.book_id)
    unnamed = undirected = ambiguous = unseparated = 0
    ordered = sorted(candidates, key=lambda candidate: candidate.candidate_id)
    for index, one in enumerate(ordered):
        for other in ordered[index + 1 :]:
            separating = axes_mod.separating(one.text, other.text)
            if not separating:
                unseparated += 1
                continue
            for orientation, (left, right) in enumerate(((one, other), (other, one))):
                result, _ = registry.complete(
                    judge_request(left.text, right.text, call_class=call_class)
                )
                calls += 1
                sentence = said(result)
                if sentence is None:
                    # A malformed answer is a call that failed, not a report. Nothing to
                    # retain, and it counts as silence for the orientation check.
                    unnamed += 1
                    rows.append((orientation, False))
                    continue
                named = e6.named_axes(sentence, separating)
                rows.append((orientation, bool(named)))

                def keep(
                    reason: DiscardReason,
                    *,
                    _sentence: str = sentence,
                    _orientation: int = orientation,
                    _left: str = left.address,
                    _right: str = right.address,
                    _separating: tuple[str, ...] = separating,
                ) -> None:
                    """Retain this sentence. Defaults bind the loop variables at definition
                    time, so the closure cannot read a later iteration's values — the late-
                    binding bug this shape exists to make unrepresentable."""
                    bucket.add(
                        reason=reason,
                        sentence=_sentence,
                        orientation=_orientation,
                        left_address=_left,
                        right_address=_right,
                        separating=_separating,
                    )

                if not named:
                    # **The discovery corpus.** A salient difference this registry cannot yet
                    # name, reported by a channel that runs at volume — the same object §74's
                    # human read produced once. Retained verbatim; it may nominate a future
                    # axis and it may never validate one.
                    unnamed += 1
                    keep(DiscardReason.UNMATCHED)
                    continue
                if len(named) > 1:
                    # "The single most salient difference" was not single. Discarded rather
                    # than resolved by picking one: choosing for the judge would be supplying
                    # the discrimination the judge was asked for.
                    ambiguous += 1
                    keep(DiscardReason.AMBIGUOUS)
                    continue
                axis_id = named[0]
                if axis_id not in directed:
                    # The composition rule biting. Kept as the queue of what reader evidence
                    # would unlock: these are axes the judge can already see.
                    undirected += 1
                    keep(DiscardReason.UNDIRECTED)
                    continue
                high_text = axes_mod.higher(axis_id, one.text, other.text)
                if high_text is None:
                    # The judge claimed a difference the material does not carry. A
                    # judge-quality signal, which is why it is its own reason code.
                    unseparated += 1
                    keep(DiscardReason.UNSEPARATED)
                    continue
                high = one if high_text == one.text else other
                low = other if high is one else one
                span = axes_mod.locate(axis_id, high.text)
                if not span:
                    unnamed += 1
                    keep(DiscardReason.UNSEPARATED)
                    continue
                difference_id = difference_id_for(
                    batch_id=batch_id,
                    axis_id=axis_id,
                    high_address=high.address,
                    low_address=low.address,
                )
                located[difference_id] = LocatedDifference(
                    difference_id=difference_id,
                    batch_id=batch_id,
                    book_id=high.book_id,
                    branch_id=high.branch_id,
                    logical_id=high.logical_id,
                    axis_id=axis_id,
                    high_address=high.address,
                    low_address=low.address,
                    span=span,
                    sentence=sentence,
                    judge_id=judge_id,
                    pool=Pool.STEERING,
                    created_at=created_at,
                )

    orientation_reading = e6.orientation_check(rows)
    asymmetric = orientation_reading.reading is e6.OrientationReading.ASYMMETRIC
    return BatchResult(
        batch_id=batch_id,
        verdict=(
            BatchVerdict.ORIENTATION_ASYMMETRIC if asymmetric else BatchVerdict.OK
        ),
        differences=() if asymmetric else tuple(located[key] for key in sorted(located)),
        discards=bucket.finish(ok=not asymmetric),
        calls=calls,
        unnamed=unnamed,
        undirected=undirected,
        ambiguous=ambiguous,
        unseparated=unseparated,
        controls=controls,
        orientation=orientation_reading,
    )


def machine_judge_id(model: str) -> str:
    """The judge id a located difference is stamped with. Always reserved-prefixed."""
    return f"{JUDGE_ID_PREFIX}{model}"


__all__ = [
    "JUDGE_CALL_CLASS",
    "JUDGE_ID_PREFIX",
    "BatchResult",
    "BatchVerdict",
    "batch_id_for",
    "judge_request",
    "machine_judge_id",
    "run_batch",
    "said",
]
