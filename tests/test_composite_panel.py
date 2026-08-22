"""Panel v2's gate and its slot frame, checked before it is pointed at the axiom battery.

Stage-0 §89's Track A2'. Two things here fail silently and both have cost this project an entry
before:

1. **The slot frame.** `Comparison.choice` is `"A"`/`"B"`, not left/right, and `chose_variant`
   undoes the orientation swap. A composite that answers in the wrong frame produces a perfectly
   well-formed win rate that is the mirror of the truth, and nothing raises.
2. **The veto.** Layer 1's whole justification is that a preference between a string and itself,
   or between two texts differing only in whitespace, becomes structurally unreachable rather than
   merely unlikely — §83 and §85 both had to void arms where the panel answered the slot on
   near-twins, and §78.1 measured a 96-100% preference produced by layout alone. A gate that lets
   one through has removed the only thing the layer is for.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

composite_panel = pytest.importorskip(
    "composite_panel",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


@dataclass
class _Pair:
    pair_id: str
    left: str
    right: str
    samples: int = 1
    question: str = "preference"


def _always_variant(_p: object, _a: str, _b: str, orientation: int, _s: int) -> tuple[str, str]:
    """A layer 3 that always names the manipulated text, whichever slot it is in."""
    return ("B" if orientation == 0 else "A"), "curious"


def test_the_gate_vetoes_identical_and_layout_only_pairs() -> None:
    """The two failure modes layer 1 exists to make unreachable."""
    gate = composite_panel.Composite(None).gate
    assert gate("a b c", "a b c")[0]
    assert gate("one two\n\nthree", "one  two\nthree")[0]
    assert gate("paragraph one\n\nparagraph two", "paragraph one\nparagraph two")[0]
    assert not gate("a b c", "a b d")[0]


def test_a_veto_answers_neither_on_every_cell_and_never_calls_layer_three() -> None:
    """The veto is final and free: layer 3 is not consulted, so nothing is spent on it."""
    calls: list[int] = []

    def counting(_p: object, _a: str, _b: str, orientation: int, _s: int) -> tuple[str, str]:
        calls.append(1)
        return "A", "curious"

    made = composite_panel.Composite(counting, verdict_source="test")(_Pair("p", "x y", "x  y"))
    assert made and all(c.choice == "neither" and not c.refused for c in made)
    assert calls == [], "layer 3 was called on a vetoed pair"


def test_the_slot_frame_is_not_inverted() -> None:
    """A layer 3 that always names the variant must read as `chose_variant` in both orientations."""
    made = composite_panel.Composite(_always_variant, verdict_source="test")(
        _Pair("p", "the original text", "the variant text")
    )
    assert len(made) == 4, "two personas x two orientations"
    assert all(c.chose_variant for c in made)
    assert {c.orientation for c in made} == {0, 1}

    def always_original(_p: object, _a: str, _b: str, orientation: int, _s: int) -> tuple[str, str]:
        return ("A" if orientation == 0 else "B"), "curious"

    mirrored = composite_panel.Composite(always_original, verdict_source="test")(
        _Pair("p", "the original text", "the variant text")
    )
    assert not any(c.chose_variant for c in mirrored)


def test_no_verdict_layer_is_a_tie_and_not_a_refusal() -> None:
    """§84 §6.4's floor: with no Track E survivor the composite declines to prefer, and says so.

    A refusal would report a transport failure; a tie reports an instrument with no opinion. The
    two are different events and §87.3 is the entry that had to separate them after the fact.
    """
    made = composite_panel.Composite(None)(_Pair("p", "wholly different", "text entirely"))
    assert all(c.choice == "neither" and not c.refused for c in made)
    assert all(c.model == "composite/no-verdict-layer" for c in made)


def test_layer_one_never_picks_a_side() -> None:
    """The design's central constraint: a counter has no valence, so it cannot vote.

    If this ever fails, the composite has started asserting craft doctrine as a premise — which
    §87.1 and §87.3 record as the hypothesis under test — and §82's definition of PREFERENCE as a
    human's blinded choice has been quietly overridden by a regex.
    """
    gated = composite_panel.Composite(None)
    for left, right in (("a b c", "a b c"), ("x\n\ny", "x y")):
        made = gated(_Pair("p", left, right))
        assert {c.choice for c in made} == {"neither"}
    assert all(entry["why"] for entry in gated.vetoed)


def test_live_axes_reports_every_admitted_counter_signed_left_to_right() -> None:
    """The composite records which counters saw a difference, whether or not the gate fired."""
    axes = composite_panel.live_axes("He felt afraid. [STATUS] HP 100", "He walked on. [STATUS] HP")
    assert set(axes) == set(composite_panel.MEMBERS), "keyed by axis, not by counter"
    assert axes["stat_flatten"]["counter"] == "system_digit_count"
    assert axes["stat_flatten"]["delta"] < 0, "digits were removed left-to-right"
    assert axes["stat_flatten"]["live"] is True
    same = composite_panel.live_axes("nothing moves here", "nothing moves here")
    assert all(not row["live"] for row in same.values())
