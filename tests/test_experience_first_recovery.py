"""A shutdown continuation must never replace a completed response."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RUNNER = (Path(__file__).resolve().parents[1]
          / "research/quality-measurement/experience-first-recovery-20260915/run.py")


@pytest.fixture
def recovery():
    spec = importlib.util.spec_from_file_location("experience_recovery_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checkpoint(recovery):
    cut = recovery.BASE.ORDER.index(recovery.INTERRUPTED)
    return {name: {"status": "completed"} for name in recovery.BASE.ORDER[:cut]} | {
        recovery.INTERRUPTED: {"status": "started"},
    }


def test_only_interrupted_and_unreached_slots_are_dispatched(recovery):
    original = checkpoint(recovery)
    remaining = recovery.remaining_slots(original)
    assert len(remaining) == 28
    assert remaining[0] == "outline-C-3"
    assert not set(remaining) & {n for n, r in original.items() if r["status"] == "completed"}
    assert len([n for n in remaining if n.startswith("draft-")]) == 18


def test_existing_interrupted_result_cannot_be_replaced(recovery):
    original = checkpoint(recovery)
    original[recovery.INTERRUPTED]["result"] = {"parsed": {"scenes": []}}
    with pytest.raises(RuntimeError, match="has a result"):
        recovery.remaining_slots(original)


def test_missing_or_failed_earlier_response_cannot_be_rescued(recovery):
    original = checkpoint(recovery)
    original["outline-A-1"]["status"] = "failed"
    with pytest.raises(RuntimeError, match="earlier response"):
        recovery.remaining_slots(original)
    del original["outline-A-1"]
    with pytest.raises(RuntimeError, match="inventory"):
        recovery.remaining_slots(original)


def test_later_response_prevents_silent_restart_from_an_old_checkpoint(recovery):
    original = checkpoint(recovery)
    original["draft-A-1"] = {"status": "completed"}
    with pytest.raises(RuntimeError, match="inventory"):
        recovery.remaining_slots(original)
