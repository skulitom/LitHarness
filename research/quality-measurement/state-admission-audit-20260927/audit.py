"""Executable counterexamples to the ecological state constructor's admission claim.

These are project-authored engineering fixtures, not a reader experiment or a prose sample.
The Boolean state enumeration is independent of the manuscript annotations being audited.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
from pathlib import Path

import litharness_contracts as lc

from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import Revision, build_revision, node_version_id
from litharness.domain.salience import (
    OPPOSITES,
    EcologicalItem,
    EvidenceCensus,
    build_state_continuity_items,
    ecological_manifest,
    evidence_census,
    public_battery,
)
from litharness.domain.serials import SerialShape
from litharness.domain.text import content_hash

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Fixture:
    revision: Revision
    census: EvidenceCensus
    item: EcologicalItem
    anchor: str
    bridge: str


def fixture(
    value: str = "locked", *, renderer: int = 0, same_scene: bool = False,
    uppercase: bool = False,
) -> Fixture:
    """Construct exact accepted spans; no model supplies an admission label."""
    rendered = value.upper() if uppercase else value
    if renderer == 0:
        anchor = f"At dawn, the marker was {rendered}."
        target = f"At dusk, the marker was {rendered}."
    elif renderer == 1:
        anchor = f"The first inspection found the marker {rendered}."
        target = f"The final inspection found the marker {rendered}."
    else:
        raise ValueError("unknown fixture renderer")
    bridge = "The marker did not change between those inspections."
    texts = [f"{anchor} {bridge} {target}"] if same_scene else [anchor, bridge, target]
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="000")]
    nodes.extend(
        Node.text_node(
            f"scene-{index}", NodeKind.SCENE, f"{index:03}", text,
            parent_logical_id="book",
        )
        for index, text in enumerate(texts, 1)
    )
    revision = build_revision(
        f"admission-fixture-{value}-{renderer}-{same_scene}-{uppercase}", "main", tuple(nodes),
    )
    records = []
    for index, (logical_id, quote) in enumerate(
        (("scene-1", anchor), (f"scene-{len(texts)}", target)), 1,
    ):
        node = revision.node(logical_id)
        start = (node.content or "").index(quote)
        records.append(lc.StateRecord(
            record_id=f"state-{index}", kind=lc.StateRecordKind.EVENT,
            subject="marker", predicate="state", value=value,
            authority=lc.StateAuthority.ACCEPTED_CANON,
            story_position=lc.StoryPosition(order_key=f"s{index:06}"),
            evidence=[lc.EvidenceSpan(
                source=lc.ResourceRef(
                    project_id="admission-audit", book_id=revision.book_id,
                    branch_id=revision.branch_id, logical_id=logical_id,
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE, version_id=node_version_id(node),
                ),
                start=start, end=start + len(quote), content_sha256=content_hash(quote),
            )],
        ))
    census = evidence_census(revision, records, (), shape=SerialShape(1, 3))
    items = build_state_continuity_items(census, revision)
    if len(items) != 1:
        raise AssertionError("the diagnostic expects one constructible state pair")
    return Fixture(revision, census, items[0], anchor, bridge)


def state_paths(*, changed_target: bool, require_persistence: bool) -> tuple[tuple[int, ...], ...]:
    """All models of the two assertions; 0/1 denote a declared binary opposition."""
    return tuple(
        path for path in product((0, 1), repeat=3)
        if path[0] == 0 and path[-1] == int(changed_target)
        and (not require_persistence or len(set(path)) == 1)
    )


def case_only_prediction(text: str) -> str:
    """A fixed edited-packet shortcut; no annotation, anchor or paired text is read."""
    return "sham" if re.search(r"\b[A-Z]{2,}\b", text) else "damaged"


def _observations(source: Fixture) -> dict[str, object]:
    item = source.item
    public = public_battery((item,))["items"][0]["variants"]

    def upper_count(text: str) -> int:
        return sum(character.isupper() for character in text)

    return {
        "item_id": item.item_id,
        "source_revision_id": source.revision.revision_id,
        "source_digest": content_hash("\n".join(
            node.content or "" for node in source.revision.nodes
        )),
        "packet_digests": sorted(content_hash(packet["text"]) for packet in public),
        "packet_count": len(public),
        "packets_with_anchor": sum(source.anchor in packet["text"] for packet in public),
        "packets_with_interval": sum(source.bridge in packet["text"] for packet in public),
        "six_field_fingerprints_match": item.damage_fingerprint == item.sham_fingerprint,
        "damage_character_delta": len(item.damaged_text) - len(item.clean_text),
        "sham_character_delta": len(item.sham_text) - len(item.clean_text),
        "damage_uppercase_delta": upper_count(item.damaged_text) - upper_count(item.clean_text),
        "sham_uppercase_delta": upper_count(item.sham_text) - upper_count(item.clean_text),
        "case_shortcut_correct": sum((
            case_only_prediction(item.damaged_text) == "damaged",
            case_only_prediction(item.sham_text) == "sham",
        )),
        "case_shortcut_total": 2,
        "manifest_eligible": ecological_manifest(source.census, (item,))["eligible_for_model_run"],
    }


def report() -> dict[str, object]:
    ordinary = [
        _observations(fixture(value, renderer=renderer))
        for value in sorted(OPPOSITES) for renderer in (0, 1)
    ]
    uppercase_control = _observations(fixture(uppercase=True))
    same_scene_control = _observations(fixture(same_scene=True))
    paths = {
        f"{'damaged' if damaged else 'clean'}_{'with' if frame else 'without'}_persistence": {
            "consistent_paths": [list(path) for path in state_paths(
                changed_target=damaged, require_persistence=frame,
            )],
        }
        for damaged in (False, True) for frame in (False, True)
    }
    sources = [
        HERE / "audit.py", HERE / "RUNBOOK.md",
        *sorted((ROOT / "src/litharness/domain").glob("*.py")),
        ROOT / "uv.lock",
    ]
    return {
        "schema": "litharness.state-admission-audit.v1",
        "scope": "deterministic construction counterexamples; no ecological accuracy claim",
        "implementation": "binary-substitution.case-sham.v1",
        "model_calls": 0,
        "database_reads": 0,
        "source_digests": {
            path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "ordinary_case_fixtures": ordinary,
        "same_scene_context_positive_control": same_scene_control,
        "uppercase_source_shortcut_destructive_control": uppercase_control,
        "binary_relation_models": paths,
        "decision": "CONSTRUCTION_DOES_NOT_ESTABLISH_SEMANTIC_ADMISSION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    payload = json.dumps(report(), indent=2, sort_keys=True) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
