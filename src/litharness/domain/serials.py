"""Serials: the open-ended production unit, and the arcs that close inside it.

Stage-0 §101 moved the unit of production from a fixed short book to a **serial** — arc,
chapter, scene — published chapter-wise at cadence. This module owns the three grains above a
scene and nothing else: it derives them, it does not persist them.

**Derived rather than stored, for `beats.py`'s reason.** The imported manuscript already *is*
the ordered, addressable set of work units; a parallel stored ordinal would create a second
answer to "which chapter is fourth" and the two would eventually disagree. `chapters_of` and
`arcs_of` read reading order and group it.

**Why the arc exists, and it is not decoration.** `template_for` picks `arc_template(n)` from a
book's *current* scene count, so on an open-ended book **appending one scene reassigns the
dramatic function of every scene already written** — a sixty-scene serial that grows to
sixty-one is a different sheet end to end, and `beat_job_id` derives from the template id, so
every beat job in the book remints. That is not a serial; it is a book being rewritten every
time it grows.

An arc fixes it by being the thing that closes. A serial has no template. **An arc has one**,
over its own scenes, and once the arc is complete its beats never move again no matter how much
serial arrives afterwards. §101's *"arcs open and close; the serial does not"* is that sentence
in code.

**What this module deliberately does not do.** It does not decide how many scenes make a chapter
or how many chapters make an arc — those are :class:`SerialShape`, supplied by the caller, the
same refusal `library.py` makes about assembly. It does not touch canon, retrieval, or the
context packet: §101 §3's *"state outlives context"* is a separate piece of work, and the one
property this module is responsible for there is that **nothing here is O(serial)** at the point
a scene is drafted (see :func:`window_for`).
"""

from __future__ import annotations

from dataclasses import dataclass

from litharness.domain.beats import (
    Beat,
    BeatTemplate,
    TemplateMismatch,
    arc_template,
    scene_nodes,
)
from litharness.domain.revision import Revision


class SerialShapeError(ValueError):
    """A shape that cannot describe a serial."""


@dataclass(frozen=True, slots=True)
class SerialShape:
    """How many scenes make a chapter, and how many chapters make an arc.

    **Operator-supplied, never inferred.** `library.py` refuses to decide how many scenes make
    a chapter and this refuses for the same reason: the tool does not know, and guessing puts a
    scheme into production that nobody declared.

    The defaults are the measured ones rather than round numbers. Four scenes per chapter is
    §101.2's finding: against the fitness shelf's 658 words per scene and the 8,192-token
    single-pass ceiling, a four-scene chapter leaves 1.23 chapters of context under the ceiling
    and a five-scene chapter leaves 0.79 — so cross-chapter measurement is available at four and
    impossible at five. Six chapters per arc is `SIX_BEAT`'s shape at chapter grain.
    """

    scenes_per_chapter: int = 4
    chapters_per_arc: int = 6

    def __post_init__(self) -> None:
        if self.scenes_per_chapter < 1:
            raise SerialShapeError("a chapter needs at least one scene")
        if self.chapters_per_arc < 1:
            raise SerialShapeError("an arc needs at least one chapter")

    @property
    def scenes_per_arc(self) -> int:
        return self.scenes_per_chapter * self.chapters_per_arc


@dataclass(frozen=True, slots=True)
class Chapter:
    """One publication unit: a run of scenes, positioned in its arc and in the serial."""

    index: int
    arc_index: int
    index_in_arc: int
    scene_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """Whether this chapter holds its shape's full complement of scenes.

        A trailing partial chapter is normal on a serial mid-production and is **not** an error:
        it is the chapter currently being written. It is not publishable, which is
        `library.py`'s rule and not this module's.
        """
        return bool(self.scene_ids)


@dataclass(frozen=True, slots=True)
class Arc:
    """A movement that opens and closes. The unit a beat template applies to."""

    index: int
    chapters: tuple[Chapter, ...]
    #: Whether every chapter this arc's shape calls for is present. **An incomplete arc has no
    #: beats**, because assigning a dramatic function to a scene in an arc whose length is not
    #: yet known is exactly the reassignment this module exists to prevent.
    closed: bool

    @property
    def scene_ids(self) -> tuple[str, ...]:
        return tuple(sid for chapter in self.chapters for sid in chapter.scene_ids)


def chapters_of(revision: Revision, shape: SerialShape) -> tuple[Chapter, ...]:
    """Group the live scenes, in reading order, into chapters of `shape`.

    The last chapter may be short; that is the one being written.
    """
    scenes = scene_nodes(revision)
    out: list[Chapter] = []
    for position in range(0, len(scenes), shape.scenes_per_chapter):
        block = tuple(scenes[position : position + shape.scenes_per_chapter])
        index = len(out) + 1
        out.append(
            Chapter(
                index=index,
                arc_index=(index - 1) // shape.chapters_per_arc + 1,
                index_in_arc=(index - 1) % shape.chapters_per_arc + 1,
                scene_ids=block,
            )
        )
    return tuple(out)


