"""The format comparison changes transport only and audits the actual native view."""

import json
import runpy
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / "research/quality-measurement/compact-json-20260913"
RUN = runpy.run_path(str(HERE / "run.py"))
AUDIT = runpy.run_path(str(HERE / "audit.py"))


def test_comparison_guards_use_this_experiment_and_counterbalanced_assignments():
    base = RUN["BASE"]
    assert base.RUN.name == "compact-json-20260913" and base.HERE == HERE
    assert base.REVISION == "991ff2c" and base.OWNER == "compact-json-20260913:"
    assert tuple(base.ORDER) == RUN["ORDER"]
    assert [RUN["compact_for_case"](name) for name in base.ORDER] == [False, True, True, False]
    with pytest.raises(ValueError, match="Unregistered"):
        RUN["compact_for_case"]("unassigned")
    with pytest.raises(RuntimeError, match="ceiling"):
        base.check_budget(0, 1_200_000, 0)
    with pytest.raises(RuntimeError, match="ceiling"):
        base.check_budget(0, 0, 3600)


def test_reply_audit_catches_lost_values_wrong_format_or_missing_native_result():
    row = {"phase": "result", "call": 1, "arguments": ["world", "query"], "argv": ["cli"],
           "returncode": 0, "stdout": '{ "x": 1 }\n', "stderr": "",
           "model_stdout": '{"x":1}'}
    visible = {"call": 1, "returncode": 0, "stdout": '{"x":1}', "stderr": ""}
    assert AUDIT["reply_matches"](row, visible, True)
    assert not AUDIT["reply_matches"](row, visible, False)
    assert not AUDIT["reply_matches"](row, {**visible, "stdout": "{}"}, True)
    assert not AUDIT["reply_matches"](row, None, True)
    assert not AUDIT["reply_matches"](row, {**visible, "model_stdout": '{"x":1}'}, True)


def test_failures_require_the_complete_unmodified_receipt():
    row = {"phase": "result", "call": 1, "arguments": ["world", "query"], "argv": ["cli"],
           "returncode": 1, "stdout": '{ "x": 1 }\n', "stderr": "problem"}
    visible = {k: v for k, v in row.items() if k != "phase"}
    assert AUDIT["reply_matches"](row, visible, True)
    assert not AUDIT["reply_matches"](row, {**visible, "stdout": '{"x":1}'}, True)


def test_native_view_extraction_does_not_reuse_a_command_identity():
    event = {"type": "item.completed", "item": {"type": "mcp_tool_call", "result": {
        "content": [{"type": "text", "text": json.dumps({"call": 1, "stdout": "ok"})}]}}}
    assert AUDIT["visible_replies"]([event]) == {1: {"call": 1, "stdout": "ok"}}
    with pytest.raises(ValueError, match="Duplicate"):
        AUDIT["visible_replies"]([event, event])


def test_unknown_usage_is_retained_without_a_false_zero_cost_comparison():
    assert AUDIT["token_difference"](10, 12) == -2
    assert AUDIT["token_difference"](None, 12) is None
    assert AUDIT["token_difference"](10, None) is None
