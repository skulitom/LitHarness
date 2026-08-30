"""Plain counts over accepted scenes, for the attribution report's reviser column.

**Operator diagnostics, not research** (stage-0 §95, §97.1). Nothing here declares a bar, ranks
two texts, or promotes a claim. Every number is a count over prose the store already holds, and
every counter below either reuses a definition recorded elsewhere in the repository or says in
its own docstring that it is a crude re-derivation and why.

**What it cannot do, said once here and again in the report.** The §185 reviser runs on the
provider's string before anything is committed, so the writer's draft is never persisted:
`application/handlers.py::revise_draft` returns one string, the store commits that one, and
`providers/cli.py` passes `--no-session-persistence` so no transcript survives either. There are
therefore no draft/revision pairs to diff. What this script measures is the *page* — the adopted
text — beside a page drawn from the same listing before the stage existed.

Read-only. It shells out to the `debug-book` verbs (`export`, `why`, `events`) rather than
opening any database, which is that skill's rule.

    uv run python plan/agent-impact/scripts/reviser_impact.py \
        --store draw2-no-reviser=runs/pilots/databases/serial18b.db \
        --store draw3-reviser=runs/pilots/databases/serial18c.db \
        --json plan/agent-impact/reviser-impact.json

Paths are resolved against the repository root by default; pass absolute paths to override.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# `research/` is not a package; the §156 counters are imported by path so the module is read
# rather than copied. It is never edited by this script.
sys.path.insert(0, str(REPO_ROOT / "research" / "quality-measurement"))
try:  # pragma: no cover - the import is the point
    from register_census import gloss_counts, gloss_hits  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    gloss_counts = gloss_hits = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------------------
# Text shaping
# ---------------------------------------------------------------------------------------

#: A line the book prints as a machine rather than as prose. The same shape
#: `domain/reviser._MACHINE_LINE` protects character-for-character; excluded from every prose
#: count below so a status panel is not read as a sentence.
MACHINE_LINE = re.compile(r"^\[[A-Z][A-Z ]*\]")

#: `export --format markdown` writes one `## Chapter N` heading per rendered unit.
CHAPTER_HEADING = re.compile(r"^## Chapter (\d+)\s*$")

#: §180.1's split, quoted from that entry: "sentences split on terminal punctuation".
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\"'”’]?\s+")

#: §180.1's join, quoted from that entry: "a count of coordinated joins (commas plus
#: free-standing *and*)". Re-derived because that entry records its script "is not kept".
JOIN = re.compile(r",|\band\b", re.IGNORECASE)

#: The connectives named in the measurement brief for this column, counted as bare tokens.
#: **Not disambiguated**: `when`, `before`, `after`, `since` and `until` are prepositions and
#: adverbs as often as they are subordinators, so this is a density of the word and not of the
#: construction. Reported as such.
SUBORDINATORS = ("while", "when", "before", "after", "since", "until", "because")

#: Tokens that settle a clause as having a verb without a parser. Used only to *flag*
#: candidates for the verbless-fragment count, never to produce the count itself — the
#: flagged set is small enough to be read, and the report carries the confirmed lines.
VERB_SIGNALS = frozenset(
    """is was were are am be been being has have had do does did will would can could
    shall should may might must said says say went came got made took gave saw knew
    stood sat lay held put let ran came kept left felt found told thought became meant
    brought sent set read hit shut spread cost cut let bet burst""".split()
)
VERB_SUFFIX = re.compile(r"(ed|ing|s)$")
WORD = re.compile(r"[A-Za-z']+")


def prose_lines(text: str) -> list[str]:
    """Every line of the body that is prose: no headings, no machine lines, no blockquotes."""
    keep = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", ">", "|", "-", "*", "---")):
            continue
        if MACHINE_LINE.match(stripped):
            continue
        keep.append(stripped)
    return keep


def paragraphs(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in prose_lines(text):
        for piece in SENTENCE_SPLIT.split(line):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def words(text: str) -> list[str]:
    return WORD.findall(text)


# ---------------------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------------------


def join_profile(sents: list[str]) -> dict[str, object]:
    """§180.1's join distribution, re-derived on its own stated definition."""
    counts = [len(JOIN.findall(s)) for s in sents]
    n = len(counts) or 1
    return {
        "sentences": len(counts),
        "median_joins": statistics.median(counts) if counts else 0,
        "share_zero_joins": sum(1 for c in counts if c == 0) / n,
        "share_ge_4_joins": sum(1 for c in counts if c >= 4) / n,
        "share_ge_6_joins": sum(1 for c in counts if c >= 6) / n,
        "max_joins": max(counts) if counts else 0,
        "worst": [
            {"joins": c, "words": len(words(s)), "text": s}
            for c, s in sorted(zip(counts, sents), key=lambda pair: -pair[0])[:5]
        ],
    }


