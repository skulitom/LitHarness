"""A stdio MCP bridge exposing only a request's fixed LitHarness command allowance."""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, TextIO

_WORLD = {
    "summary", "show", "rules", "ladders", "abilities", "cast", "threads",
    "vocabulary", "presence", "check", "declare", "declare-batch",
}
_ROSTER = {"vocabulary", "show", "check", "declare"}
_ALLOWANCE = re.compile(r"Bash\(litharness (world|roster) ([a-z-]+)(:\*)?\)")
_SHELL = re.compile(r"^(?:[;&|<>]|\d+[<>])|[\r\n]")
MAX_CALLS = 512
MAX_ARGUMENT_BYTES = 1024 * 1024
TOOL = {
    "name": "litharness_command",
    "description": (
        "Run one allowed LitHarness command. Supply arguments as individual strings, "
        "starting with world or roster; omit the litharness executable. JSON values are "
        "single literal arguments, without shell quoting. No shell is available."
    ),
    "inputSchema": {
        "type": "object", "additionalProperties": False, "required": ["arguments"],
        "properties": {"arguments": {"type": "array", "items": {"type": "string"}}},
    },
}


def _allowances(allowances: tuple[str, ...]) -> list[tuple[str, str, bool]]:
    parsed = []
    for allowance in allowances:
        match = _ALLOWANCE.fullmatch(allowance)
        if match is None:
            raise ValueError(f"unsupported LitHarness tool allowance: {allowance!r}")
        group, command, suffix = match.groups()
        if command not in (_WORLD if group == "world" else _ROSTER):
            raise ValueError(f"unsupported LitHarness command allowance: {allowance!r}")
        if group == "roster" and command in {"vocabulary", "show"} and suffix:
            raise ValueError("roster vocabulary and show allowances must be exact")
        parsed.append((group, command, bool(suffix)))
    return parsed


def validate_allowances(allowances: tuple[str, ...]) -> None:
    """Refuse unknown or widened capabilities before launching a Codex call."""
    _allowances(allowances)


def _validate_arguments(arguments: object, allowances: list[tuple[str, str, bool]]) -> list[str]:
    if not isinstance(arguments, list) or not all(isinstance(arg, str) for arg in arguments):
        raise ValueError("arguments must be an array of strings")
    if sum(len(arg.encode("utf-8")) + 1 for arg in arguments) > MAX_ARGUMENT_BYTES:
        raise ValueError("command arguments exceed the byte limit")
    if len(arguments) < 2 or not any(
        arguments[:2] == [group, command] and (prefix or len(arguments) == 2)
        for group, command, prefix in allowances
    ):
        raise ValueError("command is outside this request's allowance")
    for argument in arguments:
        if "\0" in argument:
            raise ValueError("NUL is not allowed in command arguments")
        if argument.split("=", 1)[0] in {"--database", "--roster-database"}:
            raise ValueError("database overrides are not allowed")
        if _SHELL.search(argument):
            # Batch JSON is data even when a string inside it contains shell characters.
            try:
                data = json.loads(argument)
            except (ValueError, TypeError):
                data = None
            if not isinstance(data, (dict, list)):
                raise ValueError("shell syntax is not allowed; supply literal argument strings")
    return list(arguments)


def _text(value: str | bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


class ToolBridge:
    def __init__(self, config: dict[str, Any]) -> None:
        self.allowances = _allowances(tuple(config["allowances"]))
        # The trusted CLI prints JSON through Python stdio. Match the UTF-8 decoder
        # below even on Windows, independently of the parent's locale/encoding.
        self.environment = dict(config["environment"]) | {
            "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        }
        self.cwd = str(config["cwd"])
        self.trace = Path(config["trace"])
        self.calls = 0

    def _record(self, row: dict[str, Any]) -> None:
        with self.trace.open("a", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")

    def call(self, arguments: object) -> dict[str, Any]:
        self.calls += 1
        row: dict[str, Any] = {
            "call": self.calls, "arguments": arguments, "argv": None,
            "returncode": None, "stdout": "", "stderr": "",
        }
        failure_kind = "trace"
        try:
            self._record({**row, "phase": "request"})
            failure_kind = "call_budget"
            if self.calls > MAX_CALLS:
                raise ValueError("LitHarness tool call budget exhausted")
            failure_kind = "invalid_arguments"
            argv = [sys.executable, "-m", "litharness",
                    *_validate_arguments(arguments, self.allowances)]
            row["argv"] = argv
            failure_kind = "execution"
            completed = subprocess.run(
                argv, input=b"", capture_output=True, shell=False, timeout=60,
                cwd=self.cwd, env=self.environment, check=False,
            )
            row.update(returncode=completed.returncode, stdout=_text(completed.stdout),
                       stderr=_text(completed.stderr))
        except subprocess.TimeoutExpired as error:
            row.update(stdout=_text(error.stdout), stderr=_text(error.stderr),
                       error="tool timeout", error_kind="timeout")
        except (OSError, ValueError) as error:
            row.update(error=str(error), error_kind=failure_kind)
        try:
            self._record({**row, "phase": "result"})
        except OSError as error:
            row.update(error=f"unable to record tool result: {error}", error_kind="trace")
        return {
            "content": [{"type": "text", "text": json.dumps(row, ensure_ascii=False)}],
            "isError": bool(row.get("error")) or row["returncode"] != 0,
        }


def serve(bridge: ToolBridge, source: TextIO, target: TextIO) -> None:
    """Handle line-delimited MCP JSON-RPC; tool failures stay tool results."""
    while line := source.readline(MAX_ARGUMENT_BYTES * 2 + 1):
        reply: dict[str, Any]
        request: Any = None
        try:
            if len(line) > MAX_ARGUMENT_BYTES * 2:
                raise ValueError("MCP request exceeds the size limit")
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                raise ValueError("expected a JSON-RPC 2.0 object")
            if "id" not in request:
                continue
            method = request.get("method")
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("MCP params must be an object")
            if method == "initialize":
                result = {
                    "protocolVersion": params.get("protocolVersion", "2025-03-26"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "litharness-bound-tools", "version": "1"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [TOOL]}
            elif method == "tools/call":
                supplied = params.get("arguments")
                if (params.get("name") != TOOL["name"] or not isinstance(supplied, dict)
                        or set(supplied) != {"arguments"}):
                    result = bridge.call({"invalid_tool_request": params})
                else:
                    result = bridge.call(supplied["arguments"])
            else:
                target.write(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {
                    "code": -32601, "message": "method not found",
                }}) + "\n")
                target.flush()
                continue
            reply = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except (ValueError, TypeError) as error:
            reply = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict)
                     else None, "error": {"code": -32600, "message": str(error)}}
        target.write(json.dumps(reply, ensure_ascii=False) + "\n")
        target.flush()
        if len(line) > MAX_ARGUMENT_BYTES * 2:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    with args.config.open(encoding="utf-8") as source:
        bridge = ToolBridge(json.load(source))
    if isinstance(sys.stdin, io.TextIOWrapper):
        sys.stdin.reconfigure(encoding="utf-8")
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    serve(bridge, sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
