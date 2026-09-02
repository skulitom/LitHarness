"""The settled-listing redraw, as a convention rather than a command somebody retypes.

**What this is.** `plan/continuous-loop-direction.md` build 2. Pilots 15b and 18 ran the same
recipe by hand four and four times: stand a *settled* listing — title and premise, byte for
byte — up on a fresh store, seed a world, accept it, tick until chapter 1 exists, publish.
Between those draws the pipeline changed, and the whole value of the exercise is that the
listing did not. This script is that recipe written down, with the parts a person kept in
their head turned into refusals.

**What it is not.** It is not a treatment comparison, and nothing it writes may be read as
one. Two draws under one listing are two draws (`plan/serial-pilot-15b.md` §0, the standing
boundary). Every arm here is a *description* of a book; laying two descriptions side by side
is what the folder convention is for, and a person — or a later qualified mechanism — reads
them. Nothing in this file ranks, scores or selects (§61(5), §84).

**The standing caution, and it is why the EXPERIMENT.md is mandatory.** stage-0 §105 measured
an agentic variation loop against the fixed path and found: *"The agentic path bought nothing
on these cases and cost 2.25x the calls."* Its anti-scope carries forward — *"No general prose
hill-climbing, and no selection among mechanically valid candidates by any quality proxy,
score, ranking or preference signal."* An A/B harness is exactly the machine that makes
undirected variation cheap, so the discipline is structural: an arm will not run until a
person has written down, in the experiment folder, which diagnosed defect the variant answers
and which §-entries the two arms differ by.

**Usage** (from the repository root):

    # 1. open the experiment and fill in its EXPERIMENT.md by hand
    uv run python tools/ab_redraw.py --experiment reviser-off --init-experiment

    # 2. rehearse: the exact commands, nothing spent
    uv run python tools/ab_redraw.py --experiment reviser-off --arm a \\
        --listing runs/pilots/pilot18/draw2 --writer ferreira \\
        --database runs/ab/reviser-off/a/serial.db \\
        --max-cost-usd-per-day 40 --max-tokens-per-day 20000000 --dry-run

    # 3. run it, one arm at a time
    uv run python tools/ab_redraw.py --experiment reviser-off --arm a ... # (no --dry-run)

**One arm at a time is a refusal, not a comment.** CLAUDE.md: `claude -p` fails under box
load rather than under its own concurrency, and the failure is silent-ish — a failing call
still returns and the run completes with unanswered cells. A pid lock at the runs root is
what makes a second arm refuse instead of quietly ruining both. It covers *this harness's*
arms and nothing else: it cannot see a pytest run, a GPU job or an Architect run started
elsewhere on the box, and the box rule still needs a person to check the process list.

**No paid call is made by this file's tests.** The build that introduced it made none at all;
the first real arm is the coordinator's, operator-gated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import locale
import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.application import library as library_module
from litharness.domain.jobs import JobStatus

REPO = Path(__file__).resolve().parent.parent

#: Where arms land. `runs/` is gitignored, which is the point: an arm is a run, not a commit.
DEFAULT_RUNS_ROOT = Path("runs/ab")

#: One holder across every experiment under one runs root, because the constraint being
#: enforced is about the box and not about the experiment.
LOCK_NAME = ".ab-redraw.lock"
#: The settled concept's file beside `title.txt` and `listing.txt` (stage-0 §197).
CONCEPT_NAME = "concept.json"

EXPERIMENT_FILENAME = "EXPERIMENT.md"

#: The template's unfilled markers. An EXPERIMENT.md that still carries one has not named its
#: variant, and `check_refusals` says so rather than letting the arm run against a stub.
FILL_MARKER = "FILL:"

#: Where build 1's per-draw scorecard is expected to land. Probed rather than depended on:
#: this harness shipped first and must degrade to "no scorecard" without failing an arm.
SCORECARD_CANDIDATES = (
    Path("research/quality-measurement/scorecard.py"),
    Path("tools/scorecard.py"),
)

#: `{script}`, `{database}`, `{shelf}` and `{destination}` are substituted. Overridable end to
#: end, because this shape is a guess made before build 1 landed and a wrong guess must not
#: become a silent absence.
#: §190's real interface is `scorecard.py <target> [--out <json>]`; the earlier guess at a
#: `--database --json` shape failed on the first live arm at $0 and is corrected here.
#: The contract any template is held to: the script writes its JSON to `{destination}`, and
#: whatever it prints is the table. `keep_scorecard` keeps the two apart, because this harness
#: once wrote the printed table over the JSON the script had just written — pilot 21's draws
#: 2 and 3 (2026-09-02) each hold a `scorecard.json` that `json.load` refuses.
DEFAULT_SCORECARD_COMMAND = "uv run python {script} {shelf} --out {destination}"

DEFAULT_LITHARNESS = "uv run litharness"


EXPERIMENT_TEMPLATE = """# A/B redraw: {experiment}

**Status: FILL: not yet run / running / read.** Two draws under one settled listing. This
document is written BEFORE either arm runs and is the thing that makes the arms admissible.

## The standing caution (stage-0 §105, verbatim, and it does not move)

> The agentic path bought nothing on these cases and cost 2.25x the calls.

> No general prose hill-climbing, and no selection among mechanically valid candidates by any
> quality proxy, score, ranking or preference signal — enforced by an import ban, not by
> intent.

**So: a variant comes from a diagnosed defect, never from undirected variation.** Name the
defect and where it was diagnosed, or do not run the arms.

