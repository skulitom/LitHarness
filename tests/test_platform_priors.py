"""Structural invariants for `research/quality-measurement/platform_priors.py`.

**Why research code has tests in this suite at all**, restated from
`test_ablate_structure.py` because the same argument applies and the reason is measured: a
manipulation family whose rungs are not what they claim produces a dose-response study with no
dose, and every guard that would notice is a *length* guard, which is exactly the class of
defect §78 recorded. The properties below are the ones a reader of the module cannot check by
eye and a paid GPU battery would discover only after it had run:

- the four rungs are four different texts, at scene grain and at book grain;
- the insert lane really is insertion — the original survives byte-for-byte at every dose;
- the blend lane is nested, so raising the dose adds edits and never rearranges them;
- a missing generation raises instead of quietly returning the original, which is the shape
  `bcr.battery_shelves` would otherwise turn into a silently-dropped family.

The fixture is synthetic and the generations are hand-written: the point is the algebra, and a
test that only runs where a gitignored corpus happens to sit is not a guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(RESEARCH))

ablate = pytest.importorskip("ablate", reason="research/quality-measurement is not on the path")
pp = pytest.importorskip(
    "platform_priors", reason="research/quality-measurement is not on the path"
)


SCENE = """The crate rode high on his back, roped at four points, and it had not shifted once.

That was the trouble with a good load. A bad load told you where it was.

The gate came up out of the haze the way it always did, all at once.

He knew the toll would cost him days he could not spare.

**TOLL PAID — 9 days**

[STATUS] wren — Level 2 | HP 18/22 | MP ?/? | Gold ?

She wondered whether the debt would ever close, and whether it mattered.

The road went on past the lintel, and the light on it did not change.

"You pay here," the keeper said, "or you do not pass."

