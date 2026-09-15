"""Explicitly registered recovery of one interrupted request; never redraw completed work."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/experience-first-recovery-20260915"
ORIGINAL = ROOT / "runs/experience-first-20260914"
PRIOR = HERE.with_name("experience-first-20260914")
SPEC = importlib.util.spec_from_file_location("experience_first_original", PRIOR / "run.py")
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
sha, read, write = BASE.sha, BASE.read, BASE.write
INTERRUPTED = "outline-C-3"
FINAL = Path("C:/Users/artem/AppData/Local/Temp/litharness-codex-0qurfw9p/final.txt")


def remaining_slots(receipts):
    """Only a contiguous completed prefix followed by the known outputless interruption."""
    cut = BASE.ORDER.index(INTERRUPTED)
    if set(receipts) != set(BASE.ORDER[:cut + 1]):
        raise RuntimeError("Original receipt inventory differs from the shutdown checkpoint")
    if any(receipts[n].get("status") != "completed" for n in BASE.ORDER[:cut]):
        raise RuntimeError("Cannot replace a non-completed earlier response")
    pending = receipts[INTERRUPTED]
    if pending.get("status") != "started" or "result" in pending:
        raise RuntimeError("Interrupted request has a result or a different terminal state")
    return BASE.ORDER[cut:]


def configure():
    BASE.use_source()
    BASE.LOCAL, BASE.HERE = LOCAL, HERE
    BASE.use_source = lambda: None


def prepare():
    BASE.lock()
    BASE.verify_frozen()
    if LOCAL.exists():
        raise RuntimeError("Continuation already prepared; do not redraw or refresh inputs")
    if FINAL.exists():
        raise RuntimeError("A final response exists; preserve it instead of retrying")
    receipts = {p.stem: read(p) for p in (ORIGINAL / "calls").glob("*.json")}
    remaining = remaining_slots(receipts)
    progress = read(ORIGINAL / "progress.json")
    if (progress["active"] != INTERRUPTED or progress["attempts"] != 57
            or progress["tokens"] != 406523):
        raise RuntimeError("Original checkpoint changed")
    original_manifest = read(ORIGINAL / "manifest.json")
    files = dict(original_manifest["files"])
    for folder in ("calls", "requests", "transport", "seeds"):
        for source in (ORIGINAL / folder).glob("*.json"):
            files[str(source.resolve())] = sha(source)
            if folder in ("requests", "seeds") or (
                folder == "calls" and source.stem != INTERRUPTED
            ):
                target = LOCAL / folder / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                files[str(target.resolve())] = sha(target)
    for path in (ORIGINAL / "progress.json", ORIGINAL / "manifest.json",
                 PRIOR / "registration.json", Path(__file__), HERE / "RUNBOOK.md",
                 ROOT / "tests/test_experience_first_recovery.py"):
        files[str(path.resolve())] = sha(path)
    deadline = datetime.fromisoformat(progress["started_at"]) + timedelta(minutes=180)
    manifest = {"files": files, "binary": original_manifest["binary"],
                "attempt_stop": len(remaining), "token_stop": 2500000,
                "deadline_utc": deadline.isoformat(), "remaining": remaining,
                "inherited_count": 56, "prior_attempts": 57, "prior_tokens": 406523}
    write(LOCAL / "manifest.json", manifest)
    original_registration = read(PRIOR / "registration.json")
    registration = {
        "schema": "experience-first.shutdown-continuation.v1",
        "manifest_sha256": sha(LOCAL / "manifest.json"), "remaining": remaining,
        "source_registration": {"path": (PRIOR / "registration.json").relative_to(ROOT).as_posix(),
                                "sha256": sha(PRIOR / "registration.json")},
        "source_revision": original_registration["source_revision"],
        "static_requests": original_registration["static_requests"],
        "interrupted_slot": INTERRUPTED,
        "interrupted_receipt_sha256": sha(ORIGINAL / f"calls/{INTERRUPTED}.json"),
        "interrupted_request_sha256": sha(ORIGINAL / f"requests/{INTERRUPTED}.json"),
        "final_path_exists_at_prepare": False,
        "interrupted_usage": "unknown", "max_total_attempts": 85,
        "new_call_limit": len(remaining), "deadline_utc": deadline.isoformat(),
        "known_token_admission_limit": 2500000,
        "prepared_at": datetime.now(UTC).isoformat(),
        "files": files,
    }
    write(HERE / "registration.json", registration)
    write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": "experience-first-shutdown-continuation-20260915",
        "statement": "The registered experience-first feasibility comparison continues with "
                     "56 inherited responses and one documented interrupted-request retry.",
        "status": "registered",
        "artifacts": [{"kind": "registration",
                       "path": (HERE / "registration.json").relative_to(ROOT).as_posix(),
                       "sha256": sha(HERE / "registration.json")}],
    })
    print(f"Preserved 56 completed receipts; prepared {len(remaining)} new calls; zero dispatches.")


def run():
    BASE.lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already dispatched; no second automatic continuation")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Generation disabled in tests")
    relative = (HERE / "registration.json").relative_to(ROOT).as_posix()
    for ref in ("HEAD", "origin/main"):
        saved = subprocess.check_output(["git", "show", f"{ref}:{relative}"], cwd=ROOT)
        if json.loads(saved) != read(HERE / "registration.json"):
            raise RuntimeError("Commit and push continuation registration first")
    configure()
    manifest = BASE.verify_frozen()
    from litharness.providers.codex_cli import CodexCliProvider

    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    remaining = tuple(manifest["remaining"])
    progress = {"attempts": 0, "tokens": manifest["prior_tokens"], "status": "running",
                "prior_attempts": 57, "inherited_completed": 56, "interrupted_usage": "unknown",
                "started_at": datetime.now(UTC).isoformat(),
                "slots": [{"name": n, "status": "completed", "phase": "inherited"}
                          for n in BASE.ORDER if n not in remaining]}
    write(LOCAL / "progress.json", progress)
    try:
        for name in remaining:
            BASE.lock()
            BASE.verify_frozen()
            request, lineage = BASE.slot_request(name)
            if request is None:
                write(LOCAL / f"calls/{name}.json", {
                    "name": name, "status": "skipped", "lineage": lineage,
                    "reason": "Invalid designated parent; no substitution",
                })
                progress["slots"].append({"name": name, "status": "skipped"})
                write(LOCAL / "progress.json", progress)
                continue
            if (progress["attempts"] >= manifest["attempt_stop"]
                    or progress["tokens"] >= manifest["token_stop"]
                    or datetime.now(UTC) >= datetime.fromisoformat(manifest["deadline_utc"])):
                raise RuntimeError("Registered admission ceiling reached")
            path = LOCAL / f"requests/{name}.json"
            prepared = BASE.serial(request)
            if path.exists() and read(path) != prepared:
                raise RuntimeError("Saved request changed")
            if not path.exists():
                write(path, prepared)
            row = {"name": name, "status": "started", "phase": "post_shutdown",
                   "lineage": lineage, "request": prepared, "request_sha256": sha(path),
                   "started_at": datetime.now(UTC).isoformat()}
            write(LOCAL / f"calls/{name}.json", row)
            progress["attempts"] += 1
            progress["active"] = name
            write(LOCAL / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            try:
                result = provider.complete(request)
                row.update(status="completed", result=BASE.serial(result))
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown completed-call usage")
                progress["tokens"] += result.usage.total
            except Exception as error:
                row.update(status="failed", error=str(error), raw=provider.last_attempt)
                raise
            finally:
                row["finished_at"] = datetime.now(UTC).isoformat()
                write(LOCAL / f"calls/{name}.json", row)
                progress["slots"].append({"name": name, "status": row["status"]})
                write(LOCAL / "progress.json", progress)
            print(f"Completed {name}; total known tokens {progress['tokens']}", flush=True)
        progress["status"] = "complete"
    except Exception as error:
        progress.update(status="stopped", error=str(error))
        raise
    finally:
        progress["finished_at"] = datetime.now(UTC).isoformat()
        write(LOCAL / "progress.json", progress)


def audit():
    configure()
    BASE.audit()
    path = HERE / "evidence.json"
    evidence = read(path)
    evidence["shutdown_recovery"] = {
        "inherited_complete": 56, "prior_attempts": 57,
        "interrupted_slot": INTERRUPTED, "interrupted_usage": "unknown",
        "new_attempts": evidence["progress"]["attempts"],
        "total_attempts": 57 + evidence["progress"]["attempts"],
        "original_registration_sha256": sha(PRIOR / "registration.json"),
        "original_interrupted_receipt_sha256": sha(ORIGINAL / f"calls/{INTERRUPTED}.json"),
    }
    write(path, evidence)


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