- **The diagnosed defect this answers:** FILL: what was found, in what read or instrument
  record, and where that record lives.

## The variant, by §-entry

- **Arm A** — FILL: §-entries live on this arm (or "the pipeline as merged at <sha>").
- **Arm B** — FILL: §-entries live on this arm, and nothing else differs.

The arms differ by exactly the entries named above. Anything else that moved between them is
a confound and belongs in the control statement below, named rather than assumed absent.

## The control statement (§54's shape)

§54 stated its arms as *"Same premise, same model, same budget, 30 scenes"* and then wrote
down what it could not hold constant — *"And the confound, which is not small."* Both halves
are required here.

- **Held constant:** the listing (title and premise, byte for byte — the harness records a
  sha256 of each and refuses a second arm under a different one), the writer, the scene
  count, the chapter size, both spend ceilings, a fresh store per arm.
- **Not held constant, and named:** FILL: the model version, the roster state, the date, any
  other track merged between the two arms — anything that moved besides the variant.
- **n is one per arm.** FILL: say so again in whatever this experiment concludes.

## What this experiment may and may not produce

A description of two books, side by side. It may not produce a win, a rank, a score, a bar,
or a treatment effect: two draws are two draws (`plan/serial-pilot-15b.md` §0), and no bar is
declared anywhere without §61's four attainability checks. A person reads the two folders.

## The reading

FILL: written after both arms land — what the two descriptions show, what they cannot show,
and what is owed.
"""


class Refusal(Exception):
    """A structural refusal. Exit code 2, and nothing was run."""


class Stopped(Exception):
    """The arm stopped loudly mid-recipe. Exit code 1, and what ran is on the log."""


# ------------------------------------------------------------------------------- the pid lock


class PidLock:
    """One arm at a time, `force_remote.SingleRun`'s discipline as the backtest carries it.

    O_CREAT | O_EXCL is the atomicity; the file carries the holder's pid so the refusal can
    name it. Released on exit; a crash leaves the file and the refusal says how to clear it,
    because silently stealing a lock is how two paid runs end up interleaved.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> PidLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = self.path.read_text(encoding="utf-8").strip() or "unknown"
            raise Refusal(
                f"another ab_redraw arm holds {self.path} (pid {holder}). One paid arm at a "
                "time: a `claude -p` call fails under box load and still returns, so two arms "
                "produce two books nobody can read a verdict off. If that process is dead, "
                "delete the lock file and re-run"
            ) from None
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        return self

    def __exit__(self, *exc: object) -> None:
        self.path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------------- the inputs


@dataclass(frozen=True)
class ArmSpec:
    """Everything one arm is, resolved from the command line before anything runs."""

    experiment: str
    arm: str
    listing: Path
    writer: str
    database: Path
    runs_root: Path = DEFAULT_RUNS_ROOT
    roster_database: Path | None = None
    library: Path | None = None
    scenes: int = 6
    chapter_scenes: int = 2
    max_ticks: int = 6
    max_cost_usd_per_day: float | None = None
    max_tokens_per_day: int | None = None
    extra_args: tuple[str, ...] = ()
    #: The grammatical person the book is created in, or `None` for the book as it was. A
    #: subcommand flag of `new` rather than a global one, so it cannot ride `extra_args` and
    #: has its own slot; `--person first` is stage-0 §195's position, and first-versus-third
    #: on one settled listing is the arm that position exists to be measured by.
    person: str | None = None
    #: The published books the simulated readership is offered instead of chapter one, as
    #: `litharness readers --rivals` reads them (stage-0 §198.2). `None` is the no-competitor
    #: control, which is what every reading before 2026-08-26 measured.
    rivals: Path | None = None
    litharness: tuple[str, ...] = tuple(shlex.split(DEFAULT_LITHARNESS))
    scorecard: Path | None = None
    scorecard_command: str = DEFAULT_SCORECARD_COMMAND

    @property
    def experiment_dir(self) -> Path:
        return self.runs_root / self.experiment

    @property
    def arm_dir(self) -> Path:
        return self.experiment_dir / self.arm

    @property
    def lock_path(self) -> Path:
        return self.runs_root / LOCK_NAME

    @property
    def library_root(self) -> Path:
        """Where this arm's shelves land: `--library` if given, else beside the database."""
        if self.library is not None:
            return self.library.expanduser().resolve()
        return library_module.root_for(self.database)


@dataclass(frozen=True)
class Listing:
    """A settled listing, read off disk with its digests.

    **The digests are the control, not a decoration.** "Same listing byte-for-byte" is the one
    thing an A/B redraw holds constant, and an assertion nobody can check is not a control —
    so each arm records the sha256 of both files and a second arm under a different listing is
    refused rather than compared.
    """

    title: str
    premise: str
    title_sha256: str
    premise_sha256: str
    #: The settled concept beside the listing (`concept.json`, stage-0 §197), or `None` for a
    #: listing drawn before the concept stage existed. Part of the control when present: a
    #: second arm under a different concept is a different book, and the digest says so.
    concept: str | None = None
    concept_sha256: str | None = None

    @property
    def digest(self) -> str:
        digest = f"{self.title_sha256}:{self.premise_sha256}"
        return digest if self.concept_sha256 is None else f"{digest}:{self.concept_sha256}"


