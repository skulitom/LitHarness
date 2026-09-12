"""Rebuild fixed-source sentence contrasts and all retained outputs without model calls."""

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
    draft_request,
    imports,
    parent,
    plan_request,
    read,
    sha,
    text_sha,
    write,
)

sys.path.insert(0, str(ROOT))
from tools.generation_trace import compare, load_trace


def main() -> None:
    progress = read(LOCAL / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Do not inspect an unfinished experiment")
    manifest, registration = read(LOCAL / "manifest.json"), read(HERE / "registration.json")
    discovery, _, request_type, _ = imports()
    from litharness.providers.codex_schema import prepare_codex_schema

    rows, texts, controls, traces = [], [], {}, {}
    reading = ["# Every first plan and preassigned draft\n"]
    for key in manifest["sources"]:
        reading.append(f"## Fixed premise {key}\n\n" + read(
            LOCAL / "sources" / f"{key}.json"
        )["text"] + "\n")
    for name in manifest["order"] + manifest["drafts"]:
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
                     "usage": (row.get("result") or {}).get("usage")})
        checks = controls[name] = {
            **parent.parent.transport_text_checks(request, trace.fields),
            "native_schema_equal": json.loads(trace.fields.get("transport.schema", "null"))
            == prepare_codex_schema(request.schema),
            "request_matches_saved": row["request"] == saved,
            "request_hash_matches": row["request_sha256"] == sha(
                LOCAL / "requests" / f"{name}.json"
            ),
        }
        if name in manifest["order"]:
            arm, key, _ = name.split("-")
            source = read(LOCAL / "sources" / f"{key}.json")
            original = read(ROOT / source["path"])
            checks["source_matches"] = (
                row["source"] == manifest["sources"][key] == registration["sources"][key]
                and source["text"] == parent.parse_story(original["result"]["parsed"])
                and source["text_sha256"] == text_sha(source["text"])
                and source["receipt_sha256"] == sha(ROOT / source["path"])
            )
            expected = plan_request(arm, source["text"], discovery)
        else:
            source_name = name.removeprefix("draft-")
            source_path = LOCAL / "calls" / f"{source_name}.json"
            payload = read(source_path)["result"]["parsed"]
            expected = draft_request(payload, discovery, request_type)
            checks["source_matches"] = row["source"] == {
                "parent": source_name, "receipt_sha256": sha(source_path),
                "text_sha256": parent.source_hash(payload),
            }
        checks["request_matches_registered_renderer"] = saved == json.loads(
            json.dumps(dataclasses.asdict(expected))
        )
        reading.append(f"## {name}\n\nValidation: {row.get('validation')}\n")
        payload = (row.get("result") or {}).get("parsed")
        if isinstance(payload, dict) and all(isinstance(t, str) for t in payload.values()):
            for field, story in payload.items():
                texts.append({"slot": name, "field": field, "text_sha256": text_sha(story),
                              "words": len(story.split()), "validation": row.get("validation")})
                reading.append(f"### {field}\n\n{story}\n")
        else:
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    pairs = [(f"{a}-{s}-1", f"{a}-{s}-2") for a in ARMS for s in (1, 2)]
    pairs += [(f"{a}-{s}-{r}", f"{b}-{s}-{r}") for a, b in combinations(ARMS, 2)
              for s in (1, 2) for r in (1, 2)]
    comparisons = {}
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
        "purpose": "One discovery sentence: full, omitted, or conditional on the supplied brief",
        "audit_sha256": sha(Path(__file__)),
        "manifest_matches_registration": sha(LOCAL / "manifest.json")
        == registration["manifest_sha256"],
        "frozen_file_drift": [p for p, h in manifest["files"].items() if sha(Path(p)) != h],
        "progress": progress, "calls": rows, "texts": texts, "controls": controls,
        "comparisons": comparisons, "distinct_sessions": len(sessions),
        "distinct_outputs": len(outputs),
        "shared_sessions": {s: n for s, n in sessions.items() if n > 1},
        "repeated_outputs": {s: n for s, n in outputs.items() if n > 1},
    }
    write(HERE / "evidence.json", evidence)
    write(LOCAL / "reading.json", {"markdown": "\n".join(reading)})
    print({"attempts": progress["attempts"], "tokens": progress["tokens"], "stop": progress["stop"],
           "frozen_file_drift": evidence["frozen_file_drift"], "text_units": len(texts),
           "failed_controls": {n: [k for k, v in checks.items() if not v]
                               for n, checks in controls.items() if not all(checks.values())},
           "validation": {r["slot"]: r.get("validation") for r in rows}})


if __name__ == "__main__":
    main()
