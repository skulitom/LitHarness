"""Shutdown recovery must preserve evidence and never retry ambiguous call slots."""

import importlib.util
import json
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-preserve-20260911/resume.py"
)
SPEC = importlib.util.spec_from_file_location("preserve_recovery", PATH)
assert SPEC is not None and SPEC.loader is not None
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


def test_recovery_excludes_completed_and_lost_slots_and_rejects_inventory_drift():
    original = recovery.original.ORDER
    assert recovery.remaining_slots(set(original[:4])) == original[4:]
    assert not set(recovery.LOST) & set(recovery.REMAINING)
    with pytest.raises(RuntimeError):
        recovery.remaining_slots(set(original[:3]))
    with pytest.raises(RuntimeError):
        recovery.remaining_slots(set(original[:5]))


def test_failed_atomic_replacement_leaves_previous_valid_progress(tmp_path, monkeypatch):
    path = tmp_path / "progress.json"
    recovery.durable_write(path, {"attempts": 1})

    def fail_replace(source, destination):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError):
        recovery.durable_write(path, {"attempts": 2})
    assert json.loads(path.read_text()) == {"attempts": 1}
    assert json.loads(path.with_name("progress.json.tmp").read_text()) == {"attempts": 2}
