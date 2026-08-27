"""Time-correct, model-facing views of accepted manuscript state.

Planning roles are not characters, but they still need a precise answer to "as of when?".
This module gives every planning call the same answer: choose a manuscript boundary, admit
only canon established on that side of it, then collapse superseded state before rendering.
When the ledger's story-position vocabulary cannot be translated to a scene ordinal, the
view keeps only unplaced canon rather than leaking later facts under a "current" label.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import litharness_contracts as lc

from litharness.domain import characters, extraction, state, worlds
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import Revision


@dataclass(frozen=True, slots=True)
class StoryStateView:
    """Active canon at one explicit manuscript boundary."""

    scene_logical_id: str | None
    scene_ordinal: int | None
    moment: state.StateMoment
    story_order_key: str | None
    temporal_scope: str
    coordinate_source: str
    active_records: tuple[lc.StateRecord, ...] = field(repr=False)
    superseded_records: tuple[lc.StateRecord, ...] = field(repr=False)

    @property
    def lines(self) -> tuple[str, ...]:
        projection = worlds.project(self.active_records)
        return tuple(
            projection.get(record.record_id) or state.describe(record)
            for record in self.active_records
            if projection.get(record.record_id, None) != ""
        )

    def to_jsonable(self) -> dict[str, Any]:
        hidden = worlds.hidden_record_ids(self.active_records, at=self.story_order_key)
        visible_records = tuple(
            record for record in self.active_records if record.record_id not in hidden
        )
        cast = characters.cast(visible_records)
        people = {character.subject for character in cast}
        projection = worlds.project(visible_records)
        facts = [
            projection.get(record.record_id) or state.describe(record)
            for record in visible_records
            if record.subject not in people
            and record.object_ref not in people
            and projection.get(record.record_id, None) != ""
        ]
        boundary: dict[str, Any] = {
            "moment": self.moment.value,
            "temporal_scope": self.temporal_scope,
            "coordinate_source": self.coordinate_source,
        }
        if self.scene_logical_id is not None:
            boundary["scene"] = self.scene_logical_id
        if self.scene_ordinal is not None:
            boundary["scene_ordinal"] = self.scene_ordinal
        if self.story_order_key is not None:
            boundary["story_order_key"] = self.story_order_key
        return {
            "boundary": boundary,
            "character_sheets": [character.to_jsonable() for character in cast],
            "established_facts": facts,
            "active_record_count": len(self.active_records),
            "undisclosed_record_count": len(hidden),
            "superseded_record_count": len(self.superseded_records),
        }


def _scenes(revision: Revision) -> list[Node]:
    return [
        node
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and not node.tombstoned
    ]


def at_scene(
    revision: Revision,
    records: Sequence[lc.StateRecord],
    logical_id: str,
    *,
    moment: state.StateMoment,
    story_order_key: str | None = None,
) -> StoryStateView:
    """Project canon at ``logical_id`` without treating reading order as story time."""
    scenes = _scenes(revision)
    try:
        ordinal = next(
            index for index, node in enumerate(scenes, start=1) if node.logical_id == logical_id
        )
    except StopIteration as error:
        raise KeyError(
            f"{logical_id!r} is not a live scene in revision {revision.revision_id}"
        ) from error

    attested_keys = {
        key
        for record in records
        if (key := state.order_key_of(record)) is not None
        and any(span.source.logical_id == logical_id for span in record.evidence)
    }
    if story_order_key is not None:
        cutoff = story_order_key
        coordinate_source = "explicit_story_order"
    elif len(attested_keys) == 1:
        cutoff = next(iter(attested_keys))
        coordinate_source = "evidence_attested"
    elif len(attested_keys) > 1:
        cutoff = None
        coordinate_source = "ambiguous_evidence"
    else:
        cutoff = state.scene_cutoff(records, ordinal)
        coordinate_source = "serial_ordinal" if cutoff is not None else "unavailable"
    source = tuple(records)
    temporal_scope = "bounded"
    if cutoff is None:
        # A null cutoff means "no filter" to the general state API.  At an explicitly named
        # scene that would be a future-state leak, so retain only timeless declarations and
        # report the abstention in the payload.
        source = tuple(record for record in records if state.order_key_of(record) is None)
        temporal_scope = "unplaced_only; scene-to-story coordinate unavailable"
    eligible = state.eligible_records(
        source,
        cutoff=cutoff,
        pov_character_id=None,
        excluded_predicates=tuple(extraction.CONFIGURATION_PREDICATES),
        moment=moment,
        logical_id=logical_id if moment is state.StateMoment.ENTERING and cutoff else None,
    )
    active, superseded = state.active_projection(
        eligible,
        changing_edge_predicates=(worlds.STANDS_AT_PREDICATE,),
        multi_valued_predicates=(worlds.ENTITY_ROLE_PREDICATE,),
    )
    return StoryStateView(
        scene_logical_id=logical_id,
        scene_ordinal=ordinal,
        moment=moment,
        story_order_key=cutoff,
        temporal_scope=temporal_scope,
        coordinate_source=coordinate_source,
        active_records=active,
        superseded_records=superseded,
    )


def current(
    revision: Revision,
    records: Sequence[lc.StateRecord],
) -> StoryStateView:
    """Project through the furthest accepted scene, or into scene one before drafting."""
    scenes = _scenes(revision)
    if not scenes:
        eligible = state.eligible_records(
            records,
            excluded_predicates=tuple(extraction.CONFIGURATION_PREDICATES),
        )
        active, superseded = state.active_projection(
            eligible,
            changing_edge_predicates=(worlds.STANDS_AT_PREDICATE,),
            multi_valued_predicates=(worlds.ENTITY_ROLE_PREDICATE,),
        )
        return StoryStateView(
            scene_logical_id=None,
            scene_ordinal=None,
            moment=state.StateMoment.THROUGH,
            story_order_key=None,
            temporal_scope="timeless; manuscript has no scenes",
            coordinate_source="unavailable",
            active_records=active,
            superseded_records=superseded,
        )
    latest = max(
        (index for index, node in enumerate(scenes, start=1) if node.content),
        default=0,
    )
    if latest:
        return at_scene(
            revision,
            records,
            scenes[latest - 1].logical_id,
            moment=state.StateMoment.THROUGH,
        )
    return at_scene(
        revision,
        records,
        scenes[0].logical_id,
        moment=state.StateMoment.ENTERING,
    )


def planning_records(
    records: Sequence[lc.StateRecord], view: StoryStateView
) -> tuple[lc.StateRecord, ...]:
    """Current state plus explicitly scheduled mystery design for a planning role.

    A whole-world brief formerly mixed every later and superseded fact into a value labelled
    simply ``world``.  Planning does need future reveal design, but it does not need future
    mutable state masquerading as current.  Keep the active boundary projection and add only
    the vocabulary that declares a mystery and its disclosure schedule.
    """
    reveal_design = {
        worlds.CLAIM_CONTENT,
        worlds.CLAIM_FALSE,
        worlds.DISCLOSED_TO,
        worlds.QUESTION_PREDICATE,
        worlds.REVEAL_SCENE,
    }
    by_id = {record.record_id: record for record in view.active_records}
    for record in records:
        if state.is_canon(record) and record.predicate in reveal_design:
            by_id.setdefault(record.record_id, record)
    return state.in_story_order(by_id.values())


__all__ = ["StoryStateView", "at_scene", "current", "planning_records"]
