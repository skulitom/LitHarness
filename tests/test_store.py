"""Persistence gates for Stage 0's exit criterion.

Covers the half of "revisions, patches, events, and restore work end-to-end without a
model" that lives in storage, plus the crash-safety and idempotency properties §19 asks
for. No model is involved anywhere in this file, which is the point.
"""

from __future__ import annotations

import gc
import shutil
import sqlite3
import weakref

import pytest

from litharness.adapters.sqlite_store import (
    IntegrityFailure,
    MigrationsMissing,
    SqliteStore,
    migrations_dir,
)
from litharness.domain.events import Event, EventType, OutboxState
from litharness.domain.jobs import IllegalTransition, Job, JobStatus, LeaseError
from litharness.domain.patch import apply_patch
from litharness.domain.policy import Outcome, PolicyDecision
from litharness.domain.revision import Revision
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, SCENES, build_patch, make_revision

NOW = "2026-08-12T00:00:00Z"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "litharness.db")


def test_store_context_manager_closes_the_connection(tmp_path) -> None:
    with SqliteStore.open(tmp_path / "managed.db") as managed:
        assert managed.path.endswith("managed.db")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        _ = managed.path


def test_unreachable_store_closes_its_native_handle(tmp_path) -> None:
    abandoned = SqliteStore.open(tmp_path / "abandoned.db")
    connection = abandoned._connection
    reference = weakref.ref(abandoned)

    del abandoned
    gc.collect()

    assert reference() is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def accepted_event(revision: Revision, note: str = "") -> Event:
    return Event(
        event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
        project_id=PROJECT_ID,
        created_at=NOW,
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        revision_id=revision.revision_id,
        payload={"nodes": len(revision.nodes), "note": note},
    )


# --- revisions round-trip ----------------------------------------------------------


def test_revision_round_trips_through_storage(store: SqliteStore, revision: Revision) -> None:
    store.commit_revision(revision, created_at=NOW)
    restored = store.load_revision(revision.revision_id)
    assert restored.revision_id == revision.revision_id
    assert restored.version_ids == revision.version_ids
    assert restored.rendered_text() == revision.rendered_text()


def test_committing_the_same_revision_twice_is_a_no_op(
    store: SqliteStore, revision: Revision
) -> None:
    store.commit_revision(revision, created_at=NOW)
    store.commit_revision(revision, created_at=NOW)
    count = store._connection.execute("SELECT COUNT(*) AS n FROM revisions").fetchone()["n"]
    assert count == 1


def test_unchanged_nodes_are_stored_once_across_revisions(
    store: SqliteStore, revision: Revision
) -> None:
    """Content addressing means an edit stores one new node row, not a whole new tree."""
    store.commit_revision(revision, created_at=NOW)
    before = store._connection.execute("SELECT COUNT(*) AS n FROM node_versions").fetchone()["n"]
    edited = revision.replacing([revision.node("scene-3").with_content("Rewritten scene three.")])
    store.commit_revision(edited, created_at=NOW)
    after = store._connection.execute("SELECT COUNT(*) AS n FROM node_versions").fetchone()["n"]
    assert after == before + 1


def test_fork_stores_no_new_node_versions(store: SqliteStore, revision: Revision) -> None:
    store.commit_revision(revision, created_at=NOW)
    before = store._connection.execute("SELECT COUNT(*) AS n FROM node_versions").fetchone()["n"]
    forked = revision.forked_to("55555555-5555-5555-8555-555555555555")
    store.commit_revision(forked, created_at=NOW)
    after = store._connection.execute("SELECT COUNT(*) AS n FROM node_versions").fetchone()["n"]
    assert after == before


def test_head_follows_the_latest_revision_on_a_branch(
    store: SqliteStore, revision: Revision
) -> None:
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    edited = revision.replacing([revision.node("scene-1").with_content("Later.")])
    store.commit_revision(edited, created_at="2026-08-12T00:01:00Z")
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == edited.revision_id
    assert store.lineage(edited.revision_id) == [edited.revision_id, revision.revision_id]


# --- patch + commit end to end ----------------------------------------------------


def test_patch_commit_and_reload_preserves_untouched_text(
    store: SqliteStore, revision: Revision
) -> None:
    store.commit_revision(revision, created_at=NOW)
    original = revision.node("scene-6").content
    assert original is not None

    outcome = apply_patch(revision, build_patch(revision, "scene-6", [(0, 3, "That")]))
    assert outcome.accepted and outcome.revision is not None
    store.commit_revision(
        outcome.revision, created_at=NOW, events=[accepted_event(outcome.revision)]
    )

    reloaded = store.load_revision(outcome.revision.revision_id)
    assert reloaded.node("scene-6").content == "That" + original[3:]
    assert reloaded.node("scene-1").content == revision.node("scene-1").content


