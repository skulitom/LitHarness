"""Cross narration obligations with identical writer facts; subscription research only."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
BASE = runpy.run_path(str(HERE / "prose_protected_reconstruction.py"))
CODEX, PATCH = BASE["CODEX"], BASE["PATCH"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-narration-obligations/PREREG.md"
ORDER = CODEX["ORDER"]
SYSTEM = """Write the complete chapter as novel prose in close third person, past tense.
All supplied source units are binding facts at their specified times. Context known to the
writer is not automatically something the viewpoint character knows: preserve the recorded
observations, beliefs, inferences and their timing, without turning an inference into a rule.
The required_narration list identifies information that must reach the reader in this chapter,
through action, dialogue or narration. It need not receive a separate explanation after being
shown. Units outside that list remain true and available to you but may remain unstated or
implicit. Omission does not undo an event or realization, authorize a contradiction or move
knowledge earlier. Use the same events, causal relationships, consequential quantities and
endpoint. The source sequence is not a paragraph outline. Wording and paragraph organization
are yours. Preserve the supplied literal sequence exactly, including repeated occurrences;
an inline literal may stay inline. Keep the indicated scene division. There is no word target,
compression quota, prescribed opening sentence or required comparison. Do not add incidents,
backstory, named characters, quantities, rules or revelations; do not resolve source ambiguities.
Return only the complete chapter prose without a title, commentary, analysis or score."""


def compose(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {
        "chapter",
        "facts",
        "implicit_ids",
        "scene_break_after",
        "notes",
    }:
        raise ValueError("malformed obligations source")
    chapter = source["chapter"]
    PATCH["validate_source"](chapter)
    facts = source["facts"]
    if not isinstance(facts, list) or not facts:
        raise ValueError("empty source units")
    for fact in facts:
        if (
            not isinstance(fact, dict)
            or set(fact) != {"id", "source_id", "kind", "when", "text"}
            or any(not isinstance(v, str) or not v.strip() for v in fact.values())
            or fact["kind"] not in {"context", "knowledge", "event"}
        ):
            raise ValueError("malformed source unit")
    ids = [f["id"] for f in facts]
    origins = list(dict.fromkeys(f["source_id"] for f in facts))
    if len(set(ids)) != len(ids) or origins != [f["id"] for f in chapter["protected"]]:
        raise ValueError("source coverage or order changed")
    if [f["source_id"] for f in facts] != [
        origin for origin in origins for f in facts if f["source_id"] == origin
    ]:
        raise ValueError("source units must remain grouped in source order")
    implicit = source["implicit_ids"]
    if (
        not isinstance(implicit, list)
        or not implicit
        or any(not isinstance(i, str) or i not in ids for i in implicit)
        or len(set(implicit)) != len(implicit)
        or any(f["id"] in implicit and f["kind"] == "event" for f in facts)
        or len(implicit) == len(ids)
    ):
        raise ValueError("invalid implicit permission or event demotion")
    divisions = source["scene_break_after"]
    if (
        not isinstance(divisions, list)
        or any(not isinstance(i, str) or i not in ids for i in divisions)
        or len(set(divisions)) != len(divisions)
        or not isinstance(source["notes"], str)
    ):
        raise ValueError("invalid source metadata")
    shared = {
        "source_units": facts,
        "literal_sequence": PATCH["literal_sequence"](chapter["text"], chapter["verbatim"]),
        "scene_break_after_unit": divisions,
        "source_conditions": source["notes"],
    }
    return {
        condition: {
            "system": SYSTEM,
            "prompt": "Story source and narration assignment:\n"
            + json.dumps(
                {
                    **shared,
                    "required_narration": [
                        i for i in ids if condition == "full" or i not in implicit
                    ],
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
            "files": {str(p): sha(p) for p in paths},
            "token_stop": BASE["TOKEN_STOP"],
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
        BASE["quota"](out)
        result = CODEX["complete_once"](out, name, manifest)
        path = out / f"{name}.inspection.json"
        if path.exists():
            continue
        chapter = manifest["source"]["chapter"]
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
