"""A registered chapter-one draw of the operator's restored standing directions (stage-0 §255).

`PREREG.md` is the registration and `RUNBOOK.md` the procedure. One fresh store is taken
through the production default path on the Codex provider, one stage per command, and every
stage ends at a checkpoint where this runner exits and waits for a person: the concept, the
listing, the seeded world before it is accepted, and chapter one. The person's gate read is
recorded as pass or fail; nothing here decides it.

**What this module does.** It freezes the pinned revision into an archived source and a
runtime of its own, drives the production CLI through that runtime, records every provider
call (health probes included) with admission ceilings checked before each one, records every
CLI step, and writes deterministic observations beside each checkpoint: counts, never
verdicts. It checks in code whether the restored direction texts reached the requests they
are written for (delivery, not compliance).

**What it never does.** It never reads prose for a verdict, never retries or replays a failed
call as an answer, never repairs a refused world, never compares two draws and never chooses
among them. A stage runs once per draw; a stopped draw does not resume; a new draw needs the
previous one shown to the operator and a committed amendment naming a located cause.

    uv run python research/quality-measurement/restored-directions-draw-20260922/run.py plan
    uv run python .../run.py prepare [--draw N]
    uv run python .../run.py concept      # then: gate concept pass|fail --read FILE --by WHO
    uv run python .../run.py listing      # then: gate listing ...
    uv run python .../run.py seed         # then: gate world ...
    uv run python .../run.py chapter      # then: gate chapter ...
    uv run python .../run.py shown --by WHO --how WHERE
    uv run python .../run.py publish      # after a chapter pass only
    uv run python .../run.py close --reason TEXT
    uv run python .../run.py audit

`step`, `preflight`, `bind`, `observe` and `deliver` are the child modes the frozen runtime
runs; none of them but `step` reaches a provider.
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
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs" / "restored-directions-draw-20260922"
LIBRARY = ROOT / "book-library"
ROSTER = ROOT / "runs" / "roster" / "roster.db"
TEST = ROOT / "tests" / "test_restored_directions_draw.py"
LOCK_HOLDER = ROOT / "runs" / "box.lock" / "holder"
LOCK_PREFIX = "restored-directions-draw-20260922:"
CLAIM_ID = "restored-directions-draw-20260922"
CLAIM_STATEMENT = (
    "A registered chapter-one draw series (at most three draws) records whether the restored "
    "operator directions reach the production requests they are written for, end to end on "
    "the default route through Codex, beside a person's pass or fail at four checkpoints. "
    "Delivery is not compliance; one draw is not a rate; no quality, reader or enjoyment "
    "claim is licensed."
)

# ------------------------------------------------------------------ the registration, fixed

#: The author brief: the operator's standing hook direction, chosen by the coordinator. It
#: supplies the premise on purpose (PREREG.md, "Why a hook-template brief").
BRIEF = (
    "System apocalypse. When the System arrives, every person on Earth receives exactly one "
    "Slot for one skill. The protagonist, a man in his twenties, receives a Slot that can "
    "hold as many skills as he can take. Invent the rest."
)
BRIEF_SHA256 = "20fef8c91570140f79f83ec5031e5300fc1515d8745044406127dc984e55a54e"

#: The operator's default genres for new books (commit 446638f, 2026-09-08: portal fantasy,
#: isekai, system apocalypse), as the roster's exact shelf slugs. The roster has no
#: system-apocalypse shelf; the coordinator reads it as progression-fantasy.
DEFAULT_GENRE_SHELVES: tuple[str, ...] = ("isekai", "portal-fantasy", "progression-fantasy")
#: Draw 1's writer is the first accepted, never-cast writer in the recruiter's slate order
#: (`application/recruiter.py` SLATE, then SUPPLEMENTARY) whose shelf is in
#: DEFAULT_GENRE_SHELVES. Uncast in slate order: draycott (dark-fantasy), mabry
#: (supernatural), rowntree (isekai), calloway (mystery), trevelyan (historical-portal-fantasy);
#: the first on a default shelf is rowntree. A `writer` amendment moves exactly one place
#: along, to the default-genre writers already cast, least recently cast first (PREREG.md,
#: "Writer"); those redraw writers are exempt from "never cast".
WRITER_SEQUENCE: tuple[str, ...] = ("rowntree", "barlow", "carver", "hollis", "tanaka", "marsh")
#: Each writer's accepted roster row, read from runs/roster/roster.db through a mode=ro
#: connection on 2026-09-23: the writer id and the SHA-256 of the dossier's UTF-8 bytes, the
#: way `roster_writer` computes it. `hollis` is the accepted progression-fantasy row; a
#: refused historical recruit has the same name and `roster_writer` reads accepted rows only.
WRITERS: dict[str, tuple[str, str]] = {
    "rowntree": ("wtr-43f373dd421c86f46c622872",
                 "b97a225325e883c55c5fe18a04fa6cd48ba6ce638e1d98a48efcf33d9221ffa8"),
    "barlow": ("wtr-cd62e2c28595668f856fc116",
               "6cd7d4f16a2a36b0225412b97d4f639e61d3aeac41f4447c04195cb006274409"),
    "carver": ("wtr-a429d32a0a6d8d45558d2924",
               "546df79bc9d642a6c6ab92af27669d8430500f6df7a4238effe6839c1b1982bb"),
    "hollis": ("wtr-470609b6236faa542fd60d81",
               "9806bf391a73660b03d1eef04fd2b552c14c3ede2b01ba456bc96afba730a7c8"),
    "tanaka": ("wtr-22f6efed98afdb88855326c7",
               "276d8d0a444a4b914d26e54c572b2e60a97bcb3d6d6f7e38d1ff2444c476ea61"),
    "marsh": ("wtr-692590129f954e6d35734bb7",
              "cefbf5bd14cc89130af0dc2c85557f9a1f705ab8b9ea877b8a02d7a79994c4b8"),
}
WRITER_ID, WRITER_DOSSIER_SHA256 = WRITERS[WRITER_SEQUENCE[0]]

PROVIDER = "codex"
BINARY = Path("C:/Users/artem/AppData/Local/OpenAI/Codex/bin/247581e40ee272fb/codex.exe")
#: The adapter's own defaults (`providers/codex_cli.py`); the preflight checks the frozen
#: source still says so. The child inherits no LITHARNESS_ variable, so these stay unset.
MODEL = "gpt-6-astra"
EFFORT = "medium"
UNSET = ("LITHARNESS_MODEL_TIERS", "LITHARNESS_CODEX_EFFORTS", "LITHARNESS_CODEX_MODELS")
#: The pinned revision must carry the restored directions, the tier routing, and every
#: production commit on main when this was registered: the committed plural-decade precision
#: rule, §257's fragment lineage (job input digests move, no request byte does) and §258's
#: Claude working directory (Codex already ran in a temporary directory).
REQUIRED_ANCESTORS = {
    "619c697f664c355a329e68c375d1fd896482ffe9": "stage-0 §255",
    "fd77145e43bfc5d302c821feb21d013c203def8c": "stage-0 §256",
    "1c16fe7a03423c9eeeccbe1fbaa5839eb2eb77c9": "the plural-decade precision rule",
    "60b1d565b7a492ca16653e5a8069b414fa87406b": "stage-0 §257",
    "d14650479972686badbfa6d254b477e6ca613d29": "stage-0 §258",
}
SEED_BITS = 2048

PERSON = "third"
SCENES = 24
CHAPTER_SCENES = 4
ARC_CHAPTERS = 6
CLI_HOLDER = "restored-directions-draw"

MAX_DRAWS = 3
#: Per draw. The 2026-09-12 fresh chapter on Codex (same layout) recorded 19 generation
#: invocations and 401,794 tokens in its store, 33 transport attempts with health probes,
#: about 25 minutes; the coordinator's range is 0.4 to 1M tokens per attempt.
LIMITS = {"calls": 60, "tokens": 2_000_000, "seconds": 7200}
TOTAL_LIMITS = {name: value * MAX_DRAWS for name, value in LIMITS.items()}
MAX_TICKS = 24
MAX_FAILED_TICKS = 3

STAGES: tuple[str, ...] = ("concept", "listing", "seed", "chapter")
CHECKPOINT_OF = {"concept": "concept", "listing": "listing", "seed": "world", "chapter": "chapter"}
STAGE_OF = {checkpoint: stage for stage, checkpoint in CHECKPOINT_OF.items()}
CHECKPOINTS: tuple[str, ...] = tuple(CHECKPOINT_OF.values())
FIXED_STEPS = {
    "concept": ("concept",),
    "listing": ("listing",),
    "seed": ("architect-seed", "world-check"),
}
STEP_ARGV = {
    ("seed", "architect-seed"): ["architect", "seed"],
    ("seed", "world-check"): ["world", "check"],
    ("chapter", "world-accept"): ["world", "accept"],
    ("chapter", "tick"): ["tick"],
}
#: The step that opens each stage; before it runs, the child re-reads the store the previous
#: checkpoint bound.
FIRST_STEP = {stage: (FIXED_STEPS.get(stage) or ("world-accept",))[0] for stage in STAGES}
GATE_RESULTS = ("pass", "fail")
ENDED = ("failed", "stopped")
#: One verdict line per item: the id at the start of a line (a list bullet allowed), a colon,
#: then PASS, FAIL or PARTIAL. A checkpoint passes only when every item is PASS; PARTIAL
#: counts as FAIL (PREREG.md, "The gate").
ITEM_VERDICTS = ("PASS", "FAIL", "PARTIAL")
VERDICT_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?(?P<item>[A-Z]\d+):[ \t]*(?P<verdict>PASS|FAIL|PARTIAL)\b",
    re.MULTILINE,
)

#: What each gate read answers, by id. The read carries exactly one verdict line per id; the
#: runner parses those lines and checks the recorded result against them, nothing else.
CHECKPOINT_ITEMS: dict[str, tuple[tuple[str, str], ...]] = {
    "concept": (
        ("C1", "the exception belongs to one person and works for them in chapter one"),
        ("C2", "the ranks are counted and system.start_rank places the protagonist on them"),
        ("C3", "the threat is physical"),
        ("C4", "no debt, ledger, court or tenancy frame in the premise, the threat or the "
               "system's look"),
    ),
    "listing": (
        ("L1", "the listing promises LitRPG: a system and progression the reader can see"),
        ("L2", "the exception it sells is the one person's, not a shared or issued power"),
        ("L3", "no institution-issued engine and no debt, ledger, court, tenancy or licence "
               "frame"),
        ("L4", "no internal schema word in the title or the listing"),
    ),
    "world": (
        ("W1", "no administrative pressure: the pressure comes from people, danger, distance "
               "and need"),
        ("W2", "the protagonist is placed on the ladder at the concept's start rank, or not "
               "placed for an unranked start"),
        ("W3", "world check reports no snapshot fault and no would-breach"),
    ),
    "chapter": (
        ("H1", "the exception is one person's and works on the page in chapter one"),
        ("H2", "no debt, ledger, licence or administration register"),
        ("H3", "system numbers are present and the status sheet renders"),
        ("H4", "progression is felt in the chapter"),
        ("H5", "the protagonist is in his twenties with a prior life the reader has lived"),
        ("H6", "the chapter's attention goes to the pursuit, not to one procedure"),
        ("H7", "the tone matches the popcorn shelf"),
        ("H8", "third person throughout"),
    ),
}

#: The same ten words the coordinator's 2026-09-22 gate read of *The Last Anchorage*
#: (book-library/the-last-anchorage/GATE.md) counted. That read states the words, not its
#: counting patterns, so these patterns are this runner's and its numbers are not comparable
#: to that read's byte for byte.
ADMIN_LEXICON: dict[str, str] = {
    "ledger": r"\bledgers?\b",
    "debt": r"\bdebt(?:s|ors?)?\b",
    "claim": r"\bclaim(?:s|ed|ing|ants?)?\b",
    "tenancy": r"\btenan(?:cy|cies|ts?)\b",
    "contract": r"\bcontract(?:s|ed|ual)?\b",
    "permission": r"\bpermissions?\b",
    "certify": r"\bcertif(?:y|ies|ied|ying|icates?|ication)\b",
    "inspect": r"\binspect(?:s|ed|ing|ions?|ors?)?\b",
    "compensation": r"\bcompensat(?:e|es|ed|ing|ion)\b",
    "account": r"\baccount(?:s|ed|ing|ants?)?\b",
}
#: The frames the operator's items name (court, tenancy above) and his read-7/8 and §116
#: words, reported separately and never added to the first count.
FRAME_LEXICON: dict[str, str] = {
    "court": r"\bcourts?\b",
    "licence": r"\blicen[cs](?:e|es|ed|ing)\b",
    "permit": r"\bpermits?\b",
    "registry": r"\bregist(?:ry|ries|rars?|ration|ered)\b",
    "clerk": r"\bclerks?\b",
    "fee": r"\bfees?\b",
    "tax": r"\btax(?:es|ed)?\b",
    "owe": r"\bow(?:e|es|ed|ing)\b",
}

#: Literal needles for the restored asks that have no constant of their own; each is one
#: source-line fragment, and the preflight refuses to register if the frozen source lost it.
EXCEPTION_ASK = "use exception for the one power this person has that nobody else in the world"
START_RANK_ASK = "start_rank is the rank the protagonist holds when the book opens"
SEED_STANDS_AT = (
    "Where the concept says the protagonist starts at a rank, declare them stands_at that"
)
PROBE_PROMPT = "Reply with the single word OK."
SHELF_MARKER = ".book.json"
AMENDMENT_SCHEMA = "restored-directions-draw.amendment.v1"
#: What a `fix` amendment's runner-fix commit may change, relative to the repository.
RUNNER_FIX_PATHS = (
    "research/quality-measurement/restored-directions-draw-20260922/run.py",
    "tests/test_restored_directions_draw.py",
)
#: Stop and stage reasons reach evidence.json as these codes and a hash, never as text.
REASON_CODES: tuple[tuple[str, str], ...] = (
    (r"^ceiling:", ""),
    (r"^provider failure", "provider_failure"),
    (r"reported no usage", "no_usage"),
    (r"binary changed", "binary_changed"),
    (r"tools outside the world bridge", "tools_outside_bridge"),
    (r"named model", "named_model"),
    (r"first live request", "preflight_mismatch"),
    (r"previous call failed", "previous_call_failed"),
    (r"store changed", "store_changed"),
    (r"could not be bound", "binding_failed"),
    (r"^scheduler failure", "scheduler_failure"),
    (r"world accept refused", "world_accept_refused"),
    (r"parked or poisoned", "terminal_unit"),
    (r"idle tick", "idle_tick"),
    (r"consecutive failed ticks", "failed_ticks"),
    (r"ticks without", "tick_ceiling"),
    (r"past chapter one", "scene_past_chapter_one"),
    (r"accepted scene changed", "accepted_scene_changed"),
    (r"scene count changed|stood up \d+ scenes", "scene_count"),
    (r"drafted before the chapter stage", "early_draft"),
    (r"wrote no", "missing_artifact"),
    (r"exited \d", "step_exit"),
)


class Refusal(RuntimeError):
    """A registered rule refused the action. Nothing was dispatched."""


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


def digest(value: Any) -> str:
    return sha_text(json.dumps(value, sort_keys=True, ensure_ascii=False))


def read(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path: Path | str, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def write_new(path: Path | str, value: Any) -> None:
    """Exclusive create: a record is never overwritten."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def serial(value: Any) -> Any:
    return json.loads(json.dumps(dataclasses.asdict(value), default=str))


