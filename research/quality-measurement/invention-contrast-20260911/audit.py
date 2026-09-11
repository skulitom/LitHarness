"""Rebuild transport controls and all-premise evidence without model calls."""

from __future__ import annotations

import dataclasses
import re
import sys
from collections import Counter
from pathlib import Path

from run import HERE, LOCAL, ROOT, imports, parse_premises, read, sha, text_sha, write

sys.path.insert(0, str(ROOT))
from tools.generation_trace import compare, load_trace, search


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "registration.json")
    discovery, _, _, _ = imports()
    order = manifest["order"] + ["expand-" + n for n in manifest["expansions"]]
    rows, candidates, controls, traces = [], [], {}, {}
    reading = ["# All first responses and prespecified expansions\n"]
    baseline = read(LOCAL / "requests/single-1.json")
    for name in order:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        saved = read(LOCAL / "requests" / f"{name}.json")
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({"slot": name, **summary, "validation": row.get("validation"),
                     "usage": (row.get("result") or {}).get("usage"),
                     "request_matches_saved": row["request"] == saved,
                     "request_hash_matches": row["request_sha256"]
                     == sha(LOCAL / "requests" / f"{name}.json")})
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        if not name.startswith("expand-"):
            arm, block = name.rsplit("-", 1)
            prefix = read(LOCAL / "seeds" / f"{block}.json")["brief"] + "\n\n"
            controls[name] = {
                "non_system_request_fields_match": {k: v for k, v in saved.items() if k != "system"}
                == {k: v for k, v in baseline.items() if k != "system"},
                "prepared_prefix_matches": saved["system"].startswith(prefix),
                "captured_prefix_matches":
                trace.fields.get("transport.system", "").startswith(prefix),
            }
            if row.get("validation") == "passed":
                premises = parse_premises(row["result"]["parsed"], 1 if arm == "single" else 6)
                index = 0 if arm == "single" else manifest["selections"][block]
                controls[name]["precommitted_selection_matches"] = row["selected"] == {
                    "index": index, "text_sha256": text_sha(premises[index]),
                }
                for i, premise in enumerate(premises):
                    candidates.append({"slot": name, "index": i, "text_sha256": text_sha(premise),
                                       "words": len(premise.split()), "selected": i == index})
                    selected_label = " (preselected)" if i == index else ""
                    reading.append(f"### Premise {i + 1}{selected_label}\n\n{premise}\n")
            else:
                reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
        else:
            parent = row["source"]["parent"]
            parent_path = LOCAL / "calls" / f"{parent}.json"
            parent_row = read(parent_path)
            index = parent_row["selected"]["index"]
            premise = parent_row["result"]["parsed"]["premises"][index]
            controls[name] = {
                "source_receipt_matches": row["source"]["receipt_sha256"] == sha(parent_path),
                "source_index_matches": row["source"]["index"] == index,
                "selected_text_hash_matches": row["source"]["text_sha256"] == text_sha(premise),
                "request_is_unmodified_discovery_with_selected_brief": saved
                == dataclasses.asdict(discovery.render_request(premise, person="third")),
            }
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    comparisons = {}
    for b in (1, 2):
        for a, c in (("single", "batch"), ("batch", "contrast"), ("contrast", "representative"),
                     ("contrast", "placebo"), ("representative", "placebo")):
            left, right = f"{a}-{b}", f"{c}-{b}"
            if left in traces and right in traces:
                result = compare(traces[left], traces[right])
                comparisons[f"{left}:{right}"] = {k: result[k] for k in (
                    "fields", "configuration_equal", "same_native_session",
                )}
    query = r"\b(?:Mara(?: Venn)?|Venn|water|flood\w*|repair\w*|bridge\w*|rescue\w*|support\w*)\b"
    hits = []
    for name, trace in traces.items():
        for hit in search(trace, re.compile(query, re.IGNORECASE)):
            if hit["field"] == "output.text":
                hit["path"] = trace.path.relative_to(ROOT).as_posix()
                hits.append({"slot": name, **hit})
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    candidate_hashes = Counter(c["text_sha256"] for c in candidates)
    evidence = {
        "purpose": "Batch and wording contrasts; all items retained without ranking or scores",
        "manifest_matches_registration":
        sha(LOCAL / "manifest.json") == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress, "calls": rows, "candidates": candidates, "controls": controls,
        "comparisons": comparisons,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
        "repeated_premise_text": {s: n for s, n in candidate_hashes.items() if n > 1},
        "literal_search": {
            "query": query, "hits": hits, "interpretation": "Passage locations only",
        },
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "premises": len(candidates),
           "distinct_sessions": len(sessions),
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
