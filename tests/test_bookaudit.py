"""The whole-book audit: descriptions read across scenes, never a score."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.application import bookaudit
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.promises import Promise, promise_id_for
from litharness.domain.revision import Revision, build_revision
from tests.conftest import BOOK_ID, BRANCH_ID

SCENES = [
    "Tam Cawl stood at the desk while the panel lit.\n\n"
    "[STATUS] Tam Cawl — Mark 1 | Seconds 60 | Held 1\n\n"
    "Beside him Ruth Abiola read the order aloud in Corridor B. The yard was quiet.",
    "Ruth Abiola counted the doors in Corridor B, six of them.\n\n"
    "[STATUS] Tam Cawl — Mark 2 | Seconds 45 | Held 1 | Rod 1",
    "The yard settled. Tam Cawl walked Corridor B alone.\n\n"
    "[STATUS] Tam — Mark 2 | Seconds forty | Held 1 | Rod 1",
    "",
    "",
    "",
]


def _revision(texts: list[str]) -> Revision:
    keys = initial_keys(len(texts))
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title="The Order")]
    nodes += [
        Node.text_node(
            f"scene-{index + 1}", NodeKind.SCENE, keys[index], text, parent_logical_id="book"
        )
        for index, text in enumerate(texts)
    ]
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


def _record(
    record_id: str,
    *,
    subject: str,
    predicate: str,
    value: object = None,
    object_ref: str | None = None,
    order_key: str | None = "s1",
) -> lc.StateRecord:
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.ASSERTION,
        subject=subject,
        predicate=predicate,
        value=value,
        object_ref=object_ref,
        story_position=lc.StoryPosition(order_key=order_key) if order_key else None,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
    )


class FakeStore:
    """The five reads `bookaudit.AuditStore` names, and nothing else."""

    def __init__(
        self,
        revision: Revision,
        *,
        records: list[lc.StateRecord] | None = None,
        promises: list[Promise] | None = None,
        summaries: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._revision = revision
        self._records = records or []
        self._promises = promises or []
        self._summaries = summaries or {}

    def head(self, book_id: str, branch_id: str) -> Revision | None:
        return self._revision

    def plan_items(self, book_id: str, branch_id: str) -> list[lc.PlanItem]:
        return []

    def state_records(self, book_id: str, branch_id: str) -> list[lc.StateRecord]:
        return list(self._records)

    def scene_summaries(self, book_id: str, branch_id: str) -> dict[str, dict[str, str]]:
        return self._summaries

    def promises(self, book_id: str, branch_id: str, *, open_only: bool = False) -> list[Promise]:
        return [p for p in self._promises if not open_only or p.paid_at_key is None]


def _promise(
    subject: str, *, opened: str, due: str, paid: str | None = None, located: bool = True
) -> Promise:
    return Promise(
        promise_id=promise_id_for(BOOK_ID, subject),
        subject=subject,
        description=f"what the book owes about the {subject}",
        opened_at_key=opened,
        due_key=due,
        opened_by_revision="rev-1",
        status="paid" if paid else "open",
        paid_at_key=paid,
        paid_by_revision="rev-2" if paid else None,
        paid_logical_id="scene-2" if (paid and located) else None,
        paid_start=0 if (paid and located) else None,
        paid_end=8 if (paid and located) else None,
        paid_content_hash="0" * 64 if (paid and located) else None,
        model="stub",
    )


@pytest.fixture
def book() -> bookaudit.BookFacts:
    revision = _revision(SCENES)
    records = [
        _record(
            "r1", subject="tam_cawl", predicate="entity_role", value="protagonist", order_key=None
        ),
        _record("r2", subject="ruth_abiola", predicate="entity_role", value="cast", order_key=None),
        _record("r3", subject="jonah_pratt", predicate="entity_role", value="cast", order_key=None),
        _record(
            "r4",
            subject="tam_cawl",
            predicate="stands_at",
            object_ref="mark_ladder",
            value="mark_one",
            order_key="s1",
        ),
        _record(
            "r5",
            subject="tam_cawl",
            predicate="stands_at",
            object_ref="mark_ladder",
            value="mark_two",
            order_key="s2",
        ),
        _record(
            "r6",
            subject="tam_cawl",
            predicate="stands_at",
            object_ref="mark_ladder",
            value="mark_one",
            order_key="s3",
        ),
    ]
    promises = [
        _promise("the_rod", opened="s1", due="s2", paid="s2"),
        _promise("the_renter", opened="s1", due="s2"),
        _promise("the_exception", opened="s2", due="s4", paid="s1", located=False),
    ]
    store = FakeStore(revision, records=records, promises=promises)
    loaded = bookaudit.load(store, BOOK_ID, BRANCH_ID, scenes_per_chapter=2)
    assert loaded is not None
    return loaded


def test_load_reads_scenes_keys_and_status_lines(book: bookaudit.BookFacts) -> None:
    assert [scene.ordinal for scene in book.drafted] == [1, 2, 3]
    assert book.scenes[0].story_key == "s1" and book.scenes[0].chapter == 1
    assert book.scenes[2].chapter == 2
    assert book.scene_for_key("s3") == 3
    assert book.scene_for_key("0300") == 3
    assert book.scene_for_key("nonsense") is None
    (line,) = book.scenes[1].status_lines
    assert line.subject == "Tam Cawl"
    assert dict(line.columns) == {"Mark": "2", "Seconds": "45", "Held": "1", "Rod": "1"}


def test_status_census_names_drift_falls_kind_flips_and_spellings(
    book: bookaudit.BookFacts,
) -> None:
    """§231's defect, made visible: one book, two column sets and two subject spellings."""
    census = bookaudit.status_line_report(book)
    assert sorted(census["subjects"]) == ["Tam", "Tam Cawl"]
    assert [tuple(row["labels"]) for row in census["column_sets"]] == [
        ("Mark", "Seconds", "Held"),
        ("Mark", "Seconds", "Held", "Rod"),
    ]
    (drift,) = census["drift"]
    assert drift == {
        "subject": "Tam Cawl",
        "from_scene": 1,
        "to_scene": 2,
        "added": ["Rod"],
        "removed": [],
        "reordered": False,
    }
    (fall,) = census["decreases"]
    assert (fall["column"], fall["was"], fall["now"], fall["to_scene"]) == (
        "Seconds",
        "60",
        "45",
        2,
    )
    # `Tam` is a different subject spelling, so scene 3 is compared with nothing and its
    # words-for-a-number is not a kind flip against scene 2's numbers.
    assert census["kind_flips"] == []
    assert census["silent_scenes"] == []


