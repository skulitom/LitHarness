"""T4, the L0 arm: LitHarness's real `context.assemble` over LongRangeContext workloads.

LongRangeContext emits long-serial workloads as JSON files of its `BenchmarkBook` record.
This module loads one of those files without importing LongRangeContext (§13: siblings
depend on contracts and never on each other), translates it into exactly what
`litharness.domain.context.assemble` takes — a `Revision`, `PlanItem`s, `StateRecord`s,
supplied summaries — and records what the assembler selects, omits and leaves dark.

**What is measured, and what deliberately is not scored.** This is the L0 arm of the
recursive-context measurement: the packet's *composition* under a budget, not the generated
prose. The census columns reproduce `plan/stage-0-decisions.md` §56.4 — full prose,
summaries, facts, and "dark" prior scenes (a scene present in no form at all) — so the
numbers can be laid beside that table directly.

**Identity mapping.** The packet exposes three kinds of identity and each maps back to the
workload differently:

- state items carry `record_id` as both `item_id` and `source_logical_id`, so a workload
  item id survives the round trip in the packet item itself;
- prose items expose the manuscript node's logical id, which this arm sets equal to the
  workload `scene_id`; the side map `prose_item_by_scene` recovers the workload's
  `exact_prose` item id when the workload carries those items;
- summary items are minted by `assemble` as ``summary:<label>`` with the scene's logical id
  in `source_logical_id`, so `summary_item_by_scene` does the same for `summary` items.

**POV-invisible items stay in the inputs.** LongRangeContext's baselines do not hide them,
so hiding them here would make the arms incomparable; `assemble` still filters and records
them as omissions ("not visible to POV …"), and `pov_invisible_ids_in_inputs` reports which
ids were affected so the evaluation can count leaks either way.

**Budget arithmetic.** `assemble` computes ``available = token_budget - reserved_output``
before packing anything and packs every section against `available` — the reserve is never
applied per-section or anywhere else. So passing
``token_budget = query.token_budget + DEFAULT_RESERVED_OUTPUT`` while keeping the default
reserve makes the packet's usable budget exactly the workload query's `token_budget`.
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
    DEFAULT_TOKEN_BUDGET,
    assemble,
)
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.revision import Revision, build_revision

#: §56.4's table, transcribed. Keyed by the "scenes" column (prior scenes); values are
#: (full prose, summaries, facts, dark) at the shipped default budget (6,000 with 1,500 reserved).
SECTION_56_4 = {
    20: (3, 16, 19, 0),
    30: (3, 19, 29, 7),
    57: (2, 22, 56, 32),
    82: (2, 12, 81, 67),
    120: (1, 10, 119, 108),
}

_RECORD_KINDS = {
    "fact": lc.StateRecordKind.ASSERTION,
    "thread": lc.StateRecordKind.THREAD,
    "event": lc.StateRecordKind.EVENT,
}


# -- the workload, as plain dataclasses mirroring the BenchmarkBook JSON --------------------


@dataclass(frozen=True)
class Scene:
    scene_id: str
    ordinal: int
    text: str
    chapter_id: str | None = None
    title: str | None = None
    pov_character_id: str | None = None
    revision_id: str | None = None
    branch_id: str | None = None
    story_time: Any = None


@dataclass(frozen=True)
class WorkloadItem:
    item_id: str
    kind: str
    text: str
    scene_id: str | None = None
    scene_ordinal: int | None = None
    token_count: int | None = None
    authority: str = "accepted_canon"
    confidence: float | None = None
    pov_visibility: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    superseded_by: str | None = None
    provenance: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    source_id: str | None = None
    source_revision: str | None = None
    branch_id: str | None = None
    book_id: str | None = None
    chapter_id: str | None = None


@dataclass(frozen=True)
class Query:
    query_id: str
    operation: str
    token_budget: int
    scene_id: str | None = None
    scene_ordinal: int | None = None
    pov_character_id: str | None = None
    intent: str | None = None
    book_id: str | None = None
    branch_id: str | None = None
    revision_id: str | None = None
    model_context_limit: int | None = None
    policy_version: str | None = None
    referenced_entities: tuple[str, ...] = ()
    referenced_threads: tuple[str, ...] = ()
    hard_requirements: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Workload:
    book_id: str
    branch_id: str
    title: str
    scenes: tuple[Scene, ...]
    items: tuple[WorkloadItem, ...]
    queries: tuple[Query, ...]
    metadata: dict[str, Any]


def _scene(raw: dict[str, Any]) -> Scene:
    return Scene(
        scene_id=raw["scene_id"],
        ordinal=int(raw["ordinal"]),
        text=raw.get("text") or "",
        chapter_id=raw.get("chapter_id"),
        title=raw.get("title"),
        pov_character_id=raw.get("pov_character_id"),
        revision_id=raw.get("revision_id"),
        branch_id=raw.get("branch_id"),
        story_time=raw.get("story_time"),
    )


def _ordinal_of(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    return int(value) if value is not None else None


def _item(raw: dict[str, Any]) -> WorkloadItem:
    return WorkloadItem(
        item_id=raw["item_id"],
        kind=raw["kind"],
        text=raw.get("text") or "",
        scene_id=raw.get("scene_id"),
        scene_ordinal=_ordinal_of(raw, "scene_ordinal"),
        token_count=raw.get("token_count"),
        authority=raw.get("authority") or "accepted_canon",
        confidence=raw.get("confidence"),
        pov_visibility=tuple(raw.get("pov_visibility") or ()),
        tags=tuple(raw.get("tags") or ()),
        superseded_by=raw.get("superseded_by"),
        provenance=tuple(raw.get("provenance") or ()),
        dependencies=tuple(raw.get("dependencies") or ()),
        source_id=raw.get("source_id"),
        source_revision=raw.get("source_revision"),
        branch_id=raw.get("branch_id"),
        book_id=raw.get("book_id"),
        chapter_id=raw.get("chapter_id"),
    )


def _query(raw: dict[str, Any]) -> Query:
    return Query(
        query_id=raw["query_id"],
        operation=raw.get("operation") or "draft_scene",
        token_budget=int(raw["token_budget"]),
        scene_id=raw.get("scene_id"),
        scene_ordinal=_ordinal_of(raw, "scene_ordinal"),
        pov_character_id=raw.get("pov_character_id"),
        intent=raw.get("intent"),
        book_id=raw.get("book_id"),
        branch_id=raw.get("branch_id"),
        revision_id=raw.get("revision_id"),
        model_context_limit=raw.get("model_context_limit"),
        policy_version=raw.get("policy_version"),
        referenced_entities=tuple(raw.get("referenced_entities") or ()),
        referenced_threads=tuple(raw.get("referenced_threads") or ()),
        hard_requirements=tuple(str(r) for r in raw.get("hard_requirements") or ()),
        exclusions=tuple(str(e) for e in raw.get("exclusions") or ()),
    )


def load_workload(path: Path) -> Workload:
    """Read a LongRangeContext `BenchmarkBook` JSON file. No LongRangeContext import."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    queries_raw = data.get("queries", [])
    return Workload(
        book_id=data.get("book_id") or "workload",
        branch_id=data.get("branch_id") or "main",
        title=data.get("title") or "",
        scenes=tuple(_scene(s) for s in data.get("scenes", [])),
        items=tuple(_item(i) for i in data.get("items", [])),
        queries=tuple(_query(q.get("query", q)) for q in queries_raw),
        metadata=dict(data.get("metadata") or {}),
    )


