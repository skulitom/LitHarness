"""Post-run mechanical readout; no quality scores or narrative classification."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from litharness.domain.draft import strip_em_dash, strip_markup

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/planning-material-20260916"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numbered_locations(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from numbered_locations(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from numbered_locations(item, f"{path}[{index}]")
    elif isinstance(value, str) and re.search(r"\b(?:chapter|scene)s?\s*\d", value, re.I):
        yield path


def summarize():
    state = read(LOCAL / "progress.json")
    if state["status"] != "complete":
        raise RuntimeError("This readout requires the completed registered run")
    evidence = read(HERE / "evidence.json")
    handoff = read(HERE / "handoff-evidence.json")
    files = {}
    integrity = {}
    for name, source, field in (
        ("frozen", LOCAL / "manifest.json", "files"),
        ("paired", LOCAL / "paired-sources.json", "files"),
        ("handoff", HERE / "handoff-evidence.json", "source_hashes"),
    ):
        expected = read(source)[field]
        mismatches = []
        for location, digest in expected.items():
            path = ROOT / location
            if not path.is_file() or sha(path) != digest:
                mismatches.append(location)
        integrity[name] = {"files": len(expected), "mismatches": mismatches}
        if mismatches:
            raise RuntimeError(f"Changed {name} evidence: {mismatches}")
        files[source.relative_to(ROOT).as_posix()] = sha(source)

    phases = defaultdict(lambda: {"calls": 0, "recorded_tokens": 0})
    requests = []
    for receipt in state["calls"]:
        phase = phases[receipt["phase"]]
        phase["calls"] += 1
        phase["recorded_tokens"] += receipt["tokens"]
        if receipt["profile"].startswith("planner.outline."):
            path = LOCAL / receipt["path"]
            files[path.relative_to(ROOT).as_posix()] = sha(path)
            prompt = json.loads(read(path)["request"]["prompt"])
            requests.append(
                {
                    "book": receipt["book"],
                    "call": receipt["number"],
                    "open_promises_is_null": prompt["open_promises"] is None,
                    "numbered_concept_field_locations": list(
                        numbered_locations(prompt["book_concept"], "$.book_concept")
                    ),
                    "numbered_material_field_locations": list(
                        numbered_locations(
                            prompt.get("planning_material", {}), "$.planning_material"
                        )
                    ),
                }
            )
    drafts, differences = [], []
    for raw in sorted(LOCAL.glob("books/*/writer-raw-*.md")):
        chapter = raw.with_name(f"chapter-{raw.name.split('-')[2]}.md")
        before = raw.read_text(encoding="utf-8").strip()
        after = chapter.read_text(encoding="utf-8").strip()
        cleaned = strip_markup(strip_em_dash(before)[0])[0].strip()
        if cleaned != after:
            raise RuntimeError(f"Unexpected manuscript changes: {chapter}")
        diff = list(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=raw.relative_to(ROOT).as_posix(),
                tofile=chapter.relative_to(ROOT).as_posix(),
                n=1,
                lineterm="",
            )
        )
        if diff:
            differences.append("\n".join(diff))
        drafts.append(
            {
                "book": raw.parent.name,
                "chapter": int(raw.name.split("-")[2]),
                "raw_sha256": sha(raw),
                "chapter_sha256": sha(chapter),
                "identical_before_cleanup": before == after,
                "identical_after_existing_cleanup": cleaned == after,
                "diff_hunks": sum(line.startswith("@@") for line in diff),
            }
        )
    difference_path = LOCAL / "writer-differences.diff"
    difference_path.write_text("\n\n".join(differences) + "\n", encoding="utf-8", newline="\n")
    for source in (Path(__file__), HERE / "evidence.json", difference_path):
        files[source.relative_to(ROOT).as_posix()] = sha(source)
    result = {
        "method": (
            "Post-run mechanical checks; field locations are a lexical inventory, not a metric."
        ),
        "integrity": integrity,
        "source_hashes": files,
        "phase_usage": dict(phases),
        "calls": len(state["calls"]),
        "recorded_tokens": sum(c["tokens"] for c in state["calls"]),
        "elapsed_seconds": (
            datetime.fromisoformat(state["finished_at"])
            - datetime.fromisoformat(state["started_at"])
        ).total_seconds(),
        "chapters": len(evidence["chapters"]),
        "words": sum(c["words"] for c in evidence["chapters"]),
        "coverage_items_retained": sum(
            o["coverage_items_retained"] for b in handoff["books"] for o in b["outlines"]
        ),
        "outline_requests": sorted(requests, key=lambda item: item["book"]),
        "drafts": drafts,
    }
    (HERE / "readout-controls.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({k: result[k] for k in ("integrity", "calls", "chapters", "words")}))


if __name__ == "__main__":
    summarize()
