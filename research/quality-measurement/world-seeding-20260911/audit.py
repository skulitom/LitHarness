"""Derive integrity records and a local reading copy after the experiment finishes."""

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
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "registration.json")
    rows, traces, reading = [], {}, ["# All concrete-world-seeding first responses\n"]
    for name in manifest["order"]:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            reading.append(f"## {name}\n\nNot attempted; see progress for the reason.\n")
            continue
        row = read(path)
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append(
            {
                "slot": name,
                **summary,
                **{
                    key: row.get(key)
                    for key in (
                        "validation",
                        "started_at",
                        "finished_at",
                        "machinery_names",
                        "requires_precision",
                        "discovery_preserved",
                        "seed_preserved",
                    )
                },
                "request_matches_saved": row["request"]
                == read(LOCAL / "requests" / f"{name}.json"),
                "usage": (row.get("result") or {}).get("usage"),
            }
        )
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        seed_path = LOCAL / "seeds" / f"{name}.json"
        if seed_path.exists():
            reading.append(f"### Input\n\n{read(seed_path)['brief']}\n")
        parsed = (row.get("result") or {}).get("parsed")
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                rendered = (
                    value
                    if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False, indent=2)
                )
                reading.append(f"### {key}\n\n{rendered}\n")
        else:
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    pairs, seed_controls = {}, {}
    for index in range(3):
        left, right = f"baseline-{index}", f"world-{index}"
        baseline_seed = read(LOCAL / "seeds" / f"{left}.json")
        world_seed = read(LOCAL / "seeds" / f"{right}.json")
        baseline_request = read(LOCAL / "requests" / f"{left}.json")
        world_request = read(LOCAL / "requests" / f"{right}.json")
        expected_request = {
            **baseline_request,
            "prompt": baseline_request["prompt"].replace(
                baseline_seed["brief"], world_seed["brief"], 1
            ),
        }
        seed_controls[str(index)] = {
            "same_label_and_index": all(
                baseline_seed[k] == world_seed[k] for k in ("seed", "index")
            ),
            "world_extends_exact_base_brief": world_seed["brief"].startswith(
                baseline_seed["brief"] + "\nConcrete world starting points:"
            ),
            "only_prepared_request_change_is_world_extension": expected_request == world_request,
            "seed_file_sha256": {
                name: sha(LOCAL / "seeds" / f"{name}.json") for name in (left, right)
            },
        }
        if left in traces and right in traces:
            compared = compare(traces[left], traces[right])
            pairs[str(index)] = {
                key: compared[key]
                for key in (
                    "fields",
                    "configuration_equal",
                    "same_native_session",
                )
            }
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    hits = []
    query = (
        r"\b(?:Mara Venn|Sera Venn|drowned|orchard|water|flood\w*|"
        r"repair\w*|mend\w*|nurser\w*|load-bearing)\b"
    )
    for name, trace in traces.items():
        for hit in search(trace, re.compile(query, re.IGNORECASE)):
            hit["path"] = trace.path.relative_to(ROOT).as_posix()
            hits.append({"slot": name, **hit})
    evidence = {
        "purpose": "Input controls and preservation; no quality score or candidate selection",
        "manifest_sha256": sha(LOCAL / "manifest.json"),
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress,
        "calls": rows,
        "discovery_pairs": pairs,
        "seed_controls": seed_controls,
        "distinct_sessions": len(sessions),
        "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
        "literal_search": {
            "query": query,
            "hits": hits,
            "interpretation": "Passage locations only",
        },
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
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
