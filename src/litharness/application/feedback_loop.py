"""The reader → writer loop's one coordination point: verdicts in, a frozen feedback set out.

Three callers share this module and that is why it exists rather than being spread across
them: `planner.make_plan_selector` materialises a set into the payload at enqueue,
`cli.cmd_directions` reports what the evidence says, and `judge_panel` refuses to speak on an
axis this module has no direction for. Three implementations of "is this axis directed" would
drift, and the drift is not benign — the whole composition rule is that a judge may only speak
where a reader has pointed.

**Nothing here can block.** It reads verdicts and returns text. There is no `GateOutcome`
construction, no `blocking` flag, no park, and no import of `domain.policy`;
`tests/test_reader_judge_loop.py` asserts the absence rather than trusting a caller. A
reader-derived gate would still be a gate (§10.4), and the whole point of routing feedback into
a *prompt* is that a prompt refuses nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from litharness.application.ports import (
    FeedbackLoopStore,
    FeedbackRepository,
    PreferenceRepository,
)
from litharness.domain import axes as axes_mod
from litharness.domain import directions as directions_mod
from litharness.domain import feedback as feedback_mod
from litharness.domain.directions import AxisDirection, DirectionReading
from litharness.domain.feedback import DifferenceStatus, FeedbackSet
from litharness.domain.nodes import NodeKind
from litharness.domain.pools import Pool, PoolRegistration, reader_pool
from litharness.domain.preference import PairSample, excerpt_address
from litharness.domain.revision import Revision


def excerpt_texts(store: PreferenceRepository) -> dict[str, str]:
    """Address → text for every excerpt the pair engine knows about.

    Candidate texts land in `comparison_corpus` as part of `commit_tournament`, so this
    resolves both sides of an internal sibling pair without a second table. A pair whose
    member text is missing is skipped rather than guessed at — an unresolvable member is a
    pair nothing can be measured on.
    """
    return {excerpt_address(item.excerpt_id): item.text for item in store.excerpts()}


def _reader_pool_fn(
    registration: PoolRegistration | None,
) -> Callable[[str], Pool]:
    def pool_of(reader_id: str) -> Pool:
        return reader_pool(reader_id, registration)

    return pool_of


def readings(
    store: FeedbackLoopStore,
    *,
    at: str,
) -> tuple[DirectionReading, ...]:
    """What the steering readers currently say about each registered axis.

    Read-only and total: every registered axis gets a row, and an axis with no evidence gets
    a row saying `NO_EVIDENCE` rather than being absent. §89's rulebook is the reason — five
    of seven declared quantities that could not do their job were caught by a dry run printing
    *which* precondition was unmet, and a listing that omitted the silent axes would have hidden
    every one of them.
    """
    registration = store.pool_registration()
    samples = store.pair_samples()
    texts = excerpt_texts(store)
    pool_of = _reader_pool_fn(registration)
    return tuple(
        directions_mod.read_direction(
            axis_id, samples, texts, reader_pool=pool_of, established_at=at
        )
        for axis_id in axes_mod.AXES
    )


def current_digests(
    store: FeedbackLoopStore,
) -> dict[str, str]:
    """The per-axis observation digest as it stands right now.

    A stored `AxisDirection` is stale when its own `verdicts_digest` differs from this, which is
    §72's expiry-on-use pattern moved one instrument over. Per-axis rather than global on
    purpose: the global answered-verdict digest would stale every direction whenever any
    verdict anywhere landed, and a loop that retires its evidence on unrelated rows is a loop
    that flickers rather than one that expires.
    """
    registration = store.pool_registration()
    samples: Sequence[PairSample] = store.pair_samples()
    texts = excerpt_texts(store)
    pool_of = _reader_pool_fn(registration)
    out: dict[str, str] = {}
    for axis_id in axes_mod.AXES:
        observations, _ = directions_mod.axis_observations(
            samples, texts, axis_id, reader_pool=pool_of
        )
        out[axis_id] = directions_mod.observations_digest(observations)
    return out


def live_directions(
    store: FeedbackLoopStore,
) -> tuple[tuple[AxisDirection, ...], tuple[AxisDirection, ...]]:
    """(live, stale) — the established directions, split by whether their evidence has moved.

    Newest row per axis only: `axis_directions` is newest-first and a superseded measurement is
    history, not a second claim, which is `calibrations`' own rule applied here.
    """
    digests = current_digests(store)
    live: list[AxisDirection] = []
    stale: list[AxisDirection] = []
    seen: set[str] = set()
    for direction in store.axis_directions():
        if direction.axis_id in seen:
            continue
        seen.add(direction.axis_id)
        target = (
            stale
            if direction.stale_against(digests.get(direction.axis_id, ""))
            else live
        )
        target.append(direction)
    return tuple(live), tuple(stale)


def recent_scene_texts(revision: Revision | None, *, window: int) -> tuple[str, ...]:
    """The last `window` scenes that carry prose, in reading order.

    Read off the head revision rather than from a store query: the head is already loaded on
    the planning path, and the satisfaction rule is about *this book's own* recent prose.
    """
    if revision is None:
        return ()
    texts = [
        node.content
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content and not node.tombstoned
    ]
    return tuple(texts[-window:])


@dataclass(frozen=True, slots=True)
class Materialised:
    """A feedback set plus the differences whose one-shot status the caller must now spend."""

    feedback: FeedbackSet
    spend: tuple[str, ...]


def resolve(
    store: FeedbackLoopStore,
    *,
    book_id: str,
    branch_id: str,
    head: Revision | None,
) -> Materialised:
    """The feedback set that will shape the next draft of this book, and nothing more.

    **Returns an empty set rather than raising when the loop is not running**, which is the
    autonomy constraint §61 states in one sentence: the production loop requires no human
    input, human judgment enters asynchronously and gates promotions, never ticks. With no
    pool registration, no direction, or no located difference, this returns `EMPTY` and the
    book drafts exactly as it did before — and the *empty set is recorded* rather than
    omitted, which is invariant I4's negative case.
    """
    if store.pool_registration() is None:
        return Materialised(feedback=feedback_mod.EMPTY, spend=())
    live, _stale = live_directions(store)
    if not live:
        return Materialised(feedback=feedback_mod.EMPTY, spend=())
    located = [
        difference
        for difference in store.located_differences(
            book_id=book_id, branch_id=branch_id, status=DifferenceStatus.MINTED
        )
        if difference.pool is Pool.STEERING
    ]
    recent = recent_scene_texts(head, window=feedback_mod.SATISFACTION_WINDOW)
    digests = current_digests(store)
    # `compose` takes one digest and checks each direction against it; passing the per-axis
    # map would make the signature depend on the registry. Composing per axis keeps the domain
    # function total over one axis at a time and the loop here is three iterations.
    items: list[feedback_mod.FeedbackItem] = []
    dropped = 0
    for direction in live:
        one = feedback_mod.compose(
            [direction],
            [d for d in located if d.axis_id == direction.axis_id],
            verdicts_digest=digests.get(direction.axis_id, ""),
            recent_scenes={book_id: recent},
            max_items=1,
        )
        items.extend(one.items)
        dropped += one.dropped
    kept = tuple(items[: feedback_mod.MAX_FEEDBACK_ITEMS])
    composed = feedback_mod.FeedbackSet(
        items=kept, dropped=dropped + max(0, len(items) - len(kept))
    )
    spend = tuple(
        item.origin_id
        for item in composed.items
        if item.role is feedback_mod.Role.JUDGE and item.origin_id
    )
    return Materialised(feedback=composed, spend=spend)


def payload_fields(feedback: FeedbackSet) -> dict[str, object]:
    """The three fields every draft payload carries, whether or not there was feedback.

    **`feedback` is a list and `[]` is the expected value; `feedback_digest` is a real digest
    of the empty list and is never null.** That is invariant I4 in one function: a scene
    drafted with no feedback records an explicit empty set, not a missing field, and the two
    are different facts that a nullable column cannot tell apart.
    """
    return {
        "feedback": feedback.to_payload(),
        "feedback_digest": feedback.digest,
        "feedback_dropped": feedback.dropped,
    }


def record_provenance(
    store: FeedbackRepository,
    *,
    revision_id: str,
    logical_id: str,
    job_id: str,
    payload: Mapping[str, object],
    recorded_at: str,
) -> bool:
    """Project the payload's frozen feedback onto the revision the prose actually has.

    A payload with no `feedback` key at all — a job enqueued by hand before this existed, or
    by a caller that does not use the planner — records an empty set. That is the honest
    reading and it is *not* the same row as a payload that carried `[]`: the digest of an
    empty list is a constant, so the two are distinguishable after the fact by anyone who
    cares to check the job.
    """
    raw = payload.get("feedback")
    items = tuple(raw) if isinstance(raw, list) else ()
    digest = payload.get("feedback_digest")
    dropped = payload.get("feedback_dropped")
    return store.record_scene_feedback(
        feedback_mod.SceneFeedback(
            revision_id=revision_id,
            logical_id=logical_id,
            job_id=job_id,
            digest=str(digest) if digest else feedback_mod.EMPTY.digest,
            items=items,
            dropped=int(dropped) if isinstance(dropped, int) else 0,
            recorded_at=recorded_at,
        )
    )


__all__ = [
    "Materialised",
    "current_digests",
    "excerpt_texts",
    "live_directions",
    "payload_fields",
    "readings",
    "recent_scene_texts",
    "record_provenance",
    "resolve",
]
