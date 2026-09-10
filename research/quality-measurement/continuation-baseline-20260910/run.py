"""Bounded driver of the ordinary CLI, with a frozen runtime and complete call receipts."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import importlib.metadata
import io
import json
import os
import subprocess
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/continuation-baseline-20260910"
REVISION = "d5ccb9ec7a244e8a573a0c26612373672d3c2bd7"
OWNER = "continuation-baseline-20260910: root task;"
MAX_CALLS = 120
MAX_TOKENS = 2_000_000
BOOK_CALLS = 40
BOOK_TOKENS = 700_000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_lock() -> None:
    holder = ROOT / "runs/box.lock/holder"
    if not holder.is_file() or not holder.read_text(encoding="utf-8-sig").startswith(OWNER):
        raise RuntimeError("This task does not own runs/box.lock")


def hashes(directory: Path) -> dict[str, str]:
    return {
        p.relative_to(directory).as_posix(): sha(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }


def prepare() -> None:
    check_lock()
    if (RUN / "manifest.json").exists() or (RUN / "source").exists():
        raise RuntimeError("Runtime already exists; preparation does not overwrite")
    RUN.mkdir(parents=True, exist_ok=True)
    archive = RUN / "source.zip"
    subprocess.run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--output={archive}",
            REVISION,
            "src",
            "migrations",
            "pyproject.toml",
            "uv.lock",
        ],
        cwd=ROOT,
        check=True,
    )
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(RUN / "source")
    subprocess.run(
        ["uv", "venv", "--python", str(ROOT / ".venv/Scripts/python.exe"), str(RUN / "runtime")],
        cwd=ROOT,
        check=True,
    )
    site = RUN / "runtime/Lib/site-packages"
    (site / "frozen_baseline.pth").write_text(
        str(RUN / "source/src") + "\n" + str(ROOT / ".venv/Lib/site-packages") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    candidates = list((Path(os.environ["LOCALAPPDATA"]) / "OpenAI/Codex/bin").glob("*/codex.exe"))
    binary = max(candidates, key=lambda p: p.stat().st_mtime)
    version = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    auth = subprocess.run(
        [str(binary), "login", "status"], capture_output=True, text=True, check=True
    )
    if version != "codex-cli 0.153.4" or "ChatGPT" not in auth.stdout + auth.stderr:
        raise RuntimeError("Registered version or subscription authentication differs")
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "revision": REVISION,
        "source_sha256": hashes(RUN / "source"),
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "version": version,
        "experiment_sha256": {p.name: sha(p) for p in HERE.iterdir() if p.is_file()},
        "dependencies": sorted(
            (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
        ),
        "auth_status": (auth.stdout + auth.stderr).strip(),
        "excluded_worktree_diff": subprocess.run(
            ["git", "diff", "--stat"], cwd=ROOT, capture_output=True, text=True
        ).stdout,
    }
    save(RUN / "manifest.json", manifest)
    print("Prepared frozen runtime; no model calls.")


class StopRun(RuntimeError):
    pass


def run() -> None:
    check_lock()
    manifest = load(RUN / "manifest.json")
    if (RUN / "progress.json").exists():
        raise RuntimeError("Run already started; refusing an implicit resume")
    if hashes(RUN / "source") != manifest["source_sha256"]:
        raise RuntimeError("Frozen source changed")
    for name, digest in manifest["experiment_sha256"].items():
        if sha(HERE / name) != digest:
            raise RuntimeError(f"Experiment changed: {name}")
    # Only explicitly registered application configuration enters this process.
    for key in list(os.environ):
        if key.startswith("LITHARNESS_"):
            del os.environ[key]
    os.environ.update(LITHARNESS_PROVIDER="codex", LITHARNESS_CODEX_BINARY=manifest["binary"])
    from litharness import cli
    from litharness.application.handlers import SCENE_DRAFT
    from litharness.providers import build_default_registry
    from litharness.providers.codex_cli import CodexCliProvider

    if not Path(cli.__file__).is_relative_to(RUN / "source"):
        raise RuntimeError("Interpreter did not import frozen source")
    installed = sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
    if [list(item) for item in installed] != manifest["dependencies"]:
        raise RuntimeError("Installed dependency inventory changed")
    started = time.monotonic()
    progress = {
        "started_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "calls": 0,
        "tokens": 0,
        "books": [],
        "fatal": None,
    }
    book = {}
    active_dir = RUN
    command_number = 0
    original_complete = CodexCliProvider.complete

    def recorded_complete(provider, request):
        check_lock()
        if hashes(RUN / "source") != manifest["source_sha256"]:
            progress["fatal"] = "frozen source drift"
            raise StopRun(progress["fatal"])
        if progress["fatal"]:
            raise StopRun(progress["fatal"])
        if sha(Path(manifest["binary"])) != manifest["binary_sha256"]:
            progress["fatal"] = "native binary drift"
            raise StopRun(progress["fatal"])
        if progress["calls"] >= MAX_CALLS or progress["tokens"] >= MAX_TOKENS:
            progress["fatal"] = "aggregate bound reached"
            raise StopRun(progress["fatal"])
        if time.monotonic() - started >= 10_800:
            progress["fatal"] = "three-hour new-call bound reached"
            raise StopRun(progress["fatal"])
        if book["calls"] >= BOOK_CALLS or book["tokens"] >= BOOK_TOKENS:
            raise StopRun("book bound reached")
        progress["calls"] += 1
        book["calls"] += 1
        receipt = active_dir / "calls" / f"{book['calls']:03d}.json"
        row = {
            "started_at": datetime.now(UTC).isoformat(),
            "request": dataclasses.asdict(request),
            "aggregate_attempt": progress["calls"],
            "status": "started",
        }
        save(receipt, row)
        save(RUN / "progress.json", progress)
        print(f"{book['id']}: call {book['calls']} {request.profile}", flush=True)
        try:
            result = original_complete(provider, request)
            row.update(status="completed", result=dataclasses.asdict(result))
            usage = result.usage.total
            if usage <= 0:
                progress["fatal"] = "unknown or zero reported usage"
                raise StopRun(progress["fatal"])
            progress["tokens"] += usage
            book["tokens"] += usage
            return result
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}")
            progress["fatal"] = row["error"]
            raise
        finally:
            row["finished_at"] = datetime.now(UTC).isoformat()
            save(receipt, row)
            save(RUN / "progress.json", progress)

    CodexCliProvider.complete = recorded_complete
    registry = build_default_registry()
    cli.build_default_registry = lambda: registry

    def command(args: list[str], *, name: str = "command") -> tuple[int, str]:
        nonlocal command_number
        command_number += 1
        argv = [
            "--database",
            str(active_dir / "serial.db"),
            "--library",
            str(active_dir / "library"),
            "--holder",
            "continuation-baseline-20260910",
            "--chapter-scenes",
            "1",
            "--arc-chapters",
            "6",
            "--target-words",
            "1800",
            "--max-invocations-per-day",
            "40",
            "--max-tokens-per-day",
            "700000",
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
        save(
            active_dir / "commands" / f"{command_number:03d}-{name}.json",
            {"argv": argv, "exit_code": code, "output": text},
        )
        print(
            f"{book['id']}: {name} exit={code}; calls={book['calls']} tokens={book['tokens']}",
            flush=True,
        )
        return code, text

    def must(args: list[str], name: str) -> str:
        code, output = command(args, name=name)
        if code:
            raise StopRun(f"{name} exit={code}: {output[-1500:]}")
        return output

    def checkpoint(label: str) -> dict:
        destination = active_dir / label
        destination.mkdir(exist_ok=True)
        audit = {}
        for name, args in [
            ("audit", ["audit", "--json"]),
            ("status", ["status", "--json"]),
            ("jobs", ["jobs", "--status", "queued", "--json"]),
            ("plans", ["plans", "--json"]),
            ("state", ["state", "--json"]),
            ("verify", ["verify", "--json"]),
            ("world", ["world", "show"]),
        ]:
            code, output = command(args, name=f"{label}-{name}")
            (destination / f"{name}.txt").write_text(output, encoding="utf-8", newline="\n")
            if name == "audit" and code in (0, 1):
                audit = json.loads(output)
        chapter_files = sorted((active_dir / "library").glob("*/chapters/Chapter*.txt"))
        chapter_hashes = {p.name: sha(p) for p in chapter_files}
        old = book.get("chapter_hashes", {})
        if any(chapter_hashes.get(name) != digest for name, digest in old.items()):
            progress["fatal"] = "an earlier accepted chapter changed"
            raise StopRun(progress["fatal"])
        book["chapter_hashes"] = chapter_hashes
        save(destination / "chapter-hashes.json", chapter_hashes)
        book["chapters"] = audit.get("chapters_drafted", 0)
        save(RUN / "progress.json", progress)
        return audit

    def drain() -> None:
        for _ in range(12):
            queued = json.loads(must(["jobs", "--status", "queued", "--json"], "queued"))["jobs"]
            if not queued:
                return
            if any(j["job_kind"] == SCENE_DRAFT for j in queued):
                raise StopRun("unexpected queued draft at chapter checkpoint")
            must(["tick"], "post-chapter-tick")
        raise StopRun("post-chapter drain did not settle in twelve ticks")

    save(RUN / "progress.json", progress)
    try:
        for index in range(1, 4):
            if progress["fatal"]:
                break
            active_dir = RUN / f"book-{index}"
            active_dir.mkdir()
            registry.provider.trace_directory = active_dir / "transport"
            book = {
                "id": f"book-{index}",
                "status": "running",
                "calls": 0,
                "tokens": 0,
                "chapters": 0,
            }
            progress["books"].append(book)
            command_number = 0
            try:
                must(
                    ["concept", "--scenes", "6", "--person", "third", "--out", str(active_dir)],
                    "concept",
                )
                must(
                    [
                        "listing",
                        "--concept",
                        str(active_dir / "concept.json"),
                        "--scenes",
                        "6",
                        "--person",
                        "third",
                        "--no-title-check",
                        "--title-attempts",
                        "1",
                        "--out",
                        str(active_dir),
                    ],
                    "listing",
                )
                must(["architect", "seed"], "seed")
                must(["world", "check"], "seed-check")
                must(["world", "accept"], "seed-accept")
                for chapter in range(1, 4):
                    for _ in range(12):
                        must(["tick"], "tick")
                        code, output = command(
                            ["audit", "--view", "status", "--json"], name="count"
                        )
                        if code not in (0, 1):
                            raise StopRun("cannot read accepted chapter count")
                        count = json.loads(output)["chapters_drafted"]
                        if count > chapter:
                            raise StopRun("chapter boundary overshot")
                        if count == chapter:
                            break
                    else:
                        raise StopRun("chapter did not advance in twelve ticks")
                    drain()
                    must(["architect", "grow"], "grow")
                    must(["world", "check"], "grow-check")
                    must(["world", "accept"], "grow-accept")
                    checkpoint(f"checkpoint-{chapter}")
                book["status"] = "completed"
            except StopRun as error:
                book.update(status="stopped", reason=str(error))
            finally:
                if (active_dir / "serial.db").exists():
                    checkpoint("final")
                save(RUN / "progress.json", progress)
    finally:
        progress.update(
            status="finished",
            finished_at=datetime.now(UTC).isoformat(),
            elapsed_seconds=round(time.monotonic() - started, 1),
        )
        save(RUN / "progress.json", progress)
        CodexCliProvider.complete = original_complete
    print(json.dumps(progress, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    options = parser.parse_args()
    (prepare if options.mode == "prepare" else run)()
