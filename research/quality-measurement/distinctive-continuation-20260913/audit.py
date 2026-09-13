"""Rebuild text-free engineering and continuation records from retained receipts."""

from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

from run import HERE, PARENT, PARENT_SHA, ROOT, RUN, failed_usage, hashes, load, save, sha


def events(raw):
    try:
        result = [json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()]
        return result if all(isinstance(row, dict) for row in result) else []
    except ValueError:
        # A partial or malformed receipt fails usage/session controls below.
        return []


def commands(raw):
    return [
        row for line in raw.get("commands_jsonl", "").splitlines()
        if (row := json.loads(line)).get("phase") == "result"
    ]


def arguments(row):
    value = row.get("arguments", [])
    value = value.get("arguments", []) if isinstance(value, dict) else value
    return value if isinstance(value, list) and all(isinstance(v, str) for v in value) else []


def permitted(tool, mode):
    if mode == "bridge":
        return tool == {
            "type": "mcp_tool_call", "server": "litharness", "tool": "litharness_command",
        }
    return mode == "search" and tool["type"] == "web_search"


def engineering():
    rows = []
    previous = ROOT / "runs/continuation-baseline-20260910"
    for path in sorted(previous.glob("book-*/transport/*.json")):
        raw = load(path)
        if raw.get("mode") != "bridge":
            continue
        before = after = 0
        counts = collections.Counter()
        for result in commands(raw):
            row = {key: value for key, value in result.items() if key != "phase"}
            counts[" ".join(arguments(row)[:2])] += 1
            failed = bool(row.get("error")) or row.get("returncode") != 0
            visible = row if failed else {
                key: value for key, value in row.items() if key not in {"arguments", "argv"}
            }
            before += len(json.dumps(row, ensure_ascii=False).encode())
            after += len(json.dumps(visible, ensure_ascii=False).encode())
        rows.append({
            "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
            "usage": [e.get("usage") for e in events(raw) if e.get("type") == "turn.completed"],
            "commands": dict(counts), "original_result_bytes": before,
            "compact_success_result_bytes": after,
        })
    save(HERE / "engineering.json", rows)


def stage_trace():
    """Post-run locators, not registered quality measures or production feedback."""
    parent = load(PARENT)["result"]["parsed"]
    concept_path = RUN / "book-1/concept.json"
    concept = load(concept_path)
    seed_path = RUN / "book-1/calls/013.json"
    seed = load(seed_path)
    initial_summary = next(
        command for command in commands(seed["result"]["raw"])
        if arguments(command) == ["world", "summary"]
    )
    selected = []
    for command in commands(seed["result"]["raw"]):
        args = arguments(command)
        if args[:2] != ["world", "declare-batch"]:
            continue
        for index, record in enumerate(json.loads(args[args.index("--records") + 1])):
            if record["subject"] in {"mara", "license_fork", "wren_initial_license"}:
                selected.append({
                    "bridge_call": command["call"], "batch_index_zero_based": index,
                    "subject": record["subject"], "predicate": record["predicate"],
                    "record_sha256": hashlib.sha256(json.dumps(
                        record, ensure_ascii=False, sort_keys=True,
                    ).encode()).hexdigest(),
                })
    presence = []
    for path in sorted((RUN / "book-1/calls").glob("*.json")):
        row = load(path)
        raw = row["result"]["raw"]
        presence.append({
            "call": path.stem, "profile": row["request"]["profile"], "sha256": sha(path),
            "mara_request_mentions": len(re.findall(
                r"\bmara\b", raw["prompt"] + raw["system"], re.I,
            )),
            "mara_final_mentions": len(re.findall(r"\bmara\b", row["result"]["text"], re.I)),
            "mara_tool_trace_mentions": len(re.findall(
                r"\bmara\b", raw.get("commands_jsonl", ""), re.I,
            )),
        })
    save(HERE / "stage-trace.json", {
        "status": "observed", "analysis": "post-run descriptive locators",
        "parent_sha256": sha(PARENT), "concept_sha256": sha(concept_path),
        "seed_receipt_sha256": sha(seed_path),
        "initial_world_record_count": json.loads(initial_summary["stdout"])["records"],
        "outline_receipt_sha256": sha(RUN / "book-1/calls/014.json"),
        "stored_opening_matches_parent": concept["first_arc"]["opens"] == parent["opening"],
        "stored_discovery_matches_parent_fields": all(
            concept["discovery"][key] == value for key, value in parent.items()
        ),
        "parent_mara_mentions": len(re.findall(r"\bmara\b", json.dumps(parent), re.I)),
        "parent_home_mentions": len(re.findall(r"\bhome\b", json.dumps(parent), re.I)),
        "seed_record_locators": selected, "call_presence": presence,
        "limitation": "Word matches locate text; they are not measures of creativity or causes.",
    })


