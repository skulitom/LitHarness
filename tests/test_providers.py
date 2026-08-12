"""Provider adapter gates.

The envelopes in this file are **real captured output** from the installed tools
(`claude` 2.1.227, `codex-cli` 0.147.0, `ollama` 0.32.8), not invented shapes. Parsing is
therefore tested against what the CLIs actually emit, without spawning a process or
spending quota — which is the reason both CLI adapters take an injected runner.

Live round trips are opt-in via `LITHARNESS_LIVE_PROVIDERS=1`. They are skipped by default
because a suite that silently invokes a paid CLI on every run is a suite nobody can afford
to run often, and because CI cannot assume the tools are installed.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from litharness.providers.base import (
    CompletionRequest,
    ProviderError,
    ProviderUnavailable,
    Usage,
    parse_schema_payload,
    strip_fences,
)
from litharness.providers.cli import ClaudeCodeProvider, CodexProvider, CommandResult
from litharness.providers.fake import FakeProvider
from litharness.providers.ollama import OllamaProvider
from litharness.providers.registry import (
    ProviderRegistry,
    assert_no_billing_reachable,
    in_test_mode,
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok", "word"],
    "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
}

# --- real captured envelopes --------------------------------------------------------

#: `claude -p '...' --output-format json --model claude-haiku-4-5`, warm cache.
CLAUDE_ENVELOPE = {
    "is_error": False,
    "duration_api_ms": 3211,
    "num_turns": 1,
    "stop_reason": "end_turn",
    "session_id": "751d4edb-7806-45f9-9a0c-f01fd448949b",
    "total_cost_usd": 0.012934,
    "usage": {
        "input_tokens": 10,
        "cache_creation_input_tokens": 4982,
        "cache_read_input_tokens": 19057,
        "output_tokens": 112,
        "service_tier": "standard",
    },
    "modelUsage": {
        "claude-haiku-4-5": {
            "inputTokens": 10,
            "outputTokens": 112,
            "canonicalModel": "claude-haiku-4-5",
            "contextWindow": 200000,
            "provider": "firstParty",
        }
    },
    "permission_denials": [],
    "terminal_reason": "completed",
    "subtype": "success",
    "api_error_status": None,
    # Note the fence: `claude -p` has no native structured-output mode.
    "result": '```json\n{\n  "ok": true,\n  "word": "litharness"\n}\n```',
    "type": "result",
    "duration_ms": 3610,
}

#: `codex exec ... --json`. Four events per single turn; usage rides on turn.completed.
CODEX_EVENTS = [
    {"type": "thread.started"},
    {"type": "turn.started"},
    {"type": "item.completed"},
    {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 14887,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 21,
            "reasoning_output_tokens": 0,
        },
    },
]

#: `POST /api/chat` with a `format` schema. Unfenced, no preamble.
OLLAMA_ENVELOPE = {
    "model": "llama3.2:latest",
    "created_at": "2026-08-12T14:42:45.3336231Z",
    "message": {"role": "assistant", "content": '{"ok": true, "word": "litharness"}'},
    "done": True,
    "done_reason": "stop",
    "total_duration": 2814727200,
    "prompt_eval_count": 33,
    "eval_count": 14,
}


# --- helpers -----------------------------------------------------------------------


def claude_runner(envelope: dict) -> object:
    def run(argv: Sequence[str], *, timeout: float, cwd: str | None = None) -> CommandResult:
        run.argv = list(argv)  # type: ignore[attr-defined]
        return CommandResult(0, json.dumps(envelope))

    return run


def codex_runner(events: list[dict], answer: str) -> object:
    """Writes the `-o` file the way the real CLI does, then emits JSONL on stdout."""

    def run(argv: Sequence[str], *, timeout: float, cwd: str | None = None) -> CommandResult:
        run.argv = list(argv)  # type: ignore[attr-defined]
        target = Path(argv[argv.index("-o") + 1])
        target.write_text(answer, encoding="utf-8")
        return CommandResult(0, "\n".join(json.dumps(event) for event in events))

    return run


def ollama_transport(envelope: dict) -> object:
    def transport(url: str, body: dict, timeout: float) -> dict:
        transport.body = body  # type: ignore[attr-defined]
        transport.url = url  # type: ignore[attr-defined]
        return envelope

    return transport


# --- base helpers ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('  {"a": 1}  ', '{"a": 1}'),
        ("no fence here", "no fence here"),
    ],
)
def test_fence_stripping(raw: str, expected: str) -> None:
    assert strip_fences(raw) == expected


def test_schema_parse_returns_none_rather_than_raising() -> None:
    """A malformed answer is a shape-gate result, not a crash (§4.2 ladder step 1)."""
    assert parse_schema_payload("not json at all", SCHEMA) is None
    assert parse_schema_payload('{"ok": true}', SCHEMA) is None, "missing required key"
    assert parse_schema_payload('{"ok": "yes", "word": "x"}', SCHEMA) is None, "wrong type"
    assert parse_schema_payload('["a"]', SCHEMA) is None, "not an object"
    assert parse_schema_payload('{"ok": true, "word": "x"}', SCHEMA) == {"ok": True, "word": "x"}


def test_a_boolean_does_not_satisfy_an_integer_schema() -> None:
    """`bool` is an `int` subclass in Python; a schema asking for integer means integer."""
    schema = {"required": ["n"], "properties": {"n": {"type": "integer"}}}
    assert parse_schema_payload('{"n": true}', schema) is None
    assert parse_schema_payload('{"n": 3}', schema) == {"n": 3}


def test_usage_separates_full_price_input_from_cache_reads() -> None:
    usage = Usage(input_tokens=10, cache_read_tokens=19057, cache_write_tokens=4982)
    assert usage.billable_input == 4992, "cache reads must not count as full-price input"
    assert usage.total == 24049


# --- claude_code -------------------------------------------------------------------


def test_claude_adapter_parses_the_real_envelope() -> None:
    provider = ClaudeCodeProvider(runner=claude_runner(CLAUDE_ENVELOPE))
    result = provider.complete(CompletionRequest(prompt="x", schema=SCHEMA))

    assert result.text == '{\n  "ok": true,\n  "word": "litharness"\n}', "fence not stripped"
    assert result.parsed == {"ok": True, "word": "litharness"}
    assert result.conforms
    assert result.model == "claude-haiku-4-5"
    assert result.cost_usd == pytest.approx(0.012934)
    assert result.usage.cache_read_tokens == 19057
    assert result.usage.cache_write_tokens == 4982
    assert result.invocations == 1


def test_claude_argv_carries_every_mandatory_flag() -> None:
    runner = claude_runner(CLAUDE_ENVELOPE)
    ClaudeCodeProvider(runner=runner).complete(CompletionRequest(prompt="x"))
    argv = " ".join(runner.argv)  # type: ignore[attr-defined]
    assert "--output-format json" in argv
    assert "--allowed-tools" in argv, "a tool-enabled agent could mutate canon directly"
    assert "--strict-mcp-config" in argv, "inherited MCP servers break reproducibility"
    assert '{"mcpServers":{}}' in argv
    assert "--no-session-persistence" in argv


def test_claude_reports_an_error_envelope_as_a_provider_error() -> None:
    broken = {**CLAUDE_ENVELOPE, "is_error": True, "api_error_status": 529, "result": "overloaded"}
    provider = ClaudeCodeProvider(runner=claude_runner(broken))
    with pytest.raises(ProviderError, match="529"):
        provider.complete(CompletionRequest(prompt="x"))


def test_claude_unparseable_stdout_is_a_provider_error() -> None:
    def run(argv, *, timeout, cwd=None):
        return CommandResult(1, "not json")

    with pytest.raises(ProviderError, match="unparseable"):
        ClaudeCodeProvider(runner=run).complete(CompletionRequest(prompt="x"))


def test_claude_timeout_becomes_a_provider_error() -> None:
    def run(argv, *, timeout, cwd=None):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)

    with pytest.raises(ProviderError, match="timed out"):
        ClaudeCodeProvider(runner=run).complete(
            CompletionRequest(prompt="x", timeout_seconds=1.0)
        )


def test_claude_schema_request_adds_a_json_only_instruction() -> None:
    runner = claude_runner(CLAUDE_ENVELOPE)
    ClaudeCodeProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=SCHEMA))
    argv = runner.argv  # type: ignore[attr-defined]
    system = argv[argv.index("--append-system-prompt") + 1]
    assert "no code fence" in system, "the CLI has no native structured-output mode"


# --- codex -------------------------------------------------------------------------


def test_codex_adapter_parses_events_and_the_answer_file() -> None:
    runner = codex_runner(CODEX_EVENTS, '{"ok":true,"word":"litharness"}')
    result = CodexProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=SCHEMA))

    assert result.parsed == {"ok": True, "word": "litharness"}
    assert result.usage.input_tokens == 14887
    assert result.usage.cache_read_tokens == 0, "codex does not cache; measured across repeats"
    assert result.usage.reasoning_tokens == 0
    assert result.cost_usd is None, "ChatGPT-account auth is quota, not dollars"


def test_codex_argv_carries_the_schema_and_repo_check_flags() -> None:
    runner = codex_runner(CODEX_EVENTS, '{"ok":true,"word":"x"}')
    CodexProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=SCHEMA))
    argv = runner.argv  # type: ignore[attr-defined]
    assert "--skip-git-repo-check" in argv, "the LitHarness tree is not a git repository"
    assert "--output-schema" in argv, "native schema enforcement is codex's advantage"
    assert "mcp_servers={}" in argv
    schema_path = Path(argv[argv.index("--output-schema") + 1])
    assert schema_path.name == "schema.json"


def test_codex_reasoning_tokens_are_counted() -> None:
    events = [
        *CODEX_EVENTS[:-1],
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 14887,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 21,
                "reasoning_output_tokens": 4096,
            },
        },
    ]
    result = CodexProvider(runner=codex_runner(events, "answer")).complete(
        CompletionRequest(prompt="x")
    )
    assert result.usage.reasoning_tokens == 4096
    assert result.usage.total >= 4096, "reasoning must reach the budget governor"


def test_codex_empty_answer_is_an_error_with_a_diagnostic() -> None:
    """The 0.107.0 failure mode: exit 0, empty -o file, error only in the event stream."""
    events = [{"type": "error", "detail": "The 'gpt-5.6-sol' model requires a newer version"}]
    with pytest.raises(ProviderError, match="newer version"):
        CodexProvider(runner=codex_runner(events, "")).complete(CompletionRequest(prompt="x"))


# --- ollama ------------------------------------------------------------------------


def test_ollama_adapter_parses_the_real_envelope() -> None:
    transport = ollama_transport(OLLAMA_ENVELOPE)
    result = OllamaProvider(transport=transport).complete(
        CompletionRequest(prompt="x", schema=SCHEMA)
    )
    assert result.parsed == {"ok": True, "word": "litharness"}
    assert result.usage.input_tokens == 33
    assert result.usage.output_tokens == 14
    assert result.cost_usd == 0.0, "hardware time only"
    assert result.model == "llama3.2:latest"


def test_ollama_sends_the_schema_as_the_format_field_and_pins_determinism() -> None:
    transport = ollama_transport(OLLAMA_ENVELOPE)
    OllamaProvider(transport=transport, seed=7).complete(
        CompletionRequest(prompt="x", schema=SCHEMA, system="be terse")
    )
    body = transport.body  # type: ignore[attr-defined]
    assert body["format"] == SCHEMA, "native JSON-Schema output is the whole point"
    assert body["stream"] is False
    assert body["options"]["temperature"] == 0.0
    assert body["options"]["seed"] == 7
    assert [message["role"] for message in body["messages"]] == ["system", "user"]


def test_ollama_error_field_becomes_a_provider_error() -> None:
    transport = ollama_transport({"error": "model 'nope' not found"})
    with pytest.raises(ProviderError, match="not found"):
        OllamaProvider(transport=transport).complete(CompletionRequest(prompt="x"))


def test_ollama_unreachable_daemon_is_a_provider_error() -> None:
    def transport(url, body, timeout):
        raise OSError("connection refused")

    with pytest.raises(ProviderError, match="unreachable"):
        OllamaProvider(transport=transport).complete(CompletionRequest(prompt="x"))


# --- fake --------------------------------------------------------------------------


def test_fake_is_deterministic_and_free() -> None:
    provider = FakeProvider()
    first = provider.complete(CompletionRequest(prompt="draft"))
    second = provider.complete(CompletionRequest(prompt="draft"))
    assert first.text == second.text
    assert provider.bills is False
    assert first.cost_usd == 0.0


def test_fake_synthesises_a_conforming_object_for_any_schema() -> None:
    schema = {
        "required": ["name", "count", "flag", "items", "kind"],
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
            "flag": {"type": "boolean"},
            "items": {"type": "array"},
            "kind": {"enum": ["a", "b"]},
        },
    }
    result = FakeProvider().complete(CompletionRequest(prompt="x", schema=schema))
    assert result.conforms and result.parsed is not None
    assert result.parsed["kind"] == "a"
    assert isinstance(result.parsed["count"], int)


# --- the shared conformance suite --------------------------------------------------

CONFORMANCE_CASES = [
    ("fake", lambda: FakeProvider()),
    ("claude_code", lambda: ClaudeCodeProvider(runner=claude_runner(CLAUDE_ENVELOPE))),
    (
        "codex",
        lambda: CodexProvider(runner=codex_runner(CODEX_EVENTS, '{"ok":true,"word":"c"}')),
    ),
    ("ollama", lambda: OllamaProvider(transport=ollama_transport(OLLAMA_ENVELOPE))),
]


@pytest.mark.parametrize(
    "name,build", CONFORMANCE_CASES, ids=[case[0] for case in CONFORMANCE_CASES]
)
def test_every_adapter_satisfies_the_same_contract(name: str, build) -> None:
    """Stage 0's exit clause: each configured adapter passes a conformance suite."""
    provider = build()
    assert provider.name == name
    assert isinstance(provider.bills, bool)

    result = provider.complete(CompletionRequest(prompt="Say something.", schema=SCHEMA))
    assert result.provider == name
    assert result.model, "a result must name the model that produced it, for provenance"
    assert result.schema_requested is True
    assert result.conforms, f"{name} did not satisfy the schema"
    assert result.invocations == 1
    assert result.usage.total >= 0
    assert isinstance(result.raw, dict) and result.raw, "raw envelope is the provenance record"

    free = provider.complete(CompletionRequest(prompt="Say something."))
    assert free.schema_requested is False
    assert free.conforms, "no schema requested means conformance is vacuously true"


