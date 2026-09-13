"""Five registered first-output cells against frozen production source."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib.metadata
import io
import json
import os
import runpy
import subprocess
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/growth-declarations-20260913"
PRIOR = ROOT / "runs/world-fixed-continuation-20260913"
PREVIOUS = ROOT / "research/quality-measurement/next-priorities-20260913/run.py"
_HELPERS = runpy.run_path(str(PREVIOUS))
sha, save, load, native_usage = (_HELPERS[k] for k in ("sha", "save", "load", "native_usage"))
OWNER = "growth-declarations-20260913:"
REVISION = "11d3aea"
ORDER = ("wren-seed", "opposing-seed", "capped-seed", "conditional-goal", "adopted-goal")
MAX_CALLS, MAX_TOKENS, MAX_SECONDS = 8, 1_600_000, 5400


def lock():
    holder = ROOT / "runs/box.lock/holder"
    if not holder.exists() or not holder.read_text(encoding="utf-8-sig").startswith(OWNER):
        raise RuntimeError("This experiment does not own the shared-machine lock")


def hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def clean_environment():
    for key in list(os.environ):
        if key.startswith("LITHARNESS_"):
            del os.environ[key]


def check_budget(calls, tokens, elapsed):
    if calls >= MAX_CALLS or tokens >= MAX_TOKENS or elapsed >= MAX_SECONDS:
        raise RuntimeError("Registered aggregate ceiling reached")


def transform_requests(seed, opposing, grow, seed_system, opposing_system, grow_system, inputs):
    """Keep captured application input except for the registered system and source contrasts."""
    from litharness.application import world_agent

    base = {**seed, "system": seed_system, "profile": world_agent.SEED_PROFILE}
    opposite = {**opposing, "system": opposing_system, "profile": world_agent.SEED_PROFILE}
    conditional = {**grow, "system": grow_system, "profile": world_agent.GROW_PROFILE}
    before, after = inputs["before"], inputs["after"]
    if grow["prompt"].count(before) != 1 or before == after or not inputs["cap"].strip():
        raise ValueError("The registered source contrasts are missing or not uniquely located")
    return {
        "wren-seed": base,
        "opposing-seed": opposite,
        "capped-seed": {**base, "prompt": base["prompt"] + "\n\n" + inputs["cap"]},
        "conditional-goal": conditional,
        "adopted-goal": {**conditional, "prompt": conditional["prompt"].replace(before, after)},
    }


def command(folder, args, name):
    from litharness import cli

    argv = ["--database", str(folder / "serial.db"), "--library", str(folder / "library"), *args]
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = cli.main(argv)
    destination = folder / "commands"
    save(destination / f"{len(list(destination.glob('*.json'))) + 1:03d}-{name}.json",
         {"argv": argv, "exit_code": code, "output": output.getvalue()})
    if code not in (0, 1):
        raise RuntimeError(f"{name} failed with {code}: {output.getvalue()[-1000:]}")
    return code, output.getvalue()


def prepare():
    lock()
    if (RUN / "source").exists() or (RUN / "manifest.json").exists():
        raise FileExistsError("Preparation never overwrites a registered run")
    RUN.mkdir(parents=True, exist_ok=True)
    archive = RUN / "source.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--output={archive}", REVISION,
                    "src", "migrations", "pyproject.toml", "uv.lock"], cwd=ROOT, check=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(RUN / "source")
    subprocess.run(["uv", "venv", "--python", str(ROOT / ".venv/Scripts/python.exe"),
                    str(RUN / "runtime")], cwd=ROOT, check=True)
    (RUN / "runtime/Lib/site-packages/frozen_source.pth").write_text(
        str(RUN / "source/src") + "\n" + str(ROOT / ".venv/Lib/site-packages") + "\n",
        encoding="utf-8", newline="\n",
    )
    subprocess.run([str(RUN / "runtime/Scripts/python.exe"), str(HERE / "run.py"), "inputs"],
                   cwd=ROOT, check=True)


def prepare_inputs():
    lock()
    clean_environment()
    os.environ["LITHARNESS_ENV"] = "test"
    import litharness
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application import world_agent
    from litharness.application.concept import Concept
    from litharness.domain.events import Event, EventType

    if not Path(litharness.__file__).is_relative_to(RUN / "source"):
        raise RuntimeError("Preparation requires the frozen interpreter")
    source_inputs = [PRIOR / "manifest.json", PRIOR / "book-1/calls/003.json",
                     PRIOR / "book-2/calls/002.json", PRIOR / "book-1/calls/010.json",
                     PRIOR / "book-1/concept.json", PRIOR / "book-2/concept.json",
                     PRIOR / "book-1/serial.db", PRIOR / "book-1/checkpoint-1/world.txt",
                     ROOT / "runs/next-priorities-20260913/goal-input.json", RUN / "input.json"]
    original_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in source_inputs}
    concepts = [Concept.from_text((PRIOR / f"book-{i}/concept.json").read_text(encoding="utf-8"))
                for i in (1, 2)]
    contrasts = load(RUN / "input.json")
    prior_contrast = load(ROOT / "runs/next-priorities-20260913/goal-input.json")
    if any(contrasts[key] != prior_contrast[key] for key in ("before", "after")):
        raise RuntimeError("Goal passage contrast differs from its frozen predecessor")
    requests = transform_requests(
        load(source_inputs[1])["request"], load(source_inputs[2])["request"],
        load(source_inputs[3])["request"],
        world_agent.render_seed_request("", concept=concepts[0]).system,
        world_agent.render_seed_request("", concept=concepts[1]).system,
        world_agent.render_grow_request("", logical_id="scene-2", concept=concepts[0]).system,
        contrasts,
    )
    saved_world = load(PRIOR / "book-1/checkpoint-1/world.txt")
    wanted = {r["record_id"] for r in saved_world}
    with SqliteStore.open_read_only(PRIOR / "book-1/serial.db") as store:
        [(book, branch, _)] = store.branches()
        records = [r for r in store.state_records(book, branch) if r.record_id in wanted]
        times = store.state_record_times(book, branch)
    if {r.record_id for r in records} != wanted:
        raise RuntimeError("Checkpoint identities missing from original store")
    for name in ORDER:
        folder = RUN / name
        save(folder / "request.json", requests[name])
        args = ["new", "Isolated growth fixture", "--premise", "Frozen engineering fixture.",
                "--scenes", "6"]
        if name.endswith("-seed"):
            args += ["--concept", str(PRIOR / ("book-2" if name == "opposing-seed" else "book-1")
                                     / "concept.json")]
        code, _ = command(folder, args, "new")
        if code:
            raise RuntimeError("Could not create empty fixture")
        if name.endswith("-goal"):
            with SqliteStore.open(folder / "serial.db") as store:
                [(book, branch, head)] = store.branches()
                for record in sorted(records, key=lambda r: (times[r.record_id], r.record_id)):
                    event = Event(EventType.STATE_RECORDS_ACCEPTED, "isolated-research",
                                  times[record.record_id], book_id=book, branch_id=branch,
                                  revision_id=head, payload={"fixture_restore": True,
                                  "source_record_id": record.record_id,
                                  "source_store_sha256": original_hashes[
                                      "runs/world-fixed-continuation-20260913/book-1/serial.db"]})
                    store.record_state_records(book, branch, [record],
                                               created_at=times[record.record_id], events=[event])
        _, shown = command(folder, ["world", "show"], "initial-world")
        world = json.loads(shown)
        if world != (saved_world if name.endswith("-goal") else []):
            raise RuntimeError("Prepared world differs from the registered initial condition")
        save(folder / "initial-world.json", world)
    native = Path(load(PRIOR / "manifest.json")["binary"])
    if sha(native) != load(PRIOR / "manifest.json")["binary_sha256"]:
        raise RuntimeError("Pinned native binary differs")
    auth = subprocess.run([str(native), "login", "status"], capture_output=True, text=True,
                          check=True)
    if "ChatGPT" not in auth.stdout + auth.stderr:
        raise RuntimeError("Subscription authentication required")
    scripts = [HERE / name for name in ("run.py", "audit.py", "RUNBOOK.md")]
    scripts += [PREVIOUS, ROOT / "tests/test_growth_declaration_experiment.py"]
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", REVISION], text=True).strip(),
        "binary": str(native), "binary_sha256": sha(native),
        "auth": (auth.stdout + auth.stderr).strip(), "source": hashes(RUN / "source"),
        "dependencies": sorted((d.metadata["Name"], d.version)
                               for d in importlib.metadata.distributions()),
        "protected_inputs": original_hashes,
        "scripts": {p.relative_to(ROOT).as_posix(): sha(p) for p in scripts},
        "requests": {name: sha(RUN / name / "request.json") for name in ORDER},
        "fixtures": {name: sha(RUN / name / "serial.db") for name in ORDER},
        "max_calls": MAX_CALLS, "max_tokens": MAX_TOKENS, "max_seconds": MAX_SECONDS,
    }
    for path, digest in original_hashes.items():
        if sha(ROOT / path) != digest:
            raise RuntimeError("Protected input changed during preparation")
    save(RUN / "manifest.json", manifest)
    save(HERE / "registration.json", {"manifest_sha256": sha(RUN / "manifest.json"),
         "source_revision": manifest["revision"], "assignments": list(ORDER),
         "max_calls": MAX_CALLS, "max_tokens": MAX_TOKENS, "max_seconds": MAX_SECONDS})
    print("Prepared five fixtures and frozen requests without model calls.")


def validate(manifest, *, initial=False):
    lock()
    import litharness
    if not Path(litharness.__file__).is_relative_to(RUN / "source"):
        raise RuntimeError("Must use the frozen source interpreter")
    if hashes(RUN / "source") != manifest["source"]:
        raise RuntimeError("Frozen source drift")
    for path, digest in (manifest["protected_inputs"] | manifest["scripts"]).items():
        if sha(ROOT / path) != digest:
            raise RuntimeError(f"Protected input or script drift: {path}")
    for name, digest in manifest["requests"].items():
        if sha(RUN / name / "request.json") != digest:
            raise RuntimeError(f"Request drift: {name}")
    if initial and any(sha(RUN / name / "serial.db") != digest
                       for name, digest in manifest["fixtures"].items()):
        raise RuntimeError("Initial fixture drift")
    if sha(Path(manifest["binary"])) != manifest["binary_sha256"]:
        raise RuntimeError("Native binary drift")
    installed = sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
    if [list(item) for item in installed] != manifest["dependencies"]:
        raise RuntimeError("Dependency inventory drift")


def live():
    manifest = load(RUN / "manifest.json")
    if sha(RUN / "manifest.json") != load(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Registration/manifest mismatch")
    validate(manifest, initial=True)
    registered = [*manifest["scripts"], (HERE / "registration.json").relative_to(ROOT).as_posix()]
    for relative in registered:
        committed = subprocess.check_output(["git", "show", "HEAD:" + relative])
        if committed != (ROOT / relative).read_bytes():
            raise RuntimeError("All registered code and inputs must be committed before calls")
    if subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"]).returncode:
        raise RuntimeError("Registration must be pushed before calls")
    if (RUN / "progress.json").exists():
        raise FileExistsError("Experiment already started; no implicit resume")
    clean_environment()
    os.environ.update(LITHARNESS_PROVIDER="codex", LITHARNESS_CODEX_BINARY=manifest["binary"])
    from litharness.domain.generation import CompletionRequest
    from litharness.providers import build_default_registry
    from litharness.providers.codex_cli import CodexCliProvider
    started = time.monotonic()
    progress = {"status": "running", "started_at": datetime.now(UTC).isoformat(),
                "calls": 0, "tokens": 0, "assignments": [], "fatal": None}
    active = RUN
    original = CodexCliProvider.complete

    def capture(provider, request):
        validate(manifest)
        if progress["fatal"]:
            raise RuntimeError(progress["fatal"])
        check_budget(progress["calls"], progress["tokens"], time.monotonic() - started)
        progress["calls"] += 1
        receipt = active / "calls" / f"{progress['calls']:03d}.json"
        row = {"status": "started", "started_at": datetime.now(UTC).isoformat(),
               "request": dataclasses.asdict(request)}
        save(receipt, row)
        save(RUN / "progress.json", progress)
        print(f"{active.name}: call {progress['calls']} {request.profile}", flush=True)
        try:
            result = original(provider, request)
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
            print(f"{active.name}: {row['status']}, total tokens {progress['tokens']}", flush=True)

    CodexCliProvider.complete = capture
    registry = build_default_registry()
    save(RUN / "progress.json", progress)
    try:
        for name in ORDER:
            active = RUN / name
            os.environ["LITHARNESS_DATABASE"] = str(active / "serial.db")
            registry.provider.trace_directory = active / "transport"
            payload = load(active / "request.json")
            payload["allowed_tools"] = tuple(payload["allowed_tools"])
            registry.complete(CompletionRequest(**payload))
            validate(manifest)
            for label, args in (("world", ["world", "show"]),
                                ("check", ["world", "check"]),
                                ("verify", ["verify", "--json"])):
                code, output = command(active, args, label)
                save(active / f"result-{label}.json",
                     {"exit_code": code, "result": json.loads(output)})
                if label == "verify" and (code or json.loads(output).get("unattributed")):
                    raise RuntimeError("Fixture attribution failure")
            progress["assignments"].append(name)
            save(RUN / "progress.json", progress)
        progress["status"] = "completed"
    except Exception as error:
        progress.update(status="stopped", fatal=f"{type(error).__name__}: {error}")
        raise
    finally:
        progress["finished_at"] = datetime.now(UTC).isoformat()
        progress["elapsed_seconds"] = time.monotonic() - started
        save(RUN / "progress.json", progress)
        CodexCliProvider.complete = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inputs", "live"))
    mode = parser.parse_args().mode
    {"prepare": prepare, "inputs": prepare_inputs, "live": live}[mode]()
