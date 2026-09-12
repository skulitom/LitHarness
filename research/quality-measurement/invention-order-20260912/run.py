"""Frozen order/pursuit comparison; every first output is retained."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-order-20260912"
PARENT = HERE.with_name("past-action-continuity-20260912") / "run.py"
SPEC = importlib.util.spec_from_file_location("order_utilities", PARENT)
assert SPEC is not None and SPEC.loader is not None
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
sha, text_sha, read, write = engine.sha, engine.text_sha, engine.read, engine.write
ORDER = ("control-1", "opening-1", "pursuit-1", "opening-2", "pursuit-2", "control-2",
         "pursuit-3", "control-3", "opening-3")
PURSUIT = (
    "pursuit: invent a particular person and an undertaking they want to carry out before "
    "an emergency forces their hand. Give their personal reason, a concrete move they "
    "choose to make, and another person's independently wanted outcome that complicates "
    "that move. Choose this before designing their occupation, setting or powers. "
    "Develop opening, world and growth from this pursuit."
)


def request_for(seed, arm: str):
    from litharness.application import discovery

    request = discovery.render_request("", person="third", seed=seed)
    if arm == "control":
        return request
    if arm not in ("opening", "pursuit"):
        raise ValueError(arm)
    lines = request.system.split("\n")
    world = next(i for i, line in enumerate(lines) if line.startswith("world: "))
    assert lines[world + 1].startswith("opening: ")
    lines[world], lines[world + 1] = lines[world + 1], lines[world]
    fields = ["opening", "world", "growth"]
    if arm == "pursuit":
        lines.insert(world, PURSUIT)
        assert "in the three fields" in lines[-1]
        lines[-1] = lines[-1].replace("in the three fields", "in the four fields")
        fields.insert(0, "pursuit")
    schema = {"type": "object", "additionalProperties": False, "required": fields,
              "properties": {key: {"type": "string"} for key in fields}}
    return dataclasses.replace(request, system="\n".join(lines), schema=schema)


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-order-20260912: root task;"):
        raise RuntimeError("Task does not own the shared-machine lock")


def provider_for(binary: str):
    from litharness.providers.codex_cli import CodexCliProvider

    return CodexCliProvider(binary=binary, trace_directory=LOCAL / "transport")


def prepare() -> None:
    from litharness.domain.invention import make_seed

    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared; never refresh a registration")
    seeds = [make_seed(str(secrets.randbits(2048))) for _ in range(3)]
    files = {str(p.resolve()): sha(p) for p in (ROOT / "src").rglob("*.py")}
    for p in (engine.BINARY, PARENT, Path(__file__), HERE / "RUNBOOK.md",
              ROOT / "tests/test_invention_order_experiment.py"):
        files[str(p.resolve())] = sha(p)
    for index, seed in enumerate(seeds, 1):
        path = LOCAL / "seeds" / f"{index}.json"
        write(path, seed.to_jsonable())
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        arm, index = name.split("-")
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request_for(seeds[int(index) - 1], arm)))
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {"files": files, "order": ORDER,
          "binary": str(engine.BINARY), "attempt_stop": 9, "token_stop": 100000})
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "order": ORDER,
        "runner_sha256": sha(Path(__file__)), "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "utility_sha256": sha(PARENT), "binary_sha256": sha(engine.BINARY),
        "pursuit_instruction_sha256": text_sha(PURSUIT),
        "seeds": {str(i): sha(LOCAL / "seeds" / f"{i}.json") for i in (1, 2, 3)},
        "requests": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                   cwd=ROOT, text=True).strip(),
    })
    print("Prepared nine discovery requests; no model calls.")


def run() -> None:
    from litharness.domain.generation import CompletionRequest

    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already dispatched; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No provider execution in test environment")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    registration = read(HERE / "registration.json")
    if json.loads(committed) != registration:
        raise RuntimeError("Commit registration before dispatch")
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != registration["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    provider = provider_for(manifest["binary"])
    progress = {"attempts": 0, "tokens": 0, "status": "running", "slots": []}
    write(LOCAL / "progress.json", progress)
    try:
        for name in ORDER:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen-file drift")
            if (progress["attempts"] >= manifest["attempt_stop"]
                    or progress["tokens"] >= manifest["token_stop"]):
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
    from litharness.application.discovery import Discovery
    from litharness.domain.generation import CompletionRequest
    from litharness.domain.invention import InventionSeed
    from litharness.providers.codex_schema import prepare_codex_schema

    registration = read(HERE / "registration.json")
    controls, outputs, reading, sessions = {}, [], [], []
    for name in ORDER:
        arm, index = name.split("-")
        seed = InventionSeed.from_payload(read(LOCAL / "seeds" / f"{index}.json"))
        path = LOCAL / "requests" / f"{name}.json"
        request = read(path)
        row = read(LOCAL / "calls" / f"{name}.json")
        result = row["result"]
        raw = result["raw"]
        expected = request_for(seed, arm)
        controls[name] = {
            "frozen_request": sha(path) == registration["requests"][name],
            "renderer": request == json.loads(json.dumps(dataclasses.asdict(expected))),
            "captured_prompt": raw["prompt"] == request["prompt"],
            "captured_schema": raw["schema"] == request["schema"],
            "effective_system": raw["system"] == CompletionRequest(**request).effective_system,
            "native_schema": raw["native_schema"] == prepare_codex_schema(request["schema"]),
            "native_order": (
                list(raw["native_schema"]["properties"]) == request["schema"]["required"]
            ),
            "returncode": raw["returncode"] == 0,
            "model_request": raw["requested_model"] == "gpt-6-astra",
            "effort": raw["settings"]["model_reasoning_effort"] == "medium",
            "ephemeral": "--ephemeral" in raw["argv"],
            "project_docs_off": "project_doc_max_bytes=0" in raw["argv"],
            "memory_off": "features.memories=false" in raw["argv"],
        }
        session = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
        sessions.extend(session)
        fields = result["parsed"] or {}
        try:
            Discovery.from_invention(fields)
            valid = (set(fields) == set(request["schema"]["required"])
                     and all(isinstance(v, str) and v.strip() for v in fields.values()))
        except (ValueError, TypeError, AttributeError):
            valid = False
        outputs.append({"name": name, "receipt_sha256": sha(LOCAL / "calls" / f"{name}.json"),
                        "valid": valid, "usage": result["usage"], "session_ids": session,
                        "returned_order": list(fields),
                        "order_compliant": list(fields) == request["schema"]["required"],
                        "fields": {k: {"sha256": text_sha(v), "words": len(v.split())}
                                   for k, v in fields.items() if isinstance(v, str)}})
        reading.append("# " + name + "\n\n" + "\n\n".join(
            "## " + k + "\n\n" + v for k, v in fields.items() if isinstance(v, str)))
    controls["distinct_sessions"] = {"pass": len(sessions) == len(set(sessions)) == len(ORDER)}
    report = {"all_transport_controls_pass": all(all(v.values()) for v in controls.values()),
              "controls": controls, "outputs": outputs,
              "progress": read(LOCAL / "progress.json"),
              "registration_sha256": sha(HERE / "registration.json")}
    write(HERE / "evidence.json", report)
    (LOCAL / "reading.md").write_text("\n\n".join(reading) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"controls_pass": report["all_transport_controls_pass"],
                      "outputs": len(outputs), "progress": report["progress"]}, indent=2))
    if not report["all_transport_controls_pass"]:
        raise RuntimeError("Audit failed; retain outputs and inspect the failed control")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