def rel(path: Path | str) -> str:
    return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()


def draw_dir(n: int) -> Path:
    return LOCAL / f"draw-{n}"


def progress_path(n: int) -> Path:
    return draw_dir(n) / "progress.json"


def registration_path(n: int) -> Path:
    return HERE / ("registration.json" if n == 1 else f"registration-draw{n}.json")


def amendment_paths(n: int) -> tuple[Path, Path]:
    return HERE / f"AMENDMENT-{n}.md", HERE / f"amendment-{n}.json"


def checkpoint_path(n: int, checkpoint: str, kind: str = "") -> Path:
    """`checkpoints/<checkpoint>.json` (the observation), or with `kind` the
    `<checkpoint>.binding.json` and `<checkpoint>.observation-failed.json` beside it."""
    return draw_dir(n) / "checkpoints" / f"{checkpoint}{'.' + kind if kind else ''}.json"


def within(path: Path | str, root: Path | str) -> bool:
    """Whether `path` is `root` or under it, compared case-insensitively where the OS is."""
    inner = os.path.normcase(Path(path).resolve())
    outer = os.path.normcase(Path(root).resolve())
    try:
        return os.path.commonpath([inner, outer]) == outer
    except ValueError:  # different drives
        return False


def reason_code(text: str | None) -> str | None:
    """A stop or stage reason as a code for evidence.json; the text itself stays local."""
    if not text:
        return None
    for pattern, code in REASON_CODES:
        if re.search(pattern, text):
            return code or text.split()[0]
    return "other"


def runtime_python(n: int) -> Path:
    runtime = draw_dir(n) / "runtime"
    return runtime / "Scripts" / "python.exe" if os.name == "nt" else runtime / "bin" / "python"


def site_packages(runtime: Path) -> Path:
    if os.name == "nt":
        return runtime / "Lib" / "site-packages"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return runtime / "lib" / version / "site-packages"


def draws() -> list[int]:
    """Prepared draws: a folder counts once `prepare` finished and wrote its progress record."""
    if not LOCAL.is_dir():
        return []
    found = (re.fullmatch(r"draw-(\d+)", path.name) for path in LOCAL.iterdir()
             if (path / "progress.json").is_file())
    return sorted(int(match.group(1)) for match in found if match)


def current_draw() -> int:
    found = draws()
    if not found:
        raise Refusal("no draw is prepared: run `prepare` first")
    return found[-1]


def closed() -> bool:
    return (LOCAL / "closed.json").is_file()


def parse_key(key: str) -> tuple[str, str, int]:
    stage, rest = key.split("-", 1)
    name, iteration = rest.rsplit("-", 1)
    return stage, name, int(iteration)


# ------------------------------------------------------------------------- the box and git


def lock() -> None:
    try:
        holder = LOCK_HOLDER.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise Refusal("runs/box.lock is not held; take it (RUNBOOK) before this step") from error
    if not holder.startswith(LOCK_PREFIX):
        raise Refusal(f"runs/box.lock is held by someone else, not {LOCK_PREFIX}")


def refuse_test_environment() -> None:
    if (
        os.environ.get("LITHARNESS_ENV", "").strip().lower() == "test"
        or os.environ.get("LITHARNESS_FAKE_PAD_CHARS")
    ):
        raise Refusal("a live stage never runs in test mode or on the padded fake provider")


def git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)


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


def committed_bytes(path: Path) -> bytes | None:
    done = git("show", f"HEAD:{rel(path)}")
    return done.stdout if done.returncode == 0 else None


def changed_paths(commit: str) -> list[str]:
    return git_out("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).split()


def registered_files(n: int) -> list[Path]:
    files = [Path(__file__).resolve(), HERE / "PREREG.md", HERE / "RUNBOOK.md", TEST]
    for k in range(2, n + 1):
        files += list(amendment_paths(k))
    return files


def verify_committed(n: int) -> None:
    """Refuse unless the registration is committed as it stands, pushed, and on the revision."""
    paths = [
        *registered_files(n),
        *(registration_path(k) for k in range(1, n + 1)),
        HERE / "claim.json",
    ]
    for path in paths:
        if not path.is_file():
            raise Refusal(f"missing registration file: {path.name}")
        if committed_bytes(path) != path.read_bytes():
            raise Refusal(f"not committed as it stands: {path.name}; commit before any spend")
    if not git_out("branch", "-r", "--contains", "HEAD"):
        raise Refusal("the registration commit is on no remote branch; push it first")
    revision = read(registration_path(n))["revision"]
    if not is_ancestor(revision, "HEAD"):
        raise Refusal(f"the pinned revision {revision} is not an ancestor of HEAD")


def installed_distributions(purelib: Path | str) -> list[str]:
    """`name==version` for every distribution in the shared site-packages the runtime reads."""
    return sorted(
        f"{dist.metadata.get('Name') or ''}=={dist.version}"
        for dist in importlib_metadata.distributions(path=[str(purelib)])
    )


def verify_frozen(n: int) -> dict[str, Any]:
    manifest_path = draw_dir(n) / "manifest.json"
    if sha(manifest_path) != read(registration_path(n))["manifest_sha256"]:
        raise Refusal("the local manifest is not the registered one")
    manifest: dict[str, Any] = read(manifest_path)
    for path, expected in manifest["files"].items():
        if not Path(path).is_file() or sha(path) != expected:
            raise Refusal(f"frozen input changed: {path}")
    # The archived source imports its dependencies from the shared site-packages: the
    # contracts package's files are in `files` above, and every installed version is here.
    dependencies = manifest["runtime"]
    if installed_distributions(dependencies["purelib"]) != dependencies["distributions"]:
        raise Refusal("the shared site-packages the runtime imports from changed since prepare")
    return manifest


def registration_drift(n: int) -> dict[str, str]:
    """Registered files whose bytes differ from draw `n - 1`'s registration: {path: sha now}.

    A redraw may change the runner, the test or the registration only by naming each changed
    file in its amendment (`registration_changes`), so no gate, ceiling or rule moves silently.
    """
    registered = read(registration_path(n - 1))["files"]
    drift: dict[str, str] = {}
    for path in registered_files(n - 1):
        current = sha(path) if path.is_file() else "missing"
        if registered.get(str(path)) != current:
            drift[rel(path)] = current
    return drift


def roster_writer(path: Path, name: str) -> dict[str, str]:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as connection:
        rows = connection.execute(
            "SELECT writer_id, dossier FROM roster_writers WHERE name = ? AND status = 'accepted'",
            (name,),
        ).fetchall()
    if len(rows) != 1:
        raise Refusal(f"{name} is not exactly one accepted writer in {path}")
    return {"writer_id": rows[0][0], "dossier_sha256": sha_text(rows[0][1])}


def copy_roster(destination: Path) -> Path:
    """The installation roster copied through a read-only connection; the draw reads the copy."""
    uri = f"{ROSTER.resolve().as_uri()}?mode=ro"
    with (
        contextlib.closing(sqlite3.connect(uri, uri=True)) as source,
        contextlib.closing(sqlite3.connect(destination)) as target,
    ):
        source.backup(target)
    return destination


def check_writer(n: int) -> None:
    settings = read(draw_dir(n) / "settings.json")
    if not settings.get("roster"):
        return
    row = roster_writer(Path(settings["roster"]), settings["writer"])
    if (row["writer_id"], row["dossier_sha256"]) != (
        settings["writer_id"], settings["dossier_sha256"]
    ):
        raise Refusal(f"the writer {settings['writer']} is not the registered one")


def environment(n: int, *, preflight: bool = False) -> dict[str, str]:
    """The child's environment: no inherited LitHarness, Anthropic or OpenAI setting."""
    d = draw_dir(n)
    settings = read(d / "settings.json")
    root = d / "preflight" if preflight else d
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("LITHARNESS_", "ANTHROPIC_", "OPENAI_"))
        and key.upper() not in {"PYTHONPATH", "PYTHONHOME", "PYTEST_CURRENT_TEST", "VIRTUAL_ENV"}
    }
    env.update(
        LITHARNESS_PROVIDER=PROVIDER,
        LITHARNESS_CODEX_BINARY=str(settings["binary"]["path"]),
        LITHARNESS_DATABASE=str(root / "book.db"),
        LITHARNESS_CODEX_TRACE_DIR=str(root / "transport"),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
    )
    if settings.get("roster"):
        env["LITHARNESS_ROSTER_DATABASE"] = str(settings["roster"])
    if preflight:
        env["LITHARNESS_ENV"] = "test"
    return env


# ------------------------------------------------------------------------ the CLI commands


def base_args(n: int, *, preflight: bool = False) -> list[str]:
    d = draw_dir(n)
    settings = read(d / "settings.json")
    root = d / "preflight" if preflight else d
    args = ["--database", str(root / "book.db")]
    if settings.get("roster"):
        args += ["--roster-database", str(settings["roster"])]
    return [
        *args,
        "--writer", settings["writer"],
        "--holder", CLI_HOLDER,
        "--chapter-scenes", str(CHAPTER_SCENES),
        "--arc-chapters", str(ARC_CHAPTERS),
        "--library", str(root / "library"),
        "--max-invocations-per-day", str(LIMITS["calls"]),
        "--max-tokens-per-day", str(LIMITS["tokens"]),
    ]


def stage_argv(n: int, stage: str, name: str, *, preflight: bool = False) -> list[str]:
    d = draw_dir(n)
    if (stage, name) == ("concept", "concept"):
        out = (d / "preflight" if preflight else d) / "concept"
        return [
            "concept", "--brief-file", str(d / "brief.txt"),
            "--seed", read(d / "seed.json")["label"],
            "--scenes", str(SCENES), "--person", PERSON, "--out", str(out),
        ]
    if (stage, name) == ("listing", "listing"):
        # No title lookup: a web search over an unpublished working title, as on 2026-09-12.
        return [
            "listing", "--concept", str(d / "concept" / "concept.json"),
            "--person", PERSON, "--scenes", str(SCENES), "--no-title-check",
            "--out", str(d / "listing"),
        ]
    if (stage, name) in STEP_ARGV:
        return list(STEP_ARGV[(stage, name)])
    raise ValueError(f"unregistered step {stage}/{name}")


