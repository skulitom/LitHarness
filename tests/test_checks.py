import contextlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from litharness import __main__ as cli, checks, files, sheet, tells

ROOT = Path(__file__).resolve().parents[1]
OPENING = ROOT / "experiments" / "2026-09-27-opening"
FIXTURES = json.loads((Path(__file__).parent / "fixtures.json").read_bytes())
LITE = checks.normalize(files.read(OPENING / "lite" / "chapter.md"))[0]


CATCHES = {
    "money": lambda text, stage: checks.money(text, stage),
    "leak": lambda text, stage: checks.leak(text, whole_title=stage != "chapter"),
    "person": lambda text, stage: checks.person(text),
    "admin": lambda text, stage: checks.hits(checks.ADMIN, text),
    "tells": lambda text, stage: any(tells.locate(text).values()),
}
BIBLE = """# One Slot, Open Water
## Listing
The System gives everyone one Slot. Elias Venn gets one that takes every skill he can hold.
## Person
Elias Venn. Age: 26. He was clearing a flooded underpass when the System arrived; he was good at
reading water. He wants his brother Jamie on dry ground.
## Exception
A Slot with no ceiling, which breaks the one-skill rule.
## First use
Inside the bus, Hold Breath lands in the Slot and gets Jamie out.
## Threat
The rising river, first at the underpass.
## Prize
Silver means a second Slot: one more thing he can fix at once.
## System
Blue text at the edge of sight. Ladder: Iron, Bronze, Silver
Start:
[Rank: Iron]
[Slots: 1/1]
## People
- Jamie, wants out, talks fast
- Mara, wants the gate shut, talks in orders
## Limits
Each held skill takes a breath from him, and an empty chest puts him at risk.
"""
PLAN = """=== STATE ===
## Where
Elias: the underpass, soaked, wants Jamie out.
## Held
One torch.
## Open
Who stopped the river.
## So far
The System arrived as the bus flooded.

=== PLAN ===
Title: Hold Breath
## Opening
The bus tilts.
## Movements
1. Water rises; he takes Hold Breath; Jamie is free.
2. The seat frame pins a stranger; he lifts it; the Slot aches.
3. The gate jams; he chooses the gate; the river turns.
Rise: Slots: 1/1 -> 1/2 | movement 1 | he takes Hold Breath underwater
## Options
Stay or climb.
## People
Elias, Jamie
## Ending
He holds a second slot, and the river is coming.
"""


def with_status(text, early, late):
    paragraphs = text.split("\n\n")
    paragraphs.insert(4, early)
    paragraphs.insert(9, late)
    return "\n\n".join(paragraphs)


class FixtureTests(unittest.TestCase):
    def test_every_fixture_lands_in_its_class(self):
        self.assertLessEqual(len(FIXTURES), 60)
        for case in FIXTURES:
            with self.subTest(**case):
                self.assertLessEqual(len(case["text"].split()), 40)
                self.assertEqual(bool(CATCHES[case["check"]](case["text"], case["stage"])), case["expect"] == "hit")

    def test_every_lexicon_word_is_caught_and_never_as_a_prefix(self):
        def forms(word):
            return [word[:-2], word[:-1]] if word.endswith("s?") else [word]
        for word in [f for w in checks.MONEY_WORDS if "(" not in w for f in forms(w)]:
            self.assertTrue(checks.money(f"She never spoke of the {word} again.", "chapter"), word)
        for word in [f for w in checks.INSTITUTIONAL if "(" not in w for f in forms(w)]:
            self.assertTrue(checks.money(f"He saw the {word} there.", "pitch"), word)
        for word in [f for w in checks.ADMIN_WORDS for f in forms(w)]:
            self.assertTrue(checks.hits(checks.ADMIN, f"It was the {word}."), word)
        for sentence in ("His wage was late.", "The wages came."):
            self.assertTrue(checks.money(sentence, "chapter"), sentence)
        for sentence in ("Owen lowered the released current.", "They wage war at dawn.", "The courtyard."):
            self.assertFalse(checks.money(sentence, "pitch"), sentence)


