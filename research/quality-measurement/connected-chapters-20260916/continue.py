"""Explicit, single-use continuation of the recorded resource stop; no narrative selection."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/connected-chapters-20260916"
PREFIX_CALLS = 77
PREFIX_TOKENS = 2536927
TOTAL_TOKENS = 3500000
TEST = ROOT / "tests/test_connected_chapters_continuation.py"

spec = importlib.util.spec_from_file_location("connected_chapters_parent", HERE / "run.py")
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
base = parent.base
original_admission = base.admission
original_verify = base.verify_frozen


def validate_stop(state, step):
    if (
        state["status"] != "partial"
        or state.get("stop") != "global token ceiling"
        or state.get("continuation")
        or len(state["calls"]) != PREFIX_CALLS
        or sum(c["tokens"] for c in state["calls"]) != PREFIX_TOKENS
        or any(c["status"] != "completed" for c in state["calls"])
    ):
        raise RuntimeError("Not the registered known-usage budget stop")
    if set(state["books"]) != {"A1", "A2", "B1", "B2"}:
        raise RuntimeError("The four registered books are required")
    for book, item in state["books"].items():
        if (
            item["accepted"] != 2
            or item["pending"]
            or item["terminal"]
            or item["phase"] != "grow2"
            or item["status"] != ("stopped" if book == "A2" else "running")
        ):
            raise RuntimeError("Unexpected book state at the budget stop")
    if step["key"] != "grow2-A2-1" or step["returncode"] != 2 or step["before"] != step["after"]:
        raise RuntimeError("Refused grow must preserve canonical state and jobs")


def admission(state, book, at):
    previous = base.LIMITS
    base.LIMITS = dict(
        previous, tokens=(2500000 if len(state["calls"]) < PREFIX_CALLS else TOTAL_TOKENS)
    )
    try:
        return original_admission(state, book, at)
    finally:
        base.LIMITS = previous


def verify():
    manifest = original_verify()
    amendment = base.read(HERE / "continuation.json")
    for path, expected in amendment["files"].items():
        if base.sha(path) != expected:
            raise RuntimeError(f"Continuation input changed: {path}")
    return manifest


def configure():
    parent.configure()
    base.admission, base.verify_frozen = admission, verify


def schedule():
    return [
        ("grow2", "A2"),
        *[
            (phase, book)
            for phase in ("accept-grow2", "chapter3", "drain3")
            for book in base.order(phase)
        ],
    ]


def claim(status):
    paths = [
        ("registration", HERE / p)
        for p in ("RUNBOOK.md", "registration.json", "CONTINUATION.md", "continuation.json")
    ]
    if status == "observed":
        paths.append(("derived_result", HERE / "evidence.json"))
    base.write(
        HERE / "continuation-claim.json",
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": "connected-chapters-budget-continuation-20260916",
            "status": status,
            "statement": "The explicit budget-only continuation preserves the stopped first-draw "
            "sequences and records their remaining third chapters under amended "
            "aggregate admission.",
            "artifacts": [
                {"kind": k, "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
                for k, p in paths
            ],
        },
    )


def prepare():
    base.lock()
    original_verify()
    state = base.read(LOCAL / "progress.json")
    validate_stop(state, base.read(LOCAL / "steps/grow2-A2-1.json"))
    snapshot = LOCAL / "budget-stop"
    snapshot.mkdir()
    shutil.copy2(LOCAL / "progress.json", snapshot / "progress.json")
    files = [Path(__file__), TEST, HERE / "CONTINUATION.md", snapshot / "progress.json"]
    files += list((LOCAL / "steps").glob("*.json"))
    files += list((LOCAL / "calls").glob("*.json"))
    stores = {}
    for book in sorted(state["books"]):
        current = base.book_root(book) / "book.db"
        preserved = snapshot / f"{book}.db"
        shutil.copy2(current, preserved)
        stores[book] = base.sha(current)
        files.append(preserved)
    base.write(
        HERE / "continuation.json",
        {
            "parent_status": state["status"],
            "parent_stop": state["stop"],
            "parent_calls": PREFIX_CALLS,
            "parent_tokens": PREFIX_TOKENS,
            "original_started_at": state["started_at"],
            "original_finished_at": state["finished_at"],
            "aggregate_limits": dict(parent.LIMITS, tokens=TOTAL_TOKENS),
            "remaining_order": schedule(),
            "closed_store_hashes": stores,
            "files": {str(p): base.sha(p) for p in files},
        },
    )
    claim("registered")


def execute(book, phase):
    existing = list((LOCAL / "steps").glob(f"{phase}-{book}-*.json"))
    start = max((int(p.stem.rsplit("-", 1)[-1]) for p in existing), default=0) + 1
    if start > parent.LIMITS["ticks_per_phase"]:
        raise RuntimeError("Original phase allowance exhausted")
    for iteration in range(start, parent.LIMITS["ticks_per_phase"] + 1):
        state = base.read(LOCAL / "progress.json")
        if state.get("stop") or state["books"][book]["status"] != "running":
            return
        if phase.startswith("drain") and base.metadata(book)["pending"] == 0:
            return
        key = f"{phase}-{book}-{iteration}"
        if (LOCAL / "steps" / f"{key}.json").exists():
            raise RuntimeError("Never overwrite an attempted step")
        state["active"] = key
        base.write(LOCAL / "progress.json", state)
        subprocess.run(
            [
                str(base.python_for(book[0])),
                str(Path(__file__)),
                "step",
                book,
                phase,
                str(iteration),
            ],
            cwd=ROOT,
            env=base.environment(book),
            check=True,
        )
        row = base.read(LOCAL / "steps" / f"{key}.json")
        state = base.read(LOCAL / "progress.json")
        meta = row["after"]
        state["books"][book].update(phase=phase, **meta)
        failed = (
            meta["terminal"] > 0
            or meta["accepted"] > 3
            or row["returncode"] == 2
            or (row["returncode"] != 0 and not phase.startswith(("chapter", "drain")))
            or "no_work tick=" in row["stdout"]
        )
        done = base.phase_done(phase, meta)
        if failed or (iteration == parent.LIMITS["ticks_per_phase"] and not done):
            state["books"][book].update(status="stopped", reason=f"continuation stopped in {phase}")
        base.write(LOCAL / "progress.json", state)
        print(
            json.dumps(
                {
                    "step": key,
                    "accepted": meta["accepted"],
                    "calls": len(state["calls"]),
                    "tokens": sum(c["tokens"] for c in state["calls"]),
                }
            ),
            flush=True,
        )
        if failed or done or state.get("stop"):
            return


def run():
    base.lock()
    verify()
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No test-mode dispatch")
    state = base.read(LOCAL / "progress.json")
    validate_stop(state, base.read(LOCAL / "steps/grow2-A2-1.json"))
    for path in (
        Path(__file__),
        TEST,
        HERE / "CONTINUATION.md",
        HERE / "continuation.json",
        HERE / "continuation-claim.json",
    ):
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        if committed != path.read_bytes():
            raise RuntimeError(f"Uncommitted continuation input: {path}")
    amendment = base.read(HERE / "continuation.json")
    for book, expected in amendment["closed_store_hashes"].items():
        if base.sha(base.book_root(book) / "book.db") != expected:
            raise RuntimeError("Store changed after continuation registration")
    state.pop("stop")
    state.pop("finished_at")
    state.update(
        status="running",
        continuation={
            "started_at": base.now(),
            "registration_sha256": base.sha(HERE / "continuation.json"),
        },
    )
    state["books"]["A2"].update(status="running")
    state["books"]["A2"].pop("reason", None)
    base.write(LOCAL / "progress.json", state)
    try:
        for phase, book in schedule():
            execute(book, phase)
            if base.read(LOCAL / "progress.json").get("stop"):
                break
    except BaseException as error:
        state = base.read(LOCAL / "progress.json")
        state["stop"] = f"continuation scheduler failure: {error!r}"
        base.write(LOCAL / "progress.json", state)
        raise
    finally:
        state = base.read(LOCAL / "progress.json")
        state.pop("active", None)
        for item in state["books"].values():
            if (
                item["status"] == "running"
                and item.get("accepted") == 3
                and item.get("pending") == 0
                and not item.get("terminal")
            ):
                item["status"] = "complete"
        state.update(
            status="complete"
            if not state.get("stop")
            and all(b["status"] == "complete" for b in state["books"].values())
            else "partial",
            finished_at=base.now(),
        )
        base.write(LOCAL / "progress.json", state)


def audit():
    parent.audit()
    claim("observed")
    record = base.read(HERE / "claim.json")
    record["artifacts"] += [
        {"kind": "registration", "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
        for p in (HERE / "CONTINUATION.md", HERE / "continuation.json")
    ]
    base.write(HERE / "claim.json", record)


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
