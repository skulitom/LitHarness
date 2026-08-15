"""Beats: the fixed sheet Stage 1 asks for, derived rather than stored.

§17 Stage 1 wants a "template planner (fixed beat sheet)" — not a creative one. §9's
Narrative Planning is a separate pillar, and §20.6 records the ordering trap around it, so
anything here that looked like arc generation would be inventing §9's shape ahead of its
consumer.

*(This said the pillar "does not exist", which stopped being true when
`application/narrative_planner.py` shipped the bounded directive-interpretation producer §9.3
records. What is still absent is the part this module would otherwise be tempted to invent:
whole-book plan generation, a foreshadow/payoff ledger, a progression schedule, and any
template beyond `SIX_BEAT`.)*

**A beat is a scene node plus its position in a template.** Nothing is persisted: the
imported manuscript already *is* the ordered, addressable set of work units.
`Revision.in_reading_order()` walks `children_of`, which sorts by
`(parse_key(position_key), logical_id)` and drops tombstones — a total order that exists
and is tested. Storing a parallel ordinal would create a second answer to "which scene is
third", and the two would eventually disagree.

**A scene-count mismatch refuses rather than interpolating.** The template has six
functions; a book with five scenes or seven has no defensible mapping onto it, and picking
one silently would attach the wrong dramatic function to every beat after the gap. §17's
exit is about the six-scene fixtures, so the honest failure is to say the template does not
fit and stop.
"""

from __future__ import annotations

from dataclasses import dataclass

from litharness.domain.nodes import NodeKind
from litharness.domain.revision import Revision


@dataclass(frozen=True, slots=True)
class BeatTemplate:
    """A fixed sheet of dramatic functions, one per scene."""

    template_id: str
    functions: tuple[str, ...]
    #: Whether this sheet's reading order is also its **story** order.
    #:
    #: The one place in this project entitled to answer that, and the answer is a property of
    #: the sheet rather than an inference about a book. `domain/state.py` forbids deriving a
    #: story position from a scene's ordinal, and the measurement behind that stands: the
    #: mystery fixture's scene 5 is an analepsis attested at `s1`, so ordinal-derived
    #: positions mis-slice it. What the measurement refutes is *deriving* an order from
    #: reading order for an arbitrary book — not a template *stating* that the story it lays
    #: out runs forwards. `SIX_BEAT` does run forwards, by construction: setup, inciting,
    #: rising, turn, crisis, resolution is a chronological progression with no flashback beat
    #: in it, and a book planned from it cannot contain one because there is no beat to hold
    #: it.
    #:
    #: **Defaults to False, which is the direction that makes forgetting cheap.** A future
    #: template that omits this loses extraction coverage on the books it plans; one that
    #: wrongly claimed True would mint a false story order that nothing downstream could
    #: detect, because the system would be checking its own invention.
    chronological: bool = False

    def __len__(self) -> int:
        return len(self.functions)


#: The six-beat sheet both golden fixtures fit. Deliberately the only one: a second
#: template with no book to use it would be a shape with no consumer.
SIX_BEAT = BeatTemplate(
    "template.six-beat.v0",
    ("setup", "inciting", "rising", "turn", "crisis", "resolution"),
    chronological=True,
)


@dataclass(frozen=True, slots=True)
class Beat:
    logical_id: str
    ordinal: int
    of_total: int
    title: str | None
    function: str
    template_id: str
    #: Where this beat sits in story time, when the template is entitled to say — `None`
    #: otherwise, and `None` means *abstain*, exactly as `attested_position` does.
    story_order_key: str | None = None


class TemplateMismatch(Exception):
    """The live scene count does not match the template. Never silently interpolated."""


#: Beats that happen **once** in a story, and where. A fraction of the way through, except
#: for the ones pinned to an end — a book has one inciting incident whether it is six scenes
#: or sixty, and distributing the six functions proportionally would give a sixty-scene book
#: twelve of them.
_SINGULAR = (("setup", 1), ("inciting", 2), ("turn", 0.6), ("crisis", -2), ("resolution", -1))

