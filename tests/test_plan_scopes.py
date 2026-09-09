"""Outline and writer author locks respect the same manuscript scene boundaries."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness.application import concept, outline
from litharness.domain import context, serials
from litharness.domain.beats import Beat
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plan_refinement import PlanRevision
from litharness.domain.revision import Revision
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_concept import _discovery, _example


def manuscript() -> Revision:
    return Revision(BOOK_ID, BRANCH_ID, (
        Node("book-root", NodeKind.BOOK, "1"),
        Node("part-east", NodeKind.PART, "1", parent_logical_id="book-root"),
        Node("chapter-east", NodeKind.CHAPTER, "1", parent_logical_id="part-east"),
        Node("scene-1", NodeKind.SCENE, "1", parent_logical_id="chapter-east"),
        Node("part-west", NodeKind.PART, "2", parent_logical_id="book-root"),
        Node("chapter-west", NodeKind.CHAPTER, "1", parent_logical_id="part-west"),
        Node("scene-2", NodeKind.SCENE, "1", parent_logical_id="chapter-west"),
    ))


def scope(logical_id: str, kind=lc.ResourceKind.MANUSCRIPT_SCENE) -> lc.ResourceRef:
    return lc.ResourceRef(
        project_id=PROJECT_ID, book_id=BOOK_ID, branch_id=BRANCH_ID,
        logical_id=logical_id, kind=kind,
    )


def lock(logical_id: str, target: lc.ResourceRef | None = None) -> lc.PlanItem:
    return lc.PlanItem(
        logical_id=logical_id, kind=lc.PlanKind.CONSTRAINT,
        text=f"Preserve the author decision {logical_id}.",
        authority=lc.PlanAuthority.INTENDED, locked=True, scope=target,
    )


def premise() -> lc.PlanItem:
    return lc.PlanItem(
        logical_id="premise", kind=lc.PlanKind.PREMISE,
        text="A traveller follows an impossible road.",
        authority=lc.PlanAuthority.INTENDED, locked=True,
    )


def beat(scene: str) -> Beat:
    return Beat(
        logical_id=scene, ordinal=1, of_total=1, title=None,
        function="setup", template_id="scope-test",
    )


def test_writer_omits_future_and_foreign_locks_before_spending_the_context_budget():
    first = lock("first", scope("scene-1"))
    second = replace(lock("second", scope("scene-2")), kind=lc.PlanKind.PROMISE)
    global_lock = lock("global")
    foreign_book = lock("foreign-book", replace(scope("scene-1"), book_id="another-book"))
    foreign_branch = lock("foreign-branch", replace(scope("scene-1"), branch_id="another-branch"))
    items = [premise(), first, second, global_lock, foreign_book, foreign_branch]
    for scene_id, included, excluded in (
        ("scene-1", {"first", "global"}, {"second", "foreign-book", "foreign-branch"}),
        ("scene-2", {"second", "global"}, {"first", "foreign-book", "foreign-branch"}),
    ):
        budget = sum(context.count_tokens(item.text) for item in items
                     if item.logical_id in included | {"premise"})
        packet = context.assemble(
            manuscript(), scene_id, plan_items=items, token_budget=budget, reserved_output=0,
        )
        assert {item.source_logical_id for item in packet.sections[context.CONSTRAINTS]} == included
        assert packet.used_tokens == budget
        omitted = {item.source_logical_id: item.reason for item in packet.omitted}
        assert {key for key in excluded if "scope" in omitted.get(key, "")} == excluded


@pytest.mark.parametrize(("target", "kind", "included_scenes"), [
    ("book-root", lc.ResourceKind.MANUSCRIPT_BOOK, {"scene-1", "scene-2"}),
    ("part-east", lc.ResourceKind.MANUSCRIPT_PART, {"scene-1"}),
    ("chapter-west", lc.ResourceKind.MANUSCRIPT_CHAPTER, {"scene-2"}),
    ("scene-1", lc.ResourceKind.MANUSCRIPT_SCENE, {"scene-1"}),
])
def test_outline_and_writer_agree_on_actual_manuscript_ancestor_scopes(
    target, kind, included_scenes,
):
    direction = lock("scoped-direction", scope(target, kind))
    items = (premise(), direction)
    base = PlanRevision(BOOK_ID, BRANCH_ID, items)
    revision = manuscript()
    for scene_id in ("scene-1", "scene-2"):
        request = outline.render_outline_request(
            items[0].text, (beat(scene_id),), base=base, revision=revision,
        )
        payload = json.loads(request.prompt)
        packet = context.assemble(revision, scene_id, plan_items=items)
        if scene_id in included_scenes:
            assert payload["author_locks"] == [lc.to_jsonable(direction)]
            assert direction.text in packet.render_constraints()
        else:
            assert "author_locks" not in payload
            assert "logical_id" not in payload["scenes"][0]
            assert "author_lock_ids" not in payload["scenes"][0]
            assert direction.text not in packet.render_constraints()


def test_outline_does_not_promote_unlocked_intentions_or_repeat_the_premise():
    drawn = concept.Concept.from_payload({**_example(), "discovery": _discovery()})
    generated = drawn.plan_item()
    original = premise()
    base = PlanRevision(BOOK_ID, BRANCH_ID, (original, generated))
    args = (original.text, (beat("scene-1"),))
    request = outline.render_outline_request(*args, base=base, concept=drawn)
    with_tree = outline.render_outline_request(
        *args, base=base, concept=drawn, revision=manuscript(),
    )
    assert request == with_tree
    payload = json.loads(request.prompt)
    assert "author_locks" not in payload
    assert outline.AUTHOR_LOCK_RULE not in payload["rules"]
    assert all("logical_id" not in scene and "author_lock_ids" not in scene
               for scene in payload["scenes"])

    locked_concept = replace(generated, locked=True)
    unlocked_direction = replace(lock("optional"), locked=False)
    future = lock("future", scope("scene-2"))
    foreign = lock("foreign", replace(scope("scene-1"), branch_id="other-branch"))
    edited = replace(base, items=(original, locked_concept, unlocked_direction, future, foreign),
                     plan_revision_id="")
    payload = json.loads(outline.render_outline_request(
        *args, base=edited, concept=drawn, revision=manuscript(),
    ).prompt)
    assert payload["author_locks"] == [lc.to_jsonable(locked_concept)]


def test_continuation_outline_maps_scene_and_ancestor_locks_to_local_ordinals():
    nodes = [Node("book-root", NodeKind.BOOK, "1")]
    for part_index, chapters in enumerate(((1, 2, 3), (4, 5), (6,)), start=1):
        part_id = f"part-{part_index}"
        nodes.append(Node(part_id, NodeKind.PART, str(part_index),
                          parent_logical_id="book-root"))
        for chapter_index in chapters:
            chapter_id = f"chapter-{chapter_index}"
            nodes.append(Node(chapter_id, NodeKind.CHAPTER, str(chapter_index),
                              parent_logical_id=part_id))
            for offset in (1, 2):
                scene_index = (chapter_index - 1) * 2 + offset
                nodes.append(Node(f"scene-{scene_index}", NodeKind.SCENE, str(offset),
                                  parent_logical_id=chapter_id))
    revision = Revision(BOOK_ID, BRANCH_ID, tuple(nodes))
    shape = serials.SerialShape(scenes_per_chapter=2, chapters_per_arc=3)
    arc = serials.arcs_of(revision, shape)[1]
    beats = serials.beats_for_arc(revision, arc)
    assert beats[0].logical_id == "scene-7" and beats[0].ordinal == 1

    applicable = (
        lock("global"),
        lock("first-cast", scope("scene-7")),
        lock("part-direction", scope("part-2", lc.ResourceKind.MANUSCRIPT_PART)),
        lock("chapter-direction", scope("chapter-5", lc.ResourceKind.MANUSCRIPT_CHAPTER)),
    )
    excluded = (
        lock("earlier-scene", scope("scene-1")),
        lock("foreign-branch", replace(scope("scene-7"), branch_id="another-branch")),
    )
    items = (premise(), *applicable, *excluded)
    base = PlanRevision(BOOK_ID, BRANCH_ID, items)
    payload = json.loads(outline.render_outline_request(
        items[0].text, beats, base=base, revision=revision, serial_arc_index=arc.index,
    ).prompt)
    assert payload["author_locks"] == [lc.to_jsonable(item) for item in applicable]
    expected = [
        ("scene-7", 1, ["global", "first-cast", "part-direction"]),
        ("scene-8", 2, ["global", "part-direction"]),
        ("scene-9", 3, ["global", "part-direction", "chapter-direction"]),
        ("scene-10", 4, ["global", "part-direction", "chapter-direction"]),
        ("scene-11", 5, ["global"]),
        ("scene-12", 6, ["global"]),
    ]
    assert [(scene["logical_id"], scene["ordinal"], scene["author_lock_ids"])
            for scene in payload["scenes"]] == expected
    for scene_id, _, lock_ids in expected:
        packet = context.assemble(revision, scene_id, plan_items=items)
        assert [item.source_logical_id for item in packet.sections[context.CONSTRAINTS]] == lock_ids


@pytest.mark.parametrize("kind", [lc.ResourceKind.MANUSCRIPT_BLOCK, lc.ResourceKind.ENTITY])
def test_unrepresentable_local_author_scope_is_not_silently_applied_to_the_whole_scene(kind):
    direction = lock("local", scope("local-target", kind))
    items = (premise(), direction)
    base = PlanRevision(BOOK_ID, BRANCH_ID, items)
    with pytest.raises(ValueError, match="scene-level constraint text cannot preserve"):
        context.assemble(manuscript(), "scene-1", plan_items=items)
    with pytest.raises(ValueError, match="scene-level constraint text cannot preserve"):
        outline.render_outline_request(
            items[0].text, (beat("scene-1"),), base=base, revision=manuscript(),
        )
