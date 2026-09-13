"""Derive provenance, output locators and per-tool costs from the retained first outputs."""

from __future__ import annotations

import collections
import json
import os
import runpy
from pathlib import Path

_RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, PRIOR, load, save, sha, native_usage = (
    _RUNNER[key] for key in ("HERE", "ROOT", "RUN", "PRIOR", "load", "save", "sha", "native_usage")
)


def main():
    _RUNNER["lock"]()
    progress = load(RUN / "progress.json")
    if progress["status"] == "running":
        raise RuntimeError("Wait for the live run to finish")
    manifest = load(RUN / "manifest.json")
    _RUNNER["validate"](manifest)
    os.environ["LITHARNESS_ENV"] = "test"
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.text import content_hash

    reader_source_checks = []
    for relative in manifest["inputs"]:
        if not relative.endswith("battery.private.json"):
            continue
        packet = ROOT / relative
        census = load(packet)["census"]
        database = packet.parents[2] / "serial.db"
        before = sha(database)
        with SqliteStore.open_read_only(database) as store:
            revision = store.load_revision(census["revision_id"])
        spans = [span for candidate in census["candidates"] for span in candidate["evidence"]]
        valid = all(
            content_hash(revision.node(span["logical_id"]).content or "") == span["content_hash"]
            for span in spans
        )
        if not valid or sha(database) != before:
            raise RuntimeError("Reader construction source differs from its frozen full-scene key")
        reader_source_checks.append(
            {
                "packet": relative,
                "spans": len(spans),
                "whole_scene_hashes_match": valid,
                "database_sha256": before,
            }
        )
    # Rebuild final attribution and chapter preservation even after a stopped assignment.
    old_chapters = load(RUN / "continuation/initial/chapter-hashes.json")
    final_hashes, final = _RUNNER["checkpoint"](RUN / "continuation", "audit-final", old_chapters)
    calls, sessions, profiles, total = [], [], {}, 0
    for path in sorted(RUN.glob("*/calls/*.json")):
        row = load(path)
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        events = [json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()]
        ids = [event["thread_id"] for event in events if event.get("type") == "thread.started"]
        sessions.extend(ids)
        usage = native_usage(raw)
        total += usage or 0
        profile = row["request"]["profile"]
        aggregate = profiles.setdefault(profile, {"calls": 0, "tokens": 0})
        aggregate["calls"] += 1
        aggregate["tokens"] += usage or 0
        native_tools = [
            event["item"]
            for event in events
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") not in {"reasoning", "agent_message"}
        ]
        safe = all(
            item.get("type") == "mcp_tool_call"
            and item.get("server") == "litharness"
            and item.get("tool") == "litharness_command"
            and raw.get("mode") == "bridge"
            for item in native_tools
        )
        tools = collections.defaultdict(lambda: {"calls": 0, "stdout_bytes": 0})
        declarations = []
        for number, line in enumerate(raw.get("commands_jsonl", "").splitlines(), 1):
            command = json.loads(line)
            if command.get("phase") != "result":
                continue
            args = command.get("arguments", [])
            if isinstance(args, dict):
                args = args.get("arguments", [])
            verb = " ".join(args[:2])
            tools[verb]["calls"] += 1
            tools[verb]["stdout_bytes"] += len(command.get("stdout", "").encode("utf-8"))
            if args[:2] == ["world", "declare-batch"] and "--records" in args:
                records = json.loads(args[args.index("--records") + 1])
                for index, record in enumerate(records):
                    if record.get("predicate") == "wants":
                        declarations.append(
                            {
                                "command_jsonl_line": number,
                                "batch_index": index,
                                "subject": record.get("subject"),
                                "order_key": record.get("order_key"),
                                "value_sha256": _RUNNER["hashlib"]
                                .sha256(str(record.get("value")).encode("utf-8"))
                                .hexdigest(),
                            }
                        )
        completed_usage = [
            event["usage"] for event in events if event.get("type") == "turn.completed"
        ]
        calls.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "status": row["status"],
                "profile": profile,
                "tokens": usage,
                "reported_usage": completed_usage,
                "sessions": ids,
                "native_containment": safe,
                "tool_payloads": dict(tools),
                "goal_declaration_locators": declarations,
                "error": row.get("error"),
            }
        )
    goals = []
    for name in manifest["order"]:
        folder = RUN / name
        original_ids = {row["record_id"] for row in load(folder / "initial-world.json")}
        path = folder / "result-world.json"
        if not path.exists():
            goals.append({"case": name, "completed": False})
            continue
        rows = [
            row
            for row in load(path)
            if row["record_id"] not in original_ids and row["predicate"] == "wants"
        ]
        goals.append(
            {
                "case": name,
                "completed": True,
                "world_sha256": sha(path),
                "goals": [
                    {key: row[key] for key in ("record_id", "subject", "order_key", "canon")}
                    for row in rows
                ],
            }
        )
    snapshots = []
    for label in ("initial", "chapter-4", "chapter-5", "chapter-6", "audit-final"):
        path = RUN / "continuation" / label / "world.json"
        if not path.exists():
            continue
        world = load(path)
        selected = [
            row
            for row in world
            if row["predicate"]
            in {"status_snapshot", "can_do", "stands_at", "requires", "costs", "per_rung"}
        ]
        snapshots.append(
            {
                "checkpoint": label,
                "world_sha256": sha(path),
                "records": [
                    {
                        key: row[key]
                        for key in ("record_id", "subject", "predicate", "order_key", "canon")
                    }
                    for row in selected
                ],
            }
        )
    controls = {
        "registered_manifest": sha(RUN / "manifest.json")
        == load(HERE / "registration.json")["manifest_sha256"],
        "source_scripts_inputs_unchanged": True,  # validate() above refuses any mismatch.
        "all_usage_known": all(call["tokens"] is not None for call in calls),
        "usage_matches_progress": total == progress["tokens"],
        "calls_match_progress": len(calls) == progress["calls"],
        "independent_native_sessions": len(sessions) == len(calls) == len(set(sessions)),
        "native_containment": all(call["native_containment"] for call in calls),
        "prior_chapters_preserved": all(
            final_hashes.get(name) == digest for name, digest in old_chapters.items()
        ),
        "revision_attribution": not final["verify"]["unattributed"],
        "reader_full_scene_inputs_verified": all(
            row["whole_scene_hashes_match"] for row in reader_source_checks
        ),
    }
    result = {
        "schema": "litharness.next-priorities-evidence.v1",
        "status": "observed",
        "auditor_sha256": sha(Path(__file__)),
        "registration_sha256": sha(HERE / "registration.json"),
        "progress_sha256": sha(RUN / "progress.json"),
        "progress": progress,
        "controls": controls,
        "all_provenance_controls_pass": all(controls.values()),
        "native_tokens": total,
        "profiles": profiles,
        "calls": calls,
        "goal_cases": goals,
        "continuation_chapters": final["audit"]["chapters_drafted"],
        "chapter_hashes": final_hashes,
        "world_checkpoints": snapshots,
        "reader_source_checks": reader_source_checks,
        "limitation": (
            "Provenance checks and source locators do not score semantic preservation "
            "or literary quality."
        ),
    }
    save(HERE / "evidence.json", result)
    print(
        json.dumps(
            {
                "controls": controls,
                "profiles": profiles,
                "continuation_chapters": result["continuation_chapters"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
