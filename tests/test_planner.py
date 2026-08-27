"""Stage 1 slice 7: the six-scene book drafts itself.

§17's Stage 1 exit is "the mystery and litrpg fixture books regenerate from premise to
accepted six-scene draft autonomously; zero silent mutation; every acceptance carries a
recorded policy decision".

The tests that matter most here are the ones that catch a loop *appearing* to work.
`test_the_head_lineage_is_linear` is the important one: enqueueing all six beats against a
single base produces six sibling revisions, each holding one drafted scene, each
overwriting the head — a book with one scene of prose, six accepted decisions, six
acceptance events, and no error anywhere. A per-scene assertion passes that; only the
lineage catches it.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import readers as readers_mod
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.outline import BOOK_OUTLINE
from litharness.application.planner import (
    beat_job_id,
    direction_for,
    make_plan_selector,
    packet_for,
    plan_progress,
    render_prompt,
    template_for,
)
from litharness.domain import integrity, worlds
from litharness.domain.beats import (
    SIX_BEAT,
    BeatTemplate,
    TemplateMismatch,
    arc_template,
    beats_for,
)
from litharness.domain.context import FACTS, assemble
from litharness.domain.draft import DraftPolicy, is_draftable
from litharness.domain.extraction import (
    extract_state,
    progression_target,
    render_status_line,
    speaks_system_voice,
    standing_example,
    standing_target,
    system_voice_example,
)
from litharness.domain.jobs import JobStatus
from litharness.domain.nodes import LockKind, Node, NodeKind
from litharness.domain.patch import Veto
from litharness.domain.plans import import_plan
from litharness.domain.policy import GateKind, Outcome
from litharness.domain.revision import (
    Revision,
    build_revision,
    import_manuscript,
    new_book,
)
from litharness.domain.serials import SerialShape, chapter_positions
from litharness.domain.state import import_state
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0
TICK = 300.0

#: Enough padding to clear `DraftPolicy.min_chars` without touching the gate.
PAD = 400


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "planner.db")


def _fixture(store: SqliteStore, name: str) -> tuple[str, str]:
    """Import a golden book and its plan, exactly as `cli import` does."""
    import litharness_contracts as lc

    from litharness.adapters.contracts_fixtures import (
        fixture_manuscript,
        fixture_plans,
        fixture_state,
    )

    manuscript = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript(name).read_text(encoding="utf-8")),
    )
    imported = import_manuscript(manuscript)
    revision = imported.revision
    store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")

    snapshot = lc.parse_artifact(
        lc.PlanSnapshot, json.loads(fixture_plans(name).read_text(encoding="utf-8"))
    )
    plan = import_plan(snapshot, book_id=revision.book_id, branch_id=revision.branch_id)
    store.record_plan_items(
        revision.book_id,
        revision.branch_id,
        plan.items,
        created_at="2026-08-13T00:00:00Z",
        source_revision_id=plan.source_revision_id,
    )

    state_snapshot = lc.parse_artifact(
        lc.StateSnapshot, json.loads(fixture_state(name).read_text(encoding="utf-8"))
    )
    state = import_state(state_snapshot, book_id=revision.book_id, branch_id=revision.branch_id)
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        state.records,
        created_at="2026-08-13T00:00:00Z",
        source_revision_id=state.source_revision_id,
    )
    return revision.book_id, revision.branch_id


def test_reader_direction_uses_each_reader_s_newest_read(store: SqliteStore) -> None:
    reader_id = readers_mod.pool(readers_mod.STEERING)[0].reader_id
    store.record_reader_read(
        BOOK_ID,
        BRANCH_ID,
        "rev-old",
        "scene-1",
        reader_id=reader_id,
        pool="steering",
        created_at="2026-08-20T00:00:00Z",
        hoping_for=["the old hope"],
        dreading=["the old dread"],
    )
    store.record_reader_read(
        BOOK_ID,
        BRANCH_ID,
        "rev-new",
        "scene-2",
        reader_id=reader_id,
        pool="steering",
        created_at="2026-08-21T00:00:00Z",
        hoping_for=["the new hope"],
        dreading=["the new dread"],
    )

    direction = direction_for(store, BOOK_ID, BRANCH_ID)

    assert "the new hope" in direction and "the new dread" in direction
    assert "the old hope" not in direction and "the old dread" not in direction


def test_an_open_ended_serial_never_reports_the_current_arc_as_the_ending(
    store: SqliteStore,
) -> None:
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    filled = head.replacing(
        node.with_content("Drafted scene. " * 30)
        for node in head.nodes
        if node.kind is NodeKind.SCENE
    )
    store.commit_revision(filled, created_at="2026-08-21T00:00:00Z")
    progress = plan_progress(
        store,
        book_id,
        branch_id,
        serial_shape=SerialShape(scenes_per_chapter=1, chapters_per_arc=6),
    )
    assert progress.drafted == progress.total == 6
    assert progress.open_ended and not progress.complete
    assert "remains open" in (progress.continuation_reason or "")


def test_the_production_selector_scopes_outline_work_to_one_serial_arc(
    store: SqliteStore,
) -> None:
    revision = new_book(
        BOOK_ID,
        BRANCH_ID,
        title="Endless Road",
        scenes=24,
        position_capacity=100_000,
    )
    store.commit_revision(revision, created_at="2026-08-21T00:00:00Z")
    store.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.PlanItem(
                logical_id="plan-premise",
                kind=lc.PlanKind.PREMISE,
                text="Every gate takes something different.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            )
        ],
        created_at="2026-08-21T00:00:00Z",
    )

    job = make_plan_selector(
        project_id=PROJECT_ID,
        scenes_per_chapter=4,
        chapters_per_arc=6,
        open_ended=True,
    )(store, "worker-a", START, 300.0)

    assert job is not None and job.job_kind == BOOK_OUTLINE
    assert job.payload["arc_index"] == 1
    assert job.payload["scenes_per_chapter"] == 4
    assert job.payload["chapters_per_arc"] == 6


def _conductor(store: SqliteStore, *, pad: int = PAD, **kwargs) -> Conductor:
    registry = ProviderRegistry(FakeProvider(pad_to_chars=pad))
    return Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        select=make_plan_selector(**kwargs),
        handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
    )


def _run(store: SqliteStore, ticks: int, **kwargs) -> list[TickOutcome]:
    loop = _conductor(store, **kwargs)
    return [loop.tick(START + index * TICK).outcome for index in range(ticks)]


# --- §17 Stage 1 exit ----------------------------------------------------------------


@pytest.mark.parametrize("fixture", ["mystery", "litrpg"])
def test_a_fixture_book_reaches_six_accepted_scenes_with_no_human_in_the_loop(
    store: SqliteStore, fixture: str
) -> None:
    book_id, branch_id = _fixture(store, fixture)

    outcomes = _run(store, 8)

    assert outcomes.count(TickOutcome.RAN_JOB) == 6
    assert outcomes[-1] is TickOutcome.NO_WORK
    progress = plan_progress(store, book_id, branch_id)
    assert progress.drafted == 6 and progress.complete


@pytest.mark.parametrize("fixture", ["mystery", "litrpg"])
def test_the_head_lineage_is_linear_and_carries_every_scene(
    store: SqliteStore, fixture: str
) -> None:
    """**The six-way-fork detector.**

    Planning all beats against one base produces six siblings, each with one scene, each
    overwriting `branch_heads`. Every per-scene assertion still passes; the final head
    holds one scene of prose. Only the lineage length distinguishes the two.
    """
    book_id, branch_id = _fixture(store, fixture)
    _run(store, 8)

    head = store.head(book_id, branch_id)
    assert head is not None
    assert len(store.lineage(head.revision_id)) == 7, "the branch forked instead of advancing"
    scenes = [node for node in head.in_reading_order() if node.kind is NodeKind.SCENE]
    assert len(scenes) == 6
    assert all(node.content for node in scenes), "the final head is missing prose"


def test_every_acceptance_carries_a_recorded_policy_decision(store: SqliteStore) -> None:
    """§19's integrity clause, over an autonomous run rather than a hand-driven one."""
    book_id, branch_id = _fixture(store, "mystery")
    _run(store, 8)

    head = store.head(book_id, branch_id)
    assert head is not None
    for revision_id in store.lineage(head.revision_id)[:-1]:  # the import has its own
        assert store.decision_for_revision(revision_id) is not None


def test_an_autonomous_run_leaves_the_store_verifiable(store: SqliteStore) -> None:
    """Zero silent mutation: every revision rebuilds from canonical records."""
    _fixture(store, "mystery")
    _run(store, 8)
    assert store.verify_integrity() == 7


def test_two_books_both_finish_and_neither_starves(store: SqliteStore) -> None:
    """Least-progressed-first, derived from state rather than a persisted cursor."""
    mystery = _fixture(store, "mystery")
    litrpg = _fixture(store, "litrpg")

    _run(store, 14)

    for book_id, branch_id in (mystery, litrpg):
        assert plan_progress(store, book_id, branch_id).complete


def test_the_run_does_not_lower_the_shape_gate(store: SqliteStore) -> None:
    """A gate relaxed to make the end-to-end test pass is not a gate."""
    assert DraftPolicy().min_chars == 200
    _fixture(store, "mystery")
    _run(store, 8)


# --- silent failure ------------------------------------------------------------------


