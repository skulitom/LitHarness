"""The last two research CLI call sites carry the prompt on stdin. No call is made.

`test_bt_transport.py` pins `elicit._call_cli` at stdin and its docstring owns the measurement
that forced the move: Windows caps a command line at 32,767 characters (`CreateProcess`), an
over-long argv raises `OSError` before anything is sent, and both modules here read `OSError`
as a retryable transport failure — so a request too large to *send* was retried, failed
identically, and was recorded as a failure that looks like an outage while being correlated
with prompt length. `force_remote._call` (a ~900-word seed plus whatever a passage grew to)
and `writer_states.Generator.generate` (a whole scene inside a retell turn) were the two call
sites still passing the prompt as an argv element; this file pins them at the same place as
`providers/cli.py::subprocess_runner`.

What this file does not establish: that `claude` is installed, reachable, or answers — the
subprocess is replaced, nothing is spent, and no network is touched.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

force_remote = pytest.importorskip(
    "force_remote",
    reason="research module; needs the quality-measurement directory on the path",
)
writer_states = pytest.importorskip(
    "writer_states",
    reason="research module; needs the quality-measurement directory on the path",
)

#: `CreateProcess`'s documented lpCommandLine ceiling.
WINDOWS_COMMAND_LINE_LIMIT = 32_767

#: Larger than any prompt either module has actually rendered, and over 3x the ceiling.
LONG_PROMPT = "word " * 20_000


def _capture(monkeypatch: pytest.MonkeyPatch, module: Any) -> dict[str, Any]:
    """Replace `subprocess.run` inside the module and record what the transport handed it."""
    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        seen["argv"] = list(argv)
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            argv, 0, '{"result": "ok", "stop_reason": "end_turn", "total_cost_usd": 0.0}', ""
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return seen


# ------------------------------------------------------------------ force_remote._call


def test_the_seed_travels_on_stdin_and_never_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture(monkeypatch, force_remote)
    prompt = "a distinctive marker phrase the argv must not contain"
    force_remote._call(prompt, "claude-haiku-4-5")
    argv, kwargs = seen["argv"], seen["kwargs"]
    assert prompt in kwargs["input"], "the seed is what goes down the pipe"
    assert not any(prompt in arg for arg in argv), "and it is on no argument"
    assert argv[:2] == ["claude", "-p"], "`-p` with no positional prompt reads stdin"
    assert argv[2].startswith("--"), "nothing sits between `-p` and the flags"
    assert "stdin" not in kwargs, "`input` and an explicit stdin cannot both be passed"
    system = argv[argv.index("--system-prompt") + 1]
    assert system == force_remote.CONTINUATION_SYSTEM, "the frozen instruction still rides argv"
    for flag in force_remote.CLI_HARDENING:
        assert flag in argv, "the CLAUDE.md-suppression flags survive the move"


def test_a_seed_far_over_the_windows_ceiling_still_leaves_a_sendable_command_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture(monkeypatch, force_remote)
    force_remote._call(LONG_PROMPT, "claude-haiku-4-5")
    rendered = subprocess.list2cmdline(seen["argv"])
    assert len(seen["kwargs"]["input"]) > WINDOWS_COMMAND_LINE_LIMIT
    assert len(rendered) < WINDOWS_COMMAND_LINE_LIMIT, (
        "the command line must stay sendable however long the seed is; "
        f"rendered {len(rendered)} characters"
    )


# ------------------------------------------------- writer_states.Generator.generate


def test_the_retell_prompt_travels_on_stdin_and_never_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    seen = _capture(monkeypatch, writer_states)
    prompt = "a distinctive marker phrase the argv must not contain"
    with writer_states.Generator(tmp_path / "raw.jsonl") as generator:
        record = generator.generate({"scene": "s1", "state": "sober"}, "sys", prompt)
    argv, kwargs = seen["argv"], seen["kwargs"]
    assert prompt in kwargs["input"], "the retell prompt is what goes down the pipe"
    assert not any(prompt in arg for arg in argv), "and it is on no argument"
    assert argv[:2] == ["claude", "-p"], "`-p` with no positional prompt reads stdin"
    assert argv[2].startswith("--"), "nothing sits between `-p` and the flags"
    assert "stdin" not in kwargs, "the old closed stdin is gone; it conflicts with `input`"
    assert argv[argv.index("--system-prompt") + 1] == "sys"
    for flag in writer_states.CLI_HARDENING:
        assert flag in argv, "the CLAUDE.md-suppression flags survive the move"
    assert record["text"] == "ok" and record["refused"] is False, (
        "the envelope still parses after the move"
    )


def test_a_retell_far_over_the_windows_ceiling_still_leaves_a_sendable_command_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    seen = _capture(monkeypatch, writer_states)
    with writer_states.Generator(tmp_path / "raw.jsonl") as generator:
        generator.generate({"scene": "s2", "state": "sober"}, "sys", LONG_PROMPT)
    rendered = subprocess.list2cmdline(seen["argv"])
    assert len(seen["kwargs"]["input"]) > WINDOWS_COMMAND_LINE_LIMIT
    assert len(rendered) < WINDOWS_COMMAND_LINE_LIMIT, (
        "the command line must stay sendable however long the scene is; "
        f"rendered {len(rendered)} characters"
    )
