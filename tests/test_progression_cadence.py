"""Pins for the pure counters of research/quality-measurement/progression_cadence.py.

**Two instruments live in that file and this module defends both.** `v0` is what stage-0 §155.1's
market census was computed with, so its answers are load-bearing history: a test here that lets a
v0 count move is a test that lets 67,436 published numbers stop validating. `v2` adds one line
shape — the house `[STATUS] Subject — Label N | Label N | …` page contract, which v0 could not see
and which `plan/agent-impact/draw-battery.md` measured it not seeing on ten chapters.

The house lines below are transcribed from accepted chapters on the shelf. Detector material and
nothing else: no line here reaches a prompt (§97.1).

Nothing here claims a located event is worth anything to a reader. These tests pin what the
counter counts, and which version counted it.
"""

from __future__ import annotations

import pytest

from litharness.application.statusline import parse_status_line
from litharness.domain.draft import _SYSTEM_LINE

progression_cadence = pytest.importorskip(
    "progression_cadence",
    reason="research module; needs the quality-measurement directory on the path",
)

#: One accepted `[STATUS]` line per post-redesign draw in the battery, transcribed verbatim.
#: They differ in the ways that matter to a line detector: a two-word display name, a raw
#: lowercase id, a lowercase multi-word display name, paired cells, and nine columns.
HOUSE_LINES = (
    "[STATUS] Ines — Rating 3 | Graded 9 | Written 1/12 | Warmth 6/6",
    "[STATUS] Mira Kell — Hold 3 | Carried 2/3 | Mending 4 | Reading 3 | Hearing 0 | Piecing 1",
    "[STATUS] mira — Seamwork 5 | Reach 9 | Carried 4/9 | Seams standing in Ashfen 42",
    "[STATUS] Theo — Rung 1 | Depth 0/0 | Sight 1 | Hold 0 | Quote 0 | Strike 0 | Amend 0",
    "[STATUS] the board — Ticket 1 | read the grain 2 | cold seal 2 | hold a room 0",
)


def test_the_modules_own_selftest_passes() -> None:
    """Both frozen blocks, both unit rules, the mask and the version refusal, in one call."""
    assert progression_cadence.selftest() == 0


def test_v0s_registration_digest_is_the_one_the_market_census_was_published_under() -> None:
    """Stage-0 §155.1 names this digest. If it moves, every number in that entry is orphaned."""
    assert progression_cadence.REGISTRATION_DIGEST == "5d42f2065efb7e09"
    assert progression_cadence.registration_digest() == progression_cadence.REGISTRATION_DIGEST
    assert progression_cadence.PRE_REGISTRATION["instrument"] == "progression_cadence.v0"


def test_v2_is_a_second_instrument_that_names_its_parent_by_digest() -> None:
    """A superseding version has to be addressable, and has to say what it superseded.

    The parent digest is a literal in v2's own block rather than a reference to v0's, so if v0
    ever moved, v2 would stop naming its ancestor and this assertion would say so.
    """
    assert progression_cadence.REGISTRATION_DIGEST_V2 == "f1a205af2cd3d718"
    assert progression_cadence.PRE_REGISTRATION_V2["instrument"] == "progression_cadence.v2"
    assert progression_cadence.PRE_REGISTRATION_V2["supersedes"] == "progression_cadence.v0"
    assert (
        progression_cadence.PRE_REGISTRATION_V2["inherits_registration_digest"]
        == progression_cadence.REGISTRATION_DIGEST
    )
    assert progression_cadence.REGISTRATION_DIGEST_V2 != progression_cadence.REGISTRATION_DIGEST


def test_v0_is_still_the_default_and_still_cannot_see_the_house_sheet() -> None:
    """**The blindness is preserved on purpose, and this is the test that says so.**

    v0's published market numbers were computed by a detector that could not read this line.
    Teaching v0 to read it would silently invalidate them, so the fix shipped as v2 and v0's
    answer is pinned here as history rather than tolerated as a bug.
    """
    assert progression_cadence.DEFAULT_VERSION == "v0"
    for line in HOUSE_LINES:
        assert progression_cadence._is_furniture(line) is False, line
        assert progression_cadence.locate(f"He read it.\n\n{line}\n\nShe did not.") == []


