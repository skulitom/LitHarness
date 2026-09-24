"""The chapter-one lane: a fresh book taken to chapter one for the operator's next read.

**What this is.** A production lane with no research claim, so it has no registration,
amendment or claim record (EPISTEMIC_GOVERNANCE.md, "Claim records"). One *line* fixes a brief;
each *draw* of the line takes a fresh store through the production default path on the Codex
provider in four stages, and each stage stops at a checkpoint for a person: the concept, the
listing, the seeded world before `world accept`, and chapter one. The coordinator reads the
checkpoint against the items in the draw's `items.json` and records pass or fail; a pass opens
the next stage. A chapter pass is published to `book-library/<slug>/` and sent to the operator,
whose read comes back as a harvest recorded by path and hash only.

It keeps what worked in the registered restored-directions runner
(`research/quality-measurement/restored-directions-draw-20260922/run.py`, frozen by hash and
closed, so the parts are copied, never imported or edited): the stage machine and its stop
rules, a runtime built from `git archive` of a named commit, the scrubbed child environment,
binding what each gate reads, the item-per-line gate with PARTIAL counted as FAIL, a publish
that never overwrites a shelf, and per-call transport checks. Every provider call is recorded
by production itself: each step runs with its own `LITHARNESS_CODEX_TRACE_DIR`.

**What it never does.** It writes no model-facing text of its own: every step is a production
CLI verb, built from a fixed argument list with no `--exemplars`, `--rivals`,
`--planning-material` or corpus path, and every path it passes is inside the draw. The items
and the operator's read never reach an argument, the environment or a step's inputs. It reads
no prose for a verdict and never chooses among draws. The register report
(`research/quality-measurement/register_report.py`) runs beside each gate as a subprocess and
decides nothing; its failure blocks nothing.

**Transport.** Every call a stage made is read off its trace before the stage binds its
checkpoint. A call that ran without its isolation controls, a failed call production never
followed with a completed call of the same profile, or a trace nobody can read (a call killed
while its trace was written) stops the stage operationally before anything is bound or read,
so the remedy is a retry. The gate rebuilds the same summary from the traces, files it beside
the gate record with every failed call listed and whether it was retried, and refuses a pass
over any of the three or over a stage with no traced call at all.

**Retries and redraws.** A stage that stopped for an operational cause (an exit-2 fault, a
killed runner, failed ticks, a binding failure, a failed transport check) may be retried twice
with a failure note whose SHA-256 is recorded before dispatch. The runner and every step child
the stage recorded (the process it started and the interpreter that process runs, which on
Windows are two and outlive a stopped runner) must be gone, by the OS or by a
`--verified-dead-pid` for each. The store is restored from the previous checkpoint's backup and
checked before anything is recorded or moved; the failed attempt is kept under `attempts/`, and
ceilings count every attempt, an unreadable trace as a call of unknown usage. A content stop or a
gate fail ends the draw. A new draw needs the previous draw ended, at least one located cause
(`<checkpoint>: <file>[:line][ locator]: <what the read found>`, the file one that exists in the
draw or the repository), and either a new commit touching `src/` or `migrations/` or a different
accepted writer. Every draw of a brief is counted, across lines and before the lane: one brief
has one line, a brief a registered runner already drew (`runs/<arm>/draw-<n>/brief.txt`) starts
its line as a redraw of the latest of those, and the published `DRAW.json` says "draw k of n"
over all of them (BRIEF.md §6, question 6). No brief comes from `plan/` or has the bytes of a
file there or of any read a draw recorded.

**One iteration**, from the repository root (`--no-sync` keeps uv from re-syncing the shared
environment each draw's runtime imports its dependencies from):

    # 0. the box: check the process list, then take the lock with this lane's prefix
    mkdir runs/box.lock && echo "chapter-one: <who>, <line> draw N" > runs/box.lock/holder
    # 1. a line fixes its brief; draw 1 builds the runtime (no provider call). A brief drawn
    #    before the lane takes causes and a change as a redraw does. The next draw is this one:
    #    the closed restored-directions draws 1 and 2 (rowntree) make it draw 3 of 3.
    uv run --no-sync python tools/chapter_one.py start --line read-21 \\
        --brief-file runs/restored-directions-draw-20260922/draw-2/brief.txt --writer marsh \\
        --cause "listing: plan/reader-read-20.md items 1, 4: a list of facts, not a hook" \\
        --cause "chapter: plan/reader-read-20.md items 2, 3: a rent line; 'surviving tread'"
    # 2. each stage stops at its checkpoint; write GATE-<checkpoint>.md in the draw folder with
    #    one `<id>: PASS|FAIL|PARTIAL <location>` line per item, then record it
    uv run --no-sync python tools/chapter_one.py concept --line read-21
    uv run --no-sync python tools/chapter_one.py gate concept pass --line read-21 \\
        --read runs/chapter-one/read-21/draw-1/GATE-concept.md --by coordinator
    uv run --no-sync python tools/chapter_one.py listing --line read-21   # then gate listing
    uv run --no-sync python tools/chapter_one.py seed --line read-21      # then gate world
    uv run --no-sync python tools/chapter_one.py chapter --line read-21   # then gate chapter
    # 3. after a chapter pass
    uv run --no-sync python tools/chapter_one.py publish --line read-21
    uv run --no-sync python tools/chapter_one.py sent --line read-21 --how "<where>"
    uv run --no-sync python tools/chapter_one.py read --line read-21 --harvest <read file>
    # a stage stopped operationally: write a failure note, then retry; a refusal names each PID
    # the OS still reports and wants a --verified-dead-pid for it once `taskkill /PID <pid> /T /F`
    # or the process list shows it gone
    uv run --no-sync python tools/chapter_one.py retry <stage> --line read-21 \\
        --failure <note> [--verified-dead-pid <pid> ...]
    # the next draw, after a gate fail, a stop, or a recorded read
    uv run --no-sync python tools/chapter_one.py redraw --line read-21 \\
        --cause "<checkpoint>: <file>[:line][ locator]: <what the read found>" \\
        --fix <40-hex commit> [--writer <other>]
    uv run --no-sync python tools/chapter_one.py status --line read-21

Release the lock after each command that needs it (`start`, `redraw`, a stage, `retry`), or
hold it across a checkpoint when nothing else is waiting. Exit 0 answered, 1 a stage stopped
and needs a person, 2 refused. `_step`, `_bind` and `_digest` are the child modes the draw's
runtime runs; none but `_step` reaches a provider.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
import time
import venv
import zipfile
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

TOOL = Path(__file__).resolve()
REPO = TOOL.parents[1]
RUNS = REPO / "runs" / "chapter-one"
#: Where the registered draw runners kept each draw's brief (`runs/<arm>/draw-<n>/brief.txt`):
#: a brief found there was drawn before the lane, and those draws count.
EARLIER_DRAWS = REPO / "runs"
#: The operator's reads live here (`plan/reader-read-N.md`); no brief is taken from it.
PLAN = REPO / "plan"
LIBRARY = REPO / "book-library"
ROSTER = REPO / "runs" / "roster" / "roster.db"
#: The coordinator's gate items, snapshotted into each draw at prepare. Coordinator-facing:
#: never an argument, an environment value or a step input.
ITEMS = TOOL.with_name("chapter_one_items.json")
ITEMS_SCHEMA = "chapter-one.items.v1"
#: Run as a subprocess beside each gate and never imported: research is not a production
#: import (AGENTS.md).
REGISTER_REPORT = REPO / "research" / "quality-measurement" / "register_report.py"
LOCK_HOLDER = REPO / "runs" / "box.lock" / "holder"
LOCK_PREFIX = "chapter-one:"
HOLDER = "chapter-one"
#: v1 runs on Codex only: the Claude transport writes no per-call trace yet.
PROVIDER = "codex"
SEED_BITS = 2048
SHELF_MARKER = ".book.json"

DEFAULT_LAYOUT: dict[str, Any] = {
    "person": "third",
    "scenes": 24,
    "chapter_scenes": 4,
    "arc_chapters": 6,
}
#: Per draw, every attempt counted. The registered draw 2 on the same layout spent 33 calls.
DEFAULT_LIMITS: dict[str, int] = {"calls": 60, "tokens": 2_000_000, "seconds": 7200}
MAX_TICKS = 24
MAX_FAILED_TICKS = 3
MAX_RETRIES = 2

STAGES: tuple[str, ...] = ("concept", "listing", "seed", "chapter")
CHECKPOINT_OF = {"concept": "concept", "listing": "listing", "seed": "world", "chapter": "chapter"}
STAGE_OF = {checkpoint: stage for stage, checkpoint in CHECKPOINT_OF.items()}
CHECKPOINTS: tuple[str, ...] = tuple(CHECKPOINT_OF.values())
FIXED_STEPS: dict[str, tuple[str, ...]] = {
    "concept": ("concept",),
    "listing": ("listing",),
    "seed": ("architect-seed", "world-check"),
}
STEP_ARGV: dict[tuple[str, str], list[str]] = {
    ("seed", "architect-seed"): ["architect", "seed"],
    ("seed", "world-check"): ["world", "check"],
    ("chapter", "world-accept"): ["world", "accept"],
    ("chapter", "tick"): ["tick"],
}
#: What each stage leaves in the draw, moved whole into `attempts/` by a retry.
STAGE_OUTPUTS: dict[str, tuple[str, ...]] = {
    "concept": ("concept",),
    "listing": ("listing",),
    "seed": ("views/world-show.json", "views/world-ladders.json"),
    "chapter": (
        "chapter-one.md",
        "library",
        "views/library.json",
        "views/status.json",
        "views/verify.json",
        "views/plans.json",
        "views/why-*.json",
    ),
}
GATE_RESULTS = ("pass", "fail")
ENDED = ("failed", "stopped")
# A production lane may draw again with nothing changed when a gate failed on something the
# model supplied with no source in the recorded requests (stage-0 §266): the gate is the
# filter, and every draw is still counted. A run of them is capped, so a failure that keeps
# returning goes back to a person rather than to more spend.
MAX_RESAMPLES = 3
#: One verdict line per item: the id at the start of a line (a list bullet allowed), a colon,
#: then PASS, FAIL or PARTIAL. Ids are a capital and a number or a capital, a hyphen and a word.
VERDICT_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?(?P<item>[A-Z](?:\d+|-[a-z]+)):[ \t]*(?P<verdict>PASS|FAIL|PARTIAL)\b",
    re.MULTILINE,
)
#: The mark of a stage stopped by its transport check, before anything was bound or read.
TRANSPORT_STOP = "(transport check)"
#: Stop reasons a retry may follow; anything else (a ceiling, a refused world, a parked unit,
#: an idle tick, a scene past chapter one) ends the draw, and the remedy is a redraw.
OPERATIONAL_STOPS = (
    "(operational fault)",
    "scheduler failure",
    "could not be bound",
    "consecutive failed ticks",
    "without a step record",
    "runner process ended",
    TRANSPORT_STOP,
)
#: A cause's first word: one of the four checkpoints (a stage name maps to its checkpoint), or
#: `operational` for a draw that ended on a stop no retry could clear.
CAUSE = re.compile(r"\s*(?P<checkpoint>[a-z]+)\s*:\s+(?P<where>\S.*?)\s*:\s+(?P<what>\S.*)", re.S)
#: The only flags a step or view may carry; the paths among them must lie inside the draw.
PATH_FLAGS = frozenset(
    {"--database", "--roster-database", "--library", "--brief-file", "--concept", "--out"}
)
ALLOWED_FLAGS = PATH_FLAGS | {
    "--writer",
    "--holder",
    "--chapter-scenes",
    "--arc-chapters",
    "--max-invocations-per-day",
    "--max-tokens-per-day",
    "--seed",
    "--scenes",
    "--person",
    "--no-title-check",
    "--json",
    "--scene",
}
SCRUBBED_PREFIXES = ("LITHARNESS_", "ANTHROPIC_", "OPENAI_")
SCRUBBED_NAMES = frozenset({"PYTHONPATH", "PYTHONHOME", "PYTEST_CURRENT_TEST", "VIRTUAL_ENV"})
ISOLATION_FLAGS = ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check")


class Refusal(RuntimeError):
    """A lane rule refused the action. Nothing was dispatched."""


# ------------------------------------------------------------------------------ utilities


def now() -> str:
    return datetime.now(UTC).isoformat()


def elapsed(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def sha(path: Path | str) -> str:
    digest_ = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest_.update(block)
    return digest_.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path: Path | str, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    # On Windows a reader holding the file open (a `status` beside a running stage) refuses the
    # rename for a moment; a runner that raised here would stop its stage for nothing.
    for wait in (0.05,) * 40:
        try:
            temporary.replace(path)
            return
        except PermissionError:
            time.sleep(wait)
    temporary.replace(path)


def write_new(path: Path | str, value: Any) -> None:
    """Exclusive create: a record is never overwritten."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def within(path: Path | str, root: Path | str) -> bool:
    """Whether `path` is `root` or under it, compared case-insensitively where the OS is."""
    inner = os.path.normcase(Path(path).resolve())
    outer = os.path.normcase(Path(root).resolve())
    try:
        return os.path.commonpath([inner, outer]) == outer
    except ValueError:  # different drives
        return False


