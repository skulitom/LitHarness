"""The exploratory byte calculation must preserve values and field absence."""

import copy
import json
import runpy
from pathlib import Path

import pytest

PROBE = runpy.run_path(str(Path(__file__).resolve().parents[1]
    / "research/quality-measurement/growth-declarations-20260913/payload_probe.py"))


def test_minification_preserves_nested_values_and_non_json_output():
    value = {"text": " A\nquoted \"line\" Ω ", "rows": [None, True, 0, -2, {"a": []}]}
    raw = json.dumps(value, indent=2)
    compact = PROBE["compact"](raw)
    assert json.loads(compact) == value and len(compact) < len(raw)
    plain = "declared 3 records\n  diagnostic detail\n"
    assert PROBE["compact"](plain) == plain


def test_shared_columns_preserve_null_empty_nested_and_pagination_values():
    page = {"records": [{"id": "a", "value": None}, {"value": {"nested": []}, "id": "b"}],
            "next_offset": 2, "selection_sha256": "selection"}
    before = copy.deepcopy(page)
    packed = PROBE["columnar"](page)
    assert page == before and packed["next_offset"] == 2
    assert packed["records"] == {"columns": ["id", "value"],
                                  "rows": [["a", None], ["b", {"nested": []}]]}
    empty = {"records": [], "next_offset": None}
    assert PROBE["columnar"](empty) == empty


def test_missing_fields_are_not_silently_converted_to_null():
    with pytest.raises(ValueError, match="absent fields"):
        PROBE["columnar"]({"records": [{"id": "a", "value": None}, {"id": "b"}]})
