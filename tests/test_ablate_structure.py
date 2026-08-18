"""Structural invariants for `research/quality-measurement/ablate.py`.

**Why research code has tests in this suite at all.** It normally does not — `testpaths` is
`tests` and the research directory is deliberately outside the package boundary. This module is
the exception, and a measured one: on 2026-08-18 `em_dash_strip` was found to collapse every
blank line in a passage, because its tidy-up tail was `re.sub(r"\\s+", " ", ...)` and `\\s`
matches newlines. Nine of ten "em-dash-stripped" scenes were therefore the whole scene run
together as one block, and the panel's 0.0417 preference for the original — the number
`plan/stage-0-decisions.md` §74 read as "the panel prefers the em dashes" and the number the
taste-gap programme was then built on — was a preference for a paragraphed text over an
unparagraphed one. See §78.

The defect survived review because **every guard was a length guard**. `em_dash_report` counts
em dashes, words and comma splices; `Ablation.preserves_length` is a word-count property; and
`str.split()` treats "\\n\\n" and " " identically, so the recorded `word_delta_pct` of -0.30%
was correct and told nobody anything. A layout change is invisible to a length invariant, so it
needs an invariant of its own, and that is what this module is.

The fixture is synthetic rather than drawn from `corpora/toll.db`: the database is gitignored,
and a guard that only runs where the corpus happens to sit is not a guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(RESEARCH))

ablate = pytest.importorskip("ablate", reason="research/quality-measurement is not on the path")


#: Blank-line separated, because that is the convention the generated corpus uses and the one
#: the defect destroyed. Carries an em dash, a protected system-voice line, interiority verbs,
#: stake vocabulary and enough sentences that the sentence-level arms have something to remove.
FIXTURE = """The crate rode high on his back, roped at four points, and it had not shifted once.
That was the trouble with a good load. A bad load told you where it was.

The gate came up out of the haze the way it always did, all at once — two iron uprights sunk
into the rock. He knew the toll would cost him days he could not spare. He felt the weight of
it settle, and he remembered the last time he had paid.

**TOLL PAID — 9 days**

[STATUS] wren — Level 2 | HP 18/22 | MP ?/? | Gold ?

She wondered whether the debt would ever close. The risk was that it would not, and the
danger of that was worse than the loss. He wanted to turn back, but the road did not allow it.

"You pay here," the keeper said, "or you do not pass."

