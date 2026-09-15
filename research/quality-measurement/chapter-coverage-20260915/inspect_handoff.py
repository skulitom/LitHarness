"""Deterministic post-run attribution; no generation or literary scoring."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.chapter_coverage import reconcile
from litharness.application.chapter_layout import WritingLayout
from litharness.domain.draft import strip_em_dash, strip_markup
from litharness.domain.nodes import NodeKind
from litharness.domain.scene_brief import SceneBrief

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/chapter-coverage-20260915"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outline_details(call, book, stored, ids):
    result = json.loads(call["result"]["text"])
    row = {"call": call["number"], "chapter_groups": 0}
    if book[0] == "B":
        payload = json.loads(call["request"]["prompt"])
        layout = payload["writing_layout"]
        grouping = WritingLayout(tuple(
            (c["chapter"], tuple(c["scene_ordinals"])) for c in layout["chapters"]
        ), layout["target_scene_words"])
        scenes, coverage = reconcile(result, grouping)
        row.update(valid_chapter_membership=True, chapter_groups=len(coverage))
        row["coverage_items_retained"] = sum(c.to_text(ids) in stored for c in coverage)
    else:
        scenes = result["scenes"]
    return row, {s["ordinal"]: SceneBrief.from_payload(s["brief"]).to_text() for s in scenes}


def inspect():
    state = read(LOCAL / "progress.json")
    if state["status"] == "running":
        raise RuntimeError("No narrative inspection during generation")
    sources = [Path(__file__), LOCAL / "progress.json", HERE / "evidence.json", *(
        ROOT / "src/litharness" / path for path in (
            "application/chapter_coverage.py", "application/chapter_layout.py",
            "domain/draft.py", "domain/scene_brief.py",
        )
    )]
    books = []
    for book in sorted(state["books"]):
        root = LOCAL / "books" / book
        paths = [LOCAL / c["path"] for c in state["calls"] if c["book"] == book]
        sources += paths
        calls = [read(path) for path in paths]
        outlines = [c for c in calls if c["profile"].startswith("planner.outline.")]
        preflight = LOCAL / "preflight" / f"{book}-request.json"
        sources.append(preflight)
        item = {
            "book": book, "outline_calls": len(outlines),
            "first_live_request_equals_preflight": (
                outlines[0]["request"] == read(preflight) if outlines else None
            ),
            "outlines": [], "scenes": [],
        }
        candidates = []
        database = root / "book.db"
        sources.append(database)
        with SqliteStore.open_read_only(database) as store:
            revision = store.plan_revision(f"experience-B{book[1]}", "main")
            stored = {p.text for p in revision.items} if revision else set()
            head = store.head(f"experience-B{book[1]}", "main")
            ids = {index: node.logical_id for index, node in enumerate(
                (n for n in head.nodes if n.kind is NodeKind.SCENE), 1,
            )}
            for call in outlines:
                if call["status"] != "completed":
                    continue
                try:
                    row, mapping = outline_details(call, book, stored, ids)
                except (ValueError, KeyError, TypeError) as error:
                    item["outlines"].append({
                        "call": call["number"], "parse_or_mapping_valid": False,
                        "failure_type": type(error).__name__,
                    })
                    continue
                row["parse_or_mapping_valid"] = True
                candidates.append((call["number"], mapping))
                item["outlines"].append(row)
            for ordinal in range(1, state["books"][book]["accepted"] + 1):
                path = root / "views" / f"chapter{ordinal}.json"
                chapter = root / f"chapter-{ordinal}.md"
                sources += [path, chapter]
                dossier = json.loads(read(path)["output"])
                plan = dossier["job_plan"]["plan_item"]["text"]
                brief = SceneBrief.from_text(plan)
                prompt = dossier["prompt"]
                writers = [c for c in calls if c["request"]["prompt"] == prompt["prompt"]
                           and c["request"]["system"] == prompt["system"]]
                item["scenes"].append({
                    "ordinal": ordinal,
                    "plan_sha256": hashlib.sha256(plan.encode()).hexdigest(),
                    "matching_outline_calls": [n for n, mapping in candidates
                                               if mapping.get(ordinal) == plan],
                    "job_bound_plan_available": dossier["job_plan"]["status"] == "available",
                    "full_scene_brief_in_writer_prompt": bool(brief and brief.render()
                                                              in prompt["prompt"]),
                    "matching_writer_calls": [c["number"] for c in writers],
                    "writer_calls_equal_to_accepted_text_after_strip": [
                        c["number"] for c in writers if c["status"] == "completed"
                        and c["result"]["text"].strip()
                        == chapter.read_text(encoding="utf-8").strip()
                    ],
                    "writer_calls_equal_after_existing_surface_cleanup": [
                        c["number"] for c in writers if c["status"] == "completed"
                        and strip_markup(strip_em_dash(c["result"]["text"])[0])[0].strip()
                        == chapter.read_text(encoding="utf-8").strip()
                    ],
                    "policy_attempts": len(dossier["attempts"]),
                })
        books.append(item)
    output = {"books": books, "source_hashes": {
        p.relative_to(ROOT).as_posix(): sha(p) for p in sources
    }}
    (HERE / "handoff-evidence.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n",
    )
    print(json.dumps(books, indent=2))


if __name__ == "__main__":
    inspect()
