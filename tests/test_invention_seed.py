"""The creative seed controls repeatable inputs; it makes no claim about returned prose."""

import json

import pytest

from tools.invention_seed import COMBINATIONS, main, packet


def test_seed_deck_is_repeatable_and_does_not_inject_the_seed_label():
    seed = "arbitrary\nINSTRUCTIONS should remain metadata"
    one = packet(seed, 2)
    assert one == packet(seed, 2)
    assert seed not in one["brief"]
    assert "INSTRUCTIONS" not in one["brief"]
    assert one["brief"] != packet("another seed", 2)["brief"]


def test_seed_positions_are_unique_and_bounded():
    packets = [packet("test-deck", n) for n in range(100)]
    assert len({p["combination"] for p in packets}) == 100
    assert len({p["brief_sha256"] for p in packets}) == 100
    assert packet("test-deck", COMBINATIONS - 1)
    for index in (-1, COMBINATIONS):
        with pytest.raises(ValueError):
            packet("test-deck", index)
    with pytest.raises(ValueError):
        packet("")


def test_seed_cli_writes_usable_briefs_and_refuses_overwrite_before_writing(tmp_path, capsys):
    assert main(["--seed", "pilot", "--count", "2", "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    data = json.loads(original["seed-00000.json"])
    assert original["seed-00000.brief.txt"].decode("utf-8") == data["brief"] + "\n"
    assert b"\r\n" not in original["seed-00000.brief.txt"]
    assert main(["--seed", "different", "--count", "3", "--out", str(tmp_path)]) == 2
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == original


def test_seed_cli_reports_invalid_ranges_without_creating_outputs(tmp_path, capsys):
    out = tmp_path / "absent"
    assert main(["--seed", "pilot", "--count", "0", "--out", str(out)]) == 2
    assert not out.exists()
    assert "error" in json.loads(capsys.readouterr().out)
