"""One registered six-chapter trial of the operator-requested scene directions."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/scene-consequence-20260913"
BOOK = RUN / "book"
PREVIOUS = HERE.with_name("growth-continuation-20260913") / "run.py"
SOURCE_OVERRIDES = (
    "src/litharness/application/outline.py",
    "src/litharness/domain/house.py",
)
SPEC = importlib.util.spec_from_file_location("_scene_consequence_runner", PREVIOUS)
assert SPEC is not None and SPEC.loader is not None
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)
BASE = DRIVER.BASE
for key, value in {"HERE": HERE, "ROOT": ROOT, "RUN": RUN, "BOOK": BOOK}.items():
    setattr(DRIVER, key, value)
for key, value in {
    "HERE": HERE,
    "ROOT": ROOT,
    "RUN": RUN,
    "OWNER": "scene-consequence-20260913:",
    "REVISION": "52c2fdf",
    "MAX_CALLS": 32,
    "MAX_TOKENS": 2_200_000,
    "MAX_SECONDS": 5400,
}.items():
    setattr(BASE, key, value)
sha, load, save = BASE.sha, BASE.load, BASE.save
CHAPTERS = DRIVER.CHAPTERS
validate, live = DRIVER.validate, DRIVER.live


def prepare_inputs():
    BASE.lock()
    if "litharness" in sys.modules:
        raise RuntimeError("Apply registered source overlay before importing the package")
    overrides = {}
    for relative in SOURCE_OVERRIDES:
        source, destination = ROOT / relative, RUN / "source" / relative
        destination.write_bytes(source.read_bytes())
        overrides[relative] = sha(source)
    DRIVER.prepare_inputs()
    manifest = load(RUN / "manifest.json")
    scripts = [
        PREVIOUS,
        PREVIOUS.with_name("audit.py"),
        PREVIOUS.with_name("readout.py"),
        ROOT / "tests/test_scene_consequence_experiment.py",
        ROOT / "tests/test_scene_brief.py",
        ROOT / "tests/test_planner.py",
        *(ROOT / relative for relative in SOURCE_OVERRIDES),
    ]
    manifest["scripts"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in scripts})
    baseline = ROOT / "runs/growth-continuation-20260913"
    protected = [
        baseline / "progress.json",
        baseline / "book/serial.db",
        ROOT / "research/quality-measurement/growth-continuation-20260913/evidence.json",
        ROOT / "research/quality-measurement/growth-continuation-20260913/readout.json",
        ROOT / "research/quality-measurement/growth-continuation-20260913/REPORT.md",
    ]
    protected += sorted((baseline / "book/calls").glob("*.json"))
    protected += sorted((baseline / "book/library").glob("*/chapters/Chapter*.txt"))
    manifest["protected_inputs"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in protected})
    manifest["source_overrides"] = overrides
    save(RUN / "manifest.json", manifest)
    registration = load(HERE / "registration.json")
    registration.update(
        manifest_sha256=sha(RUN / "manifest.json"),
        source_base_revision=registration.pop("source_revision"),
        source_overrides=overrides,
        contrast="historical opening versus one fresh opening; bundled directions, no ranking",
    )
    save(HERE / "registration.json", registration)
    print("Frozen two explicit source overrides; unrelated working-tree edits are excluded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inputs", "live"))
    {"prepare": BASE.prepare, "inputs": prepare_inputs, "live": live}[parser.parse_args().mode]()
