import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from litharness import serial


class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = patch.dict(os.environ, {"LITHARNESS_HOME": self.tmp.name})
        home.start()
        self.addCleanup(home.stop)
        self.brief = Path(self.tmp.name) / "slot.txt"
        self.brief.write_bytes(b"story brief\n")
        self.binary = Path(self.tmp.name) / "codex.exe"
        self.binary.write_bytes(b"fake binary")

    def opening(self, replies, resume=False):
        prompts = []
        def call(prompt, directory, **kwargs):
            prompts.append(prompt)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply, {}
        return serial.opening(self.brief, 500, self.binary, resume, call=call), prompts

    def test_resume_retains_plan_and_failure_then_rejects_tampering(self):
        with self.assertRaises(ValueError):
            self.opening(["plan", ValueError("transport")])
        root = Path(self.tmp.name) / "openings" / "slot-500"
        self.assertEqual((root / "plan.md").read_bytes(), b"plan")
        self.assertFalse((root / "lock").exists())
        (_, result), prompts = self.opening(["word " * 500], resume=True)
        self.assertEqual(len(prompts), 1)
        self.assertIn("plan", prompts[0])
        self.assertEqual(result["word_count"], 500)
        self.assertEqual(len(result["attempts"]), 3)
        _, prompts = self.opening([], resume=True)
        self.assertEqual(prompts, [])
        (root / "chapter.md").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.opening([], resume=True)

    def test_existing_opening_and_changed_brief_are_refused(self):
        self.opening(["content", "content"])
        with self.assertRaises(FileExistsError):
            self.opening([])
        self.brief.write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.opening([], resume=True)

    def test_invalid_request_does_not_create_run(self):
        self.brief.write_bytes(b"  \n")
        with self.assertRaises(ValueError):
            self.opening([])
        self.assertFalse((Path(self.tmp.name) / "openings").exists())

    def test_totals_count_unknown_usage(self):
        rows = [{"usage": {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 2}, "seconds": 1.5},
                {"usage": None, "seconds": 2}]
        self.assertEqual(serial.totals(rows), {"calls": 2, "seconds": 3.5, "unknown_usage_calls": 1,
                                               "input_tokens": 10, "cached_input_tokens": 4,
                                               "output_tokens": 2, "uncached_input_tokens": 6})
