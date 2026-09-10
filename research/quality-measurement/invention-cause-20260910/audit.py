"""Derive prose-free integrity and comparison records from the completed diagnostic phases."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from run import HERE, LOCAL, ROOT, read, sha, write

sys.path.insert(0, str(ROOT))

from tools.generation_trace import compare, load_trace


def phase(directory: Path, registration: Path) -> dict:
    manifest = read(directory / "manifest.json")
    progress = read(directory / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    rows = []
    for name in manifest["order"]:
        path = directory / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        trace = load_trace(path)
        result = row.get("result") or {}
        expected = directory / "request.json"
        if not expected.exists():
            expected = directory / "requests" / f"{name}.json"
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({
            "slot": name, **summary, "validation": row.get("validation"),
            "started_at": row.get("started_at"), "finished_at": row.get("finished_at"),
            "request_matches_prepared": row["request"] == read(expected),
            "usage": result.get("usage"),
        })
    return {
        "registration": registration.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha(directory / "manifest.json"),
        "manifest_matches_registration": (
            sha(directory / "manifest.json") == read(registration)["manifest_sha256"]
        ),
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress, "calls": rows,
    }


def main() -> None:
    phases = [phase(LOCAL, HERE / "registration.json"),
              phase(LOCAL / "phase2", HERE / "phase2-registration.json")]
    calls = [r for p in phases for r in p["calls"] if r["status"] != "not_attempted"]
    sessions = Counter(s for row in calls for s in row["sessions"])
    outputs = Counter(row["field_sha256"].get("output.text") for row in calls)
    comparisons = {}
    for label, left, right in (
        ("full_minimal", "calls/full-1.json", "calls/minimal-1.json"),
        ("astra_gpt55", "phase2/calls/astra-1.json", "phase2/calls/gpt55-1.json"),
        ("astra_opus", "phase2/calls/astra-1.json", "phase2/calls/opus-1.json"),
    ):
        result = compare(load_trace(LOCAL / left), load_trace(LOCAL / right))
        comparisons[label] = {
            "left": left, "right": right, "fields": result["fields"],
            "configuration_equal": result["configuration_equal"],
            "same_native_session": result["same_native_session"],
        }
    write(HERE / "evidence.json", {
        "purpose": "Generation debugging; no quality scores or candidate selection",
        "phases": phases, "comparisons": comparisons,
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if s is not None and n > 1},
        "limits": [
            "Native transport capture contains submitted inputs, not every backend instruction.",
            "Different requested models can also select different native model metadata/routes.",
            "Fresh sessions and different bytes do not establish premise diversity.",
            "The retained treatments require reading; keywords do not classify water worlds.",
        ],
    })
    print(json.dumps({
        "calls": len(calls), "tokens": sum(p["progress"]["tokens"] for p in phases),
        "frozen_file_drift": [f for p in phases for f in p["frozen_file_drift"]],
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
    }))


if __name__ == "__main__":
    main()
