"""Ablate retained history with repeated, fixed-premise preservation-only expansions."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-preserve-20260911"
PARENT = HERE.with_name("invention-memory-20260911")
SPEC = importlib.util.spec_from_file_location("memory_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports, request_matches = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports, parent.request_matches
)
PRESERVE = (
    "Preserve the supplied premise's central action and pursuit. "
    "Do not replace the supplied premise with another story."
)
ORDER = (
    "clean-1-1", "preserve-1-1", "combined-1-1",
    "preserve-2-1", "combined-2-1", "clean-2-1",
    "combined-1-2", "preserve-1-2", "clean-1-2",
    "clean-2-2", "combined-2-2", "preserve-2-2",
)


def expansion_request(arm: str, premise: str, history: list[str], discovery):
    if arm == "combined":
        return parent.expansion_request("retain-structure-1", premise, history, discovery)
    request = discovery.render_request(premise, person="third")
    if arm == "preserve":
        return dataclasses.replace(request, prompt=PRESERVE + "\n\n" + request.prompt)
    if arm != "clean":
        raise ValueError(f"Unknown arm: {arm}")
    return request


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-preserve-20260911: root task;"):
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
    history = read(parent.LOCAL / "history.json")["premises"]
    discovery, _, _, _ = imports()
    sources = {}
    for block in ("1", "2"):
        path = parent.LOCAL / "calls" / f"structure-{block}.json"
        row = read(path)
        if row.get("validation") != "passed":
            raise RuntimeError("Invalid parent premise")
        index = old["selections"][block]
        premise = parent.parse_premises(row["result"]["parsed"], 6)[index]
        if row["selected"] != {"index": index, "text_sha256": text_sha(premise)}:
            raise RuntimeError("Parent selection changed")
        sources[block] = {"path": path.relative_to(ROOT).as_posix(), "index": index,
                          "receipt_sha256": sha(path), "text_sha256": text_sha(premise),
                          "premise": premise}
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "inputs.json", {"sources": sources, "history": history})
    for p in (Path(__file__), HERE / "RUNBOOK.md", HERE / "audit.py", old_path,
              PARENT / "registration.json", LOCAL / "inputs.json",
              ROOT / "tests/test_invention_preserve_experiment.py"):
        files[str(p.resolve())] = sha(p)
    for name in ORDER:
        arm, block, _ = name.split("-")
        request = expansion_request(arm, sources[block]["premise"], history, discovery)
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request))
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "files": files, "binary": old["binary"],
        "token_stop": 100000, "attempt_stop": len(ORDER),
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "inputs_sha256": sha(LOCAL / "inputs.json"),
        "sources": {b: {k: v for k, v in s.items() if k != "premise"}
                    for b, s in sources.items()},
        "order": ORDER, "requested_model": "gpt-6-astra", "effort": "medium",
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "audit_sha256": sha(HERE / "audit.py"),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "binary_sha256": sha(Path(old["binary"])),
    })
    print({"model_calls": 0, "attempt_ceiling": len(ORDER), "order": ORDER})


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Provider experiment cannot run in the test environment")
    discovery, _, CompletionRequest, CodexCliProvider = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    sources = read(LOCAL / "inputs.json")["sources"]
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    try:
        for name in ORDER:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen-file drift")
            if (progress["tokens"] >= manifest["token_stop"]
                    or progress["attempts"] >= manifest["attempt_stop"]):
                raise RuntimeError("Registered bound reached")
            path = LOCAL / "requests" / f"{name}.json"
            request = CompletionRequest(**read(path))
            if not request_matches(read(path), request):
                raise RuntimeError("Prepared request changed")
            source = sources[name.split("-")[1]]
            row = {"request": dataclasses.asdict(request), "request_sha256": sha(path),
                   "source": {k: v for k, v in source.items() if k != "premise"},
                   "status": "started", "started_at": datetime.now(UTC).isoformat()}
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
