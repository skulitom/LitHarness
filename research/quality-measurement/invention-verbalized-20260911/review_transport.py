"""Post-observation supplement: compare captured system with the frozen effective renderer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from run import HERE, LOCAL, ROOT, imports, read, sha, write

sys.path.insert(0, str(ROOT))
from tools.generation_trace import load_trace


def main() -> None:
    if read(LOCAL / "progress.json")["status"] != "finished":
        raise RuntimeError("Review requires a finished run")
    _, _, request_type, _ = imports()
    from litharness.providers.codex_schema import prepare_codex_schema
    rows = {}
    for path in sorted((LOCAL / "calls").glob("*.json")):
        row = read(path)
        request = request_type(**row["request"])
        trace = load_trace(path)
        captured = trace.fields["transport.system"]
        rows[path.stem] = {
            "receipt_sha256": sha(path),
            "raw_system_equal": captured == request.system,
            "effective_system_equal": captured == request.effective_system,
            "prompt_equal": trace.fields["transport.prompt"] == request.prompt,
            "native_schema_equal": json.loads(trace.fields["transport.schema"])
            == prepare_codex_schema(request.schema),
            "extra_instruction_negative_control_rejected":
            captured + "\nUNREGISTERED_EXTRA_INSTRUCTION" != request.effective_system,
        }
    write(HERE / "transport-review.json", {
        "post_observation": True, "reviewer_sha256": sha(Path(__file__)),
        "original_audit_sha256": sha(HERE / "audit.py"),
        "original_evidence_sha256": sha(HERE / "evidence.json"),
        "explanation": (
            "The registered raw-system equality omitted CompletionRequest.effective_system's "
            "schema instruction. Original failed flags remain unchanged."
        ),
        "calls": rows,
    })
    print({name: {k: v for k, v in row.items() if k != "receipt_sha256"}
           for name, row in rows.items()})


if __name__ == "__main__":
    main()
