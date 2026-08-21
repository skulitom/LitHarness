"""The packet's story-time cutoff: what a scene may be told about its own future.

`domain/context.py::assemble` has taken a `story_time_cutoff` since it was written and
`application/planner.py::packet_for` never passed one. That omission was documented and
correctly reasoned — nothing defines a mapping from a manuscript scene to an `order_key`, and
in the live loop records are extracted from accepted prose, so the only records that exist
describe scenes already written.

**The second half of that argument holds for extracted records and not for the loop.** Two
cases reach it:

- **Out-of-order drafting, with no seeding at all.** §4.1's rule is that "a blocked beat is
  skipped, not waited on", so beat 3 can poison, beats 4-8 draft, and `revive` then re-runs
  beat 3 against a store whose canon already holds what scenes 4-8 established. Records about
  scenes not yet written is exactly the state the docstring said could not arise.
- **Seeded records**, which are future-dated by construction. A want or a fear that changes
  across a book has to be dated ahead of the scene that will hold it, so with no cutoff scene
  one is handed what the character will want in chapter two.

These tests live beside `tests/test_context.py` rather than in it because they need a store,
and that file is deliberately store-free: `assemble` stays pure so the golden `GoldContextSuite`
can grade it without a database. The cutoff is chosen in `packet_for`, which is the one place
the packet touches the store, so this is where it can be tested at all.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import (
    fixture_manuscript,
    fixture_plans,
    fixture_state,
)
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import packet_for
from litharness.domain.beats import Beat, beats_for, template_for
from litharness.domain.context import FACTS, assemble
from litharness.domain.extraction import (
    PLANNED_POSITION_VERSION,
    extract_state,
    has_story_vocabulary,
    stated_position,
)
from litharness.domain.findings import DetectorInput
from litharness.domain.integrity import detect_contradictions
from litharness.domain.plans import import_plan
from litharness.domain.revision import Revision, import_manuscript, new_book
from litharness.domain.state import import_state, order_key_of
from tests.conftest import BOOK_ID, BRANCH_ID

CREATED = "2026-08-22T00:00:00Z"

#: A status line in the Serial Pilot's declared `Loop | Day` sheet, which `extract_state`
#: reads back. Written with the em dash the pattern anchors on.
STATUS_LINE = "[STATUS] silas — Loop 2 | Day 1"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "cutoff.db")


def _want(record_id: str, value: str, order_key: str, *, declared: bool = True) -> lc.StateRecord:
    """A seeded interiority record, dated at a beat.

    `declared` is the switch the trap test flips: without
    `PLANNED_POSITION_VERSION` the record reads as a story position somebody else chose, and
    everything downstream abstains. See `test_an_undeclared_dated_record_turns_the_cutoff_off`.
    """
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.KNOWLEDGE,
        subject="silas",
        predicate="wants",
        value=value,
        story_position=lc.StoryPosition(order_key=order_key),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
        evidence=[],
        predicate_registry_version=PLANNED_POSITION_VERSION if declared else None,
    )


def _book_zero(store: SqliteStore, records: list[lc.StateRecord], *, scenes: int = 8) -> Revision:
    """A book this system planned itself: no imported snapshot, so no vocabulary of its own."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Reappraisal", scenes=scenes)
    store.commit_revision(revision, created_at=CREATED)
    if records:
        store.record_state_records(BOOK_ID, BRANCH_ID, records, created_at=CREATED)
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None
    return head


def _beat(revision: Revision, ordinal: int) -> Beat:
    return beats_for(revision, template_for(revision))[ordinal - 1]


def _seed_records() -> list[lc.StateRecord]:
    """The Serial Pilot's seed, read from the file the run actually uses.

    Read rather than transcribed, because these tests are about what that seed does — a copy
    here would keep passing after the seed changed, which is the failure mode a fixture of a
    live artifact has.
    """
    from pathlib import Path

    path = Path(__file__).parents[1] / "plan" / "serial-pilot-seed.json"
    snapshot = lc.parse_artifact(
        lc.StateSnapshot, json.loads(path.read_text(encoding="utf-8"))
    )
    return list(import_state(snapshot, book_id=BOOK_ID, branch_id=BRANCH_ID).records)


def _unplaced(records: list[lc.StateRecord]) -> list[lc.StateRecord]:
    """The part of a seed that is true of the book rather than of a moment in it."""
    return [record for record in records if record.story_position is None]


def _seeded_interiority(records: list[lc.StateRecord]) -> list[lc.StateRecord]:
    return [record for record in records if record.predicate in {"wants", "fears"}]


# -- the leak, reproduced ---------------------------------------------------------------------


