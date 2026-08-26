"""blurb_rewrite's frozen bytes and registered definitions, checked without calls.

What this file pins: the ask produces and never judges (the rail that makes the instrument
admissible at all), the request shape copied from the measurement conventions, the sentence
splitter on a three-sentence blurb and its edges, normalise's quote-and-echo stripping,
span_diff on pairs whose change_rate and spans were derived by hand before running, stable-
repair merging over overlapping spans, KG's share arithmetic, and the no-third-party-prose rule
on a pool-sourced result row. What it does not establish: anything about any model's rewriting
— no call happens here.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "research" / "quality-measurement"
if str(_HERE) not in sys.path:  # house pattern; conftest inserts it too, this is defensive
    sys.path.insert(0, str(_HERE))

blurb_rewrite = pytest.importorskip(
    "blurb_rewrite",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

# verdict vocabulary that must never reach a model in the frozen bytes
BANNED = re.compile(
    r"\b(fix|improve|polish|wrong|error|flaw|judge|quality|better|worse|rate|score)\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------------------- the frozen ask


def test_the_ask_produces_and_never_judges() -> None:
    assert "Write that sentence as it would be written" in blurb_rewrite.ASK
    assert "Reply with a single sentence" in blurb_rewrite.SYSTEM
    for byte_string in (blurb_rewrite.SYSTEM, blurb_rewrite.ASK):
        match = BANNED.search(byte_string)
        assert match is None, f"verdict word {match.group(0)!r} in a frozen byte string"


def test_requests_are_small_unschemaed_generation_class_calls() -> None:
    prompt = blurb_rewrite.render_ask("A Title", "One line. Two line.", 2, "Two line.")
    request = blurb_rewrite.build_request(prompt)
    assert request.system == blurb_rewrite.SYSTEM
    assert request.schema is None
    assert request.max_output_tokens == blurb_rewrite.MAX_OUTPUT_TOKENS == 256
    assert request.call_class == "generation"
    assert request.profile == "reader.rewrite.v0"


def test_the_ask_carries_title_blank_line_listing_sentence_and_k() -> None:
    prompt = blurb_rewrite.render_ask("Patch Notes", "He woke. It rained.", 2, "It rained.")
    assert prompt.startswith("Patch Notes\n\nHe woke. It rained.\n---\nSentence 2 of this "
                             "listing:\nIt rained.\n\n")


# ------------------------------------------------------------------------------- sentences


def test_sentences_splits_a_three_sentence_blurb_exactly() -> None:
    blurb = "Renn counted the seals twice. The tower was empty. He climbed anyway."
    assert blurb_rewrite.sentences(blurb) == [
        "Renn counted the seals twice.",
        "The tower was empty.",
        "He climbed anyway.",
    ]


def test_a_single_sentence_blurb_is_one_sentence() -> None:
    assert blurb_rewrite.sentences("Only one sentence lives here.") == [
        "Only one sentence lives here."
    ]


def test_a_trailing_ellipsis_stays_one_sentence_and_a_mid_ellipsis_splits() -> None:
    assert blurb_rewrite.sentences("It kept falling...") == ["It kept falling..."]
    assert blurb_rewrite.sentences("It kept falling... Then silence.") == [
        "It kept falling...",
        "Then silence.",
    ]


def test_abbreviation_false_splits_fall_as_they_fall() -> None:
    # Registered limitation, asserted so any "fix" to it shows up as a deliberate change.
    assert blurb_rewrite.sentences("He met Mr. Wu inside.") == ["He met Mr.", "Wu inside."]


# ------------------------------------------------------------------------------- normalise


def test_normalise_strips_surrounding_quotes_and_collapses_whitespace() -> None:
    assert blurb_rewrite.normalise('  "The tower was empty."  ') == "The tower was empty."


def test_normalise_drops_a_leading_sentence_echo() -> None:
    assert blurb_rewrite.normalise("Sentence 12: He took the stairs.") == "He took the stairs."
    assert blurb_rewrite.normalise('"Sentence 3: He took the stairs."') == "He took the stairs."

# ------------------------------------------------------------------------------- span_diff


def test_an_exact_echo_diffs_to_zero_with_no_changed_spans() -> None:
    sentence = "He found a patch of notes on the desk."
    assert blurb_rewrite.span_diff(sentence, sentence) == (0.0, [])


def test_a_two_token_replace_has_the_exact_hand_derived_rate_and_span() -> None:
    # Tokens: the ward |held firm| -> |gave way|. 4 original tokens, 2 matched, so
    # change_rate = 1 - 2/4 = 1/2 and the original-side span is token offsets [2, 4).
    original = "the ward held firm"
    rewrite = "the ward gave way"
    rate, spans = blurb_rewrite.span_diff(original, rewrite)
    assert rate == pytest.approx(1 / 2)
    assert spans == [(2, 4)]


def test_overlapping_changed_spans_from_three_draws_merge_into_one_stable_repair() -> None:
    # (2,6) twice and (4,8) once: token votes are 2,2,3,3,1,1 so positions 4-5 reach the
    # threshold of 3 draws and merge to one span; nothing else is stable.
    draws = [[(2, 6)], [(2, 6)], [(4, 8)], []]
    assert blurb_rewrite.stable_repairs(draws, n_tokens=10) == [(4, 6)]


def test_spans_below_three_of_four_draws_are_not_stable() -> None:
    assert blurb_rewrite.stable_repairs([[(0, 2)], [(0, 2)]], n_tokens=10) == []
    assert blurb_rewrite.stable_repairs([[(0, 2)], [(5, 7)], [(0, 2)], [(5, 7)]], n_tokens=10) == (
        []
    )


# --------------------------------------------------------------------------- the controls


def test_kg_share_counts_pairs_where_low_needs_more_repair() -> None:
    pairs = [(0.60, 0.20), (0.50, 0.30), (0.40, 0.35), (0.20, 0.50)]
    stat = blurb_rewrite.gradient_stat(pairs)
    assert stat["pairs"] == 4
    assert stat["wins"] == 3
    assert stat["share"] == pytest.approx(0.75)
    lo, hi = stat["bootstrap_interval"]
    assert 0.0 <= lo <= hi <= 1.0


def test_kf_summary_reports_both_rounds_and_the_direction_share() -> None:
    summary = blurb_rewrite.fixed_point_summary([0.4, 0.3], [0.1, 0.35])
    assert summary["pairs"] == 2
    assert summary["round1_mean"] == pytest.approx(0.35)
    assert summary["round2_mean"] == pytest.approx(0.225)
    assert summary["share_round2_below"] == pytest.approx(0.5)


# --------------------------------------------------------------------- the prose firewall


def test_a_pool_sourced_result_row_contains_no_third_party_prose() -> None:
    original = "A patch of notes lined the shelf beside his certainties."
    rewrites = ["A ledger of receipts filled the shelf beside his convictions."]
    row = blurb_rewrite.sentence_report(1, original, rewrites, allow_prose=False)
    blob = json.dumps(row)
    for leak in ("patch", "notes", "ledger", "receipts", "certainties", "convictions", "shelf"):
        assert leak not in blob, f"pool row leaked the prose word {leak!r}"
    # The same call with allow_prose=True is where our own listings' prose is allowed.
    ours = blurb_rewrite.sentence_report(1, original, rewrites, allow_prose=True)
    assert ours["original"] == original


def test_a_pool_sourced_listing_row_carries_offsets_and_counts_only() -> None:
    body = "A patch of notes lined the shelf. He sold his certainties by the yard."
    replies = [["A ledger filled the crate."] * blurb_rewrite.K_DRAWS,
               ["He sold certainties wholesale."] * blurb_rewrite.K_DRAWS]
    report = blurb_rewrite.listing_report(
        "some-rival", "Some Rival", body, replies, source_kind="high", allow_prose=False
    )
    blob = json.dumps(report)
    assert "patch" not in blob and "certainties" not in blob
    assert report["digest"] and report["words"] == len(body.split())
    assert all("original" not in row for row in report["sentences"])
    assert all("rewrites" not in row for row in report["sentences"])


# --------------------------------------------------------------------------------- selftest


def test_the_selftest_passes() -> None:
    assert blurb_rewrite.selftest() == 0

# END_OF_CHUNK_2