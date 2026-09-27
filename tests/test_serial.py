"""Serial runs through the real transport with a fake CLI: no test spawns a model."""
import contextlib
from functools import partial
import io
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from litharness import __main__ as cli, files, serial, transport
from tests.test_checks import BIBLE, PLAN
from tests.test_transport import events

PROSE = "Elias braced a boot on the seat frame and pulled while the water climbed past his knees."


def plan_for(prompt):
    n = int(re.search(r"Plan chapter (\d+)", prompt)[1])
    return PLAN.replace("1/1 -> 1/2 | movement 1", f"1/{n} -> 1/{n + 1} | movement {min(n, 3)}")


def draft_for(prompt, extra=""):
    n, words = int(re.search(r"Write chapter (\d+)", prompt)[1]), int(re.search(r"Aim for (\d+) words", prompt)[1])
    return "\n\n".join([PROSE] * 3 + [f"[Slots: 1/{n + 1}]"] + [PROSE] * (words // 14) + [extra])


class Fake:
    """A CLI that answers by stage; a reply may be a function of the prompt or an exception."""

    def __init__(self, **replies):
        self.replies, self.asked = {"pitch": BIBLE, "plan": plan_for, "draft": draft_for, **replies}, []

    def __call__(self, argv, input=None, **kwargs):
        prompt = input.decode()
        stage = next(s for s, head in (("pitch", "Develop"), ("plan", "Plan"), ("draft", "Write"), ("rewrite", "Say"))
                     if prompt.startswith(head))
        self.asked.append(stage)
        reply = self.replies[stage]
        reply = reply.pop(0) if isinstance(reply, list) else reply
        if isinstance(reply, Exception):
            return subprocess.CompletedProcess(argv, 1, b"", b"boom")
        text = reply(prompt) if callable(reply) else reply
        Path(argv[argv.index("--output-last-message") + 1]).write_bytes(text.encode())
        return subprocess.CompletedProcess(argv, 0, events(text).encode(), b"")


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for patcher in (patch.dict(os.environ, {"LITHARNESS_HOME": self.tmp.name}),  # durability is not under test:
                        contextlib.redirect_stdout(io.StringIO()), patch.object(files.os, "fsync")):  # 2 ms a write
            patcher.__enter__()
            self.addCleanup(patcher.__exit__, None, None, None)
        self.brief = Path(self.tmp.name) / "slot.txt"
        self.brief.write_bytes(b"System apocalypse. One Slot each; his holds every skill he can take.\n")
        self.root = serial.folder("slot")

    def run_new(self, fake, words=1500):
        return serial.new("slot", self.brief, words, Path("codex.exe"), "codex-cli 1", partial(transport.codex, runner=fake))

    def run_next(self, fake, n=1):
        return list(serial.next_chapters("slot", n, Path("codex.exe"), partial(transport.codex, runner=fake)))

    def test_pitch_then_chapters_with_code_owned_sheets_and_reports(self):
        fake = Fake()
        self.assertEqual(self.run_new(fake).read_bytes(), BIBLE.encode())
        self.assertEqual(files.read(self.root / "ch00" / "sheet.txt"), "[Rank: Iron]\n[Slots: 1/1]\n")
        self.run_next(fake, 2)
        self.assertEqual(fake.asked, ["pitch", "plan", "draft", "plan", "draft"])
        self.assertEqual(files.read(self.root / "ch02" / "sheet.txt"), "[Rank: Iron]\n[Slots: 1/3]\n")
        receipt = files.load(next((self.root / "ch01" / "calls").glob("draft-d1/receipt.json")))
        self.assertEqual(receipt["output_sha256"], files.digest(self.root / "ch01" / "final.md"))
        self.assertIn("usage: draws plan 1 of 3, draft 1 of 3; 2 calls", files.read(self.root / "ch01" / "report.md"))
        self.assertIn("PREVIOUS CHAPTER", files.read(self.root / "ch02" / "calls" / "plan-d1" / "prompt.txt"))
        self.assertIn("slot: 2 chapters", serial.status("slot"))

    def test_three_failed_draws_stop_with_quotes_and_a_changed_input_opens_draw_four(self):
        fake = Fake(pitch=BIBLE.replace("Age: 26", "Age: 40"))
        with self.assertRaisesRegex(serial.Stop, r"3 draws failed\n  pitch-shape: Age is not 20-29"):
            self.run_new(fake)
        with self.assertRaises(serial.Stop):
            self.run_new(fake)
        self.assertEqual(fake.asked, ["pitch"] * 3)
        files.write(self.root / "brief.md", "System apocalypse, edited by hand.\n")
        fake.replies["pitch"] = BIBLE
        self.run_new(fake)
        self.assertTrue((self.root / "ch00" / "calls" / "pitch-d4" / "final.md").is_file())
        self.assertEqual({k: v for k, v in files.load(self.root / "manifest.json")["stages"]["ch00/pitch"]["draws"][-1].items()
                          if k in ("k", "of")}, {"k": 4, "of": 6})
        self.assertIn("hand-edited: brief.md", serial.status("slot"))

    def test_a_money_word_located_in_our_request_stops_without_a_redraw(self):
        for brief, echo in ((b"He rents a room above the flooded underpass.\n", "paying rent"), (b"He owes Mara.\n", "owed")):
            with self.subTest(echo=echo):
                self.brief.write_bytes(brief)
                fake = Fake(pitch=BIBLE.replace("reading water", f"reading water, {echo}"))
                with self.assertRaisesRegex(serial.Stop, r"located in our request: '\w+' in brief.md:1"):
                    self.run_new(fake)
                with self.assertRaises(serial.Stop):
                    self.run_new(fake)
                self.assertEqual(fake.asked, ["pitch"])
                serial.redraw("slot", 0)
                (self.root / "serial.json").unlink()

    def test_a_kill_after_any_write_resumes_without_buying_anything_twice(self):
        told = "Nobody moved. Nobody spoke. Nothing came. He waited the way he always waited."
        for kill_at in range(1, 12):
            with self.subTest(kill_at=kill_at), tempfile.TemporaryDirectory() as home, \
                    patch.dict(os.environ, {"LITHARNESS_HOME": home}):
                fake, writes, real = Fake(draft=partial(draft_for, extra=told), rewrite="1. Everyone froze.\n"), [0], serial.keep
                def keep(*args):
                    writes[0] += 1
                    real(*args)
                    if writes[0] == kill_at:
                        raise KeyboardInterrupt
                with patch.object(serial, "keep", side_effect=keep):
                    for _ in range(3):
                        try:
                            self.run_new(fake, words=500)
                            self.run_next(fake)
                            break
                        except KeyboardInterrupt:
                            pass
                self.assertEqual(fake.asked, ["pitch", "plan", "draft", "rewrite"])
                self.assertEqual(serial.status("slot").count("hand-edited"), 0)

    def test_resume_adopts_a_finished_call_and_spends_nothing_again(self):
        fake = Fake()
        self.run_new(fake)
        with patch.object(serial.checks, "hard", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.run_next(fake)
        self.run_next(fake)
        self.assertEqual(fake.asked, ["pitch", "plan", "draft"])
        self.run_next(fake)
        self.assertEqual(serial.done(self.root), 2)
        before = list(fake.asked)
        self.run_new(fake)
        self.assertEqual(fake.asked, before)

    def test_transport_faults_are_retried_twice_and_never_counted_as_draws(self):
        fake = Fake(pitch=[RuntimeError(), RuntimeError(), BIBLE])
        self.run_new(fake)
        self.assertEqual(len(files.load(self.root / "manifest.json")["stages"]["ch00/pitch"]["draws"]), 1)
        self.assertTrue((self.root / "ch00" / "calls" / "pitch-d1r2" / "final.md").is_file())
        fake.replies["plan"] = [RuntimeError()] * 3
        with self.assertRaises(transport.Fault):
            self.run_next(fake)

    def test_spend_limits(self):
        self.assertEqual((serial.DRAWS, serial.RETRIES, serial.MAX_REQUEST, serial.MAX_CHAPTERS), (3, 2, 32_000, 10))
        fake = Fake()
        self.run_new(fake)
        with self.assertRaises(ValueError):
            self.run_next(fake, 11)
        files.write(self.root / "ch00" / "bible.md", BIBLE + "x" * 32_000)
        with self.assertRaisesRegex(ValueError, "over 32000"):
            self.run_next(fake)
        self.assertEqual(fake.asked, ["pitch"])

    def test_redraw_moves_chapters_aside_and_next_plans_again(self):
        fake = Fake()
        self.run_new(fake)
        self.run_next(fake, 2)
        aside = serial.redraw("slot", 2)
        self.assertTrue((aside / "ch02" / "chapter.md").is_file())
        self.assertEqual(serial.done(self.root), 1)
        self.run_next(fake)
        self.assertEqual(fake.asked[-2:], ["plan", "draft"])

    def test_tells_rewrite_keeps_only_rewrites_that_clear_the_counter(self):
        told = ("Nobody moved. Nobody spoke. Nothing came. Nothing changed. No one asked. It never ended. "
                "He waited the way he always waited. It went the way it always went.")
        answer = "".join(f"{i}. Everyone froze {i}.\n" for i in range(1, 7))
        fake = Fake(draft=partial(draft_for, extra=told), rewrite=answer + "7. He waited the way he did.\n8. As usual.\n")
        self.run_new(fake)
        self.run_next(fake)
        chapter = files.read(self.root / "ch01" / "chapter.md")
        self.assertIn("Everyone froze 6. He waited the way he always waited. As usual.", chapter)
        report = files.read(self.root / "ch01" / "report.md")
        self.assertIn("- rewrite: Nobody moved. => Everyone froze 1.\n", report)
        self.assertNotIn("He waited the way he did.", report)
        self.assertEqual(fake.asked.count("rewrite"), 1)


class CliTests(unittest.TestCase):
    def test_spending_verbs_need_the_canary_pin(self):
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"LITHARNESS_HOME": home}), \
                patch.object(transport, "preflight", return_value="codex-cli 2"), \
                patch.object(transport, "native_binary", return_value=Path("codex.exe")), \
                patch.object(cli.files, "box_lock", return_value=Path(home) / "box.lock"), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            files.save(Path(home) / "canary.json", {"codex": {"version": "codex-cli 1"}})
            self.assertEqual(cli.main(["next", "nothing-here"]), 1)
            self.assertFalse((Path(home) / "serials" / "nothing-here").exists())
            (Path(home) / "serials" / "slot").mkdir(parents=True)
            self.assertEqual(cli.main(["next", "slot"]), 1)
            self.assertFalse((Path(home) / "box.lock").exists())
        self.assertIn("codex-cli 2 has not passed the canary", err.getvalue())


class RecheckTests(unittest.TestCase):
    setUp, run_new, run_next = SerialTests.setUp, SerialTests.run_new, SerialTests.run_next

    def test_a_check_fixed_after_three_failed_draws_adopts_a_stored_answer_without_a_call(self):
        fake = Fake()
        self.run_new(fake)
        real = serial.checks.hard
        with patch.object(serial.checks, "hard", side_effect=lambda stage, *a, **k: ["fields: 0"] if stage == "plan"
                          else real(stage, *a, **k)), self.assertRaisesRegex(serial.Stop, "3 draws failed"):
            self.run_next(fake)
        self.run_next(fake)
        self.assertEqual(fake.asked, ["pitch", "plan", "plan", "plan", "draft"])
        self.assertIn("rechecked", files.load(self.root / "manifest.json")["stages"]["ch01/plan"]["draws"][0])
