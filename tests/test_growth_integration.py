"""A repeated paid investment reaches the next writer through accepted extraction."""

from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.planner import make_plan_selector
from litharness.domain import gamesystem as gs
from litharness.domain import worlds
from litharness.domain.generation import CompletionRequest, CompletionResult, Usage
from litharness.domain.policy import Outcome
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import PROJECT_ID
from tests.helpers import accepted_all
from tests.test_growth_limits import _system, _with_ability
from tests.test_outline import START, a_book


@pytest.mark.parametrize("limit", ["open", 2])
def test_second_paid_investment_is_extracted_and_carried_to_the_next_writer(
    tmp_path: Path,
    limit: worlds.GrowthLimit,
) -> None:
    system = _with_ability(_system(limit), "duration", growth_limit=1)
    opening = gs.CharacterSheet(
        system,
        "smith",
        "r4",
        (("weld", 1), ("load", 1), ("duration", 1), ("brace", 1), ("point", 2)),
    )
    canon = accepted_all(
        [
            *gs.records_for(system),
            *gs.records_for_sheet(opening),
            worlds.world_record("smith", worlds.ENTITY_ROLE_PREDICATE, value="protagonist"),
        ]
    )
    requests: list[CompletionRequest] = []
    provider = FakeProvider()

    def complete(request: CompletionRequest) -> CompletionResult:
        requests.append(request)
        assert request.system is not None
        line = next(row for row in request.system.splitlines() if row.startswith("[STATUS]"))
        assert "Load 2" in line and "Point 1" in line and "Weld 1" in line
        prose = (
            "The smith braced the cracked lintel before spending another point on Load. "
            "The seam took its weight, leaving one point in reserve. She lifted the brace "
            "carefully and watched for a new crack along the old joint. When none appeared, "
            "she marked the tested span in chalk and went to fetch the longer support. "
            "The unused point would have to wait until she knew what the next span needed."
        )
        return CompletionResult(
            text=f"{prose}\n\n{line}\n", provider="fake", model="fixed", usage=Usage(10, 20)
        )

    provider.complete = complete  # type: ignore[method-assign]
    registry = ProviderRegistry(provider)
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision = a_book(store, scenes=6, sheet=False)
        store.record_state_records(
            revision.book_id, revision.branch_id, canon, created_at="2026-08-16T00:00:00Z"
        )
        selector = make_plan_selector(project_id=PROJECT_ID, outline=True)
        conductor = Conductor(
            store=store,
            holder="growth-test",
            project_id=PROJECT_ID,
            registry=registry,
            select=selector,
            handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
        )
        result = conductor.tick(START)
        assert result.outcome is TickOutcome.RAN_JOB
        head = store.head(revision.book_id, revision.branch_id)
        assert head is not None and head.node("scene-1").content
        decision = store.decision_for_revision(head.revision_id)
        assert decision is not None and decision.outcome is Outcome.ACCEPT
        assert len(requests) == 1 and store.verify_integrity() == 2
        records = store.state_records(revision.book_id, revision.branch_id)
        before = gs.sheet_of(records, "smith", at="s0")
        after = gs.sheet_of(records, "smith", at="s1")
        assert before is not None and after is not None
        assert (before.magnitude("load"), before.magnitude("point")) == (1, 2)
        assert (after.magnitude("load"), after.magnitude("point")) == (2, 1)
        assert after.system.scale.maximum == 1 and after.magnitude("weld") == 1
        deepen = gs.Move(gs.AdvanceKind.DEEPEN, ability_id="load")
        assert (deepen in gs.legal_moves(after)) is (limit == "open")
        next_job = selector(store, "growth-test", START + 1, 60.0)
        assert next_job is not None and next_job.payload["logical_id"] == "scene-2"
        next_system = next_job.payload["system"]
        line = next(row for row in next_system.splitlines() if row.startswith("[STATUS]"))
        assert "Load 2" in line and "Point 1" in line
        rule = (
            "load can be gained or deepened repeatedly; no cap is declared"
            if limit == "open"
            else "load can be gained or deepened up to 2"
        )
        assert rule in next_system