def test_a_book_that_makes_no_progress_is_loud_not_quiet(store: SqliteStore) -> None:
    """The green-board test. With the fake's answer below the length floor, every beat
    poisons — and the failure must be visible in all three places an operator looks."""
    book_id, branch_id = _fixture(store, "mystery")
    loop = _conductor(store, pad=0)
    for index in range(30):
        loop.tick(START + index * TICK)

    assert plan_progress(store, book_id, branch_id).drafted == 0
    assert store.job_counts_by_status().get("poisoned", 0) == 6
    assert len(store.open_exceptions()) == 6, (
        "attempt exhaustion must file an exception; a poisoned queue and an empty "
        "exception list is a green board over a book with no prose"
    )


def test_a_premise_less_book_is_blocked_and_says_so(store: SqliteStore) -> None:
    """Not silently skipped. A planner that substituted a placeholder would draft a book
    against a premise nobody wrote, and no gate here can detect that."""
    import litharness_contracts as lc

    from litharness.adapters.contracts_fixtures import fixture_manuscript

    manuscript = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript("mystery").read_text(encoding="utf-8")),
    )
    revision = import_manuscript(manuscript).revision
    store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")

    outcomes = _run(store, 3)

    assert outcomes == [TickOutcome.NO_WORK] * 3
    progress = plan_progress(store, revision.book_id, revision.branch_id)
    assert progress.blocked_reason is not None
    assert "premise" in progress.blocked_reason
    assert not progress.complete, "a blocked book must not read as finished"


def test_a_finished_book_and_a_blocked_book_are_distinguishable(store: SqliteStore) -> None:
    """Both report NO_WORK. Telling them apart is the difference between a green board and
    a true one."""
    book_id, branch_id = _fixture(store, "mystery")
    _run(store, 8)
    finished = plan_progress(store, book_id, branch_id)
    assert finished.complete and finished.blocked_reason is None


# --- selection correctness -----------------------------------------------------------


def test_the_planner_never_offers_a_beat_the_gate_would_refuse(store: SqliteStore) -> None:
    """The precondition and the gate are one function, so this cannot drift. A selector
    that offered a refused node would escalate on attempt one and file an exception —
    filling the queue §4.3 reserves for the director."""
    from litharness.domain.draft import draft_block, gate_draft

    revision = build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node(
                logical_id="empty",
                kind=NodeKind.SCENE,
                position_key="010",
                parent_logical_id="book",
            ),
            Node.text_node(
                "full", NodeKind.SCENE, "020", "Already written.", parent_logical_id="book"
            ),
            Node(
                logical_id="locked",
                kind=NodeKind.SCENE,
                position_key="030",
                parent_logical_id="book",
                lock=LockKind.PUBLISHED,
            ),
        ],
    )
    for logical_id in ("empty", "full", "locked", "missing"):
        blocked = draft_block(revision, logical_id)
        refused = gate_draft(revision, logical_id, "x" * 400)
        assert (blocked is None) == is_draftable(revision, logical_id)
        # Draftable iff the gate does not refuse it structurally.
        assert (blocked is None) == (refused.accepted or refused.veto_kinds == ())


def test_a_beat_already_planned_is_not_planned_again(store: SqliteStore) -> None:
    """Derived job ids plus `has_job`. Two selections before the first completes must not
    produce two jobs for one beat — the fastest way to fork the branch."""
    _fixture(store, "mystery")
    select = make_plan_selector()

    first = select(store, "worker-a", START, 600.0)
    assert first is not None
    # Claimed and leased, so it is not re-offered; and its beat must not be re-enqueued.
    second = select(store, "worker-b", START + 1.0, 600.0)

    assert second is None or second.job_id != first.job_id
    assert sum(store.job_counts_by_status().values()) == 1


def test_ticking_a_finished_book_enqueues_nothing(store: SqliteStore) -> None:
    _fixture(store, "mystery")
    _run(store, 8)
    before = sum(store.job_counts_by_status().values())
    _run(store, 4)
    assert sum(store.job_counts_by_status().values()) == before == 6


def test_a_poisoned_beat_does_not_stall_its_successors(store: SqliteStore) -> None:
    """§4.1: a blocked item never stalls the queue — the Conductor works elsewhere."""
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    # Lock scene-3 so it can never be drafted.
    locked = head.node("scene-3")
    frozen = Revision(
        book_id=head.book_id,
        branch_id=head.branch_id,
        nodes=tuple(
            node
            if node.logical_id != "scene-3"
            else Node(
                logical_id=node.logical_id,
                kind=node.kind,
                position_key=node.position_key,
                parent_logical_id=node.parent_logical_id,
                title=locked.title,
                lock=LockKind.PUBLISHED,
            )
            for node in head.nodes
        ),
        parent_revision_id=head.revision_id,
    )
    store.commit_revision(frozen, created_at="2026-08-13T00:01:00Z")

    _run(store, 10)

    final = store.head(book_id, branch_id)
    assert final is not None
    drafted = [
        node.logical_id
        for node in final.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content
    ]
    assert "scene-3" not in drafted
    assert len(drafted) == 5, "a locked beat stopped the book instead of being skipped"


def test_editing_the_prompt_template_does_not_mint_a_second_job() -> None:
    """The job id excludes the prompt on purpose: a template edit must not re-enqueue work
    already accepted."""
    first = beat_job_id("b", "br", "scene-1", SIX_BEAT.template_id, 0)
    second = beat_job_id("b", "br", "scene-1", SIX_BEAT.template_id, 0)
    assert first == second
    assert beat_job_id("b", "br", "scene-1", SIX_BEAT.template_id, 1) != first


def test_every_planned_payload_is_total(store: SqliteStore) -> None:
    """A missing key raises `HandlerInputError`, which is a job failure with no policy
    decision recorded — so payload construction must never depend on `.get`."""
    _fixture(store, "mystery")
    _conductor(store).tick(START)
    [job] = store.jobs_by_status(JobStatus.RUNNING) or store.jobs_by_status(JobStatus.SUCCEEDED)
    for key in ("revision_id", "logical_id", "prompt", "system", "book_id", "branch_id"):
        assert key in job.payload
    assert job.payload["selected_by"]["predicate"] == "draftable.v0"


# --- beats ---------------------------------------------------------------------------


def test_a_scene_count_mismatch_refuses_rather_than_interpolating() -> None:
    revision = build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node(
                logical_id="scene-1",
                kind=NodeKind.SCENE,
                position_key="010",
                parent_logical_id="book",
            ),
        ],
    )
    with pytest.raises(TemplateMismatch, match="does not fit"):
        beats_for(revision, SIX_BEAT)


def test_beats_follow_position_order_not_insertion_order(store: SqliteStore) -> None:
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beats = beats_for(head, SIX_BEAT)
    assert [beat.logical_id for beat in beats] == [f"scene-{n}" for n in range(1, 7)]
    assert [beat.function for beat in beats] == list(SIX_BEAT.functions)
    assert beats[0].ordinal == 1 and beats[-1].of_total == 6


def test_the_prompt_names_the_beat_and_the_premise() -> None:
    template = BeatTemplate("t.v0", ("setup",))
    revision = build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="A Book"),
            Node(
                logical_id="s1",
                kind=NodeKind.SCENE,
                position_key="010",
                parent_logical_id="book",
                title="The Study",
            ),
        ],
    )
    [beat] = beats_for(revision, template)
    packet = assemble(
        revision,
        "s1",
        plan_items=[
            lc.PlanItem(
                logical_id="plan-premise",
                kind=lc.PlanKind.PREMISE,
                text="A locked room.",
                authority=lc.PlanAuthority.INTENDED,
            )
        ],
    )
    system, prompt = render_prompt(beat, book_title="A Book", packet=packet)
    assert "scene" in system.lower()
    assert "The Study" in prompt and "1 of 1" in prompt
    assert "setup" in prompt and "A locked room." in prompt


def test_the_prompt_carries_the_context_packet_and_ends_with_the_instruction(
    store: SqliteStore,
) -> None:
    """§12 step 2 reaching the prompt, and the ordering that makes it useful.

    The packet goes first and the instruction last, because the last thing in a prompt is
    the thing a model acts on — leading with "write this scene" and then supplying the book
    invites a scene written from the header.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[-1]
    packet = packet_for(store, head, beat)
    system, prompt = render_prompt(beat, book_title="The Vane House", packet=packet)

    # The two locked plan items that bear on scene 6, which the pre-packet prompt omitted.
    assert "rain-on-glass motif repeats deliberately in scenes 1, 3, and 6" in system
    assert "sealed letter must be read aloud at the will reading" in system
    assert "AUTHOR-LOCKED STORY DECISIONS" in system
    assert "rain-on-glass motif repeats deliberately in scenes 1, 3, and 6" not in prompt
    # The open thread the resolution owes a payoff.
    assert "sealed_letter_reading" in prompt
    assert prompt.rstrip().endswith("Dramatic function: resolution.")


def test_reader_reactions_are_context_and_cannot_outrank_author_locks(
    store: SqliteStore,
) -> None:
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[-1]
    packet = packet_for(store, head, beat)
    reaction = "Readers hope the sealed letter stays closed."

    system, prompt = render_prompt(
        beat,
        book_title="The Vane House",
        packet=packet,
        direction=reaction,
    )

    assert reaction not in system
    assert reaction in prompt and prompt.index(reaction) < prompt.index("Now write")
    assert "sealed letter must be read aloud at the will reading" in system
    assert system.rstrip().endswith(packet.render_constraints())


def test_the_target_length_reaches_the_prompt_at_all(store: SqliteStore) -> None:
    """The defect this file could not see, because the only test of it was `@live`.

    `render_prompt` accepted `target_words` and never read it: the parameter and its call
    site landed in `8f7075c` and the body was untouched, so asking for 900 words and asking
    for nothing produced **byte-identical** prompts. Every number that commit records is
    therefore two draws from the same request, and the live test that carried them routed
    both of its arms through the same ignoring function, so its assertion could not fail on
    any model at all.

    The property is checkable with no model at all, which is the whole lesson: a live test
    was written for a question that never needed one, and the cheap test that would have
    caught it was never written. Both directions are asserted, because a function that
    ignores the parameter passes the first half and a function that always emits the block
    passes the second.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[0]
    packet = packet_for(store, head, beat)

    asked, _ = render_prompt(beat, book_title=None, packet=packet, target_words=900)
    silent, _ = render_prompt(beat, book_title=None, packet=packet, target_words=0)

    assert "900" in asked
    assert asked != silent
    assert "900" not in silent
    # A target of zero is "do not ask", not "ask for zero words".
    assert "0 words" not in silent