def read_listing(directory: Path) -> Listing:
    title_path = directory / "title.txt"
    premise_path = directory / "listing.txt"
    missing = [p.name for p in (title_path, premise_path) if not p.is_file()]
    if missing:
        raise Refusal(
            f"the settled listing at {directory} is missing {', '.join(missing)}. A redraw "
            "stands up a listing that already exists; it does not draw one"
        )
    title = title_path.read_text(encoding="utf-8").strip()
    premise = premise_path.read_text(encoding="utf-8").strip()
    for name, text in (("title.txt", title), ("listing.txt", premise)):
        if not text:
            raise Refusal(f"{directory / name} is empty; there is no settled listing here")
    concept: str | None = None
    concept_path = directory / CONCEPT_NAME
    if concept_path.is_file():
        concept = concept_path.read_text(encoding="utf-8").strip()
        if not concept:
            raise Refusal(f"{concept_path} is empty; a settled concept is a file with a book in it")
    return Listing(
        title=title,
        premise=premise,
        title_sha256=hashlib.sha256(title.encode("utf-8")).hexdigest(),
        premise_sha256=hashlib.sha256(premise.encode("utf-8")).hexdigest(),
        concept=concept,
        concept_sha256=(
            hashlib.sha256(concept.encode("utf-8")).hexdigest() if concept is not None else None
        ),
    )


# ------------------------------------------------------------------------------- the refusals


def sibling_digests(spec: ArmSpec) -> dict[str, str]:
    """Listing digests already recorded by other arms of this experiment."""
    found: dict[str, str] = {}
    if not spec.experiment_dir.is_dir():
        return found
    for record in sorted(spec.experiment_dir.glob("*/arm.json")):
        if record.parent.name == spec.arm:
            continue
        try:
            payload = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        digest = payload.get("listing", {}).get("digest")
        if isinstance(digest, str):
            found[record.parent.name] = digest
    return found


def check_refusals(spec: ArmSpec, listing: Listing) -> None:
    """Every structural refusal except the lock, which is taken by the run itself.

    Ordered cheapest-to-most-surprising so the message a person sees first is the one they
    can act on fastest.
    """
    if not spec.writer.strip():
        raise Refusal(
            "--writer is required. No writer is the pipeline's control arm, and a redraw whose "
            "arms were drafted by nobody-in-particular holds nothing constant"
        )

    experiment_file = spec.experiment_dir / EXPERIMENT_FILENAME
    if not experiment_file.is_file():
        raise Refusal(
            f"{experiment_file} does not exist. §105 measured undirected variation at 2.25x "
            "the calls for nothing, so an arm does not run until a person has written down "
            "which diagnosed defect the variant answers and which §-entries the arms differ "
            f"by. Open it with: --experiment {spec.experiment} --init-experiment"
        )
    unfilled = [
        line.strip()
        for line in experiment_file.read_text(encoding="utf-8").splitlines()
        if FILL_MARKER in line
    ]
    if unfilled:
        raise Refusal(
            f"{experiment_file} still carries {len(unfilled)} unfilled {FILL_MARKER} marker(s); "
            "it names no variant yet. First: "
            + (unfilled[0][:110] + ("..." if len(unfilled[0]) > 110 else ""))
        )

    if spec.max_cost_usd_per_day is None or spec.max_tokens_per_day is None:
        missing = [
            flag
            for flag, value in (
                ("--max-cost-usd-per-day", spec.max_cost_usd_per_day),
                ("--max-tokens-per-day", spec.max_tokens_per_day),
            )
            if value is None
        ]
        raise Refusal(
            f"both spend ceilings are required; missing {', '.join(missing)}. They ride every "
            "invocation this harness makes, including in --dry-run, because a rehearsal that "
            "prints different commands from the run is not a rehearsal"
        )

    if spec.database.exists():
        raise Refusal(
            f"{spec.database} already exists. Every arm draws on a FRESH store — that is what "
            "makes the two draws comparable at all — so this harness never appends to one"
        )

    record = spec.arm_dir / "arm.json"
    if record.exists():
        raise Refusal(
            f"{record} already exists: arm {spec.arm!r} of {spec.experiment!r} is recorded. "
            "Overwriting it would leave one folder describing two books. Use a new --arm label"
        )

    for name, digest in sibling_digests(spec).items():
        if digest != listing.digest:
            raise Refusal(
                f"arm {name!r} of this experiment ran under a different listing "
                f"({digest[:12]}... against this arm's {listing.digest[:12]}...). Byte-for-byte "
                "is the only thing an A/B redraw holds constant; two listings are two books "
                "and there is nothing here to compare"
            )


# ---------------------------------------------------------------------------------- the recipe


@dataclass(frozen=True)
class Step:
    """One invocation of the recipe."""

    label: str
    argv: tuple[str, ...]
    #: The tick loop is one step run up to `repeat` times, stopping on chapter 1.
    repeat: int = 1
    note: str = ""


def prefix(spec: ArmSpec) -> list[str]:
    """The global flags every invocation carries, ceilings included.

    **Uniform on purpose.** Pilot 12 §5 lost a run to a flag remembered on some calls and not
    others, and pilot 15b's recipe answers it by carrying `--library` and `--chapter-scenes`
    "wherever they apply". Carrying the whole prefix everywhere is the version of that a
    script can hold: "both ceilings on every paid invocation" then needs nobody to know which
    invocations are paid, and `--chapter-scenes` cannot mean one thing to the planner and
    another to the packager.
    """
    argv = [*spec.litharness, "--database", str(spec.database)]
    if spec.roster_database is not None:
        argv += ["--roster-database", str(spec.roster_database)]
    if spec.library is not None:
        argv += ["--library", str(spec.library)]
    argv += [
        "--writer",
        spec.writer,
        "--chapter-scenes",
        str(spec.chapter_scenes),
        "--max-cost-usd-per-day",
        _number(spec.max_cost_usd_per_day),
        "--max-tokens-per-day",
        _number(spec.max_tokens_per_day),
    ]
    argv += spec.extra_args
    return argv


