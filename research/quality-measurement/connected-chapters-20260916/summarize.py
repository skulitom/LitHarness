"""Rebuild numeric integrity and resource controls after the fixed generation run."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/connected-chapters-20260916"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize():
    state = read(LOCAL / "progress.json")
    if state["status"] == "running":
        raise RuntimeError("Generation must finish or stop before readout")
    evidence = read(HERE / "evidence.json")
    handoff = read(HERE / "handoff-evidence.json")
    manifest = read(LOCAL / "manifest.json")
    frozen_ok = all(sha(Path(p)) == expected for p, expected in manifest["files"].items())
    handoff_ok = all(sha(ROOT / p) == expected for p, expected in handoff["source_hashes"].items())
    phases = defaultdict(lambda: {"calls": 0, "known_tokens": 0})
    for call in state["calls"]:
        phases[call["phase"]]["calls"] += 1
        phases[call["phase"]]["known_tokens"] += call["tokens"]
    scenes = [s for book in handoff["books"] for s in book["scenes"]]
    source_boundary = []
    for book in sorted(state["books"]):
        preflight = read(LOCAL / "preflight" / f"{book}.json")["request"]
        calls = [
            c for c in state["calls"] if c["book"] == book and c["profile"] == preflight["profile"]
        ]
        source_boundary.append(
            {
                "book": book,
                "invention_attempts": len(calls),
                "first_invention_request_matches_preflight": bool(calls)
                and read(LOCAL / calls[0]["path"])["request"] == preflight,
            }
        )
    result = {
        "status": state["status"],
        "stop": state.get("stop"),
        "source_hashes": {
            str(p.relative_to(ROOT)).replace("\\", "/"): sha(p)
            for p in (
                Path(__file__),
                HERE / "evidence.json",
                HERE / "handoff-evidence.json",
                LOCAL / "manifest.json",
                LOCAL / "progress.json",
            )
        },
        "integrity": {
            "frozen_files": len(manifest["files"]),
            "frozen_files_match": frozen_ok,
            "handoff_source_files": len(handoff["source_hashes"]),
            "handoff_source_files_match": handoff_ok,
            "transport_controls": evidence["all_transport_controls_pass"],
            "step_controls": evidence["all_step_controls_pass"],
            "job_bound_plans": all(s["job_bound_plan_available"] for s in scenes),
            "full_briefs_in_writer_requests": all(
                s["full_scene_brief_in_writer_prompt"] for s in scenes
            ),
            "briefs_match_recorded_outlines": all(
                bool(s["matching_outline_calls"]) for s in scenes
            ),
            "accepted_equal_raw_or_surface_cleanup": all(
                bool(
                    s["writer_calls_equal_to_accepted_text"]
                    or s["writer_calls_equal_after_existing_surface_cleanup"]
                )
                for s in scenes
            ),
        },
        "calls": len(state["calls"]),
        "known_tokens": sum(c["tokens"] for c in state["calls"]),
        "unknown_usage_calls": sum(c["usage_unknown"] for c in evidence["calls"]),
        "elapsed_seconds": (
            datetime.fromisoformat(state["finished_at"])
            - datetime.fromisoformat(state["started_at"])
        ).total_seconds(),
        "phases": dict(phases),
        "chapters": len(evidence["chapters"]),
        "words": sum(c["words"] for c in evidence["chapters"]),
        "scenes_with_writer_receipts": sum(bool(s["matching_writer_calls"]) for s in scenes),
        "scenes_equal_to_raw": sum(bool(s["writer_calls_equal_to_accepted_text"]) for s in scenes),
        "scenes_equal_after_cleanup": sum(
            bool(s["writer_calls_equal_after_existing_surface_cleanup"]) for s in scenes
        ),
        "source_boundary": source_boundary,
    }
    if state.get("continuation"):
        amendment = read(HERE / "continuation.json")
        stopped = read(LOCAL / "budget-stop/progress.json")
        prefix = amendment["parent_calls"]
        result["continuation"] = {
            "original_status": stopped["status"],
            "original_stop": stopped["stop"],
            "original_calls": prefix,
            "original_tokens": sum(c["tokens"] for c in stopped["calls"]),
            "additional_calls": len(state["calls"]) - prefix,
            "additional_tokens": sum(c["tokens"] for c in state["calls"][prefix:]),
            "original_call_metadata_preserved": state["calls"][:prefix] == stopped["calls"],
            "frozen_continuation_inputs_match": all(
                sha(Path(p)) == expected for p, expected in amendment["files"].items()
            ),
            "preparation_gap_seconds": (
                datetime.fromisoformat(state["continuation"]["started_at"])
                - datetime.fromisoformat(stopped["finished_at"])
            ).total_seconds(),
        }
        for p in (
            HERE / "CONTINUATION.md",
            HERE / "continuation.json",
            LOCAL / "budget-stop/progress.json",
        ):
            result["source_hashes"][p.relative_to(ROOT).as_posix()] = sha(p)
    (HERE / "readout-controls.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    summarize()
