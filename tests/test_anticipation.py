"""The anticipation probe's frozen bytes and registered definitions, checked without calls.

What this file pins: the probe asks for description and never a rating (the report-channel
rail), the stop point's paragraph arithmetic on both sides of its boundaries, the grounding
and distinctness scorers on hand-stated inputs, the stance arithmetic, the strict parser, the
cell aggregation's scorable floor (one draw is the 0.54-reliability trap), and the four kill
conditions on constructed cells where the correct verdict is stated before anything runs.
What it does not establish: anything about any model's anticipation — no call happens here.
"""

from __future__ import annotations

import re

import pytest

anticipation = pytest.importorskip(
    "anticipation",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

BANNED = re.compile(r"\b(quality|good|bad|rate|score|judge|grade|better|worse)\b", re.I)


# ------------------------------------------------------------------------- the frozen probe


def test_the_probe_describes_and_never_rates() -> None:
    assert "describe" in anticipation.PROBE
    assert "Without judging the writing" in anticipation.PROBE
    match = BANNED.search(anticipation.PROBE.replace("judging", ""))
    assert match is None, f"verdict word {match.group(0)!r} in the probe"


def test_the_schema_demands_exactly_three_closed_items() -> None:
    schema = anticipation.PROBE_SCHEMA
    assert schema["minItems"] == schema["maxItems"] == anticipation.N_OUTCOMES
    items = schema["items"]
    assert items["required"] == ["outcome", "stance"]
    assert items["additionalProperties"] is False
    assert items["properties"]["stance"]["enum"] == ["hope", "dread", "neither"]


def test_the_word_valence_appears_nowhere_in_the_module() -> None:
    """The ledger reserves 'valence' for reader preference; this instrument may not reuse it."""
    from pathlib import Path

    source = Path(anticipation.__file__).read_text(encoding="utf-8")
    assert "valence" not in source.lower()


# ---------------------------------------------------------------------------- the stop point


def test_stop_point_lands_on_the_boundary_nearest_sixty_percent() -> None:
    # Paragraph words: 10, 10, 10, 10, 10 -> total 50, target 30; boundary after p3.
    paragraphs = [" ".join([f"p{i}w{j}" for j in range(10)]) for i in range(5)]
    text = "\n\n".join(paragraphs)
    assert anticipation.stop_point(text) == "\n\n".join(paragraphs[:3])


def test_stop_point_never_returns_the_whole_text_and_needs_a_future() -> None:
    two = "first paragraph words here.\n\nsecond paragraph must remain unread."
    assert anticipation.stop_point(two) == "first paragraph words here."
    with pytest.raises(ValueError, match="future"):
        anticipation.stop_point("only one paragraph lives here")


# ------------------------------------------------------------------------------- the scorers


PASSAGE = (
    "Marrow counted the forged seals twice.\n\nThe gate inspector was due at dawn, and "
    "failure meant the debtor cells."
)


def test_specificity_is_the_grounded_fraction_of_content_tokens() -> None:
    # Content tokens of the outcome: marrow, forged, seals, fail, gate -> 4 of 5 grounded
    # ("fail" is not in the passage; "failure" is, and no stemming is registered).
    outcome = "Marrow's forged seals fail at the gate."
    assert anticipation.specificity(outcome, PASSAGE) == pytest.approx(4 / 5)


def test_an_ungrounded_outcome_scores_zero_and_stopwords_carry_nothing() -> None:
    assert anticipation.specificity("It might just happen to them.", PASSAGE) == 0.0
    assert anticipation.specificity("", PASSAGE) == 0.0


def test_length_cannot_buy_specificity_past_the_word_cap() -> None:
    grounded_tail = " ".join(["padding"] * anticipation.OUTCOME_MAX_WORDS) + " Marrow seals"
    # The grounded tokens sit past the 50-word cap, so they never score.
    assert anticipation.specificity(grounded_tail, PASSAGE) == 0.0


def test_distinctness_separates_different_futures_from_duplicates() -> None:
    a = "Marrow burns the seals."
    b = "The inspector arrives early at dawn."
    c = "Rain floods the debtor cells."
    assert anticipation.distinctness([a, b, c]) > 0.7
    assert anticipation.distinctness([a, a, a]) == 0.0
    assert anticipation.distinctness([a]) == 0.0
    assert anticipation.distinctness([]) == 0.0


def test_stance_stats_score_engagement_and_bipolarity_by_hand() -> None:
    mixed = anticipation.stance_stats(["hope", "dread", "neither"])
    assert mixed["engagement"] == pytest.approx(2 / 3)
    assert mixed["bipolar"] is True
    flat = anticipation.stance_stats(["neither"] * 3)
    assert flat["engagement"] == 0.0
    assert flat["bipolar"] is False
    one_sided = anticipation.stance_stats(["hope", "hope", "hope"])
    assert one_sided["engagement"] == 1.0
    assert one_sided["bipolar"] is False


# --------------------------------------------------------------------------------- the parser


def _payload(items: list[dict]) -> str:
    import json

    return json.dumps(items)


def test_the_parser_accepts_exactly_the_registered_shape() -> None:
    good = _payload(
        [
            {"outcome": "Marrow burns the seals.", "stance": "dread"},
            {"outcome": "The inspector is late.", "stance": "hope"},
            {"outcome": "Rain keeps falling.", "stance": "neither"},
        ]
    )
    parsed = anticipation.parse_response(good)
    assert parsed is not None and len(parsed) == 3
    assert parsed[0] == ("Marrow burns the seals.", "dread")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not json",
        _payload([{"outcome": "x", "stance": "hope"}] * 2),  # two items
        _payload([{"outcome": "x", "stance": "hope"}] * 4),  # four items
        _payload([{"outcome": "x", "stance": "excited"}] * 3),  # out-of-enum stance
        _payload([{"outcome": "x"}] * 3),  # missing key
        _payload([{"outcome": "x", "stance": "hope", "rating": 5}] * 3),  # extra key
    ],
)
def test_every_malformed_shape_parses_to_one_none(bad: str) -> None:
    assert anticipation.parse_response(bad) is None


