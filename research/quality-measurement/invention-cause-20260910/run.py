"""Frozen, tool-free first-invention comparison using the production Codex transport."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-cause-20260910"
BASELINE = ROOT / "runs/continuation-baseline-20260910"
ORDER = ("full-1", "minimal-1", "minimal-2", "full-2", "minimal-3", "full-3", "full-4", "minimal-4")
MINIMAL = (
    "Invent an original LitRPG story in portal fantasy, isekai, or system apocalypse. "
    "Describe its world, the opening chapter's events, and the protagonist's possible "
    "growth in the three requested fields. Return story material rather than advice."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lock() -> None:
    if (
        not (ROOT / "runs/box.lock/holder")
        .read_text(encoding="utf-8-sig")
        .startswith("invention-cause-20260910: root task;")
    ):
        raise RuntimeError("This task does not own the shared-machine lock")


def prepare() -> None:
    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared")
    from litharness.application import discovery

    if not Path(discovery.__file__).is_relative_to(BASELINE / "source"):
        raise RuntimeError("Use the baseline's frozen interpreter")
    full = discovery.render_request("", person="third")
    binary = Path(read(BASELINE / "manifest.json")["binary"])
    files = {str(HERE / n): sha(HERE / n) for n in ("RUNBOOK.md", "run.py")}
    files.update(
        {
            str(p): sha(p)
            for p in (BASELINE / "source").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
    )
    files[str(binary)] = sha(binary)
    for name in ORDER:
        request = dataclasses.replace(full, system=MINIMAL) if name.startswith("minimal") else full
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request))
        files[str(path)] = sha(path)
    manifest = {"order": ORDER, "files": files, "binary": str(binary), "token_stop": 160000}
    write(LOCAL / "manifest.json", manifest)
    write(
        HERE / "registration.json",
        {
            "manifest_sha256": sha(LOCAL / "manifest.json"),
            "source_revision": read(BASELINE / "manifest.json")["revision"],
            "runbook_sha256": sha(HERE / "RUNBOOK.md"),
            "runner_sha256": sha(HERE / "run.py"),
            "request_sha256": {name: sha(LOCAL / "requests" / f"{name}.json") for name in ORDER},
            "model": "gpt-6-astra",
            "effort": "medium",
            "order": ORDER,
        },
    )
    print("Prepared eight requests; no model calls")


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    for key in list(os.environ):
        if key.startswith("LITHARNESS_"):
            del os.environ[key]
    from litharness.application.discovery import Discovery
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import CodexCliProvider

    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Prepared manifest changed")
    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    try:
        for name in manifest["order"]:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen input/source/binary drift")
            if progress["tokens"] >= manifest["token_stop"]:
                raise RuntimeError("Registered token bound reached")
            request = CompletionRequest(**read(LOCAL / "requests" / f"{name}.json"))
            row = {
                "request": dataclasses.asdict(request),
                "started_at": datetime.now(UTC).isoformat(),
                "status": "started",
            }
            progress["attempts"] += 1
            write(LOCAL / "calls" / f"{name}.json", row)
            write(LOCAL / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            try:
                result = provider.complete(request)
                row.update(result=dataclasses.asdict(result), status="completed")
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown usage")
                progress["tokens"] += result.usage.total
                try:
                    if not isinstance(result.parsed, dict):
                        raise ValueError("No structured invention returned")
                    Discovery.from_invention(result.parsed)
                    row["validation"] = "passed"
                except (TypeError, ValueError) as error:
                    row["validation"] = str(error)
            except Exception as error:
                row.update(status="failed", error=f"{type(error).__name__}: {error}")
                raise
            finally:
                row["finished_at"] = datetime.now(UTC).isoformat()
                write(LOCAL / "calls" / f"{name}.json", row)
                progress["slots"].append({"name": name, "status": row["status"]})
                write(LOCAL / "progress.json", progress)
            print(f"Finished {name}; tokens={progress['tokens']}", flush=True)
    except Exception as error:
        progress["stop"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        progress["status"] = "finished"
        write(LOCAL / "progress.json", progress)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    args = parser.parse_args()
    (prepare if args.mode == "prepare" else run)()
