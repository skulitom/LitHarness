"""The second authentication recovery keeps the questions and re-pins only the executable."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/promise-payoff-challenge-20260922/recover2.py"
    )
    monkeypatch.syspath_prepend(str(path.parents[1]))
    spec = importlib.util.spec_from_file_location("promise_recovery2_test", path)
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
    original, local = tmp_path / "report", tmp_path / "local"
    (original / "recovery").mkdir(parents=True)
    (local / "recovery").mkdir(parents=True)
    (original / "registration.json").write_text("{}", encoding="utf-8")
    (original / "recovery/registration.json").write_text("{}", encoding="utf-8")
    (local / "tasks.private.json").write_text('[{"frozen":true}]', encoding="utf-8")
    (local / "raw.jsonl").write_text('{"error":"expired"}', encoding="utf-8")
    (local / "recovery/raw.jsonl").write_text('{"error":"expired"}', encoding="utf-8")
    binary = tmp_path / "claude.exe"
    binary.write_bytes(b"new cli")

    def check_output(argv, **kwargs):
        # The executable reports its version; git reports every file as committed as it stands.
        if argv[-1] == "--version":
            return "2.1.280 (Claude Code)\n"
        return (tmp_path / argv[-1].split(":", 1)[1]).read_bytes()

    monkeypatch.setattr(recovery.base, "ROOT", tmp_path)
    monkeypatch.setattr(recovery.base, "BINARY", binary)
    monkeypatch.setattr(recovery.subprocess, "check_output", check_output)
    monkeypatch.setattr(recovery, "ORIGINAL", original)
    monkeypatch.setattr(recovery, "ORIGINAL_LOCAL", local)
    monkeypatch.setattr(recovery, "FIRST", original / "recovery")
    monkeypatch.setattr(recovery, "FIRST_LOCAL", local / "recovery")
    monkeypatch.setattr(recovery, "HERE", original / "recovery2")
    monkeypatch.setattr(recovery, "LOCAL", local / "recovery2")
    monkeypatch.setattr(recovery, "extra_sources", list)
    monkeypatch.setattr(
        recovery,
        "verify_original",
        lambda: {"binary_sha256": "old", "binary_version": "2.1.263 (Claude Code)"},
    )
    return recovery, local, binary


def test_second_recovery_preserves_both_failures_and_repins_the_cli(tmp_path, monkeypatch):
    recovery, local, _ = _load(monkeypatch, tmp_path)
    recovery.prepare()
    reg = json.loads((tmp_path / "report/recovery2/registration.json").read_text(encoding="utf-8"))
    assert reg["recovery2"]["prior_failed_attempts"] == 2
    assert reg["recovery2"]["combined_dispatch_ceiling"] == 29
    assert reg["recovery2"]["previous_binary_version"] == "2.1.263 (Claude Code)"
    assert reg["binary_version"] == "2.1.280 (Claude Code)"
    assert (local / "recovery2/tasks.private.json").read_bytes() == (
        local / "tasks.private.json"
    ).read_bytes()
    assert (local / "raw.jsonl").read_text() == '{"error":"expired"}'
    assert (local / "recovery/raw.jsonl").read_text() == '{"error":"expired"}'
    with pytest.raises(ValueError, match="already prepared"):
        recovery.prepare()


def test_second_recovery_refuses_changed_questions_or_another_cli(tmp_path, monkeypatch):
    recovery, local, binary = _load(monkeypatch, tmp_path)
    recovery.prepare()
    assert recovery.verify()["binary_version"] == "2.1.280 (Claude Code)"
    binary.write_bytes(b"yet another cli")
    with pytest.raises(ValueError, match="CLI changed"):
        recovery.verify()
    binary.write_bytes(b"new cli")
    (local / "recovery2/tasks.private.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Changed recovery tasks"):
        recovery.verify()
