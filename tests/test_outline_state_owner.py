"""Outline state and its resulting milestones belong to the same identified actor."""

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.outline import make_outline_handler
from litharness.domain import worlds
from litharness.domain.beats import arc_template, beats_for
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.helpers import accepted
from tests.test_outline import SEED, START, StubPlanner, _job, a_book, with_schedule


@pytest.fixture
def store(tmp_path):
    with SqliteStore.open(tmp_path / "book.db") as opened:
        yield opened


@pytest.mark.parametrize("protagonist,owners,expected", [
    ("hero", ("hero", "rival"), "hero"),
    ("hero", ("rival", "hero"), "hero"),
    ("hero", ("rival",), None),
    (None, ("hero", "rival"), None),
    (None, ("hero",), "hero"),
])
def test_request_and_persisted_milestones_never_borrow_another_actors_sheet(
    store, protagonist, owners, expected,
):
    a_book(store, scenes=6, sheet=False)
    records = []
    if protagonist:
        records.append(accepted(worlds.world_record(
            protagonist, worlds.ENTITY_ROLE_PREDICATE, value="protagonist",
        )))
    for owner in owners:
        records.append(accepted(worlds.world_record(
            owner, "status_snapshot", value={**SEED, "level": 1 if owner == "hero" else 9},
        )))
    store.record_state_records(BOOK_ID, BRANCH_ID, records, created_at=START)
    model = StubPlanner(with_schedule(6))
    make_outline_handler(model, store, PROJECT_ID)(_job(store), START)
    body = json.loads(model.requests[0].prompt)
    assert body["starting_state"] == (SEED if expected else None)
    assert body.get("starting_state_subject") == expected
    milestones = [r for r in store.state_records(BOOK_ID, BRANCH_ID)
                  if r.record_id.startswith("milestone-")]
    assert {r.subject for r in milestones} == ({expected} if expected else set())


def test_owner_selection_still_excludes_future_and_proposed_snapshots(store):
    revision = a_book(store, scenes=6, sheet=False)
    beats = beats_for(revision, arc_template(6))
    records = [accepted(worlds.world_record(
        "hero", worlds.ENTITY_ROLE_PREDICATE, value="protagonist",
    ))]
    for identity, owner, value, authority, key in [
        ("entry", "hero", SEED, lc.StateAuthority.ACCEPTED_CANON, None),
        ("rival", "rival", {**SEED, "level": 9}, lc.StateAuthority.ACCEPTED_CANON, None),
        ("future", "hero", {**SEED, "level": 7}, lc.StateAuthority.ACCEPTED_CANON,
         beats[-1].story_order_key),
        ("proposal", "hero", {**SEED, "level": 8}, lc.StateAuthority.PROPOSED, None),
    ]:
        records.append(lc.StateRecord(
            record_id=identity, subject=owner, predicate="status_snapshot", value=value,
            kind=lc.StateRecordKind.ASSERTION, authority=authority,
            story_position=lc.StoryPosition(order_key=key) if key else None,
        ))
    store.record_state_records(BOOK_ID, BRANCH_ID, records, created_at=START)
    model = StubPlanner(with_schedule(6))
    make_outline_handler(model, store, PROJECT_ID)(_job(store), START)
    body = json.loads(model.requests[0].prompt)
    assert body["starting_state"] == SEED
    assert body["starting_state_subject"] == "hero"