if sys.platform == "win32":

    def pid_running(pid: int) -> bool | None:
        """Whether the OS reports a process with this PID still running; None when it cannot
        tell (a process of another user it may not open)."""
        import ctypes
        from ctypes import wintypes

        if pid <= 0:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            # ERROR_INVALID_PARAMETER: no process has this PID. Anything else (access denied)
            # means one does, and whose it is is not known here.
            return False if ctypes.get_last_error() == 87 else None
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            return bool(code.value == 259)  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

else:

    def pid_running(pid: int) -> bool | None:
        """Whether the OS reports a process with this PID still running."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


def parse_key(key: str) -> tuple[str, str, int]:
    stage, rest = key.split("-", 1)
    name, iteration = rest.rsplit("-", 1)
    return stage, name, int(iteration)


def line_dir(line: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", line):
        raise Refusal(f"{line!r} is not a line name: lowercase letters, digits and hyphens")
    return RUNS / line


def draw_dir(line: str, n: int) -> Path:
    return line_dir(line) / f"draw-{n}"


def draws(line: str) -> list[int]:
    """Prepared draws: a folder counts once prepare wrote its progress record."""
    root = line_dir(line)
    if not root.is_dir():
        return []
    found = (
        re.fullmatch(r"draw-(\d+)", path.name)
        for path in root.iterdir()
        if (path / "progress.json").is_file()
    )
    return sorted(int(match.group(1)) for match in found if match)


def current(line: str) -> Path:
    found = draws(line)
    if not found:
        raise Refusal(f"line {line} has no draw: run `start` first")
    return draw_dir(line, found[-1])


def progress(d: Path) -> dict[str, Any]:
    state: dict[str, Any] = read(d / "progress.json")
    return state


def save(d: Path, state: dict[str, Any]) -> None:
    write(d / "progress.json", state)


def ledger(d: Path, event: str, **fields: Any) -> None:
    """Append one event to the line's ledger; nothing in it is ever rewritten."""
    entry = {"event": event, "draw": d.name, "at": now(), **fields}
    with (d.parent / "ledger.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def checkpoint_path(d: Path, checkpoint: str, kind: str = "") -> Path:
    return d / "checkpoints" / f"{checkpoint}{'.' + kind if kind else ''}.json"


def runtime_python(d: Path) -> Path:
    runtime = d / "runtime"
    return runtime / "Scripts" / "python.exe" if os.name == "nt" else runtime / "bin" / "python"


def site_packages(runtime: Path) -> Path:
    if os.name == "nt":
        return runtime / "Lib" / "site-packages"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return runtime / "lib" / version / "site-packages"


# ------------------------------------------------------------------ the box, env and git


def lock() -> None:
    try:
        holder = LOCK_HOLDER.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise Refusal("runs/box.lock is not held; take it (see this file's docstring)") from error
    if not holder.startswith(LOCK_PREFIX):
        raise Refusal(f"runs/box.lock is held by someone else, not {LOCK_PREFIX}")


def refuse_live_environment() -> None:
    if os.environ.get("LITHARNESS_ENV", "").strip().lower() == "test" or os.environ.get(
        "LITHARNESS_FAKE_PAD_CHARS"
    ):
        raise Refusal("the lane never runs in test mode or on the padded fake provider")
    chosen = os.environ.get("LITHARNESS_PROVIDER", "").strip().lower()
    if chosen and chosen != PROVIDER:
        raise Refusal(
            f"LITHARNESS_PROVIDER={chosen}: v1 runs on codex only, the provider whose every "
            "call production traces"
        )


def git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=False)


def git_out(*args: str) -> str:
    done = git(*args)
    if done.returncode:
        message = done.stderr.decode("utf-8", errors="replace").strip()
        raise Refusal(f"git {' '.join(args)} failed: {message}")
    return done.stdout.decode("utf-8").strip()


def is_ancestor(older: str, newer: str) -> bool:
    done = git("merge-base", "--is-ancestor", older, newer)
    if done.returncode not in (0, 1):
        raise Refusal(f"git cannot relate {older} to {newer}")
    return done.returncode == 0


