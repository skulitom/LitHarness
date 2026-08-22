"""F4's canonicalizer and its two controls, pinned so the vacuous one stays labelled.

Stage-0 §99.1. The directive's default — compute every F4 statistic on canonicalized text — makes
the whitespace sham compare `canonical(x)` against `canonical(rewhitespace(x))`, which a total
canonicalizer renders **byte-identical before a model sees either**. Zero for any model, including
one that reads nothing but layout. That is a control that cannot fail (§50), and the danger is not
that it exists but that somebody later quotes it as evidence the instrument ignores formatting.

So these tests hold three things: the canonicalizer is total and idempotent, the whitespace check
declares its own vacuity, and the paragraph-break sham survives canonicalization while changing no
words — which is what makes it a control that can actually fail.

No GPU: `force_gpu` is imported by the module under test, so the whole file skips where torch is
absent.
"""

from __future__ import annotations

import pytest

f4 = pytest.importorskip(
    "surprisal_field", reason="research module; needs torch and the quality-measurement path"
)

PROSE = (
    "The archive was cold. Nobody had signed the register. She waited an hour.\n\n"
    "Outside the rain began. The road would be impassable by dark. He did not come."
)


# ------------------------------------------------------------------------ the canonicalizer


def test_canonical_is_idempotent():
    """Idempotence is what makes choice (i) meaningful: text goes in once and stays put."""
    messy = "One   line.\r\n  Two line.\n\n\n\nA new  paragraph.\nSame paragraph.  \n"
    once = f4.canonical(messy)
    assert f4.canonical(once) == once
    assert f4.is_canonical(once)


def test_canonical_changes_layout_and_not_one_word():
    """Anything beyond whitespace would be editing the prose rather than normalising its layout."""
    messy = "One   line.\r\n  Two line.\n\n\n\nA new  paragraph.\n"
    assert sorted(f4.canonical(messy).split()) == sorted(messy.split())


def test_canonical_absorbs_the_whitespace_transform():
    """The property the whole of §99.1 turns on. If this ever fails, choice (i) is not in force
    and every F4 number computed behind it is partly about formatting."""
    from force_harness import rewhitespace

    assert f4.canonical(rewhitespace(PROSE, 1.0)) == f4.canonical(PROSE)


# ---------------------------------------------------------------------------- the controls


def test_the_whitespace_control_declares_that_it_cannot_fail():
    """It is a unit test of our own canonicalizer, and it has to say so in its own output.

    Reporting it as §78.1's formatting control would be quoting a check that returns PASS for a
    model that reads nothing but layout.
    """
    coverage = f4.canonicalization_coverage(PROSE)
    assert coverage["status"] == "PASS"
    assert coverage["cannot_fail_on_the_model"] is True
    assert "not a model control" in coverage["kind"]


def test_the_paragraph_sham_survives_canonicalization_and_changes_no_words():
    """F4's real §78.1 control, and both halves matter.

    Surviving canonicalization is what lets it reach the model at all; changing no words is what
    makes a movement attributable to layout rather than to vocabulary.
    """
    moved = f4.paragraph_break_sham(PROSE)
    assert moved is not None
    assert moved != f4.canonical(PROSE)
    assert f4.canonical(moved) == moved
    assert sorted(moved.split()) == sorted(f4.canonical(PROSE).split())
    assert len(f4.paragraphs_of(moved)) == len(f4.paragraphs_of(PROSE)) + 1


def test_the_paragraph_sham_refuses_a_text_that_cannot_carry_it():
    """A transform that changed nothing is a placebo wearing a control's name (§95.15's B25)."""
    assert f4.paragraph_break_sham("One paragraph. Two sentences.") is None
    assert f4.paragraph_break_sham("Single.") is None


def test_the_paragraph_sham_is_deterministic():
    """A random boundary would make the control's own re-runs incomparable."""
    assert f4.paragraph_break_sham(PROSE) == f4.paragraph_break_sham(PROSE)


# -------------------------------------------------------------------------- shape statistics


def test_the_shape_statistic_refuses_a_short_series():
    assert f4.trajectory_shape([1.0, 2.0])["status"] == "INSUFFICIENT_N"


def test_burstiness_is_bounded_and_scale_free():
    """A burstiness that scaled with the mean would smuggle the monotone claim §99 voids back in
    through the shape statistic."""
    small = f4.trajectory_shape([1.0, 5.0, 2.0, 8.0, 1.5, 6.0, 2.5, 7.0, 3.0])
    scaled = f4.trajectory_shape([10 * v for v in [1.0, 5.0, 2.0, 8.0, 1.5, 6.0, 2.5, 7.0, 3.0]])
    assert -1.0 <= small["burstiness"] <= 1.0
    assert small["burstiness"] == pytest.approx(scaled["burstiness"], abs=1e-9)


def test_the_mean_is_named_so_it_cannot_be_quoted_as_a_quality_reading():
    """§99's opening paragraph voids any arm monotone in surprisal level, so the level is carried
    under a key that makes quoting it as quality visibly wrong."""
    shape = f4.trajectory_shape([1.0, 5.0, 2.0, 8.0, 1.5, 6.0, 2.5, 7.0, 3.0])
    assert "mean_surprisal_NOT_A_QUALITY_READING" in shape
    assert not any(k in shape for k in ("quality", "score", "rating"))


def test_the_declared_confound_is_measured_rather_than_assumed():
    assert f4.dialogue_share('"Hello," she said.\n\nHe left.') == 0.5
    assert f4.dialogue_share(PROSE) == 0.0


def test_the_module_selftest_passes():
    assert f4.selftest() == 0
