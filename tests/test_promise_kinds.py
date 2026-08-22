"""What the pure reading layer of ``promise_kinds.py`` pins, and nothing more.

Checked directly, on constructed inputs whose answers were worked out by hand before running
anything: how ``reported_kinds`` normalises a model's kind strings (case, space, blanks,
non-strings, junk list entries); the pre-registered cut/nominate arithmetic of
``read_distribution`` at both of its thresholds, including the sole-kind rescue and the
empty-distribution degenerate case; and the two open-arm derivations — ``open_schema``
swapping only ``kind``'s enum for a string-or-null choice, ``open_system`` substituting the
enumeration out of the shipped prompt and refusing loudly when it cannot.

Not established here: nothing about the study itself. No corpus is read, no database opened,
no model called, no result file written, so these tests say the *rule* executes as written,
not that the taxonomy it prunes is the right one or that any observed distribution supports it.
Module-level constants (shares, sample counts, call guards) are deliberately not asserted;
only behaviour that sits on either side of them is.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

promise_kinds = pytest.importorskip(
    "promise_kinds",
    reason="research module; needs the quality-measurement directory on the path",
)

CANDIDATES = ("plot", "character", "progression", "mystery", "tone")


# --- reported_kinds -----------------------------------------------------------


def test_reported_kinds_normalises_each_kind_by_case_and_surrounding_space():
    answer = {
        "promises_opened": [
            {"kind": "  Plot ", "why": "the duel was left unresolved"},
            {"kind": "TONE"},
        ]
    }
    assert promise_kinds.reported_kinds(answer) == ["plot", "tone"]


def test_reported_kinds_returns_none_where_a_promise_names_no_usable_kind():
    answer = {
        "promises_opened": [
            {"note": "no kind key at all"},
            {"kind": ""},
            {"kind": "   "},
            {"kind": 7},
        ]
    }
    assert promise_kinds.reported_kinds(answer) == [None, None, None, None]


def test_reported_kinds_returns_empty_when_the_answer_carries_no_promise_list():
    assert promise_kinds.reported_kinds({}) == []
    assert promise_kinds.reported_kinds({"promises_opened": None}) == []
    assert promise_kinds.reported_kinds({"promises_opened": {"kind": "plot"}}) == []
    assert promise_kinds.reported_kinds({"promises_opened": "one plot debt"}) == []


def test_reported_kinds_skips_list_entries_that_are_not_dicts():
    answer = {"promises_opened": ["plot", {"kind": "tone"}, 42, {"kind": "mystery"}]}
    assert promise_kinds.reported_kinds(answer) == ["tone", "mystery"]


# --- read_distribution --------------------------------------------------------


def test_read_distribution_keeps_a_candidate_exactly_at_the_minor_share():
    # 5 of 100 is exactly MINOR_SHARE, and the cut condition is strict (<), so it stays.
    result = promise_kinds.read_distribution(
        Counter({"plot": 5}), candidates=CANDIDATES, sole=set(), total=100
    )
    assert result["keep"] == ["plot"]
    assert "plot" not in [entry["kind"] for entry in result["cut"]]


def test_read_distribution_cuts_a_candidate_below_the_minor_share():
    result = promise_kinds.read_distribution(
        Counter({"plot": 96, "tone": 4}), candidates=CANDIDATES, sole=set(), total=100
    )
    assert result["keep"] == ["plot"]
    cut = next(entry for entry in result["cut"] if entry["kind"] == "tone")
    assert cut["reports"] == 4
    assert cut["share"] == 0.04



def test_read_distribution_cuts_a_candidate_nobody_reported():
    result = promise_kinds.read_distribution(
        Counter({"plot": 50}), candidates=CANDIDATES, sole=set(), total=100
    )
    never = next(entry for entry in result["cut"] if entry["kind"] == "mystery")
    assert never["reports"] == 0
    assert never["share"] == 0.0
    assert never["why"] == "never reported"


def test_read_distribution_nominates_an_out_of_set_kind_exactly_at_the_nominate_share():
    # 10 of 100 is exactly NOMINATE_SHARE, and the nomination filter is >=, so it clears.
    result = promise_kinds.read_distribution(
        Counter({"plot": 90, "worldbuilding": 10}),
        candidates=CANDIDATES,
        sole=set(),
        total=100,
    )
    assert result["nominations"] == [{"kind": "worldbuilding", "reports": 10, "share": 0.1}]
    # A nomination is reported for an operator act, never silently admitted to the set.
    assert "worldbuilding" not in result["keep"]
    assert result["keep"] == ["plot"]


def test_read_distribution_lists_but_does_not_nominate_an_out_of_set_kind_below_the_share():
    result = promise_kinds.read_distribution(
        Counter({"plot": 91, "worldbuilding": 9}),
        candidates=CANDIDATES,
        sole=set(),
        total=100,
    )
    assert result["nominations"] == []
    # The tail is still printed rather than dropped on the floor.
    assert result["unregistered"] == [{"kind": "worldbuilding", "reports": 9}]


def test_read_distribution_cuts_every_candidate_and_nominates_nothing_on_an_empty_input():
    result = promise_kinds.read_distribution(
        Counter(), candidates=CANDIDATES, sole=set(), total=0
    )
    assert result["reported_promises"] == 0
    assert result["keep"] == []
    assert [(entry["kind"], entry["reports"]) for entry in result["cut"]] == [
        (kind, 0) for kind in CANDIDATES
    ]
    assert result["nominations"] == []
    assert result["unregistered"] == []


def test_read_distribution_orders_nominations_by_most_reported_then_alphabetically():
    result = promise_kinds.read_distribution(
        Counter({"zeta": 20, "alpha": 10, "beta": 10}),
        candidates=("plot",),
        sole=set(),
        total=100,
    )
    assert [entry["kind"] for entry in result["nominations"]] == ["zeta", "alpha", "beta"]
    assert [entry["share"] for entry in result["nominations"]] == [0.2, 0.1, 0.1]


def test_read_distribution_orders_the_reported_counts_by_most_reported_then_alphabetically():
    result = promise_kinds.read_distribution(
        Counter({"mystery": 3, "plot": 7, "zebra": 2, "alpaca": 2}),
        candidates=("plot", "mystery", "tone"),
        sole=set(),
        total=14,
    )
    assert list(result["counts"].items()) == [
        ("plot", 7),
        ("mystery", 3),
        ("alpaca", 2),
        ("zebra", 2),
    ]


# --- open_schema --------------------------------------------------------------


def _shipped_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "promises_opened": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["plot", "character"]},
                        "note": {"type": "string"},
                    },
                    "required": ["kind", "note"],
                },
            },
        },
    }


def test_open_schema_replaces_the_kind_enum_with_a_string_or_null_choice():
    result = promise_kinds.open_schema(_shipped_schema())
    kind = result["properties"]["promises_opened"]["items"]["properties"]["kind"]
    assert kind == {"anyOf": [{"type": "string"}, {"type": "null"}]}


def test_open_schema_leaves_every_part_except_kind_as_it_was_given():
    expected = _shipped_schema()
    expected["properties"]["promises_opened"]["items"]["properties"]["kind"] = {
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }
    assert promise_kinds.open_schema(_shipped_schema()) == expected


def test_open_schema_does_not_mutate_the_schema_it_is_given():
    shipped = _shipped_schema()
    promise_kinds.open_schema(shipped)
    kind = shipped["properties"]["promises_opened"]["items"]["properties"]["kind"]
    assert kind == {"enum": ["plot", "character"]}


# --- open_system --------------------------------------------------------------


def test_open_system_substitutes_one_word_of_your_own_choosing_for_the_enumeration():
    shipped = "Report each debt. Choose among (plot, character, mystery, tone) freely."
    result = promise_kinds.open_system(shipped, ("plot", "character", "mystery", "tone"))
    assert result == "Report each debt. Choose among (one word of your own choosing) freely."
    assert "(plot, character, mystery, tone)" not in result


def test_open_system_raises_when_the_shipped_prompt_lacks_the_enumeration():
    with pytest.raises(SystemExit):
        promise_kinds.open_system("Report each debt. No enumeration survives here.", CANDIDATES)


def test_open_system_refuses_an_enumeration_joined_in_a_different_order():
    shipped = "Choose among (tone, character) freely."
    with pytest.raises(SystemExit):
        promise_kinds.open_system(shipped, ("character", "tone"))


# --- the module's own hermetic proof ------------------------------------------


def test_the_module_selftest_passes():
    assert promise_kinds.selftest() == 0


def test_read_distribution_keeps_a_below_share_candidate_that_was_some_promise_sole_kind():
    # tone is far under the minor share, but it was the only kind one promise got.
    result = promise_kinds.read_distribution(
        Counter({"plot": 97, "tone": 3}), candidates=CANDIDATES, sole={"tone"}, total=100
    )
    assert result["keep"] == ["plot", "tone"]
