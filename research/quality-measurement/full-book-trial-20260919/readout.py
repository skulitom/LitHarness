"""Post-run diagnostics; never changes the frozen run or supplies production feedback."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("readout_recovery", HERE / "recover.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
base, LOCAL = recovery.base, recovery.LOCAL


def bridge_check(raw, request, executable):
    from litharness.providers.codex_tools import _allowances, _validate_arguments

    observed = []
    for line in raw.get("commands_jsonl", "").splitlines():
        row = json.loads(line)
        if row["phase"] != "result" or row.get("argv") is None:
            continue
        try:
            expected = [str(executable), "-m", "litharness",
                        *_validate_arguments(row["arguments"],
                                             _allowances(request["allowed_tools"]))]
        except ValueError:
            return False, observed
        observed.append(row["argv"][0])
        if row["argv"] != expected:
            return False, observed
    return True, observed


def collect():
    import litharness
    from litharness import cli
    from litharness.mcp_server import Binding, make_tools

    base.lock()
    if not Path(litharness.__file__).is_relative_to(recovery.SOURCE):
        raise RuntimeError("Readout must use the frozen recovery interpreter")
    manifest = base.verify_frozen()
    state = base.read(LOCAL / "progress.json")
    if state["status"] == "running":
        raise RuntimeError("Wait for generation to stop")
    destination = LOCAL / "readout-frozen"
    if destination.exists():
        raise RuntimeError("Readout already exists; do not overwrite its source snapshot")
    destination.mkdir()
    database = base.book_root("A1") / "book.db"
    # Include committed WAL state without opening the original writable.
    before = base.sha(database)
    copy = destination / "book.db"
    with (contextlib.closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as origin,
          contextlib.closing(sqlite3.connect(copy)) as target):
        origin.backup(target)
    t = make_tools(Binding(copy, copy, "read", "full-book-final-readout"))
    info, book = t["store_info"](), t["book"]()
    base.write(destination / "store-info.json", info)
    base.write(destination / "book.json", book)
    chapters = []
    for n in range(1, state["books"]["A1"]["accepted"] + 1):
        why = t["why"](scene=str(n), include_prompt=False)
        trace = t["scene_trace"](scene=str(n))
        base.write(destination / f"trace-{n}.json", trace)
        stages = trace["stages"]
        different = stages["accepted"]["metadata"]["differs_from_raw_draft"]
        for stage in ("raw_draft", "pre_revision_draft") if different else ():
            if not stages[stage]["available"]:
                continue
            offset, pages = 0, []
            while True:
                view = t["scene_trace"](scene=str(n), stage=stage, offset=offset, max_chars=20000)
                pages.append(view["excerpt"])
                offset = view["excerpt"]["next_offset"]
                if offset is None:
                    break
            base.write(destination / f"{stage}-{n}.json", pages)
        context = why.get("context") or {}
        chapters.append({
            "chapter": n, "logical_id": why["logical_id"],
            "decision_id": why["decision"]["decision_id"], "job": why["job"],
            "attempts": len(why["attempts"]), "context_tokens": context.get("tokens"),
            "context_budget": context.get("budget"),
            "omitted_items": len(why.get("context_omitted") or []),
            "trace_sha256": base.sha(destination / f"trace-{n}.json"),
            "raw_differs_from_accepted": different,
            "stage_absences": trace["absent"],
            "job_plan_status": why["job_plan"]["status"],
            "job_plan_prompt_equivalence": why["job_plan"]["prompt_equivalence_verified"],
        })
    frozen_evidence = base.read(HERE / "evidence.json")
    corrected = []
    for c in frozen_evidence["calls"]:
        row = base.read(LOCAL / state["calls"][c["number"] - 1]["path"])
        runtime = "A" if c["number"] <= 41 else "A-recovery"
        executable = LOCAL / "runtimes" / runtime / "Scripts/python.exe"
        if manifest["files"].get(str(executable)) != base.sha(executable):
            raise RuntimeError("Executable not frozen at registration")
        raw = row.get("result", {}).get("raw", row.get("raw", {})) or {}
        passed, observed = bridge_check(raw, row["request"], executable)
        checks = dict(c["checks"], bridge_source_and_scope=passed)
        corrected.append({"number": c["number"], "phase": c["phase"],
                          "expected_runtime": runtime, "bridge_checked_commands": len(observed),
                          "checks": checks})
    os.environ["LITHARNESS_ENV"] = "test"
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = cli.main(["--database", str(copy), "--chapter-scenes", "1", "--arc-chapters", "6",
                         "--volume-chapters", "24", "reader-evidence-audit",
                         "--out", str(destination / "reader-audit"), "--json"])
    (destination / "reader-audit.log").write_text(output.getvalue(), encoding="utf-8")
    if code:
        raise RuntimeError("Reader evidence inventory failed")
    reader = base.read(destination / "reader-audit/evidence-audit.json")
    if base.sha(database) != before:
        raise RuntimeError("Original book changed during readout")
    result = {
        "schema": "litharness.full-book-readout.v1", "model_calls": 0,
        "method": "Post-run read-only diagnostics, not a preregistered reader experiment.",
        "script_sha256": base.sha(Path(__file__)), "source_database_sha256": before,
        "snapshot_sha256": base.sha(copy), "runtime_source": str(litharness.__file__),
        "source_unchanged": True, "frozen_audit_sha256": base.sha(HERE / "evidence.json"),
        "auditor_correction": "Frozen auditor expected runtimes/A for all calls. "
        "Use the exact registered A-recovery executable after call 41; all other checks retained.",
        "transport_calls": corrected,
        "all_transport_controls_pass_with_registered_runtime": all(
            all(c["checks"].values()) for c in corrected),
        "chapters": chapters, "reader_admission": reader,
        "reader_artifacts": {name: base.sha(destination / "reader-audit" / name)
                             for name in ("evidence-audit.json", "battery.public.json",
                                          "battery.private.json")},
        "limitations": ["One book, with explicit interruptions and mixed production revisions.",
                        "No quality estimate, qualified reader or release approval."],
    }
    base.write(HERE / "readout.json", result)
    print(json.dumps({"transport_controls": result[
        "all_transport_controls_pass_with_registered_runtime"],
        "omitted_items": sum(c["omitted_items"] for c in chapters),
        "changed_drafts": [c["chapter"] for c in chapters if c["raw_differs_from_accepted"]],
        "reader_census": reader["census"],
        "reader_eligible": reader["ecological_manifest"]["eligible_for_model_run"]}))


if __name__ == "__main__":
    collect()
