import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from litharness import files


class WriteTests(unittest.TestCase):
    def test_stored_bytes_are_exact_and_their_hash_is_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "chapter.md"
            stored = files.write(path, "one\ntwo’\n")
            self.assertEqual(path.read_bytes(), "one\ntwo’\n".encode())
            self.assertEqual(stored, files.digest(path))
            self.assertEqual([p.name for p in path.parent.iterdir()], ["chapter.md"])

    def test_permission_error_is_retried_then_raised(self):
        real = os.replace
        with tempfile.TemporaryDirectory() as tmp:
            flaky = iter([PermissionError(), PermissionError()])
            def replace(*args):
                error = next(flaky, None)
                if error:
                    raise error
                return real(*args)
            with patch.object(files.os, "replace", side_effect=replace), patch.object(files.time, "sleep"):
                files.write(Path(tmp) / "a.txt", "x")
            with patch.object(files.os, "replace", side_effect=PermissionError()), \
                    patch.object(files.time, "sleep"), self.assertRaises(PermissionError):
                files.write(Path(tmp) / "b.txt", "x")


class LockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lock = Path(self.tmp.name) / "runs" / "box.lock"

    def test_holder_line_and_refusal_while_alive(self):
        files.lock(self.lock, "next slot")
        line = (self.lock / "holder").read_text()
        self.assertRegex(line, rf"^litharness pid={os.getpid()} start=\S+ next slot \d{{8}}T\d{{6}}Z\n$")
        with self.assertRaises(files.Held):
            files.lock(self.lock, "next other")
        files.unlock(self.lock)
        self.assertFalse(self.lock.exists())

    def test_a_finished_holder_is_cleared_and_a_foreign_one_never(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        start = files.probe(child.pid)[1]
        child.kill()
        child.wait()
        self.lock.mkdir(parents=True)
        (self.lock / "holder").write_text(f"litharness pid={child.pid} start={start} next slot 20260927T000000Z\n")
        files.lock(self.lock, "next slot")
        files.unlock(self.lock)
        self.lock.mkdir()
        (self.lock / "holder").write_text("claude-session: corpus pass, 20:10\n")
        with self.assertRaisesRegex(files.Held, "corpus pass"):
            files.lock(self.lock, "next slot")

    def test_a_reused_pid_does_not_keep_a_lock(self):
        self.assertFalse(files.gone(os.getpid(), files.probe(os.getpid())[1]))
        if files.probe(os.getpid())[1] != "-":
            self.assertTrue(files.gone(os.getpid(), "1"))

    def test_box_lock_is_found_in_the_main_checkout_from_a_worktree(self):
        root = Path(self.tmp.name)
        gitdir = root / "main" / ".git" / "worktrees" / "w"
        gitdir.mkdir(parents=True)
        (gitdir / "commondir").write_text("../..\n")
        (root / "w" / "pkg").mkdir(parents=True)
        (root / "w" / ".git").write_text(f"gitdir: {gitdir}\n")
        expected = (root / "main" / "runs" / "box.lock").resolve()
        self.assertEqual(files.box_lock(root / "w" / "pkg" / "files.py"), expected)
        self.assertEqual(files.box_lock(root / "main" / "pkg" / "files.py"), expected)
