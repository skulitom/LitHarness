"""One frozen four-arc book trial; structural completion is not a quality verdict."""

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
LOCAL = ROOT / "runs/full-book-trial-20260919"
REVISION = "6c3bda417a994724a34355ae18e9561003223bc8"
BINARY = Path("C:/Users/artem/AppData/Local/OpenAI/Codex/bin/247581e40ee272fb/codex.exe")
OWNER = "full-book-trial-20260919: root task;"
CHAPTERS = 24
ARC = 6
LIMITS = {"calls": 300, "tokens": 8000000, "seconds": 14400,
          "book_calls": 300, "ticks_per_phase": 20}
SUPPORT = HERE.parent / "experience-workflow-continuation-20260915/run.py"
TEST = ROOT / "tests/test_full_book_trial.py"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


support = module("full_book_transport", SUPPORT)
base = support.base
BASE_PATH = Path(base.__file__)
original_metadata = base.metadata
original_command = base.command


def phases():
    result = ["concept", "new", "seed", "accept-seed"]
    for chapter in range(1, CHAPTERS + 1):
        result += [f"chapter{chapter}", f"drain{chapter}"]
        if chapter < CHAPTERS and chapter % 3 == 0:
            result += [f"grow{chapter}", f"accept-grow{chapter}"]
        if chapter < CHAPTERS and chapter % ARC == 0:
            result.append(f"extend{chapter}")
    return tuple(result)


PHASES = phases()


def configure():
    base.LOCAL, base.HERE, base.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.INPUTS = base.read(HERE / "inputs.json")
    base.REVISIONS, base.BINARY = {"A": REVISION}, BINARY
    base.LIMITS, base.OWNER, base.PHASES = LIMITS, OWNER, PHASES
    base.base_args, base.command, base.metadata, base.claim = base_args, command, metadata, claim
    base.order = lambda phase: ("A1",)
    base.transport_details = lambda raw, payload, book: support.details(raw, payload, book, LOCAL)


def base_args(book):
    return ["--database", str(base.book_root(book) / "book.db"), "--writer", "halloran",
            "--holder", "full-book-trial", "--chapter-scenes", "1", "--arc-chapters", str(ARC),
            "--volume-chapters", str(CHAPTERS), "--target-words", "2200",
            "--library", str(base.book_root(book) / "library"),
            "--max-invocations-per-day", str(LIMITS["calls"]),
            "--max-tokens-per-day", str(LIMITS["tokens"])]


def metadata(book):
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.beats import scene_nodes

    result = original_metadata(book)
    database = base.book_root(book) / "book.db"
    result.update(total=0, scene_ids=[], exceptions=0)
    if database.exists():
        with SqliteStore.open_read_only(database) as store:
            branches = store.branches()
            head = store.head(*branches[0][:2]) if branches else None
            scenes = scene_nodes(head) if head else ()
            result.update(total=len(scenes), scene_ids=list(scenes),
                          exceptions=len(store.open_exceptions()))
    return result


def command(book, phase):
    if phase not in PHASES:
        raise ValueError("Unregistered phase")
    if phase.startswith("grow"):
        chapter = int(phase.removeprefix("grow"))
        return ["architect", "grow", "--scene", metadata(book)["scene_ids"][chapter - 1]]
    if phase.startswith("extend"):
        return ["extend", "--arcs", "1"]
    if phase.startswith(("chapter", "drain")):
        return ["tick"]
    result = original_command(book, phase)
    if phase == "concept":
        result.append("--planning-material")
    return result


