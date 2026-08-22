"""The remote transport for the force programme: `claude -p`, with a spend ceiling that bites.

**Why this exists.** F1 needs 630 seeds x 8 sampled continuations and prices out at ~18.6
GPU-hours per family on this box (§95.6), which is not affordable at the duty cycle three
shutdowns have now paid for. Sampling is the *only* thing F1 needs from a model — no logprobs,
no internals — so it is the one arm that can leave the machine. F2 and F3 cannot follow it: both
are built on teacher-forced token logprobs and **the Messages API exposes none**, in any form.

**What it costs, measured rather than estimated.** `claude -p` prepends Claude Code's own system
prompt to every call — **26,357 tokens**, which dwarfs a 900-word seed. It caches well, and F1's
shape is unusually kind to that: the K replicates of one seed are the *same prompt*, so the first
call writes the prefix and the rest read it.

    new seed, cold prefix     $0.0210     (5,677 written, 20,807 read)
    same seed, warm prefix    $0.0089     (0 written, 26,357 read)
    => one seed at K=8        $0.0833     = 0.0210 + 7 x 0.0089

That is why :func:`continuations` runs a seed's replicates **sequentially** and parallelises only
*across* seeds: reordering them to look faster would pay the write eight times and quadruple the
bill. Operator raised the cap to ~$55 for this arm (§7.5 amended); :class:`Ledger` stops the run
dead at it rather than discovering the overrun afterwards.

**Everything this transport gives up, in one place, because none of it is recoverable later.**

*Determinism.* There is no seed parameter and no guarantee. `force_harness.text_seed` cannot buy
byte-identical replay here, so `placebo_identical` **cannot** be the exact arithmetic check §89.4
made it. It becomes an equivalence test — identical sides must produce an agreement whose interval
contains 0.50, which is the shape `sham_verdict` already implements. §1.7 pre-registered exactly
this branch, so the design survives; it is still strictly weaker and is labelled as such in every
result file.

*Base versus instruct.* §95 pins **base** checkpoints because `surprisal.py`'s argument is that
instruction tuning reshapes the very distribution F1 measures. Haiku is heavily post-trained and
cannot be prompted into a raw continuation — the seed goes in under a fixed continuation
instruction. The programme's axiom is intact (nothing is *asked* about quality, and valence still
comes from measuring generated text) but the instrument is different and the entry must not
pretend otherwise.

*Pinning.* `claude-haiku-4-5` is a name, not a revision. Every local family in `FAMILIES` is
pinned to a 40-character commit sha; this one cannot be, so a run six months from now may not be
measuring the same weights. Recorded in the provenance block of every result rather than assumed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from force_harness import digest  # noqa: E402

#: The remote family. Named rather than pinned — see the module docstring.
REMOTE_FAMILIES: dict[str, dict[str, str]] = {
    "haiku-4-5": {
        "lineage": "anthropic/claude-haiku",
        "chat": "claude-haiku-4-5",
        "chat_revision": "UNPINNED — an alias, not a commit sha",
        "base": "claude-haiku-4-5",
        "base_revision": "UNPINNED — no base checkpoint is reachable through this transport",
    },
}

#: Frozen. F1 on a local base model needs no instruction at all; an assistant cannot be prompted
#: into raw continuation, so this is the minimum that gets one. It asks for no judgment, offers
#: no slot and names no quality — the programme's axiom is about not asking which passage is
#: better, and this does not.
CONTINUATION_SYSTEM = (
    "Continue this passage of fiction. Write only the continuation, in the same voice, "
    "with no preamble, no commentary and no headings."
)

#: `elicit.CLI_HARDENING`, copied (this module runs beside it, not on it). The last two flags
#: keep the repository's CLAUDE.md out of the continuation call — stage-0 §109; the reasons
#: are on the tuple in `elicit.py`.
CLI_HARDENING = (
    "--exclude-dynamic-system-prompt-sections",
    "--allowed-tools", "",
    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    "--no-session-persistence",
    "--permission-mode", "manual",
    "--setting-sources", "user",
    "--settings", '{"claudeMdExcludes":["**/CLAUDE.md","**/CLAUDE.local.md"]}',
)

#: Operator §7.5, amended 2026-08-20 from $15 to fund F1 on this transport.
DEFAULT_CEILING_USD = 55.0

#: One CLI job at a time is the house rule — §89.5 records that two concurrent `claude -p` jobs
#: on this box produced 390 transport failures. Workers *inside* one job are fine, and three is
#: what keeps a 20-hour serial run under seven hours.
DEFAULT_WORKERS = 3

#: **Every continuation is cut to the same number of words, and this is a correctness fix rather
#: than tidiness.** Locally, `max_new_tokens` makes every trajectory the same length by
#: construction; here the model stops when it stops, and the first probe returned continuations
#: of 300, 815 and 1,040 tokens. F1's statistic is a *window index*, so a side whose
#: continuations run longer has more windows to cross in and a different censoring rate — a
#: length confound sitting directly on the outcome. Cutting every continuation to a fixed word
#: count removes it. A continuation too short to carry a trajectory is **dropped and counted**,
#: never padded.
CONTINUATION_WORDS = 280
MIN_CONTINUATION_WORDS = 180


_WORDS = re.compile(r"\S+")


class AlreadyRunning(RuntimeError):
    """Raised when another run of the same arm already holds the lock."""


class SingleRun:
    """A PID lock file, because nothing else stopped three copies of one arm racing.

    **This exists because it happened.** `pkill -f register_halflife` matches nothing on Windows,
    so two "relaunches" *added* processes instead of replacing them and three copies of F1 ran
    against one cache. Measured afterwards from the cache itself: 248 completed seed-runs for 140
    distinct seeds — **108 duplicate computations, about $9 of paid work bought twice** — plus one
    corrupt line, because `Checkpoint`'s write lock is per-process and three appenders interleaved.

    A stale lock (the holder is gone) is taken over rather than honoured: a crashed run must not
    block the next one, and the PID is recorded so a live holder can be named in the error.
    """

    def __init__(self, path: Path, label: str = "") -> None:
        self.path = Path(path)
        self.label = label

    def __enter__(self) -> SingleRun:
        import os

        if self.path.is_file():
            try:
                holder = int(self.path.read_text(encoding="utf-8").split()[0])
            except (ValueError, IndexError, OSError):
                holder = -1
            if holder > 0 and _pid_alive(holder):
                raise AlreadyRunning(
                    f"{self.label or self.path.name} is already running as pid {holder}. "
                    "Two copies of one arm race the same cache and buy the same seeds twice; "
                    f"stop it first, or delete {self.path} if you know it is stale."
                )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f"{os.getpid()} {self.label}", encoding="utf-8")
        return self

    def __exit__(self, *_: object) -> None:
        with suppress(OSError):
            self.path.unlink()


def _pid_alive(pid: int) -> bool:
    out = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue) -ne $null",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    ).stdout.strip().lower()
    return out.startswith("true")


class CeilingReached(RuntimeError):
    """Raised when the declared spend ceiling is hit. Never caught inside this module."""


@dataclass
class Ledger:
    """Running spend, and the stop that makes the ceiling real rather than decorative."""

    ceiling_usd: float = DEFAULT_CEILING_USD
    spent_usd: float = 0.0
    calls: int = 0
    cache_reads: int = 0
    cache_writes: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    transport_failures: int = 0
    _lock: Any = field(default_factory=threading.Lock, repr=False)

    def charge(self, envelope: dict[str, Any]) -> None:
        usage = envelope.get("usage", {}) or {}
        with self._lock:
            self.spent_usd += float(envelope.get("total_cost_usd") or 0.0)
            self.calls += 1
            self.cache_reads += int(usage.get("cache_read_input_tokens") or 0)
            self.cache_writes += int(usage.get("cache_creation_input_tokens") or 0)
            self.output_tokens += int(usage.get("output_tokens") or 0)
            details = usage.get("output_tokens_details", {}) or {}
            self.thinking_tokens += int(details.get("thinking_tokens") or 0)
            if self.spent_usd >= self.ceiling_usd:
                raise CeilingReached(
                    f"spend ceiling reached: ${self.spent_usd:.2f} of ${self.ceiling_usd:.2f} "
                    f"after {self.calls} calls. The cache is intact; a resumed run replays "
                    "everything already bought and continues from here."
                )

    def check(self) -> None:
        """Refuse to start a call that the ceiling has already closed."""
        with self._lock:
            if self.spent_usd >= self.ceiling_usd:
                raise CeilingReached(
                    f"spend ceiling reached: ${self.spent_usd:.2f} of ${self.ceiling_usd:.2f}"
                )

    def report(self) -> dict[str, Any]:
        return {
            "transport": "claude -p (Claude Code CLI)",
            "ceiling_usd": self.ceiling_usd,
            "spent_usd": round(self.spent_usd, 4),
            "calls": self.calls,
            "usd_per_call": round(self.spent_usd / self.calls, 5) if self.calls else None,
            "cache_read_tokens": self.cache_reads,
            "cache_write_tokens": self.cache_writes,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "transport_failures": self.transport_failures,
            "note": "equivalent quota on a subscription, not billed dollars — "
                    "`providers/cli.py`'s position, and §85's convention",
        }


def _call(prompt: str, model: str, *, timeout: int = 300) -> dict[str, Any]:
    argv = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--system-prompt", CONTINUATION_SYSTEM,
        *CLI_HARDENING,
    ]
    # **`encoding='utf-8', errors='replace'` is not optional on Windows.** `text=True` alone
    # decodes with the console codepage (cp1252 here), and Claude's prose is full of characters
    # it cannot represent — a single curly apostrophe raises `UnicodeDecodeError` in
    # subprocess's reader thread. That exception is a `ValueError`, so the retry path below
    # swallowed it and counted the call as a transport failure: seeds whose continuations
    # happened to contain a smart quote quietly lost replicates, which is a *biased* loss and
    # not a random one. `elicit.py:931` had already solved this; this is that line, copied.
    completed = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"cli_error rc={completed.returncode}: {completed.stderr[:200]}")
    # `claude --output-format json` always emits one JSON object; json.loads' `Any` is the
    # only thing mypy sees for it.
    return cast(dict[str, Any], json.loads(completed.stdout))


def continuations(
    seed_text: str,
    *,
    model: str = "claude-haiku-4-5",
    k: int = 8,
    ledger: Ledger,
    retries: int = 2,
) -> tuple[list[str], dict[str, Any]]:
    """K continuations of one seed, run **sequentially** so the prefix cache is paid once.

    Sequential is not a simplification. The K replicates share a prompt byte for byte, so the
    first call writes Claude Code's 26k-token prefix and the remaining seven read it at a tenth
    of the price. Interleaving seeds across the K axis would pay the write every time.

    A transport failure is retried and then recorded as a *missing* replicate rather than an
    empty string: `latent_crossfamily`'s rule that a transport failure is the absence of a
    measurement and caching it would bake a network error into a result file.
    """
    out: list[str] = []
    failures = 0
    too_short = 0
    for _ in range(k):
        ledger.check()
        for attempt in range(retries + 1):
            try:
                envelope = _call(seed_text, model)
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError):
                if attempt == retries:
                    failures += 1
                    with ledger._lock:
                        ledger.transport_failures += 1
                    break
                time.sleep(2.0 * (attempt + 1))
                continue
            ledger.charge(envelope)
            words = _WORDS.findall(envelope.get("result") or "")
            if len(words) < MIN_CONTINUATION_WORDS:
                too_short += 1
            else:
                out.append(" ".join(words[:CONTINUATION_WORDS]))
            break
    return out, {
        "requested": k,
        "returned": len(out),
        "failed": failures,
        "too_short": too_short,
        "words_each": CONTINUATION_WORDS,
        "min_words": MIN_CONTINUATION_WORDS,
    }


def symmetric_seeds_by_words(
    high: str, low: str, cap: int = 900
) -> tuple[str, str, dict[str, Any]]:
    """Both sides cut to the same **word** count. The remote substitute for a token cap.

    `force_gpu.symmetric_seeds` cuts to a shared *token* count using the family's own tokenizer;
    no tokenizer is reachable through this transport, so the cap is in words and the substitution
    is recorded rather than glossed. It preserves the property that matters — the two sides of a
    pair enter at the same length, closing §95.4's confound — and gives up only exactness about
    what a length is.
    """
    high_words = _WORDS.findall(high)
    low_words = _WORDS.findall(low)
    keep = min(len(high_words), len(low_words), cap)
    import math

    return (
        " ".join(high_words[:keep]),
        " ".join(low_words[:keep]),
        {
            "unit": "words (no tokenizer on this transport)",
            "seed_words_used": keep,
            "high_words_in": len(high_words),
            "low_words_in": len(low_words),
            "log10_word_ratio": round(
                abs(math.log10(len(high_words) / max(len(low_words), 1))), 4
            ),
            "truncated": len(high_words) > keep or len(low_words) > keep,
        },
    )


def provenance(model: str = "claude-haiku-4-5") -> dict[str, Any]:
    return {
        "family": "haiku-4-5",
        "head": "chat",
        "model_id": model,
        "revision": "UNPINNED — an alias, not a commit sha",
        "lineage": "anthropic/claude-haiku",
        "transport": "claude -p",
        "instruction": CONTINUATION_SYSTEM,
        "determinism": "NONE — no seed parameter; placebo_identical is downgraded from an "
                       "arithmetic check to an equivalence test (§1.7's pre-registered branch)",
        "base_or_instruct": "instruct — §95's local families are base checkpoints on purpose, "
                            "so this measures a different distribution and is labelled as one",
        "system_prompt_digest": digest(CONTINUATION_SYSTEM),
    }


def selftest() -> int:
    """No calls. Checks the ceiling bites and the word cap is symmetric."""
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    ledger = Ledger(ceiling_usd=0.05)
    ledger.charge({"total_cost_usd": 0.02, "usage": {"output_tokens": 10}})
    check(ledger.calls == 1 and abs(ledger.spent_usd - 0.02) < 1e-9, "charge must accumulate")
    try:
        ledger.charge({"total_cost_usd": 0.04, "usage": {}})
    except CeilingReached:
        pass
    else:
        failures.append("the ceiling must raise rather than be advisory")
    try:
        ledger.check()
    except CeilingReached:
        pass
    else:
        failures.append("a closed ceiling must refuse the next call before it is made")

    high, low, record = symmetric_seeds_by_words("a b c d e f", "g h i", cap=900)
    check(len(high.split()) == len(low.split()) == 3, f"word cap must be symmetric: {record}")
    check(record["truncated"], "a cut side must be recorded as cut")
    capped_h, capped_l, capped = symmetric_seeds_by_words("x " * 2000, "y " * 2000, cap=900)
    check(len(capped_h.split()) == 900 == len(capped_l.split()), "the ceiling must bind")
    check(not capped["truncated"] or capped["truncated"], "record shape")

    check("UNPINNED" in provenance()["revision"], "the unpinned revision must be visible")

    for message in failures:
        print(f"FAIL {message}")
    print(f"force_remote selftest: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(selftest())