#: What every scene that is not a singular beat is doing: the story getting worse.
_REPEATED = "rising"


def arc_template(scenes: int) -> BeatTemplate:
    """A chronological sheet of `scenes` beats, on the six-beat arc.

    §17 Stage 3 needs a book of 50-80k words and `SIX_BEAT` is exactly six functions long, so
    `beats_for` refuses every longer book — the wall Book Zero hits before it starts.

    **It reproduces `SIX_BEAT` exactly at six, and that is the property that makes it safe.**
    A generalisation that drifted at n=6 would be a *different* template quietly relabelling
    every beat of both golden fixtures, and `beat_job_id` carries the template id rather than
    its content, so nothing downstream would notice. `test_the_arc_reproduces_the_six_beat_sheet`
    pins it.

    **Singular beats stay singular.** A story has one inciting incident and one crisis at any
    length; only *rising* repeats. Spreading the six functions proportionally — the obvious
    implementation — would give a sixty-scene book twelve inciting incidents, which is not a
    longer story but a broken one.

    Refuses below six: the six-beat sheet is the floor this project's fixtures and gates are
    built on, and an arc with fewer scenes than named beats has no defensible assignment.
    """
    if scenes < len(SIX_BEAT):
        raise TemplateMismatch(
            f"an arc needs at least {len(SIX_BEAT)} scenes to carry its named beats; "
            f"asked for {scenes}"
        )
    functions = [_REPEATED] * scenes
    for name, where in _SINGULAR:
        index = (scenes + int(where)) if isinstance(where, int) and where < 0 else (
            int(where) - 1 if isinstance(where, int) else _proportional(scenes, where)
        )
        functions[index] = name
    return BeatTemplate(f"template.arc-{scenes}.v0", tuple(functions), chronological=True)


def _proportional(scenes: int, fraction: float) -> int:
    """The scene at `fraction` of the way through, as a 0-based index.

    Rounded up so a six-scene book puts the turn at scene 4 — which is where `SIX_BEAT` has
    it, and the whole reason this rounds the way it does.
    """
    return min(scenes - 1, max(0, -(-int(scenes * fraction * 100) // 100) - 1))


def scene_nodes(revision: Revision) -> list[str]:
    """Live scene logical ids in reading order."""
    return [
        node.logical_id
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE
    ]


def beats_for(revision: Revision, template: BeatTemplate = SIX_BEAT) -> tuple[Beat, ...]:
    """Zip the live scenes against the template, in reading order."""
    scenes = scene_nodes(revision)
    if len(scenes) != len(template):
        raise TemplateMismatch(
            f"{template.template_id} has {len(template)} beats but the book has "
            f"{len(scenes)} live scene(s); a template that does not fit is not applied, "
            "because guessing the mapping mislabels every beat after the gap"
        )
    by_id = {node.logical_id: node for node in revision.nodes}
    # **Zero-padded to the book's own width, because order keys are compared as strings.**
    # `s10 < s2` lexicographically, so an unpadded key silently reverses story order the
    # moment a book passes nine scenes — and every consumer compares them that way:
    # `records_before` slices the context packet on `<=`, `changes_between` matches on
    # equality, and propagation's `fact_changed` filter asks which records come after the
    # change. Measured on a 24-scene Book Zero, whose ledger read back s1, s10, s11 … s2.
    # Width 1 at six scenes, so `s1` to `s6` is unchanged and matches what both fixtures author.
    width = len(str(len(scenes)))
    return tuple(
        Beat(
            logical_id=logical_id,
            ordinal=index + 1,
            of_total=len(scenes),
            title=by_id[logical_id].title,
            function=template.functions[index],
            template_id=template.template_id,
            story_order_key=(
                f"s{index + 1:0{width}d}" if template.chronological else None
            ),
        )
        for index, logical_id in enumerate(scenes)
    )


__all__ = [
    "SIX_BEAT",
    "Beat",
    "BeatTemplate",
    "TemplateMismatch",
    "arc_template",
    "beats_for",
    "scene_nodes",
]
