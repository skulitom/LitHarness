"""Frozen premise-batch contrasts, preselected slots, and unchanged discovery expansion."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-contrast-20260911"
SOURCE = LOCAL / "source"
ARMS = ("single", "batch", "contrast", "representative", "placebo")
ORDER = tuple(f"{a}-1" for a in ARMS) + tuple(f"{a}-2" for a in reversed(ARMS))
EXPANSIONS = ("single-1", "contrast-1", "contrast-2", "single-2")
CONTRAST = (
    "Make the six premises differ substantially in protagonist, setting, central conflict, "
    "and the way power growth drives the plot."
)
REPRESENTATIVE = "Use a representative sample."
PLACEBO = "Return the requested output."
BASE = (
    "Invent original LitRPG story premises in portal fantasy, isekai, or system apocalypse. "
    "Write 80-120 words per premise. Each premise must identify its protagonist, setting, "
    "central conflict, first consequential use of a power, and how power growth drives "
    "further events. Return story material rather than advice."
)
SCHEMA = {
    "type": "object", "properties": {
        "premises": {"type": "array", "items": {"type": "string"}},
    }, "required": ["premises"], "additionalProperties": False,
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def selected_index(number: str) -> int:
    return random.Random("invention-contrast.v1:" + number).randrange(6)


def parse_premises(payload: object, count: int) -> list[str]:
    if not isinstance(payload, dict) or set(payload) != {"premises"}:
        raise ValueError("Expected a premises object")
    premises = payload["premises"]
    if not isinstance(premises, list) or len(premises) != count:
        raise ValueError(f"Expected exactly {count} premises")
    if any(not isinstance(p, str) or not p.strip() for p in premises):
        raise ValueError("Every premise must be non-empty text")
    return premises


def system_text(prefix: str, arm: str) -> str:
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    count = 1 if arm == "single" else 6
    parts = [prefix, BASE, f"Return exactly {count} {'premise' if count == 1 else 'premises' }."]
    if arm in ("contrast", "representative", "placebo"):
        parts.append(CONTRAST)
    if arm == "representative":
        parts.append(REPRESENTATIVE)
    elif arm == "placebo":
        parts.append(PLACEBO)
    return "\n\n".join(parts)


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-contrast-20260911: root task;"):
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
    return discovery, invention, CompletionRequest, CodexCliProvider


def prepare() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; never refresh after dispatch")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(["git", "ls-files", "src"], cwd=ROOT, text=True).splitlines()
    for name in paths:
        target = SOURCE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(["git", "show", f"{revision}:{name}"], cwd=ROOT))
    _, invention, CompletionRequest, _ = imports()
    seed_file = LOCAL / "draws.json"
    if not seed_file.exists():
        write(seed_file, {str(b): str(secrets.randbits(2048)) for b in (1, 2)})
    numbers = read(seed_file)
    selections = {b: selected_index(n) for b, n in numbers.items()}
    binary = Path(read(ROOT / "runs/invention-nonce-20260911/manifest.json")["binary"])
    files = {
        str(p.resolve()): sha(p) for p in SOURCE.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    for p in (Path(__file__), HERE / "RUNBOOK.md", HERE / "sources.json", HERE / "SOURCES.md",
              ROOT / "uv.lock", ROOT / "tools/generation_trace.py", binary, seed_file):
        files[str(p.resolve())] = sha(p)
    for name in ORDER:
        arm, block = name.rsplit("-", 1)
        seed = invention.make_seed(numbers[block])
        request = CompletionRequest(
            prompt="Create the requested story material.", system=system_text(seed.brief, arm),
            schema=SCHEMA, max_output_tokens=3200, timeout_seconds=600,
            profile="experiment.invention-contrast.v1",
        )
        for path, data in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{block}.json", seed.to_jsonable()),
        ):
            write(path, data)
            files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "expansions": EXPANSIONS, "files": files,
        "binary": str(binary), "token_stop": 100000, "attempt_stop": 14,
        "selections": selections,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "base_revision": revision,
        "order": ORDER, "expansions": EXPANSIONS, "selections": selections,
        "numbers": numbers, "model": "gpt-6-astra", "effort": "medium",
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "sources_sha256": sha(HERE / "sources.json"),
        "binary_sha256": sha(binary),
    })
    print({"prepared_generations": len(ORDER), "expansion_ceiling": len(EXPANSIONS),
           "selections_zero_based": selections, "model_calls": 0})


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Do not run a provider experiment inside the test environment")
    discovery, _, CompletionRequest, CodexCliProvider = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)

    def complete(name: str, request, *, count: int | None, source: dict | None = None) -> None:
        lock()
        if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
            raise RuntimeError("Frozen-file drift")
        if (progress["tokens"] >= manifest["token_stop"]
                or progress["attempts"] >= manifest["attempt_stop"]):
            raise RuntimeError("Registered bound reached")
        path = LOCAL / "requests" / f"{name}.json"
        if source is not None:
            write(path, dataclasses.asdict(request))
        elif read(path) != dataclasses.asdict(request):
            raise RuntimeError("Prepared request changed")
        row = {"request": dataclasses.asdict(request), "request_sha256": sha(path),
               "status": "started", "started_at": datetime.now(UTC).isoformat(), "source": source}
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
                if count is None:
                    discovery.Discovery.from_invention(result.parsed)
                else:
                    premises = parse_premises(result.parsed, count)
                    block = name.rsplit("-", 1)[1]
                    index = 0 if count == 1 else manifest["selections"][block]
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
            complete(name, CompletionRequest(**read(LOCAL / "requests" / f"{name}.json")),
                     count=1 if name.startswith("single-") else 6)
        for parent in EXPANSIONS:
            path = LOCAL / "calls" / f"{parent}.json"
            row = read(path)
            name = f"expand-{parent}"
            if row.get("validation") != "passed":
                progress["slots"].append({"name": name, "status": "skipped_invalid_parent"})
                write(LOCAL / "progress.json", progress)
                continue
            count = 1 if parent.startswith("single-") else 6
            premises = parse_premises(row["result"]["parsed"], count)
            index = row["selected"]["index"]
            complete(name, discovery.render_request(premises[index], person="third"), count=None,
                     source={"parent": parent, "receipt_sha256": sha(path), "index": index,
                             "text_sha256": text_sha(premises[index])})
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