def test_v2_locates_the_house_page_contract_in_every_shape_the_shelf_has_drawn() -> None:
    """The whole reason this version exists, over the five real line shapes on the shelf."""
    for line in HOUSE_LINES:
        assert progression_cadence._is_furniture(line, version="v2") is True, line
        events = progression_cadence.locate(
            f"He read it.\n\n{line}\n\nShe did not.", version="v2"
        )
        assert [event.family for event in events] == ["system_block"], line


def test_v2_reads_the_line_before_and_after_the_normaliser_folds_its_dash() -> None:
    """`normalise` folds U+2014 to an ASCII hyphen, and callers split lines on their own.

    `_is_furniture` is called on RAW lines by `plan/agent-impact/scripts/draw_battery.py`, so a
    pattern that only knew the folded form would work inside `locate` and fail from outside it.
    """
    # By codepoint, not by glyph: a test about telling three dashes apart should not ask a
    # reviewer to tell two of them apart in a diff. `statusline` makes the same choice.
    em, en = chr(0x2014), chr(0x2013)
    raw = HOUSE_LINES[0]
    folded = progression_cadence.normalise(raw)
    assert em in raw and em not in folded
    for line in (raw, folded, raw.replace(em, en)):
        assert progression_cadence._is_furniture(line, version="v2") is True, line


def test_v2_adds_one_shape_and_changes_no_v0_answer() -> None:
    """A superseding version that also moved an old answer would be a rewrite, not an addition.

    Every case v0's own selftest pins is re-run through v2 and has to agree, including the two
    corrections v0 recorded making: the scene divider and the box-drawn sheet.
    """
    samples = (
        progression_cadence._SELFTEST_FURNITURE,
        progression_cadence._SELFTEST_PROSE,
        "He stopped.\n\n***\n\nShe did not.",
        "One.\n\n---\n\nTwo.",
        "[A/N: sorry for the late chapter, exams!]\n\nHe walked on.",
        "=====\n| Strength: 14 |\n| Level: 3 |\n=====\n\nHe closed it.",
        "Nothing happens here. Nobody gains anything at all.",
    )
    for text in samples:
        assert progression_cadence.locate(text) == progression_cadence.locate(
            text, version="v2"
        ), text


def test_the_reject_list_still_runs_before_v2s_shape_check() -> None:
    """An author's note wearing columns is an author's note, however well it fits the pattern."""
    note = "[A/N] late again — sorry 1 | exams 2 | soon 3"
    assert progression_cadence._is_furniture(note, version="v2") is False


@pytest.mark.parametrize(
    "line",
    [
        "[STATUS] Ines — Rating 3",  # one column is a sentence with a bracket on it
        "[STATUS] Ines — Rating | Graded | Written",  # a tagged list of words, no quantity
        "Ines — Rating 3 | Graded 9",  # no tag: prose cannot be told from a panel
        "The plan — hers, not his — needed three more days.",  # dashes, no tag, no columns
        "***",
        "* * *",
    ],
)
def test_v2s_narrowings_each_refuse_a_shape(line: str) -> None:
    """Every clause in the added pattern is a narrowing, and each one is here to be argued with.

    The tag keeps prose out, two columns rather than one is what makes a panel, and the digit
    requirement keeps a tagged list of words from scoring.
    """
    assert progression_cadence._is_furniture(line, version="v2") is False


def test_the_block_run_rule_survives_the_new_shape() -> None:
    """v0's unit rule is unchanged: a run of furniture is ONE event however long it is."""
    two_prints = (
        "She read it.\n\n"
        f"{HOUSE_LINES[0]}\n\n"
        "Then again, later.\n\n"
        f"{HOUSE_LINES[0]}\n\n"
        "Outside, rain.\n"
    )
    assert len(progression_cadence.locate(two_prints, version="v2")) == 2
    adjacent = f"She read it.\n\n{HOUSE_LINES[0]}\n{HOUSE_LINES[1]}\n\nOutside, rain.\n"
    assert len(progression_cadence.locate(adjacent, version="v2")) == 1


def test_the_mask_indexes_the_callers_own_lines_and_drops_frames_too() -> None:
    """A prose-side counter wants the sheet AND the scene separator gone; neither is narration."""
    text = f"One.\n\n{HOUSE_LINES[0]}\n\n* * *\n\nTwo.\n"
    mask = progression_cadence.furniture_mask(text, version="v2")
    assert len(mask) == len(text.splitlines())
    assert [line for line, hidden in zip(text.splitlines(), mask, strict=True) if hidden] == [
        HOUSE_LINES[0],
        "* * *",
    ]
    assert sum(progression_cadence.furniture_mask(text)) == 1  # v0 sees only the separator


