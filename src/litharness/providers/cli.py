"""The CLI-backed frontier adapter: local Claude Code, reduced to a completion endpoint.

It shells out, so it takes an injected `runner`. That is not decoration — it is what
makes the parsing testable against the real captured envelope without spawning a process
or spending quota. Every flag below was verified against the installed CLI (`claude`
2.1.227; the CLAUDE.md suppression against 2.1.236) and the numbers in
`plan/provider-adapters.md` are measurements, not estimates.
(The Codex fallback adapter that used to live beside this one is retired with provider
plurality; its measurements stay in that document.)

The per-invocation harness tax is the reason `invocations` exists on `CompletionResult`:
`claude -p` carries ~24k input tokens of its own system prompt and tool definitions per
call (~19k cache-read, ~5k rewritten every time; ~27k on 2.1.236, measured 2026-08-22 as
21,352 read + ~5.3k written — the user-level skills and plugins ride along, and only
`--bare` would drop them). Token accounting alone hides a cost that scales with call
count.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
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
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> CommandResult: ...


def subprocess_runner(
    argv: Sequence[str], *, timeout: float, cwd: str | None = None, stdin: str | None = None
) -> CommandResult:
    """Real execution. The prompt goes down stdin, and the pipe is read as UTF-8.

    **The prompt is not a command-line argument, and Windows is why.** `CreateProcess` caps a
    command line at 32,767 characters, so once a book had enough prior prose to fill a 16k-token
    packet, every draft raised `[WinError 206] The filename or extension is too long` — measured
    at a 35,714-character prompt on Serial Pilot 1's sixth scene. It surfaced as an `OSError`,
    which `classify_provider_failure` reads as `unavailable` and therefore *retryable*, so the
    conductor refunded the attempt and requeued it forever: a book that stopped advancing while
    `status` reported no parked units, no poisoned units and nothing needing attention. The
    first five scenes had drafted fine, which is what made it look like an outage.

    Passing the prompt on stdin removes the ceiling rather than raising it. It also costs
    nothing that closing stdin was buying: `claude -p` waits three seconds only when stdin is an
    open pipe with no data, and a pipe that is written and closed does not wait.

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
    generation. The retired Ollama adapter was never affected: it decoded its own body
    explicitly.

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
        input=stdin if stdin is not None else "",
        cwd=cwd,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


#: Settings JSON passed on every call. Globs rather than one path so `.claude/CLAUDE.md`
#: and `CLAUDE.local.md` in the working directory are covered as well as the root file.
CLAUDE_MD_EXCLUDES = '{"claudeMdExcludes":["**/CLAUDE.md","**/CLAUDE.local.md"]}'


@dataclass
class ClaudeCodeProvider:
    """`claude -p` reduced from an agent to a single-shot completion.

    Five flags are not optional, each for a reason that cost something to learn:

    * `--allowed-tools` — **empty unless the request names tools**, and empty is what
      every drafting and reader call sends. Without the flag this is an agent that can
      read and write files outside the revision store, violating "no subsystem mutates
      canon directly" (§5). `CompletionRequest.allowed_tools` is how a role that
      *manages* the world asks for the world's own commands and nothing else; the rule
      it keeps is that canon is reached through a recorded decision, not that a model
      may never run a command.
    * `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` — otherwise the call inherits
      whatever MCP servers the machine has configured: slow, and not reproducible, which
      §11 requires.
    * `--no-session-persistence` — otherwise every scene leaves a session on disk.
    * `--setting-sources user --settings {claudeMdExcludes}` — otherwise the call reads
      the repository's CLAUDE.md (and project/local settings) from the working directory,
      none of which the frozen prompt records. See the comment on `_argv` for what was
      measured and why `--bare` could not be the answer.
    * stdin closed — see `subprocess_runner`.

    **This runs against whatever authentication the local `claude` install already has**, and
    passes no credential of its own — so on a Claude subscription it consumes that
    subscription, and no API key is involved. `total_cost_usd` from the envelope is then an
    *equivalent* API price for quota already paid for, rather than money being charged.

    **It is recorded anyway, and that is deliberate.** The obvious move is the one the
    retired Codex adapter made — reporting `cost_usd=None` because "ChatGPT-account auth is
    quota rather than dollars" — and it is the wrong move here. A subscription is *also* a
    bounded resource, the
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

    def _model_for(self, request: CompletionRequest) -> str:
        """The model this call asks for: the request's, or this adapter's own.

        A request naming none is byte-identical to what it always sent, which is what makes
        the field additive rather than a change to every existing call site.
        """
        return request.model or self.model

    def _argv(self, request: CompletionRequest) -> list[str]:
        argv = [
            self.binary,
            # `-p` with no positional prompt: the prompt arrives on stdin. See
            # `subprocess_runner` for the Windows command-line ceiling that forced this.
            "-p",
            "--output-format",
            "json",
            "--model",
            self._model_for(request),
            "--allowed-tools",
            # Empty for every call that asks for nothing, which is every drafting call and
            # every reader call — byte-identical to what this always sent. A role that
            # manages the world names the commands it needs and gets those only.
            ",".join(request.allowed_tools),
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-session-persistence",
            "--permission-mode",
            "manual",
            # A `-p` call loads the same context an interactive session would: any CLAUDE.md
            # in the working directory or its ancestors, plus `~/.claude`'s settings, skills
            # and plugins — and `--append-system-prompt` goes in *after* it. The loop runs
            # from the repository root, and the repository carries a CLAUDE.md written for
            # sessions rather than for the writer, so without these flags it would ride into
            # every drafting call and the frozen prompt (§103) would no longer be the whole
            # of what the model saw. Measured 2026-08-22 on `claude` 2.1.236 with a marker
            # CLAUDE.md in the working directory: without either flag the model echoed the
            # marker; with either one it did not. `--bare` is the documented full
            # suppression and skips keychain reads, which is where a subscription login
            # lives ("Not logged in"), so it is unusable here; `--system-prompt` is
            # documented to ignore CLAUDE.md and was measured *not* to. Two mechanisms
            # because each covers the other's gap: `claudeMdExcludes` is the documented
            # CLAUDE.md control, and `--setting-sources user` is docs-silent on CLAUDE.md but
            # also drops project and local settings.json — hooks, permissions, env — which
            # this adapter never wanted. The live test checks the outcome, not the mechanism.
            "--setting-sources",
            "user",
            "--settings",
            CLAUDE_MD_EXCLUDES,
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
        return request.effective_system

    def health(self) -> bool:
        try:
            result = self.complete(
                CompletionRequest(prompt="Reply with the single word OK.", timeout_seconds=120.0)
            )
        except ProviderError:
            return False
        return bool(result.text.strip())

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started = time.monotonic()
        try:
            outcome = self.runner(
                self._argv(request), timeout=request.timeout_seconds, stdin=request.prompt
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
        # Against what this call *asked for*, not against the adapter's default: a request
        # naming its own model and attributed to the adapter's would be §56.2's defect with
        # the sign flipped — a provenance record confidently naming a model that did not
        # write the prose.
        resolved = _resolved_model(model_usage, self._model_for(request))
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