def test_a_want_dated_later_in_the_book_does_not_reach_an_earlier_scene(
    store: SqliteStore,
) -> None:
    """`plan/interiority-model.md`'s measured blocker, closed.

    Two wants, one at `s1` and one at `s5`, and the packet for scene 1. Before the cutoff was
    passed both arrived in the Established facts block — the story's engine handed over before
    it starts. This fails on the `packet_for` that passes no cutoff.
    """
    head = _book_zero(
        store,
        [
            _want("w1", "the senior seal on his card", "s1"),
            _want("w5", "to know what the token is", "s5"),
        ],
    )
    packet = packet_for(store, head, _beat(head, 1), token_budget=16000)

    assert packet.contains_ref("w1"), "what he already wants is his to want"
    assert not packet.contains_ref("w5")
    rendered = packet.render()
    assert "the senior seal on his card" in rendered
    assert "to know what the token is" not in rendered


def test_the_scene_the_want_is_dated_at_is_the_first_one_told(store: SqliteStore) -> None:
    """The boundary is inclusive, which is what `records_before` means by "at or before".

    Asserted across the whole book rather than at one scene, because a cutoff that was off by
    one would still pass the test above.
    """
    head = _book_zero(store, [_want("w5", "to know what the token is", "s5")])
    told = [
        beat.ordinal
        for beat in beats_for(head, template_for(head))
        if packet_for(store, head, beat, token_budget=16000).contains_ref("w5")
    ]
    assert told == [5, 6, 7, 8]


def test_a_record_the_extractor_wrote_for_a_later_scene_does_not_reach_an_earlier_one(
    store: SqliteStore,
) -> None:
    """The same leak with nothing seeded, which is why this change stands on its own merits.

    §4.1: "a blocked or parked item never stalls the queue", so beat 3 can poison while beats
    4-8 draft, and `revive` then re-runs beat 3. The record here is genuinely `extract_state`'s
    output rather than an imitation of one, so what is asserted is the shape the loop actually
    writes.
    """
    seed = _seed_records()
    head = _book_zero(store, seed)
    later = extract_state(
        f"Silas turned the token over.\n\n{STATUS_LINE}\n\nHe put it away.\n",
        known=seed,
        project_id="11111111-1111-5111-8111-111111111111",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-4",
        version_id="v4",
        stated_order_key="s4",
    )
    assert len(later) == 1, "the pilot's declared sheet must actually read back"
    store.record_state_records(BOOK_ID, BRANCH_ID, later, created_at=CREATED)
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None

    early = packet_for(store, head, _beat(head, 2), token_budget=16000)
    assert not early.contains_ref(later[0].record_id)
    assert "loop=2" not in early.render()
    # And the scene it was read from is still told it.
    assert packet_for(store, head, _beat(head, 4), token_budget=16000).contains_ref(
        later[0].record_id
    )


# -- what must not change -----------------------------------------------------------------------


@pytest.mark.parametrize("fixture_id", ["mystery", "litrpg"])
def test_a_book_whose_story_positions_somebody_else_chose_gets_no_cutoff(
    store: SqliteStore, fixture_id: str
) -> None:
    """The abstention, in the same cases and for the same reason as `stated_position`.

    Both golden fixtures carry an imported snapshot at `fixture.v1`, and the mystery's scene 5
    is an analepsis attested at `s1` — the measured case that makes an ordinal-derived cutoff
    wrong. So every beat of both books abstains, and every packet is byte-identical to the one
    the no-cutoff `packet_for` produced.
    """
    revision = _import_fixture(store, fixture_id)
    records = store.state_records(revision.book_id, revision.branch_id)
    assert has_story_vocabulary(records)

    for beat in beats_for(revision, template_for(revision)):
        assert stated_position(records, beat.story_order_key) is None
        before = assemble(
            revision,
            beat.logical_id,
            plan_items=store.plan_items(revision.book_id, revision.branch_id),
            state_records=records,
            query_id=f"beat:{beat.logical_id}",
        )
        assert packet_for(store, revision, beat).render() == before.render()


def test_the_unplaced_ability_graph_survives_the_cutoff(store: SqliteStore) -> None:
    """A record with no `story_position` is true of the book rather than of a moment in it.

    The Serial Pilot's seed is fifteen such records — `plan/serial-pilot-1.md` §2 calls them
    "the initial condition, true before the book begins" — and a cutoff that treated unplaced
    as "later than everything" would empty the first packet of every book in the project.
    """
    seed = _seed_records()
    head = _book_zero(store, seed)
    packet = packet_for(store, head, _beat(head, 1), token_budget=16000)

    packed = {item.source_logical_id for item in packet.sections[FACTS]}
    # Every unplaced record except the sheet declaration, which is excluded as configuration.
    expected = {
        record.record_id
        for record in _unplaced(seed)
        if record.predicate != "status_sheet"
    }
    assert expected <= packed
    assert len(expected) == 14, "the ability graph is fourteen records plus its sheet"


