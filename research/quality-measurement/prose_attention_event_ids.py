"""Documented visible-group ID expansion for the initial attention response only."""

from __future__ import annotations

import argparse
import copy
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
T = runpy.run_path(str(HERE / "prose_attention_events.py"))
read, write_new, sha = T["read"], T["write_new"], T["sha"]


def normalize_visible_refs(state: Any, known_facts: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(state, dict) or set(state) != {
        "concern",
        "foreground",
        "peripheral",
        "basis",
        "unresolved",
    }:
        raise ValueError("invalid state shape")
    leaves = {u["id"] for u in known_facts}
    groups: dict[str, list[str]] = {}
    for unit in known_facts:
        groups.setdefault(unit["source_id"], []).append(unit["id"])
    result = copy.deepcopy(state)
    for key, low, high in (("foreground", 1, 3), ("peripheral", 0, 3), ("basis", 1, 5)):
        T["reference_list"](state[key], list(leaves | set(groups)), low, high)
        expanded = []
        for ref in state[key]:
            if ref in leaves:
                if ref in groups and groups[ref] != [ref]:
                    raise ValueError("ambiguous ID namespace")
                expanded.append(ref)
            else:
                expanded.extend(groups[ref])
        result[key] = list(dict.fromkeys(expanded))
    T["validate_state"](result, [u["id"] for u in known_facts])
    return result


def prepare(out: Path) -> None:
    m = T["CODEX"]["validate"](out)
    raw_result = read(out / "initial-1/full-1.result.json")
    parsed = T["CODEX"]["parse_events"](read(out / "initial-1/full-1.raw.json")["stdout"])
    if parsed["text"] != raw_result["text"] or parsed["usage"] != raw_result["usage"]:
        raise ValueError("initial raw/result mismatch")
    actual = read(out / "initial-1/full-1.request.json")
    if (
        actual["prompt"] != m["initial_request"]["prompt"]
        or actual["system"] != m["initial_request"]["system"]
    ):
        raise ValueError("initial request mismatch")
    known = json.loads(actual["prompt"])["known_facts"]
    initial = normalize_visible_refs(json.loads(raw_result["text"]), known)
    request = T["updates_request"](m["source"], initial)
    payload = json.loads(request["prompt"])
    # Remove the competing metadata namespace before this first update call.
    payload["source_units"] = [
        {k: v for k, v in u.items() if k != "source_id"} for u in payload["source_units"]
    ]
    payload["reference_field"] = "Use source_units.id exactly, restricted by allowed_ids_after."
    request["prompt"] = json.dumps(payload, ensure_ascii=False)
    files = [
        Path(__file__),
        HERE / "prose-attention-events/AMENDMENT.md",
        *T["artifact_files"](out, ("initial-1",)),
    ]
    write_new(
        out / "normalization-manifest.json",
        {
            "initial": initial,
            "request": request,
            "visible_groups": {
                g: [u["id"] for u in known if u["source_id"] == g]
                for g in dict.fromkeys(u["source_id"] for u in known)
            },
            "files": {str(p): sha(p) for p in files},
            "amendment_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
        },
    )


def check(out: Path) -> tuple[Any, Any]:
    m = T["CODEX"]["validate"](out)
    n = read(out / "normalization-manifest.json")
    T["verify_files"](n)
    return m, n


def updates(out: Path) -> None:
    m, n = check(out)
    bundle = {
        "initial": n["initial"],
        "request": n["request"],
        "files": {
            **n["files"],
            str(out / "normalization-manifest.json"): sha(out / "normalization-manifest.json"),
        },
    }
    path = out / "updates-manifest.json"
    if path.exists():
        if read(path) != bundle:
            raise ValueError("updates input changed")
    else:
        write_new(path, bundle)
    r = T["call"](out, "updates-1", n["request"], m)
    T["trajectory"](m["source"], n["initial"], json.loads(r["text"]))


def freeze(out: Path, review: Path) -> None:
    check(out)
    T["freeze"](out, review)


def drafts(out: Path) -> None:
    for name in T["ORDER"][2:]:
        m, _ = check(out)
        d = read(out / "draft-manifest.json")
        T["verify_files"](d)
        if d["requests"] != T["writer_requests"](m["source"], d["initial"], d["updates"]):
            raise ValueError("writer requests changed")
        T["call"](out, name, d["requests"][name.rsplit("-", 1)[0]], m)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "updates", "freeze", "draft"))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "freeze":
        if not args.review:
            parser.error("freeze requires --review")
        freeze(out, args.review.resolve())
    else:
        {"prepare": prepare, "updates": updates, "draft": drafts}[args.phase](out)


if __name__ == "__main__":
    main()