def test_a_vetoed_patch_leaves_storage_untouched(store: SqliteStore, revision: Revision) -> None:
    store.commit_revision(revision, created_at=NOW)
    outcome = apply_patch(revision, build_patch(revision, "scene-1", [(0, 10, "A"), (5, 15, "B")]))
    assert not outcome.accepted
    assert store.head(BOOK_ID, BRANCH_ID) is not None
    assert store.head(BOOK_ID, BRANCH_ID).revision_id == revision.revision_id  # type: ignore[union-attr]
    assert store._connection.execute("SELECT COUNT(*) AS n FROM revisions").fetchone()["n"] == 1


# --- events and the outbox --------------------------------------------------------


def test_events_commit_atomically_with_their_revision(
    store: SqliteStore, revision: Revision
) -> None:
    store.commit_revision(revision, created_at=NOW, events=[accepted_event(revision)])
    log = store.read_log()
    assert len(log) == 1
    assert log[0].event.revision_id == revision.revision_id
    assert len(store.pending_outbox()) == 1


def test_duplicate_event_delivery_is_idempotent(store: SqliteStore, revision: Revision) -> None:
    """Same logical event twice: one row, because the key is content-derived."""
    event = accepted_event(revision)
    store.commit_revision(revision, created_at=NOW, events=[event])
    store.append_events([event])
    assert len(store.read_log()) == 1


def test_out_of_order_delivery_still_yields_one_row_each(
    store: SqliteStore, revision: Revision
) -> None:
    first = accepted_event(revision, note="a")
    second = accepted_event(revision, note="b")
    store.append_events([second, first, second])
    assert len({item.event.idempotency_key for item in store.read_log()}) == 2


def test_redelivery_after_dispatch_does_not_requeue_the_outbox(
    store: SqliteStore, revision: Revision
) -> None:
    """The send-then-mark hazard: a duplicate must not resurrect a dispatched event."""
    event = accepted_event(revision)
    store.append_events([event])
    store.mark_sent(event.idempotency_key)
    assert store.pending_outbox() == []
    store.append_events([event])
    assert store.pending_outbox() == [], "a duplicate event re-opened a delivered outbox row"


def test_outbox_is_drained_in_log_order(store: SqliteStore, revision: Revision) -> None:
    events = [accepted_event(revision, note=str(index)) for index in range(5)]
    store.append_events(events)
    pending = store.pending_outbox()
    assert [entry.event.payload["note"] for entry in pending] == ["0", "1", "2", "3", "4"]
    for entry in pending:
        store.mark_sent(entry.idempotency_key)
    assert store.pending_outbox() == []


def test_an_undelivered_event_stays_pending(store: SqliteStore, revision: Revision) -> None:
    event = accepted_event(revision)
    store.append_events([event])
    store.record_delivery_attempt(event.idempotency_key, now=0.0)
    pending = store.pending_outbox()
    assert len(pending) == 1
    assert pending[0].state is OutboxState.PENDING
    assert pending[0].delivery_attempts == 1


# --- jobs and leases --------------------------------------------------------------


def test_job_status_machine_refuses_an_illegal_transition() -> None:
    job = Job(job_id="j1", job_kind="draft_scene")
    with pytest.raises(IllegalTransition):
        job.transition_to(JobStatus.SUCCEEDED)
    running = job.transition_to(JobStatus.RUNNING)
    assert running.attempts == 1
    assert running.transition_to(JobStatus.SUCCEEDED).status.is_terminal


def test_repeated_failure_poisons_rather_than_spinning() -> None:
    """§4.2's requirement: the failure mode is a parked unit, never a spin loop."""
    job = Job(job_id="j1", job_kind="draft_scene", max_attempts=2)
    job = job.transition_to(JobStatus.RUNNING).fail("boom")
    assert job.status is JobStatus.FAILED
    job = job.transition_to(JobStatus.QUEUED).transition_to(JobStatus.RUNNING).fail("boom again")
    assert job.status is JobStatus.POISONED
    assert job.lease_holder is None


def test_only_one_holder_can_claim_a_job(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="tick"))
    first = store.claim_next("worker-a", now=100.0, duration=60.0)
    assert first is not None and first.lease_holder == "worker-a"
    assert store.claim_next("worker-b", now=100.0, duration=60.0) is None


