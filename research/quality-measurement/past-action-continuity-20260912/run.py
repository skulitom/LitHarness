"""Frozen six-call continuation experiment; no scoring or candidate selection."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/past-action-continuity-20260912"
SOURCE = ROOT / (
    "runs/fresh-chapter-review-20260912/provider-traces/"
    "attempt-90ec376bfbbf43b7a010b2973b74f7d3.json"
)
BINARY = Path(r"C:\Users\artem\AppData\Local\OpenAI\Codex\bin\7ac07f4ce733f89a\codex.exe")
RULE = (
    "Before adding a past action or revealing what someone already knew, check it against "
    "their behavior in the accepted prose. Preserve established motives and secrets; an "
    "explanation of the current problem must also make sense of what those people said "
    "and did before."
)
ORDER = ("actual-control-1", "actual-treatment-1", "secret-control-1",
         "secret-treatment-1", "actual-treatment-2", "actual-control-2")
SECRET = (
    "Author directions: third person, Iona's viewpoint. Preserve that Iona disabled the "
    "signal before this scene. She must conceal that fact from Captain Vey until her "
    "brother's escape is confirmed. Do not make Vey complicit.\n\n"
    "Accepted prose:\nIona kept her burned thumb inside her cuff. In the signal room, "
    "Captain Vey asked her to test the transmitter. She turned its dial as slowly as she "
    "could. Her brother needed time to reach the border, and a working signal would send "
    "Vey's patrols after him. She had removed the contact herself before Vey arrived. "
    "If he noticed her burn, she would blame the kettle.\n\n"
    "Now write the next scene, approximately 650 words. Vey demands a repair. Iona "
    "appears to cooperate while stalling. A coded bell finally confirms her brother "
    "has crossed; only then may she decide what to do about the missing contact."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def system_for(system: str, arm: str) -> str:
    if arm == "control":
        return system
    if arm != "treatment":
        raise ValueError(arm)
    first, rest = system.split("\n\n", 1)
    return first + "\n\n" + RULE + "\n\n" + rest


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("fresh-chapter-review-20260912: root task;"):
        raise RuntimeError("Root task does not own the shared-machine lock")


def prepare() -> None:
    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Prepared already; never refresh a registration")
    source = read(SOURCE)
    files = {str(p.resolve()): sha(p) for p in (ROOT / "src").rglob("*.py")}
    for p in (SOURCE, BINARY, Path(__file__), HERE / "RUNBOOK.md",
              ROOT / "tests/test_past_action_experiment.py"):
        files[str(p.resolve())] = sha(p)
    for name in ORDER:
        case, arm, _ = name.split("-")
        system = source["system"] if case == "actual" else (
            "You are drafting one scene of a novel. Write only the scene's prose. "
            "Respect established facts and author directions.\n\n"
            "Continue from the accepted prose without repeating it."
        )
        request = {
            "prompt": source["prompt"] if case == "actual" else SECRET,
            "system": system_for(system, arm), "schema": None,
            "profile": "default", "max_output_tokens": 4096,
            "timeout_seconds": 600, "model": "gpt-6-astra",
        }
        path = LOCAL / "requests" / f"{name}.json"
        write(path, request)
        files[str(path.resolve())] = sha(path)
    manifest = {"files": files, "order": ORDER, "binary": str(BINARY),
                "attempt_stop": 6, "token_stop": 150000}
    write(LOCAL / "manifest.json", manifest)
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "order": ORDER,
        "source_sha256": sha(SOURCE), "binary_sha256": sha(BINARY),
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                   cwd=ROOT, text=True).strip(),
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "requests": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "rule_sha256": text_sha(RULE), "model": "gpt-6-astra", "effort": "medium",
    })
    print("Prepared six requests; no model calls.")


def run() -> None:
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import CodexProvider

    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already dispatched; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No provider execution in test environment")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    if json.loads(committed) != read(HERE / "registration.json"):
        raise RuntimeError("Commit registration before dispatch")
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    provider = CodexProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    progress = {"attempts": 0, "tokens": 0, "status": "running", "slots": []}
    write(LOCAL / "progress.json", progress)
    try:
        for name in ORDER:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen-file drift")
            if progress["attempts"] >= 6 or progress["tokens"] >= 150000:
                raise RuntimeError("Registered ceiling reached")
            request = CompletionRequest(**read(LOCAL / "requests" / f"{name}.json"))
            row = {"name": name, "started_at": datetime.now(UTC).isoformat(),
                   "request": dataclasses.asdict(request), "status": "started"}
            path = LOCAL / "calls" / f"{name}.json"
            write(path, row)
            progress["attempts"] += 1
            write(LOCAL / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            try:
                result = provider.complete(request)
                row.update(status="completed", result=dataclasses.asdict(result))
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown usage")
                progress["tokens"] += result.usage.total
            except Exception as error:
                row.update(status="failed", error=str(error), raw=provider.last_attempt)
                raise
            finally:
                row["finished_at"] = datetime.now(UTC).isoformat()
                write(path, row)
                progress["slots"].append({"name": name, "status": row["status"]})
                write(LOCAL / "progress.json", progress)
            print(f"Completed {name}; cumulative tokens {progress['tokens']}", flush=True)
        progress["status"] = "complete"
    except Exception as error:
        progress.update(status="stopped", error=str(error))
        raise
    finally:
        write(LOCAL / "progress.json", progress)


def audit() -> None:
    registration = read(HERE / "registration.json")
    controls = []
    rows = []
    source = read(SOURCE)
    for name in ORDER:
        path = LOCAL / "requests" / f"{name}.json"
        request = read(path)
        row = read(LOCAL / "calls" / f"{name}.json")
        result = row["result"]
        raw = result["raw"]
        controls.extend([
            sha(path) == registration["requests"][name],
            raw["prompt"] == request["prompt"], raw["system"] == request["system"],
            raw["schema"] is None, raw["returncode"] == 0,
            raw["requested_model"] == "gpt-6-astra",
            raw["settings"]["model_reasoning_effort"] == "medium",
        ])
        case, arm, _ = name.split("-")
        if case == "actual":
            controls.extend([request["prompt"] == source["prompt"],
                             request["system"] == system_for(source["system"], arm)])
        text = result["text"]
        rows.append({"name": name, "receipt_sha256": sha(LOCAL / "calls" / f"{name}.json"),
                     "text_sha256": text_sha(text), "words": len(text.split()),
                     "usage": result["usage"]})
    for arm in ("control", "treatment"):
        controls.append(read(LOCAL / "requests" / f"actual-{arm}-1.json") ==
                        read(LOCAL / "requests" / f"actual-{arm}-2.json"))
    report = {"all_transport_controls_pass": all(controls), "controls": len(controls),
              "progress": read(LOCAL / "progress.json"), "outputs": rows,
              "registration_sha256": sha(HERE / "registration.json")}
    write(HERE / "evidence.json", report)
    print(json.dumps(report, indent=2))
    if not all(controls):
        raise RuntimeError("Audit failed")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
