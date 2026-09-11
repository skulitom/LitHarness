"""Frozen verbalized-sampling contrasts; probabilities never select or reject stories."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import math
import os
import random
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-verbalized-20260911"
PARENT = HERE.with_name("invention-contrast-20260911")
SPEC = importlib.util.spec_from_file_location("verbalized_contrast_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, imports = parent.sha, parent.text_sha, parent.read, parent.imports
ARMS = ("batch", "format", "full", "tail")
ORDER = tuple(f"{a}-1" for a in ARMS) + tuple(f"{a}-2" for a in reversed(ARMS))
EXPANSIONS = tuple("expand-" + n for n in reversed(ORDER))
OBJECT_SCHEMA = {
    "type": "object", "properties": {"premises": {"type": "array", "items": {
        "type": "object", "properties": {
            "text": {"type": "string"}, "probability": {"type": "number"},
        }, "required": ["text", "probability"], "additionalProperties": False,
    }}}, "required": ["premises"], "additionalProperties": False,
}
FORMAT = (
    "For each premise, put the story in text and the fixed placeholder 0.0 in probability. "
    "This placeholder is output formatting, not an estimate."
)
FULL = (
    "Draw six possible responses to this story task. For each, put the story in text and "
    "your estimated probability of that response in probability. These estimates refer "
    "to the full space of possible responses, not shares normalized over the six returned items."
)
TAIL = (
    "Choose these responses from low-probability parts of that full distribution; "
    "each response should have an estimated probability below 0.10."
)


def write(path: Path, value: object) -> None:
    """Keep the old receipt valid if a new write or replacement is interrupted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def selected_index(number: str) -> int:
    return random.Random("invention-verbalized.v1:" + number).randrange(6)


def parse_items(payload: object, arm: str) -> list[dict]:
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    if arm == "batch":
        return [{"text": p, "probability": None} for p in parent.parse_premises(payload, 6)]
    if not isinstance(payload, dict) or set(payload) != {"premises"}:
        raise ValueError("Expected a premises object")
    items = payload["premises"]
    if not isinstance(items, list) or len(items) != 6:
        raise ValueError("Expected exactly six items")
    for item in items:
        if not isinstance(item, dict) or set(item) != {"text", "probability"}:
            raise ValueError("Expected text and probability fields")
        if not isinstance(item["text"], str) or not item["text"].strip():
            raise ValueError("Expected non-empty story text")
        value = item["probability"]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Expected a finite numeric probability")
    # Instruction compliance is audited separately; a high estimate never drops a story.
    return items


def invention_request(arm: str, prefix: str, request_type):
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    system = parent.system_text(prefix, "batch")
    if arm == "format":
        system += "\n\n" + FORMAT
    elif arm in ("full", "tail"):
        system += "\n\n" + FULL
        if arm == "tail":
            system += "\n\n" + TAIL
    return request_type(
        prompt="Create the requested story material.", system=system,
        schema=parent.SCHEMA if arm == "batch" else OBJECT_SCHEMA,
        max_output_tokens=3200, timeout_seconds=600, profile="experiment.invention-contrast.v1",
    )


def expansion_request(item: dict, discovery):
    return discovery.render_request(item["text"], person="third")


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-verbalized-20260911: root task;"):
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
    for path in (
        Path(__file__), HERE / "audit.py", HERE / "RUNBOOK.md", HERE / "SOURCES.md",
        HERE / "sources.json", ROOT / "tests/test_invention_verbalized_experiment.py",
        old_path, PARENT / "registration.json", draws,
        *(ROOT / row["path"] for row in read(HERE / "sources.json")),
    ):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        arm, block = name.rsplit("-", 1)
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
        "token_stop": 120000, "attempt_stop": 16, "selections": selections,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "numbers": numbers, "selections": selections,
        "order": ORDER, "expansions": EXPANSIONS, "requested_model": "gpt-6-astra",
        "effort": "medium", "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "runner_sha256": sha(Path(__file__)), "audit_sha256": sha(HERE / "audit.py"),
        "sources_sha256": sha(HERE / "sources.json"), "binary_sha256": sha(Path(old["binary"])),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "attempt_stop": 16, "token_stop": 120000,
    })
    print({"model_calls": 0, "selections_zero_based": selections, "attempt_ceiling": 16})


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
                    arm, block = name.rsplit("-", 1)
                    items = parse_items(result.parsed, arm)
                    index = manifest["selections"][block]
                    row["selected"] = {
                        "index": index, "text_sha256": text_sha(items[index]["text"]),
                    }
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
            index = manifest["selections"][source_name.rsplit("-", 1)[1]]
            item = parse_items(row["result"]["parsed"], source_name.split("-", 1)[0])[index]
            complete(name, expansion_request(item, discovery), source={
                "parent": source_name, "receipt_sha256": sha(path), "index": index,
                "text_sha256": text_sha(item["text"]),
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
