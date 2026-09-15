"""Reuse recorded worlds; compare only the production planning handoff."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import venv
import zipfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/chapter-coverage-20260915"
PARENT = ROOT / "runs/experience-workflow-20260915"
SUPPORT = HERE.parent / "experience-workflow-continuation-20260915/run.py"
spec = importlib.util.spec_from_file_location("coverage_support", SUPPORT)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
base = support.base
PARENT_RUNNER = HERE.parent / "experience-workflow-20260915/run.py"
REVISIONS = {"A": "d247331", "B": "aa33e6a"}
SOURCES = {"2": {"seed": 38, "outline": 58}, "4": {"seed": 46, "outline": 74}}
PHASES = ("chapter1", "drain1", "grow1", "accept-grow1", "chapter2", "drain2")
original_command = base.command


def order(phase):
    step = PHASES.index(phase) if phase in PHASES else 0
    return tuple(f"{arm}{case}" for index, case in enumerate(SOURCES)
                 for arm in ("AB" if (index + step) % 2 == 0 else "BA"))


def command(book, phase):
    if phase == "grow1":
        return ["architect", "grow", "--scene", "scene-1"]
    return original_command(book, phase)


def configure():
    base.LOCAL, base.HERE, base.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.INPUTS = {key: value for key, value in base.INPUTS.items() if key in SOURCES}
    base.REVISIONS, base.PHASES, base.order = REVISIONS, PHASES, order
    base.LIMITS = {"calls": 80, "tokens": 2000000, "seconds": 7200,
                   "book_calls": 20, "ticks_per_phase": 20}
    base.OWNER = "chapter-coverage-20260915: root task;"
    base.command, base.claim = command, claim
    base.transport_details = lambda raw, payload, book: support.details(raw, payload, book, LOCAL)


def source_call(case, role):
    return PARENT / "calls" / f"{SOURCES[case][role]:04d}-B{case}.json"


def replay_commands(call):
    """Only recorded successful declarations may mutate the reconstructed world."""
    from litharness.providers.codex_tools import _allowances, _validate_arguments

    allowances = _allowances(tuple(call["request"]["allowed_tools"]))
    result = []
    for line in call["result"]["raw"]["commands_jsonl"].splitlines():
        row = json.loads(line)
        if row.get("phase") != "result" or row.get("argv") is None:
            continue
        arguments = _validate_arguments(row["arguments"], allowances)
        if arguments[:2] == ["world", "declare-batch"]:
            if row["returncode"] != 0:
                raise RuntimeError("A failed declaration needs a separately specified replay")
            result.append(arguments)
        elif arguments[:2] not in (["world", "vocabulary"], ["world", "summary"],
                                   ["world", "check"], ["world", "query"]):
            raise RuntimeError("Unregistered seed operation")
    if not result:
        raise RuntimeError("No recorded declarations")
    return result


def setup(book):
    """Build a fresh empty book and replay source declarations with billing disabled."""
    from litharness import cli

    verify_origin(book)
    if os.environ.get("LITHARNESS_ENV") != "test":
        raise RuntimeError("Offline setup requires test mode")
    cli._completion_call = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("No completion during setup")
    )
    case, records = book[1], []
    args = original_command(book, "new")
    args[args.index("--book") + 1] = f"experience-B{case}"
    commands = [args, *replay_commands(base.read(source_call(case, "seed"))), ["world", "accept"]]
    for arguments in commands:
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli.main(base.base_args(book) + arguments)
        records.append({"arguments": arguments, "returncode": code,
                        "stdout": output.getvalue(), "stderr": error.getvalue()})
        base.write(LOCAL / "setup" / f"{book}.json", records)
        if code != 0:
            raise RuntimeError(f"Offline setup failed for {book}")
    if base.metadata(book)["accepted"] != 0:
        raise RuntimeError("Reconstructed store contains drafted prose")


def request_control(control, treatment, original, rule):
    """Exact fixed inputs, with only the implemented handoff changes allowed."""
    from litharness.application.outline import CHAPTER_OUTLINE_SCHEMA, CONCEPT_OUTLINE_SCHEMA

    if control != original:
        raise ValueError("Control request differs from the original pre-outline request")
    a, b = dict(control), dict(treatment)
    ap, bp = json.loads(a.pop("prompt")), json.loads(b.pop("prompt"))
    if b.pop("profile") != "planner.outline.v5" or a.pop("profile") != "planner.outline.v4":
        raise ValueError("Unexpected outline profiles")
    old_schema, new_schema = a.pop("schema"), b.pop("schema")
    if old_schema != CONCEPT_OUTLINE_SCHEMA or new_schema != CHAPTER_OUTLINE_SCHEMA:
        raise ValueError("Unexpected coverage schema")
    layout = bp.pop("writing_layout")
    expected = [{"chapter": i, "scene_ordinals": [i], "target_words": 1400}
                for i in range(1, 7)]
    if layout != {"chapters": expected, "target_scene_words": 1400}:
        raise ValueError("Treatment changed the chapter layout")
    if bp["rules"].count(rule) != 1:
        raise ValueError("Coverage rule is missing or duplicated")
    bp["rules"].remove(rule)
    if ap != bp or a != b:
        raise ValueError("Treatment changed inputs beyond the registered handoff")
    return True


def preflight(book):
    from litharness import cli
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.generation import Resolution

    verify_origin(book)
    if os.environ.get("LITHARNESS_ENV") != "test":
        raise RuntimeError("Offline preflight requires test mode")
    path = LOCAL / "preflight" / book / "book.db"
    path.parent.mkdir(parents=True)
    shutil.copy2(LOCAL / "initial-stores" / f"{book}.db", path)
    reached = []

    class Boundary(Exception):
        pass

    class Probe:
        def resolve(self, call_class="generation"):
            return SimpleNamespace(name="codex"), Resolution("codex")

        def complete(self, request):
            reached.append(base.serial(request))
            raise Boundary()

    cli.build_default_registry = Probe
    arguments = [*base.base_args(book), "tick"]
    arguments[arguments.index("--database") + 1] = str(path)
    args = cli.build_parser().parse_args(arguments)
    with SqliteStore.open(path) as store:
        conductor = cli._conductor(store, args)
        job = conductor.select(store, "offline-coverage", 1760000000.0, 60)
        if job is None or job.job_kind != "book_outline":
            raise RuntimeError("Preflight did not reach an opening outline")
        try:
            conductor.handlers["book_outline"](job, 1760000000.0)
        except Boundary:
            pass
        else:
            raise RuntimeError("Preflight never reached the model boundary")
    if len(reached) != 1:
        raise RuntimeError("Preflight produced an unexpected number of requests")
    base.write(LOCAL / "preflight" / f"{book}-request.json", reached[0])


def prepare():
    from litharness.application.chapter_layout import PLANNING_RULE

    base.lock()
    if LOCAL.exists():
        raise RuntimeError("Never overwrite a prepared or dispatched comparison")
    LOCAL.mkdir(parents=True)
    base.write(HERE / "inputs.json", base.INPUTS)
    files = [Path(__file__), HERE / "RUNBOOK.md", HERE / "inputs.json", SUPPORT,
             PARENT_RUNNER, ROOT / "tests/test_chapter_coverage_experiment.py",
             base.BINARY, ROOT / "uv.lock"]
    for arm, revision in REVISIONS.items():
        archive = LOCAL / f"source-{arm}.zip"
        subprocess.run(["git", "archive", "--format=zip", f"--output={archive}", revision,
                        "src", "migrations", "pyproject.toml", "uv.lock"], cwd=ROOT, check=True)
        source = LOCAL / "sources" / arm
        with zipfile.ZipFile(archive) as packed:
            packed.extractall(source)
        runtime = LOCAL / "runtimes" / arm
        venv.EnvBuilder(with_pip=False).create(runtime)
        pth = runtime / "Lib/site-packages/experiment-source.pth"
        pth.write_text(str(source / "src") + "\n" + sysconfig.get_path("purelib") + "\n",
                       encoding="utf-8")
        files += [archive, pth, runtime / "pyvenv.cfg", base.python_for(arm)]
        files += [p for p in source.rglob("*") if p.is_file()]
    for book in order("chapter1"):
        case = book[1]
        destination = base.book_root(book)
        (destination / "concept").mkdir(parents=True)
        original = PARENT / "books" / f"B{case}" / "concept/concept.json"
        shutil.copy2(original, destination / "concept/concept.json")
        files += [original, source_call(case, "seed"), source_call(case, "outline"),
                  destination / "concept/concept.json"]
        env = base.environment(book) | {"LITHARNESS_ENV": "test"}
        offline_child(book, "setup", env)
        initial = LOCAL / "initial-stores" / f"{book}.db"
        initial.parent.mkdir(exist_ok=True)
        shutil.copy2(destination / "book.db", initial)
        offline_child(book, "preflight", env)
        files += [initial, LOCAL / "setup" / f"{book}.json",
                  LOCAL / "setup" / f"{book}-origin.json",
                  LOCAL / "preflight" / f"{book}-request.json"]
    controls = {}
    for case in SOURCES:
        controls[case] = request_control(
            base.read(LOCAL / "preflight" / f"A{case}-request.json"),
            base.read(LOCAL / "preflight" / f"B{case}-request.json"),
            base.read(source_call(case, "outline"))["request"], PLANNING_RULE,
        )
    manifest = {
        "files": {str(p): base.sha(p) for p in files}, "revisions": REVISIONS,
        "limits": base.LIMITS, "order": {phase: order(phase) for phase in PHASES},
        "offline_request_controls": controls,
    }
    base.write(LOCAL / "manifest.json", manifest)
    base.write(HERE / "registration.json", manifest | {
        "manifest_sha256": base.sha(LOCAL / "manifest.json"),
    })
    claim("registered")
    print("Prepared four stores; exact original control and isolated treatment requests verified.")


def offline_child(book, mode, env):
    result = subprocess.run(
        [str(base.python_for(book[0])), str(Path(__file__)), mode, book],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    path = LOCAL / "setup" / f"{mode}-{book}-process.json"
    base.write(path, {"returncode": result.returncode, "stdout": result.stdout,
                      "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError(f"Offline {mode} failed for {book}; receipt: {path}\n{result.stderr}")


def verify_origin(book):
    import litharness_contracts

    import litharness

    if not Path(litharness.__file__).is_relative_to(LOCAL / "sources" / book[0]):
        raise RuntimeError("Offline setup imported an unfrozen source")
    base.write(LOCAL / "setup" / f"{book}-origin.json", {
        "source": litharness.__file__, "contracts": litharness_contracts.__file__,
    })


def claim(status):
    files = [("registration", HERE / name) for name in ("RUNBOOK.md", "registration.json")]
    if status == "observed":
        files.append(("derived_result", HERE / "evidence.json"))
    base.write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": "chapter-coverage-fixed-story-20260915",
        "statement": "Fixed source concepts and pre-outline worlds reach control and treatment "
                     "with only the registered chapter-planning handoff changed.",
        "status": status,
        "artifacts": [{"kind": kind, "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
                      for kind, p in files],
    })


def run():
    test = ROOT / "tests/test_chapter_coverage_experiment.py"
    data = subprocess.check_output(["git", "show", f"HEAD:{test.relative_to(ROOT).as_posix()}"],
                                   cwd=ROOT)
    if data != test.read_bytes():
        raise RuntimeError("Experiment tests are not committed")
    base.run()
    state = base.read(LOCAL / "progress.json")
    for book in state["books"].values():
        if book["status"] == "running" and book["accepted"] == 2 and book["pending"] == 0:
            book["status"] = "complete"
    base.write(LOCAL / "progress.json", state)


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "collect":
        base.collect(sys.argv[2])
    elif mode in {"setup", "preflight"}:
        {"setup": setup, "preflight": preflight}[mode](sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": base.audit}[mode]()