# --------------------------------------------------------------------------------- plan


def plan() -> dict[str, Any]:
    """The registered plan, printed. Reads nothing and writes nothing."""
    body = {
        "brief": BRIEF,
        "brief_sha256": BRIEF_SHA256,
        "writer_sequence": list(WRITER_SEQUENCE),
        "writer_rule": {"slate": "application/recruiter.py SLATE, then SUPPLEMENTARY",
                        "default_genre_shelves": list(DEFAULT_GENRE_SHELVES),
                        "draw_1": {"name": WRITER_SEQUENCE[0], "writer_id": WRITER_ID,
                                   "dossier_sha256": WRITER_DOSSIER_SHA256}},
        "gate_rule": "pass only when every item is PASS; PARTIAL counts as FAIL",
        "provider": {"name": PROVIDER, "binary": str(BINARY), "model": MODEL, "effort": EFFORT},
        "layout": {"scenes": SCENES, "chapter_scenes": CHAPTER_SCENES,
                   "arc_chapters": ARC_CHAPTERS, "person": PERSON},
        "stages": {stage: {"checkpoint": CHECKPOINT_OF[stage],
                           "items": [item for item, _ in CHECKPOINT_ITEMS[CHECKPOINT_OF[stage]]]}
                   for stage in STAGES},
        "limits": {"per_draw": LIMITS, "total": TOTAL_LIMITS, "max_ticks": MAX_TICKS,
                   "max_failed_ticks": MAX_FAILED_TICKS, "max_draws": MAX_DRAWS},
        "lock_prefix": LOCK_PREFIX,
    }
    print(json.dumps(body, ensure_ascii=False, indent=2))
    return body


# ------------------------------------------------------------------------------ prepare


def next_draw_refusal(n: int) -> str | None:
    if closed():
        return "the draw series is closed"
    if not 1 <= n <= MAX_DRAWS:
        return f"at most {MAX_DRAWS} draws are registered"
    existing = draws()
    expected = existing[-1] + 1 if existing else 1
    if n != expected:
        return f"the next draw to prepare is {expected}, not {n}"
    if any(read(progress_path(k)).get("status") == "passed" for k in existing):
        return "a draw passed chapter one; no further draw is registered"
    return None


def commit_problem(commit: Any, previous_revision: str, previous_draw: int) -> str | None:
    """Why `commit` cannot stand in an amendment for the next draw, or None."""
    if not re.fullmatch(r"[0-9a-f]{40}", str(commit)):
        return f"{commit!r} is not a full commit id"
    if not is_ancestor(commit, "HEAD"):
        return f"{commit} is not on HEAD"
    if is_ancestor(commit, previous_revision):
        return f"{commit} was already in draw {previous_draw}; a redraw follows a new fix"
    return None


def amendment_problems(
    n: int, amendment: dict[str, Any], previous_settings: dict[str, Any],
    drift: dict[str, str] | None = None,
) -> list[str]:
    """What keeps a committed amendment from licensing draw `n`; empty when nothing does.

    `drift` is `registration_drift(n)`: every registered file that changed since draw
    `n - 1` was registered must be named in `registration_changes` with its sha256 now and
    the commit that changed it, whatever the amendment's kind.
    """
    problems = []
    if amendment.get("schema") != AMENDMENT_SCHEMA:
        problems.append(f"schema must be {AMENDMENT_SCHEMA}")
    if amendment.get("draw") != n or amendment.get("previous_draw") != n - 1:
        problems.append(f"the amendment must name draw {n} after draw {n - 1}")
    cause = amendment.get("located_cause") or {}
    if cause.get("checkpoint") not in (*CHECKPOINTS, "operational"):
        problems.append("located_cause.checkpoint names a checkpoint or `operational`")
    if not str(cause.get("where") or "").strip():
        problems.append("located_cause.where says where the cause was located")
    revision = previous_settings["revision"]
    listed = {str(entry.get("path") or ""): entry
              for entry in amendment.get("registration_changes") or []}
    for path, current in sorted((drift or {}).items()):
        entry = listed.get(path)
        if entry is None:
            problems.append(f"{path} changed since draw {n - 1} was registered; "
                            "registration_changes names it with its sha256 and commit")
        elif entry.get("sha256") != current:
            problems.append(f"registration_changes gives {path} a sha256 its bytes do not have")
        elif problem := commit_problem(entry.get("commit"), revision, n - 1):
            problems.append(problem)
        elif path not in changed_paths(str(entry["commit"])):
            problems.append(f"{entry['commit']} does not change {path}")
    problems += [f"registration_changes lists {path}, which did not change"
                 for path in sorted(set(listed) - set(drift or {}))]
    kind = amendment.get("kind")
    if kind == "fix":
        production = amendment.get("fix_commits") or []
        runner = amendment.get("runner_fix_commits") or []
        if not production and not runner:
            problems.append("a fix amendment names its fix commits")
        for commit in production:
            if problem := commit_problem(commit, revision, n - 1):
                problems.append(problem)
            elif not any(p.startswith(("src/", "migrations/")) for p in changed_paths(commit)):
                problems.append(f"{commit} changes no production path")
        # A runner fix: the observers and the scheduler are this folder's run.py, frozen
        # per draw, so a defect in them is fixed there and named as such.
        for commit in runner:
            if problem := commit_problem(commit, revision, n - 1):
                problems.append(problem)
                continue
            paths = changed_paths(commit)
            if RUNNER_FIX_PATHS[0] not in paths or not set(paths) <= set(RUNNER_FIX_PATHS):
                problems.append(f"{commit} is not a runner fix: it must change run.py and "
                                "nothing but run.py and its test")
    elif kind == "transport":
        receipt = amendment.get("failed_receipt") or {}
        path = draw_dir(n - 1) / str(receipt.get("path") or "missing")
        if (
            not path.is_file()
            or sha(path) != receipt.get("sha256")
            or read(path).get("status") != "failed"
        ):
            problems.append("a transport amendment cites the previous draw's failed receipt")
    elif kind == "writer":
        previous = previous_settings["writer"]
        index = WRITER_SEQUENCE.index(previous) if previous in WRITER_SEQUENCE else -1
        expected = WRITER_SEQUENCE[index + 1] if 0 <= index < len(WRITER_SEQUENCE) - 1 else None
        if expected is None or amendment.get("writer") != expected:
            problems.append(f"a writer amendment names the next writer in the registered "
                            f"sequence: {expected}")
        elif (amendment.get("writer_id"), amendment.get("dossier_sha256")) != WRITERS[expected]:
            problems.append(f"a writer amendment carries {expected}'s registered writer_id and "
                            "dossier_sha256")
    else:
        problems.append("kind is fix, transport or writer")
    return problems


def expected_writer(n: int, amendment: dict[str, Any] | None,
                    previous_settings: dict[str, Any] | None) -> tuple[str, str, str]:
    """(name, writer_id, dossier_sha256) draw `n` must resolve from its roster copy."""
    if n == 1 or amendment is None or previous_settings is None:
        return WRITER_SEQUENCE[0], WRITER_ID, WRITER_DOSSIER_SHA256
    if amendment["kind"] == "writer":
        return amendment["writer"], amendment["writer_id"], amendment["dossier_sha256"]
    return (previous_settings["writer"], previous_settings["writer_id"],
            previous_settings["dossier_sha256"])


def validate_redraw(n: int) -> dict[str, Any]:
    previous = n - 1
    state = read(progress_path(previous))
    if state["status"] not in ENDED:
        raise Refusal(f"draw {previous} has not ended in a fail or a stop ({state['status']})")
    if not state.get("shown"):
        raise Refusal(f"draw {previous} was not shown to the operator; every draw is shown first")
    for path in amendment_paths(n):
        if not path.is_file() or committed_bytes(path) != path.read_bytes():
            raise Refusal(f"{path.name} must exist and be committed before draw {n}")
    if not amendment_paths(n)[0].read_text(encoding="utf-8").strip():
        raise Refusal(f"AMENDMENT-{n}.md is empty")
    drift = registration_drift(n)
    for path in drift:
        local = ROOT / path
        if not local.is_file() or committed_bytes(local) != local.read_bytes():
            raise Refusal(f"{path} changed since draw {previous} and is not committed as it "
                          "stands")
    amendment: dict[str, Any] = read(amendment_paths(n)[1])
    problems = amendment_problems(n, amendment, read(draw_dir(previous) / "settings.json"), drift)
    if problems:
        raise Refusal("; ".join(problems))
    return amendment


def binary_version(path: Path) -> str:
    """`codex --version`: prints a version and makes no model call."""
    done = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, timeout=60, check=True
    )
    return done.stdout.strip()


