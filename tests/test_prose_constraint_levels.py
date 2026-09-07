"""Verify nested input exposure, whole-run quota and test containment."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAL = runpy.run_path(str(ROOT / "research/quality-measurement/prose_constraint_levels.py"))
FIXTURE = runpy.run_path(str(ROOT / "tests/test_prose_narration_obligations.py"))


def source():
    return {
        "chapter_source": FIXTURE["source"](),
        "common": {"units": [{"id": "C1", "text": "COMMON"}], "display_templates": {"one": "ONE"}},
        "required_ending": [{"id": "E1", "text": "ENDING_SECRET"}],
        "ending_displays": {"end": "ENDING_DISPLAY"},
    }


def test_constraint_levels_are_strictly_additive_without_reference_or_endpoint_leakage():
    s = source()
    before = copy.deepcopy(s)
    requests = TRIAL["compose"](s)
    p, e, d = (json.loads(requests[k]["prompt"]) for k in ("premise", "ending", "sequence"))
    assert e.pop("required_ending") == s["required_ending"]
    assert e.pop("ending_display_templates") == s["ending_displays"]
    assert e == p
    assert d.pop("event_sequence") == s["chapter_source"]["facts"]
    assert d.pop("scene_break_after_unit") == s["chapter_source"]["scene_break_after"]
    assert d == json.loads(requests["ending"]["prompt"])
    assert "ENDING_SECRET" not in requests["premise"]["prompt"]
    assert "ENDING_DISPLAY" not in requests["premise"]["prompt"]
    assert "Two awards." not in requests["ending"]["prompt"]
    assert all("Incidental original wording" not in r["prompt"] for r in requests.values())
    assert len({r["system"] for r in requests.values()}) == 1
    assert s == before


@pytest.mark.parametrize("bad", [[], [{"id": "C1", "text": ""}], [{"id": "C1", "text": "x"}] * 2])
def test_constraint_levels_reject_invalid_common_units(bad):
    s = source()
    s["common"]["units"] = bad
    with pytest.raises(ValueError, match="source units"):
        TRIAL["compose"](s)


def test_constraint_levels_reject_display_collision():
    s = source()
    s["ending_displays"]["one"] = "OTHER"
    with pytest.raises(ValueError, match="collision"):
        TRIAL["compose"](s)


def test_constraint_levels_quota_counts_all_folders_reasoning_and_failures(tmp_path):
    p = tmp_path / "premise-1"
    p.mkdir()
    path = p / "full-1.result.json"
    TRIAL["write_new"](
        path,
        {
            "status": "completed",
            "usage": {
                "input_tokens": 5,
                "cached_input_tokens": 5,
                "output_tokens": 7,
                "reasoning_output_tokens": 11,
            },
        },
    )
    assert TRIAL["quota"](tmp_path) == 23
    value = json.loads(path.read_text())
    value["usage"]["reasoning_output_tokens"] = 110_000
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match="token stop"):
        TRIAL["quota"](tmp_path)
    path.write_text(json.dumps({"status": "failed"}))
    with pytest.raises(RuntimeError, match="failure"):
        TRIAL["quota"](tmp_path)


def test_constraint_levels_live_guard_prevents_request_creation(tmp_path):
    s = source()
    TRIAL["write_new"](
        tmp_path / "manifest.json",
        {
            "files": {},
            "source": s,
            "requests": TRIAL["compose"](s),
            "prefix": ["node", "codex"],
        },
    )
    (tmp_path / "premise-1").mkdir()
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["run"](tmp_path)
    assert not list(tmp_path.glob("*/full-1.request.json"))
