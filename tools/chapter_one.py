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

**Retries and redraws.** A stage that stopped for an operational cause (an exit-2 fault, a
killed runner, failed ticks, a binding failure) may be retried twice with a failure note whose
SHA-256 is recorded before dispatch; the failed attempt is kept under `attempts/`, the store
is restored from the previous checkpoint's backup, and ceilings count every attempt. A content
stop or a gate fail ends the draw. A new draw needs the previous draw ended, a located cause,
and either a new commit touching `src/` or `migrations/` or a different accepted writer; every
draw is counted and the published `DRAW.json` says "draw k of n" (BRIEF.md §6, question 6).

**One iteration**, from the repository root (`--no-sync` keeps uv from re-syncing the shared
environment each draw's runtime imports its dependencies from):

    # 0. the box: check the process list, then take the lock with this lane's prefix
    mkdir runs/box.lock && echo "chapter-one: <who>, <line> draw N" > runs/box.lock/holder
    # 1. a line fixes its brief; draw 1 builds the runtime (no provider call)
    uv run --no-sync python tools/chapter_one.py start --line <line> --brief-file <brief> \\
        --writer <accepted writer>
    # 2. each stage stops at its checkpoint; write GATE-<checkpoint>.md in the draw folder with
    #    one `<id>: PASS|FAIL|PARTIAL <location>` line per item, then record it
    uv run --no-sync python tools/chapter_one.py concept --line <line>
    uv run --no-sync python tools/chapter_one.py gate concept pass --line <line> \\
        --read runs/chapter-one/<line>/draw-1/GATE-concept.md --by coordinator
    uv run --no-sync python tools/chapter_one.py listing --line <line>   # then gate listing
    uv run --no-sync python tools/chapter_one.py seed --line <line>      # then gate world
    uv run --no-sync python tools/chapter_one.py chapter --line <line>   # then gate chapter
    # 3. after a chapter pass
    uv run --no-sync python tools/chapter_one.py publish --line <line>
    uv run --no-sync python tools/chapter_one.py sent --line <line> --how "<where>"
    uv run --no-sync python tools/chapter_one.py read --line <line> --harvest <read file>
    # a stage stopped operationally: write a failure note, then
    uv run --no-sync python tools/chapter_one.py retry <stage> --line <line> --failure <note>
    # the next draw, after a gate fail, a stop, or a recorded read
    uv run --no-sync python tools/chapter_one.py redraw --line <line> \\
        --cause "<where: what the read found>" --fix <40-hex commit> [--writer <other>]
    uv run --no-sync python tools/chapter_one.py status --line <line>

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
import venv
import zipfile
from collections import Counter
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

TOOL = Path(__file__).resolve()
REPO = TOOL.parents[1]
RUNS = REPO / "runs" / "chapter-one"
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
#: One verdict line per item: the id at the start of a line (a list bullet allowed), a colon,
#: then PASS, FAIL or PARTIAL. Ids are a capital and a number or a capital, a hyphen and a word.
VERDICT_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?(?P<item>[A-Z](?:\d+|-[a-z]+)):[ \t]*(?P<verdict>PASS|FAIL|PARTIAL)\b",
    re.MULTILINE,
)
#: Stop reasons a retry may follow; anything else (a ceiling, a refused world, a parked unit,
#: an idle tick, a scene past chapter one) ends the draw, and the remedy is a redraw.
OPERATIONAL_STOPS = (
    "(operational fault)",
    "scheduler failure",
    "could not be bound",
    "consecutive failed ticks",
    "without a step record",
    "runner process ended",
)
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


