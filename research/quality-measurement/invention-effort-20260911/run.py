"""Fixed-prompt low/medium effort control using the previous frozen transport."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import random
import secrets
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-effort-20260911"
PARENT = HERE.with_name("invention-contrast-20260911")
SPEC = importlib.util.spec_from_file_location("contrast_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports
)
ORDER = ("low-1", "medium-1", "medium-2", "low-2", "low-3", "medium-3")
EXPANSIONS = tuple(reversed(ORDER))


def selected_index(number: str) -> int:
    return random.Random("invention-effort.v1:" + number).randrange(6)


def effort_for(name: str) -> str:
    if name.startswith("expand-") and name[7:] in ORDER:
        return "medium"
    if name in ORDER:
        return name.split("-", 1)[0]
    raise ValueError(f"Unknown slot: {name}")


def request_matches(saved: dict, request) -> bool:
    return saved == json.loads(json.dumps(dataclasses.asdict(request)))


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-effort-20260911: root task;"):
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
    _, invention, CompletionRequest, _ = imports()
    draws = LOCAL / "draws.json"
    if not draws.exists():
        write(draws, {str(b): str(secrets.randbits(2048)) for b in (1, 2, 3)})
    numbers = read(draws)
    selections = {b: selected_index(n) for b, n in numbers.items()}
    for p in (Path(__file__), HERE / "RUNBOOK.md", old_path, PARENT / "registration.json", draws):
        files[str(p.resolve())] = sha(p)
    for name in ORDER:
        block = name.rsplit("-", 1)[1]
        seed = invention.make_seed(numbers[block])
        request = CompletionRequest(
            prompt="Create the requested story material.",
            system=parent.system_text(seed.brief, "batch"), schema=parent.SCHEMA,
            max_output_tokens=3200, timeout_seconds=600, profile="experiment.invention-contrast.v1",
        )
        for path, data in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{block}.json", seed.to_jsonable()),
        ):
            write(path, data)
            files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "expansions": EXPANSIONS, "files": files, "binary": old["binary"],
        "token_stop": 90000, "attempt_stop": 12, "selections": selections,
        "effort": {n: effort_for(n) for n in (*ORDER, *("expand-" + p for p in EXPANSIONS))},
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "numbers": numbers, "selections": selections,
        "order": ORDER, "expansions": EXPANSIONS, "requested_model": "gpt-6-astra",
        "effort": read(LOCAL / "manifest.json")["effort"],
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "binary_sha256": sha(Path(old["binary"])),
    })
    print({"model_calls": 0, "selections_zero_based": selections, "attempt_ceiling": 12})


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
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)

    def complete(name: str, request, source: dict | None = None) -> None:
        lock()
        if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
            raise RuntimeError("Frozen-file drift")
        if progress["tokens"] >= manifest["token_stop"] or progress["attempts"] >= 12:
            raise RuntimeError("Registered bound reached")
        effort = effort_for(name)
        if effort != manifest["effort"][name]:
            raise RuntimeError("Registered effort changed")
        provider = CodexCliProvider(binary=manifest["binary"], reasoning_effort=effort,
                                    trace_directory=LOCAL / "transport")
        path = LOCAL / "requests" / f"{name}.json"
        if source is not None:
            write(path, dataclasses.asdict(request))
        elif not request_matches(read(path), request):
            raise RuntimeError("Prepared request changed")
        row = {"request": dataclasses.asdict(request), "request_sha256": sha(path),
               "requested_effort": effort, "source": source, "status": "started",
               "started_at": datetime.now(UTC).isoformat()}
        progress["attempts"] += 1
        write(LOCAL / "calls" / f"{name}.json", row)
        write(LOCAL / "progress.json", progress)
        print(f"Starting {name} ({effort})", flush=True)
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
                    premises = parent.parse_premises(result.parsed, 6)
                    index = manifest["selections"][name.rsplit("-", 1)[1]]
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
            complete(name, CompletionRequest(**read(LOCAL / "requests" / f"{name}.json")))
        for name in EXPANSIONS:
            path = LOCAL / "calls" / f"{name}.json"
            row = read(path)
            if row.get("validation") != "passed":
                progress["slots"].append({"name": "expand-" + name,
                                          "status": "skipped_invalid_parent"})
                write(LOCAL / "progress.json", progress)
                continue
            index = row["selected"]["index"]
            premise = parent.parse_premises(row["result"]["parsed"], 6)[index]
            complete("expand-" + name, discovery.render_request(premise, person="third"),
                     source={"parent": name, "receipt_sha256": sha(path), "index": index,
                             "text_sha256": text_sha(premise)})
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