@pytest.mark.parametrize(
    "name,build", CONFORMANCE_CASES, ids=[case[0] for case in CONFORMANCE_CASES]
)
def test_every_adapter_reports_health_without_raising(name: str, build) -> None:
    assert build().health() in {True, False}


# --- registry ----------------------------------------------------------------------


class StubProvider:
    def __init__(self, name: str, *, bills: bool, healthy: bool = True, raises: bool = False):
        self.name = name
        self.bills = bills
        self._healthy = healthy
        self._raises = raises
        self.probes = 0

    def health(self) -> bool:
        self.probes += 1
        if self._raises:
            raise RuntimeError("probe blew up")
        return self._healthy

    def complete(self, request: CompletionRequest):
        return FakeProvider(name=self.name).complete(request)


def registry(*providers, order=None, environ=None, cheap_order=()) -> ProviderRegistry:
    return ProviderRegistry(
        providers=list(providers),
        order=order or [provider.name for provider in providers],
        cheap_order=cheap_order,
        environ=environ if environ is not None else {},
    )


def test_resolution_follows_the_configured_order() -> None:
    reg = registry(
        StubProvider("claude_code", bills=True),
        StubProvider("codex", bills=True),
        StubProvider("ollama", bills=False),
    )
    provider, resolution = reg.resolve()
    assert provider.name == "claude_code"
    assert not resolution.is_fallback


