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

**The blocker came back one round later anyway, and the second half of this file is why.**
Measured on Serial Pilot 13's accepted world, 2026-08-29. A first accept leaves the replaced
records proposed, exactly as designed — and they sit in slots canon now holds. `superseded` was
called with the proposals alone, so on the *second* accept nothing supersedes them, all 24
promote, and canon ends with two values in twenty-four slots: MAJOR, blocking, every scene of
the book refused. Reproduced on a copy of that database before the fix and zero after it.

The same omission had a quieter face. Every read view loaded the raw record list, so the
Architect's replaced first drafts were reported as part of the world: `world ladders` printed
`[]` for a world whose three chains resolve, because a `precedes` edge with no criterion belongs
to every ladder and the strays spliced all three. `world check` called that world incoherent
while `world accept` had accepted it without `--force` — two answers to one question. Both are
`integrity.in_force`, and `show` is deliberately not on it.

No model call and no network. The end-to-end cases drive `main(argv)` on a temporary store.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.application import world as world_view
from litharness.cli import EXIT_OK, main
from litharness.domain import worlds
from litharness.domain.findings import DetectorInput
from litharness.domain.integrity import detect_contradictions, in_force, superseded


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


def accepted(record: lc.StateRecord) -> lc.StateRecord:
    return lc.StateRecord(
        record_id=record.record_id,
        kind=record.kind,
        subject=record.subject,
        predicate=record.predicate,
        value=record.value,
        object_ref=record.object_ref,
        story_position=record.story_position,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=list(record.pov_visibility),
        evidence=list(record.evidence),
        predicate_registry_version=record.predicate_registry_version,
        note=record.note,
    )


def test_canon_holds_its_slot_against_a_proposal_written_after_it() -> None:
    """The one that reopened the blocker: time alone is not the ordering.

    A proposal a first accept left behind is *older* than nothing — it simply sits in a slot
    canon now holds. Ordering the group by the clock put it last in its own group of one and
    promoted it, which is two values in one canon slot and every scene refused.
    """
    settled = accepted(record("kell", "life_status", value="alive"))
    stray = record("kell", "life_status", value="hurt")
    replaced = superseded(
        [settled, stray], declared_at=times((settled, "10:00"), (stray, "10:05"))
    )
    assert replaced == (stray.record_id,)


def test_canon_is_never_reported_replaced_even_by_later_canon() -> None:
    """Two accepted records in one slot is a real contradiction, and hiding one would hide it.

    `detect_contradictions` is what says so, and every caller that filters on `superseded`
    would stop being able to see it. A tidy-up that quietly drops an accepted record is worse
    than the untidiness.
    """
    early = accepted(record("kell", "life_status", value="alive"))
    late = accepted(record("kell", "life_status", value="hurt"))
    assert superseded([early, late], declared_at=times((early, "10:00"), (late, "10:05"))) == ()


def test_the_records_in_force_are_canon_plus_the_proposals_nothing_answered() -> None:
    """`in_force` is the positive form, and the read views are its whole reason for existing."""
    settled = accepted(record("kell", "life_status", value="alive"))
    stray = record("kell", "life_status", value="hurt")
    unrelated = record("kell", "trait", object_ref="keen_scent")
    speaking = in_force(
        [settled, stray, unrelated],
        declared_at=times((settled, "10:00"), (stray, "10:05"), (unrelated, "10:06")),
    )
    assert [item.record_id for item in speaking] == [settled.record_id, unrelated.record_id]


