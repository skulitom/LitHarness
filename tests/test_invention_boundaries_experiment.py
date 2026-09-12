"""Protect source identity, complete crossing and provider dispatch in the research run."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

from litharness.domain.invention import make_seed
from litharness.providers.cli import ClaudeCodeProvider
from litharness.providers.codex_cli import CodexCliProvider


def module():
    path = (
        Path(__file__).resolve().parents[1]
        / "research/quality-measurement/invention-boundaries-20260912/run.py"
    )
    spec = importlib.util.spec_from_file_location("boundary_experiment", path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_chapter_inputs_preserve_unicode_source_and_only_selected_material(tmp_path):
    e = module()
    e.LOCAL = tmp_path
    source = 'A chosen action\u2014and its consequence.\nUnchanged "evidence".'
    plan = {"world": "PRIVATE-PLAN " * 30, "opening": "Planned action", "growth": "Growth"}
    e.write(tmp_path / "nico.json", {"source": source, "plan": plan})
    e.write(tmp_path / "seeds/0.json", make_seed("9876543210").to_jsonable())
    requests = {a: e.chapter_request(a) for a in ("source", "plan", "pad", "both")}
    assert len({r.system for r in requests.values()}) == 1
    assert len(requests["pad"].prompt) == len(requests["both"].prompt)
    assert e.chapter_material("source", source, plan) == {"premise": source}
    assert e.chapter_material("both", source, plan) == {"premise": source, "plan": plan}
    assert e.chapter_material("pad", source, plan)["premise"] == source
    assert "PRIVATE-PLAN" not in requests["source"].prompt + requests["pad"].prompt
    assert source not in e.chapter_material("plan", source, plan).values()


def test_every_first_design_gets_both_expanders_with_identical_requests(tmp_path):
    e = module()
    e.LOCAL = tmp_path
    assert len(e.ORDER) == len(set(e.ORDER)) == 16
    assert set(e.PLANS) == {f"plan-{i}-{x}-{s}" for i in e.MODELS for x in e.MODELS for s in (1, 2)}
    for s in (1, 2):
        e.write(tmp_path / f"seeds/{s}.json", make_seed(str(1234567890 + s)).to_jsonable())
        assert e.slot_request(f"magic-astra-{s}")[0] == e.slot_request(f"magic-opus-{s}")[0]
        for i in e.MODELS:
            mechanics = {k: f"{i}-{s} " + k for k in e.parent.MAGIC_FIELDS}
            path = tmp_path / f"calls/magic-{i}-{s}.json"
            e.write(path, {"status": "completed", "result": {"parsed": mechanics}})
            a, lineage = e.slot_request(f"plan-{i}-astra-{s}")
            b, other = e.slot_request(f"plan-{i}-opus-{s}")
            assert a == b == e.parent.plan_request(e.seed(s), mechanics)
            assert a.model is None
            assert lineage == other == {"slot": path.stem, "receipt_sha256": e.sha(path)}


def test_invalid_parent_skips_both_descendants_without_using_other_design(tmp_path):
    e = module()
    e.LOCAL = tmp_path
    e.write(tmp_path / "seeds/1.json", make_seed("123456789").to_jsonable())
    for inventor, fields in (
        ("astra", {}),
        ("opus", dict.fromkeys(e.parent.MAGIC_FIELDS, "valid")),
    ):
        e.write(
            tmp_path / f"calls/magic-{inventor}-1.json",
            {"status": "completed", "result": {"parsed": fields}},
        )
    for expander in e.MODELS:
        assert e.slot_request(f"plan-astra-{expander}-1")[0] is None
        assert e.slot_request(f"plan-opus-{expander}-1")[0] is not None
    with pytest.raises(ValueError):
        e.slot_request("plan-opus-opus-3")


def test_provider_route_uses_expander_and_safe_tool_free_medium_request(tmp_path, monkeypatch):
    e = module()
    e.LOCAL = tmp_path
    monkeypatch.setattr(e, "claude_auth", lambda environment: None)
    e.write(tmp_path / "seeds/1.json", make_seed("123456789").to_jsonable())
    request = e.slot_request("magic-astra-1")[0]
    for inventor in e.MODELS:
        native = e.provider_for(f"plan-{inventor}-astra-1", {}, tmp_path / "not-written.json")
        claude = e.provider_for(f"plan-{inventor}-opus-1", {}, tmp_path / "not-written.json")
        assert isinstance(native, CodexCliProvider)
        assert isinstance(claude, ClaudeCodeProvider)
        argv = claude._argv(request)
        for key, value in (("--tools", ""), ("--model", "claude-opus-5"), ("--effort", "medium")):
            assert argv[argv.index(key) + 1] == value
        assert "--safe-mode" in argv and "--no-session-persistence" in argv
        assert argv[argv.index("--system-prompt") + 1] == request.effective_system


def test_reported_opus_requires_attribution_and_rejects_downgrade():
    e = module()
    assert e.reported_opus_matches(
        {"model": "claude-opus-5", "raw": {"modelUsage": {"claude-opus-5": {}}}}
    )
    assert not e.reported_opus_matches({"model": "claude-opus-5", "raw": {}})
    assert not e.reported_opus_matches(
        {"model": "claude-haiku-4-5", "raw": {"modelUsage": {"claude-haiku-4-5": {}}}}
    )


def test_nonzero_claude_exit_stops_even_with_parseable_success(tmp_path, monkeypatch):
    e = module()
    e.LOCAL = tmp_path
    monkeypatch.setattr(e, "claude_auth", lambda environment: None)
    monkeypatch.setattr(
        e.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, '{"subtype":"success"}', "error"),
    )
    e.write(tmp_path / "seeds/1.json", make_seed("123456789").to_jsonable())
    row = {}
    provider = e.provider_for("magic-opus-1", row, tmp_path / "receipt.json")
    with pytest.raises(RuntimeError, match="Claude process exited 1"):
        provider.complete(e.slot_request("magic-opus-1")[0])
    assert row["transport"]["returncode"] == 1
    assert row["transport"]["stdout"] == '{"subtype":"success"}'
