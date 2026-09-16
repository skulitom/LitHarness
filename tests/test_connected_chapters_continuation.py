"""A resource amendment cannot silently resume failures or replace recorded work."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/connected-chapters-20260916/continue.py"
)


@pytest.fixture
def experiment():
    spec = importlib.util.spec_from_file_location("connected_chapters_continuation_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.configure()
    return module


def stopped(experiment):
    calls = [
        {"status": "completed", "tokens": 0, "book": "A1"} for _ in range(experiment.PREFIX_CALLS)
    ]
    calls[-1]["tokens"] = experiment.PREFIX_TOKENS
    state = {
        "status": "partial",
        "stop": "global token ceiling",
        "calls": calls,
        "books": {
            book: {
                "accepted": 2,
                "pending": 0,
                "terminal": 0,
                "phase": "grow2",
                "status": "stopped" if book == "A2" else "running",
            }
            for book in ("A1", "A2", "B1", "B2")
        },
    }
    step = {
        "key": "grow2-A2-1",
        "returncode": 2,
        "before": {"head": "same"},
        "after": {"head": "same"},
    }
    return state, step


@pytest.mark.parametrize("fault", ["usage", "provider", "prior_resume", "head", "jobs", "volume"])
def test_only_the_exact_unchanged_budget_stop_can_resume(experiment, fault):
    state, step = stopped(experiment)
    experiment.validate_stop(state, step)
    if fault == "usage":
        state["calls"][-1]["tokens"] += 1
    elif fault == "provider":
        state["calls"][-1]["status"] = "failed"
    elif fault == "prior_resume":
        state["continuation"] = {"started": "earlier"}
    elif fault == "head":
        step["after"]["head"] = "changed"
    elif fault == "jobs":
        state["books"]["B1"]["terminal"] = 1
    else:
        state["books"]["A1"]["accepted"] = 3
    with pytest.raises(RuntimeError):
        experiment.validate_stop(state, step)


def test_prefix_uses_original_limit_and_continuation_retains_clock_and_call_bounds(experiment):
    at = datetime.now(UTC).isoformat()
    state, _ = stopped(experiment)
    state.pop("stop")
    state["started_at"] = at
    for i, call in enumerate(state["calls"]):
        call["book"] = ("A1", "B1", "A2", "B2")[i % 4]
    prefix = deepcopy(state)
    prefix["calls"].pop(0)
    assert experiment.admission(prefix, "B1", at) == "global token ceiling"
    assert experiment.admission(state, "B1", at) is None
    later = (datetime.fromisoformat(at) + timedelta(seconds=10800)).isoformat()
    assert experiment.admission(state, "B1", later) == "elapsed-time ceiling"
    state["calls"][-1]["tokens"] = experiment.TOTAL_TOKENS
    assert experiment.admission(state, "B1", at) == "global token ceiling"


def test_remaining_order_never_reinvents_or_redrafts_existing_chapters(experiment):
    work = experiment.schedule()
    assert work[0] == ("grow2", "A2")
    assert len(work) == 13
    for phase in ("accept-grow2", "chapter3", "drain3"):
        assert [book for p, book in work if p == phase] == list(experiment.base.order(phase))
    assert not any(p in ("concept", "new", "seed", "chapter1", "chapter2") for p, _ in work)


def test_resumed_step_appends_an_iteration_instead_of_overwriting(
    experiment, tmp_path, monkeypatch
):
    base = experiment.base
    monkeypatch.setattr(experiment, "LOCAL", tmp_path)
    monkeypatch.setattr(base, "LOCAL", tmp_path)
    state, _ = stopped(experiment)
    state.pop("stop")
    state["books"]["A2"]["status"] = "running"
    base.write(tmp_path / "progress.json", state)
    old = tmp_path / "steps/grow2-A2-1.json"
    base.write(old, {"preserved": True})
    digest = base.sha(old)
    seen = []

    def step(argv, **kwargs):
        seen.append(argv[-1])
        base.write(
            tmp_path / "steps" / f"grow2-A2-{argv[-1]}.json",
            {
                "returncode": 0,
                "stdout": "",
                "after": {
                    "accepted": 2,
                    "pending": 0,
                    "terminal": 0,
                },
            },
        )

    monkeypatch.setattr(experiment.subprocess, "run", step)
    experiment.execute("A2", "grow2")
    assert seen == ["2"]
    assert base.sha(old) == digest
