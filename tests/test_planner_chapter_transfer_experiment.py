"""Contain the fixed plan pair and its reused execution loop without model calls."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from litharness.domain.invention import make_seed


def module():
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/planner-chapter-transfer-20260913/run.py"
    )
    spec = importlib.util.spec_from_file_location("chapter_transfer_experiment", path)
    assert spec is not None and spec.loader is not None
    e = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(e)
    return e


def prepare_local(e, root):
    e.LOCAL = root
    e.write(root / "seed.json", make_seed("9876543210").to_jsonable())
    for arm in ("astra", "opus"):
        plan = {"world": f"{arm} world—unchanged", "opening": arm + " pursuit", "growth": "Later"}
        e.write(
            root / "parents" / f"{arm}.json",
            {
                "plan": plan,
                "source_path": arm + ".json",
                "receipt_sha256": arm,
                "mechanics_receipt_sha256": "same-first-design",
            },
        )


def test_fixed_pair_only_changes_plan_and_preserves_exact_unicode(tmp_path):
    e = module()
    prepare_local(e, tmp_path)
    a, la = e.slot_request("draft-astra-1")
    b, lb = e.slot_request("draft-opus-1")
    assert [k for k in e.normalized(a) if e.normalized(a)[k] != e.normalized(b)[k]] == ["prompt"]
    for arm, request in (("astra", a), ("opus", b)):
        source = e.read(tmp_path / "parents" / f"{arm}.json")
        assert json.loads(request.prompt.split("\n", 1)[1]) == source["plan"]
        assert "receipt_sha256" not in request.prompt
    assert la["mechanics_receipt_sha256"] == lb["mechanics_receipt_sha256"]
    assert la["snapshot_sha256"] != lb["snapshot_sha256"]
    with pytest.raises(ValueError):
        e.slot_request("draft-opus-2")


def test_parent_verification_rejects_source_changed_after_evidence(tmp_path):
    e = module()
    e.PREVIOUS = tmp_path / "previous"
    e.PRIOR_RECORDS = tmp_path / "records"
    m = e.PREVIOUS / "calls/magic-astra-1.json"
    p = e.PREVIOUS / "calls/plan-astra-astra-1.json"
    e.write(m, {"original": True})
    e.write(p, {"original": True})
    e.write(
        e.PRIOR_RECORDS / "evidence.json",
        {
            "all_controls_pass": True,
            "outputs": [
                {"name": x.stem, "receipt_sha256": e.sha(x), "valid": True} for x in (m, p)
            ],
        },
    )
    e.write(p, {"original": False})
    with pytest.raises(RuntimeError, match="differs from previous evidence"):
        e.verified_parent("astra")


def test_reused_loop_stops_after_failed_first_call_without_retry_or_second(tmp_path, monkeypatch):
    e = module()
    prepare_local(e, tmp_path)
    e.HERE = tmp_path / "registration"
    e.write(
        tmp_path / "manifest.json",
        {
            "binary": "unused",
            "files": {},
            "attempt_stop": 2,
            "token_stop": 30000,
        },
    )
    registration = {"manifest_sha256": e.sha(tmp_path / "manifest.json")}
    e.write(e.HERE / "registration.json", registration)
    monkeypatch.setattr(e, "lock", lambda: None)
    monkeypatch.setattr(e, "ROOT", tmp_path)
    monkeypatch.setattr(e.driver, "ROOT", tmp_path)
    monkeypatch.setattr(
        e.subprocess, "check_output", lambda *a, **kw: json.dumps(registration).encode()
    )
    # Only the fake object below can be constructed; no billing provider is reachable.
    monkeypatch.delenv("LITHARNESS_ENV", raising=False)
    calls = []

    class FailingProvider:
        def __init__(self):
            self.last_attempt = {"failure": "retained"}

        def complete(self, request):
            calls.append(request)
            raise RuntimeError("first return failed")

    monkeypatch.setattr(e.driver, "provider_for", lambda binary: FailingProvider())
    with pytest.raises(RuntimeError, match="first return failed"):
        e.run()
    assert len(calls) == 1
    assert e.read(tmp_path / "progress.json")["status"] == "stopped"
    assert e.read(tmp_path / "calls/draft-astra-1.json")["raw"] == {"failure": "retained"}
    assert not (tmp_path / "calls/draft-opus-1.json").exists()
    with pytest.raises(RuntimeError, match="no implicit resume"):
        e.run()
