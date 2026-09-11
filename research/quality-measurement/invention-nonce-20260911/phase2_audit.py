"""Audit captured native constraints and task-format controls; retain all first responses."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from phase2 import HERE, LOCAL, ROOT, read, sha, write

sys.path.insert(0, str(ROOT))
from tools.generation_trace import compare, load_trace, search


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "format-registration.json")
    rows, traces, reading = [], {}, ["# All invention-format first responses\n"]
    for name in manifest["order"]:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({
            "slot": name, **summary,
            "validation": row.get("validation"),
            "usage": (row.get("result") or {}).get("usage"),
            "request_matches_saved": row["request"] == read(LOCAL / "requests" / f"{name}.json"),
        })
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    comparisons = {}
    for index in (1, 2):
        for left_arm, right_arm in (
            ("native", "prompt-json"), ("prompt-json", "free-premise"),
        ):
            left, right = f"{left_arm}-{index}", f"{right_arm}-{index}"
            if left in traces and right in traces:
                compared = compare(traces[left], traces[right])
                comparisons[f"{left}:{right}"] = {
                    k: compared[k] for k in ("fields", "configuration_equal", "same_native_session")
                }
    query = r"\b(?:Mara Venn|Mara|Venn|water|flood\w*|repair\w*|bridge\w*|refuge\w*|registr\w*)\b"
    hits = []
    for name, trace in traces.items():
        for hit in search(trace, re.compile(query, re.IGNORECASE)):
            hit["path"] = trace.path.relative_to(ROOT).as_posix()
            hits.append({"slot": name, **hit})
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    evidence = {
        "purpose": "Native constraint and task format; no quality score or candidate selection",
        "manifest_sha256": sha(LOCAL / "manifest.json"),
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress, "calls": rows, "comparisons": comparisons,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
        "literal_search": {
            "query": query, "hits": hits, "interpretation": "Passage locations only",
        },
    }
    write(HERE / "format-evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({
        "attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
        "frozen_file_drift": evidence["frozen_file_drift"],
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "validation": {r["slot"]: r.get("validation") for r in rows},
    })


if __name__ == "__main__":
    main()
