"""bench.py on synthetic text only: no genre prose, no corpus, no model."""
from pathlib import Path
import unittest

import bench

ROOT = Path(__file__).resolve().parents[1]


class BenchTests(unittest.TestCase):
    def test_furniture_takes_system_lines_and_leaves_prose_notes_and_headings(self):
        for line in ("[Level: 3]", "<Skill acquired: Swim>", "[STATUS] Ana, Rank 2", "Strength: 12", "[Required rank: Cleared.]"):
            self.assertTrue(bench.furniture(line), line)
        for line in ("He ran for the door.", "[A/N: thanks for reading]", "Chapter 3: The Gate", "Note: bring rope"):
            self.assertFalse(bench.furniture(line), line)

    def test_a_growing_field_is_a_gain_and_a_notice_with_a_full_stop_is_not_a_field(self):
        page = "He woke.\n\n[Level: 1]\n\nHe fought.\n\n[Level: 2]\n\n[Required rank: 3.]\n\n[Required rank: 4.]\n"
        m = bench.measure(page)
        self.assertEqual((m["events"], m["system_lines"]), (1, 4))
        self.assertEqual(bench.measure("[Level: 1]\n[Level: 1]\n\nHe waited.")["events"], 0)
        self.assertEqual(bench.measure("He learned a new skill today.")["events"], 1)

    def test_our_formatting_and_plain_ascii_measure_the_same(self):
        ours = "“Run,” she said. *Not yet,* he thought.\n\n[Rank: Iron]\n\n———\n\nHe ran."
        plain = '"Run," she said. Not yet, he thought.\n\n[Rank: Iron]\n\nHe ran.'
        self.assertEqual(bench.measure(ours), bench.measure(plain))

    def test_placement_and_the_family_count(self):
        values = [float(v) for v in range(1, 101)]
        place = bench.placement(95.5, values)
        self.assertEqual((round(place["pct"]), place["flag"]), (95, "above"))
        self.assertEqual(bench.placement(50.0, values)["flag"], "")
        reference = [dict.fromkeys(bench.measure("x").keys(), 1.0) for _ in range(20)]
        ours = dict(reference[0], viol_k=9.0, sys_lines_k=9.0, turns_k=9.0)
        self.assertEqual(bench.family_count(ours, reference, bench.CONTENT), ["dialogue"])  # loose and chosen: printed only
        self.assertEqual(bench.family_count(ours, reference, bench.CONTENT, counted=False), ["furniture", "dialogue"])

    def test_the_runtime_never_reads_the_corpus_or_a_report(self):
        for path in (ROOT / "litharness").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("corpora", text, path.name)
            self.assertNotIn("baseline", text, path.name)