def test_an_unhealthy_provider_is_skipped_and_the_fallback_is_recorded() -> None:
    """§5 rule 4: a switch changes provenance, so it must not be silent."""
    reg = registry(
        StubProvider("claude_code", bills=True, healthy=False),
        StubProvider("codex", bills=True),
    )
    provider, resolution = reg.resolve()
    assert provider.name == "codex"
    assert resolution.fell_back_from == ("claude_code",)
    assert resolution.is_fallback


def test_a_probe_that_raises_counts_as_unhealthy() -> None:
    reg = registry(
        StubProvider("claude_code", bills=True, raises=True),
        StubProvider("ollama", bills=False),
    )
    assert reg.resolve()[0].name == "ollama"


def test_no_healthy_provider_raises_rather_than_returning_none() -> None:
    reg = registry(StubProvider("ollama", bills=False, healthy=False))
    with pytest.raises(ProviderUnavailable, match="no healthy provider"):
        reg.resolve()


def test_health_is_probed_once_per_tick_and_reset_clears_it() -> None:
    stub = StubProvider("ollama", bills=False)
    reg = registry(stub)
    reg.resolve()
    reg.resolve()
    assert stub.probes == 1, "a probe per call would make every tick pay a round trip"
    reg.reset_health()
    reg.resolve()
    assert stub.probes == 2


