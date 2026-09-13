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
RUN = ROOT / "runs/world-fixed-continuation-20260913"
REVISION = "HEAD"
OWNER = "world-fixed-continuation-20260913: root task;"
MAX_CALLS = 40
MAX_TOKENS = 2_200_000
BOOK_CALLS = 35
BOOK_TOKENS = 1_900_000


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


PARENT = ROOT / "runs/invention-boundaries-20260912/calls/plan-astra-opus-1.json"
PARENT_SHA = "da04af43a6cbcea990c855f5c0b57831304f6b9dbe5951a775330374a66452b8"
CONTROL = ROOT / "runs/world-boundary-fixes-20260913/control-treatment.json"
CONTROL_SHA = "1cdb21f7ea7152e1718d7629ff59d38a443f7438703f20b70c27b142fcc94c8a"


def parent_plan() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise RuntimeError("Fixed Wren treatment changed")
    return load(PARENT)["result"]["parsed"]


def failed_usage(raw: dict) -> int | None:
    """Retain native usage even when the strict transport rejects the result."""
    try:
        events = [json.loads(line) for line in raw.get("stdout", "").splitlines() if line.strip()]
        completed = [row for row in events if row.get("type") == "turn.completed"]
        if len(completed) != 1:
            return None
        usage = completed[0]["usage"]
        counts = [usage["input_tokens"], usage["output_tokens"]]
        if any(type(value) is not int or value < 0 for value in counts):
            return None
        return sum(counts) or None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def prepare() -> None:
    check_lock()
    if (RUN / "manifest.json").exists() or (RUN / "source").exists():
        raise RuntimeError("Runtime already exists; preparation does not overwrite")
    parent_plan()
    if sha(CONTROL) != CONTROL_SHA:
        raise RuntimeError("Fixed opposing treatment changed")
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
    if version != "codex-cli 0.154.0-alpha.6.2" or "ChatGPT" not in auth.stdout + auth.stderr:
        raise RuntimeError("Registered version or subscription authentication differs")
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", REVISION], text=True).strip(),
        "parent_sha256": PARENT_SHA,
        "control_sha256": sha(CONTROL),
        "protected_files": {
            path.relative_to(ROOT).as_posix(): sha(path)
            for path in [
                ROOT / "runs/distinctive-continuation-20260913/book-1/serial.db",
                *sorted((ROOT / "runs/distinctive-continuation-20260913/book-1/library").glob(
                    "*/chapters/Chapter*.txt",
                )),
            ]
        },
        "source_sha256": hashes(RUN / "source"),
        "binary": str(binary),
        "binary_sha256": sha(binary),
        "version": version,
        "experiment_sha256": {
            name: sha(HERE / name)
            for name in ("run.py", "RUNBOOK.md", "audit.py", "capture_audit.py")
        },
        "dependencies": sorted(
            (d.metadata["Name"], d.version) for d in importlib.metadata.distributions()
        ),
        "auth_status": (auth.stdout + auth.stderr).strip(),
        "excluded_worktree_diff": subprocess.run(
            ["git", "diff", "--stat"], cwd=ROOT, capture_output=True, text=True
        ).stdout,
    }
    for prior_name in ("world-boundary-fixes-20260913", "world-runtime-fixes-20260913"):
        prior = ROOT / "runs" / prior_name
        protected = [*prior.glob("book-*/serial.db"),
                     *prior.glob("book-*/library/*/chapters/*.txt")]
        for path in protected:
            manifest["protected_files"][path.relative_to(ROOT).as_posix()] = sha(path)
    save(RUN / "manifest.json", manifest)
    save(HERE / "registration.json", {
        "manifest_sha256": sha(RUN / "manifest.json"),
        "source_revision": manifest["revision"],
        "binary_sha256": manifest["binary_sha256"],
        "parent_path": PARENT.relative_to(ROOT).as_posix(),
        "parent_sha256": PARENT_SHA,
        "max_calls": MAX_CALLS, "max_tokens": MAX_TOKENS,
        "book_calls": BOOK_CALLS, "book_tokens": BOOK_TOKENS,
        "control_sha256": manifest["control_sha256"],
        "assigned_books": 2, "chapters_by_book": [3, 0],
    })
    print("Prepared frozen runtime; no model calls.")


