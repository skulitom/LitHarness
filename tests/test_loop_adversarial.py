"""The adversarial battery's mechanical half: the two transforms and the degenerate maxima.

What this file pins: that the damage transform moves the order-sensitive rows and leaves the
counting rows exactly alone (the structural fact the battery's own reading depends on), that
the sham refuses rather than reporting an unmoved control, that each degeneracy check fires on
a fixture built to be that degenerate maximum and stays clear on the matched clean one, that a
check which could not run reports so instead of reporting clear, and that the report carries no
aggregate and no field named score or verdict.

What this file does not establish: anything about a real draw. Every fixture below is written
here, and the numbers are properties of these fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "research" / "loop"))

adv = pytest.importorskip("adversarial", reason="research module; imported by path")
ma = pytest.importorskip("measures_adapter", reason="research module; imported by path")

# --------------------------------------------------------------------------------- fixtures

#: Ordinary prose, calibrated against the instruments rather than written and hoped for. It
#: carries: names in mid-sentence position (`register_census.proper_nouns` excludes
#: sentence-initial words, so a fixture whose names all open sentences has no cast at all);
#: mundane anchors in three families, so the system share of anchored mentions sits near 0.29
#: with room to rise rather than at a degenerate 1.0; two status blocks and two progression
#: moves made in prose, using phrasings the frozen `level_up` and `capability_gain` patterns
#: actually match; varied sentence length; and enough words to clear `MIN_WORDS`.
CLEAN_PARAGRAPHS = (
    "The lantern still cost twenty crowns, and Rook counted his coins twice before he paid.",
    "At the gate the keeper wanted five more. He paid Marrow's price without looking up.",
    "[STATUS] Rook\nTier: Bronze 2",
    "The Shadowstep trick carried him through the wicket before the hounds had turned, and it "
    "cost him a breath he did not have.",
    "It had rained for three days, and the stair up to Marrow ran ninety steps in the dark.",
    "He advanced to Bronze 3 somewhere on that stair, and the ache in his ribs went quiet.",
    "The lamps along the Ward burned low. Somebody had trimmed them badly, or not at all.",
    "Tier: Bronze 3",
    "She asked Rook what he had spent. He told her the truth, which surprised them both.",
    "He unlocked the Quiet Hands skill that night, forty crowns lighter and no wiser for it.",
)


def draw(draw_id: str, paragraphs: tuple[str, ...]) -> adv.Draw:
    """One chapter built from paragraphs; the battery reads a draw's joined text."""
    return adv.Draw(draw_id=draw_id, chapters=("\n\n".join(paragraphs),))


@pytest.fixture
def clean() -> adv.Draw:
    return draw("clean", CLEAN_PARAGRAPHS)


@pytest.fixture
def measures() -> ma.Measures:
    """The local fallback explicitly, so these expectations do not move when a scorecard lands.

    A test that silently picked up whatever module happened to be importable would change its
    own subject the day the sibling track merges.
    """
    return ma.Measures(source="local-fallback", battery=ma.local_battery)


# ------------------------------------------------------------------------- the damage transform


def test_shuffle_moves_only_the_order_sensitive_rows(clean: adv.Draw, measures: ma.Measures):
    """The fact the damage arm's whole reading rests on, stated as a test.

    A paragraph shuffle is exactly length-preserving — the same paragraphs, reordered — so
    every row that counts something must come back identical, and only the rows that ask WHERE
    an event fell may move. This is why `damage_survival` firing on a counting row is expected
    rather than alarming, and why a scorecard made of counts alone cannot be damage-tested.
    """
    before = adv.flatten(measures.of(clean.text))
    after = adv.flatten(measures.of(adv.damage(clean.text)))
    moved = {name for name in before if before[name] != after.get(name)}
    assert moved <= {"cadence.first_event_fraction", "cadence.median_gap", "cadence.gap_cv"}
    assert moved, "the fixture must have enough events for the shuffle to move something"
    counting_rows = {
        "words", "prose_words", "cadence.events", "cadence.furniture_events",
        "cadence.prose_anchored_events", "numbers.mentions", "numbers.system_any",
        "sentences.count", "sentences.mean_words", "sentences.length_cv", "cast.proper_nouns",
        "em_dash",
    }
    assert counting_rows & moved == set()


def test_damage_is_length_preserving(clean: adv.Draw):
    shuffled = adv.damage(clean.text)
    assert shuffled != clean.text
    assert sorted(shuffled.split()) == sorted(clean.text.split())


def test_damage_survival_refuses_when_there_is_nothing_to_displace(measures: ma.Measures):
    """Too few paragraphs is not-run, never clear: an unmoved damage arm is no control."""
    tiny = adv.Draw("tiny", (" ".join(["word"] * 200),))
    result = adv.damage_survival(tiny, "cadence", measures, None)
    assert result.fired is None
    assert "no control" in result.note