def test_cheap_call_classes_prefer_a_non_billing_provider_in_production() -> None:
    """§3: the per-invocation harness tax dwarfs a small mechanical payload."""
    reg = registry(
        StubProvider("claude_code", bills=True),
        StubProvider("ollama", bills=False),
        order=["claude_code", "ollama"],
        cheap_order=["ollama", "claude_code"],
    )
    assert reg.resolve("generation")[0].name == "claude_code"
    assert reg.resolve("extraction")[0].name == "ollama"
    assert reg.resolve("mechanical")[0].name == "ollama"


# --- the test-mode guard -----------------------------------------------------------


def test_test_mode_excludes_every_billing_provider() -> None:
    reg = registry(
        StubProvider("claude_code", bills=True),
        StubProvider("codex", bills=True),
        StubProvider("ollama", bills=False),
        environ={"LITHARNESS_ENV": "test"},
    )
    assert reg.test_mode
    assert [p.name for p in reg.candidates()] == ["ollama"]
    assert reg.resolve()[0].name == "ollama"
    assert_no_billing_reachable(reg)


def test_the_guard_holds_even_when_the_order_names_only_paid_providers() -> None:
    """The guard must not depend on `order` being configured correctly."""
    reg = registry(
        StubProvider("claude_code", bills=True),
        StubProvider("codex", bills=True),
        order=["claude_code", "codex"],
        environ={"LITHARNESS_ENV": "test"},
    )
    with pytest.raises(ProviderUnavailable, match="test mode"):
        reg.resolve()
    assert_no_billing_reachable(reg)


