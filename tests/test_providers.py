"""Provider adapter gates, for the pinned world: `claude_code` plus the deterministic fake.

The envelope in this file is **real captured output** from the installed tool
(`claude` 2.1.227), not an invented shape. Parsing is therefore tested against what the
CLI actually emits, without spawning a process or spending quota — which is the reason the
adapter takes an injected runner.

The live round trip is opt-in via `LITHARNESS_LIVE_PROVIDERS=1`. It is skipped by default
because a suite that silently invokes a paid CLI on every run is a suite nobody can afford
to run often, and because CI cannot assume the tool is installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Sequence

import pytest

from litharness.providers import build_default_registry
from litharness.providers.base import (
    BlockedProviderError,
    CompletionRequest,
    ProviderError,
    ProviderFailureKind,
    ProviderUnavailable,
    RetryableProviderError,
    Sampler,
    Usage,
    classify_provider_failure,
    parse_schema_payload,
    provider_error,
    strip_fences,
)
from litharness.providers.cli import ClaudeCodeProvider, CommandResult
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import (
    BillingGuardViolation,
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

# --- the real captured envelope -----------------------------------------------------

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


# --- helpers -----------------------------------------------------------------------


def claude_runner(envelope: dict) -> object:
    def run(
        argv: Sequence[str], *, timeout: float, cwd: str | None = None, stdin: str | None = None
    ) -> CommandResult:
        run.argv = list(argv)  # type: ignore[attr-defined]
        run.stdin = stdin  # type: ignore[attr-defined]
        return CommandResult(0, json.dumps(envelope))

    return run


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


def test_a_samplers_opinions_merge_over_defaults_field_by_field() -> None:
    """Per-request decoding, and *partial* per-request decoding.

    Field-by-field merging is what lets a request raise the temperature without also
    having to restate the seed, and lets a field left `None` keep the adapter's. The
    retired Ollama transport tests used to pin this at the wire; `Sampler` is kept (it
    feeds `draft_sampler` and the policy digest), so the merge semantics are pinned here
    directly, with no transport.
    """
    merged = Sampler(temperature=0.7, top_p=0.9, repeat_penalty=1.05).merged_over(
        temperature=0.0, seed=7
    )
    assert merged == {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.05, "seed": 7}


def test_a_sampler_field_left_none_stays_absent_rather_than_becoming_a_default() -> None:
    """`None` means "no opinion", and no layer may translate that into a number.

    The failure this refuses is silent and one-directional: a `None` serialised as `0`
    makes every call greedy, which looks like working software and is the exact setting
    the measurement in `domain/generation.py` says makes a retry return the same answer
    three times.
    """
    merged = Sampler(temperature=0.7).merged_over(seed=7, top_p=None)
    assert merged == {"temperature": 0.7, "seed": 7}
    assert "top_p" not in merged
    assert "repeat_penalty" not in merged


@pytest.mark.parametrize(
    "message,status,expected",
    [
        ("too many requests", 429, ProviderFailureKind.RATE_LIMIT),
        ("overloaded", 529, ProviderFailureKind.OVERLOADED),
        ("prompt exceeds the context window", 400, ProviderFailureKind.CONTEXT_OVERFLOW),
        ("invalid API key", 401, ProviderFailureKind.AUTH),
        ("bad parameter", 422, ProviderFailureKind.INVALID_REQUEST),
        ("upstream exploded", 503, ProviderFailureKind.SERVER_ERROR),
    ],
)
def test_provider_failures_are_classified_for_recovery(
    message: str, status: int, expected: ProviderFailureKind
) -> None:
    assert classify_provider_failure(message, status=status) is expected


def test_provider_error_factory_selects_recovery_semantics_and_keeps_context() -> None:
    retryable = provider_error(
        "quota is momentarily busy",
        kind=ProviderFailureKind.RATE_LIMIT,
        status=429,
        request_id="req-1",
        retry_after_seconds=3.0,
    )
    blocked = provider_error(
        "prompt exceeds the context window",
        status=400,
        raw="provider diagnostic",
    )

    assert isinstance(retryable, RetryableProviderError)
    assert retryable.diagnostic() == {
        "classification": "rate_limit",
        "status": 429,
        "request_id": "req-1",
        "retry_after_seconds": 3.0,
    }
    assert isinstance(blocked, BlockedProviderError)
    assert blocked.kind is ProviderFailureKind.CONTEXT_OVERFLOW
    assert blocked.raw == "provider diagnostic"


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
    with pytest.raises(RetryableProviderError, match="529") as raised:
        provider.complete(CompletionRequest(prompt="x"))
    assert raised.value.kind is ProviderFailureKind.OVERLOADED
    assert raised.value.status == 529


def test_claude_unparseable_stdout_is_a_provider_error() -> None:
    def run(argv, *, timeout, cwd=None, stdin=None):
        return CommandResult(1, "not json")

    with pytest.raises(ProviderError, match="unparseable"):
        ClaudeCodeProvider(runner=run).complete(CompletionRequest(prompt="x"))


def test_claude_timeout_becomes_a_provider_error() -> None:
    def run(argv, *, timeout, cwd=None, stdin=None):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)

    with pytest.raises(RetryableProviderError, match="timed out") as raised:
        ClaudeCodeProvider(runner=run).complete(CompletionRequest(prompt="x", timeout_seconds=1.0))
    assert raised.value.kind is ProviderFailureKind.TIMEOUT


def test_claude_schema_request_adds_a_json_only_instruction() -> None:
    runner = claude_runner(CLAUDE_ENVELOPE)
    ClaudeCodeProvider(runner=runner).complete(CompletionRequest(prompt="x", schema=SCHEMA))
    argv = runner.argv  # type: ignore[attr-defined]
    system = argv[argv.index("--append-system-prompt") + 1]
    assert "no code fence" in system, "the CLI has no native structured-output mode"


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


def test_fake_consumes_a_scripted_sequence_of_results_and_failures() -> None:
    provider = FakeProvider(
        responses=[
            provider_error("busy", kind=ProviderFailureKind.OVERLOADED),
            "recovered answer",
        ]
    )
    with pytest.raises(RetryableProviderError, match="busy"):
        provider.complete(CompletionRequest(prompt="first"))

    result = provider.complete(CompletionRequest(prompt="second"))
    assert result.text == "recovered answer"
    assert provider.calls == 2
    with pytest.raises(ProviderError, match="no scripted fake responses"):
        provider.complete(CompletionRequest(prompt="third"))


# --- the shared conformance suite --------------------------------------------------

CONFORMANCE_CASES = [
    ("fake", lambda: FakeProvider()),
    ("claude_code", lambda: ClaudeCodeProvider(runner=claude_runner(CLAUDE_ENVELOPE))),
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
        self.healthy = healthy
        self._raises = raises
        self.probes = 0

    def health(self) -> bool:
        self.probes += 1
        if self._raises:
            raise RuntimeError("probe blew up")
        return self.healthy

    def complete(self, request: CompletionRequest):
        return FakeProvider(name=self.name).complete(request)


def registry(provider, environ=None) -> ProviderRegistry:
    return ProviderRegistry(provider, environ=environ if environ is not None else {})


def test_resolving_returns_the_pinned_provider_with_no_fallback() -> None:
    """One provider, healthy: it serves, and the resolution records no switch — the
    `fell_back_from` slot is schema'd vocabulary that stays empty going forward."""
    stub = StubProvider("pinned", bills=False)
    provider, resolution = registry(stub).resolve()
    assert provider is stub
    assert resolution.provider == "pinned"
    assert resolution.fell_back_from == ()
    assert not resolution.is_fallback