def fix_problem(commit: str, previous_revision: str) -> str | None:
    """Why `commit` cannot license a redraw after a draw at `previous_revision`, or None."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        return f"{commit!r} is not a full commit id"
    if not is_ancestor(commit, "HEAD"):
        return f"{commit} is not on HEAD"
    if is_ancestor(commit, previous_revision):
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


def resolve_binary(explicit: str | None) -> Path:
    candidate = (
        explicit or os.environ.get("LITHARNESS_CODEX_BINARY", "").strip() or shutil.which("codex")
    )
    if not candidate or not Path(candidate).is_file():
        raise Refusal("no Codex binary: pass --codex-binary PATH")
    return Path(candidate).resolve()


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
        **extra,
    )
    print(f"Prepared {line} draw {n} at {revision[:12]} ({writer}); no provider call.")
    if not settings["on_remote"]:
        print("  note: HEAD is on no remote branch; push it so the draw's revision is backed up.")
    return d


def start(
    line: str,
    brief_file: Path,
    writer: str,
    *,
    binary: str | None = None,
    layout: dict[str, Any] | None = None,
    limits: dict[str, int] | None = None,
) -> Path:
    refuse_live_environment()
    lock()
    root = line_dir(line)
    if draws(line):
        raise Refusal(f"line {line} exists; its next draw is `redraw`, and a new brief a new line")
    brief = Path(brief_file).read_bytes()
    if not brief.strip():
        raise Refusal("the brief is empty")
    fixed = {
        "brief_sha256": hashlib.sha256(brief).hexdigest(),
        "provider": PROVIDER,
        "layout": layout or dict(DEFAULT_LAYOUT),
        "limits": limits or dict(DEFAULT_LIMITS),
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
    return prepare(line, 1, writer=writer, binary=binary, extra={})


def redraw(
    line: str, cause: str, fixes: list[str], writer: str | None, binary: str | None = None
) -> Path:
    """The next draw: the previous one ended, the cause is located, and something changed."""
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
    if not cause.strip():
        raise Refusal("a redraw names its located cause: where, and what the read found")
    problems = [p for commit in fixes if (p := fix_problem(commit, settings["revision"]))]
    if problems:
        raise Refusal("; ".join(problems))
    chosen = writer or str(settings["writer"])
    if not fixes and chosen == settings["writer"]:
        raise Refusal(
            "the same revision and writer draw the same distribution again: a redraw needs a "
            "new commit touching src/ or migrations/ (--fix) or a different accepted writer"
        )
    extra = {
        "after": found[-1],
        "cause": cause,
        "fixes": fixes,
        "writer_changed_from": settings["writer"] if chosen != settings["writer"] else None,
    }
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


def trace_tokens(raw: dict[str, Any]) -> int | None:
    for event in raw.get("events") or []:
        usage = event.get("usage") if event.get("type") == "turn.completed" else None
        if isinstance(usage, dict):
            return int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
    return None


def spend(d: Path) -> dict[str, int]:
    rows = [read(path) for path in traces(d)]
    tokens = [trace_tokens(raw) for raw in rows]
    return {
        "calls": len(rows),
        "tokens": sum(t for t in tokens if t is not None),
        "usage_unknown": sum(t is None for t in tokens),
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
    bridge = [
        json.loads(line) for line in (raw.get("commands_jsonl") or "").splitlines() if line.strip()
    ]
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
        "bridge_runtime": all(
            bool(entry["argv"])
            and entry["argv"][1:3] == ["-m", "litharness"]
            and os.path.normcase(str(entry["argv"][0])) == os.path.normcase(str(python))
            for entry in results
        ),
    }


def transport_summary(d: Path, stage: str, checkpoint: str) -> dict[str, Any]:
    """The stage's calls as production traced them: failed ones listed (production may have
    retried them), and every isolation check that failed on a dispatched call."""
    python = runtime_python(d)
    failed: list[dict[str, str]] = []
    isolation: dict[str, list[str]] = {}
    models: Counter[str] = Counter()
    rows = traces(d, stage=stage, attempts=False)
    tokens = 0
    for path in rows:
        raw = read(path)
        name = path.relative_to(d).as_posix()
        if "failure" in raw or raw.get("returncode") not in (0, None) or "final_text" not in raw:
            failed.append({"trace": name, "failure": str(raw.get("failure") or "")[:300]})
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
        "isolation_failures": isolation,
        "profiles": dict(sorted(models.items())),
        "draw_spend": spend(d),
        "recorded_at": now(),
    }
    write(checkpoint_path(d, checkpoint, "transport"), summary)
    return summary


def write_receipts(d: Path) -> None:
    """`calls/`: a derived copy of each completed trace in the shape the register report reads.
    Rebuilt whole at each checkpoint; the traces under `transport/` stay the record."""
    folder = d / "calls"
    if folder.is_dir():
        for old in folder.glob("*.json"):
            old.unlink()
    for index, path in enumerate(traces(d, attempts=False), start=1):
        raw = read(path)
        if "final_text" not in raw or "failure" in raw:
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


def metadata(d: Path) -> dict[str, Any]:
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.jobs import JobStatus
    from litharness.domain.nodes import NodeKind

    database = d / "book.db"
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


def store_digest(d: Path) -> str | None:
    """One digest over the store a gate read: every state record, and the scenes' ids and
    accepted texts. None before the store exists."""
    from litharness.adapters.sqlite_store import SqliteStore

    database = d / "book.db"
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
    book = metadata(d)
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
    argv: list[str], env: dict[str, str], *, timeout: float | None = None, capture: bool = False
) -> tuple[int | None, str]:
    """A child in the draw's runtime: (its exit code, or None when the wall time ran out;
    its stdout when captured)."""
    process = subprocess.Popen(
        argv,
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        text=True,
        encoding="utf-8",
    )
    try:
        out, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        process.communicate()
        return None, ""
    return process.returncode, out or ""


def child_digest(d: Path) -> str | None:
    code, out = run_child(
        [str(runtime_python(d)), str(TOOL), "_digest", str(d)], environment(d), capture=True
    )
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
        code, _ = run_child(argv, environment(d, key), timeout=remaining)
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
    code, _ = run_child(argv, environment(d))
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
        if outcome is None:
            outcome = bind_checkpoint(d, checkpoint)
    except BaseException as error:
        finish_stage(d, stage, f"scheduler failure: {error!r}")
        raise
    finish_stage(d, stage, outcome)
    summary = transport_summary(d, stage, checkpoint)
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
        print(f"  failed (production may have retried it): {failure['trace']} {failure['failure']}")
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


def gate(line: str, checkpoint: str, result: str, read_file: Path, by: str) -> dict[str, Any]:
    """Record a person's pass or fail at a checkpoint, held to the items the draw snapshotted.

    The register report is filed beside the gate (run now if it has not been) and recorded by
    hash; it decides nothing, and a failure to run it blocks nothing.
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
    summary_path = checkpoint_path(d, checkpoint, "transport")
    summary = read(summary_path) if summary_path.is_file() else {"isolation_failures": {}}
    if result == "pass" and summary["isolation_failures"]:
        raise Refusal(
            "a call ran without its isolation controls, so what the model saw is not "
            f"known: {sorted(summary['isolation_failures'])}"
        )
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
        "transport": {
            "failed": len(summary.get("failed", [])),
            "sha256": sha(summary_path) if summary_path.is_file() else None,
        },
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


