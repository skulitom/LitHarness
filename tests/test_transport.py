import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from litharness import files, transport
from litharness.transport import FALLBACK


def events(text="chapter", usage=None, extra=()):
    return "\n".join(json.dumps(e) for e in [
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        *extra,
        {"type": "turn.completed", "usage": usage if usage is not None else {
            "input_tokens": 25, "cached_input_tokens": 10, "output_tokens": 3}},
    ])


def fake(text="chapter", stdout=None, code=0, seen=None):
    def run(argv, **kwargs):
        if seen is not None:
            seen.update(argv=argv, **kwargs, listing=list(Path(kwargs["cwd"]).iterdir()))
        Path(argv[argv.index("--output-last-message") + 1]).write_bytes(text.encode())
        return subprocess.CompletedProcess(argv, code, (events(text) if stdout is None else stdout).encode(), b"")
    return run


def call(root, runner, **kwargs):
    return transport.codex("brief\nline\n", root, system="system", model="m", effort="medium",
                           binary=Path("codex.exe"), runner=runner, **kwargs)


class ParseTests(unittest.TestCase):
    def test_valid_output_and_cache_usage(self):
        self.assertEqual(transport.parse_result(events(), "chapter\n")["input_tokens"], 25)

    def test_refuses_tools_failures_and_mismatched_output(self):
        bad = [events(extra=[{"type": "item.started", "item": {"type": "command_execution"}}]),
               events(extra=[{"type": "turn.failed"}]),
               events(usage={"input_tokens": 1, "cached_input_tokens": 5, "output_tokens": 1}),
               events(usage={"input_tokens": True, "output_tokens": 1}), events("different")]
        for stream in bad:
            with self.subTest(stream=stream), self.assertRaises(transport.Fault):
                transport.parse_result(stream, "chapter")


class CodexTests(unittest.TestCase):
    def test_isolates_environment_and_stores_hash_true_receipts(self):
        seen = {}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"OPENAI_API_KEY": "do-not-inherit", "GIT_DIR": "x", "GIT_WORK_TREE": "y"}):
            root = Path(tmp) / "attempt"
            text, receipt = call(root, fake(seen=seen))
            self.assertEqual(text, "chapter")
            self.assertEqual(seen["input"], b"brief\nline\n")
            self.assertEqual((root / "prompt.txt").read_bytes(), b"brief\nline\n")
            stored = files.load(root / "receipt.json")
            self.assertEqual(stored["status"], "completed")
            self.assertEqual(stored["prompt_sha256"], files.digest(root / "prompt.txt"))
            self.assertEqual(stored["output_sha256"], files.digest(root / "final.md"))
        for key in ("OPENAI_API_KEY", "GIT_DIR", "GIT_WORK_TREE"):
            self.assertNotIn(key, seen["env"])
        self.assertFalse(seen["shell"])
        self.assertEqual(seen["listing"], [])
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "features.shell_tool=false",
                     "project_doc_max_bytes=0", 'history.persistence="none"'):
            self.assertIn(flag, seen["argv"])
        self.assertEqual(seen["argv"][seen["argv"].index("--cd") + 1], seen["cwd"])

    def test_timeout_retains_partial_logs_with_unknown_usage(self):
        def slow(argv, **kwargs):
            raise subprocess.TimeoutExpired("codex", 1, output=b"partial", stderr=b"problem")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            with self.assertRaises(transport.Fault):
                call(root, slow)
            receipt = files.load(root / "receipt.json")
            self.assertEqual(receipt["status"], "failed")
            self.assertIsNone(receipt["usage"])
            self.assertGreaterEqual(receipt["seconds"], 0)
            self.assertEqual((root / "events.jsonl").read_bytes(), b"partial")

    def test_nonzero_exit_and_existing_directory_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(transport.Fault):
                call(Path(tmp) / "a", fake(code=3))
            with self.assertRaises(FileExistsError):
                call(Path(tmp) / "a", fake())

    def test_refuses_a_working_directory_inside_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            with self.assertRaises(transport.Fault):
                transport.no_git(Path(tmp) / "inner")
            self.assertEqual(transport.no_git(Path(tmp).parent), Path(tmp).parent)

    def test_refuses_shell_wrappers(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "codex.cmd"
            wrapper.write_text("@echo off")
            with self.assertRaises(ValueError):
                transport.native_binary(str(wrapper))


def stream(events_list):
    return "\n".join(json.dumps(e) for e in events_list)


class RobustnessTests(unittest.TestCase):
    def test_leading_reconnect_notices_are_tolerated_within_one_turn(self):
        start = [{"type": "thread.started"}, {"type": "turn.started"}]
        again = {"type": "error", "message": "Reconnecting... 2/5 (request timed out)"}
        fallback = {"type": "item.completed", "item": {"type": "error", "message": FALLBACK}}
        body = [json.loads(line) for line in events().splitlines()]
        self.assertEqual(transport.parse_result(stream(start + [again, again, fallback] + body), "chapter")["output_tokens"], 3)
        for bad in (start + body[:1] + [again] + body[1:], start + [again, start[1]] + body,
                    start + [{"type": "error", "message": "unavailable"}] + body, [again] + body):
            with self.subTest(bad=bad), self.assertRaises(transport.Fault):
                transport.parse_result(stream(bad), "chapter")

    def test_preflight_needs_a_chatgpt_login_and_reads_the_version_once(self):
        seen = []
        def run(argv, **kwargs):
            seen.append(argv[-1])
            login = b"Logged in using ChatGPT\n" if "chatgpt" in str(kwargs.get("env", {}).get("MARK")) else b"Logged in using an API key\n"
            return subprocess.CompletedProcess(argv, 0, b"codex-cli 9.9\n" if argv[-1] == "--version" else b"", login)
        with patch.dict(transport.CLI, clear=True), patch.dict(os.environ, {"MARK": "chatgpt"}), \
                patch.object(transport, "ENV_KEYS", transport.ENV_KEYS | {"MARK"}):
            self.assertEqual(transport.preflight(Path("x"), run), "codex-cli 9.9")
            transport.preflight(Path("x"), run)
        self.assertEqual(seen, ["status", "--version"])
        with patch.dict(transport.CLI, clear=True), self.assertRaises(transport.Fault):
            transport.preflight(Path("x"), run)

    def test_canary_pins_the_version_only_when_nothing_leaks(self):
        def run(argv, input=None, **kwargs):
            if input is None:
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            control = re.search(r"CONTROL-(\w+)", input.decode())[1]
            leak = re.search(r"CANARY-\w+", (Path(kwargs["cwd"]) / "AGENTS.md").read_text())[0] if self.leaky else "NONE"
            return fake(f"CONTROL-{control}\n{leak}")(argv, input=input, **kwargs)
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"LITHARNESS_HOME": home}), \
                patch.dict(transport.CLI, {str(Path(home) / "codex.exe"): "codex-cli 9"}):
            binary = Path(home) / "codex.exe"
            binary.write_bytes(b"fake")
            self.leaky = True
            self.assertEqual(transport.canary(binary, "m", "medium", run), ["agents"])
            self.assertFalse((Path(home) / "canary.json").exists())
            self.leaky = False
            self.assertEqual(transport.canary(binary, "m", "medium", run), [])
            self.assertEqual(files.load(Path(home) / "canary.json")["codex"]["version"], "codex-cli 9")