def test_asking_for_a_length_does_not_disturb_the_instruction_the_model_acts_on(
    store: SqliteStore,
) -> None:
    """The target goes in `system`; the prompt still ends with the beat.

    `test_the_prompt_carries_the_context_packet_and_ends_with_the_instruction` records why
    the last line matters — the last thing in a prompt is the thing a model acts on. A
    length instruction appended there would displace it, so this pins that the two changes
    cannot collide.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[-1]
    packet = packet_for(store, head, beat)
    _, prompt = render_prompt(beat, book_title=None, packet=packet, target_words=900)
    assert prompt.rstrip().endswith("Dramatic function: resolution.")


def test_the_prompt_asks_for_system_voice_only_where_the_book_speaks_it(
    store: SqliteStore,
) -> None:
    """§12 step 5 could read the `[STATUS]` line and nothing ever asked for one, so every
    record in the system came from an imported snapshot: the contradiction detector could
    only fire on prose somebody else wrote, and the propagation producer had no fact of the
    system's own to compare.

    The instruction carries the book's own current status line, and is omitted for a book
    whose canon holds no status snapshot — a stat block in a locked-room mystery is not a
    smaller error than a missing one.
    """
    litrpg_ids = _fixture(store, "litrpg")
    mystery_ids = _fixture(store, "mystery")

    prompts = {}
    for name, (book_id, branch_id) in (("litrpg", litrpg_ids), ("mystery", mystery_ids)):
        head = store.head(book_id, branch_id)
        assert head is not None
        beat = beats_for(head, SIX_BEAT)[0]
        prompts[name] = render_prompt(
            beat,
            book_title=None,
            packet=packet_for(store, head, beat),
            status_example=system_voice_example(
                store.state_records(book_id, branch_id), at=beat.story_order_key
            ),
        )[0]

    assert "[STATUS] rook — Level 3 | HP 24/30 | MP 8/10 | Gold 45" in prompts["litrpg"]
    assert "{subject}" not in prompts["litrpg"], "a placeholder is a thing a model copies"
    assert "[STATUS]" not in prompts["mystery"]
    assert not speaks_system_voice(store.state_records(*mystery_ids))


def test_the_planner_puts_the_system_voice_instruction_on_the_queued_job(
    store: SqliteStore,
) -> None:
    """End to end through the selector, because `render_prompt` taking the flag is worth
    nothing if the one caller in production never passes it — which is the defect shape this
    project keeps finding."""
    _fixture(store, "litrpg")
    make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 300.0)

    [job] = [
        unit for unit in store.jobs_by_status(JobStatus.QUEUED) if unit.job_kind == SCENE_DRAFT
    ]
    assert "[STATUS] rook — Level 3" in str(job.payload["system"])


# --- where the scene sits in its chapter -----------------------------------------------


def test_the_prompt_is_byte_identical_when_a_chapter_is_one_scene(
    store: SqliteStore,
) -> None:
    """The control, and the reason it is a byte comparison rather than a substring one.

    `--chapter-scenes 1` is the default and it asserts nothing: production books hold no
    chapter nodes and no assembly scheme is decided. A cue rendered under it would put a
    scheme nobody chose into every prompt this system has ever produced — and, because
    `input_digest_for` covers the prompt and that digest is the sampler seed, it would also
    silently move the decoding of every newly minted job. So the falsy case must produce
    exactly the bytes that omitting the parameter produces.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]
    packet = packet_for(store, head, beat)

    absent = render_prompt(beat, book_title="The Vane House", packet=packet)
    one_scene = render_prompt(
        beat,
        book_title="The Vane House",
        packet=packet,
        chapter=chapter_positions(head, SerialShape(scenes_per_chapter=1)).get(beat.logical_id),
    )

    assert one_scene == absent


def test_the_prompt_says_which_chapter_the_scene_is_in_and_where(store: SqliteStore) -> None:
    """Position, in the beat line, in the form the operator's shape implies.

    Scene 4 of the six-scene fixture at four scenes a chapter is the last scene of chapter 1;
    scene 5 opens chapter 2, whose complement is the two scenes that exist rather than the
    four the shape would eventually hold.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    positions = chapter_positions(head, SerialShape(scenes_per_chapter=4))
    beats = beats_for(head, SIX_BEAT)

    rendered = {
        beat.logical_id: render_prompt(
            beat,
            book_title=None,
            packet=packet_for(store, head, beat),
            chapter=positions.get(beat.logical_id),
        )[1]
        for beat in beats
    }

    assert "scene 4 of 6. Chapter 1, scene 4 of 4. Dramatic function:" in rendered["scene-4"]
    assert "scene 5 of 6. Chapter 2, scene 1 of 2. Dramatic function:" in rendered["scene-5"]
    assert "scene 1 of 6. Chapter 1, scene 1 of 4. Dramatic function:" in rendered["scene-1"]


def test_the_chapter_cue_carries_no_verb_and_no_adjective(store: SqliteStore) -> None:
    """**The boundary, asserted rather than trusted.**

    The system may tell a writer where a scene sits; it may not tell it how to end a chapter.
    That is the director's to say, and a default in this line would be this system's own taste
    arriving in every prompt it renders. The words below are the ones a hook instruction would
    have to use, and the cue is checked for all of them.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]
    packet = packet_for(store, head, beat)
    position = chapter_positions(head, SerialShape(scenes_per_chapter=4))[beat.logical_id]

    _, prompt = render_prompt(beat, book_title=None, packet=packet, chapter=position)

    cue = prompt.rsplit("scene 4 of 6.", 1)[1].split("Dramatic function:")[0]
    assert cue == " Chapter 1, scene 4 of 4. "
    for forbidden in ("hook", "cliff", "closing", "final", "last", "end", "stakes", "question"):
        assert forbidden not in cue.lower()


# --- whose scene this is ---------------------------------------------------------------
#
# `plan/reader-read-3.md` note 3: *"Its too confusing who the main character is."* The first
# two words of the book are a different person's name; the protagonist enters at word 17 with
# no role and no want, and his trade is first stated at word 804 inside a line he reads aloud.
# C5 — "the first sentence of a scene puts a person in a situation" — was in the packet and was
# obeyed. *Which* person was unsaid, because nothing in the pipeline had a protagonist to name.
#
# `packet_for` has taken a `pov_character_id` since it was written and no production caller ever
# passed one: every packet this system has ever built was built for no one.


def test_the_prompt_is_byte_identical_when_canon_names_no_protagonist(
    store: SqliteStore,
) -> None:
    """The control, and it is a byte comparison for the chapter cue's reason.

    Every book written before a world could declare a protagonist passes `None` here, and
    `input_digest_for` covers the prompt and is the sampler seed — so a fragment rendered under
    the falsy case would silently move the decoding of every newly minted job.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]
    packet = packet_for(store, head, beat)

    absent = render_prompt(beat, book_title="The Vane House", packet=packet)
    explicit = render_prompt(beat, book_title="The Vane House", packet=packet, point_of_view=None)
    assert explicit == absent
    assert "Point of view" not in absent[1]


def test_the_prompt_says_whose_scene_it_is(store: SqliteStore) -> None:
    """Position and fact, in the beat line, beside the chapter cue and before the function."""
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]
    packet = packet_for(store, head, beat)
    position = chapter_positions(head, SerialShape(scenes_per_chapter=4))[beat.logical_id]

    _, prompt = render_prompt(
        beat, book_title=None, packet=packet, chapter=position, point_of_view="silas"
    )
    assert (
        "scene 4 of 6. Chapter 1, scene 4 of 4. Point of view: silas. Dramatic function:" in prompt
    )

    # And without a chapter scheme it sits directly after the ordinal.
    _, alone = render_prompt(beat, book_title=None, packet=packet, point_of_view="silas")
    assert "scene 4 of 6. Point of view: silas. Dramatic function:" in alone


def test_the_point_of_view_fragment_carries_no_verb_and_no_adjective(
    store: SqliteStore,
) -> None:
    """**The boundary, asserted rather than trusted** — the chapter cue's test, one field over.

    The system may tell a writer whose scene this is; it may not tell it how to handle them.
    Open on the hero, make them likeable, show them winning, have them progress faster than
    anyone: that is the director's to say, and a default in this line would be this system's own
    taste arriving in every prompt it renders (stage-0 §95, §97.1). The operator's own words for
    a hook use exactly these verbs, which is why the fragment that came out of them must not.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]
    packet = packet_for(store, head, beat)

    _, prompt = render_prompt(beat, book_title=None, packet=packet, point_of_view="silas")
    cue = prompt.rsplit("scene 4 of 6.", 1)[1].split("Dramatic function:")[0]
    assert cue == " Point of view: silas. "
    for forbidden in (
        "hero",
        "likeable",
        "sympathetic",
        "win",
        "open",
        "first",
        "faster",
        "best",
        "should",
        "must",
        "make",
        "show",
    ):
        assert forbidden not in cue.lower()


