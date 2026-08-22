"""Pins for the hermetic half of ``research/quality-measurement/personas.py``.

These tests cover the pure surface only: ``Anchor`` and ``Persona`` invariants,
``system_prompt``, ``pair_turn``, ``fidelity_probe`` and ``anchor_agreement``. Every
expected value comes from a persona built inside the test whose correct answer can be
stated by hand; the shipped ``PANEL`` is never used as an oracle.

They do not establish that any model call, database read, corpus load, CLI path or
sleeping/spawning behaviour works — nothing here touches ``elicit.py`` or storage — and
they do not establish that the authored v0 taste is faithful to real readers; that is
precisely what offline arithmetic cannot measure.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

personas = pytest.importorskip(
    "personas",
    reason="research module; needs the quality-measurement directory on the path",
)


def _anchor(
    work: str,
    verdict: str,
    reason_code: str,
    *,
    held_out: bool = False,
) -> personas.Anchor:
    return personas.Anchor(
        work=work,
        verdict=verdict,
        reason_code=reason_code,
        reason=f"what decided {work}",
        held_out=held_out,
    )


def _persona(*anchors: personas.Anchor) -> personas.Persona:
    return personas.Persona(
        persona_id="tester",
        name="the test reader",
        reads_for="sentences that earn their length",
        drops_on="scenes that cost nobody anything",
        anchors=anchors,
    )


# --------------------------------------------------------------------- Anchor invariants


def test_an_unknown_verdict_word_is_refused_at_construction():
    with pytest.raises(ValueError, match="loved-it"):
        _anchor("Some Book", "loved-it", "none")


def test_an_empty_verdict_string_is_refused_rather_than_tolerated():
    with pytest.raises(ValueError):
        _anchor("Some Book", "", "none")


def test_an_unknown_reason_code_is_refused_at_construction():
    with pytest.raises(ValueError, match="too-slow"):
        _anchor("Some Book", "would-stop", "too-slow")


def test_the_none_reason_code_is_valid_on_either_side_of_the_verdict_split():
    stopping = personas.Anchor(
        work="Stop Book",
        verdict="would-stop",
        reason_code="none",
        reason="nothing fit",
    )
    keeping = personas.Anchor(
        work="Keep Book",
        verdict="keep-reading",
        reason_code="none",
        reason="nothing fit yet",
    )
    assert stopping.authored is True
    assert keeping.held_out is False


def test_every_declared_reason_code_constructs_a_valid_anchor():
    for code in (*personas.STOP_CODES, *personas.KEEP_CODES, "none"):
        anchor = _anchor("Some Book", "not-sure", code)
        assert anchor.reason_code == code


def test_an_anchor_rejects_edits_after_construction():
    anchor = _anchor("Some Book", "not-sure", "none")
    with pytest.raises(dataclasses.FrozenInstanceError):
        anchor.verdict = "keep-reading"  # type: ignore[misc]


# --------------------------------------------------------------------- Persona invariants


def test_shown_and_held_out_anchors_partition_the_anchors_preserving_order():
    alpha = _anchor("Alpha", "keep-reading", "curious")
    beta = _anchor("Beta", "would-stop", "jargon-wall", held_out=True)
    gamma = _anchor("Gamma", "not-sure", "padding")
    persona = _persona(alpha, beta, gamma)
    assert persona.shown_anchors == (alpha, gamma)
    assert persona.held_out_anchors == (beta,)


def test_a_persona_with_no_anchors_has_two_empty_partitions_rather_than_crashing():
    persona = _persona()
    assert persona.shown_anchors == ()
    assert persona.held_out_anchors == ()


def test_a_persona_with_only_held_out_anchors_shows_none():
    beta = _anchor("Beta", "would-stop", "jargon-wall", held_out=True)
    persona = _persona(beta)
    assert persona.shown_anchors == ()
    assert persona.held_out_anchors == (beta,)


# ------------------------------------------------------------------------- system_prompt


def test_the_system_prompt_opens_as_a_reader_and_states_both_taste_lines():
    persona = _persona()
    prompt = personas.system_prompt(persona)
    assert prompt.startswith("You are a reader.")
    assert f"What you read for: {persona.reads_for}\n" in prompt
    assert f"What makes you put a book down: {persona.drops_on}\n" in prompt


def test_shown_anchors_are_rendered_with_their_verdict_and_reason():
    prompt = personas.system_prompt(_persona(_anchor("Alpha", "not-sure", "padding")))
    assert "- Alpha: not-sure — what decided Alpha" in prompt


def test_held_out_works_are_named_while_their_verdict_and_reason_stay_hidden():
    shown = _anchor("Alpha", "keep-reading", "curious")
    held = _anchor("Beta", "would-stop", "jargon-wall", held_out=True)
    prompt = personas.system_prompt(_persona(shown, held))
    assert "- Beta" in prompt
    assert "Other books you have read and have firm opinions about:" in prompt
    # The held-out verdict and reason appear nowhere, because the shown anchor's
    # verdict differs from the held-out one on purpose.
    assert "would-stop" not in prompt
    assert "jargon-wall" not in prompt
    assert "what decided Beta" not in prompt
    assert "- Alpha: keep-reading — what decided Alpha" in prompt


def test_a_persona_with_no_held_out_anchors_gets_no_other_books_block():
    prompt = personas.system_prompt(_persona(_anchor("Alpha", "keep-reading", "curious")))
    assert "Other books you have read" not in prompt


def test_the_system_prompt_is_byte_identical_across_calls():
    persona = _persona(
        _anchor("Alpha", "not-sure", "padding"),
        _anchor("Beta", "would-stop", "flat-voice", held_out=True),
    )
    assert personas.system_prompt(persona) == personas.system_prompt(persona)


# ------------------------------------------------------------------------------ pair_turn


def test_pair_turn_carries_both_passages_verbatim_under_labelled_headers_in_order():
    turn = personas.pair_turn("first text", "second text")
    head = "PASSAGE A\n\nfirst text\n\n---\n\nPASSAGE B\n\nsecond text\n\n---\n\n"
    assert turn.startswith(head)


def test_pair_turn_offers_every_reason_code_backticked_except_none():
    turn = personas.pair_turn("a", "b")
    for code in (*personas.STOP_CODES, *personas.KEEP_CODES):
        assert f"`{code}`" in turn
    assert "`none`" not in turn
    assert "or none if nothing on the list fits" in turn


def test_each_declared_question_key_renders_its_own_wording():
    preference = personas.pair_turn("a", "b", question="preference")
    intensity = personas.pair_turn("a", "b", question="intensity")
    paraphrase = personas.pair_turn("a", "b", question="preference_paraphrase")
    assert "rather keep reading" in preference
    assert "hit you harder" in intensity
    assert "carry on with only one of them" in paraphrase


def test_pair_turn_defaults_to_the_preference_question():
    assert personas.pair_turn("a", "b") == personas.pair_turn("a", "b", question="preference")


def test_an_unknown_question_key_is_refused():
    with pytest.raises(ValueError, match="intensity_but_wrong"):
        personas.pair_turn("a", "b", question="intensity_but_wrong")


def test_pair_turn_with_two_empty_passages_still_renders_the_full_frame():
    turn = personas.pair_turn("", "")
    assert turn.startswith("PASSAGE A\n\n\n\n---\n\nPASSAGE B\n\n\n\n---\n\n")


# -------------------------------------------------------------------------- fidelity_probe


def test_a_persona_without_held_out_anchors_gets_no_probe():
    persona = _persona(_anchor("Alpha", "keep-reading", "curious"))
    assert personas.fidelity_probe(persona) is None


def test_the_probe_names_each_held_out_work_once_in_anchor_order():
    first = _anchor("Alpha", "keep-reading", "curious", held_out=True)
    second = _anchor("Beta", "would-stop", "jargon-wall", held_out=True)
    probe = personas.fidelity_probe(_persona(first, second))
    assert probe is not None
    turn, _schema = probe
    assert turn.startswith("Before we go on, some books you've read.")
    assert turn.endswith("\n\n- Alpha\n- Beta")


def test_the_probe_never_reveals_the_answers_it_checks_and_skips_shown_anchors():
    shown = _anchor("Alpha", "keep-reading", "pulled-forward")
    held = _anchor("Beta", "would-stop", "numbers-meaningless", held_out=True)
    probe = personas.fidelity_probe(_persona(shown, held))
    assert probe is not None
    turn, _schema = probe
    assert "- Beta" in turn
    assert "would-stop" not in turn
    assert "numbers-meaningless" not in turn
    assert "what decided Beta" not in turn
    assert "- Alpha" not in turn


def test_the_probe_schema_is_closed_and_fully_required_at_both_levels():
    probe = personas.fidelity_probe(
        _persona(_anchor("Beta", "not-sure", "none", held_out=True)),
    )
    assert probe is not None
    _turn, schema = probe
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["verdicts"]
    items = schema["properties"]["verdicts"]["items"]
    assert items["additionalProperties"] is False
    assert sorted(items["required"]) == ["reason_code", "verdict", "work"]
    for field in ("verdict", "reason_code"):
        assert items["properties"][field]["enum"]


# ------------------------------------------------------------------------ anchor_agreement


def test_perfect_held_out_answers_score_one_on_both_agreements():
    persona = _persona(
        _anchor("Alpha", "keep-reading", "curious", held_out=True),
        _anchor("Beta", "would-stop", "jargon-wall", held_out=True),
    )
    report = personas.anchor_agreement(persona, [
        {"work": "Alpha", "verdict": "keep-reading", "reason_code": "curious"},
        {"work": "Beta", "verdict": "would-stop", "reason_code": "jargon-wall"},
    ])
    assert report["persona"] == "tester"
    assert report["held_out"] == 2
    assert report["matched"] == 2
    assert report["verdict_agreement"] == 1.0
    assert report["reason_agreement"] == 1.0


def test_every_mismatched_verdict_scores_zero_while_reason_agreement_stays_independent():
    persona = _persona(_anchor("Alpha", "keep-reading", "curious", held_out=True))
    report = personas.anchor_agreement(persona, [
        {"work": "Alpha", "verdict": "would-stop", "reason_code": "curious"},
    ])
    assert report["matched"] == 1
    assert report["verdict_agreement"] == 0.0
    assert report["reason_agreement"] == 1.0


def test_partial_reason_agreement_is_rounded_to_four_decimal_places():
    persona = _persona(
        _anchor("A1", "keep-reading", "curious", held_out=True),
        _anchor("A2", "keep-reading", "curious", held_out=True),
        _anchor("A3", "keep-reading", "curious", held_out=True),
    )
    report = personas.anchor_agreement(persona, [
        {"work": "A1", "verdict": "keep-reading", "reason_code": "curious"},
        {"work": "A2", "verdict": "keep-reading", "reason_code": "none"},
        {"work": "A3", "verdict": "keep-reading", "reason_code": "none"},
    ])
    assert report["verdict_agreement"] == 1.0
    assert report["reason_agreement"] == round(1 / 3, 4) == 0.3333


def test_answer_work_fields_match_case_and_whitespace_insensitively():
    persona = _persona(_anchor("Odd  Title ", "not-sure", "none", held_out=True))
    report = personas.anchor_agreement(persona, [
        {"work": " odd  TITLE ", "verdict": "not-sure", "reason_code": "none"},
    ])
    assert report["matched"] == 1
    assert report["verdict_agreement"] == 1.0
    assert report["detail"][0]["work"] == "Odd  Title "


def test_answers_about_non_held_out_works_are_skipped_not_scored():
    persona = _persona(
        _anchor("Held", "keep-reading", "curious", held_out=True),
        _anchor("Shown", "keep-reading", "curious"),
    )
    report = personas.anchor_agreement(persona, [
        {"work": "Shown", "verdict": "keep-reading", "reason_code": "curious"},
        {"work": "Unknown", "verdict": "keep-reading", "reason_code": "curious"},
    ])
    assert report["held_out"] == 1
    assert report["matched"] == 0
    assert report["verdict_agreement"] == 0.0
    assert report["detail"] == []


def test_an_answer_without_a_work_field_matches_nothing_without_crashing():
    persona = _persona(_anchor("Held", "keep-reading", "curious", held_out=True))
    report = personas.anchor_agreement(persona, [
        {"verdict": "keep-reading", "reason_code": "curious"},
    ])
    assert report["matched"] == 0
    assert report["verdict_agreement"] == 0.0
    assert report["detail"] == []


def test_a_matched_answer_missing_its_verdict_counts_as_disagreement():
    persona = _persona(_anchor("Held", "keep-reading", "curious", held_out=True))
    report = personas.anchor_agreement(persona, [{"work": "Held", "reason_code": "curious"}])
    assert report["matched"] == 1
    assert report["verdict_agreement"] == 0.0
    entry = report["detail"][0]
    assert entry["expected_verdict"] == "keep-reading"
    assert entry["got_verdict"] is None
    assert entry["verdict_ok"] is False


def test_duplicate_held_out_titles_collapse_to_one_expected_entry_last_anchor_winning():
    persona = _persona(
        _anchor("Twin", "keep-reading", "curious", held_out=True),
        _anchor("Twin", "would-stop", "jargon-wall", held_out=True),
    )
    report = personas.anchor_agreement(persona, [
        {"work": "twin", "verdict": "would-stop", "reason_code": "jargon-wall"},
    ])
    assert report["held_out"] == 1
    assert report["matched"] == 1
    assert report["verdict_agreement"] == 1.0
    assert report["detail"][0]["expected_verdict"] == "would-stop"


def test_an_empty_answer_list_gives_zero_agreements_rather_than_dividing_by_zero():
    persona = _persona(_anchor("Held", "keep-reading", "curious", held_out=True))
    report = personas.anchor_agreement(persona, [])
    assert report["matched"] == 0
    assert report["verdict_agreement"] == 0.0
    assert report["reason_agreement"] == 0.0
    assert report["detail"] == []


def test_a_persona_with_no_held_out_anchors_reports_zeroes_for_any_answers():
    report = personas.anchor_agreement(
        _persona(),
        [{"work": "Anything", "verdict": "keep-reading", "reason_code": "curious"}],
    )
    assert report["held_out"] == 0
    assert report["matched"] == 0
    assert report["verdict_agreement"] == 0.0
    assert report["reason_agreement"] == 0.0
    assert report["detail"] == []
