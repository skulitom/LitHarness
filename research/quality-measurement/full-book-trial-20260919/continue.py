"""Explicit one-time continuation of the preserved scene-id runner failure."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("full_book_continued", HERE / "run.py")
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)
trial.configure()
base, LOCAL = trial.base, trial.LOCAL


def stopped():
    state = base.read(LOCAL / "runner-stop/progress.json")
    if (len(state["calls"]) != 3 or sum(c["tokens"] for c in state["calls"]) != 22984
            or any(c["status"] != "completed" for c in state["calls"])
            or not state.get("stop", "").startswith("scheduler failure:")
            or state.get("active") != "new-A1-1"):
        raise RuntimeError("Not the registered runner stop")
    current = trial.metadata("A1")
    if (current["accepted"] != 0 or current["total"] != 6
            or current["pending"] or current["terminal"]):
        raise RuntimeError("Stopped book changed")
    if base.sha(base.book_root("A1") / "book.db") != base.sha(LOCAL / "runner-stop/book.db"):
        raise RuntimeError("Stopped database bytes changed")
    return state, current


def files():
    return [HERE / "run.py", HERE / "audit.py", HERE / "continue.py",
            HERE / "CONTINUATION.md", trial.TEST]


def prepare():
    base.lock()
    if (HERE / "continuation.json").exists():
        raise RuntimeError("Continuation already prepared")
    state, current = stopped()
    manifest = base.read(LOCAL / "runner-stop/manifest.json")
    mutable = {str(p) for p in files()}
    for name, expected in manifest["files"].items():
        if name not in mutable and base.sha(name) != expected:
            raise RuntimeError(f"Original frozen input changed: {name}")
    captured = [*files(), *(LOCAL / "runner-stop").iterdir()]
    manifest["files"].update({str(p): base.sha(p) for p in captured if p.is_file()})
    base.write(LOCAL / "manifest.json", manifest)
    base.write(HERE / "continuation.json", {
        "schema": "litharness.full-book-continuation.v1", "original_calls": 3,
        "original_tokens": 22984, "original_started_at": state["started_at"],
        "limits": trial.LIMITS, "frozen_files": manifest["files"],
        "manifest_sha256": base.sha(LOCAL / "manifest.json"), "stopped_metadata": current,
        "receipt_gap": "new-A1-1 after-metadata failed before its step receipt was persisted",
    })
    trial.claim("registered")


def run():
    base.lock()
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No live test-mode continuation")
    base.verify_frozen()
    state, current = stopped()
    if base.read(LOCAL / "progress.json") != state:
        raise RuntimeError("Continuation was already used or progress changed")
    for path in [*files(), HERE / "continuation.json", HERE / "claim.json"]:
        content = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(trial.ROOT).as_posix()}"], cwd=trial.ROOT,
        )
        if content != path.read_bytes():
            raise RuntimeError(f"Uncommitted continuation input: {path}")
    state["original_stop"] = state.pop("stop")
    state["continuation_started_at"] = base.now()
    state["books"]["A1"].update(current, status="running")
    state.pop("active", None)
    base.write(LOCAL / "progress.json", state)
    try:
        for phase in trial.PHASES[trial.PHASES.index("seed"):]:
            trial.execute("A1", phase)
            state = base.read(LOCAL / "progress.json")
            if state.get("stop") or state["books"]["A1"]["status"] == "stopped":
                break
    except BaseException as error:
        state = base.read(LOCAL / "progress.json")
        state["stop"] = f"continuation scheduler failure: {error!r}"
        base.write(LOCAL / "progress.json", state)
        raise
    finally:
        state = base.read(LOCAL / "progress.json")
        state.pop("active", None)
        try:
            current = trial.metadata("A1")
            book = state["books"]["A1"]
            complete = (not state.get("stop") and book["status"] == "running"
                        and current["accepted"] == current["total"] == trial.CHAPTERS
                        and not current["pending"] and not current["terminal"]
                        and not current["exceptions"])
            book.update(current, status="complete" if complete else "stopped")
            state["status"] = "complete" if complete else "partial"
        except Exception as error:
            state.update(status="partial", finalization_error=repr(error))
        state["finished_at"] = base.now()
        base.write(LOCAL / "progress.json", state)


if __name__ == "__main__":
    {"prepare": prepare, "run": run}[sys.argv[1]]()