def test_a_book_with_no_dated_records_at_all_is_unchanged(store: SqliteStore) -> None:
    """A cutoff over a book whose canon is entirely unplaced can only be a no-op, and saying
    so is cheaper than trusting it: this is the shape the pilot's seed had before any
    interiority was dated into it, and the shape every book has before its first scene is
    accepted."""
    seed = _unplaced(_seed_records())
    head = _book_zero(store, seed)
    beat = _beat(head, 4)
    with_cutoff = packet_for(store, head, beat, token_budget=16000)
    without = assemble(
        head,
        beat.logical_id,
        state_records=store.state_records(BOOK_ID, BRANCH_ID),
        query_id=f"beat:{beat.logical_id}",
        token_budget=16000,
    )
    assert with_cutoff.render() == without.render()


# -- the trap ------------------------------------------------------------------------------------


def test_an_undeclared_dated_record_turns_the_cutoff_off(store: SqliteStore) -> None:
    """Pinned because it is silent, and because it is the reason `PLANNED_POSITION_VERSION`
    exists.

    A dated canon record with no declaration is, to `has_story_vocabulary`, a story position
    somebody else chose — so `stated_position` abstains, the cutoff is `None`, and the leak
    the seeding was for comes back with nothing in the log to say why. It also turns off §12
    step 5 extraction for the whole book at the same moment, which is the larger half of the
    damage; `test_extraction_survives_a_declared_seed_position` measures that half.

    The default direction is deliberate — forgetting the declaration loses coverage rather
    than minting a false order — and this test is what makes forgetting visible.
    """
    head = _book_zero(
        store,
        [
            _want("w1", "the senior seal on his card", "s1"),
            _want("w5", "to know what the token is", "s5", declared=False),
        ],
    )
    records = store.state_records(BOOK_ID, BRANCH_ID)
    assert has_story_vocabulary(records) is True
    assert stated_position(records, "s1") is None
    assert packet_for(store, head, _beat(head, 1), token_budget=16000).contains_ref("w5")


def test_extraction_survives_a_declared_seed_position() -> None:
    """The other half of the same declaration, measured rather than argued.

    Without it, one dated seed record makes `extract_state` return nothing for every scene of
    the book — a book whose scenes look, at every layer, like they established nothing. That
    is the failure `has_story_vocabulary`'s own docstring records finding by running Book Zero.
    """
    seed = _seed_records()
    prose = f"Silas turned the token over.\n\n{STATUS_LINE}\n\nHe put it away.\n"

    def read_back(records: list[lc.StateRecord]) -> int:
        return len(
            extract_state(
                prose,
                known=records,
                project_id="11111111-1111-5111-8111-111111111111",
                book_id=BOOK_ID,
                branch_id=BRANCH_ID,
                logical_id="scene-3",
                version_id="v3",
                stated_order_key="s3",
            )
        )

    assert read_back(seed) == 1
    assert read_back([*seed, _want("w1", "the senior seal", "s1", declared=False)]) == 0
    assert read_back([*seed, _want("w1", "the senior seal", "s1")]) == 1


# -- helpers ---------------------------------------------------------------------------------


