"""Prefix-only anticipations before incoming events; isolated prose diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
T = runpy.run_path(str(HERE / "prose_attention_events.py"))
CODEX = T["CODEX"]
read, write_new, sha = (T[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-prospective-attention"
ORDER = (
    "expectation-1",
    "expectation-2",
    "expectation-3",
    "source-1",
    "prospective-1",
    "prospective-2",
    "source-2",
)
TOKEN_STOP = 125_000
EXPECTATION_SYSTEM = """At the end of these available source facts, propose the protagonist's
immediate working anticipation and a concrete particular they might watch for next. You are
not given the next event. Use only supplied knowledge. An anticipation is tentative, not a
prediction asserted as fact, a new motive, or a demand that the story fulfill it. Ordinary
continuation or unresolved uncertainty is acceptable; do not manufacture a dramatic problem.
Return only JSON with exactly these keys:
{"anticipation":"1-20 words", "watch_for":"1-20 words", "basis":["source_units.id"]}.
Use 1-5 distinct available IDs as basis. Watch_for should specify something observable or
attendable, not an explanation of what a future event means. Do not invent biography,
identities, rules, incidents, a plan of future actions, an answer, dialogue or chapter prose.
Initial_ids identify facts already known at the opening, even if listed later. Other units
have occurred in their supplied order. This is the complete information available to you;
do not infer an omitted continuation. If no compatible proposal is possible, return
{"unavailable":true}."""
WRITER_SYSTEM = """Write the complete opening chapter as novel prose in close third person,
past tense. Aim for 1500-1800 words. Return only the chapter, without title or commentary.
All source_units remain true at their specified times. Preserve events, causal relations,
quantities, scene division, viewpoint knowledge and ending. The required_narration IDs must
reach the reader through action, dialogue or narration; other facts may remain implicit.
Showing an event does not require explaining it afterward. Paragraph organization, gestures
and immediate dialogue are yours. Do not add incidents, biography, identities, powers or rules.
Preserve display messages and their occurrence order, with punctuation fitting placement.
If prospective_attention is supplied, each card is a tentative anticipation available just
BEFORE its before unit begins. Let it shape what the character attends to as that incoming
event is encountered, not an explanation supplied after the event is understood. Later cards
cannot influence earlier attention. Basis IDs refer to already available facts, not events to
move. These cards are provisional attention guidance, not new canon, required inner speech,
paragraphs to insert, or new motives for established actions. The incoming source governs
what actually happens and how understanding changes. Do not keep an expectation true or active
against contradictory evidence; no persistence beyond the encounter is prescribed. There is
no duty to state the anticipation, explain a mismatch or announce the card's meaning. Handle
all required actions and interpretations at their source times. No prescribed paragraph
pattern, interpretation ban or additional narrative is requested."""


def payload(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or set(source) != {"source", "before_ids", "planner_units"}:
        raise ValueError("invalid prospective source")
    p = T["payload"](source["source"])
    p["source_units"] = [
        {k: v for k, v in u.items() if k != "source_id"} for u in p["source_units"]
    ]
    ids = [u["id"] for u in p["source_units"]]
    planner = source["planner_units"]
    if not isinstance(planner, list) or len(planner) != len(ids):
        raise ValueError("complete reviewed planner view required")
    for original, unit in zip(p["source_units"], planner, strict=True):
        if (
            not isinstance(unit, dict)
            or set(unit) != {"id", "kind", "text"}
            or any(unit[k] != original[k] for k in ("id", "kind"))
            or not isinstance(unit["text"], str)
            or not unit["text"].strip()
        ):
            raise ValueError("invalid reviewed planner unit")
    possible = [
        u["id"]
        for u in p["source_units"]
        if u["kind"] != "context" and u["id"] not in source["source"]["initial_ids"]
    ]
    T["reference_list"](source["before_ids"], possible, 3, 3)
    if source["before_ids"] != sorted(source["before_ids"], key=ids.index):
        raise ValueError("boundary order changed")
    return p


def prefix_units(source: Any, before: str) -> list[dict[str, Any]]:
    payload(source)
    units = source["planner_units"]
    if before not in source["before_ids"]:
        raise ValueError("unregistered boundary")
    ids = [u["id"] for u in units]
    known = set(source["source"]["initial_ids"]) | set(ids[: ids.index(before)])
    # Select only earlier/known units. Their text also requires a frozen semantic review:
    # source annotations can refer to the future even inside an earlier fact.
    return [u for u in units if u["id"] in known]


def expectation_requests(source: Any) -> list[dict[str, str]]:
    payload(source)
    return [
        {
            "system": EXPECTATION_SYSTEM,
            "prompt": json.dumps(
                {
                    "source_units": prefix_units(source, before),
                    "initial_ids": source["source"]["initial_ids"],
                },
                ensure_ascii=False,
            ),
        }
        for before in source["before_ids"]
    ]


def validate_expectation(source: Any, before: str, value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"anticipation", "watch_for", "basis"}:
        raise ValueError("no valid expectation")
    for key in ("anticipation", "watch_for"):
        if not isinstance(value[key], str) or not 1 <= len(value[key].split()) <= 20:
            raise ValueError("invalid expectation text length")
    T["reference_list"](value["basis"], [u["id"] for u in prefix_units(source, before)], 1, 5)


def writer_requests(source: Any, expectations: Any) -> dict[str, Any]:
    common = payload(source)
    if not isinstance(expectations, list) or len(expectations) != 3:
        raise ValueError("three expectations required")
    cards = []
    for before, value in zip(source["before_ids"], expectations, strict=True):
        validate_expectation(source, before, value)
        cards.append({"before": before, **value})
    return {
        "source": {"system": WRITER_SYSTEM, "prompt": json.dumps(common, ensure_ascii=False)},
        "prospective": {
            "system": WRITER_SYSTEM,
            "prompt": json.dumps({**common, "prospective_attention": cards}, ensure_ascii=False),
        },
    }


def quota(out: Path) -> int:
    requests = list(out.glob("*/full-1.request.json"))
    if len(requests) > len(ORDER) or any(p.parent.name not in ORDER for p in requests):
        raise ValueError("unregistered invocation")
    total = 0
    for path in out.glob("*/full-1.result.json"):
        r = read(path)
        if path.parent.name not in ORDER or r["status"] != "completed":
            raise RuntimeError("previous failure; no retry")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            n = r["usage"].get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(n) is not int or n < 0:
                raise ValueError("invalid usage")
            total += n
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")
    return total


def call(out: Path, name: str, request: Any, m: Any) -> dict[str, Any]:
    # Block before order checks as well as inside the inherited transport.
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("live trial is disabled in tests")
    quota(out)
    if name not in ORDER:
        raise ValueError("unregistered invocation")
    if any(not (out / n / "full-1.result.json").exists() for n in ORDER[: ORDER.index(name)]):
        raise ValueError("prior invocation missing")
    print(f"LOGICAL CALL {name}", flush=True)
    return CODEX["complete_once"](
        out / name, "full-1", {"prefix": m["prefix"], "requests": {"full": request}}
    )


def prepare(out: Path, source_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    requests = expectation_requests(source)
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
    systems = []
    for name in ORDER:
        folder = out / name
        (folder / "work").mkdir(parents=True)
        path = folder / "system.txt"
        path.write_text(
            EXPECTATION_SYSTEM if name.startswith("expectation-") else WRITER_SYSTEM,
            encoding="utf-8",
            newline="\n",
        )
        systems.append(path)
    files = [
        Path(__file__),
        *[
            HERE / p
            for p in (
                "prose_attention_events.py",
                "prose_attention.py",
                "prose_constraint_levels.py",
                "prose_narration_obligations.py",
                "prose_protected_reconstruction.py",
                "prose_paragraph_revision.py",
                "prose_codex.py",
            )
        ],
        REG / "PREREG.md",
        REG / "RUNBOOK.md",
        source_path,
        source_path.with_name("prepare_source.py"),
        source_path.with_name("source-review.md"),
        Path(prefix[1]),
        *systems,
    ]
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "expectation_requests": requests,
            "prefix": prefix,
            "order": ORDER,
            "token_stop": TOKEN_STOP,
            "files": {str(p): sha(p) for p in files},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
        },
    )


def derive(out: Path) -> None:
    for index, name in enumerate(ORDER[:3]):
        m = CODEX["validate"](out)
        if m["expectation_requests"] != expectation_requests(m["source"]):
            raise ValueError("expectation requests changed")
        r = call(out, name, m["expectation_requests"][index], m)
        validate_expectation(m["source"], m["source"]["before_ids"][index], json.loads(r["text"]))


def freeze(out: Path, review_path: Path) -> None:
    m = CODEX["validate"](out)
    expectations = [json.loads(read(out / n / "full-1.result.json")["text"]) for n in ORDER[:3]]
    requests = writer_requests(m["source"], expectations)
    review = read(review_path)
    if (
        review.get("text_sha256") != {n: sha(out / n / "full-1.txt") for n in ORDER[:3]}
        or review.get("reviewed_before_ids") != m["source"]["before_ids"]
        or any(
            review.get(k) is not True
            for k in (
                "source_compatible",
                "knowledge_timing",
                "no_new_canon",
                "all_prefix_inputs_read",
            )
        )
    ):
        raise ValueError("complete semantic review required")
    files = [*T["artifact_files"](out, ORDER[:3]), review_path]
    write_new(
        out / "draft-manifest.json",
        {
            "expectations": expectations,
            "requests": requests,
            "review": review,
            "files": {str(p): sha(p) for p in files},
        },
    )


def draft(out: Path) -> None:
    for name in ORDER[3:]:
        m = CODEX["validate"](out)
        d = read(out / "draft-manifest.json")
        T["verify_files"](d)
        if d["requests"] != writer_requests(m["source"], d["expectations"]):
            raise ValueError("writer request changed")
        call(out, name, d["requests"][name.rsplit("-", 1)[0]], m)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "derive", "freeze", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase in ("prepare", "freeze"):
        path = args.source if args.phase == "prepare" else args.review
        if not path:
            parser.error("prepare requires --source; freeze requires --review")
        {"prepare": prepare, "freeze": freeze}[args.phase](out, path.resolve())
    else:
        {"derive": derive, "draft": draft}[args.phase](out)


if __name__ == "__main__":
    main()
