"""Lossless annotation movement, matched arms and subscription dispatch containment."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_source_contract.py"))
F = runpy.run_path(str(ROOT / "tests/test_prose_prospective_attention.py"))


def source():
    original = F["source"]()
    facts = original["source"]["chapter_source"]["facts"]
    segments = [
        {"role": "story", "text": "An event. "},
        {"role": "editorial", "text": "Preserve its timing.\n"},
        {"role": "story", "text": " A consequence."},
        {"role": "editorial", "text": " Do not invent an explanation."},
    ]
    facts[1]["text"] = "".join(s["text"] for s in segments)
    return {"source": original, "partitions": [{"id": facts[1]["id"], "segments": segments}]}


def test_source_contract_split_is_lossless_and_preserves_every_other_field():
    s = source()
    before = copy.deepcopy(s)
    embedded, separated = (T["payloads"](s)[k] for k in ("embedded", "separated"))
    assert embedded == T["BASE"]["payload"](s["source"])
    assert separated.pop("editorial_constraints") == [
        {"source_id": "F1b", "text": "Preserve its timing.\n"},
        {"source_id": "F1b", "text": " Do not invent an explanation."},
    ]
    assert separated["source_units"][1]["text"] == "An event.  A consequence."
    separated["source_units"][1]["text"] = embedded["source_units"][1]["text"]
    assert separated == embedded
    assert s == before


def test_source_contract_constraint_order_follows_source_and_segment_order():
    s = source()
    facts = s["source"]["source"]["chapter_source"]["facts"]
    facts[0]["text"] = "Earlier story. Earlier direction."
    s["partitions"].append(
        {
            "id": facts[0]["id"],
            "segments": [
                {"role": "story", "text": "Earlier story."},
                {"role": "editorial", "text": " Earlier direction."},
            ],
        }
    )
    constraints = T["payloads"](s)["separated"]["editorial_constraints"]
    assert [c["source_id"] for c in constraints] == ["F1a", "F1b", "F1b"]


@pytest.mark.parametrize(
    "bad",
    [
        "wrapper",
        "empty",
        "duplicate",
        "unknown",
        "missing_id",
        "missing_segments",
        "empty_segments",
        "unknown_role",
        "missing_role",
        "missing_text",
        "empty_text",
        "blank_story",
        "blank_editorial",
        "only_story",
        "only_editorial",
        "changed_text",
        "dropped_space",
        "extra_field",
    ],
)
def test_source_contract_refuses_invalid_or_lossy_partitions(bad):
    s = source()
    partition, segments = s["partitions"][0], s["partitions"][0]["segments"]
    if bad == "wrapper":
        s["extra"] = True
    elif bad == "empty":
        s["partitions"] = []
    elif bad == "duplicate":
        s["partitions"].append(copy.deepcopy(partition))
    elif bad == "unknown":
        partition["id"] = "missing"
    elif bad == "missing_id":
        partition.pop("id")
    elif bad == "missing_segments":
        partition.pop("segments")
    elif bad == "empty_segments":
        partition["segments"] = []
    elif bad == "unknown_role":
        segments[0]["role"] = "interpretation"
    elif bad == "missing_role":
        segments[0].pop("role")
    elif bad == "missing_text":
        segments[0].pop("text")
    elif bad == "empty_text":
        segments[0]["text"] = ""
    elif bad in ("blank_story", "blank_editorial"):
        role = bad.removeprefix("blank_")
        for segment in segments:
            if segment["role"] == role:
                segment["text"] = " \n"
    elif bad in ("only_story", "only_editorial"):
        for segment in segments:
            segment["role"] = bad.removeprefix("only_")
    elif bad == "changed_text":
        segments[0]["text"] += "NEW"
    elif bad == "dropped_space":
        segments[0]["text"] = segments[0]["text"].rstrip()
    else:
        segments[0]["extra"] = "instruction"
    with pytest.raises(ValueError):
        T["compose"](s)


def test_source_contract_changes_only_representation_and_the_exact_length_substring():
    requests = T["compose"](source())
    assert set(requests) == {
        "embedded-target",
        "separated-target",
        "embedded-free",
        "separated-free",
    }
    for representation in ("embedded", "separated"):
        target, free = (requests[f"{representation}-{length}"] for length in ("target", "free"))
        assert target["prompt"] == free["prompt"]
        assert target["system"] == (T["BASE"]["WRITER_SYSTEM"] + "\n" + T["EDITORIAL_INSTRUCTION"])
        assert free["system"] == target["system"].replace("Aim for 1500-1800 words. ", "", 1)
        assert "prospective_attention" not in json.loads(target["prompt"])
        assert "Incidental original wording" not in target["prompt"]
    for length in ("target", "free"):
        assert (
            requests[f"embedded-{length}"]["system"] == (requests[f"separated-{length}"]["system"])
        )


def _completed(out, name, result=None):
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    T["write_new"](folder / "full-1.request.json", {})
    T["write_new"](
        folder / "full-1.result.json",
        result
        or {
            "status": "completed",
            "usage": {
                "input_tokens": 7,
                "cached_input_tokens": 7,
                "output_tokens": 3,
                "reasoning_output_tokens": 2,
            },
        },
    )


def test_source_contract_quota_counts_reasoning_once_and_stops_at_the_bound(tmp_path):
    for name in T["ORDER"][:2]:
        _completed(tmp_path, name)
    assert T["quota"](tmp_path) == 24
    path = tmp_path / T["ORDER"][1] / "full-1.result.json"
    result = T["read"](path)
    result["usage"]["reasoning_output_tokens"] += T["TOKEN_STOP"] - 24
    path.write_text(json.dumps(result))
    with pytest.raises(RuntimeError, match="token stop"):
        T["quota"](tmp_path)


@pytest.mark.parametrize("bad", ["unknown", "order", "orphan", "missing", "failed", "usage"])
def test_source_contract_quota_refuses_unregistered_missing_failed_or_invalid_calls(tmp_path, bad):
    name = "unknown" if bad == "unknown" else T["ORDER"][1 if bad == "order" else 0]
    _completed(tmp_path, name)
    folder = tmp_path / name
    if bad == "orphan":
        (folder / "full-1.request.json").unlink()
    elif bad == "missing":
        (folder / "full-1.result.json").unlink()
    elif bad == "failed":
        (folder / "full-1.result.json").write_text(json.dumps({"status": "failed"}))
    elif bad == "usage":
        result = T["read"](folder / "full-1.result.json")
        result["usage"]["input_tokens"] = True
        (folder / "full-1.result.json").write_text(json.dumps(result))
    with pytest.raises((ValueError, RuntimeError)):
        T["quota"](tmp_path)


@pytest.mark.parametrize("name", T["ORDER"])
def test_source_contract_test_guard_precedes_every_dispatch(tmp_path, name):
    with pytest.raises(RuntimeError, match="disabled in tests"):
        T["call"](tmp_path, name, {}, {})
    assert not list(tmp_path.glob("*/full-1.request.json"))


def test_source_contract_test_guard_also_blocks_prepare_and_draft(tmp_path):
    with pytest.raises(RuntimeError, match="disabled in tests"):
        T["prepare"](tmp_path / "new", tmp_path / "missing-source.json")
    with pytest.raises(RuntimeError, match="disabled in tests"):
        T["draft"](tmp_path)
    assert not list(tmp_path.iterdir())


def _manifest(out, monkeypatch):
    s = source()
    source_path = out / "source.json"
    T["write_new"](source_path, s)
    requests = T["compose"](s)
    prefix = ["node", "codex.js"]
    systems = []
    for name in T["ORDER"]:
        folder = out / name
        folder.mkdir()
        path = folder / "system.txt"
        path.write_text(requests[name.rsplit("-", 1)[0]]["system"], encoding="utf-8")
        systems.append(path)
    paths = [source_path, *systems]
    monkeypatch.setitem(T["validate"].__globals__, "_files", lambda *_: paths)
    manifest = {
        "source": s,
        "source_path": str(source_path),
        "requests": requests,
        "slot_requests": {
            n: T["_record"](out, n, requests[n.rsplit("-", 1)[0]], prefix) for n in T["ORDER"]
        },
        "prefix": prefix,
        "order": list(T["ORDER"]),
        "token_stop": T["TOKEN_STOP"],
        "files": {str(p): T["sha"](p) for p in paths},
        "authentication": "chatgpt",
        "reasoning_effort": "high",
        "transport_slot_per_logical_call": "full-1",
    }
    T["write_new"](out / "manifest.json", manifest)
    return manifest


@pytest.mark.parametrize("bad", ["system", "request", "slot", "source", "order", "inventory"])
def test_source_contract_validation_detects_frozen_artifact_and_identity_tampering(
    tmp_path, monkeypatch, bad
):
    manifest = _manifest(tmp_path, monkeypatch)
    assert T["validate"](tmp_path) == manifest
    if bad == "system":
        (tmp_path / T["ORDER"][0] / "system.txt").write_text("changed")
    else:
        if bad == "request":
            manifest["requests"]["embedded-target"]["prompt"] += "changed"
        elif bad == "slot":
            manifest["slot_requests"][T["ORDER"][0]]["reasoning_effort"] = "low"
        elif bad == "source":
            manifest["source"]["partitions"].clear()
        elif bad == "order":
            manifest["order"].reverse()
        else:
            manifest["files"].pop(manifest["source_path"])
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        T["validate"](tmp_path)


def test_source_contract_recorded_request_identity_cannot_drift(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    record = copy.deepcopy(manifest["slot_requests"][T["ORDER"][0]])
    record["prompt"] += "changed"
    T["write_new"](tmp_path / T["ORDER"][0] / "full-1.request.json", record)
    with pytest.raises(ValueError, match="recorded request identity"):
        T["validate"](tmp_path)


def test_source_contract_dispatch_order_and_effort_with_an_inert_transport(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    calls = []

    def inert(folder, name, request, *, effort):
        calls.append((folder.name, name, effort))
        T["write_new"](folder / "full-1.request.json", manifest["slot_requests"][folder.name])
        result = {"status": "completed", "usage": {"input_tokens": 1, "output_tokens": 1}}
        T["write_new"](folder / "full-1.result.json", result)
        assert request["requests"]["full"] == (manifest["requests"][folder.name.rsplit("-", 1)[0]])
        return result

    monkeypatch.setitem(T["CODEX"], "complete_once", inert)
    monkeypatch.delenv("LITHARNESS_ENV")
    with pytest.raises(ValueError, match="prior invocation missing"):
        T["call"](tmp_path, T["ORDER"][1], manifest["requests"]["separated-target"], manifest)
    assert calls == []
    T["draft"](tmp_path)
    assert calls == [(name, "full-1", "high") for name in T["ORDER"]]
