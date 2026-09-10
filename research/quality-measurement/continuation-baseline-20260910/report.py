"""Derive a prose-free baseline report from retained run and checkpoint artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/continuation-baseline-20260910"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def transport_summary(path: Path) -> dict:
    raw = read(path)
    events = raw.get("events") or [
        json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()
    ]
    completed = [e for e in events if e.get("type") == "turn.completed"]
    usage = completed[0].get("usage", {}) if len(completed) == 1 else {}
    inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
    total = (
        inputs + outputs
        if type(inputs) is int and type(outputs) is int and min(inputs, outputs) >= 0
        else None
    )
    commands = [json.loads(line) for line in raw.get("commands_jsonl", "").splitlines()]
    requests = [row for row in commands if row.get("phase") == "request"]
    returned = [row for row in commands if row.get("phase") == "result"]
    unexpected = sorted(
        {
            (item.get("server", ""), item.get("tool", ""))
            for event in events
            if (item := event.get("item", {})).get("type") == "mcp_tool_call"
            and (item.get("server"), item.get("tool")) != ("litharness", "litharness_command")
        }
    )
    return {
        "file": path.name,
        "sha256": sha(path),
        "guard_rejected": bool(raw.get("failure")),
        "native_reported_tokens": total,
        "wall_ms": raw.get("wall_ms"),
        "bridge_requests": len(requests),
        "bridge_results": len(returned),
        "bridge_commands": dict(
            Counter(
                " ".join(r["arguments"][:2])
                if isinstance(r.get("arguments"), list)
                and all(isinstance(a, str) for a in r["arguments"][:2])
                else "invalid_arguments"
                for r in returned
            )
        ),
        "bridge_stdout_characters": sum(len(r.get("stdout", "")) for r in returned),
        "unexpected_mcp_tools": unexpected,
    }


def main() -> None:
    progress = read(RUN / "progress.json")
    if progress["status"] != "finished":
        raise RuntimeError("Baseline still running")
    manifest = read(RUN / "manifest.json")
    report = {
        "schema": "litharness.continuation-baseline-result.v1",
        "registration_sha256": sha(HERE / "PREREG.md"),
        "runner_sha256": sha(HERE / "run.py"),
        "derivation_sha256": sha(Path(__file__)),
        "source_manifest_sha256": sha(RUN / "manifest.json"),
        "progress_sha256": sha(RUN / "progress.json"),
        "frozen_source_intact": all(
            sha(RUN / "source" / name) == digest
            for name, digest in manifest["source_sha256"].items()
        ),
        "registered_files_intact": all(
            sha(HERE / name) == digest for name, digest in manifest["experiment_sha256"].items()
        ),
        "started_at": progress["started_at"],
        "finished_at": progress["finished_at"],
        "elapsed_seconds": progress["elapsed_seconds"],
        "native_attempts": progress["calls"],
        "reported_tokens": progress["tokens"],
        "stopped_globally": progress["fatal"] is not None,
        "global_stop": (
            progress["fatal"]
            if progress["fatal"]
            in (None, "aggregate bound reached", "three-hour new-call bound reached")
            else "other failure; inspect ignored progress receipt"
        ),
        "books": [],
        "limitations": [
            "Three-book engineering pilot; no estimate of literary quality or improvement.",
            "Native model identity is requested, not independently reported by the backend.",
            "All prose, databases and complete transport receipts remain in ignored runs/.",
            "Token accounting covers returned usage; an in-flight call may exceed a bound.",
            "Reported totals include cached input and reasoning under the production "
            "Usage contract.",
            "The frozen progress ledger omits usage from a provider-rejected response; "
            "native traces are reported separately.",
            "Listing observations are inert and are not reader-validity evidence.",
        ],
    }
    for index in range(1, 4):
        directory = RUN / f"book-{index}"
        item = next((b for b in progress["books"] if b["id"] == f"book-{index}"), None)
        if item is None:
            report["books"].append({"id": f"book-{index}", "status": "not_started"})
            continue
        entry = {name: item[name] for name in ("id", "status", "calls", "tokens", "chapters")}
        report["books"].append(entry)
        if "reason" in item:
            entry["stop_reason_sha256"] = hashlib.sha256(item["reason"].encode()).hexdigest()
        if (directory / "listing.json").is_file():
            entry["title"] = read(directory / "listing.json")["title"]
        calls = [read(path) for path in sorted((directory / "calls").glob("*.json"))]
        entry["receipt_statuses"] = dict(Counter(c["status"] for c in calls))
        entry["profiles"] = dict(Counter(c["request"]["profile"] for c in calls))
        profile_tokens = Counter()
        usage_components = Counter()
        for call in calls:
            if call["status"] == "completed":
                profile_tokens[call["request"]["profile"]] += sum(call["result"]["usage"].values())
                usage_components.update(call["result"]["usage"])
        entry["reported_tokens_by_profile"] = dict(profile_tokens)
        entry["usage_components"] = dict(usage_components)
        entry["receipt_counts_reconcile"] = len(calls) == item["calls"]
        entry["receipt_tokens_reconcile"] = sum(profile_tokens.values()) == item["tokens"]
        entry["receipt_hashes"] = {
            p.name: sha(p) for p in sorted((directory / "calls").glob("*.json"))
        }
        entry["transport"] = [
            transport_summary(p) for p in sorted((directory / "transport").glob("*.json"))
        ]
        entry["transport_counts_reconcile"] = len(entry["transport"]) == item["calls"]
        native_totals = [r["native_reported_tokens"] for r in entry["transport"]]
        entry["native_usage_complete"] = all(n is not None for n in native_totals)
        entry["native_reported_tokens"] = sum(n for n in native_totals if n is not None)
        entry["commands"] = [
            {"file": p.name, "exit_code": read(p)["exit_code"], "sha256": sha(p)}
            for p in sorted((directory / "commands").glob("*.json"))
        ]
        entry["checkpoints"] = []
        for path in sorted(directory.glob("checkpoint-*")):
            audit = read(path / "audit.txt")
            entry["checkpoints"].append(
                {
                    "name": path.name,
                    "chapters": audit["chapters_drafted"],
                    "words": audit["words"],
                    "chapter_hashes": read(path / "chapter-hashes.json"),
                    "audit_sha256": sha(path / "audit.txt"),
                    "state_sha256": sha(path / "state.txt"),
                    "verify_sha256": sha(path / "verify.txt"),
                }
            )
        final_audit = directory / "final/audit.txt"
        if final_audit.is_file():
            try:
                audit = read(final_audit)
                entry.update(words=audit["words"], final_revision_audit_sha256=sha(final_audit))
            except (ValueError, KeyError):
                entry["final_audit_available"] = False
        entry["final_chapter_hashes"] = item.get("chapter_hashes", {})
        earlier_checkpoints = [
            checkpoint
            for checkpoint in entry["checkpoints"]
            if checkpoint["chapters"] < item["chapters"]
        ]
        entry["earlier_chapters_unchanged"] = (
            all(
                entry["final_chapter_hashes"].get(name) == digest
                for checkpoint in earlier_checkpoints
                for name, digest in checkpoint["chapter_hashes"].items()
            )
            if earlier_checkpoints
            else None
        )
        verification = directory / "final/verify.txt"
        if verification.is_file():
            try:
                entry["final_revision_verification"] = read(verification)
            except ValueError:
                entry["final_revision_verification_available"] = False
    report["aggregate_counts_reconcile"] = (
        sum(b.get("calls", 0) for b in report["books"]) == report["native_attempts"]
        and sum(b.get("tokens", 0) for b in report["books"]) == report["reported_tokens"]
    )
    report["native_reported_tokens"] = sum(
        b.get("native_reported_tokens", 0) for b in report["books"]
    )
    (HERE / "results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "books": [
                    {k: b[k] for k in ("id", "status", "chapters", "words") if k in b}
                    for b in report["books"]
                ],
                "native_attempts": report["native_attempts"],
                "reported_tokens": report["reported_tokens"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