def test_an_expired_lease_is_reclaimable(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="tick"))
    store.claim_next("worker-a", now=100.0, duration=60.0)
    assert store.claim_next("worker-b", now=120.0, duration=60.0) is None
    second = store.claim_next("worker-b", now=200.0, duration=60.0)
    assert second is not None and second.lease_holder == "worker-b"


def test_a_stale_holder_cannot_advance_a_job(store: SqliteStore) -> None:
    """Wall-clock expiry means a paused process may still believe it holds the lease."""
    store.enqueue(Job(job_id="j1", job_kind="tick"))
    claimed = store.claim_next("worker-a", now=100.0, duration=60.0)
    assert claimed is not None
    claimed.assert_held_by("worker-a", now=120.0)
    with pytest.raises(LeaseError):
        claimed.assert_held_by("worker-a", now=200.0)
    with pytest.raises(LeaseError):
        claimed.assert_held_by("worker-b", now=120.0)


def test_job_survives_a_round_trip(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="tick", input_digest="abc", idempotency_key="k"))
    claimed = store.claim_next("worker-a", now=10.0, duration=30.0)
    assert claimed is not None
    store.save_job(claimed.transition_to(JobStatus.RUNNING))
    reloaded = store.load_job("j1")
    assert reloaded.status is JobStatus.RUNNING
    assert reloaded.attempts == 1
    assert reloaded.lease_holder == "worker-a"
    assert reloaded.input_digest == "abc"


def test_enqueue_is_idempotent_on_job_id(store: SqliteStore) -> None:
    store.enqueue(Job(job_id="j1", job_kind="tick"))
    store.enqueue(Job(job_id="j1", job_kind="tick"))
    assert store._connection.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"] == 1


# --- restore and integrity --------------------------------------------------------


def test_restore_rebuilds_every_revision_from_canonical_records(
    store: SqliteStore, revision: Revision
) -> None:
    store.commit_revision(revision, created_at=NOW, events=[accepted_event(revision)])
    edited = revision.replacing([revision.node("scene-2").with_content("Changed.")])
    store.commit_revision(edited, created_at=NOW, events=[accepted_event(edited)])
    assert store.verify_integrity() == 2


def test_reopening_the_database_preserves_everything(tmp_path, revision: Revision) -> None:
    path = tmp_path / "restore.db"
    first = SqliteStore.open(path)
    first.commit_revision(revision, created_at=NOW, events=[accepted_event(revision)])
    first.close()

    second = SqliteStore.open(path)
    assert second.verify_integrity() == 1
    assert second.load_revision(revision.revision_id).rendered_text() == revision.rendered_text()
    assert len(second.read_log()) == 1


def test_tampered_content_is_caught_by_restore(store: SqliteStore, revision: Revision) -> None:
    """One altered character anywhere in storage must fail loudly, not read back quietly."""
    store.commit_revision(revision, created_at=NOW)
    store._connection.execute(
        "UPDATE node_versions SET content = content || ' tampered' WHERE logical_id = 'scene-1'"
    )
    with pytest.raises(ValueError):
        store.verify_integrity()


def test_a_reordered_node_changes_the_revision_id_and_is_caught(
    store: SqliteStore, revision: Revision
) -> None:
    store.commit_revision(revision, created_at=NOW)
    store._connection.execute(
        "UPDATE node_versions SET position_key = '999' WHERE logical_id = 'scene-2'"
    )
    with pytest.raises(IntegrityFailure):
        store.verify_integrity()


