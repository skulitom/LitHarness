"""Provider adapters, pinned: local Claude Code for production, a deterministic fake for
the model-free suite and for explicitly requested model-free runs.

§1a requires a frontier generator — the objective is a reader who carries on — so there is
no fallback chain and no sub-frontier tier: an unhealthy provider surfaces as
`ProviderUnavailable` and the unit parks or requeues — the book waits, it never degrades.
(Derived from §1a.5 until §126 made that the long-term goal; `registry.py` carries why the
rule survives the demotion.) The retired plurality design and its
measurements stay recorded in `plan/provider-adapters.md`.
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
from litharness.providers.cli import ClaudeCodeProvider, CommandResult
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import (
    BillingGuardViolation,
    ProviderRegistry,
    in_test_mode,
)


def build_default_registry() -> ProviderRegistry:
    """The pinned provider: Claude Code, or the padded fake on explicit opt-in.

    **The fake is never a silent generation backstop, and that is a fix rather than an
    omission.** It used to backstop generation, and a backstop that cannot clear the gate
    it feeds is not one: the fake's answer is ~140 characters against
    `DraftPolicy.min_chars` of 200, so with every real provider down, six beats each
    generated canned text three times, failed the shape gate three times, exhausted their
    attempt budgets and **poisoned** — five exceptions filed and six unrevivable job ids
    burned, for an outage. Measured exactly that way when the local Ollama daemon stopped
    mid-session.

    With no fake to absorb it, an outage surfaces as `ProviderUnavailable`, which the
    Conductor already handles correctly: the attempt is given back and the unit requeues.
    §19.1 states the rule this is the fourth instance of — **a refusal reached before the
    work must cost time, never the unit** — and this instance hid better than the others,
    because the work did not look refused. A healthy provider answered; it just could not
    write.

    `LITHARNESS_FAKE_PAD_CHARS` is therefore the one road to a model-free run: setting it
    *is* the statement "I am deliberately running this loop on the fake", so it is also
    what selects the fake, padded past the shape-gate floor. Opt-in and off by default —
    a default that quietly made the fake look like a competent writer would make the gate
    untestable.

    `LITHARNESS_ENV=test` no longer filters: the pinned registry *refuses* to resolve a
    billing provider in test mode (`BillingGuardViolation`), so this stays safe to call
    from a test process — the registry, not the caller, enforces that.
    """
    pad = int(os.environ.get("LITHARNESS_FAKE_PAD_CHARS", "0") or 0)
    if pad:
        return ProviderRegistry(FakeProvider(pad_to_chars=pad))
    return ProviderRegistry(ClaudeCodeProvider())


__all__ = [
    "BillingGuardViolation",
    "BlockedProviderError",
    "ClaudeCodeProvider",
    "CommandResult",
    "CompletionRequest",
    "CompletionResult",
    "FakeProvider",
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
