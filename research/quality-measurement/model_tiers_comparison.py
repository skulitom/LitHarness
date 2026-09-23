"""Model tiers (`model-tiers.v1`): may the candidate roles of docs/model-policy.md move tier?

`model-tiers-20260922/PREREG.md` is the registration: the claim, the design, the outcomes, the
decision rule and what it cannot establish. `RUNBOOK.md` owns the commands. This module carries
the frozen constants, the plan, the prepare / run / analyse legs and the reading. It edits
nothing in production and decides nothing there: a pass licenses proposing a tier change to the
operator, and the policy's rule that "the review recommends; it never changes routing" holds.

**Scene summaries, the one role a pass can license proposing, on the Codex provider only.**
Profile `mechanical` (`application/summarize.py`), the basic-tier candidate, in two blocks:

* *Recorded wording.* The 24 summary requests the full-book trial recorded under
  `runs/full-book-trial-20260919/calls/` are replayed byte for byte on `gpt-6-astra` at medium
  effort (the control: the strong model's own re-run against its own accepted record),
  `gpt-6-luna` at medium and `gpt-6-luna` at high, and read against the accepted records.
* *Current wording.* Stage-0 §255 reworded the summary prompt after the trial, so each request
  is rebuilt from the scene and the trial's own `promises` rows the recorded ledger listed:
  under the trial's frozen runtime those rows must rebuild the recorded request whole, byte for
  byte, and under the pinned registration source they give the request production sends now.
  Those bytes run on two `gpt-6-astra` replicates (a reference and a floor) and both Luna cells;
  with no accepted record for this wording, a candidate's agreement with the reference is read
  against the second Astra's.

Outcomes are the pipeline's own parse and tolerant reads, a strict check of the registered
schema, exact evidence location, whether a paid subject is off the list it was shown, which
listed promises the answer settles, and field-level agreement, all computed here.

**The Architect's seed is a screen, never a licence.** The seed request is rebuilt by the
production CLI from the trial's pre-seed store and run on `gpt-6-sol` and `gpt-6-astra`, two
replicates each, each into a fresh copy of that store. Two replicates can show a gross failure
and cannot establish reliability, so no outcome of the seed proposes anything.

**No model rates, ranks or chooses anything a claim depends on.** Every outcome is code over the
answers; no prose field is scored for quality; the verdict is arithmetic over pre-declared
margins. Transport failures are counted before any verdict and are never kept as answers
(stage-0 §224, §235). The request of every summary unit carries no model: the cell's model and
effort are the Codex adapter's own settings (`CodexCliProvider(model=..., model_efforts=...)`),
so every cell of a block sends the same bytes and only `--model` and the effort differ.

**Everything runs on pinned copies, so later commits change nothing the arm runs.** `prepare`
archives HEAD's `src/`, `migrations/`, `pyproject.toml` and `uv.lock` under
`runs/model-tiers-20260922/source/`, builds `runs/model-tiers-20260922/runtime/` whose `.pth`
points there (the full-book trial's `runtimes/A` pattern), and copies the registered Codex bin
folder whole (the executable sits beside its helpers). `run` and `analyse` refuse unless they
execute under that runtime, so the adapter, the tool bridge (`sys.executable -m litharness`)
and the world CLI of the reading all run the archived source, whose whole tree is hashed before
every call.

    uv run python research/quality-measurement/model_tiers_comparison.py plan
    uv run python research/quality-measurement/model_tiers_comparison.py prepare \\
        --codex-binary <native codex.exe>
    runs/model-tiers-20260922/runtime/Scripts/python.exe \\
        research/quality-measurement/model_tiers_comparison.py run
    uv run python research/quality-measurement/model_tiers_comparison.py close   # after a kill
    runs/model-tiers-20260922/runtime/Scripts/python.exe \\
        research/quality-measurement/model_tiers_comparison.py analyse
    uv run python research/quality-measurement/model_tiers_comparison.py claim   # PREREG edit

Top-level imports are the standard library only: `prepare` runs this file under the trial's
frozen runtime and under the pinned runtime (`render-seed`, `render-summaries`, `open-store`),
and each interpreter must import it without importing the live checkout.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import difflib
import hashlib
import io
import json
import math
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import time
import unicodedata
import venv
import zipfile
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

VERSION = "model-tiers.v1"
LOCK_PREFIX = "model-tiers-20260922:"


@dataclass(frozen=True, slots=True)
class Cell:
    """One model at one reasoning effort on the Codex adapter."""

    name: str
    model: str
    effort: str
    arm: str  # "control", "floor" or "candidate"


ASTRA = Cell("astra-medium", "gpt-6-astra", "medium", "control")
#: The second Astra of the current-wording block: the same model, effort and bytes as the
#: reference, so its agreement with the reference is the floor a candidate is read against.
ASTRA_FLOOR = Cell("astra-medium-2", "gpt-6-astra", "medium", "floor")
LUNA_MEDIUM = Cell("luna-medium", "gpt-6-luna", "medium", "candidate")
LUNA_HIGH = Cell("luna-high", "gpt-6-luna", "high", "candidate")
#: The recorded-wording block: the recorded bytes, read against the accepted records.
SUMMARY_CELLS: tuple[Cell, ...] = (ASTRA, LUNA_MEDIUM, LUNA_HIGH)
#: The current-wording block: HEAD's (§255) bytes, read against the reference Astra.
CURRENT_CELLS: tuple[Cell, ...] = (ASTRA, ASTRA_FLOOR, LUNA_MEDIUM, LUNA_HIGH)
SUMMARY_CANDIDATES: tuple[Cell, ...] = (LUNA_MEDIUM, LUNA_HIGH)
SEED_CELLS: tuple[Cell, ...] = (ASTRA, Cell("sol-medium", "gpt-6-sol", "medium", "candidate"))
SEED_REPLICATES = 2
#: ABBA, so neither arm's seeds all sit at one end of the run.
SEED_ORDER: tuple[tuple[str, int], ...] = (
    ("astra-medium", 0), ("sol-medium", 0), ("sol-medium", 1), ("astra-medium", 1),
)
#: The adapter's `reasoning_effort`; each cell's own effort goes in `model_efforts`.
ADAPTER_EFFORT = "medium"

# ------------------------------------------------------------------ what the trial recorded

SUMMARY_PROFILE = "mechanical"
EXPECTED_SCENES = 24
RECORDED_MODEL = "gpt-6-astra"
RECORDED_EFFORT = "medium"
TRIAL_SEED_CALL = "0005-A1.json"
TRIAL_SEED_PROFILE = "architect.seed.v8"
TRIAL_ACCEPT_STEP = "accept-seed-A1-1.json"
TRIAL_SEED_STEP = "seed-A1-1.json"
#: The trial's global arguments for its book, except `--database` and `--library`, which name
#: its own files (`full-book-trial-20260919/run.py`, `base_args`).
TRIAL_GLOBAL_ARGS: tuple[str, ...] = (
    "--writer", "halloran", "--holder", "full-book-trial", "--chapter-scenes", "1",
    "--arc-chapters", "6", "--volume-chapters", "24", "--target-words", "2200",
    "--max-invocations-per-day", "300", "--max-tokens-per-day", "8000000",
)
SCENE_PREFIX = "The scene:\n\n"
#: The ledger block as the trial's source (6c3bda4, before stage-0 §255) wrote it.
LEDGER_HEADING_RECORDED = "\n\nThe book's ledger of debts still unpaid, as it stores them."
#: The ledger block as HEAD writes it since stage-0 §255.
LEDGER_HEADING_CURRENT = "\n\nThe book's open promises, as it stores them."
#: Both versions open the thread block with these words.
THREAD_HEADING = "\n\nThe book records these threads"
LEDGER_LINE = re.compile(r"^- (\S+) owes: ", re.MULTILINE)
LEDGER_LINE_CURRENT = re.compile(r"^- (\S+): ", re.MULTILINE)
DEFAULT_SYSTEM = "Complete the user's requested task."
#: The `promises` columns a ledger line is rendered from, plus identity; every other column
#: (payment, evidence anchors) postdates the call or does not reach the prompt, and the frozen
#: rebuild proves the rendered bytes whatever is left out.
LEDGER_ROW_FIELDS: tuple[str, ...] = (
    "promise_id", "subject", "description", "opened_at_key", "due_key", "opened_by_revision",
    "model", "kind", "window_start_key", "window_end_key", "scheduled_by_plan_revision",
)
#: The accept step's own report of what it did, which the seed world's reconstruction must
#: reproduce (`read_trial`).
ACCEPTED_LINE = re.compile(r"accepted (\d+) of (\d+) proposal")
MINTED_LINE = re.compile(r"(\d+) record\(s\) minted")
LEFT_LINE = re.compile(r"(\d+) left proposed")

# ------------------------------------------------------------------------- the ceilings

LIMITS: dict[str, float] = {"calls": 240, "tokens": 7_000_000, "seconds": 14_400}
#: Worst-case admission charge per call, and the charge for an attempt whose usage is unknown.
RESERVE: dict[str, dict[str, float]] = {
    "summary": {"tokens": 40_000, "seconds": 300.0},
    "seed": {"tokens": 1_500_000, "seconds": 3_600.0},
}
MAX_ATTEMPTS = 2
TRANSPORT_CIRCUIT = 3

# ---------------------------------------------------------------------- the decision rule

ALPHA = 0.05
#: Candidate cells per role; the one-sided level of each candidate's tests is ALPHA / this.
#: The seed has no entry: it is a screen and tests nothing (PREREG, "The seed screen").
CANDIDATES: dict[str, int] = {"summary": 2}
VALIDATOR_MARGIN = 0.15
#: The candidate's excess rate of scenes whose settled-promise set differs from the reference,
#: over the control's own: 0.25 is 6 of 24 scenes.
SETTLEMENT_MARGIN = 0.25
AGREEMENT_MARGIN = 0.10
SEED_AGREEMENT_MARGIN = 0.25
#: Student t, one-sided 0.975 quantile at 23 degrees of freedom: 24 paired scenes, alpha 0.025.
T_CRITICAL_23 = 2.0686576104190406
#: Every agreement component computed and reported per scene.
REPORTED_COMPONENTS: tuple[str, ...] = (
    "delta_presence", "delta_who", "paid_matched_set", "opened_count", "opened_kinds",
)
#: The composite's components. `paid_matched_set` has its own exact test (the settlement
#: test), and `delta_presence` is left out: it is near-constant (the record has a delta in 24
#: of 24 scenes) and `delta_who` already scores a delta present on one side only as 0.
COMPOSITE_COMPONENTS: tuple[str, ...] = ("delta_who", "opened_count", "opened_kinds")
SEED_COMPONENTS: tuple[str, ...] = (
    "protagonists", "system_count", "ladder_lengths", "grant_counts", "cast", "status_sheet",
)
PROSE_FIELDS: tuple[str, ...] = ("setting", "characters", "events", "open")
DELTA_KEYS: tuple[str, ...] = ("who", "what_changed", "from", "to")
STRUCTURED_FIELDS: tuple[str, ...] = (
    "delta.null", "delta.who", "delta.what_changed", "delta.from", "delta.to",
    "promises_opened.count", "promises_opened.subject", "promises_opened.description",
    "promises_opened.kind", "promises_opened.due_hint", "promises_opened.evidence_quote",
    "promises_paid.count", "promises_paid.subject", "promises_paid.matched",
    "promises_paid.evidence_quote",
)

# ------------------------------------------------------------------ failure classification

#: Failure kinds that name the model's act only when the attempt shows a model turn: on a
#: nonzero Codex exit they come from `classify_provider_failure` matching words in stderr.
MODEL_TURN_KINDS = frozenset({"refusal", "safety"})
#: Adapter messages that name the model's own act rather than the stream's condition.
MODEL_ACT_MARKS: tuple[str, ...] = (
    "attempted an unpermitted activity",
    "returned without any successful scoped world command",
)
#: Bridge refusals the model caused: arguments it never recovered, or the call budget it spent.
MODEL_BRIDGE_KINDS = frozenset({"invalid_arguments", "call_budget"})
ANSWER_STATUSES = frozenset({"answered", "answered_unusable"})
ISOLATION_FLAGS: tuple[str, ...] = (
    "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
)
_CLEAN_ENV_DROP = ("LITHARNESS_", "ANTHROPIC_", "OPENAI_")
_RUN_ENV_DROP: tuple[str, ...] = (
    "LITHARNESS_ROSTER_DATABASE", "LITHARNESS_RECRUIT_SHELF", "LITHARNESS_RECRUIT_SHAPE",
    "LITHARNESS_MODEL_TIERS", "LITHARNESS_CODEX_EFFORTS", "LITHARNESS_CODEX_MODELS",
    "LITHARNESS_DATABASE",
)


# ============================================================================ paths


@dataclass(frozen=True, slots=True)
class Paths:
    """Where this registration's files live. Tests point every one of them at a scratch root."""

    root: Path
    arm_dir: Path
    local: Path
    trial: Path
    trial_here: Path
    lock_holder: Path
    runner_file: Path
    test_file: Path

    @property
    def registration(self) -> Path:
        return self.arm_dir / "registration.json"

    @property
    def claim(self) -> Path:
        return self.arm_dir / "claim.json"

    @property
    def prereg(self) -> Path:
        return self.arm_dir / "PREREG.md"

    @property
    def runbook(self) -> Path:
        return self.arm_dir / "RUNBOOK.md"

    @property
    def ledger(self) -> Path:
        return self.arm_dir / "ledger.jsonl"

    @property
    def results(self) -> Path:
        return self.arm_dir / "results.json"

    @property
    def inputs_dir(self) -> Path:
        return self.local / "inputs"

    @property
    def summary_inputs(self) -> Path:
        return self.inputs_dir / "summaries.json"

    @property
    def seed_inputs(self) -> Path:
        return self.inputs_dir / "seed.json"

    @property
    def seed_template(self) -> Path:
        return self.inputs_dir / "pre-seed.db"

    @property
    def calls_dir(self) -> Path:
        return self.local / "calls"

    @property
    def transport_dir(self) -> Path:
        return self.local / "transport"

    @property
    def seeds_dir(self) -> Path:
        return self.local / "seeds"

    @property
    def analysis_dir(self) -> Path:
        return self.local / "analysis"

    @property
    def trial_store(self) -> Path:
        return self.trial / "books" / "A1" / "book.db"

    @property
    def pre_seed_store(self) -> Path:
        return self.trial / "runner-stop" / "book.db"

    @property
    def frozen_python(self) -> Path:
        return self.trial / "runtimes" / "A" / "Scripts" / "python.exe"

    @property
    def frozen_source(self) -> Path:
        return self.trial / "sources" / "A" / "src"

    @property
    def source_archive(self) -> Path:
        """`git archive` of the registration commit's production files."""
        return self.local / "source.zip"

    @property
    def source_dir(self) -> Path:
        """That archive extracted: `src/`, `migrations/`, `pyproject.toml`, `uv.lock`."""
        return self.local / "source"

    @property
    def runtime_dir(self) -> Path:
        return self.local / "runtime"

    @property
    def runtime_python(self) -> Path:
        scripts = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
        return self.runtime_dir.joinpath(*scripts)

    @property
    def runtime_pth(self) -> Path:
        site = (self.runtime_dir / "Lib" / "site-packages" if os.name == "nt"
                else Path(sysconfig.get_path("purelib", vars={"base": str(self.runtime_dir)})))
        return site / "model-tiers-source.pth"

    @property
    def codex_dir(self) -> Path:
        """Pinned copies of the registered Codex bin folder, named by the original folder."""
        return self.local / "codex"


DEFAULT_PATHS = Paths(
    root=ROOT,
    arm_dir=HERE / "model-tiers-20260922",
    local=ROOT / "runs" / "model-tiers-20260922",
    trial=ROOT / "runs" / "full-book-trial-20260919",
    trial_here=HERE / "full-book-trial-20260919",
    lock_holder=ROOT / "runs" / "box.lock" / "holder",
    runner_file=Path(__file__).resolve(),
    test_file=ROOT / "tests" / "test_model_tiers_comparison.py",
)


# ========================================================================= utilities


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    return sha_text(canonical(value))


