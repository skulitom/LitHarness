"""T4's oracle: does the L0 arm describe what `context.assemble` really selects?

Three layers, in rising stakes:

1. **Round-trip on the committed fixture** — every id the arm reports exists in the
   workload it came from, and the census columns account for every selected id. This is the
   mapping contract: a packet identity that cannot be traced back to a workload item makes
   every downstream number fiction.
2. **A hand-built six-scene workload** whose answer can be *stated*, not just recomputed —
   the dark count especially, which is the column §56.4 is about. With six 50-token scenes,
   five 6-token facts, a 4-token premise and a usable budget of 150, the arithmetic is
   forced: premise 4 + facts 30 = 34 spent, prose ceiling 150 carries scenes 5 and 4
   (34+50, 134), scene 3 would need 184 and goes dark with scenes 2 and 1 behind it.
3. **The §56.4 reproduction** over LongRangeContext's own long-serial workloads when they
   exist. Skipped while `benchmarks/corpora/rlm/` is absent — another task generates them —
   and honest either way about the numbers it prints.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

arm = pytest.importorskip(
    "context_l0_arm",
    reason="research module; needs the quality-measurement directory on the path",
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lrc-synthetic-20-chapter.json"

#: Where the sibling repository's long-serial workloads land when its generator has run.
RLM_DIR = Path(r"C:\DEV\LongRangeContext\benchmarks\corpora\rlm")



def _scene_text(index: int) -> str:
    """Exactly 50 regex-v1 tokens: `Scene`, the digit, `opens`, `.`, then 46 fillers."""
    return f"Scene {index} opens. " + " ".join(["filler"] * 46)


def _tiny_workload(*, with_summaries: bool = False, secret_pov: bool = False):
    """Six scenes of known cost, one fact each, drafting scene 6 at a 150-token budget."""
    scenes = tuple(
        arm.Scene(scene_id=f"s{index}", ordinal=index, text=_scene_text(index))
        for index in range(1, 7)
    )
    items = [
        arm.WorkloadItem(
            item_id=f"f{index}",
            kind="fact",
            text="alice keeps the ledger true.",
            scene_id=f"s{index}",
            scene_ordinal=index,
            # 6 tokens: alice, keeps, the, ledger, true, and the period.
            pov_visibility=("mara",) if (secret_pov and index == 1) else (),
        )
        for index in range(1, 6)
    ]
    if with_summaries:
        items += [
            arm.WorkloadItem(
                item_id=f"sum-{index}",
                kind="summary",
                text=f"Scene {index} happened here.",
                scene_id=f"s{index}",
                scene_ordinal=index,
                authority="derived",
            )
            for index in range(1, 4)
        ]
    query = arm.Query(
        query_id="q6",
        operation="draft_scene",
        token_budget=150,
        scene_id="s6",
        scene_ordinal=6,
        pov_character_id="ada",
        intent="A tiny book.",
    )
    return arm.Workload(
        book_id="tiny-book",
        branch_id="main",
        title="Tiny",
        scenes=scenes,
        items=tuple(items),
        queries=(query,),
        metadata={},
    )


# -- 1. round-trip on the committed fixture --------------------------------------------------


def test_the_fixture_exists_and_carries_draft_queries():
    workload = arm.load_workload(FIXTURE)
    drafts = arm.draft_queries(workload)
    assert drafts, "the fixture must carry at least one draft_scene query"
    assert all(q.operation == "draft_scene" for q in drafts)


def test_every_selected_id_round_trips_to_a_workload_id():
    workload = arm.load_workload(FIXTURE)
    valid_ids = {item.item_id for item in workload.items} | {
        scene.scene_id for scene in workload.scenes
    }
    for query in arm.draft_queries(workload):
        selection = arm.run_query(workload, query)
        assert set(selection.selected_ids) <= valid_ids, (
            f"{query.query_id}: a selected id names nothing in the workload"
        )
        assert len(selection.selected_ids) == len(set(selection.selected_ids))


def test_the_census_columns_add_up_to_the_selection():
    workload = arm.load_workload(FIXTURE)
    for query in arm.draft_queries(workload):
        selection = arm.run_query(workload, query)
        assert (
            selection.full_prose_count + selection.summary_count + selection.fact_count
            == len(selection.selected_ids)
        ), f"{query.query_id}: the columns do not account for every selected id"


def test_the_usable_budget_equals_the_workload_token_budget():
    workload = arm.load_workload(FIXTURE)
    for query in arm.draft_queries(workload):
        selection = arm.run_query(workload, query)
        assert selection.used_tokens <= query.token_budget, (
            f"{query.query_id}: the packet spent {selection.used_tokens} of a "
            f"{query.token_budget}-token budget"
        )


def test_pov_invisible_ids_are_reported_not_hidden():
    workload = arm.load_workload(FIXTURE)
    query = arm.draft_queries(workload)[0]
    selection = arm.run_query(workload, query)
    invisible = set(selection.pov_invisible_ids_in_inputs)
    by_id = {item.item_id: item for item in workload.items}
    assert invisible, "the synthetic fixture deliberately restricts some records to other POVs"
    for item_id in invisible:
        item = by_id[item_id]
        assert item.pov_visibility, "a reported id must actually carry a restriction"
        assert query.pov_character_id not in item.pov_visibility
        # And kept in the inputs means kept: the packet recorded the exclusion rather than
        # the arm silently dropping it upstream.
        reasons = [reason for omitted, reason in selection.omitted if omitted == item_id]
        assert any("not visible to POV" in reason for reason in reasons)


# -- 2. the hand-built six-scene workload, where the answer is statable ----------------------


def test_dark_count_on_the_hand_built_workload_is_three():
    workload = _tiny_workload()
    selection = arm.run_query(workload, workload.queries[0])
    # Stated by hand, before running: 150 usable - 4 premise - 30 facts leaves prose room
    # for scenes 5 and 4 whole; scenes 3, 2 and 1 arrive in no form at all.
    assert selection.full_prose_count == 2
    assert selection.summary_count == 0
    assert selection.fact_count == 5
    assert selection.dark_prior_scenes == ("s1", "s2", "s3")


def test_a_supplied_summary_lights_a_dark_scene_without_spending_prose():
    workload = _tiny_workload(with_summaries=True)
    selection = arm.run_query(workload, workload.queries[0])
    # Scenes 5 and 4 still pack whole; the evicted 3, 2 and 1 arrive as summaries instead of
    # going dark — 15 tokens of summary, and they all fit under what remained after prose.
    assert selection.full_prose_count == 2
    assert selection.summary_count == 3
    assert selection.fact_count == 5
    assert selection.dark_prior_scenes == ()
    # And the summaries map back to their workload item ids, not to `assemble`'s minted
    # `summary:<label>` identifiers.
    assert {"sum-1", "sum-2", "sum-3"} <= set(selection.selected_ids)


def test_a_pov_restricted_fact_is_reported_and_excluded_by_the_packet():
    workload = _tiny_workload(secret_pov=True)
    selection = arm.run_query(workload, workload.queries[0])
    assert selection.pov_invisible_ids_in_inputs == ("f1",)
    assert selection.fact_count == 4, "the restricted record did not reach the packet"
    reasons = {reason for omitted, reason in selection.omitted if omitted == "f1"}
    assert any("not visible to POV" in reason for reason in reasons)


# -- the documented CLI surface ---------------------------------------------------------------


def test_main_writes_the_documented_json(tmp_path):
    out = tmp_path / "l0.json"
    assert arm.main(["--workload", str(FIXTURE), "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert set(report) == {"strategy", "selections", "details", "source"}
    assert report["strategy"] == "litharness-assemble"
    assert set(report["source"]) == {
        "litharness_commit",
        "counter",
        "token_budget_default",
        "reserved_output",
    }
    workload = arm.load_workload(FIXTURE)
    expected_queries = {q.query_id for q in arm.draft_queries(workload)}
    assert set(report["selections"]) == expected_queries
    assert set(report["details"]) == expected_queries
    for detail in report["details"].values():
        assert set(detail) == {
            "selected_ids",
            "omitted",
            "tokens_by_section",
            "used_tokens",
            "dark_prior_scenes",
            "full_prose_count",
            "summary_count",
            "fact_count",
            "pov_invisible_ids_in_inputs",
        }


def test_census_prints_a_section_56_4_style_table(capsys):
    assert arm.main(["--workload", str(FIXTURE), "--census"]) == 0
    printed = capsys.readouterr().out
    assert "scenes" in printed and "dark" in printed
    # One data row per draft_scene query, beyond the header and rule lines.
    data_rows = [line for line in printed.splitlines() if line[:6].strip().isdigit()]
    assert len(data_rows) == 2


# -- 3. the real test: reproduce §56.4 over LongRangeContext's own workloads -----------------


def _reference_table() -> list[dict[str, int]]:
    return [
        {
            "scenes": scenes,
            "full_prose": expected[0],
            "summaries": expected[1],
            "facts": expected[2],
            "dark": expected[3],
        }
        for scenes, expected in sorted(arm.SECTION_56_4.items())
    ]


@pytest.mark.skipif(not RLM_DIR.is_dir(), reason="rlm workloads not generated yet")
def test_census_over_rlm_serial_lands_on_section_56_4():
    rows: list[dict[str, int]] = []
    failures: list[str] = []
    for scenes, expected in sorted(arm.SECTION_56_4.items()):
        path = RLM_DIR / f"rlm-serial-{scenes}.json"
        if not path.exists():
            pytest.fail(
                f"{RLM_DIR} exists but {path.name} is missing; the generator is part-done"
            )
        workload = arm.load_workload(path)
        queries = arm.draft_queries(workload)
        if not queries:
            pytest.fail(f"{path.name} carries no draft_scene query to census")
        last = max(queries, key=lambda q: q.scene_ordinal or 0)
        # §56.4's table was measured at the shipped default budget (6,000 with 1,500
        # reserved, i.e. the 4,500 usable tokens the workload queries already carry);
        # the 24,000 figure in that entry is the OTHER column, the one with zero dark
        # scenes. The census therefore runs each query at its own budget, unforced.
        selection = arm.run_query(workload, last)
        rows.append(
            {
                "scenes": scenes,
                "full_prose": selection.full_prose_count,
                "summaries": selection.summary_count,
                "facts": selection.fact_count,
                "dark": len(selection.dark_prior_scenes),
            }
        )
        # The gate is scaled to the phenomenon, not to a curve fit. Dark prior scenes —
        # the quantity §56.4 is about — and the prose/facts columns are gated at ±15%
        # relative with a minimum slack of 2 (an absolute ±5 on dark would be ±71% at
        # 30 scenes and ±4.6% at 120). Summaries are reported, never gated: with fixed
        # per-item sizes the summary count is the residual of the budget arithmetic,
        # and §56.4's implied summary sizes drift with horizon — gating that residual
        # would force per-horizon generator knobs, i.e. tuning the instrument to the
        # answer.
        checked = (
            ("full prose", selection.full_prose_count, expected[0]),
            ("facts", selection.fact_count, expected[2]),
            ("dark", len(selection.dark_prior_scenes), expected[3]),
        )
        for column, actual, want in checked:
            slack = max(0.15 * want, 2)
            if abs(actual - want) > slack:
                failures.append(
                    f"rlm-serial-{scenes}: {column} = {actual}, §56.4 says {want} "
                    f"(±15% allows {want - slack:.1f}-{want + slack:.1f})"
                )

    # Printed whichever way the comparison lands — the numbers are the deliverable, and a
    # bare assert would hide exactly what the workload generator needs corrected.
    print()
    print(arm.format_census(rows))
    print("\n§56.4 reference:")
    print(arm.format_census(_reference_table()))
    if failures:
        pytest.fail("census misses §56.4:\n" + "\n".join(failures))