def claim(status):
    files = [("registration", HERE / name) for name in ("RUNBOOK.md", "registration.json")]
    if (HERE / "continuation.json").exists():
        files += [("registration", HERE / name)
                  for name in ("CONTINUATION.md", "continuation.json")]
    if status == "observed":
        files.append(("derived_result", HERE / "evidence.json"))
    base.write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1", "claim_id": "full-book-trial-20260919",
        "status": status,
        "statement": "The frozen single-book trial records reached chapters, arc transitions, "
        "operational controls and located story-delivery observations. No quality benefit, "
        "reader qualification or release approval is licensed.",
        "artifacts": [{"kind": kind, "path": p.relative_to(ROOT).as_posix(),
                       "sha256": base.sha(p)} for kind, p in files],
    })


def registered_files():
    return [Path(__file__), HERE / "audit.py", HERE / "RUNBOOK.md", HERE / "inputs.json",
            TEST, SUPPORT, BASE_PATH]


def preflight(book):
    from litharness import cli

    if os.environ.get("LITHARNESS_ENV") != "test":
        raise RuntimeError("Preflight requires billing disabled")
    reached = []

    def stop(request, **kwargs):
        reached.append(base.serial(request))
        return None, "offline boundary"

    original = cli._completion_call
    cli._completion_call = stop
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(base_args(book) + command(book, "concept"))
    finally:
        cli._completion_call = original
    if (code != 2 or len(reached) != 1
            or reached[0]["profile"] != "writer.concept.material.v1"
            or reached[0]["allowed_tools"]):
        raise RuntimeError("Unexpected invention boundary")
    base.write(LOCAL / "preflight.json", {"provider_calls": 0, "request": reached[0]})


