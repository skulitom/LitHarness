"""Reconstruct from protected facts, crossing exposure to the old prose; research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
CODEX = runpy.run_path(str(HERE / "prose_codex.py"))
PATCH = runpy.run_path(str(HERE / "prose_paragraph_revision.py"))
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-protected-reconstruction/PREREG.md"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
TOKEN_STOP = 90_000
SYSTEM = """Write the complete chapter as novel prose from the required story record. Preserve
the recorded events, causal and temporal relationships, consequential quantities, viewpoint
knowledge, unresolved ambiguities and endpoint. Use close third person, past tense. The wording
and paragraph organization are yours; the record is not a paragraph outline. Its facts need
to be conveyed, but need not be separately explained after being shown. Preserve the supplied
literal sequence exactly, including repeated occurrences; an inline literal may stay inline.
Keep the indicated scene division. No word target, compression quota, required comparisons or
prescribed opening sentence. Do not add incidents, backstory, named characters, quantities,
rules or revelations. If reference prose is supplied, its unprotected incidental information
and phrasing are optional; omit or defer them when unnecessary. The required record takes
precedence. Return only the complete prose, without commentary, a title, a patch list or a score."""


def compose(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {"chapter", "scene_break_after"}:
        raise ValueError("malformed reconstruction source")
    chapter = source["chapter"]
    PATCH["validate_source"](chapter)
    facts = chapter["protected"]
    divisions = source["scene_break_after"]
    if (
        not isinstance(divisions, list)
        or any(not isinstance(d, str) or d not in {f["id"] for f in facts} for d in divisions)
        or len(set(divisions)) != len(divisions)
    ):
        raise ValueError("unknown or repeated scene division")
    record = {
        "required_facts": [{"id": f["id"], "text": f["text"]} for f in facts],
        "literal_sequence": PATCH["literal_sequence"](chapter["text"], chapter["verbatim"]),
        "scene_break_after_fact": divisions,
        "source_conditions": chapter["notes"],
    }
    shared = "Required story record:\n" + json.dumps(record, ensure_ascii=False)
    return {
        "full": {
            "system": SYSTEM,
            "prompt": shared + "\n\nOptional reference prose:\n" + chapter["text"],
        },
        "focused": {"system": SYSTEM, "prompt": shared},
    }


def quota(out: Path) -> None:
    total = 0
    for path in out.glob("*.result.json"):
        result = read(path)
        if result["status"] != "completed":
            raise RuntimeError("previous transport failure; no retry")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = result["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid quota usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")


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
        HERE / "prose_codex.py",
        HERE / "prose_paragraph_revision.py",
        REGISTRATION,
        REGISTRATION.with_name("RUNBOOK.md"),
        source_path,
        source_path.with_name("source-review.md"),
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
            "files": {str(p): sha(p) for p in paths},
            "token_stop": TOKEN_STOP,
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
        },
    )


def run(out: Path) -> None:
    for name in ORDER:
        m = CODEX["validate"](out)
        if m["requests"] != compose(m["source"]):
            raise ValueError("frozen requests changed")
        quota(out)
        r = CODEX["complete_once"](out, name, m)
        path = out / f"{name}.inspection.json"
        if path.exists():
            continue
        chapter = m["source"]["chapter"]
        expected = PATCH["literal_sequence"](chapter["text"], chapter["verbatim"])
        actual = PATCH["literal_sequence"](r["text"], chapter["verbatim"])
        write_new(
            path,
            {
                "literal_sequence_matches": actual == expected,
                "expected_literal_occurrences": len(expected),
                "actual_literal_occurrences": len(actual),
                "source_manifest_sha256": sha(out / "manifest.json"),
                "result_sha256": sha(out / f"{name}.result.json"),
                "semantic_status": "unassessed; literal checks cannot certify meaning",
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
