"""Ablate or scope one discovery sentence against fixed source premises and fresh controls."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/discovery-life-scope-20260912"
PARENT = HERE.with_name("invention-genre-deferral-20260912")
SPEC = importlib.util.spec_from_file_location("life_scope_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports
)
ARMS = ("full", "omit", "scoped")
SOURCES = {"1": "adapt-late-1-1", "2": "adapt-late-2-1"}
ORDER = (
    "full-1-1", "omit-1-1", "scoped-1-1", "scoped-2-1", "omit-2-1", "full-2-1",
    "scoped-1-2", "omit-1-2", "full-1-2", "full-2-2", "omit-2-2", "scoped-2-2",
)
DRAFTS = ("draft-full-2-1", "draft-scoped-2-1", "draft-scoped-1-1", "draft-full-1-1")
ORIGINAL = (
    "Give unfamiliar life or intelligence its own pursuits, relationships and history, "
    "with tangible traces inviting contact and investigation. "
)
SCOPED = (
    "If the author's brief introduces unfamiliar life or intelligence, develop its own "
    "pursuits, relationships and history, with tangible traces inviting contact and "
    "investigation. "
)


def plan_request(arm: str, source: str, discovery):
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    request = discovery.render_request(source, person="third")
    if request.system.count(ORIGINAL) != 1:
        raise ValueError("Expected exactly one registered sentence")
    replacement = {"full": ORIGINAL, "omit": "", "scoped": SCOPED}[arm]
    return dataclasses.replace(request, system=request.system.replace(ORIGINAL, replacement, 1))


def draft_request(payload: dict, discovery, request_type):
    return parent.dependent_request("draft", payload, discovery, request_type)


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("discovery-life-scope-20260912: root task;"):
        raise RuntimeError("This task does not own the shared-machine lock")


def prepare() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; never refresh after dispatch")
    old_path = parent.LOCAL / "manifest.json"
    old = read(old_path)
    if sha(old_path) != read(PARENT / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Parent manifest changed")
    files = dict(old["files"])
    if any(sha(Path(p)) != h for p, h in files.items()):
        raise RuntimeError("Parent frozen-file drift")
    discovery, _, _, _ = imports()
    source_records = {}
    for key, name in SOURCES.items():
        path = parent.LOCAL / "calls" / f"{name}.json"
        receipt = read(path)
        if receipt.get("validation") != "passed":
            raise RuntimeError("The fixed parent source was not valid")
        source = parent.parse_story(receipt["result"]["parsed"])
        source_records[key] = {"parent": name, "path": path.relative_to(ROOT).as_posix(),
                               "receipt_sha256": sha(path), "text_sha256": text_sha(source)}
        target = LOCAL / "sources" / f"{key}.json"
        write(target, {**source_records[key], "text": source})
        files[str(path.resolve())], files[str(target.resolve())] = sha(path), sha(target)
    for path in (
        Path(__file__), HERE / "audit.py", HERE / "RUNBOOK.md", HERE / "SOURCES.md",
        ROOT / "tests/test_discovery_life_scope_experiment.py", old_path,
        PARENT / "run.py", PARENT / "registration.json", PARENT / "evidence.json",
        PARENT / "REPORT.md",
    ):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        arm, key, _ = name.split("-")
        request = plan_request(arm, read(LOCAL / "sources" / f"{key}.json")["text"], discovery)
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request))
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "drafts": DRAFTS, "files": files, "binary": old["binary"],
        "token_stop": 120000, "attempt_stop": 16, "sources": source_records,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "sources": source_records,
        "order": ORDER, "drafts": DRAFTS, "requested_model": "gpt-6-astra", "effort": "medium",
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "audit_sha256": sha(HERE / "audit.py"), "binary_sha256": sha(Path(old["binary"])),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "attempt_stop": 16, "token_stop": 120000,
    })
    print({"model_calls": 0, "plan_calls": len(ORDER), "draft_calls": len(DRAFTS)})


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Provider experiment cannot run in the test environment")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    if json.loads(committed) != read(HERE / "registration.json"):
        raise RuntimeError("Registration must be committed before dispatch")
    discovery, _, request_type, provider_type = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    provider = provider_type(binary=manifest["binary"], trace_directory=LOCAL / "transport")

    def complete(name: str, request, source: dict, *, draft: bool = False):
        lock()
        if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
            raise RuntimeError("Frozen-file drift")
        if (progress["tokens"] >= manifest["token_stop"]
                or progress["attempts"] >= manifest["attempt_stop"]):
            raise RuntimeError("Registered bound reached")
        path = LOCAL / "requests" / f"{name}.json"
        if draft:
            write(path, dataclasses.asdict(request))
        elif read(path) != json.loads(json.dumps(dataclasses.asdict(request))):
            raise RuntimeError("Prepared request changed")
        row = {"request": dataclasses.asdict(request), "request_sha256": sha(path),
               "source": source, "status": "started", "started_at": datetime.now(UTC).isoformat()}
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
                if draft:
                    parent.parse_story(result.parsed)
                else:
                    discovery.Discovery.from_invention(result.parsed)
                row["validation"] = "passed"
            except (TypeError, ValueError, AttributeError) as error:
                row["validation"] = str(error)
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}",
                       raw=provider.last_attempt)
            raise
        finally:
            row["finished_at"] = datetime.now(UTC).isoformat()
            write(LOCAL / "calls" / f"{name}.json", row)
            progress["slots"].append({"name": name, "status": row["status"]})
            write(LOCAL / "progress.json", progress)
        print(f"Finished {name}; tokens={progress['tokens']}", flush=True)

    try:
        for name in ORDER:
            key = name.split("-")[1]
            complete(name, request_type(**read(LOCAL / "requests" / f"{name}.json")),
                     manifest["sources"][key])
        for name in DRAFTS:
            source_name = name.removeprefix("draft-")
            path = LOCAL / "calls" / f"{source_name}.json"
            receipt = read(path)
            if receipt.get("validation") != "passed":
                progress["slots"].append({"name": name, "status": "skipped_invalid_parent"})
                write(LOCAL / "progress.json", progress)
                continue
            payload = receipt["result"]["parsed"]
            complete(name, draft_request(payload, discovery, request_type), {
                "parent": source_name, "receipt_sha256": sha(path),
                "text_sha256": parent.source_hash(payload),
            }, draft=True)
    except Exception as error:
        progress["stop"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        progress["status"] = "finished"
        write(LOCAL / "progress.json", progress)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    (prepare if parser.parse_args().mode == "prepare" else run)()