def test_the_guard_assertion_fails_loudly_if_a_paid_provider_becomes_reachable() -> None:
    reg = registry(
        StubProvider("claude_code", bills=True),
        StubProvider("ollama", bills=False),
        environ={},  # not test mode
    )
    with pytest.raises(AssertionError, match="not 'test'"):
        assert_no_billing_reachable(reg)


def test_in_test_mode_reads_the_environment_case_insensitively() -> None:
    assert in_test_mode({"LITHARNESS_ENV": "TEST"})
    assert in_test_mode({"LITHARNESS_ENV": " test "})
    assert not in_test_mode({"LITHARNESS_ENV": "production"})
    assert not in_test_mode({})


def test_duplicate_provider_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate provider names"):
        registry(StubProvider("ollama", bills=False), StubProvider("ollama", bills=False))


# --- opt-in live round trips -------------------------------------------------------

live = pytest.mark.skipif(
    os.environ.get("LITHARNESS_LIVE_PROVIDERS") != "1",
    reason="set LITHARNESS_LIVE_PROVIDERS=1 to exercise the installed tools (spends quota)",
)


@live
def test_live_ollama_round_trip() -> None:
    provider = OllamaProvider(model="llama3.2:latest")
    assert provider.health()
    result = provider.complete(
        CompletionRequest(prompt="Return ok=true and word=litharness", schema=SCHEMA)
    )
    assert result.parsed == {"ok": True, "word": "litharness"}


@live
def test_live_codex_round_trip() -> None:
    provider = CodexProvider()
    result = provider.complete(
        CompletionRequest(prompt="Return ok=true and word=litharness", schema=SCHEMA)
    )
    assert result.conforms
    assert result.usage.input_tokens > 0


@live
def test_live_claude_round_trip() -> None:
    provider = ClaudeCodeProvider(model="claude-haiku-4-5")
    result = provider.complete(
        CompletionRequest(prompt="Return ok=true and word=litharness", schema=SCHEMA)
    )
    assert result.conforms
    assert result.cost_usd is not None


# --- the suite-wide guard ----------------------------------------------------------


def test_the_whole_suite_runs_with_the_billing_guard_active() -> None:
    """`tests/conftest.py` sets LITHARNESS_ENV=test at import.

    Asserted rather than assumed: this is the property Stage 0's exit criterion names, and
    a guard nobody checks is a guard that silently stops applying the day someone changes
    the conftest.
    """
    assert in_test_mode(), "LITHARNESS_ENV=test is not active for this run"

    real = ProviderRegistry(
        providers=[ClaudeCodeProvider(), CodexProvider(), OllamaProvider(), FakeProvider()],
        order=["claude_code", "codex", "ollama", "fake"],
        cheap_order=["ollama", "fake"],
    )
    assert [provider.name for provider in real.candidates()] == ["ollama", "fake"]
    assert_no_billing_reachable(real)
