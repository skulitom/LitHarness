"""The two CLI-backed adapters: local Claude Code, and Codex as fallback.

Both shell out, so both take an injected `runner`. That is not decoration — it is what
makes the parsing testable against real captured envelopes without spawning a process or
spending quota. Every flag below was verified against the installed CLIs (`claude`
2.1.227, `codex-cli` 0.147.0) and the numbers in `plan/provider-adapters.md` are
measurements, not estimates.

The per-invocation harness tax is the reason `invocations` exists on `CompletionResult`:
`claude -p` carries ~24k input tokens of its own system prompt and tool definitions per
call (~19k cache-read, ~5k rewritten every time), and `codex exec` carries ~14.8k that
**never** caches. Token accounting alone hides a cost that scales with call count.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderFailureKind,
    Usage,
    parse_schema_payload,
    provider_error,
    strip_fences,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


class Runner(Protocol):
    def __call__(
        self, argv: Sequence[str], *, timeout: float, cwd: str | None = None
    ) -> CommandResult: ...


def subprocess_runner(
    argv: Sequence[str], *, timeout: float, cwd: str | None = None
) -> CommandResult:
    """Real execution. stdin is closed, never inherited, and the pipe is read as UTF-8.

    `claude -p` waits on stdin and prints "no stdin data received in 3s" otherwise —
    three seconds of dead time on every single call.

    **`encoding` is not a default worth inheriting, and the defect it caused is measured.**
    `text=True` alone decodes with `locale.getpreferredencoding()`, which is `cp1252` on a
    Windows host — so every non-ASCII character in a scene these adapters return was mangled
    on the way in. Measured on a real `claude -p` draft: the em dash the generator wrote came
    back as `â€"`, the three UTF-8 bytes of U+2014 reinterpreted one at a time.

    That is worse than cosmetic here, because `STATUS_PATTERN` matches on U+2014 exactly. A
    mangled dash means the status line does not parse, which means `extract_state` reads
    **nothing** from any scene a CLI provider wrote — the silent shape `extraction.py`'s
    docstring names, where a scene that established no state is indistinguishable from one
    nobody could read. Curly quotes, ellipses and accented names in the prose were corrupted
    the same way, and that text goes into an immutable store.

    It survived because every test injects a `Runner` and this function is the one part of the
    adapter a fake cannot exercise, and because no run had ever put a CLI provider in front of
    generation. `OllamaProvider` was never affected: it decodes its own body explicitly.

    `errors="replace"` rather than strict: an undecodable byte should arrive as a visible
    U+FFFD, not raise and cost the unit an attempt, and not be silently transliterated into
    characters that look deliberate.
    """
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        cwd=cwd,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass
class ClaudeCodeProvider:
    """`claude -p` reduced from an agent to a single-shot completion.

    Four flags are not optional, each for a reason that cost something to learn:

    * `--allowed-tools ''` — without it this is an agent that can read and write files
      outside the revision store, violating "no subsystem mutates canon directly" (§5).
    * `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` — otherwise the call inherits
      whatever MCP servers the machine has configured: slow, and not reproducible, which
      §11 requires.
    * `--no-session-persistence` — otherwise every scene leaves a session on disk.
    * stdin closed — see `subprocess_runner`.

    **This runs against whatever authentication the local `claude` install already has**, and
    passes no credential of its own — so on a Claude subscription it consumes that
    subscription, and no API key is involved. `total_cost_usd` from the envelope is then an
    *equivalent* API price for quota already paid for, rather than money being charged.

    **It is recorded anyway, and that is deliberate.** The obvious move is `CodexProvider`'s
    — it reports `cost_usd=None` because "ChatGPT-account auth is quota rather than dollars"
    — and it is the wrong move here. A subscription is *also* a bounded resource, the
    equivalent price is the best available proxy for how fast it is being consumed, and
    `--max-cost-usd-per-day` is the only ceiling that tracks consumption rather than call
    count. Nulling the field would delete the operator's usage governor to win an argument
    about the word "cost". Read it as spend under API-key auth and as quota burn under a
    subscription; the ceiling is useful either way, and `raw` keeps the whole envelope.

    `bills` is a different question and stays `True` under a subscription: it means "this
    reaches a real external service", which is what `LITHARNESS_ENV=test` filters on. A test
    process must not consume subscription quota any more than it may spend money.
    """

    name: str = "claude_code"
    bills: bool = True
    model: str = "claude-opus-5"
    binary: str = "claude"
    runner: Runner = subprocess_runner
    extra_args: tuple[str, ...] = ()

    def _argv(self, request: CompletionRequest) -> list[str]:
        argv = [
            self.binary,
            "-p",
            request.prompt,
            "--output-format",
            "json",
            "--model",
            self.model,
            "--allowed-tools",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-session-persistence",
            "--permission-mode",
            "manual",
        ]
        system = self._system_prompt(request)
        if system:
            argv += ["--append-system-prompt", system]
        return argv + list(self.extra_args)

    @staticmethod
    def _system_prompt(request: CompletionRequest) -> str:
        """Role framing, plus a JSON-only instruction when a schema was asked for.

        `claude -p` has no native structured-output mode — it returned fenced markdown when
        asked for JSON — so the instruction plus fence-stripping is the whole mechanism.
        """
        parts = [request.system] if request.system else []
        if request.schema is not None:
            parts.append(
                "Reply with a single JSON object conforming to this schema and nothing "
                "else — no prose, no code fence:\n"
                + json.dumps(request.schema, sort_keys=True)
            )
        return "\n\n".join(parts)

    def health(self) -> bool:
        try:
            result = self.complete(
                CompletionRequest(
                    prompt="Reply with the single word OK.", timeout_seconds=120.0
                )
            )
        except ProviderError:
            return False
        return bool(result.text.strip())

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started = time.monotonic()
        try:
            outcome = self.runner(self._argv(request), timeout=request.timeout_seconds)
        except subprocess.TimeoutExpired as error:
            raise provider_error(
                f"{self.name} timed out after {request.timeout_seconds}s",
                kind=ProviderFailureKind.TIMEOUT,
            ) from error
        except (OSError, FileNotFoundError) as error:
            raise provider_error(
                f"{self.name} could not be executed: {error}",
                kind=ProviderFailureKind.UNAVAILABLE,
            ) from error
        wall_ms = int((time.monotonic() - started) * 1000)

        try:
            envelope = json.loads(outcome.stdout)
        except json.JSONDecodeError as error:
            raise provider_error(
                f"{self.name} returned unparseable output (exit {outcome.returncode}): "
                f"{outcome.stdout[:200]!r}",
                kind=ProviderFailureKind.MALFORMED_RESPONSE,
                raw=outcome.stdout,
            ) from error

        if envelope.get("is_error") or envelope.get("subtype") not in {None, "success"}:
            raw_status = envelope.get("api_error_status")
            status = raw_status if isinstance(raw_status, int) else None
            error_type = str(envelope.get("subtype") or "") or None
            message = (
                f"{self.name} reported an error: {raw_status} "
                f"{str(envelope.get('result', ''))[:200]}"
            )
            raise provider_error(
                message,
                provider_error_type=error_type,
                status=status,
                request_id=str(envelope["request_id"]) if envelope.get("request_id") else None,
                raw=json.dumps(envelope, ensure_ascii=False),
            )

        text = strip_fences(str(envelope.get("result", "")))
        usage_block = envelope.get("usage") or {}
        model_usage = envelope.get("modelUsage") or {}
        resolved = _resolved_model(model_usage, self.model)
        return CompletionResult(
            text=text,
            provider=self.name,
            model=str(resolved),
            usage=Usage(
                input_tokens=int(usage_block.get("input_tokens", 0)),
                output_tokens=int(usage_block.get("output_tokens", 0)),
                cache_read_tokens=int(usage_block.get("cache_read_input_tokens", 0)),
                cache_write_tokens=int(usage_block.get("cache_creation_input_tokens", 0)),
            ),
            parsed=parse_schema_payload(text, request.schema),
            schema_requested=request.schema is not None,
            cost_usd=envelope.get("total_cost_usd"),
            wall_ms=wall_ms,
            raw=envelope,
        )


def _resolved_model(model_usage: dict[str, Any], requested: str) -> str:
    """Which model actually wrote the text, out of every model the invocation billed.

    **`claude -p` bills more than one model per call, and taking the first was reporting the
    wrong one.** Measured: a call requesting `claude-opus-5` returned `modelUsage` keyed
    `['claude-haiku-4-5-20251001', 'claude-opus-5']` — Opus wrote the prose and Haiku is the
    CLI's own overhead — and `next(iter(...))` reported `claude-haiku-4-5`. That value is
    recorded on the `PolicyDecision` for every accepted scene, so a run drafted by Opus is
    attributable to Haiku in the store. §56.2 caught it during the frontier arm and the
    frontier duplication run wrote four such rows before this landed.

    §19's attribution chain is one of the things §18 says is kept absolutely, and a provenance
    record that names a model which did not write the prose is the failure it exists to
    prevent — worse than a missing field, because it is confidently wrong.

    The requested model wins when it is present, since that is what the call asked for and
    got. Otherwise the entry that produced the most output tokens does, because the model that
    wrote the answer is the one that wrote the most of it — and that also covers a CLI which
    silently downgrades, where reporting the requested model would be the same lie inverted.
    """
    if not model_usage:
        return requested

    def canonical(key: str, info: Any) -> str:
        if isinstance(info, dict):
            named = info.get("canonicalModel")
            if isinstance(named, str) and named:
                return named
        return key

    named = {key: canonical(key, info) for key, info in model_usage.items()}
    for key, name in named.items():
        if requested in (key, name):
            return name

    def output_of(info: Any) -> int:
        block = info if isinstance(info, dict) else {}
        try:
            return int(block.get("outputTokens", block.get("output_tokens", 0)) or 0)
        except (TypeError, ValueError):
            return 0

    busiest = max(model_usage.items(), key=lambda item: output_of(item[1]))
    return named[busiest[0]]


@dataclass
class CodexProvider:
    """`codex exec` as the fallback tier.

    Advantages over `claude -p`: `--output-schema` enforces the shape natively, so no
    fence-stripping heuristic, and the JSONL event stream is small and stable
    (`thread.started`, `turn.started`, `item.completed`, `turn.completed`).

    Disadvantages, both measured: it never caches (`cached_input_tokens` was 0 across
    byte-identical repeat calls, so its ~14.8k tax is full price every time), and it
    reports no cost, because ChatGPT-account auth is quota rather than dollars.

    `--skip-git-repo-check` is required because the LitHarness tree is not a git
    repository. `-c mcp_servers={}` suppresses the MCP servers it otherwise starts.
    """

    name: str = "codex"
    bills: bool = True
    model: str | None = None  # None = the CLI's own default
    binary: str = "codex"
    runner: Runner = subprocess_runner
    sandbox: str = "read-only"
    extra_args: tuple[str, ...] = ()
    _workdir: str | None = field(default=None, repr=False)

    def health(self) -> bool:
        try:
            result = self.complete(
                CompletionRequest(
                    prompt="Reply with the single word OK.",
                    schema={
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["ok"],
                        "properties": {"ok": {"type": "boolean"}},
                    },
                    timeout_seconds=180.0,
                )
            )
        except ProviderError:
            return False
        return result.conforms

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started = time.monotonic()
        with TemporaryDirectory() as scratch:
            schema_path = Path(scratch) / "schema.json"
            answer_path = Path(scratch) / "last-message.txt"
            argv = [
                self.binary,
                "exec",
                self._prompt(request),
                "-o",
                str(answer_path),
                "--json",
                "--skip-git-repo-check",
                "--sandbox",
                self.sandbox,
                "--color",
                "never",
                "-c",
                "mcp_servers={}",
            ]
            if request.schema is not None:
                schema_path.write_text(
                    json.dumps(request.schema, sort_keys=True), encoding="utf-8"
                )
                argv += ["--output-schema", str(schema_path)]
            if self.model:
                argv += ["-m", self.model]
            argv += list(self.extra_args)

            try:
                outcome = self.runner(
                    argv, timeout=request.timeout_seconds, cwd=self._workdir
                )
            except subprocess.TimeoutExpired as error:
                raise provider_error(
                    f"{self.name} timed out after {request.timeout_seconds}s",
                    kind=ProviderFailureKind.TIMEOUT,
                ) from error
            except (OSError, FileNotFoundError) as error:
                raise provider_error(
                    f"{self.name} could not be executed: {error}",
                    kind=ProviderFailureKind.UNAVAILABLE,
                ) from error

            # The `-o` file is the contract for the final answer; the event stream is for
            # usage and provenance. Reassembling the text from events would be fragile.
            text = answer_path.read_text(encoding="utf-8").strip() if answer_path.exists() else ""

        wall_ms = int((time.monotonic() - started) * 1000)
        events = _parse_jsonl(outcome.stdout)
        usage = _codex_usage(events)

        if not text:
            detail = _codex_error(events, outcome.stderr)
            status = _codex_status(events)
            raise provider_error(
                f"{self.name} produced no answer (exit {outcome.returncode}): {detail}",
                status=status,
                raw=json.dumps({"events": events, "stderr": outcome.stderr}, ensure_ascii=False),
            )

        return CompletionResult(
            text=strip_fences(text),
            provider=self.name,
            model=self.model or _codex_model(events) or "codex-default",
            usage=usage,
            parsed=parse_schema_payload(text, request.schema),
            schema_requested=request.schema is not None,
            cost_usd=None,  # subscription quota, not dollars
            wall_ms=wall_ms,
            raw={"events": events},
        )

    @staticmethod
    def _prompt(request: CompletionRequest) -> str:
        return f"{request.system}\n\n{request.prompt}" if request.system else request.prompt


def _parse_jsonl(stream: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stream.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _codex_usage(events: list[dict[str, Any]]) -> Usage:
    for event in reversed(events):
        if event.get("type") == "turn.completed":
            block = event.get("usage") or {}
            return Usage(
                input_tokens=int(block.get("input_tokens", 0)),
                output_tokens=int(block.get("output_tokens", 0)),
                cache_read_tokens=int(block.get("cached_input_tokens", 0)),
                cache_write_tokens=int(block.get("cache_write_input_tokens", 0)),
                reasoning_tokens=int(block.get("reasoning_output_tokens", 0)),
            )
    return Usage()


def _codex_model(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        model = event.get("model")
        if isinstance(model, str):
            return model
    return None


def _codex_error(events: list[dict[str, Any]], stderr: str) -> str:
    for event in reversed(events):
        for key in ("error", "detail", "message"):
            if key in event:
                return str(event[key])[:200]
    return stderr.strip()[:200] or "no diagnostic output"


def _codex_status(events: list[dict[str, Any]]) -> int | None:
    for event in reversed(events):
        for key in ("status", "status_code", "http_status"):
            value = event.get(key)
            if isinstance(value, int):
                return value
        nested = event.get("error")
        if isinstance(nested, dict):
            value = nested.get("status") or nested.get("status_code")
            if isinstance(value, int):
                return value
    return None
