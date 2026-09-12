"""Fresh empty-brief mechanics transfer, with two preassigned opening chapters."""

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
LOCAL = ROOT / "runs/mechanics-fresh-transfer-20260912"
UTILITIES = HERE.with_name("past-action-continuity-20260912") / "run.py"
SPEC = importlib.util.spec_from_file_location("mechanics_utilities", UTILITIES)
assert SPEC is not None and SPEC.loader is not None
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
sha, text_sha, read, write = engine.sha, engine.text_sha, engine.read, engine.write
MAGIC_ORDER = ("magic-staged-1", "magic-staged-2", "magic-staged-3")
PLAN_ORDER = ("plan-direct-1", "plan-staged-1", "plan-staged-2", "plan-direct-2",
              "plan-direct-3", "plan-staged-3")
ORDER = MAGIC_ORDER + PLAN_ORDER + ("draft-staged-1", "draft-direct-1")
MAGIC_TASK = (
    "Design one coherent magic discipline for a LitRPG novel. Specify what a novice can "
    "do, its operative rule and limitation, how capability develops, and a later extension. "
    "Describe concrete mechanics in 250-350 words total. Invent no protagonist, setting, "
    "plot or scene. Respect any supplied pursuit as context when present.\n"
    "novice: the initial supernatural operation and how it is performed.\n"
    "limitation: the operative restriction or cost and what the novice cannot yet do.\n"
    "advancement: how the discipline is acquired and how greater capability is earned.\n"
    "extension: a later capability and the new actions it permits."
)
MAGIC_FIELDS = ("novice", "limitation", "advancement", "extension")
MAGIC_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": list(MAGIC_FIELDS),
    "properties": {key: {"type": "string"} for key in MAGIC_FIELDS},
}


def magic_request(seed):
    from litharness.domain.generation import CompletionRequest

    return CompletionRequest(
        system=seed.brief + "\n\n" + MAGIC_TASK,
        prompt="No story pursuit is supplied.",
        schema=MAGIC_SCHEMA, model="gpt-6-astra", max_output_tokens=1400, timeout_seconds=600,
    )


def plan_request(seed, mechanics=None):
    from litharness.application import discovery

    brief = "" if mechanics is None else json.dumps({"magic": mechanics}, ensure_ascii=False)
    return discovery.render_request(
        brief, person="third", seed=seed,
    )


DRAFT_TASK = (
    "Write the opening chapter of the supplied LitRPG story proposal as finished fiction "
    "in third person, past tense. Dramatize the connected action described in opening, "
    "using world and growth as background constraints. Write 1200-1600 words. "
    "Return only the chapter prose, without a title, outline or commentary."
)
DRAFT_SCHEMA = {
    "type": "object", "properties": {"story": {"type": "string"}},
    "required": ["story"], "additionalProperties": False,
}


def draft_request(seed, plan):
    from litharness.domain.generation import CompletionRequest

    return CompletionRequest(
        system=seed.brief + "\n\n" + DRAFT_TASK,
        prompt="Story proposal:\n" + json.dumps(plan, ensure_ascii=False, sort_keys=True),
        schema=DRAFT_SCHEMA, model="gpt-6-astra", max_output_tokens=4200, timeout_seconds=600,
    )


def valid_fields(value, fields) -> bool:
    return (isinstance(value, dict) and set(value) == set(fields)
            and all(isinstance(v, str) and v.strip() for v in value.values()))


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("mechanics-fresh-transfer-20260912: root task;"):
        raise RuntimeError("Task does not own shared-machine lock")


def provider_for(binary: str):
    from litharness.providers.codex_cli import CodexCliProvider

    return CodexCliProvider(binary=binary, trace_directory=LOCAL / "transport")


def inputs(index: str):
    from litharness.domain.invention import InventionSeed

    return InventionSeed.from_payload(read(LOCAL / "seeds" / f"{index}.json"))