def _number(value: float | int | None) -> str:
    """A ceiling as the CLI wants it; `check_refusals` has already rejected None."""
    if value is None:  # pragma: no cover - refused upstream, kept so the type is honest
        raise Refusal("a spend ceiling reached the command builder unset")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def plan_steps(spec: ArmSpec, listing: Listing) -> list[Step]:
    """The standard recipe, in order — pilot 15b §1 and pilot 18 §3/§5/§7.

    `world accept` takes no `--force`, and this harness offers no way to pass one: accepting
    a world that contradicts itself is a person's call on a named contradiction, never a step
    a script takes to keep going.
    """
    base = prefix(spec)
    return [
        Step("init", (*base, "init")),
        Step(
            "new",
            (
                *base,
                "new",
                listing.title,
                "--premise",
                listing.premise,
                "--scenes",
                str(spec.scenes),
                *(("--person", spec.person) if spec.person else ()),
                *(
                    ("--concept", str(spec.listing / CONCEPT_NAME))
                    if listing.concept is not None
                    else ()
                ),
            ),
            note="the settled listing, byte for byte off disk",
        ),
        Step("architect seed", (*base, "architect", "seed"), note="paid"),
        Step(
            "world check",
            (*base, "world", "check"),
            note="exits 1 when the world contradicts itself; the arm stops there",
        ),
        Step("world accept", (*base, "world", "accept"), note="no --force, ever"),
        Step(
            "tick",
            (*base, "tick"),
            repeat=spec.max_ticks,
            note=f"paid; until chapter 1 ({spec.chapter_scenes} scene(s)) completes or the cap",
        ),
        Step("library", (*base, "library")),
        # **The simulated readership on chapter one, after the shelf and last** (§198.2): a
        # reading recorded beside the chapter and never a gate, so it follows the shelf and a
        # refused call loses nothing a person reads. The scene is chapter one's last; the
        # command stops the reader part-way through it and names a rival it has not opened.
        Step(
            "readers",
            (
                *base,
                "readers",
                "--scene",
                f"scene-{spec.chapter_scenes}",
                *(("--rivals", str(spec.rivals)) if spec.rivals else ()),
            ),
            note="paid; the readership's reading, recorded and never a gate",
        ),
    ]


# ------------------------------------------------------------------------------ reading it back


@dataclass(frozen=True)
class StoreState:
    """What the store says after a step. Read after every one of them."""

    exists: bool = False
    exceptions: tuple[str, ...] = ()
    poisoned: tuple[str, ...] = ()
    parked: tuple[str, ...] = ()
    scenes_drafted: int = 0
    scenes_total: int = 0
    chapter_complete: bool = False
    book_id: str = ""
    branch_id: str = ""
    shelf: str = ""

    @property
    def trouble(self) -> tuple[str, ...]:
        """Everything that means stop. Empty is the only acceptable answer."""
        return (*self.exceptions, *self.poisoned, *self.parked)


def read_store(database: Path, chapter_scenes: int, library_root: Path) -> StoreState:
    """Exceptions, terminal jobs, and how much of chapter 1 exists.

    **The exception read is the point.** CLAUDE.md's standing warning is that a failing
    `claude -p` call still returns and the run completes with unanswered cells, so "the
    command exited 0" is not evidence that the step worked. `PROVIDER_UNAVAILABLE` is the
    transport failure's name on this side of the house, and it arrives in the same table as
    every other escalation, so one read covers all of them.
    """
    if not database.exists():
        return StoreState(exists=False)
    store = SqliteStore.open(database)
    try:
        exceptions = tuple(
            f"{record.kind.value} {record.exception_id}: {record.summary}"
            for record in store.open_exceptions()
        )
        poisoned = tuple(
            f"poisoned {job.job_kind} {job.job_id}: {job.error or 'no error recorded'}"
            for job in store.jobs_by_status(JobStatus.POISONED)
        )
        parked = tuple(
            f"parked {job.job_kind} {job.job_id}: {job.error or 'no error recorded'}"
            for job in store.jobs_by_status(JobStatus.PARKED)
        )
        branches = store.branches()
        if len(branches) != 1:
            return StoreState(
                exists=True, exceptions=exceptions, poisoned=poisoned, parked=parked
            )
        book_id, branch_id, _ = branches[0]
        document = export_module.collect(
            store,
            book_id=book_id,
            branch_id=branch_id,
            generated_at=datetime.now(tz=UTC).isoformat(),
        )
        first_chapter = document.scenes[:chapter_scenes]
        return StoreState(
            exists=True,
            exceptions=exceptions,
            poisoned=poisoned,
            parked=parked,
            scenes_drafted=document.drafted,
            scenes_total=document.total,
            chapter_complete=(
                len(first_chapter) == chapter_scenes
                and all(scene.drafted for scene in first_chapter)
            ),
            book_id=book_id,
            branch_id=branch_id,
            shelf=library_module.shelf_slug(library_root, document.title, book_id),
        )
    finally:
        store.close()


