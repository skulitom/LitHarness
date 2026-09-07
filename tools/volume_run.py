"""Draw a whole release volume of one serial, arc by arc, and record every step.

`tools/ab_redraw.py` stops at chapter one by construction: it exists to compare two draws of
one opening. Nothing in the repository drew a book past its second chapter before this
script (stage-0 §232 was the first attempt past chapter one), so this is the recipe for the
long run: stand the book up under a settled listing and concept, tick until the first arc is
drafted, put the Architect on the world at a chapter cadence, run the readership at each arc
end, extend the serial by one closed arc, and go again until the volume has its chapters.

**Resumable, because a night-long run is killed by something.** A store that already exists is
not re-seeded; the loop reads what is drafted and carries on. `tick` itself is restart-safe
(a killed unit is reclaimed and replayed), so the driver never needs to know where a tick
died. A `control.json` beside the log is read before every step, so the cadence can be
changed and the run paused or stopped without killing it.

**What stops the loop, and loudly.** A parked or poisoned unit, an open exception, three
idle ticks with scenes still undrafted, or `--max-failures` consecutive failed ticks. Each is
written to `run.json` with its reason; the driver never retries into a wall.

Everything the CLI does is spent through the CLI, argv handed to the OS as a list. No model
call is made here; nothing here reads the prose.

    uv run python tools/volume_run.py --run runs/volume1 --listing runs/volume1 \
        --writer tanaka --roster-database runs/roster/roster.db \
        --arcs 4 --chapter-scenes 2 --arc-chapters 12 --grow-every 1 \
        --max-cost-usd-per-day 400 --max-tokens-per-day 400000000 \
        --exemplars book-library --exemplars-limit 3 \
        --rivals research/quality-measurement/derived/rivals.json
"""

from __future__ import annotations

import argparse
import json
import locale
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.domain.jobs import JobStatus

OUTCOME = re.compile(r"^(no_work|ran_job|job_failed|job_parked|replayed) tick=", re.MULTILINE)


@dataclass(frozen=True)
class Spec:
    run: Path
    listing: Path
    database: Path
    writer: str
    roster_database: Path | None
    library: Path
    chapter_scenes: int
    arc_chapters: int
    arcs: int
    grow_every: int
    person: str
    max_cost_usd_per_day: float
    max_tokens_per_day: int
    exemplars: Path | None
    exemplars_limit: int
    rivals: Path | None
    tick_delay: float
    failure_delay: float
    max_failures: int
    max_idle: int
    litharness: tuple[str, ...]
    readers_at_arc_end: bool
    seed_attempts: int = 2

    @property
    def scenes_per_arc(self) -> int:
        return self.chapter_scenes * self.arc_chapters

    def base(self) -> list[str]:
        argv = [*self.litharness, "--database", str(self.database)]
        if self.roster_database is not None:
            argv += ["--roster-database", str(self.roster_database)]
        argv += [
            "--writer",
            self.writer,
            "--library",
            str(self.library),
            "--chapter-scenes",
            str(self.chapter_scenes),
            "--arc-chapters",
            str(self.arc_chapters),
            "--max-cost-usd-per-day",
            str(self.max_cost_usd_per_day),
            "--max-tokens-per-day",
            str(self.max_tokens_per_day),
        ]
        if self.exemplars is not None:
            argv += [f"--exemplars={self.exemplars}", f"--exemplars-limit={self.exemplars_limit}"]
        return argv


@dataclass
class Probe:
    exists: bool
    drafted: int = 0
    total: int = 0
    scene_ids: tuple[str, ...] = ()
    drafted_ids: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    parked: tuple[str, ...] = ()
    poisoned: tuple[str, ...] = ()
    stale: tuple[str, ...] = ()
    title: str = ""

    @property
    def trouble(self) -> tuple[str, ...]:
        return (*self.exceptions, *self.parked, *self.poisoned)