def fix_problem(commit: str, previous_revision: str | None) -> str | None:
    """Why `commit` cannot license a redraw after a draw at `previous_revision`, or None. A
    declared earlier draw whose revision is not on disk checks only the commit itself."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        return f"{commit!r} is not a full commit id"
    if not is_ancestor(commit, "HEAD"):
        return f"{commit} is not on HEAD"
    if previous_revision is not None and is_ancestor(commit, previous_revision):
        return f"{commit} was already in the previous draw; a redraw follows a new fix"
    paths = git_out("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).split()
    if not any(path.startswith(("src/", "migrations/")) for path in paths):
        return f"{commit} changes no production path (src/ or migrations/)"
    return None


def roster_writer(path: Path, name: str) -> dict[str, str]:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
        rows = connection.execute(
            "SELECT writer_id, dossier FROM roster_writers WHERE name = ? AND status = 'accepted'",
            (name,),
        ).fetchall()
    if len(rows) != 1:
        raise Refusal(f"{name} is not exactly one accepted writer in {path}")
    return {"writer_id": str(rows[0][0]), "dossier_sha256": sha_text(str(rows[0][1]))}


def copy_roster(destination: Path) -> Path:
    """The installation roster copied through a read-only connection; the draw reads the copy."""
    uri = f"{ROSTER.resolve().as_uri()}?mode=ro"
    with (
        contextlib.closing(sqlite3.connect(uri, uri=True)) as source,
        contextlib.closing(sqlite3.connect(destination)) as target,
    ):
        source.backup(target)
    return destination


# Production refuses these before any call (providers/codex_cli.py), and `shutil.which` finds
# npm's `codex.cmd` first on this host, so the lane resolves the native executable the wrapper
# launches and never freezes a wrapper into a draw.
WRAPPER_SUFFIXES = frozenset({".bat", ".cmd", ".ps1"})
NPM_NATIVE = Path(
    "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor"
    "/x86_64-pc-windows-msvc/bin/codex.exe"
)


def resolve_binary(explicit: str | None) -> Path:
    candidate = (
        explicit or os.environ.get("LITHARNESS_CODEX_BINARY", "").strip() or shutil.which("codex")
    )
    if not candidate or not Path(candidate).is_file():
        raise Refusal("no Codex binary: pass --codex-binary PATH")
    path = Path(candidate).resolve()
    if path.suffix.lower() in WRAPPER_SUFFIXES:
        native = path.parent / NPM_NATIVE
        if not native.is_file():
            raise Refusal(
                f"{path} is a shell wrapper, which production refuses: pass --codex-binary "
                "with the native codex.exe"
            )
        path = native.resolve()
    return path


def binary_record(path: Path) -> dict[str, Any]:
    """The binary by hash and `codex --version`, which prints a version and makes no call."""
    done = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, timeout=60, check=True
    )
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": sha(path),
        "version": done.stdout.strip(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def installed_distributions(purelib: Path | str) -> list[str]:
    return sorted(
        f"{dist.name}=={dist.version}"
        for dist in importlib_metadata.distributions(path=[str(purelib)])
    )


def build_runtime(d: Path, revision: str) -> dict[str, Any]:
    """The archived source of `revision` and a runtime that imports it, never the checkout.

    Third-party dependencies come from the shared site-packages; every installed version is
    recorded so a stage can refuse a changed environment.
    """
    archive = d / "source.zip"
    done = git(
        "archive",
        "--format=zip",
        f"--output={archive}",
        revision,
        "src",
        "migrations",
        "pyproject.toml",
        "uv.lock",
    )
    if done.returncode:
        raise Refusal(f"git archive failed: {done.stderr.decode('utf-8', errors='replace')}")
    source = d / "source"
    with zipfile.ZipFile(archive) as packed:
        packed.extractall(source)
    runtime = d / "runtime"
    venv.EnvBuilder(with_pip=False).create(runtime)
    # A plain path entry does not process the shared directory's editable-install .pth, so
    # the archived source is what imports, here and in every world-tool child.
    purelib = Path(sysconfig.get_path("purelib"))
    pth = site_packages(runtime) / "chapter-one-source.pth"
    pth.write_text(f"{source / 'src'}\n{purelib}\n", encoding="utf-8")
    probe = subprocess.run(
        [
            str(runtime_python(d)),
            "-c",
            "import json, litharness\n"
            "from litharness.providers.codex_cli import CodexCliProvider as C\n"
            "p = C()\n"
            "print(json.dumps({'source': litharness.__file__, 'model': p.model, "
            "'effort': p.reasoning_effort}))",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env=environment(d),
    )
    origin: dict[str, Any] = json.loads(probe.stdout)
    if not Path(origin["source"]).resolve().is_relative_to(source.resolve()):
        raise Refusal("the draw's runtime imported the live checkout")
    origin |= {"purelib": str(purelib), "distributions": installed_distributions(purelib)}
    write(d / "runtime.json", origin)
    return origin


def environment(d: Path, key: str | None = None) -> dict[str, str]:
    """The child's environment: no inherited LitHarness, Anthropic or OpenAI setting.

    A step's `key` gives it its own transport folder, so every provider call production makes
    for that step is traced there.
    """
    settings = read(d / "settings.json")
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(SCRUBBED_PREFIXES) and name.upper() not in SCRUBBED_NAMES
    }
    env.update(
        LITHARNESS_PROVIDER=PROVIDER,
        LITHARNESS_CODEX_BINARY=str(settings["binary"]["path"]),
        LITHARNESS_DATABASE=str(d / "book.db"),
        LITHARNESS_ROSTER_DATABASE=str(d / "roster.db"),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
    )
    if key is not None:
        env["LITHARNESS_CODEX_TRACE_DIR"] = str(d / "transport" / key)
    return env


# ------------------------------------------------------------------------ the CLI commands


def base_args(d: Path, settings: dict[str, Any]) -> list[str]:
    layout, limits = settings["layout"], settings["limits"]
    return [
        "--database",
        str(d / "book.db"),
        "--roster-database",
        str(d / "roster.db"),
        "--writer",
        str(settings["writer"]),
        "--holder",
        HOLDER,
        "--chapter-scenes",
        str(layout["chapter_scenes"]),
        "--arc-chapters",
        str(layout["arc_chapters"]),
        "--library",
        str(d / "library"),
        "--max-invocations-per-day",
        str(limits["calls"]),
        "--max-tokens-per-day",
        str(limits["tokens"]),
    ]


def stage_argv(d: Path, settings: dict[str, Any], stage: str, name: str) -> list[str]:
    layout = settings["layout"]
    if (stage, name) == ("concept", "concept"):
        return [
            "concept",
            "--brief-file",
            str(d / "brief.txt"),
            "--seed",
            str(read(d / "seed.json")["label"]),
            "--scenes",
            str(layout["scenes"]),
            "--person",
            str(layout["person"]),
            "--out",
            str(d / "concept"),
        ]
    if (stage, name) == ("listing", "listing"):
        # No title lookup: a web search over an unpublished working title.
        return [
            "listing",
            "--concept",
            str(d / "concept" / "concept.json"),
            "--person",
            str(layout["person"]),
            "--scenes",
            str(layout["scenes"]),
            "--no-title-check",
            "--out",
            str(d / "listing"),
        ]
    if (stage, name) in STEP_ARGV:
        return list(STEP_ARGV[(stage, name)])
    raise ValueError(f"no such step {stage}/{name}")


def argv_refusal(d: Path, argv: list[str]) -> str | None:
    """Why an argument list may not ride a step or view, or None: an unlisted flag, a flag in
    `--flag=value` form, or a path outside the draw."""
    for index, token in enumerate(argv):
        if not token.startswith("-"):
            continue
        if "=" in token or token not in ALLOWED_FLAGS:
            return f"{token} is not an argument this lane passes"
        if token in PATH_FLAGS:
            value = argv[index + 1] if index + 1 < len(argv) else ""
            if not value or not within(value, d):
                return f"{token} {value!r} lies outside the draw"
    return None


# --------------------------------------------------------------------- start and redraw


def load_items(path: Path) -> dict[str, Any]:
    items: dict[str, Any] = read(path)
    if items.get("schema") != ITEMS_SCHEMA:
        raise Refusal(f"{path} is not {ITEMS_SCHEMA}")
    lists = items.get("checkpoints") or {}
    if set(lists) != set(CHECKPOINTS):
        raise Refusal(f"{path} must list items for exactly {list(CHECKPOINTS)}")
    ids = [entry["id"] for entries in lists.values() for entry in entries]
    if len(ids) != len(set(ids)) or not all(VERDICT_LINE.match(f"{i}: PASS") for i in ids):
        raise Refusal(f"{path} repeats an item id or has one no verdict line can name")
    return items


def item_ids(d: Path, checkpoint: str) -> list[str]:
    return [str(entry["id"]) for entry in load_items(d / "items.json")["checkpoints"][checkpoint]]


def prepare(line: str, n: int, *, writer: str, binary: str | None, extra: dict[str, Any]) -> Path:
    """Freeze draw `n` of `line`: source, runtime, roster copy, brief, seed, items, binary."""
    root = line_dir(line)
    line_record = read(root / "line.json")
    revision = git_out("rev-parse", "HEAD")
    dirty = git_out(
        "status", "--porcelain", "--", "src", "migrations", "pyproject.toml", "uv.lock"
    ).splitlines()
    if dirty:
        raise Refusal(
            "uncommitted production changes would not be in the draw, which runs the committed "
            f"revision: {dirty}; commit them or set them aside first"
        )
    load_items(ITEMS)
    binary_path = resolve_binary(binary)
    d = draw_dir(line, n)
    if d.exists():
        raise Refusal(
            f"{d} exists without a finished prepare; nothing was bought, so move it aside "
            "(it stays the record of that attempt) and try again"
        )
    d.mkdir(parents=True)
    row = roster_writer(copy_roster(d / "roster.db"), writer)
    shutil.copy2(root / "brief.txt", d / "brief.txt")
    if sha(d / "brief.txt") != line_record["brief_sha256"]:
        raise Refusal("the draw's brief is not the line's brief")
    shutil.copy2(ITEMS, d / "items.json")
    write(d / "seed.json", {"label": str(secrets.randbits(SEED_BITS))})
    # The causes say what a read found, so they stay out of `settings.json`, which every child
    # reads; the draw keeps them beside it, by hash in the settings.
    causes = extra.pop("causes", None)
    if causes is not None:
        write_new(d / "causes.json", causes)
        extra["causes_sha256"] = sha(d / "causes.json")
    settings = {
        "line": line,
        "draw": n,
        "revision": revision,
        "on_remote": bool(git_out("branch", "-r", "--contains", "HEAD")),
        "writer": writer,
        **row,
        "binary": binary_record(binary_path),
        "provider": PROVIDER,
        "layout": line_record["layout"],
        "limits": line_record["limits"],
        "brief_sha256": line_record["brief_sha256"],
        "items_sha256": sha(d / "items.json"),
        "tool_sha256": sha(TOOL),
        "prepared_at": now(),
        **extra,
    }
    write(d / "settings.json", settings)
    runtime = build_runtime(d, revision)
    save(
        d,
        {
            "draw": n,
            "status": "prepared",
            "stages": {},
            "gates": {},
            "stop": None,
            "retries": {},
            "attempts": [],
        },
    )
    ledger(
        d,
        "prepared",
        revision=revision,
        writer=writer,
        model=runtime.get("model"),
        effort=runtime.get("effort"),
        causes=causes,
        **extra,
    )
    print(f"Prepared {line} draw {n} at {revision[:12]} ({writer}); no provider call.")
    if not settings["on_remote"]:
        print("  note: HEAD is on no remote branch; push it so the draw's revision is backed up.")
    return d


def located_cause(cause: str, roots: Sequence[Path]) -> dict[str, str]:
    """`cause` as a located cause's fields, or a Refusal saying why it is not one.

    A located cause is `<checkpoint>: <file>[:line][ locator]: <what the read found>`: the
    checkpoint is one of the four (a stage name maps to its own) or `operational`; the file
    exists, under one of `roots` (the draw the cause was found in, its line, the repository) or
    as an absolute path, with an optional `:line` and any further locator (`items 1, 4`); and
    `what` says what the read found there. The frozen runner asked the same of an amendment's
    `located_cause` (a checkpoint and a `where`)."""
    shape = (
        "a located cause reads `<checkpoint>: <file>[:line][ locator]: <what the read found>`, "
        f"the checkpoint one of {[*CHECKPOINTS, 'operational']}"
    )
    match = CAUSE.fullmatch(cause)
    if not match:
        raise Refusal(f"{shape}; {cause!r} is not one")
    checkpoint = CHECKPOINT_OF.get(match["checkpoint"], match["checkpoint"])
    if checkpoint not in (*CHECKPOINTS, "operational"):
        raise Refusal(f"{shape}; {match['checkpoint']!r} is no checkpoint")
    token, _, locator = match["where"].partition(" ")
    name = re.sub(r"(?::\d+(?:-\d+)?)+$", "", token)
    candidate = Path(name)
    places = [candidate] if candidate.is_absolute() else [root / candidate for root in roots]
    if not name or not any(place.is_file() for place in places):
        raise Refusal(
            f"{shape}; {name!r} is no file in {[str(root) for root in roots]} or on its own path"
        )
    return {
        "checkpoint": checkpoint,
        "file": name,
        "where": match["where"],
        "locator": locator.strip(),
        "what": match["what"].strip(),
    }


def located_causes(causes: Sequence[str], roots: Sequence[Path]) -> list[dict[str, str]]:
    if not causes:
        raise Refusal("a redraw names at least one located cause (--cause)")
    return [located_cause(cause, roots) for cause in causes]


def brief_problem(path: Path, brief: bytes) -> str | None:
    """Why a file may not be a line's brief, or None. The brief is the one text of the lane's
    that reaches a model, so it never comes from `plan/`, where the operator's reads are kept,
    never has the bytes of a file there, and never has the bytes of a read or a gate read any
    draw recorded (§97.1, §148)."""
    if within(path, PLAN):
        return f"{path} is under plan/, where the operator's reads are kept; a read is no brief"
    brief_sha = hashlib.sha256(brief).hexdigest()
    same_size = (
        kept for kept in PLAN.rglob("*") if kept.is_file() and kept.stat().st_size == len(brief)
    )
    for kept in same_size:
        if sha(kept) == brief_sha:
            return f"{path} has the bytes of {kept}; nothing kept under plan/ is a brief"
    for recorded in sorted(RUNS.glob("*/draw-*/progress.json")):
        state = read(recorded)
        reads = [state.get("read") or {}, *state.get("gates", {}).values()]
        if brief_sha in {entry.get("sha256") or entry.get("read_sha256") for entry in reads}:
            return f"{path} has the bytes of a read {recorded.parent} recorded; a read is no brief"
    return None


def lines_with_brief(brief_sha: str) -> list[str]:
    return sorted(
        path.parent.name
        for path in RUNS.glob("*/line.json")
        if read(path).get("brief_sha256") == brief_sha
    )


def earlier_draws(brief_sha: str) -> list[Path]:
    """Draw folders outside the lane whose brief has these bytes, in draw order."""
    found = [
        path.parent
        for path in EARLIER_DRAWS.glob("*/draw-*/brief.txt")
        if re.fullmatch(r"draw-\d+", path.parent.name)
        and not within(path, RUNS)
        and sha(path) == brief_sha
    ]

    def order(folder: Path) -> tuple[str, int]:
        return str(folder.parent), int(folder.name.removeprefix("draw-"))

    return sorted(found, key=order)


def earlier_record(
    brief_sha: str,
    writer: str,
    *,
    causes: Sequence[str],
    fixes: Sequence[str],
    prior_draws: int,
    prior_source: Path | None,
) -> dict[str, Any]:
    """The draws of this brief made before its line, which the line's count starts after.

    Found: a registered runner's draws of the same bytes. Declared: `prior_draws` the scan
    cannot see, with `prior_source` saying where they are recorded. A line's first draw after
    any of them is a redraw, held to the redraw rule against the latest one found."""
    found = earlier_draws(brief_sha)
    if prior_draws < 0:
        raise Refusal("--prior-draws counts draws; it is never negative")
    if prior_draws and (prior_source is None or not Path(prior_source).exists()):
        raise Refusal("--prior-draws needs --prior-source naming where those draws are recorded")
    record: dict[str, Any] = {
        "draws": len(found) + prior_draws,
        "found": [str(folder) for folder in found],
        "declared": prior_draws,
        "source": str(Path(prior_source).resolve()) if prior_source else None,
    }
    if not record["draws"]:
        if causes or fixes:
            raise Refusal("a brief nobody drew before has no redraw cause or fix to record")
        return record
    roots = [found[-1], REPO] if found else [REPO]
    try:
        located = located_causes(causes, roots)
    except Refusal as error:
        raise Refusal(
            f"this brief was drawn {record['draws']} times before ({record['found']}, "
            f"{prior_draws} declared), so this line's first draw is a redraw: {error}"
        ) from error
    after: dict[str, Any] | None = None
    if found:
        settings_path = found[-1] / "settings.json"
        before = read(settings_path) if settings_path.is_file() else {}
        if not before.get("revision") or not before.get("writer"):
            raise Refusal(f"{settings_path} records no revision and writer to redraw against")
        after = {
            "folder": str(found[-1]),
            "revision": str(before["revision"]),
            "writer": str(before["writer"]),
        }
    problems = [p for c in fixes if (p := fix_problem(c, after["revision"] if after else None))]
    if problems:
        raise Refusal("; ".join(problems))
    if after and not fixes and writer == after["writer"]:
        raise Refusal(
            "the same revision and writer draw the same distribution again: a redraw needs a "
            "new commit touching src/ or migrations/ (--fix) or a different accepted writer"
        )
    if after is None and not fixes:
        raise Refusal(
            "the declared earlier draws leave no revision or writer here to compare a writer "
            "with, so a redraw after them names a new commit touching src/ or migrations/ (--fix)"
        )
    return record | {"after": after, "causes": located, "fixes": list(fixes)}


def drawn_before(line: str) -> int:
    """How many draws of this line's brief came before its draw 1."""
    earlier = read(line_dir(line) / "line.json").get("earlier") or {}
    return int(earlier.get("draws") or 0)


def start(
    line: str,
    brief_file: Path,
    writer: str,
    *,
    binary: str | None = None,
    layout: dict[str, Any] | None = None,
    limits: dict[str, int] | None = None,
    causes: Sequence[str] = (),
    fixes: Sequence[str] = (),
    prior_draws: int = 0,
    prior_source: Path | None = None,
) -> Path:
    refuse_live_environment()
    lock()
    root = line_dir(line)
    if draws(line):
        raise Refusal(f"line {line} exists; its next draw is `redraw`, and a new brief a new line")
    brief = Path(brief_file).read_bytes()
    if not brief.strip():
        raise Refusal("the brief is empty")
    brief_sha = hashlib.sha256(brief).hexdigest()
    problem = brief_problem(Path(brief_file), brief)
    if problem:
        raise Refusal(problem)
    # A second line on one brief would start its count again at draw 1 and skip the redraw rule.
    others = [name for name in lines_with_brief(brief_sha) if name != line]
    if others:
        raise Refusal(
            f"line {others[0]} already draws this brief; its next draw is "
            f"`redraw --line {others[0]}`"
        )
    earlier = earlier_record(
        brief_sha,
        writer,
        causes=causes,
        fixes=fixes,
        prior_draws=prior_draws,
        prior_source=prior_source,
    )
    fixed = {
        "brief_sha256": brief_sha,
        "provider": PROVIDER,
        "layout": layout or dict(DEFAULT_LAYOUT),
        "limits": limits or dict(DEFAULT_LIMITS),
        "earlier": earlier,
    }
    if (root / "line.json").exists():
        # A first prepare that was refused bought nothing; the line starts again only as it was.
        recorded = read(root / "line.json")
        if any(recorded.get(key) != value for key, value in fixed.items()):
            raise Refusal(f"line {line} was opened with another brief, layout or ceilings")
    else:
        root.mkdir(parents=True, exist_ok=True)
        (root / "brief.txt").write_bytes(brief)
        record = {"line": line, "brief_from": str(Path(brief_file).resolve()), **fixed}
        write_new(root / "line.json", record | {"created_at": now()})
    extra: dict[str, Any] = {}
    if earlier["draws"]:
        after = earlier["after"] or {}
        extra = {
            "after_earlier": earlier["draws"],
            "causes": earlier["causes"],
            "fixes": list(fixes),
            "writer_changed_from": after.get("writer") if after.get("writer") != writer else None,
        }
    return prepare(line, 1, writer=writer, binary=binary, extra=extra)


