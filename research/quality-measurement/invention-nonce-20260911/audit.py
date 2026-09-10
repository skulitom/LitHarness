"""Audit opaque prefix placement, fresh sessions and identical-prefix repeats."""

from __future__ import annotations

import base64
import re
import sys
from collections import Counter
from pathlib import Path

from run import HERE, LOCAL, ROOT, read, sha, write

sys.path.insert(0, str(ROOT))
from tools.generation_trace import compare, load_trace, search


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "registration.json")
    rows, traces, controls = [], {}, {}
    reading = ["# All Base64 preprompt first responses\n"]
    baseline = read(LOCAL / "requests/control-1.json")
    for name in manifest["order"]:
        saved = read(LOCAL / "requests" / f"{name}.json")
        seed = read(LOCAL / "seeds" / f"{name}.json")
        prefix = seed["brief"] if seed else ""
        controls[name] = {
            "only_request_change_is_prefix": saved == {
                **baseline, "system": prefix + "\n\n" + baseline["system"]
                if seed else baseline["system"],
            },
            "prefix_characters": len(prefix),
            "integer_roundtrip": int.from_bytes(base64.b64decode(prefix), "big")
            == int(seed["seed"]) if seed else None,
        }
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({
            "slot": name, **summary, "validation": row.get("validation"),
            "request_matches_saved": row["request"] == saved,
            "usage": (row.get("result") or {}).get("usage"),
        })
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    comparisons = {}
    pairs = [("control-1", n) for n in manifest["order"] if n != "control-1"]
    pairs.extend((n, f"repeat-{n}") for n in ("short-1", "long-1"))
    for left, right in pairs:
        if left in traces and right in traces:
            compared = compare(traces[left], traces[right])
            comparisons[f"{left}:{right}"] = {
                k: compared[k] for k in ("fields", "configuration_equal", "same_native_session")
            }
    for name, trace in traces.items():
        if "control-1" in traces and "transport.system" in trace.fields:
            seed = read(LOCAL / "seeds" / f"{name}.json")
            controls[name]["captured_system_is_prefix_plus_control"] = (
                trace.fields["transport.system"]
                == (seed["brief"] + "\n\n" if seed else "")
                + traces["control-1"].fields["transport.system"]
            )
    query = r"\b(?:Mara Venn|Mara|Venn|water|flood\w*|repair\w*|bridge\w*|refuge\w*|registr\w*)\b"
    hits = []
    for name, trace in traces.items():
        for hit in search(trace, re.compile(query, re.IGNORECASE)):
            if hit["field"] == "output.text":
                hit["path"] = trace.path.relative_to(ROOT).as_posix()
                hits.append({"slot": name, **hit})
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    evidence = {
        "purpose": "Opaque input prefix and replay; no quality score or candidate selection",
        "manifest_sha256": sha(LOCAL / "manifest.json"),
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress, "calls": rows, "comparisons": comparisons,
        "prefix_controls": controls,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
        "literal_search": {
            "query": query, "hits": hits, "interpretation": "Passage locations only",
        },
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({
        "attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
        "frozen_file_drift": evidence["frozen_file_drift"],
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "validation": {r["slot"]: r.get("validation") for r in rows},
    })


if __name__ == "__main__":
    main()