def probe(database: Path) -> Probe:
    """What the store holds: drafted scenes, and every reason a person is needed."""
    if not database.exists():
        return Probe(exists=False)
    store = SqliteStore.open(database)
    try:
        exceptions = tuple(
            f"exception {record.kind.value} {record.exception_id}: {record.summary}"
            for record in store.open_exceptions()
        )
        branches = store.branches()
        if len(branches) != 1:
            return Probe(
                exists=True,
                exceptions=exceptions,
                parked=tuple(
                    f"parked {job.job_kind} {job.job_id}: {job.error or 'no error recorded'}"
                    for job in store.jobs_by_status(JobStatus.PARKED)
                ),
                poisoned=tuple(
                    f"poisoned {job.job_kind} {job.job_id}: {job.error or 'no error recorded'}"
                    for job in store.jobs_by_status(JobStatus.POISONED)
                ),
            )
        book_id, branch_id, _ = branches[0]
        document = export_module.collect(
            store,
            book_id=book_id,
            branch_id=branch_id,
            generated_at=datetime.now(tz=UTC).isoformat(),
        )
        drafted_ids = tuple(scene.logical_id for scene in document.scenes if scene.drafted)
        # **A parked draft whose scene is accepted at head is a stale row, not a wall.** The
        # first whole-volume draw revived a parked scene-23 draft, the revived attempt
        # accepted, and the job's earlier park decision re-parked it after the fact, twice.
        # A parked unit is never claimed, and a drafted scene is never re-enqueued, so the
        # row blocks nothing; the driver names it and carries on.
        parked: list[str] = []
        stale: list[str] = []
        for job in store.jobs_by_status(JobStatus.PARKED):
            scene = (job.payload or {}).get("logical_id") if isinstance(job.payload, dict) else None
            line = f"parked {job.job_kind} {job.job_id}: {job.error or 'no error recorded'}"
            if job.job_kind == "scene_draft" and scene in drafted_ids:
                stale.append(f"stale {line} (scene {scene} is accepted at head)")
            else:
                parked.append(line)
        poisoned = tuple(
            f"poisoned {job.job_kind} {job.job_id}: {job.error or 'no error recorded'}"
            for job in store.jobs_by_status(JobStatus.POISONED)
        )
        return Probe(
            exists=True,
            drafted=document.drafted,
            total=document.total,
            scene_ids=tuple(scene.logical_id for scene in document.scenes),
            drafted_ids=drafted_ids,
            exceptions=exceptions,
            parked=tuple(parked),
            poisoned=poisoned,
            stale=tuple(stale),
            title=document.title,
        )
    finally:
        store.close()


@dataclass
class StepResult:
    label: str
    argv: tuple[str, ...]
    returncode: int
    seconds: float
    output: str


