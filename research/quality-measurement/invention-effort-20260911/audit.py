"""Rebuild effort controls, exact selection provenance, and the complete reading copy."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from run import (
    HERE,
    LOCAL,
    ROOT,
    effort_for,
    imports,
    parent,
    read,
    request_matches,
    sha,
    text_sha,
    write,
)

sys.path.insert(0, str(ROOT))
from tools.generation_trace import load_trace


def without_effort(configuration: dict) -> dict:
    return {**configuration, "settings": {
        k: v for k, v in configuration["settings"].items() if k != "model_reasoning_effort"
    }}


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    manifest = read(LOCAL / "manifest.json")
    discovery, _, _, _ = imports()
    traces, rows, candidates, controls = {}, [], [], {}
    reading = ["# All first responses and preselected expansions\n"]
    for name in manifest["order"] + ["expand-" + n for n in manifest["expansions"]]:
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
                     "usage": (row.get("result") or {}).get("usage")})
        checks = controls[name] = {
            "saved_request_matches": saved == row["request"],
            "request_hash_matches": row["request_sha256"]
            == sha(LOCAL / "requests" / f"{name}.json"),
            "requested_effort_matches": row["requested_effort"] == effort_for(name),
            "captured_effort_matches": bool(trace.configuration) and
            trace.configuration["settings"]["model_reasoning_effort"] == effort_for(name),
        }
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        if name.startswith("expand-"):
            source = row["source"]
            source_path = LOCAL / "calls" / f"{source['parent']}.json"
            source_row = read(source_path)
            index = source_row["selected"]["index"]
            premise = source_row["result"]["parsed"]["premises"][index]
            checks.update({
                "source_receipt_matches": source["receipt_sha256"] == sha(source_path),
                "source_index_matches": source["index"] == index,
                "selected_text_hash_matches": source["text_sha256"] == text_sha(premise),
                "unmodified_expansion_request": request_matches(
                    saved, discovery.render_request(premise, person="third")
                ),
            })
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
        else:
            block = name.rsplit("-", 1)[1]
            prefix = read(LOCAL / "seeds" / f"{block}.json")["brief"]
            checks["prepared_system_matches"] = saved["system"] == parent.system_text(
                prefix, "batch"
            )
            checks["captured_prefix_matches"] = trace.fields.get("transport.system", "").startswith(
                prefix + "\n\n"
            )
            if row.get("validation") == "passed":
                premises = parent.parse_premises(row["result"]["parsed"], 6)
                index = manifest["selections"][block]
                checks["precommitted_selection_matches"] = row["selected"] == {
                    "index": index, "text_sha256": text_sha(premises[index]),
                }
                for i, premise in enumerate(premises):
                    candidates.append({"slot": name, "index": i, "text_sha256": text_sha(premise),
                                       "words": len(premise.split()), "selected": i == index})
                    label = " (preselected)" if i == index else ""
                    reading.append(f"### Premise {i + 1}{label}\n\n{premise}\n")
            else:
                reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    pairs = {}
    for b in (1, 2, 3):
        left, right = traces.get(f"low-{b}"), traces.get(f"medium-{b}")
        if left is not None and right is not None:
            pairs[str(b)] = {
                "all_input_fields_identical":
                {k: v for k, v in left.fields.items() if k != "output.text"}
                == {k: v for k, v in right.fields.items() if k != "output.text"},
                "configuration_identical_except_effort":
                bool(left.configuration and right.configuration)
                and without_effort(left.configuration) == without_effort(right.configuration),
                "sessions_disjoint": bool(left.sessions and right.sessions)
                and set(left.sessions).isdisjoint(right.sessions),
            }
    sessions = Counter(s for t in traces.values() for s in t.sessions)
    outputs = Counter(text_sha(t.fields["output.text"]) for t in traces.values()
                      if "output.text" in t.fields)
    evidence = {
        "audit_sha256": sha(Path(__file__)), "progress": progress,
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == read(HERE / "registration.json")["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "calls": rows, "candidates": candidates, "controls": controls, "paired_controls": pairs,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "premises": len(candidates),
           "distinct_sessions": len(sessions), "paired_controls": pairs,
           "failed_controls": {n: [k for k, v in c.items() if not v]
                               for n, c in controls.items() if not all(c.values())},
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
