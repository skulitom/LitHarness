"""A fixed six-chapter continuation from the first retained growth seed."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib.metadata
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/growth-continuation-20260913"
BOOK = RUN / "book"
PARENT = ROOT / "research/quality-measurement/growth-declarations-20260913/run.py"
SPEC = importlib.util.spec_from_file_location("_growth_continuation_helpers", PARENT)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)
for key, value in {
    "HERE": HERE,
    "ROOT": ROOT,
    "RUN": RUN,
    "OWNER": "growth-continuation-20260913:",
    "REVISION": "23243c3",
    "MAX_CALLS": 32,
    "MAX_TOKENS": 2_200_000,
    "MAX_SECONDS": 5400,
}.items():
    setattr(BASE, key, value)
sha, load, save = BASE.sha, BASE.load, BASE.save
CHAPTERS = 6


def command(args, name):
    from litharness import cli

    argv = [
        "--database",
        str(BOOK / "serial.db"),
        "--library",
        str(BOOK / "library"),
        "--holder",
        "growth-continuation-20260913",
        "--chapter-scenes",
        "1",
        "--arc-chapters",
        str(CHAPTERS),
        "--target-words",
        "1800",
        "--max-invocations-per-day",
        str(BASE.MAX_CALLS),
        "--max-tokens-per-day",
        str(BASE.MAX_TOKENS),
        *args,
    ]
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            code = cli.main(argv)
        except Exception as error:
            code = 2
            print(f"{type(error).__name__}: {error}")
    folder = BOOK / "commands"
    save(
        folder / f"{len(list(folder.glob('*.json'))) + 1:03d}-{name}.json",
        {"argv": argv, "exit_code": code, "output": output.getvalue()},
    )
    return code, output.getvalue()


def must(args, name):
    code, output = command(args, name)
    if code:
        raise RuntimeError(f"{name} exit={code}: {output[-1500:]}")
    return output


def check_chapter_count(count, target):
    if type(count) is not int or not 0 <= count <= target <= CHAPTERS:
        raise RuntimeError("Unexpected accepted chapter count")
    return count == target


def prepare_inputs():
    BASE.lock()
    BASE.clean_environment()
    os.environ["LITHARNESS_ENV"] = "test"
    import litharness
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.events import Event, EventType

    if not Path(litharness.__file__).is_relative_to(RUN / "source"):
        raise RuntimeError("Preparation requires frozen source")
    prior = ROOT / "runs/growth-declarations-20260913"
    inputs = [
        prior / "manifest.json",
        prior / "wren-seed/serial.db",
        prior / "wren-seed/result-world.json",
        ROOT / "runs/world-fixed-continuation-20260913/book-1/concept.json",
        ROOT / "runs/next-priorities-20260913/continuation/serial.db",
    ]
    inputs += sorted(
        (ROOT / "runs/next-priorities-20260913/continuation/library").glob(
            "*/chapters/Chapter*.txt"
        )
    )
    protected = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    BOOK.mkdir(parents=True)
    (BOOK / "concept.json").write_bytes(inputs[3].read_bytes())
    with SqliteStore.open_read_only(inputs[1]) as store:
        [(book, branch, _)] = store.branches()
        records, times = store.state_records(book, branch), store.state_record_times(book, branch)
    must(
        [
            "new",
            "Growth continuation probe",
            "--premise",
            "Wren arrives in Kesh Gorge, where Loadstitch can open the way "
            "into the Trestle's history.",
            "--concept",
            str(BOOK / "concept.json"),
            "--scenes",
            str(CHAPTERS),
        ],
        "new",
    )
    with SqliteStore.open(BOOK / "serial.db") as store:
        [(book, branch, head)] = store.branches()
        for record in sorted(records, key=lambda r: (times[r.record_id], r.record_id)):
            event = Event(
                EventType.STATE_RECORDS_ACCEPTED,
                "isolated-research",
                times[record.record_id],
                book_id=book,
                branch_id=branch,
                revision_id=head,
                payload={
                    "fixture_restore": True,
                    "source_record_id": record.record_id,
                    "source_store_sha256": protected[inputs[1].relative_to(ROOT).as_posix()],
                },
            )
            store.record_state_records(
                book, branch, [record], created_at=times[record.record_id], events=[event]
            )
    world = json.loads(must(["world", "show"], "initial-world"))
    if world != load(inputs[2])["result"]:
        raise RuntimeError("Reconstructed seed world differs")
    save(BOOK / "initial-world.json", world)
    must(["world", "check"], "initial-check")
    parent = load(inputs[0])
    binary = Path(parent["binary"])
    if sha(binary) != parent["binary_sha256"]:
        raise RuntimeError("Pinned native executable changed")
    auth = subprocess.run(
        [str(binary), "login", "status"], capture_output=True, text=True, check=True
    )
    if "ChatGPT" not in auth.stdout + auth.stderr:
        raise RuntimeError("Subscription authentication required")
    scripts = [HERE / name for name in ("run.py", "audit.py", "RUNBOOK.md")]
    scripts += [
        PARENT,
        BASE.PREVIOUS,
        ROOT / "tests/test_growth_integration.py",
        ROOT / "tests/test_growth_continuation_experiment.py",
    ]
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", BASE.REVISION], text=True).strip(),
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "auth": (auth.stdout + auth.stderr).strip(),
        "source": BASE.hashes(RUN / "source"),
        "dependencies": sorted(
            (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
        ),
        "protected_inputs": protected,
        "scripts": {p.relative_to(ROOT).as_posix(): sha(p) for p in scripts},
        "requests": {},
        "fixtures": {"book": sha(BOOK / "serial.db")},
        "concept_sha256": sha(BOOK / "concept.json"),
        "initial_world_sha256": sha(BOOK / "initial-world.json"),
        "chapters": CHAPTERS,
        "max_calls": BASE.MAX_CALLS,
        "max_tokens": BASE.MAX_TOKENS,
        "max_seconds": BASE.MAX_SECONDS,
    }
    if any(sha(ROOT / p) != digest for p, digest in protected.items()):
        raise RuntimeError("Protected input changed during preparation")
    save(RUN / "manifest.json", manifest)
    save(
        HERE / "registration.json",
        {
            "manifest_sha256": sha(RUN / "manifest.json"),
            "source_revision": manifest["revision"],
            "concept_sha256": manifest["concept_sha256"],
            "chapters": CHAPTERS,
            "max_calls": BASE.MAX_CALLS,
            "max_tokens": BASE.MAX_TOKENS,
            "max_seconds": BASE.MAX_SECONDS,
        },
    )
    print("Prepared the retained seed world in a new six-chapter book; no model calls.")


def validate(manifest, *, initial=False):
    BASE.validate(manifest, initial=initial)
    if (
        sha(BOOK / "concept.json") != manifest["concept_sha256"]
        or sha(BOOK / "initial-world.json") != manifest["initial_world_sha256"]
    ):
        raise RuntimeError("Frozen concept or initial readout drift")


def checkpoint(label, progress, manifest):
    from litharness.adapters.sqlite_store import SqliteStore

    validate(manifest)
    folder = BOOK / label
    folder.mkdir()
    count = None
    for name, args in (
        ("audit", ["audit", "--json"]),
        ("status", ["status", "--json"]),
        ("plans", ["plans", "--json"]),
        ("state", ["state", "--json"]),
        ("world", ["world", "show"]),
        ("check", ["world", "check"]),
        ("verify", ["verify", "--json"]),
    ):
        code, output = command(args, f"{label}-{name}")
        save(folder / f"{name}.json", {"exit_code": code, "result": json.loads(output)})
        if code not in (0, 1) or (name in {"check", "verify"} and code):
            raise RuntimeError(f"Checkpoint {name} failed")
        if name == "audit":
            count = json.loads(output)["chapters_drafted"]
        if name == "verify" and json.loads(output).get("unattributed"):
            raise RuntimeError("Unattributed revision")
    chapters = {p.name: sha(p) for p in sorted((BOOK / "library").glob("*/chapters/Chapter*.txt"))}
    old = progress["chapter_hashes"]
    if any(chapters.get(name) != digest for name, digest in old.items()):
        raise RuntimeError("Earlier accepted chapter changed")
    if count != len(chapters):
        raise RuntimeError("Chapter count differs from exported files")
    save(folder / "chapter-hashes.json", chapters)
    with SqliteStore.open_read_only(BOOK / "serial.db") as store:
        store.backup_to(folder / "serial.db")
    progress.update(chapters=count, chapter_hashes=chapters)
    save(RUN / "progress.json", progress)


def live():
    manifest = load(RUN / "manifest.json")
    if sha(RUN / "manifest.json") != load(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Registration/manifest mismatch")
    validate(manifest, initial=True)
    registered = [*manifest["scripts"], (HERE / "registration.json").relative_to(ROOT).as_posix()]
    for relative in registered:
        if (
            subprocess.check_output(["git", "show", "HEAD:" + relative])
            != (ROOT / relative).read_bytes()
        ):
            raise RuntimeError("Registered scripts must be committed")
    if subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"]).returncode:
        raise RuntimeError("Registration must be pushed")
    if (RUN / "progress.json").exists():
        raise FileExistsError("Already started; no implicit resume")
    BASE.clean_environment()
    os.environ.update(LITHARNESS_PROVIDER="codex", LITHARNESS_CODEX_BINARY=manifest["binary"])
    from litharness import cli
    from litharness.application.handlers import SCENE_DRAFT
    from litharness.providers import build_default_registry
    from litharness.providers.codex_cli import CodexCliProvider

    started = time.monotonic()
    progress = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "calls": 0,
        "tokens": 0,
        "chapters": 0,
        "chapter_hashes": {},
        "fatal": None,
    }
    original, original_builder = CodexCliProvider.complete, cli.build_default_registry

    def capture(provider, request):
        validate(manifest)
        if progress["fatal"]:
            raise RuntimeError(progress["fatal"])
        BASE.check_budget(progress["calls"], progress["tokens"], time.monotonic() - started)
        progress["calls"] += 1
        path = BOOK / "calls" / f"{progress['calls']:03d}.json"
        row = {
            "status": "started",
            "started_at": datetime.now(UTC).isoformat(),
            "request": dataclasses.asdict(request),
        }
        save(path, row)
        save(RUN / "progress.json", progress)
        try:
            result = original(provider, request)
            row.update(status="completed", result=dataclasses.asdict(result))
            usage = BASE.native_usage(result.raw)
            if not usage or usage != result.usage.total:
                raise RuntimeError("Unknown or mismatched native usage")
            progress["tokens"] += usage
            return result
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}")
            if "result" not in row:
                row["transport"] = provider.last_attempt
                usage = BASE.native_usage(provider.last_attempt)
                row["failed_native_tokens"] = usage
                progress["tokens"] += usage or 0
            progress["fatal"] = row["error"]
            raise
        finally:
            row["finished_at"] = datetime.now(UTC).isoformat()
            save(path, row)
            save(RUN / "progress.json", progress)

    CodexCliProvider.complete = capture
    registry = build_default_registry()
    registry.provider.trace_directory = BOOK / "transport"
    cli.build_default_registry = lambda: registry
    save(RUN / "progress.json", progress)
    try:
        must(["world", "check"], "seed-check")
        must(["world", "accept"], "seed-accept")
        checkpoint("seeded", progress, manifest)
        for chapter in range(1, CHAPTERS + 1):
            print(f"Chapter {chapter}: starting; tokens={progress['tokens']}", flush=True)
            for _ in range(12):
                must(["tick"], "draft-tick")
                code, output = command(["audit", "--view", "status", "--json"], "count")
                if code not in (0, 1):
                    raise RuntimeError("Cannot read chapter count")
                if check_chapter_count(json.loads(output)["chapters_drafted"], chapter):
                    break
            else:
                raise RuntimeError("No expected progress in twelve ticks")
            for _ in range(12):
                queued = json.loads(must(["jobs", "--status", "queued", "--json"], "queued"))[
                    "jobs"
                ]
                if not queued:
                    break
                if any(j["job_kind"] == SCENE_DRAFT for j in queued):
                    raise RuntimeError("Unexpected queued draft at chapter boundary")
                must(["tick"], "post-chapter-tick")
            else:
                raise RuntimeError("Post-chapter work did not settle")
            must(["architect", "grow"], "grow")
            must(["world", "check"], "grow-check")
            must(["world", "accept"], "grow-accept")
            checkpoint(f"checkpoint-{chapter}", progress, manifest)
            if not check_chapter_count(progress["chapters"], chapter):
                raise RuntimeError("Chapter checkpoint is incomplete")
            print(
                f"Chapter {chapter}: accepted; calls={progress['calls']} "
                f"tokens={progress['tokens']}",
                flush=True,
            )
        progress["status"] = "completed"
    except Exception as error:
        progress.update(status="stopped", fatal=f"{type(error).__name__}: {error}")
        raise
    finally:
        progress.update(
            finished_at=datetime.now(UTC).isoformat(), elapsed_seconds=time.monotonic() - started
        )
        save(RUN / "progress.json", progress)
        CodexCliProvider.complete, cli.build_default_registry = original, original_builder


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inputs", "live"))
    {"prepare": BASE.prepare, "inputs": prepare_inputs, "live": live}[parser.parse_args().mode]()
