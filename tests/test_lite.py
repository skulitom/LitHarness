import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import lite


def events(text="chapter", usage=None, extra=()):
    return "\n".join(json.dumps(e) for e in [
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        *extra,
        {"type": "turn.completed", "usage": usage if usage is not None else {
            "input_tokens": 25, "cached_input_tokens": 10, "output_tokens": 3}},
    ])


class TransportTests(unittest.TestCase):
    def test_valid_output_and_cache_usage(self):
        self.assertEqual(lite.parse_result(events(), "chapter\n")["input_tokens"], 25)

    def test_refuses_tools_failures_and_mismatched_output(self):
        bad = [events(extra=[{"type": "item.started", "item": {"type": "command_execution"}}]),
               events(extra=[{"type": "turn.failed"}]),
               events(usage={"input_tokens": 1, "cached_input_tokens": 5, "output_tokens": 1}),
               events(usage={"input_tokens": True, "output_tokens": 1}), events("different")]
        for stream in bad:
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                lite.parse_result(stream, "chapter")

    def test_isolates_environment_and_saves_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            def fake_run(argv, **kwargs):
                self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
                self.assertFalse(kwargs["shell"])
                self.assertEqual(list(Path(kwargs["cwd"]).iterdir()), [])
                self.assertIn("--ignore-user-config", argv)
                self.assertIn("features.shell_tool=false", argv)
                self.assertIn("project_doc_max_bytes=0", argv)
                Path(argv[argv.index("--output-last-message") + 1]).write_text("chapter")
                return subprocess.CompletedProcess(argv, 0, events(), "")
            with patch.dict(lite.os.environ, {"OPENAI_API_KEY": "test-do-not-inherit"}), \
                 patch.object(lite.subprocess, "run", side_effect=fake_run):
                result, _ = lite.complete("brief", root, binary=Path("codex.exe"),
                                          model="model", effort="medium")
            self.assertEqual(result, "chapter")
            receipt = json.loads((root / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "completed")
            self.assertGreaterEqual(receipt["seconds"], 0)

    def test_timeout_retains_partial_logs_with_unknown_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            with patch.object(lite.subprocess, "run", side_effect=subprocess.TimeoutExpired(
                "codex", 1, output=b"partial", stderr=b"problem")), self.assertRaises(subprocess.TimeoutExpired):
                lite.complete("brief", root, binary=Path("codex.exe"), model="m", effort="medium")
            receipt = json.loads((root / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertIsNone(receipt["usage"])
            self.assertEqual((root / "events.jsonl").read_text(), "partial")


class GenerationTests(unittest.TestCase):
    def test_resume_retains_plan_and_failure_then_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            binary = Path(tmp) / "codex.exe"
            binary.write_bytes(b"fake binary")
            args = (root, "story brief", "", 500, binary, "m", "medium")
            with patch.object(lite, "complete", side_effect=[("plan", {}), ValueError("transport")]):
                with self.assertRaises(ValueError):
                    lite.generate(*args)
            self.assertEqual((root / "plan.md").read_text(), "plan")
            self.assertFalse((root / ".running").exists())
            with patch.object(lite, "complete", return_value=("word " * 500, {})) as provider:
                result = lite.generate(*args, resume=True)
                self.assertEqual(provider.call_count, 1)
                self.assertIn("plan", provider.call_args.args[0])
            self.assertEqual(result["word_count"], 500)
            self.assertEqual(len(result["attempts"]), 3)
            with patch.object(lite, "complete") as provider:
                lite.generate(*args, resume=True)
                provider.assert_not_called()
            (root / "chapter.md").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                lite.generate(*args, resume=True)

    def test_existing_directory_and_changed_brief_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            binary = Path(tmp) / "codex.exe"
            binary.write_bytes(b"binary")
            args = (root, "brief", "", 500, binary, "m", "medium")
            with patch.object(lite, "complete", return_value=("content", {})):
                lite.generate(*args)
            with self.assertRaises(FileExistsError):
                lite.generate(*args)
            with self.assertRaisesRegex(ValueError, "changed"):
                lite.generate(root, "changed", "", 500, binary, "m", "medium", resume=True)

    def test_invalid_request_does_not_create_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            with self.assertRaises(ValueError):
                lite.generate(root, "", "", 500, Path("missing"), "m", "medium")
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
