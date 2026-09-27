"""Create, resume and export a serial through the existing production commands.

Each run owns one directory and database. The manifest stores settings and completed
setup receipts; the book, jobs and acceptance decisions remain in the ordinary store.
This is an operator workflow, not the chapter-one reading lane or a research runner.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from litharness import cli
from litharness.adapters.sqlite_store import MigrationsMissing, SqliteStore
from litharness.application.planner import plan_progress
from litharness.domain import directors
from litharness.domain.beats import scene_nodes
from litharness.domain.jobs import JobStatus
from litharness.domain.serials import SerialShape

SCHEMA = "litharness.production-run.v1"
MODEL_ENV = (
    "LITHARNESS_PROVIDER", "LITHARNESS_MODEL_TIERS",
    "LITHARNESS_CLAUDE_MODELS", "LITHARNESS_CODEX_MODELS",
    "LITHARNESS_CODEX_EFFORTS", "LITHARNESS_FAKE_PAD_CHARS",
)
ACTIVE = ("queued", "running", "failed")


def _save(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextlib.contextmanager
def _exclusive(root: Path) -> Iterator[None]:
    """A process lock released by the OS even if the runner is killed."""
    with (root / ".runner.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        _lock(handle, acquire=True)
        try:
            yield
        finally:
            handle.seek(0)
            _lock(handle, acquire=False)


def _lock(handle: BinaryIO, *, acquire: bool) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            mode = fcntl.LOCK_EX | fcntl.LOCK_NB if acquire else fcntl.LOCK_UN
            fcntl.flock(handle.fileno(), mode)
    except OSError as error:
        raise ValueError("this production run is already active in another process") from error


@contextlib.contextmanager
def _environment(saved: dict[str, str | None]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in (*MODEL_ENV, cli.DATABASE_ENV)}
    try:
        for key in MODEL_ENV:
            value = saved.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _invoke(command: list[str], settings: dict[str, Any], log: TextIO) -> int:
    args = cli.build_parser().parse_args(command)
    for key, value in settings.items():
        if key in {"database", "roster_database", "library"} and value is not None:
            value = Path(value)
        setattr(args, key, value)
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            result: int = args.func(args)
            return result
        except (
            OSError, ValueError, sqlite3.Error, MigrationsMissing, directors.IllegalBrief,
        ) as error:
            print(f"litharness: {type(error).__name__}: {error}", file=sys.stderr)
            return cli.EXIT_FAULT


def _load(root: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((root / "run.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported production-run manifest")
    if Path(manifest["settings"]["database"]) != root / "book.db":
        raise ValueError("run directory moved; its recorded database path no longer matches")
    created = any(
        row["stage"] == "create" and row["exit_code"] == 0 for row in manifest["attempts"]
    ) or "seed" in manifest["completed"]
    if created and not (root / "book.db").exists():
        raise ValueError("saved book database is missing; restore it before resuming")
    for relative, expected in manifest["artifacts"].items():
        if _digest(root / relative) != expected:
            raise ValueError(f"saved input changed: {relative}; restore it before resuming")
    return manifest


def _new(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    shape = SerialShape(args.chapter_scenes, args.arc_chapters)
    if shape.scenes_per_arc < 6:
        raise ValueError("an opening arc needs at least six scenes")
    if args.chapters < 1 or args.max_ticks < 1:
        raise ValueError("--chapters and --max-ticks must be positive")
    brief = args.brief_file.read_text(encoding="utf-8") if args.brief_file else args.brief
    defaults = vars(cli.build_parser().parse_args(["tick"]))
    settings = {
        key: str(value.resolve()) if isinstance(value, Path) else value
        for key, value in defaults.items()
        if key not in {"func", "command", "queued_only"}
    }
    settings.update(
        database=str(root / "book.db"), library=str(root / "library"),
        chapter_scenes=args.chapter_scenes, arc_chapters=args.arc_chapters,
    )
    if settings["exemplars"]:
        settings["exemplars"] = str(Path(settings["exemplars"]).resolve())
    for key in (
        "writer", "target_words", "context_budget", "max_tokens_per_day",
        "max_invocations_per_day", "roster_database",
    ):
        value = getattr(args, key)
        if value is not None:
            settings[key] = str(value.resolve()) if isinstance(value, Path) else value
    # Start reserves a new directory; it never adopts or overwrites an existing book.
    root.mkdir(parents=True, exist_ok=False)
    (root / "brief.txt").write_text(brief, encoding="utf-8", newline="\n")
    manifest: dict[str, Any] = {
        "schema": SCHEMA, "book": str(uuid.uuid4()), "branch": str(uuid.uuid4()),
        "settings": settings, "environment": {key: os.environ.get(key) for key in MODEL_ENV},
        "person": args.person, "target_chapters": args.chapters,
        "completed": [], "artifacts": {"brief.txt": _digest(root / "brief.txt")},
        "attempts": [], "state": "ready", "reason": "", "ticks": 0,
    }
    _save(root / "run.json", manifest)
    return manifest


def _snapshot(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    database = root / "book.db"
    report: dict[str, Any] = {
        "chapters": 0, "scenes": 0, "planned_scenes": 0,
        "jobs": {}, "blocked": None, "book_exists": False, "attention": [], "exceptions": [],
    }
    if not database.exists():
        return report
    settings = manifest["settings"]
    shape = SerialShape(settings["chapter_scenes"], settings["arc_chapters"])
    with SqliteStore.open_read_only(database) as store:
        branches = store.branches()
        if any((book, branch) != (manifest["book"], manifest["branch"])
               for book, branch, _ in branches):
            raise ValueError("run database contains another book or branch; refusing to tick it")
        report["jobs"] = store.job_counts_by_status()
        for status in (
            JobStatus.FAILED, JobStatus.PARKED, JobStatus.POISONED, JobStatus.RUNNING,
            JobStatus.QUEUED,
        ):
            for job in store.jobs_by_status(status, limit=5):
                if status == JobStatus.QUEUED and job.lease_holder is None:
                    continue
                report["attention"].append({
                    "id": job.job_id, "status": status.value, "error": job.error,
                    "lease_expires_at": job.lease_expires_at,
                })
        report["exceptions"] = [
            {"id": item.exception_id, "summary": item.summary}
            for item in store.open_exceptions(limit=5)
        ]
        head = store.head(manifest["book"], manifest["branch"])
        if head is None:
            return report
        report["book_exists"] = True
        scenes = tuple(scene_nodes(head))
        report["planned_scenes"] = len(scenes)
        for scene in scenes:
            if not head.node(scene).content:
                break
            report["scenes"] += 1
        report["chapters"] = report["scenes"] // shape.scenes_per_chapter
        args = argparse.Namespace(**settings)
        progress = plan_progress(
            store, manifest["book"], manifest["branch"],
            policy=cli._draft_policy(args), serial_shape=shape,
        )
        report["blocked"] = progress.blocked_reason
    return report


def _stage(
    root: Path, manifest: dict[str, Any], name: str, command: list[str],
    *, output: str | None = None, remember: bool = True,
) -> bool:
    if remember and name in manifest["completed"]:
        return True
    attempts = manifest["attempts"]
    number = attempts[-1].get("number", len(attempts)) + 1 if attempts else 1
    # A crash can leave a directory before its receipt reaches run.json. Keep that
    # evidence and reserve a fresh number, including when reading older manifests.
    while any((root / "attempts").glob(f"{number:05d}-*")):
        number += 1
    attempt = root / "attempts" / f"{number:05d}-{name}"
    attempt.mkdir(parents=True)
    if output:
        command = [*command, "--out", str(attempt)]
    receipt: dict[str, Any] = {
        "stage": name, "command": command, "log": str(attempt.relative_to(root) / "log.txt"),
        "number": number, "started": time.time(), "exit_code": None,
    }
    manifest["attempts"].append(receipt)
    manifest.update(state="running", reason=name)
    _save(root / "run.json", manifest)
    print(f"{name}: running (log: {root / receipt['log']})", flush=True)
    with (attempt / "log.txt").open("w", encoding="utf-8", newline="\n") as log:
        code = _invoke(command, manifest["settings"], log)
    receipt.update(exit_code=code, finished=time.time())
    if code:
        manifest.update(state="attention", reason=f"{name} stopped with exit {code}")
    else:
        if output:
            path = attempt / output
            relative = str(path.relative_to(root))
            manifest["artifacts"][relative] = _digest(path)
            manifest[name + "_path"] = relative
        if remember:
            manifest["completed"].append(name)
        manifest.update(state="ready", reason="")
    _save(root / "run.json", manifest)
    return code == 0


def _stop(
    root: Path, manifest: dict[str, Any], reason: str, *, exit_code: int = cli.EXIT_ATTENTION,
) -> int:
    manifest.update(state="attention", reason=reason)
    _save(root / "run.json", manifest)
    _show(root, manifest)
    return exit_code


def _stopped_stage(root: Path, manifest: dict[str, Any]) -> int:
    """Retain the command's distinction between an operational fault and attention."""
    return _stop(root, manifest, manifest["reason"],
                 exit_code=int(manifest["attempts"][-1]["exit_code"]))


