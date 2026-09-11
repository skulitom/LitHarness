"""VS metadata cannot filter or select stories or leak into an expansion request."""

import importlib.util
import json
import random
from pathlib import Path

import pytest

from litharness.application import discovery
from litharness.domain.generation import CompletionRequest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-verbalized-20260911/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_verbalized_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_verbalized_controls_isolate_tail_instruction_and_object_format():
    requests = {a: experiment.invention_request(a, "OPAQUE_PREFIX", CompletionRequest)
                for a in experiment.ARMS}
    assert requests["batch"].schema == experiment.parent.SCHEMA
    assert requests["format"].schema == requests["full"].schema == requests["tail"].schema
    assert requests["tail"].system == requests["full"].system + "\n\n" + experiment.TAIL
    assert requests["format"].system == requests["batch"].system + "\n\n" + experiment.FORMAT
    assert requests["full"].system == requests["batch"].system + "\n\n" + experiment.FULL
    assert all(r.system.startswith("OPAQUE_PREFIX\n\n") for r in requests.values())
    assert len({r.prompt for r in requests.values()}) == 1
    with pytest.raises(ValueError):
        experiment.invention_request("unknown", "prefix", CompletionRequest)


def test_probability_estimates_never_reject_or_reorder_well_formed_stories():
    values = [-0.5, 0, 0.01, 0.1, 0.9, 1.5]
    items = [{"text": f"Story {i}", "probability": p} for i, p in enumerate(values)]
    for arm in ("format", "full", "tail"):
        assert experiment.parse_items({"premises": items}, arm) == items
    assert experiment.parse_items({"premises": [p["text"] for p in items]}, "batch") == [
        {"text": p["text"], "probability": None} for p in items
    ]


@pytest.mark.parametrize("bad", [True, "0.01", None, float("nan"), float("inf")])
def test_invalid_probability_shape_is_distinct_from_low_probability_compliance(bad):
    items = [{"text": "Premise", "probability": 0.01} for _ in range(6)]
    items[2]["probability"] = bad
    with pytest.raises(ValueError):
        experiment.parse_items({"premises": items}, "tail")


def test_expansion_uses_only_story_and_selection_has_no_response_argument():
    item = {"text": "SELECTED_STORY", "probability": 0.987654321}
    assert experiment.expansion_request(item, discovery) == discovery.render_request(
        item["text"], person="third"
    )
    state = random.getstate()
    assert experiment.selected_index("123456789") == random.Random(
        "invention-verbalized.v1:123456789"
    ).randrange(6)
    assert random.getstate() == state
    assert len(experiment.ORDER) + len(experiment.EXPANSIONS) == 16


def test_atomic_receipt_replacement_preserves_old_data_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    experiment.write(path, {"attempts": 1})

    def fail_replace(source, destination):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError):
        experiment.write(path, {"attempts": 2})
    assert json.loads(path.read_text()) == {"attempts": 1}
    assert json.loads(path.with_name("progress.json.tmp").read_text()) == {"attempts": 2}
