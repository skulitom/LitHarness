"""The CLI transport carries the prompt on stdin, and Windows is why. No call is made.

The sim-readership pilot of 2026-08-30 lost 380 of its 400 planned C-arm sessions and 12 of
its 40 recognition probes to one line: `elicit._call_cli` passed the whole prompt as an argv
element. Windows caps a command line at 32,767 characters, `subprocess.run` raised `OSError`
above it, and `_call_cli` turned that into a `refused` record it deliberately does not cache —
so a request too large to *send* left no trace and the arm finished short while reporting as
a finished arm. The threshold was sharp enough to reconstruct from the raw cache: the two
pairs whose stage-1 command lines measured 26,305 and 31,651 characters bought sessions, the
next-smallest at 35,204 bought none, and the 31,651 pair lost every stage-2 call at 33,727.

`providers/cli.py::subprocess_runner` had already been moved to stdin for the same ceiling on
the generation side (measured at a 35,714-character prompt). This file pins the research
transport at the same place.

What this file does not establish: that `claude` is installed, reachable, or answers — the
subprocess is replaced, nothing is spent, and no network is touched.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

elicit = pytest.importorskip("elicit", reason="research module; imported by path")

#: `CreateProcess`'s documented lpCommandLine ceiling.
WINDOWS_COMMAND_LINE_LIMIT = 32_767


def _capture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace `subprocess.run` inside elicit and record what the transport handed it."""
    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        seen["argv"] = list(argv)
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            argv, 0, '{"result": "ok", "stop_reason": "end_turn", "total_cost_usd": 0.0}', ""
        )

    monkeypatch.setattr(elicit.subprocess, "run", fake_run)
    return seen


def _elicitor(tmp_path: Any) -> Any:
    return elicit.Elicitor(
        cache_path=tmp_path / "raw.jsonl", model="claude-haiku-4-5", transport="cli"
    )


def test_the_prompt_travels_on_stdin_and_never_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    seen = _capture(monkeypatch)
    prompt = "a distinctive marker phrase the argv must not contain"
    with _elicitor(tmp_path) as elicitor:
        elicitor.ask_raw(
            "sys", [{"role": "user", "content": prompt}], schema=None, max_tokens=16,
            tag={"stage": "test"}, sample=1,
        )
    argv, kwargs = seen["argv"], seen["kwargs"]
    assert prompt in kwargs["input"], "the prompt is what goes down the pipe"
    assert not any(prompt in arg for arg in argv), "and it is on no argument"
    assert argv[:2] == ["claude", "-p"], "`-p` with no positional prompt reads stdin"
    assert argv[2].startswith("--"), "nothing sits between `-p` and the flags"
    assert "stdin" not in kwargs, "`input` and a closed stdin cannot both be passed"


def test_a_prompt_far_over_the_windows_ceiling_still_leaves_a_sendable_command_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """The pilot's largest C-arm cell was ~71,000 characters; this is larger still."""
    seen = _capture(monkeypatch)
    prompt = "word " * 20_000  # 100,000 characters, over 3x the ceiling
    with _elicitor(tmp_path) as elicitor:
        elicitor.ask_raw(
            "sys", [{"role": "user", "content": prompt}], schema=None, max_tokens=16,
            tag={"stage": "test"}, sample=2,
        )
    rendered = subprocess.list2cmdline(seen["argv"])
    assert len(seen["kwargs"]["input"]) > WINDOWS_COMMAND_LINE_LIMIT
    assert len(rendered) < WINDOWS_COMMAND_LINE_LIMIT, (
        "the command line must stay sendable however long the prompt is; "
        f"rendered {len(rendered)} characters"
    )


def test_the_schema_instruction_still_rides_the_system_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """The stdin move must not disturb the CLI's substitute for structured output."""
    seen = _capture(monkeypatch)
    schema = {"type": "object", "properties": {"continue": {"enum": ["A", "B"]}}}
    with _elicitor(tmp_path) as elicitor:
        elicitor.ask_raw(
            "sys", [{"role": "user", "content": "q"}], schema=schema, max_tokens=16,
            tag={"stage": "test"}, sample=3,
        )
    system = seen["argv"][seen["argv"].index("--system-prompt") + 1]
    assert system.startswith("sys")
    assert '"continue"' in system, "the schema is appended to the system prompt, as before"
    for flag in elicit.CLI_HARDENING:
        assert flag in seen["argv"], "the CLAUDE.md-suppression flags survive the move"
