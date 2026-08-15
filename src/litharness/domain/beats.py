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
    return tuple(
        Beat(
            logical_id=logical_id,
            ordinal=index + 1,
            of_total=len(scenes),
            title=by_id[logical_id].title,
            function=template.functions[index],
            template_id=template.template_id,
            story_order_key=(f"s{index + 1}" if template.chronological else None),
        )
        for index, logical_id in enumerate(scenes)
    )


__all__ = [
    "SIX_BEAT",
    "Beat",
    "BeatTemplate",
    "TemplateMismatch",
    "beats_for",
    "scene_nodes",
]
