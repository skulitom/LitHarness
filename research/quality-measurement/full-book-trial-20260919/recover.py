"""One registered recovery of the preserved second-arc contract failure."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import sysconfig
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("book_recovery", HERE / "run.py")
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)
trial.configure()
base, LOCAL = trial.base, trial.LOCAL
STOP = LOCAL / "arc2-stop"
SOURCE = LOCAL / "sources/A/recovery"
RUNTIME = LOCAL / "runtimes/A-recovery"
JOB = "outline-05469bc2bdcee1a70d2bca32"
EXCEPTION = "exc-0c297ba9d5355d0f54499106"
original_metadata = trial.metadata


def metadata(book):
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.jobs import JobStatus

    result = original_metadata(book)
    if not base.read(LOCAL / "progress.json").get("recovery_ready"):
        return result
    with SqliteStore.open_read_only(base.book_root(book) / "book.db") as store:
        old = [j for j in store.jobs_by_status(JobStatus.POISONED, limit=10000) if j.job_id == JOB]
        if (len(old) != 1 or old[0].attempts != 3
                or store.plan_epoch("experience-A1", "main") <= old[0].payload["plan_epoch"]):
            raise RuntimeError("Historical failure or recovery epoch changed")
    result["historical_terminal_ids"] = [JOB]
    result["terminal"] -= 1
    return result


trial.metadata = base.metadata = metadata
trial.__file__ = base.__file__ = str(Path(__file__).resolve())
base.python_for = lambda arm: RUNTIME / "Scripts/python.exe"


def files():
    return [HERE / name for name in ("recover.py", "RECOVERY.md", "run.py", "audit.py")] + [
        trial.TEST, trial.ROOT / "tests/test_outline_payoff_scope.py"]


def stopped():
    state = base.read(STOP / "progress.json")
    current = original_metadata("A1")
    if (state["status"] != "partial" or len(state["calls"]) != 41
            or sum(c["tokens"] for c in state["calls"]) != 1014525
            or any(c["status"] != "completed" for c in state["calls"])
            or current["accepted"] != 6 or current["total"] != 12 or current["pending"]
            or current["terminal"] != 1 or current["exceptions"] != 1
            or current["scene_hashes"] != state["books"]["A1"]["scene_hashes"]
            or base.read(LOCAL / "progress.json") != state
            or base.sha(base.book_root("A1") / "book.db") != base.sha(STOP / "book.db")):
        raise RuntimeError("Not the exact registered second-arc stop")
    return state, current


def prepare():
    base.lock()
    if (HERE / "recovery.json").exists() or SOURCE.exists() or RUNTIME.exists():
        raise RuntimeError("Recovery already prepared")
    state, current = stopped()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    changes = subprocess.check_output(
        ["git", "diff", "--name-only", trial.REVISION, revision, "--", "src", "migrations"],
        text=True,
    ).splitlines()
    if changes != ["src/litharness/application/outline.py"]:
        raise RuntimeError("Production recovery contains unexpected changes")
    archive = LOCAL / "source-recovery.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--output={archive}", revision,
                    "src", "migrations", "pyproject.toml", "uv.lock"], check=True)
    with zipfile.ZipFile(archive) as packed:
        packed.extractall(SOURCE)
    venv.EnvBuilder(with_pip=False).create(RUNTIME)
    pth = RUNTIME / "Lib/site-packages/experiment-source.pth"
    pth.write_text(str(SOURCE / "src") + "\n" + sysconfig.get_path("purelib") + "\n",
                   encoding="utf-8")
    manifest = base.read(STOP / "manifest.json")
    mutable = {str(p) for p in files()}
    for name, expected in manifest["files"].items():
        if name not in mutable and base.sha(name) != expected:
            raise RuntimeError(f"Original frozen input changed: {name}")
    captured = [*files(), archive, pth, RUNTIME / "pyvenv.cfg", base.python_for("A"),
                *SOURCE.rglob("*"), *STOP.rglob("*")]
    manifest["files"].update({str(p): base.sha(p) for p in captured if p.is_file()})
    manifest["recovery_revision"] = revision
    base.write(LOCAL / "manifest.json", manifest)
    base.write(HERE / "recovery.json", {
        "schema": "litharness.full-book-recovery.v1", "production_revision": revision,
        "historical_poisoned_job": JOB, "exception": EXCEPTION,
        "original_calls": 41, "original_tokens": 1014525,
        "original_started_at": state["started_at"], "limits": trial.LIMITS,
        "stopped_metadata": current, "frozen_files": manifest["files"],
        "manifest_sha256": base.sha(LOCAL / "manifest.json"),
    })
    trial.claim("registered")


def recover_store():
    from litharness import cli

    reason = "Outline contract fixed; preserve debts and accepted prose; replan unwritten arc."
    before = original_metadata("A1")
    commands = [["resolve", EXCEPTION, reason], ["replan", "--reason", reason]]
    os.environ["LITHARNESS_ENV"] = "test"
    rows = []
    try:
        for command in commands:
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                code = cli.main(base.base_args("A1") + command)
            rows.append({"arguments": command, "returncode": code, "output": output.getvalue()})
            base.write(LOCAL / "recovery-operations.json", {"before": before, "operations": rows})
            if code:
                raise RuntimeError("Recovery operation failed")
    finally:
        os.environ.pop("LITHARNESS_ENV", None)
    after = original_metadata("A1")
    if (after["scene_hashes"] != before["scene_hashes"] or after["head"] != before["head"]
            or after["accepted"] != 6 or after["total"] != 12 or after["exceptions"]):
        raise RuntimeError("Recovery changed manuscript or left exceptions")
    base.write(LOCAL / "recovery-operations.json", {
        "before": before, "operations": rows, "after": after, "provider_calls": 0})


def run():
    base.lock()
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("No live test-mode recovery")
    base.verify_frozen()
    state, _ = stopped()
    for path in [*files(), HERE / "recovery.json", HERE / "claim.json"]:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(trial.ROOT).as_posix()}"], cwd=trial.ROOT)
        if committed != path.read_bytes():
            raise RuntimeError(f"Uncommitted recovery input: {path}")
    if base.admission(state, "A1", base.now()):
        raise RuntimeError("Original budget exhausted before recovery")
    state.update(recovery_started_at=base.now(), status="running")
    base.write(LOCAL / "progress.json", state)
    try:
        recover_store()
        state["recovery_ready"] = True
        state["books"]["A1"].update(status="running", reason=None)
        base.write(LOCAL / "progress.json", state)
        for phase in trial.PHASES[trial.PHASES.index("chapter7"):]:
            trial.execute("A1", phase, start_iteration=4 if phase == "chapter7" else 1)
            state = base.read(LOCAL / "progress.json")
            if state.get("stop") or state["books"]["A1"]["status"] == "stopped":
                break
    except BaseException as error:
        state = base.read(LOCAL / "progress.json")
        state["stop"] = f"recovery failure: {error!r}"
        base.write(LOCAL / "progress.json", state)
        raise
    finally:
        state = base.read(LOCAL / "progress.json")
        state.pop("active", None)
        try:
            current = metadata("A1")
            complete = (not state.get("stop") and state["books"]["A1"]["status"] == "running"
                        and current["accepted"] == current["total"] == trial.CHAPTERS
                        and not current["pending"] and not current["terminal"]
                        and not current["exceptions"])
            state["books"]["A1"].update(current, status="complete" if complete else "stopped")
            state["status"] = "complete" if complete else "partial"
        except Exception as error:
            state.update(status="partial", finalization_error=repr(error))
        state["finished_at"] = base.now()
        base.write(LOCAL / "progress.json", state)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "collect":
        trial.collect(sys.argv[2])
    elif mode == "audit":
        trial.module("recovery_audit", HERE / "audit.py").audit(trial)
    else:
        {"prepare": prepare, "run": run}[mode]()
