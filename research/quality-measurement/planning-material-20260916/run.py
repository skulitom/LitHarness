"""Isolated material prototype, shared fresh concepts, and bounded chapter continuations."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/planning-material-20260916"
PREVIOUS = HERE.parent / "chapter-coverage-20260915"
LEGACY = ROOT / "runs/beat-labels-20260915"
REVISION = "80d37ba"
TEST = ROOT / "tests/test_planning_material_experiment.py"
OWNER = "planning-material-20260916: root task;"
LIMITS = {"calls": 120, "tokens": 2000000, "seconds": 7200, "book_calls": 30, "ticks_per_phase": 20}
SOURCE_PHASES = ("concept", "new", "seed", "accept-seed")
PHASES = ("material", "chapter1", "drain1", "grow1", "accept-grow1", "chapter2", "drain2")
FRESH = ("1", "3")
CASES = ("1", "2", "3", "4")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


coverage = module("material_coverage_support", PREVIOUS / "run.py")
base = coverage.base
material = module("planning_material_prototype", HERE / "material.py")
original_command = base.command


def order(phase):
    if phase in SOURCE_PHASES:
        return tuple(f"A{case}" for case in FRESH)
    if phase == "material":
        return tuple(f"B{case}" for case in CASES)
    step = PHASES.index(phase) if phase in PHASES else 0
    cases = FRESH if phase in PHASES[3:] else CASES
    return tuple(
        f"{arm}{case}"
        for i, case in enumerate(cases)
        for arm in ("AB" if (i + step) % 2 == 0 else "BA")
    )


def all_books(phase=None):
    return tuple(f"{arm}{case}" for case in CASES for arm in "AB")


def command(book, phase):
    if phase == "material":
        return ["research-material"]
    if phase == "grow1":
        return ["architect", "grow", "--scene", "scene-1"]
    if phase not in SOURCE_PHASES + PHASES:
        raise ValueError("Unregistered phase")
    return original_command(book, phase)


def configure():
    base.LOCAL, base.HERE, base.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    coverage.LOCAL, coverage.HERE, coverage.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.INPUTS = base.read(HERE / "inputs.json")
    base.REVISIONS = {"A": REVISION, "B": REVISION}
    base.LIMITS, base.OWNER = LIMITS, OWNER
    base.PHASES, base.order, base.command, base.claim = (
        SOURCE_PHASES + PHASES,
        all_books,
        command,
        claim,
    )
    base.transport_details = lambda raw, payload, book: coverage.support.details(
        raw, payload, book, LOCAL
    )


def claim(status):
    paths = [("registration", HERE / name) for name in ("RUNBOOK.md", "registration.json")]
    if status == "observed":
        paths.append(("derived_result", HERE / "evidence.json"))
        if (HERE / "handoff-evidence.json").exists():
            paths.append(("control_result", HERE / "handoff-evidence.json"))
    base.write(
        HERE / "claim.json",
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": "planning-material-20260916",
            "statement": "The registered authoring comparison records source transformation, "
            "outline handoff and reached chapters with generated developments and "
            "tentative placement separated. It licenses no quality effect.",
            "status": status,
            "artifacts": [
                {"kind": kind, "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
                for kind, p in paths
            ],
        },
    )


def prepare():
    base.prepare()
    files = [
        Path(__file__),
        HERE / "material.py",
        HERE / "inspect_handoff.py",
        TEST,
        PREVIOUS / "run.py",
        coverage.SUPPORT,
        coverage.PARENT_RUNNER,
    ]
    for book in all_books():
        if book[1] in FRESH:
            continue
        origin = f"B{book[1]}"
        root = base.book_root(book)
        source = LEGACY / "initial-stores" / f"{origin}.db"
        concept = LEGACY / "books" / origin / "concept/concept.json"
        (root / "concept").mkdir()
        initial = LOCAL / "initial-stores" / f"{book}.db"
        initial.parent.mkdir(exist_ok=True)
        for target in (root / "book.db", initial):
            shutil.copy2(source, target)
        shutil.copy2(concept, root / "concept/concept.json")
        files += [source, concept, initial, root / "concept/concept.json"]
    manifest = base.read(LOCAL / "manifest.json")
    manifest["files"].update({str(p): base.sha(p) for p in files})
    manifest.update(
        order={phase: order(phase) for phase in SOURCE_PHASES + PHASES},
        chapters_per_case={case: 2 if case in FRESH else 1 for case in CASES},
        prototype=material.VERSION,
        frozen_input_note="Fresh paired sources are sealed automatically after seeding.",
    )
    base.write(LOCAL / "manifest.json", manifest)
    base.write(
        HERE / "registration.json",
        manifest | {"manifest_sha256": base.sha(LOCAL / "manifest.json")},
    )
    claim("registered")


def verify_pairs():
    path = LOCAL / "paired-sources.json"
    if path.exists():
        for name, expected in base.read(path)["files"].items():
            if base.sha(name) != expected:
                raise RuntimeError(f"Paired source changed: {name}")


def seal_pairs():
    files, pairs = [], []
    state = base.read(LOCAL / "progress.json")
    for case in CASES:
        a, b = f"A{case}", f"B{case}"
        if state["books"][a]["status"] != "running":
            state["books"][b].update(status="stopped", reason="shared source did not finish")
            continue
        if case in FRESH:
            source = base.book_root(a)
            target = base.book_root(b)
            shutil.copy2(source / "book.db", target / "book.db")
            shutil.copytree(source / "concept", target / "concept")
            for book in (a, b):
                initial = LOCAL / "initial-stores" / f"{book}.db"
                initial.parent.mkdir(exist_ok=True)
                shutil.copy2(base.book_root(book) / "book.db", initial)
        for book in (a, b):
            if base.metadata(book)["accepted"] != 0:
                raise RuntimeError("Shared source already has manuscript")
            coverage.offline_child(
                book, "preflight", base.environment(book) | {"LITHARNESS_ENV": "test"}
            )
            files += [
                LOCAL / "initial-stores" / f"{book}.db",
                base.book_root(book) / "concept/concept.json",
                LOCAL / "preflight" / f"{book}-request.json",
            ]
        initial_equal = base.sha(LOCAL / "initial-stores" / f"{a}.db") == base.sha(
            LOCAL / "initial-stores" / f"{b}.db"
        )
        requests_equal = base.read(LOCAL / "preflight" / f"{a}-request.json") == base.read(
            LOCAL / "preflight" / f"{b}-request.json"
        )
        if not initial_equal or not requests_equal:
            raise RuntimeError("Paired initial state or outline request differs")
        pairs.append(
            {
                "case": case,
                "initial_bytes_equal": initial_equal,
                "original_requests_equal": requests_equal,
                "fresh": case in FRESH,
            }
        )
    base.write(LOCAL / "progress.json", state)
    base.write(
        LOCAL / "paired-sources.json",
        {"pairs": pairs, "sealed_at": base.now(), "files": {str(p): base.sha(p) for p in files}},
    )


def install_transform(book):
    from litharness.application import concept, outline

    original = outline.render_outline_request

    def rendered(*args, **kwargs):
        verify_pairs()
        request = original(*args, **kwargs)
        if request.profile != "planner.outline.v6":
            raise ValueError("Unexpected outline profile")
        expected = base.read(LOCAL / "preflight" / f"{book}-request.json")
        if base.serial(request) != expected:
            raise ValueError("Live outline differs from the sealed original request")
        if book[0] == "B":
            artifact = load_material(book[1])
            return replace(
                request,
                profile=material.PROFILE,
                prompt=material.transform_prompt(
                    request.prompt,
                    artifact,
                    concept.FIRST_ARC_RULE,
                ),
            )
        return request

    outline.render_outline_request = rendered


def load_material(case):
    artifact = base.read(LOCAL / "materials" / f"{case}.json")
    state = base.read(LOCAL / "progress.json")
    calls = [
        base.read(LOCAL / c["path"])
        for c in state["calls"]
        if c["book"] == f"B{case}" and c["profile"] == "research.planning-material.v1"
    ]
    concept = json.loads(base.read(LOCAL / "preflight" / f"B{case}-request.json")["prompt"])[
        "book_concept"
    ]
    if len(calls) != 1 or calls[0]["status"] != "completed":
        raise ValueError("Material requires exactly one completed source transformation")
    expected = {
        "source_concept_sha256": material.digest(concept),
        "source_units": material.source_units(concept),
        "material": json.loads(calls[0]["result"]["text"]),
    }
    if artifact != expected:
        raise ValueError("Material differs from its first recorded output")
    return artifact


def material_step(book, iteration):
    import litharness
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import CodexCliProvider

    base.lock()
    base.verify_frozen()
    verify_pairs()
    if not Path(litharness.__file__).is_relative_to(LOCAL / "sources" / book[0]):
        raise RuntimeError("Material call imported an unfrozen source")
    key = f"material-{book}-{iteration}"
    if base.read(LOCAL / "progress.json").get("active") != key:
        raise RuntimeError("Unadmitted material call")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Material generation is disabled in tests")
    base.install_recorder(book, "material")
    request = base.read(LOCAL / "preflight" / f"{book}-request.json")
    concept = json.loads(request["prompt"])["book_concept"]
    record = {
        "key": key,
        "book": book,
        "phase": "material",
        "started_at": base.now(),
        "source": str(litharness.__file__),
        "arguments": base.base_args(book) + command(book, "material"),
        "before": base.metadata(book),
        "stdout": "",
        "stderr": "",
    }
    try:
        provider = CodexCliProvider(
            binary=str(base.BINARY), trace_directory=base.book_root(book) / "transport"
        )
        result = provider.complete(
            CompletionRequest(
                prompt=json.dumps(
                    material.generation_payload(concept),
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                ),
                system=material.TASK,
                schema=material.SCHEMA,
                profile="research.planning-material.v1",
                max_output_tokens=8192,
                timeout_seconds=900,
            )
        )
        value = json.loads(result.text)
        material.validate(value, concept)
        base.write(
            LOCAL / "materials" / f"{book[1]}.json",
            {
                "source_concept_sha256": material.digest(concept),
                "source_units": material.source_units(concept),
                "material": value,
            },
        )
        record["returncode"] = 0
    except Exception as error:
        record.update(returncode=2, exception=repr(error))
    record.update(after=base.metadata(book), finished_at=base.now())
    base.write(LOCAL / "steps" / f"{key}.json", record)


def execute(book, phase):
    for iteration in range(1, LIMITS["ticks_per_phase"] + 1):
        state = base.read(LOCAL / "progress.json")
        if state.get("stop") or state["books"][book]["status"] != "running":
            return
        if phase.startswith("drain") and base.metadata(book)["pending"] == 0:
            return
        state["active"] = f"{phase}-{book}-{iteration}"
        base.write(LOCAL / "progress.json", state)
        subprocess.run(
            [
                str(base.python_for(book[0])),
                str(Path(__file__)),
                "step",
                book,
                phase,
                str(iteration),
            ],
            cwd=ROOT,
            env=base.environment(book),
            check=True,
        )
        row = base.read(LOCAL / "steps" / f"{phase}-{book}-{iteration}.json")
        state = base.read(LOCAL / "progress.json")
        meta = row["after"]
        state["books"][book].update(phase=phase, **meta)
        failed = (
            meta["terminal"] > 0
            or row["returncode"] == 2
            or (row["returncode"] != 0 and not phase.startswith(("chapter", "drain")))
            or "no_work tick=" in row["stdout"]
        )
        done = base.phase_done(phase, meta)
        if failed or (iteration == LIMITS["ticks_per_phase"] and not done):
            state["books"][book].update(status="stopped", reason=f"workflow stopped in {phase}")
        base.write(LOCAL / "progress.json", state)
        print(
            json.dumps(
                {
                    "book": book,
                    "phase": phase,
                    "accepted": meta["accepted"],
                    "status": state["books"][book]["status"],
                    "calls": len(state["calls"]),
                    "tokens": sum(c["tokens"] for c in state["calls"]),
                }
            ),
            flush=True,
        )
        if failed or done or state.get("stop"):
            return


def run():
    base.lock()
    base.verify_frozen()
    if os.environ.get("LITHARNESS_ENV") == "test" or (LOCAL / "progress.json").exists():
        raise RuntimeError("No test-mode, duplicate or implicit-resume dispatch")
    for path in (
        Path(__file__),
        HERE / "material.py",
        TEST,
        HERE / "RUNBOOK.md",
        HERE / "inputs.json",
        HERE / "registration.json",
        HERE / "claim.json",
    ):
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        if committed != path.read_bytes():
            raise RuntimeError(f"Uncommitted registration input: {path}")
    base.write(
        LOCAL / "progress.json",
        {
            "status": "running",
            "started_at": base.now(),
            "calls": [],
            "books": {book: {"status": "running", "accepted": 0} for book in all_books()},
        },
    )
    try:
        for phase in SOURCE_PHASES:
            for book in order(phase):
                execute(book, phase)
        if not base.read(LOCAL / "progress.json").get("stop"):
            seal_pairs()
            for phase in PHASES:
                for book in order(phase):
                    execute(book, phase)
    except Exception as error:
        state = base.read(LOCAL / "progress.json")
        state["stop"] = f"scheduler failure: {error!r}"
        base.write(LOCAL / "progress.json", state)
        raise
    finally:
        state = base.read(LOCAL / "progress.json")
        state.pop("active", None)
        for book, item in state["books"].items():
            if (
                item["status"] == "running"
                and item.get("accepted") == (2 if book[1] in FRESH else 1)
                and item.get("pending") == 0
                and not item.get("terminal")
            ):
                item["status"] = "complete"
        state.update(
            status="complete"
            if not state.get("stop")
            and all(item["status"] == "complete" for item in state["books"].values())
            else "partial",
            finished_at=base.now(),
        )
        base.write(LOCAL / "progress.json", state)


def audit():
    from litharness.application.concept import FIRST_ARC_RULE

    verify_pairs()
    base.audit()
    state = base.read(LOCAL / "progress.json")
    evidence = base.read(HERE / "evidence.json")
    rows = []
    for book in all_books():
        path = LOCAL / "preflight" / f"{book}-request.json"
        if not path.exists():
            rows.append({"book": book, "paired_source_available": False})
            continue
        source = base.read(path)
        expected = source
        artifact_path = LOCAL / "materials" / f"{book[1]}.json"
        if book[0] == "B" and artifact_path.exists():
            expected = {
                **source,
                "profile": material.PROFILE,
                "prompt": material.transform_prompt(
                    source["prompt"], load_material(book[1]), FIRST_ARC_RULE
                ),
            }
        calls = [
            base.read(LOCAL / c["path"])
            for c in state["calls"]
            if c["book"] == book and c["profile"].startswith("planner.outline.")
        ]
        rows.append(
            {
                "book": book,
                "paired_source_available": True,
                "outline_calls": len(calls),
                "all_actual_outline_requests_equal_expected": bool(calls)
                and all(c["request"] == expected for c in calls),
                "material_sha256": base.sha(artifact_path) if artifact_path.exists() else None,
            }
        )
    evidence["material_controls"] = rows
    paired = LOCAL / "paired-sources.json"
    evidence["paired_sources"] = base.read(paired) if paired.exists() else None
    base.write(HERE / "evidence.json", evidence)
    module("planning_material_handoff", HERE / "inspect_handoff.py").inspect()
    claim("observed")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "step":
        book, phase, iteration = sys.argv[2], sys.argv[3], int(sys.argv[4])
        if phase == "material":
            material_step(book, iteration)
        else:
            verify_pairs()
            if phase in PHASES:
                install_transform(book)
            base.step(book, phase, iteration)
    elif mode == "preflight":
        coverage.preflight(sys.argv[2])
    elif mode == "collect":
        base.collect(sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
