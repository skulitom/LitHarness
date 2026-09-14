"""Extra preparation commands cannot misidentify the seed acceptance evidence."""

import json
import runpy
from pathlib import Path

import pytest

LOCATE = runpy.run_path(str(
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/opening-consequence-20260914/audit_correction.py"
))["seed_acceptance_receipt"]


@pytest.mark.parametrize("ordinal", [6, 12])
def test_seed_acceptance_is_located_after_additional_preparation_commands(tmp_path, ordinal):
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "005-seed-check.json").write_text(
        json.dumps({"argv": ["world", "check"], "exit_code": 0}), encoding="utf-8",
    )
    expected = commands / f"{ordinal:03d}-seed-accept.json"
    expected.write_text(
        json.dumps({"argv": ["--database", "fixture.db", "world", "accept"], "exit_code": 0}),
        encoding="utf-8",
    )
    assert LOCATE(tmp_path) == expected
    (commands / "099-seed-accept.json").write_bytes(expected.read_bytes())
    with pytest.raises(RuntimeError, match="exactly one"):
        LOCATE(tmp_path)


@pytest.mark.parametrize("argv,code", [(["world", "check"], 0), (["world", "accept"], 1)])
def test_seed_acceptance_locator_refuses_unrelated_or_failed_receipts(tmp_path, argv, code):
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "006-seed-accept.json").write_text(
        json.dumps({"argv": argv, "exit_code": code}), encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="successful world accept"):
        LOCATE(tmp_path)