# ------------------------------------------------------------------------ cells and the kills


def _draw(spec_outcome: str, stance: str) -> list[tuple[str, str]]:
    return [(spec_outcome, stance)] * anticipation.N_OUTCOMES


def test_a_single_answered_draw_is_not_scorable() -> None:
    cell = anticipation.cell_score(
        "p1", "original", "climber", PASSAGE, [_draw("Marrow burns the seals.", "hope")]
    )
    assert cell.draws_answered == 1
    assert not cell.scorable


def _cell(arm: str, spec_value: float, engagement: float) -> anticipation.CellScore:
    return anticipation.CellScore(
        passage_id="p1", arm=arm, persona_id="climber", draws_answered=4,
        mean_specificity=spec_value, mean_distinctness=0.5, engagement=engagement,
        bipolar_rate=0.5, recurrence=0.0,
    )


def test_the_kill_table_passes_a_well_separated_battery() -> None:
    cells = [
        _cell("original", 0.60, 0.80),
        _cell("destake", 0.30, 0.30),          # far from original
        _cell("deplete_matched", 0.52, 0.70),  # near original: deletion alone did little
        _cell("rename_entities", 0.58, 0.78),  # shams sit close
        _cell("rewhitespace", 0.61, 0.81),
    ]
    table = anticipation.kills(cells)
    assert table["k1"]["verdict"] == "PASS"
    assert table["k2"]["verdict"] == "PASS"
    assert table["k3"]["verdict"] == "PASS"
    assert table["scorable_cells"] == 5


