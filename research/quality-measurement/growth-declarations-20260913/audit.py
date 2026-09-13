"""Derive typed boundaries, receipt provenance and counterfactual arithmetic without calls."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import runpy
from pathlib import Path

_RUN = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, ORDER, load, save, sha = (
    _RUN[k] for k in ("HERE", "ROOT", "RUN", "ORDER", "load", "save", "sha")
)


def investment_control(system, ability):
    """Counterfactual held-at-one sheet with exactly enough stock for two purchases."""
    from litharness.domain import gamesystem as gs

    prices = dict(ability.price)
    sheet = dataclasses.replace(gs.starting_sheet(system, "counterfactual"), magnitudes=tuple(
        (other.ability_id, prices.get(other.ability_id, 0) * 2 if other.is_stock else 1)
        for other in system.abilities
    ))
    original = sheet
    steps = []
    for index in (1, 2):
        offered = any(move.kind is gs.AdvanceKind.DEEPEN and move.ability_id == ability.ability_id
                      for move in gs.legal_moves(sheet))
        try:
            advanced = gs.deepen(sheet, ability.ability_id, at=f"s{index}")
        except gs.IllegalAdvance:
            steps.append({"offered": offered, "direct_execution": False})
            break
        sheet = advanced.sheet
        steps.append({"offered": offered, "direct_execution": True,
                      "after": dict(sheet.magnitudes),
                      "record_ids": [r.record_id for r in advanced.records]})
    return {"counterfactual": True, "before": dict(original.magnitudes), "steps": steps}


def main():
    progress = load(RUN / "progress.json")
    if progress["status"] == "running":
        raise RuntimeError("Wait for the live experiment to finish")
    manifest = load(RUN / "manifest.json")
    _RUN["validate"](manifest)
    os.environ["LITHARNESS_ENV"] = "test"
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import gamesystem as gs

    result = {"schema": "litharness.growth-declarations-evidence.v1",
              "manifest_sha256": sha(RUN / "manifest.json"),
              "progress_sha256": sha(RUN / "progress.json"),
              "status": progress["status"], "fatal": progress["fatal"],
              "cells": [], "calls": [], "total_native_tokens": 0}
    sessions = []
    for name in ORDER:
        folder = RUN / name
        database = folder / "serial.db"
        before = sha(database)
        with SqliteStore.open_read_only(database) as store:
            [(book, branch, _)] = store.branches()
            records = store.state_records(book, branch)
        completion, reasons = gs.completion_records(records)
        systems = gs.systems_of([*records, *completion])
        initial = {r["record_id"] for r in load(folder / "initial-world.json")}
        wants = [r for r in records if r.predicate == "wants" and r.record_id not in initial]
        cell = {"name": name, "completed": name in progress["assignments"],
                "database_sha256": before, "request_sha256": sha(folder / "request.json"),
                "completion_reasons": list(reasons), "systems": [],
                "wants": [{"record_id": r.record_id, "subject": r.subject,
                           "value_sha256": hashlib.sha256(
                               str(r.value).encode()).hexdigest(),
                           "authority": r.authority.value} for r in wants]}
        save(folder / "wants.private.json", [r.to_jsonable() if hasattr(r, "to_jsonable")
             else dataclasses.asdict(r) for r in wants])
        for system in systems:
            wrong = gs.check_draw(system, drawn=name.endswith("-seed"))
            cell["systems"].append({
                "system_id": system.system_id, "digest": system.digest,
                "default_maximum": system.scale.maximum, "rank_ids": list(system.rank_ids),
                "complaints": list(wrong),
                "abilities": [{"id": a.ability_id, "label": a.name,
                    "growth_limit": a.growth_limit,
                    "effective_limit": system.depth_limit(a.ability_id),
                    "per_rung": a.per_rung, "price": list(a.price),
                    "needs": [dataclasses.asdict(n) for n in a.needs],
                    "control": investment_control(system, a) if not wrong else None}
                    for a in system.abilities],
            })
        for label in ("world", "check", "verify"):
            path = folder / f"result-{label}.json"
            if path.exists():
                cell[f"{label}_sha256"] = sha(path)
                if label == "check":
                    # This raw check remains private; only its arithmetic status/counts travel.
                    checked = load(path)["result"]
                    cell["check"] = {"ok": checked["ok"], "complaints": len(checked["complaints"]),
                                     "would_not_finish": len(checked["would_not_finish"]),
                                     "unplaceable": len(checked["unplaceable"])}
        if sha(database) != before:
            raise RuntimeError("Audit changed a fixture store")
        cell["database_unchanged"] = True
        result["cells"].append(cell)
    for path in sorted(RUN.glob("*/calls/*.json")):
        row = load(path)
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        events = [json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()]
        native_sessions = [e["thread_id"] for e in events if e.get("type") == "thread.started"]
        sessions.extend(native_sessions)
        tools = [e["item"] for e in events if e.get("type") == "item.completed"
                 and e.get("item", {}).get("type") not in {"reasoning", "agent_message"}]
        contained = all(t.get("type") == "mcp_tool_call" and t.get("server") == "litharness"
                        and t.get("tool") == "litharness_command" for t in tools)
        usage = _RUN["native_usage"](raw)
        result["total_native_tokens"] += usage or 0
        result["calls"].append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
             "profile": row["request"]["profile"], "status": row["status"],
             "native_tokens": usage, "mode": raw.get("mode"), "session_ids": native_sessions,
             "command_count": len(tools), "commands_contained": contained})
    result["session_count"] = len(sessions)
    result["distinct_session_count"] = len(set(sessions))
    result["usage_matches_progress"] = result["total_native_tokens"] == progress["tokens"]
    result["protected_inputs_unchanged"] = all(sha(ROOT / path) == digest
        for path, digest in manifest["protected_inputs"].items())
    save(HERE / "evidence.json", result)
    print(json.dumps({key: result[key] for key in ("status", "fatal", "total_native_tokens",
                     "session_count", "usage_matches_progress", "protected_inputs_unchanged")},
                     indent=2))


if __name__ == "__main__":
    main()
