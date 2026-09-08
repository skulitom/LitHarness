import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clean_start import codex_chapter as codex


class CodexTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = self.root / "codex.exe"
        self.binary.touch()
        self.out = self.root / "output"
        self.calls = []
        self.auth_ok = True
        self.text = "# First\n\nAn unopened door—火.\n"
        self.events = [
            {"type": "thread.started", "thread_id": "test"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": self.text}},
            {"type": "turn.completed", "usage": {"output_tokens": 20}},
        ]

    def fake(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if "--version" in argv:
            value = b"codex-cli 0.153.4"
        elif "login" in argv:
            self.assertNotIn("--ignore-user-config", argv)
            value = b"Logged in using ChatGPT" if self.auth_ok else b"Logged in using an API key"
        else:
            self.assertEqual(kwargs["payload"], "Fresh brief")
            self.assertEqual(list(kwargs["cwd"].iterdir()), [])
            (self.out / "response.txt").write_bytes(self.text.encode("utf-8"))
            value = "\n".join(json.dumps(event) for event in self.events).encode("utf-8")
        return subprocess.CompletedProcess(argv, 0, value, b"")

    def test_success_preserves_first_response_and_isolation(self):
        with patch.object(codex, "invoke", self.fake):
            codex.generate(self.binary, self.out, "Fresh brief")
        self.assertEqual((self.out / "chapter.md").read_bytes(), self.text.encode("utf-8"))
        argv, options = self.calls[-1]
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("features.shell_tool=false", argv)
        self.assertIn('forced_login_method="chatgpt"', argv)
        self.assertIn("project_doc_max_bytes=0", argv)
        for key in (
            "features.code_mode", "features.view_image", "features.browser_use",
            "features.browser_use_external", "features.browser_use_full_cdp_access",
            "features.in_app_browser", "features.computer_use", "features.image_generation",
            "features.sleep_tool", "features.goals", "features.skill_search",
            "features.tool_suggest", "features.workspace_dependencies",
            "features.skill_mcp_dependency_install", "features.multi_agent_v2",
            "tools.update_plan.enabled", "tools.experimental_request_user_input.enabled",
            "skills.include_instructions", "skills.bundled.enabled",
        ):
            self.assertIn(f"{key}=false", argv)
        request = json.loads((self.out / "request.json").read_bytes())
        self.assertEqual(request["builtin_controls"], "unused-builtins-disabled.v1")
        self.assertEqual(request["system"], codex.SYSTEM)
        self.assertEqual(request["brief"], "Fresh brief")
        self.assertFalse(options["cwd"].exists())
        self.assertEqual(json.loads((self.out / "result.json").read_bytes())["status"], "complete")

    def test_api_auth_aborts_before_generation_and_no_overwrite(self):
        self.auth_ok = False
        with patch.object(codex, "invoke", self.fake):
            with self.assertRaises(ValueError):
                codex.generate(self.binary, self.out, "Fresh brief")
            with self.assertRaises(FileExistsError):
                codex.generate(self.binary, self.out, "Fresh brief")
        self.assertEqual(len(self.calls), 2)
        self.assertFalse((self.out / "chapter.md").exists())

    def test_incomplete_or_tool_using_results_are_not_chapters(self):
        for extra in (
            {"type": "turn.failed"},
            {"type": "error"},
            {"type": "item.started", "item": {"type": "command_execution"}},
            {"type": "item.completed", "item": {"type": "command_execution"}},
            {"type": "turn.completed"},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                events = "\n".join(json.dumps(e) for e in [*self.events, extra]).encode("utf-8")
                codex.read_result(subprocess.CompletedProcess([], 0, events, b""))


if __name__ == "__main__":
    unittest.main()
