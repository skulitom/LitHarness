"""Conventional status punctuation does not change declared labels or value semantics."""

from __future__ import annotations

import pytest

from litharness.domain.sheet import Sheet, SheetField, sheet_from_line


@pytest.mark.parametrize("separator", [" ", ": ", ":", " : ", "\t:\t"])
def test_delimiter_is_shared_by_declared_strict_and_taught_numeric_readers(separator):
    sheet = Sheet((SheetField("rank", "Grade"), SheetField("mana", "Mana", paired=True)))
    line = f"[STATUS] Mira — Grade{separator}1 | Mana{separator}3/8"
    [(_, values, _)] = sheet.read(line)
    assert values == {"rank": 1, "mana": 3, "mana_max": 8}
    strict = sheet.pattern.fullmatch(line)
    assert strict is not None and strict.group("rank") == "1"
    taught = sheet_from_line(line)
    assert taught is not None
    assert [(field.name, field.label) for field in taught.fields] == [
        ("grade", "Grade"), ("mana", "Mana"),
    ]
    [(_, first_values, _)] = taught.read(line)
    assert first_values == {"grade": 1, "mana": 3, "mana_max": 8}


def test_longest_declared_label_and_typed_values_keep_their_meaning():
    sheet = Sheet((
        SheetField("cold", "Cold"), SheetField("cold_seal", "Cold Seal"),
        SheetField("grade", "Grade", kind="ordinal"),
        SheetField("class", "Class", kind="name"),
        SheetField("note", "Note", kind="text"),
        SheetField("patterns", "Patterns", kind="set"),
    ))
    line = ("[STATUS] Mira — Cold Seal: 2 | Grade: Copper | Class: Warden | "
            "Note: Warning: bridge closed | Patterns: Cold Seal 2, Ember")
    [(_, values, _)] = sheet.read(line, ids={
        "copper": "copper", "warden": "warden", "cold seal": "cold_seal", "ember": "ember",
    })
    assert values == {
        "cold_seal": 2, "grade": "copper", "class": "warden",
        "note": "Warning: bridge closed", "patterns": [["cold_seal", 2], ["ember"]],
    }
    [(_, cleared, _)] = sheet.read("[STATUS] Mira — Cold: 0 | Patterns: none")
    assert cleared == {"cold": 0, "patterns": []}


@pytest.mark.parametrize("pair", [
    "Gradebook: 1", "Invented: 1", "Grade:: 1", "Grade: 1 Depth", "Grade: 1.",
    "Grade: one", "Grade: 1/2", "Grade: -1", "Grade: 1.0", "Grade:", "Grade=1",
    "Mana: 3", "Mana: 3/8 points",
])
def test_colon_does_not_relax_label_or_numeric_value_validation(pair):
    sheet = Sheet((SheetField("rank", "Grade"), SheetField("mana", "Mana", paired=True)))
    assert sheet.read(f"[STATUS] Mira — {pair}") == []


def test_colons_inside_declared_labels_remain_part_of_the_exact_label():
    sheet = Sheet((SheetField("fire", "Damage: Fire"), SheetField("damage", "Damage")))
    [(_, values, _)] = sheet.read("[STATUS] Mira — Damage: Fire: 3")
    assert values == {"fire": 3}