def build_runtime(n: int, revision: str) -> tuple[list[Path], dict[str, Any]]:
    """The archived source and a runtime that imports it; returns the files to freeze and the
    runtime record. Dependencies come from the shared site-packages, so the contracts
    package's files are frozen by hash and every installed version is recorded."""
    d = draw_dir(n)
    archive = d / "source.zip"
    done = git("archive", "--format=zip", f"--output={archive}", revision,
               "src", "migrations", "pyproject.toml", "uv.lock")
    if done.returncode:
        raise Refusal(f"git archive failed: {done.stderr.decode('utf-8', errors='replace')}")
    source = d / "source"
    with zipfile.ZipFile(archive) as packed:
        packed.extractall(source)
    runtime = d / "runtime"
    venv.EnvBuilder(with_pip=False).create(runtime)
    # A plain path entry does not process the shared directory's editable-install .pth, so
    # the frozen source is what imports, here and in every world-tool child.
    purelib = Path(sysconfig.get_path("purelib"))
    pth = site_packages(runtime) / "restored-directions-source.pth"
    pth.write_text(f"{source / 'src'}\n{purelib}\n", encoding="utf-8")
    probe = subprocess.run(
        [str(runtime_python(n)), "-c",
         "import json, importlib.metadata as m, litharness, litharness_contracts; "
         "print(json.dumps({'source': litharness.__file__, 'contracts': "
         "litharness_contracts.__file__, "
         "'contracts_version': m.version('litharness-contracts')}))"],
        capture_output=True, text=True, encoding="utf-8", check=True, env=environment(n),
    )
    origin = json.loads(probe.stdout)
    if not Path(origin["source"]).resolve().is_relative_to(source.resolve()):
        raise Refusal("the frozen runtime imported the live checkout")
    contracts = Path(origin["contracts"]).resolve().parent
    if not within(contracts, purelib):
        raise Refusal(f"litharness_contracts imported from {contracts}, not the site-packages")
    origin |= {"purelib": str(purelib), "distributions": installed_distributions(purelib)}
    write(d / "runtime.json", origin)
    files = [archive, pth, runtime / "pyvenv.cfg", runtime_python(n), d / "runtime.json"]
    files += [p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [p for p in contracts.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [p for info in purelib.glob("litharness_contracts-*.dist-info")
              for p in info.rglob("*") if p.is_file()]
    return files, origin


def prepare(n: int = 1) -> dict[str, Any]:
    """Freeze draw `n`: source, runtime, roster copy, brief, seed, binary, offline preflight."""
    lock()
    refuse_test_environment()
    reason = next_draw_refusal(n)
    if reason:
        raise Refusal(reason)
    amendment, previous_settings = None, None
    if n > 1:
        amendment = validate_redraw(n)
        previous_settings = read(draw_dir(n - 1) / "settings.json")
    writer, writer_id, dossier_sha256 = expected_writer(n, amendment, previous_settings)
    revision = git_out("rev-parse", "HEAD")
    for commit, entry in REQUIRED_ANCESTORS.items():
        if not is_ancestor(commit, revision):
            raise Refusal(f"{revision} does not carry {entry} ({commit})")
    dirty = git_out("status", "--porcelain", "--", "src", "migrations", "pyproject.toml",
                    "uv.lock").splitlines()
    d = draw_dir(n)
    if d.exists():
        raise Refusal(f"{d} exists without a finished prepare; nothing was bought, so move it "
                      "aside (it stays the record of that attempt) and prepare again")
    d.mkdir(parents=True)
    roster = copy_roster(d / "roster.db")
    row = roster_writer(roster, writer)
    # Every draw's writer is checked: draw 1 against the registered row, a writer redraw
    # against its amendment's, and a fix or transport redraw against the previous draw's.
    if (row["writer_id"], row["dossier_sha256"]) != (writer_id, dossier_sha256):
        raise Refusal(f"{writer}'s roster row is not the one this registration names "
                      f"({writer_id}, dossier {dossier_sha256[:12]})")
    (d / "brief.txt").write_bytes(BRIEF.encode("utf-8"))
    if sha(d / "brief.txt") != BRIEF_SHA256:
        raise Refusal("the brief does not hash to the registered brief")
    write(d / "seed.json", {"label": str(secrets.randbits(SEED_BITS)), "index": 0})
    stat = BINARY.stat()
    binary = {"path": str(BINARY), "sha256": sha(BINARY), "version": binary_version(BINARY),
              "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    settings = {"draw": n, "revision": revision, "writer": writer, "roster": str(roster),
                **row, "binary": binary}
    write(d / "settings.json", settings)
    files, runtime = build_runtime(n, revision)
    subprocess.run([str(runtime_python(n)), str(Path(__file__).resolve()), "preflight", str(n)],
                   cwd=ROOT, env=environment(n, preflight=True), check=True)
    preflight_record = read(d / "preflight.json")
    files += [*registered_files(n), d / "brief.txt", d / "seed.json", d / "settings.json",
              d / "preflight.json", BINARY]
    manifest = {
        "schema": "restored-directions-draw.registration.v1",
        "draw": n,
        "revision": revision,
        "dirty_paths_left_out_of_the_archive": dirty,
        "runtime": {"purelib": runtime["purelib"], "distributions": runtime["distributions"],
                    "contracts_version": runtime["contracts_version"]},
        "provider": {"name": PROVIDER, "binary": {k: binary[k] for k in ("path", "sha256",
                     "version")}, "model": MODEL, "effort": EFFORT, "unset": list(UNSET)},
        "brief": {"text": BRIEF, "sha256": BRIEF_SHA256},
        "writer": {"name": writer, "writer_id": row["writer_id"],
                   "dossier_sha256": row["dossier_sha256"], "roster_copy_sha256": sha(roster),
                   "rule": {"slate": "application/recruiter.py SLATE, then SUPPLEMENTARY",
                            "default_genre_shelves": list(DEFAULT_GENRE_SHELVES),
                            "sequence": list(WRITER_SEQUENCE)}},
        "layout": {"scenes": SCENES, "chapter_scenes": CHAPTER_SCENES,
                   "arc_chapters": ARC_CHAPTERS, "person": PERSON, "target_words": "CLI default",
                   "planning_material": False, "title_check": False},
        "disclosed_deviations": [
            "listing --no-title-check",
            "concept --person third (the README recipe passes no person to concept)",
            f"--max-invocations-per-day {LIMITS['calls']} --max-tokens-per-day "
            f"{LIMITS['tokens']} on every verb (CLI defaults 500 and 5,000,000)",
        ],
        "limits": {"per_draw": LIMITS, "total": TOTAL_LIMITS, "max_ticks": MAX_TICKS,
                   "max_failed_ticks": MAX_FAILED_TICKS, "max_draws": MAX_DRAWS,
                   "cli_daily": {"invocations": LIMITS["calls"], "tokens": LIMITS["tokens"]}},
        "stages": {stage: {"checkpoint": CHECKPOINT_OF[stage],
                           "steps": list(FIXED_STEPS.get(stage, ("world-accept", "tick")))}
                   for stage in STAGES},
        "checkpoint_items": {k: [list(item) for item in v] for k, v in CHECKPOINT_ITEMS.items()},
        "lexicons": {"admin": ADMIN_LEXICON, "frame": FRAME_LEXICON},
        "preflight": {k: v for k, v in preflight_record.items() if k != "request"},
        "seed_sha256": sha(d / "seed.json"),
        "amendment": amendment,
        "lock_prefix": LOCK_PREFIX,
        "files": {str(path): sha(path) for path in files},
    }
    write(d / "manifest.json", manifest)
    write(registration_path(n), manifest | {"manifest_sha256": sha(d / "manifest.json")})
    write(progress_path(n), {"draw": n, "status": "registered", "registered_at": now(),
                             "calls": [], "stages": {}, "gates": {}, "stop": None})
    claim("registered")
    print(f"Prepared draw {n} at {revision}: frozen source, runtime, roster copy and offline "
          "preflight; no provider call. Commit and push the registration before `concept`.")
    return manifest


# ------------------------------------------------------------------------------ admission


def draw_seconds(state: dict[str, Any], at: str) -> float:
    total = 0.0
    for record in state.get("stages", {}).values():
        if record.get("status") == "running":
            total += elapsed(record["started_at"], at)
        else:
            total += float(record.get("seconds") or 0.0)
    return total


def admission(n: int, state: dict[str, Any], at: str) -> str | None:
    """Before a stage and before every call: the reason nothing more may be spent, or None."""
    calls = state["calls"]
    if state.get("stop"):
        return f"draw {n} stopped: {state['stop']}"
    if any(call["status"] != "completed" for call in calls):
        return "a previous call failed or never finished; its usage is unknown"
    used = {"calls": len(calls), "tokens": sum(c["tokens"] for c in calls),
            "seconds": draw_seconds(state, at)}
    for name, limit in LIMITS.items():
        if used[name] >= limit:
            return f"ceiling:{name}"
    for k in draws():
        if k == n:
            continue
        other = read(progress_path(k))
        used["calls"] += len(other["calls"])
        used["tokens"] += sum(c["tokens"] for c in other["calls"])
        used["seconds"] += draw_seconds(other, at)
    for name, limit in TOTAL_LIMITS.items():
        if used[name] >= limit:
            return f"ceiling:total_{name}"
    return None


def request_refusal(request: Any) -> str | None:
    tools = tuple(request.allowed_tools or ())
    if tools and not all(tool.startswith("Bash(litharness world ") for tool in tools):
        return f"a request asked for tools outside the world bridge: {list(tools)}"
    if request.model is not None:
        return f"a request named model {request.model!r}; every role is registered strong"
    return None


def install_recorder(n: int, stage: str, provider_class: Any = None) -> Callable[..., Any]:
    """Wrap the provider so every call is admitted, receipted and chained; returns the original.

    A failed call is kept as failed with its usage unknown and stops the draw: it is never
    retried here and never replayed as an answer.
    """
    from litharness.providers.base import ProviderUnavailable

    if provider_class is None:
        from litharness.providers.codex_cli import CodexCliProvider as provider_class
    original = provider_class.complete
    d = draw_dir(n)

    def refuse(state: dict[str, Any], reason: str) -> None:
        state["stop"] = state.get("stop") or reason
        write(progress_path(n), state)
        raise ProviderUnavailable(reason)

    def recorded(provider: Any, request: Any) -> Any:
        lock()
        state = read(progress_path(n))
        at = now()
        if getattr(provider, "bills", False):
            registered = read(d / "settings.json")["binary"]
            current = Path(registered["path"]).stat()
            if (current.st_size, current.st_mtime_ns) != (registered["size"],
                                                           registered["mtime_ns"]):
                refuse(state, "the provider binary changed")
        serialized = serial(request)
        probe = is_probe(serialized)
        reason = admission(n, state, at) or request_refusal(request)
        # The first live invention request must be the one the offline preflight registered
        # (PREREG.md, "Invention seed"): checked here, before it is dispatched.
        if (not reason and stage == "concept" and not probe
                and all(call.get("probe") for call in state["calls"])
                and digest(serialized) != read(d / "preflight.json")["request_sha256"]):
            reason = "the first live request is not the one the offline preflight registered"
        if reason:
            refuse(state, reason)
        number = len(state["calls"]) + 1
        path = d / "calls" / f"{number:04d}-{stage}.json"
        previous = d / state["calls"][-1]["path"] if state["calls"] else None
        row: dict[str, Any] = {
            "number": number, "draw": n, "stage": stage, "provider": provider.name,
            "profile": request.profile, "started_at": at, "request": serialized,
            "status": "started", "previous_receipt_sha256": sha(previous) if previous else None,
        }
        write_new(path, row)
        meta = {"number": number, "stage": stage, "profile": request.profile, "probe": probe,
                "status": "started", "tokens": 0, "path": path.relative_to(d).as_posix()}
        state["calls"].append(meta)
        write(progress_path(n), state)
        print(f"CALL {number} {stage} {request.profile}", flush=True)
        try:
            result = original(provider, request)
            row.update(status="completed", finished_at=now(), result=serial(result))
            meta.update(status="completed", tokens=int(result.usage.total))
            if getattr(provider, "bills", False) and result.usage.total <= 0:
                state["stop"] = state.get("stop") or (
                    "a call reported no usage; the ceiling cannot be read")
        except BaseException as error:
            row.update(status="failed", finished_at=now(), error=repr(error),
                       raw=getattr(provider, "last_attempt", None), usage_unknown=True)
            meta["status"] = "failed"
            state["stop"] = state.get("stop") or (
                "provider failure; usage unknown; the receipt is kept and never replayed")
            raise
        finally:
            write(path, row)
            write(progress_path(n), state)
        return result

    provider_class.complete = recorded
    return original


def forbid_provider_calls() -> None:
    from litharness.providers.codex_cli import CodexCliProvider
    from litharness.providers.fake import FakeProvider

    def refuse(provider: Any, request: Any) -> Any:
        raise RuntimeError("no provider call is made while observing")

    CodexCliProvider.complete = refuse
    FakeProvider.complete = refuse


# ---------------------------------------------------------------------- the child: steps


def metadata(n: int) -> dict[str, Any]:
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.jobs import JobStatus
    from litharness.domain.nodes import NodeKind

    empty: dict[str, Any] = {"exists": False, "accepted": 0, "total": 0, "pending": 0,
                             "terminal": 0, "exceptions": 0, "scene_ids": [],
                             "scene_hashes": {}, "head": None, "jobs": {}}
    database = draw_dir(n) / "book.db"
    if not database.exists():
        return empty
    with SqliteStore.open_read_only(database) as store:
        branches = store.branches()
        head = store.head(branches[0][0], branches[0][1]) if branches else None
        scenes = ([node for node in head.in_reading_order() if node.kind is NodeKind.SCENE]
                  if head else [])
        jobs = {status.value: len(store.jobs_by_status(status, limit=10000))
                for status in JobStatus}
        exceptions = len(store.open_exceptions())
    drafted = {node.logical_id: sha_text(node.content)
               for node in scenes if (node.content or "").strip()}
    return {
        "exists": True,
        "accepted": len(drafted),
        "total": len(scenes),
        "scene_ids": [node.logical_id for node in scenes],
        "scene_hashes": drafted,
        "head": head.revision_id if head else None,
        "jobs": jobs,
        "pending": sum(jobs.get(key, 0) for key in ("queued", "pending", "failed", "running")),
        "terminal": sum(jobs.get(key, 0) for key in ("parked", "poisoned")),
        "exceptions": exceptions,
    }


def execute_step(n: int, key: str, *, provider_class: Any = None) -> dict[str, Any]:
    """Run one admitted CLI step in this process and write its record."""
    import litharness
    from litharness import cli

    state = read(progress_path(n))
    if state.get("active") != key:
        raise Refusal("this step was not admitted by the registered scheduler")
    stage, name, _ = parse_key(key)
    install_recorder(n, stage, provider_class)
    arguments = base_args(n) + stage_argv(n, stage, name)
    record: dict[str, Any] = {"key": key, "stage": stage, "name": name, "arguments": arguments,
                              "source": str(litharness.__file__), "started_at": now(),
                              "before": metadata(n)}
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = cli.main(arguments)
        except BaseException as error:
            code = 2
            record["exception"] = repr(error)
    record.update(finished_at=now(), returncode=code, stdout=stdout.getvalue(),
                  stderr=stderr.getvalue(), after=metadata(n))
    write_new(draw_dir(n) / "steps" / f"{key}.json", record)
    return record


def require_frozen_source(n: int) -> None:
    """A child mode imports the draw's archived source, never the live checkout."""
    import litharness

    source = (draw_dir(n) / "source").resolve()
    if not Path(str(litharness.__file__)).resolve().is_relative_to(source):
        raise Refusal("this child imported an unfrozen source")


def store_digest(n: int) -> str | None:
    """One digest over the store a gate read: every state record, and the scenes' ids and
    accepted texts. None before the store exists."""
    from litharness.adapters.sqlite_store import SqliteStore

    database = draw_dir(n) / "book.db"
    if not database.exists():
        return None
    with SqliteStore.open_read_only(database) as store:
        branches = store.branches()
        records = store.state_records(branches[0][0], branches[0][1]) if branches else []
    rows = sorted(json.dumps(serial(record), sort_keys=True, ensure_ascii=False)
                  for record in records)
    book = metadata(n)
    return digest({"records": rows, "scene_ids": book["scene_ids"],
                   "scene_hashes": book["scene_hashes"]})


def bound_store_refusal(n: int, key: str) -> str | None:
    """Before a stage's first step: the reason its store is not the one the previous
    checkpoint bound, or None. `world accept` then acts only on the world the W gate read."""
    stage, name, iteration = parse_key(key)
    index = STAGES.index(stage)
    if not index or name != FIRST_STEP[stage] or iteration != 1:
        return None
    checkpoint = CHECKPOINT_OF[STAGES[index - 1]]
    bound = read(checkpoint_path(n, checkpoint, "binding")).get("store_sha256")
    if bound is not None and store_digest(n) != bound:
        return (f"the store changed after the {checkpoint} checkpoint was bound; the gate did "
                "not read this store")
    return None


def step(n: int, key: str) -> None:
    refuse_test_environment()
    lock()
    verify_frozen(n)
    require_frozen_source(n)
    reason = bound_store_refusal(n, key)
    if reason:
        state = read(progress_path(n))
        state["stop"] = state.get("stop") or reason
        write(progress_path(n), state)
        raise Refusal(reason)
    record = execute_step(n, key)
    print(json.dumps({"step": key, "returncode": record["returncode"],
                      "accepted": record["after"]["accepted"]}))


def concept_needles(n: int | None) -> dict[str, str]:
    """What the outline must carry of this book's own concept: the first use the placement
    rule places, and the start rank in the words the projection writes ("rank 3 of 12",
    "unranked"). Empty before the concept exists."""
    from litharness.application import concept

    path = draw_dir(n) / "concept" / "concept.json" if n is not None else None
    if path is None or not path.is_file():
        return {}
    projected = concept.Concept.from_text(path.read_text(encoding="utf-8")).for_outline()
    needles = {}
    if str(projected.get("first_use") or "").strip():
        needles["concept_first_use"] = str(projected["first_use"])
    label = (projected.get("horizon") or {}).get("start_rank")
    if label:
        needles["start_rank_label"] = str(label)
    return needles


def delivery_table(n: int | None = None) -> dict[str, dict[str, Any]]:
    """Which request profile each restored direction rides, and the exact text it must carry.

    With a draw, the outline row also needs that draw's concept's first use and start-rank
    label: the placement rule without the first use it places delivers nothing.
    """
    from litharness.application import concept, discovery, outline, world_agent

    for module, literal in ((concept, EXCEPTION_ASK), (concept, START_RANK_ASK),
                            (world_agent, SEED_STANDS_AT)):
        if literal not in Path(str(module.__file__)).read_text(encoding="utf-8"):
            raise Refusal(f"{module.__name__} no longer carries {literal!r}; the table is stale")
    return {
        "discovery": {"stage": "concept", "profile": discovery.PROFILE,
                      "needles": {"direction": discovery.DIRECTION,
                                  "world_direction": discovery.WORLD_DIRECTION}},
        "development": {"stage": "concept", "profile": concept.DISCOVERY_CONCEPT_PROFILE,
                        "needles": {"world_direction": discovery.WORLD_DIRECTION,
                                    "exception_ask": EXCEPTION_ASK,
                                    "start_rank_ask": START_RANK_ASK}},
        "seed": {"stage": "seed", "profile": world_agent.SEED_PROFILE,
                 "needles": {"lived_world": discovery.LIVED_WORLD,
                             "stands_at": SEED_STANDS_AT}},
        "outline": {"stage": "chapter", "profile": outline.CONCEPT_PROFILE,
                    "needles": {"first_use_rule": concept.FIRST_USE_RULE,
                                "early_magic_rule": concept.EARLY_MAGIC_RULE,
                                **concept_needles(n)}},
    }


def public_table(table: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {name: {"stage": entry["stage"], "profile": entry["profile"],
                   "needles": {k: sha_text(v) for k, v in entry["needles"].items()}}
            for name, entry in table.items()}


def carries(request: dict[str, Any], needle: str) -> bool:
    forms = {needle, json.dumps(needle, ensure_ascii=False)[1:-1], json.dumps(needle)[1:-1]}
    texts = (request.get("prompt") or "", request.get("system") or "")
    return any(form in text for form in forms for text in texts)


def delivery_result(rows: Iterable[dict[str, Any]], entry: dict[str, Any]) -> dict[str, Any]:
    matching = [row["request"] for row in rows if row["request"].get("profile") == entry["profile"]]
    carrying = {name: sum(carries(request, text) for request in matching)
                for name, text in entry["needles"].items()}
    result: dict[str, Any] = {
        "profile": entry["profile"], "requests": len(matching), "carrying": carrying,
        "delivered": bool(matching) and all(count == len(matching) for count in carrying.values()),
    }
    if entry.get("needles", {}).get("start_rank_ask"):
        requires = [
            "start_rank" in ((((request.get("schema") or {}).get("properties") or {})
                              .get("system") or {}).get("required") or [])
            for request in matching
        ]
        result["schema_requires_start_rank"] = bool(requires) and all(requires)
        result["delivered"] = result["delivered"] and result["schema_requires_start_rank"]
    return result


def preflight(n: int) -> None:
    """Offline: the concept command reaches one discovery request carrying the directions."""
    from litharness import cli
    from litharness.domain import invention
    from litharness.providers.codex_cli import CodexCliProvider
    from litharness.providers.routing import ModelRouting

    if os.environ.get("LITHARNESS_ENV", "").strip().lower() != "test":
        raise Refusal("the preflight runs with billing disabled")
    problems = []
    if invention.DEFAULT_VERSION != invention.PREFIX_VERSION or invention.PREFIX_BITS != SEED_BITS:
        problems.append("the production invention seed is not the registered prefix seed")
    adapter = CodexCliProvider()
    if (adapter.model, adapter.reasoning_effort) != (MODEL, EFFORT):
        problems.append(f"the adapter defaults are {adapter.model}/{adapter.reasoning_effort}")
    if ModelRouting.from_environ(PROVIDER, {}).role_tiers:
        problems.append("the shipped routing is not every role strong")
    table = delivery_table()
    reached: list[Any] = []
    original = cli._completion_call

    def boundary(request: Any, **_: Any) -> tuple[None, str]:
        reached.append(serial(request))
        return None, "registered offline boundary"

    (draw_dir(n) / "preflight").mkdir(parents=True, exist_ok=True)
    cli._completion_call = boundary
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(base_args(n, preflight=True)
                            + stage_argv(n, "concept", "concept", preflight=True))
    finally:
        cli._completion_call = original
    request = reached[0] if len(reached) == 1 else None
    if code != 2 or request is None:
        problems.append(f"concept did not stop at one request (exit {code}, {len(reached)})")
    else:
        if request["profile"] != table["discovery"]["profile"]:
            problems.append(f"the first request is {request['profile']}")
        if request.get("allowed_tools") or request.get("model") is not None:
            problems.append("the invention request carries tools or a model")
        if not carries(request, BRIEF):
            problems.append("the invention request does not carry the brief")
        problems += [f"the invention request lacks {name}"
                     for name, text in table["discovery"]["needles"].items()
                     if not carries(request, text)]
    if problems:
        raise Refusal("preflight: " + "; ".join(problems))
    write(draw_dir(n) / "preflight.json", {
        "provider_calls": 0, "request": request, "request_sha256": digest(request),
        "profile": request["profile"], "delivery_table": public_table(table),
        "adapter": {"model": MODEL, "effort": EFFORT},
        "routing": {"role_tiers": [], "strong": "adapter default"},
        "invention": {"version": invention.DEFAULT_VERSION, "bits": SEED_BITS},
    })


# -------------------------------------------------------------------- inert observations


def lexicon_counts(text: str, lexicon: dict[str, str]) -> dict[str, int]:
    return {name: len(re.findall(pattern, text, flags=re.IGNORECASE))
            for name, pattern in lexicon.items()}


def text_observations(text: str) -> dict[str, Any]:
    """Counts over a text. They are printed beside a gate and decide nothing."""
    words = len(text.split())
    numbers = re.findall(r"\d+", text)

    def block(lexicon: dict[str, str]) -> dict[str, Any]:
        counts = lexicon_counts(text, lexicon)
        total = sum(counts.values())
        return {"counts": {k: v for k, v in counts.items() if v}, "total": total,
                "per_1k_words": round(1000.0 * total / words, 2) if words else 0.0}

    return {"words": words, "admin_lexicon": block(ADMIN_LEXICON),
            "frame_lexicon": block(FRAME_LEXICON), "numbers": len(numbers),
            "digit_characters": sum(len(number) for number in numbers)}


def prose_observations(text: str) -> dict[str, Any]:
    from litharness.application.statusline import parse_status_line
    from litharness.domain import tells

    lines = [parse_status_line(line.strip()) for line in text.splitlines()]
    status = [line for line in lines if line is not None]
    located = Counter(item.family for item in tells.locate(text))
    return text_observations(text) | {
        "status_lines": len(status),
        "status_cells": sum(len(line.cells) for line in status),
        "tells": {"located": dict(located),
                  "per_1k_words": {k: round(v, 2) for k, v in tells.density(text).items()},
                  "longest_sentence_words": tells.longest_sentence(text)},
    }


def receipts(n: int) -> list[dict[str, Any]]:
    return [read(path) for path in sorted((draw_dir(n) / "calls").glob("*.json"))]


def is_probe(request: dict[str, Any]) -> bool:
    return request.get("profile") == "default" and request.get("prompt") == PROBE_PROMPT


def artifacts(n: int, paths: Iterable[Path]) -> dict[str, str]:
    d = draw_dir(n)
    return {path.relative_to(d).as_posix(): sha(path) for path in sorted(paths) if path.is_file()}


def json_in(output: str) -> Any:
    start = output.find("{")
    if start < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(output[start:])[0]
    except ValueError:
        return None


def view(n: int, name: str, arguments: list[str]) -> Path:
    from litharness import cli

    output = io.StringIO()
    record: dict[str, Any] = {"arguments": arguments}
    # A view that refuses or raises is recorded as it failed; an observation never stops on it.
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = cli.main(base_args(n) + arguments)
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else 2
            record["exception"] = "SystemExit"
        except Exception as error:  # recorded, never raised past a view
            code = 2
            record["exception"] = type(error).__name__
    path = draw_dir(n) / "views" / f"{name}.json"
    write(path, record | {"returncode": code, "output": output.getvalue()})
    return path


def string_leaves(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in string_leaves(item)]
    if isinstance(value, list | tuple):
        return [leaf for item in value for leaf in string_leaves(item)]
    return []


def observe_concept(n: int, rows: list[dict[str, Any]], table: dict[str, Any]) -> dict[str, Any]:
    from litharness.application import discovery, precision

    folder = draw_dir(n) / "concept"
    concept = read(folder / "concept.json")
    system = concept.get("system") or {}
    threat = concept.get("threat") or {}
    treatment = concept.get("discovery") or {}
    fields = {
        "person_before": concept.get("person_before"), "exception": concept.get("exception"),
        "want": concept.get("want"), "first_use": concept.get("first_use"),
        "threat.what": threat.get("what"), "threat.first_reach": threat.get("first_reach"),
        **{f"system.{key}": system.get(key)
           for key in ("name", "manner", "look", "pays", "strongest_known")},
        **{f"discovery.{key}": treatment.get(key)
           for key in ("experience_brief", "world", "opening", "growth")},
    }
    surfaces = ("person_before", "exception", "want", "threat.what", "system.look")
    steps, start = system.get("steps"), system.get("start_rank")
    developed = [row for row in rows if row["request"].get("profile")
                 == table["development"]["profile"] and row["status"] == "completed"]
    parsed = ((developed[-1].get("result") or {}).get("parsed") or {}) if developed else {}
    before = parsed.get("system") or {}
    observations = {
        "author_brief_retained": concept.get("author_brief") == BRIEF,
        "discovery_version": treatment.get("version"),
        "discovery_version_is_current": treatment.get("version") == discovery.VERSION,
        "system_steps": steps,
        "start_rank_present": "start_rank" in system,
        "start_rank": start,
        "start_rank_in_range": (isinstance(start, int) and not isinstance(start, bool)
                                and isinstance(steps, int) and 0 <= start < steps),
        "strongest_known_carries_a_number": bool(re.search(r"\d",
                                                           str(system.get("strongest_known")))),
        "open_questions": len(concept.get("debts") or []),
        "second_system": concept.get("second_system") is not None,
        "precision_calls": sum(row["request"].get("profile") == precision.PROFILE
                               for row in rows),
        "precision_kept": {key: before.get(key) == system.get(key)
                           for key in ("steps", "start_rank", "strongest_known")}
        if before else None,
        "fields": {name: text_observations(str(text or "")) for name, text in fields.items()},
        "premise_threat_look": text_observations("\n".join(str(fields[k] or "")
                                                           for k in surfaces)),
    }
    return {
        "observations": observations,
        "delivery": {name: delivery_result(rows, table[name])
                     for name in ("discovery", "development")},
        "artifacts": artifacts(n, folder.rglob("*")),
    }


def observe_listing(n: int, rows: list[dict[str, Any]], table: dict[str, Any]) -> dict[str, Any]:
    from litharness.domain import schema_words

    folder = draw_dir(n) / "listing"
    title = (folder / "title.txt").read_text(encoding="utf-8").strip()
    listing = (folder / "listing.txt").read_text(encoding="utf-8")
    book = metadata(n)
    # The listing loop's browsing-reader answers are model verdicts; they are not read here.
    observations = {
        "title_words": len(title.split()),
        "schema_words_in_title": list(schema_words.taken_as_a_name(title)),
        "schema_words_in_listing": list(schema_words.named_in(listing)),
        "listing": prose_observations(listing),
        "book_scenes": book["total"],
        "book_stood_up": book["total"] == SCENES and not book["accepted"],
    }
    return {"observations": observations, "delivery": {},
            "artifacts": artifacts(n, folder.rglob("*"))}


def opening_ranks(records: list[Any], protagonists: tuple[str, ...]) -> list[int | None]:
    """The rank each un-keyed `stands_at` of a protagonist declares, counted from one.

    Read off the records as declared, proposals included: `world_brief.ladder_for` reads
    canon only, and before `world accept` nothing is canon. None for a standing whose rung is
    on no one chain.
    """
    from litharness.domain import state, worlds

    ranks: list[int | None] = []
    for record in records:
        if (record.predicate != worlds.STANDS_AT_PREDICATE or record.subject not in protagonists
                or not record.object_ref or state.order_key_of(record)):
            continue
        criterion = (str(record.value or "").strip()
                     or worlds.criterion_of_rung(records, record.object_ref))
        ranks.append(worlds.rung_index(records, criterion, record.object_ref)
                     if criterion else None)
    return ranks


def observe_world(n: int, rows: list[dict[str, Any]], table: dict[str, Any]) -> dict[str, Any]:
    import litharness_contracts as lc

    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import integrity, schema_words, worlds

    d = draw_dir(n)
    with SqliteStore.open_read_only(d / "book.db") as store:
        book, branch, _ = store.branches()[0]
        written = store.state_records(book, branch)
        # What the world says, as the world views and `world accept` read it: a proposal a
        # later declaration of its slot replaced is not part of it.
        records = list(integrity.in_force(written,
                                          declared_at=store.state_record_times(book, branch)))
    check_path = d / "steps" / "seed-world-check-1.json"
    check = read(check_path)
    payload = json_in(check["stdout"]) or {}
    (d / "views").mkdir(parents=True, exist_ok=True)
    write(d / "views" / "world-check.json", {"returncode": check["returncode"],
                                             "payload": payload})
    shown = view(n, "world-show", ["world", "show", "--json"])
    ladders = view(n, "world-ladders", ["world", "ladders", "--json"])
    protagonists = worlds.entities_with_role(records, "protagonist")
    stands = [r for r in records
              if r.predicate == worlds.STANDS_AT_PREDICATE and r.subject in protagonists]
    ranks = opening_ranks(records, protagonists)
    declared = ranks[0] if len(ranks) == 1 else None
    start = (read(d / "concept" / "concept.json").get("system") or {}).get("start_rank")
    roles = Counter(role for tags in worlds.entity_roles(records).values() for role in tags)
    matches = None if start is None else (not stands if start == 0 else declared == start)
    texts = [leaf for record in records for leaf in string_leaves(record.value)]
    observations = {
        "records_written": len(written),
        "records": len(records),
        "replaced": len(written) - len(records),
        "proposed": sum(r.authority is not lc.StateAuthority.ACCEPTED_CANON for r in records),
        "protagonists": len(protagonists),
        "protagonist_stands_at": len(stands),
        "protagonist_opening_standings": len(ranks),
        "ladder_found": declared is not None,
        "declared_start_rank": declared,
        "concept_start_rank": start,
        "declared_start_matches_concept": matches,
        "roles": dict(roles),
        "schema_word_complaints": len(schema_words.world_complaints(records)),
        "world_text": text_observations("\n".join(texts)),
        "world_check": {"returncode": check["returncode"], "ok": payload.get("ok"),
                        **{key: len(value) for key, value in payload.items()
                           if isinstance(value, list)}},
    }
    return {"observations": observations, "delivery": {"seed": delivery_result(rows,
                                                                               table["seed"])},
            "artifacts": artifacts(n, [d / "views" / "world-check.json", shown, ladders])}


def promise_lines(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    from litharness.domain.promises import PROMISE_LINE_PREFIX

    heading = "Open threads the book has not yet resolved:"
    found: dict[str, dict[str, int]] = {}
    for row in rows:
        request = row["request"]
        if is_probe(request):
            continue
        text = f"{request.get('prompt') or ''}\n{request.get('system') or ''}"
        counts = found.setdefault(request.get("profile") or "default",
                                  {"requests": 0, "threads_heading": 0, "open_prefix": 0,
                                   "old_owes": 0})
        counts["requests"] += 1
        counts["threads_heading"] += text.count(heading)
        counts["open_prefix"] += text.count(PROMISE_LINE_PREFIX)
        counts["old_owes"] += len(re.findall(r"\bowes:", text))
    return found


def observe_chapter(n: int, rows: list[dict[str, Any]], table: dict[str, Any]) -> dict[str, Any]:
    import litharness_contracts as lc

    from litharness.domain import characters, names, schema_words

    # The reading copy and the library export are the binding's (`bind`), not observations.
    views = [view(n, "status", ["status", "--json"]), view(n, "verify", ["verify", "--json"]),
             view(n, "plans", ["plans", "--json"])]
    views += [view(n, f"why-{k}", ["why", "--scene", str(k), "--json"])
              for k in range(1, CHAPTER_SCENES + 1)]
    texts, records = chapter_texts(n)
    chapter = "\n\n".join(texts)
    canon = [r for r in records if r.authority is lc.StateAuthority.ACCEPTED_CANON]
    people = characters.cast(canon)
    given = [names.display_name(canon, person.subject).split()[:1] for person in people]
    named = sum(bool(g) and bool(re.search(rf"\b{re.escape(g[0])}\b", chapter)) for g in given)
    shelves = library_shelves(n)
    observations = {
        "scenes": len(texts),
        "scene_words": [len(text.split()) for text in texts],
        "chapter": prose_observations(chapter),
        "cast_declared": len(people),
        "cast_named_in_chapter": named,
        "schema_words_in_chapter": len(schema_words.named_in(chapter)),
        "library_shelves": len(shelves),
        "promise_lines_by_profile": promise_lines(rows),
    }
    return {"observations": observations,
            "delivery": {"outline": delivery_result(rows, table["outline"])},
            "artifacts": artifacts(n, views)}


OBSERVERS = {"concept": observe_concept, "listing": observe_listing, "world": observe_world,
             "chapter": observe_chapter}


def observe(n: int, checkpoint: str) -> None:
    forbid_provider_calls()
    rows = receipts(n)
    body = OBSERVERS[checkpoint](n, rows, delivery_table(n))
    calls = read(progress_path(n))["calls"]
    body["calls"] = {"count": len(calls),
                     "failed": sum(call["status"] != "completed" for call in calls),
                     "tokens": sum(call["tokens"] for call in calls)}
    body["checkpoint"] = checkpoint
    write_new(checkpoint_path(n, checkpoint), body)


# ------------------------------------------------------------ binding what the gate reads


def chapter_texts(n: int) -> tuple[list[str], list[Any]]:
    """Chapter one's scene texts in reading order, and the store's state records."""
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.nodes import NodeKind

    with SqliteStore.open_read_only(draw_dir(n) / "book.db") as store:
        book, branch, _ = store.branches()[0]
        head = store.head(book, branch)
        records = store.state_records(book, branch)
    scenes = ([node for node in head.in_reading_order() if node.kind is NodeKind.SCENE]
              if head else [])
    return [(node.content or "").strip() for node in scenes[:CHAPTER_SCENES]], records


def library_shelves(n: int) -> list[Path]:
    return sorted(marker.parent for marker in (draw_dir(n) / "library").glob(f"*/{SHELF_MARKER}"))


def checkpoint_files(n: int, checkpoint: str) -> list[Path]:
    """The files a gate read reads at this checkpoint, beside the stage's own step records."""
    d = draw_dir(n)
    steps = sorted((d / "steps").glob(f"{STAGE_OF[checkpoint]}-*.json"))
    if checkpoint == "concept":
        return [*(d / "concept").rglob("*"), *steps]
    if checkpoint == "listing":
        return [*(d / "listing").rglob("*"), *steps]
    if checkpoint == "chapter":
        shelves = [p for shelf in library_shelves(n) for p in shelf.rglob("*")]
        return [d / "chapter-one.md", d / "views" / "library.json", *shelves, *steps]
    return steps


def bind(n: int, checkpoint: str) -> None:
    """Child mode: record what the gate at this checkpoint reads, before any observation.

    The files by hash, and the store by `store_digest`; the next stage re-checks both before
    it acts. At the chapter checkpoint it first writes the reading copy and exports the
    library (the reading edition `publish` copies). No provider call is made.
    """
    forbid_provider_calls()
    d = draw_dir(n)
    if checkpoint == "chapter":
        texts, _ = chapter_texts(n)
        title_path = d / "listing" / "title.txt"
        title = title_path.read_text(encoding="utf-8").strip() if title_path.is_file() else ""
        (d / "chapter-one.md").write_text(
            f"# {title}\n\n## Chapter 1\n\n" + "\n\n* * *\n\n".join(texts) + "\n",
            encoding="utf-8")
        view(n, "library", ["library"])
    write_new(checkpoint_path(n, checkpoint, "binding"), {
        "checkpoint": checkpoint,
        "artifacts": artifacts(n, checkpoint_files(n, checkpoint)),
        "store_sha256": store_digest(n),
        "recorded_at": now(),
    })


def binding_changes(n: int, checkpoint: str, gate_entry: dict[str, Any] | None = None) -> list[str]:
    """What changed since this checkpoint was bound (and, given its gate, since it was read)."""
    d = draw_dir(n)
    path = checkpoint_path(n, checkpoint, "binding")
    if not path.is_file():
        return [path.relative_to(d).as_posix()]
    if gate_entry is not None and sha(path) != gate_entry.get("binding_sha256"):
        return [path.relative_to(d).as_posix()]
    return [p for p, h in read(path)["artifacts"].items()
            if not (d / p).is_file() or sha(d / p) != h]


def deliver(n: int) -> None:
    rows = receipts(n)
    table = delivery_table(n)
    write(draw_dir(n) / "delivery.json", {
        "table": public_table(table),
        "results": {name: delivery_result(rows, entry) for name, entry in table.items()},
        "promise_lines_by_profile": promise_lines(rows),
    })


# ----------------------------------------------------------------- the parent: stages


def stage_refusal(n: int, state: dict[str, Any], stage: str) -> str | None:
    if stage not in STAGES:
        return f"unknown stage {stage}"
    if state["status"] in (*ENDED, "passed"):
        return f"draw {n} has ended ({state['status']})"
    if state.get("stop"):
        return f"draw {n} stopped: {state['stop']}"
    if state.get("active"):
        return f"a step is recorded as active ({state['active']}); check by PID that none is live"
    if stage in state["stages"]:
        return f"{stage} already ran in draw {n}; a stage never runs twice or resumes"
    index = STAGES.index(stage)
    if index:
        checkpoint = CHECKPOINT_OF[STAGES[index - 1]]
        gate = state["gates"].get(checkpoint)
        if not gate or gate["result"] != "pass":
            return f"{stage} waits for a recorded pass at the {checkpoint} checkpoint"
    return admission(n, state, now())


def refuse_stage(n: int, state: dict[str, Any], stage: str) -> None:
    """Raise the reason `stage` may not start, or return.

    A ceiling reached at a stage boundary is an operational stop and ends the draw: a call
    admitted below a ceiling may cross it, the stage it ends can finish, and the next stage
    can never be admitted. Left `ready`, that draw could be neither gated nor redrawn.
    """
    reason = stage_refusal(n, state, stage)
    if not reason:
        return
    if reason.startswith("ceiling:"):
        state["stop"] = state.get("stop") or reason
        state["status"] = "stopped"
        write(progress_path(n), state)
        print(f"STOPPED before {stage}: {reason}\nDraw {n} has ended. Show it to the operator, "
              "then record `shown`.")
    raise Refusal(reason)


def dispatch(n: int, stage: str, name: str, iteration: int) -> dict[str, Any]:
    key = f"{stage}-{name}-{iteration}"
    path = draw_dir(n) / "steps" / f"{key}.json"
    if path.exists():
        raise Refusal(f"refusing a duplicate step {key}")
    state = read(progress_path(n))
    state["active"] = key
    state["stages"][stage]["steps"].append(key)
    write(progress_path(n), state)
    subprocess.run([str(runtime_python(n)), str(Path(__file__).resolve()), "step", str(n), key],
                   cwd=ROOT, env=environment(n), check=True)
    record: dict[str, Any] = read(path)
    state = read(progress_path(n))
    state.pop("active", None)
    write(progress_path(n), state)
    print(json.dumps({"draw": n, "step": key, "returncode": record["returncode"],
                      "accepted": record["after"]["accepted"], "calls": len(state["calls"]),
                      "tokens": sum(c["tokens"] for c in state["calls"]),
                      "stop": state.get("stop")}), flush=True)
    return record


def step_problem(n: int, name: str, record: dict[str, Any]) -> str | None:
    state = read(progress_path(n))
    if state.get("stop"):
        return state["stop"]
    code = record["returncode"]
    if code == 2:
        return f"{name} exited 2 (operational fault) {record.get('exception', '')}".strip()
    if code and not (name == "world-check" and code == 1):
        return f"{name} exited {code}"
    before, after = record["before"], record["after"]
    if after["accepted"]:
        return "a scene was drafted before the chapter stage"
    if after["terminal"] or after["exceptions"]:
        return "a parked or poisoned unit or an open exception needs a person"
    d = draw_dir(n)
    if name == "concept" and not (d / "concept" / "concept.json").is_file():
        return "concept wrote no concept.json"
    if name == "listing":
        if not (d / "listing" / "title.txt").is_file():
            return "listing wrote no title"
        if after["total"] != SCENES:
            return f"the listing stood up {after['total']} scenes, not {SCENES}"
    elif after["total"] != before["total"]:
        return "the scene count changed"
    return None


def tick_verdict(record: dict[str, Any], state: dict[str, Any]) -> tuple[str | None, bool]:
    """One tick's operational reading: (a stop reason, chapter one accepted)."""
    if state.get("stop"):
        return state["stop"], False
    before, after = record["before"], record["after"]
    if record["returncode"] == 2:
        return f"tick exited 2 (operational fault) {record.get('exception', '')}".strip(), False
    if after["terminal"] or after["exceptions"]:
        return "a parked or poisoned unit or an open exception needs a person", False
    if after["total"] != before["total"]:
        return "the scene count changed", False
    if any(after["scene_hashes"].get(k) != v for k, v in before["scene_hashes"].items()):
        return "an accepted scene changed", False
    chapter = after["scene_ids"][:CHAPTER_SCENES]
    beyond = sorted(set(after["scene_hashes"]) - set(chapter))
    if beyond:
        return f"a scene past chapter one was drafted: {beyond}", False
    done = len(chapter) == CHAPTER_SCENES and all(s in after["scene_hashes"] for s in chapter)
    if not done and "no_work tick=" in record["stdout"]:
        return "an idle tick before chapter one was accepted", False
    return None, done


def drive_chapter(n: int) -> str | None:
    record = dispatch(n, "chapter", "world-accept", 1)
    state = read(progress_path(n))
    if state.get("stop"):
        return state["stop"]
    if record["returncode"] != 0:
        return (f"world accept refused (exit {record['returncode']}); a person reads world "
                "check, and no automatic repair is made")
    failed = 0
    for iteration in range(1, MAX_TICKS + 1):
        record = dispatch(n, "chapter", "tick", iteration)
        reason, done = tick_verdict(record, read(progress_path(n)))
        if reason:
            return reason
        if done:
            return None
        failed = failed + 1 if record["returncode"] == 1 else 0
        if failed >= MAX_FAILED_TICKS:
            return f"{failed} consecutive failed ticks"
    return f"{MAX_TICKS} ticks without accepting chapter one"


def drive(n: int, stage: str) -> str | None:
    if stage == "chapter":
        return drive_chapter(n)
    for name in FIXED_STEPS[stage]:
        reason = step_problem(n, name, dispatch(n, stage, name, 1))
        if reason:
            return reason
    return None


def finish_stage(n: int, stage: str, reason: str | None) -> None:
    state = read(progress_path(n))
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
    write(progress_path(n), state)


def child(n: int, mode: str, checkpoint: str, log: Path | None = None) -> int:
    """Run a no-provider child mode (`bind`, `observe`) in the draw's runtime; its exit code."""
    argv = [str(runtime_python(n)), str(Path(__file__).resolve()), mode, str(n), checkpoint]
    if log is None:
        return subprocess.run(argv, cwd=ROOT, env=environment(n), check=False).returncode
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        return subprocess.run(argv, cwd=ROOT, env=environment(n), stdout=handle,
                              stderr=subprocess.STDOUT, check=False).returncode


def bind_checkpoint(n: int, checkpoint: str) -> str | None:
    """Bind what the gate will read; a failure is an operational stop, since nothing unbound
    may be gated."""
    code = child(n, "bind", checkpoint)
    if code or not checkpoint_path(n, checkpoint, "binding").is_file():
        return (f"the {checkpoint} checkpoint could not be bound (bind exited {code}); the "
                "runner is frozen for this draw, so a runner fix is a `fix` amendment")
    return None


def observe_checkpoint(n: int, checkpoint: str) -> bool:
    """Write the inert observations. A failure is recorded and the gate proceeds without
    them: observations decide nothing, so they can block nothing."""
    d = draw_dir(n)
    log = d / "checkpoints" / f"{checkpoint}.observe.log"
    code = child(n, "observe", checkpoint, log)
    if checkpoint_path(n, checkpoint).is_file():
        return True
    write_new(checkpoint_path(n, checkpoint, "observation-failed"), {
        "checkpoint": checkpoint, "returncode": code, "log": log.relative_to(d).as_posix(),
        "log_sha256": sha(log) if log.is_file() else None, "recorded_at": now(),
    })
    return False


def run_stage(stage: str) -> int:
    refuse_test_environment()
    lock()
    n = current_draw()
    verify_committed(n)
    verify_frozen(n)
    check_writer(n)
    state = read(progress_path(n))
    refuse_stage(n, state, stage)
    index = STAGES.index(stage)
    if index:
        # The inputs this stage acts on are the ones the previous gate read: its files here,
        # its store in the child before the stage's first step (`bound_store_refusal`).
        previous = CHECKPOINT_OF[STAGES[index - 1]]
        changed = binding_changes(n, previous, state["gates"][previous])
        if changed:
            raise Refusal(f"what the {previous} gate read changed since it was recorded: "
                          f"{changed}")
    state["status"] = "running"
    state["stages"][stage] = {"status": "running", "started_at": now(), "steps": []}
    write(progress_path(n), state)
    checkpoint = CHECKPOINT_OF[stage]
    try:
        outcome = drive(n, stage)
        if outcome is None:
            outcome = bind_checkpoint(n, checkpoint)
    except BaseException as error:
        finish_stage(n, stage, f"scheduler failure: {error!r}")
        raise
    finish_stage(n, stage, outcome)
    if outcome is not None:
        print(f"STOPPED in {stage}: {outcome}\nDraw {n} has ended. Read its transport receipts "
              "first, show it to the operator, then record `shown`.")
        return 1
    observe_checkpoint(n, checkpoint)
    print_checkpoint(n, checkpoint)
    return 0


def print_checkpoint(n: int, checkpoint: str) -> None:
    d = draw_dir(n)
    calls = read(progress_path(n))["calls"]
    failed = [c["number"] for c in calls if c["status"] != "completed"]
    binding = read(checkpoint_path(n, checkpoint, "binding"))
    print(f"CHECKPOINT {checkpoint}, draw {n}. The runner exits here and waits for a person.")
    print(f"  transport first: {len(calls)} calls, failed or unfinished {failed or 'none'}, "
          f"{sum(c['tokens'] for c in calls)} tokens")
    print(f"  bound for the gate: {len(binding['artifacts'])} files and the store "
          f"({binding['store_sha256'] or 'none yet'})")
    if checkpoint_path(n, checkpoint).is_file():
        body = read(checkpoint_path(n, checkpoint))
        print("  delivery (code-checked; delivery is not compliance):")
        print(json.dumps(body["delivery"], ensure_ascii=False, indent=2))
        print("  observations (inert counts beside the gate; they decide nothing):")
        print(json.dumps(body["observations"], ensure_ascii=False, indent=2))
    else:
        failure = read(checkpoint_path(n, checkpoint, "observation-failed"))
        print(f"  OBSERVATION FAILED (exit {failure['returncode']}); recorded, and the gate "
              f"proceeds without it. Log: {d / failure['log']}. Delivery is checked at audit.")
    print("  the gate read answers, one line each (`<id>: PASS|FAIL|PARTIAL <location>`):")
    for item, text in CHECKPOINT_ITEMS[checkpoint]:
        print(f"    {item}: {text}")
    print(f"  then: run.py gate {checkpoint} pass|fail --read <gate read> --by <who>")


# ------------------------------------------------------------------ a person's records


def item_verdicts(checkpoint: str, text: str) -> dict[str, str]:
    """Each item's verdict from its one verdict line, or a Refusal naming what is wrong."""
    ids = [item for item, _ in CHECKPOINT_ITEMS[checkpoint]]
    found: dict[str, list[str]] = {}
    for match in VERDICT_LINE.finditer(text):
        if match["item"] in ids:
            found.setdefault(match["item"], []).append(match["verdict"])
    missing = [item for item in ids if item not in found]
    if missing:
        raise Refusal(f"the gate read does not answer {missing}: each item needs a line "
                      "`<id>: PASS|FAIL|PARTIAL <location>`")
    doubled = [item for item in ids if len(found[item]) > 1]
    if doubled:
        raise Refusal(f"the gate read answers {doubled} more than once; one verdict per item")
    return {item: found[item][0] for item in ids}


def gate_result_refusal(result: str, verdicts: dict[str, str]) -> str | None:
    """The registered rule: pass only when every item is PASS; PARTIAL counts as FAIL."""
    short = sorted(item for item, verdict in verdicts.items() if verdict != "PASS")
    if result == "pass" and short:
        return f"a pass is recorded only when every item is PASS; not PASS: {short}"
    if result == "fail" and not short:
        return "every item reads PASS, so the registered rule records a pass, not a fail"
    return None


def gate(checkpoint: str, result: str, read_file: Path, by: str) -> dict[str, Any]:
    """Record a person's pass or fail at a checkpoint.

    The runner reads the item verdict lines and holds the result to the registered rule; it
    checks nothing else about the read. What the read covers is bound: the checkpoint's
    binding, and its observation when there is one (a recorded observation failure stands in
    for it, since observations decide nothing).
    """
    if checkpoint not in CHECKPOINTS:
        raise Refusal(f"unknown checkpoint {checkpoint}")
    if result not in GATE_RESULTS:
        raise Refusal("a gate is pass or fail")
    n = current_draw()
    d = draw_dir(n)
    state = read(progress_path(n))
    if state.get("active") or any(s.get("status") == "running" for s in state["stages"].values()):
        raise Refusal("a stage is running; a gate is recorded only at a checkpoint")
    record = state["stages"].get(STAGE_OF[checkpoint])
    if not record or record.get("status") != "done":
        raise Refusal(f"the {checkpoint} checkpoint was not reached in draw {n}")
    if checkpoint in state["gates"]:
        raise Refusal(f"the {checkpoint} gate is already recorded; one verdict per checkpoint")
    unfinished = [c["number"] for c in state["calls"] if c["status"] != "completed"]
    if unfinished:
        raise Refusal(f"transport failures are read before any verdict: calls {unfinished}")
    binding_path = checkpoint_path(n, checkpoint, "binding")
    if not binding_path.is_file():
        raise Refusal(f"the {checkpoint} checkpoint was never bound; nothing unbound is gated")
    changed = binding_changes(n, checkpoint)
    body_path = checkpoint_path(n, checkpoint)
    failure_path = checkpoint_path(n, checkpoint, "observation-failed")
    if body_path.is_file():
        observation = "recorded"
        changed += [p for p, h in read(body_path)["artifacts"].items()
                    if not (d / p).is_file() or sha(d / p) != h]
    elif failure_path.is_file():
        observation = "failed"
    else:
        raise Refusal(f"the {checkpoint} observation is neither recorded nor recorded as "
                      f"failed; run `<draw runtime python> run.py observe {n} {checkpoint}` "
                      "(it makes no provider call)")
    if changed:
        raise Refusal(f"checkpoint artifacts changed since they were recorded: {changed}")
    text = read_file.read_text(encoding="utf-8") if read_file.is_file() else ""
    if not text.strip():
        raise Refusal("the gate read is missing or empty")
    verdicts = item_verdicts(checkpoint, text)
    refusal = gate_result_refusal(result, verdicts)
    if refusal:
        raise Refusal(refusal)
    entry = {"result": result, "items": verdicts, "by": by, "read": str(read_file.resolve()),
             "read_sha256": sha(read_file), "binding_sha256": sha(binding_path),
             "observation": observation,
             "checkpoint_sha256": sha(body_path) if body_path.is_file() else None,
             "observation_failure_sha256": sha(failure_path) if failure_path.is_file() else None,
             "recorded_at": now()}
    state["gates"][checkpoint] = entry
    if result == "fail":
        state["status"] = "failed"
    else:
        state["status"] = "passed" if checkpoint == "chapter" else "ready"
    write(progress_path(n), state)
    print(f"draw {n}: {checkpoint} {result} recorded.")
    if result == "fail":
        print("The draw has ended. Show it to the operator, then record `shown`.")
    return entry


def shown(by: str, how: str) -> None:
    n = current_draw()
    state = read(progress_path(n))
    if state["status"] not in (*ENDED, "passed"):
        raise Refusal(f"draw {n} has not ended ({state['status']})")
    if state["status"] == "passed" and not state.get("published") and library_shelves(n):
        raise Refusal("publish the reading edition before recording that it was shown")
    if state.get("shown"):
        raise Refusal(f"draw {n} is already recorded as shown")
    state["shown"] = {"by": by, "how": how, "at": now()}
    write(progress_path(n), state)


def publish() -> Path:
    n = current_draw()
    d = draw_dir(n)
    state = read(progress_path(n))
    if state["status"] != "passed":
        raise Refusal("only a draw that passed chapter one is copied to the book library")
    if state.get("published"):
        raise Refusal("already published")
    shelves = library_shelves(n)
    if len(shelves) != 1:
        raise Refusal(f"expected one library shelf, found {len(shelves)}; with none, the draw "
                      "is shown from its run folder")
    destination = LIBRARY / shelves[0].name
    if destination.exists():
        raise Refusal(f"{destination} exists; a shelf is never overwritten")
    shutil.copytree(shelves[0], destination)
    shutil.copy2(d / "chapter-one.md", destination / "chapter-one.md")
    state["published"] = {"path": str(destination), "at": now(),
                          "files": {p.relative_to(destination).as_posix(): sha(p)
                                    for p in sorted(destination.rglob("*")) if p.is_file()}}
    write(progress_path(n), state)
    print(f"Reading edition copied to {destination}.")
    return destination


def close(reason: str) -> None:
    if not reason.strip():
        raise Refusal("closing the series records the operator's reason")
    states = [read(progress_path(k)) for k in draws()]
    if any(s.get("active") for s in states):
        raise Refusal("a step is recorded as active")
    write_new(LOCAL / "closed.json", {"reason": reason, "at": now(), "draws": draws()})


# ------------------------------------------------------------------------------ audit


def numeric(value: Any) -> Any:
    """Counts and flags only: evidence.json carries no prose."""
    if isinstance(value, dict):
        kept = {k: numeric(v) for k, v in value.items()}
        return {k: v for k, v in kept.items() if v is not None or value[k] is None}
    if isinstance(value, list):
        return len(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return None


def transport_checks(row: dict[str, Any], python: Path) -> dict[str, bool]:
    result = row.get("result") or {}
    raw = result.get("raw") or row.get("raw") or {}
    request = row["request"]
    argv, settings = raw.get("argv") or [], raw.get("settings") or {}
    tools = request.get("allowed_tools") or []
    bridge = [json.loads(line) for line in (raw.get("commands_jsonl") or "").splitlines()
              if line.strip()]
    results = [entry for entry in bridge if entry.get("phase") == "result"
               and entry.get("argv") is not None]
    working = raw.get("working_directory")
    return {
        "completed": row["status"] == "completed",
        "provider": raw.get("provider") == PROVIDER,
        "model": raw.get("requested_model") == MODEL and request.get("model") is None,
        "effort": settings.get("model_reasoning_effort") == EFFORT,
        "isolated": all(flag in argv
                        for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules")),
        # §258's control, on the Codex side: the call ran outside the repository.
        "outside_repository": bool(working) and not within(working, ROOT),
        "skip_git_repo_check": "--skip-git-repo-check" in argv,
        "no_memory": settings.get("features.memories") is False,
        "no_project_docs": settings.get("project_doc_max_bytes") == 0,
        "no_search": settings.get("web_search") == "disabled",
        "mode": raw.get("mode") == ("bridge" if tools else "completion"),
        "world_only": all(tool.startswith("Bash(litharness world ") for tool in tools),
        "prompt": raw.get("prompt") == request.get("prompt"),
        "bridge_runtime": all(
            bool(entry["argv"]) and entry["argv"][1:3] == ["-m", "litharness"]
            and os.path.normcase(str(entry["argv"][0])) == os.path.normcase(str(python))
            for entry in results
        ),
        "usage_recorded": row["status"] != "completed"
        or sum((result.get("usage") or {}).values()) > 0,
    }


def draw_evidence(n: int) -> dict[str, Any]:
    d = draw_dir(n)
    state = read(progress_path(n))
    settings = read(d / "settings.json")
    preflight_record = read(d / "preflight.json")
    calls, previous, sessions = [], None, set()
    for meta in state["calls"]:
        path = d / meta["path"]
        row = read(path)
        checks = transport_checks(row, runtime_python(n))
        checks["receipt_chain"] = row.get("previous_receipt_sha256") == previous
        previous = sha(path)
        raw = (row.get("result") or {}).get("raw") or row.get("raw") or {}
        ids = [event.get("thread_id") for event in raw.get("events") or []
               if event.get("type") == "thread.started"]
        checks["fresh_session"] = len(ids) == 1 and bool(ids[0]) and ids[0] not in sessions
        sessions.update(ids)
        calls.append({"number": meta["number"], "stage": meta["stage"],
                      "profile": meta["profile"], "status": meta["status"],
                      "tokens": meta["tokens"], "receipt_sha256": previous,
                      "request_sha256": digest(row["request"]), "checks": checks})
    first = next((row for row in receipts(n) if not is_probe(row["request"])), None)
    checkpoints: dict[str, Any] = {}
    for checkpoint in CHECKPOINTS:
        body, binding = checkpoint_path(n, checkpoint), checkpoint_path(n, checkpoint, "binding")
        failed = checkpoint_path(n, checkpoint, "observation-failed")
        if not binding.is_file():
            continue
        checkpoints[checkpoint] = {
            "binding_sha256": sha(binding),
            "observation": ("recorded" if body.is_file()
                            else "failed" if failed.is_file() else "missing"),
            "sha256": sha(body) if body.is_file() else None,
            "observations": numeric(read(body)["observations"]) if body.is_file() else None,
        }

    def coded(text: str | None) -> dict[str, str | None] | None:
        return {"code": reason_code(text), "sha256": sha_text(text)} if text else None

    return {
        "draw": n,
        "status": state["status"],
        "stop": coded(state.get("stop")),
        "revision": settings["revision"],
        "writer": settings["writer"],
        "writer_id": settings["writer_id"],
        "dossier_sha256": settings["dossier_sha256"],
        "binary": {k: settings["binary"][k] for k in ("sha256", "version")},
        "registration_sha256": sha(registration_path(n)),
        "stages": {name: {"status": record.get("status"), "seconds": record.get("seconds"),
                          "reason": coded(record.get("reason")),
                          "steps": len(record.get("steps", []))}
                   for name, record in state["stages"].items()},
        "steps": [{"key": path.stem, "sha256": sha(path), "returncode": read(path)["returncode"]}
                  for path in sorted((d / "steps").glob("*.json"))],
        "gates": {name: {k: gate_.get(k) for k in ("result", "items", "read_sha256",
                                                    "binding_sha256", "observation",
                                                    "checkpoint_sha256")}
                  for name, gate_ in state["gates"].items()},
        "checkpoints": checkpoints,
        "delivery": read(d / "delivery.json")["results"],
        "first_request_matches_preflight": first is not None
        and digest(first["request"]) == preflight_record["request_sha256"],
        "calls": calls,
        "known_tokens": sum(c["tokens"] for c in state["calls"]),
        "all_transport_controls_pass": all(all(c["checks"].values()) for c in calls),
        "shown": bool(state.get("shown")),
        "published": bool(state.get("published")),
    }


def audit() -> dict[str, Any]:
    found = draws()
    if not found:
        raise Refusal("nothing to audit")
    states = {n: read(progress_path(n)) for n in found}
    if any(s.get("active") or any(r.get("status") == "running" for r in s["stages"].values())
           for s in states.values()):
        raise Refusal("a stage is running")
    passed = any(s["status"] == "passed" and s.get("shown") for s in states.values())
    exhausted = len(found) == MAX_DRAWS and all(
        s["status"] in ENDED and s.get("shown") for s in states.values())
    if not (passed or exhausted or closed()):
        raise Refusal("the audit is final: it follows a shown pass, three shown ended draws, "
                      "or `close`")
    unshown = [n for n, s in states.items() if s["status"] in (*ENDED, "passed")
               and not s.get("shown")]
    if unshown:
        raise Refusal(f"every ended draw is shown to the operator first: {unshown}")
    for n in found:
        subprocess.run([str(runtime_python(n)), str(Path(__file__).resolve()), "deliver", str(n)],
                       cwd=ROOT, env=environment(n), check=True)
    closing = read(LOCAL / "closed.json") if closed() else None
    evidence = {
        "schema": "restored-directions-draw.evidence.v1",
        "claim_id": CLAIM_ID,
        "draws": [draw_evidence(n) for n in found],
        "closed": ({"at": closing["at"], "draws": closing["draws"],
                    "reason_sha256": sha_text(closing["reason"])} if closing else None),
        "totals": {"calls": sum(len(s["calls"]) for s in states.values()),
                   "tokens": sum(c["tokens"] for s in states.values() for c in s["calls"])},
        "audited_at": now(),
    }
    write(HERE / "evidence.json", evidence)
    claim("observed")
    print(json.dumps({"draws": len(found), "statuses": [s["status"] for s in states.values()],
                      "transport_controls": [d["all_transport_controls_pass"]
                                             for d in evidence["draws"]]}))
    return evidence


def claim(status: str) -> None:
    files = [("registration", HERE / "PREREG.md"), ("registration", HERE / "RUNBOOK.md")]
    files += [("registration", registration_path(k)) for k in range(1, MAX_DRAWS + 1)
              if registration_path(k).is_file()]
    files += [("registration", path) for k in range(2, MAX_DRAWS + 1)
              for path in amendment_paths(k) if path.is_file()]
    if status == "observed":
        files.append(("derived_result", HERE / "evidence.json"))
    write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": CLAIM_ID,
        "status": status,
        "statement": CLAIM_STATEMENT,
        "artifacts": [{"kind": kind, "path": rel(path), "sha256": sha(path)}
                      for kind, path in files],
    })


def status() -> None:
    for n in draws():
        state = read(progress_path(n))
        print(json.dumps({
            "draw": n, "status": state["status"], "stop": state.get("stop"),
            "stages": {k: v.get("status") for k, v in state["stages"].items()},
            "gates": {k: v["result"] for k, v in state["gates"].items()},
            "calls": len(state["calls"]), "tokens": sum(c["tokens"] for c in state["calls"]),
            "shown": bool(state.get("shown")), "published": bool(state.get("published")),
        }))
    if closed():
        print("closed:", json.dumps(read(LOCAL / "closed.json")))


# --------------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("plan")
    sub.add_parser("status")
    sub.add_parser("prepare").add_argument("--draw", type=int, default=1)
    for stage in STAGES:
        sub.add_parser(stage)
    gate_parser = sub.add_parser("gate")
    gate_parser.add_argument("checkpoint", choices=CHECKPOINTS)
    gate_parser.add_argument("result", choices=GATE_RESULTS)
    gate_parser.add_argument("--read", type=Path, required=True)
    gate_parser.add_argument("--by", required=True)
    shown_parser = sub.add_parser("shown")
    shown_parser.add_argument("--by", required=True)
    shown_parser.add_argument("--how", required=True)
    sub.add_parser("publish")
    sub.add_parser("close").add_argument("--reason", required=True)
    sub.add_parser("audit")
    for child in ("preflight", "deliver"):
        sub.add_parser(child).add_argument("draw", type=int)
    step_parser = sub.add_parser("step")
    step_parser.add_argument("draw", type=int)
    step_parser.add_argument("key")
    for child_mode in ("observe", "bind"):
        child_parser = sub.add_parser(child_mode)
        child_parser.add_argument("draw", type=int)
        child_parser.add_argument("checkpoint", choices=CHECKPOINTS)
    args = parser.parse_args(argv)
    try:
        if args.mode in STAGES:
            return run_stage(args.mode)
        if args.mode == "plan":
            plan()
        elif args.mode == "status":
            status()
        elif args.mode == "prepare":
            prepare(args.draw)
        elif args.mode == "gate":
            gate(args.checkpoint, args.result, args.read, args.by)
        elif args.mode == "shown":
            shown(args.by, args.how)
        elif args.mode == "publish":
            publish()
        elif args.mode == "close":
            close(args.reason)
        elif args.mode == "audit":
            audit()
        elif args.mode == "step":
            step(args.draw, args.key)
        else:
            require_frozen_source(args.draw)
            if args.mode == "preflight":
                preflight(args.draw)
            elif args.mode == "deliver":
                deliver(args.draw)
            elif args.mode == "observe":
                observe(args.draw, args.checkpoint)
            elif args.mode == "bind":
                bind(args.draw, args.checkpoint)
    except Refusal as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"a child step failed ({error.returncode}); its record and the progress file "
              "say where; nothing resumes implicitly", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
