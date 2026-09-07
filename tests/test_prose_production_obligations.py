"""Call-free controls for exact subtraction, frozen dispatch and transport stop rules."""

from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_production_obligations.py"))


def source():
    prompt = (
        "Fact: known.\nDebt one: Explain price.\nWindow: 2-3.\n"
        "Debt two: Explain price.\nWindow: 2-3.\nEnd."
    )
    text = ": Explain price."
    start = prompt.index(text)
    return {
        "control": {"system": "Frozen system.\r\n", "prompt": prompt, "timeout": 300},
        "cuts": [
            {"start": start, "end": start + len(text), "text": text, "witness": "Explain price."}
        ],
        "original_request_path": "original.json",
        "original_request_sha256": "0" * 64,
    }


def test_subtraction_preserves_every_byte_outside_the_reviewed_span():
    s = source()
    before = copy.deepcopy(s)
    requests = T["compose"](s)
    assert s == before
    assert requests["control"] == s["control"]
    assert requests["single"] == {
        **s["control"],
        "prompt": s["control"]["prompt"].replace(": Explain price.", "", 1),
    }
    assert requests["single"]["prompt"].count("Explain price.") == 1
    assert requests["single"]["prompt"].count("Window: 2-3.") == 2
    assert "Debt one\nWindow: 2-3." in requests["single"]["prompt"]


@pytest.mark.parametrize(
    "bad",
    [
        "empty",
        "overlap",
        "boolean",
        "range",
        "text",
        "blank_witness",
        "outside_witness",
        "unique_witness",
        "remove_all_copies",
        "whole_prompt",
        "schema",
        "timeout",
        "hash",
    ],
)
def test_invalid_or_unpreserved_cuts_are_refused(bad):
    s = source()
    prompt, cut = s["control"]["prompt"], s["cuts"][0]
    if bad == "empty":
        s["cuts"] = []
    elif bad == "overlap":
        s["cuts"].append(dict(cut))
    elif bad == "boolean":
        cut["start"] = True
    elif bad == "range":
        cut["end"] = len(prompt) + 1
    elif bad == "text":
        cut["text"] += "changed"
    elif bad == "blank_witness":
        cut["witness"] = " "
    elif bad == "outside_witness":
        cut["witness"] = "Window: 2-3."
    elif bad == "unique_witness":
        cut.update(start=0, text=prompt[: cut["end"]], witness="Fact: known.")
    elif bad == "remove_all_copies":
        start = prompt.rindex(cut["text"])
        s["cuts"].append({**cut, "start": start, "end": start + len(cut["text"])})
    elif bad == "whole_prompt":
        cut.update(start=0, end=len(prompt), text=prompt)
    elif bad == "schema":
        cut["replacement"] = "Another instruction."
    elif bad == "timeout":
        s["control"]["timeout"] = True
    else:
        s["original_request_sha256"] = "missing"
    with pytest.raises(ValueError):
        T["compose"](s)


def _manifest(out, monkeypatch):
    s = source()
    original = out / "original.json"
    T["write_new"](original, s["control"])
    s["original_request_path"] = str(original)
    s["original_request_sha256"] = T["sha"](original)
    source_path = out / "source.json"
    T["write_new"](source_path, s)
    requests = T["compose"](s)
    prefix = ["node", "codex.js"]
    paths = [original, source_path]
    for name in T["ORDER"]:
        folder = out / name
        (folder / "work").mkdir(parents=True)
        system = folder / "system.txt"
        system.write_bytes(requests[name.rsplit("-", 1)[0]]["system"].encode())
        paths.append(system)
    monkeypatch.setitem(T["validate"].__globals__, "_files", lambda *_: paths)
    manifest = {
        "source": s,
        "source_path": str(source_path),
        "requests": requests,
        "prefix": prefix,
        "slot_requests": {
            name: T["_record"](out, name, requests[name.rsplit("-", 1)[0]], prefix)
            for name in T["ORDER"]
        },
        "files": {str(path): T["sha"](path) for path in paths},
        "order": list(T["ORDER"]),
        "token_stop": T["TOKEN_STOP"],
        "token_counter": "input_tokens + output_tokens",
        "authentication": "chatgpt",
        "reasoning_effort": "high",
        "transport_slot_per_logical_call": "full-1",
        "source_timeout": 300,
        "transport_timeout_seconds": 900,
    }
    T["write_new"](out / "manifest.json", manifest)
    return manifest


