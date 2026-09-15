"""Four opening chapters; remove only generic outline role labels in treatment."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import sysconfig
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/beat-labels-20260915"
PARENT = ROOT / "runs/chapter-coverage-20260915"
PREVIOUS = HERE.parent / "chapter-coverage-20260915"
REVISIONS = {"A": "89527c3", "B": "34c9418"}
PHASES = ("chapter1", "drain1")
CASES = ("2", "4")
ROLE_RULE = "Respect the dramatic function given for each scene."
ROLES = ["setup", "inciting", "rising", "turn", "crisis", "resolution"]
LIMITS = {"calls": 40, "tokens": 600000, "seconds": 3600,
          "book_calls": 10, "ticks_per_phase": 20}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


coverage = module("beat_label_support", PREVIOUS / "run.py")
base = coverage.base


def order(phase):
    step = PHASES.index(phase) if phase in PHASES else 0
    return tuple(f"{arm}{case}" for index, case in enumerate(CASES)
                 for arm in ("AB" if (index + step) % 2 == 0 else "BA"))


def command(book, phase):
    if phase not in PHASES:
        raise ValueError("Only chapter one and its queued follow-up work are registered")
    return ["tick"]


def configure():
    coverage.LOCAL, coverage.HERE, coverage.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.LOCAL, base.HERE, base.__file__ = LOCAL, HERE, str(Path(__file__).resolve())
    base.INPUTS = {key: value for key, value in base.INPUTS.items() if key in CASES}
    base.REVISIONS, base.PHASES, base.order = REVISIONS, PHASES, order
    base.LIMITS, base.OWNER = LIMITS, "beat-labels-20260915: root task;"
    base.command, base.claim = command, claim
    base.transport_details = lambda raw, payload, book: coverage.support.details(
        raw, payload, book, LOCAL,
    )


def request_control(control, treatment, original):
    if control != original:
        raise ValueError("Control differs from the preceding treatment's preflight request")
    a, b = dict(control), dict(treatment)
    ap, bp = json.loads(a.pop("prompt")), json.loads(b.pop("prompt"))
    if a.pop("profile") != "planner.outline.v5" or b.pop("profile") != "planner.outline.v6":
        raise ValueError("Unexpected profiles")
    if [s.get("dramatic_function") for s in ap["scenes"]] != ROLES:
        raise ValueError("Unexpected generic role labels")
    for scene in ap["scenes"]:
        del scene["dramatic_function"]
    if ap["rules"].count(ROLE_RULE) != 1:
        raise ValueError("The original role instruction is missing or duplicated")
    ap["rules"].remove(ROLE_RULE)
    if ap != bp or a != b:
        raise ValueError("Treatment changed something beyond role labels and their instruction")
    return True


def prepare():
    base.lock()
    if LOCAL.exists():
        raise RuntimeError("Never overwrite a prepared or dispatched experiment")
    LOCAL.mkdir(parents=True)
    base.write(HERE / "inputs.json", base.INPUTS)
    files = [Path(__file__), HERE / "RUNBOOK.md", HERE / "inputs.json",
             ROOT / "tests/test_beat_label_experiment.py", PREVIOUS / "run.py",
             PREVIOUS / "inspect_handoff.py", coverage.SUPPORT, coverage.PARENT_RUNNER,
             ROOT / "uv.lock", base.BINARY]
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
                       encoding="utf-8", newline="\n")
        files += [archive, pth, runtime / "pyvenv.cfg", base.python_for(arm)]
        files += [p for p in source.rglob("*") if p.is_file()]
    for book in order("chapter1"):
        origin = f"B{book[1]}"
        root = base.book_root(book)
        (root / "concept").mkdir(parents=True)
        original_store = PARENT / "initial-stores" / f"{origin}.db"
        original_concept = PARENT / "books" / origin / "concept/concept.json"
        initial = LOCAL / "initial-stores" / f"{book}.db"
        initial.parent.mkdir(exist_ok=True)
        for destination in (root / "book.db", initial):
            shutil.copy2(original_store, destination)
        shutil.copy2(original_concept, root / "concept/concept.json")
        env = base.environment(book) | {"LITHARNESS_ENV": "test"}
        coverage.offline_child(book, "preflight", env)
        if base.metadata(book)["accepted"] != 0:
            raise RuntimeError("Starting store contains manuscript prose")
        if base.sha(root / "book.db") != base.sha(initial):
            raise RuntimeError("Preparation changed the live starting store")
        files += [original_store, original_concept, initial, root / "concept/concept.json",
                  PARENT / "preflight" / f"{origin}-request.json",
                  LOCAL / "preflight" / f"{book}-request.json",
                  LOCAL / "setup" / f"{book}-origin.json",
                  LOCAL / "setup" / f"preflight-{book}-process.json"]
    controls = {case: request_control(
        base.read(LOCAL / "preflight" / f"A{case}-request.json"),
        base.read(LOCAL / "preflight" / f"B{case}-request.json"),
        base.read(PARENT / "preflight" / f"B{case}-request.json"),
    ) for case in CASES}
    manifest = {
        "files": {str(p): base.sha(p) for p in files}, "revisions": REVISIONS,
        "limits": LIMITS, "order": {phase: order(phase) for phase in PHASES},
        "offline_request_controls": controls, "chapters_per_book": 1,
    }
    base.write(LOCAL / "manifest.json", manifest)
    base.write(HERE / "registration.json", manifest | {
        "manifest_sha256": base.sha(LOCAL / "manifest.json"),
    })
    claim("registered")
    print("Four identical starting-store copies prepared; only label removal differs in requests.")


def finalize(state):
    for item in state["books"].values():
        if (item["status"] == "running" and item.get("accepted") == 1
                and item.get("pending") == 0 and not item.get("terminal")):
            item["status"] = "complete"
    state["status"] = (
        "complete" if not state.get("stop")
        and all(b["status"] == "complete" for b in state["books"].values()) else "partial"
    )
    return state


def run():
    for path in (ROOT / "tests/test_beat_label_experiment.py", HERE / "claim.json"):
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT,
        )
        if committed != path.read_bytes():
            raise RuntimeError("Experiment tests or claim are not committed")
    base.run()
    state = finalize(base.read(LOCAL / "progress.json"))
    base.write(LOCAL / "progress.json", state)
    print(json.dumps({"registered_status": state["status"], "chapter_target": 1}))


def claim(status):
    files = [("registration", HERE / name) for name in ("RUNBOOK.md", "registration.json")]
    if status == "observed":
        files.append(("derived_result", HERE / "evidence.json"))
        if (HERE / "handoff-evidence.json").exists():
            files.append(("control_result", HERE / "handoff-evidence.json"))
    base.write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1", "claim_id": "beat-labels-fixed-story-20260915",
        "statement": "The fixed-story comparison records opening outlines and drafts with only "
                     "generic outline role labels and their instruction removed in treatment; "
                     "no quality or popularity effect is licensed.",
        "status": status,
        "artifacts": [{"kind": kind, "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
                      for kind, p in files],
    })


def audit():
    base.audit()
    evidence = base.read(HERE / "evidence.json")
    state = base.read(LOCAL / "progress.json")
    calls = [base.read(LOCAL / c["path"]) for c in state["calls"]]
    steps = [base.read(p) for p in (LOCAL / "steps").glob("*.json")]
    evidence["single_chapter_controls"] = {
        "only_registered_phases": all(s["phase"] in PHASES for s in steps)
            and all(c["phase"] in PHASES for c in calls),
        "no_second_chapter": all(s["after"]["accepted"] <= 1 for s in steps),
        "all_requests_tool_free": all(not c["request"]["allowed_tools"] for c in calls),
    }
    base.write(HERE / "evidence.json", evidence)
    analysis = module("beat_label_handoff", PREVIOUS / "inspect_handoff.py")
    analysis.LOCAL, analysis.HERE = LOCAL, HERE
    original = analysis.outline_details
    # Both arms now have chapter coverage; the preceding helper used it only in B.
    analysis.outline_details = lambda call, book, stored, ids: original(
        call, f"B{book[1]}", stored, ids,
    )
    analysis.inspect()
    handoff = base.read(HERE / "handoff-evidence.json")
    handoff["source_hashes"][Path(__file__).relative_to(ROOT).as_posix()] = base.sha(Path(__file__))
    base.write(HERE / "handoff-evidence.json", handoff)
    claim("observed")


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "collect":
        base.collect(sys.argv[2])
    elif mode == "preflight":
        coverage.preflight(sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