def arcs_of(revision: Revision, shape: SerialShape) -> tuple[Arc, ...]:
    """Group chapters into arcs. The last arc is open unless its chapters are all present."""
    chapters = chapters_of(revision, shape)
    out: list[Arc] = []
    for position in range(0, len(chapters), shape.chapters_per_arc):
        block = tuple(chapters[position : position + shape.chapters_per_arc])
        scenes_present = sum(len(c.scene_ids) for c in block)
        out.append(
            Arc(
                index=len(out) + 1,
                chapters=block,
                closed=(
                    len(block) == shape.chapters_per_arc
                    and scenes_present == shape.scenes_per_arc
                ),
            )
        )
    return tuple(out)


def beats_for_arc(
    revision: Revision, arc: Arc, template: BeatTemplate | None = None
) -> tuple[Beat, ...]:
    """The dramatic sheet for one **closed** arc, over that arc's own scenes.

    **Refuses an open arc rather than fitting a sheet to a partial one.** A template chosen from
    a length that is still growing reassigns every beat behind it the moment the next scene
    lands, which is the defect this module was written to prevent — so an arc gets its beats
    when it closes and never before. That is a refusal in `beats.py`'s own idiom: a scene-count
    mismatch refuses rather than interpolating.
    """
    if not arc.closed:
        raise TemplateMismatch(
            f"arc {arc.index} is still open ({len(arc.chapters)} chapters, "
            f"{len(arc.scene_ids)} scenes): a sheet fitted to a growing arc reassigns every "
            "beat behind it when the next scene lands"
        )
    sheet = template or arc_template(len(arc.scene_ids))
    # `beats.beats_for` zips a sheet against the WHOLE revision; an arc is a slice of one, so
    # the zip is done here rather than by handing that function a revision it would mis-measure.
    scenes = arc.scene_ids
    if len(scenes) != len(sheet):
        raise TemplateMismatch(
            f"{sheet.template_id} has {len(sheet)} beats but arc {arc.index} has "
            f"{len(scenes)} scenes"
        )
    return tuple(
        Beat(
            logical_id=logical_id,
            ordinal=position + 1,
            of_total=len(scenes),
            title=None,
            function=sheet.functions[position],
            template_id=sheet.template_id,
            story_order_key=logical_id,
        )
        for position, logical_id in enumerate(scenes)
    )


@dataclass(frozen=True, slots=True)
class Extension:
    """What appending one more chapter to this serial means, computed before anything is made."""

    chapter_index: int
    arc_index: int
    index_in_arc: int
    scenes_to_add: int
    opens_new_arc: bool
    closes_arc: bool


def next_chapter(revision: Revision, shape: SerialShape) -> Extension:
    """The next chapter this serial would grow by. **This is the endless part.**

    A serial is never finished, so this never refuses: there is always a next chapter. What it
    reports is where that chapter sits — whether it opens an arc, whether it closes one — so a
    caller can act on an arc boundary without recomputing the arithmetic and getting a different
    answer.

    It completes a partially-written chapter before starting a new one, so a serial interrupted
    mid-chapter resumes rather than abandoning the fragment.
    """
    scenes = len(scene_nodes(revision))
    per_chapter = shape.scenes_per_chapter
    written_whole, remainder = divmod(scenes, per_chapter)
    chapter_index = written_whole + 1
    index_in_arc = (chapter_index - 1) % shape.chapters_per_arc + 1
    return Extension(
        chapter_index=chapter_index,
        arc_index=(chapter_index - 1) // shape.chapters_per_arc + 1,
        index_in_arc=index_in_arc,
        scenes_to_add=per_chapter - remainder,
        opens_new_arc=index_in_arc == 1 and remainder == 0,
        closes_arc=index_in_arc == shape.chapters_per_arc,
    )


#: How many *chapters* of prior prose a scene's context may draw on, whatever the serial's
#: length. §101 §8's G0 requirement in one constant: **the packet must not grow O(serial)**.
#:
#: This is a bound on the window, not a claim that the window is sufficient — §101 §3's durable
#: canon is what carries everything older, and it is queried rather than concatenated. Two
#: chapters is what the 8,192-token single-pass ceiling admits at four scenes each (§101.2),
#: which makes the bound the same one the measurement side already lives under.
CONTEXT_WINDOW_CHAPTERS = 2


def window_for(
    revision: Revision, shape: SerialShape, chapter_index: int
) -> tuple[str, ...]:
    """The scene ids a chapter's drafting context may read directly. **Bounded, always.**

    The whole point is what it does *not* return: everything before the window. On a serial of
    four hundred chapters this returns the same number of scenes it returns on a serial of four,
    which is the property `test_the_window_does_not_grow_with_the_serial` pins and the reason
    §101 §8 asks for it to be measured rather than assumed.
    """
    chapters = chapters_of(revision, shape)
    first = max(0, chapter_index - 1 - CONTEXT_WINDOW_CHAPTERS)
    return tuple(
        sid for chapter in chapters[first : chapter_index - 1] for sid in chapter.scene_ids
    )


__all__ = [
    "CONTEXT_WINDOW_CHAPTERS",
    "Arc",
    "Chapter",
    "Extension",
    "SerialShape",
    "SerialShapeError",
    "arcs_of",
    "beats_for_arc",
    "chapters_of",
    "next_chapter",
    "window_for",
]