# -- translation into what `assemble` takes -------------------------------------------------


@dataclass(frozen=True)
class L0Inputs:
    """Everything `assemble` needs for one query, plus the maps back to workload ids."""

    revision: Revision
    plan_items: tuple[lc.PlanItem, ...]
    state_records: tuple[lc.StateRecord, ...]
    summaries: dict[str, str]
    token_budget: int
    reserved_output: int
    #: scene_id -> the workload's exact_prose / summary item id for that scene.
    prose_item_by_scene: dict[str, str]
    summary_item_by_scene: dict[str, str]
    target_scene_id: str
    prior_scene_ids: tuple[str, ...]
    pov_invisible_item_ids: tuple[str, ...]


def parse_record_text(text: str) -> tuple[str, str, str]:
    """Subject / predicate / value, parsed leniently as T4 specifies.

    The generator writes facts as ``"<subject> <predicate> <value>."``; the lenient read is
    first word subject, last word value (trailing period stripped), everything between the
    predicate. One- and two-word texts degrade rather than raise — the arm must run over any
    generator output, and a mis-parsed record costs a few tokens of rendering, not correctness
    of the measurement.
    """
    words = text.split()
    if len(words) >= 3:
        return words[0], " ".join(words[1:-1]), words[-1].rstrip(".")
    if len(words) == 2:
        return words[0], "is", words[1].rstrip(".")
    if words:
        return words[0], "is", ""
    return "unknown", "is", ""


