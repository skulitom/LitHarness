"""Call-free controls for exact permission relocation, frozen dispatch and transport stop rules."""

from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_disclosure_permission.py"))


def source():
    prompt = (
        "Fact: the gate opens at noon.\nOther material: Ω.\n"
        "Hidden truths:\nNever reveal these yet.\n"
        "- the gate opens at noon.\n"
        "- the cellar contains a map.\n\n"
        "Scene plan: a visitor arrives.\n"
    )
    hidden_start = prompt.index("Hidden truths:")
    hidden_end = prompt.index("Scene plan:")
    text = "- the gate opens at noon.\n"
    start = prompt.index(text)
    return {
        "control": {"system": "Frozen system.\r\n", "prompt": prompt, "timeout": 300},
        "hidden_block": {
            "start": hidden_start,
            "end": hidden_end,
            "text": prompt[hidden_start:hidden_end],
        },
        "release": {"start": start, "end": start + len(text), "text": text},
        "original_request_path": "original.json",
        "original_request_sha256": "0" * 64,
    }


def test_permission_relocation_preserves_facts_and_has_an_exact_inverse():
    s = source()
    before = copy.deepcopy(s)
    requests, receipt = T["compose"](s), T["transformation_receipt"](s)
    assert s == before
    assert requests["control"] == s["control"]
    for field in ("system", "timeout"):
        assert requests["permission"][field] == s["control"][field]
    original, treatment = s["control"]["prompt"], requests["permission"]["prompt"]
    hidden, release = s["hidden_block"], s["release"]
    block = receipt["permission_after"]
    remaining_span = receipt["hidden_after"]
    remaining = treatment[remaining_span["start"] : remaining_span["end"]]
    assert treatment[: block["start"]] == original[: hidden["start"]]
    assert treatment[remaining_span["end"] :] == original[hidden["end"] :]
    assert treatment[block["start"] : block["end"]] == (
        T["PERMISSION_HEADING"] + release["text"] + "\n"
    )
    assert remaining == hidden["text"].replace(release["text"], "", 1)
    assert "Never reveal these yet.\n" in remaining
    assert "- the cellar contains a map.\n" in remaining
    witness = release["text"][2:].rstrip("\n")
    assert original.count(witness) == treatment.count(witness) == 2
    assert witness not in remaining
    offset = receipt["release_insert_offset_in_remaining_hidden"]
    reconstructed = (
        treatment[: block["start"]]
        + remaining[:offset]
        + release["text"]
        + remaining[offset:]
        + treatment[remaining_span["end"] :]
    )
    assert reconstructed == original
    assert len(treatment) - len(original) == len(T["PERMISSION_HEADING"]) + 1
    assert receipt["control_prompt_sha256"] == T["_text_sha"](reconstructed)
    assert receipt["permission_prompt_sha256"] == T["_text_sha"](treatment)


@pytest.mark.parametrize(
    "bad",
    [
        "schema",
        "shape",
        "hidden_shape",
        "boolean",
        "range",
        "negative",
        "text",
        "hidden_text",
        "hidden_midline",
        "release_midline",
        "outside",
        "overlap",
        "multiline",
        "unterminated",
        "crlf",
        "blank",
        "not_bullet",
        "third_copy",
        "no_outside_copy",
        "two_hidden_copies",
        "timeout",
        "hash",
        "empty_prompt",
    ],
)
def test_malformed_or_uncontained_permission_is_refused(bad):
    s = source()
    prompt, release, hidden = s["control"]["prompt"], s["release"], s["hidden_block"]
    if bad == "schema":
        s["automatic_disclosure"] = True
    elif bad == "shape":
        release["witness"] = "inferred"
    elif bad == "hidden_shape":
        hidden.pop("text")
    elif bad == "boolean":
        release["start"] = True
    elif bad == "range":
        release["end"] = len(prompt) + 1
    elif bad == "negative":
        hidden["start"] = -1
    elif bad == "text":
        release["text"] += "changed"
    elif bad == "hidden_text":
        hidden["text"] += "changed"
    elif bad == "hidden_midline":
        hidden.update(start=hidden["start"] + 1, text=hidden["text"][1:])
    elif bad == "release_midline":
        release.update(start=release["start"] + 1, text=release["text"][1:])
    elif bad == "outside":
        end = prompt.index("\n") + 1
        release.update(start=0, end=end, text=prompt[:end])
    elif bad == "overlap":
        release.update(start=hidden["start"], text=prompt[hidden["start"] : release["end"]])
    elif bad == "multiline":
        release.update(end=hidden["end"] - 1, text=prompt[release["start"] : hidden["end"] - 1])
    elif bad == "unterminated":
        release.update(end=release["end"] - 1, text=release["text"][:-1])
    elif bad in {"crlf", "blank", "not_bullet"}:
        replacement = {
            "crlf": release["text"].replace("\n", "\r\n"),
            "blank": "-  \n",
            "not_bullet": "* the gate opens at noon.\n",
        }[bad]
        s["control"]["prompt"] = prompt[: release["start"]] + replacement + prompt[release["end"] :]
        hidden["end"] += len(replacement) - len(release["text"])
        release.update(end=release["start"] + len(replacement), text=replacement)
        hidden["text"] = s["control"]["prompt"][hidden["start"] : hidden["end"]]
    elif bad in {"third_copy", "two_hidden_copies"}:
        addition = release["text"]
        position = len(prompt) if bad == "third_copy" else hidden["end"] - 1
        s["control"]["prompt"] = prompt[:position] + addition + prompt[position:]
        if bad == "two_hidden_copies":
            hidden["end"] += len(addition)
            hidden["text"] = s["control"]["prompt"][hidden["start"] : hidden["end"]]
    elif bad == "no_outside_copy":
        s["control"]["prompt"] = prompt.replace("Fact: the gate opens at noon.", "Fact: X.", 1)
        shift = len(prompt) - len(s["control"]["prompt"])
        for span in (hidden, release):
            span["start"] -= shift
            span["end"] -= shift
    elif bad == "timeout":
        s["control"]["timeout"] = True
    elif bad == "hash":
        s["original_request_sha256"] = "missing"
    else:
        s["control"]["prompt"] = " "
    with pytest.raises(ValueError):
        T["compose"](s)


