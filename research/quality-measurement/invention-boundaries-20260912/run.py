"""Frozen chapter input contrast and crossed mechanics inventor/expander experiment."""

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
LOCAL = ROOT / "runs/invention-boundaries-20260912"
PARENT = HERE.with_name("mechanics-fresh-transfer-20260912") / "run.py"
SPEC = importlib.util.spec_from_file_location("boundary_parent", PARENT)
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write = parent.sha, parent.text_sha, parent.read, parent.write
CLAUDE = Path(r"C:\Users\artem\.local\bin\claude.exe")
MODELS = {"astra": "gpt-6-astra", "opus": "claude-opus-5"}
SOURCE_ROOT = ROOT / "runs/discovery-life-scope-20260912"
SOURCE_FILE = SOURCE_ROOT / "sources/2.json"
PLAN_FILE = SOURCE_ROOT / "calls/scoped-2-1.json"
SAVED_REQUEST = SOURCE_ROOT / "requests/scoped-2-1.json"
CHAPTERS = ("chapter-plan", "chapter-source", "chapter-pad", "chapter-both")
MAGIC = ("magic-astra-1", "magic-opus-1", "magic-opus-2", "magic-astra-2")
# Plan names are plan-INVENTOR-EXPANDER-SEED.
PLANS = (
    "plan-astra-astra-1",
    "plan-astra-opus-1",
    "plan-opus-opus-1",
    "plan-opus-astra-1",
    "plan-opus-opus-2",
    "plan-opus-astra-2",
    "plan-astra-astra-2",
    "plan-astra-opus-2",
)
ORDER = CHAPTERS + MAGIC + PLANS
CHAPTER_TASK = (
    "Write the opening chapter of the supplied LitRPG story as finished fiction in third "
    "person, past tense. Develop its connected action, character choices and consequences. "
    "Write 1200-1600 words. Return only the chapter prose, without a title, outline or commentary. "
    "A field named non_story_padding, if present, is inert test padding "
    "and supplies no story facts."
)


def lock():
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-boundaries-20260912: root task;"):
        raise RuntimeError("Task does not own shared-machine lock")


def normalized(value):
    return json.loads(json.dumps(dataclasses.asdict(value)))


def seed(index):
    from litharness.domain.invention import InventionSeed

    return InventionSeed.from_payload(read(LOCAL / "seeds" / f"{index}.json"))


def material_prompt(material):
    return "Story material:\n" + json.dumps(material, ensure_ascii=False, sort_keys=True)


