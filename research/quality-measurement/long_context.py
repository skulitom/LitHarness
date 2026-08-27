"""First-party, model-free endurance workloads for LitHarness context assembly.

The production promise is an endless serial packaged in roughly fifty-chapter releases. This
module therefore generates its own deterministic manuscripts at chapter horizons, translates
their state, events, summaries, and open threads into the real ``context.assemble`` inputs, and
reports what survives the fixed prompt budget. It imports no external context subsystem and
reads no external fixture tree: the workload and the strategy it measures both belong to
LitHarness.

The generated prose is repetitive synthetic padding. It exists to exert realistic token
pressure, not to imitate a novel or stand in for a model-quality test.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain.context import (
    COUNTER_ID,
    DEFAULT_RESERVED_OUTPUT,
    assemble,
)
from litharness.domain.extraction import PLANNED_POSITION_VERSION
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.revision import Revision, build_revision

SCENES_PER_CHAPTER = 4
HORIZON_CHAPTERS = (6, 25, 50, 60, 100)
WORDS_PER_SCENE = 650
SUMMARY_WORDS = 45
USABLE_TOKEN_BUDGET = 4_500
SENTINEL_ID = "thread-volume-one-bell"

CHARACTERS = ("ada", "bram", "cora", "dax", "elin", "farah")
_PLACES = ("archive", "bridge", "foundry", "garden", "harbour", "tower")
_FILLER = (
    "watch",
    "ledger",
    "weather",
    "footstep",
    "window",
    "question",
    "answer",
    "road",
    "lantern",
    "silence",
    "promise",
    "threshold",
)


@dataclass(frozen=True, slots=True)
class Scene:
    scene_id: str
    ordinal: int
    text: str
    chapter: int


@dataclass(frozen=True, slots=True)
class WorkloadItem:
    item_id: str
    kind: str
    text: str
    scene_id: str
    scene_ordinal: int
    subject: str = "serial"
    predicate: str = "records"
    value: object = "true"
    authority: lc.StateAuthority = lc.StateAuthority.ACCEPTED_CANON
    pov_visibility: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Query:
    query_id: str
    scene_id: str
    scene_ordinal: int
    token_budget: int
    pov_character_id: str
    intent: str
    operation: str = "draft_scene"


@dataclass(frozen=True, slots=True)
class Workload:
    book_id: str
    branch_id: str
    title: str
    chapters: int
    scenes_per_chapter: int
    scenes: tuple[Scene, ...]
    items: tuple[WorkloadItem, ...]
    queries: tuple[Query, ...]


def _padded_words(lead: str, total: int, *, phase: int) -> str:
    words = lead.split()
    words.extend(_FILLER[(phase + index) % len(_FILLER)] for index in range(total - len(words)))
    return " ".join(words) + "."


def generate_workload(
    chapters: int,
    *,
    scenes_per_chapter: int = SCENES_PER_CHAPTER,
    words_per_scene: int = WORDS_PER_SCENE,
) -> Workload:
    """Construct one deterministic serial prefix with no I/O and no model call."""
    if chapters < 1:
        raise ValueError("a context workload needs at least one chapter")
    if scenes_per_chapter < 1:
        raise ValueError("scenes_per_chapter must be positive")
    if words_per_scene < 100:
        raise ValueError("words_per_scene must be at least 100")

    scene_count = chapters * scenes_per_chapter
    scenes: list[Scene] = []
    items: list[WorkloadItem] = []
    for ordinal in range(1, scene_count + 1):
        chapter = (ordinal - 1) // scenes_per_chapter + 1
        scene_id = f"scene-{ordinal:06d}"
        character = CHARACTERS[(ordinal - 1) % len(CHARACTERS)]
        place = _PLACES[(ordinal * 5) % len(_PLACES)]
        prose = _padded_words(
            f"Scene {ordinal} follows {character} through the {place}",
            words_per_scene,
            phase=ordinal,
        )
        summary = _padded_words(
            f"Chapter {chapter} scene {ordinal} moves {character} to the {place}",
            SUMMARY_WORDS,
            phase=ordinal * 3,
        )
        scenes.append(Scene(scene_id, ordinal, prose, chapter))
        items.extend(
            (
                WorkloadItem(f"prose-{ordinal:06d}", "exact_prose", prose, scene_id, ordinal),
                WorkloadItem(f"summary-{ordinal:06d}", "summary", summary, scene_id, ordinal),
                WorkloadItem(
                    f"goal-{ordinal:06d}",
                    "fact",
                    f"{character} pursues objective {ordinal} from the {place}.",
                    scene_id,
                    ordinal,
                    subject=character,
                    predicate="pursues",
                    value=f"objective-{ordinal}",
                    # Some current state belongs to another viewpoint. The real assembler must
                    # record its exclusion instead of silently leaking it into a no-POV call.
                    pov_visibility=("rival",) if ordinal % 29 == 0 else (),
                ),
            )
        )
        if ordinal % scenes_per_chapter == 0:
            items.append(
                WorkloadItem(
                    f"chapter-event-{chapter:04d}",
                    "event",
                    f"The serial completed chapter {chapter} at scene {ordinal}.",
                    scene_id,
                    ordinal,
                    subject="serial",
                    predicate="completed_chapter",
                    value=chapter,
                )
            )

    # Open early enough to cross the first release boundary on every full-volume workload.
    if scene_count > 40:
        sentinel_scene = scenes[39]
        items.append(
            WorkloadItem(
                SENTINEL_ID,
                "thread",
                "The bell beneath the archive must answer after the first volume boundary.",
                sentinel_scene.scene_id,
                sentinel_scene.ordinal,
                subject="archive_bell",
                predicate="owed",
                value=state_mod.THREAD_OPEN,
            )
        )

    target = scenes[-1]
    query = Query(
        query_id=f"draft-{target.scene_id}",
        scene_id=target.scene_id,
        scene_ordinal=target.ordinal,
        token_budget=USABLE_TOKEN_BUDGET,
        pov_character_id="ada",
        intent=(
            "Continue the serial from established state while preserving distant open promises."
        ),
    )
    return Workload(
        book_id=f"litharness-endurance-{chapters}",
        branch_id="main",
        title=f"LitHarness endurance prefix ({chapters} chapters)",
        chapters=chapters,
        scenes_per_chapter=scenes_per_chapter,
        scenes=tuple(scenes),
        items=tuple(items),
        queries=(query,),
    )


@dataclass(frozen=True, slots=True)
class EnduranceInputs:
    revision: Revision
    plan_items: tuple[lc.PlanItem, ...]
    state_records: tuple[lc.StateRecord, ...]
    summaries: dict[str, str]
    token_budget: int
    reserved_output: int
    prose_item_by_scene: dict[str, str]
    summary_item_by_scene: dict[str, str]
    target_scene_id: str
    prior_scene_ids: tuple[str, ...]
    pov_invisible_item_ids: tuple[str, ...]


def build_inputs(workload: Workload, query: Query) -> EnduranceInputs:
    prior = [scene for scene in workload.scenes if scene.ordinal < query.scene_ordinal]
    target = next(scene for scene in workload.scenes if scene.scene_id == query.scene_id)
    manuscript = [*prior, target]
    keys = iter(initial_keys(len(manuscript)))
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title=workload.title)]
    nodes.extend(
        Node.text_node(
            scene.scene_id,
            NodeKind.SCENE,
            next(keys),
            scene.text,
            parent_logical_id="book",
            title=f"Chapter {scene.chapter}",
        )
        for scene in manuscript
    )
    revision = build_revision(workload.book_id, workload.branch_id, nodes)
    records: list[lc.StateRecord] = []
    invisible: list[str] = []
    kind_map = {
        "fact": lc.StateRecordKind.ASSERTION,
        "event": lc.StateRecordKind.EVENT,
        "thread": lc.StateRecordKind.THREAD,
    }
    for item in workload.items:
        if item.kind not in kind_map:
            continue
        records.append(
            lc.StateRecord(
                record_id=item.item_id,
                kind=kind_map[item.kind],
                subject=item.subject,
                predicate=item.predicate,
                value=item.value,
                story_position=lc.StoryPosition(order_key=f"s{item.scene_ordinal:06d}"),
                authority=item.authority,
                pov_visibility=list(item.pov_visibility),
                predicate_registry_version=PLANNED_POSITION_VERSION,
            )
        )
        if item.pov_visibility and query.pov_character_id not in item.pov_visibility:
            invisible.append(item.item_id)

    return EnduranceInputs(
        revision=revision,
        plan_items=(
            lc.PlanItem(
                logical_id=f"plan-{query.query_id}",
                kind=lc.PlanKind.PREMISE,
                text=query.intent,
                authority=lc.PlanAuthority.INTENDED,
            ),
        ),
        state_records=tuple(records),
        summaries={
            item.scene_id: item.text
            for item in workload.items
            if item.kind == "summary" and item.scene_ordinal < query.scene_ordinal
        },
        token_budget=query.token_budget + DEFAULT_RESERVED_OUTPUT,
        reserved_output=DEFAULT_RESERVED_OUTPUT,
        prose_item_by_scene={
            item.scene_id: item.item_id
            for item in workload.items
            if item.kind == "exact_prose"
        },
        summary_item_by_scene={
            item.scene_id: item.item_id for item in workload.items if item.kind == "summary"
        },
        target_scene_id=query.scene_id,
        prior_scene_ids=tuple(scene.scene_id for scene in prior),
        pov_invisible_item_ids=tuple(invisible),
    )


@dataclass(frozen=True, slots=True)
class ContextSelection:
    query_id: str
    selected_ids: tuple[str, ...]
    omitted: tuple[tuple[str, str], ...]
    tokens_by_section: dict[str, int]
    used_tokens: int
    dark_prior_scenes: tuple[str, ...]
    full_prose_count: int
    summary_count: int
    fact_count: int
    pov_invisible_ids_in_inputs: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "selected_ids": list(self.selected_ids),
            "omitted": [list(pair) for pair in self.omitted],
            "tokens_by_section": self.tokens_by_section,
            "used_tokens": self.used_tokens,
            "dark_prior_scenes": list(self.dark_prior_scenes),
            "full_prose_count": self.full_prose_count,
            "summary_count": self.summary_count,
            "fact_count": self.fact_count,
            "pov_invisible_ids_in_inputs": list(self.pov_invisible_ids_in_inputs),
        }


def _workload_id_for(
    item_kind: lc.ContextItemKind, source_logical_id: str, inputs: EnduranceInputs
) -> str | None:
    if item_kind in (lc.ContextItemKind.PLAN, lc.ContextItemKind.AUTHOR_RULE):
        return None
    if item_kind is lc.ContextItemKind.EXACT_PROSE:
        return inputs.prose_item_by_scene.get(source_logical_id, source_logical_id)
    if item_kind is lc.ContextItemKind.SUMMARY:
        return inputs.summary_item_by_scene.get(source_logical_id, source_logical_id)
    return source_logical_id


def _map_omission(source_logical_id: str, inputs: EnduranceInputs) -> str:
    if source_logical_id in inputs.prose_item_by_scene:
        return inputs.prose_item_by_scene[source_logical_id]
    if source_logical_id in inputs.summary_item_by_scene:
        return inputs.summary_item_by_scene[source_logical_id]
    return source_logical_id


def run_query(workload: Workload, query: Query | None = None) -> ContextSelection:
    selected_query = query or workload.queries[-1]
    inputs = build_inputs(workload, selected_query)
    packet = assemble(
        inputs.revision,
        inputs.target_scene_id,
        plan_items=inputs.plan_items,
        state_records=inputs.state_records,
        query_id=selected_query.query_id,
        pov_character_id=selected_query.pov_character_id,
        token_budget=inputs.token_budget,
        reserved_output=inputs.reserved_output,
        summaries=inputs.summaries,
        story_time_cutoff=f"s{selected_query.scene_ordinal:06d}",
        state_moment=state_mod.StateMoment.ENTERING,
        project_state_changes=True,
    )

    selected: list[str] = []
    prose_ids: set[str] = set()
    summary_ids: set[str] = set()
    prose_count = summary_count = fact_count = 0
    for packed in packet.items:
        workload_id = _workload_id_for(packed.kind, packed.source_logical_id, inputs)
        if workload_id is None:
            continue
        selected.append(workload_id)
        if packed.kind is lc.ContextItemKind.EXACT_PROSE:
            prose_count += 1
            prose_ids.add(packed.source_logical_id)
        elif packed.kind is lc.ContextItemKind.SUMMARY:
            summary_count += 1
            summary_ids.add(packed.source_logical_id)
        else:
            fact_count += 1

    return ContextSelection(
        query_id=selected_query.query_id,
        selected_ids=tuple(selected),
        omitted=tuple(
            (_map_omission(item.source_logical_id, inputs), item.reason)
            for item in packet.omitted
        ),
        tokens_by_section={
            name: sum(item.tokens for item in section)
            for name, section in packet.sections.items()
        },
        used_tokens=packet.used_tokens,
        dark_prior_scenes=tuple(
            scene_id
            for scene_id in inputs.prior_scene_ids
            if scene_id not in prose_ids and scene_id not in summary_ids
        ),
        full_prose_count=prose_count,
        summary_count=summary_count,
        fact_count=fact_count,
        pov_invisible_ids_in_inputs=inputs.pov_invisible_item_ids,
    )


def census_rows(chapter_horizons: tuple[int, ...] = HORIZON_CHAPTERS) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for chapters in chapter_horizons:
        workload = generate_workload(chapters)
        selection = run_query(workload)
        rows.append(
            {
                "chapters": chapters,
                "scenes": len(workload.scenes),
                "full_prose": selection.full_prose_count,
                "summaries": selection.summary_count,
                "facts": selection.fact_count,
                "dark": len(selection.dark_prior_scenes),
                "used_tokens": selection.used_tokens,
            }
        )
    return rows


def format_census(rows: list[dict[str, int]]) -> str:
    columns = ("chapters", "scenes", "full_prose", "summaries", "facts", "dark", "used_tokens")
    widths = {
        column: max(len(column), *(len(str(row[column])) for row in rows))
        for column in columns
    }
    header = "  ".join(f"{column:>{widths[column]}}" for column in columns)
    lines = [header, "-" * len(header)]
    lines.extend(
        "  ".join(f"{row[column]:>{widths[column]}}" for column in columns) for row in rows
    )
    return "\n".join(lines)


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--chapters",
        nargs="+",
        type=int,
        default=list(HORIZON_CHAPTERS),
        help="chapter horizons to exercise (default: 6 25 50 60 100)",
    )
    parser.add_argument("--out", type=Path, default=None, help="write the report JSON here")
    parser.add_argument("--census", action="store_true", help="print the context-pressure table")
    args = parser.parse_args(argv)

    horizons: dict[str, dict[str, Any]] = {}
    for chapters in args.chapters:
        selection = run_query(generate_workload(chapters))
        horizons[str(chapters)] = selection.to_json()
    report = {
        "strategy": "litharness-context.v1",
        "horizons": horizons,
        "source": {
            "litharness_commit": git_head(),
            "counter": COUNTER_ID,
            "usable_token_budget": USABLE_TOKEN_BUDGET,
            "reserved_output": DEFAULT_RESERVED_OUTPUT,
            "scenes_per_chapter": SCENES_PER_CHAPTER,
        },
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    else:
        print(rendered)
    if args.census:
        print(format_census(census_rows(tuple(args.chapters))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
