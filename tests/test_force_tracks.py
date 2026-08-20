"""The statistics under §95's four force tracks, on constructed inputs.

Each track's headline number is a small piece of arithmetic sitting on top of a lot of
generation, and the generation is what everyone looks at. These are the pieces that decide what
the generation *means*, and every one of them fails by returning a plausible number:

- **F1's crossover** is a window index with a censoring rule. Get the censoring wrong and the
  statistic reports the length of the continuation rather than anything about prose — which is
  exactly what the first pilot found at a 97.9% censoring rate.
- **F2's site matching** is what stops a retention force from measuring *rarity* instead of
  retention: pick a rare token on one side and a common one on the other and the uplift follows
  the frequency gap.
- **F2's decay slope** must refuse an incomplete ladder rather than fit one.
- **F3's pairing** must invert views *and* followers in `crossed`, or §79's two-stratum design
  stops being adversarial and a popularity proxy clears both halves.
- **FX's saturation check** is one of three pre-registered kill conditions, so a wrong answer
  either kills a live pilot or lets a dead one run.

`force_gpu` is never imported here — it needs torch. The track modules import it at module level,
so each is skipped rather than failed where torch is absent.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

SKIP = "research module; needs torch and the quality-measurement directory on the path"
register_halflife = pytest.importorskip("register_halflife", reason=SKIP)
retention_distance = pytest.importorskip("retention_distance", reason=SKIP)
compression_progress = pytest.importorskip("compression_progress", reason=SKIP)
transmission_chains = pytest.importorskip("transmission_chains", reason=SKIP)
force_market = pytest.importorskip("force_market", reason=SKIP)


# ------------------------------------------------------------------------------------ F1


def test_windows_are_equal_length_and_overlap_by_the_declared_stride():
    text = " ".join(f"w{i}" for i in range(250))
    got = register_halflife.windows(text)
    expected = (250 - register_halflife.WINDOW_WORDS) // register_halflife.STRIDE_WORDS + 1
    assert len(got) == expected
    assert all(len(window.split()) == register_halflife.WINDOW_WORDS for window in got)


def test_a_text_shorter_than_one_window_is_a_single_window():
    assert register_halflife.windows("short text") == ["short text"]


def test_length_is_excluded_from_the_f1_feature_space():
    """Every window is the same length by construction, so `words` carries only the last window."""
    assert "words" not in register_halflife.ACTIVE


def test_crossover_finds_the_first_index_where_the_median_wins():
    index, censored = register_halflife.crossover([0.0, 1.0, 2.0, 3.0], [3.0, 2.0, 1.0, 0.0])
    assert (index, censored) == (2, False)


def test_a_trajectory_that_never_crosses_is_censored_at_the_end():
    index, censored = register_halflife.crossover([0.0, 0.1], [5.0, 5.0])
    assert (index, censored) == (2, True)


def test_the_half_life_fit_refuses_rather_than_returning_zero():
    assert register_halflife.half_life([1.0], [1.0]) != register_halflife.half_life([1.0], [1.0]) \
        or True  # NaN != NaN; the point is that it is not a number a caller would use
    import math

    assert math.isnan(register_halflife.half_life([1.0], [1.0]))
    # A ratio that never moves is not a decay, however the distances are scaled.
    assert math.isinf(register_halflife.half_life([0.0] * 4, [4.0, 2.0, 1.0, 0.5]))


def test_the_inverted_u_alternative_is_not_triggered_by_a_straight_line():
    covariate = {f"k{i}": float(i) for i in range(20)}
    rising = register_halflife.inverted_u(covariate, {f"k{i}": 3.0 * i for i in range(20)})
    assert not rising["interior_peak"]
    humped = register_halflife.inverted_u(covariate, {f"k{i}": -((i - 10) ** 2) for i in range(20)})
    assert humped["interior_peak"]


def test_the_inverted_u_alternative_is_sized_rather_than_merely_signed():
    """`quad < 0 and the peak is interior` has no standard error in it, and a coin satisfies it.

    Measured on 2,000 synthetic samples with y independent of x, the sign-only rule fired 42% of
    the time — and the run it declared READ on had quadratic -0.017463 +/- 0.013543, t = -1.29,
    R^2 = 0.003. `plan/force-program.md` said "significant" all along; the implementation had
    quietly weakened it to "signed".

    The expected rate for a two-sided test at alpha, restricted to a negative coefficient with
    an interior peak, is about half of alpha.
    """
    import random

    rng = random.Random(11)
    fires = 0
    trials = 400
    for _ in range(trials):
        covariate = {f"k{i}": rng.gauss(0, 1) for i in range(60)}
        values = {f"k{i}": rng.gauss(0, 1) for i in range(60)}
        if register_halflife.inverted_u(covariate, values)["interior_peak"]:
            fires += 1
    assert fires / trials < 0.10, f"{fires}/{trials} false positives"

    # And the standard error is reported, so a reader never has to take the sign on faith.
    covariate = {f"k{i}": float(i) for i in range(20)}
    noisy = {f"k{i}": -((i - 10) ** 2) + 40 * ((i % 3) - 1) for i in range(20)}
    read = register_halflife.inverted_u(covariate, noisy)
    assert read["quadratic_se"] > 0
    assert read["interior_peak"] == (abs(read["quadratic_t"]) >= read["significance_bar"]
                                     and read["quadratic"] < 0)


# ------------------------------------------------------------------------------------ F2


def test_probe_candidates_skip_the_window_opening_and_the_frequency_extremes():
    counts = Counter({"rare": 3, "scarce": 4, "common": 5000, "mid": 50})
    window = " ".join(["common"] * 8 + ["rare", "common", "mid", "scarce", "common"])
    sites = retention_distance.candidate_sites(window, counts)
    assert [word for _, word, _ in sites] == ["rare", "mid", "scarce"]
    assert all(index >= 8 for index, _, _ in sites)


def test_site_matching_refuses_a_frequency_gap_and_accepts_a_matched_one():
    counts = Counter({"rare": 3, "scarce": 4, "mid": 50})
    high = " ".join(["x"] * 8 + ["rare"])
    assert retention_distance.matched_sites(high, " ".join(["x"] * 8 + ["mid"]), counts) == ([], [])
    picked_high, picked_low = retention_distance.matched_sites(
        high, " ".join(["x"] * 8 + ["scarce"]), counts
    )
    assert len(picked_high) == len(picked_low) == 1


def test_the_decay_slope_refuses_an_incomplete_ladder():
    short = dict(zip(retention_distance.DISTANCES[:2], [1.0, 0.5], strict=True))
    assert retention_distance.decay_slope(short) is None


def test_the_distance_ladder_is_equally_spaced_in_log2():
    import math

    steps = [
        math.log2(b) - math.log2(a)
        for a, b in zip(
            retention_distance.DISTANCES, retention_distance.DISTANCES[1:], strict=False
        )
    ]
    assert max(steps) - min(steps) < 1e-9


# ------------------------------------------------------------------------------------ F3


def _fiction(work: str, author: str, conversion: float, views: float, followers: float):
    return {
        "work_id": work, "author": author, "conversion": conversion,
        "views": views, "followers": followers, "published_chapters": 40,
    }


def test_f3_pairing_keeps_authors_disjoint_and_inverts_crossed_covariates():
    made = [
        _fiction("a", "A", 0.010, 50_000, 500.0),
        _fiction("b", "B", 0.002, 55_000, 110.0),
        _fiction("c", "C", 0.020, 12_000, 240.0),
        _fiction("d", "D", 0.004, 90_000, 360.0),
    ]
    pairs = compression_progress.pair_fictions(made)
    assert pairs, "the constructed corpus must yield at least one pair"
    works = [pair[side]["work_id"] for pair in pairs for side in ("high", "low")]
    assert len(works) == len(set(works)), "fictions must not be reused across pairs"
    for pair in pairs:
        assert pair["high"]["conversion"] > pair["low"]["conversion"]
        assert pair["high"]["author"] != pair["low"]["author"]
        if pair["stratum"] == "crossed":
            # Every prose-blind popularity rule must point AWAY from the label here.
            assert pair["high"]["views"] < pair["low"]["views"]
            assert pair["high"]["followers"] < pair["low"]["followers"]


def test_f3_refuses_a_conversion_gap_below_the_declared_floor():
    thin = [_fiction("a", "A", 0.010, 50_000, 500.0), _fiction("b", "B", 0.009, 50_000, 450.0)]
    assert compression_progress.pair_fictions(thin) == []


def test_f3_ladder_fits_inside_the_smaller_family_context():
    """The ladder is bounded by the substrate, not by preference.

    The bound has moved twice and the docstring should not outlive the reason. It was Qwen2.5-3B's
    32,768 *positions*; then it was attention memory, which is a much tighter ceiling and is what
    `CONTEXT_CAP` records; and Qwen2.5-3B was retired on 2026-08-20 for Qwen3.5-4B, which is
    hybrid rather than fully global. What has to stay true regardless of the family is that the
    top rung leaves a target chapter to predict.
    """
    import force_gpu

    assert max(compression_progress.LADDER) < compression_progress.CHAPTERS
    smallest_ceiling = min(
        shape["max_positions"] for shape in force_gpu.ATTENTION_SHAPE.values()
    )
    assert smallest_ceiling >= compression_progress.CONTEXT_CAP


# ------------------------------------------------------------------------------------ FX


def test_the_skeleton_is_content_words_only():
    original = "The bridge groaned. Marek counted the planks and the river took the seventh."
    assert transmission_chains.skeleton_retention(original, original) == 1.0
    assert "the" not in transmission_chains.skeleton(original)
    assert transmission_chains.skeleton_retention(original, "nothing whatsoever here") < 0.2


def test_mutation_is_zero_on_identity_and_one_on_disjoint_vocabulary():
    text = "The bridge groaned and Marek counted planks"
    assert transmission_chains.mutation_rate(text, text) == 0.0
    assert transmission_chains.mutation_rate(text, "entirely different vocabulary appears") == 1.0


def test_the_saturation_kill_condition_separates_a_flat_curve_from_a_moving_one():
    flat = [{"skeleton": 0.5, "style": 0.5, "mutation": 0.5} for _ in range(6)]
    assert transmission_chains.saturated(flat)
    moving = [
        {"skeleton": 0.9 - 0.1 * i, "style": 0.9 - 0.1 * i, "mutation": 0.1 * i}
        for i in range(6)
    ]
    assert not transmission_chains.saturated(moving)


def test_a_side_the_budget_never_bought_drops_its_pair_rather_than_crashing():
    """The path a spend ceiling exercises: seeds it could not afford yield no continuations.

    That must produce an empty statistic (so the pair drops), a counted drop, and — on a binding
    stratum left under the refuting floor — `DEGRADED_STRATUM` rather than a FAIL the force never
    earned. Before the ceiling was made to degrade, this path abandoned the whole run and
    returned NOT_RUN, throwing away a corpus that had already been paid for.
    """
    assert not register_halflife.side_statistics("word " * 300, [], median={}, scale={})

    import force_harness

    scored = {"p1": {"high": 3.0, "low": 2.0}, "p2": {"high": 1.0, "low": 4.0}}
    members = [
        force_harness.ForcePair(pair_id=f"p{i}", stratum="crossed", high="x", low="y")
        for i in range(1, 6)
    ]
    wins, decided, total = force_harness.pair_agreement(scored, members)
    assert (wins, decided, total) == (1, 2, 2)
    row = force_harness.verdict(
        "crossed", wins, decided, total, n_before_drops=len(members), binding=True
    )
    assert row["status"] == "DEGRADED_STRATUM"
    assert row["dropped_before_scoring"] == 3


def _f3_fixture(count: int = 24) -> tuple[list[dict], dict[str, str]]:
    """`count` pairs of ten-chapter fictions, alternating strata, with single-newline paragraphs.

    The paragraph separator matters: `rewhitespace` promotes `\\n` to `\\n\\n`, so a statistic
    that reads layout moves on the sham and one that reads prose does not. Text this short never
    reaches a model — every test below substitutes the statistic.
    """
    pairs: list[dict] = []
    texts: dict[str, str] = {}
    for index in range(count):
        stratum = "aligned" if index % 2 == 0 else "crossed"
        sides = {}
        for side in ("high", "low"):
            ids = [f"c{index}-{side}-{k}" for k in range(10)]
            for position, cid in enumerate(ids):
                # A different paragraph count per chapter, so the layout statistic varies.
                lines = [f"Sentence {n} of {cid}." for n in range(2 + position)]
                texts[cid] = "\n".join(lines)
            sides[side] = {"work_id": f"w{index}{side}", "chapter_ids": ids}
        pairs.append({"pair_id": f"f3-{stratum}{index}", "stratum": stratum, **sides})
    return pairs, texts


def test_f3_refuses_a_layout_reading_instead_of_publishing_it(tmp_path, monkeypatch):
    """F3 ran neither control and wrote `status = "READ"` as a literal.

    The consequence, and the reason this is the highest-severity finding the review returned: a
    statistic that reads *only newline counts* — no prose, no model, nothing a force is supposed
    to measure — published `aligned PASS / crossed PASS / status READ` and fired the headline
    sentence. The identical statistic VOIDs in F1, F2 and FX, which run their controls. The arm
    was not measuring worse than its siblings; it was declining to check.

    `rewhitespace` changes no character of any word and promotes the paragraph separator, so a
    layout reader moves on the sham and is disqualified where it used to pass.
    """
    import argparse

    import force_gpu

    monkeypatch.setattr(compression_progress, "DERIVED", tmp_path)
    monkeypatch.setattr(
        compression_progress, "learnability_slope",
        lambda family, chapters, foreign, cache, governor, **kw: float(
            sum(chapter.count("\n") for chapter in chapters)
        ),
    )
    pairs, texts = _f3_fixture()
    args = argparse.Namespace(
        rest_ratio=force_gpu.DEFAULT_REST_RATIO, controls=20, placebo_tolerance=0.0
    )
    report = compression_progress.run_family("gemma-3-4b", pairs, texts, args)

    # The controls ran, and they are the two §1.3 names rather than whatever the arm had handy.
    assert set(report["control_states"]) == {"placebo_identical", "rewhitespace_sham"}
    # Byte-identical input scored twice is still zero — the arithmetic was never the problem.
    assert report["placebo_identical"]["status"] == "PASS"
    # And the sham catches what the strata could not: this force is reading layout.
    assert report["rewhitespace_sham"]["status"] == "VOID"
    assert report["status"] == "VOID"
    assert compression_progress.headline_verdict({"gemma-3-4b": report}, {})["verdict"] == "VOID"


def test_f3_lets_a_prose_reading_through_the_same_controls():
    """The mirror, without which the test above only proves the arm can say no.

    A statistic blind to whitespace — word count stands in for one — leaves the sham with no
    reason to prefer either side. Every sham pair ties, which is `NOT_SCREENABLE` rather than
    PASS: §94.2's direction, where insufficient evidence fails a control instead of passing it.
    A sham with nothing to reject certifies nothing, and F1's whitespace sham is the case that
    made that rule — 100 of 100 of its pairs produced byte-identical feature rows.
    """
    import force_harness

    tied = {f"sham:{i}": {"high": 10.0, "low": 10.0} for i in range(20)}
    members = [
        force_harness.ForcePair(
            pair_id=f"sham:{i}", stratum="rewhitespace_sham", high="", low=""
        )
        for i in range(20)
    ]
    read = force_harness.sham_verdict(
        "rewhitespace_sham", *force_harness.pair_agreement(tied, members)
    )
    assert read["status"] == "NOT_SCREENABLE"
    assert force_harness.arm_status({
        "placebo_identical": {"status": "PASS"}, "rewhitespace_sham": read,
    })["status"] == "NOT_SCREENABLE"

    # A sham that decides and splits evenly is the shape that certifies: interval over 0.50.
    split = {f"sham:{i}": {"high": 1.0 + (i % 2), "low": 2.0 - (i % 2)} for i in range(40)}
    members = [
        force_harness.ForcePair(
            pair_id=f"sham:{i}", stratum="rewhitespace_sham", high="", low=""
        )
        for i in range(40)
    ]
    passed = force_harness.sham_verdict(
        "rewhitespace_sham", *force_harness.pair_agreement(split, members)
    )
    assert passed["status"] == "PASS"


# ------------------------------------------------------------------------------------ FM


def test_the_market_pays_for_being_right_not_for_being_loud():
    """FM settled every bet as "yes", so the ranking was the log geometric mean of confidence.

    `ForcePair` always carries the high-conversion text in `high`, and nothing swapped the
    sides, so `settle` scored `log(p)` on every pair whatever the competitor had said. A
    perfectly calibrated force at 0.52 scored -0.6923; a constant 0.95 scored -0.0513; the
    accuracy a real force needed to out-earn the constant was 0.9920. The committed dry run duly
    gave the text-blind constant a bankroll of 10836.81 and 0.8804 of the promoted ensemble.
    """
    pair = force_market.ForcePair(pair_id="x1", stratum="aligned", high="H", low="L")
    shown, outcome = force_market.presented(pair)
    # Deterministic: the same pair is presented the same way in every process, forever.
    assert force_market.presented(pair) == (shown, outcome)
    assert outcome == (1 if shown.high == "H" else 0)

    # Over many pairs the coin actually turns over, or the swap is decorative.
    ids = [force_market.ForcePair(pair_id=f"p{i}", stratum="aligned", high="H", low="L")
           for i in range(200)]
    flips = sum(1 for p in ids if force_market.presented(p)[1] == 0)
    assert 60 < flips < 140, flips

    loud = force_market.Competitor("loud", lambda _: 0.95)
    coin = force_market.Competitor("coin", lambda _: 0.5)
    force_market.run_market([loud, coin], ids)
    assert loud.bankroll < coin.bankroll
    assert not (sum(loud.log_scores) / len(loud.log_scores)) > -0.6931


def test_the_promoted_ensemble_excludes_anything_that_lost_to_a_coin():
    """Solvency is not skill: a flat stake leaves a sub-coin forecaster standing at the end.

    Weighting by `1 / |mean log score|` over every solvent entry promoted `coin` at 0.0628 and a
    constant 0.95 at 0.0357 — a FORECAST-class candidate part-built from a coin and from
    something that loses to one.
    """
    ids = [force_market.ForcePair(pair_id=f"q{i}", stratum="aligned", high="H", low="L")
           for i in range(120)]
    loud = force_market.Competitor("loud", lambda _: 0.95)
    coin = force_market.Competitor("coin", lambda _: 0.5)
    force_market.run_market([loud, coin], ids)
    promoted = force_market.promotion([loud, coin])
    assert promoted["status"] == "NO_SURVIVOR"
    assert "coin" in promoted["solvent_but_below_coin"]


def test_every_track_selftest_passes():
    for module in (
        register_halflife, retention_distance, compression_progress, transmission_chains,
        force_market,
    ):
        assert module.selftest() == 0, module.__name__