def redraw(
    line: str,
    causes: Sequence[str],
    fixes: list[str],
    writer: str | None,
    binary: str | None = None,
    resample: str | None = None,
) -> Path:
    """The next draw: the previous one ended, each cause is located, and something changed.

    `resample` is the one exception to "something changed": a gate failed on text the model
    supplied that no recorded request contains, which a change to our text cannot reach. It says
    why, needs the previous draw failed at a gate (not stopped), and at most `MAX_RESAMPLES`
    draws in a row may be resamples.
    """
    refuse_live_environment()
    lock()
    found = draws(line)
    if not found:
        raise Refusal(f"line {line} has no draw: run `start` first")
    previous = draw_dir(line, found[-1])
    state, settings = progress(previous), read(previous / "settings.json")
    ended = state["status"] in ENDED or (state["status"] == "passed" and state.get("read"))
    if not ended:
        raise Refusal(
            f"draw {found[-1]} has not ended ({state['status']}): a gate fail, a stop, or a "
            "published chapter whose read is recorded ends it"
        )
    located = located_causes(causes, [previous, previous.parent, REPO])
    problems = [p for commit in fixes if (p := fix_problem(commit, settings["revision"]))]
    if problems:
        raise Refusal("; ".join(problems))
    chosen = writer or str(settings["writer"])
    reason = (resample or "").strip()
    if resample is not None and (fixes or chosen != settings["writer"]):
        raise Refusal("a resample changes nothing: drop --fix and --writer, or drop --resample")
    if resample is not None:
        if not reason:
            raise Refusal("a resample says what the model supplied that no request contains")
        if state["status"] != "failed" or not any(
            gate.get("result") == "fail" for gate in state["gates"].values()
        ):
            raise Refusal("only a gate fail is resampled; a stop is retried or redrawn")
        run = 0
        for k in reversed(found):
            if not read(draw_dir(line, k) / "settings.json").get("resample"):
                break
            run += 1
        if run >= MAX_RESAMPLES:
            raise Refusal(
                f"{run} resamples in a row: a failure that keeps returning goes to a person, "
                "with a change to our text (--fix) or a different writer"
            )
    elif not fixes and chosen == settings["writer"]:
        raise Refusal(
            "the same revision and writer draw the same distribution again: a redraw needs a "
            "new commit touching src/ or migrations/ (--fix), a different accepted writer, or "
            "--resample when the gate failed on model-supplied text no request contains"
        )
    extra = {
        "after": found[-1],
        "causes": located,
        "fixes": fixes,
        "writer_changed_from": settings["writer"] if chosen != settings["writer"] else None,
    }
    if reason:
        extra["resample"] = reason
    return prepare(
        line, found[-1] + 1, writer=chosen, binary=binary or settings["binary"]["path"], extra=extra
    )


# ------------------------------------------------------------------- spend and transport


def traces(d: Path, *, stage: str | None = None, attempts: bool = True) -> list[Path]:
    """Every production transport trace of the draw, a failed attempt's included."""
    pattern = f"transport/{stage}-*/attempt-*.json" if stage else "transport/*/attempt-*.json"
    found = list(d.glob(pattern))
    if attempts:
        found += d.glob("attempts/*/transport/*/attempt-*.json")
    return sorted(found, key=lambda path: (path.stat().st_mtime_ns, path.name))


def read_trace(path: Path) -> dict[str, Any] | None:
    """A trace as production wrote it, or None when it cannot be read: a call killed while its
    trace was being written leaves a truncated file, which is a call whose usage and isolation
    are unknown, never a reason for the lane to stop answering."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def trace_tokens(raw: dict[str, Any]) -> int | None:
    for event in raw.get("events") or []:
        usage = event.get("usage") if event.get("type") == "turn.completed" else None
        if isinstance(usage, dict):
            return int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
    return None


def spend(d: Path) -> dict[str, int]:
    """Every traced call counts, an unreadable one as a call of unknown usage."""
    rows = [read_trace(path) for path in traces(d)]
    tokens = [None if raw is None else trace_tokens(raw) for raw in rows]
    return {
        "calls": len(rows),
        "tokens": sum(t for t in tokens if t is not None),
        "usage_unknown": sum(t is None for t in tokens),
        "unreadable": sum(raw is None for raw in rows),
    }


def draw_seconds(state: dict[str, Any], at: str) -> float:
    records = [
        *state.get("stages", {}).values(),
        *(entry["record"] for entry in state.get("attempts", [])),
    ]
    total = 0.0
    for record in records:
        if record.get("status") == "running":
            total += elapsed(record["started_at"], at)
        else:
            total += float(record.get("seconds") or 0.0)
    return total


def admission(d: Path, state: dict[str, Any]) -> str | None:
    """Before a stage and every step: the reason nothing more may be spent, or None."""
    if state.get("stop"):
        return str(state["stop"])
    limits = read(d / "settings.json")["limits"]
    used = spend(d) | {"seconds": draw_seconds(state, now())}
    for name in ("calls", "tokens", "seconds"):
        if used[name] >= limits[name]:
            return f"ceiling:{name}"
    return None


def trace_checks(raw: dict[str, Any], python: Path) -> dict[str, bool]:
    """A dispatched Codex call's isolation, read off production's own trace."""
    argv, settings = raw.get("argv") or [], raw.get("settings") or {}
    bridge: list[dict[str, Any]] = []
    bridge_readable = True
    for line in (raw.get("commands_jsonl") or "").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            bridge_readable = False
            continue
        if isinstance(entry, dict):
            bridge.append(entry)
    results = [e for e in bridge if e.get("phase") == "result" and e.get("argv") is not None]
    working = raw.get("working_directory")
    return {
        "provider": raw.get("provider") == PROVIDER,
        "isolated": all(flag in argv for flag in ISOLATION_FLAGS),
        # §258's control on the Codex side: the call ran outside the repository.
        "outside_repository": bool(working) and not within(str(working), REPO),
        "no_memory": settings.get("features.memories") is False,
        "no_project_docs": settings.get("project_doc_max_bytes") == 0,
        "no_search": settings.get("web_search") == "disabled",
        "bridge_runtime": bridge_readable
        and all(
            bool(entry["argv"])
            and entry["argv"][1:3] == ["-m", "litharness"]
            and os.path.normcase(str(entry["argv"][0])) == os.path.normcase(str(python))
            for entry in results
        ),
    }


def transport_summary(
    d: Path, stage: str, checkpoint: str, kind: str = "transport"
) -> dict[str, Any]:
    """The stage's calls as production traced them, filed as `checkpoints/<cp>.<kind>.json`.

    Every failed call is listed with whether production retried it, meaning a completed call
    of the same profile came after it in the stage (the scheduler retries a failed job on a
    later tick). Every isolation check that failed on a dispatched call is listed too. A trace
    nobody can read fails the isolation check, since what that call was sent is not known."""
    python = runtime_python(d)
    rows = [(path, read_trace(path)) for path in traces(d, stage=stage, attempts=False)]
    failed: list[dict[str, Any]] = []
    isolation: dict[str, list[str]] = {}
    models: Counter[str] = Counter()
    tokens = 0
    for index, (path, raw) in enumerate(rows):
        name = path.relative_to(d).as_posix()
        if raw is None:
            failed.append({"trace": name, "failure": "unreadable trace", "retried": False})
            isolation[name] = ["readable"]
            models["unreadable trace"] += 1
            continue
        if call_failed(raw):
            retried = any(
                later is not None
                and not call_failed(later)
                and later.get("profile") == raw.get("profile")
                for _, later in rows[index + 1 :]
            )
            failed.append(
                {
                    "trace": name,
                    "profile": raw.get("profile"),
                    "failure": str(raw.get("failure") or "")[:300],
                    "retried": retried,
                }
            )
        if "argv" in raw:
            broken = [check for check, ok in trace_checks(raw, python).items() if not ok]
            if broken:
                isolation[name] = broken
        models[
            f"{raw.get('profile')} {raw.get('requested_model')} {raw.get('reasoning_effort')}"
        ] += 1
        tokens += trace_tokens(raw) or 0
    summary = {
        "stage": stage,
        "calls": len(rows),
        "tokens": tokens,
        "failed": failed,
        "unretried": [entry["trace"] for entry in failed if not entry["retried"]],
        "isolation_failures": isolation,
        "profiles": dict(sorted(models.items())),
        "draw_spend": spend(d),
        "recorded_at": now(),
    }
    write(checkpoint_path(d, checkpoint, kind), summary)
    return summary


def call_failed(raw: dict[str, Any]) -> bool:
    return "failure" in raw or raw.get("returncode") not in (0, None) or "final_text" not in raw


def transport_problem(summary: dict[str, Any]) -> str | None:
    """Why no gate may read over these calls, or None: a call that ran without its isolation
    controls or cannot be read (what the model saw is not known), a failed call production never
    retried (the checkpoint may lack its answer), or no traced call at all (no evidence)."""
    if not summary["calls"]:
        return "the stage traced no call, so nothing shows how its calls were isolated"
    parts = []
    if summary["isolation_failures"]:
        parts.append(
            "a call ran without its isolation controls or left a trace nobody can read, so what "
            f"the model saw is not known: {sorted(summary['isolation_failures'])}"
        )
    unreadable = set(summary["isolation_failures"])
    unretried = [trace for trace in summary["unretried"] if trace not in unreadable]
    if unretried:
        parts.append(f"a failed call production never retried: {unretried}")
    return "; ".join(parts) or None


def write_receipts(d: Path) -> None:
    """`calls/`: a derived copy of each completed trace in the shape the register report reads.
    Rebuilt whole at each checkpoint; the traces under `transport/` stay the record."""
    folder = d / "calls"
    if folder.is_dir():
        for old in folder.glob("*.json"):
            old.unlink()
    for index, path in enumerate(traces(d, attempts=False), start=1):
        raw = read_trace(path)
        if raw is None or "final_text" not in raw or "failure" in raw:
            continue
        request = {
            "profile": raw.get("profile"),
            "prompt": raw.get("prompt"),
            "system": raw.get("system"),
        }
        write(
            folder / f"{index:04d}-{path.parent.name}.json",
            {
                "profile": raw.get("profile"),
                "request": request,
                "result": {"text": raw.get("final_text")},
                "status": "completed",
                "trace": path.relative_to(d).as_posix(),
                "trace_sha256": sha(path),
            },
        )


def file_register_report(d: Path, checkpoint: str) -> dict[str, Any]:
    """Run the register report beside the gate and file what it printed. Inert: it decides
    nothing, and a failure is recorded and blocks nothing."""
    text = d / "checkpoints" / f"{checkpoint}.register.txt"
    failed = checkpoint_path(d, checkpoint, "register-failed")
    if not text.is_file() and not failed.is_file():
        write_receipts(d)
        argv = [sys.executable, str(REGISTER_REPORT), "--draw", str(d)]
        listing = d / "listing" / "listing.txt"
        if listing.is_file():
            argv += ["--listing", str(listing)]
        if checkpoint == "chapter" and (d / "chapter-one.md").is_file():
            argv += ["--chapter", str(d / "chapter-one.md")]
        argv += ["--json", str(checkpoint_path(d, checkpoint, "register"))]
        try:
            done = subprocess.run(
                argv,
                cwd=REPO,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=900,
                check=False,
            )
            code, out, err = done.returncode, done.stdout, done.stderr
        except (OSError, subprocess.SubprocessError) as error:
            code, out, err = None, "", repr(error)
        if code == 0:
            text.parent.mkdir(parents=True, exist_ok=True)
            text.write_text(out, encoding="utf-8", newline="\n")
        else:
            write_new(failed, {"returncode": code, "stderr": err[-4000:], "at": now()})
    if text.is_file():
        return {"register_report": text.relative_to(d).as_posix(), "register_sha256": sha(text)}
    return {"register_report": None, "register_failure_sha256": sha(failed)}


# --------------------------------------------------------------- the child: store reads


def require_frozen_source(d: Path) -> None:
    """A child mode imports the draw's archived source, never the live checkout."""
    import litharness

    if not Path(str(litharness.__file__)).resolve().is_relative_to((d / "source").resolve()):
        raise Refusal("this child imported an unfrozen source")


