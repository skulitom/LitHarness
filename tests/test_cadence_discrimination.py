"""Hermetic pins on the pure core of `research/quality-measurement/cadence_discrimination.py`.

What these tests pin: the classification edges of the two frozen matchers (`names_cadence`,
`claims_omission`), scene-to-span partitioning (`spans`), placement-by-fraction and its
guarantees (`place`: original paragraphs untouched, word multiset preserved, distinct
boundaries), pair construction and both controls (`build_pairs`), the premise check
(`certify`), and the verdict buckets (`score`: UNREADABLE, NAMES_CADENCE, DOES_NOT, and VOID
from either control firing).

What they do not establish: anything about whether a model can name cadence. No network, no
model call, no corpus or results read, no subprocess, no sleep — every expectation below was
derived by hand from the functions' code before running them. `selftest()` is deliberately
not called: it reads `corpora/toll-scenes.json`, so it is not hermetic. Spans passed through
`place` keep at least four paragraphs, because below that the insert-position dedup walk can
exhaust its distinct boundaries and never terminate; that hazard is noted here rather than
pinned as a hanging test.
"""

from __future__ import annotations

import dataclasses
import sys
from collections import Counter
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

cadence = pytest.importorskip(
    "cadence_discrimination",
    reason="research module; needs the quality-measurement directory on the path",
)


def _span(*paragraphs: str) -> str:
    return "\n\n".join(paragraphs)


#: Five short paragraphs. Each carries a ". Capital" seam so the whitespace sham has something
#: to change, and five is safely above the paragraph floor noted in the module docstring.
PROSE_SPAN = _span(
    "Arbor vale quiets. Merton counts the boats twice.",
    "The ferryman waits. Nobody pays him today.",
    "A lamp burns low. Sela trims the wick and sits.",
    "Rain finds the roof. The ledger stays open.",
    "Morning arrives late. The harbour answers anyway.",
)


def _row(arm: str, *, fired: bool, refused: bool = False) -> dict[str, object]:
    return {"arm": arm, "refused": refused, "named_cadence": fired, "pair": f"p-{arm}"}


# --------------------------------------------------------------------------- names_cadence


def test_names_cadence_accepts_responses_that_name_placement():
    assert cadence.names_cadence(
        "One resolves things throughout and the other saves it all for the end."
    )
    assert cadence.names_cadence("Passage two clusters its revelations early.")


def test_names_cadence_rejects_responses_that_name_no_cadence_property():
    assert not cadence.names_cadence("One passage is more descriptive than the other.")
    assert not cadence.names_cadence("They are identical.")
    assert not cadence.names_cadence("Passage A uses double spaces after periods.")


def test_names_cadence_treats_none_and_empty_as_silent():
    assert not cadence.names_cadence(None)
    assert not cadence.names_cadence("")


def test_names_cadence_requires_the_phrase_spread_out_not_spread_alone():
    assert not cadence.names_cadence("The scenes are spread across the passage.")
    assert cadence.names_cadence("The scenes are spread out across the passage.")


# ------------------------------------------------------------------------- claims_omission


def test_claims_omission_fires_on_a_claim_that_text_is_missing_or_left_out():
    assert cadence.claims_omission("Passage two omits the scene where the debt is paid.")
    assert cadence.claims_omission("Passage one leaves out the ending's answer.")


def test_claims_omission_stays_silent_on_a_difference_that_is_not_an_omission():
    assert not cadence.claims_omission(
        "One resolves things throughout and the other saves it all for the end."
    )
    assert not cadence.claims_omission("They are identical.")


def test_claims_omission_treats_none_and_empty_as_silent():
    assert not cadence.claims_omission(None)
    assert not cadence.claims_omission("")


def test_claims_omission_matches_detail_as_a_noun_but_not_detailed():
    assert cadence.claims_omission("The first passage gives more detail than the second.")
    assert not cadence.claims_omission("The first passage is more detailed.")


# ------------------------------------------------------------------------------------ Pair


def test_pair_compares_equal_to_and_hashes_with_an_identical_pair():
    first = cadence.Pair("id", "arm", "left text", "right text")
    second = cadence.Pair("id", "arm", "left text", "right text")
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_pair_refuses_field_assignment():
    pair = cadence.Pair("id", "arm", "left", "right")
    with pytest.raises(dataclasses.FrozenInstanceError):
        pair.arm = "other"


