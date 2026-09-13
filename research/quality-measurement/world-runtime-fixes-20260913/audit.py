"""Extend the reused boundary audit with paginated-query and timing readouts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from run import HERE, RUN, load, save, sha


def audit():
    spec = importlib.util.spec_from_file_location(
        "world_runtime_audit", RUN / "source/capture-audit.py",
    )
    assert spec is not None and spec.loader is not None
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.audit()
    evidence = load(HERE / "evidence.json")
    evidence["capture_audit_sha256"] = evidence["audit_sha256"]
    evidence["audit_sha256"] = sha(Path(__file__))
    queries, timing = [], []
    for path in sorted(RUN.glob("book-*/calls/*.json")):
        row = load(path)
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        for number, command in enumerate(base.commands(raw), 1):
            args = base.arguments(command)
            if args[:2] != ["world", "query"]:
                continue
            stdout = command.get("stdout", "")
            try:
                payload = json.loads(stdout)
            except ValueError:
                payload = {}
            queries.append({
                "call": f"{path.parent.parent.name}/{path.stem}", "bridge_call": number,
                "arguments": args, "bytes": len(stdout.encode("utf-8")),
                "records": len(payload.get("records", [])), "total": payload.get("total"),
                "next_offset": payload.get("next_offset"),
                "selection_sha256": payload.get("selection_sha256"),
                "returncode": command.get("returncode"),
            })
    for path in sorted(RUN.glob("book-*/commands/*check.json")):
        receipt = load(path)
        try:
            checked = json.loads(receipt["output"])
        except ValueError:
            continue
        timing.append({
            "path": path.relative_to(RUN).as_posix(), "sha256": sha(path),
            "ok": checked.get("ok"), "unplaceable": checked.get("unplaceable", []),
        })
    evidence.update(query_reads=queries, timing_checks=timing)
    save(HERE / "evidence.json", evidence)


if __name__ == "__main__":
    audit()
