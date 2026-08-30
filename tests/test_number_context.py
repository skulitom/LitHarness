"""Pins for the pure counters of research/quality-measurement/number_context.py.

Every case here is hand-derived from text on disk. The mundane fixtures are read 8 §4.1's own
exhaustive list for *Unlicensed Weather* chapter 1, held as detector material and nothing else
(§97.1); the refused cases are shapes a first version actually drew and a hand-check rejected,
so each narrowing has a receipt that fails if it is ever loosened back.

Nothing here claims a number in any family harms a reader. These tests pin what the counter
counts.
"""

from __future__ import annotations

import pytest

number_context = pytest.importorskip(
    "number_context",
    reason="research module; needs the quality-measurement directory on the path",
)


#: One accepted `[STATUS]` line, transcribed from a chapter on the shelf. Detector material and
#: nothing else: no line here reaches a prompt (§97.1). Six digits in four cells, which is what
#: makes it useful — under v0 they fall THROUGH the furniture rule into the prose families.
HOUSE_LINE = "[STATUS] Ines — Rating 3 | Graded 9 | Written 1/12 | Warmth 6/6"


def families(text: str) -> list[str]:
    return [family for _surface, family in number_context.family_of(text)]


def test_the_modules_own_selftest_passes() -> None:
    """The frozen block, the fixtures, the refusals and the unit rules, in one call."""
    assert number_context.selftest() == []


def test_every_operator_named_item_lands_in_its_hand_counted_family() -> None:
    """Read 8 §4.1's list is the ground truth this instrument exists to reproduce."""
    for text, expected in number_context.FIXTURE_MUNDANE:
        assert expected in families(text), text


def test_every_hand_checked_false_positive_stays_refused() -> None:
    """`one` as a pronoun, and the indefinite article the registration refuses to count."""
    for text in number_context.FIXTURE_REFUSED:
        located = [
            family
            for family in families(text)
            if family in {*number_context.MUNDANE_CORE, "object_count"}
            or family.startswith("system")
        ]
        assert located == [], (text, located)


def test_an_hour_of_rain_is_refused_and_the_registration_says_so() -> None:
    """The operator's own list has one member this instrument cannot see, on purpose.

    `a` and `an` are not numerals. Admitting them would sweep in every indefinite noun phrase
    in the language, which is not precision -- so the recall hole is declared in
    `PRE_REGISTRATION["refused"]` rather than patched with a special case.
    """
    assert families("An hour of rain on your table by noon.") == []
    assert "indefinite_article_durations" in number_context.PRE_REGISTRATION["refused"]


def test_the_head_window_stops_at_a_preposition_once_a_head_is_found() -> None:
    """`the first surprise of the morning` is an enumeration and not a duration.

    A first version walked a flat four-token window and reached `morning` past `surprise`,
    reporting a calendar mention where the numeral enumerates surprises. The partitive `of` is
    only transparent BEFORE a head has been seen, which is what keeps `four of the guild's
    jars` a count of jars.
    """
    assert families("That was the first surprise of the morning.") == ["ordinal_enumeration"]
    assert families("Four of the guild's jars rode in a frame.") == ["object_count"]


def test_ordinality_is_read_off_the_last_token_of_a_merged_run() -> None:
    """`twenty-second` opens on a cardinal and is an ordinal, and a first version disagreed."""
    assert families("At the twenty-second jar she stopped.") == ["ordinal_enumeration"]


def test_adjectives_and_quantity_modifiers_do_not_hide_a_closed_lexicon_head() -> None:
    assert families("He waited two long days.") == ["calendar_duration"]
    assert families("He waited three more days.") == ["calendar_duration"]


def test_adjacent_numerals_are_one_mention_and_an_arrow_is_two() -> None:
    """The unit rule, and the status-block case that corrected it.

    Adjacency in the token list is not adjacency on the line: the tokeniser emits no `->`, so
    `Strength 14 -> 17` was being merged into a single mention and a five-number status block
    reported three.
    """
    assert len(number_context.locate("She counted twenty-two jars, then two or three more.")) == 2
    assert len(number_context.locate("[Strength 14 -> 17]")) == 2


