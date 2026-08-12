"""The exception queue (§4.3, §19 Autonomy).

The ESCALATE branch already emitted `EXCEPTION_RAISED`, and an event is a fact in a log
rather than a queue: answering "what is waiting for me" meant replaying the event stream
and reconstructing which escalations had since been resolved. These tests assert the
queue exists, is idempotent under replay, and keeps resolution separate from requeueing.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import status as status_module
from litharness.domain.exceptions import (
    ExceptionKind,
    ExceptionRecord,
    ExceptionStatus,
    exception_id_for,
)
from litharness.domain.jobs import JobStatus
from tests.test_draft import PROSE, START, conductor_for, registry_with, seeded_with_prose


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "exceptions.db")


def sample(job_id: str = "draft-1") -> ExceptionRecord:
    return ExceptionRecord(
        exception_id=exception_id_for(job_id, ExceptionKind.CONSTRAINT_CONFLICT, "dec-1"),
        kind=ExceptionKind.CONSTRAINT_CONFLICT,
        summary="two locked constraints cannot both be satisfied",
        job_id=job_id,
        decision_id="dec-1",
        raised_at="2026-08-12T00:00:00Z",
    )


# --- the queue -----------------------------------------------------------------------


def test_an_exception_round_trips(store: SqliteStore) -> None:
    record = sample()
    assert store.raise_exception(record) is True
    assert store.load_exception(record.exception_id) == record


def test_raising_the_same_escalation_twice_yields_one_exception(store: SqliteStore) -> None:
    """Content-derived ids. A replayed tick must not build a queue of identical entries,
    which would be the fastest way to make the queue useless."""
    record = sample()
    assert store.raise_exception(record) is True
    assert store.raise_exception(record) is False
    assert len(store.open_exceptions()) == 1


def test_resolving_closes_it_and_removes_it_from_the_queue(store: SqliteStore) -> None:
    record = sample()
    store.raise_exception(record)

    closed = store.resolve_exception(
        record.exception_id, "unlocked the node", at="2026-08-12T01:00:00Z"
    )

    assert closed.status is ExceptionStatus.RESOLVED
    assert closed.resolution == "unlocked the node"
    assert store.open_exceptions() == []


def test_dismissing_records_that_the_escalation_was_right(store: SqliteStore) -> None:
    """"I looked and did nothing" has to be a recordable answer rather than an absence,
    or the queue cannot distinguish it from an unread one."""
    record = sample()
    store.raise_exception(record)

    closed = store.resolve_exception(
        record.exception_id,
        "the lock is correct; this scene stays as written",
        at="2026-08-12T01:00:00Z",
        status=ExceptionStatus.DISMISSED,
    )

    assert closed.status is ExceptionStatus.DISMISSED
    assert store.open_exceptions() == []


def test_acknowledged_exceptions_stay_in_the_queue(store: SqliteStore) -> None:
    """Acknowledged means seen, not handled. Dropping it from the queue would lose the
    unit the moment someone glanced at it."""
    store.raise_exception(sample())
    assert ExceptionStatus.ACKNOWLEDGED.is_open


# --- raised by the loop --------------------------------------------------------------


def test_an_escalated_unit_lands_in_the_queue(store: SqliteStore) -> None:
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)

    conductor_for(store, registry).tick(START)

    [raised] = store.open_exceptions()
    assert raised.job_id == "draft-1"
    assert raised.kind is ExceptionKind.REPEATED_GATE_FAILURE
    assert "target_has_no_content" in raised.summary
    # Bound to the decision that produced it, so the gate trail is one hop away rather
    # than a join the human does by hand.
    assert raised.decision_id is not None
    assert store.load_decision(raised.decision_id).job_id == "draft-1"


def test_resolving_an_exception_does_not_restart_the_work(store: SqliteStore) -> None:
    """Two separate acts on purpose. A director may decide the escalation was correct and
    the unit should stay stopped; collapsing them makes that inexpressible."""
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)
    conductor_for(store, registry).tick(START)
    [raised] = store.open_exceptions()

    store.resolve_exception(raised.exception_id, "reviewed", at="2026-08-12T01:00:00Z")

    assert store.load_job("draft-1").status is JobStatus.PARKED
    assert store.open_exceptions() == []

    store.revive("draft-1")
    assert store.load_job("draft-1").status is JobStatus.QUEUED


def test_open_exceptions_count_toward_needs_attention(store: SqliteStore) -> None:
    """§19 Autonomy pairs parked units *and* exceptions; the operator surface has to
    count both or a resolved-but-still-parked unit looks like nothing is wrong."""
    registry, _ = registry_with(PROSE)
    seeded_with_prose(store)
    conductor_for(store, registry).tick(START)

    report = status_module.collect(store, START + 1.0)
    assert report.open_exceptions == 1
    assert report.needs_attention >= 2  # the parked job and its exception
