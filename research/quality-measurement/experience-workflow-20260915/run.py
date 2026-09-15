"""Frozen production workflow comparison, with a recording-only provider boundary."""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import sysconfig
import venv
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/experience-workflow-20260915"
REVISIONS = {"A": "294e93e", "B": "7b0ebc4"}
BINARY = Path("C:/Users/artem/AppData/Local/OpenAI/Codex/bin/bffc5354119c8421/codex.exe")
INPUTS = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
LIMITS = {
    "calls": 240,
    "tokens": 4000000,
    "seconds": 14400,
    "book_calls": 45,
    "ticks_per_phase": 20,
}
PHASES = (
    "concept",
    "new",
    "seed",
    "accept-seed",
    "chapter1",
    "drain1",
    "grow1",
    "accept-grow1",
    "chapter2",
    "drain2",
)
OWNER = "experience-workflow-20260915: root task;"


def now():
    return datetime.now(UTC).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def serial(value):
    return json.loads(json.dumps(dataclasses.asdict(value)))


def order(phase):
    step = PHASES.index(phase)
    return tuple(
        f"{arm}{index}" for index in INPUTS for arm in ("AB" if (int(index) + step) % 2 else "BA")
    )


def book_root(book):
    if len(book) != 2 or book[0] not in REVISIONS or book[1] not in INPUTS:
        raise ValueError("Unknown registered book")
    return LOCAL / "books" / book


def python_for(arm):
    return LOCAL / "runtimes" / arm / "Scripts/python.exe"


def environment(book):
    # Provider transport applies its narrower subscription allowlist again.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("LITHARNESS_", "ANTHROPIC_", "OPENAI_"))
        and key.upper() not in {"PYTHONPATH", "PYTHONHOME", "PYTEST_CURRENT_TEST"}
    }
    env.update(
        LITHARNESS_PROVIDER="codex",
        LITHARNESS_CODEX_BINARY=str(BINARY),
        LITHARNESS_DATABASE=str(book_root(book) / "book.db"),
        LITHARNESS_CODEX_TRACE_DIR=str(book_root(book) / "transport"),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
    )
    return env


