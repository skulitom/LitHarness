"""Inspect a finished seeding pilot without opening a store or invoking a model."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from run import HERE, LOCAL, ROOT, read, sha, write

sys.path.insert(0, str(ROOT))

from tools.generation_trace import compare, load_trace, search


def main() -> None:
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "registration.json")
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    rows, traces = [], {}
    treatments = [
        "# All first responses from the creative seeding pilot\n",
        "In registered call order; no response selected or redrawn.\n",
    ]
    for name in manifest["order"]:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            treatments.append(f"## {name}\n\nNot attempted.\n")
            continue
        row = read(path)
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append(
            {
                "slot": name,
                **summary,
                "validation": row.get("validation"),
                "started_at": row.get("started_at"),
                "finished_at": row.get("finished_at"),
                "request_matches_prepared": row["request"]
                == read(LOCAL / "requests" / f"{name}.json"),
                "usage": (row.get("result") or {}).get("usage"),
            }
        )
        treatments.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        parsed = (row.get("result") or {}).get("parsed")
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                text = (
                    value
                    if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False, indent=2)
                )
                treatments.append(f"### {key}\n\n{text}\n")
        else:
            treatments.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    comparisons = {}
    for left, right in (
        ("control-1", "control-2"),
        ("control-1", "control-3"),
        ("control-1", "nonce-1"),
        ("control-1", "ingredients-0-a"),
        ("ingredients-0-a", "ingredients-0-b"),
        ("ingredients-1-a", "ingredients-1-b"),
        ("ingredients-2-a", "ingredients-2-b"),
    ):
        if left not in traces or right not in traces:
            continue
        value = compare(traces[left], traces[right])
        comparisons[f"{left}/{right}"] = {
            "fields": value["fields"],
            "configuration_equal": value["configuration_equal"],
            "same_native_session": value["same_native_session"],
        }
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    # Literal diagnostics locate evidence; they do not classify premises or score quality.
    queries = {}
    for label, pattern in {
        "previous_recurring_name": r"\bMara Venn\b",
        "repair_vocabulary": r"\b(?:repair\w*|mend\w*|salvag\w*)\b",
        "aquatic_vocabulary": r"\b(?:water|sea|ocean|flood\w*|drown\w*|tidal|tide\w*|island\w*)\b",
    }.items():
        hits = []
        for name, trace in traces.items():
            for hit in search(trace, re.compile(pattern, re.IGNORECASE)):
                hit["path"] = trace.path.relative_to(ROOT).as_posix()
                hits.append({"slot": name, **hit})
        queries[label] = {"pattern": pattern, "hits": hits}
    evidence = {
        "purpose": "Input seeding trial; no quality scores or candidate selection",
        "registration": (HERE / "registration.json").relative_to(ROOT).as_posix(),
        "manifest_sha256": sha(LOCAL / "manifest.json"),
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress,
        "calls": rows,
        "comparisons": comparisons,
        "distinct_sessions": len(sessions),
        "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
        "literal_searches": queries,
        "limits": [
            "Literal searches locate passages; inspect full treatments to interpret them.",
            "Distinct output bytes do not establish distinct premises or global originality.",
            "Seeds reproduce authored ingredient combinations, not native sampling or prose.",
            "Transport receipts do not expose every backend instruction or sampling setting.",
        ],
    }
    write(HERE / "evidence.json", evidence)
    with (LOCAL / "TREATMENTS.md").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(treatments))
    print(
        json.dumps(
            {
                "attempts": progress["attempts"],
                "tokens": progress["tokens"],
                "stop": progress["stop"],
                "frozen_file_drift": evidence["frozen_file_drift"],
                "distinct_sessions": len(sessions),
                "distinct_outputs": len(outputs),
                "validation": {r["slot"]: r.get("validation") for r in rows},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