def length_profile(sents: list[str]) -> dict[str, float]:
    lengths = [len(words(s)) for s in sents]
    if not lengths:
        return {}
    return {
        "sentences": len(lengths),
        "words": sum(lengths),
        "mean_sentence_words": statistics.mean(lengths),
        "median_sentence_words": statistics.median(lengths),
        "p90_sentence_words": (
            statistics.quantiles(lengths, n=10)[-1] if len(lengths) > 1 else lengths[0]
        ),
        "max_sentence_words": max(lengths),
        "share_over_thirty": sum(1 for n in lengths if n > 30) / len(lengths),
    }


def subordinator_density(text: str) -> dict[str, object]:
    toks = [w.lower() for w in words(text)]
    hits = {w: toks.count(w) for w in SUBORDINATORS}
    total = sum(hits.values())
    return {
        "per_100_words": 100.0 * total / len(toks) if toks else 0.0,
        "total": total,
        "by_word": hits,
        "words": len(toks),
    }


def repeated_openings(sents: list[str]) -> dict[str, object]:
    """The reviser's third craft clause: "a run of sentences beginning the same way".

    Counted as adjacent sentences sharing their first word, case-folded — the cheapest
    reading of "beginning the same way" and deliberately not a shape model.
    """
    firsts = [(words(s) or [""])[0].lower() for s in sents]
    runs = sum(1 for a, b in zip(firsts, firsts[1:]) if a and a == b)
    return {
        "adjacent_same_opening": runs,
        "rate_per_100_sentences": 100.0 * runs / len(firsts) if firsts else 0.0,
        "distinct_openings": len(set(firsts)),
        "sentences": len(firsts),
    }


def em_dashes(text: str) -> int:
    return text.count("—")


def fragment_candidates(sents: list[str]) -> list[str]:
    """Sentences carrying no token this script can see as a verb. **Candidates, not a count.**

    There is no parser here, so this over-flags every sentence whose only verb is an
    irregular past tense the `VERB_SIGNALS` list does not name. The flagged set is printed
    so a human reads it; the report's verbless-fragment number is the read one.
    """
    flagged = []
    for s in sents:
        toks = [w.lower() for w in words(s)]
        if any(t in VERB_SIGNALS for t in toks):
            continue
        if any(VERB_SUFFIX.search(t) and len(t) > 3 for t in toks):
            continue
        flagged.append(s)
    return flagged


def battery(text: str) -> dict[str, object]:
    sents = sentences(text)
    body = "\n".join(prose_lines(text))
    out: dict[str, object] = {
        "chars": len(text),
        "prose_words": len(words(body)),
        "paragraphs": len(paragraphs(text)),
        "length": length_profile(sents),
        "joins": join_profile(sents),
        "subordinators": subordinator_density(body),
        "openings": repeated_openings(sents),
        # **Prose only.** `extraction`'s status line carries a bare U+2014 as its own separator
        # and `strip_em_dash` passes machine lines through untouched (§180.4), so counting the
        # raw unit would report one mark per status panel and call it a habit.
        "em_dashes_in_stored_prose": em_dashes(body),
        "fragment_candidates": fragment_candidates(sents),
    }
    if gloss_counts is not None:
        out["register_census_156"] = gloss_counts(body)
        out["register_census_156_hits"] = gloss_hits(body)
    else:
        out["register_census_156"] = "register_census.py not importable"
    return out


# ---------------------------------------------------------------------------------------
# The store, read through the debug-book verbs only
# ---------------------------------------------------------------------------------------


