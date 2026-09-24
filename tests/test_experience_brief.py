"""Automatic experience intent survives planning without becoming author authority."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, discovery, export, outline, world_agent
from litharness.application.planner import packet_for
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.plan_refinement import PlanRevision
from litharness.domain.revision import new_book
from litharness.providers.base import parse_schema_payload
from litharness.providers.fake import FakeProvider
from tests.test_concept import _discovery, _example, _scripted

EXPERIENCE = (
    "Desire: share the high garden with her brother. "
    "Use: wake a seed with her existing touch magic and climb its stem. "
    "Consequence: they sit in the garden and taste its fruit. "
    "Next desire: grow a shelter there. "
    "Coverage: reach and enjoy the garden in the opening chapter; build later; "
    "leave the reef's origin unresolved. The fruit and climbing route can change."
)


def treatment():
    return discovery.Discovery.from_invention({**_discovery(), "experience_brief": EXPERIENCE})


@pytest.mark.parametrize("brief", ["", "Keep the brother on the ground until chapter three."])
def test_discovery_invents_experience_under_author_direction_in_its_existing_call(brief):
    request = discovery.render_request(brief)
    assert request.profile == "writer.discovery.v18"
    assert "experience_brief" in request.schema["required"]
    assert "Desire, Use, Consequence, Next desire and Coverage" in request.system
    assert "The author's supplied brief takes priority" in request.system
    assert "revisable story proposals" in request.system
    assert brief in request.prompt
    # The provider's shape boundary refuses omission before concept development.
    assert parse_schema_payload(json.dumps(_discovery()), request.schema) is None
    payload = {**_discovery(), "experience_brief": EXPERIENCE}
    assert parse_schema_payload(json.dumps(payload), request.schema) == payload


@pytest.mark.parametrize("invalid", [None, "", "   ", 3, {}])
def test_present_but_malformed_experience_is_rejected(invalid):
    with pytest.raises(ValueError, match="experience_brief must be non-empty"):
        discovery.Discovery.from_invention({**_discovery(), "experience_brief": invalid})


def test_legacy_discovery_does_not_acquire_generated_material_during_read():
    old = {**_discovery(), "version": "magical-discovery.v3"}
    retained = discovery.Discovery.from_payload(old)
    assert retained.to_jsonable() == old
    assert retained.experience_brief == ""
    assert "Proposed experience brief" not in retained.render()


def test_experience_names_and_quantities_use_existing_preparation_rules():
    with pytest.raises(ValueError, match="reserved names: standing"):
        discovery.Discovery.from_invention({
            **_discovery(), "experience_brief": "She invents the Standing.",
        })
    source = replace(treatment(), experience_brief="Reach the garden nineteen minutes later.")
    assert source.has_quantities()
    edit = {"field": "experience_brief", "before": "nineteen minutes", "after": "a while"}
    prepared = source.with_precision_edits({"edits": [edit]})
    assert prepared.experience_brief == "Reach the garden a while later."
    assert prepared.world == source.world
    assert source.experience_brief == "Reach the garden nineteen minutes later."
    drawn = concept.Concept.from_development(_example(), source, author_brief="Wait nineteen days.")
    fields, protected = drawn.precision_material()
    assert fields["discovery.experience_brief"] == source.experience_brief
    assert protected["author_brief"] == "Wait nineteen days."
    revised = drawn.with_precision_edits({
        "edits": [{**edit, "field": "discovery.experience_brief"}],
    })
    assert revised.discovery == prepared
    assert revised.author_brief == drawn.author_brief


@pytest.mark.parametrize("arc", [1, 2])
def test_planner_gets_experience_separately_from_author_brief_and_opening_staging(arc):
    source = treatment()
    author = "AUTHOR_CHOICE: the brother stays on the ground until chapter three."
    answer = {**_example(), "discovery": {**_discovery(), "experience_brief": "REPLACEMENT"}}
    drawn = concept.Concept.from_development(answer, source, author_brief=author)
    restored = concept.Concept.from_text(drawn.to_text())
    assert restored.discovery == source
    assert restored.author_brief == author
    assert not restored.plan_item().locked
    assert restored.plan_item().authority == lc.PlanAuthority.INTENDED
    development = concept.render_concept_request(author, scenes=6, discovery=source)
    assert EXPERIENCE in development.prompt
    assert author in development.prompt
    assert "The author's supplied brief takes priority" in development.system
    revision = new_book("b", "main", title="Garden", scenes=6)
    base = PlanRevision("b", "main", (
        lc.PlanItem(
            logical_id="premise", kind=lc.PlanKind.PREMISE, text="Garden",
            authority=lc.PlanAuthority.INTENDED,
        ),
    ))
    request = outline.render_outline_request(
        "Garden", beats_for(revision, arc_template(6)),
        base=base, concept=restored, serial_arc_index=arc,
    )
    payload = json.loads(request.prompt)
    assert payload["book_concept"]["author_brief"] == author
    assert payload["book_concept"]["discovery"]["experience_brief"] == EXPERIENCE
    assert "opening" not in payload["book_concept"]["discovery"]
    assert concept.EXPERIENCE_ARC_RULE in payload["rules"]
    assert "create no author deadlines" in concept.EXPERIENCE_ARC_RULE
    assert EXPERIENCE not in restored.render_for_world()
    assert EXPERIENCE not in restored.render_for_listing()
    assert EXPERIENCE not in world_agent.render_seed_request("Garden", concept=restored).prompt
    legacy = replace(restored, discovery=replace(source, experience_brief=""))
    legacy_request = outline.render_outline_request(
        "Garden", beats_for(revision, arc_template(6)),
        base=base, concept=legacy,
    )
    assert concept.EXPERIENCE_ARC_RULE not in json.loads(legacy_request.prompt)["rules"]


def test_cli_keeps_generated_brief_through_persistence_and_original_brief_for_drafting(
    tmp_path, monkeypatch,
):
    author = "Keep the brother on the ground until chapter three."
    brief_file = tmp_path / "brief.txt"
    brief_file.write_text(author, encoding="utf-8")
    source = treatment()
    call = _scripted(source.to_jsonable(), _example(), {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    db, out = tmp_path / "book.db", tmp_path / "concept"
    assert cli.main([
        "--database", str(db), "concept", "--brief-file", str(brief_file),
        "--scenes", "6", "--out", str(out),
    ]) == cli.EXIT_OK
    assert [request.profile for request in call.seen] == [
        discovery.PROFILE, concept.DISCOVERY_CONCEPT_PROFILE, concept.precision.PROFILE,
    ]
    assert author in call.seen[0].prompt
    assert author in call.seen[1].prompt
    assert EXPERIENCE in call.seen[1].prompt
    saved = concept.Concept.from_text((out / "concept.json").read_text(encoding="utf-8"))
    assert saved.author_brief == author
    assert saved.discovery == source
    assert EXPERIENCE in (out / "concept.txt").read_text(encoding="utf-8")
    assert json.loads((out / "discovery-trace.json").read_text(encoding="utf-8"))[
        "request"
    ]["profile"] == discovery.PROFILE
    assert cli.main([
        "--database", str(db), "new", "Garden", "--premise", "A gardener explores the sky.",
        "--scenes", "6", "--concept", str(out / "concept.json"),
    ]) == cli.EXIT_OK
    with SqliteStore.open(db) as store:
        book, branch = export.resolve_branch(store, None, None)
        retained = concept.concept_of(store.plan_items(book, branch))
        assert retained == saved
        head = store.head(book, branch)
        packet = packet_for(store, head, beats_for(head, arc_template(6))[0])
        assert author in packet.render()
        assert EXPERIENCE not in packet.render()


@pytest.mark.parametrize("include_empty", [False, True])
def test_incomplete_new_experience_stops_before_concept_development(
    tmp_path, monkeypatch, capsys, include_empty,
):
    payload = _discovery()
    if include_empty:
        payload["experience_brief"] = ""
    provider = FakeProvider(responses=[json.dumps(payload)])

    def complete(request, **kwargs):
        return provider.complete(request), None

    monkeypatch.setattr(cli, "_completion_call", complete)
    out = tmp_path / "out"
    assert cli.main([
        "--database", str(tmp_path / "book.db"), "concept", "--out", str(out),
    ]) == cli.EXIT_FAULT
    assert provider.calls == 1
    assert "discovery is unusable" in capsys.readouterr().err
    assert (out / "discovery-trace.json").exists()
    assert not (out / "concept.json").exists()
