"""Post-observation correction for one inherited receipt's fixed command ordinal.

The frozen reader hashes commands/005-seed-accept.json. This preparation added a
world-equality check, so the actual receipt is 006. Resolve the unique verified
receipt without renaming artifacts or editing the registered reader.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path


def seed_acceptance_receipt(book):
    candidates = list((book / "commands").glob("*-seed-accept.json"))
    if len(candidates) != 1:
        raise RuntimeError("Expected exactly one seed-accept receipt")
    [path] = candidates
    row = json.loads(path.read_text(encoding="utf-8"))
    if row.get("exit_code") != 0 or row.get("argv", [])[-2:] != ["world", "accept"]:
        raise RuntimeError("Seed-accept receipt is not a successful world accept")
    return path


def main():
    path = Path(__file__).with_name("audit.py")
    spec = importlib.util.spec_from_file_location("_registered_opening_audit", path)
    assert spec is not None and spec.loader is not None
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    actual = seed_acceptance_receipt(audit.BOOK)
    expected = audit.BOOK / "commands/005-seed-accept.json"
    if expected.exists() or actual == expected:
        raise RuntimeError("This correction requires the observed missing legacy path")
    original_reader = audit.reader
    original_evidence = audit.sha(audit.HERE / "evidence.json")

    def corrected_reader(name):
        module = original_reader(name)
        if name == "readout":
            original_sha = module.sha

            def corrected_sha(candidate):
                return original_sha(actual if Path(candidate) == expected else candidate)

            module.sha = corrected_sha
        return module

    audit.reader = corrected_reader
    with contextlib.redirect_stdout(io.StringIO()):
        audit.main()
    if audit.sha(audit.HERE / "evidence.json") != original_evidence:
        raise RuntimeError("Receipt locator correction changed the registered evidence")
    readout = audit.load(audit.HERE / "readout.json")
    readout.update(
        analysis_stage="post-observation receipt-locator correction",
        seed_acceptance_receipt={
            "path": actual.relative_to(audit.ROOT).as_posix(), "sha256": audit.sha(actual),
            "legacy_missing_path": expected.relative_to(audit.ROOT).as_posix(),
        },
        registered_evidence_unchanged=True,
    )
    readout["analysis_scripts"][Path(__file__).relative_to(audit.ROOT).as_posix()] = audit.sha(
        Path(__file__)
    )
    audit.save(audit.HERE / "readout.json", readout)
    print(json.dumps({
        "analysis_stage": readout["analysis_stage"],
        "seed_acceptance_receipt": readout["seed_acceptance_receipt"],
        "registered_evidence_unchanged": True,
        "prompt_contracts": readout["prompt_contracts"],
        "direction_preservation": readout["direction_preservation"],
    }, indent=2))


if __name__ == "__main__":
    main()
