"""Cross one local character objective with fixed chapter rules; subscription research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
BASE = runpy.run_path(str(HERE / "prose_narration_obligations.py"))
CODEX, PATCH = BASE["CODEX"], BASE["PATCH"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-conflicting-objectives/PREREG.md"
ORDER = CODEX["ORDER"]
SYSTEM = (
    BASE["SYSTEM"]
    + """
The local interaction assignment is also binding. Within its scope you may develop immediate
gestures, brief dialogue and responses consistent with all recorded actions and their order.
This permission does not license additional incidents, knowledge, backstory or resolution.
Render another character's intention only through what the viewpoint character can observe
or infer at that time. The assigned objective must be discernible in the local interaction."""
)


def compose(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {"chapter_source", "interaction"}:
        raise ValueError("malformed objective source")
    interaction = source["interaction"]
    if (
        not isinstance(interaction, dict)
        or set(interaction) != {"scope", "shared", "objectives"}
        or not isinstance(interaction["scope"], list)
        or not interaction["scope"]
        or len(set(interaction["scope"])) != len(interaction["scope"])
        or not isinstance(interaction["shared"], str)
        or not interaction["shared"].strip()
        or not isinstance(interaction["objectives"], dict)
        or set(interaction["objectives"]) != {"full", "focused"}
        or any(not isinstance(v, str) or not v.strip() for v in interaction["objectives"].values())
        or interaction["objectives"]["full"] == interaction["objectives"]["focused"]
    ):
        raise ValueError("invalid interaction assignment")
    original = BASE["compose"](source["chapter_source"])["full"]
    payload = json.loads(original["prompt"].split("\n", 1)[1])
    if any(i not in payload["required_narration"] for i in interaction["scope"]):
        raise ValueError("unknown interaction scope")
    return {
        condition: {
            "system": SYSTEM,
            "prompt": "Story source and narration assignment:\n"
            + json.dumps(
                {
                    **payload,
                    "local_interaction": {
                        "scope": interaction["scope"],
                        "shared": interaction["shared"],
                        "objective": interaction["objectives"][condition],
                    },
                },
                ensure_ascii=False,
            ),
        }
        for condition in ("full", "focused")
    }


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    requests = compose(source)
    prefix = CODEX["command_prefix"]()
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=CODEX["subscription_env"](),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("ChatGPT subscription required")
    out.mkdir(parents=True, exist_ok=False)
    (out / "work").mkdir()
    (out / "system.txt").write_text(SYSTEM, encoding="utf-8", newline="\n")
    paths = [
        Path(__file__),
        HERE / "prose_narration_obligations.py",
        HERE / "prose_protected_reconstruction.py",
        HERE / "prose_codex.py",
        HERE / "prose_paragraph_revision.py",
        REGISTRATION,
        REGISTRATION.with_name("RUNBOOK.md"),
        source_path,
        source_path.with_name("source-review.md"),
        source_path.with_name("prepare_source.py"),
        Path(prefix[1]),
        out / "system.txt",
    ]
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "requests": requests,
            "prefix": prefix,
            "order": ORDER,
            "condition_labels": {
                "full": "aligned goal, fear impedes action",
                "focused": "conflicting goal",
            },
            "files": {str(p): sha(p) for p in paths},
            "token_stop": BASE["BASE"]["TOKEN_STOP"],
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
        },
    )


def run(out: Path) -> None:
    for name in ORDER:
        manifest = CODEX["validate"](out)
        if manifest["requests"] != compose(manifest["source"]):
            raise ValueError("frozen requests changed")
        BASE["BASE"]["quota"](out)
        result = CODEX["complete_once"](out, name, manifest)
        path = out / f"{name}.inspection.json"
        if path.exists():
            continue
        chapter = manifest["source"]["chapter_source"]["chapter"]
        expected = PATCH["literal_sequence"](chapter["text"], chapter["verbatim"])
        actual = PATCH["literal_sequence"](result["text"], chapter["verbatim"])
        write_new(
            path,
            {
                "literal_sequence_matches": actual == expected,
                "expected_literal_occurrences": len(expected),
                "actual_literal_occurrences": len(actual),
                "source_manifest_sha256": sha(out / "manifest.json"),
                "result_sha256": sha(out / f"{name}.result.json"),
                "semantic_status": "unassessed; literal checks do not establish meaning",
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(args.out.resolve(), args.source.resolve())
    else:
        run(args.out.resolve())


if __name__ == "__main__":
    main()
