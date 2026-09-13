"""Call-free construction controls and descriptive Architect trace profiling."""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import os
import re
import runpy
from pathlib import Path

_RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, PRIOR, ROOT, RUN, load, lock, native_usage, save, sha = (
    _RUNNER[key]
    for key in ("HERE", "PRIOR", "ROOT", "RUN", "load", "lock", "native_usage", "save", "sha")
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def deletion_candidates(text, start, end):
    """Mechanical proposals only: matching edits are never called semantic controls."""
    from litharness.domain.salience import _fingerprint

    if not 0 <= start < end <= len(text) or text.count(text[start:end]) != 1:
        raise ValueError("Payoff quote must be nonempty and unique")
    damaged = text[:start] + text[end:]
    fingerprint = _fingerprint(text, damaged, position=start, anchor_distance=0)
    matches = []
    for match in re.finditer(r"[^.!?\n]+[.!?]+", text):
        left, right = match.span()
        while left < right and text[left].isspace():
            left += 1
        if left < end and right > start:
            continue
        sham = text[:left] + text[right:]
        other = _fingerprint(text, sham, position=left, anchor_distance=0)
        if other == fingerprint:
            matches.append({"start": left, "end": right, "text": sham})
    return {"damaged": damaged, "fingerprint": dataclasses.asdict(fingerprint), "matches": matches}


def construction():
    from litharness.adapters.sqlite_store import SqliteStore

    results, private, books = [], [], set()
    for packet in sorted(
        (ROOT / "runs/causal-reader-admission-20260913").glob(
            "source-*/*/*/battery.private.json",
        )
    ):
        census = load(packet)["census"]
        database = packet.parents[2] / "serial.db"
        before = sha(database)
        with SqliteStore.open_read_only(database) as store:
            revision = store.load_revision(census["revision_id"])
        for candidate in census["candidates"]:
            if candidate["family"] != "promise_payoff":
                continue
            books.add(census["book_id"])
            target = candidate["evidence"][1]
            text = revision.node(target["logical_id"]).content or ""
            if text[target["start"] : target["end"]] != target["quote"]:
                raise RuntimeError("Registered payoff span changed")
            proposed = deletion_candidates(text, target["start"], target["end"])
            results.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "book_id": census["book_id"],
                    "revision_id": census["revision_id"],
                    "packet_sha256": sha(packet),
                    "fingerprint": proposed["fingerprint"],
                    "matching_sentence_deletions": len(proposed["matches"]),
                    "semantic_damage_verified": False,
                    "semantic_sham_verified": False,
                }
            )
            private.append({"candidate": candidate, "proposed": proposed})
        if sha(database) != before:
            raise RuntimeError("Admission source backup changed")
    save(RUN / "construction-private.json", private)
    return {
        "candidate_relations": len(results),
        "independent_book_ids": len(books),
        "with_mechanical_matches": sum(bool(row["matching_sentence_deletions"]) for row in results),
        "verified_semantic_pairs": 0,
        "eligible_for_reader_calls": False,
        "items": results,
        "limitation": (
            "Removing one unique quote does not prove removal of its semantic payoff; "
            "a matched non-key sentence may also carry the payoff or another important relation."
        ),
    }


def profile(paths):
    calls = []
    for path in paths:
        row = load(path)
        if not row["request"]["profile"].startswith("architect."):
            continue
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        seen_records, seen_queries = set(), set()
        returned, repeated, query_bytes, record_bytes, repeated_bytes = 0, 0, 0, 0, 0
        repeated_queries, queries, other_bytes, tool_counts = 0, 0, 0, collections.Counter()
        for line in raw.get("commands_jsonl", "").splitlines():
            command = json.loads(line)
            if command.get("phase") != "result":
                continue
            args = command.get("arguments", [])
            if isinstance(args, dict):
                args = args.get("arguments", [])
            verb = " ".join(args[:2])
            tool_counts[verb] += 1
            stdout = command.get("stdout", "")
            if args[:2] != ["world", "query"]:
                other_bytes += len(stdout.encode("utf-8"))
                continue
            queries += 1
            query_bytes += len(stdout.encode("utf-8"))
            key = digest({"arguments": args, "stdout": stdout})
            repeated_queries += key in seen_queries
            seen_queries.add(key)
            if command.get("returncode"):
                continue
            payload = json.loads(stdout)
            for record in payload.get("records", []):
                key = digest(record)
                size = len(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8"))
                returned += 1
                record_bytes += size
                if key in seen_records:
                    repeated += 1
                    repeated_bytes += size
                seen_records.add(key)
        calls.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "profile": row["request"]["profile"],
                "native_tokens": native_usage(raw),
                "wall_ms": raw.get("wall_ms"),
                "queries": queries,
                "query_stdout_bytes": query_bytes,
                "other_tool_stdout_bytes": other_bytes,
                "returned_records": returned,
                "repeated_exact_records": repeated,
                "serialized_record_bytes": record_bytes,
                "repeated_exact_record_bytes": repeated_bytes,
                "repeated_exact_query_results": repeated_queries,
                "tool_counts": dict(tool_counts),
            }
        )
    return calls


def main():
    lock()
    os.environ["LITHARNESS_ENV"] = "test"
    prior = sorted(PRIOR.glob("book-*/calls/*.json"))
    current = sorted(RUN.glob("*/calls/*.json"))
    report = {
        "schema": "litharness.next-priorities-probes.v1",
        "model_calls": 0,
        "script_sha256": sha(Path(__file__)),
        "construction": construction(),
        "architect_calls": profile([*prior, *current]),
    }
    save(HERE / "probes.json", report)
    print(
        json.dumps(
            {
                "construction": {
                    key: value
                    for key, value in report["construction"].items()
                    if key not in {"items", "limitation"}
                },
                "architect_calls": len(report["architect_calls"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