def test_the_kill_table_kills_a_constant_probe_and_an_unsupported_stake_reading() -> None:
    flat = [_cell(arm, 0.50, 0.50) for arm in anticipation.ARMS]
    assert anticipation.kills(flat)["k1"]["verdict"] == "KILL"
    matched_did_it = [
        _cell("original", 0.60, 0.80),
        _cell("destake", 0.35, 0.40),
        _cell("deplete_matched", 0.30, 0.35),  # the control moved even further
        _cell("rename_entities", 0.58, 0.78),
        _cell("rewhitespace", 0.59, 0.79),
    ]
    assert anticipation.kills(matched_did_it)["k3"]["verdict"] == "KILL"


def test_the_kill_table_reads_unreadable_with_no_scorable_cells() -> None:
    lonely = anticipation.CellScore(
        passage_id="p1", arm="original", persona_id="climber", draws_answered=1,
        mean_specificity=0.5, mean_distinctness=0.5, engagement=0.5, bipolar_rate=0.5,
        recurrence=0.0,
    )
    table = anticipation.kills([lonely])
    assert table["k1"]["verdict"] == "UNREADABLE"
    assert table["scorable_cells"] == 0


# ----------------------------------------------------------------------------------- selftest


def test_the_selftest_passes() -> None:
    assert anticipation.selftest() == 0


# ------------------------------------------------------------------------------ the arm texts


def test_the_dry_elicitor_leg_fails_when_the_stripper_truncates_an_array(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The guard must be able to fail, or it is not a guard.

    Restores the pre-2026-09-04 stripper — first balanced `{...}` only — and asserts the leg
    returns non-zero. That is the run this leg's absence let through: 800 calls, zero transport
    failures, zero scorable cells (stage-0 §226).
    """
    import elicit

    def object_only(text: str) -> str:
        stripped = text.strip()
        start = stripped.find("{")
        if start < 0:
            return stripped
        depth = 0
        for index in range(start, len(stripped)):
            if stripped[index] == "{":
                depth += 1
            elif stripped[index] == "}":
                depth -= 1
                if depth == 0:
                    return stripped[start : index + 1]
        return stripped

    monkeypatch.setattr(elicit, "_strip_fence", object_only)

    class _Args:
        cache = str(tmp_path / "dry.jsonl")
        model = "claude-haiku-4-5"

    assert anticipation.dry_elicitor(_Args()) == 1


def test_the_dry_elicitor_leg_passes_on_the_fixed_stripper(tmp_path) -> None:
    class _Args:
        cache = str(tmp_path / "dry.jsonl")
        model = "claude-haiku-4-5"

    assert anticipation.dry_elicitor(_Args()) == 0


def test_the_replay_cache_defaults_beside_the_result_and_not_into_the_working_directory() -> None:
    """An 800-call run's cache must not land wherever the operator happened to be standing."""
    assert anticipation.DEFAULT_CACHE.is_absolute()
    assert anticipation.DEFAULT_CACHE.parent == anticipation.RESULTS
    assert anticipation.DEFAULT_CACHE.name.endswith(".jsonl")


def test_a_damaged_arm_keeps_the_paragraph_convention_the_stop_point_reads() -> None:
    """Found by the first dry run: `destake` rebuilt the text with single newlines and every
    damaged arm arrived at `stop_point` as one paragraph. The arm text must carry the same
    paragraph breaks as the original so the registered cut falls at its own 60%."""
    paragraphs = [
        "Marrow counted the forged seals twice and the count came out the same.",
        "The gate inspector was due at dawn, and failure meant the debtor cells.",
        "Rain moved in from the harbour while the lamps were lit one by one.",
        "Nobody on the wall spoke, and the seals stayed in the drawer.",
    ]
    text = "\n\n".join(paragraphs)
    assert anticipation._arm_text("original", text) == text
    for arm in anticipation.ARMS[1:]:
        shown = anticipation._arm_text(arm, text)
        assert "\n\n" in shown, arm
        # Never a single-newline text: the stop point would see one paragraph and raise.
        assert not any("\n" in part for part in shown.split("\n\n")), arm
        anticipation.stop_point(shown)
