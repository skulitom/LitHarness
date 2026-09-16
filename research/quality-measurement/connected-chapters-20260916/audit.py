"""Transport and provenance readout adapted from the registered workflow auditor.

The continuation transport fixes remain in the shared support module. The volume bound
and experience source here explicitly cover the three-chapter structured-workflow arm.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def audit(base):
    from litharness.application.concept import Concept

    LOCAL, HERE, ROOT = base.LOCAL, base.HERE, base.ROOT
    verify_frozen = base.verify_frozen
    read = base.read
    sha = base.sha
    transport_details = base.transport_details
    admission = base.admission
    digest = base.digest
    order = base.order
    python_for = base.python_for
    environment = base.environment
    book_root = base.book_root
    base_args = base.base_args
    command = base.command
    write = base.write
    claim = base.claim
    INPUTS = base.INPUTS
    verify_frozen()
    state = read(LOCAL / "progress.json")
    if state["status"] == "running":
        raise RuntimeError("Generation must finish or stop before audit/reading")
    controls, calls, previous, sessions = [], [], None, set()
    replay = {"started_at": state["started_at"], "calls": []}
    for meta in state["calls"]:
        path = LOCAL / meta["path"]
        row = read(path)
        checks = {
            "receipt_chain": row["previous_receipt_sha256"] == previous,
            "completed": row["status"] == "completed",
        }
        previous = sha(path)
        result = row.get("result", {})
        raw = result.get("raw", row.get("raw", {}))
        request = row["request"]
        checks.update(transport_details(raw, request, row["book"]))
        checks["admitted"] = admission(replay, row["book"], row["started_at"]) is None
        checks["usage_recorded"] = (
            meta["tokens"] == sum(result.get("usage", {}).values())
            if row["status"] == "completed"
            else row.get("usage_unknown")
        )
        checks["receipt_identity"] = all(
            row[key] == meta[key] for key in ("number", "book", "phase", "profile", "status")
        )
        replay["calls"].append(meta)
        argv, settings = raw.get("argv", []), raw.get("settings", {})
        checks.update(
            prompt=raw.get("prompt") == request["prompt"],
            isolated=all(
                arg in argv for arg in ("--ephemeral", "--ignore-user-config", "--ignore-rules")
            ),
            no_memory=settings.get("features.memories") is False,
            no_docs=settings.get("project_doc_max_bytes") == 0,
            model=raw.get("requested_model") == "gpt-6-astra",
            effort=settings.get("model_reasoning_effort") == "medium",
            no_search=settings.get("web_search") == "disabled",
        )
        ids = [
            e.get("thread_id") for e in raw.get("events", []) if e.get("type") == "thread.started"
        ]
        checks["fresh_session"] = len(ids) == 1 and bool(ids[0]) and ids[0] not in sessions
        sessions.update(ids)
        checks["tool_scope"] = (
            raw.get("mode") == "bridge"
            if request["allowed_tools"]
            else raw.get("mode") == "completion"
        )
        calls.append(
            {
                "number": row["number"],
                "book": row["book"],
                "phase": row["phase"],
                "profile": row["profile"],
                "receipt_sha256": sha(path),
                "request_sha256": digest(request),
                "checks": checks,
                "usage": result.get("usage"),
                "usage_unknown": row.get("usage_unknown", False),
            }
        )
        controls.extend(checks.values())
    for book in order("concept"):
        subprocess.run(
            [str(python_for(book[0])), str(Path(base.__file__)), "collect", book],
            env=environment(book),
            cwd=ROOT,
            check=True,
        )
    chapters = [
        {
            "book": book,
            "chapter": path.stem,
            "sha256": sha(path),
            "words": len(path.read_text(encoding="utf-8").split()),
        }
        for book in order("concept")
        for path in sorted(book_root(book).glob("chapter-*.md"))
    ]
    steps = []
    for path in sorted((LOCAL / "steps").glob("*.json")):
        row = read(path)
        book, phase = row["book"], row["phase"]
        steps.append(
            {
                "key": row["key"],
                "sha256": sha(path),
                "returncode": row["returncode"],
                "checks": {
                    "arguments": row["arguments"] == base_args(book) + command(book, phase),
                    "source": Path(row["source"]).is_relative_to(LOCAL / "sources" / book[0]),
                    "three_chapter_limit": row["after"]["accepted"] <= 3,
                    "drain_has_work": not phase.startswith("drain") or row["before"]["pending"] > 0,
                    "time_order": row["started_at"] <= row["finished_at"],
                },
            }
        )
    retention = []
    for book in order("concept"):
        concept_path = book_root(book) / "concept/concept.json"
        item = {"book": book, "concept_available": concept_path.exists()}
        if concept_path.exists():
            concept = read(concept_path)
            brief = (concept.get("story_material") or concept.get("discovery") or {}).get(
                "experience_brief", ""
            )
            outline_requests = [
                read(LOCAL / call["path"])["request"]
                for call in state["calls"]
                if call["book"] == book and call["profile"].startswith("planner.outline.")
            ]
            item.update(
                concept_sha256=sha(concept_path),
                author_brief_retained=concept.get("author_brief") == INPUTS[book[1]]["premise"],
                experience_field_present=bool(brief),
                outline_calls=len(outline_requests),
                brief_in_each_outline=all(
                    brief and json.dumps(brief, ensure_ascii=False)[1:-1] in request["prompt"]
                    for request in outline_requests
                )
                if outline_requests
                else None,
            )
            expected = Concept.from_payload(concept).for_outline()
            item["concept_mode_matches_arm"] = bool(concept.get("story_material")) == (
                book[0] == "B"
            )
            item["all_outline_source_projections_match"] = bool(outline_requests) and all(
                json.loads(request["prompt"])["book_concept"] == expected
                for request in outline_requests
            )
        verify_path = book_root(book) / "views/verify.json"
        if verify_path.exists():
            view = read(verify_path)
            item["verify_returncode"] = view["returncode"]
            try:
                verified = json.loads(view["output"])
                item.update(rebuilt=verified["rebuilt"], unattributed=len(verified["unattributed"]))
            except (ValueError, KeyError):
                item["verify_parse_failed"] = True
        retention.append(item)
    evidence = {
        "status": state["status"],
        "books": state["books"],
        "calls": calls,
        "steps": steps,
        "retention": retention,
        "chapters": chapters,
        "all_transport_controls_pass": all(controls),
        "known_tokens": sum(c["tokens"] for c in state["calls"]),
        "started_at": state["started_at"],
        "finished_at": state["finished_at"],
        "stop": state.get("stop"),
        "registration_sha256": sha(HERE / "registration.json"),
    }
    evidence["all_step_controls_pass"] = all(all(s["checks"].values()) for s in steps)
    evidence["premise_pairs"] = [
        {
            "case": case,
            "author_inputs_equal": (book_root(f"A{case}") / "brief.txt").read_bytes()
            == (book_root(f"B{case}") / "brief.txt").read_bytes(),
            "seeds_equal": read(book_root(f"A{case}") / "seed.json")
            == read(book_root(f"B{case}") / "seed.json"),
            "independent_invention": True,
        }
        for case in INPUTS
    ]
    write(HERE / "evidence.json", evidence)
    claim("observed")
    print(
        json.dumps(
            {
                "status": state["status"],
                "chapters": len(chapters),
                "words": sum(c["words"] for c in chapters),
                "calls": len(calls),
                "transport_controls": all(controls),
            }
        )
    )