def test_an_unhealthy_provider_raises_rather_than_degrading() -> None:
    """§1a.5: a silent mid-book fallback to a weaker model is a quality defect, not
    resilience. With one pinned provider an outage is `ProviderUnavailable` — the
    conductor requeues or parks the unit, and the book waits rather than degrades."""
    reg = registry(StubProvider("pinned", bills=False, healthy=False))
    with pytest.raises(ProviderUnavailable, match="unhealthy"):
        reg.resolve()


def test_a_probe_that_raises_counts_as_unhealthy() -> None:
    reg = registry(StubProvider("pinned", bills=False, raises=True))
    with pytest.raises(ProviderUnavailable):
        reg.resolve()


def test_a_negative_verdict_heals_after_reset() -> None:
    """One failed probe must not kill the provider for the life of the process — the
    dead-forever bug §16 recorded. `reset_health` clears the negative verdict, so the
    next tick re-probes and a recovered provider serves again."""
    flaky = StubProvider("pinned", bills=False, healthy=False)
    reg = registry(flaky)

    with pytest.raises(ProviderUnavailable):
        reg.resolve()
    flaky.healthy = True
    with pytest.raises(ProviderUnavailable):
        reg.resolve()
    assert flaky.probes == 1, "a verdict must be cached until the next reset, not re-probed"

    reg.reset_health()
    provider, _ = reg.resolve()
    assert provider is flaky
    assert flaky.probes == 2


