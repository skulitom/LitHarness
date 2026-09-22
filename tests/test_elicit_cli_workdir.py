"""`elicit`'s `claude -p` runs outside every repository, and a failed call keeps its cause.

What this file pins, with `subprocess.run` replaced and no call made:

* **the working directory.** Every call gets a fresh empty temporary directory that is not the
  process's own and that no git work tree contains, even when the process stands in a
  repository holding a marker file, which is what the milder-dose arm's git probe found reaching
  the model on 2026-09-22 (`cost-that-bites-milder-20260922/AMENDMENT-1.md`). The directory is
  gone afterwards, and a temporary root inside a repository is refused before any process
  starts;
* **nothing sent changes.** The argv, stdin and cache key are what they were before the fix
  (the key below was computed on the unfixed module), so a cached record still replays without
  a call;
* **what the reader sees does, so contexts are never pooled.** A bought answer carries
  `cli_workdir` in its record and not in its key, and a cache holding an answer without it is
  replayed but never bought into, so an arm bought in part from the repository root cannot be
  resumed across the fix; a transport failure in an old cache blocks nothing;
* **no git location variable reaches the child**, and when none is set the environment is
  inherited unchanged;
* **the failure detail.** A failed call's reason carries the envelope's cause rather than its
  first line of boilerplate keys, never a success envelope's answer, and the first 2,000
  characters of stdout and stderr are kept in `failure_details` and in the caller's
  `failure_log`, never in the cache (§235).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

elicit = pytest.importorskip(
    "elicit",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

SYSTEM = "You are a reader."
SCHEMA = {
    "type": "object",
    "properties": {"action": {"type": "string"}},
    "required": ["action"],
    "additionalProperties": False,
}
TURNS: list[dict[str, Any]] = [
    {"role": "user", "content": [
        {"type": "text", "text": "Opening A...", "cache_control": {"type": "ephemeral"}}]},
    {"role": "assistant", "content": '{"action": "read", "book": "A"}'},
    {"role": "user", "content": "More."},
]
#: The key this request had on the unfixed module (2026-09-22, before the working-directory
#: change), and the argv and stdin it sent then.
KEY_BEFORE_THE_FIX = "683ec7fbf88570aa6d8e:7"
ARGV_BEFORE_THE_FIX = [
    "claude", "-p", "--output-format", "json", "--model", "claude-haiku-4-5",
    "--system-prompt",
    SYSTEM + "\n\nReply with a single JSON object conforming to this schema and nothing else "
    "— no prose, no code fence:\n" + json.dumps(SCHEMA, sort_keys=True),
    *elicit.CLI_HARDENING,
]
STDIN_BEFORE_THE_FIX = (
    'Opening A...\n\n---\n\nYour answer was:\n\n{"action": "read", "book": "A"}\n\n---\n\nMore.'
)
ENVELOPE = json.dumps({
    "type": "result", "subtype": "success", "is_error": False,
    "result": '{"action": "read"}', "stop_reason": "end_turn", "total_cost_usd": 0.001,
    "modelUsage": {"claude-haiku-4-5": {"inputTokens": 5, "outputTokens": 2}},
})


def _repository(tmp_path: Path) -> Path:
    """A scratch git work tree holding the marker the arm's git probe asks about."""
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    (repository / "GIT_CONTEXT_LEAKED").write_text("context probe\n", encoding="utf-8")
    return repository


def _ask(elicitor: Any, sample: int = 7) -> dict[str, Any]:
    record: dict[str, Any] = elicitor.ask_raw(
        SYSTEM, TURNS, schema=SCHEMA, max_tokens=60, tag={"stage": "action", "feed": "f"},
        sample=sample,
    )
    return record