def prepare():
    base.prepare()
    subprocess.run([str(base.python_for("A")), str(Path(__file__)), "preflight", "A1"],
                   cwd=ROOT, env=base.environment("A1") | {"LITHARNESS_ENV": "test"}, check=True)
    manifest = base.read(LOCAL / "manifest.json")
    manifest["files"].update({str(p): base.sha(p)
                              for p in [*registered_files(), LOCAL / "preflight.json"]})
    manifest.update(chapters=CHAPTERS, arcs=CHAPTERS // ARC, target_words_per_chapter=2200)
    base.write(LOCAL / "manifest.json", manifest)
    base.write(HERE / "registration.json",
               manifest | {"manifest_sha256": base.sha(LOCAL / "manifest.json")})
    claim("registered")


def phase_done(phase, meta):
    if phase.startswith("chapter"):
        return meta["accepted"] == int(phase.removeprefix("chapter"))
    if phase.startswith("drain"):
        return meta["pending"] == 0
    return True


def transition_error(phase, before, after):
    if after["terminal"] or after.get("exceptions"):
        return "terminal job or open exception"
    if any(after.get("scene_hashes", {}).get(key) != value
           for key, value in before.get("scene_hashes", {}).items()):
        return "accepted manuscript changed"
    if after["accepted"] > CHAPTERS or after.get("total", 0) > CHAPTERS:
        return "volume boundary exceeded"
    if phase.startswith("chapter") and after["accepted"] > int(phase.removeprefix("chapter")):
        return "chapter boundary exceeded"
    if phase.startswith("extend"):
        boundary = int(phase.removeprefix("extend"))
        if (before["accepted"] != boundary or before["total"] != boundary
                or before["pending"] or after["total"] != boundary + ARC
                or after["accepted"] != boundary):
            return "invalid arc extension"
    elif phase not in ("new", "concept") and after.get("total") != before.get("total"):
        return "unexpected scene count change"
    return None


def execute(book, phase):
    for iteration in range(1, LIMITS["ticks_per_phase"] + 1):
        state = base.read(LOCAL / "progress.json")
        if state.get("stop") or state["books"][book]["status"] != "running":
            return
        before = metadata(book)
        if phase.startswith("drain") and not before["pending"]:
            return
        reason = base.admission(state, book, base.now())
        if phase.startswith("extend"):
            boundary = int(phase.removeprefix("extend"))
            if before["accepted"] != boundary or before["total"] != boundary or before["pending"]:
                reason = "refused extension of incomplete or undrained arc"
        if reason:
            state["stop"] = reason
            base.write(LOCAL / "progress.json", state)
            return
        key = f"{phase}-{book}-{iteration}"
        if (LOCAL / "steps" / f"{key}.json").exists():
            raise RuntimeError("Refusing duplicate step")
        state["active"] = key
        base.write(LOCAL / "progress.json", state)
        subprocess.run([str(base.python_for(book[0])), str(Path(__file__)), "step", book,
                        phase, str(iteration)], cwd=ROOT, env=base.environment(book), check=True)
        row = base.read(LOCAL / "steps" / f"{key}.json")
        after = row["after"]
        state = base.read(LOCAL / "progress.json")
        state["books"][book].update(phase=phase, **after)
        error = transition_error(phase, row["before"], after)
        if (row["returncode"] == 2
                or (row["returncode"] and not phase.startswith(("chapter", "drain")))):
            error = error or "operational exit"
        done = phase_done(phase, after)
        if "no_work tick=" in row["stdout"] and not done:
            error = error or "idle before target"
        if iteration == LIMITS["ticks_per_phase"] and not done:
            error = error or "phase ceiling"
        if error:
            state["books"][book].update(status="stopped", reason=f"{phase}: {error}")
        base.write(LOCAL / "progress.json", state)
        print(json.dumps({"phase": phase, "chapters": after["accepted"],
                          "calls": len(state["calls"]),
                          "tokens": sum(c["tokens"] for c in state["calls"]),
                          "stop": state.get("stop") or error}), flush=True)
        if error or done or state.get("stop"):
            return


def run():
    base.lock()
    base.verify_frozen()
    if os.environ.get("LITHARNESS_ENV") == "test" or (LOCAL / "progress.json").exists():
        raise RuntimeError("No test-mode, duplicate or implicit-resume dispatch")
    for path in [*registered_files(), HERE / "registration.json", HERE / "claim.json"]:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT,
        )
        if committed != path.read_bytes():
            raise RuntimeError(f"Uncommitted registration input: {path}")
    base.write(LOCAL / "progress.json", {
        "status": "running", "started_at": base.now(), "calls": [],
        "books": {"A1": {"status": "running", "accepted": 0}},
    })
    try:
        for phase in PHASES:
            execute("A1", phase)
            state = base.read(LOCAL / "progress.json")
            if state.get("stop") or state["books"]["A1"]["status"] == "stopped":
                break
    except BaseException as error:
        state = base.read(LOCAL / "progress.json")
        state["stop"] = f"scheduler failure: {error!r}"
        base.write(LOCAL / "progress.json", state)
        raise
    finally:
        state = base.read(LOCAL / "progress.json")
        state.pop("active", None)
        try:
            current = metadata("A1")
        except Exception as error:
            state.update(status="partial", finished_at=base.now(),
                         finalization_error=repr(error))
            base.write(LOCAL / "progress.json", state)
            raise
        book = state["books"]["A1"]
        complete = (not state.get("stop") and book["status"] == "running"
                    and current["accepted"] == current["total"] == CHAPTERS
                    and not current["pending"] and not current["terminal"]
                    and not current["exceptions"])
        book.update(current, status="complete" if complete else "stopped")
        state.update(status="complete" if complete else "partial", finished_at=base.now())
        base.write(LOCAL / "progress.json", state)


def collect(book):
    from litharness import cli

    base.collect(book)
    if not (base.book_root(book) / "book.db").exists():
        return
    for n in range(1, metadata(book)["accepted"] + 1):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main([*base_args(book), "why", "--scene", str(n), "--json"])
        base.write(base.book_root(book) / f"views/chapter{n}.json",
                   {"returncode": code, "output": output.getvalue()})


def audit():
    module("full_book_audit", HERE / "audit.py").audit(sys.modules[__name__])


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode in {"collect", "preflight"}:
        {"collect": collect, "preflight": preflight}[mode](sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
