"""brief_capability's frozen bytes and registered definitions, checked without calls.

What this file pins: the three conditions are the registered ones and `empty` really is the
empty brief (the control every listing on disk was drawn under); P is a Jaccard over opening
*content* tokens and refuses to report a lock from one draw; KP0, the arm's own sham, sits
below within-writer agreement, which is the precondition for P meaning anything; T and C are
per-hundred-word membership counts; the call arithmetic is exact rather than a worst case;
and the paid run refuses without `--yes`.

What it does not establish: anything about any brief's effect. No call happens here, and
nothing under `derived/`, `results/` or `corpora/` is read or written.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "research" / "quality-measurement"
if str(_HERE) not in sys.path:  # house pattern; conftest inserts it too, this is defensive
    sys.path.insert(0, str(_HERE))

brief_capability = pytest.importorskip(
    "brief_capability",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def test_the_three_conditions_are_the_registered_ones() -> None:
    assert list(brief_capability.BRIEFS) == ["empty", "label", "situation"]
    # The control has to be the empty brief or it is not the condition every listing ran under.
    assert brief_capability.BRIEFS["empty"] == ""
    # §136's two-word shelf label, kept so "a brief works" cannot be read off "a label works".
    assert brief_capability.BRIEFS["label"] == "light fantasy"
    # The situation brief must carry no genre word and no tonal adjective, or a tonal move
    # under it would just be the tone word echoed back.
    situation = brief_capability.BRIEFS["situation"].lower()
    for banned in ("light", "fantasy", "grim", "dark", "cosy", "cozy", "funny", "warm"):
        assert banned not in situation


def test_the_call_arithmetic_is_exact_and_has_no_worst_case() -> None:
    assert brief_capability.plan_calls() == 4 * 3 * 4 == 48
    assert brief_capability.K_DRAWS == 4


def test_p_reads_the_opening_sentence_and_ignores_stopwords() -> None:
    tokens = brief_capability.opening_tokens("The screen and the door opened. A second sentence.")
    assert "screen" in tokens and "door" in tokens
    assert "the" not in tokens and "and" not in tokens
    # Only the opening sentence — the unit reader-read-5 §4.3 found locked.
    assert "second" not in tokens


def test_p_locks_at_one_on_repetition_and_at_zero_on_disjoint_openings() -> None:
    same = ["Every screen on Earth lit at once.", "Every screen on Earth lit at once."]
    assert brief_capability.premise_lock(same) == 1.0
    apart = ["Every screen on Earth lit at once.", "A bell rang in the orchard."]
    assert brief_capability.premise_lock(apart) == 0.0


def test_one_draw_reports_no_lock_rather_than_inventing_one() -> None:
    assert brief_capability.premise_lock(["a single opening."]) is None
    assert brief_capability.premise_lock([]) is None


def test_kp0_sits_below_within_writer_agreement_or_p_is_reading_the_prompt() -> None:
    """The arm's own sham. Two writers who repeat themselves but not each other."""
    locked = {
        "a": ["Every screen on Earth lit at once.", "Every screen on Earth lit at once."],
        "b": ["A bell rang in the orchard.", "A bell rang in the orchard."],
    }
    within = statistics.fmean(
        [brief_capability.premise_lock(texts) or 0.0 for texts in locked.values()]
    )
    between = brief_capability.between_writer_lock(locked)
    assert between is not None
    assert between < within
    assert between == 0.0  # they share no content token


def test_t_and_c_are_per_hundred_words_of_the_listing_itself() -> None:
    assert brief_capability.threat_per_100("he killed the monster") == 50.0
    assert brief_capability.threat_per_100("a quiet afternoon in the orchard") == 0.0
    assert brief_capability.coordinator_per_100("one and two then three") == pytest.approx(40.0)


def test_the_run_refuses_to_spend_without_yes(capsys: pytest.CaptureFixture[str]) -> None:
    assert brief_capability.main(["--run"]) == 1
    assert "--yes" in capsys.readouterr().err


def test_the_dry_run_prints_the_exact_plan_and_constructs_no_registry(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert brief_capability.main(["--dry-run"]) == 0
    captured = capsys.readouterr()
    assert "calls: 48 exactly" in captured.out
    assert "nothing spent" in captured.err


def test_the_selftest_passes() -> None:
    assert brief_capability.selftest() == 0
