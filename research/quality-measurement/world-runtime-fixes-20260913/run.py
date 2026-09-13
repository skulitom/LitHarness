"""Repeat the fixed boundary cases using a frozen copy of their audited capture driver."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/world-runtime-fixes-20260913"
PREVIOUS = ROOT / "research/quality-measurement/world-boundary-fixes-20260913"
CONTROL = ROOT / "runs/world-boundary-fixes-20260913/control-treatment.json"
PARENT = ROOT / "runs/invention-boundaries-20260912/calls/plan-astra-opus-1.json"
PARENT_SHA = "da04af43a6cbcea990c855f5c0b57831304f6b9dbe5951a775330374a66452b8"


def driver(path: Path):
    spec = importlib.util.spec_from_file_location("world_runtime_capture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.HERE, module.ROOT, module.RUN = HERE, ROOT, RUN
    module.PARENT, module.PARENT_SHA, module.CONTROL = PARENT, PARENT_SHA, CONTROL
    # One task still owns the machine throughout both registered runs.
    module.OWNER = "world-boundary-fixes-20260913: root task;"
    return module


_frozen_driver = RUN / "source/capture-run.py"
_utilities = driver(_frozen_driver if _frozen_driver.exists() else PREVIOUS / "run.py")
sha, load, save = _utilities.sha, _utilities.load, _utilities.save
hashes, failed_usage = _utilities.hashes, _utilities.failed_usage


def prepare():
    _utilities.prepare()
    # Freeze the reused capture code beside the production snapshot. Every native call
    # verifies that whole directory, so concurrent helper edits cannot change this arm.
    for name in ("run.py", "audit.py"):
        shutil.copyfile(PREVIOUS / name, RUN / "source" / f"capture-{name}")
    manifest = load(RUN / "manifest.json")
    manifest["source_sha256"] = hashes(RUN / "source")
    manifest["capture_helpers"] = {
        name: sha(PREVIOUS / name) for name in ("run.py", "audit.py")
    }
    prior = ROOT / "runs/world-boundary-fixes-20260913"
    for path in [*prior.glob("book-*/serial.db"), *prior.glob("book-*/library/*/chapters/*.txt")]:
        manifest["protected_files"][path.relative_to(ROOT).as_posix()] = sha(path)
    save(RUN / "manifest.json", manifest)
    registration = load(HERE / "registration.json")
    registration["manifest_sha256"] = sha(RUN / "manifest.json")
    registration["capture_helpers"] = manifest["capture_helpers"]
    save(HERE / "registration.json", registration)


def run():
    driver(RUN / "source/capture-run.py").run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    options = parser.parse_args()
    (prepare if options.mode == "prepare" else run)()
