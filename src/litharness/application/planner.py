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
from litharness.application.director import (
    direct_job_id,
    director_job,
    scene_block,
)
from litharness.application.feedback_loop import payload_fields, resolve
from litharness.application.handlers import SCENE_DRAFT
from litharness.application.narrative_planner import (
    NARRATIVE_PLAN,
    is_interpretive_actionable,
    narrative_job_id,
)
from litharness.application.outline import (
    BOOK_OUTLINE,
    OUTLINE_PRIORITY,
    outline_job_id,
)
from litharness.application.plan_search import (
    PLAN_SEARCH,
    PLAN_SEARCH_PRIORITY,
    plan_search_job_id,
    span_select_job,
    span_select_job_id,
)
from litharness.application.ports import ApplicationStore, PlanningStore
from litharness.domain import worlds
from litharness.domain.beats import (
    SIX_BEAT,
    Beat,
    BeatTemplate,
    TemplateMismatch,
    beats_for,
    template_for,
)
from litharness.domain.candidates import (
    CandidateStatus,
    SpanCandidate,
    evidence_complete,
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
from litharness.domain.extraction import (
    progression_target,
    stated_position,
    system_voice_example,
)
from litharness.domain.feedback import FeedbackSet
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plans import premise_of, scene_plan_for, scene_plan_line
from litharness.domain.revision import Revision
from litharness.domain.serials import Position, SerialShape, chapter_positions
from litharness.domain.text import content_hash
from litharness.domain.writers import Writer

DEFAULT_TEMPLATE = SIX_BEAT


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


def _enqueue_direction(store: ApplicationStore, director_id: str) -> bool:
    """Mint one Director unit for a book whose current scene-block has not been spoken for.

    Two bounds, and they answer different failure modes. The **block** key means a book hears
    from its Director once per `DIRECTIVE_EVERY` accepted scenes rather than once per tick, and
    it is keyed on progress rather than on plan epoch because a directive *causes* an epoch bump
    and a bound that its own effect resets is a spin loop. The **live** check means a Director
    that has already spoken and not yet been interpreted stays quiet, so the inbox cannot fill
    with machine direction while a person's sits behind it.
    """
    enqueued = False
    for book_id, branch_id, _head in store.branches():
        head = store.head(book_id, branch_id)
        if head is None:
            continue
        if store.machine_directives(book_id, branch_id, live_only=True):
            continue
        block = scene_block(head)
        job_id = direct_job_id(book_id, branch_id, block)
        if store.has_job(job_id):
            continue
        if store.enqueue(director_job(book_id, branch_id, block, director_id)):
            enqueued = True
    return enqueued


def _enqueue_ready_selections(store: ApplicationStore) -> bool:
    """Materialise `span_select` work for every parked tournament whose evidence is ready.

    The human path (§61 Add 3): a `plan_search` job parks its span awaiting reader
    verdicts, and nothing about a parked unit can wake itself — so the selector, which
    already materialises directives and outlines, is the seam that notices the evidence
    arriving. Readiness is derived, not stored: the required sample ids are content
    addresses over the candidate texts, `evidence_complete` demands an answered verdict on
    BOTH orientations of every sibling pair, and the whole scan opens with one indexed
    query that is empty in the normal state.

    A group whose plan epoch has moved is discarded here rather than judged: the epoch
    machinery already cancelled its queued selection job, and its candidates are evidence
    about a dead plan. Discarding keeps the pending scan self-cleaning instead of
    re-checking a dead tournament every tick forever. A group whose *head* moved is still
    enqueued — the selection handler owns that refusal, because a stale tournament must
    discard with a recorded decision, and the selector records nothing.
    """
    pending = store.pending_span_candidates()
    if not pending:
        return False
    groups: dict[tuple[str, str, str, str], list[SpanCandidate]] = {}
    for candidate in pending:
        key = (
            candidate.book_id,
            candidate.branch_id,
            candidate.logical_id,
            candidate.job_id,
        )
        groups.setdefault(key, []).append(candidate)
    samples = store.pair_samples()
    enqueued = False
    for (book_id, branch_id, logical_id, search_job_id), group in sorted(groups.items()):
        epoch = group[0].plan_epoch
        if store.plan_epoch(book_id, branch_id) != epoch:
            for candidate in group:
                store.set_span_candidate_status(
                    candidate.candidate_id, CandidateStatus.DISCARDED
                )
            continue
        if store.has_job(span_select_job_id(book_id, branch_id, logical_id, epoch)):
            continue
        if not evidence_complete(group, samples):
            continue
        if store.enqueue(
            span_select_job(
                book_id, branch_id, logical_id, epoch, search_job_id=search_job_id
            )
        ):
            enqueued = True
    return enqueued


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
    scene_plan: str | None = None,
    feedback: FeedbackSet | None = None,
    writer: Writer | None = None,
    criteria: str | None = None,
    chapter: Position | None = None,
    point_of_view: str | None = None,
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

    **`feedback` is the seam the reader → writer loop attaches to, and it goes in the system
    message rather than in the packet.** The packet's own contract is "established and may be
    relied on; do not contradict it" — a craft instruction is neither established nor a fact
    about the story, and putting the two under one heading is how an instruction becomes canon.
    It sits beside `target_words` and the status-line instruction because those are the two
    existing inputs of the same kind: things about *how* to write, not about *what* is true.
    Empty by default and empty is the common case: with no pool registration, no established
    direction or no located difference, `feedback_loop.resolve` returns an empty set and this
    renders nothing (`plan/reader-judge-loop.md` §5.1).

    **`criteria` is the standard the scene is being judged against inside its own world**
    (`plan/state-model-abilities.md` §5 item 11: *show the generator the criterion it is writing
    against*). It goes in the system message for the boundary `feedback` and `writer` already
    observe: a criterion is a rule about how this world judges, which is closer to how to write
    the book than to what happened in it, and under the packet's "established and may be relied
    on" heading it would invite a scene to *state* the ladder rather than show somebody moving
    up it. `None` for every book that declares no criterion, which is every book written before
    `domain/worlds.py` existed.

    **`writer` is the drafter's identity, and `None` is the control.** Until 2026-08-20 the
    drafter had none: the paragraph above was the whole of its self, and everything topical it
    knew arrived through the packet, which is a *book*-shaped input. A dossier is the first
    *writer*-shaped one. Off by default because **no writer is the control** — a change to
    drafting behaviour that could only be produced by editing code is an arm nobody can
    reproduce — and because the prior in `plan/writer-roster.md` §2 says a roster is more likely
    decorative than not until `writer_distinctness` says otherwise.

    **`chapter` is a position and it is deliberately not an instruction.** Until now the draft
    path had no notion of a chapter at all: grouping existed only at publish time as
    `--chapter-scenes`, `domain/serials.py` had no caller in `src/`, and a writer told "scene 4
    of 8" could not know that scene 4 was the last one a reader receives in one sitting. The
    fragment says where the scene sits and then stops — `Chapter 2, scene 1 of 4.` — with no verb
    and no adjective, because *how* to end a chapter is the director's to say and a default here
    would be this system's own taste arriving in every prompt it ever renders (stage-0 §95's
    scope axiom, §97.1). `None` renders nothing and is the control, and
    `serials.chapter_positions` returns nothing at all under the shape that asserts nothing, so
    the default path is byte-identical to what it was before this existed.

    It goes in the **beat line**, after the ordinal and before the dramatic function, and not
    after the statement. `plans.scene_plan_line` is rendered last always, and `plan_search`'s
    controlled comparison is only controlled while the K candidates differ in that final
    fragment and nowhere else.

    **`point_of_view` is the same class of thing as `chapter`, and it is held to the same
    boundary.** It says whose scene this is — one declared cast id, the one this book's canon
    names as its protagonist — and then stops. `Point of view: kell.` has no verb and no
    adjective, because *how* to handle a protagonist is the director's to say and a default here
    would be this system's own taste arriving in every prompt it ever renders (stage-0 §95's
    scope axiom, §97.1). Nothing here says open on them, make them likeable, or show them
    winning; `test_the_point_of_view_fragment_carries_no_verb_and_no_adjective` checks it.

    `None` renders nothing and is the control: every book written before a world could declare a
    protagonist passes `None`, and its prompt is byte-identical to what it was. It sits beside
    the chapter cue and before the dramatic function, for the chapter cue's reason.
    """
    system = (
        "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
        "no commentary, no summary of what you wrote. The context below is established and "
        "may be relied on; do not contradict it."
    )
    if writer is not None:
        # **Ahead of the mechanics and never in the packet** (`plan/writer-roster.md` §3.2).
        # The packet's contract is "established and may be relied on; do not contradict it",
        # and a novelist's career is not a fact about the story — putting one under that
        # heading is how a writer's biography becomes canon in the book they are writing.
        # This is the boundary `feedback` already observes, for the same stated reason.
        #
        # It goes *first* because it is who is writing, and the mechanics that follow are
        # what to do; the packet and the beat still come last in `prompt`, where a model
        # acts on them. And R5 holds regardless of order: where the dossier and the packet
        # meet, the packet outranks it. A writer who knows metallurgy from the inside is
        # being asked to write *this* book, not a book about metallurgy — which is the
        # contamination G3 exists to measure.
        system = f"{writer.render()}\n\n{system}"
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
    if criteria:
        # **The criterion the scene is writing against** (`plan/state-model-abilities.md` §5
        # item 11). It goes in the system message rather than in the packet for the boundary
        # `feedback` and the writer dossier already observe: a criterion is a rule about how
        # this world *judges*, which is closer to how to write the book than to what happened
        # in it. Putting it under "established and may be relied on" would invite the scene to
        # state the ladder rather than to show somebody moving up it.
        system += (
            "\nThis world judges people by the following, and a scene that changes where "
            "someone stands must show the change rather than announce it — a rank is "
            "something a reader sees, never something a narrator reports:\n"
            f"{criteria}"
        )
    if feedback is not None and not feedback.empty:
        system += f"\n{feedback.render()}"
    title = f"{book_title}: " if book_title else ""
    # **What this scene is for, which until now was one word shared with twenty-four others.**
    # `arc_template(30)` yields 25 `rising` beats, and the line below was the whole of the
    # plan-side instruction — so twenty-five of thirty (ordinals 3-17 and 19-28, the turn at
    # 18) were asked an identical question, and Book
    # Zero answered it by re-issuing its own errand five times (§52). The statement goes last
    # for the reason the beat line already went last: the final thing in a prompt is the thing
    # a model acts on, and between "rising" and "Kestrel is refused entry at the archive",
    # this is the one to act on.
    plan_line = scene_plan_line(scene_plan) if scene_plan else ""
    chapter_line = (
        ""
        if chapter is None
        else (
            f" Chapter {chapter.chapter_index}, scene {chapter.index_in_chapter} of "
            f"{chapter.scenes_in_chapter}."
        )
    )
    pov_line = "" if not point_of_view else f" Point of view: {point_of_view}."
    prompt = (
        f"{packet.render()}\n\n"
        f"Now write {title}{beat.title or beat.logical_id} — scene {beat.ordinal} of "
        f"{beat.of_total}.{chapter_line}{pov_line} Dramatic function: {beat.function}."
        f"{plan_line}"
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

    **The story-time cutoff is the beat's own key, and only where the planner is entitled to
    state one.** This paragraph used to say no cutoff was passed at all, on the ground that
    nothing defines a mapping from a manuscript scene to an `order_key` and that in the live
    loop the question does not arise, because records are extracted from accepted prose and
    so only ever describe scenes already written.

    That reasoning is sound for extracted records and does not reach **seeded** ones. A want
    or a fear that changes across a book is future-dated by construction, so a packet with no
    cutoff hands scene one what the character will want in chapter two — the story's engine
    given away before it starts. Measured on an eight-scene book seeded with two wants at
    `s1` and `s5`: both arrived in the Established facts block while drafting scene 1.

    **The claim is still not this module's**, and it is not minted here either. It is
    `stated_position`, unchanged and called one layer over: a `BeatTemplate` that declares
    itself chronological is a statement about the sheet the planner laid out, and
    `beats_for` turns it into `story_order_key`. So this abstains in exactly the cases
    `extraction` abstains in, for exactly its reasons — a book with a story vocabulary
    somebody else chose gets no cutoff, and its packet is byte-identical to what it was
    before this existed. Both golden fixtures are that book.

    A record with no `story_position` survives any cutoff (`state.records_before`), which is
    what keeps a world rule, a standing relationship or the fifteen-record ability-graph seed
    — all of them true of the book rather than of a moment in it — in every packet.
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

    records = store.state_records(revision.book_id, revision.branch_id)

    return assemble(
        revision,
        beat.logical_id,
        plan_items=store.plan_items(revision.book_id, revision.branch_id),
        state_records=records,
        query_id=f"beat:{beat.logical_id}",
        pov_character_id=pov_character_id,
        token_budget=token_budget,
        # See the docstring. `stated_position` is the entitlement check, not a new one: it
        # returns the beat's key only for a book whose story positions nobody else chose.
        story_time_cutoff=stated_position(records, beat.story_order_key),
        summaries=summaries,
        # **Where the book stands, and it is a different question from the cutoff above.**
        # The cutoff decides which records *exist yet* and is gated by `stated_position`, so it
        # is `None` for any book whose story positions somebody else chose. This asks whether
        # the reader has been *told* a thing, against positions the Architect minted from this
        # book's own beat sheet — so it is entitled to the beat's key unconditionally, and a
        # forged world's schedule keeps working on an imported book where the cutoff abstains.
        #
        # The two lines were written by different sessions within a day of each other and the
        # merge is where they met. They agree: a non-chronological template mints no key, both
        # go `None`, the cutoff returns everything and every scheduled answer stays hidden —
        # which is the safe direction for each of them separately.
        disclosure_at=beat.story_order_key,
        # The promise ledger's open rows (§61 Add 2), surfaced in the THREADS section so
        # generation gets to SEE what the book owes and by when. Read-only, and `assemble`
        # packs them as DERIVED — a model-sourced debt informs the scene without entering
        # canon, the property §46 built for milestones.
        promises=tuple(
            store.promises(revision.book_id, revision.branch_id, open_only=True)
        ),
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
    outline: bool = True,
    plan_search: bool = False,
    director_id: str = "",
    scenes_per_chapter: int = 1,
) -> WorkSelector:
    """Build a `WorkSelector` that materialises the next unblocked beat.

    A closure rather than a widened protocol: `WorkSelector.__call__(store, holder, now,
    duration)` has no book scope, and the book set is state the selector carries. Widening
    the protocol would change every existing selector and its tests for one caller's
    benefit — the same reason handlers are closures.

    **`outline=False` is the operator saying "do not spend a model call planning this book",
    and it exists because the measurement needs it.** §54's headline — near-copies 5/30 with
    no outline against 0/30 with one — is a comparison of two books, and a control arm that
    could only be produced by editing the code would be a control nobody could reproduce. It
    is also the honest flag for a book somebody plans by hand: the drafting path already
    treats a scene without a statement as ordinary, so this changes nothing except whether
    the statements are asked for.

    `token_budget` bounds the *context* a beat is drafted against, and is separate from
    `BudgetPolicy`'s ceilings, which bound the spend. They fail differently and on purpose: a
    context budget drops the oldest scene from the packet, a spend ceiling refuses the call.

    **`plan_search=True` is the §61 Add 3 arm: a span is drafted by tournament.** Instead
    of one `scene_draft` per beat, the selector mints one `plan_search` job — K alternative
    beat-plans, K candidate drafts, pairwise selection — and the winner arrives through the
    selection job's commit. Off by default for the same reason `outline` is a flag: the
    acceptance experiment (search book vs no-search book) needs two arms an operator can
    reproduce without editing code, and the no-search arm is exactly the behaviour that
    shipped before this existed. A beat whose scene-plan item is director-locked drafts the
    ordinary way even under the flag — alternatives touch only unlocked SCENE_PLAN items.

    **`scenes_per_chapter` is the operator's shape, and the only thing it does is tell the
    writer where the scene sits.** It is the number `--chapter-scenes` already hands
    `library.publish`, threaded to the one other place in the system where a chapter means
    anything — so a book is grouped for a reader and drafted against the same grouping rather
    than against two that can disagree. One is the default and it asserts nothing, which is
    `library.py`'s refusal and now this path's: under it `serials.chapter_positions` yields no
    positions and every rendered prompt is byte-for-byte what it was before this parameter
    existed. Nothing here tells a scene what to *do* about being last in its chapter; that is
    the director's to say (stage-0 §95).
    """

    def select(
        store: ApplicationStore, holder: str, now: float, duration: float
    ) -> Job | None:
        # 1. Make safe, explicit direction claimable first. A constraint received before
        #    this tick must affect the next scene, not the scene after it.
        _enqueue_verbatim_direction(store)
        _enqueue_interpretive_direction(store)

        # 1a. The Director speaks, if one is selected and this book's block is unspoken for.
        #     **After both human lanes and before the drain**, which is the whole ordering
        #     argument: a person's direction is materialised first and can never be buried by
        #     a machine's, and direction that exists before this tick shapes the next scene
        #     rather than the one after it (§4.1's reason for putting ingest first).
        if director_id:
            _enqueue_direction(store, director_id)

        # 1b. Wake any parked tournament whose evidence arrived since the last tick.
        #     Unconditional rather than gated on `plan_search`: verdicts answer whenever
        #     readers answer, and a tournament minted under the flag must still complete
        #     after the flag is turned off — evidence paid for is evidence consumed.
        _enqueue_ready_selections(store)

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
        # A tournament awaiting selection IS this book's one draft in flight (§21), even
        # though its job row is parked: the candidates were drafted against the current
        # head and the selection will commit one of them. Minting more draft work for the
        # same book would guarantee that whichever commits first invalidates the other —
        # paid drafts systematically discarded as stale. So the *book's drafting* waits on
        # the evidence while the Conductor works elsewhere: other books, and every queued
        # non-draft unit, which the drain above claims before this loop is reached. A
        # stale group (epoch moved) was already discarded by the readiness scan.
        awaiting = {
            (candidate.book_id, candidate.branch_id)
            for candidate in store.pending_span_candidates()
            if candidate.plan_epoch
            == store.plan_epoch(candidate.book_id, candidate.branch_id)
        }
        for progress in sorted(books, key=lambda item: (item.drafted, item.book_id)):
            if progress.blocked_reason is not None:
                continue
            if (progress.book_id, progress.branch_id) in awaiting:
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
            # Where each scene sits in its chapter, grouped once per book rather than once
            # per beat. Empty under the default shape, which asserts nothing, and empty is
            # what makes the ordinary prompt byte-identical to what it was.
            positions = (
                chapter_positions(head, SerialShape(scenes_per_chapter=scenes_per_chapter))
                if scenes_per_chapter > 1
                else {}
            )

            # **The book is outlined when its own sheet cannot tell its scenes apart.**
            # `arc_template(30)` yields 25 `rising` beats, and the beat's function word is
            # the whole of the plan-side instruction — so twenty-five scenes are asked an
            # identical question, which §52 measured as the cause of both the duplicated
            # scenes and the ledger that moved once. At six scenes every function is distinct
            # and there is nothing for an outline to disambiguate, which is why both golden
            # fixtures are untouched by this: the condition is the defect, not the book.
            #
            # **Enqueued, never waited on.** It outranks scene work (300 against 0) so it is
            # claimed first when both are queued, and a scene drafted without a statement
            # simply omits the line — which is exactly the behaviour that shipped before this
            # existed. An outline that fails must leave a degraded book, not a stalled one.
            functions = [beat.function for beat in beats]
            plan_items = store.plan_items(progress.book_id, progress.branch_id)
            needs_outline = (
                outline
                and len(set(functions)) < len(functions)
                and any(
                    scene_plan_for(plan_items, beat.logical_id) is None for beat in beats
                )
            )
            if needs_outline:
                outline_id = outline_job_id(progress.book_id, progress.branch_id, epoch)
                if not store.has_job(outline_id):
                    outline_payload = {
                        "book_id": progress.book_id,
                        "branch_id": progress.branch_id,
                        "plan_epoch": epoch,
                    }
                    store.enqueue(
                        Job(
                            job_id=outline_id,
                            job_kind=BOOK_OUTLINE,
                            idempotency_key=outline_id,
                            payload=outline_payload,
                            input_digest=input_digest_for(outline_payload),
                            priority=OUTLINE_PRIORITY,
                        )
                    )
                    claimed = store.claim_next(holder, now=now, duration=duration)
                    if claimed is not None:
                        return claimed

            ids = [
                beat_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id,
                    template_for(head, template).template_id, epoch,
                )
                for beat in beats
            ]
            # A tournament or its selection is this book's one draft in flight too: K
            # candidates ride one frozen base inside the search job, and the selection
            # commits against that same base — a scene_draft planned beside either would
            # fork the branch exactly as two scene_drafts would. PARKED is deliberately
            # not "unfinished" here (§4.2: a parked unit never stalls the queue), which is
            # what lets the book draft elsewhere while a span awaits verdicts.
            ids += [
                plan_search_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id, epoch
                )
                for beat in beats
            ]
            ids += [
                span_select_job_id(
                    progress.book_id, progress.branch_id, beat.logical_id, epoch
                )
                for beat in beats
            ]
            # One draft in flight per book. Drain-first usually achieves this, but not when
            # the queued job is leased by another holder — and a second beat planned against
            # the same base is exactly how the branch forks.
            if store.any_unfinished(ids):
                continue

            # **Whose book this is, read once per book rather than once per beat.** It is a
            # position in the same sense `positions` is one: canon names one member of
            # the cast as this book's protagonist, and the packet and the beat line are told
            # which. Until this line existed `packet_for`'s `pov_character_id` seam had never
            # been passed anything by any production caller — every packet this system has ever
            # built was built for no one — while the outline invented whoever acted in the book
            # (`plan/reader-read-3.md` notes 1 and 3).
            #
            # `None` for every book whose canon declares no protagonist, and then the packet
            # filters nothing, the facts block keeps its old heading and the beat line renders
            # no fragment — byte-identical to what it was, which `input_digest_for` makes
            # load-bearing because that digest is also the sampler seed.
            # Read here rather than beside `positions`, which is pure: this is a query, and
            # a book whose work is already in flight has just `continue`d above without one.
            pov = worlds.protagonist_brief(
                store.state_records(progress.book_id, progress.branch_id)
            )
            pov_id = pov.subject if pov is not None else None

            for beat in beats:
                # 4. The selector's precondition IS the gate's — one function, no drift.
                if not is_draftable(head, beat.logical_id, policy=policy):
                    continue
                plan_item = scene_plan_for(
                    store.plan_items(progress.book_id, progress.branch_id),
                    beat.logical_id,
                )
                # Alternatives touch only unlocked SCENE_PLAN items: a director-locked
                # statement is direction, and searching over direction would put the
                # tournament's winner where the director's word was. That beat drafts
                # the ordinary way, statement intact.
                searching = plan_search and not (
                    plan_item is not None and plan_item.locked
                )
                job_id = (
                    plan_search_job_id(
                        progress.book_id, progress.branch_id, beat.logical_id, epoch
                    )
                    if searching
                    else beat_job_id(
                        progress.book_id, progress.branch_id, beat.logical_id,
                        template_for(head, template).template_id, epoch,
                    )
                )
                if store.has_job(job_id):
                    # Already planned under this epoch: in flight, or burned by a poison.
                    continue
                try:
                    packet = packet_for(
                        store, head, beat,
                        token_budget=token_budget,
                        pov_character_id=pov_id,
                    )
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
                # **The reader → writer loop is materialised HERE, at enqueue, and never at
                # render time (invariant I5).** The payload is the record of what was
                # actually asked and per-attempt replay fidelity depends on it: a handler
                # that rebuilt the prompt from live tables would make every replay a
                # different experiment, and the retry ladder — which deliberately re-reads
                # the same frozen prompt and varies only the sampler seed — would stop
                # varying only the seed. Empty is the common case and costs two indexed
                # queries; with no registration or no established direction, `resolve`
                # returns an empty set and the book drafts exactly as it did before.
                materialised = resolve(
                    store, book_id=progress.book_id, branch_id=progress.branch_id, head=head
                )
                system, prompt = render_prompt(
                    beat,
                    book_title=_book_title(head),
                    packet=packet,
                    feedback=materialised.feedback,
                    status_example=system_voice_example(
                        store.state_records(progress.book_id, progress.branch_id),
                        at=beat.story_order_key,
                    ),
                    target_words=(policy or DraftPolicy()).target_words,
                    # Under search the statement line is deliberately ABSENT: the handler
                    # appends one alternative per candidate draft, in the same last-line
                    # position (`scene_plan_line`, one function, two callers), so the K
                    # drafts differ exactly where the generator is most sensitive.
                    scene_plan=(
                        None
                        if searching
                        else (plan_item.text if plan_item is not None else None)
                    ),
                    progression=progression_target(
                        store.state_records(progress.book_id, progress.branch_id),
                        at=beat.story_order_key,
                    ),
                    criteria=worlds.criterion_brief(
                        store.state_records(progress.book_id, progress.branch_id)
                    ),
                    chapter=positions.get(beat.logical_id),
                    point_of_view=pov_id,
                )
                payload: dict[str, object] = {
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
                    # What shaped the prose, beside what grounded it. **Always present and
                    # `[]` when there was none** — invariant I4's negative case: "this scene
                    # had no feedback" and "nobody recorded whether this scene had feedback"
                    # are different facts, and an absent key cannot tell them apart. The
                    # digest of the empty list is a real digest, never null, which is what
                    # makes the two distinguishable after the fact.
                    **payload_fields(materialised.feedback),
                }
                if searching:
                    # The tournament reads the epoch at the top of the payload (the
                    # handler's stale pre-flight and the candidates' provenance both key
                    # on it), and outranks scene work for the same reason the outline
                    # does: it IS this span's drafting, one lane up.
                    payload["plan_epoch"] = epoch
                inserted = store.enqueue(
                    Job(
                        job_id=job_id,
                        job_kind=PLAN_SEARCH if searching else SCENE_DRAFT,
                        payload=payload,
                        input_digest=input_digest_for(payload),
                        priority=PLAN_SEARCH_PRIORITY if searching else 0,
                    )
                )
                if not inserted:
                    # A row exists that `has_job` did not see. Counting it as planned would
                    # be reporting a write that did nothing.
                    continue
                # **One-shot, and spent only after the job that carries it exists.** A
                # located difference materialised into a payload that failed to enqueue
                # would be spent on nothing, which is the one way this loop could silently
                # lose feedback. Spending after the insert makes the failure mode "the same
                # item is offered again", which is recoverable.
                for difference_id in materialised.spend:
                    store.spend_located_difference(difference_id)
                if materialised.feedback.dropped:
                    # The cap is reported, never silent: a bound coverage reads as "covered
                    # everything" when it did not (§89's rail, four modules deep).
                    store.bump_digest(
                        day, "feedback_dropped", materialised.feedback.dropped
                    )
                store.bump_digest(
                    day, "tournaments_enqueued" if searching else "beats_enqueued"
                )
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