def _show(root: Path, manifest: dict[str, Any]) -> None:
    report = _snapshot(root, manifest)
    print(f"{report['chapters']}/{manifest['target_chapters']} chapters; "
          f"last recorded state: {manifest['state']}")
    print(f"  {report['scenes']} consecutive scenes accepted; jobs {report['jobs']}")
    if manifest["reason"]:
        print(f"  {manifest['reason']}")
    if report["blocked"]:
        print(f"  planner: {report['blocked']}")
    for job in report["attention"]:
        print(f"  {job['status']} {job['id']}: {job['error'] or 'no error recorded'}")
        if job["lease_expires_at"] is not None:
            expires = datetime.fromtimestamp(job["lease_expires_at"], UTC)
            print(f"    lease expires {expires:%Y-%m-%d %H:%M:%S UTC}; resume after expiry")
    for item in report["exceptions"]:
        print(f"  exception {item['id']}: {item['summary']}")
    if manifest["state"] != "complete":
        print(f'  resume: uv run python tools/produce.py resume "{root}"')
        if (root / "book.db").exists():
            print(f'  inspect: uv run litharness --database "{root / "book.db"}" status')
        if manifest["attempts"]:
            last = manifest["attempts"][-1]
            log = root / last["log"]
            print(f"  last log: {log}")
            if last["exit_code"] is None:
                print("  last attempt has no completion receipt; resume checks the saved book")
            elif last["exit_code"] and log.exists():
                for line in log.read_text(encoding="utf-8")[-1500:].splitlines()[-6:]:
                    print(f"    {line}")
    else:
        print(f"  reading copy: {root / 'book.html'}")