def test_the_point_of_view_goes_before_the_beat_and_never_after_the_statement(
    store: SqliteStore,
) -> None:
    """`plans.scene_plan_line` is rendered last, always, and §61's comparison depends on it.

    `plan_search` mints K candidate drafts that differ only in that final fragment; a viewpoint
    appended after it would make the K prompts differ in two places and the tournament would
    stop being a controlled comparison.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[-1]
    packet = packet_for(store, head, beat)

    _, planned = render_prompt(
        beat,
        book_title=None,
        packet=packet,
        point_of_view="silas",
        scene_plan="Silas is refused entry at the archive.",
    )
    assert planned.rstrip().endswith("Silas is refused entry at the archive.")
    assert planned.index("Point of view: silas.") < planned.index("Dramatic function:")


def test_the_packet_is_built_for_the_protagonist_when_canon_names_one(
    store: SqliteStore,
) -> None:
    """The seam that existed and was never passed anything, measured on a real packet.

    Two effects and only two, both of them the packet's own: the facts block is labelled with
    whose knowledge it is, and `state.visible_to` admits records restricted to that id. On a
    forged world the second is a no-op — `records_for` writes no `pov_visibility` at all, because
    the iceberg is a claim with a disclosure and not packet access control (§107.4) — so the
    labelled heading is the whole of the observable difference, and that is what is asserted.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]

    for_nobody = packet_for(store, head, beat)
    for_silas = packet_for(store, head, beat, pov_character_id="silas")

    assert "Established facts:" in for_nobody.render()
    assert "Established facts known to silas:" in for_silas.render()
    assert [item.item_id for item in for_silas.sections[FACTS]] == [
        item.item_id for item in for_nobody.sections[FACTS]
    ]
    assert len(for_silas.omitted) == len(for_nobody.omitted)


