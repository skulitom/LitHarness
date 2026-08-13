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

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.planner import (
    beat_job_id,
    make_plan_selector,
    packet_for,
    plan_progress,
    render_prompt,
)
from litharness.domain.beats import SIX_BEAT, BeatTemplate, TemplateMismatch, beats_for
from litharness.domain.context import assemble
from litharness.domain.draft import DraftPolicy, is_draftable
from litharness.domain.jobs import JobStatus
from litharness.domain.nodes import LockKind, Node, NodeKind
from litharness.domain.plans import import_plan
from litharness.domain.revision import Revision, build_revision, import_manuscript
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
    state = import_state(
        state_snapshot, book_id=revision.book_id, branch_id=revision.branch_id
    )
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        state.records,
        created_at="2026-08-13T00:00:00Z",
        source_revision_id=state.source_revision_id,
    )
    return revision.book_id, revision.branch_id


def _conductor(store: SqliteStore, *, pad: int = PAD, **kwargs) -> Conductor:
    registry = ProviderRegistry(providers=[FakeProvider(pad_to_chars=pad)], order=["fake"])
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
            Node(logical_id="empty", kind=NodeKind.SCENE, position_key="010",
                 parent_logical_id="book"),
            Node.text_node("full", NodeKind.SCENE, "020", "Already written.",
                           parent_logical_id="book"),
            Node(logical_id="locked", kind=NodeKind.SCENE, position_key="030",
                 parent_logical_id="book", lock=LockKind.PUBLISHED),
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
            node if node.logical_id != "scene-3" else Node(
                logical_id=node.logical_id, kind=node.kind, position_key=node.position_key,
                parent_logical_id=node.parent_logical_id, title=locked.title,
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
            Node(logical_id="scene-1", kind=NodeKind.SCENE, position_key="010",
                 parent_logical_id="book"),
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
            Node(logical_id="s1", kind=NodeKind.SCENE, position_key="010",
                 parent_logical_id="book", title="The Study"),
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
    _, prompt = render_prompt(beat, book_title="The Vane House", packet=packet)

    # The two locked plan items that bear on scene 6, which the pre-packet prompt omitted.
    assert "rain-on-glass motif repeats deliberately in scenes 1, 3, and 6" in prompt
    assert "sealed letter must be read aloud at the will reading" in prompt
    # The open thread the resolution owes a payoff.
    assert "sealed_letter_reading" in prompt
    assert prompt.rstrip().endswith("Dramatic function: resolution.")


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