def verb(database: Path, *args: str) -> str:
    result = subprocess.run(
        ["uv", "run", "litharness", "--database", str(database), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
        check=False,
    )
    if result.returncode == 2:
        raise SystemExit(f"litharness {' '.join(args)} failed: {result.stderr}")
    return result.stdout


def split_export(markdown: str) -> dict[str, str]:
    """The rendered units of one export, keyed by their heading number."""
    units: dict[str, list[str]] = {}
    current: str | None = None
    for line in markdown.split("\n"):
        heading = CHAPTER_HEADING.match(line.strip())
        if heading:
            current = heading.group(1)
            units[current] = []
            continue
        if current is not None:
            units[current].append(line)
    return {
        key: "\n".join(lines).strip() for key, lines in units.items() if "".join(lines).strip()
    }


@dataclass
class StoreReport:
    label: str
    database: str
    units: dict[str, dict[str, object]] = field(default_factory=dict)
    decisions: list[dict[str, object]] = field(default_factory=list)
    acceptance_events: list[dict[str, object]] = field(default_factory=list)


def read_store(label: str, database: Path) -> StoreReport:
    report = StoreReport(label=label, database=str(database))
    units = split_export(verb(database, "export"))
    for key, text in sorted(units.items(), key=lambda kv: int(kv[0])):
        measures = battery(text)
        if not measures["prose_words"]:  # an undrafted unit renders as a placeholder line
            continue
        measures["text_sha256"] = sha256(text.encode("utf-8")).hexdigest()
        report.units[key] = measures

    events = json.loads(verb(database, "events", "--limit", "500", "--json") or "{}")
    for event in events.get("events", []):
        if event.get("event_type") == "ManuscriptRevisionAccepted" and event["payload"].get(
            "accepted"
        ):
            report.acceptance_events.append(event)

    report.decisions = all_decisions(database)
    return report


def all_decisions(database: Path) -> list[dict[str, object]]:
    """Every policy decision in the store, read off a copy.

    **The verbs cannot answer this one and that is the reason for the copy.** `why --scene N`
    prints `attempts` scoped to the *accepting* job, so the decisions belonging to a job that
    was poisoned before a `replan` reissued its beat are not reachable through any verb — and
    on the one store that has a reviser in it, three of the five reviser calls sit on exactly
    such a job. `events --json` names those decisions but carries no spend. The read below is
    read-only, against a copy in a scratch directory, and touches no live file: the
    `debug-book` rule is *do not open the database*, and this is the case it reserves for.
    """
    with tempfile.TemporaryDirectory(prefix="reviser-impact-") as scratch:
        copy = Path(scratch) / database.name
        copy.write_bytes(database.read_bytes())
        con = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "select decision_id, outcome, job_id, logical_id, attempt, provider, model, "
                "profile, invocations, total_tokens, cost_usd, reason, gates, decided_at "
                "from policy_decisions order by decided_at, rowid"
            ).fetchall()
        finally:
            con.close()
    keys = (
        "decision_id outcome job_id logical_id attempt provider model profile invocations "
        "total_tokens cost_usd reason gates decided_at"
    ).split()
    out = []
    for row in rows:
        record = dict(zip(keys, row))
        record["gates"] = json.loads(str(record["gates"])) if record["gates"] else []
        out.append(record)
    return out


def spend_table(report: StoreReport) -> dict[str, object]:
    rows: dict[str, dict[str, float]] = {}
    for decision in report.decisions:
        profile = str(decision.get("profile"))
        row = rows.setdefault(
            profile, {"decisions": 0, "invocations": 0, "tokens": 0, "cost_usd": 0.0}
        )
        row["decisions"] += 1
        row["invocations"] += decision.get("invocations") or 0
        row["tokens"] += decision.get("total_tokens") or 0
        row["cost_usd"] += decision.get("cost_usd") or 0.0
    return rows


def containment_table(report: StoreReport) -> dict[str, object]:
    """Every containment verdict in the store, and what the ladder then did with the text.

    `wasted` counts a reviser call whose adopted text the gate ladder afterwards refused: the
    stage runs in front of the ladder, so a refused attempt has already paid for a rewrite.
    """
    held = refused = wasted = 0
    reasons: list[str] = []
    outcomes = {
        (d["job_id"], d["attempt"]): d
        for d in report.decisions
        if d.get("profile") == "default"
    }
    for decision in report.decisions:
        for gate in decision["gates"]:
            if gate.get("rule_or_critic_id") != "revision.containment.v0":
                continue
            if gate.get("passed"):
                held += 1
                sibling = outcomes.get((decision["job_id"], decision["attempt"]))
                if sibling and sibling["outcome"] != "accept":
                    wasted += 1
            else:
                refused += 1
                if gate.get("detail"):
                    reasons.append(str(gate["detail"]))
    return {
        "calls": held + refused,
        "adopted": held,
        "discarded": refused,
        "adopted_then_refused_by_the_ladder": wasted,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="a store to measure; repeatable",
    )
    parser.add_argument("--json", type=Path, default=None, help="write the whole report here")
    args = parser.parse_args()

    out: dict[str, object] = {
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "stores": {},
    }
    for spec in args.store:
        label, _, path = spec.partition("=")
        database = Path(path)
        if not database.is_absolute():
            database = REPO_ROOT / path
        report = read_store(label, database)
        out["stores"][label] = {
            "database": report.database,
            "units": report.units,
            "spend_by_profile": spend_table(report),
            "containment": containment_table(report),
            "decisions": report.decisions,
            "acceptance": [
                {
                    "revision_id": event["revision_id"],
                    "logical_id": event["payload"].get("logical_id"),
                    "chars": event["payload"].get("chars"),
                    "em_dashes_removed": event["payload"].get("em_dashes_removed"),
                    "revised_by": event["payload"].get("revised_by"),
                    "decision_id": event["payload"].get("decision_id"),
                }
                for event in report.acceptance_events
            ],
        }

    text = json.dumps(out, indent=1, ensure_ascii=False)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.json} ({sha256(text.encode('utf-8')).hexdigest()[:16]})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