def read_spend(database: Path, started: datetime, ended: datetime) -> dict[str, object]:
    """What this arm cost, off `policy_decisions` — the durable record of what was consumed.

    Summed over the UTC days the run touched rather than "today", because an arm that starts
    at 23:50 and finishes at 00:20 would otherwise report a fraction of itself as the whole.
    The store is fresh per arm, so this total is the arm's.
    """
    if not database.exists():
        return {"invocations": 0, "tokens": 0, "cost_usd": 0.0, "days": []}
    store = SqliteStore.open(database)
    try:
        days: list[str] = []
        cursor = started.date()
        while cursor <= ended.date():
            days.append(cursor.isoformat())
            cursor = cursor + timedelta(days=1)
        invocations = tokens = 0
        cost = 0.0
        per_day: dict[str, dict[str, object]] = {}
        for day in days:
            spend = store.spend_on(day)
            invocations += spend.invocations
            tokens += spend.tokens
            cost += spend.cost_usd
            per_day[day] = {
                "invocations": spend.invocations,
                "tokens": spend.tokens,
                "cost_usd": round(spend.cost_usd, 4),
            }
        return {
            "invocations": invocations,
            "tokens": tokens,
            "cost_usd": round(cost, 4),
            "days": per_day,
            "source": "policy_decisions",
            "caveat": (
                "reported cost is a floor rather than a total (serial pilot 12 §5): a "
                "provider that reports no cost contributes zero"
            ),
        }
    finally:
        store.close()


def shelf_files(library_root: Path, shelf: str) -> list[str]:
    """The published paths, so the coordinator's read has a folder to open."""
    root = library_root / shelf
    if not shelf or not root.is_dir():
        return []
    return sorted(
        str(path.relative_to(library_root).as_posix()) for path in root.rglob("*") if path.is_file()
    )


# ------------------------------------------------------------------------------------ the runner


@dataclass
class StepResult:
    label: str
    argv: tuple[str, ...]
    returncode: int
    seconds: float
    output: str


def decode_output(raw: bytes) -> str:
    """A step's output as text: UTF-8 where it is UTF-8, the console codepage where it is not.

    Children disagree about what they print in. §190's scorecard reconfigures its stdout to
    UTF-8 — its `--out` help names the console codepage as what mangles an em dash — while a
    child that never reconfigures prints in that codepage. `text=True` decoded both as the
    codepage, which is how the section sign reached the first live arms' folders as two
    characters. UTF-8 goes first because codepage text with a high byte in it is almost never
    valid UTF-8; the fallback replaces rather than raises, because a step's output is evidence
    and never a reason to fail the step. Line endings are folded the way `text=True` folded
    them, so nothing downstream sees a difference but the characters.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode(locale.getpreferredencoding(False), errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def subprocess_runner(label: str, argv: Sequence[str], cwd: Path) -> StepResult:
    started = datetime.now(tz=UTC)
    # argv is built in this file and handed to the OS as a list; nothing is shell-interpolated.
    # Bytes rather than `text=True`: the decoding is `decode_output`'s, one stream at a time.
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    elapsed = (datetime.now(tz=UTC) - started).total_seconds()
    return StepResult(
        label=label,
        argv=tuple(argv),
        returncode=completed.returncode,
        seconds=elapsed,
        output=decode_output(completed.stdout or b"") + decode_output(completed.stderr or b""),
    )


def idle(result: StepResult) -> bool:
    """Did this tick find nothing to do? `run-loop.ps1`'s own test, and the same string."""
    return "no_work" in result.output.casefold()


@dataclass
class ArmRun:
    """What happened, accumulated as it happens so a stop still leaves a readable folder."""

    spec: ArmSpec
    listing: Listing
    started_at: str
    steps: list[StepResult] = field(default_factory=list)
    stopped: str = ""
    state: StoreState = field(default_factory=StoreState)
    ticks: int = 0


def run_arm(
    spec: ArmSpec,
    listing: Listing,
    *,
    runner: Callable[[str, Sequence[str], Path], StepResult] = subprocess_runner,
    probe: Callable[[Path, int, Path], StoreState] = read_store,
    cwd: Path = REPO,
) -> ArmRun:
    """The recipe, with the store read after every step.

    **Always returns the run, stop or no stop.** `Stopped` is caught here rather than thrown
    at the caller because the folder is the deliverable: a stopped arm is precisely the one
    somebody needs the command log of, and an exception that escaped with the accumulated
    steps inside it would leave an empty folder behind the failure.
    """
    run = ArmRun(spec=spec, listing=listing, started_at=datetime.now(tz=UTC).isoformat())

    # sqlite cannot create intermediate directories, and the first live arm proved it: `init`
    # exited 2 on a database whose arm folder did not exist yet, then the folder appeared when
    # this module wrote the command log into it, so the same command by hand succeeded and the
    # failure read as a mystery. The folder is made before the first step, not at the write.
    spec.database.parent.mkdir(parents=True, exist_ok=True)
    spec.arm_dir.mkdir(parents=True, exist_ok=True)

    def look() -> StoreState:
        run.state = probe(spec.database, spec.chapter_scenes, spec.library_root)
        return run.state

    try:
        for step in plan_steps(spec, listing):
            if step.label == "tick":
                _tick_loop(spec, step, run, runner, look, cwd)
                continue
            result = runner(step.label, step.argv, cwd)
            run.steps.append(result)
            # A refused reading is recorded and does not stop the arm: the chapter is on the
            # shelf already, and a reading that did not happen is a line in the folder,
            # not a halted book (§198.2).
            if result.returncode != 0 and step.label != "readers":
                detail = (
                    ". `world check` exits 1 when the world contradicts itself by arithmetic. "
                    "The standing allowance is ONE re-seed on mechanical complaints and it is "
                    "a person's call; this harness will not spend it, and will never pass "
                    "`--force` to `world accept`"
                    if step.label == "world check"
                    else ""
                )
                raise Stopped(f"`{step.label}` exited {result.returncode}{detail}")
            state = look()
            if state.trouble:
                raise Stopped(f"after `{step.label}`: " + "; ".join(state.trouble))
    except Stopped as halt:
        run.stopped = str(halt)
    return run


