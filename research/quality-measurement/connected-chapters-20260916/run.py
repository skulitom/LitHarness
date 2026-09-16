"""Compare first-draw production workflows through three chapters, without story selection."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/connected-chapters-20260916"
REVISION = "79f4da7"
OWNER = "connected-chapters-20260916: root task;"
LIMITS = {
    "calls": 140,
    "tokens": 2500000,
    "seconds": 10800,
    "book_calls": 40,
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
    "grow2",
    "accept-grow2",
    "chapter3",
    "drain3",
)
SUPPORT = HERE.parent / "experience-workflow-continuation-20260915/run.py"
HANDOFF = HERE.parent / "planning-material-20260916/inspect_handoff.py"
TEST = ROOT / "tests/test_connected_chapters_experiment.py"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


support = module("connected_chapter_transport", SUPPORT)
base = support.base
BASE_PATH = Path(base.__file__)
original_command = base.command
original_base_args = base.base_args


def command(book, phase):
    if phase not in PHASES:
        raise ValueError("Unregistered phase")
    if phase.startswith("grow"):
        return ["architect", "grow", "--scene", f"scene-{phase[-1]}"]
    if phase in {"chapter3", "drain3"}:
        return ["tick"]
    result = original_command(book, phase)
    if phase == "concept" and book.startswith("B"):
        result.append("--planning-material")
    return result


def base_args(book):
    result = original_base_args(book)
    result[result.index("--holder") + 1] = "connected-chapters"
    result[result.index("--max-invocations-per-day") + 1] = str(LIMITS["book_calls"])
    return result


def configure():
    base.LOCAL, base.HERE, base.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.INPUTS = base.read(HERE / "inputs.json")
    base.REVISIONS = {"A": REVISION, "B": REVISION}
    base.LIMITS, base.OWNER, base.PHASES = LIMITS, OWNER, PHASES
    base.command, base.base_args, base.claim = command, base_args, claim
    base.transport_details = lambda raw, payload, book: support.details(raw, payload, book, LOCAL)


def claim(status):
    files = [("registration", HERE / name) for name in ("RUNBOOK.md", "registration.json")]
    if status == "observed":
        files += [("derived_result", HERE / "evidence.json")]
        if (HERE / "handoff-evidence.json").exists():
            files += [("control_result", HERE / "handoff-evidence.json")]
    base.write(
        HERE / "claim.json",
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": "connected-chapters-20260916",
            "status": status,
            "statement": "The registered first-draw workflow comparison records intended and "
            "enacted activity across reached consecutive chapters, with located continuation "
            "observations and production controls. It licenses no literary-quality effect.",
            "artifacts": [
                {"kind": kind, "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
                for kind, p in files
            ],
        },
    )


def registered_files():
    return [
        Path(__file__),
        HERE / "audit.py",
        HERE / "RUNBOOK.md",
        HERE / "inputs.json",
        TEST,
        SUPPORT,
        BASE_PATH,
        HANDOFF,
    ]


def prepare():
    base.prepare()
    for book in base.order("concept"):
        subprocess.run(
            [str(base.python_for(book[0])), str(Path(__file__)), "preflight", book],
            cwd=ROOT,
            env=base.environment(book) | {"LITHARNESS_ENV": "test"},
            check=True,
        )
    manifest = base.read(LOCAL / "manifest.json")
    manifest["files"].update({str(p): base.sha(p) for p in registered_files()})
    manifest["files"].update({str(p): base.sha(p) for p in (LOCAL / "preflight").glob("*.json")})
    manifest.update(
        chapters_per_book=3, source_pairing="same author brief and seed; fresh invention"
    )
    base.write(LOCAL / "manifest.json", manifest)
    base.write(
        HERE / "registration.json",
        manifest | {"manifest_sha256": base.sha(LOCAL / "manifest.json")},
    )
    claim("registered")


def preflight(book):
    from litharness import cli

    if os.environ.get("LITHARNESS_ENV") != "test":
        raise RuntimeError("Preflight requires billing disabled")
    reached = []

    def stop(request, **kwargs):
        reached.append(base.serial(request))
        return None, "registered offline boundary"

    original = cli._completion_call
    cli._completion_call = stop
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(base_args(book) + command(book, "concept"))
    finally:
        cli._completion_call = original
    expected = "writer.concept.material.v1" if book.startswith("B") else "writer.discovery.v13"
    if code != 2 or len(reached) != 1 or reached[0]["profile"] != expected:
        raise RuntimeError(
            f"Concept boundary unexpected: {code}, {[r['profile'] for r in reached]}"
        )
    if reached[0]["allowed_tools"]:
        raise RuntimeError("Concept invention unexpectedly allows tools")
    base.write(LOCAL / "preflight" / f"{book}.json", {"provider_calls": 0, "request": reached[0]})


def execute(book, phase):
    for iteration in range(1, LIMITS["ticks_per_phase"] + 1):
        state = base.read(LOCAL / "progress.json")
        if state.get("stop") or state["books"][book]["status"] != "running":
            return
        if phase.startswith("drain") and base.metadata(book)["pending"] == 0:
            return
        state["active"] = f"{phase}-{book}-{iteration}"
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
        row = base.read(LOCAL / "steps" / f"{phase}-{book}-{iteration}.json")
        state = base.read(LOCAL / "progress.json")
        meta = row["after"]
        state["books"][book].update(phase=phase, **meta)
        failed = (
            meta["terminal"] > 0
            or meta["accepted"] > 3
            or row["returncode"] == 2
            or (row["returncode"] != 0 and not phase.startswith(("chapter", "drain")))
            or "no_work tick=" in row["stdout"]
        )
        done = base.phase_done(phase, meta)
        if failed or (iteration == LIMITS["ticks_per_phase"] and not done):
            state["books"][book].update(status="stopped", reason=f"workflow stopped in {phase}")
        base.write(LOCAL / "progress.json", state)
        print(
            json.dumps(
                {
                    "book": book,
                    "phase": phase,
                    "accepted": meta["accepted"],
                    "status": state["books"][book]["status"],
                    "calls": len(state["calls"]),
                    "tokens": sum(c["tokens"] for c in state["calls"]),
                }
            ),
            flush=True,
        )
        if failed or done or state.get("stop"):
            return


def run():
    base.lock()
    base.verify_frozen()
    if os.environ.get("LITHARNESS_ENV") == "test" or (LOCAL / "progress.json").exists():
        raise RuntimeError("No test-mode, duplicate or implicit-resume dispatch")
    for path in [*registered_files(), HERE / "registration.json", HERE / "claim.json"]:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        if committed != path.read_bytes():
            raise RuntimeError(f"Uncommitted registration input: {path}")
    base.write(
        LOCAL / "progress.json",
        {
            "status": "running",
            "started_at": base.now(),
            "calls": [],
            "books": {book: {"status": "running", "accepted": 0} for book in base.order("concept")},
        },
    )
    try:
        for phase in PHASES:
            for book in base.order(phase):
                execute(book, phase)
            if base.read(LOCAL / "progress.json").get("stop"):
                break
    except BaseException as error:
        state = base.read(LOCAL / "progress.json")
        state["stop"] = f"scheduler failure: {error!r}"
        base.write(LOCAL / "progress.json", state)
        raise
    finally:
        state = base.read(LOCAL / "progress.json")
        state.pop("active", None)
        for item in state["books"].values():
            if (
                item["status"] == "running"
                and item.get("accepted") == 3
                and item.get("pending") == 0
                and not item.get("terminal")
            ):
                item["status"] = "complete"
        state.update(
            status="complete"
            if not state.get("stop")
            and all(b["status"] == "complete" for b in state["books"].values())
            else "partial",
            finished_at=base.now(),
        )
        base.write(LOCAL / "progress.json", state)


def collect(book):
    from litharness import cli

    base.collect(book)
    if not (base.book_root(book) / "book.db").exists():
        return
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli.main([*base_args(book), "why", "--scene", "3", "--json"])
    base.write(
        base.book_root(book) / "views/chapter3.json",
        {"returncode": code, "output": output.getvalue()},
    )


def audit():
    reader = module("connected_chapters_readout", HERE / "audit.py")
    reader.audit(base)
    handoff = module("connected_chapters_handoff", HANDOFF)
    handoff.LOCAL, handoff.HERE = LOCAL, HERE
    handoff.inspect()
    claim("observed")


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "collect":
        collect(sys.argv[2])
    elif mode == "preflight":
        preflight(sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
