"""Offline containment and protocol checks for the Codex LitHarness tool bridge."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from litharness.providers import codex_tools


def make_bridge(
    tmp_path: Path, allowances: tuple[str, ...] | None = None,
) -> codex_tools.ToolBridge:
    return codex_tools.ToolBridge({
        "allowances": allowances or ("Bash(litharness world show:*)",
                                      "Bash(litharness world declare-batch:*)"),
        "environment": {"LITHARNESS_DATABASE": "pinned.db", "PATH": "fixed"},
        "cwd": str(tmp_path), "trace": str(tmp_path / "trace.jsonl"),
    })


@pytest.mark.parametrize("allowance", [
    "Bash(litharness world accept:*)", "Bash(litharness:*)", "Bash(python:*)",
    "Bash(litharness roster show:*)", "Bash(litharness roster vocabulary:*)",
    "Bash(litharness world show:*); calc", "Bash(litharness world unknown:*)",
])
def test_allowances_refuse_unknown_or_widened_capabilities(allowance: str) -> None:
    with pytest.raises(ValueError):
        codex_tools.validate_allowances((allowance,))


@pytest.mark.parametrize("arguments", [
    ["world", "accept"], ["python", "-c", "print(1)"],
    ["--database", "other.db", "world", "show"],
    ["world", "show", "--database=other.db"],
    ["world", "show", "--roster-database", "other.db"],
    ["world", "show", ";", "calc"], ["world", "show", "&&", "calc"],
    ["world", "show", ">output.txt"], ["world", "show", "2>&1"],
    ["world", "show", "|", "calc"], ["world", "show", "\ncalc"],
    ["roster", "show"], ["world", "show", 3], "world show",
])
def test_denied_arguments_never_start_a_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: Any,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("denied command reached subprocess")
    monkeypatch.setattr(codex_tools.subprocess, "run", forbidden)
    bridge = make_bridge(tmp_path)
    assert bridge.call(arguments)["isError"]
    rows = [json.loads(line) for line in bridge.trace.read_text().splitlines()]
    assert [row["phase"] for row in rows] == ["request", "result"]
    assert rows[1]["argv"] is None
    assert rows[1]["error_kind"] == "invalid_arguments"


def test_exact_roster_profile_prevents_dossier_access(tmp_path: Path) -> None:
    bridge = make_bridge(tmp_path, ("Bash(litharness roster show)",))
    assert bridge.call(["roster", "show", "--dossier"])["isError"]
    assert bridge.call(["world", "show"])["isError"]


def test_batch_json_passes_literally_with_fixed_environment_and_no_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch = '[\n{"subject":"Mira", "value":"$(calc) ; & > café"}\n]'
    arguments = ["world", "declare-batch", "--records", batch]
    calls = []
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "été".encode(), b"")
    monkeypatch.setattr(codex_tools.subprocess, "run", run)
    bridge = make_bridge(tmp_path)
    result = bridge.call(arguments)
    assert not result["isError"]
    argv, options = calls[0]
    assert argv == [sys.executable, "-m", "litharness", *arguments]
    assert options["shell"] is False and options["input"] == b""
    assert options["env"] == {
        "LITHARNESS_DATABASE": "pinned.db", "PATH": "fixed",
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
    }
    assert options["cwd"] == str(tmp_path) and options["timeout"] == 60
    recorded = json.loads(result["content"][0]["text"])
    assert recorded["stdout"] == "été" and recorded["returncode"] == 0
    assert "environment" not in recorded


def test_real_python_cli_output_uses_pinned_utf8_despite_parent_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_run = subprocess.run
    prose = "Vocabulary — café 火 §167"

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert argv == [sys.executable, "-m", "litharness", "world", "show"]
        script = f"import sys; print({prose!r}); print({prose!r}, file=sys.stderr)"
        return original_run([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(codex_tools.subprocess, "run", run)
    bridge = codex_tools.ToolBridge({
        "allowances": ["Bash(litharness world show:*)"],
        "environment": dict(os.environ) | {"PYTHONUTF8": "0", "PYTHONIOENCODING": "ascii"},
        "cwd": str(tmp_path), "trace": str(tmp_path / "trace.jsonl"),
    })
    result = bridge.call(["world", "show"])
    assert not result["isError"]
    row = json.loads(result["content"][0]["text"])
    assert row["stdout"].strip() == row["stderr"].strip() == prose
    retained = json.loads(bridge.trace.read_text(encoding="utf-8").splitlines()[-1])
    assert retained["stdout"] == row["stdout"] and retained["stderr"] == row["stderr"]


def test_timeout_is_recorded_without_crashing_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(argv: list[str], **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(argv, 60, output=b"partial", stderr=b"timeout detail")
    monkeypatch.setattr(codex_tools.subprocess, "run", run)
    result = make_bridge(tmp_path).call(["world", "show"])
    assert result["isError"]
    recorded = json.loads(result["content"][0]["text"])
    assert recorded["stdout"] == "partial" and recorded["stderr"] == "timeout detail"
    assert recorded["error"] == "tool timeout"
    assert recorded["error_kind"] == "timeout"


def test_call_and_argument_limits_prevent_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("over-budget command reached subprocess")
    monkeypatch.setattr(codex_tools.subprocess, "run", forbidden)
    bridge = make_bridge(tmp_path)
    bridge.calls = codex_tools.MAX_CALLS
    result = bridge.call(["world", "show"])
    assert result["isError"]
    assert json.loads(result["content"][0]["text"])["error_kind"] == "call_budget"
    bridge.calls = 0
    monkeypatch.setattr(codex_tools, "MAX_ARGUMENT_BYTES", 20)
    assert bridge.call(["world", "show", "x" * 30])["isError"]


def test_mcp_protocol_initialization_listing_and_error_recovery(tmp_path: Path) -> None:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18",
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "litharness_command", "arguments": {"arguments": ["world", "accept"]},
        }},
        {"jsonrpc": "2.0", "id": 4, "method": "unknown"},
        {"jsonrpc": "2.0", "id": 5, "method": "ping"},
    ]
    output = io.StringIO()
    codex_tools.serve(make_bridge(tmp_path), io.StringIO(
        "\n".join(json.dumps(request) for request in requests) + "\n",
    ), output)
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(replies) == 5
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    assert replies[1]["result"]["tools"] == [codex_tools.TOOL]
    assert replies[2]["result"]["isError"]
    assert replies[3]["error"]["code"] == -32601
    assert replies[4]["result"] == {}


def test_real_stdio_bridge_lists_tool_and_refuses_accept_without_database_access(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "allowances": ["Bash(litharness world show:*)"], "environment": {},
        "cwd": str(tmp_path), "trace": str(tmp_path / "trace.jsonl"),
    }), encoding="utf-8")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "litharness_command", "arguments": {"arguments": ["world", "accept"]},
        }},
    ]
    result = subprocess.run(
        [sys.executable, "-m", "litharness.providers.codex_tools", "--config", str(config)],
        input=("\n".join(json.dumps(row) for row in requests) + "\n").encode(),
        capture_output=True, shell=False, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    replies = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
    assert replies[0]["result"]["tools"] == [codex_tools.TOOL]
    assert replies[1]["result"]["isError"]


@pytest.mark.parametrize("error", [OSError("cannot launch"), ValueError("invalid launch")])
def test_subprocess_failures_have_execution_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception,
) -> None:
    def run(*args: Any, **kwargs: Any) -> None:
        raise error
    monkeypatch.setattr(codex_tools.subprocess, "run", run)
    result = make_bridge(tmp_path).call(["world", "show"])
    assert result["isError"]
    row = json.loads(result["content"][0]["text"])
    assert row["error_kind"] == "execution"
    assert row["argv"][:3] == [sys.executable, "-m", "litharness"]


@pytest.mark.parametrize("failed_write", [1, 2])
def test_trace_failure_is_distinct_and_initial_failure_prevents_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_write: int,
) -> None:
    bridge = make_bridge(tmp_path)
    writes = 0
    executions = []
    def record(row: dict[str, Any]) -> None:
        nonlocal writes
        writes += 1
        if writes == failed_write:
            raise OSError("trace unavailable")
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        executions.append(argv)
        return subprocess.CompletedProcess(argv, 0, b"ok", b"")
    monkeypatch.setattr(bridge, "_record", record)
    monkeypatch.setattr(codex_tools.subprocess, "run", run)
    result = bridge.call(["world", "show"])
    assert result["isError"]
    assert json.loads(result["content"][0]["text"])["error_kind"] == "trace"
    assert len(executions) == failed_write - 1


def test_nonzero_cli_verdict_is_not_classified_as_bridge_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 1, b'{"ok":false}', b"")
    monkeypatch.setattr(codex_tools.subprocess, "run", run)
    bridge = make_bridge(tmp_path, ("Bash(litharness world check:*)",))
    result = bridge.call(["world", "check"])
    row = json.loads(result["content"][0]["text"])
    assert row["returncode"] == 1 and row["stdout"] == '{"ok":false}'
    assert "error_kind" not in row and "error" not in row


def test_malformed_tool_shape_is_invalid_arguments_and_server_recovers(tmp_path: Path) -> None:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "litharness_command", "arguments": {"args": ["world", "show"]},
        }},
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ]
    output = io.StringIO()
    codex_tools.serve(make_bridge(tmp_path), io.StringIO(
        "\n".join(json.dumps(row) for row in requests) + "\n",
    ), output)
    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    result = replies[0]["result"]
    assert result["isError"]
    assert json.loads(result["content"][0]["text"])["error_kind"] == "invalid_arguments"
    assert replies[1]["result"] == {}