# ----------------------------------------------------------------------------------- spans


def test_spans_joins_consecutive_scene_pairs_into_disjoint_spans():
    assert cadence.spans(["a", "b", "c", "d"]) == ["a\n\nb", "c\n\nd"]


def test_spans_drops_a_final_scene_that_cannot_fill_one():
    joined = cadence.spans(["a", "b", "c", "d", "e"])
    assert joined == ["a\n\nb", "c\n\nd"]
    assert all("e" not in span for span in joined)
def test_spans_of_no_scenes_is_empty():
    assert cadence.spans([]) == []


def test_spans_of_fewer_scenes_than_one_span_holds_is_empty():
    assert cadence.spans(["a"]) == []


def test_spans_of_one_scene_each_returns_every_scene_alone():
    assert cadence.spans(["a", "b"], per_span=1) == ["a", "b"]


# ----------------------------------------------------------------------------------- place


def test_place_inserts_payoffs_before_paragraphs_at_the_requested_fractions():
    blocks = [f"block {index}" for index in range(10)]
    placed = cadence.place(_span(*blocks), (0.20, 0.40, 0.60, 0.80))
    # round(fraction * 10) lands on 2, 4, 6 and 8, so each payoff precedes its own block.
    assert placed.split("\n\n") == [
        "block 0",
        "block 1",
        cadence.PAYOFFS[0],
        "block 2",
        "block 3",
        cadence.PAYOFFS[1],
        "block 4",
        "block 5",
        cadence.PAYOFFS[2],
        "block 6",
        "block 7",
        cadence.PAYOFFS[3],
        "block 8",
        "block 9",
    ]


def test_place_keeps_every_original_paragraph_byte_identical_and_in_order():
    blocks = [f"block {index}" for index in range(5)]
    placed = cadence.place(_span(*blocks), (0.20, 0.40, 0.60, 0.80))
    survivors = [piece for piece in placed.split("\n\n") if piece not in cadence.PAYOFFS]
    assert survivors == blocks


def test_place_preserves_the_word_multiset_for_every_cadence():
    expected = sorted(
        PROSE_SPAN.split() + [word for payoff in cadence.PAYOFFS for word in payoff.split()]
    )
    for fractions in cadence.CADENCES.values():
        placed = cadence.place(PROSE_SPAN, fractions)
        assert sorted(placed.split()) == expected


def test_place_on_an_empty_span_returns_it_unmodified():
    assert cadence.place("", (0.20, 0.40, 0.60, 0.80)) == ""


def test_place_clamps_fraction_zero_and_one_to_the_outer_edges():
    blocks = [f"block {index}" for index in range(4)]
    placed = cadence.place(_span(*blocks), (1.0, 0.0))
    assert placed.split("\n\n") == [
        cadence.PAYOFFS[1],
        "block 0",
        "block 1",
        "block 2",
        "block 3",
        cadence.PAYOFFS[0],
    ]


def test_place_sends_colliding_fractions_to_distinct_adjacent_boundaries():
    blocks = [f"block {index}" for index in range(5)]
    placed = cadence.place(_span(*blocks), (0.4, 0.4))
    pieces = placed.split("\n\n")
    # Both fractions round to boundary 2; the second walks to 3 rather than merging with it.
    assert len(pieces) == 7
    assert pieces[2] == cadence.PAYOFFS[0]
    assert pieces[3] == "block 2"
    assert pieces[4] == cadence.PAYOFFS[1]
    assert pieces[5] == "block 3"

# ------------------------------------------------------------------------------ build_pairs


def test_build_pairs_makes_five_pairs_per_span_over_three_arms():
    pairs = cadence.build_pairs([PROSE_SPAN, PROSE_SPAN])
    assert len(pairs) == 10
    assert Counter(pair.arm for pair in pairs) == Counter(
        {"cadence": 6, "placebo": 2, "sham": 2}
    )


def test_build_pairs_ids_name_the_span_index_and_the_contrast():
    pairs = cadence.build_pairs([PROSE_SPAN])
    assert {pair.pair_id for pair in pairs} == {
        "cadence-0-even-vs-front_loaded",
        "cadence-0-even-vs-starved_dumped",
        "cadence-0-front_loaded-vs-starved_dumped",
        "placebo-0",
        "sham-0",
    }


