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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

import litharness_contracts as lc

from litharness.application import exemplars as exemplars_mod
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
from litharness.application.editorial import enqueue_ready_editorial_panel
from litharness.application.exemplars import Shelf
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
from litharness.application.ports import ApplicationStore, PlanningStore
from litharness.domain import genre, house, progression, staging, worlds
from litharness.domain import state as state_mod
from litharness.domain.beats import (
    SIX_BEAT,
    Beat,
    BeatTemplate,
    TemplateMismatch,
    beats_for,
    template_for,
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
    Movable,
    change_example,
    gain_example,
    graph_line_for,
    movable_names,
    notice_lines,
    offered_choice,
    offered_line,
    progression_target,
    readout_lines,
    standing_example,
    standing_target,
    stated_position,
    system_voice_example,
)
from litharness.domain.genre import genre_block
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plans import premise_of, scene_plan_for, scene_plan_line
from litharness.domain.revision import Revision
from litharness.domain.serials import (
    Position,
    SerialShape,
    arcs_of,
    beats_for_arc,
    beats_for_serial,
    chapter_positions,
)
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
        if directive.book_id in {None, book_id} and directive.branch_id in {None, branch_id}
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


def beat_job_id(book_id: str, branch_id: str, logical_id: str, template_id: str, epoch: int) -> str:
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


def gain_line_for(
    records: Sequence[lc.StateRecord],
    target: Movable | None,
    moved: progression.MovedLine | None,
    *,
    at: str | None,
) -> str | None:
    """The notice for this scene, or `None`: the beat names a grant the person did not
    hold and now holds (a gain, not a deepening or a rise), and the book's graph line
    has a phrase for `can_do` (§208)."""
    if target is None or moved is None:
        return None
    # A rise on a rung column the book declared `ordinal` moves from one name to another
    # (§234); a name is never a gain, and comparing it with zero would be a crash rather
    # than an abstention.
    if not isinstance(moved.was, int) or not isinstance(moved.now, int):
        return None
    if moved.was != 0 or moved.now < 1:
        return None
    return gain_example(records, at=at, ability_id=target.key)


