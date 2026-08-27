"""A declaration a later one replaced is not carried into canon, and why that is a blocker.

**Measured on Serial Pilot 7, 2026-08-25, and this file exists because of it.** The Architect
seeded a world of 208 records, improving four of its own declarations on the way. `world declare`
appends and has no retraction path, so those four slots ended up holding two values each;
`world accept` carried both; `detect_contradictions` read two values at one story position as
MAJOR and **blocking**; and every scene of the book was refused three times and poisoned. Not one
word could be drafted, and `dismiss` did not help — the pre-flight gate reads stored findings,
but the integrity gate re-derives them from canon on every single attempt.

**What is being pinned here is that the two halves share one idea of a slot.** If
`integrity.superseded` and `integrity.detect_contradictions` ever disagreed about what makes two
records the same fact, acceptance would leave behind exactly the pairs the detector fires on and
the blocker would come straight back. Both call `disagreement_key`, and the tests below are the
cases where a *wrong* key is tempting: two edges, two moments, and a subject with two roles.

No model call and no network. The end-to-end case drives `main(argv)` on a temporary store.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.cli import EXIT_OK, main
from litharness.domain import worlds
from litharness.domain.findings import DetectorInput
from litharness.domain.integrity import detect_contradictions, superseded


def record(subject: str, predicate: str, **kwargs: object) -> lc.StateRecord:
    return worlds.world_record(subject, predicate, **kwargs)  # type: ignore[arg-type]


def times(*pairs: tuple[lc.StateRecord, str]) -> dict[str, str]:
    return {item.record_id: when for item, when in pairs}


def test_a_redeclared_fact_leaves_the_earlier_one_behind() -> None:
    first = record("crit_glasses", "manifests_as", value="how many vials a body will hold")
    second = record("crit_glasses", "manifests_as", value="one order, eleven rungs")
    replaced = superseded([first, second], declared_at=times((first, "10:00"), (second, "10:05")))
    assert replaced == (first.record_id,)


def test_the_same_fact_declared_twice_supersedes_nothing() -> None:
    """Two identical declarations are one fact, and `detect_contradictions` agrees."""
    once = record("dan", "life_status", value="alive")
    again = record("dan", "life_status", value="alive")
    assert superseded([once, again], declared_at=times((once, "10:00"), (again, "10:05"))) == ()


def test_declaration_order_decides_which_one_survives() -> None:
    """The record carries no timestamp, so the store's is what orders them."""
    early = record("dan", "life_status", value="alive")
    late = record("dan", "life_status", value="hurt")
    assert superseded([early, late], declared_at=times((early, "10:05"), (late, "10:00"))) == (
        late.record_id,
    )


def test_two_edges_are_two_facts_and_neither_replaces_the_other() -> None:
    """`object_ref` is in the key, for `detect_contradictions`' own measured reason.

    A creature with two traits, or a card in two hands, is not a redeclaration. Dropping the
    edge from the key here would silently delete half of every two-valued relation a world
    declares.
    """
    keen = record("ash", "trait", object_ref="keen_scent")
    night = record("ash", "trait", object_ref="night_sight")
    assert superseded([keen, night], declared_at=times((keen, "10:00"), (night, "10:05"))) == ()


def test_a_value_that_changes_between_scenes_is_a_story_and_not_a_replacement() -> None:
    """The story position is in the key. Without it, every progression would be superseded."""
    before = record("dan", "life_status", value="whole", order_key="010")
    after = record("dan", "life_status", value="one-handed", order_key="020")
    assert superseded([before, after], declared_at=times((before, "10:00"), (after, "10:05"))) == ()


def test_a_protagonist_does_not_replace_being_cast() -> None:
    """`entity_role` is the one multi-valued predicate, and this is the case that proves why.

    A second role on a cast member poisoned two scenes of the first book drafted on a world
    that declared a protagonist. Reading the second role as *replacing* the first would be the
    same defect with the damage moved: the world would declare a protagonist and canon would
    not have one.
    """
    cast = record("dan", worlds.ENTITY_ROLE_PREDICATE, value="cast")
    lead = record("dan", worlds.ENTITY_ROLE_PREDICATE, value="protagonist")
    assert superseded([cast, lead], declared_at=times((cast, "10:00"), (lead, "10:05"))) == ()


@pytest.fixture
def fake(monkeypatch) -> None:
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")


def test_accepting_a_redeclared_world_leaves_canon_with_nothing_to_contradict(
    fake, tmp_path, capsys
) -> None:
    """The end-to-end case, which is the one Serial Pilot 7 could not get past.

    Two declarations into one slot, then `accept` — and the detector that refused every scene
    of that book has nothing to say about this canon.
    """
    db = tmp_path / "world.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "listing", "--writer", "vance", "--scenes", "24"]) == EXIT_OK
    )
    for value in ("how many vials a body will hold", "one order, eleven rungs"):
        assert (
            main(
                [
                    "--database",
                    str(db),
                    "world",
                    "declare",
                    "crit_glasses",
                    "manifests_as",
                    "--value",
                    value,
                ]
            )
            == EXIT_OK
        )
    capsys.readouterr()
    assert main(["--database", str(db), "world", "accept"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "1 left proposed" in out

    with SqliteStore.open(db) as store:
        book_id, branch_id = export_module.resolve_branch(store, None, None)
        records = store.state_records(book_id, branch_id)
        head = store.head(book_id, branch_id)
        assert head is not None
        findings = detect_contradictions(
            DetectorInput(
                book_id=book_id,
                branch_id=branch_id,
                logical_id="scene-1",
                records=tuple(records),
            )
        )
    assert findings == []
    canon = [
        item
        for item in records
        if item.subject == "crit_glasses" and item.authority is lc.StateAuthority.ACCEPTED_CANON
    ]
    assert [item.value for item in canon] == ["one order, eleven rungs"]