class Recorder:
    """`subprocess.run` as the transport calls it: records what it was handed and the state of
    the directory it was told to run in, while the call is in flight."""

    def __init__(self, completed: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.completed = completed

    def __call__(self, argv: list[str], **kwargs: Any) -> Any:
        cwd = kwargs.get("cwd")
        directory = Path(cwd).resolve() if cwd is not None else None
        self.calls.append({
            "argv": list(argv),
            "input": kwargs.get("input"),
            "cwd": directory,
            "process_cwd": Path.cwd().resolve(),
            "existed": directory is not None and directory.is_dir(),
            "entries": sorted(p.name for p in directory.iterdir()) if directory else None,
            "env": kwargs.get("env", "absent"),
        })
        if self.completed is not None:
            return self.completed(argv)
        return subprocess.CompletedProcess(argv, 0, ENVELOPE, "")


def test_every_call_runs_in_a_fresh_empty_directory_outside_any_git_work_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.chdir(repository)
    recorder = Recorder()
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    with elicit.Elicitor(tmp_path / "raw.jsonl", model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        _ask(elicitor, sample=1)
        _ask(elicitor, sample=2)
    assert len(recorder.calls) == 2
    directories = [call["cwd"] for call in recorder.calls]
    for call in recorder.calls:
        directory = call["cwd"]
        assert directory is not None, "the call inherited the process's working directory"
        assert call["existed"] and call["entries"] == []
        assert call["process_cwd"] == repository.resolve()
        assert directory != call["process_cwd"]
        assert repository.resolve() not in (directory, *directory.parents)
        assert not any((path / ".git").exists() for path in (directory, *directory.parents))
        assert elicit._git_work_tree_at(directory) is None
        assert directory.name.startswith(elicit.CLI_WORKDIR_PREFIX)
    assert directories[0] != directories[1]
    assert not any(directory.exists() for directory in directories)


def test_the_argv_stdin_and_cache_key_are_the_ones_sent_before_the_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    cache = tmp_path / "raw.jsonl"
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        record = _ask(elicitor)
    assert record["key"] == KEY_BEFORE_THE_FIX
    assert recorder.calls[0]["argv"] == ARGV_BEFORE_THE_FIX
    assert recorder.calls[0]["input"] == STDIN_BEFORE_THE_FIX
    # A record cached under the old key replays without starting a process.
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        again = _ask(elicitor)
        assert elicitor.replayed == 1 and elicitor.api_calls == 0
    assert again["text"] == record["text"]
    assert len(recorder.calls) == 1


def test_a_bought_answer_carries_the_workdir_mark_in_its_record_and_not_in_its_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(elicit.subprocess, "run", Recorder())
    cache = tmp_path / "raw.jsonl"
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        record = _ask(elicitor)
        assert elicitor.unmarked_answers == 0
    assert record["key"] == KEY_BEFORE_THE_FIX
    assert record[elicit.CLI_WORKDIR_FIELD] == elicit.CLI_WORKDIR_MARK
    [line] = cache.read_text(encoding="utf-8").splitlines()
    assert json.loads(line)[elicit.CLI_WORKDIR_FIELD] == elicit.CLI_WORKDIR_MARK
    # The next invocation replays its own marked answers and may buy beside them.
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        assert elicitor.unmarked_answers == 0
        _ask(elicitor)
        _ask(elicitor, sample=8)
        assert elicitor.replayed == 1 and elicitor.api_calls == 1


def _pre_fix_answer(key: str) -> dict[str, Any]:
    """A record as the unfixed transport wrote it: an answer, and no working-directory mark."""
    return {"stage": "action", "feed": "f", "key": key, "model": "claude-haiku-4-5",
            "text": '{"action": "read"}', "refused": False, "stop_reason": "end_turn",
            "usage": {"input": 5, "output": 2, "cache_read": 0, "cache_write": 0,
                      "equivalent_usd": 0.001}}


def test_a_cache_holding_pre_fix_answers_is_replayed_and_never_bought_into(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    cache = tmp_path / "raw.jsonl"
    cache.write_text(json.dumps(_pre_fix_answer(KEY_BEFORE_THE_FIX)) + "\n", encoding="utf-8")
    before = cache.read_bytes()
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        assert elicitor.unmarked_answers == 1
        replayed = _ask(elicitor)
        assert replayed["text"] == '{"action": "read"}' and elicitor.replayed == 1
        with pytest.raises(RuntimeError, match="without the 'cli_workdir' mark"):
            _ask(elicitor, sample=8)
        assert elicitor.api_calls == 0 and elicitor.transport_failures == 0
    assert recorder.calls == [], "the refusal comes before any process starts"
    assert cache.read_bytes() == before
    # A dry run of the same cache still replays, and stands in for the rest without a call.
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None, transport="cli",
                         dry_run=True) as elicitor:
        assert _ask(elicitor, sample=8)["dry_run"] is True
    assert recorder.calls == []


def test_a_transport_failure_in_an_old_cache_blocks_no_purchase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    cache = tmp_path / "raw.jsonl"
    failure = {**_pre_fix_answer(KEY_BEFORE_THE_FIX), "text": "", "refused": True,
               "stop_reason": "cli_error:rc=1", "usage": {}}
    cache.write_text(json.dumps(failure) + "\n", encoding="utf-8")
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        assert elicitor.unmarked_answers == 0
        record = _ask(elicitor)
    assert len(recorder.calls) == 1
    assert record[elicit.CLI_WORKDIR_FIELD] == elicit.CLI_WORKDIR_MARK


def test_git_location_variables_never_reach_the_child_and_nothing_else_moves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    for name in elicit.GIT_LOCATION_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    recorder = Recorder()
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    with elicit.Elicitor(tmp_path / "raw.jsonl", model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        _ask(elicitor, sample=1)
        monkeypatch.setenv("GIT_DIR", str(repository / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(repository))
        monkeypatch.setenv("ELICIT_TEST_KEPT", "kept")
        _ask(elicitor, sample=2)
    unset, child = recorder.calls[0]["env"], recorder.calls[1]["env"]
    assert unset is None, "with no git location variable the environment is inherited as is"
    assert isinstance(child, dict)
    assert not {name.upper() for name in child} & elicit.GIT_LOCATION_VARIABLES
    assert child["ELICIT_TEST_KEPT"] == "kept"
    assert recorder.calls[0]["argv"] == recorder.calls[1]["argv"]


def test_a_temporary_root_inside_a_repository_is_refused_before_any_process_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    inside = repository / "tmp"
    inside.mkdir()
    monkeypatch.setattr(elicit.tempfile, "tempdir", str(inside))
    recorder = Recorder()
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    with elicit.Elicitor(tmp_path / "raw.jsonl", model="claude-haiku-4-5", spot_model=None,
                         transport="cli") as elicitor:
        with pytest.raises(RuntimeError, match="inside the git work tree"):
            _ask(elicitor)
        assert elicitor.api_calls == 0 and elicitor.transport_failures == 0
    assert recorder.calls == []
    assert list(inside.iterdir()) == []


def _failed_envelope(cause: str, padding: int) -> str:
    """An error envelope shaped like milder-v4's five: boilerplate keys first, the cause last."""
    return json.dumps({
        "duration_api_ms": 0, "stop_reason": "stop_sequence", "session_id": "s" * 36,
        "padding": "p" * padding, "type": "result", "subtype": "success", "is_error": True,
        "result": cause,
    })


def test_a_failed_call_keeps_its_cause_and_its_envelope_and_is_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdout = _failed_envelope("Claude AI usage limit reached|1758580000", padding=3000)
    recorder = Recorder(lambda argv: subprocess.CompletedProcess(argv, 1, stdout, ""))
    monkeypatch.setattr(elicit.subprocess, "run", recorder)
    cache = tmp_path / "raw.jsonl"
    log = tmp_path / "failures.jsonl"
    with elicit.Elicitor(cache, model="claude-haiku-4-5", spot_model=None, transport="cli",
                         failure_log=log) as elicitor:
        record = _ask(elicitor)
        reason = record["stop_reason"]
        assert elicit._is_transport_failure(reason)
        assert reason.startswith("cli_error:rc=1:Claude AI usage limit reached")
        assert "duration_api_ms" not in reason
        assert len(reason) <= len("cli_error:rc=1:") + elicit._CLI_STDERR_CHARS
        assert elicitor.failure_reasons[reason] == 1 and elicitor.transport_failures == 1
        assert elicitor._cache == {}
        [entry] = elicitor.failure_details
    assert entry["key"] == record["key"] and entry["stop_reason"] == reason
    assert entry["tag"] == {"stage": "action", "feed": "f"}
    detail = entry["detail"]
    assert detail["returncode"] == 1
    assert detail["stdout"] == stdout[: elicit._CLI_FAILURE_DETAIL_CHARS]
    assert detail["stdout_chars"] == len(stdout) > elicit._CLI_FAILURE_DETAIL_CHARS
    assert detail["stderr"] == "" and detail["stderr_chars"] == 0
    [line] = log.read_text(encoding="utf-8").splitlines()
    assert json.loads(line) == entry
    assert not cache.exists(), "a failure is not an answer: nothing is cached (§235)"


def test_a_short_envelope_with_its_cause_last_is_kept_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdout = _failed_envelope("API Error: 529 overloaded", padding=0)
    monkeypatch.setattr(elicit.subprocess, "run",
                        Recorder(lambda argv: subprocess.CompletedProcess(argv, 1, stdout, "")))
    with elicit.Elicitor(tmp_path / "raw.jsonl", model="m", spot_model=None,
                         transport="cli") as elicitor:
        record = _ask(elicitor)
        assert record["stop_reason"] == "cli_error:rc=1:API Error: 529 overloaded"
        assert elicitor.failure_details[0]["detail"]["stdout"] == stdout
    assert elicitor.failure_log is None


def test_a_success_envelope_beside_a_failed_exit_never_puts_the_answer_in_the_reason() -> None:
    answer = '{"action": "read", "book": "the-target-book"}'
    stdout = json.dumps({"result": answer, "type": "result", "subtype": "success",
                         "is_error": False})
    reason = elicit._cli_failure_reason(subprocess.CompletedProcess(["claude"], 1, stdout, ""))
    assert reason == "cli_error:rc=1:an envelope that names no error"
    assert "the-target-book" not in reason
    assert elicit._envelope_cause({"result": answer, "subtype": "success"}) == ""
    cause = elicit._envelope_cause({"result": "overloaded", "subtype": "error_during_execution"})
    assert cause == "error_during_execution overloaded"


def test_stderr_still_wins_over_the_envelope_for_the_reason() -> None:
    completed = subprocess.CompletedProcess(
        ["claude"], 1, _failed_envelope("from stdout", 0), "You've hit your usage limit\n"
    )
    assert elicit._cli_failure_reason(completed) == "cli_error:rc=1:You've hit your usage limit"


def test_a_timeout_keeps_its_partial_output_and_is_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timed_out(argv: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(argv, 300, output=b"partial \xe2\x80\x94 out",
                                        stderr="still thinking")

    monkeypatch.setattr(elicit.subprocess, "run", timed_out)
    log = tmp_path / "failures.jsonl"
    log.write_text('{"torn": ', encoding="utf-8")  # a kill mid-append left this
    cache = tmp_path / "raw.jsonl"
    with elicit.Elicitor(cache, model="m", spot_model=None, transport="cli",
                         failure_log=log) as elicitor:
        record = _ask(elicitor)
        assert record["stop_reason"] == "transport_error:TimeoutExpired"
        [entry] = elicitor.failure_details
    assert entry["detail"]["error"] == "TimeoutExpired"
    assert entry["detail"]["stdout"] == "partial — out"
    assert entry["detail"]["stderr"] == "still thinking"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == '{"torn": ' and json.loads(lines[1]) == entry
    assert not cache.exists()


def test_the_working_directory_check_is_stricter_than_git(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    nested = worktree / "a" / "b"
    nested.mkdir(parents=True)
    assert elicit._git_work_tree_at(nested) == worktree  # a worktree's `.git` is a file
    assert elicit._git_work_tree_at(tmp_path / "elsewhere") is None
