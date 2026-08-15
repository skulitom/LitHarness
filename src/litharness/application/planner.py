"""Work selection over the book's state — §4.1's policy, replacing the FIFO placeholder.

`fifo_selector` was honest about being a placeholder, and its stated blocker was "a plan
graph and a findings store that do not exist". This module removes the first half; the
findings store landed with slice 9.

**`jobs.priority` is no longer inert, and this docstring said it was for two stages after it
stopped being true.** Both lanes here mint above the default (1000 + precedence for explicit
direction, 500 + precedence for interpretive), and Stage 2's repair chain mints at 80 and 100,
so the claim order `(priority DESC, rowid)` now sorts a queue with four bands in it. What is
still absent is a *severity* ordering: a finding's severity does not reach the job it
produces, so two repairs of very different urgency are claimed in insertion order. That is the
column's remaining unused half, and it is the accurate version of what this paragraph used to
claim about the whole of it.

Four decisions here are load-bearing.

**Explicit direction is materialised before the queue is drained.** A newly ingested,
unambiguously scoped constraint or veto becomes a high-priority deterministic plan job
before an older scene draft can be claimed. Everything else retains the durable queue's
ordering. This is the smallest rule under which "the next tick sees the directive" means
the system cannot draft one more scene against an explicit constraint already in its inbox.

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

from litharness.application.conductor import WorkSelector
from litharness.application.directive_planner import (
    DIRECTIVE_PLAN,
    directive_job_id,
    is_verbatim_actionable,
)
from litharness.application.handlers import SCENE_DRAFT
from litharness.application.narrative_planner import (
    NARRATIVE_PLAN,
    is_interpretive_actionable,
    narrative_job_id,
)
from litharness.application.ports import ApplicationStore, PlanningStore
from litharness.domain.beats import (
    SIX_BEAT,
    Beat,
    BeatTemplate,
    TemplateMismatch,
    arc_template,
    beats_for,
    scene_nodes,
)
from litharness.domain.context import (
    COUNTER_ID,
    DEFAULT_TOKEN_BUDGET,
    ContextBudgetTooSmall,
    ContextPacket,
    assemble,
)
from litharness.domain.directives import Directive, DirectiveStatus
from litharness.domain.draft import DraftPolicy, is_draftable
from litharness.domain.events import payload_digest
from litharness.domain.extraction import progression_target, system_voice_example
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plans import premise_of
from litharness.domain.revision import Revision
from litharness.domain.text import content_hash

DEFAULT_TEMPLATE = SIX_BEAT


def template_for(revision: Revision, template: BeatTemplate | None = None) -> BeatTemplate:
    """The sheet that fits this book, unless a caller names one.

    **`SIX_BEAT` is kept for six-scene books rather than letting the arc cover them**, even
    though `arc_template(6)` produces identical functions. `beat_job_id` derives from the
    template *id*, so switching the fixtures onto `template.arc-6.v0` would remint every beat
    job id in both golden books for no change in what any beat asks for. The arc reproduces
    the sheet; it does not replace it.

    A book of any other length gets an arc of its own length, which is what makes §17 Stage 3
    reachable at all: `beats_for` refuses a mismatch, so before this every book that was not
    exactly six scenes reported itself blocked.
    """
    if template is not None:
        return template
    scenes = len(scene_nodes(revision))
    return SIX_BEAT if scenes == len(SIX_BEAT) else arc_template(scenes)


def _resolved_directive_scope(
    directive: Directive, branches: list[tuple[str, str, str]]
) -> tuple[str, str] | None:
    """Resolve only unambiguous scope; never guess across books or branches."""
    candidates = [
        (book_id, branch_id)
        for book_id, branch_id, _ in branches
        if directive.book_id in {None, book_id}
        and directive.branch_id in {None, branch_id}
    ]
    return candidates[0] if len(candidates) == 1 else None


def _enqueue_verbatim_direction(store: PlanningStore) -> bool:
    """Materialise the highest-precedence safe directive, if its scope is unambiguous."""
    branches = store.branches()
    for directive in store.ingested_directives_by_status(DirectiveStatus.RECEIVED):
        if not is_verbatim_actionable(directive):
            continue
        scope = _resolved_directive_scope(directive, branches)
        if scope is None:
            continue
        book_id, branch_id = scope
        if store.plan_revision(book_id, branch_id) is None:
            continue
        # The resolved scope belongs to the work unit, not the immutable directive. An
        # unscoped instruction stays visibly unscoped even when one current branch made its
        # destination unambiguous at selection time.
        payload = {
            "directive_id": directive.directive_id,
            "book_id": book_id,
            "branch_id": branch_id,
        }
        inserted = store.enqueue(
            Job(
                job_id=directive_job_id(directive.directive_id),
                job_kind=DIRECTIVE_PLAN,
                payload=payload,
                input_digest=input_digest_for(payload),
                # Explicit direction must precede already-queued scene work. Precedence
                # remains visible inside this lane, above the ordinary priority-0 queue.
                priority=1000 + directive.precedence,
            )
        )
        if inserted:
            return True
    return False


def _enqueue_interpretive_direction(store: PlanningStore) -> bool:
    """Materialise one model-backed directive only when its destination is unambiguous."""
    branches = store.branches()
    for directive in store.ingested_directives_by_status(DirectiveStatus.RECEIVED):
        if not is_interpretive_actionable(directive):
            continue
        scope = _resolved_directive_scope(directive, branches)
        if scope is None:
            continue
        book_id, branch_id = scope
        if store.plan_revision(book_id, branch_id) is None:
            continue
        epoch = store.plan_epoch(book_id, branch_id)
        payload = {
            "directive_id": directive.directive_id,
            "book_id": book_id,
            "branch_id": branch_id,
            "plan_epoch": epoch,
        }
        if store.enqueue(
            Job(
                job_id=narrative_job_id(directive.directive_id, epoch),
                job_kind=NARRATIVE_PLAN,
                payload=payload,
                input_digest=input_digest_for(payload),
                # Mechanical constraints/vetoes use 1000+. Model interpretation still
                # outranks prose, but can never jump ahead of exact director instruction.
                priority=500 + directive.precedence,
            )
        ):
            return True
    return False


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


def render_prompt(
    beat: Beat,
    *,
    book_title: str | None,
    packet: ContextPacket,
    status_example: str | None = None,
    target_words: int = 0,
    progression: str | None = None,
) -> tuple[str, str]:
    """(system, prompt) for one beat, grounded in an assembled context packet.

    This was the seam §12 step 2 attaches to, and the packet is now what fills it. Before,
    the prompt was the scene's title, its ordinal, the word "resolution" and the premise —
    so the final scene of a locked-room mystery was asked to resolve it while knowing
    nothing of what had been found, who was in the room, or what the book had promised.

    The packet goes *before* the instruction and the instruction last, because the last
    thing in a prompt is the thing a model acts on; leading with "write this scene" and
    then supplying the book invites a scene written from the header.

    **`status_example` closes the loop §12 step 5 opened and could not run.** Extraction reads
    the `[STATUS]` line and nothing else, and nothing ever asked a generator to write one — so
    every record in the system came from an imported snapshot, `state.contradiction.v0` could
    only fire on prose somebody else wrote, and the propagation producer had no fact of the
    system's own to compare.

    **It is the book's own current line rather than a template with placeholders, and that is
    a measurement.** Shown `STATUS_TEMPLATE` with its `{subject}` slot intact, one of three
    local models wrote the placeholder out verbatim. The line still matched the parser — a
    brace-wrapped word is a perfectly good subject — and still extracted nothing, because
    `{subject}` is no name canon knows: a scene that looks right, parses right, and
    establishes nothing. See `extraction.system_voice_example`.

    It is **omitted unless the book already speaks system voice**, since the example is built
    from canon and there is none to build from otherwise. A stat block in a locked-room
    mystery is not a smaller error than a missing one.

    **`target_words` was a parameter this function accepted and never read**, and the defect
    is worth stating because of what was recorded on top of it. It arrived in `8f7075c` as
    exactly two lines — the signature here and the call site in `make_plan_selector` — while
    the body below constructed `system` and `prompt` without ever mentioning it. So the
    numbers that commit reports (`llama3.2` 235 -> 232, `phi4` 289 -> 426, "+47%") are two
    draws from **byte-identical prompts**, and its live test loops over
    `(0, DraftPolicy().target_words)` through the same ignoring function, so the assertion
    could not fail. Measured after wiring it (three draws per arm, seeds held common):
    `llama3.2` 279 -> 384 and `phi4` 324 -> 612 words. The instruction the record called
    ignored by a 3B model moves it 38%, because it had never been sent.
    """
    system = (
        "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
        "no commentary, no summary of what you wrote. The context below is established and "
        "may be relied on; do not contradict it."
    )
    if status_example:
        # Values as well as shape. A model asked for a status line with no numbers in view
        # invents them, and an invented balance is a contradiction the gate refuses and the
        # repair loop pays for.
        system += (
            " This book states its game state on the page. End the scene with a status line "
            f"in this form, which is the state as it stands:\n{status_example}\n"
            "Write the character's name as your prose spells it, carry these values forward "
            "unchanged unless this scene changes them, and write the numbers the scene "
            "leaves true."
        )
        if progression:
            # **The instruction above defaults to stasis, and a model with no reason to
            # change anything keeps everything.** Measured over 24 scenes: the ledger never
            # moved once. A milestone gives the scene somewhere to be going, which is the
            # thing "unless this scene changes them" silently assumed the model would decide
            # for itself. "Toward" rather than "to": jumping to the milestone would collapse
            # the progression the schedule exists to spread out.
            system += (
                " The book's plan has the state reaching this later on:\n"
                f"{progression}\n"
                "Move it toward that in this scene where the events warrant it; do not jump "
                "to it, and do not move it for no reason on the page."
            )
    if target_words:
        # **Length is asked for by giving the scene somewhere to spend it**, which is the
        # difference the measurement found. A bare "write approximately 900 words" moves
        # `phi4` 324 -> 458; naming what the length is *for* moves it 324 -> 611, and
        # `llama3.2` 279 -> 384 where the bare form reached 329. The second sentence is
        # doing the work: a model told only a number pads, and padding is §1a.3 item 6's
        # "summarising instead of dramatising" arriving by the door that was opened to
        # avoid it. So the instruction spends its words on events rather than on the count.
        system += (
            f" Write approximately {target_words} words. A scene of that length has room to "
            "play out in real time — what is said, what is done, what is noticed — instead "
            "of being told in summary. Do not pad it with restatement to reach the length; "
            "give the scene enough events to fill it."
        )
    title = f"{book_title}: " if book_title else ""
    prompt = (
        f"{packet.render()}\n\n"
        f"Now write {title}{beat.title or beat.logical_id} — scene {beat.ordinal} of "
        f"{beat.of_total}. Dramatic function: {beat.function}."
    )
    return system, prompt


def packet_for(
    store: PlanningStore,
    revision: Revision,
    beat: Beat,
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    pov_character_id: str | None = None,
) -> ContextPacket:
    """Load this book's plan and state and assemble the beat's packet.

    The one place the packet touches the store. `assemble` stays pure so the golden
    `GoldContextSuite` can grade it without a database, which is also what keeps the grading
    honest — a test that had to build a store to ask "is the motive in the packet" would be
    testing the store.

    **No story-time cutoff is passed, and that is a decision rather than an omission.**
    `domain/state.py` records why: nothing defines a mapping from a manuscript scene to an
    `order_key`, and inventing `f"s{beat.ordinal}"` would fit both fixtures and silently
    mis-slice every other book. In the live loop the question does not arise — records are
    extracted from accepted prose, so the only records that exist describe scenes already
    written. It arises only for a book imported with its state intact, which is inspection.
    """
    # **Only a summary of the prose that is actually there.** `scene_summaries` returns every
    # summary ever written for a scene, keyed by the content hash it was written from, and the
    # packet takes the one matching the node's current text. A scene repaired since it was
    # summarised therefore contributes nothing rather than contributing a description of prose
    # the book no longer contains — which is the failure mode a summary cache has and a prose
    # cache does not, since the prose is the thing itself.
    stored = store.scene_summaries(revision.book_id, revision.branch_id)
    summaries: dict[str, str] = {}
    for logical_id, by_hash in stored.items():
        try:
            node = revision.node(logical_id)
        except KeyError:
            continue
        if node.content is None:
            continue
        current = by_hash.get(content_hash(node.content))
        if current is not None:
            summaries[logical_id] = current

    return assemble(
        revision,
        beat.logical_id,
        plan_items=store.plan_items(revision.book_id, revision.branch_id),
        state_records=store.state_records(revision.book_id, revision.branch_id),
        query_id=f"beat:{beat.logical_id}",
        pov_character_id=pov_character_id,
        token_budget=token_budget,
        summaries=summaries,
    )


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
    store: PlanningStore,
    book_id: str,
    branch_id: str,
    *,
    template: BeatTemplate | None = None,
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
        beats = beats_for(head, template_for(head, template))
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
    template: BeatTemplate | None = None,
    policy: DraftPolicy | None = None,
    project_id: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> WorkSelector:
    """Build a `WorkSelector` that materialises the next unblocked beat.

    A closure rather than a widened protocol: `WorkSelector.__call__(store, holder, now,
    duration)` has no book scope, and the book set is state the selector carries. Widening
    the protocol would change every existing selector and its tests for one caller's
    benefit — the same reason handlers are closures.

    `token_budget` bounds the *context* a beat is drafted against, and is separate from
    `BudgetPolicy`'s ceilings, which bound the spend. They fail differently and on purpose: a
    context budget drops the oldest scene from the packet, a spend ceiling refuses the call.
    """

    def select(
        store: ApplicationStore, holder: str, now: float, duration: float
    ) -> Job | None:
        # 1. Make safe, explicit direction claimable first. A constraint received before
        #    this tick must affect the next scene, not the scene after it.
        _enqueue_verbatim_direction(store)
        _enqueue_interpretive_direction(store)

        # 2. Drain. Retries, revived units and hand-enqueued work retain their ordering,
        #    except for explicit direction; one draft at a time keeps lineage linear.
        claimed = store.claim_next(holder, now=now, duration=duration)
        if claimed is not None:
            return claimed

        stamp = datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")
        day = stamp[:10]

        # 3. Least-progressed book first: fairness derived from state, no cursor to drift.
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
            if premise_of(store.plan_items(progress.book_id, progress.branch_id)) is None:
                continue  # pragma: no cover - blocked_reason covers it
            plan_revision = store.plan_revision(progress.book_id, progress.branch_id)
            if plan_revision is None:  # pragma: no cover - premise lookup implies a plan
                continue
            epoch = store.plan_epoch(progress.book_id, progress.branch_id)
            beats = beats_for(head, template_for(head, template))
            ids = [
                beat_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id,
                    template_for(head, template).template_id, epoch,
                )
                for beat in beats
            ]
            # One draft in flight per book. Drain-first usually achieves this, but not when
            # the queued job is leased by another holder — and a second beat planned against
            # the same base is exactly how the branch forks.
            if store.any_unfinished(ids):
                continue

            for beat in beats:
                # 4. The selector's precondition IS the gate's — one function, no drift.
                if not is_draftable(head, beat.logical_id, policy=policy):
                    continue
                job_id = beat_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id,
                    template_for(head, template).template_id, epoch,
                )
                if store.has_job(job_id):
                    # Already planned under this epoch: in flight, or burned by a poison.
                    continue
                try:
                    packet = packet_for(store, head, beat, token_budget=token_budget)
                except ContextBudgetTooSmall:
                    # A ceiling too small to hold the premise refuses the *book*, not this
                    # beat: every beat of it would refuse identically, and enqueueing six
                    # units that each fail the same way is how a queue fills with one
                    # misconfiguration. Skipping leaves `plan_progress` reporting the book
                    # undrafted, which is true.
                    break
                if packet.omitted:
                    # **A book being written blind should not be quiet about it.** The
                    # omissions have always been recorded on the job payload, where nothing
                    # reads them; the daily digest is §4.3's operator report and `status`
                    # already prints it. Measured: at the 900-word target this binds at
                    # scene 5 and the packet holds three prior scenes, so by mid-book a scene
                    # is drafted knowing almost nothing of the book before it — and it drops
                    # the *oldest* prose rather than the least relevant, with no way to know
                    # the difference (§12 gives relevance to LongRangeContext).
                    store.bump_digest(
                        datetime.fromtimestamp(now, tz=UTC).date().isoformat(),
                        "context_omitted",
                        len(packet.omitted),
                    )
                system, prompt = render_prompt(
                    beat,
                    book_title=_book_title(head),
                    packet=packet,
                    status_example=system_voice_example(
                        store.state_records(progress.book_id, progress.branch_id),
                        at=beat.story_order_key,
                    ),
                    target_words=(policy or DraftPolicy()).target_words,
                    progression=progression_target(
                        store.state_records(progress.book_id, progress.branch_id),
                        at=beat.story_order_key,
                    ),
                )
                payload = {
                    "revision_id": head.revision_id,
                    "book_id": progress.book_id,
                    "branch_id": progress.branch_id,
                    "logical_id": beat.logical_id,
                    "prompt": prompt,
                    "system": system,
                    "profile": "default",
                    "plan_revision_id": plan_revision.plan_revision_id,
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
                        # Where the template says this beat sits in story time, or None when
                        # it is not entitled to say. Travels on the payload rather than being
                        # recomputed in the handler, so the position a scene was extracted
                        # under is the one the plan held when the work was selected — a later
                        # template edit cannot retroactively move a scene already written.
                        "story_order_key": beat.story_order_key,
                    },
                    # What the scene was told, and what it was not. `context_omitted` is the
                    # honest half: a baseline that packs by priority rather than relevance
                    # will drop things a scorer would have kept, and the omission being in
                    # the payload is what makes that reviewable after the fact instead of
                    # invisible in a prompt nobody kept.
                    "context": {
                        "query_id": packet.query_id,
                        "items": len(packet.items),
                        "tokens": packet.used_tokens,
                        "budget": packet.token_budget,
                        "counter": COUNTER_ID,
                        "sections": {
                            name: len(items)
                            for name, items in packet.sections.items()
                            if items
                        },
                    },
                    "context_omitted": [
                        {"source": item.source_logical_id, "reason": item.reason}
                        for item in packet.omitted
                    ],
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

        # 5. Nothing draftable anywhere. NO_WORK, which `status` distinguishes from
        #    "finished" via plan_progress.
        return None

    return select


__all__ = [
    "DEFAULT_TEMPLATE",
    "BookProgress",
    "beat_job_id",
    "make_plan_selector",
    "packet_for",
    "plan_progress",
    "render_prompt",
    "template_for",
]