def decode_output(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode(locale.getpreferredencoding(False), errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def tree_state(cwd: Path) -> dict[str, object]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=30
        )
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", "src", "tools"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {"head": None, "dirty": None}
    if head.returncode != 0 or status.returncode != 0:
        return {"head": None, "dirty": None}
    dirty = sorted(line[3:].strip() for line in status.stdout.splitlines() if line.strip())
    return {"head": head.stdout.strip(), "dirty": dirty}


class Log:
    def __init__(self, run: Path) -> None:
        self.commands = run / "commands.log"
        self.progress = run / "progress.log"

    def command(self, result: StepResult) -> None:
        with self.commands.open("a", encoding="utf-8") as handle:
            handle.write("\n$ " + " ".join(_quote(part) for part in result.argv) + "\n")
            handle.write(f"# {result.label} · exit {result.returncode} · {result.seconds:.1f}s\n")
            for line in result.output.rstrip().splitlines():
                handle.write("    " + line + "\n")

    def note(self, message: str) -> None:
        stamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{stamp} {message}"
        print(line, flush=True)
        with self.progress.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _quote(part: str) -> str:
    return part if re.fullmatch(r"[\w./=:\\-]+", part) else "'" + part.replace("'", "'\\''") + "'"


def run_step(label: str, argv: Sequence[str], cwd: Path, log: Log) -> StepResult:
    started = time.monotonic()
    completed = subprocess.run(list(argv), cwd=cwd, capture_output=True, check=False)
    result = StepResult(
        label=label,
        argv=tuple(argv),
        returncode=completed.returncode,
        seconds=time.monotonic() - started,
        output=decode_output(completed.stdout or b"") + decode_output(completed.stderr or b""),
    )
    log.command(result)
    return result


@dataclass
class RunState:
    started: str
    tree_at_start: dict[str, object]
    ticks: int = 0
    grows: int = 0
    extends: int = 0
    readers_runs: int = 0
    seed_attempts: int = 0
    failures: int = 0
    idle: int = 0
    last_grow_chapter: int = 0
    chapters_complete: int = 0
    stopped: str | None = None
    finished: str | None = None
    tree_at_finish: dict[str, object] | None = None
    notes: list[str] = field(default_factory=list)


def read_control(run: Path) -> dict[str, object]:
    path = run / "control.json"
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save(run: Path, state: RunState, spec: Spec) -> None:
    payload = {"spec": {k: str(v) if isinstance(v, Path) else v for k, v in asdict(spec).items()}}
    payload.update(asdict(state))
    (run / "run.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def read_spend(database: Path) -> dict[str, object]:
    """Spend off `policy_decisions`; a floor, not a total (serial pilot 12 §5)."""
    import sqlite3

    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT COALESCE(SUM(invocations),0), COALESCE(SUM(total_tokens),0), "
            "COALESCE(SUM(cost_usd),0), COUNT(*) FROM policy_decisions"
        ).fetchone()
    return {
        "invocations": rows[0],
        "tokens": rows[1],
        "cost_usd": round(rows[2], 4),
        "decisions": rows[3],
        "source": "policy_decisions",
        "caveat": "a floor rather than a total: a provider that reports no cost contributes zero",
    }


#: §213.1's fault, as `world check` prints it, with the number the column takes named in it.
FAULT = re.compile(
    r"^(?P<subject>\S+)'s status_snapshot puts '(?P<value>[^']+)' in the (?P<column>\S+) "
    r"column, which takes a whole number; the rung \S+ is (?P<number>\d+) of \d+"
)


def _json_in(output: str) -> dict[str, Any] | list[Any] | None:
    """The JSON a verb printed, found by its first bracket; None when there is none."""
    for opener in ("{", "["):
        start = output.find(opener)
        if start >= 0:
            try:
                loaded: Any = json.loads(output[start:])
            except ValueError:
                continue
            return loaded if isinstance(loaded, dict | list) else None
    return None


def world_faults(spec: Spec, cwd: Path, log: Log) -> tuple[list[str], list[str]]:
    """What `world check` previews as refusable: snapshot faults and gate breaches."""
    result = run_step("world check", [*spec.base(), "world", "check"], cwd, log)
    payload = _json_in(result.output)
    if not isinstance(payload, dict):
        return [], []
    return list(payload.get("snapshot_faults") or []), list(payload.get("would_breach") or [])


def repair_snapshot_faults(spec: Spec, cwd: Path, log: Log, state: RunState) -> bool:
    """The operator's documented fix for §213.1, done from the arithmetic's own message.

    `world check` names the rung and the number the column takes; the faulty snapshot is
    redeclared with that number in that column and nothing else changed, which is the
    `world declare` the refusal asks for. A later declaration fills the slot, so the faulty
    proposal is left behind unaccepted. Anything the pattern does not name is left to a
    person. Returns True when `world accept` then accepts.
    """
    base = spec.base()
    faults, breaches = world_faults(spec, cwd, log)
    if breaches or not faults:
        return False
    parsed = [FAULT.match(fault) for fault in faults]
    if not all(parsed):
        state.notes.append("snapshot fault(s) the driver cannot read: " + "; ".join(faults))
        return False
    shown = run_step("world show", [*base, "world", "show", "--json"], cwd, log)
    rows = _json_in(shown.output)
    if not isinstance(rows, list):
        return False
    for match in parsed:
        assert match is not None
        subject, bad, column = match.group("subject"), match.group("value"), match.group("column")
        number = int(match.group("number"))
        for row in rows:
            value = row.get("value") if isinstance(row, dict) else None
            if (
                row.get("subject") == subject
                and row.get("predicate") == "status_snapshot"
                and isinstance(value, dict)
                and value.get(column) == bad
            ):
                fixed = dict(value)
                fixed[column] = number
                argv = [
                    *base,
                    "world",
                    "declare",
                    subject,
                    "status_snapshot",
                    "--value",
                    json.dumps(fixed),
                ]
                if row.get("order_key"):
                    argv += ["--order-key", str(row["order_key"])]
                declared = run_step(f"world declare {subject} status_snapshot", argv, cwd, log)
                log.note(
                    f"repaired {subject}'s snapshot: {column} {bad!r} -> {number} "
                    f"(exit {declared.returncode})"
                )
    accept = run_step("world accept", [*base, "world", "accept"], cwd, log)
    log.note(f"world accept after repair: exit {accept.returncode}")
    return accept.returncode == 0


def set_aside(spec: Spec, log: Log, attempt: int) -> None:
    """Keep a refused store beside the run rather than deleting it: it is the record."""
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(spec.database) + suffix)
        if path.exists():
            target = spec.database.with_name(
                f"{spec.database.stem}.refused-{attempt}{spec.database.suffix}{suffix}"
            )
            path.replace(target)
    if spec.library.exists():
        spec.library.replace(spec.library.with_name(f"{spec.library.name}.refused-{attempt}"))
    log.note(f"store set aside as refused-{attempt}")


