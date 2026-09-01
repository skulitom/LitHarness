"""Pins for `research/quality-measurement/scorecard.py`, the per-draw scorecard.

**Hermetic.** Every chapter below is synthetic — written here to exercise a counter, not
transcribed from any book — so nothing in this file is book text, no shelf path is read, and no
corpus is opened. The market reference values are re-read from the committed results JSON where
the source is machine-readable, so a transcription typo in the scorecard fails here rather than
being printed beside a book forever.

**What these tests defend is mostly a refusal.** The scorecard describes and does not judge, and
three of the pins below exist to keep it that way: no row may be named as a score or a verdict,
no v2 row may carry a market reference (stage-0 §189.3), and every row without a reference must
say *why* it has none rather than showing an empty column.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

scorecard = pytest.importorskip(
    "scorecard",
    reason="research module; needs the quality-measurement directory on the path",
)
chapter_measures = pytest.importorskip("chapter_measures")
progression_cadence = pytest.importorskip("progression_cadence")
number_context = pytest.importorskip("number_context")
register_census = pytest.importorskip("register_census")

RESULTS = Path(__file__).resolve().parent.parent / "research" / "quality-measurement" / "results"

#: A synthetic chapter carrying one of everything the card counts: a house `[STATUS]` line, a
#: second print of it with one cell moved, a tier-A gloss, a tier-B gloss, an em dash in prose,
#: a sentence over thirty words, a four-join chain, and two mid-sentence capitals.
CHAPTER_ONE = """\
Nia set the crate down where Bram could reach it, so nobody had to ask.

[STATUS] Nia — Grip 2 | Carried 1/3

She counted the lids twice, then a third time, and she counted the straps as well, and the
tally still came out at seven, which was one short of what the docket in her pocket said it
ought to be at this hour of a Tuesday morning.

Bram said it the way people say a thing when they have said it before — flatly, and to the wall.

[STATUS] Nia — Grip 3 | Carried 1/3
"""

#: A second chapter with no furniture, no gloss and no dash, so aggregation across two chapters
#: has something to average that is not the same number twice.
CHAPTER_TWO = """\
The gate held. Bram tested it. It held again.