class StopRun(RuntimeError):
    pass


def run() -> None:
    check_lock()
    manifest = load(RUN / "manifest.json")
    registration = load(HERE / "registration.json")
    if sha(RUN / "manifest.json") != registration["manifest_sha256"]:
        raise RuntimeError("Prepared manifest differs from registration")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    if committed != (HERE / "registration.json").read_bytes():
        raise RuntimeError("Registration must be committed before generation")
    if (RUN / "progress.json").exists():
        raise RuntimeError("Run already started; refusing an implicit resume")
    parent_plan()
    if sha(CONTROL) != registration["control_sha256"]:
        raise RuntimeError("Contrast treatment changed")
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
        if any(sha(HERE / name) != digest
               for name, digest in manifest["experiment_sha256"].items()):
            progress["fatal"] = "experiment script drift"
            raise StopRun(progress["fatal"])
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
        if time.monotonic() - started >= 7200:
            progress["fatal"] = "two-hour new-call bound reached"
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
            raw = provider.last_attempt
            row["transport"] = raw
            # Completed rows were already charged before a post-result stop.
            if "result" not in row:
                usage = failed_usage(raw)
                row["failed_native_tokens"] = usage
                if usage is not None:
                    progress["tokens"] += usage
                    book["tokens"] += usage
                else:
                    progress["usage_incomplete"] = True
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
            "world-fixed-continuation-20260913",
            "--chapter-scenes",
            "1",
            "--arc-chapters",
            "6",
            "--target-words",
            "1800",
            "--max-invocations-per-day",
            str(BOOK_CALLS),
            "--max-tokens-per-day",
            str(BOOK_TOKENS),
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
            if code not in (0, 1):
                raise StopRun(f"Cannot read {label} {name}: exit={code}")
            if name == "verify" and code:
                raise StopRun("Attribution verification failed")
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
        for index in range(1, 3):
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
                # A fixed treatment enters the ordinary concept development request once.
                # No invention, candidate selection, dossier feedback or silent repair here.
                from litharness.application.concept import Concept, render_concept_request
                from litharness.application.discovery import Discovery

                source = parent_plan() if index == 1 else load(CONTROL)
                discovery = Discovery.from_invention(source)
                request = render_concept_request("", scenes=6, person="third", discovery=discovery)
                result, _ = registry.complete(request)
                if not isinstance(result.parsed, dict):
                    raise StopRun("Fixed treatment development did not return a concept")
                concept = Concept.from_development(result.parsed, discovery)
                (active_dir / "concept.json").write_text(
                    concept.to_text() + "\n", encoding="utf-8", newline="\n",
                )
                save(active_dir / "concept-parent.json", {
                    "path": (PARENT if index == 1 else CONTROL).relative_to(ROOT).as_posix(),
                    "sha256": PARENT_SHA if index == 1 else sha(CONTROL),
                    "concept_sha256": sha(active_dir / "concept.json"),
                })
                premise = (
                    "Wren arrives in Kesh Gorge, where Loadstitch can open the way into "
                    "the Trestle's history."
                    if index == 1 else
                    "Mara uses her existing Fold and Anchor to search the star orchard "
                    "for a way home."
                )
                must(
                    [
                        "new", f"World boundary probe {index}", "--premise", premise,
                        "--concept",
                        str(active_dir / "concept.json"),
                        "--scenes",
                        "6",
                    ],
                    "new",
                )
                checkpoint("empty")
                must(["architect", "seed"], "seed")
                must(["world", "check"], "seed-check")
                must(["world", "accept"], "seed-accept")
                checkpoint("seeded")
                for chapter in range(1, 4) if index == 1 else ():
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
                expected = 3 if index == 1 else 0
                if book["chapters"] != expected or len(book["chapter_hashes"]) != expected:
                    raise StopRun("Unexpected accepted chapter count")
                book["status"] = "completed"
            except Exception as error:
                book.update(status="stopped", reason=f"{type(error).__name__}: {error}")
                progress["fatal"] = book["reason"]
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
