"""Audit actual provider schema behavior without changing the frozen experiment runner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("experience_recovery_audit_driver", HERE / "run.py")
assert SPEC is not None and SPEC.loader is not None
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)


def schema_controls(raw, requested):
    from litharness.providers.codex_schema import prepare_codex_schema

    native, reason, variant = None, None, None
    if requested is not None:
        try:
            native = prepare_codex_schema(requested)
        except ValueError as error:
            reason = str(error)
        variant = ("strict-nullable-optionals.v1" if native is not None
                   else "prompt-only-original.v1")
    return {
        "original_schema": raw.get("schema") == requested,
        "native_schema": raw.get("native_schema") == native,
        "native_schema_reason": raw.get("native_schema_omission_reason") == reason,
        "schema_variant": raw.get("schema_variant") == variant,
        "native_schema_argument": (("--output-schema" in raw.get("argv", []))
                                   == (native is not None)),
    }


def audit():
    if DRIVER.read(DRIVER.LOCAL / "progress.json")["status"] == "running":
        raise RuntimeError("No reading or audit until dispatch stops")
    DRIVER.configure()
    base = DRIVER.BASE
    base.verify_frozen()
    controls, outputs, sessions, reading = {}, [], [], []
    for name in base.ORDER:
        path = base.LOCAL / f"calls/{name}.json"
        if not path.exists():
            outputs.append({"name": name, "status": "not_reached"})
            continue
        row = base.read(path)
        request, lineage = base.slot_request(name)
        entry = {"name": name, "status": row["status"], "receipt_sha256": base.sha(path),
                 "lineage": lineage, "phase": row.get("phase", "inherited")}
        controls[name] = {"lineage": lineage == row["lineage"]}
        if row["status"] == "skipped":
            controls[name]["invalid_parent"] = request is None
        elif row["status"] == "completed":
            result, raw = row["result"], row["result"]["raw"]
            prepared = base.read(base.LOCAL / f"requests/{name}.json")
            controls[name].update({
                "renderer": prepared == base.serial(request) == row["request"],
                "request_hash": row["request_sha256"] == base.sha(
                    base.LOCAL / f"requests/{name}.json"),
                "captured_prompt": raw["prompt"] == request.prompt,
                "captured_system": raw["system"] == request.effective_system,
                "returncode": raw["returncode"] == 0,
                "requested_model": raw["requested_model"] == "gpt-6-astra",
                "effort": raw["settings"]["model_reasoning_effort"] == "medium",
                "ephemeral": "--ephemeral" in raw["argv"],
                "config_off": "--ignore-user-config" in raw["argv"],
                "rules_off": "--ignore-rules" in raw["argv"],
                "docs_off": "project_doc_max_bytes=0" in raw["argv"],
                "memory_off": "features.memories=false" in raw["argv"],
                "no_tools_allowed": not request.allowed_tools,
                "completion_mode": raw["mode"] == "completion",
                **schema_controls(raw, request.schema),
            })
            ids = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
            sessions.extend(ids)
            entry["valid"] = base.conforms(name.split("-")[0], result["parsed"])
            entry.update(usage=result["usage"], session_ids=ids,
                         started_at=row["started_at"], finished_at=row["finished_at"])
            payload = result["parsed"]
            text = (payload["story"] if name.startswith("draft-") and entry["valid"]
                    else result["text"] if payload is None
                    else json.dumps(payload, ensure_ascii=False, indent=2))
            entry["rendered_words"] = len(text.split())
            entry["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
            if isinstance(payload, dict):
                entry["field_words"] = {k: len(v.split()) for k, v in payload.items()
                                        if isinstance(v, str)}
            copy = base.LOCAL / f"reading/{name}.md"
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(text + "\n", encoding="utf-8", newline="\n")
            reading.append(f"- [{name}](reading/{name}.md)")
        outputs.append(entry)
    completed = sum(o["status"] == "completed" for o in outputs)
    controls["sessions"] = {"distinct_completed": len(sessions) == len(set(sessions)) == completed}
    controls["seeds"] = {"distinct": len({base.inputs(i)[1].brief for i in base.BRIEFS}) == 6}
    progress = base.read(base.LOCAL / "progress.json")
    evidence = {
        "registration_sha256": base.sha(HERE / "registration.json"),
        "outputs": outputs, "controls": controls,
        "all_controls_pass": all(all(v.values()) for v in controls.values()), "progress": progress,
        "audit_correction": {
            "identifier": "provider-dynamic-schema-fallback.v1",
            "auditor_sha256": base.sha(Path(__file__)),
            "amendment_sha256": base.sha(HERE / "AUDIT_AMENDMENT.md"),
            "original_failure_sha256": base.sha(base.LOCAL / "audit-original-failure.log"),
        },
        "shutdown_recovery": {
            "inherited_complete": 56, "prior_attempts": 57,
            "interrupted_slot": DRIVER.INTERRUPTED, "interrupted_usage": "unknown",
            "new_attempts": progress["attempts"], "total_attempts": 57 + progress["attempts"],
            "original_registration_sha256": base.sha(DRIVER.PRIOR / "registration.json"),
            "original_interrupted_receipt_sha256": base.sha(
                DRIVER.ORIGINAL / f"calls/{DRIVER.INTERRUPTED}.json"),
        },
    }
    base.write(HERE / "evidence.json", evidence)
    (base.LOCAL / "READING.md").write_text(
        "# All reached outputs\n\n" + "\n".join(reading) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"completed": completed, "controls_pass": evidence["all_controls_pass"],
                      "run_status": progress["status"],
                      "total_attempts": 57 + progress["attempts"]}))
    if not evidence["all_controls_pass"]:
        raise RuntimeError("Audit failed; preserve outputs")


if __name__ == "__main__":
    audit()
