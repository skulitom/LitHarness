"""Work selection over the book's state — §4.1's policy, replacing the FIFO placeholder.

`fifo_selector` was honest about being a placeholder, and its stated blocker was "a plan
graph and a findings store that do not exist". This module removes the first half. The
second is untouched: `jobs.priority` stays inert, because a severity ordering with no
findings store is a selector over a column with one value.

Four decisions here are load-bearing.

**The queue is drained before the plan is consulted.** `claim_next` runs first and returns
immediately if it finds anything. That is what keeps requeued retries, revived units and
hand-enqueued jobs working — and, more importantly, it is what serialises drafting. Only
one draft job exists per book at a time, so revisions form a linear chain R0→R1→…→R6
instead of six siblings each overwriting the head. The alternative, planning all six beats
up front, produces a book with one scene of prose and no error anywhere.

**A blocked beat is skipped, not waited on.** §4.1: "a blocked or parked item never stalls
the queue — the Conductor works elsewhere in the book." There is no predecessor rule: if
beat 3 poisons, beats 4-6 still draft and the book finishes with a visible hole. A
sequential rule would be easier to reason about and would let one bad scene stop the book.

**Job ids are derived, and include the plan epoch.** Derived so a replayed tick converges
instead of re-enqueueing; epoch-versioned because `idempotency_key` is UNIQUE, so a
poisoned beat's id is spent forever and without a version "try scene 3 again" would be
inexpressible. The prompt is deliberately *excluded* from the derivation — editing the
template must not mint a second job for work already done.

**Books are visited least-progressed first.** Derived from the head revision rather than a
persisted cursor: fairness that cannot drift, and it is what makes §17's *two* fixture
books both finish rather than the first one starving the second.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import WorkSelector
from litharness.application.handlers import SCENE_DRAFT
from litharness.domain.beats import SIX_BEAT, Beat, BeatTemplate, TemplateMismatch, beats_for
from litharness.domain.draft import DraftPolicy, is_draftable
from litharness.domain.events import payload_digest
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plans import premise_of
from litharness.domain.revision import Revision

DEFAULT_TEMPLATE = SIX_BEAT


def beat_job_id(
    book_id: str, branch_id: str, logical_id: str, template_id: str, epoch: int
) -> str:
    """Stable identity for "draft this beat of this book under this plan epoch".

    Excludes the prompt and the base revision. Including the prompt would mint a second job
    every time the template is edited, for work already accepted; including the base would
    mint one after every acceptance, since the head moves each time.
    """
    material = payload_digest(
        {
            "book_id": book_id,
            "branch_id": branch_id,
            "logical_id": logical_id,
            "template_id": template_id,
            "epoch": epoch,
        }
    )
    return f"beat-{sha256(material.encode()).hexdigest()[:24]}"


def render_prompt(beat: Beat, *, book_title: str | None, premise: str) -> tuple[str, str]:
    """(system, prompt) for one beat. Deliberately thin.

    This is the seam context assembly attaches to in the next slice — §12 step 2 wants the
    frozen revision's local prose, locked constraints, game state, POV-visible knowledge and
    distant callbacks. None of that is here, and pretending otherwise by stuffing in
    whatever is cheap to reach would make the later slice a rewrite rather than an
    extension. What is here is what a template planner can honestly supply: where the scene
    sits, what it is for, and what the book is about.
    """
    system = (
        "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
        "no commentary, no summary of what you wrote."
    )
    title = f"{book_title}: " if book_title else ""
    prompt = (
        f"{title}{beat.title or beat.logical_id}\n"
        f"Scene {beat.ordinal} of {beat.of_total}. Dramatic function: {beat.function}.\n\n"
        f"Premise: {premise}\n\n"
        "Write this scene."
    )
    return system, prompt


@dataclass(frozen=True, slots=True)
class BookProgress:
    """What the operator surface reports per book."""

    book_id: str
    branch_id: str
    drafted: int
    total: int
    #: Set when the book cannot be planned at all — no premise, or a template mismatch.
    blocked_reason: str | None = None

    @property
    def complete(self) -> bool:
        return self.blocked_reason is None and self.total > 0 and self.drafted == self.total


def _book_title(revision: Revision) -> str | None:
    roots = revision.children_of(None)
    return roots[0].title if roots else None


def plan_progress(
    store: SqliteStore,
    book_id: str,
    branch_id: str,
    *,
    template: BeatTemplate = DEFAULT_TEMPLATE,
    policy: DraftPolicy | None = None,
) -> BookProgress:
    """How far this book has got, and why it cannot move if it cannot.

    A blocked book reports its reason rather than looking finished. `NO_WORK` over a book
    with no premise and `NO_WORK` over a finished book are the same tick outcome, and
    telling them apart is the difference between a green board and a true one.
    """
    head = store.head(book_id, branch_id)
    if head is None:
        return BookProgress(book_id, branch_id, 0, 0, "no head revision")
    try:
        beats = beats_for(head, template)
    except TemplateMismatch as mismatch:
        return BookProgress(book_id, branch_id, 0, 0, str(mismatch))
    if premise_of(store.plan_items(book_id, branch_id)) is None:
        return BookProgress(
            book_id,
            branch_id,
            sum(1 for beat in beats if not is_draftable(head, beat.logical_id, policy=policy)),
            len(beats),
            "no single premise plan item; import a plan snapshot for this book",
        )
    drafted = sum(
        1 for beat in beats if not is_draftable(head, beat.logical_id, policy=policy)
    )
    return BookProgress(book_id, branch_id, drafted, len(beats))


def make_plan_selector(
    *,
    template: BeatTemplate = DEFAULT_TEMPLATE,
    policy: DraftPolicy | None = None,
    project_id: str = "",
) -> WorkSelector:
    """Build a `WorkSelector` that materialises the next unblocked beat.

    A closure rather than a widened protocol: `WorkSelector.__call__(store, holder, now,
    duration)` has no book scope, and the book set is state the selector carries. Widening
    the protocol would change every existing selector and its tests for one caller's
    benefit — the same reason handlers are closures.
    """

    def select(store: SqliteStore, holder: str, now: float, duration: float) -> Job | None:
        # 1. Drain first. Retries, revived units and hand-enqueued work outrank planning,
        #    and one in-flight draft per book is what keeps the lineage linear.
        claimed = store.claim_next(holder, now=now, duration=duration)
        if claimed is not None:
            return claimed

        stamp = datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")
        day = stamp[:10]

        # 2. Least-progressed book first: fairness derived from state, no cursor to drift.
        books = [
            plan_progress(store, book_id, branch_id, template=template, policy=policy)
            for book_id, branch_id, _ in store.branches()
        ]
        for progress in sorted(books, key=lambda item: (item.drafted, item.book_id)):
            if progress.blocked_reason is not None:
                continue
            head = store.head(progress.book_id, progress.branch_id)
            if head is None:  # pragma: no cover - plan_progress already excluded this
                continue
            premise = premise_of(store.plan_items(progress.book_id, progress.branch_id))
            if premise is None:  # pragma: no cover - blocked_reason covers it
                continue
            epoch = store.plan_epoch(progress.book_id, progress.branch_id)
            beats = beats_for(head, template)
            ids = [
                beat_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id,
                    template.template_id, epoch,
                )
                for beat in beats
            ]
            # One draft in flight per book. Drain-first usually achieves this, but not when
            # the queued job is leased by another holder — and a second beat planned against
            # the same base is exactly how the branch forks.
            if store.any_unfinished(ids):
                continue

            for beat in beats:
                # 3. The selector's precondition IS the gate's — one function, no drift.
                if not is_draftable(head, beat.logical_id, policy=policy):
                    continue
                job_id = beat_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id,
                    template.template_id, epoch,
                )
                if store.has_job(job_id):
                    # Already planned under this epoch: in flight, or burned by a poison.
                    continue
                system, prompt = render_prompt(
                    beat, book_title=_book_title(head), premise=premise
                )
                payload = {
                    "revision_id": head.revision_id,
                    "book_id": progress.book_id,
                    "branch_id": progress.branch_id,
                    "logical_id": beat.logical_id,
                    "prompt": prompt,
                    "system": system,
                    "profile": "default",
                    # Why this beat, recorded durably. There is no WorkSelected event type
                    # in the contract, and inventing one would need a minor for something
                    # only this payload reads.
                    "selected_by": {
                        "template_id": beat.template_id,
                        "beat_function": beat.function,
                        "ordinal": beat.ordinal,
                        "of_total": beat.of_total,
                        "plan_epoch": epoch,
                        "predicate": "draftable.v0",
                    },
                }
                inserted = store.enqueue(
                    Job(
                        job_id=job_id,
                        job_kind=SCENE_DRAFT,
                        payload=payload,
                        input_digest=input_digest_for(payload),
                    )
                )
                if not inserted:
                    # A row exists that `has_job` did not see. Counting it as planned would
                    # be reporting a write that did nothing.
                    continue
                store.bump_digest(day, "beats_enqueued")
                return store.claim_next(holder, now=now, duration=duration)

        # 4. Nothing draftable anywhere. NO_WORK, which `status` distinguishes from
        #    "finished" via plan_progress.
        return None

    return select


__all__ = [
    "DEFAULT_TEMPLATE",
    "BookProgress",
    "beat_job_id",
    "make_plan_selector",
    "plan_progress",
    "render_prompt",
]