def chapter_material(arm, source, plan):
    if arm == "source":
        return {"premise": source}
    if arm == "plan":
        return {"plan": plan}
    if arm == "both":
        return {"premise": source, "plan": plan}
    if arm != "pad":
        raise ValueError(arm)
    value = {"premise": source, "non_story_padding": ""}
    count = len(material_prompt(chapter_material("both", source, plan))) - len(
        material_prompt(value)
    )
    if count <= 0:
        raise ValueError("No positive padding length")
    value["non_story_padding"] = ("padding " * (count // 8 + 1))[:count]
    return value


def chapter_request(arm):
    from litharness.domain.generation import CompletionRequest

    frozen = read(LOCAL / "nico.json")
    material = chapter_material(arm, frozen["source"], frozen["plan"])
    return CompletionRequest(
        system=seed(0).brief + "\n\n" + CHAPTER_TASK,
        prompt=material_prompt(material),
        schema=parent.DRAFT_SCHEMA,
        max_output_tokens=4200,
        timeout_seconds=600,
    )


def provider_name(name):
    if name not in ORDER:
        raise ValueError(name)
    parts = name.split("-")
    return "astra" if parts[0] == "chapter" else parts[1] if parts[0] == "magic" else parts[2]


def slot_request(name):
    provider_name(name)
    parts = name.split("-")
    if parts[0] == "chapter":
        return chapter_request(parts[1]), {"nico_sha256": sha(LOCAL / "nico.json")}
    if parts[0] == "magic":
        return dataclasses.replace(parent.magic_request(seed(parts[2])), model=None), None
    _, inventor, _, index = parts
    path = LOCAL / "calls" / f"magic-{inventor}-{index}.json"
    row = read(path)
    lineage = {"slot": path.stem, "receipt_sha256": sha(path)}
    if row["status"] != "completed":
        raise RuntimeError("Designated parent did not complete")
    mechanics = row["result"]["parsed"]
    if not parent.valid_fields(mechanics, parent.MAGIC_FIELDS):
        return None, lineage
    return parent.plan_request(seed(index), mechanics), lineage


def claude_auth(environment):
    status = subprocess.run(
        [str(CLAUDE), "auth", "status", "--json"],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    value = json.loads(status.stdout)
    if not (
        value.get("loggedIn")
        and value.get("authMethod") == "claude.ai"
        and value.get("apiProvider") == "firstParty"
    ):
        raise RuntimeError("Claude subscription authentication required")


def prepare():
    from litharness.application import discovery
    from litharness.domain.invention import make_seed
    from litharness.providers.codex_cli import subscription_environment

    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared; never redraw")
    claude_auth(subscription_environment(dict(os.environ)))
    source_record = read(SOURCE_FILE)
    source = source_record["text"]
    original_source = ROOT / source_record["path"]
    if (
        sha(original_source) != source_record["receipt_sha256"]
        or text_sha(source) != source_record["text_sha256"]
        or read(original_source)["result"]["parsed"]["story"] != source
    ):
        raise RuntimeError("Source identity changed")
    saved, current = (
        read(SAVED_REQUEST),
        normalized(discovery.render_request(source, person="third")),
    )
    differences = [k for k in sorted(set(saved) | set(current)) if saved.get(k) != current.get(k)]
    if differences != ["profile"] or (saved["profile"], current["profile"]) != (
        "writer.discovery.v10",
        "writer.discovery.v11",
    ):
        raise RuntimeError("Current discovery differs beyond recorded profile label")
    plan_receipt = read(PLAN_FILE)
    if plan_receipt["status"] != "completed" or plan_receipt["request"] != saved:
        raise RuntimeError("Plan is not the completed result of the saved request")
    plan = plan_receipt["result"]["parsed"]
    discovery.Discovery.from_invention(plan)
    write(
        LOCAL / "nico.json",
        {
            "source": source,
            "plan": plan,
            "source_receipt_sha256": sha(original_source),
            "plan_receipt_sha256": sha(PLAN_FILE),
            "saved_request_sha256": sha(SAVED_REQUEST),
            "current_request": current,
            "request_differences": differences,
        },
    )
    for index in (0, 1, 2):
        write(
            LOCAL / "seeds" / f"{index}.json", make_seed(str(secrets.randbits(2048))).to_jsonable()
        )
    files = {str(p.resolve()): sha(p) for p in (ROOT / "src").rglob("*.py")}
    dependencies = (
        Path(__file__),
        HERE / "RUNBOOK.md",
        PARENT,
        parent.UTILITIES,
        parent.engine.BINARY,
        CLAUDE,
        ROOT / "tests/test_invention_boundaries_experiment.py",
        SOURCE_FILE,
        PLAN_FILE,
        SAVED_REQUEST,
        original_source,
        LOCAL / "nico.json",
    )
    for p in dependencies:
        files[str(p.resolve())] = sha(p)
    for p in (LOCAL / "seeds").glob("*.json"):
        files[str(p.resolve())] = sha(p)
    for name in CHAPTERS + MAGIC:
        request, _ = slot_request(name)
        path = LOCAL / "requests" / f"{name}.json"
        write(path, normalized(request))
        files[str(path.resolve())] = sha(path)
    write(
        LOCAL / "manifest.json",
        {
            "files": files,
            "order": ORDER,
            "attempt_stop": 16,
            "token_stop": 160000,
            "models": MODELS,
        },
    )
    write(
        HERE / "registration.json",
        {
            "manifest_sha256": sha(LOCAL / "manifest.json"),
            "order": ORDER,
            "models": MODELS,
            "source_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "runner_sha256": sha(Path(__file__)),
            "runbook_sha256": sha(HERE / "RUNBOOK.md"),
            "nico_sha256": sha(LOCAL / "nico.json"),
            "seeds": {str(i): sha(LOCAL / "seeds" / f"{i}.json") for i in (0, 1, 2)},
            "static_requests": {n: sha(LOCAL / "requests" / f"{n}.json") for n in CHAPTERS + MAGIC},
            "chapter_prompt_characters": {n: len(slot_request(n)[0].prompt) for n in CHAPTERS},
            "padding_added_input_tolerance": 0.10,
        },
    )
    print("Prepared eight static requests and eight fixed descendants; zero generation calls.")


def provider_for(name, row, receipt):
    from litharness.providers.cli import ClaudeCodeProvider, CommandResult
    from litharness.providers.codex_cli import CodexCliProvider, subscription_environment

    route = provider_name(name)
    if route == "astra":
        return CodexCliProvider(
            binary=str(parent.engine.BINARY),
            model=MODELS[route],
            trace_directory=LOCAL / "transport" / name,
        )
    environment = subscription_environment(dict(os.environ))
    claude_auth(environment)

    def capture(argv, *, timeout, cwd=None, stdin=None):
        row["transport"] = {
            "argv": list(argv),
            "prompt": stdin,
            "system": argv[argv.index("--system-prompt") + 1],
            "native_schema": json.loads(argv[argv.index("--json-schema") + 1]),
            "cwd": cwd,
            "auth_method": "claude.ai",
            "environment_keys": sorted(environment),
        }
        write(receipt, row)
        outcome = subprocess.run(
            list(argv),
            env=environment,
            cwd=cwd,
            input=stdin or "",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        row["transport"].update(
            stdout=outcome.stdout, stderr=outcome.stderr, returncode=outcome.returncode
        )
        if outcome.returncode != 0:
            raise RuntimeError(f"Claude process exited {outcome.returncode}")
        return CommandResult(outcome.returncode, outcome.stdout, outcome.stderr)

    return ClaudeCodeProvider(
        binary=str(CLAUDE), model=MODELS[route], runner=capture, extra_args=("--effort", "medium")
    )


def reported_opus_matches(result):
    # Without modelUsage the adapter falls back to the requested model, not attribution.
    return bool(result["raw"].get("modelUsage")) and result["model"] == MODELS["opus"]


def run():
    lock()
    if (LOCAL / "progress.json").exists() or os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No implicit resume or execution in test environment")
    registration = read(HERE / "registration.json")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    if json.loads(committed) != registration:
        raise RuntimeError("Commit registration first")
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != registration["manifest_sha256"]:
        raise RuntimeError("Manifest drift")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": []}
    write(LOCAL / "progress.json", progress)
    try:
        for name in ORDER:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen input drift")
            request, lineage = slot_request(name)
            receipt = LOCAL / "calls" / f"{name}.json"
            if request is None:
                row = {
                    "name": name,
                    "status": "skipped",
                    "lineage": lineage,
                    "reason": "Invalid designated first parent; no substitution",
                }
                write(receipt, row)
                progress["slots"].append(row)
                write(LOCAL / "progress.json", progress)
                continue
            if progress["tokens"] >= manifest["token_stop"] or progress["attempts"] >= 16:
                raise RuntimeError("Registered ceiling reached")
            path = LOCAL / "requests" / f"{name}.json"
            payload = normalized(request)
            if path.exists() and read(path) != payload:
                raise RuntimeError("Static request drift")
            if not path.exists():
                write(path, payload)
            row = {
                "name": name,
                "request": payload,
                "request_sha256": sha(path),
                "lineage": lineage,
                "provider": provider_name(name),
                "status": "started",
                "started_at": datetime.now(UTC).isoformat(),
            }
            write(receipt, row)
            progress["attempts"] += 1
            write(LOCAL / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            provider = None
            try:
                provider = provider_for(name, row, receipt)
                result = provider.complete(request)
                row.update(status="completed", result=dataclasses.asdict(result))
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown usage")
                progress["tokens"] += result.usage.total
                if provider_name(name) == "opus" and not reported_opus_matches(row["result"]):
                    raise RuntimeError("Claude model attribution missing or mismatched")
            except Exception as error:
                row.update(
                    status="failed",
                    error=str(error),
                    last_attempt=getattr(provider, "last_attempt", None),
                )
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


def audit():
    from litharness.application.discovery import Discovery
    from litharness.providers.codex_schema import prepare_codex_schema

    registration = read(HERE / "registration.json")
    controls = {
        "frozen": {p: sha(Path(p)) == h for p, h in read(LOCAL / "manifest.json")["files"].items()},
        "manifest": {"hash": sha(LOCAL / "manifest.json") == registration["manifest_sha256"]},
    }
    outputs, reading, sessions = [], [], []
    input_totals = {}
    for name in ORDER:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            controls[name] = {"reached": False}
            outputs.append({"name": name, "status": "not_reached"})
            continue
        row = read(path)
        if row["status"] != "completed":
            request, lineage = slot_request(name)
            controls[name] = {
                "valid_skip": row["status"] == "skipped" and request is None,
                "lineage": row["lineage"] == lineage,
            }
            outputs.append({"name": name, "status": row["status"], "receipt_sha256": sha(path)})
            continue
        request, lineage = slot_request(name)
        result = row["result"]
        c = {
            "request": row["request"]
            == read(LOCAL / "requests" / f"{name}.json")
            == normalized(request),
            "hash": row["request_sha256"] == sha(LOCAL / "requests" / f"{name}.json"),
            "lineage": row["lineage"] == lineage,
        }
        raw = result["raw"] if row["provider"] == "astra" else row["transport"]
        c.update(
            prompt=raw["prompt"] == request.prompt,
            system=raw["system"] == request.effective_system,
            returncode=raw["returncode"] == 0,
        )
        if row["provider"] == "astra":
            c.update(
                schema=raw["native_schema"] == prepare_codex_schema(request.schema),
                model=raw["requested_model"] == MODELS["astra"],
                effort=raw["settings"]["model_reasoning_effort"] == "medium",
                ephemeral="--ephemeral" in raw["argv"],
                docs_off="project_doc_max_bytes=0" in raw["argv"],
                memory_off="features.memories=false" in raw["argv"],
            )
            ids = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
        else:
            argv = raw["argv"]
            c.update(
                schema=raw["native_schema"] == request.schema,
                model=argv[argv.index("--model") + 1] == MODELS["opus"],
                reported_model=reported_opus_matches(result),
                effort=argv[argv.index("--effort") + 1] == "medium",
                safe="--safe-mode" in argv,
                ephemeral="--no-session-persistence" in argv,
                tools_off=argv[argv.index("--tools") + 1] == "",
                mcp_off=json.loads(argv[argv.index("--mcp-config") + 1]) == {"mcpServers": {}},
                memory_off=json.loads(argv[argv.index("--settings") + 1])["autoMemoryEnabled"]
                is False,
                subscription=raw["auth_method"] == "claude.ai",
            )
            ids = [result["raw"].get("session_id")]
        controls[name] = c
        sessions.extend(ids)
        fields = result["parsed"]
        valid = parent.valid_fields(fields, request.schema["required"])
        if valid and name.startswith("plan-"):
            try:
                Discovery.from_invention(fields)
            except (ValueError, TypeError, AttributeError):
                valid = False
        fields = fields if isinstance(fields, dict) else {"unparsed": result["text"]}
        outputs.append(
            {
                "name": name,
                "provider": row["provider"],
                "status": row["status"],
                "valid": valid,
                "receipt_sha256": sha(path),
                "lineage": lineage,
                "usage": result["usage"],
                "session_ids": ids,
                "fields": {
                    k: {"sha256": text_sha(v), "words": len(v.split())}
                    for k, v in fields.items()
                    if isinstance(v, str)
                },
            }
        )
        reading.append(
            "# "
            + name
            + "\n\n"
            + "\n\n".join("## " + k + "\n\n" + v for k, v in fields.items() if isinstance(v, str))
        )
        if name in CHAPTERS:
            u = result["usage"]
            input_totals[name] = (
                u["input_tokens"] + u["cache_read_tokens"] + u["cache_write_tokens"]
            )
            if valid:
                (LOCAL / (name + ".md")).write_text(
                    fields["story"] + "\n", encoding="utf-8", newline="\n"
                )
    padding = {"available": set(CHAPTERS) <= input_totals.keys(), "input_tokens": input_totals}
    if padding["available"]:
        added_both = input_totals["chapter-both"] - input_totals["chapter-source"]
        added_pad = input_totals["chapter-pad"] - input_totals["chapter-source"]
        padding.update(
            added_both=added_both,
            added_pad=added_pad,
            matched=added_both > 0 and abs(added_both - added_pad) / added_both <= 0.10,
        )
    completed = sum(o["status"] == "completed" for o in outputs)
    controls["sessions"] = {
        "distinct": bool(all(sessions)) and len(set(sessions)) == len(sessions) == completed
    }
    report = {
        "all_controls_pass": all(all(c.values()) for c in controls.values()),
        "controls": controls,
        "outputs": outputs,
        "padding_placebo": padding,
        "progress": read(LOCAL / "progress.json"),
        "registration_sha256": sha(HERE / "registration.json"),
    }
    write(HERE / "evidence.json", report)
    (LOCAL / "reading.md").write_text("\n\n".join(reading) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "controls_pass": report["all_controls_pass"],
                "completed": completed,
                "progress": report["progress"],
                "padding": padding,
            },
            indent=2,
        )
    )
    if not report["all_controls_pass"]:
        raise RuntimeError("Audit failed; retain first outputs")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
