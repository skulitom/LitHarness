"""One explicitly registered retry after authentication, preserving the original attempt."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import promise_payoff_challenge as base

ORIGINAL = base.HERE
ORIGINAL_LOCAL = base.LOCAL
HERE = ORIGINAL / "recovery"
LOCAL = ORIGINAL_LOCAL / "recovery"
ORIGINAL_VERIFY = base.verify


def extra_sources() -> list[Path]:
    return [
        Path(__file__),
        ORIGINAL / "RECOVERY.md",
        base.ROOT / "tests/test_promise_payoff_recovery.py",
        ORIGINAL / "observations.json",
        ORIGINAL / "failure.json",
        ORIGINAL_LOCAL / "raw.jsonl",
    ]


def prepare() -> None:
    reg = ORIGINAL_VERIFY()
    if LOCAL.exists() or HERE.exists():
        raise ValueError("Recovery already prepared; preserve its artifacts")
    LOCAL.mkdir()
    HERE.mkdir()
    shutil.copyfile(ORIGINAL_LOCAL / "tasks.private.json", LOCAL / "tasks.private.json")
    reg["recovery"] = {
        "original_registration_sha256": base.file_hash(ORIGINAL / "registration.json"),
        "prior_failed_attempts": 1,
        "combined_dispatch_ceiling": 28,
        "extra_hashes": {
            p.relative_to(base.ROOT).as_posix(): base.file_hash(p) for p in extra_sources()
        },
        "tasks_sha256": base.file_hash(LOCAL / "tasks.private.json"),
    }
    base.write_json(HERE / "registration.json", reg)


def verify() -> dict:
    base.HERE = ORIGINAL
    try:
        ORIGINAL_VERIFY()
    finally:
        base.HERE = HERE
    reg_path = HERE / "registration.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    recovery = reg["recovery"]
    if recovery["original_registration_sha256"] != base.file_hash(ORIGINAL / "registration.json"):
        raise ValueError("Changed original registration")
    if base.file_hash(LOCAL / "tasks.private.json") != recovery["tasks_sha256"]:
        raise ValueError("Changed recovery tasks")
    if (LOCAL / "tasks.private.json").read_bytes() != (
        ORIGINAL_LOCAL / "tasks.private.json"
    ).read_bytes():
        raise ValueError("Recovery questions differ")
    for name, expected in recovery["extra_hashes"].items():
        if base.file_hash(base.ROOT / name) != expected:
            raise ValueError("Changed recovery artifact")
    for path in [reg_path, *[p for p in extra_sources() if not p.is_relative_to(ORIGINAL_LOCAL)]]:
        committed = subprocess.check_output(
            ["git", "show", "HEAD:" + path.relative_to(base.ROOT).as_posix()],
            cwd=base.ROOT,
        )
        if committed != path.read_bytes():
            raise ValueError("Recovery not committed")
    return reg


def execute(mode: str) -> None:
    verify()
    base.LOCAL, base.HERE, base.verify = LOCAL, HERE, verify
    if mode == "run":
        base.run()
    else:
        base.analyse()
        claim_path = HERE / "claim.json"
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim["claim_id"] += ".recovery1"
        base.write_json(claim_path, claim)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "analyse"))
    mode = parser.parse_args().mode
    prepare() if mode == "prepare" else execute(mode)