def serial(value: Any) -> Any:
    return json.loads(json.dumps(dataclasses.asdict(value), ensure_ascii=False))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def write_new(path: Path, value: Any) -> None:
    """Exclusive create: a receipt or a reading is never overwritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def key_for(path: Path, root: Path) -> str:
    """A registration key: relative to the root when under it, else absolute. `root / key` reads
    either back, because joining an absolute path yields it."""
    resolved = path.resolve()
    return (resolved.relative_to(root.resolve()).as_posix()
            if resolved.is_relative_to(root.resolve()) else resolved.as_posix())


def tree_hashes(folder: Path) -> dict[str, str]:
    """Every file under a folder by relative path, bytecode caches aside (an import writes them).

    Equality of two of these is equality of the whole tree: a file added, removed or changed
    anywhere in it breaks it."""
    if not folder.is_dir():
        return {}
    return {
        path.relative_to(folder).as_posix(): sha_file(path)
        for path in sorted(folder.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def tree_difference(expected: Mapping[str, str], current: Mapping[str, str]) -> list[str]:
    """The first few paths that differ between two trees, for a refusal message."""
    names = sorted(set(expected) | set(current))
    return [name for name in names if expected.get(name) != current.get(name)][:5]


def now() -> str:
    return datetime.now(UTC).isoformat()


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def schema_canonical(value: Any) -> Any:
    """A JSON Schema with every `required` list sorted: equal up to member order."""
    if isinstance(value, dict):
        return {
            key: sorted(item) if key == "required" and isinstance(item, list)
            else schema_canonical(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [schema_canonical(item) for item in value]
    return value


def text_norm(value: object) -> str:
    """NFKC, casefolded, every run of non-alphanumerics one space. For agreement, never quality."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def copy_store(source: Path, target: Path) -> None:
    """A byte copy of a closed store, its write-ahead log too when it holds anything."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    wal = source.with_name(source.name + "-wal")
    if wal.is_file() and wal.stat().st_size:
        shutil.copy2(wal, target.with_name(target.name + "-wal"))


def offline_environment(binary: str | None = None) -> dict[str, str]:
    """No LitHarness, Anthropic or OpenAI settings from the caller; billing disabled."""
    env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith(_CLEAN_ENV_DROP)
        and key.upper() not in {"PYTHONPATH", "PYTHONHOME", "PYTEST_CURRENT_TEST"}
    }
    env.update(LITHARNESS_ENV="test", LITHARNESS_PROVIDER="codex", PYTHONIOENCODING="utf-8",
               PYTHONUTF8="1")
    if binary:
        env["LITHARNESS_CODEX_BINARY"] = binary
    return env


@contextlib.contextmanager
def scoped_environ(*, drop: Sequence[str] = (), put: Mapping[str, str] | None = None
                   ) -> Iterator[None]:
    """Change this process's environment for one block and put it back afterwards."""
    saved = {key: os.environ.get(key) for key in {*drop, *(put or {})}}
    try:
        for key in drop:
            os.environ.pop(key, None)
        for key, value in (put or {}).items():
            os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# ======================================================================== the design


def design() -> dict[str, Any]:
    """Every constant the reading depends on. Its digest is registered."""
    return {
        "version": VERSION,
        "summary_cells": [dataclasses.asdict(cell) for cell in SUMMARY_CELLS],
        "current_cells": [dataclasses.asdict(cell) for cell in CURRENT_CELLS],
        "summary_candidates": [cell.name for cell in SUMMARY_CANDIDATES],
        "seed_cells": [dataclasses.asdict(cell) for cell in SEED_CELLS],
        "seed_replicates": SEED_REPLICATES,
        "seed_order": [list(item) for item in SEED_ORDER],
        "summary_rotation": "scene i (0-based) runs the recorded block's cells rotated left by "
        "i mod 3, then the current block's rotated left by i mod 4",
        "seed_licence": "none: a screen for gross failure",
        "adapter_effort": ADAPTER_EFFORT,
        "summary_profile": SUMMARY_PROFILE,
        "expected_scenes": EXPECTED_SCENES,
        "recorded_model": RECORDED_MODEL,
        "recorded_effort": RECORDED_EFFORT,
        "trial_seed_call": TRIAL_SEED_CALL,
        "trial_seed_profile": TRIAL_SEED_PROFILE,
        "trial_global_args": list(TRIAL_GLOBAL_ARGS),
        "limits": LIMITS,
        "reserve": RESERVE,
        "max_attempts": MAX_ATTEMPTS,
        "transport_circuit": TRANSPORT_CIRCUIT,
        "alpha": ALPHA,
        "candidates": CANDIDATES,
        "validator_margin": VALIDATOR_MARGIN,
        "settlement_margin": SETTLEMENT_MARGIN,
        "agreement_margin": AGREEMENT_MARGIN,
        "seed_agreement_margin": SEED_AGREEMENT_MARGIN,
        "t_critical_23": T_CRITICAL_23,
        "reported_components": list(REPORTED_COMPONENTS),
        "composite_components": list(COMPOSITE_COMPONENTS),
        "seed_components": list(SEED_COMPONENTS),
        "structured_fields": list(STRUCTURED_FIELDS),
        "prose_fields": list(PROSE_FIELDS),
        "ledger_row_fields": list(LEDGER_ROW_FIELDS),
        "model_turn_kinds": sorted(MODEL_TURN_KINDS),
        "model_act_marks": list(MODEL_ACT_MARKS),
        "model_bridge_kinds": sorted(MODEL_BRIDGE_KINDS),
        "isolation_flags": list(ISOLATION_FLAGS),
    }


def registration_digest() -> str:
    return digest(design())


@dataclass(frozen=True, slots=True)
class Unit:
    """One planned answer: a scene summary on one cell in one block, or one seed replicate.

    `block` is "recorded" (the trial's bytes), "current" (HEAD's §255 bytes) or "seed"; the
    role is "summary" for both summary blocks, which is what the reservation and the served-mode
    check read."""

    unit_id: str
    role: str
    cell: Cell
    item: str
    position: int
    block: str

    def slug(self, attempt: int) -> str:
        return f"{self.unit_id.replace('/', '_')}_a{attempt}"


BLOCK_PREFIX: dict[str, str] = {"recorded": "summary", "current": "current"}


def plan(scenes: Sequence[str]) -> list[Unit]:
    """Per scene, the recorded block's cells then the current block's, each rotated per scene;
    then the seeds in ABBA order."""
    units: list[Unit] = []
    for index, scene in enumerate(scenes):
        for block, cells in (("recorded", SUMMARY_CELLS), ("current", CURRENT_CELLS)):
            shift = index % len(cells)
            for cell in (*cells[shift:], *cells[:shift]):
                units.append(Unit(f"{BLOCK_PREFIX[block]}/{scene}/{cell.name}", "summary", cell,
                                  scene, len(units), block))
    by_name = {cell.name: cell for cell in SEED_CELLS}
    for name, replicate in SEED_ORDER:
        cell = by_name[name]
        units.append(Unit(f"seed/{name}/r{replicate}", "seed", cell, f"r{replicate}", len(units),
                          "seed"))
    return units


# ================================================================= request rebuilding


def rebuild_request(payload: Mapping[str, Any]) -> Any:
    """The `CompletionRequest` a recorded `dataclasses.asdict` payload describes."""
    from litharness.domain.generation import CompletionRequest, Sampler

    fields = dict(payload)
    sampler = fields.get("sampler")
    fields["sampler"] = Sampler(**sampler) if isinstance(sampler, dict) else None
    fields["allowed_tools"] = tuple(fields.get("allowed_tools") or ())
    return CompletionRequest(**fields)


def round_trips(payload: Mapping[str, Any]) -> bool:
    return canonical(serial(rebuild_request(payload))) == canonical(dict(payload))


def ledger_subjects(suffix: str) -> list[str] | None:
    """The subjects the recorded ledger block showed, or None when the suffix is not that block."""
    if not suffix:
        return []
    if not suffix.startswith(LEDGER_HEADING_RECORDED) or THREAD_HEADING in suffix:
        return None
    lines = [line for line in suffix.splitlines() if line.startswith("- ")]
    subjects = LEDGER_LINE.findall(suffix)
    return subjects if len(subjects) == len(lines) else None


def current_ledger_subjects(suffix: str) -> list[str] | None:
    """The subjects HEAD's (§255) ledger block lists, or None when the suffix is not that block."""
    if not suffix:
        return []
    if not suffix.startswith(LEDGER_HEADING_CURRENT) or THREAD_HEADING in suffix:
        return None
    lines = [line for line in suffix.splitlines() if line.startswith("- ")]
    subjects = LEDGER_LINE_CURRENT.findall(suffix)
    return subjects if len(subjects) == len(lines) else None


def ledger_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """A trial `promises` row as it stood open when a summary call listed it."""
    return {**{name: row.get(name) for name in LEDGER_ROW_FIELDS}, "status": "open"}


def accept_counts(stdout: str) -> dict[str, int]:
    """(accepted, proposals, minted, left) from the `world accept` step's own report."""
    accepted = ACCEPTED_LINE.search(stdout)
    if accepted is None:
        raise RuntimeError("the accept step's stdout does not say what it accepted")
    minted = MINTED_LINE.search(stdout)
    left = LEFT_LINE.search(stdout)
    counts = {
        "accepted": int(accepted.group(1)),
        "proposals": int(accepted.group(2)),
        "minted": int(minted.group(1)) if minted else 0,
        "left": int(left.group(1)) if left else 0,
    }
    if counts["accepted"] + counts["left"] != counts["proposals"]:
        raise RuntimeError(f"the accept step's report does not add up: {counts}")
    return counts


def paid_entries(parsed: Mapping[str, Any]) -> list[dict[str, Any]]:
    """`promises_paid` read exactly as the summary handler reads it."""
    entries: list[dict[str, Any]] = []
    raw = parsed.get("promises_paid")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                entries.append({"subject": item, "evidence_quote": ""})
            elif isinstance(item, dict) and isinstance(item.get("subject"), str):
                entries.append(item)
    return entries