def test_a_positive_verdict_survives_reset_because_the_probe_is_billed_work() -> None:
    """The other half of the asymmetry. The pinned provider's probe is a real, metered
    round trip that no budget ceiling sees (§56.2), so a positive verdict, once bought,
    is kept for the life of the process — the per-tick reset must not re-pay it."""
    stub = StubProvider("pinned", bills=False)
    reg = registry(stub)

    reg.resolve()
    for _ in range(5):
        reg.reset_health()
        reg.resolve()

    assert stub.probes == 1, "a reset re-paid a probe the process had already bought"


# --- the test-mode guard -----------------------------------------------------------


def test_the_billing_guard_raises_in_test_mode_before_any_probe() -> None:
    """§5 rule 2, preserved by refusal instead of filtering. The plural registry filtered
    billing providers and quietly proceeded on what remained; with one provider there is
    nothing to substitute, and never substituting silently is the recorded lesson — so a
    test run that reaches for a billing provider gets a dedicated, loud error. Before the
    probe, because the probe is itself a billed call."""
    paid = StubProvider("paid", bills=True)
    reg = registry(paid, environ={"LITHARNESS_ENV": "test"})

    with pytest.raises(BillingGuardViolation, match="LITHARNESS_ENV"):
        reg.resolve()
    assert paid.probes == 0, "the guard must refuse before paying for the health probe"

    with pytest.raises(BillingGuardViolation):
        reg.complete(CompletionRequest(prompt="x"))


def test_the_guard_assertion_fails_loudly_outside_test_mode() -> None:
    reg = registry(StubProvider("paid", bills=True), environ={})  # not test mode
    with pytest.raises(AssertionError, match="not 'test'"):
        assert_no_billing_reachable(reg)


def test_the_guard_assertion_asserts_the_refusal() -> None:
    """`assert_no_billing_reachable` now proves the guard by the raise: a registry
    holding a billing provider must refuse to resolve it in test mode, and a non-billing
    provider has nothing to refuse."""
    paid = registry(StubProvider("paid", bills=True), environ={"LITHARNESS_ENV": "test"})
    assert_no_billing_reachable(paid)

    free = registry(StubProvider("free", bills=False), environ={"LITHARNESS_ENV": "test"})
    assert_no_billing_reachable(free)


def test_in_test_mode_reads_the_environment_case_insensitively() -> None:
    assert in_test_mode({"LITHARNESS_ENV": "TEST"})
    assert in_test_mode({"LITHARNESS_ENV": " test "})
    assert not in_test_mode({"LITHARNESS_ENV": "production"})
    assert not in_test_mode({})


# --- the default registry ----------------------------------------------------------


