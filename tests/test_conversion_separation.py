"""Hermetic pins on the pure core of ``research/quality-measurement/conversion_separation.py``.

Pinned: what ``deciles``, ``separation``, ``permuted_band``, ``era_auc``, ``stratified``,
``_verdict`` and ``report`` return on constructed inputs whose answers were derived by hand
from the code before running anything — the decile floor and its tenth-of-the-table boundary,
rank-AUC tie handling, the null band's collapse points, the era control's cohort filter, band
pooling and its small-band guard, the verdict's branch order, and ``summarise_stories``'
grouping and filtering (through a stubbed shard loader and stubbed craft scorers, so no
corpus and no real metric is touched).

Not established: anything about the cached RoyalRoad shards, the four refuted metrics' own
arithmetic, the statistical validity of the conversion label, the CLI, or result-file output.
An empty table is exercised for ``deciles``, ``separation``, ``permuted_band`` and
``era_auc``; ``stratified`` on a truly empty list raises on ``min()`` before it can answer,
so its smallest case here is a nine-row table whose bands cannot be split.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

conversion_separation = pytest.importorskip(
    "conversion_separation",
    reason="research module; needs the quality-measurement directory on the path",
)

#: Every column `report` and `stratified` read off a story row: the five CRAFT metrics plus
#: the four prose-blind baselines. Constructed rows carry all of them.
METRICS = (
    "dialogue_ratio",
    "opening_shape_repetition",
    "sentence_length_cv",
    "tricolon_rate",
    "word_count",
    "chapters_seen",
    "mean_words",
    "log_views",
    "followers",
)


def story_row(index: int, **columns: Any) -> dict[str, Any]:
    """A full row in which every metric column reads `index`; overrides win."""
    row: dict[str, Any] = {name: float(index) for name in METRICS}
    row.update({"work_id": f"s{index}", "conversion": float(index), "cohort": None})
    row.update(columns)
    return row


# --------------------------------------------------------------------------- separation


def test_separation_is_one_when_every_top_value_beats_every_bottom_value():
    top = [{"word_count": 2.0}, {"word_count": 3.0}]
    bottom = [{"word_count": 0.0}, {"word_count": 1.0}]
    assert conversion_separation.separation(top, bottom, "word_count") == 1.0


def test_separation_is_zero_when_every_top_value_ranks_below_every_bottom_value():
    top = [{"word_count": 0.0}, {"word_count": 1.0}]
    bottom = [{"word_count": 2.0}, {"word_count": 3.0}]
    assert conversion_separation.separation(top, bottom, "word_count") == 0.0


def test_separation_gives_half_credit_for_each_ordered_pair_win_on_partial_overlap():
    # Pairs won: 1<2 loses, 1<3 loses, 4>2 wins, 4>3 wins -> 2 of 4 -> 0.5.
    top = [{"word_count": 1.0}, {"word_count": 4.0}]
    bottom = [{"word_count": 2.0}, {"word_count": 3.0}]
    assert conversion_separation.separation(top, bottom, "word_count") == 0.5


def test_separation_counts_a_tie_between_the_deciles_as_half_a_win():
    top = [{"word_count": 2.0}]
    bottom = [{"word_count": 2.0}]
    assert conversion_separation.separation(top, bottom, "word_count") == 0.5


def test_separation_returns_half_for_an_empty_side_instead_of_crashing():
    assert conversion_separation.separation([], [], "word_count") == 0.5


def test_separation_reads_only_the_column_it_is_named():
    # By word_count the top decile is above; by followers it is below. The name decides.
    top = [{"word_count": 5.0, "followers": 1.0}]
    bottom = [{"word_count": 1.0, "followers": 9.0}]
    assert conversion_separation.separation(top, bottom, "followers") == 0.0
    assert conversion_separation.separation(top, bottom, "word_count") == 1.0


# ------------------------------------------------------------------------------ deciles


def test_deciles_of_ten_stories_pick_the_single_highest_and_lowest_by_conversion():
    rows = [{"conversion": float(i)} for i in range(1, 11)]
    top, bottom = conversion_separation.deciles(rows)
    assert [row["conversion"] for row in top] == [10.0]
    assert [row["conversion"] for row in bottom] == [1.0]


def test_deciles_of_twenty_stories_take_two_per_side():
    rows = [{"conversion": float(i)} for i in range(1, 21)]
    top, bottom = conversion_separation.deciles(rows)
    assert [row["conversion"] for row in top] == [19.0, 20.0]
    assert [row["conversion"] for row in bottom] == [1.0, 2.0]


def test_deciles_of_nineteen_stories_still_take_one_per_side():
    rows = [{"conversion": float(i)} for i in range(1, 20)]
    top, bottom = conversion_separation.deciles(rows)
    assert [row["conversion"] for row in top] == [19.0]
    assert [row["conversion"] for row in bottom] == [1.0]


def test_deciles_of_three_stories_bottom_out_at_one_per_side():
    rows = [{"conversion": 3.0}, {"conversion": 1.0}, {"conversion": 2.0}]
    top, bottom = conversion_separation.deciles(rows)
    assert [row["conversion"] for row in top] == [3.0]
    assert [row["conversion"] for row in bottom] == [1.0]


def test_deciles_of_an_empty_list_are_two_empty_lists():
    assert conversion_separation.deciles([]) == ([], [])


def test_deciles_sort_by_the_key_they_are_given_not_always_conversion():
    rows = [
        {"conversion": 1.0, "followers": 100.0},
        {"conversion": 2.0, "followers": 300.0},
        {"conversion": 3.0, "followers": 200.0},
    ]
    top, bottom = conversion_separation.deciles(rows, key="followers")
    assert [row["followers"] for row in top] == [300.0]
    assert [row["followers"] for row in bottom] == [100.0]


# ------------------------------------------------------------------------- permuted_band


def band_rows(labels: list[float], values: list[float]) -> list[dict[str, Any]]:
    return [
        {"conversion": label, "word_count": value}
        for label, value in zip(labels, values, strict=True)
    ]


def test_permuted_band_collapses_to_half_when_the_metric_column_is_constant():
    rows = band_rows([float(i) for i in range(1, 11)], [7.0] * 10)
    assert conversion_separation.permuted_band(rows, "word_count", draws=5) == (0.5, 0.5)


def test_permuted_band_collapses_to_the_point_estimate_when_the_label_has_no_variance():
    # With every label equal, shuffling changes nothing, the pairing sorts by value, and the
    # decile split is the true extremes — so every draw scores 1.0 and the band is a point.
    rows = band_rows([0.5] * 10, [float(i) for i in range(1, 11)])
    assert conversion_separation.permuted_band(rows, "word_count", draws=5) == (1.0, 1.0)


def test_permuted_band_of_one_story_is_half():
    rows = band_rows([0.5], [3.0])
    assert conversion_separation.permuted_band(rows, "word_count", draws=5) == (0.5, 0.5)


def test_permuted_band_of_an_empty_list_is_half():
    assert conversion_separation.permuted_band([], "word_count", draws=5) == (0.5, 0.5)


def test_permuted_band_is_identical_across_calls_with_the_same_seed():
    labels = [float(i) for i in range(1, 11)]
    values = [1.0, 3.0, 2.0, 5.0, 4.0, 7.0, 6.0, 9.0, 8.0, 10.0]
    rows = band_rows(labels, values)
    assert conversion_separation.permuted_band(rows, "word_count", draws=5) == (
        conversion_separation.permuted_band(rows, "word_count", draws=5)
    )


# ------------------------------------------------------------------------------- era_auc


def era_rows(recent: list[float], older: list[float]) -> list[dict[str, Any]]:
    rows = [{"cohort": "undeclared_2025", "word_count": v} for v in recent]
    rows += [{"cohort": "human_pre_llm", "word_count": v} for v in older]
    return rows


def test_era_auc_is_one_when_every_recent_story_beats_every_older_story():
    rows = era_rows([2.0, 3.0], [0.0, 1.0])
    assert conversion_separation.era_auc(rows, "word_count") == 1.0


def test_era_auc_is_zero_when_every_recent_story_ranks_below_every_older_story():
    rows = era_rows([0.0, 1.0], [2.0, 3.0])
    assert conversion_separation.era_auc(rows, "word_count") == 0.0


def test_era_auc_counts_a_tied_score_as_half_a_win():
    assert conversion_separation.era_auc(era_rows([2.0], [2.0]), "word_count") == 0.5


def test_era_auc_ignores_stories_outside_the_two_era_cohorts():
    rows = era_rows([2.0, 3.0], [0.0, 1.0])
    rows += [
        {"cohort": None, "word_count": 100.0},
        {"cohort": "declared_2025", "word_count": 0.0},
    ]
    assert conversion_separation.era_auc(rows, "word_count") == 1.0


def test_era_auc_is_nan_without_both_cohorts_present():
    assert math.isnan(conversion_separation.era_auc([], "word_count"))
    assert math.isnan(conversion_separation.era_auc(era_rows([1.0], []), "word_count"))
    only_other = [{"cohort": None, "word_count": 1.0}]
    assert math.isnan(conversion_separation.era_auc(only_other, "word_count"))


# ----------------------------------------------------------------------------- stratified


def test_stratified_pools_a_monotone_metric_to_a_perfect_auc_across_three_bands_of_twenty():
    # conversion, followers and word_count all read i: inside each 20-story band the decile
    # split is two a side and word_count separates it perfectly. A band of exactly 20 counts.
    rows = [story_row(i) for i in range(1, 61)]
    block = conversion_separation.stratified(rows, by="followers")
    assert block["by"] == "followers"
    assert block["min_band"] == 20
    assert block["per_band"]["word_count"] == [1.0, 1.0, 1.0]
    assert block["pooled_auc"]["word_count"] == 1.0


def test_stratified_pools_band_aucs_of_one_zero_and_half_to_a_half():
    # Band 1 tracks the label (auc 1.0), band 2 runs against it (auc 0.0), band 3 is constant
    # (ties at half, auc 0.5). Equal band sizes pool to (1 + 0 + 0.5) / 3 = 0.5.
    rows = []
    for i in range(1, 61):
        band = (i - 1) // 20
        word_count = {0: float(i), 1: -float(i), 2: 100.0}[band]
        rows.append(story_row(i, word_count=word_count))
    block = conversion_separation.stratified(rows, by="followers")
    assert block["per_band"]["word_count"] == [1.0, 0.0, 0.5]
    assert block["pooled_auc"]["word_count"] == 0.5


def test_stratified_with_bands_smaller_than_twenty_reports_nan_and_no_per_band_numbers():
    rows = [story_row(i) for i in range(1, 10)]
    block = conversion_separation.stratified(rows, by="followers")
    assert block["min_band"] == 3
    assert block["per_band"]["word_count"] == []
    assert math.isnan(block["pooled_auc"]["word_count"])


# ------------------------------------------------------------------------------- _verdict


def test_a_best_prose_metric_inside_its_null_band_reads_no_separation_even_with_a_big_margin():
    best_prose = {"outside_null": False, "conversion_auc": 0.90}
    best_blind = {"conversion_auc": 0.60}
    assert conversion_separation._verdict(best_prose, best_blind).startswith("NO SEPARATION")


def test_a_blind_baseline_with_a_larger_margin_reads_separation_is_prose_blind():
    best_prose = {"outside_null": True, "conversion_auc": 0.55}
    best_blind = {"conversion_auc": 0.60}
    assert conversion_separation._verdict(best_prose, best_blind).startswith(
        "SEPARATION IS PROSE-BLIND"
    )


def test_exactly_equal_margins_break_toward_the_prose_blind_reading():
    # Margins are both 0.10; the >= comparison means the baseline still decides.
    best_prose = {"outside_null": True, "conversion_auc": 0.60}
    best_blind = {"conversion_auc": 0.40}
    assert conversion_separation._verdict(best_prose, best_blind).startswith(
        "SEPARATION IS PROSE-BLIND"
    )


def test_an_outside_null_prose_metric_with_the_larger_margin_reads_provisionally():
    best_prose = {"outside_null": True, "conversion_auc": 0.70}
    best_blind = {"conversion_auc": 0.55}
    assert conversion_separation._verdict(best_prose, best_blind).startswith(
        "PROSE SEPARATES, PROVISIONALLY"
    )


def test_a_below_chance_prose_metric_still_reads_provisionally_on_absolute_margin():
    # Margin 0.30 against the baseline's 0.05: direction does not matter, distance does.
    best_prose = {"outside_null": True, "conversion_auc": 0.20}
    best_blind = {"conversion_auc": 0.55}
    assert conversion_separation._verdict(best_prose, best_blind).startswith(
        "PROSE SEPARATES, PROVISIONALLY"
    )


# ---------------------------------------------------------------------- summarise_stories

#: Deterministic stand-ins for the five CRAFT scorers, so the tests pin grouping and
#: filtering rather than the refuted metrics' own arithmetic.
STUB_METRICS: dict[str, Any] = {
    "dialogue_ratio": lambda text: float(text.count('"')),
    "opening_shape_repetition": lambda text: float(len(text)),
    "sentence_length_cv": lambda text: float(len(text.split())),
    "tricolon_rate": lambda text: 1.0,
    "word_count": lambda text: float(len(text.split())),
}


@pytest.fixture
def stub_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversion_separation, "CRAFT", dict(STUB_METRICS))


@pytest.fixture
def shard_loader(monkeypatch: pytest.MonkeyPatch):
    """Replaces the corpus loader; returns an installer recording the kwargs it receives."""
    calls: list[dict[str, Any]] = []

    def install(units: list[SimpleNamespace]):
        def fake_loader(**kwargs: Any):
            calls.append(kwargs)
            return iter(units)

        monkeypatch.setattr(conversion_separation, "royalroad_chapters", fake_loader)
        return calls

    return install


def chapter(
    work_id: str,
    *,
    conversion: float | None = 0.05,
    followers: float = 50.0,
    total_views: float = 4000.0,
    cohort: str | None = "human_pre_llm",
    text: str = 'he said "no"',
) -> SimpleNamespace:
    meta: dict[str, Any] = {
        "followers": followers,
        "total_views": total_views,
        "cohort": cohort,
    }
    if conversion is not None:
        meta["conversion"] = conversion
    return SimpleNamespace(work_id=work_id, meta=meta, text=text)


def test_a_story_is_one_row_with_each_metric_averaged_over_its_chapters(
    shard_loader, stub_metrics
):
    shard_loader(
        [
            chapter("s", text='he said "hello there"'),
            chapter("s", text="no quotes here"),
        ]
    )
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=0.0, limit=0
    )
    assert len(rows) == 1
    assert rows[0]["work_id"] == "s"
    assert rows[0]["chapters_seen"] == 2.0
    # 'he said "hello there"' is 4 words with 2 quote marks; 'no quotes here' is 3 words.
    assert rows[0]["mean_words"] == 3.5
    assert rows[0]["sentence_length_cv"] == 3.5
    assert rows[0]["dialogue_ratio"] == 1.0
    assert rows[0]["tricolon_rate"] == 1.0


def test_a_story_with_fewer_chapters_than_min_chapters_is_dropped(shard_loader, stub_metrics):
    shard_loader([chapter("thin"), chapter("full"), chapter("full")])
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=2, min_views=0.0, limit=0
    )
    assert [row["work_id"] for row in rows] == ["full"]


def test_a_story_at_min_views_survives_while_a_story_below_it_is_dropped(
    shard_loader, stub_metrics
):
    shard_loader([chapter("lo", total_views=999.0), chapter("hi", total_views=1000.0)])
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=1000.0, limit=0
    )
    assert [row["work_id"] for row in rows] == ["hi"]


def test_a_chapter_without_a_conversion_label_produces_no_story_row(shard_loader, stub_metrics):
    shard_loader([chapter("ghost", conversion=None), chapter("real", conversion=0.1)])
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=0.0, limit=0
    )
    assert [row["work_id"] for row in rows] == ["real"]


def test_a_story_spanning_both_eras_gets_no_cohort_while_a_unanimous_story_keeps_its(
    shard_loader, stub_metrics
):
    shard_loader(
        [
            chapter("straddle", cohort="human_pre_llm"),
            chapter("straddle", cohort="undeclared_2025"),
            chapter("pure", cohort="undeclared_2025"),
            chapter("pure", cohort="undeclared_2025"),
        ]
    )
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=0.0, limit=0
    )
    by_id = {row["work_id"]: row for row in rows}
    assert by_id["straddle"]["cohort"] is None
    assert by_id["pure"]["cohort"] == "undeclared_2025"


def test_a_story_whose_scorer_fails_on_every_chapter_is_dropped(shard_loader, monkeypatch):
    def broken_on_sentinel(text: str) -> float:
        if "BOOM" in text:
            raise ValueError("unscorable")
        return float(text.count('"'))

    metrics = dict(STUB_METRICS)
    metrics["dialogue_ratio"] = broken_on_sentinel
    monkeypatch.setattr(conversion_separation, "CRAFT", metrics)
    shard_loader([chapter("doomed", text="BOOM"), chapter("fine")])
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=0.0, limit=0
    )
    assert [row["work_id"] for row in rows] == ["fine"]


def test_a_failed_chapter_only_removes_itself_from_the_metric_that_crashed(
    shard_loader, monkeypatch
):
    def selective(text: str) -> float:
        if "BOOM" in text:
            raise ValueError("unscorable")
        return float(text.count('"'))

    metrics = dict(STUB_METRICS)
    metrics["dialogue_ratio"] = selective
    monkeypatch.setattr(conversion_separation, "CRAFT", metrics)
    shard_loader([chapter("partial", text="BOOM"), chapter("partial", text='"yes"')])
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=0.0, limit=0
    )
    assert len(rows) == 1
    # Only the surviving chapter feeds dialogue_ratio; word_count averaged over both
    # ('BOOM' and '"yes"' are one word each).
    assert rows[0]["dialogue_ratio"] == 2.0
    assert rows[0]["mean_words"] == 1.0


def test_log_views_floors_total_views_at_one_so_zero_view_stories_survive(
    shard_loader, stub_metrics
):
    shard_loader([chapter("zero", total_views=0.0), chapter("kilo", total_views=1000.0)])
    rows = conversion_separation.summarise_stories(
        shards=(3,), min_chapters=1, min_views=0.0, limit=0
    )
    by_id = {row["work_id"]: row for row in rows}
    assert by_id["zero"]["log_views"] == 0.0
    assert by_id["kilo"]["log_views"] == 3.0


def test_shards_and_limit_are_forwarded_to_the_shard_loader(shard_loader, stub_metrics):
    calls = shard_loader([])
    conversion_separation.summarise_stories(
        shards=(7, 9), min_chapters=2, min_views=1.0, limit=5
    )
    assert calls == [{"shards": (7, 9), "limit": 5}]


# --------------------------------------------------------------------------------- report


def test_report_reads_a_variance_free_label_as_no_separation_inside_a_point_null():
    # Every label equal: the stable sort makes the last row the top decile and the first row
    # the bottom, every monotone column scores 1.0, and every permutation reproduces the same
    # 1.0 — so the whole table sits inside a point null and the verdict refuses to separate.
    rows = [story_row(i, conversion=0.5) for i in range(1, 11)]
    result = conversion_separation.report(rows, draws=3)
    table = {entry["metric"]: entry for entry in result["table"]}
    assert result["stories"] == 10
    assert result["decile_size"] == 1
    assert result["permutation_draws"] == 3
    assert result["cohorts"] == {None: 10}
    for name in METRICS:
        assert table[name]["conversion_auc"] == 1.0
        assert table[name]["null_p05"] == 1.0
        assert table[name]["null_p95"] == 1.0
        assert table[name]["outside_null"] is False
    assert result["verdict"].startswith("NO SEPARATION")
    assert result["label_components"] == {"followers": 1.0, "log_views": 1.0}
    for key in ("stratified_by_followers", "stratified_by_length"):
        block = result[key]
        assert all(math.isnan(value) for value in block["pooled_auc"].values())
        assert all(not per_band for per_band in block["per_band"].values())


def test_report_ranks_a_monotone_metric_at_one_and_a_constant_metric_at_half():
    # word_count tracks the label (headline 1.0), mean_words runs against it (0.0), the rest
    # are constant (ties at half, and a point null at 0.5 so outside_null is deterministically
    # False). Cohorts sit on the ends, so the era control sees the same directions.
    def era_row(index: int) -> dict[str, Any]:
        cohort = None
        if index == 1:
            cohort = "human_pre_llm"
        elif index == 10:
            cohort = "undeclared_2025"
        return story_row(
            index,
            cohort=cohort,
            dialogue_ratio=7.0,
            opening_shape_repetition=7.0,
            sentence_length_cv=7.0,
            tricolon_rate=7.0,
            chapters_seen=7.0,
            mean_words=-float(index),
        )

    result = conversion_separation.report([era_row(i) for i in range(1, 11)], draws=3)
    table = {entry["metric"]: entry for entry in result["table"]}
    assert result["permutation_draws"] == 3
    assert table["word_count"]["reads_prose"] is True
    assert table["word_count"]["conversion_auc"] == 1.0
    assert table["word_count"]["era_auc"] == 1.0
    assert table["mean_words"]["conversion_auc"] == 0.0
    assert table["mean_words"]["era_auc"] == 0.0
    assert table["dialogue_ratio"]["conversion_auc"] == 0.5
    assert table["dialogue_ratio"]["outside_null"] is False
    assert table["chapters_seen"]["reads_prose"] is False
    assert result["label_components"] == {"followers": 1.0, "log_views": 1.0}