def _tick_loop(
    spec: ArmSpec,
    step: Step,
    run: ArmRun,
    runner: Callable[[str, Sequence[str], Path], StepResult],
    look: Callable[[], StoreState],
    cwd: Path,
) -> None:
    """Tick until chapter 1 exists, and stop loudly on every other way of ending.

    Pilot 15b's loop "stopped itself at tick 4 ... so the gate on everything past chapter 1
    held by construction rather than by remembering to stop". Three endings are failures and
    are named as such: a non-zero tick, an idle queue with the chapter unfinished, and the cap.
    """
    for ordinal in range(1, step.repeat + 1):
        result = runner(f"tick {ordinal}/{step.repeat}", step.argv, cwd)
        run.steps.append(result)
        run.ticks = ordinal
        if result.returncode != 0:
            raise Stopped(f"`tick` {ordinal} exited {result.returncode}")
        state = look()
        if state.trouble:
            raise Stopped(f"after tick {ordinal}: " + "; ".join(state.trouble))
        if state.chapter_complete:
            return
        if idle(result):
            raise Stopped(
                f"the queue went idle at tick {ordinal} with chapter 1 at "
                f"{state.scenes_drafted} of {spec.chapter_scenes} scene(s) drafted. Nothing is "
                "claimable and the chapter will not finish on its own"
            )
    raise Stopped(
        f"the tick cap ({step.repeat}) was reached with chapter 1 at "
        f"{run.state.scenes_drafted} of {spec.chapter_scenes} scene(s) drafted. Raise "
        "--max-ticks only after reading why it took them"
    )


# --------------------------------------------------------------------------------- the scorecard


def find_scorecard(explicit: Path | None, repo: Path = REPO) -> Path | None:
    """Build 1's per-draw scorecard, if it has landed. Probed, never required.

    This harness shipped before it. An arm that cannot find a scorecard is an arm without a
    scorecard column, not a failed arm — and a scorecard that is present but does not answer
    to this invocation shape is recorded as `failed` with its output, so the absence has a
    reason rather than being silence.
    """
    if explicit is not None:
        return explicit if explicit.is_file() else None
    for candidate in SCORECARD_CANDIDATES:
        path = repo / candidate
        if path.is_file():
            return path
    return None


def run_scorecard(
    spec: ArmSpec,
    state: StoreState,
    destination: Path,
    *,
    runner: Callable[[str, Sequence[str], Path], StepResult] = subprocess_runner,
    repo: Path = REPO,
) -> dict[str, object]:
    script = find_scorecard(spec.scorecard, repo)
    if script is None:
        return {
            "status": "absent",
            "detail": "no per-draw scorecard found; probed "
            + ", ".join(path.as_posix() for path in SCORECARD_CANDIDATES),
        }
    # **Split the template, then substitute — never the other way around.** `shlex.split` runs
    # in POSIX mode, where a backslash escapes the next character, so splitting a command that
    # already carries `C:\DEV\...\serial.db` silently eats every separator and hands the
    # scorecard a path to a file that does not exist. Substituting into already-split tokens
    # keeps a Windows path whole.
    argv = [
        token.format(
            script=str(script),
            database=str(spec.database),
            shelf=str(spec.library_root / state.shelf) if state.shelf else "",
            destination=str(destination),
        )
        for token in shlex.split(spec.scorecard_command)
    ]
    result = runner("scorecard", argv, repo)
    if result.returncode != 0:
        return {
            "status": "failed",
            "script": str(script),
            "argv": list(argv),
            "returncode": result.returncode,
            "detail": result.output[-2000:],
        }
    kept = keep_scorecard(destination, result.output)
    return {
        "status": kept.pop("status"),
        "script": str(script),
        "argv": list(argv),
        **kept,
    }