@pytest.mark.parametrize(
    "bad",
    [
        "original",
        "system",
        "request",
        "slot",
        "source",
        "order",
        "inventory",
        "counter",
    ],
)
def test_freeze_rejects_source_request_or_dispatch_drift(tmp_path, monkeypatch, bad):
    manifest = _manifest(tmp_path, monkeypatch)
    assert T["validate"](tmp_path) == manifest
    if bad == "original":
        (tmp_path / "original.json").write_text("changed")
    elif bad == "system":
        (tmp_path / T["ORDER"][0] / "system.txt").write_text("changed")
    else:
        if bad == "request":
            manifest["requests"]["single"]["prompt"] += "changed"
        elif bad == "slot":
            manifest["slot_requests"][T["ORDER"][0]]["reasoning_effort"] = "low"
        elif bad == "source":
            manifest["source"]["cuts"].clear()
        elif bad == "order":
            manifest["order"].reverse()
        elif bad == "inventory":
            manifest["files"].pop(manifest["source_path"])
        else:
            manifest["token_counter"] = "input + output + reasoning"
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        T["validate"](tmp_path)


def _completed(out, name, *, request=None, usage=None, stderr="", status="completed"):
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    T["write_new"](folder / "full-1.request.json", request or {})
    T["write_new"](folder / "full-1.raw.json", {"stdout": "", "stderr": stderr, "exit_code": 0})
    result = {
        "status": status,
        "usage": usage
        if usage is not None
        else {
            "input_tokens": 7,
            "cached_input_tokens": 7,
            "output_tokens": 3,
            "reasoning_output_tokens": 2,
        },
    }
    T["write_new"](folder / "full-1.result.json", result)
    T["write_new"](folder / "transport-audit.json", T["_audit"](folder))
    return result


def test_counter_uses_input_plus_output_without_cached_or_reasoning_double_count(tmp_path):
    for name in T["ORDER"][:2]:
        _completed(tmp_path, name)
    assert T["quota"](tmp_path) == 20


def test_counter_stops_at_the_registered_bound(tmp_path):
    _completed(
        tmp_path,
        T["ORDER"][0],
        usage={
            "input_tokens": T["TOKEN_STOP"] - 2,
            "output_tokens": 2,
            "reasoning_output_tokens": 1,
        },
    )
    with pytest.raises(RuntimeError, match="token stop"):
        T["quota"](tmp_path)


@pytest.mark.parametrize(
    "bad",
    [
        "unknown",
        "order",
        "orphan_result",
        "missing",
        "failed",
        "orphan_raw",
        "audit_missing",
        "artifact_changed",
        "boolean_usage",
        "reasoning_exceeds_output",
    ],
)
def test_incomplete_failed_or_changed_calls_cannot_be_retried(tmp_path, bad):
    if bad == "orphan_raw":
        folder = tmp_path / T["ORDER"][0]
        folder.mkdir()
        T["write_new"](folder / "full-1.raw.json", {})
    else:
        name = "unknown" if bad == "unknown" else T["ORDER"][1 if bad == "order" else 0]
        usage = None
        if bad == "boolean_usage":
            usage = {"input_tokens": True, "output_tokens": 3}
        elif bad == "reasoning_exceeds_output":
            usage = {"input_tokens": 7, "output_tokens": 3, "reasoning_output_tokens": 4}
        _completed(tmp_path, name, usage=usage, status="failed" if bad == "failed" else "completed")
        folder = tmp_path / name
        removed = {
            "orphan_result": "full-1.request.json",
            "missing": "full-1.result.json",
            "audit_missing": "transport-audit.json",
        }.get(bad)
        if removed:
            (folder / removed).unlink()
        if bad == "artifact_changed":
            (folder / "full-1.raw.json").write_text(json.dumps({"stderr": "changed"}))
    with pytest.raises((ValueError, RuntimeError)):
        T["quota"](tmp_path)


