"""Reconcile historical screen outcomes with raw actions, without reading an effect."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = HERE.parents[2]
SOURCE = RESEARCH / "cost-that-bites"
sys.path.insert(0, str(RESEARCH))

import feed_core  # noqa: E402
import feed_session  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_path = SOURCE / f"raw-volume-screen-{data['book']}.jsonl"
    result = {
        "book": data["book"],
        "result_path": path.relative_to(ROOT).as_posix(),
        "result_sha256": sha(path),
        "chapters_reported": data["chapters"],
        "chunks_reported": data["chunks"],
        "reading_reported": data["reading"],
        "checks": {},
        "provenance_limits": [
            "No source-text or competitor digest manifest is present in the result.",
            "Raw cache records contain request keys, not the full frozen requests.",
            "No per-call timestamps establish when each response was obtained.",
            "Registration specifies draw 6 with three chapters; no expansion amendment found.",
        ],
    }
    checks = result["checks"]
    if data["reading"] == "TOO_SHORT":
        checks["intact_below_registered_floor"] = data["chunks"]["intact"] < 11
        checks["no_saved_sessions"] = not data.get("rows") and not raw_path.exists()
        return result
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    result.update(
        raw_path=raw_path.relative_to(ROOT).as_posix(),
        raw_sha256=sha(raw_path),
        raw_calls=len(rows),
        models=sorted({r["model"] for r in rows}),
    )
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["feed"], row["arm"], row["rotation"], row["replicate"])].append(row)
    checks["every_variant_clears_floor"] = all(n >= 11 for n in data["chunks"].values())
    checks["three_versions"] = {r["version"] for r in data["rows"]} == {
        "intact",
        "sham",
        "shuffled",
    }
    checks["raw_transport_clean"] = all(not r.get("refused") for r in rows)
    checks["raw_economics_match_registration"] = all(
        (r["budget"], r["read_cost"], r["skim_cost"]) == (24, 3, 1) for r in rows
    )
    checks["raw_call_count_matches_ledger"] = len(rows) == data["ledger"]["api_calls"]
    checks["no_reported_transport_failures"] = data["ledger"]["transport_failures"] == 0
    checks["three_scorable_sessions_reported"] = data["scorable"] == data["sessions"] == 3
    session_checks = []
    for row in data["rows"]:
        stored = row["session"]
        key = (stored["feed_id"], stored["arm"], stored["rotation"], stored["replicate"])
        raw = sorted(grouped.pop(key, []), key=lambda r: r["step"])
        actions = [feed_session._parse_choice(r) for r in raw]
        expected = [tuple(a) for a in stored["actions"]]
        session = feed_core.FeedSession(**{**stored, "actions": tuple(expected)})
        session_checks.append(
            {
                "version": row["version"],
                "actions_match_raw": actions == expected,
                "steps_contiguous": [r["step"] for r in raw] == list(range(len(raw))),
                "scorable": session.scorable,
                "no_exit_note": not session.exit_note,
                "registered_budget_spent": session.spent_units == 24,
                "registered_prices": (session.read_cost, session.skim_cost) == (3, 1),
                "raw_session_metadata_matches": all(
                    r["stage"] == "action" and r["model"] == session.model for r in raw
                ),
            }
        )
    checks["no_unmatched_raw_sessions"] = not grouped
    result["sessions"] = session_checks
    totals = {
        name: sum(r.get("usage", {}).get(name, 0) for r in rows)
        for name in ("input", "output", "cache_read", "cache_write", "equivalent_usd")
    }
    checks["usage_matches_raw"] = all(
        abs(totals[name] - data["ledger"]["spend"][name]) <= 0.0001 for name in totals
    )
    result["equivalent_usd"] = round(totals["equivalent_usd"], 6)
    result["transport_failures_reported"] = data["ledger"]["transport_failures"]
    return result


def main() -> None:
    paths = sorted(SOURCE.glob("results-volume-screen-*.json"))
    inspected = [inspect(path) for path in paths]
    result = {
        "schema": "litharness.volume-screen-audit.v1",
        "analysis": "Feasibility and record reconciliation only. No allocation effect computed.",
        "registration_path": (SOURCE / "PREREG-volume-screen.md").relative_to(ROOT).as_posix(),
        "registration_sha256": sha(SOURCE / "PREREG-volume-screen.md"),
        "derivation_sha256": sha(Path(__file__)),
        "helper_sha256": {
            name: sha(RESEARCH / name)
            for name in ("feed_core.py", "feed_session.py", "bcr.py", "elicit.py")
        },
        "untracked_inputs": subprocess.run(
            [
                "git",
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
                "research/quality-measurement/cost-that-bites",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines(),
        "records": inspected,
    }
    failures = []
    for record in inspected:
        failures.extend(
            f"{record['book']}: {name}" for name, value in record["checks"].items() if not value
        )
        for session in record.get("sessions", []):
            failures.extend(
                f"{record['book']}/{session['version']}: {name}"
                for name, value in session.items()
                if name != "version" and not value
            )
    result["failed_reconciliation_checks"] = failures
    result["provenance_verified"] = False
    output = HERE / "results.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "records": len(inspected),
                "failed_checks": failures,
                "provenance_verified": False,
                "output": str(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