def metadata(d: Path, database: Path | None = None) -> dict[str, Any]:
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.jobs import JobStatus
    from litharness.domain.nodes import NodeKind

    database = database or d / "book.db"
    if not database.exists():
        return {
            "exists": False,
            "accepted": 0,
            "total": 0,
            "terminal": 0,
            "exceptions": 0,
            "scene_ids": [],
            "scene_hashes": {},
            "jobs": {},
        }
    with SqliteStore.open_read_only(database) as store:
        branches = store.branches()
        head = store.head(branches[0][0], branches[0][1]) if branches else None
        scenes = (
            [node for node in head.in_reading_order() if node.kind is NodeKind.SCENE]
            if head
            else []
        )
        jobs = {s.value: len(store.jobs_by_status(s, limit=10000)) for s in JobStatus}
        exceptions = len(store.open_exceptions())
    drafted = {n.logical_id: sha_text(n.content or "") for n in scenes if (n.content or "").strip()}
    return {
        "exists": True,
        "accepted": len(drafted),
        "total": len(scenes),
        "scene_ids": [node.logical_id for node in scenes],
        "scene_hashes": drafted,
        "jobs": jobs,
        "terminal": sum(jobs.get(key, 0) for key in ("parked", "poisoned")),
        "exceptions": exceptions,
    }


def store_digest(d: Path, database: Path | None = None) -> str | None:
    """One digest over the store a gate read: every state record, and the scenes' ids and
    accepted texts. None before the store exists. `database` digests another copy, such as a
    checkpoint's backup, by the same rule."""
    from litharness.adapters.sqlite_store import SqliteStore

    database = database or d / "book.db"
    if not database.exists():
        return None
    with SqliteStore.open_read_only(database) as store:
        branches = store.branches()
        records = store.state_records(branches[0][0], branches[0][1]) if branches else []
    rows = sorted(
        json.dumps(
            json.loads(json.dumps(dataclasses.asdict(record), default=str)),
            sort_keys=True,
            ensure_ascii=False,
        )
        for record in records
    )
    book = metadata(d, database)
    body = {"records": rows, "scene_ids": book["scene_ids"], "scene_hashes": book["scene_hashes"]}
    return sha_text(json.dumps(body, sort_keys=True, ensure_ascii=False))


def chapter_texts(d: Path, chapter_scenes: int) -> list[str]:
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.nodes import NodeKind

    with SqliteStore.open_read_only(d / "book.db") as store:
        book, branch, _ = store.branches()[0]
        head = store.head(book, branch)
    scenes = [n for n in head.in_reading_order() if n.kind is NodeKind.SCENE] if head else []
    return [(node.content or "").strip() for node in scenes[:chapter_scenes]]


def view(d: Path, settings: dict[str, Any], name: str, arguments: list[str]) -> Path:
    """A read-only CLI view, recorded as it answered; a view never stops the lane."""
    from litharness import cli

    argv = base_args(d, settings) + arguments
    reason = argv_refusal(d, argv)
    if reason:
        raise Refusal(reason)
    output = io.StringIO()
    record: dict[str, Any] = {"arguments": arguments}
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = cli.main(argv)
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else 2
            record["exception"] = "SystemExit"
        except Exception as error:  # recorded, never raised past a view
            code = 2
            record["exception"] = type(error).__name__
    path = d / "views" / f"{name}.json"
    write(path, record | {"returncode": code, "output": output.getvalue()})
    return path


def library_shelves(d: Path) -> list[Path]:
    return sorted(marker.parent for marker in (d / "library").glob(f"*/{SHELF_MARKER}"))


def checkpoint_files(d: Path, checkpoint: str) -> list[Path]:
    """The files a gate read reads at this checkpoint, beside the stage's own step records."""
    steps = sorted((d / "steps").glob(f"{STAGE_OF[checkpoint]}-*.json"))
    if checkpoint in ("concept", "listing"):
        return [*(d / checkpoint).rglob("*"), *steps]
    if checkpoint == "world":
        return [*(d / "views").glob("world-*.json"), *steps]
    shelves = [path for shelf in library_shelves(d) for path in shelf.rglob("*")]
    views = [d / "views" / f"{name}.json" for name in ("library", "status", "verify", "plans")]
    return [d / "chapter-one.md", *views, *(d / "views").glob("why-*.json"), *shelves, *steps]


def bind(d: Path, checkpoint: str) -> None:
    """Record what the gate at this checkpoint reads, and back the store up for a retry of the
    next stage. At the world checkpoint it writes the world views; at chapter one the reading
    copy, the library export and the status views. No provider call is made."""
    settings = read(d / "settings.json")
    if checkpoint == "world":
        view(d, settings, "world-show", ["world", "show", "--json"])
        view(d, settings, "world-ladders", ["world", "ladders", "--json"])
    if checkpoint == "chapter":
        texts = chapter_texts(d, int(settings["layout"]["chapter_scenes"]))
        title_path = d / "listing" / "title.txt"
        title = title_path.read_text(encoding="utf-8").strip() if title_path.is_file() else ""
        (d / "chapter-one.md").write_text(
            f"# {title}\n\n## Chapter 1\n\n" + "\n\n* * *\n\n".join(texts) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        view(d, settings, "library", ["library"])
        for name in ("status", "verify", "plans"):
            view(d, settings, name, [name, "--json"])
        for k in range(1, int(settings["layout"]["chapter_scenes"]) + 1):
            view(d, settings, f"why-{k}", ["why", "--scene", str(k), "--json"])
    backup = None
    if (d / "book.db").exists():
        backup = d / "checkpoints" / f"{checkpoint}.book.db"
        backup.parent.mkdir(parents=True, exist_ok=True)
        with (
            contextlib.closing(sqlite3.connect(d / "book.db")) as source,
            contextlib.closing(sqlite3.connect(backup)) as target,
        ):
            source.backup(target)
    files = checkpoint_files(d, checkpoint)
    write_new(
        checkpoint_path(d, checkpoint, "binding"),
        {
            "checkpoint": checkpoint,
            "artifacts": {
                p.relative_to(d).as_posix(): sha(p) for p in sorted(files) if p.is_file()
            },
            "store_sha256": store_digest(d),
            "store_backup": backup.relative_to(d).as_posix() if backup else None,
            "recorded_at": now(),
        },
    )


def binding_changes(
    d: Path, checkpoint: str, gate_entry: dict[str, Any] | None = None
) -> list[str]:
    """What changed since this checkpoint was bound (and, given its gate, since it was read)."""
    path = checkpoint_path(d, checkpoint, "binding")
    if not path.is_file():
        return [path.relative_to(d).as_posix()]
    if gate_entry is not None and sha(path) != gate_entry.get("binding_sha256"):
        return [path.relative_to(d).as_posix()]
    return [
        name
        for name, digest_ in read(path)["artifacts"].items()
        if not (d / name).is_file() or sha(d / name) != digest_
    ]


def child_step(d: Path, key: str) -> None:
    """Run one step's production CLI verb in this process and write its record."""
    import litharness
    from litharness import cli

    require_frozen_source(d)
    stage, name, _ = parse_key(key)
    settings = read(d / "settings.json")
    arguments = base_args(d, settings) + stage_argv(d, settings, stage, name)
    reason = argv_refusal(d, arguments)
    if reason:
        raise Refusal(reason)
    record: dict[str, Any] = {
        "key": key,
        "stage": stage,
        "name": name,
        "arguments": arguments,
        "source": str(litharness.__file__),
        "tool_sha256": sha(TOOL),
        "started_at": now(),
        "before": metadata(d),
    }
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = cli.main(arguments)
        except BaseException as error:
            code = 2
            record["exception"] = repr(error)
    record.update(
        finished_at=now(),
        returncode=code,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
        after=metadata(d),
    )
    write_new(d / "steps" / f"{key}.json", record)


def record_child(d: Path, key: str) -> None:
    """A child's first act: its own PID beside the draw. On Windows the runtime's `python.exe`
    is a launcher that runs the interpreter as a process of its own, so the PID the parent saw
    start is not this one, and the parent can die before it records either."""
    write(d / "children" / f"{key}.json", {"pid": os.getpid(), "started_at": now()})


def child_pids(d: Path, keys: Sequence[str]) -> dict[str, int]:
    """The PIDs children of these keys recorded for themselves."""
    found: dict[str, int] = {}
    for key in keys:
        path = d / "children" / f"{key}.json"
        with contextlib.suppress(OSError, ValueError):
            pid = read(path).get("pid")
            if isinstance(pid, int):
                found[f"interpreter {key}"] = pid
    return found


def forbid_provider_calls() -> None:
    from litharness.providers.codex_cli import CodexCliProvider

    def refuse(provider: Any, request: Any) -> Any:
        raise RuntimeError("no provider call is made while binding")

    setattr(CodexCliProvider, "complete", refuse)  # noqa: B010


# ---------------------------------------------------------------- the parent: stages


def kill_tree(process: subprocess.Popen[str]) -> None:
    """Stop a child and anything it started; on Windows only taskkill /T reaches the tree."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        process.kill()


def run_child(
    argv: list[str],
    env: dict[str, str],
    *,
    timeout: float | None = None,
    capture: bool = False,
    started: Callable[[int], None] | None = None,
) -> tuple[int | None, str]:
    """A child in the draw's runtime: (its exit code, or None when the wall time ran out;
    its stdout when captured). `started` hears the child's PID before anything waits on it; a
    runner stopped while it waits takes the child's tree down with it."""
    process = subprocess.Popen(
        argv,
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        text=True,
        encoding="utf-8",
    )
    try:
        if started is not None:
            started(process.pid)
        out, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        process.communicate()
        return None, ""
    except BaseException:
        kill_tree(process)
        raise
    return process.returncode, out or ""


def run_tracked(
    d: Path,
    stage: str,
    key: str,
    argv: list[str],
    env: dict[str, str],
    *,
    timeout: float | None = None,
) -> int | None:
    """A child whose PID the stage record holds from its start until it ends. A runner killed
    by PID leaves its child running on Windows, and that child and its Codex process may still
    be writing to the store and the traces; `retry` wants every such PID gone. The child also
    records its own interpreter's PID (`record_child`)."""

    def started(pid: int) -> None:
        state = progress(d)
        state["stages"][stage]["child"] = {"key": key, "pid": pid, "started_at": now()}
        save(d, state)

    code, _ = run_child(argv, env, timeout=timeout, started=started)
    state = progress(d)
    child = state["stages"][stage].get("child")
    if child and child.get("key") == key:
        child["ended_at"] = now()
        save(d, state)
    return code


def child_digest(d: Path, database: Path | None = None) -> str | None:
    argv = [str(runtime_python(d)), str(TOOL), "_digest", str(d)]
    if database is not None:
        argv.append(str(database))
    code, out = run_child(argv, environment(d), capture=True)
    if code != 0:
        raise Refusal(f"the store digest child exited {code}")
    value: str | None = json.loads(out.strip().splitlines()[-1])["store_sha256"]
    return value


