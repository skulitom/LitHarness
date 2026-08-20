"""One entry point that reads every force result and says what the programme currently knows.

Four tracks, two transports, several refusal states and a market that is gated: the state of the
force programme is spread across `results/force-*.json` and nobody should have to reconstruct it
by opening six files in the right order. This opens them and prints the one table that matters,
plus the sentence §9 of the design says the programme is entitled to.

**It computes nothing.** Every number here was decided by the module that produced it, under bars
declared before that module ran; this only collects them. That is deliberate — a reporter that
recomputed a verdict would be a second implementation of the bars, and the whole point of
`force_harness` is that there is exactly one.

**It refuses to summarise a refusal into a pass or a fail.** `NOT_RUN`, `NOT_SCREENABLE`,
`DEGRADED_STRATUM`, `INSUFFICIENT_N`, `INERT_GENERATOR`, `SPLIT_FAMILY` and `VOID` print as
themselves, because §1.5 makes them verdicts and a table that collapsed them would be the exact
failure the states exist to prevent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from force_harness import RESULTS, combine_families, force_verdict  # noqa: E402

#: Track -> the result file it writes. A missing file is `NOT_RUN`, which is a state and not a gap.
TRACKS: dict[str, tuple[str, str]] = {
    "F1": ("force-f1-haiku.json",
           "register half-life - what the text does to the generation field"),
    "F2": ("force-f2.json", "retention under distance — what survives a context flush"),
    "F3": ("force-f3.json", "compression progress — does a book teach the model to read it"),
    "FX": ("force-fx.json", "transmission chains — what survives being retold"),
    "FM": ("force-fm-dryrun.json", "the market — gated on a force clearing the bars"),
}

BINDING = ("aligned", "crossed")


def _load(name: str) -> dict[str, Any] | None:
    path = RESULTS / name
    if not path.is_file():
        # A run that stopped early still writes a `-partial` artifact scored from its cache. That
        # is a different state from never having run, and the table has to be able to say so.
        partial = RESULTS / name.replace(".json", "-partial.json")
        if partial.is_file():
            path = partial
        else:
            return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _track_row(track: str, report: dict[str, Any] | None) -> dict[str, Any]:
    if report is None:
        # A track whose substrate has been surveyed but never scored is not the same state as one
        # nothing has touched, and collapsing the two would hide the survey's own findings.
        survey = _load(f"force-{track.lower()}-survey.json")
        if survey is not None:
            return {
                "track": track,
                "status": "SURVEY_ONLY",
                "detail": survey.get("price", {}).get("verdict", "surveyed, not scored"),
                "pairs": survey.get("pairs"),
            }
        return {"track": track, "status": "NOT_RUN", "detail": "no result file"}
    combined = report.get("combined", {})
    row: dict[str, Any] = {
        "track": track,
        "status": report.get("force_verdict") or report.get("status") or "READ",
        "pairs": report.get("pairs"),
        "families": sorted((report.get("per_family") or {}).keys()),
    }
    for stratum in BINDING:
        entry = combined.get(stratum) or {}
        row[stratum] = entry.get("status", "-")
    controls: dict[str, str] = {}
    for family, block in (report.get("per_family") or {}).items():
        for control in ("placebo_identical", "rewhitespace_sham"):
            if control in block:
                controls[f"{family}/{control}"] = block[control].get("status", "-")
    row["controls"] = controls
    ledgers = {
        family: block["ledger"]["spent_usd"]
        for family, block in (report.get("per_family") or {}).items()
        if isinstance(block.get("ledger"), dict) and block["ledger"].get("spent_usd") is not None
    }
    if ledgers:
        row["spent_usd"] = round(sum(ledgers.values()), 2)
    return row


def collect() -> dict[str, Any]:
    rows = [_track_row(track, _load(name)) for track, (name, _) in TRACKS.items()]
    passed = [
        row["track"] for row in rows
        if all(row.get(stratum) == "PASS" for stratum in BINDING)
    ]
    return {
        "tracks": rows,
        "forces_clearing_both_binding_strata": passed,
        "reading": (
            "A force cleared both binding strata: machine valence exists on this material, "
            "obtained without asking a model a question or a human for a judgment."
            if passed
            else "No force has cleared both binding strata. That is not yet the programme's "
                 "negative sentence - section 9 reserves that for every force failing with "
                 "controls clean across two families, and the table says which tracks have not "
                 "run rather than which have failed."
        ),
    }


def render(summary: dict[str, Any]) -> str:
    lines = [
        f"{'track':<5} {'status':<17} {'aligned':<17} {'crossed':<17} families",
        "-" * 86,
    ]
    for row in summary["tracks"]:
        families = ", ".join(row.get("families") or []) or "-"
        lines.append(
            f"{row['track']:<5} {str(row['status'])[:16]:<17} "
            f"{str(row.get('aligned', '-'))[:16]:<17} {str(row.get('crossed', '-'))[:16]:<17} "
            f"{families}"
        )
        for name, status in (row.get("controls") or {}).items():
            lines.append(f"      control {name}: {status}")
        if row.get("spent_usd") is not None:
            lines.append(f"      spend: ${row['spent_usd']} equivalent quota")
    lines.append("")
    lines.append(summary["reading"])
    return "\n".join(lines)


def reassemble(path: Path, *, apply: bool) -> dict[str, Any]:
    """Recompute one artifact's `combined` and headline from its stored `per_family`.

    **Not a second implementation of the bars — the opposite.** Every stratum reading inside
    `per_family` was computed by the track that ran, and stays exactly as it was written; only
    the two *combining* steps are redone, both by calling `force_harness` rather than restating
    it. What this exists for is the gap between when a run was scored and when the combining
    rules were last corrected: 15 of 16 `combined` rows across the committed files did not match
    what the current module returns, and an artifact whose headline predates a fix to the
    headline function is a stale claim sitting in the repository looking authoritative.

    A rewritten file records `reassembled` with the before-and-after, so the change is legible in
    the artifact rather than only in this script's output. The alternative — regenerating from
    the GPU — costs hours and would answer a question that was already paid for.
    """
    report = json.loads(path.read_text(encoding="utf-8"))
    per_family = report.get("per_family")
    if not isinstance(per_family, dict) or not per_family:
        return {"file": path.name, "status": "SKIPPED", "why": "no per_family block to read"}
    if report.get("WITHDRAWN"):
        # **A withdrawal is a decision, not a computation, and recomputing over one erases it.**
        # `force-f2-partial.json` carries a hand-set `force_verdict: VOID` beside a per-family
        # status of NOT_SCREENABLE, because the measurement was retracted for a reason no
        # combining rule can see (B3: every uplift read one token past its matched site). Left to
        # itself this function would have replaced the retraction with the milder computed state.
        return {"file": path.name, "status": "SKIPPED",
                "why": "artifact is WITHDRAWN; its headline is a retraction, not a combining step"}
    # Diagnostic strata (`crossed_loose`, the level arms, the shuffled arm) are recombined too,
    # so an artifact does not end up mixing fresh binding rows with stale diagnostic ones.
    #
    # A stratum is a block `verdict()` wrote, identified by its own `stratum` key — matching on
    # "every key the family block happens to hold" swept in `cache`, `governor`, `ledger` and
    # `seed_budget` and published combined verdicts for them. The old `combined` keys are unioned
    # in because a stratum **no family ran** is still a row: it lives nowhere in `per_family` and
    # `combine_families` reports it as NOT_SCREENABLE, which is the honest state and is exactly
    # the row a strict recompute would have deleted.
    labels = set(BINDING) | set(report.get("combined") or {})
    for block in per_family.values():
        labels |= {
            label for label, value in block.items()
            if isinstance(value, dict) and "stratum" in value
        }
    combined = {label: combine_families(per_family, label) for label in sorted(labels)}
    headline = force_verdict(per_family, combined)
    was = {
        "force_verdict": report.get("force_verdict"),
        "combined": {k: (v or {}).get("status") for k, v in
                     (report.get("combined") or {}).items()},
    }
    now = {
        "force_verdict": headline["verdict"],
        "combined": {k: v.get("status") for k, v in combined.items()},
    }
    changed = was != now
    row = {"file": path.name, "changed": changed, "was": was, "now": now}
    if not apply or not changed:
        row["status"] = "WOULD_CHANGE" if changed else "CURRENT"
        return row
    report["combined"] = combined
    report["force_verdict"] = headline["verdict"]
    report["force_verdict_detail"] = headline
    history = report.get("reassembled")
    report["reassembled"] = (history if isinstance(history, list) else
                             [history] if history else []) + [{
        "why": "combining rules changed after this run was scored; per-family readings untouched",
        "was": was, "now": now,
    }]
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    row["status"] = "REWRITTEN"
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--reassemble", action="store_true",
                        help="recompute every artifact's combined/headline from its stored "
                             "per_family; dry run unless --apply is given")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.reassemble:
        rows = [reassemble(p, apply=args.apply) for p in sorted(RESULTS.glob("force-*.json"))]
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    summary = collect()
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json else render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