def _import_fixture(store: SqliteStore, name: str) -> Revision:
    """A golden book with its plan and state, exactly as `cli import` lands them."""
    manuscript = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript(name).read_text(encoding="utf-8")),
    )
    revision = import_manuscript(manuscript).revision
    store.commit_revision(revision, created_at=CREATED)

    plan = import_plan(
        lc.parse_artifact(
            lc.PlanSnapshot, json.loads(fixture_plans(name).read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_plan_items(
        revision.book_id,
        revision.branch_id,
        plan.items,
        created_at=CREATED,
        source_revision_id=plan.source_revision_id,
    )

    state = import_state(
        lc.parse_artifact(
            lc.StateSnapshot, json.loads(fixture_state(name).read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        state.records,
        created_at=CREATED,
        source_revision_id=state.source_revision_id,
    )
    head = store.head(revision.book_id, revision.branch_id)
    assert head is not None
    return head


# -- the seeded interiority, and the proof it lands ---------------------------------------------


def test_the_pilot_seed_carries_dated_interiority_at_all() -> None:
    """A guard on the guard: the tests below would pass vacuously over a seed with none.

    Four is the number `plan/serial-pilot-1.md` §8 records adding — sparing on purpose, since
    each one occupies every packet from its own scene to the end of the book.
    """
    seeded = _seeded_interiority(_seed_records())
    assert len(seeded) == 4
    assert {record.predicate for record in seeded} == {"wants", "fears"}
    assert all(record.story_position is not None for record in seeded)
    assert all(record.kind is lc.StateRecordKind.KNOWLEDGE for record in seeded)


def test_every_seeded_want_and_fear_lands_at_its_own_scene_and_not_before(
    store: SqliteStore,
) -> None:
    """The two claims of `plan/handoff-interiority.md` Task 2, over the real seed.

    Asserted here and printed by `tools/interiority_packet_proof.py`, which reports the same
    grid as output rather than as a pass.
    """
    seed = _seed_records()
    head = _book_zero(store, seed)
    beats = beats_for(head, template_for(head))
    carried = {
        beat.story_order_key: {
            record.record_id
            for record in _seeded_interiority(seed)
            if packet_for(store, head, beat, token_budget=16000).contains_ref(record.record_id)
        }
        for beat in beats
    }
    for record in _seeded_interiority(seed):
        assert record.story_position is not None
        dated_at = record.story_position.order_key
        assert dated_at is not None
        for key, present in carried.items():
            assert key is not None
            due = key >= dated_at
            assert (record.record_id in present) is due, (record.record_id, key)


def test_the_seeded_interiority_costs_the_packet_almost_nothing(store: SqliteStore) -> None:
    """The whole ability graph measured 351 tokens of a 16,000 budget; this is smaller again.

    Worth a number rather than a claim of cheapness, because the argument for seeding rather
    than instructing rests on the packet being able to carry it in every scene.
    """
    seed = _seed_records()
    head = _book_zero(store, seed)
    beat = _beat(head, 8)  # the last scene, where all four are due
    packet = packet_for(store, head, beat, token_budget=16000)
    interior_tokens = sum(
        item.tokens
        for item in packet.sections[FACTS]
        if item.source_logical_id in {r.record_id for r in _seeded_interiority(seed)}
    )
    assert 0 < interior_tokens < 150, interior_tokens
    assert packet.used_tokens < 16000


def test_several_dated_wants_for_one_subject_are_not_a_blocking_contradiction() -> None:
    """The decision `plan/handoff-interiority.md` Task 2 asks to be made deliberately.

    The seed's standing property is that no two canon records share a `(subject, predicate)`
    pair, because until scoped cardinality lands (`plan/state-model-abilities.md` §2) a
    repeated predicate is reported as a blocking contradiction. Two `silas wants` records
    break that property as stated — and not the property the detector actually has, which
    groups on `(subject, predicate, order_key)`. Distinct positions are distinct groups.

    Measured rather than reasoned about, because the detector's key is what decides it and a
    later change to that key would silently make the seed blocking.
    """
    seed = _seed_records()
    findings = detect_contradictions(
        DetectorInput(
            book_id=BOOK_ID, branch_id=BRANCH_ID, logical_id="scene-1", records=tuple(seed)
        )
    )
    assert findings == []

    groups: dict[tuple[str, str, str], list[str]] = {}
    for record in seed:
        key = (record.subject, record.predicate, order_key_of(record) or "")
        groups.setdefault(key, []).append(record.record_id)
    assert not [ids for ids in groups.values() if len(ids) > 1]
    # And the property that would collide if the positions were dropped, so the reason this
    # passes is on the record: two `silas wants`, separated only by where they sit.
    pairs = [(record.subject, record.predicate) for record in seed]
    assert pairs.count(("silas", "wants")) == 2


def test_the_seeded_interiority_is_objective_rather_than_pov_restricted() -> None:
    """`pov_visibility` empty, deliberately, and it is the counter-intuitive direction.

    A private desire looks like the obvious candidate for a POV whitelist. Nothing in the live
    loop passes a `pov_character_id` — `packet_for`'s parameter defaults to `None` and no
    caller sets it — and `visible_to` treats an absent POV as not satisfying a restriction, so
    a restricted record would be dropped from every packet in the book and recorded as "not
    visible to POV (none named)". The tone note anchors the whole pilot to Silas, so there is
    no second POV for an objective record to leak to.
    """
    for record in _seeded_interiority(_seed_records()):
        assert record.pov_visibility == []


def test_the_proof_tool_reports_both_claims_holding() -> None:
    """The deliverable is output, not a passing test — so the thing that produces the output
    is what this exercises, exit code and all."""
    from tools.interiority_packet_proof import main

    assert main([]) == 0