Rain came off the roof in one sheet.
"""


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    """A two-chapter book laid out the way the shelf lays one out."""
    chapters = tmp_path / "a-synthetic-book" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "Chapter1.txt").write_text(CHAPTER_ONE, encoding="utf-8")
    (chapters / "Chapter2.txt").write_text(CHAPTER_TWO, encoding="utf-8")
    return chapters.parent


# ------------------------------------------------------------------ the shape of the row list


def test_row_keys_are_unique() -> None:
    keys = [row.key for row in scorecard.ROWS]
    assert len(keys) == len(set(keys))


def test_every_reference_belongs_to_a_row() -> None:
    """A reference with no row is a market number nobody will ever see."""
    assert set(scorecard.REFERENCES) <= {row.key for row in scorecard.ROWS}


def test_every_row_without_a_reference_says_why() -> None:
    """An empty reference column is indistinguishable from an unmeasured one."""
    for row in scorecard.ROWS:
        if row.key not in scorecard.REFERENCES:
            assert row.no_reference, f"{row.key} has neither a reference nor a stated reason"


def test_no_v2_row_carries_a_market_reference() -> None:
    """Stage-0 §189.3: *no v2 number may be placed beside any market number, and none is*.

    The direction of the invalidity is the one that flatters us — v2 adds an accepted line
    shape and removes none, so it can only ever locate more furniture than the v0 instrument
    every published market figure was computed with. This test is that refusal, mechanised.
    """
    measured_at_v2 = [r for r in scorecard.ROWS if r.key.startswith(("cadence_v2", "numbers_v2"))]
    assert measured_at_v2, "the guard is pointless if it guards nothing"
    for row in measured_at_v2:
        assert row.key not in scorecard.REFERENCES, f"{row.key} put a v2 number beside v0"
        assert row.no_reference == scorecard.NO_REF_V2
    # The mask row also runs at v2 but is not a property of the book, so it states its own
    # reason rather than §189's. It must still carry no reference.
    assert "v2_mask_matches_pipeline" not in scorecard.REFERENCES


def test_no_row_is_a_score_or_a_verdict() -> None:
    """§61's four attainability checks stand between any row and a bar, and none has been run.

    The scorecard therefore has no aggregate, no total, no pass/fail and no threshold, and the
    cheapest way for one to arrive is a row quietly named like one.
    """
    banned = ("score", "total", "overall", "pass", "fail", "grade", "rating", "bar", "threshold")
    for row in scorecard.ROWS:
        assert not any(word in row.key.lower() for word in banned), row.key


def test_the_no_bar_line_names_section_61() -> None:
    assert "§61" in scorecard.NO_BAR
    assert "no bar" in scorecard.NO_BAR


def test_every_row_reads_a_key_the_battery_actually_produces(book: Path) -> None:
    """`path` rows are dotted lookups into `chapter_measures.battery`; a typo must fail here."""
    blob = chapter_measures.battery(CHAPTER_ONE)
    for row in scorecard.ROWS:
        if row.compute is None:
            scorecard._dig(blob, row.path)  # raises KeyError on a bad path
        else:
            row.compute(blob)


# --------------------------------------------------------- the transcribed reference values


def test_register_census_references_match_the_committed_results_file() -> None:
    """The gloss and proper-noun references are transcribed constants; this re-reads them.

    They are the two whose source is machine-readable. The cadence and number-context
    references live in prose in `progression-cadence-results.md` and `number-context-results.md`
    and stage-0 §155.1/§162, and are not re-derivable here without a corpus.
    """
    recorded = json.loads((RESULTS / "register-census.json").read_text(encoding="utf-8"))
    assert recorded["registration_digest"] == scorecard.DIGEST_REGISTER_V0
    gloss = recorded["gloss_per_1k"]
    tier_a, tier_b = gloss["market_litrpg|tier_a"], gloss["market_litrpg|tier_b"]
    assert scorecard.REFERENCES["gloss_tier_a_per_1k"].value == tier_a["mean"]
    assert scorecard.REFERENCES["gloss_tier_b_per_1k"].value == tier_b["mean"]
    assert scorecard.REFERENCES["gloss_tier_a_per_1k"].n == tier_a["n"]
    nouns = recorded["proper_noun_per_1k"]["market_litrpg"]
    assert scorecard.REFERENCES["proper_nouns_per_1k"].value == nouns["p50"]
    assert scorecard.REFERENCES["proper_nouns_per_1k"].n == nouns["n"]


def test_the_quoted_instrument_digests_are_the_live_ones() -> None:
    """A reference names the counter that produced it. If a module is edited its digest rotates
    and the scorecard's citation goes stale silently; this is how that surfaces."""
    assert progression_cadence.REGISTRATION_DIGEST == scorecard.DIGEST_CADENCE_V0
    assert progression_cadence.REGISTRATION_DIGEST_V2 == scorecard.DIGEST_CADENCE_V2
    assert number_context.REGISTRATION_DIGEST == scorecard.DIGEST_NUMBERS_V0
    assert number_context.REGISTRATION_DIGEST_V2 == scorecard.DIGEST_NUMBERS_V2
    assert register_census.registration_digest() == scorecard.DIGEST_REGISTER_V0


# ------------------------------------------------------------------------------ the counters


def test_a_moved_cell_is_reported_and_an_unmoved_one_is_not() -> None:
    """The A1 row the §184 gate cares about: does a protagonist's own number change on the page?"""
    moved = chapter_measures.status_profile(CHAPTER_ONE)
    assert moved["status_lines"] == 2
    assert moved["any_number_moved"] is True
    assert moved["cells_moved"] == ["Nia:Grip 2->3"]

    still = CHAPTER_ONE.replace("Grip 3", "Grip 2")
    assert chapter_measures.status_profile(still)["any_number_moved"] is False


def test_the_scorecard_reports_the_moved_cell(book: Path) -> None:
    card = scorecard.build(book)
    rows = {row["key"]: row for row in card.rows}
    assert rows["status_number_moved"]["value"] is True
    assert rows["status_cells_moved"]["value"] == ["Nia:Grip 2->3"]
    assert rows["status_lines"]["value"] == 2