def build_inputs(workload: Workload, query: Query) -> L0Inputs:
    target_ordinal = query.scene_ordinal if query.scene_ordinal is not None else 10**9
    ordered = sorted(workload.scenes, key=lambda s: s.ordinal)
    prior_scenes = [s for s in ordered if s.ordinal < target_ordinal]
    target_scene = next((s for s in ordered if s.scene_id == query.scene_id), None)

    # The manuscript holds the prior scenes plus the target itself; a scene node's logical id
    # equals the workload `scene_id`, which is how packet prose items map back. The target's
    # own text rides along harmlessly: `assemble` only reads content of scenes before it.
    manuscript = [*prior_scenes, *([target_scene] if target_scene else [])]
    keys = iter(initial_keys(len(manuscript)))
    nodes = [
        Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title=workload.title)
    ]
    nodes += [
        Node.text_node(
            scene.scene_id,
            NodeKind.SCENE,
            next(keys),
            scene.text or "",
            parent_logical_id="book",
            title=scene.title or scene.scene_id,
        )
        for scene in manuscript
    ]
    revision = build_revision(workload.book_id, workload.branch_id, nodes)

    plan_items = (
        lc.PlanItem(
            logical_id=f"plan-{query.query_id}",
            kind=lc.PlanKind.PREMISE,
            # The query intent is the target scene's plan statement; `assemble` packs exactly
            # one premise (`premise_of` refuses zero or many) as its non-droppable first item.
            text=query.intent or f"Draft {query.scene_id}.",
            authority=lc.PlanAuthority.INTENDED,
        ),
    )

    state_records: list[lc.StateRecord] = []
    pov_invisible: list[str] = []
    for item in workload.items:
        if item.kind not in _RECORD_KINDS:
            continue
        if item.scene_ordinal is None or item.scene_ordinal >= target_ordinal:
            continue  # strictly before the target, like every other input here
        subject, predicate, value = parse_record_text(item.text)
        if item.kind == "thread":
            # A workload thread item is an open promise by construction (tags
            # `(<thread_id>, <subject>, "due:<ordinal>")`). `state.open_threads` selects
            # THREAD records whose value equals `THREAD_OPEN`, so that is the value the
            # promise gets; anything else would fall through into FACTS wearing thread
            # clothes.
            value = state_mod.THREAD_OPEN
        state_records.append(
            lc.StateRecord(
                record_id=item.item_id,
                kind=_RECORD_KINDS[item.kind],
                subject=subject,
                predicate=predicate,
                value=value,
                story_position=lc.StoryPosition(order_key=f"{item.scene_ordinal:04d}"),
                authority=lc.StateAuthority(item.authority),
                confidence=item.confidence,
                pov_visibility=list(item.pov_visibility),
                evidence=[],
            )
        )
        if item.pov_visibility and (
            query.pov_character_id is None or query.pov_character_id not in item.pov_visibility
        ):
            pov_invisible.append(item.item_id)

    summaries = {
        item.scene_id: item.text
        for item in workload.items
        if item.kind == "summary"
        and item.scene_ordinal is not None
        and item.scene_ordinal < target_ordinal
        and item.scene_id
    }
    prose_item_by_scene = {
        item.scene_id: item.item_id
        for item in workload.items
        if item.kind == "exact_prose" and item.scene_id
    }
    summary_item_by_scene = {
        item.scene_id: item.item_id
        for item in workload.items
        if item.kind == "summary" and item.scene_id
    }

    return L0Inputs(
        revision=revision,
        plan_items=plan_items,
        state_records=tuple(state_records),
        summaries=summaries,
        # `assemble`'s only budget step is `available = token_budget - reserved_output`
        # (context.py, first statement of the body). Adding the default reserve back here
        # therefore makes the packet's usable budget exactly `query.token_budget`.
        token_budget=query.token_budget + DEFAULT_RESERVED_OUTPUT,
        reserved_output=DEFAULT_RESERVED_OUTPUT,
        prose_item_by_scene=prose_item_by_scene,
        summary_item_by_scene=summary_item_by_scene,
        target_scene_id=query.scene_id or "",
        prior_scene_ids=tuple(s.scene_id for s in prior_scenes),
        pov_invisible_item_ids=tuple(pov_invisible),
    )


