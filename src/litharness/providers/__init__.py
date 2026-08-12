"""Provider adapters: local Claude Code by default, Codex as fallback, Ollama for
mechanical work and tests, and a deterministic fake for the model-free suite.

Design and measurements: `plan/provider-adapters.md`.
"""

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    Provider,
    ProviderError,
    ProviderUnavailable,
    Usage,
)
from litharness.providers.cli import ClaudeCodeProvider, CodexProvider, CommandResult
from litharness.providers.fake import FakeProvider
from litharness.providers.ollama import OllamaProvider
from litharness.providers.registry import ProviderRegistry, Resolution, in_test_mode


def build_default_registry() -> ProviderRegistry:
    """The four adapters in the order `plan/provider-adapters.md` specifies.

    The order is the design, not a default to tweak casually: the local Claude Code session
    generates, Codex is the fallback, Ollama takes mechanical work, and the deterministic
    fake backstops both. `cheap_order` routes extraction and evaluation to non-billing
    providers even in production, because the CLI adapters' per-invocation harness tax
    (~24k input tokens for `claude -p`, ~14.8k for `codex exec`) dwarfs a small payload.

    `LITHARNESS_ENV=test` filters billing providers out of resolution entirely, so this is
    safe to call from a test process — the registry, not the caller, enforces that.
    """
    return ProviderRegistry(
        providers=[
            ClaudeCodeProvider(),
            CodexProvider(),
            OllamaProvider(),
            FakeProvider(),
        ],
        order=["claude_code", "codex", "ollama", "fake"],
        cheap_order=["ollama", "fake", "claude_code", "codex"],
    )


__all__ = [
    "ClaudeCodeProvider",
    "CodexProvider",
    "CommandResult",
    "CompletionRequest",
    "CompletionResult",
    "FakeProvider",
    "OllamaProvider",
    "Provider",
    "ProviderError",
    "ProviderRegistry",
    "ProviderUnavailable",
    "Resolution",
    "Usage",
    "build_default_registry",
    "in_test_mode",
]
