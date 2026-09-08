"""Located source edits: bounded application and quota flow, never prose quality scores."""

import json

import pytest

from litharness import cli
from litharness.application import concept, discovery, precision
from tests.test_concept import _example, _scripted


def material():
    return discovery.Discovery(
        "Trees float over a valley forty miles wide.",
        "She waited nineteen minutes. Then she lifted a seed.\n[STATUS] Mana 7/10",
        "She can grow a bridge.",
    )


def edits():
    return {
        "edits": [
            {"field": "world", "before": "forty miles wide", "after": "broad as the horizon"},
            {"field": "opening", "before": "nineteen minutes", "after": "a while"},
        ]
    }


def test_located_edits_preserve_everything_else_and_system_values():
    source = material()
    prepared = source.with_precision_edits(edits())
    assert prepared.world == "Trees float over a valley broad as the horizon."
    assert prepared.opening == "She waited a while. Then she lifted a seed.\n[STATUS] Mana 7/10"
    assert prepared.growth == source.growth
    assert prepared.version == source.version
    assert "nineteen minutes" in source.opening
    assert source.with_precision_edits({"edits": []}) == source


@pytest.mark.parametrize(
    "edit",
    [
        {"field": "unknown", "before": "forty miles", "after": "broad"},
        {"field": "world", "before": "not in source", "after": "broad"},
        {"field": "world", "before": "forty miles", "after": "fifty miles"},
        {"field": "world", "before": "Trees", "after": "Clouds"},
        {"field": "world", "before": "forty miles", "after": "new\nparagraph"},
        {"field": "world", "before": "forty miles", "after": "new\rparagraph"},
        {"field": "world", "before": "forty miles", "after": "the Standing"},
        {"field": "opening", "before": "7/10", "after": "full"},
        {"field": "opening", "before": "7", "after": "full"},
    ],
)
def test_unlocated_broad_or_system_edits_are_rejected(edit):
    with pytest.raises(ValueError):
        material().with_precision_edits({"edits": [edit]})


def test_ambiguous_overlapping_and_partial_token_edits_are_rejected():
    source = discovery.Discovery("Ten birds. Ten birds.", "A stone.", "She has 123 coins.")
    for edit in (
        {"field": "world", "before": "Ten birds", "after": "Birds"},
        {"field": "opening", "before": "one", "after": "x"},
        {"field": "growth", "before": "2", "after": ""},
    ):
        with pytest.raises(ValueError):
            source.with_precision_edits({"edits": [edit]})
    with pytest.raises(ValueError, match="overlap"):
        material().with_precision_edits({"edits": [edits()["edits"][0]] * 2})
    repeated = discovery.Discovery("one bird one bird one", "An encounter.", "A pursuit.")
    with pytest.raises(ValueError, match="uniquely"):
        repeated.with_precision_edits(
            {"edits": [{"field": "world", "before": "one bird one", "after": "birds"}]}
        )


def test_signed_compound_quantities_and_inline_displays_are_not_partially_edited():
    source = discovery.Discovery("Twenty-one birds.", "A toll of -123 coins.", "It read [Mana 7].")
    for field, before in (("world", "one"), ("opening", "123"), ("growth", "7")):
        with pytest.raises(ValueError):
            source.with_precision_edits(
                {"edits": [{"field": field, "before": before, "after": "some"}]}
            )
    mixed = discovery.Discovery("At 2 she counted 123 birds.", "An encounter.", "A pursuit.")
    with pytest.raises(ValueError, match="complete quantity"):
        mixed.with_precision_edits(
            {
                "edits": [
                    {"field": "world", "before": "2 she counted 12", "after": "dawn she counted"}
                ]
            }
        )


def test_quantity_scheduling_is_presence_only():
    assert material().has_quantities()
    assert discovery.Discovery("stone", "alone", "done").has_quantities() is False
    assert discovery.Discovery("One path.", "", "").has_quantities()


@pytest.mark.parametrize("phrase", ["a mile", "an hour", "a month", "a decade"])
def test_article_unit_quantities_are_editable_without_counting_relative_spans(phrase):
    source = discovery.Discovery(f"She travelled for {phrase}.", "An encounter.", "A pursuit.")
    prepared = source.with_precision_edits(
        {"edits": [{"field": "world", "before": phrase, "after": "a while"}]}
    )
    assert prepared.world == "She travelled for a while."
    assert not prepared.has_quantities()


def test_a_replacement_may_keep_a_quantity_the_phrase_already_carried():
    """The refused Marrowgate draw: context quoted around the removed hour is not invention."""
    source = discovery.Discovery(
        "A valley.", "At two in the morning the twelfth gauge moves.", "A pursuit."
    )
    before = "At two in the morning the twelfth"
    after = "In the small hours the twelfth"
    prepared = source.with_precision_edits(
        {"edits": [{"field": "opening", "before": before, "after": after}]}
    )
    assert prepared.opening == "In the small hours the twelfth gauge moves."
    for after in (
        "In the small hours the twelfth of twelve",
        "At three in the morning the twelfth",
        "Around two in the morning the twelfth",
    ):
        with pytest.raises(ValueError, match="invent"):
            source.with_precision_edits(
                {"edits": [{"field": "opening", "before": before, "after": after}]}
            )


