"""Rebuild controls and complete inspection material, without model calls or story scores."""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

from run import (
    ARMS,
    HERE,
    LOCAL,
    ROOT,
    expansion_request,
    imports,
    invention_request,
    parse_items,
    read,
    selected_index,
    sha,
    text_sha,
    write,
)

sys.path.insert(0, str(ROOT))
from tools.generation_trace import compare, load_trace


def request_matches(saved: dict, request) -> bool:
    return saved == json.loads(json.dumps(dataclasses.asdict(request)))


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished experiment")
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "registration.json")
    discovery, _, request_type, _ = imports()
    rows, candidates, controls, traces = [], [], {}, {}
    reading = ["# All first responses and preselected expansions\n"]
    for name in manifest["order"] + manifest["expansions"]:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        saved = read(LOCAL / "requests" / f"{name}.json")
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({"slot": name, **summary, "receipt_sha256": sha(path),
                     "validation": row.get("validation"),
                     "usage": (row.get("result") or {}).get("usage"),
                     "request_matches_saved": row["request"] == saved,
                     "request_hash_matches": row["request_sha256"]
                     == sha(LOCAL / "requests" / f"{name}.json")})
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        if name in manifest["order"]:
            arm, block = name.rsplit("-", 1)
            prefix = read(LOCAL / "seeds" / f"{block}.json")["brief"]
            index = selected_index(registration["numbers"]["selection"][block])
            controls[name] = {
                "request_matches_registered_renderer": request_matches(
                    saved, invention_request(arm, prefix, request_type)
                ),
                "captured_system_matches": trace.fields.get("transport.system") == saved["system"],
                "captured_prefix_matches":
                trace.fields.get("transport.system", "").startswith(prefix + "\n\n"),
                "precommitted_index_matches": index == manifest["selections"][block],
            }
            if row.get("validation") == "passed":
                items = parse_items(row["result"]["parsed"], arm)
                controls[name]["selected_item_matches"] = row["selected"] == {
                    "index": index, "text_sha256": text_sha(items[index]["text"]),
                }
                for i, item in enumerate(items):
                    value = item["probability"]
                    candidates.append({
                        "slot": name, "index": i, "text_sha256": text_sha(item["text"]),
                        "words": len(item["text"].split()), "selected": i == index,
                        "stated_probability": value,
                        "within_probability_range": None if value is None else 0 <= value <= 1,
                        "below_tail_threshold": None if value is None else 0 <= value < 0.10,
                        "placeholder_is_zero": None if arm != "format" else value == 0,
                    })
                    label = " (preselected)" if i == index else ""
                    reading.append(
                        f"### Premise {i + 1}{label}; estimate={value}\n\n{item['text']}\n"
                    )
            else:
                reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
        else:
            source_name = row["source"]["parent"]
            source_path = LOCAL / "calls" / f"{source_name}.json"
            source_row = read(source_path)
            index = source_row["selected"]["index"]
            item = parse_items(source_row["result"]["parsed"], source_name.split("-", 1)[0])[index]
            controls[name] = {
                "source_receipt_matches": row["source"]["receipt_sha256"] == sha(source_path),
                "source_index_matches": row["source"]["index"] == index,
                "selected_text_hash_matches":
                row["source"]["text_sha256"] == text_sha(item["text"]),
                "request_is_unmodified_discovery_with_story_only": request_matches(
                    saved, expansion_request(item, discovery)
                ),
            }
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    comparisons = {}
    for block in (1, 2):
        for left_arm, right_arm in pairwise(ARMS):
            left, right = f"{left_arm}-{block}", f"{right_arm}-{block}"
            if left in traces and right in traces:
                comparison = compare(traces[left], traces[right])
                comparisons[f"{left}:{right}"] = {k: comparison[k] for k in (
                    "fields", "configuration_equal", "same_native_session",
                )}
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    premise_hashes = Counter(c["text_sha256"] for c in candidates)
    evidence = {
        "purpose": "VS contrasts with random positional expansion; no probability-based selection",
        "audit_sha256": sha(Path(__file__)),
        "manifest_matches_registration":
        sha(LOCAL / "manifest.json") == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress, "calls": rows, "candidates": candidates, "controls": controls,
        "comparisons": comparisons, "distinct_sessions": len(sessions),
        "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
        "repeated_premise_text": {s: n for s, n in premise_hashes.items() if n > 1},
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "premises": len(candidates),
           "distinct_sessions": len(sessions),
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
