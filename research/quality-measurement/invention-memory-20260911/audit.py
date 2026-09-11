"""Offline history and carry-through provenance, with every first response retained."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from run import (
    HERE,
    LOCAL,
    ROOT,
    expansion_request,
    generation_prompt,
    imports,
    parse_premises,
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
    history = read(LOCAL / "history.json")
    discovery, _, _, _ = imports()
    traces, rows, candidates, controls = {}, [], [], {}
    reading = ["# All first responses and preselected expansions\n"]
    base_request = read(LOCAL / "requests/baseline-1.json")
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
        rows.append({"slot": name, **summary, "validation": row.get("validation"),
                     "usage": (row.get("result") or {}).get("usage")})
        checks = controls[name] = {
            "saved_request_matches": saved == row["request"],
            "request_hash_matches": row["request_sha256"]
            == sha(LOCAL / "requests" / f"{name}.json"),
            "captured_prompt_matches": saved["prompt"] == trace.fields.get("transport.prompt"),
            "medium_effort_captured": bool(trace.configuration) and
            trace.configuration["settings"]["model_reasoning_effort"] == "medium",
        }
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        if name in manifest["expansions"]:
            source = row["source"]
            source_path = LOCAL / "calls" / f"{source['parent']}.json"
            source_row = read(source_path)
            index = source_row["selected"]["index"]
            premise = source_row["result"]["parsed"]["premises"][index]
            checks.update({
                "source_receipt_matches": source["receipt_sha256"] == sha(source_path),
                "source_index_matches": source["index"] == index,
                "selected_text_hash_matches": source["text_sha256"] == text_sha(premise),
                "registered_expansion_matches": request_matches(
                    saved, expansion_request(name, premise, history["premises"], discovery)
                ),
            })
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
        else:
            arm, block = name.rsplit("-", 1)
            checks.update({
                "registered_prompt_matches": saved["prompt"]
                == generation_prompt(arm, history["premises"]),
                "non_text_fields_match":
                {k: v for k, v in saved.items() if k not in ("system", "prompt")}
                == {k: v for k, v in base_request.items() if k not in ("system", "prompt")},
                "same_system_within_block": saved["system"]
                == read(LOCAL / "requests" / f"baseline-{block}.json")["system"],
                "captured_prefix_matches": trace.fields.get("transport.system", "").startswith(
                    read(LOCAL / "seeds" / f"{block}.json")["brief"] + "\n\n"
                ),
            })
            if row.get("validation") == "passed":
                premises = parse_premises(row["result"]["parsed"], 6)
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
    baseline = traces.get("baseline-1")
    for name, trace in traces.items():
        controls[name]["configuration_matches_baseline"] = bool(baseline and baseline.configuration)
        if baseline is not None:
            controls[name]["configuration_matches_baseline"] &= (
                trace.configuration == baseline.configuration
            )
    source_checks = []
    for premise, origin in zip(history["premises"], history["provenance"], strict=True):
        path = ROOT / origin["source"]
        source_checks.append({
            "receipt_matches": sha(path) == origin["receipt_sha256"],
            "text_matches": text_sha(premise) == origin["text_sha256"],
            "original_item_matches": premise
            == read(path)["result"]["parsed"]["premises"][origin["index"]],
        })
    sessions = Counter(s for t in traces.values() for s in t.sessions)
    outputs = Counter(text_sha(t.fields["output.text"]) for t in traces.values()
                      if "output.text" in t.fields)
    evidence = {
        "audit_sha256": sha(Path(__file__)), "progress": progress,
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "history_matches_registration": sha(LOCAL / "history.json")
        == registration["history_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "calls": rows, "candidates": candidates, "controls": controls,
        "history_controls": source_checks,
        "distinct_sessions": len(sessions), "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "premises": len(candidates),
           "distinct_sessions": len(sessions),
           "failed_controls": {n: [k for k, v in c.items() if not v]
                               for n, c in controls.items() if not all(c.values())},
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