He understood then that the price was never the days. It was the arithmetic of them."""


def _variants(scene: str = SCENE) -> object:
    """A hand-built cache: one blend arm that moves half the paragraphs, an inert placebo, and
    both insert arms carrying their full ladder."""
    blocks = ablate.paragraphs(scene)
    rewrite = list(blocks)
    for index in range(0, len(blocks), 2):
        rewrite[index] = rewrite[index] + " It was, in some sense, seemingly true."
    variants = pp.Variants()
    variants.add(scene, pp.Generated("purple_prose_dose", "s1", pieces=rewrite))
    variants.add(scene, pp.Generated(pp.PLACEBO, "s1", pieces=list(blocks)))
    variants.add(
        scene,
        pp.Generated(
            "character_flood", "s1",
            pieces=[f"{name} was there too, and said nothing." for name in pp.FLOOD_NAMES],
        ),
    )
    variants.add(
        scene,
        pp.Generated(
            "pov_fragment", "s1",
            pieces=[
                f"{pp.POV_NAME} watched, and counted to {index}, and said nothing."
                for index in range(max(pp.POV_LADDER.values()))
            ],
        ),
    )
    return variants


@pytest.mark.parametrize("key", ["purple_prose_dose", "character_flood", "pov_fragment"])
def test_every_rung_renders_a_distinct_text(key: str) -> None:
    variants = _variants()
    rendered = [pp.build(variants, key, SCENE, dose) for dose in pp.DOSES]
    assert len(set(rendered)) == len(pp.DOSES)
    assert SCENE not in rendered


@pytest.mark.parametrize("key", ["character_flood", "pov_fragment"])
def test_the_insert_lane_leaves_every_original_paragraph_byte_for_byte(key: str) -> None:
    variants = _variants()
    blocks = ablate.paragraphs(SCENE)
    for dose in pp.DOSES:
        variant = pp.build(variants, key, SCENE, dose)
        missing = [block for block in blocks if block not in variant]
        assert not missing, f"{key} at dose {dose} lost {len(missing)} paragraph(s)"


def test_blend_doses_are_nested_rather_than_resampled() -> None:
    """Raising the dose adds edits and never moves the ones already made.

    Nesting is what makes the ladder a dose of one thing. Four independent draws would produce a
    monotone-looking curve out of four different manipulations, and the isotonic fit the kill
    condition reads would then be fitting noise with a shape.
    """
    variants = _variants()
    blocks = ablate.paragraphs(SCENE)
    previous: set[int] = set()
    for dose in pp.DOSES:
        rendered = ablate.paragraphs(pp.build(variants, "purple_prose_dose", SCENE, dose))
        changed = set(pp.changed_indices(blocks, rendered))
        assert previous < changed, f"dose {dose} is not a strict superset of the dose below it"
        previous = changed


def test_no_family_collapses_the_passage_to_one_block() -> None:
    """§78's layout lesson: a blank-line corpus that comes back single-spaced is a different
    text, and every length guard reports that nothing happened."""
    variants = _variants()
    for key in ("purple_prose_dose", "character_flood", "pov_fragment"):
        for dose in pp.DOSES:
            variant = pp.build(variants, key, SCENE, dose)
            assert len(ablate.paragraphs(variant)) >= len(ablate.paragraphs(SCENE))
            assert "\n\n" in variant


def test_a_missing_generation_raises_instead_of_returning_the_original() -> None:
    with pytest.raises(pp.MissingVariant):
        pp.build(_variants(), "tense_shift", SCENE, 1.0)


def test_register_refuses_a_family_it_cannot_build() -> None:
    with pytest.raises(pp.MissingVariant):
        pp.register(_variants(), [SCENE], families=["suffering_load"], into={})


def test_the_bridged_ablation_declares_its_sign_is_a_hypothesis() -> None:
    """`ablate.Ablation.sign` means certified damage. Borrowing it for a platform prior is only
    honest if every shelf carries the word."""
    installed: dict[str, object] = {}
    pp.register(_variants(), [SCENE], families=["purple_prose_dose"], into=installed)
    assert "HYPOTHESISED" in installed["purple_prose_dose"].note  # type: ignore[attr-defined]


def test_an_inert_rewrite_does_not_certify() -> None:
    blocks = ablate.paragraphs(SCENE)
    inert = pp.Variants()
    inert.add(SCENE, pp.Generated("purple_prose_dose", "s1", pieces=list(blocks)))
    inert.add(SCENE, pp.Generated(pp.PLACEBO, "s1", pieces=list(blocks)))
    row = pp.certify(inert, SCENE, "purple_prose_dose", floor=pp.placebo_floor(inert, SCENE))
    assert not row["certified"]
    assert row["faults"]


def test_a_clean_arm_certifies_and_keeps_its_protected_spans() -> None:
    variants = _variants()
    row = pp.certify(
        variants, SCENE, "purple_prose_dose", floor=pp.placebo_floor(variants, SCENE)
    )
    assert row["certified"], row["faults"]
    assert row["system_voice"]["kept"] == row["system_voice"]["spans"]
    assert row["distinct_rungs"] == len(pp.DOSES)


def test_dose_counts_are_strictly_increasing_at_every_reachable_size() -> None:
    for total in range(pp.MIN_ELIGIBLE, 60):
        counts = pp.dose_counts(total)
        assert counts == sorted(set(counts)), f"{total} -> {counts}"


def test_spread_boundaries_are_prefix_nested() -> None:
    wide = pp.spread_boundaries(24, 4)
    for count in range(1, 4):
        assert pp.spread_boundaries(24, count) == wide[:count]


def test_book_grain_rungs_are_four_distinct_non_intact_books() -> None:
    variants = _variants()
    book = [(f"s{index}", SCENE) for index in range(4)]
    for key in ("purple_prose_dose", "character_flood", "pov_fragment"):
        rendered = [pp.build_book(variants, key, book, dose) for dose in pp.DOSES]
        assert len(set(rendered)) == len(pp.DOSES), key
        assert pp.book_text(book) not in rendered, key


def test_a_book_too_short_for_the_ladder_is_skipped_with_a_reason() -> None:
    """A shelf set that quietly covered three families out of six would read as a six-family run
    that found nothing. Every drop comes back with its reason."""
    variants = _variants()
    _, skipped = pp.shelves(variants, [("s0", SCENE), ("s1", SCENE)], families=["pov_fragment"])
    assert skipped and skipped[0]["family"] == "pov_fragment"
    assert skipped[0]["why"]
