"""Replace one reviewed clause in a frozen final scene-plan wrapper; subscription only."""

from __future__ import annotations

import argparse
import math
import re
import runpy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHARED = runpy.run_path(str(HERE / "prose_request_experiment.py"))
CODEX = SHARED["CODEX"]
read, write_new, sha = (SHARED[key] for key in ("read", "write_new", "sha"))
_text_sha = SHARED["text_sha"]
REG = HERE / "prose-recall-clarification"
ORDER = ("control-1", "clarified-1", "clarified-2", "control-2")
TOKEN_STOP = 100_000
EFFORT = "high"
TRANSPORT_TIMEOUT = 900


def _span(prompt: str, value: Any, *, replacement: bool = False) -> tuple[int, int, str]:
    expected = {"start", "end", "text"} | ({"replacement"} if replacement else set())
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("invalid reviewed span shape")
    start, end, text = (value[key] for key in ("start", "end", "text"))
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(prompt):
        raise ValueError("invalid reviewed span offsets")
    if not isinstance(text, str) or not text.strip() or prompt[start:end] != text:
        raise ValueError("reviewed span does not match exact prompt text")
    return start, end, text


def compose(source: Any) -> dict[str, dict[str, Any]]:
    """Apply one exact reviewed replacement, without inferring its narrative meaning."""
    if not isinstance(source, dict) or set(source) != {
        "control",
        "scene_plan",
        "replacement",
        "original_request_path",
        "original_request_sha256",
    }:
        raise ValueError("invalid source schema")
    control = source["control"]
    if not isinstance(control, dict) or set(control) != {"system", "prompt", "timeout"}:
        raise ValueError("invalid original request shape")
    if any(
        not isinstance(control[key], str) or not control[key].strip()
        for key in ("system", "prompt")
    ):
        raise ValueError("nonempty system and prompt required")
    timeout = control["timeout"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid original timeout")
    if not isinstance(source["original_request_path"], str) or not source["original_request_path"]:
        raise ValueError("original request path required")
    digest = source["original_request_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid original request hash")
    prompt = control["prompt"]
    plan_start, plan_end, plan = _span(prompt, source["scene_plan"])
    if (
        plan_end != len(prompt)
        or not plan.startswith("Now write ")
        or (plan_start and prompt[plan_start - 1] != "\n")
        or prompt.rfind("\nNow write ") not in {-1, plan_start - 1}
    ):
        raise ValueError("scene plan must identify the final task wrapper")
    start, end, original = _span(prompt, source["replacement"], replacement=True)
    if not plan_start < start < end < plan_end:
        raise ValueError("replacement must be strictly inside the final scene-plan wrapper")
    replacement = source["replacement"]["replacement"]
    if (
        not isinstance(replacement, str)
        or not replacement.strip()
        or replacement == original
        or len(original.splitlines()) != 1
        or len(replacement.splitlines()) != 1
        or any(character in original + replacement for character in "\r\n")
    ):
        raise ValueError("reviewed replacement must change one nonblank single-line clause")
    clarified = prompt[:start] + replacement + prompt[end:]
    return {"control": dict(control), "clarified": {**control, "prompt": clarified}}


def transformation_receipt(source: Any) -> dict[str, Any]:
    requests = compose(source)
    before, after = requests["control"]["prompt"], requests["clarified"]["prompt"]
    plan, replacement = source["scene_plan"], source["replacement"]
    start, end = replacement["start"], replacement["end"]
    after_end = start + len(replacement["replacement"])
    return {
        "schema": "litharness.prose-recall-clarification-transform.v1",
        "offset_unit": "unicode_code_points_half_open",
        "control_prompt_sha256": _text_sha(before),
        "clarified_prompt_sha256": _text_sha(after),
        "system_sha256": _text_sha(requests["control"]["system"]),
        "control_prompt_characters": len(before),
        "clarified_prompt_characters": len(after),
        "scene_plan_before": {"start": plan["start"], "end": plan["end"]},
        "scene_plan_after": {"start": plan["start"], "end": len(after)},
        "replacement_before": {"start": start, "end": end},
        "replacement_after": {"start": start, "end": after_end},
        "original_clause_sha256": _text_sha(replacement["text"]),
        "replacement_clause_sha256": _text_sha(replacement["replacement"]),
        "prefix_sha256": _text_sha(before[:start]),
        "suffix_sha256": _text_sha(before[end:]),
        "before_scene_plan_sha256": _text_sha(before[: plan["start"]]),
        "inverse_recovers_original": (
            after[:start] + replacement["text"] + after[after_end:] == before
        ),
    }


EXPERIMENT = SHARED["FrozenSceneExperiment"](
    root=ROOT,
    order=ORDER,
    registered_files=(
        Path(__file__).resolve(),
        ROOT / "tests/test_prose_recall_clarification.py",
        REG / "PREREG.md",
        REG / "RUNBOOK.md",
    ),
    compose=compose,
    receipt=transformation_receipt,
    token_stop=TOKEN_STOP,
)
prepare, validate, quota, call, draft = (
    getattr(EXPERIMENT, name) for name in ("prepare", "validate", "quota", "call", "draft")
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--slot", choices=ORDER)
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.source is None or args.slot is not None:
            parser.error("prepare requires --source and takes no --slot")
        prepare(args.out, args.source)
    else:
        if args.source is not None:
            parser.error("draft uses the frozen source; --source is not accepted")
        draft(args.out, args.slot)


if __name__ == "__main__":
    main()
