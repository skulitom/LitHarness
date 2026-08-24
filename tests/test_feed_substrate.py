"""The feed substrate's builders and corpus report, checked without calls or corpora.

What this file pins: the intact arm's deterministic seating (first three competitors, order
preserved, both counts named on a refusal), the three control arms' relationship to their texts
(placebo byte-identical; whitespace and rename arms touching the competitors and never the
target), the report that lists short members rather than dropping them, and the two loaders'
file shapes and error paths — all on synthetic text, with `corpus_io.generated_scenes` faked.
Every expected chunk count is derived by hand before anything runs: a paragraph of exactly
`feed_core.CHUNK_WORDS` words is one `bcr.chunks` chunk (the chunker never splits a paragraph),
so N such paragraphs are N chunks, and `MIN_CHUNKS_FEED` = MIDSTREAM_CHUNK + BUDGET_UNITS //
READ_COST = 3 + 8 = 11 of them is the floor a full-length member sits on.

What this file does not establish: anything about any reader, and nothing about
`feed_core` itself — its arithmetic is pinned in `tests/test_feed_core.py`, not here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

feed_substrate = pytest.importorskip(
    "feed_substrate",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
corpus_io = pytest.importorskip(
    "corpus_io",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


# ------------------------------------------------------------------------ synthetic members


def _paragraph(marker: str) -> str:
    """Exactly CHUNK_WORDS words: one whole bcr.chunks chunk by construction."""
    return " ".join(f"{marker}-{index}" for index in range(feed_substrate.feed_core.CHUNK_WORDS))


def _book(paragraphs: int, marker: str = "w") -> str:
    return "\n\n".join(_paragraph(f"{marker}{p}") for p in range(paragraphs))


# ---------------------------------------------------------------------------------- the arms


def test_intact_feed_takes_the_first_three_competitors_in_the_order_given() -> None:
    target = ("t0", _book(11, "t"))
    competitors = [(f"c{i}", _book(11, f"c{i}")) for i in range(1, 6)]
    spec = feed_substrate.intact_feed("f1", target, competitors)
    assert spec.arm == "intact"
    assert spec.target == target[1]
    assert len(spec.others) == feed_substrate.feed_core.FEED_SIZE - 1
    assert spec.others == (competitors[0][1], competitors[1][1], competitors[2][1])
    assert spec.note == "target=t0 others=c1,c2,c3"


def test_intact_feed_with_too_few_competitors_raises_naming_both_counts() -> None:
    target = ("t0", _book(11, "t"))
    with pytest.raises(ValueError, match=r"2 competitor\(s\).*needs 3"):
        feed_substrate.intact_feed(
            "f1", target, [("c1", _book(11, "c1")), ("c2", _book(11, "c2"))]
        )


@pytest.mark.parametrize("build", ["placebo_feed", "whitespace_feed", "rename_feed"], ids=str)
def test_control_builders_refuse_an_empty_text(build: str) -> None:
    builder = getattr(feed_substrate, build)
    with pytest.raises(ValueError, match="empty"):
        builder("f1", "   \n  ")


def test_intact_feed_refuses_an_empty_competitor_and_target() -> None:
    target = ("t0", "")
    with pytest.raises(ValueError, match="target text is empty"):
        feed_substrate.intact_feed(
            "f1", target, [("c1", _book(11)), ("c2", _book(11)), ("c3", _book(11))]
        )
    with pytest.raises(ValueError, match="competitor c2 is empty"):
        feed_substrate.intact_feed(
            "f1", ("t0", _book(11)), [("c1", _book(11)), ("c2", ""), ("c3", _book(11))]
        )


def test_placebo_feed_makes_four_byte_identical_members_with_no_fault_at_full_length() -> None:
    text = _book(feed_substrate.feed_core.MIN_CHUNKS_FEED)
    spec = feed_substrate.placebo_feed("f1", text)
    assert spec.arm == "fp1_placebo"
    assert spec.target == text
    assert spec.others == (text, text, text)
    assert len(spec.texts()) == feed_substrate.feed_core.FEED_SIZE
    assert spec.fault() is None


def test_whitespace_feed_damages_reshapeable_bytes_and_leaves_the_target_identical() -> None:
    # Sentence-final single spaces before capitals are what rewhitespace reshapes; the target
    # member must come back as the exact input bytes.
    text = (
        "Ada counted the coins twice. She paid without looking up.\n\n"
        "The gatekeeper wanted five more. Ada paid again. Nobody spoke."
    )
    spec = feed_substrate.whitespace_feed("f1", text)
    assert spec.arm == "fp3_whitespace"
    assert spec.target == text, "the intact arm must leave the target untouched"
    assert all(other != text for other in spec.others), "rewhitespace must move some bytes"
    assert len(set(spec.others)) == 1, (
        "at strength 1.0 the standing transform is deterministic, so identical copies are "
        "expected and accepted"
    )


def test_rename_feed_renames_a_recognisable_name_and_leaves_the_target_identical() -> None:
    # "Marrow" appears three times, mid-sentence at least once, and never lowercase — exactly
    # the shape ablate.rename_entities selects; every other capitalised token is too rare.
    text = (
        "Marrow spoke to Marrow quietly. Nobody saw Marrow leave.\n\n"
        "The road stayed quiet until morning."
    )
    spec = feed_substrate.rename_feed("f1", text)
    assert spec.arm == "fp4_rename"
    assert spec.target == text, "the intact arm must leave the target untouched"
    assert all(other != text for other in spec.others), "rename_entities must move some bytes"
    assert "Marrow" not in spec.others[0]
    assert len(set(spec.others)) == 1, (
        "at strength 1.0 the standing transform is deterministic, so identical copies are "
        "expected and accepted"
    )


def test_short_texts_build_without_raising_because_fault_is_the_callers_check() -> None:
    # Shortness surfaces through fault() and the report, never as an exception from a builder.
    for builder in (
        feed_substrate.placebo_feed,
        feed_substrate.whitespace_feed,
        feed_substrate.rename_feed,
    ):
        spec = builder("f-short", "One short scene.")
        assert isinstance(spec.fault(), str)


# -------------------------------------------------------------------------------- the report


def test_the_report_counts_a_mixed_corpus_and_lists_its_short_members() -> None:
    # 11 paragraphs clear exactly; 12 clear with room; 2 do not. Chunk counts derived by hand:
    # one CHUNK_WORDS-word paragraph per chunk.
    texts = {
        "long-a": _book(11, "a"),
        "long-b": _book(12, "b"),
        "short-one": _book(2, "s"),
    }
    report = feed_substrate.substrate_report(texts)
    assert report["members"] == 3
    assert report["clearing"] == 2
    assert report["short"] == 1
    assert report["short_names"] == ["short-one"]
    assert report["per_member"]["long-a"] == {
        "chunks": feed_substrate.feed_core.MIN_CHUNKS_FEED,
        "clears": True,
    }
    assert report["per_member"]["long-b"] == {"chunks": 12, "clears": True}
    assert report["per_member"]["short-one"] == {"chunks": 2, "clears": False}


def test_a_member_at_exactly_min_chunks_clears_and_one_paragraph_fewer_does_not() -> None:
    floor = feed_substrate.feed_core.MIN_CHUNKS_FEED
    at_floor = feed_substrate.substrate_report({"at-floor": _book(floor)})
    assert at_floor["clearing"] == 1
    assert at_floor["short_names"] == []
    below = feed_substrate.substrate_report({"below-floor": _book(floor - 1)})
    assert below["clearing"] == 0
    assert below["short_names"] == ["below-floor"]


def test_an_empty_corpus_reports_zero_members_without_dropping_anything() -> None:
    report = feed_substrate.substrate_report({})
    assert report == {"members": 0, "clearing": 0, "short": 0, "short_names": [], "per_member": {}}


# ---------------------------------------------------------------------------------- the loads


def test_load_scene_texts_reads_unit_ids_and_texts_from_a_bcr_shaped_json(tmp_path: Path) -> None:
    path = tmp_path / "scenes.json"
    path.write_text(
        json.dumps(
            {
                "scenes": [
                    {"unit_id": "toll:s1", "text": "First scene."},
                    {"unit_id": "toll:s2", "text": "Second scene."},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert feed_substrate.load_scene_texts(path) == {
        "toll:s1": "First scene.",
        "toll:s2": "Second scene.",
    }


def test_load_scene_texts_on_a_missing_file_raises_naming_the_path(tmp_path: Path) -> None:
    absent = tmp_path / "absent.json"
    with pytest.raises(FileNotFoundError) as excinfo:
        feed_substrate.load_scene_texts(absent)
    assert str(absent) in str(excinfo.value)


def test_fitness_texts_reads_each_database_sorted_by_filename_and_joins_scenes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "fitness"
    directory.mkdir()
    for name in ("fitness-00.db", "fitness-01.db", "fitness-02.db"):
        (directory / name).write_text("stub — the loader is faked below", encoding="utf-8")

    calls: list[Path] = []

    def fake_generated_scenes(database: Path, **_: object) -> list[corpus_io.Unit]:
        calls.append(Path(database))
        book = Path(database).stem
        return [
            corpus_io.Unit(
                unit_id=f"gen:{book}:scene-{index}",
                source="generated",
                text=f"Scene {index} of {book}.",
                position=index,
                work_id=book,
            )
            for index in (1, 2)
        ]

    monkeypatch.setattr(feed_substrate.corpus_io, "generated_scenes", fake_generated_scenes)

    texts = feed_substrate.fitness_texts(directory)

    assert [name for name, _ in texts] == ["fitness-00", "fitness-01", "fitness-02"], (
        "filename order is the seating order; discovery order must not leak in"
    )
    assert dict(texts)["fitness-01"] == "Scene 1 of fitness-01.\n\nScene 2 of fitness-01."
    assert calls == [directory / "fitness-00.db", directory / "fitness-01.db",
                     directory / "fitness-02.db"]


def test_fitness_texts_on_a_missing_directory_raises_naming_it(tmp_path: Path) -> None:
    absent = tmp_path / "nowhere"
    with pytest.raises(FileNotFoundError) as excinfo:
        feed_substrate.fitness_texts(absent)
    assert str(absent) in str(excinfo.value)


def test_fitness_texts_over_a_directory_with_no_databases_returns_an_empty_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(feed_substrate.corpus_io, "generated_scenes", lambda db, **_: [])
    assert feed_substrate.fitness_texts(empty) == []


def test_fitness_texts_takes_the_largest_book_from_a_store_holding_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed driver attempt can leave a second book in a database; the export layer then
    refuses without --book (measured on the delivered shelf; fitness_books.word_count's
    docstring records it). A shelf member is one book: the largest single one is the member."""
    directory = tmp_path / "fitness"
    directory.mkdir()
    (directory / "fitness-07.db").write_text("stub", encoding="utf-8")
    big = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    big_branch = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    small = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    small_branch = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    def fake_generated_scenes(
        database: Path, *, book: str | None = None, branch: str | None = None, **_: object
    ) -> list[corpus_io.Unit]:
        if book is None:
            lines = [
                "2 branches match; name one with --book and --branch:",
                f"  --book {big} --branch {big_branch}",
                f"  --book {small} --branch {small_branch}",
            ]
            raise ValueError(chr(10).join(lines))
        words = "many words here indeed truly" if book == big else "few"
        return [
            corpus_io.Unit(
                unit_id=f"gen:{book}:s1",
                source="generated",
                text=words,
                position=1,
                work_id=book,
            )
        ]

    monkeypatch.setattr(feed_substrate.corpus_io, "generated_scenes", fake_generated_scenes)
    texts = feed_substrate.fitness_texts(directory)
    assert texts == [("fitness-07", "many words here indeed truly")]