def opened_items(parsed: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = parsed.get("promises_opened")
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def recordable_opened(parsed: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The opened items the handler would record: a subject and a description."""
    from litharness.domain.extraction import normalise_subject

    return [
        item for item in opened_items(parsed)
        if normalise_subject(str(item.get("subject", "") or ""))
        and str(item.get("description", "") or "").strip()
    ]


def paid_split(parsed: Mapping[str, Any], shown: Sequence[str]) -> tuple[list[str], list[str]]:
    """(paid_matched, paid_unmatched) as `make_summary_handler` computes them."""
    from litharness.domain.extraction import normalise_subject

    names = [str(entry["subject"]) for entry in paid_entries(parsed)]
    listed = set(shown)
    return (
        [name for name in names if normalise_subject(name) in listed],
        [name for name in names if normalise_subject(name) not in listed],
    )


# ========================================================================= the trial


@dataclass(frozen=True)
class TrialView:
    """What the trial's final store and its pre-seed snapshot say, read from temporary copies."""

    scenes: dict[str, str]
    summaries: dict[str, dict[str, Any]]
    person_names: tuple[str, ...]
    seed_world: dict[str, Any]
    plan_items: list[list[Any]]
    pre_seed_plan_items: list[list[Any]]
    pre_seed_state_records: int
    #: The trial's `promises` rows by subject (stored normalised, one row per subject).
    promise_rows: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    #: The seed world's reconstruction against the accept step's own report.
    seed_counts: dict[str, int] = dataclasses.field(default_factory=dict)


def _plan_items(connection: sqlite3.Connection) -> list[list[Any]]:
    return [
        list(row) for row in connection.execute(
            "SELECT logical_id, kind, item_json FROM plan_items ORDER BY logical_id"
        )
    ]


def read_trial(paths: Paths) -> TrialView:
    """The trial's scenes, accepted summaries, promise rows, people and accepted seed world.

    Read from temporary copies. The seed world is the trial's own canon declared before its
    `world accept` of the seed finished: acceptance promotes in place and only upward, so a
    record canon now that existed then was accepted then (stage-0 §146.9's rail,
    `SqliteStore.promote_state_records`). **That holds only when nothing declared then was
    promoted or retracted later**, so the reconstruction must reproduce the accept step's own
    report: canon declared before it equals "accepted N" plus "M minted", and everything
    declared before it equals the proposals plus the minted records. A proposal left pending
    and promoted by a later accept, or a retracted row, breaks one of the two counts.
    """
    import litharness_contracts as lc

    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import worlds
    from litharness.domain.names import display_name
    from litharness.domain.nodes import NodeKind

    accept_step = read_json(paths.trial / "steps" / TRIAL_ACCEPT_STEP)
    accepted_at = parse_time(accept_step["finished_at"])
    counts = accept_counts(str(accept_step.get("stdout") or ""))
    canon_authority = {lc.StateAuthority.ACCEPTED_CANON, lc.StateAuthority.AUTHOR_LOCKED}
    with tempfile.TemporaryDirectory(prefix="model-tiers-trial-",
                                     ignore_cleanup_errors=True) as tmp:
        final, pre = Path(tmp) / "final" / "book.db", Path(tmp) / "pre" / "book.db"
        copy_store(paths.trial_store, final)
        copy_store(paths.pre_seed_store, pre)
        # A copy, so an open that migrates it touches nothing the registration hashes.
        with SqliteStore.open(final) as store:
            branches = store.branches()
            if len(branches) != 1:
                raise RuntimeError(f"the trial store holds {len(branches)} branches, not one")
            book_id, branch_id, _ = branches[0]
            head = store.head(book_id, branch_id)
            if head is None:
                raise RuntimeError("the trial store has no head revision")
            scenes = {
                node.logical_id: node.content or "" for node in head.nodes
                if node.kind is NodeKind.SCENE and (node.content or "").strip()
            }
            records = store.state_records(book_id, branch_id)
            times = store.state_record_times(book_id, branch_id)
        with contextlib.closing(sqlite3.connect(f"{final.as_uri()}?mode=ro", uri=True)) as con:
            summaries = {
                row[0]: {"content_hash": row[1], "summary": row[2],
                         "promises": json.loads(row[3]) if row[3] else None}
                for row in con.execute(
                    "SELECT logical_id, content_hash, summary, promises_json FROM scene_summaries"
                )
            }
            final_items = _plan_items(con)
            columns = ", ".join(LEDGER_ROW_FIELDS)
            promise_list = [
                dict(zip(LEDGER_ROW_FIELDS, row, strict=True))
                for row in con.execute(f"SELECT {columns} FROM promises ORDER BY promise_id")
            ]
        with contextlib.closing(sqlite3.connect(f"{pre.as_uri()}?mode=ro", uri=True)) as con:
            pre_items = _plan_items(con)
            pre_records = int(con.execute("SELECT COUNT(*) FROM state_records").fetchone()[0])
    promise_rows = {str(row["subject"]): row for row in promise_list}
    if len(promise_rows) != len(promise_list):
        raise RuntimeError("the trial's promises table holds two rows under one subject")
    canon = [record for record in records if record.authority in canon_authority]
    people = set(worlds.entities_with_role(canon, "protagonist"))
    people |= set(worlds.entities_with_role(canon, "cast"))
    names = tuple(sorted({display_name(canon, subject) for subject in people}))
    declared_then = [
        record for record in records
        if record.record_id in times and parse_time(times[record.record_id]) <= accepted_at
    ]
    seed_canon = [record for record in declared_then if record.authority in canon_authority]
    seed_counts = {**counts, "canon_declared_before_accept": len(seed_canon),
                   "declared_before_accept": len(declared_then)}
    if (len(seed_canon) != counts["accepted"] + counts["minted"]
            or len(declared_then) != counts["proposals"] + counts["minted"]):
        raise RuntimeError(
            "the seed world's reconstruction does not reproduce the accept step's report, so a "
            f"record was promoted or retracted after it: {seed_counts}"
        )
    return TrialView(
        scenes=scenes, summaries=summaries, person_names=names,
        seed_world=structure(seed_canon), plan_items=final_items,
        pre_seed_plan_items=pre_items, pre_seed_state_records=pre_records,
        promise_rows=promise_rows, seed_counts=seed_counts,
    )


def recorded_summary_calls(paths: Paths) -> list[tuple[Path, dict[str, Any]]]:
    rows = []
    for path in sorted((paths.trial / "calls").glob("*.json")):
        row = read_json(path)
        if row.get("profile") == SUMMARY_PROFILE:
            rows.append((path, row))
    return rows


def required_names(text: str, names: Sequence[str]) -> list[str]:
    return [name for name in names if name and _contains(text, name)]


def quantities(text: str) -> list[str]:
    """Every whole number the scene prints, once; a decimal's parts are not whole numbers."""
    found = re.findall(r"(?<![\w.])\d+(?!\w|\.\d)", text)
    return sorted(set(found), key=lambda q: (len(q), q))


def _contains(text: str, word: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None


def _argv_setting(argv: Sequence[str], option: str) -> str | None:
    items = list(argv)
    return items[items.index(option) + 1] if option in items[:-1] else None


def summary_unit_input(path: Path, row: Mapping[str, Any], trial: TrialView
                       ) -> tuple[dict[str, Any], dict[str, bool]]:
    """One recorded summary request, its accepted answer and every identity check on them."""
    from litharness.application.summarize import flatten
    from litharness.domain.extraction import normalise_subject
    from litharness.domain.text import content_hash
    from litharness.providers.codex_schema import prepare_codex_schema

    payload = row["request"]
    result = row.get("result") or {}
    raw = result.get("raw") or {}
    request = rebuild_request(payload)
    parsed = result.get("parsed")
    argv = raw.get("argv") or []
    native_now = prepare_codex_schema(request.schema)
    checks: dict[str, bool] = {
        "completed": row.get("status") == "completed",
        "round_trip": round_trips(payload),
        "sent_prompt": raw.get("prompt") == request.prompt,
        "sent_system": raw.get("system") == (request.effective_system or DEFAULT_SYSTEM),
        "sent_schema": canonical(raw.get("schema")) == canonical(request.schema),
        "native_schema_semantic": canonical(schema_canonical(raw.get("native_schema")))
        == canonical(schema_canonical(native_now)),
        "recorded_model": result.get("model") == RECORDED_MODEL
        and _argv_setting(argv, "--model") == RECORDED_MODEL
        and f"model_reasoning_effort={json.dumps(RECORDED_EFFORT)}" in argv,
        "parsed": isinstance(parsed, dict),
    }
    body = request.prompt[len(SCENE_PREFIX):] if request.prompt.startswith(SCENE_PREFIX) else None
    matches = [
        scene for scene, text in trial.scenes.items()
        if body is not None and body.startswith(text)
        and (len(body) == len(text) or body[len(text):].startswith("\n\n"))
    ]
    checks["scene_link"] = len(matches) == 1
    scene = matches[0] if len(matches) == 1 else ""
    text = trial.scenes.get(scene, "")
    suffix = body[len(text):] if body is not None and scene else ""
    shown = ledger_subjects(suffix)
    checks["suffix_format"] = shown is not None
    shown = shown or []
    checks["shown_normalised"] = all(normalise_subject(subject) == subject for subject in shown)
    accepted = trial.summaries.get(scene) or {}
    checks["accepted_hash"] = bool(scene) and accepted.get("content_hash") == content_hash(text)
    checks["accepted_summary"] = isinstance(parsed, dict) and accepted.get("summary") == flatten(
        parsed
    )
    matched, unmatched = paid_split(parsed, shown) if isinstance(parsed, dict) else ([], [])
    stored = accepted.get("promises") or {}
    checks["accepted_paid_split"] = (
        list(stored.get("paid_matched", [])) == matched
        and list(stored.get("paid_unmatched", [])) == unmatched
    )
    unit = {
        "scene": scene,
        "call": path.name,
        "call_sha256": sha_file(path),
        "request": payload,
        "request_sha256": digest(payload),
        "scene_text": text,
        "scene_sha256": sha_text(text),
        "suffix_empty": suffix == "",
        "shown": shown,
        "record": {
            "parsed": parsed,
            "text_sha256": sha_text(str(result.get("text", ""))),
            "usage": result.get("usage"),
            "wall_ms": result.get("wall_ms"),
            "cli_version": raw.get("cli_version"),
            "paid_matched": matched,
            "paid_unmatched": unmatched,
        },
        "required_names": required_names(text, trial.person_names),
        "quantities": quantities(text),
        "native_schema_bytes_equal": canonical(raw.get("native_schema")) == canonical(native_now),
    }
    return unit, checks


Renderer = Callable[[Path, str, Sequence[str], Path, str | None], dict[str, Any]]


def render_in(paths: Paths) -> Renderer:
    """Run one of this file's offline render modes under a given interpreter, billing disabled."""

    def render(python: Path, mode: str, arguments: Sequence[str], out: Path,
               binary: str | None) -> dict[str, Any]:
        completed = subprocess.run(
            [str(python), str(paths.runner_file), mode, *map(str, arguments), "--out", str(out)],
            cwd=paths.root, env=offline_environment(binary), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600, check=False,
        )
        if completed.returncode != 0 or not out.is_file():
            raise RuntimeError(
                f"{mode} under {python} failed ({completed.returncode}): "
                f"{completed.stderr.strip()[-600:]}"
            )
        return dict(read_json(out))

    return render


def build_summary_inputs(paths: Paths, trial: TrialView, renderer: Renderer
                         ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The 24 recorded requests checked, and the current-wording request of each rebuilt.

    Refuses unless every identity check passes. Each request's ledger is rebuilt from the
    trial's own `promises` rows under the subjects its recorded prompt listed, in that order,
    and rendered twice through the summariser's own request builder (`render-summaries`):
    under the trial's frozen runtime the whole request must equal the record byte for byte
    (canonical JSON), which proves the rows, the order and the scene text are what the trial
    sent; under the pinned registration source the same rows give the request production sends
    now (§255's wording), which the current block replays.
    """
    rows = recorded_summary_calls(paths)
    units, failures = [], {}
    for path, row in rows:
        unit, checks = summary_unit_input(path, row, trial)
        units.append(unit)
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            failures[path.name] = failed
    scenes = [unit["scene"] for unit in units]
    if len(units) != EXPECTED_SCENES or len(set(scenes)) != len(scenes):
        raise RuntimeError(f"{len(units)} recorded summaries over {len(set(scenes))} scenes, "
                           f"not {EXPECTED_SCENES} distinct")
    if failures:
        raise RuntimeError(f"recorded summary requests fail identity checks: {failures}")
    unlisted = {unit["scene"]: [s for s in unit["shown"] if s not in trial.promise_rows]
                for unit in units}
    unlisted = {scene: names for scene, names in unlisted.items() if names}
    if unlisted:
        raise RuntimeError(f"ledger subjects with no row in the trial's promises: {unlisted}")
    for unit in units:
        unit["ledger_rows"] = [ledger_row(trial.promise_rows[s]) for s in unit["shown"]]
    frozen, current = _render_summaries(paths, units, renderer)
    frozen_source = Path(frozen["source"]).resolve().is_relative_to(paths.frozen_source.resolve())
    current_source = Path(current["source"]).resolve().is_relative_to(
        (paths.source_dir / "src").resolve()
    )
    not_rebuilt = [
        unit["scene"] for unit in units
        if canonical(frozen["requests"].get(unit["scene"])) != canonical(unit["request"])
    ]
    if not frozen_source or not current_source or not_rebuilt:
        raise RuntimeError(
            "the summariser does not rebuild the recorded requests from the trial's rows: "
            f"frozen source {frozen_source}, pinned source {current_source}, "
            f"not byte-identical {not_rebuilt}"
        )
    current_failures = {}
    for unit in units:
        request = current["requests"].get(unit["scene"])
        checks = current_request_checks(unit, request)
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            current_failures[unit["scene"]] = failed
        unit["current_request"] = request
        unit["current_request_sha256"] = digest(request)
    if current_failures:
        raise RuntimeError(f"current-wording requests fail identity checks: {current_failures}")
    identity = {
        "requests": len(units),
        "checks_passed_on_every_request": [
            "completed", "round_trip", "sent_prompt", "sent_system", "sent_schema",
            "native_schema_semantic", "recorded_model", "parsed", "scene_link", "suffix_format",
            "shown_normalised", "accepted_hash", "accepted_summary", "accepted_paid_split",
        ],
        "native_schema_bytes_equal": sum(unit["native_schema_bytes_equal"] for unit in units),
        "native_schema_note": "equal up to the order of `required` members when not byte-equal",
        "frozen_rebuild": {"source": "frozen runtime", "whole_request_byte_identical": len(units),
                           "ledger_rows": sum(len(unit["ledger_rows"]) for unit in units)},
        "current": {
            "checks_passed_on_every_request": [
                "scene", "ledger", "other_fields", "model_unset", "round_trip",
            ],
            "system_differs": sum(unit["current_request"]["system"] != unit["request"]["system"]
                                  for unit in units),
            "prompt_differs": sum(unit["current_request"]["prompt"] != unit["request"]["prompt"]
                                  for unit in units),
        },
        "passed": True,
    }
    return units, identity


def _render_summaries(paths: Paths, units: Sequence[Mapping[str, Any]], renderer: Renderer
                      ) -> tuple[dict[str, Any], dict[str, Any]]:
    """Each unit's request built by the summariser under the frozen and the pinned runtime."""
    render_units = [
        {"scene": unit["scene"], "text": unit["scene_text"], "promises": unit["ledger_rows"],
         "call_class": unit["request"]["call_class"]}
        for unit in units
    ]
    with tempfile.TemporaryDirectory(prefix="model-tiers-summary-", ignore_cleanup_errors=True
                                     ) as tmp:
        units_file = Path(tmp) / "units.json"
        write_json(units_file, {"units": render_units})
        frozen = renderer(paths.frozen_python, "render-summaries",
                          ["--units-file", str(units_file)], Path(tmp) / "frozen.json", None)
        current = renderer(paths.runtime_python, "render-summaries",
                           ["--units-file", str(units_file)], Path(tmp) / "current.json", None)
    return frozen, current


def current_request_checks(unit: Mapping[str, Any], request: Any) -> dict[str, bool]:
    """The current-wording request differs from the recorded one in its wording only."""
    if not isinstance(request, dict):
        return {"present": False}
    recorded = unit["request"]
    head = SCENE_PREFIX + unit["scene_text"]
    prompt = str(request.get("prompt", ""))
    suffix = prompt[len(head):] if prompt.startswith(head) else None
    return {
        "scene": suffix is not None,
        "ledger": suffix is not None and current_ledger_subjects(suffix) == list(unit["shown"]),
        "other_fields": {k: v for k, v in request.items() if k not in {"system", "prompt"}}
        == {k: v for k, v in recorded.items() if k not in {"system", "prompt"}},
        "model_unset": request.get("model") is None,
        "round_trip": round_trips(request),
    }


def _changed_lines(before: str, after: str) -> int:
    return sum(
        1 for line in difflib.ndiff(before.splitlines(), after.splitlines())
        if line.startswith(("+ ", "- "))
    )


def build_seed_inputs(paths: Paths, trial: TrialView, binary: str, renderer: Renderer
                      ) -> tuple[dict[str, Any], dict[str, Any]]:
    """The seed request the pinned source builds from the trial's pre-seed store, and the
    template store.

    The frozen runtime must rebuild the recorded `architect.seed.v8` request byte for byte from
    the same snapshot, which proves the snapshot, its concept and listing and these arguments
    are the trial's; the pinned runtime's rebuild is then the request the screen sends. The
    template is migrated once, by the pinned runtime (`open-store`), and every attempt copies it.
    """
    recorded_row = read_json(paths.trial / "calls" / TRIAL_SEED_CALL)
    recorded = recorded_row["request"]
    checks = {
        "recorded_profile": recorded_row.get("profile") == TRIAL_SEED_PROFILE
        and recorded_row.get("status") == "completed",
        "pre_seed_world_empty": trial.pre_seed_state_records == 0,
    }
    # Informational: later operations may rewrite plan items, and the frozen rebuild below is
    # the proof that this snapshot is the trial's seed input.
    plan_items_equal = trial.pre_seed_plan_items == trial.plan_items
    with tempfile.TemporaryDirectory(prefix="model-tiers-seed-", ignore_cleanup_errors=True) as t:
        tmp = Path(t)
        copy_store(paths.pre_seed_store, tmp / "frozen" / "book.db")
        frozen = renderer(paths.frozen_python, "render-seed",
                          ["--database", str(tmp / "frozen" / "book.db"),
                           "--library", str(tmp / "frozen" / "library")],
                          tmp / "frozen.json", binary)
        paths.inputs_dir.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            with contextlib.suppress(FileNotFoundError):
                Path(str(paths.seed_template) + suffix).unlink()
        copy_store(paths.pre_seed_store, paths.seed_template)
        # The pinned source applies any migration the snapshot lacks, once, here.
        opened = renderer(paths.runtime_python, "open-store",
                          ["--database", str(paths.seed_template)], tmp / "open.json", None)
        wal = Path(str(paths.seed_template) + "-wal")
        if wal.is_file() and wal.stat().st_size:
            raise RuntimeError("the migrated template kept a non-empty write-ahead log")
        for suffix in ("-wal", "-shm"):
            with contextlib.suppress(FileNotFoundError):
                Path(str(paths.seed_template) + suffix).unlink()
        copy_store(paths.seed_template, tmp / "head" / "book.db")
        head = renderer(paths.runtime_python, "render-seed",
                        ["--database", str(tmp / "head" / "book.db"),
                         "--library", str(tmp / "head" / "library")],
                        tmp / "head.json", binary)
    pinned_source = (paths.source_dir / "src").resolve()
    checks["frozen_source"] = Path(frozen["source"]).resolve().is_relative_to(
        paths.frozen_source.resolve()
    )
    checks["frozen_identical"] = canonical(frozen["request"]) == canonical(recorded)
    checks["template_migrated_by_pinned_source"] = Path(opened["source"]).resolve(
    ).is_relative_to(pinned_source)
    checks["head_source"] = Path(head["source"]).resolve().is_relative_to(pinned_source)
    request = head["request"]
    checks["head_profile"] = str(request.get("profile", "")).startswith("architect.seed.")
    checks["head_tools"] = bool(request.get("allowed_tools")) and all(
        str(item).startswith("Bash(litharness world ") for item in request["allowed_tools"]
    )
    checks["head_model_unset"] = request.get("model") is None
    checks["head_round_trip"] = round_trips(request)
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"the seed request fails identity checks: {failed}")
    seed = {
        "request": request,
        "request_sha256": digest(request),
        "recorded_request_sha256": digest(recorded),
        "profile": request["profile"],
        "recorded_profile": recorded["profile"],
        "record": trial.seed_world,
        "template_sha256": sha_file(paths.seed_template),
    }
    identity = {
        "checks": checks,
        "seed_world_counts": trial.seed_counts,
        "plan_items_equal_final_store": plan_items_equal,
        "profile": request["profile"],
        "recorded_profile": recorded["profile"],
        "system_lines_changed": _changed_lines(recorded.get("system") or "",
                                               request.get("system") or ""),
        "prompt_lines_changed": _changed_lines(recorded.get("prompt") or "",
                                               request.get("prompt") or ""),
        "passed": True,
    }
    return seed, identity


# ====================================================================== registration


def sources(paths: Paths) -> list[Path]:
    """This arm's own tracked files. They must be committed as registered before `run`.

    Production code is not here: it runs from the pinned archive (`build_runtime`), whose
    whole tree is registered and hashed before every call, so a later commit to `src/`,
    `migrations/` or `uv.lock` changes nothing the arm runs and never blocks a resume or the
    reading."""
    return [
        paths.runner_file,
        paths.prereg,
        paths.runbook,
        paths.test_file,
        paths.trial_here / "registration.json",
    ]


#: What the pinned runtime reports about itself, run with no LitHarness settings.
RUNTIME_PROBE = (
    "import json, sys, litharness, litharness_contracts, jsonschema; "
    "print(json.dumps({'litharness': litharness.__file__, "
    "'litharness_contracts': litharness_contracts.__file__, "
    "'jsonschema': jsonschema.__file__, 'executable': sys.executable}))"
)


def build_runtime(paths: Paths, git: Git) -> dict[str, Any]:
    """Archive HEAD's production files and build the interpreter the arm runs under.

    The full-book trial's pattern (`experience-workflow-20260915/run.py`, `prepare`):
    `git archive` of `src/`, `migrations/`, `pyproject.toml` and `uv.lock`, extracted under
    the ignored local folder, and a venv whose `.pth` puts the archived `src/` first and the
    shared environment's site-packages (third-party packages only: a plain path entry does not
    process the editable install's `.pth`) after it. Refused unless the probe imports
    `litharness` from the archive. Rebuilt from nothing on every `prepare`, which is refused
    once anything was bought.
    """
    for folder in (paths.source_dir, paths.runtime_dir):
        shutil.rmtree(folder, ignore_errors=True)
        if folder.exists():
            raise RuntimeError(f"could not clear {folder} for a fresh build")
    paths.local.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(FileNotFoundError):
        paths.source_archive.unlink()
    git(["archive", "--format=zip", f"--output={paths.source_archive}", "HEAD", "src",
         "migrations", "pyproject.toml", "uv.lock"], paths.root)
    with zipfile.ZipFile(paths.source_archive) as packed:
        packed.extractall(paths.source_dir)
    venv.EnvBuilder(with_pip=False).create(paths.runtime_dir)
    purelib = sysconfig.get_path("purelib")
    paths.runtime_pth.parent.mkdir(parents=True, exist_ok=True)
    paths.runtime_pth.write_text(f"{paths.source_dir / 'src'}\n{purelib}\n", encoding="utf-8")
    completed = subprocess.run(
        [str(paths.runtime_python), "-c", RUNTIME_PROBE], cwd=paths.root,
        env=offline_environment(), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"the pinned runtime does not start: {completed.stderr[-600:]}")
    probe = json.loads(completed.stdout)
    if not Path(probe["litharness"]).resolve().is_relative_to((paths.source_dir / "src").resolve()):
        raise RuntimeError(f"the pinned runtime imported {probe['litharness']}, not the archive")
    return {"archive_sha256": sha_file(paths.source_archive), "purelib": purelib, "probe": probe}


def runtime_record(paths: Paths, runtime: Mapping[str, Any]) -> dict[str, Any]:
    """The pinned runtime's files and trees as registered: the archive's whole tree, the
    contracts package it imports from the shared environment, and the venv's own files."""
    contracts = Path(runtime["probe"]["litharness_contracts"]).resolve().parent
    return {
        "trees": {key_for(folder, paths.root): tree_hashes(folder)
                  for folder in (paths.source_dir, contracts)},
        "files": {key_for(path, paths.root): sha_file(path)
                  for path in (paths.runtime_python, paths.runtime_dir / "pyvenv.cfg",
                               paths.runtime_pth, paths.source_archive)},
    }


def pin_codex(paths: Paths, codex_binary: Path,
              binary_reader: Callable[[Path], dict[str, str]]) -> dict[str, Any]:
    """Copy the registered Codex bin folder whole into the ignored local folder, hash-checked.

    `codex.exe` sits beside the helper executables it starts, so the folder is the unit. The
    copy is named by the original folder; an earlier prepare's copy of the same bytes is kept,
    of other bytes replaced (nothing has been bought, or prepare would have refused). The arm
    runs the copy, so an update of the operator's app changes nothing it runs."""
    original = binary_reader(codex_binary)
    source = Path(original["path"]).parent
    wanted = tree_hashes(source)
    if not wanted:
        raise RuntimeError(f"{source} holds no files")
    target = paths.codex_dir / source.name
    if target.exists() and tree_hashes(target) != wanted:
        shutil.rmtree(target)
    if not target.exists():
        partial = target.with_name(target.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        shutil.copytree(source, partial)
        partial.replace(target)
    folder_hashes = tree_hashes(target)
    if folder_hashes != wanted:
        raise RuntimeError(f"the pinned copy {target} does not hash to {source}")
    pinned = binary_reader(target / Path(original["path"]).name)
    if pinned["sha256"] != original["sha256"] or pinned["version"] != original["version"]:
        raise RuntimeError(f"the pinned {pinned['path']} is not {original['path']}")
    return {**pinned, "original": original["path"], "folder": key_for(target, paths.root),
            "folder_hashes": folder_hashes}


def trial_inputs(paths: Paths, summaries: Sequence[Mapping[str, Any]]) -> list[Path]:
    """The trial's files the registration reads; they live under ignored runs/ and are hashed."""
    files = [paths.trial / "calls" / str(unit["call"]) for unit in summaries]
    files += [
        paths.trial / "calls" / TRIAL_SEED_CALL,
        paths.trial_store,
        paths.pre_seed_store,
        paths.trial / "steps" / TRIAL_SEED_STEP,
        paths.trial / "steps" / TRIAL_ACCEPT_STEP,
        paths.frozen_python,
        paths.trial / "runtimes" / "A" / "pyvenv.cfg",
        paths.trial / "runtimes" / "A" / "Lib" / "site-packages" / "experiment-source.pth",
    ]
    wal = paths.trial_store.with_name(paths.trial_store.name + "-wal")
    if wal.is_file() and wal.stat().st_size:
        files.append(wal)
    return files


def _git(args: Sequence[str], root: Path) -> bytes:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout


Git = Callable[[Sequence[str], Path], bytes]


def production_state(paths: Paths, git: Git) -> dict[str, str]:
    """The commit and the production trees; refuses a production tree that differs from HEAD."""
    dirty = git(["status", "--porcelain", "--", "src", "migrations"], paths.root).strip()
    if dirty:
        raise RuntimeError(
            "src/ or migrations/ differ from HEAD; the comparison runs committed production "
            f"code only:\n{dirty.decode(errors='replace')}"
        )
    return {
        "commit": git(["rev-parse", "HEAD"], paths.root).decode().strip(),
        "src_tree": git(["rev-parse", "HEAD:src"], paths.root).decode().strip(),
        "migrations_tree": git(["rev-parse", "HEAD:migrations"], paths.root).decode().strip(),
    }


def binary_info(path: Path) -> dict[str, str]:
    """The native Codex executable: path, sha256 and `--version` (which makes no model call)."""
    resolved = path.resolve()
    if resolved.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("the Codex binary must be the native executable, not a shell shim")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    version = subprocess.run([str(resolved), "--version"], capture_output=True, text=True,
                             timeout=60, check=True).stdout.strip()
    return {"path": str(resolved), "sha256": sha_file(resolved), "version": version}


def write_claim(paths: Paths, status: str) -> None:
    files = [("registration", paths.prereg), ("registration", paths.runbook)]
    if paths.registration.is_file():
        files.append(("registration", paths.registration))
    if status == "observed":
        files += [
            ("raw_result", paths.ledger),
            ("derived_result", paths.results),
            ("control_result", paths.results),
        ]
    write_json(paths.claim, {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": VERSION,
        "statement": CLAIM_STATEMENT,
        "status": status,
        "artifacts": [
            {"kind": kind, "path": rel(path, paths.root), "sha256": sha_file(path)}
            for kind, path in files
        ],
    })


CLAIM_STATEMENT = (
    "On the Codex provider only, against fresh gpt-6-astra controls on one pinned binary and "
    "one pinned source, gpt-6-luna (medium or high effort) summarises the full-book trial's 24 "
    "scenes, under the recorded wording and under the current (stage-0 section 255) wording, "
    "with validator outcomes, settled-promise sets and structured agreement no worse than the "
    "control beyond the registered margins; one book, computed in code, licensing only a "
    "Codex-only proposal to the operator. Two gpt-6-sol seeds of that trial's world are a "
    "screen for gross failure and license nothing."
)


RuntimeBuilder = Callable[[Paths, Git], dict[str, Any]]
Pinner = Callable[[Paths, Path, Callable[[Path], dict[str, str]]], dict[str, Any]]


def prepare(
    *,
    paths: Paths = DEFAULT_PATHS,
    codex_binary: Path,
    git: Git = _git,
    binary_reader: Callable[[Path], dict[str, str]] = binary_info,
    trial_reader: Callable[[Paths], TrialView] = read_trial,
    renderer: Renderer | None = None,
    runtime_builder: RuntimeBuilder = build_runtime,
    pinner: Pinner = pin_codex,
) -> dict[str, Any]:
    """Pin the source and the binary, freeze the inputs (local), the registration and the
    claim. No provider call.

    Refused once any call has been dispatched or a reading exists: a registration is never
    refreshed after spend. Refused when src/ or migrations/ differ from HEAD, because the
    archive is HEAD's and this process's own reads of the trial import the live checkout.
    """
    if any(line.get("event") == "dispatch" for line in read_ledger(paths.ledger)):
        raise RuntimeError("calls have been dispatched: a registration is never refreshed after")
    if paths.results.exists():
        raise RuntimeError("a reading exists; nothing is registered after it")
    production = production_state(paths, git)
    runtime = runtime_builder(paths, git)
    binary = pinner(paths, codex_binary, binary_reader)
    trial = trial_reader(paths)
    render = renderer or render_in(paths)
    summaries, summary_identity = build_summary_inputs(paths, trial, render)
    seed, seed_identity = build_seed_inputs(paths, trial, binary["path"], render)
    write_json(paths.summary_inputs, {"version": VERSION, "units": summaries})
    write_json(paths.seed_inputs, {"version": VERSION, **seed})
    local_inputs = [paths.summary_inputs, paths.seed_inputs, paths.seed_template]
    registration = {
        "version": VERSION,
        "prepared_at": now(),
        "design": design(),
        "registration_digest": registration_digest(),
        "production": {**production, "python": sys.version.split()[0],
                       "jsonschema": _jsonschema_version()},
        "runtime": {**runtime, **runtime_record(paths, runtime),
                    "python": key_for(paths.runtime_python, paths.root)},
        "binary": binary,
        "inputs": {
            "scenes": [unit["scene"] for unit in summaries],
            "summary_requests": [
                {key: unit[key] for key in ("scene", "call", "call_sha256", "request_sha256",
                                            "current_request_sha256", "scene_sha256")}
                for unit in summaries
            ],
            "seed_request_sha256": seed["request_sha256"],
            "seed_recorded_request_sha256": seed["recorded_request_sha256"],
            "seed_profile": seed["profile"],
            "seed_template_sha256": seed["template_sha256"],
        },
        "request_identity": {"summaries": summary_identity, "seed": seed_identity},
        "input_hashes": {
            rel(path, paths.root): sha_file(path)
            for path in [*trial_inputs(paths, summaries), *local_inputs]
        },
        "source_hashes": {rel(path, paths.root): sha_file(path) for path in sources(paths)},
        "planned_units": len(plan([unit["scene"] for unit in summaries])),
    }
    write_json(paths.registration, registration)
    write_claim(paths, "registered")
    return registration


def refresh_claim(*, paths: Paths = DEFAULT_PATHS) -> dict[str, Any]:
    """Rewrite claim.json after an edit to the PREREG or RUNBOOK, before `prepare`. No call.

    Refused once a registration exists (`prepare` rewrites the claim, and a claim citing an
    edited PREREG beside a registration that hashed the old one would disagree with it), once
    anything was dispatched, and once a reading exists.
    """
    if paths.results.exists():
        raise RuntimeError("a reading exists; the claim moves only through analyse")
    if any(line.get("event") == "dispatch" for line in read_ledger(paths.ledger)):
        raise RuntimeError("calls have been dispatched: the registration is fixed")
    if paths.registration.exists():
        raise RuntimeError("registration.json exists; prepare again, which rewrites the claim")
    write_claim(paths, "registered")
    return dict(read_json(paths.claim))


def _jsonschema_version() -> str:
    from importlib.metadata import version

    return version("jsonschema")


# ============================================================================ verify


def check_lock(paths: Paths) -> None:
    holder = paths.lock_holder
    if not holder.is_file():
        raise RuntimeError("runs/box.lock is not held; take it (RUNBOOK) before a run")
    if not holder.read_text(encoding="utf-8-sig").startswith(LOCK_PREFIX):
        raise RuntimeError(f"runs/box.lock is held by someone else, not {LOCK_PREFIX}")


def check_frozen(reg: Mapping[str, Any], paths: Paths) -> None:
    """Every registered file byte-identical, and the pinned runtime's trees whole.

    Run before every call: the archived source is what the adapter, the tool bridge and the
    world CLI import, so a file changed, added or removed anywhere in it halts the run."""
    for field in ("source_hashes", "input_hashes"):
        for name, expected in reg[field].items():
            path = paths.root / name
            if not path.is_file() or sha_file(path) != expected:
                raise RuntimeError(f"changed frozen file: {name}")
    runtime = reg["runtime"]
    for name, expected in runtime["files"].items():
        path = paths.root / name
        if not path.is_file() or sha_file(path) != expected:
            raise RuntimeError(f"changed pinned runtime file: {name}")
    for name, expected in runtime["trees"].items():
        changed = tree_difference(expected, tree_hashes(paths.root / name))
        if changed:
            raise RuntimeError(f"changed pinned runtime tree {name}: {changed}")


def check_interpreter(paths: Paths) -> None:
    """`run` and `analyse` execute under the pinned runtime, importing the archived source.

    The tool bridge starts `sys.executable -m litharness` and the reading's world CLI does the
    same, so the interpreter this process runs is what every child imports."""
    import litharness

    source = (paths.source_dir / "src").resolve()
    imported = Path(litharness.__file__).resolve()
    if not imported.is_relative_to(source) or (
        Path(sys.executable).resolve() != paths.runtime_python.resolve()
    ):
        raise RuntimeError(
            f"this process runs {sys.executable} importing {imported}; run and analyse execute "
            f"under the pinned runtime {paths.runtime_python} (RUNBOOK), never the live checkout"
        )


def check_codex(reg: Mapping[str, Any], paths: Paths,
                binary_reader: Callable[[Path], dict[str, str]]) -> None:
    """The pinned Codex folder whole, and its executable's hash and version."""
    pinned = reg["binary"]
    changed = tree_difference(pinned["folder_hashes"], tree_hashes(paths.root / pinned["folder"]))
    if changed:
        raise RuntimeError(f"the pinned Codex folder changed: {changed}")
    current = binary_reader(Path(pinned["path"]))
    for key in ("path", "sha256", "version"):
        if current[key] != pinned[key]:
            raise RuntimeError(f"the Codex binary changed: {key}")


def verify(
    paths: Paths = DEFAULT_PATHS,
    *,
    check_lock_held: bool = False,
    check_binary: bool = False,
    require_pushed: bool = True,
    git: Git = _git,
    binary_reader: Callable[[Path], dict[str, str]] = binary_info,
    interpreter: Callable[[Paths], None] | None = check_interpreter,
) -> dict[str, Any]:
    """Refuse unless the interpreter, every frozen byte, the committed (and, for a run, pushed)
    registration and the pinned binary match.

    Nothing here reads the live checkout's `src/`: the arm runs the pinned archive, so commits
    made after registration neither block a resume nor the reading."""
    if not paths.registration.is_file():
        raise RuntimeError("no registration.json; run prepare")
    reg: dict[str, Any] = read_json(paths.registration)
    if reg.get("registration_digest") != registration_digest():
        raise RuntimeError("the registered constants differ from this module's")
    if interpreter is not None:
        interpreter(paths)
    check_frozen(reg, paths)
    for name in [rel(paths.registration, paths.root), *reg["source_hashes"]]:
        try:
            committed = git(["show", f"HEAD:{name}"], paths.root)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"not committed: {name}") from error
        if committed != (paths.root / name).read_bytes():
            raise RuntimeError(f"not committed as registered: {name}")
    if require_pushed and not git(["branch", "-r", "--contains", "HEAD"], paths.root).strip():
        raise RuntimeError("the registration commit is on no remote branch; push it first")
    if check_binary:
        check_codex(reg, paths, binary_reader)
    if check_lock_held:
        check_lock(paths)
    return reg


@dataclass(frozen=True)
class Inputs:
    summaries: dict[str, dict[str, Any]]
    seed: dict[str, Any]
    requests: dict[str, Any]


def load_inputs(paths: Paths, reg: Mapping[str, Any]) -> Inputs:
    """The frozen inputs, each request rebuilt and checked against its registered digest."""
    units = read_json(paths.summary_inputs)["units"]
    seed = read_json(paths.seed_inputs)
    registered = {item["scene"]: item for item in reg["inputs"]["summary_requests"]}
    summaries = {}
    requests: dict[str, Any] = {}
    for unit in units:
        entry = registered.get(unit["scene"]) or {}
        if entry.get("request_sha256") != digest(unit["request"]) or entry.get(
            "current_request_sha256"
        ) != digest(unit["current_request"]):
            raise RuntimeError(f"the summary requests for {unit['scene']} are not the registered "
                               "ones")
        summaries[unit["scene"]] = unit
        requests[f"recorded:{unit['scene']}"] = rebuild_request(unit["request"])
        requests[f"current:{unit['scene']}"] = rebuild_request(unit["current_request"])
    if digest(seed["request"]) != reg["inputs"]["seed_request_sha256"]:
        raise RuntimeError("the seed request is not the registered one")
    requests["seed"] = rebuild_request(seed["request"])
    return Inputs(summaries=summaries, seed=seed, requests=requests)


def request_for(unit: Unit, inputs: Inputs) -> Any:
    return inputs.requests["seed"] if unit.block == "seed" else inputs.requests[
        f"{unit.block}:{unit.item}"
    ]


def request_digest_for(unit: Unit, inputs: Inputs) -> str:
    if unit.block == "seed":
        return str(inputs.seed["request_sha256"])
    key = "request_sha256" if unit.block == "recorded" else "current_request_sha256"
    return str(inputs.summaries[unit.item][key])


# ============================================================================ ledger


def read_ledger(path: Path) -> list[dict[str, Any]]:
    """Every ledger line. A truncated last line (a kill mid-append) is skipped, not fatal."""
    if not path.is_file():
        return []
    lines = []
    for text in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            lines.append(record)
    return lines


def append_ledger(path: Path, line: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torn = path.is_file() and path.stat().st_size and path.read_bytes()[-1:] != b"\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        if torn:
            handle.write("\n")
        handle.write(json.dumps(dict(line), sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


@dataclass
class LedgerState:
    answered: dict[str, dict[str, Any]]
    attempts: Counter[str]
    used: dict[str, float]
    interrupted: list[dict[str, Any]]
    unknown_usage: int
    invocations: int
    next_seq: int
    finished: bool
    #: Calls served otherwise (another model, effort, version, mode or isolation). Once one
    #: exists this registration buys nothing more (`run`).
    halted: list[dict[str, Any]] = dataclasses.field(default_factory=list)


def ledger_state(lines: Sequence[Mapping[str, Any]]) -> LedgerState:
    """What was dispatched and answered, and what it cost, charging reservations where unknown."""
    dispatched = {int(line["seq"]): line for line in lines if line.get("event") == "dispatch"}
    calls = {int(line["seq"]): line for line in lines if line.get("event") == "call"}
    answered: dict[str, dict[str, Any]] = {}
    attempts: Counter[str] = Counter()
    tokens = seconds = 0.0
    unknown = 0
    for seq, line in sorted(dispatched.items()):
        attempts[str(line["unit"])] += 1
        reserve = RESERVE[str(line["role"])]
        call = calls.get(seq)
        if call is None:
            tokens += reserve["tokens"]
            seconds += reserve["seconds"]
            unknown += 1
            continue
        if call.get("usage_known"):
            tokens += float(call.get("tokens") or 0)
        else:
            tokens += reserve["tokens"]
            unknown += 1
        seconds += float(call.get("wall_ms") or 0) / 1000.0
        if call.get("status") in ANSWER_STATUSES:
            if str(call["unit"]) in answered:
                raise RuntimeError(f"two answers for {call['unit']} in the ledger")
            answered[str(call["unit"])] = dict(call)
    interrupted = [dict(line) for seq, line in sorted(dispatched.items()) if seq not in calls]
    invocations = {int(line["invocation"]) for line in lines if "invocation" in line}
    return LedgerState(
        answered=answered,
        attempts=attempts,
        used={"calls": float(len(dispatched)), "tokens": tokens, "seconds": seconds},
        interrupted=interrupted,
        unknown_usage=unknown,
        invocations=max(invocations, default=0),
        next_seq=max(dispatched, default=0) + 1,
        finished=bool(lines) and "finished_at" in lines[-1],
        halted=[dict(line) for _seq, line in sorted(calls.items())
                if line.get("status") == "halted"],
    )


def admit(role: str, used: Mapping[str, float]) -> str | None:
    """May one more call of this role start? Its worst case must fit under every ceiling."""
    if used["calls"] + 1 > LIMITS["calls"]:
        return "ceiling:calls"
    if used["tokens"] + RESERVE[role]["tokens"] > LIMITS["tokens"]:
        return "ceiling:tokens"
    if used["seconds"] + RESERVE[role]["seconds"] > LIMITS["seconds"]:
        return "ceiling:seconds"
    return None


# ============================================================================== run


def codex_provider(cell: Cell, binary: str, trace: Path | None) -> Any:
    """The production Codex adapter, pinned to one model and one effort for that model."""
    from litharness.providers.codex_cli import CodexCliProvider

    return CodexCliProvider(
        model=cell.model,
        reasoning_effort=ADAPTER_EFFORT,
        model_efforts={cell.model: cell.effort},
        binary=binary,
        trace_directory=trace,
    )


def model_turn_seen(attempt: Any) -> bool:
    """Whether the attempt's own JSONL shows the model took a turn: a `turn.completed` event or
    an `agent_message` item. The adapter keeps stdout in its attempt before it classifies."""
    if not isinstance(attempt, Mapping):
        return False
    for text in str(attempt.get("stdout") or "").splitlines():
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn.completed":
            return True
        item = event.get("item")
        if str(event.get("type", "")).startswith("item.") and isinstance(item, dict) and (
            item.get("type") == "agent_message"
        ):
            return True
    return False


def classify_failure(error: BaseException, attempt: Any = None) -> tuple[str, str]:
    """(status, kind): the model's own act is an unusable answer; anything else is transport.

    A refusal or safety kind is the model's act only when the attempt shows a model turn. On a
    nonzero Codex exit those kinds are `classify_provider_failure` matching words ("safety",
    "prohibited", "refusal") in stderr, and a platform or connection error that says them is
    transport, never a kept, failing answer (§235)."""
    kind = str(getattr(error, "kind", "unknown"))
    text = str(error)
    if kind in MODEL_TURN_KINDS:
        if model_turn_seen(attempt):
            return "answered_unusable", f"model_{kind}"
        return "transport_failure", f"platform_{kind}"
    if kind == "malformed_response":
        if any(mark in text for mark in MODEL_ACT_MARKS):
            return "answered_unusable", "model_act"
        found = re.search(r"The scoped command failed \(([a-z_]+)\)", text)
        if found and found.group(1) in MODEL_BRIDGE_KINDS:
            return "answered_unusable", f"bridge_{found.group(1)}"
        if found:
            return "transport_failure", f"bridge_{found.group(1)}"
    return "transport_failure", kind


def attempt_usage(attempt: Any) -> dict[str, int] | None:
    """The `turn.completed` usage in an attempt's stdout, mapped as the adapter maps it."""
    if not isinstance(attempt, dict):
        return None
    for text in str(attempt.get("stdout") or "").splitlines():
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        usage = event.get("usage") or {}
        try:
            inputs, outputs = int(usage["input_tokens"]), int(usage["output_tokens"])
            cached = int(usage.get("cached_input_tokens", 0))
            reasoning = int(usage.get("reasoning_output_tokens", 0))
        except (KeyError, TypeError, ValueError):
            return None
        return {"input_tokens": inputs - cached, "cache_read_tokens": cached,
                "output_tokens": outputs - reasoning, "reasoning_tokens": reasoning,
                "cache_write_tokens": 0}
    return None


def served_as_registered(raw: Mapping[str, Any], unit: Unit, version: str,
                         interpreter: str | None = None) -> str | None:
    """None when the attempt ran the registered model, effort, binary and isolation, else why.

    With `interpreter`, a seed's tool bridge must have been started on it: the bridge's MCP
    server is `sys.executable -m litharness.providers.codex_tools`, so this is the proof the
    Architect's world commands ran the pinned source."""
    argv = list(raw.get("argv") or [])
    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    checks = (
        ("requested_model", raw.get("requested_model") == unit.cell.model),
        ("reasoning_effort", raw.get("reasoning_effort") == unit.cell.effort),
        ("cli_version", raw.get("cli_version") == version),
        ("argv_model", _argv_setting(argv, "--model") == unit.cell.model),
        ("argv_effort", f"model_reasoning_effort={json.dumps(unit.cell.effort)}" in argv),
        ("isolation", all(flag in argv for flag in ISOLATION_FLAGS)
         and "project_doc_max_bytes=0" in argv),
        ("mode", raw.get("mode") == ("bridge" if unit.role == "seed" else "completion")),
        ("bridge_interpreter", interpreter is None or unit.role != "seed"
         or _same_path(settings.get("mcp_servers.litharness.command"), interpreter)),
    )
    return next((name for name, passed in checks if not passed), None)


def _same_path(left: object, right: object) -> bool:
    if not isinstance(left, str) or not isinstance(right, str) or not left or not right:
        return False
    return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
        str(Path(right).resolve())
    )


def fresh_seed_store(paths: Paths, unit: Unit, attempt: int) -> Path:
    folder = paths.seeds_dir / f"{unit.cell.name}-{unit.item}" / f"attempt-{attempt}"
    if folder.exists():
        raise RuntimeError(f"{folder} exists: a seed attempt never reuses a store")
    store = folder / "book.db"
    copy_store(paths.seed_template, store)
    if sha_file(store) != sha_file(paths.seed_template):
        raise RuntimeError("the seed store copy does not hash to the template")
    return store


ProviderFactory = Callable[[Cell, str, Path | None], Any]


def dispatch(
    unit: Unit,
    attempt: int,
    seq: int,
    request: Any,
    request_sha256: str,
    *,
    paths: Paths,
    reg: Mapping[str, Any],
    provider_factory: ProviderFactory,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """One call through the adapter; its receipt is written once and its ledger fields returned."""
    from litharness.providers.base import ProviderError

    provider = provider_factory(unit.cell, reg["binary"]["path"],
                                paths.transport_dir / unit.slug(attempt))
    store = fresh_seed_store(paths, unit, attempt) if unit.role == "seed" else None
    started_at, started = now(), clock()
    result = None
    failure: dict[str, Any] | None = None
    status = "answered"
    kind: str | None = None
    usage: dict[str, int] | None = None
    put = {"LITHARNESS_DATABASE": str(store.resolve())} if store is not None else {}
    with scoped_environ(drop=_RUN_ENV_DROP, put=put):
        try:
            result = provider.complete(request)
        except ProviderError as error:
            status, kind = classify_failure(error, getattr(provider, "last_attempt", None))
            failure = {"kind": kind, "provider_kind": str(error.kind),
                       "message": " ".join(str(error).split())[:600]}
            usage = attempt_usage(getattr(provider, "last_attempt", None))
    wall_ms = int((clock() - started) * 1000)
    raw: dict[str, Any] = {}
    if result is not None:
        raw = dict(result.raw or {})
        usage = serial(result.usage)
        foreign = served_as_registered(raw, unit, reg["binary"]["version"], sys.executable)
        if foreign is not None:
            status, kind = "halted", f"served_otherwise:{foreign}"
    receipt_path = paths.calls_dir / f"{seq:04d}-{unit.slug(attempt)}.json"
    write_new(receipt_path, {
        "version": VERSION,
        "seq": seq,
        "unit": unit.unit_id,
        "role": unit.role,
        "cell": dataclasses.asdict(unit.cell),
        "attempt": attempt,
        "request_sha256": request_sha256,
        "started_at": started_at,
        "finished_at": now(),
        "status": status,
        "failure": failure,
        "result": serial(result) if result is not None else None,
        "attempt_raw": getattr(provider, "last_attempt", None) if result is None else None,
        "store": rel(store, paths.root) if store is not None else None,
    })
    tokens = sum(usage.values()) if usage else None
    return {
        "status": status,
        "failure_kind": kind,
        "tokens": tokens,
        "usage_known": bool(usage) and bool(tokens),
        "wall_ms": wall_ms,
        "receipt": rel(receipt_path, paths.root),
        "receipt_sha256": sha_file(receipt_path),
        "cli_version": raw.get("cli_version"),
        "requested_model": raw.get("requested_model"),
        "reasoning_effort": raw.get("reasoning_effort"),
    }


def stat_guard(folder: Path) -> Callable[[], str | None]:
    """Between calls: a stat, not a hash, of every file in the pinned Codex folder (`verify`
    hashes all of them at the start of each invocation). A change halts the run."""

    def signature() -> list[tuple[str, int, int]]:
        return sorted(
            (path.relative_to(folder).as_posix(), path.stat().st_size, path.stat().st_mtime_ns)
            for path in folder.rglob("*") if path.is_file()
        )

    first = signature()

    def guard() -> str | None:
        return None if signature() == first else "binary_changed"

    return guard


def run(
    *,
    paths: Paths = DEFAULT_PATHS,
    verifier: Callable[..., dict[str, Any]] = verify,
    provider_factory: ProviderFactory = codex_provider,
    guard: Callable[[], str | None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Buy the plan under the lock; resumable. Refused once a reading exists.

    Each unit is dispatched at most `MAX_ATTEMPTS` times, a second attempt only in the second
    pass and only after a transport failure or an interrupted dispatch (a kill, whose outcome
    never reached the ledger). An answer, usable or not, is never bought again. A call served
    otherwise halts the run, and once one has, `run` refuses: the registration's premise (this
    model, effort, binary, mode and isolation) failed, so nothing more is bought under it and
    the halted unit is never re-sent. The ledger gets a `dispatch` line before every call and a
    `call` line after it, so a kill loses no attempt: an interrupted dispatch counts as an
    attempt and is charged its role's reservation. The live log names outcomes and tokens,
    never an agreement or a verdict.
    """
    if paths.results.exists():
        raise RuntimeError("a reading exists; nothing is bought after it has been seen")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("run dispatches paid calls and refuses test mode")
    reg = verifier(paths, check_lock_held=True, check_binary=True)
    inputs = load_inputs(paths, reg)
    units = plan(reg["inputs"]["scenes"])
    lines = read_ledger(paths.ledger)
    state = ledger_state(lines)
    if state.halted:
        raise RuntimeError(
            "a call was served otherwise "
            f"({[line.get('failure_kind') for line in state.halted]}); this registration buys "
            "nothing more, and a re-run is a new registration"
        )
    for name in ("calls", "tokens", "seconds"):
        if state.used[name] >= LIMITS[name]:
            raise RuntimeError(f"the {name} ceiling is already reached by earlier invocations")
    number = state.invocations + 1
    base = {"invocation": number, "registration_sha256": sha_file(paths.registration)}
    append_ledger(paths.ledger, {**base, "event": "started", "started_at": now(),
                                 "pid": os.getpid(), "prior": state.used,
                                 "interrupted_before": len(state.interrupted),
                                 "executable": sys.executable})
    binary_guard = guard or stat_guard(paths.root / reg["binary"]["folder"])
    used = dict(state.used)
    attempts = Counter(state.attempts)
    answered = set(state.answered)
    seq = state.next_seq
    consecutive = 0
    stop: str | None = None
    fresh = 0
    try:
        for attempt_pass in range(1, MAX_ATTEMPTS + 1):
            for unit in units:
                if unit.unit_id in answered or attempts[unit.unit_id] >= attempt_pass:
                    continue
                stop = admit(unit.role, used) or binary_guard()
                if stop is None:
                    try:
                        check_lock(paths)
                        check_frozen(reg, paths)
                    except RuntimeError as error:
                        stop = f"halt:{error}"
                if stop is not None:
                    break
                attempt = attempts[unit.unit_id] + 1
                append_ledger(paths.ledger, {**base, "event": "dispatch", "seq": seq,
                                             "unit": unit.unit_id, "role": unit.role,
                                             "cell": unit.cell.name, "attempt": attempt,
                                             "at": now()})
                fields = dispatch(unit, attempt, seq, request_for(unit, inputs),
                                  request_digest_for(unit, inputs), paths=paths, reg=reg,
                                  provider_factory=provider_factory, clock=clock)
                append_ledger(paths.ledger, {**base, "event": "call", "seq": seq,
                                             "unit": unit.unit_id, "role": unit.role,
                                             "cell": unit.cell.name, "attempt": attempt,
                                             **fields})
                seq += 1
                fresh += 1
                attempts[unit.unit_id] = attempt
                used["calls"] += 1
                used["tokens"] += (float(fields["tokens"]) if fields["usage_known"]
                                   else RESERVE[unit.role]["tokens"])
                used["seconds"] += fields["wall_ms"] / 1000.0
                if fields["status"] in ANSWER_STATUSES:
                    answered.add(unit.unit_id)
                log(f"  [{len(answered)}/{len(units)}] {unit.unit_id} attempt {attempt}: "
                    f"{fields['status']} tokens={fields['tokens']} wall={fields['wall_ms']}ms")
                if fields["status"] == "halted":
                    stop = f"halt:{fields['failure_kind']}"
                    break
                consecutive = consecutive + 1 if fields["status"] == "transport_failure" else 0
                if consecutive >= TRANSPORT_CIRCUIT:
                    stop = "transport_circuit"
                    break
            if stop is not None:
                break
    except BaseException as error:
        append_ledger(paths.ledger, {**base, "event": "finished", "finished_at": now(),
                                     "stop": f"error:{type(error).__name__}", "complete": False,
                                     "fresh_calls": fresh, "used": used})
        raise
    missing = [unit.unit_id for unit in units if unit.unit_id not in answered]
    line = {**base, "event": "finished", "finished_at": now(), "stop": stop,
            "complete": stop is None and not missing, "fresh_calls": fresh, "used": used,
            "missing": missing}
    append_ledger(paths.ledger, line)
    return line


def refuse_while_held(paths: Paths) -> None:
    """A reading, or a close, never happens while this arm holds the box: a run may be live."""
    try:
        text = paths.lock_holder.read_text(encoding="utf-8-sig")
    except OSError:
        return
    if text.startswith(LOCK_PREFIX):
        raise RuntimeError("runs/box.lock names this arm, so a run may be live; release the lock "
                           "once the run process has ended (check it by PID), then try again")


def close(*, paths: Paths = DEFAULT_PATHS) -> dict[str, Any]:
    """Record the operator's decision that a killed invocation will not be resumed."""
    if paths.results.exists():
        raise RuntimeError("a reading exists; nothing is closed after it")
    refuse_while_held(paths)
    lines = read_ledger(paths.ledger)
    if not lines:
        raise RuntimeError("no ledger: nothing to close")
    state = ledger_state(lines)
    if state.finished:
        raise RuntimeError("the last invocation finished: nothing to close")
    line = {"event": "closed", "invocation": state.invocations, "finished_at": now(),
            "stop": "closed_after_interruption", "complete": False, "used": state.used,
            "interrupted": [item["unit"] for item in state.interrupted]}
    append_ledger(paths.ledger, line)
    return line


# ====================================================================== the outcomes


def strict_conforms(parsed: Any) -> bool:
    """The registered summary schema, all of it: nested required fields, enums, no extras."""
    from jsonschema import Draft202012Validator

    from litharness.application.summarize import SUMMARY_SCHEMA

    return bool(Draft202012Validator(SUMMARY_SCHEMA).is_valid(parsed))


def handler_losses(parsed: Mapping[str, Any]) -> list[str]:
    """What `make_summary_handler`'s tolerant reads would silently drop from this answer."""
    from litharness.application.summarize import extract_delta
    from litharness.domain.extraction import normalise_subject
    from litharness.domain.promises import normalise_kind

    losses: list[str] = []
    delta = parsed.get("delta")
    if delta is not None and extract_delta(delta) is None:
        losses.append("delta")
    opened = parsed.get("promises_opened")
    if not isinstance(opened, list):
        losses.append("promises_opened")
    else:
        for item in opened:
            if not isinstance(item, dict):
                losses.append("opened_item")
                continue
            if not normalise_subject(str(item.get("subject", "") or "")) or not str(
                item.get("description", "") or ""
            ).strip():
                losses.append("opened_fields")
            kind = item.get("kind")
            if kind is not None and normalise_kind(kind) is None:
                losses.append("opened_kind")
    paid = parsed.get("promises_paid")
    if not isinstance(paid, list):
        losses.append("promises_paid")
    else:
        for item in paid:
            name = item if isinstance(item, str) else (
                item.get("subject") if isinstance(item, dict) else None
            )
            if not isinstance(name, str) or not normalise_subject(name):
                losses.append("paid_item")
    return losses


def evidence_quotes(parsed: Mapping[str, Any]) -> list[str]:
    quotes = [item.get("evidence_quote") for item in opened_items(parsed)]
    quotes += [entry.get("evidence_quote") for entry in paid_entries(parsed)]
    return [quote for quote in quotes if isinstance(quote, str) and quote.strip()]


def validators(parsed: Any, scene_text: str) -> dict[str, Any]:
    """The two registered validator families for one answer, and their parts."""
    from litharness.application.summarize import exact_evidence_span

    if not isinstance(parsed, dict):
        return {"parsed": False, "strict_schema": False, "handler_usable": False, "losses": [],
                "conformance": False, "quotes": 0, "quotes_located": 0, "evidence": False}
    strict = strict_conforms(parsed)
    losses = handler_losses(parsed)
    quotes = evidence_quotes(parsed)
    located = sum(1 for quote in quotes if exact_evidence_span(scene_text, quote) is not None)
    return {
        "parsed": True,
        "strict_schema": strict,
        "handler_usable": not losses,
        "losses": losses,
        "conformance": strict and not losses,
        "quotes": len(quotes),
        "quotes_located": located,
        "evidence": located == len(quotes),
    }


def _jaccard(left: set[Any], right: set[Any]) -> float:
    return 1.0 if not left and not right else len(left & right) / len(left | right)


def _overlap(left: Counter[Any], right: Counter[Any]) -> float:
    total = max(sum(left.values()), sum(right.values()))
    return 1.0 if total == 0 else sum((left & right).values()) / total


def components(answer: Any, record: Mapping[str, Any], shown: Sequence[str]) -> dict[str, float]:
    """The five reported agreement components of one answer with a reference answer (the
    accepted record, or the reference Astra in the current block). Each is symmetric."""
    from litharness.application.summarize import extract_delta
    from litharness.domain.extraction import normalise_subject
    from litharness.domain.promises import normalise_kind

    if not isinstance(answer, dict):
        return dict.fromkeys(REPORTED_COMPONENTS, 0.0)
    mine, theirs = extract_delta(answer.get("delta")), extract_delta(record.get("delta"))
    if mine is None and theirs is None:
        who = 1.0
    elif mine is None or theirs is None:
        who = 0.0
    else:
        who = float(text_norm(mine["who"]) == text_norm(theirs["who"]))
    matched = {normalise_subject(name) for name in paid_split(answer, shown)[0]}
    accepted = {normalise_subject(name) for name in paid_split(record, shown)[0]}
    opened, accepted_opened = recordable_opened(answer), recordable_opened(record)
    largest = max(len(opened), len(accepted_opened), 1)
    kinds = Counter(normalise_kind(item.get("kind")) for item in opened)
    accepted_kinds = Counter(normalise_kind(item.get("kind")) for item in accepted_opened)
    return {
        "delta_presence": float((mine is None) == (theirs is None)),
        "delta_who": who,
        "paid_matched_set": float(matched == accepted),
        "opened_count": 1.0 - abs(len(opened) - len(accepted_opened)) / largest,
        "opened_kinds": _overlap(kinds, accepted_kinds),
    }


def composite(parts: Mapping[str, float]) -> float:
    return statistics.fmean(parts[name] for name in COMPOSITE_COMPONENTS)


def field_agreement(left: Any, right: Any, shown: Sequence[str]) -> dict[str, dict[str, float]]:
    """Every structured field, exact and normalized; reported beside the control, never decides."""
    from litharness.application.summarize import extract_delta
    from litharness.domain.extraction import normalise_subject
    from litharness.domain.promises import normalise_kind, parse_due_hint

    if not isinstance(left, dict) or not isinstance(right, dict):
        return {name: {"exact": 0.0, "normalized": 0.0} for name in STRUCTURED_FIELDS}
    out: dict[str, dict[str, float]] = {}
    raw_left, raw_right = left.get("delta"), right.get("delta")
    delta_left, delta_right = extract_delta(raw_left), extract_delta(raw_right)
    out["delta.null"] = {"exact": float((raw_left is None) == (raw_right is None)),
                         "normalized": float((delta_left is None) == (delta_right is None))}
    for key in DELTA_KEYS:
        exact_left = raw_left.get(key) if isinstance(raw_left, dict) else None
        exact_right = raw_right.get(key) if isinstance(raw_right, dict) else None
        norm_left = text_norm(delta_left[key]) if delta_left else None
        norm_right = text_norm(delta_right[key]) if delta_right else None
        out[f"delta.{key}"] = {"exact": float(exact_left == exact_right),
                               "normalized": float(norm_left == norm_right)}
    opened_left, opened_right = opened_items(left), opened_items(right)

    def values(items: Sequence[Mapping[str, Any]], key: str) -> list[Any]:
        return [item.get(key) for item in items]

    out["promises_opened.count"] = {
        "exact": float(len(opened_left) == len(opened_right)),
        "normalized": float(len(recordable_opened(left)) == len(recordable_opened(right))),
    }
    for key in ("subject", "description", "evidence_quote"):
        raw_l = {str(v) for v in values(opened_left, key) if isinstance(v, str) and v.strip()}
        raw_r = {str(v) for v in values(opened_right, key) if isinstance(v, str) and v.strip()}
        normal = normalise_subject if key == "subject" else text_norm
        out[f"promises_opened.{key}"] = {
            "exact": _jaccard(raw_l, raw_r),
            "normalized": _jaccard({normal(v) for v in raw_l}, {normal(v) for v in raw_r}),
        }
    out["promises_opened.kind"] = {
        "exact": _overlap(Counter(json.dumps(v) for v in values(opened_left, "kind")),
                          Counter(json.dumps(v) for v in values(opened_right, "kind"))),
        "normalized": _overlap(Counter(normalise_kind(v) for v in values(opened_left, "kind")),
                               Counter(normalise_kind(v) for v in values(opened_right, "kind"))),
    }
    out["promises_opened.due_hint"] = {
        "exact": _overlap(Counter(json.dumps(v) for v in values(opened_left, "due_hint")),
                          Counter(json.dumps(v) for v in values(opened_right, "due_hint"))),
        "normalized": _overlap(
            Counter(parse_due_hint(v) for v in values(opened_left, "due_hint")),
            Counter(parse_due_hint(v) for v in values(opened_right, "due_hint")),
        ),
    }
    paid_left, paid_right = paid_entries(left), paid_entries(right)
    raw_paid_left = left.get("promises_paid") if isinstance(left.get("promises_paid"), list) else []
    raw_paid_right = (right.get("promises_paid") if isinstance(right.get("promises_paid"), list)
                      else [])
    out["promises_paid.count"] = {"exact": float(len(raw_paid_left) == len(raw_paid_right)),
                                  "normalized": float(len(paid_left) == len(paid_right))}
    names_left = {str(entry["subject"]) for entry in paid_left}
    names_right = {str(entry["subject"]) for entry in paid_right}
    out["promises_paid.subject"] = {
        "exact": _jaccard(names_left, names_right),
        "normalized": _jaccard({normalise_subject(n) for n in names_left},
                               {normalise_subject(n) for n in names_right}),
    }
    matched_left, matched_right = paid_split(left, shown)[0], paid_split(right, shown)[0]
    out["promises_paid.matched"] = {
        "exact": float(set(matched_left) == set(matched_right)),
        "normalized": float({normalise_subject(n) for n in matched_left}
                            == {normalise_subject(n) for n in matched_right}),
    }
    quotes_left = {q for q in (e.get("evidence_quote") for e in paid_left)
                   if isinstance(q, str) and q.strip()}
    quotes_right = {q for q in (e.get("evidence_quote") for e in paid_right)
                    if isinstance(q, str) and q.strip()}
    out["promises_paid.evidence_quote"] = {
        "exact": _jaccard(quotes_left, quotes_right),
        "normalized": _jaccard({text_norm(q) for q in quotes_left},
                               {text_norm(q) for q in quotes_right}),
    }
    return out


def prose(parsed: Any, names: Sequence[str], amounts: Sequence[str]) -> dict[str, Any]:
    """Length and whether the scene's names and numbers appear. Never scored for quality."""
    from litharness.application.summarize import extract_delta

    if not isinstance(parsed, dict):
        return {"words": None, "words_total": None, "names_required": len(names),
                "names_present": 0, "quantities_required": len(amounts), "quantities_present": 0}
    words = {field: len(str(parsed.get(field, "") or "").split()) for field in PROSE_FIELDS}
    blob = " ".join(str(parsed.get(field, "") or "") for field in PROSE_FIELDS)
    delta = extract_delta(parsed.get("delta")) or {}
    with_delta = blob + " " + " ".join(delta.values())
    return {
        "words": words,
        "words_total": sum(words.values()),
        "names_required": len(names),
        "names_present": sum(1 for name in names if _contains(blob, name)),
        "quantities_required": len(amounts),
        "quantities_present": sum(1 for amount in amounts if _contains(with_delta, amount)),
    }


def summary_outcome(unit_input: Mapping[str, Any], answer: Any, status: str, kind: str | None,
                    usage: Mapping[str, Any] | None, wall_ms: int | None,
                    reference: Any) -> dict[str, Any]:
    """Everything the reading computes for one answer.

    `reference` is what agreement is scored against: the accepted record in the recorded
    block, the reference Astra's answer in the current block. With no parsed reference
    (the reference cell itself, or a reference that did not parse) there is no agreement."""
    shown = unit_input["shown"]
    scored = isinstance(reference, dict)
    parts = components(answer, reference, shown) if scored else None
    unmatched = paid_split(answer, shown)[1] if isinstance(answer, dict) else []
    return {
        "status": status,
        "unusable_kind": kind if status == "answered_unusable" else None,
        "parsed": isinstance(answer, dict),
        "validators": validators(answer, unit_input["scene_text"]),
        "components": parts,
        "composite": composite(parts) if parts is not None else None,
        "fields": field_agreement(answer, reference, shown) if scored else None,
        "paid_unmatched": len(unmatched),
        "prose": prose(answer, unit_input["required_names"], unit_input["quantities"]),
        "usage": dict(usage or {}),
        "tokens": sum(int(v or 0) for v in (usage or {}).values()),
        "wall_ms": wall_ms,
    }


# ------------------------------------------------------------------------ the statistics


def binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def cp_upper(k: int, n: int, alpha: float) -> float:
    """Exact one-sided upper bound on a binomial rate: the largest p with P(X <= k) >= alpha."""
    if k >= n:
        return 1.0
    low, high = k / n, 1.0
    for _ in range(100):
        middle = (low + high) / 2
        if binomial_cdf(k, n, middle) > alpha:
            low = middle
        else:
            high = middle
    return high


def cp_lower(k: int, n: int, alpha: float) -> float:
    """Exact one-sided lower bound: the smallest p with P(X >= k) >= alpha."""
    if k <= 0:
        return 0.0
    low, high = 0.0, k / n
    for _ in range(100):
        middle = (low + high) / 2
        if 1 - binomial_cdf(k - 1, n, middle) < alpha:
            low = middle
        else:
            high = middle
    return low


def validator_test(candidate: Sequence[bool], control: Sequence[bool], alpha: float
                   ) -> dict[str, Any]:
    """Non-inferiority of a per-scene pass flag, paired by scene.

    b scenes fail on the candidate only, c on the control only; the excess failure rate is
    p10 - p01 <= p10, so the exact upper bound on p10 bounds it (pass). Fail needs the exact
    lower bound on p10 less the upper bound on p01, each at alpha / 2, above the margin.
    """
    n = len(candidate)
    if n != len(control) or n == 0:
        raise ValueError("paired flags of equal, non-zero length are required")
    only_candidate = sum(1 for mine, theirs in zip(candidate, control, strict=True)
                         if not mine and theirs)
    only_control = sum(1 for mine, theirs in zip(candidate, control, strict=True)
                       if mine and not theirs)
    upper = cp_upper(only_candidate, n, alpha)
    lower = cp_lower(only_candidate, n, alpha / 2) - cp_upper(only_control, n, alpha / 2)
    verdict = ("pass" if upper <= VALIDATOR_MARGIN
               else "fail" if lower > VALIDATOR_MARGIN else "inconclusive")
    return {"n": n, "candidate_passes": sum(candidate), "control_passes": sum(control),
            "candidate_only_failures": only_candidate, "control_only_failures": only_control,
            "excess_upper_bound": upper, "excess_lower_bound": lower,
            "margin": VALIDATOR_MARGIN, "alpha": alpha, "verdict": verdict}


def settlement_test(candidate: Sequence[bool], control: Sequence[bool], alpha: float
                    ) -> dict[str, Any]:
    """Non-inferiority of a per-scene agreement flag whose control is itself noisy, paired.

    The flag is "settles the same set of listed promises as the reference". b scenes agree on
    the control only, c on the candidate only; the candidate's excess disagreement rate is
    p10 - p01. With probability at least 1 - alpha, p10 is under the exact upper bound on b/n
    and p01 over the exact lower bound on c/n, each at alpha / 2, so the difference of the two
    bounds bounds the excess: **pass** when it is at most the margin. **Fail** when the lower
    bound on p10 less the upper bound on p01 exceeds the margin; otherwise inconclusive.
    """
    n = len(candidate)
    if n != len(control) or n == 0:
        raise ValueError("paired flags of equal, non-zero length are required")
    only_control = sum(1 for mine, theirs in zip(candidate, control, strict=True)
                       if not mine and theirs)
    only_candidate = sum(1 for mine, theirs in zip(candidate, control, strict=True)
                         if mine and not theirs)
    upper = cp_upper(only_control, n, alpha / 2) - cp_lower(only_candidate, n, alpha / 2)
    lower = cp_lower(only_control, n, alpha / 2) - cp_upper(only_candidate, n, alpha / 2)
    verdict = ("pass" if upper <= SETTLEMENT_MARGIN
               else "fail" if lower > SETTLEMENT_MARGIN else "inconclusive")
    return {"n": n, "candidate_agrees": sum(candidate), "control_agrees": sum(control),
            "control_only_agreements": only_control,
            "candidate_only_agreements": only_candidate,
            "excess_upper_bound": upper, "excess_lower_bound": lower,
            "margin": SETTLEMENT_MARGIN, "margin_scenes": SETTLEMENT_MARGIN * n,
            "alpha": alpha, "verdict": verdict}


def agreement_test(candidate: Sequence[float], control: Sequence[float], alpha: float
                   ) -> dict[str, Any]:
    """Non-inferiority of the paired per-scene composite: t bounds on the mean difference."""
    if len(candidate) != EXPECTED_SCENES or len(control) != EXPECTED_SCENES:
        raise ValueError(f"the registered t quantile is for {EXPECTED_SCENES} paired scenes")
    if not math.isclose(alpha, ALPHA / CANDIDATES["summary"]):
        raise ValueError("the registered t quantile is for alpha 0.025")
    differences = [mine - theirs for mine, theirs in zip(candidate, control, strict=True)]
    mean = statistics.fmean(differences)
    sd = statistics.stdev(differences)
    half = T_CRITICAL_23 * sd / math.sqrt(len(differences))
    lower, upper = mean - half, mean + half
    verdict = ("pass" if lower >= -AGREEMENT_MARGIN
               else "fail" if upper < -AGREEMENT_MARGIN else "inconclusive")
    return {"n": len(differences), "candidate_mean": statistics.fmean(candidate),
            "control_mean": statistics.fmean(control), "mean_difference": mean,
            "sd_difference": sd, "lower": lower, "upper": upper, "margin": AGREEMENT_MARGIN,
            "alpha": alpha, "verdict": verdict}


def combine(verdicts: Sequence[str]) -> str:
    if all(verdict == "pass" for verdict in verdicts):
        return "pass"
    if any(verdict == "fail" for verdict in verdicts):
        return "fail"
    return "inconclusive"


Rows = Mapping[str, Mapping[str, Mapping[str, Any]]]


def _validator_tests(mine: Mapping[str, Mapping[str, Any]],
                     control: Mapping[str, Mapping[str, Any]], scenes: Sequence[str],
                     alpha: float) -> dict[str, Any]:
    return {
        family: validator_test([mine[s]["validators"][family] for s in scenes],
                               [control[s]["validators"][family] for s in scenes], alpha)
        for family in ("conformance", "evidence")
    }


def _floor_tests(mine: Mapping[str, Mapping[str, Any]], floor: Mapping[str, Mapping[str, Any]],
                 scenes: Sequence[str], alpha: float, unscored: Sequence[str]
                 ) -> dict[str, Any]:
    """The settlement and agreement tests: the candidate's agreement with the reference against
    the floor's. A floor that did not parse (or a reference that did not, in the current block)
    has no agreement to read against, so both tests are inconclusive rather than scored in the
    candidate's favour."""
    if unscored:
        withheld = {"verdict": "inconclusive", "reason": "the control or reference has no parsed "
                    "answer in these scenes, so the floor is undefined there",
                    "scenes": list(unscored)}
        return {"settlement": dict(withheld), "agreement": dict(withheld)}
    return {
        "settlement": settlement_test(
            [mine[s]["components"]["paid_matched_set"] == 1.0 for s in scenes],
            [floor[s]["components"]["paid_matched_set"] == 1.0 for s in scenes], alpha),
        "agreement": agreement_test([float(mine[s]["composite"]) for s in scenes],
                                    [float(floor[s]["composite"]) for s in scenes], alpha),
    }


def recorded_block_tests(mine: Mapping[str, Mapping[str, Any]],
                         control: Mapping[str, Mapping[str, Any]], scenes: Sequence[str],
                         alpha: float) -> dict[str, Any]:
    """Recorded wording: the candidate and the fresh Astra, each against the accepted record."""
    unscored = [s for s in scenes if not control[s]["parsed"]]
    return {**_validator_tests(mine, control, scenes, alpha),
            **_floor_tests(mine, control, scenes, alpha, unscored)}


def current_block_tests(mine: Mapping[str, Mapping[str, Any]],
                        reference: Mapping[str, Mapping[str, Any]],
                        floor: Mapping[str, Mapping[str, Any]], scenes: Sequence[str],
                        ledger_scenes: Sequence[str], alpha: float) -> dict[str, Any]:
    """Current wording: validators against the reference Astra, a clean-copy test over the
    scenes that listed a ledger, and agreement with the reference against the second Astra's."""
    tests = _validator_tests(mine, reference, scenes, alpha)
    tests["clean_copy"] = validator_test(
        [mine[s]["paid_unmatched"] == 0 and mine[s]["parsed"] for s in ledger_scenes],
        [reference[s]["paid_unmatched"] == 0 and reference[s]["parsed"] for s in ledger_scenes],
        alpha,
    )
    unscored = [s for s in scenes if not reference[s]["parsed"] or not floor[s]["parsed"]]
    return {**tests, **_floor_tests(mine, floor, scenes, alpha, unscored)}


def summary_decision(recorded: Rows, current: Rows, scenes: Sequence[str],
                     ledger_scenes: Sequence[str]) -> dict[str, Any]:
    """Each candidate cell against the controls of both blocks, scene-paired.

    INCOMPLETE on any missing answer a test needs; PASS only when every test of both blocks
    passes (an intersection-union test: no further division of alpha); FAIL when any fails."""
    alpha = ALPHA / CANDIDATES["summary"]
    control = recorded.get(ASTRA.name, {})
    reference = current.get(ASTRA.name, {})
    floor = current.get(ASTRA_FLOOR.name, {})
    decisions: dict[str, Any] = {}
    for cell in SUMMARY_CANDIDATES:
        mine_recorded = recorded.get(cell.name, {})
        mine_current = current.get(cell.name, {})
        missing = [f"recorded/{s}" for s in scenes
                   if s not in mine_recorded or s not in control]
        missing += [f"current/{s}" for s in scenes
                    if any(s not in table for table in (mine_current, reference, floor))]
        if missing:
            decisions[cell.name] = {"verdict": "incomplete", "missing": missing}
            continue
        tests = {
            "recorded": recorded_block_tests(mine_recorded, control, scenes, alpha),
            "current": current_block_tests(mine_current, reference, floor, scenes,
                                           ledger_scenes, alpha),
        }
        decisions[cell.name] = {
            "verdict": combine([test["verdict"] for block in tests.values()
                                for test in block.values()]),
            "tests": tests,
            "tokens": sum(mine_recorded[s]["tokens"] + mine_current[s]["tokens"]
                          for s in scenes),
        }
    passing = [name for name, item in decisions.items() if item["verdict"] == "pass"]
    chosen = min(passing, key=lambda name: (decisions[name]["tokens"],
                                            name != LUNA_MEDIUM.name)) if passing else None
    cell = next((item for item in SUMMARY_CANDIDATES if item.name == chosen), None)
    return {
        "candidates": decisions,
        "proposal": None if cell is None else {
            "role": "mechanical (scene summaries)",
            "provider": "codex",
            "tier": "basic",
            "model": cell.model,
            "effort": cell.effort,
            "cell": cell.name,
            "scope": "LITHARNESS_PROVIDER=codex only. The role map is provider-agnostic "
            "(routing.ModelRouting.from_environ applies LITHARNESS_MODEL_TIERS on either "
            "provider), so moving this role would also move Claude summaries to "
            "claude-haiku-4-5, which nothing here tested; enacting it needs a Claude arm on the "
            "same requests or a per-provider role map first",
            "licence": "a proposal to the operator; nothing moves without the operator's agreement",
        },
        "tie_break": "fewest recorded tokens over both blocks, then medium effort",
    }


# ------------------------------------------------------------------------------- seeds


def structure(records: Sequence[Any]) -> dict[str, Any]:
    """The declared shape of a world, by the domain's own readers. Counts and ids only."""
    from litharness.domain import worlds

    protagonists = worlds.entities_with_role(records, "protagonist")
    systems = worlds.entities_with_role(records, "system")
    capabilities = set(worlds.capabilities(records))
    return {
        "protagonists": list(protagonists),
        "systems": list(systems),
        "grant_counts": sorted(
            len([s for s in worlds.governed(records, system) if s in capabilities])
            for system in systems
        ),
        "ladder_lengths": sorted(
            len(worlds.ladder_of(records, criterion)) for criterion in worlds.criteria(records)
        ),
        "cast": list(worlds.entities_with_role(records, "cast")),
        "status_sheet": any(record.predicate == "status_sheet" for record in records),
        "protagonist_standing": bool(protagonists)
        and bool(worlds.standing_of(records, protagonists[0])),
        "records": len(records),
        "by_predicate": dict(sorted(Counter(record.predicate for record in records).items())),
    }


def seed_components(shape: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, float]:
    return {
        "protagonists": float(shape["protagonists"] == record["protagonists"]),
        "system_count": float(len(shape["systems"]) == len(record["systems"])),
        "ladder_lengths": float(shape["ladder_lengths"] == record["ladder_lengths"]),
        "grant_counts": float(shape["grant_counts"] == record["grant_counts"]),
        "cast": _jaccard(set(shape["cast"]), set(record["cast"])),
        "status_sheet": float(shape["status_sheet"] == record["status_sheet"]),
    }


def complaint_kind(text: str) -> str:
    """A complaint with its subject, quoted values and numbers masked: the check's own template."""
    body = str(text).split(" ", 1)[1] if " " in str(text) else str(text)
    body = re.sub(r"'[^']*'|\"[^\"]*\"|`[^`]*`", "...", body)
    body = re.sub(r"\b\d+\b", "N", body)
    return " ".join(body.split()[:8])


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list | dict | tuple) else int(bool(value))


def parse_check(code: int, stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        return {"exit": code, "parsed": False, "ok": False}
    complaints = [str(item) for item in payload.get("complaints") or []]
    return {
        "exit": code,
        "parsed": True,
        "ok": bool(payload.get("ok")),
        "complaints": len(complaints),
        "complaint_kinds": dict(Counter(complaint_kind(item) for item in complaints)),
        **{key: _count(payload.get(key)) for key in (
            "would_not_finish", "will_not_resolve", "unmanifested", "snapshot_faults",
            "would_breach", "machinery_names", "unplaceable", "gaps")},
    }


def bridge_stats(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """The tool bridge's own receipts: commands by verb, failures, declarations and refusals."""
    rows = []
    for text in str((raw or {}).get("commands_jsonl") or "").splitlines():
        with contextlib.suppress(json.JSONDecodeError):
            rows.append(json.loads(text))
    results = [row for row in rows if isinstance(row, dict) and row.get("phase") == "result"]
    verbs: Counter[str] = Counter()
    nonzero: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    declared = refused = 0
    for row in results:
        argv = row.get("argv") or []
        verb = " ".join(str(part) for part in argv[3:5]) if len(argv) >= 5 else "(not executed)"
        verbs[verb] += 1
        if row.get("error_kind"):
            errors[str(row["error_kind"])] += 1
        elif row.get("returncode") not in (0, None):
            nonzero[verb] += 1
        if verb == "world declare-batch" and not row.get("error_kind"):
            counted = _batch_counts(str(row.get("stdout") or ""))
            declared += counted[0]
            refused += counted[1]
        elif verb == "world declare" and not row.get("error_kind"):
            declared += int(row.get("returncode") == 0)
            refused += int(row.get("returncode") not in (0, None))
    return {"commands": len(results), "by_verb": dict(sorted(verbs.items())),
            "nonzero_exit_by_verb": dict(sorted(nonzero.items())),
            "bridge_errors_by_kind": dict(sorted(errors.items())),
            "declared": declared, "declaration_refusals": refused}


def _batch_counts(stdout: str) -> tuple[int, int]:
    with contextlib.suppress(json.JSONDecodeError, TypeError, ValueError):
        payload = json.loads(stdout)
        if isinstance(payload, dict):
            return int(payload.get("declared") or 0), int(payload.get("refused") or 0)
    found = re.search(r"\((\d+) declared, (\d+) refused", stdout)
    return (int(found.group(1)), int(found.group(2))) if found else (0, 0)


WorldCli = Callable[[Path, Sequence[str]], tuple[int, str, str]]


def run_world_cli(database: Path, arguments: Sequence[str]) -> tuple[int, str, str]:
    """A world command through the production CLI on a copy, offline."""
    completed = subprocess.run(
        [sys.executable, "-m", "litharness", "--database", str(database), *arguments],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=offline_environment(), timeout=600, check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def store_shape(database: Path, accepted: bool) -> dict[str, Any]:
    """The accepted copy's canon, or its in-force proposals read as if accepted when refused."""
    import litharness_contracts as lc

    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import integrity

    with SqliteStore.open_read_only(database) as store:
        book_id, branch_id, _ = store.branches()[0]
        records = store.state_records(book_id, branch_id)
        times = store.state_record_times(book_id, branch_id)
    canon = [record for record in records if record.authority in {
        lc.StateAuthority.ACCEPTED_CANON, lc.StateAuthority.AUTHOR_LOCKED}]
    if accepted:
        view, basis = canon, "accepted"
    else:
        view = [dataclasses.replace(record, authority=lc.StateAuthority.ACCEPTED_CANON)
                for record in integrity.in_force(records, declared_at=times)]
        basis = "proposed_as_if_accepted"
    shape = structure(view)
    shape["basis"] = basis
    shape["authority"] = dict(sorted(Counter(r.authority.value for r in records).items()))
    return shape


SeedInspector = Callable[[Path, Path], dict[str, Any]]


def inspect_seed(world_cli: WorldCli = run_world_cli,
                 shape_reader: Callable[[Path, bool], dict[str, Any]] = store_shape
                 ) -> SeedInspector:
    """World check, accept on a copy, check again, and the declared shape; the seed store stays."""

    def inspect(store: Path, work: Path) -> dict[str, Any]:
        # A stale write-ahead log from an earlier, interrupted reading would replay into the new
        # copy, so the working folder starts empty every time.
        shutil.rmtree(work, ignore_errors=True)
        pre, accept = work / "check" / "book.db", work / "accept" / "book.db"
        copy_store(store, pre)
        copy_store(store, accept)
        pre_check = parse_check(*world_cli(pre, ["world", "check", "--json"])[:2])
        code, _stdout, stderr = world_cli(accept, ["world", "accept"])
        post_check = parse_check(*world_cli(accept, ["world", "check", "--json"])[:2])
        refusals = [line.split("litharness:", 1)[1].strip() for line in stderr.splitlines()
                    if line.startswith("litharness:")]
        return {
            "pre_check": pre_check,
            "accept_exit": code,
            "accept_refusal_kinds": dict(Counter(complaint_kind(item) for item in refusals)),
            "post_check": post_check,
            "shape": shape_reader(accept, code == 0),
        }

    return inspect


def seed_clean(outcome: Mapping[str, Any]) -> bool:
    return (outcome.get("status") == "answered"
            and bool(outcome["pre_check"].get("ok"))
            and outcome["accept_exit"] == 0
            and bool(outcome["post_check"].get("ok"))
            and outcome["post_check"].get("would_not_finish", 1) == 0)


SEED_LICENCE = (
    "none: two replicates a side can show a gross failure and cannot establish reliability (a "
    "Sol clean 70% of the time would look clean in both 49% of the time), so no outcome here "
    "proposes a seed tier; that needs its own registration with enough replicates, and grow"
)


def seed_screen(rows: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    """The seed screen. It reads what two replicates a side can show and proposes nothing."""
    control = rows.get(ASTRA.name, {})
    candidate = rows.get("sol-medium", {})
    replicates = [f"r{index}" for index in range(SEED_REPLICATES)]
    missing = [f"{name}/{rep}" for name, table in (("astra-medium", control),
                                                   ("sol-medium", candidate))
               for rep in replicates if rep not in table]
    if missing:
        return {"verdict": "incomplete", "missing": missing, "proposal": None,
                "licence": SEED_LICENCE}
    clean_candidate = sum(seed_clean(candidate[rep]) for rep in replicates)
    clean_control = sum(seed_clean(control[rep]) for rep in replicates)
    agree_candidate = statistics.fmean(candidate[rep]["agreement"] for rep in replicates)
    agree_control = statistics.fmean(control[rep]["agreement"] for rep in replicates)
    if clean_candidate < clean_control:
        verdict = "failure_seen"
    elif clean_candidate == SEED_REPLICATES and agree_candidate >= (
        agree_control - SEED_AGREEMENT_MARGIN
    ):
        verdict = "no_gross_failure_seen"
    else:
        verdict = "unclear"
    return {
        "verdict": verdict,
        "clean_candidate": clean_candidate,
        "clean_control": clean_control,
        "agreement_candidate": agree_candidate,
        "agreement_control": agree_control,
        "margin": SEED_AGREEMENT_MARGIN,
        "proposal": None,
        "licence": SEED_LICENCE,
    }


# =========================================================================== analyse


def answer_receipts(paths: Paths, state: LedgerState, units: Sequence[Unit], inputs: Inputs,
                    version: str) -> dict[str, dict[str, Any]]:
    """Every answer's receipt, verified; refuses a transport failure kept as an answer (§235)."""
    by_id = {unit.unit_id: unit for unit in units}
    receipts: dict[str, dict[str, Any]] = {}
    for unit_id, line in state.answered.items():
        unit = by_id.get(unit_id)
        if unit is None:
            raise RuntimeError(f"the ledger answers {unit_id}, which no planned unit is")
        path = paths.root / str(line["receipt"])
        if not path.is_file() or sha_file(path) != line["receipt_sha256"]:
            raise RuntimeError(f"the receipt for {unit_id} is missing or changed")
        receipt = read_json(path)
        if receipt.get("status") != line["status"] or receipt.get("unit") != unit_id:
            raise RuntimeError(f"the receipt for {unit_id} disagrees with the ledger")
        if receipt.get("request_sha256") != request_digest_for(unit, inputs):
            raise RuntimeError(f"the receipt for {unit_id} is for another request")
        if receipt["status"] == "answered":
            if receipt.get("result") is None or receipt.get("failure") is not None:
                raise RuntimeError(f"{unit_id} is marked answered without a result")
            foreign = served_as_registered(receipt["result"].get("raw") or {}, unit, version,
                                           sys.executable)
            if foreign is not None:
                raise RuntimeError(f"{unit_id} was served otherwise ({foreign})")
        else:
            failure = receipt.get("failure") or {}
            status, _kind = classify_failure(_Failure(failure), receipt.get("attempt_raw"))
            if status != "answered_unusable":
                raise RuntimeError(f"{unit_id} keeps a transport failure as an answer (§235)")
        receipts[unit_id] = receipt
    return receipts


class _Failure(Exception):
    """A recorded failure re-read through `classify_failure`."""

    def __init__(self, failure: Mapping[str, Any]) -> None:
        super().__init__(str(failure.get("message", "")))
        self.kind = str(failure.get("provider_kind", "unknown"))


def transport_block(lines: Sequence[Mapping[str, Any]], state: LedgerState,
                    units: Sequence[Unit]) -> dict[str, Any]:
    """Read first, before any verdict: what the transport did and what is missing."""
    calls = [line for line in lines if line.get("event") == "call"]
    by_cell: dict[str, Counter[str]] = {}
    for line in calls:
        # The unit id's first part names the block: summary (recorded), current, or seed.
        key = f"{str(line['unit']).split('/', 1)[0]}/{line['cell']}"
        by_cell.setdefault(key, Counter())[str(line["status"])] += 1
    failures = Counter(str(line.get("failure_kind")) for line in calls
                       if line.get("status") == "transport_failure")
    unusable = Counter(str(line.get("failure_kind")) for line in calls
                       if line.get("status") == "answered_unusable")
    missing = [unit.unit_id for unit in units if unit.unit_id not in state.answered]
    finished = [line for line in lines if line.get("event") in {"finished", "closed"}]
    return {
        "invocations": state.invocations,
        "stops": [line.get("stop") for line in finished],
        "dispatched": int(state.used["calls"]),
        "by_cell_status": {key: dict(value) for key, value in sorted(by_cell.items())},
        "transport_failures_by_kind": dict(failures),
        "unusable_answers_by_kind": dict(unusable),
        "redispatched_units": sorted(u for u, n in state.attempts.items() if n > 1),
        "interrupted_dispatches": [line["unit"] for line in state.interrupted],
        "unknown_usage_attempts": state.unknown_usage,
        "halts": [line.get("failure_kind") for line in calls if line.get("status") == "halted"],
        "halted_units": [line["unit"] for line in state.halted],
        "used": state.used,
        "limits": LIMITS,
        "planned_units": len(units),
        "answered_units": len(state.answered),
        "missing_units": missing,
        "coverage": "complete" if not missing else "partial",
    }


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def cell_aggregate(outcomes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts and means over one cell's scenes. Numbers only. Agreement means are over the
    scenes that had a parsed reference (none for the current block's reference cell)."""
    validity = [item["validators"] for item in outcomes]
    scored = [item for item in outcomes if item["components"] is not None]
    prose_rows = [item["prose"] for item in outcomes]
    tokens = [item["tokens"] for item in outcomes]
    walls = [item["wall_ms"] for item in outcomes if item.get("wall_ms") is not None]
    usage_totals: Counter[str] = Counter()
    for item in outcomes:
        usage_totals.update({key: int(value or 0) for key, value in item["usage"].items()})
    words = [row["words_total"] for row in prose_rows if row["words_total"] is not None]
    return {
        "answers": len(outcomes),
        "unusable": sum(1 for item in outcomes if item["status"] == "answered_unusable"),
        "parse_failures_would_retry": sum(1 for v in validity if not v["parsed"]),
        "strict_schema_failures": sum(
            1 for v in validity if v["parsed"] and not v["strict_schema"]
        ),
        "handler_losses": dict(Counter(loss for v in validity for loss in v["losses"])),
        "conformance_passes": sum(1 for v in validity if v["conformance"]),
        "evidence_passes": sum(1 for v in validity if v["evidence"]),
        "quotes": sum(v["quotes"] for v in validity),
        "quotes_located": sum(v["quotes_located"] for v in validity),
        "paid_unmatched": sum(item["paid_unmatched"] for item in outcomes),
        "scenes_with_paid_unmatched": sum(1 for item in outcomes if item["paid_unmatched"]),
        "scored_scenes": len(scored),
        "composite_mean": _mean([item["composite"] for item in scored]),
        "component_means": {name: _mean([item["components"][name] for item in scored])
                            for name in REPORTED_COMPONENTS},
        "field_agreement": {
            field: {mode: _mean([item["fields"][field][mode] for item in scored])
                    for mode in ("exact", "normalized")}
            for field in STRUCTURED_FIELDS
        },
        "prose_words_mean": _mean(words),
        "prose_words_max": max(words, default=None),
        "names_required": sum(row["names_required"] for row in prose_rows),
        "names_present": sum(row["names_present"] for row in prose_rows),
        "quantities_required": sum(row["quantities_required"] for row in prose_rows),
        "quantities_present": sum(row["quantities_present"] for row in prose_rows),
        "tokens_total": sum(tokens),
        "tokens_mean": _mean(tokens),
        "tokens_max": max(tokens, default=None),
        "usage_totals": dict(usage_totals),
        "wall_ms_mean": _mean(walls),
        "wall_ms_max": max(walls, default=None),
    }


def analyse_summaries(inputs: Inputs, receipts: Mapping[str, Mapping[str, Any]],
                      units: Sequence[Unit], scenes: Sequence[str]) -> tuple[dict[str, Any],
                                                                             dict[str, Any]]:
    """Both summary blocks: the recorded wording against the accepted records, the current
    wording against the reference Astra, and the decision over both."""
    answers: dict[str, dict[str, dict[str, Any]]] = {"recorded": {}, "current": {}}
    for unit in units:
        if unit.role != "summary" or unit.unit_id not in receipts:
            continue
        receipt = receipts[unit.unit_id]
        result = receipt.get("result") or {}
        answer = result.get("parsed") if receipt["status"] == "answered" else None
        answers[unit.block].setdefault(unit.cell.name, {})[unit.item] = (answer, receipt)
    reference_answers = {scene: pair[0]
                         for scene, pair in answers["current"].get(ASTRA.name, {}).items()}
    rows: dict[str, dict[str, dict[str, dict[str, Any]]]] = {"recorded": {}, "current": {}}
    for block, table in answers.items():
        for cell_name, by_scene in table.items():
            for scene, (answer, receipt) in by_scene.items():
                unit_input = inputs.summaries[scene]
                if block == "recorded":
                    reference = unit_input["record"]["parsed"]
                elif cell_name == ASTRA.name:
                    reference = None
                else:
                    reference = reference_answers.get(scene)
                result = receipt.get("result") or {}
                failure = receipt.get("failure") or {}
                usage = (result.get("usage") if result
                         else attempt_usage(receipt.get("attempt_raw")))
                rows[block].setdefault(cell_name, {})[scene] = summary_outcome(
                    unit_input, answer, receipt["status"], failure.get("kind"), usage,
                    result.get("wall_ms") if result else None, reference,
                )
    record_rows = []
    for scene in scenes:
        unit_input = inputs.summaries[scene]
        record = unit_input["record"]
        record_rows.append(summary_outcome(unit_input, record["parsed"], "answered", None,
                                           record.get("usage"), record.get("wall_ms"),
                                           record["parsed"]))
    control_answers = {scene: pair[0]
                       for scene, pair in answers["recorded"].get(ASTRA.name, {}).items()}
    with_control = {}
    for cell in SUMMARY_CANDIDATES:
        mine = answers["recorded"].get(cell.name, {})
        pairs = [
            field_agreement(mine[s][0], control_answers[s], inputs.summaries[s]["shown"])
            for s in scenes if s in mine and isinstance(control_answers.get(s), dict)
        ]
        with_control[cell.name] = {
            field: {mode: _mean([pair[field][mode] for pair in pairs])
                    for mode in ("exact", "normalized")}
            for field in STRUCTURED_FIELDS
        }
    ledger_scenes = [scene for scene in scenes if inputs.summaries[scene]["shown"]]
    public = {
        "recorded": {
            "cells": {name: cell_aggregate(list(table.values()))
                      for name, table in rows["recorded"].items()},
            "record": cell_aggregate(record_rows),
            "agreement_with_control": with_control,
        },
        "current": {
            "reference": ASTRA.name,
            "floor": ASTRA_FLOOR.name,
            "ledger_scenes": len(ledger_scenes),
            "cells": {name: cell_aggregate(list(table.values()))
                      for name, table in rows["current"].items()},
        },
        "decision": summary_decision(rows["recorded"], rows["current"], scenes, ledger_scenes),
    }
    detail = {block: {name: {scene: {k: v for k, v in outcome.items() if k != "fields"}
                             for scene, outcome in table.items()}
                      for name, table in by_cell.items()}
              for block, by_cell in rows.items()}
    return public, detail


def analyse_seeds(paths: Paths, inputs: Inputs, receipts: Mapping[str, Mapping[str, Any]],
                  units: Sequence[Unit], inspector: SeedInspector
                  ) -> tuple[dict[str, Any], dict[str, Any]]:
    record = inputs.seed["record"]
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    for unit in units:
        if unit.role != "seed" or unit.unit_id not in receipts:
            continue
        receipt = receipts[unit.unit_id]
        result = receipt.get("result") or {}
        raw = result.get("raw") if result else receipt.get("attempt_raw")
        store = paths.root / str(receipt["store"])
        inspected = inspector(store, paths.analysis_dir / unit.slug(int(receipt["attempt"])))
        usage = result.get("usage") if result else attempt_usage(receipt.get("attempt_raw"))
        parts = seed_components(inspected["shape"], record)
        rows.setdefault(unit.cell.name, {})[unit.item] = {
            "status": receipt["status"],
            "unusable_kind": (receipt.get("failure") or {}).get("kind"),
            **inspected,
            "bridge": bridge_stats(raw),
            "components": parts,
            "agreement": statistics.fmean(parts.values()),
            "tokens": sum(int(v or 0) for v in (usage or {}).values()),
            "usage": dict(usage or {}),
            "wall_ms": result.get("wall_ms") if result else None,
        }
    for table in rows.values():
        for outcome in table.values():
            outcome["clean"] = seed_clean(outcome)

    def public_row(outcome: Mapping[str, Any]) -> dict[str, Any]:
        shape = outcome["shape"]
        return {
            "status": outcome["status"], "unusable_kind": outcome["unusable_kind"],
            "clean": outcome["clean"], "pre_check": outcome["pre_check"],
            "accept_exit": outcome["accept_exit"],
            "accept_refusal_kinds": outcome["accept_refusal_kinds"],
            "post_check": outcome["post_check"], "bridge": outcome["bridge"],
            "components": outcome["components"], "agreement": outcome["agreement"],
            "tokens": outcome["tokens"], "usage": outcome["usage"],
            "wall_ms": outcome["wall_ms"],
            "shape": {"basis": shape.get("basis"), "protagonists": len(shape["protagonists"]),
                      "systems": len(shape["systems"]), "grant_counts": shape["grant_counts"],
                      "ladder_lengths": shape["ladder_lengths"], "cast": len(shape["cast"]),
                      "status_sheet": shape["status_sheet"],
                      "protagonist_standing": shape["protagonist_standing"],
                      "records": shape["records"], "by_predicate": shape["by_predicate"],
                      "authority": shape.get("authority")},
        }

    public = {
        "cells": {name: {rep: public_row(outcome) for rep, outcome in sorted(table.items())}
                  for name, table in rows.items()},
        "record": {"protagonists": len(record["protagonists"]),
                   "systems": len(record["systems"]), "grant_counts": record["grant_counts"],
                   "ladder_lengths": record["ladder_lengths"], "cast": len(record["cast"]),
                   "status_sheet": record["status_sheet"],
                   "protagonist_standing": record["protagonist_standing"],
                   "records": record["records"]},
        "decision": seed_screen(rows),
    }
    return public, rows


NOT_ESTABLISHED: tuple[str, ...] = (
    "anything about quality: no prose field is scored, and agreement with Astra's record is "
    "not correctness",
    "any book but this one: 24 scenes and one world from one trial, one writer, one generator",
    "the current (post-§255) wording against an accepted record: none exists, so that block "
    "reads a candidate against a second Astra, not against what production accepted",
    "the ledger's feedback loop: each replayed request shows Astra's own ledger, so whether a "
    "candidate reproduces subjects it coined itself scenes earlier is untested",
    "downstream effect on drafting: summaries feed evicted context, and no chapter is drafted",
    "the Claude provider: a pass covers LITHARNESS_PROVIDER=codex only, and the role map would "
    "move Claude summaries to claude-haiku-4-5 too",
    "the Architect's seed on standard: two replicates a side are a screen, never a licence",
    "the Architect's grow, which is 7 of the trial's 8 Architect calls and most of its tokens",
    "title availability checks: no recorded request exists",
    "the served model: Codex JSONL reports the requested model, not a resolved one",
    "credits or dollars: Codex reports tokens only",
    "that the candidate is equivalent: a pass bounds a deficit at the registered margins only",
)


def analyse(
    *,
    paths: Paths = DEFAULT_PATHS,
    verifier: Callable[..., dict[str, Any]] = verify,
    inspector: SeedInspector | None = None,
) -> dict[str, Any]:
    """The reading, once: transport first, then the receipts, then the decision.

    Refused while the box lock names this arm, while the last invocation has no finished line,
    and once a reading exists; refused outside the pinned runtime, which the world CLI of the
    seed reading runs as well. It needs HEAD committed as registered but not pushed: `run`
    required the push before anything was bought. Writes the numbers to `results.json`
    (committed) and the ids and per-unit detail to the ignored local folder.
    """
    if paths.results.exists():
        raise RuntimeError(f"{rel(paths.results, paths.root)} exists; a reading is written once")
    refuse_while_held(paths)
    reg = verifier(paths, require_pushed=False)
    inputs = load_inputs(paths, reg)
    lines = read_ledger(paths.ledger)
    if not lines:
        raise RuntimeError("no ledger: nothing was bought")
    state = ledger_state(lines)
    if not state.finished:
        raise RuntimeError("the last invocation has no finished line: it is running, or it was "
                           "killed; resume it with run, or record that it will not be resumed "
                           "with close")
    scenes = list(reg["inputs"]["scenes"])
    units = plan(scenes)
    receipts = answer_receipts(paths, state, units, inputs, reg["binary"]["version"])
    transport = transport_block(lines, state, units)
    summaries, summary_detail = analyse_summaries(inputs, receipts, units, scenes)
    seeds, seed_detail = analyse_seeds(paths, inputs, receipts, units,
                                       inspector or inspect_seed())
    detail_path = paths.analysis_dir / "analysis.json"
    write_json(detail_path, {"summaries": summary_detail, "seeds": seed_detail,
                             "seed_record": inputs.seed["record"]})
    result = {
        "study": VERSION,
        "registration_sha256": sha_file(paths.registration),
        "registration_digest": reg["registration_digest"],
        "ledger_sha256": sha_file(paths.ledger),
        "analysis_sha256": sha_file(detail_path),
        "binary": reg["binary"],
        "transport": transport,
        "summaries": summaries,
        "seeds": seeds,
        "licence": "A summary candidate's pass licenses proposing `mechanical` on the basic tier "
        "to the operator for LITHARNESS_PROVIDER=codex only; enacting it needs a Claude arm on "
        "the same requests or a per-provider role map first. The seed screen licenses nothing. "
        "Nothing moves without the operator's agreement (docs/model-policy.md, Rules).",
        "not_established": list(NOT_ESTABLISHED),
    }
    write_new(paths.results, result)
    write_claim(paths, "observed")
    return result


# ============================================================ offline render modes


def render_seed_mode(database: Path, library: Path, out: Path) -> int:
    """The seed request the production CLI builds, stopped at the completion boundary.

    Runs under whichever interpreter executes this file (the trial's frozen runtime, or the
    pinned one), with billing disabled: the registry refuses a billing provider in test mode,
    and the completion call is replaced before it can be reached.
    """
    if os.environ.get("LITHARNESS_ENV") != "test":
        raise RuntimeError("the render boundary runs with billing disabled (LITHARNESS_ENV=test)")
    import litharness
    from litharness import cli

    reached: list[Any] = []

    def boundary(request: Any, **_: Any) -> tuple[None, str]:
        reached.append(request)
        return None, "model-tiers offline render boundary"

    original = cli._completion_call
    cli._completion_call = boundary  # type: ignore[assignment]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["--database", str(database), *TRIAL_GLOBAL_ARGS,
                             "--library", str(library), "architect", "seed"])
    finally:
        cli._completion_call = original  # type: ignore[assignment]
    if code != 2 or len(reached) != 1:
        raise RuntimeError(f"the seed command did not stop at one completion boundary ({code})")
    write_json(out, {"source": litharness.__file__, "returncode": code,
                     "request": serial(reached[0])})
    return 0


def render_summaries_mode(units_file: Path, out: Path) -> int:
    """Each unit's summary request, built the way the summary handler builds it.

    Runs under whichever interpreter executes this file. Per unit: the scene text and the
    ledger rows (`ledger_row`) in the order the recorded prompt listed them, no open threads
    (no recorded prompt carries a thread block), through `render_summary_prompt` and then the
    handler's own `CompletionRequest` fields (`make_summary_handler`). No store is opened.
    """
    import litharness
    from litharness.application.summarize import PROFILE, SUMMARY_SCHEMA, render_summary_prompt
    from litharness.domain.generation import PROFILES, CompletionRequest
    from litharness.domain.promises import Promise

    names = {field.name for field in dataclasses.fields(Promise)}
    requests: dict[str, Any] = {}
    for unit in read_json(units_file)["units"]:
        promises = tuple(
            Promise(**{key: value for key, value in row.items() if key in names})
            for row in unit["promises"]
        )
        system, prompt = render_summary_prompt(unit["text"], open_promises=promises)
        requests[str(unit["scene"])] = serial(CompletionRequest(
            prompt=prompt,
            system=system,
            schema=SUMMARY_SCHEMA,
            profile=PROFILE,
            call_class=str(unit["call_class"]),
            sampler=PROFILES[PROFILE],
            max_output_tokens=512,
        ))
    write_json(out, {"source": litharness.__file__, "requests": requests})
    return 0


def open_store_mode(database: Path, out: Path) -> int:
    """Open (and so migrate) one store under whichever interpreter executes this file."""
    import litharness
    from litharness.adapters.sqlite_store import SqliteStore

    with SqliteStore.open(database):
        pass
    write_json(out, {"source": litharness.__file__})
    return 0


# ============================================================================== CLI


def print_plan(paths: Paths = DEFAULT_PATHS) -> None:
    """The shape of the plan from the recorded calls alone. Opens no store and writes nothing."""
    rows = recorded_summary_calls(paths)
    phases = [str(row.get("phase", "")) for _path, row in rows]
    shaped = sum(1 for _path, row in rows if str(row["request"]["prompt"]).startswith(SCENE_PREFIX))
    units = plan([f"unit-{index + 1}" for index in range(len(rows))])
    counts = Counter(unit.block for unit in units)
    print(f"{VERSION}: {len(rows)} recorded `{SUMMARY_PROFILE}` requests (expected "
          f"{EXPECTED_SCENES}), {shaped} of them opening on the scene; {counts['recorded']} "
          f"recorded-wording units on {[c.name for c in SUMMARY_CELLS]}, {counts['current']} "
          f"current-wording units on {[c.name for c in CURRENT_CELLS]}, {counts['seed']} seed "
          f"units on {[c.name for c in SEED_CELLS]} in the order {list(SEED_ORDER)}")
    print(f"  ceilings {LIMITS}; reservations {RESERVE}; at most {MAX_ATTEMPTS} dispatches a unit")
    print(f"  recorded phases: {', '.join(phases)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("plan")
    prepare_parser = modes.add_parser("prepare")
    prepare_parser.add_argument("--codex-binary", type=Path, required=True)
    modes.add_parser("claim")
    modes.add_parser("run")
    modes.add_parser("close")
    modes.add_parser("analyse")
    seed_parser = modes.add_parser("render-seed")
    seed_parser.add_argument("--database", type=Path, required=True)
    seed_parser.add_argument("--library", type=Path, required=True)
    seed_parser.add_argument("--out", type=Path, required=True)
    summary_parser = modes.add_parser("render-summaries")
    summary_parser.add_argument("--units-file", type=Path, required=True)
    summary_parser.add_argument("--out", type=Path, required=True)
    store_parser = modes.add_parser("open-store")
    store_parser.add_argument("--database", type=Path, required=True)
    store_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "render-seed":
        return render_seed_mode(args.database, args.library, args.out)
    if args.mode == "render-summaries":
        return render_summaries_mode(args.units_file, args.out)
    if args.mode == "open-store":
        return open_store_mode(args.database, args.out)
    if args.mode == "plan":
        print_plan()
        return 0
    if args.mode == "claim":
        print(json.dumps(refresh_claim(), indent=2))
        return 0
    if args.mode == "prepare":
        registration = prepare(codex_binary=args.codex_binary)
        binary = {key: value for key, value in registration["binary"].items()
                  if key != "folder_hashes"}
        print(json.dumps({"units": registration["planned_units"], "binary": binary,
                          "runtime": registration["runtime"]["probe"],
                          "seed_profile": registration["inputs"]["seed_profile"],
                          "request_identity": registration["request_identity"]},
                         indent=2, default=str))
        print("wrote registration.json and claim.json; commit and push them before run")
        return 0
    if args.mode == "run":
        line = run()
        print(json.dumps({key: line[key] for key in ("stop", "complete", "fresh_calls", "used")},
                         indent=2))
        return 0 if line["complete"] else 2
    if args.mode == "close":
        print(json.dumps(close(), indent=2))
        return 0
    result = analyse()
    print(json.dumps({"transport": result["transport"],
                      "summary_decision": result["summaries"]["decision"],
                      "seed_screen": result["seeds"]["decision"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
