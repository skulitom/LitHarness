"""One cross-platform entry point for LitHarness development checks."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO: Final = Path(__file__).resolve().parents[1]
SMOKE_TESTS: Final = (
    "tests/test_architecture.py",
    "tests/test_domain.py",
    "tests/test_context.py",
    "tests/test_state.py",
    "tests/test_serials.py",
)

_SOURCE_TESTS: Final = {
    "src/litharness/cli.py": (
        "tests/test_cli.py",
        "tests/test_import.py",
        "tests/test_listing_loop.py",
        "tests/test_world_slots.py",
    ),
    "src/litharness/adapters/contracts_fixtures.py": (
        "tests/test_import.py",
        "tests/test_continuity_evaluator.py",
    ),
    "src/litharness/adapters/sqlite_audience.py": (
        "tests/test_listing_loop.py",
        "tests/test_feed_session.py",
    ),
    "src/litharness/adapters/sqlite_jobs.py": (
        "tests/test_conductor.py",
        "tests/test_store.py",
    ),
    "src/litharness/adapters/sqlite_plans.py": (
        "tests/test_planner.py",
        "tests/test_store.py",
    ),
    "src/litharness/adapters/sqlite_store.py": ("tests/test_store.py",),
    "src/litharness/application/ports.py": ("tests/test_architecture.py",),
    # `_matching_test` would look for `tests/test_world.py`, which does not exist, and send
    # every touch of the Architect's view layer to a full run. The slot suite is the one that
    # grades it: it reads `vocabulary` line by line against the readers in `domain/worlds.py`.
    "src/litharness/application/world.py": ("tests/test_world_slots.py",),
    # The four modules split out of `domain/extraction.py` (stage-0 §215) have no test file
    # of their own name: the tests that read them are the ones that read `extraction`, by the
    # subject each module holds, and `_matching_test` would otherwise send every touch of a
    # sheet reader to the quick lane.
    "src/litharness/domain/names.py": (
        "tests/test_display_names.py",
        "tests/test_extraction.py",
    ),
    "src/litharness/domain/sheet.py": (
        "tests/test_display_names.py",
        "tests/test_extraction.py",
        "tests/test_order_key_spaces.py",
        "tests/test_page_contract.py",
    ),
    "src/litharness/domain/graphline.py": (
        "tests/test_extraction.py",
        "tests/test_worlds.py",
    ),
    "src/litharness/domain/moves.py": (
        "tests/test_choice_points.py",
        "tests/test_progression_gate.py",
        "tests/test_progression_prompt.py",
        "tests/test_two_systems.py",
    ),
    # The two modules split out of `domain/gamesystem.py` (stage-0 §216), by the same rule.
    "src/litharness/domain/systems.py": (
        "tests/test_gamesystem.py",
        "tests/test_seed_completion_bounds.py",
        "tests/test_two_systems.py",
    ),
    "src/litharness/domain/advancement.py": (
        "tests/test_choice_points.py",
        "tests/test_gamesystem.py",
        "tests/test_progression_prompt.py",
    ),
    "tools/check.py": ("tests/test_check_tool.py",),
}

_QUICK_PATHS: Final = {
    "pyproject.toml",
    "uv.lock",
    "tests/conftest.py",
}


@dataclass(frozen=True, slots=True)
class ChangedSelection:
    tests: tuple[str, ...]
    include_intensive: bool = False
    use_quick: bool = False
    use_full: bool = False
    reason: str = ""


def _normalise(path: str) -> str:
    return path.strip().replace("\\", "/").removeprefix("./")


def _matching_test(path: str) -> str | None:
    stem = Path(path).stem.replace("-", "_")
    candidate = f"tests/test_{stem}.py"
    return candidate if (REPO / candidate).is_file() else None


def select_changed(paths: list[str]) -> ChangedSelection:
    """Choose a conservative local test slice for a set of changed repository paths."""
    changed = sorted({_normalise(path) for path in paths if _normalise(path)})
    if not changed:
        return ChangedSelection(SMOKE_TESTS, reason="no changed paths; running smoke")
    if len(changed) > 20:
        return ChangedSelection((), use_full=True, reason="more than 20 paths changed")

    selected = set(SMOKE_TESTS)
    include_intensive = False
    unknown_code: list[str] = []
    quick_reason = ""
    for path in changed:
        if path in _QUICK_PATHS or path.startswith(".github/workflows/"):
            quick_reason = quick_reason or f"repository config changed: {path}"
            continue

        if path.startswith("migrations/"):
            selected.update(("tests/test_store.py", "tests/test_import.py"))
            continue

        if path.startswith("tests/") and path.endswith(".py"):
            selected.add(path)
            continue

        if path in _SOURCE_TESTS:
            selected.update(_SOURCE_TESTS[path])
            continue

        if path.startswith("src/") and path.endswith(".py"):
            if match := _matching_test(path):
                selected.add(match)
            else:
                unknown_code.append(path)
            continue

        if path.startswith("research/") and path.endswith(".py"):
            if match := _matching_test(path):
                selected.add(match)
            else:
                unknown_code.append(path)
            continue

        if path.startswith("tools/") and path.endswith(".py"):
            if match := _matching_test(path):
                selected.add(match)
            else:
                unknown_code.append(path)
            continue

        if path.endswith(".md"):
            # The intensive architecture check resolves every symbol and test name cited by
            # prose, so documentation changes need that one repository-wide scan.
            include_intensive = True
            selected.add("tests/test_architecture.py")
            continue

        if match := _matching_test(path):
            selected.add(match)

    if unknown_code:
        quick_reason = "no safe test mapping for " + ", ".join(unknown_code)
    if quick_reason:
        # A quick fallback is sufficient for unknown code or config, unless prose also changed:
        # only the full lane includes the repository-wide symbol resolver needed by docs.
        return ChangedSelection(
            (),
            use_quick=not include_intensive,
            use_full=include_intensive,
            reason=quick_reason,
        )
    return ChangedSelection(
        tuple(sorted(selected)),
        include_intensive=include_intensive,
        reason=f"selected from {len(changed)} changed path(s)",
    )


def changed_paths() -> list[str]:
    tracked = subprocess.run(
        ["git", "diff", "HEAD", "--name-only"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return sorted(set(tracked + untracked))


def _run(command: list[str]) -> None:
    print(f"\n> {shlex.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=REPO, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def _pytest(*args: str) -> list[str]:
    return ["uv", "run", "pytest", *args]


def run_mode(mode: str) -> None:
    if mode == "smoke":
        _run(_pytest(*SMOKE_TESTS, "-m", "not intensive", "-n", "0"))
        return
    if mode == "changed":
        paths = changed_paths()
        selection = select_changed(paths)
        print(f"changed: {selection.reason}")
        if selection.use_full:
            run_mode("full")
            return
        if selection.use_quick:
            run_mode("quick")
            return
        command = _pytest(*selection.tests, "-n", "0")
        if not selection.include_intensive:
            command.extend(("-m", "not intensive"))
        _run(command)
        return
    if mode == "quick":
        _run(_pytest("-m", "not intensive", "-n", "auto", "--dist", "loadscope"))
        return
    if mode == "full":
        _run(_pytest("-n", "auto", "--dist", "loadscope"))
        return
    if mode == "handoff":
        commands = (
            ["uv", "run", "ruff", "check", "."],
            ["uv", "run", "mypy"],
            ["git", "diff", "HEAD", "--check"],
            ["uv", "lock", "--check"],
            _pytest("-n", "auto", "--dist", "loadscope", "--cov=litharness"),
            ["uv", "build", "--wheel"],
            [
                "uv",
                "run",
                "python",
                "research/quality-measurement/corpus_leak_audit.py",
            ],
        )
        for command in commands:
            _run(command)
        return
    raise AssertionError(f"unhandled check mode: {mode}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("smoke", "changed", "quick", "full", "handoff"))
    args = parser.parse_args(argv)
    run_mode(args.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
