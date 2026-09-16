"""Source accounting and reader facts survive planning without becoming canon or scores."""

import copy
import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import development_coverage as coverage
from litharness.application import outline, planner
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.plans import scene_plan_for
from litharness.domain.scene_brief import PREFIX, READER_PREFIX, SceneBrief
from litharness.providers.base import parse_schema_payload
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_outline import START, StubPlanner, a_book
from tests.test_scene_brief import brief_payload, outlined_payload
from tests.test_story_material import AUTHOR, intended

FACT = "She deliberately sold her family's seed reserve and concealed the sale."


def allocation(source):
    return {
        "source_id": source.story_material.for_planning()["source_id"],
        "entries": [
            {"development_id": "D1", "disposition": "planned", "scene_ordinals": [1],
             "reason": "The climb and its consequence share the opening activity."},
            {"development_id": "D2", "disposition": "planned", "scene_ordinals": [1, 2],
             "reason": "The choice begins during arrival and its consequences continue."},
            {"development_id": "D3", "disposition": "deferred", "scene_ordinals": [],
             "reason": "The later route requires cooperation not yet established."},
            {"development_id": "D4", "disposition": "deferred", "scene_ordinals": [],
             "reason": "The origin stays unresolved."},
        ],
    }


def response(source, *, chapters=True):
    payload = outlined_payload()
    payload["payoff_windows"] = []
    for entry in payload["scenes"]:
        entry["brief"]["reader_facts"] = [FACT] if entry["ordinal"] == 1 else []
    if chapters:
        payload["chapters"] = [
            {"chapter": s["ordinal"], "intent": s["brief"]["pursuit"],
             "adaptation": "Grouped within the supplied chapter.", "scenes": [s]}
            for s in payload.pop("scenes")
        ]
    payload["development_coverage"] = allocation(source)
    return payload


@pytest.mark.parametrize("facts", [[], [FACT]])
def test_old_briefs_keep_their_bytes_and_new_briefs_preserve_reader_knowledge(facts):
    old_payload = brief_payload()
    old = PREFIX + json.dumps(old_payload, ensure_ascii=False, sort_keys=True)
    assert SceneBrief.from_text(old).to_text() == old
    new = SceneBrief.from_payload({**old_payload, "reader_facts": facts})
    assert new.to_text().startswith(READER_PREFIX)
    assert SceneBrief.from_text(new.to_text()) == new
    rendered = new.render()
    if facts:
        assert FACT in rendered
        assert rendered.index(FACT) < rendered.index("Intended changes")
        assert "They need not be disclosed to other characters" in rendered
        assert rendered.index(old_payload["future_dependencies"][0]) > rendered.index(
            "Later-story dependencies"
        )
    else:
        assert "Facts to establish" not in rendered


@pytest.mark.parametrize("facts", [None, "a fact", [""], [12]])
def test_malformed_reader_facts_are_not_silently_dropped(facts):
    with pytest.raises(ValueError):
        SceneBrief.from_payload({**brief_payload(), "reader_facts": facts})


def test_stored_version_cannot_hide_or_invent_reader_facts():
    for prefix, payload in [
        (PREFIX, {**brief_payload(), "reader_facts": []}),
        (READER_PREFIX, brief_payload()),
    ]:
        with pytest.raises(ValueError, match="version"):
            SceneBrief.from_text(prefix + json.dumps(payload))


def test_allocation_accepts_grouping_spanning_and_deferment_with_stable_scene_ids():
    source = intended()
    payload = allocation(source)
    # Response-local ordinals need not equal the manuscript's chapter or scene numbers.
    payload["entries"].reverse()
    stored = coverage.to_text(payload, source.story_material, {1: "scene-11", 2: "scene-12"})
    result = json.loads(stored.removeprefix(coverage.PREFIX))
    assert result["requested_scene_ids"] == ["scene-11", "scene-12"]
    assert [e["development_id"] for e in result["entries"]] == ["D1", "D2", "D3", "D4"]
    assert result["entries"][0]["scene_ids"] == ["scene-11"]
    assert result["entries"][1]["scene_ids"] == ["scene-11", "scene-12"]
    assert result["entries"][2]["scene_ids"] == []
    payload["entries"][-1].update(disposition="established", scene_ordinals=[],
                                  reason="The accepted prefix contains the climb.")
    assert '"established"' in coverage.to_text(payload, source.story_material, {1: "s11", 2: "s12"})


