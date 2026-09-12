"""Rebuild history coverage, exact-repeat controls and complete output inventory offline."""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from run import (
    ARMS,
    HERE,
    LOCAL,
    ROOT,
    expansion_request,
    history_pair,
    imports,
    invention_request,
    parent,
    read,
    selected_index,
    sha,
    text_sha,
    transport_text_checks,
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
    manifest, registration = read(LOCAL / "manifest.json"), read(HERE / "registration.json")
    histories = read(LOCAL / "history.json")
    discovery, _, request_type, _ = imports()
    from litharness.providers.codex_schema import prepare_codex_schema
    sources, history_checks = [], {}
    for source in registration["history_provenance"]:
        name, index = source["slot"], source["index"]
        premise_path = parent.LOCAL / "calls" / f"{name}.json"
        plan_path = parent.LOCAL / "calls" / f"expand-{name}.json"
        premise_row, plan_row = read(premise_path), read(plan_path)
        premise = parent.parse_items(premise_row["result"]["parsed"], name.split("-", 1)[0])[
            index
        ]["text"]
        plan = plan_row["result"]["parsed"]
        sources.append((premise, plan))
        history_checks[name] = {
            "premise_receipt_matches": sha(premise_path) == source["premise_receipt_sha256"],
            "plan_receipt_matches": sha(plan_path) == source["plan_receipt_sha256"],
            "premise_text_matches": text_sha(premise) == source["text_sha256"],
            "plan_fields_match": {k: text_sha(v) for k, v in plan.items()}
            == source["plan_field_sha256"],
        }
    rows, candidates, controls, traces = [], [], {}, {}
    reading = ["# All new first responses and repeated expansions\n"]
    for name in manifest["order"] + manifest["expansions"]:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            rows.append({"slot": name, "status": "not_attempted"})
            continue
        row = read(path)
        saved = read(LOCAL / "requests" / f"{name}.json")
        request = request_type(**saved)
        trace = traces[name] = load_trace(path)
        summary = trace.summary()
        summary["path"] = path.relative_to(ROOT).as_posix()
        rows.append({"slot": name, **summary, "receipt_sha256": sha(path),
                     "validation": row.get("validation"),
                     "usage": (row.get("result") or {}).get("usage"),
                     "request_matches_saved": row["request"] == saved,
                     "request_hash_matches": row["request_sha256"]
                     == sha(LOCAL / "requests" / f"{name}.json")})
        controls[name] = {
            **transport_text_checks(request, trace.fields),
            "native_schema_equal": json.loads(trace.fields.get("transport.schema", "null"))
            == prepare_codex_schema(request.schema),
        }
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        if name in manifest["order"]:
            block = name.rsplit("-", 1)[1]
            prefix = read(LOCAL / "seeds" / f"{block}.json")["brief"]
            index = selected_index(registration["numbers"]["selection"][block])
            controls[name].update({
                "request_matches_registered_renderer": request_matches(
                    saved, invention_request(prefix, histories, request_type)
                ),
                "captured_prefix_matches":
                trace.fields.get("transport.system", "").startswith(prefix + "\n\n"),
                "precommitted_index_matches": index == manifest["selections"][block],
            })
            if row.get("validation") == "passed":
                premises = parent.parent.parse_premises(row["result"]["parsed"], 6)
                controls[name]["selected_item_matches"] = row["selected"] == {
                    "index": index, "text_sha256": text_sha(premises[index]),
                }
                for i, premise in enumerate(premises):
                    candidates.append({"slot": name, "index": i, "text_sha256": text_sha(premise),
                                       "words": len(premise.split()), "selected": i == index})
                    label = " (preselected)" if i == index else ""
                    reading.append(f"### Premise {i + 1}{label}\n\n{premise}\n")
            else:
                reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
        else:
            arm, block, _ = name.split("-")
            source_name = f"invent-{block}"
            source_path = LOCAL / "calls" / f"{source_name}.json"
            index = manifest["selections"][block]
            premise = parent.parent.parse_premises(read(source_path)["result"]["parsed"], 6)[index]
            controls[name].update({
                "source_matches": row["source"] == {
                    "parent": source_name, "receipt_sha256": sha(source_path), "index": index,
                    "text_sha256": text_sha(premise),
                },
                "request_matches_registered_renderer": request_matches(
                    saved, expansion_request(arm, premise, histories, discovery)
                ),
            })
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    comparisons = {}
    pairs = []
    for block in (1, 2):
        pairs.extend((f"{a}-{block}-1", f"{a}-{block}-2") for a in ARMS)
        for repeat in (1, 2):
            pairs.extend((f"{a}-{block}-{repeat}", f"{b}-{block}-{repeat}")
                         for a, b in combinations(ARMS, 2))
    for left, right in pairs:
        if left in traces and right in traces:
            result = compare(traces[left], traces[right])
            comparisons[f"{left}:{right}"] = {k: result[k] for k in (
                "fields", "configuration_equal", "same_native_session",
            )}
    sessions = Counter(s for row in rows for s in row.get("sessions", []))
    outputs = Counter(row.get("field_sha256", {}).get("output.text") for row in rows)
    outputs.pop(None, None)
    evidence = {
        "purpose": "Full versus short generated-history coverage with repeated clean controls",
        "audit_sha256": sha(Path(__file__)),
        "manifest_matches_registration":
        sha(LOCAL / "manifest.json") == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "history_matches_original_fields": histories == history_pair(sources),
        "history_checks": history_checks,
        "history_characters": {a: len(json.dumps(h)) for a, h in histories.items()},
        "progress": progress, "calls": rows, "candidates": candidates, "controls": controls,
        "comparisons": comparisons, "distinct_sessions": len(sessions),
        "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
    }
    write(HERE / "evidence.json", evidence)
    (LOCAL / "TREATMENTS.md").write_text("\n".join(reading), encoding="utf-8", newline="\n")
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "premises": len(candidates),
           "failed_controls": {n: [k for k, v in checks.items() if not v]
                               for n, checks in controls.items() if not all(checks.values())},
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