def test_a_system_magnitude_and_a_system_ordinal_are_different_columns() -> None:
    """The split our own shelf forced, and the reason a single `system` column would lie.

    Every system-anchored number on the shelf is an ordinal on a ladder word -- `fourth grade`,
    `THIRD TIER` -- and not one is a magnitude. A ladder position and a quantity on a sheet are
    different objects.
    """
    assert families("You'll want the fourth-grade price.") == ["system_ordinal"]
    assert families("He reached level 12 that morning.") == ["system_magnitude"]
    assert "system" not in number_context.FAMILIES


def test_a_labelled_slot_governs_its_number_but_at_that_point_does_not() -> None:
    """The preceding-anchor window is one token and its lexicon is deliberately narrow.

    `at that point three days later` puts a system word immediately before a mundane numeral.
    Admitting `point` as a preceding anchor turned a duration into a stat, so it is not one.
    """
    assert families("He reached rank 3 that year.") == ["system_magnitude"]
    assert families("At that point three days had gone.") == ["calendar_duration"]


def test_mundane_core_never_includes_object_count_or_ordinals() -> None:
    """The lowest-precision families are reported and never pooled into the headline.

    `object_count` finds its head by a stopword rule rather than a closed lexicon, and an
    ordinal date cannot be told from an ordinal enumeration without a parser. A count named for
    one defect that measures another is the lying column stage-0 §150.4 deleted a field for.
    """
    assert set(number_context.MUNDANE_CORE) == {
        "calendar_duration",
        "age",
        "money",
        "measure",
    }
    row = number_context.measure("She counted thirty jars over eight days.")
    assert row.by_family["object_count"] == 1
    assert row.by_family["calendar_duration"] == 1
    assert row.mundane_core == 1


def test_system_any_is_the_only_sum_and_both_halves_survive_it() -> None:
    row = number_context.measure("He reached level 12. You'll want the fourth-grade price.")
    assert row.by_family["system_magnitude"] == 1
    assert row.by_family["system_ordinal"] == 1
    assert row.system_any == 2


def test_a_status_block_is_system_by_location_and_a_scene_divider_is_nothing() -> None:
    """The furniture line shapes are copied from `progression_cadence.v0`, correction included.

    A run of frame characters is a scene divider that every fiction on the platform uses, and
    counting it would put every one of them inside a status block.
    """
    block = number_context.measure("[Mana: 240/300]\n[Level 12]")
    assert block.by_family["system_magnitude"] == 3
    assert number_context.measure("He stopped.\n\n***\n\nShe did not.").mentions == 0


def test_the_recorded_false_positive_is_still_recorded() -> None:
    """A measured error with no mechanical fix is kept visible, not quietly borne.

    `three levels of it below the lobby` is a parking structure. `levels` is also the anchor
    this genre's sheet uses, and nothing short of a sense disambiguator separates them, so both
    halves of every comparison carry the same small architectural contamination.
    """
    assert number_context.MEASURED_FALSE_POSITIVES
    for text, family in number_context.MEASURED_FALSE_POSITIVES:
        assert family in families(text)


def test_a_structural_heading_is_skipped_in_any_of_the_shards_languages() -> None:
    """`Capitulo 6` and `Cena 1` were object counts, and the shards are not all English.

    A heading's number is navigation and not narration. The word bound keeps prose *about* a
    chapter, which is a different sentence and does carry counts.
    """
    assert families("Capitulo 6: A Sombra Que Espreita") == []
    assert families("Cena 1: A Segunda Conversa com o Velho") == []
    prose = "Chapter 6 had taught him that eight days was a long time to wait for a letter."
    assert "calendar_duration" in families(prose)


def test_english_share_separates_english_prose_from_the_shards_other_languages() -> None:
    """The control that keeps a non-English market row from reading as a numberless one.

    Every English lexicon in this module scores a Portuguese chapter near zero, which depresses
    the market's mundane density and INFLATES any ours-versus-market gap. The census reports the
    market with and without those rows; this pins that the measure can tell them apart.
    """
    english = "The road came off the moor and down into the town by the time she reached it."
    other = "A vila estava silenciosa, mas o velho seguiu as vozes baixas ate o fundo do poco."
    assert number_context.english_share(english) > 0.30
    assert number_context.english_share(other) < 0.10
    assert number_context.english_share("") == 0.0
    # `a` and `as` were in the set until this sample lifted a Portuguese line above the floor.
    assert "a" not in number_context.ENGLISH_FUNCTION_WORDS
    assert "as" not in number_context.ENGLISH_FUNCTION_WORDS


