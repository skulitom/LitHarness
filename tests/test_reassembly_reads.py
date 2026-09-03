"""The order-recovery arm's registered classes and its analysis, checked without a call.

What this file pins: the stimulus table matches the class counts `PREREG.md` fixed before
spend (twelve chapters where the operator named a chapter-level item, seven where every item
was a sentence); the paired-class bootstrap refuses below two chapters a side rather than
manufacturing a bound, is deterministic in its inputs, and names its direction; and the
description assembles each of the three registered readings plus the below-the-anchors list.
What it does not establish: anything about any chapter's recoverability — no call happens here.

**Why it exists.** The arm's analysis had never executed when it was registered; only its dry
run had. A defect in the reading would have surfaced after $30 of calls, which is the
"the first paid run is also the first integration test" failure this directory keeps recording.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_RUN = (
    Path(__file__).resolve().parent.parent
    / "research"
    / "quality-measurement"
    / "reassembly-reads"
    / "run.py"
)

if not _RUN.is_file():  # pragma: no cover - research tree absent
    pytest.skip("research module absent", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("reassembly_reads_run", _RUN)
assert _spec is not None and _spec.loader is not None
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)

#: The four placed openings' means from `../reassembly/results.json`, the reference range.
ANCHORS = {
    "shelf-primal-hunter": 0.9969,
    "shelf-randidly": 0.9954,
    "shelf-defiance": 0.8835,
    "shelf-gam3": 0.8544,
}


def _rows(s_taus: list[float], t_taus: list[float]) -> dict[str, dict[str, Any]]:
    rows = {f"s{i}": {"class": "S", "mean_tau": tau} for i, tau in enumerate(s_taus)}
    rows.update({f"t{i}": {"class": "T", "mean_tau": tau} for i, tau in enumerate(t_taus)})
    return rows


# ------------------------------------------------------------------ the registered stimuli


def test_the_stimulus_table_carries_the_classes_the_registration_fixed() -> None:
    classes = [cls for _name, _root, _relative, cls in arm.STIMULI]
    assert len(arm.STIMULI) == 19
    assert classes.count("S") == 12
    assert classes.count("T") == 7
    names = [name for name, _root, _relative, _cls in arm.STIMULI]
    assert len(set(names)) == len(names), "a stimulus is listed twice"


def test_every_reused_stimulus_is_in_the_table_and_names_a_prior_cell() -> None:
    names = {name for name, _root, _relative, _cls in arm.STIMULI}
    for name, key in arm.REUSED.items():
        assert name in names, f"{name} is reused but not a registered stimulus"
        assert key.startswith("ours-"), key


def test_a_stimulus_root_resolves_under_the_root_it_names() -> None:
    library, runs = Path("/lib"), Path("/runs")
    where = {"library": library, "runs": runs}
    for root, base in where.items():
        assert arm.stimulus_path(root, "a/b.txt", library=library, runs=runs) == base / "a/b.txt"


# --------------------------------------------------------------------- the paired bootstrap


def test_the_bootstrap_refuses_below_two_chapters_in_either_class() -> None:
    one_sided = arm.class_difference(_rows([0.9, 0.8], [0.95]))
    assert one_sided["interval"] is None
    assert one_sided["t"] == 1
    assert arm.class_difference(_rows([0.9], [0.95, 0.96]))["interval"] is None
    assert arm.class_difference({})["interval"] is None


def test_the_bootstrap_is_deterministic_in_its_values_and_orders_t_minus_s() -> None:
    rows = _rows([0.80, 0.82, 0.84, 0.86], [0.90, 0.92, 0.94, 0.96])
    first, second = arm.class_difference(rows), arm.class_difference(rows)
    assert first == second
    # means 0.93 and 0.83, so T minus S is 0.10 and the sign says T recovers better.
    assert first["point"] == pytest.approx(0.10, abs=1e-9)
    assert first["low"] <= first["point"] <= first["high"]
    assert first["s"] == 4 and first["t"] == 4
    assert first["alpha"] == arm.ALPHA and first["resamples"] == arm.RESAMPLES


def test_a_wide_separation_reads_above_zero_and_its_mirror_reads_below() -> None:
    high_t = arm.class_difference(_rows([0.50, 0.52, 0.54, 0.56], [0.90, 0.92, 0.94, 0.96]))
    assert high_t["above_zero"] is True and high_t["below_zero"] is False
    high_s = arm.class_difference(_rows([0.90, 0.92, 0.94, 0.96], [0.50, 0.52, 0.54, 0.56]))
    assert high_s["below_zero"] is True and high_s["above_zero"] is False


def test_overlapping_classes_leave_zero_inside_the_interval() -> None:
    overlapping = arm.class_difference(
        _rows([0.80, 0.90, 0.85, 0.95], [0.82, 0.93, 0.84, 0.91])
    )
    assert overlapping["above_zero"] is False and overlapping["below_zero"] is False
    assert overlapping["low"] <= 0.0 <= overlapping["high"]


# ------------------------------------------------------------------------- the description


@pytest.mark.parametrize(
    ("s_taus", "t_taus", "expected"),
    [
        ([0.50, 0.52, 0.54, 0.56], [0.90, 0.92, 0.94, 0.96],
         "RECOVERABILITY_RUNS_WITH_THE_CHAPTER_LEVEL_ITEMS"),
        ([0.90, 0.92, 0.94, 0.96], [0.50, 0.52, 0.54, 0.56], "INVERTED"),
        ([0.80, 0.90, 0.85, 0.95], [0.82, 0.93, 0.84, 0.91], "NO_SEPARATION"),
    ],
)
def test_the_description_reads_each_registered_outcome(
    s_taus: list[float], t_taus: list[float], expected: str
) -> None:
    assert arm.describe(_rows(s_taus, t_taus), ANCHORS)["reading"] == expected


def test_the_description_carries_the_anchor_range_and_both_class_summaries() -> None:
    described = arm.describe(_rows([0.80, 0.90, 0.85, 0.95], [0.82, 0.93, 0.84, 0.91]), ANCHORS)
    assert described["anchors_range"] == [0.8544, 0.9969]
    for name, count in (("S", 4), ("T", 4)):
        block = described["classes"][name]
        assert block["chapters"] == count
        assert block["min"] <= block["mean"] <= block["max"]
        # Listed per chapter and sorted by tau, so the weakest chapter is readable at a glance.
        assert list(block["per_chapter"].values()) == sorted(block["per_chapter"].values())


def test_chapters_below_the_anchor_range_are_named_whatever_their_class() -> None:
    described = arm.describe(_rows([0.40, 0.90, 0.88, 0.91], [0.30, 0.93, 0.92, 0.94]), ANCHORS)
    # The anchors' floor is Gam3 at 0.8544; both weak chapters fall under it, one per class.
    assert described["below_anchors_range"] == ["s0", "t0"]


def test_a_class_too_small_to_bootstrap_reads_unreadable_rather_than_a_number() -> None:
    described = arm.describe(_rows([0.90, 0.88, 0.91], [0.93]), ANCHORS)
    assert described["reading"] == "UNREADABLE"
    assert described["t_minus_s"]["interval"] is None
