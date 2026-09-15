"""The continuation fixes a real CLI boundary, without changing generation content."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from litharness import cli
from litharness.domain.generation import CompletionRequest
from litharness.providers.codex_cli import _BRIDGE_NOTE
from litharness.providers.codex_schema import prepare_codex_schema

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/experience-workflow-continuation-20260915/run.py"
)


@pytest.fixture
def continuation():
    spec = importlib.util.spec_from_file_location("experience_continuation_test", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_grow_resolves_a_logical_id_but_not_an_ordinal(continuation, tmp_path, monkeypatch):
    args = ["--database", str(tmp_path / "book.db"), "--chapter-scenes", "1"]
    assert cli.main([*args, "new", "Test", "--premise", "A premise.", "--scenes", "6"]) == 0
    reached = []

    def stop(request, **kwargs):
        reached.append(request.profile)
        return None, "offline preflight"

    monkeypatch.setattr(cli, "_completion_call", stop)
    with pytest.raises(KeyError, match="no node 1"):
        cli.main([*args, "architect", "grow", "--scene", "1"])
    assert not reached
    assert cli.main(args + continuation.command("A1", "grow1")) == 2
    assert len(reached) == 1
    assert reached[0].startswith("architect.grow.")


def test_schema_order_correction_preserves_other_semantics(continuation):
    left = {"required": ["b", "a"], "enum": ["b", "a"]}
    assert continuation.schema_canonical(left) == {"required": ["a", "b"], "enum": ["b", "a"]}
    assert continuation.schema_canonical(left) != continuation.schema_canonical(
        left | {"required": ["a"]}
    )


def test_corrected_controls_detect_system_schema_and_bridge_mutations(continuation, tmp_path):
    schema = {
        "type": "object",
        "properties": {"z": {"type": "string"}, "a": {"type": "string"}},
        "required": ["z", "a"],
    }
    tools = ("Bash(litharness world summary)",)
    request = CompletionRequest(prompt="Original", schema=schema, allowed_tools=tools)
    payload = json.loads(json.dumps(continuation.base.serial(request), sort_keys=True))
    command = {
        "phase": "result",
        "arguments": ["world", "summary"],
        "argv": [
            str(tmp_path / "runtimes/A/Scripts/python.exe"),
            "-m",
            "litharness",
            "world",
            "summary",
        ],
    }
    raw = {
        "system": request.effective_system + "\n\n" + _BRIDGE_NOTE,
        "schema": schema,
        "native_schema": prepare_codex_schema(schema),
        "argv": ["--output-schema", "path"],
        "commands_jsonl": json.dumps(command | {"phase": "request", "argv": None})
        + "\n"
        + json.dumps(command),
    }
    assert all(continuation.details(raw, payload, "A1", tmp_path).values())
    changed = raw | {
        "system": "Changed",
        "native_schema": raw["native_schema"] | {"required": ["a"]},
        "commands_jsonl": json.dumps(command | {"argv": ["wrong-python", *command["argv"][1:]]}),
    }
    checks = continuation.details(changed, payload, "A1", tmp_path)
    assert (
        not checks["system"]
        and not checks["native_schema"]
        and not checks["bridge_source_and_scope"]
    )


def test_empty_system_uses_only_the_exact_adapter_default(continuation):
    payload = continuation.base.serial(CompletionRequest(prompt="OK"))
    assert continuation.details({"system": "Complete the user's requested task."}, payload, "A1")[
        "system"
    ]
    assert not continuation.details({"system": "Something else"}, payload, "A1")["system"]
