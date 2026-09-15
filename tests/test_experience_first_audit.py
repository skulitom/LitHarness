"""Both schema transport routes must remain auditable without weakening original validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from litharness.application.outline import CONCEPT_OUTLINE_SCHEMA
from litharness.providers.codex_schema import prepare_codex_schema

AUDITOR = (Path(__file__).resolve().parents[1]
           / "research/quality-measurement/experience-first-recovery-20260915/audit.py")


def load_auditor():
    spec = importlib.util.spec_from_file_location("experience_transport_audit_test", AUDITOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fallback():
    try:
        prepare_codex_schema(CONCEPT_OUTLINE_SCHEMA)
    except ValueError as error:
        reason = str(error)
    else:
        raise AssertionError("Fixture must exercise a dynamic-map fallback")
    return {"schema": CONCEPT_OUTLINE_SCHEMA, "native_schema": None,
            "native_schema_omission_reason": reason, "schema_variant": "prompt-only-original.v1",
            "argv": ["exec", "--json"]}


def test_documented_dynamic_map_fallback_passes_exact_controls():
    assert all(load_auditor().schema_controls(fallback(), CONCEPT_OUTLINE_SCHEMA).values())


def test_missing_fallback_reason_or_native_argument_fails():
    auditor = load_auditor()
    raw = fallback()
    raw["native_schema_omission_reason"] = None
    assert not auditor.schema_controls(raw, CONCEPT_OUTLINE_SCHEMA)["native_schema_reason"]
    raw = fallback()
    raw["argv"] += ["--output-schema", "different.json"]
    assert not auditor.schema_controls(raw, CONCEPT_OUTLINE_SCHEMA)["native_schema_argument"]


def test_fixed_schema_must_have_native_enforcement():
    auditor = load_auditor()
    shape = {"type": "object", "properties": {"story": {"type": "string"}},
             "required": ["story"], "additionalProperties": False}
    raw = {"schema": shape, "native_schema": prepare_codex_schema(shape),
           "native_schema_omission_reason": None, "schema_variant": "strict-nullable-optionals.v1",
           "argv": ["--output-schema", "schema.json"]}
    assert all(auditor.schema_controls(raw, shape).values())
    raw["native_schema"] = None
    assert not auditor.schema_controls(raw, shape)["native_schema"]


def test_changed_original_schema_is_still_a_failure():
    raw = fallback()
    raw["schema"] = {"type": "object"}
    assert not load_auditor().schema_controls(raw, CONCEPT_OUTLINE_SCHEMA)["original_schema"]
