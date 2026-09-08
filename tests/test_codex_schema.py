"""Offline checks for the Codex transport shape, separate from domain validation."""

from copy import deepcopy

import pytest

from litharness.application.concept import CONCEPT_SCHEMA
from litharness.application.outline import CONCEPT_OUTLINE_SCHEMA, OUTLINE_SCHEMA
from litharness.domain.scene_brief import SCHEMA as SCENE_BRIEF_SCHEMA
from litharness.providers.codex_schema import (
    prepare_codex_schema,
    restore_optional_omissions,
)


def test_optional_nested_fields_round_trip_without_mutating_input() -> None:
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["items", "required_null"],
        "properties": {
            "items": {"type": "array", "items": {
                "type": "object", "properties": {
                    "name": {"type": "string"}, "note": {"type": "string"},
                }, "required": ["name"], "additionalProperties": False,
            }},
            "required_null": {"type": "string"},
            "optional": {"type": "integer"},
            "nullable": {"anyOf": [{"type": "null"}, {"type": "string"}]},
        },
    }
    before = deepcopy(schema)
    transport = prepare_codex_schema(schema)
    assert schema == before
    assert transport["required"] == list(schema["properties"])
    assert transport["properties"]["optional"] == {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
    }
    nested = transport["properties"]["items"]["items"]
    assert nested["required"] == ["name", "note"]
    assert nested["additionalProperties"] is False
    payload = {
        "items": [{"name": "Mira", "note": None}, {"name": "Orr", "note": "keep"}],
        "required_null": None, "optional": None, "nullable": None, "unexpected": None,
    }
    frozen = deepcopy(payload)
    assert restore_optional_omissions(payload, schema) == {
        "items": [{"name": "Mira"}, {"name": "Orr", "note": "keep"}],
        "required_null": None, "nullable": None, "unexpected": None,
    }
    assert payload == frozen


def test_nullable_object_union_restores_nested_omissions() -> None:
    branch = {"type": "object", "additionalProperties": False,
              "properties": {"note": {"type": "string"}}}
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"second": {"anyOf": [{"type": "null"}, branch]}}}
    transport = prepare_codex_schema(schema)
    assert transport["properties"]["second"]["anyOf"][1]["required"] == ["note"]
    assert restore_optional_omissions({"second": {"note": None}}, schema) == {"second": {}}
    assert restore_optional_omissions({"second": None}, schema) == {"second": None}


def test_nullable_type_union_preserves_null_but_enum_can_disallow_it() -> None:
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "nullable": {"type": ["string", "null"]},
        "enum": {"type": ["string", "null"], "enum": ["yes"]},
    }}
    transport = prepare_codex_schema(schema)
    assert "anyOf" not in transport["properties"]["nullable"]
    assert "anyOf" in transport["properties"]["enum"]
    assert restore_optional_omissions({"nullable": None, "enum": None}, schema) == {
        "nullable": None,
    }


def test_real_concept_and_scene_brief_shapes_translate() -> None:
    for schema in (CONCEPT_SCHEMA, SCENE_BRIEF_SCHEMA):
        before = deepcopy(schema)
        transport = prepare_codex_schema(schema)
        assert transport["required"] == list(schema["properties"])
        assert schema == before
    transport = prepare_codex_schema(SCENE_BRIEF_SCHEMA)
    assert "minLength" not in transport["properties"]["situation"]
    assert "minItems" not in transport["properties"]["changes"]
    assert SCENE_BRIEF_SCHEMA["properties"]["changes"]["minItems"] == 1
    # The downstream constructor still owns this constraint; the transport does not repair it.
    invalid = {"situation": "", "pursuit": "", "changes": [], "future_dependencies": []}
    assert restore_optional_omissions(invalid, SCENE_BRIEF_SCHEMA) == invalid


@pytest.mark.parametrize("schema, message", [
    ({"type": "array", "items": {"type": "string"}}, "root must"),
    ({"type": "object"}, "dynamic map"),
    ({"type": "object", "properties": {}, "additionalProperties": True}, "dynamic map"),
    ({"type": "object", "properties": {}, "patternProperties": {}}, "keywords"),
    ({"type": "object", "properties": {"item": {"$ref": "#/$defs/item"}}}, "keywords"),
    ({"type": "object", "properties": {"item": {"type": "array"}}}, "items schema"),
    ({"type": "object", "properties": {}, "required": ["unknown"]}, "invalid required"),
    (OUTLINE_SCHEMA, "milestones\\[\\].state"),
    (CONCEPT_OUTLINE_SCHEMA, "milestones\\[\\].state"),
])
def test_unsupported_shapes_fail_before_transport(schema: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        prepare_codex_schema(schema)


def test_ambiguous_union_refuses_to_erase_a_potentially_meaningful_null() -> None:
    branches = [
        {"type": "object", "properties": {"x": {"type": "string"}}},
        {"type": "object", "properties": {"x": {"type": ["string", "null"]}}},
    ]
    with pytest.raises(ValueError, match="ambiguous anyOf"):
        restore_optional_omissions({"x": None}, {"anyOf": branches})
    assert restore_optional_omissions({"x": "kept"}, {"anyOf": branches}) == {"x": "kept"}
    assert restore_optional_omissions(123, {"anyOf": branches}) == 123
