"""Bounded format comparison over byte-identical paired grow requests."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/compact-json-20260913"
PARENT = ROOT / "research/quality-measurement/growth-declarations-20260913/run.py"
SPEC = importlib.util.spec_from_file_location("_compact_json_frozen_driver", PARENT)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)
ORDER = ("verbatim-conditional", "compact-adopted", "compact-conditional", "verbatim-adopted")
for key, value in {"HERE": HERE, "ROOT": ROOT, "RUN": RUN, "ORDER": ORDER,
                   "OWNER": "compact-json-20260913:", "REVISION": "991ff2c",
                   "MAX_CALLS": 8, "MAX_TOKENS": 1_200_000, "MAX_SECONDS": 3600}.items():
    setattr(BASE, key, value)
sha, load, save = BASE.sha, BASE.load, BASE.save


def compact_for_case(name):
    if name not in ORDER:
        raise ValueError("Unregistered format assignment")
    return name.startswith("compact-")


def prepare_inputs():
    BASE.lock()
    BASE.clean_environment()
    os.environ["LITHARNESS_ENV"] = "test"
    import litharness
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.events import Event, EventType

    if not Path(litharness.__file__).is_relative_to(RUN / "source"):
        raise RuntimeError("Preparation requires the frozen interpreter")
    prior = ROOT / "runs/world-fixed-continuation-20260913"
    parent_run = ROOT / "runs/growth-declarations-20260913"
    inputs = [prior / "book-1/serial.db", prior / "book-1/checkpoint-1/world.txt",
              parent_run / "manifest.json",
              parent_run / "conditional-goal/request.json",
              parent_run / "adopted-goal/request.json"]
    protected = {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs}
    world = load(inputs[1])
    wanted = {r["record_id"] for r in world}
    with SqliteStore.open_read_only(inputs[0]) as store:
        [(book, branch, _)] = store.branches()
        records = [r for r in store.state_records(book, branch) if r.record_id in wanted]
        times = store.state_record_times(book, branch)
    if {r.record_id for r in records} != wanted:
        raise RuntimeError("Original checkpoint identities are missing")
    for name in ORDER:
        folder = RUN / name
        folder.mkdir(parents=True)
        source = parent_run / ("conditional-goal" if name.endswith("conditional")
                               else "adopted-goal") / "request.json"
        (folder / "request.json").write_bytes(source.read_bytes())
        code, _ = BASE.command(folder, ["new", "Isolated format fixture", "--premise",
                                       "Frozen engineering fixture.", "--scenes", "6"], "new")
        if code:
            raise RuntimeError("Fixture creation failed")
        with SqliteStore.open(folder / "serial.db") as store:
            [(book, branch, head)] = store.branches()
            for record in sorted(records, key=lambda r: (times[r.record_id], r.record_id)):
                event = Event(EventType.STATE_RECORDS_ACCEPTED, "isolated-research",
                    times[record.record_id], book_id=book, branch_id=branch, revision_id=head,
                    payload={"fixture_restore": True, "source_record_id": record.record_id,
                             "source_store_sha256": protected[
                                 inputs[0].relative_to(ROOT).as_posix()]})
                store.record_state_records(book, branch, [record],
                                           created_at=times[record.record_id], events=[event])
        _, output = BASE.command(folder, ["world", "show"], "initial-world")
        if json.loads(output) != world:
            raise RuntimeError("Restored fixture differs from the original checkpoint")
        save(folder / "initial-world.json", world)
    parent_manifest = load(parent_run / "manifest.json")
    binary = Path(parent_manifest["binary"])
    if sha(binary) != parent_manifest["binary_sha256"]:
        raise RuntimeError("Pinned native binary changed")
    auth = subprocess.run([str(binary), "login", "status"], capture_output=True, text=True,
                          check=True)
    if "ChatGPT" not in auth.stdout + auth.stderr:
        raise RuntimeError("Subscription authentication required")
    scripts = [HERE / name for name in ("run.py", "audit.py", "RUNBOOK.md")]
    scripts += [PARENT, BASE.PREVIOUS, ROOT / "tests/test_compact_json_experiment.py"]
    manifest = {"created_at": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", BASE.REVISION], text=True).strip(),
        "binary": str(binary), "binary_sha256": sha(binary),
        "auth": (auth.stdout + auth.stderr).strip(), "source": BASE.hashes(RUN / "source"),
        "dependencies": sorted((d.metadata["Name"], d.version)
                               for d in importlib.metadata.distributions()),
        "protected_inputs": protected,
        "scripts": {p.relative_to(ROOT).as_posix(): sha(p) for p in scripts},
        "requests": {name: sha(RUN / name / "request.json") for name in ORDER},
        "fixtures": {name: sha(RUN / name / "serial.db") for name in ORDER},
        "formats": {name: compact_for_case(name) for name in ORDER},
        "max_calls": BASE.MAX_CALLS, "max_tokens": BASE.MAX_TOKENS,
        "max_seconds": BASE.MAX_SECONDS}
    if any(sha(ROOT / p) != digest for p, digest in protected.items()):
        raise RuntimeError("Protected input changed during preparation")
    for suffix in ("conditional", "adopted"):
        if manifest["requests"][f"compact-{suffix}"] != manifest["requests"][f"verbatim-{suffix}"]:
            raise RuntimeError("Paired application requests differ")
    save(RUN / "manifest.json", manifest)
    save(HERE / "registration.json", {"manifest_sha256": sha(RUN / "manifest.json"),
         "source_revision": manifest["revision"], "assignments": list(ORDER),
         "formats": manifest["formats"], "max_calls": BASE.MAX_CALLS,
         "max_tokens": BASE.MAX_TOKENS, "max_seconds": BASE.MAX_SECONDS})
    print("Prepared four identical worlds and byte-identical paired requests; no model calls.")


def live():
    from litharness.providers.codex_cli import CodexCliProvider

    original = CodexCliProvider.complete

    def configured(provider, request):
        name = Path(os.environ["LITHARNESS_DATABASE"]).parent.name
        provider.compact_tool_json = compact_for_case(name)
        return original(provider, request)

    CodexCliProvider.complete = configured
    try:
        BASE.live()
    finally:
        CodexCliProvider.complete = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inputs", "live"))
    mode = parser.parse_args().mode
    {"prepare": BASE.prepare, "inputs": prepare_inputs, "live": live}[mode]()