def test_a_stray_first_draft_does_not_splice_the_ladders_it_was_replaced_in() -> None:
    """Serial Pilot 13's world in miniature: `world ladders` printed `[]` for this shape.

    Each rung edge exists twice — the criterion-less draft the Architect wrote first, and the
    corrected canon edge that replaced it. `rank_order` reads an edge with no criterion as
    belonging to every ladder, so the two drafts gave `ladder_of` a second edge out of each
    rung and it returned empty for both chains rather than guess.
    """
    criteria = [
        accepted(record("crit_seal", worlds.TYPE_PREDICATE, value=worlds.CRITERION)),
        accepted(record("crit_seal", worlds.COMPARATOR_PREDICATE, value="ordinal")),
    ]
    drafts = [
        record("first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal", order_key="a"),
        record("second_seal", worlds.PRECEDES_PREDICATE, object_ref="third_seal", order_key="a"),
    ]
    corrected = [
        accepted(
            record(
                "first_seal",
                worlds.PRECEDES_PREDICATE,
                object_ref="second_seal",
                value="crit_seal",
                order_key="a",
            )
        ),
        accepted(
            record(
                "second_seal",
                worlds.PRECEDES_PREDICATE,
                object_ref="third_seal",
                value="crit_seal",
                order_key="a",
            )
        ),
    ]
    everything = [*criteria, *drafts, *corrected]
    when = times(*((item, f"10:{index:02d}") for index, item in enumerate(everything)))

    assert worlds.ladder_of(everything, "crit_seal") == ()
    speaking = in_force(everything, declared_at=when)
    assert worlds.ladder_of(speaking, "crit_seal") == ("first_seal", "second_seal", "third_seal")
    assert [row["criterion"] for row in world_view.ladders(speaking)] == ["crit_seal"]


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


def test_a_second_accept_does_not_promote_what_the_first_one_left_behind(
    fake, tmp_path, capsys
) -> None:
    """The blocker one round later, which is the case the fix above was measured on.

    The record the first accept declined to carry is still a proposal, and its slot now belongs
    to canon. Promoting it is two values in one accepted slot — MAJOR, blocking, every scene of
    the book refused three times and poisoned. `--force` is used deliberately: it is the flag
    an operator reaches for when a world complains, and it must not be able to buy this.
    """
    db = tmp_path / "world.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "listing", "--writer", "vance", "--scenes", "24"]) == EXIT_OK
    )
    for value in ("how many vials a body will hold", "one order, eleven rungs"):
        assert (
            main(
                ["--database", str(db), "world", "declare", "crit_glasses", "manifests_as",
                 "--value", value]
            )
            == EXIT_OK
        )
    assert main(["--database", str(db), "world", "accept"]) == EXIT_OK
    capsys.readouterr()

    assert main(["--database", str(db), "world", "accept", "--force"]) == EXIT_OK
    assert "accepted 0 of 1 proposal(s)" in capsys.readouterr().out

    with SqliteStore.open(db) as store:
        book_id, branch_id = export_module.resolve_branch(store, None, None)
        records = store.state_records(book_id, branch_id)
        findings = detect_contradictions(
            DetectorInput(
                book_id=book_id, branch_id=branch_id, logical_id="scene-1", records=tuple(records)
            )
        )
    assert findings == []
    canon = [
        item
        for item in records
        if item.subject == "crit_glasses" and item.authority is lc.StateAuthority.ACCEPTED_CANON
    ]
    assert len(canon) == 1, "a stray proposal reached canon on the second round"


def test_the_views_read_the_accepted_world_and_show_reads_everything(
    fake, tmp_path, capsys
) -> None:
    """`check` agrees with `accept`, and `show` is the one view that still sees the strays.

    A world `world accept` took without `--force` must not be called incoherent by
    `world check` — that was two answers to one question, and it is the pair pilot 12's seed
    read before concluding the CLI was at fault. `show` keeps every record because it is the
    provenance view: an Architect that cannot see what it proposed proposes it again.
    """
    db = tmp_path / "world.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "listing", "--writer", "vance", "--scenes", "24"]) == EXIT_OK
    )
    for value in ("how many vials a body will hold", "one order, eleven rungs"):
        assert (
            main(
                ["--database", str(db), "world", "declare", "crit_glasses", "manifests_as",
                 "--value", value]
            )
            == EXIT_OK
        )
    assert main(["--database", str(db), "world", "accept"]) == EXIT_OK
    capsys.readouterr()

    assert main(["--database", str(db), "world", "check"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["ok"] is True

    assert main(["--database", str(db), "world", "summary"]) == EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["replaced"] == 1, "the dead declaration is counted rather than netted away"

    assert main(["--database", str(db), "world", "show", "--subject", "crit_glasses"]) == EXIT_OK
    shown = json.loads(capsys.readouterr().out)
    assert len(shown) == 2, "`show` is the provenance view and must keep the replaced record"
