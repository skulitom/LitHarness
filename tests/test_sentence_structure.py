"""Punctuation normalization preserves interruptions, status extraction and stored provenance."""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain import voice
from litharness.domain.draft import strip_em_dash
from litharness.domain.events import EventType
from tests.conftest import FIXTURE_SHEET
from tests.test_draft import START, conductor_for, registry_with, seeded

MARK = voice.EXHIBITION_MARKERS["em_dash"]


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "sentence-structure.db")


def test_the_spaced_habit_becomes_a_comma() -> None:
    text, removed = strip_em_dash(f"He set it down {MARK} the wrong hand {MARK} and waited.")
    assert text == "He set it down, the wrong hand, and waited."
    assert removed == 2


def test_the_mark_survives_where_it_is_a_device_and_not_a_habit() -> None:
    for line in (f'"You have no business {MARK}"', f'"Dan{MARK}"', f"He turned{MARK}"):
        text, removed = strip_em_dash(line)
        assert text == line
        assert removed == 0


def test_immediacy_is_what_separates_the_device_from_the_habit() -> None:
    text, removed = strip_em_dash(f'He shrugged {MARK} "fine" {MARK} and left.')
    assert MARK not in text
    assert removed == 2


def test_a_status_line_still_parses_after_the_strip() -> None:
    line = FIXTURE_SHEET.template.format(
        subject="Theo", level=3, hp=10, hp_max=12, mp=1, mp_max=4, gold=7
    )
    scene = f"He put it down {MARK} and looked.\n\n{line}\n\nThe room went quiet."
    stripped, removed = strip_em_dash(scene)

    assert removed == 1, "the prose mark goes and the machine's separator does not"
    match = FIXTURE_SHEET.pattern.search(stripped)
    assert match is not None
    assert match.group("subject") == "Theo"
    assert match.group("level") == "3"


def test_a_stop_does_not_collect_a_second_comma() -> None:
    text, removed = strip_em_dash(f"He stopped, {MARK} then went on.")
    assert text == "He stopped, then went on."
    assert removed == 1


def test_the_strip_is_idempotent_and_leaves_clean_prose_alone() -> None:
    original = f"She waited {MARK} counting {MARK} and the door opened."
    once, first = strip_em_dash(original)
    twice, second = strip_em_dash(once)
    assert twice == once
    assert second == 0
    assert first == 2

    clean = "She waited, counting, and the door opened."
    assert strip_em_dash(clean) == (clean, 0)


def test_the_mark_comes_from_its_one_registered_home() -> None:
    assert MARK == "\u2014"
    assert strip_em_dash(f"a {MARK} b")[1] == 1
    assert strip_em_dash("a \u2013 b") == ("a \u2013 b", 0), (
        "the en dash is a different character and a different question; `statusline` accepts "
        "it where `extraction` does not, and that divergence is not this track's to settle"
    )


def test_a_drafted_scene_reaches_the_store_without_the_mark(store: SqliteStore) -> None:
    prose = (
        f"Rook set the lantern on the ledger stone {MARK} the one that had not cracked {MARK} "
        "and counted what the night had cost him. Forty-five gold in, twenty gone to the flame, "
        "five more to the gatekeeper who had not looked up. He wrote none of it down. The tally "
        f"lived where it always had {MARK} behind his teeth, where no clerk could reach it, and "
        "he had never once been wrong about it before tonight."
    )
    registry, _ = registry_with(prose)
    seeded(store)

    conductor_for(store, registry).tick(START)

    accepted = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
    ]
    assert len(accepted) == 1
    assert accepted[0].payload["em_dashes_removed"] == 3

    committed = store.load_revision(accepted[0].revision_id or "")
    content = committed.node("scene-1").content or ""
    assert MARK not in content
    assert "ledger stone, the one that had not cracked, and counted" in content