@pytest.mark.parametrize("ordinal", ["third", "twenty-third", "one hundred and third", "23rd"])
def test_ordinal_quantities_can_be_replaced_only_as_complete_spans(ordinal):
    source = discovery.Discovery("A valley.", f"She learned on the {ordinal} day.", "A pursuit.")
    assert source.has_quantities()
    prepared = source.with_precision_edits(
        {
            "edits": [
                {"field": "opening", "before": f"on the {ordinal} day", "after": "after a few days"}
            ]
        }
    )
    assert prepared.opening == "She learned after a few days."
    assert not prepared.has_quantities()
    for before, after in ((ordinal[-3:], "later"), (ordinal, "fourth")):
        with pytest.raises(ValueError):
            source.with_precision_edits(
                {"edits": [{"field": "opening", "before": before, "after": after}]}
            )


def test_cli_prepares_all_invented_material_after_development(tmp_path, monkeypatch):
    source = material()
    proposal = {
        "edits": [{**edit, "field": "discovery." + edit["field"]} for edit in edits()["edits"]]
    }
    proposal["edits"].append({"field": "person_before", "before": "second-year", "after": "former"})
    call = _scripted(source.to_jsonable(), _example(), proposal)
    monkeypatch.setattr(cli, "_completion_call", call)
    db, out = tmp_path / "book.db", tmp_path / "out"
    assert cli.main(["--database", str(db), "init"]) == cli.EXIT_OK
    assert cli.main(["--database", str(db), "concept", "--out", str(out)]) == cli.EXIT_OK
    assert [r.profile for r in call.seen] == [
        discovery.PROFILE,
        concept.DISCOVERY_CONCEPT_PROFILE,
        precision.PROFILE,
    ]
    retained = concept.Concept.from_text((out / "concept.json").read_text(encoding="utf-8"))
    assert retained.discovery == source.with_precision_edits(edits())
    assert retained.first_arc.opens == retained.discovery.opening
    assert retained.person_before == "a former physics dropout stacking shelves on nights"
    assert retained.system.steps == 12
    assert retained.debts[0].due_scene == 5
    original = json.loads((out / "discovery-trace.json").read_text(encoding="utf-8"))
    assert json.loads(original["response"]) == source.to_jsonable()
    audit = json.loads((out / "concept-precision-trace.json").read_text(encoding="utf-8"))
    assert json.loads(audit["response"]) == proposal


def test_concept_precision_protects_structure_and_edits_the_opening_at_one_address():
    developed = concept.Concept.from_development(_example(), material())
    fields, protected = developed.precision_material()
    assert "first_arc.opens" not in fields
    assert protected["first_arc.opens"] == developed.discovery.opening
    assert protected["system.steps"] == 12
    assert protected["debts.0.due_scene"] == 5
    assert protected["system.name"] == "the Tally"
    assert developed.with_precision_edits({"edits": []}) == developed
    for field in ("system.steps", "debts.0.due_scene", "first_arc.opens", "discovery.version"):
        with pytest.raises(ValueError, match="unknown field"):
            developed.with_precision_edits(
                {"edits": [{"field": field, "before": "12", "after": "many"}]}
            )
    changed = developed.with_precision_edits(
        {"edits": [{"field": "debts.1.subject", "before": "eleven years", "after": "lost years"}]}
    )
    assert changed.debts[1].subject == "the lost years"
    assert changed.debts[1].due_scene == developed.debts[1].due_scene
    request = precision.render_request(fields, protected)
    allowed = request.schema["properties"]["edits"]["items"]["properties"]["field"]["enum"]
    assert set(allowed) == set(fields)
    assert json.loads(request.prompt)["protected"] == protected


@pytest.mark.parametrize("refuse", [False, True])
def test_invalid_edits_or_quota_refusal_stop_before_persistence(tmp_path, monkeypatch, refuse):
    source = material()
    call = _scripted(source.to_jsonable(), _example(), {"edits": [{"field": "missing"}]})

    def answer(request, **kwargs):
        if refuse and request.profile == precision.PROFILE:
            return None, "quota exhausted"
        return call(request, **kwargs)

    monkeypatch.setattr(cli, "_completion_call", answer)
    db, out = tmp_path / "book.db", tmp_path / "out"
    assert cli.main(["--database", str(db), "init"]) == cli.EXIT_OK
    assert cli.main(["--database", str(db), "concept", "--out", str(out)]) == cli.EXIT_FAULT
    assert not (out / "concept.json").exists()
    assert sum(r.profile == concept.DISCOVERY_CONCEPT_PROFILE for r in call.seen) == 1
