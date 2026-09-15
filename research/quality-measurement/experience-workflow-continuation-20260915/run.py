"""Explicit continuation after the registered runner used an ordinal as a logical ID."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT_HERE = HERE.parent / "experience-workflow-20260915"
PARENT = ROOT / "runs/experience-workflow-20260915"
LOCAL = ROOT / "runs/experience-workflow-continuation-20260915"
spec = importlib.util.spec_from_file_location("registered_workflow", PARENT_HERE / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original_command = base.command
original_details = base.transport_details
PHASES = ("grow1", "accept-grow1", "chapter2", "drain2")


def command(book, phase):
    if phase == "grow1":
        return ["architect", "grow", "--scene", "scene-1"]
    return original_command(book, phase)


def schema_canonical(value):
    if isinstance(value, dict):
        return {
            key: sorted(item)
            if key == "required" and isinstance(item, list)
            else schema_canonical(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [schema_canonical(item) for item in value]
    return value


def details(raw, payload, book, root=None):
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import _BRIDGE_NOTE
    from litharness.providers.codex_schema import prepare_codex_schema
    from litharness.providers.codex_tools import _allowances, _validate_arguments

    root = root or LOCAL
    checks = original_details(raw, payload, book)
    request = CompletionRequest(**(payload | {"sampler": None}))
    system = request.effective_system
    if request.allowed_tools:
        system = "\n\n".join(part for part in (system, _BRIDGE_NOTE) if part)
    checks["system"] = raw.get("system") == (system or "Complete the user's requested task.")
    native = None
    if request.schema is not None:
        with contextlib.suppress(ValueError):
            native = prepare_codex_schema(request.schema)
    checks["native_schema"] = schema_canonical(raw.get("native_schema")) == schema_canonical(native)
    checks["bridge_source_and_scope"] = True
    for line in raw.get("commands_jsonl", "").splitlines():
        row = json.loads(line)
        if row["phase"] != "result" or row.get("argv") is None:
            continue
        try:
            expected = [
                str(root / "runtimes" / book[0] / "Scripts/python.exe"),
                "-m",
                "litharness",
                *_validate_arguments(row["arguments"], _allowances(request.allowed_tools)),
            ]
            checks["bridge_source_and_scope"] &= row["argv"] == expected
        except ValueError:
            checks["bridge_source_and_scope"] = False
    return checks


def configure():
    parent = base.read(PARENT / "progress.json")
    counts = {book: sum(c["book"] == book for c in parent["calls"]) for book in parent["books"]}
    if set(counts.values()) != {12} or parent["status"] != "partial" or parent.get("stop"):
        raise RuntimeError("This continuation is only for the recorded identifier failure")
    base.LIMITS = dict(base.LIMITS, calls=144, tokens=1899211, book_calls=33)
    base.LOCAL, base.HERE, base.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.command, base.transport_details, base.claim = command, details, claim
    return parent


def claim(status):
    files = [
        ("registration", HERE / "RUNBOOK.md"),
        ("registration", HERE / "registration.json"),
        ("control_result", HERE / "parent-controls.json"),
    ]
    if status == "observed":
        files.append(("derived_result", HERE / "evidence.json"))
    base.write(
        HERE / "claim.json",
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": "experience-workflow-identifier-continuation-20260915",
            "status": status,
            "statement": "The explicitly registered continuation corrects only a runner scene "
            "identifier, retaining all initial outputs and the original aggregate "
            "resource ceilings.",
            "artifacts": [
                {"kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": base.sha(path)}
                for kind, path in files
            ],
        },
    )


def preflight(book):
    from litharness import cli

    reached = []
    original = cli._completion_call

    def stop(request, **kwargs):
        reached.append(
            {"profile": request.profile, "request_sha256": base.digest(base.serial(request))}
        )
        return None, "registered offline preflight"

    before = base.metadata(book)
    cli._completion_call = stop
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(base.base_args(book) + command(book, "grow1"))
    finally:
        cli._completion_call = original
    after = base.metadata(book)
    if len(reached) != 1 or code != 2 or before != after or before["accepted"] != 1:
        raise RuntimeError("Corrected command did not reach the completion boundary unchanged")
    base.write(
        LOCAL / "preflight" / f"{book}.json",
        {"book": book, "before": before, "after": after, "reached": reached, "provider_calls": 0},
    )


def prepare():
    parent = configure()
    base.lock()
    if LOCAL.exists():
        raise RuntimeError("Never overwrite a continuation")
    if any(c["status"] != "completed" for c in parent["calls"]):
        raise RuntimeError("Unknown parent usage prohibits this continuation")
    if sum(c["tokens"] for c in parent["calls"]) != 2100789:
        raise RuntimeError("Parent usage changed")
    LOCAL.mkdir(parents=True)
    files = [
        Path(__file__),
        HERE / "RUNBOOK.md",
        PARENT_HERE / "run.py",
        ROOT / "tests/test_experience_workflow_continuation.py",
        PARENT / "progress.json",
        PARENT_HERE / "registration.json",
        PARENT_HERE / "evidence.json",
        base.BINARY,
    ]
    for arm in "AB":
        for folder in ("sources", "runtimes"):
            shutil.copytree(
                PARENT / folder / arm,
                LOCAL / folder / arm,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        pth = LOCAL / "runtimes" / arm / "Lib/site-packages/experiment-source.pth"
        pth.write_text(
            pth.read_text(encoding="utf-8").replace(str(PARENT), str(LOCAL)), encoding="utf-8"
        )
        files += [
            p
            for folder in ("sources", "runtimes")
            for p in (LOCAL / folder / arm).rglob("*")
            if p.is_file()
        ]
    parents = {}
    for book in base.order("concept"):
        failed = PARENT / "steps" / f"grow1-{book}-1.json"
        row = base.read(failed)
        if row["before"] != row["after"] or not row.get("exception", "").startswith("KeyError("):
            raise RuntimeError("Parent failure changed state or differs from the registered cause")
        source = PARENT / "books" / book
        wal = source / "book.db-wal"
        if wal.exists() and wal.stat().st_size:
            raise RuntimeError("Parent store must be closed and checkpointed before copying")
        shutil.copytree(source, base.book_root(book))
        # Canonical stores are byte-identical before any read or resumed action.
        if base.sha(source / "book.db") != base.sha(base.book_root(book) / "book.db"):
            raise RuntimeError("Store snapshot mismatch")
        parents[book] = {
            "database_sha256": base.sha(source / "book.db"),
            "head": row["before"]["head"],
            "scene_hashes": row["before"]["scene_hashes"],
        }
        files += [source / "book.db", failed]
        subprocess.run(
            [str(base.python_for(book[0])), str(Path(__file__)), "preflight", book],
            cwd=ROOT,
            env=base.environment(book),
            check=True,
        )
        files += [
            LOCAL / "preflight" / f"{book}.json",
            base.book_root(book) / "brief.txt",
            base.book_root(book) / "seed.json",
            base.book_root(book) / "concept/concept.json",
        ]
    corrected = []
    old = base.read(PARENT_HERE / "evidence.json")
    for meta, old_row in zip(parent["calls"], old["calls"], strict=True):
        path = PARENT / meta["path"]
        row = base.read(path)
        checks = old_row["checks"] | details(
            row["result"]["raw"], row["request"], row["book"], PARENT
        )
        corrected.append(
            {"number": row["number"], "receipt_sha256": base.sha(path), "checks": checks}
        )
        files.append(path)
    base.write(
        HERE / "parent-controls.json",
        {
            "original_evidence_sha256": base.sha(PARENT_HERE / "evidence.json"),
            "calls": corrected,
            "all_controls_pass": all(all(row["checks"].values()) for row in corrected),
        },
    )
    if not base.read(HERE / "parent-controls.json")["all_controls_pass"]:
        raise RuntimeError("Unresolved parent transport control failure")
    files.append(HERE / "parent-controls.json")
    manifest = {
        "files": {str(path): base.sha(path) for path in files},
        "parents": parents,
        "limits_remaining": base.LIMITS,
        "original_started_at": parent["started_at"],
        "original_calls": 96,
        "original_tokens": 2100789,
        "order": {phase: base.order(phase) for phase in PHASES},
    }
    base.write(LOCAL / "manifest.json", manifest)
    base.write(
        HERE / "registration.json",
        manifest | {"manifest_sha256": base.sha(LOCAL / "manifest.json")},
    )
    claim("registered")
    print(
        "Prepared identical parent snapshots; all eight offline grow preflights "
        "and controls passed."
    )


def run():
    parent = configure()
    base.lock()
    base.verify_frozen()
    if os.environ.get("LITHARNESS_ENV") == "test" or (LOCAL / "progress.json").exists():
        raise RuntimeError("No test-mode, duplicate or implicit resume")
    for path in (
        Path(__file__),
        HERE / "RUNBOOK.md",
        HERE / "registration.json",
        HERE / "parent-controls.json",
        ROOT / "tests/test_experience_workflow_continuation.py",
    ):
        data = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        if base.digest(data.hex()) != base.digest(path.read_bytes().hex()):
            raise RuntimeError("Continuation is not committed")
    books = {
        book: {key: value for key, value in row.items() if key not in {"status", "reason"}}
        | {"status": "running"}
        for book, row in parent["books"].items()
    }
    base.write(
        LOCAL / "progress.json",
        {
            "status": "running",
            "started_at": parent["started_at"],
            "continuation_started_at": base.now(),
            "calls": [],
            "books": books,
        },
    )
    for phase in PHASES:
        for book in base.order(phase):
            state = base.read(LOCAL / "progress.json")
            if state.get("stop"):
                break
            if state["books"][book]["status"] != "running":
                continue
            if phase.startswith("drain") and state["books"][book]["pending"] == 0:
                continue
            for iteration in range(1, base.LIMITS["ticks_per_phase"] + 1):
                state = base.read(LOCAL / "progress.json")
                key = f"{phase}-{book}-{iteration}"
                state["active"] = key
                base.write(LOCAL / "progress.json", state)
                subprocess.run(
                    [
                        str(base.python_for(book[0])),
                        str(Path(__file__)),
                        "step",
                        book,
                        phase,
                        str(iteration),
                    ],
                    cwd=ROOT,
                    env=base.environment(book),
                    check=True,
                )
                row = base.read(LOCAL / "steps" / f"{key}.json")
                state = base.read(LOCAL / "progress.json")
                meta = row["after"]
                state["books"][book].update(phase=phase, **meta)
                failed = (
                    meta["terminal"] > 0
                    or row["returncode"] == 2
                    or "no_work tick=" in row["stdout"]
                    or (row["returncode"] != 0 and not phase.startswith(("chapter", "drain")))
                    or (
                        iteration == base.LIMITS["ticks_per_phase"]
                        and not base.phase_done(phase, meta)
                    )
                )
                if failed:
                    state["books"][book].update(
                        status="stopped", reason=f"workflow stopped in {phase}"
                    )
                base.write(LOCAL / "progress.json", state)
                if state.get("stop") or failed or base.phase_done(phase, meta):
                    break
        if base.read(LOCAL / "progress.json").get("stop"):
            break
    state = base.read(LOCAL / "progress.json")
    state.pop("active", None)
    complete = all(b["accepted"] == 2 and b["status"] == "running" for b in state["books"].values())
    state.update(status="complete" if complete else "partial", finished_at=base.now())
    base.write(LOCAL / "progress.json", state)
    print(json.dumps({"status": state["status"], "calls": len(state["calls"])}))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode in {"prepare", "run"}:
        {"prepare": prepare, "run": run}[mode]()
    else:
        configure()
        if mode == "step":
            base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        elif mode == "preflight":
            preflight(sys.argv[2])
        elif mode == "collect":
            base.collect(sys.argv[2])
        elif mode == "audit":
            base.audit()