He understood then that the price was never the days. It was the arithmetic of them."""


def _arms() -> dict[str, object]:
    """Every registered transform, plus the two functions kept out of the registries."""
    arms: dict[str, object] = {}
    for group in (ablate.PERSONA_SET, ablate.READER_DEFECT_SET):
        for ablation in group:
            arms[ablation.key] = ablation.apply
    arms["em_dash_strip"] = ablate.em_dash_strip
    arms["em_dash_inject"] = ablate.em_dash_inject
    return arms


def test_em_dash_strip_preserves_paragraph_structure() -> None:
    """The repaired invariant, asserted on the exact property that was broken.

    Newline count and blank-line count must both survive the substitution untouched. This is
    stricter than "does not flatten": the transform replaces a mark with a comma and is
    entitled to change nothing else about the layout at all.
    """
    stripped = ablate.em_dash_strip(FIXTURE, 1.0)
    assert stripped != FIXTURE, "fixture must contain a strippable prose em dash"
    assert stripped.count("\n") == FIXTURE.count("\n"), (
        "em_dash_strip changed the newline count; it is reformatting the passage, "
        "which is the §78 defect"
    )
    assert stripped.count("\n\n") == FIXTURE.count("\n\n"), (
        "em_dash_strip changed the blank-line count; see §78"
    )


def test_em_dash_strip_leaves_protected_system_voice_alone() -> None:
    """`**TOLL PAID — 9 days**` and the `[STATUS]` line keep their dashes.

    `ablate._PROTECTED` is why §74's result is about a prose tell rather than about mangled
    stat blocks, and it is cheap to keep asserting.
    """
    stripped = ablate.em_dash_strip(FIXTURE, 1.0)
    assert "**TOLL PAID — 9 days**" in stripped
    assert "[STATUS] wren — Level 2" in stripped


@pytest.mark.parametrize("key", sorted(_arms()))
def test_no_transform_collapses_a_passage_to_one_block(key: str) -> None:
    """No arm may return a passage with every line break removed.

    The catastrophic class, banned outright rather than characterised: a variant that is one
    block of text differs from its original by layout before it differs by anything the arm
    claims to manipulate, and a panel comparing the two is answering a question nobody asked.
    Under the pre-§78 `em_dash_strip` this parametrisation failed on exactly one arm.
    """
    result = _arms()[key](FIXTURE, 1.0)
    if result == FIXTURE:
        pytest.skip(f"{key} is a no-op on this fixture")
    assert result.count("\n") > 0, (
        f"{key} removed every line break from the passage; see §78"
    )


#: The arms that route through `_rebuild`, which joins blocks with `_join` — a fixed single
#: newline — so a blank-line-separated source comes back single-newline separated. The round
#: trip through `paragraphs()` is lossy in exactly the direction that function's own docstring
#: warns about, and this set is the recorded blast radius (§78). It is pinned rather than fixed
#: because fixing `_join` changes the variant text of seven arms, which would invalidate the
#: recorded persona-battery and CDG numbers pooled over them; the re-spend is an operator call.
SEPARATOR_DOWNGRADING_ARMS = frozenset({
    "sentence_deletion",
    "sentence_shuffle",
    "paragraph_shuffle",
    "filler_inject",
    "destake",
    "deplete_matched",
    "interiority_strip",
    # Added deliberately, and the only member whose downgrade is load-bearing rather than a defect:
    # `interiority_deplete_matched` is `interiority_strip`'s control, and §81's primary comparison
    # puts the two against *each other*. Both must carry the same formatting, so the control has to
    # route through `_rebuild` exactly as the arm does. If `_join` is ever fixed, both leave this
    # set together and that comparison stays valid — the property to preserve when it happens.
    "interiority_deplete_matched",
})


def test_rebuild_arms_downgrade_the_paragraph_separator() -> None:
    """Characterisation, not approval: this records which arms lose the blank line.

    Kept as a test so the set cannot change silently in either direction. An arm leaving the
    set means someone fixed `_join` and every recorded number pooled over that arm needs
    re-reading; an arm joining it means a new transform inherited the defect.
    """
    downgraded = set()
    for key, apply in sorted(_arms().items()):
        result = apply(FIXTURE, 1.0)
        if result == FIXTURE:
            continue
        if result.count("\n\n") < FIXTURE.count("\n\n") and result.count("\n") > 0:
            downgraded.add(key)
    assert downgraded == set(SEPARATOR_DOWNGRADING_ARMS), (
        f"the set of separator-downgrading arms changed: {sorted(downgraded)} "
        f"!= {sorted(SEPARATOR_DOWNGRADING_ARMS)}; see §78 before updating this constant"
    )


def test_interiority_deplete_matched_matches_the_interiority_budget() -> None:
    """The replacement control removes the same word count as the arm it controls.

    Exact rather than approximate: `_interiority_plan` returns the budget and the fill closes the
    residual with the nearest remaining sentence, so the two arms differ by at most one sentence's
    rounding. Measured at 446 against 447 words over the ten drafted scenes. If this drifts, the
    interiority arm has a length confound again and §81's primary comparison stops being one.
    """
    base = len(FIXTURE.split())
    arm = base - len(ablate.interiority_strip(FIXTURE, 1.0).split())
    control = base - len(ablate.interiority_deplete_matched(FIXTURE, 1.0).split())
    assert arm > 0, "fixture must contain interiority sentences"
    assert control > 0, "fixture must contain non-interiority sentences to delete"
    assert abs(arm - control) <= max(2, round(0.15 * arm)), (
        f"interiority_deplete_matched removed {control} words against the arm's {arm}; "
        "the control is no longer matched"
    )


def test_interiority_deplete_matched_keeps_the_interiority_it_controls_for() -> None:
    """The control must not remove interiority itself, or both sides lose the same thing.

    `interiority_strip` drives the interiority-verb count to zero. Its control has to leave that
    count alone, otherwise the primary comparison is between two texts that both lack interiority
    and it measures nothing.
    """
    before = len(ablate._INTERIOR.findall(FIXTURE))
    stripped = len(ablate._INTERIOR.findall(ablate.interiority_strip(FIXTURE, 1.0)))
    controlled = len(ablate._INTERIOR.findall(
        ablate.interiority_deplete_matched(FIXTURE, 1.0)))
    assert before > 0
    assert stripped == 0, "the arm should remove every interiority-reporting sentence"
    assert controlled == before, (
        f"the control removed interiority too ({controlled} of {before} left); "
        "it must delete only sentences reporting no inner state"
    )


def test_deplete_matched_does_not_match_the_interiority_budget() -> None:
    """§74 called `deplete_matched` `interiority_strip`'s matched control. It is not one.

    `deplete_matched` takes its word budget from `_stake_plan`, so it is matched to `destake`.
    Against `interiority_strip` it removes a different amount of text — measured at -7.44%
    against -4.44% over the ten drafted scenes — and a "matched" control that removes 1.7x the
    words is the length confound it exists to remove. Asserted so the claim cannot be repeated
    from the docstring; §78 records it and `interiority_deplete_matched` is the control that
    actually matches.
    """
    interiority = ablate.interiority_strip(FIXTURE, 1.0)
    depleted = ablate.deplete_matched(FIXTURE, 1.0)
    base = len(FIXTURE.split())
    interiority_removed = base - len(interiority.split())
    depleted_removed = base - len(depleted.split())
    assert interiority_removed > 0, "fixture must contain interiority sentences"
    assert interiority_removed != depleted_removed, (
        "deplete_matched now matches interiority_strip's budget; if that was deliberate, "
        "update §74's claim and this test together"
    )
