"""Translate fixed JSON shapes for Codex transport, retaining the caller's schema.

Transport constraints are intentionally weaker than the original schema. Callers must
still parse against that original and run their normal downstream validation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# These checks remain the responsibility of the original schema's downstream gate.
_OMITTED = {
    "$schema", "default", "examples", "format", "pattern", "minLength", "maxLength",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minItems", "maxItems", "uniqueItems", "minProperties", "maxProperties",
}
_SUPPORTED = {
    "type", "enum", "const", "title", "description", "properties", "required",
    "additionalProperties", "items", "anyOf",
}
_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def prepare_codex_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a strict fixed-shape transport schema without mutating ``schema``.

    Optional properties become required and nullable. Dynamic maps, references and
    unsupported structural keywords fail before a model call instead of losing shape.
    """
    if schema.get("type") != "object" or "anyOf" in schema:
        raise ValueError("Codex schema root must be a fixed object")
    return _prepare(schema, "$")


def _prepare(schema: dict[str, Any], path: str) -> dict[str, Any]:
    unknown = set(schema) - _SUPPORTED - _OMITTED
    if unknown:
        raise ValueError(f"unsupported Codex schema keywords at {path}: {sorted(unknown)}")
    result = {
        key: deepcopy(value) for key, value in schema.items()
        if key in {"type", "enum", "title", "description"}
    }
    if "const" in schema:
        if "enum" in schema:
            raise ValueError(f"combined enum and const unsupported at {path}")
        result["enum"] = [deepcopy(schema["const"])]
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    if kind is not None and (not kinds or any(item not in _TYPES for item in kinds)):
        raise ValueError(f"unsupported Codex schema type at {path}: {kind!r}")
    if "anyOf" in schema:
        if kind is not None or "properties" in schema or "items" in schema:
            raise ValueError(f"combined anyOf and structural schema unsupported at {path}")
        branches = schema["anyOf"]
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"anyOf must contain schemas at {path}")
        result["anyOf"] = [_prepare(branch, f"{path}.anyOf[{i}]")
                           for i, branch in enumerate(branches)]
        return result
    if kind is None:
        raise ValueError(f"Codex schema needs a type or anyOf at {path}")
    if "object" in kinds:
        properties = schema.get("properties")
        if (
            not isinstance(properties, dict)
            or schema.get("additionalProperties", False) is not False
        ):
            raise ValueError(f"Codex schema requires fixed properties; dynamic map at {path}")
        required = schema.get("required", [])
        if not isinstance(required, list) or not set(required) <= set(properties):
            raise ValueError(f"invalid required properties at {path}")
        converted = {}
        for name, child in properties.items():
            converted_child = _prepare(child, f"{path}.{name}")
            if name not in required and not _accepts_null(child):
                converted_child = {"anyOf": [converted_child, {"type": "null"}]}
            converted[name] = converted_child
        result.update(properties=converted, required=list(properties), additionalProperties=False)
    elif "properties" in schema or "required" in schema or "additionalProperties" in schema:
        raise ValueError(f"object properties on a non-object at {path}")
    if "array" in kinds:
        if not isinstance(schema.get("items"), dict):
            raise ValueError(f"Codex arrays need a single items schema at {path}")
        result["items"] = _prepare(schema["items"], f"{path}[]")
    elif "items" in schema:
        raise ValueError(f"array items on a non-array at {path}")
    return result


def _accepts_null(schema: dict[str, Any]) -> bool:
    if "enum" in schema and None not in schema["enum"]:
        return False
    if "const" in schema and schema["const"] is not None:
        return False
    if "anyOf" in schema:
        return any(_accepts_null(branch) for branch in schema["anyOf"])
    kind = schema.get("type")
    return kind is None or kind == "null" or (isinstance(kind, list) and "null" in kind)


def restore_optional_omissions(payload: object, schema: dict[str, Any]) -> object:
    """Remove only nullable placeholders introduced for optional properties.

    Required or originally nullable values are untouched. This is not a validator:
    invalid values remain available to the caller's existing validation boundary.
    """
    if "anyOf" in schema:
        branches = [branch for branch in schema["anyOf"] if _matches_kind(payload, branch)]
        if not branches:
            return deepcopy(payload)
        candidates = [restore_optional_omissions(payload, branch) for branch in branches]
        if any(candidate != candidates[0] for candidate in candidates[1:]):
            raise ValueError("ambiguous anyOf branches disagree on optional omissions")
        return candidates[0]
    if isinstance(payload, dict) and "properties" in schema:
        properties = schema["properties"]
        required = schema.get("required", [])
        result = {}
        for key, value in payload.items():
            child = properties.get(key)
            if child is None:
                result[key] = deepcopy(value)
            elif not (value is None and key not in required and not _accepts_null(child)):
                result[key] = restore_optional_omissions(value, child)
        return result
    if isinstance(payload, list) and isinstance(schema.get("items"), dict):
        return [restore_optional_omissions(item, schema["items"]) for item in payload]
    return deepcopy(payload)


def _matches_kind(value: object, schema: dict[str, Any]) -> bool:
    """Disambiguate union shapes, without claiming full JSON Schema validation."""
    if "enum" in schema and value not in schema["enum"]:
        return False
    if "const" in schema and value != schema["const"]:
        return False
    if "anyOf" in schema:
        return any(_matches_kind(value, branch) for branch in schema["anyOf"])
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    matches = {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }
    return kind is None or any(matches.get(item, False) for item in kinds if isinstance(item, str))
