"""`litharness audit`: the whole-book views on the command line and as the MCP tool."""

from __future__ import annotations

import json

from litharness.cli import EXIT_ATTENTION, EXIT_FAULT, EXIT_OK, main


def _imported(tmp_path):  # type: ignore[no-untyped-def]
    db = tmp_path / "audit.db"
    assert main(["--database", str(db), "import", "--fixture", "litrpg"]) == EXIT_OK
    return str(db)


def test_audit_reads_the_fixture_across_its_scenes(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    db = _imported(tmp_path)
    capsys.readouterr()
    code = main(["--database", db, "audit"])
    out = capsys.readouterr().out
    assert code in (EXIT_OK, EXIT_ATTENTION)
    assert "audit:" in out and "Descriptive only" in out
    assert ("look at:" in out) == (code == EXIT_ATTENTION)


def test_audit_json_carries_every_view_and_the_attention_lines(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    db = _imported(tmp_path)
    capsys.readouterr()
    code = main(["--database", db, "audit", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code in (EXIT_OK, EXIT_ATTENTION)
    for view in ("status", "promises", "facts", "cast", "plans", "refrains", "seams", "sheet"):
        assert view in payload, view
    assert isinstance(payload["attention_lines"], list)
    assert payload["scenes_total"] >= 1 and payload["scenes_drafted"] <= payload["scenes_total"]
    assert (code == EXIT_ATTENTION) == bool(payload["attention_lines"])


def test_audit_one_view_and_an_unknown_one(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    db = _imported(tmp_path)
    capsys.readouterr()
    code = main(["--database", db, "audit", "--view", "refrains", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code in (EXIT_OK, EXIT_ATTENTION)
    assert "refrains" in payload and "promises" not in payload
    # argparse refuses a view the module does not know before the store is opened
    try:
        main(["--database", db, "audit", "--view", "scores"])
    except SystemExit as stop:
        assert stop.code == 2
    else:  # pragma: no cover - argparse always exits here
        raise AssertionError("an unknown view was accepted")
    assert EXIT_FAULT == 2
