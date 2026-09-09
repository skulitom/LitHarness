"""Subscription-only Codex CLI transport with isolated completion and scoped tool modes."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol
from uuid import uuid4

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderFailureKind,
    Usage,
    classify_provider_failure,
    parse_schema_payload,
    provider_error,
)
from litharness.providers.cli import CommandResult
from litharness.providers.codex_schema import prepare_codex_schema, restore_optional_omissions

_ENV_KEYS = frozenset(
    [
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "COMSPEC",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "USERNAME",
        "USERDOMAIN",
        "LANG",
        "LC_ALL",
        "TZ",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
        "TERM",
        "CODEX_HOME",
        "CODEX_CA_CERTIFICATE",
    ]
)
_BRIDGE_ENV_KEYS = (
    "LITHARNESS_DATABASE",
    "LITHARNESS_ROSTER_DATABASE",
    "LITHARNESS_RECRUIT_SHELF",
    "LITHARNESS_RECRUIT_SHAPE",
)
_BRIDGE_NOTE = (
    "Use the litharness_command MCP tool for the litharness commands described above. "
    "Pass their arguments as a JSON array, excluding the leading litharness executable. "
    "The bridge executes only the commands this task permits, without a shell."
)
_BRIDGE_APPROVAL_KEY = "mcp_servers.litharness.tools.litharness_command.approval_mode"


def subscription_environment(source: dict[str, str]) -> dict[str, str]:
    """Keep platform/auth locations and connection settings, without API keys or app controls."""
    return {key: value for key, value in source.items() if key.upper() in _ENV_KEYS}


class CodexRunner(Protocol):
    def __call__(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        cwd: str,
        env: dict[str, str],
        stdin: str = "",
    ) -> CommandResult: ...


def subprocess_runner(
    argv: Sequence[str],
    *,
    timeout: float,
    cwd: str,
    env: dict[str, str],
    stdin: str = "",
) -> CommandResult:
    completed = subprocess.run(
        list(argv),
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _json_file(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _text(value: str | bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


@dataclass
class CodexCliProvider:
    """One explicitly chosen Codex model; no application retry or model fallback.

    Plain completions disable unused built-ins and reject reported tool activity. WebSearch
    enables native search; world/roster requests use a local MCP bridge that checks the
    existing command allowance before dispatch.
    Raw JSONL, stderr and the submitted transport configuration remain in the result. They
    describe the local request, not a capture of every provider-side instruction.
    """

    name: str = "codex"
    bills: bool = True
    supports_tool_permissions: bool = True
    model: str = "gpt-6-astra"
    reasoning_effort: str = "medium"
    binary: str = "codex.exe" if os.name == "nt" else "codex"
    runner: CodexRunner = subprocess_runner
    trace_directory: Path | None = None
    last_attempt: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def health(self) -> bool:
        try:
            return bool(
                self.complete(
                    CompletionRequest(
                        prompt="Reply with the single word OK.",
                        timeout_seconds=120,
                    )
                ).text.strip()
            )
        except ProviderError:
            return False

    def _mode(self, request: CompletionRequest) -> str:
        if not request.allowed_tools:
            return "completion"
        if request.allowed_tools == ("WebSearch",):
            return "search"
        from litharness.providers.codex_tools import validate_allowances

        validate_allowances(request.allowed_tools)
        return "bridge"

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started = time.monotonic()
        raw: dict[str, Any] = {
            "provider": self.name,
            "requested_model": request.model or self.model,
        }
        self.last_attempt = raw
        trace_path = None
        try:
            if self.trace_directory is not None:
                self.trace_directory.mkdir(parents=True, exist_ok=True)
                trace_path = self.trace_directory / f"attempt-{uuid4().hex}.json"
                _json_file(trace_path, raw)
            mode = self._mode(request)
            native_schema = None
            schema_reason = None
            if request.schema is not None:
                try:
                    native_schema = prepare_codex_schema(request.schema)
                except ValueError as error:
                    # Open maps cannot become closed objects without changing the requested
                    # data. Keep the original JSON instruction and downstream validation.
                    schema_reason = str(error)
            if Path(self.binary).suffix.lower() in {".bat", ".cmd", ".ps1"}:
                raise ValueError("Codex must be a native executable, not a shell wrapper")
            with TemporaryDirectory(prefix="litharness-codex-") as temporary:
                artifacts = Path(temporary)
                working = artifacts / "working"
                working.mkdir()
                env = subscription_environment(dict(os.environ))
                auth = self.runner(
                    [
                        self.binary,
                        "-c",
                        'forced_login_method="chatgpt"',
                        "-c",
                        'model_provider="openai"',
                        "login",
                        "status",
                    ],
                    timeout=30,
                    cwd=str(working),
                    env=env,
                )
                if auth.returncode or "Logged in using ChatGPT" not in auth.stdout + auth.stderr:
                    raise provider_error(
                        "Codex requires a ChatGPT subscription login; no generation attempted",
                        kind=ProviderFailureKind.AUTH,
                    )
                raw["auth_method"] = "chatgpt"
                version = self.runner(
                    [self.binary, "--version"],
                    timeout=30,
                    cwd=str(working),
                    env=env,
                )
                if version.returncode:
                    raise ValueError("Could not read the installed Codex version")
                raw["cli_version"] = version.stdout.strip()
                system = request.effective_system
                if mode == "bridge":
                    system = "\n\n".join(part for part in (system, _BRIDGE_NOTE) if part)
                system_path = artifacts / "system.txt"
                system_path.write_text(
                    system or "Complete the user's requested task.", encoding="utf-8"
                )
                final_path = artifacts / "final.txt"
                argv = [
                    self.binary,
                    "exec",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--cd",
                    str(working),
                    "--model",
                    request.model or self.model,
                    "--json",
                    "--color",
                    "never",
                    "--output-last-message",
                    str(final_path),
                ]
                settings: dict[str, Any] = {
                    "forced_login_method": "chatgpt",
                    "model_provider": "openai",
                    "model_instructions_file": system_path.as_posix(),
                    "model_reasoning_effort": self.reasoning_effort,
                    "project_doc_max_bytes": 0,
                    "web_search": "live" if mode == "search" else "disabled",
                    "hide_agent_reasoning": True,
                    "features.shell_tool": False,
                    "features.multi_agent": False,
                    "features.apps": False,
                    "features.plugins": False,
                    "features.hooks": False,
                    "features.memories": False,
                    "features.code_mode": False,
                    "features.view_image": False,
                    "features.browser_use": False,
                    "features.browser_use_external": False,
                    "features.browser_use_full_cdp_access": False,
                    "features.in_app_browser": False,
                    "features.computer_use": False,
                    "features.image_generation": False,
                    "features.sleep_tool": False,
                    "features.goals": False,
                    "features.skill_search": False,
                    "features.tool_suggest": False,
                    "features.workspace_dependencies": False,
                    "features.skill_mcp_dependency_install": False,
                    "features.multi_agent_v2": False,
                    "tools.update_plan.enabled": False,
                    "tools.experimental_request_user_input.enabled": False,
                    "skills.include_instructions": False,
                    "skills.bundled.enabled": False,
                    "history.persistence": "none",
                }
                bridge_trace = artifacts / "commands.jsonl"
                if mode == "bridge":
                    bridge_env = {
                        key: os.environ[key] for key in _BRIDGE_ENV_KEYS if key in os.environ
                    }
                    if not bridge_env.get("LITHARNESS_DATABASE"):
                        raise ValueError("Scoped Codex commands require LITHARNESS_DATABASE")
                    for key in ("LITHARNESS_DATABASE", "LITHARNESS_ROSTER_DATABASE"):
                        if bridge_env.get(key):
                            bridge_env[key] = str(Path(bridge_env[key]).resolve())
                    bridge_config = artifacts / "bridge.json"
                    _json_file(
                        bridge_config,
                        {
                            "allowances": list(request.allowed_tools),
                            "environment": env | bridge_env,
                            "cwd": str(working),
                            "trace": str(bridge_trace),
                        },
                    )
                    settings.update(
                        {
                            "mcp_servers.litharness.command": sys.executable,
                            "mcp_servers.litharness.args": [
                                "-m",
                                "litharness.providers.codex_tools",
                                "--config",
                                str(bridge_config),
                            ],
                            "mcp_servers.litharness.enabled": True,
                            "mcp_servers.litharness.required": True,
                            "mcp_servers.litharness.enabled_tools": ["litharness_command"],
                            _BRIDGE_APPROVAL_KEY: "approve",
                        }
                    )
                for key, value in settings.items():
                    argv.extend(["-c", f"{key}={json.dumps(value)}"])
                if native_schema is not None:
                    schema_path = artifacts / "schema.json"
                    _json_file(schema_path, native_schema)
                    argv.extend(["--output-schema", str(schema_path)])
                argv.append("-")
                raw.update(
                    argv=argv,
                    prompt=request.prompt,
                    system=system_path.read_text(encoding="utf-8"),
                    mode=mode,
                    settings=settings,
                    builtin_controls="unused-builtins-disabled.v1",
                    schema=request.schema,
                    native_schema=native_schema,
                    schema_variant=(
                        "strict-nullable-optionals.v1"
                        if native_schema is not None
                        else "prompt-only-original.v1"
                        if request.schema is not None
                        else None
                    ),
                    native_schema_omission_reason=schema_reason,
                    model_attribution="requested; Codex JSONL does not report a resolved model",
                    working_directory=str(working),
                    environment_keys=sorted(env),
                )
                if trace_path is not None:
                    _json_file(trace_path, raw)
                try:
                    response = self.runner(
                        argv,
                        timeout=request.timeout_seconds,
                        cwd=str(working),
                        env=env,
                        stdin=request.prompt,
                    )
                except subprocess.TimeoutExpired as error:
                    raw.update(
                        stdout=_text(error.stdout), stderr=_text(error.stderr), timed_out=True
                    )
                    raise
                finally:
                    # Failed validation and timeouts still remove this temporary directory.
                    # Capture the independent final file before either can discard evidence.
                    if final_path.is_file():
                        final_bytes = final_path.read_bytes()
                        try:
                            raw["final_text"] = final_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            raw["final_bytes_base64"] = base64.b64encode(final_bytes).decode(
                                "ascii"
                            )
                    if bridge_trace.exists():
                        raw["commands_jsonl"] = bridge_trace.read_text(encoding="utf-8")
                raw.update(
                    stdout=response.stdout, stderr=response.stderr, returncode=response.returncode
                )
                text, events, usage = _completed_response(response, final_path, mode)
                raw.update(events=events, final_text=text)
                if mode == "bridge":
                    _validate_bridge_activity(
                        events, raw.get("commands_jsonl", ""), request.profile
                    )
                if native_schema is not None and request.schema is not None:
                    try:
                        payload = restore_optional_omissions(json.loads(text), request.schema)
                        text = json.dumps(payload, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        # Preserve malformed text for the existing format-failure policy.
                        # Ambiguous restoration is a ValueError and must refuse this result.
                        pass
                return CompletionResult(
                    text=text,
                    provider=self.name,
                    model=request.model or self.model,
                    usage=usage,
                    parsed=parse_schema_payload(text, request.schema),
                    schema_requested=request.schema is not None,
                    cost_usd=None,
                    wall_ms=int((time.monotonic() - started) * 1000),
                    raw=raw,
                )
        except subprocess.TimeoutExpired as error:
            raw["failure"] = str(error)
            raise provider_error(
                f"Codex timed out after {error.timeout}s",
                kind=ProviderFailureKind.TIMEOUT,
                raw=json.dumps(raw, ensure_ascii=False),
            ) from error
        except OSError as error:
            raw["failure"] = str(error)
            raise provider_error(
                f"Codex could not be executed: {error}",
                kind=ProviderFailureKind.UNAVAILABLE,
                raw=json.dumps(raw, ensure_ascii=False),
            ) from error
        except ValueError as error:
            raw["failure"] = str(error)
            raise provider_error(
                f"Codex request or response was unusable: {error}",
                kind=ProviderFailureKind.INVALID_REQUEST
                if "stdout" not in raw
                else ProviderFailureKind.MALFORMED_RESPONSE,
                raw=json.dumps(raw, ensure_ascii=False),
            ) from error
        except ProviderError as error:
            raw["failure"] = str(error)
            raise
        finally:
            if trace_path is not None:
                raw["wall_ms"] = int((time.monotonic() - started) * 1000)
                _json_file(trace_path, raw)


def _transport_notice(event: dict[str, Any]) -> bool:
    """Recognize native connection notices, not arbitrary model or tool errors."""
    if event.get("type") == "error":
        message = event.get("message")
        return isinstance(message, str) and re.fullmatch(
            r"Reconnecting\.\.\. [1-9][0-9]*/[1-9][0-9]* \(.+\)", message, re.DOTALL
        ) is not None
    item = event.get("item")
    return (
        event.get("type") == "item.completed"
        and isinstance(item, dict)
        and item.get("type") == "error"
        and isinstance(item.get("message"), str)
        and item["message"].startswith("Falling back from WebSockets to HTTPS transport.")
    )


def _completed_response(
    response: CommandResult,
    final_path: Path,
    mode: str,
) -> tuple[str, list[dict[str, Any]], Usage]:
    if response.returncode:
        diagnostics = [response.stderr]
        for line in response.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") in {"error", "turn.failed"}:
                diagnostics.append(json.dumps(event, ensure_ascii=False))
        detail = "\n".join(part for part in diagnostics if part)
        raise provider_error(
            f"Codex exited with code {response.returncode}: {detail[:300]}",
            kind=classify_provider_failure(detail),
            raw=response.stdout + response.stderr,
        )
    events = [json.loads(line) for line in response.stdout.splitlines() if line.strip()]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Codex JSONL contains a non-object event")
    # The CLI can recover connection setup before producing content. These notices
    # remain in the receipt; they cannot excuse a failed turn or invalid final output.
    transport_notices: set[int] = set()
    for index, event in enumerate(events):
        if event.get("type") in {"thread.started", "turn.started"}:
            continue
        if not _transport_notice(event):
            break
        transport_notices.add(index)
    if transport_notices and (
        sum(event.get("type") == "turn.started" for event in events) != 1
        or sum(event.get("type") == "thread.started" for event in events) > 1
    ):
        raise ValueError("Codex transport recovery did not stay within one turn")
    completed = [event for event in events if event.get("type") == "turn.completed"]
    if len(completed) != 1 or any(
        event.get("type") in {"turn.failed", "error"} and index not in transport_notices
        for index, event in enumerate(events)
    ):
        raise ValueError("Codex did not report exactly one successful turn")
    for index, event in enumerate(events):
        if index in transport_notices:
            continue
        if not str(event.get("type", "")).startswith("item."):
            continue
        item = event.get("item") or {}
        kind = item.get("type")
        if kind in {"agent_message", "reasoning"}:
            continue
        if mode == "search" and kind == "web_search":
            continue
        if (
            mode == "bridge"
            and kind == "mcp_tool_call"
            and (item.get("server") == "litharness" and item.get("tool") == "litharness_command")
        ):
            continue
        raise ValueError(f"Codex attempted an unpermitted activity: {kind}")
    if not final_path.is_file():
        raise ValueError("Codex completed without its final-message file")
    text = final_path.read_bytes().decode("utf-8")
    messages = [
        event["item"].get("text")
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    if not text.strip() or not messages or text.rstrip("\r\n") != str(messages[-1]).rstrip("\r\n"):
        raise ValueError("Codex final-message file does not match its last emitted message")
    reported = completed[0].get("usage")
    if not isinstance(reported, dict) or not {"input_tokens", "output_tokens"} <= set(reported):
        raise ValueError("Codex completed without required input/output token usage")
    counts = [
        reported.get(key, 0)
        for key in (
            "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"
        )
    ]
    if any(type(value) is not int for value in counts):
        raise ValueError("Codex token usage must contain integer counts")
    inputs, cached, outputs, reasoning = counts
    if min(inputs, cached, outputs, reasoning) < 0 or cached > inputs or reasoning > outputs:
        raise ValueError("Codex returned inconsistent token usage")
    return (
        text,
        events,
        Usage(
            input_tokens=inputs - cached,
            cache_read_tokens=cached,
            output_tokens=outputs - reasoning,
            reasoning_tokens=reasoning,
        ),
    )


def _validate_bridge_activity(
    events: list[dict[str, Any]],
    commands_jsonl: str,
    profile: str,
) -> None:
    """A blocked tool turn is not a successful architect run merely because prose arrived."""
    commands = [json.loads(line) for line in commands_jsonl.splitlines() if line.strip()]
    finished = [row for row in commands if isinstance(row, dict) and row.get("phase") == "result"]

    def executed(row: dict[str, Any]) -> bool:
        return (
            type(row.get("returncode")) is int
            and isinstance(row.get("argv"), list)
            and bool(row["argv"])
            and not row.get("error")
            and not row.get("error_kind")
        )

    def recovered_arguments(row: dict[str, Any]) -> bool:
        return (
            row.get("error_kind") == "invalid_arguments"
            and bool(row.get("error"))
            and row.get("argv") is None
            and row.get("returncode") is None
            and type(row.get("call")) is int
            and any(
                executed(later)
                and type(later.get("call")) is int
                and later["call"] > row["call"]
                for later in finished
            )
        )

    # The bridge knows whether it refused arguments or failed to execute/record a command.
    # Only argument refusals can be recovered by the model in this same response.
    for row in finished:
        if (row.get("error") or row.get("error_kind")) and not recovered_arguments(row):
            kind = row.get("error_kind", "unclassified")
            raise ValueError(f"The scoped command failed ({kind}): {row.get('error', '')}")

    for event in events:
        item = event.get("item") or {}
        if event.get("type") != "item.completed" or item.get("type") != "mcp_tool_call":
            continue
        result = item.get("result") or {}
        failed = (
            item.get("status") in {"failed", "cancelled"}
            or item.get("error")
            or (isinstance(result, dict) and result.get("isError"))
        )
        if not failed:
            continue
        # Both ordinary nonzero CLI results and recovered argument mistakes must have an
        # exact bridge receipt. A denial before the bridge was reached has no such receipt.
        receipts = []
        if isinstance(result, dict):
            for block in result.get("content", []):
                try:
                    receipt = json.loads(block.get("text", ""))
                except (ValueError, AttributeError):
                    continue
                if isinstance(receipt, dict):
                    receipts.append(receipt)
        if item.get("error") or item.get("status") == "cancelled" or not any(
            type(row.get("call")) is int
            and {key: value for key, value in row.items() if key != "phase"}
            == {key: value for key, value in receipt.items() if key != "phase"}
            and (executed(row) or recovered_arguments(row))
            for row in finished
            for receipt in receipts
        ):
            raise ValueError("The MCP tool failed without a completed scoped command receipt")
    # Optional-tool diagnostics may legitimately answer without using a tool. These roles
    # explicitly require inspecting the stored world; no command means their task did not run.
    if profile.startswith(("architect.seed.v", "architect.grow.v")) and not any(
        executed(row) and row["returncode"] == 0 for row in finished
    ):
        raise ValueError("The architect returned without any successful scoped world command")