def test_damage_survival_names_the_rows_that_survived(clean: adv.Draw, measures: ma.Measures):
    """With a baseline the check is a sign test: does the shuffled winner still beat it?"""
    baseline = draw("base", CLEAN_PARAGRAPHS[:6])
    result = adv.damage_survival(clean, "words", measures, baseline)
    assert result.fired is True
    assert "words" in result.numbers["survived_rows"]
    entry = result.numbers["rows"]["words"]
    assert entry["intact"] == entry["shuffled"] > entry["baseline"]


# --------------------------------------------------------------------------- the sham transform


def test_sham_windows_drop_the_offset_and_stay_distinct(clean: adv.Draw):
    windows = adv.sham_windows(clean.text)
    assert windows is not None
    first, second = windows
    assert first != second
    assert second == "\n\n".join(CLEAN_PARAGRAPHS[adv.SHAM_OFFSET_PARAGRAPHS:])


def test_sham_windows_refuse_a_text_too_short_to_window():
    assert adv.sham_windows("one\n\ntwo") is None


def test_sham_separation_ignores_rows_with_no_margin(clean: adv.Draw, measures: ma.Measures):
    """A row on which the two arms agreed is not a win being defended, so it cannot be swamped."""
    result = adv.sham_separation(clean, "words", measures, clean)
    assert result.numbers["rows"]["words"]["real_margin"] == 0
    assert result.numbers["swamped_rows"] == []
    assert result.fired is False


def test_sham_separation_without_a_baseline_is_not_run(clean: adv.Draw, measures: ma.Measures):
    result = adv.sham_separation(clean, "words", measures, None)
    assert result.fired is None
    assert result.numbers["rows"]


# ------------------------------------------------------------------------- furniture spam


FURNITURE_SPAM = (
    *CLEAN_PARAGRAPHS,
    "[STATUS] Rook\nTier: Bronze 3",
    "The stair went up.",
    "[STATUS] Marrow\nTier: Silver 1",
    "The rain kept on.",
    "[STATUS] Rook\nTier: Bronze 3",
)


def test_furniture_spam_fires_when_the_gain_is_all_furniture():
    """More status blocks, no more moves made in prose: the cadence row rises on nothing."""
    result = adv.furniture_spam(
        draw("win", FURNITURE_SPAM), "cadence", draw("base", CLEAN_PARAGRAPHS)
    )
    assert result.fired is True
    assert result.numbers["furniture_rose"] and result.numbers["prose_flat"]


def test_furniture_spam_is_clear_when_the_prose_carries_the_gain():
    """The same cadence rise, made by moves a sentence had to make, does not fire."""
    earned = (
        *CLEAN_PARAGRAPHS,
        "He advanced to Bronze 4 before the bells, and the ache went quiet again.",
        "She unlocked the Long Count ability the same night, which nobody had expected of her.",
    )
    result = adv.furniture_spam(draw("win", earned), "cadence", draw("base", CLEAN_PARAGRAPHS))
    assert result.fired is False
    assert result.numbers["prose_flat"] is False


def test_furniture_spam_without_a_baseline_fires_only_at_the_extreme():
    """No baseline means no decomposition, so only an all-furniture draw is unambiguous."""
    all_furniture = (
        "[STATUS] Rook\nTier: Bronze 2",
        *(
            f"The lamp burned low over the {name} and nobody came to trim it at all tonight."
            for name in ("stair", "ward", "gate", "well", "arch", "yard", "door", "sill")
        ),
    )
    result = adv.furniture_spam(draw("win", all_furniture), "cadence", None)
    assert result.fired is True
    assert result.numbers["winner_furniture_share"] == 1.0
    assert adv.furniture_spam(draw("win", CLEAN_PARAGRAPHS), "cadence", None).fired is False


# ---------------------------------------------------------------------- checklist stuffing


STUFFED = (
    *CLEAN_PARAGRAPHS,
    "Vigor 16, Guile 12, Reach 9, Ward 4, and the tier counter sat at Bronze 3 with 240 "
    "points banked against a threshold of 300 points and a rank cap of 5 ranks.",
    "Silver 1 wanted 400 points, Silver 2 wanted 900 points, and the ladder ran to 12 ranks.",
)


def test_checklist_stuffing_fires_when_system_nouns_crowd_out_the_anchors():
    result = adv.checklist_stuffing(draw("win", STUFFED), "numbers", draw("base", CLEAN_PARAGRAPHS))
    assert result.numbers["comparative_fired"] is True
    assert result.fired is True


