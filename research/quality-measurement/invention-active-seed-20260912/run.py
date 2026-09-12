"""Frozen active-prefix wording contrast with repeated invention and unchanged expansion."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import random
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-active-seed-20260912"
PARENT = HERE.with_name("invention-verbalized-20260911")
SPEC = importlib.util.spec_from_file_location("active_seed_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports
)
ARMS = ("passive", "diverse", "active")
ORDER = (
    "passive-1-1", "diverse-1-1", "active-1-1", "diverse-2-1", "active-2-1", "passive-2-1",
    "active-1-2", "diverse-1-2", "passive-1-2", "passive-2-2", "active-2-2", "diverse-2-2",
)
EXPANSIONS = tuple("expand-" + n for n in reversed(ORDER[:6]))
DIVERSITY = (
    "For this open-ended task, generate diverse premises spanning different protagonists, "
    "settings, powers, initiating actions, causal sequences and continuing pursuits."
)
TASK_USE = (
    "Use the full range of possibilities in the story task to guide your creative decisions, "
    "drawing on the whole task."
)
SEED_USE = (
    "Use the exact contents of the random string at the start of this prompt to guide your "
    "creative decisions, drawing on the whole string."
)
FINAL_ONLY = "Return only the requested story material."


def selected_index(number: str) -> int:
    return random.Random("invention-active-seed.v1:" + number).randrange(6)


def invention_request(arm: str, prefix: str, request_type):
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    system = parent.parent.system_text(prefix, "batch")
    if arm != "passive":
        use = SEED_USE if arm == "active" else TASK_USE
        system += "\n\n" + " ".join((DIVERSITY, use, FINAL_ONLY))
    return request_type(
        prompt="Create the requested story material.", system=system,
        schema=parent.parent.SCHEMA, max_output_tokens=3200, timeout_seconds=600,
        profile="experiment.invention-contrast.v1",
    )


def expansion_request(premise: str, discovery):
    return discovery.render_request(premise, person="third")


def transport_text_checks(request, fields: dict) -> dict:
    return {"effective_system_equal": fields.get("transport.system") == request.effective_system,
            "prompt_equal": fields.get("transport.prompt") == request.prompt}


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-active-seed-20260912: root task;"):
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
    _, invention, request_type, _ = imports()
    draws = LOCAL / "draws.json"
    if not draws.exists():
        write(draws, {kind: {str(b): str(secrets.randbits(2048)) for b in (1, 2)}
                      for kind in ("prefix", "selection")})
    numbers = read(draws)
    selections = {b: selected_index(n) for b, n in numbers["selection"].items()}
    for source in read(HERE / "sources.json"):
        if sha(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError("Literature snapshot differs from the source record")
    for path in (
        Path(__file__), HERE / "audit.py", HERE / "RUNBOOK.md", HERE / "SOURCES.md",
        HERE / "sources.json", ROOT / "tests/test_invention_active_seed_experiment.py",
        old_path, PARENT / "run.py", PARENT / "registration.json", draws,
        *(ROOT / row["path"] for row in read(HERE / "sources.json")),
    ):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        arm, block, _ = name.split("-")
        seed = invention.make_seed(numbers["prefix"][block])
        request = invention_request(arm, seed.brief, request_type)
        for path, data in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{block}.json", seed.to_jsonable()),
        ):
            write(path, data)
            files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "expansions": EXPANSIONS, "files": files, "binary": old["binary"],
        "token_stop": 120000, "attempt_stop": 18, "selections": selections,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "numbers": numbers, "selections": selections,
        "order": ORDER, "expansions": EXPANSIONS, "requested_model": "gpt-6-astra",
        "effort": "medium", "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "runner_sha256": sha(Path(__file__)), "audit_sha256": sha(HERE / "audit.py"),
        "sources_sha256": sha(HERE / "sources.json"), "binary_sha256": sha(Path(old["binary"])),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "attempt_stop": 18, "token_stop": 120000,
    })
    print({"model_calls": 0, "selections_zero_based": selections, "attempt_ceiling": 18})


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

    def complete(name: str, request, source: dict | None = None) -> None:
        lock()
        if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
            raise RuntimeError("Frozen-file drift")
        if (progress["tokens"] >= manifest["token_stop"]
                or progress["attempts"] >= manifest["attempt_stop"]):
            raise RuntimeError("Registered bound reached")
        path = LOCAL / "requests" / f"{name}.json"
        if source is not None:
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
                if source is not None:
                    discovery.Discovery.from_invention(result.parsed)
                else:
                    premises = parent.parent.parse_premises(result.parsed, 6)
                    block = name.split("-")[1]
                    index = manifest["selections"][block]
                    row["selected"] = {"index": index, "text_sha256": text_sha(premises[index])}
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
            complete(name, request_type(**read(LOCAL / "requests" / f"{name}.json")))
        for name in EXPANSIONS:
            source_name = name.removeprefix("expand-")
            path = LOCAL / "calls" / f"{source_name}.json"
            row = read(path)
            if row.get("validation") != "passed":
                progress["slots"].append({"name": name, "status": "skipped_invalid_parent"})
                write(LOCAL / "progress.json", progress)
                continue
            index = manifest["selections"][source_name.split("-")[1]]
            premise = parent.parent.parse_premises(row["result"]["parsed"], 6)[index]
            complete(name, expansion_request(premise, discovery), source={
                "parent": source_name, "receipt_sha256": sha(path), "index": index,
                "text_sha256": text_sha(premise),
            })
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