def slot_request(name: str):
    from litharness.application.discovery import Discovery

    if name not in ORDER:
        raise ValueError(name)
    stage, arm, index = name.split("-")
    seed = inputs(index)
    if stage == "magic":
        return magic_request(seed), None
    if stage == "plan" and arm == "direct":
        return plan_request(seed), None
    parent_stage = "magic" if stage == "plan" else "plan"
    parent = LOCAL / "calls" / f"{parent_stage}-{arm}-{index}.json"
    receipt = read(parent)
    lineage = {"slot": parent.stem, "receipt_sha256": sha(parent)}
    if receipt.get("status") == "skipped":
        return None, lineage
    if receipt.get("status") != "completed":
        raise RuntimeError("Designated parent did not complete")
    source = receipt["result"]["parsed"]
    fields = MAGIC_FIELDS if stage == "plan" else ("world", "opening", "growth")
    if not valid_fields(source, fields):
        return None, lineage
    if stage == "plan":
        return plan_request(seed, source), lineage
    try:
        Discovery.from_invention(source)
    except (ValueError, TypeError, AttributeError):
        return None, lineage
    return draft_request(seed, source), lineage


def prepare() -> None:
    from litharness.domain.invention import make_seed

    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared; do not redraw inputs")
    files = {str(p.resolve()): sha(p) for p in (ROOT / "src").rglob("*.py")}
    for p in (engine.BINARY, UTILITIES, Path(__file__), HERE / "RUNBOOK.md",
              HERE.with_name("mechanics-isolation-20260912") / "run.py",
              ROOT / "tests/test_mechanics_fresh_transfer_experiment.py"):
        files[str(p.resolve())] = sha(p)
    for index in (1, 2, 3):
        seed_path = LOCAL / "seeds" / f"{index}.json"
        write(seed_path, make_seed(str(secrets.randbits(2048))).to_jsonable())
        files[str(seed_path.resolve())] = sha(seed_path)
    static = MAGIC_ORDER + tuple(n for n in PLAN_ORDER if "-direct-" in n)
    for name in static:
        request, lineage = slot_request(name)
        assert lineage is None
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request))
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {"files": files, "order": ORDER,
          "binary": str(engine.BINARY), "attempt_stop": 11, "token_stop": 90000})
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "order": ORDER,
        "runner_sha256": sha(Path(__file__)), "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "utility_sha256": sha(UTILITIES), "binary_sha256": sha(engine.BINARY),
        "mechanics_task_sha256": text_sha(MAGIC_TASK),
        "draft_task_sha256": text_sha(DRAFT_TASK),
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                   cwd=ROOT, text=True).strip(),
        "seeds": {str(i): sha(LOCAL / "seeds" / f"{i}.json") for i in (1, 2, 3)},
        "static_requests": {n: sha(LOCAL / "requests" / f"{n}.json") for n in static},
    })
    print("Prepared six static requests and five fixed descendant slots; zero calls.")