def test_promise_ledger_marks_overdue_unlocated_and_early(book: bookaudit.BookFacts) -> None:
    ledger = bookaudit.promise_report(book)
    assert ledger["last_drafted_scene"] == 3
    by_subject = {row["subject"]: row for row in ledger["promises"]}
    assert by_subject["the_rod"]["paid_scene"] == 2 and by_subject["the_rod"]["payment_located"]
    assert ledger["overdue"] == ["the_renter"]
    assert ledger["paid_unlocated"] == ["the_exception"]
    assert ledger["paid_early"] == ["the_exception"]
    assert ledger["open"] == 1


def test_fact_timeline_lists_moves_and_returns(book: bookaudit.BookFacts) -> None:
    facts = bookaudit.fact_timeline(book)
    (moving,) = facts["moving_facts"]
    assert moving["subject"] == "tam_cawl" and moving["predicate"] == "stands_at"
    assert moving["values"] == [
        "mark_ladder mark_one",
        "mark_ladder mark_two",
        "mark_ladder mark_one",
    ]
    assert moving["reverted"] == ["mark_ladder mark_one"]
    assert [row["scene"] for row in moving["history"]] == [1, 2, 3]
    assert bookaudit.fact_timeline(book, subject="ruth_abiola")["moving_facts"] == []


def test_cast_presence_names_scenes_gaps_and_the_never_seen(book: bookaudit.BookFacts) -> None:
    cast = bookaudit.cast_presence(book, gap=1)
    by_subject = {row["subject"]: row for row in cast["people"]}
    assert by_subject["tam_cawl"]["scenes"] == [1, 2, 3]
    assert by_subject["ruth_abiola"]["scenes"] == [1, 2]
    assert cast["never_on_page"] == ["jonah_pratt"]
    # Corridor recurs mid-sentence in every drafted scene and nobody declared it.
    assert any(row["word"] == "Corridor" for row in cast["undeclared"])


def test_report_and_attention_compose_every_view(book: bookaudit.BookFacts) -> None:
    audit = bookaudit.report(book)
    assert audit["caveat"] == bookaudit.DESCRIPTIVE_ONLY
    assert audit["scenes_drafted"] == 3 and audit["scenes_total"] == 6
    assert audit["chapters_drafted"] == 1
    assert set(bookaudit.VIEWS) <= set(audit)
    notes = bookaudit.attention(audit)
    assert "status line printed under 2 subject spellings" in notes
    assert "status line printed with 2 column sets" in notes
    assert "debt open past its due scene: the_renter" in notes
    assert "debt paid with no located quote: the_exception" in notes
    assert "declared and never named on the page: jonah_pratt" in notes
    assert any(note.startswith("tam_cawl stands_at returned") for note in notes)
    assert "drafted without a scene plan: scenes [1, 2, 3]" in notes


def test_a_view_can_be_chosen_and_an_unknown_one_refused(book: bookaudit.BookFacts) -> None:
    only = bookaudit.report(book, views=("status",))
    assert "status" in only and "promises" not in only
    with pytest.raises(ValueError, match="unknown audit view"):
        bookaudit.report(book, views=("scores",))


def test_no_head_is_none() -> None:
    class Empty(FakeStore):
        def head(self, book_id: str, branch_id: str) -> Revision | None:
            return None

    assert (
        bookaudit.load(Empty(_revision(SCENES)), BOOK_ID, BRANCH_ID, scenes_per_chapter=2) is None
    )