def test_checklist_stuffing_is_clear_when_mundane_anchors_grow_too():
    """More numbers is not the defect; more SYSTEM numbers as a share of the anchors is."""
    mundane = (
        *CLEAN_PARAGRAPHS,
        "The rain had run for three days, the ledger showed forty crowns, and the stair "
        "climbed ninety steps to a door two hands thick.",
    )
    result = adv.checklist_stuffing(draw("win", mundane), "numbers", draw("base", CLEAN_PARAGRAPHS))
    assert result.numbers["comparative_fired"] is False


def test_checklist_stuffing_outlier_form_needs_a_family(clean: adv.Draw):
    """Under MIN_FAMILY the outlier form does not run, and says so rather than staying quiet."""
    result = adv.checklist_stuffing(clean, "numbers", None, family=[clean, clean])
    assert result.fired is None
    assert "under MIN_FAMILY" in result.note
    assert "screening_cutoff" not in result.numbers


def test_checklist_stuffing_outlier_form_reports_the_constant_it_used(clean: adv.Draw):
    """The screening constant is reported beside every number it was applied to, never hidden."""
    family = [draw(f"f{i}", CLEAN_PARAGRAPHS) for i in range(adv.MIN_FAMILY)]
    result = adv.checklist_stuffing(draw("win", STUFFED), "numbers", None, family=family)
    assert result.numbers["screening_constant_MAD_K"] == adv.MAD_K
    assert result.numbers["family_n"] == adv.MIN_FAMILY


# ------------------------------------------------------------------------- sentence maxima


STACCATO = tuple(
    f"{verb} the door. {verb} the stair. {verb} the lamp. {verb} the gate. {verb} the well."
    for verb in ("He took", "He shut", "He left", "He found", "He lost", "He held")
)


def test_staccato_monotony_fires_when_the_mean_and_the_variation_both_fall():
    result = adv.staccato_monotony(
        draw("win", STACCATO), "sentences", draw("base", CLEAN_PARAGRAPHS)
    )
    assert result.numbers["mean_fell"] and result.numbers["cv_fell"]
    assert result.fired is True


def test_staccato_monotony_is_clear_when_only_the_mean_falls():
    """Shorter sentences that still vary is what a real fix looks like; it must not fire."""
    varied = (
        "He took the door.",
        "The stair went up past three landings and a window nobody had washed in a year.",
        "He shut it.",
        "Marrow was waiting at the top with the ledger open for once, which meant trouble.",
        "He left.",
        "The rain came down the way it always did, sideways and without any hurry at all.",
    ) * 2
    result = adv.staccato_monotony(draw("win", varied), "sentences", draw("base", CLEAN_PARAGRAPHS))
    assert result.numbers["cv_fell"] is False
    assert result.fired is False


def test_staccato_monotony_without_a_baseline_is_not_run(clean: adv.Draw):
    assert adv.staccato_monotony(clean, "sentences", None).fired is None


def test_opening_repetition_fires_on_a_repeated_first_word():
    result = adv.opening_repetition(
        draw("win", STACCATO), "sentences", draw("base", CLEAN_PARAGRAPHS)
    )
    assert result.fired is True
    assert (
        result.numbers["winner_top_opening_share"]
        > result.numbers["baseline_top_opening_share"]
    )


def test_opening_repetition_is_clear_when_openings_vary(clean: adv.Draw):
    assert adv.opening_repetition(clean, "sentences", draw("base", STACCATO)).fired is False


# ---------------------------------------------------------------------------- cast starvation


def test_cast_starvation_fires_when_the_page_empties_without_shortening():
    """Same length, fewer people: the cast row improved by removing the cast."""
    emptied = (
        *(
        paragraph.replace("Rook", "the boy").replace("Marrow", "the woman")
        .replace("Shadowstep", "old").replace("Ward", "ward").replace("Quiet Hands", "quiet")
        for paragraph in CLEAN_PARAGRAPHS
        ),
        "The lamp burned on over the empty stair for a long while after that, and nobody at "
        "all came up or went down it again before the morning bells had finished.",
    )
    result = adv.cast_starvation(draw("win", emptied), "cast", draw("base", CLEAN_PARAGRAPHS))
    assert result.numbers["names_fell"] and result.numbers["words_held"]
    assert result.fired is True


def test_cast_starvation_is_clear_when_the_names_stay(clean: adv.Draw):
    assert adv.cast_starvation(clean, "cast", draw("base", CLEAN_PARAGRAPHS)).fired is False


# ------------------------------------------------------------------------------ word dilution