def test_build_pairs_faces_the_placebo_variant_against_itself():
    for pair in cadence.build_pairs([PROSE_SPAN]):
        if pair.arm == "placebo":
            assert pair.left == pair.right


def test_build_pairs_makes_the_sham_differ_only_in_whitespace():
    shams = [pair for pair in cadence.build_pairs([PROSE_SPAN]) if pair.arm == "sham"]
    assert len(shams) == 1
    assert shams[0].right != shams[0].left
    assert shams[0].right.split() == shams[0].left.split()


def test_build_pairs_of_no_spans_is_empty():
    assert cadence.build_pairs([]) == []


# ---------------------------------------------------------------------------------- certify


def test_certify_passes_a_well_formed_multi_paragraph_span():
    assert cadence.certify([PROSE_SPAN]) == []


def test_certify_faults_an_empty_span_whose_variants_are_byte_identical():
    faults = cadence.certify([""])
    assert sum(1 for fault in faults if "byte-identical" in fault) == 1
    # One missing-payoff fault per cadence variant, and none claiming the words diverge.
    assert sum(1 for fault in faults if "payoffs are present" in fault) == 3
    assert not any("identical words" in fault for fault in faults)


def test_certify_reports_no_faults_for_no_spans():
    assert cadence.certify([]) == []


# ------------------------------------------------------------------------------------ score


def test_score_reads_an_empty_batch_as_unreadable():
    report = cadence.score([])
    assert report["verdict"] == "UNREADABLE"
    assert report["cadence_rate"] is None
    assert report["null_rate"] is None
    assert report["fisher_p"] == 1.0


def test_score_excludes_refused_rows_from_every_count():
    report = cadence.score([
        _row("cadence", fired=True),
        _row("cadence", fired=True, refused=True),
        _row("placebo", fired=False),
        _row("sham", fired=False),
    ])
    assert report["cadence"] == {"fired": 1, "responses": 1}
    assert report["null"] == {"fired": 0, "responses": 2}


def test_score_reads_a_clean_batch_with_every_cadence_cell_firing_as_names_cadence():
    rows = [_row("cadence", fired=True) for _ in range(20)]
    rows += [_row("placebo", fired=False) for _ in range(10)]
    rows += [_row("sham", fired=False) for _ in range(10)]
    report = cadence.score(rows)
    assert report["verdict"] == "NAMES_CADENCE"
    assert report["controls_hold"] is True
    assert report["cadence_rate"] == 1.0
    assert report["null_rate"] == 0.0


def test_score_reads_a_batch_where_the_matcher_never_fires_as_does_not():
    rows = [_row(arm, fired=False) for arm in ("cadence", "placebo", "sham")] * 20
    report = cadence.score(rows)
    assert report["verdict"] == "DOES_NOT"
    assert report["cadence_rate"] == 0.0


def test_score_voids_a_perfect_signal_when_the_placebo_names_cadence():
    rows = [_row("cadence", fired=True) for _ in range(5)]
    rows += [_row("placebo", fired=True)]
    rows += [_row("sham", fired=False)]
    report = cadence.score(rows)
    assert report["verdict"] == "VOID"
    assert report["controls_hold"] is False


def test_score_voids_a_batch_when_only_the_whitespace_sham_names_cadence():
    rows = [_row("cadence", fired=True) for _ in range(5)]
    rows += [_row("placebo", fired=False)]
    rows += [_row("sham", fired=True)]
    assert cadence.score(rows)["verdict"] == "VOID"


def test_score_counts_omission_claims_per_arm_from_optional_row_fields():
    cadence_fired = _row("cadence", fired=True)
    cadence_fired["claims_omission"] = True
    cadence_quiet = _row("cadence", fired=True)
    cadence_quiet["claims_omission"] = False
    placebo = _row("placebo", fired=False)
    placebo["claims_omission"] = True
    report = cadence.score([cadence_fired, cadence_quiet, placebo])
    assert report["DIAGNOSTIC_omission_claims"]["cadence"] == {"claims": 1, "responses": 2}
    assert report["DIAGNOSTIC_omission_claims"]["placebo"] == {"claims": 1, "responses": 1}
    assert "sham" not in report["DIAGNOSTIC_omission_claims"]


