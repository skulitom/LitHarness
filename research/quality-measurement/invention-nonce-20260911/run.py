"""Freeze and run the registered random integer Base64 preprompt comparisons."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-nonce-20260911"
SOURCE = LOCAL / "source"
OWNED = (
    "src/litharness/domain/invention.py", "src/litharness/application/discovery.py",
    "src/litharness/cli.py",
)
ORDER = (
    "control-1", "short-1", "long-1", "control-2", "long-2", "short-2",
    "repeat-long-1", "repeat-short-1",
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
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(["git", "ls-files", "src"], cwd=ROOT, text=True).splitlines()
    for name in paths:
        target = SOURCE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        content = (
            (ROOT / name).read_bytes() if name in OWNED
            else subprocess.check_output(["git", "show", f"{revision}:{name}"], cwd=ROOT)
        )
        target.write_bytes(content)
    discovery, _, invention, _ = imports()
    saved = HERE / "registration.json"
    numbers = read(saved)["numbers"] if saved.exists() else {
        f"{arm}-{i}": str(secrets.randbits(bits))
        for arm, bits in (("short", 2048), ("long", 8192)) for i in (1, 2)
    }
    binary = Path(read(ROOT / "runs/continuation-baseline-20260910/manifest.json")["binary"])
    files = {
        str(path): sha(path)
        for path in SOURCE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    for path in (
        Path(__file__), HERE / "RUNBOOK.md", ROOT / "uv.lock", binary,
        ROOT / "tools/generation_trace.py",
    ):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        seed_name = name.removeprefix("repeat-")
        seed = (
            invention.make_seed(numbers[seed_name], version=invention.PREFIX_VERSION)
            if seed_name in numbers else None
        )
        request = discovery.render_request("", person="third", seed=seed)
        for path, value in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{name}.json", seed.to_jsonable() if seed else None),
        ):
            write(path, value)
            files[str(path)] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "files": files, "binary": str(binary), "token_stop": 80000,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"),
        "order": ORDER, "base_revision": revision,
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "diagnostic_tool_sha256": sha(ROOT / "tools/generation_trace.py"),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "numbers": numbers, "model": "gpt-6-astra", "effort": "medium",
        "native_sampler_seed": None, "creative_seed": invention.PREFIX_VERSION,
        "documentation": "https://learn.chatgpt.com/docs/non-interactive-mode",
    })
    print("Prepared eight first-response requests; no model calls")


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Do not run a provider experiment inside the test environment")
    discovery, CompletionRequest, _, CodexCliProvider = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
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
                    if not isinstance(result.parsed, dict):
                        raise ValueError("No conforming three-field JSON output")
                    discovery.Discovery.from_invention(result.parsed)
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
