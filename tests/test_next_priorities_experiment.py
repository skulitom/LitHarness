"""Registration controls and a counterexample to payoff deletion as a hidden key."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

FOLDER = (
    Path(__file__).resolve().parents[1] / "research/quality-measurement/next-priorities-20260913"
)


def module(name):
    spec = importlib.util.spec_from_file_location(f"next_priorities_{name}", FOLDER / f"{name}.py")
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FOLDER))
    try:
        spec.loader.exec_module(result)
    finally:
        sys.path.remove(str(FOLDER))
    return result


def test_goal_cells_change_only_the_registered_passage_and_instruction():
    run = module("run")
    original = {
        "prompt": "Before. Perhaps a return. After.",
        "system": "Reconcile.",
        "profile": "architect.grow.v4",
        "allowed_tools": ["one"],
    }
    change = {
        "before": "Perhaps a return.",
        "after": "She chose to return.",
        "clarification": "Preserve established desires.",
    }
    cells = run.requests(original, change)
    assert cells["current-conditional"] == original
    assert original["prompt"] == "Before. Perhaps a return. After."
    assert cells["current-adopted"]["prompt"] == "Before. She chose to return. After."
    assert cells["clarified-conditional"]["prompt"] == original["prompt"]
    assert cells["clarified-adopted"]["system"] == "Reconcile.\n\nPreserve established desires."
    for cell in cells.values():
        assert cell["profile"] == original["profile"]
        assert cell["allowed_tools"] == original["allowed_tools"]
    with pytest.raises(ValueError, match="uniquely"):
        run.requests({**original, "prompt": original["prompt"] * 2}, change)


@pytest.mark.parametrize("calls,tokens,elapsed", [(20, 0, 0), (0, 2_000_000, 0), (0, 0, 7200)])
def test_live_bounds_refuse_before_another_native_call(calls, tokens, elapsed):
    with pytest.raises(RuntimeError, match="ceiling"):
        module("run").check_budget(calls, tokens, elapsed)


def test_native_usage_requires_one_complete_nonnegative_envelope():
    run = module("run")
    good = '{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}}'
    assert run.native_usage({"stdout": good}) == 15
    assert run.native_usage({"stdout": good + "\n" + good}) is None
    assert run.native_usage({"stdout": good.replace("12", "-1")}) is None
    assert run.native_usage({"stdout": ""}) is None


def test_matching_deletion_dose_does_not_certify_semantic_payoff_removal():
    probe = module("probe")
    payoff = "Bram returned the key."
    second_realization = "The key was back with its owner."
    text = "Clouds drifted. " * 80 + payoff + " Rain crossed the yard. " + second_realization
    text += " Clouds drifted." * 80
    start = text.index(payoff)
    result = probe.deletion_candidates(text, start, start + len(payoff))
    assert text.count(payoff) == 1
    assert payoff not in result["damaged"]
    assert second_realization in result["damaged"]
    assert result["matches"]  # Even a matching shallow sham cannot fix the semantic key.


def test_deletion_constructor_refuses_ambiguous_payoff_evidence():
    with pytest.raises(ValueError, match="unique"):
        module("probe").deletion_candidates("A debt paid. A debt paid.", 0, 12)


def test_probe_does_not_import_another_experiments_cached_run_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "run", ModuleType("unrelated_run"))
    assert module("probe").HERE == FOLDER