def render_prompt(
    beat: Beat,
    *,
    book_title: str | None,
    packet: ContextPacket,
    status_example: str | None = None,
    status_moved: progression.MovedLine | None = None,
    target_words: int = 0,
    progression: str | None = None,
    scene_plan: str | None = None,
    writer: Writer | None = None,
    criteria: str | None = None,
    standing: str | None = None,
    standing_line: str | None = None,
    chapter: Position | None = None,
    point_of_view: str | None = None,
    offer_line: str | None = None,
    shelf: Shelf | None = None,
    gain_line: str | None = None,
    change_line: str | None = None,
    notices: tuple[str, ...] = (),
    readouts: tuple[str, ...] = (),
) -> tuple[str, str]:
    """(system, prompt) for one beat, grounded in an assembled context packet.

    `shelf` is the exemplar shelf (stage-0 §196): its openings block goes into the prompt
    *before* the packet, so the packet and the task still end the prompt, and the system gains
    the one sentence saying whose the block is and what may not be taken from it. `None` is
    every book drafted before the shelf existed, byte for byte.

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
    a measurement.** Shown the line's own template with its `{subject}` slot intact, one of three
    local models wrote the placeholder out verbatim. The line still matched the parser — a
    brace-wrapped word is a perfectly good subject — and still extracted nothing, because
    `{subject}` is no name canon knows: a scene that looks right, parses right, and
    establishes nothing. See `extraction.system_voice_example`.

    It is **omitted unless the book already speaks system voice**, since the example is built
    from canon and there is none to build from otherwise. A stat block in a locked-room
    mystery is not a smaller error than a missing one.

    **`status_moved` replaces that example with the line the scene leaves** (§186), on the
    scenes whose plan named a quantity as moving and only those. `None` — every unscheduled
    scene, every book with no sheet, every case `progression.moved_example` abstains on — keeps
    the entering line byte for byte, and the two are the arms of one measurement. It is a
    `MovedLine` rather than a string because the ask states in words what the column read
    entering the scene: a filled example is copied verbatim (§169), and a number a writer
    cannot tell has changed is one they may quietly change back.

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

    **`criteria` is the standard the scene is being judged against inside its own world**
    (`plan/state-model-abilities.md` §5 item 11: *show the generator the criterion it is writing
    against*). It goes in the system message for the boundary `writer` already observes: a
    criterion is a rule about how this world judges, which is closer to how to write the book
    than to what happened in it, and under the packet's "established and may be relied on"
    heading it would invite a scene to *state* the ladder rather than show somebody moving up
    it. `None` for every book that declares no criterion, which is every book written before
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
    after the statement. `plans.scene_plan_line` is rendered last always.

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
    # **The house rules reach the writer, and until 2026-08-23 nothing like them did.** Five
    # rule changes that afternoon made a forged premise clear and made its ladder a chain of
    # abilities; every one of them edited the Architect. The first book written on that world
    # opened on a call-centre shift rendered step by step, and the operator's reading was that
    # the clarity work had not been applied at all. It had not: this prompt was the three
    # sentences below and nothing else. `domain/house` carries the two rules once, with the
    # boundary `point_of_view` states — neither of them is a judgment about a story.
    system = house.with_house_rules(
        "You are drafting one scene of a novel. Write only the scene's prose: no headings, "
        "no commentary, no summary of what you wrote. The context below is established and "
        "may be relied on; do not contradict it."
    )
    if writer is not None:
        # **Ahead of the mechanics and never in the packet** (`plan/writer-roster.md` §3.2).
        # The packet's contract is "established and may be relied on; do not contradict it",
        # and a novelist's career is not a fact about the story — putting one under that
        # heading is how a writer's biography becomes canon in the book they are writing.
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
        #
        # **The line moved off the scene's end and onto the change, and that is §161's
        # furniture contract.** It used to read "End the scene with a status line in this
        # form", which is a footer: a scene could advance the sheet in its prose and report
        # the result after the reader had already left the moment. Read 8 §4.2 measured what
        # a progression that happens off the furniture becomes — §157's beats fired twice on
        # schedule in pilot 14 and both landed as guild promotions, narrated. A number that
        # moves where the reader cannot see the system say so has not moved for the reader.
        #
        # **"Exactly once" is load-bearing and it is not tidiness.** `extract_state`
        # runs `sheet.pattern.finditer` over the scene and mints one ACCEPTED_CANON record
        # per match, all at the same `order_key` — so a scene printing the line before and
        # after a change writes two canon snapshots that disagree at one position, which is
        # precisely the shape `integrity.detect_contradictions` groups on. Asking for the
        # line at the moment of change *and* at the scene's end would have manufactured the
        # contradictions the gate then refuses and the repair loop pays for. One line per
        # scene keeps the read-back single-valued, and the placement rule decides where the
        # one goes: at the change if there is one, at the end if there is not, so the
        # guaranteed emission the footer form bought is not given up to get the placement.
        # **The anchor moved from the number to the person, 2026-08-30 (§173).** Read 10, on
        # the draw the gate passed: a status line arriving at a number-move is *noise*, and if
        # the book has one it has to be part of the world the characters are interacting with.
        # Both halves of the old placement were correct against the defect §161 wrote them for
        # and both anchored on an **event in the machinery** — a line that appears because a
        # number moved is a line the narrator emits. So the first placement is now a person
        # reading it, and the two the contract already had are kept behind it: the cardinality
        # is untouched, the guaranteed emission is untouched, and what moved is which of the
        # three placements comes first. The rewrite adds no demand — `house.demands` reads one
        # sentence either way, which `tests/test_prompt_budget.py`'s `status_example` row is
        # what proves rather than an arithmetic performed here.
        #
        # **The example is the state the scene LEAVES where a beat named a move, 2026-08-30
        # (§186).** Pilot 18 draw 3 is the located case and it cost two paid attempts: the plan
        # read *Rating moves here*, this block handed over `Rating 2` and called it the state as
        # it stands, and both drafts printed `Rating 2`. §169 measured why — a model copies a
        # filled example character for character, which is the whole reason the example is
        # filled rather than a template — so the one concrete artifact in the prompt was proof
        # that the numbers had not moved, while the plan asked for a move; §184's gate now
        # refuses that contradiction instead of publishing it, and refusing it was costing two
        # attempts a scene.
        #
        # **One sentence swapped for one sentence, one line for one line.** The count cannot
        # move because nothing is added: the two sentences below are the same string on both
        # arms, and `tests/test_prompt_budget.py`'s `status_moved` row is the marginal zero.
        # A scene whose plan named no move renders the identical bytes it rendered before —
        # that is what `status_moved is None` means, and it is the control every measurement
        # in §186 is against.
        stands, example = (
            (
                f"which is the state this scene leaves once {status_moved.name} has moved "
                f"from the {status_moved.was} it stood at",
                status_moved.line,
            )
            if status_moved is not None
            else ("which is the state as it stands", status_example)
        )
        system += (
            f" The people in this book can read their own state, in this form, {stands}:\n"
            f"{example}\n"
            "Print that line exactly once, where somebody in the scene reads it; failing that, "
            "where one of its numbers changes, or at the scene's end. Write the character's "
            "name as your prose spells it, carry these values forward unchanged unless this "
            "scene changes them, and write the numbers the scene leaves true."
        )
        if offer_line:
            # **The fork as furniture, beside the sheet it belongs to** (2026-09-01, the
            # opening-parity track). §173 gave the system a fork and the plan an offer beat,
            # and the packet rendered the ways as flat triples — `warrant offers stock as one
            # way to take it` — so the one thing a reader of this genre wants to see, the menu
            # with what each way opens, reached the writer as notation. The book prints it as
            # it prints the sheet: one bracketed line, in the book's own words, exactly once.
            # Inside the `status_example` branch because a fork needs the sheet it is a fork in.
            system += (
                " Where this fork is put in front of the person, the book prints this line, "
                "exactly once, and they read it on the page:\n"
                f"{offer_line}"
            )
        if gain_line:
            # **The notice** (§208): where the beat names a grant gained and the book's
            # graph line has a phrase for it, the line is shown filled, as the standing
            # line is on a rise. Furniture the reader watches; the sheet is the record.
            system += (
                " Where they gain it, the book prints this line, exactly once, and they read "
                "it on the page:\n"
                f"{gain_line}"
            )
        if change_line:
            # **The change of kind** (§212): where a declared change lands on the person at
            # this position — a grant evolving, merging, or going — the line after it, shown
            # filled as the moved line is, and printed once. What the change is stands in the
            # packet as the world's own sentence; this is the furniture the reader watches.
            system += (
                " Where this happens to them, the book prints this line, exactly once, and "
                "they read it on the page:\n"
                f"{change_line}"
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
    if notices:
        # **The System's own voice** (§218): where a declared change with a line in the
        # world's register lands on the person at this scene, the book prints that line under
        # its own bracket, once. The fit census (§217) ranked this first, in four market
        # stories of five; the shape was declared already and nothing asked for it. Outside
        # the `status_example` branch because a book whose progression is a ladder with no
        # numbers still has a System that speaks, and the graph line is the declaration that
        # says so. `extraction.notice_lines` is the one reader of what lands here.
        system += (
            " Where the world says this to them, the book prints this line, exactly once, and "
            "they read it on the page:\n" + "\n".join(notices)
        )
    if readouts:
        # **The readout on request** (§220, §209's owed item): where the scene's plan names
        # another owner of a sheet — a creature, a rival, a follower, a place — the book
        # prints that owner's line, once, where the protagonist reads it. The trigger is the
        # plan's naming and nothing a model ranks; `extraction.readout_lines` is the one
        # reader of it, and the line is rendered through the owner's own sheet (§206).
        system += (
            " Where they read another's sheet, the book prints this line, exactly once, and it "
            "is read on the page:\n" + "\n".join(readouts)
        )
    if standing:
        # **The numeric block's wording, reused deliberately** (`plan/stage-0-decisions.md`
        # §113). A standing is a position on a declared ladder and a status snapshot is a set
        # of declared numbers; they are the same class of fact, and saying the second one's
        # sentence in a second register would be this module deciding one of them matters more.
        # "Toward" rather than "to", and "where the events warrant it", for exactly the reasons
        # the block above gives.
        #
        # It sits outside the `status_example` branch because the two are independent: a world
        # can declare a rank ladder and no stat sheet, which is true of the legacy generated
        # worlds, and nesting it would make the ladder unreachable for all of them.
        system += (
            "\nThe book's plan has the standing reaching this later on:\n"
            f"{standing}\n"
            "Move it toward that in this scene where the events warrant it; do not jump to it, "
            "and do not move it for no reason on the page."
        )
        if standing_line:
            # **A filled example, never a template with braces**, and that is a measurement
            # rather than a preference — `system_voice_example`'s. Shown the line's own template
            # with its `{subject}` slot intact, a model wrote the placeholder out verbatim; the line
            # matched the pattern, named a subject canon has never heard of, and extraction
            # yielded nothing. `extraction.standing_example` renders this one with the book's own
            # label, the book's own phrase for a change of standing and the rung the standing
            # currently names, so the model is shown a line `parse_graph_line` has already agreed
            # reads. A book that declares no graph line passes `None` and is asked to print
            # nothing — the declare -> ask -> print -> read chain simply does not start.
            system += (
                "\nWhen the standing changes, print the line in this form, as the book "
                f"prints it:\n{standing_line}"
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
        # the writer dossier already observes: a criterion is a rule about how this world
        # *judges*, which is closer to how to write the book than to what happened in it.
        # Putting it under "established and may be relied on" would invite the scene to
        # state the ladder rather than to show somebody moving up it.
        #
        # **Re-aimed 2026-08-29 as §161, and this is read 4's suppressor 2.** It read "a
        # scene that changes where someone stands must show the change rather than announce
        # it — a rank is something a reader sees, never something a narrator reports", and
        # read 4's analysis of *A Good Take* named it one of three standing instructions
        # actively suppressing the thing the operator keeps asking for: "a standing
        # prohibition on printing the ladder". It was written against told-not-shown (§5 item
        # 11) and it is defensible at that target; what it could not do is tell a narrator's
        # summary apart from the book's own printed furniture, and both arrive in this same
        # system message.
        #
        # **The repair narrows the prohibition's object rather than adding an exemption.** A
        # carve-out written as its own demand would be a permission, and §138 measured a
        # permission-only clause returning more than six times what a prohibition-only one
        # did, worse than silence. So the object shrinks from "a narrator reports a rank" to
        # "a narrator reports a rank whose change the reader was never shown" — which is the
        # failure §5 item 11 actually named — and the printed line falls outside it.
        #
        # **The furniture is then named anyway, and the reason it is affordable is where it
        # sits.** Four books running have failed the same way, so leaving the exemption
        # implicit was worth less than saying it; `house.demands` splits on sentence
        # terminators and a line break, so hanging it off a semicolon inside the same
        # sentence names the exemption at a cost of zero demands. It is also delimiting
        # rather than permitting — it says what the prohibition does not reach, and licenses
        # no token the `status_example` block above has not already asked for by name.
        #
        # **What went with it was an affirmative half that is carried twice over already.**
        # "Must show the change rather than announce it" is the `standing` block four lines
        # up ("do not move it for no reason on the page") and `standing_line` right after it
        # ("when the standing changes, print the line in this form"). §138's reading is that
        # the prohibition half is the half that gets obeyed; the affirmative half here was
        # redundant with two better-addressed demands.
        system += (
            "\nThis world judges people by the following, and what fails is a narrator "
            "reporting a rank whose change the reader was never shown; the line the book "
            "itself prints is not that:\n"
            f"{criteria}"
        )
    # **Transport authority now agrees with author authority.** Constraints used to sit in
    # the user prompt while house rules, a writer dossier and reader reactions sat in the
    # system message.  That made the provider hierarchy the inverse of the plan hierarchy:
    # a model resolving a conflict correctly would disobey the author-locked item.  Keep the
    # packet items and accounting intact, but put their locked block last in the system
    # message, after every lower-authority writing aid.
    locked = packet.render_constraints()
    if locked:
        system += f"\n\nAUTHOR-LOCKED STORY DECISIONS — these outrank all other guidance:\n{locked}"
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
    scene_position = f"scene {beat.ordinal} of {beat.of_total}"
    if chapter is not None:
        if chapter.open_ended:
            scene_position = (
                f"open-ended series; release volume {chapter.volume_index} "
                f"(packaging only); arc {chapter.arc_index}; chapter "
                f"{chapter.chapter_index} ({chapter.chapter_in_arc} of this arc); scene "
                f"{chapter.index_in_chapter} of {chapter.scenes_in_chapter} "
                f"(arc scene {beat.ordinal} of {beat.of_total})"
            )
        else:
            scene_position += (
                f". Chapter {chapter.chapter_index}, scene {chapter.index_in_chapter} of "
                f"{chapter.scenes_in_chapter}"
            )
    pov_line = "" if not point_of_view else f" Point of view: {point_of_view}."
    prompt = (
        f"{packet.render(include_constraints=False)}\n\n"
        f"Now write {title}{beat.title or beat.logical_id} — {scene_position}."
        f"{pov_line} Dramatic function: {beat.function}."
        f"{plan_line}"
    )
    if shelf is not None:
        system += f"\n{exemplars_mod.SHELF_SYSTEM}"
        prompt = f"{exemplars_mod.render_openings(shelf)}\n\n{prompt}"
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
        state_moment=state_mod.StateMoment.ENTERING,
        project_state_changes=True,
        summaries=summaries,
        # **Where the book stands, and it is a different question from the cutoff above.**
        # The cutoff decides which records *exist yet* and is gated by `stated_position`, so it
        # is `None` for any book whose story positions somebody else chose. This asks whether
        # the reader has been *told* a thing, so it is entitled to the beat's key
        # unconditionally where the cutoff abstains.
        #
        # ~~against positions the Architect minted from this book's own beat sheet~~ … ~~and a
        # legacy world's schedule keeps working on an imported book~~. **Both false** (§165.3,
        # fixed in §167): the beat's key is a scene key, an Architect's schedule is written in
        # digits, and a schedule did not "keep working" — it read as wholly disclosed from scene
        # one, on every book that had one. The key passed here is unchanged; what changed is that
        # `undisclosed_claims` no longer compares it against a coordinate from another space.
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
        promises=tuple(store.promises(revision.book_id, revision.branch_id, open_only=True)),
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
    #: An endless serial is never complete. This names the next structural action once every
    #: currently closed arc is drafted, without misreporting the serial as a finished book.
    continuation_reason: str | None = None
    open_ended: bool = False

    @property
    def complete(self) -> bool:
        return (
            not self.open_ended
            and self.blocked_reason is None
            and self.total > 0
            and self.drafted == self.total
        )


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
    serial_shape: SerialShape | None = None,
) -> BookProgress:
    """How far this book has got, and why it cannot move if it cannot.

    A blocked book reports its reason rather than looking finished. `NO_WORK` over a book
    with no premise and `NO_WORK` over a finished book are the same tick outcome, and
    telling them apart is the difference between a green board and a true one.
    """
    head = store.head(book_id, branch_id)
    if head is None:
        return BookProgress(book_id, branch_id, 0, 0, "no head revision")
    serial_mode = False
    if serial_shape is not None:
        grouped = arcs_of(head, serial_shape)
        serial_mode = bool(grouped and len(grouped[0].scene_ids) >= serial_shape.scenes_per_arc)
    try:
        beats = (
            beats_for_serial(head, serial_shape)
            if serial_mode and serial_shape is not None
            else beats_for(head, template_for(head, template))
        )
    except TemplateMismatch as mismatch:
        return BookProgress(book_id, branch_id, 0, 0, str(mismatch), open_ended=serial_mode)
    continuation = None
    if serial_mode and serial_shape is not None:
        arcs = arcs_of(head, serial_shape)
        if arcs and not arcs[-1].closed:
            missing = serial_shape.scenes_per_arc - len(arcs[-1].scene_ids)
            continuation = (
                f"arc {arcs[-1].index} needs {missing} more planned scene node(s) before "
                "its beat sheet can be fixed"
            )
        elif arcs:
            continuation = f"ready to plan arc {arcs[-1].index + 1}; the serial remains open"
    if premise_of(store.plan_items(book_id, branch_id)) is None:
        return BookProgress(
            book_id,
            branch_id,
            sum(1 for beat in beats if not is_draftable(head, beat.logical_id, policy=policy)),
            len(beats),
            "no single premise plan item; import a plan snapshot for this book",
            continuation,
            serial_mode,
        )
    drafted = sum(1 for beat in beats if not is_draftable(head, beat.logical_id, policy=policy))
    # **The house genre floor, reported as a reason and not as a finished book.** One door
    # along from the premise block and written under the same argument: a book with no
    # starting sheet is not idle, it is stopped, and `complete` must not read True over it.
    # It is checked *after* `drafted` is counted so the report still says how far the book
    # actually got — a blocked book that also claims zero drafted scenes hides its own state.
    genre_reason = (
        genre_block(store.state_records(book_id, branch_id))
        if (policy or DraftPolicy()).require_starting_sheet
        else None
    )
    return BookProgress(
        book_id,
        branch_id,
        drafted,
        len(beats),
        genre_reason,
        continuation,
        serial_mode,
    )


def make_plan_selector(
    *,
    template: BeatTemplate | None = None,
    policy: DraftPolicy | None = None,
    project_id: str = "",
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    outline: bool = True,
    director_id: str = "",
    scenes_per_chapter: int = 1,
    chapters_per_arc: int = 6,
    chapters_per_volume: int = 50,
    open_ended: bool = False,
    writer: Writer | None = None,
    shelf: Shelf | None = None,
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
    treats a scene without a statement as ordinary, so this changes nothing except what
    plan-side text reaches the prompt — the statements, and §155.3's scheduled beat with
    them. The beat costs no model call, but it rides the same plan line, and holding it
    back here is what keeps the bare pre-plan prompt reproducible through a flag rather
    than by editing code — the property this arm exists for. (§155.3's own control,
    an unscheduled scene left byte-identical, needs no flag at all.)

    `token_budget` bounds the *context* a beat is drafted against, and is separate from
    `BudgetPolicy`'s ceilings, which bound the spend. They fail differently and on purpose: a
    context budget drops the oldest scene from the packet, a spend ceiling refuses the call.

    **`scenes_per_chapter` is the operator's shape, and the only thing it does is tell the
    writer where the scene sits.** It is the number `--chapter-scenes` already hands the
    export path, threaded to the one other place in the system where a chapter means
    anything — so a book is grouped for a reader and drafted against the same grouping rather
    than against two that can disagree. One is the default and it asserts nothing: under it
    `serials.chapter_positions` yields no positions and every rendered prompt is byte-for-byte
    what it was before this parameter existed. Nothing here tells a scene what to *do* about
    being last in its chapter; that is the director's to say (stage-0 §95).

    **`writer` was a parameter `render_prompt` accepted and no production path ever passed**,
    which is `target_words`' defect in a second place and worse. `render_prompt` has carried a
    dossier since 2026-08-20 and this selector — the only caller in `src/` — had no way to
    supply one, so every scene this system has ever drafted was written by nobody. It became
    visible when the listing loop landed on 2026-08-25: a book whose listing and world are
    both a named cast writer's, and whose chapters are drafted by an anonymous prompt, is
    `domain/house.py`'s two-prompt-stack failure with the stacks swapped.

    `None` stays the default and stays the control, for `render_prompt`'s stated reason: a
    change to drafting behaviour that could only be produced by editing code is an arm nobody
    can reproduce, and §137 leaves the gate that would license a *comparison* between writers
    with no key. So this makes one writer reachable; it establishes nothing about which.
    """

    def select(store: ApplicationStore, holder: str, now: float, duration: float) -> Job | None:
        # 1. Make safe, explicit direction claimable first. A constraint received before
        #    this tick must affect the next scene, not the scene after it.
        _enqueue_verbatim_direction(store)
        _enqueue_interpretive_direction(store)

        # Reader answers are never prose context. A complete panel becomes eligible for
        # editorial interpretation only when its exact mechanism version is qualified.
        enqueue_ready_editorial_panel(store)

        # 1a. The Director speaks, if one is selected and this book's block is unspoken for.
        #     **After both human lanes and before the drain**, which is the whole ordering
        #     argument: a person's direction is materialised first and can never be buried by
        #     a machine's, and direction that exists before this tick shapes the next scene
        #     rather than the one after it (§4.1's reason for putting ingest first).
        if director_id:
            _enqueue_direction(store, director_id)

        # 2. Drain. Retries, revived units and hand-enqueued work retain their ordering,
        #    except for explicit direction; one draft at a time keeps lineage linear.
        claimed = store.claim_next(holder, now=now, duration=duration)
        if claimed is not None:
            return claimed

        stamp = datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")
        day = stamp[:10]

        # 3. Least-progressed book first: fairness derived from state, no cursor to drift.
        serial_shape = (
            SerialShape(
                scenes_per_chapter=scenes_per_chapter,
                chapters_per_arc=chapters_per_arc,
            )
            if open_ended
            else None
        )
        books = [
            plan_progress(
                store,
                book_id,
                branch_id,
                template=template,
                policy=policy,
                serial_shape=serial_shape,
            )
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
            book_serial_shape = serial_shape if progress.open_ended else None
            all_beats = (
                beats_for_serial(head, book_serial_shape)
                if book_serial_shape is not None
                else beats_for(head, template_for(head, template))
            )
            beats = all_beats
            arc_index = 0
            if book_serial_shape is not None:
                # Work one closed arc at a time. Its outline, progression schedule, promises,
                # and dramatic functions then share one bounded scope and never call the
                # latest planned arc the end of the series.
                beats = ()
                for arc in arcs_of(head, book_serial_shape):
                    if not arc.closed:
                        continue
                    arc_beats = beats_for_arc(head, arc)
                    if any(
                        is_draftable(head, beat.logical_id, policy=policy) for beat in arc_beats
                    ):
                        beats = arc_beats
                        arc_index = arc.index
                        break
                if not beats:
                    continue
            # Where each scene sits in its chapter, grouped once per book rather than once
            # per beat. Empty under the default shape, which asserts nothing, and empty is
            # what makes the ordinary prompt byte-identical to what it was.
            positions = (
                chapter_positions(
                    head,
                    book_serial_shape or SerialShape(scenes_per_chapter=scenes_per_chapter),
                    chapters_per_volume=chapters_per_volume,
                    open_ended=open_ended,
                )
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
            # simply omits the statement — the scheduled house beat still rides where the
            # cadence schedules one (the `scene_plan` fold below), so an outline that fails
            # leaves a degraded book, not a stalled one and not an off-schedule one.
            #
            # **§155.3's beat schedule is deliberately not keyed to this gate.** It was, by
            # accident of call site: the beat's only fold lived in `outline_proposal`, so a
            # book this gate correctly declined to outline — every six-scene book — was also
            # a book the cadence could never reach, and six is the standard pilot length
            # (pilot 14 §3 measured the dead spot live). The gate answers "can the sheet
            # tell its scenes apart"; the schedule answers "which scenes carry a beat"; the
            # fold below is what keeps the second question answered when this one says no.
            functions = [beat.function for beat in beats]
            plan_items = store.plan_items(progress.book_id, progress.branch_id)
            needs_outline = (
                outline
                and len(set(functions)) < len(functions)
                and any(scene_plan_for(plan_items, beat.logical_id) is None for beat in beats)
            )
            if needs_outline:
                outline_id = outline_job_id(
                    progress.book_id,
                    progress.branch_id,
                    epoch,
                    scope=f"arc-{arc_index}" if arc_index else "book",
                )
                if not store.has_job(outline_id):
                    outline_payload = {
                        "book_id": progress.book_id,
                        "branch_id": progress.branch_id,
                        "plan_epoch": epoch,
                        **(
                            {
                                "arc_index": arc_index,
                                "scenes_per_chapter": scenes_per_chapter,
                                "chapters_per_arc": chapters_per_arc,
                            }
                            if arc_index
                            else {}
                        ),
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
                    progress.book_id,
                    progress.branch_id,
                    beat.logical_id,
                    beat.template_id,
                    epoch,
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
            book_records = store.state_records(progress.book_id, progress.branch_id)

            # **The house genre floor, in front of the spend rather than behind it.** The
            # budget gate's argument, applied to a condition that is knowable even earlier: a
            # check that runs after the provider call records a book that should not have been
            # drafted, it does not prevent one. Refusing here means no packet is built, no job
            # is enqueued and no call is made for a book that cannot speak system voice.
            #
            # `continue` to the next book rather than `break` out of the loop, and never a
            # raise: one book missing its starting sheet is not a reason for the other books
            # on this tick to stop. `plan_progress` reports the same refusal with the same
            # reason, so `status` says why the board is not moving instead of showing a book
            # that looks finished.
            if (policy or DraftPolicy()).require_starting_sheet and genre_block(
                book_records
            ) is not None:
                continue

            pov = worlds.protagonist_brief(book_records)
            pov_id = pov.subject if pov is not None else None

            for beat in beats:
                # 4. The selector's precondition IS the gate's — one function, no drift.
                if not is_draftable(head, beat.logical_id, policy=policy):
                    continue
                plan_item = scene_plan_for(
                    store.plan_items(progress.book_id, progress.branch_id),
                    beat.logical_id,
                )
                job_id = beat_job_id(
                    progress.book_id,
                    progress.branch_id,
                    beat.logical_id,
                    beat.template_id,
                    epoch,
                )
                if store.has_job(job_id):
                    # Already planned under this epoch: in flight, or burned by a poison.
                    continue
                try:
                    packet = packet_for(
                        store,
                        head,
                        beat,
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
                    # the difference (the first-party endurance suite measures this limit).
                    store.bump_digest(
                        datetime.fromtimestamp(now, tz=UTC).date().isoformat(),
                        "context_omitted",
                        len(packet.omitted),
                    )
                # **One read, where there were four.** Every input below is a different
                # question put to the same rows, and this render used to ask the store for them
                # once per question — the habit `application/outline.py` names in its own canon
                # read as "the pattern this deliberately does not copy". Adding the standing and
                # its printed form would have made it six.
                # The floor above already read this book's records, and nothing on this path
                # writes state, so the per-beat re-read this replaces was the same rows
                # fetched again once per scene.
                records = book_records
                position = positions.get(beat.logical_id)
                status_line = system_voice_example(records, at=beat.story_order_key)
                # **The interaction beat, wrapped around whatever plan text this scene already
                # had** (§173). Read 10's central item is that the furniture arrives as a
                # narrator's overlay because nothing in the book ever opens it, and
                # `plan/house-genre-constraint.md` named the altitude that answers that without a
                # §138 formula: the plan, not a clause. It wraps **both** branches rather than
                # riding inside the `with_beat` one, because a fork is read out of canon at the
                # position being drafted — a stored outline statement was composed before the
                # book reached this rung, and folding a fork into it would state a schedule
                # (§110.3's measurement, one object along).
                #
                # `reads` is the same value the furniture ask is given, so the beat cannot ask
                # somebody to open an interface the writer was never handed; a second reader of
                # that question would be a second answer to it.
                #
                # **`None` in, `None` out.** A book with no plan text and no outline passes
                # `None` and keeps the §54 control arm's byte-identical prompt.
                # §175's staging bound composes here, inside the statement-less branch only —
                # a stored statement already carries it, folded by `outline_proposal` in the
                # same order — and §173's interaction wrap goes around whichever branch stood,
                # at the `scene_plan=` below. Bound first, wrap second: the bound says what
                # the scene may not also contain, the wrap says what somebody in it does.
                base_plan = (
                    plan_item.text
                    if plan_item is not None
                    else (
                        staging.with_bound(
                            genre.with_beat(
                                "",
                                beat.ordinal,
                                beat.of_total,
                                counts=movable_names(
                                    records, character=pov_id, at=beat.story_order_key
                                ),
                            ),
                            beat.ordinal,
                            arc_index=arc_index or None,
                        )
                        if outline
                        else None
                    )
                )
                # **What the beat asked for, recorded where it was asked** (§184). Both
                # branches above carry the beat — a stored statement had it folded in by
                # `outline_proposal`, a statement-less scene gets it derived here — so the
                # composed text is the one place they agree, and reading the ask out of it is
                # the only answer that does not re-derive one. `movables` supplies the column
                # the named quantity moves, off the same records the vocabulary came from and
                # at the position being drafted. Read from `base_plan` rather than from the
                # wrapped `scene_plan` below because §173's interaction beat only ever appends
                # after this one, so the answer is identical and the smaller read is the
                # honest one.
                beat_target = progression.named_target(
                    base_plan or "",
                    records,
                    character=pov_id,
                    at=beat.story_order_key,
                )
                # **And what that ask means for the one artifact the writer can copy** (§186).
                # Composed here rather than inside `render_prompt` because it is a reading of
                # this book's records at this position — the same read `status_line` above is,
                # one move on — and because the ask and the check must be answered from one
                # set of records: `beat_target` is what goes on the payload for the gate, and
                # it is the same object the example is built from. `None` on every scene where
                # `moved_example` abstains, which renders the prompt that was rendered before.
                beat_moved = progression.moved_example(
                    records, beat_target, character=pov_id, at=beat.story_order_key
                )
                beat_gain = gain_line_for(records, beat_target, beat_moved, at=beat.story_order_key)
                system, prompt = render_prompt(
                    beat,
                    book_title=_book_title(head),
                    packet=packet,
                    # A status snapshot is the value *entering* its keyed scene (the imported
                    # s1 snapshot is the seed), unlike an extracted assertion whose evidence
                    # establishes it during that scene.  Keep the exact snapshot here; the
                    # ordinary character/world records still use StateMoment.ENTERING.
                    status_example=status_line,
                    status_moved=beat_moved,
                    target_words=(policy or DraftPolicy()).target_words,
                    # A stored statement already carries the beat where the cadence schedules
                    # one — `outline_proposal` folded it in — so it is passed verbatim. A
                    # scene with **no** statement still gets the scheduled beat, derived here
                    # the way `beats_for` derives the sheet: a pure function of the position,
                    # stored nowhere. §155.3 schedules scene 1 always, "however short the
                    # book", but the fold in `outline_proposal` is reachable only through
                    # `needs_outline` — and at six scenes every dramatic function is distinct,
                    # so the standard pilot length was the one length the schedule could not
                    # reach (pilot 14 §3). `with_beat("")` is the bare beat on a scheduled
                    # ordinal and `""` (which renders nothing) everywhere else; gated on
                    # `outline` so the §54 control arm still reproduces the pre-plan prompt.
                    # **`counts` is the book's own word for what moves in it** (§161), and
                    # `movable_names` is the one place that question is answered — the
                    # recognition ratchet is the mode, so nothing here branches on what kind
                    # of book this is. Read at the position being drafted, so the quantity
                    # the plan names is one the writer can see on the line it was handed.
                    # `()` for every book that speaks no system voice, which composes the
                    # unnamed `BEAT` and is byte-identical to what this call site rendered
                    # before.
                    # **The opening's cast bound rides the same fold, and for the same
                    # reason.** §175: the packet's cast section is the one part with no scene
                    # scoping, so at a budget that does not bind every declared person reaches
                    # every scene — nine sheets in the chapter read 10 called crowded, and the
                    # writer used all nine. `staging` bounds how many of them reach one page
                    # without cutting the packet, because no honest order to cut it by exists.
                    # Folded around the beat rather than beside it: the statement and the beat
                    # say what the scene contains, the bound says what it may not also contain.
                    # A stored statement already carries both — `outline_proposal` folds them
                    # in the same order — so only the statement-less branch composes here.
                    # **The opening's two beats ride the same render-time fold as the
                    # interaction beat** (2026-09-01, the opening-parity track): who the
                    # person was before, then the first printed line inside that; and the
                    # first chapter ending on a thing read or offered and unanswered. Gated
                    # on the same `reads` so every book that prints no line composes the
                    # sentence it composed before, and keyed to the chapter shape where one
                    # exists so the hook lands on the first chapter's last scene whatever
                    # its length.
                    scene_plan=(
                        genre.with_opening(
                            genre.with_interaction(
                                base_plan,
                                beat.ordinal,
                                beat.of_total,
                                reads=status_line is not None,
                                offer=offered_choice(
                                    records, character=pov_id, at=beat.story_order_key
                                ),
                            ),
                            beat.ordinal,
                            reads=status_line is not None,
                            arc_index=arc_index or None,
                            chapter_scene=(
                                position.index_in_chapter if position is not None else None
                            ),
                            scenes_in_chapter=(
                                position.scenes_in_chapter if position is not None else None
                            ),
                        )
                        if base_plan is not None
                        else None
                    ),
                    progression=progression_target(records, at=beat.story_order_key),
                    criteria=worlds.criterion_brief(records),
                    # The ladder's two, and both are `None` for every book whose canon declares
                    # no standing — which is every book written before 2026-08-22, and the
                    # byte-identical control this whole slice is measured against. The printed
                    # form is asked for only where the book declared one and it names the
                    # standing predicate; `graph_line_for` is what refuses a malformed
                    # declaration, so a world whose label was a sentence prints nothing rather
                    # than a line no parser can read.
                    standing=standing_target(records, at=beat.story_order_key),
                    standing_line=(
                        standing_example(records, at=beat.story_order_key)
                        if graph_line_for(records) is not None
                        else None
                    ),
                    chapter=position,
                    point_of_view=pov_id,
                    writer=writer,
                    offer_line=offered_line(records, character=pov_id, at=beat.story_order_key),
                    gain_line=beat_gain,
                    change_line=change_example(records, character=pov_id, at=beat.story_order_key),
                    notices=notice_lines(records, character=pov_id, at=beat.story_order_key),
                    readouts=readout_lines(
                        records, plan=base_plan, at=beat.story_order_key, protagonist=pov_id
                    ),
                    shelf=shelf,
                )
                payload: dict[str, object] = {
                    "revision_id": head.revision_id,
                    "book_id": progress.book_id,
                    "branch_id": progress.branch_id,
                    "logical_id": beat.logical_id,
                    "prompt": prompt,
                    "system": system,
                    # **Which exemplars this scene was shown, by identity and never by
                    # text** (§196). Absent without a shelf, so a payload drafted before the
                    # shelf existed is the payload it was.
                    **({"exemplars": shelf.record()} if shelf is not None else {}),
                    # **The packet on its own, for the reviser** (§185). The assembled
                    # `prompt` above already contains it, and this is deliberately a second
                    # copy rather than an offset into the first: the reviser must be shown
                    # the facts the scene may not contradict *without* the closing "Now
                    # write ..." that follows them, and a stored length to slice at is a
                    # derived answer that goes stale the first time the tail changes —
                    # §184's own rule about reading an ask instead of recomputing one. A job
                    # enqueued before this key existed revises on the scene alone.
                    "packet": packet.render(include_constraints=False),
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
                        "open_ended_serial": book_serial_shape is not None,
                        "arc_index": arc_index or None,
                        "plan_epoch": epoch,
                        "predicate": "draftable.v0",
                        # Where the template says this beat sits in story time, or None when
                        # it is not entitled to say. Travels on the payload rather than being
                        # recomputed in the handler, so the position a scene was extracted
                        # under is the one the plan held when the work was selected — a later
                        # template edit cannot retroactively move a scene already written.
                        "story_order_key": beat.story_order_key,
                        # The scheduled beat's ask, for the gate that checks it landed
                        # (§184). Two keys rather than one because the name is the book's
                        # word and the column is the number it moves, and the gate needs
                        # both without re-deriving either. Absent — rather than null — on
                        # every scene whose plan named no quantity, which is every
                        # unscheduled scene, every book with no sheet, and every job
                        # enqueued before this existed; the gate reads an absence as
                        # nothing to check.
                        **(
                            {
                                "progression_beat": beat_target.name,
                                "progression_column": beat_target.key,
                            }
                            if beat_target is not None
                            else {}
                        ),
                        **(
                            {
                                "chapter_index": position.chapter_index,
                                "chapter_scene_index": position.index_in_chapter,
                                "chapter_scenes": position.scenes_in_chapter,
                                "chapter_end": (
                                    position.index_in_chapter == position.scenes_in_chapter
                                ),
                                "volume_index": position.volume_index,
                                "chapter_in_volume": position.chapter_in_volume,
                            }
                            if position is not None
                            else {}
                        ),
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
                            name: len(items) for name, items in packet.sections.items() if items
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
                        priority=0,
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
