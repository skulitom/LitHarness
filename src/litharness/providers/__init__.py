"""Provider adapters: local Claude Code by default, Codex as fallback, Ollama for
mechanical work and tests, and a deterministic fake for the model-free suite.

Design and measurements: `plan/provider-adapters.md`.
"""

import os

from litharness.providers.base import (
    BlockedProviderError,
    CompletionRequest,
    CompletionResult,
    Provider,
    ProviderError,
    ProviderFailureKind,
    ProviderUnavailable,
    Resolution,
    RetryableProviderError,
    Usage,
    classify_provider_failure,
    provider_error,
)
from litharness.providers.cli import ClaudeCodeProvider, CodexProvider, CommandResult
from litharness.providers.fake import FakeProvider
from litharness.providers.ollama import OllamaProvider
from litharness.providers.registry import ProviderRegistry, in_test_mode

#: The order `plan/provider-adapters.md` specifies, named once so `prefer` reorders rather
#: than rewrites it.
#:
#: **`fake` is not in it, and that is a fix rather than an omission.** It used to backstop
#: generation, and a backstop that cannot clear the gate it feeds is not one: the fake's
#: answer is ~80 characters against `DraftPolicy.min_chars` of 200, so with every real
#: provider down, six beats each generated canned text three times, failed the shape gate
#: three times, exhausted their attempt budgets and **poisoned** — five exceptions filed and
#: six unrevivable job ids burned, for an outage. Measured exactly that way when the local
#: Ollama daemon stopped mid-session.
#:
#: With no fake to absorb it, the outage surfaces as `ProviderUnavailable`, which the
#: Conductor already handles correctly: the attempt is given back and the unit requeues. §19.1
#: states the rule this is the fourth instance of — **a refusal reached before the work must
#: cost time, never the unit** — and this instance hid better than the others, because the
#: work did not look refused. A healthy provider answered; it just could not write.
#:
#: `fake` stays in `DEFAULT_CHEAP_ORDER`: extraction and mechanical calls are schema-shaped
#: and a deterministic answer there is the point.
DEFAULT_ORDER = ("claude_code", "codex", "ollama")
DEFAULT_CHEAP_ORDER = ("ollama", "fake", "claude_code", "codex")


def build_default_registry(
    prefer: str | None = None, *, refuse_billing: bool = False, model: str | None = None
) -> ProviderRegistry:
    """The four adapters in the order `plan/provider-adapters.md` specifies.

    The order is the design, not a default to tweak casually: the local Claude Code session
    generates, Codex is the fallback, Ollama takes mechanical work, and the deterministic
    fake backstops both. `cheap_order` routes extraction and evaluation to non-billing
    providers even in production, because the CLI adapters' per-invocation harness tax
    (~24k input tokens for `claude -p`, ~14.8k for `codex exec`) dwarfs a small payload.

    `LITHARNESS_ENV=test` filters billing providers out of resolution entirely, so this is
    safe to call from a test process — the registry, not the caller, enforces that.

    **`prefer` and `refuse_billing` are the operator's two levers, and they answer different
    questions.** "Draft this book on my local model" is a preference: the chain still falls
    back, and §5 rule 4 makes the fallback an event rather than a silent switch. "This run
    must not spend money" is not a preference at all, and expressing it by *preferring* a
    free provider would be a bill waiting for the first health blip. Before these existed the
    only lever was `LITHARNESS_ENV=test`, which is the guarantee that test runs cannot bill —
    a thing to keep, not a thing to configure production with.

    An unknown `prefer` name raises. `order` deliberately ignores names it does not know, so
    a typo would leave the default order in place and the operator would find out from the
    bill; this is the one place a provider name arrives from a human.

    **`model` names the Ollama model, and until it existed no shipped command could.** Every
    adapter was constructed argument-free, so `OllamaProvider.model` was `qwen3:4b` for every
    invocation of every subcommand — while `plan/stage-0-decisions.md` §44 attributes the
    first Book Zero run to `llama3.2:3b` and §45's table names two more. `--prefer ollama`
    selects the *adapter* and has never selected a model, so those attributions cannot have
    come from the CLI. Scene length is a property of the generator (§45), so the one knob
    that moves it most was the one an operator could not turn.

    It applies to Ollama alone. `ClaudeCodeProvider.model` and `CodexProvider.model` are
    per-vendor identifiers from disjoint namespaces, and one flag setting all three would
    let `--model phi4:latest` reach `claude -p --model phi4:latest`. A billing provider is
    the wrong place to discover a typo.
    """
    # The fake's answer is ~140 characters and `DraftPolicy.min_chars` is 200, so a
    # model-free run would fail the shape gate on every beat. `LITHARNESS_FAKE_PAD_CHARS`
    # pads it to a length that clears the floor. Opt-in and off by default: padding is
    # scaffolding for exercising the loop without a model, and a default that quietly made
    # the fake look like a competent writer would make the gate untestable.
    pad = int(os.environ.get("LITHARNESS_FAKE_PAD_CHARS", "0") or 0)
    providers: list[Provider] = [
        ClaudeCodeProvider(),
        CodexProvider(),
        OllamaProvider() if model is None else OllamaProvider(model=model),
        FakeProvider(pad_to_chars=pad),
    ]
    order, cheap = list(DEFAULT_ORDER), list(DEFAULT_CHEAP_ORDER)
    if pad:
        # Setting the pad *is* the statement "I am deliberately running this loop on the
        # fake", so it is also what makes the fake eligible to generate. Without it the fake
        # cannot serve prose at all, which is what stops an outage looking like a bad writer.
        order.append("fake")
    if prefer is not None:
        known = {provider.name for provider in providers}
        if prefer not in known:
            raise ValueError(
                f"unknown provider {prefer!r}; adapters are {sorted(known)}"
            )
        order = [prefer, *(name for name in order if name != prefer)]
        cheap = [prefer, *(name for name in cheap if name != prefer)]
    return ProviderRegistry(
        providers=providers,
        order=order,
        cheap_order=cheap,
        refuse_billing=refuse_billing,
    )


__all__ = [
    "DEFAULT_CHEAP_ORDER",
    "DEFAULT_ORDER",
    "BlockedProviderError",
    "ClaudeCodeProvider",
    "CodexProvider",
    "CommandResult",
    "CompletionRequest",
    "CompletionResult",
    "FakeProvider",
    "OllamaProvider",
    "Provider",
    "ProviderError",
    "ProviderFailureKind",
    "ProviderRegistry",
    "ProviderUnavailable",
    "Resolution",
    "RetryableProviderError",
    "Usage",
    "build_default_registry",
    "classify_provider_failure",
    "in_test_mode",
    "provider_error",
]
