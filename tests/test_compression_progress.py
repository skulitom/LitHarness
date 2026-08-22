"""Hermetic tests for the pure core of `compression_progress` (track F3).

What is pinned: the two-stratum pairing and its declared tolerances (`pair_fictions`), the
rung arithmetic, cache replay and replicate semantics of the scorer (`learnability_slope`),
the tokenizer-only memory screen (`ladder_fits`), the pair split with its recorded causes
(`fit_filter`), the pre-pairing feasibility filter and its chapter slice
(`feasible_fictions`), the donor rotation (`donor_prose`), the harness translation
(`as_force_pairs_static`), the `Fiction` record, and the module's own selftest.

What they do not establish: anything about real NLL, real tokenizers or real corpora. Every
attribute the module touches on `force_gpu` is replaced with word counting and synthetic
logprobs whose slopes are known before the call, so a pass here proves control flow and
arithmetic, never model behaviour. `survey` and `chapter_texts` read parquet shards through
`corpus_io` and are deliberately untouched, as are every forward pass, database, results
file, CLI path, sleep and subprocess in the module.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

SKIP = "research module; needs the quality-measurement directory on the path"
compression_progress = pytest.importorskip("compression_progress", reason=SKIP)

force_gpu = compression_progress.force_gpu

FAMILIES = ("gemma", "qwen")


# ------------------------------------------------------------------ force_gpu stand-ins


class StubGPU:
    """Replaces what `compression_progress` touches on `force_gpu`; nothing leaves the process.

    Token counts are word counts, the ceiling is a dial, and `token_logprobs` returns
    synthetic values: NLL_true stays at `true_nats` at every rung while NLL_foreign sits
    `foreign_gap(rung)` above it. The scorer therefore reads gaps the test chose, and every
    expected slope is derivable by hand rather than observed.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, ceiling: int = 1_000) -> None:
        self.ceiling = ceiling
        self.true_nats = 1.0
        self.foreign_gap = self._half_nat_per_rung
        self.blank_foreign_rungs: frozenset[int] = frozenset()
        #: every prefix handed to `token_logprobs`, true contexts at odd indices
        self.prefixes: list[str] = []
        self.true_prefixes: list[str] = []
        self.tokenizer_calls = 0
        monkeypatch.setattr(force_gpu, "context_limit", self._context_limit)
        monkeypatch.setattr(force_gpu, "count_tokens", self._count_tokens)
        monkeypatch.setattr(force_gpu, "repeat_to_tokens", self._repeat_to_tokens)
        monkeypatch.setattr(force_gpu, "resolve", self._resolve)
        monkeypatch.setattr(force_gpu, "token_logprobs", self._token_logprobs)

    def _half_nat_per_rung(self, rung: int) -> float:
        return 0.5 * rung

    def _context_limit(self, family: str, head: str = "base") -> int:
        return self.ceiling

    def _count_tokens(self, family: str, text: str, head: str = "base") -> int:
        self.tokenizer_calls += 1
        return len(text.split())

    def _repeat_to_tokens(self, family: str, text: str, tokens: int, head: str = "base") -> str:
        return text

    def _resolve(self, family: str, head: str) -> tuple[str, str]:
        return (f"{family}-stub", "stub-rev")

    def _token_logprobs(
        self,
        family: str,
        prefix: str,
        target: str,
        head: str = "base",
        governor: object | None = None,
        max_prefix_tokens: int | None = None,
    ) -> tuple[list[float], dict[str, Any]]:
        # The scorer calls the true condition before its foreign twin at every rung, so the
        # parity of the call log separates them; cached rungs make no calls at all.
        rung = len(self.prefixes) // 2 + 1
        self.prefixes.append(prefix)
        if len(self.prefixes) % 2 == 1:
            self.true_prefixes.append(prefix)
            return [-self.true_nats] * 4, {}
        if rung in self.blank_foreign_rungs:
            return [], {}
        return [-(self.true_nats + self.foreign_gap(rung))] * 4, {}


