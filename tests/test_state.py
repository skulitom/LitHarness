"""The objective-story-state layer: import, visibility, ordering, and the store round trip."""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import fixture_state
from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain import state as state_mod
from litharness.domain.draft import gate_draft
from litharness.domain.events import Event, EventType
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import build_revision
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID


def load_state(fixture_id: str) -> lc.StateSnapshot:
    return lc.parse_artifact(
        lc.StateSnapshot, json.loads(fixture_state(fixture_id).read_text(encoding="utf-8"))
    )


def record(
    record_id: str,
    *,
    kind: lc.StateRecordKind = lc.StateRecordKind.ASSERTION,
    subject: str = "subject",
    predicate: str = "predicate",
    value: object = "value",
    order_key: str | None = "s1",
    authority: lc.StateAuthority = lc.StateAuthority.ACCEPTED_CANON,
    pov_visibility: list[str] | None = None,
) -> lc.StateRecord:
    return lc.StateRecord(
        record_id=record_id,
        kind=kind,
        subject=subject,
        predicate=predicate,
        value=value,
        story_position=lc.StoryPosition(order_key=order_key) if order_key else None,
        authority=authority,
        pov_visibility=list(pov_visibility or []),
    )


# -- import ------------------------------------------------------------------------------


def test_import_reanchors_on_the_local_book_and_keeps_the_upstream_id() -> None:
    """The third artifact to make the same decision plans and manuscripts already make.

    A contracts snapshot pins `revision_id` to the upstream UUID5, which by construction is
    never the sha256 address this package mints. Matching records to a manuscript by that
    field would therefore never succeed.
    """
    snapshot = load_state("mystery")
    imported = state_mod.import_state(snapshot, book_id=BOOK_ID, branch_id=BRANCH_ID)

    assert imported.book_id == BOOK_ID
    assert imported.branch_id == BRANCH_ID
    assert imported.source_revision_id == snapshot.revision_id
    assert imported.source_revision_id != BOOK_ID
    assert len(imported.records) == 16


# -- visibility --------------------------------------------------------------------------


def test_an_unrestricted_record_is_visible_to_everyone_including_no_one() -> None:
    objective = record("rec", pov_visibility=[])
    assert state_mod.visible_to(objective, "mara")
    assert state_mod.visible_to(objective, None)


def test_a_restricted_record_reaches_only_the_characters_it_names() -> None:
    private = record("rec", pov_visibility=["brandt"])
    assert state_mod.visible_to(private, "brandt")
    assert not state_mod.visible_to(private, "mara")


def test_an_absent_pov_does_not_satisfy_a_restriction() -> None:
    """The golden suite settles this, and it settles it in the safe direction.

    `q3-repair-bruno` forbids `rec-brandt-knows-letter` in a case whose query names **no**
    POV at all. So "no POV" cannot mean "no restriction applies" — if it did, forgetting to
    pass the POV would mean leaking every private fact in the book, and nothing downstream
    could tell that had happened.
    """
    assert not state_mod.visible_to(record("rec", pov_visibility=["brandt"]), None)


def test_the_fixtures_private_record_is_exactly_the_one_the_gold_suite_forbids() -> None:
    records = load_state("mystery").records
    restricted = {
        item.record_id: tuple(item.pov_visibility) for item in records if item.pov_visibility
    }
    assert restricted == {
        "rec-brandt-knows-letter": ("brandt",),
        "rec-mara-knows-floorboard": ("mara", "brandt"),
    }
    by_id = {item.record_id: item for item in records}
    # Drafting scene 6 from Mara's POV: she knows the floorboard, not the letter.
    assert state_mod.visible_to(by_id["rec-mara-knows-floorboard"], "mara")
    assert not state_mod.visible_to(by_id["rec-brandt-knows-letter"], "mara")


# -- canon -------------------------------------------------------------------------------


def test_a_proposal_is_not_canon() -> None:
    """§11: no proposal becomes canon merely because a model returned it."""
    assert state_mod.is_canon(record("a", authority=lc.StateAuthority.ACCEPTED_CANON))
    assert state_mod.is_canon(record("b", authority=lc.StateAuthority.AUTHOR_LOCKED))
    assert not state_mod.is_canon(record("c", authority=lc.StateAuthority.PROPOSED))
    assert not state_mod.is_canon(record("d", authority=lc.StateAuthority.DERIVED))


def test_every_fixture_record_is_canon() -> None:
    """Both fixtures ship established facts, not proposals. If that ever stops being true
    the packet tests silently start measuring a filter instead of an assembler."""
    for fixture_id in ("mystery", "litrpg"):
        assert all(state_mod.is_canon(item) for item in load_state(fixture_id).records)


# -- ordering and slicing ------------------------------------------------------------------


