"""Call-free controls for a final-wrapper-only clause edit and shared frozen dispatch."""

from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_recall_clarification.py"))
HELPER = T["SHARED"]


def source():
    old = "paid with the hours until sleep"
    new = "costs the memories formed from this bell until sleep"
    prompt = (
        f"An earlier quotation says: {old}.\n\n"
        "Now write Earlier scene. This is retained prose, not the final task.\n\n"
        f"Now write Scene 2. This scene: The purchase is {old}. Then leave the hall."
    )
    plan_start = prompt.rindex("Now write ")
    start = prompt.rindex(old)
    return {
        "control": {"system": f"Literal world cost: {old}.\r\n", "prompt": prompt, "timeout": 300},
        "scene_plan": {"start": plan_start, "end": len(prompt), "text": prompt[plan_start:]},
        "replacement": {"start": start, "end": start + len(old), "text": old, "replacement": new},
        "original_request_path": "original.json",
        "original_request_sha256": "0" * 64,
    }


def test_only_reviewed_clause_changes_with_exact_inverse_and_prior_prose_preserved():
    s = source()
    untouched = copy.deepcopy(s)
    requests, receipt = T["compose"](s), T["transformation_receipt"](s)
    assert s == untouched and requests["control"] == s["control"]
    assert requests["clarified"]["system"] == s["control"]["system"]
    assert requests["clarified"]["timeout"] == s["control"]["timeout"]
    before, after = requests["control"]["prompt"], requests["clarified"]["prompt"]
    edit, wrapper = s["replacement"], s["scene_plan"]
    end = edit["start"] + len(edit["replacement"])
    assert after[: edit["start"]] == before[: edit["start"]]
    assert after[end:] == before[edit["end"] :]
    assert after[: wrapper["start"]] == before[: wrapper["start"]]
    assert after[edit["start"] : end] == edit["replacement"]
    assert after[: edit["start"]] + edit["text"] + after[end:] == before
    assert before.count(edit["text"]) == 2 and after.count(edit["text"]) == 1
    assert receipt["inverse_recovers_original"] is True
    assert receipt["replacement_after"] == {"start": edit["start"], "end": end}
    assert receipt["control_prompt_sha256"] == T["_text_sha"](before)
    assert receipt["clarified_prompt_sha256"] == T["_text_sha"](after)
    assert receipt["before_scene_plan_sha256"] == T["_text_sha"](after[: wrapper["start"]])


@pytest.mark.parametrize(
    "bad",
    [
        "schema",
        "boolean",
        "range",
        "text",
        "outside",
        "overlap",
        "whole_wrapper",
        "wrapper_start",
        "wrapper_end",
        "earlier_wrapper",
        "empty",
        "same",
        "multiline",
        "old_multiline",
        "timeout",
        "hash",
    ],
)
def test_bad_or_nonlocal_replacements_are_refused(bad):
    s = source()
    edit, wrapper, prompt = s["replacement"], s["scene_plan"], s["control"]["prompt"]
    if bad == "schema":
        edit["another_edit"] = "not allowed"
    elif bad == "boolean":
        edit["start"] = True
    elif bad == "range":
        edit["end"] = len(prompt) + 1
    elif bad == "text":
        edit["text"] += "changed"
    elif bad == "outside":
        edit["start"] = prompt.index(edit["text"])
        edit["end"] = edit["start"] + len(edit["text"])
    elif bad in {"overlap", "whole_wrapper"}:
        edit["start"] = wrapper["start"]
        if bad == "whole_wrapper":
            edit["end"] = wrapper["end"]
        edit["text"] = prompt[edit["start"] : edit["end"]]
    elif bad == "wrapper_start":
        wrapper["start"] += 1
        wrapper["text"] = prompt[wrapper["start"] :]
    elif bad == "wrapper_end":
        wrapper["end"] -= 1
        wrapper["text"] = prompt[wrapper["start"] : wrapper["end"]]
    elif bad == "earlier_wrapper":
        wrapper["start"] = prompt.index("Now write ")
        wrapper["text"] = prompt[wrapper["start"] :]
    elif bad == "empty":
        edit["replacement"] = " "
    elif bad == "same":
        edit["replacement"] = edit["text"]
    elif bad == "multiline":
        edit["replacement"] += "\nAnother instruction."
    elif bad == "old_multiline":
        text = wrapper["text"].replace(". This scene:", ".\nThis scene:", 1)
        s["control"]["prompt"] = prompt[: wrapper["start"]] + text
        wrapper.update(text=text, end=len(s["control"]["prompt"]))
        edit.update(start=wrapper["start"] + len("Now write "), end=wrapper["end"] - 1)
        edit["text"] = s["control"]["prompt"][edit["start"] : edit["end"]]
    elif bad == "timeout":
        s["control"]["timeout"] = True
    else:
        s["original_request_sha256"] = "changed"
    with pytest.raises(ValueError):
        T["compose"](s)


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    runner = HELPER["FrozenSceneExperiment"](
        root=tmp_path,
        order=T["ORDER"],
        registered_files=(),
        compose=T["compose"],
        receipt=T["transformation_receipt"],
        token_stop=T["TOKEN_STOP"],
    )
    out = tmp_path / "runs" / "trial"
    out.mkdir(parents=True)
    s = source()
    original = out / "original.json"
    T["write_new"](original, s["control"])
    s["original_request_path"], s["original_request_sha256"] = str(original), T["sha"](original)
    source_path = out / "source.json"
    T["write_new"](source_path, s)
    requests, prefix, paths = T["compose"](s), ["node", "codex.js"], [original, source_path]
    for name in runner.order:
        folder = out / name
        (folder / "work").mkdir(parents=True)
        system = folder / "system.txt"
        system.write_bytes(requests[name.rsplit("-", 1)[0]]["system"].encode("utf-8"))
        paths.append(system)
    monkeypatch.setattr(runner, "_files", lambda *_: paths)
    manifest = {
        **runner._settings(s),
        "source": s,
        "source_path": str(source_path),
        "requests": requests,
        "transformation": T["transformation_receipt"](s),
        "prefix": prefix,
        "files": {str(path): T["sha"](path) for path in paths},
        "slot_requests": {
            name: runner._record(out, name, requests[name.rsplit("-", 1)[0]], prefix)
            for name in runner.order
        },
    }
    T["write_new"](out / "manifest.json", manifest)
    return runner, out, manifest


