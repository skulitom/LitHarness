"""What `_persona_degeneracy` computes, pinned on inputs whose answers are derived by hand.

The function is the corrected reading under §89: the independent unit of a screen is the
(pair, orientation) cell, personas are replicates when they answer alike, and a panel whose
answer vectors coincide is one judge wearing several hats. These tests pin that arithmetic —
the degeneracy flag on each side of its `distinct < seated` boundary, the cell counting
(including the rule that one decided persona makes the whole cell decided), the treatment of
abstentions and missing rows, and the per-persona chose-A rates — using small constructed
comparison lists, no fixtures, no transport, no files.

They do not establish anything about `screen`, which cannot be driven without an `Elicitor`
(it builds one directly, reads the fixture families from disk, and caches raw comparisons
under `results/`); stubbing all three would test the stubs, so `screen`'s status logic is
deliberately uncovered here. Nor do they establish that any real judge is eligible: nothing
here touches a model, and the module has no `selftest()` to call.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

latent_crossfamily = pytest.importorskip(
    "latent_crossfamily",
    reason="research module; needs the quality-measurement directory on the path",
)


@dataclass
class Row:
    """The attributes `_persona_degeneracy` reads off a comparison."""

    persona_id: str
    pair_id: str
    orientation: int
    choice: str | None


def test_an_empty_comparison_list_reports_no_personas_and_no_cells():
    report = latent_crossfamily._persona_degeneracy([])
    assert report["personas_seated"] == 0
    assert report["distinct_answer_vectors"] == 0
    assert report["degenerate"] is False
    assert report["independent_cells"] == 0
    assert report["decided_cells"] == 0
    assert report["per_persona_chose_A"] == {}


def test_one_persona_on_one_cell_is_not_degenerate_and_its_cell_is_decided():
    # One judge cannot be degenerate by replication: distinct == seated is the boundary itself.
    report = latent_crossfamily._persona_degeneracy([Row("p1", "s1", 0, "A")])
    assert report["personas_seated"] == 1
    assert report["distinct_answer_vectors"] == 1
    assert report["degenerate"] is False
    assert report["independent_cells"] == 1
    assert report["decided_cells"] == 1


def test_two_personas_with_identical_answer_vectors_are_degenerate():
    # The §89 shape: qwen3:14b returned one answer vector across four personas, byte-identical.
    rows = [
        Row("p1", "s1", 0, "A"),
        Row("p1", "s1", 1, "B"),
        Row("p2", "s1", 0, "A"),
        Row("p2", "s1", 1, "B"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["personas_seated"] == 2
    assert report["distinct_answer_vectors"] == 1
    assert report["degenerate"] is True


def test_two_personas_differing_on_one_cell_are_not_degenerate():
    # One cell apart is the smallest possible disagreement, and it already clears the flag.
    rows = [
        Row("p1", "s1", 0, "A"),
        Row("p1", "s1", 1, "B"),
        Row("p2", "s1", 0, "B"),
        Row("p2", "s1", 1, "B"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["personas_seated"] == 2
    assert report["distinct_answer_vectors"] == 2
    assert report["degenerate"] is False


def test_a_panel_of_three_with_two_answer_vectors_is_degenerate():
    # Two of three agreeing is still fewer distinct vectors than seats: replicates, not judges.
    rows = [
        Row("p1", "s1", 0, "A"),
        Row("p2", "s1", 0, "A"),
        Row("p3", "s1", 0, "B"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["personas_seated"] == 3
    assert report["distinct_answer_vectors"] == 2
    assert report["degenerate"] is True


def test_a_cell_is_decided_when_any_persona_answers_a_slot():
    # Cell (s1,0): p1 abstains but p2 picks A, so the cell carries a decision. Cell (s1,1):
    # nobody picks a slot — p1 says neither and p2 has no row at all — so it does not.
    rows = [
        Row("p1", "s1", 0, "neither"),
        Row("p1", "s1", 1, "neither"),
        Row("p2", "s1", 0, "A"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["personas_seated"] == 2
    assert report["independent_cells"] == 2
    assert report["decided_cells"] == 1


def test_both_orientations_of_one_pair_count_as_two_independent_cells():
    rows = [
        Row("p1", "s1", 0, "A"),
        Row("p1", "s1", 1, "A"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["independent_cells"] == 2
    assert report["decided_cells"] == 2
    assert report["per_persona_chose_A"]["p1"] == 1.0


def test_chose_a_rate_counts_only_decided_answers_and_rounds_to_four_places():
    # p1 answered A, B, B, neither across four cells: 1 of 3 decided answers is A -> 0.3333.
    rows = [
        Row("p1", "s1", 0, "A"),
        Row("p1", "s1", 1, "B"),
        Row("p1", "s1", 2, "B"),
        Row("p1", "s1", 3, "neither"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["per_persona_chose_A"]["p1"] == 0.3333


def test_an_all_b_persona_scores_zero_and_an_all_a_persona_scores_one():
    rows = [
        Row("b_only", "s1", 0, "B"),
        Row("b_only", "s1", 1, "B"),
        Row("a_only", "s1", 0, "A"),
        Row("a_only", "s1", 1, "A"),
    ]
    rates = latent_crossfamily._persona_degeneracy(rows)["per_persona_chose_A"]
    assert rates["b_only"] == 0.0
    assert rates["a_only"] == 1.0


def test_a_persona_with_no_decided_answers_scores_zero_rather_than_crashing():
    rows = [
        Row("p1", "s1", 0, "neither"),
        Row("p1", "s1", 1, None),
        Row("p2", "s1", 0, "B"),
        Row("p2", "s1", 1, "A"),
    ]
    report = latent_crossfamily._persona_degeneracy(rows)
    assert report["per_persona_chose_A"]["p1"] == 0.0
    assert report["per_persona_chose_A"]["p2"] == 0.5


def test_the_report_does_not_depend_on_the_order_of_the_input_rows():
    ordered = [
        Row("p1", "s1", 0, "A"),
        Row("p1", "s1", 1, "neither"),
        Row("p2", "s1", 1, "B"),
        Row("p2", "s1", 0, "B"),
        Row("p2", "s1", 2, "A"),
    ]
    shuffled = [ordered[i] for i in (4, 0, 3, 1, 2)]
    forward = latent_crossfamily._persona_degeneracy(ordered)
    backward = latent_crossfamily._persona_degeneracy(shuffled)
    assert forward == backward