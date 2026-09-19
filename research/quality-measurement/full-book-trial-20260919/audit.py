"""Reconcile recorded execution without producing a literary verdict."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def audit(run):
    from litharness.application.concept import Concept

    base, local, here = run.base, run.LOCAL, run.HERE
    manifest = base.verify_frozen()
    state = base.read(local / "progress.json")
    if state["status"] == "running":
        raise RuntimeError("No reading while generation runs")
    calls, previous, sessions = [], None, set()
    replay = {"started_at": state["started_at"], "calls": []}
    for meta in state["calls"]:
        path = local / meta["path"]
        row = base.read(path)
        result = row.get("result", {})
        raw = result.get("raw", row.get("raw", {})) or {}
        request = row["request"]
        checks = base.transport_details(raw, request, row["book"])
        settings, argv = raw.get("settings", {}), raw.get("argv", [])
        ids = [e.get("thread_id") for e in raw.get("events", [])
               if e.get("type") == "thread.started"]
        checks.update(
            receipt_chain=row["previous_receipt_sha256"] == previous,
            receipt_identity=all(row[k] == meta[k] for k in
                                 ("number", "book", "phase", "profile", "status")),
            completed=row["status"] == "completed",
            admitted=base.admission(replay, row["book"], row["started_at"]) is None,
            usage_recorded=(meta["tokens"] == sum(result.get("usage", {}).values())
                            if row["status"] == "completed" else False),
            prompt=raw.get("prompt") == request["prompt"],
            isolated=all(flag in argv for flag in
                         ("--ephemeral", "--ignore-user-config", "--ignore-rules")),
            no_memory=settings.get("features.memories") is False,
            no_docs=settings.get("project_doc_max_bytes") == 0,
            no_search=settings.get("web_search") == "disabled",
            model=raw.get("requested_model") == "gpt-6-astra",
            effort=settings.get("model_reasoning_effort") == "medium",
            fresh_session=len(ids) == 1 and bool(ids[0]) and ids[0] not in sessions,
        )
        sessions.update(ids)
        previous = base.sha(path)
        replay["calls"].append(meta)
        calls.append({"number": row["number"], "phase": row["phase"],
                      "profile": row["profile"], "receipt_sha256": previous,
                      "request_sha256": base.digest(request), "checks": checks,
                      "usage": result.get("usage"),
                      "usage_unknown": row.get("usage_unknown", False)})
    subprocess.run([str(base.python_for("A")), str(Path(run.__file__)), "collect", "A1"],
                   cwd=run.ROOT, env=base.environment("A1"), check=True)
    root = base.book_root("A1")
    chapters = [{"chapter": int(p.stem.split("-")[-1]), "sha256": base.sha(p),
                 "words": len(p.read_text(encoding="utf-8").split())}
                for p in root.glob("chapter-*.md")]
    chapters.sort(key=lambda item: item["chapter"])
    steps = []
    for path in sorted((local / "steps").glob("*.json")):
        row = base.read(path)
        phase = row["phase"]
        checks = {
            "arguments": row["arguments"] == run.base_args("A1") + run.command("A1", phase),
            "source": Path(row["source"]).is_relative_to(local / "sources/A"),
            "transition": run.transition_error(phase, row["before"], row["after"]) is None,
            "drain_has_work": not phase.startswith("drain") or row["before"]["pending"] > 0,
            "time_order": row["started_at"] <= row["finished_at"],
        }
        steps.append({"key": row["key"], "phase": phase, "sha256": base.sha(path),
                      "returncode": row["returncode"], "checks": checks,
                      "accepted_before": row["before"]["accepted"],
                      "accepted_after": row["after"]["accepted"]})
    retention = {"concept_available": (root / "concept/concept.json").exists()}
    if retention["concept_available"]:
        payload = base.read(root / "concept/concept.json")
        expected = Concept.from_payload(payload).for_outline()
        outlines = [base.read(local / item["path"])["request"] for item in state["calls"]
                    if item["profile"].startswith("planner.outline.")]
        retention.update(
            concept_sha256=base.sha(root / "concept/concept.json"),
            author_brief_retained=payload.get("author_brief") == base.INPUTS["1"]["premise"],
            structured_material_present=bool(payload.get("story_material")),
            outline_calls=len(outlines),
            all_outline_source_projections_match=(all(
                json.loads(item["prompt"])["book_concept"] == expected for item in outlines
            ) if outlines else None),
        )
    views = root / "views"
    verify = base.read(views / "verify.json") if (views / "verify.json").exists() else None
    if verify:
        verify = {"returncode": verify["returncode"], **json.loads(verify["output"])}
    evidence = {
        "schema": "litharness.full-book-trial.v1", "status": state["status"],
        "stop": state.get("stop"), "books": state["books"], "calls": calls,
        "chapters": chapters, "steps": steps, "retention": retention, "verify": verify,
        "known_tokens": sum(c["tokens"] for c in state["calls"]),
        "started_at": state["started_at"], "finished_at": state["finished_at"],
        "frozen_files_verified": len(manifest["files"]),
        "all_transport_controls_pass": (
            bool(calls) and all(all(c["checks"].values()) for c in calls)
        ),
        "all_step_controls_pass": bool(steps) and all(all(s["checks"].values()) for s in steps),
        "extension_boundaries": sorted(int(s["phase"].removeprefix("extend")) for s in steps
                                       if s["phase"].startswith("extend") and not s["returncode"]),
        "registration_sha256": base.sha(here / "registration.json"),
        "original_stop": state.get("original_stop"),
        "continuation_started_at": state.get("continuation_started_at"),
        "continuation": (base.read(here / "continuation.json")
                         if (here / "continuation.json").exists() else None),
        "limitations": ["One first-draw book; no independent replication or quality estimate.",
                        "Structural completion does not establish story closure or fulfillment.",
                        "No qualified reader mechanism or release approval."],
    }
    base.write(here / "evidence.json", evidence)
    run.claim("observed")
    print(json.dumps({"status": state["status"], "chapters": len(chapters),
                      "words": sum(c["words"] for c in chapters), "calls": len(calls),
                      "transport_controls": evidence["all_transport_controls_pass"],
                      "stop": state.get("stop")}))
