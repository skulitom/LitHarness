"""Research collection controls without a model, network call or GPU."""

from __future__ import annotations

import copy
import importlib.util
from collections import Counter
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/jev-verification-20260919/benchmark.py"
)


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("jev_benchmark_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def perfect_rows(bench):
    rows = bench.manifest()["cases"]
    for row in rows:
        row.update({
            "prediction": row["expected"],
            "probabilities": [float(label == row["expected"]) for label in bench.LABELS],
            "tokens": 40, "inference_seconds": 0.1, "temperature_c": 40,
        })
    return rows


def test_control_construction_and_missing_evidence_are_neutral(bench):
    cases = bench.build_cases()
    assert len(cases) == 360
    assert len({row["id"] for row in cases}) == 360
    assert len({row["family"] for row in cases}) == 12
    base = [row for row in cases if row["variant"] == "base"]
    assert Counter(row["expected"] for row in base) == dict.fromkeys(bench.LABELS, 24)
    for family in {row["family"] for row in cases}:
        for surface in (0, 1):
            triple = [row for row in base if row["family"] == family and row["surface"] == surface]
            assert len({row["hypothesis"] for row in triple}) == 1  # no label in hypothesis
            neutral = next(row for row in triple if row["expected"] == "neutral")
            removed = [row for row in cases if row["family"] == family
                       and row["surface"] == surface and row["variant"] == "remove_evidence"]
            assert all(row["expected"] == "neutral" for row in removed)
            assert all(row["premise"] == neutral["premise"] for row in removed)
    by_id = {row["id"]: row for row in cases}
    for row in cases:
        original = by_id[row["id"].rsplit(".", 1)[0] + ".base"]
        if row["variant"] == "reflow":
            assert row["premise"].split() == original["premise"].split()
            assert row["hypothesis"].split() == original["hypothesis"].split()
        elif row["variant"] == "rename":
            assert row["premise"] != original["premise"]
        elif row["variant"] == "distractor":
            assert original["premise"] in row["premise"]


def test_metadata_is_never_part_of_model_input(bench):
    case = bench.build_cases()[0]
    changed = {**case, "id": "SECRET", "expected": "OTHER", "family": "HIDDEN"}
    assert bench.format_input(case) == bench.format_input(changed)


def test_artifact_hashes_survive_git_line_ending_normalisation(bench, tmp_path):
    output = tmp_path / "data.json"
    bench.write_json(output, {"key": "value"})
    assert b"\r" not in output.read_bytes()
    assert output.read_bytes().endswith(b"\n")


@pytest.mark.parametrize("lengths", [[], [0], [4097], [12, 5000]])
def test_no_silent_truncation(bench, lengths):
    with pytest.raises(ValueError, match="never silently truncate"):
        bench.check_tokens(lengths)
    bench.check_tokens([1, 4096])


@pytest.mark.parametrize("values", [[0.5, 0.5], [0.9, 0.9, 0.9], [float("nan"), 0, 1], [-1, 1, 1]])
def test_invalid_scores_cannot_enter_analysis(bench, values):
    with pytest.raises(ValueError, match="probability"):
        bench.prediction(values)


def test_metrics_separate_correctness_from_invariance_and_confidence(bench):
    rows = perfect_rows(bench)
    report = bench.analyse(rows, bench.manifest())
    assert report["all"]["accuracy"] == 1
    assert report["all"]["multiclass_brier_sum"] == 0
    assert not report["invariance"]["rename"]["prediction_flips"]
    bad = next(row for row in rows if row["variant"] == "rename"
               and row["expected"] == "contradiction")
    bad.update(prediction="entailment", probabilities=[0.01, 0.98, 0.01])
    report = bench.analyse(rows, bench.manifest())
    assert report["all"]["confident_false_entailments"] == [bad["id"]]
    assert report["invariance"]["rename"]["prediction_flips"] == [bad["id"]]
    for row in rows:
        row.update(prediction="neutral", probabilities=[0.0, 0.0, 1.0])
    report = bench.analyse(rows, bench.manifest())
    assert report["by_variant"]["base"]["accuracy"] == pytest.approx(1 / 3)
    assert report["by_variant"]["remove_evidence"]["accuracy"] == 1
    assert report["all"]["accuracy"] < 0.5


@pytest.mark.parametrize("fault", ["missing", "duplicate", "metadata", "probabilities"])
def test_incomplete_or_mismatched_observations_are_rejected(bench, fault):
    rows = copy.deepcopy(perfect_rows(bench))
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows[-1] = rows[0]
    elif fault == "metadata":
        rows[0]["expected"] = "entailment"
    else:
        rows[0]["probabilities"] = [0, 1, 0]
    with pytest.raises(ValueError):
        bench.analyse(rows, bench.manifest())


def test_thermal_hysteresis_and_sensor_failure(bench, monkeypatch):
    readings = iter([73, 69, 66, 65])
    sleeps = []
    monkeypatch.setattr(bench, "temperature", lambda: next(readings))
    monkeypatch.setattr(bench.time, "sleep", sleeps.append)
    assert bench.cool(2) == 65
    assert sleeps == [2, 5, 5, 5]

    def failed_sensor():
        raise RuntimeError("sensor unavailable")

    monkeypatch.setattr(bench, "temperature", failed_sensor)
    with pytest.raises(RuntimeError, match="sensor unavailable"):
        bench.cool(0)
