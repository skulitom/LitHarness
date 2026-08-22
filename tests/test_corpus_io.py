"""Hermetic pins on the pure helpers of research/quality-measurement/corpus_io.py.

These tests pin: `Unit.words` counting, `era_cohort`'s cohort boundaries and drop rules,
`by_story`'s grouping, ordering and five-chapter minimum, `_shard_path` against a fabricated
HF-cache layout (the real cache is never touched), and `fixture_scenes` reading the golden
books shipped inside the installed `litharness_contracts` package.

They do not establish anything about the Mother-of-Learning or RoyalRoad loaders (they read
files on this machine), `generated_scenes` (it opens a book database), or any CLI or model
path. Passing says the pure plumbing is correct; it says nothing about whether the corpora
these loaders exist to read are present, current, or valid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

corpus_io = pytest.importorskip(
    "corpus_io",
    reason="research module; needs the quality-measurement directory on the path",
)


def _make_unit(
    *,
    unit_id: str = "c1",
    work_id: str = "w",
    text: str = "some prose",
    released_at: str | None = None,
    position: int = 0,
) -> corpus_io.Unit:
    return corpus_io.Unit(
        unit_id=unit_id,
        source="test",
        text=text,
        position=position,
        work_id=work_id,
        released_at=released_at,
    )


# ------------------------------------------------------------------------------ Unit.words


def test_words_counts_whitespace_separated_tokens():
    assert _make_unit(text="one two three").words == 3


def test_words_counts_tokens_across_mixed_whitespace_runs():
    assert _make_unit(text="  alpha\nbeta\t\rgamma  ").words == 3


def test_words_is_zero_for_an_empty_text():
    assert _make_unit(text="").words == 0


# ------------------------------------------------------------------------------ era_cohort


def test_era_cohort_classifies_a_pre_2023_chapter_as_human_pre_llm():
    assert corpus_io.era_cohort("2021-07-14T09:00:00Z", '["Fanfiction"]') == "human_pre_llm"


def test_era_cohort_drops_a_pre_llm_chapter_whose_story_declared_ai_assistance():
    assert corpus_io.era_cohort("2021-07-14T09:00:00Z", '["AI-Assisted Content"]') is None


def test_era_cohort_classifies_a_declared_chapter_from_2025_onward_as_declared_ai_2025():
    assert corpus_io.era_cohort("2025-03-01T00:00:00Z", '["AI-Assisted Content"]') == (
        "declared_ai_2025"
    )


def test_era_cohort_classifies_an_undeclared_chapter_from_2025_onward_as_undeclared_2025():
    assert corpus_io.era_cohort("2026-08-22T00:00:00Z", '["Fantasy"]') == "undeclared_2025"


def test_era_cohort_keeps_2022_drops_2023_and_2024_and_reopens_at_2025():
    assert corpus_io.era_cohort("2022-12-31T23:59:59Z", "[]") == "human_pre_llm"
    assert corpus_io.era_cohort("2023-01-01T00:00:00Z", "[]") is None
    assert corpus_io.era_cohort("2024-12-31T23:59:59Z", "[]") is None
    assert corpus_io.era_cohort("2025-01-01T00:00:00Z", "[]") == "undeclared_2025"


def test_era_cohort_returns_none_for_a_missing_release_date():
    assert corpus_io.era_cohort(None, "[]") is None


def test_era_cohort_returns_none_for_an_empty_release_date_and_missing_warnings():
    assert corpus_io.era_cohort("", None) is None


def test_era_cohort_treats_missing_warnings_as_no_declaration():
    assert corpus_io.era_cohort("2025-06-01T00:00:00Z", None) == "undeclared_2025"


# -------------------------------------------------------------------------------- by_story


def test_by_story_groups_units_by_work_id():
    first = [_make_unit(work_id="w1", unit_id=f"w1:c{i}") for i in range(3)]
    second = [_make_unit(work_id="w2", unit_id=f"w2:c{i}") for i in range(3)]
    grouped = corpus_io.by_story(first + second, min_chapters=3)
    assert set(grouped) == {"w1", "w2"}
    assert {unit.unit_id for unit in grouped["w1"]} == {"w1:c0", "w1:c1", "w1:c2"}


def test_by_story_orders_a_stories_chapters_by_release_date():
    late = _make_unit(unit_id="c-late", released_at="2024-02-02")
    early = _make_unit(unit_id="c-early", released_at="2020-01-01")
    mid = _make_unit(unit_id="c-mid", released_at="2022-06-15")
    grouped = corpus_io.by_story([late, early, mid], min_chapters=2)
    assert [unit.unit_id for unit in grouped["w"]] == ["c-early", "c-mid", "c-late"]


def test_by_story_sorts_a_unit_with_no_release_date_before_any_dated_unit():
    undated = _make_unit(unit_id="c-undated", released_at=None)
    dated = _make_unit(unit_id="c-dated", released_at="2020-01-01")
    grouped = corpus_io.by_story([dated, undated], min_chapters=2)
    assert [unit.unit_id for unit in grouped["w"]] == ["c-undated", "c-dated"]


def test_by_story_breaks_a_release_date_tie_on_unit_id():
    b = _make_unit(unit_id="b", released_at="2023-01-01")
    a = _make_unit(unit_id="a", released_at="2023-01-01")
    c = _make_unit(unit_id="c", released_at="2023-01-01")
    grouped = corpus_io.by_story([b, c, a], min_chapters=2)
    assert [unit.unit_id for unit in grouped["w"]] == ["a", "b", "c"]


def test_by_story_keeps_a_story_meeting_the_default_five_chapter_minimum():
    units = [_make_unit(unit_id=f"c{i}") for i in range(5)]
    assert list(corpus_io.by_story(units)) == ["w"]


def test_by_story_drops_a_story_one_chapter_short_of_the_default_minimum():
    units = [_make_unit(unit_id=f"c{i}") for i in range(4)]
    assert corpus_io.by_story(units) == {}

def test_by_story_returns_an_empty_dict_when_given_no_units():
    assert corpus_io.by_story([]) == {}




# ----------------------------------------------------------------------------- _shard_path


def test_shard_path_returns_the_pinned_snapshot_file_over_a_decoy_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoy = tmp_path / "snapshots" / ("d" * 40) / "data" / "train-00009-of-00047.parquet"
    pinned = tmp_path / "snapshots" / corpus_io.SNAPSHOT_REVISION / "data" / (
        "train-00009-of-00047.parquet"
    )
    decoy.parent.mkdir(parents=True)
    decoy.touch()
    pinned.parent.mkdir(parents=True)
    pinned.touch()
    monkeypatch.setattr(corpus_io, "HF_CACHE", tmp_path)
    corpus_io._shard_path.cache_clear()
    assert corpus_io._shard_path(9) == pinned


def test_shard_path_raises_when_the_pinned_snapshot_file_is_absent_from_the_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(corpus_io, "HF_CACHE", tmp_path)
    corpus_io._shard_path.cache_clear()
    with pytest.raises(FileNotFoundError):
        corpus_io._shard_path(11)


# -------------------------------------------------------------------------- fixture_scenes


def _skip_without_golden_fixtures() -> None:
    pytest.importorskip(
        "litharness_contracts.fixtures",
        reason="fixture_scenes reads golden books shipped in litharness_contracts",
    )


def test_fixture_scenes_returns_the_six_mystery_scenes_in_reading_order():
    _skip_without_golden_fixtures()
    scenes = corpus_io.fixture_scenes("mystery")
    assert [scene.unit_id for scene in scenes] == [
        f"mystery:scene-{number}" for number in range(1, 7)
    ]
    assert [scene.position for scene in scenes] == [1, 2, 3, 4, 5, 6]


def test_fixture_scenes_labels_every_mystery_scene_as_a_fixture_of_that_book():
    _skip_without_golden_fixtures()
    scenes = corpus_io.fixture_scenes("mystery")
    assert all(scene.source == "fixture" and scene.work_id == "mystery" for scene in scenes)


def test_fixture_scenes_carries_each_nodes_title_into_meta():
    _skip_without_golden_fixtures()
    by_position = {scene.position: scene for scene in corpus_io.fixture_scenes("mystery")}
    assert by_position[1].meta["title"] == "The Study"
    assert by_position[6].meta["title"] == "The Ledger Closes"


def test_fixture_scenes_skips_non_scene_nodes_so_only_scened_prose_is_returned():
    _skip_without_golden_fixtures()
    # The mystery manuscript opens with a 'book' node titled "The Vane House"; it holds no
    # scene prose and must not surface as a measurable unit.
    scenes = corpus_io.fixture_scenes("mystery")
    assert all(scene.meta["title"] != "The Vane House" for scene in scenes)
    assert all(scene.text for scene in scenes)


def test_fixture_scenes_reads_the_litrpg_book_too():
    _skip_without_golden_fixtures()
    scenes = corpus_io.fixture_scenes("litrpg")
    assert len(scenes) == 6
    assert {scene.work_id for scene in scenes} == {"litrpg"}
    assert scenes[0].unit_id == "litrpg:scene-1"
