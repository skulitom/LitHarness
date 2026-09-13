"""Rebuild source-boundary and retrieval locators without committing generated text."""

from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from run import CONTROL, HERE, PARENT, PARENT_SHA, ROOT, RUN, failed_usage, hashes, load, save, sha


def events(raw):
    try:
        values = [json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()]
        return values if all(isinstance(row, dict) for row in values) else []
    except ValueError:
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


def audit():
    progress, manifest = load(RUN / "progress.json"), load(RUN / "manifest.json")
    if progress["status"] != "finished":
        raise RuntimeError("Wait for generation to finish")
    registration = load(HERE / "registration.json")
    controls = {
        "manifest": sha(RUN / "manifest.json") == registration["manifest_sha256"],
        "source": hashes(RUN / "source") == manifest["source_sha256"],
        "parent": sha(PARENT) == PARENT_SHA == registration["parent_sha256"],
        "contrast": sha(CONTROL) == registration["control_sha256"],
        "runner": all(
            sha(HERE / name) == digest for name, digest in manifest["experiment_sha256"].items()
        ),
        "prior_book_unchanged": all(
            sha(ROOT / path) == digest for path, digest in manifest["protected_files"].items()
        ),
    }
    calls, sessions, profiles, tokens = [], [], {}, 0
    for path in sorted(RUN.glob("book-*/calls/*.json")):
        row = load(path)
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        native = events(raw)
        usage = failed_usage(raw)
        tokens += usage or 0
        ids = [event["thread_id"] for event in native if event.get("type") == "thread.started"]
        sessions += ids
        profile = row["request"]["profile"]
        aggregate = profiles.setdefault(profile, {"calls": 0, "tokens": 0})
        aggregate["calls"] += 1
        aggregate["tokens"] += usage or 0
        tools = [
            {key: item.get(key) for key in ("type", "server", "tool")}
            for event in native if event.get("type") == "item.completed"
            and (item := event.get("item", {})).get("type") not in {"agent_message", "reasoning"}
        ]
        reads, declarations = [], []
        counts = collections.Counter()
        for number, command in enumerate(commands(raw), 1):
            args = arguments(command)
            counts[" ".join(args[:2])] += 1
            if args[:2] == ["world", "show"]:
                stdout = command.get("stdout", "").encode()
                reads.append({
                    "bridge_call": number, "arguments": args, "bytes": len(stdout),
                    "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                    "scoped": any(
                        flag in args for flag in ("--subject", "--subjects", "--predicate")
                    ),
                })
            if args[:2] == ["world", "declare-batch"] and "--records" in args:
                try:
                    records = json.loads(args[args.index("--records") + 1])
                except (ValueError, IndexError):
                    continue  # The unparseable attempt remains in its full command receipt.
                if not isinstance(records, list):
                    continue
                for index, record in enumerate(records):
                    if not isinstance(record, dict):
                        continue
                    declarations.append({
                        "bridge_call": number, "batch_index": index,
                        "subject": record.get("subject"), "predicate": record.get("predicate"),
                        "record_sha256": hashlib.sha256(json.dumps(
                            record, ensure_ascii=False, sort_keys=True,
                        ).encode()).hexdigest(),
                    })
        calls.append({
            "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
            "status": row["status"], "profile": profile, "tokens": usage,
            "returned_usage": row.get("result", {}).get("usage"), "sessions": ids,
            "mode": raw.get("mode"), "native_tools": tools, "tool_counts": dict(counts),
            "show_reads": reads, "declarations": declarations,
            "error": row.get("error"),
        })
    controls.update(
        attempts=len(calls) == progress["calls"],
        known_usage=all(call["tokens"] is not None for call in calls),
        tokens=tokens == progress["tokens"],
        fresh_sessions=len(sessions) == len(calls) == len(set(sessions)),
        native_containment=all(
            call["mode"] == "bridge" and tool == {
                "type": "mcp_tool_call", "server": "litharness", "tool": "litharness_command",
            }
            for call in calls for tool in call["native_tools"]
        ),
    )
    books = []
    for index, book in enumerate(progress["books"], 1):
        directory = RUN / book["id"]
        concept_path = directory / "concept.json"
        source = load(PARENT)["result"]["parsed"] if index == 1 else load(CONTROL)
        if concept_path.exists():
            concept = load(concept_path)
            controls[f"{book['id']}_source_preserved"] = all(
                concept["discovery"][key] == value for key, value in source.items()
            ) and concept["first_arc"]["opens"] == source["opening"]
        checkpoints = []
        for label in ("empty", "seeded", "checkpoint-1", "final"):
            checkpoint = directory / label
            if not (checkpoint / "verify.txt").exists():
                continue
            verification = load(checkpoint / "verify.txt")
            world = load(checkpoint / "world.txt")
            controls[f"{book['id']}_{label}_attributed"] = not verification["unattributed"]
            if label == "empty":
                controls[f"{book['id']}_initially_empty"] = not world
            checkpoints.append({
                "label": label, "verification": verification, "world_records": len(world),
                "world_sha256": sha(checkpoint / "world.txt"),
                "chapter_hashes": load(checkpoint / "chapter-hashes.json"),
            })
        books.append({
            "id": book["id"], "status": book["status"], "chapters": book["chapters"],
            "concept_sha256": sha(concept_path) if concept_path.exists() else None,
            "checkpoints": checkpoints, "reason": book.get("reason"),
        })
    completed = len(books) == 2 and all(book["status"] == "completed" for book in books)
    save(HERE / "evidence.json", {
        "schema": "litharness.world-boundary-evidence.v1", "status": "observed",
        "registration_sha256": sha(HERE / "registration.json"),
        "progress_sha256": sha(RUN / "progress.json"), "audit_sha256": sha(Path(__file__)),
        "controls": controls, "all_provenance_controls_pass": all(controls.values()),
        "assigned_execution_completed": completed, "native_tokens": tokens,
        "profiles": profiles, "calls": calls, "books": books,
        "limitation": "Execution checks do not establish semantic preservation or quality.",
    })
    print(json.dumps(
        {"completed": completed, "controls": controls, "profiles": profiles}, indent=2,
    ))


if __name__ == "__main__":
    audit()
