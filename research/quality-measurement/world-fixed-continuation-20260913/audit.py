"""Extend the reused boundary audit with paginated-query and timing readouts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

from run import HERE, RUN, load, save, sha


def audit():
    spec = importlib.util.spec_from_file_location(
        "world_runtime_audit", HERE / "capture_audit.py",
    )
    assert spec is not None and spec.loader is not None
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.audit()
    evidence = load(HERE / "evidence.json")
    evidence["capture_audit_sha256"] = evidence["audit_sha256"]
    evidence["audit_sha256"] = sha(Path(__file__))
    queries, timing, shows, grow_keys = [], [], [], []
    for path in sorted(RUN.glob("book-*/calls/*.json")):
        row = load(path)
        if row["request"]["profile"].startswith("architect.grow."):
            grow_keys.append({
                "call": f"{path.parent.parent.name}/{path.stem}",
                "supplied_keys": re.findall(
                    r"This chapter's exact story key: ([^.\s]+)\.", row["request"]["prompt"],
                ),
            })
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        for number, command in enumerate(base.commands(raw), 1):
            args = base.arguments(command)
            if args[:2] == ["world", "show"]:
                shows.append({
                    "call": f"{path.parent.parent.name}/{path.stem}", "bridge_call": number,
                    "arguments": args, "executed": command.get("argv") is not None,
                    "returncode": command.get("returncode"), "error": command.get("error"),
                })
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
                "offset": payload.get("offset"),
                "next_offset": payload.get("next_offset"),
                "selection_sha256": payload.get("selection_sha256"),
                "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
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
    worlds = []
    for path in sorted(RUN.glob("book-*/final/world.txt")):
        seed_path = path.parent.parent / "seeded/world.txt"
        seeded = load(seed_path) if seed_path.exists() else []
        initial_ids = {record["record_id"] for record in seeded}
        accepted = [record for record in load(path) if record["canon"]]
        introduced = [record for record in accepted if record["record_id"] not in initial_ids]
        unplaceable = [record for record in accepted if record["order_key"] is not None
                       and re.fullmatch(r"s\d+", record["order_key"]) is None]
        worlds.append({
            "book": path.parent.parent.name, "accepted_count": len(accepted),
            "introduced_canon": [
                {key: record[key] for key in ("record_id", "subject", "predicate", "order_key")}
                for record in introduced
            ],
            "unplaceable_canon_ids": [record["record_id"] for record in unplaceable],
        })
    evidence.update(query_reads=queries, timing_checks=timing, show_attempts=shows,
                    grow_story_keys=grow_keys, final_worlds=worlds)
    positioned = []
    for book in evidence["books"]:
        known = set()
        for checkpoint in book["checkpoints"]:
            records = load(RUN / book["id"] / checkpoint["label"] / "world.txt")
            accepted = [record for record in records if record["canon"]]
            introduced = [record for record in accepted if record["record_id"] not in known]
            positioned.append({
                "book": book["id"], "checkpoint": checkpoint["label"],
                "new_accepted_ids_and_keys": [
                    {key: record[key] for key in ("record_id", "order_key")}
                    for record in introduced
                ],
                "unplaceable_canon_ids": [
                    record["record_id"] for record in accepted
                    if record["order_key"] is not None
                    and re.fullmatch(r"s\d+", record["order_key"]) is None
                ],
            })
            known.update(record["record_id"] for record in accepted)
    evidence["checkpoint_positions"] = positioned
    save(HERE / "evidence.json", evidence)


if __name__ == "__main__":
    audit()
