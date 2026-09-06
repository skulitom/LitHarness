"""Resume unchanged Codex diagnostics after retaining an unexpected Claude auxiliary call."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
TRIAL = runpy.run_path(str(HERE / "prose_editor_boundary.py"))
read, write_new, sha = (TRIAL[k] for k in ("read", "write_new", "sha"))
SKIP = {"claude-static-1", "claude-static-2", "claude-full-2"}


def recover(raw: dict[str, Any]) -> dict[str, Any]:
    if raw["exit_code"] != 0:
        raise ValueError("cannot recover a failed transport")
    events = [json.loads(line) for line in raw["stdout"].splitlines() if line.strip()]
    results = [e for e in events if e.get("type") == "result"]
    if len(results) != 1:
        raise ValueError("expected one result")
    result = results[0]
    models = result.get("modelUsage", {})
    if set(models) != {TRIAL["CLAUDE_MODEL"], "claude-haiku-4-5-20251001"}:
        raise ValueError("unregistered recovery model set")
    for e in events:
        if e.get("type") == "assistant" and e["message"].get("model") != TRIAL["CLAUDE_MODEL"]:
            raise ValueError("unexpected primary writer")
    # Reuse all original response checks after removing only the audited auxiliary usage row.
    isolated = json.loads(json.dumps(events))
    next(e for e in isolated if e.get("type") == "result")["modelUsage"] = {
        TRIAL["CLAUDE_MODEL"]: models[TRIAL["CLAUDE_MODEL"]]
    }
    parsed = TRIAL["parse_claude"]("\n".join(map(json.dumps, isolated)))
    keys = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "outputTokens")
    if any(type(m.get(k)) is not int or m[k] < 0 for m in models.values() for k in keys):
        raise ValueError("incomplete whole-CLI accounting")
    main = models[TRIAL["CLAUDE_MODEL"]]
    if (
        parsed["usage"]["input_tokens"] != sum(main[k] for k in keys[:3])
        or parsed["usage"]["output_tokens"] != main["outputTokens"]
    ):
        raise ValueError("main-model usage disagrees")
    parsed["usage"] = {
        "input_tokens": sum(m[k] for m in models.values() for k in keys[:3]),
        "cached_input_tokens": sum(m["cacheReadInputTokens"] for m in models.values()),
        "output_tokens": sum(m["outputTokens"] for m in models.values()),
    }
    return {
        "status": "completed",
        **parsed,
        "model_usage": models,
        "containment": "failed: unexpected auxiliary model; offline accounting recovery only",
        "original_result_status": "failed",
    }


def prepare(out: Path) -> None:
    TRIAL["CODEX"]["validate"](out)
    folder = out / "claude-full-1"
    failed = read(folder / "result.json")
    if failed.get("error") != "unexpected or missing resolved Claude model":
        raise ValueError("not the registered recovery case")
    recovered = recover(read(folder / "raw.json"))
    recovered["wall_ms"] = failed["wall_ms"]
    write_new(folder / "recovered.json", recovered)
    (folder / "prose.txt").write_text(recovered["text"] + "\n", encoding="utf-8", newline="\n")
    paths = [
        out / "manifest.json",
        Path(__file__),
        HERE / "prose-editor-boundary/AMENDMENT.md",
        folder / "request.json",
        folder / "raw.json",
        folder / "result.json",
        folder / "recovered.json",
    ]
    write_new(
        out / "resume-manifest.json",
        {
            "files": {str(p): sha(p) for p in paths},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "skipped_calls": sorted(SKIP),
            "maximum_actual_calls": 20,
        },
    )


def run(out: Path) -> None:
    prior: dict[str, Any] = {}
    for name in TRIAL["ORDER"]:
        manifest = TRIAL["CODEX"]["validate"](out)
        resume = read(out / "resume-manifest.json")
        if any(sha(Path(p)) != h for p, h in resume["files"].items()):
            raise ValueError("frozen recovery changed")
        if name in SKIP:
            path = out / f"{name}.skipped.json"
            if not path.exists():
                write_new(path, {"reason": "Claude comparison stopped by registered amendment"})
            continue
        if name == "claude-full-1":
            prior[name] = read(out / name / "recovered.json")
        else:
            prior[name] = TRIAL["complete"](out, name, manifest, prior)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.phase == "prepare" else run)(args.out.resolve())


if __name__ == "__main__":
    main()
