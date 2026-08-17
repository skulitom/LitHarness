"""The operator report, and the one null it used to keep silently.

`litharness status` is where §19's "parked units and exceptions are visible and bounded" is
answered. This file covers the line added after §56.5 measured what an unreported null costs:
the six-rule LitRPG pack reaches the loop only through `--continuity-evaluator-command`,
which defaults to unset, so every Book Zero on record drafted with the genre's best
deterministic quality claim switched off and nothing anywhere said so.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import (
    fixture_manuscript,
    fixture_plans,
    fixture_state,
)
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import status as status_module
from litharness.domain.plans import import_plan
from litharness.domain.revision import import_manuscript
from litharness.domain.state import import_state

NOW = 1_760_000_000.0


@pytest.fixture()
def store(tmp_path) -> SqliteStore:  # type: ignore[no-untyped-def]
    opened = SqliteStore.open(tmp_path / "status.db")
    try:
        yield opened
    finally:
        opened.close()


def _book(store: SqliteStore, name: str) -> tuple[str, str]:
    """Import a golden book with its plan and state, exactly as `cli import` does."""
    manuscript = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript(name).read_text(encoding="utf-8")),
    )
    revision = import_manuscript(manuscript).revision
    store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")

    plan = import_plan(
        lc.parse_artifact(
            lc.PlanSnapshot, json.loads(fixture_plans(name).read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_plan_items(
        revision.book_id, revision.branch_id, plan.items, created_at="2026-08-13T00:00:00Z"
    )

    state = import_state(
        lc.parse_artifact(
            lc.StateSnapshot, json.loads(fixture_state(name).read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_state_records(
        revision.book_id, revision.branch_id, state.records, created_at="2026-08-13T00:00:00Z"
    )
    return revision.book_id, revision.branch_id


def test_a_litrpg_book_with_no_evaluator_wired_says_the_rules_pack_is_off(
    store: SqliteStore,
) -> None:
    """§30's decision applied to a second null, and §56.5 is why it was needed.

    `stats.ceiling.v0` and its five siblings are built and green in a sibling checkout and
    reach the loop only through `--continuity-evaluator-command`, which defaults to unset.
    §52, §54.1, §55.1 and §56 all drafted without it, and §56.5 measured the cost: an
    `MP 6/4` reaching accepted canon across twelve ACCEPT decisions and zero findings, then
    rendered into every later prompt as the state to carry forward.

    There is nowhere to default *to* — the pack's path belongs to a machine, not to this
    package — so the fix is the outbox's: keep the null and make it visible.
    """
    _book(store, "litrpg")

    unwired = status_module.collect(store, NOW, continuity_evaluator=False)
    wired = status_module.collect(store, NOW, continuity_evaluator=True)

    assert unwired.unchecked_system_voice_books == 1
    rendered = unwired.render()
    assert "rules pack" in rendered and "NOT RUNNING" in rendered, rendered
    assert unwired.as_dict()["unchecked_system_voice_books"] == 1

    assert wired.unchecked_system_voice_books == 0
    assert "rules pack" not in wired.render(), (
        "a wired run must not carry the warning; a line that is always there is a line "
        "nobody reads"
    )


def test_a_book_that_does_not_speak_system_voice_is_not_accused(store: SqliteStore) -> None:
    """The negative control, and the reason this reads canon rather than a genre flag.

    A locked-room mystery has no ledger for the LitRPG pack to check, so reporting it as
    unchecked would be the report crying wolf on every book in the store. `speaks_system_voice`
    answers off the records, which is the same reason `render_prompt` consults it before asking
    a scene for a status line at all.
    """
    _book(store, "mystery")

    report = status_module.collect(store, NOW, continuity_evaluator=False)

    assert report.unchecked_system_voice_books == 0
    assert "rules pack" not in report.render()


def test_the_warning_defaults_off_so_an_embedding_is_not_accused(store: SqliteStore) -> None:
    """`collect` defaults `continuity_evaluator=True`.

    Only the CLI knows whether the sibling is wired. A default of False would make every
    other caller — and every test that builds a status report for an unrelated reason —
    report a missing evaluator it has no opinion about.
    """
    _book(store, "litrpg")

    assert status_module.collect(store, NOW).unchecked_system_voice_books == 0