def test_the_chapter_cue_goes_before_the_beat_and_never_after_the_statement(
    store: SqliteStore,
) -> None:
    """`plans.scene_plan_line` is rendered last, always, and §61's comparison depends on it.

    `plan_search` mints K candidate drafts that differ only in that final fragment; a cue
    appended after it would make the K prompts differ in two places and the tournament would
    stop being a controlled comparison. The statement therefore stays the last thing in the
    prompt with the cue present.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[-1]
    packet = packet_for(store, head, beat)
    position = chapter_positions(head, SerialShape(scenes_per_chapter=4))[beat.logical_id]

    _, bare = render_prompt(beat, book_title=None, packet=packet, chapter=position)
    _, planned = render_prompt(
        beat,
        book_title=None,
        packet=packet,
        chapter=position,
        scene_plan="The letter is read aloud.",
    )

    assert bare.rstrip().endswith("Dramatic function: resolution.")
    assert planned.rstrip().endswith("This scene: The letter is read aloud.")
    assert planned.index("Chapter 2,") < planned.index("Dramatic function:")


def test_the_planner_puts_the_chapter_position_on_the_queued_job(
    store: SqliteStore,
) -> None:
    """End to end through the selector, because a parameter no production caller passes is a
    parameter that does nothing — the defect shape
    `test_the_target_length_reaches_the_prompt_at_all` records, arriving one layer up."""
    _fixture(store, "mystery")

    make_plan_selector(project_id=PROJECT_ID, scenes_per_chapter=4)(store, "worker-a", START, 300.0)

    [job] = [
        unit for unit in store.jobs_by_status(JobStatus.QUEUED) if unit.job_kind == SCENE_DRAFT
    ]
    assert "Chapter 1, scene 1 of 4." in str(job.payload["prompt"])


def test_the_default_selector_queues_the_prompt_it_always_queued(store: SqliteStore) -> None:
    """The other half of the control: the production path at its default renders no cue."""
    _fixture(store, "mystery")

    make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 300.0)

    [job] = [
        unit for unit in store.jobs_by_status(JobStatus.QUEUED) if unit.job_kind == SCENE_DRAFT
    ]
    assert "Chapter" not in str(job.payload["prompt"])


def test_a_tick_over_a_book_planned_before_the_cue_remints_nothing(
    store: SqliteStore,
) -> None:
    """Replay: job identity is content-derived and deliberately excludes the prompt.

    `beat_job_id` keys on book, branch, scene, template and plan epoch, so a book whose beats
    were planned before this parameter existed converges rather than growing a second job per
    beat when the shape changes. The prompt of the job already stored is the prompt it was
    planned with, which is what makes a replayed attempt the same experiment.
    """
    _fixture(store, "mystery")
    make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 300.0)
    before = {
        unit.job_id: (unit.input_digest, str(unit.payload["prompt"]))
        for unit in store.jobs_by_status(JobStatus.QUEUED)
    }

    make_plan_selector(project_id=PROJECT_ID, scenes_per_chapter=4)(
        store, "worker-a", START + TICK, 300.0
    )

    after = {
        unit.job_id: (unit.input_digest, str(unit.payload["prompt"]))
        for unit in store.jobs_by_status(JobStatus.QUEUED)
    }
    assert after == before


def _writing(store: SqliteStore, prose: str) -> Conductor:
    """A loop whose generator writes exactly this scene, however the prompt asked."""
    registry = ProviderRegistry(FakeProvider(responses=[prose] * 8))
    return Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        select=make_plan_selector(project_id=PROJECT_ID),
        handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
    )


#: What the litrpg fixture's canon holds at `s1`, which a redraft of scene 1 must not
#: contradict. Written out rather than read from the snapshot, so a fixture change that moved
#: it fails this test loudly instead of making it vacuous.
S1_STATUS = {"level": 3, "hp": 24, "hp_max": 30, "mp": 8, "mp_max": 10, "gold": 45}


def _scene(status: dict[str, int]) -> str:
    body = "Rook counted what the night had left him and found it thinner than morning. " * 8
    return f"{body}\n\n{render_status_line('Rook', status)}\n"


def test_a_generated_scene_that_contradicts_canon_is_now_refused(store: SqliteStore) -> None:
    """**The measurable gain, and it is the gate rather than the extraction.**

    §8.3's fourth promotion clause and §17 Stage 1 both name the same missing leg: validation
    on model-written rather than templated prose. It was missing for a mechanical reason —
    nothing asked a generator for a `[STATUS]` line, so a generated litrpg scene carried no
    game state, `state.contradiction.v0` had nothing to read, and **every generated scene
    passed the integrity gate vacuously**. A scene claiming Rook had forty gold where canon
    says forty-five was accepted, because it never said so on the page.

    It now says so, and is refused. That is the deterministic gate going from vacuous to live
    on this system's own output.
    """
    _fixture(store, "litrpg")
    loop = _writing(store, _scene({**S1_STATUS, "gold": 40}))

    loop.tick(START)
    outcome = loop.tick(START + TICK)

    assert outcome is not None
    head = store.head(*_fixture_ids(store))
    assert head is not None
    assert head.node("scene-1").content is None, "the contradicting scene must not be accepted"
    [finding] = [item for item in store.findings(*_fixture_ids(store)) if item.blocks]
    assert finding.rule_or_critic_id == integrity.CONTRADICTION_RULE


def test_a_generated_scene_that_carries_canon_forward_is_accepted(store: SqliteStore) -> None:
    """The other half, and the one that keeps the gate from being a wall: a scene that states
    the established numbers is prose the book can keep. Without this the previous test would
    also pass on a gate that refused everything."""
    _fixture(store, "litrpg")
    loop = _writing(store, _scene(S1_STATUS))

    loop.tick(START)
    loop.tick(START + TICK)

    head = store.head(*_fixture_ids(store))
    assert head is not None
    assert "[STATUS] Rook" in (head.node("scene-1").content or "")


def _fixture_ids(store: SqliteStore) -> tuple[str, str]:
    book_id, branch_id, _ = store.branches()[0]
    return book_id, branch_id


# --- Book Zero: a book with no snapshot to read a position out of --------------------


def _seeded_sheet() -> lc.StateRecord:
    """A starting character sheet, and **deliberately with no story position**.

    Which is what a starting sheet is: the initial condition, true before the book begins
    rather than at some moment inside it. It gives the book a subject canon knows and tells
    the system this one states its game state on the page, without claiming a story-time
    vocabulary the book has not yet written.
    """
    return lc.StateRecord(
        record_id="rec-seed-rook",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate="status_snapshot",
        value={"level": 3, "hp": 24, "hp_max": 30, "mp": 8, "mp_max": 10, "gold": 45},
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def _book_zero(store: SqliteStore) -> tuple[str, str]:
    """The litrpg book with its plan and a seed sheet, but **no state snapshot** — every
    scene empty, and nothing anywhere attesting where any of them sits in story time."""
    from litharness.adapters.contracts_fixtures import fixture_manuscript, fixture_plans

    manuscript = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript("litrpg").read_text(encoding="utf-8")),
    )
    revision = import_manuscript(manuscript).revision
    store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")
    plan = import_plan(
        lc.parse_artifact(
            lc.PlanSnapshot, json.loads(fixture_plans("litrpg").read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_plan_items(
        revision.book_id, revision.branch_id, plan.items, created_at="2026-08-13T00:00:00Z"
    )
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        [_seeded_sheet()],
        created_at="2026-08-13T00:00:00Z",
    )
    return revision.book_id, revision.branch_id


def test_a_book_with_no_snapshot_could_not_extract_a_single_fact_it_wrote(
    store: SqliteStore,
) -> None:
    """The defect, stated as the loop actually met it. Every record in the system came from an
    imported snapshot, because `attested_position` reads a scene's story position out of the
    book's own evidence and a book this system wrote has none. So §12 step 5 extracted nothing
    from Book Zero — forever, and silently, since a scene with no extractable state looks
    exactly like one that established none.

    The template is entitled to answer: `SIX_BEAT` runs setup → resolution with no flashback
    beat in it, so a book planned from it cannot contain one. That is a statement about the
    sheet rather than an inference about a book, which is what makes it different from the
    ordinal scheme `test_the_obvious_order_key_scheme_is_wrong` refutes.
    """
    book_id, branch_id = _book_zero(store)
    loop = _writing(
        store, _scene({"level": 3, "hp": 24, "hp_max": 30, "mp": 8, "mp_max": 10, "gold": 45})
    )

    loop.tick(START)
    loop.tick(START + TICK)

    extracted = [
        record
        for record in store.state_records(book_id, branch_id)
        if record.record_id != "rec-seed-rook"
    ]
    assert extracted, "the book wrote a status line and could not place it"
    placed = {
        record.story_position.order_key: record
        for record in extracted
        if record.story_position is not None
    }
    assert "s1" in placed
    assert placed["s1"].value["gold"] == 45
    assert placed["s1"].note and "stated by the plan" in placed["s1"].note


def test_every_scene_of_a_book_zero_run_is_placed_not_just_the_first(
    store: SqliteStore,
) -> None:
    """**The defect a whole run finds and one scene never would.** Scene 1's own placed record
    is a canon record carrying an order key, so a guard asking "does this book have a story
    vocabulary" answers yes from scene 2 onward and every later scene abstains — a six-scene
    book extracting exactly one fact, looking at every layer like a book whose other five
    scenes established nothing.

    The guard asks whether somebody *else* chose the vocabulary, which is what
    `REGISTRY_VERSION` has always been for.
    """
    book_id, branch_id = _book_zero(store)
    balances = [45, 40, 38, 33, 30, 20]
    registry = ProviderRegistry(
        FakeProvider(
            responses=[
                _scene({"level": 3, "hp": 24, "hp_max": 30, "mp": 8, "mp_max": 10, "gold": gold})
                for gold in balances
            ]
        )
    )
    loop = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        select=make_plan_selector(project_id=PROJECT_ID),
        handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
    )
    for index in range(13):
        if loop.tick(START + index * TICK).outcome is TickOutcome.NO_WORK:
            break

    assert plan_progress(store, book_id, branch_id).drafted == 6
    placed = {
        record.story_position.order_key: record.value["gold"]
        for record in store.state_records(book_id, branch_id)
        if record.story_position is not None
    }
    assert placed == {f"s{index + 1}": gold for index, gold in enumerate(balances)}


def test_the_seeded_book_asks_for_the_line_it_will_later_read(store: SqliteStore) -> None:
    """The other half of the same circle: a book with no status record at all is not asked for
    system voice, so it writes none, so there is nothing to place. One seeded sheet — the
    starting condition a LitRPG book has anyway — closes it, and it is authored input rather
    than a genre this system guessed."""
    _book_zero(store)
    make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 300.0)

    [job] = [
        unit for unit in store.jobs_by_status(JobStatus.QUEUED) if unit.job_kind == SCENE_DRAFT
    ]
    assert "[STATUS] rook — Level 3 | HP 24/30 | MP 8/10 | Gold 45" in str(job.payload["system"])
    assert job.payload["selected_by"]["story_order_key"] == "s1"


def test_a_template_that_does_not_say_it_runs_forwards_places_nothing(
    store: SqliteStore,
) -> None:
    """The default is abstention, so a future template that forgets loses extraction coverage
    rather than minting a story order nothing downstream could detect as wrong."""
    quiet = BeatTemplate("template.quiet.v0", SIX_BEAT.functions)
    assert not quiet.chronological

    revision = store.head(*_book_zero(store))
    assert revision is not None

    assert [beat.story_order_key for beat in beats_for(revision, quiet)] == [None] * 6
    assert [beat.story_order_key for beat in beats_for(revision, SIX_BEAT)] == [
        f"s{index}" for index in range(1, 7)
    ]


live = pytest.mark.skipif(
    os.environ.get("LITHARNESS_LIVE_PROVIDERS") != "1",
    reason="set LITHARNESS_LIVE_PROVIDERS=1 to ask a real model (spends quota)",
)


@live
def test_a_real_model_writes_a_line_this_extractor_can_read(store: SqliteStore) -> None:
    """**The one thing `FakeProvider` structurally cannot check.** Every other test in this
    project runs on a provider that ignores the prompt, so nothing anywhere verifies that the
    instruction produces a line the extractor accepts — and the failure is silent, because a
    scene whose state nobody could read is indistinguishable from one that established none.

    It found a real defect. Shown `STATUS_TEMPLATE` with its `{subject}` slot intact, one of
    the three local models this once ran against wrote `[STATUS] {subject} — Level 3 | ...`
    out verbatim: the line matched the parser, extracted nothing, and no gate objected.
    Showing the book's own current line instead fixed it.

    The sub-frontier arms (llama3.2/qwen3/phi4 via Ollama) were retired with provider
    plurality, so this now runs on the pinned frontier provider — opting in spends quota —
    and it skips rather than fails where the CLI is not installed or authenticated.
    """
    from litharness.providers.base import CompletionRequest
    from litharness.providers.cli import ClaudeCodeProvider

    provider = ClaudeCodeProvider()
    if not provider.health():
        pytest.skip(f"{provider.binary} is not installed or not answering")

    book_id, branch_id = _book_zero(store)
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[0]
    system, prompt = render_prompt(
        beat,
        book_title=None,
        packet=packet_for(store, head, beat),
        status_example=system_voice_example(
            store.state_records(book_id, branch_id), at=beat.story_order_key
        ),
    )

    text = provider.complete(
        CompletionRequest(prompt=prompt, system=system, profile="default")
    ).text

    extracted = extract_state(
        text or "",
        known=store.state_records(book_id, branch_id),
        project_id=PROJECT_ID,
        book_id=book_id,
        branch_id=branch_id,
        logical_id=beat.logical_id,
        version_id="v",
        stated_order_key=beat.story_order_key,
    )
    assert extracted, f"{provider.model} wrote a scene this extractor reads nothing out of:\n{text}"
    assert extracted[0].subject == "rook"


# --- the plan store ------------------------------------------------------------------


def test_the_fixture_plan_is_reanchored_to_the_local_book(store: SqliteStore) -> None:
    """Contracts pins `PlanSnapshot.revision_id` to its own UUID5, which is never the
    sha256 content address import mints — so matching a plan to its manuscript by that
    field would never succeed. Keyed on the local book instead; the upstream id is kept."""
    book_id, branch_id = _fixture(store, "mystery")
    items = store.plan_items(book_id, branch_id)
    assert len(items) == 5
    assert {item.logical_id for item in items} >= {"plan-premise", "plan-promise-letter"}


def test_reimporting_the_same_plan_writes_no_new_rows(store: SqliteStore) -> None:
    book_id, branch_id = _fixture(store, "mystery")
    before = len(store.plan_items(book_id, branch_id))
    _fixture(store, "mystery")
    assert len(store.plan_items(book_id, branch_id)) == before


def test_plan_items_round_trip_through_the_contract(store: SqliteStore) -> None:
    """Stored verbatim as `item_json`, so authority/locked/links survive even though
    selection reads only kind and text."""
    import litharness_contracts as lc

    book_id, branch_id = _fixture(store, "mystery")
    locked = [item for item in store.plan_items(book_id, branch_id) if item.locked]
    assert len(locked) == 4
    assert all(item.authority is lc.PlanAuthority.INTENDED for item in locked)


def test_bumping_the_epoch_reissues_a_burned_beat(store: SqliteStore) -> None:
    """A poisoned beat burns its derived id forever — `idempotency_key` is UNIQUE. Without
    a version in the derivation, "try scene 3 again" would be inexpressible."""
    book_id, branch_id = _fixture(store, "mystery")
    loop = _conductor(store, pad=0)
    for index in range(6):
        loop.tick(START + index * TICK)
    assert store.job_counts_by_status().get("poisoned", 0) >= 1

    before = store.plan_epoch(book_id, branch_id)
    after = store.bump_plan_epoch(book_id, branch_id, at="2026-08-13T01:00:00Z", reason="test")
    assert after == before + 1

    # A fresh id under the new epoch, so the beat is plannable again.
    head = store.head(book_id, branch_id)
    assert head is not None
    new_id = beat_job_id(book_id, branch_id, "scene-1", SIX_BEAT.template_id, after)
    assert not store.has_job(new_id)
    assert _conductor(store).tick(START + 100 * TICK).outcome is TickOutcome.RAN_JOB


# --- §17 Stage 1 exit clause 4: planted-defect injection ------------------------------


def _plant(store: SqliteStore, book_id: str, branch_id: str, logical_id: str) -> str:
    """Inject a real planted defect from the fixture's own findings artifact.

    From `findings.json` rather than hand-built, so what the gate refuses is a defect the
    fixture authors labelled — a fabricated finding would only prove the gate can read a
    dataclass this file wrote.
    """
    from dataclasses import replace as dataclass_replace

    from litharness.adapters.contracts_fixtures import fixture_findings
    from litharness.adapters.evaluation_artifact import load_findings

    findings = load_findings(fixture_findings("litrpg")).findings
    planted = next(item for item in findings if item.finding_id == "f-gold-ledger")
    # Re-anchored onto the node under test: the artifact's own scope names the *producer's*
    # book, which is never the sha256 address this store minted on import.
    moved = dataclass_replace(planted, logical_id=logical_id)
    store.record_findings(book_id, branch_id, [moved], created_at="2026-08-13T00:00:00Z")
    return moved.finding_id


def test_a_planted_defect_is_refused_by_the_gate_not_accepted_by_luck(
    store: SqliteStore,
) -> None:
    """§17 Stage 1's fourth exit clause, over a real tick rather than a unit test.

    Before this slice the only blocking gate in the wired path was `shape.draft.v0`, so a
    candidate of plausible length was accepted whatever the book said. The assertion that
    matters is the second one: the scene is still **empty** afterwards. A gate that recorded
    a refusal and committed the revision anyway would satisfy every other check here.
    """
    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None
    first = beats_for(head, SIX_BEAT)[0].logical_id
    _plant(store, book_id, branch_id, first)

    outcomes = _run(store, 3)

    # The unit ran — this is not a book that quietly had nothing to do.
    assert TickOutcome.NO_WORK not in outcomes
    head = store.head(book_id, branch_id)
    assert head is not None
    assert head.node(first).content is None, "a planted defect reached accepted canon"


def test_the_refusal_is_recorded_as_an_integrity_gate_on_the_decision(
    store: SqliteStore,
) -> None:
    """ "Caught by gates, not luck" has to be legible afterwards or it is indistinguishable
    from the model happening not to produce anything. The decision names the gate."""
    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None
    first = beats_for(head, SIX_BEAT)[0].logical_id
    _plant(store, book_id, branch_id, first)
    _run(store, 2)

    job_id = beat_job_id(book_id, branch_id, first, SIX_BEAT.template_id, 0)
    decision = store.latest_decision_for(job_id)
    assert decision is not None
    integrity = [gate for gate in decision.gates if gate.gate is GateKind.INTEGRITY]
    assert integrity, "the integrity gate did not run"
    assert not integrity[0].passed
    assert Veto.CONTINUITY_BREACH in decision.failed_vetoes
    assert decision.outcome in {Outcome.RETRY, Outcome.PARK}


def test_the_defect_stops_that_beat_without_stalling_the_book(store: SqliteStore) -> None:
    """§4.1: a blocked item never stalls the queue — the Conductor works elsewhere in the
    book. A gate that blocked the whole branch would convert one defect into a dead book,
    which is the more expensive failure and the easier one to ship by accident."""
    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None
    beats = beats_for(head, SIX_BEAT)
    _plant(store, book_id, branch_id, beats[0].logical_id)

    _run(store, 14)

    head = store.head(book_id, branch_id)
    assert head is not None
    assert head.node(beats[0].logical_id).content is None, "the planted beat was accepted"
    drafted = [
        beat.logical_id for beat in beats[1:] if head.node(beat.logical_id).content is not None
    ]
    assert len(drafted) == 5, f"the book stalled; only {drafted} advanced"


def test_a_standing_finding_parks_the_unit_revivably_and_costs_no_tokens(
    store: SqliteStore,
) -> None:
    """§19.1's rule, third instance: **a refusal reached before the work must cost time,
    never the unit.**

    A finding already on record cannot be caused or cleared by the candidate, so all three
    attempts meet the identical refusal. Charging them poisons the unit — terminal,
    unrevivable, idempotency key burned — roughly fifteen minutes into a run at the plan's
    cadence, which is long before a human reads the queue. The operator's correct response is
    to dismiss the finding, and it would arrive to find nothing left to resume.

    This is the same shape as `ProviderUnavailable` and as the budget ceiling, both of which
    §19.1 records as having been charged against a unit that never ran. Three instances, one
    rule.
    """
    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None
    first = beats_for(head, SIX_BEAT)[0].logical_id
    _plant(store, book_id, branch_id, first)

    _run(store, 4)

    job = store.load_job(beat_job_id(book_id, branch_id, first, SIX_BEAT.template_id, 0))
    assert job.status is JobStatus.PARKED, "a pre-flight refusal destroyed the unit it refused"
    assert job.attempts == 0, "the attempt was charged for work that never ran"
    # Refused in front of the spend, so no provider was reached at all.
    decision = store.latest_decision_for(job.job_id)
    assert decision is not None
    assert decision.refused_before_work
    assert decision.invocations == 0 and decision.total_tokens == 0


def test_dismissing_the_finding_then_reviving_lets_the_beat_through(
    store: SqliteStore,
) -> None:
    """The operator's way out, end to end and by the documented verbs.

    `dismiss` then `revive` — no epoch bump, no new database. This is the test that would
    have caught the defect above: it passes only because the unit parked instead of
    poisoning, and `revive` refuses a poisoned unit by design.

    One tick, deliberately: `revive` puts the unit back with its *frozen* base, so it is the
    right verb only while that base is still the head. Once other beats have advanced, the
    revived unit meets `_stale_base` instead — see the next test, which is the case an
    operator who read the queue an hour later actually has.
    """
    from litharness.domain.findings import Status

    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None
    first = beats_for(head, SIX_BEAT)[0].logical_id
    finding_id = _plant(store, book_id, branch_id, first)
    _run(store, 1)
    head = store.head(book_id, branch_id)
    assert head is not None and head.node(first).content is None

    store.set_finding_status(finding_id, Status.ACCEPTED_INTENTIONAL)
    store.revive(beat_job_id(book_id, branch_id, first, SIX_BEAT.template_id, 0))
    _run(store, 8)

    head = store.head(book_id, branch_id)
    assert head is not None
    assert head.node(first).content is not None, "dismissing the finding did not unblock it"


def test_after_the_head_has_moved_the_recovery_verb_is_replan(store: SqliteStore) -> None:
    """`revive` alone is not enough once other beats have advanced, and that is by design
    rather than a gap: the payload freezes a base revision, `save_job` never rewrites it, and
    `_stale_base` escalates rather than retrying against an id that will never be current.

    What was missing is the verb that clears it. `handlers._stale_base` and migration 011
    both name `replan`, and until now `bump_plan_epoch` had exactly one caller and it was a
    test — the same shape as `reset_health` documenting "called at the start of a tick" with
    no non-test caller.
    """
    from litharness.domain.findings import Status

    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None
    first = beats_for(head, SIX_BEAT)[0].logical_id
    finding_id = _plant(store, book_id, branch_id, first)

    # Long enough that the other five beats draft and the head moves well past the base the
    # blocked unit was planned against.
    _run(store, 10)
    store.set_finding_status(finding_id, Status.ACCEPTED_INTENTIONAL)
    store.revive(beat_job_id(book_id, branch_id, first, SIX_BEAT.template_id, 0))
    _run(store, 4)

    head = store.head(book_id, branch_id)
    assert head is not None
    assert head.node(first).content is None, "a stale base should not have drafted"

    epoch = store.bump_plan_epoch(
        book_id, branch_id, at="2026-08-13T03:00:00Z", reason="finding dismissed"
    )
    assert epoch == 1
    _run(store, 6)

    head = store.head(book_id, branch_id)
    assert head is not None
    assert head.node(first).content is not None, "replan did not reissue the freed beat"
    # And it reissued only what was still empty: the other five keep the prose they had.
    scenes = [node for node in head.in_reading_order() if node.kind is NodeKind.SCENE]
    assert all(node.content for node in scenes)


def test_a_candidate_the_model_got_wrong_still_costs_its_attempts(store: SqliteStore) -> None:
    """The other side of the distinction, so the fix above is not read as "integrity never
    charges". A refusal about *this candidate* is about the work and is charged normally —
    only a refusal that was knowable before the generation is free."""
    from litharness.domain.integrity import STANDING_GATE
    from litharness.domain.policy import PRE_FLIGHT

    assert STANDING_GATE in PRE_FLIGHT
    # The post-generation gate is deliberately absent: its refusal judges output that exists.
    from litharness.domain.integrity import INTEGRITY_GATE

    assert INTEGRITY_GATE not in PRE_FLIGHT


def test_a_clean_book_is_not_refused_by_the_new_gate(store: SqliteStore) -> None:
    """The false-accept clause's twin, and the one that would actually stop the project: a
    gate that refuses a conforming book is not a floor, it is an outage. Both fixtures still
    reach six accepted scenes with the integrity gate live."""
    for fixture in ("mystery", "litrpg"):
        book_id, branch_id = _fixture(store, fixture)
        _run(store, 20)
        head = store.head(book_id, branch_id)
        assert head is not None
        scenes = [node for node in head.in_reading_order() if node.kind is NodeKind.SCENE]
        assert all(node.content for node in scenes), f"{fixture} was refused by the new gate"


@pytest.mark.parametrize("fixture", ["mystery", "litrpg"])
def test_an_autonomous_run_extracts_nothing_from_a_fixture_book(
    store: SqliteStore, fixture: str
) -> None:
    r"""The tripwire on §12 step 5, and it guards the *extractor* rather than the prompt.

    Extraction runs on every accepted scene now, so a six-scene autonomous run is where a
    careless pattern would surface as canon nobody authored. It holds today for a reason
    worth stating rather than assuming: ``FakeProvider`` echoes ``[fake:<digest>] ...`` and
    ``STATUS_PATTERN`` anchors on ``^\[STATUS\]``, so the echo never matches -- not "the
    fake emits no bracket lines", which is false. ``FakeProvider`` ignores prompts entirely,
    so a ``render_prompt`` change cannot move this either.
    """
    book_id, branch_id = _fixture(store, fixture)
    before = len(store.state_records(book_id, branch_id))

    _run(store, 8)

    assert len(store.state_records(book_id, branch_id)) == before, "no invented canon"
    assert store.findings(book_id, branch_id) == [], "and nothing for the gate to refuse"


def test_a_scene_contradicting_established_canon_is_refused_and_writes_nothing(
    store: SqliteStore,
) -> None:
    """§12 steps 5 and 6 closing on each other, which is why extraction exists.

    The litrpg fixture establishes Rook at `Gold 45` at story position s1. A candidate whose
    own system voice says `Gold 14` contradicts it — a corruption only this store can see,
    because ContinuityEvaluation never sees a LitHarness store mid-run. Before extraction the
    detector had no in-process producer and this candidate was accepted.

    Both refusals in the ladder are exercised, and the second is the one §19.1 paid for: the
    candidate's own contradiction costs an attempt, and the *next* tick meets the finding
    already standing and parks pre-flight for no attempt and no tokens.

    The assertions that matter are negative: the node is still empty and **no state row was
    written**. Extraction runs before the gate precisely so refusing is free — extracting
    after acceptance would commit both the prose and the contradicting record, then report it.
    """
    book_id, branch_id = _fixture(store, "litrpg")
    before = len(store.state_records(book_id, branch_id))

    class Contradicting(FakeProvider):
        def complete(self, request):  # type: ignore[override]
            result = super().complete(request)
            line = "[STATUS] Rook — Level 4 | HP 34/30 | MP 6/10 | Gold 14"
            return replace(result, text=f"{line}\n\n{result.text}")

    registry = ProviderRegistry(Contradicting(pad_to_chars=PAD))
    loop = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        select=make_plan_selector(),
        handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
    )
    outcomes = [loop.tick(START + index * TICK).outcome for index in range(4)]

    assert TickOutcome.RAN_JOB not in outcomes, "no candidate may be accepted"
    head = store.head(book_id, branch_id)
    assert head is not None
    assert not (head.node("scene-1").content or ""), "the beat's node is still empty"
    assert len(store.state_records(book_id, branch_id)) == before, "and nothing was written"

    # Asserted positively, because "no candidate was accepted" is equally true of a handler
    # that crashed — this test passed its three negative assertions once while the provider
    # was raising a NameError, which is the shape of a green test over a dead mechanism.
    assert outcomes == [
        TickOutcome.JOB_FAILED,  # the candidate's own contradiction, charged an attempt
        TickOutcome.JOB_PARKED,  # the finding now stands: refused pre-flight, free
        TickOutcome.JOB_FAILED,  # and the next beat meets the same wall
        TickOutcome.JOB_PARKED,
    ]

    findings = store.findings(book_id, branch_id)
    assert findings, "the contradiction is on record"
    assert any("position s1" in finding.message for finding in findings)
    assert any(finding.rule_or_critic_id == integrity.CONTRADICTION_RULE for finding in findings)


# --- Stage 3: a book longer than six scenes ------------------------------------------


def test_the_arc_reproduces_the_six_beat_sheet() -> None:
    """**The property that makes generalising safe.** `arc_template(6)` must be `SIX_BEAT`
    function for function — a generalisation that drifted at six would be a *different*
    template quietly relabelling every beat of both golden fixtures, and `beat_job_id`
    derives from the template id rather than its content, so nothing downstream would
    notice."""
    assert arc_template(len(SIX_BEAT)).functions == SIX_BEAT.functions


def test_a_longer_arc_keeps_its_singular_beats_singular() -> None:
    """A story has one inciting incident at any length. Spreading the six functions
    proportionally — the obvious implementation — gives a sixty-scene book twelve of them,
    which is not a longer story but a broken one. Only *rising* repeats."""
    functions = arc_template(60).functions

    assert len(functions) == 60
    for once in ("setup", "inciting", "turn", "crisis", "resolution"):
        assert functions.count(once) == 1, once
    assert functions[0] == "setup"
    assert functions[-1] == "resolution"
    assert functions[-2] == "crisis"
    assert functions.count("rising") == 55


def test_an_arc_shorter_than_its_named_beats_is_refused() -> None:
    """The six-beat sheet is the floor the fixtures and gates are built on, and an arc with
    fewer scenes than named beats has no defensible assignment — the same refusal
    `beats_for` makes rather than interpolating."""
    with pytest.raises(TemplateMismatch, match="at least 6 scenes"):
        arc_template(5)


def test_a_six_scene_book_keeps_the_six_beat_template_id(store: SqliteStore) -> None:
    """The arc reproduces the sheet; it does not replace it. Switching the fixtures onto
    `template.arc-6.v0` would remint every beat job id in both golden books for no change in
    what any beat asks for."""
    book_id, branch_id = _fixture(store, "litrpg")
    head = store.head(book_id, branch_id)
    assert head is not None

    assert template_for(head).template_id == SIX_BEAT.template_id


def test_a_book_of_another_length_gets_an_arc_of_its_own_length(store: SqliteStore) -> None:
    """Before this, `beats_for` refused every book that was not exactly six scenes — so a
    50-80k word Book Zero reported itself blocked before its first tick."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book Zero", scenes=24)
    store.commit_revision(revision, created_at="2026-08-15T00:00:00Z")

    template = template_for(revision)

    assert template.template_id == "template.arc-24.v0"
    assert len(beats_for(revision, template)) == 24
    assert template.chronological, "an arc runs forwards, so its beats can state where they sit"


