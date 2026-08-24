"""The backtest corpus module's deterministic core, checked on synthetic rows only.

What this file pins: field extraction and JSON decoding in `fiction_from_rows` (with its two
refusals), the derived counts and their None branches, all three paths of the chapters-1-3
rule at PREREG §2 including the three-cached-chapters boundary, every eligibility slug with
the refusal order pinned, the matching-cell bands at their exact bounds, and the divergent
pairing's greedy on a hand-built cell whose correct pairing is stated before anything runs.
Every expectation below is derived by hand from the design; follower counts in the pairing
tests are chosen as multiples over 8192 so conversions are exact binary fractions and ratio
comparisons carry no floating-point accident. What this file does not establish: anything
about real shard data — no parquet is read here, `load_fiction_rows` is only asserted to
exist and to name its venv, and nothing in this module ever calls a model or a network.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)

module = pytest.importorskip("corpus", reason="research module; imported by path")

corpus_io = pytest.importorskip("corpus_io", reason="research module; imported by path")

#: Thirty words clears the blurb floor exactly; twenty-nine does not.
BLURB_FLOOR = 30


def _blurb(words: int) -> str:
    return " ".join(f"scene{index}" for index in range(words))


DEFAULT_DATES = (
    "2025-02-01T00:00:00Z",
    "2025-02-02T00:00:00Z",
    "2025-02-03T00:00:00Z",
)


def _rows(
    fiction_id: str = "f1",
    *,
    author: str = "Ann",
    tags: str = '["LitRPG"]',
    warnings: str = "[]",
    description: str | None = None,
    status: str | None = None,
    followers: float = 30.0,
    total_views: float = 600.0,
    average_views: float = 200.0,
    chapters: tuple[tuple[str, str, int], ...] | None = None,
) -> list[dict[str, Any]]:
    """Hand-built dump rows for one fiction; `chapters` are (title, release_datetime, words)."""
    description = _blurb(BLURB_FLOOR) if description is None else description
    if chapters is None:
        chapters = tuple(
            zip(
                ("Chapter 1", "Chapter 2", "Chapter 3"),
                DEFAULT_DATES,
                (1500, 1501, 1502),
                strict=True,
            )
        )
    return [
        {
            "fiction_id": fiction_id,
            "title": f"Book {fiction_id}",
            "author": author,
            "tags": tags,
            "warnings": warnings,
            "description": description,
            "status": status,
            "followers": followers,
            "total_views": total_views,
            "average_views": average_views,
            "chapter_id": f"{fiction_id}-c{position}",
            "chapter_title": title,
            "release_datetime": released_at,
            "words": words,
        }
        for position, (title, released_at, words) in enumerate(chapters)
    ]


def _fic(fiction_id: str = "f1", **overrides: Any):
    return module.fiction_from_rows(_rows(fiction_id, **overrides))


def _member(fiction_id: str, author: str, followers: int, *, tags: str = '["LitRPG"]'):
    """A pairing-test member: mid-band (recovered 16), conversion an exact dyadic fraction.

    views 8192 / average_views 512 recovers 16 chapters, and followers/8192 is a binary
    fraction, so ratios between members are exact floats — the 3x floor boundary can be hit
    precisely rather than approximately.
    """
    return _fic(
        fiction_id,
        author=author,
        tags=tags,
        followers=float(followers),
        total_views=8192.0,
        average_views=512.0,
    )


# ----------------------------------------------------------- fiction_from_rows


def test_fiction_from_rows_extracts_the_dump_fields_and_decodes_the_json_columns() -> None:
    fiction = module.fiction_from_rows(
        _rows(
            "f9",
            author="Bo",
            tags='["LitRPG", "High Fantasy"]',
            warnings=f'["{corpus_io.AI_WARNING}"]',
            description="A slow-burn cartography litRPG about maps that redraw themselves.",
            status="Ongoing",
            followers=45.0,
            total_views=900.0,
            average_views=300.0,
        )
    )
    assert fiction.fiction_id == "f9"
    assert fiction.title == "Book f9"
    assert fiction.author == "Bo"
    assert fiction.tags == ("LitRPG", "High Fantasy")
    assert fiction.warnings == (corpus_io.AI_WARNING,)
    assert fiction.status == "Ongoing"
    assert fiction.followers == 45.0
    assert fiction.total_views == 900.0
    assert fiction.average_views == 300.0
    # Earliest chapter date, not the first row's.
    assert fiction.first_release == DEFAULT_DATES[0]
    # Words carried per chapter from the synthetic rows (1500, 1501, 1502).
    assert [chapter.words for chapter in fiction.chapters] == [1500, 1501, 1502]


def test_fiction_from_rows_sorts_chapters_by_release_then_ordinal_with_none_last() -> None:
    # Two chapters share a timestamp; the unparsable title sorts after the parsed ordinal
    # there (sentinel, not crash), and the earlier-dated chapter leads overall.
    fiction = module.fiction_from_rows(
        _rows(
            "f1",
            chapters=(
                ("Chapter 2", "2025-02-01T00:00:00Z", 1500),
                ("Interlude", "2025-02-01T00:00:00Z", 1501),
                ("Chapter 1", "2025-01-01T00:00:00Z", 1502),
            ),
        )
    )
    assert [chapter.chapter_id for chapter in fiction.chapters] == [
        "f1-c2",
        "f1-c0",
        "f1-c1",
    ]
    assert [chapter.ordinal for chapter in fiction.chapters] == [1, 2, None]


def test_fiction_from_rows_refuses_rows_spanning_two_fiction_ids() -> None:
    with pytest.raises(ValueError, match="mixed fiction_ids"):
        module.fiction_from_rows([*_rows("f1"), *_rows("f2")])


def test_fiction_from_rows_refuses_an_empty_row_sequence() -> None:
    with pytest.raises(ValueError, match="empty"):
        module.fiction_from_rows([])


def test_fiction_from_rows_survives_a_minimal_row_carrying_no_optional_fields() -> None:
    # Every row is a chapter row by construction, so the single bare row still yields one
    # degenerate chapter — what must not happen is a crash on the missing columns.
    fiction = module.fiction_from_rows([{"fiction_id": "m1"}])
    assert fiction.fiction_id == "m1"
    assert fiction.tags == ()
    assert fiction.warnings == ()
    assert fiction.description == ""
    assert fiction.status is None
    assert len(fiction.chapters) == 1
    assert fiction.chapters[0].ordinal is None
    assert fiction.chapters[0].words == 0
    assert fiction.first_release == ""


# --------------------------------------------- recovered count, conversion


def test_recovered_chapter_count_rounds_total_views_over_average_views() -> None:
    # Hand-derived: round(1000 / 300) = round(3.33) = 3; round(1200 / 400) = 3 exactly.
    assert module.recovered_chapter_count(_fic(total_views=1000.0, average_views=300.0)) == 3
    assert module.recovered_chapter_count(_fic(total_views=1200.0, average_views=400.0)) == 3


def test_recovered_chapter_count_is_none_when_average_views_is_zero() -> None:
    assert module.recovered_chapter_count(_fic(average_views=0.0)) is None


def test_conversion_is_followers_over_total_views() -> None:
    assert module.conversion(_fic(followers=30.0, total_views=600.0)) == pytest.approx(0.05)


def test_conversion_is_none_when_total_views_is_zero() -> None:
    assert module.conversion(_fic(total_views=0.0)) is None


# ------------------------------------------------------------- chapters 1-3


def test_chapters_1_to_3_returns_parsed_ordinals_in_ordinal_order_when_all_present() -> None:
    # Five chapters, release order scrambled relative to ordinal order; ordinals
    # {1, 2, 3, 7} parse, so the ordinal path wins and chapter 7 stays out.
    fiction = module.fiction_from_rows(
        _rows(
            "f1",
            chapters=(
                ("Chapter 3", "2025-02-03T00:00:00Z", 1500),
                ("Prologue", "2025-02-01T00:00:00Z", 1200),
                ("Chapter 1", "2025-01-05T00:00:00Z", 1400),
                ("Chapter 7", "2025-03-01T00:00:00Z", 1600),
                ("Chapter 2", "2025-02-02T00:00:00Z", 1450),
            ),
        )
    )
    opening = module.chapters_1_to_3(fiction)
    assert opening is not None
    assert [chapter.ordinal for chapter in opening] == [1, 2, 3]
    assert [chapter.chapter_id for chapter in opening] == ["f1-c2", "f1-c4", "f1-c0"]


def test_chapters_1_to_3_falls_back_to_release_order_when_the_dump_holds_the_whole_fiction(
) -> None:
    # No title parses to an ordinal; four cached chapters against a recovered count of
    # exactly 4 (round(800 / 200)) proves the dump holds the whole fiction.
    dates = (
        "2025-02-01T00:00:00Z",
        "2025-02-02T00:00:00Z",
        "2025-02-03T00:00:00Z",
        "2025-02-04T00:00:00Z",
    )
    fiction = module.fiction_from_rows(
        _rows(
            "f1",
            total_views=800.0,
            average_views=200.0,
            chapters=tuple(
                zip(("Arrival", "Market Day", "The Gate", "Deep"), dates, (2000,) * 4, strict=True)
            ),
        )
    )
    assert module.recovered_chapter_count(fiction) == 4
    opening = module.chapters_1_to_3(fiction)
    assert opening is not None
    assert [chapter.chapter_id for chapter in opening] == ["f1-c0", "f1-c1", "f1-c2"]


def test_three_cached_chapters_suffice_only_when_the_recovered_count_is_three() -> None:
    # The fallback's lower boundary sits at exactly three cached chapters: enough when the
    # recovered count is 3 (round(900 / 300)), not when it is 4 (round(1200 / 300)).
    titles_dates = tuple(
        zip(("Arrival", "Market Day", "The Gate"), DEFAULT_DATES, (2000, 2000, 2000), strict=True)
    )
    enough = module.fiction_from_rows(
        _rows("f1", total_views=900.0, average_views=300.0, chapters=titles_dates)
    )
    assert module.chapters_1_to_3(enough) is not None
    too_few = module.fiction_from_rows(
        _rows("f1", total_views=1200.0, average_views=300.0, chapters=titles_dates)
    )
    assert module.recovered_chapter_count(too_few) == 4
    assert module.chapters_1_to_3(too_few) is None


def test_chapters_1_to_3_is_none_for_partial_ordinals_and_an_incomplete_cache() -> None:
    # Ordinals {1, 2} are present but 3 is missing; three cached chapters against a
    # recovered count of round(5000 / 500) = 10 leaves neither path available.
    fiction = module.fiction_from_rows(
        _rows(
            "f1",
            total_views=5000.0,
            average_views=500.0,
            chapters=(
                ("Chapter 1", DEFAULT_DATES[0], 1500),
                ("Chapter 2", DEFAULT_DATES[1], 1500),
                ("Interlude", DEFAULT_DATES[2], 1400),
            ),
        )
    )
    assert module.chapters_1_to_3(fiction) is None


# --------------------------------------------------------------- eligibility


def test_the_registered_view_floor_is_three_hundred() -> None:
    # PREREG §1 stamps the floor; a change here is a registration event, not an edit.
    assert module.VIEW_FLOOR == 300


def test_a_fully_eligible_fiction_returns_none_from_eligibility() -> None:
    # The default construction clears every rule: undeclared 2025 cohort, thirty-word
    # blurb, parsed ordinals 1-3, 600 views over the floor, conversion 0.05.
    assert module.eligibility(_fic()) is None


def test_a_declared_ai_fiction_is_refused_as_declared_ai() -> None:
    fiction = _fic(warnings=f'["{corpus_io.AI_WARNING}"]')
    assert module.eligibility(fiction) == "declared_ai"


def test_a_fiction_outside_every_cohort_is_refused_as_no_cohort() -> None:
    # 2024 is inside neither era_cohort branch: not pre-2023, not 2025+.
    fiction = _fic(
        chapters=(
            ("Chapter 1", "2024-06-01T00:00:00Z", 1500),
            ("Chapter 2", "2024-06-02T00:00:00Z", 1500),
            ("Chapter 3", "2024-06-03T00:00:00Z", 1500),
        )
    )
    assert module.eligibility(fiction) == "no_cohort"


def test_a_blurb_under_thirty_words_is_refused_and_thirty_words_clears_it() -> None:
    short = _fic(description=_blurb(BLURB_FLOOR - 1))
    assert len(short.description.split()) == BLURB_FLOOR - 1
    assert module.eligibility(short) == "blurb_short"
    exact = _fic(description=_blurb(BLURB_FLOOR))
    assert module.eligibility(exact) is None


def test_a_fiction_without_identifiable_chapters_one_to_three_is_refused_as_no_ch123() -> None:
    fiction = _fic(
        description=_blurb(40),
        total_views=5000.0,
        average_views=100.0,  # recovers 50 from only 3 cached, untitled-opening rows
        chapters=(
            ("Arrival", DEFAULT_DATES[0], 1500),
            ("Market Day", DEFAULT_DATES[1], 1500),
            ("The Gate", DEFAULT_DATES[2], 1500),
        ),
    )
    assert module.chapters_1_to_3(fiction) is None
    assert module.eligibility(fiction) == "no_ch123"


def test_total_views_below_the_floor_is_low_exposure_and_at_the_floor_passes() -> None:
    under = _fic(total_views=299.0)
    assert module.eligibility(under) == "low_exposure"
    at_floor = _fic(total_views=300.0, followers=15.0, average_views=100.0)  # recovered 3
    assert module.conversion(at_floor) == pytest.approx(0.05)
    assert module.eligibility(at_floor) is None


def test_zero_followers_leave_no_usable_outcome_so_the_fiction_is_refused_as_no_outcome() -> None:
    # Views clear the floor, so this is the one slug low_exposure cannot pre-empt: a
    # conversion of exactly zero cannot anchor a ratio pair.
    fiction = _fic(followers=0.0)
    assert module.conversion(fiction) == 0.0
    assert module.eligibility(fiction) == "no_outcome"


def test_a_fiction_failing_two_rules_reports_the_first_slug_in_the_fixed_order() -> None:
    declared_first = _fic(warnings=f'["{corpus_io.AI_WARNING}"]', description="Two words only")
    assert module.eligibility(declared_first) == "declared_ai"
    uncohorted_second = _fic(
        description="Two words only",
        chapters=(
            ("Chapter 1", "2024-06-01T00:00:00Z", 1500),
            ("Chapter 2", "2024-06-02T00:00:00Z", 1500),
            ("Chapter 3", "2024-06-03T00:00:00Z", 1500),
        ),
    )
    assert module.eligibility(uncohorted_second) == "no_cohort"


# ------------------------------------------------------------------- cells


def test_cell_key_carries_cohort_lead_family_band_and_normalised_status() -> None:
    # Default construction: undeclared-2025 cohort, LitRPG lead, recovered 3 (short band),
    # unrecorded status normalised to "".
    assert module.cell_key(_fic()) == ("undeclared_2025", "LitRPG", "short", "")
    recorded = _fic(status="Ongoing")
    assert module.cell_key(recorded)[3] == "Ongoing"


def test_cell_key_band_bounds_sit_at_seven_eight_and_twenty_four_twenty_five() -> None:
    def band_for(views: float, average: float) -> str:
        return module.cell_key(_fic(total_views=views, average_views=average))[2]

    # Hand-derived recovered counts: 7, 8, 24, 25 — all exact integer divisions.
    assert band_for(8400.0, 1200.0) == "short"   # round(7)
    assert band_for(8000.0, 1000.0) == "mid"     # round(8)
    assert band_for(9600.0, 400.0) == "mid"      # round(24)
    assert band_for(10000.0, 400.0) == "long"    # round(25)


def test_an_unrecoverable_chapter_count_bands_as_unknown() -> None:
    assert module.cell_key(_fic(average_views=0.0))[2] == "unknown"


def test_lead_tag_family_takes_the_first_listed_lead_tag_not_the_first_tag() -> None:
    assert module.cell_key(_fic(tags='["High Fantasy", "LitRPG"]'))[1] == "LitRPG"
    assert module.cell_key(_fic(tags='["Romance", "Comedy"]'))[1] == "other"


# --------------------------------------------------------- divergent pairing


def test_pairing_pairs_highest_against_lowest_with_an_author_conflict_skipped() -> None:
    # One cell, four members, conversions exact: p=.0234375 (Ann), q=.0078125 (Bo),
    # r=.005859375 (Cyd), s=.001953125 (Ann). Stated before running:
    #   round 1 — high p; lowest s shares p's author, so it is skipped, and r pairs at
    #             .0234375/.005859375 = exactly 4.0, committing authors Ann and Cyd;
    #   round 2 — high q's only remaining partner is s, but Ann is spent, so s leaves the
    #             pool and no second pair can form. §79's disjointness costs s its pairing.
    members = [
        _member("p", "Ann", 192),
        _member("q", "Bo", 64),
        _member("r", "Cyd", 48),
        _member("s", "Ann", 16),
    ]
    pairs = module.divergent_pairs(members)
    assert [(pair.high, pair.low) for pair in pairs] == [("p", "r")]
    assert pairs[0].ratio == pytest.approx(4.0)
    used = [fid for pair in pairs for fid in (pair.high, pair.low)]
    assert len(used) == len(set(used)) == 2
    authors_by_id = {fiction.fiction_id: fiction.author for fiction in members}
    spent_authors = {authors_by_id[fid] for fid in used}
    assert len(spent_authors) == len(used)  # no author appears twice across the output
    assert all(pair.cell == ("undeclared_2025", "LitRPG", "mid", "") for pair in pairs)


def test_a_conversion_ratio_of_exactly_the_minimum_is_paired() -> None:
    # 192/8192 over 64/8192 is exactly 3.0, and the floor is inclusive.
    pairs = module.divergent_pairs([_member("hi", "Ann", 192), _member("lo", "Bo", 64)])
    assert [(pair.high, pair.low) for pair in pairs] == [("hi", "lo")]
    assert pairs[0].ratio == pytest.approx(3.0)


def test_a_pair_below_the_ratio_floor_produces_nothing() -> None:
    # 176/8192 over 64/8192 is exactly 2.75 — near, but under the registered 3x gap.
    pairs = module.divergent_pairs([_member("hi", "Ann", 176), _member("lo", "Bo", 64)])
    assert pairs == []


def test_author_disjointness_holds_across_cells_so_a_shared_author_pairs_only_once() -> None:
    # Two cells, each internally pairable at ratio 4.0, but Ann writes the high member of
    # both. Cells run in sorted key order ("High Fantasy" < "LitRPG"), so the High Fantasy
    # pair consumes Ann first and the LitRPG cell is left with one usable member.
    fantasy = [
        _member("f-hi", "Ann", 192, tags='["High Fantasy"]'),
        _member("f-lo", "Cyd", 64, tags='["High Fantasy"]'),
    ]
    litrpg = [_member("l-hi", "Ann", 192), _member("l-lo", "Bo", 64)]
    pairs = module.divergent_pairs(fantasy + litrpg)
    assert len(pairs) == 1
    assert {pairs[0].high, pairs[0].low} == {"f-hi", "f-lo"}
    authors_by_id = {fiction.fiction_id: fiction.author for fiction in fantasy + litrpg}
    assert {authors_by_id[fid] for fid in (pairs[0].high, pairs[0].low)} == {"Ann", "Cyd"}


def test_ineligible_members_are_ignored_and_a_lone_member_pairs_with_nothing() -> None:
    paired_cell = [
        _member("g-hi", "Xan", 192),
        _member("g-lo", "Yue", 64),
        _fic("g-ai", author="Zed", warnings=f'["{corpus_io.AI_WARNING}"]', followers=float(10**6)),
    ]
    lone_cell = [_fic("h-only", author="Wren", tags='["Sci-fi"]')]
    pairs = module.divergent_pairs(paired_cell + lone_cell)
    # The declared-AI member would have been a tempting high; eligibility removes it and
    # the g-cell still pairs. The Sci-fi singleton produces nothing.
    assert [(pair.high, pair.low) for pair in pairs] == [("g-hi", "g-lo")]


def test_divergent_pairs_output_is_independent_of_input_order() -> None:
    members = [
        _member("p", "Ann", 192),
        _member("q", "Bo", 64),
        _member("r", "Cyd", 48),
        _member("s", "Ann", 16),
    ]
    assert module.divergent_pairs(members) == module.divergent_pairs(list(reversed(members)))


def test_pair_id_is_sha256_over_the_sorted_ids_so_it_is_order_free_and_content_addressed() -> None:
    members = [_member("p", "Ann", 192), _member("r", "Cyd", 48)]
    (pair,) = module.divergent_pairs(members)
    expected = hashlib.sha256(b"p\x00r").hexdigest()[:16]
    assert pair.pair_id == expected
    assert len(pair.pair_id) == 16
    int(pair.pair_id, 16)
    reversed_run = module.divergent_pairs(list(reversed(members)))
    assert reversed_run[0].pair_id == pair.pair_id


# ------------------------------------------------------- cache address, loader


def test_excerpt_digest_is_sha256_hex_over_utf8_bytes_and_stable() -> None:
    digest = module.excerpt_digest("Kade counted the coins twice.")
    assert digest == hashlib.sha256(b"Kade counted the coins twice.").hexdigest()
    assert digest == module.excerpt_digest("Kade counted the coins twice.")
    assert digest != module.excerpt_digest("kade counted the coins twice.")
    assert len(digest) == 64


def test_load_fiction_rows_exists_names_its_pyarrow_venv_and_is_never_imported_here() -> None:
    assert callable(module.load_fiction_rows)
    doc = module.load_fiction_rows.__doc__ or ""
    assert "pyarrow" in doc
    assert "MirrorBench" in doc  # the venv that carries pyarrow, named per house convention
    # The lazy-import rule, pinned structurally: importing this module must not pull pyarrow.
    assert "pyarrow" not in sys.modules


def test_chapter_text_is_carried_and_words_derive_from_it_without_a_words_column() -> None:
    """The real dump carries `text` and no `words`; the arms excerpt `Chapter.text`.

    Added with the integration amendment: the module brief's original Chapter shape had no
    text field and named a words column the dump does not carry.
    """
    fiction = module.fiction_from_rows(
        [
            {
                "fiction_id": "t1",
                "chapter_id": "t1-c0",
                "chapter_title": "Chapter 1",
                "release_datetime": DEFAULT_DATES[0],
                "text": "Dawn came late over the harbour.",
            }
        ]
    )
    assert fiction.chapters[0].text == "Dawn came late over the harbour."
    assert fiction.chapters[0].words == 6
