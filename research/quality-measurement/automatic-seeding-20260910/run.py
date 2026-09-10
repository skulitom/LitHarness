"""Freeze and exercise the default seed policy against its ingredient-only input control."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/automatic-seeding-20260910"
SOURCE = LOCAL / "source"
OWNED = (
    "src/litharness/domain/invention.py",
    "src/litharness/application/discovery.py",
    "src/litharness/application/concept.py",
    "src/litharness/cli.py",
)
ORDER = (
    "ingredients-0",
    "actions-0",
    "actions-1",
    "ingredients-1",
    "ingredients-2",
    "actions-2",
    "development-0",
    "development-2",
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
    if not holder.startswith("automatic-seeding-20260910: root task;"):
        raise RuntimeError("This task does not own the shared-machine lock")


def imports() -> tuple:
    sys.path.insert(0, str(SOURCE / "src"))
    from litharness.application import concept, discovery
    from litharness.domain import invention
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import CodexCliProvider

    for module in (concept, discovery, invention, sys.modules[CodexCliProvider.__module__]):
        if not Path(module.__file__).is_relative_to(SOURCE):
            raise RuntimeError("Generation imported mutable source")
    return concept, discovery, invention, CompletionRequest, CodexCliProvider


def prepare() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; never refresh after dispatch")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(["git", "ls-files", "src"], cwd=ROOT, text=True).splitlines()
    for name in sorted(set(paths) | set(OWNED)):
        content = (
            (ROOT / name).read_bytes()
            if name in OWNED
            else subprocess.check_output(["git", "show", f"{revision}:{name}"], cwd=ROOT)
        )
        target = SOURCE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    _, discovery, invention, _, _ = imports()
    binary = Path(read(ROOT / "runs/continuation-baseline-20260910/manifest.json")["binary"])
    files = {
        str(path): sha(path)
        for path in SOURCE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    for path in (Path(__file__), HERE / "RUNBOOK.md", ROOT / "uv.lock", binary):
        files[str(path.resolve())] = sha(path)
    registration_path = HERE / "registration.json"
    labels = (
        read(registration_path)["seed_labels"]
        if registration_path.exists()
        else [uuid.uuid4().hex for _ in range(3)]
    )
    for name in ORDER[:6]:
        mode, index_text = name.split("-")
        index = int(index_text)
        seed = invention.make_seed(labels[index], actions=mode == "actions")
        request = discovery.render_request("", person="third", seed=seed)
        for path, value in (
            (LOCAL / "seeds" / f"{name}.json", seed.to_jsonable()),
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
        ):
            write(path, value)
            files[str(path)] = sha(path)
    write(
        LOCAL / "manifest.json",
        {
            "order": ORDER,
            "files": files,
            "binary": str(binary),
            "token_stop": 95000,
        },
    )
    write(
        HERE / "registration.json",
        {
            "manifest_sha256": sha(LOCAL / "manifest.json"),
            "order": ORDER,
            "base_revision": revision,
            "owned_source_sha256": {p: sha(ROOT / p) for p in OWNED},
            "seed_labels": labels,
            "seed_index": 0,
            "version": invention.VERSION,
            "runbook_sha256": sha(HERE / "RUNBOOK.md"),
            "runner_sha256": sha(Path(__file__)),
            "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER[:6]},
            "model": "gpt-6-astra",
            "effort": "medium",
            "native_sampler_seed": None,
        },
    )
    print("Prepared six discovery requests and two conditional developments; no model calls")


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Do not run a provider experiment inside the test environment")
    concept, discovery, invention, CompletionRequest, CodexCliProvider = imports()
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
            if progress["tokens"] >= manifest["token_stop"] or progress["attempts"] >= 8:
                raise RuntimeError("Registered bound reached")
            developed = name.startswith("development-")
            if developed:
                index = name.split("-")[1]
                parent = read(LOCAL / "calls" / f"actions-{index}.json")
                if parent.get("validation") != "passed":
                    progress["slots"].append({"name": name, "status": "skipped_invalid_discovery"})
                    write(LOCAL / "progress.json", progress)
                    continue
                treatment = discovery.Discovery.from_invention(parent["result"]["parsed"])
                seed = invention.InventionSeed.from_payload(
                    read(LOCAL / "seeds" / f"actions-{index}.json")
                )
                request = concept.render_concept_request(
                    "", scenes=6, person="third", discovery=treatment
                )
                request = dataclasses.replace(request, timeout_seconds=600.0)
                write(LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request))
            else:
                request = CompletionRequest(**read(LOCAL / "requests" / f"{name}.json"))
            row = {
                "request": dataclasses.asdict(request),
                "status": "started",
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
                        raise ValueError("No structured output")
                    if developed:
                        value = concept.Concept.from_development(
                            result.parsed, treatment, invention_seed=seed
                        )
                        row["machinery_names"] = list(value.machinery_names())
                        row["requires_precision"] = value.has_quantities()
                        row["discovery_preserved"] = value.discovery == treatment
                        row["seed_preserved"] = value.invention_seed == seed
                        write(LOCAL / "developed" / f"{name}.json", value.to_jsonable())
                    else:
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