@pytest.mark.parametrize("environment", ["test", " TEST ", "Test"])
def test_test_environment_blocks_prepare_call_and_draft_before_any_subprocess(
    tmp_path,
    monkeypatch,
    environment,
):
    monkeypatch.setenv("LITHARNESS_ENV", environment)
    for function, args in (
        (T["prepare"], (tmp_path / "new", tmp_path / "missing-source.json")),
        (T["call"], (tmp_path, T["ORDER"][0], {}, {})),
        (T["draft"], (tmp_path,)),
    ):
        with pytest.raises(RuntimeError, match="disabled in tests"):
            function(*args)
    assert not list(tmp_path.iterdir())


def _inert_transport(manifest, calls, *, retry=False):
    def inert(folder, name, request, *, effort):
        calls.append(folder.name)
        assert name == "full-1" and effort == "high"
        assert request["requests"]["full"] == manifest["requests"][folder.name.rsplit("-", 1)[0]]
        T["write_new"](folder / "full-1.request.json", manifest["slot_requests"][folder.name])
        T["write_new"](
            folder / "full-1.raw.json",
            {
                "stdout": "",
                "stderr": "retrying sampling request (1/5)" if retry else "",
                "exit_code": 0,
            },
        )
        result = {
            "status": "completed",
            "text": "Retained synthetic output.",
            "usage": {"input_tokens": 2, "output_tokens": 1},
        }
        T["write_new"](folder / "full-1.result.json", result)
        return result

    return inert


def test_slots_are_sequential_isolated_and_completed_slots_never_dispatch_twice(
    tmp_path, monkeypatch
):
    manifest = _manifest(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setitem(T["CODEX"], "complete_once", _inert_transport(manifest, calls))
    monkeypatch.delenv("LITHARNESS_ENV")
    with pytest.raises(ValueError, match="prior invocation missing"):
        T["call"](tmp_path, "single-1", manifest["requests"]["single"], manifest)
    assert calls == []
    T["draft"](tmp_path, slot="control-1")
    assert calls == ["control-1"]
    T["draft"](tmp_path)
    T["draft"](tmp_path)
    assert calls == list(T["ORDER"])
    assert T["quota"](tmp_path) == 12


def test_internal_sampling_retry_retains_completion_and_stops_before_another_call(
    tmp_path, monkeypatch
):
    manifest = _manifest(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setitem(T["CODEX"], "complete_once", _inert_transport(manifest, calls, retry=True))
    monkeypatch.delenv("LITHARNESS_ENV")
    with pytest.raises(RuntimeError, match="internal sampling retry retained"):
        T["draft"](tmp_path)
    assert calls == ["control-1"]
    folder = tmp_path / "control-1"
    result_path = folder / "full-1.result.json"
    original_hash = T["sha"](result_path)
    assert T["read"](result_path)["status"] == "completed"
    assert T["read"](folder / "transport-audit.json")["internal_sampling_retry_reported"] is True
    with pytest.raises(RuntimeError, match="internal sampling retry retained"):
        T["draft"](tmp_path, slot="single-1")
    assert calls == ["control-1"] and T["sha"](result_path) == original_hash


def test_polluted_work_directory_is_refused_before_transport(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setitem(T["CODEX"], "complete_once", _inert_transport(manifest, calls))
    monkeypatch.delenv("LITHARNESS_ENV")
    (tmp_path / "control-1/work/unexpected.txt").write_text("foreign material")
    with pytest.raises(ValueError, match="not empty"):
        T["draft"](tmp_path)
    assert calls == []
