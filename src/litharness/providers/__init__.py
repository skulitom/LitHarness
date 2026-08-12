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
    "in_test_mode",
]
