"""Isolated deletion-only diagnostic; exact spans, no production write or quality score."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import runpy
import subprocess
from pathlib import Path
from typing import Any

from litharness.domain.generation import CompletionRequest

ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).with_name("prose_inputs.py")
REGISTRATION = Path(__file__).with_name("prose-subtraction") / "PREREG.md"
COMMON = runpy.run_path(str(HELPER))
read_json, write_new, digest, complete_once = (
    COMMON[key] for key in ("read_json", "write_new", "digest", "complete_once")
)
ORDER = ("original", "literal")
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cuts"],
    "properties": {
        "cuts": {
            "type": "array",
            "maxItems": 25,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["paragraph", "quote", "reason"],
                "properties": {
                    "paragraph": {"type": "integer"},
                    "quote": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        }
    },
}


def request(scene: str) -> CompletionRequest:
    return CompletionRequest(
        system=(
            "Edit this scene by deletion only. Consider explanatory passages that repeat an "
            "implication already established, comparisons that interrupt the immediate action, "
            "and narrator commentary announcing what a moment means or what will be remembered. "
            "These are possible local defects, not forbidden sentence patterns. Keep useful "
            "detail, distinctive attitude and the information needed to follow what happens. "
            "You may remove incidental emphasis, repeated interpretations and dispensable "
            "asides. Preserve the events, their order, causes, character choices, uncertainty, "
            "negation, knowledge boundaries, relationships and consequential quantities. "
            "Preserve all printed text, dialogue and scene breaks verbatim. Add or replace "
            "nothing. Each cut must leave grammatical, connected prose in its surrounding "
            "paragraph; include the appropriate adjacent punctuation or whitespace in a cut "
            "when needed. A cut may remove a whole paragraph. Copy each exact contiguous span "
            "from its numbered paragraph. Each quote must occur exactly once in that paragraph; "
            "cuts must not overlap. Give a short reason for each cut. Up to 25 cuts; no target "
            "number or length, and an empty list is allowed. Do not fix plot errors."
        ),
        prompt=json.dumps(
            [{"paragraph": i, "text": p} for i, p in enumerate(scene.strip().split("\n\n"), 1)],
            ensure_ascii=False,
        ),
        schema=SCHEMA,
        model=COMMON["MODEL"],
        max_output_tokens=6500,
        timeout_seconds=600,
        profile="trial.prose-subtraction.v1",
    )


def apply_cuts(scene: str, payload: Any) -> str:
    """Check deletion identity and overlap; this does not prove semantic preservation."""
    if not isinstance(payload, dict) or set(payload) != {"cuts"}:
        raise ValueError("malformed cut response")
    cuts = payload["cuts"]
    if not isinstance(cuts, list) or len(cuts) > 25:
        raise ValueError("malformed cuts or too many cuts")
    paragraphs = scene.strip().split("\n\n")
    spans: dict[int, list[tuple[int, int]]] = {}
    for cut in cuts:
        if not isinstance(cut, dict) or set(cut) != {"paragraph", "quote", "reason"}:
            raise ValueError("malformed cut")
        index, quote, reason = cut["paragraph"], cut["quote"], cut["reason"]
        if type(index) is not int or not 1 <= index <= len(paragraphs):
            raise ValueError("unknown paragraph")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("missing reason")
        if not isinstance(quote, str) or not quote.strip():
            raise ValueError("empty quote")
        source = paragraphs[index - 1]
        starts = [m.start() for m in re.finditer(f"(?={re.escape(quote)})", source)]
        if len(starts) != 1:
            raise ValueError("quote missing or ambiguous")
        span = (starts[0], starts[0] + len(quote))
        prior = spans.setdefault(index - 1, [])
        if any(span[0] < end and start < span[1] for start, end in prior):
            raise ValueError("overlapping cuts")
        prior.append(span)
    for index, ranges in spans.items():
        for start, end in sorted(ranges, reverse=True):
            paragraphs[index] = paragraphs[index][:start] + paragraphs[index][end:]
    return "\n\n".join(p.strip() for p in paragraphs if p.strip())


def prepare(out: Path, source: Path) -> None:
    if not out.resolve().is_relative_to(ROOT / "runs") or out.resolve() == ROOT / "runs":
        raise ValueError("output must be a new directory beneath runs")
    inputs = {
        "original": read_json(source / "manifest.json")["source_scene"],
        "literal": read_json(source / "literal_unbounded-1.result.json")["text"],
    }
    out.mkdir(parents=True, exist_ok=False)
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "files": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (Path(__file__), HELPER, REGISTRATION)
            },
            "sources": inputs,
            "sources_digest": digest(inputs),
            "order": ORDER,
            "max_calls": 2,
            "spend_stop_usd": 2.0,
        },
    )


def run(out: Path) -> None:
    manifest = read_json(out / "manifest.json")
    for path, expected in manifest["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError("registered code or procedure changed")
    if digest(manifest["sources"]) != manifest["sources_digest"]:
        raise ValueError("frozen source changed")
    for name in ORDER:
        if not (out / f"{name}.request.json").exists():
            results = [read_json(p) for p in out.glob("*.result.json")]
            if len(list(out.glob("*.request.json"))) >= 2:
                raise ValueError("two-call limit reached")
            if (
                any(r["cost_usd"] is None for r in results)
                or sum(r["cost_usd"] for r in results) >= 2.0
            ):
                raise ValueError("spend stop reached or cost missing")
        scene = manifest["sources"][name]
        result = complete_once(out, name, request(scene))
        # An invalid response is retained and does not block the other fixed position.
        try:
            edited = apply_cuts(scene, result["parsed"])
            outcome = {"status": "applied_local_only", "text": edited}
        except ValueError as error:
            outcome = {"status": "rejected", "error": str(error)}
        path = out / f"{name}.application.json"
        if path.exists():
            if read_json(path) != outcome:
                raise ValueError("recorded application differs")
        else:
            write_new(path, outcome)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if args.source is None:
            parser.error("prepare requires source directory")
        prepare(args.out, args.source)
    else:
        run(args.out)


if __name__ == "__main__":
    main()
