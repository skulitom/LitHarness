"""Slice 5b: the direction inbox (§4.3), capture half only.

The tests that matter most here are the ones about what is *not* built. A directive is
captured durably and stops at RECEIVED because the Narrative Planner (§9) does not exist to
interpret it, and the honest failure mode for that is a visible queue of unread direction
rather than either silent dropping or an invented interpreter. Two tests pin exactly that,
so a later change that starts quietly interpreting has to argue with them first.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome, no_op_handler
from litharness.domain.directives import (
    Directive,
    DirectiveKind,
    DirectiveStatus,
    IllegalTransition,
    directive_id_for,
)
from litharness.domain.events import EventType
from litharness.domain.jobs import Job
from tests.conftest import PROJECT_ID

START = 1_760_000_000.0
STAMP = "2026-08-12T00:00:00Z"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "directives.db")


def conductor(store: SqliteStore, holder: str = "worker-a", **kwargs) -> Conductor:
    kwargs.setdefault("handlers", {"noop": no_op_handler})
    return Conductor(store=store, holder=holder, project_id=PROJECT_ID, **kwargs)


def directive(body: str, kind: DirectiveKind = DirectiveKind.TONE_NOTE) -> Directive:
    return Directive(
        directive_id=directive_id_for(kind, body, STAMP),
        kind=kind,
        body=body,
        received_at=STAMP,
    )


# --- capture -------------------------------------------------------------------------


def test_a_directive_survives_a_round_trip(store: SqliteStore) -> None:
    given = directive("More dungeon crawling, less court intrigue.")
    assert store.submit_directive(given, received_at=STAMP) is True
    assert store.load_directive(given.directive_id) == given


def test_submitting_the_same_directive_twice_collapses(store: SqliteStore) -> None:
    given = directive("More dungeon crawling.")
    assert store.submit_directive(given, received_at=STAMP) is True
    assert store.submit_directive(given, received_at=STAMP) is False
    assert len(store.pending_directives()) == 1


def test_the_same_words_at_a_later_time_are_a_second_directive() -> None:
    """A director who repeats an instruction next week means it again. Deduping on body
    alone would swallow the repetition, which is itself a signal."""
    first = directive_id_for(DirectiveKind.TONE_NOTE, "More dungeon crawling.", STAMP)
    later = directive_id_for(
        DirectiveKind.TONE_NOTE, "More dungeon crawling.", "2026-08-19T00:00:00Z"
    )
    assert first != later


def test_an_empty_directive_is_refused() -> None:
    with pytest.raises(ValueError, match="empty body"):
        Directive(directive_id="d-1", kind=DirectiveKind.TONE_NOTE, body="   ")


# --- precedence ----------------------------------------------------------------------


def test_a_veto_outranks_an_earlier_tone_note(store: SqliteStore) -> None:
    """Arrival order must not decide conflicts. A refusal outranks a suggestion however
    late it arrives, so precedence leads the drain query and rowid only breaks ties."""
    store.submit_directive(directive("Warmer tone throughout."), received_at=STAMP)
    store.submit_directive(
        directive("Never kill the mentor.", DirectiveKind.VETO), received_at=STAMP
    )

    assert [d.kind for d in store.pending_directives()] == [
        DirectiveKind.VETO,
        DirectiveKind.TONE_NOTE,
    ]


def test_equal_precedence_drains_in_arrival_order(store: SqliteStore) -> None:
    for index in range(3):
        store.submit_directive(directive(f"Note {index}."), received_at=STAMP)
    assert [d.body for d in store.pending_directives()] == ["Note 0.", "Note 1.", "Note 2."]


def test_precedence_defaults_by_kind_and_can_be_overridden() -> None:
    assert directive("x", DirectiveKind.VETO).precedence == 100
    assert directive("x", DirectiveKind.TONE_NOTE).precedence == 10
    explicit = Directive(
        directive_id="d", kind=DirectiveKind.VETO, body="x", precedence=5
    )
    assert explicit.precedence == 5


# --- ingest at tick ------------------------------------------------------------------


def test_the_tick_drains_the_inbox_and_records_each_arrival(store: SqliteStore) -> None:
    store.submit_directive(directive("More dungeon crawling."), received_at=STAMP)

    result = conductor(store).tick(START)

    assert result.ingested == 1
    events = [entry.event for entry in store.read_log()]
    assert [event.event_type for event in events] == [EventType.DIRECTIVE_INGESTED]
    assert store.digest(events[0].created_at[:10])["directives_ingested"] == 1


def test_an_ingested_directive_is_not_drained_twice(store: SqliteStore) -> None:
    store.submit_directive(directive("More dungeon crawling."), received_at=STAMP)
    conductor(store).tick(START)
    assert conductor(store).tick(START + 300.0).ingested == 0
    assert store.pending_directives() == []


def test_ingest_runs_before_selection(store: SqliteStore) -> None:
    """§4.1's ordering, and the reason for it: a directive that arrived since the last
    tick must be able to influence what this tick picks up. If selection ran first the
    directive would sit unread for a full cycle behind the work it was meant to redirect.
    """
    seen: list[int] = []

    def selector(store_, holder, now, duration):
        seen.append(len(store_.pending_directives()))
        return store_.claim_next(holder, now=now, duration=duration)

    store.submit_directive(directive("More dungeon crawling."), received_at=STAMP)
    store.enqueue(Job(job_id="noop-1", job_kind="noop"))

    conductor(store, select=selector).tick(START)

    # Zero pending by the time selection ran: the inbox was already drained.
    assert seen == [0]


def test_a_non_leader_tick_does_not_touch_the_inbox(store: SqliteStore) -> None:
    """Ingest mutates shared state, so it sits inside the leadership guard with everything
    else. Two overlapping cron ticks must not both drain."""
    store.submit_directive(directive("More dungeon crawling."), received_at=STAMP)
    conductor(store, holder="leader").tick(START)

    follower = Conductor(store=store, holder="follower", project_id=PROJECT_ID)
    result = follower.tick(START + 1.0)

    assert result.outcome is TickOutcome.NOT_LEADER
    assert result.ingested == 0


def test_a_no_op_tick_with_an_empty_inbox_stays_a_no_op(store: SqliteStore) -> None:
    """The endurance property: ingest must not add per-tick state growth when there is
    nothing to ingest."""
    result = conductor(store).tick(START)
    assert result.outcome is TickOutcome.NO_WORK
    assert result.ingested == 0
    assert store.read_log() == []


# --- what is deliberately not built --------------------------------------------------


def test_an_ingested_directive_stays_uninterpreted(store: SqliteStore) -> None:
    """The Narrative Planner (§9) does not exist, so nothing may claim to have understood
    a directive. An interpretation invented here would be worse than none: it would look
    like the system had acted on direction it had merely filed."""
    store.submit_directive(directive("More dungeon crawling."), received_at=STAMP)
    conductor(store).tick(START)

    [received] = store.directives_by_status(DirectiveStatus.RECEIVED)
    assert received.interpretation is None
    assert received.produced_constraint_ids == ()
    assert store.directives_by_status(DirectiveStatus.INTERPRETED) == []


def test_the_ingest_event_says_what_it_is_waiting_for(store: SqliteStore) -> None:
    """Unread direction must read as unread in the log, not as handled."""
    store.submit_directive(directive("More dungeon crawling."), received_at=STAMP)
    conductor(store).tick(START)

    payload = store.read_log()[0].event.payload
    assert payload["interpreted"] is False
    assert payload["awaiting"] == "narrative_planner"


def test_interpret_is_the_only_way_out_of_received() -> None:
    """The seam the planner will attach to, so it inherits one transition rather than a
    schema to negotiate."""
    given = directive("More dungeon crawling.")
    read = given.interpret(
        "Increase dungeon beats per arc.", at=STAMP, constraint_ids=("c-1",)
    )

    assert read.status is DirectiveStatus.INTERPRETED
    assert read.interpretation == "Increase dungeon beats per arc."
    assert read.produced_constraint_ids == ("c-1",)
    # The director's words are never rewritten by the reading.
    assert read.body == given.body


def test_an_illegal_transition_raises() -> None:
    given = directive("More dungeon crawling.")
    with pytest.raises(IllegalTransition):
        given.transition_to(DirectiveStatus.APPLIED)