@pytest.fixture()
def stub_gpu(monkeypatch: pytest.MonkeyPatch) -> StubGPU:
    return StubGPU(monkeypatch)


class MemoryCache:
    """Duck-typed `Checkpoint`: same get/put rows, counters instead of a JSONL file."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.reads = 0
        self.writes = 0

    def get(self, key: str) -> dict[str, Any] | None:
        self.reads += 1
        return self.rows.get(key)

    def put(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.writes += 1
        row = {"key": key, **payload}
        self.rows[key] = row
        return row


def words(count: int) -> str:
    return " ".join(f"w{i:04d}" for i in range(count))


FOUR_CHAPTERS = ("alpha beta", "gamma delta", "epsilon zeta", "eta theta")
FOREIGN = "omega psi"


# ------------------------------------------------------------------------------- Fiction


def test_a_fiction_record_compares_by_value_and_refuses_mutation():
    first = compression_progress.Fiction("w", "A", 0.01, 100.0, 4, ("c1", "c2"))
    same = compression_progress.Fiction("w", "A", 0.01, 100.0, 4, ("c1", "c2"))
    other = compression_progress.Fiction("w", "A", 0.02, 100.0, 4, ("c1", "c2"))
    assert first == same
    assert first != other
    with pytest.raises(FrozenInstanceError):
        first.conversion = 0.5



# -------------------------------------------------------------------------- pair_fictions


def fiction_row(
    work_id: str, author: str, conversion: float, views: int, followers: int, chapters: int
) -> dict[str, Any]:
    return {
        "work_id": work_id,
        "author": author,
        "conversion": conversion,
        "views": views,
        "followers": followers,
        "published_chapters": chapters,
    }


def test_crossed_is_formed_first_and_aligned_takes_what_remains():
    made = [
        fiction_row("a", "A", 0.020, 10_000, 100, 40),
        fiction_row("b", "B", 0.005, 50_000, 500, 41),
        fiction_row("c", "C", 0.010, 40_000, 400, 42),
        fiction_row("d", "D", 0.004, 45_000, 180, 39),
    ]
    pairs = compression_progress.pair_fictions(made)
    assert [p["pair_id"] for p in pairs] == ["f3-crossed0", "f3-aligned1"]
    assert [p["stratum"] for p in pairs] == ["crossed", "aligned"]
    crossed, aligned = pairs
    # The crossed pair points every popularity rule AWAY: fewer views AND fewer followers.
    assert crossed["high"]["work_id"] == "a"
    assert crossed["low"]["work_id"] == "b"
    assert crossed["high"]["views"] < crossed["low"]["views"]
    assert crossed["high"]["followers"] < crossed["low"]["followers"]
    # The aligned pair keeps views within the tolerance while conversion still separates.
    assert aligned["high"]["work_id"] == "c"
    assert aligned["low"]["work_id"] == "d"
    assert aligned["high"]["conversion"] > aligned["low"]["conversion"]
    assert abs(aligned["log_view_gap"]) <= 0.30
    for pair in pairs:
        assert pair["high"]["conversion"] > pair["low"]["conversion"]
    sides = [pair[side]["work_id"] for pair in pairs for side in ("high", "low")]
    authors = [pair[side]["author"] for pair in pairs for side in ("high", "low")]
    assert len(set(sides)) == 4
    assert len(set(authors)) == 4



def test_a_conversion_ratio_of_exactly_two_still_pairs():
    # Views inverted (21000 > 20000) so the pair cannot qualify as crossed; it must land
    # in aligned on the ratio boundary alone.
    hi = fiction_row("hi", "H", 0.010, 21_000, 200, 40)
    lo = fiction_row("lo", "L", 0.005, 20_000, 210, 40)
    pairs = compression_progress.pair_fictions([hi, lo])
    assert len(pairs) == 1
    assert pairs[0]["stratum"] == "aligned"
    assert pairs[0]["conversion_ratio"] == 2.0


def test_a_conversion_ratio_below_two_never_pairs():
    hi = fiction_row("hi", "H", 0.010, 20_000, 200, 40)
    lo = fiction_row("lo", "L", 0.006, 21_000, 210, 40)
    assert compression_progress.pair_fictions([hi, lo]) == []


def test_a_view_gap_just_inside_three_tenths_of_a_decade_still_pairs():
    hi = fiction_row("hi", "H", 0.020, 19_900, 300, 40)
    lo = fiction_row("lo", "L", 0.005, 10_000, 150, 40)
    # log10(19900 / 10000) = 0.2989, inside the 0.30 ceiling.
    pairs = compression_progress.pair_fictions([hi, lo])
    assert [p["stratum"] for p in pairs] == ["aligned"]


def test_a_view_gap_just_outside_three_tenths_of_a_decade_does_not_pair():
    hi = fiction_row("hi", "H", 0.020, 20_000, 300, 40)
    lo = fiction_row("lo", "L", 0.005, 10_000, 150, 40)
    # log10(20000 / 10000) = 0.30103, past the 0.30 ceiling.
    assert compression_progress.pair_fictions([hi, lo]) == []


def test_a_chapter_count_ratio_just_inside_the_tolerance_still_pairs():
    hi = fiction_row("hi", "H", 0.020, 15_000, 300, 158)
    lo = fiction_row("lo", "L", 0.005, 10_000, 150, 100)
    # log10(158 / 100) = 0.1987, inside the 0.20 ceiling.
    pairs = compression_progress.pair_fictions([hi, lo])
    assert [p["stratum"] for p in pairs] == ["aligned"]


def test_a_chapter_count_ratio_just_outside_the_tolerance_does_not_pair():
    hi = fiction_row("hi", "H", 0.020, 15_000, 300, 159)
    lo = fiction_row("lo", "L", 0.005, 10_000, 150, 100)
    # log10(159 / 100) = 0.2012, past the 0.20 ceiling.
    assert compression_progress.pair_fictions([hi, lo]) == []


def test_equal_views_keep_a_pair_out_of_crossed():
    """Crossed demands strictly fewer views; equal views fall through to aligned."""
    hi = fiction_row("hi", "H", 0.020, 20_000, 100, 40)
    lo = fiction_row("lo", "L", 0.005, 20_000, 500, 40)
    pairs = compression_progress.pair_fictions([hi, lo])
    assert [p["stratum"] for p in pairs] == ["aligned"]
    assert pairs[0]["high"]["views"] == pairs[0]["low"]["views"]


def test_fictions_without_views_or_conversion_are_never_paired():
    dead = fiction_row("dead", "Z", 0.0, 0, 0, 40)
    live = fiction_row("live", "Y", 0.020, 20_000, 300, 40)
    assert compression_progress.pair_fictions([dead, live]) == []


def test_an_empty_pool_pairs_to_nothing():
    assert compression_progress.pair_fictions([]) == []



# ------------------------------------------------------------------------ feasible_fictions


def pool_fiction(work_id: str, chapter_ids: list[str]) -> dict[str, Any]:
    return {
        "work_id": work_id,
        "author": work_id.upper(),
        "conversion": 0.010,
        "views": 20_000,
        "followers": 200.0,
        "published_chapters": 40,
        "chapter_ids": list(chapter_ids),
    }


def shard_texts(*chapter_ids: str) -> dict[str, str]:
    return {cid: words(10) for cid in chapter_ids}


def test_a_feasible_fiction_keeps_only_its_first_four_chapter_ids(stub_gpu):
    ids = ["c1", "c2", "c3", "c4", "c5", "c6"]
    out = compression_progress.feasible_fictions(
        [pool_fiction("w", ids)], shard_texts(*ids), FAMILIES
    )
    assert len(out) == 1
    assert out[0]["chapter_ids"] == ["c1", "c2", "c3", "c4"]
    assert out[0]["work_id"] == "w"
    assert out[0]["views"] == 20_000


def test_a_fiction_with_three_chapters_is_dropped_before_pairing(stub_gpu):
    fictions = [pool_fiction("w", ["c1", "c2", "c3"])]
    texts = shard_texts("c1", "c2", "c3")
    assert compression_progress.feasible_fictions(fictions, texts, FAMILIES) == []


def test_a_fiction_with_a_missing_chapter_text_is_dropped(stub_gpu):
    fictions = [pool_fiction("w", ["c1", "c2", "c3", "c4"])]
    texts = shard_texts("c1", "c2", "c3")  # c4 absent from the shards
    assert compression_progress.feasible_fictions(fictions, texts, FAMILIES) == []


def test_an_empty_pool_yields_no_feasible_fictions(stub_gpu):
    assert compression_progress.feasible_fictions([], {}, FAMILIES) == []


# ---------------------------------------------------------------------------- ladder_fits


def test_a_small_ladder_fits_with_room_to_spare(stub_gpu):
    assert compression_progress.ladder_fits("gemma", ("a", "b", "c", "d")) is True


def test_a_ladder_whose_largest_rung_equals_the_budget_fits(stub_gpu):
    # Ceiling 1000 minus a 1-word target minus the 256-word margin leaves a 743-word budget;
    # the largest rung, all three body chapters joined, is exactly 743 words in either order.
    chapters = (words(300), words(243), words(200), "t")
    assert compression_progress.ladder_fits("gemma", chapters) is True


def test_a_ladder_one_word_over_the_budget_does_not_fit(stub_gpu):
    chapters = (words(300), words(243), words(201), "t")
    assert compression_progress.ladder_fits("gemma", chapters) is False


def test_fewer_than_two_chapters_do_not_fit_and_never_touch_the_tokenizer(stub_gpu):
    assert compression_progress.ladder_fits("gemma", ()) is False
    assert compression_progress.ladder_fits("gemma", ("solo",)) is False
    assert stub_gpu.tokenizer_calls == 0



# ------------------------------------------------------------------------------ fit_filter


def fit_pair(pair_id: str, stratum: str, high_ids: list[str], low_ids: list[str]) -> dict[str, Any]:
    return {
        "pair_id": pair_id,
        "stratum": stratum,
        "high": {"chapter_ids": list(high_ids)},
        "low": {"chapter_ids": list(low_ids)},
    }


SHORT_IDS = ["s1", "s2", "s3", "s4"]


def test_a_pair_both_sides_fit_is_kept_and_nothing_is_excluded(stub_gpu):
    pair = fit_pair("f3-aligned0", "aligned", SHORT_IDS, SHORT_IDS)
    texts = shard_texts(*SHORT_IDS)
    kept, excluded = compression_progress.fit_filter([pair], texts, FAMILIES)
    assert kept == [pair]
    assert excluded == []


def test_a_pair_with_a_missing_low_chapter_is_excluded_for_the_missing_text(stub_gpu):
    pair = fit_pair("f3-crossed0", "crossed", SHORT_IDS, ["s1", "ghost", "s3", "s4"])
    texts = shard_texts(*SHORT_IDS)
    kept, excluded = compression_progress.fit_filter([pair], texts, FAMILIES)
    assert kept == []
    assert len(excluded) == 1
    assert excluded[0]["pair_id"] == "f3-crossed0"
    assert excluded[0]["stratum"] == "crossed"
    offenders = excluded[0]["offenders"]
    assert [o["side"] for o in offenders] == ["low"]
    assert "shards" in offenders[0]["why"]


def test_a_side_over_the_ceiling_names_every_family_as_offender(stub_gpu):
    long_ids = ["b1", "b2", "b3", "b4"]
    pair = fit_pair("f3-aligned0", "aligned", long_ids, SHORT_IDS)
    texts = {**shard_texts(*SHORT_IDS), **{cid: words(400) for cid in long_ids}}
    kept, excluded = compression_progress.fit_filter([pair], texts, FAMILIES)
    assert kept == []
    offenders = excluded[0]["offenders"]
    assert {o["side"] for o in offenders} == {"high"}
    assert {o["family"] for o in offenders} == set(FAMILIES)
    assert all("ceiling" in o["why"] for o in offenders)


def test_a_pair_where_only_the_low_side_busts_the_ceiling_names_only_the_low_side(stub_gpu):
    long_ids = ["b1", "b2", "b3", "b4"]
    pair = fit_pair("f3-crossed0", "crossed", SHORT_IDS, long_ids)
    texts = {**shard_texts(*SHORT_IDS), **{cid: words(400) for cid in long_ids}}
    kept, excluded = compression_progress.fit_filter([pair], texts, FAMILIES)
    assert kept == []
    assert {o["side"] for o in excluded[0]["offenders"]} == {"low"}


def test_an_empty_pair_list_filters_to_two_empty_lists(stub_gpu):
    assert compression_progress.fit_filter([], {}, FAMILIES) == ([], [])



# ---------------------------------------------------------------------- learnability_slope


def test_a_foreign_penalty_growing_half_a_nat_per_rung_scores_a_slope_of_one_half(stub_gpu):
    # Gaps 0.5, 1.0, 1.5 over rungs 1..3: the OLS slope is the endpoint difference over
    # the span, (1.5 - 0.5) / 2.
    slope = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, MemoryCache(), object()
    )
    assert slope == pytest.approx(0.5)


def test_a_foreign_penalty_shrinking_half_a_nat_per_rung_scores_minus_one_half(stub_gpu):
    def shrinking(rung: int) -> float:
        return 1.5 - 0.5 * rung

    stub_gpu.foreign_gap = shrinking
    slope = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, MemoryCache(), object()
    )
    assert slope == pytest.approx(-0.5)


def test_a_constant_foreign_penalty_scores_a_zero_slope(stub_gpu):
    def flat(rung: int) -> float:
        return 0.75

    stub_gpu.foreign_gap = flat
    slope = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, MemoryCache(), object()
    )
    assert slope == pytest.approx(0.0)


def test_a_rung_without_logprobs_is_skipped_and_leaves_the_ladder_incomplete(stub_gpu):
    stub_gpu.blank_foreign_rungs = frozenset({2})
    cache = MemoryCache()
    slope = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, cache, object()
    )
    assert slope is None
    # Rung 2's foreign pass ran and came back empty; the other four rungs were scored.
    assert len(stub_gpu.prefixes) == 6
    assert cache.writes == 3


def test_a_single_chapter_returns_none_without_any_forward_pass(stub_gpu):
    cache = MemoryCache()
    slope = compression_progress.learnability_slope("gemma", ("solo",), FOREIGN, cache, object())
    assert slope is None
    assert stub_gpu.prefixes == []
    assert cache.writes == 0


def test_two_chapters_carry_one_rung_and_cannot_fit_a_slope(stub_gpu):
    chapters = ("alpha beta", "gamma delta")
    slope = compression_progress.learnability_slope(
        "gemma", chapters, FOREIGN, MemoryCache(), object()
    )
    assert slope is None
    assert len(stub_gpu.prefixes) == 2



def test_a_top_rung_exactly_at_the_budget_is_scored(monkeypatch):
    StubGPU(monkeypatch)
    # Ceiling 1000 minus a 300-word target minus the 256-word margin leaves a 444-word
    # budget; the top rung, all three body chapters joined, is exactly 144+150+150 words.
    chapters = (words(144), words(150), words(150), words(300))
    slope = compression_progress.learnability_slope(
        "gemma", chapters, FOREIGN, MemoryCache(), object()
    )
    assert slope == pytest.approx(0.5)


def test_a_top_rung_one_word_over_the_budget_aborts_the_whole_fiction(monkeypatch):
    StubGPU(monkeypatch)
    chapters = (words(145), words(150), words(150), words(300))
    slope = compression_progress.learnability_slope(
        "gemma", chapters, FOREIGN, MemoryCache(), object()
    )
    assert slope is None


def test_shuffled_reverses_the_body_order_of_every_true_context(stub_gpu):
    chapters = ("one alpha", "two bravo", "three charlie", "four delta")
    compression_progress.learnability_slope(
        "gemma", chapters, FOREIGN, MemoryCache(), object(), shuffled=True
    )
    assert stub_gpu.true_prefixes == [
        "three charlie\n\n",
        "three charlie\n\ntwo bravo\n\n",
        "three charlie\n\ntwo bravo\n\none alpha\n\n",
    ]


def test_replicate_recomputes_every_rung_and_a_plain_repeat_replays_the_cache(stub_gpu):
    cache = MemoryCache()
    first = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, cache, object()
    )
    assert len(stub_gpu.prefixes) == 6
    assert cache.writes == 3
    second = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, cache, object()
    )
    assert len(stub_gpu.prefixes) == 6
    assert second == first
    third = compression_progress.learnability_slope(
        "gemma", FOUR_CHAPTERS, FOREIGN, cache, object(), replicate=True
    )
    assert len(stub_gpu.prefixes) == 12
    assert third == first



# ------------------------------------------------------------------------------ donor_prose


def donor_pair(pair_id: str, high_ids: list[str]) -> dict[str, Any]:
    return {
        "pair_id": pair_id,
        "stratum": "aligned",
        "high": {"chapter_ids": list(high_ids)},
        "low": {"chapter_ids": []},
    }


DONOR_TEXTS = {
    "h0a": "zeroth donor text",
    "h1a": "first donor text",
    "h1b": "second donor text",
}


def test_the_donor_for_pair_zero_is_the_next_pair_s_high_side_joined():
    pairs = [donor_pair("p0", ["h0a"]), donor_pair("p1", ["h1a", "h1b"])]
    donor = compression_progress.donor_prose(pairs, 0, DONOR_TEXTS)
    assert donor == "first donor text\n\nsecond donor text"


def test_the_donor_wraps_to_the_first_pair_from_the_last_index():
    pairs = [donor_pair("p0", ["h0a"]), donor_pair("p1", ["h1a", "h1b"])]
    donor = compression_progress.donor_prose(pairs, 1, DONOR_TEXTS)
    assert donor == "zeroth donor text"


def test_a_single_pair_has_no_donor():
    pairs = [donor_pair("p0", ["h0a"])]
    assert compression_progress.donor_prose(pairs, 0, DONOR_TEXTS) == ""


def test_an_empty_pair_list_has_no_donor():
    assert compression_progress.donor_prose([], 0, DONOR_TEXTS) == ""


def test_a_donor_chapter_without_text_is_left_out_of_the_join():
    pairs = [donor_pair("p0", ["h0a"]), donor_pair("p1", ["h1a", "ghost"])]
    donor = compression_progress.donor_prose(pairs, 0, DONOR_TEXTS)
    assert donor == "first donor text"


# ------------------------------------------------------------------------ as_force_pairs_static


def test_force_pairs_carry_id_and_stratum_and_no_prose():
    subset = [
        fit_pair("f3-aligned0", "aligned", ["h0a"], ["l0a"]),
        fit_pair("f3-crossed1", "crossed", ["h1a"], ["l1a"]),
    ]
    got = compression_progress.as_force_pairs_static(subset)
    assert [(p.pair_id, p.stratum, p.high, p.low) for p in got] == [
        ("f3-aligned0", "aligned", "", ""),
        ("f3-crossed1", "crossed", "", ""),
    ]


def test_an_empty_pair_list_maps_to_no_force_pairs():
    assert compression_progress.as_force_pairs_static([]) == []


# --------------------------------------------------------------------------------- selftest


def test_the_module_selftest_passes():
    assert compression_progress.selftest() == 0