def test_records_are_ordered_by_story_position_with_unplaced_ones_last() -> None:
    ordered = state_mod.in_story_order(
        [
            record("c", order_key="s2"),
            record("a", order_key=None),
            record("b", order_key="s1"),
        ]
    )
    assert [item.record_id for item in ordered] == ["b", "c", "a"]


def test_records_at_the_same_position_break_ties_on_id_so_packing_is_reproducible() -> None:
    ordered = state_mod.in_story_order(
        [record("z", order_key="s1"), record("a", order_key="s1")]
    )
    assert [item.record_id for item in ordered] == ["a", "z"]


def test_a_cutoff_keeps_unplaced_records_rather_than_dropping_them() -> None:
    """An unplaced record asserts no narrative position. Treating that as "later than
    everything" would drop every standing world rule from every packet."""
    kept = state_mod.records_before(
        [
            record("early", order_key="s1"),
            record("late", order_key="s9"),
            record("rule", order_key=None),
        ],
        "s2",
    )
    assert {item.record_id for item in kept} == {"early", "rule"}


def test_no_cutoff_returns_everything() -> None:
    records = [record("a", order_key="s1"), record("b", order_key="s9")]
    assert state_mod.records_before(records, None) == tuple(records)


def test_open_threads_finds_the_promise_the_book_owes() -> None:
    threads = state_mod.open_threads(load_state("mystery").records)
    assert [item.record_id for item in threads] == ["rec-letter-promise"]


def test_a_resolved_thread_is_not_open() -> None:
    threads = state_mod.open_threads(
        [
            record("open", kind=lc.StateRecordKind.THREAD, value="open"),
            record("paid", kind=lc.StateRecordKind.THREAD, value="resolved"),
        ]
    )
    assert [item.record_id for item in threads] == ["open"]


# -- the kind mapping ---------------------------------------------------------------------


def test_an_event_record_is_referenced_as_a_state_event_resource() -> None:
    """`StateRecordKind` and `ResourceKind` are not the same vocabulary, and this is the one
    member where they differ. `ResourceKind(record.kind.value)` would raise here and work
    everywhere else — a bug that looks like it works, and the golden suite names this exact
    resource kind for `rec-julian-at-house`."""
    assert state_mod.resource_kind(record("e", kind=lc.StateRecordKind.EVENT)) is (
        lc.ResourceKind.STATE_EVENT
    )
    with pytest.raises(ValueError):
        lc.ResourceKind(lc.StateRecordKind.EVENT.value)


def test_every_state_record_kind_has_a_resource_kind() -> None:
    """A member added upstream without a mapping would silently become UNKNOWN, and a packet
    item with an UNKNOWN source kind matches no golden target."""
    assert set(state_mod.RESOURCE_KIND) == set(lc.StateRecordKind)


# -- rendering ----------------------------------------------------------------------------


def test_a_dict_value_renders_deterministically() -> None:
    described = state_mod.describe(
        record("e", subject="julian", predicate="present_at",
               value={"when": "night_of_death", "place": "vane_house"})
    )
    # Sorted by key, so two runs produce one string and the packet's token count is stable.
    assert described == "julian present_at place=vane_house, when=night_of_death"


def test_describe_states_the_record_and_invents_no_prose() -> None:
    """A renderer that wrote "Mara knows that the key is hidden under the floorboard" would
    put a sentence into the packet that the record does not contain, and the generator would
    be free to echo that phrasing back as though it were the book's."""
    records = {item.record_id: item for item in load_state("mystery").records}
    assert state_mod.describe(records["rec-key-opens-vault"]) == "brass_key opens west_vault"
    assert state_mod.describe(records["rec-edmund-dead"]) == "edmund life_status dead"


# -- the store ----------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "litharness.db")


def test_records_round_trip_through_the_store(store: SqliteStore) -> None:
    source = load_state("mystery")
    written = store.record_state_records(
        BOOK_ID, BRANCH_ID, source.records, created_at="2026-08-13T00:00:00Z"
    )
    assert written == 16

    loaded = store.state_records(BOOK_ID, BRANCH_ID)
    assert len(loaded) == 16
    by_id = {item.record_id: item for item in loaded}
    # The two fields the table does not have columns for, proving `record_json` carries the
    # whole artifact rather than the columns being the record.
    assert by_id["rec-brandt-knows-letter"].pov_visibility == ["brandt"]
    assert by_id["rec-edmund-dead"].evidence[0].start == 239
    # A dict value survives the JSON column round trip as a dict, not as its repr.
    assert by_id["rec-key-discovered"].value == {
        "item": "brass_key",
        "location": "under_floorboard",
    }


def test_reimporting_the_same_snapshot_writes_nothing(store: SqliteStore) -> None:
    source = load_state("mystery")
    store.record_state_records(BOOK_ID, BRANCH_ID, source.records, created_at="t")
    assert store.record_state_records(BOOK_ID, BRANCH_ID, source.records, created_at="t") == 0
    assert len(store.state_records(BOOK_ID, BRANCH_ID)) == 16


