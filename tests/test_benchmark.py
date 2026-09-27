import json
import unittest

from analyze import render, totals
from benchmark import CRITERIA, decode_judgment


class EvidenceTests(unittest.TestCase):
    def test_quote_in_wrong_passage_invalidates_judgment(self):
        result = {"criteria": [{"name": name, "A": 3, "B": 3,
                                "quote_A": "red rope", "quote_B": "blue gate"}
                               for name in CRITERIA], "overall": "tie"}
        _, problems = decode_judgment(json.dumps(result), "a red rope", "a blue gate")
        self.assertEqual(problems, [])
        result["criteria"][0]["quote_A"] = "blue gate"
        _, problems = decode_judgment(json.dumps(result), "a red rope", "a blue gate")
        self.assertEqual(len(problems), 1)
        self.assertIn("Unlocated quote", problems[0])

    def test_missing_criterion_does_not_silently_score(self):
        _, problems = decode_judgment('{"criteria": [], "overall": "A"}', "a", "b")
        self.assertTrue(problems)

    def test_totals_do_not_double_count_cached_input_or_hide_unknown_usage(self):
        report = totals([{"seconds": 2, "usage": {"input_tokens": 100,
                         "cached_input_tokens": 60, "output_tokens": 20}},
                         {"seconds": 3, "usage": None}])
        self.assertEqual(report["total_input_and_output_tokens"], 120)
        self.assertEqual(report["uncached_input_tokens"], 40)
        self.assertEqual(report["unknown_usage_calls"], 1)
        self.assertEqual(report["seconds"], 5)

    def test_reading_copy_escapes_html(self):
        rendered = render('# <title>\n\n<script>alert(1)</script>\n\n* * *')
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<hr>", rendered)

    def test_running_receipt_is_marked_incomplete(self):
        report = totals([{"status": "running", "usage": None}])
        self.assertEqual(report["unknown_duration_calls"], 1)
        self.assertEqual(report["unknown_usage_calls"], 1)


if __name__ == "__main__":
    unittest.main()