def test_an_empty_book_is_all_draftable_and_says_nothing(store: SqliteStore) -> None:
    """Empty rather than absent is what draftable means: `gate_draft` fills an empty node and
    refuses to overwrite content, so a scene the planner can work on is one that exists and
    says nothing."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book Zero", scenes=12)

    scenes = [node for node in revision.in_reading_order() if node.kind is NodeKind.SCENE]
    assert len(scenes) == 12
    assert all(node.content is None for node in scenes)
    assert all(is_draftable(revision, node.logical_id) for node in scenes)
    assert [node.position_key for node in scenes] == sorted(node.position_key for node in scenes), (
        "reading order must follow position order"
    )


def test_story_order_keys_sort_as_story_order_past_nine_scenes(store: SqliteStore) -> None:
    """**Order keys are compared as strings, and `s10 < s2`.**

    Every consumer compares them that way: `records_before` slices the context packet on
    `<=`, `changes_between` matches on equality, and propagation's `fact_changed` filter asks
    which records come *after* the change. An unpadded key therefore reverses story order the
    moment a book passes nine scenes — silently, since nothing else changes shape.

    Measured on a 24-scene Book Zero, whose ledger read back s1, s10, s11 … s2. Width comes
    from the book's own scene count, so `s1`-`s6` at six scenes is unchanged and still matches
    what both golden fixtures author.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book Zero", scenes=24)
    keys = [beat.story_order_key for beat in beats_for(revision, template_for(revision))]

    assert keys[:3] == ["s01", "s02", "s03"]
    assert keys[-1] == "s24"
    assert keys == sorted(keys), "story order must survive a string sort"

    six = new_book(BOOK_ID, BRANCH_ID, title="Six", scenes=6)
    assert [beat.story_order_key for beat in beats_for(six, template_for(six))] == [
        f"s{n}" for n in range(1, 7)
    ], "the six-scene convention both fixtures author is unchanged"