def lock():
    if not (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig").startswith(OWNER):
        raise RuntimeError("This task does not own the machine lock")


def verify_frozen():
    manifest = read(LOCAL / "manifest.json")
    for path, expected in manifest["files"].items():
        if sha(path) != expected:
            raise RuntimeError(f"Frozen input changed: {path}")
    return manifest


def prepare():
    lock()
    if LOCAL.exists():
        raise RuntimeError("Existing experiment root: never overwrite or implicitly resume")
    LOCAL.mkdir(parents=True)
    files = [
        Path(__file__),
        HERE / "RUNBOOK.md",
        HERE / "inputs.json",
        ROOT / "tests/test_experience_workflow.py",
        BINARY,
        ROOT / "uv.lock",
    ]
    for arm, revision in REVISIONS.items():
        archive = LOCAL / f"source-{arm}.zip"
        subprocess.run(
            [
                "git",
                "archive",
                "--format=zip",
                f"--output={archive}",
                revision,
                "src",
                "migrations",
                "pyproject.toml",
                "uv.lock",
            ],
            cwd=ROOT,
            check=True,
        )
        source = LOCAL / "sources" / arm
        with zipfile.ZipFile(archive) as packed:
            packed.extractall(source)
        runtime = LOCAL / "runtimes" / arm
        venv.EnvBuilder(with_pip=False).create(runtime)
        # A plain path entry does not process the shared directory's editable-install .pth.
        # Native MCP children use this same interpreter after PYTHONPATH is stripped.
        pth = runtime / "Lib/site-packages/experiment-source.pth"
        pth.write_text(
            str(source / "src") + "\n" + sysconfig.get_path("purelib") + "\n", encoding="utf-8"
        )
        files += [archive, pth, runtime / "pyvenv.cfg", python_for(arm)]
        files += [path for path in source.rglob("*") if path.is_file()]
        probe = subprocess.run(
            [
                str(python_for(arm)),
                "-c",
                "import json,litharness,litharness_contracts; "
                "print(json.dumps({'source':litharness.__file__,'contracts':litharness_contracts.__file__}))",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env=environment(f"{arm}1"),
        )
        origin = json.loads(probe.stdout)
        if not Path(origin["source"]).is_relative_to(source):
            raise RuntimeError("Runtime imported the live checkout")
        write(LOCAL / f"runtime-{arm}.json", origin)
    for index, value in INPUTS.items():
        seed = str(secrets.randbits(2048))
        for arm in REVISIONS:
            destination = book_root(f"{arm}{index}")
            destination.mkdir(parents=True)
            path = destination / "brief.txt"
            path.write_text(value["premise"], encoding="utf-8")
            write(destination / "seed.json", {"label": seed})
            files += [path, destination / "seed.json"]
    manifest = {
        "files": {str(path): sha(path) for path in files},
        "revisions": REVISIONS,
        "limits": LIMITS,
        "order": {phase: order(phase) for phase in PHASES},
    }
    write(LOCAL / "manifest.json", manifest)
    write(HERE / "registration.json", manifest | {"manifest_sha256": sha(LOCAL / "manifest.json")})
    claim("registered")
    print("Prepared frozen source archives and isolated runtimes; no provider calls.")


def claim(status):
    artifacts = [
        {
            "kind": "registration",
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha(path),
        }
        for path in (HERE / "RUNBOOK.md", HERE / "registration.json")
    ]
    if status == "observed":
        artifacts.append(
            {
                "kind": "derived_result",
                "path": str((HERE / "evidence.json").relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha(HERE / "evidence.json"),
            }
        )
    write(
        HERE / "claim.json",
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": "experience-production-workflow-20260915",
            "status": status,
            "statement": "The frozen whole-workflow comparison records generated intent, planning "
            "and reached chapter outputs under its production controls; "
            "no quality effect is licensed.",
            "artifacts": artifacts,
        },
    )


def base_args(book):
    return [
        "--database",
        str(book_root(book) / "book.db"),
        "--writer",
        "halloran",
        "--holder",
        "experience-workflow",
        "--chapter-scenes",
        "1",
        "--arc-chapters",
        "6",
        "--target-words",
        "1400",
        "--max-invocations-per-day",
        "45",
        "--max-tokens-per-day",
        "1500000",
    ]


def command(book, phase):
    root = book_root(book)
    if phase == "concept":
        return [
            "concept",
            "--brief-file",
            str(root / "brief.txt"),
            "--seed",
            read(root / "seed.json")["label"],
            "--person",
            "third",
            "--scenes",
            "6",
            "--out",
            str(root / "concept"),
        ]
    if phase == "new":
        return [
            "new",
            INPUTS[book[1]]["title"],
            "--premise",
            INPUTS[book[1]]["premise"],
            "--concept",
            str(root / "concept/concept.json"),
            "--scenes",
            "6",
            "--person",
            "third",
            "--book",
            f"experience-{book}",
            "--branch",
            "main",
        ]
    if phase in {"seed", "grow1"}:
        return ["architect", "seed"] if phase == "seed" else ["architect", "grow", "--scene", "1"]
    if phase.startswith("accept-"):
        return ["world", "accept"]
    if phase in {"chapter1", "chapter2", "drain1", "drain2"}:
        return ["tick"]
    raise ValueError(phase)


def admission(state, book, at):
    calls = state["calls"]
    if state.get("stop") or any(row["status"] != "completed" for row in calls):
        return "previous failed or interrupted call"
    if len(calls) >= LIMITS["calls"]:
        return "global call ceiling"
    if sum(row["tokens"] for row in calls) >= LIMITS["tokens"]:
        return "global token ceiling"
    if (
        datetime.fromisoformat(at) - datetime.fromisoformat(state["started_at"])
    ).total_seconds() >= (LIMITS["seconds"]):
        return "elapsed-time ceiling"
    if state.get("books", {}).get(book, {}).get("status") == "stopped":
        return "book stopped"
    if sum(row["book"] == book for row in calls) >= LIMITS["book_calls"]:
        return "book call ceiling"
    return None


def install_recorder(book, phase):
    from litharness.providers.base import ProviderUnavailable
    from litharness.providers.codex_cli import CodexCliProvider
    from litharness.providers.codex_tools import validate_allowances

    original = CodexCliProvider.complete

    def recorded(provider, request):
        lock()
        verify_frozen()
        state = read(LOCAL / "progress.json")
        at = now()
        reason = admission(state, book, at)
        if reason:
            if reason.startswith("book"):
                state["books"][book]["status"] = "stopped"
                state["books"][book]["reason"] = reason
            else:
                state["stop"] = reason
            write(LOCAL / "progress.json", state)
            raise ProviderUnavailable(reason)
        if request.allowed_tools:
            validate_allowances(request.allowed_tools)
            if not all(item.startswith("Bash(litharness world ") for item in request.allowed_tools):
                raise RuntimeError("Non-world tools outside this experiment")
        number = len(state["calls"]) + 1
        path = LOCAL / "calls" / f"{number:04d}-{book}.json"
        row = {
            "number": number,
            "book": book,
            "phase": phase,
            "started_at": at,
            "profile": request.profile,
            "request": serial(request),
            "status": "started",
            "previous_receipt_sha256": sha(LOCAL / state["calls"][-1]["path"])
            if state["calls"]
            else None,
        }
        write(path, row)
        meta = {key: row[key] for key in ("number", "book", "phase", "profile", "status")}
        meta.update(path=str(path.relative_to(LOCAL)), tokens=0)
        state["calls"].append(meta)
        write(LOCAL / "progress.json", state)
        print(f"CALL {number} {book} {phase} {request.profile}", flush=True)
        try:
            result = original(provider, request)
            row.update(status="completed", finished_at=now(), result=serial(result))
            meta.update(status="completed", tokens=result.usage.total)
        except BaseException as error:
            row.update(
                status="failed",
                finished_at=now(),
                error=repr(error),
                raw=provider.last_attempt,
                usage_unknown=True,
            )
            meta["status"] = "failed"
            state["stop"] = "provider failure; preserve unknown usage"
            raise
        finally:
            write(path, row)
            write(LOCAL / "progress.json", state)
        return result

    CodexCliProvider.complete = recorded


def metadata(book):
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.jobs import JobStatus
    from litharness.domain.nodes import NodeKind

    database = book_root(book) / "book.db"
    if not database.exists():
        return {"accepted": 0, "pending": 0, "terminal": 0}
    with SqliteStore.open(database) as store:
        branches = store.branches()
        head = store.head(branches[0][0], branches[0][1]) if branches else None
        scenes = [node for node in head.nodes if node.kind is NodeKind.SCENE] if head else []
        completed = [node for node in scenes if (node.content or "").strip()]
        jobs = {
            status.value: len(store.jobs_by_status(status, limit=10000)) for status in JobStatus
        }
        return {
            "accepted": len(completed),
            "head": head.revision_id if head else None,
            "scene_hashes": {
                node.logical_id: hashlib.sha256(node.content.encode()).hexdigest()
                for node in completed
            },
            "jobs": jobs,
            "pending": sum(jobs.get(key, 0) for key in ("queued", "pending", "failed", "running")),
            "terminal": sum(jobs.get(key, 0) for key in ("parked", "poisoned")),
        }


def step(book, phase, iteration):
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No live step in test mode")
    lock()
    verify_frozen()
    import litharness
    from litharness import cli

    source = LOCAL / "sources" / book[0]
    if not Path(litharness.__file__).is_relative_to(source):
        raise RuntimeError("Child imported an unfrozen source")
    state = read(LOCAL / "progress.json")
    key = f"{phase}-{book}-{iteration}"
    if state.get("active") != key:
        raise RuntimeError("Step was not admitted by the registered scheduler")
    install_recorder(book, phase)
    stdout, stderr = io.StringIO(), io.StringIO()
    arguments = base_args(book) + command(book, phase)
    record = {
        "key": key,
        "book": book,
        "phase": phase,
        "arguments": arguments,
        "source": str(litharness.__file__),
        "started_at": now(),
        "before": metadata(book),
    }
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = cli.main(arguments)
        except BaseException as error:
            code = 2
            record["exception"] = repr(error)
    record.update(
        finished_at=now(),
        returncode=code,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
        after=metadata(book),
    )
    write(LOCAL / "steps" / f"{key}.json", record)
    print(json.dumps({"step": key, "returncode": code, "accepted": record["after"]["accepted"]}))


def phase_done(phase, meta):
    if phase.startswith("chapter"):
        return meta["accepted"] >= int(phase[-1])
    if phase.startswith("drain"):
        return meta["pending"] == 0
    return True


def run():
    lock()
    verify_frozen()
    if os.environ.get("LITHARNESS_ENV") == "test" or (LOCAL / "progress.json").exists():
        raise RuntimeError("No test-mode, duplicate or implicit-resume dispatch")
    # Ensure registration is actually committed, not just written before model calls.
    for path in (
        Path(__file__),
        HERE / "RUNBOOK.md",
        HERE / "inputs.json",
        HERE / "registration.json",
        ROOT / "tests/test_experience_workflow.py",
    ):
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        if hashlib.sha256(committed).hexdigest() != sha(path):
            raise RuntimeError(f"Registration not committed: {path}")
    write(
        LOCAL / "progress.json",
        {
            "status": "running",
            "started_at": now(),
            "calls": [],
            "books": {book: {"status": "running", "accepted": 0} for book in order("concept")},
        },
    )
    for phase in PHASES:
        for book in order(phase):
            state = read(LOCAL / "progress.json")
            if state.get("stop"):
                break
            if state["books"][book]["status"] != "running":
                continue
            if phase.startswith("drain") and state["books"][book].get("pending") == 0:
                continue
            for iteration in range(1, LIMITS["ticks_per_phase"] + 1):
                state = read(LOCAL / "progress.json")
                state["active"] = f"{phase}-{book}-{iteration}"
                write(LOCAL / "progress.json", state)
                subprocess.run(
                    [
                        str(python_for(book[0])),
                        str(Path(__file__)),
                        "step",
                        book,
                        phase,
                        str(iteration),
                    ],
                    cwd=ROOT,
                    env=environment(book),
                    check=True,
                )
                result = read(LOCAL / "steps" / f"{phase}-{book}-{iteration}.json")
                state = read(LOCAL / "progress.json")
                meta = result["after"]
                state["books"][book].update(phase=phase, **meta)
                failed = (
                    meta["terminal"] > 0
                    or result["returncode"] == 2
                    or (result["returncode"] != 0 and not phase.startswith(("chapter", "drain")))
                    or "no_work tick=" in result["stdout"]
                )
                if failed or (
                    iteration == LIMITS["ticks_per_phase"] and not phase_done(phase, meta)
                ):
                    state["books"][book]["status"] = "stopped"
                    state["books"][book]["reason"] = f"workflow stopped in {phase}"
                write(LOCAL / "progress.json", state)
                print(
                    json.dumps(
                        {
                            "book": book,
                            "phase": phase,
                            "iteration": iteration,
                            "accepted": meta["accepted"],
                            "status": state["books"][book]["status"],
                            "calls": len(state["calls"]),
                            "tokens": sum(c["tokens"] for c in state["calls"]),
                        }
                    ),
                    flush=True,
                )
                if state.get("stop") or failed or phase_done(phase, meta):
                    break
        if read(LOCAL / "progress.json").get("stop"):
            break
    state = read(LOCAL / "progress.json")
    state.pop("active", None)
    complete = all(b["accepted"] == 2 and b["status"] == "running" for b in state["books"].values())
    state.update(status="complete" if complete else "partial", finished_at=now())
    write(LOCAL / "progress.json", state)
    print(json.dumps({"status": state["status"], "calls": len(state["calls"])}))


def collect(book):
    from litharness import cli
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.nodes import NodeKind

    if read(LOCAL / "progress.json")["status"] == "running":
        raise RuntimeError("No reading during generation")
    database = book_root(book) / "book.db"
    if not database.exists():
        return
    with SqliteStore.open(database) as store:
        if not (branches := store.branches()):
            return
        head = store.head(branches[0][0], branches[0][1])
        for index, node in enumerate((n for n in head.nodes if n.kind is NodeKind.SCENE), 1):
            if not (node.content or "").strip():
                continue
            path = book_root(book) / f"chapter-{index}.md"
            path.write_text(node.content + "\n", encoding="utf-8")
    for name, arguments in {
        "plans": ["plans", "--json"],
        "world": ["state", "--json"],
        "verify": ["verify", "--json"],
        "status": ["status", "--json"],
        "chapter1": ["why", "--scene", "1", "--json"],
        "chapter2": ["why", "--scene", "2", "--json"],
    }.items():
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(base_args(book) + arguments)
        write(
            book_root(book) / "views" / f"{name}.json",
            {"returncode": code, "output": output.getvalue()},
        )


def transport_details(raw, payload, book):
    from litharness.domain.generation import CompletionRequest, Sampler
    from litharness.providers.codex_cli import _BRIDGE_NOTE
    from litharness.providers.codex_schema import prepare_codex_schema
    from litharness.providers.codex_tools import _validate_arguments

    fields = dict(payload)
    fields["sampler"] = Sampler(**fields["sampler"]) if fields["sampler"] else None
    request = CompletionRequest(**fields)
    system = request.effective_system
    if request.allowed_tools:
        system = "\n\n".join(part for part in (system, _BRIDGE_NOTE) if part)
    native, reason = None, None
    if request.schema is not None:
        try:
            native = prepare_codex_schema(request.schema)
        except ValueError as error:
            reason = str(error)
    checks = {
        "system": raw.get("system") == system,
        "original_schema": raw.get("schema") == request.schema,
        "native_schema": raw.get("native_schema") == native,
        "native_schema_reason": raw.get("native_schema_omission_reason") == reason,
        "schema_argument": ("--output-schema" in raw.get("argv", [])) == (native is not None),
        "world_only": all(
            tool.startswith("Bash(litharness world ") for tool in request.allowed_tools
        ),
    }
    bridge_calls = [json.loads(line) for line in raw.get("commands_jsonl", "").splitlines()]
    bridge_results = [row for row in bridge_calls if row["phase"] == "result"]
    checks["bridge_source_and_scope"] = True
    for row in bridge_results:
        if row.get("argv") is not None:
            try:
                expected = [
                    str(python_for(book[0])),
                    "-m",
                    "litharness",
                    *_validate_arguments(row["arguments"], request.allowed_tools),
                ]
                checks["bridge_source_and_scope"] &= row["argv"] == expected
            except ValueError:
                checks["bridge_source_and_scope"] = False
    checks["bridge_receipts_paired"] = len(bridge_calls) == 2 * len(bridge_results)
    tools = [event.get("item", {}) for event in raw.get("events", [])]
    checks["no_unscoped_tool_events"] = not any(
        item.get("type") in {"command_execution", "web_search", "file_change"}
        or (
            item.get("type") == "mcp_tool_call"
            and (
                not request.allowed_tools
                or item.get("server") != "litharness"
                or item.get("tool") != "litharness_command"
            )
        )
        for item in tools
    )
    return checks


def audit():
    verify_frozen()
    state = read(LOCAL / "progress.json")
    if state["status"] == "running":
        raise RuntimeError("Generation must finish or stop before audit/reading")
    controls, calls, previous, sessions = [], [], None, set()
    replay = {"started_at": state["started_at"], "calls": []}
    for meta in state["calls"]:
        path = LOCAL / meta["path"]
        row = read(path)
        checks = {
            "receipt_chain": row["previous_receipt_sha256"] == previous,
            "completed": row["status"] == "completed",
        }
        previous = sha(path)
        result = row.get("result", {})
        raw = result.get("raw", row.get("raw", {}))
        request = row["request"]
        checks.update(transport_details(raw, request, row["book"]))
        checks["admitted"] = admission(replay, row["book"], row["started_at"]) is None
        checks["usage_recorded"] = (
            meta["tokens"] == sum(result.get("usage", {}).values())
            if row["status"] == "completed"
            else row.get("usage_unknown")
        )
        checks["receipt_identity"] = all(
            row[key] == meta[key] for key in ("number", "book", "phase", "profile", "status")
        )
        replay["calls"].append(meta)
        argv, settings = raw.get("argv", []), raw.get("settings", {})
        checks.update(
            prompt=raw.get("prompt") == request["prompt"],
            isolated=all(
                arg in argv for arg in ("--ephemeral", "--ignore-user-config", "--ignore-rules")
            ),
            no_memory=settings.get("features.memories") is False,
            no_docs=settings.get("project_doc_max_bytes") == 0,
            model=raw.get("requested_model") == "gpt-6-astra",
            effort=settings.get("model_reasoning_effort") == "medium",
            no_search=settings.get("web_search") == "disabled",
        )
        ids = [
            e.get("thread_id") for e in raw.get("events", []) if e.get("type") == "thread.started"
        ]
        checks["fresh_session"] = len(ids) == 1 and bool(ids[0]) and ids[0] not in sessions
        sessions.update(ids)
        checks["tool_scope"] = (
            raw.get("mode") == "bridge"
            if request["allowed_tools"]
            else raw.get("mode") == "completion"
        )
        calls.append(
            {
                "number": row["number"],
                "book": row["book"],
                "phase": row["phase"],
                "profile": row["profile"],
                "receipt_sha256": sha(path),
                "request_sha256": digest(request),
                "checks": checks,
                "usage": result.get("usage"),
                "usage_unknown": row.get("usage_unknown", False),
            }
        )
        controls.extend(checks.values())
    for book in order("concept"):
        subprocess.run(
            [str(python_for(book[0])), str(Path(__file__)), "collect", book],
            env=environment(book),
            cwd=ROOT,
            check=True,
        )
    chapters = [
        {
            "book": book,
            "chapter": path.stem,
            "sha256": sha(path),
            "words": len(path.read_text(encoding="utf-8").split()),
        }
        for book in order("concept")
        for path in sorted(book_root(book).glob("chapter-*.md"))
    ]
    steps = []
    for path in sorted((LOCAL / "steps").glob("*.json")):
        row = read(path)
        book, phase = row["book"], row["phase"]
        steps.append(
            {
                "key": row["key"],
                "sha256": sha(path),
                "returncode": row["returncode"],
                "checks": {
                    "arguments": row["arguments"] == base_args(book) + command(book, phase),
                    "source": Path(row["source"]).is_relative_to(LOCAL / "sources" / book[0]),
                    "two_chapter_limit": row["after"]["accepted"] <= 2,
                    "drain_has_work": not phase.startswith("drain") or row["before"]["pending"] > 0,
                    "time_order": row["started_at"] <= row["finished_at"],
                },
            }
        )
    retention = []
    for book in order("concept"):
        concept_path = book_root(book) / "concept/concept.json"
        item = {"book": book, "concept_available": concept_path.exists()}
        if concept_path.exists():
            concept = read(concept_path)
            brief = concept.get("discovery", {}).get("experience_brief", "")
            outline_requests = [
                read(LOCAL / call["path"])["request"]
                for call in state["calls"]
                if call["book"] == book and call["profile"].startswith("planner.outline.")
            ]
            item.update(
                concept_sha256=sha(concept_path),
                author_brief_retained=concept.get("author_brief") == INPUTS[book[1]]["premise"],
                experience_field_present=bool(brief),
                outline_calls=len(outline_requests),
                brief_in_each_outline=all(
                    brief and json.dumps(brief, ensure_ascii=False)[1:-1] in request["prompt"]
                    for request in outline_requests
                )
                if outline_requests
                else None,
            )
        verify_path = book_root(book) / "views/verify.json"
        if verify_path.exists():
            view = read(verify_path)
            item["verify_returncode"] = view["returncode"]
            try:
                verified = json.loads(view["output"])
                item.update(rebuilt=verified["rebuilt"], unattributed=len(verified["unattributed"]))
            except (ValueError, KeyError):
                item["verify_parse_failed"] = True
        retention.append(item)
    evidence = {
        "status": state["status"],
        "books": state["books"],
        "calls": calls,
        "steps": steps,
        "retention": retention,
        "chapters": chapters,
        "all_transport_controls_pass": all(controls),
        "known_tokens": sum(c["tokens"] for c in state["calls"]),
        "started_at": state["started_at"],
        "finished_at": state["finished_at"],
        "stop": state.get("stop"),
        "registration_sha256": sha(HERE / "registration.json"),
    }
    write(HERE / "evidence.json", evidence)
    claim("observed")
    print(
        json.dumps(
            {
                "status": state["status"],
                "chapters": len(chapters),
                "words": sum(c["words"] for c in chapters),
                "calls": len(calls),
                "transport_controls": all(controls),
            }
        )
    )


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "step":
        step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "collect":
        collect(sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