def audit():
    progress = load(RUN / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Wait for generation to finish")
    manifest = load(RUN / "manifest.json")
    registration = load(HERE / "registration.json")
    controls = {
        "manifest": sha(RUN / "manifest.json") == registration["manifest_sha256"],
        "source": hashes(RUN / "source") == manifest["source_sha256"],
        "parent": sha(PARENT) == PARENT_SHA == registration["parent_sha256"],
        "runner": all(
            sha(HERE / name) == digest for name, digest in manifest["experiment_sha256"].items()
        ),
    }
    calls, sessions, tokens, profiles = [], [], 0, {}
    for path in sorted(RUN.glob("book-*/calls/*.json")):
        row = load(path)
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        usage = failed_usage(raw)
        if usage is not None:
            tokens += usage
        native = events(raw)
        ids = [e["thread_id"] for e in native if e.get("type") == "thread.started"]
        sessions += ids
        command_counts = collections.Counter(" ".join(arguments(c)[:2]) for c in commands(raw))
        stdout_bytes = collections.Counter()
        for command in commands(raw):
            stdout_bytes[" ".join(arguments(command)[:2])] += len(
                command.get("stdout", "").encode()
            )
        profile = row["request"]["profile"]
        entry = profiles.setdefault(profile, {"calls": 0, "tokens": 0})
        entry["calls"] += 1
        entry["tokens"] += usage or 0
        record = {
            "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
            "status": row["status"], "profile": profile, "tokens": usage,
            "returned_usage": row.get("result", {}).get("usage"),
            "native_session_ids": ids, "mode": raw.get("mode"),
            "tool_commands": dict(command_counts),
            "tool_stdout_bytes": dict(stdout_bytes),
            "native_tools": [
                {key: item.get(key) for key in ("type", "server", "tool")}
                for e in native if e.get("type") == "item.completed"
                and (item := e.get("item", {})).get("type") not in {"agent_message", "reasoning"}
            ],
        }
        if row.get("error"):
            record["error"] = row["error"]
        calls.append(record)
    controls.update(
        accounted_attempts=len(calls) == progress["calls"],
        known_usage=all(row["tokens"] is not None for row in calls),
        accounted_tokens=tokens == progress["tokens"],
        fresh_sessions=len(sessions) == len(calls) == len(set(sessions)),
        native_containment=all(
            permitted(tool, row["mode"]) for row in calls for tool in row["native_tools"]
        ),
    )
    checkpoints, previous = [], {}
    for directory in [*sorted((RUN / "book-1").glob("checkpoint-*")), RUN / "book-1/final"]:
        if not (directory / "chapter-hashes.json").exists():
            continue
        current = load(directory / "chapter-hashes.json")
        verification = load(directory / "verify.txt")
        status = load(directory / "audit.txt")
        unchanged = all(current.get(name) == digest for name, digest in previous.items())
        controls[f"{directory.name}_preserved"] = unchanged
        controls[f"{directory.name}_attributed"] = not verification["unattributed"]
        checkpoints.append({
            "label": directory.name, "chapters": status["chapters_drafted"],
            "hashes": current, "verification": verification,
            "audit_sha256": sha(directory / "audit.txt"),
            "verify_sha256": sha(directory / "verify.txt"),
        })
        previous = current
    exported = {
        path.name: sha(path)
        for path in (RUN / "book-1/library").glob("*/chapters/Chapter*.txt")
    }
    controls["current_exports_match_checkpoint"] = exported == previous
    controls["three_checkpoint_sequence"] = [
        (row["label"], row["chapters"]) for row in checkpoints
    ] == [("checkpoint-1", 1), ("checkpoint-2", 2), ("checkpoint-3", 3), ("final", 3)]
    output = {
        "schema": "litharness.distinctive-continuation-evidence.v1",
        "registration_sha256": sha(HERE / "registration.json"),
        "progress_sha256": sha(RUN / "progress.json"),
        "audit_sha256": sha(Path(__file__)), "controls": controls,
        "all_controls_pass": all(controls.values()), "calls": calls, "profiles": profiles,
        "native_tokens": tokens, "checkpoints": checkpoints,
        "milestone_completed": bool(progress["books"])
        and progress["books"][0]["status"] == "completed"
        and progress["books"][0]["chapters"] == 3,
    }
    save(HERE / "evidence.json", output)
    print(json.dumps({key: output[key] for key in (
        "all_controls_pass", "milestone_completed", "native_tokens", "profiles",
    )}, indent=2))


if __name__ == "__main__":
    engineering()
    audit()
    stage_trace()
