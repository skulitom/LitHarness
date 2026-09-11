"""Explicit remaining-slot continuation; never overwrite or retry a shutdown-lost call."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("preserve_original", HERE / "run.py")
assert SPEC is not None and SPEC.loader is not None
original = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(original)
ROOT, LOCAL = original.ROOT, original.LOCAL
RECOVERY = LOCAL / "recovery"
REMAINING = original.ORDER[4:]
LOST = ("combined-1-1", "preserve-2-1")
sha, read = original.sha, original.read


def durable_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def remaining_slots(existing: set[str]) -> tuple[str, ...]:
    if existing != set(original.ORDER[:4]):
        raise RuntimeError("Unexpected original call inventory; do not infer resume position")
    return REMAINING


def prepare() -> None:
    original.lock()
    if (RECOVERY / "progress.json").exists():
        raise RuntimeError("Recovery phase already started")
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Original manifest changed")
    files = dict(manifest["files"])
    if any(sha(Path(p)) != h for p, h in files.items()):
        raise RuntimeError("Frozen-file drift")
    remaining_slots({p.stem for p in (LOCAL / "calls").glob("*.json")})
    records = {}
    known_tokens = 0
    for name in original.ORDER[:4]:
        path = LOCAL / "calls" / f"{name}.json"
        data = path.read_bytes()
        if name in LOST:
            if not data or data.strip(b"\x00"):
                raise RuntimeError("Lost receipt is not the inspected all-zero artifact")
            records[name] = {"status": "lost_after_shutdown", "usage": None}
        else:
            row = read(path)
            if row.get("status") != "completed" or row.get("validation") != "passed":
                raise RuntimeError("Previously valid receipt changed")
            usage = row["result"]["usage"]
            known_tokens += sum(usage.values())
            records[name] = {"status": "completed", "usage": usage}
        records[name].update(path=path.relative_to(ROOT).as_posix(), sha256=sha(path))
    for path in (
        HERE / "RECOVERY.md", Path(__file__), HERE / "audit_recovery.py",
        ROOT / "tests/test_invention_preserve_recovery.py", LOCAL / "manifest.json",
        HERE / "registration.json", LOCAL / "progress.json", LOCAL / "run.log",
        *sorted((LOCAL / "calls").glob("*.json")),
        *sorted((LOCAL / "transport").glob("*.json")),
        *sorted(p for p in (LOCAL / "crash-snapshot").rglob("*") if p.is_file()),
    ):
        files[str(path.resolve())] = sha(path)
    registration = {
        "original_registration_sha256": sha(HERE / "registration.json"),
        "records": records, "known_original_tokens": known_tokens,
        "unknown_original_usage_slots": list(LOST), "remaining": list(REMAINING),
        "attempt_stop_remaining": len(REMAINING), "token_stop_remaining": 65000,
        "files": files, "binary": manifest["binary"],
    }
    durable_write(RECOVERY / "manifest.json", registration)
    durable_write(HERE / "recovery-registration.json", {
        **{k: v for k, v in registration.items() if k not in ("files", "binary")},
        "manifest_sha256": sha(RECOVERY / "manifest.json"),
        "amendment_sha256": sha(HERE / "RECOVERY.md"),
        "runner_sha256": sha(Path(__file__)), "audit_sha256": sha(HERE / "audit_recovery.py"),
        "snapshot_manifest_sha256": sha(LOCAL / "crash-snapshot/manifest.json"),
    })
    print({"known_original_tokens": known_tokens, "lost_slots": LOST, "remaining": REMAINING})


def run() -> None:
    original.lock()
    if (RECOVERY / "progress.json").exists():
        raise RuntimeError("Recovery already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Provider experiment cannot run in test environment")
    registration = read(HERE / "recovery-registration.json")
    if sha(RECOVERY / "manifest.json") != registration["manifest_sha256"]:
        raise RuntimeError("Recovery manifest changed")
    manifest = read(RECOVERY / "manifest.json")
    discovery, _, CompletionRequest, CodexCliProvider = original.imports()
    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=RECOVERY / "transport")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    durable_write(RECOVERY / "progress.json", progress)
    try:
        for name in REMAINING:
            original.lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen-file drift")
            if (progress["attempts"] >= manifest["attempt_stop_remaining"]
                    or progress["tokens"] >= manifest["token_stop_remaining"]):
                raise RuntimeError("Recovery bound reached")
            path = LOCAL / "requests" / f"{name}.json"
            request = CompletionRequest(**read(path))
            source = read(LOCAL / "inputs.json")["sources"][name.split("-")[1]]
            row = {"request": dataclasses.asdict(request), "request_sha256": sha(path),
                   "source": {k: v for k, v in source.items() if k != "premise"},
                   "status": "started", "started_at": datetime.now(UTC).isoformat()}
            progress["attempts"] += 1
            durable_write(RECOVERY / "calls" / f"{name}.json", row)
            durable_write(RECOVERY / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            try:
                result = provider.complete(request)
                row.update(result=dataclasses.asdict(result), status="completed")
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown usage")
                progress["tokens"] += result.usage.total
                try:
                    discovery.Discovery.from_invention(result.parsed)
                    row["validation"] = "passed"
                except (ValueError, TypeError, AttributeError) as error:
                    row["validation"] = str(error)
            except Exception as error:
                row.update(status="failed", error=f"{type(error).__name__}: {error}",
                           raw=provider.last_attempt)
                raise
            finally:
                row["finished_at"] = datetime.now(UTC).isoformat()
                durable_write(RECOVERY / "calls" / f"{name}.json", row)
                progress["slots"].append({"name": name, "status": row["status"]})
                durable_write(RECOVERY / "progress.json", progress)
            print(f"Finished {name}; resumed tokens={progress['tokens']}", flush=True)
    except Exception as error:
        progress["stop"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        progress["status"] = "finished"
        durable_write(RECOVERY / "progress.json", progress)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    (prepare if parser.parse_args().mode == "prepare" else run)()