# -- running one query -----------------------------------------------------------------------


@dataclass(frozen=True)
class L0Selection:
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
    item_kind: lc.ContextItemKind, source_logical_id: str, inputs: L0Inputs
) -> str | None:
    """Map a packed item back to a workload id, or None when it is not from the workload.

    The premise (and any locked constraint) is the arm's own scaffolding, never part of the
    answer, so PLAN/AUTHOR_RULE items drop out here rather than surfacing as selections.
    """
    if item_kind in (lc.ContextItemKind.PLAN, lc.ContextItemKind.AUTHOR_RULE):
        return None
    if item_kind is lc.ContextItemKind.EXACT_PROSE:
        return inputs.prose_item_by_scene.get(source_logical_id, source_logical_id)
    if item_kind is lc.ContextItemKind.SUMMARY:
        return inputs.summary_item_by_scene.get(source_logical_id, source_logical_id)
    return source_logical_id  # a state record already carries its workload item id


def _map_omission(source_logical_id: str, inputs: L0Inputs) -> str:
    """Map an omission back to a workload id.

    An omitted thing is by definition not among the packed items, so classification is by
    membership in the side maps: prose omissions carry the scene's logical id, summary
    omissions too (`assemble` records them against the node), and record omissions already
    carry their workload item id.
    """
    if source_logical_id in inputs.prose_item_by_scene:
        return inputs.prose_item_by_scene[source_logical_id]
    if source_logical_id in inputs.summary_item_by_scene:
        return inputs.summary_item_by_scene[source_logical_id]
    return source_logical_id


