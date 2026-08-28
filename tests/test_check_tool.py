from __future__ import annotations

from tools import check


def test_a_domain_change_gets_smoke_and_its_focused_test() -> None:
    selection = check.select_changed(["src/litharness/domain/context.py"])

    assert not selection.use_quick
    assert not selection.include_intensive
    assert set(check.SMOKE_TESTS) <= set(selection.tests)
    assert "tests/test_context.py" in selection.tests


def test_documentation_runs_the_symbol_resolver() -> None:
    selection = check.select_changed(["README.md"])

    assert not selection.use_quick
    assert selection.include_intensive
    assert "tests/test_architecture.py" in selection.tests


def test_repository_configuration_falls_back_to_the_quick_lane() -> None:
    selection = check.select_changed(["pyproject.toml"])

    assert selection.use_quick
    assert "config" in selection.reason


def test_documentation_mixed_with_a_fallback_escalates_to_full() -> None:
    selection = check.select_changed(["README.md", "pyproject.toml"])

    assert selection.use_full
    assert not selection.use_quick


def test_an_unmapped_source_module_falls_back_instead_of_underselecting() -> None:
    selection = check.select_changed(["src/litharness/application/not_yet_tested.py"])

    assert selection.use_quick
    assert "no safe test mapping" in selection.reason


def test_a_changed_test_always_selects_itself() -> None:
    selection = check.select_changed(["tests/test_covers.py"])

    assert not selection.use_quick
    assert "tests/test_covers.py" in selection.tests