def test_the_default_registry_pins_claude_code(monkeypatch) -> None:
    monkeypatch.delenv("LITHARNESS_FAKE_PAD_CHARS", raising=False)
    reg = build_default_registry()
    assert isinstance(reg.provider, ClaudeCodeProvider)
    assert reg.provider.name == "claude_code"


def test_an_outage_is_an_outage_and_not_a_writer_who_cannot_write(monkeypatch) -> None:
    """**Measured when the local Ollama daemon stopped mid-session, and it destroyed a book.**

    The fake used to backstop generation. A backstop that cannot clear the gate it feeds is
    not one: its answer is ~80 characters against a 200-char floor, so with every real
    provider down, six beats each generated canned text three times, failed the shape gate
    three times, spent their attempt budgets and **poisoned** — five exceptions and six
    unrevivable job ids, for an outage.

    The outage has to surface as an outage. `ProviderUnavailable` is what the Conductor
    already handles correctly: the attempt is given back and the unit requeues, so the outage
    costs time rather than the work. §19.1's rule, fourth instance — and this one hid best,
    because nothing looked refused. A healthy provider answered; it simply could not write.
    In the pinned world the same lesson reads: the default registry never holds the fake.
    """
    monkeypatch.delenv("LITHARNESS_FAKE_PAD_CHARS", raising=False)
    assert not isinstance(build_default_registry().provider, FakeProvider)

    down = registry(StubProvider("pinned", bills=False, healthy=False))
    with pytest.raises(ProviderUnavailable):
        down.resolve("generation")


def test_padding_the_fake_is_how_you_ask_for_a_model_free_loop(monkeypatch) -> None:
    """Setting the pad is the statement "I am deliberately running on the fake", so it is
    also what selects the fake. The scaffolding stays reachable; what it stops doing is
    arriving uninvited during an outage."""
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")

    reg = build_default_registry()
    assert isinstance(reg.provider, FakeProvider)
    assert reg.provider.pad_to_chars == 400


# --- opt-in live round trips -------------------------------------------------------