def test_word_dilution_fires_when_only_the_denominator_moved(measures: ma.Measures):
    """The em-dash rate falls because the chapter got longer, not because the dashes went."""
    dashed = (*CLEAN_PARAGRAPHS, "He stopped at the sill — the rain had turned — and waited.")
    padding = tuple(
        f"The {place} stood open to the weather and nobody had thought to see to it yet."
        for place in ("yard", "arch", "well", "gate", "sill", "door", "stair", "ward")
    )
    result = adv.word_dilution(
        draw("win", (*dashed, *padding)), "em_dash", measures, draw("base", dashed)
    )
    assert result.numbers["words_rose"] is True
    assert result.numbers["diluted_rows"] == ["em_dash"]
    assert result.fired is True


def test_word_dilution_is_clear_when_the_raw_count_actually_fell(measures: ma.Measures):
    dashed = (*CLEAN_PARAGRAPHS, "He stopped at the sill — the rain had turned — and waited.")
    fixed = (*CLEAN_PARAGRAPHS, "He stopped at the sill. The rain had turned, and he waited.")
    result = adv.word_dilution(draw("win", fixed), "em_dash", measures, draw("base", dashed))
    assert result.fired is False


def test_word_dilution_without_a_baseline_is_not_run(clean: adv.Draw, measures: ma.Measures):
    assert adv.word_dilution(clean, "em_dash", measures, None).fired is None


# ------------------------------------------------------------------------------- the battery


def test_unknown_axis_degrades_and_says_that_it_did():
    """The graceful-degradation contract while the scorecard track is unmerged."""
    names, recognised = adv.checks_for_axis("beat-satisfaction-not-yet-shipped")
    assert recognised is False
    assert names == adv.AXIS_AGNOSTIC
    known, flag = adv.checks_for_axis("sentences")
    assert flag is True
    assert "staccato_monotony" in known and "opening_repetition" in known


def test_every_axis_in_the_registry_dispatches(clean: adv.Draw, measures: ma.Measures):
    """A check named in `AXIS_CHECKS` with no branch in `run_battery` must not reach a run."""
    baseline = draw("base", CLEAN_PARAGRAPHS[:6])
    for axis in adv.AXIS_CHECKS:
        report = adv.run_battery(clean, axis, baseline=baseline, measures=measures)
        assert report.axis_recognised is True


def test_battery_refuses_a_draw_under_the_word_floor(measures: ma.Measures):
    with pytest.raises(ValueError, match="MIN_WORDS"):
        adv.run_battery(adv.Draw("stub", ("three words only",)), "cadence", measures=measures)


def test_report_carries_no_aggregate_and_no_verdict(clean: adv.Draw, measures: ma.Measures):
    """Containment, as a scan of the emitted record: no score, no verdict, no overall outcome."""
    report = adv.run_battery(clean, "cadence", baseline=draw("b", CLEAN_PARAGRAPHS[:6]),
                             measures=measures)
    rendered = report.to_json().lower()
    for forbidden in ("score", "verdict", "quality", "overall", "pass", "fail"):
        assert f'"{forbidden}"' not in rendered
    assert set(report.to_dict()) == {
        "variant", "axis", "axis_recognised", "measures_source", "baseline", "family",
        "preference", "checks",
    }


def test_report_separates_fired_from_could_not_run(clean: adv.Draw, measures: ma.Measures):
    """A check that could not run is not a check that passed."""
    report = adv.run_battery(clean, "sentences", measures=measures)
    assert "staccato_monotony" in report.not_run
    assert "staccato_monotony" not in report.fired
    assert report.table().splitlines()[1:]


def test_preference_probe_is_optional_and_records_that_it_was_not_purchased(
    clean: adv.Draw, measures: ma.Measures
):
    """No paid call is made by this build; the report says so rather than omitting the half."""
    report = adv.run_battery(clean, "cadence", measures=measures)
    assert report.preference == {"purchased": False, "note": "panel preference not purchased"}

    seen: list[tuple[str, str]] = []

    def probe(intact: str, shuffled: str) -> dict[str, object]:
        seen.append((intact, shuffled))
        return {"continue": "neither"}

    paid = adv.run_battery(clean, "cadence", measures=measures, preference=probe)
    assert paid.preference["purchased"] is True
    assert len(seen) == 1 and seen[0][0] != seen[0][1]


def test_flatten_excludes_booleans():
    """A True differenced against a False would be reported as a movement of one unit."""
    assert adv.flatten({"a": True, "b": 2, "c": {"d": 3.5}}) == {"b": 2.0, "c.d": 3.5}


def test_measures_adapter_falls_back_and_honours_a_preference():
    assert ma.load_measures("no-such-module-anywhere").source == "local-fallback"
    assert ma.load_measures().source in {"local-fallback", *ma.SCORECARD_MODULES}