def keep_scorecard(destination: Path, printed: str) -> dict[str, object]:
    """Leave the JSON where the script wrote it, and the printed table beside it as `.md`.

    §190's script writes its JSON to `--out` and prints its table, and this harness's first
    live arms wrote that stdout over the file the script had just written: pilot 21's draws 2
    and 3 (2026-09-02) each hold a `scorecard.json` that is the table, which `json.load`
    refuses. So the two are kept apart, and the JSON is loaded before the arm calls it
    written — a `scorecard.json` that exists is one that parses, or it is moved aside and the
    record says so. The table is fenced, because a Markdown viewer would otherwise reflow its
    columns into prose. Nothing here reads a value: the JSON is parsed, never interpreted.
    """
    if not destination.is_file():
        return {
            "status": "unparsed",
            "detail": (
                f"the scorecard exited 0 and wrote nothing at {destination}; the command "
                "template must carry `--out {destination}`, which holds the JSON while "
                "stdout holds the table"
            ),
        }
    try:
        json.loads(destination.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        aside = destination.with_suffix(".unparsed.txt")
        destination.replace(aside)
        return {
            "status": "unparsed",
            "detail": f"{destination.name} did not parse ({exc}); moved to {aside.name}",
        }
    record: dict[str, object] = {"status": "written", "path": destination.name, "table": None}
    body = printed.strip("\r\n")
    if body.strip():
        table = destination.with_suffix(".md")
        table.write_text(f"```text\n{body}\n```\n", encoding="utf-8", newline="\n")
        record["table"] = table.name
    return record


# -------------------------------------------------------------------------------- what it writes


def write_folder(run: ArmRun, *, scorecard: dict[str, object], spend: dict[str, object]) -> Path:
    """`runs/ab/<experiment>/<arm>/` — the command log, the spend, the shelf, the scorecard.

    The scorecard is two files when it ran: `scorecard.json`, which loads, and `scorecard.md`,
    the table it printed. `run_scorecard` leaves those; this writes the rest and the record.
    """
    directory = run.spec.arm_dir
    directory.mkdir(parents=True, exist_ok=True)

    log = [
        f"# {run.spec.experiment} / {run.spec.arm}",
        f"# started {run.started_at}",
        f"# listing {run.spec.listing} digest {run.listing.digest}",
        "",
    ]
    for result in run.steps:
        log.append(f"$ {shlex.join(result.argv)}")
        log.append(f"# {result.label} · exit {result.returncode} · {result.seconds:.1f}s")
        log.extend(f"    {line}" for line in result.output.splitlines())
        log.append("")
    if run.stopped:
        log.append(f"# STOPPED: {run.stopped}")
    (directory / "commands.log").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    for result in run.steps:
        if result.label == "readers":
            (directory / "readers.txt").write_text(
                result.output, encoding="utf-8", newline="\n"
            )

    (directory / "spend.json").write_text(
        json.dumps(spend, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    files = shelf_files(run.spec.library_root, run.state.shelf)
    if run.state.shelf:
        shelf_text = "\n".join([str(run.spec.library_root / run.state.shelf), *files]) + "\n"
    else:
        shelf_text = "no shelf: this arm published nothing\n"
    (directory / "shelf.txt").write_text(shelf_text, encoding="utf-8", newline="\n")

    record: dict[str, object] = {
        "experiment": run.spec.experiment,
        "arm": run.spec.arm,
        "started_at": run.started_at,
        "finished_at": datetime.now(tz=UTC).isoformat(),
        "listing": {
            "directory": str(run.spec.listing),
            "title_sha256": run.listing.title_sha256,
            "premise_sha256": run.listing.premise_sha256,
            "concept_sha256": run.listing.concept_sha256,
            "digest": run.listing.digest,
        },
        "writer": run.spec.writer,
        "database": str(run.spec.database),
        "scenes": run.spec.scenes,
        "chapter_scenes": run.spec.chapter_scenes,
        "ticks": run.ticks,
        "extra_args": list(run.spec.extra_args),
        "person": run.spec.person,
        "rivals": str(run.spec.rivals) if run.spec.rivals else None,
        "ceilings": {
            "max_cost_usd_per_day": run.spec.max_cost_usd_per_day,
            "max_tokens_per_day": run.spec.max_tokens_per_day,
        },
        "steps": [
            {
                "label": result.label,
                "argv": list(result.argv),
                "returncode": result.returncode,
                "seconds": round(result.seconds, 2),
            }
            for result in run.steps
        ],
        "store": asdict(run.state),
        "shelf": {
            "root": str(run.spec.library_root),
            "slug": run.state.shelf,
            "files": files,
        },
        "spend": spend,
        "scorecard": scorecard,
        "stopped": run.stopped,
        "boundary": (
            "One arm is a description of one book. Two arms are two draws, never a treatment "
            "effect (plan/serial-pilot-15b.md §0). Nothing here is a bar, a rank or a score."
        ),
    }
    (directory / "arm.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return directory


def init_experiment(runs_root: Path, experiment: str) -> Path:
    """Open the experiment folder with an unfilled EXPERIMENT.md. Never overwrites one.

    Takes the two things it needs rather than an `ArmSpec`, because opening an experiment
    happens before any arm exists and a spec assembled from placeholder paths would be a lie
    the signature told.
    """
    path = runs_root / experiment / EXPERIMENT_FILENAME
    if path.exists():
        raise Refusal(f"{path} already exists; a filled experiment note is not regenerated")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        EXPERIMENT_TEMPLATE.format(experiment=experiment), encoding="utf-8", newline="\n"
    )
    return path


def rehearsal(spec: ArmSpec, listing: Listing) -> str:
    """The exact commands, and nothing spent."""
    lines = [
        f"# dry run · {spec.experiment} / {spec.arm} · nothing below was executed",
        f"# listing {spec.listing} · digest {listing.digest}",
        f"# results would land in {spec.arm_dir}",
    ]
    if spec.lock_path.exists():
        holder = spec.lock_path.read_text(encoding="utf-8").strip() or "unknown"
        lines.append(
            f"# NOTE: {spec.lock_path} is held right now (pid {holder}); a real arm would refuse"
        )
    lines.append("")
    for step in plan_steps(spec, listing):
        if step.note:
            lines.append(f"# {step.label}: {step.note}")
        lines.append(shlex.join(step.argv))
        if step.repeat > 1:
            lines.append(f"#   ... repeated up to {step.repeat} times")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------ the parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ab_redraw",
        description="The settled-listing redraw, one arm at a time.",
    )
    parser.add_argument("--experiment", required=True, help="names runs/ab/<experiment>/")
    parser.add_argument("--arm", default="", help="names runs/ab/<experiment>/<arm>/")
    parser.add_argument(
        "--init-experiment",
        action="store_true",
        help="write the EXPERIMENT.md template and exit; run no arm",
    )
    parser.add_argument(
        "--listing", type=Path, help="a settled listing directory holding title.txt and listing.txt"
    )
    parser.add_argument("--writer", default="", help="the roster id drafting both arms")
    parser.add_argument("--database", type=Path, help="a store that does not exist yet")
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--roster-database", type=Path, default=None)
    parser.add_argument("--library", type=Path, default=None)
    parser.add_argument("--scenes", type=int, default=6)
    parser.add_argument("--chapter-scenes", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=6, help="the tick cap (default: 6)")
    parser.add_argument("--max-cost-usd-per-day", type=float, default=None)
    parser.add_argument("--max-tokens-per-day", type=int, default=None)
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        dest="extra_args",
        help="a flag carried on every invocation — how a variant that IS a flag is expressed. "
        "**Write it with an equals sign**: `--extra-arg=--no-revise` (§185's control arm). "
        "Argparse reads a bare `--extra-arg --no-revise` as a missing value followed by an "
        "unknown option, and refuses. Repeatable; recorded in arm.json",
    )
    parser.add_argument(
        "--person",
        choices=("first", "third"),
        default=None,
        help="the grammatical person the arm's book is created in (`new --person`); a variant "
        "that is this flag is expressed here rather than through --extra-arg, because it is "
        "a flag of `new` and not of every invocation. Recorded in arm.json",
    )
    parser.add_argument(
        "--rivals",
        type=Path,
        default=None,
        help="a JSON list of published books for the readership step (`readers --rivals`); "
        "without it the readers are offered no named competitor, the control arm",
    )
    parser.add_argument("--litharness", default=DEFAULT_LITHARNESS, help="how to invoke the CLI")
    parser.add_argument("--scorecard", type=Path, default=None, help="build 1's script, explicitly")
    parser.add_argument("--scorecard-command", default=DEFAULT_SCORECARD_COMMAND)
    parser.add_argument(
        "--dry-run", action="store_true", help="print the exact commands; spend nothing"
    )
    return parser


def spec_from(args: argparse.Namespace) -> ArmSpec:
    if args.listing is None or args.database is None:
        raise Refusal("--listing and --database are both required to run an arm")
    if not args.arm:
        raise Refusal("--arm is required: it names the folder this draw is recorded in")
    return ArmSpec(
        experiment=args.experiment,
        arm=args.arm,
        listing=args.listing,
        writer=args.writer,
        database=args.database,
        runs_root=args.runs_root,
        roster_database=args.roster_database,
        library=args.library,
        scenes=args.scenes,
        chapter_scenes=args.chapter_scenes,
        max_ticks=args.max_ticks,
        max_cost_usd_per_day=args.max_cost_usd_per_day,
        max_tokens_per_day=args.max_tokens_per_day,
        extra_args=tuple(args.extra_args),
        person=args.person,
        rivals=args.rivals,
        litharness=tuple(shlex.split(args.litharness)),
        scorecard=args.scorecard,
        scorecard_command=args.scorecard_command,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.init_experiment:
            path = init_experiment(args.runs_root, args.experiment)
            print(f"wrote {path}")
            print(f"Fill every {FILL_MARKER} marker before an arm will run.")
            return 0

        spec = spec_from(args)
        listing = read_listing(spec.listing)
        check_refusals(spec, listing)

        if args.dry_run:
            print(rehearsal(spec, listing))
            return 0
    except Refusal as refusal:
        print(f"ab_redraw: REFUSED — {refusal}", file=sys.stderr)
        return 2

    try:
        with PidLock(spec.lock_path):
            started = datetime.now(tz=UTC)
            run = run_arm(spec, listing)
            spend = read_spend(spec.database, started, datetime.now(tz=UTC))
            scorecard: dict[str, object] = (
                {"status": "skipped", "detail": "the arm stopped before it had a draw"}
                if run.stopped
                else run_scorecard(spec, run.state, spec.arm_dir / "scorecard.json")
            )
            spec.arm_dir.mkdir(parents=True, exist_ok=True)
            directory = write_folder(run, scorecard=scorecard, spend=spend)
    except Refusal as refusal:
        print(f"ab_redraw: REFUSED — {refusal}", file=sys.stderr)
        return 2

    headline = "STOPPED" if run.stopped else "drew chapter 1"
    print(f"=== {spec.experiment} / {spec.arm} · {headline} ===")
    print(f"folder    {directory}")
    print(f"listing   {spec.listing} · digest {run.listing.digest}")
    print(
        f"spend     {spend['invocations']} call(s), {spend['tokens']} token(s), "
        f"${spend['cost_usd']}"
    )
    print(f"shelf     {run.state.shelf or 'none published'}")
    print(f"scorecard {scorecard['status']}")
    if run.stopped:
        print()
        print(f"STOPPED: {run.stopped}")
        print("Read commands.log before re-running anything; a call that returned is not a")
        print("call that worked (CLAUDE.md's silent-ish failure).")
        return 1
    print()
    print("One arm is one description of one book. Two arms are two draws, never a treatment")
    print("effect. Fill in the experiment's reading; nothing here declares a bar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
