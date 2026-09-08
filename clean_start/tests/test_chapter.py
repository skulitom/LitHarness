"""Offline transport tests. These cannot call a model."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clean_start import chapter


class ChapterTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.executable = self.root / "claude.exe"
        self.executable.touch()
        self.out = self.root / "run"
        self.calls = []
        self.text = "# Chapter 1\n\nA café, a door—and 火.\n\n  "
        self.login = {"loggedIn": True, "authMethod": "claude.ai", "email": "private"}
        self.envelope = {
            "is_error": False, "subtype": "success", "stop_reason": "end_turn",
            "num_turns": 1, "result": self.text, "modelUsage": {chapter.MODEL: {}},
        }
        self.generation_error = None

    def fake(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        self.assertEqual(list(kwargs["cwd"].iterdir()), [])
        if "--version" in argv:
            output = "2.1.263"
        elif "auth" in argv:
            output = json.dumps(self.login)
        else:
            if self.generation_error:
                raise self.generation_error
            output = json.dumps(self.envelope)
        return subprocess.CompletedProcess(argv, 0, output.encode("utf-8"), b"")

    def generate(self, **kwargs):
        with patch.object(chapter, "invoke", self.fake):
            return chapter.generate(self.executable, self.out, "My fresh brief. 火", **kwargs)

    def test_first_response_is_exact_and_request_is_isolated(self):
        self.generate()
        self.assertEqual((self.out / "chapter.md").read_bytes(), self.text.encode("utf-8"))
        self.assertEqual(len(self.calls), 3)
        argv, options = self.calls[-1]
        self.assertEqual(options["payload"], "My fresh brief. 火")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--max-turns") + 1], "1")
        self.assertEqual(argv[argv.index("--mcp-config") + 1], '{"mcpServers":{}}')
        self.assertIn("--safe-mode", argv)
        self.assertNotIn("--bare", argv)
        self.assertNotIn("--fallback-model", argv)
        self.assertNotIn("--append-system-prompt", argv)
        self.assertEqual(argv[argv.index("--system-prompt") + 1], chapter.SYSTEM)
        self.assertIn("--safe-mode", self.calls[1][0])
        self.assertEqual(self.calls[1][0][self.calls[1][0].index("--setting-sources") + 1], "")
        self.assertFalse(options["cwd"].exists())
        result = json.loads((self.out / "result.json").read_bytes())
        self.assertEqual(result["status"], "complete")
        self.assertNotIn("private", (self.out / "result.json").read_text())
        raw = json.loads((self.out / "stdout.json").read_bytes())
        self.assertEqual(raw["result"], self.text)

    def test_environment_drops_keys_routes_and_agent_settings(self):
        safe = chapter.subscription_environment({
            "Path": "bin", "SystemRoot": "windows", "USERPROFILE": "profile",
            "ANTHROPIC_API_KEY": "secret", "ANTHROPICS_API_KEY": "secret",
            "OPENAI_API_KEY": "secret", "ANTHROPIC_BASE_URL": "route",
            "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_OAUTH_TOKEN": "secret",
            "CLAUDE_CODE_SIMPLE": "1", "CLAUDE_CONFIG_DIR": "other-login",
        })
        self.assertEqual(safe, {"Path": "bin", "SystemRoot": "windows", "USERPROFILE": "profile"})

    def test_api_login_or_logged_out_never_generates(self):
        for login in ({"loggedIn": False}, {"loggedIn": True, "authMethod": "api_key"}):
            with self.subTest(login=login):
                self.login = login
                self.out = self.root / str(len(self.calls))
                before = len(self.calls)
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertEqual(len(self.calls) - before, 2)
                self.assertFalse((self.out / "chapter.md").exists())
                self.assertFalse(self.calls[-1][1]["cwd"].exists())

    def test_unsuccessful_results_are_preserved_without_retry_or_chapter(self):
        bad = [
            {"is_error": True}, {"stop_reason": "max_tokens"}, {"result": " "},
            {"num_turns": 2}, {"modelUsage": {}}, {"subtype": "error_max_turns"},
        ]
        original = self.envelope.copy()
        for index, change in enumerate(bad):
            with self.subTest(change=change):
                self.envelope = original | change
                self.out = self.root / str(index)
                before = len(self.calls)
                with self.assertRaises(ValueError):
                    self.generate()
                self.assertEqual(len(self.calls) - before, 3)
                self.assertTrue((self.out / "stdout.json").exists())
                self.assertFalse((self.out / "chapter.md").exists())
                result = json.loads((self.out / "result.json").read_bytes())
                self.assertEqual(result["status"], "failed")

    def test_malformed_and_nonzero_response_rejected(self):
        for output, returncode in ((b"not json", 0), (b"{}", 1), (b"[]", 0)):
            with self.subTest(output=output), self.assertRaises(ValueError):
                chapter.completed_chapter(subprocess.CompletedProcess([], returncode, output))

    def test_timeout_retains_partial_output_and_cleans_workspace(self):
        self.generation_error = subprocess.TimeoutExpired(
            "claude", 900, output=b"partial", stderr=b"failure"
        )
        with self.assertRaisesRegex(ValueError, "No retry"):
            self.generate()
        self.assertEqual((self.out / "stdout.json").read_bytes(), b"partial")
        self.assertEqual((self.out / "stderr.txt").read_bytes(), b"failure")
        self.assertEqual(len(self.calls), 3)
        self.assertFalse(self.calls[-1][1]["cwd"].exists())

    def test_dry_run_and_existing_directory_never_call_claude(self):
        self.generate(dry_run=True)
        self.assertEqual(self.calls, [])
        frozen = (self.out / "request.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.generate()
        self.assertEqual(self.calls, [])
        self.assertEqual((self.out / "request.json").read_bytes(), frozen)

    def test_real_subprocess_roundtrips_utf8_and_shell_literals(self):
        payload = "火 café `echo secret` $(echo secret) & %PATH%\n" * 4000
        response = chapter.invoke(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
            cwd=self.root, env=chapter.subscription_environment(dict(os.environ)), payload=payload,
        )
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(response.stdout, payload.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