def test_aggregation_uses_the_rule_each_row_names(book: Path) -> None:
    """Counts sum, rates mean, booleans reduce with `any`, name lists union. A column silently
    averaged when it should have been summed is the failure this pins."""
    card = scorecard.build(book)
    rows = {row["key"]: row for row in card.rows}
    assert len(card.chapters) == 2
    # summed across both chapters, and chapter 2 carries no furniture
    assert rows["status_lines"]["per_chapter"] == {"Chapter1": 2, "Chapter2": 0}
    assert rows["status_lines"]["value"] == 2
    # a share is over this book's chapters, not over the market
    assert rows["carries_status_line"]["value"] == 0.5
    # `any` over the two chapters
    assert rows["status_number_moved"]["value"] is True
    # every row records both the aggregate and what it was aggregated from
    for row in card.rows:
        assert set(row["per_chapter"]) == {"Chapter1", "Chapter2"}
        assert "aggregation" in row


def test_gloss_and_em_dash_are_counted_on_prose_not_on_the_status_lines(book: Path) -> None:
    """The `[STATUS]` line's own subject separator is U+2014, so a file-level em-dash count is
    furniture and not voice."""
    card = scorecard.build(book)
    rows = {row["key"]: row for row in card.rows}
    assert rows["em_dash_in_prose"]["per_chapter"]["Chapter1"] == 1
    assert rows["gloss_tier_a"]["per_chapter"]["Chapter1"] >= 1
    assert rows["gloss_tier_b"]["per_chapter"]["Chapter1"] >= 1
    assert rows["gloss_tier_a"]["per_chapter"]["Chapter2"] == 0


def test_the_long_sentence_and_the_chain_are_both_seen(book: Path) -> None:
    card = scorecard.build(book)
    rows = {row["key"]: row for row in card.rows}
    assert rows["sentence_words_max"]["value"] > 30
    assert rows["chain_4plus_share"]["per_chapter"]["Chapter1"] > 0


def test_the_v2_mask_still_agrees_with_the_pipelines_own_rule(book: Path) -> None:
    """The research modules transcribe `draft._SYSTEM_LINE` rather than importing it. This row
    is the check that the transcription has not drifted; a value below 1.0 means it has."""
    card = scorecard.build(book)
    rows = {row["key"]: row for row in card.rows}
    assert rows["v2_mask_matches_pipeline"]["value"] == 1.0


# ----------------------------------------------------------------------------- inputs and IO


def test_chapters_sort_numerically_not_lexically(tmp_path: Path) -> None:
    """`Chapter10` follows `Chapter9`. Lexical order puts it after `Chapter1` and silently
    reorders every per-chapter column."""
    chapters = tmp_path / "book" / "chapters"
    chapters.mkdir(parents=True)
    for n in (1, 2, 9, 10):
        (chapters / f"Chapter{n}.txt").write_text(CHAPTER_TWO, encoding="utf-8")
    found = [p.stem for p in scorecard.chapter_paths(chapters.parent)]
    assert found == ["Chapter1", "Chapter2", "Chapter9", "Chapter10"]


def test_a_single_chapter_file_is_a_valid_target(tmp_path: Path) -> None:
    one = tmp_path / "Chapter1.txt"
    one.write_text(CHAPTER_ONE, encoding="utf-8")
    card = scorecard.build(one)
    assert card.chapters == ["Chapter1.txt"]


def test_a_directory_with_no_chapters_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        scorecard.chapter_paths(tmp_path)


def test_main_writes_utf8_json_with_lf_and_prints_the_no_bar_line(
    book: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "card.json"
    assert scorecard.main([str(book), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "§61" in printed
    raw = out.read_bytes()
    assert b"\r\n" not in raw, "the repo is LF and core.autocrlf is global on this box"
    card = json.loads(raw.decode("utf-8"))
    assert card["no_bar"] == scorecard.NO_BAR
    assert {row["key"] for row in card["rows"]} == {row.key for row in scorecard.ROWS}
    # the JSON keeps the whole battery per chapter, so a later question does not need a re-run
    assert set(card["per_chapter"]) == {"Chapter1", "Chapter2"}


def test_the_table_shows_the_refusal_reason_in_full(book: Path) -> None:
    """A refusal cut in half reads as a shorter claim than it is, so the reference column wraps
    rather than truncating."""
    table = scorecard.render(scorecard.build(book))
    assert "v2 incomparable" in table
    assert "§189.3" in table
    assert "DETECTOR MISMATCH" in table, "the system-line reference's limitation must be visible"
