"""Post-observation, lossless byte-layout measurements on the preceding continuation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def compact(text):
    """Preserve non-JSON output and every JSON value; change serialization only."""
    try:
        value = json.loads(text)
    except ValueError:
        return text
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    assert json.loads(rendered) == value
    return rendered


def columnar(payload):
    """Share keys only when all record objects have the same key set."""
    records = payload["records"]
    if not records:
        return payload
    fields = list(records[0])
    if not all(set(record) == set(fields) for record in records):
        raise ValueError("Unequal key sets must not turn absent fields into null values")
    packed = {**payload, "records": {
        "columns": fields, "rows": [[record[field] for field in fields] for record in records],
    }}
    restored = {**packed, "records": [dict(zip(fields, row, strict=True))
                                      for row in packed["records"]["rows"]]}
    assert restored == payload
    return packed


def main():
    sources, by_command = [], {}
    queries = {"replies": 0, "records": 0, "original_utf8_bytes": 0,
               "canonical_object_utf8_bytes": 0, "columnar_utf8_bytes": 0, "round_trips": 0}
    for path in sorted((ROOT / "runs/next-priorities-20260913/continuation/calls").glob("*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if not row["request"]["profile"].startswith("architect.grow"):
            continue
        sources.append({"path": path.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for line in row["result"]["raw"]["commands_jsonl"].splitlines():
            command = json.loads(line)
            if command.get("phase") != "result":
                continue
            args = command.get("arguments", [])
            if isinstance(args, dict):
                args = args.get("arguments", [])
            verb = " ".join(args[:2])
            raw = command.get("stdout", "")
            rendered = compact(raw)
            counts = by_command.setdefault(verb, {"replies": 0, "before_bytes": 0,
                                                   "after_bytes": 0})
            counts["replies"] += 1
            counts["before_bytes"] += len(raw.encode("utf-8"))
            counts["after_bytes"] += len(rendered.encode("utf-8"))
            if verb != "world query":
                continue
            payload = json.loads(raw)
            packed = json.dumps(columnar(payload), ensure_ascii=False, separators=(",", ":"))
            queries["replies"] += 1
            queries["records"] += len(payload["records"])
            queries["round_trips"] += 1
            queries["original_utf8_bytes"] += len(raw.encode("utf-8"))
            queries["canonical_object_utf8_bytes"] += len(rendered.encode("utf-8"))
            queries["columnar_utf8_bytes"] += len(packed.encode("utf-8"))
    if not sources or not queries["replies"]:
        raise RuntimeError("The retained continuation query cohort is unavailable")
    result = {"design_timing": "post-observation; not part of the five registered model cells",
              "model_calls": 0, "source_receipts": sources,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "by_command": by_command, "queries": queries,
              "limitation": "Byte-only prototypes; no model behavior, native token, latency or "
                            "monetary savings measured. No production output was changed."}
    path = HERE / "payload-probe.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(queries, indent=2))


if __name__ == "__main__":
    main()
