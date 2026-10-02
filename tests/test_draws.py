"""draws.py end to end through the real transport with a fake CLI: an oracle, nulls, faults and resume."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import draws
from litharness import files, serial, transport
from tests.test_checks import BIBLE
from tests.test_serial import Fake
from tests.test_transport import INSTALLED

CASES = {"cases": [{"id": "slot", "tags": ["premise"], "brief": "System apocalypse. One Slot each; his holds every skill."},
                   {"id": "cook", "tags": ["premise"], "brief": "An apprentice cook is stranded in an island city."}]}


class DrawsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home, self.err = Path(self.tmp.name), io.StringIO()
        files.save(self.home / "cases.json", CASES)
        files.save(self.home / "canary.json", {name: {"version": version} for name, (_, version) in INSTALLED.items()})
        homes = dict.fromkeys(("LITHARNESS_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR"), self.tmp.name)  # no real home is read
        for patcher in (patch.dict(os.environ, homes), patch.dict(transport.CLI, INSTALLED),
                        patch.object(draws, "CASES", self.home / "cases.json"), patch.object(draws.time, "sleep"),
                        patch.object(draws.files, "box_lock", return_value=self.home / "box.lock"),
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(self.err),
                        patch.object(files.os, "fsync")):
            patcher.__enter__()
            self.addCleanup(patcher.__exit__, None, None, None)
        self.flow = self.home / "evals" / "pitch-draws"

    def rows(self, variant="baseline", name="results.jsonl"):
        return draws.load(self.flow / variant / name)

    def test_nothing_is_drawn_until_a_person_approves_the_harness(self):
        fake = Fake()
        self.assertEqual((draws.main(["run"], fake), len(fake.asked)), (2, 0))
        self.assertEqual((draws.main(["approve"]), draws.main(["run", "--reps", "2"], fake)), (0, 0))
        files.save(self.home / "cases.json", {"cases": CASES["cases"][:1]})  # an edited case list is a changed harness
        self.assertEqual(draws.main(["run", "--reps", "2"], fake), 2)
        self.assertEqual((len(fake.asked), self.err.getvalue().count("python draws.py approve")), (4, 2))

    def test_an_oracle_passes_every_draw_and_a_resume_buys_nothing(self):
        fake = Fake()
        draws.main(["approve"])
        self.assertEqual(draws.main(["run", "--reps", "2", "--agent", "claude"], fake), 0)
        rows = self.rows()
        self.assertEqual(sorted((row["prompt_id"], row["rep"], row["grade"]["pass"]) for row in rows),
                         [("cook", 0, 1), ("cook", 1, 1), ("slot", 0, 1), ("slot", 1, 1)])
        self.assertEqual({(row["model"], row["meta"]["agent"], row["usage"]["input_tokens"], row["tokens"]) for row in rows},
                         {("claude-opus-5-5", "claude:claude-opus-5-5:medium", 4, 28)})
        self.assertEqual(files.load(self.flow / "baseline" / "traces" / "slot_rep1.json")[2]["content"], BIBLE)
        self.assertEqual((draws.main(["run", "--reps", "2", "--agent", "claude"], fake), len(fake.asked)), (0, 4))
        self.assertEqual(draws.main(["run", "--reps", "2", "--agent", "codex"], fake), 2)  # one agent a variant
        self.assertEqual((serial.DRAWS, os.environ["LITHARNESS_HOME"], len(self.rows())), (3, self.tmp.name, 4))
        self.assertIn("| baseline | claude:claude-opus-5-5:medium | 2 | 4 | 100% | too few briefs | 100% | 100% | 100% |",
                      files.read(self.flow / "summary.md"))

    def test_wrong_answers_are_graded_by_family_and_two_variants_are_compared_brief_by_brief(self):
        draws.main(["approve"])
        draws.main(["run"], Fake(pitch="I do not know."))
        draws.main(["run", "--variant", "v1", "--reps", "1"], Fake(pitch=BIBLE.replace("reading water", "reading water, paying rent")))
        draws.main(["run", "--variant", "v2", "--reps", "1"], Fake())
        null, money = self.rows()[0], self.rows("v1")[0]
        self.assertEqual((null["grade"], null["money_hits"]), ({"pass": 0, "money_clean": 1, "shape_ok": 0, "leak_clean": 1}, 0))
        self.assertEqual((money["grade"], money["money_hits"]), ({"pass": 0, "money_clean": 0, "shape_ok": 1, "leak_clean": 1}, 1))
        self.assertIn("money: 'rent'", money["explanation"]["pass"])
        summary = files.read(self.flow / "summary.md")
        self.assertIn("| v1 | 2 | +0 points | too few briefs | too few briefs |", summary)
        self.assertIn("| v2 | 2 | +100 points | too few briefs | too few briefs |", summary)
        self.assertIn("| slot | premise | 0/4 | 0/1 | 1/1 |", summary)

    def test_an_interval_needs_five_briefs_and_says_whether_a_difference_is_within_noise(self):
        signed = lambda share: f"{100 * share:+.0f}"  # noqa: E731
        self.assertEqual(draws.spread([0.2, 1.0]), (0.6, "too few briefs", True))
        mean, band, noise = draws.spread([0.0, 0.25, 0.5, 0.75, 1.0, 0.5])
        self.assertEqual((mean, noise, draws.spread([0.0, 0.25, 0.5, 0.75, 1.0, 0.5])[1]), (0.5, False, band))  # seeded
        self.assertRegex(band, r"^\d+% to \d+%$")
        self.assertTrue(draws.spread([0.5, -0.5, 0.25, -0.25, 0.0], signed)[2])
        self.assertRegex(draws.spread([0.5, 0.75, 1.0, 0.5, 0.75], signed)[1], r"^\+\d+ to \+\d+$")
        self.assertFalse(draws.spread([0.5, 0.75, 1.0, 0.5, 0.75], signed)[2])

    def test_an_attempt_without_an_answer_is_an_error_beside_the_rows_and_is_drawn_again(self):
        draws.main(["approve"])
        self.assertEqual(draws.main(["run", "--reps", "1", "--only", "slot"], Fake(pitch=" ")), 2)  # no row: nothing to report
        self.assertEqual((self.rows(), [e["failure_class"] for e in self.rows(name="errors.jsonl")]), ([], ["serving_error"]))
        self.assertEqual(draws.main(["run", "--reps", "1", "--only", "slot"], Fake()), 0)
        self.assertEqual([(row["grade"]["pass"], row["meta"]["attempts"]) for row in self.rows()], [(1, 4)])
        with patch.object(draws, "STREAK", 2):
            draws.main(["run", "--variant", "v1", "--reps", "3", "--jobs", "1"], Fake(pitch=" "))
        self.assertEqual(len(self.rows("v1", "errors.jsonl")), 2)  # two in a row stop the run
        self.assertIn("stopped after 2 failures in a row", self.err.getvalue())
        self.assertFalse((self.home / "box.lock").exists())