@pytest.mark.parametrize("damage", [
    lambda p: p.update(source_id="another-source"),
    lambda p: p.pop("source_id"),
    lambda p: p.update(entries="text"),
    lambda p: p["entries"].pop(),
    lambda p: p["entries"].append(copy.deepcopy(p["entries"][0])),
    lambda p: p["entries"][0].update(development_id="invented"),
    lambda p: p["entries"][0].update(disposition="fulfilled"),
    lambda p: p["entries"][0].update(scene_ordinals=[]),
    lambda p: p["entries"][0].update(scene_ordinals=[True]),
    lambda p: p["entries"][0].update(scene_ordinals=[3]),
    lambda p: p["entries"][0].update(scene_ordinals=[1, 1]),
    lambda p: p["entries"][0].update(reason=" "),
    lambda p: p["entries"][0].update(rating=10),
    lambda p: p["entries"][2].update(scene_ordinals=[1]),
])
def test_invalid_accounting_refuses_unknown_sources_coordinates_and_missing_developments(damage):
    source = intended()
    payload = allocation(source)
    damage(payload)
    with pytest.raises(ValueError):
        coverage.to_text(payload, source.story_material, {1: "s1", 2: "s2"})


@pytest.mark.parametrize("chapters", [False, True])
def test_schema_requires_accounting_and_reader_facts_only_in_structured_mode(tmp_path, chapters):
    source = intended()
    with SqliteStore.open(tmp_path / "schema.db") as store:
        revision = a_book(store, scenes=6, extra_plan_items=(source.plan_item(),))
        beats = beats_for(revision, arc_template(6))
        request = outline.render_outline_request(
            "Explore", beats, base=store.plan_revision(BOOK_ID, BRANCH_ID), concept=source,
            chapter_by_scene={b.logical_id: b.ordinal for b in beats} if chapters else None,
        )
    payload = response(source, chapters=chapters)
    assert parse_schema_payload(json.dumps(payload), request.schema) == payload
    payload.pop("development_coverage")
    assert parse_schema_payload(json.dumps(payload), request.schema) is None
    payload = response(source, chapters=chapters)
    scenes = payload["chapters"][0]["scenes"] if chapters else payload["scenes"]
    scenes[0]["brief"].pop("reader_facts")
    with pytest.raises(outline.OutlineOutputError, match="reader_facts"):
        outline._statements({"scenes": scenes}, len(scenes), structured=True,
                            reader_facts_required=True)
    properties = request.schema["properties"]
    scene_schema = (properties["chapters"]["items"]["properties"]["scenes"]
                    if chapters else properties["scenes"])
    assert "reader_facts" in scene_schema["items"]["properties"]["brief"]["required"]
    assert "development_coverage" not in outline.CHAPTER_OUTLINE_SCHEMA["properties"]


@pytest.mark.parametrize("damage", [None, "missing_development", "missing_reader_facts"])
def test_accounting_and_facts_are_atomic_scoped_and_replay_safe(tmp_path, monkeypatch, damage):
    source = intended()
    response_payload = response(source)
    if damage == "missing_development":
        response_payload["development_coverage"]["entries"].pop()
    if damage == "missing_reader_facts":
        response_payload["chapters"][0]["scenes"][0]["brief"].pop("reader_facts")
    with SqliteStore.open(tmp_path / "book.db") as store:
        a_book(store, scenes=6, extra_plan_items=(source.plan_item(),))
        before = store.plan_revision(BOOK_ID, BRANCH_ID)
        model = StubPlanner(response_payload)
        monkeypatch.setattr(cli, "build_default_registry", lambda: model)
        args = cli.build_parser().parse_args([
            "--project", PROJECT_ID, "--chapter-scenes", "1", "--arc-chapters", "6", "tick",
        ])
        conductor = cli._conductor(store, args)
        job = conductor.select(store, "worker", START, 60)
        assert job.job_kind == outline.BOOK_OUTLINE
        handler = conductor.handlers[outline.BOOK_OUTLINE]
        handler(job, START)
        after = store.plan_revision(BOOK_ID, BRANCH_ID)
        if damage:
            assert after == before
            assert not store.latest_decision_for(job.job_id).accepted
            return
        assert after != before
        account = after.item("development-coverage-scene-1")
        assert account.authority is lc.PlanAuthority.INTENDED and not account.locked
        assert store.decision_for_revision(after.plan_revision_id).accepted
        handler(replace(job, attempts=job.attempts + 1), START + 1)
        assert len(model.requests) == 1
        assert store.plan_revision(BOOK_ID, BRANCH_ID) == after
        writer = conductor.select(store, "writer", START + 2, 60)
        assert writer.job_kind == planner.SCENE_DRAFT
        prompt = writer.payload["prompt"]
        brief = SceneBrief.from_text(scene_plan_for(after.items, "scene-1").text)
        assert brief.reader_facts == (FACT,)
        assert brief.render() in prompt and AUTHOR in prompt
        assert coverage.PREFIX not in prompt and "development_coverage" not in prompt
        assert "LATER_EVENT" not in prompt and "OPEN_QUESTION" not in prompt
        assert READER_PREFIX not in prompt
        assert all(r.predicate != "reader_facts" for r in store.state_records(BOOK_ID, BRANCH_ID))