def run_query(workload: Workload, query: Query) -> L0Selection:
    inputs = build_inputs(workload, query)
    packet = assemble(
        inputs.revision,
        inputs.target_scene_id,
        plan_items=inputs.plan_items,
        state_records=inputs.state_records,
        query_id=query.query_id,
        pov_character_id=query.pov_character_id,
        token_budget=inputs.token_budget,
        reserved_output=inputs.reserved_output,
        summaries=inputs.summaries,
    )

    selected: list[str] = []
    prose_count = summary_count = fact_count = 0
    in_prose: set[str] = set()
    in_summary: set[str] = set()
    for packed in packet.items:
        workload_id = _workload_id_for(packed.kind, packed.source_logical_id, inputs)
        if workload_id is None:
            continue
        selected.append(workload_id)
        if packed.kind is lc.ContextItemKind.EXACT_PROSE:
            prose_count += 1
            in_prose.add(packed.source_logical_id)
        elif packed.kind is lc.ContextItemKind.SUMMARY:
            summary_count += 1
            in_summary.add(packed.source_logical_id)
        else:  # FACT, THREAD, EVENT, HIDDEN — every record form counts into "facts"
            fact_count += 1

    omitted = [(_map_omission(o.source_logical_id, inputs), o.reason) for o in packet.omitted]
    dark = tuple(
        scene_id
        for scene_id in inputs.prior_scene_ids
        if scene_id not in in_prose and scene_id not in in_summary
    )
    tokens_by_section = {
        name: sum(packed.tokens for packed in packed_items)
        for name, packed_items in packet.sections.items()
    }
    return L0Selection(
        query_id=query.query_id,
        selected_ids=tuple(selected),
        omitted=tuple(omitted),
        tokens_by_section=tokens_by_section,
        used_tokens=packet.used_tokens,
        dark_prior_scenes=dark,
        full_prose_count=prose_count,
        summary_count=summary_count,
        fact_count=fact_count,
        pov_invisible_ids_in_inputs=inputs.pov_invisible_item_ids,
    )


# -- main: run every draft_scene query, optionally print the §56.4-style census --------------


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def draft_queries(workload: Workload) -> list[Query]:
    """The queries this arm answers, in scene order. `assemble` drafts; nothing else."""
    return sorted(
        (q for q in workload.queries if q.operation == "draft_scene"),
        key=lambda q: q.scene_ordinal if q.scene_ordinal is not None else -1,
    )


def format_census(rows: list[dict[str, int]]) -> str:
    header = f"{'scenes':>6}   {'full prose':>10}   {'summaries':>9}   {'facts':>5}   {'dark':>5}"
    lines = [header]
    lines.append("-" * len(header))
    for row in rows:
        lines.append(
            f"{row['scenes']:>6}   {row['full_prose']:>10}   {row['summaries']:>9}"
            f"   {row['facts']:>5}   {row['dark']:>5}"
        )
    return "\n".join(lines)


def census_rows(workload: Workload) -> list[dict[str, int]]:
    """One §56.4-shaped row per draft_scene query, in scene order."""
    rows: list[dict[str, int]] = []
    for query in draft_queries(workload):
        selection = run_query(workload, query)
        rows.append(
            {
                "scenes": (query.scene_ordinal or 1) - 1,
                "full_prose": selection.full_prose_count,
                "summaries": selection.summary_count,
                "facts": selection.fact_count,
                "dark": len(selection.dark_prior_scenes),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workload", required=True, type=Path, help="BenchmarkBook JSON file")
    parser.add_argument("--out", type=Path, default=None, help="write the report JSON here")
    parser.add_argument(
        "--census",
        action="store_true",
        help="print a §56.4-style census table over every draft_scene query",
    )
    args = parser.parse_args(argv)

    workload = load_workload(args.workload)
    selections: dict[str, list[str]] = {}
    details: dict[str, dict[str, Any]] = {}
    for query in draft_queries(workload):
        selection = run_query(workload, query)
        selections[query.query_id] = list(selection.selected_ids)
        details[query.query_id] = selection.to_json()

    report = {
        "strategy": "litharness-assemble",
        "selections": selections,
        "details": details,
        "source": {
            "litharness_commit": git_head(),
            "counter": COUNTER_ID,
            "token_budget_default": DEFAULT_TOKEN_BUDGET,
            "reserved_output": DEFAULT_RESERVED_OUTPUT,
        },
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.write_text(rendered + "\n", encoding="utf-8", newline="\n")
    else:
        print(rendered)

    if args.census:
        print(format_census(census_rows(workload)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