def _manifest(out, monkeypatch):
    monkeypatch.setitem(T["validate"].__globals__, "ROOT", out.parent.parent)
    out.mkdir(parents=True, exist_ok=True)
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
        "transformation": T["transformation_receipt"](s),
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
        "receipt",
        "auth",
        "argv",
    ],
)
def test_freeze_rejects_source_request_or_dispatch_drift(tmp_path, monkeypatch, bad):
    tmp_path = tmp_path / "runs" / "trial"
    manifest = _manifest(tmp_path, monkeypatch)
    assert T["validate"](tmp_path) == manifest
    if bad == "original":
        (tmp_path / "original.json").write_text("changed")
    elif bad == "system":
        (tmp_path / T["ORDER"][0] / "system.txt").write_text("changed")
    else:
        if bad == "request":
            manifest["requests"]["permission"]["prompt"] += "changed"
        elif bad == "slot":
            manifest["slot_requests"][T["ORDER"][0]]["reasoning_effort"] = "low"
        elif bad == "source":
            manifest["source"]["release"]["start"] += 1
        elif bad == "order":
            manifest["order"].reverse()
        elif bad == "inventory":
            manifest["files"].pop(manifest["source_path"])
        elif bad == "receipt":
            manifest["transformation"]["release_before"]["end"] += 1
        elif bad == "auth":
            manifest["authentication"] = "api"
        elif bad == "argv":
            manifest["slot_requests"][T["ORDER"][0]]["argv"].append("--enable=web_search")
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
        "text": "Synthetic completion.",
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
    (folder / "full-1.txt").write_text(result["text"] + "\n", encoding="utf-8", newline="\n")
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
        "text_changed",
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
        elif bad == "text_changed":
            (folder / "full-1.txt").write_text("changed")
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
        (folder / "full-1.txt").write_text(result["text"] + "\n", encoding="utf-8", newline="\n")
        return result

    return inert


def test_slots_are_sequential_isolated_and_completed_slots_never_dispatch_twice(
    tmp_path, monkeypatch
):
    tmp_path = tmp_path / "runs" / "trial"
    manifest = _manifest(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setitem(T["CODEX"], "complete_once", _inert_transport(manifest, calls))
    monkeypatch.delenv("LITHARNESS_ENV")
    with pytest.raises(ValueError, match="prior invocation missing"):
        T["call"](tmp_path, "permission-1", manifest["requests"]["permission"], manifest)
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
    tmp_path = tmp_path / "runs" / "trial"
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
        T["draft"](tmp_path, slot="permission-1")
    assert calls == ["control-1"] and T["sha"](result_path) == original_hash


def test_polluted_work_directory_is_refused_before_transport(tmp_path, monkeypatch):
    tmp_path = tmp_path / "runs" / "trial"
    manifest = _manifest(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setitem(T["CODEX"], "complete_once", _inert_transport(manifest, calls))
    monkeypatch.delenv("LITHARNESS_ENV")
    (tmp_path / "control-1/work/unexpected.txt").write_text("foreign material")
    with pytest.raises(ValueError, match="not empty"):
        T["draft"](tmp_path)
    assert calls == []


@pytest.mark.parametrize(
    ("returncode", "message"),
    [(0, "Logged in using an API key"), (1, "Logged in using ChatGPT"), (0, "")],
)
def test_prepare_requires_confirmed_subscription_without_login_fallback(
    tmp_path, monkeypatch, returncode, message
):
    out = tmp_path / "runs" / "trial"
    _manifest(out, monkeypatch)
    target = out.parent / "fresh"
    calls = []

    def status(arguments, **kwargs):
        calls.append(arguments)
        assert arguments == ["node", "codex.js", "login", "status"]
        assert "OPENAI_API_KEY" not in kwargs["env"]
        return SimpleNamespace(returncode=returncode, stdout=message, stderr="")

    monkeypatch.delenv("LITHARNESS_ENV")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-value")
    monkeypatch.setitem(T["prepare"].__globals__, "_registration_commit", lambda: "0" * 40)
    monkeypatch.setitem(T["CODEX"], "command_prefix", lambda: ["node", "codex.js"])
    monkeypatch.setattr(T["subprocess"], "run", status)
    with pytest.raises(RuntimeError, match="ChatGPT subscription required"):
        T["prepare"](target, out / "source.json")
    assert len(calls) == 1 and not target.exists()


def test_registration_includes_every_imported_research_implementation():
    paths = {path.name for path in T["_registered_files"]()}
    assert {
        "prose_disclosure_permission.py",
        "prose_production_obligations.py",
        "prose_codex.py",
        "test_prose_disclosure_permission.py",
        "PREREG.md",
        "RUNBOOK.md",
    } == paths
