"""Offline subscription transport, schema handoff and opt-in composition checks."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from litharness.providers import (
    BillingGuardViolation,
    ClaudeCodeProvider,
    CodexCliProvider,
    FakeProvider,
    build_default_registry,
)
from litharness.providers.base import CompletionRequest, ProviderError, ProviderFailureKind
from litharness.providers.cli import CommandResult
from litharness.providers.codex_cli import (
    _validate_bridge_activity,
    subprocess_runner,
    subscription_environment,
)


class Runner:
    def __init__(self):
        self.calls = []
        self.text = "# A chapter\n\nCafé 火—and a door.\n\n"
        self.auth = "Logged in using ChatGPT"
        self.extra_events = []
        self.completed = True
        self.returncode = 0
        self.stderr = "diagnostic stderr"
        self.stdout_override = None
        self.timeout = False
        self.schema = None
        self.system = None
        self.bridge = None
        self.omit_final = False
        self.mismatch = False
        self.final_bytes = None

    def __call__(self, argv, *, timeout, cwd, env, stdin=""):
        self.calls.append((list(argv), cwd, dict(env), stdin))
        assert Path(cwd).is_dir() and not list(Path(cwd).iterdir())
        if "login" in argv:
            return CommandResult(0, "", self.auth)
        if "--version" in argv:
            return CommandResult(0, "codex-cli 0.153.4\n")
        settings = {}
        for index, arg in enumerate(argv):
            if arg == "-c":
                key, value = argv[index + 1].split("=", 1)
                settings[key] = json.loads(value)
        self.system = Path(settings["model_instructions_file"]).read_text(encoding="utf-8")
        if "--output-schema" in argv:
            self.schema = json.loads(Path(argv[argv.index("--output-schema") + 1]).read_bytes())
        if "mcp_servers.litharness.args" in settings:
            self.bridge = json.loads(Path(settings["mcp_servers.litharness.args"][-1]).read_bytes())
            Path(self.bridge["trace"]).write_text('{"test": "command trace"}\n', encoding="utf-8")
        if self.final_bytes is not None:
            Path(argv[argv.index("--output-last-message") + 1]).write_bytes(self.final_bytes)
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, timeout, output=b"partial", stderr=b"timed out")
        if not self.omit_final and self.final_bytes is None:
            Path(argv[argv.index("--output-last-message") + 1]).write_text(
                "different" if self.mismatch else self.text,
                encoding="utf-8",
                newline="",
            )
        events = [
            {"type": "thread.started", "thread_id": "fresh"},
            {"type": "turn.started"},
            *self.extra_events,
            {"type": "item.completed", "item": {"type": "agent_message", "text": self.text}},
        ]
        if self.completed:
            events.append(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 30,
                        "output_tokens": 12,
                        "reasoning_output_tokens": 4,
                    },
                }
            )
        stdout = (
            self.stdout_override
            if self.stdout_override is not None
            else "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
        )
        return CommandResult(self.returncode, stdout, self.stderr)


def test_codex_request_isolated_and_raw_response_preserved(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("CODEX_THREAD_ID", "inherited-thread")
    runner = Runner()
    result = CodexCliProvider(runner=runner).complete(
        CompletionRequest(
            prompt="An exact fresh brief. 火",
            system="Original author instructions.",
        )
    )
    assert result.text == runner.text
    assert result.provider == "codex" and result.model == "gpt-6-astra"
    assert result.cost_usd is None and result.usage.total == 112
    assert result.usage.input_tokens == 70 and result.usage.cache_read_tokens == 30
    assert result.usage.output_tokens == 8 and result.usage.reasoning_tokens == 4
    assert result.raw["stdout"] and result.raw["stderr"] == "diagnostic stderr"
    assert result.raw["system"] == runner.system == "Original author instructions."
    assert result.raw["settings"]["model_reasoning_effort"] == "medium"
    for feature in (
        "code_mode", "view_image", "browser_use", "browser_use_external",
        "browser_use_full_cdp_access", "in_app_browser", "computer_use", "image_generation",
        "sleep_tool", "goals", "skill_search", "tool_suggest", "workspace_dependencies",
        "skill_mcp_dependency_install", "multi_agent_v2",
    ):
        assert result.raw["settings"][f"features.{feature}"] is False
    for setting in (
        "tools.update_plan.enabled", "tools.experimental_request_user_input.enabled",
        "skills.include_instructions", "skills.bundled.enabled",
    ):
        assert result.raw["settings"][setting] is False
    assert "features.code_mode_host" not in result.raw["settings"]
    assert "features.unified_exec" not in result.raw["settings"]
    assert result.raw["settings"]["web_search"] == "disabled"
    assert result.raw["builtin_controls"] == "unused-builtins-disabled.v1"
    argv, cwd, env, stdin = runner.calls[-1]
    assert stdin == "An exact fresh brief. 火" and argv[-1] == "-"
    assert "--ignore-user-config" in argv and "--ignore-rules" in argv
    assert "--ephemeral" in argv and "--skip-git-repo-check" in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "OPENAI_API_KEY" not in env and "CODEX_THREAD_ID" not in env
    assert not Path(cwd).exists()
    assert len(runner.calls) == 3


def test_codex_subscription_environment_discards_keys_routes_and_agent_controls():
    assert subscription_environment(
        {
            "Path": "bin",
            "CODEX_HOME": "existing-auth-location",
            "HOME": "profile",
            "ANTHROPIC_API_KEY": "secret",
            "OPENAI_API_KEY": "secret",
            "CODEX_API_KEY": "secret",
            "OPENAI_BASE_URL": "route",
            "CODEX_THREAD_ID": "thread",
            "CODEX_MODEL": "other",
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "PYTHONPATH": "injection",
        }
    ) == {"Path": "bin", "CODEX_HOME": "existing-auth-location", "HOME": "profile"}


def test_codex_wrong_auth_never_generates():
    runner = Runner()
    runner.auth = "Logged in using an API key"
    with pytest.raises(ProviderError) as caught:
        CodexCliProvider(runner=runner).complete(CompletionRequest(prompt="x"))
    assert caught.value.kind == ProviderFailureKind.AUTH and len(runner.calls) == 1
    assert not Path(runner.calls[0][1]).exists()


def test_codex_schema_native_optionals_restore_absence_and_keep_original():
    runner = Runner()
    runner.text = '{"name": "a", "number": null}'
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name"],
        "properties": {"name": {"type": "string"}, "number": {"type": "integer"}},
    }
    result = CodexCliProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=schema))
    assert result.parsed == {"name": "a"}
    assert runner.schema["required"] == ["name", "number"]
    assert schema["required"] == ["name"]
    assert result.raw["final_text"] == runner.text
    assert result.raw["schema"] == schema
    assert result.raw["schema_variant"] == "strict-nullable-optionals.v1"


def test_codex_open_map_keeps_original_prompt_schema_and_validation():
    runner = Runner()
    runner.text = '{"state": {"A": 3}}'
    schema = {"type": "object", "required": ["state"], "properties": {"state": {"type": "object"}}}
    result = CodexCliProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=schema))
    assert result.parsed == {"state": {"A": 3}}
    assert runner.schema is None and "--output-schema" not in runner.calls[-1][0]
    assert result.raw["schema_variant"] == "prompt-only-original.v1"
    assert result.raw["native_schema_omission_reason"]
    assert json.dumps(schema, sort_keys=True) in runner.system


@pytest.mark.parametrize("value, conforms", [(None, True), ("retained", True), (42, False)])
def test_codex_completion_validates_original_nullable_type_list(value, conforms):
    runner = Runner()
    runner.text = json.dumps({"note": value})
    schema = {
        "type": "object", "additionalProperties": False, "required": ["note"],
        "properties": {"note": {"type": ["string", "null"]}},
    }
    result = CodexCliProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=schema))
    assert result.conforms is conforms
    assert result.parsed == ({"note": value} if conforms else None)
    assert runner.schema["properties"]["note"]["type"] == ["string", "null"]
    assert result.raw["final_text"] == runner.text


def test_codex_ambiguous_optional_restoration_refuses_and_retains_original_output():
    runner = Runner()
    runner.text = '{"choice": {"kind": "a", "note": null}}'
    branches = [
        {
            "type": "object", "additionalProperties": False, "required": ["kind"],
            "properties": {
                "kind": {"type": "string", "enum": ["a"]},
                "note": {"type": "string"},
            },
        },
        {
            "type": "object", "additionalProperties": False, "required": ["kind"],
            "properties": {
                "kind": {"type": "string", "enum": ["b"]},
                "note": {"type": ["string", "null"]},
            },
        },
    ]
    schema = {
        "type": "object", "additionalProperties": False, "required": ["choice"],
        "properties": {"choice": {"anyOf": branches}},
    }
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError, match="ambiguous anyOf") as caught:
        provider.complete(CompletionRequest(prompt="x", schema=schema))
    assert caught.value.kind == ProviderFailureKind.MALFORMED_RESPONSE
    assert provider.last_attempt["final_text"] == runner.text
    assert provider.last_attempt["stdout"] and provider.last_attempt["stderr"]
    assert provider.last_attempt["schema"] == schema
    assert len(runner.calls) == 3


def test_codex_invalid_original_required_field_does_not_conform():
    runner = Runner()
    runner.text = "{}"
    result = CodexCliProvider(runner=runner).complete(
        CompletionRequest(
            prompt="x",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            },
        )
    )
    assert result.schema_requested and result.parsed is None and not result.conforms


@pytest.mark.parametrize(
    "bad", ["missing_turn", "error", "tool", "malformed", "nonzero", "missing_file", "mismatch"]
)
def test_codex_failed_or_contaminated_output_never_succeeds(bad):
    runner = Runner()
    if bad == "missing_turn":
        runner.completed = False
    elif bad == "error":
        runner.extra_events = [{"type": "error", "message": "unavailable"}]
    elif bad == "tool":
        runner.extra_events = [{"type": "item.started", "item": {"type": "command_execution"}}]
    elif bad == "malformed":
        runner.stdout_override = "not JSONL"
    elif bad == "nonzero":
        runner.returncode = 1
    elif bad == "missing_file":
        runner.omit_final = True
    elif bad == "mismatch":
        runner.mismatch = True
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError):
        provider.complete(CompletionRequest(prompt="x"))
    assert len(runner.calls) == 3 and "stdout" in provider.last_attempt
    if bad != "missing_file":
        expected = "different" if bad == "mismatch" else runner.text
        assert provider.last_attempt["final_text"] == expected
        assert "final_bytes_base64" not in provider.last_attempt
    assert not Path(runner.calls[-1][1]).exists()


@pytest.fixture
def transport_notices():
    return [
        {"type": "error", "message": "Reconnecting... 2/5 (HTTP 503 Service Unavailable)"},
        {
            "type": "item.completed",
            "item": {
                "type": "error",
                "message": "Falling back from WebSockets to HTTPS transport. HTTP 503",
            },
        },
    ]


@pytest.mark.parametrize("indexes", [(0,), (1,), (0, 1)])
def test_codex_recovered_connection_setup_preserves_answer_usage_and_notices(
    transport_notices, indexes
):
    runner = Runner()
    runner.extra_events = [transport_notices[index] for index in indexes]
    result = CodexCliProvider(runner=runner).complete(CompletionRequest(prompt="x"))
    assert result.text == runner.text and result.usage.total == 112
    assert all(event in result.raw["events"] for event in runner.extra_events)
    assert all(event in [json.loads(line) for line in result.raw["stdout"].splitlines()]
               for event in runner.extra_events)
    assert len(runner.calls) == 3  # Login, version, and one native generation; no wrapper retry.


@pytest.mark.parametrize("bad", [
    "missing_turn", "duplicate_completion", "failed_turn", "nonzero", "missing_file",
    "mismatch", "missing_usage", "invalid_usage", "tool", "unknown_error", "unknown_item",
    "after_content", "after_completion", "duplicate_start", "missing_start", "multiple_threads",
])
def test_codex_transport_notices_do_not_excuse_failed_or_contaminated_output(
    transport_notices, bad
):
    runner = Runner()
    completed = {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 12}}
    message = {"type": "item.completed", "item": {"type": "agent_message", "text": runner.text}}
    events = [{"type": "turn.started"}, *transport_notices, message, completed]
    if bad == "missing_turn":
        events.pop()
    elif bad == "duplicate_completion":
        events.append(completed)
    elif bad == "failed_turn":
        events.insert(-1, {"type": "turn.failed"})
    elif bad == "nonzero":
        runner.returncode = 1
    elif bad == "missing_file":
        runner.omit_final = True
    elif bad == "mismatch":
        runner.mismatch = True
    elif bad == "missing_usage":
        completed.pop("usage")
    elif bad == "invalid_usage":
        completed["usage"]["input_tokens"] = -1
    elif bad == "tool":
        events.insert(-1, {"type": "item.started", "item": {"type": "command_execution"}})
    elif bad == "unknown_error":
        events.insert(1, {"type": "error", "message": "unavailable"})
    elif bad == "unknown_item":
        events.insert(1, {"type": "item.completed", "item": {"type": "error", "message": "failed"}})
    elif bad == "after_content":
        events = [{"type": "turn.started"}, message, *transport_notices, completed]
    elif bad == "after_completion":
        events = [{"type": "turn.started"}, message, completed, *transport_notices]
    elif bad == "duplicate_start":
        events.insert(2, {"type": "turn.started"})
    elif bad == "missing_start":
        events.pop(0)
    elif bad == "multiple_threads":
        events[:0] = [
            {"type": "thread.started", "thread_id": "first"},
            {"type": "thread.started", "thread_id": "second"},
        ]
    runner.stdout_override = "\n".join(json.dumps(event) for event in events)
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError):
        provider.complete(CompletionRequest(prompt="x"))
    assert provider.last_attempt["stdout"] == runner.stdout_override
    assert len(runner.calls) == 3


def test_codex_invalid_utf8_final_file_is_preserved_without_replacement_characters():
    runner = Runner()
    runner.final_bytes = b"prefix\xff\xfepartial-final"
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError) as caught:
        provider.complete(CompletionRequest(prompt="x"))
    assert caught.value.kind == ProviderFailureKind.MALFORMED_RESPONSE
    assert "final_text" not in provider.last_attempt
    assert base64.b64decode(provider.last_attempt["final_bytes_base64"]) == runner.final_bytes
    assert not Path(runner.calls[-1][1]).exists()


def test_codex_stdout_only_rate_limit_is_classified_and_preserved():
    runner = Runner()
    runner.returncode = 1
    runner.stderr = ""
    runner.stdout_override = json.dumps({"type": "error", "message": "rate_limit exceeded"})
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError) as caught:
        provider.complete(CompletionRequest(prompt="x"))
    assert caught.value.kind == ProviderFailureKind.RATE_LIMIT
    assert provider.last_attempt["stdout"] == runner.stdout_override
    assert provider.last_attempt["stderr"] == ""
    assert provider.last_attempt["final_text"] == runner.text
    assert len(runner.calls) == 3


@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": 100}, {"output_tokens": 12}])
def test_codex_completion_without_required_usage_cannot_report_zero_usage(usage):
    runner = Runner()
    completed = {"type": "turn.completed"}
    if usage is not None:
        completed["usage"] = usage
    runner.stdout_override = "\n".join(json.dumps(event) for event in [
        {"type": "item.completed", "item": {"type": "agent_message", "text": runner.text}},
        completed,
    ])
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError) as caught:
        provider.complete(CompletionRequest(prompt="x"))
    assert caught.value.kind == ProviderFailureKind.MALFORMED_RESPONSE
    assert "required input/output token usage" in str(caught.value)
    assert provider.last_attempt["stdout"] == runner.stdout_override
    assert provider.last_attempt["final_text"] == runner.text


def test_codex_timeout_retains_final_file_written_before_timeout():
    runner = Runner()
    runner.final_bytes = "unfinished final 火".encode()
    runner.timeout = True
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError) as caught:
        provider.complete(CompletionRequest(prompt="x"))
    assert caught.value.kind == ProviderFailureKind.TIMEOUT
    assert provider.last_attempt["final_text"] == "unfinished final 火"
    assert "final_bytes_base64" not in provider.last_attempt
    assert provider.last_attempt["stdout"] == "partial"
    assert not Path(runner.calls[-1][1]).exists()


def test_codex_timeout_preserves_partial_output_and_never_retries():
    runner = Runner()
    runner.timeout = True
    provider = CodexCliProvider(runner=runner)
    with pytest.raises(ProviderError) as caught:
        provider.complete(CompletionRequest(prompt="x"))
    assert caught.value.kind == ProviderFailureKind.TIMEOUT
    assert provider.last_attempt["stdout"] == "partial"
    assert provider.last_attempt["stderr"] == "timed out"
    assert len(runner.calls) == 3 and not Path(runner.calls[-1][1]).exists()


def test_codex_search_permission_only_allows_search():
    runner = Runner()
    runner.extra_events = [{"type": "item.completed", "item": {"type": "web_search"}}]
    result = CodexCliProvider(runner=runner).complete(
        CompletionRequest(prompt="x", allowed_tools=("WebSearch",))
    )
    assert result.raw["settings"]["web_search"] == "live"
    assert result.raw["settings"]["features.shell_tool"] is False


def test_codex_scoped_bridge_pins_database_without_exposing_it_to_completion(monkeypatch, tmp_path):
    runner = Runner()
    runner.extra_events = [
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "litharness",
                "tool": "litharness_command",
            },
        }
    ]
    database = str(tmp_path / "book.db")
    monkeypatch.setenv("LITHARNESS_DATABASE", database)
    result = CodexCliProvider(runner=runner).complete(
        CompletionRequest(
            prompt="Build this world.",
            allowed_tools=("Bash(litharness world declare:*)",),
        )
    )
    assert runner.bridge["environment"]["LITHARNESS_DATABASE"] == database
    assert "LITHARNESS_DATABASE" not in runner.calls[-1][2]
    assert result.raw["commands_jsonl"] == '{"test": "command trace"}\n'
    assert "litharness_command" in result.raw["system"]
    assert result.raw["settings"]["features.shell_tool"] is False
    assert result.raw["settings"]["mcp_servers.litharness.enabled_tools"] == ["litharness_command"]
    assert (
        result.raw["settings"]["mcp_servers.litharness.tools.litharness_command.approval_mode"]
        == "approve"
    )
    assert "mcp_servers.litharness.default_tools_approval_mode" not in result.raw["settings"]


@pytest.mark.parametrize("profile", ["architect.seed.v1", "architect.seed.v2", "architect.grow.v1"])
def test_codex_architect_cannot_succeed_without_a_command_receipt(profile):
    with pytest.raises(ValueError, match="without any successful"):
        _validate_bridge_activity([], "", profile)


def test_codex_optional_tool_diagnostic_can_complete_without_commands():
    _validate_bridge_activity([], "", "diagnostic.no-tools-requested.v1")


def test_codex_mcp_denial_cannot_be_hidden_by_a_successful_final_message():
    failed = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "status": "failed",
            "error": "approval required",
        },
    }
    with pytest.raises(ValueError, match="without a completed scoped command receipt"):
        _validate_bridge_activity([failed], "", "diagnostic.tools.v1")


def test_codex_architect_can_fix_domain_errors_after_successful_command_execution():
    success = {
        "phase": "result",
        "call": 1,
        "argv": ["python", "world", "vocabulary"],
        "returncode": 0,
        "stdout": "vocabulary",
    }
    domain_error = {
        "phase": "result",
        "call": 2,
        "argv": ["python", "world", "check"],
        "returncode": 1,
        "stdout": "contradiction",
    }
    failed = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "status": "failed",
            "result": {
                "isError": True,
                "content": [{"type": "text", "text": json.dumps(domain_error)}],
            },
        },
    }
    trace = "\n".join(json.dumps(row) for row in [success, domain_error])
    _validate_bridge_activity([failed], trace, "architect.seed.v1")
    failed["item"]["result"] = None
    failed["item"]["error"] = "approval required"
    with pytest.raises(ValueError, match="without a completed scoped command receipt"):
        _validate_bridge_activity([failed], trace, "architect.seed.v1")


@pytest.mark.parametrize(
    "arguments,error",
    [
        (
            {"invalid_tool_request": {"arguments": {"args": ["world", "vocabulary"]}}},
            "arguments must be an array of strings",
        ),
        (["world", "--help"], "command is outside this request's allowance"),
    ],
)
def test_codex_recovers_logged_argument_refusals_only_after_a_later_execution(arguments, error):
    refused = {
        "phase": "result", "call": 1, "arguments": arguments, "argv": None,
        "returncode": None, "stdout": "", "stderr": "",
        "error": error, "error_kind": "invalid_arguments",
    }
    later = {
        "phase": "result", "call": 2, "arguments": ["world", "vocabulary"],
        "argv": ["python", "-m", "litharness", "world", "vocabulary"],
        "returncode": 0, "stdout": "vocabulary", "stderr": "",
    }
    # Codex reports isError tool responses as failed items but preserves their text receipt.
    failed = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call", "status": "failed", "error": None,
            "result": {
                "content": [{"type": "text", "text": json.dumps(
                    {key: value for key, value in refused.items() if key != "phase"}
                )}],
                "structured_content": None,
            },
        },
    }
    trace = "\n".join(json.dumps(row) for row in [refused, later])
    _validate_bridge_activity([failed], trace, "architect.seed.v1")

    with pytest.raises(ValueError, match="invalid_arguments"):
        _validate_bridge_activity([failed], json.dumps(refused), "diagnostic.tools.v1")
    later["call"] = 0
    with pytest.raises(ValueError, match="invalid_arguments"):
        _validate_bridge_activity(
            [failed], "\n".join(json.dumps(row) for row in [later, refused]), "architect.seed.v1"
        )
    failed["item"]["result"]["content"][0]["text"] = json.dumps({**refused, "call": 99})
    with pytest.raises(ValueError, match="without a completed scoped command receipt"):
        _validate_bridge_activity([failed], trace, "architect.seed.v1")


@pytest.mark.parametrize("kind", ["call_budget", "execution", "timeout", "trace", "unknown"])
def test_codex_bridge_runtime_and_budget_failures_survive_other_successful_commands(kind):
    success = {
        "phase": "result", "call": 1, "argv": ["python", "world", "vocabulary"],
        "returncode": 0, "stdout": "vocabulary",
    }
    failure = {
        "phase": "result", "call": 2, "argv": None, "returncode": None,
        "stdout": "", "stderr": "", "error": "bridge failure", "error_kind": kind,
    }
    later = {**success, "call": 3}
    trace = "\n".join(json.dumps(row) for row in [success, failure, later])
    with pytest.raises(ValueError, match=kind):
        _validate_bridge_activity([], trace, "architect.seed.v1")


@pytest.mark.parametrize(
    "tools", [("Bash(litharness world accept:*)",), ("Bash(python:*)",), ("Read",)]
)
def test_codex_unsupported_allowance_refuses_before_auth(tools):
    runner = Runner()
    with pytest.raises(ProviderError) as caught:
        CodexCliProvider(runner=runner).complete(CompletionRequest(prompt="x", allowed_tools=tools))
    assert caught.value.kind == ProviderFailureKind.INVALID_REQUEST and not runner.calls


def test_codex_registry_opt_in_preserves_default_fake_and_billing_guard(monkeypatch):
    monkeypatch.delenv("LITHARNESS_FAKE_PAD_CHARS", raising=False)
    monkeypatch.delenv("LITHARNESS_PROVIDER", raising=False)
    assert isinstance(build_default_registry().provider, ClaudeCodeProvider)
    monkeypatch.setenv("LITHARNESS_PROVIDER", "codex")
    monkeypatch.setenv("LITHARNESS_CODEX_BINARY", "chosen-codex.exe")
    monkeypatch.setenv("LITHARNESS_CODEX_TRACE_DIR", "chosen-traces")
    registry = build_default_registry()
    assert isinstance(registry.provider, CodexCliProvider)
    assert registry.provider.binary == "chosen-codex.exe"
    assert registry.provider.trace_directory == Path("chosen-traces")
    with pytest.raises(BillingGuardViolation):
        registry.resolve()
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    assert isinstance(build_default_registry().provider, FakeProvider)


def test_codex_real_subprocess_preserves_large_unicode_stdin(tmp_path):
    text = "火 café `literal` $(literal) & %PATH%\n" * 4000
    result = subprocess_runner(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        timeout=30,
        cwd=str(tmp_path),
        env=subscription_environment(dict(os.environ)),
        stdin=text,
    )
    assert result.returncode == 0 and result.stdout == text


def test_codex_optional_trace_survives_failed_calls_without_overwrite(tmp_path):
    runner = Runner()
    runner.mismatch = True
    trace = tmp_path / "trace"
    provider = CodexCliProvider(runner=runner, trace_directory=trace)
    for _ in range(2):
        with pytest.raises(ProviderError):
            provider.complete(CompletionRequest(prompt="Retain this exact request."))
    records = list(trace.glob("attempt-*.json"))
    assert len(records) == 2
    for path in records:
        raw = json.loads(path.read_bytes())
        assert raw["prompt"] == "Retain this exact request."
        assert raw["final_text"] == "different"
        assert runner.text in [
            json.loads(line).get("item", {}).get("text") for line in raw["stdout"].splitlines()
        ]
        assert "does not match" in raw["failure"]
        assert raw["wall_ms"] >= 0