@pytest.mark.parametrize(
    "bad",
    ["original", "system", "requests", "receipt", "source", "slot", "order", "auth", "inventory"],
)
def test_frozen_identity_and_configuration_drift_is_rejected(frozen, bad):
    runner, out, manifest = frozen
    assert runner.validate(out) == manifest
    if bad == "original":
        (out / "original.json").write_text("changed")
    elif bad == "system":
        (out / "control-1/system.txt").write_text("changed")
    else:
        if bad == "requests":
            manifest["requests"]["clarified"]["prompt"] += "changed"
        elif bad == "receipt":
            manifest["transformation"]["replacement_after"]["end"] += 1
        elif bad == "source":
            manifest["source"]["replacement"]["replacement"] += "changed"
        elif bad == "slot":
            manifest["slot_requests"]["control-1"]["argv"].append("--enable=web_search")
        elif bad == "order":
            manifest["order"].reverse()
        elif bad == "auth":
            manifest["authentication"] = "api"
        else:
            manifest["files"].pop(manifest["source_path"])
        (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        runner.validate(out)


def _completion(folder, request, *, stderr="", usage=None, status="completed"):
    folder.mkdir(parents=True, exist_ok=True)
    T["write_new"](folder / "full-1.request.json", request)
    T["write_new"](folder / "full-1.raw.json", {"stdout": "", "stderr": stderr, "exit_code": 0})
    result = {
        "status": status,
        "text": "Synthetic output.",
        "usage": usage
        if usage is not None
        else {
            "input_tokens": 7,
            "output_tokens": 3,
            "cached_input_tokens": 5,
            "reasoning_output_tokens": 2,
        },
    }
    T["write_new"](folder / "full-1.result.json", result)
    (folder / "full-1.txt").write_text(result["text"] + "\n", encoding="utf-8", newline="\n")
    return result


def _transport(manifest, calls, *, retry=False):
    def inert(folder, name, request, *, effort):
        calls.append(folder.name)
        assert name == "full-1" and effort == "high"
        assert request["requests"]["full"] == manifest["requests"][folder.name.rsplit("-", 1)[0]]
        return _completion(
            folder,
            manifest["slot_requests"][folder.name],
            stderr="retrying sampling request (1/5)" if retry else "",
        )

    return inert


def test_fixed_order_isolated_dispatch_and_completed_slots_are_never_redrawn(frozen, monkeypatch):
    runner, out, manifest = frozen
    calls = []
    monkeypatch.delenv("LITHARNESS_ENV")
    monkeypatch.setitem(T["CODEX"], "complete_once", _transport(manifest, calls))
    with pytest.raises(ValueError, match="prior invocation missing"):
        runner.call(out, "clarified-1")
    assert not calls
    runner.draft(out, "control-1")
    runner.draft(out)
    runner.draft(out)
    assert calls == list(T["ORDER"])
    assert runner.quota(out) == 40


def test_internal_retry_retains_output_and_stops_before_any_other_call(frozen, monkeypatch):
    runner, out, manifest = frozen
    calls = []
    monkeypatch.delenv("LITHARNESS_ENV")
    monkeypatch.setitem(T["CODEX"], "complete_once", _transport(manifest, calls, retry=True))
    with pytest.raises(RuntimeError, match="internal sampling retry"):
        runner.draft(out)
    before = T["sha"](out / "control-1/full-1.result.json")
    with pytest.raises(RuntimeError, match="internal sampling retry"):
        runner.draft(out, "clarified-1")
    assert calls == ["control-1"]
    assert T["sha"](out / "control-1/full-1.result.json") == before


@pytest.mark.parametrize(
    "bad",
    [
        "incomplete",
        "failure",
        "raw_changed",
        "text_changed",
        "audit_missing",
        "quota",
        "invalid_usage",
        "orphan",
    ],
)
def test_failure_or_artifact_drift_stops_without_transport(frozen, monkeypatch, bad):
    runner, out, manifest = frozen
    folder = out / "control-1"
    usage = {"input_tokens": 99999, "output_tokens": 1} if bad == "quota" else None
    if bad == "invalid_usage":
        usage = {"input_tokens": True, "output_tokens": 1}
    _completion(
        folder,
        manifest["slot_requests"]["control-1"],
        usage=usage,
        status="failed" if bad == "failure" else "completed",
    )
    T["write_new"](folder / "transport-audit.json", HELPER["audit"](folder))
    if bad == "incomplete":
        (folder / "full-1.result.json").unlink()
    elif bad == "audit_missing":
        (folder / "transport-audit.json").unlink()
    elif bad in {"raw_changed", "text_changed"}:
        (folder / ("full-1.raw.json" if bad == "raw_changed" else "full-1.txt")).write_text(
            '{"stderr":"changed"}'
        )
    elif bad == "orphan":
        (out / "foreign").mkdir()
        T["write_new"](out / "foreign/full-1.raw.json", {})
    calls = []
    monkeypatch.delenv("LITHARNESS_ENV")
    monkeypatch.setitem(T["CODEX"], "complete_once", _transport(manifest, calls))
    with pytest.raises((ValueError, RuntimeError)):
        runner.draft(out, "clarified-1")
    assert not calls


@pytest.mark.parametrize("environment", ["test", " TEST ", "Test"])
def test_test_environment_blocks_all_spending_entrypoints(tmp_path, monkeypatch, environment):
    monkeypatch.setenv("LITHARNESS_ENV", environment)
    for function, args in (
        (T["prepare"], (tmp_path / "out", tmp_path / "source.json")),
        (T["call"], (tmp_path, "control-1")),
        (T["draft"], (tmp_path,)),
    ):
        with pytest.raises(RuntimeError, match="disabled in tests"):
            function(*args)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("returncode", "message"), [(0, "Logged in using an API key"), (1, "Logged in using ChatGPT")]
)
def test_prepare_refuses_unconfirmed_subscription_and_strips_api_environment(
    frozen, monkeypatch, returncode, message
):
    runner, out, _ = frozen
    calls = []

    def status(arguments, **kwargs):
        calls.append(arguments)
        assert arguments == ["node", "codex.js", "login", "status"]
        assert "OPENAI_API_KEY" not in kwargs["env"]
        return SimpleNamespace(returncode=returncode, stdout=message, stderr="")

    monkeypatch.delenv("LITHARNESS_ENV")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-value")
    monkeypatch.setattr(runner, "_registration_commit", lambda: "0" * 40)
    monkeypatch.setitem(T["CODEX"], "command_prefix", lambda: ["node", "codex.js"])
    monkeypatch.setattr(HELPER["subprocess"], "run", status)
    fresh = out.parent / "new"
    with pytest.raises(RuntimeError, match="ChatGPT subscription required"):
        runner.prepare(fresh, out / "source.json")
    assert len(calls) == 1 and not fresh.exists()


def test_registration_covers_new_runner_helper_and_all_reused_implementations():
    names = {path.name for path in T["EXPERIMENT"].registered_files}
    assert names == {
        "prose_recall_clarification.py",
        "prose_request_experiment.py",
        "prose_production_obligations.py",
        "prose_codex.py",
        "test_prose_recall_clarification.py",
        "PREREG.md",
        "RUNBOOK.md",
    }
