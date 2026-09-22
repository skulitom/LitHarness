"""The second registered retry: identical questions and limits on the re-authenticated CLI."""

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
FIRST = ORIGINAL / "recovery"
FIRST_LOCAL = ORIGINAL_LOCAL / "recovery"
HERE = ORIGINAL / "recovery2"
LOCAL = ORIGINAL_LOCAL / "recovery2"


def extra_sources() -> list[Path]:
    return [
        Path(__file__),
        ORIGINAL / "RECOVERY2.md",
        base.ROOT / "tests/test_promise_payoff_recovery2.py",
        ORIGINAL / "recover.py",
        ORIGINAL / "observations.json",
        ORIGINAL / "failure.json",
        FIRST / "registration.json",
        FIRST / "observations.json",
        FIRST / "failure.json",
        ORIGINAL_LOCAL / "raw.jsonl",
        FIRST_LOCAL / "raw.jsonl",
    ]


def verify_original() -> dict:
    """The original registration's checks, except the executable, which re-pins below."""
    reg_path = ORIGINAL / "registration.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    for field in ("source_hashes", "input_hashes"):
        for name, expected in reg[field].items():
            if base.file_hash(base.ROOT / name) != expected:
                raise ValueError(f"Changed frozen file: {name}")
    for path in [reg_path, *base.sources()]:
        committed = subprocess.check_output(
            ["git", "show", "HEAD:" + path.relative_to(base.ROOT).as_posix()],
            cwd=base.ROOT,
        )
        if committed != path.read_bytes():
            raise ValueError("Registration/source not committed")
    return reg


def prepare() -> None:
    reg = verify_original()
    if LOCAL.exists() or HERE.exists():
        raise ValueError("Recovery already prepared; preserve its artifacts")
    LOCAL.mkdir()
    HERE.mkdir()
    shutil.copyfile(ORIGINAL_LOCAL / "tasks.private.json", LOCAL / "tasks.private.json")
    reg["recovery2"] = {
        "original_registration_sha256": base.file_hash(ORIGINAL / "registration.json"),
        "recovery1_registration_sha256": base.file_hash(FIRST / "registration.json"),
        "prior_failed_attempts": 2,
        "combined_dispatch_ceiling": 29,
        "previous_binary_sha256": reg["binary_sha256"],
        "previous_binary_version": reg["binary_version"],
        "extra_hashes": {
            p.relative_to(base.ROOT).as_posix(): base.file_hash(p) for p in extra_sources()
        },
        "tasks_sha256": base.file_hash(LOCAL / "tasks.private.json"),
    }
    reg["binary_sha256"] = base.file_hash(base.BINARY)
    reg["binary_version"] = subprocess.check_output(
        [str(base.BINARY), "--version"], text=True
    ).strip()
    base.write_json(HERE / "registration.json", reg)


def verify() -> dict:
    verify_original()
    reg_path = HERE / "registration.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    recovery = reg["recovery2"]
    if recovery["original_registration_sha256"] != base.file_hash(ORIGINAL / "registration.json"):
        raise ValueError("Changed original registration")
    if recovery["recovery1_registration_sha256"] != base.file_hash(FIRST / "registration.json"):
        raise ValueError("Changed first recovery registration")
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
    if base.file_hash(base.BINARY) != reg["binary_sha256"]:
        raise ValueError("CLI changed")
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
        claim["claim_id"] += ".recovery2"
        base.write_json(claim_path, claim)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "analyse"))
    mode = parser.parse_args().mode
    prepare() if mode == "prepare" else execute(mode)