def stage_refusal(d: Path, state: dict[str, Any], stage: str) -> str | None:
    if stage not in STAGES:
        return f"unknown stage {stage}"
    if state["status"] in (*ENDED, "passed"):
        return f"{d.name} has ended ({state['status']})"
    if state.get("stop"):
        return f"{d.name} stopped: {state['stop']}"
    if state.get("active"):
        return f"a step is recorded as active ({state['active']}); check by PID that none is live"
    if stage in state["stages"]:
        return f"{stage} already ran in {d.name}; a stopped stage is retried with `retry`"
    index = STAGES.index(stage)
    if index:
        checkpoint = CHECKPOINT_OF[STAGES[index - 1]]
        gate_entry = state["gates"].get(checkpoint)
        if not gate_entry or gate_entry["result"] != "pass":
            return f"{stage} waits for a recorded pass at the {checkpoint} checkpoint"
    return admission(d, state)


def refuse_stage(d: Path, state: dict[str, Any], stage: str) -> None:
    """Raise the reason `stage` may not start. A ceiling reached at a stage boundary ends the
    draw: the last call of a stage may cross one, and the next stage is then never admitted."""
    reason = stage_refusal(d, state, stage)
    if not reason:
        return
    if reason.startswith("ceiling:"):
        state["stop"] = state.get("stop") or reason
        state["status"] = "stopped"
        save(d, state)
        ledger(d, "stopped", stage=stage, reason=reason)
    raise Refusal(reason)


def dispatch(d: Path, stage: str, name: str, iteration: int) -> dict[str, Any]:
    key = f"{stage}-{name}-{iteration}"
    path = d / "steps" / f"{key}.json"
    if path.exists():
        raise Refusal(f"refusing a duplicate step {key}")
    state = progress(d)
    stop = admission(d, state)
    if stop is None:
        state["active"] = key
        state["stages"][stage]["steps"].append(key)
        save(d, state)
        limit = float(read(d / "settings.json")["limits"]["seconds"])
        remaining = max(limit - draw_seconds(state, now()), 1.0)
        argv = [str(runtime_python(d)), str(TOOL), "_step", str(d), key]
        code = run_tracked(d, stage, key, argv, environment(d, key), timeout=remaining)
        state = progress(d)
        state.pop("active", None)
        if code is None:
            stop = "ceiling:seconds"
        elif not path.is_file():
            stop = f"the {key} child exited {code} without a step record"
    if stop is not None:
        state["stop"] = state.get("stop") or stop
    save(d, state)
    record: dict[str, Any] = (
        read(path)
        if path.is_file()
        else {"key": key, "returncode": 2, "stdout": "", "before": {}, "after": {}}
    )
    print(
        json.dumps(
            {
                "step": key,
                "returncode": record["returncode"],
                "accepted": record["after"].get("accepted"),
                "stop": state.get("stop"),
                **spend(d),
            }
        ),
        flush=True,
    )
    return record


def step_problem(d: Path, name: str, record: dict[str, Any]) -> str | None:
    state = progress(d)
    if state.get("stop"):
        return str(state["stop"])
    code = record["returncode"]
    if code == 2:
        return f"{name} exited 2 (operational fault) {record.get('exception', '')}".strip()
    if code and not (name == "world-check" and code == 1):
        return f"{name} exited {code}"
    after = record["after"]
    if after["accepted"]:
        return "a scene was drafted before the chapter stage"
    if after["terminal"] or after["exceptions"]:
        return "a parked or poisoned unit or an open exception needs a person"
    if name == "concept" and not (d / "concept" / "concept.json").is_file():
        return "concept wrote no concept.json"
    if name == "listing":
        scenes = int(read(d / "settings.json")["layout"]["scenes"])
        if not (d / "listing" / "title.txt").is_file():
            return "listing wrote no title"
        if after["total"] != scenes:
            return f"the listing stood up {after['total']} scenes, not {scenes}"
    elif after["total"] != record["before"]["total"]:
        return "the scene count changed"
    return None


def tick_verdict(
    record: dict[str, Any], state: dict[str, Any], chapter_scenes: int
) -> tuple[str | None, bool]:
    """One tick's operational reading: (a stop reason, chapter one accepted)."""
    if state.get("stop"):
        return str(state["stop"]), False
    before, after = record["before"], record["after"]
    if record["returncode"] == 2:
        return f"tick exited 2 (operational fault) {record.get('exception', '')}".strip(), False
    if after["terminal"] or after["exceptions"]:
        return "a parked or poisoned unit or an open exception needs a person", False
    if after["total"] != before["total"]:
        return "the scene count changed", False
    if any(after["scene_hashes"].get(k) != v for k, v in before["scene_hashes"].items()):
        return "an accepted scene changed", False
    chapter = after["scene_ids"][:chapter_scenes]
    beyond = sorted(set(after["scene_hashes"]) - set(chapter))
    if beyond:
        return f"a scene past chapter one was drafted: {beyond}", False
    done = len(chapter) == chapter_scenes and all(s in after["scene_hashes"] for s in chapter)
    if not done and "no_work tick=" in record["stdout"]:
        return "an idle tick before chapter one was accepted", False
    return None, done


def drive_chapter(d: Path) -> str | None:
    chapter_scenes = int(read(d / "settings.json")["layout"]["chapter_scenes"])
    record = dispatch(d, "chapter", "world-accept", 1)
    state = progress(d)
    if state.get("stop"):
        return str(state["stop"])
    if record["returncode"] != 0:
        return (
            f"world accept refused (exit {record['returncode']}); a person reads world "
            "check, and no automatic repair is made"
        )
    failed = 0
    for iteration in range(1, MAX_TICKS + 1):
        record = dispatch(d, "chapter", "tick", iteration)
        reason, done = tick_verdict(record, progress(d), chapter_scenes)
        if reason:
            return reason
        if done:
            return None
        failed = failed + 1 if record["returncode"] == 1 else 0
        if failed >= MAX_FAILED_TICKS:
            return f"{failed} consecutive failed ticks"
    return f"{MAX_TICKS} ticks without accepting chapter one"


def drive(d: Path, stage: str) -> str | None:
    if stage == "chapter":
        return drive_chapter(d)
    for name in FIXED_STEPS[stage]:
        reason = step_problem(d, name, dispatch(d, stage, name, 1))
        if reason:
            return reason
    return None


def finish_stage(d: Path, stage: str, reason: str | None) -> None:
    state = progress(d)
    state.pop("active", None)
    record = state["stages"][stage]
    record["finished_at"] = now()
    record["seconds"] = round(elapsed(record["started_at"], record["finished_at"]), 1)
    if reason is None:
        record["status"] = "done"
        state["status"] = "at_checkpoint"
    else:
        record.update(status="stopped", reason=reason)
        state["status"] = "stopped"
        state["stop"] = state.get("stop") or reason
    save(d, state)
    ledger(d, "stage", stage=stage, status=record["status"], reason=reason)


def bind_checkpoint(d: Path, checkpoint: str) -> str | None:
    """Bind what the gate will read; a failure is an operational stop, since nothing unbound
    may be gated."""
    argv = [str(runtime_python(d)), str(TOOL), "_bind", str(d), checkpoint]
    code = run_tracked(d, STAGE_OF[checkpoint], f"bind-{checkpoint}", argv, environment(d))
    if code or not checkpoint_path(d, checkpoint, "binding").is_file():
        return f"the {checkpoint} checkpoint could not be bound (bind exited {code})"
    return None


def verify_runtime(d: Path) -> None:
    runtime = read(d / "runtime.json")
    if installed_distributions(runtime["purelib"]) != runtime["distributions"]:
        raise Refusal(
            "the shared site-packages the draw's runtime imports changed since prepare; run "
            "the lane with `uv run --no-sync` and restore the environment"
        )


def run_stage(line: str, stage: str) -> int:
    refuse_live_environment()
    lock()
    d = current(line)
    verify_runtime(d)
    state = progress(d)
    refuse_stage(d, state, stage)
    index = STAGES.index(stage)
    if index:
        # The inputs this stage acts on are the ones the previous gate read: its files, and
        # its store, so `world accept` accepts only the world the W gate read.
        previous = CHECKPOINT_OF[STAGES[index - 1]]
        changed = binding_changes(d, previous, state["gates"][previous])
        if changed:
            raise Refusal(f"what the {previous} gate read changed since it was recorded: {changed}")
        bound = read(checkpoint_path(d, previous, "binding"))["store_sha256"]
        if bound is not None and child_digest(d) != bound:
            raise Refusal(
                f"the store changed after the {previous} checkpoint was bound; the "
                "gate did not read this store"
            )
    state["status"] = "running"
    state["stages"][stage] = {
        "status": "running",
        "started_at": now(),
        "steps": [],
        "runner_pid": os.getpid(),
    }
    save(d, state)
    checkpoint = CHECKPOINT_OF[stage]
    try:
        outcome = drive(d, stage)
        # Read before anything is bound, so a call no gate may pass over stops the stage while
        # a retry is still open to it: nothing it wrote has been bound or read.
        summary = transport_summary(d, stage, checkpoint)
        if outcome is None:
            problem = transport_problem(summary)
            if problem:
                outcome = f"{TRANSPORT_STOP} {problem}; nothing was bound or read"
            else:
                outcome = bind_checkpoint(d, checkpoint)
    except BaseException as error:
        finish_stage(d, stage, f"scheduler failure: {error!r}")
        raise
    finish_stage(d, stage, outcome)
    if outcome is not None:
        print(f"STOPPED in {stage}: {outcome}")
        print_transport(summary)
        print(
            "Read the step records and the traces first. An operational stop may be retried "
            "with a failure note (`retry`); any other stop ends the draw (`redraw`)."
        )
        return 1
    file_register_report(d, checkpoint)
    print_checkpoint(d, checkpoint, summary)
    return 0


def print_transport(summary: dict[str, Any]) -> None:
    print(
        f"  transport first: {summary['calls']} calls in this stage, {summary['tokens']} tokens; "
        f"draw so far {summary['draw_spend']}"
    )
    for failure in summary["failed"]:
        retried = "retried by production" if failure["retried"] else "NOT RETRIED"
        print(f"  failed call ({retried}): {failure['trace']} {failure['failure']}")
    for name, checks in summary["isolation_failures"].items():
        print(f"  ISOLATION FAILED on {name}: {checks}")


def print_checkpoint(d: Path, checkpoint: str, summary: dict[str, Any]) -> None:
    binding = read(checkpoint_path(d, checkpoint, "binding"))
    print(f"CHECKPOINT {checkpoint}, {d.parent.name} {d.name}. The lane waits for a person.")
    print_transport(summary)
    print(
        f"  bound for the gate: {len(binding['artifacts'])} files and the store "
        f"({binding['store_sha256'] or 'none yet'})"
    )
    report = d / "checkpoints" / f"{checkpoint}.register.txt"
    if report.is_file():
        print(f"  register report beside the gate (decides nothing): {report}")
    else:
        print("  register report did not run; recorded, and the gate proceeds without it")
    print("  the gate read answers, one line each (`<id>: PASS|FAIL|PARTIAL <location>`):")
    for entry in load_items(d / "items.json")["checkpoints"][checkpoint]:
        print(f"    {entry['id']}: {entry['text']}")
    print(
        f"  then: chapter_one.py gate {checkpoint} pass|fail --line {d.parent.name} "
        f"--read {d / f'GATE-{checkpoint}.md'} --by <who>"
    )


# ----------------------------------------------------------------------------- the gate


def item_verdicts(ids: list[str], text: str) -> dict[str, str]:
    """Each item's verdict from its one verdict line, or a Refusal naming what is wrong."""
    found: dict[str, list[str]] = {}
    for match in VERDICT_LINE.finditer(text):
        if match["item"] in ids:
            found.setdefault(match["item"], []).append(match["verdict"])
    missing = [item for item in ids if item not in found]
    if missing:
        raise Refusal(
            f"the gate read does not answer {missing}: each item needs a line "
            "`<id>: PASS|FAIL|PARTIAL <location>`"
        )
    doubled = [item for item in ids if len(found[item]) > 1]
    if doubled:
        raise Refusal(f"the gate read answers {doubled} more than once; one verdict per item")
    return {item: found[item][0] for item in ids}


def gate_result_refusal(result: str, verdicts: dict[str, str]) -> str | None:
    """Pass only when every item is PASS; PARTIAL counts as FAIL."""
    short = sorted(item for item, verdict in verdicts.items() if verdict != "PASS")
    if result == "pass" and short:
        return f"a pass is recorded only when every item is PASS; not PASS: {short}"
    if result == "fail" and not short:
        return "every item reads PASS, so the rule records a pass, not a fail"
    return None


