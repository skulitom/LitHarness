"""Authentication recovery preserves the original questions and stopped observations."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_recovery_is_append_only_and_detects_changed_questions(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/promise-payoff-challenge-20260922/recover.py"
    )
    monkeypatch.syspath_prepend(str(path.parents[1]))
    spec = importlib.util.spec_from_file_location("promise_recovery_test", path)
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
    original, local = tmp_path / "report", tmp_path / "local"
    original.mkdir()
    local.mkdir()
    (original / "registration.json").write_text("{}", encoding="utf-8")
    (local / "tasks.private.json").write_text('[{"frozen":true}]', encoding="utf-8")
    (local / "raw.jsonl").write_text('{"error":"expired"}', encoding="utf-8")
    monkeypatch.setattr(recovery, "ORIGINAL", original)
    monkeypatch.setattr(recovery, "ORIGINAL_LOCAL", local)
    monkeypatch.setattr(recovery, "HERE", original / "recovery")
    monkeypatch.setattr(recovery, "LOCAL", local / "recovery")
    monkeypatch.setattr(recovery, "ORIGINAL_VERIFY", dict)
    monkeypatch.setattr(recovery, "extra_sources", list)
    # Restored by monkeypatch after the wrapper deliberately rebinds these module fields.
    monkeypatch.setattr(recovery.base, "HERE", original)
    recovery.prepare()
    assert (local / "recovery/tasks.private.json").read_bytes() == (
        local / "tasks.private.json"
    ).read_bytes()
    assert (local / "raw.jsonl").read_text() == '{"error":"expired"}'
    with pytest.raises(ValueError, match="already prepared"):
        recovery.prepare()
    (local / "recovery/tasks.private.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Changed recovery tasks"):
        recovery.verify()
