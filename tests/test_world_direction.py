"""The §116 world and cost direction, restored where a world is now invented (stage-0 §255).

Routing, byte identity and scope only. Nothing here reads what a model does with the text.
"""

from __future__ import annotations

import pytest

from litharness.application import chapter_layout, concept, discovery, overview, world_agent
from litharness.domain import house
from litharness.domain.serials import SerialShape
from tests.test_concept import _discovery, _example
from tests.test_story_material import concept_payload


def _treatment(**overrides: str) -> discovery.Discovery:
    return discovery.Discovery("Place.", "Action.", "Growth.", **overrides)


def _concepts() -> dict[str, concept.Concept | None]:
    one_system = {**_example(), "second_system": None}
    return {
        "none": None,
        "legacy": concept.Concept.from_payload(one_system),
        "discovery": concept.Concept.from_payload({**one_system, "discovery": _discovery()}),
        "second system": concept.Concept.from_payload(_example()),
        "structured": concept.Concept.from_payload(concept_payload()),
    }


def test_the_world_direction_is_its_three_sentences() -> None:
    assert (
        f"{discovery.LIVED_WORLD} {discovery.READER_LIFE} {discovery.PERSONAL_COST}"
        == discovery.WORLD_DIRECTION
    )
    assert len(house.demands(discovery.WORLD_DIRECTION)) == 3


def test_the_protagonist_is_described_by_who_they_were_never_by_how_to_feel() -> None:
    """The target-readership direction says who the person was the day before, the §112
    declarative half; it never tells a writer to make them likeable or relatable, and it names
    no example life (§174.3, §262)."""
    text = discovery.READER_LIFE.lower()
    assert "twenties" in text and "a life that reader has lived" in text
    assert not any(word in text for word in ("likeable", "likable", "relatable", "sympathetic"))


def test_the_lived_world_names_no_list_of_pressures() -> None:
    """§263: the six-item pressure list was recited as the arc in all three draws that received
    it. The direction keeps the world a place people live in and lists nothing for a model to
    cover."""
    text = discovery.LIVED_WORLD.lower()
    assert "a place people live in" in text
    assert ":" not in text and text.count(",") <= 1
    assert not any(word in text for word in ("rivals", "teachers", "distance", "hunger"))


def test_invention_and_seed_share_one_world_direction_verbatim() -> None:
    layout = chapter_layout.WritingLayout.opening(6, SerialShape(1, 6), 1400)
    invention = {
        "discovery": discovery.render_request("").system,
        "development": concept.render_concept_request(
            "",
            scenes=6,
            discovery=_treatment(),
        ).system,
        "development, experience": concept.render_concept_request(
            "",
            scenes=6,
            discovery=_treatment(experience_brief="Proposed experience."),
        ).system,
        "structured": concept.render_material_request("", layout=layout).system,
    }
    for name, system in invention.items():
        assert (system or "").count(discovery.WORLD_DIRECTION) == 1, name
    for name, drawn in _concepts().items():
        seed = world_agent.render_seed_request("a listing", concept=drawn).system or ""
        assert seed.count(discovery.LIVED_WORLD) == 1, name
        # The seed's system text already says what a grant costs in the system's own terms.
        assert discovery.PERSONAL_COST not in seed, name


def test_world_direction_stays_out_of_the_floor_listing_drafting_grow_and_stored_directions() -> (
    None
):
    drawn = concept.Concept.from_payload({**_example(), "discovery": _discovery()})
    surfaces = {
        "grow": world_agent.render_grow_request("prose", logical_id="s1").system or "",
        "house floor": house.HOUSE_RULES,
        "scene drafting floor": house.with_house_rules("t", scene_draft=True),
        "listing": overview._system(None),
        "listing, supplied concept": overview._system(None, supplied_concept=True),
        "legacy concept task": concept._system(None),
        "legacy concept request": concept.render_concept_request("", scenes=6).system or "",
        "treatment render": _treatment().render(),
        # What a locked concept hands a scene writer without a scene plan (planner.packet_for).
        "concept render": drawn.render(include_placements=True),
        "listing material": drawn.render_for_listing(),
        **{f"direction {version}": text for version, text in discovery.DIRECTIONS.items()},
    }
    for name, text in surfaces.items():
        assert discovery.LIVED_WORLD not in text, name
        assert discovery.PERSONAL_COST not in text, name


@pytest.mark.parametrize("name", ["none", "legacy", "discovery", "second system", "structured"])
def test_supplied_material_still_takes_precedence(name: str) -> None:
    """A routing contract, not a semantic claim: the default comes before the precedence line."""
    assert discovery.LIVED_WORLD.startswith("By default")
    seed = world_agent.render_seed_request("a listing", concept=_concepts()[name]).system or ""
    assert seed.index(discovery.LIVED_WORLD) < seed.index(
        "Supplied motives and mechanics take precedence over defaults"
    )
    assert concept.MATERIAL_TASK.index(discovery.WORLD_DIRECTION) < concept.MATERIAL_TASK.index(
        "The author's supplied brief takes priority"
    )


def test_the_world_direction_speaks_none_of_this_system_s_own_vocabulary() -> None:
    found = sorted(
        word for word in house.MACHINERY_WORDS if word in discovery.WORLD_DIRECTION.lower()
    )
    assert not found, found
