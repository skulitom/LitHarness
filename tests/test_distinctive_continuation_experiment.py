"""Accounting controls for the isolated continuation driver; no native calls."""

import importlib.util
import json
from pathlib import Path

import pytest


def runner():
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/distinctive-continuation-20260913/run.py"
    )
    spec = importlib.util.spec_from_file_location("distinctive_continuation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rejected_native_usage_includes_cached_input_once():
    raw = {"stdout": json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 12,
        "reasoning_output_tokens": 5,
    }})}
    assert runner().failed_usage(raw) == 112


@pytest.mark.parametrize("stdout", [
    "", "partial", "{}", "null", "[]",
    '{"type":"turn.completed","usage":{"input_tokens":true,"output_tokens":2}}',
    '{"type":"turn.completed","usage":{"input_tokens":-1,"output_tokens":2}}',
    '{"type":"turn.completed","usage":{"input_tokens":0,"output_tokens":0}}',
    '{"type":"turn.completed"}\n{"type":"turn.completed"}',
])
def test_unaccountable_native_failure_cannot_be_reported_as_zero(stdout):
    assert runner().failed_usage({"stdout": stdout}) is None