def test_a_schedule_is_a_record_that_is_not_canon(store: SqliteStore) -> None:
    """**The shape the system already had.** A milestone is a claim about what the state
    *should become* at a future position, which `PROPOSED` says exactly — so it needs no new
    storage, no contract field and no prose to parse.

    And because `is_canon` excludes it, the context packet does not hand it to a scene as an
    established fact and `detect_contradictions` does not weigh it against what the prose
    says. It informs generation and contaminates nothing.
    """
    book_id, branch_id = _book_zero(store)
    goal = lc.StateRecord(
        record_id="rec-goal",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate="status_snapshot",
        value={"level": 5, "hp": 44, "hp_max": 44, "mp": 12, "mp_max": 12, "gold": 5},
        story_position=lc.StoryPosition(order_key="s6"),
        authority=lc.StateAuthority.PROPOSED,
    )
    store.record_state_records(book_id, branch_id, [goal], created_at="2026-08-15T00:00:00Z")
    records = store.state_records(book_id, branch_id)

    assert progression_target(records, at="s1") == (
        "[STATUS] rook — Level 5 | HP 44/44 | MP 12/12 | Gold 5"
    )
    # The seed sheet is canon and is what the scene is shown as *current*; the milestone is
    # not, and is what it is shown as *coming*. Neither is the other.
    assert "Gold 45" in (system_voice_example(records, at="s1") or ""), "the seed"
    assert not speaks_system_voice([goal]), "a proposal does not make a book speak"


def test_a_schedule_aims_at_the_next_milestone_not_the_last(store: SqliteStore) -> None:
    """A book aims at where it is going. Never interpolated between milestones either: a
    level curve's shape is a modelling choice the author made when they wrote the schedule,
    and inventing points on it would be deriving the one thing extraction refuses to."""
    book_id, branch_id = _book_zero(store)
    milestones = [
        lc.StateRecord(
            record_id=f"rec-goal-{key}",
            kind=lc.StateRecordKind.ASSERTION,
            subject="rook",
            predicate="status_snapshot",
            value={"level": level, "hp": 20, "hp_max": 20, "mp": 5, "mp_max": 5, "gold": 50},
            story_position=lc.StoryPosition(order_key=key),
            authority=lc.StateAuthority.PROPOSED,
        )
        for key, level in (("s2", 2), ("s5", 4))
    ]
    store.record_state_records(book_id, branch_id, milestones, created_at="2026-08-15T00:00:00Z")
    records = store.state_records(book_id, branch_id)

    assert "Level 2" in (progression_target(records, at="s1") or "")
    assert "Level 4" in (progression_target(records, at="s3") or "")
    assert progression_target(records, at="s6") is None, "nothing ahead is nothing to aim at"


