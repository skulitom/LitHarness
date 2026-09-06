"""Paragraph patches with two information-preservation instructions; isolated research."""

from __future__ import annotations

import argparse
import json
import re
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
CODEX = runpy.run_path(str(HERE / "prose_codex.py"))
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
ROOT = HERE.parents[1]
REGISTRATION = HERE / "prose-paragraph-revision/PREREG.md"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
TOKEN_STOP = 90_000
SYSTEM = """Revise the supplied chapter at paragraph level for continuity of attention and
readable prose. Work with the existing events and viewpoint. You may split or merge paragraphs
and rephrase sentences. Do not add incidents, backstory, dialogue, rules or revelations, resolve
source ambiguities, or extend the chapter. No target length, deletion quota or required style.
Follow the condition's information-preservation instruction and the shared protected facts.
Preserve the listed literal spans exactly, in their existing order and number of occurrences.
Return only JSON: {"patches": [{"first": 1, "last": 2, "paragraphs": ["replacement paragraph"],
"reason": "what this change does", "omitted_or_deferred": ["information no longer stated"]}]}.
Each patch replaces an inclusive range of the ORIGINAL numbered paragraphs. Patches must be
ordered and nonoverlapping. Each replacement string is one paragraph, without blank lines.
An empty paragraphs array deletes that range. Unmentioned paragraphs remain verbatim. An empty
patches array is allowed. List substantive information removed or deferred in that patch; do
not claim a quality score, compare candidates or supply a second version."""
CONDITIONS = {
    "full": "Preserve every distinct piece of information in the chapter, including incidental "
    "background, sensory details, comparisons and interpretations. Repeated statements of the "
    "same information may be combined. Information may move within the chapter but must remain "
    "explicit somewhere; paraphrasing must retain its meaning.",
    "focused": "Preserve the shared protected facts and their causal and temporal relationships. "
    "Other incidental background, comparisons, interpretations and sensory detail may be omitted "
    "or deferred beyond this chapter when unnecessary here. Deferral means leaving it unstated, "
    "not promising a later scene. Do not replace removed information with new information.",
}


def validate_source(source: Any) -> None:
    if not isinstance(source, dict) or set(source) != {"text", "protected", "verbatim", "notes"}:
        raise ValueError("malformed source")
    if any(not isinstance(source[k], str) or not source[k].strip() for k in ("text", "notes")):
        raise ValueError("nonempty source and review notes required")
    paragraphs = source["text"].split("\n\n")
    facts = source["protected"]
    if not isinstance(facts, list) or not facts:
        raise ValueError("protected facts required")
    identifiers = set()
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {"id", "paragraphs", "text"}:
            raise ValueError("malformed protected fact")
        if any(not isinstance(fact[k], str) or not fact[k].strip() for k in ("id", "text")):
            raise ValueError("nonempty fact identifiers and descriptions required")
        if fact["id"] in identifiers:
            raise ValueError("duplicate fact id")
        identifiers.add(fact["id"])
        positions = fact["paragraphs"]
        if (
            not isinstance(positions, list)
            or not positions
            or any(type(p) is not int or not 1 <= p <= len(paragraphs) for p in positions)
        ):
            raise ValueError("unknown source paragraph")
    spans = source["verbatim"]
    if (
        not isinstance(spans, list)
        or not spans
        or any(not isinstance(s, str) or not s or s not in source["text"] for s in spans)
    ):
        raise ValueError("literal spans must come from source")
    if len(set(spans)) != len(spans):
        raise ValueError("duplicate literal pattern")


def literal_sequence(text: str, spans: list[str]) -> list[str]:
    pattern = "|".join(re.escape(s) for s in sorted(spans, key=len, reverse=True))
    return re.findall(pattern, text)


def apply_patches(source: str, payload: Any) -> str:
    """Validate patch coordinates and preserve untouched text; no semantic guarantee."""
    if not isinstance(payload, dict) or set(payload) != {"patches"}:
        raise ValueError("malformed patch envelope")
    patches = payload["patches"]
    if not isinstance(patches, list):
        raise ValueError("patches must be an array")
    original, result, cursor = source.split("\n\n"), [], 0
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != {
            "first",
            "last",
            "paragraphs",
            "reason",
            "omitted_or_deferred",
        }:
            raise ValueError("malformed patch")
        first, last = patch["first"], patch["last"]
        if (
            type(first) is not int
            or type(last) is not int
            or not cursor < first <= last <= len(original)
        ):
            raise ValueError("unknown, overlapping or unordered paragraph range")
        replacement = patch["paragraphs"]
        if not isinstance(replacement, list) or any(
            not isinstance(p, str) or not p.strip() or "\n\n" in p or "\r" in p for p in replacement
        ):
            raise ValueError("replacement must be an array of nonempty paragraphs")
        if not isinstance(patch["reason"], str) or not patch["reason"].strip():
            raise ValueError("patch reason required")
        omissions = patch["omitted_or_deferred"]
        if not isinstance(omissions, list) or any(
            not isinstance(s, str) or not s.strip() for s in omissions
        ):
            raise ValueError("malformed omission record")
        result.extend(original[cursor : first - 1])
        result.extend(replacement)
        cursor = last
    result.extend(original[cursor:])
    text = "\n\n".join(result)
    if not text.strip():
        raise ValueError("empty chapter")
    return text


def requests(source: Any) -> dict[str, Any]:
    validate_source(source)
    shared = json.dumps(
        {
            **source,
            "text": [
                {"paragraph": i, "text": p} for i, p in enumerate(source["text"].split("\n\n"), 1)
            ],
        },
        ensure_ascii=False,
    )
    return {
        name: {"system": SYSTEM, "prompt": instruction + "\n\n" + shared}
        for name, instruction in CONDITIONS.items()
    }


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    frozen = requests(source)
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
            "requests": frozen,
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
        previous = [read(p) for p in out.glob("*.result.json")]
        if any(r["status"] != "completed" for r in previous):
            raise RuntimeError("prior transport failure; no retry")
        total = sum(
            r["usage"].get(k, 0)
            for r in previous
            for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
        )
        if total >= TOKEN_STOP:
            raise RuntimeError("subscription token stop reached")
        result = CODEX["complete_once"](out, name, m)
        application_path = out / f"{name}.application.json"
        if application_path.exists():
            continue
        try:
            payload = json.loads(result["text"])
            edited = apply_patches(m["source"]["text"], payload)
            literals = m["source"]["verbatim"]
            literal_match = literal_sequence(edited, literals) == literal_sequence(
                m["source"]["text"], literals
            )
            application = {
                "status": "applied_for_inspection",
                "text": edited,
                "patches": len(payload["patches"]),
                "literal_sequence_matches": literal_match,
                "source_sha256": sha(out / "manifest.json"),
                "result_sha256": sha(out / f"{name}.result.json"),
            }
        except (ValueError, TypeError) as error:
            application = {"status": "rejected", "error": str(error)}
        write_new(application_path, application)


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