def gate_transport(d: Path, checkpoint: str, summary: dict[str, Any] | None) -> dict[str, Any]:
    """What the gate record holds of the calls under it: the summary rebuilt at the gate, by
    path and hash, and every failed call with whether production retried it."""
    if summary is None:
        return {"summary": None}
    path = checkpoint_path(d, checkpoint, "gate-transport")
    return {
        "summary": path.relative_to(d).as_posix(),
        "sha256": sha(path),
        "calls": summary["calls"],
        "failed": summary["failed"],
        "unretried": summary["unretried"],
        "isolation_failures": summary["isolation_failures"],
    }


def gate(line: str, checkpoint: str, result: str, read_file: Path, by: str) -> dict[str, Any]:
    """Record a person's pass or fail at a checkpoint, held to the items the draw snapshotted.

    The stage's transport summary is rebuilt from its traces and filed beside the gate record,
    every failed call listed with whether production retried it; a pass is refused over any
    call `transport_problem` names, and over a summary that cannot be built. The register
    report is filed beside the gate (run now if it has not been) and recorded by hash; it
    decides nothing, and a failure to run it blocks nothing.
    """
    checkpoint = CHECKPOINT_OF.get(checkpoint, checkpoint)
    if checkpoint not in CHECKPOINTS:
        raise Refusal(f"unknown checkpoint {checkpoint}")
    if result not in GATE_RESULTS:
        raise Refusal("a gate is pass or fail")
    d = current(line)
    state = progress(d)
    if state.get("active") or any(s.get("status") == "running" for s in state["stages"].values()):
        raise Refusal("a stage is running; a gate is recorded only at a checkpoint")
    record = state["stages"].get(STAGE_OF[checkpoint])
    if not record or record.get("status") != "done":
        raise Refusal(f"the {checkpoint} checkpoint was not reached in {d.name}")
    if checkpoint in state["gates"]:
        raise Refusal(f"the {checkpoint} gate is already recorded; one verdict per checkpoint")
    binding_path = checkpoint_path(d, checkpoint, "binding")
    if not binding_path.is_file():
        raise Refusal(f"the {checkpoint} checkpoint was never bound; nothing unbound is gated")
    changed = binding_changes(d, checkpoint)
    if changed:
        raise Refusal(f"checkpoint artifacts changed since they were bound: {changed}")
    # Rebuilt from the stage's traces now, never read from the summary the stage saved: a runner
    # that died after the stage finished may never have written one, and a summary nobody can
    # build refuses a pass rather than letting one through unchecked.
    try:
        summary = transport_summary(d, STAGE_OF[checkpoint], checkpoint, "gate-transport")
    except (OSError, ValueError) as error:
        if result == "pass":
            raise Refusal(
                f"the transport summary could not be built, so no pass: {error!r}"
            ) from error
        summary = None
    problem = transport_problem(summary) if summary is not None else None
    if result == "pass" and problem:
        raise Refusal(problem)
    text = read_file.read_text(encoding="utf-8") if read_file.is_file() else ""
    if not text.strip():
        raise Refusal("the gate read is missing or empty")
    verdicts = item_verdicts(item_ids(d, checkpoint), text)
    refusal = gate_result_refusal(result, verdicts)
    if refusal:
        raise Refusal(refusal)
    entry = {
        "result": result,
        "items": verdicts,
        "by": by,
        "read": str(read_file.resolve()),
        "read_sha256": sha(read_file),
        "binding_sha256": sha(binding_path),
        "items_sha256": sha(d / "items.json"),
        "transport": gate_transport(d, checkpoint, summary),
        **file_register_report(d, checkpoint),
        "recorded_at": now(),
    }
    state["gates"][checkpoint] = entry
    if result == "fail":
        state["status"] = "failed"
    else:
        state["status"] = "passed" if checkpoint == "chapter" else "ready"
    save(d, state)
    ledger(
        d,
        "gate",
        checkpoint=checkpoint,
        result=result,
        items=verdicts,
        read_sha256=entry["read_sha256"],
    )
    print(f"{d.name}: {checkpoint} {result} recorded.")
    if result == "fail":
        print("The draw has ended; its next draw needs a located cause and a change (`redraw`).")
    return entry


# ------------------------------------------------------------------------------ retry


def move_into(d: Path, pattern: str, folder: Path) -> None:
    for path in sorted(d.glob(pattern)):
        target = folder / path.relative_to(d)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))


def operational(stop: str) -> bool:
    return any(marker in stop for marker in OPERATIONAL_STOPS)


def live_processes(
    d: Path, state: dict[str, Any], record: dict[str, Any], verified: Sequence[int]
) -> dict[str, str]:
    """The processes a stopped or abandoned stage may still have writing to the draw, each
    named with what the OS says of it, once neither the OS nor the operator has cleared it.

    They are the runner (while the stage is recorded as running), the child it started and did
    not see end, and the interpreter that child recorded for itself: on Windows the runtime's
    `python.exe` is a launcher, so those are two processes, and both outlive a stopped runner."""
    candidates: dict[str, int] = {}
    if record.get("status") == "running" and isinstance(record.get("runner_pid"), int):
        candidates["runner"] = int(record["runner_pid"])
    child = record.get("child") or {}
    keys = [str(state["active"])] if state.get("active") else []
    if child and not child.get("ended_at"):
        if isinstance(child.get("pid"), int):
            candidates[f"child {child.get('key')}"] = int(child["pid"])
        keys.append(str(child.get("key")))
    candidates |= child_pids(d, sorted(set(keys)))
    active = str(state.get("active") or "")
    recorded = child.get("key") == active or any(name.endswith(f" {active}") for name in candidates)
    if active and not recorded:
        # Marked active, and no PID recorded for it by the runner or the child: the runner died
        # between the two, and whether that child started is not known here.
        candidates[f"child {active} (no PID recorded)"] = -1
    live: dict[str, str] = {}
    for name, pid in candidates.items():
        if pid in verified:
            continue
        running = pid_running(pid) if pid > 0 else None
        if running is False:
            continue
        live[name] = f"{pid}, {'running' if running else 'not known to have ended'}"
    return live


def retry(
    line: str,
    stage: str,
    failure: Path,
    verified_dead_pids: Sequence[int] = (),
    codex_binary: str | None = None,
) -> int:
    """Run a stage again after an operational stop, keeping the failed attempt.

    The draw's Codex binary is kept, with one exception: a shell wrapper frozen into the draw,
    which production refuses before any call, is replaced by the native executable (resolved
    as `start` resolves one, or `codex_binary`), and the retry records both.

    Everything that can refuse is checked before anything is recorded or moved: the stop, the
    processes that may still write to the draw, the note, the runtime, and the store itself,
    restored from the previous checkpoint's backup into `restore/` and digested there. Only then
    are the retry and its failure note's SHA-256 recorded, the failed attempt's steps, traces,
    outputs and store moved to `attempts/<stage>-<k>/`, a folder never used before, and the
    checked copy renamed into place. The stage then runs with the same seed and arguments, and
    the ceilings count every attempt.
    """
    refuse_live_environment()
    lock()
    if stage not in STAGES:
        raise Refusal(f"unknown stage {stage}")
    d = current(line)
    verify_runtime(d)
    state = progress(d)
    record = state["stages"].get(stage)
    checkpoint = CHECKPOINT_OF[stage]
    if record is None:
        raise Refusal(f"{stage} has not run in {d.name}")
    if checkpoint in state["gates"]:
        raise Refusal(f"the {checkpoint} gate is recorded; a retry never follows a read")
    if checkpoint_path(d, checkpoint, "binding").is_file():
        raise Refusal(f"the {checkpoint} checkpoint is bound; its outputs may have been read")
    if record["status"] == "running":
        reason = "the runner process ended mid-stage"
    elif record["status"] == "stopped":
        reason = str(record.get("reason") or "")
    else:
        raise Refusal(f"{stage} is {record['status']}; only a stopped stage is retried")
    live = live_processes(d, state, record, verified_dead_pids)
    if live:
        raise Refusal(
            f"{stage} may still have processes writing to {d.name}: {live}. Verify in "
            "PowerShell that each has ended: stop a live one with `taskkill /PID <pid> /T /F`, "
            "which takes its Codex process too, or find a PID with no recorded number by its "
            f"`_step {d}` command line; then pass --verified-dead-pid once per PID (-1 for one "
            "with no number)"
        )
    # The draw's own stop is read as well as the stage's: a ceiling reached before a scheduler
    # failure was recorded is still a ceiling.
    stops = [reason, *([str(state["stop"])] if state.get("stop") else [])]
    content = [stop for stop in stops if not operational(stop)]
    if content:
        raise Refusal(
            f"{content[0]!r} is not an operational stop; the draw has ended, and the "
            "remedy is a redraw with a located cause"
        )
    earlier = state["retries"].get(stage, [])
    if len(earlier) >= MAX_RETRIES:
        raise Refusal(f"{stage} was retried {len(earlier)} times; the draw has ended")
    if not failure.is_file() or not failure.read_text(encoding="utf-8").strip():
        raise Refusal(
            "a retry needs its failure note: what failed, the failed trace, the "
            "remedy, and that no answer was read"
        )
    note = {"path": str(failure.resolve()), "sha256": sha(failure)}
    settings = read(d / "settings.json")
    binary_replaced: dict[str, Any] | None = None
    if Path(str(settings["binary"]["path"])).suffix.lower() in WRAPPER_SUFFIXES:
        native = resolve_binary(codex_binary)
        binary_replaced = {"before": settings["binary"], "after": binary_record(native)}
    elif codex_binary is not None:
        raise Refusal(
            "a retry keeps the draw's Codex binary; only a shell wrapper, which production "
            "refuses before any call, is replaced"
        )
    index = STAGES.index(stage)
    # The store the stage will start from, restored and checked before anything is recorded
    # or moved, so a failed check leaves the failed attempt where it was and no retry counted.
    restore = d / "restore"
    shutil.rmtree(restore, ignore_errors=True)
    restored: Path | None = None
    if index:
        previous = CHECKPOINT_OF[STAGES[index - 1]]
        bound = read(checkpoint_path(d, previous, "binding"))
        if bound["store_backup"]:
            restore.mkdir()
            restored = restore / "book.db"
            shutil.copy2(d / bound["store_backup"], restored)
        try:
            found = child_digest(d, restored) if restored else None
        except Refusal:
            shutil.rmtree(restore, ignore_errors=True)
            raise
        if found != bound["store_sha256"]:
            shutil.rmtree(restore, ignore_errors=True)
            raise Refusal(f"the {previous} checkpoint's backup is not the store its gate read")
    if record["status"] == "running":
        # Its wall time ends at the last thing it wrote, not at this retry.
        written = [
            p.stat().st_mtime
            for p in (*d.glob(f"steps/{stage}-*.json"), *d.glob(f"transport/{stage}-*/*.json"))
        ]
        ended = max(written, default=datetime.fromisoformat(record["started_at"]).timestamp())
        seconds = ended - datetime.fromisoformat(record["started_at"]).timestamp()
        record = record | {"status": "abandoned", "seconds": round(max(seconds, 0.0), 1)}
    # A folder no attempt used before, whatever the record says: a failed attempt is never
    # moved onto another one.
    used = [
        int(match.group(1))
        for path in (d / "attempts").glob(f"{stage}-*")
        if (match := re.fullmatch(rf"{re.escape(stage)}-(\d+)", path.name))
    ]
    attempt = max([len(earlier), *used]) + 1
    folder = d / "attempts" / f"{stage}-{attempt}"
    # Recorded before anything moves, so a retry that fails from here on still counts, and the
    # next one takes the next folder.
    state["attempts"].append(
        {
            "stage": stage,
            "attempt": attempt,
            "record": record,
            "stop": reason,
            "folder": folder.relative_to(d).as_posix(),
        }
    )
    entry: dict[str, Any] = {"attempt": attempt, "failure_note": note, "at": now()}
    if binary_replaced is not None:
        entry["binary_replaced"] = binary_replaced
    state["retries"][stage] = [*earlier, entry]
    del state["stages"][stage]
    state.pop("active", None)
    state["stop"] = None
    state["status"] = "ready" if index else "prepared"
    save(d, state)
    ledger(
        d,
        "retry",
        stage=stage,
        attempt=attempt,
        stop=reason,
        failure_note=note,
        **({"binary_replaced": binary_replaced} if binary_replaced is not None else {}),
    )
    if binary_replaced is not None:
        write(d / "settings.json", settings | {"binary": binary_replaced["after"]})
    for pattern in (
        f"steps/{stage}-*.json",
        f"transport/{stage}-*",
        f"children/{stage}-*.json",
        f"children/bind-{checkpoint}.json",
        f"checkpoints/{checkpoint}.*",
        "calls",
        "book.db",
        "book.db-wal",
        "book.db-shm",
        *STAGE_OUTPUTS[stage],
    ):
        move_into(d, pattern, folder)
    if restored is not None:
        # The copy checked above, renamed into place: nothing changes its bytes on the way.
        restored.replace(d / "book.db")
    shutil.rmtree(restore, ignore_errors=True)
    return run_stage(line, stage)