def test_the_registration_declares_no_bar_and_names_its_direction() -> None:
    """`REGISTERED` under EPISTEMIC_GOVERNANCE means the direction was fixed before the run."""
    registration = number_context.PRE_REGISTRATION
    assert "REGISTERED DIRECTION" in registration["predicted"]
    declaration = registration["declares_no_bar"]
    assert declaration.startswith("No target density, ratio or floor is declared")
    assert "four attainability checks" not in declaration or "range at the real n" in declaration
    # The three precision fixes made after the market half opened are disclosed, with the
    # direction each moves the census's own headline, and the pre-market commit is named.
    assert "96b622f" in registration["narrowings_from_the_market_half"]
    assert "CUTS AGAINST" in registration["narrowings_from_the_market_half"]
    assert registration["residuals"]
    assert number_context.registration_digest() == number_context.REGISTRATION_DIGEST


def test_v0s_registration_digest_is_the_one_the_market_census_was_published_under() -> None:
    """Stage-0 §162 names this digest. If it moves, every number in that entry is orphaned."""
    assert number_context.REGISTRATION_DIGEST == "8e10ac598828d404"
    assert number_context.PRE_REGISTRATION["instrument"] == "number_context.v0"


def test_v2_is_a_second_instrument_that_names_its_parent_by_digest() -> None:
    """A superseding version has to be addressable, and has to say what it superseded."""
    assert number_context.REGISTRATION_DIGEST_V2 == "6c007094f6159474"
    assert number_context.PRE_REGISTRATION_V2["instrument"] == "number_context.v2"
    assert (
        number_context.PRE_REGISTRATION_V2["inherits_registration_digest"]
        == number_context.REGISTRATION_DIGEST
    )
    assert number_context.REGISTRATION_DIGEST_V2 != number_context.REGISTRATION_DIGEST
    assert number_context.DEFAULT_VERSION == "v0"


def test_v0_still_misfiles_the_house_sheet_and_that_is_the_point() -> None:
    """**The inherited blindness is preserved on purpose, and worse than a zero.**

    v0 copied `progression_cadence.v0`'s line shapes deliberately, so it inherited their
    blindness deliberately too: the sheet is not furniture, so its own values fall THROUGH into
    the ordinary prose families. `plan/agent-impact/draw-battery.md` §3.2 measured a nine-column
    sheet printed twice inflating `object_count` from 12 to 28. Teaching v0 to see it would
    invalidate stage-0 §162's market numbers, so the fix is v2 and this is v0 pinned as history.
    """
    row = number_context.measure(HOUSE_LINE)
    assert row.furniture_lines == 0
    assert row.system_any == 0
    assert row.by_family["object_count"] + row.by_family["unanchored"] == 6


def test_v2_files_a_sheets_cells_as_system_numbers_by_location() -> None:
    """The whole reason this version exists: `[STATUS]` is furniture, so its cells are the sheet's.

    Six mentions, because the tokeniser does not merge across `/` — `1/12` and `6/6` are each two
    quantities, which is the unit rule a status block corrected in v0 and v2 does not touch.
    """
    row = number_context.measure(HOUSE_LINE, version="v2")
    assert row.furniture_lines == 1
    assert row.system_any == 6
    assert row.by_family["system_magnitude"] == 6
    assert row.mundane_core == 0
    assert row.by_family["object_count"] == 0
    assert row.version == "v2"


def test_v2_takes_the_sheet_out_of_the_prose_families_and_adds_nothing_to_them() -> None:
    """**The check that says v2 is a subtraction and not a second guess.**

    Run over a whole chapter, v2 has to reproduce v0-run-on-prose exactly for every non-system
    family — otherwise the added shape is doing something beyond relabelling the sheet's cells.
    The battery measured this on all ten of its chapters and it held on every one.
    """
    chapter = (
        "She counted thirty jars over eight days, and the row went away from her.\n"
        "\n"
        f"{HOUSE_LINE}\n"
        "\n"
        "Four of the guild's jars rode in a padded frame. She was nineteen.\n"
    )
    prose = "\n".join(line for line in chapter.split("\n") if not line.startswith("[STATUS]"))
    whole_v2 = number_context.measure(chapter, version="v2")
    prose_v0 = number_context.measure(prose)
    for family in (*number_context.MUNDANE_CORE, "object_count", "unanchored"):
        assert whole_v2.by_family[family] == prose_v0.by_family[family], family
    assert prose_v0.system_any == 0
    assert whole_v2.system_any == 6