def retry(line: str, stage: str, failure: Path, verified_dead_pid: int | None = None) -> int:
    """Run a stage again after an operational stop, keeping the failed attempt.

    The failure note's SHA-256 is recorded before anything moves or dispatches. The failed
    attempt's steps, traces, outputs and store go to `attempts/<stage>-<k>/`; the store is
    restored from the previous checkpoint's backup and checked against its bound digest; the
    stage then runs with the same seed and arguments, and the ceilings count every attempt.
    """
    refuse_live_environment()
    lock()
    if stage not in STAGES:
        raise Refusal(f"unknown stage {stage}")
    d = current(line)
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
        if verified_dead_pid != record.get("runner_pid"):
            raise Refusal(
                f"{stage} is recorded as running under PID {record.get('runner_pid')}; "
                "verify in PowerShell that it has ended, then pass "
                "--verified-dead-pid with that PID"
            )
        reason = "the runner process ended mid-stage"
    elif record["status"] == "stopped":
        reason = str(record.get("reason") or state.get("stop") or "")
    else:
        raise Refusal(f"{stage} is {record['status']}; only a stopped stage is retried")
    if not any(marker in reason for marker in OPERATIONAL_STOPS):
        raise Refusal(
            f"{reason!r} is not an operational stop; the draw has ended, and the "
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
    if record["status"] == "running":
        # Its wall time ends at the last thing it wrote, not at this retry.
        written = [
            p.stat().st_mtime
            for p in (*d.glob(f"steps/{stage}-*.json"), *d.glob(f"transport/{stage}-*/*.json"))
        ]
        ended = max(written, default=datetime.fromisoformat(record["started_at"]).timestamp())
        seconds = ended - datetime.fromisoformat(record["started_at"]).timestamp()
        record = record | {"status": "abandoned", "seconds": round(max(seconds, 0.0), 1)}
    attempt = len(earlier) + 1
    folder = d / "attempts" / f"{stage}-{attempt}"
    ledger(d, "retry", stage=stage, attempt=attempt, stop=reason, failure_note=note)
    for pattern in (
        f"steps/{stage}-*.json",
        f"transport/{stage}-*",
        f"checkpoints/{checkpoint}.*",
        "calls",
        "book.db",
        "book.db-wal",
        "book.db-shm",
        *STAGE_OUTPUTS[stage],
    ):
        move_into(d, pattern, folder)
    index = STAGES.index(stage)
    if index:
        previous = CHECKPOINT_OF[STAGES[index - 1]]
        bound = read(checkpoint_path(d, previous, "binding"))
        if bound["store_backup"]:
            shutil.copy2(d / bound["store_backup"], d / "book.db")
        if child_digest(d) != bound["store_sha256"]:
            raise Refusal(f"the restored store is not the one the {previous} gate read")
    state = progress(d)
    state["attempts"].append(
        {
            "stage": stage,
            "attempt": attempt,
            "record": record,
            "stop": reason,
            "folder": folder.relative_to(d).as_posix(),
        }
    )
    state["retries"][stage] = [*earlier, {"attempt": attempt, "failure_note": note, "at": now()}]
    del state["stages"][stage]
    state.pop("active", None)
    state["stop"] = None
    state["status"] = "ready" if index else "prepared"
    save(d, state)
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
    destination = LIBRARY / shelves[0].name
    if destination.exists():
        raise Refusal(f"{destination} exists; a shelf is never overwritten")
    found = draws(line)
    settings = read(d / "settings.json")
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
    number, count = found[-1], len(found)
    write_new(
        destination / "DRAW.json",
        {
            "line": line,
            "draw": number,
            "of": count,
            "label": f"draw {number} of {count}",
            "earlier": earlier,
            "revision": settings["revision"],
            "writer": settings["writer"],
            "writer_id": settings["writer_id"],
            "dossier_sha256": settings["dossier_sha256"],
            "cause": settings.get("cause"),
            "fixes": settings.get("fixes", []),
            "brief_sha256": settings["brief_sha256"],
            "items_sha256": settings["items_sha256"],
            "gates": {c: g["result"] for c, g in state["gates"].items()},
            "retries": {s: len(r) for s, r in state["retries"].items()},
            "spend": spend(d),
        },
    )
    state["published"] = {
        "path": str(destination),
        "at": now(),
        "label": f"draw {number} of {count}",
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
    found = draws(line)
    rows = []
    for k in found:
        d = draw_dir(line, k)
        state, settings = progress(d), read(d / "settings.json")
        rows.append(
            {
                "draw": f"{k} of {len(found)}",
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
    again = sub.add_parser("redraw", help="the next draw of a line whose last draw ended")
    again.add_argument("--line", required=True)
    again.add_argument("--cause", required=True, help="where the cause was located, and what")
    again.add_argument(
        "--fix", action="append", default=[], help="a 40-hex src/ or migrations/ commit"
    )
    again.add_argument("--writer", help="a different accepted writer")
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
    retry_parser.add_argument("--verified-dead-pid", type=int)
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
            )
        elif args.mode == "redraw":
            redraw(args.line, args.cause, args.fix, args.writer, args.codex_binary)
        elif args.mode == "gate":
            gate(args.line, args.checkpoint, args.result, args.read, args.by)
        elif args.mode == "retry":
            return retry(args.line, args.stage, args.failure, args.verified_dead_pid)
        elif args.mode == "publish":
            publish(args.line)
        elif args.mode == "sent":
            sent(args.line, args.how)
        elif args.mode == "read":
            record_read(args.line, args.harvest)
        elif args.mode == "status":
            status(args.line)
        elif args.mode == "_step":
            child_step(args.draw, args.name)
        elif args.mode == "_bind":
            require_frozen_source(args.draw)
            forbid_provider_calls()
            bind(args.draw, args.name)
        elif args.mode == "_digest":
            require_frozen_source(args.draw)
            print(json.dumps({"store_sha256": store_digest(args.draw)}))
    except Refusal as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
