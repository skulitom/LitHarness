"""The serial grain: arcs that close, chapters that publish, and a window that does not grow.

Stage-0 §101. Three properties are load-bearing and each fails by returning a plausible value
rather than by raising:

1. **An arc's beats never move once it closes.** `template_for` picks `arc_template(n)` from a
   book's current scene count, so on an open-ended book appending one scene reassigns the
   dramatic function of every scene already written — and `beat_job_id` derives from the
   template id, so every beat job remints. A serial that rewrites itself every time it grows is
   not a serial. This is the defect the arc grain exists to prevent, and it is the first test.
2. **Extension is always available and never loses a partial chapter.** "Endless" is the
   capability; resuming an interrupted chapter rather than abandoning it is what makes it
   usable.
3. **The drafting window is bounded independent of serial length** — §101 §8's G0 requirement
   that the packet must not grow O(serial), measured rather than assumed.
"""

from __future__ import annotations

import pytest

from litharness.domain.beats import TemplateMismatch, arc_template
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import Revision
from litharness.domain.serials import (
    CONTEXT_WINDOW_CHAPTERS,
    Position,
    SerialShape,
    SerialShapeError,
    arcs_of,
    beats_for_arc,
    chapter_positions,
    chapters_of,
    next_chapter,
    window_for,
)

SHAPE = SerialShape(scenes_per_chapter=4, chapters_per_arc=6)


def _serial(scenes: int) -> Revision:
    """A revision holding `scenes` live scene nodes in reading order, and nothing else."""
    nodes = [
        Node(
            logical_id="bk",
            kind=NodeKind.BOOK,
            parent_logical_id=None,
            position_key="000000",
            title="A Serial",
        )
    ]
    nodes += [
        Node(
            logical_id=f"s{i:04d}",
            kind=NodeKind.SCENE,
            parent_logical_id="bk",
            position_key=f"{i:06d}",
            title=None,
        )
        for i in range(1, scenes + 1)
    ]
    return Revision(
        revision_id="r" * 24,
        book_id="bk",
        branch_id="br",
        parent_revision_id=None,
        nodes=tuple(nodes),
    )


# --------------------------------------------------- where one scene sits, for the drafter


def test_a_scenes_position_agrees_with_the_chapters_it_is_grouped_into():
    """The arithmetic and the grouping are one answer, checked across every length that matters.

    `serials.py`'s own rule is that a second answer to "which chapter is fourth" would
    eventually disagree with the first. `chapter_positions` is a caller of `chapters_of` rather
    than a `divmod` beside it, and this is the assertion that would catch it becoming one.
    """
    for scenes in range(30):
        revision = _serial(scenes)
        positions = chapter_positions(revision, SHAPE)
        expected = {
            logical_id: Position(chapter.index, index + 1, len(chapter.scene_ids))
            for chapter in chapters_of(revision, SHAPE)
            for index, logical_id in enumerate(chapter.scene_ids)
        }
        assert positions == expected
        assert len(positions) == scenes


def test_the_shape_that_asserts_nothing_yields_no_position_at_all():
    """One scene per chapter is `library.py`'s refusal, and this is the same refusal.

    An empty mapping rather than `Position(4, 1, 1)` for every scene: the default declares no
    assembly scheme, and rendering one would turn the refusal into a scheme nobody chose.
    """
    assert chapter_positions(_serial(9), SerialShape(scenes_per_chapter=1)) == {}


def test_a_trailing_partial_chapter_reports_the_scenes_it_actually_has():
    """`scene 1 of 1`, not `scene 1 of 4`.

    The last chapter is the one being written. Reporting the shape's full complement would tell
    the writer about three scenes nobody has decided to write yet.
    """
    positions = chapter_positions(_serial(9), SHAPE)
    assert positions["s0009"] == Position(chapter_index=3, index_in_chapter=1, scenes_in_chapter=1)
    assert positions["s0008"] == Position(chapter_index=2, index_in_chapter=4, scenes_in_chapter=4)


def test_positions_are_keyed_by_the_same_scene_ids_the_beats_are():
    """Both read `scene_nodes`, so a beat's ordinal and its position are cut from one list.

    A position looked up by a key the beat does not carry would silently render nothing, which
    is the failure mode a `.get` cannot distinguish from "this book has no chapters".
    """
    revision = _serial(8)
    positions = chapter_positions(revision, SHAPE)
    beats = beats_for_arc(revision, arcs_of(revision, SerialShape(4, 2))[0])
    assert {beat.logical_id for beat in beats} == set(positions)
    assert [positions[beat.logical_id].chapter_index for beat in beats] == [1, 1, 1, 1, 2, 2, 2, 2]


# ------------------------------------------------------------------ the reason arcs exist


def test_a_closed_arcs_beats_do_not_move_when_the_serial_grows():
    """The defect this grain prevents, stated as the property it must hold.

    Whole-book templating reassigns every beat on every append. Arc-scoped templating cannot:
    arc 1's scenes and its sheet are both fixed the moment it closes.
    """
    short = _serial(SHAPE.scenes_per_arc)
    long = _serial(SHAPE.scenes_per_arc * 7 + 3)

    first_short = beats_for_arc(short, arcs_of(short, SHAPE)[0])
    first_long = beats_for_arc(long, arcs_of(long, SHAPE)[0])
    assert first_short == first_long

    # And the whole-book alternative really does move, which is what makes this worth pinning.
    assert arc_template(SHAPE.scenes_per_arc).template_id != arc_template(
        SHAPE.scenes_per_arc * 7 + 3
    ).template_id