# ----------------------------------------------------------- publish, sent, read, status


def publish(line: str) -> Path:
    d = current(line)
    state = progress(d)
    if state["status"] != "passed":
        raise Refusal("only a draw that passed chapter one is copied to the book library")
    if state.get("published"):
        raise Refusal("already published")
    shelves = library_shelves(d)
    if len(shelves) != 1:
        raise Refusal(f"expected one library shelf, found {len(shelves)}")
    # What the operator is sent is what the chapter gate read, file by file: a shelf or reading
    # copy regenerated after the gate is refused, and so is a file the binding never listed.
    changed = binding_changes(d, "chapter", state["gates"].get("chapter"))
    if changed:
        raise Refusal(f"what the chapter gate read changed since it was recorded: {changed}")
    bound = read(checkpoint_path(d, "chapter", "binding"))["artifacts"]
    shelf_files = sorted(p for p in shelves[0].rglob("*") if p.is_file())
    sources = [d / "chapter-one.md", *shelf_files]
    unbound = sorted(
        p.relative_to(d).as_posix() for p in sources if p.relative_to(d).as_posix() not in bound
    )
    if unbound:
        raise Refusal(f"the chapter gate never read {unbound}; nothing ungated is published")
    if (shelves[0] / "chapter-one.md").exists():
        raise Refusal("the shelf holds a chapter-one.md, which the reading copy would replace")
    destination = LIBRARY / shelves[0].name
    if destination.exists():
        raise Refusal(f"{destination} exists; a shelf is never overwritten")
    found = draws(line)
    settings = read(d / "settings.json")
    before = drawn_before(line)
    earlier = []
    for k in found[:-1]:
        other = progress(draw_dir(line, k))
        other_settings = read(draw_dir(line, k) / "settings.json")
        earlier.append(
            {
                "draw": k,
                "status": other["status"],
                "writer": other_settings["writer"],
                "revision": other_settings["revision"],
                "gates": {c: g["result"] for c, g in other["gates"].items()},
                "stop": other.get("stop"),
            }
        )
    shutil.copytree(shelves[0], destination)
    shutil.copy2(d / "chapter-one.md", destination / "chapter-one.md")
    files = {
        path.relative_to(destination).as_posix(): sha(path)
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    gated = {"chapter-one.md": bound["chapter-one.md"]} | {
        p.relative_to(shelves[0]).as_posix(): bound[p.relative_to(d).as_posix()]
        for p in shelf_files
    }
    if files != gated:
        raise Refusal(
            f"{destination} does not hold the bytes the chapter gate read; it stays as copied "
            "for a person to look at, and nothing records it as published"
        )
    # Every draw of the brief counts, the ones before this line included.
    number, count = before + found[-1], before + len(found)
    write_new(
        destination / "DRAW.json",
        {
            "line": line,
            "draw": number,
            "of": count,
            "label": f"draw {number} of {count}",
            "line_draw": found[-1],
            "before_line": read(line_dir(line) / "line.json").get("earlier"),
            "earlier": earlier,
            "revision": settings["revision"],
            "writer": settings["writer"],
            "writer_id": settings["writer_id"],
            "dossier_sha256": settings["dossier_sha256"],
            "causes": read(d / "causes.json") if (d / "causes.json").is_file() else [],
            "fixes": settings.get("fixes", []),
            "brief_sha256": settings["brief_sha256"],
            "items_sha256": settings["items_sha256"],
            "gates": {c: g["result"] for c, g in state["gates"].items()},
            "retries": {s: len(r) for s, r in state["retries"].items()},
            "spend": spend(d),
            "files": files,
        },
    )
    state["published"] = {
        "path": str(destination),
        "at": now(),
        "label": f"draw {number} of {count}",
        "files": files,
    }
    save(d, state)
    ledger(d, "published", path=str(destination), label=f"draw {number} of {count}")
    print(f"Reading edition copied to {destination}: {line} draw {number} of {count}.")
    return destination


def sent(line: str, how: str) -> None:
    d = current(line)
    state = progress(d)
    if state["status"] not in (*ENDED, "passed"):
        raise Refusal(f"{d.name} has not ended ({state['status']})")
    if state["status"] == "passed" and not state.get("published"):
        raise Refusal("publish the reading edition before recording that it was sent")
    if state.get("sent"):
        raise Refusal(f"{d.name} is already recorded as sent")
    state["sent"] = {"how": how, "at": now()}
    save(d, state)
    ledger(d, "sent", how=how)


def record_read(line: str, harvest: Path) -> None:
    """The operator's read, by path and SHA-256 only: a harvest, never data, and never an input
    to any step (§97.1, §148)."""
    d = current(line)
    state = progress(d)
    if not state.get("sent"):
        raise Refusal(f"{d.name} was not recorded as sent")
    if state.get("read"):
        raise Refusal(f"{d.name}'s read is already recorded")
    if not harvest.is_file():
        raise Refusal(f"no harvest at {harvest}")
    state["read"] = {"path": str(harvest.resolve()), "sha256": sha(harvest), "at": now()}
    save(d, state)
    ledger(d, "read", path=state["read"]["path"], sha256=state["read"]["sha256"])


def status(line: str) -> list[dict[str, Any]]:
    """One row per draw, after the brief every draw of the line is told, printed whole so the
    coordinator sees what the model is sent."""
    found = draws(line)
    before = drawn_before(line)
    brief = line_dir(line) / "brief.txt"
    print(
        json.dumps(
            {
                "line": line,
                "brief_sha256": sha(brief),
                "drawn_before_line": before,
                "brief": brief.read_text(encoding="utf-8"),
            },
            ensure_ascii=False,
        )
    )
    rows = []
    for k in found:
        d = draw_dir(line, k)
        state, settings = progress(d), read(d / "settings.json")
        rows.append(
            {
                "draw": f"{before + k} of {before + len(found)}",
                "status": state["status"],
                "stop": state.get("stop"),
                "writer": settings["writer"],
                "revision": settings["revision"][:12],
                "stages": {s: r.get("status") for s, r in state["stages"].items()},
                "gates": {c: g["result"] for c, g in state["gates"].items()},
                "retries": {s: len(r) for s, r in state["retries"].items()},
                "active": state.get("active"),
                "spend": spend(d),
                "published": bool(state.get("published")),
                "sent": bool(state.get("sent")),
                "read": bool(state.get("read")),
            }
        )
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    return rows


# ------------------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    begin = sub.add_parser("start", help="a new line and its first draw; no provider call")
    begin.add_argument("--line", required=True)
    begin.add_argument("--brief-file", type=Path, required=True)
    begin.add_argument("--writer", required=True, help="an accepted writer in the roster")
    begin.add_argument("--provider", choices=(PROVIDER,), default=PROVIDER)
    begin.add_argument("--codex-binary")
    begin.add_argument("--person", default=DEFAULT_LAYOUT["person"])
    for name in ("scenes", "chapter_scenes", "arc_chapters"):
        begin.add_argument(f"--{name.replace('_', '-')}", type=int, default=DEFAULT_LAYOUT[name])
    for name in ("calls", "tokens", "seconds"):
        begin.add_argument(f"--max-{name}", type=int, default=DEFAULT_LIMITS[name])
    begin.add_argument(
        "--cause", action="append", default=[], help="for a brief drawn before, as redraw's"
    )
    begin.add_argument("--fix", action="append", default=[], help="as redraw's --fix")
    begin.add_argument(
        "--prior-draws", type=int, default=0, help="draws of this brief the scan cannot see"
    )
    begin.add_argument("--prior-source", type=Path, help="where those draws are recorded")
    again = sub.add_parser("redraw", help="the next draw of a line whose last draw ended")
    again.add_argument("--line", required=True)
    again.add_argument(
        "--cause",
        action="append",
        required=True,
        help="`<checkpoint>: <file>[:line][ locator]: <what the read found>`, once per cause",
    )
    again.add_argument(
        "--fix", action="append", default=[], help="a 40-hex src/ or migrations/ commit"
    )
    again.add_argument("--writer", help="a different accepted writer")
    again.add_argument(
        "--resample",
        help="draw again unchanged: what the model supplied that no recorded request contains",
    )
    again.add_argument("--codex-binary")
    for stage in STAGES:
        sub.add_parser(stage).add_argument("--line", required=True)
    gate_parser = sub.add_parser("gate")
    gate_parser.add_argument("checkpoint", choices=(*CHECKPOINTS, "seed"))
    gate_parser.add_argument("result", choices=GATE_RESULTS)
    gate_parser.add_argument("--line", required=True)
    gate_parser.add_argument("--read", type=Path, required=True)
    gate_parser.add_argument("--by", required=True)
    retry_parser = sub.add_parser("retry")
    retry_parser.add_argument("stage", choices=STAGES)
    retry_parser.add_argument("--line", required=True)
    retry_parser.add_argument("--failure", type=Path, required=True)
    retry_parser.add_argument(
        "--verified-dead-pid", type=int, action="append", default=[], help="once per PID"
    )
    retry_parser.add_argument(
        "--codex-binary", help="the native executable, when the draw froze a shell wrapper"
    )
    for name in ("publish", "status"):
        sub.add_parser(name).add_argument("--line", required=True)
    sent_parser = sub.add_parser("sent")
    sent_parser.add_argument("--line", required=True)
    sent_parser.add_argument("--how", required=True)
    read_parser = sub.add_parser("read")
    read_parser.add_argument("--line", required=True)
    read_parser.add_argument("--harvest", type=Path, required=True)
    for child in ("_step", "_bind", "_digest"):
        child_parser = sub.add_parser(child)
        child_parser.add_argument("draw", type=Path)
        if child != "_digest":
            child_parser.add_argument("name")
        else:
            child_parser.add_argument("database", type=Path, nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode in STAGES:
            return run_stage(args.line, args.mode)
        if args.mode == "start":
            layout = {
                "person": args.person,
                "scenes": args.scenes,
                "chapter_scenes": args.chapter_scenes,
                "arc_chapters": args.arc_chapters,
            }
            limits = {
                "calls": args.max_calls,
                "tokens": args.max_tokens,
                "seconds": args.max_seconds,
            }
            start(
                args.line,
                args.brief_file,
                args.writer,
                binary=args.codex_binary,
                layout=layout,
                limits=limits,
                causes=args.cause,
                fixes=args.fix,
                prior_draws=args.prior_draws,
                prior_source=args.prior_source,
            )
        elif args.mode == "redraw":
            redraw(args.line, args.cause, args.fix, args.writer, args.codex_binary, args.resample)
        elif args.mode == "gate":
            gate(args.line, args.checkpoint, args.result, args.read, args.by)
        elif args.mode == "retry":
            return retry(
                args.line, args.stage, args.failure, args.verified_dead_pid, args.codex_binary
            )
        elif args.mode == "publish":
            publish(args.line)
        elif args.mode == "sent":
            sent(args.line, args.how)
        elif args.mode == "read":
            record_read(args.line, args.harvest)
        elif args.mode == "status":
            status(args.line)
        elif args.mode == "_step":
            record_child(args.draw, args.name)
            child_step(args.draw, args.name)
        elif args.mode == "_bind":
            record_child(args.draw, f"bind-{args.name}")
            require_frozen_source(args.draw)
            forbid_provider_calls()
            bind(args.draw, args.name)
        elif args.mode == "_digest":
            require_frozen_source(args.draw)
            print(json.dumps({"store_sha256": store_digest(args.draw, args.database)}))
    except Refusal as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
