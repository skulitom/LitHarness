"""Rebuild exact input, source and repeat controls without model calls."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from run import (
    HERE,
    LOCAL,
    ORDER,
    ROOT,
    expansion_request,
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


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished batch")
    manifest = read(LOCAL / "manifest.json")
    registration = read(HERE / "registration.json")
    inputs = read(LOCAL / "inputs.json")
    discovery, _, _, _ = imports()
    rows, controls, traces = [], {}, {}
    reading = ["# Every first-response expansion\n"]
    for name in ORDER:
        arm, block, repeat = name.split("-")
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        saved = read(LOCAL / "requests" / f"{name}.json")
        source = inputs["sources"][block]
        source_path = ROOT / source["path"]
        original = read(source_path)["result"]["parsed"]["premises"][source["index"]]
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({"slot": name, **summary, "validation": row.get("validation"),
                     "usage": (row.get("result") or {}).get("usage")})
        clean = read(LOCAL / "requests" / f"clean-{block}-{repeat}.json")
        request = expansion_request(arm, source["premise"], inputs["history"], discovery)
        checks = controls[name] = {
            "saved_request_matches": saved == row["request"],
            "request_hash_matches": row["request_sha256"]
            == registration["request_sha256"][name] == sha(LOCAL / "requests" / f"{name}.json"),
            "registered_request_matches": request_matches(saved, request),
            "captured_prompt_matches": trace.fields.get("transport.prompt") == saved["prompt"],
            "medium_effort_captured": bool(trace.configuration)
            and trace.configuration["settings"]["model_reasoning_effort"] == "medium",
            "repeat_request_identical": saved
            == read(LOCAL / "requests" / f"{arm}-{block}-{3 - int(repeat)}.json"),
            "only_user_prompt_varies": {k: v for k, v in saved.items() if k != "prompt"}
            == {k: v for k, v in clean.items() if k != "prompt"},
            "source_metadata_matches": row["source"] == registration["sources"][block],
            "source_receipt_matches": sha(source_path) == source["receipt_sha256"],
            "source_text_matches": original == source["premise"]
            and text_sha(original) == source["text_sha256"],
        }
        if arm == "combined":
            old = read(parent.LOCAL / "requests" / f"retain-structure-{block}.json")
            checks["original_combined_request_identical"] = saved == old
        if arm == "clean":
            old = read(parent.LOCAL / "requests" / f"expand-structure-{block}.json")
            checks["original_clean_request_identical"] = saved == old
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n\n"
                       + trace.fields.get("output.text", "No final output captured.") + "\n")
    baseline = traces.get(ORDER[0])
    for name, trace in traces.items():
        controls[name]["configuration_matches_baseline"] = bool(baseline and baseline.configuration)
        if baseline is not None:
            controls[name]["configuration_matches_baseline"] &= (
                trace.configuration == baseline.configuration
            )
            controls[name]["transport_system_matches_baseline"] = (
                trace.fields.get("transport.system") == baseline.fields.get("transport.system")
            )
    repeats = {}
    for block in ("1", "2"):
        for arm in ("clean", "preserve", "combined"):
            a, b = (traces.get(f"{arm}-{block}-{r}") for r in (1, 2))
            repeats[f"{arm}-{block}"] = {
                "captured_inputs_equal": bool(a and b) and
                {k: v for k, v in a.fields.items() if k != "output.text"}
                == {k: v for k, v in b.fields.items() if k != "output.text"},
            }
    sessions = Counter(s for t in traces.values() for s in t.sessions)
    outputs = Counter(text_sha(t.fields["output.text"]) for t in traces.values()
                      if "output.text" in t.fields)
    evidence = {
        "audit_sha256": sha(Path(__file__)), "progress": progress,
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "inputs_match_registration": sha(LOCAL / "inputs.json") == registration["inputs_sha256"],
        "history_matches_parent": inputs["history"]
        == read(parent.LOCAL / "history.json")["premises"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "calls": rows, "controls": controls, "repeat_controls": repeats,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "distinct_sessions": len(sessions),
           "failed_controls": {n: [k for k, v in c.items() if not v]
                               for n, c in controls.items() if not all(c.values())},
           "repeat_controls": repeats,
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
