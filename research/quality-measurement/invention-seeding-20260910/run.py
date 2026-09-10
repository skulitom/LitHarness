"""A frozen three-condition test of actual creative inputs, with all first responses retained."""

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
LOCAL = ROOT / "runs/invention-seeding-20260910"
BASELINE = ROOT / "runs/continuation-baseline-20260910"
SEED = "20260910-invention-seed-pilot"
ORDER = (
    "control-1", "nonce-1", "ingredients-0-a", "ingredients-1-a", "control-2", "nonce-2",
    "ingredients-2-a", "ingredients-0-b", "nonce-3", "ingredients-1-b", "ingredients-2-b",
    "control-3",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-seeding-20260910: root task;"):
        raise RuntimeError("This task does not own the shared-machine lock")


def prepare() -> None:
    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared")
    from litharness.application import discovery

    sys.path.insert(0, str(ROOT))
    from tools.invention_seed import packet

    if not Path(discovery.__file__).is_relative_to(BASELINE / "source"):
        raise RuntimeError("Use the baseline's frozen interpreter")
    original = discovery.render_request("", person="third")
    binary = Path(read(BASELINE / "manifest.json")["binary"])
    files = {str(p): sha(p) for p in (
        HERE / "RUNBOOK.md", Path(__file__), ROOT / "tools/invention_seed.py", binary,
    )}
    files.update({str(p): sha(p) for p in (BASELINE / "source").rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"})
    packets = []
    for index in range(3):
        value = packet(SEED, index)
        path = LOCAL / "packets" / f"seed-{index:05d}.json"
        if read(path) != value:
            raise RuntimeError("Previewed seed packet changed")
        packets.append(value)
        files[str(path)] = sha(path)
        brief_path = path.with_suffix(".brief.txt")
        if brief_path.read_text(encoding="utf-8") != value["brief"] + "\n":
            raise RuntimeError("Brief file differs from its receipt")
        files[str(brief_path)] = sha(brief_path)
    for name in ORDER:
        request = original
        if name.startswith("nonce-"):
            nonce = hashlib.sha256(f"{SEED}/{name}".encode()).hexdigest()
            request = dataclasses.replace(original, prompt=original.prompt + (
                f"\nInvention seed: {nonce}. Use this identifier to vary the invention."
            ))
        elif name.startswith("ingredients-"):
            index = int(name.split("-")[1])
            request = discovery.render_request(packets[index]["brief"], person="third")
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request))
        files[str(path)] = sha(path)
    manifest = {"order": ORDER, "files": files, "binary": str(binary), "token_stop": 160000}
    write(LOCAL / "manifest.json", manifest)
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "order": ORDER,
        "source_revision": read(BASELINE / "manifest.json")["revision"],
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "seed_tool_sha256": sha(ROOT / "tools/invention_seed.py"), "seed_label": SEED,
        "packet_sha256": {str(i): sha(LOCAL / "packets" / f"seed-{i:05d}.json") for i in range(3)},
        "request_sha256": {name: sha(LOCAL / "requests" / f"{name}.json") for name in ORDER},
        "model": "gpt-6-astra", "effort": "medium", "native_sampler_seed": None,
    })
    print("Prepared twelve requests; no model calls")


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
    if not Path(sys.modules[Discovery.__module__].__file__).is_relative_to(BASELINE / "source"):
        raise RuntimeError("Use the baseline's frozen interpreter")
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
            row = {"request": dataclasses.asdict(request),
                   "started_at": datetime.now(UTC).isoformat(), "status": "started"}
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