def stand_up(spec: Spec, cwd: Path, log: Log, state: RunState) -> bool:
    title = (spec.listing / "title.txt").read_text(encoding="utf-8").strip()
    premise = (spec.listing / "listing.txt").read_text(encoding="utf-8").strip()
    concept = spec.listing / "concept.json"
    base = spec.base()
    for attempt in range(1, spec.seed_attempts + 1):
        if attempt > 1:
            set_aside(spec, log, attempt - 1)
        log.note(f"standing up '{title}' in {spec.database} (seed attempt {attempt})")
        state.seed_attempts = attempt
        accepted = False
        for label, argv in (
            ("init", [*base, "init"]),
            (
                "new",
                [
                    *base,
                    "new",
                    title,
                    "--premise",
                    premise,
                    "--scenes",
                    str(spec.scenes_per_arc),
                    "--person",
                    spec.person,
                    *(["--concept", str(concept)] if concept.exists() else []),
                ],
            ),
            ("architect seed", [*base, "architect", "seed"]),
            ("world check", [*base, "world", "check"]),
            ("world accept", [*base, "world", "accept"]),
        ):
            result = run_step(label, argv, cwd, log)
            log.note(f"{label}: exit {result.returncode} in {result.seconds:.0f}s")
            if label == "world check":
                if result.returncode not in (0, 1):
                    state.stopped = f"world check exited {result.returncode}"
                    return False
                continue
            if label == "world accept":
                accepted = result.returncode == 0
                if not accepted:
                    log.note("world accept refused the seed; trying the documented repair")
                    accepted = repair_snapshot_faults(spec, cwd, log, state)
                break
            if result.returncode != 0:
                state.stopped = f"{label} exited {result.returncode}"
                return False
        if accepted:
            # The world as canon, read once more: a fault the preview could not see would
            # print on every scene, so it stops the run here rather than forty scenes later.
            faults, breaches = world_faults(spec, cwd, log)
            if faults or breaches:
                state.stopped = "accepted world reads faulty: " + "; ".join([*faults, *breaches])
                return False
            return True
        log.note(f"seed attempt {attempt} refused")
    state.stopped = f"the seed was refused {spec.seed_attempts} time(s); a person reads world check"
    return False


