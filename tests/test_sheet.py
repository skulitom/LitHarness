import unittest

from litharness import sheet

SYSTEM = """A blue pane only he can see.
Ladder: Iron, Bronze -> Silver, Gold
Start:
- [Rank: Iron]
[Slots: 1/1]

[Grip: 3]
People: none here
"""
RANKS = ["Iron", "Bronze", "Silver", "Gold"]


class SheetTests(unittest.TestCase):
    def test_ladder_and_values(self):
        self.assertEqual(sheet.ladder(SYSTEM), RANKS)
        self.assertEqual(sheet.value("12", RANKS), (12, None))
        self.assertEqual(sheet.value("bronze", RANKS), (2, None))
        self.assertEqual(sheet.value("3 / 5", RANKS), (3, 5))
        for raw in ("twelve", "12 (+1)", "-3", "Copper"):
            self.assertIsNone(sheet.value(raw, RANKS), raw)
        self.assertEqual(sheet.order("0/4", RANKS), 4)

    def test_start_lines_become_the_first_sheet(self):
        self.assertEqual(sheet.start(SYSTEM), {"Rank": "Iron", "Slots": "1/1", "Grip": "3"})
        self.assertEqual(sheet.start("Start: [Rank: Iron] [Slots: 1/1]\nPeople: two"),
                         {"Rank": "Iron", "Slots": "1/1"})
        self.assertEqual(sheet.read(sheet.render(sheet.start(SYSTEM))), sheet.start(SYSTEM))

    def test_only_whole_bracket_lines_are_status_lines(self):
        page = "[STATUS] Owen, rank 2\nHe said [Grip: 4] quietly.\n  [Grip: 4]  \n[The System hums]\n"
        self.assertEqual([(label, raw) for label, raw, _ in sheet.fields(page)], [("Grip", "4")])

    def test_replay_keeps_the_last_value_and_names_each_change(self):
        before = sheet.start(SYSTEM)
        page = ("[rank: Bronze]\nHe ran.\n[Slots: 0/2]\n[Grip: 2]\n[Skill: Air Step]\n"
                "[Breath: 3]\n[Slots: 0/2]\n")
        after, events = sheet.replay(before, page, RANKS)
        self.assertEqual(after, {"Rank": "Bronze", "Slots": "0/2", "Grip": "2", "Breath": "3"})
        self.assertEqual([(kind, label) for kind, label, *_ in events],
                         [("rise", "Rank"), ("rise", "Slots"), ("fall", "Grip"), ("new", "Breath")])
        self.assertEqual(events[0][2:4], ("Iron", "Bronze"))