def test_a_line_printed_again_with_nothing_moved_is_named() -> None:
    same = "[STATUS] Tam Cawl — Mark 1 | Seconds 60"
    texts = [
        f"One.\n\n{same}",
        f"Two.\n\n{same}",
        "Three.\n\n[STATUS] Tam Cawl — Mark 2 | Seconds 60",
        "",
        "",
        "",
    ]
    loaded = bookaudit.load(FakeStore(_revision(texts)), BOOK_ID, BRANCH_ID, scenes_per_chapter=2)
    assert loaded is not None
    census = bookaudit.status_line_report(loaded)
    assert census["unmoved"] == [{"subject": "Tam Cawl", "from_scene": 1, "to_scene": 2}]
    assert "status line printed 1 time(s) with no number moved" in bookaudit.attention(
        bookaudit.report(loaded, views=("status",))
    )


def test_refrains_name_word_runs_said_in_more_than_one_scene() -> None:
    texts = [
        "It came at a reader's pace, four legs, waist high. The yard was cold.\n\n"
        "[STATUS] Tam — Mark 1 | Seconds 60",
        "Nothing else. It came at a reader's pace, four legs, waist high, and stopped.",
        "Morning. The kettle ticked. It came at a reader's pace and the corridor went white.",
        "",
        "",
        "",
    ]
    loaded = bookaudit.load(FakeStore(_revision(texts)), BOOK_ID, BRANCH_ID, scenes_per_chapter=2)
    assert loaded is not None
    census = bookaudit.refrains(loaded, words=4)
    phrases = {row["phrase"]: row["scenes"] for row in census["phrases"]}
    assert phrases["it came at a reader's pace four legs waist high"] == [1, 2]
    assert phrases["it came at a reader's pace"] == [1, 2, 3]
    # The status line's words are not prose and are not counted.
    assert not any("mark 1" in phrase for phrase in phrases)
    notes = bookaudit.attention(bookaudit.report(loaded, views=("refrains",)))
    assert any(note.startswith("2 word run(s) said in more than one scene") for note in notes)


def test_seams_name_an_opening_that_repeats_the_previous_close() -> None:
    close = "Behind the mesh the plant knocked once and started taking the room back."
    texts = [
        "The panel went blank in front of his face at the end of row D. " + close,
        "The panel had gone blank in front of his face at the end of row D, and blank was new. "
        + close
        + " Ruthanne. Pen.",
        "Morning came up grey over the lot and nobody had slept.",
        "",
        "",
        "",
    ]
    loaded = bookaudit.load(FakeStore(_revision(texts)), BOOK_ID, BRANCH_ID, scenes_per_chapter=2)
    assert loaded is not None
    found = bookaudit.seams(loaded)
    (row,) = found["restated"]
    assert (row["from_scene"], row["to_scene"], row["same_chapter"]) == (1, 2, True)
    assert "the plant knocked once and started taking the room back" in " | ".join(row["phrases"])
    assert row["shared_words"] >= 10
    notes = bookaudit.attention(bookaudit.report(loaded, views=("seams",)))
    assert any(
        note.startswith("scene 2 opens on") and note.endswith("(same chapter)") for note in notes
    )


def test_the_sheet_is_read_beside_the_page_scene_by_scene() -> None:
    """Chapter 3 of the first whole-volume draw printed Reading 0 while the world held it;
    the comparison names the column, the scene, both numbers."""
    from test_choice_points import _accepted, _system

    from litharness.domain import gamesystem, worlds

    system = _system()
    records = [_accepted(record) for record in gamesystem.records_for(system)]
    records.append(_accepted(worlds.world_record("kell", "entity_role", value="protagonist")))
    records.append(_accepted(worlds.world_record("kell", "is_a", value="Kell Marrow")))
    records.append(_accepted(worlds.world_record("kell", "stands_at", object_ref="r_second")))
    records.append(_accepted(worlds.world_record("kell", "can_do", object_ref="cap_read", value=2)))
    records.append(
        _accepted(worlds.world_record("kell", "can_do", object_ref="cap_slack", value=1))
    )
    texts = [
        "Kell stood at the desk.\n\n[STATUS] Kell — Seal 2 | Reading 2 | Slack 1",
        "Kell walked.\n\n[STATUS] Kell — Seal 1 | Reading 0 | Slack 1 | Kiln Hand 0",
        "",
        "",
        "",
        "",
    ]
    loaded = bookaudit.load(
        FakeStore(_revision(texts), records=records), BOOK_ID, BRANCH_ID, scenes_per_chapter=2
    )
    assert loaded is not None
    compared = bookaudit.sheet_vs_page(loaded)
    assert compared["comparable"] and compared["systems"] == ["sys_weave"]
    assert compared["scenes"][0]["columns"]["Reading"] == {"page": 2, "world": 2}
    assert [(m["scene"], m["column"], m["page"], m["world"]) for m in compared["mismatches"]] == [
        (2, "Seal", 1, 2),
        (2, "Reading", 0, 2),
    ]
    notes = bookaudit.attention(bookaudit.report(loaded, views=("sheet",)))
    assert "scene 2: the page prints Reading 0 and the world's edges hold 2 for kell" in notes
