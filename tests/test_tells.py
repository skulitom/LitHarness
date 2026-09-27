"""The tell counter, on synthetic sentences only."""
import unittest

from litharness import tells

NAMED = {
    "absence": "He fixed radios in the back room for a crowd that never came.",
    "paradox": "He was leaving without leaving, one foot on the step.",
    "the_way": "Marco checked the lock twice, the way he always checked it.",
    "echo": "Marco checked the lock and counted, then checked the hinge and counted.",
    "chained_and": "She fed the cat and locked the door and killed the lights and slept.",
    "long": "He walked " + "very " * 33 + "far.",
}
PLAIN = "The bus was late. Mira read the timetable twice. Rain drummed on the shelter roof."


def families(text):
    return {family for family, hits in tells.locate(text).items() if hits}


class TellsTests(unittest.TestCase):
    def test_each_family_is_located_and_plain_prose_is_not(self):
        self.assertEqual(set(tells.CEILINGS) | {"long"}, set(NAMED))
        for family, sentence in NAMED.items():
            self.assertIn(sentence, tells.locate(sentence)[family], family)
        self.assertIn("paradox", families("Not a knock, a kick."))
        self.assertEqual(families(PLAIN), set())
        self.assertEqual(tells.over(PLAIN), [])

    def test_speech_italics_and_system_lines_are_not_the_narrator(self):
        self.assertEqual(families('"Nobody knows the code," Tam said.'), set())
        self.assertEqual(families("“Nothing works.” He shrugged."), set())
        self.assertEqual(families("Nobody knew the code. Tam typed it anyway."), {"absence"})
        page = "[Level: 2]\n[Strength: 7]\n\n*Nobody saw that.* He pocketed the key.\n\nNO CLASS ASSIGNED. NOTHING ISSUED."
        self.assertEqual(families(page), set())
        self.assertEqual(tells.narration(page), "He pocketed the key.")

    def test_a_cut_keeps_sentence_boundaries(self):
        self.assertEqual(tells.narration('He said, "Go now." Then he left.'), "He said,\n\nThen he left.")
        self.assertEqual(tells.narration('He shouted "Stop!" and ran.'), "He shouted and ran.")
        self.assertEqual(tells.sentences("One. Two words.\n\nThree here!"), ["One.", "Two words.", "Three here!"])

    def test_rates_use_the_shelf_divisor_and_long_is_no_family(self):
        page = '"Hold still," Ana said.\n\n' + NAMED["absence"] + " " + PLAIN + " " + NAMED["long"]
        self.assertAlmostEqual(tells.rates(page)["absence"], 1000.0 / tells.words(page))
        self.assertEqual(tells.over(page), ["absence"])
        self.assertNotIn("long", tells.rates(page))

    def test_shape(self):
        report = tells.shape("Go. He ran for the door. " + NAMED["long"])
        self.assertEqual((report["long"], report["median"]), ([NAMED["long"]], 5.0))
        self.assertAlmostEqual(report["short_share"], 1 / 3)
        self.assertEqual(tells.shape(""), {"long": [], "median": 0.0, "short_share": 0.0})

    def test_the_counter_has_no_ear_for_a_simile_said_without_its_words(self):
        blind = "The phone slid out of his hand like a bar of soap goes."
        self.assertEqual(families(blind), set())
        self.assertEqual(families(blind.replace("like", "the way")), {"the_way"})