def test_v2_adds_one_shape_and_changes_no_v0_answer() -> None:
    """Every pinned classification is re-run through v2 and has to agree; it must add only."""
    samples = [
        *(text for text, _f in number_context.FIXTURE_CLASSIFIED),
        *number_context.FIXTURE_REFUSED,
        *(text for text, _f in number_context.FIXTURE_MUNDANE),
        "[Mana: 240/300]\n[Level 12]",
        "He stopped.\n\n***\n\nShe did not.",
        "[A/N: sorry for the late chapter, exams!]\n\nHe walked on.",
    ]
    for text in samples:
        assert families(text) == [
            family for _s, family in number_context.family_of(text, version="v2")
        ], text


@pytest.mark.parametrize(
    "line",
    [
        "[A/N] late again — sorry 1 | exams 2 | soon 3",
        "[STATUS] Ines — Rating 3",
        "[STATUS] Ines — Rating | Graded | Written",
        "The plan — hers, not his — needed three more days.",
        "* * *",
    ],
)
def test_v2s_narrowings_each_refuse_a_shape(line: str) -> None:
    """The added pattern is a stack of narrowings and each one is here to be argued with."""
    assert number_context.is_furniture_line(line, version="v2") is False


def test_the_two_copies_of_the_added_shape_have_not_drifted() -> None:
    """This module copies `progression_cadence`'s line shapes rather than importing them.

    The copy is a recorded decision (`line_shapes_copied_deliberately`): a content-addressed
    registration must be self-contained, or the neighbour's digest could change this instrument
    silently. The cost of a copy is drift, and this is the receipt against it.
    """
    cadence = pytest.importorskip("progression_cadence")
    assert (
        number_context.PRE_REGISTRATION_V2["patterns_added"]["furniture_tagged_columns"]
        == cadence.PRE_REGISTRATION_V2["patterns_added"]["furniture_tagged_columns"]
    )
    for line in (HOUSE_LINE, "[A/N] late — sorry 1 | exams 2", "[STATUS] Ines — Rating 3"):
        assert number_context.is_furniture_line(line, version="v2") == cadence._is_furniture(
            line, version="v2"
        ), line


def test_an_unknown_version_is_refused_rather_than_falling_back() -> None:
    """A typo that silently answered as v0 would publish v0 numbers under a v2 label."""
    assert number_context.VERSIONS == ("v0", "v2")
    with pytest.raises(ValueError, match="unknown instrument version"):
        number_context.measure("x", version="v1")
    with pytest.raises(ValueError, match="unknown instrument version"):
        number_context.is_furniture_line("x", version="")


def test_v2_declares_no_bar_and_says_it_is_not_comparable_with_the_market() -> None:
    """v2 moves numbers from the mundane side to the system side, and §162's finding is that our
    system side is empty — so an ours-v2-against-market-v0 comparison would report progress that
    is entirely the detector's. The registration says so in its own bytes."""
    block = number_context.PRE_REGISTRATION_V2
    assert "No target density, ratio or floor is declared" in block["declares_no_bar"]
    limit = block["not_comparable_with_the_market_census"]
    assert "has NOT been run over the market" in limit
    assert number_context.REGISTRATION_DIGEST in limit
    assert "entirely the detector's" in limit


def test_density_is_per_thousand_words_and_a_share_is_none_when_nothing_anchors() -> None:
    row = number_context.measure(" ".join(["word"] * 999 + ["days"]))
    assert row.words == 1000
    assert row.system_share_of_anchored is None
    counted = number_context.measure("eight days " + " ".join(["word"] * 998))
    assert counted.per_1k(counted.by_family["calendar_duration"]) == pytest.approx(1.0)