def test_an_open_arc_refuses_a_sheet_rather_than_fitting_one():
    """A template fitted to a growing arc reassigns every beat behind it on the next append."""
    partial = _serial(SHAPE.scenes_per_arc + 5)
    arcs = arcs_of(partial, SHAPE)
    assert arcs[0].closed and not arcs[-1].closed
    with pytest.raises(TemplateMismatch):
        beats_for_arc(partial, arcs[-1])


def test_every_scene_in_a_closed_arc_gets_exactly_one_beat():
    revision = _serial(SHAPE.scenes_per_arc * 2)
    for arc in arcs_of(revision, SHAPE):
        beats = beats_for_arc(revision, arc)
        assert len(beats) == len(arc.scene_ids)
        assert [b.logical_id for b in beats] == list(arc.scene_ids)
        assert {b.ordinal for b in beats} == set(range(1, len(beats) + 1))


# ----------------------------------------------------------------------------- the grouping


def test_chapters_and_arcs_partition_the_scenes_in_order():
    revision = _serial(50)
    chapters = chapters_of(revision, SHAPE)
    flat = [sid for c in chapters for sid in c.scene_ids]
    assert flat == [f"s{i:04d}" for i in range(1, 51)]
    assert [sid for a in arcs_of(revision, SHAPE) for sid in a.scene_ids] == flat


def test_a_trailing_partial_chapter_is_normal_and_not_an_error():
    """It is the chapter currently being written."""
    revision = _serial(SHAPE.scenes_per_chapter * 3 + 1)
    chapters = chapters_of(revision, SHAPE)
    assert len(chapters) == 4
    assert len(chapters[-1].scene_ids) == 1


def test_an_empty_serial_has_no_chapters_and_still_has_a_next_one():
    revision = _serial(0)
    assert chapters_of(revision, SHAPE) == ()
    assert next_chapter(revision, SHAPE).chapter_index == 1


def test_a_shape_that_cannot_describe_a_serial_is_refused():
    for bad in ({"scenes_per_chapter": 0}, {"chapters_per_arc": 0}):
        with pytest.raises(SerialShapeError):
            SerialShape(**bad)


# ------------------------------------------------------------------------- endless extension


def test_a_serial_always_has_a_next_chapter_at_any_length():
    """"Endless" as a capability rather than a claim: extension never refuses."""
    for scenes in (0, 1, 7, 24, 25, 1000, 4001):
        extension = next_chapter(_serial(scenes), SHAPE)
        assert extension.scenes_to_add >= 1
        assert extension.chapter_index >= 1


def test_extension_finishes_a_partial_chapter_before_starting_a_new_one():
    """A serial interrupted mid-chapter resumes rather than abandoning the fragment."""
    partial = next_chapter(_serial(SHAPE.scenes_per_chapter * 2 + 1), SHAPE)
    assert partial.chapter_index == 3
    assert partial.scenes_to_add == SHAPE.scenes_per_chapter - 1
    assert not partial.opens_new_arc

    whole = next_chapter(_serial(SHAPE.scenes_per_chapter * 2), SHAPE)
    assert whole.chapter_index == 3
    assert whole.scenes_to_add == SHAPE.scenes_per_chapter


def test_arc_boundaries_are_reported_before_the_chapter_is_made():
    """So a caller can act on a boundary without recomputing the arithmetic differently."""
    at_boundary = next_chapter(_serial(SHAPE.scenes_per_arc), SHAPE)
    assert at_boundary.opens_new_arc
    assert at_boundary.arc_index == 2
    assert at_boundary.index_in_arc == 1

    closing = next_chapter(_serial(SHAPE.scenes_per_chapter * 5), SHAPE)
    assert closing.closes_arc
    assert closing.index_in_arc == SHAPE.chapters_per_arc


def test_repeated_extension_reproduces_the_grouping_it_predicted():
    """The arithmetic that plans the growth and the arithmetic that reads it must agree.

    Grown one chapter at a time from empty, every `Extension` must land where it said it would.
    Two independent implementations of the same index arithmetic is how they drift apart.
    """
    scenes = 0
    for _ in range(15):
        extension = next_chapter(_serial(scenes), SHAPE)
        scenes += extension.scenes_to_add
        chapters = chapters_of(_serial(scenes), SHAPE)
        landed = chapters[extension.chapter_index - 1]
        assert landed.index == extension.chapter_index
        assert landed.arc_index == extension.arc_index
        assert landed.index_in_arc == extension.index_in_arc
        assert len(landed.scene_ids) == SHAPE.scenes_per_chapter


# ------------------------------------------------------- the property G0 asks to be measured


def test_the_window_does_not_grow_with_the_serial():
    """§101 §8: the packet must not grow O(serial). Measured, not assumed.

    A four-hundred-chapter serial hands a scene the same amount of prior prose as a
    four-chapter one. Everything older is canon's job, queried rather than concatenated.
    """
    sizes = set()
    for chapters in (4, 40, 400):
        revision = _serial(SHAPE.scenes_per_chapter * chapters)
        sizes.add(len(window_for(revision, SHAPE, chapters)))
    assert len(sizes) == 1
    assert sizes.pop() == CONTEXT_WINDOW_CHAPTERS * SHAPE.scenes_per_chapter


def test_the_window_is_the_chapters_immediately_before_the_target():
    revision = _serial(SHAPE.scenes_per_chapter * 10)
    window = window_for(revision, SHAPE, 10)
    chapters = chapters_of(revision, SHAPE)
    expected = tuple(
        sid for c in chapters[10 - 1 - CONTEXT_WINDOW_CHAPTERS : 9] for sid in c.scene_ids
    )
    assert window == expected


def test_the_window_never_reaches_past_the_start():
    revision = _serial(SHAPE.scenes_per_chapter * 2)
    assert len(window_for(revision, SHAPE, 1)) == 0
    assert len(window_for(revision, SHAPE, 2)) == SHAPE.scenes_per_chapter