def run() -> None:
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
            request, lineage = slot_request(name)
            if request is None:
                row = {"name": name, "status": "skipped", "lineage": lineage,
                       "reason": "Invalid or skipped designated parent; no replacement"}
                write(LOCAL / "calls" / f"{name}.json", row)
                progress["slots"].append(row)
                write(LOCAL / "progress.json", progress)
                continue
            if (progress["attempts"] >= manifest["attempt_stop"]
                    or progress["tokens"] >= manifest["token_stop"]):
                raise RuntimeError("Registered ceiling reached")
            path = LOCAL / "requests" / f"{name}.json"
            serialized = json.loads(json.dumps(dataclasses.asdict(request)))
            if path.exists():
                if read(path) != serialized:
                    raise RuntimeError("Prepared request changed")
            else:
                write(path, serialized)
            row = {"name": name, "started_at": datetime.now(UTC).isoformat(),
                   "request": serialized, "request_sha256": sha(path),
                   "lineage": lineage, "status": "started"}
            receipt = LOCAL / "calls" / f"{name}.json"
            write(receipt, row)
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
                write(receipt, row)
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
    from litharness.providers.codex_schema import prepare_codex_schema

    controls, outputs, reading, sessions = {}, [], [], []
    registration = read(HERE / "registration.json")
    controls["frozen_inputs"] = {
        p: sha(Path(p)) == h for p, h in read(LOCAL / "manifest.json")["files"].items()
    }
    controls["manifest"] = {
        "hash": sha(LOCAL / "manifest.json") == registration["manifest_sha256"],
        "seeds_distinct": len({inputs(str(i)).brief for i in (1, 2, 3)}) == 3,
    }
    for name in ORDER:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            controls[name] = {"reached": False}
            outputs.append({"name": name, "status": "not_reached"})
            continue
        row = read(path)
        request, lineage = slot_request(name)
        if row["status"] == "skipped":
            controls[name] = {"skip_parent": request is None, "lineage": lineage == row["lineage"]}
            outputs.append({"name": name, "status": "skipped", "receipt_sha256": sha(path)})
            continue
        if row["status"] != "completed":
            controls[name] = {"completed": False}
            outputs.append({"name": name, "status": row["status"], "receipt_sha256": sha(path)})
            continue
        assert request is not None
        prepared = read(LOCAL / "requests" / f"{name}.json")
        result, raw = row["result"], row["result"]["raw"]
        controls[name] = {
            "renderer": prepared == json.loads(json.dumps(dataclasses.asdict(request))),
            "receipt_request": prepared == row["request"],
            "saved_request_hash": row["request_sha256"] == sha(LOCAL / "requests" / f"{name}.json"),
            "lineage": lineage == row["lineage"],
            "captured_prompt": raw["prompt"] == request.prompt,
            "captured_schema": raw["schema"] == request.schema,
            "effective_system": raw["system"] == request.effective_system,
            "native_schema": raw["native_schema"] == prepare_codex_schema(request.schema),
            "returncode": raw["returncode"] == 0,
            "model_request": raw["requested_model"] == "gpt-6-astra",
            "effort": raw["settings"]["model_reasoning_effort"] == "medium",
            "ephemeral": "--ephemeral" in raw["argv"],
            "project_docs_off": "project_doc_max_bytes=0" in raw["argv"],
            "memory_off": "features.memories=false" in raw["argv"],
        }
        if name in registration["static_requests"]:
            controls[name]["frozen_static"] = (
                sha(LOCAL / "requests" / f"{name}.json") == registration["static_requests"][name]
            )
        session = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
        sessions.extend(session)
        fields = result["parsed"]
        valid = valid_fields(fields, request.schema["required"])
        if valid and name.startswith("plan-"):
            try:
                Discovery.from_invention(fields)
            except (ValueError, TypeError, AttributeError):
                valid = False
        fields = fields if isinstance(fields, dict) else {"unparsed": result["text"]}
        outputs.append({"name": name, "status": row["status"], "receipt_sha256": sha(path),
                        "valid": valid, "usage": result["usage"], "session_ids": session,
                        "lineage": lineage, "returned_order": list(fields),
                        "fields": {k: {"sha256": text_sha(v), "words": len(v.split())}
                                   for k, v in fields.items() if isinstance(v, str)}})
        reading.append("# " + name + "\n\n" + "\n\n".join(
            "## " + k + "\n\n" + v for k, v in fields.items() if isinstance(v, str)))
        if name.startswith("draft-") and valid:
            (LOCAL / (name + ".md")).write_text(fields["story"] + "\n", encoding="utf-8",
                                                newline="\n")
    completed = sum(o["status"] == "completed" for o in outputs)
    controls["sessions"] = {"distinct": len(sessions) == len(set(sessions)) == completed}
    report = {"all_controls_pass": all(all(v.values()) for v in controls.values()),
              "controls": controls, "outputs": outputs, "progress": read(LOCAL / "progress.json"),
              "registration_sha256": sha(HERE / "registration.json")}
    write(HERE / "evidence.json", report)
    (LOCAL / "reading.md").write_text("\n\n".join(reading) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"controls_pass": report["all_controls_pass"],
                      "completed": completed, "progress": report["progress"]}, indent=2))
    if not report["all_controls_pass"]:
        raise RuntimeError("Audit failed; inspect failed controls without replacing outputs")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
