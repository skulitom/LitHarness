import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from litharness import files, transport


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
