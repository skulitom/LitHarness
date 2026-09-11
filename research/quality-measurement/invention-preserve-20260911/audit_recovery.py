"""Audit recoverable evidence while keeping shutdown losses explicit."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from resume import HERE, LOCAL, LOST, RECOVERY, ROOT, original, read, sha

sys.path.insert(0, str(ROOT))
from tools.generation_trace import load_trace


def main() -> None:
    progress = read(RECOVERY / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Keep new prose unread until recovery finishes")
    registration = read(HERE / "registration.json")
    recovery = read(HERE / "recovery-registration.json")
    manifest = read(RECOVERY / "manifest.json")
    inputs = read(LOCAL / "inputs.json")
    discovery, _, _, _ = original.imports()
    rows, controls, traces = [], {}, {}
    reading = ["# Every recoverable first response; missing slots retained\n"]
    for name in original.ORDER:
        if name in LOST:
            rows.append({"slot": name, **recovery["records"][name]})
            reading.append(f"## {name}\n\nLost after shutdown; no replacement.\n")
            continue
        path = (LOCAL if name in original.ORDER[:2] else RECOVERY) / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        saved = read(LOCAL / "requests" / f"{name}.json")
        arm, block, _ = name.split("-")
        source = inputs["sources"][block]
        source_path = ROOT / source["path"]
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({"slot": name, **summary, "validation": row.get("validation"),
                     "usage": (row.get("result") or {}).get("usage")})
        request = original.expansion_request(arm, source["premise"], inputs["history"], discovery)
        controls[name] = {
            "saved_request_matches": saved == row["request"],
            "registered_request_hash_matches": row["request_sha256"]
            == registration["request_sha256"][name] == sha(LOCAL / "requests" / f"{name}.json"),
            "registered_request_matches": original.request_matches(saved, request),
            "captured_prompt_matches": trace.fields.get("transport.prompt") == saved["prompt"],
            "medium_effort_captured": bool(trace.configuration)
            and trace.configuration["settings"]["model_reasoning_effort"] == "medium",
            "source_metadata_matches": row["source"] == registration["sources"][block],
            "source_receipt_matches": sha(source_path) == source["receipt_sha256"],
            "source_text_matches": source["premise"]
            == read(source_path)["result"]["parsed"]["premises"][source["index"]]
            and original.text_sha(source["premise"]) == source["text_sha256"],
        }
        reading.append(f"## {name}\n\nReceipt: {path.relative_to(LOCAL).as_posix()}\n\n"
                       + trace.fields.get("output.text", "No final output captured.") + "\n")
    baseline = traces["clean-1-1"]
    for name, trace in traces.items():
        controls[name]["configuration_matches_pre_shutdown_baseline"] = (
            bool(baseline.configuration) and trace.configuration == baseline.configuration
        )
        controls[name]["transport_system_matches_baseline"] = (
            trace.fields.get("transport.system") == baseline.fields.get("transport.system")
        )
    repeats = {}
    for block in ("1", "2"):
        for arm in ("clean", "preserve", "combined"):
            a, b = (traces.get(f"{arm}-{block}-{r}") for r in (1, 2))
            repeats[f"{arm}-{block}"] = None if not (a and b) else (
                {k: v for k, v in a.fields.items() if k != "output.text"}
                == {k: v for k, v in b.fields.items() if k != "output.text"}
            )
    sessions = Counter(s for t in traces.values() for s in t.sessions)
    outputs = Counter(original.text_sha(t.fields["output.text"]) for t in traces.values()
                      if "output.text" in t.fields)
    evidence = {
        "audit_sha256": sha(Path(__file__)), "recovery_progress": progress,
        "original_known_tokens": recovery["known_original_tokens"],
        "unknown_usage_slots": list(LOST), "original_token_ceiling_verified": None,
        "recovery_manifest_matches_registration": sha(RECOVERY / "manifest.json")
        == recovery["manifest_sha256"],
        "original_registration_matches": sha(HERE / "registration.json")
        == recovery["original_registration_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "calls": rows, "controls": controls, "repeat_captured_inputs_equal": repeats,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
    }
    original.write(HERE / "evidence.json", evidence)
    (RECOVERY / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"recovery_attempts": progress["attempts"], "recovery_tokens": progress["tokens"],
           "stop": progress["stop"], "lost_slots": LOST, "distinct_sessions": len(sessions),
           "frozen_file_drift": evidence["frozen_file_drift"],
           "failed_controls": {n: [k for k, v in c.items() if not v]
                               for n, c in controls.items() if not all(c.values())},
           "repeat_inputs_equal": repeats,
           "validation": {r["slot"]: r.get("validation", r["status"]) for r in rows}})


if __name__ == "__main__":
    main()