def grow(spec: Spec, cwd: Path, log: Log, state: RunState, scene_id: str) -> None:
    base = spec.base()
    result = run_step(
        f"architect grow {scene_id}", [*base, "architect", "grow", "--scene", scene_id], cwd, log
    )
    state.grows += 1
    log.note(f"grow on {scene_id}: exit {result.returncode} in {result.seconds:.0f}s")
    if result.returncode != 0:
        state.notes.append(f"grow on {scene_id} exited {result.returncode}")
        return
    check = run_step("world check", [*base, "world", "check"], cwd, log)
    accept = run_step("world accept", [*base, "world", "accept"], cwd, log)
    log.note(f"world check exit {check.returncode}; world accept exit {accept.returncode}")
    if accept.returncode != 0:
        repaired = repair_snapshot_faults(spec, cwd, log, state)
        state.notes.append(
            f"world accept refused after grow on {scene_id} (exit {accept.returncode}); "
            + ("repaired and accepted" if repaired else "proposals left unaccepted")
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw a whole volume of one serial, arc by arc.")
    parser.add_argument(
        "--run", type=Path, required=True, help="folder for the log, store and library"
    )
    parser.add_argument(
        "--listing", type=Path, required=True, help="title.txt, listing.txt, concept.json"
    )
    parser.add_argument("--database", type=Path, help="defaults to <run>/serial.db")
    parser.add_argument("--writer", required=True)
    parser.add_argument("--roster-database", type=Path)
    parser.add_argument("--library", type=Path, help="defaults to <run>/book-library")
    parser.add_argument("--chapter-scenes", type=int, default=2)
    parser.add_argument("--arc-chapters", type=int, default=12)
    parser.add_argument("--arcs", type=int, default=4, help="closed arcs to draft in total")
    parser.add_argument(
        "--grow-every", type=int, default=1, help="chapters between Architect grows; 0 never"
    )
    parser.add_argument("--person", choices=("first", "third"), default="third")
    parser.add_argument("--max-cost-usd-per-day", type=float, default=400.0)
    parser.add_argument("--max-tokens-per-day", type=int, default=400_000_000)
    parser.add_argument("--exemplars", type=Path)
    parser.add_argument("--exemplars-limit", type=int, default=3)
    parser.add_argument("--rivals", type=Path)
    parser.add_argument("--no-readers", action="store_true", help="skip the readership at arc ends")
    parser.add_argument("--tick-delay", type=float, default=5.0)
    parser.add_argument("--failure-delay", type=float, default=90.0)
    parser.add_argument("--max-failures", type=int, default=5)
    parser.add_argument("--max-idle", type=int, default=3)
    parser.add_argument(
        "--seed-attempts",
        type=int,
        default=2,
        help="fresh seeds to try when accept refuses and the repair fails",
    )
    parser.add_argument("--litharness", default="uv run litharness")
    args = parser.parse_args(argv)

    run: Path = args.run
    run.mkdir(parents=True, exist_ok=True)
    spec = Spec(
        run=run,
        listing=args.listing,
        database=args.database or run / "serial.db",
        writer=args.writer,
        roster_database=args.roster_database,
        library=args.library or run / "book-library",
        chapter_scenes=args.chapter_scenes,
        arc_chapters=args.arc_chapters,
        arcs=args.arcs,
        grow_every=args.grow_every,
        person=args.person,
        max_cost_usd_per_day=args.max_cost_usd_per_day,
        max_tokens_per_day=args.max_tokens_per_day,
        exemplars=args.exemplars,
        exemplars_limit=args.exemplars_limit,
        rivals=args.rivals,
        tick_delay=args.tick_delay,
        failure_delay=args.failure_delay,
        max_failures=args.max_failures,
        max_idle=args.max_idle,
        litharness=tuple(args.litharness.split()),
        readers_at_arc_end=not args.no_readers,
        seed_attempts=args.seed_attempts,
    )
    cwd = Path.cwd()
    log = Log(run)
    state = RunState(started=datetime.now(tz=UTC).isoformat(), tree_at_start=tree_state(cwd))
    save(run, state, spec)
    log.note(
        f"volume run: {spec.arcs} arc(s) of {spec.scenes_per_arc} scene(s), "
        f"grow every {spec.grow_every} chapter(s)"
    )

    try:
        current = probe(spec.database)
        if not current.exists:
            if not stand_up(spec, cwd, log, state):
                return finish(run, log, state, spec, 1)
            current = probe(spec.database)
        else:
            log.note(f"resuming: {current.drafted} of {current.total} scene(s) drafted")
        state.chapters_complete = current.drafted // spec.chapter_scenes
        state.last_grow_chapter = state.chapters_complete

        while True:
            control = read_control(run)
            if control.get("stop"):
                state.stopped = "control.json asked to stop"
                break
            if control.get("pause"):
                log.note("paused by control.json; checking again in 60s")
                time.sleep(60)
                continue
            asked = control.get("grow_every")
            grow_every = int(asked) if isinstance(asked, int | str) else spec.grow_every

            current = probe(spec.database)
            for row in current.stale:
                if row not in state.notes:
                    state.notes.append(row)
                    log.note(row[:200])
            if current.trouble:
                state.stopped = "needs a person: " + "; ".join(current.trouble)
                break
            if current.drafted >= current.total:
                arcs_drafted = current.total // spec.scenes_per_arc
                log.note(
                    f"arc {arcs_drafted} complete: {current.drafted} of {current.total} scene(s)"
                )
                if spec.readers_at_arc_end and current.drafted_ids:
                    readers_argv = [*spec.base(), "readers", "--scene", current.drafted_ids[-1]]
                    if spec.rivals is not None:
                        readers_argv += ["--rivals", str(spec.rivals)]
                    result = run_step(f"readers arc {arcs_drafted}", readers_argv, cwd, log)
                    state.readers_runs += 1
                    log.note(f"readers on {current.drafted_ids[-1]}: exit {result.returncode}")
                if arcs_drafted >= spec.arcs:
                    state.finished = datetime.now(tz=UTC).isoformat()
                    break
                result = run_step("extend", [*spec.base(), "extend", "--arcs", "1"], cwd, log)
                state.extends += 1
                if result.returncode != 0:
                    state.stopped = f"extend exited {result.returncode}"
                    break
                log.note(f"extended by one arc; now {arcs_drafted + 1} planned")
                save(run, state, spec)
                continue

            before = current.drafted
            result = run_step("tick", [*spec.base(), "tick"], cwd, log)
            state.ticks += 1
            match = OUTCOME.search(result.output)
            outcome = match.group(1) if match else f"unparsed exit {result.returncode}"
            after = probe(spec.database)
            if after.drafted != before:
                log.note(
                    f"tick {state.ticks}: {outcome} · {after.drafted}/{after.total} "
                    "scene(s) drafted "
                    f"({result.seconds:.0f}s)"
                )
            else:
                log.note(f"tick {state.ticks}: {outcome} ({result.seconds:.0f}s)")

            if outcome in {"ran_job", "replayed"}:
                state.failures = 0
                state.idle = 0
            elif outcome == "no_work":
                state.idle += 1
                if state.idle >= spec.max_idle:
                    state.stopped = (
                        f"{state.idle} idle tick(s) with {after.drafted} of {after.total} drafted; "
                        "nothing is claimable"
                    )
                    break
                time.sleep(30)
            elif outcome == "job_parked":
                state.stopped = "a unit parked: " + "; ".join(
                    after.trouble or ("see commands.log",)
                )
                break
            else:
                state.failures += 1
                if after.trouble:
                    state.stopped = "needs a person: " + "; ".join(after.trouble)
                    break
                if state.failures >= spec.max_failures:
                    state.stopped = f"{state.failures} consecutive failed tick(s)"
                    break
                time.sleep(spec.failure_delay)

            chapters = after.drafted // spec.chapter_scenes
            if chapters > state.chapters_complete:
                state.chapters_complete = chapters
                log.note(f"chapter {chapters} complete")
                if grow_every > 0 and chapters - state.last_grow_chapter >= grow_every:
                    grow(spec, cwd, log, state, after.drafted_ids[-1])
                    state.last_grow_chapter = chapters
            save(run, state, spec)
            time.sleep(spec.tick_delay)
    except KeyboardInterrupt:
        state.stopped = "interrupted"
    return finish(run, log, state, spec, 0 if state.finished else 1)


def finish(run: Path, log: Log, state: RunState, spec: Spec, code: int) -> int:
    cwd = Path.cwd()
    if spec.database.exists():
        run_step("library", [*spec.base(), "library"], cwd, log)
        try:
            (run / "spend.json").write_text(
                json.dumps(read_spend(spec.database), indent=2), encoding="utf-8"
            )
        except Exception as error:
            state.notes.append(f"spend unreadable: {error}")
    state.tree_at_finish = tree_state(cwd)
    save(run, state, spec)
    if state.finished:
        log.note(f"FINISHED: {spec.arcs} arc(s) drafted")
    else:
        log.note(f"STOPPED: {state.stopped}")
    return code


if __name__ == "__main__":
    sys.exit(main())
