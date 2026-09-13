"""Verify actual native-visible replies and report both fixed format pairs."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import runpy
from datetime import datetime
from pathlib import Path

RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, ORDER, BASE, load, save, sha = (
    RUNNER[k] for k in ("HERE", "ROOT", "RUN", "ORDER", "BASE", "load", "save", "sha")
)


def visible_replies(events):
    replies = {}
    for event in events:
        item = event.get("item", {})
        if event.get("type") != "item.completed" or item.get("type") != "mcp_tool_call":
            continue
        for content in (item.get("result") or {}).get("content", []):
            if content.get("type") != "text":
                continue
            try:
                payload = json.loads(content["text"])
            except ValueError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("call"), int):
                if payload["call"] in replies:
                    raise ValueError("Duplicate native-visible command identity")
                replies[payload["call"]] = payload
    return replies


def reply_matches(row, visible, compact):
    from litharness.providers.codex_tools import compact_json_stdout

    original = row.get("stdout", "")
    successful = row.get("returncode") == 0 and not row.get("error")
    expected = compact_json_stdout(original) if compact and successful else original
    recorded = row.get("model_stdout", original)
    expected_keys = set(row) - {"phase", "model_stdout"}
    if successful:
        expected_keys -= {"arguments", "argv"}
    return (visible is not None and set(visible) == expected_keys
            and recorded == expected and visible.get("stdout") == expected
            and all(visible[key] == row[key] for key in expected_keys - {"stdout"}))


def token_difference(compact, verbatim):
    return compact - verbatim if compact is not None and verbatim is not None else None


def main():
    progress = load(RUN / "progress.json")
    if progress["status"] == "running":
        raise RuntimeError("Wait for the live comparison to finish")
    manifest = load(RUN / "manifest.json")
    BASE.validate(manifest)
    from litharness.adapters.sqlite_store import SqliteStore

    calls, cells, sessions = [], [], []
    for name in ORDER:
        folder = RUN / name
        compact = RUNNER["compact_for_case"](name)
        for path in sorted((folder / "calls").glob("*.json")):
            row = load(path)
            raw = row.get("result", {}).get("raw", row.get("transport", {}))
            events = [json.loads(line) for line in raw.get("stdout", "").splitlines()
                      if line.strip()]
            views = visible_replies(events)
            command_rows = [json.loads(line) for line in raw.get("commands_jsonl", "").splitlines()
                            if line.strip()]
            commands = [c for c in command_rows if c.get("phase") == "result"]
            native_sessions = [e["thread_id"] for e in events if e.get("type") == "thread.started"]
            sessions.extend(native_sessions)
            usages = [e["usage"] for e in events if e.get("type") == "turn.completed"]
            usage = usages[0] if len(usages) == 1 else {}
            expected_format = "compact-json-whitespace.v1" if compact else "verbatim"
            tools = [e["item"] for e in events if e.get("type") == "item.completed"
                     and e.get("item", {}).get("type") not in {"reasoning", "agent_message"}]
            details = [{"call": c["call"], "returncode": c.get("returncode"),
                "error_kind": c.get("error_kind"),
                "raw_stdout_bytes": len(c.get("stdout", "").encode("utf-8")),
                "model_stdout_bytes": len(views.get(c["call"], {}).get("stdout", "").encode()),
                "visible_matches_expected": reply_matches(c, views.get(c["call"]), compact)}
                for c in commands]
            calls.append({"cell": name, "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path), "profile": row["request"]["profile"],
                "status": row["status"], "native_usage": usage,
                "native_tokens": BASE.native_usage(raw), "session_ids": native_sessions,
                "elapsed_seconds": (datetime.fromisoformat(row["finished_at"])
                                    - datetime.fromisoformat(row["started_at"])).total_seconds(),
                "format": raw.get("tool_reply_format"),
                "format_matches": raw.get("mode") != "bridge"
                                  or raw.get("tool_reply_format") == expected_format,
                "commands_contained": all(t.get("type") == "mcp_tool_call"
                    and t.get("server") == "litharness" and t.get("tool") == "litharness_command"
                    for t in tools),
                "visible_command_count": len(views), "command_count": len(commands),
                "raw_stdout_bytes": sum(c["raw_stdout_bytes"] for c in details),
                "model_stdout_bytes": sum(c["model_stdout_bytes"] for c in details),
                "replies_match": len(views) == len(commands)
                                 and all(c["visible_matches_expected"] for c in details),
                "commands": details})
        database = folder / "serial.db"
        before = sha(database)
        initial = {r["record_id"] for r in load(folder / "initial-world.json")}
        with SqliteStore.open_read_only(database) as store:
            [(book, branch, _)] = store.branches()
            wants = [r for r in store.state_records(book, branch)
                     if r.predicate == "wants" and r.record_id not in initial]
        save(folder / "wants.private.json", [dataclasses.asdict(r) for r in wants])
        cell = {"name": name, "completed": name in progress["assignments"],
                "request_sha256": sha(folder / "request.json"), "database_sha256": before,
                "database_unchanged": sha(database) == before,
                "wants": [{"subject": r.subject, "record_id": r.record_id,
                           "value_sha256": hashlib.sha256(str(r.value).encode()).hexdigest()}
                          for r in wants]}
        check = folder / "result-check.json"
        if check.exists():
            checked = load(check)["result"]
            cell["check"] = {"ok": checked["ok"], "complaints": len(checked["complaints"]),
                             "unplaceable": len(checked["unplaceable"])}
            cell["check_sha256"] = sha(check)
        cells.append(cell)
    pairs = []
    for suffix in ("conditional", "adopted"):
        pair = {prefix: next((c for c in calls if c["cell"] == f"{prefix}-{suffix}"
                            and c["profile"].startswith("architect.grow")), None)
                for prefix in ("verbatim", "compact")}
        if all(pair.values()):
            pairs.append({"source": suffix,
                **{key: {k: value[k] for k in ("native_tokens", "native_usage", "elapsed_seconds",
                         "command_count", "raw_stdout_bytes", "model_stdout_bytes")}
                   for key, value in pair.items()},
                "compact_minus_verbatim_tokens": token_difference(
                    pair["compact"]["native_tokens"], pair["verbatim"]["native_tokens"])})
    result = {"schema": "litharness.compact-json-comparison.v1", "status": progress["status"],
        "fatal": progress["fatal"], "manifest_sha256": sha(RUN / "manifest.json"),
        "progress_sha256": sha(RUN / "progress.json"), "calls": calls, "cells": cells,
        "pairs": pairs, "native_tokens": sum(c["native_tokens"] or 0 for c in calls),
        "native_session_count": len(sessions), "distinct_native_sessions": len(set(sessions)),
        "protected_inputs_unchanged": all(sha(ROOT / p) == digest
                                          for p, digest in manifest["protected_inputs"].items())}
    result["usage_matches_progress"] = result["native_tokens"] == progress["tokens"]
    save(HERE / "evidence.json", result)
    print(json.dumps({k: result[k] for k in ("status", "fatal", "native_tokens",
                     "usage_matches_progress", "protected_inputs_unchanged", "pairs")}, indent=2))


if __name__ == "__main__":
    main()