def test_a_book_with_no_schedule_asks_for_nothing_extra(store: SqliteStore) -> None:
    """Opt-in by authoring one. A book without a schedule gets the instruction it got
    before — which, measured, means its ledger is whatever its model does unprompted."""
    book_id, branch_id = _book_zero(store)
    records = store.state_records(book_id, branch_id)

    assert progression_target(records) is None
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[0]
    system, _ = render_prompt(
        beat,
        book_title=None,
        packet=packet_for(store, head, beat),
        status_example=system_voice_example(records, at=beat.story_order_key),
        progression=progression_target(records, at=beat.story_order_key),
    )
    assert "reaching this later on" not in system


def test_a_book_written_blind_says_so_in_the_digest(store: SqliteStore) -> None:
    """**The omissions were recorded where nothing reads them.**

    `context_omitted` has always been on the job payload — the honest half of a packet that
    packs by priority rather than relevance — and no operator surface showed it. So a book
    could reach mid-draft with every scene written knowing three scenes of its own history,
    and `status` would report a clean system.

    Measured: at the 900-word target the 6,000-token default binds at **scene 5** and holds
    three prior scenes, against scene 24 at the 160 words a 3B model actually writes. The two
    numbers this project asks an operator to choose — scene length and context budget — are
    coupled, and nothing said so.
    """
    book_id, branch_id = _book_zero(store)
    head = store.head(book_id, branch_id)
    assert head is not None
    prose = ("Rook counted the coins by the gate. " * 40).strip()
    # One child revision, not four: each `replacing` parents on the revision it was called
    # against, so a chain built from `head` produces siblings rather than a lineage.
    filled = head.replacing(
        [head.node(f"scene-{index}").with_content(prose) for index in range(1, 5)]
    )
    store.commit_revision(filled, created_at="2026-08-15T00:01:00Z")

    # A budget too small to hold four scenes of prose: the packet drops the oldest.
    make_plan_selector(project_id=PROJECT_ID, token_budget=2200)(store, "worker-a", START, 300.0)

    day = datetime.fromtimestamp(START, tz=UTC).date().isoformat()
    assert store.digest(day).get("context_omitted", 0) > 0


def test_a_packet_that_fits_says_nothing(store: SqliteStore) -> None:
    """The counter must mean "this book is being written blind", so it cannot fire on a book
    whose context fits — which is every six-scene fixture, and the reason this limit has been
    invisible since it was written."""
    _fixture(store, "litrpg")
    make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 300.0)

    day = datetime.fromtimestamp(START, tz=UTC).date().isoformat()
    assert store.digest(day).get("context_omitted", 0) == 0


# --- the ladder reaches the writer (plan/stage-0-decisions.md §113) ---------------------------


def _ladder_records(subject: str = "rook") -> list[lc.StateRecord]:
    """A three-rung ordinal chain, a graph line that prints a change on it, and a standing."""
    return [
        worlds.world_record(
            "assay_grade",
            worlds.TYPE_PREDICATE,
            value=worlds.CRITERION,
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "assay_grade",
            worlds.COMPARATOR_PREDICATE,
            value="ordinal",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        *[
            worlds.world_record(
                rung,
                worlds.MANIFESTS_PREDICATE,
                value=form,
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
            for rung, form in (
                ("third_seal", "a lead seal that greens in a week"),
                ("second_seal", "a brass seal worn at the throat"),
                ("first_seal", "a silver seal nobody hands back"),
            )
        ],
        *[
            worlds.world_record(
                lower,
                worlds.PRECEDES_PREDICATE,
                object_ref=higher,
                value="assay_grade",
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
            for lower, higher in (
                ("third_seal", "second_seal"),
                ("second_seal", "first_seal"),
            )
        ],
        worlds.world_record(
            subject,
            worlds.ENTITY_ROLE_PREDICATE,
            value="protagonist",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            subject,
            worlds.STANDS_AT_PREDICATE,
            object_ref="third_seal",
            value="assay_grade",
            order_key="s1",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "book",
            worlds.GRAPH_LINE_PREDICATE,
            value={
                "label": "ASSAY",
                "edges": [{"phrase": "now stands at", "predicate": worlds.STANDS_AT_PREDICATE}],
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]


def _scheduled(subject: str = "rook") -> list[lc.StateRecord]:
    """The outline's own PROPOSED rung schedule, as `standing_milestone_records` writes it."""
    return [
        lc.StateRecord(
            record_id=f"standing-{key}",
            kind=lc.StateRecordKind.RELATIONSHIP,
            subject=subject,
            predicate=worlds.STANDS_AT_PREDICATE,
            value="assay_grade",
            object_ref=rung,
            authority=lc.StateAuthority.PROPOSED,
            story_position=lc.StoryPosition(order_key=key),
        )
        for key, rung in (("s3", "second_seal"), ("s5", "first_seal"))
    ]


def test_a_standing_schedule_aims_at_the_next_rung_not_the_last() -> None:
    """`progression_target`'s rule, transposed: a book aims at where it is going.

    And it carries the number, because on this brief the number *is* the rung's place in the
    chain — the operator's direction, bronze is 1 and gold is 3.
    """
    records = [*_ladder_records(), *_scheduled()]

    at_one = standing_target(records, at="s1") or ""
    assert "rook stands at third_seal (1 of 3)" in at_one
    assert "the book's plan has them at second_seal (2 of 3)" in at_one
    # The visible form travels with the rung: a rank a reader is told rather than shown is
    # what `manifests_as` exists to refuse.
    assert "a brass seal worn at the throat" in at_one

    assert "first_seal (3 of 3)" in (standing_target(records, at="s4") or "")
    assert standing_target(records, at="s6") is None, "nothing ahead is nothing to aim at"
    # Never interpolated: the schedule's shape is the schedule's.
    assert "second_seal" not in (standing_target(records, at="s4") or "")


def test_the_writer_is_handed_the_next_rung_and_the_line_the_book_prints(
    store: SqliteStore,
) -> None:
    """The ask, in the numeric block's own wording, and a filled example rather than a form."""
    book_id, branch_id = _book_zero(store)
    store.record_state_records(
        book_id,
        branch_id,
        [*_ladder_records(), *_scheduled()],
        created_at="2026-08-22T00:00:00Z",
    )
    records = store.state_records(book_id, branch_id)
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[0]
    packet = packet_for(store, head, beat)

    system, _ = render_prompt(
        beat,
        book_title=None,
        packet=packet,
        standing=standing_target(records, at=beat.story_order_key),
        standing_line=standing_example(records, at=beat.story_order_key),
    )
    assert "The book's plan has the standing reaching this later on:" in system
    assert "Move it toward that in this scene where the events warrant it" in system
    assert "[ASSAY] rook now stands at third_seal" in system
    # A filled line, never a form with braces: the measurement `system_voice_example` records.
    assert "{" not in system.split("print the line in this form")[-1]


def test_the_standing_block_carries_no_verb_and_no_adjective(store: SqliteStore) -> None:
    """**The §113 standing boundary, asserted rather than trusted.**

    Code carries facts, positions and schedules — never taste. The system may tell a writer
    that the plan has a standing reaching a rung later on, in exactly the register it already
    tells a writer that the plan has a *number* reaching one. It may not say the rise should be
    earned, felt, triumphant or paid off: that is the operator's to say through a directive, and
    a default here would be this system's own taste arriving in every prompt it renders. The
    words below are the ones such an instruction would have to use.

    `test_the_chapter_cue_carries_no_verb_and_no_adjective` is the pattern; this is the same
    check one block down.
    """
    book_id, branch_id = _book_zero(store)
    store.record_state_records(
        book_id,
        branch_id,
        [*_ladder_records(), *_scheduled()],
        created_at="2026-08-22T00:00:00Z",
    )
    records = store.state_records(book_id, branch_id)
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[0]
    packet = packet_for(store, head, beat)

    bare, _ = render_prompt(beat, book_title=None, packet=packet)
    withled, _ = render_prompt(
        beat,
        book_title=None,
        packet=packet,
        standing=standing_target(records, at=beat.story_order_key),
        standing_line=standing_example(records, at=beat.story_order_key),
    )
    authority_marker = "\n\nAUTHOR-LOCKED STORY DECISIONS"
    bare_guidance = bare.split(authority_marker, 1)[0]
    withled_guidance = withled.split(authority_marker, 1)[0]
    block = withled_guidance[len(bare_guidance) :].lower()
    assert block, "the standing block is what is being checked"
    for forbidden in (
        "earn",
        "earned",
        "deserve",
        "triumph",
        "victory",
        "feel",
        "felt",
        "emotion",
        "satisfying",
        "satisfy",
        "reward",
        "rewarding",
        "celebrate",
        "climax",
        "pay it off",
        "payoff",
        "exciting",
        "epic",
        "hard-won",
        "struggle",
        "moment",
    ):
        assert forbidden not in block, forbidden


def test_a_book_with_no_ladder_renders_the_prompt_it_rendered_before(
    store: SqliteStore,
) -> None:
    """The byte-identical control, and it is a byte comparison for `input_digest_for`'s reason.

    The digest covers the prompt and is the sampler seed, so a block rendered for a book that
    declares nothing would silently re-decode every job every existing book mints. Both golden
    fixtures are in this state and stay in it.
    """
    book_id, branch_id = _fixture(store, "mystery")
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = beats_for(head, SIX_BEAT)[3]
    packet = packet_for(store, head, beat)
    records = store.state_records(book_id, branch_id)

    assert standing_target(records) is None
    assert standing_example(records) is None
    absent = render_prompt(beat, book_title="The Vane House", packet=packet)
    passed = render_prompt(
        beat,
        book_title="The Vane House",
        packet=packet,
        standing=standing_target(records),
        standing_line=standing_example(records),
    )
    assert passed == absent