live = pytest.mark.skipif(
    os.environ.get("LITHARNESS_LIVE_PROVIDERS") != "1",
    reason="set LITHARNESS_LIVE_PROVIDERS=1 to exercise the installed tools (spends quota)",
)


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
    the conftest. The pinned provider bills, so the registry must refuse to resolve it —
    the guard is now the raise, not a filtered candidate list.
    """
    assert in_test_mode(), "LITHARNESS_ENV=test is not active for this run"

    real = ProviderRegistry(ClaudeCodeProvider())
    with pytest.raises(BillingGuardViolation):
        real.resolve()
    assert_no_billing_reachable(real)


# --- the one part of the adapter a fake runner cannot exercise ----------------------


def test_the_real_runner_decodes_utf8_rather_than_the_host_locale() -> None:
    """The bug every other test in this file is structurally unable to see.

    `subprocess_runner` is the seam the injected `Runner` replaces, so the whole adapter
    suite runs without ever decoding a real pipe. It shipped with `text=True` and no
    `encoding`, which decodes with `locale.getpreferredencoding()` — `cp1252` on a Windows
    host. Measured on a real `claude -p` draft: the em dash the generator wrote arrived as
    `â€”`, the three UTF-8 bytes of U+2014 read one at a time.

    **The em dash is not incidental.** `extraction.STATUS_PATTERN` matches on U+2014
    exactly, so a mangled dash means the status line does not parse and `extract_state`
    reads nothing — every scene a CLI provider drafts would establish no state, silently,
    which is the exact failure `extraction.py` warns about. The assertion below therefore
    checks the parser rather than the codepoint: a test that only compared strings would
    pass on a repair that fixed the dash and broke the pipe.
    """
    from litharness.domain.extraction import STATUS_PATTERN
    from litharness.providers.cli import subprocess_runner

    line = "[STATUS] rook — Level 1 | HP 12/18 | MP 4/4 | Gold 25"
    result = subprocess_runner(
        [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.reconfigure(encoding='utf-8'); print({line!r})",
        ],
        timeout=60.0,
    )

    assert result.returncode == 0, result.stderr
    assert "—" in result.stdout, f"em dash did not survive the pipe: {result.stdout!r}"
    assert STATUS_PATTERN.search(result.stdout), (
        "a status line written by a CLI provider does not parse; extraction would read "
        f"nothing from every scene it drafts. Got {result.stdout!r}"
    )


def test_the_recorded_model_is_the_one_that_wrote_the_prose() -> None:
    """`claude -p` bills more than one model per call, and taking the first named the wrong one.

    Measured envelope shape from a real call requesting `claude-opus-5`: `modelUsage` came
    back keyed `['claude-haiku-4-5-20251001', 'claude-opus-5']` — Opus wrote the prose, Haiku
    is the CLI's own overhead — and `next(iter(...))` reported Haiku. That value lands on the
    `PolicyDecision` of every accepted scene, so a book drafted by Opus was attributable to a
    model that did not write a word of it. §19's attribution chain is what that breaks, and a
    provenance record which is confidently wrong is worse than one that is missing.
    """
    envelope = dict(CLAUDE_ENVELOPE)
    envelope["modelUsage"] = {
        "claude-haiku-4-5-20251001": {
            "inputTokens": 4,
            "outputTokens": 21,
            "canonicalModel": "claude-haiku-4-5",
        },
        "claude-opus-5": {
            "inputTokens": 6000,
            "outputTokens": 1170,
            "canonicalModel": "claude-opus-5",
        },
    }

    result = ClaudeCodeProvider(model="claude-opus-5", runner=claude_runner(envelope)).complete(
        CompletionRequest(prompt="write a scene")
    )

    assert result.model == "claude-opus-5", (
        "the requested model billed output on this call and is what wrote the text"
    )


def test_a_silent_downgrade_is_recorded_as_the_model_that_answered() -> None:
    """The other direction, and why the requested model is not simply trusted.

    If the CLI serves a different model than the one asked for, reporting the request would
    be the same lie inverted — a decision claiming Opus wrote prose Haiku wrote. With the
    requested model absent from the billing, the entry that produced the output is the honest
    answer.
    """
    envelope = dict(CLAUDE_ENVELOPE)
    envelope["modelUsage"] = {
        "claude-haiku-4-5-20251001": {"outputTokens": 900, "canonicalModel": "claude-haiku-4-5"},
        "some-router-model": {"outputTokens": 3, "canonicalModel": "some-router-model"},
    }

    result = ClaudeCodeProvider(model="claude-opus-5", runner=claude_runner(envelope)).complete(
        CompletionRequest(prompt="write a scene")
    )

    assert result.model == "claude-haiku-4-5"


def test_the_prompt_travels_on_stdin_and_never_on_the_command_line() -> None:
    """Windows caps a command line at 32,767 characters, and the prompt is unbounded.

    Measured on Serial Pilot 1: a 35,714-character packet raised `[WinError 206] The filename
    or extension is too long`, which arrives as an `OSError` and is classified `unavailable`
    and therefore *retryable* — so the conductor refunded the attempt and requeued it forever.
    The book stopped advancing while `status` reported no parked units, no poisoned units and
    nothing needing attention, and the first five scenes had drafted fine, which is what made
    it look like an outage rather than a ceiling.
    """
    long_prompt = "word " * 9000
    runner = claude_runner({"result": "text", "usage": {}, "total_cost_usd": 0.1})
    provider = ClaudeCodeProvider(runner=runner)  # type: ignore[arg-type]

    provider.complete(CompletionRequest(prompt=long_prompt))

    argv = runner.argv  # type: ignore[attr-defined]
    assert long_prompt not in argv
    assert sum(len(part) for part in argv) < 2000, argv
    assert runner.stdin == long_prompt  # type: ignore[attr-defined]