def test_the_store_and_the_domain_slice_story_time_identically(store: SqliteStore) -> None:
    """One query, two implementations is how a selector drifts from its gate — the lesson
    `draft_block` records. `records_before` and the `before` argument answer the same
    question, including the awkward half of it: unplaced records survive a cutoff."""
    records = [
        record("early", order_key="s1"),
        record("late", order_key="s9"),
        record("unplaced", order_key=None),
    ]
    store.record_state_records(BOOK_ID, BRANCH_ID, records, created_at="t")
    for cutoff in (None, "s0", "s1", "s2", "s9"):
        stored = store.state_records(BOOK_ID, BRANCH_ID, before=cutoff)
        from_store = {item.record_id for item in stored}
        in_memory = {item.record_id for item in state_mod.records_before(records, cutoff)}
        assert from_store == in_memory, cutoff


def test_the_store_orders_unplaced_records_last(store: SqliteStore) -> None:
    """SQLite sorts NULL first by default, which would put a standing world rule ahead of
    scene one — the opposite of `in_story_order`."""
    store.record_state_records(
        BOOK_ID,
        BRANCH_ID,
        [record("unplaced", order_key=None), record("placed", order_key="s1")],
        created_at="t",
    )
    assert [item.record_id for item in store.state_records(BOOK_ID, BRANCH_ID)] == [
        "placed",
        "unplaced",
    ]


def test_records_are_scoped_to_their_book_and_branch(store: SqliteStore) -> None:
    store.record_state_records(BOOK_ID, BRANCH_ID, [record("mine")], created_at="t")
    store.record_state_records(BOOK_ID, "other-branch", [record("theirs")], created_at="t")
    assert [item.record_id for item in store.state_records(BOOK_ID, BRANCH_ID)] == ["mine"]


def test_a_subject_query_narrows_to_one_entity(store: SqliteStore) -> None:
    store.record_state_records(BOOK_ID, BRANCH_ID, load_state("mystery").records, created_at="t")
    keys = store.state_records(BOOK_ID, BRANCH_ID, subject="brass_key")
    assert {item.record_id for item in keys} == {"rec-key-missing", "rec-key-opens-vault"}


def test_the_accepting_event_commits_with_the_records(store: SqliteStore) -> None:
    """Same atomicity as every other write here: a record without the event recording it
    cannot be rebuilt, which is §19's recovery clause."""
    store.record_state_records(
        BOOK_ID,
        BRANCH_ID,
        [record("rec")],
        created_at="2026-08-13T00:00:00Z",
        events=[
            Event(
                event_type=EventType.STATE_RECORDS_ACCEPTED,
                project_id=PROJECT_ID,
                created_at="2026-08-13T00:00:00Z",
                book_id=BOOK_ID,
                branch_id=BRANCH_ID,
                payload={"records": 1, "extracted": False},
            )
        ],
    )
    types = [stored.event.event_type for stored in store.read_log()]
    assert EventType.STATE_RECORDS_ACCEPTED in types


def test_reverting_retracts_the_state_read_out_of_the_discarded_prose(
    store: SqliteStore,
) -> None:
    """The trap migration 016 exists for, and it is unclearable without it.

    Extraction writes canon whose evidence cites one node version. `revert` moves the head
    back past that version, so the prose the record was read from leaves the book — and
    without retraction the record does not. Redraft that scene with different numbers and
    `state.contradiction.v0` fires against the orphan, refusing the beat forever: the
    detector runs in-process on every attempt and mints its finding OPEN each time, while
    `litharness dismiss` satisfies only the *pre-flight* standing gate. §19.1's free
    revivable park becomes a paid unclearable one, through a door §19.1 did not know about.
    """
    base = build_revision(
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
    store.commit_revision(base, created_at="2026-08-13T00:00:00Z")
    drafted = gate_draft(base, "scene-1", "x" * 400).revision
    assert drafted is not None
    extracted = record("rec-extracted", subject="rook", predicate="status_snapshot")
    store.commit_revision(
        drafted, created_at="2026-08-13T00:00:01Z", state_records=[extracted]
    )
    assert [r.record_id for r in store.state_records(BOOK_ID, BRANCH_ID)] == ["rec-extracted"]

    store.revert(
        BOOK_ID,
        BRANCH_ID,
        base.revision_id,
        created_at="2026-08-13T00:00:02Z",
        project_id=PROJECT_ID,
    )

    assert store.state_records(BOOK_ID, BRANCH_ID) == [], "the orphan is gone from canon"
    # Forward-only: the row survives, marked, so the record still explains itself.
    row = store._connection.execute(
        "SELECT retracted_by_revision_id, retracted_at FROM state_records "
        "WHERE record_id = ?",
        ("rec-extracted",),
    ).fetchone()
    assert row["retracted_by_revision_id"], "retracted, not deleted"
    assert row["retracted_at"] == "2026-08-13T00:00:02Z"
