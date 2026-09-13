"""Frozen, bounded goal and continuation experiments over disposable stores."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import importlib.metadata
import io
import json
import os
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/next-priorities-20260913"
PRIOR = ROOT / "runs/world-fixed-continuation-20260913"
OWNER = "next-priorities-20260913:"
ORDER = ("current-conditional", "clarified-adopted", "current-adopted", "clarified-conditional")
MAX_CALLS, MAX_TOKENS = 20, 2_000_000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def lock():
    if not (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig").startswith(OWNER):
        raise RuntimeError("This task does not own the shared-machine lock")


def backup(source, target):
    if target.exists():
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with (
        contextlib.closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src,
        contextlib.closing(sqlite3.connect(target)) as dst,
    ):
        src.backup(dst)


def requests(original, transformation):
    before, after = transformation["before"], transformation["after"]
    if original["prompt"].count(before) != 1 or before == after:
        raise ValueError("The original conditional passage must be uniquely located")
    result = {}
    for name in ORDER:
        request = dict(original)
        if name.endswith("-adopted"):
            request["prompt"] = request["prompt"].replace(before, after)
        if name.startswith("clarified-"):
            request["system"] += "\n\n" + transformation["clarification"]
        result[name] = request
    return result


def check_budget(calls, tokens, elapsed):
    if calls >= MAX_CALLS or tokens >= MAX_TOKENS or elapsed >= 7200:
        raise RuntimeError("Registered new-call ceiling reached")


def native_usage(raw):
    try:
        events = [json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()]
        completed = [row["usage"] for row in events if row.get("type") == "turn.completed"]
        if len(completed) != 1:
            return None
        counts = [completed[0]["input_tokens"], completed[0]["output_tokens"]]
        return sum(counts) if all(type(v) is int and v >= 0 for v in counts) else None
    except (ValueError, KeyError, TypeError):
        return None


def clean_environment():
    for key in list(os.environ):
        if key.startswith("LITHARNESS_"):
            del os.environ[key]


def command(directory, args, name):
    from litharness import cli

    argv = [
        "--database",
        str(directory / "serial.db"),
        "--library",
        str(directory / "library"),
        "--holder",
        "next-priorities-20260913",
        "--chapter-scenes",
        "1",
        "--arc-chapters",
        "6",
        "--target-words",
        "1800",
        "--max-invocations-per-day",
        "60",
        "--max-tokens-per-day",
        "4000000",
        *args,
    ]
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            code = cli.main(argv)
        except Exception as error:
            code = 2
            print(f"{type(error).__name__}: {error}")
    text = output.getvalue()
    folder = directory / "commands"
    number = len(list(folder.glob("*.json"))) + 1
    save(folder / f"{number:03d}-{name}.json", {"argv": argv, "exit_code": code, "output": text})
    if code not in (0, 1):
        raise RuntimeError(f"{name} exit={code}: {text[-1000:]}")
    return code, text


def must(directory, args, name):
    code, text = command(directory, args, name)
    if code:
        raise RuntimeError(f"{name} exit={code}: {text[-1000:]}")
    return text


def checkpoint(directory, label, earlier):
    result = {}
    for name, args in (
        ("audit", ["audit", "--json"]),
        ("verify", ["verify", "--json"]),
        ("plans", ["plans", "--json"]),
        ("state", ["state", "--json"]),
        ("world", ["world", "show"]),
        ("jobs", ["jobs", "--status", "queued", "--json"]),
    ):
        code, text = command(directory, args, label + "-" + name)
        result[name] = json.loads(text)
        save(directory / label / f"{name}.json", result[name])
        if name == "verify" and (code or result[name].get("unattributed")):
            raise RuntimeError("Revision attribution failed")
    files = sorted((directory / "library").glob("*/chapters/Chapter*.txt"))
    current = {p.name: sha(p) for p in files}
    if any(current.get(name) != digest for name, digest in earlier.items()):
        raise RuntimeError("An earlier accepted chapter changed")
    save(directory / label / "chapter-hashes.json", current)
    return current, result


def prepare():
    lock()
    if (RUN / "manifest.json").exists():
        raise FileExistsError("Experiment already prepared")
    clean_environment()
    os.environ["LITHARNESS_ENV"] = "test"
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.events import Event, EventType

    old_manifest = load(PRIOR / "manifest.json")
    original = load(PRIOR / "book-1/calls/010.json")["request"]
    for name, request in requests(original, load(RUN / "goal-input.json")).items():
        save(RUN / name / "request.json", request)
    saved_world = load(PRIOR / "book-1/checkpoint-1/world.txt")
    ids = {row["record_id"] for row in saved_world}
    source = PRIOR / "book-1/serial.db"
    before = sha(source)
    with SqliteStore.open_read_only(source) as store:
        [(book, branch, _)] = store.branches()
        records = [r for r in store.state_records(book, branch) if r.record_id in ids]
        times = store.state_record_times(book, branch)
    if {r.record_id for r in records} != ids:
        raise RuntimeError("Checkpoint identities missing from the source store")
    for name in ORDER:
        folder = RUN / name
        must(
            folder,
            [
                "new",
                "Goal boundary fixture",
                "--premise",
                "Isolated world fixture.",
                "--scenes",
                "6",
            ],
            "fixture-new",
        )
        with SqliteStore.open(folder / "serial.db") as store:
            [(fixture_book, fixture_branch, head)] = store.branches()
            for record in sorted(records, key=lambda r: (times[r.record_id], r.record_id)):
                event = Event(
                    EventType.STATE_RECORDS_ACCEPTED,
                    "isolated-research",
                    times[record.record_id],
                    book_id=fixture_book,
                    branch_id=fixture_branch,
                    revision_id=head,
                    payload={
                        "source_record_id": record.record_id,
                        "source_store_sha256": before,
                        "fixture_restore": True,
                    },
                )
                store.record_state_records(
                    fixture_book,
                    fixture_branch,
                    [record],
                    created_at=times[record.record_id],
                    events=[event],
                )
        shown = json.loads(must(folder, ["world", "show"], "fixture-world"))
        if shown != saved_world:
            raise RuntimeError("Reconstructed fixture differs from the recorded world readout")
        save(folder / "initial-world.json", shown)
    backup(source, RUN / "continuation/serial.db")
    must(RUN / "continuation", ["library"], "initial-library")
    initial_hashes = load(PRIOR / "book-1/final/chapter-hashes.json")
    current, initial = checkpoint(RUN / "continuation", "initial", initial_hashes)
    if current != initial_hashes or initial["audit"]["chapters_drafted"] != 3:
        raise RuntimeError("Continuation backup does not reproduce the three chapters")
    if sha(source) != before:
        raise RuntimeError("Original store changed during preparation")
    native = Path(old_manifest["binary"])
    auth = subprocess.run(
        [str(native), "login", "status"], capture_output=True, text=True, check=True
    )
    if "ChatGPT" not in auth.stdout + auth.stderr:
        raise RuntimeError("ChatGPT subscription authentication required")
    inputs = [
        RUN / "goal-input.json",
        PRIOR / "manifest.json",
        source,
        PRIOR / "book-1/calls/010.json",
        PRIOR / "book-1/checkpoint-1/world.txt",
        *sorted((PRIOR / "book-1/library").glob("*/chapters/Chapter*.txt")),
        *(RUN / name / "request.json" for name in ORDER),
        *(RUN / name / "serial.db" for name in (*ORDER, "continuation")),
        *sorted(
            (ROOT / "runs/causal-reader-admission-20260913").glob(
                "source-*/*/*/battery.private.json"
            )
        ),
    ]
    files = [HERE / name for name in ("run.py", "probe.py", "RUNBOOK.md")]
    files += [ROOT / "tests/test_next_priorities_experiment.py"]
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "baseline_revision": old_manifest["revision"],
        "binary": str(native),
        "binary_sha256": sha(native),
        "source": str(PRIOR / "source"),
        "source_sha256": old_manifest["source_sha256"],
        "dependencies": sorted(
            (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
        ),
        "inputs": {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs},
        "scripts": {p.relative_to(ROOT).as_posix(): sha(p) for p in files},
        "order": list(ORDER),
        "max_calls": MAX_CALLS,
        "max_tokens": MAX_TOKENS,
    }
    save(RUN / "manifest.json", manifest)
    save(
        HERE / "registration.json",
        {
            "manifest_sha256": sha(RUN / "manifest.json"),
            "baseline_revision": manifest["baseline_revision"],
            "max_calls": MAX_CALLS,
            "max_tokens": MAX_TOKENS,
            "goal_cells": list(ORDER),
            "continuation_target": 6,
            "reader_calls": 0,
        },
    )
    print("Prepared four identical world fixtures and a three-chapter backup; no model calls.")


def validate(manifest, *, initial=False):
    lock()
    import litharness

    source = Path(manifest["source"])
    if not Path(litharness.__file__).is_relative_to(source):
        raise RuntimeError("Must use the registered frozen interpreter/source")
    for relative, digest in manifest["source_sha256"].items():
        if sha(source / relative) != digest:
            raise RuntimeError(f"Frozen production source drift: {relative}")
    for relative, digest in (manifest["scripts"] | manifest["inputs"]).items():
        local_store = relative.startswith("runs/next-priorities-20260913/") and relative.endswith(
            "serial.db"
        )
        if not initial and local_store:
            continue
        if sha(ROOT / relative) != digest:
            raise RuntimeError(f"Registered input/script drift: {relative}")
    if sha(Path(manifest["binary"])) != manifest["binary_sha256"]:
        raise RuntimeError("Native executable drift")
    installed = sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
    if [list(row) for row in installed] != manifest["dependencies"]:
        raise RuntimeError("Dependency inventory drift")


def live():
    manifest = load(RUN / "manifest.json")
    if sha(RUN / "manifest.json") != load(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Registration/manifest mismatch")
    validate(manifest, initial=True)
    for relative in [
        *manifest["scripts"],
        (HERE / "registration.json").relative_to(ROOT).as_posix(),
    ]:
        committed = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
        if committed != (ROOT / relative).read_bytes():
            raise RuntimeError("Registration, scripts and tests must be committed before calls")
    if (RUN / "progress.json").exists():
        raise FileExistsError("Live run already started; refusing implicit resume")
    clean_environment()
    os.environ.update(LITHARNESS_PROVIDER="codex", LITHARNESS_CODEX_BINARY=manifest["binary"])
    from litharness import cli
    from litharness.application.handlers import SCENE_DRAFT
    from litharness.domain.generation import CompletionRequest
    from litharness.providers import build_default_registry
    from litharness.providers.codex_cli import CodexCliProvider

    started = time.monotonic()
    progress = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "calls": 0,
        "tokens": 0,
        "assignments": [],
        "fatal": None,
    }
    active = RUN
    original_complete = CodexCliProvider.complete

    def capture(provider, request):
        validate(manifest)
        if progress["fatal"]:
            raise RuntimeError(progress["fatal"])
        check_budget(progress["calls"], progress["tokens"], time.monotonic() - started)
        progress["calls"] += 1
        receipt = active / "calls" / f"{progress['calls']:03d}.json"
        row = {
            "started_at": datetime.now(UTC).isoformat(),
            "request": dataclasses.asdict(request),
            "status": "started",
        }
        save(receipt, row)
        save(RUN / "progress.json", progress)
        print(f"{active.name}: call {progress['calls']} {request.profile}", flush=True)
        try:
            result = original_complete(provider, request)
            row.update(status="completed", result=dataclasses.asdict(result))
            usage = native_usage(result.raw)
            if not usage or usage != result.usage.total:
                raise RuntimeError("Unknown or mismatched native usage")
            progress["tokens"] += usage
            return result
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}")
            if "result" not in row:
                row["transport"] = provider.last_attempt
                usage = native_usage(provider.last_attempt)
                row["failed_native_tokens"] = usage
                progress["tokens"] += usage or 0
            progress["fatal"] = row["error"]
            raise
        finally:
            row["finished_at"] = datetime.now(UTC).isoformat()
            save(receipt, row)
            save(RUN / "progress.json", progress)
            print(f"{active.name}: {row['status']}; total tokens={progress['tokens']}", flush=True)

    CodexCliProvider.complete = capture
    registry = build_default_registry()
    cli.build_default_registry = lambda: registry
    save(RUN / "progress.json", progress)
    try:
        for name in ORDER:
            active = RUN / name
            os.environ["LITHARNESS_DATABASE"] = str(active / "serial.db")
            registry.provider.trace_directory = active / "transport"
            payload = load(active / "request.json")
            payload["allowed_tools"] = tuple(payload["allowed_tools"])
            registry.complete(CompletionRequest(**payload))
            shown = json.loads(must(active, ["world", "show"], "result-world"))
            save(active / "result-world.json", shown)
            checked_code, checked = command(active, ["world", "check"], "result-check")
            save(
                active / "result-check.json",
                {"exit_code": checked_code, "check": json.loads(checked)},
            )
            progress["assignments"].append({"name": name, "status": "completed"})
            save(RUN / "progress.json", progress)
        active = RUN / "continuation"
        os.environ["LITHARNESS_DATABASE"] = str(active / "serial.db")
        registry.provider.trace_directory = active / "transport"
        hashes = load(active / "initial/chapter-hashes.json")
        for chapter in range(4, 7):
            for _ in range(12):
                must(active, ["tick"], "tick")
                _, count_text = command(active, ["audit", "--view", "status", "--json"], "count")
                count = json.loads(count_text)["chapters_drafted"]
                if count > chapter:
                    raise RuntimeError("Chapter boundary overshot")
                if count == chapter:
                    break
            else:
                raise RuntimeError("Chapter did not advance in twelve ticks")
            for _ in range(12):
                queued = json.loads(
                    must(active, ["jobs", "--status", "queued", "--json"], "queued")
                )["jobs"]
                if not queued:
                    break
                if any(job["job_kind"] == SCENE_DRAFT for job in queued):
                    raise RuntimeError("Unexpected queued draft at chapter checkpoint")
                must(active, ["tick"], "drain")
            else:
                raise RuntimeError("Post-chapter jobs did not settle")
            must(active, ["architect", "grow"], "grow")
            must(active, ["world", "check"], "grow-check")
            must(active, ["world", "accept"], "grow-accept")
            hashes, _ = checkpoint(active, f"chapter-{chapter}", hashes)
            progress["assignments"].append({"name": f"chapter-{chapter}", "status": "completed"})
            save(RUN / "progress.json", progress)
        progress["status"] = "completed"
    except Exception as error:
        progress.update(status="stopped", fatal=f"{type(error).__name__}: {error}")
    finally:
        CodexCliProvider.complete = original_complete
        progress.update(
            finished_at=datetime.now(UTC).isoformat(),
            elapsed_seconds=round(time.monotonic() - started, 1),
        )
        save(RUN / "progress.json", progress)
    print(json.dumps(progress, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "live"))
    (prepare if parser.parse_args().mode == "prepare" else live)()