def test_prose_only_keeps_the_characters_a_prose_counter_is_looking_for() -> None:
    """**The mask is computed on normalised lines and applied to raw ones, and it must be.**

    `normalise` folds U+2014 to a hyphen, so a mask that returned normalised text would delete
    the em-dash signal it was invoked to protect. The battery measured what this is worth: three
    chapters with no em dash anywhere in their prose scored 2 on the raw file, because the
    `[STATUS]` line's own subject separator is U+2014.
    """
    text = f"He said it — and meant it.\n\n{HOUSE_LINES[0]}\n\nShe did not.\n"
    prose = progression_cadence.prose_only(text, version="v2")
    assert prose.count("—") == 1
    assert "[STATUS]" not in prose
    assert "He said it — and meant it." in prose


def test_the_v2_shape_agrees_with_the_pipeline_on_the_lines_both_were_written_for() -> None:
    """The transcription check, and it is a check rather than a guarantee.

    The research modules run under an interpreter where the package is absent, so v2 transcribes
    the shape `application/statusline` recognises instead of importing it — and `statusline`'s own
    docstring argues a renderer's choice and a counter's definition should be free to stop
    agreeing. This pins that on the shelf's real lines they have not, so a divergence is a
    failing test rather than a discovery three months later.
    """
    for line in HOUSE_LINES:
        assert parse_status_line(line) is not None
        assert _SYSTEM_LINE.match(line) is not None
        assert progression_cadence._is_furniture(line, version="v2") is True
    # And the other direction: what the pipeline calls prose, v2 does not call furniture.
    for line in ("He read it.", "The plan — hers, not his — needed three more days."):
        assert parse_status_line(line) is None
        assert progression_cadence._is_furniture(line, version="v2") is False


def test_an_unknown_version_is_refused_rather_than_falling_back() -> None:
    """A typo that silently answered as v0 would publish v0 numbers under a v2 label."""
    assert progression_cadence.VERSIONS == ("v0", "v2")
    for call in (
        lambda: progression_cadence.locate("x", version="v1"),
        lambda: progression_cadence.furniture_mask("x", version="v3"),
        lambda: progression_cadence._is_furniture("x", version=""),
    ):
        with pytest.raises(ValueError, match="unknown instrument version"):
            call()


def test_every_measured_row_carries_the_version_that_counted_it() -> None:
    """Two versions in one list must not be poolable by accident."""
    kwargs = {
        "fiction_id": 0,
        "chapter_id": 0,
        "litrpg": True,
        "quarantined": False,
        "cohort": None,
    }
    text = f"She read it.\n\n{HOUSE_LINES[0]}\n\nOutside, rain.\n"
    v0 = progression_cadence.measure(text, **kwargs)
    v2 = progression_cadence.measure(text, **kwargs, version="v2")
    assert (v0.version, v0.events) == ("v0", 0)
    assert (v2.version, v2.events) == ("v2", 1)


def test_v2_declares_no_bar_and_says_it_is_not_comparable_with_the_market() -> None:
    """The two things a version that finds MORE furniture must not be allowed to imply.

    Every market number for this instrument is v0's, and v2 can only ever locate more than v0
    locates — so a v2 house count read against a v0 market percentile overstates our position by
    an unmeasured amount. The registration says so in its own bytes, not only in a document.
    """
    block = progression_cadence.PRE_REGISTRATION_V2
    assert "No target cadence is declared" in block["declares_no_bar"]
    assert "detector change and NOT an improvement" in block["declares_no_bar"]
    limit = block["not_comparable_with_the_market_census"]
    assert "has NOT been run over the market" in limit
    # The limit names the digest every market number was published under, not just a version
    # label: a reader checking it can address the bytes.
    assert progression_cadence.REGISTRATION_DIGEST in limit
    assert block["residuals"][: len(progression_cadence.PRE_REGISTRATION["residuals"])] == (
        progression_cadence.PRE_REGISTRATION["residuals"]
    )


def test_a_v2_census_may_not_overwrite_the_file_the_market_numbers_were_read_off() -> None:
    """§155's numbers live in `progression-cadence.json`, and a v2 pass there would erase them."""
    results = progression_cadence.RESULTS / "progression-cadence.json"
    assert (
        progression_cadence.main(
            ["census", "--version", "v2", "--results", str(results)]
        )
        == 1
    )
