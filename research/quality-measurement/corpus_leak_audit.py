"""Is any third-party prose committed to this repository, now or anywhere in its history?

This repository is public and its measurements run over corpora it does not own: Mother of
Learning (806k words, one author), ~68,000 RoyalRoad chapters, and the reviews attached to both.
Every one of those lives outside the working tree by design, but a results file that happened to
record a *passage* instead of a passage id would put someone else's novel into a public git
history, where deleting it later does not remove it.

The near-miss that prompted this: `taste_calibration.py --dump` writes an excerpt bundle holding
~294,363 words of Mother of Learning and RoyalRoad chapters, as a bridge between the interpreter
that can read the corpora and the interpreter that can drive the panel. It was staged and never
committed. It is now ignored. This module exists so that "never committed" is a checked fact
rather than a recollection, and so the check can run again after any new experiment.

**What counts as a leak here.** Not character names — `ablate.py` lists `Zorian, The, You,
Mother, Cyoria` in a comment explaining why an entity extractor picked function words, and a list
of proper nouns in a technical note is neither expression nor redistribution. Not our own
generated prose, which we own. What counts is a **long contiguous run of someone else's text**:
a string value long enough to be an excerpt rather than a citation.

**Scope is the whole history, not the working tree.** `git rev-list --objects --all` enumerates
every blob any commit ever pointed at, including files deleted since, so a leak that was
committed and then removed is still found.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

#: A string value at or above this many words is an excerpt rather than a citation. Deliberately
#: low: our own scenes run ~1,000 words, so this catches anything passage-sized and then the
#: report says which corpus it came from.
EXCERPT_WORDS = 120

#: Paths whose long strings are ours by construction. `toll-scenes.json` is this system's own
#: drafted prose and the plan and brief are prose we wrote.
OURS = (
    "corpora/toll-scenes.json",
    "plan/",
    "README.md",
    "PLAN.md",
    "CONTRIBUTING.md",
)

#: Fields that hold what a model *said*, never what it read. Every long string in this history
#: is one of these — 1,243 of them, all in `.text` — because `elicit` records the answer beside a
#: passage *id* and keys the prompt by digest, so the passage itself is never serialised. They are
#: reported and not failed on.
#:
#: **This is the audit's one soft spot and it is named rather than hidden.** A future results
#: file that put corpus text in a field called `text` would pass. What makes that unlikely rather
#: than impossible is that the leak-shaped mistake is writing a *new* field — an excerpt bundle,
#: a passage dump — and any new field name fails loudly. If a schema ever needs to record source
#: text, it must not call the field one of these.
RESPONSE_FIELDS = frozenset({"text", "result", "completion", "reason", "note", "reading"})

#: Below this many commits the history is shallow and the audit cannot do its job. It fails
#: rather than reporting clean, because a check that passes on a shallow clone is a check that
#: cannot fail — the shape of every proxy BRIEF §2 had to refute.
MIN_COMMITS = 50

#: Extensions worth opening. A `.py` file's long strings are code, and **`.md` is excluded on
#: purpose**: every markdown file in this repository is prose this project wrote — the plan, the
#: brief, the ledger, the research write-ups. Scanning them produced 1,257 "findings", all of
#: them our own documents, which is the shape of a check that cannot fail informatively. Corpus
#: text would arrive as a *data* field in a results file, and that is what this looks at.
DATA_SUFFIXES = (".json", ".jsonl", ".csv", ".txt")


def _run(args: list[str]) -> str:
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    ).stdout


def long_strings(payload: object, path: str = "") -> list[tuple[str, int, str]]:
    """Every string value in a decoded JSON structure that is excerpt-sized."""
    found: list[tuple[str, int, str]] = []
    if isinstance(payload, str):
        count = len(payload.split())
        if count >= EXCERPT_WORDS:
            found.append((path, count, payload[:160].replace("\n", " ")))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            found.extend(long_strings(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload[:400]):
            found.extend(long_strings(value, f"{path}[{index}]"))
    return found


def scan_blob(name: str, content: str) -> list[tuple[str, int, str]]:
    """Excerpt-sized strings in one blob, whatever shape it is in."""
    if name.endswith(".jsonl"):
        found = []
        for number, line in enumerate(content.splitlines()[:5000], start=1):
            try:
                found.extend(
                    (f"line{number}{p}", c, s) for p, c, s in long_strings(json.loads(line))
                )
            except json.JSONDecodeError:
                continue
        return found
    if name.endswith(".json"):
        try:
            return long_strings(json.loads(content))
        except json.JSONDecodeError:
            return []
    # csv/txt: a single run of prose with no JSON structure to walk.
    words = len(content.split())
    return [("<whole file>", words, content[:160].replace("\n", " "))] if words >= 2000 else []


def history_blobs() -> list[tuple[str, str]]:
    """(sha, path) for every blob any commit ever pointed at, deduplicated."""
    listing = _run(["git", "rev-list", "--objects", "--all"])
    seen: dict[str, str] = {}
    for line in listing.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        sha, path = parts
        if path.endswith(DATA_SUFFIXES) and not any(marker in path for marker in OURS):
            seen.setdefault(sha, path)
    return sorted(seen.items(), key=lambda pair: pair[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=int, default=EXCERPT_WORDS)
    parser.add_argument("--show", type=int, default=12, help="findings to print")
    parser.add_argument("--min-commits", type=int, default=MIN_COMMITS,
                        help="refuse to report clean below this depth")
    args = parser.parse_args(argv)

    commits = len(_run(["git", "rev-list", "--all"]).split())
    if commits < args.min_commits:
        print(
            f"REFUSING: {commits} commits reachable, below the {args.min_commits} floor. This is "
            "a shallow clone and the audit would report clean without having looked. Fetch the "
            "full history (actions/checkout with fetch-depth: 0) and run again.",
            file=sys.stderr,
        )
        return 2

    blobs = history_blobs()
    print(f"scanning {len(blobs)} data blobs across {commits} commits", file=sys.stderr)
    findings: list[tuple[str, str, str, int, str]] = []
    responses = 0
    for sha, path in blobs:
        content = _run(["git", "cat-file", "-p", sha])
        if not content:
            continue
        for field, count, sample in scan_blob(path, content):
            if count < args.words:
                continue
            leaf = field.rsplit(".", 1)[-1] if "." in field else field
            if leaf in RESPONSE_FIELDS:
                responses += 1
                continue
            findings.append((path, sha[:8], field, count, sample))

    if not findings:
        print(
            f"\nCLEAN: no excerpt-sized string outside a model-response field, across {commits} "
            f"commits and {len(blobs)} data blobs."
        )
        print(
            f"({responses} long strings sit in {sorted(RESPONSE_FIELDS)} — what the panel said, "
            f"never what it read. Threshold {args.words} words.)"
        )
        return 0

    print(f"\n{len(findings)} excerpt-sized strings found, in {len({f[0] for f in findings})} "
          "distinct paths:\n")
    by_path: dict[str, list[tuple[str, str, str, int, str]]] = {}
    for finding in findings:
        by_path.setdefault(finding[0], []).append(finding)
    for path, group in sorted(by_path.items(), key=lambda kv: -max(f[3] for f in kv[1])):
        worst = max(group, key=lambda f: f[3])
        print(f"  {path}: {len(group)} strings, longest {worst[3]} words at {worst[2]}")
        # ASCII-safe: this prints to a cp1252 console on Windows and a sample of prose will
        # otherwise raise UnicodeEncodeError and abort the audit mid-report.
        print(f"          {worst[4].encode('ascii', 'replace').decode('ascii')[:150]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