def test_foreign_keys_are_enforced(store: SqliteStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute(
            "INSERT INTO revision_nodes (revision_id, logical_id, version_id) "
            "VALUES ('ghost', 'x', 'y')"
        )


def test_a_rolled_back_transaction_leaves_no_partial_state(
    store: SqliteStore, revision: Revision
) -> None:
    """The mid-write crash: at most the in-flight unit is lost, never half of it."""
    with pytest.raises(sqlite3.IntegrityError), store.transaction() as connection:
        connection.execute(
            "INSERT INTO revisions (revision_id, book_id, branch_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (revision.revision_id, BOOK_ID, BRANCH_ID, NOW),
        )
        connection.execute(
            "INSERT INTO revision_nodes (revision_id, logical_id, version_id) "
            "VALUES (?, 'scene-1', 'missing-version')",
            (revision.revision_id,),
        )
    assert store._connection.execute("SELECT COUNT(*) AS n FROM revisions").fetchone()["n"] == 0
    assert store.verify_integrity() == 0


# --- backup and restore (§19 Recovery, §18 "kept absolutely") ------------------------


def test_backup_captures_data_still_in_the_wal(tmp_path) -> None:
    """The reason a backup here cannot be a file copy.

    In WAL mode committed data lives partly in the `-wal` sidecar until a checkpoint, so
    copying the main database file — the obvious thing a cron job would do — silently omits
    everything committed since the last one. This asserts the backup sees a revision that
    was committed moments earlier and never checkpointed.
    """
    store = SqliteStore.open(tmp_path / "live.db")
    revision = make_revision()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")

    store.backup_to(tmp_path / "backup.db")

    restored = SqliteStore.open(tmp_path / "backup.db")
    assert restored.load_revision(revision.revision_id).revision_id == revision.revision_id
    assert restored.verify_integrity() == 1


def test_backup_refuses_to_overwrite_or_target_the_live_database(tmp_path) -> None:
    """The two mistakes that make a backup worthless."""
    store = SqliteStore.open(tmp_path / "live.db")
    with pytest.raises(ValueError, match="must differ"):
        store.backup_to(tmp_path / "live.db")
    (tmp_path / "taken.db").write_bytes(b"")
    with pytest.raises(FileExistsError):
        store.backup_to(tmp_path / "taken.db")


def test_a_destroyed_database_restores_from_backup_with_everything_intact(tmp_path) -> None:
    """The drill §19 Recovery actually asks for: not "a file exists" but "the system comes
    back". Prose, the policy decision that accepted it, and the undelivered outbox all have
    to survive — a restore that returns the manuscript and loses the audit trail or the
    pending events has not restored the system."""
    live = tmp_path / "live.db"
    store = SqliteStore.open(live)
    revision = make_revision()
    event = Event(
        event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
        project_id=PROJECT_ID,
        created_at="2026-08-12T00:00:00Z",
        revision_id=revision.revision_id,
        payload={"decision_id": "dec-1"},
    )
    store.commit_revision(revision, created_at=event.created_at, events=[event])
    store.record_decision(
        PolicyDecision(
            decision_id="dec-1",
            outcome=Outcome.ACCEPT,
            job_id="draft-1",
            resulting_revision_id=revision.revision_id,
        ),
        decided_at="2026-08-12T00:00:00Z",
    )
    pending_before = [entry.idempotency_key for entry in store.pending_outbox()]
    assert pending_before

    store.backup_to(tmp_path / "backup.db")
    store.close()

    # Destroy the primary the way corruption actually presents: readable file, junk inside.
    for sidecar in (live.with_name(live.name + "-wal"), live.with_name(live.name + "-shm")):
        sidecar.unlink(missing_ok=True)
    live.write_bytes(b"this is not a database" * 64)
    corrupt = None
    try:
        with pytest.raises(sqlite3.DatabaseError):
            corrupt = SqliteStore.open(live)
            corrupt.verify_integrity()
    finally:
        if corrupt is not None:
            corrupt.close()

    live.unlink()
    shutil.copy(tmp_path / "backup.db", live)
    recovered = SqliteStore.open(live)

    assert recovered.verify_integrity() == 1
    assert recovered.load_revision(revision.revision_id).node("scene-1").content == SCENES[0]
    decision = recovered.decision_for_revision(revision.revision_id)
    assert decision is not None and decision.outcome is Outcome.ACCEPT
    assert [entry.idempotency_key for entry in recovered.pending_outbox()] == pending_before


# --- failure surfaces ----------------------------------------------------------------


def test_an_empty_migration_set_is_fatal_rather_than_a_silent_empty_schema(tmp_path) -> None:
    """The failure this replaces was the dangerous kind: `migrate` returned cleanly, `open`
    handed back a store with no tables, and the first write failed far from the cause. On a
    restored host it would have looked like data loss."""
    empty = tmp_path / "no-migrations"
    empty.mkdir()
    with pytest.raises(MigrationsMissing, match=r"no \.sql migrations"):
        SqliteStore.open(tmp_path / "x.db", migrations=empty)


def test_the_packaged_migrations_are_discoverable(tmp_path) -> None:
    """`migrations_dir()` must resolve under the install layout in play. The previous
    hardcoded repo-root path resolved to nothing once installed from a wheel."""
    resolved = migrations_dir()
    assert sorted(p.name for p in resolved.glob("*.sql"))[0] == "001_initial.sql"


def test_a_storage_error_is_not_masked_by_its_own_rollback(tmp_path) -> None:
    """A full disk used to report "cannot rollback - no transaction is active".

    SQLite auto-rolls-back on SQLITE_FULL, so the explicit ROLLBACK in `__exit__` raised
    and replaced the real exception on the way out — the operator was told the rollback
    failed and never told the disk was full. Simulated here with a page cap.
    """
    store = SqliteStore.open(tmp_path / "full.db")
    store._connection.execute("PRAGMA max_page_count=64")
    with pytest.raises(sqlite3.OperationalError) as caught:
        for index in range(200):
            store.enqueue(Job(job_id=f"j-{index}", job_kind="noop", payload={"pad": "x" * 4000}))
    assert "cannot rollback" not in str(caught.value)
    assert "full" in str(caught.value).lower()


# --- reversibility (§19 Integrity, second half) --------------------------------------


def test_the_head_is_a_stored_pointer_not_the_newest_timestamp(
    store: SqliteStore, revision: Revision
) -> None:
    """Inferring the head by `created_at` made reverting inexpressible — a revision
    restoring older content would carry an older timestamp and therefore not be the head —
    and made branch state depend on a clock, with ties broken by content hash."""
    store.commit_revision(revision, created_at="2026-08-12T00:05:00Z")
    edited = revision.replacing([revision.node("scene-1").with_content("Later.")])
    # Deliberately an *earlier* stamp than its parent.
    store.commit_revision(edited, created_at="2026-08-12T00:00:00Z")

    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.revision_id == edited.revision_id


def test_revert_restores_content_by_going_forward(
    store: SqliteStore, revision: Revision
) -> None:
    """History is immutable and content-addressed, so undo cannot mean deletion: every
    span citing the bad revision would become unresolvable and the record would lose the
    fact that it ever existed."""
    store.commit_revision(revision, created_at=NOW)
    original = revision.node("scene-1").content
    bad = revision.replacing([revision.node("scene-1").with_content("A regrettable line.")])
    store.commit_revision(bad, created_at="2026-08-12T00:01:00Z")

    reverted = store.revert(
        BOOK_ID,
        BRANCH_ID,
        revision.revision_id,
        created_at="2026-08-12T00:02:00Z",
        project_id=PROJECT_ID,
    )

    assert reverted.node("scene-1").content == original
    assert store.head(BOOK_ID, BRANCH_ID).revision_id == reverted.revision_id  # type: ignore[union-attr]
    # Both the mistake and the correction survive — that is what "forward" buys.
    assert store.load_revision(bad.revision_id).node("scene-1").content == "A regrettable line."
    assert store.lineage(reverted.revision_id)[:3] == [
        reverted.revision_id,
        bad.revision_id,
        revision.revision_id,
    ]


def test_revert_stores_no_new_node_versions(store: SqliteStore, revision: Revision) -> None:
    """Free in storage: node versions are content addresses, so restoring old content
    inserts no new node rows."""
    store.commit_revision(revision, created_at=NOW)
    bad = revision.replacing([revision.node("scene-1").with_content("A regrettable line.")])
    store.commit_revision(bad, created_at="2026-08-12T00:01:00Z")
    before = store._connection.execute("SELECT COUNT(*) AS n FROM node_versions").fetchone()["n"]

    store.revert(
        BOOK_ID,
        BRANCH_ID,
        revision.revision_id,
        created_at="2026-08-12T00:02:00Z",
        project_id=PROJECT_ID,
    )

    after = store._connection.execute("SELECT COUNT(*) AS n FROM node_versions").fetchone()["n"]
    assert after == before


def test_a_node_added_after_the_target_is_tombstoned_not_dropped(
    store: SqliteStore, revision: Revision
) -> None:
    """A revision that dropped a node would make its predecessor unreconstructible and
    break the restore guarantee."""
    from litharness.domain.nodes import Node, NodeKind

    store.commit_revision(revision, created_at=NOW)
    added = Revision(
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        nodes=(
            *revision.nodes,
            Node.text_node("scene-7", NodeKind.SCENE, "070", "Extra.", parent_logical_id="book"),
        ),
        parent_revision_id=revision.revision_id,
    )
    store.commit_revision(added, created_at="2026-08-12T00:01:00Z")

    reverted = store.revert(
        BOOK_ID,
        BRANCH_ID,
        revision.revision_id,
        created_at="2026-08-12T00:02:00Z",
        project_id=PROJECT_ID,
    )

    assert reverted.node("scene-7").tombstoned
    assert "scene-7" not in [node.logical_id for node in reverted.children_of("book")]
    assert store.verify_integrity() == 3


def test_reverting_is_itself_reversible(store: SqliteStore, revision: Revision) -> None:
    """Forward-only history means undo composes: reverting the revert restores the change."""
    store.commit_revision(revision, created_at=NOW)
    bad = revision.replacing([revision.node("scene-1").with_content("A regrettable line.")])
    store.commit_revision(bad, created_at="2026-08-12T00:01:00Z")
    store.revert(
        BOOK_ID,
        BRANCH_ID,
        revision.revision_id,
        created_at="2026-08-12T00:02:00Z",
        project_id=PROJECT_ID,
    )

    again = store.revert(
        BOOK_ID,
        BRANCH_ID,
        bad.revision_id,
        created_at="2026-08-12T00:03:00Z",
        project_id=PROJECT_ID,
    )

    assert again.node("scene-1").content == "A regrettable line."


def test_a_revert_is_attributable_like_any_other_mutation(
    store: SqliteStore, revision: Revision
) -> None:
    """§19's Integrity clause is one sentence — attributable *and* reversible — and the
    reversibility half shipped violating the attribution half. A revert committed a
    revision, moved the head, and left `decision_for_revision` answering None. §17 Stage 1
    lists "zero silent mutation" as an exit criterion; this was the one.
    """
    store.commit_revision(revision, created_at=NOW, events=[accepted_event(revision)])
    bad = revision.replacing([revision.node("scene-1").with_content("A regrettable line.")])
    store.commit_revision(bad, created_at="2026-08-12T00:01:00Z", events=[accepted_event(bad)])

    reverted = store.revert(
        BOOK_ID,
        BRANCH_ID,
        revision.revision_id,
        created_at="2026-08-12T00:02:00Z",
        project_id=PROJECT_ID,
    )

    decision = store.decision_for_revision(reverted.revision_id)
    assert decision is not None, "a revert committed a revision nothing explains"
    assert decision.outcome is Outcome.ACCEPT
    assert decision.base_revision_id == bad.revision_id
    assert revision.revision_id[:12] in (decision.reason or "")
    # The log too, not only the decision table: derived state is rebuilt from events.
    accepted = [
        entry
        for entry in store.read_log()
        if entry.event.revision_id == reverted.revision_id
        and entry.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
    ]
    assert len(accepted) == 1
    assert accepted[0].event.payload["reverted_to"] == revision.revision_id


def test_reverting_twice_to_one_target_is_two_attributed_mutations(
    store: SqliteStore, revision: Revision
) -> None:
    """Worth pinning because the intuition goes the other way: reverting to the same target
    twice is *not* idempotent, because the head moved in between and a revision id covers
    its parent. Two forward moves, two revisions, two decisions — and the second is not a
    duplicate judgment of the first. Only a genuinely replayed revert, from the same head,
    collapses; that is what the derived decision id is for.
    """
    store.commit_revision(revision, created_at=NOW)
    bad = revision.replacing([revision.node("scene-1").with_content("A regrettable line.")])
    store.commit_revision(bad, created_at="2026-08-12T00:01:00Z")

    reverts = [
        store.revert(
            BOOK_ID, BRANCH_ID, revision.revision_id, created_at=stamp, project_id=PROJECT_ID
        )
        for stamp in ("2026-08-12T00:02:00Z", "2026-08-12T00:03:00Z")
    ]

    assert reverts[0].revision_id != reverts[1].revision_id
    assert reverts[1].parent_revision_id == reverts[0].revision_id
    decisions = [store.decision_for_revision(item.revision_id) for item in reverts]
    assert all(decision is not None for decision in decisions)
    assert decisions[0].decision_id != decisions[1].decision_id  # type: ignore[union-attr]


def test_unattributed_revisions_names_what_no_decision_explains(
    store: SqliteStore, revision: Revision
) -> None:
    """The check that makes the clause hold for paths nobody has written yet. A structural
    constraint on `revert` would only ever have guarded `revert`."""
    store.commit_revision(revision, created_at=NOW)  # the raw primitive, as a test does
    assert store.unattributed_revisions() == [revision.revision_id]

    reverted = store.revert(
        BOOK_ID,
        BRANCH_ID,
        revision.revision_id,
        created_at="2026-08-12T00:02:00Z",
        project_id=PROJECT_ID,
    )

    assert reverted.revision_id not in store.unattributed_revisions()
