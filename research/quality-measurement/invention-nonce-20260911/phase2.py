"""Freeze and run the registered fixed-prefix native-schema and free-premise contrasts."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASELOCAL = ROOT / "runs/invention-nonce-20260911"
LOCAL = BASELOCAL / "format"
SOURCE = BASELOCAL / "source"
ORDER = (
    "native-1", "prompt-json-1", "free-premise-1",
    "free-premise-2", "prompt-json-2", "native-2",
)
FREE_PREMISE = (
    "Invent an original LitRPG story in portal fantasy, isekai, or system apocalypse. "
    "Write one concrete story proposal in ordinary paragraphs. "
    "Return story material rather than advice."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-nonce-20260911: root task;"):
        raise RuntimeError("This task does not own the shared-machine lock")


def imports() -> tuple:
    sys.path.insert(0, str(SOURCE / "src"))
    from litharness.application import discovery
    from litharness.domain import invention
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import CodexCliProvider

    for module in (discovery, invention, sys.modules[CodexCliProvider.__module__]):
        if not Path(module.__file__).is_relative_to(SOURCE):
            raise RuntimeError("Generation imported mutable source")
    return discovery, CompletionRequest, invention, CodexCliProvider


def prepare() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; never refresh after dispatch")
    parent = read(BASELOCAL / "manifest.json")
    if sha(BASELOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Initial manifest changed")
    if any(sha(Path(p)) != h for p, h in parent["files"].items()):
        raise RuntimeError("Initial frozen-file drift")
    _, CompletionRequest, _, _ = imports()
    control_path = BASELOCAL / "requests/short-1.json"
    seed_path = BASELOCAL / "seeds/short-1.json"
    native = CompletionRequest(**read(control_path))
    prefix = read(seed_path)["brief"]
    requests = {
        "native": native,
        "prompt-json": dataclasses.replace(native, schema=None, system=native.effective_system),
        "free-premise": dataclasses.replace(native, schema=None, system=prefix+"\n\n"+FREE_PREMISE),
    }
    files = dict(parent["files"])
    for path in (Path(__file__), HERE / "FORMAT.md", control_path, seed_path):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(requests[name.rsplit("-", 1)[0]]))
        files[str(path)] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "files": files, "binary": parent["binary"], "token_stop": 50000,
    })
    write(HERE / "format-registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "order": ORDER,
        "initial_manifest_sha256": sha(BASELOCAL / "manifest.json"),
        "runbook_sha256": sha(HERE / "FORMAT.md"), "runner_sha256": sha(Path(__file__)),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "model": "gpt-6-astra", "effort": "medium", "fixed_seed_slot": "short-1",
    })
    print("Prepared six fixed-prefix format requests; no model calls")


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Do not run a provider experiment inside the test environment")
    discovery, CompletionRequest, _, CodexCliProvider = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "format-registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    try:
        for name in manifest["order"]:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen-file drift")
            if progress["tokens"] >= manifest["token_stop"] or progress["attempts"] >= len(ORDER):
                raise RuntimeError("Registered bound reached")
            request = CompletionRequest(**read(LOCAL / "requests" / f"{name}.json"))
            row = {
                "request": dataclasses.asdict(request), "status": "started",
                "started_at": datetime.now(UTC).isoformat(),
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
                    if name.startswith("free-premise-"):
                        if not result.text.strip():
                            raise ValueError("Empty plain-text output")
                    else:
                        from litharness.providers.base import parse_schema_payload
                        parsed = parse_schema_payload(
                            result.text, read(BASELOCAL / "requests/short-1.json")["schema"]
                        )
                        if not isinstance(parsed, dict):
                            raise ValueError("No conforming three-field JSON output")
                        discovery.Discovery.from_invention(parsed)
                    row["validation"] = "passed"
                except (TypeError, ValueError) as error:
                    row["validation"] = str(error)
            except Exception as error:
                row.update(status="failed", error=f"{type(error).__name__}: {error}")
                row["raw"] = provider.last_attempt
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