def _run(root: Path, manifest: dict[str, Any], *, max_ticks: int) -> int:
    _snapshot(root, manifest)  # Validate the dedicated database before invoking any model.
    shape = SerialShape(
        manifest["settings"]["chapter_scenes"], manifest["settings"]["arc_chapters"],
    )
    scoped = ["--book", manifest["book"], "--branch", manifest["branch"]]
    person = ["--person", manifest["person"]] if manifest["person"] else []
    if not _stage(root, manifest, "concept", [
        "concept", "--brief-file", str(root / "brief.txt"),
        "--scenes", str(shape.scenes_per_arc), *person,
    ], output="concept.json"):
        return _stopped_stage(root, manifest)
    concept_path = str(root / manifest["concept_path"])
    if not _stage(root, manifest, "listing", [
        "listing", "--concept", concept_path, *person,
    ], output="listing.json"):
        return _stopped_stage(root, manifest)
    if not _snapshot(root, manifest)["book_exists"]:
        listing = json.loads((root / manifest["listing_path"]).read_text(encoding="utf-8"))
        if not _stage(root, manifest, "create", [
            "new", listing["title"], "--premise", listing["listing"],
            "--concept", concept_path, "--scenes", str(shape.scenes_per_arc), *person, *scoped,
        ], remember=False):
            return _stopped_stage(root, manifest)
    for name, command in (
        ("seed", ["architect", "seed", *scoped]),
        ("accept-world", ["world", "accept", *scoped]),
    ):
        if not _stage(root, manifest, name, command):
            return _stopped_stage(root, manifest)
    ticks = 0
    while True:
        report = _snapshot(root, manifest)
        reached = report["chapters"] >= manifest["target_chapters"]
        active = sum(report["jobs"].get(status, 0) for status in ACTIVE)
        if report["blocked"] and not active:
            return _stop(root, manifest, report["blocked"])
        if reached and not active:
            if report["exceptions"]:
                return _stop(root, manifest, "chapter target reached; resolve open exceptions")
            if not _stage(root, manifest, "export", [
                "export", str(root / "book.html"), *scoped,
            ], remember=False):
                return _stopped_stage(root, manifest)
            manifest.update(state="complete", reason="chapter target reached; queued work drained")
            _save(root / "run.json", manifest)
            _show(root, manifest)
            return cli.EXIT_OK
        if ticks >= max_ticks:
            return _stop(root, manifest,
                         f"stopped at the per-invocation limit of {max_ticks} ticks")
        if (
            not reached and report["scenes"] == report["planned_scenes"] and not active
            and not _stage(root, manifest, "extend", ["extend", "--arcs", "1", *scoped],
                           remember=False)
        ):
            return _stopped_stage(root, manifest)
        before = report
        if not _stage(root, manifest, "tick", ["tick", *(["--queued-only"] if reached else [])],
                      remember=False):
            return _stopped_stage(root, manifest)
        manifest["ticks"] += 1
        ticks += 1
        _save(root / "run.json", manifest)
        after = _snapshot(root, manifest)
        if after == before:
            return _stop(root, manifest,
                         "no progress; inspect active leases, jobs and planner status")
        if after["chapters"] != before["chapters"]:
            print(f"accepted {after['chapters']}/{manifest['target_chapters']} chapters",
                  flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="create a new run and write to its chapter target")
    start.add_argument("directory", type=Path)
    brief = start.add_mutually_exclusive_group()
    brief.add_argument("--brief", default="")
    brief.add_argument("--brief-file", type=Path)
    start.add_argument("--chapters", type=int, default=6)
    start.add_argument("--chapter-scenes", type=int, default=4)
    start.add_argument("--arc-chapters", type=int, default=6)
    start.add_argument("--person", choices=("first", "third"), default="third")
    start.add_argument("--writer")
    start.add_argument("--roster-database", type=Path)
    for name in ("target-words", "context-budget", "max-tokens-per-day", "max-invocations-per-day"):
        start.add_argument("--" + name, type=int)
    start.add_argument("--max-ticks", type=int, default=1000)
    resume = sub.add_parser("resume", help="continue the saved run, optionally to a later chapter")
    resume.add_argument("directory", type=Path)
    resume.add_argument("--chapters", type=int)
    resume.add_argument("--max-ticks", type=int, default=1000)
    status = sub.add_parser("status", help="read progress without creating or migrating a database")
    status.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    root = args.directory.resolve()
    try:
        if args.command == "status":
            _show(root, _load(root))
            return cli.EXIT_OK
        if args.max_ticks < 1 or (args.chapters is not None and args.chapters < 1):
            raise ValueError("--chapters and --max-ticks must be positive")
        if args.command == "start":
            _new(root, args)
        with _exclusive(root):
            manifest = _load(root)
            if args.command == "resume" and args.chapters is not None:
                if args.chapters < manifest["target_chapters"]:
                    raise ValueError("resume cannot lower the saved chapter target")
                manifest["target_chapters"] = args.chapters
                _save(root / "run.json", manifest)
            with _environment(manifest["environment"]):
                return _run(root, manifest, max_ticks=args.max_ticks)
    except KeyboardInterrupt:
        print(f'Interrupted. Resume with: uv run python tools/produce.py resume "{root}"')
        return cli.EXIT_ATTENTION
    except (OSError, ValueError, KeyError, sqlite3.Error, MigrationsMissing) as error:
        print(f"produce: {error}", file=sys.stderr)
        return cli.EXIT_FAULT


if __name__ == "__main__":
    raise SystemExit(main())