class DocumentTests(unittest.TestCase):
    def test_length_and_band(self):
        self.assertTrue(checks.length(LITE, 1500))
        self.assertFalse(checks.length(LITE, 4000))
        self.assertIn("outside 1200-2000", checks.report(LITE, target=1500))
        self.assertNotIn("outside", checks.report(LITE, target=4000).splitlines()[0])

    def test_rise_needs_a_status_line_and_an_early_rise_in_chapter_one(self):
        self.assertEqual(checks.rise(LITE, 1, {}, []), ["rise: chapter 1 has no status line"])
        good = with_status(LITE, "[Slots: 1/1]", "[Slots: 1/2]")
        self.assertEqual(checks.rise(good, 1, {}, []), [])
        late = LITE.replace("\n\n", "\n\n[Slots: 1/1]\n\n", 1) + "\n[Slots: 1/2]\n"
        self.assertEqual(checks.rise(late, 1, {}, []), ["rise: chapter 1's first rise is missing or after the word midpoint"])
        planned = checks.planned(PLAN)
        self.assertEqual(checks.rise(good, 2, {"Slots": "1/1"}, [], planned), [])
        self.assertIn("not printed", checks.rise(LITE, 2, {"Slots": "1/1"}, [], planned)[0])

    def test_fields(self):
        ranks = ["Iron", "Bronze", "Silver"]
        self.assertEqual(checks.fields("[Rank: Bronze]\n[Slots: 1/2]\n[Grip: 3]", {"Rank": "Iron"}, ranks), [])
        for bad in ("[Rank: Copper]", "[Grip: 0]", "[Slots: 3/2]", "[Slots: 0/0]"):
            self.assertTrue(checks.fields(bad, {"Rank": "Iron"}, ranks), bad)
        acquired = ("Installed skills", "0", "1", "1", "he installs it")
        self.assertEqual(checks.fields("[Installed skills: 0]\n[Installed skills: 1]", {}, ranks, acquired), [])
        self.assertTrue(checks.fields("[Installed skills: 0]", {}, ranks))
        many = "\n".join(f"[Skill{i}: 1]" for i in range(13))
        self.assertIn("12-line sheet", checks.fields(many, {}, ranks)[-1])

    def test_pitch_shape(self):
        self.assertEqual(checks.hard("pitch", BIBLE), [])
        lite_plan = files.read(OPENING / "lite" / "plan.md")
        self.assertIn("pitch-shape: '## Listing' is missing or empty", checks.pitch_shape(lite_plan))
        for old, new in (("Age: 26", "Age: 34"), ("Iron, Bronze, Silver", "Iron, Bronze"), ("[Slots: 1/1]", "[Slots: 2/1]")):
            self.assertTrue(checks.pitch_shape(BIBLE.replace(old, new, 1)), new)

    def test_plan_shape(self):
        ranks = ["Iron", "Bronze", "Silver"]
        self.assertEqual(checks.hard("plan", PLAN, n=1, ranks=ranks), [])
        self.assertTrue(checks.plan_shape(files.read(OPENING / "lite" / "plan.md"), 1, ranks))
        for old, new in (("movement 1", "movement 2"), ("Rise: Slots: 1/1 -> 1/2", "Rise: none"),
                         ("Title: Hold Breath", ""), ("3. The gate", "The gate")):
            self.assertTrue(checks.plan_shape(PLAN.replace(old, new), 1, ranks), new)
        self.assertEqual(checks.plan_shape(PLAN.replace("movement 1", "movement 2"), 2, ranks), [])

    def test_sheet_report(self):
        page = "[Rank: Bronze]\n\n[Grip: 2]\n\n[grip: 3]\n\n[HP: 5]\n\n[Rank: Iron]"
        report = checks.report(page, before={"Rank": "Iron", "Grip": "3"}, ranks=["Iron", "Bronze"])
        for line in ("fall Rank: Bronze -> Iron", "new HP: 5", "spelled 2 ways", "generic label: HP"):
            self.assertIn(line, report)

    def test_review_cases_that_would_burn_draws(self):
        self.assertEqual(checks.person("The mine was dark. " * 4 + "He took Hold Breath I at Tier I."), [])
        self.assertEqual(sheet.ladder("Ladder: Iron (lowest), Bronze, Silver, and Gold. Each doubles."),
                         ["Iron", "Bronze", "Silver", "Gold"])
        self.assertEqual(sheet.ladder("Ladder: Iron, Bronze and Silver"), ["Iron", "Bronze", "Silver"])
        self.assertEqual((sheet.value("1,050/1,200", []), sheet.value("10²", [])), ((1050, 1200), None))
        self.assertEqual(checks.items("- Jamie\n  - wants out\n  - talks fast\n- Mara\n  - wants the gate"), 2)
        named = "**Wenna Keel**, 22\n- Want: out\n- Talk: clipped\n**Ysolde Keel**, 91\n- Want: whole\n- Talk: formal\n"
        self.assertEqual((checks.items(named), checks.items(named + "**Teo Marr**\n- Want: rights")), (2, 3))
        self.assertEqual(checks.items("Three people matter.\n- Wenna\n- Ysolde\n- Teo\n- Mara"), 4)
        for leaked in ("**Title:** Hold Breath", "CHAPTER THREE: HOLD BREATH", "## Chapter Eleven"):
            self.assertTrue(checks.leak(leaked), leaked)
        for clean in ("“Go.” Listing, the hull tipped.", "Mara said, “Listing won't help.”"):
            self.assertEqual(checks.leak(clean), [], clean)
        echo = BIBLE.replace("# One Slot, Open Water", "# Off the Sheet")
        self.assertEqual((checks.hard("pitch", echo, brief="the same sheet"), bool(checks.hard("pitch", echo))), ([], True))
        self.assertTrue(checks.leak("Off the Sheet Ladder", True, "the same sheet"))
        self.assertEqual(checks.normalize("*Not now—* he thought.")[0], "*Not now,* he thought.\n")

    def test_rise_semantics(self):
        ranks, before = ["Iron", "Bronze", "Silver"], {"Slots": "1/1", "Mana": "5/5"}
        plan = PLAN.replace("## Movements\n1.", "## Movements\n**1.**").replace("Rise:", "- Rise:")
        self.assertEqual(checks.hard("plan", plan, n=1, ranks=ranks, before=before), [])
        for old, new in (("Slots: 1/1 -> 1/2", "Slot: 1/1 -> 1/2"), ("Slots: 1/1 -> 1/2", "Slots: 1/2 -> 1/1")):
            self.assertTrue(checks.plan_shape(PLAN.replace(old, new), 1, ranks, before), new)
        spent = checks.planned(PLAN.replace("Slots: 1/1 -> 1/2", "Mana: 5/5 -> 5/8"))
        self.assertEqual(checks.rise("[Mana: 3/8]", 2, before, ranks, spent), [])
        self.assertTrue(checks.rise("[Slots: 1/2]", 2, {"Slots": "1/2"}, ranks, checks.planned(PLAN)))
        masked = with_status(LITE, "[Slots: 1/1]\n[Level: 1]", "").rstrip() + "\n[Slots: 1/2]\n"
        self.assertIn("after the word midpoint", checks.rise(masked, 1, before, ranks, checks.planned(PLAN))[0])
        bible = BIBLE.replace("Elias Venn.", "His name: Elias Venn.")
        self.assertIn("literals: name MISSING", checks.report("Jamie ran.", bible=bible))

    def test_person_skips_speech_italics_and_status_lines(self):
        self.assertEqual(checks.person('"I will," he said. *I have to move.*\n[My Rank: 2]\nHe moved.'), [])
        self.assertTrue(checks.person("I will move. He moved."))


class CheckVerbTests(unittest.TestCase):
    def run_check(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["check", *map(str, args)])
        return code, out.getvalue()

    def test_frozen_chapters_and_a_test_serial(self):
        code, out = self.run_check(OPENING / "lite" / "chapter.md")
        self.assertEqual(code, 1)
        for line in ("rise: chapter 1 has no status line", "length: 4065 words", "inspection x4, council x3"):
            self.assertIn(line, out)
        self.assertIn("rise: chapter 1 has no status line", self.run_check(OPENING / "baseline" / "chapter-one.md")[1])
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"LITHARNESS_HOME": home}):
            files.write(Path(home) / "serials" / "t" / "ch00" / "bible.md", BIBLE.replace("Elias Venn.", "Elias Venn, 26."))
            files.save(Path(home) / "serials" / "t" / "serial.json", {"words": 1500})
            out = self.run_check(OPENING / "lite" / "chapter.md", "--serial", "t")[1]
        self.assertIn("literals: name present", out)
        self.assertIn("literals: age MISSING", out)
