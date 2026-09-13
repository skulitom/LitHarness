"""The isolated directions use recorded production planning and reach actual requests."""

import json
import runpy
from pathlib import Path

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, outline
from litharness.domain.directives import DirectiveStatus
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_concept import _discovery, _example
from tests.test_outline import START, StubPlanner, a_book
from tests.test_scene_brief import outlined_payload

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "research/quality-measurement/opening-consequence-20260914"


def test_delegated_directions_have_policy_provenance_and_reach_outline_and_writer(
    tmp_path, monkeypatch,
):
    runner = runpy.run_path(str(HERE / "run.py"))
    directions = json.loads((HERE / "directions.json").read_text(encoding="utf-8"))[
        "pre_registration"
    ]
    database = tmp_path / "directed.db"
    drawn = concept.Concept.from_payload({**_example(), "discovery": _discovery()})
    with SqliteStore.open(database) as store:
        a_book(store, scenes=6, extra_plan_items=(drawn.plan_item(),))
    installed = runner["install_directions"](database, directions)
    assert {item["name"] for item in installed} == {"opening", "consequence"}
    with SqliteStore.open(database) as store:
        for item in installed:
            directive = store.load_directive(item["directive_id"])
            assert directive.status is DirectiveStatus.APPLIED
            assert directive.metadata["literal_user_quotation"] is False
            assert directive.author.startswith("operator-delegated:")
            plan = store.plan_revision(BOOK_ID, BRANCH_ID).item(item["logical_id"])
            assert plan.locked and plan.text == directions[item["name"]]
        assert concept.concept_of(store.plan_items(BOOK_ID, BRANCH_ID)) == drawn
        registry = StubPlanner(outlined_payload())
        monkeypatch.setattr(cli, "build_default_registry", lambda: registry)
        args = cli.build_parser().parse_args([
            "--project", PROJECT_ID, "--target-words", "1800",
            "--chapter-scenes", "1", "--arc-chapters", "6", "tick",
        ])
        conductor = cli._conductor(store, args)
        job = conductor.select(store, "outline-test", START + 10, 60)
        assert job is not None and job.job_kind == outline.BOOK_OUTLINE
        conductor.handlers[job.job_kind](job, START + 10)
        payload = json.loads(registry.requests[0].prompt)
        assert set(directions.values()) <= {item["text"] for item in payload["author_locks"]}
        assert [item["chapter"] for item in payload["scenes"]] == list(range(1, 7))
        assert payload["target_scene_words"] == 1800
        writer = conductor.select(store, "writer-test", START + 11, 60)
        assert writer is not None
        assert all(body in writer.payload["system"] for body in directions.values())


def test_trial_uses_unchanged_source_and_bounded_original_layout():
    runner = runpy.run_path(str(HERE / "run.py"))
    base, driver = runner["BASE"], runner["DRIVER"]
    assert driver.RUN == base.RUN == ROOT / "runs/opening-consequence-20260914"
    assert driver.BOOK == driver.RUN / "book"
    assert base.REVISION == "14fd7fb"
    assert base.OWNER == "opening-consequence-20260914:"
    assert (driver.CHAPTERS, base.MAX_CALLS, base.MAX_TOKENS, base.MAX_SECONDS) == (
        6, 32, 2_200_000, 5400,
    )
