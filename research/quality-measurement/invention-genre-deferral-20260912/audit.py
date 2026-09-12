"""Offline first-output inventory, frozen-input controls and full generation lineage."""

from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

from run import (
    ARMS,
    HERE,
    LOCAL,
    ROOT,
    core,
    dependent_request,
    imports,
    invention_request,
    parent,
    parse_story,
    read,
    selected_index,
    sha,
    source_for,
    source_hash,
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
    discovery, invention, request_type, _ = imports()
    from litharness.providers.codex_schema import prepare_codex_schema

    rows, texts, controls, traces = [], [], {}, {}
    reading = ["# Every first response and every preselected chain\n"]
    schedule = manifest["order"] + [s + "-" + c for s in manifest["stages"]
                                    for c in manifest["chains"]]
    for name in schedule:
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
        controls[name] = {
            **parent.transport_text_checks(request, trace.fields),
            "native_schema_equal": json.loads(trace.fields.get("transport.schema", "null"))
            == prepare_codex_schema(request.schema),
            "request_matches_saved": row["request"] == saved,
            "request_hash_matches": row["request_sha256"] == sha(
                LOCAL / "requests" / f"{name}.json"
            ),
        }
        reading.append(f"## {name}\n\nReceipt: calls/{name}.json\n")
        if name in manifest["order"]:
            arm, block, repeat = name.split("-")
            seed = invention.make_seed(registration["numbers"]["prefix"][block])
            index = selected_index(registration["numbers"]["selection"][block])
            expected = invention_request(arm, seed.brief, request_type)
            controls[name].update({
                "seed_packet_matches": read(LOCAL / "seeds" / f"{block}.json")
                == seed.to_jsonable(),
                "captured_prefix_matches": trace.fields.get("transport.system", "").startswith(
                    seed.brief + "\n\n"
                ),
                "precommitted_index_matches": index == manifest["selections"][block],
            })
            if row.get("validation") == "passed":
                for i, story in enumerate(core.parse_premises(row["result"]["parsed"], 6)):
                    texts.append({"slot": name, "index": i, "text_sha256": text_sha(story),
                                  "words": len(story.split()),
                                  "scheduled_for_adaptation": i == index and repeat == "1"})
                    reading.append(f"### Premise {i + 1}\n\n{story}\n")
        else:
            stage, chain = name.split("-", 1)
            stage_index = manifest["stages"].index(stage)
            source_name = (chain if stage_index == 0
                           else manifest["stages"][stage_index - 1] + "-" + chain)
            source_path = LOCAL / "calls" / f"{source_name}.json"
            index = manifest["selections"][chain.split("-")[1]]
            source = source_for(stage, read(source_path), index)
            expected = dependent_request(stage, source, discovery, request_type)
            controls[name]["source_matches"] = row["source"] == {
                "parent": source_name, "receipt_sha256": sha(source_path),
                "index": index if stage == "adapt" else None, "text_sha256": source_hash(source),
            }
            if row.get("validation") == "passed":
                payload = row["result"]["parsed"]
                parts = payload if stage == "plan" else {"story": parse_story(payload)}
                for field, story in parts.items():
                    texts.append({"slot": name, "field": field, "text_sha256": text_sha(story),
                                  "words": len(story.split())})
                    reading.append(f"### {field}\n\n{story}\n")
        controls[name]["request_matches_registered_renderer"] = saved == json.loads(
            json.dumps(dataclasses.asdict(expected))
        )
        if row.get("validation") != "passed":
            reading.append(trace.fields.get("output.text", "No final output captured.") + "\n")
    pairs = [(f"{a}-{b}-1", f"{a}-{b}-2") for a in ARMS for b in (1, 2)]
    pairs += [(f"early-{b}-{r}", f"late-{b}-{r}") for b in (1, 2) for r in (1, 2)]
    pairs += [(f"{a}-1-{r}", f"{a}-2-{r}") for a in ARMS for r in (1, 2)]
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
        "purpose": "Early versus deferred genre cue; all outputs and preselected story chains",
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
